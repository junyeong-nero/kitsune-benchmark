"""No-model checks for bounded observation, never an empty-URL allowlist."""
import copy
import json
import unittest
from unittest.mock import patch

from kitsune_benchmark.agent_combinations_session import CombinationsSession, PENDING_URL_POLLS, PENDING_URL_SECONDS
from kitsune_benchmark.expanded_session import ExpandedSession


class PendingURLTests(unittest.TestCase):
    def setUp(self):
        self.origin = "http://127.0.0.1:5000"
        self.url = self.origin + "/t/local/order/2"
        self.seed = {"id": "seed", "url": self.origin + "/t/local/orders", "active": True, "title": "Orders"}
        self.session = CombinationsSession({"target": "browser-harness", "origin": self.origin})
        self.session.evidence.update(setup_complete=True, initial_tabs=[self.seed], snapshots=[[self.seed]])
        self.pending = [{**self.seed, "active": False}, {"id": "new", "url": "", "active": True, "title": ""}]
        self.settled = [self.pending[0], {**self.pending[1], "url": self.url}]
        self.params = {"name": "browser_new_tab", "arguments": {"url": self.url}}
        self.response = {"id": "native-1", "result": self.result({"targetId": "new"})}
        self.session.pending_tab_receipt = {"request": copy.deepcopy(self.params), "response": copy.deepcopy(self.response)}
        self.calls = []

    @staticmethod
    def result(value):
        return {"content": [{"type": "text", "text": json.dumps(value)}]}

    def observe(self, snapshots, operation=None, slow_recheck=False):
        clock = [0.0]
        state = [snapshots[0]]
        sequence = iter(snapshots)

        def tool(name, args):
            self.assertEqual(args, {})
            self.calls.append(name)
            if name == "browser_list_tabs":
                if slow_recheck and len(self.calls) > 1:
                    clock[0] += PENDING_URL_SECONDS + 1
                state[0] = next(sequence, state[0])
                return self.result([{"targetId": t["id"], "target_id": t["id"], "url": t["url"],
                                     "title": t["title"]} for t in state[0]])
            self.assertEqual(name, "browser_current_tab")
            return self.result({"targetId": next(t["id"] for t in state[0] if t["active"])})

        with patch.object(self.session, "tool", side_effect=tool), \
                patch("kitsune_benchmark.agent_combinations_session.time.monotonic", side_effect=lambda: clock[0]), \
                patch("kitsune_benchmark.agent_combinations_session.time.sleep", side_effect=lambda delay: clock.__setitem__(0, clock[0] + delay)):
            return (operation or self.session.inventory)()

    def test_local_pending_target_settles_without_mutation_or_response_rewrite(self):
        emitted = []
        message = {"jsonrpc": "2.0", "id": 42, "method": "tools/call", "params": self.params}
        with patch.object(ExpandedSession, "request", return_value=self.response), patch.object(self.session, "save"):
            self.observe([self.pending, self.settled], lambda: self.session.forward(message, emitted.append))
        self.assertEqual(emitted, [{**self.response, "id": 42}])
        self.assertEqual(self.session.evidence["outside_navigation"], 0)
        self.assertEqual(len(self.session.evidence["snapshots"]), 2)
        self.assertEqual(len(self.session.evidence["tab_calls"]), 1)
        record = self.session.evidence["pending_url_observations"][0]
        self.assertEqual(record["status"], "settled")
        self.assertEqual(record["snapshot_index"], 1)
        self.assertEqual(record["samples"][0]["tabs"][1]["url"], "")
        self.assertEqual(record["samples"][0]["native_inventory"]["listed"][1]["target_id"], "new")
        self.assertEqual(record["samples"][1]["tabs"][1]["url"], self.url)
        self.assertEqual(record["receipt"]["request"], self.params)
        self.assertEqual(self.session.evidence["post_call_inventory_sec"], record["elapsed_sec"])
        self.assertIsNone(self.session.pending_tab_receipt)
        self.assertEqual(self.calls, ["browser_list_tabs", "browser_current_tab"] * 2)

    def test_persistent_empty_stays_empty_and_counts_outside(self):
        tabs = self.observe([self.pending])
        self.assertEqual(tabs[1]["url"], "")
        self.assertEqual(self.session.evidence["outside_navigation"], 1)
        record = self.session.evidence["pending_url_observations"][0]
        self.assertEqual(record["status"], "unresolved")
        self.assertLessEqual(len(record["samples"]), PENDING_URL_POLLS + 1)
        self.assertLessEqual(record["elapsed_sec"], PENDING_URL_SECONDS)

    def test_ambiguous_or_unrequested_empty_is_never_repolled(self):
        for case in ("missing_receipt", "failed_call", "missing_target", "reused_seed", "closed_old_target",
                     "foreign_request", "blank_request", "missing_previous", "unrelated_call", "extra_target"):
            with self.subTest(case=case):
                self.setUp()
                receipt = self.session.pending_tab_receipt
                if case == "missing_receipt":
                    self.session.pending_tab_receipt = None
                elif case == "failed_call":
                    receipt["response"]["result"]["isError"] = True
                elif case == "missing_target":
                    receipt["response"]["result"] = self.result({})
                elif case == "reused_seed":
                    receipt["response"]["result"] = self.result({"targetId": "seed"})
                    self.pending = [{**self.seed, "url": ""}]
                elif case == "closed_old_target":
                    self.session.evidence["snapshots"].insert(0, [*self.session.evidence["initial_tabs"], self.settled[1]])
                elif case == "foreign_request":
                    receipt["request"]["arguments"]["url"] = "https://outside.invalid/"
                elif case == "blank_request":
                    receipt["request"]["arguments"]["url"] = "about:blank"
                elif case == "missing_previous":
                    self.session.evidence["snapshots"] = []
                elif case == "unrelated_call":
                    receipt["request"]["name"] = "browser_js"
                else:
                    self.pending.append({**self.seed, "id": "unrequested", "active": False})
                self.observe([self.pending])
                self.assertEqual(self.calls, ["browser_list_tabs", "browser_current_tab"])
                self.assertEqual(self.session.evidence["outside_navigation"], 1)
                self.assertEqual(self.session.evidence["pending_url_observations"][0]["status"], "ineligible")

    def test_unexpected_resolution_is_a_failure_not_a_normalized_url(self):
        for url in ("https://outside.invalid/", "chrome://settings/help", "about:blank", self.origin + "/different"):
            with self.subTest(url=url):
                self.setUp()
                changed = [self.settled[0], {**self.settled[1], "url": url}]
                with self.assertRaisesRegex(ValueError, "unexpected URL"):
                    self.observe([self.pending, changed])
                record = self.session.evidence["pending_url_observations"][0]
                self.assertEqual(record["status"], "failed")
                self.assertEqual(record["samples"][-1]["tabs"][1]["url"], url)

    def test_nonpending_target_change_is_not_hidden_by_a_settled_target(self):
        for change in ("foreign", "missing", "extra", "active"):
            with self.subTest(change=change):
                self.setUp()
                changed = copy.deepcopy(self.settled)
                if change == "foreign":
                    changed[0]["url"] = "https://outside.invalid/"
                elif change == "missing":
                    changed.pop(0)
                elif change == "extra":
                    changed.append({**self.seed, "id": "extra", "active": False})
                else:
                    changed[0]["active"], changed[1]["active"] = True, False
                with self.assertRaisesRegex(ValueError, "Ambiguous inventory"):
                    self.observe([self.pending, changed])
                self.assertEqual(self.session.evidence["pending_url_observations"][0]["status"], "failed")

    def test_late_rpc_cannot_extend_the_settlement_window(self):
        with self.assertRaisesRegex(ValueError, "exceeded its window"):
            self.observe([self.pending, self.settled], slow_recheck=True)
        self.assertEqual(self.session.evidence["pending_url_observations"][0]["status"], "failed")

    def test_real_foreign_url_without_pending_state_counts_normally(self):
        foreign = [self.settled[0], {**self.settled[1], "url": "https://outside.invalid/"}]
        self.observe([foreign])
        self.assertEqual(self.session.evidence["outside_navigation"], 1)
        self.assertNotIn("pending_url_observations", self.session.evidence)

    def test_existing_inactive_help_keeps_one_main_observation_per_call(self):
        help_tab = {"id": "help", "url": "chrome://settings/help", "active": False, "title": "Help"}
        self.session.evidence["snapshots"].append([self.seed, help_tab])
        self.session.evidence["outside_navigation"] = 1
        self.observe([[*self.pending, help_tab], [*self.settled, help_tab]])
        self.assertEqual(self.session.evidence["outside_navigation"], 2)
        self.assertEqual(self.session.evidence["pending_url_observations"][0]["status"], "settled")

    def test_fresh_help_or_existing_foreign_does_not_qualify_for_stabilization(self):
        for url, known in (("chrome://settings/help", False), ("https://outside.invalid/", True)):
            with self.subTest(url=url):
                self.setUp()
                foreign = {"id": "foreign", "url": url, "active": False, "title": "Foreign"}
                if known:
                    self.session.evidence["snapshots"].append([self.seed, foreign])
                self.observe([[*self.pending, foreign]])
                self.assertEqual(self.session.evidence["outside_navigation"], 2)
                self.assertEqual(self.session.evidence["pending_url_observations"][0]["status"], "ineligible")

    def test_setup_is_not_reinterpreted_by_agent_observer(self):
        self.session.evidence["setup_complete"] = False
        self.observe([self.pending])
        self.assertNotIn("pending_url_observations", self.session.evidence)
        self.assertEqual(self.session.evidence["outside_navigation"], 0)

    def test_cleanup_error_is_not_masked(self):
        with patch.object(ExpandedSession, "close", side_effect=ValueError("cleanup failed")), patch.object(self.session, "save"):
            with self.assertRaisesRegex(ValueError, "cleanup failed"):
                self.session.close()
        self.assertNotIn("session_closed", self.session.evidence)


if __name__ == "__main__":
    unittest.main()
