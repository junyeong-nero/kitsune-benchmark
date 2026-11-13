"""Stress-only tree discovery must batch, preserve custody and exclude other apps."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from kitsune_benchmark.stress_resources import StressProcessProbe


class StressProbeTests(TestCase):
    def capture(self, known, rows):
        probe = StressProcessProbe()
        probe.known = known.copy()
        iterator = Mock(return_value=[SimpleNamespace(info=row) for row in rows])
        table = {row['pid']: row for row in rows}
        def process(pid):
            row = table[pid]
            return SimpleNamespace(pid=pid, oneshot=nullcontext, create_time=lambda: row['create_time'],
                cpu_times=lambda: SimpleNamespace(user=1, system=2), status=lambda: 'running',
                memory_info=lambda: SimpleNamespace(rss=100))
        with patch('kitsune_benchmark.stress_resources.psutil.process_iter', iterator), \
             patch('kitsune_benchmark.stress_resources.psutil.Process', side_effect=process), \
             patch('kitsune_benchmark.stress_resources.psutil.virtual_memory', return_value=SimpleNamespace(total=10000, available=5000)), \
             patch('kitsune_benchmark.stress_resources.psutil.swap_memory', return_value=SimpleNamespace(used=0)):
            processes, _ = probe.capture()
        iterator.assert_called_once()
        iterator.cache_clear.assert_called_once()
        return probe, processes

    def row(self, pid, ppid, created=1, name='python'):
        return dict(pid=pid, ppid=ppid, create_time=created, name=name)

    def meta(self):
        return dict(component='mcp', owner='kitsune', externally_managed=False)

    def test_descendants_and_reparented_known_child_only(self):
        rows = [self.row(100, 1), self.row(101, 100), self.row(102, 101, name='firefox'),
                self.row(103, 1), self.row(900, 1)]
        probe, processes = self.capture({(100, 1): self.meta(), (103, 1): self.meta()}, rows)
        self.assertCountEqual([p['pid'] for p in processes], [100, 101, 102, 103])
        self.assertEqual(next(p['component'] for p in processes if p['pid'] == 102), 'browser')
        self.assertEqual(probe.errors, 0)

    def test_recycled_root_never_adopts_new_children(self):
        probe, processes = self.capture({(100, 1): self.meta()}, [self.row(100, 1, created=2), self.row(101, 100)])
        self.assertEqual(processes, [])
        self.assertEqual(probe.errors, 0)

    def test_missing_owned_identity_is_an_error(self):
        probe, processes = self.capture({(100, 1): self.meta()}, [self.row(100, 1, created=None)])
        self.assertEqual(processes, [])
        self.assertEqual(probe.errors, 1)
