"""Stdio MCP relay of the full-native track (#109): the personal/gallery relay, unchanged, plus Kitsune's gateway.

personal_session.py is frozen in each taskset tag, so this subclass adds what only full-native runs need. Their
`gateway` arm publishes browser_tools_call, which runs the tool it names, and both arms may publish Kitsune's container
tools, whose commands carry their own URLs. So the relay:

- blocks out-of-fixture navigation for every `url` in a call's arguments, nested ones included;
- counts a browser_tools_call as the tool it runs: a gateway `browser_tabs close` is a close attempt, and its tab call
  is recorded under the tool it ran, with `via: "browser_tools_call"`, for the custody grader;
- waits up to AGENT_REQUEST_SECONDS for the agent's calls, not the frozen relay's 60 s, because Kitsune's containers
  run for minutes.

The call is forwarded to the native server unchanged. Runs as an absolute-path script. No model calls.
"""
from __future__ import annotations

import json
from pathlib import Path
import queue
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kitsune_benchmark.personal_session import NativeSession  # noqa: E402

# Kitsune's gateway tool (KITSUNE_PUBLISH narrower than KITSUNE_CAPS): runs the tool it names with that tool's arguments.
GATEWAY_CALL = "browser_tools_call"
# The relay's answer to an out-of-fixture navigation, the same text as the frozen relay's.
OUTSIDE_NAVIGATION = "Only local fixture navigation is allowed."
# How long the relay waits for a native reply. Kitsune times a batch, parallel, workflow or resume call out after
# container_request_seconds (waits.py): its 300 s deadline plus 15 s to settle plus 15 s for the partial report.
AGENT_REQUEST_SECONDS = 330
HARNESS_REQUEST_SECONDS = 60  # the frozen relay's limit, kept for the harness's own setup and inventory calls


def agent_call(name, arguments: dict) -> tuple[object, dict]:
    """The tool an agent call runs and its arguments: a browser_tools_call runs the tool it names. Any other call is
    returned unchanged."""
    if name == GATEWAY_CALL and isinstance(arguments, dict) and isinstance(arguments.get("name"), str):
        inner = arguments.get("arguments")
        return arguments["name"], inner if isinstance(inner, dict) else {}
    return name, arguments


def call_urls(value) -> list[str]:
    """Every string `url` in a call's arguments, nested ones included: the commands of Kitsune's container tools
    (browser_batch, browser_parallel, browser_retry, ...) carry their own."""
    if isinstance(value, dict):
        return [url for key, item in value.items()
                for url in ([item] if key == "url" and isinstance(item, str) else call_urls(item))]
    if isinstance(value, list):
        return [url for item in value for url in call_urls(item)]
    return []


class FullNativeSession(NativeSession):
    def request(self, method: str, params: dict | None = None, *, notify=None, role="harness") -> dict:
        """NativeSession.request (frozen) with a deadline by role: AGENT_REQUEST_SECONDS for the agent's calls,
        HARNESS_REQUEST_SECONDS for the harness's. Otherwise the same exchange, diagnostics and metadata."""
        self.serial += 1
        request_id = "personal-harness-" + str(self.serial)
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        started = time.monotonic()
        self.diagnostic("rpc_started", request_id=request_id, role=role, method=method,
                        tool=(params or {}).get("name"), action=(params or {}).get("arguments", {}).get("action"))
        self.send(request)
        deadline = time.monotonic() + (AGENT_REQUEST_SECONDS if role == "agent" else HARNESS_REQUEST_SECONDS)
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
            elif message.get("method") == "elicitation/create":
                self.send({"jsonrpc": "2.0", "id": message["id"],
                           "result": self.answer_elicitation(message.get("params") or {}, role, (params or {}).get("name"))})
            elif "method" in message:
                self.send({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32601, "message": "Server-initiated requests unsupported in benchmark."}})
            else:
                raise ValueError("Unexpected native MCP response.")
            if time.monotonic() >= deadline:
                raise ValueError("Native MCP request timed out.")

    def forward(self, message: dict, emit) -> None:
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if message.get("method") != "tools/call" or "id" not in message:
            return super().forward(message, emit)
        called = params.get("name")
        name, arguments = agent_call(called, params.get("arguments", {}))
        outside = [url for url in call_urls(arguments) if url != "about:blank"
                   and "{0.scheme}://{0.netloc}".format(urlsplit(url)) != self.config["origin"]]
        if outside:
            self.prepare()
            self.evidence["outside_navigation"] += 1
            # Do not perform known out-of-fixture navigations.
            self.save()
            emit({"jsonrpc": "2.0", "id": message["id"], "result": {
                "isError": True, "content": [{"type": "text", "text": OUTSIDE_NAVIGATION}]}})
            return
        calls = len(self.evidence["tab_calls"])
        super().forward(message, emit)
        if called == name or len(self.evidence["tab_calls"]) == calls:
            return
        if name == "browser_tabs" and arguments.get("action") == "close":
            self.evidence["close_attempts"] += 1
        call = self.evidence["tab_calls"][-1]
        call["tool"] = name
        for key in ("action", "index", "tab_id", "url"):
            value = arguments.get(key)
            call[key] = int(value) if isinstance(value, float) and value.is_integer() else value
        call["via"] = called
        self.save()


def main() -> int:
    config = json.loads(Path(sys.argv[1]).read_text())
    session = FullNativeSession(config)

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
        print("Full-native fixture MCP setup/inventory failed; inspect private artifacts.", file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
