# WebArena-Pro: Kitsune main (`2ce7360`) on Claude Code (API key)

**25 November 2026 · 26 attempts · Kitsune arm only · one repeat per cell.** Kitsune main at `2ce7360`, which merges the fixes for #627–#635, passed 12/26 (test 6/19, dev 6/7) on the `claude-api` harness. The [`c7149a8` check](2026-11-24-kitsune-main-c7149a8-claude-api.md) a day earlier passed 13/26. The only change in the pass set was `wap-077`, where the answer left out the flight number this time, so a tool change did not cause it. Total input fell 11%, tool calls 7% and median time 14%. Tool errors rose from 7 to 12; two of the 12 trace to a tool lead (E3, E4), and the rest were the agent's own selectors, its Python, or the `wap-247` time budget. **No grade in this run was decided by a Kitsune bug.** The README figure was not updated.

[Public per-attempt metrics (CSV)](2026-11-25-kitsune-main-2ce7360-claude-api.csv) · [Running guide](../running.md). Recompute with `python3 summary.py docs/results/2026-11-25-kitsune-main-2ce7360-claude-api.csv`. The CSV omits prompts, answers, tool payloads, credentials and transcripts.

## Comparison with `c7149a8`

Same harness (`claude-api`), model, task order and site pins. This is still one repeat per cell, not a controlled A/B.

| Run | Kitsune | Test /19 | Dev /7 | Mean score | Total calls | Tool errors | Median seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-11-25 `claude-api` | main (`2ce7360`) | 6 | 6 | .606 | 311 | 12 | 46.0 |
| 2026-11-24 `claude-api` | main (`c7149a8`) | 7 | 6 | .644 | 334 | 7 | 53.2 |
| 2026-11-23 `claude-api` | v0.8.2 (`9a777eb`) | 6 | 6 | .606 | 369 | 15 | 46.6 |

| Run | Total input | Cached input | Output | Input on common passes | Calls on common passes | Seconds on common passes |
|---|---:|---:|---:|---:|---:|---:|
| 2026-11-25 | 5,167,058 | 4,751,947 | 63,591 | 1,070,183 | 88 | 383 |
| 2026-11-24 | 5,811,881 | 5,379,026 | 66,457 | 1,244,864 | 103 | 476 |

Input includes cache reads and cache creation. Both runs report usage on 25/26 attempts; the `wap-247` timeout reports none. The common passes are the same 12 tasks in both runs: on them, input fell 14%, calls 15% and agent time 20%.

