# H18: list short similar-item runs in full — frozen protocol

[Results index](../results/README.md) · [Issue #4](https://github.com/junyeong-nero/kitsune-benchmark/issues/4) ·
[Draft hypothesis and the offline analysis](2026-10-25-issue-18-ui-table-rounds.md#draft-hypothesis-not-opened-as-an-issue)

This file freezes the cohort before any agent run. It was committed before the first execution, and it is not
edited after that. Results go in a separate report.

**H18:** On paginated tables, Kitsune's collapsed-list summaries in snapshots and action deltas cause separate
expansion/verification model rounds. Listing the collapsed items reduces model requests per successful run, and
lowers total input, because avoided prefix re-sends outweigh larger observations.

## Arms

| Arm | Kitsune checkout |
| --- | --- |
| A, baseline | `main` `dbc84f8` (v0.7.0 + 8), clean detached worktree |
| B, intervention | `exp/h18-list-short-runs` = `dbc84f8` + one commit: a similar-item run that would hide **at most five items** (`LISTED_REMAINDER_LIMIT = 5`, so runs of up to ten) is listed in full, in snapshots and action deltas. Runs that would hide more still show five items and the marker. Scoped snapshots are unchanged (up to 100 items) |

Tool names, descriptions, schemas, ref semantics and the prompt are identical: the commit changes only
`extension/content/content.js`, extension tests and the API reference. No instruction to batch calls. Playwright
is not run; it is not an arm. Including row cell values in page-turn deltas is a separate factor, not tested here.

No-model arm check (`scripts/probe-h18-collapse.py`, first `browser_snapshot` of variant 0): isolated `ui-table`
baseline has one marker hiding 3 rows and lists 5 checkbox rows; the intervention has no marker and lists all 8.
`mm-grid` isolated: baseline one marker hiding 4; intervention none. The crowded `ui-table` and `ui-infinite` first
snapshots contain no table or list rows on either arm (the crowded table is past the first snapshot's limit; the
infinite list loads after scrolling).

## Cells and order

- **Table cells:** `ui-table` variants 0–2 × crowded/isolated, 4 repeats per arm: 48 runs.
- **Guard cells,** 3 repeats per arm: `ui-infinite` v0 isolated (runs of 2–65 hidden in the v0.7.0 cohort, partly
  affected), `mm-grid` v0 isolated (runs hiding 3–4, fully affected) and personal `pb-longpage-01` v0 (runs hiding
  175, unaffected; a personal-track control): 18 runs.
- **66 agent runs**, one harness invocation each, Kitsune target only. `mm-grid` is added to the draft's two guards
  because it is the most collapse-heavy non-table gallery task the change affects.
- Order within a cell: ABBA / BAAB for 4 repeats, ABA / BAB for 3, alternating between cells (A = baseline).
  Repeat-major across cells, so drift over the session spreads over every cell. `scripts/run-h18.py plan` prints
  the order.

## Fixed conditions

Benchmark `taskset-v3` (`component-gallery-v2` and `personal-browsing-local-v3`), primary contract
`v2_agent_tab_cleanup`, strict `v1_strict_close` beside it. Default subscription harness: Claude Code 2.1.303,
`claude-opus-5-5`, effort medium, claude.ai login, no API key. Gallery timeout 240 s and personal timeout as in the
configs. Sequential runs; no automatic retries; unscorable runs are reported, not replaced.

## Counted per run

Model requests, input split into cache read / cache write / uncached and prefix × requests vs non-prefix/history,
output, MCP calls, observation-only / follow-up / chained rounds and expansion reads
(`scripts/analyze-model-rounds.py`), result chars, collapse markers returned, tool errors and those recovered
within a successful run, failures and unscorable runs.

## Estimands

A *pair* is the baseline and intervention run of one cell and repeat. It is *jointly successful* when both runs are
scorable and pass the primary (v2) `task_success`.

- **Request ratio:** the median, over all jointly successful isolated table pairs pooled across variants (up to 12),
  of intervention requests / baseline requests. Not a median of per-cell medians.
- **Table input ratio:** Σ intervention input / Σ baseline input over all jointly successful table pairs, both
  layouts (up to 24). **Guard input ratio:** the same per guard cell.
- Failed or unscorable runs drop their pair from every ratio and are listed. With fewer than 10 of 12 isolated or
  20 of 24 table pairs jointly successful, the verdict is inconclusive regardless of the ratios.
- **Gates,** separate from the ratios: over all attempts per cell and arm, successes (an unscorable run counts as
  no success), v1/v2 safety failures, and failed MCP calls within successful runs (recovered errors).

## Decision

- **Support** requires all of: in every cell, intervention successes ≥ baseline and safety failures ≤ baseline;
  request ratio ≤ 0.85; table input ratio ≤ 0.95; every guard input ratio ≤ 1.05; recovered errors not higher in
  total.
- **Reject** if the request ratio is > 0.95 or the table input ratio is > 1.00.
- Anything else is **inconclusive**, with no adoption claim.

`scripts/run-h18.py analyze` computes these from the log.

## Stops

The driver stops on a harness error without a parseable summary (retried on resume), two unscorable runs in a row,
a Kitsune revision change or dirty checkout, tool surfaces that differ between the arms, a collapse marker hiding at
most five items in an intervention run, or navigation outside the fixture.

## Changes from the draft

- Baseline is the current Kitsune `main` (`dbc84f8`), not v0.4.1 `83acfe9`: an adoption decision is about the
  current code, and v0.7.0 still collapses the `ui-table` pages (3 hidden rows per page).
- `taskset-v3` replaces `taskset-v2` (the current taskset; same primary contract). The gallery timeout is the
  config's 240 s, not 180 s.
- The threshold is fixed at five hidden items.
- A third guard, `mm-grid` v0 isolated; the personal guard is `pb-longpage-01` v0.

## Out of scope

Parallelizing state-dependent clicks or writes, prompt or description changes that steer batching, and further
snapshot truncation.
