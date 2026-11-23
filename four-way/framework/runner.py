"""Execute one WebArena-Pro cell; the public matrix entry point is benchmark.py."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time

from framework import codex, transcript
from framework.arms import surface
from framework.launch import launch
from framework.procs import GROUP, kill_tree

ROOT = Path(__file__).resolve().parents[1]
POLICY = ('Use only the designated browser and the task websites\' UI. No other websites, tabs you did not open, '
          'profiles, agents, shell commands, filesystem, page evaluation, source, storage, direct HTTP or site API calls. '
          'You are already signed in; do not sign out. The harness owns setup and teardown. If blocked, report it; '
          'do not switch tools.')
FINISH = ('When you are done, end your reply with one line: FINAL ANSWER: <answer>. If the task only asks you to '
          'change something, write FINAL ANSWER: done.')
KEEP = {'HOME','PATH','TMPDIR','LANG','USER','SHELL'}
# Windows: the profile and app-data folders (CLI sign-in), temp, executable lookup and Claude Code's Git Bash.
KEEP_WINDOWS = {'USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA','LOCALAPPDATA','PROGRAMDATA','TEMP','TMP','SYSTEMROOT',
                'SYSTEMDRIVE','WINDIR','COMSPEC','PATHEXT','USERNAME','CLAUDE_CODE_GIT_BASH_PATH'}


def wap_core(*args):
    core = os.environ['BENCH_WAP_CORE']
    ssh = shlex.split(os.environ.get('BENCH_WAP_SSH', ''))
    script = os.environ['BENCH_WAP_SCRIPT'] if ssh else str(ROOT / 'framework/wap_core.py')
    cmd = ['uv', 'run', '--locked', '--directory', core, 'python', script, *args]
    if ssh:
        cmd = [*ssh, 'export PATH=$HOME/.local/bin:$PATH WP_URL_MODE=port; ' + shlex.join(cmd)]
    p = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=900,
                       env={**os.environ, 'WP_URL_MODE': 'port'})
    return json.loads(p.stdout.strip().splitlines()[-1])


def agent(harness, executable, model, surfaced, prompt, folder, timeout):
    servers, tools, allow, _ = surfaced
    env = {k: v for k, v in os.environ.items() if k in KEEP | KEEP_WINDOWS}
    if harness == 'codex':
        cmd = codex.command(executable, model, servers, env, prompt)
    else:
        if harness == 'claude-api':  # API-key billing; the init event's apiKeySource is checked in attempt()
            env['ANTHROPIC_API_KEY'] = os.environ['ANTHROPIC_API_KEY']
        elif 'CLAUDE_CODE_OAUTH_TOKEN' in os.environ:
            env['CLAUDE_CODE_OAUTH_TOKEN'] = os.environ['CLAUDE_CODE_OAUTH_TOKEN']
        config = folder / 'mcp.json'
        config.write_text(json.dumps({'mcpServers': servers}))
        cmd = [executable, '-p', '--model', model, '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
               '--setting-sources', '', '--disable-slash-commands', '--permission-mode', 'dontAsk', '--strict-mcp-config',
               '--mcp-config', str(config), '--tools', tools, '--allowedTools', allow, '--', prompt]
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=folder, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, encoding='utf-8', errors='replace', **GROUP)
    expired = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        expired = True
    finally:
        kill_tree(proc)
        if expired:
            stdout, stderr = proc.communicate()
        proc.wait()
    return stdout, stderr, proc.returncode, expired, round(time.monotonic() - start, 3)


def attempt(cell, task, settings, executable, log):
    with tempfile.TemporaryDirectory(prefix='browser-bench-') as tmp, launch() as launch_url:
        folder = Path(tmp)
        state = (f'/tmp/wap-bench/{folder.name}' if os.environ.get('BENCH_WAP_SSH') else str(folder / 'wap'))
        prep = wap_core('prepare', task['task_id'], state)
        urls = prep['urls']; states = {}
        for site, storage in prep['states'].items():
            states[site] = folder / f'{site}.json'
            states[site].write_text(json.dumps(storage))
        login = dict(states=states, urls=urls, credentials=prep['credentials'], launch=launch_url)
        with surface(cell['arm'], settings, folder, urls[task['sites'][0]], cell['browser_mode'], login) as surfaced:
            sites = '\n'.join(f'- {s}: {urls[s]}' for s in task['sites'])
            prompt = f'{surfaced[3]}\n\nTask websites:\n{sites}\nRules: {POLICY}\nTask: {task["intent"]}\n{FINISH}'
            stdout, stderr, rc, expired, seconds = agent(cell['harness'], executable, cell['model'], surfaced, prompt, folder, cell['timeout'])
        log.write_text(stdout + ('\n# stderr\n' + stderr if stderr else ''), encoding='utf-8')
        summary = transcript.summarize(cell['harness'], stdout)
        answer = summary.get('final_answer') or ''
        grade = wap_core('grade', task['task_id'], state, answer)
        graded = 'pass' if grade['success'] else 'fail'
        error = 'timeout' if expired else f'agent_exit_{rc}' if rc else None if summary['completed'] else 'incomplete'
        billing = {'claude-api': 'ANTHROPIC_API_KEY', 'claude': 'none'}.get(cell['harness'])
        if billing and summary.get('api_key_source') not in (None, billing):
            error = 'billing_mismatch'  # stops the matrix: the cell was not billed as planned
        return dict(summary, graded=graded, status='error' if error else graded, error=error, agent_seconds=seconds,
                    score=grade['score'], answer=answer, rubrics=grade['nodes'])
