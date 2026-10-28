# H310: budget-truncated snapshots fill `main` first and leave link URLs out — Kitsune A/B

[Results index](README.md) · [Frozen protocol](../experiments/2026-10-28-h310-snapshot-budget-ab.md) ·
[kitsune#310](https://github.com/junyeong-nero/kitsune/issues/310)

**Verdict: support** under the predeclared rule.

- **Primary input ratio:** **0.768** over 24/24 joint-success crowded pairs (threshold ≤ 0.90).
- **Pooled guard input ratio:** **0.973** (≤ 1.05).
- **Gates:** every gate holds. Both arms succeeded in all 66 runs, with no safety failure.
- **Fewer model requests:** median per-pair request ratio 0.817.
- **Fewer searches:** `browser_find` calls on the primary cells fell from 60 to 18.

## Setup

- **Arms:**
  - A: Kitsune main `f0ca705`.
  - B: `exp/h310-snapshot-budget` `d571963` = A plus one commit.
  - Both were clean worktrees, and their revisions were checked before every run.
- **Harness:** Claude Code `2.1.303` on the subscription, `claude-opus-5-5`, medium.
- **Target:** Kitsune only, fresh profile per run.
- **Benchmark source:** main `c0432ff`. The protocol and driver were frozen in kitsune-benchmark#36 before the
  first run.
- **Run plan:** 66 runs, repeat-major, ABBA/BAAB per cell. Orders run: AB 34, BA 32. No unscorable run, no stop,
  no retry. Total wall time was 30.6 minutes.
- **In-effect check:** all 24 of B's primary runs had a truncated first snapshot with **0** `/url` lines; A's had
  1,920 in total. Neither arm truncated any guard page.

## Primary cells (crowded gallery, variant 0, 4 pairs each)

| Cell | Input A → B | Ratio | Requests A → B | `browser_find` A → B | Per-pair input ratios |
| --- | ---: | ---: | ---: | ---: | --- |
| `ui-sortable` | 609,240 → 362,763 | **0.60** | 35 → 22 | 12 → 0 | 0.74, 0.52, 0.60, 0.57 |
| `mm-label` | 413,139 → 261,385 | **0.63** | 25 → 17 | 8 → 1 | 0.79, 0.63, 0.51, 0.66 |
| `ui-shadow` | 524,488 → 368,265 | **0.70** | 29 → 23 | 7 → 2 | 0.69, 0.69, 0.53, 0.88 |
| `ui-slider` | 424,877 → 356,829 | 0.84 | 26 → 22 | 15 → 11 | 0.71, 0.82, 0.83, 1.03 |
| `ui-rowmenu` | 355,490 → 299,397 | 0.84 | 23 → 19 | 9 → 0 | 0.83, 0.85, 0.80, 0.88 |
| `ui-table` | 705,287 → 680,618 | 0.97 | 39 → 37 | 9 → 4 | 1.13, 0.81, 1.04, 0.89 |
| **All primary** | 3,032,521 → 2,329,257 | **0.768** | 177 → 140 | 60 → 18 | |

Other totals over the 24 primary pairs (A → B):

- MCP calls 256 → 212;
- elapsed 575 s → 490 s;
- output tokens 20,401 → 17,198;
- cache reads 2.69M → 2.03M.

Per cell:

- **Largest gains:** the cells whose controls were entirely past the first snapshot (`ui-sortable`, `mm-label`,
  `ui-shadow`). B's agents acted from the first snapshot instead of searching for the section first.
- **`ui-slider`:** still needs per-step key presses (kitsune#311). That is why its `browser_find` count stays high
  and its gain is smaller.
- **`ui-table`:** the table's rows still need page turns and expansion reads (H18). Seeing the section earlier
  barely changes its cost.

## Guards (not truncated on either arm, 3 pairs each)

| Cell | Input A → B | Ratio | Per-pair ratios |
| --- | ---: | ---: | --- |
| isolated `ui-sortable` | 164,738 → 178,158 | 1.08 | 0.80, 1.25, 1.32 |
| isolated `ui-shadow` | 122,889 → 122,980 | 1.00 | 1.00, 1.00, 1.00 |
| `pb-longpage-01` | 252,516 → 224,684 | 0.89 | 1.00, 0.85, 0.84 |
| **Pooled** | 540,143 → 525,822 | **0.973** | |

No guard snapshot was truncated, so both arms returned identical observations on these pages. The isolated
`ui-sortable` ratio of 1.08 comes from the model's paths (0.80 to 1.32 within the cell), as in H18's guard spread.

## Errors

The model recovered from failed tool calls: A 2, B 3 (`ui-shadow` 1 → 2, `ui-slider` 1 → 1). This is not a gate.
The `ui-shadow` errors are the shadow-root container step `"eN >> .."` (kitsune#312). B's agents reach that form
directly, so they try its container more often.

## Interpretation and limits

- **What changed:** on pages larger than the budget, the first snapshot now carries the content the task needs. The
  saving comes from skipped search-and-scope rounds, not from smaller observations. B's truncated snapshots are about
  as long as A's, about 8.9k vs 9.2k characters.
- **Fixture:** the crowded fixture's 68 links share one URL, which makes `/url` lines unusually costly here.
  - For public pages, the no-model measurement linked from the protocol shows 1.5–2.3× more `main` refs in B's
    first snapshot.
  - This A/B ran no live-site tasks.
- **Scope:** one model, effort and harness; Kitsune only, not compared with Playwright; variant 0 only. Each cell's
  repeats are paired runs, not independent samples of the page.
- **Raw evidence** is private: `artifacts/h310/` (runs.jsonl, analysis.json, driver logs), with pair directories
  under `artifacts/gallery` and `artifacts/personal`.

## Reproduce

The intervention commit `d571963` is kept as the Kitsune tag `h310-intervention`; its branch `exp/h310-snapshot-budget` was deleted after #310 was solved differently by Kitsune #319.

```sh
uv run --locked python scripts/run-h310.py analyze   # from artifacts/h310/runs.jsonl; no browser or model
```
