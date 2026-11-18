"""Offline controls; no vendor session or model invocation."""
import collections
import importlib.util
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from kitsune_benchmark import adapter
from kitsune_benchmark.four_surface import ROOT, fixture_for, plan
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

    def test_private_grader_file_must_be_unreachable(self):
        with TemporaryDirectory() as d, patch.object(cli, 'ROOT', Path(d)), patch.object(cli.ego_mcp, 'find_binary', return_value='ego'):
            (Path(d) / 'artifacts').mkdir()
            for value in ('visible', 'EACCES', 'unknown'):
                reply = {'content': [{'text': '{"privateFileAccess":"' + value + '"}'}]}
                with patch.object(cli.ego_mcp, 'run_script', return_value=reply):
                    if value == 'EACCES':
                        cli.check_worker()
                    else:
                        with self.assertRaises(ValueError):
                            cli.check_worker()
            self.assertEqual(list((Path(d) / 'artifacts').iterdir()), [])

    def test_main_requires_successful_instrumented_pilot(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            pilot = out/'pilot'
            pilot.mkdir()
            provenance = {'test': True}
            images = out/'images'
            images.mkdir()
            args = Namespace(out=out/'main', pilot=pilot, scope='main', kitsune_project=out, release_base=out,
                             aside_profile='bench', ego_profile='bench', image_drop=images, dedicated_worker=True)
            adapter.write_json(pilot/'manifest.json', {'provenance': provenance, 'plan': plan('pilot')})
            with patch.object(cli, 'check_worker'), patch.object(cli, 'pins', return_value=provenance), \
                    patch.object(cli, 'run_cell') as run:
                with self.assertRaisesRegex(ValueError, 'Pilot evidence'):
                    cli.run(args, plan('main'))
                self.assertFalse(args.out.exists())
                run.assert_not_called()
