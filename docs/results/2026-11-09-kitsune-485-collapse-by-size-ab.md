# kitsune#485: collapse a similar-item run by size, not count — Kitsune A/B

[Results index](README.md) · [Results by Kitsune version](kitsune-versions.md) ·
[Frozen protocol](../experiments/2026-11-08-kitsune-485-collapse-by-size-ab.md) ·
[H18, the earlier collapse A/B](2026-10-28-h18-collapse-ab.md) · Upstream: kitsune#485, kitsune PR #493

**Verdict: `inconclusive` under the predeclared rule**, as H18 was, and for the same reason.

- **On the target cells the change did what kitsune#485 asks.**
  - Expansion reads fell from **25 to 0**, and markers hiding 3–5 items from 312 to 0.
  - Requests fell from 237 to 180, and target input ratio was **0.743**. The median per-pair request ratio was 0.75.
  - All 32 target pairs succeeded, with no safety failures and no recovered errors in either arm.
- **Both guard input ratios exceed 1.05:** `ui-infinite` **1.113** and `pb-longpage-01` **1.082**. In every guard
  pair, the tool results stayed identical between the arms until the two runs took different paths. B's extra requests
  were a `browser_tabs list` (2 `ui-infinite` runs) and an extra `browser_find` (2 `pb-longpage-01` runs), each
  chosen before the change could have shown anything different (see [guards](#guards)). The rule does not exempt
  them.

## Setup

- 2026-11-09 15:11–15:49 KST, 80 agent runs, **all scorable**, no retries, no stop. Driver wall time 38.3 min.
  The protocol file is dated 2026-11-08 (UTC); it was committed (`ba69135`) before the first run.
- Arms, Kitsune target only:
  - **A:** `85b50d2` (main, `v0.7.3-18-g85b50d2`: `ad04bac` plus #489–#492). The frozen protocol says
    "v0.7.3 + 14", a counting error; the revision is the one it names.
  - **B:** `357456e` = `85b50d2` + kitsune PR #493. A hidden stretch that the count rule (#458) would collapse is
    listed when its lines total at most 600 characters as the agent reads them.
  - Both arms ran from clean detached worktrees on every run, with one identical tool surface.
- Benchmark `taskset-v3.5-10-g3ba6f61` + protocol commit. Primary contract `v2_agent_tab_cleanup`. Claude Code
  2.1.303 on the claude.ai subscription, `claude-opus-5-5`, effort medium. Client list-price estimate $9.13 (not a
  charge on the subscription).
- Cells, 4 repeats per arm, ABBA/BAAB, with 20 AB and 20 BA runs per arm:
  - **Target:** `ui-table` v0–2 and `mm-grid` v0, each crowded and isolated.
  - **Guards:** `ui-infinite` v0 isolated and `pb-longpage-01` v0.
- **Arm check:**
  - On target cells, A returned 312 markers hiding 3–5 items and B returned 0. B returned no markers at all on
    target cells, crowded included.
  - The in-run stop (a marker hiding ≤ 5 items in a B run of isolated `ui-table`) never fired.

## Decision criteria

| Criterion | Threshold | Measured | Result |
| --- | --- | --- | --- |
| Jointly successful target pairs | ≥ 26/32 | 32/32 (40/40 overall) | met |
| Successes and safety failures, every cell | B ≥ A, B ≤ A | 40/40 vs 40/40; 0 vs 0 | met |
| Expansion reads on target runs | B lower than A (else reject); B = 0 (support) | **25 → 0** | support side |
| Target input ratio | > 1.00 rejects | **0.743** | not rejected |
| Guard input ratio, every guard cell | ≤ 1.05 | `ui-infinite` **1.113**, `pb-longpage-01` **1.082** | **not met** |

No reject condition holds and one support condition fails, so the verdict is inconclusive. Recovered errors (reported,
not gated): 0 vs 0.

## Target cells

Totals over the jointly successful pairs. Input includes cache read and cache write.

| | `ui-table` isolated A / B | `ui-table` crowded A / B | `mm-grid` isolated A / B | `mm-grid` crowded A / B |
| --- | ---: | ---: | ---: | ---: |
| Pairs | 12 | 12 | 4 | 4 |
| Model requests | 92 / **67** | 97 / **70** | 21 / 18 | 27 / 25 |
| Input tokens | 1,190,327 / **850,716** | 1,749,981 / **1,233,752** | 243,839 / 205,430 | 469,340 / 423,346 |
| Expansion reads | 11 / **0** | 11 / **0** | 1 / 0 | 2 / 0 |
| Observation-only rounds | 29 / 12 | 27 / 12 | 9 / 8 | 15 / 13 |
| Collapse markers returned | 98 / 0 | 128 / 0 | 36 / 0 | 50 / 0 |
| Result chars | 112,135 / 98,384 | 202,263 / 197,313 | 11,452 / 9,382 | 51,589 / 47,555 |

Per-pair input ratios B/A:

| Cell | r0–r3 |
| --- | --- |
| `ui-table` v0 crowded / isolated | 0.565, 0.668, 0.743, 0.515 / 0.721, 0.830, 0.863, 0.719 |
| `ui-table` v1 crowded / isolated | 0.868, 0.755, 0.669, 0.849 / 0.743, 0.526, 0.625, 0.593 |
| `ui-table` v2 crowded / isolated | 0.969, 0.649, 0.724, 0.670 / 0.743, 1.041, 1.029, 0.463 |
| `mm-grid` v0 crowded / isolated | 0.833, 0.824, 0.809, 1.186 / 0.831, 0.982, 0.781, 0.776 |

- B was lower in 29 of 32 pairs. The three higher pairs (`ui-table` v2 isolated r1–r2, `mm-grid` crowded r3) are
  within 4% of A, except `mm-grid` crowded r3 at 1.186.
- **The mechanism matches H18's.** Results are smaller in total although each listed page is longer, because the
  model no longer re-reads collapsed containers. Chained observation rounds on `ui-table` went 31 → 0.
- **Unlike H18's B, this change is a size rule, not a count rule.** H18 listed every run that hid at most five items.
  Here, the crowded `ui-table` and `mm-grid` pages also lost all their markers: none of their hidden stretches
  reached 600 characters.

## Guards

| Cell | Requests A / B | Input A / B | Ratio | Per-pair ratios r0–r3 | Markers per run, A and B |
| --- | ---: | ---: | ---: | --- | --- |
| `ui-infinite` v0 isolated | 20 / 22 | 202,666 / 225,628 | **1.113** | 1.218, 1.008, 1.225, 1.003 | A: 25, 65, 9 (twice each); B: 25, 65 (twice each) |
| `pb-longpage-01` v0 | 27 / 29 | 324,168 / 350,725 | **1.082** | 1.165, 1.215, 0.975, 0.998 | identical: 175 (twice) |

- **`ui-infinite`:**
  - Both arms' calls returned results of identical size up to `browser_find load_more` (185, 807 and 406 characters).
  - The only output the change alters is the final click's delta. B lists the 9 items after #71 that A hides
    behind a marker: 1,084 vs 365 characters. It is the last tool result before the answer.
  - In r0 and r2, B inserted a `browser_tabs action=list` (334 characters) between the snapshot and `load_more`.
    That is one extra request, chosen before any output differed. Those two pairs make the cell's ratio. In r1 and
    r3 the requests were equal and the ratios were 1.008 and 1.003.
- **`pb-longpage-01`:**
  - The markers were identical (175 hidden, twice per run), and every observation both arms shared had the same
    size (622, 1,751, 1,203, 598 characters).
  - In r0 and r1, B ran one more `browser_find` with a different query before opening the form tab. In r2 and r3 the
    ratios were 0.975 and 0.998.

This is an interpretation from the transcripts. As in H18, 4 guard pairs cannot separate a 5% threshold from path
variance. On `ui-infinite`, the change's only visible cost is about 720 characters in the final result.

## Interpretation and next step

- Two cohorts now show the same result.
  - On paginated tables and grids, collapsing a few short rows costs separate expansion rounds, and listing them
    removes the rounds and lowers input. Here that held in 29/32 pairs, with no success, safety or error cost.
  - Neither cohort could clear a 1.05 guard threshold. In both, the guards' divergence came before any output
    the change touched.
- The size rule has no visible downside on these guards. The predeclared rule still allows no adoption claim from
  this cohort.
- Deciding on kitsune PR #493 needs either an owner decision that weighs these transcripts, or a guard design that
  can resolve 5%. That would mean more repeats, or guard cells where the change alters an early observation,
  chosen before execution.

## Limits

- One model and harness; gallery variants 0–2 for `ui-table` but only v0 for `mm-grid` and the guards.
- `analyze-model-rounds.py` counts an expansion read only when a `browser_snapshot` targets a container that the
  latest result showed collapsed. Other recovery paths (`browser_find`) are not counted as expansions.

## Reproduction

```sh
git -C ../kitsune worktree add --detach ../worktrees/kitsune-485-A 85b50d2
git -C ../kitsune worktree add --detach ../worktrees/kitsune-485-B 357456e
uv run --locked python scripts/run-k485.py run \
  --baseline ../worktrees/kitsune-485-A --baseline-sha 85b50d2cdce53c3e7eefb02e4b3d4e2e95ecfee9 \
  --intervention ../worktrees/kitsune-485-B --intervention-sha 357456e366ab41b5b02da7639daa06ea5d8ebf7c
uv run --locked python scripts/run-k485.py analyze
```

Run log and analysis: `artifacts/k485/runs.jsonl`, `artifacts/k485/analysis.json` (not committed).
