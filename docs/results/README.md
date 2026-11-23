# Result reports

[Documentation index](../README.md) · [Running guide](../running.md) · [Archived reports](../archive/results/README.md)

Reports from the current `four-way/` suite, newest first. Each is a dated record of one execution: a later change
to the configured models or billing does not change what an older report measured. Both reports below predate the
current Claude-only matrix (`claude-api`, then `claude`) and include Codex.

| Date | Report | Agents | Scope and outcome |
| --- | --- | --- | --- |
| 2026-11-20 | [WebArena-Pro four-way, 26 tasks: Aside, EgoLite, Playwright MCP and Kitsune](2026-11-20-webarena-pro-four-way.md) ([CSV](2026-11-20-webarena-pro-four-way.csv)) | `claude-opus-5-5` (Claude Code), `gpt-6.1-sol` (Codex), subscriptions | 208 attempts (19 test + 7 dev per arm). Claude: Aside/EgoLite 12, Playwright/Kitsune 13 passes. Codex: all four 12 passes. On each model's 12 common successes, Kitsune used 39% (Claude) and 87% (Codex) of Playwright input. |
| 2026-11-19 | [Four-way, 12 tasks: Aside, EgoLite, Playwright MCP and Kitsune](2026-11-19-four-way-12-task.md) | `claude-opus-5-5` (Claude Code), `gpt-6.1-sol` (Codex), subscriptions | 12 original local fixtures × 4 arms × 2 agents, 96 attempts. Passed: Claude 47/48, Codex 43/48. Kitsune used the fewest tool calls and least input. A different benchmark from the WebArena-Pro run, not extra samples for it. |

## Evidence standard

Each new report should identify:

- Exact tasks, repetitions, order and stopping policy.
- Harness (`claude-api` or `claude`), model and browser/tool pins.
- Initial state, tool policy and how success was graded.
- Graded failures vs timeouts vs infrastructure or agent errors, and any excluded attempts.
- Usage fields and cache accounting.
- Reproduction command and private artifact identifiers, without publishing credentials, site data or raw transcripts.
