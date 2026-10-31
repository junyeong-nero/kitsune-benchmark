from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import Mock, patch

from kitsune_benchmark.adapter import (await_harness, command, model_request_observed, plan, run, settings,
                                       preflight, terminate_group)
from kitsune_benchmark.audit import audit_events
from kitsune_benchmark.viewport import viewport_record
from kitsune_benchmark.runtime import API_ENV, codex_environment, find_codex
from kitsune_benchmark.smoke import ROOT, session_setup
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
# A native MCP server for the personal relay that writes its pid to argv[2]: its setup navigate is refused (as
# Kitsune's needs_user) with "fail".
FAKE_NATIVE = '''import json, os, pathlib, sys
fail = sys.argv[1] == "fail"
pathlib.Path(sys.argv[2]).write_text(str(os.getpid()))
urls = ["about:blank"]
active = 0
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    method, params = message["method"], message.get("params", {})
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "browser_snapshot", "inputSchema": {"type": "object"}}]}
    else:
        name, args = params["name"], params["arguments"]
        result = {"content": [{"type": "text", "text": "native result"}]}
        if name == "browser_navigate" and fail:
            result = {"isError": True, "content": [{"type": "text", "text": json.dumps({"code": "needs_user"})}]}
        elif name == "browser_navigate":
            urls[active] = args["url"]
        elif name == "browser_tabs" and args["action"] == "list":
            result = {"content": [{"type": "text", "text": "\\n".join(
                f"- {i}: " + ("(current) " if i == active else "") + f"[]({url})" for i, url in enumerate(urls))}]}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
'''


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

    def fake_mcp_client(self, relay_argv: list[str], impatient: bool = False) -> str:
        """A Codex stand-in that starts the relay as its MCP server and, like a client that awaits its tool list,
        makes its "model request" (model.json) only once tools/list is answered. An impatient client makes its
        request (and reports usage) first, as one that timed tools/list out would."""
        path = self.root / "codex"
        early = "print(" + repr("\n".join(json.dumps(e) for e in EVENTS)) + ", flush=True)" if impatient else ""
        path.write_text(f'''#!{sys.executable}
import json, pathlib, subprocess, sys
args = sys.argv[1:]
if args == ['--version']:
    print('codex-cli 0.163.0'); sys.exit(0)
if args == ['login', 'status']:
    print('Logged in using ChatGPT'); sys.exit(0)
if args == ['exec', '--help']:
    print({HELP!r}); sys.exit(0)
sys.stdin.read()
{early}
relay = subprocess.Popen({relay_argv!r}, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
pathlib.Path({str(self.root / "relay.pid")!r}).write_text(str(relay.pid))
def send(message):
    relay.stdin.write((json.dumps(message) + "\\n").encode())
    relay.stdin.flush()
send({{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {{"protocolVersion": "2024-11-05", "capabilities": {{}}}}}})
relay.stdout.readline()
send({{"jsonrpc": "2.0", "method": "notifications/initialized"}})
send({{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}})
listed = relay.stdout.readline().decode()
pathlib.Path({str(self.root / "model.json")!r}).write_text(listed)
print({"\n".join(json.dumps(e) for e in EVENTS)!r})
pathlib.Path(args[args.index('--output-last-message') + 1]).write_text('Test answer.')
''')
        path.chmod(0o700)
        return str(path)

    def test_failed_session_setup_stops_the_harness_before_its_model_request(self):
        for mode, expected in (("fail", "setup_failed"), ("ok", "completed_unscored")):
            with self.subTest(mode=mode):
                for name in ("evidence.json", "model.json", "relay.pid", "native.pid"):
                    (self.root / name).unlink(missing_ok=True)
                (self.root / "native.py").write_text(FAKE_NATIVE)
                config = self.root / "session.json"
                config.write_text(json.dumps({
                    "target": "playwright",
                    "upstream": [sys.executable, str(self.root / "native.py"), mode, str(self.root / "native.pid")],
                    "bootstrap_url": "http://local/t/start", "urls": ["http://local/t/article"], "active_index": 0,
                    "evidence_path": str(self.root / "evidence.json"), "origin": "http://local"}))
                path = self.fake_mcp_client([sys.executable, str(ROOT / "kitsune_benchmark/personal_session.py"), str(config)])
                result = self.execute(path, timeout=30, session_setup=lambda: session_setup(self.root / "evidence.json"))
                self.assertEqual(result["execution_status"], expected)
                for name in ("relay.pid", "native.pid"):  # the relay and its native server are both gone
                    pid = int((self.root / name).read_text())
                    status = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
                    self.assertTrue(not status or status.startswith("Z"), (name, status))
                evidence = json.loads((self.root / "evidence.json").read_text())
                if mode == "fail":
                    # Stopped while the relay held tools/list: no model request, no usage, well before the timeout.
                    self.assertFalse((self.root / "model.json").exists())
                    self.assertTrue(result["harness_error"])
                    self.assertEqual(result["usage"], {})
                    self.assertIs(result["model_request_observed"], False)
                    self.assertLess(result["elapsed_sec"], 20)
                    self.assertEqual(evidence["error"], "native_session_setup_or_inventory_failed")
                else:
                    listed = json.loads((self.root / "model.json").read_text())
                    self.assertEqual(listed["result"]["tools"][0]["name"], "browser_snapshot")
                    self.assertTrue(evidence["setup_complete"])
                    self.assertEqual(result["usage"]["input_tokens"], 20)
                    self.assertNotIn("model_request_observed", result)

    def test_failed_session_setup_records_a_model_request_the_client_already_made(self):
        # A client that gave up on tools/list (or never waited) may have made its request: recorded, with a warning.
        (self.root / "native.py").write_text(FAKE_NATIVE)
        config = self.root / "session.json"
        config.write_text(json.dumps({
            "target": "playwright", "upstream": [sys.executable, str(self.root / "native.py"), "fail", str(self.root / "native.pid")],
            "bootstrap_url": "http://local/t/start", "urls": ["http://local/t/article"], "active_index": 0,
            "evidence_path": str(self.root / "evidence.json"), "origin": "http://local"}))
        path = self.fake_mcp_client([sys.executable, str(ROOT / "kitsune_benchmark/personal_session.py"), str(config)],
                                    impatient=True)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = self.execute(path, timeout=30, session_setup=lambda: session_setup(self.root / "evidence.json"))
        self.assertEqual(result["execution_status"], "setup_failed")
        self.assertIs(result["model_request_observed"], True)
        self.assertEqual(result["usage"]["input_tokens"], 20)
        self.assertIn("already made a model request", stderr.getvalue())

    def test_model_request_observed_reads_both_harness_audits(self):
        self.assertFalse(model_request_observed({"usage": {}, "mcp_calls": 0, "num_turns": None,
                                                 "token_attribution": {"requests": 0}}))
        self.assertFalse(model_request_observed({"usage": {}, "mcp_calls": 0}))  # Codex audit
        for audit in ({"usage": {"input_tokens": 3}}, {"token_attribution": {"requests": 1}}, {"num_turns": 1},
                      {"mcp_calls": 1}):
            with self.subTest(audit=audit):
                self.assertTrue(model_request_observed(audit))

    def test_await_harness_polls_the_session_setup_only_until_it_settles(self):
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired("harness", 0.1), subprocess.TimeoutExpired("harness", 0.1), 0]
        outcomes = iter([None, None, True])
        self.assertFalse(await_harness(process, b"prompt", 30, lambda: next(outcomes)))
        first, second, third = [c.kwargs["timeout"] for c in process.wait.call_args_list]
        self.assertEqual((first, second), (0.1, 0.1))
        self.assertGreater(third, 29)
        process.stdin.write.assert_called_once_with(b"prompt")  # written and closed once, whatever the polls
        process.stdin.close.assert_called_once_with()
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("harness", 0.1)
        outcomes = iter([None, False])
        self.assertTrue(await_harness(process, b"prompt", 30, lambda: next(outcomes)))
        self.assertEqual(process.wait.call_count, 1)
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("harness", 1)
        with self.assertRaises(subprocess.TimeoutExpired):
            await_harness(process, b"prompt", 1)
        process = Mock()
        self.assertFalse(await_harness(process, b"prompt", 30))
        self.assertGreater(process.wait.call_args.kwargs["timeout"], 29)

    def test_await_harness_delivers_the_whole_prompt_to_a_late_reader_while_polling(self):
        # The prompt exceeds the pipe buffer and is read only after several polls; the reader must still reach EOF.
        out = self.root / "prompt-length.txt"
        process = subprocess.Popen([sys.executable, "-c", "import pathlib, sys, time; time.sleep(0.5); "
                                    f"pathlib.Path({str(out)!r}).write_text(str(len(sys.stdin.buffer.read())))"],
                                   stdin=subprocess.PIPE)
        polls = iter([None] * 10 + [True] * 1000)
        try:
            self.assertFalse(await_harness(process, b"x" * 2_000_000, 20, lambda: next(polls)))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        self.assertEqual(out.read_text(), "2000000")

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
