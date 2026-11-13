# Exhibition: Aside and ego(lite) on the external MiniWoB++ tasks

[Results index](README.md) · [External track](../external.md) ·
[Reference cohort: Kitsune main `ad04bac`](2026-11-08-main-ad04bac.md)

**Bottom line:**

- **Both solved all 7 tasks**, as Playwright and Kitsune did in the reference cohort.
- **They used about half the calls and input.** Calls: Aside 27, ego 30, Playwright 57, Kitsune 54. Input tokens:
  Aside 208k, ego 217k, Playwright 476k, Kitsune 463k.
- **The reason is the tool shape, not the browser.** Each arm has one code-execution tool. The agent opened a page and
  read it in one call, then clicked and re-read it in one call.
- **This is an exhibition, not part of the head-to-head.** The tool policy, browser and profile differ (see
  [Not comparable](#not-comparable)). One attempt per task.

## Arms

| Arm | Product | Tool given to the model | Browser |
| --- | --- | --- | --- |
| `aside` | [Aside](https://aside.com) CLI `1.26.1107.24`, Aside Browser `1.0.1022.1` | `repl` from `aside mcp` (Playwright-style JavaScript; 120 s per call). `exec`, `browser_profiles` and `memory_search` are filtered out. | The installed Aside Browser, signed in, its `Profile 0` |
| `ego` | [ego(lite)](https://github.com/citrolabs/ego-lite) `0.6.2.9` (Chromium 156) | `run_script`: `kitsune_benchmark/ego_mcp.py` runs `code` with `ego-browser nodejs` (120 s per call). The description is the vendor's `ego-browser skill` guide (v2.2.0), unedited. | The installed ego lite app; one task space per run |

- **Why only `repl` for Aside:** `exec` hands the task to Aside's own agent and model, so the run would no longer
  measure the fixed outer model.
- **Why a wrapper for ego:** ego(lite) ships no MCP server. Its agents run `ego-browser nodejs` as a shell heredoc,
  and the harness gives the model no shell. The wrapper exposes only that entry point.

## Design

- **Tasks:** the 7 MiniWoB++ tasks of `external-v1`, seed 42, upstream `33c3b4d` (task HTML SHA-256 identical to the
  reference cohort's). The prompt is unchanged, including "Use only the provided UI observation and interaction tools.
  Do not inspect or modify ... reward variables, timers, or evaluation instrumentation."
- **Model and harness:** `claude-opus-5-5`, medium, Claude Code `2.1.303` on the subscription.
- **Benchmark:** `taskset-v3.5-13-g53d6a9b` plus this change (manifests record `dirty`).
- **Runs:** one per task and arm, 14 in all. `mw-click-test-2` ran first as a check, then the other 6. Aside ran
  before ego in each pair, sequentially.
- **When:** 2026-11-09, 22:12–22:20 KST.
- **Reference:** Playwright MCP `0.0.83` and Kitsune `ad04bac` from the
  [2026-11-08 lite cohort](2026-11-08-main-ad04bac.md) (`taskset-v3.5-6`). Same model, harness, tasks and seed. That
  cohort ran its two targets concurrently.

## Results

| | Playwright | Kitsune `ad04bac` | Aside | ego |
| --- | ---: | ---: | ---: | ---: |
| Success (raw reward 1) | 7/7 | 7/7 | 7/7 | 7/7 |
| MCP calls | 57 | 54 | **27** | 30 |
| Input tokens | 475,817 | 463,419 | **207,843** | 217,192 |
| Output tokens | 4,338 | 4,409 | 4,429 | 6,179 |
| Elapsed | 147 s | 119 s | 125 s | 159 s |
| Claude Code list-price estimate | $0.507 | $0.469 | **$0.377** | $0.420 |

Per task, calls / input tokens:

| Task | Playwright | Kitsune | Aside | ego |
| --- | ---: | ---: | ---: | ---: |
| `mw-click-test-2` | 5 / 60,725 | 5 / 51,559 | 3 / 22,673 | 3 / 21,530 |
| `mw-click-checkboxes` | 6 / 50,826 | 6 / 52,715 | 3 / 22,907 | 4 / 28,356 |
| `mw-enter-text` | 6 / 50,579 | 6 / 41,583 | 3 / 22,720 | 4 / 28,206 |
| `mw-choose-list` | 6 / 50,768 | 5 / 51,563 | 3 / 22,685 | 3 / 21,571 |
| `mw-login-user` | 6 / 61,135 | 7 / 54,955 | 3 / 23,024 | 3 / 21,296 |
| `mw-use-autocomplete` | 9 / 64,226 | 7 / 64,538 | 4 / 29,884 | 5 / 36,051 |
| `mw-book-flight` | 19 / 137,558 | 18 / 146,506 | 8 / 63,950 | 8 / 60,182 |

- **How the calls were spent:** a typical Aside run was `openTab` + `snapshot`, click START + `snapshot`, act +
  `snapshot`. ego runs did the same with `page.goto`/`page.click` + `page.snapshot()`. The ego agent re-declared
  `taskSpace(...)` in every call, as the vendor guide asks.
- **Input:** with fewer requests, the fixed prefix is re-sent fewer times. This holds even though ego's tool
  description (the vendor guide, about 22k characters) is longer than Aside's `repl` description (about 6k).
- **Elapsed:** ego was slowest overall, mostly in `mw-use-autocomplete` (37 s) and `mw-book-flight` (53 s). Each ego
  call starts a new Node.js process.
- **No reward tampering seen:** none of the 14 runs' scripts mention `core.`, `endEpisode`, `WOB_`, `EPISODE` or
  `evaluate(`. Every call was page navigation, snapshots and UI actions.

## Not comparable

- **Tool policy:** Playwright and Kitsune get the 23-tool UI allowlist, which excludes code execution because
  MiniWoB rewards are client-side state. Here code execution is the only tool, so only the prompt forbids touching
  the reward. Aside's `repl` also offers `fetch`, `fs` and `path`.
- **Browser and profile:** Chromium-based vendor apps with a persistent, signed-in profile, not a fresh private
  Firefox per run. Afterwards Aside listed no fixture tab, but ego kept every task space the agent created (e.g.
  `miniwob click-test-2`). `taskSpace(name)` resumes a space with the same name, so a rerun can start in the old
  space: close those spaces in ego lite before repeating.
- **Resources:** the RAM/CPU collector sees only the MCP process, not the browser app.
- **Timing:** the reference cohort ran its targets concurrently; these arms ran one at a time. Different days.
- **Repetition:** one attempt, no counterbalancing.

Only the MiniWoB tasks are supported. Personal, gallery and coexistence seed and grade tabs over Firefox WebDriver
BiDi, so these arms would need a CDP equivalent.

## Reproduce

```sh
# Needs Aside Browser signed in, ~/.local/bin/aside, and /Applications/ego lite.app after onboarding.
uv run --locked python -m kitsune_benchmark external --kind miniwob --targets aside,ego --execute
```

Artifacts: `artifacts/external/20261109T131246Z-50d8722cda` (`mw-click-test-2`) and
`artifacts/external/20261109T131328Z-a85dac75b5` (suite summary for the other six).
