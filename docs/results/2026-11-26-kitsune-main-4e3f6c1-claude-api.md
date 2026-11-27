# WebArena-Pro: Kitsune main (`4e3f6c1`) on Claude Code (API key)

**26 November 2026 · 26 attempts · Kitsune arm only · one repeat per cell.** Kitsune main at `4e3f6c1`, which merges the fixes for #666–#670 on top of v0.8.3, passed 12/26 (test 6/19, dev 6/7) on the `claude-api` harness. The [`0a8ada9` check](2026-11-25-kitsune-main-0a8ada9-claude-api.md) a day earlier passed 13/26. The only change in the pass set was `wap-077`, where the answer left out the flight number again, so a tool change did not cause it. Total input fell 7% and tool calls 8%; tool errors fell from 13 to 6, and none of the six traces to a tool defect. **No grade in this run was decided by a Kitsune bug.**

[Public per-attempt metrics (CSV)](2026-11-26-kitsune-main-4e3f6c1-claude-api.csv) · [Running guide](../running.md). Recompute with `python3 summary.py docs/results/2026-11-26-kitsune-main-4e3f6c1-claude-api.csv`. The CSV omits prompts, answers, tool payloads, credentials and transcripts.

## Comparison with earlier runs

Same harness (`claude-api`), model, task order and site pins. This is still one repeat per cell, not a controlled A/B.

| Run | Kitsune | Test /19 | Dev /7 | Mean score | Total calls | Tool errors | Median seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-11-26 `claude-api` | main (`4e3f6c1`) | 6 | 6 | .606 | 290 | 6 | 46.5 |
| 2026-11-25 `claude-api` | main (`0a8ada9`) | 7 | 6 | .644 | 314 | 13 | 45.5 |
| 2026-11-25 `claude-api` | main (`2ce7360`) | 6 | 6 | .606 | 311 | 12 | 46.0 |
| 2026-11-23 `claude-api` | v0.8.2 (`9a777eb`) | 6 | 6 | .606 | 369 | 15 | 46.6 |

| Run | Total input | Cached input | Output | Input on common passes | Calls on common passes | Seconds on common passes |
|---|---:|---:|---:|---:|---:|---:|
| `4e3f6c1` | 4,655,914 | 4,256,154 | 59,269 | 1,063,225 | 88 | 378 |
| `0a8ada9` | 5,030,673 | 4,612,232 | 60,767 | 1,103,955 | 90 | 369 |
| `2ce7360` | 5,167,058 | 4,751,947 | 63,591 | 1,070,183 | 88 | 383 |

Input includes cache reads and cache creation. Each run reports usage on 25/26 attempts; the `wap-247` timeout reports none. The common passes are the same 12 tasks in all four runs, and they are this run's whole pass set. On them, input, calls and time are within 4% of `0a8ada9`. Against v0.8.2, total input is down 35% (7,118,982 to 4,655,914) and calls are down 21%.

