# kitsune#485: collapse a similar-item run by size, not count — frozen protocol

[Results index](../results/README.md) · Upstream: kitsune#485, kitsune PR #493 ·
[H18, the earlier collapse A/B](2026-10-28-h18-collapse-ab.md)

This file freezes the cohort before any agent run. It is committed before the first execution and not edited
after that. Results go in a separate report.

**Hypothesis (kitsune#485):** a marker that hides 3 short table rows makes the agent spend a request to expand
them. Listing a hidden stretch whose lines total at most 600 characters removes those expansions on `ui-table` and
`mm-grid`, without raising input on guard units where the collapse markers hide long runs.

## Arms

| Arm | Kitsune checkout |
| --- | --- |
| A, baseline | `main` `85b50d2` (v0.7.3 + 14), clean detached worktree |
| B, intervention | `357456e` = `85b50d2` + one commit (kitsune PR #493). A hidden stretch that the count rule (#458, at least 3 items) would collapse is listed when its lines, as the agent reads them, total at most `COLLAPSE_MAX_LISTED_CHARS = 600`. Everything else, including the delta removal fold (#471), is unchanged |

The commit changes `extension/content/content.js`, tests and docs only. Tool names, descriptions, schemas and the
prompt are identical. Playwright is not run.

## Cells and order

- **Target cells,** 4 repeats per arm: `ui-table` variants 0–2 × crowded/isolated, and `mm-grid` v0 ×
  crowded/isolated: 64 runs.
- **Guard cells,** 4 repeats per arm (H18 had 3 and found them too few): `ui-infinite` v0 isolated and personal
  `pb-longpage-01` v0, the guards kitsune#485 names: 16 runs.
- **80 agent runs,** one harness invocation each, Kitsune target only. Order within a cell ABBA / BAAB,
  alternating between cells; repeat-major across cells. `scripts/run-k485.py plan` prints it.

## Fixed conditions

Benchmark `taskset-v3.5-10-g3ba6f61` plus this protocol and its runner. Primary contract `v2_agent_tab_cleanup`,
strict `v1_strict_close` beside it. Default subscription harness: Claude Code 2.1.303, `claude-opus-5-5`, effort
medium, claude.ai login, no API key. Sequential runs, no automatic retries; unscorable runs are reported, not
replaced.

## Counted per run

As in H18: model requests, input, output, prefix × requests and history, MCP calls, observation-only, follow-up and
chained rounds, **expansion reads** (`scripts/analyze-model-rounds.py`: a `browser_snapshot` of a container whose
latest state was collapsed), result chars, collapse markers returned and those hiding 3–5 items, tool errors and
those recovered within a successful run.

## Estimands

A pair is the A and B run of one cell and repeat; jointly successful when both are scorable and pass primary
`task_success`.

- **Expansion reads,** per arm, summed over every scorable target run (the issue's acceptance measure).
- **Target input ratio:** Σ B input / Σ A input over jointly successful target pairs (up to 32).
- **Guard input ratio:** the same per guard cell (up to 4 pairs each).
- **Descriptive:** the median per-pair request ratio over target pairs; totals per task and layout.
- **Gates,** over all attempts per cell and arm: successes, v1/v2 safety failures, recovered errors.

## Decision

- With fewer than 26 of 32 target pairs jointly successful: **inconclusive**.
- **Reject** if B's expansion reads are not lower than A's, or the target input ratio is > 1.00.
- **Support** requires all of: B has 0 expansion reads on target runs; in every cell, B's successes ≥ A's and its
  safety failures ≤ A's; every guard input ratio ≤ 1.05.
- Anything else is **inconclusive**. Recovered errors are reported, not gated.

`scripts/run-k485.py analyze` computes these from the log. As H18 showed, 4 guard pairs may not separate a 5%
threshold from path variance; the report will say whether a guard run got a marker the arms list differently.

## Stops

The runner stops (exit 2) on a harness error without a parseable summary, two unscorable runs in a row, a Kitsune
revision change or dirty checkout, tool surfaces that differ between the arms, a marker hiding at most 5 items in a
B run of isolated `ui-table` (the change is not in effect), or navigation outside the fixture.
