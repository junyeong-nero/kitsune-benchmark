"""Opt-in, no-model v4 seeding and document-verification regression through real MCP UI tools."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark.personal import PersonalServer
from kitsune_benchmark.personal_session import NativeSession
from kitsune_benchmark.smoke import ROOT
from test_coexistence import ref_for, snapshot_text
from test_personal import agent_tool, isolated_kitsune
from test_taskset_v4 import VALID, new_tasks


class NativeTasksetV4Tests(unittest.TestCase):
    def run_tasks(self, target):
        for task in new_tasks():
            variants = range(3) if task["fixture"] == "doc_verify" else (0,)
            for variant in variants:
                with self.subTest(target=target, task=task["id"], variant=variant), \
                        tempfile.TemporaryDirectory(prefix="v4-", dir="/tmp") as folder, \
                        PersonalServer(task, variant, report_viewport=True, user_channel=True) as server, \
                        ExitStack() as stack:
                    server.begin(target)
                    trial = server.trials[server.by_target[target]]
                    port = server.bidi_ports[target]
                    if target == "kitsune":
                        upstream = stack.enter_context(isolated_kitsune(folder, 805, bidi_port=port))
                    else:
                        options = Path(folder) / "user-channel.json"
                        options.write_text(json.dumps({"browser": {"launchOptions": {
                            "args": [f"--remote-debugging-port={port}", "--remote-allow-system-access"],
                            "firefoxUserPrefs": {"remote.prefs.recommended": False}}}}))
                        stack.enter_context(patch.dict(os.environ, {
                            "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / "artifacts/browsers"),
                            "PLAYWRIGHT_SKIP_BROWSER_GC": "1", "PWTEST_SOCKETS_DIR": folder}))
                        upstream = ["node", str(ROOT / "node_modules/@playwright/mcp/cli.js"), "--browser", "firefox",
                                    "--isolated", "--headless", "--viewport-size", "1280x720", "--config", str(options)]
                    session = NativeSession({"target": target, "upstream": upstream,
                        "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
                        "active_index": trial.active_index, "evidence_path": folder + "/evidence.json",
                        "origin": server.origin, "seeding": "user_channel",
                        "user_driver": {"bidi_url": f"ws://127.0.0.1:{port}"}})
                    stack.callback(session.close)
                    session.start()
                    initialized = session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                        "clientInfo": {"name": "taskset-v4-test", "version": "1"}})
                    self.assertNotIn("error", initialized)
                    session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                    session.prepare()
                    self.assertTrue(session.evidence["setup_complete"])
                    self.assertEqual(session.evidence["seeding"], "user_channel")
                    self.assertEqual(session.evidence["seeded_owned_by_agent"], 0 if target == "kitsune" else None)
                    seeded = trial.evaluate(VALID, session.evidence)
                    self.assertTrue(seeded["scorable"] and seeded["initial_state_verified"], seeded)
                    self.assertEqual(seeded["seeded_tab_custody"]["custody"], "kept")
                    if task["fixture"] == "doc_verify":
                        self.verify_document(session, trial)

    def verify_document(self, session, trial):
        def call(name, arguments):
            result = agent_tool(session, name, arguments)
            self.assertFalse(result.get("isError"), result)
            return "\n".join(item.get("text", "") for item in result.get("content", []))

        def form(path, values, button):
            # Work in an agent-owned copy; neither target navigates or writes a starting tab.
            opened = call("browser_tabs", {"action": "new", "url": trial.url(path)})
            tree = snapshot_text(session, opened)
            for label, value in values.items():
                if value:
                    call("browser_type", {"target": ref_for(tree, "textbox", label), "element": label, "text": value})
            clicked = call("browser_click", {"target": ref_for(tree, "button", button), "element": button})
            # Playwright action replies can link a snapshot file instead of embedding the page text.
            return snapshot_text(session, clicked)

        _, number, when, issuer = trial.impl.DATA[trial.variant]
        failed = form("/verify", {"문서확인번호": number, "발급일자": "2027-01-01"}, "확인하기")
        self.assertIn("일치하지 않습니다" if issuer else "일치하는 문서가 없습니다", failed)
        form("/memo", trial.impl.expected, "저장")
        outcome = trial.evaluate(VALID, session.evidence)
        self.assertTrue(outcome["scorable"] and outcome["safety_pass"], outcome)
        self.assertFalse(outcome["task_success"], outcome)
        verified = form("/verify", {"문서확인번호": number, "발급일자": when}, "확인하기")
        self.assertIn("정상 발급된 진본" if issuer else "일치하는 문서가 없습니다", verified)
        outcome = trial.evaluate(VALID, session.evidence)
        self.assertTrue(outcome["task_success"], outcome)
        self.assertEqual(outcome["seeded_tab_custody"]["custody"], "kept")
        self.assertEqual(outcome["saved_state"]["verification_checks"][-1]["status"],
                         "verified" if issuer else "not_found")

    @unittest.skipUnless(os.environ.get("PERSONAL_KITSUNE_TEST") == "1", "opt-in isolated Kitsune; no model calls")
    def test_kitsune_v4_seeding_and_document_verification(self):
        self.run_tasks("kitsune")

    @unittest.skipUnless(os.environ.get("PERSONAL_BROWSER_TEST") == "1", "opt-in isolated Playwright; no model calls")
    def test_playwright_v4_seeding_and_document_verification(self):
        self.run_tasks("playwright")


if __name__ == "__main__":
    unittest.main()
