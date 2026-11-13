"""No-model H18 arm check: collapse markers in the first snapshot of each cell, per Kitsune checkout.

usage: uv run --locked python scripts/probe-h18-collapse.py KITSUNE_DIR [KITSUNE_DIR...]
Disposable headless Firefox per checkout and cell; prints the hidden count of every marker and the number of
checkbox rows listed. No model call.
"""
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
CELLS = [('ui-table', 'isolated'), ('ui-table', 'crowded'), ('ui-infinite', 'isolated'), ('mm-grid', 'isolated')]
MARKER = re.compile(r'… (\d+) more similar items; snapshot ')


def probe(task_id, layout):
    from test_personal import isolated_kitsune
    from kitsune_benchmark.gallery import GalleryServer, select
    from kitsune_benchmark.personal_session import NativeSession
    with tempfile.TemporaryDirectory(prefix='h18-probe-', dir='/tmp') as folder, \
            GalleryServer(select([task_id])[0], 0, layout) as fixture:
        fixture.begin('kitsune')
        trial = fixture.trials[fixture.by_target['kitsune']]
        with isolated_kitsune(folder) as upstream:
            session = NativeSession({'target': 'kitsune', 'upstream': upstream,
                'bootstrap_url': trial.url('/start'), 'urls': [trial.url(p) for p in trial.paths],
                'active_index': trial.active_index, 'evidence_path': folder + '/evidence.json', 'origin': fixture.origin})
            try:
                session.start()
                session.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                    'clientInfo': {'name': 'h18-probe', 'version': '1'}})
                session.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                session.prepare()
                tab_id = next(t['id'] for t in session.inventory() if t['active'])
                result = session.tool('browser_snapshot', {'tab_id': tab_id})
                text = next(c['text'] for c in result['content'] if c['type'] == 'text')
                try:
                    text = json.loads(text).get('snapshot', text)
                except ValueError:
                    pass
                return {'markers': [int(n) for n in MARKER.findall(text)], 'checkbox_lines': text.count('- checkbox "'),
                        'chars': len(text)}
            finally:
                session.close()


def main():
    report = {}
    for project in sys.argv[1:]:
        os.environ['KITSUNE_PROJECT'] = str(Path(project).resolve())
        report[project] = {f'{task}/{layout}': probe(task, layout) for task, layout in CELLS}
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
