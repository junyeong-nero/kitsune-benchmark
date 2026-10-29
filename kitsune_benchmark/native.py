"""Isolated Playwright MCP and Kitsune MCP servers for no-model tool probes.

The same isolation as the paired runner: a private Firefox profile and, for Kitsune, a private bridge, ports, home
and token. No model, harness login or user profile is involved. `headed` shows the browser window (needed for
OS-level input such as browser_trusted_click); `caps` sets KITSUNE_CAPS for the Kitsune MCP server.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import secrets
import subprocess
from unittest.mock import patch

from .adapter import resolve, terminate_group
from .runtime import codex_environment
from .smoke import ROOT, await_bridge, copy_extension, private_ports


def firefox_binary(env: dict) -> str:
    return subprocess.run(["node", "-e", "console.log(require('playwright').firefox.executablePath())"],
                          cwd=ROOT, env=env, text=True, capture_output=True, check=True).stdout.strip()


@contextmanager
def playwright_server(folder: str, *, headed: bool = False):
    """Yields the Playwright MCP command; the environment is patched for the duration."""
    env = {"PLAYWRIGHT_BROWSERS_PATH": str(ROOT / "artifacts/browsers"), "PLAYWRIGHT_SKIP_BROWSER_GC": "1",
           "PWTEST_SOCKETS_DIR": folder}
    command = ["node", str(ROOT / "node_modules/@playwright/mcp/cli.js"), "--browser", "firefox", "--isolated",
               "--viewport-size", "1280x720"]
    if not headed:
        command.append("--headless")
    with patch.dict(os.environ, env):
        yield command


@contextmanager
def kitsune_server(folder: str, project: str | Path, *, headed: bool = False, caps: str | None = None,
                   height: int = 805):
    """Starts a private bridge and Firefox with the Kitsune extension; yields the Kitsune MCP command."""
    project = Path(project).expanduser().resolve()
    env = codex_environment(resolve("codex"))  # resolve only; no Codex process, login or model call
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / "artifacts/browsers")
    binary = firefox_binary(env)
    http_port, ws_port = private_ports()
    destination = Path(folder) / "extension"
    copy_extension(project / "extension", destination, ws_port)
    env.update(KITSUNE_HOME=str(Path(folder) / "home"), KITSUNE_HTTP_PORT=str(http_port),
               KITSUNE_WS_PORT=str(ws_port), KITSUNE_TOKEN=secrets.token_urlsafe(32))
    if caps:
        env["KITSUNE_CAPS"] = caps
    with ExitStack() as stack:
        def spawn(args, filename):
            log = stack.enter_context((Path(folder) / filename).open("wb"))
            process = subprocess.Popen(args, env=env, cwd=folder, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True)
            stack.callback(terminate_group, process)
            return process
        bridge = spawn(["uv", "run", "--locked", "--project", str(project), "python", "-m", "kitsune.bridge"],
                       "bridge.log")
        await_bridge(http_port, env["KITSUNE_TOKEN"], bridge)
        args = [str(ROOT / "node_modules/.bin/web-ext"), "run", "--no-config-discovery", "--no-input",
                "--source-dir", str(destination), "--artifacts-dir", str(Path(folder) / "web-ext"),
                "--firefox", binary, "--no-reload", "--start-url", "about:blank",
                "--args=--width=1280", f"--args=--height={height}"]
        if not headed:
            args.append("--args=-headless")
        browser = spawn(args, "firefox.log")
        await_bridge(http_port, env["KITSUNE_TOKEN"], browser, extension=True)
        with patch.dict(os.environ, env):
            yield ["uv", "run", "--locked", "--project", str(project), "kitsune"]
