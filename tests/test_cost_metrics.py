"""Synthetic records only: no model, browser, or private artifacts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from kitsune_benchmark.cost_metrics import (aggregate_costs, load_pair_resource_phases, normalized_usage,
                                           pair_resource_phases, resource_cost, run_timing)
from kitsune_benchmark.personal import aggregate_results


class CostMetricsTests(unittest.TestCase):
    def run_record(self, success=True, cpu=3, rss=100, duration=2):
        return {"benchmark_evaluation": {"scorable": True, "task_success": success},
                "usage": {"input_tokens": 100, "cached_input_tokens": 60, "cache_creation_input_tokens": 10,
                          "uncached_input_tokens": 30, "output_tokens": 5}, "elapsed_sec": 10,
                "timing": {"relay_setup_sec": 2, "elapsed_minus_relay_setup_sec": 8, "agent_native_rpc_sec": .5},
                "resources": {"task": {"sampled_peak_rss_bytes": rss * 2, "time_weighted_mean_rss_bytes": rss,
                    "duration_sec": duration, "observed_cpu_user_sec": cpu - 1, "observed_cpu_system_sec": 1}}}

    def test_uncached_input_excludes_creation_and_prefers_explicit_provider_field(self):
        self.assertEqual(normalized_usage(self.run_record())["uncached_input_tokens"], 30)
        self.assertEqual(normalized_usage({"usage": {"input_tokens": 100, "cached_input_tokens": 60,
                                                      "cache_creation_input_tokens": 10}})["uncached_input_tokens"], 30)
        self.assertEqual(normalized_usage({"usage": {"input_tokens": 100, "cached_input_tokens": 60}})
                         ["uncached_input_tokens"], 40)
        self.assertNotIn("uncached_input_tokens", normalized_usage({"usage": {"input_tokens": 100}}))

    def test_all_success_same_success_failed_and_unknown_costs_with_coverage(self):
        success = self.run_record()
        failed = self.run_record(False, cpu=5, rss=200, duration=6)
        missing = {"benchmark_evaluation": {"scorable": False}}
        pairs = [{"results": {"playwright": success, "kitsune": success}},
                 {"results": {"playwright": failed, "kitsune": success}},
                 {"results": {"playwright": missing}}, {"results": {"playwright": success}}]
        data = aggregate_results(pairs)["playwright"]
        self.assertEqual(data["reported_usage_all_runs"]["uncached_input_tokens"], 90)
        costs = data["cost_metrics"]
        self.assertEqual(costs["user_interventions"], {"count": 0, "status": "none_by_protocol"})
        self.assertEqual(costs["paired_attempts"], 2)
        for scope, attempted, tokens in (("all_attempts", 4, 300), ("successful_tasks", 2, 200),
                                         ("same_successful_tasks", 1, 100), ("failed_attempts", 1, 100)):
            self.assertEqual(costs[scope]["attempted"], attempted)
            self.assertEqual(costs[scope]["usage"]["input_tokens"]["total"], tokens)
            self.assertEqual(costs[scope]["usage"]["uncached_input_tokens"]["total"], tokens * .3)
        all_cost = costs["all_attempts"]
        self.assertEqual(all_cost["usage"]["input_tokens"]["missing_runs"], 1)
        self.assertEqual(all_cost["resources_task"]["runs_missing_resources"], 1)
        self.assertEqual(all_cost["elapsed_sec"], {"total": 30, "reported_runs": 3, "missing_runs": 1})
        self.assertEqual(all_cost["timing"]["elapsed_minus_relay_setup_sec"]["total"], 24)
        resources = all_cost["resources_task"]
        self.assertEqual(resources["observed_cpu_sec"]["total"], 11)
        self.assertEqual(resources["sampled_peak_rss_bytes"], 400)
        self.assertAlmostEqual(resources["mean_task_sampled_peak_rss_bytes"], 800 / 3)
        self.assertEqual(resources["time_weighted_mean_rss_bytes"], 160)
        self.assertEqual(resources["rss_observed_duration_sec"], 10)
        self.assertEqual(costs["failed_attempts"]["resources_task"]["observed_cpu_sec"]["total"], 5)
        self.assertEqual(costs["same_successful_tasks"]["resources_task"]["time_weighted_mean_rss_bytes"], 100)
        successful = costs["successful_tasks"]["resources_task"]
        self.assertEqual(successful["observed_cpu_sec_per_measured_task"], 3)
        self.assertEqual(successful["mean_task_sampled_peak_rss_bytes"], 200)
        self.assertIsNone(costs["unscored_or_unknown_attempts"]["usage"]["input_tokens"]["total"])
        self.assertIsNone(costs["unscored_or_unknown_attempts"]["resources_task"]["sampled_peak_rss_bytes"])
        self.assertIsNone(aggregate_costs([])["kitsune"]["all_attempts"]["usage"]["input_tokens"]["total"])

    def test_paired_attempts_distinguishes_no_pairing_from_no_joint_successes(self):
        success, failed = self.run_record(), self.run_record(False)
        unpaired = aggregate_costs([{"results": {"playwright": success}}, {"results": {"kitsune": success}}])
        paired = aggregate_costs([{"results": {"playwright": failed, "kitsune": success}}])
        for target in ("playwright", "kitsune"):
            self.assertEqual(unpaired[target]["paired_attempts"], 0)
            self.assertEqual(paired[target]["paired_attempts"], 1)
            self.assertEqual(unpaired[target]["same_successful_tasks"]["attempted"], 0)
            self.assertEqual(paired[target]["same_successful_tasks"]["attempted"], 0)

    def test_missing_success_measurements_do_not_dilute_measured_task_cost(self):
        missing = {"benchmark_evaluation": {"scorable": True, "task_success": True}, "usage": None,
                   "resources": None}
        costs = aggregate_costs([{"results": {"kitsune": r}} for r in (self.run_record(), missing)])
        successful = costs["kitsune"]["successful_tasks"]
        self.assertEqual(successful["attempted"], 2)
        self.assertEqual(successful["usage"]["uncached_input_tokens"]["missing_runs"], 1)
        self.assertEqual(successful["resources_task"]["observed_cpu_sec_per_measured_task"], 3)
        self.assertEqual(successful["resources_task"]["runs_missing_resources"], 1)

    def test_pair_setup_and_ready_remain_separate_from_task_cost(self):
        run = self.run_record()
        setup = {**run["resources"]["task"], "observed_cpu_user_sec": 20}
        summary = {"metrics": {"phase/setup/owner/kitsune": setup,
                               "phase/ready/owner/kitsune": run["resources"]["task"],
                               "phase/setup/all": {"observed_cpu_user_sec": 999}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resource-summary.json"
            path.write_text(json.dumps(summary))
            pair = load_pair_resource_phases({"results": {"kitsune": run, "playwright": run},
                                              "resource_summary_path": str(path),
                                              "timing": {"kitsune_cold_start_setup_sec": 4}})
            self.assertEqual(pair["resource_phases"], pair_resource_phases(summary, pair["results"]))
            costs = aggregate_costs([pair])
        lifecycle = costs["kitsune"]["pair_lifecycle"]
        self.assertEqual(lifecycle["cold_start_setup_elapsed_sec"]["total"], 4)
        self.assertEqual(lifecycle["setup"]["observed_cpu_sec"]["total"], 21)
        self.assertEqual(lifecycle["ready"]["observed_cpu_sec"]["total"], 3)
        self.assertEqual(costs["kitsune"]["all_attempts"]["resources_task"]["observed_cpu_sec"]["total"], 3)
        self.assertIsNone(costs["playwright"]["pair_lifecycle"]["setup"]["observed_cpu_sec"]["total"])
        self.assertIsNone(costs["playwright"]["pair_lifecycle"]["cold_start_setup_elapsed_sec"]["total"])

    def test_cold_start_cost_survives_stopping_before_kitsune_task(self):
        run = self.run_record(False)
        bucket = run["resources"]["task"]
        summary = {"metrics": {f"phase/{phase}/owner/kitsune": bucket for phase in ("setup", "ready")}}
        pair = {"results": {"playwright": run}, "timing": {"kitsune_cold_start_setup_sec": 4},
                "resource_phases": pair_resource_phases(summary, ("playwright", "kitsune"))}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resource-summary.json"
            path.write_text(json.dumps(summary))
            legacy = {k: v for k, v in pair.items() if k != "resource_phases"}
            legacy["resource_summary_path"] = str(path)
            for record in (pair, load_pair_resource_phases(legacy)):
                costs = aggregate_costs([record])["kitsune"]
                self.assertEqual(costs["all_attempts"]["attempted"], 0)
                self.assertEqual(costs["pair_lifecycle"]["cold_start_setup_elapsed_sec"]["total"], 4)
                for phase in ("setup", "ready"):
                    self.assertEqual(costs["pair_lifecycle"][phase]["observed_cpu_sec"]["total"], 3)

    def test_run_timing_skips_malformed_and_non_object_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = ['{"kind":', '', 'null', '[]',
                       json.dumps({"kind": "setup_completed", "duration_sec": 2}),
                       json.dumps({"kind": "rpc_completed", "role": "agent", "method": "tools/call",
                                   "duration_sec": .5}), '{truncated']
            (root / "kitsune-native-rpc.jsonl").write_text("\n".join(records))
            self.assertEqual(run_timing(root, "kitsune", {"elapsed_sec": 10}),
                             {"relay_setup_sec": 2, "elapsed_minus_relay_setup_sec": 8,
                              "agent_native_rpc_sec": .5})

    def test_readiness_sleep_and_agent_rpc_are_nested_not_added_to_elapsed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run_timing(root, "kitsune", {})["relay_setup_sec"], None)
            records = [{"kind": "setup_completed", "duration_sec": 2},
                       {"kind": "readiness_wait", "duration_sec": 1},
                       {"kind": "rpc_completed", "role": "agent", "method": "tools/call", "duration_sec": .5}]
            (root / "kitsune-native-rpc.jsonl").write_text("\n".join(json.dumps(r) for r in records))
            timing = run_timing(root, "kitsune", {"elapsed_sec": 10})
        self.assertEqual(timing, {"relay_setup_sec": 2, "elapsed_minus_relay_setup_sec": 8,
                                  "agent_native_rpc_sec": .5})

    def test_unmeasured_or_zero_duration_resources_are_not_zero_rss(self):
        result = resource_cost([None, {"duration_sec": 0, "time_weighted_mean_rss_bytes": None}])
        self.assertIsNone(result["time_weighted_mean_rss_bytes"])
        self.assertIsNone(result["observed_cpu_sec"]["total"])
        self.assertEqual(result["runs_missing_resources"], 1)

    def test_per_tool_analysis_exposes_costs_without_pairing_parallel_fixtures(self):
        spec = importlib.util.spec_from_file_location("analyze_per_tool", Path(__file__).resolve().parents[1]
                                                     / "scripts/analyze-per-tool.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            records = [("personal-v0", {"pair_dir": directory, "results": {t: self.run_record()}})
                       for t in ("playwright", "kitsune")]
            report = module.cost_report(records)["personal"]
        self.assertEqual(report["kitsune"]["all_attempts"]["usage"]["uncached_input_tokens"]["total"], 30)
        self.assertEqual(report["kitsune"]["same_successful_tasks"]["attempted"], 0)
        self.assertEqual(report["kitsune"]["paired_attempts"], 0)
