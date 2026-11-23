from contextlib import ExitStack, nullcontext, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import urlopen

import local
from fixture import fixture
from framework import procs
from pages import PAGES


def done(stdout='ok'):
    return json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'num_turns': 1, 'result': stdout})


class LocalTests(unittest.TestCase):
    def test_plan_rotates_two_arms_per_task(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(local.main([]), 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(set(PAGES), {t['id'] for t in local.TASKS})
        self.assertEqual(len(plan), 12 * 2)
        self.assertEqual({(c['harness'], c['model']) for c in plan}, {('claude', 'claude-opus-5-5')})
        for i in range(0, len(plan), 2):
            self.assertEqual({c['arm'] for c in plan[i:i + 2]}, set(local.ARMS))
            self.assertEqual(len({c['task'] for c in plan[i:i + 2]}), 1)
        self.assertEqual([c['arm'] for c in plan[:4]], ['playwright', 'kitsune', 'kitsune', 'playwright'])

    def test_grades_actual_submissions_not_agent_reply(self):
        cell = next(local.matrix())
        for task in local.TASKS:
            for submits, expected in [([], 'fail'), ([{'invalid': 'value'}], 'fail'),
                                      ([task['expected']], 'pass'), ([task['expected']] * 2, 'fail')]:
                with self.subTest(task=task['id'], status=expected):
                    def agent(harness, exe, model, surfaced, prompt, folder, timeout):
                        url = prompt.split('Fixture: ')[1].splitlines()[0]
                        with urlopen(url) as response:
                            self.assertIn(b'<form', response.read())
                        for values in submits:
                            with urlopen(url, urlencode(values, doseq=True).encode()) as response:
                                self.assertEqual(response.status, 200)
                        return done('I did it'), '', 0, False, 1.0
                    with tempfile.TemporaryDirectory() as tmp, patch.object(local.runner, 'agent', agent):
                        row = local.attempt(cell, task, {'command': 'unused'}, 'claude', Path(tmp) / 'log')
                    self.assertEqual(row['status'], expected)
        timeout = lambda *_: ('', 'x', None, True, 300.0)
        with tempfile.TemporaryDirectory() as tmp, patch.object(local.runner, 'agent', timeout):
            row = local.attempt(cell, local.TASKS[0], {'command': 'unused'}, 'claude', Path(tmp) / 'log')
        self.assertEqual((row['status'], row['graded'], row['error']), ('error', 'fail', 'timeout'))

    def test_execute_runs_the_selected_cells(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(local, 'claude_binary', lambda: 'claude'), \
                patch.object(local, 'browser', lambda cell, logs: nullcontext({})), \
                patch.object(local, 'attempt', return_value={'status': 'pass'}), redirect_stdout(io.StringIO()):
            out = Path(tmp) / 'out'
            self.assertEqual(local.main(['--execute', '--arm', 'playwright', '--task', 'confirm', '--out', str(out)]), 0)
            rows = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
        self.assertEqual([(r['harness'], r['task'], r['arm']) for r in rows], [('claude', 'confirm', 'playwright')])

    def test_kitsune_cells_require_a_synced_checkout(self):
        stale = subprocess.CompletedProcess([], 1)
        with patch.dict('os.environ', BENCH_KITSUNE_CHECKOUT='checkout'), patch.object(local.subprocess, 'run', return_value=stale) as run, \
                patch.object(local, 'attempt', side_effect=AssertionError), redirect_stdout(io.StringIO()), \
                patch('sys.stderr', io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                local.main(['--execute', '--task', 'confirm', '--arm', 'kitsune'])
        self.assertEqual(run.call_args.args[0], ['uv', 'sync', '--locked', '--check', '--directory', 'checkout'])
        self.assertIn('uv sync --locked', err.getvalue())

    def test_playwright_arm_runs_the_package_script_with_node(self):
        with local.browser({'arm': 'playwright'}, None) as settings:
            self.assertEqual(Path(settings['args'][0]), local.PLAYWRIGHT)
            self.assertIn('--isolated', settings['args'])

    def test_windows_rejects_cmd_shims(self):
        with patch.object(local, 'WINDOWS', True), patch.object(local, 'binary', lambda name: r'C:\npm\claude.cmd'):
            with self.assertRaisesRegex(ValueError, 'BENCH_CLAUDE'):
                local.claude_binary()
        with patch.object(local, 'WINDOWS', True), patch.object(local, 'binary', lambda name: r'C:\bin\claude.exe'):
            self.assertEqual(local.claude_binary(), r'C:\bin\claude.exe')

    def test_kill_tree_stops_a_child_and_its_descendant(self):
        script = ('import subprocess, sys, time; c = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]); '
                  'print(c.pid, flush=True); time.sleep(60)')
        proc = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, text=True, **procs.GROUP)
        child = int(proc.stdout.readline())
        procs.kill_tree(proc)
        self.assertIsNotNone(proc.wait(timeout=10))
        proc.stdout.close()

        def alive():
            if os.name == 'nt':  # os.kill(pid, 0) would terminate the process on Windows
                out = subprocess.run(['tasklist', '/FI', f'PID eq {child}', '/NH'], capture_output=True, text=True).stdout
                return str(child) in out
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                return False
            return True
        for _ in range(50):
            if not alive():
                break
            time.sleep(.1)
        self.assertFalse(alive())

    def test_venv_exe(self):
        expected = Path('v/Scripts/python.exe') if os.name == 'nt' else Path('v/bin/python')
        self.assertEqual(procs.venv_exe('v', 'python'), expected)

    def test_real_ui(self):
        """Optional: drive every fixture through Node Playwright + Firefox, without model calls."""
        if not os.getenv('BENCH_TEST_FIREFOX'):
            self.skipTest('set BENCH_TEST_FIREFOX=1 with Node Playwright and Firefox installed')
        with ExitStack() as stack:
            cells = [stack.enter_context(fixture(t['id'])) for t in local.TASKS]
            subprocess.run(['node', str(local.ROOT / 'local-tasks/verify-ui.cjs'), *[u for u, _ in cells]], check=True,
                           timeout=120)
            for task, (_, submitted) in zip(local.TASKS, cells):
                self.assertEqual(submitted, [task['expected']])
