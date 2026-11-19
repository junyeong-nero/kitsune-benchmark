"""Offline controls; no vendor session or model invocation."""
import collections
import importlib.util
import io
import json
import plistlib
import sys
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from PIL import Image
from kitsune_benchmark import adapter
from kitsune_benchmark.four_surface import ROOT, VendorWorker, config, fixture_for, plan, run_cell
from kitsune_benchmark.specs import Server
from kitsune_benchmark.four_surface_report import chart, measured, records, summarize
from kitsune_benchmark.four_surface_session import Session

spec = importlib.util.spec_from_file_location('four_surface_cli', ROOT / 'scripts/run-four-surface.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def result(cell, **kw):
    return {**cell, 'status': 'completed_unscored', 'valid_evidence': True, 'scorable': True, 'safety': True,
            'functional': True, 'success': True, 'calls': 2, 'elapsed': 5.0, 'input': 100, **kw}


class FourSurfaceTests(unittest.TestCase):
    def test_browser_skills_resolve_inside_the_checkout(self):
        for name in ('kitsune-bench-ego', 'kitsune-bench-aside'):
            with self.subTest(name=name):
                source = ROOT / '.agents/skills' / name / 'SKILL.md'
                link = ROOT / '.claude/skills' / name
                self.assertFalse(link.readlink().is_absolute())
                self.assertEqual((link / 'SKILL.md').resolve(strict=True), source)
                self.assertIn(f'\nname: {name}\n', source.read_text())

    def test_frozen_counts_and_pairing(self):
        for scope, size, tasks in [('pilot', 32, 4), ('main', 320, 20), ('replication', 320, 20), ('release', 12, 3)]:
            matrix = plan(scope)
            cells = matrix['cells']
            self.assertEqual(matrix, plan(scope))
            self.assertEqual(len(cells), size)
            self.assertEqual(len({c['task'] for c in cells}), tasks)
            self.assertEqual({c['variant'] for c in cells}, {int(scope == 'replication')})
            counts = collections.Counter((c['harness'], c['task'], c['repeat']) for c in cells)
            self.assertEqual(set(counts.values()), {2 if scope == 'release' else 4})
            self.assertEqual([c['seq'] for c in cells], list(range(1, size + 1)))
            self.assertEqual(len({(c['task'], c['repeat'], c['arm'], c['model']) for c in cells}), size)
            for task in {c['task'] for c in cells}:
                fixture_for(next(c for c in cells if c['task'] == task), scope == 'release')

    def test_pilot_rejects_duplicates_and_tasks_outside_the_main_set(self):
        cfg = config()
        for pilot in [cfg['pilot'] + cfg['pilot'][:1], cfg['pilot'] + ['extra'], cfg['pilot'][1:] + ['extra']]:
            with patch('kitsune_benchmark.four_surface.config', return_value={**cfg, 'pilot': pilot}), \
                    self.assertRaisesRegex(ValueError, 'task registry'):
                plan('pilot')

    def test_incomplete_unsafe_and_joint_success(self):
        matrix = plan('pilot')
        rows = [result(c) for c in matrix['cells']]
        first = rows[0]
        first.update(success=False, safety=False)
        missing = next(r for r in rows if r['task'] != first['task'] and r['harness'] == first['harness']
                       and r['arm'] == first['arm'])
        missing['input'] = None
        report = summarize(matrix, rows)
        arm = report['models'][first['harness']]['arms'][first['arm']]
        self.assertEqual((arm['started'], arm['measured'], arm['input_known'], arm['unsafe']), (4, 3, 3, 1))
        self.assertEqual(report['models'][first['harness']]['joint_success_cells'], 2)
        self.assertEqual((arm['joint_input'], arm['input_sum']), (200, 300))
        self.assertFalse(measured(missing))
        with self.assertRaises(ValueError):
            summarize(matrix, rows + [first])
        with self.assertRaises(ValueError):
            summarize(matrix, [dict(first, model='wrong')])

    def test_chart_rejects_pilot_and_incomplete_main(self):
        for scope in ('pilot', 'main', 'release'):
            with self.assertRaises(ValueError):
                chart(summarize(plan(scope), []))
        matrix = plan('main')
        figure = chart(summarize(matrix, [result(c) for c in matrix['cells']]))
        self.assertIn('40 shared cells', figure)
        self.assertEqual(figure.count('40/40'), 8)
        ElementTree.fromstring(figure)

    def test_started_cell_is_never_replaced_or_hidden(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            cell = plan('pilot')['cells'][0]
            p = out / 'cell-001'
            p.mkdir()
            adapter.write_json(p/'started.json', cell)
            self.assertEqual(records(out, plan('pilot')), [dict(cell, status='interrupted')])
            adapter.write_json(p/'result.json', dict(cell, task='wrong'))
            with self.assertRaisesRegex(ValueError, 'does not match'):
                records(out, plan('pilot'))

    def test_probe_pins_do_not_relax_the_legacy_defaults(self):
        report = {'prerequisites_ok': True, 'checks': [{'name': 'claude_version', 'detail': 'claude-code 2.1.327'}]}
        with patch.object(adapter.claude_harness, 'diagnose', return_value=report):
            with self.assertRaisesRegex(ValueError, 'pin'):
                adapter.harness_preflight('claude', '/claude', {})
            self.assertEqual(adapter.harness_preflight('claude', '/claude', {}, cli_version='2.1.327'), report)

    def test_vendor_profile_override_is_not_forwarded(self):
        s = Session({'target': 'aside'})
        replies = []
        with patch.object(s, 'request', side_effect=AssertionError('must not forward')):
            s.forward({'id': 1, 'method': 'tools/call', 'params': {'name': 'repl', 'arguments': {'profile_id': 'other'}}},
                      replies.append)
        self.assertTrue(replies[0]['result']['isError'])

    def test_wrong_gui_version_fails_even_with_a_valid_signature(self):
        with TemporaryDirectory() as d, patch.object(cli.subprocess, 'run', return_value=Namespace(returncode=0)):
            props = Path(d)/'Contents/Info.plist'
            props.parent.mkdir()
            with patch.dict(cli.VENDOR_APPS, {'ego':Path(d)}, clear=True):
                props.write_bytes(plistlib.dumps({'CFBundleShortVersionString':config()['vendor_gui_versions']['ego']}))
                cli.check_install()
                props.write_bytes(plistlib.dumps({'CFBundleShortVersionString':'different'}))
                with self.assertRaisesRegex(ValueError,'does not match'):
                    cli.check_install()

    def test_rejected_gui_bundle_blocks_before_vendor_code_or_model_output(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as drop:
            args = Namespace(out=Path(d)/'pilot', scope='pilot', dedicated_worker=True, ego_server_name='bench-unit',
                             aside_profile='aside-test', ego_profile='ego-test', aside_cli=Path(sys.executable),
                             ego_cli=Path(sys.executable), image_drop=Path(drop))
            with patch.dict(cli.VENDOR_APPS, {'ego':Path(d)}, clear=True), \
                    patch.object(cli.subprocess,'run',return_value=Namespace(returncode=1, stderr=b'detritus not allowed')) as signs, \
                    patch.object(cli.ego_mcp,'run_script') as vendor, patch.object(cli,'run_cell') as start, \
                    self.assertRaisesRegex(ValueError,'EgoLite GUI bundle failed strict signature'):
                cli.run(args, plan('pilot'))
            self.assertEqual(signs.call_args.args[0], ['/usr/bin/codesign','--verify','--strict',Path(d)])
            vendor.assert_not_called()
            start.assert_not_called()
            self.assertFalse(args.out.exists())
            self.assertEqual(list(Path(drop).iterdir()), [])

    def test_named_worker_needs_a_denied_file_and_a_real_png_handoff(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as drop, patch.object(cli, 'ROOT', Path(d)), \
                patch.object(cli, 'check_install'), patch.object(cli.secrets, 'token_hex', return_value='unique'), \
                patch.object(cli.secrets, 'token_bytes', return_value=bytes([1,2,3])*4):
            out = Path(drop)/'four-control-unique.png'
            old = Path(drop)/'older.png'
            old.write_bytes(b'do not touch')
            png = io.BytesIO()
            Image.new('RGB',(4,1),(1,2,3)).save(png,format='PNG')
            for value, handoff, ok in [('visible',None,False), ('EACCES',None,False), ('EPERM','corrupt',False),
                                       ('ENOENT','link',False), ('unknown','png',False), ('EACCES','png',True)]:
                def control(binary, code, *, server_name):
                    self.assertEqual((binary,server_name), ('/verified/ego','bench-only'))
                    self.assertIn(str(out), code)
                    self.assertEqual(len(list((Path(d)/'artifacts').iterdir())), 1)
                    if handoff == 'link':
                        out.symlink_to(old)
                    elif handoff:
                        out.write_bytes(png.getvalue() if handoff == 'png' else b'not a PNG')
                    return {'content':[{'text':json.dumps({'privateFileAccess':value})}]}
                with self.subTest(value=value, handoff=handoff), patch.object(cli.ego_mcp,'run_script',side_effect=control):
                    if ok:
                        cli.check_worker('/verified/ego','bench-only',Path(drop))
                    else:
                        with self.assertRaises(ValueError):
                            cli.check_worker('/verified/ego','bench-only',Path(drop))
                    self.assertEqual(old.read_bytes(), b'do not touch')
                    self.assertEqual(list(Path(drop).iterdir()), [old])
                    self.assertEqual(list((Path(d)/'artifacts').iterdir()), [])

    def test_missing_vendor_routes_stop_before_probe_output_or_model(self):
        with TemporaryDirectory() as d, patch.object(cli, 'check_worker') as probe, patch.object(cli, 'run_cell') as start:
            args = Namespace(out=Path(d)/'pilot', scope='pilot', dedicated_worker=True, ego_server_name=None,
                             aside_profile='synthetic-a', ego_profile='synthetic-e', aside_cli=None, ego_cli=None, image_drop=Path(d))
            for name in (None,'','default','x'*65,'bad name','bench-only'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    args.ego_server_name = name
                    cli.run(args, plan('pilot'))
            args.aside_cli = Path(sys.executable)
            with self.assertRaisesRegex(ValueError,'EgoLite test route'):
                cli.run(args, plan('pilot'))
            probe.assert_not_called()
            start.assert_not_called()
            self.assertFalse(args.out.exists())

    def test_model_setup_uses_only_the_preflight_routes_not_the_ambient_defaults(self):
        w = VendorWorker('/test/aside','/test/ego','bench-only','aside-test','ego-test')
        with TemporaryDirectory() as d:
            for target in ('aside','ego'):
                cell = next(c for c in plan('pilot')['cells'] if c['surface'] == target)
                pair_dir = Path(d)/target
                pair_dir.mkdir()

                def capture(**kw):
                    task = kw['task_for_target'](target)
                    spec = kw['prepare_server'](target, Server(target,'ambient',(),('EGO_BROWSER_BIN',)),task,pair_dir)
                    self.assertEqual(spec.env_vars, ())
                    s = json.loads((pair_dir/'session.json').read_text())
                    if target == 'aside':
                        self.assertEqual(s['upstream'][:2], ['/usr/bin/env','-i'])
                        self.assertEqual(s['upstream'][-6:], ['/test/aside','mcp','--host','local','--profile','aside-test'])
                    else:
                        self.assertEqual(s['upstream'][2:], ['--binary','/test/ego','--ego-server-name','bench-only'])
                        self.assertEqual(s['vendor_profile'],'ego-test')
                    raise RuntimeError('captured before model start')
                with patch('kitsune_benchmark.four_surface.source_revision',return_value={'revision':cell['sha'],'dirty':False}), \
                        patch('kitsune_benchmark.four_surface.run_pair',side_effect=capture), \
                        self.assertRaisesRegex(RuntimeError,'captured before model start'):
                    run_cell(cell,Path(d),w,Path(d))

    def test_main_requires_successful_instrumented_pilot(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            pilot = out/'pilot'
            pilot.mkdir()
            provenance = {'test': True}
            images = out/'images'
            images.mkdir()
            args = Namespace(out=out/'main', pilot=pilot, scope='main', kitsune_project=out, release_base=out,
                             aside_profile='bench', ego_profile='bench', image_drop=images, dedicated_worker=True,
                             aside_cli=Path(sys.executable), ego_cli=Path(sys.executable), ego_server_name='bench-only')
            adapter.write_json(pilot/'manifest.json', {'provenance': {**provenance,'image_drop':str(images.resolve())}, 'plan': plan('pilot')})
            with patch.object(cli, 'check_worker'), patch.object(cli, 'pins', return_value=provenance), \
                    patch.object(cli, 'run_cell') as run:
                with self.assertRaisesRegex(ValueError, 'Pilot evidence'):
                    cli.run(args, plan('main'))
                self.assertFalse(args.out.exists())
                run.assert_not_called()
