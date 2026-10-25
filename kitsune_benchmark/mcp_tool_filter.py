"""Stdio MCP relay that exposes only allowlisted tools, like Codex `enabled_tools`.

Usage: mcp_tool_filter.py '<json tool list>' -- command [args...]
Runs as an absolute-path script. Only newline-delimited stdio MCP servers are
supported. Non-allowlisted tools are dropped from tools/list and their calls
are refused without reaching the native server. No model calls.
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import threading


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[2] != "--":
        print("usage: mcp_tool_filter.py TOOLS_JSON -- command [args...]", file=sys.stderr)
        return 2
    allowed = set(json.loads(sys.argv[1]))
    child = subprocess.Popen(sys.argv[3:], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=sys.stderr, bufsize=0)
    list_ids: set = set()
    lock = threading.Lock()
    output_closed = threading.Event()

    def emit(message: dict) -> None:
        with lock:
            sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    def relay_output() -> None:
        try:
            for line in child.stdout:
                if not line.strip():
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict) and message.get("id") in list_ids and "method" not in message:
                    list_ids.discard(message["id"])
                    result = message.get("result")
                    if isinstance(result, dict) and isinstance(result.get("tools"), list):
                        result["tools"] = [t for t in result["tools"] if isinstance(t, dict) and t.get("name") in allowed]
                emit(message)
        except (OSError, ValueError):
            pass
        finally:
            output_closed.set()

    reader = threading.Thread(target=relay_output, daemon=True)
    reader.start()
    stopped = False
    client_eof = False
    buffer = b""
    try:
        while not output_closed.is_set() and child.poll() is None:
            if not select.select([sys.stdin], [], [], 0.1)[0]:
                continue
            chunk = os.read(sys.stdin.fileno(), 65536)
            buffer += chunk
            lines = buffer.split(b"\n")
            buffer = lines.pop()
            if not chunk and buffer:
                lines.append(buffer)
                buffer = b""
            for line in lines:
                if not line.strip():
                    continue
                message = json.loads(line)
                method = message.get("method") if isinstance(message, dict) else None
                if method == "tools/list" and "id" in message:
                    list_ids.add(message["id"])
                elif method == "tools/call" and "id" in message:
                    name = (message.get("params") or {}).get("name")
                    if name not in allowed:
                        emit({"jsonrpc": "2.0", "id": message["id"], "result": {"isError": True, "content": [
                            {"type": "text", "text": "Tool is not enabled in this benchmark."}]}})
                        continue
                child.stdin.write(line + b"\n")
                child.stdin.flush()
            if not chunk:
                client_eof = True
                break
    except (OSError, ValueError):
        pass
    finally:
        try:
            child.stdin.close()  # Let the native server clean up on EOF.
        except OSError:
            pass
        try:
            child.wait(timeout=1 if output_closed.is_set() else 5)
        except subprocess.TimeoutExpired:
            stopped = True
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        reader.join(timeout=3)
        child.stdout.close()
    code = child.returncode
    if stopped and client_eof and code < 0:
        return 0
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    raise SystemExit(main())
