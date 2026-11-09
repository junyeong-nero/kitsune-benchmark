"""Stdio MCP server exposing ego(lite)'s `ego-browser nodejs` CLI as one tool, `run_script` (exhibition arm).

ego(lite) ships no MCP server; agents run it as a shell heredoc. The benchmark gives the model no shell, so this wraps
that one entry point: the tool's `code` is the script body that would go inside the heredoc, and the tool description
is the vendor's own usage guide (`ego-browser skill`), unedited. Runs as an absolute-path script. No model calls.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

APP = "/Applications/ego lite.app"
TIMEOUT_SEC = 120
PROTOCOL = "2024-11-05"


def find_binary() -> str:
    override = os.environ.get("EGO_BROWSER_BIN")
    if override:
        return override
    found = sorted(glob.glob(APP + "/Contents/Frameworks/*.framework/Versions/Current/Helpers/ego-browser"))
    if not found:
        raise SystemExit("ego-browser not found; install ego(lite).")
    return found[0]


def describe(binary: str) -> str:
    guide = subprocess.run([binary, "skill"], capture_output=True, text=True, timeout=30)
    text = (guide.stdout + guide.stderr).strip()
    return ("Run one JavaScript script with `ego-browser nodejs`, ego(lite)'s browser automation runtime. `code` is the "
            "script body, exactly what would go inside the `ego-browser nodejs <<'EOF' ... EOF` heredoc; the tool "
            f"returns its console output. {TIMEOUT_SEC}s per call. The vendor's usage guide follows.\n\n" + text)


def run_script(binary: str, code: str) -> dict:
    try:
        done = subprocess.run([binary, "nodejs"], input=code, capture_output=True, text=True, timeout=TIMEOUT_SEC)
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "") if isinstance(error.stdout, str) else ""
        return {"isError": True, "content": [{"type": "text", "text": f"Timed out after {TIMEOUT_SEC}s.\n{output}"}]}
    output = (done.stdout + done.stderr).strip() or "(no output)"
    return {"isError": done.returncode != 0, "content": [{"type": "text", "text": output}]}


def main() -> int:
    binary = find_binary()
    tool = {"name": "run_script", "description": describe(binary),
            "inputSchema": {"type": "object", "properties": {"code": {"type": "string",
                            "description": "JavaScript run by `ego-browser nodejs`."}},
                            "required": ["code"], "additionalProperties": False}}

    def reply(message_id, result=None, error=None):
        body = {"jsonrpc": "2.0", "id": message_id}
        body.update({"error": error} if error else {"result": result})
        print(json.dumps(body, ensure_ascii=False), flush=True)

    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        if "id" not in message:
            continue  # notifications
        method, params = message.get("method"), message.get("params") or {}
        if method == "initialize":
            reply(message["id"], {"protocolVersion": params.get("protocolVersion", PROTOCOL),
                                  "capabilities": {"tools": {}}, "serverInfo": {"name": "ego-browser", "version": "1"}})
        elif method == "tools/list":
            reply(message["id"], {"tools": [tool]})
        elif method == "tools/call":
            code = (params.get("arguments") or {}).get("code")
            if params.get("name") != "run_script" or not isinstance(code, str):
                reply(message["id"], error={"code": -32602, "message": "Unknown tool or missing code."})
            else:
                reply(message["id"], run_script(binary, code))
        elif method == "ping":
            reply(message["id"], {})
        else:
            reply(message["id"], error={"code": -32601, "message": "Method not found."})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
