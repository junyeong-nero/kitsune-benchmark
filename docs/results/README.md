# Result reports

[Documentation index](../README.md) · [Running guide](../running.md)

Reports are dated records of actual executions. **Changing the configured model
does not change the model used in an older report.** Different tasks, models,
tool policies and instrumentation are not a single comparable leaderboard.
For the same reports grouped by Kitsune revision, see
[results by Kitsune version](kitsune-versions.md).

| Date | Report | Model | Scope and outcome |
| --- | --- | --- | --- |
| 2026-10-28 | [H321: no link URLs in truncated snapshots, live sites — stopped](2026-10-28-h321-live-urls-stopped.md) | `claude-opus-5-5`, medium (Claude Code subscription) | Kitsune `5dbcaff` vs `9608032` (kitsune#321). **No verdict**: stopped after 9 of 36 runs because no live run took an untargeted snapshot, so the change was never exercised. On live tasks `browser_find` produces 83% of tool-result characters (single results up to 39.6k): the next lever |
| 2026-10-28 | [H310: snapshot budget fills `main` first, drops link URLs when truncated, Kitsune A/B](2026-10-28-h310-snapshot-budget-ab.md) | `claude-opus-5-5`, medium (Claude Code subscription) | Kitsune `f0ca705` vs `d571963` (kitsune#310). 66 runs, all successful, none unscorable. Crowded primary input ratio **0.768** (24/24 pairs; `ui-sortable` 0.60, `mm-label` 0.63, `ui-shadow` 0.70), requests 177 → 140, `browser_find` 60 → 18. Pooled guard ratio 0.973 → **support** |
| 2026-10-28 | [New tracks: external-v1 + coexistence-local-v1](2026-10-28-new-tracks-v0.7.0.md) | `claude-opus-5-5`, medium (Claude Code subscription) | First run of the two new tracks on Kitsune v0.7.0, 110 scorable runs, no retries. External MiniWoB 7/7 both, 3 live tasks completed (advisory matches 2/2 both). Coexistence user-seeded v2 28/28 both, **v3 view 2/28 PW vs 28/28 K**; `co-typing-01` v0-2: PW 2/3 success, 0/3 user-input, 393 misdirected characters, K 3/3, 0; protect arm 28/28, 1 refusal |
| 2026-10-28 | [H18: list short similar-item runs, Kitsune A/B](2026-10-28-h18-collapse-ab.md) | `claude-opus-5-5`, medium (Claude Code subscription) | Kitsune `dbc84f8` vs `53cceea` (runs hiding ≤ 5 listed in full), 66 scorable Kitsune-only runs, all successful. `ui-table` isolated request ratio 0.578, table input ratio 0.679, expansion reads 47 → 0; guard input `ui-infinite` 1.171 and `pb-longpage-01` 1.071 (change not visible there), recovered errors 4 vs 0 → **inconclusive**, no adoption claim |
| 2026-10-26 | [Kitsune v0.7.0 full suite + coexistence, subscription](2026-10-26-opus-subscription-v0.7.0.md) | `claude-opus-5-5`, medium (Claude Code subscription) | **First `taskset-v3` cohort**: 480 scorable runs, no retries. That is 422 `taskset-v3` runs plus 58 runs of the pre-freeze coexistence draft (`coexistence-v0-draft`). Personal PW 83/84 vs K 84/84; crowded 63/63 vs 62/63; isolated both 63/63; MiniWoB both pass. Joint-success input K/PW 0.807 / 0.840 / 0.954 at ±5% calls; long-page input 0.650. Coexistence v3 view 2/28 vs 28/28, typing misdirected 48 vs 0. Not comparable with v1.x/v2 reports |
| 2026-10-25 | [Issue #18: `ui-table` model rounds](../experiments/2026-10-25-issue-18-ui-table-rounds.md) | Offline, 16 existing v0.4.1 validation runs | Figures reproduce (isolated requests 25 vs 36); same observation calls (24 vs 24), but Kitsune issues 19 in observation-only rounds vs 4 for PW, mostly expanding or checking collapsed-list results; extra prefix re-sends +100,855 tokens vs input +98,020. Draft A/B hypothesis only |
| 2026-10-25 | [v0.4.1 issue candidates: 40 additional model runs](2026-10-25-v0.4.1-model-validation.md) | `claude-opus-5-5`, medium (Claude Code subscription) | Separate targeted cohort, all scorable: incremental deletion PW 3/3 vs K 0/3; newline 3/3 vs 2/3 with disclosed fixture caveats; tables both 8/8, K input +4.4% crowded / +27.3% isolated; tabs and slider both 3/3. After review: Kitsune #267 and benchmark #11 filed; four existing issues received evidence comments |
| 2026-10-25 | [Kitsune v0.4.1 full suite + coexistence, subscription](2026-10-25-opus-subscription-v0.4.1.md) | `claude-opus-5-5`, medium (Claude Code subscription; blocking MCP startup) | 448 selected scorable runs after one explicit setup retry (449 attempts). Personal PW 72/72 vs K 69/72, both 72/72 on v2; crowded both 63/63; isolated 63/63 vs 62/63; MiniWoB both pass. Coexistence view left initial tab: 22 vs 0; typing misdirected characters: 36 vs 0. Separate cohort from v0.4.0 API |
| 2026-10-25 | [Kitsune v0.4.1 subscription attempt — incomplete](2026-10-25-opus-subscription-v0.4.1-incomplete.md) | `claude-opus-5-5`, medium (Claude Code subscription) | Stopped on MCP startup error; personal v0 PW 24/24 successes, Kitsune 2 successes + 1 unscorable out of 3 attempted. No full-suite score or comparison with the API cohort |
| 2026-10-24 | [Opus full suite, Kitsune v0.4.0 + coexistence](2026-10-24-opus-full-v0.4.0.md) | `claude-opus-5-5`, medium (Claude Code API, bare) | `taskset-v1.2`, 398 scorable runs, $29.14: personal 72/72 PW vs 69/72 Kitsune (71/72 on contract v2), crowded 63/63 vs 62/63, isolated 62/63 vs 60/63; Kitsune now 0.83–0.93× cost of Playwright on joint successes (v0.3.1: 0.90–1.25×), screenshots 470 → 106; **regression: `fill_form` checkbox blocked under core caps** (kitsune#236); collapsed table rows unreachable (kitsune#237); coexistence v3 user view 2/24 PW vs 23/24 Kitsune at 0.84× cost |
| 2026-10-23 | [Coexistence draft: user-seeded + typing user](2026-10-23-coexistence-user-seeded.md) | `claude-opus-5-5`, medium (Claude Code API, bare) | Draft track, 50 valid scorable runs, $2.83: 24 personal tasks user-seeded v1 24/24 both, **v3 user view 2/24 PW vs 24/24 Kitsune**; `co-typing-01` 87 vs 0 misdirected keystrokes; Kitsune 1.19× cost, 1.37× calls; first typing pair invalid (content BiDi input broke Juggler; fixed) |
| 2026-10-23 | [Opus full suite, Kitsune v0.3.1](2026-10-23-opus-full-v0.3.1.md) | `claude-opus-5-5`, medium (Claude Code API, bare) | `taskset-v1.2` (same 23-tool allowlist), 398 scorable runs, $31.67: personal 72/72 PW vs 71/72 Kitsune; crowded 63/63 vs 61/63, isolated 62/63 vs 60/63; Kitsune 1.3–1.7× calls on joint successes; snapshot lacks text/link URLs, Playwright selector syntax unsupported, hover does not scroll |
| 2026-10-23 | [Hypothesis #7: lean + keypress, C1](2026-10-23-issue-7-lean-keypress-c1.md) | `claude-haiku-5-5`, medium (Claude Code API, bare) | Kitsune `c1f23b8`, 396 scorable Kitsune-only runs, $1.21, AB/BA: `ui-sortable` 0/6 → 6/6; personal 69/72 both; same-success personal input +10.1% (definition alone +7.3%) → **rejected** |
| 2026-10-23 | [Opus full suite, Kitsune v0.3.0](2026-10-23-opus-full-v0.3.0.md) | `claude-opus-5-5`, medium (Claude Code API, bare) | `taskset-v1`, 398 scorable runs, $27.98: personal 67/72 PW vs 68/72 Kitsune; gallery crowded 63/63 vs 60/63, isolated 63/63 vs 57/63; Kitsune cost ×0.67 on crowded; snapshot drops `img`, lean lacks keypress; two grader defects |
| 2026-10-22 | [Tool usage inventory](2026-10-22-tool-usage.md) | Offline, 196 existing Kitsune runs | 2,084 agent calls; exposure-aware counts and error categories; status/page-info candidates for default-surface ablation, not API removal |
| 2026-10-22 | [Sonnet / Opus targeted follow-up](2026-10-22-sonnet-opus-target-view.md) | Sonnet 5.5 / Opus 5.5, medium (Claude Code API, bare) | 16 scorable runs in 4m37s; catalog requests −13.8% / −11.8%, elapsed −8.5% / −17.3%, but cost +15.1% / +13.5%; no-model probe confirms video screenshot(ref) failure |
| 2026-10-22 | [Target/action view A/B](2026-10-22-target-view-ab.md) | `claude-haiku-5-5`, medium (Claude Code API, bare) | 60 scorable runs; native/catalog both 28/30 strict, requests −2.2% but input +6.0%, elapsed +2.9%, cost +10.0%; chart assets absent from source snapshot, video crop divergence; no global-default adoption |
| 2026-10-22 | [Disclosure × expect A/B](2026-10-22-disclosure-ab.md) | `claude-haiku-5-5`, medium (Claude Code API, bare) | 72 scorable Kitsune runs, 2×2 factorial: rich-only requests +3.0%; combined −7.9% with task-sensitive timing; no-model probes confirm ref invalidation and ungrounded expect selectors; paid selector not justified yet |
| 2026-10-22 | [Kitsune 0.3.0 rerun](2026-10-22-kitsune-0.3.0.md) | `claude-haiku-5-5`, medium (Claude Code API, bare/full descriptions) | 96 scorable runs; bare PW/Kitsune 22/24 vs 23/24, full 23/24 vs 19/24 (Kitsune v2: 22/24); Kitsune input +4.2% / +16.2%; default now lean |
| 2026-10-21 | [Component gallery](2026-10-21-gallery.md) | `claude-haiku-5-5`, medium (Claude Code API) | 21 tasks × 2 layouts: crowded 20/21 Playwright vs 15/21 Kitsune (3.23× input on joint successes); isolated 21/21 vs 18/21 (1.88×); Kitsune fails shadow DOM, iframe, native video |
| 2026-10-21 | [Token efficiency analysis](2026-10-21-token-efficiency.md) | `claude-haiku-5-5`, medium (Claude Code API, `--bare`) | 24 pairs, 23/24 each, $0.099; Kitsune +30.5% input, all from the fixed prefix (tool definitions × requests); client truncates descriptions; savings estimates |
| 2026-10-21 | [All 24 personal tasks, Claude Code](2026-10-21-personal-24-claude-haiku.md) | `claude-haiku-5-5`, medium (Claude Code) | 24 variant-0 pairs / 48 agent runs, all scorable; 21/24 Playwright vs 23/24 Kitsune; Kitsune 1.69× input on the 20 jointly successful tasks |
| 2026-10-19 | [Six-task personal pilot](2026-10-19-personal-six-task.md) | `gpt-6-luna`, medium | Six variant-0 pairs / 12 agent runs, all scorable; current grader 3/6 Playwright vs 4/6 Kitsune; cache intervention and format/safety caveats documented |
| 2026-10-19 | [Personal current-page pair](2026-10-19-personal-current-page.md) | `gpt-6-luna`, medium | `pb-current-01`, variant 0; one attempt per MCP; both externally scorable, functionally successful and safety-passing |
| 2026-10-18 | [MiniWoB++ pilot](2026-10-18-miniwob.md) | `gpt-6.1-sol`, medium | Only `click-test-2`, seed 42; both passed original reward evaluation in a non-standard Firefox/MCP track |
| 2026-10-18 | [Read-only smoke](2026-10-18-smoke.md) | `gpt-6.1-sol`, medium | One Example Domain pair; execution completed, no external task-success label |

## Evidence standard

Each new report should identify:

- Exact selected task(s), variant/seed, repetitions, order and stopping policy.
- Requested model/effort, Codex and MCP/browser pins, source cleanliness/hashes.
- Initial/reset state, tool allowlist and external success/safety checks.
- Scorable vs ordinary task failure vs execution/setup error.
- Reported usage fields, cache accounting, agent calls and hidden harness work.
- Instrumented timing/resource scope and important confounders.
- Reproduction command and private artifact identifiers, without publishing
  credentials, session tokens, real page contents or unreviewed raw logs.

The six-task personal pilot is recorded, **only for variant 0 with one attempt
per MCP**. Later reports include 24-task model evaluations and targeted repeated,
counterbalanced trials; their scope and limitations are recorded in each report.
No real-account experiment or WebArena result has been recorded. Native-browser
fixture tests and the TTL cache intervention use no model and must not be counted
as LLM benchmark runs. See [optimization findings](../optimization-findings.md)
for the evidence and precise observability limits.
