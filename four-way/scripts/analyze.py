"""Summarize run JSONL files: outcomes, tool calls, tokens and failure causes per harness x arm."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from statistics import mean, median
import sys

ARMS = ('aside', 'egolite', 'playwright', 'kitsune')
MARK = {'pass': 'PASS', 'fail': 'FAIL', 'error': 'ERR'}


def load(paths):
    rows = []
    for path in paths:
        rows += [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return rows


def signature(message):
    """First meaningful line with ids/numbers/paths blanked, so repeats of one problem group together."""
    error, code = re.search(r'"error":"([^"]+)"', message or ''), re.search(r'"code":"([^"]+)"', message or '')
    if error and code:  # JSON tool errors (Kitsune, Playwright)
        return f'{code[1]}: {error[1]}'[:120]
    lines = [l.strip() for l in (message or '').splitlines() if l.strip() and not l.startswith(('#', 'Exit code'))]
    line = lines[0] if lines else (message or '').strip()
    line = re.sub(r'\"(e|f\d*e|@)?\d+\"|\b[0-9A-F]{16,}\b|\d+(\.\d+)?', '#', line)
    return re.sub(r'(/[\w.-]+)+', '<path>', line)[:120]


def fmt(value, digits=0):
    if value is None:
        return '-'
    return f'{value:,.{digits}f}'


def avg(values):
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def summary(rows):
    out = {}
    for (harness, arm), group in sorted(groups(rows).items()):
        ran = [r for r in group if r.get('phase') != 'setup']
        status = Counter(r['status'] for r in group)
        tok = lambda r, k: (r.get('tokens') or {}).get(k)
        passed = [r for r in ran if r['status'] == 'pass']
        out[f'{harness}/{arm}'] = {
            'harness': harness, 'arm': arm, 'attempts': len(group), **{s: status[s] for s in MARK},
            'pass_rate': status['pass'] / len(group),
            'median_seconds': median([r['agent_seconds'] for r in ran]) if ran else None,
            'mean_tool_calls': avg(r.get('tool_calls') for r in ran),
            'mean_tool_errors': avg(len(r.get('tool_errors') or []) for r in ran),
            'mean_input_tokens': avg(tok(r, 'input') for r in ran),
            'mean_cached_input_tokens': avg(tok(r, 'cached_input') for r in ran),
            'mean_output_tokens': avg(tok(r, 'output') for r in ran),
            'total_input_tokens': sum(tok(r, 'input') or 0 for r in ran),
            'total_output_tokens': sum(tok(r, 'output') or 0 for r in ran),
            'input_tokens_per_pass': sum(tok(r, 'input') or 0 for r in ran) / len(passed) if passed else None,
            'mean_cost_usd': avg(r.get('cost_usd') for r in ran),
        }
    return out


def groups(rows):
    g = defaultdict(list)
    for r in rows:
        g[r['harness'], r['arm']].append(r)
    return g


def report(rows):
    s = summary(rows)
    harnesses = sorted({r['harness'] for r in rows})
    arms = [a for a in ARMS if any(r['arm'] == a for r in rows)]
    tasks = list(dict.fromkeys(r['task'] for r in rows))
    lines = ['# Browser benchmark report', '',
             f'{len(rows)} attempts; harness/model: ' +
             ', '.join(sorted({f"{r['harness']}={r['model']}" for r in rows})) + '; browser modes: ' +
             ', '.join(sorted({f"{r['arm']}={r['browser_mode']}" for r in rows})) + '.', '',
             '`pass`: exactly one correct submission. `fail`: wrong/no/duplicate submission. `error`: timeout, agent crash or setup failure (counted in the denominator).',
             'Token means cover attempts where the agent ran. Input includes cached input. For CLI arms (aside, egolite) a tool call is one',
             '`./browser` script, which may batch several page actions; for MCP arms it is one MCP tool call.', '',
             '## Overview', '',
             '| harness | arm | pass | fail | err | pass rate | median s | tool calls | tool errors | input tok | cached | output tok | input tok / pass | cost $ |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for v in s.values():
        lines.append(f"| {v['harness']} | {v['arm']} | {v['pass']} | {v['fail']} | {v['error']} | {v['pass_rate']:.0%} | "
                     f"{fmt(v['median_seconds'], 1)} | {fmt(v['mean_tool_calls'], 1)} | {fmt(v['mean_tool_errors'], 1)} | "
                     f"{fmt(v['mean_input_tokens'])} | {fmt(v['mean_cached_input_tokens'])} | {fmt(v['mean_output_tokens'])} | "
                     f"{fmt(v['input_tokens_per_pass'])} | {fmt(v['mean_cost_usd'], 3)} |")
    by = {(r['harness'], r['task'], r['arm']): r for r in rows}
    for h in harnesses:
        lines += ['', f'## Per task: {h}', '', 'Cell: outcome / tool calls / input kTok / seconds.', '',
                  '| task | ' + ' | '.join(arms) + ' |', '|---|' + '---|' * len(arms)]
        for t in tasks:
            cells = []
            for a in arms:
                r = by.get((h, t, a))
                if not r:
                    cells.append('')
                elif r.get('phase') == 'setup':
                    cells.append('ERR setup')
                else:
                    k = ((r.get('tokens') or {}).get('input') or 0) / 1000
                    cells.append(f"{MARK[r['status']]} / {r.get('tool_calls')} / {k:.0f}k / {r['agent_seconds']:.0f}s")
            lines.append(f'| {t} | ' + ' | '.join(cells) + ' |')
    lines += ['', '## Tool usage', '', 'Total calls per tool across all tasks.', '']
    for (h, a), group in sorted(groups(rows).items()):
        tools = Counter()
        for r in group:
            tools.update(r.get('tools') or {})
        names = ', '.join(f'{re.sub("^mcp__browser__", "", k)} {v}' for k, v in tools.most_common())
        lines.append(f'- **{h}/{a}**: {names or "-"}')
    lines += ['', '## Problems', '', 'Recurring tool errors (normalized first line, count):', '']
    for (h, a), group in sorted(groups(rows).items()):
        sigs = Counter(signature(e.get('message')) for r in group for e in r.get('tool_errors') or [])
        if sigs:
            lines.append(f'- **{h}/{a}**')
            lines += [f'  - {n}x `{sig}`' for sig, n in sigs.most_common(6)]
    lines += ['', 'Unsuccessful attempts:', '']
    for r in rows:
        if r['status'] == 'pass':
            continue
        why = r.get('message') or r.get('error') or ''
        if r.get('phase') != 'setup':
            why = f"submitted {json.dumps(r.get('submissions'))}" + (f"; {r['error']}" if r.get('error') else '')
            first = (r.get('tool_errors') or [{}])[0].get('message')
            if first:
                why += f'; first tool error: `{signature(first)}`'
        final = ' '.join((r.get('final_message') or r.get('stderr_tail') or '').split())[:220]
        lines.append(f"- {r['harness']}/{r['arm']}/{r['task']} {MARK[r['status']]}: {why}" + (f'. Agent: "{final}"' if final else ''))
    return '\n'.join(lines) + '\n', s


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs', nargs='+', type=Path, help='JSONL files from scripts/run.py')
    p.add_argument('--out', type=Path, help='Write report.md and summary.json into this directory')
    args = p.parse_args()
    text, s = report(load(args.runs))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / 'report.md').write_text(text)
        (args.out / 'summary.json').write_text(json.dumps(s, indent=2))
    sys.stdout.write(text)


if __name__ == '__main__':
    main()
