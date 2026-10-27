# H18: list short similar-item runs in full — Kitsune A/B

[Results index](README.md) · [Issue #4](https://github.com/junyeong-nero/kitsune-benchmark/issues/4) ·
[Frozen protocol](../experiments/2026-10-28-h18-collapse-ab.md) ·
[Offline analysis that proposed H18](../experiments/2026-10-25-issue-18-ui-table-rounds.md)

**Verdict: `inconclusive` under the predeclared rule.** On `ui-table` the change met both support thresholds by a
wide margin. Isolated request ratio **0.578** (threshold ≤ 0.85), table input ratio **0.679** (≤ 0.95), and
24/24 table pairs had fewer requests and less input with the intervention. Two predeclared conditions failed:
guard input ratios on `ui-infinite` (**1.171**) and `pb-longpage-01` (**1.071**) exceed 1.05, and the intervention
had **4** recovered tool errors against 0. The change had no visible effect in those two guard cells (see
[guards](#guards)), so their differences look like path variance, but the rule allows no adoption claim from this
cohort.

## Setup

- 2026-10-28 08:00–08:40 KST (pairs `20261027T230012Z-b03c7b0f12` … `20261027T234006Z-5f0c694537`), 66 agent
  runs, **all scorable**, no retries, no stop. Driver wall time 40.6 min.
- Arms, Kitsune target only: **A** baseline `dbc84f8` (main, v0.7.0 + 8); **B** intervention `53cceea` =
  `dbc84f8` + one commit (kitsune `exp/h18-list-short-runs`). B lists a similar-item run in full when it would hide
  at most five items. Both checkouts clean on every run; one identical tool surface across all 66 runs.
- Benchmark `aad4a67` (protocol commit, before the first run), `taskset-v3`, primary contract
  `v2_agent_tab_cleanup`. Claude Code 2.1.303 on the claude.ai subscription, `claude-opus-5-5`, effort medium.
  Client list-price estimate $8.82 (not a charge on the subscription).
- Cells: `ui-table` v0–2 × crowded/isolated, 4 repeats per arm (ABBA/BAAB); guards `ui-infinite` v0 isolated,
  `mm-grid` v0 isolated, personal `pb-longpage-01` v0, 3 repeats per arm (ABA/BAB). Order counts: 17 AB / 16 BA
  per arm.
- The arm check held: **0** collapse markers in 24 intervention `ui-table` runs and 3 `mm-grid` runs; baseline
  `ui-table` runs returned 350 markers.

## Decision criteria

| Criterion | Threshold | Measured | Result |
| --- | --- | --- | --- |
| Jointly successful pairs | ≥ 10/12 isolated, ≥ 20/24 table | 12/12, 24/24 (33/33 overall) | met |
| Successes, every cell | intervention ≥ baseline | 33/33 vs 33/33, equal in every cell | met |
| Safety failures (v1 and v2), every cell | intervention ≤ baseline | 0 vs 0 | met |
| Request ratio (median, isolated table pairs) | ≤ 0.85 support; > 0.95 reject | **0.578** | support side |
| Table input ratio (Σ, all table pairs) | ≤ 0.95 support; > 1.00 reject | **0.679** | support side |
| Guard input ratio, every guard cell | ≤ 1.05 | `ui-infinite` **1.171**, `mm-grid` 0.837, `pb-longpage-01` **1.071** | **not met** |
| Recovered errors, total | intervention ≤ baseline | **4** vs 0 | **not met** |

No reject condition holds, and not every support condition does, so the verdict is inconclusive. Strict v1 success
was also 33/33 vs 33/33.

## Table cells

Totals over the jointly successful pairs. Input includes cache read and cache write.

| | Isolated A | Isolated B | Crowded A | Crowded B |
| --- | ---: | ---: | ---: | ---: |
| Pairs | 12 | 12 | 12 | 12 |
| Model requests | 113 | **66** (−41.6%) | 118 | **93** (−21.2%) |
| Input tokens | 1,470,043 | **816,706** (−44.4%) | 2,152,417 | **1,644,640** (−23.6%) |
| Input per request | 13,009 | 12,374 | 18,241 | 17,684 |
| Prefix × requests | 1,060,971 | 619,683 (−441,288) | 1,107,837 | 873,159 (−234,678) |
| Non-prefix/history | 409,072 | 197,023 (−212,049) | 1,044,580 | 771,481 (−273,099) |
| Output tokens | 12,005 | 9,580 | 14,144 | 12,204 |
| MCP calls | 158 | 129 | 185 | 159 |
| Observation-only rounds | 56 | **13** | 61 | **36** |
| … follow-up after an action | 23 | 1 | 13 | 0 |
| … chained after an observation | 21 | 0 | 36 | 24 |
| Expansion reads | 22 | **0** | 25 | **0** |
| Collapse markers returned | 176 | 0 | 174 | 0 |
| Result chars | 107,138 | 89,066 | 232,717 | 220,175 |
| Failed MCP calls (recovered) | 0 | 0 | 0 | **2** (1 run) |
| Agent elapsed (s) | 333.2 | 215.7 | 368.5 | 321.4 |

Per pair, B/A:

| Cell | Request ratios r0–r3 | Input ratios r0–r3 |
| --- | --- | --- |
| v0 crowded | 0.889, 0.900, 0.800, 0.889 | 0.891, 0.907, 0.763, 0.877 |
| v0 isolated | 0.625, 0.750, 0.750, 0.625 | 0.594, 0.705, 0.785, 0.590 |
| v1 crowded | 0.727, 0.700, 0.636, 0.800 | 0.689, 0.663, 0.592, 0.774 |
| v1 isolated | 0.667, 0.545, 0.556, 0.500 | 0.684, 0.526, 0.500, 0.465 |
| v2 crowded | 0.700, 0.700, 0.889, 0.889 | 0.649, 0.655, 0.885, 0.914 |
| v2 isolated | 0.600, 0.500, 0.500, 0.500 | 0.547, 0.470, 0.471, 0.471 |

Isolated request ratios range 0.50–0.75 and crowded 0.64–0.90 (median 0.80); input ratios 0.47–0.79 and
0.59–0.91. The mechanism the offline analysis proposed shows up directly. Expansion reads go from 47 to 0, and
follow-up observation rounds from 36 to 1. Results are smaller in total although each listed page is longer, because
the model no longer re-reads collapsed containers. Input per request barely changes (−4.9% isolated, −3.1%
crowded). So the input saving comes mainly from fewer requests: prefix re-sends −675,966 tokens and history
−485,148 over the 24 table pairs.

The 2 errors: one crowded v0 intervention run (r1) clicked four refs in one request. Two of them were stale
(`stale_ref`, element removed) after a re-render, so the model took a new snapshot and finished the task correctly.
The baseline had no stale-ref error. One run is too few to tell whether full listing invites more batched clicks.

## Guards

| Cell | Requests A / B | Input A / B | Ratio | Markers per run, A and B |
| --- | ---: | ---: | ---: | --- |
| `ui-infinite` v0 isolated | 41 / 39 | 552,631 / 647,345 | **1.171** (r0–r2: 0.942, 1.500, 1.100) | identical: hiding 9, 25, 65 |
| `mm-grid` v0 isolated | 18 / 15 | 211,688 / 177,141 | 0.837 (0.840, 0.832, 0.839) | A 8 (hiding 3–4); B 0 |
| `pb-longpage-01` v0 | 20 / 21 | 237,735 / 254,558 | **1.071** (1.016, 1.196, 1.020) | identical: hiding 175 |

- **`mm-grid`,** the guard the change affects, improved: one request fewer per run and −16% input in every
  repeat.
- **`ui-infinite` and `pb-longpage-01`:** every baseline run returned only markers hiding more than five items (9–65 and
  175). So no observation had a run that the intervention lists differently, and both arms got the same markers. The
  first snapshots match (24 and 382 chars). The differences come from the model's paths. `ui-infinite` r1 (B) made 15
  requests with two `browser_wait_for` timeouts, the 2 recovered errors counted against B; its pair ratio 1.500 drives
  the cell. `pb-longpage-01` r1 (A) merged two rounds into one (6 vs 7 requests). This is an interpretation from the
  transcripts. The predeclared rule does not exempt unaffected guards, and the verdict stands.

## Interpretation and next step

- On paginated tables the evidence supports the mechanism: collapsing 8-row pages causes separate expansion and
  verification rounds. Listing them removes those rounds and lowers total input despite longer observations. This
  holds across 3 variants × 2 layouts, 24/24 pairs, with no success or safety cost.
- The cohort does not support an adoption claim. The guard criterion failed in two cells that the change did not
  visibly touch, and the errors were not lower. Three repeats per guard cell are too few to separate a 5% guard
  threshold from run-to-run variance (`ui-infinite` pair ratios 0.94–1.50).
- A confirmatory cohort would need more guard repeats, or guards selected where the change has an effect, decided
  before execution. It should also track stale-ref errors after batched clicks. Kitsune
  `exp/h18-list-short-runs` stays an experiment branch until then.

## Limits

- One model, effort and harness (Claude Code subscription); batching behaviour may differ elsewhere. 4 repeats per
  table cell and 3 per guard cell.
- The threshold (five hidden items) was fixed before the run. Other thresholds were not tested.
- Observational labels (follow-up, expansion) come from `scripts/analyze-model-rounds.py`; they are structural, not
  the model's stated reasons. The guard interpretation and the error descriptions come from reading the private
  transcripts.

## Reproduce

```sh
uv run --locked python scripts/probe-h18-collapse.py BASELINE_DIR INTERVENTION_DIR   # no model
uv run --locked python scripts/run-h18.py plan                                       # no model
uv run --locked python scripts/run-h18.py run --baseline BASELINE_DIR --baseline-sha dbc84f8f8dd163f70d387c55c5e2963396c9f535 \
  --intervention INTERVENTION_DIR --intervention-sha 53cceea59f6e7e8f732366dacd70a7772a79ba19   # 66 agent runs
uv run --locked python scripts/run-h18.py analyze                                    # no model
```

Private artifacts: `artifacts/h18/runs.jsonl` and `analysis.json`.
