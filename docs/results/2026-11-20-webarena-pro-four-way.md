# WebArena-Pro four-way, 26 tasks: Aside, EgoLite, Playwright MCP and Kitsune under Claude Code

[Results index](README.md) · [Suite and running guide](../../four-way/README.md#webarena-pro-subset---suite-webarena-pro)

> **Draft.** The Codex (`gpt-6.1-sol`) run is still in progress. Its results are added before this report is final;
> everything below is Claude Code only.

![Four-way benchmark, 26 WebArena-Pro tasks, Claude Code, 104 attempts. Passed: Kitsune 13/26; Playwright MCP 13/26; Aside 12/26; EgoLite 12/26. Mean input tokens per attempt: Kitsune 283k; EgoLite 360k; Aside 463k; Playwright MCP 660k. Mean tool calls: EgoLite 12.8; Kitsune 14.0; Aside 16.1; Playwright MCP 29.8.](../assets/2026-11-20-webarena-pro-four-way.svg)

## Summary

- **Success was tied, and the task decided it.** Kitsune and Playwright MCP passed 13 of 26 tasks, Aside and EgoLite
  12. All four arms passed the same 12 tasks and missed the same 13; one of those, `wap-247`, timed out for every arm.
- **The one split came from the answer's wording.** The answer check of `wap-077` needs the flight number
  (`DL6387`). The Kitsune and Playwright MCP attempts reported it; the Aside and EgoLite attempts found the same
  flight and named only the airline and times.
- **Kitsune used the least input.** Mean input per attempt was Kitsune 283k, EgoLite 360k, Aside 463k and Playwright
  MCP 660k tokens, cache included. The list-price cost of all attempts was $6.7, $9.3, $10.3 and $12.4.
- **The order holds on the 12 tasks every arm passed.** Total input there was Kitsune 1.08M, EgoLite 2.14M, Aside
  2.76M and Playwright MCP 2.78M tokens: Kitsune used 39% of Playwright MCP's input, with 91 tool calls to its 201.
- **EgoLite made the fewest tool calls**, 12.8 per attempt; Kitsune made 14.0, Aside 16.1 and Playwright MCP 29.8.
  For Aside and EgoLite one call is a script that can batch actions.
- **Most shared misses ended at a judge this suite does not run.** In 11 of the 13, the failing rubric node fell
  through to WebArena-Pro's LLM judge, which is not configured here, so it failed. Whether the judge would have
  passed any of them is unknown ([details](#why-tasks-failed)).

These are single attempts per task. Read a one-task difference as an observation, not a ranking.

## Setup

| | |
| --- | --- |
| Date | 2026-11-20 |
| Agent | Claude Code 2.1.327, `claude-opus-5-5` (subscription) |
| Aside | CLI 1.26.1107.24, existing profile; signed in through the site's login form |
| EgoLite | `ego-browser` 0.6.3.14, existing profile, new TaskSpace per attempt; signed in with CDP `Network.setCookie` |
| Playwright MCP | 0.0.83, isolated headless Firefox; signed in with `--storage-state` |
| Kitsune | main `4e6d6fb` (build `0.8.0+a5ac123`), private bridge and headless Firefox started by `scripts/kitsune_runtime.py`; signed in with `cookies.set`\* |
| Tasks | 26 [WebArena-Pro](https://arxiv.org/abs/2611.17955) tasks (19 test, 7 dev) on 8 apps, from `McGill-NLP/webarena-pro@42f4a076` ([selection](../../four-way/README.md#webarena-pro-subset---suite-webarena-pro)); 1 repeat, 600 s wall budget |
| Sites | every site of a task is recreated from its seed image before each attempt; they ran in a GitHub codespace behind a port-forward tunnel |
| Plan | 26 tasks × 4 arms = 104 attempts; the starting arm rotates per task |
| Grading | WebArena-Pro's evaluation DAG with its `backend_state` and `answer_match` checks only; pass = full score |

\* The run metadata's `versions.kitsune` is `git describe` of the operator's own Kitsune checkout, not of the runtime.
Every runtime's `env.json` records build `0.8.0+a5ac123ed8baab30`, which is `4e6d6fb`.

Grading has no LLM judge and no UI evidence, so it is stricter than the paper's: **these scores are not comparable to
its 62.3%**.

## Results

| Agent | Arm | Pass | Fail | Error | Mean score | Median s | Tool calls | Tool errors | Input tok | Cached | Output tok | Cost $ (sum) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude | Aside | 12 | 13 | 1 | 0.61 | 67.7 | 16.1 | 2.7 | 462,781 | 432,073 | 3,938 | 10.27 |
| Claude | EgoLite | 12 | 13 | 1 | 0.61 | 63.9 | **12.8** | 1.3 | 360,049 | 331,000 | 3,673 | 9.30 |
| Claude | Playwright | 13 | 12 | 1 | 0.64 | 59.9 | 29.8 | 1.3 | 659,560 | 621,130 | 3,304 | 12.44 |
| Claude | **Kitsune** | 13 | 12 | 1 | 0.63 | 59.9 | 14.0 | **1.0** | **283,019** | 263,342 | **2,952** | **6.73** |

How to read the table:

- Tool calls, tool errors and the token columns are means per attempt; Median s is the median agent time.
- Mean score is WebArena-Pro's partial credit (the share of rubric nodes passed). Pass needs a full score.
- Input includes cached input. Cost is the list-price estimate Claude Code reports, summed over the attempts.
- The attempt that timed out (`wap-247`) has no token count or cost in any arm. It is left out of the token means and
  the cost sum, and stays in the pass denominator and the tool-call mean.
- **Tool calls are not the same unit for every arm.** For Aside and EgoLite, one call is one `./browser` JavaScript
  script, which can batch several page actions. For Playwright and Kitsune, one call is one MCP tool call.

### Tasks every arm passed

12 tasks: `wap-138`, `wap-142`, `wap-143`, `wap-144`, `wap-199`, `wap-229`, `wap-230`, `wap-231`, `wap-233`,
`wap-238`, `wap-239` and `wap-244`. Totals over those tasks:

| Arm | Input | vs Playwright | Tool calls | vs Playwright | Median s |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Kitsune** | **1.08M** | 39% | **91** | 45% | **36.4** |
| EgoLite | 2.14M | 77% | 94 | 47% | 45.6 |
| Aside | 2.76M | 99% | 140 | 70% | 52.7 |
| Playwright | 2.78M | 100% | 201 | 100% | 50.3 |

### Per task

Cells: outcome (with the score of a partial miss) / tool calls / input kTok / seconds.

**Claude Code, `claude-opus-5-5`**

| Task | Sites | Aside | EgoLite | Playwright | Kitsune |
| --- | --- | --- | --- | --- | --- |
| `wap-065` | flight-search | **FAIL** / 13 / 242k / 55s | **FAIL** / 7 / 141k / 35s | **FAIL** / 13 / 116k / 25s | **FAIL** / 5 / 56k / 22s |
| `wap-069` | flight-search, password-manager, travelmap | **FAIL** 0.50 / 50 / 2464k / 253s | **FAIL** 0.50 / 47 / 1893k / 351s | **FAIL** 0.50 / 112 / 2936k / 220s | **FAIL** 0.50 / 48 / 1806k / 406s |
| `wap-077` | flight-search | **FAIL** / 11 / 200k / 40s | **FAIL** / 7 / 140k / 36s | PASS / 22 / 337k / 46s | PASS / 15 / 219k / 62s |
| `wap-095` | jobportal | **FAIL** / 11 / 191k / 51s | **FAIL** / 9 / 208k / 49s | **FAIL** / 24 / 557k / 59s | **FAIL** / 12 / 185k / 52s |
| `wap-096` | jobportal | **FAIL** / 17 / 373k / 92s | **FAIL** / 12 / 309k / 61s | **FAIL** / 32 / 901k / 81s | **FAIL** / 27 / 613k / 152s |
| `wap-138` | minerva-lite | PASS / 10 / 129k / 39s | PASS / 8 / 205k / 45s | PASS / 17 / 315k / 36s | PASS / 7 / 75k / 33s |
| `wap-139` | minerva-lite | **FAIL** / 16 / 355k / 69s | **FAIL** / 14 / 341k / 81s | **FAIL** / 33 / 587k / 58s | **FAIL** / 15 / 243k / 60s |
| `wap-140` | minerva-lite, flight-search | **FAIL** 0.50 / 27 / 653k / 283s | **FAIL** 0.50 / 26 / 915k / 236s | **FAIL** 0.50 / 56 / 1250k / 167s | **FAIL** 0.50 / 24 / 450k / 108s |
| `wap-229` | pipedrive | PASS / 2 / 42k / 10s | PASS / 4 / 86k / 18s | PASS / 5 / 68k / 31s | PASS / 6 / 61k / 16s |
| `wap-230` | pipedrive | PASS / 11 / 217k / 51s | PASS / 9 / 183k / 46s | PASS / 18 / 182k / 42s | PASS / 11 / 130k / 79s |
| `wap-231` | pipedrive | PASS / 8 / 150k / 26s | PASS / 7 / 154k / 34s | PASS / 10 / 113k / 23s | PASS / 6 / 96k / 21s |
| `wap-238` | thunderbird | PASS / 23 / 535k / 105s | PASS / 10 / 214k / 64s | PASS / 36 / 515k / 70s | PASS / 7 / 74k / 36s |
| `wap-239` | thunderbird | PASS / 34 / 891k / 210s | PASS / 10 / 226k / 72s | PASS / 11 / 156k / 43s | PASS / 10 / 115k / 66s |
| `wap-247` | travelmap | **ERR** / 18 / – / 600s | **ERR** / 15 / – / 600s | **ERR** / 19 / – / 600s | **ERR** / 21 / – / 600s |
| `wap-258` | x-lite | **FAIL** 0.75 / 17 / 711k / 125s | **FAIL** 0.75 / 15 / 503k / 85s | **FAIL** 0.75 / 27 / 957k / 90s | **FAIL** 0.75 / 12 / 240k / 95s |
| `wap-260` | x-lite | **FAIL** 0.67 / 14 / 497k / 97s | **FAIL** 0.67 / 12 / 339k / 64s | **FAIL** 0.67 / 23 / 777k / 57s | **FAIL** 0.67 / 10 / 156k / 56s |
| `wap-261` | x-lite | **FAIL** 0.67 / 15 / 595k / 100s | **FAIL** 0.67 / 17 / 520k / 107s | **FAIL** 0.67 / 40 / 1429k / 126s | **FAIL** 0.33 / 9 / 163k / 78s |
| `wap-341` | travelmap, flight-search | **FAIL** / 37 / 1772k / 364s | **FAIL** / 29 / 880k / 366s | **FAIL** / 95 / 2326k / 208s | **FAIL** / 31 / 960k / 286s |
| `wap-344` | flight-search | **FAIL** 0.67 / 18 / 525k / 114s | **FAIL** 0.67 / 15 / 361k / 108s | **FAIL** 0.67 / 46 / 1012k / 138s | **FAIL** 0.67 / 23 / 517k / 131s |
| `wap-079` (dev) | flight-search | **FAIL** / 14 / 237k / 73s | **FAIL** / 14 / 309k / 89s | **FAIL** / 33 / 525k / 88s | **FAIL** / 21 / 386k / 97s |
| `wap-142` (dev) | minerva-lite | PASS / 10 / 131k / 54s | PASS / 11 / 254k / 66s | PASS / 27 / 344k / 72s | PASS / 12 / 142k / 60s |
| `wap-143` (dev) | minerva-lite | PASS / 8 / 102k / 49s | PASS / 7 / 167k / 46s | PASS / 18 / 275k / 64s | PASS / 6 / 69k / 37s |
| `wap-144` (dev) | minerva-lite | PASS / 10 / 156k / 59s | PASS / 9 / 261k / 59s | PASS / 21 / 282k / 61s | PASS / 7 / 90k / 49s |
| `wap-199` (dev) | password-manager | PASS / 3 / 37k / 20s | PASS / 2 / 43k / 20s | PASS / 4 / 43k / 21s | PASS / 3 / 28k / 23s |
| `wap-233` (dev) | pipedrive | PASS / 10 / 204k / 58s | PASS / 10 / 204k / 79s | PASS / 23 / 316k / 58s | PASS / 11 / 142k / 60s |
| `wap-244` (dev) | thunderbird | PASS / 11 / 162k / 67s | PASS / 7 / 146k / 44s | PASS / 11 / 169k / 57s | PASS / 5 / 59k / 31s |

### Tool usage

| Agent | Arm | Calls by tool (all 26 tasks) |
| --- | --- | --- |
| Claude | Aside | `./browser` 418 |
| Claude | EgoLite | `./browser` 333 |
| Claude | Playwright | snapshot 156, click 147, find 144, navigate 110, type 62, take_screenshot 49, tabs 35, wait_for 22, fill_form 17, run_code_unsafe 10, select_option 9, press_key 6, navigate_back 4, hover 3, handle_dialog 2 |
| Claude | Kitsune | run_python 328, tabs 25, take_screenshot 8, tools_call 2, ask_user 1 |

## Why tasks failed

The rubric trail of each row names the check that failed. Every arm failed the same way on each of these tasks,
except where noted.

| Task | What the trail shows |
| --- | --- |
| `wap-065` | The answer check looks for flights `UA1976` and `WN797`. Every arm answered Frontier F9, which lands at 7:11 AM the next day. |
| `wap-069` | Flights booked (rubric 1 passed). No confirmed lodging booking for the guest (rubric 2). |
| `wap-095` | The backend has no application to `Backend Engineer (Go)` from the user. |
| `wap-096` | None of the six checks passed: the two intern postings are still open, and the expected part-time postings are missing. |
| `wap-139` | The answer check expects a report that the student is already registered. Every arm answered `done`. |
| `wap-140` | The answer check passed. The backend has no booking: every arm stopped at the payment details. |
| `wap-247` | Every arm hit the 600 s budget before it answered. |
| `wap-258` | Three of four checks passed. The follow the backend expects is missing. |
| `wap-260` | Both message checks passed. The bookmark count was not the expected one. |
| `wap-261` | The bookmark count was not the expected one. The Kitsune attempt also sent no message: the agent stopped to ask which posts to save (score 0.33, the others 0.67). |
| `wap-341` | The answer must be exactly `Toronto; $206.54`. Every arm answered Toronto at about $197. |
| `wap-344` | Two of three checks passed. The backend has no valid booking. |
| `wap-079` | The backend has no booking from YUL: every arm named a ticket in its answer. |

In `wap-258` and `wap-344` a backend check decided the failing node. In the other 11 tasks it fell through to the LLM
judge, which this suite does not configure, so the node failed. Whether the paper's judge would have accepted any of
those answers is unknown. The same happened to the Aside and EgoLite answers of `wap-077`, which lacked the flight
number.

## Problems found

Counts are tool errors over the 26 Claude attempts of each arm.

- **Kitsune (27):** 7 navigations to TravelMap pages reported `timedOut` with the tab still `loading`, which stopped
  the script that made them ([kitsune#561](https://github.com/junyeong-nero/kitsune/issues/561)). Three calls failed
  on a URL with the origin doubled (`Illegal URL: http://localhost:4701http://localhost:4701/…`). In `wap-261` the
  agent asked the user to choose posts instead of acting.
- **Aside (69):** 23 `RefStaleError`s, since refs do not survive between its one-shot REPL calls.
- **EgoLite (33):** 11 clicks on a disabled element timed out, and 5 refs were stale.
- **Playwright MCP (34):** 9 refs were missing from the current snapshot, and 6 calls failed with `Malformed value`.
  It made the most calls: 156 snapshots and 144 finds over 26 tasks.

## Limits

- One attempt per task and agent. A one-task difference is within noise.
- No LLM judge or UI evidence: a rubric the backend check cannot prove fails. Scores are not comparable to the
  paper's.
- Browser environments differ. Aside and EgoLite drove the operator's profiles; Playwright MCP and Kitsune ran an
  isolated headless Firefox. This is a product comparison, not a browser-engine comparison.
- The sites ran in a GitHub codespace behind a port-forward tunnel, which adds 0.3–0.9 s to a heavy page load.
- Cost is Claude Code's list-price estimate, not billed cost.
- 26 tasks on 8 of WebArena-Pro's 20 apps, chosen so that grading needs no judge. They are not a sample of the
  benchmark.

## Harness issues during the run

These were fixed during the run and the affected attempts run again. For each task and arm the first valid
measurement counts; a later one never replaces it.

- **EgoLite started signed out.** Chromium rejected sign-in cookies with `SameSite=None` and no `Secure`, which Core
  records for cookies without a `SameSite` attribute. Eight EgoLite attempts on minerva-lite, thunderbird and x-lite
  are listed as invalid (`invalid.txt`) and were rerun after the fix.
- **Two setup failures** were rerun: a `killpg` `EPERM` on macOS and a failed setup command.
- A transcript parser crash on a system event and a Kitsune worktree that was pruned mid-run also affected attempts,
  which were run again. The runtime then used a private export of the same commit.

The fixes are not in this repository yet: the run used a working tree on top of `1ef91e1`.

## Reproduce

From `four-way/`, with the sites and a Kitsune runtime started as in the
[suite guide](../../four-way/README.md#setup):

```sh
python3 scripts/run.py --suite webarena-pro --execute --browser-mode existing-profile \
  --arm-mode playwright=isolated --arm-mode kitsune=isolated --harness claude --model claude-opus-5-5 \
  --out runs/wap/claude.jsonl
python3 scripts/analyze.py runs/wap/claude.jsonl --out runs/wap/analysis
python3 scripts/figure.py runs/wap/analysis/summary.json ../docs/assets/2026-11-20-webarena-pro-four-way.svg \
  --suite webarena-pro
```

This run started one Kitsune runtime per task and ran the tasks one at a time, because the host has 8 GB of memory.

Data: the per-attempt rows, raw transcripts and run metadata are not published yet.
