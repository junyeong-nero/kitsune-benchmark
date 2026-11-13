"""Owned Chrome for no-model fixtures and operator-assisted extension login.

Never attach to an existing browser or copy a profile. Connection details and
credentials stay inside an ignored, mode-0700 artifact directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

import psutil

from .adapter import terminate_group, write_json
from .runtime import BASE_ENV

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FORBIDDEN_PORTS = {9222, 9223, 47651, 47652}


def connection(profile: Path) -> str:
    """Read only the endpoint Chrome published inside this owned profile."""
    lines = (profile / "DevToolsActivePort").read_text().splitlines()
    if len(lines) != 2:
        raise ValueError("Invalid private Chrome endpoint record")
    port = int(lines[0])
    if not 1024 <= port <= 65535 or port in FORBIDDEN_PORTS:
        raise ValueError("Refusing a default or invalid debugging port")
    path = urlsplit(lines[1])
    if (path.scheme or path.netloc or path.query or path.fragment
            or not path.path.startswith("/devtools/browser/")
            or any(c.isspace() for c in lines[1])):
        raise ValueError("Invalid private Chrome WebSocket path")
    return f"ws://127.0.0.1:{port}{path.path}"


def launch(parent: Path, *, executable: Path = CHROME, headed: bool = False,
           url: str = "about:blank", timeout: float = 30) -> dict:
    if not executable.is_file():
        raise ValueError("Chrome executable is unavailable")
    if url != "about:blank" and not url.startswith("https://claude.ai/"):
        raise ValueError("Startup may open only a blank page or Claude's setup page")
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="chrome-", dir=parent)).resolve()
    profile = folder / "profile"
    home, temp = folder / "home", folder / "tmp"
    for path in (profile, home, temp):
        path.mkdir(mode=0o700)
    env = {k: v for k, v in os.environ.items() if k in BASE_ENV}
    env.update(HOME=str(home), TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp))
    argv = [str(executable), f"--user-data-dir={profile}", "--remote-debugging-port=0",
            "--remote-debugging-address=127.0.0.1", "--no-first-run", "--no-default-browser-check",
            "--disable-sync", "--disable-background-networking", "--window-size=1280,900",
            *([] if headed else ["--headless=new"]), url]
    log = folder / "browser.log"
    with log.open("xb") as stream:
        log.chmod(0o600)
        process = subprocess.Popen(argv, cwd=folder, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=stream, start_new_session=True)
    try:
        started = psutil.Process(process.pid).create_time()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError("Private Chrome exited before readiness; inspect its private log")
            try:
                endpoint = connection(profile)
                break
            except FileNotFoundError:
                time.sleep(0.1)
        else:
            raise TimeoutError("Private Chrome did not publish an endpoint")
        record = {"pid": process.pid, "created": started, "profile": str(profile),
                  "folder": str(folder), "executable": str(executable), "argv": argv,
                  "ws_url": endpoint, "headed": headed, "model_invoked": False,
                  "started_utc": datetime.now(timezone.utc).isoformat()}
        write_json(folder / "launcher.json", record)
        return record
    except BaseException:
        terminate_group(process)
        raise


def owned_process(record: dict) -> psutil.Process | None:
    try:
        process = psutil.Process(record["pid"])
        if (process.create_time() != record["created"]
                or f"--user-data-dir={record['profile']}" not in process.cmdline()
                or os.getpgid(process.pid) != process.pid):
            raise ValueError("Process identity differs; refusing to signal it")
        return process
    except psutil.NoSuchProcess:
        return None


def stop(record: dict) -> None:
    process = owned_process(record)
    if process is None:
        return
    os.killpg(process.pid, 15)
    try:
        process.wait(timeout=5)
    except psutil.TimeoutExpired:
        if owned_process(record) is not None:
            os.killpg(process.pid, 9)
            process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare-login", "status", "stop"))
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    if args.action == "prepare-login":
        if args.record is not None:
            parser.error("prepare-login creates a fresh profile; do not supply --record")
        record = launch(ROOT / "artifacts/private-chrome", headed=True, url="https://claude.ai/chrome")
        print(json.dumps({"model_invoked": False, "record": str(Path(record["folder"]) / "launcher.json"),
                          "profile": record["profile"], "next": "Operator installs extension and logs in; do not send a task yet."}))
    else:
        if args.record is None:
            parser.error("--record is required")
        record = json.loads(args.record.read_text())
        if args.action == "stop":
            stop(record)
        print(json.dumps({"running": owned_process(record) is not None, "model_invoked": False}))


if __name__ == "__main__":
    main()
