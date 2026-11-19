"""One Claude Code harness; official stdin CLIs or native stdio MCP servers."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
from uuid import uuid4

ARMS = ('aside', 'egolite', 'playwright', 'kitsune')


def binary(name):
    found = shutil.which(name)
    if not found:
        raise ValueError(f'Missing executable: {name}')
    return str(Path(found).absolute())


def required(key):
    value = os.environ.get(key)
    if not value:
        raise ValueError(f'Set {key} for a dedicated benchmark browser (no default profile).')
    return value


def config(arm, mode='isolated'):
    root = Path(__file__).resolve().parents[2]  # repository root
    if arm in ('kitsune', 'playwright'):
        name, local = ((arm, root.parent / 'kitsune/.venv/bin/kitsune') if arm == 'kitsune' else
                       ('playwright-mcp', root / 'node_modules/.bin/playwright-mcp'))
        cmd = binary(os.environ.get('BENCH_' + arm.upper()) or shutil.which(name) or str(local))
    if mode == 'existing-profile':
        if arm == 'aside':
            return [binary('aside'), 'repl', '--host', 'local', '--file', '-']
        if arm == 'egolite':
            if sys.platform == 'darwin':
                # Changing the profile does not waive the native app integrity check. Non-strict: Finder xattrs
                # (com.apple.FinderInfo) fail --strict without invalidating the signature or notarization.
                app = '/Applications/ego lite.app'
                if any(subprocess.run(c + [app], capture_output=True).returncode
                       for c in (['codesign', '--verify'], ['spctl', '-a'])):
                    raise ValueError('EgoLite app failed codesign --verify or Gatekeeper; existing-profile run not started.')
            return [binary('ego-browser'), 'nodejs']
        if arm == 'playwright':
            return {'command': cmd, 'args': ['--extension']}
        return {'command': cmd, 'env': {'KITSUNE_USER_TABS': 'read-only', 'KITSUNE_NO_BRIDGE_RESTART': '1'}}
    if mode != 'isolated':
        raise ValueError(f'Unknown browser mode: {mode}')
    if arm == 'aside':
        return [binary('aside'), 'repl', '--host', 'local', '--profile', required('BENCH_ASIDE_PROFILE'), '--file', '-']
    if arm == 'egolite':
        return [binary('ego-browser'), '--ego-server-name=' + required('BENCH_EGO_SERVICE'), 'nodejs']
    if arm == 'playwright':
        return {'command': cmd, 'args': ['--browser', 'firefox', '--isolated', '--headless', '--viewport-size', '1280x720']}
    port = int(required('BENCH_KITSUNE_HTTP_PORT'))
    if not 1024 <= port <= 65535 or port == 47651:
        raise ValueError('Use a dedicated, non-default Kitsune bridge port.')
    return {'command': cmd, 'env': {
        'KITSUNE_HTTP_PORT': str(port), 'KITSUNE_TOKEN': required('BENCH_KITSUNE_TOKEN'),
        'KITSUNE_HOME': str(Path(required('BENCH_KITSUNE_HOME')).resolve()), 'KITSUNE_NO_BRIDGE_RESTART': '1'}}


def vendor(argv, code=None):
    # EgoLite prints console.log output on stderr; Aside on stdout.
    p = subprocess.run(argv, input=code, text=True, capture_output=True, check=True, timeout=90)
    return p.stdout + p.stderr


def open_in_aside(url):
    subprocess.run(['open', '-g', '-a', 'Aside', url], check=True, timeout=30)


def aside_target(settings, url):
    """One-shot `aside repl` sessions close tabs they open, so the app opens the tab and each call attaches."""
    open_in_aside(url)
    find = f'const t=(await listBrowserTabs()).find(t=>t.url==={json.dumps(url)});console.log("TARGET="+(t?t.targetId:""))'
    for _ in range(20):
        match = re.search(r'\bTARGET=([0-9A-F]+)\b', vendor(settings, find))
        if match:
            return match[1]
        time.sleep(0.5)
    raise ValueError('Aside did not report the fixture tab')


@contextmanager
def surface(arm, settings, folder, url, mode='isolated'):
    if isinstance(settings, dict):
        hint = f'Open {url} in a fresh benchmark tab using the browser MCP tools.'
        if mode == 'existing-profile':
            hint = (f'Your first browser action must be browser_tabs(action="new", url="{url}"). ' if arm == 'kitsune' else
                    f'Your first browser action must be browser_tabs(action="new"), then browser_navigate to {url} in that new tab. ')
            hint += ('Never list, inspect, select or change a pre-existing tab. If creating a new tab fails, stop. '
                     'After submission leave the fixture tab open for the operator. Do not close the browser.')
        yield ({'browser': settings}, '', 'mcp__browser__*', hint)
        return
    # Only this CLI invocation is pre-approved. JS is one argument, passed unchanged on stdin.
    prefix = ''
    if arm == 'aside':
        guide = vendor([settings[0], 'guide', 'repl'])
        target = aside_target(settings, url)
        prefix = f'printf "%s\\n" {shlex.quote(f"await attachBrowserTab({json.dumps(target)});")}; '
        hint = ('Every ./browser call is a fresh REPL session that the wrapper first attaches to the fixture tab, so `page` '
                'is already the fixture. Variables do not persist between calls. Never call openTab, closeTab, '
                'listBrowserTabs or attachBrowserTab yourself.')
        # REPL sessions cannot close app-opened tabs (closeTab only detaches) and goto(about:/data:) never reports
        # readiness on them. Leave the dead fixture tab for the operator.
        close = None
    else:
        guide = vendor([settings[0], 'skill'])
        receipt = vendor(settings, f'const t=await taskSpace("bench-{uuid4().hex}");console.log("SPACE="+t.spaceId)')
        match = re.search(r'\bSPACE=(\d+)\b', receipt)
        if not match:
            raise ValueError('EgoLite returned no TaskSpace ID')
        space = match[1]
        close = f'await (await taskSpace({space})).finish({{keep:[]}})'
        hint = f'Resume taskSpace({space}); use page("p1"). Do not finish it.'
    wrapper = folder / 'browser'
    wrapper.write_text('#!/bin/sh\n[ "$#" -eq 1 ] || exit 2\n{ ' + prefix + 'printf "%s\\n" "$1"; } | ' + shlex.join(settings) + '\n')
    wrapper.chmod(0o700)
    try:
        if arm == 'egolite':
            vendor(settings, f'await (await taskSpace({space})).page("p1").goto({json.dumps(url)})')
        yield ({}, 'Bash', 'Bash(./browser:*)', f'Use Bash only as ./browser followed by one quoted JavaScript argument. {hint}\nCLI reference:\n{guide}')
    finally:
        # Best effort: a cleanup failure must not discard the attempt's result.
        try:
            if close:
                vendor(settings, close)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f'warning: {arm} cleanup failed: {type(exc).__name__}', file=sys.stderr)
