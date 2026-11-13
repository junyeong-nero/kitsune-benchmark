"""Offline load runner tests: no browser or model required."""
import io
import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.stress import (Client, SafetyStop, StressCollector, aggregate_levels,
                                      failed, load_worker, percentiles, run_stress, stress_plan)


class StressTests(unittest.TestCase):
    def test_plan_never_spawns(self):
        with patch('kitsune_benchmark.stress.subprocess.Popen') as spawn:
            plan = run_stress(clients=(1, 4))
        spawn.assert_not_called()
        self.assertFalse(plan['model_invoked'])
        self.assertEqual(plan['clients'], [1, 4])

    def test_validation(self):
        for kwargs in ({'clients': ()}, {'clients': (0,)}, {'clients': (129,)},
                       {'duration': float('nan')}, {'timeout': 0}, {'interval': 0},
                       {'idle': float('inf')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_stress(**kwargs)

    def test_fixed_profile_and_schedule(self):
        plan = stress_plan('release-v1')
        self.assertEqual(plan['protocol'], 'stress-v1')
        self.assertEqual(len(plan['schedule']), 18)
        self.assertEqual([s['clients'] for s in plan['schedule'][6:12]], [32, 16, 8, 4, 2, 1])
        self.assertEqual(plan['duration'], 30)
        with self.assertRaises(ValueError):
            stress_plan('release-v1', duration=2)
        for kwargs in ({'repeats': 0}, {'warmup': -1}, {'min_available_mib': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                stress_plan(**kwargs)

    def test_safety_guard_latches(self):
        class Probe:
            errors = 0
            def capture(self):
                return [], {'available_memory_bytes': 100 * 2**20}
        with tempfile.TemporaryDirectory() as directory:
            with StressCollector(Path(directory), min_available_mib=512, max_rss_mib=4096,
                                 probe=Probe()) as resources:
                with self.assertRaises(SafetyStop):
                    resources.check()
                resources.set_phase('cleanup')
            self.assertEqual(resources.stop_reason, 'host_available_memory_below_reserve')

    def test_aggregate_excludes_invalid_runs(self):
        def row(rate, valid):
            return {'clients': 1, 'valid': valid, 'successful_requests_per_sec': rate,
                    'latency_sec_success': {'p95': .01, 'p99': .02},
                    'resources': {'phase/load/all': {'mean_cpu_percent_one_core': 50,
                        'time_weighted_mean_rss_bytes': 100, 'sampled_peak_rss_bytes': 200}}}
        aggregate = aggregate_levels([row(10, True), row(30, True), row(900, False)])[0]
        self.assertEqual(aggregate['valid_repeats'], 2)
        self.assertEqual(aggregate['requests_per_sec'], {'median': 20, 'min': 10, 'max': 30})

    def test_cli_plan(self):
        with patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(main(['stress', '--clients', '1,2']), 0)
        self.assertEqual(json.loads(out.getvalue())['mode'], 'stress_plan_only')

    def test_percentile_nearest_rank(self):
        self.assertEqual(percentiles(range(1, 101)), {'p50': 50, 'p95': 95, 'p99': 99})
        self.assertEqual(percentiles([]), {'p50': None, 'p95': None, 'p99': None})

    def test_errors(self):
        self.assertTrue(failed({'error': {}}))
        self.assertTrue(failed({'result': {'isError': True}}))
        self.assertFalse(failed({'result': {}}))
        self.assertTrue(failed({'result': {'structuredContent': {'error': 'disconnected'}}}))
        self.assertTrue(failed({'result': {'content': [{'type': 'text', 'text': '{"ok":false}'}]}}))

    def test_worker_stops_after_timeout(self):
        class Fake:
            def call(self):
                raise TimeoutError()
        event = threading.Event()
        event.set()
        with tempfile.TemporaryDirectory() as directory:
            samples, errors = load_worker(Fake(), 0, event, [time.monotonic() + 1], Path(directory))
            rows = (Path(directory) / 'requests-0.jsonl').read_text().splitlines()
        self.assertEqual(len(samples), 1)
        self.assertEqual(errors, {'TimeoutError': 1})
        self.assertEqual(len(rows), 1)

    def test_rpc_ignores_notifications_and_matches_id(self):
        client = Client.__new__(Client)
        client.pending, client.serial, client.timeout = queue.Queue(), 0, 0.1
        client.send = lambda message: None
        client.pending.put({'method': 'notifications/progress'})
        client.pending.put({'id': 1, 'result': {'ok': True}})
        self.assertEqual(client.request('tools/list', {})['result'], {'ok': True})
        with self.assertRaises(TimeoutError):
            client.request('tools/list', {})
        client.pending.put(None)
        with self.assertRaises(EOFError):
            client.request('tools/list', {})


if __name__ == '__main__':
    unittest.main()
