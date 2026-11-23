"""Start a private Kitsune runtime (bridge + headless Firefox with that checkout's extension) for isolated runs.

Only the extension copy's WS port changes. The bridge gets private ports, home and token. Publish env.json
once both bridge and extension are ready; stop the owned child groups when interrupted.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'four-way'))
from framework.procs import GROUP, kill_tree, venv_exe
WS_SETTING = "const WS_URL = 'ws://127.0.0.1:47652';"


def ports():
    with socket.socket() as a, socket.socket() as b:
        a.bind(('127.0.0.1', 0)); b.bind(('127.0.0.1', 0))
        found = a.getsockname()[1], b.getsockname()[1]
    return ports() if {47651, 47652} & set(found) else found


def status(port, token):
    request = urllib.request.Request(f'http://127.0.0.1:{port}/api/status', headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=1) as r:
            return json.load(r)
    except (OSError, ValueError):
        return None


def wait(port, token, process, extension=False, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit('bridge/browser exited; see logs')
        s = status(port, token)
        if s and (not extension or s.get('extension_connected')):
            return s
        time.sleep(0.25)
    raise SystemExit('timed out waiting for bridge/extension')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkout', type=Path, help='Kitsune checkout with a synced .venv')
    p.add_argument('folder', type=Path, help='New private runtime folder')
    args = p.parse_args()
    checkout, folder = args.checkout.resolve(), args.folder.resolve()
    folder.mkdir(parents=True)
    http, ws = ports()
    source = (checkout / 'extension/background/background.js').read_text(encoding='utf-8')
    if source.count(WS_SETTING) != 1:
        raise SystemExit('unexpected extension endpoint')
    shutil.copytree(checkout / 'extension', folder / 'extension')
    (folder / 'extension/background/background.js').write_text(source.replace(WS_SETTING, f"const WS_URL = 'ws://127.0.0.1:{ws}';"),
                                                               encoding='utf-8')
    token = secrets.token_urlsafe(32)
    env = {k: v for k, v in os.environ.items() if k not in ('VIRTUAL_ENV', 'PYTHONPATH', 'PYTHONHOME')}
    env.update(KITSUNE_HOME=str(folder / 'home'), KITSUNE_HTTP_PORT=str(http), KITSUNE_WS_PORT=str(ws), KITSUNE_TOKEN=token,
               PYTHONUNBUFFERED='1')  # bridge.log stays complete even when Windows teardown kills the bridge
    firefox = subprocess.run(['node', '-e', "console.log(require('playwright').firefox.executablePath())"],
                             cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    procs = []

    def spawn(argv, log):
        procs.append(subprocess.Popen(argv, env=env, cwd=folder, stdin=subprocess.DEVNULL, stdout=(folder / log).open('wb'),
                                      stderr=subprocess.STDOUT, **GROUP))
        return procs[-1]

    def stop(*_):
        raise SystemExit(0)

    def cleanup():
        for proc in procs:
            kill_tree(proc, signal.SIGTERM)
        for proc in procs:
            proc.wait(timeout=15)

    # Windows has no SIGTERM delivery: the parent kills this process tree instead (see benchmark.settings).
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        bridge = spawn([str(venv_exe(checkout / '.venv', 'python')), '-m', 'kitsune.bridge'], 'bridge.log')
        wait(http, token, bridge)
        # node + the package script, not node_modules/.bin, which holds a .cmd shim on Windows.
        browser = spawn([shutil.which('node'), str(ROOT / 'node_modules/web-ext/bin/web-ext.js'), 'run', '--no-config-discovery', '--no-input',
                         '--source-dir', str(folder / 'extension'), '--artifacts-dir', str(folder / 'web-ext'),
                         '--firefox', firefox, '--no-reload', '--start-url', 'about:blank',
                         '--args=--width=1280', '--args=--height=805', '--args=-headless',
                         # Bound memory on small hosts: few content processes (one per site under Fission).
                         '--pref=dom.ipc.processCount=2', '--pref=dom.ipc.processCount.webIsolated=1'], 'firefox.log')
        s = wait(http, token, browser, extension=True)
        revision = (subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', '--short', 'HEAD'],
                                            text=True).strip() if (checkout / '.git').exists() else 'export')
        pending = folder / 'env.tmp'
        pending.write_text(json.dumps({
            'BENCH_KITSUNE': str(venv_exe(checkout / '.venv', 'kitsune')), 'BENCH_KITSUNE_HTTP_PORT': str(http),
            'BENCH_KITSUNE_TOKEN': token, 'BENCH_KITSUNE_HOME': str(folder / 'home'),
            'revision': revision, 'build': s.get('build') or s.get('version')}), encoding='utf-8')
        pending.replace(folder / 'env.json')
        print('ready', revision, flush=True)
        while all(proc.poll() is None for proc in procs):
            time.sleep(1)
        raise SystemExit('bridge or browser exited')
    finally:
        cleanup()


if __name__ == '__main__':
    main()
