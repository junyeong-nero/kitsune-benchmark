"""Offline checks for native schema preservation and pilot-specific provenance."""
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

    def test_private_upstream_env_does_not_replace_cli_login_environment(self):
        env = {"HOME": "/owned", "BU_CDP_WS": "ws://127.0.0.1:55555/devtools/browser/owned"}
        session = CombinationsSession({"target": "browser-harness", "upstream_env": env})
        with patch.object(ExpandedSession, "start") as start:
            session.start()
            start.assert_called_once_with(env=env)


if __name__ == "__main__":
    unittest.main()
