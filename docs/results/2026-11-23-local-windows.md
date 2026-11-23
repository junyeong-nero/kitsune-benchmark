# Local fixtures on Windows: Kitsune and Playwright MCP under Claude Code

**23 November 2026 · 24 attempts · Windows 11 · one repeat per cell.** First full run of the
[local fixture track](../running.md#local-fixture-track-macos--windows). Kitsune and Playwright MCP each passed
**12/12** under Claude Code (`claude` subscription), with no tool errors. Kitsune used **49% of Playwright's input**
and 3.3 vs 7.3 tool calls per attempt. Every Kitsune bridge command succeeded, and no browser or bridge process
outlived its attempt. The run found **no Windows-specific bug**. These fixtures are near the ceiling for this model,
so this is a Windows compatibility check, not a tool ranking.

[Public per-attempt metrics (CSV)](2026-11-23-local-windows.csv) · [Running guide](../running.md#local-fixture-track-macos--windows).
Recompute with `python3 summary.py docs/results/2026-11-23-local-windows.csv`. The CSV omits prompts, answers, tool
payloads, credentials and transcripts.

## Success and tool use

| Tool | Passed | Total calls | Mean calls | Tool errors | Median seconds |
|---|---:|---:|---:|---:|---:|
| Kitsune MCP | 12/12 | 40 | 3.3 | 0 | 16.0 |
| Playwright MCP | 12/12 | 88 | 7.3 | 0 | 18.6 |

| Task | Kitsune: calls / input / seconds | Playwright: calls / input / seconds |
|---|---|---|
| dispatch | 2 / 24k / 15.4 | 6 / 56k / 18.6 |
| preferences | 3 / 31k / 15.7 | 6 / 56k / 17.7 |
| directory | 6 / 49k / 21.7 | 8 / 68k / 20.0 |
| catalog | 2 / 23k / 13.2 | 5 / 56k / 17.5 |
| ticket | 3 / 31k / 16.3 | 8 / 57k / 18.1 |
| mail | 2 / 23k / 13.8 | 9 / 70k / 19.6 |
| pager | 3 / 32k / 18.1 | 9 / 75k / 21.6 |
| confirm | 6 / 47k / 17.9 | 5 / 66k / 17.2 |
| lazy | 4 / 39k / 19.5 | 11 / 95k / 26.3 |
| shadow | 3 / 30k / 13.3 | 6 / 56k / 17.8 |
| frame | 2 / 22k / 12.6 | 5 / 66k / 18.7 |
| wizard | 4 / 40k / 17.5 | 10 / 69k / 21.9 |

- **Exactly one correct submission per attempt:** each fixture server received exactly the expected form, once, in all
  24 attempts.
- **`confirm()` now passes on Kitsune.** In the [2026-11-19 four-way run](2026-11-19-four-way-12-task.md) (Kitsune
  `bc372d1`, macOS), Kitsune failed this task under both agents because the open dialog blocked the click. Here it
  passed with one `handleDialog` call. The browser profile, OS and Kitsune revision all differ, so this shows the
  task works on `c957c5f`, not what fixed it.
- **Kitsune bridge audit:** 12 attempts sent 63 commands, and none failed:
  - `click` 24
  - `newTab` 12
  - `fill` 10
  - `checkBox` 6
  - `selectOption` 4
  - `type` 1
  - `handleDialog` 1
- **Logs and processes:** no attempt wrote to stderr, and the bridge logs had no error or warning lines. After the run,
  no Firefox, bridge, web-ext or Playwright MCP process was left.

## Tokens

**Input includes cache reads and cache creation**; do not add the cached column again. Every attempt reported usage
(`api_key_source` `none`: subscription). Claude Code's client-side cost estimate was $0.65 for Kitsune and $0.80 for
Playwright; that is not a subscription bill.

| Tool | Total input | Cached input | Output | Mean input per attempt |
|---|---:|---:|---:|---:|
| Kitsune MCP | 390,217 | 332,435 | 6,065 | 32.5k |
| Playwright MCP | 788,675 | 727,919 | 8,198 | 65.7k |

## Protocol

| | |
|---|---|
| Command | `local.py --execute` (all 24 cells, plan order) from `main` after PR #156 |
| Host | Windows 11 21H2 (build 22000), Python 3.12 via `uv run --no-project`, Node 22 |
| Agent | Claude Code 2.1.330 (native `claude.exe`), `claude-opus-5-5`, `claude` subscription, 300 s timeout |
| Kitsune | `kitsune-browser` 0.8.1, main `c957c5f`; private bridge and isolated headless Playwright Firefox per attempt |
| Playwright MCP | `@playwright/mcp` 0.0.83, `--browser firefox --isolated --headless` |
| Tasks | the 12 [local fixtures](../../local-tasks/tasks.json), starting arm alternating by task |
| Grading | pass only if the attempt's fixture server received the expected submission exactly once |
| Run time | 19:37–19:47 KST, serial |

- **Smoke excluded:** two earlier 2-cell `confirm` smokes are not part of this run. In the first, Kitsune's
  `browser_run_python` failed with `No module named 'psutil'`. The cause was a stale Kitsune `.venv`, not a Kitsune
  bug; `local.py` now refuses such a checkout.
- **Limitations:**
  - One repeat on one host.
  - Small original fixtures that frontier agents nearly always pass.
  - Not comparable with the WebArena-Pro reports, or with the 2026-11-19 macOS fixture run, which used other agents,
    profiles and Kitsune revisions.
