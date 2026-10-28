import collections
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

SPEC = importlib.util.spec_from_file_location("run_h321", Path(__file__).resolve().parents[1] / "scripts/run-h321.py")
h321 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h321)


def record(run, requests, input_tokens, success=True):
    return {**run, "status": "ok", "scorable": True, "success": success, "safety_v1": True, "safety_v2": True,
            "failed_mcp_calls": 0, "mcp_calls": 5, "usage": {"input_tokens": input_tokens},
            "token_attribution": {"requests": requests}, "snapshots": {"truncated": 1, "url_lines": 0, "find_calls": 2},
            "run_dir": None}


def analyze(rows):
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        with contextlib.redirect_stdout(io.StringIO()):
            h321.analyze(types.SimpleNamespace(out=folder))
        return json.loads(Path(folder, "analysis.json").read_text())


class PlanTest(unittest.TestCase):
    def test_counts_cells_and_counterbalancing(self):
        runs = h321.plan()
        self.assertEqual(len(runs), 36)
        self.assertEqual(collections.Counter(r["kind"] for r in runs), {"table": 24, "guard": 12})
        self.assertTrue(all(r["track"] == "external" and r["variant"] is None for r in runs if r["kind"] == "table"))
        self.assertEqual({r["cell"] for r in runs if r["kind"] == "table"},
                         {"live-steam-goty-2025-negative-100h", "live-wikipedia-firefox-release", "live-mdn-array-at-firefox"})
        self.assertTrue(all(r["layout"] == "isolated" for r in runs if r["kind"] == "guard"))
        self.assertEqual(len({(r["cell"], r["repeat"], r["arm"]) for r in runs}), 36)


class VerdictTest(unittest.TestCase):
    def test_support_when_live_input_falls_and_guards_hold(self):
        rows = [record(r, 10, 1000 if r["arm"] == "baseline" or r["kind"] == "guard" else 850) for r in h321.plan()]
        report = analyze(rows)
        self.assertAlmostEqual(report["primary_input_ratio"], 0.85)
        self.assertEqual(report["verdict"], "support")

    def test_reject_at_or_above_parity(self):
        self.assertEqual(analyze([record(r, 10, 1000) for r in h321.plan()])["verdict"], "reject")

    def test_fewer_advisory_matches_block_support(self):
        rows = []
        for r in h321.plan():
            rec = record(r, 10, 1000 if r["arm"] == "baseline" else 800)
            rec["advisory"] = not (r["arm"] == "intervention" and r["cell"] == "live-mdn-array-at-firefox" and r["repeat"] == 0)
            rows.append(rec)
        report = analyze(rows)
        self.assertFalse(report["gates_ok"])
        self.assertEqual(report["verdict"], "inconclusive")

    def test_incomplete_live_runs_drop_pairs(self):
        rows = [record(r, 10, 1000 if r["arm"] == "baseline" else 800,
                       success=not (r["arm"] == "intervention" and r["kind"] == "table" and r["repeat"] < 2))
                for r in h321.plan()]
        report = analyze(rows)
        self.assertEqual(report["jointly_successful_pairs"]["primary"], 6)
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
            self.assertEqual(h321.truncated_snapshots(folder), {"truncated": 1, "url_lines": 1, "find_calls": 1})
        self.assertEqual(h321.truncated_snapshots(None), {"truncated": 0, "url_lines": 0, "find_calls": 0})


if __name__ == "__main__":
    unittest.main()
