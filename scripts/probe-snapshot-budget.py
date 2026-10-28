"""No-model check for kitsune#310: what the 12,000-character snapshot budget keeps on gallery pages.

usage: uv run --locked python scripts/probe-snapshot-budget.py KITSUNE_DIR OUT_DIR [--layout crowded|isolated|both]
       uv run --locked python scripts/probe-snapshot-budget.py KITSUNE_DIR OUT_DIR --live [URL ...]
       add --reuse to re-analyse captured snapshots without a browser

Gallery mode: for each gallery task (variant 0), opens the task page in a disposable headless Firefox with that
Kitsune checkout and saves two core browser_snapshot results: the default one (truncated at SNAPSHOT_LIMIT) and the
whole snapshot (via `filename`). Live mode does the same for public pages (network access, no login). Then it
replays the budget offline under several strategies (see `strategies`) and reports how much of the task's section
(gallery) or of `main` (live) survives. No model call.

The replay sees neither unrendered DOM grouping nor pre-alias refs, so it keeps more than the extension does
(crowded gallery: 11.9k vs 9.2k characters). `v070_actual` is the measured result; compare strategies with
`document_order`, the replay of the current behavior.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
LIMIT = 12000
MARKER = '- … truncated; browser_find searches the rest'
URL_LINE = re.compile(r'^( *)- /url: "(.*)"$')


def capture(task, layout, out: Path):
    from test_personal import isolated_kitsune
    from kitsune_benchmark.gallery import GalleryServer
    from kitsune_benchmark.personal_session import NativeSession
    with tempfile.TemporaryDirectory(prefix='snapshot-budget-', dir='/tmp') as folder, \
            GalleryServer(task, 0, layout) as fixture:
        fixture.begin('kitsune')
        trial = fixture.trials[fixture.by_target['kitsune']]
        with isolated_kitsune(folder) as upstream:
            session = NativeSession({'target': 'kitsune', 'upstream': upstream,
                'bootstrap_url': trial.url('/start'), 'urls': [trial.url(p) for p in trial.paths],
                'active_index': trial.active_index, 'evidence_path': folder + '/evidence.json', 'origin': fixture.origin})
            try:
                session.start()
                session.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                    'clientInfo': {'name': 'snapshot-budget-probe', 'version': '1'}})
                session.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                session.prepare()
                text = lambda result: next(c['text'] for c in result['content'] if c['type'] == 'text')
                truncated = json.loads(text(session.tool('browser_snapshot', {})))
                full_path = Path(folder) / 'full.yml'
                session.tool('browser_snapshot', {'filename': str(full_path)})
                full = full_path.read_text()
            finally:
                session.close()
    record = {'task': task.id, 'title': task.title, 'layout': layout, 'page_url': truncated.get('url'),
              'truncated': truncated.get('snapshot'), 'truncated_flag': truncated.get('truncated', False), 'full': full}
    (out / f'{task.id}-{layout}.json').write_text(json.dumps(record, ensure_ascii=False, indent=1))
    return record


def parse(snapshot: str):
    lines = [line for line in snapshot.split('\n') if line and line != MARKER]
    indents = [len(line) - len(line.lstrip()) for line in lines]
    parents, stack = [], []
    for i, indent in enumerate(indents):
        while stack and indents[stack[-1]] >= indent:
            stack.pop()
        parents.append(stack[-1] if stack else None)
        stack.append(i)
    return lines, indents, parents


def subtree(indents, start):
    end = start + 1
    while end < len(indents) and indents[end] > indents[start]:
        end += 1
    return range(start, end)


SMALL_BLOCK_LIMIT = 2000  # extension/content/content.js


def cut_points(lines, indents):
    """Indices a bounded snapshot may end before: not strictly inside a small block (content.js `cuts`).
    The indentation tree stands in for the DOM tree."""
    block_limit = min(SMALL_BLOCK_LIMIT, LIMIT / 4)
    inside = [False] * (len(lines) + 1)
    for start in range(len(lines)):
        span = subtree(indents, start)
        cost = sum(len(lines[i]) + 1 for i in span)
        if cost <= block_limit:
            for i in range(start + 1, span.stop):
                inside[i] = True
    return {i for i, split in enumerate(inside) if not split}


def fill(lines, indents, order, budget=LIMIT):
    """Longest prefix of `order` that ends at a cut and fits (content.js, no target). `order` is a list of
    segments in document order; a segment boundary is always a cut."""
    cuts = cut_points(lines, indents)
    kept, used = set(), 0
    for segment in order:
        pending, cost, done = [], used, False
        for k, i in enumerate(segment):
            if k and i in cuts:
                if cost > budget + 1:
                    done = True
                    break
                kept.update(pending)
                used, pending = cost, []
            pending.append(i)
            cost += len(lines[i]) + 1
        if not done and cost <= budget + 1:
            kept.update(pending)
            used = cost
        else:
            return kept
    return kept


def compact_urls(lines, page_url):
    """Same-origin URLs as paths; drop a /url equal to the page URL or to the previous link's URL."""
    origin = re.match(r'^(https?://[^/]+)', page_url or '')
    origin = origin.group(1) if origin else None
    out, previous = [], None
    for line in lines:
        match = URL_LINE.match(line)
        if not match:
            out.append(line)
            continue
        indent, url = match.groups()
        if url == page_url or url == previous:
            previous = url
            continue
        previous = url
        shown = url[len(origin):] or '/' if origin and url.startswith(origin + '/') else url
        out.append(f'{indent}- /url: "{shown}"')
    return out


