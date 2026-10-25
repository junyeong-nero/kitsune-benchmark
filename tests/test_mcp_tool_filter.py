"""No-model subprocess coverage for the allowlist relay's lifecycle."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest


FILTER = Path(__file__).resolve().parents[1] / "kitsune_benchmark/mcp_tool_filter.py"
UPSTREAM = '''import json, os, signal, sys, time
from pathlib import Path
mode = sys.argv[1]
Path(sys.argv[2]).write_text(str(os.getpid()))
if mode == "early":
    sys.exit(7)
if mode == "signal":
    os.kill(os.getpid(), signal.SIGTERM)
if mode in ("stdout_eof", "kill"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN if mode == "kill" else signal.SIG_DFL)
    os.close(1)
    while True:
        time.sleep(1)
for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if "id" not in request:
        continue
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "exit-probe", "version": "1"}}
    elif method == "tools/list":
        if mode == "fail":
            sys.exit(2)
        result = {"tools": [{"name": "browser_snapshot"}, {"name": "browser_navigate"}]}
    else:
        result = {"content": [{"type": "text", "text": request["params"]["name"]}]}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
if mode == "client_stop":
    while True:
        time.sleep(1)
sys.exit(4 if mode == "eof_fail" else 0)
'''


class McpToolFilterTests(unittest.TestCase):
    @contextmanager
    def relay(self, mode):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "upstream.py"
            pidfile = Path(folder) / "upstream.pid"
            script.write_text(UPSTREAM)
            process = subprocess.Popen([sys.executable, str(FILTER), '["browser_snapshot"]', "--",
                sys.executable, str(script), mode, str(pidfile)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            pid = None
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() or not pidfile.read_text():
                    self.assertLess(time.monotonic(), deadline, "upstream did not start")
                    time.sleep(0.01)
                pid = int(pidfile.read_text())
                yield process, pid
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def send(self, process, method, request_id=1, **params):
        process.stdin.write((json.dumps({"jsonrpc": "2.0", "id": request_id,
            "method": method, "params": params}) + "\n").encode())

    def response(self, process):
        self.assertTrue(select.select([process.stdout], [], [], 5)[0], "no bounded response")
        return json.loads(process.stdout.readline())

    def exited(self, process, pid, code):
        self.assertEqual(process.wait(timeout=12), code)
        self.assertTrue(select.select([process.stdout], [], [], 1)[0], "stdout did not close")
        self.assertEqual(process.stdout.read(), b"")
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(process.stderr.read(), b"")

    def test_initialize_then_tools_list_failure_with_client_stdin_open(self):
        with self.relay("fail") as (process, pid):
            self.send(process, "initialize")
            self.assertEqual(self.response(process)["result"]["serverInfo"]["name"], "exit-probe")
            self.send(process, "tools/list", 2)
            self.exited(process, pid, 2)
            self.assertFalse(process.stdin.closed)

    def test_exit_before_initialize_with_partial_client_input(self):
        with self.relay("early") as (process, pid):
            try:
                process.stdin.write(b'{"jsonrpc":')
            except BrokenPipeError:
                pass
            self.exited(process, pid, 7)
            self.assertFalse(process.stdin.closed)

    def test_upstream_signal_exit_is_nonzero(self):
        with self.relay("signal") as (process, pid):
            self.exited(process, pid, 128 + signal.SIGTERM)

    def test_normal_client_eof(self):
        with self.relay("normal") as (process, pid):
            self.send(process, "initialize")
            self.response(process)
            process.stdin.close()
            self.exited(process, pid, 0)

    def test_client_eof_does_not_mask_upstream_failure(self):
        with self.relay("eof_fail") as (process, pid):
            process.stdin.close()
            self.exited(process, pid, 4)

    def test_allowlist_filters_catalog_and_refuses_disabled_calls(self):
        with self.relay("normal") as (process, pid):
            self.send(process, "tools/list")
            self.assertEqual(self.response(process)["result"]["tools"], [{"name": "browser_snapshot"}])
            self.send(process, "tools/call", 2, name="browser_navigate", arguments={})
            self.assertTrue(self.response(process)["result"]["isError"])
            self.send(process, "tools/call", 3, name="browser_snapshot", arguments={})
            self.assertEqual(self.response(process)["result"]["content"][0]["text"], "browser_snapshot")
            process.stdin.close()
            self.exited(process, pid, 0)

    def test_client_eof_allows_relay_initiated_stop(self):
        with self.relay("client_stop") as (process, pid):
            self.send(process, "initialize")
            self.response(process)
            process.stdin.close()
            self.exited(process, pid, 0)

    def test_upstream_stdout_eof_cleans_up_live_child_as_failure(self):
        with self.relay("stdout_eof") as (process, pid):
            self.exited(process, pid, 128 + signal.SIGTERM)
            self.assertFalse(process.stdin.closed)

    def test_cleanup_kills_child_that_ignores_terminate_as_failure(self):
        with self.relay("kill") as (process, pid):
            self.exited(process, pid, 128 + signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