- **`wap-077` pass → fail:** the agent found the same flight (Delta, 3:30 PM, 6h 19m, $309) but did not open its details, so the answer has no `DL6387`. The task has gone fail, pass, fail over the last three runs on the agent's answer alone.
- **`wap-261` halved:** 24 calls and 601k input became 15 calls and 300k. The snapshot now shows `[action="/bookmark/t833"]` on the icon-only button (#632). The agent still lost two calls to it (E3 below).
- **`wap-341` input fell from 742k to 387k**, and `wap-140` from 556k to 391k. Scripts read whole result pages in one `tab.text()` (#630): `wap-069` read 200 of 200 fares on each search, against 176 before.
- **`wap-239` and `wap-233` got shorter:** 146k to 76k and 153k to 92k input, 12 to 7 and 11 to 7 calls.
- **Four tasks used more input:** `wap-079` (107k to 207k), `wap-077` (86k to 168k), `wap-258` (225k to 372k) and `wap-096` (285k to 373k). In each the agent took a longer route; `wap-258` also hit two selector errors of its own.
- **`wap-247` timed out at 600 seconds again**, but it read 106 of 135 cities, against 36 before. It checked `browser.seconds_left` and ended each script itself (#618). At about 3.2 s per page on one tab, 135 pages do not fit (#634).
- **Warnings changed as intended:** "Page text was cut" went from 15 to 0 and "Query results were truncated" from 13 to 0.
- **Tool errors:**
  - `not_found` 5
  - `ambiguous_target` 3
  - `script_error` 2
  - `script_timeout` 1
  - `needs_user` 1

  Three `not_found` errors were `text=Select flight` on the return leg, where the button says "Book" (`wap-069`, `wap-079`, `wap-140`). One was a selector for a page the script had already left (`wap-258`). Both `script_error`s were the agent's Python. Two `ambiguous_target`s were loose selectors (`tbody tr td`, `input[name=q]`), refused with nothing dispatched. The remaining two errors are E3 and E4 below.
- **Cost:** Claude Code estimated $4.30 for the run. The Anthropic Console is the billing source.

## Effect of the #627–#635 fixes

| Issue | Seen in this run |
|---|---|
| #627 fresh page text | No stale `Loading...` after a successful `wait_for` (`wap-229`, `wap-231`; stale in 3 tasks on 2026-11-24) |
| #628 role hint | `wap-077`: `query('main article')` warned "use [role=article]", and the next call did |
| #629 textarea line breaks | `wap-244`: `tab.markdown('#composebody')` returned the quoted reply with its line breaks, and the agent rebuilt the body from it |
| #630 full page text in scripts | 0 "Page text was cut" warnings (15 before); 200 of 200 fares read in `wap-069` |
| #631 rendering hint | 24 reports in 11 tasks. The `Loading...` form was followed by `wait_for` 2 of 2 times; the no-content form 0 of 7 times (E2) |
| #632 unnamed controls | `wap-261`: 24 calls to 15; the agent found the bookmark button from the snapshot line, with no HTML query |
| #633 query warnings | 0 truncation warnings (13 before); the unknown-field warning fired 3 times, and `wap-096` then used `tab.html` |
| #634 / #647 script threads | No script used threads. `wap-247` stayed on one tab |
| #635 comma selector list | Not exercised: no `unsupported_selector` error |

## Why the 14 tasks failed

None of these grades came from a tool defect.

| Task | Score | Cause |
|---|---:|---|
| `wap-065` | 0 | The answer has none of the flight numbers the rubric requires (`UA1976`, `WN797`) |
| `wap-069` | .5 | The flights passed, paid with the password manager's card; the agent booked the cheapest Toronto stay, not the expected listing |
| `wap-077` | 0 | The answer left out the flight number `DL6387` |
| `wap-079` | 0 | Stopped at checkout without paying |
| `wap-095` | 0 | Applied to the contract role instead of Backend Engineer (Go) |
| `wap-096` | 0 | Titled the new posts "Product Designer (Part-Time)" and "Data Scientist (Part-Time)"; the rubric expects "Product Design" and "Data Science" |
| `wap-139` | 0 | Registered a course instead of answering that the student was already registered |
| `wap-140` | .5 | Typed card details of its own instead of the password manager's card; payment failed and the agent asked the user |
| `wap-247` | 0 | 600 s timeout (see above) |
| `wap-258` | .75 | Did not follow City Desk |
| `wap-260`, `wap-261` | .67 | Bookmark count off by 2, as in every earlier run and arm |
| `wap-341` | 0 | Right city, wrong total: the agent entered 2027 dates on the listing, got no quote, and priced the stay as two nights plus fees (`$197` against `$206.54`) |
| `wap-344` | .67 | Typed card details of its own; payment failed |

## Bug and enhancement leads from the transcripts

Found by reading all 26 transcripts after the run. Counts are from this run only. Every item was then reproduced on local fixture pages with the same runtime (main `2ce7360`, isolated headless Firefox). B3 came out of those reproductions and is not in the transcripts.

### Bugs

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| B1 | [#650](https://github.com/junyeong-nero/kitsune/issues/650) | `tab.query(fields=['value'])` cuts a value at 400 characters and `tab.forms()` at 100, with no marker in the value. `query` warns, but only after the script has ended; `forms()` does not warn. A script that reads a reply body and fills it back writes the cut text: in the reproduction, 405 characters instead of 1,604. | `wap-244` (rebuilt the body, 2 more calls), `wap-238` (dropped the quoted message from three replies), `wap-096` (1 more call) |
| B2 | [#648](https://github.com/junyeong-nero/kitsune/issues/648) | A `<form>` with a control named `value` is listed as `form "" [value="[object HTMLInputElement]"]`: `form.value` returns the control. | `wap-233` in all three runs; no calls lost |
| B3 | [#649](https://github.com/junyeong-nero/kitsune/issues/649) | The snapshot names `<button value="x">Named</button>` as `button "x"`. The resolver uses the text: `role=button[name="Named"]` matches and `role=button[name="x"]` is `not_found`. | Reproduction only |

### Enhancements

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| E1 | [#651](https://github.com/junyeong-nero/kitsune/issues/651) | In a script, `navigate` raises the rendering warning as it returns, even when the next line is the `wait_for` it recommends. | 10 of 20 script warnings (`wap-069`, `wap-140`, `wap-229`, `wap-231`, `wap-341`) |
| E2 | [#652](https://github.com/junyeong-nero/kitsune/issues/652) | The no-content hint says "wait for text you expect". On a first visit the agent knows no text, so it sleeps. A wait that needs no text (`wait_for(content=True)`) is missing. | 7 cases on the flight-search start page: 6 followed by `time.sleep`, 0 by `wait_for`. 90 of 287 scripts sleep, 148 s in all |
| E3 | [#653](https://github.com/junyeong-nero/kitsune/issues/653) | The #632 identity is printed as `[action="/bookmark/t833"]` or `[testid="…"]` on the button's line and reads like the button's attribute. `button[action=…]` matches nothing and fails with a bare `not_found`. | `wap-261` (2 calls), `wap-260` (hedged with both forms) |
| E4 | [#654](https://github.com/junyeong-nero/kitsune/issues/654) | `text=Jane Smith` matches the title and the subtitle inside one list button and is refused as `ambiguous_target`, although both matches are the same control (follow-up to #573). | `wap-069` (1 call) |
| E5 | [#655](https://github.com/junyeong-nero/kitsune/issues/655) | Fields whose `<label>` is not associated are `textbox ""` or are named by a placeholder such as `"4111111111111111"`; `tab.forms()` returns `label: ''`. The agent maps labels to fields by order. | Flight-search booking form: `wap-069` and `wap-344` (1 call each), `wap-140` |
| E6 | [#656](https://github.com/junyeong-nero/kitsune/issues/656) | Every button line ends with `[value=""]`. | 444 of 1,636 snapshot lines, 5.9% of snapshot characters |
| – | [#634](https://github.com/junyeong-nero/kitsune/issues/634) (comment) | `wap-247` ran `help(browser.parallel)`, got one line with no example, and stayed on one tab at about 3.2 s per page. | `wap-247` (timeout in three runs) |

## Protocol and exclusions

- Command: `python3 benchmark.py --execute --harness claude-api --arm kitsune --allow-api-billing`, the 26 cells in matrix order. Every `api_key_source` was `ANTHROPIC_API_KEY`.
- Runner `14edccc`. Kitsune main `2ce7360` ran from a separate runtime checkout (`uv sync --locked`) with isolated headless Firefox. Model: `claude-opus-5-5`, Claude Code 2.1.331.
- Sites and Core: WebArena-Pro `42f4a076` in a Codespace, restarted for this run, with container egress blocked again after the restart. Ports were forwarded over SSH (`-L`). Each attempt recreated its sites and signed in before measurement.
- Grading is unchanged: `backend_state` and `answer_match`, with no working LLM judge. A rubric that escalates to `llm_judge` fails with `configuration_error`, as intended.
- No attempt was excluded. The four-way runner does not save the bridge audit, so the timings for #634 come from transcript timestamps. Raw evidence remains private.
