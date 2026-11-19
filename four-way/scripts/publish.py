"""Build the Hugging Face dataset folder (testset + run logs) and optionally upload it with the `hf` CLI."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from framework.fixture import render
from scripts.analyze import load, report

# Fields with per-row varying keys are stored as JSON strings so the dataset viewer sees one schema.
NESTED = ('submissions', 'tools', 'tool_errors', 'harness_warnings', 'tokens')

CARD = '''---
pretty_name: Kitsune four-way browser agent benchmark
configs:
- config_name: tasks
  data_files: data/tasks.jsonl
- config_name: runs
  data_files: data/runs.jsonl
---
# Four-way browser agent benchmark

One coding-agent harness (Claude Code or Codex) solves the same local web tasks through four browser surfaces:
**Aside CLI REPL**, **EgoLite CLI**, **Playwright MCP** and **Kitsune MCP**. The grader checks the values the
fixture server actually received, not the agent's reply: an attempt passes only with exactly one correct submission.

Framework, runner and analyzer: the `kitsune-benchmark` repository (`scripts/run.py`, `scripts/analyze.py`).

## Configs

- `tasks` ({n_tasks} rows): `id`, `skill`, `prompt`, `expected` (JSON string of the exact submitted form),
  `html` (the complete fixture page served on 127.0.0.1). The tasks are original and small; they are not
  MiniWoB++ or WebArena data, only inspired by their state-based grading.
- `runs` ({n_runs} rows): one row per attempt with `status` (`pass`/`fail`/`error`), `agent_seconds`,
  `tool_calls`, `tools`, `tool_errors`, token usage (`tokens`: input incl. cached, cached_input, output),
  `turns`, `cost_usd` (Claude only) and the agent's final message.

Raw agent event streams (Claude `stream-json`, Codex `--json`) are under `transcripts/`; run metadata
(Git revision, product and CLI versions) in `meta/`. `report.md` is the generated analysis; `findings.md`, when
present, is the hand-written interpretation (Korean).

## Results

{results}

## Caveats

- End-to-end product comparison including each tool's interface, not pure browser latency.
- Browser modes differ: Aside, EgoLite and Kitsune drove the operator's existing local profile; Playwright MCP used
  an isolated headless Firefox because its existing-profile mode needs the Chrome bridge extension.
- CLI arms (Aside, EgoLite) receive one `./browser` script per tool call, which may batch actions; each Aside call is a
  fresh REPL session attached to the fixture tab, so snapshot refs do not survive between calls.
- Codex runs CLI arms without its OS sandbox (seatbelt blocks the products' localhost/keychain/LaunchServices access);
  tool restrictions are instructions, as for Claude Code.
- One repeat per task and harness: small samples, no confidence intervals.
'''


def flat(row, columns):
    """Same columns in every file; nested values as JSON strings."""
    return {k: json.dumps(row[k]) if k in NESTED and k in row else row.get(k) for k in columns}


def build(runs, out, notes=None):
    if out.exists():
        shutil.rmtree(out)
    (out / 'data').mkdir(parents=True)
    tasks = json.loads((ROOT / 'testset/tasks.json').read_text())
    with (out / 'data/tasks.jsonl').open('w') as f:
        for t in tasks:
            f.write(json.dumps({**t, 'expected': json.dumps(t['expected']), 'html': render(t['id'])}) + '\n')
    rows = load(runs)
    columns = list(dict.fromkeys(k for r in rows for k in r))
    # One file: per-file type inference would type a column that is all-null in one run file as null.
    (out / 'data/runs.jsonl').write_text(''.join(json.dumps(flat(r, columns)) + '\n' for r in rows))
    for run in runs:
        meta = run.with_suffix('.meta.json')
        if meta.exists():
            shutil.copy(meta, (out / 'meta').mkdir(exist_ok=True) or out / 'meta' / meta.name)
        logs = run.with_suffix('.transcripts')
        if logs.exists():
            shutil.copytree(logs, out / 'transcripts' / logs.name)
    text, summary = report(rows)
    (out / 'report.md').write_text(text)
    if notes:
        shutil.copy(notes, out / 'findings.md')
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    overview = text.split('## Overview\n\n', 1)[1].split('\n\n', 1)[0]
    (out / 'README.md').write_text(CARD.format(n_tasks=len(tasks), n_runs=len(rows), results=overview +
                                               '\n\nPer-task cells, tool usage and failure analysis: `report.md`.'))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs', nargs='+', type=Path, help='JSONL files from scripts/run.py')
    p.add_argument('--out', type=Path, default=ROOT / 'dist/hf')
    p.add_argument('--notes', type=Path, help='Hand-written analysis to include as findings.md')
    p.add_argument('--repo', help='Upload to this dataset repo, e.g. user/name (created private if missing)')
    args = p.parse_args()
    out = build(args.runs, args.out, args.notes)
    print(f'built {out}')
    if args.repo:
        subprocess.run(['hf', 'repo', 'create', args.repo, '--repo-type', 'dataset', '--private', '--exist-ok'], check=True)
        subprocess.run(['hf', 'upload', args.repo, str(out), '.', '--repo-type', 'dataset',
                        '--delete', '*', '--commit-message', 'Update testset and runs'], check=True)


if __name__ == '__main__':
    main()
