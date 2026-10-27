"""Offline comparison protocol/transport tests; no real browser or inference."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.stress_compare import BASELINE, await_stable_extension, comparison_plan, paired_ratios, worker
from kitsune_benchmark.stress_http import HTTPClient, decode_response


class ComparisonTests(unittest.TestCase):
    def test_fixed_profile_has_balanced_pairs(self):
        plan = comparison_plan('shared-browser-v1')
        self.assertEqual(len(plan['schedule']), 24)
        self.assertEqual(plan['duration'], 30)
        for count in plan['clients']:
            rows = [s for s in plan['schedule'] if s['clients'] == count]
            self.assertCountEqual([r['target'] for r in rows], ['kitsune'] * 2 + ['playwright'] * 2)
            self.assertEqual({r['pair_order'] for r in rows}, {'kp', 'pk'})
        with self.assertRaises(ValueError):
            comparison_plan('shared-browser-v1', repeats=3)
        with self.assertRaises(ValueError):
            comparison_plan(clients=[1, 1])

    def test_extension_requires_stable_hello_and_generation(self):
        clock = [0.0]
        sequence = iter([
            {'extension_connected': True, 'extension_generation': 1},
            {'extension_connected': True, 'extension_generation': 1, 'extension_version': '0.7'},
            {'extension_connected': False},
        ])
        def status(*_):
            return next(sequence, {'extension_connected': True, 'extension_generation': 2, 'extension_version': '0.7'})
        with patch('kitsune_benchmark.stress.bridge_status', side_effect=status), \
             patch('kitsune_benchmark.stress.time.monotonic', side_effect=lambda: clock[0]), \
             patch('kitsune_benchmark.stress.time.sleep', side_effect=lambda dt: clock.__setitem__(0, clock[0] + dt)):
            ready = await_stable_extension(12345, 'test', Mock(poll=lambda: None), Mock())
        self.assertEqual(ready['extension_generation'], 2)
        self.assertGreaterEqual(clock[0], 1.75)

    def test_cli_plan_has_no_launch(self):
        with patch('kitsune_benchmark.stress_compare.subprocess.Popen') as spawn, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['stress-compare', '--profile', 'shared-browser-v1']), 0)
        spawn.assert_not_called()
        self.assertFalse(json.loads(out.getvalue())['model_invoked'])

    def test_finite_sse_and_json_id_matching(self):
        answer = {'jsonrpc': '2.0', 'id': 2, 'result': {}}
        self.assertEqual(decode_response(json.dumps(answer).encode(), 'application/json', 2), answer)
        body = b': keepalive\r\n\r\nevent: message\r\ndata: ' + json.dumps(answer).encode() + b'\r\n\r\n'
        self.assertEqual(decode_response(body, 'text/event-stream', 2), answer)
        with self.assertRaises(ValueError):
            decode_response(body, 'text/event-stream', 3)
        with self.assertRaises(ValueError):
            decode_response(body + body, 'text/event-stream', 2)

    def test_real_loopback_http_sessions_notifications_and_delete(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_):
                pass
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append((data['method'], self.headers.get('Mcp-Session-Id'), self.headers.get('Host')))
                if 'id' not in data:
                    self.send_response(202)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                result = {'protocolVersion': '2024-11-05', 'serverInfo': {'name': 'fake'}} if data['method'] == 'initialize' else {'content': []}
                body = b'data: ' + json.dumps({'jsonrpc': '2.0', 'id': data['id'], 'result': result}).encode() + b'\n\n'
                self.send_response(200)
                self.send_header('Mcp-Session-Id', 'private-test-session')
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_DELETE(self):
                seen.append(('DELETE', self.headers.get('Mcp-Session-Id'), None))
                self.send_response(200)
                self.send_header('Content-Length', '0')
                self.end_headers()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = HTTPClient(server.server_port, 1)
        try:
            client.initialize()
            client.call()
            client.close()
            self.assertIsNone(client.close_error)
            self.assertEqual([row[0] for row in seen], ['initialize', 'notifications/initialized', 'tools/call', 'tools/call', 'DELETE'])
            self.assertIsNone(seen[0][1])
            self.assertTrue(all(r[1] == 'private-test-session' for r in seen[1:]))
            self.assertTrue(seen[0][2].startswith('localhost:'))
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            thread.join()

    def test_worker_validates_content_and_records_volume(self):
        class Fake:
            def call(self):
                return {'result': {'structuredContent': {'tabs': [
                    {'index': i, 'url': url, 'current': i == 1} for i, url in enumerate(BASELINE)]}}}
        start = threading.Event()
        start.set()
        with tempfile.TemporaryDirectory() as directory:
            result = worker(Fake(), 'kitsune', 0, start, [time.monotonic() + .02], Path(directory))
        self.assertTrue(result['samples'])
        self.assertEqual(result['errors'], {})
        self.assertGreater(result['json_bytes'], 0)

    def test_ratio_only_uses_complete_valid_pairs(self):
        def row(target, rate, valid=True):
            return {'repeat': 1, 'clients': 2, 'target': target, 'pair_order': 'kp', 'valid': valid,
                    'successful_requests_per_sec': rate, 'latency_sec_success': {'p95': .1},
                    'resources': {'phase/load/all': {'time_weighted_mean_rss_bytes': 100}}}
        self.assertEqual(paired_ratios([row('kitsune', 10)]), [])
        self.assertEqual(paired_ratios([row('kitsune', 10), row('playwright', 20, False)]), [])
        ratios = paired_ratios([row('kitsune', 10), row('playwright', 20)])[0]['ratios_kitsune_over_playwright']
        self.assertEqual(ratios['throughput'], .5)
