"""Codex / Claude Code CLI orchestration. No direct model API client or credential copying."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from .viewport import viewport_record
from . import claude_harness
from .audit import audit_events
from .doctor import diagnose
from .runtime import codex_environment, find_codex
from .resources import ResourceCollector, ResourceRoot
from .specs import Server, Task, positive_int, text, toml_value

PINNED_CODEX_VERSION = "0.163.0"
DISABLED_FEATURES = (
    "shell_tool", "apps", "browser_use", "browser_use_external", "in_app_browser",
    "image_generation", "view_image", "multi_agent", "multi_agent_v2", "memories",
    "external_agent_memory_import", "hooks", "plugins", "remote_plugin",
    "skill_search", "skill_mcp_dependency_install", "shell_snapshot", "tool_suggest",
)
COMMON_INSTRUCTIONS = (
    "Perform the user task using only the tools from the browser MCP server. "
    "Do not use shell, filesystem, built-in search, other agents, or alternative network access. "
    "Do not modify browser settings, unrelated tabs, or accounts. "
    "If blocked, report the blocker honestly. State the final result concisely. "
    "Do not claim that an external evaluator has marked the task successful."
)
HARNESSES = ("codex", "claude", "claude-api", "claude-api-full")
CLAUDE_HARNESSES = ("claude", "claude-api", "claude-api-full")
# API-key harnesses: claude-api uses --bare (first-paragraph tool descriptions);
# claude-api-full omits --bare, so the client sends full descriptions.
API_HARNESSES = ("claude-api", "claude-api-full")
REQUIRED_EXEC_FLAGS = (
    "--ignore-user-config", "--ignore-rules", "--ephemeral", "--json",
    "--output-last-message", "--skip-git-repo-check",
)


def settings(server: Server) -> dict:
    values = {
        "model_provider": "openai",
        "model_reasoning_effort": "medium",
        "forced_login_method": "chatgpt",
        "approval_policy": "never",
        "web_search": "disabled",
        "project_doc_max_bytes": 0,
        "suppress_unstable_features_warning": True,
        "developer_instructions": COMMON_INSTRUCTIONS,
        "skills.include_instructions": False,
        "skills.bundled.enabled": False,
        "plugins._default.enabled": False,
        "features.skip_host_skill_discovery": True,
        "mcp_servers": {"browser": {
            "command": server.command, "args": server.args, "env_vars": server.env_vars,
            "startup_timeout_sec": server.startup_timeout_sec,
            "tool_timeout_sec": server.tool_timeout_sec,
            "required": True, "enabled": True,
            "default_tools_approval_mode": "approve",
        }},
    }
    if server.enabled_tools:
        values["mcp_servers"]["browser"]["enabled_tools"] = server.enabled_tools
    values.update({f"features.{name}": False for name in DISABLED_FEATURES})
    return values


def command(executable: str, server: Server, model: str, final_path: Path) -> list[str]:
    text(model, "model")
    argv = [
        executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check", "--sandbox", "read-only", "--json", "--color", "never",
        "--model", model, "--output-last-message", str(final_path),
    ]
    for key, value in settings(server).items():
        argv.extend(["-c", key + "=" + toml_value(value)])
    # Prompt travels through stdin rather than the process argument list.
    return argv + ["-"]


def resolve(executable: str, harness: str = "codex") -> str:
    if harness in CLAUDE_HARNESSES:
        found = claude_harness.find_claude(executable)
        if found is None:
            raise ValueError("Claude Code not found; pass --claude with the executable path.")
        return str(Path(found).absolute())
    found = find_codex(executable)
    if found is None:
        raise ValueError("Codex not found; pass --codex with the executable path.")
    return str(Path(found).absolute())


def harness_pins(spec: dict, harness: str) -> tuple[str, str]:
    """Return (model, effort) for a harness after checking its CLI version pin."""
    if harness in CLAUDE_HARNESSES:
        pins = spec.get("claude_code")
        if not isinstance(pins, dict) or pins.get("version") != claude_harness.PINNED_CLAUDE_VERSION:
            raise ValueError("Experiment lacks a Claude Code pin matching " + claude_harness.PINNED_CLAUDE_VERSION)
        return text(pins.get("model"), "model"), pins.get("effort", "medium")
    if harness != "codex":
        raise ValueError("Unknown harness.")
    if spec["codex_version"] != PINNED_CODEX_VERSION or spec["reasoning_effort"] != "medium":
        raise ValueError("Experiment differs from adapter pins.")
    return spec["model"], spec["reasoning_effort"]


def harness_environment(harness: str, path: str, server: Server | None = None,
                        codex_home: str | None = None) -> dict[str, str]:
    extra = server.env_vars if server is not None else ()
    if harness in API_HARNESSES:
        key = claude_harness.load_api_key()
        workspace, _ = claude_harness.resolve_workspace(key)
        return claude_harness.claude_environment(path, extra, server=server, api_key=key, workspace_id=workspace)
    if harness == "claude":
        return claude_harness.claude_environment(path, extra, server=server)
    return codex_environment(path, codex_home, extra)


def with_claude_overrides(spec: dict, model: str | None = None,
                          max_budget_usd_per_run: float | None = None, codex_model: str | None = None) -> dict:
    """Copy of spec with CLI overrides of its claude_code model/per-run cap and Codex model; the config file
    stays unchanged."""
    if codex_model is not None:
        spec = {**spec, "model": text(codex_model, "codex_model")}
    if model is None and max_budget_usd_per_run is None:
        return spec
    pins = dict(spec.get("claude_code") or {})
    if model is not None:
        pins["model"] = text(model, "model")
    if max_budget_usd_per_run is not None:
        if isinstance(max_budget_usd_per_run, bool) or not isinstance(max_budget_usd_per_run, (int, float)) \
                or max_budget_usd_per_run <= 0:
            raise ValueError("max_budget_usd_per_run must be a positive amount.")
        pins["max_budget_usd_per_run"] = float(max_budget_usd_per_run)
    return {**spec, "claude_code": pins}


def per_run_cap(spec: dict) -> float:
    """The per-run dollar cap: an explicit claude_code.max_budget_usd_per_run (the CLI override), else the
    entry for the run's model in claude_code.max_budget_usd_per_run_by_model."""
    pins = spec.get("claude_code") or {}
    value = pins.get("max_budget_usd_per_run")
    if value is None:
        value = (pins.get("max_budget_usd_per_run_by_model") or {}).get(pins.get("model"))
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"No per-run dollar cap for model {pins.get('model')!r}: add it to "
                         "claude_code.max_budget_usd_per_run_by_model or pass --max-budget-usd-per-run.")
    return float(value)


