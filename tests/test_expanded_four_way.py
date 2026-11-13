"""Frozen plan, Codex-only accounting and fail-closed execution; no model calls."""
from collections import Counter
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("expanded_four_test", ROOT / "scripts/run-expanded-four-way.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
B, C, A, E = experiment.ARMS


def row(planned, **overrides):
    return {**planned, "harness": "codex", "model": experiment.MODEL, "execution_status": "completed_unscored",
            "scorable": True, "success": True, "grade_success": True, "safety_pass": True,
            "input": 100, "cached_input": 80, "output": 10, "calls": 3,
            "elapsed": 20, "adjusted_elapsed": 18, "published": experiment.EXPECTED[planned["arm"]],
            "outside_navigation": 0, "violations": [], "run_dir": "/unused", **overrides}


class FourWayTests(unittest.TestCase):
    def test_184_cells_and_counterbalanced_order(self):
        plan = experiment.plan()
        self.assertEqual(len(plan), 184)
        self.assertEqual(Counter(r["arm"] for r in plan), {a: 46 for a in experiment.ARMS})
        self.assertEqual(len({(r["unit"], r["repeat"], r["arm"]) for r in plan}), 184)
        self.assertEqual(Counter(r["track"] for r in plan), {"personal": 56, "gallery": 128})
        self.assertEqual(Counter(r["layout"] for r in plan), {None: 56, "isolated": 80, "crowded": 48})
        self.assertEqual({r["track"] for r in plan[:8]}, {"personal", "gallery"})
        self.assertEqual({r["variant"] for r in plan}, {0})
        for condition in experiment.conditions():
            orders = [[r["arm"] for r in plan if r["unit"] == condition["unit"] and r["repeat"] == repeat]
                      for repeat in (0, 1)]
            self.assertEqual(orders[0], orders[1][::-1])

    def test_same_sources_no_caps_and_native_vendor_surfaces(self):
        self.assertEqual(experiment.MODEL, "gpt-6.1-sol")
        self.assertEqual(experiment.EXPECTED, {B: 14, C: 6, A: 1, E: 1})
        self.assertEqual(experiment.ARMS[B][2:], ({}, None))
        self.assertEqual(experiment.ARMS[C][2:], ({}, None))
        self.assertEqual(experiment.ARMS[A][3], ("repl",))
        self.assertEqual(experiment.ARMS[E][3], ("run_script",))
        self.assertEqual(experiment.five.SHAS, {
            "main": "47dafa20a3fddc697a7d991e15d39e4b0232c10d",
            "scripting": "f5c7a0f85aefd89e621e73665e33d33d79d50676"})

    def test_runner_calls_codex_and_leaves_config_files_unchanged(self):
        for planned in experiment.plan()[:4]:
            with patch.object(experiment, "run_pair", return_value={}) as run:
                experiment.run_one(planned, experiment.five.PROJECT_DEFAULTS)
                kwargs = run.call_args.kwargs
                self.assertEqual(kwargs["harness"], "codex")
                self.assertEqual(kwargs["executable"], "codex")
                self.assertEqual(kwargs["experiment_spec"]["model"], "gpt-6.1-sol")
                self.assertEqual(kwargs["experiment_spec"]["reasoning_effort"], "medium")
                self.assertEqual(kwargs["kitsune_env"], {})
                self.assertTrue(kwargs["record_catalog"])
                self.assertEqual(kwargs["targets"], (experiment.ARMS[planned["arm"]][0],))
        self.assertEqual(experiment.personal.config()["model"], "gpt-6-luna")

    def test_missing_usage_and_unmatched_cells_have_no_all_attempt_ratio(self):
        plan = experiment.plan()
        baseline, candidate = row(plan[0]), row(plan[1], input=None)
        report = experiment.compare([baseline, candidate], (B, C))
        self.assertEqual(report["arms"][C]["metrics"]["input"]["missing"], 1)
        self.assertIsNone(report["ratios"]["all_attempt"]["input"])
        self.assertIsNone(report["ratios"]["joint"]["input"])
        self.assertIsNone(experiment.compare([baseline], (B, C))["ratios"]["all_attempt"]["input"])

    def test_failures_stay_in_all_attempt_but_not_joint(self):
        plan = experiment.plan()
        rows = [row(plan[0]), row(plan[1], success=False, grade_success=False, input=160)]
        result = experiment.compare(rows, (B, C))
        self.assertEqual(result["joint_cells"], 0)
        self.assertEqual(result["ratios"]["all_attempt"]["input"], 1.6)
        self.assertIsNone(result["ratios"]["joint"]["input"])
        self.assertIsNone(experiment.stop_reason(rows[1]))

    def test_unknown_or_wrong_model_evidence_stops(self):
        planned = experiment.plan()[0]
        cases = [{"input": None}, {"safety_pass": None}, {"grade_success": None},
                 {"adjusted_elapsed": None}, {"adjusted_elapsed": -1}, {"published": 30},
                 {"model": "claude-opus-5-5"}, {"harness": "claude"}, {"execution_status": "timeout"},
                 {"outside_navigation": 1}, {"violations": ["forbidden_or_unknown_item"]}]
        for change in cases:
            with self.subTest(change=change):
                self.assertIsNotNone(experiment.stop_reason(row(planned, **change)))

    def test_duplicate_cell_is_not_silently_overwritten(self):
        baseline = row(experiment.plan()[0])
        with self.assertRaises(ValueError):
            experiment.compare([baseline, baseline], (B, C))

    def harness(self, directory, overrides=None):
        out = Path(directory)
        catalogs = {a: {"tools": [{"name": f"tool{i}"} for i in range(n)], "instructions": None,
                        "server_info": {"name": a, "version": "test"}} for a, n in experiment.EXPECTED.items()}
        (out / "catalog-preflight.json").write_text(json.dumps({"catalogs": catalogs, "vendors": {}}))
        current, launched = {}, []
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(experiment, "source_revision", return_value={"revision": "frozen"}))
        stack.enter_context(patch.object(experiment.five, "verify_sources"))
        stack.enter_context(patch.object(experiment, "harness_preflight", return_value={"subscription": True}))
        stack.enter_context(patch.object(experiment.five, "vendor_pins", return_value={}))
        stack.enter_context(patch.object(experiment, "preflight", side_effect=lambda projects, arm=None: {arm: catalogs[arm]}))
        stack.enter_context(patch.object(experiment.five, "observed_catalog", side_effect=lambda pair: catalogs[current["arm"]]))

        def run_one(planned, projects):
            launched.append(planned["seq"])
            current.update(planned)
            return {"pair_dir": "/unused"}

        stack.enter_context(patch.object(experiment, "run_one", side_effect=run_one))
        stack.enter_context(patch.object(experiment, "metrics", side_effect=lambda pair, arm:
            row(current, **(overrides or {}))))
        return out, launched

    def test_initial_invocation_caps_at_eight_and_requires_matching_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            out, launched = self.harness(directory)
            self.assertEqual(experiment.do_run(out, experiment.five.PROJECT_DEFAULTS, None), 0)
            self.assertEqual(launched, list(range(1, 9)))
            with self.assertRaises(FileNotFoundError):
                experiment.do_run(out, experiment.five.PROJECT_DEFAULTS, 1)
            digest = hashlib.sha256((out / "runs.jsonl").read_bytes()).hexdigest()
            (out / "first-eight-audit.json").write_text(json.dumps({"continue": True, "first_eight_sha256": digest}))
            self.assertEqual(experiment.do_run(out, experiment.five.PROJECT_DEFAULTS, 1), 0)
            self.assertEqual(launched, list(range(1, 10)))

    def test_timeout_is_retained_and_blocks_automatic_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            out, launched = self.harness(directory, {"execution_status": "timeout", "input": None, "scorable": False})
            self.assertEqual(experiment.do_run(out, experiment.five.PROJECT_DEFAULTS, None), 2)
            self.assertEqual(launched, [1])
            self.assertTrue((out / "stopped.json").exists())
            self.assertIsNone(json.loads((out / "runs.jsonl").read_text())["input"])
            with self.assertRaises(ValueError):
                experiment.do_run(out, experiment.five.PROJECT_DEFAULTS, None)

    def test_catalog_drift_prevents_next_model_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            out, launched = self.harness(directory)
            with patch.object(experiment, "preflight", return_value={B: {"tools": []}}):
                with self.assertRaisesRegex(ValueError, "catalog drift"):
                    experiment.do_run(out, experiment.five.PROJECT_DEFAULTS, None)
            self.assertEqual(launched, [])


if __name__ == "__main__":
    unittest.main()
