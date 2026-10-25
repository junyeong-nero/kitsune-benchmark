"""Stdio MCP relay: seed an isolated session, preserve native schemas/results.

Runs as an absolute-path script from the private Codex cwd. No model calls.
Harness tab queries are hidden from the model and counted separately. Their
wall time IS included in the agent run; this is not an uninstrumented latency
benchmark. Only newline-delimited stdio MCP servers are supported.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit


def tabs_from_result(target: str, result: dict) -> list[dict]:
    if result.get("isError"):
        raise ValueError("Tab inventory failed.")
    texts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
    if target == "playwright":
        tabs = []
        for text in texts:
            for line in text.splitlines():
                match = re.fullmatch(r"- (\d+): (\(current\) )?\[(.*)\]\((.*)\)", line)
                if match:
                    tabs.append({"id": int(match[1]), "active": bool(match[2]), "title": match[3], "url": match[4]})
    elif target == "kitsune":
        data = result.get("structuredContent")
        if not isinstance(data, dict) or not isinstance(data.get("tabs"), list):
            data = None
            for text in texts:
                try:
                    candidate = json.loads(text)
                    if isinstance(candidate, dict) and isinstance(candidate.get("tabs"), list):
                        data = candidate
                        break
                except ValueError:
                    continue
        # Kitsune >= 0.3.1 mirrors Playwright's browser_tabs: index-addressed, and `current` (the tab its tools
        # act on) plays the role of Playwright's "(current)" marker. Older Kitsune lists tab ids and `active`.
        tabs = [{"id": tab["index"], "active": bool(tab.get("current")), "title": tab.get("title") or "",
                 "url": tab["url"]} if "index" in tab else
                {"id": tab["id"], "active": tab["active"], "title": tab.get("title", ""), "url": tab["url"]}
                for tab in data["tabs"]] if data else []
    else:
        raise ValueError("Unknown MCP target.")
    if (not tabs or any(type(tab["id"]) is not int or type(tab["active"]) is not bool
                        or not isinstance(tab["url"], str) for tab in tabs)
            or len({t["id"] for t in tabs}) != len(tabs)):
        raise ValueError("Unrecognized native tab inventory schema.")
    return tabs


class NativeSession:
    def __init__(self, config: dict):
        self.config = config
        self.process = None
        self.pending = queue.Queue()
        self.serial = 0
        self.tab_indexed = False
        self.started_mono = time.monotonic()
        self.metadata = {"enabled_tools": config.get("enabled_tools", []), "tools_pages": []}
        self.evidence = {"setup_complete": False, "target": config.get("target"), "initial_tabs": [], "snapshots": [], "tab_calls": [],
                         "harness_calls": 0, "harness_seconds": 0.0,
                         "close_attempts": 0, "outside_navigation": 0}

    def start(self):
        self.process = subprocess.Popen(self.config["upstream"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=sys.stderr, bufsize=0)

        def read():
            try:
                for line in self.process.stdout:
                    if line.strip():
                        self.pending.put(json.loads(line))
            except (ValueError, OSError):
                pass
            finally:
                self.pending.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, message: dict):
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
        self.process.stdin.flush()

    def diagnostic(self, kind: str, **values):
        path = self.config.get("diagnostics_path")
        if path:
            entry = {"kind": kind, "time_utc": datetime.now(timezone.utc).isoformat(),
                     "offset_sec": time.monotonic() - self.started_mono, **values}
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def record_response(self, method: str, params: dict | None, message: dict,
                        role: str, request_id: str, started: float):
        result = message.get("result", {})
        texts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
        cached = False
        for text in texts:
            try:
                value = json.loads(text)
                cached = cached or (isinstance(value, dict) and value.get("_cached") is True)
            except ValueError:
                pass
        self.diagnostic("rpc_completed", request_id=request_id, role=role, method=method,
            tool=(params or {}).get("name"), action=(params or {}).get("arguments", {}).get("action"),
            duration_sec=time.monotonic() - started, cached=cached,
            serialized_response_bytes=len(json.dumps(message, ensure_ascii=False).encode()),
            response_text_chars=sum(len(text) for text in texts),
            response_text_bytes=sum(len(text.encode()) for text in texts),
            is_error="error" in message or result.get("isError") is True)
        if self.config.get("metadata_path") and method in {"initialize", "tools/list"}:
            if method == "initialize":
                self.metadata["initialize"] = result
            else:
                self.metadata["tools_pages"].append(result)
            self.write_private_json(Path(self.config["metadata_path"]), self.metadata)

    def request(self, method: str, params: dict | None = None, *, notify=None, role="harness") -> dict:
        self.serial += 1
        request_id = "personal-harness-" + str(self.serial)
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        started = time.monotonic()
        self.diagnostic("rpc_started", request_id=request_id, role=role, method=method,
                        tool=(params or {}).get("name"), action=(params or {}).get("arguments", {}).get("action"))
        self.send(request)
        deadline = time.monotonic() + 60
        while True:
            try:
                message = self.pending.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise ValueError("Native MCP request timed out.") from exc
            if message is None:
                raise ValueError("Native MCP closed before replying.")
            if message.get("id") == request_id and ("result" in message or "error" in message):
                self.record_response(method, params, message, role, request_id, started)
                return message
            if "method" in message and "id" not in message:
                if notify:
                    notify(message)
            elif "method" in message:
                self.send({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32601, "message": "Server-initiated requests unsupported in benchmark."}})
            else:
                raise ValueError("Unexpected native MCP response.")
            if time.monotonic() >= deadline:
                raise ValueError("Native MCP request timed out.")

    def tool(self, name: str, arguments: dict) -> dict:
        started = time.monotonic()
        try:
            result = self.request("tools/call", {"name": name, "arguments": arguments})
            self.evidence["harness_calls"] += 1
            if "error" in result or result.get("result", {}).get("isError"):
                raise ValueError("Harness browser tool failed.")
            return result["result"]
        finally:
            self.evidence["harness_seconds"] += time.monotonic() - started

    def inventory(self) -> list[dict]:
        result = self.tool("browser_tabs", {"action": "list"})
        texts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
        self.tab_indexed = '"index"' in json.dumps(result.get("structuredContent")) + "".join(texts)
        return tabs_from_result(self.config["target"], result)

    def wait_inventory(self, predicate, timeout: float = 10) -> list[dict]:
        deadline = time.monotonic() + timeout
        while True:
            try:
                tabs = self.inventory()
                if predicate(tabs):
                    return tabs
            except ValueError:
                if time.monotonic() >= deadline:
                    raise
            if time.monotonic() >= deadline:
                raise ValueError("Native tab state did not settle before setup deadline.")
            started = time.monotonic()
            time.sleep(0.1)
            elapsed = time.monotonic() - started
            self.evidence["harness_seconds"] += elapsed
            self.diagnostic("readiness_wait", duration_sec=elapsed)

    def prepare(self):
        if self.evidence["setup_complete"]:
            return
        setup_started = time.monotonic()
        self.diagnostic("setup_started")
        # Provisioning uses only the same native UI tools. No JS evaluation,
        # browser debugging connection or extra capability is given to the model.
        tabs = self.wait_inventory(lambda tabs: len(tabs) >= 1)
        if len(tabs) != 1:
            raise ValueError("Expected exactly one initial tab in a fresh profile.")
        self.tool("browser_navigate", {"url": self.config["bootstrap_url"]})
        self.tool("browser_navigate", {"url": self.config["urls"][0]})
        for url in self.config["urls"][1:]:
            self.tool("browser_tabs", {"action": "new", "url": url})
        tabs = self.wait_inventory(lambda tabs: sorted(t["url"] for t in tabs) == sorted(self.config["urls"]))
        desired = self.config["urls"][self.config["active_index"]]
        chosen = [tab for tab in tabs if tab["url"] == desired]
        if len(chosen) != 1 or sorted(t["url"] for t in tabs) != sorted(self.config["urls"]):
            raise ValueError("Session seed URLs differ from specification.")
        field = "index" if self.config["target"] == "playwright" or self.tab_indexed else "tab_id"
        self.tool("browser_tabs", {"action": "select", field: chosen[0]["id"]})
        tabs = self.wait_inventory(lambda tabs: any(tab["url"] == desired and tab["active"] for tab in tabs))
        if not any(tab["url"] == desired and tab["active"] for tab in tabs):
            raise ValueError("Active starting tab was not established.")
        self.evidence.update(setup_complete=True, initial_tabs=tabs, snapshots=[tabs])
        self.save()
        self.diagnostic("setup_completed", duration_sec=time.monotonic() - setup_started)

    @staticmethod
    def write_private_json(path: Path, value: dict):
        temporary = path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)

    def save(self):
        self.write_private_json(Path(self.config["evidence_path"]), self.evidence)

    def forward(self, message: dict, emit) -> None:
        method = message.get("method")
        if method in {"tools/list", "tools/call"}:
            self.prepare()
        if "id" not in message:
            self.send(message)
            return
        if method == "tools/call":
            arguments = message.get("params", {}).get("arguments", {})
            name = message.get("params", {}).get("name")
            if name == "browser_tabs" and arguments.get("action") == "close":
                self.evidence["close_attempts"] += 1
            url = arguments.get("url")
            if isinstance(url, str):
                parsed = urlsplit(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                if url != "about:blank" and origin != self.config["origin"]:
                    self.evidence["outside_navigation"] += 1
                    # Do not perform known out-of-fixture navigations.
                    self.save()
                    emit({"jsonrpc": "2.0", "id": message["id"], "result": {
                        "isError": True, "content": [{"type": "text", "text": "Only local fixture navigation is allowed."}]}})
                    return
        result = self.request(method, message.get("params"), notify=emit, role="agent")
        if method == "tools/call":
            # Inventory isn't sent to the model. Explicit separate harness counts
            # prevent attributing these calls to the agent's tool-use efficiency.
            self.evidence["snapshots"].append(self.inventory())
            # The call behind each snapshot, so graders can follow starting tabs by identity.
            call = {"tool": name, "error": "error" in result or result.get("result", {}).get("isError") is True}
            for key in ("action", "index", "tab_id", "url"):
                value = arguments.get(key)
                call[key] = int(value) if isinstance(value, float) and value.is_integer() else value
            self.evidence["tab_calls"].append(call)
            self.evidence["tab_ids"] = "index" if self.config["target"] == "playwright" or self.tab_indexed else "stable"
            self.save()
        emit({**result, "id": message["id"]})

    def close(self):
        if self.process:
            try:
                self.process.stdin.close()  # Let a nested relay/native server clean up on EOF.
            except OSError:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            self.reader.join(timeout=5)
            self.process.stdout.close()


def main() -> int:
    config = json.loads(Path(sys.argv[1]).read_text())
    session = NativeSession(config)

    def emit(message):
        print(json.dumps(message, ensure_ascii=False), flush=True)

    try:
        session.start()
        for line in sys.stdin:
            if line.strip():
                session.forward(json.loads(line), emit)
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        session.evidence["error"] = "native_session_setup_or_inventory_failed"
        session.save()
        print("Personal fixture MCP setup/inventory failed; inspect private artifacts.", file=sys.stderr)
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
