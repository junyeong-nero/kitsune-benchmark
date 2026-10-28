import collections
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

SPEC = importlib.util.spec_from_file_location("run_h310", Path(__file__).resolve().parents[1] / "scripts/run-h310.py")
h310 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h310)


def record(run, requests, input_tokens, success=True):
    return {**run, "status": "ok", "scorable": True, "success": success, "safety_v1": True, "safety_v2": True,
            "failed_mcp_calls": 0, "mcp_calls": 5, "usage": {"input_tokens": input_tokens},
            "token_attribution": {"requests": requests}, "snapshots": {"truncated": 1, "url_lines": 0, "find_calls": 2},
            "run_dir": None}


def analyze(rows):
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        with contextlib.redirect_stdout(io.StringIO()):
            h310.analyze(types.SimpleNamespace(out=folder))
        return json.loads(Path(folder, "analysis.json").read_text())


class PlanTest(unittest.TestCase):
    def test_counts_cells_and_counterbalancing(self):
        runs = h310.plan()
        self.assertEqual(len(runs), 66)
        self.assertEqual(collections.Counter(r["kind"] for r in runs), {"table": 48, "guard": 18})
        self.assertTrue(all(r["layout"] == "crowded" for r in runs if r["kind"] == "table"))
        self.assertTrue(all(r["layout"] != "crowded" for r in runs if r["kind"] == "guard"))
        for cell in {r["cell"] for r in runs}:
            first = [r["arm"] for r in runs if r["cell"] == cell][::2]
            self.assertIn(first, (["baseline", "intervention", "intervention", "baseline"],
                                  ["intervention", "baseline", "baseline", "intervention"],
                                  ["baseline", "intervention", "baseline"], ["intervention", "baseline", "intervention"]))
        self.assertEqual(len({(r["cell"], r["repeat"], r["arm"]) for r in runs}), 66)


class VerdictTest(unittest.TestCase):
    def test_support_when_primary_input_falls_and_guards_hold(self):
        rows = [record(r, 10 if r["arm"] == "baseline" else 8,
                       1000 if r["arm"] == "baseline" else (850 if r["kind"] == "table" else 1000)) for r in h310.plan()]
        report = analyze(rows)
        self.assertAlmostEqual(report["primary_input_ratio"], 0.85)
        self.assertAlmostEqual(report["pooled_guard_input_ratio"], 1.0)
        self.assertEqual(report["verdict"], "support")
        self.assertEqual(report["totals"]["primary_crowded"]["baseline"]["find_calls"], 48)

    def test_reject_at_or_above_parity(self):
        rows = [record(r, 10, 1000) for r in h310.plan()]
        self.assertEqual(analyze(rows)["verdict"], "reject")

    def test_small_gain_is_inconclusive(self):
        rows = [record(r, 10, 1000 if r["arm"] == "baseline" else 950) for r in h310.plan()]
        self.assertEqual(analyze(rows)["verdict"], "inconclusive")

    def test_guard_growth_or_lost_success_blocks_support(self):
        rows = [record(r, 10, 1000 if r["arm"] == "baseline" else (1200 if r["kind"] == "guard" else 800))
                for r in h310.plan()]
        self.assertEqual(analyze(rows)["verdict"], "inconclusive")
        rows = [record(r, 10, 1000 if r["arm"] == "baseline" else 800,
                       success=not (r["arm"] == "intervention" and r["cell"] == "ui-slider/v0/crowded" and r["repeat"] == 0))
                for r in h310.plan()]
        report = analyze(rows)
        self.assertFalse(report["gates_ok"])
        self.assertEqual(report["verdict"], "inconclusive")

    def test_too_few_joint_pairs_is_inconclusive(self):
        rows = [record(r, 10, 1000 if r["arm"] == "baseline" else 800,
                       success=not (r["arm"] == "baseline" and r["kind"] == "table" and r["repeat"] < 2))
                for r in h310.plan()]
        report = analyze(rows)
        self.assertEqual(report["jointly_successful_pairs"]["primary"], 12)
        self.assertEqual(report["verdict"], "inconclusive")


class InEffectTest(unittest.TestCase):
    def test_truncated_snapshot_url_lines_and_find_calls_are_counted(self):
        snapshot = {"snapshot": "- main \"\" [ref=e1]\n  - link \"a\" [ref=e2]\n    - /url: \"/a\"", "truncated": True}
        events = [{"message": {"content": [{"type": "tool_use", "name": "mcp__browser__browser_find", "id": "1"}]}},
                  {"message": {"content": [{"type": "tool_result", "tool_use_id": "1",
                                            "content": [{"type": "text", "text": json.dumps(snapshot)}]}]}},
                  {"message": {"content": [{"type": "tool_result", "content": json.dumps({"snapshot": "x"})}]}}]
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
            self.assertEqual(h310.truncated_snapshots(folder), {"truncated": 1, "url_lines": 1, "find_calls": 1})
        self.assertEqual(h310.truncated_snapshots(None), {"truncated": 0, "url_lines": 0, "find_calls": 0})


if __name__ == "__main__":
    unittest.main()