def claude_budget(spec: dict, harness: str) -> float | None:
    """Per-run --max-budget-usd for API-key runs; subscription runs are not dollar-capped."""
    if harness not in API_HARNESSES:
        return None
    return per_run_cap(spec)


def claude_preflight(path: str, env: dict[str, str], *, api: bool = False, model: str | None = None) -> dict:
    report = claude_harness.diagnose(path, env=env, api=api, model=model)
    if not report["prerequisites_ok"]:
        failures = ", ".join(c["name"] for c in report["checks"] if not c["passed"])
        raise ValueError("Claude Code preflight failed: " + failures)
    version = next(c["detail"] for c in report["checks"] if c["name"] == "claude_version")
    if version != "claude-code " + claude_harness.PINNED_CLAUDE_VERSION:
        raise ValueError("Claude Code version differs from the validated pin " + claude_harness.PINNED_CLAUDE_VERSION)
    return report


def harness_preflight(harness: str, path: str, env: dict[str, str], model: str | None = None) -> dict:
    if harness in CLAUDE_HARNESSES:
        return claude_preflight(path, env, api=harness in API_HARNESSES, model=model)
    return preflight(path, env)


def plan(server: Server, task: Task, model: str, executable: str = "codex", timeout: int = 300) -> dict:
    positive_int(timeout, "timeout")
    path = resolve(executable)
    return {
        "mode": "plan_only", "model_invoked": False,
        "expected_codex_version": PINNED_CODEX_VERSION,
        "reasoning_effort": "medium",
        "model": text(model, "model"), "server": asdict(server), "task": asdict(task),
        "timeout_sec": timeout,
        "argv_template": command(path, server, model, Path("<PRIVATE_RUN_DIR>/final.txt")),
        "auth": "Existing ChatGPT CLI login; API/provider environment not inherited.",
        "workspace": "Fresh temporary directory outside the source repository.",
        "scoring": "Unscored; no external evaluator implemented.",
    }


def preflight(path: str, env: dict[str, str]) -> dict:
    report = diagnose(path, env=env)
    if not report["prerequisites_ok"]:
        failures = ", ".join(c["name"] for c in report["checks"] if not c["passed"])
        raise ValueError("Codex preflight failed: " + failures)
    version = next(c["detail"] for c in report["checks"] if c["name"] == "codex_version")
    if version != "codex-cli " + PINNED_CODEX_VERSION:
        raise ValueError("Codex version differs from the validated pin " + PINNED_CODEX_VERSION)
    result = subprocess.run([path, "exec", "--help"], env=env,
                            capture_output=True, text=True, timeout=15, check=False)
    if result.returncode or any(flag not in result.stdout for flag in REQUIRED_EXEC_FLAGS):
        raise ValueError("Installed Codex lacks required isolation/trace options.")
    return report


