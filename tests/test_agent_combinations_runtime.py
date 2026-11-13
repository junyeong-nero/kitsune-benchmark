"""No browser/model tests for the separate pilot's explicit runtime probes."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from kitsune_benchmark import agent_combinations_runtime as runtime

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("combinations_preflight", ROOT / "scripts/preflight-agent-combinations.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class RuntimeTests(unittest.TestCase):
    def test_private_environment_excludes_keys_and_browser_attachment_defaults(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                "HOME": "/everyday", "OPENAI_API_KEY": "secret", "ANTHROPIC_API_KEY": "secret",
                "BU_CDP_WS": "ws://localhost:9222", "AGENT_BROWSER_AUTO_CONNECT": "1",
                "KITSUNE_HOME": "/everyday-kitsune", "NODE_OPTIONS": "--import=hook"}):
            env = runtime.private_environment(Path(directory))
            self.assertEqual(env["HOME"], directory + "/home")
            self.assertEqual(env["TMPDIR"], directory + "/tmp")
            for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "BU_CDP_WS", "AGENT_BROWSER_AUTO_CONNECT",
                        "KITSUNE_HOME", "NODE_OPTIONS"):
                self.assertNotIn(key, env)
            self.assertEqual(Path(env["HOME"]).stat().st_mode & 0o777, 0o700)

    def test_zen_rejects_drift_before_launch(self):
        with patch.object(runtime, "source_revision", return_value={"revision": "wrong", "dirty": False}), \
                patch.object(runtime.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(ValueError, "pinned"):
                with runtime.zen_runtime(Path("/unused"), ROOT, bidi_port=51001):
                    self.fail("must not yield")
            spawn.assert_not_called()

    def test_zen_failure_cleans_owned_group_and_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "run"
            process = Mock(pid=1234)
            process.poll.return_value = -15
            with patch.object(runtime, "source_revision", return_value={"revision": runtime.KITSUNE_SHA, "dirty": False}), \
                    patch.object(runtime, "copy_extension", return_value={}), \
                    patch.object(runtime, "ZEN", Path(__file__)), \
                    patch.object(runtime, "private_ports", return_value=(51001, 51002)), \
                    patch.object(runtime.subprocess, "Popen", return_value=process) as spawn, \
                    patch.object(runtime, "await_bridge", side_effect=ValueError("bridge failed")), \
                    patch.object(runtime, "terminate_group") as stop:
                with self.assertRaisesRegex(ValueError, "bridge failed"):
                    with runtime.zen_runtime(folder, ROOT, bidi_port=51003):
                        self.fail("must not yield")
            stop.assert_called_once_with(process)
            self.assertTrue(spawn.call_args.kwargs["start_new_session"])
            self.assertTrue(json.loads((folder / "cleanup.json").read_text())["owned_launchers_stopped"])

    def test_zen_uses_explicit_binary_profile_and_private_bidi(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "run"
            process = Mock(pid=1234)
            process.poll.return_value = 0
            with patch.object(runtime, "source_revision", return_value={"revision": runtime.KITSUNE_SHA, "dirty": False}), \
                    patch.object(runtime, "copy_extension", return_value={}), \
                    patch.object(runtime, "ZEN", Path(__file__)), \
                    patch.object(runtime, "private_ports", return_value=(51001, 51002)), \
                    patch.object(runtime.subprocess, "Popen", return_value=process) as spawn, \
                    patch.object(runtime, "await_bridge"), patch.object(runtime, "terminate_group"):
                with runtime.zen_runtime(folder, ROOT, bidi_port=51003):
                    argv = spawn.call_args.args[0]
                    self.assertEqual(argv[argv.index("--firefox") + 1], __file__)
                    self.assertEqual(argv[argv.index("--firefox-profile") + 1], str(folder.resolve() / "profile"))
                    self.assertIn("--args=--remote-debugging-port=51003", argv)
                    self.assertIn("--args=--remote-allow-system-access", argv)


class ProbeTests(unittest.TestCase):
    def test_catalog_pagination_is_complete_and_duplicate_names_fail(self):
        session = Mock()
        session.request.side_effect = [{"result": {}}, {"result": {"tools": [{"name": "a"}], "nextCursor": "2"}},
                                       {"result": {"tools": [{"name": "b"}]}}]
        self.assertEqual(probe.initialize(session), [{"name": "a"}, {"name": "b"}])
        session.request.side_effect = [{"result": {}}, {"result": {"tools": [{"name": "a"}, {"name": "a"}]}}]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            probe.initialize(session)

    def test_path_only_is_not_a_delivered_image(self):
        self.assertEqual(probe.image_evidence({"content": [{"type": "text", "text": '{"path":"/tmp/a.png"}'}]}), [])
        stream = io.BytesIO()
        Image.new("RGB", (16, 12)).save(stream, format="PNG")
        result = {"content": [{"type": "image", "mimeType": "image/png", "data": base64.b64encode(stream.getvalue()).decode()}]}
        self.assertEqual([(i["width"], i["height"]) for i in probe.image_evidence(result)], [(16, 12)])


class RelayCleanupTests(unittest.TestCase):
    def test_completed_relay_needs_no_signalling(self):
        from kitsune_benchmark import agent_combinations_fixture as fixture
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            path = out / "evidence.json"
            path.write_text('{"session_closed":true}')
            with patch.object(fixture.os, "killpg") as signal:
                fixture.await_relay_close({"evidence_path": str(path)}, out)
            signal.assert_not_called()

    def test_changed_process_identity_is_never_signalled(self):
        from kitsune_benchmark import agent_combinations_fixture as fixture
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "relay-process.json").write_text(json.dumps({"pid": 42, "created": 10, "config": "/private/config"}))
            with patch.object(fixture.time, "monotonic", side_effect=[0, 16]), \
                    patch.object(fixture.psutil, "Process") as process, patch.object(fixture.os, "killpg") as signal:
                process.return_value.create_time.return_value = 11
                with self.assertRaisesRegex(ValueError, "identity changed"):
                    fixture.await_relay_close({"evidence_path": str(out / "missing")}, out)
            signal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
