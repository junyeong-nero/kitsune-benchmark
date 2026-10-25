import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import Mock, patch

from kitsune_benchmark.adapter import command, plan, run, settings, preflight, terminate_group
from kitsune_benchmark.audit import audit_events
from kitsune_benchmark.viewport import viewport_record
from kitsune_benchmark.runtime import API_ENV, codex_environment, find_codex
from kitsune_benchmark.specs import Server, Task, load_server, load_task, toml_value

SERVER = Server("test", "/test/mcp", ("--test",))
TASK = Task("test-task", "Read a test page; do not change anything.")
CALL = {"id": "call_1", "type": "mcp_tool_call", "server": "browser", "tool": "navigate", "status": "completed"}
EVENTS = [
    {"type": "thread.started", "thread_id": "test-thread"},
    {"type": "turn.started"},
    {"type": "item.started", "item": {**CALL, "status": "in_progress"}},
    {"type": "item.completed", "item": CALL},
    {"type": "turn.completed", "usage": {"input_tokens": 20, "cached_input_tokens": 5, "output_tokens": 4}},
]
HELP = "--json --output-last-message --skip-git-repo-check --ignore-user-config --ignore-rules --ephemeral"


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def fake_codex(self, events=None, mode="normal", version="0.163.0", login="Logged in using ChatGPT", help_text=HELP):
        path = self.root / "codex"
        event_lines = "\n".join(json.dumps(e) for e in (EVENTS if events is None else events))
        script = f'''#!{sys.executable}
import json,os,pathlib,sys,time,subprocess
args=sys.argv[1:]
if args==['--version']:
 print('codex-cli {version}'); sys.exit(0)
if args==['login','status']:
 print({login!r}); sys.exit(0)
if args==['exec','--help']:
 print({help_text!r}); sys.exit(0)
if not args or args[0]!='exec': sys.exit(22)
prompt=sys.stdin.read()
pathlib.Path({str(self.root / 'observed.json')!r}).write_text(json.dumps({{'argv':args,'env':dict(os.environ),'cwd':os.getcwd(),'prompt':prompt}}))
if {mode!r}=='sleep':
 child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
 pathlib.Path({str(self.root / 'child.pid')!r}).write_text(str(child.pid))
 time.sleep(60)
if {mode!r}=='malformed':
 print('not JSON')
else:
 print({event_lines!r})
if {mode!r}!='no_final':
 pathlib.Path(args[args.index('--output-last-message')+1]).write_text('Test answer, not a success label.')
sys.exit(1 if {mode!r}=='error' else 0)
'''
        path.write_text(script)
        path.chmod(0o700)
        return str(path)

    def execute(self, path, **kwargs):
        return run(SERVER, TASK, "test-model", executable=path,
                   output_root=str(self.root / "runs"), confirm_isolated_browser=True, **kwargs)

    def test_command_has_one_mcp_and_native_config(self):
        argv = command("/codex", SERVER, "fixed-model", Path("/private/final.txt"))
        self.assertEqual(argv[-1], "-")
        self.assertNotIn(TASK.prompt, argv)
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--json"):
            self.assertIn(flag, argv)
        config = {}
        for i, arg in enumerate(argv):
            if arg == "-c":
                key, value = argv[i + 1].split("=", 1)
                config[key] = tomllib.loads("value=" + value)["value"]
        self.assertEqual(set(config["mcp_servers"]), {"browser"})
        self.assertEqual(config["mcp_servers"]["browser"]["args"], ["--test"])
        self.assertEqual(config["mcp_servers"]["browser"]["default_tools_approval_mode"], "approve")
        self.assertTrue(config["suppress_unstable_features_warning"])
        self.assertEqual(config["forced_login_method"], "chatgpt")
        self.assertEqual(config["model_provider"], "openai")
        self.assertEqual(config["model_reasoning_effort"], "medium")
        self.assertFalse(config["features.shell_tool"])
        self.assertEqual(config["web_search"], "disabled")
        self.assertTrue(config["features.skip_host_skill_discovery"])
        self.assertEqual(config["project_doc_max_bytes"], 0)

    def test_toml_roundtrip(self):
        value = {"text": 'quotes " unicode 한글\n', "flag": True, "args": ["a", "b"], "timeout": 60}
        self.assertEqual(tomllib.loads("v=" + toml_value(value))["v"], value)
        with self.assertRaises(ValueError):
            toml_value(None)

    def test_plan_never_invokes_codex(self):
        executable = self.fake_codex()
        with patch("subprocess.Popen", side_effect=AssertionError("no processes in plan")):
            result = plan(SERVER, TASK, "fixed-model", executable)
        self.assertFalse(result["model_invoked"])
        self.assertFalse((self.root / "observed.json").exists())

    def test_environment_is_allowlisted(self):
        source = {"HOME": str(self.root), "PATH": "/bin", "OPENAI_API_KEY": "SECRET",
                  "OPENAI_BASE_URL": "https://wrong", "NODE_OPTIONS": "--require evil",
                  "CODEX_HOME": "/auth-home", "MCP_TOKEN": "PRIVATE", "OTHER": "PRIVATE2"}
        env = codex_environment("/nvm/bin/codex", extra_names=("MCP_TOKEN",), source=source)
        self.assertEqual(env["PATH"], "/nvm/bin:/bin")
        self.assertEqual(env["CODEX_HOME"], "/auth-home")
        self.assertEqual(env["MCP_TOKEN"], "PRIVATE")
        self.assertNotIn("NODE_OPTIONS", env)
        self.assertNotIn("OTHER", env)
        self.assertFalse(API_ENV & env.keys())
        for key in (*API_ENV, "CODEX_HOME", "CODEX_CONFIG", "OPENAI_BASE_URL", "NODE_OPTIONS", "HOME", "PYTHONPATH"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                codex_environment("/codex", extra_names=(key,), source={key: "secret"})
        with self.assertRaises(ValueError):
            codex_environment("/codex", extra_names=("MISSING",), source={})

    def test_successful_fake_run_is_unscored_and_private(self):
        path = self.fake_codex()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "NEVER_PASS_THIS"}):
            viewport = viewport_record("playwright", ("--viewport-size", "1280x720"))
            result = self.execute(path, viewport=viewport)
        self.assertEqual(result["execution_status"], "completed_unscored")
        self.assertIsNone(result["task_success"])
        self.assertEqual(result["evaluation"], "not_implemented")
        self.assertEqual(result["mcp_calls"], 1)
        self.assertEqual(result["completed_mcp_calls"], 1)
        self.assertEqual(result["usage"]["input_tokens"], 20)
        observed = json.loads((self.root / "observed.json").read_text())
        self.assertEqual(observed["prompt"], TASK.prompt)
        self.assertNotIn("OPENAI_API_KEY", observed["env"])
        self.assertTrue(Path(observed["cwd"]).name.startswith("kitsune-benchmark-"))
        self.assertFalse(Path(observed["cwd"]).exists())
        run_dir = Path(result["run_dir"])
        self.assertEqual(run_dir.stat().st_mode & 0o777, 0o700)
        for file in run_dir.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("NEVER_PASS_THIS", file.read_text())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        self.assertEqual(manifest["codex_version"], "0.163.0")
        self.assertEqual(manifest["environment_reset"], "not_implemented")
        self.assertEqual(manifest["viewport"], viewport)

    def test_requires_browser_confirmation_before_preflight(self):
        with self.assertRaises(ValueError):
            run(SERVER, TASK, "fixed-model", executable="/nonexistent")
        self.assertFalse((self.root / "runs").exists())

    def test_preflight_rejects_api_login_version_or_missing_flags(self):
        options = [{"login": "Logged in using an API key: SECRET"},
                   {"version": "0.100.0"}, {"help_text": "--json"}]
        for option in options:
            with self.subTest(option=option):
                path = self.fake_codex(**option)
                with self.assertRaises(ValueError):
                    self.execute(path)
                self.assertFalse((self.root / "observed.json").exists())

    def test_forbidden_tools_and_foreign_mcp_invalidate(self):
        for item in ({"type": "command_execution", "id": "bad"},
                     {"type": "web_search", "id": "bad"},
                     {"type": "file_change", "id": "bad"},
                     {**CALL, "id": "bad", "server": "other"}):
            with self.subTest(item=item):
                path = self.fake_codex(events=EVENTS + [{"type": "item.completed", "item": item}])
                result = self.execute(path)
                self.assertEqual(result["execution_status"], "invalid_trace")
                self.assertTrue(result["violations"])

    def test_malformed_missing_and_failed_runs(self):
        for mode, events, expected in (
            ("malformed", EVENTS, "invalid_trace"),
            ("no_final", EVENTS, "incomplete"),
            ("normal", [{"type": "turn.completed"}], "incomplete"),
            ("normal", [{"type": "turn.failed"}], "harness_error"),
            ("error", EVENTS, "harness_error"),
        ):
            with self.subTest(mode=mode, expected=expected):
                self.assertEqual(self.execute(self.fake_codex(events=events, mode=mode))["execution_status"], expected)

    def test_timeout_kills_process_group(self):
        result = self.execute(self.fake_codex(mode="sleep"), timeout=1)
        self.assertEqual(result["execution_status"], "timeout")
        pid = int((self.root / "child.pid").read_text())
        # A zombie on some platforms may remain until reaped by init; a live
        # child must not survive. ps is test-only and never exposed to Codex.
        status = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        self.assertTrue(not status or status.startswith("Z"), status)

    def test_audit_fails_closed_on_unknown_and_invalid_encoding(self):
        path = self.root / "events.jsonl"
        path.write_bytes(b'[]\n{"type":"future.event"}\n\xff\n{"type":"item.completed","item":{}}\n')
        result = audit_events(path)
        self.assertIn("malformed_event", result["violations"])
        self.assertIn("unrecognized_event", result["violations"])
        self.assertIn("malformed_jsonl", result["violations"])
        self.assertIn("forbidden_or_unknown_item", result["violations"])

    def test_launch_failure_is_recorded_without_exception_contents(self):
        path = self.fake_codex()
        with patch("kitsune_benchmark.adapter.preflight", return_value={}), patch(
            "kitsune_benchmark.adapter.subprocess.Popen", side_effect=OSError("SECRET")):
            result = self.execute(path)
        self.assertEqual(result["execution_status"], "harness_error")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_failed_mcp_calls_are_counted_without_judging_success(self):
        path = self.root / "events.jsonl"
        events = [
            {"type": "item.started", "item": {**CALL, "status": "in_progress"}},
            {"type": "item.completed", "item": {**CALL, "result": {"isError": True}}},
            {"type": "turn.completed", "usage": {"input_tokens": 3}},
            {"type": "turn.completed", "usage": {"input_tokens": 7}},
        ]
        path.write_text("\n".join(json.dumps(e) for e in events))
        result = audit_events(path)
        self.assertEqual(result["mcp_calls"], 1)
        self.assertEqual(result["failed_mcp_calls"], 1)
        self.assertEqual(result["usage"]["input_tokens"], 10)
        self.assertIsNone(result["task_success"])

    def test_nvm_discovery_and_ambiguity(self):
        bin_dir = self.root / ".nvm/versions/node/v1/bin"
        bin_dir.mkdir(parents=True)
        executable = bin_dir / "codex"
        executable.write_text("fake")
        executable.chmod(0o700)
        with patch("kitsune_benchmark.runtime.Path.home", return_value=self.root), patch(
                "kitsune_benchmark.runtime.shutil.which", return_value=None), patch(
                "kitsune_benchmark.runtime.os.access", side_effect=lambda p, mode: str(p).startswith(str(self.root))):
            self.assertEqual(find_codex(), str(executable))
            second = self.root / ".nvm/versions/node/v2/bin/codex"
            second.parent.mkdir(parents=True)
            second.write_text("fake")
            with self.assertRaises(ValueError):
                find_codex()
            self.assertIsNone(find_codex("/explicit/missing"))

    def test_dead_group_permission_error_is_not_a_cleanup_failure(self):
        process = Mock(pid=123456)
        with patch("kitsune_benchmark.adapter.os.killpg", side_effect=[None, PermissionError()]), patch(
                "kitsune_benchmark.adapter._has_live_group", return_value=False):
            terminate_group(process)
        self.assertTrue(process.wait.called)
        with patch("kitsune_benchmark.adapter.os.killpg", side_effect=PermissionError()), patch(
                "kitsune_benchmark.adapter._has_live_group", return_value=True):
            with self.assertRaises(PermissionError):
                terminate_group(process)

    def test_error_items_are_harness_errors_not_unknown_tools(self):
        path = self.root / "events.jsonl"
        path.write_text(json.dumps({"type": "item.completed", "item": {
            "id": "error", "type": "error", "message": "CLI diagnostic"}}))
        result = audit_events(path)
        self.assertTrue(result["harness_error"])
        self.assertEqual(result["violations"], [])

    def test_input_validation(self):
        server = self.root / "server.json"
        for value in ({"id": "x", "command": "mcp", "env": {"secret": "no"}},
                      {"id": "../bad", "command": "mcp"},
                      {"id": "x", "command": "mcp", "args": "wrong"},
                      {"id": "x", "command": "mcp", "tool_timeout_sec": False}):
            with self.subTest(value=value):
                server.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    load_server(server)
        server.write_text(json.dumps({"id": "x", "command": "mcp", "args": []}))
        self.assertEqual(load_server(server).id, "x")
        task = self.root / "task.json"
        task.write_text(json.dumps({"id": "task", "prompt": "hello"}))
        self.assertEqual(load_task(task), Task("task", "hello"))
        with self.assertRaises(ValueError):
            plan(SERVER, TASK, "SET_EXPLICIT_MODEL", self.fake_codex())
        with self.assertRaises(ValueError):
            plan(SERVER, TASK, "model", self.fake_codex(), timeout=0)


if __name__ == "__main__":
    unittest.main()
