"""Plan or run a paired local browser benchmark. No model calls without --execute."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from framework import codex, transcript
from framework.arms import ARMS, binary, config, surface
from framework.fixture import fixture

TASKS = json.loads((ROOT / 'testset/tasks.json').read_text())
POLICY = ('Use only the designated browser and the rendered fixture UI. No other tabs, profiles, agents, shell commands, '
          'filesystem, page evaluation, source, storage, direct HTTP, or network inspection. Stop after one submission. '
          'The harness owns teardown. If blocked, report it; do not switch tools.')


def matrix(tasks, arms, repeats):
    for r in range(repeats):
        for i, task in enumerate(tasks):
            start = (i + r) % len(arms)
            for arm in arms[start:] + arms[:start]:
                yield task, arm, r + 1


def kill(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def invoke(argv, cwd, env, timeout):
    """Run the agent; keep partial output on timeout so failures stay analyzable."""
    p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill(p)
        stdout, stderr = p.communicate()
    finally:
        kill(p)
        p.wait()
    return {'stdout': stdout, 'stderr': stderr, 'returncode': p.returncode, 'timed_out': timed_out}


def attempt(task, arm, settings, executable, model, timeout, harness='claude', browser_mode='isolated', log=None):
    env = {k: v for k, v in os.environ.items() if k in {'HOME','PATH','TMPDIR','LANG','USER','SHELL','CLAUDE_CODE_OAUTH_TOKEN'}}
    with tempfile.TemporaryDirectory(prefix='browser-bench-') as tmp, fixture(task['id']) as (url, submissions):
        with surface(arm, settings, Path(tmp), url, browser_mode) as (servers, tools, allow, instructions):
            prompt = f'{instructions}\n\nFixture: {url}\nRules: {POLICY}\nTask: {task["prompt"]}'
            if harness == 'codex':
                env.pop('CLAUDE_CODE_OAUTH_TOKEN', None)
                argv = codex.command(executable, model, servers, env, prompt)
            else:
                mcp_config = Path(tmp) / 'mcp.json'
                mcp_config.write_text(json.dumps({'mcpServers': servers}))
                argv = [executable, '-p', '--model', model, '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
                        '--setting-sources', '', '--disable-slash-commands', '--permission-mode', 'dontAsk',
                        '--strict-mcp-config', '--mcp-config', str(mcp_config),
                        '--tools', tools, '--allowedTools', allow, '--', prompt]
            start = time.monotonic()
            run = invoke(argv, tmp, env, timeout)
            seconds = round(time.monotonic()-start, 3)
    if log:
        log.write_text(run['stdout'] + ('\n# stderr\n' + run['stderr'] if run['stderr'] else ''))
    summary = transcript.summarize(harness, run['stdout'])
    graded = 'pass' if submissions == [task['expected']] else 'fail'
    record = {'status': graded, 'graded': graded, 'submissions': list(submissions), 'agent_seconds': seconds, **summary}
    if run['timed_out'] or run['returncode'] or not summary['completed']:
        record['status'] = 'error'
        record['error'] = 'timeout' if run['timed_out'] else f'agent_exit_{run["returncode"]}' if run['returncode'] else 'incomplete'
        record['stderr_tail'] = run['stderr'][-400:]
    return record


def version(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        return (p.stdout.strip() or p.stderr.strip()).splitlines()[0]
    except (OSError, IndexError, subprocess.SubprocessError):
        return None


def metadata(args):
    versions = {'claude': ['claude', '--version'], 'codex': ['codex', '--version'], 'aside': ['aside', '--version'],
                'egolite': ['ego-browser', '--version'], 'kitsune': ['git', '-C', str(ROOT.parent.parent / 'kitsune'), 'describe', '--always', '--dirty'],
                'playwright-mcp': [str(ROOT.parent / 'node_modules/.bin/playwright-mcp'), '--version']}
    return {'git_revision': version(['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD']),
            'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'harness': args.harness, 'model': args.model,
            'browser_mode': args.modes, 'timeout': args.timeout, 'repeat': args.repeat,
            'versions': {k: version(v) for k, v in versions.items()}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--arm', choices=ARMS, action='append')
    p.add_argument('--task', choices=[t['id'] for t in TASKS], action='append')
    p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--timeout', type=int, default=180, help='Agent time limit per attempt in seconds')
    p.add_argument('--browser-mode', choices=('isolated', 'existing-profile'), default='isolated',
                   help='existing-profile uses the installed products’ normal local browser connection')
    p.add_argument('--arm-mode', action='append', default=[], metavar='ARM=MODE',
                   help='Per-arm browser mode override, e.g. playwright=isolated')
    p.add_argument('--harness', choices=('claude', 'codex'), default='claude')
    p.add_argument('--model', help='Same model ID for every arm; required for execution')
    p.add_argument('--out', type=Path, help='New JSONL file; never appended to or overwritten')
    args = p.parse_args()
    if min(args.repeat, args.timeout) < 1:
        p.error('repeat and timeout must be positive')
    arms = [a for a in ARMS if not args.arm or a in args.arm]
    modes = {a: args.browser_mode for a in ARMS}
    for item in args.arm_mode:
        arm, _, mode = item.partition('=')
        if arm not in ARMS or mode not in ('isolated', 'existing-profile'):
            p.error(f'invalid --arm-mode {item}')
        modes[arm] = mode
    args.modes = {a: modes[a] for a in arms}
    rows = list(matrix([t for t in TASKS if not args.task or t['id'] in args.task], arms, args.repeat))
    if not args.execute:
        print(json.dumps([{'task': t['id'], 'arm': a, 'repeat': r, 'harness': args.harness, 'model': args.model, 'browser_mode': modes[a]} for t,a,r in rows], indent=2))
        return 0
    if not args.model or not args.out:
        p.error('--execute needs --model and --out')
    try:
        executable = binary(args.harness)
        configs = {a: config(a, modes[a]) for a in arms}
    except ValueError as exc:
        p.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    logs = args.out.with_suffix('.transcripts')
    totals = {a: Counter() for a in arms}
    with args.out.open('x') as out:
        logs.mkdir()
        args.out.with_suffix('.meta.json').write_text(json.dumps(metadata(args), indent=2))
        for n, (task, arm, r) in enumerate(rows, 1):
            log = logs / f'{n:03d}-{task["id"]}-{arm}.jsonl'
            try:
                result = attempt(task, arm, configs[arm], executable, args.model, args.timeout, args.harness, modes[arm], log)
                result['transcript'] = f'{logs.name}/{log.name}'
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                # Avoid logging full command lines, fixture URLs or guide contents.
                result = {'status': 'error', 'error': type(exc).__name__, 'phase': 'setup'}
                if isinstance(exc, ValueError):
                    result['message'] = str(exc)[:300]
                if isinstance(exc, subprocess.CalledProcessError):
                    result.update(command=Path(exc.cmd[0]).name, exit_code=exc.returncode, stderr_tail=(exc.stderr or '')[-300:])
                elif isinstance(exc, subprocess.TimeoutExpired):
                    result.update(command=Path(exc.cmd[0]).name, timeout_seconds=exc.timeout)
            record = dict(task=task['id'], arm=arm, repeat=r, harness=args.harness, browser_mode=modes[arm], model=args.model, timeout=args.timeout, **result)
            out.write(json.dumps(record) + '\n'); out.flush()
            totals[arm][result['status']] += 1
            print(arm, task['id'], result['status'], flush=True)
    print(json.dumps(totals, indent=2))
    return int(any(c['error'] or c['fail'] for c in totals.values()))


if __name__ == '__main__':
    sys.exit(main())
