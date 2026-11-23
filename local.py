"""Plan (default) or execute the local fixture matrix: Kitsune and Playwright MCP under Claude Code.

Runs on macOS, Linux and Windows. It needs no Docker site host, WebArena-Pro, Aside or EgoLite: each attempt gets
its own loopback fixture server, and grading uses only the form submissions that server received.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

import benchmark as bench  # also puts four-way/ on sys.path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'local-tasks'))
from fixture import fixture
from framework import runner, transcript
from framework.arms import binary, surface
from framework.procs import WINDOWS

ARMS = ('playwright', 'kitsune')
MODEL = bench.MODELS['claude']
TASKS = json.loads((ROOT / 'local-tasks/tasks.json').read_text(encoding='utf-8'))
POLICY = ('Use only the designated browser and the rendered fixture UI. No other tabs, profiles, agents, shell commands, '
          'filesystem, page evaluation, source, storage, direct HTTP, or network inspection. Stop after one submission. '
          'The harness owns teardown. If blocked, report it; do not switch tools.')
PLAYWRIGHT = ROOT / 'node_modules/@playwright/mcp/cli.js'


def matrix(tasks=TASKS):
    for i, task in enumerate(tasks):
        start = i % len(ARMS)
        for arm in ARMS[start:] + ARMS[:start]:
            yield dict(harness='claude', model=MODEL, task=task['id'], arm=arm, timeout=300)


@contextmanager
def browser(cell, logs):
    if cell['arm'] == 'playwright':
        # node + the package script: node_modules/.bin holds a .cmd shim on Windows, which a stdio MCP client cannot run.
        yield {'command': shutil.which('node'), 'args': [str(PLAYWRIGHT), '--browser', 'firefox', '--isolated', '--headless',
                                                         '--viewport-size', '1280x720']}
        return
    with bench.settings(cell, logs) as settings:
        yield settings


def claude_binary():
    path = binary(os.environ.get('BENCH_CLAUDE') or 'claude')
    if WINDOWS and Path(path).suffix.lower() in ('.cmd', '.bat'):
        # cmd.exe cuts an argument at its first newline, and the prompt has several.
        raise ValueError(f'claude resolves to the {path} shim; set BENCH_CLAUDE to the native claude.exe')
    return path


def attempt(cell, task, settings, executable, log):
    with tempfile.TemporaryDirectory(prefix='browser-bench-') as tmp, fixture(task['id']) as (url, submissions):
        with surface(cell['arm'], settings, Path(tmp), url) as surfaced:
            prompt = f'{surfaced[3]}\n\nFixture: {url}\nRules: {POLICY}\nTask: {task["prompt"]}'
            stdout, stderr, rc, expired, seconds = runner.agent(cell['harness'], executable, cell['model'], surfaced, prompt,
                                                                Path(tmp), cell['timeout'])
        submitted = list(submissions)
    log.write_text(stdout + ('\n# stderr\n' + stderr if stderr else ''), encoding='utf-8')
    summary = transcript.summarize(cell['harness'], stdout)
    # Pass only on exactly one correct submission: recovering after a wrong one is still a failure.
    graded = 'pass' if submitted == [task['expected']] else 'fail'
    error = 'timeout' if expired else f'agent_exit_{rc}' if rc else None if summary['completed'] else 'incomplete'
    return dict(summary, graded=graded, status='error' if error else graded, error=error, agent_seconds=seconds,
                submissions=submitted)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true', help='actually start browsers and invoke Claude Code')
    p.add_argument('--out', type=Path, help='new private run directory (default: runs/local-<timestamp>)')
    p.add_argument('--task', action='append', choices=[t['id'] for t in TASKS], help='only these tasks (repeatable)')
    p.add_argument('--arm', action='append', choices=ARMS, help='only these browser arms (repeatable)')
    args = p.parse_args(argv)
    tasks = {t['id']: t for t in TASKS}
    cells = [c for c in matrix() if all(not chosen or c[key] in chosen for key, chosen in
                                        (('task', args.task), ('arm', args.arm)))]
    if not args.execute:
        print(json.dumps(cells, indent=2)); return 0
    if not shutil.which('node'):
        p.error('node is not on PATH')
    if any(c['arm'] == 'kitsune' for c in cells) and not os.getenv('BENCH_KITSUNE_CHECKOUT'):
        p.error('set BENCH_KITSUNE_CHECKOUT first (see README)')
    executable = claude_binary()
    folder = args.out or Path('runs') / time.strftime('local-%Y%m%d-%H%M%S')
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    (folder / 'plan.json').write_text(json.dumps(cells, indent=2))
    with (folder / 'results.jsonl').open('x', encoding='utf-8') as out:
        for i, cell in enumerate(cells, 1):
            log = folder / f'{i:03}-{cell["task"]}-{cell["arm"]}.jsonl'
            print(f'[{i}/{len(cells)}] {log.stem}', flush=True)
            try:
                with browser(cell, folder / (log.stem + '-runtime')) as settings:
                    row = attempt(cell, tasks[cell['task']], settings, executable, log)
            except Exception as exc:
                # Do not leak commands or credentials. Never count infra errors as task failures.
                out.write(json.dumps(dict(cell, status='infra_error', error=type(exc).__name__)) + '\n')
                print(f'Infrastructure failure: {type(exc).__name__}; stopped. See {folder}', file=sys.stderr)
                return 2
            out.write(json.dumps(dict(cell, **row, transcript=log.name)) + '\n'); out.flush()
            if row['status'] == 'error' and row['error'] != 'timeout':
                return 2  # subscription/agent failure: do not burn through the remaining matrix
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
