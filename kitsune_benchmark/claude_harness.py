"""Claude Code CLI harness: command, read-only diagnostics and stream-json audit.

Two explicit auth modes, never mixed or used as a fallback for each other:
- `claude`: the existing claude.ai subscription login; API keys are stripped.
- `claude-api`: ANTHROPIC_API_KEY read only from the repository `.env`, with
  `--bare` so OAuth/keychain credentials are never read.
No direct model API client and no user/project settings, hooks, skills or MCP servers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .runtime import BASE_ENV
from .specs import Server, text

PINNED_CLAUDE_VERSION = "2.1.303"
MCP_PREFIX = "mcp__browser__"
CLAUDE_API_ENV = frozenset({
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
})
REQUIRED_FLAGS = (
    "--print", "--output-format", "--mcp-config", "--strict-mcp-config", "--tools",
    "--allowedTools", "--setting-sources", "--no-session-persistence", "--permission-mode",
)
API_FLAGS = ("--bare", "--max-budget-usd")
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
MODELS_URL = "https://api.anthropic.com/v1/models?limit=1000"
WORKSPACES_URL = "https://api.anthropic.com/v1/organizations/workspaces"
FILTER_SCRIPT = Path(__file__).resolve().parent / "mcp_tool_filter.py"
BENIGN_EVENTS = {"rate_limit_event", "stream_event", "tool_progress", "keep_alive", "auth_status"}

CommandRunner = Callable[[Sequence[str], Mapping[str, str]], subprocess.CompletedProcess[str]]


def find_claude(executable: str = "claude") -> str | None:
    found = shutil.which(executable)
    if found or executable != "claude":
        return found
    home = Path.home()
    candidates = [home / ".local/bin/claude", home / ".claude/local/claude",
                  Path("/opt/homebrew/bin/claude"), Path("/usr/local/bin/claude")]
    runnable = [p for p in candidates if p.is_file() and os.access(p, os.X_OK)]
    if len(runnable) > 1:
        raise ValueError("Multiple Claude Code installations found; pass --claude explicitly.")
    return str(runnable[0]) if runnable else None


def read_env_file(path: Path | None = None) -> dict[str, str]:
    """Minimal KEY=VALUE parser for `.env`; the process environment is not consulted."""
    path = ENV_FILE if path is None else path
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise ValueError(f"{path.name} not found; add ANTHROPIC_API_KEY=... to it.") from exc
    values = {}
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        values[name] = value.strip("'\"")
    return values


def load_api_key(path: Path | None = None) -> str:
    value = read_env_file(path).get("ANTHROPIC_API_KEY")
    if value is None:
        raise ValueError("ANTHROPIC_API_KEY is missing from .env.")
    if not re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", value):
        raise ValueError("ANTHROPIC_API_KEY in .env does not look like an Anthropic API key.")
    return value


def api_headers(api_key: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    if workspace_id:
        headers["anthropic-workspace-id"] = workspace_id
    return headers


def list_workspaces(api_key: str, timeout: int = 15) -> list[dict]:
    request = urllib.request.Request(WORKSPACES_URL, headers=api_headers(api_key))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return [w for w in json.load(response).get("data", []) if isinstance(w, dict) and not w.get("archived_at")]


_WORKSPACE_CACHE: dict[tuple[str, str | None], tuple[str | None, str]] = {}


def needs_workspace(api_key: str, timeout: int = 15) -> bool:
    """Free GET /v1/models without a workspace header; True only for the API's 'not scoped' error."""
    request = urllib.request.Request(MODELS_URL, headers=api_headers(api_key))
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return False
    except urllib.error.HTTPError as exc:
        try:
            message = str(json.load(exc).get("error", {}).get("message", ""))
        except (OSError, ValueError, AttributeError):
            message = ""
        if exc.code == 400 and "not scoped to a workspace" in message:
            return True
        # Other failures (bad key, network) are reported by check_api_key.
        return False
    except OSError:
        return False


