import copy
from http.cookiejar import CookieJar
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.personal import (PROTECTED_NOTE, PersonalServer, aggregate_results, catalog, config,
                                       run_personal, selected_tasks)
from kitsune_benchmark.personal_session import NativeSession, tabs_from_result
from kitsune_benchmark.smoke import ROOT, await_bridge, copy_extension, private_ports
from kitsune_benchmark.adapter import resolve, terminate_group
from kitsune_benchmark.runtime import codex_environment
from kitsune_benchmark.specs import Server


def evidence_for(trial):
    tabs = [{"id": i, "url": trial.url(path), "active": i == trial.active_index}
            for i, path in enumerate(trial.paths)]
    return {"setup_complete": True, "initial_tabs": tabs, "snapshots": [copy.deepcopy(tabs)]}


def opener():
    return build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))


class PersonalTests(unittest.TestCase):
    def test_catalog_covers_24_runnable_specs_and_six_task_pilot(self):
        data = catalog()
        self.assertEqual(len(data["tasks"]), 24)
        self.assertEqual(len(selected_tasks()), 6)
        self.assertTrue(all(t["status"] == "runnable" for t in data["tasks"]))
        self.assertEqual(config()["model"], "gpt-6-luna")
        self.assertTrue(all(t["relationship"].startswith("original") for t in data["tasks"]))
        self.assertIn("OPEN RAIL", data["sources"]["assistantbench"]["repository_license_observed"])

    def test_plan_and_cli_never_start_processes(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no browser or inference")):
            plan = run_personal()
            self.assertFalse(plan["model_invoked"])
            self.assertEqual(plan["planned_model_runs"], 12)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["personal", "--task", "pb-tabs-01", "--variant", "2"]), 0)
                self.assertEqual(main(["personal", "--task", "pb-tabs-99"]), 2)
                self.assertEqual(main(["personal", "--all", "--task", "pb-tabs-01"]), 2)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["personal", "--all"]), 0)
            self.assertEqual(json.loads(out.getvalue())["planned_model_runs"], 48)
        for ids in (["missing"], ["pb-current-01", "pb-current-01"], []):
            with self.assertRaises(ValueError):
                selected_tasks(ids)
        for variant in (-1, 3, True):
            with self.assertRaises(ValueError):
                run_personal(variant=variant)

    def test_three_variants_have_different_answers_for_every_fixture(self):
        for task in selected_tasks():
            answers = []
            for variant in range(3):
                with PersonalServer(task, variant) as server:
                    server.begin("playwright")
                    trial = server.trials[server.by_target["playwright"]]
                    answers.append(json.dumps(trial.expected, sort_keys=True))
            self.assertEqual(len(set(answers)), 3)

    def test_test_cookie_is_required_and_targets_are_reset(self):
        with PersonalServer(selected_tasks(["pb-account-01"])[0], 0) as server:
            server.begin("playwright")
            server.begin("kitsune")
            a, b = [server.trials[server.by_target[t]] for t in ("playwright", "kitsune")]
            self.assertNotEqual(a.token, b.token)
            self.assertEqual(a.expected, b.expected)
            client = opener()
            with self.assertRaises(HTTPError) as error:
                client.open(a.url("/orders"))
            self.assertEqual(error.exception.code, 404)
            with client.open(a.url("/start")) as response:
                self.assertIn("HttpOnly", response.headers["Set-Cookie"])
            with client.open(a.url("/orders")) as response:
                self.assertEqual(response.status, 200)
            with self.assertRaises(HTTPError):
                client.open(b.url("/orders"))
            a.note = "changed"
            self.assertEqual(b.note, "")
            self.assertEqual(b.protected, PROTECTED_NOTE)

    def test_real_http_form_grading_all_six_and_all_variants(self):
        for task in selected_tasks():
            for variant in range(3):
                with self.subTest(task=task["id"], variant=variant), PersonalServer(task, variant) as server:
                    server.begin("playwright")
                    trial = server.trials[server.by_target["playwright"]]
                    client = opener()
                    client.open(trial.url("/start")).close()
                    for path in trial.paths:
                        with client.open(trial.url(path)) as response:
                            self.assertIn(b"Content-Security-Policy", str(response.headers).encode())
                    source = {"policy": "/policy/current", "orders": "/order/2"}.get(task["fixture"])
                    if source:
                        client.open(trial.url(source)).close()
                    draft = task["fixture"] in {"calendar", "contact"}
                    values = trial.expected if draft else {"메모": trial.expected["answer"]}
                    request = Request(trial.url("/draft" if draft else "/note"),
                                      data=urlencode(values).encode())
                    with client.open(request) as response:
                        self.assertEqual(response.status, 200)
                    result = trial.evaluate({"execution_status": "completed_unscored"}, evidence_for(trial))
                    self.assertTrue(result["scorable"])
                    self.assertTrue(result["task_success"])
                    self.assertTrue(result["safety_pass"])

    def test_no_self_report_grading_and_fail_closed_evidence(self):
        with PersonalServer(selected_tasks(["pb-current-01"])[0], 0) as server:
            server.begin("playwright")
            trial = server.trials[server.by_target["playwright"]]
            result = {"execution_status": "completed_unscored", "final": "I completed the task"}
            self.assertFalse(trial.evaluate(result, evidence_for(trial))["task_success"])
            trial.note = trial.expected["answer"]
            for evidence in ({}, {"setup_complete": True}, {**evidence_for(trial), "error": "inventory_error"}):
                evaluation = trial.evaluate(result, evidence)
                self.assertFalse(evaluation["scorable"])
                self.assertIsNone(evaluation["task_success"])
            evaluation = trial.evaluate({"execution_status": "timeout"}, evidence_for(trial))
            self.assertIsNone(evaluation["task_success"])
            bad_active = evidence_for(trial)
            bad_active["initial_tabs"][0]["active"] = False
            self.assertFalse(trial.evaluate(result, bad_active)["scorable"])

    def test_correct_answer_still_fails_on_safety_or_missing_source(self):
        for task in selected_tasks():
            with PersonalServer(task, 0) as server:
                server.begin("playwright")
                trial = server.trials[server.by_target["playwright"]]
                if "answer" in trial.expected:
                    trial.note = trial.expected["answer"]
                else:
                    trial.draft = trial.expected
                valid = {"execution_status": "completed_unscored"}
                if task["fixture"] in {"orders", "policy"}:
                    self.assertFalse(trial.evaluate(valid, evidence_for(trial))["task_success"])
                    trial.visits.extend(["/order/2", "/policy/current"])
                self.assertTrue(trial.evaluate(valid, evidence_for(trial))["task_success"])
                for change in ("tab_missing", "close", "external", "protected", "forbidden"):
                    with self.subTest(task=task["id"], change=change):
                        evidence = evidence_for(trial)
                        if change == "tab_missing":
                            evidence["snapshots"].append(evidence["initial_tabs"][:-1])
                        elif change == "close":
                            evidence["close_attempts"] = 1
                        elif change == "external":
                            evidence["outside_navigation"] = 1
                        elif change == "protected":
                            trial.protected = "changed"
                        else:
                            trial.forbidden.append("submit")
                        self.assertFalse(trial.evaluate(valid, evidence)["task_success"])
                        trial.protected = PROTECTED_NOTE
                        trial.forbidden.clear()

    def test_forbidden_and_malformed_http_writes(self):
        with PersonalServer(selected_tasks(["pb-safe-01"])[0], 0) as server:
            server.begin("playwright")
            trial = server.trials[server.by_target["playwright"]]
            client = opener()
            client.open(trial.url("/start")).close()
            for path, body, headers, status in [
                ("/submit", b"x=1", {}, 403),
                ("/draft", b"x=1", {}, 400),
                ("/draft", b"x=1", {"Origin": "https://example.com"}, 403),
                ("/draft", b"x=1&x=2", {}, 400),
                ("/draft", b"{}", {"Content-Type": "application/json"}, 400),
            ]:
                with self.assertRaises(HTTPError) as error:
                    client.open(Request(trial.url(path), data=body, headers=headers))
                self.assertEqual(error.exception.code, status)
            self.assertEqual(trial.forbidden, ["/submit"])
            self.assertEqual(trial.draft, {})

    def test_prepare_server_preserves_tool_allowlist_and_private_config(self):
        task = selected_tasks()[0]
        with tempfile.TemporaryDirectory() as folder, PersonalServer(task, 0) as server:
            prompt = server.begin("playwright")
            upstream = Server("playwright", "node", ("cli.js",), (), 60, 45, ("browser_tabs",))
            wrapped = server.prepare_server("playwright", upstream, prompt, Path(folder))
            self.assertEqual(wrapped.enabled_tools, upstream.enabled_tools)
            stored = json.loads(Path(wrapped.args[-1]).read_text())
            self.assertEqual(stored["upstream"], ["node", "cli.js"])
            self.assertEqual(Path(wrapped.args[-1]).stat().st_mode & 0o777, 0o600)
            self.assertFalse(server.evaluate("playwright", {"execution_status": "completed_unscored"})["scorable"])

    def test_suite_stops_after_unscorable_pair_without_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            pair = {"pair_dir": folder, "results": {"playwright": {"benchmark_evaluation": {"scorable": False}}}}
            with patch("kitsune_benchmark.personal.run_pair", return_value=pair) as run:
                result = run_personal(execute=True)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(result["requested_pairs"], 6)
            self.assertEqual(result["attempted_pairs"], 1)
            self.assertEqual(result["completed_pairs"], 0)

    def test_aggregation_keeps_failure_cost_and_missing_usage_separate(self):
        successful = {"benchmark_evaluation": {"scorable": True, "task_success": True, "safety_pass": True},
                      "usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 5},
                      "mcp_calls": 4, "elapsed_sec": 10}
        failed = {"benchmark_evaluation": {"scorable": True, "task_success": False, "safety_pass": False},
                  "usage": {"input_tokens": 50, "output_tokens": 2}, "mcp_calls": 1, "elapsed_sec": 1}
        missing = {"benchmark_evaluation": {"scorable": False}, "usage": {}}
        result = aggregate_results([{"results": {"playwright": r}} for r in [successful, failed, missing]])
        p = result["playwright"]
        self.assertEqual((p["attempted"], p["scorable"], p["unscorable"], p["successes"]), (3, 2, 1, 1))
        self.assertEqual(p["scorable_success_rate"], .5)
        self.assertEqual(p["safety_failures"], 1)
        self.assertEqual(p["reported_usage_all_runs"]["input_tokens"], 150)
        self.assertEqual(p["reported_usage_successful_runs"]["input_tokens"], 100)
        self.assertEqual(p["runs_with_usage"], 2)
        self.assertEqual(p["instrumented_elapsed_sec_successful_runs"], 10)
        self.assertIsNone(result["kitsune"]["scorable_success_rate"])

    def test_aggregation_counts_unpublished_allowlisted_tools(self):
        lean = {"benchmark_evaluation": {"scorable": True, "task_success": False},
                "tool_surface": {"missing": ["browser_keypress", "browser_drag"]}}
        full = {"benchmark_evaluation": {"scorable": True, "task_success": True}, "tool_surface": {"missing": []}}
        k = aggregate_results([{"results": {"kitsune": r}} for r in [lean, full, {}]])["kitsune"]
        self.assertEqual((k["runs_with_tool_surface"], k["runs_missing_allowlisted_tools"]), (2, 1))
        self.assertEqual(k["missing_allowlisted_tools"], ["browser_drag", "browser_keypress"])


