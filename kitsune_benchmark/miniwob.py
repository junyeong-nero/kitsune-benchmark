"""Pinned MiniWoB++ HTML tasks and original client-side reward telemetry.

This is a Firefox/MCP UI-only pilot, not the standard Chrome/Gym benchmark.
Telemetry comes from upstream core.endEpisode, never the agent's final answer.
It is not a cryptographically isolated anti-cheating evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .adapter import with_claude_overrides
from .smoke import ROOT, TARGETS, run_pair
from .specs import Task

# taskset-v1.2: Kitsune v0.3.1 publishes Playwright MCP 0.0.83's 25 default tools under the same names, so both
# targets get that set minus the two code-execution tools (browser_evaluate, browser_run_code_unsafe), which
# could rewrite page state or rewards. browser_emulate_media answers not_supported on Kitsune.
CORE_TOOLS = ("browser_close", "browser_resize", "browser_console_messages", "browser_handle_dialog",
    "browser_emulate_media", "browser_file_upload", "browser_drop", "browser_find",
    "browser_fill_form", "browser_press_key", "browser_type", "browser_navigate", "browser_navigate_back",
    "browser_network_requests", "browser_network_request", "browser_take_screenshot",
    "browser_snapshot", "browser_click", "browser_drag", "browser_hover", "browser_select_option",
    "browser_tabs", "browser_wait_for")
UI_TOOLS = {"playwright": CORE_TOOLS, "kitsune": CORE_TOOLS}


def config() -> dict:
    return json.loads((ROOT / "configs/benchmarks/miniwob.json").read_text())


def verify_source(source: Path, revision: str) -> None:
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=10, check=True)
    dirty = subprocess.run(["git", "-C", str(source), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=10, check=True)
    if commit.stdout.strip() != revision or dirty.stdout.strip():
        raise ValueError("MiniWoB checkout must match the pinned clean revision.")


def fetch_source(spec: dict) -> Path:
    source = ROOT / spec["source_directory"]
    if not source.exists():
        source.mkdir(parents=True)
        for args in (["git", "init"], ["git", "remote", "add", "origin", spec["source_repository"]],
                     ["git", "fetch", "--depth", "1", "origin", spec["source_revision"]],
                     ["git", "checkout", "--detach", "FETCH_HEAD"]):
            subprocess.run(args, cwd=source, capture_output=True, text=True, timeout=90, check=True)
    verify_source(source, spec["source_revision"])
    return source


def bootstrap(token: str, task_id: str, seed: int, timeout_ms: int) -> str:
    values = json.dumps({"token": token, "task_id": task_id, "seed": seed, "timeout_ms": timeout_ms})
    return """<script>
