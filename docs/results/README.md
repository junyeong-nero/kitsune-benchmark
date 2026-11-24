# Result reports

[Documentation index](../README.md) · [Running guide](../running.md) · [Archived reports](../archive/results/README.md)

Reports from the current `four-way/` suite and the local fixture track (`local.py`), newest first. Each is a dated record of one execution: a later change
to the configured models or billing does not change what an older report measured. The 2026-11-19 and 2026-11-20
reports predate the current Claude-only matrix (`claude-api`, then `claude`) and include Codex.

| Date | Report | Agents | Scope and outcome |
| --- | --- | --- | --- |
| 2026-11-24 | [Kitsune main `c7149a8` on WebArena-Pro, `claude-api`](2026-11-24-kitsune-main-c7149a8-claude-api.md) ([CSV](2026-11-24-kitsune-main-c7149a8-claude-api.csv)) | `claude-opus-5-5` (Claude Code), API key | Main after the #613–#619 fixes, Kitsune arm only, 26 attempts. 13/26 passed vs 12/26 on v0.8.2; only `wap-077` changed, and the agent's reading caused that. Input −18%, tool errors 15 → 7; no grade came from a tool bug. Transcript review lists 2 bug and 7 enhancement leads, not yet filed. |
| 2026-11-23 | [Local fixtures on Windows: Kitsune and Playwright MCP](2026-11-23-local-windows.md) ([CSV](2026-11-23-local-windows.csv)) | `claude-opus-5-5` (Claude Code), subscription | First full local-track run, Windows 11, Kitsune `c957c5f`, 24 attempts. Both arms 12/12 with no tool errors; Kitsune used 49% of Playwright's input (3.3 vs 7.3 calls per attempt). No Windows-specific bug; Kitsune's `confirm()` task, failed on 2026-11-19, passed. Compatibility check, not a ranking. |
| 2026-11-23 | [Kitsune v0.8.2 on WebArena-Pro, `claude-api`](2026-11-23-kitsune-0.8.2-claude-api.md) ([CSV](2026-11-23-kitsune-0.8.2-claude-api.csv)) | `claude-opus-5-5` (Claude Code), API key | Release check, Kitsune arm only, 26 attempts. 12/26 passed vs 13/26 on 2026-11-20; only `wap-077` changed. Input and calls within 1–2%; no navigation timeouts. No material change. Transcript review filed Kitsune #613–#619; #613 (`tab.text()` returns one `<article>`) caused the `wap-341` fail. |
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
