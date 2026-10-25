"""Offline paired analysis for the representation-only target view experiment."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import statistics

from .disclosure_analysis import trace, paired


def metrics(entry):
    run = entry['pair']['results']['kitsune']
    evaluation = run['benchmark_evaluation']
    attribution = run['token_attribution']
    row = {key: entry[key] for key in ('arm', 'task', 'track', 'layout', 'unit', 'block', 'repeat', 'position')}
    row.update(group='personal' if entry['track'] == 'personal' else 'crowded-ui' if entry['layout'] == 'crowded' else 'isolated-media',
               success=evaluation['task_success'], functional=evaluation['functional_success'], safety=evaluation['safety_pass'],
               v1=evaluation['contracts']['v1_strict_close']['task_success'],
               v2=evaluation['contracts']['v2_agent_tab_cleanup']['task_success'], outcome=evaluation.get('outcome'),
               input=run['usage']['input_tokens'], output=run['usage']['output_tokens'],
               requests=attribution['requests'], calls=run['mcp_calls'], failed_calls=run['failed_mcp_calls'],
               cost=run['list_price_cost_usd'], elapsed=run['elapsed_sec'],
               first_input=attribution['first_request_input_tokens'], prefix=attribution['prefix_x_requests_tokens'],
               history=attribution['history_tokens'],
               formatter_sec=0., native_text_bytes=0, delivered_text_bytes=0,
               formatted=0, fallback=0, interactions=0, media=0, context=0,
               native_calls=0, native_agent_sec=0., screenshot_calls=0, image_blocks=0,
               pair_dir=entry['pair']['pair_dir'])
    event_path = Path(run['run_dir']) / 'events.jsonl'
    row.update(trace(event_path))
    calls = set()
    for line in event_path.read_text().splitlines():
        event = json.loads(line)
        content = event.get('message', {}).get('content', [])
        if not isinstance(content, list):
            continue
        for item in content:
            if item.get('type') == 'tool_use' and item['id'] not in calls:
                calls.add(item['id'])
                row['screenshot_calls'] += item['name'].endswith('__browser_screenshot')
            if item.get('type') == 'tool_result' and isinstance(item.get('content'), list):
                row['image_blocks'] += sum(part.get('type') == 'image' for part in item['content'])
    for line in (Path(entry['pair']['pair_dir']) / 'kitsune-native-rpc.jsonl').read_text().splitlines():
        record = json.loads(line)
        if record['kind'] == 'target_view_delivered':
            for key in ('formatter_sec', 'native_text_bytes', 'delivered_text_bytes', 'formatted', 'fallback', 'interactions', 'media', 'context'):
                row[key] += record.get(key, 0)
        if record['kind'] == 'rpc_completed' and record.get('method') == 'tools/call' and record.get('role') == 'agent':
            row['native_calls'] += 1
            row['native_agent_sec'] += record['duration_sec']
    assert row['requests'] == row['trace_requests']
    return row


SUM_KEYS = ('input', 'output', 'requests', 'calls', 'failed_calls', 'cost', 'elapsed', 'first_input', 'prefix', 'history',
            'formatter_sec', 'native_text_bytes', 'delivered_text_bytes', 'formatted', 'fallback', 'interactions', 'media',
            'context', 'native_calls', 'native_agent_sec', 'screenshot_calls', 'image_blocks', 'snapshot_calls',
            'consecutive_reads', 'multi_tool_requests', 'errors_expect_validation', 'errors_outcome_timeout', 'stale_ref_errors')


def aggregate(rows):
    return {'n': len(rows), 'success': sum(r['success'] for r in rows), 'functional': sum(r['functional'] for r in rows),
            'safety_failures': sum(not r['safety'] for r in rows), 'v1': sum(r['v1'] for r in rows),
            'v2': sum(r['v2'] for r in rows),
            **{key: sum(r.get(key, 0) for r in rows) for key in SUM_KEYS}}


def analyze(path):
    summary = json.loads(path.read_text())
    rows, excluded = [], []
    for entry in summary['runs']:
        result = entry['pair']['results'].get('kitsune', {})
        if not result.get('benchmark_evaluation', {}).get('scorable'):
            excluded.append({k: entry[k] for k in ('task', 'arm', 'repeat', 'unit')})
        else:
            rows.append(metrics(entry))
    groups = {'all': rows, **{group: [r for r in rows if r['group'] == group]
                             for group in ('personal', 'crowded-ui', 'isolated-media')}}
    results = {}
    for name, members in groups.items():
        if not members:
            continue
        complete = {r['block'] for r in members if r['arm'] == 'A'} & {r['block'] for r in members if r['arm'] == 'B'}
        comparisons = paired([r for r in members if r['block'] in complete], 'A', 'B') if complete else None
        results[name] = {'arms': {arm: aggregate([r for r in members if r['arm'] == arm]) for arm in 'AB'},
                         'contrast': comparisons}
    return {'source': str(path), 'state': summary['state'], 'excluded_unscorable': excluded,
            'rows': rows, 'groups': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.summary.resolve())
    with args.output.open('x') as file:
        json.dump(result, file, indent=2)
    print(json.dumps({'state': result['state'], 'groups': result['groups'], 'output': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
