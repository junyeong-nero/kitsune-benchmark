import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from kitsune_benchmark.__main__ import main


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.server = root / "server.json"
        self.server.write_text(json.dumps({"id": "test", "command": "test-mcp", "args": []}))
        self.task = root / "task.json"
        self.task.write_text(json.dumps({"id": "task", "prompt": "test prompt"}))
        self.flags = ["--server", str(self.server), "--task", str(self.task), "--model", "fixed-model"]

    def test_plan_outputs_json_without_processes(self):
        out = io.StringIO()
        with patch("kitsune_benchmark.adapter.resolve", return_value="/codex"), patch(
                "subprocess.Popen", side_effect=AssertionError("No model in plan")), redirect_stdout(out):
            code = main(["plan", *self.flags])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out.getvalue())["model_invoked"])

    def test_run_requires_operator_confirmation(self):
        out = io.StringIO()
        with redirect_stdout(out), patch("subprocess.Popen", side_effect=AssertionError("No confirmation")):
            code = main(["run", *self.flags])
        self.assertEqual(code, 2)
        self.assertIn("No API fallback", out.getvalue())

    def test_execution_status_exit_codes_and_arguments(self):
        for status, expected in (("completed_unscored", 0), ("invalid_trace", 3), ("timeout", 3)):
            with self.subTest(status=status), patch("kitsune_benchmark.__main__.run",
                    return_value={"execution_status": status}) as mocked, redirect_stdout(io.StringIO()):
                code = main(["run", *self.flags, "--confirm-isolated-browser", "--timeout", "17"])
                self.assertEqual(code, expected)
                self.assertTrue(mocked.call_args.kwargs["confirm_isolated_browser"])
                self.assertEqual(mocked.call_args.kwargs["timeout"], 17)

    def test_claude_model_override_reaches_plans(self):
        flags = ["--harness", "claude-api", "--claude-model", "claude-opus-5-5", "--max-budget-usd-per-run", "5"]
        for command in (["personal", "--all"], ["gallery"]):
            with self.subTest(command=command[0]):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(main([*command, *flags]), 0)
                result = json.loads(out.getvalue())
                self.assertEqual(result["model"], "claude-opus-5-5")
                self.assertEqual(result["worst_case_usd"], result["planned_model_runs"] * 5.0)

    def test_codex_model_override_reaches_plans(self):
        for command in (["personal", "--all"], ["gallery"], ["coexistence"], ["benchmark"]):
            with self.subTest(command=command[0]):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(main([*command, "--harness", "codex", "--codex-model", "gpt-6.1-sol"]), 0)
                result = json.loads(out.getvalue())
                self.assertEqual(result.get("model") or result["config"]["model"], "gpt-6.1-sol")
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            main(["personal", "--harness", "claude", "--codex-model", "gpt-6.1-sol"])

    def test_elicitation_policy_reaches_session_config_and_is_recorded(self):
        # #59: --elicitation sets the relay's answer to Kitsune's prompts (personal_session.py) on the relay tracks.
        from kitsune_benchmark.personal import runnable_ids
        from kitsune_benchmark.specs import Server
        tracks = (("personal", "kitsune_benchmark.personal", runnable_ids()[0]),
                  ("gallery", "kitsune_benchmark.smoke", "mm-audio"),  # run_gallery imports run_pair when called
                  ("coexistence", "kitsune_benchmark.coexistence", "co-typing-01"))
        for (command, module, task), policy in ((track, policy) for track in tracks
                                                          for policy in (None, "decline", "accept")):
            expected = policy or "decline"
            flag = ["--elicitation", policy] if policy else []
            with self.subTest(command=command, policy=policy), tempfile.TemporaryDirectory() as folder:
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(main([command, "--task", task, *flag]), 0)
                self.assertEqual(json.loads(out.getvalue())["elicitation"], expected)
                specs, settings = [], {}
                def run_pair(**kwargs):
                    specs.append(kwargs["experiment_spec"])
                    for target in kwargs["targets"]:
                        prompt = kwargs["task_for_target"](target)
                        wrapped = kwargs["prepare_server"](target, Server(target, "node", ("cli.js",)), prompt, Path(folder))
                        settings[target] = json.loads(Path(wrapped.args[-1]).read_text())["elicitation"]
                    return {"pair_dir": folder, "results": {t: {"benchmark_evaluation": {"scorable": False}}
                                                             for t in kwargs["targets"]}}
                out = io.StringIO()
                with patch(module + ".run_pair", side_effect=run_pair), redirect_stdout(out):
                    main([command, "--task", task, *flag, "--execute"])
                result = json.loads(out.getvalue())
                self.assertEqual(settings, {"playwright": expected, "kitsune": expected})
                self.assertEqual(specs[0]["elicitation"], expected, "the pair manifest records the experiment")
                self.assertEqual(result["elicitation"], expected)
                self.assertEqual(json.loads(Path(result["suite_summary_path"]).read_text())["elicitation"], expected)
                pair = json.loads((Path(folder) / f"{command}-summary.json").read_text())
                self.assertEqual(pair["elicitation"], expected)
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            main(["personal", "--elicitation", "approve"])
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            main(["external", "--elicitation", "accept"])  # no relay, no prompts to answer

    def test_claude_overrides_rejected_for_codex(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            main(["personal", "--harness", "codex", "--claude-model", "claude-opus-5-5"])

    def test_subscription_harness_is_default_and_api_billing_needs_opt_in(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["personal"]), 0)
        self.assertEqual(json.loads(out.getvalue())["harness"], "claude")
        for harness in ("claude-api", "claude-api-full"):
            with self.subTest(harness=harness), redirect_stdout(io.StringIO()), \
                    patch("subprocess.Popen", side_effect=AssertionError("no process")), self.assertRaises(SystemExit):
                main(["personal", "--harness", harness, "--execute"])

    def test_override_leaves_config_untouched(self):
        from kitsune_benchmark.adapter import with_claude_overrides
        spec = {"claude_code": {"model": "claude-haiku-5-5", "max_budget_usd_per_run": 0.5}}
        changed = with_claude_overrides(spec, "claude-opus-5-5", 5)
        self.assertEqual(changed["claude_code"], {"model": "claude-opus-5-5", "max_budget_usd_per_run": 5.0})
        self.assertEqual(spec["claude_code"]["model"], "claude-haiku-5-5")
        with self.assertRaises(ValueError):
            with_claude_overrides(spec, max_budget_usd_per_run=0)


if __name__ == "__main__":
    unittest.main()
