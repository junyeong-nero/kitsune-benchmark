# WebArena-Pro: two subscription agents, four browser tools

**20 November 2026 · 208 retained attempts · one repeat per cell.** Kitsune and Playwright passed the same tasks under each model: 13/26 on Claude Code and 12/26 on Codex. On the 12 tasks all four tools solved within each model, Kitsune used **39% of Playwright's input on Claude but 87% on Codex**. The size of the token difference depends on the model and the tasks; it is not a general success-rate or latency advantage.

![Four-way benchmark, 26 WebArena-Pro tasks, 208 attempts. Passed, Claude Code / Codex: Kitsune 13/26 and 12/26; Playwright MCP 13/26 and 12/26; Aside 12/26 and 12/26; EgoLite 12/26 and 12/26. Mean input tokens per attempt: Kitsune 283k / 414k; Aside 463k / 512k; EgoLite 360k / 622k; Playwright MCP 660k / 809k. Mean tool calls per attempt: Kitsune 14.0 / 15.8; Aside 16.1 / 15.6; EgoLite 12.8 / 17.5; Playwright MCP 29.8 / 35.1.](../assets/2026-11-20-webarena-pro-four-way.svg)

The figure's bars are means per attempt from the CSV: input over the attempts that reported usage, tool calls over all 26. The tables below give totals.

[Public per-attempt metrics (CSV)](2026-11-20-webarena-pro-four-way.csv) · [Run instructions](../../README.md). Recompute status counts, token totals/coverage and median latency with `python3 summary.py docs/results/2026-11-20-webarena-pro-four-way.csv`. The CSV deliberately omits prompts, answers, tool payloads, credentials and transcripts.

## Success and tool use

Test and dev have **different denominators**. Mean score is the mean rubric score over 26 tasks; a partial score is not a pass. Calls and tool errors are observed events, not counts of individual UI interactions. Median agent time includes tool use but not reset, login or grading.

| Model | Tool | Test /19 | Dev /7 | Mean score | Total calls | Tool errors | Median seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude | Aside | 6 | 6 | .606 | 418 | 69 | 67.7 |
| Claude | EgoLite | 6 | 6 | .606 | 333 | 33 | 63.9 |
| Claude | Playwright | 7 | 6 | .644 | 776 | 34 | 59.9 |
| Claude | Kitsune | 7 | 6 | .631 | 364 | 27 | 59.9 |
| Codex | Aside | 6 | 6 | .574 | 405 | 49 | 58.6 |
| Codex | EgoLite | 6 | 6 | .587 | 454 | 53 | 68.5 |
| Codex | Playwright | 6 | 6 | .574 | 912 | 41 | 64.0 |
| Codex | Kitsune | 6 | 6 | .574 | 410 | 33 | 70.3 |

- **Claude:** only `wap-077` separated tools: Playwright and Kitsune passed. All four passed 12 other tasks, failed 12 and timed out on `wap-247` (600 seconds per arm).
- **Codex:** all four arms passed the same 12 tasks and failed the same 14. `wap-247` was an ordinary graded failure, not a timeout. Codex passed `wap-077` with every tool but missed `wap-230` with every tool. The pass set differs from Claude's, even though the all-arm pass counts match.
- A tool error need not imply task failure. In the Claude trace, seven Kitsune results included a navigation timeout on three tasks. A follow-up Firefox measurement found one Travelmap page reached DOMContentLoaded in 1.7 s but load in 25.2 s, past the navigation deadline. This identifies a recovery cost, not evidence that changing navigation would have flipped a grade. [Kitsune #561](https://github.com/junyeong-nero/kitsune/issues/561).

## Tokens

**Input includes cache reads**; do not add the cached column again. Claude input also includes cache creation. Output is separate. Claude reported no usage for the four timed-out attempts, so its sums cover 25/26 attempts per tool (not 26 with zero cost). Codex reported usage on all 26. These are usage counters, not subscription bills.

| Model | Tool | Total input | Cached input | Output | Input on all-arm passes | Calls on all-arm passes |
|---|---|---:|---:|---:|---:|---:|
| Claude | Aside | 11,569,519 | 10,801,831 | 98,440 | 2,755,724 | 140 |
| Claude | EgoLite | 9,001,229 | 8,274,988 | 91,826 | 2,142,992 | 94 |
| Claude | Playwright | 16,488,999 | 15,528,255 | 82,606 | 2,779,471 | 201 |
| Claude | Kitsune | 7,075,487 | 6,583,562 | 73,805 | 1,080,616 | 91 |
| Codex | Aside | 13,306,701 | 12,269,056 | 37,373 | 3,126,494 | 128 |
| Codex | EgoLite | 16,177,697 | 14,937,984 | 42,244 | 3,737,376 | 133 |
| Codex | Playwright | 21,045,000 | 19,722,240 | 29,414 | 3,194,106 | 258 |
| Codex | Kitsune | 10,760,825 | 9,730,304 | 26,715 | 2,762,957 | 135 |

The last two columns restrict each model separately to its 12 common successes, so an early failure cannot look token-efficient. On Codex the Kitsune/Playwright input ratio changes from 51% over **all** tasks to 87% on **common successes**. On Claude the corresponding figures are 43% and 39%.

## Protocol and exclusions

- [Upstream](https://github.com/McGill-NLP/webarena-pro/tree/42f4a076), [frozen manifest](../../four-way/testset/webarena-pro.json): 19 test and seven dev tasks across eight small self-hosted apps. Every rubric node starts with `backend_state` or `answer_match`; no baseline-dependent tasks. Core evaluates the final site state and/or answer. We supplied no Playwright trajectory evidence or working LLM judge. **Do not compare these scores to the full paper leaderboard.**
- `claude-opus-5-5` and `gpt-6.1-sol` drove the browser locally. Aside/EgoLite used existing profiles; Playwright MCP and Kitsune (`4e6d6fb`) used isolated headless Firefox. Sites and Core ran in a Codespace over forwarded ports. Each attempt recreated its sites and signed in before measurement. We did not measure tunnel latency separately.
- Retain one valid measurement per model/task/tool. Exclude pre-fix EgoLite sign-in attempts, quota/setup-only failures and duplicate retries; **do not** exclude measured timeouts or genuine failures. A macOS cleanup exception, transcript parser fix and remote setup interruptions were runner issues, not task failures. Raw evidence remains private.
- One repeat, selected lightweight sites, different browser engines/profiles, batching opportunities and different subscription accounting limit any generalization. The earlier [12-fixture study](2026-11-19-four-way-12-task.md) is a different benchmark, not extra samples for this one.
