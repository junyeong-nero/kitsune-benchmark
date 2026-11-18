"""Aggregate only matching planned cells. Missing usage is never a zero-cost run."""
from __future__ import annotations

import json
import statistics


def measured(row):
    return (row.get('status') == 'completed_unscored' and row.get('scorable') is True
            and row.get('valid_evidence') is True and type(row.get('safety')) is bool
            and type(row.get('success')) is bool and type(row.get('input')) is int
            and row['input'] > 0 and isinstance(row.get('elapsed'), (int, float)) and row['elapsed'] > 0)


def records(out, matrix):
    rows = []
    for cell in matrix['cells']:
        folder = out / f"cell-{cell['seq']:03d}"
        if not folder.exists():
            continue
        if not (folder/'started.json').is_file() or json.loads((folder/'started.json').read_text()) != cell:
            raise ValueError('Started cell does not match the frozen plan')
        result = folder/'result.json'
        if not result.exists():
            rows.append({**cell, 'status':'interrupted'})
            continue
        row = json.loads(result.read_text())
        if any(row.get(k) != v for k,v in cell.items()):
            raise ValueError('Result does not match the planned cell')
        rows.append(row)
    return rows


def summarize(matrix, rows):
    planned = matrix['cells']
    expected = {r['seq']:r for r in planned}
    seen = set()
    for r in rows:
        seq = r['seq']
        if seq in seen or seq not in expected or any(r.get(k)!=v for k,v in expected[seq].items()):
            raise ValueError('Duplicate or mismatched cell')
        seen.add(seq)
    report = {'benchmark':matrix['id'], 'scope':matrix['scope'], 'planned':len(planned), 'started':len(rows),
              'measured':sum(map(measured, rows)), 'models':{}}
    for h in dict.fromkeys(r['harness'] for r in planned):
        targets = list(dict.fromkeys(r['arm'] for r in planned if r['harness']==h))
        per_arm = {a:[r for r in rows if r['harness']==h and r['arm']==a] for a in targets}
        def key(r):
            return r['task'], r['variant'], r['repeat']
        joint = set.intersection(*[{key(r) for r in rr if measured(r) and r['success'] and r['safety']}
                                   for rr in per_arm.values()])
        arms = {}
        for arm, rr in per_arm.items():
            valid = [r for r in rr if measured(r)]
            shared = [r for r in valid if key(r) in joint]
            inputs = [r['input'] for r in rr if type(r.get('input')) is int]
            times = [r['elapsed'] for r in rr if isinstance(r.get('elapsed'),(int,float))]
            arms[arm] = {'planned':sum(r['harness']==h and r['arm']==arm for r in planned), 'started':len(rr),
                         'scorable':sum(r.get('scorable') is True for r in rr), 'measured':len(valid),
                         'functional':sum(r.get('functional') is True for r in valid),
                         'success':sum(r['success'] for r in valid), 'unsafe':sum(r.get('safety') is False for r in rr),
                         'input_known':len(inputs), 'input_sum':sum(inputs) if inputs else None,
                         'elapsed_known':len(times), 'elapsed_sum':round(sum(times),3) if times else None,
                         'joint_input':sum(r['input'] for r in shared) if shared else None,
                         'joint_elapsed':round(sum(r['elapsed'] for r in shared),3) if shared else None,
                         'joint_median_calls':statistics.median(r['calls'] for r in shared) if shared else None}
        report['models'][h] = {'joint_success_cells':len(joint), 'arms':arms}
    if matrix['scope'] == 'release':
        report['release_cases'] = [
            {'model': r['model'], 'task': r['task'], 'arm': r['arm'], 'measured': measured(r),
             'success': r.get('success'), 'safe': r.get('safety'), 'channel_complete': r.get('user_channel_complete'),
             'input_intact': (r.get('user_input') or {}).get('user_input_intact'),
             'view_transitions_away': (r.get('user_view') or {}).get('view_transitions_away'),
             'view_away_after_calls': (r.get('user_view') or {}).get('view_left_initial_after_calls')}
            for r in rows]
    return report


def chart(report):
    """Render only a complete MAIN result; pilots, partials and release A/Bs cannot become README figures."""
    from html import escape
    if (report['scope']!='main' or report['planned']!=320 or report['measured']!=report['planned']
            or report['started']!=report['planned']):
        raise ValueError('README chart requires all 320 measured main cells')
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 400" role="img" aria-labelledby="title desc">',
             '<title id="title">Four-surface task success</title><desc id="desc">20 synthetic tasks, two starts each. '
             'Counts include only functional successes that also pass custody and safety.</desc>',
             '<rect width="960" height="400" fill="#18202c"/>',
             '<g fill="white" font-family="system-ui,sans-serif"><text x="24" y="40" font-size="24">Four-surface benchmark · task success</text>',
             '<text x="24" y="68" font-size="15">20 tasks × 2 repeats per surface and model · higher is better</text>']
    for x,h,label in [(24,'codex','Codex · GPT-6.2-Sol'),(500,'claude','Claude Code · Opus 5.5')]:
        model = report['models'][h]
        parts.append(f'<text x="{x}" y="111" font-size="19">{label}</text>')
        parts.append(f'<text x="{x}" y="136" font-size="13">Surface</text><text x="{x+130}" y="136" font-size="13">Success</text>'
                     f'<text x="{x+277}" y="136" font-size="13">Input · {model["joint_success_cells"]} shared cells</text>')
        for i,(a,name) in enumerate([('ego','EgoLite'),('aside','Aside'),('playwright','Playwright MCP'),('kitsune','Kitsune')]):
            r = report['models'][h]['arms'][a]
            if r['measured']!=40 or r['planned']!=40 or r['unsafe'] or not 0<=r['success']<=40:
                raise ValueError('Unexpected panel denominators')
            y=166+i*43
            input_text = f'{r["joint_input"]:,}' if r['joint_input'] is not None else 'n/a'
            parts.extend([f'<text x="{x}" y="{y}" font-size="15">{escape(name)}</text>',
                          f'<rect x="{x+130}" y="{y-11}" width="{r["success"]*2}" height="11" fill="#70b4db"/>',
                          f'<text x="{x+216}" y="{y}" font-size="14">{r["success"]}/40</text>',
                          f'<text x="{x+277}" y="{y}" font-size="15">{input_text}</text>'])
    return '\n'.join(parts+['<text x="24" y="344" font-size="14">Input includes cache reads; compare only within a model on cells all four solved. Not billed cost.</text>',
                            '<text x="24" y="371" font-size="14">Local fixtures · writable task tabs · separate from the Kitsune-only release check</text></g></svg>\n'])
