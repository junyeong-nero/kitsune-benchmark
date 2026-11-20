"""Export public numeric metrics from a private results.jsonl (or summarize an exported CSV)."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from statistics import median

FIELDS = ('harness','model','split','task','arm','status','score','agent_seconds','tool_calls','tool_errors','input','cached_input','output')


def metrics(row):
    tokens = row.get('tokens') or {}
    return {**{k: row.get(k) for k in FIELDS[:9]}, 'tool_errors': len(row.get('tool_errors') or []),
            **{k: tokens.get(k) for k in FIELDS[-3:]}}


def export(rows, path):
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader(); writer.writerows(metrics(r) for r in rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path); p.add_argument('--csv', type=Path)
    args = p.parse_args()
    if args.source.suffix == '.csv':
        if args.csv: p.error('--csv requires a results.jsonl source')
        with args.source.open() as f: rows = list(csv.DictReader(f))
    else:
        raw = [json.loads(line) for line in args.source.read_text().splitlines() if line.strip()]
        if args.csv: export(raw, args.csv)
        rows = list(map(metrics, raw))
    groups = defaultdict(list)
    for r in rows: groups[r['harness'], r['arm']].append(r)
    for key, group in groups.items():
        times = [float(r['agent_seconds']) for r in group if r['agent_seconds'] not in ('', None)]
        print(*key, dict(Counter(r['status'] for r in group)), 'input:', sum(int(r['input'] or 0) for r in group),
              'usage receipts:', sum(r['input'] not in ('', None) for r in group), 'median seconds:', median(times) if times else '-')


if __name__ == '__main__': main()
