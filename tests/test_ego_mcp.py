"""No-model coverage for the ego(lite) exhibition wrapper and the exhibition target list."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from kitsune_benchmark.external import TOOLS, run_external
from kitsune_benchmark.smoke import ALL_TARGETS, EXHIBITION_TARGETS, TARGETS

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


if __name__ == "__main__":
    unittest.main()
