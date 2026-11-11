"""No model/browser calls: isolate scripting's CAPS defaults without changing the prior experiment."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SPEC = importlib.util.spec_from_file_location(
    "codex_caps_ab", Path(__file__).resolve().parents[1] / "scripts/run-codex-scripting-caps-ab.py")
caps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(caps)


class CodexScriptingCapsTests(unittest.TestCase):
    def test_same_eighty_run_abba_schedule_both_scripting(self):
        plan = caps.plan()
        self.assertEqual(len(plan), 80)
        self.assertEqual([r["arm"] for r in plan[:2]], ["core", "default"])
        self.assertEqual([r["arm"] for r in plan[40:42]], ["default", "core"])
        self.assertEqual(caps.suite.ab.EXPECTED_TOOLS, {"core": 14, "default": 14})
        self.assertNotIn("KITSUNE_CAPS", caps.ARMS["default"])
        self.assertTrue(all(env["KITSUNE_SCRIPTING"] == "1" for env in caps.ARMS.values()))
        for new, original in zip(plan, caps._ORIGINAL_PLAN):
            for key in ("seq", "task", "track", "repeat"):
                self.assertEqual(new[key], original[key])
        self.assertIn(Path(caps.__file__), caps.suite.RUNNER_FILES)

    def test_selected_caps_reach_the_shared_runner_without_allowlist(self):
        from kitsune_benchmark import external, miniwob
        with patch.object(miniwob, "BenchmarkServer", return_value=MagicMock()), \
             patch.object(external, "verify_source"), \
             patch("kitsune_benchmark.smoke.run_pair") as run:
            for item in caps.plan()[:2]:
                caps.suite.ab.run_one(item, "/pinned", caps.suite.BENCHMARK, harness="codex")
                kwargs = run.call_args.kwargs
                self.assertEqual(kwargs["kitsune_env"], caps.ARMS[item["arm"]])
                self.assertEqual(kwargs["harness"], "codex")
                self.assertIsNone(kwargs["enabled_tools"])

    def test_catalog_probe_requires_python_in_both_arms(self):
        tools = ["browser_run_python"] + [f"tool_{i}" for i in range(13)]
        with patch.object(caps.suite, "resolve", return_value="/codex"), \
             patch.object(caps.suite, "codex_environment", return_value={}), \
             patch.object(caps.suite.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(tools))) as run:
            self.assertEqual(set(caps.suite.catalogs("/pinned")), {"core", "default"})
            self.assertEqual(run.call_args_list[0].kwargs["env"], caps.ARMS["core"])
            self.assertEqual(run.call_args_list[1].kwargs["env"], caps.ARMS["default"])

    def test_ratios_are_default_over_core(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            rows = [{"task": "t", "repeat": 0, "track": "personal", "arm": arm,
                     "scorable": True, "success": True, "execution_status": "completed_unscored",
                     "input": value, "output": 10, "cached_input": 0, "calls": 1, "elapsed": 1,
                     "python_calls": 0, "python_errors": 0}
                    for arm, value in (("core", 100), ("default", 50))]
            (out / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            report = caps.suite.analyze(out)["tracks"]["all"]
            self.assertEqual(report["joint_input_ratio"], .5)
            self.assertEqual(report["joint_cells"], 1)


if __name__ == "__main__":
    unittest.main()
