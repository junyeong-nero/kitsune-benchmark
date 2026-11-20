"""Plan (default) or execute the serial two-model, four-browser WebArena-Pro matrix."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent / 'four-way'
sys.path.insert(0, str(ROOT))
from framework.arms import ARMS, binary, config
from framework.runner import attempt

MODELS = {'claude': 'claude-opus-5-5', 'codex': 'gpt-6.1-sol'}
TASKS = json.loads((ROOT / 'testset/webarena-pro.json').read_text())


def matrix(tasks=TASKS):
    for harness, model in MODELS.items():
        for i, task in enumerate(tasks):
            start = i % len(ARMS)
            for arm in ARMS[start:] + ARMS[:start]:
                yield dict(harness=harness, model=model, task=task['id'], split=task['split'], arm=arm,
                           browser_mode='existing-profile' if arm in ('aside', 'egolite') else 'isolated', timeout=600)


@contextmanager
def settings(cell):
    arm = cell['arm']
    if arm != 'kitsune':
        yield config(arm, cell['browser_mode'])
        return
    # Private runtime only for the Kitsune attempt; do not target the user's bridge/profile.
    with tempfile.TemporaryDirectory(prefix='bench-kitsune-') as tmp:
        folder = Path(tmp) / 'runtime'
        proc = subprocess.Popen([sys.executable, str(ROOT / 'scripts/kitsune_runtime.py'),
                                 os.environ['BENCH_KITSUNE_CHECKOUT'], str(folder)])
        try:
            deadline = time.monotonic() + 140
            while not (folder / 'env.json').is_file():
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('private Kitsune bridge/Firefox failed to start')
                time.sleep(.25)
            env = json.loads((folder / 'env.json').read_text())
            yield {'command': env['BENCH_KITSUNE'], 'env': {k.removeprefix('BENCH_'): env[k] for k in
                   ('BENCH_KITSUNE_HTTP_PORT', 'BENCH_KITSUNE_HOME', 'BENCH_KITSUNE_TOKEN')} | {'KITSUNE_NO_BRIDGE_RESTART': '1'}}
        finally:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=30)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true', help='actually reset sites and invoke both subscriptions')
    p.add_argument('--out', type=Path, help='new private run directory (default: runs/<timestamp>)')
    p.add_argument('--task', choices=[t['id'] for t in TASKS], help='optional single-task smoke (8 attempts)')
    args = p.parse_args(argv)
    tasks = {t['id']: t for t in TASKS}
    cells = [c for c in matrix() if not args.task or c['task'] == args.task]
    if not args.execute:
        print(json.dumps(cells, indent=2)); return 0
    for key in ['BENCH_WAP_CORE', 'BENCH_KITSUNE_CHECKOUT'] + (['BENCH_WAP_SCRIPT'] if os.getenv('BENCH_WAP_SSH') else []):
        if not os.getenv(key):
            p.error(f'set {key} first (see README)')
    executables = {h: binary(h) for h in MODELS}
    folder = args.out or Path('runs') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    (folder / 'plan.json').write_text(json.dumps(cells, indent=2))
    with (folder / 'results.jsonl').open('x') as out:
        for i, cell in enumerate(cells, 1):
            log = folder / f'{i:03}-{cell["harness"]}-{cell["task"]}-{cell["arm"]}.jsonl'
            print(f'[{i}/{len(cells)}] {log.stem}', flush=True)
            try:
                with settings(cell) as browser:
                    row = attempt(cell, tasks[cell['task']], browser, executables[cell['harness']], log)
            except Exception as exc:
                # Do not leak commands, storage state or credentials. Never count infra errors as task failures.
                out.write(json.dumps(dict(cell, status='infra_error', error=type(exc).__name__)) + '\n')
                print(f'Infrastructure failure: {type(exc).__name__}; stopped. See {folder}', file=sys.stderr)
                return 2
            out.write(json.dumps(dict(cell, **row, transcript=log.name)) + '\n'); out.flush()
            if row['status'] == 'error' and row['error'] != 'timeout':
                return 2  # subscription/agent failure: do not burn through the remaining matrix
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
