"""Bounded, model-free closed-loop load on independent MCPs sharing one browser."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import queue
import secrets
import statistics
import subprocess
import sys
import threading
import time
import uuid

import psutil

from .adapter import terminate_group, write_json
from .resources import ResourceCollector, ResourceRoot
from .stress_resources import StressProcessProbe
from .smoke import ROOT, await_bridge, benchmark_source, copy_extension, private_ports, source_revision

PROTOCOL = "stress-v1"
PROFILE_PATH = ROOT / "configs/benchmarks/stress-v1.json"
DEFAULTS = dict(clients=(1, 2, 4, 8), duration=15.0, idle=2.0, timeout=10.0, interval=0.25,
                repeats=1, warmup=3.0, cooldown=3.0, min_available_mib=512, max_rss_mib=4096)


def stress_plan(profile=None, **overrides):
    if profile not in (None, "release-v1"):
        raise ValueError("Unknown stress profile")
    explicit = {k: v for k, v in overrides.items() if v is not None}
    if explicit.keys() - DEFAULTS.keys():
        raise ValueError("Unknown stress setting")
    if profile and explicit:
        raise ValueError("Fixed --profile cannot be combined with workload overrides; omit it for custom runs")
    config = json.loads(PROFILE_PATH.read_text()) if profile else dict(DEFAULTS)
    config.update(explicit)
    clients = config["clients"]
    if not clients or len(clients) > 16 or any(type(n) is not int or not 1 <= n <= 128 for n in clients):
        raise ValueError("clients must contain 1–16 levels, each between 1 and 128")
    if type(config["repeats"]) is not int or not 1 <= config["repeats"] <= 10:
        raise ValueError("repeats must be between 1 and 10")
    for name, lower, upper in (("duration", 0.1, 3600), ("idle", 0.1, 60), ("warmup", 0, 60),
                               ("cooldown", 0, 60), ("timeout", 0.1, 120), ("interval", 0.05, 60),
                               ("min_available_mib", 128, 1048576), ("max_rss_mib", 128, 1048576)):
        value = config[name]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be between {lower} and {upper}")
    return {**config, "protocol": PROTOCOL, "profile": profile or "custom", "clients": list(clients),
            "order": "alternating", "model_invoked": False,
            "workload": "browser_tabs list", "topology": "N stdio MCPs -> one bridge -> one Firefox",
            "load_model": "closed loop, one in-flight request per client, no think time",
            "schedule": [{"repeat": repeat + 1, "clients": n,
                          "order": "forward" if repeat % 2 == 0 else "reverse"}
                         for repeat in range(config["repeats"])
                         for n in (clients if repeat % 2 == 0 else list(reversed(clients)))]}


class SafetyStop(RuntimeError):
    pass


class StressCollector(ResourceCollector):
    """Sampled safety limits, including connect/setup; never raise in sampler thread."""
    def __init__(self, *args, min_available_mib, max_rss_mib, **kwargs):
        self.min_available = min_available_mib * 2**20
        self.max_rss = max_rss_mib * 2**20
        self.stop_reason = None
        self.load_gaps = []
        self.last_load_sample = None
        super().__init__(*args, **kwargs)

    def sample(self):
        super().sample()
        with self._lock:
            row = self._previous
            if row and row["phase"] == "load":
                if self.last_load_sample is not None:
                    gap = row["elapsed_sec"] - self.last_load_sample
                    if gap > 0.01:
                        self.load_gaps.append(gap)
                self.last_load_sample = row["elapsed_sec"]
            if not row or self.stop_reason or self.phase == "cleanup":
                return
            if row["system"]["available_memory_bytes"] < self.min_available:
                self.stop_reason = "host_available_memory_below_reserve"
            elif row["groups"]["all"]["rss"] > self.max_rss:
                self.stop_reason = "owned_rss_above_limit"

    def check(self):
        if self.stop_reason:
            raise SafetyStop(self.stop_reason)


def aggregate_levels(levels):
    """Run-level medians/ranges, not misleading pooled request percentiles."""
    result = []
    for count in sorted({r["clients"] for r in levels}):
        runs = [r for r in levels if r["clients"] == count and r.get("valid")]
        metrics = {}
        for name, extract in {
            "requests_per_sec": lambda r: r["successful_requests_per_sec"],
            "p95_latency_sec": lambda r: r["latency_sec_success"]["p95"],
            "p99_latency_sec": lambda r: r["latency_sec_success"]["p99"],
            "mean_cpu_percent_one_core": lambda r: r["resources"]["phase/load/all"]["mean_cpu_percent_one_core"],
            "mean_rss_bytes": lambda r: r["resources"]["phase/load/all"]["time_weighted_mean_rss_bytes"],
            "peak_rss_bytes": lambda r: r["resources"]["phase/load/all"]["sampled_peak_rss_bytes"],
        }.items():
            values = [extract(r) for r in runs]
            metrics[name] = {"median": statistics.median(values), "min": min(values), "max": max(values)} if values else None
        result.append({"clients": count, "valid_repeats": len(runs), **metrics})
    return result


def percentiles(values):
    ordered = sorted(values)
    return {f"p{p}": ordered[max(0, math.ceil(len(ordered) * p / 100) - 1)]
            if ordered else None for p in (50, 95, 99)}


class Client:
    """One sequential request stream per independent stdio process."""
    def __init__(self, process, timeout):
        self.process, self.timeout = process, timeout
        self.pending = queue.Queue()
        self.serial = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                if line.strip():
                    self.pending.put(json.loads(line))
        except (ValueError, OSError):
            pass
        finally:
            self.pending.put(None)

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()

    def request(self, method, params):
        self.serial += 1
        self.send({"jsonrpc": "2.0", "id": self.serial, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                message = self.pending.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise TimeoutError("MCP response timeout") from exc
            if message is None:
                raise EOFError("MCP closed")
            if message.get("id") == self.serial and ("result" in message or "error" in message):
                return message
            if "method" in message and "id" in message:
                self.send({"jsonrpc": "2.0", "id": message["id"],
                           "error": {"code": -32601, "message": "Unsupported"}})
            if time.monotonic() >= deadline:
                raise TimeoutError("MCP response timeout")

    def initialize(self):
        response = self.request("initialize", {"protocolVersion": "2024-11-05",
            "capabilities": {}, "clientInfo": {"name": "kitsune-stress", "version": "1"}})
        if "error" in response:
            raise ValueError("MCP initialize failed")
        self.metadata = response.get("result", {})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self.call()

    def call(self):
        return self.request("tools/call", {"name": "browser_tabs", "arguments": {"action": "list"}})


def failed(response):
    if "error" in response:
        return True
    result = response.get("result", {})
    if result.get("isError"):
        return True
    bodies = [result.get("structuredContent")]
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                bodies.append(json.loads(item["text"]))
            except (ValueError, KeyError):
                pass
    return any(isinstance(body, dict) and ("error" in body or body.get("ok") is False) for body in bodies)


def load_worker(client, index, start, deadline, directory):
    start.wait()
    samples, errors = [], {}
    path = directory / f"requests-{index}.jsonl"
    with path.open("x") as stream:
        path.chmod(0o600)
        while time.monotonic() < deadline[0]:
            before = time.monotonic()
            fatal = False
            try:
                response = client.call()
                error = "tool_error" if failed(response) else None
            except (TimeoutError, EOFError, OSError) as exc:
                error, fatal = type(exc).__name__, True
            elapsed = time.monotonic() - before
            samples.append((elapsed, error))
            if error:
                errors[error] = errors.get(error, 0) + 1
            stream.write(json.dumps({"client": index, "started_mono": before,
                                     "latency_sec": elapsed, "error": error}) + "\n")
            # Never reuse a timed-out stream: its late response could poison later calls.
            if fatal:
                break
    return samples, errors


def run_stress(*, execute=False, profile=None, kitsune_project=None, **overrides):
    plan = stress_plan(profile, **overrides)
    duration, idle, timeout, interval = (plan[k] for k in ("duration", "idle", "timeout", "interval"))
    if not execute:
        return {"mode": "stress_plan_only", **plan}
    project = Path(kitsune_project).expanduser().resolve() if kitsune_project else ROOT.parent / "kitsune"
    web_ext = ROOT / "node_modules/.bin/web-ext"
    if os.name != "posix" or not web_ext.exists() or not (project / "extension/manifest.json").exists():
        raise ValueError("Requires POSIX, npm ci, and a Kitsune checkout (--kitsune-project)")
    # No inherited Kitsune settings, model credentials or proxy configuration.
    env = {k: v for k, v in os.environ.items() if k in
           {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"}}
    env.update(PLAYWRIGHT_BROWSERS_PATH=str(ROOT / "artifacts/browsers"), PLAYWRIGHT_SKIP_BROWSER_GC="1")
    binary = subprocess.run(["node", "-e", "console.log(require('playwright').firefox.executablePath())"],
                            cwd=ROOT, env=env, capture_output=True, text=True, check=True, timeout=10)
    firefox = Path(binary.stdout.strip())
    if not firefox.is_file():
        raise ValueError("Private Firefox missing; run npm run setup:firefox")
    directory = ROOT / "artifacts/stress" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, mode=0o700)
    summary = {**plan, "run_dir": str(directory), "levels": [], "status": "running"}
    identity = source_revision(project)
    if profile and (not identity["revision"] or identity["dirty"]):
        raise ValueError("Release profile requires a clean, committed Kitsune checkout")
    def version(argv):
        return subprocess.run(argv, env=env, capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    manifest = {**plan, "kitsune_source": {**identity,
        "describe": version(["git", "-C", str(project), "describe", "--tags", "--always", "--dirty"])},
        "benchmark_source": benchmark_source(), "browser_binary": str(firefox),
        "resource_probe": "single-table-v1",
        "versions": {"firefox": version([str(firefox), "--version"]), "node": version(["node", "--version"]),
                     "uv": version(["uv", "--version"]), "python": sys.version, "psutil": psutil.__version__},
        "host": {"os": platform.platform(), "arch": platform.machine(), "logical_cpus": psutil.cpu_count(),
                 "physical_cpus": psutil.cpu_count(logical=False), "total_ram_bytes": psutil.virtual_memory().total,
                 "available_ram_bytes_at_start": psutil.virtual_memory().available,
                 "swap_used_bytes_at_start": psutil.swap_memory().used},
        "file_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
            ("kitsune_benchmark/stress.py", "kitsune_benchmark/stress_resources.py", "kitsune_benchmark/resources.py", "kitsune_benchmark/smoke.py",
             "kitsune_benchmark/adapter.py", "configs/benchmarks/stress-v1.json", "uv.lock", "package-lock.json")}}
    write_json(directory / "manifest.json", manifest)
    summary["manifest_path"] = str(directory / "manifest.json")
    try:
        # Fresh bridge/browser per level: no retained clients or accumulated browser state.
        for level, scheduled in enumerate(plan["schedule"]):
            count = scheduled["clients"]
            if source_revision(project) != identity:
                raise ValueError("Kitsune source changed during sweep")
            print(f"stress repeat {scheduled['repeat']}: {count} clients", file=sys.stderr, flush=True)
            stage = directory / f"{level:02d}-repeat-{scheduled['repeat']}-clients-{count}"
            stage.mkdir(mode=0o700)
            http, ws = private_ports()
            copy_extension(project / "extension", stage / "extension", ws)
            stage_env = {**env, "KITSUNE_HOME": str(stage / "bridge-home"), "KITSUNE_HTTP_PORT": str(http),
                         "KITSUNE_WS_PORT": str(ws), "KITSUNE_TOKEN": secrets.token_urlsafe(32)}
            with ExitStack() as stack:
                resources = stack.enter_context(StressCollector(stage, interval_sec=interval, probe=StressProcessProbe(),
                    min_available_mib=plan["min_available_mib"], max_rss_mib=plan["max_rss_mib"]))
                resources.check()
                resources.set_phase("setup")

                def spawn(argv, name, component, stdio=False):
                    log = stack.enter_context((stage / (name + ".log")).open("xb"))
                    os.chmod(log.name, 0o600)
                    process = subprocess.Popen(argv, cwd=stage, env=stage_env, start_new_session=True,
                        stdin=subprocess.PIPE if stdio else subprocess.DEVNULL,
                        stdout=subprocess.PIPE if stdio else log, stderr=log)
                    def cleanup():
                        terminate_group(process)
                        for pipe in (process.stdin, process.stdout):
                            if pipe:
                                pipe.close()
                    stack.callback(cleanup)
                    resources.register(ResourceRoot(process.pid, component, "kitsune"))
                    resources.check()
                    return process

                base = ["uv", "run", "--locked", "--project", str(project)]
                bridge = spawn(base + ["python", "-m", "kitsune.bridge"], "bridge", "bridge")
                await_bridge(http, stage_env["KITSUNE_TOKEN"], bridge)
                browser = spawn([str(web_ext), "run", "--no-config-discovery", "--no-input",
                    "--source-dir", str(stage / "extension"), "--artifacts-dir", str(stage / "web-ext"),
                    "--firefox", str(firefox), "--no-reload", "--start-url", "about:blank", "--args=-headless"],
                    "firefox", "browser_launcher")
                await_bridge(http, stage_env["KITSUNE_TOKEN"], browser, extension=True)
                resources.set_phase("connect")
                connected = [Client(spawn(base + ["kitsune"], f"client-{i}", "mcp", True), timeout)
                             for i in range(count)]
                before = time.monotonic()
                with ThreadPoolExecutor(max_workers=count) as pool:
                    responses = list(pool.map(lambda c: c.initialize(), connected))
                if any(failed(r) for r in responses):
                    raise ValueError("Client warmup failed; inspect stage logs")
                connect_seconds = time.monotonic() - before
                write_json(stage / "clients.json", [c.metadata for c in connected])
                resources.set_phase("warmup")
                def warm(c):
                    end = time.monotonic() + plan["warmup"]
                    while time.monotonic() < end:
                        resources.check()
                        if failed(c.call()):
                            raise ValueError("Load warmup failed")
                with ThreadPoolExecutor(max_workers=count) as pool:
                    list(pool.map(warm, connected))
                resources.check()
                resources.set_phase("idle")
                time.sleep(idle)
                resources.check()
                start, deadline = threading.Event(), [0.0]
                with ThreadPoolExecutor(max_workers=count) as pool:
                    futures = [pool.submit(load_worker, c, i, start, deadline, stage)
                               for i, c in enumerate(connected)]
                    try:
                        resources.set_phase("load")
                        before = time.monotonic()
                        deadline[0] = before + duration
                        start.set()
                        while not all(f.done() for f in futures):
                            if resources.stop_reason:
                                deadline[0] = 0
                            time.sleep(0.05)
                        outcomes = [f.result() for f in futures]
                        elapsed = time.monotonic() - before
                    finally:
                        # Release waiting workers even on interruption/setup failure.
                        deadline[0] = 0
                        start.set()
                resources.set_phase("cleanup")
            samples = [s for rows, _ in outcomes for s in rows]
            successes = [latency for latency, error in samples if error is None]
            errors = {}
            for _, counts in outcomes:
                for error, amount in counts.items():
                    errors[error] = errors.get(error, 0) + amount
            metrics = {}
            for key, bucket in resources.summary["metrics"].items():
                if key.startswith(("phase/load/", "phase/idle/")):
                    seconds = bucket["duration_sec"]
                    metrics[key] = {**bucket, "mean_cpu_percent_one_core":
                        100 * (bucket["observed_cpu_user_sec"] + bucket["observed_cpu_system_sec"]) / seconds if seconds else None}
            reasons = (["request_errors"] if errors else [])
            if resources.summary["sampling_errors"]:
                reasons.append("resource_sampling_errors")
            if resources.summary["unexpected_alive_at_stop"]:
                reasons.append("surviving_processes")
            if resources.stop_reason:
                reasons.append(resources.stop_reason)
            if any(not rows for rows, _ in outcomes):
                reasons.append("client_without_measured_requests")
            if source_revision(project) != identity:
                reasons.append("source_changed")
            cadence = {"median_sec": statistics.median(resources.load_gaps) if resources.load_gaps else None,
                       "max_sec": max(resources.load_gaps, default=None), "intervals": len(resources.load_gaps)}
            warnings = (["sampling_cadence_degraded"] if cadence["max_sec"] is None
                        or cadence["max_sec"] > max(1.0, interval * 4) else [])
            result = {**scheduled, "valid": not reasons, "invalid_reasons": reasons,
                      "measurement_warnings": warnings, "load_sample_cadence": cadence,
                      "initialize_and_probe_sec": connect_seconds, "elapsed_sec": elapsed,
                      "attempts": len(samples), "successes": len(successes), "errors": errors,
                      "error_rate": (len(samples) - len(successes)) / len(samples) if samples else None,
                      "successful_requests_per_sec": len(successes) / elapsed,
                      "latency_sec_all": percentiles([s[0] for s in samples]),
                      "latency_sec_success": percentiles(successes),
                      "per_client_attempts": [len(rows) for rows, _ in outcomes], "resources": metrics,
                      "resource_summary_path": str(stage / "resource-summary.json")}
            write_json(stage / "summary.json", result)
            summary["levels"].append(result)
            if reasons:
                summary.update(status="stopped" if resources.stop_reason else "failed", stopped_reason=reasons)
                break
            if level + 1 < len(plan["schedule"]):
                time.sleep(plan["cooldown"])
        else:
            summary["status"] = "completed"
    except SafetyStop as exc:
        summary.update(status="stopped", stopped_reason=str(exc), incomplete_level=scheduled,
                       incomplete_resource_summary_path=str(stage / "resource-summary.json"))
    except BaseException as exc:
        summary.update(status="failed", failure_type=type(exc).__name__)
        raise
    finally:
        summary["aggregates"] = aggregate_levels(summary["levels"])
        summary["completed_levels"] = len(summary["levels"])
        summary["requested_levels"] = len(plan["schedule"])
        path = directory / "summary.json"
        write_json(path, summary)
    return summary
