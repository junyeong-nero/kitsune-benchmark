import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark.disclosure_session import DisclosureSession
from kitsune_benchmark.disclosure_experiment import (
    ARMS, PIN, TASKS, EXPECT_GUIDANCE, ExperimentFixture, budget_allows, schedule, run)
from kitsune_benchmark.personal import PersonalServer, selected_tasks
from kitsune_benchmark.smoke import ROOT, source_revision


class FakeSession(DisclosureSession):
    def __init__(self, policy="rich", replies=None):
        super().__init__({"target": "kitsune", "disclosure_policy": policy})
        self.calls = []
        self.replies = list(replies or [])
        self.diagnostics = []

    def native_request(self, method, params=None, **kwargs):
        self.calls.append((method, copy.deepcopy(params), kwargs["role"]))
        return self.replies.pop(0) if self.replies else {
            "result": {"content": [{"type": "text", "text": "original"}], "structuredContent": {"text": "original"}}}

    def diagnostic(self, kind, **values):
        self.diagnostics.append((kind, values))


class DisclosureTests(unittest.TestCase):
    def test_native_is_exact_passthrough(self):
        s = FakeSession("native")
        params = {"name": "browser_page_text", "arguments": {"tab_id": 3}}
        result = s.request("tools/call", params, role="agent")
        self.assertEqual(len(s.calls), 1)
        self.assertEqual(s.calls[0][1], params)
        self.assertEqual(result["result"]["content"][0]["text"], "original")

    def test_snapshot_adds_text_without_losing_scope_or_mutating_input(self):
        s = FakeSession()
        p = {"name": "browser_snapshot", "arguments": {"tab_id": 4, "selector": "main", "max_depth": 2, "text": False}}
        s.request("tools/call", p, role="agent")
        self.assertFalse(p["arguments"]["text"])
        self.assertEqual(s.calls[0][1]["arguments"], {**p["arguments"], "text": True})

    def test_inventory_only_is_expanded(self):
        for action in ("list", "new", "close", "select"):
            s = FakeSession()
            p = {"name": "browser_tabs", "arguments": {"action": action}}
            s.request("tools/call", p, role="agent")
            self.assertEqual(s.calls[0][1]["arguments"].get("include_active", False), action == "list")

    def test_setup_and_tool_schema_unchanged(self):
        for method, role in [("tools/call", "harness"), ("tools/list", "agent")]:
            s = FakeSession()
            p = {"name": "browser_snapshot", "arguments": {}}
            s.request(method, p, role=role)
            self.assertEqual(s.calls[0][1], p)
            self.assertFalse(s.diagnostics)

    def test_page_text_keeps_original_and_adds_refs_to_same_tab(self):
        s = FakeSession()
        result = s.request("tools/call", {"name": "browser_page_text", "arguments": {"tab_id": 7}}, role="agent")
        self.assertEqual(s.calls[1], ("tools/call", {"name": "browser_snapshot", "arguments": {"text": False, "tab_id": 7}}, "disclosure"))
        self.assertEqual(result["result"]["content"][0]["text"], "original")
        self.assertIn("additional_actionable_context", result["result"]["structuredContent"])
        self.assertEqual(len(s.calls), 2)

    def test_failed_primary_read_is_not_enriched(self):
        for reply in [{"error": {"code": -1}}, {"result": {"isError": True, "content": []}}]:
            s = FakeSession(replies=[reply])
            self.assertEqual(s.request("tools/call", {"name": "browser_page_text"}, role="agent"), reply)
            self.assertEqual(len(s.calls), 1)

    def test_failed_supplement_is_marked_not_silenced_or_retried(self):
        primary = {"result": {"content": [{"type": "text", "text": "original"}]}}
        s = FakeSession(replies=[primary, {"result": {"isError": True, "content": [{"type": "text", "text": "error"}]}}])
        r = s.request("tools/call", {"name": "browser_page_text", "arguments": {}}, role="agent")
        self.assertNotIn("isError", r["result"])
        self.assertIn("unavailable", r["result"]["content"][1]["text"])
        self.assertTrue(s.diagnostics[-1][1]["supplement_failed"])
        self.assertEqual(len(s.calls), 2)

    def test_write_and_expect_arguments_never_modified(self):
        s = FakeSession()
        p = {"name": "browser_click", "arguments": {"ref": "e1", "expect": {"url_changed": True}}}
        s.request("tools/call", p, role="agent")
        self.assertEqual(s.calls[0][1], p)
        self.assertEqual(len(s.calls), 1)

    def test_invalid_policy_or_target_rejected(self):
        with self.assertRaises(ValueError):
            FakeSession("typo")
        with self.assertRaises(ValueError):
            DisclosureSession({"target": "playwright"})

    def test_complete_matched_schedule(self):
        plan = schedule()
        self.assertEqual(len(plan), 72)
        self.assertEqual(len({p["block"] for p in plan}), 18)
        for task in TASKS:
            for rep in range(3):
                block = [p for p in plan if p["task"] == task and p["repeat"] == rep]
                self.assertEqual({p["arm"] for p in block}, set(ARMS))
                self.assertEqual({p["position"] for p in block}, {0, 1, 2, 3})

    def test_budget_reserves_full_cap(self):
        self.assertTrue(budget_allows(1.5, 2, .5))
        self.assertFalse(budget_allows(1.50001, 2, .5))

    def test_plan_never_invokes_model_or_creates_directory(self):
        with tempfile.TemporaryDirectory() as root, patch("kitsune_benchmark.disclosure_experiment.run_pair") as mock:
            out = Path(root) / "new"
            result = run(out, Path(root), execute=False)
            self.assertEqual(len(result["schedule"]), 72)
            self.assertFalse(out.exists())
            mock.assert_not_called()

    def test_prepare_server_updates_existing_settings(self):
        from kitsune_benchmark.specs import Server
        task = selected_tasks([TASKS[0]])[0]
        fixture = ExperimentFixture(task, 0, "B")
        fixture.origin = "http://127.0.0.1:12345"
        request = fixture.begin("kitsune")
        with tempfile.TemporaryDirectory() as root:
            server = fixture.prepare_server("kitsune", Server("kitsune", "echo", ()), request, Path(root))
            settings = json.loads(Path(server.args[-1]).read_text())
            self.assertEqual(settings["disclosure_policy"], "rich")
            self.assertTrue(server.args[0].endswith("disclosure_session.py"))

    def test_execute_updates_status_multiple_times_without_overwriting_evidence(self):
        from kitsune_benchmark.disclosure_experiment import PIN
        fake_pair = {"results": {"kitsune": {"benchmark_evaluation": {"scorable": True}, "list_price_cost_usd": 0.001}}}
        with tempfile.TemporaryDirectory() as root, \
                patch("kitsune_benchmark.disclosure_experiment.schedule", return_value=schedule()[:2]), \
                patch("kitsune_benchmark.disclosure_experiment.source_revision", return_value={"revision": PIN, "dirty": False}), \
                patch("kitsune_benchmark.disclosure_experiment.ExperimentFixture"), \
                patch("kitsune_benchmark.disclosure_experiment.run_pair", return_value=fake_pair) as mock:
            out = Path(root) / "new"
            result = run(out, Path(root), execute=True)
            self.assertEqual(result["runs"], 2)
            self.assertEqual(result["state"], "completed")
            self.assertEqual(len(json.loads((out / "summary.json").read_text())["runs"]), 2)
            self.assertEqual(mock.call_count, 2)
            self.assertEqual(mock.call_args.kwargs["executable"], "claude")
            self.assertEqual(mock.call_args.kwargs["harness"], "claude-api")
            with self.assertRaises(FileExistsError):
                run(out, Path(root), execute=True)

    def test_prompt_preserves_original_contract(self):
        task = selected_tasks([TASKS[0]])[0]
        for arm in ARMS:
            # Trial initialization only: no browser/model/HTTP server needed.
            fixture = ExperimentFixture(task, 0, arm)
            fixture.origin = "http://127.0.0.1:12345"
            base = PersonalServer(task, 0)
            base.origin = fixture.origin
            original = base.begin("kitsune").prompt
            prompt = fixture.begin("kitsune").prompt
            self.assertEqual(prompt, original + ("\n" + EXPECT_GUIDANCE if ARMS[arm][1] else ""))


