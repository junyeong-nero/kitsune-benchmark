import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch

from kitsune_benchmark import claude_harness
from kitsune_benchmark.__main__ import main
from kitsune_benchmark.adapter import claude_budget, harness_pins, run
from kitsune_benchmark.claude_harness import (FILTER_SCRIPT, audit_events, claude_environment, command, diagnose,
                                              load_api_key)
from kitsune_benchmark.personal import config, run_personal
from kitsune_benchmark.specs import Task
from kitsune_benchmark.specs import Server

SERVER = Server("kitsune", "uv", ("run", "kitsune"), ("KITSUNE_TOKEN",), 30, 45, ("browser_tabs", "browser_click"))
INIT = {"type": "system", "subtype": "init", "tools": ["mcp__browser__browser_tabs", "mcp__browser__browser_click"],
        "mcp_servers": [{"name": "browser", "status": "connected"}], "model": "claude-haiku-5-5"}
RESULT = {"type": "result", "subtype": "success", "is_error": False, "result": "done", "num_turns": 3,
          "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "cache_creation_input_tokens": 100,
                                            "cache_read_input_tokens": 1000, "output_tokens": 50}}


def tool_use(call_id, name="mcp__browser__browser_tabs", **arguments):
    return {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
        {"type": "text", "text": "checking"}, {"type": "tool_use", "id": call_id, "name": name, "input": arguments}]}}


def tool_result(call_id, is_error=False):
    return {"type": "user", "parent_tool_use_id": None, "message": {"content": [
        {"type": "tool_result", "tool_use_id": call_id, "is_error": is_error, "content": "x"}]}}


def audit(*events, allowed=SERVER.enabled_tools):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "events.jsonl"
        path.write_text("\n".join(e if isinstance(e, str) else json.dumps(e) for e in events) + "\n")
        return audit_events(path, allowed_tools=allowed)


