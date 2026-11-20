import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import urlopen

from scripts import run
from testset.pages import PAGES


class BenchmarkTests(unittest.TestCase):
    def test_codex_configuration_and_receipt(self):
        from framework import codex
        env = {}
        server = {'command':'kitsune', 'env':{'KITSUNE_TOKEN':'secret-value'}}
        argv = codex.command('codex', 'gpt-6.2-sol', {'browser':server}, env, 'task')
        self.assertNotIn('secret-value', ' '.join(argv))
        self.assertEqual(env, server['env'])
        self.assertIn('features.shell_tool=false', argv)
        self.assertIn('features.shell_tool=true', codex.command('codex', 'model', {}, {}, 'task'))

    def test_transcript_summaries(self):
        from framework.transcript import summarize
        events = [{'type':'item.completed','item':{'type':'mcp_tool_call','tool':'browser_click','status':'completed'}},
                  {'type':'item.completed','item':{'type':'mcp_tool_call','tool':'browser_click','status':'failed','error':{'message':'no ref'}}},
                  {'type':'item.completed','item':{'type':'agent_message','text':'done'}},
                  {'type':'turn.completed','usage':{'input_tokens':40,'cached_input_tokens':10,'output_tokens':5}}]
        s = summarize('codex', '\n'.join(map(json.dumps, events)))
        self.assertEqual((s['completed'], s['tool_calls'], s['tools'], s['final_message']), (True, 2, {'browser_click':2}, 'done'))
        self.assertEqual((s['tokens'], s['tool_errors']), ({'input':40,'cached_input':10,'output':5}, [{'tool':'browser_click','message':'no ref'}]))
        self.assertFalse(summarize('codex', '{"type":"turn.failed"}')['completed'])
        events = [{'type':'assistant','message':{'content':[{'type':'tool_use','id':'a','name':'Bash','input':{}}]}},
                  {'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'a','is_error':True,'content':'boom'}]}},
                  {'type':'result','subtype':'success','is_error':False,'num_turns':2,'result':'ok','total_cost_usd':0.1,
                   'usage':{'input_tokens':3,'cache_creation_input_tokens':4,'cache_read_input_tokens':5,'output_tokens':6}}]
        s = summarize('claude', 'not json\n' + '\n'.join(map(json.dumps, events)))
        self.assertEqual((s['completed'], s['tool_calls'], s['turns'], s['final_message']), (True, 1, 2, 'ok'))
        self.assertEqual((s['tokens'], s['tool_errors']), ({'input':12,'cached_input':5,'output':6}, [{'tool':'Bash','message':'boom'}]))

    def test_final_answer_and_wap_plan(self):
        from framework.transcript import final_answer
        self.assertIsNone(final_answer('no marker'))
        self.assertEqual(final_answer('FINAL ANSWER: draft\nmore\nFINAL ANSWER: **Toronto; $412**\n'), 'Toronto; $412')
        self.assertEqual(final_answer('FINAL ANSWER: COMP 210\nCOMP 330'), 'COMP 210\nCOMP 330')
        tasks = run.load_tasks('webarena-pro')
        self.assertEqual(len(tasks), 26)
        self.assertTrue(all(t['suite'] == 'webarena-pro' and t['sites'] and t['intent'] for t in tasks))
        plan = json.loads(subprocess.check_output(['python3', 'scripts/run.py', '--suite', 'webarena-pro', '--task', 'wap-199']))
        self.assertEqual({r['task'] for r in plan}, {'wap-199'})
        self.assertNotEqual(subprocess.run(['python3', 'scripts/run.py', '--task', 'wap-199'], capture_output=True).returncode, 0)

    def test_wap_attempt_grades_state_and_answer(self):
        task = run.load_tasks('webarena-pro')[0]
        calls = []
        def core(cmd, task_id, folder, *rest):
            calls.append((cmd, rest))
            if cmd == 'prepare':
                Path(folder).mkdir(parents=True)
                urls = {s: f'http://localhost:{3000 + i}' for i, s in enumerate(task['sites'])}
                (Path(folder) / 'prepare.json').write_text(json.dumps({'urls': urls, 'credentials': {}}))
                for s in task['sites']:
                    (Path(folder) / f'{s}.json').write_text(json.dumps({'cookies': [{'name': s, 'value': 'v', 'path': '/'}]}))
                return {'ok': True}
            return {'score': 1.0, 'success': rest == ('Denver',), 'nodes': []}
        done = {'type': 'result', 'subtype': 'success', 'is_error': False, 'num_turns': 1, 'result': 'Found it.\nFINAL ANSWER: Denver'}
        seen = {}
        def agent(argv, cwd, env, timeout):
            seen['prompt'] = argv[-1]
            seen['config'] = json.loads((Path(cwd) / 'mcp.json').read_text())
            return {'stdout': json.dumps(done), 'stderr': '', 'returncode': 0, 'timed_out': False}
        with patch.object(run, 'wap_core', core), patch.object(run, 'invoke', agent):
            result = run.attempt(task, 'playwright', {'command': 'pw', 'args': ['--isolated']}, 'claude', 'model', 5)
        self.assertEqual((result['status'], result['answer'], [c[0] for c in calls]), ('pass', 'Denver', ['prepare', 'grade']))
        self.assertIn('FINAL ANSWER', seen['prompt'])
        self.assertIn(task['intent'], seen['prompt'])
        self.assertIn('--storage-state', seen['config']['mcpServers']['browser']['args'])

    def test_launch_page(self):
        from framework.fixture import launch
        with launch() as url:
            with urlopen(url) as response:
                self.assertIn(b'Benchmark task', response.read())

    def test_analysis_report(self):
        from scripts.analyze import report, signature
        base = {'harness':'claude', 'model':'m', 'browser_mode':'isolated', 'task':'dispatch', 'agent_seconds':10}
        rows = [dict(base, arm='kitsune', status='pass', tool_calls=3, tokens={'input':100,'cached_input':50,'output':5}, tools={'browser_tabs':3}),
                dict(base, arm='aside', status='fail', tool_calls=2, tokens={'input':300,'cached_input':0,'output':5}, submissions=[],
                     tool_errors=[{'tool':'Bash','message':'RefStaleError: Ref "e12" is stale'}]*2),
                dict(base, arm='egolite', status='error', phase='setup', error='ValueError', message='no space')]
        text, s = report(rows)
        self.assertEqual((s['claude/kitsune']['pass_rate'], s['claude/aside']['input_tokens_per_pass']), (1, None))
        self.assertIsNone(s['claude/egolite']['mean_tool_calls'])
        self.assertIn('2x `RefStaleError: Ref # is stale`', text)
        self.assertIn('ERR setup', text)
        self.assertEqual(signature('{"error":"timed out","code":"timeout"}'), 'timeout: timed out')

    def test_figure_renders_every_arm(self):
        import xml.etree.ElementTree as ET
        from scripts.figure import render
        cell = {'attempts':12, 'pass':11, 'fail':1, 'error':0, 'mean_input_tokens':50_000, 'mean_tool_calls':4.0}
        svg = render({f'{h}/{a}': cell for h in ('claude','codex') for a in run.ARMS})
        ET.fromstring(svg)
        for name in ('Kitsune', 'Aside', 'EgoLite', 'Playwright MCP', '11/12', '50k', '1 fail'):
            self.assertIn(name, svg)
        self.assertNotIn('<svg xmlns', svg[10:])  # icons inlined as groups, not nested documents

    def test_webarena_pro_figure_uses_its_own_scale_and_shows_misses_plainly(self):
        import xml.etree.ElementTree as ET
        from scripts.figure import render
        cell = {'attempts':26, 'pass':13, 'fail':12, 'error':1, 'mean_input_tokens':400_000, 'mean_tool_calls':20.0}
        both = render({f'{h}/{a}': cell for h in ('claude','codex') for a in run.ARMS}, 'webarena-pro')
        ET.fromstring(both)
        for text in ('13/26', '400k', '20.0', '>800k<', '>40<', 'MCP · isolated Firefox', 'Top / bottom bar:'):
            self.assertIn(text, both)
        # Half the scale: 400k of 800k and 20 of 40 calls. A miss is the usual outcome here, not an alert.
        self.assertIn('width="145.0"', both)
        self.assertIn('width="100.0"', both)
        self.assertNotIn('12 fail', both)
        self.assertNotIn('MCP · your Firefox', both)
        # An agent that has not run is left out, and the other's bar is centered on the row.
        one = render({f'claude/{a}': cell for a in run.ARMS}, 'webarena-pro')
        ET.fromstring(one)
        self.assertNotIn('gpt-6.1-sol', one)
        self.assertNotIn('Top / bottom bar:', one)
        self.assertEqual(one.count('>13/26<'), 4)

    def test_existing_profile_routes_and_isolated_default(self):
        from framework.arms import config
        with patch.dict('os.environ', {}, clear=True), patch('framework.arms.binary', side_effect=str), \
                patch('framework.arms.sys.platform', 'linux'):
            self.assertEqual(config('aside', 'existing-profile')[1:], ['repl','--host','local','--file','-'])
            self.assertEqual(config('egolite', 'existing-profile')[1:], ['nodejs'])
            self.assertEqual(config('playwright', 'existing-profile')['args'], ['--extension'])
            self.assertEqual(config('kitsune', 'existing-profile')['env']['KITSUNE_USER_TABS'], 'read-only')
            with self.assertRaises(ValueError):
                config('aside')
            self.assertIn('--isolated', config('playwright')['args'])
        args = ['python3', 'scripts/run.py', '--task', 'dispatch', '--browser-mode', 'existing-profile']
        for harness, model in [('codex','gpt-6.2-sol'), ('claude','claude-opus-5-5')]:
            rows = json.loads(subprocess.check_output(args + ['--harness', harness, '--model', model]))
            self.assertEqual(len(rows), 4)
            self.assertEqual({(r['browser_mode'],r['model']) for r in rows}, {('existing-profile',model)})

    def test_paired_plan(self):
        plan = json.loads(subprocess.check_output(['python3', 'scripts/run.py', '--repeat', '2']))
        self.assertEqual(set(PAGES), {t['id'] for t in run.TASKS})
        self.assertEqual(len(plan), len(run.TASKS) * 4 * 2)
        for i in range(0, len(plan), 4):
            self.assertEqual({r['arm'] for r in plan[i:i+4]}, set(run.ARMS))
            self.assertEqual(len({(r['task'], r['repeat']) for r in plan[i:i+4]}), 1)

    def test_grades_actual_submissions_not_agent_reply(self):
        for task in run.TASKS:
            for submits, expected_status in [([], 'fail'), ([{'invalid':'value'}], 'fail'),
                                             ([task['expected']], 'pass'), ([task['expected']]*2, 'fail')]:
                with self.subTest(task=task['id'], status=expected_status):
                    def fake_agent(argv, *_):
                        url = argv[-1].split('Fixture: ')[1].splitlines()[0]
                        with urlopen(url) as response:
                            self.assertIn(b'<form', response.read())
                        for values in submits:
                            with urlopen(url, urlencode(values, doseq=True).encode()) as response:
                                self.assertEqual(response.status, 200)
                        done = {'type':'result','subtype':'success','is_error':False,'num_turns':1,'result':'ok'}
                        return {'stdout': json.dumps(done), 'stderr': '', 'returncode': 0, 'timed_out': False}
                    with patch.object(run, 'invoke', fake_agent):
                        result = run.attempt(task, 'playwright', {'command':'unused'}, 'claude', 'model', 5)
                    self.assertEqual(result['status'], expected_status)
        with patch.object(run, 'invoke', lambda *_: {'stdout':'', 'stderr':'x', 'returncode':0, 'timed_out':True}):
            result = run.attempt(run.TASKS[0], 'playwright', {'command':'unused'}, 'claude', 'model', 5)
        self.assertEqual((result['status'], result['graded'], result['error']), ('error', 'fail', 'timeout'))

    def test_cli_surfaces_use_assigned_context_and_clean_up(self):
        from framework.arms import surface
        for arm in ('aside', 'egolite'):
            calls = []
            def vendor(argv, code=None):
                calls.append((argv, code))
                return 'SPACE=72' if code and 'bench-' in code else 'TARGET=AB12' if code and 'listBrowserTabs' in code else 'guide'
            with tempfile.TemporaryDirectory() as tmp, patch('framework.arms.vendor', vendor), \
                    patch('framework.arms.open_in_aside', lambda url: None):
                with self.assertRaises(TimeoutError):
                    with surface(arm, ['/bin/cat'], Path(tmp), 'http://localhost:9999/test') as (servers, tools, allow, hint):
                        self.assertEqual((servers, tools, allow), ({}, 'Bash', 'Bash(./browser:*)'))
                        script = 'console.log("quoted string")'
                        attach = 'await attachBrowserTab("AB12");\n' if arm == 'aside' else ''
                        self.assertEqual(subprocess.check_output([str(Path(tmp)/'browser'), script], text=True), attach+script+'\n')
                        if arm == 'egolite':
                            self.assertIn('taskSpace(72)', hint)
                        raise TimeoutError()
            self.assertIn('listBrowserTabs' if arm == 'aside' else 'finish', calls[-1][1])

    def test_real_ui(self):
        """Optional: use installed Node Playwright + Firefox, without model calls."""
        import os
        if not os.getenv('BENCH_TEST_FIREFOX'):
            self.skipTest('set BENCH_TEST_FIREFOX=1 with Node Playwright and Firefox installed')
        from contextlib import ExitStack
        with ExitStack() as stack:
            cells = [stack.enter_context(run.fixture(t['id'])) for t in run.TASKS]
            subprocess.run(['node', str(Path(__file__).with_name('verify-ui.cjs')), *[u for u,_ in cells]], check=True, timeout=60)
            for task, (_, submitted) in zip(run.TASKS, cells):
                self.assertEqual(submitted, [task['expected']])
