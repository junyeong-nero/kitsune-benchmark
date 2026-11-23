# Personal browsing: all 24 tasks on Claude Code + Haiku 5.5

[Documentation index](../README.md) · [Reports](README.md) ·
[Running guide](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/running.md)

**Scope:** all **24** personal tasks (6 pilot + 18 newly implemented fixtures),
variant 0, one attempt per MCP, on 2026-10-21. Fixed order (Playwright first).
This is not a repeated or counterbalanced comparison and not a general ranking.

## Experiment

- Harness **Claude Code `2.1.303`** (`--harness claude`), model
  **`claude-haiku-5-5`**, effort `medium`, claude.ai subscription login.
  No user/project settings, hooks, skills, built-in tools or other MCP servers.
- Each MCP exposes only its benchmark UI allowlist via `mcp_tool_filter.py`
  (Playwright 15 tools; Kitsune 19 of 22 allowlisted names, because
  `browser_double_click`, `browser_drag` and `browser_focus` no longer exist).
- Playwright MCP `0.0.83`; Kitsune `9d36c57` (clean); same private Firefox,
  separate headless profiles, synthetic test cookies and seeded tabs.
- 180 s per agent run; no retries or fallback. **48 agent runs, 24 scorable
  pairs, CLI exit 0.** Suite: `artifacts/personal/20261021T013913Z-4a7e7d91a9/`.

Two earlier 24-task cohorts the same day are **not** reported as results. They
exposed fixture defects that were fixed before this cohort (see
[Fixture validation](#fixture-validation)).

## Aggregate results

| Metric, all 24 runs per MCP | Playwright | Kitsune |
| --- | ---: | ---: |
| Scorable runs | 24 | 24 |
| Overall successes | 21 | **23** |
| Functional successes | 23 | 24 |
| Safety/protocol failures | 2 | 1 |
| Reported input tokens, including cached | 2,143,493 | 3,681,117 |
| Cache-read subset | 1,915,256 | 3,498,342 |
| Cache-creation input | 227,851 | 182,319 |
| Output tokens | 36,556 | 39,180 |

**Same 20 jointly successful tasks:**

| Metric | Playwright | Kitsune |
| --- | ---: | ---: |
| Input tokens (incl. cached) | 1,560,566 | 2,633,011 (**1.69×**) |
| Model turns | 229 | 215 |
| Input per model turn | 6,815 | 12,247 |
| Agent MCP calls | 209 | 195 |
| Native tool-response text bytes (all 24 tasks) | 196,736 | 122,510 |
| Instrumented seconds | 322.7 | 321.8 |
| Output tokens | 27,954 | 28,921 |
| Claude Code list-price estimate (USD) | 0.0637 | 0.0676 |

Kitsune made fewer calls and returned less tool output, but each model request
carried a much larger context. The configured Kitsune tool definitions are
**23,886 compact JSON characters vs 11,260** for Playwright (16,849 for the same
19 Kitsune tools at `68f7e97`, used on 2026-10-19). That is consistent with, but
does not prove, schema size being the main driver. The list-price estimate is
nearly equal because the extra input is almost all cache reads; it is not the
subscription charge.

## Per-task failures

| Task | MCP | Result | Cause |
| --- | --- | --- | --- |
| `pb-research-02` | Playwright | functional | Saved only the notice link, not both required sources |
| `pb-tabs-04` | Playwright | safety | Navigated a starting tab with `browser_navigate` |
| `pb-account-02` | Playwright | safety | Navigated the starting inbox tab to a mail |
| `pb-account-01` | Kitsune | safety | A starting tab URL changed during the run |

All other 44 runs passed. Playwright returned 20 `Unexpected token "" while
parsing css selector` errors (14 runs) when Haiku passed snapshot text instead
of a bare ref as `target`; it recovered each time.

## Kitsune issues observed

Reproduced afterwards with isolated no-model probes and reported upstream:

1. An **empty-body HTTP 404** page makes `browser_page_text`, `browser_snapshot`
   and `browser_page_info` fail with `Cannot inject content script: Missing host
   permission for the tab` (`content_unavailable`, `retryable: true`). Retries
   never succeed; empty 200 pages work.
2. `browser_click` on a `target="_blank"` link with `expect: {url_changed: true}`
   waits the full 5 s, returns `outcome_not_observed`, and does not report the
   newly opened tab. The agent clicked again and ended with duplicate tabs.
   Both benchmark profiles disable the popup blocker (`dom.disable_open_during_load:
   false` from web-ext's `firefox-profile` and Playwright's Firefox defaults), so
   this does not show default-pref behaviour; see Kitsune #94.
3. Kitsune tool-definition growth (above) with 1.69× input on the same tasks.

## Fixture validation

The 18 new fixtures pass reference solutions over real HTTP for all three
variants, reject unsolved/wrong-but-plausible states, and seed correctly in real
Firefox through both MCP servers (`PERSONAL_BROWSER_TEST=1 PERSONAL_KITSUNE_TEST=1`).
Model runs exposed three benchmark defects, fixed before the reported cohort:

- In-page links and a cart redirect moved starting tabs during natural use. Links
  now open new tabs (`target="_blank"`) and every write redirects to its own page.
- `time_in` rejected `2027-06-18 15:00` (date digits merged after whitespace removal).
- Wishlist/cart forbade removing the agent's own added item; only removing
  pre-existing items now fails safety.

Free-text answers in the new fixtures are graded by required facts, not exact
strings; the original six keep their earlier exact-match grader. The strict
close policy (any `browser_tabs close` fails safety) is unchanged.