def resolve_workspace(api_key: str, path: Path | None = None,
                      lister: Callable[[str], list[dict]] | None = None,
                      prober: Callable[[str], bool] | None = None) -> tuple[str | None, str]:
    """Return (workspace_id, how) for the anthropic-workspace-id header.

    Explicit ANTHROPIC_WORKSPACE_ID in .env wins. Otherwise the API decides: only a key
    rejected as "not scoped to a workspace" gets one, and only if it has exactly one
    active workspace. Several workspaces must be chosen explicitly.
    """
    explicit = read_env_file(path).get("ANTHROPIC_WORKSPACE_ID")
    if explicit is not None:
        if not re.fullmatch(r"wrkspc_[A-Za-z0-9]+", explicit):
            raise ValueError("ANTHROPIC_WORKSPACE_ID in .env does not look like a workspace ID (wrkspc_…).")
        return explicit, "explicit (.env)"
    cache_key = (api_key, None)
    if lister is None and prober is None and cache_key in _WORKSPACE_CACHE:
        return _WORKSPACE_CACHE[cache_key]
    if not (prober or needs_workspace)(api_key):
        result = (None, "key accepted without a workspace header")
        if lister is None and prober is None:
            _WORKSPACE_CACHE[cache_key] = result
        return result
    try:
        workspaces = (lister or list_workspaces)(api_key)
    except (OSError, ValueError) as exc:
        raise ValueError("Could not list workspaces for this user key; set ANTHROPIC_WORKSPACE_ID in .env.") from exc
    if len(workspaces) != 1:
        names = ", ".join(f"{w.get('id')} ({w.get('name')})" for w in workspaces) or "none"
        raise ValueError(f"User key has {len(workspaces)} active workspaces ({names}); set ANTHROPIC_WORKSPACE_ID in .env.")
    result = (workspaces[0]["id"], f"auto: only active workspace ({workspaces[0].get('name')})")
    if lister is None and prober is None:
        _WORKSPACE_CACHE[cache_key] = result
    return result


