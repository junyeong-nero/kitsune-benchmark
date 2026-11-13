"""No model or browser is launched by these unit tests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import psutil

from kitsune_benchmark import private_chrome as chrome


class PrivateChromeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executable = self.root / "chrome"
        self.executable.touch()

    def endpoint(self, value):
        (self.root / "DevToolsActivePort").write_text(value)
        return chrome.connection(self.root)

    def test_endpoint_accepts_only_owned_loopback_shape(self):
        self.assertEqual(self.endpoint("53128\n/devtools/browser/test-id\n"),
                         "ws://127.0.0.1:53128/devtools/browser/test-id")
        for value in ("9222\n/devtools/browser/id", "47651\n/devtools/browser/id",
                      "70000\n/devtools/browser/id", "abc\n/devtools/browser/id",
                      "53128\nws://example.com/devtools/browser/id",
                      "53128\n//example.com/devtools/browser/id",
                      "53128\n/devtools/browser/id?token=secret",
                      "53128\n/devtools/browser/has space", "53128"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.endpoint(value)

    def test_launch_uses_new_profile_and_strips_model_credentials(self):
        process = Mock(pid=1234)
        process.poll.return_value = None
        with patch.object(chrome.subprocess, "Popen", return_value=process) as spawn, \
                patch.object(chrome.psutil, "Process") as proc, \
                patch.object(chrome, "connection", return_value="ws://127.0.0.1:53128/devtools/browser/id"), \
                patch.dict(os.environ, {"HOME": "/everyday", "ANTHROPIC_API_KEY": "secret",
                                        "BU_CDP_URL": "http://localhost:9222", "AGENT_BROWSER_AUTO_CONNECT": "1"}):
            proc.return_value.create_time.return_value = 42.0
            record = chrome.launch(self.root / "runs", executable=self.executable)
        argv = spawn.call_args.args[0]
        options = spawn.call_args.kwargs
        self.assertIn("--headless=new", argv)
        self.assertIn("--remote-debugging-port=0", argv)
        self.assertIn("--disable-sync", argv)
        self.assertIn("--password-store=basic", argv)
        self.assertIn("--use-mock-keychain", argv)
        self.assertIn("--disable-component-update", argv)
        self.assertIn("--no-service-autorun", argv)
        self.assertIn(f"--user-data-dir={record['profile']}", argv)
        self.assertTrue(options["start_new_session"])
        self.assertEqual(options["cwd"], Path(record["folder"]))
        self.assertNotEqual(options["env"]["HOME"], "/everyday")
        for key in ("ANTHROPIC_API_KEY", "BU_CDP_URL", "AGENT_BROWSER_AUTO_CONNECT"):
            self.assertNotIn(key, options["env"])
        self.assertEqual(Path(record["folder"]).stat().st_mode & 0o777, 0o700)
        path = Path(record["folder"]) / "launcher.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(json.loads(path.read_text())["model_invoked"])

    def test_invalid_endpoint_cleans_up_only_owned_process(self):
        process = Mock(pid=1234)
        process.poll.return_value = None
        with patch.object(chrome.subprocess, "Popen", return_value=process), \
                patch.object(chrome.psutil, "Process"), \
                patch.object(chrome, "connection", side_effect=ValueError("unsafe port")), \
                patch.object(chrome, "terminate_group") as stop:
            with self.assertRaisesRegex(ValueError, "unsafe port"):
                chrome.launch(self.root / "runs", executable=self.executable)
        stop.assert_called_once_with(process)

    def test_startup_timeout_cleans_up_owned_process(self):
        process = Mock(pid=1234)
        with patch.object(chrome.subprocess, "Popen", return_value=process), \
                patch.object(chrome.psutil, "Process"), \
                patch.object(chrome, "terminate_group") as stop:
            with self.assertRaises(TimeoutError):
                chrome.launch(self.root / "runs", executable=self.executable, timeout=0)
        stop.assert_called_once_with(process)

    def test_arbitrary_startup_urls_are_rejected_without_launch(self):
        with patch.object(chrome.subprocess, "Popen") as spawn:
            for url in ("file:///etc/passwd", "https://example.com", "https://claude.ai.evil.test/"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    chrome.launch(self.root / "runs", executable=self.executable, url=url)
        spawn.assert_not_called()

    def test_stop_refuses_reused_pid_or_foreign_profile(self):
        record = {"pid": 1234, "created": 42.0, "profile": "/owned/profile"}
        with patch.object(chrome.psutil, "Process") as proc, patch.object(chrome.os, "killpg") as kill:
            proc.return_value.create_time.return_value = 43.0
            with self.assertRaisesRegex(ValueError, "identity"):
                chrome.stop(record)
            proc.return_value.create_time.return_value = 42.0
            proc.return_value.cmdline.return_value = ["chrome", "--user-data-dir=/everyday/profile"]
            with self.assertRaisesRegex(ValueError, "identity"):
                chrome.stop(record)
        kill.assert_not_called()

    def test_stop_accepts_only_verified_process_group(self):
        record = {"pid": 1234, "created": 42.0, "profile": "/owned/profile"}
        with patch.object(chrome.psutil, "Process") as proc, \
                patch.object(chrome.os, "getpgid", return_value=1234), \
                patch.object(chrome.os, "killpg") as kill:
            proc.return_value.pid = 1234
            proc.return_value.create_time.return_value = 42.0
            proc.return_value.cmdline.return_value = ["chrome", "--user-data-dir=/owned/profile"]
            chrome.stop(record)
            kill.assert_called_once_with(1234, 15)
            proc.return_value.wait.assert_called_once_with(timeout=5)

    def test_missing_process_is_already_stopped(self):
        with patch.object(chrome.psutil, "Process", side_effect=psutil.NoSuchProcess(1234)), \
                patch.object(chrome.os, "killpg") as kill:
            chrome.stop({"pid": 1234})
        kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
