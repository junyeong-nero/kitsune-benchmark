"""Private Firefox controls for the frozen gallery and pilot. Never invokes a model."""
import base64
from contextlib import ExitStack, contextmanager
import io
from itertools import groupby
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image
from kitsune_benchmark.four_surface import ROOT, fixture_for, plan
from kitsune_benchmark.four_surface_session import Session
from kitsune_benchmark.personal import free_port
from kitsune_benchmark.personal_session import result_json
from kitsune_benchmark.viewport import CONTENT_HEIGHT, FIREFOX_CHROME_HEIGHT
from tests.test_personal import agent_tool, isolated_kitsune


@contextmanager
def native_control(cell):
    target = cell['surface']
    with tempfile.TemporaryDirectory(dir='/tmp') as d, ExitStack() as stack:
        f = stack.enter_context(fixture_for(cell, False))
        task = f.begin(target)
        t = f.trials[f.by_target[target]]
        port = free_port()
        stack.enter_context(patch.dict(os.environ, {'PLAYWRIGHT_BROWSERS_PATH': str(ROOT/'artifacts/browsers'),
            'KITSUNE_PROJECT': os.environ.get('KITSUNE_PROJECT', str(ROOT.parent/'kitsune')),
            'KITSUNE_USER_TABS': 'read-only', 'PWTEST_SOCKETS_DIR': d}))
        cmd = (stack.enter_context(isolated_kitsune(d, CONTENT_HEIGHT + FIREFOX_CHROME_HEIGHT, port))
               if target == 'kitsune' else ['node', str(ROOT/'node_modules/@playwright/mcp/cli.js'), '--isolated',
                   '--headless', '--browser', 'firefox', '--viewport-size', '1280x720', '--output-dir', d])
        f.evidence_paths[target] = Path(d)/'evidence.json'
        sess = Session(dict(target=target, upstream=cmd, urls=[t.url(p) for p in t.paths], origin=f.origin,
                            active_index=t.active_index, bootstrap_url=t.url('/start'), task_tab='agent',
                            evidence_path=str(f.evidence_paths[target]), user_driver={'bidi_url':f'ws://127.0.0.1:{port}'}))
        stack.callback(sess.close)
        sess.start()
        sess.request('initialize', {'protocolVersion':'2024-11-05', 'capabilities':{},
                                    'clientInfo':{'name':'fixture-control','version':'1'}})
        sess.send({'jsonrpc':'2.0','method':'notifications/initialized'})
        sess.forward({'id':1,'jsonrpc':'2.0','method':'tools/list'}, lambda reply: None)
        yield f, task, sess


def ui_call(sess, name, **args):
    if name not in sess.evidence['catalog_tools']:
        assert sess.config['target'] == 'kitsune'
        name, args = 'browser_tools_call', {'name': name, 'arguments': args}
    result = agent_tool(sess, name, args)
    if result.get('isError'):
        raise AssertionError(f'{name} failed in the reference path: {result_json(result, "code")}')
    return result


def snapshot(sess):
    r = ui_call(sess, 'browser_snapshot', depth=12)
    return result_json(r, 'snapshot') or '\n'.join(i.get('text', '') for i in r['content'])


def peak_month(png):
    # Read only the rendered image: six groups of tall blue columns, in month order.
    with Image.open(io.BytesIO(png)) as image:
        rgb = image.convert('RGB')
        pixels = rgb.load()
        heights = [sum(b - max(r, g) > 45 for r, g, b in (pixels[x, y] for y in range(rgb.height)))
                   for x in range(rgb.width)]
    bars = [max(group) for colored, group in groupby(heights, key=lambda h: h > 5) if colored]
    assert len(bars) == 6 and bars.count(max(bars)) == 1, 'Chart did not render six bars with a unique peak'
    return str(1 + bars.index(max(bars))) + '월'