def landmark_first(lines, indents):
    """`main` subtree first, then everything else in document order."""
    main = next((i for i, line in enumerate(lines) if re.match(r'^ *- main\b', line)), None)
    if main is None:
        return [list(range(len(lines)))]
    first = list(subtree(indents, main))
    rest = set(first)
    return [first, [i for i in range(len(lines)) if i not in rest]]


def strategies(full, page_url):
    b_lines, b_indents, _ = parse(full)
    c_lines, c_indents, _ = parse('\n'.join(compact_urls(b_lines, page_url)))
    # Only a snapshot that would be truncated drops its /url lines; whole, scoped and saved snapshots keep them (#218).
    d_lines, d_indents, _ = parse('\n'.join(line for line in b_lines if not URL_LINE.match(line)))
    return {
        'drop_urls_when_truncated': (d_lines, d_indents, fill(d_lines, d_indents, [list(range(len(d_lines)))])),
        'main_first+drop_urls': (d_lines, d_indents, fill(d_lines, d_indents, landmark_first(d_lines, d_indents))),
        'document_order': (b_lines, b_indents, fill(b_lines, b_indents, [list(range(len(b_lines)))])),
        'compact_urls': (c_lines, c_indents, fill(c_lines, c_indents, [list(range(len(c_lines)))])),
        'main_first': (b_lines, b_indents, fill(b_lines, b_indents, landmark_first(b_lines, b_indents))),
        'main_first+compact_urls': (c_lines, c_indents, fill(c_lines, c_indents, landmark_first(c_lines, c_indents))),
    }


def section_lines(lines, indents, title):
    """The task's own section: from its heading to the next heading at the same depth."""
    start = next((i for i, line in enumerate(lines) if re.match(r'^ *- heading "' + re.escape(title) + '"', line)), None)
    if start is None:
        return []
    end = start + 1
    while end < len(lines) and not (indents[end] <= indents[start] and lines[end].lstrip().startswith('- heading')):
        end += 1
    return list(range(start, end))


def analyse(record):
    out = {'task': record['task'], 'layout': record['layout'], 'full_chars': len(record['full']),
           'v070_truncated': record['truncated_flag']}
    for name, (lines, indents, kept) in strategies(record['full'], record['page_url']).items():
        section = section_lines(lines, indents, record['title'])
        refs = [i for i in section if '[ref=' in lines[i]]
        out[name] = {'section_lines_kept': f'{sum(i in kept for i in section)}/{len(section)}',
                     'section_refs_kept': f'{sum(i in kept for i in refs)}/{len(refs)}',
                     'whole_section': bool(section) and all(i in kept for i in section),
                     'kept_chars': sum(len(lines[i]) + 1 for i in kept)}
    # The real v0.7.0 result, measured on the same section (the ground truth for document_order).
    lines, indents, _ = parse(record['full'])
    section = section_lines(lines, indents, record['title'])
    refs = [i for i in section if '[ref=' in lines[i]]
    actual_lines = set(record['truncated'].split('\n'))
    out['v070_actual'] = {'section_lines_kept': f'{sum(lines[i] in actual_lines for i in section)}/{len(section)}',
                          'section_refs_kept': f'{sum(lines[i] in actual_lines for i in refs)}/{len(refs)}',
                          'whole_section': bool(section) and all(lines[i] in actual_lines for i in section),
                          'kept_chars': len(record['truncated'])}
    # Simulator check. The replay sees no unrendered DOM grouping and no pre-alias refs, so it can keep more lines
    # than v0.7.0; compare it with `v070_actual` per section, not line for line.
    actual = {line for line in record['truncated'].split('\n') if line and line != MARKER}
    lines, _, kept = strategies(record['full'], record['page_url'])['document_order']
    simulated = {lines[i] for i in kept}
    out['simulator_matches_v070'] = (simulated == actual) if record['truncated_flag'] else None
    out['simulator_line_diff'] = len(simulated ^ actual) if record['truncated_flag'] else None
    return out


