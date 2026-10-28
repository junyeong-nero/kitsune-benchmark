# H310: budget-truncated snapshots fill `main` first and leave link URLs out — frozen protocol

[Results index](../results/README.md) · [kitsune#310](https://github.com/junyeong-nero/kitsune/issues/310) ·
[No-model measurement](https://github.com/junyeong-nero/kitsune/issues/310#issuecomment-6467413596)

This file freezes the cohort before any agent run. It was committed before the first execution and is not edited
after that. Results go in a separate report.

**H310:** When a page is larger than the 12,000-character snapshot budget, Kitsune fills the budget in document order
and gives a `/url` line to every link. On pages with a large banner or navigation, that pushes the task's own content
out of the first snapshot, and the agent pays for extra `browser_find` / scoped-snapshot rounds. Two changes should
lower total input on those pages: drop `/url` lines from a snapshot that is truncated for budget, and fill `main`
(with its ancestors) before the rest. Pages that fit the budget must be unaffected.

## Arms

| Arm | Kitsune checkout |
| --- | --- |
| A, baseline | `main` `f0ca705` (v0.7.0 + 12), clean detached worktree |
| B, intervention | `exp/h310-snapshot-budget` = `f0ca705` + one commit `d571963`. The change applies only when a snapshot without a target is truncated for its budget: link `/url` lines are dropped, `main` with its ancestors is filled first, then the rest in document order. Each part ends between small blocks (unchanged `cuts`). The result carries `urls_omitted: true`, and the core hint adds one sentence saying so. Whole, scoped (`target`), `filename` and action-delta snapshots are unchanged |

Tool names, descriptions and schemas are identical. The commit changes `extension/content/content.js`, one hint
string in `src/kitsune/playwright_tools.py`, and two extension tests. Kitsune's own suites pass on B: 861 Python
tests and every `tests/*.cjs`. Playwright is not run; it is not an arm. The benchmark checkout is `main` after
kitsune-benchmark#35, which lets setup run against Kitsune main's `no_current_tab` refusal (kitsune#303).

**No-model arm check** (`scripts/probe-snapshot-budget.py`, real Firefox, first core `browser_snapshot`):

- Crowded gallery, task section refs fully present in the first snapshot: A 1/21 tasks, B 20/21. B's truncated
  snapshots contain 0 `/url` lines.
- `main` refs on five public pages (A → B): Wikipedia 61 → 139, MDN 49 → 84 (all), Steam 74 → 116, GitHub 73 → 117,
  BBC News 58 → 88.

## Cells and order

| Kind | Cells (gallery task, variant 0) | Repeats per arm |
| --- | --- | --- |
| Primary | crowded `ui-sortable`, `ui-shadow`, `ui-slider`, `ui-rowmenu`, `ui-table`, `mm-label` | 4 |
| Guard | isolated `ui-sortable`, isolated `ui-shadow`, personal `pb-longpage-01` | 3 |

How the cells were chosen:

- **Primary cells:** the crowded tasks whose section v0.7.0's first snapshot loses, and whose Kitsune/Playwright input
  ratio was high on 2026-10-26.
- **Guard cells:** not truncated in any 2026-10-26 run, so B should leave them alone.

The run count is 66: 48 primary, 18 guard. Runs are executed repeat-major, so drift over the session spreads over
every cell. Arms alternate ABBA/BAAB with four repeats and ABA/BAB with three, and the pattern alternates between
cells (`scripts/run-h310.py plan`).

The harness is Claude Code `2.1.303` on the subscription, with the config model (`claude-opus-5-5`) and effort
(medium). It runs the Kitsune target only, with fresh profiles per run. Unscorable runs are logged and never
replaced.

## Stops

The driver exits and does not continue on any of these:

- a harness error without a summary;
- two unscorable runs in a row;
- a Kitsune revision change or dirty checkout;
- tool surfaces that differ between the arms;
- a truncated intervention snapshot that still lists `/url` lines (the change is not in effect);
- navigation outside the fixture.

## Estimands and decision (predeclared)

A pair is a cell repeat in which both arms are scorable and successful.

- **Primary estimand:** the primary input ratio, Σ input tokens(B) / Σ input tokens(A) over joint-success primary
  pairs.
- **Secondary estimands** (reported, not decisive):
  - the median per-pair request ratio;
  - `browser_find` calls;
  - truncated snapshots;
  - per-cell ratios;
  - cache-read/write and output tokens.
- **Guard estimand:** the pooled guard input ratio.
- **Gates**, per cell:
  - B's successes ≥ A's;
  - B's v1/v2 safety failures ≤ A's.

| Verdict | Condition |
| --- | --- |
| **support** | ≥ 18 joint primary pairs, primary input ratio ≤ 0.90, pooled guard input ratio ≤ 1.05, every gate holds |
| **reject** | ≥ 18 joint primary pairs and primary input ratio ≥ 1.00 |
| **inconclusive** | anything else |

The H18 cohort showed per-pair ratios from 0.94 to 1.50 on one guard cell. A pooled guard ratio is therefore used
instead of per-cell guard thresholds; per-cell ratios are still reported.

## Reproduce

```sh
uv run --locked python scripts/run-h310.py plan
uv run --locked python scripts/run-h310.py run --baseline ../worktrees/kitsune-h310-base \
  --baseline-sha f0ca7056d77f819b58bde4378131ce79f9df23ba --intervention ../worktrees/kitsune-h310 \
  --intervention-sha d57196342a588aed1873386959ef014bf1f7e9a4
uv run --locked python scripts/run-h310.py analyze
```
