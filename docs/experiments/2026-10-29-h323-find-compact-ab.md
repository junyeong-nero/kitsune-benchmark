# H323: compact `browser_find` results — frozen protocol

[Results index](../results/README.md) · [kitsune#323](https://github.com/junyeong-nero/kitsune/issues/323) ·
[H321 report (why find)](../results/2026-10-28-h321-live-urls-stopped.md)

This file freezes the cohort before any agent run. It was committed before the first execution and is not edited
after that. Results go in a separate report.

**H323:** On live sites, agents work through `browser_find`, which produced 83% of tool-result characters in nine live
runs. Each result repeats the matched line, duplicates overlapping context, matches and shows `/url` lines, and has no
size bound. Compact results should lower total input on find-heavy tasks without lowering completion, answers or
graded success.

## Arms

| Arm | Kitsune checkout |
| --- | --- |
| A, baseline | `main` `5dbcaff`, clean detached worktree |
| B, intervention | `exp/find-compact` `2459e95` = `5dbcaff` + two commits, changing only core `browser_find`'s inline result |

What B changes:

- **Blocks:** one block per `path`, holding the union of the ±2-line windows, in document order. A gap is shown as
  `  …`, and matched lines are prefixed `> `. There is no separate `match` field.
- **URLs:** `/url` lines are searched only for URL-like queries (starting with `/`, `http` or `www.`). They are shown
  only as the URL of a matched link.
- **Size bound:** the result is cut line by line at 8,000 characters and then reports `truncated`, `shown` and a
  hint.
- **Unchanged:** `count` (all matches) and `filename` (every match, unchanged format).

Tool names, descriptions and schemas are identical: the schema is Playwright MCP's mirrored text. On B, Kitsune's
suites pass: 892 Python tests, every `tests/*.cjs`, and the real-browser find, snapshot and observation suites. The
full real-browser suite fails only tests that also fail on A; one `wait_for` test failed once and passed on two
reruns.

Known behavior difference: a non-matched link in a find window no longer shows its URL. In A, a Steam run navigated
by a URL read from such a window; in B the agent has to click the link or snapshot its container.

**No-model arm check** (real Firefox, the queries agents used on 2026-10-28, result characters A → B):

| Page and query | A | B |
| --- | ---: | ---: |
| Wikipedia regex `/Initial release\|First release\|Release/` | 36,555 | 8,046 (cut) |
| Wikipedia regex `/2002\|Initial\|Developer/` | 18,743 | 8,029 (cut) |
| Wikipedia text `Release` | 231,915 | 7,850 (cut) |
| Steam Awards text `Winner` | 12,878 | 4,831 |
| MDN text `Firefox` | 1,714 | 1,213 |
| Steam app regex `/Review Type\|Playtime\|Negative/i` | 434 | 368 |

All three cut Wikipedia results still contain the answer, "November 9, 2004".

## Cells and order

| Kind | Cells | Repeats per arm |
| --- | --- | --- |
| Primary | live `live-steam-goty-2025-negative-100h`, `live-wikipedia-firefox-release`, `live-mdn-array-at-firefox`; personal `pb-longpage-01` v0 (graded) | 4 |
| Guard | gallery isolated `ui-shadow` v0, isolated `ui-select` v0 | 3 |

- **Run count:** 44 (32 primary, 12 guard).
- **Order:** repeat-major, with ABBA/BAAB or ABA/BAB alternating between cells (`scripts/run-h323.py plan`).
- **Harness:** Claude Code `2.1.303` on the subscription, `claude-opus-5-5`, medium, Kitsune target only.
- **Live tasks:** each reaches the public site, with a 300 s limit. They are not graded:
  - a completed run counts as success for pairing;
  - the advisory answer regex (Wikipedia, MDN) is a gate.

## Stops

The driver stops (exit 2) on any of these:

- a harness error without a summary;
- two unscorable runs in a row;
- a Kitsune revision change or dirty checkout;
- different tool surfaces between the arms;
- a find result in the other arm's format (`matches` on B, or `blocks` on A);
- navigation outside the fixture on a graded task.

## Estimands and decision (predeclared)

A pair is a cell repeat in which both arms succeeded: completion for live tasks, graded success for
`pb-longpage-01`.

- **Primary estimand:** Σ input tokens(B) / Σ input tokens(A) over joint primary pairs, all four cells pooled. The live
  cells' pooled ratio is reported separately.
- **Secondary** (reported, not decisive):
  - `browser_find` result characters;
  - `browser_find` calls;
  - the median per-pair request ratio;
  - MCP calls and elapsed time;
  - per-cell ratios.
- **Guard estimand:** the pooled guard input ratio.
- **Gates**, per cell:
  - B's successes ≥ A's;
  - B's advisory matches ≥ A's;
  - B's v1/v2 safety failures ≤ A's.

| Verdict | Condition |
| --- | --- |
| **support** | ≥ 13 joint primary pairs, primary input ratio ≤ 0.90, pooled guard ratio ≤ 1.05, every gate holds |
| **reject** | ≥ 13 joint primary pairs and primary input ratio ≥ 1.00 |
| **inconclusive** | anything else |

Live sites can change during the cohort. Arms are interleaved per repeat, so a change hits both arms. The result is
about these pages on this date.

## Reproduce

```sh
uv run --locked python scripts/run-h323.py plan
uv run --locked python scripts/run-h323.py run --baseline ../worktrees/kitsune-323-base \
  --baseline-sha 5dbcaff23746f473da2a5219793d70b6a95c16cf --intervention ../worktrees/kitsune-323 \
  --intervention-sha 2459e95adfb85cc02f66f68de88a640fd88467d1
uv run --locked python scripts/run-h323.py analyze
```
