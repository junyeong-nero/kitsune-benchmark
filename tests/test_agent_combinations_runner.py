"""No model/browser tests for the approved cap, audit latch and failure retention."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("combinations_runner", ROOT / "scripts/run-agent-combinations.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def result(row):
    return {**row, "harness": "claude_code" if row["baseline"].startswith("claude-") else "codex",
        "reported_model": row["model"], "execution_status": "completed_unscored", "scorable": True,
        "success": True, "safety_pass": True, "input": 100, "cached_input": 80, "output": 10,
        "elapsed": 20, "adjusted_elapsed": 18, "outside_navigation": 0, "violations": []}


class RunnerTests(unittest.TestCase):
    def manifest(self, out):
        value = {"plan": runner.plan(), "cli_ready": True, "api_budget_usd": 0}
        (out / "manifest.json").write_text(json.dumps(value))
        return value

    def test_default_invocation_stops_at_nine_and_requires_matching_audit(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "verify"), \
                patch.object(runner, "run_one", side_effect=lambda row, *_: result(row)) as run:
            out = Path(directory)
            self.manifest(out)
            self.assertEqual(runner.do_run(out, 27), 0)
            self.assertEqual(run.call_count, 9)
            self.assertEqual(len(runner.load_rows(out)), 9)
            with self.assertRaises(FileNotFoundError):
                runner.do_run(out, 27)
            audit = out / "first-nine-audit.json"
            audit.write_text(json.dumps({"continue": True, "first_nine_sha256": "wrong"}))
            with self.assertRaisesRegex(ValueError, "audit"):
                runner.do_run(out, 27)
            audit.write_text(json.dumps({"continue": True, "first_nine_sha256": hashlib.sha256((out / "runs.jsonl").read_bytes()).hexdigest()}))
            self.assertEqual(runner.do_run(out, 1), 0)
            self.assertEqual(run.call_count, 10)
            self.assertEqual(len(list(out.glob("attempt-*/started.json"))), 10)

    def test_missing_usage_stops_and_keeps_the_attempt(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "verify"), \
                patch.object(runner, "run_one", side_effect=lambda row, *_: {**result(row), "input": None}) as run:
            out = Path(directory)
            self.manifest(out)
            self.assertEqual(runner.do_run(out, 27), 2)
            self.assertEqual(run.call_count, 1)
            self.assertIsNone(runner.load_rows(out)[0]["input"])
            self.assertTrue((out / "stopped.json").is_file())
            with self.assertRaisesRegex(ValueError, "Prior stop"):
                runner.do_run(out, 27)
            self.assertEqual(run.call_count, 1)

    def test_partial_start_is_never_automatically_retried(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "verify"), \
                patch.object(runner, "run_one", side_effect=ValueError("setup failed")) as run:
            out = Path(directory)
            self.manifest(out)
            with self.assertRaisesRegex(ValueError, "setup failed"):
                runner.do_run(out, 1)
            with self.assertRaisesRegex(ValueError, "no completed row"):
                runner.do_run(out, 1)
            self.assertEqual(run.call_count, 1)
            self.assertTrue((out / "attempt-001/started.json").is_file())

    def test_ordinary_task_failure_is_not_an_infrastructure_stop(self):
        row = result(runner.plan()["attempts"][0])
        self.assertIsNone(runner.stop_reason({**row, "success": False}))
        for change in ({"reported_model": "substitute"}, {"harness": "claude-api"},
                       {"outside_navigation": 1}, {"adjusted_elapsed": -1}, {"teardown_error": "unknown"}):
            with self.subTest(change=change):
                self.assertIsNotNone(runner.stop_reason({**row, **change}))

    def test_tampered_plan_is_rejected_before_runtime_or_inference(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "verify") as verify, \
                patch.object(runner, "run_one") as run:
            out = Path(directory)
            value = self.manifest(out)
            value["plan"]["attempts"][0]["model"] = "substitute"
            (out / "manifest.json").write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "authorized"):
                runner.do_run(out, 1)
            verify.assert_not_called()
            run.assert_not_called()

    def test_incomplete_preflight_cannot_be_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preflight.json"
            path.write_text(json.dumps({"model_invoked": False, "checks": {}}))
            with patch.object(runner, "pins") as pins, self.assertRaisesRegex(ValueError, "21-cell"):
                runner.freeze(path, Path(directory) / "cohort", ROOT)
            pins.assert_not_called()
            self.assertFalse((Path(directory) / "cohort").exists())

    def test_aside_only_uses_native_repl_without_changing_its_schema(self):
        tools = [{"name": "repl", "inputSchema": {"properties": {"code": {"type": "string"}}}}, {"name": "exec"}]
        value = runner.canonical({"serverInfo": {"name": "aside"}}, [{"tools": tools}], "aside")
        self.assertEqual(value["tools"], tools[:1])
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            runner.canonical({"serverInfo": {}}, [{"tools": tools, "nextCursor": "more"}], "aside")


if __name__ == "__main__":
    unittest.main()
