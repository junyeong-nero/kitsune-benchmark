"""One paired smoke run using private Firefox/bridge resources, not a benchmark."""

from __future__ import annotations

from contextlib import ExitStack
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

from .cost_metrics import observation_volume, pair_resource_phases, rpc_records, run_timing
from .adapter import (API_HARNESSES, PINNED_CODEX_VERSION, claude_budget, harness_environment, harness_pins, harness_preflight,
                      resolve, run, terminate_group, write_json)
from .resources import ResourceCollector, ResourceRoot
from .viewport import CONTENT_HEIGHT, CONTENT_WIDTH, FIREFOX_CHROME_HEIGHT, observed_viewport, viewport_record
from .specs import Server, Task, identifier, load_task, positive_int

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ("playwright", "kitsune")
WS_SETTING = "const WS_URL = 'ws://127.0.0.1:47652';"


def copy_extension(source: Path, destination: Path, ws_port: int) -> dict:
    """Only alter the private extension copy's endpoint; leave source untouched."""
    if not 1024 <= ws_port <= 65535 or ws_port == 47652:
        raise ValueError("Smoke extension requires a non-default unprivileged WS port.")
    script = source / "background/background.js"
    original = script.read_text()
    if original.count(WS_SETTING) != 1:
        raise ValueError("Unexpected Kitsune extension endpoint; review the copy patch.")
    shutil.copytree(source, destination)
    patched = original.replace(WS_SETTING, f"const WS_URL = 'ws://127.0.0.1:{ws_port}';")
    (destination / "background/background.js").write_text(patched)
    return {
        "change": "WS_URL only in private copy",
        "original_background_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "patched_background_sha256": hashlib.sha256(patched.encode()).hexdigest(),
        "ws_port": ws_port,
    }


def private_ports() -> tuple[int, int]:
    with socket.socket() as http, socket.socket() as ws:
        http.bind(("127.0.0.1", 0))
        ws.bind(("127.0.0.1", 0))
        ports = (http.getsockname()[1], ws.getsockname()[1])
    if any(p in {47651, 47652} for p in ports):
        return private_ports()
    return ports


def bridge_status(port: int, token: str) -> dict | None:
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/status",
                                     headers={"Authorization": "Bearer " + token})
    try:
        # A proxy must never receive the test bridge's bearer token.
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=1) as response:
            return json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return None


def await_bridge(port: int, token: str, process: subprocess.Popen,
                 *, extension: bool = False, timeout: int = 40) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("Test browser/bridge exited; inspect private setup logs.")
        status = bridge_status(port, token)
        if status and (not extension or status.get("extension_connected")):
            return status
        time.sleep(0.25)
    raise ValueError("Timed out waiting for isolated bridge/extension; inspect private setup logs.")


def source_revision(path: Path) -> dict:
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=10)
    dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=10)
    return {"revision": result.stdout.strip() if result.returncode == 0 else None,
            "dirty": bool(dirty.stdout) if dirty.returncode == 0 else None}


def tool_surface(metadata_path: Path, enabled_tools: tuple[str, ...]) -> dict | None:
    """Allowlisted tools the native server actually published (#1); None without session metadata."""
    try:
        metadata = json.loads(metadata_path.read_text())
    except (OSError, ValueError):
        return None
    published = sorted({tool["name"] for page in metadata.get("tools_pages", []) if isinstance(page, dict)
                        for tool in page.get("tools", []) if isinstance(tool, dict) and "name" in tool})
    enabled = sorted(enabled_tools)
    exposed = [name for name in enabled if name in published]
    return {"enabled": enabled, "published_count": len(published), "exposed": exposed,
            "missing": [name for name in enabled if name not in published],
            "no_allowlisted_tools": not exposed}


def session_setup(evidence_path: Path) -> bool | None:
    """A session relay's setup from its evidence (#56): True once complete, False once failed, None while pending."""
    try:
        evidence = json.loads(evidence_path.read_text())
    except (OSError, ValueError):
        return None
    if evidence.get("setup_complete") is True:
        return True
    return False if evidence.get("error") else None


def rewrite_json(path: Path, value: dict) -> None:
    """Replace a private JSON record written earlier with write_json."""
    temporary = path.with_name(path.name + ".tmp")
    write_json(temporary, value)
    os.replace(temporary, path)


def benchmark_source() -> dict:
    """This repository's revision and nearest frozen taskset tag (e.g. taskset-v1-3-gabc1234-dirty)."""
    taskset = subprocess.run(["git", "-C", str(ROOT), "describe", "--tags", "--match", "taskset-*", "--dirty"],
                             capture_output=True, text=True, timeout=10)
    return {**source_revision(ROOT), "taskset": taskset.stdout.strip() if taskset.returncode == 0 else None}


