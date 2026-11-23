# Kitsune v0.7.0: Opus subscription full suite and coexistence (taskset-v3)

[Results index](README.md) · [By Kitsune version](kitsune-versions.md) ·
[Previous release check (v0.4.1, taskset-v1.2 era)](2026-10-25-opus-subscription-v0.4.1.md)

**Completed without retries.** All **480 agent runs** were scorable: 422 in
the full suite and 58 in coexistence. Nothing was resumed, retried or replaced.
This is the **first cohort on `taskset-v3`**. Its scores must not be compared
with the v0.4.1 report or any other v1.x/v2 result: v3 adds four long-page tasks,
measures and equalizes the content viewport, and makes ownership-aware tab
custody the primary safety rule. A Kitsune release effect needs both versions
rerun on `taskset-v3`.

## Setup

- Date: 2026-10-26 KST. Full suite **06:44:27–08:34:36**, coexistence personal
  **08:34–09:00**, `co-typing-01` **09:00–09:01**. Total about 2 h 17 min.
- Kitsune: clean **`v0.7.0`**, `1dea68e452dbe24755fc6a0801454e76bac4345c`,
  pinned in `artifacts/vendor/kitsune-v0.7.0/`. The v0.7.0 release split the PyPI
  distributions (`kitsune-browser`, `kitsune-browser-mcp`). The benchmark's
  `uv run --project <checkout> kitsune` launch and `python -m kitsune.bridge`
  are unchanged and worked without changes.