LIVE_URLS = ('https://en.wikipedia.org/wiki/Firefox',
             'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at',
             'https://store.steampowered.com/app/1030300/Hollow_Knight_Silksong/',
             'https://github.com/junyeong-nero/kitsune',
             'https://www.bbc.com/news')


def capture_live(urls, out: Path):
    import time
    from test_personal import isolated_kitsune
    from kitsune_benchmark.personal_session import NativeSession
    text = lambda result: next(c['text'] for c in result['content'] if c['type'] == 'text')
    records = []
    with tempfile.TemporaryDirectory(prefix='snapshot-budget-live-', dir='/tmp') as folder, \
            isolated_kitsune(folder) as upstream:
        session = NativeSession({'target': 'kitsune', 'upstream': upstream, 'bootstrap_url': 'about:blank',
            'urls': ['about:blank'], 'active_index': 0, 'evidence_path': folder + '/evidence.json',
            'origin': 'http://127.0.0.1'})
        try:
            session.start()
            session.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                'clientInfo': {'name': 'snapshot-budget-probe', 'version': '1'}})
            session.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            session.tool('browser_tabs', {'action': 'new', 'url': 'about:blank'})
            for url in urls:
                session.tool('browser_navigate', {'url': url})
                time.sleep(4)  # let late content render; the same for every page
                truncated = json.loads(text(session.tool('browser_snapshot', {})))
                path = Path(folder) / 'full.yml'
                session.tool('browser_snapshot', {'filename': str(path)})
                name = re.sub(r'[^a-z0-9]+', '-', url.split('//', 1)[1].lower()).strip('-')[:60]
                record = {'name': name, 'url': url, 'page_url': truncated.get('url'), 'truncated': truncated.get('snapshot'),
                          'truncated_flag': truncated.get('truncated', False), 'full': path.read_text()}
                (out / f'live-{name}.json').write_text(json.dumps(record, ensure_ascii=False, indent=1))
                records.append(record)
        finally:
            session.close()
    return records


def analyse_live(record):
    """How many `main` refs each strategy keeps (pages without `main`: the whole page)."""
    def main_refs(lines, indents, kept):
        start = next((i for i, line in enumerate(lines) if re.match(r'^ *- main\b', line)), None)
        span = subtree(indents, start) if start is not None else range(len(lines))
        refs = [i for i in span if '[ref=' in lines[i]]
        return f'{sum(i in kept for i in refs)}/{len(refs)}'
    lines, indents, _ = parse(record['full'])
    actual = set(record['truncated'].split('\n'))
    out = {'page': record['name'], 'full_chars': len(record['full']),
           'url_line_share': round(sum(len(l) + 1 for l in lines if URL_LINE.match(l)) / max(1, len(record['full'])), 3),
           'v070_actual': main_refs(lines, indents, {i for i, line in enumerate(lines) if line in actual})}
    for name, (s_lines, s_indents, kept) in strategies(record['full'], record['page_url']).items():
        out[name] = main_refs(s_lines, s_indents, kept)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kitsune')
    parser.add_argument('out')
    parser.add_argument('--layout', choices=('crowded', 'isolated', 'both'), default='both')
    parser.add_argument('--reuse', action='store_true', help='Analyse already captured snapshots in OUT_DIR')
    parser.add_argument('--live', nargs='*', metavar='URL', help='Public pages instead of the gallery (default: LIVE_URLS)')
    args = parser.parse_args()
    from kitsune_benchmark.gallery import select
    os.environ['KITSUNE_PROJECT'] = str(Path(args.kitsune).resolve())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.live is not None:
        records = ([json.loads(path.read_text()) for path in sorted(out.glob('live-*.json'))] if args.reuse
                   else capture_live(args.live or LIVE_URLS, out))
        rows = [analyse_live(record) for record in records]
        for row in rows:
            print(json.dumps(row, ensure_ascii=False), flush=True)
        (out / 'analysis-live.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    layouts = ('crowded', 'isolated') if args.layout == 'both' else (args.layout,)
    rows = []
    for layout in layouts:
        for task in select():
            path = out / f'{task.id}-{layout}.json'
            if args.reuse and path.exists():
                record = json.loads(path.read_text())
            else:
                try:
                    record = capture(task, layout, out)
                except ValueError:  # sporadic new-tab load timeout (kitsune#293): one retry
                    record = capture(task, layout, out)
            rows.append(analyse(record))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    (out / 'analysis.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