def write_json(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    path.chmod(0o600)


def _has_live_group(pgid: int) -> bool:
    result = subprocess.run(["ps", "-axo", "pgid=,stat="],
                            capture_output=True, text=True, timeout=2, check=True)
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == str(pgid) and not fields[1].startswith("Z"):
            return True
    return False


def _await_dead_group(pgid: int) -> bool:
    deadline = time.monotonic() + 2
    while _has_live_group(pgid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def terminate_group(process: subprocess.Popen) -> None:
    """Bound cleanup to this run's process group, including MCP children."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin can report EPERM for a group containing only dead/zombie
        # descendants. Allow a bounded grace period for in-flight exits.
        # Never swallow a permission error for surviving live processes.
        if not _await_dead_group(process.pid):
            raise
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    # The parent may have exited while children ignored SIGTERM.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        if not _await_dead_group(process.pid):
            raise
    process.wait()


SETUP_POLL_SEC = 0.1


def write_prompt(stream, prompt: bytes) -> None:
    """Write the whole prompt, then close stdin so the harness sees its end; a harness that exited is ignored."""
    try:
        stream.write(prompt)
    except OSError:
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


def await_harness(process: subprocess.Popen, prompt: bytes, timeout: int,
                  session_setup: Callable[[], bool | None] | None = None) -> bool:
    """Send the prompt and wait for the harness to exit; TimeoutExpired after `timeout`.

    The prompt is written once, in the background, so a harness that reads stdin late still gets all of it.
    session_setup reports a session relay's setup: None while pending, True once complete, False if it failed.
    Until it settles it is polled every SETUP_POLL_SEC; on failure this returns True at once, with the harness still
    running, for the caller to stop it. The relay leaves the client's tool list unanswered after a failed setup, so
    the harness has not sent a model request yet if the client was still waiting for that list (#56)."""
    deadline = time.monotonic() + timeout
    threading.Thread(target=write_prompt, args=(process.stdin, prompt), daemon=True).start()
    while True:
        outcome = session_setup() if session_setup is not None else True
        if outcome is False:
            return True
        remaining = deadline - time.monotonic()
        try:
            process.wait(timeout=remaining if outcome else min(remaining, SETUP_POLL_SEC))
            return False
        except subprocess.TimeoutExpired:
            if time.monotonic() >= deadline:
                raise


def model_request_observed(audit: dict) -> bool:
    """Whether the harness's events show a model request: usage, an assistant message, a turn or a tool call."""
    return bool(audit.get("usage") or (audit.get("token_attribution") or {}).get("requests")
                or audit.get("num_turns") or audit.get("mcp_calls"))


def run(
    server: Server, task: Task, model: str, *, executable: str = "codex",
    codex_home: str | None = None, timeout: int = 300, output_root: str = "runs",
    confirm_isolated_browser: bool = False,
    resource_roots: tuple[ResourceRoot, ...] = (),
    resource_observer: ResourceCollector | None = None,
    viewport: dict | None = None,
    harness: str = "codex", effort: str = "medium", max_budget_usd: float | None = None,
    session_setup: Callable[[], bool | None] | None = None,
) -> dict:
    """session_setup: see await_harness. A failed setup stops the harness and records `setup_failed`."""
    if harness not in HARNESSES:
        raise ValueError("Unknown harness.")
    if harness in API_HARNESSES and max_budget_usd is None:
        raise ValueError("claude-api runs require a per-run dollar cap.")
    if os.name != "posix":
        raise ValueError("Process-group cleanup is currently supported only on POSIX.")
    if not confirm_isolated_browser:
        raise ValueError("Use --confirm-isolated-browser only after setting up a dedicated test browser/profile.")
    positive_int(timeout, "timeout")
    text(model, "model")
    path = resolve(executable, harness)
    env = harness_environment(harness, path, server, codex_home)
    preflight_report = harness_preflight(harness, path, env, model)
    root = Path(output_root).expanduser().absolute()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12])
    run_dir.mkdir(mode=0o700)
    final_path = run_dir / "final.txt"
    if harness in CLAUDE_HARNESSES:
        api = harness in API_HARNESSES
        argv = claude_harness.command(path, server, model, COMMON_INSTRUCTIONS, effort,
                                      api=api, max_budget_usd=max_budget_usd, bare=harness == "claude-api")
        versions = {"harness": "claude_code", "claude_code_version": claude_harness.PINNED_CLAUDE_VERSION,
                    "auth_policy": "anthropic_api_key_from_env_file" if api else "claude_ai_subscription_only",
                    "mcp_startup": {"connection_nonblocking": False,
                                    "timeout_ms": int(env["MCP_TIMEOUT"]),
                                    "tool_timeout_ms": int(env["MCP_TOOL_TIMEOUT"])}}
        if api:
            # Workspace IDs are not secrets; record which workspace is billed.
            header = env.get("ANTHROPIC_CUSTOM_HEADERS", "")
            versions["anthropic_workspace_id"] = header.split(":", 1)[1].strip() if header else None
    else:
        argv = command(path, server, model, final_path)
        versions = {"harness": "codex", "codex_version": PINNED_CODEX_VERSION,
                    "auth_policy": "chatgpt_subscription_only"}
    manifest = {
        "schema_version": 1, **versions,
        "viewport": viewport if viewport is not None else viewport_record(server.id, server.args),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "reasoning_effort": effort,
        "server": asdict(server), "task": asdict(task),
        "harness_sha256": hashlib.sha256(b"".join(
            p.name.encode() + b"\x00" + p.read_bytes()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        )).hexdigest(),
        "prompt_sha256": hashlib.sha256(task.prompt.encode()).hexdigest(),
        "timeout_sec": timeout,
        "argv": argv, "preflight": preflight_report,
        "isolated_browser_confirmed_by_operator": True,
        "environment_reset": "not_implemented", "external_evaluation": "not_implemented",
        "token_budget": "not_enforced",
        "api_cost": ({"max_budget_usd_per_run": max_budget_usd, "source": "Claude Code total_cost_usd estimate"}
                     if max_budget_usd is not None else None),
        "resource_sampling_interval_sec": 1.0,
        "privacy": "Private raw artifacts; review/redact before sharing.",
    }
    write_json(run_dir / "manifest.json", manifest)
    started = time.monotonic()
    timed_out = False
    interrupted = False
    setup_failed = False
    returncode = None
    launch_failed = False
    events_path = run_dir / "events.jsonl"
    stderr_path = run_dir / "stderr.log"
    with ResourceCollector(run_dir, roots=resource_roots) as resources:
        with tempfile.TemporaryDirectory(prefix="kitsune-benchmark-") as workspace:
            with events_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
                try:
                    process = subprocess.Popen(argv, cwd=workspace, env=env,
                        stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, start_new_session=True)
                except OSError:
                    launch_failed = True
                else:
                    resource_root = ResourceRoot(process.pid, "harness", server.id)
                    resources.register(resource_root)
                    if resource_observer is not None:
                        resource_observer.register(resource_root)
                    resources.set_phase("task")
                    try:
                        setup_failed = await_harness(process, task.prompt.encode(), timeout, session_setup)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                    except KeyboardInterrupt:
                        interrupted = True
                    finally:
                        resources.set_phase("cleanup")
                        terminate_group(process)
                    returncode = process.returncode
    if harness in CLAUDE_HARNESSES:
        audit = claude_harness.audit_events(
            events_path, allowed_tools=server.enabled_tools or None,
            expected_key_source="ANTHROPIC_API_KEY" if harness in API_HARNESSES else "none")
        final = audit.pop("final_message")
        if final is not None:
            final_path.write_text(final)
    else:
        audit = audit_events(events_path, allowed_tools=server.enabled_tools or None)
    if setup_failed:
        audit["harness_error"] = True
        # The guarantee holds only while the client still waits for its tool list (#56); record what happened.
        audit["model_request_observed"] = model_request_observed(audit)
        if audit["model_request_observed"]:
            print("warning: session setup failed, but the harness had already made a model request", file=sys.stderr)
    # Even stderr and successful final answers may contain private page contents.
    for file in run_dir.iterdir():
        if file.is_file():
            file.chmod(0o600)
    if interrupted:
        status = "interrupted"
    elif setup_failed:
        status = "setup_failed"
    elif timed_out:
        status = "timeout"
    elif launch_failed or returncode != 0 or audit["harness_error"]:
        status = "harness_error"
    elif audit["violations"]:
        status = "invalid_trace"
    elif not audit["turn_completed"] or not audit["completed_mcp_calls"] or not final_path.is_file():
        status = "incomplete"
    else:
        status = "completed_unscored"
    summary = {
        "schema_version": 1, "run_dir": str(run_dir), "execution_status": status,
        "returncode": returncode, "elapsed_sec": round(time.monotonic() - started, 3),
        "harness": versions["harness"],
        "model": model, "server_id": server.id, "task_id": task.id, **audit,
        "resources": {
            "summary_path": str(run_dir / "resource-summary.json"),
            "task": resources.summary["metrics"].get("phase/task/all"),
            "sampling_errors": resources.summary["sampling_errors"],
            "unexpected_alive_at_stop": resources.summary["unexpected_alive_at_stop"],
        },
    }
    write_json(run_dir / "summary.json", summary)
    return summary
