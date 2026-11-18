"""Real-browser positive controls for exactly the gallery subset used in four-surface-v1. No models."""
import json
import os
from contextlib import ExitStack
from pathlib import Path
import subprocess
import tempfile
import unittest

from kitsune_benchmark.four_surface import ROOT, fixture_for, plan
from kitsune_benchmark.four_surface_session import Session
from kitsune_benchmark.personal import free_port


@unittest.skipUnless(os.environ.get('FOUR_SURFACE_NATIVE_TEST') == '1', 'opt-in private Firefox, no inference')
class FourSurfaceNativeControls(unittest.TestCase):
    def test_native_cursors_catalog_and_custody(self):
        try:
            from test_coexistence import kitsune_with_user_channel
        except ImportError:
            from tests.test_coexistence import kitsune_with_user_channel
        from unittest.mock import patch
        for target in ('kitsune', 'playwright'):
            cell = next(c for c in plan('pilot')['cells'] if c['surface'] == target)
            with ExitStack() as stack, tempfile.TemporaryDirectory(dir='/tmp') as d:
                f = stack.enter_context(fixture_for(cell, False))
                f.begin(target)
                t = f.trials[f.by_target[target]]
                port = free_port()
                stack.enter_context(patch.dict(os.environ, {'PLAYWRIGHT_BROWSERS_PATH': str(ROOT/'artifacts/browsers'),
                    'KITSUNE_PROJECT': os.environ.get('KITSUNE_PROJECT', str(ROOT.parent/'kitsune'))}))
                cmd = (stack.enter_context(kitsune_with_user_channel(d, port)) if target == 'kitsune' else
                       ['node', str(ROOT/'node_modules/@playwright/mcp/cli.js'), '--isolated', '--headless', '--browser', 'firefox'])
                sess = Session(dict(target=target, upstream=cmd, urls=[t.url(p) for p in t.paths], origin=f.origin,
                                    active_index=t.active_index, bootstrap_url=t.url('/start'), task_tab='agent',
                                    evidence_path=str(Path(d)/'evidence.json'), user_driver={'bidi_url':f'ws://127.0.0.1:{port}'}))
                try:
                    sess.start()
                    sess.request('initialize', {'protocolVersion':'2024-11-05', 'capabilities':{},
                                                'clientInfo':{'name':'fixture-control','version':'1'}})
                    sess.send({'jsonrpc':'2.0','method':'notifications/initialized'})
                    replies = []
                    sess.forward({'id':1,'jsonrpc':'2.0','method':'tools/list'}, replies.append)
                    sess.forward({'id':2,'jsonrpc':'2.0','method':'tools/call',
                                  'params':{'name':'browser_tabs','arguments':{'action':'list'}}}, replies.append)
                    self.assertIn('browser_tabs', sess.evidence['catalog_tools'])
                    self.assertEqual(len(sess.evidence['tab_calls']), 1)
                    self.assertEqual(len(sess.evidence['snapshots']), 2)
                    if target == 'kitsune':
                        self.assertTrue(all(sess.evidence['setup_tabs_owned']))
                    self.assertFalse(replies[-1]['result'].get('isError'))
                finally:
                    sess.close()
                self.assertTrue(sess.evidence['session_closed'])

    def test_isolated_gallery_contracts(self):
        tasks = {r['task']: r for r in plan('main')['cells'] if not r['task'].startswith('pb-')}
        self.assertEqual(len(tasks), 8)
        with ExitStack() as stack, tempfile.TemporaryDirectory() as d:
            trials = {}
            jobs = []
            for task, row in tasks.items():
                fixture = stack.enter_context(fixture_for(row, False))
                fixture.begin('reference')
                trial = fixture.trials[fixture.by_target['reference']]
                trials[task] = trial
                jobs.append({'task': task, 'component': trial.task.component, 'layout': 'isolated',
                             'start': trial.url('/start'), 'page': trial.url(trial.paths[0]), 'data': trial.mine})
            job = Path(d) / 'controls.json'
            job.write_text(json.dumps(jobs))
            env = {**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(ROOT / 'artifacts/browsers')}
            run = subprocess.run(['node', str(ROOT/'scripts/gallery-reference.mjs'), str(job)], cwd=ROOT,
                                 env=env, capture_output=True, text=True, timeout=400, check=True)
            observed = [json.loads(line) for line in run.stdout.splitlines()]
            self.assertCountEqual([r['task'] for r in observed], tasks.keys())
            for r in observed:
                t = trials[r['task']]
                self.assertIsNone(r['error'], r)
                self.assertEqual(r['pageErrors'], [])
                self.assertTrue(t.task.grade(t, t.mine)['success'], r['task'])
