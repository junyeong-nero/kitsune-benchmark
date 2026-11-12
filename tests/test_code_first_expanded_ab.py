"""No-inference plan, treatment, fixture and conditional-merge checks."""
from collections import Counter
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("expanded_ab_test", ROOT / "scripts/run-code-first-expanded-ab.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
five = experiment.five
B, C = experiment.BASELINE, experiment.CANDIDATE


class ExpandedPlanTests(unittest.TestCase):
    def test_frozen_sources_actual_surfaces_and_no_vendor_apps(self):
        self.assertEqual(five.SHAS, {"main": "47dafa20a3fddc697a7d991e15d39e4b0232c10d",
                                    "scripting": "f5c7a0f85aefd89e621e73665e33d33d79d50676"})
        self.assertEqual(five.EXPECTED, {B: 14, C: 6})
        self.assertEqual(five.vendor_pins(), {})
        self.assertTrue(five.RECORD_CATALOG)
        self.assertIn(experiment.PROTOCOL, five.RUNNER_FILES)
        for arm in five.ARMS:
            self.assertEqual(five.ARMS[arm][2:], ({}, None))
        self.assertEqual(experiment.ELICITATION, "decline")

    def test_120_unique_cells_46_new_pairs_and_layouts(self):
        rows = experiment.plan()
        self.assertEqual(len(rows), 120)
        self.assertEqual([r["seq"] for r in rows], list(range(1, 121)))
        self.assertEqual(Counter(r["arm"] for r in rows), {B: 60, C: 60})
        self.assertEqual(Counter(r["track"] for r in rows), {"miniwob": 28, "personal": 28, "gallery": 64})
        self.assertEqual(len({(r["unit"], r["repeat"], r["arm"]) for r in rows}), 120)
        self.assertEqual(len([r for r in rows if r["track"] != "miniwob" and r["arm"] == B]), 46)
        self.assertEqual({r["track"] for r in rows[:6]}, {"miniwob", "personal", "gallery"})
        self.assertEqual({r["variant"] for r in rows}, {0})
        for condition in experiment.conditions():
            orders = [[r["arm"] for r in rows if r["unit"] == condition["unit"] and r["repeat"] == repeat]
                      for repeat in range(2)]
            self.assertEqual(orders[0], orders[1][::-1])
        self.assertEqual(len({r["unit"] for r in rows if r["task"] == "ui-table"}), 2)

    def test_selected_tasks_exist_without_starting_a_browser(self):
        self.assertEqual(len(experiment.personal.selected_tasks(list(experiment.PERSONAL))), 7)
        self.assertEqual(len(experiment.gallery.select(list(experiment.ISOLATED))), 10)
        self.assertEqual(len(experiment.gallery.select(list(experiment.CROWDED))), 6)
        self.assertEqual(five.suite.model(), "claude-opus-5-5")

    def test_gallery_uses_unchanged_fixture_policy_and_actual_default(self):
        row = next(r for r in experiment.plan() if r["unit"] == "ui-table@crowded" and r["arm"] == C)
        with patch.object(experiment.gallery, "GalleryServer") as server, patch.object(experiment, "run_pair") as run:
            fixture = server.return_value
            fixture.kitsune_bidi_port = 12345
            experiment.run_one(row, five.PROJECT_DEFAULTS)
            self.assertEqual(server.call_args.args[1:], (0, "crowded", "decline"))
            args = run.call_args.kwargs
            self.assertEqual(args["kitsune_project"], five.PROJECT_DEFAULTS["scripting"])
            self.assertEqual(args["kitsune_env"], {})
            self.assertIsNone(args["enabled_tools"])
            self.assertEqual(args["targets"], ("kitsune",))
            self.assertTrue(args["record_catalog"])
            self.assertTrue(args["equalize_kitsune_viewport"])
            self.assertIs(args["task_for_target"], fixture.begin)
            self.assertEqual(args["experiment_spec"]["timeout_sec"], 240)

    def test_primary_grades_are_preserved_not_coerced_to_success(self):
        pair = {"results": {"kitsune": {"benchmark_evaluation": {
            "task_success": None, "safety_pass": None, "functional_success": True}}}}
        with patch.object(experiment, "_base_metrics", return_value={"success": False}):
            row = experiment.metrics(pair, B)
        self.assertFalse(row["success"])
        self.assertIsNone(row["grade_success"])
        self.assertIsNone(row["safety_pass"])
        self.assertTrue(row["functional_success"])


class GateTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{**r, "scorable": True, "success": True, "grade_success": True,
                      "safety_pass": None if r["track"] == "miniwob" else True,
                      "input": 80 if r["arm"] == C else 100, "elapsed": 10,
                      "output": 10, "calls": 3, "requests": 4, "cost": .1,
                      "page_js_hits": 0, "script_calls": 2 if r["arm"] == C else 0}
                     for r in experiment.plan()]

    def analysis(self):
        with patch.object(five.suite.ab, "load_log", return_value=self.rows):
            return experiment.analyze(Path("unused"))

    def change_candidate_primary(self, **changes):
        row = next(r for r in self.rows if r["arm"] == C and r["track"] != "miniwob")
        row.update(changes)

    def test_pass_never_merges_without_manual_audit_and_tests(self):
        report = self.analysis()
        self.assertTrue(report["numeric_gate"]["passes"])
        self.assertFalse(report["merge_authorized_by_metrics_alone"])
        self.assertEqual(report["comparisons"]["primary"]["joint_cells"], 46)
        self.assertEqual(len(report["per_unit"]), 30)
        self.assertEqual(report["comparisons"]["gallery_isolated"]["joint_cells"], 20)
        self.assertEqual(report["comparisons"]["gallery_crowded"]["joint_cells"], 12)

    def test_incomplete_duplicate_and_unknown_evidence_cannot_pass(self):
        self.rows.pop()
        self.assertFalse(self.analysis()["numeric_gate"]["passes"])
        self.rows.append(dict(self.rows[0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.analysis()

    def test_failed_work_remains_in_primary_totals_and_blocks_success_regression(self):
        self.change_candidate_primary(success=False, grade_success=False, input=1)
        report = self.analysis()
        self.assertFalse(report["numeric_gate"]["passes"])
        self.assertEqual(report["comparisons"]["primary"]["joint_cells"], 45)
        self.assertEqual(report["comparisons"]["primary"]["arms"][C]["attempts"], 46)
        self.assertEqual(report["comparisons"]["primary"]["arms"][C]["input"], 45 * 80 + 1)
        self.assertEqual(report["regressed_conditions"], ["pb-current-01"])

    def test_insufficient_savings_not_rounded_into_a_pass(self):
        for row in self.rows:
            row["input"] = 9001 if row["arm"] == C else 10000
        self.assertFalse(self.analysis()["numeric_gate"]["checks"]["primary_joint_input_at_most_0_90"])

    def test_slower_candidate_is_held(self):
        for row in self.rows:
            if row["arm"] == C:
                row["elapsed"] = 11.01
        self.assertFalse(self.analysis()["numeric_gate"]["passes"])

    def test_safety_unknown_and_page_js_are_not_free_savings(self):
        for changes in ({"safety_pass": None}, {"safety_pass": False}, {"grade_success": None}, {"page_js_hits": 1}):
            with self.subTest(changes=changes):
                self.setUp()
                self.change_candidate_primary(**changes)
                self.assertFalse(self.analysis()["numeric_gate"]["passes"])

    def test_small_survivor_set_is_held_even_without_regression(self):
        for row in self.rows:
            if row["track"] == "personal":
                row.update(success=False, grade_success=False)
        report = self.analysis()
        self.assertEqual(report["comparisons"]["primary"]["joint_cells"], 32)
        self.assertFalse(report["numeric_gate"]["passes"])

    def test_pilot_guard_tokens_cannot_manufacture_primary_savings(self):
        for row in self.rows:
            if row["arm"] == C:
                row["input"] = 1 if row["track"] == "miniwob" else 101
        report = self.analysis()
        self.assertFalse(report["numeric_gate"]["passes"])
        self.assertGreater(report["comparisons"]["primary"]["joint_ratios"]["input"], 1)


if __name__ == "__main__":
    unittest.main()