class SessionTests(unittest.TestCase):
    def test_relay_entrypoint_transports_real_jsonrpc_without_browser_or_model(self):
        fake = '''import json, sys
urls = ["about:blank"]
active = 0
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    method, params = message["method"], message.get("params", {})
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake-native", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "browser_snapshot", "inputSchema": {"type": "object"}}]}
    else:
        name, args = params["name"], params["arguments"]
        result = {"content": [{"type": "text", "text": "native result"}]}
        if name == "browser_navigate":
            urls[active] = args["url"]
        if name == "browser_tabs":
            if args["action"] == "new":
                urls.append(args["url"])
                active = len(urls) - 1
            elif args["action"] == "select":
                active = args["index"]
            else:
                result = {"content": [{"type": "text", "text": "\\n".join(f"- {i}: " + ("(current) " if i == active else "") + f"[]({url})" for i, url in enumerate(urls))}]}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "native.py").write_text(fake)
            settings = {"target": "playwright", "upstream": [sys.executable, str(root / "native.py")],
                "bootstrap_url": "http://local/t/start", "urls": ["http://local/t/article", "http://local/t/protected"],
                "active_index": 0, "evidence_path": str(root / "evidence.json"), "origin": "http://local",
                "enabled_tools": ["browser_snapshot"], "diagnostics_path": str(root / "rpc.jsonl"),
                "metadata_path": str(root / "metadata.json")}
            (root / "config.json").write_text(json.dumps(settings))
            transport = NativeSession({"upstream": [sys.executable, str(ROOT / "kitsune_benchmark/personal_session.py"), str(root / "config.json")]})
            try:
                transport.start()
                response = transport.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
                self.assertEqual(response["result"]["serverInfo"]["name"], "fake-native")
                transport.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                response = transport.request("tools/list")
                self.assertEqual(response["result"]["tools"][0]["name"], "browser_snapshot")
                response = transport.request("tools/call", {"name": "browser_snapshot", "arguments": {}})
                self.assertEqual(response["result"]["content"][0]["text"], "native result")
                evidence = json.loads((root / "evidence.json").read_text())
                self.assertTrue(evidence["setup_complete"])
                self.assertEqual(len(evidence["snapshots"]), 2)
                self.assertGreater(evidence["harness_calls"], 5)
                records = [json.loads(line) for line in (root / "rpc.jsonl").read_text().splitlines()]
                rpc = [entry for entry in records if entry["kind"] == "rpc_completed"]
                self.assertTrue(any(entry["role"] == "harness" for entry in rpc))
                self.assertTrue(any(entry["role"] == "agent" and entry["tool"] == "browser_snapshot" for entry in rpc))
                self.assertTrue(all(entry["duration_sec"] >= 0 and entry["serialized_response_bytes"] > 0 for entry in rpc))
                self.assertTrue(any(entry["kind"] == "setup_completed" for entry in records))
                metadata = json.loads((root / "metadata.json").read_text())
                self.assertEqual(metadata["enabled_tools"], ["browser_snapshot"])
                self.assertEqual(metadata["initialize"]["serverInfo"]["name"], "fake-native")
                self.assertEqual(metadata["tools_pages"][0]["tools"][0]["name"], "browser_snapshot")
                for filename in ("rpc.jsonl", "metadata.json"):
                    self.assertEqual((root / filename).stat().st_mode & 0o777, 0o600)
            finally:
                transport.close()

    def test_native_tool_failure_preserves_only_sanitized_fields(self):
        failure = {"stage": "tab_creation", "tool": "browser_tabs", "code": "TAB_CREATE_FAILED",
                   "duration_ms": 125, "message": "https://user:password@private.invalid/?token=secret",
                   "credentials": "sk-private-secret"}
        responses = [
            {"error": {"code": -32000, "message": failure["message"], "data": failure}},
            {"result": {"isError": True, "structuredContent": {"error": failure}}},
            {"result": {"isError": True, "content": [{"type": "text", "text": json.dumps(failure)}]}},
        ]
        for response in responses:
            with self.subTest(response=response):
                session = NativeSession({})
                with patch.object(session, "request", return_value=response), self.assertRaises(ValueError) as caught:
                    session.tool("browser_tabs", {"action": "new", "url": failure["message"]})
                message = str(caught.exception)
                fields = session.evidence["native_error"]
                self.assertEqual(fields, json.loads(message.split(": ", 1)[1]))
                self.assertEqual(set(fields), {"stage", "tool", "code", "duration_ms", "duration_sec"})
                self.assertEqual({key: fields[key] for key in ("stage", "tool", "code", "duration_ms")},
                    {key: failure[key] for key in ("stage", "tool", "code", "duration_ms")})
                self.assertGreaterEqual(fields["duration_sec"], 0)
                self.assertNotIn("private", message)
                self.assertNotIn("password", message)
                self.assertNotIn("credentials", message)
                self.assertNotIn("https://", message)
                self.assertEqual(session.evidence["harness_calls"], 1)
                self.assertGreaterEqual(session.evidence["harness_seconds"], 0)

    def test_native_tool_failure_omits_sensitive_and_malformed_fields(self):
        responses = [
            {"error": {"code": -32001, "data": {"stage": "https://private.invalid", "tool": "sk-secret",
                "duration_ms": "https://private.invalid", "duration": float("inf")}}},
            {"result": {"isError": True, "structuredContent": {"stage": ["secret"], "code": {"token": "secret"}},
                "content": [{"type": "text", "text": "Bearer secret https://private.invalid"}]}},
            {"result": {"isError": True, "structuredContent": {"stage": "private.example.com",
                "tool": "ghp_" + "a" * 36, "code": "x" * 65, "duration_ms": True,
                "duration": float("nan")}}},
        ]
        for response in responses:
            session = NativeSession({})
            with patch.object(session, "request", return_value=response), self.assertRaises(ValueError) as caught:
                session.tool("browser_tabs", {})
            message = str(caught.exception)
            fields = session.evidence["native_error"]
            self.assertEqual(fields, json.loads(message.split(": ", 1)[1]))
            self.assertEqual(fields["stage"], "tools/call")
            self.assertEqual(fields["tool"], "browser_tabs")
            if "error" in response:
                self.assertEqual(fields["code"], -32001)
            self.assertNotIn("duration_ms", fields)
            self.assertNotIn("duration", fields)
            for sensitive in ("private", "secret", "Bearer", "token", "https://", "ghp_", "x" * 65):
                self.assertNotIn(sensitive, message)

    def test_relay_entrypoint_saves_sanitized_setup_failure_to_native_evidence(self):
        failure = {"stage": "tab_creation", "tool": "browser_navigate", "code": "NAV_FAILED",
                   "duration_ms": 125, "message": "https://user:password@private.invalid/?token=secret",
                   "credentials": "sk-private-secret"}
        fake = '''import json, sys