def solve_pilot(task, sess):
    def click(selector):
        ui_call(sess, 'browser_click', target=selector)

    if task.id == 'ui-infinite':
        name = re.search("'([^']+)'", task.prompt)[1] + ' 저장'
        if sess.config['target'] == 'kitsune':
            found = ui_call(sess, 'browser_find', text=name, load_more=True)
            assert result_json(found, 'count'), 'Target document not found in the rendered list'
        else:
            for _ in range(14):
                if name in snapshot(sess):
                    break
                ui_call(sess, 'browser_press_key', key='End')
                time.sleep(.5)  # each rendered batch arrives asynchronously
            else:
                raise AssertionError('Target document never appeared in the scrollable list')
        click(f'button[aria-label="{name}"]')
        return
    if task.id == 'mm-chart':
        shot = ui_call(sess, 'browser_take_screenshot', target='img', element='월별 매출 막대 그래프', type='png')
        png = next(i['data'] for i in shot['content'] if i['type'] == 'image')
        month = peak_month(base64.b64decode(png, validate=True))
        click(f'input[value="{month}"]')
        click('button.puzzle-submit')
        return
    text = snapshot(sess)
    if task.id == 'pb-current-04':
        cells = re.findall(r'^\s*- (?:cell|text) "([^"\n]+)"', text, re.M)
        price, name = min((int(p[:-1].replace(',', '')), n) for n, people, p in zip(cells, cells[1:], cells[2:])
                          if (m := re.fullmatch(r'최대 (\d+)명', people)) and int(m[1]) >= 3 and p.endswith('원'))
        fields, title, save = {'플랜': name, '월 요금': str(price)}, '메모', '저장'
    elif task.id == 'pb-handoff-01':
        fields = {key: re.search(key + r': ([^\n"\[]+)', text)[1].strip() for key in ('제목', '날짜', '시각', '장소')}
        title, save = '테스트 캘린더', '초안 저장'
    else:
        raise AssertionError(task.id)
    tab = next(t for t in sess.evidence['initial_tabs'] if t['title'] == title)
    ui_call(sess, 'browser_tabs', action='select', index=tab['id'])
    for label, value in fields.items():
        ui_call(sess, 'browser_type', target=f'input[name="{label}"]', text=value)
    ref = re.search(r'button "' + save + r'" \[ref=([^\]]+)\]', snapshot(sess))
    assert ref, 'No save/draft button in the rendered form'
    click(ref[1])


@unittest.skipUnless(os.environ.get('FOUR_SURFACE_NATIVE_TEST') == '1', 'opt-in private Firefox, no inference')
class FourSurfaceNativeControls(unittest.TestCase):
    def test_four_pilot_goals_through_both_native_relays(self):
        cells = [c for c in plan('pilot')['cells'] if c['surface'] in ('kitsune', 'playwright') and c['harness'] == 'codex']
        self.assertEqual(len(cells), 8)  # plan selects four tasks; no Codex/Claude client is started
        for cell in cells:
            target = cell['surface']
            with self.subTest(surface=target, task=cell['task']):
                with native_control(cell) as (f, task, sess):
                    self.assertIn('browser_tabs', sess.evidence['catalog_tools'])
                    self.assertEqual(sess.evidence['cursor_setup'], 'browser_tabs select')
                    if target == 'kitsune':
                        self.assertTrue(all(sess.evidence['setup_tabs_owned']))
                    solve_pilot(task, sess)
                    calls = len(sess.evidence['tab_calls'])
                    self.assertGreater(calls, 0)
                    self.assertEqual(len(sess.evidence['snapshots']), calls + 1)
                    g = f.evaluate(target, {'execution_status': 'completed_unscored', 'mcp_calls': calls})
                    self.assertEqual((g['scorable'], g['functional_success'], g['safety_pass'], g['task_success']), (True,) * 4)
                    self.assertEqual(g['seeded_tab_custody']['custody'], 'kept')
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