class ClaudeHarnessTests(unittest.TestCase):
    def test_command_disables_builtins_and_user_config(self):
        argv = command("/bin/claude", SERVER, "claude-haiku-5-5", "only browser")
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
        for flag in ("--strict-mcp-config", "--no-session-persistence", "--print"):
            self.assertIn(flag, argv)
        config_value = json.loads(argv[argv.index("--mcp-config") + 1])
        self.assertEqual(list(config_value["mcpServers"]), ["browser"])
        browser = config_value["mcpServers"]["browser"]
        self.assertNotIn("env", browser)
        self.assertEqual(browser["args"][0], str(FILTER_SCRIPT))
        self.assertEqual(json.loads(browser["args"][1]), list(SERVER.enabled_tools))
        self.assertEqual(browser["args"][2:], ["--", "uv", "run", "kitsune"])
        self.assertEqual(argv[argv.index("--allowedTools") + 1],
                         "mcp__browser__browser_tabs,mcp__browser__browser_click")

    def test_environment_drops_api_credentials(self):
        source = {"HOME": "/h", "PATH": "/usr/bin", "ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "k",
                  "CLAUDE_CODE_USE_BEDROCK": "1", "KITSUNE_TOKEN": "t"}
        env = claude_environment("/opt/claude", ("KITSUNE_TOKEN",), source, SERVER)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", env)
        self.assertEqual(env["KITSUNE_TOKEN"], "t")
        self.assertEqual(env["MCP_TOOL_TIMEOUT"], "45000")
        with self.assertRaises(ValueError):
            claude_environment("/opt/claude", ("ANTHROPIC_BASE_URL",), {"ANTHROPIC_BASE_URL": "x"})

    def test_mcp_startup_blocks_and_cannot_be_overridden(self):
        source = {"PATH": "/usr/bin", "MCP_CONNECTION_NONBLOCKING": "true", "MCP_TIMEOUT": "1"}
        for key in (None, "explicit-api-key"):
            env = claude_environment("/opt/claude", source=source, server=SERVER, api_key=key)
            self.assertEqual(env["MCP_CONNECTION_NONBLOCKING"], "false")
            self.assertEqual(env["MCP_TIMEOUT"], "30000")
            self.assertEqual(env["MCP_TOOL_TIMEOUT"], "45000")
        with self.assertRaises(ValueError):
            claude_environment("/opt/claude", ("MCP_CONNECTION_NONBLOCKING",), source, SERVER)

    def test_missing_pending_and_empty_catalog_are_harness_errors(self):
        for status in ("pending", "failed", "connected"):
            init = {**INIT, "tools": [], "mcp_servers": [{"name": "browser", "status": status}]}
            result = audit(init, RESULT)
            self.assertTrue(result["harness_error"])
            self.assertEqual(result["mcp_calls"], 0)
        self.assertTrue(audit(RESULT)["harness_error"])
        # Malformed tool entries must not crash the audit (dicts are unhashable).
        bad = audit({**INIT, "tools": [{"name": "browser_tabs"}]}, RESULT)
        self.assertIn("unexpected_builtin_tools", bad["violations"])

    def test_successful_trace_usage_and_failed_calls(self):
        result = audit(INIT, tool_use("a"), tool_result("a"), tool_use("b", "mcp__browser__browser_click"),
                       tool_result("b", True), {"type": "rate_limit_event"}, RESULT)
        self.assertTrue(result["turn_completed"])
        self.assertFalse(result["harness_error"])
        self.assertEqual((result["mcp_calls"], result["completed_mcp_calls"], result["failed_mcp_calls"]), (2, 2, 1))
        self.assertEqual(result["usage"], {"input_tokens": 1110, "cached_input_tokens": 1000,
                                           "cache_creation_input_tokens": 100, "uncached_input_tokens": 10,
                                           "output_tokens": 50})
        self.assertEqual(result["final_message"], "done")
        self.assertEqual(result["violations"], [])

    def test_builtin_foreign_and_unlisted_tools_invalidate(self):
        bad_init = {**INIT, "tools": ["Bash", "mcp__browser__browser_tabs"]}
        self.assertIn("unexpected_builtin_tools", audit(bad_init, RESULT)["violations"])
        unlisted = {**INIT, "tools": ["mcp__browser__browser_tabs", "mcp__browser__browser_js"]}
        self.assertIn("tool_outside_benchmark_allowlist", audit(unlisted, RESULT)["violations"])
        foreign = {**INIT, "mcp_servers": [{"name": "browser", "status": "connected"}, {"name": "x"}]}
        self.assertIn("unexpected_mcp_server", audit(foreign, RESULT)["violations"])
        self.assertIn("forbidden_or_unknown_item", audit(INIT, tool_use("a", "Bash"), RESULT)["violations"])
        invented = audit(INIT, tool_use("z", "mcp__browser__browser_wait"), tool_result("z", True), RESULT)
        self.assertEqual((invented["violations"], invented["nonexistent_tool_calls"], invented["mcp_calls"]), ([], 1, 0))
        exposed = {**INIT, "tools": INIT["tools"] + ["mcp__browser__browser_dom"]}  # exists, but not allowlisted
        self.assertIn("tool_outside_benchmark_allowlist",
                      audit(exposed, tool_use("a", "mcp__browser__browser_dom"), RESULT)["violations"])
        self.assertIn("forbidden_navigation_scheme",
                      audit(INIT, tool_use("a", url="javascript:alert(1)"), RESULT)["violations"])
        sub = {**tool_use("a"), "parent_tool_use_id": "p"}
        self.assertIn("subagent_activity", audit(INIT, sub, RESULT)["violations"])
        self.assertIn("unrecognized_event", audit(INIT, {"type": "mystery"}, RESULT)["violations"])
        self.assertIn("malformed_jsonl", audit(INIT, "{not json", RESULT)["violations"])

    def test_errors_are_harness_errors(self):
        failed = {**RESULT, "subtype": "error_during_execution", "is_error": True}
        self.assertTrue(audit(INIT, failed)["harness_error"])
        self.assertFalse(audit(INIT, failed)["turn_completed"])
        limited = {"type": "assistant", "error": "rate_limit", "message": {"content": [{"type": "text", "text": "limit"}]}}
        self.assertTrue(audit(INIT, limited, RESULT)["harness_error"])
        pending = {**INIT, "mcp_servers": [{"name": "browser", "status": "failed"}]}
        self.assertTrue(audit(pending, RESULT)["harness_error"])
        self.assertFalse(audit(INIT)["turn_completed"])

    def test_doctor_requires_claude_ai_login(self):
        def runner(argv, env):
            if argv[1:] == ["--version"]:
                return subprocess.CompletedProcess(argv, 0, "2.1.303 (Claude Code)\n", "")
            if argv[1:] == ["--help"]:
                return subprocess.CompletedProcess(argv, 0, " ".join(
                    ["--print", "--output-format", "--mcp-config", "--strict-mcp-config", "--tools",
                     "--allowedTools", "--setting-sources", "--no-session-persistence", "--permission-mode"]), "")
            return subprocess.CompletedProcess(argv, 0, json.dumps(login), "")
        login = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "email": "secret"}
        report = diagnose("claude", env={"PATH": "/usr/bin"}, runner=runner, resolve=lambda _: "/bin/claude")
        self.assertTrue(report["prerequisites_ok"])
        self.assertNotIn("secret", json.dumps(report))
        login = {"loggedIn": True, "authMethod": "api_key", "apiProvider": "firstParty"}
        self.assertFalse(diagnose("claude", env={}, runner=runner, resolve=lambda _: "/bin/claude")["prerequisites_ok"])
        report = diagnose("claude", env={"ANTHROPIC_API_KEY": "k"}, runner=runner, resolve=lambda _: "/bin/claude")
        self.assertFalse(report["prerequisites_ok"])

    def test_tool_filter_hides_and_refuses_unlisted_tools(self):
        native = ("import json,sys\n"
                  "for line in sys.stdin:\n"
                  " m=json.loads(line)\n"
                  " if 'id' not in m: continue\n"
                  " r={'tools':[{'name':'browser_tabs'},{'name':'browser_js'}]} if m['method']=='tools/list' "
                  "else {'content':[{'type':'text','text':m['params']['name']}]}\n"
                  " print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}),flush=True)\n")
        requests = [{"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "browser_js"}},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "browser_tabs"}}]
        out = subprocess.run([sys.executable, str(FILTER_SCRIPT), '["browser_tabs"]', "--", sys.executable, "-c", native],
                             input="".join(json.dumps(r) + "\n" for r in requests), capture_output=True,
                             text=True, timeout=20, check=True).stdout
        replies = {m["id"]: m["result"] for m in map(json.loads, out.splitlines())}
        self.assertEqual(replies[1]["tools"], [{"name": "browser_tabs"}])
        self.assertTrue(replies[2]["isError"])
        self.assertEqual(replies[3]["content"][0]["text"], "browser_tabs")

    def test_config_pins(self):
        self.assertEqual(harness_pins(config(), "claude"), ("claude-opus-5-5", "medium"))
        self.assertEqual(harness_pins(config(), "codex")[0], config()["model"])
        with self.assertRaises(ValueError):
            harness_pins({"claude_code": {"model": "m", "version": "0.0.1"}}, "claude")


KEY = "sk-ant-api03-" + "x" * 40
HELP = " ".join(claude_harness.REQUIRED_FLAGS + claude_harness.API_FLAGS)


class ClaudeApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env_file = self.root / ".env"
        self.env_file.write_text(f"# comment\nOTHER=1\nexport ANTHROPIC_API_KEY='{KEY}'\n")
        patcher = patch.object(claude_harness, "ENV_FILE", self.env_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_env_file_parsing(self):
        self.assertEqual(load_api_key(), KEY)
        for content, message in (("OTHER=1\n", "missing"), ("ANTHROPIC_API_KEY=not-a-key\n", "does not look")):
            self.env_file.write_text(content)
            with self.assertRaisesRegex(ValueError, message):
                load_api_key()
        self.env_file.unlink()
        with self.assertRaisesRegex(ValueError, "not found"):
            load_api_key()

    def test_api_command_and_environment(self):
        argv = command("/bin/claude", SERVER, "claude-haiku-5-5", "only browser", api=True, max_budget_usd=0.5)
        self.assertEqual(argv[1], "--bare")
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "0.5")
        self.assertNotIn(KEY, " ".join(argv))
        self.assertNotIn("--bare", command("/bin/claude", SERVER, "m", "i"))
        for bad in (0, -1, True, "1"):
            with self.assertRaises(ValueError):
                command("/bin/claude", SERVER, "m", "i", api=True, max_budget_usd=bad)
        # Inherited keys are still dropped; only the explicit .env key is passed.
        env = claude_environment("/opt/claude", (), {"HOME": "/h", "ANTHROPIC_API_KEY": "inherited"}, api_key=KEY)
        self.assertEqual(env["ANTHROPIC_API_KEY"], KEY)
        self.assertNotIn("ANTHROPIC_API_KEY", claude_environment("/opt/claude", (), {"ANTHROPIC_API_KEY": "inherited"}))

    def test_api_doctor_never_retains_key(self):
        def runner(argv, env):
            out = "2.1.303 (Claude Code)" if argv[1:] == ["--version"] else HELP
            return subprocess.CompletedProcess(argv, 0, out, "")
        seen = []
        report = diagnose("claude", env={}, runner=runner, resolve=lambda _: "/bin/claude", api=True,
                          model="claude-haiku-5-5", key_checker=lambda key, model, ws: (seen.append((key, model, ws)) or (True, "ok")))
        self.assertTrue(report["prerequisites_ok"], report)
        self.assertEqual(seen, [(KEY, "claude-haiku-5-5", None)])
        self.assertNotIn(KEY, json.dumps(report))
        self.assertEqual(report["auth_policy"], "anthropic_api_key_from_env_file")
        self.assertNotIn("claude_ai_login", [c["name"] for c in report["checks"]])
        rejected = diagnose("claude", env={}, runner=runner, resolve=lambda _: "/bin/claude", api=True,
                            key_checker=lambda key, model, ws: (False, "rejected"))
        self.assertFalse(rejected["prerequisites_ok"])
        no_ws = diagnose("claude", env={}, runner=runner, resolve=lambda _: "/bin/claude", api=True,
                         workspace_resolver=lambda key: (_ for _ in ()).throw(ValueError("2 active workspaces")))
        self.assertFalse(no_ws["prerequisites_ok"])
        self.assertNotIn("api_key_accepted", [c["name"] for c in no_ws["checks"]])

    def test_user_key_workspace_resolution(self):
        user_key = "sk-ant-usr01-" + "y" * 40
        one = lambda key: [{"id": "wrkspc_01ABC", "name": "Claude Code"}]
        scoped, unscoped = (lambda key: False), (lambda key: True)
        # The API decides, not the key prefix: a user key accepted without a header needs none.
        self.assertEqual(claude_harness.resolve_workspace(user_key, lister=one, prober=scoped),
                         (None, "key accepted without a workspace header"))
        workspace, how = claude_harness.resolve_workspace(user_key, lister=one, prober=unscoped)
        self.assertEqual(workspace, "wrkspc_01ABC")
        self.assertIn("auto", how)
        two = lambda key: [{"id": "wrkspc_01A", "name": "a"}, {"id": "wrkspc_01B", "name": "b"}]
        with self.assertRaisesRegex(ValueError, "2 active workspaces"):
            claude_harness.resolve_workspace(user_key, lister=two, prober=unscoped)
        self.env_file.write_text(f"ANTHROPIC_API_KEY={user_key}\nANTHROPIC_WORKSPACE_ID=wrkspc_01B\n")
        self.assertEqual(claude_harness.resolve_workspace(user_key, lister=two, prober=unscoped),
                         ("wrkspc_01B", "explicit (.env)"))
        self.env_file.write_text(f"ANTHROPIC_API_KEY={user_key}\nANTHROPIC_WORKSPACE_ID=nope\n")
        with self.assertRaisesRegex(ValueError, "does not look like"):
            claude_harness.resolve_workspace(user_key, lister=two, prober=unscoped)
        env = claude_environment("/opt/claude", (), {"HOME": "/h"}, api_key=user_key, workspace_id="wrkspc_01B")
        self.assertEqual(env["ANTHROPIC_CUSTOM_HEADERS"], "anthropic-workspace-id: wrkspc_01B")
        self.assertNotIn("ANTHROPIC_CUSTOM_HEADERS", claude_environment("/opt/claude", (), {"HOME": "/h"}, api_key=KEY))

    def test_auth_source_is_pinned_per_mode(self):
        api_init = {**INIT, "apiKeySource": "ANTHROPIC_API_KEY"}
        sub_init = {**INIT, "apiKeySource": "none"}
        self.assertEqual(audit(api_init, RESULT, allowed=None)["violations"], [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "e.jsonl"
            path.write_text(json.dumps(sub_init) + "\n" + json.dumps(RESULT) + "\n")
            self.assertIn("unexpected_auth_source", audit_events(path, expected_key_source="ANTHROPIC_API_KEY")["violations"])
            self.assertEqual(audit_events(path, expected_key_source="none")["violations"], [])

    def fake_claude(self):
        observed = self.root / "observed.json"
        events = [{"type": "system", "subtype": "ui_invalidate"},
                  {**INIT, "tools": [], "apiKeySource": "@SOURCE@"},
                  {**RESULT, "total_cost_usd": 0.004}]
        script = f"""#!{sys.executable}
import json, os, pathlib, sys
args = sys.argv[1:]
if args == ['--version']:
    print('2.1.303 (Claude Code)'); sys.exit(0)
if args == ['--help']:
    print({HELP!r}); sys.exit(0)
prompt = sys.stdin.read()
pathlib.Path({str(observed)!r}).write_text(json.dumps({{'argv': args, 'key': os.environ.get('ANTHROPIC_API_KEY')}}))
source = 'ANTHROPIC_API_KEY' if '--bare' in args and os.environ.get('ANTHROPIC_API_KEY') else 'none'
print({chr(10).join(json.dumps(e) for e in events)!r}.replace('@SOURCE@', source))
"""
        path = self.root / "claude"
        path.write_text(script)
        path.chmod(0o700)
        return str(path), observed

    def test_fake_api_run_passes_key_only_through_env(self):
        path, observed = self.fake_claude()
        server = Server("kitsune", sys.executable, ("-c", "pass"))
        with patch.object(claude_harness, "check_api_key", return_value=(True, "ok")), \
                patch.object(claude_harness, "needs_workspace", return_value=False), \
                patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-inherited-must-not-be-used"}):
            result = run(server, Task("t", "prompt"), "claude-haiku-5-5", executable=path,
                         output_root=str(self.root / "runs"), confirm_isolated_browser=True,
                         harness="claude-api", max_budget_usd=0.5)
        self.assertEqual(result["execution_status"], "harness_error", result)  # empty MCP catalog
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["list_price_cost_usd"], 0.004)
        seen = json.loads(observed.read_text())
        self.assertEqual(seen["key"], KEY)
        self.assertIn("--bare", seen["argv"])
        for file in Path(result["run_dir"]).iterdir():
            self.assertNotIn(KEY, file.read_text(), file.name)
            self.assertNotIn("inherited-must-not", file.read_text(), file.name)
        manifest = json.loads((Path(result["run_dir"]) / "manifest.json").read_text())
        self.assertEqual(manifest["auth_policy"], "anthropic_api_key_from_env_file")
        self.assertEqual(manifest["api_cost"]["max_budget_usd_per_run"], 0.5)
        self.assertEqual(manifest["mcp_startup"], {
            "connection_nonblocking": False, "timeout_ms": server.startup_timeout_sec * 1000,
            "tool_timeout_ms": server.tool_timeout_sec * 1000})
        with self.assertRaisesRegex(ValueError, "dollar cap"):
            run(server, Task("t", "p"), "m", executable=path, confirm_isolated_browser=True, harness="claude-api")

    def test_budget_config_and_suite_stop(self):
        self.assertEqual(claude_budget(config(), "claude-api"), 1.0)  # opus default
        self.assertIsNone(claude_budget(config(), "claude"))
        with self.assertRaises(ValueError):
            claude_budget({"claude_code": {}}, "claude-api")
        calls = []

        def fake_pair(**kwargs):
            folder = tempfile.mkdtemp(dir=self.root)
            calls.append(kwargs["harness"])
            ok = {"benchmark_evaluation": {"scorable": True, "task_success": True}, "list_price_cost_usd": 0.2, "usage": {}}
            return {"pair_dir": folder, "results": {"playwright": dict(ok), "kitsune": dict(ok)}}
        with patch("kitsune_benchmark.personal.run_pair", side_effect=fake_pair):
            # Worst case per pair is 2 x 1.0 (opus) = 2.0 and each pair really costs 0.4:
            # pairs start at spent 0, 0.4, 0.8; the 4th would risk 1.2 + 2.0 > 3.0.
            result = run_personal(execute=True, harness="claude-api", budget_usd=3.0)
        self.assertEqual(calls, ["claude-api"] * 3)
        self.assertEqual(result["stopped_reason"], "suite_budget")
        self.assertAlmostEqual(result["estimated_cost_usd"], 1.2)
        with self.assertRaises(ValueError):
            run_personal(execute=True, harness="claude", budget_usd=1.0)
        with patch("kitsune_benchmark.personal.run_pair", side_effect=fake_pair), self.assertRaisesRegex(ValueError, "nothing was run"):
            run_personal(execute=True, harness="claude-api", budget_usd=0.5)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["personal", "--harness", "claude-api", "--all", "--budget-usd", "30"]), 0)
        plan = json.loads(out.getvalue())
        self.assertEqual((plan["worst_case_usd"], plan["suite_budget_usd"], plan["planned_model_runs"]), (48.0, 30.0, 48))


class BenchmarkProtocolTests(unittest.TestCase):
    def test_token_attribution_splits_prefix_history_and_carry(self):
        def assistant(mid, total, call=None):
            content = [{"type": "tool_use", "id": call, "name": "mcp__browser__browser_tabs", "input": {}}] if call else []
            return {"type": "assistant", "parent_tool_use_id": None, "message": {"id": mid, "content": content,
                    "usage": {"input_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": total - 1}}}
        result = audit(INIT, assistant("m1", 1000, "a"), assistant("m1", 1000), tool_result("a"),
                       {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": "x" * 50}]}},
                       assistant("m2", 1300, "b"), tool_result("b"), assistant("m3", 1600), RESULT)
        a = result["token_attribution"]
        self.assertEqual((a["requests"], a["request_input_tokens"], a["first_request_input_tokens"]), (3, 3900, 1000))
        self.assertEqual((a["prefix_x_requests_tokens"], a["history_tokens"]), (3000, 900))
        tabs = a["per_tool"]["browser_tabs"]
        self.assertEqual(tabs["calls"], 2)
        # Result "a" (50 chars after the overwrite) is re-sent by 2 later requests, "b" (1 char) by 1.
        self.assertEqual((tabs["result_chars"], tabs["carry_chars"]), (51, 101))

    def test_full_description_api_harness_omits_bare(self):
        argv = command("/bin/claude", SERVER, "m", "i", api=True, max_budget_usd=0.5, bare=False)
        self.assertNotIn("--bare", argv)
        self.assertIn("--max-budget-usd", argv)
        self.assertEqual(harness_pins(config(), "claude-api-full"), ("claude-opus-5-5", "medium"))
        self.assertEqual(claude_budget(config(), "claude-api-full"), 1.0)

    def test_per_run_cap_follows_the_model_unless_overridden(self):
        from kitsune_benchmark.adapter import per_run_cap, with_claude_overrides
        for model, cap in (("claude-opus-5-5", 1.0), ("claude-sonnet-5-5", 0.5), ("claude-haiku-5-5", 0.1)):
            self.assertEqual(per_run_cap(with_claude_overrides(config(), model)), cap)
        self.assertEqual(per_run_cap(with_claude_overrides(config(), "claude-haiku-5-5", 2)), 2.0)
        with self.assertRaisesRegex(ValueError, "--max-budget-usd-per-run"):
            per_run_cap(with_claude_overrides(config(), "some-new-model"))

    def test_v2_contract_allows_closing_agent_tabs_only(self):
        from kitsune_benchmark.personal import PersonalServer, selected_tasks
        with PersonalServer(selected_tasks(["pb-current-01"])[0], 0) as server:
            server.begin("kitsune")
            trial = server.trials[server.by_target["kitsune"]]
            trial.note = trial.expected["answer"]
            tabs = [{"id": i, "url": trial.url(p), "active": i == 0} for i, p in enumerate(trial.paths)]
            opened = [dict(tabs[0], active=False), tabs[1], {"id": 2, "url": trial.url("/article"), "active": True}]
            evidence = {"setup_complete": True, "initial_tabs": tabs, "snapshots": [tabs, opened, tabs], "close_attempts": 1,
                        "tab_calls": [{"tool": "browser_tabs", "action": "new"}, {"tool": "browser_tabs", "action": "close", "index": 2}]}
            e = trial.evaluate({"execution_status": "completed_unscored"}, evidence)
            self.assertTrue(e["task_success"], "v2 is primary since taskset-v2 (#9)")
            self.assertFalse(e["contracts"]["v1_strict_close"]["task_success"])
            self.assertTrue(e["contracts"]["v2_agent_tab_cleanup"]["task_success"])
            evidence["snapshots"].append(tabs[1:])  # a starting tab disappeared
            evidence["tab_calls"].append({"tool": "browser_click"})
            self.assertFalse(trial.evaluate({"execution_status": "completed_unscored"}, evidence)
                             ["contracts"]["v2_agent_tab_cleanup"]["task_success"])

    def test_targets_preset_and_revision_guard(self):
        plan = run_personal(task_ids=["pb-current-01"], harness="claude-api", targets=("kitsune",), kitsune_preset="lean")
        self.assertEqual((plan["planned_model_runs"], plan["worst_case_usd"], plan["targets"]), (1, 1.0, ["kitsune"]))
        with self.assertRaises(ValueError):
            run_personal(task_ids=["pb-current-01"], targets=("chrome",))
        revisions = iter([{"revision": "a", "dirty": False}] * 4 + [{"revision": "b", "dirty": False}] * 4)
        calls = []
        def fake_pair(**kwargs):
            calls.append((kwargs["kitsune_preset"], kwargs["targets"]))
            ok = {"benchmark_evaluation": {"scorable": True, "task_success": True}, "usage": {}}
            return {"pair_dir": tempfile.mkdtemp(), "results": {"kitsune": dict(ok)}}
        with patch("kitsune_benchmark.personal.run_pair", side_effect=fake_pair), \
                patch("kitsune_benchmark.personal.source_revision", side_effect=lambda path: next(revisions)):
            result = run_personal(execute=True, targets=("kitsune",), kitsune_preset="lean")
        # Reads: start a; pair 1 after a; pair 2 before a, after a; pair 3 before b -> stop.
        self.assertEqual(result["stopped_reason"], "kitsune_revision_changed")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], ("lean", ("kitsune",)))
        self.assertEqual(result["completed_pairs"], 2)


if __name__ == "__main__":
    unittest.main()
