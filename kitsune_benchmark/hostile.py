"""Hostile-UI capability matrix: which tool strategies real-web components accept, per MCP server. No model calls.

Components are hand-written defense pages (`hostile_pages.py`, one mechanism each) and real UI libraries bundled
locally (`fixtures/hostile`, built into artifacts/hostile/bundle). For every component, strategy and target, a fresh
page is opened, the strategy's tool calls are made through the MCP server, and success is read from the fixture
server: the component's own handler reports it. Tool responses never decide success. Every input event the page
receives is counted with its isTrusted, so a failure shows which events arrived.

Plan-only by default. `--execute` starts isolated browsers; it never calls a model or uses quota. Strategies that
need OS input (browser_trusted_click) run only with --trusted, which also needs --headed: the real pointer moves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
import json
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time

from .hostile_pages import FRAME_PAY, PAGES
from .smoke import ROOT, TARGETS, source_revision

CATALOG = ROOT / "tasks/hostile/catalog.json"
BUNDLE = ROOT / "artifacts/hostile/bundle"
TRUSTED_TOOLS = {"browser_trusted_click"}
READY_TIMEOUT = 8.0
SETTLE_SEC = 2.0

REPORT_JS = """(() => {
  const token = location.pathname.split('/')[2];
  const counts = {};
  const types = ['pointerdown','pointerup','pointermove','pointerover','pointerenter','mousedown','mouseup','mousemove',
    'mouseover','mouseenter','click','dblclick','contextmenu','keydown','keyup','beforeinput','input','change','focus',
    'dragstart','drop'];
  let dirty = false;
  for (const t of types) window.addEventListener(t, e => {
    // Pointer events also record pointerType ("" when a synthetic event leaves it unset).
    const k = t + (e.isTrusted ? ':trusted' : ':synthetic') + (t.startsWith('pointer') ? ':' + (e.pointerType || 'none') : '');
    counts[k] = (counts[k] || 0) + 1; dirty = true;
  }, true);
  const send = (kind, detail) => navigator.sendBeacon('/t/' + token + '/event',
    new Blob([JSON.stringify({kind, detail: detail === undefined ? null : detail, events: counts})], {type: 'application/json'}));
  window.__hostile = {done: d => send('done', d), progress: d => send('progress', d), ready: () => send('ready')};
  setInterval(() => { if (dirty) { dirty = false; send('trace'); } }, 250);
  if (!document.currentScript.dataset.manualReady) addEventListener('load', () => window.__hostile.ready());
})();"""


def catalog() -> dict:
    spec = json.loads(CATALOG.read_text())
    if spec.get("schema_version") != 1:
        raise ValueError("Expected hostile catalog schema v1.")
    ids = [c["id"] for c in spec["components"]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate hostile component.")
    for c in spec["components"]:
        if c["layer"] not in ("catalog", "library"):
            raise ValueError(f"Unknown layer: {c['id']}")
        if c["layer"] == "catalog" and c["id"] not in PAGES:
            raise ValueError(f"Catalog component without a page: {c['id']}")
        for name in c["strategies"]:
            steps = spec["strategies"].get(name)
            if steps is None:
                raise ValueError(f"Unknown strategy {name} in {c['id']}")
            for ref in re.findall(r'"@(\w+)"', json.dumps(steps)):
                if ref not in c["targets"]:
                    raise ValueError(f"{c['id']}/{name} needs target {ref}")
            for value in re.findall(r'"\$(\w+)"', json.dumps(steps)):
                if value not in c.get("values", {}):
                    raise ValueError(f"{c['id']}/{name} needs value {value}")
    return spec


def needs_trusted(steps: list[dict]) -> bool:
    return any(step.get("tool") in TRUSTED_TOOLS for step in steps)


def plan(component_ids: list[str] | None = None, targets: tuple[str, ...] = TARGETS, trusted: bool = False) -> list[dict]:
    spec = catalog()
    components = spec["components"]
    if component_ids:
        known = {c["id"] for c in components}
        if set(component_ids) - known:
            raise ValueError("Unknown hostile component.")
        components = [c for c in components if c["id"] in component_ids]
    cells = []
    for target in targets:
        for c in components:
            for name in c["strategies"]:
                steps = spec["strategies"][name]
                if needs_trusted(steps) and (not trusted or target != "kitsune"):
                    continue  # OS input: Kitsune only, and only when the operator opted in
                cells.append({"target": target, "component": c["id"], "layer": c["layer"], "strategy": name})
    return cells


# ---- Fixture server ----------------------------------------------------------------------------------------------

@dataclass
class Trial:
    component: str
    ready: bool = False
    done: dict | None = None
    progress: list = field(default_factory=list)
    events: dict = field(default_factory=dict)


class HostileServer:
    def __init__(self):
        self.trials: dict[str, Trial] = {}
        self.lock = threading.RLock()
        self.http: ThreadingHTTPServer | None = None

    def __enter__(self):
        controller = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, body=b"", content_type="text/html; charset=utf-8"):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/__hostile/report.js":
                    return self.reply(200, REPORT_JS.encode(), "text/javascript")
                if path.startswith("/bundle/") and re.fullmatch(r"/bundle/lib-[a-z0-9-]+\.js", path):
                    file = BUNDLE / path.rsplit("/", 1)[1]
                    return self.reply(200, file.read_bytes(), "text/javascript") if file.is_file() else self.reply(404)
                parts = path.split("/")
                if len(parts) >= 5 and parts[1] == "t":
                    with controller.lock:
                        trial = controller.trials.get(parts[2])
                    if trial is None:
                        return self.reply(404)
                    if parts[3] == "c" and parts[4] == trial.component:
                        return self.reply(200, page(trial.component).encode())
                    if parts[3] == "frame" and parts[4] == "pay":
                        return self.reply(200, shell(*FRAME_PAY).encode())
                self.reply(404)

            def do_POST(self):
                parts = self.path.split("/")
                if len(parts) != 4 or parts[1] != "t" or parts[3] != "event":
                    return self.reply(404)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    data = json.loads(self.rfile.read(min(length, 65536)))
                except ValueError:
                    return self.reply(400)
                with controller.lock:
                    trial = controller.trials.get(parts[2])
                    if trial is None or not isinstance(data, dict):
                        return self.reply(404)
                    kind = data.get("kind")
                    if isinstance(data.get("events"), dict):
                        trial.events = data["events"]
                    if kind == "ready":
                        trial.ready = True
                    elif kind == "done" and trial.done is None:
                        trial.done = data.get("detail") or {}
                    elif kind == "progress":
                        trial.progress = (trial.progress + [data.get("detail")])[-5:]
                self.reply(204)

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *args):
        if self.http:
            self.http.shutdown()
            self.http.server_close()

    def begin(self, component: str) -> tuple[str, str]:
        token = secrets.token_hex(12)
        with self.lock:
            self.trials[token] = Trial(component)
        return token, f"http://127.0.0.1:{self.http.server_port}/t/{token}/c/{component}"

    def state(self, token: str) -> Trial:
        with self.lock:
            return self.trials[token]


def shell(title: str, body: str, script: str, *, manual_ready: bool = False, bundle: str | None = None) -> str:
    ready = ' data-manual-ready="1"' if manual_ready else ""
    tail = f'<script src="/bundle/{bundle}.js"></script>' if bundle else f"<script>{script}</script>"
    return (f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{escape(title)}</title>'
            f'<script src="/__hostile/report.js"{ready}></script>'
            '<style>body{font:16px system-ui;margin:24px}button{font:inherit;padding:6px 12px}</style>'
            f'<body><main><h1>{escape(title)}</h1>{body}</main>{tail}</body></html>')


def page(component: str) -> str:
    if component in PAGES:
        return shell(*PAGES[component])
    return shell(component, '<div id="root"></div>', "", manual_ready=True, bundle=component)


# ---- Running a strategy through an MCP server --------------------------------------------------------------------

REF = re.compile(r'- (?P<role>[a-z]+)(?: "(?P<name>(?:[^"\\]|\\.)*)")?[^\n]*?\[ref=(?P<ref>[^\]\s]+)\]')


def result_text(result: dict) -> str:
    return "\n".join(c.get("text", "") for c in (result.get("content") or []) if c.get("type") == "text")


def resolve(snapshot: str, spec: dict) -> str | None:
    """The ref of the first element with one of spec's roles whose name contains spec's name."""
    want = spec["name"].lower()
    for match in REF.finditer(snapshot.replace('\\"', '"').replace("\\n", "\n")):
        if match["role"] in spec["role"] and want in (match["name"] or "").lower():
            return match["ref"]
    return None


def substitute(value, values: dict, refs: dict):
    if isinstance(value, str):
        if value.startswith("@"):
            return refs[value[1:]]
        if value.startswith("$"):
            return values[value[1:]]
        return value
    if isinstance(value, list):
        return [substitute(v, values, refs) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, values, refs) for k, v in value.items()}
    return value


def expand(steps: list[dict], values: dict) -> list[dict]:
    out = []
    for step in steps:
        if "keys" in step:
            text = values[step["keys"][1:]]
            out += [{"tool": "browser_press_key", "args": {"key": ch}} for ch in text]
        else:
            out += [{"tool": step["tool"], "args": step["args"]}] * step.get("repeat", 1)
    return out


class Runner:
    def __init__(self, session, server: HostileServer, spec: dict):
        self.session, self.server, self.spec = session, server, spec
        self.opened = False

    def call(self, name: str, args: dict) -> dict:
        started = time.monotonic()
        response = self.session.request("tools/call", {"name": name, "arguments": args})
        result = response.get("result") or {}
        text = result_text(result)
        error = response.get("error") or (result.get("isError") and text[:300])
        return {"tool": name, "ok": not error, "error": error or None, "chars": len(text),
                "ms": round((time.monotonic() - started) * 1000), "text": text}

    def open(self, url: str) -> dict:
        if not self.opened:
            self.opened = True
            return self.call("browser_tabs", {"action": "new", "url": url})
        return self.call("browser_navigate", {"url": url})

    def targets(self, needed: set[str], component: dict) -> tuple[dict, str | None]:
        snapshot = self.call("browser_snapshot", {})["text"]
        refs = {}
        for name in needed:
            ref = resolve(snapshot, component["targets"][name])
            if ref is None:
                return refs, name
            refs[name] = ref
        return refs, None

    def run(self, component: dict, strategy: str) -> dict:
        token, url = self.server.begin(component["id"])
        record = {"component": component["id"], "layer": component["layer"], "mechanism": component["mechanism"],
                  "strategy": strategy, "steps": []}
        opened = self.open(url)
        deadline = time.monotonic() + READY_TIMEOUT
        while not self.server.state(token).ready and time.monotonic() < deadline:
            time.sleep(0.1)
        if not opened["ok"] or not self.server.state(token).ready:
            return {**record, "outcome": "page_not_ready", "accepted": None}
        values = component.get("values", {})
        for step in expand(self.spec["strategies"][strategy], values):
            needed = set(re.findall(r'"@(\w+)"', json.dumps(step["args"])))
            refs, missing = self.targets(needed, component) if needed else ({}, None)
            if missing:
                record["steps"].append({"tool": step["tool"], "ok": False, "error": f"target_not_found:{missing}"})
                break
            args = substitute(step["args"], values, refs)
            if step["tool"] in ("browser_click", "browser_hover", "browser_type", "browser_select_option"):
                args.setdefault("element", next(iter(component["targets"][n]["name"] for n in needed), "element"))
            if step["tool"] == "browser_drag":
                args.update(startElement=component["targets"]["source"]["name"], endElement=component["targets"]["dest"]["name"])
            done = self.call(step["tool"], args)
            done.pop("text")
            record["steps"].append(done)
            if self.server.state(token).done is not None:
                break
        deadline = time.monotonic() + SETTLE_SEC
        while self.server.state(token).done is None and time.monotonic() < deadline:
            time.sleep(0.1)
        state = self.server.state(token)
        record.update(accepted=state.done is not None, done=state.done, progress=state.progress, events=state.events,
                      outcome="accepted" if state.done is not None else
                      ("target_not_found" if any(str(s.get("error", "")).startswith("target_not_found") for s in record["steps"])
                       else "tool_error" if any(not s["ok"] for s in record["steps"]) else "not_accepted"))
        return record


def run_hostile(*, execute: bool = False, component_ids: list[str] | None = None, targets: tuple[str, ...] = TARGETS,
                kitsune_project: str | None = None, headed: bool = False, trusted: bool = False,
                out: str | None = None) -> dict:
    if trusted and not headed:
        raise ValueError("--trusted needs --headed: OS input needs a visible browser window.")
    cells = plan(component_ids, targets, trusted)
    if not execute:
        return {"mode": "hostile_plan_only", "model_invoked": False, "cells": len(cells),
                "components": len({c["component"] for c in cells}), "targets": list(targets), "trusted": trusted,
                "bundle_built": BUNDLE.is_dir(), "plan": cells,
                "next": "Build the library bundles (npm --prefix fixtures/hostile ci --ignore-scripts && npm --prefix "
                        "fixtures/hostile run build), then run with --execute. No model is called."}
    if not BUNDLE.is_dir():
        raise ValueError("Library bundles missing: npm --prefix fixtures/hostile ci --ignore-scripts && "
                         "npm --prefix fixtures/hostile run build")
    from .native import kitsune_server, playwright_server
    from .personal_session import NativeSession
    spec = catalog()
    by_id = {c["id"]: c for c in spec["components"]}
    project = Path(kitsune_project).expanduser().resolve() if kitsune_project else ROOT.parent / "kitsune"
    source = source_revision(project) if "kitsune" in targets else None
    out_dir = Path(out or ROOT / "artifacts/hostile/runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with HostileServer() as server:
        for target in targets:
            mine = [c for c in cells if c["target"] == target]
            with tempfile.TemporaryDirectory(prefix=f"hostile-{target}-", dir="/tmp") as folder:
                launcher = (playwright_server(folder, headed=headed) if target == "playwright" else
                            kitsune_server(folder, project, headed=headed, caps="core,browse" if trusted else None))
                with launcher as upstream:
                    session = NativeSession({"target": target, "upstream": upstream, "bootstrap_url": "about:blank",
                                             "urls": ["about:blank"], "active_index": 0,
                                             "evidence_path": folder + "/evidence.json", "origin": "http://127.0.0.1"})
                    try:
                        session.start()
                        session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                                       "clientInfo": {"name": "hostile-matrix", "version": "1"}})
                        session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                        runner = Runner(session, server, spec)
                        for cell in mine:
                            try:
                                record = runner.run(by_id[cell["component"]], cell["strategy"])
                            except (OSError, ValueError) as error:
                                record = {**cell, "outcome": "runner_error", "accepted": None, "error": str(error)[:300]}
                            record["target"] = target
                            results.append(record)
                            print(f"{target:10} {cell['component']:22} {cell['strategy']:24} {record['outcome']}", flush=True)
                    finally:
                        session.close()
    after = source_revision(project) if "kitsune" in targets else None
    if after != source:
        raise ValueError("The Kitsune checkout changed during the matrix; rerun on a pinned checkout.")
    summary = {"mode": "hostile_executed", "model_invoked": False, "suite": spec["suite"], "targets": list(targets),
               "headed": headed, "trusted": trusted, "kitsune_project": str(project), "kitsune_source": source,
               "benchmark_source": source_revision(ROOT), "results": results,
               "matrix": matrix(results)}
    (out_dir / "results.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    (out_dir / "matrix.md").write_text(summary["matrix"] + "\n")
    summary["out_dir"] = str(out_dir)
    return summary


def matrix(results: list[dict]) -> str:
    """Markdown: one row per component and strategy, a column per target."""
    targets = sorted({r["target"] for r in results}, key=lambda t: TARGETS.index(t) if t in TARGETS else 9)
    cell = {(r["component"], r["strategy"], r["target"]): r for r in results}
    rows = ["| Component | Mechanism | Strategy | " + " | ".join(targets) + " |",
            "| --- | --- | --- | " + " | ".join("---" for _ in targets) + " |"]
    seen = []
    for r in results:
        key = (r["component"], r["strategy"])
        if key in seen:
            continue
        seen.append(key)
        marks = []
        for t in targets:
            x = cell.get((*key, t))
            marks.append("–" if x is None else "✅" if x.get("accepted") else f"❌ {x.get('outcome')}")
        rows.append(f"| {key[0]} | {r.get('mechanism', '')} | {key[1]} | " + " | ".join(marks) + " |")
    return "\n".join(rows)
