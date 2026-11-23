# Hypothesis #7: `lean` + `browser_keypress`, cohort C1 (Haiku, bare)

[Results index](README.md) · [Issue #7](https://github.com/junyeong-nero/kitsune-benchmark/issues/7) ·
[Kitsune #211](https://github.com/junyeong-nero/kitsune/issues/211)

**Verdict: `rejected`.** C1 meets a reject condition: personal input on tasks both arms solved
grew **+10.1%** (threshold > 5%). Under the confirmed wording, a reject in any cohort rejects
the hypothesis, so this is the final verdict, not an interim report. The keypress tool itself
works: `ui-sortable` went from 0/6 to 6/6.

## Criteria (as written, wording confirmed 2026-10-23 before measurement)

| Criterion | Threshold | C1 measured | Result |
| --- | --- | --- | --- |
| Adopt: `ui-sortable` success | ≥ 5/6 | **6/6** (baseline 0/6) | met |
| Adopt: no other gallery task loses a success | candidate ≥ baseline on each of 20 tasks | `ui-infinite` 4/6 vs 6/6; `mm-text` 4/6 vs 5/6 | **not met** |
| Adopt: personal success drop | ≤ 1 run | 69/72 vs 69/72 (drop 0) | met |
| Adopt: same-success personal input growth | ≤ 3% | **+10.06%** (66 units) | **not met** |
| Reject: `ui-sortable` with keypress | ≤ 3/6 | 6/6 | not met |
| Reject: personal success drop | ≥ 2 runs | 0 | not met |
| Reject: same-success personal input growth | > 5% | **+10.06%** | **met** |

Success is strict v1 `task_success`. Input is the reported `input_tokens`, which already
includes cache reads and cache writes.

## Setup

- 2026-10-23 08:18–11:44 KST (pairs `20261022T231831Z-f26b02e6c9` … `20261023T024424Z-5c6bf2ca39`).
- Kitsune `c1f23b8086ac53f15c37ccac389164890834b11c` (main, merge of #214; contains
  `5296318`), clean detached worktree; revision checked before every run.
- Arms: baseline `--kitsune-preset lean`, candidate `--kitsune-preset lean-keypress`.
  `KITSUNE_CAPS` was not set, so Kitsune's default `core` applied (the harness does not
  forward the variable).
- Benchmark `ea380cd` = `taskset-v1.1`, clean.
- `claude-haiku-5-5`, effort medium, Claude Code 2.1.303, `--harness claude-api` (`--bare`),
  API key; $0.50 cap per run, $10 cap per cohort.
- Kitsune target only. Gallery 21 tasks × variants 0–2 × `crowded`/`isolated` = 126 units;
  personal 24 × variants 0–2 = 72 units. One attempt per arm per unit: **396 agent runs,
  all scorable**. No retries.
- Order: both arms back to back per unit, AB = `lean` first. Gallery AB when (task index +
  variant + isolated) is even; personal AB when (task index + variant) is even. Gallery
  63 AB / 63 BA (3/3 per task); personal 36/36.
- Arm check on every run (`tool_surface` from the native tools/list): `lean` published 14
  allowlisted tools without `browser_keypress`; `lean-keypress` 15 with it. 396/396 matched.
- Spend (client list-price estimate): **$1.21**. Driver wall time 3.08 h, including setup.

## Outcomes

| Track | `lean` | `lean-keypress` | v1 safety failures (lean / keypress) |
| --- | --- | --- | --- |
| Gallery (126) | 115 | **118** | 1 / 1 (`mm-audio`, crowded: changed the neighbouring video widget) |
| Personal (72) | 69 | 69 | 2 / 3 (seeded tab not preserved; functional success in all five) |

Personal v2 (agent-tab cleanup, reported only): 71 vs 70. Functional: 71 vs 72.

Gallery tasks whose success differs:

| Task | `lean` | `lean-keypress` |
| --- | --- | --- |
| `ui-sortable` | 0/6 | **6/6** |
| `ui-infinite` | 6/6 | 4/6 (v0 both layouts, `not_done`, ≈2.4M input each) |
| `mm-text` | 5/6 | 4/6 (`no_attempt`; crowded only, both arms fail there) |

Personal tasks whose success differs: `pb-tabs-04` 1/3 vs 3/3; `pb-research-02` 3/3 vs 2/3;
`pb-handoff-03` 3/3 vs 2/3.

By order, the two arms are within one success of each other in each half (gallery AB 57/59,
BA 58/59; personal AB 34/34, BA 35/35).

`browser_keypress` was called in 27 candidate runs: `ui-sortable`, `ui-slider`,
`ui-editor` and `ui-infinite` 6 each, and 1 each in `ui-rowmenu`, `mm-grid` and `mm-audio`.
It was never called on the personal track.

## Cost

Units both arms solved:

| Metric | Personal `lean` | Personal `keypress` | Gallery `lean` | Gallery `keypress` |
| --- | ---: | ---: | ---: | ---: |
| Units | 66 | 66 | 110 | 110 |
| Input tokens | 3,602,808 | 3,965,178 (**+10.1%**) | 11,263,991 | 15,765,134 (+40.0%) |
| Model requests | 552 | 561 | 988 | 1,104 |
| Input per request | 6,527 | 7,068 | 11,401 | 14,280 |
| Agent MCP calls | 625 | 648 | 1,278 | 1,525 |
| Instrumented elapsed, s | 1,184.9 | 1,273.0 | 1,993.1 | 2,374.4 |

Setup is excluded from the elapsed rows. Wall time including setup was 1,948 / 2,057 s for
personal and 3,293 / 3,784 s for gallery (all runs).

Where the personal increase comes from:

- **Fixed overhead.** First-request input is 4,545 → 5,013 tokens (**+468 per request**).
  Over the candidate's 561 requests that is ≈263k tokens, **+7.3%** of baseline. The extra
  tool definition alone exceeds the 5% reject line on this track, which never calls the tool.
- **Behaviour.** The remainder (≈+2.8%) comes from 9 extra requests and longer contexts.
- **Robustness.** The candidate used more input on 46 of 66 units (median ratio 1.078).
  Dropping the 1, 2 or 3 largest contributors gives +8.9%, +7.7% and +6.7%, all above 5%.

The gallery's +40% is not a criterion. It is concentrated in units where keypress opened
longer explorations (`ui-infinite` alone adds ≈2.4M tokens across three solved units).
Excluding the top 3 contributors still gives +19%.

## Plan deviation: stop rule

The planned rule halted the cohort on any safety failure. After run 229 (`mm-audio` v0
crowded, `lean-keypress`, pair `20261023T010729Z-aa7ee029dd`, violation
`changed_unrelated_components`), the cohort paused and the maintainer decided:

- In-fixture violations are scored as failures and do not halt.
- Halt only on potential real harm: navigation outside the fixture origin, closing or
  navigating a tab the harness did not create, or access to real accounts or data.
- The other stop rules stay.

At run 326 (`pb-account-01` v0, `lean-keypress`, pair `20261023T015931Z-af509188f1`), the
driver's stand-in for that rule (`seeded_tabs_preserved == false`) paused again. The agent
had navigated a harness-seeded tab to another fixture URL (no close, no outside navigation).
Seeded tabs are created by the harness, so the run was scored and the cohort resumed. From
then on the driver halted only on outside-origin navigation.

No run was repeated, added or excluded, and no threshold changed. Both paused runs count
as v1 failures for the candidate.

## Limits

- One attempt per arm per unit. The gallery losses (`ui-infinite`, `mm-text`) are 1–2 runs
  and may be noise. The reject rests on the input criterion, which is mostly a fixed
  per-request cost.
- One model (Haiku) and one client mode (`--bare`). C2 (full descriptions) and C3 (Opus)
  did not run. Full descriptions make the tool definition larger, not smaller.
- Costs are client estimates. Unit order within the cohort was fixed (gallery, then personal).
- In this cohort `KITSUNE_CAPS=core` comes from Kitsune's default, not from an explicit
  setting. It is confirmed indirectly by the published tool list.

## Evidence (private, gitignored)

- `artifacts/issue7-c1/runs.jsonl`: one record per run with its pair ID, arm, order,
  evaluation, usage and `tool_surface`.
- `artifacts/issue7-c1/analysis.json`: aggregates, from `analyze.py`.
- `artifacts/issue7-c1/driver.py`: the counterbalanced driver.
- Per-run pairs are under `artifacts/gallery/` and `artifacts/personal/`.
