# Scripting-surface schema text (kitsune#521, PR kitsune#523): base vs trim

[Protocol](../experiments/2026-11-11-kitsune-521-schema-trim-ab.md) ·
[Previous run (#519/#520 rerun)](2026-11-11-kitsune-scripting-guide-ab.md)

**Bottom line:** supported by the protocol's rule.

- **Both arms 40/40.** Matched input, trim / base: **0.882** (rule ≤ 0.95). Requests 0.991 (228 → 226),
  list-price cost **0.955** (rule ≤ 1.00), output 0.977. Trim used less input in 33 of 40 cells; the cell median
  is 0.892.
- **First request 7,638 → 6,696** tokens (median, −942, −12.3%). The PR removes 2,942 definition characters.
- **No argument errors in either arm.** There were 0 `InputValidationError` or `validation error` results. Failed
  tool results: base 7, trim 8. None of the failed direct-tool calls came from the trimmed schema text:
  - trim had 2 `stale_ref` (`pb-account-01` r0) and 6 Python failures;
  - base had 7 Python failures.
- **The cleanest estimate of the prefix effect** comes from the 31 cells where neither arm called Python:
  - input **0.902**, requests 158 → 159, cost 0.989;
  - that ~10% matches the first-request saving.
  - The overall 0.882 includes larger Python-path swings in gallery, so read it as noise around that ~10%, not
    extra saving:
    - `ui-infinite` r1: base ran 5 Python calls, 3 of them failed; 0.35.
    - `ui-editor` r0: 0.46.

Two repeats per arm; per-track differences are observations.

## Setup

- `base`: Kitsune main `7b089d9` (`artifacts/vendor/kitsune-521-base-7b089d9/`).
- `trim`: PR #523 `695fdd8`, which is main plus one commit (`artifacts/vendor/kitsune-521-trim-695fdd8/`).
- Both arms ran with `KITSUNE_SCRIPTING=1` and published 14 tools on every run. Both checkouts were clean.
- Runner: `scripts/run-schema-trim-ab.py`, which reuses the original runner's tasks, ABBA order, metrics and
  stops.
- `claude-opus-5-5`, medium, Claude Code 2.1.303, subscription.
- Runs: 3 uncounted smokes passed, then 80/80 counted runs were scorable, with no stop (2026-11-11, KST evening).

## Results

| Track | Cells | Successes B / T | Input | Requests | Cost | Cells with less T input | First request B → T |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| MiniWoB | 14 | 14 / 14 | 0.918 | 1.014 | 1.019 | 12/14 | 7,618 → 6,675 |
| Personal | 14 | 14 / 14 | 0.964 | 1.057 | 0.998 | 10/14 | 7,770 → 6,830 |
| Gallery | 12 | 12 / 12 | 0.737 | 0.881 | 0.837 | 11/12 | 7,638 → 6,696 |
| All | 40 | 40 / 40 | **0.882** | 0.991 | **0.955** | 33/40 | 7,638 → 6,696 |

| Cells | n | Input | Requests B → T | Cost |
| --- | ---: | ---: | --- | ---: |
| No Python call in either arm | 31 | **0.902** | 158 → 159 | 0.989 |
| Python in either arm | 9 | 0.846 | 70 → 67 | 0.897 |
| All except `ui-editor` | 38 | 0.901 | 212 → 212 | 0.976 |

## Python

- **Calls:** base 23 (9 runs), trim 19 (8 runs).
- **Trim's Python failures** were all `TypeError`s from direct-tool argument names used on Python methods:
  - `Tab.find(regex=...)`, `Tab.find(text=...)` and `Tab.snapshot(boxes=True)`;
  - the same `find(regex=...)` error appeared in the previous run, so this is not new to the trim;
  - the Python `Tab` signatures differ from the direct tools' parameters. That is a separate Kitsune
    observation, not caused by this PR.
- **Base's Python failures** came from `ui-editor` and `ui-infinite`.

## Integrity

- **Reward / page-JS patterns:** 2 hits, both `.evaluate(` in trim's `ui-editor` r0. Both are read-only checks
  of the editor text (`innerText`/`value`). The edit itself was `browser_fill_form` + `browser_click`.
- **URL in Python code:** one, the local fixture memo URL in `pb-longpage-01` r1. It stays in the fixture.

## Reading for kitsune#521 / #523

- This A/B supports merging #523. The scripting surface's prefix drops by about 940 tokens per request, with
  no argument errors, the same success and no extra requests where Python is not involved.
- #521's remaining gap to the one-tool surfaces (first request ~6.7k vs 4.8–5.1k) is now mostly:
  - the tool-level descriptions, including `browser_run_python`'s guide;
  - the server instructions;
  - the harness's own system prompt.

## Artifacts

`artifacts/schema-trim-ab-521/{runs.jsonl,smoke.jsonl,analysis.json,driver.log}`; per-run directories under
`artifacts/scripting-ab/` (listed in `runs.jsonl`).