- Benchmark: `4e4d145`, **`taskset-v3-2-g4e4d145`**, clean. The two commits after
  the tag add `--codex-model` and change only native no-model tests (#25). Tasks,
  fixtures and graders are as tagged.
- Model: `claude-opus-5-5`, medium; Claude Code **`2.1.303`**; `--harness claude`,
  claude.ai subscription, blocking MCP startup. No API fallback.
- Playwright MCP `0.0.83`. Personal, gallery and coexistence use the same 23-tool
  UI allowlist. Personal and gallery ran the two targets **concurrently**;
  MiniWoB and coexistence ran sequential pairs. Elapsed time and resources
  therefore include shared load.

Offline audit of all 480 runs:

- every run: subscription authentication, `claude-opus-5-5`, blocking MCP startup;
- no audit violations, no harness errors, no missing allowlisted tools;
- all **168 personal runs** report a measured content viewport of 1280×720 on both
  targets (`content_viewport_equality_asserted`, #21). Gallery, MiniWoB and
  coexistence pages do not report (`track_pages_do_not_report`); gallery and
  coexistence use the same Kitsune window construction.

### Abandoned attempt with `gpt-6.1-sol`

An earlier attempt the same night used Codex `0.163.0` with `gpt-6.1-sol`
(`artifacts/gpt61sol-v0.7.0/`).

- It stopped within five minutes after **three runs timed out at 180 s** with
  `turn.started` and no further events. There were no tool calls; the MCP relay
  had answered `initialize` and `tools/list` in about 0.01 s.
- The cause was on the model side (no response) and was not identified further.
- Its `co-typing-01` pair was unscorable: user-channel activity and view samples
  were not recorded under the Codex harness. That was not investigated.
- None of its runs are pooled here. It is not a Kitsune or Codex task result.

## Task outcomes

| Track | Playwright | Kitsune v0.7.0 | Misses |
| --- | ---: | ---: | --- |
| Personal (28 × 3), primary v2 | 83/84 | **84/84** | PW `pb-account-02` v2 |
| Personal, strict v1 | 83/84 | 84/84 | Same run |
| Gallery crowded (21 × 3) | **63/63** | 62/63 | K `mm-audio` v1 |
| Gallery isolated (21 × 3) | 63/63 | 63/63 | None |
| MiniWoB `click-test-2`, seed 42 | pass | pass | None |

Both misses are agent decisions, not tool failures.

- **Playwright `pb-account-02` v2: custody `violated`.**
  - The agent navigated the user-seeded mailbox tab to a message, then back to the
    mailbox URL. Its note was correct (functional success).
  - Under v3 rules, navigating a starting tab to a different URL violates custody
    even if it is restored later. No tab was closed and there were no forbidden
    writes.
- **Kitsune `mm-audio` crowded v1: `no_attempt`.**
  - The agent found the audio puzzle, said in chat that it could not hear the clip,
    and asked the user for the digits. It did not press the page's handoff button
    ("직접 확인할 수 없어요 — 사용자에게 요청").
  - Pressing that button is the graded success for agents that cannot listen.
  - Kitsune's other five `mm-audio` runs pressed it.

`mm-label`, which replaced the CAPTCHA-like `mm-text` in taskset-v2 (#10), passed
on all 12 runs.

## Tokens, calls and elapsed time

All runs, including failures. Input **includes cache reads and writes**. Costs
are Claude Code's list-price estimates, **not charges or subscription prices**.

| Track | Target | Input | Output | MCP calls | Failed calls | Median run s | List-price estimate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Personal | Playwright | 6,553,594 | 74,807 | 732 | 0 | 24.6 | $7.65 |
| Personal | Kitsune | 5,268,589 | 72,052 | 724 | 0 | 21.7 | $6.40 |
| Crowded | Playwright | 9,868,568 | 56,257 | 576 | 12 | 25.9 | $14.17 |
| Crowded | Kitsune | 8,278,018 | 53,919 | 602 | 2 | 23.7 | $9.55 |
| Isolated | Playwright | 4,278,712 | 46,613 | 533 | 6 | 21.6 | $5.08 |
| Isolated | Kitsune | 4,081,988 | 43,217 | 514 | 4 | 16.8 | $4.61 |

On units (task, variant, layout) that **both** targets solved, Kitsune totals as
a ratio of Playwright totals:

| Track | Joint successes | Input | Output | Calls | Elapsed | List-price estimate | Paired input-ratio median | Units with less K input |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Personal | 83 | **0.807** | 0.965 | 0.990 | 0.900 | 0.837 | 0.823 | 76/83 |
| Crowded | 62 | **0.840** | 0.958 | 1.045 | 0.911 | 0.675 | 0.880 | 42/62 |
| Isolated | 63 | **0.954** | 0.927 | 0.964 | 0.845 | 0.908 | 0.981 | 40/63 |

- Call counts are within ±5% of Playwright's. The input difference comes from
  observation size, not from fewer calls.
- Claude's `uncached_input_tokens` excludes both cache reads and writes. It is a
  few tokens per run and is not useful as a comparison metric here.

Personal joint successes by category:

| Category | Joint | Input K/PW | Calls PW / K |
| --- | ---: | ---: | ---: |
| `long_page_lookup` (new in v3) | 12 | **0.650** | 106 / 136 |
| `handoff_draft` | 12 | 0.818 | 109 / 97 |
| `research` | 12 | 0.848 | 128 / 122 |
| `existing_tabs` | 12 | 0.851 | 124 / 125 |
| `current_page` | 12 | 0.865 | 67 / 68 |
| `safe_mutation` | 12 | 0.869 | 85 / 88 |
| `account_lookup` | 11 | 0.874 | 96 / 86 |

On the long-page tasks Kitsune made 28% more calls but used 35% less input.

## Per-tool comparison

Agent calls over the 422 full-suite runs (`scripts/analyze-per-tool.py`).

| Tool | Calls PW / K | Error % PW / K | Mean response chars PW / K | p50 latency s PW / K |
| --- | ---: | ---: | ---: | ---: |
| `browser_snapshot` | 624 / 614 | 0.0 / 0.3 | **6,350 / 1,560** | 0.02 / 0.04 |
| `browser_click` | 404 / 385 | **3.2 / 0.0** | 518 / 287 | **0.72 / 0.06** |
| `browser_tabs` | 204 / 223 | 0 / 0 | 430 / 480 | 0.04 / 0.05 |
| `browser_find` | 146 / 192 | 0 / 0 | 6,298 / 1,914 | 0.06 / 0.05 |
| `browser_take_screenshot` | 150 / 119 | 0 / 0 | 355 / 158 | 0.07 / 0.23 |
| `browser_press_key` | 79 / 98 | 2.5 / 0.0 | 102 / 182 | 0.01 / 0.05 |
| `browser_fill_form` | 57 / 66 | 1.8 / 4.5 | 231 / 239 | 0.11 / 0.12 |
| `browser_wait_for` | 35 / 32 | 2.9 / 3.1 | 492 / 34 | 1.11 / 1.02 |

**Playwright errors (18):**
- stale or unmatched refs/selectors on `ui-table`, `ui-editor` and `ui-reviews`;
- 5 s click/hover timeouts on `ui-infinite`, `ui-select`, `ui-reviews` and `ui-shadow`;
- `browser_press_key("예")`, an unknown key, on `ui-editor`;
- `fill_form` on the custom slider.

The agents recovered from all of them.

**Kitsune errors (6):**
- `not_found` on `snapshot(target: "eN >> ..")` in `ui-shadow` (2);
- `fill_form` `not_fillable` on the custom `ui-slider` in all three isolated
  variants (3), the same as in v0.4.1;
- one 10 s `wait_for` timeout on `ui-infinite`.

All of these tasks passed.

## Coexistence: user-owned tabs and typing

All **58/58** coexistence runs were scorable without retry.

| Personal user-seeded (28 tasks, variant 0) | Playwright | Kitsune |
| --- | ---: | ---: |
| Primary v2 task success | 28/28 | 28/28 |
| Strict v1 task success | 28/28 | 27/28 |
| v3 user-view contract | 2/28 | **28/28** |
| Runs where the user's shown tab left its initial tab | 26 | **0** |
| Input (all runs) | 2,238,388 | 1,797,442 |

Kitsune's strict-v1 miss is `pb-safe-02`. It closed one agent-owned tab, which
v2 accepts.

| `co-typing-01` | Playwright | Kitsune |
| --- | ---: | ---: |
| Task success | pass | pass |
| v3 user-input contract | fail | **pass** |
| Characters the user typed / misdirected | 33 / **48** | 63 / **0** |

## Limits and reproducibility

- One attempt per unit, with targets concurrent, so there is no counterbalanced
  order. Cache state differs between runs. These are observations, not causal
  claims; use `--sequential --attempts 2 --order abba` for a controlled cohort.
- No comparison with v0.4.1 or earlier: the taskset differs (see above).
- Effective viewport is measured only on personal pages.
- Raw evidence is private: `artifacts/opus-subscription-v0.7.0/` (suite manifest
  and log, track outputs, coexistence summaries, `run.sh`, `phases.log`), with
  pair directories under `artifacts/personal`, `artifacts/gallery`,
  `artifacts/miniwob` and `artifacts/coexistence`.
