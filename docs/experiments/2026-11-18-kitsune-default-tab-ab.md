# Kitsune A/B: a script's `tab` defaults to the viewed tab

Second follow-up to the [five-surface comparison](2026-11-17-five-surface.md), after the
[persistent-variables A/B](2026-11-18-kitsune-repl-state-ab.md) was not supported.

## Why

Before any MCP selection, `browser_run_python`'s `tab` was `None`. Codex therefore opened
almost every Kitsune run with `browser_tabs list` → `browser_tabs select` → `browser_run_python`.
That pattern occurred 67 times across the five-surface and repl-ab cohorts, plus `tab_id`/`index`
mix-ups on `select`. Aside's `page` is bound from the start.

## Treatment

| Arm | Kitsune | Change |
| --- | --- | --- |
| base | `14d9ceb` (main) | `tab` is `None` until `browser_tabs new/select` |
| tab | `8d86930` (`feat/python-default-tab`) | without a selection, `tab` is the one tab the user views (None with several windows); the description says scripts need no `browser_tabs` list/select |

The write policy is unchanged: a viewed tab that is the user's stays read-only for writes.
The host reads `/api/tabs` once per call when nothing is selected. MCP selection is not
changed. The matrix is the same as the repl A/B: Codex `gpt-6.1-sol` and Opus, × 23
conditions × 2 arms = 92 attempts, A/B order alternating, agent-owned personal tabs.

## Result (`artifacts/tabs-ab-v1`): supported for Codex, neutral for Opus

All 92 attempts were scorable. Success: Codex base 22/23 (`ui-toast` again), tab 23/23;
Opus 23/23 both.

| Model | personal | isolated | crowded | all: median / geomean input | time (geomean) | calls | `browser_tabs` calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex | 1.00 | 0.87 | 0.82 | **0.86 / 0.90** | 0.95 | 173 → 130 | 52 → **0** |
| Opus | 1.03 | 1.01 | 0.96 | 1.01 / 0.90 | 0.85 | 107 → 86 | 4 → 0 |

Input ratios are tab/base on paired conditions. Codex input was lower in 16 of 23 pairs
(6/6 crowded), and every Codex tab run started with `browser_run_python`, against 1 of 23 in
base. Opus rarely called `browser_tabs` before, so its median is unchanged. Its geomean and
time gains come from a few crowded pairs and are single-repeat variance until repeated.

Decision: the Codex effect meets the ≤ 0.90 rule, has a clear mechanism (the removed
list/select round trips) and costs no success. Recommended for a Kitsune PR, with a
second repeat if a release claim depends on the size.
