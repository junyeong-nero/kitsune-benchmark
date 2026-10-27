import collections
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

SPEC = importlib.util.spec_from_file_location("run_h18", Path(__file__).resolve().parents[1] / "scripts/run-h18.py")
h18 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h18)


def record(run, requests, input_tokens, success=True):
    return {**run, "status": "ok", "scorable": True, "success": success, "safety_v1": True, "safety_v2": True,
            "failed_mcp_calls": 0, "mcp_calls": 5, "usage": {"input_tokens": input_tokens},
            "token_attribution": {"requests": requests}, "collapse_markers": [], "run_dir": None}


def analyze(rows):
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        with contextlib.redirect_stdout(io.StringIO()):
            h18.analyze(types.SimpleNamespace(out=folder))
        return json.loads(Path(folder, "analysis.json").read_text())


class PlanTest(unittest.TestCase):
    def test_counts_and_counterbalancing(self):
        runs = h18.plan()
        self.assertEqual(len(runs), 66)
        self.assertEqual(collections.Counter(r["kind"] for r in runs), {"table": 48, "guard": 18})
        for cell in {r["cell"] for r in runs}:
            first = [r["arm"] for r in runs if r["cell"] == cell][::2]
            repeats = len(first)
            self.assertIn(repeats, (3, 4))
            # Each repeat runs both arms back to back; first arms follow ABBA/BAAB or ABA/BAB.
            self.assertIn(first, (["baseline", "intervention", "intervention", "baseline"],
                                  ["intervention", "baseline", "baseline", "intervention"],
                                  ["baseline", "intervention", "baseline"], ["intervention", "baseline", "intervention"]))
        self.assertEqual(len({(r["cell"], r["repeat"], r["arm"]) for r in runs}), 66)


class VerdictTest(unittest.TestCase):
    def test_support_when_requests_and_input_fall(self):
        rows = [record(r, 10 if r["arm"] == "baseline" else 7, 1000 if r["arm"] == "baseline" else 900)
                for r in h18.plan()]
        report = analyze(rows)
        self.assertEqual(report["request_ratio"], 0.7)
        self.assertAlmostEqual(report["table_input_ratio"], 0.9)
        self.assertEqual(report["verdict"], "support")

    def test_reject_when_input_grows(self):
        rows = [record(r, 10 if r["arm"] == "baseline" else 7, 1000 if r["arm"] == "baseline" else 1100)
                for r in h18.plan()]
        self.assertEqual(analyze(rows)["verdict"], "reject")

    def test_failures_drop_pairs_and_too_few_is_inconclusive(self):
        rows = [record(r, 10 if r["arm"] == "baseline" else 7, 1000 if r["arm"] == "baseline" else 900,
                       success=not (r["arm"] == "intervention" and r["kind"] == "table" and r["layout"] == "isolated"
                                    and r["repeat"] < 2))
                for r in h18.plan()]
        report = analyze(rows)
        self.assertEqual(report["jointly_successful_pairs"]["isolated_table"], 6)
        self.assertEqual(len(report["dropped_pairs"]), 6)
        self.assertEqual(report["verdict"], "inconclusive")

    def test_guard_growth_blocks_support(self):
        rows = [record(r, 10 if r["arm"] == "baseline" else 7,
                       1000 if r["arm"] == "baseline" else (1200 if r["kind"] == "guard" else 900)) for r in h18.plan()]
        report = analyze(rows)
        self.assertEqual(report["verdict"], "inconclusive")
        self.assertAlmostEqual(report["guard_input_ratio"]["mm-grid/v0/isolated"], 1.2)


if __name__ == "__main__":
    unittest.main()
