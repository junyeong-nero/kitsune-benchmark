"""Hostile-UI capability matrix: catalog, fixture server, target resolution and plans. No browser or model."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch
from urllib.request import Request, build_opener, ProxyHandler

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.hostile import (HostileServer, Runner, catalog, expand, matrix, page, plan, resolve,
                                       run_hostile, substitute)
from kitsune_benchmark.hostile_pages import FRAME_PAY, PAGES
from kitsune_benchmark.native import kitsune_server

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

    def test_kitsune_only_strategies_are_planned_for_kitsune_only(self):
        cells = plan(["long-press", "hover-intent", "css-hover-menu"])
        only = [cell for cell in cells if cell["kitsune_only"]]
        self.assertEqual({(c["component"], c["strategy"]) for c in only},
                         {("long-press", "long_press"), ("hover-intent", "hover_intent"), ("css-hover-menu", "hover_intent")})
        self.assertEqual({c["target"] for c in only}, {"kitsune"})
        self.assertIn({"target": "playwright", "component": "long-press", "layer": "catalog", "strategy": "click",
                       "kitsune_only": False}, cells)

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


class Session:
    """A fake MCP session: every page is ready, the snapshot has the targets, tools answer `replies[name]`."""
    def __init__(self, server, replies=None):
        self.server, self.replies, self.calls = server, replies or {}, []

    def request(self, method, params):
        name = params["name"]
        self.calls.append((name, params["arguments"]))
        if name == "browser_tabs":
            token = params["arguments"]["url"].split("/t/")[1].split("/")[0]
            self.server.state(token).ready = True
        if name == "browser_snapshot":
            return {"result": {"content": [{"type": "text", "text": PLAYWRIGHT_SNAPSHOT + HOSTILE_TARGETS}]}}
        return self.replies.get(name, {"result": {"content": [{"type": "text", "text": "{\"ok\": true}"}]}})


HOSTILE_TARGETS = """
- button "Hold to delete" [ref=e20]
- group "Preview tile" [ref=e21]"""


def reply(text, error=False):
    return {"result": {"content": [{"type": "text", "text": text}], "isError": error}}


class RunnerTests(unittest.TestCase):
    def run_strategy(self, component_id, strategy, replies=None, spec=None):
        spec = spec or catalog()
        component = next(c for c in spec["components"] if c["id"] == component_id)
        with HostileServer() as server, patch("kitsune_benchmark.hostile.SETTLE_SEC", 0.2), \
                patch("kitsune_benchmark.hostile.STEP_PAUSE", 0):
            session = Session(server, replies)
            return Runner(session, server, spec).run(component, strategy), session.calls

    def test_strategy_success_comes_from_the_page_not_the_tool(self):
        record, calls = self.run_strategy("trusted-click", "click")
        self.assertEqual(record["outcome"], "not_accepted", "an ok tool response is not success")
        self.assertEqual([name for name, _ in calls], ["browser_tabs", "browser_snapshot", "browser_click"])
        table = matrix([{**record, "target": "kitsune"}])
        self.assertIn("❌ not_accepted", table)

    def test_kitsune_only_parameters_are_sent_and_their_absence_is_unsupported(self):
        held = reply('{"ok": true, "held_ms": 712}')
        record, calls = self.run_strategy("long-press", "long_press", {"browser_click": held})
        self.assertEqual(calls[-1], ("browser_click", {"target": "e20", "hold_ms": 700, "element": "Hold to delete"}))
        self.assertEqual(record["outcome"], "not_accepted", "applied, but the fake page reports nothing")
        self.assertTrue(record["kitsune_only"])
        # v0.7.1 ignores hold_ms: the click succeeds without held_ms.
        record, _ = self.run_strategy("long-press", "long_press")
        self.assertEqual(record["outcome"], "unsupported")
        self.assertEqual(record["steps"][0]["unsupported"], ["hold_ms"])
        # A newer server with an older extension says so; the reason sits past the error's first 300 characters.
        old = reply(json.dumps({"error": "The extension clicked without holding the button", "code":
                                "extension_version_mismatch", "hint": "x" * 300, "state": {"reason": "hold_unsupported"}}),
                    error=True)
        record, _ = self.run_strategy("long-press", "long_press", {"browser_click": old})
        self.assertEqual(record["outcome"], "unsupported")
        # A hover that ignored duration_ms and steps stops the strategy before its click.
        record, calls = self.run_strategy("hover-intent", "hover_intent")
        self.assertEqual(record["outcome"], "unsupported")
        self.assertEqual(record["steps"][0]["unsupported"], ["duration_ms", "steps"])
        self.assertEqual([name for name, _ in calls], ["browser_tabs", "browser_snapshot", "browser_hover"])
        moved = reply('{"ok": true, "moves": 6, "hovered_ms": 540}')
        record, calls = self.run_strategy("hover-intent", "hover_intent", {"browser_hover": moved})
        self.assertNotIn("unsupported", record["steps"][0])
        self.assertEqual(calls[2][1], {"target": "e21", "duration_ms": 500, "steps": 5, "element": "Preview tile"})

    def test_a_shared_strategy_with_the_same_parameters_is_judged_by_the_page_only(self):
        spec = catalog()
        spec["strategies"]["shared_hover"] = spec["strategies"]["hover_intent"]
        record, calls = self.run_strategy("hover-intent", "shared_hover", spec=spec)
        self.assertFalse(record["kitsune_only"])
        self.assertEqual(record["outcome"], "target_not_found", "no unsupported mark on a shared strategy")
        self.assertNotIn("unsupported", record["steps"][0])
        self.assertEqual([name for name, _ in calls], ["browser_tabs", "browser_snapshot", "browser_hover",
                                                      "browser_snapshot"])

    def test_matrix_reports_kitsune_only_strategies_separately(self):
        rows = [{"component": "long-press", "mechanism": "hold", "strategy": "click", "target": t,
                 "kitsune_only": False, "accepted": False, "outcome": "not_accepted"} for t in ("playwright", "kitsune")]
        rows.append({"component": "long-press", "mechanism": "hold", "strategy": "long_press", "target": "kitsune",
                     "kitsune_only": True, "accepted": True, "outcome": "accepted"})
        shared, only = matrix(rows).split("Kitsune-only strategies")
        self.assertIn("| long-press | hold | click | ❌ not_accepted | ❌ not_accepted |", shared)
        self.assertNotIn("long_press", shared)
        self.assertIn("| long-press | hold | long_press | n/a | ✅ |", only)
        self.assertTrue(matrix(rows[2:]).startswith("Kitsune-only strategies"))


class NativeTests(unittest.TestCase):
    def test_kitsune_server_drops_the_benchmark_python_environment(self):
        process = MagicMock()
        with tempfile.TemporaryDirectory() as folder, \
                patch.dict(os.environ, {"VIRTUAL_ENV": "/bench/.venv", "VIRTUAL_ENV_PROMPT": "bench"}), \
                patch("kitsune_benchmark.native.resolve", return_value="/opt/codex"), \
                patch("kitsune_benchmark.native.firefox_binary", return_value="/opt/firefox"), \
                patch("kitsune_benchmark.native.copy_extension"), patch("kitsune_benchmark.native.await_bridge"), \
                patch("kitsune_benchmark.native.private_ports", return_value=(1, 2)), \
                patch("kitsune_benchmark.native.terminate_group"), \
                patch("subprocess.Popen", return_value=process) as popen:
            with kitsune_server(folder, folder) as command:
                self.assertEqual(command[-1], "kitsune")
                self.assertNotIn("VIRTUAL_ENV", os.environ, "the MCP server is started with os.environ")
                self.assertNotIn("VIRTUAL_ENV_PROMPT", os.environ)
                self.assertIn("KITSUNE_TOKEN", os.environ)
            self.assertEqual(os.environ["VIRTUAL_ENV"], "/bench/.venv")
            self.assertNotIn("VIRTUAL_ENV", popen.call_args_list[0].kwargs["env"])


if __name__ == "__main__":
    unittest.main()