def claude_environment(
    executable: str,
    extra_names: tuple[str, ...] = (),
    source: Mapping[str, str] | None = None,
    server: Server | None = None,
    api_key: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, str]:
    """Allowlisted environment. Inherited API keys and provider switches are never passed;
    only an explicitly supplied `.env` key is, for the `claude-api` harness."""
    source = os.environ if source is None else source
    for name in extra_names:
        if (name in BASE_ENV or name in {"NODE_OPTIONS", "NODE_PATH", "LD_PRELOAD",
                "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME"}
                or name.startswith(("ANTHROPIC_", "CLAUDE_", "MCP_", "OPENAI_", "CODEX_"))):
            raise ValueError("MCP env_vars cannot override harness authentication, runtime, or configuration.")
        if name not in source:
            raise ValueError(f"Required MCP environment variable is missing: {name}")
    env = {k: v for k, v in source.items() if k in BASE_ENV or k in extra_names}
    env["PATH"] = str(Path(executable).absolute().parent) + os.pathsep + env.get("PATH", os.defpath)
    env.update({"NO_COLOR": "1", "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1",
                "DISABLE_ERROR_REPORTING": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    # Claude Code 2.1.303 defaults to nonblocking MCP connection. A slow
    # fixture seed/tools-list can otherwise leave the first inference with no
    # tools even though MCP_TIMEOUT has not expired. Own this switch rather
    # than inheriting it: both subscription and API cohorts must await startup.
    env["MCP_CONNECTION_NONBLOCKING"] = "false"
    if server is not None:
        env["MCP_TIMEOUT"] = str(server.startup_timeout_sec * 1000)
        env["MCP_TOOL_TIMEOUT"] = str(server.tool_timeout_sec * 1000)
    if api_key is not None:
        env["ANTHROPIC_API_KEY"] = api_key
        if workspace_id:
            env["ANTHROPIC_CUSTOM_HEADERS"] = "anthropic-workspace-id: " + workspace_id
    return env


def mcp_config(server: Server) -> dict:
    # Declared env_vars are inherited by name from the restricted environment;
    # their values never enter argv or the manifest.
    command, args = server.command, list(server.args)
    if server.enabled_tools:
        # Claude Code's --allowedTools only pre-approves; it does not hide tools.
        # Filter tools/list so the model sees the same set Codex enabled_tools exposes.
        command, args = sys.executable, [str(FILTER_SCRIPT), json.dumps(list(server.enabled_tools)),
                                         "--", command, *args]
    return {"mcpServers": {"browser": {"type": "stdio", "command": command, "args": args}}}


def command(executable: str, server: Server, model: str, instructions: str, effort: str = "medium",
            *, api: bool = False, max_budget_usd: float | None = None, bare: bool | None = None) -> list[str]:
    """bare (default: same as api) adds --bare. Claude Code --bare also sends only the first
    paragraph of each MCP tool description; non-bare sends descriptions in full."""
    text(model, "model")
    bare = api if bare is None else bare
    argv = [
        executable, *(["--bare"] if bare else []), "--print", "--verbose", "--output-format", "stream-json",
        "--model", model, "--effort", effort,
        "--setting-sources", "", "--strict-mcp-config",
        "--mcp-config", json.dumps(mcp_config(server), ensure_ascii=True),
        # No built-in tools at all (no Bash/Read/Web/Task); only browser MCP tools.
        "--tools", "",
        "--permission-mode", "dontAsk",
        "--no-session-persistence", "--disable-slash-commands",
        "--append-system-prompt", instructions,
    ]
    if max_budget_usd is not None:
        if not isinstance(max_budget_usd, (int, float)) or isinstance(max_budget_usd, bool) or max_budget_usd <= 0:
            raise ValueError("max_budget_usd must be a positive number.")
        argv += ["--max-budget-usd", f"{max_budget_usd:g}"]
    if server.enabled_tools:
        argv += ["--allowedTools", ",".join(MCP_PREFIX + tool for tool in server.enabled_tools)]
    else:
        argv += ["--allowedTools", MCP_PREFIX + "*"]
    # Prompt travels through stdin rather than the process argument list.
    return argv


def check_api_key(api_key: str, model: str | None = None, workspace_id: str | None = None,
                  timeout: int = 15) -> tuple[bool, str]:
    """Free metadata request (GET /v1/models): validates the key and model ID without inference."""
    request = urllib.request.Request(MODELS_URL, headers=api_headers(api_key, workspace_id))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            ids = {item.get("id") for item in json.load(response).get("data", []) if isinstance(item, dict)}
    except urllib.error.HTTPError as exc:
        try:
            message = str(json.load(exc).get("error", {}).get("message", ""))[:160].replace(api_key, "<key>")
        except (OSError, ValueError, AttributeError):
            message = ""
        return False, f"Anthropic API rejected the request (HTTP {exc.code}). {message}".strip()
    except (OSError, ValueError):
        return False, "Anthropic API not reachable; no key material retained."
    if model is not None and model not in ids:
        return False, f"Key accepted, but model {model} is not listed for it."
    return True, "Key accepted" + (f"; model {model} available." if model else ".")


def run_command(argv: Sequence[str], env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, env=dict(env), capture_output=True, text=True, timeout=15, check=False)


def diagnose(
    executable: str = "claude",
    *,
    env: Mapping[str, str] | None = None,
    runner: CommandRunner = run_command,
    resolve: Callable[[str], str | None] = find_claude,
    api: bool = False,
    model: str | None = None,
    key_loader: Callable[[], str] | None = None,
    key_checker: Callable[..., tuple[bool, str]] | None = None,
    workspace_resolver: Callable[[str], tuple[str | None, str]] | None = None,
) -> dict[str, Any]:
    """Allowlisted diagnostics only; raw auth output (email/org) and key material are never retained.

    With api=True this makes one free GET /v1/models request; it never runs inference.
    """
    child_env = dict(os.environ if env is None else env)
    path = resolve(executable)
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    add("claude_installed", path is not None,
        "Executable found." if path else "Claude Code not found; install it or pass --claude PATH.")
    if api:
        key_loader = load_api_key if key_loader is None else key_loader
        key_checker = check_api_key if key_checker is None else key_checker
        workspace_resolver = resolve_workspace if workspace_resolver is None else workspace_resolver
        try:
            key = key_loader()
        except ValueError as exc:
            add("api_key_in_env_file", False, str(exc))
        else:
            add("api_key_in_env_file", True, "ANTHROPIC_API_KEY found in .env (value not retained).")
            try:
                workspace, how = workspace_resolver(key)
            except ValueError as exc:
                add("api_workspace", False, str(exc))
            else:
                add("api_workspace", True, f"{workspace or 'none needed'} — {how}")
                add("api_key_accepted", *key_checker(key, model, workspace))
    else:
        api_auth_present = any(child_env.get(key) for key in CLAUDE_API_ENV)
        add("no_api_key_environment", not api_auth_present,
            "API/provider credential environment detected; unset it for subscription-only runs."
            if api_auth_present else "No known API/provider credential environment detected.")
    probes = [("claude_version", [path, "--version"]), ("print_json_support", [path, "--help"])]
    if not api:
        probes.append(("claude_ai_login", [path, "auth", "status"]))
    if path is not None:
        for name, argv in probes:
            try:
                result = runner(argv, child_env)
            except (OSError, subprocess.TimeoutExpired):
                add(name, False, "Command could not complete; no raw output retained.")
                continue
            if result.returncode != 0:
                add(name, False, "Command failed; inspect the CLI locally (raw output omitted).")
            elif name == "claude_version":
                match = re.search(r"\b(\d+\.\d+\.\d+)\s+\(Claude Code\)", result.stdout)
                add(name, match is not None, "claude-code " + match.group(1) if match else "Unrecognized version output.")
            elif name == "print_json_support":
                missing = [flag for flag in REQUIRED_FLAGS + (API_FLAGS if api else ()) if flag not in result.stdout]
                add(name, not missing, "Expected print flags available." if not missing
                    else "Missing flags: " + ", ".join(missing))
            else:
                try:
                    status = json.loads(result.stdout)
                except ValueError:
                    status = {}
                ok = (isinstance(status, dict) and status.get("loggedIn") is True
                      and status.get("authMethod") == "claude.ai" and status.get("apiProvider") == "firstParty")
                add(name, ok, "claude.ai subscription login reported." if ok
                    else "claude.ai login not confirmed; run claude auth login.")
    return {
        "harness": "claude_code",
        "auth_policy": "anthropic_api_key_from_env_file" if api else "claude_ai_subscription_only",
        "model_invoked": False,
        "prerequisites_ok": all(check["passed"] for check in checks),
        "checks": checks,
        "limitations": [
            "No model, MCP server, or browser was started.",
            "Tool isolation and environment reset remain unverified." if api else
            "Model availability, quota, tool isolation, and environment reset remain unverified.",
            "total_cost_usd is Claude Code's client-side estimate; the API console is the billing source." if api else
            "total_cost_usd is Claude Code's list-price estimate, not the subscription charge.",
        ],
    }


def token_attribution(request_inputs: list[int], call_tool: dict[str, tuple[str, int]],
                      result_chars: dict[str, int]) -> dict:
    """Split input into the fixed prefix re-sent with every request and accumulated history.

    The first request's input approximates the prefix (system prompt, tool definitions and
    task). Tool results are measured in characters (no tokenizer); carry_chars multiplies
    each result by the number of later requests that re-send it.
    """
    total = sum(request_inputs)
    prefix = request_inputs[0] if request_inputs else 0
    per_tool: dict[str, dict[str, int]] = {}
    for call_id, (tool, index) in call_tool.items():
        chars = result_chars.get(call_id, 0)
        entry = per_tool.setdefault(tool, {"calls": 0, "result_chars": 0, "carry_chars": 0})
        entry["calls"] += 1
        entry["result_chars"] += chars
        entry["carry_chars"] += chars * max(len(request_inputs) - index - 1, 0)
    return {"requests": len(request_inputs), "request_input_tokens": total,
            "first_request_input_tokens": prefix, "prefix_x_requests_tokens": prefix * len(request_inputs),
            "history_tokens": max(total - prefix * len(request_inputs), 0),
            "per_tool": dict(sorted(per_tool.items(), key=lambda kv: -kv[1]["carry_chars"]))}


def audit_events(path: Path, *, allowed_tools: tuple[str, ...] | None = None,
                 expected_key_source: str | None = None) -> dict:
    """Conservative audit of Claude Code stream-json; never judges task success.

    expected_key_source pins the credential Claude Code reports in its init event
    ("none" for subscription OAuth, "ANTHROPIC_API_KEY" for the .env key).
    """
    violations: set[str] = set()
    calls: set[str] = set()
    completed_calls: set[str] = set()
    failed_calls: set[str] = set()
    usage: dict[str, int] = {}
    completed = False
    harness_error = False
    events = 0
    final = None
    cost = None
    turns = None
    api_error = None
    # Token attribution: per-request input (deduplicated by message id), and per tool the
    # result size and how many later requests re-send it ("carry").
    init_tools: set[str] | None = None
    hallucinated_calls = 0
    hallucinated_ids: set[str] = set()
    request_inputs: list[int] = []
    request_ids: set = set()
    call_tool: dict[str, tuple[str, int]] = {}
    result_chars: dict[str, int] = {}
    with path.open("rb") as stream:
        for raw_line in stream:
            if not raw_line.strip():
                continue
            events += 1
            try:
                event = json.loads(raw_line.decode("utf-8"))
            except (ValueError, UnicodeError):
                violations.add("malformed_jsonl")
                continue
            if not isinstance(event, dict):
                violations.add("malformed_event")
                continue
            kind = event.get("type")
            if kind in BENIGN_EVENTS:
                continue
            if kind == "system":
                if event.get("subtype") == "init":
                    if expected_key_source is not None and event.get("apiKeySource") != expected_key_source:
                        violations.add("unexpected_auth_source")
                    tools = event.get("tools")
                    init_tools = {t for t in tools if isinstance(t, str)} if isinstance(tools, list) else set()
                    if not init_tools:
                        harness_error = True
                    if not isinstance(tools, list) or any(
                            not isinstance(t, str) or not t.startswith(MCP_PREFIX) for t in tools):
                        violations.add("unexpected_builtin_tools")
                    elif allowed_tools is not None and any(t[len(MCP_PREFIX):] not in allowed_tools for t in tools):
                        violations.add("tool_outside_benchmark_allowlist")
                    servers = event.get("mcp_servers")
                    if not isinstance(servers, list) or [s.get("name") for s in servers if isinstance(s, dict)] != ["browser"]:
                        violations.add("unexpected_mcp_server")
                    elif servers[0].get("status") != "connected":
                        harness_error = True
                continue
            if kind == "result":
                tokens = event.get("usage")
                if event.get("is_error") is not False or event.get("subtype") != "success":
                    harness_error = True
                else:
                    completed = True
                if isinstance(event.get("result"), str):
                    final = event["result"]
                if isinstance(event.get("api_error"), str):  # e.g. usage_limit_reached: the session limit (#69)
                    api_error = event["api_error"]
                if isinstance(event.get("total_cost_usd"), (int, float)):
                    cost = event["total_cost_usd"]
                if type(event.get("num_turns")) is int:
                    turns = event["num_turns"]
                if isinstance(tokens, dict):
                    raw = {key: tokens.get(key) for key in (
                        "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}
                    if all(type(v) is int and v >= 0 for v in raw.values()):
                        # Same convention as Codex: input_tokens is total input,
                        # cached_input_tokens a subset (cache reads) of it.
                        usage = {"input_tokens": raw["input_tokens"] + raw["cache_creation_input_tokens"]
                                 + raw["cache_read_input_tokens"],
                                 "cached_input_tokens": raw["cache_read_input_tokens"],
                                 "cache_creation_input_tokens": raw["cache_creation_input_tokens"],
                                 "uncached_input_tokens": raw["input_tokens"],
                                 "output_tokens": raw["output_tokens"]}
                continue
            if kind not in {"assistant", "user"}:
                violations.add("unrecognized_event")
                continue
            message = event.get("message")
            if not isinstance(message, dict):
                violations.add("malformed_item")
                continue
            if kind == "assistant" and event.get("error"):
                harness_error = True
            if kind == "assistant" and message.get("id") not in request_ids:
                request_ids.add(message.get("id"))
                request_usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                request_inputs.append(sum(v for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
                                          if type(v := request_usage.get(k)) is int and v >= 0))
            if event.get("parent_tool_use_id") is not None:
                violations.add("subagent_activity")
            content = message.get("content")
            if isinstance(content, str):
                continue
            if not isinstance(content, list):
                violations.add("malformed_item")
                continue
            for block in content:
                if not isinstance(block, dict):
                    violations.add("malformed_item")
                    continue
                block_type = block.get("type")
                if kind == "assistant":
                    if block_type in {"text", "thinking", "redacted_thinking"}:
                        continue
                    if block_type != "tool_use":
                        violations.add("forbidden_or_unknown_item")
                        continue
                    name = block.get("name")
                    call_id = block.get("id")
                    if not isinstance(name, str) or not name.startswith(MCP_PREFIX):
                        violations.add("forbidden_or_unknown_item")
                        continue
                    if not isinstance(call_id, str):
                        violations.add("missing_mcp_call_id")
                        continue
                    if init_tools is not None and name not in init_tools:
                        # The model invented a tool name; Claude Code refuses it, so nothing ran.
                        # A model error, not a capability breach: counted, not a violation.
                        hallucinated_calls += 1
                        hallucinated_ids.add(call_id)
                        continue
                    calls.add(call_id)
                    call_tool[call_id] = (name[len(MCP_PREFIX):], len(request_inputs) - 1)
                    if allowed_tools is not None:
                        if name[len(MCP_PREFIX):] not in allowed_tools:
                            violations.add("tool_outside_benchmark_allowlist")
                        arguments = block.get("input")
                        if isinstance(arguments, dict):
                            url = arguments.get("url")
                            if isinstance(url, str) and url.strip().lower().startswith(("javascript:", "data:", "file:")):
                                violations.add("forbidden_navigation_scheme")
                else:
                    if block_type == "text":
                        continue
                    if block_type != "tool_result":
                        violations.add("forbidden_or_unknown_item")
                        continue
                    call_id = block.get("tool_use_id")
                    if call_id not in calls:
                        if call_id in hallucinated_ids:
                            continue
                        violations.add("unmatched_tool_result")
                        continue
                    completed_calls.add(call_id)
                    if block.get("is_error") is True:
                        failed_calls.add(call_id)
                    body = block.get("content")
                    result_chars[call_id] = len(body) if isinstance(body, str) else sum(
                        len(item.get("text", "")) for item in body if isinstance(item, dict)) if isinstance(body, list) else 0
    return {
        "events": events,
        "turn_completed": completed,
        "harness_error": harness_error or init_tools is None,
        "api_error": api_error,
        "mcp_calls": len(calls),
        "completed_mcp_calls": len(completed_calls),
        "failed_mcp_calls": len(failed_calls),
        "usage": usage,
        "num_turns": turns,
        "list_price_cost_usd": cost,
        "token_attribution": token_attribution(request_inputs, call_tool, result_chars),
        "nonexistent_tool_calls": hallucinated_calls,
        "final_message": final,
        "violations": sorted(violations),
        "task_success": None,
        "evaluation": "not_implemented",
    }