failure = json.loads(sys.argv[1])
for line in sys.stdin:
    message = json.loads(line)
    if message["params"]["name"] == "browser_tabs":
        result = {"content": [{"type": "text", "text": "- 0: (current) [](about:blank)"}]}
    else:
        result = {"isError": True, "structuredContent": {"error": failure}}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "native.py").write_text(fake)
            settings = {"target": "playwright", "upstream": [sys.executable, str(root / "native.py"),
                json.dumps(failure)], "bootstrap_url": failure["message"],
                "evidence_path": str(root / "evidence.json")}
            (root / "config.json").write_text(json.dumps(settings))
            result = subprocess.run([sys.executable, str(ROOT / "kitsune_benchmark/personal_session.py"),
                str(root / "config.json")], input=json.dumps({"id": 1, "method": "tools/list"}) + "\n",
                text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            evidence = json.loads((root / "evidence.json").read_text())
            self.assertFalse(evidence["setup_complete"])
            self.assertEqual(evidence["error"], "native_session_setup_or_inventory_failed")
            fields = evidence["native_error"]
            self.assertEqual(set(fields), {"stage", "tool", "code", "duration_ms", "duration_sec"})
            for key in ("stage", "tool", "code", "duration_ms"):
                self.assertEqual(fields[key], failure[key])
            self.assertGreaterEqual(fields["duration_sec"], 0)
            self.assertEqual((root / "evidence.json").stat().st_mode & 0o777, 0o600)
            for sensitive in ("private", "password", "credentials", "https://", "sk-"):
                self.assertNotIn(sensitive, json.dumps(evidence))

    def test_native_inventory_parsers(self):
        playwright = {"content": [{"type": "text", "text": "### Result\n- 0: [A](http://localhost/a)\n- 1: (current) [B](http://localhost/b)"}]}
        self.assertEqual(tabs_from_result("playwright", playwright)[1]["id"], 1)
        tabs = {"tabs": [{"id": 33, "url": "http://localhost/a", "title": "A", "active": True}]}
        for response in ({"structuredContent": tabs}, {"content": [{"type": "text", "text": json.dumps(tabs)}]}):
            self.assertEqual(tabs_from_result("kitsune", response)[0]["id"], 33)
        for target in ("kitsune", "playwright"):
            for response in ({}, {"isError": True}, {"content": [{"type": "text", "text": "unknown format"}]}):
                with self.assertRaises(ValueError):
                    tabs_from_result(target, response)

    def test_relay_preserves_native_schema_result_and_tracks_hidden_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {"target": "playwright", "upstream": [], "bootstrap_url": "http://local/t/start",
                        "urls": ["http://local/t/article"], "active_index": 0,
                        "evidence_path": folder + "/evidence.json", "origin": "http://local"}
            session = NativeSession(settings)
            responses = []
            state = {"url": "about:blank"}
            def fake_request(method, params=None, **kwargs):
                if method == "tools/list":
                    return {"result": {"tools": [{"name": "native_schema_unchanged", "inputSchema": {"type": "object"}}]}}
                name, args = params["name"], params["arguments"]
                if name == "browser_navigate":
                    state["url"] = args["url"]
                if name == "browser_tabs" and args["action"] == "list":
                    return {"result": {"content": [{"type": "text", "text": f'- 0: (current) []({state["url"]})'}]}}
                return {"result": {"content": [{"type": "text", "text": "native result unchanged"}]}}
            # The f-string above is a normal native tab list, not a custom tool schema.
            session.request = fake_request
            session.forward({"id": 91, "method": "tools/list"}, responses.append)
            self.assertEqual(responses[-1]["id"], 91)
            self.assertEqual(responses[-1]["result"]["tools"][0]["name"], "native_schema_unchanged")
            count = session.evidence["harness_calls"]
            session.forward({"id": 92, "method": "tools/call", "params": {"name": "browser_snapshot", "arguments": {}}}, responses.append)
            self.assertEqual(responses[-1]["result"]["content"][0]["text"], "native result unchanged")
            self.assertEqual(session.evidence["harness_calls"], count + 1)
            self.assertEqual(len(session.evidence["snapshots"]), 2)
            session.forward({"id": 93, "method": "tools/call", "params": {"name": "browser_navigate", "arguments": {"url": "https://external.invalid"}}}, responses.append)
            self.assertTrue(responses[-1]["result"]["isError"])
            self.assertEqual(session.evidence["outside_navigation"], 1)
            self.assertEqual(state["url"], settings["urls"][0])
            self.assertEqual(Path(settings["evidence_path"]).stat().st_mode & 0o777, 0o600)


@contextmanager
def isolated_kitsune(folder):
    """Match the paired runner's isolated Firefox/extension setup, without Codex."""
    import secrets
    import subprocess
    project = Path(os.environ.get("KITSUNE_PROJECT", ROOT.parent / "kitsune"))
    env = codex_environment(resolve("codex"))  # resolve only; no Codex process/login/model call
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / "artifacts/browsers")
    binary = subprocess.run(["node", "-e", "console.log(require('playwright').firefox.executablePath())"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=True).stdout.strip()
    http_port, ws_port = private_ports()
    destination = Path(folder) / "extension"
    copy_extension(project / "extension", destination, ws_port)
    env.update(KITSUNE_HOME=str(Path(folder) / "home"), KITSUNE_HTTP_PORT=str(http_port),
               KITSUNE_WS_PORT=str(ws_port), KITSUNE_TOKEN=secrets.token_urlsafe(32))
    with ExitStack() as stack:
        def spawn(args, filename):
            log = stack.enter_context((Path(folder) / filename).open("wb"))
            process = subprocess.Popen(args, env=env, cwd=folder, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, start_new_session=True)
            stack.callback(terminate_group, process)
            return process
        bridge = spawn(["uv", "run", "--locked", "--project", str(project), "python", "-m", "kitsune.bridge"], "bridge.log")
        await_bridge(http_port, env["KITSUNE_TOKEN"], bridge)
        browser = spawn([str(ROOT / "node_modules/.bin/web-ext"), "run", "--no-config-discovery", "--no-input",
            "--source-dir", str(destination), "--artifacts-dir", str(Path(folder) / "web-ext"),
            "--firefox", binary, "--no-reload", "--start-url", "about:blank", "--args=-headless",
            "--args=--width=1280", "--args=--height=720"], "firefox.log")
        await_bridge(http_port, env["KITSUNE_TOKEN"], browser, extension=True)
        with patch.dict(os.environ, env):
            yield ["uv", "run", "--locked", "--project", str(project), "kitsune"]


@unittest.skipUnless(os.environ.get("PERSONAL_KITSUNE_TEST") == "1", "opt-in isolated Kitsune/Firefox MCP test; no model calls")
class NativeKitsuneTests(unittest.TestCase):
    def test_six_fixtures_seed_and_solve_via_real_kitsune_ui(self):
        for task in selected_tasks():
            with self.subTest(task=task["id"]), tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as folder, PersonalServer(task, 0) as server:
                server.begin("kitsune")
                trial = server.trials[server.by_target["kitsune"]]
                with isolated_kitsune(folder) as upstream:
                    settings = {"target": "kitsune", "upstream": upstream,
                        "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
                        "active_index": trial.active_index, "evidence_path": folder + "/evidence.json", "origin": server.origin}
                    session = NativeSession(settings)
                    try:
                        session.start()
                        session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "personal-fixture-test", "version": "1"}})
                        session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                        session.prepare()
                        source = {"policy": "/policy/current", "orders": "/order/2"}.get(task["fixture"])
                        if source:
                            session.tool("browser_tabs", {"action": "new", "url": trial.url(source)})
                        draft = task["fixture"] in {"calendar", "contact"}
                        path = {"article": "/article", "products": "/compare", "policy": "/search", "orders": "/orders",
                                "calendar": "/calendar", "contact": "/contact"}[task["fixture"]]
                        tab = next(t for t in session.inventory() if t["url"] == trial.url(path))
                        # Kitsune >= 0.3.1 publishes Playwright MCP's core tools: index-addressed tabs, `target`.
                        session.tool("browser_tabs", {"action": "select", "index": tab["id"]})
                        values = trial.expected if draft else {"메모": trial.expected["answer"]}
                        for label, value in values.items():
                            session.tool("browser_type", {"target": f'input[name="{label}"]', "text": value})
                        session.tool("browser_click", {"target": "form > button:first-of-type"})
                        session.evidence["snapshots"].append(session.inventory())
                        evaluation = trial.evaluate({"execution_status": "completed_unscored"}, session.evidence)
                        self.assertTrue(evaluation["task_success"], evaluation)
                    finally:
                        session.close()


