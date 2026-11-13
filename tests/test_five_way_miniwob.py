"""No-inference coverage for the fixed five-way subscription comparison."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("five_way", ROOT / "scripts/run-five-way-miniwob.py")
five = importlib.util.module_from_spec(spec)
spec.loader.exec_module(five)


def measured(arm, **updates):
    return {"scorable": True, "success": True, "execution_status": "completed_unscored",
            "input": 100, "output": 10, "cached_input": 50, "requests": 3, "calls": 4,
            "elapsed": 5, "cost": .1, "first_input": 50, "run_dir": "/unused", "pair_dir": "/unused",
            "published": five.EXPECTED[arm], "relay_published": None, "script_calls": 0, "script_errors": 0,
            "tool_errors": {}, "reward_pattern_hits": 0, "page_js_hits": 0, **updates}


class PlanTests(unittest.TestCase):
    def test_complete_balanced_schedule(self):
        rows = five.plan()
        self.assertEqual(len(rows), 70)
        self.assertEqual([r["seq"] for r in rows], list(range(1, 71)))
        self.assertEqual(Counter(r["arm"] for r in rows), {a: 14 for a in five.ARMS})
        self.assertEqual(len({(r["task"], r["repeat"], r["arm"]) for r in rows}), 70)
        for task in five.suite.ab.MINIWOB:
            orders = [[r["arm"] for r in rows if r["task"] == task and r["repeat"] == rep] for rep in (0, 1)]
            self.assertEqual(orders[0], orders[1][::-1])

    def test_tool_and_source_treatments(self):
        self.assertEqual(five.ARMS["kitsune-main"][1:3], ("main", {}))
        self.assertEqual(five.ARMS["kitsune-scripting"][1:], ("scripting", {"KITSUNE_SCRIPTING": "1"}, None))
        self.assertEqual(five.ARMS["aside"][3], ("repl",))
        self.assertEqual(five.ARMS["ego"][3], ("run_script",))
        self.assertEqual(five.suite.HARNESS, "claude")
        self.assertEqual(five.suite.model(), "claude-opus-5-5")
        for arm, (_, _, _, tools) in five.ARMS.items():
            if tools is not None:
                self.assertEqual(len(tools), five.EXPECTED[arm])

    def test_source_guard(self):
        projects = {"main": "main-path", "scripting": "script-path"}
        expected = [{"revision": sha, "dirty": False} for sha in (*five.SHAS.values(), "bench")]
        with patch.object(five, "source_revision", side_effect=expected):
            five.verify_sources(projects, "bench")
        for changed in ({"revision": five.SHAS["main"], "dirty": True}, {"revision": "changed", "dirty": False}):
            with patch.object(five, "source_revision", return_value=changed), self.assertRaises(ValueError):
                five.verify_sources(projects, "bench")


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.args = argparse.Namespace(out=self.temp.name, main_project="main", scripting_project="script",
                                       limit=2, continue_unstarted=True)
        (Path(self.temp.name) / "catalog-preflight.json").write_text(json.dumps({"vendors": {"version": "fixed"}}))
        self.patch(five, "verify_sources", return_value=None)
        self.patch(five, "vendor_pins", return_value={"version": "fixed"})
        self.patch(five.suite.ab, "git", return_value="benchmark-sha")
        self.run = self.patch(five, "run_one", side_effect=lambda row, projects: row)
        self.metric = self.patch(five, "metrics", side_effect=lambda pair, arm: measured(arm))

    def patch(self, module, name, **kwargs):
        patcher = patch.object(module, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def rows(self):
        return five.suite.ab.load_log(Path(self.args.out))

    def test_bounded_run_resumes_only_missing_cells(self):
        self.assertEqual(five.do_run(self.args), 0)
        self.assertEqual(five.do_run(self.args), 0)
        self.assertEqual([r["seq"] for r in self.rows()], [1, 2, 3, 4])
        self.assertTrue(all(r["harness"] == "claude" for r in self.rows()))
        self.assertEqual(self.run.call_count, 4)

    def test_quota_failure_retained_and_blocks_resume(self):
        self.metric.side_effect = lambda pair, arm: measured(arm, **({"scorable": False, "success": False,
            "execution_status": "harness_error"} if pair["seq"] == 2 else {}))
        self.assertEqual(five.do_run(self.args), 2)
        self.assertEqual(len(self.rows()), 2)
        with self.assertRaisesRegex(ValueError, "Prior failed"):
            five.do_run(self.args)
        self.assertEqual(self.run.call_count, 2)

    def test_catalog_mismatch_retained_and_stops(self):
        self.metric.side_effect = lambda pair, arm: measured(arm, published=99)
        self.assertEqual(five.do_run(self.args), 2)
        self.assertEqual(len(self.rows()), 1)

    def test_vendor_change_blocks_resume_before_inference(self):
        five.do_run(self.args)
        five.vendor_pins.return_value = {"version": "changed"}
        with self.assertRaisesRegex(ValueError, "Vendor preflight"):
            five.do_run(self.args)
        self.assertEqual(self.run.call_count, 2)

    def test_changed_source_after_attempt_preserves_row(self):
        five.verify_sources.side_effect = [None, None, ValueError("changed")]
        with self.assertRaisesRegex(ValueError, "changed"):
            five.do_run(self.args)
        self.assertEqual(len(self.rows()), 1)

    def test_runner_exception_marker_blocks_resume(self):
        (Path(self.temp.name) / "stopped.json").write_text('{"reason": "metrics failed"}')
        with self.assertRaisesRegex(ValueError, "Prior runner exception"):
            five.do_run(self.args)
        self.run.assert_not_called()

    def test_schedule_reordering_is_not_silently_skipped(self):
        five.do_run(self.args)
        rows = self.rows()[::-1]
        (Path(self.args.out) / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        with self.assertRaisesRegex(ValueError, "Prior failed"):
            five.do_run(self.args)
        self.assertEqual(self.run.call_count, 2)


class MetricsTests(unittest.TestCase):
    def test_vendor_script_audit_and_normalization(self):
        pair = {"pair_dir": "/pair", "results": {"ego": {"run_dir": "/run"}}}
        calls = [{"tool": "run_script", "arguments": {"code": "page.evaluate(() => core.foo);"}, "error": True},
                 {"tool": "repl", "arguments": {"code": "page.goto('http://127.0.0.1:123/miniwob/x')"}, "error": False}]
        with patch.object(five.suite, "metrics", return_value=measured("ego")) as metric, \
                patch.object(five, "agent_calls", return_value=calls):
            result = five.metrics(pair, "ego")
        self.assertEqual(metric.call_args.args[0]["results"], {"kitsune": pair["results"]["ego"]})
        self.assertEqual((result["script_calls"], result["script_errors"]), (2, 1))
        self.assertEqual((result["reward_pattern_hits"], result["page_js_hits"]), (1, 1))
        self.assertEqual(len(result["script_urls"]), 1)

    def test_comparisons_use_joint_success_and_keep_failed_attempts(self):
        rows = [{**r, **measured(r["arm"]), "harness": "claude"} for r in five.plan()]
        rows[0]["success"] = False
        rows[0]["input"] = 99999
        with patch.object(five.suite.ab, "load_log", return_value=rows):
            report = five.analyze(Path("unused"))
        self.assertEqual(report["runs"], 70)
        self.assertEqual(report["arms"]["kitsune-main"]["attempts"], 14)
        self.assertEqual(report["arms"]["kitsune-main"]["successes"], 13)
        self.assertEqual(report["all_five_joint_cells"], 13)
        self.assertEqual(report["paired_ratios"]["kitsune-main"]["ego"]["joint_cells"], 13)
        self.assertEqual(report["paired_ratios"]["kitsune-main"]["ego"]["input"], 1)
        self.assertEqual(report["paired_ratios"]["kitsune-scripting"]["ego"]["joint_cells"], 14)


if __name__ == "__main__":
    unittest.main()