def experiment() -> dict:
    spec = json.loads((ROOT / "configs/experiments/smoke.json").read_text())
    if spec["codex_version"] != PINNED_CODEX_VERSION or spec["reasoning_effort"] != "medium":
        raise ValueError("Smoke configuration differs from adapter pins.")
    return spec


def run_pair(*, execute: bool = False, kitsune_project: str | None = None,
             executable: str = "codex", timeout: int | None = None,
             experiment_spec: dict | None = None, artifact_scope: str = "smoke",
             task_for_target: Callable[[str], Task] | None = None,
             evaluate: Callable[[str, dict], dict] | None = None,
             enabled_tools: dict[str, tuple[str, ...]] | None = None,
             prepare_server: Callable[[str, Server, Task, Path], Server] | None = None,
             harness: str = "codex", kitsune_preset: str | None = None,
             targets: tuple[str, ...] = TARGETS,
             kitsune_env: dict[str, str] | None = None,
             kitsune_firefox_args: tuple[str, ...] = (),
             kitsune_firefox_prefs: dict[str, str] | None = None,
             viewport_reports: Callable[[str], list[dict] | None] | None = None,
             equalize_kitsune_viewport: bool = False) -> dict:
    """kitsune_preset sets KITSUNE_TOOL_PRESET for the Kitsune server (A/B of its tool surface).
    targets restricts which MCPs run, e.g. Kitsune-only A/B arms.
    kitsune_env adds KITSUNE_* settings (e.g. KITSUNE_PROTECT_USER_TABS) for the Kitsune server;
    kitsune_firefox_args/prefs extend the web-ext Firefox launch (the coexistence track's user
    channel). viewport_reports returns a target's fixture page viewport reports after its run;
    equalize_kitsune_viewport adds Firefox's chrome height to the Kitsune window so its content
    viewport matches Playwright's. The defaults leave every existing track's launch unchanged."""
    if not targets or len(set(targets)) != len(targets) or set(targets) - set(TARGETS):
        raise ValueError("targets must be a non-empty subset of playwright, kitsune.")
    if kitsune_preset is not None and not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", kitsune_preset):
        raise ValueError("Invalid Kitsune tool preset name.")
    reserved = {"KITSUNE_HOME", "KITSUNE_HTTP_PORT", "KITSUNE_WS_PORT", "KITSUNE_TOKEN", "KITSUNE_TOOL_PRESET"}
    for key, value in (kitsune_env or {}).items():
        if not re.fullmatch(r"KITSUNE_[A-Z_]{1,40}", key) or key in reserved or not isinstance(value, str):
            raise ValueError("kitsune_env takes KITSUNE_* string settings other than the bridge/preset ones.")
    for arg in kitsune_firefox_args:
        if not re.fullmatch(r"--[a-z][a-z-]{1,40}(=[0-9]{1,5})?", arg):
            raise ValueError("Unsupported Firefox launch argument.")
    for key, value in (kitsune_firefox_prefs or {}).items():
        if not re.fullmatch(r"[a-z][a-zA-Z0-9_.-]{1,80}", key) or not re.fullmatch(r"true|false|[0-9]{1,9}", value):
            raise ValueError("Unsupported Firefox preference.")
    spec = experiment() if experiment_spec is None else experiment_spec
    model, effort = harness_pins(spec, harness)
    max_budget_usd = claude_budget(spec, harness)
    if not execute:
        return {"mode": "smoke_plan_only", "model_invoked": False, "experiment": spec,
                "next": "Install pinned tools/private Firefox, then use smoke --execute."
                " Execution consumes subscription quota."}
    if os.name != "posix":
        raise ValueError("Smoke process isolation requires POSIX.")
    timeout = spec["timeout_sec"] if timeout is None else positive_int(timeout, "timeout")
    path = resolve(executable, harness)
    env = harness_environment(harness, path)
    harness_preflight(harness, path, env, model)
    if harness in API_HARNESSES:
        # The key is re-read per run from .env; keep it out of the shared pair environment.
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_CUSTOM_HEADERS", None)
    project = Path(kitsune_project).expanduser().resolve() if kitsune_project else ROOT.parent / "kitsune"
    if not (project / "extension/manifest.json").is_file():
        raise ValueError("Kitsune source/extension not found; set --kitsune-project.")
    web_ext = ROOT / "node_modules/.bin/web-ext"
    playwright_cli = ROOT / "node_modules/@playwright/mcp/cli.js"
    if not web_ext.exists() or not playwright_cli.exists():
        raise ValueError("Install pinned tools with npm ci --ignore-scripts first.")
    cache = ROOT / "artifacts/browsers"
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(cache)
    env["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"
    get_binary = subprocess.run(["node", "-e", "console.log(require('playwright').firefox.executablePath())"],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=10, check=True)
    firefox = Path(get_binary.stdout.strip())
    if not firefox.is_file():
        raise ValueError("Private Firefox missing; install with PLAYWRIGHT_BROWSERS_PATH and GC disabled.")
    parent = ROOT / "artifacts" / identifier(artifact_scope)
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    pair_dir = parent / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:10])
    pair_dir.mkdir(mode=0o700)
    http_port, ws_port = private_ports()
    patch_info = copy_extension(project / "extension", pair_dir / "extension", ws_port)
    env.update({
        "KITSUNE_HOME": str(pair_dir / "bridge-home"),
        "KITSUNE_HTTP_PORT": str(http_port), "KITSUNE_WS_PORT": str(ws_port),
        "KITSUNE_TOKEN": secrets.token_urlsafe(32),
    })
    kitsune_vars = ("KITSUNE_HOME", "KITSUNE_HTTP_PORT", "KITSUNE_WS_PORT", "KITSUNE_TOKEN")
    if kitsune_preset is not None:
        env["KITSUNE_TOOL_PRESET"] = kitsune_preset
        kitsune_vars += ("KITSUNE_TOOL_PRESET",)
    for key, value in sorted((kitsune_env or {}).items()):
        env[key] = value
        kitsune_vars += (key,)
    specs = {
        "playwright": Server("playwright", "node", (
            str(playwright_cli), "--browser", "firefox", "--isolated", "--headless",
            "--viewport-size", f"{CONTENT_WIDTH}x{CONTENT_HEIGHT}"),
            ("PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_SKIP_BROWSER_GC", "PWTEST_SOCKETS_DIR"), 60, 45),
        "kitsune": Server("kitsune", "uv", ("run", "--locked", "--project", str(project), "kitsune"),
            kitsune_vars, 60, 45),
    }
    specs = {target: specs[target] for target in targets}
    if enabled_tools is not None:
        specs = {target: replace(server, enabled_tools=enabled_tools[target]) for target, server in specs.items()}
    window_height = CONTENT_HEIGHT + (FIREFOX_CHROME_HEIGHT if equalize_kitsune_viewport else 0)
    firefox_args = ("-headless", f"--width={CONTENT_WIDTH}", f"--height={window_height}", *kitsune_firefox_args)
    viewports = {target: viewport_record(target, server.args, firefox_args, equalized=equalize_kitsune_viewport)
                 for target, server in specs.items()}
    manifest = {
        "viewport": viewports,
        "experiment": spec, "harness": harness, "model": model, "reasoning_effort": effort,
        "max_budget_usd_per_run": max_budget_usd, "kitsune_tool_preset": kitsune_preset,
        "targets": list(targets),
        **({"kitsune_env": dict(sorted(kitsune_env.items()))} if kitsune_env else {}),
        **({"kitsune_firefox_args": list(kitsune_firefox_args)} if kitsune_firefox_args else {}),
        **({"kitsune_firefox_prefs": dict(kitsune_firefox_prefs)} if kitsune_firefox_prefs else {}),
        "enabled_tools": enabled_tools, "browser_binary": str(firefox), "headless": True,
        "kitsune_source": source_revision(project), "benchmark_source": benchmark_source(),
        "extension_patch": patch_info,
        "http_port": http_port, "ws_port": ws_port,
        "limitations": ["One caller-ordered smoke pair, not benchmark evidence.",
                        "Configured Firefox window size is not a content viewport measurement; observed values,"
                        " when fixture pages report them, are in viewport.effective once each run finishes.",
                        "External success evaluation not implemented." if evaluate is None
                        else "External per-target evaluator attached; inspect its track/integrity limits."],
    }
    write_json(pair_dir / "pair-manifest.json", manifest)
    default_task = load_task(ROOT / spec["task"]) if task_for_target is None else None
    results = {}
    with ExitStack() as stack:
        resources = stack.enter_context(ResourceCollector(pair_dir))
        resources.set_phase("setup")
        setup_started = time.monotonic()
        # macOS Unix-domain socket paths are short; the repository artifact
        # path plus Playwright worker suffix exceeds that limit.
        env["PWTEST_SOCKETS_DIR"] = stack.enter_context(
            tempfile.TemporaryDirectory(prefix="bmb-", dir="/tmp"))
        def spawn(argv: list[str], filename: str, component: str) -> subprocess.Popen:
            log = stack.enter_context((pair_dir / filename).open("xb"))
            os.chmod(log.name, 0o600)
            process = subprocess.Popen(argv, env=env, cwd=pair_dir, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True)
            resources.register(ResourceRoot(process.pid, component, "kitsune"))
            def cleanup() -> None:
                resources.set_phase("cleanup")
                terminate_group(process)
            stack.callback(cleanup)
            return process
        # A Playwright-only run (e.g. one half of a parallel suite) starts no Kitsune bridge or browser.
        if "kitsune" in specs:
            bridge = spawn(["uv", "run", "--locked", "--project", str(project),
                            "python", "-m", "kitsune.bridge"], "bridge.log", "bridge")
            await_bridge(http_port, env["KITSUNE_TOKEN"], bridge)
            browser = spawn([str(web_ext), "run", "--no-config-discovery", "--no-input",
                "--source-dir", str(pair_dir / "extension"), "--artifacts-dir", str(pair_dir / "web-ext"),
                "--firefox", str(firefox), "--no-reload", "--start-url", "about:blank",
                *("--args=" + arg for arg in firefox_args),
                *(f"--pref={key}={value}" for key, value in (kitsune_firefox_prefs or {}).items())],
                "firefox.log", "browser_launcher")
            await_bridge(http_port, env["KITSUNE_TOKEN"], browser, extension=True)
        setup_seconds = time.monotonic() - setup_started
        resources.set_phase("ready")
        time.sleep(1)
        # Scope these values to this Python process and its children only.
        # adapter.run itself still applies the restricted environment policy.
        previous = {key: os.environ.get(key) for key in env}
        try:
            os.environ.update(env)
            for target, server in specs.items():
                task = task_for_target(target) if task_for_target else default_task
                assert task is not None
                if prepare_server is not None:
                    server = prepare_server(target, server, task, pair_dir)
                resources.set_phase("task_" + target)
                external = (ResourceRoot(bridge.pid, "bridge", "kitsune", True),
                            ResourceRoot(browser.pid, "browser_launcher", "kitsune", True)) if target == "kitsune" else ()
                # Session relays (prepare_server) set up lazily and record it in this evidence file.
                evidence = pair_dir / (target + "-session-evidence.json")
                result = run(server, task, model, executable=path, timeout=timeout,
                             output_root=str(pair_dir / "runs"), confirm_isolated_browser=True,
                             resource_roots=external, resource_observer=resources, viewport=viewports[target],
                             harness=harness, effort=effort, max_budget_usd=max_budget_usd,
                             session_setup=partial(session_setup, evidence) if prepare_server is not None else None)
                if result["execution_status"] == "setup_failed":
                    print(f"warning: {target} session setup failed; the harness was stopped before the agent started",
                          file=sys.stderr)
                result["viewport"] = observed_viewport(viewports[target],
                                                       viewport_reports(target) if viewport_reports else None)
                run_manifest = Path(result["run_dir"]) / "manifest.json"
                rewrite_json(run_manifest, {**json.loads(run_manifest.read_text()), "viewport": result["viewport"]})
                result["observation_volume"] = observation_volume(rpc_records(pair_dir, target))
                result["timing"] = run_timing(pair_dir, target, result)
                if evaluate is not None:
                    evaluation = evaluate(target, result)
                    write_json(Path(result["run_dir"]) / "evaluation.json", evaluation)
                    result["benchmark_evaluation"] = evaluation
                if server.enabled_tools:
                    surface = tool_surface(pair_dir / (target + "-native-metadata.json"), server.enabled_tools)
                    if surface is not None:
                        result["tool_surface"] = surface
                        if surface["no_allowlisted_tools"]:
                            print(f"warning: {target} published none of the allowlisted tools", file=sys.stderr)
                        elif surface["missing"]:
                            print(f"warning: {target} did not publish allowlisted tools: "
                                  + ", ".join(surface["missing"]), file=sys.stderr)
                results[target] = result
                write_json(pair_dir / (target + "-summary.json"), result)
                if (result["execution_status"] != "completed_unscored"
                        or (evaluate is not None and not result["benchmark_evaluation"].get("scorable"))):
                    # Do not silently substitute another model/harness or keep
                    # spending quota after the first integration failure.
                    break
        finally:
            resources.set_phase("cleanup")
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    observed = {target: results[target]["viewport"] if target in results else record
                for target, record in viewports.items()}
    rewrite_json(pair_dir / "pair-manifest.json", {**manifest, "viewport": observed})
    summary = {"pair_dir": str(pair_dir), "harness": harness, "model": model, "results": results,
               "task_success": None, "viewport": observed,
               "evaluation": "per_target_external_evaluator" if evaluate else "not_implemented",
               "resource_summary_path": str(pair_dir / "resource-summary.json"),
               "resource_phases": pair_resource_phases(resources.summary, specs),
               "timing": {"kitsune_cold_start_setup_sec": setup_seconds if "kitsune" in specs else None}}
    write_json(pair_dir / "pair-summary.json", summary)
    return summary
