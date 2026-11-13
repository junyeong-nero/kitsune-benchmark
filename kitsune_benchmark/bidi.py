"""Minimal WebDriver BiDi client over a stdlib WebSocket. No model calls.

The coexistence track drives a simulated *user* through this channel: tabs it
opens are not MCP-created (so Kitsune does not list them as owned), its input is
trusted (`isTrusted: true`), and it can read which tab the user actually sees.
The agent never sees this channel. Only what the track needs is implemented:
text frames, client masking, continuation frames, ping/pong and close.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import time
from urllib.parse import urlsplit


class BidiError(RuntimeError):
    pass


class WebSocket:
    def __init__(self, url: str, timeout: float = 10):
        parts = urlsplit(url)
        if parts.scheme != "ws" or parts.hostname not in {"127.0.0.1", "localhost"}:
            raise BidiError("Only local ws:// endpoints are supported.")
        self.sock = socket.create_connection((parts.hostname, parts.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = parts.path or "/"
        request = (f"GET {path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\n"
                   "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise BidiError("WebSocket handshake closed.")
            response += chunk
        head, _, self.buffer = response.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise BidiError("WebSocket handshake refused: " + head.split(b"\r\n", 1)[0].decode(errors="replace"))

    def _read(self, size: int) -> bytes:
        while len(self.buffer) < size:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise BidiError("WebSocket closed.")
            self.buffer += chunk
        data, self.buffer = self.buffer[:size], self.buffer[size:]
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        size = len(payload)
        if size < 126:
            header = struct.pack("!BB", 0x80 | opcode, 0x80 | size)
        elif size < 1 << 16:
            header = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, size)
        else:
            header = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, size)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def send(self, text: str) -> None:
        self._send_frame(0x1, text.encode())

    def recv(self, timeout: float) -> str:
        self.sock.settimeout(timeout)
        message = b""
        while True:
            first, second = self._read(2)
            opcode, size = first & 0x0F, second & 0x7F
            if size == 126:
                size = struct.unpack("!H", self._read(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if second & 0x80 else None
            payload = self._read(size)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise BidiError("WebSocket closed by peer.")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode in {0x1, 0x0, 0x2}:
                message += payload
                if first & 0x80:
                    return message.decode()

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        self.sock.close()


class Bidi:
    """One BiDi session. Events are kept for `events()`; commands block on their id."""

    def __init__(self, url: str, timeout: float = 15):
        self.ws = WebSocket(url.rstrip("/") + "/session")
        self.timeout = timeout
        self.serial = 0
        self.queued_events: list[dict] = []
        self.command("session.new", {"capabilities": {}})

    def command(self, method: str, params: dict | None = None, timeout: float | None = None) -> dict:
        self.serial += 1
        ident = self.serial
        self.ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BidiError(f"BiDi {method} timed out.")
            message = json.loads(self.ws.recv(remaining))
            if message.get("id") == ident:
                if message.get("type") == "error":
                    raise BidiError(f"BiDi {method}: {message.get('error')}: {message.get('message')}")
                return message.get("result", {})
            if message.get("type") == "event":
                self.queued_events.append(message)

    def events(self) -> list[dict]:
        events, self.queued_events = self.queued_events, []
        return events

    def close(self) -> None:
        try:
            self.command("session.end", timeout=3)
        except (BidiError, OSError):
            pass
        self.ws.close()

    # -- helpers used by the user driver --

    def top_contexts(self) -> list[dict]:
        return self.command("browsingContext.getTree", {"maxDepth": 0})["contexts"]

    def evaluate(self, context: str, expression: str, *, await_promise: bool = False):
        """Evaluates in a sandbox realm, so page scripts cannot see or observe it."""
        result = self.command("script.evaluate", {
            "expression": expression, "awaitPromise": await_promise,
            "target": {"context": context, "sandbox": "kitsune-benchmark-user"},
            "resultOwnership": "none"})
        if result.get("type") == "exception":
            raise BidiError("BiDi evaluate threw: " + json.dumps(result.get("exceptionDetails"))[:300])
        return unwrap(result.get("result", {}))


def unwrap(value: dict):
    kind = value.get("type")
    if kind in {"string", "number", "boolean"}:
        return value.get("value")
    if kind in {"undefined", "null"}:
        return None
    if kind == "array":
        return [unwrap(item) for item in value.get("value", [])]
    if kind == "object":
        return {unwrap(k) if isinstance(k, dict) else k: unwrap(v) for k, v in value.get("value", [])}
    return value
