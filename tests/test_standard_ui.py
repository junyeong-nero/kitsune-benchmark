"""Standard UI catalog contracts: real stdio probes, never a model or browser."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from kitsune_benchmark.catalog import preflight_catalog
from kitsune_benchmark.miniwob import UI_TOOLS
from kitsune_benchmark.smoke import run_pair
from kitsune_benchmark.specs import Server

# This native-server stand-in accepts initialize/list only. No fixture seeding/tool call is allowed.
FAKE = r'''
import json, os, sys
pages = json.loads(sys.argv[1])
for line in sys.stdin:
    message = json.loads(line)
    method = message['method']
    if method == 'notifications/initialized': continue
    if method == 'initialize':
        print(json.dumps({'jsonrpc':'2.0','id':'approval','method':'elicitation/create',
            'params':{'requestedSchema':{'properties':{'decision':{'enum':['Approve']}}}}}), flush=True)
        answer = json.loads(sys.stdin.readline())
        assert answer['result']['action'] == 'decline', 'Metadata probes must never approve'
        result = {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},
                  'serverInfo':{'name':'test','version':'1'}, 'instructions':os.environ.get('PROFILE_MARKER')}
    elif method == 'tools/list':
        result = pages[int(message.get('params', {}).get('cursor', '0'))]
    else: raise AssertionError('No browser/tool actions permitted: ' + method)
    print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}), flush=True)
'''


def page(names, **kwargs):
    return {'tools': [{'name': n, 'description': 'native text', 'inputSchema': {'type': 'object'}} for n in names], **kwargs}


class CatalogTests(unittest.TestCase):
    def probe(self, pages, enabled, expected):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'catalog.json'
        self.last_catalog_path = path
        server = Server('kitsune', sys.executable, ('-c', FAKE, json.dumps(pages)), enabled_tools=enabled)
        with patch('kitsune_benchmark.adapter.run', side_effect=AssertionError('no model')):
            preflight_catalog(server, expected, {'PROFILE_MARKER': 'probe environment'}, path)
        return json.loads(path.read_text()), path

    def test_legacy_native_superset_filters_to_exact_ui_catalog(self):
        tools = UI_TOOLS['kitsune']
        record, path = self.probe([page([*tools, 'browser_evaluate', 'browser_tools_call'])], tools, tools)
        self.assertTrue(record['catalog_valid'])
        self.assertFalse(record['model_invoked'])
        self.assertEqual(record['exposed_tools'], sorted(tools))
        self.assertEqual(record['initialize']['instructions'], 'probe environment')
        self.assertEqual(len(record['tools_pages'][0]['tools']), 25)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_default_14_cannot_silently_become_standard_11(self):
        minimal = ('browser_tabs', 'browser_navigate', 'browser_snapshot', 'browser_find', 'browser_click',
                   'browser_type', 'browser_fill_form', 'browser_select_option', 'browser_press_key',
                   'browser_wait_for', 'browser_take_screenshot', 'browser_ask_user', 'browser_resume',
                   'browser_run_python')
        with self.assertRaisesRegex(ValueError, 'Catalog mismatch'):
            self.probe([page(minimal)], UI_TOOLS['kitsune'], UI_TOOLS['kitsune'])
        failed = json.loads(self.last_catalog_path.read_text())
        self.assertFalse(failed['catalog_valid'])
        self.assertFalse(failed['model_invoked'])
        self.assertEqual(len(failed['exposed_tools']), 11)
        self.assertEqual(len(failed['missing_tools']), 12)
        # The native product-default surface itself is valid unfiltered; only the standard UI contract rejects it.
        record, _ = self.probe([page(minimal)], (), minimal)
        self.assertTrue(record['catalog_valid'])
        self.assertEqual(len(record['exposed_tools']), 14)

    def test_pagination_is_complete_before_validation(self):
        record, _ = self.probe([page(['a'], nextCursor='1'), page(['b', 'extra'])], ('a', 'b'), ('a', 'b'))
        self.assertEqual(len(record['tools_pages']), 2)
        self.assertEqual(record['exposed_tools'], ['a', 'b'])

    def test_missing_extra_duplicate_and_looping_catalogs_fail(self):
        for pages, enabled, expected in (([page([])], (), ('a',)), ([page(['a', 'b'])], (), ('a',)),
                                          ([page(['a', 'a'])], ('a',), ('a',)),
                                          ([page(['a'], nextCursor='0')], ('a',), ('a',))):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                self.probe(pages, enabled, expected)

    def test_existing_evidence_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'catalog.json'
            path.write_text('preserve')
            with patch('subprocess.Popen', side_effect=AssertionError('no process')):
                with self.assertRaises(ValueError):
                    preflight_catalog(Server('kitsune', 'unused', ()), ('a',), {}, path)
            self.assertEqual(path.read_text(), 'preserve')


class StandardProfileTests(unittest.TestCase):
    def test_standard_plan_is_explicit_and_does_not_mutate_callers(self):
        env = {'KITSUNE_USER_TABS': 'allow'}
        with patch('subprocess.Popen', side_effect=AssertionError('plan starts no process')):
            plan = run_pair(standard_ui=True, enabled_tools=UI_TOOLS, kitsune_env=env)
        self.assertEqual(plan['kitsune_profile'], 'legacy-ui-23')
        self.assertEqual(plan['kitsune_env'], {**env, 'KITSUNE_SCRIPTING': '0'})
        self.assertEqual(env, {'KITSUNE_USER_TABS': 'allow'})

    def test_standard_profile_rejects_conflicting_surface_or_filter(self):
        for kwargs in ({'kitsune_env': {'KITSUNE_SCRIPTING': '1'}},
                       {'enabled_tools': {'kitsune': ('browser_snapshot',), 'playwright': UI_TOOLS['playwright']}},
                       {'enabled_tools': None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_pair(**{'standard_ui': True, 'enabled_tools': UI_TOOLS, **kwargs})

    def test_all_native_catalogs_are_checked_before_any_agent_or_fixture_seed(self):
        from kitsune_benchmark import smoke
        from kitsune_benchmark.specs import Task
        spec = smoke.experiment()
        for failed_target in ('playwright', 'kitsune', None):
            with self.subTest(failed_target=failed_target), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                root = Path(folder)
                for filename in ('project/extension/manifest.json', 'node_modules/.bin/web-ext',
                                 'node_modules/@playwright/mcp/cli.js', 'firefox'):
                    path = root / filename
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                probes = []
                def probe(server, expected, env, path):
                    probes.append(server.id)
                    self.assertEqual(expected, UI_TOOLS[server.id])
                    self.assertEqual(env['KITSUNE_SCRIPTING'], '0')
                    if server.id == failed_target:
                        raise ValueError('Catalog mismatch')
                def agent(server, *args, **kwargs):
                    self.assertEqual(probes, ['playwright', 'kitsune'])
                    self.assertEqual(smoke.os.environ['KITSUNE_SCRIPTING'], '0')
                    raise RuntimeError('Reached agent boundary without starting a model')
                patches = {'ROOT': root, 'resolve': MagicMock(return_value='unused'),
                           'harness_environment': MagicMock(return_value={}), 'harness_preflight': MagicMock(),
                           'copy_extension': MagicMock(return_value={}), 'source_revision': MagicMock(return_value={}),
                           'benchmark_source': MagicMock(return_value={}),
                           'private_ports': MagicMock(return_value=(51234, 51235)),
                           'await_bridge': MagicMock(), 'terminate_group': MagicMock(),
                           'ResourceCollector': MagicMock(), 'preflight_catalog': probe, 'run': MagicMock(side_effect=agent)}
                for name, value in patches.items():
                    stack.enter_context(patch.object(smoke, name, value))
                stack.enter_context(patch.object(smoke.subprocess, 'run', return_value=MagicMock(stdout=str(root / 'firefox'))))
                stack.enter_context(patch.object(smoke.subprocess, 'Popen'))
                stack.enter_context(patch.object(smoke.time, 'sleep'))
                stack.enter_context(patch.object(smoke.os, 'environ', {}))
                begin = MagicMock(return_value=Task('test', 'test'))
                with self.assertRaisesRegex(ValueError if failed_target else RuntimeError,
                                            'Catalog mismatch' if failed_target else 'Reached agent boundary'):
                    run_pair(execute=True, kitsune_project=str(root / 'project'), standard_ui=True,
                             enabled_tools=UI_TOOLS, task_for_target=begin, experiment_spec=spec)
                if failed_target:
                    patches['run'].assert_not_called()
                    begin.assert_not_called()
                else:
                    self.assertEqual(patches['run'].call_count, 1)
                manifest = json.loads(next(root.glob('artifacts/smoke/*/pair-manifest.json')).read_text())
                self.assertEqual(manifest['kitsune_profile'], 'legacy-ui-23')
                self.assertEqual(manifest['kitsune_env'], {'KITSUNE_SCRIPTING': '0'})
                self.assertNotIn('KITSUNE_SCRIPTING', smoke.os.environ)

    def test_standard_track_plans_and_execution_routes_select_the_profile(self):
        from kitsune_benchmark import coexistence, external, gallery, personal, smoke
        cases = ((personal, 'run_personal', 'PersonalServer', 'pb-current-01'),
                 (gallery, 'run_gallery', 'GalleryServer', 'ui-table'),
                 (coexistence, 'run_coexistence', 'CoexistenceServer', 'co-typing-01'),
                 (external, 'run_external', 'BenchmarkServer', 'mw-click-test-2'),
                 (external, 'run_external', None, 'live-mdn-array-at-firefox'))
        for module, function, fixture_class, task in cases:
            with self.subTest(function=function, task=task), ExitStack() as stack:
                runner = getattr(module, function)
                with patch('subprocess.Popen', side_effect=AssertionError('no process in plan')):
                    self.assertEqual(runner(task_ids=[task])['kitsune_profile'], 'legacy-ui-23')
                if fixture_class:
                    fixture = stack.enter_context(patch.object(module, fixture_class)).return_value.__enter__.return_value
                    fixture.bidi_ports = {'kitsune': 51234}
                    fixture.kitsune_bidi_port = 51234
                stack.enter_context(patch.object(module if module is not gallery else smoke, 'source_revision', return_value={}))
                if module is gallery:
                    stack.enter_context(patch.object(gallery.media, 'font'))
                if module is external:
                    stack.enter_context(patch.object(external, 'verify_source'))
                    stack.enter_context(patch.object(external, 'task_sha256', return_value='hash'))
                paired = stack.enter_context(patch.object(module if module is not gallery else smoke, 'run_pair',
                                                         side_effect=RuntimeError('before model')))
                with self.assertRaisesRegex(RuntimeError, 'before model'):
                    runner(execute=True, task_ids=[task])
                self.assertTrue(paired.call_args.kwargs['standard_ui'])

    def test_nonstandard_experiments_keep_their_existing_configuration(self):
        plan = run_pair(kitsune_env={'KITSUNE_SCRIPTING': '1'}, enabled_tools=None)
        self.assertNotIn('kitsune_profile', plan)
        plan = run_pair(standard_ui=True, enabled_tools=UI_TOOLS, targets=('playwright',))
        self.assertNotIn('kitsune_env', plan)


if __name__ == '__main__':
    unittest.main()
