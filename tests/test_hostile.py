"""Hostile-UI capability matrix: catalog, fixture server, target resolution and plans. No browser or model."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.request import Request, build_opener, ProxyHandler

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.hostile import (HostileServer, Runner, catalog, expand, matrix, page, plan, resolve,
                                       run_hostile, substitute)
from kitsune_benchmark.hostile_pages import FRAME_PAY, PAGES

OPENER = build_opener(ProxyHandler({}))
PLAYWRIGHT_SNAPSHOT = """### Page
```yaml
- main [ref=e2]:
  - table [ref=e4]:
    - row [ref=e6]:
      - cell "Report.pdf" [ref=e7]
  - button "Confirm" [ref=e9]
  - iframe [ref=f4e4]:
    - button "Pay" [ref=f5e4]
```"""
KITSUNE_SNAPSHOT = json.dumps({"snapshot": '- main "" [ref=e0]\n  - button "Report.pdf2 MB" [ref=e2]\n'
                                           '  - combobox "Theme" [ref=e3] [value=""]'})


class CatalogTests(unittest.TestCase):
    def test_every_component_has_a_page_or_a_bundle_and_complete_strategies(self):
        spec = catalog()
        layers = {c["layer"] for c in spec["components"]}
        self.assertEqual(layers, {"catalog", "library"})
        for c in spec["components"]:
            if c["layer"] == "catalog":
                self.assertIn(c["id"], PAGES)
                # The cross-origin frame's own page reports success.
                script = PAGES[c["id"]][2] if c["id"] != "cross-origin-iframe" else FRAME_PAY[2]
                self.assertIn("__hostile.done", script)
            else:
                self.assertTrue(c["id"].startswith("lib-"))
                self.assertIn("library", c)

    def test_plan_keeps_os_input_opt_in_and_kitsune_only(self):
        plain = plan()
        self.assertFalse(any(cell["strategy"].startswith("trusted") for cell in plain))
        trusted = plan(trusted=True)
        extra = [cell for cell in trusted if cell["strategy"].startswith("trusted")]
        self.assertTrue(extra)
        self.assertEqual({cell["target"] for cell in extra}, {"kitsune"})
        self.assertEqual(len(plan(["trusted-click"], ("kitsune",))), 1)
        with self.assertRaises(ValueError):
            plan(["nope"])

    def test_plan_only_starts_nothing_and_trusted_needs_headed(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no processes in plan")):
            result = run_hostile()
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["cells"], len(plan()))
        with self.assertRaises(ValueError):
            run_hostile(trusted=True)
        with patch("subprocess.Popen", side_effect=AssertionError("no processes")), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["hostile"]), 0)


class ResolutionTests(unittest.TestCase):
    def test_roles_and_name_substrings_resolve_in_both_formats(self):
        self.assertEqual(resolve(PLAYWRIGHT_SNAPSHOT, {"role": ["row", "cell", "button"], "name": "Report.pdf"}), "e7")
        self.assertEqual(resolve(PLAYWRIGHT_SNAPSHOT, {"role": ["button"], "name": "Pay"}), "f5e4")
        self.assertEqual(resolve(KITSUNE_SNAPSHOT, {"role": ["row", "cell", "button"], "name": "Report.pdf"}), "e2")
        self.assertEqual(resolve(KITSUNE_SNAPSHOT, {"role": ["combobox"], "name": "Theme"}), "e3")
        self.assertIsNone(resolve(KITSUNE_SNAPSHOT, {"role": ["button"], "name": "Pay"}))

    def test_steps_expand_keys_repeats_and_placeholders(self):
        steps = [{"tool": "browser_click", "args": {"target": "@field"}}, {"keys": "$text"},
                 {"tool": "browser_press_key", "args": {"key": "PageUp"}, "repeat": 2}]
        expanded = expand(steps, {"text": "ab"})
        self.assertEqual([s["args"].get("key") for s in expanded], [None, "a", "b", "PageUp", "PageUp"])
        args = substitute({"target": "@field", "text": "$text", "values": ["$text"]}, {"text": "Mango"}, {"field": "e3"})
        self.assertEqual(args, {"target": "e3", "text": "Mango", "values": ["Mango"]})


class ServerTests(unittest.TestCase):
    def test_pages_events_and_done_are_recorded_per_trial(self):
        with HostileServer() as server:
            token, url = server.begin("trusted-click")
            with OPENER.open(url, timeout=2) as response:
                html = response.read().decode()
            self.assertIn("/__hostile/report.js", html)
            self.assertIn("isTrusted", html)
            with OPENER.open(url.split("/t/")[0] + "/__hostile/report.js", timeout=2) as response:
                self.assertIn("sendBeacon", response.read().decode())
            event = url.split("/c/")[0] + "/event"
            for body in ({"kind": "ready", "events": {}}, {"kind": "progress", "detail": {"ignored": 1}},
                         {"kind": "done", "detail": {"trusted": True}, "events": {"click:trusted": 1}},
                         {"kind": "done", "detail": {"second": True}}):
                OPENER.open(Request(event, data=json.dumps(body).encode()), timeout=2).close()
            state = server.state(token)
            self.assertTrue(state.ready)
            self.assertEqual(state.done, {"trusted": True}, "the first done wins")
            self.assertEqual(state.events, {"click:trusted": 1})
            other, _ = server.begin("trusted-click")
            self.assertIsNone(server.state(other).done)

    def test_library_pages_wait_for_their_bundle_and_frames_serve(self):
        html = page("lib-radix-select")
        self.assertIn('data-manual-ready="1"', html)
        self.assertIn("/bundle/lib-radix-select.js", html)
        with HostileServer() as server:
            token, url = server.begin("cross-origin-iframe")
            frame = url.replace("/c/cross-origin-iframe", "/frame/pay")
            with OPENER.open(frame, timeout=2) as response:
                self.assertIn("Pay", response.read().decode())


class RunnerTests(unittest.TestCase):
    def test_strategy_success_comes_from_the_page_not_the_tool(self):
        class Session:
            def __init__(self, server):
                self.server, self.calls = server, []

            def request(self, method, params):
                name = params["name"]
                self.calls.append(name)
                if name == "browser_tabs":
                    token = params["arguments"]["url"].split("/t/")[1].split("/")[0]
                    self.server.state(token).ready = True
                    self.token = token
                if name == "browser_snapshot":
                    return {"result": {"content": [{"type": "text", "text": PLAYWRIGHT_SNAPSHOT}]}}
                return {"result": {"content": [{"type": "text", "text": "{\"ok\": true}"}]}}

        spec = catalog()
        component = next(c for c in spec["components"] if c["id"] == "trusted-click")
        with HostileServer() as server, patch("kitsune_benchmark.hostile.SETTLE_SEC", 0.2):
            session = Session(server)
            record = Runner(session, server, spec).run(component, "click")
            self.assertEqual(record["outcome"], "not_accepted", "an ok tool response is not success")
            self.assertEqual(session.calls, ["browser_tabs", "browser_snapshot", "browser_click"])
            table = matrix([{**record, "target": "kitsune"}])
            self.assertIn("❌ not_accepted", table)


if __name__ == "__main__":
    unittest.main()
