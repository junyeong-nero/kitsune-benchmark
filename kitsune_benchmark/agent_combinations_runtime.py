"""Owned runtimes for the separate agent-combinations pilot; no model calls.

Historical Firefox runners are unchanged. Zen is launched explicitly with a new
profile, HOME, extension copy and bridge. Never attach to an everyday browser.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import hashlib
import os
from pathlib import Path
import plistlib
import secrets
import subprocess
import tempfile

from . import ego_mcp, private_chrome
from .adapter import resolve, terminate_group, write_json
from .agent_combinations import KITSUNE_SHA
from .runtime import BASE_ENV
from .smoke import await_bridge, copy_extension, private_ports, source_revision

ROOT = Path(__file__).resolve().parents[1]
ZEN = Path("/Applications/Zen.app/Contents/MacOS/zen")
TOOLS = ROOT / "configs/agent-combinations"


def validation_fingerprint():
    paths = [*ROOT.glob("kitsune_benchmark/*.py"), *ROOT.glob("kitsune_benchmark/gallery_static/*"),
             ROOT / "tasks/personal/catalog.json", ROOT / "package-lock.json", ROOT / "uv.lock",
             TOOLS / "package-lock.json", TOOLS / "python/uv.lock",
             ROOT / "scripts/preflight-agent-combinations.py"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def runtime_pins():
    files = {"zen": ZEN, "chrome": private_chrome.CHROME,
             "aside_cli": Path.home() / ".local/bin/aside", "ego_cli": Path(ego_mcp.find_binary()),
             "agent_browser": TOOLS / "node_modules/@agent-browser/cli-darwin-arm64/bin/agent-browser"}
    apps = {name: Path("/Applications") / app / "Contents/Info.plist" for name, app in (
        ("zen", "Zen.app"), ("chrome", "Google Chrome.app"), ("aside", "Aside.app"), ("ego", "ego lite.app"))}
    files.update({name + "_plist": path for name, path in apps.items()})
    files.update({h: Path(resolve(h, h)) for h in ("codex", "claude")})
    return {"versions": {name: plistlib.loads(path.read_bytes())["CFBundleShortVersionString"] for name, path in apps.items()},
        "files": {name: {"path": str(path.resolve()), "sha256": digest(path)} for name, path in files.items()},
        "ego_guide_sha256": hashlib.sha256(ego_mcp.describe(ego_mcp.find_binary()).encode()).hexdigest(),
        "node": subprocess.run(["node", "--version"], capture_output=True, text=True, check=True, timeout=10).stdout.strip()}


def private_environment(folder: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in BASE_ENV}
    for key, name in (("HOME", "home"), ("TMPDIR", "tmp")):
        path = folder / name
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        env[key] = str(path)
    env.update(TMP=env["TMPDIR"], TEMP=env["TMPDIR"])
    return env


@contextmanager
def chrome_runtime(folder: Path, surface: str):
    """Attach only to the fresh Chrome whose endpoint this helper just created."""
    if surface not in {"playwright", "devtools", "browser-harness", "agent-browser"}:
        raise ValueError("Unknown private Chrome surface")
    folder = folder.resolve()
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    env = private_environment(folder)
    record = private_chrome.launch(folder)
    try:
        with tempfile.TemporaryDirectory(prefix="ac-", dir="/tmp") as sockets:
            if surface == "playwright":
                env.update(PWTEST_SOCKETS_DIR=sockets, DEBUG="pw:api")
                command = ["node", str(ROOT / "node_modules/@playwright/mcp/cli.js"),
                           "--browser", "chrome", "--cdp-endpoint", record["ws_url"],
                           "--viewport-size", "1280x720"]
            elif surface == "devtools":
                command = [str(TOOLS / "node_modules/.bin/chrome-devtools-mcp"),
                           "--wsEndpoint", record["ws_url"], "--no-usage-statistics", "--no-performance-crux"]
            elif surface == "browser-harness":
                command = [str(TOOLS / "python/.venv/bin/browser-harness-mcp")]
                env.update(BU_CDP_WS=record["ws_url"], BU_NAME="pilot", BH_HOME=env["HOME"],
                           BH_RUNTIME_DIR=sockets, BH_TMP_DIR=env["TMPDIR"],
                           BH_AGENT_WORKSPACE=str(folder / "workspace"))
            else:
                config = folder / "agent-browser.json"
                write_json(config, {"cdp": record["ws_url"], "autoConnect": False})
                command = [str(TOOLS / "node_modules/.bin/agent-browser"), "mcp", "--config", str(config)]
                env.update(AGENT_BROWSER_CDP=record["ws_url"], AGENT_BROWSER_SESSION="pilot",
                           AGENT_BROWSER_SOCKET_DIR=sockets, AGENT_BROWSER_CONFIG=str(config))
            write_json(folder / "surface.json", {"model_invoked": False, "surface": surface,
                "command": command, "private_chrome_record": str(Path(record["folder"]) / "launcher.json")})
            try:
                yield command, env, record
            finally:
                if surface == "browser-harness":
                    subprocess.run([str(TOOLS / "python/.venv/bin/python"), "-c",
                        "from browser_harness.admin import restart_daemon; restart_daemon()"],
                        env=env, cwd=folder, check=True, timeout=30, capture_output=True)
                elif surface == "agent-browser" and list(Path(sockets).glob("*.sock")):
                    # Explicit owned socket/session; never the user's default daemon.
                    subprocess.run([str(TOOLS / "node_modules/.bin/agent-browser"), "close"],
                        env=env, cwd=folder, check=True, timeout=30, capture_output=True)
    finally:
        private_chrome.stop(record)
        write_json(folder / "cleanup.json", {"model_invoked": False,
            "owned_chrome_stopped": private_chrome.owned_process(record) is None})


@contextmanager
def zen_runtime(folder: Path, project: Path, *, bidi_port: int, sha: str = KITSUNE_SHA):
    """Yield a raw Kitsune stdio command and its explicitly isolated environment."""
    folder, project = folder.resolve(), project.resolve()
    if source_revision(project) != {"revision": sha, "dirty": False}:
        raise ValueError("Kitsune must be clean at the pilot's pinned source")
    if not ZEN.is_file():
        raise ValueError("The pilot requires Zen, not a substituted Firefox binary")
    if not 1024 <= bidi_port <= 65535 or bidi_port in {9222, 9223, 47651, 47652}:
        raise ValueError("Refusing a default or invalid BiDi port")
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    env = private_environment(folder)
    profile = folder / "profile"
    profile.mkdir(mode=0o700)
    http, ws = private_ports()
    extension = folder / "extension"
    patched = copy_extension(project / "extension", extension, ws)
    env.update(KITSUNE_HOME=str(folder / "bridge-home"), KITSUNE_HTTP_PORT=str(http),
               KITSUNE_WS_PORT=str(ws), KITSUNE_TOKEN=secrets.token_urlsafe(32),
               KITSUNE_NO_BRIDGE_RESTART="1", MOZ_REMOTE_ALLOW_SYSTEM_ACCESS="1")
    uv = ["uv", "run", "--locked", "--project", str(project)]
    processes = []
    try:
        with ExitStack() as stack:
            def spawn(argv, name):
                path = folder / (name + ".log")
                log = stack.enter_context(path.open("xb"))
                path.chmod(0o600)
                process = subprocess.Popen(argv, env=env, cwd=folder, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=log, start_new_session=True)
                processes.append((name, process))
                stack.callback(terminate_group, process)
                return process

            bridge = spawn([*uv, "python", "-m", "kitsune.bridge"], "bridge")
            await_bridge(http, env["KITSUNE_TOKEN"], bridge)
            argv = [str(ROOT / "node_modules/.bin/web-ext"), "run", "--no-config-discovery", "--no-input",
                "--source-dir", str(extension), "--artifacts-dir", str(folder / "web-ext"),
                "--firefox", str(ZEN), "--firefox-profile", str(profile), "--keep-profile-changes",
                "--no-reload", "--start-url", "about:blank", "--args=-headless",
                "--args=--width=1280", "--args=--height=805", f"--args=--remote-debugging-port={bidi_port}",
                "--args=--remote-allow-system-access", "--pref=remote.prefs.recommended=false"]
            browser = spawn(argv, "zen")
            write_json(folder / "runtime.json", {"model_invoked": False, "browser": str(ZEN),
                "kitsune_source": sha, "profile": str(profile), "argv": argv,
                "extension_copy": patched, "bidi_port": bidi_port,
                "processes": [{"role": name, "pid": p.pid} for name, p in processes]})
            await_bridge(http, env["KITSUNE_TOKEN"], browser, extension=True)
            yield [*uv, "kitsune"], env
    finally:
        write_json(folder / "cleanup.json", {"model_invoked": False,
            "processes": [{"role": name, "pid": p.pid, "returncode": p.poll()} for name, p in processes],
            "owned_launchers_stopped": all(p.poll() is not None for _, p in processes)})
