"""No-model coverage for the ego(lite) exhibition wrapper and the exhibition target list."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from kitsune_benchmark.miniwob import config
from kitsune_benchmark.external import TOOLS, run_external
from kitsune_benchmark.smoke import ALL_TARGETS, EXHIBITION_TARGETS, TARGETS, run_pair

WRAPPER = Path(__file__).resolve().parents[1] / "kitsune_benchmark/ego_mcp.py"
FAKE = '''#!/bin/sh
if [ "$1" = skill ]; then echo "GUIDE TEXT" >&2; exit 0; fi
code=$(cat)
case "$code" in *fail*) echo "boom"; exit 1;; esac
echo "ran: $code"
'''


class EgoWrapperTest(unittest.TestCase):
    def call(self, *messages):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "ego-browser"
            fake.write_text(FAKE)
            fake.chmod(0o755)
            lines = "".join(json.dumps(m) + "\n" for m in messages)
            done = subprocess.run([sys.executable, str(WRAPPER)], input=lines, capture_output=True, text=True,
                                  timeout=30, env={**os.environ, "EGO_BROWSER_BIN": str(fake)})
        return [json.loads(line) for line in done.stdout.splitlines()]

    def test_lists_one_tool_with_the_vendor_guide(self):
        replies = self.call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                            {"jsonrpc": "2.0", "method": "notifications/initialized"},
                            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual([r["id"] for r in replies], [1, 2])
        tools = replies[1]["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["run_script"])
        self.assertIn("GUIDE TEXT", tools[0]["description"])

    def test_runs_code_on_stdin_and_reports_failures(self):
        ok, failed, unknown = self.call(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "run_script", "arguments": {"code": "hi"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "run_script", "arguments": {"code": "fail"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "other", "arguments": {}}})
        self.assertEqual(ok["result"], {"isError": False, "content": [{"type": "text", "text": "ran: hi"}]})
        self.assertTrue(failed["result"]["isError"])
        self.assertIn("error", unknown)


class ExhibitionTargetsTest(unittest.TestCase):
    def test_head_to_head_defaults_are_unchanged(self):
        self.assertEqual(TARGETS, ("playwright", "kitsune"))
        self.assertEqual(ALL_TARGETS, TARGETS + EXHIBITION_TARGETS)
        self.assertEqual(TOOLS["aside"], ("repl",))
        self.assertEqual(TOOLS["ego"], ("run_script",))

    def test_external_plan_accepts_exhibition_targets(self):
        plan = run_external(kind="miniwob", targets=("aside", "ego"), harness="claude")
        self.assertEqual(plan["planned_model_runs"], 14)
        self.assertEqual(plan["ui_tools"], {"aside": ("repl",), "ego": ("run_script",)})
        with self.assertRaises(ValueError):
            run_external(kind="miniwob", targets=("nope",), harness="claude")

    @patch("kitsune_benchmark.external.run_pair", side_effect=AssertionError("must reject before execution"))
    @patch("kitsune_benchmark.external.verify_source", side_effect=AssertionError("must reject before setup"))
    def test_external_exhibition_rejects_live_and_mixed_task_sets(self, verify, pair):
        for target in EXHIBITION_TARGETS:
            for kind in (None, "live"):
                for execute in (False, True):
                    with self.subTest(target=target, kind=kind, execute=execute):
                        with self.assertRaisesRegex(ValueError, "external MiniWoB"):
                            run_external(kind=kind, targets=(target,), execute=execute)
        plan = run_external(task_ids=["mw-login-user"], targets=("ego",))
        self.assertEqual(plan["planned_model_runs"], 1)

    @patch("kitsune_benchmark.smoke.resolve", side_effect=AssertionError("must reject before harness setup"))
    def test_pair_exhibition_rejects_other_tracks_before_execution(self, resolve):
        for target in EXHIBITION_TARGETS:
            for scope, task in (("smoke", {}), ("benchmark", {"kind": "miniwob"}),
                                ("personal", {}), ("gallery", {}), ("coexistence", {}),
                                ("external", {}), ("external", {"kind": "live"})):
                for execute in (False, True):
                    with self.subTest(target=target, scope=scope, task=task, execute=execute):
                        with self.assertRaisesRegex(ValueError, "external MiniWoB"):
                            run_pair(targets=(target,), artifact_scope=scope, execute=execute,
                                     experiment_spec={**config(), "selected_task": task})
        plan = run_pair(targets=EXHIBITION_TARGETS, artifact_scope="external", enabled_tools=TOOLS,
                        experiment_spec={**config(), "selected_task": {"kind": "miniwob"}})
        self.assertFalse(plan["model_invoked"])

    def test_exhibition_pair_requires_the_code_tool_allowlist(self):
        for tools in (None, {}, {"aside": ("exec",)}, {"aside": ("repl", "exec")}):
            with self.subTest(tools=tools), self.assertRaisesRegex(ValueError, "allowlist"):
                run_pair(targets=("aside",), artifact_scope="external", enabled_tools=tools,
                         experiment_spec={**config(), "selected_task": {"kind": "miniwob"}})

    def test_ego_binary_override_is_declared_to_the_harness(self):
        from kitsune_benchmark.specs import Server
        # Stop at server construction, before starting any MCP, browser or model.
        captured = []

        def server(*args, **kwargs):
            result = Server(*args, **kwargs)
            if result.id == "ego":
                captured.append(result)
                raise RuntimeError("captured ego server")
            return result

        for env, expected in (({}, ()), ({"EGO_BROWSER_BIN": "/tmp/test-ego"}, ("EGO_BROWSER_BIN",))):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as directory, \
                    patch.dict(os.environ, env, clear=True), \
                    patch("kitsune_benchmark.smoke.ROOT", Path(directory)), \
                    patch("kitsune_benchmark.smoke.resolve", return_value="fake-codex"), \
                    patch("kitsune_benchmark.smoke.harness_environment", return_value={}), \
                    patch("kitsune_benchmark.smoke.harness_preflight"), \
                    patch("kitsune_benchmark.smoke.Path.is_file", return_value=True), \
                    patch("kitsune_benchmark.smoke.Path.exists", return_value=True), \
                    patch("kitsune_benchmark.smoke.subprocess.run", return_value=Mock(stdout="/tmp/firefox")), \
                    patch("kitsune_benchmark.smoke.private_ports", return_value=(51000, 51001)), \
                    patch("kitsune_benchmark.smoke.copy_extension"), \
                    patch("kitsune_benchmark.smoke.Server", side_effect=server):
                with self.assertRaisesRegex(RuntimeError, "captured ego server"):
                    run_pair(execute=True, targets=("ego",), artifact_scope="external", enabled_tools=TOOLS,
                             experiment_spec={**config(), "selected_task": {"kind": "miniwob"}})
            self.assertEqual(captured[-1].env_vars, expected)


if __name__ == "__main__":
    unittest.main()
