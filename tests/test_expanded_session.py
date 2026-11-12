"""No-model relay/image tests. Live vendor and isolated Firefox checks are opt-in."""
import base64
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from kitsune_benchmark import gallery, personal
from kitsune_benchmark.expanded_ego_mcp import attach_images
from kitsune_benchmark.expanded_session import ExpandedSession, prepare_relay, receipt
from kitsune_benchmark.personal_session import result_json
from kitsune_benchmark.specs import Server
from kitsune_benchmark.smoke import ROOT

VALID = {"execution_status": "completed_unscored"}


def initialize(session):
    emitted = []
    session.start()
    session.forward({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "expanded-no-model-test", "version": "1"}}}, emitted.append)
    assert "error" not in emitted[0], emitted
    session.forward({"jsonrpc": "2.0", "method": "notifications/initialized"}, emitted.append)
    session.prepare()


def agent_call(session, name, arguments):
    emitted = []
    session.forward({"jsonrpc": "2.0", "id": len(session.evidence["tab_calls"]) + 10,
        "method": "tools/call", "params": {"name": name, "arguments": arguments}}, emitted.append)
    return next(r["result"] for r in emitted if "result" in r)


class ExpandedSessionTests(unittest.TestCase):
    def test_only_agent_declines_are_delayed_without_approving_them(self):
        session = ExpandedSession({"target": "kitsune", "elicitation": "decline"})
        prompt = {"requestedSchema": {"properties": {"decision": {"enum": ["Approve", "Decline"]}}}}
        with patch("kitsune_benchmark.expanded_session.time.sleep") as sleep:
            self.assertEqual(session.answer_elicitation(prompt, "agent", "browser_tabs"), {"action": "decline"})
            sleep.assert_called_once_with(2.0)
            self.assertEqual(session.answer_elicitation(prompt, "harness", "browser_tabs"),
                             {"action": "accept", "content": {"decision": "Approve"}})
            sleep.assert_called_once()

    def test_inventory_receipt_does_not_use_arbitrary_console_text(self):
        result = {"content": [{"type": "text", "text": "log\n[1,2]\n{\"inventory\":2}\n{\"wanted\":[1]}"}]}
        self.assertEqual(receipt(result, "wanted"), [1])
        with self.assertRaises(ValueError):
            receipt(result, "absent")

    def test_only_new_local_png_receipts_attach_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "image.png"
            started = time.time_ns()
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"test")
            raw = {"isError": False, "content": [{"type": "text", "text": json.dumps({"screenshot": str(path)})}]}
            result = attach_images(raw, root, started)
            self.assertEqual([c["type"] for c in result["content"]], ["text", "image"])
            self.assertEqual(len(raw["content"]), 1)
            self.assertTrue(attach_images(raw, root, time.time_ns() + 1)["isError"])
            self.assertTrue(attach_images(raw, root / "different", started)["isError"])
            path.write_bytes(b"not an image")
            self.assertTrue(attach_images(raw, root, started)["isError"])
            self.assertEqual(attach_images(raw, None, started), raw)

    def test_symlink_does_not_attach(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (root / "link.png").symlink_to(root / "source.png")
            raw = {"content": [{"type": "text", "text": json.dumps({"screenshot": str(root / "link.png")})}]}
            self.assertTrue(attach_images(raw, root, 0)["isError"])

    def test_vendor_setup_is_not_claimed_as_user_owned_or_profile_isolated(self):
        with tempfile.TemporaryDirectory() as directory, personal.PersonalServer(
                personal.selected_tasks(["pb-current-01"])[0], 0) as fixture:
            task = fixture.begin("ego")
            server = Server("ego", "python", ("old-wrapper",), (), 60, 130, enabled_tools=("run_script",))
            prepared = prepare_relay(fixture, "unique-context", Path(directory) / "images")(
                "ego", server, task, Path(directory))
            config = json.loads(Path(prepared.args[-1]).read_text())
            self.assertNotIn("seeding", config)
            self.assertIn("expanded_ego_mcp.py", config["upstream"][1])
            self.assertEqual(config["context"], "unique-context")
            self.assertEqual(config["enabled_tools"], ["run_script"])


@unittest.skipUnless(os.environ.get("EXPANDED_VENDOR_TEST") == "1", "opt-in installed vendor browsers; no model")
class VendorLiveTests(unittest.TestCase):
    def session(self, fixture, target, directory):
        task = fixture.begin(target)
        native = Server(target, str(Path.home() / ".local/bin/aside"), ("mcp",), (), 60, 130,
                        enabled_tools=("repl" if target == "aside" else "run_script",))
        context = "bm-expanded-no-model-" + Path(directory).name
        images = Path(directory) / "images"
        relay = prepare_relay(fixture, context, images)(target, native, task, Path(directory))
        return ExpandedSession(json.loads(Path(relay.args[-1]).read_text())), context, images

    def call(self, session, code):
        args = {"code": code}
        if session.config["target"] == "aside":
            args["title"] = "No-model reference action"
        result = agent_call(session, "repl" if session.config["target"] == "aside" else "run_script", args)
        self.assertFalse(result.get("isError"), result)
        return result

    def test_all_personal_initial_states_and_scorable_noncompletion(self):
        tasks = ["pb-current-01", "pb-tabs-01", "pb-research-01", "pb-account-01", "pb-handoff-01", "pb-safe-01", "pb-longpage-01"]
        for target in ("aside", "ego"):
            for task in personal.selected_tasks(tasks):
                with self.subTest(target=target, task=task["id"]), tempfile.TemporaryDirectory(prefix="expanded-") as directory, personal.PersonalServer(task, 0) as fixture:
                    session, context, _ = self.session(fixture, target, directory)
                    try:
                        initialize(session)
                        self.call(session, "console.log((await snapshot(page)).tree)" if target == "aside" else
                                  f"const t=await taskSpace({json.dumps(context)}); console.log(await t.page('p1').snapshot());")
                        grade = fixture.evaluate(target, VALID)
                        self.assertTrue(grade["scorable"], grade)
                        self.assertTrue(grade["safety_pass"], grade)
                        self.assertFalse(grade["functional_success"], grade)
                        self.assertEqual(session.evidence["profile_isolated"], False)
                    finally:
                        session.close()

    def test_chart_images_survive_actual_mcp_transport(self):
        for target in ("aside", "ego"):
            with self.subTest(target=target), tempfile.TemporaryDirectory(prefix="expanded-") as directory, gallery.GalleryServer(gallery.BY_ID["mm-chart"], 0, "isolated", "decline") as fixture:
                session, context, images = self.session(fixture, target, directory)
                try:
                    initialize(session)
                    code = "await display(await page.screenshot());" if target == "aside" else (
                        f"const t=await taskSpace({json.dumps(context)}); const p=t.page('p1'); "
                        f"console.log(JSON.stringify({{screenshot:await p.screenshot({{path:{json.dumps(str(images / 'chart.png'))}}})}}));")
                    result = self.call(session, code)
                    images = [c for c in result["content"] if c["type"] == "image"]
                    self.assertTrue(images)
                    for image in images:
                        self.assertIn(image["mimeType"], ("image/png", "image/jpeg"))
                        signature = b"\x89PNG\r\n\x1a\n" if image["mimeType"] == "image/png" else b"\xff\xd8"
                        self.assertTrue(base64.b64decode(image["data"], validate=True).startswith(signature))
                    self.assertTrue(fixture.evaluate(target, VALID)["scorable"])
                finally:
                    session.close()


@unittest.skipUnless(os.environ.get("EXPANDED_KITSUNE_TEST") == "1", "opt-in isolated Firefox; no model")
class KitsuneDeclineLiveTests(unittest.TestCase):
    def test_both_sources_decline_settles_without_timeout_or_write(self):
        from test_personal import isolated_kitsune
        sources = [ROOT / "artifacts/vendor/kitsune-code-first-baseline-47dafa2", ROOT.parent / "kitsune"]
        for source in sources:
            with self.subTest(source=str(source)), patch.dict(os.environ, KITSUNE_PROJECT=str(source)), tempfile.TemporaryDirectory(prefix="expanded-k-") as directory, personal.PersonalServer(
                    personal.selected_tasks(["pb-handoff-01"])[0], 0, user_channel=True) as fixture:
                task = fixture.begin("kitsune")
                with isolated_kitsune(directory, bidi_port=fixture.bidi_ports["kitsune"]) as upstream:
                    native = Server("kitsune", upstream[0], tuple(upstream[1:]), (), 60, 45)
                    relay = prepare_relay(fixture, "unused", Path(directory) / "images")("kitsune", native, task, Path(directory))
                    session = ExpandedSession(json.loads(Path(relay.args[-1]).read_text()))
                    try:
                        initialize(session)
                        started = time.monotonic()
                        denied = agent_call(session, "browser_tabs", {"action": "request", "index": 1, "reason": "No-model decline test"})
                        self.assertTrue(denied.get("isError"), denied)
                        self.assertEqual(result_json(denied, "state")["decision"], "declined")
                        self.assertLess(time.monotonic() - started, 15)
                        listed = agent_call(session, "browser_tabs", {"action": "list"})
                        self.assertFalse(listed.get("isError"), listed)
                        self.assertEqual(session.evidence["seeded_owned_by_agent"], 0)
                        self.assertTrue(fixture.evaluate("kitsune", VALID)["safety_pass"])
                    finally:
                        session.close()


if __name__ == "__main__":
    unittest.main()
