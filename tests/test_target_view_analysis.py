import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark.target_view_analysis import aggregate, analyze


class TargetViewAnalysisTests(unittest.TestCase):
    def test_keeps_failure_v1_and_v2_separate(self):
        result = aggregate([{'success': False, 'functional': True, 'safety': False, 'v1': False, 'v2': True, 'requests': 3},
                            {'success': True, 'functional': True, 'safety': True, 'v1': True, 'v2': True, 'requests': 7}])
        self.assertEqual(result['n'], 2)
        self.assertEqual(result['success'], 1)
        self.assertEqual(result['functional'], 2)
        self.assertEqual((result['v1'], result['v2']), (1, 2))
        self.assertEqual(result['requests'], 10)

    def test_unscorable_not_counted_as_zero_cost_success(self):
        summary = {'state': 'stopped', 'runs': [{'task': 'x', 'arm': 'A', 'repeat': 0, 'unit': 'gallery/x',
                    'pair': {'results': {'kitsune': {'benchmark_evaluation': {'scorable': False}}}}}]}
        with tempfile.TemporaryDirectory() as root, patch('kitsune_benchmark.target_view_analysis.metrics') as mocked:
            path = Path(root) / 'summary.json'
            path.write_text(json.dumps(summary))
            result = analyze(path)
        self.assertEqual(result['state'], 'stopped')
        self.assertEqual(len(result['excluded_unscorable']), 1)
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['groups'], {})
        mocked.assert_not_called()


if __name__ == '__main__':
    unittest.main()