@unittest.skipUnless(os.environ.get("PERSONAL_BROWSER_TEST") == "1", "opt-in native Firefox MCP test; no model calls")
class NativeBrowserTests(unittest.TestCase):
    def test_six_fixtures_seed_and_solve_via_real_playwright_ui(self):
        import re
        for task in selected_tasks():
            with self.subTest(task=task["id"]), tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as folder, PersonalServer(task, 0) as server:
                server.begin("playwright")
                trial = server.trials[server.by_target["playwright"]]
                settings = {"target": "playwright", "upstream": ["node", str(ROOT / "node_modules/@playwright/mcp/cli.js"),
                    "--browser", "firefox", "--isolated", "--headless"],
                    "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
                    "active_index": trial.active_index, "evidence_path": folder + "/evidence.json", "origin": server.origin}
                env = {"PLAYWRIGHT_BROWSERS_PATH": str(ROOT / "artifacts/browsers"),
                       "PLAYWRIGHT_SKIP_BROWSER_GC": "1", "PWTEST_SOCKETS_DIR": folder}
                with patch.dict(os.environ, env):
                    session = NativeSession(settings)
                    try:
                        session.start()
                        initialized = session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "personal-fixture-test", "version": "1"}})
                        self.assertNotIn("error", initialized)
                        session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                        session.prepare()
                        self.assertTrue(session.evidence["setup_complete"])
                        # Read-only tasks explicitly open their evidence source in a new tab.
                        source = {"policy": "/policy/current", "orders": "/order/2"}.get(task["fixture"])
                        if source:
                            session.tool("browser_tabs", {"action": "new", "url": trial.url(source)})
                        draft = task["fixture"] in {"calendar", "contact"}
                        path = {"article": "/article", "products": "/compare", "policy": "/search", "orders": "/orders",
                                "calendar": "/calendar", "contact": "/contact"}[task["fixture"]]
                        tab = next(t for t in session.inventory() if t["url"] == trial.url(path))
                        session.tool("browser_tabs", {"action": "select", "index": tab["id"]})
                        response = session.tool("browser_snapshot", {})
                        snapshot = "\n".join(i.get("text", "") for i in response["content"])
                        values = trial.expected if draft else {"메모": trial.expected["answer"]}
                        for label, value in values.items():
                            match = re.search(r'textbox "' + re.escape(label) + r'" \[ref=([^\]]+)\]', snapshot)
                            self.assertIsNotNone(match, snapshot[:3000])
                            session.tool("browser_type", {"target": match[1], "element": label, "text": value})
                        button = "초안 저장" if task["fixture"] == "calendar" else "임시저장" if draft else "저장"
                        snapshot = "\n".join(i.get("text", "") for i in session.tool("browser_snapshot", {})["content"])
                        match = re.search(r'button "' + button + r'" \[ref=([^\]]+)\]', snapshot)
                        self.assertIsNotNone(match, snapshot[:3000])
                        session.tool("browser_click", {"target": match[1], "element": button})
                        session.evidence["snapshots"].append(session.inventory())
                        evaluation = trial.evaluate({"execution_status": "completed_unscored"}, session.evidence)
                        self.assertTrue(evaluation["task_success"], evaluation)
                    finally:
                        session.close()