(() => {
  'use strict';
  const conf = CONFIG;
  Math.seedrandom(String(conf.seed));
  core.EPISODE_MAX_TIME = conf.timeout_ms;
  const post = (kind, extra) => navigator.sendBeacon('/__bench/' + conf.token + '/event',
    new Blob([JSON.stringify({kind, task_id: conf.task_id, seed: conf.seed,
      timer_budget_ms: core.EPISODE_MAX_TIME, ...extra})], {type: 'application/json'}));
  const start = core.startEpisodeReal;
  core.startEpisodeReal = function(...args) {
    const result = start.apply(this, args);
    post('start', {query: core.getUtterance()});
    return result;
  };
  const end = core.endEpisode;
  core.endEpisode = function(...args) {
    const wasRunning = core.EP_TIMER !== null;
    const result = end.apply(this, args);
    if (wasRunning && window.WOB_DONE_GLOBAL === true) {
      post('end', {done: true, raw_reward: WOB_RAW_REWARD_GLOBAL,
        reward: WOB_REWARD_GLOBAL, reason: WOB_REWARD_REASON,
        elapsed_ms: Date.now() - core.ept0});
    }
    return result;
  };
})();
</script>""".replace("CONFIG", values)


@dataclass
class Trial:
    task_id: str
    seed: int
    timeout_ms: int
    page_loads: int = 0
    starts: int = 0
    errors: int = 0
    terminal: dict | None = None
    received: threading.Event = field(default_factory=threading.Event)

    def event(self, data: dict) -> bool:
        if (data.get("task_id") != self.task_id or data.get("seed") != self.seed
                or data.get("timer_budget_ms") != self.timeout_ms):
            self.errors += 1
            return False
        if data.get("kind") == "start":
            self.starts += 1
            return True
        if data.get("kind") != "end" or data.get("done") is not True:
            self.errors += 1
            return False
        for key in ("reward", "raw_reward"):
            value = data.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not -1 <= value <= 1:
                self.errors += 1
                return False
        if self.terminal is not None:
            self.errors += 1
            return False
        self.terminal = {key: data.get(key) for key in ("done", "reward", "raw_reward", "reason", "elapsed_ms")}
        self.received.set()
        return True

    def evaluate(self, execution_status: str) -> dict:
        valid_trace = execution_status == "completed_unscored"
        valid_episode = self.page_loads == 1 and self.starts == 1 and self.errors == 0
        scorable = valid_trace and valid_episode
        return {"benchmark": "MiniWoB++", "track": "firefox-mcp-ui-pilot",
                "task_id": self.task_id, "seed": self.seed, "episode_timeout_ms": self.timeout_ms,
                "page_loads": self.page_loads, "episode_starts": self.starts,
                "telemetry_errors": self.errors, "scorable": scorable,
                "task_success": bool(self.terminal and self.terminal["raw_reward"] > 0) if scorable else None,
                "outcome": "official_terminal_reward" if self.terminal else "no_terminal_reward",
                "official_reward": self.terminal,
                "integrity": "Client-side upstream reward instrumentation; not hardened against malicious agents.",
                "not_standard_gym_score": True}


class BenchmarkServer:
    def __init__(self, source: Path, spec: dict) -> None:
        self.source = source
        self.spec = spec
        self.trials: dict[str, Trial] = {}
        self.by_target: dict[str, str] = {}
        self.lock = threading.RLock()
        self.http: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> BenchmarkServer:
        controller = self

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def list_directory(self, path):
                self.send_error(404)
                return None

            def do_GET(self):
                parsed = urlsplit(self.path)
                if parsed.path == "/miniwob/" + controller.spec["task_id"] + ".html":
                    token = parse_qs(parsed.query).get("trial", [None])[0]
                    with controller.lock:
                        trial = controller.trials.get(token)
                        if trial is None:
                            self.send_error(404)
                            return
                        trial.page_loads += 1
                        original = (controller.source / "miniwob/html/miniwob" / (trial.task_id + ".html")).read_text()
                        injection = bootstrap(token, trial.task_id, trial.seed, trial.timeout_ms)
                        payload = original.replace("</body>", injection + "\n</body>").encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(payload)
                elif parsed.path.startswith("/__bench/"):
                    self.send_error(405)
                else:
                    super().do_GET()

            def do_POST(self):
                parts = urlsplit(self.path).path.split("/")
                if len(parts) != 4 or parts[1] != "__bench" or parts[3] != "event":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 16384:
                        raise ValueError()
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError()
                except (ValueError, OSError):
                    self.send_error(400)
                    return
                with controller.lock:
                    trial = controller.trials.get(parts[2])
                    accepted = trial is not None and trial.event(data)
                self.send_response(204 if accepted else 400)
                self.end_headers()

        self.http = ThreadingHTTPServer(("127.0.0.1", 0),
            partial(Handler, directory=str(self.source / "miniwob/html")))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        return self

    def begin(self, target: str) -> Task:
        assert self.http is not None
        token = secrets.token_hex(16)
        trial = Trial(self.spec["task_id"], self.spec["seed"], self.spec["episode_timeout_ms"])
        with self.lock:
            self.trials[token] = trial
            self.by_target[target] = token
        url = f"http://127.0.0.1:{self.http.server_port}/miniwob/{trial.task_id}.html?trial={token}"
        return Task(f"miniwob-{trial.task_id}-seed-{trial.seed}",
            f"Open {url} in a new tab. Click START exactly once, then follow the task instruction "
            "displayed on the page. Stop after completing the task. Do not restart, reload, or retry the episode. "
            "Use only the provided UI observation and interaction tools. Do not inspect or modify source code, "
            "reward variables, timers, or evaluation instrumentation. Report what you did concisely; "
            "the external evaluator, not your final answer, determines success.")

    def evaluate(self, target: str, result: dict) -> dict:
        with self.lock:
            trial = self.trials[self.by_target[target]]
        trial.received.wait(timeout=0.5)
        with self.lock:
            return trial.evaluate(result["execution_status"])

    def __exit__(self, *args) -> None:
        if self.http:
            self.http.shutdown()
            self.http.server_close()
        if self.thread:
            self.thread.join(timeout=3)


def run_benchmark(*, execute: bool = False, fetch: bool = False,
                  kitsune_project: str | None = None, executable: str = "codex",
                  harness: str = "codex", claude_model: str | None = None,
                  max_budget_usd_per_run: float | None = None, targets: tuple[str, ...] = TARGETS,
                  codex_model: str | None = None) -> dict:
    spec = with_claude_overrides(config(), claude_model, max_budget_usd_per_run, codex_model)
    source = fetch_source(spec) if fetch else ROOT / spec["source_directory"]
    if not execute:
        return {"mode": "benchmark_plan_only", "model_invoked": False, "config": spec,
                "source_present": source.exists(), "ui_tools": UI_TOOLS}
    verify_source(source, spec["source_revision"])
    with BenchmarkServer(source, spec) as benchmark:
        result = run_pair(execute=True, kitsune_project=kitsune_project, executable=executable,
            experiment_spec=spec, artifact_scope="miniwob", task_for_target=benchmark.begin,
            evaluate=benchmark.evaluate, enabled_tools=UI_TOOLS, harness=harness, targets=targets)
    result["benchmark_config"] = spec
    result["upstream_task_sha256"] = hashlib.sha256(
        (source / "miniwob/html/miniwob" / (spec["task_id"] + ".html")).read_bytes()).hexdigest()
    path = Path(result["pair_dir"]) / "benchmark-summary.json"
    with path.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    path.chmod(0o600)
    return result