@unittest.skipUnless(os.environ.get("DISCLOSURE_BROWSER_TEST") == "1", "opt-in no-model Firefox test")
class NativeDisclosureTests(unittest.TestCase):
    def test_enrichment_in_real_firefox(self):
        # v0.7.1+ core is Playwright-shaped: include_active/text are dropped and browser_page_text is unpublished.
        revision = source_revision(Path(os.environ.get("KITSUNE_PROJECT", ROOT.parent / "kitsune")))["revision"]
        if revision != PIN:
            self.skipTest(f"rich disclosure targets the experiment's Kitsune {PIN[:7]}, not {revision}")
        from test_personal import isolated_kitsune
        task = selected_tasks([TASKS[0]])[0]
        with tempfile.TemporaryDirectory(prefix="disc-", dir="/tmp") as folder, PersonalServer(task, 0) as fixture:
            fixture.begin("kitsune")
            trial = fixture.trials[fixture.by_target["kitsune"]]
            with isolated_kitsune(folder) as upstream:
                session = DisclosureSession({"target": "kitsune", "disclosure_policy": "rich", "upstream": upstream,
                    "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
                    "active_index": trial.active_index, "evidence_path": folder + "/evidence.json",
                    "origin": fixture.origin, "diagnostics_path": folder + "/rpc.jsonl"})
                try:
                    session.start()
                    session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                        "clientInfo": {"name": "disclosure-test", "version": "1"}})
                    session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                    session.prepare()
                    inventory_before = session.inventory()
                    for name, arguments in (("browser_tabs", {"action": "list"}), ("browser_snapshot", {}),
                                            ("browser_page_text", {})):
                        responses = []
                        session.forward({"jsonrpc": "2.0", "id": name, "method": "tools/call",
                            "params": {"name": name, "arguments": arguments}}, responses.append)
                        reply = responses[-1]
                        self.assertNotIn("error", reply)
                        self.assertFalse(reply["result"].get("isError", False))
                        if name == "browser_tabs":
                            self.assertIn("active_page", str(reply))
                        if name == "browser_page_text":
                            self.assertIn("Additional actionable context", str(reply))
                            self.assertIn("ref=", str(reply))
                    self.assertEqual(inventory_before, session.inventory())
                    rpc = [json.loads(line) for line in Path(folder + "/rpc.jsonl").read_text().splitlines()]
                    self.assertEqual(sum(x["kind"] == "rpc_completed" and x.get("role") == "disclosure" for x in rpc), 1)
                    self.assertFalse(next(x for x in rpc if x["kind"] == "disclosure_delivered")["supplement_failed"])
                finally:
                    session.close()


if __name__ == "__main__":
    unittest.main()
