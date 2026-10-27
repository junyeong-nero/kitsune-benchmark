"""Single process-table scan for stress runs; graded tracks keep their existing probe.

psutil.Process.children() can enumerate the whole machine on each call. Doing it
for every known process twice per sample makes observation itself a scaling load.
Only owned rows are returned or persisted; no command lines or environment read.
"""
from collections import defaultdict, deque
import os

import psutil

from .resources import ProcessProbe, component_for


class StressProcessProbe(ProcessProbe):
    def capture(self):
        # Avoid process_iter's cross-sample PID cache; identity is (pid, create_time).
        psutil.process_iter.cache_clear()
        table = {p.info['pid']: p.info for p in psutil.process_iter(
            ['pid', 'ppid', 'create_time', 'name'], ad_value=None)}
        children = defaultdict(list)
        for row in table.values():
            children[row['ppid']].append(row)
        pending = deque(self.known)
        seen = set()
        processes = []
        while pending:
            key = pending.popleft()
            if key in seen or key[0] == os.getpid():
                continue
            seen.add(key)
            row = table.get(key[0])
            if row is None:
                continue  # Exited; never adopt a recycled root PID.
            if row['create_time'] is None:
                self.errors += 1
                continue
            if row['create_time'] != key[1]:
                continue
            meta = self.known[key]
            for child in children[key[0]]:
                if child['create_time'] is None or child['name'] is None:
                    self.errors += 1
                    continue
                child_key = (child['pid'], child['create_time'])
                self.known.setdefault(child_key, {**meta, 'component': component_for(child['name'], meta['component'])})
                pending.append(child_key)
            try:
                p = psutil.Process(key[0])
                with p.oneshot():
                    if p.create_time() != key[1]:
                        continue
                    cpu = p.cpu_times()
                    processes.append({'pid': p.pid, 'create_time': key[1], 'ppid': row['ppid'],
                        'name': row['name'], 'status': p.status(), 'rss_bytes': p.memory_info().rss,
                        'cpu_user_sec': cpu.user, 'cpu_system_sec': cpu.system, **meta})
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                self.errors += 1
        memory, swap = psutil.virtual_memory(), psutil.swap_memory()
        return processes, {'total_memory_bytes': memory.total, 'available_memory_bytes': memory.available,
                           'swap_used_bytes': swap.used, 'logical_cpu_count': psutil.cpu_count()}