- **`wap-077` pass → fail:** the agent found the same flight (Delta, 3:30 PM, 6h 19m, $309) and left `DL6387` out of the answer. The task has gone fail, pass, fail, pass, fail over the last five runs on the agent's answer alone.
- **`wap-341` used 31% less input** (615k to 424k, 25 calls to 20) and **`wap-344` 26% less** (274k to 203k). Both lost calls to `fill_form` or to the calendar on `0a8ada9`.
- **`wap-233` and `wap-095` used more input** (108k to 138k and 139k to 177k). In `wap-233` the agent opened all 32 deals of two stages to check that they were open, in one 100-call script.
- **`wap-247` timed out at 600 seconds for the fifth run.** It stayed on one tab and did not use `browser.parallel`. Three 120-second scripts read 57 of 135 cities at about 3.2 s per page; a fourth lost its batch at the deadline, because it printed only at the end and one city can take more than the 8 seconds it kept in reserve. The site is the bottleneck (#634).
- **Tool errors:**
  - `script_error` 2
  - `not_found` 2
  - `script_timeout` 1
  - `needs_user` 1

  Both `script_error`s were a variable from an earlier script (`wap-069`, `wap-140`). Both `not_found`s were "Select flight" on the return leg, where the button says "Book" (`wap-069`, `wap-079`). The `needs_user` was the agent asking for card details in `wap-140`. There was no `No field was filled` (2 before, #666), no `stale_ref` and no navigate timeout.
- **Fixed sleeps fell:** 78 of 266 scripts sleep, 127 s in all, against 91 of 290 and 190 s on `0a8ada9`. 60 of the 90 sleeps follow a click (E1).
- **Cost:** Claude Code estimated $4.03 for the run. The Anthropic Console is the billing source.

## Effect of the #666–#670 fixes

| Issue | Seen in this run |
|---|---|
| #666 `fill_form` with refs and shown labels | `wap-140` and `wap-344` filled the eight booking fields with one `fill_form` keyed by refs; both calls succeeded (both failed with `No field was filled` before) |
| #667 no-content hint names `tab.wait_for(content=True)` | After the direct hint 1 of 5 next calls used it (`wap-344`; 0 of 5 before) and 4 slept (E2). After a script warning 3 of 3 next calls waited, 2 with `content=True` |
| #668 `NameError` hint | Both `NameError`s got "Variables do not carry over between scripts", and the next call defined the value again. One also got "Earlier operations may have taken effect" after two reads (B3) |
| #669 `browser.parallel` example and results | Not exercised: no script used `browser.parallel` or `help()` |
| #670 `button[action=…]` from the snapshot | `wap-260` and `wap-261` clicked `button[action="/bookmark/t…"]` five times with no `not_found` (1 lost call before) |

## Why the 14 tasks failed

None of these grades came from a tool defect. Thirteen causes are the same as on `0a8ada9`.

| Task | Score | Cause |
|---|---:|---|
| `wap-065` | 0 | The answer has none of the flight numbers the rubric requires (`UA1976`, `WN797`) |
| `wap-069` | .5 | The flights passed, paid with the password manager's card; the agent booked the cheapest Toronto stay, not the expected listing |
| `wap-077` | 0 | The answer left out the flight number `DL6387` |
| `wap-079` | 0 | Stopped at the fare options without booking |
| `wap-095` | 0 | Applied to the contract role instead of Backend Engineer (Go) |
| `wap-096` | 0 | Kept "Intern" in the new titles; the rubric expects "Product Design" and "Data Science" |
| `wap-139` | 0 | Registered a course instead of answering that the student was already registered |
| `wap-140` | .5 | Typed card details of its own instead of the password manager's card; payment failed and the agent asked the user |
| `wap-247` | 0 | 600 s timeout (see above) |
| `wap-258` | .75 | Did not follow City Desk |
| `wap-260`, `wap-261` | .67 | Bookmark count off by 2, as in every earlier run and arm |
| `wap-341` | 0 | Right city, wrong total (`$197` against `$206.54`) |
| `wap-344` | .67 | Typed card details of its own; payment failed |

## Bug and enhancement leads from the transcripts

Found by reading the transcripts after the run. Counts are from this run only. B1–B3, E1, E3 and E4 were reproduced on local fixture pages with the same runtime (main `4e3f6c1`, isolated headless Firefox); B3 was also checked against the source. E2, E5 and E6 rest on the transcripts. None of them lost a grade, and B1, B2 and E4 lost no call.

### Bugs

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| B1 | [#678](https://github.com/junyeong-nero/kitsune/issues/678) | A `<select>` inside its own `<label>` is named by the label text and every option: the snapshot prints `combobox "City Any city Albany"` and `combobox "Sort Recommended Top rated Pri"` (cut), and `tab.forms()` returns `label: 'City\n        \n          Any city\n …'` (cut at 100 characters). `role=combobox[name="City"]` is `not_found`. A `<label for>` select is named correctly (`combobox "Amenity"`). | 9 snapshot lines (`wap-069`, `wap-138`) and 24 `forms()` labels in 8 tasks (TravelMap search form, Minerva-lite term selector). The agents then read the real options with `select[name=…] option` queries (`wap-069`, `wap-142`, `wap-247`, `wap-341`) |
| B2 | [#679](https://github.com/junyeong-nero/kitsune/issues/679) | A name taken from block-level children is joined with no space: `button "ChicagoUSAORD$128"`, `button "Visa PlatinumVisa • ••••1111"`, `option "Seoul (ICN)Incheon International Airport, Republic of Korea"`, `button "Basic Economy$474Most restrictions applySeat selection· Fee…"`. `tab.text()` puts each part on its own line. Only the glued form resolves: `role=button[name="Chicago USA ORD $128"]` is `not_found`. | At least 115 snapshot lines in 7 tasks (flight-search and password manager: `wap-065`, `wap-069`, `wap-077`, `wap-079`, `wap-140`, `wap-341`, `wap-344`) |
| B3 | [#680](https://github.com/junyeong-nero/kitsune/issues/680) | A `NameError` after read-only operations gets "Earlier operations may have taken effect. Inspect the page; do not replay the whole script." The #668 hint checks whether any operation ran, not whether one wrote; the deadline hint already uses the write check ("Nothing was written"). | `wap-140`: the script had run `wait_for` and `tab.text()` only |

### Enhancements

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| E1 | [#681](https://github.com/junyeong-nero/kitsune/issues/681) | A click that leaves the page loading gives no signal. In the reproduction a click whose result arrives 1.5 s later returns after 0.5 s with the delta `text "Loading..."`, no `rendering` field and no warning; the next `tab.text()` reads `Loading...`; `wait=True` changes nothing. The rendering warning (#631, #651) covers `navigate` and `new_tab` only, so agents sleep after clicks. | 60 of 90 sleeps follow a click (94 of 127 s) and 19 follow `fill` or `type`; 12 of 266 scripts read the action's own `r['snapshot']` |
| E2 | [#682](https://github.com/junyeong-nero/kitsune/issues/682) | The rendering state of a `browser_tabs new` does not reach the next script. The direct hint was followed by `time.sleep(1); print(tab.snapshot())` 4 of 5 times, and that script's first read raised no warning. The script warning is followed far more often. | Direct hint: 1 of 5 waited (`wap-344`); 4 slept (`wap-065`, `wap-069`, `wap-077`, `wap-079`). Script warning: 7 of 8 next calls used `wait_for` |
| E3 | [#683](https://github.com/junyeong-nero/kitsune/issues/683) | The script warning reports the state at the time `navigate` or `new_tab` returned, at the next read, without checking again. After `new_tab(…); time.sleep(2); tab.snapshot()` it says "The page still shows 'Loading...'" above a snapshot of the rendered page. | 2 of 8 script warnings (`wap-069`, `wap-140`) |
| E4 | [#684](https://github.com/junyeong-nero/kitsune/issues/684) | An icon button whose only text is a count is listed as `button "6"` or `button "47"`. Its `data-testid` or form action is printed only when the name is empty (#632), as on the bookmark button beside it, so nothing says which is repost and which is like. | 28 buttons in x-lite snapshots (`wap-258`, `wap-260`, `wap-261`); no task in this run needed them |
| E5 | [#685](https://github.com/junyeong-nero/kitsune/issues/685) | Hints of errors raised in a script name direct tools: `not_found` says "take a new browser_snapshot, or browser_wait_for the element". The code-first surface does not publish either tool; the script forms are `tab.snapshot()` and `tab.wait_for()` (same class as #667). | 2 `not_found` errors (`wap-069`, `wap-079`); both agents recovered with one read script |
| E6 | [#686](https://github.com/junyeong-nero/kitsune/issues/686) | `tab.snapshot()` returns a string and an action returns a dict with `['snapshot']`; the description says neither. Scripts hedge with `isinstance`, and two of them take the snapshot twice to do it. One script split `str(s)` on a literal `\n` and printed the whole page as one line. | 5 scripts in 4 tasks (`wap-096`, `wap-140`, `wap-258`, `wap-260`); 1 lost call (`wap-260`) |
| – | [#634](https://github.com/junyeong-nero/kitsune/issues/634) | With the #669 example in the description, the agent still chose one tab for 135 cities. A read loop that keeps its rows in a local list loses them at the deadline; only `result` and printed output survive. | `wap-247` (timeout in five runs) |

## Protocol and exclusions

- Command: `python3 benchmark.py --execute --harness claude-api --arm kitsune --allow-api-billing`, the 26 cells in matrix order. Every `api_key_source` was `ANTHROPIC_API_KEY`.
- Runner `480b818`. Kitsune main `4e3f6c1` ran from a separate runtime checkout (`uv sync --locked`) with isolated headless Firefox. Model: `claude-opus-5-5`, Claude Code 2.1.332.
- Sites and Core: WebArena-Pro `42f4a076` in a Codespace, restarted for this run, with container egress blocked again after the restart. Ports were forwarded over SSH (`-L`). Each attempt recreated its sites and signed in before measurement. The run started at 23:54 KST on 26 November and ended at 00:41 on 27 November.
- Grading is unchanged: `backend_state` and `answer_match`, with no working LLM judge. A rubric that escalates to `llm_judge` fails with `configuration_error`, as intended.
- No attempt was excluded. The four-way runner does not save the bridge audit, so the timings for #634 come from transcript timestamps. Raw evidence remains private.
