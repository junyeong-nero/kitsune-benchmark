"""No-model checks for the latest-main five-way cohort and its catalog/state safeguards."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark import adapter
from kitsune_benchmark.specs import Server, Task
from kitsune_benchmark.viewport import viewport_record

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("five_way_main", ROOT / "scripts/run-five-way-main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)
five = main.five
CATALOG = {"tools": [{"name": "test"}], "instructions": None, "server_info": {"name": "test", "version": "1"}}


class MainTests(unittest.TestCase):
    def test_same_source_actual_default_and_optout(self):
        self.assertEqual(set(five.SHAS.values()), {main.SHA})
        self.assertEqual(set(five.PROJECT_DEFAULTS.values()), {str(ROOT / "artifacts/vendor/kitsune-main-79eb955")})
        self.assertEqual(five.ARMS["kitsune-legacy"][2:], ({"KITSUNE_SCRIPTING": "0"}, None))
        self.assertEqual(five.ARMS["kitsune-default"][2:], ({}, None))
        self.assertEqual(list(five.EXPECTED.values()), [30, 14, 23, 1, 1])
        self.assertEqual(len(five.plan()), 70)
        self.assertTrue(five.RECORD_CATALOG)
        self.assertIn(ROOT / "scripts/run-five-way-main.py", five.RUNNER_FILES)
        with patch.object(five.suite.ab, "load_log", return_value=[]):
            self.assertEqual(list(five.analyze(Path("unused"))["paired_ratios"]), ["kitsune-legacy", "kitsune-default"])

    def test_fresh_context_instruction_is_shared_and_changes_per_attempt(self):
        prompts = []
        with patch.object(five, "BenchmarkServer") as server, patch.object(five.external, "verify_source"), \
                patch.object(five.external, "task_sha256", return_value="taskhash"), patch.object(five, "run_pair") as run:
            fixture = server.return_value.__enter__.return_value
            fixture.begin.return_value = Task("test", "Original task.")
            run.side_effect = lambda **kwargs: prompts.append(kwargs["task_for_target"](kwargs["targets"][0]).prompt)
            for row in (five.plan()[0], five.plan()[3], five.plan()[36]):
                five.run_one(row, five.PROJECT_DEFAULTS)
                self.assertTrue(run.call_args.kwargs["record_catalog"])
        self.assertEqual(len(set(prompts)), 3)
        self.assertTrue(all(p.startswith("Original task.") and five.CONTEXT_PREFIX in p for p in prompts))

    def test_actual_catalog_uses_first_complete_listing_not_later_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            records = [
                {"method": "initialize", "response": {"result": {"serverInfo": CATALOG["server_info"]}}},
                {"method": "tools/list", "response": {"result": {"tools": [{"name": "z"}], "nextCursor": "next"}}},
                {"method": "tools/list", "response": {"result": {"tools": [{"name": "a"}]}}},
                {"method": "tools/list", "response": {"result": {"tools": [{"name": "changed"}]}}},
            ]
            path = Path(directory) / "catalog-metadata.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in records))
            self.assertEqual([t["name"] for t in five.observed_catalog(directory)["tools"]], ["a", "z"])
            path.unlink()
            self.assertIsNone(five.observed_catalog(directory))

    def test_direct_and_gateway_page_js_are_audited_too(self):
        pair = {"pair_dir": "unused", "results": {"kitsune": {}}}
        calls = [{"tool": "browser_evaluate", "arguments": {"function": "() => core.foo"}, "error": False},
                 {"tool": "browser_tools_call", "arguments": {"name": "browser_evaluate", "arguments": {}}, "error": False}]
        with patch.object(five.suite, "metrics", return_value={"run_dir": "unused"}), \
                patch.object(five, "agent_calls", return_value=calls):
            row = five.metrics(pair, "kitsune-legacy")
        self.assertEqual((row["direct_js_calls"], row["page_js_hits"], row["reward_pattern_hits"]), (2, 2, 1))
        self.assertEqual(row["script_calls"], 0)

    def test_shared_browser_confirmation_is_narrow_and_not_isolation(self):
        task = Task("test", "test")
        for name, isolated in (("kitsune", False), ("ego", True)):
            with self.assertRaisesRegex(ValueError, "Shared-browser confirmation"):
                adapter.run(Server(name, "unused", ()), task, "test", confirm_isolated_browser=isolated,
                            confirm_shared_exhibition_browser=True)
        with patch.object(adapter, "resolve", side_effect=ValueError("past explicit browser guard")):
            with self.assertRaisesRegex(ValueError, "past explicit browser guard"):
                adapter.run(Server("ego", "unused", ()), task, "test", confirm_shared_exhibition_browser=True)
        record = viewport_record("ego", (), ("-headless", "--width=1280", "--height=720"))
        self.assertEqual(record["configured_args"], [])
        self.assertIsNone(record["configured"])


class CatalogDriverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.args = argparse.Namespace(out=str(self.out), main_project="main", scripting_project="main",
                                       limit=1, continue_unstarted=True)
        (self.out / "catalog-preflight.json").write_text(json.dumps({"vendors": {"version": "fixed"},
            "catalogs": {arm: CATALOG for arm in five.ARMS}}))
        self.patch(five, "verify_sources", return_value=None)
        self.patch(five, "vendor_pins", return_value={"version": "fixed"})
        self.patch(five.suite.ab, "git", return_value="benchmark-sha")
        self.probe = self.patch(five, "preflight", side_effect=lambda projects, arm: {arm: CATALOG})
        self.actual = self.patch(five, "observed_catalog", return_value=CATALOG)
        self.run = self.patch(five, "run_one", return_value={"pair_dir": "unused"})
        self.metric = self.patch(five, "metrics", side_effect=lambda pair, arm: {
            "success": True, "scorable": True, "execution_status": "completed_unscored", "input": 100,
            "output": 10, "requests": 4, "calls": 3, "first_input": 20, "cost": .1,
            "published": five.EXPECTED[arm], "run_dir": "unused", "script_calls": 0, "script_errors": 0})

    def patch(self, module, name, **kwargs):
        patcher = patch.object(module, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_stable_catalog_records_both_probes_and_resumes(self):
        self.assertEqual(five.do_run(self.args), 0)
        self.assertEqual(five.do_run(self.args), 0)
        self.assertEqual(len(list((self.out / "catalogs").glob("*.json"))), 4)
        self.assertEqual([r["seq"] for r in five.suite.ab.load_log(self.out)], [1, 2])

    def test_changed_preflight_stops_before_model(self):
        self.probe.side_effect = lambda projects, arm: {arm: {**CATALOG, "instructions": "changed"}}
        with self.assertRaisesRegex(ValueError, "no inference started"):
            five.do_run(self.args)
        self.run.assert_not_called()

    def test_changed_actual_catalog_preserves_attempt_and_blocks_resume(self):
        self.actual.return_value = {**CATALOG, "instructions": "changed"}
        self.assertEqual(five.do_run(self.args), 2)
        self.assertEqual(len(five.suite.ab.load_log(self.out)), 1)
        self.assertTrue((self.out / "stopped.json").exists())
        with self.assertRaisesRegex(ValueError, "Prior runner exception"):
            five.do_run(self.args)
        self.assertEqual(self.run.call_count, 1)

    def test_missing_catalog_does_not_mask_execution_failure(self):
        measured = self.metric.side_effect
        self.metric.side_effect = lambda pair, arm: {**measured(pair, arm), "execution_status": "harness_error",
                                                   "success": False, "scorable": False}
        self.actual.return_value = None
        self.assertEqual(five.do_run(self.args), 2)
        self.assertEqual(json.loads((self.out / "stopped.json").read_text())["reason"], "execution error or unscorable run")
        self.assertEqual(len(five.suite.ab.load_log(self.out)), 1)

    def test_changed_postflight_preserves_attempt(self):
        self.probe.side_effect = [{"kitsune-legacy": CATALOG}, {"kitsune-legacy": {**CATALOG, "instructions": "changed"}}]
        self.assertEqual(five.do_run(self.args), 2)
        self.assertEqual(len(five.suite.ab.load_log(self.out)), 1)
        self.assertTrue((self.out / "stopped.json").exists())


if __name__ == "__main__":
    unittest.main()
