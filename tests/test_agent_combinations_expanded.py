"""Expanded authorization and scheduler checks; never browser/model execution."""
from contextlib import redirect_stdout
from collections import Counter
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from kitsune_benchmark import agent_combinations as pilot, agent_combinations_expanded as expanded

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("expanded_combinations_runner", ROOT / "scripts/run-agent-combinations.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ExpandedTests(unittest.TestCase):
    def test_plan_is_offline_and_keeps_the_old_pilot_separate(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no process during planning")):
            plan = expanded.plan()
            self.assertEqual(expanded.plan("pilot"), pilot.plan())
        self.assertFalse(plan["model_invoked"] or plan["execution_ready"] or plan["prior_cohorts_pooled"])
        self.assertEqual(plan["api_budget_usd"], 0)
        self.assertEqual((plan["operator_start_cap"], plan["executable_start_cap"]), (207, 207))
        self.assertEqual((plan["manual_starts"], plan["native_agent_starts"]), (0, 0))
        self.assertEqual(pilot.plan()["executable_start_cap"], 30)

    def test_exact_matrix_models_variants_and_order(self):
        rows = expanded.plan()["attempts"]
        self.assertEqual(len(rows), 207)
        self.assertEqual(len({(r["baseline"], r["unit"], r["variant"], r["repeat"]) for r in rows}), 207)
        self.assertEqual(set(Counter(r["baseline"] for r in rows).values()), {23})
        self.assertEqual(set(Counter(r["unit"] for r in rows).values()), {9})
        self.assertEqual(Counter(r["model"] for r in rows), {pilot.MODELS["codex"]: 161, pilot.MODELS["claude"]: 46})
        self.assertEqual({(r["variant"], r["repeat"], r["effort"], r["execution"]) for r in rows}, {(0, 0, "medium", "cli")})
        self.assertEqual({r["unit"] for r in rows[:9]}, {"pb-current-01"})
        self.assertEqual({r["unit"] for r in rows[9:18]}, {"ui-infinite@isolated"})
        self.assertEqual(Counter(r["track"] for r in expanded.conditions()), {"personal": 7, "gallery": 16})
        self.assertEqual(Counter(r["layout"] for r in expanded.conditions()), {None: 7, "isolated": 10, "crowded": 6})

    def test_growth_duplicates_and_unknown_scope_are_rejected(self):
        with patch.object(expanded, "PERSONAL", expanded.PERSONAL + ("unapproved",)):
            with self.assertRaisesRegex(ValueError, "authorized"):
                expanded.plan()
        with patch.object(expanded, "CROWDED", expanded.CROWDED[:-1] + (expanded.CROWDED[0],)):
            with self.assertRaisesRegex(ValueError, "authorized"):
                expanded.plan()
        with self.assertRaisesRegex(ValueError, "scope"):
            expanded.plan("all-repository-suites")

    def test_pilot_evidence_or_oversized_cap_cannot_authorize_expanded(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            report = out / "preflight.json"
            report.write_text(json.dumps({"plan": pilot.plan(), "model_invoked": False, "checks": {}}))
            with patch.object(runner, "pins") as pins:
                with self.assertRaisesRegex(ValueError, "161-cell"):
                    runner.freeze(report, out / "cohort", ROOT, scope="expanded", start_cap=207)
                with self.assertRaisesRegex(ValueError, "207"):
                    runner.freeze(report, out / "cohort", ROOT, scope="expanded", start_cap=208)
                with self.assertRaisesRegex(ValueError, "27"):
                    runner.freeze(report, out / "cohort", ROOT, scope="pilot", start_cap=28)
            pins.assert_not_called()
            self.assertFalse((out / "cohort").exists())

    def test_207_starts_still_need_first_nine_audit_and_never_repeat(self):
        def result(row, *_):
            return {**row, "harness": "claude_code" if row["baseline"].startswith("claude-") else "codex",
                "reported_model": row["model"], "execution_status": "completed_unscored", "scorable": True,
                "success": row["seq"] != 23, "safety_pass": row["seq"] != 23,
                "input": 100, "cached_input": 80, "output": 10, "elapsed": 20, "adjusted_elapsed": 18}
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "verify"), \
                patch.object(runner, "run_one", side_effect=result) as run, redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest = {"scope": "expanded", "plan": expanded.plan(), "cli_ready": True,
                        "api_budget_usd": 0, "authorized_cli_starts": 207}
            (out / "manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(runner.do_run(out, 207), 0)
            self.assertEqual(run.call_count, 9)
            with self.assertRaises(FileNotFoundError):
                runner.do_run(out, 207)
            (out / "first-nine-audit.json").write_text(json.dumps({"continue": True,
                "first_nine_sha256": hashlib.sha256((out / "runs.jsonl").read_bytes()).hexdigest()}))
            self.assertEqual(runner.do_run(out, 1000), 0)
            self.assertEqual(run.call_count, 207)
            self.assertEqual(runner.do_run(out, 207), 0)
            self.assertEqual(run.call_count, 207)
            self.assertEqual(len(list(out.glob("attempt-*/started.json"))), 207)
            self.assertFalse((out / "attempt-208").exists())
            self.assertIs(runner.load_rows(out)[22]["success"], False)

    def test_low_disk_stops_before_a_counted_start_without_deleting_evidence(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "verify"), \
                patch.object(runner.shutil, "disk_usage", return_value=SimpleNamespace(free=1024)), \
                patch.object(runner, "run_one") as run:
            out = Path(directory)
            manifest = {"scope": "expanded", "plan": expanded.plan(), "cli_ready": True,
                        "api_budget_usd": 0, "authorized_cli_starts": 207}
            (out / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "2 GiB"):
                runner.do_run(out, 207)
            run.assert_not_called()
            self.assertFalse(list(out.glob("attempt-*")))
            self.assertEqual(json.loads((out / "manifest.json").read_text()), json.loads(json.dumps(manifest)))

    def test_synthetic_safety_failure_is_measured_but_boundary_failure_stops(self):
        row = {**expanded.plan()["attempts"][0], "harness": "codex", "reported_model": pilot.MODELS["codex"],
            "execution_status": "completed_unscored", "scorable": True, "success": False, "safety_pass": False,
            "input": 100, "cached_input": 80, "output": 10, "adjusted_elapsed": 18}
        self.assertIsNotNone(runner.stop_reason(row, "pilot"))
        self.assertIsNone(runner.stop_reason(row, "expanded"))
        for change in ({"outside_navigation": 1}, {"violations": ["shell"]}, {"teardown_error": "unknown"},
                       {"input": None}, {"safety_pass": None}, {"execution_status": "timeout"}):
            self.assertIsNotNone(runner.stop_reason({**row, **change}, "expanded"))


if __name__ == "__main__":
    unittest.main()
