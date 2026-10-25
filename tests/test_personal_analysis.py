import json
from pathlib import Path
import tempfile
import unittest

from kitsune_benchmark.personal_analysis import analyze_run, analyze_suite, native_error


class PersonalAnalysisTests(unittest.TestCase):
    def fixture(self, root):
        run = root / "run"
        run.mkdir()
        events = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "tool": "browser_snapshot",
                   "result": {"content": [{"type": "text", "text": "snapshot"}]}}}]
        (run / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
        result = {"run_dir": str(run), "execution_status": "completed_unscored", "elapsed_sec": 10,
                  "mcp_calls": 1, "usage": {"input_tokens": 100, "cached_input_tokens": 70, "output_tokens": 2},
                  "benchmark_evaluation": {"scorable": True, "task_success": True, "functional_success": True,
                    "safety_pass": True, "seeded_tabs_preserved": True, "harness_mcp_calls": 4, "harness_seconds": 2}}
        pair = {"pair_dir": str(root), "personal_task": "test-task", "variant": 0, "results": {"kitsune": result}}
        return pair, result

    def test_error_detection_covers_native_and_json_wrapped_errors(self):
        for result in ({"isError": True}, {"content": [{"type": "text", "text": "### Error\ninvalid ref"}]},
                       {"content": [{"type": "text", "text": '{"error":"stale ref"}'}]},
                       {"content": [{"type": "text", "text": '{"ok":false}'}]}):
            self.assertTrue(native_error(result))
        self.assertFalse(native_error({"content": [{"type": "text", "text": "ordinary snapshot"}]}))

    def test_missing_diagnostics_stay_null_not_measured_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            pair, result = self.fixture(Path(folder))
            row = analyze_run(pair, "kitsune", result)
            self.assertFalse(row["native_diagnostics_available"])
            self.assertIsNone(row["agent_native_rpc_sec"])
            self.assertIsNone(row["setup_sec"])
            self.assertIsNone(row["enabled_schema_chars"])
            self.assertEqual(row["noncached_input_tokens"], 30)
            self.assertEqual(row["agent_tool_sequence"], ["browser_snapshot"])

    def test_phases_and_enabled_schemas_are_not_double_counted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pair, result = self.fixture(root)
            def rpc(role, method, tool, offset, duration, cached=False):
                return {"kind": "rpc_completed", "role": role, "method": method, "tool": tool,
                    "offset_sec": offset, "duration_sec": duration, "cached": cached,
                    "response_text_chars": 20, "response_text_bytes": 25, "is_error": False}
            records = [rpc("agent", "initialize", None, .2, .2),
                       rpc("harness", "tools/call", "browser_tabs", 1, .1, True),
                       {"kind": "readiness_wait", "duration_sec": .5},
                       {"kind": "setup_completed", "offset_sec": 2, "duration_sec": 1.8},
                       rpc("agent", "tools/call", "browser_snapshot", 3, .3),
                       rpc("harness", "tools/call", "browser_tabs", 3.1, .1)]
            (root / "kitsune-native-rpc.jsonl").write_text("\n".join(json.dumps(r) for r in records))
            tool = {"name": "browser_snapshot", "inputSchema": {"type": "object"}}
            metadata = {"enabled_tools": ["browser_snapshot", "missing"], "initialize": {"instructions": "abc"},
                        "tools_pages": [{"tools": [tool, {"name": "disabled"}]}, {"tools": [tool]}]}
            (root / "kitsune-native-metadata.json").write_text(json.dumps(metadata))
            row = analyze_run(pair, "kitsune", result)
            self.assertTrue(row["native_diagnostics_available"])
            self.assertEqual(row["native_tool_count"], 2)
            self.assertEqual(row["enabled_tool_count"], 1)
            self.assertEqual(row["enabled_tools_missing"], ["missing"])
            self.assertEqual(row["cached_setup_tab_reads"], 1)
            self.assertEqual(row["readiness_wait_sec"], .5)
            self.assertEqual(row["agent_native_rpc_sec"], .3)
            self.assertEqual(row["post_setup_inventory_rpc_sec"], .1)
            self.assertAlmostEqual(row["residual_non_rpc_sec"], 7.6)
            self.assertEqual(row["agent_response_text_bytes"], 25)

    def test_aggregate_separates_same_successful_task_subset(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pair, result = self.fixture(root)
            pair["results"]["playwright"] = result
            suite_path = root / "suite.json"
            suite_path.write_text(json.dumps({"model": "test", "requested_pairs": 1,
                                             "completed_pairs": 1, "pairs": [pair]}))
            analysis = analyze_suite(suite_path)
            for target in ("playwright", "kitsune"):
                data = analysis["by_target"][target]
                self.assertEqual(data["both_successful_tasks"], ["test-task"])
                self.assertEqual(data["both_successful_input_tokens"], 100)
                self.assertEqual(data["diagnostic_runs"], 0)
                self.assertEqual(data["totals"]["noncached_input_tokens"], 30)
                self.assertEqual(data["both_successful_uncached_input_tokens"], 30)
                self.assertEqual(data["cost_metrics"]["same_successful_tasks"]["usage"]["input_tokens"]["total"], 100)
                self.assertIsNone(data["totals"]["setup_sec"])
                self.assertEqual(data["totals_coverage"]["setup_sec"]["missing_runs"], 1)

    def test_claude_raw_uncached_and_missing_costs_survive_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pair, result = self.fixture(root)
            result["usage"].update(cache_creation_input_tokens=10, uncached_input_tokens=20)
            pair["results"]["playwright"] = {**result, "usage": {}, "benchmark_evaluation": {"scorable": False}}
            path = root / "suite.json"
            path.write_text(json.dumps({"pairs": [pair]}))
            analysis = analyze_suite(path)
            kitsune = analysis["by_target"]["kitsune"]
            self.assertEqual(kitsune["totals"]["uncached_input_tokens"], 20)
            self.assertIsNone(kitsune["both_successful_uncached_input_tokens"])
            missing = analysis["by_target"]["playwright"]["cost_metrics"]["all_attempts"]
            self.assertEqual(missing["usage"]["uncached_input_tokens"],
                             {"total": None, "reported_runs": 0, "missing_runs": 1})
            self.assertIsNone(missing["resources_task"]["observed_cpu_sec"]["total"])
