"""Offline checks for native schema preservation and pilot-specific provenance."""
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image

from kitsune_benchmark.agent_combinations_session import CombinationsSession, browser_harness_image
from kitsune_benchmark.expanded_session import ExpandedSession


class SessionTests(unittest.TestCase):
    def test_decline_is_explicit_form_content_not_unknown_protocol_decline(self):
        session = CombinationsSession({"target": "kitsune"})
        params = {"message": "Held because the agent did not open this tab",
                  "requestedSchema": {"properties": {"decision": {"enum": ["Approve", "Decline"]}}}}
        self.assertEqual(session.answer_elicitation(params, "agent", "browser_tools_call"),
                         {"action": "accept", "content": {"decision": "Decline"}})
        self.assertEqual(session.evidence["elicitations"][-1]["provenance"], "simulated_form_decision")
        self.assertEqual(session.answer_elicitation(params, "harness", "browser_tools_call"),
                         {"action": "accept", "content": {"decision": "Approve"}})
        self.assertEqual(session.answer_elicitation({}, "agent", "browser_ask_user"), {"action": "decline"})

    def test_kitsune_setup_routes_unlisted_controls_through_actual_gateway(self):
        session = CombinationsSession({"target": "kitsune"})
        with patch.object(ExpandedSession, "tool", return_value={}) as tool:
            session.tool("browser_navigate", {"url": "about:blank"})
            tool.assert_called_once_with("browser_tools_call", {"name": "browser_navigate", "arguments": {"url": "about:blank"}}, ())
            tool.reset_mock()
            session.tool("browser_tabs", {"action": "list"})
            tool.assert_called_once_with("browser_tabs", {"action": "list"}, ())

    def test_devtools_inventory_retains_native_ids_selection_and_checks_origin(self):
        session = CombinationsSession({"target": "devtools", "origin": "http://127.0.0.1:5000"})
        result = {"content": [{"type": "text", "text": "## Pages\n1: about:blank\n3: http://127.0.0.1:5000/task [selected]"}]}
        with patch.object(session, "tool", return_value=result):
            tabs = session.inventory()
            self.assertEqual([t["id"] for t in tabs], [1, 3])
            self.assertEqual([t["active"] for t in tabs], [False, True])
            session.evidence["setup_complete"] = True
            session.inventory()
            self.assertEqual(session.evidence["outside_navigation"], 0)
            self.assertIn("post_call_inventory_sec", session.evidence)

    def test_browser_harness_bridge_attaches_only_fresh_owned_pngs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shot.png"
            started = time.time_ns()
            Image.new("RGB", (8, 8)).save(path)
            result = {"content": [{"type": "text", "text": json.dumps({"path": str(path), "width": 8, "height": 8})}]}
            attached = browser_harness_image(result, directory, started)
            self.assertEqual(attached["content"][0], result["content"][0])
            self.assertEqual(attached["content"][1]["type"], "image")
            self.assertNotIn("isError", attached)
            self.assertTrue(browser_harness_image(result, directory, time.time_ns() + 10_000_000)["isError"])
            self.assertTrue(browser_harness_image(result, Path(directory) / "different", started)["isError"])

    def test_setup_responses_are_retained_but_agent_responses_are_not_duplicated(self):
        session = CombinationsSession({"target": "browser-harness"})
        params = {"name": "browser_current_tab", "arguments": {}}
        reply = {"id": "1", "result": {"content": [{"type": "text", "text": "{}"}]}}
        with patch.object(ExpandedSession, "request", return_value=reply):
            session.request("tools/call", params)
            session.evidence["setup_complete"] = True
            session.request("tools/call", params, role="agent")
        self.assertEqual(session.evidence["setup_rpc"], [{"request": params, "response": reply}])

    def test_browser_harness_navigation_waits_for_committed_url_and_load(self):
        session = CombinationsSession({"target": "browser-harness"})
        url = "http://127.0.0.1:5000/task"
        replies = [{}, {"targetId": "owned", "url": "about:blank"},
                   {"targetId": "owned", "url": url}, {"ok": True}]
        with patch.object(session, "tool", side_effect=[{"content": [{"type": "text", "text": json.dumps(v)}]} for v in replies]) as tool, \
                patch("kitsune_benchmark.agent_combinations_session.time.sleep"):
            session.navigate(url, {"id": "owned"})
        self.assertEqual([c.args[0] for c in tool.call_args_list],
                         ["browser_goto", "browser_current_tab", "browser_current_tab", "browser_wait_for_load"])

    def test_browser_harness_navigation_timeout_is_not_ignored(self):
        session = CombinationsSession({"target": "browser-harness"})
        blank = {"content": [{"type": "text", "text": json.dumps({"targetId": "owned", "url": "about:blank"})}]}
        with patch.object(session, "tool", return_value=blank), \
                patch("kitsune_benchmark.agent_combinations_session.time.monotonic", side_effect=[0, 0, 6]), \
                patch("kitsune_benchmark.agent_combinations_session.time.sleep"):
            with self.assertRaisesRegex(ValueError, "navigation"):
                session.navigate("http://127.0.0.1:5000/task", {"id": "owned"})

    def test_browser_harness_setup_cannot_reuse_a_stale_blank_target(self):
        # The pinned native new_tab(url) may reuse the current blank target while
        # navigation is in flight. Force that documented branch deterministically.
        class DelayedHarness(CombinationsSession):
            def __init__(self, config):
                super().__init__(config)
                self.tabs = {"t1": "about:blank"}
                self.current = "t1"
                self.new_urls = []

            def inventory(self):
                return [{"id": key, "url": url, "active": key == self.current} for key, url in self.tabs.items()]

            def navigate(self, url, tab):
                self.tabs[tab["id"]] = url

            def tool(self, name, args):
                value = {}
                if name == "browser_switch_tab":
                    self.current = args["target"]
                elif name == "browser_new_tab":
                    self.new_urls.append(args["url"])
                    if args["url"] == "about:blank":
                        self.current = "t" + str(len(self.tabs) + 1)
                    self.tabs[self.current] = args["url"]
                    value = {"targetId": self.current}
                else:
                    raise AssertionError(name)
                return {"content": [{"type": "text", "text": json.dumps(value)}]}

        urls = ["http://127.0.0.1:5000/" + path for path in ("directory", "memo", "protected")]
        session = DelayedHarness({"target": "browser-harness", "chrome_ws_url": "ws://127.0.0.1:55555/devtools/browser/owned",
            "origin": "http://127.0.0.1:5000", "bootstrap_url": "http://127.0.0.1:5000/start", "urls": urls, "active_index": 0})
        with patch("kitsune_benchmark.agent_combinations_session.urllib.request.build_opener") as opener, patch.object(session, "save"):
            opener.return_value.open.return_value = io.StringIO('[{"id":"t1","type":"page"}]')
            session.prepare()
        self.assertEqual(session.new_urls, ["about:blank", "about:blank"])
        self.assertEqual(sorted(session.tabs.values()), sorted(urls))
        self.assertEqual(len(session.evidence["fixture_tabs_before_validation"]), 3)

    def test_private_upstream_env_does_not_replace_cli_login_environment(self):
        env = {"HOME": "/owned", "BU_CDP_WS": "ws://127.0.0.1:55555/devtools/browser/owned"}
        session = CombinationsSession({"target": "browser-harness", "upstream_env": env})
        with patch.object(ExpandedSession, "start") as start:
            session.start()
            start.assert_called_once_with(env=env)


if __name__ == "__main__":
    unittest.main()
