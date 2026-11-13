"""Claude-only orchestration/usage/catalog guards, without inference or browsers."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "claude_caps_ab", Path(__file__).resolve().parents[1] / "scripts/run-claude-scripting-caps-ab.py")
caps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(caps)
suite = caps.suite


class ClaudeScriptingCapsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pair_dir = self.root / "pair"
        self.run_dir = self.pair_dir / "run"
        self.run_dir.mkdir(parents=True)
        self.events = self.run_dir / "events.jsonl"
        tools = ["mcp__browser__browser_run_python"] + [f"mcp__browser__tool{i}" for i in range(13)]
        events = [{"type": "system", "subtype": "init", "tools": tools},
                  {"type": "assistant", "message": {"id": "m1", "usage": {
                      "input_tokens": 100, "cache_read_input_tokens": 600, "cache_creation_input_tokens": 300},
                      "content": [{"type": "tool_use", "id": "t1", "name": tools[0],
                                   "input": {"code": "result = tab.snapshot()"}}]}},
                  {"type": "assistant", "message": {"id": "m1", "content": []}},
                  {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                              "is_error": True, "content": "error"}]}}]
        self.events.write_text("\n".join(json.dumps(e) for e in events))
        self.pair = {"pair_dir": str(self.pair_dir), "results": {"kitsune": {
            "run_dir": str(self.run_dir), "execution_status": "completed_unscored",
            "benchmark_evaluation": {"scorable": True, "task_success": True},
            "usage": {"input_tokens": 1000, "output_tokens": 20, "cached_input_tokens": 600},
            "mcp_calls": 1, "elapsed_sec": 2, "list_price_cost_usd": .1}}}

    def test_plan_and_usage_stay_claude_separate_from_codex(self):
        self.assertEqual(suite.HARNESS, "claude")
        self.assertEqual(suite.model(), "claude-opus-5-5")
        self.assertEqual(len(caps.plan()), 80)
        self.assertEqual([r["arm"] for r in caps.plan()[:2]], ["core", "default"])
        self.assertEqual([r["arm"] for r in caps.plan()[40:42]], ["default", "core"])
        row = suite.metrics(self.pair)
        self.assertEqual((row["published"], row["requests"], row["first_input"], row["cost"]), (14, 1, 1000, .1))
        self.assertEqual((row["python_calls"], row["python_errors"]), (1, 1))
        self.assertIsNone(row["relay_published"])
        self.assertIsNone(suite.stop_reason({**row, "track": "miniwob", "arm": "core"}))

    def test_missing_metrics_or_catalog_and_quota_failure_stop(self):
        row = {**suite.metrics(self.pair), "track": "miniwob", "arm": "core"}
        for updates in ({"published": None}, {"cost": None}, {"requests": 0}, {"first_input": None},
                        {"execution_status": "harness_error"}, {"track": "personal"}):
            self.assertIsNotNone(suite.stop_reason({**row, **updates}, True))
        self.assertIsNone(suite.stop_reason({**row, "track": "personal", "relay_published": 14}))

    def test_orchestration_records_claude_and_does_not_skip_failed_attempt(self):
        args = SimpleNamespace(out=str(self.root / "cohort"), kitsune_project="/pinned", kitsune_sha="pinned",
                               limit=None, continue_unstarted=True)
        with patch.object(suite.ab, "git", side_effect=lambda p, *a: "pinned" if a[0] == "rev-parse" else ""), \
             patch.object(suite, "catalogs", return_value={}), \
             patch.object(suite.ab, "plan", return_value=caps.plan()[:2]), \
             patch.object(suite.ab, "run_one", return_value=self.pair) as run, \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.pair["results"]["kitsune"]["execution_status"] = "harness_error"
            self.assertEqual(suite.do_run(args), 2)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs["harness"], "claude")
            self.assertEqual(suite.ab.load_log(Path(args.out))[0]["harness"], "claude")
            with self.assertRaisesRegex(ValueError, "Prior failed"):
                suite.do_run(args)

    def test_analysis_adds_observed_cost_and_requests(self):
        out = self.root / "cohort"
        out.mkdir()
        rows = [{**suite.metrics(self.pair), **r} for r in caps.plan()[:2]]
        rows[1].update(cost=.05, requests=2)
        (out / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        report = suite.analyze(out)
        self.assertEqual(report["harness"], "claude")
        all_tracks = report["tracks"]["all"]
        self.assertEqual(all_tracks["joint_cost_ratio"], .5)
        self.assertEqual(all_tracks["joint_requests_ratio"], 2)
        self.assertEqual(all_tracks["arms"]["core"]["first_input_median"], 1000)


if __name__ == "__main__":
    unittest.main()
