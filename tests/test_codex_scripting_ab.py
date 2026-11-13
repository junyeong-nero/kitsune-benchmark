"""No model/browser calls: Codex A/B orchestration, metrics and resume boundaries."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

SPEC = importlib.util.spec_from_file_location(
    "codex_scripting_ab", Path(__file__).resolve().parents[1] / "scripts/run-codex-scripting-ab.py")
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


class CodexScriptingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pair_dir = self.root / "pair"
        self.pair_dir.mkdir()
        self.run_dir = self.pair_dir / "run"
        self.run_dir.mkdir()
        self.events = self.run_dir / "events.jsonl"
        self.events.write_text("")
        self.pair = {"pair_dir": str(self.pair_dir), "results": {"kitsune": {
            "run_dir": str(self.run_dir), "execution_status": "completed_unscored",
            "benchmark_evaluation": {"scorable": True, "task_success": True},
            "usage": {"input_tokens": 1000, "cached_input_tokens": 700, "output_tokens": 20},
            "mcp_calls": 1, "elapsed_sec": 2}}}

    def test_codex_metrics_do_not_invent_requests_cost_or_catalog(self):
        item = {"id": "c1", "type": "mcp_tool_call", "server": "browser", "tool": "browser_run_python",
                "arguments": {"code": "result = tab.snapshot()"}, "status": "completed",
                "result": {"isError": True, "content": [{"type": "text", "text": "error"}]}}
        self.events.write_text("\n".join(json.dumps(e) for e in (
            {"type": "item.started", "item": item}, {"type": "item.completed", "item": item},
            {"type": "turn.completed", "usage": {"input_tokens": 1000}})))
        row = suite.metrics(self.pair)
        self.assertEqual((row["input"], row["cached_input"], row["python_calls"], row["python_errors"]),
                         (1000, 700, 1, 1))
        self.assertIsNone(row["published"])
        for key in ("requests", "cost", "first_input"):
            self.assertNotIn(key, row)
        self.assertEqual(row["tamper_hits"], 0)

    def test_relay_catalog_and_stop_conditions(self):
        (self.pair_dir / "kitsune-native-metadata.json").write_text(json.dumps({"tools_pages": [
            {"tools": [{"name": f"tool_{i}"} for i in range(14)]}]}))
        row = {"track": "personal", "arm": "scripting", **suite.metrics(self.pair)}
        self.assertEqual(row["published"], 14)
        self.assertIsNone(suite.stop_reason(row))
        for updates in ({"published": None}, {"published": 27}, {"scorable": False},
                        {"execution_status": "harness_error"}, {"input": None}):
            self.assertIsNotNone(suite.stop_reason({**row, **updates}))
        self.assertIsNone(suite.stop_reason({**row, "success": False}), "graded failures remain valid")
        self.assertIsNone(suite.stop_reason({**row, "track": "miniwob", "published": None}))

    def test_shared_runner_defaults_stay_claude_and_codex_is_explicit(self):
        from kitsune_benchmark import external, miniwob
        run = suite.ab.plan()[0]
        fixture = MagicMock()
        with patch.object(miniwob, "BenchmarkServer", return_value=fixture), \
             patch.object(external, "verify_source"), \
             patch("kitsune_benchmark.smoke.run_pair", return_value=self.pair) as pair:
            suite.ab.run_one(run, "/pinned")
            self.assertEqual((pair.call_args.kwargs["harness"], pair.call_args.kwargs["executable"]),
                             ("claude", "claude"))
            suite.ab.run_one(run, "/pinned", harness="codex")
            self.assertEqual((pair.call_args.kwargs["harness"], pair.call_args.kwargs["executable"]),
                             ("codex", "codex"))
            self.assertIsNone(pair.call_args.kwargs["enabled_tools"])
            with self.assertRaises(ValueError):
                suite.ab.run_one(run, "/pinned", harness="claude-api")

    def run_suite(self, out, *, limit=None, fail=False, sha="pinned", continue_unstarted=False):
        args = SimpleNamespace(out=str(out), kitsune_project="/pinned", kitsune_sha=sha, limit=limit,
                               continue_unstarted=continue_unstarted)
        if fail:
            self.pair["results"]["kitsune"]["execution_status"] = "harness_error"
        with patch.object(suite.ab, "git", side_effect=lambda path, *a: "pinned" if a[0] == "rev-parse" else ""), \
             patch.object(suite, "catalogs", return_value={}), \
             patch.object(suite, "model", return_value="gpt-6-luna"), \
             patch.object(suite.ab, "plan", return_value=suite.ab.plan()[:2]), \
             patch.object(suite.ab, "run_one", return_value=self.pair) as run, \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = suite.do_run(args)
            return code, run.call_count

    def test_resume_valid_rows_and_analyze_without_cost(self):
        out = self.root / "cohort"
        self.assertEqual(self.run_suite(out, limit=1), (0, 1))
        self.assertEqual(self.run_suite(out), (0, 1))
        self.assertEqual(self.run_suite(out), (0, 0))
        report = suite.analyze(out)
        self.assertEqual(report["runs"], 2)
        self.assertEqual(report["tracks"]["all"]["joint_input_ratio"], 1)
        self.assertEqual(report["tracks"]["all"]["joint_cells"], 1)
        self.assertNotIn("cost", report["tracks"]["all"]["arms"]["legacy"])

    def test_failure_stops_and_is_not_skipped_on_resume(self):
        out = self.root / "failed"
        self.assertEqual(self.run_suite(out, fail=True), (2, 1))
        with self.assertRaisesRegex(ValueError, "Prior failed"):
            self.run_suite(out)

    def test_explicit_continuation_preserves_raw_attempt_and_manifest(self):
        out = self.root / "unstarted"
        self.pair["results"]["kitsune"]["benchmark_evaluation"] = {"scorable": False, "task_success": None}
        (self.run_dir / "evaluation.json").write_text(json.dumps({
            "episode_starts": 0, "telemetry_errors": 0, "outcome": "no_terminal_reward"}))
        self.assertEqual(self.run_suite(out), (2, 1))
        manifest = (out / "manifest.json").read_bytes()
        first_row = (out / "runs.jsonl").read_bytes()
        self.pair["results"]["kitsune"]["benchmark_evaluation"] = {"scorable": True, "task_success": True}
        self.assertEqual(self.run_suite(out, continue_unstarted=True), (0, 1))
        self.assertEqual((out / "manifest.json").read_bytes(), manifest)
        self.assertTrue((out / "runs.jsonl").read_bytes().startswith(first_row))
        self.assertTrue((out / "continuation.json").exists())
        report = suite.analyze(out)["tracks"]["all"]
        self.assertEqual(report["arms"]["legacy"]["unstarted"], 1)
        self.assertEqual(report["joint_cells"], 0)
        with self.assertRaisesRegex(ValueError, "Prior failed"):
            self.run_suite(out)

    def test_continuation_never_ignores_execution_or_telemetry_errors(self):
        grade = self.run_dir / "evaluation.json"
        grade.write_text(json.dumps({"episode_starts": 0, "telemetry_errors": 0,
                                     "outcome": "no_terminal_reward"}))
        row = {"track": "miniwob", "arm": "scripting", **suite.metrics(self.pair), "scorable": False}
        self.assertIsNone(suite.stop_reason(row, True))
        self.assertIsNotNone(suite.stop_reason({**row, "execution_status": "harness_error"}, True))
        grade.write_text(json.dumps({"episode_starts": 0, "telemetry_errors": 1,
                                     "outcome": "no_terminal_reward"}))
        self.assertIsNotNone(suite.stop_reason(row, True))

    def test_mixed_cohorts_and_source_changes_refused(self):
        out = self.root / "old"
        out.mkdir()
        (out / "runs.jsonl").write_text('{"harness":"claude","seq":1}\n')
        with self.assertRaisesRegex(ValueError, "no Codex manifest"):
            self.run_suite(out)
        with self.assertRaisesRegex(ValueError, "revision changed"):
            self.run_suite(self.root / "new", sha="different")
        clean = self.root / "clean"
        self.run_suite(clean, limit=1)
        path = clean / "manifest.json"
        data = json.loads(path.read_text())
        data["model"] = "different"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "different experiment"):
            self.run_suite(clean)


if __name__ == "__main__":
    unittest.main()
