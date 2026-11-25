# WebArena-Pro: Kitsune main (`0a8ada9`, the v0.8.3 candidate) on Claude Code (API key)

**25 November 2026 · 26 attempts · Kitsune arm only · one repeat per cell.** Kitsune main at `0a8ada9`, which merges the fixes for #648–#656 and is the commit planned for the v0.8.3 tag, passed 13/26 (test 7/19, dev 6/7) on the `claude-api` harness. The [`2ce7360` check](2026-11-25-kitsune-main-2ce7360-claude-api.md) earlier the same day passed 12/26. The only change in the pass set was `wap-077`, where the answer included the flight number again, so a tool change did not cause it. Input, calls and time were within 3% of that run on the 12 tasks both passed. Tool errors went from 12 to 13; three of the 13 trace to a tool lead (B1, E4). **No grade in this run was decided by a Kitsune bug.**

[Public per-attempt metrics (CSV)](2026-11-25-kitsune-main-0a8ada9-claude-api.csv) · [Running guide](../running.md). Recompute with `python3 summary.py docs/results/2026-11-25-kitsune-main-0a8ada9-claude-api.csv`. The CSV omits prompts, answers, tool payloads, credentials and transcripts.

## Comparison with earlier runs

Same harness (`claude-api`), model, task order and site pins. This is still one repeat per cell, not a controlled A/B.

| Run | Kitsune | Test /19 | Dev /7 | Mean score | Total calls | Tool errors | Median seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-11-25 `claude-api` | main (`0a8ada9`) | 7 | 6 | .644 | 314 | 13 | 45.5 |
| 2026-11-25 `claude-api` | main (`2ce7360`) | 6 | 6 | .606 | 311 | 12 | 46.0 |
| 2026-11-24 `claude-api` | main (`c7149a8`) | 7 | 6 | .644 | 334 | 7 | 53.2 |
| 2026-11-23 `claude-api` | v0.8.2 (`9a777eb`) | 6 | 6 | .606 | 369 | 15 | 46.6 |

| Run | Total input | Cached input | Output | Input on common passes | Calls on common passes | Seconds on common passes |
|---|---:|---:|---:|---:|---:|---:|
| `0a8ada9` | 5,030,673 | 4,612,232 | 60,767 | 1,103,955 | 90 | 369 |
| `2ce7360` | 5,167,058 | 4,751,947 | 63,591 | 1,070,183 | 88 | 383 |
| `c7149a8` | 5,811,881 | 5,379,026 | 66,457 | 1,244,864 | 103 | 476 |

Input includes cache reads and cache creation. Each run reports usage on 25/26 attempts; the `wap-247` timeout reports none. The common passes are the same 12 tasks in all three runs. Against v0.8.2, total input is down 29% (7,118,982 to 5,030,673) and calls are down 15%.

- **`wap-077` fail → pass:** the answer has `DL6387` this time. The task has gone fail, pass, fail, pass over the last four runs on the agent's answer alone.
- **`wap-096` used 42% less input** (373k to 217k, 18 calls to 10) and **`wap-069` 24% less** (860k to 650k).
- **`wap-238` and `wap-244` kept the quoted message.** The same read-then-fill script that wrote a cut reply body on `2ce7360` wrote the whole body (#650).
- **`wap-341` and `wap-140` used more input** (387k to 615k and 391k to 548k). In `wap-341` the agent first entered 2027 dates, then worked through the calendar. In `wap-140` it lost three calls to errors (B1, E2).
- **`wap-247` timed out at 600 seconds for the fourth run.** It used `browser.parallel` for the first time, spent six calls learning it, lost one script's results to the deadline, and read 42 of 135 cities, against 106 on one tab before (E3). Seven tabs were 1.3 times as fast as one, so the site is the bottleneck (#634).
- **Tool errors:**
  - `script_error` 4
  - `not_found` 3
  - `No field was filled` 2
  - `stale_ref` 1
  - `script_timeout` 1
  - navigate timeout 1
  - `needs_user` 1

  Three `script_error`s were a variable from an earlier script (E2); the fourth was `KeyError: 'text'` on a `browser.parallel` result (E3). Two `not_found`s were `text=Select flight` on the return leg, where the button says "Book". The third was `button[action=…]` (E4). Both `No field was filled` errors are B1. The `stale_ref` was a ref the agent's own click had removed, and the navigate timeout was TravelMap not answering after the parallel batches. There was no `ambiguous_target` (3 before).
- **Cost:** Claude Code estimated $4.23 for the run. The Anthropic Console is the billing source.

## Effect of the #648–#656 fixes

| Issue | Seen in this run |
|---|---|
| #648 form `value` | `wap-233`: the New Deal form is `form "" [ref=e133]`, with no `[value="[object HTMLInputElement]"]` |
| #649 button named by `value` | Not exercised |
| #650 whole form values in scripts | 0 value-clip warnings (3 before); `wap-238` and `wap-244` wrote the whole reply body |
| #651 rendering warning at the first read | 12 script warnings, none in a script that calls `wait_for` before it reads (10 of 20 before) |
| #652 `wait_for(content=True)` | Used 4 times (`wap-140`, `wap-341`). After a script warning 2 of 6 next calls used it; after the direct hint 0 of 5 did (E1) |
| #653 hint for `button[action=…]` | `wap-261`: the hint named `form[action="/bookmark/t836"] button`, and the next call used it (1 lost call, 2 before) |
| #654 `text=` inside one control | Not exercised |
| #655 unassociated labels | The booking form lists `textbox "First name"` and `textbox "Card number" [placeholder="4111111111111111"]`; the form's three `textbox ""` lines are gone |
| #656 `[value=""]` on buttons | 0 button lines with an empty value (444 before) |

## Why the 13 tasks failed

None of these grades came from a tool defect.

| Task | Score | Cause |
|---|---:|---|
| `wap-065` | 0 | The answer has none of the flight numbers the rubric requires |
| `wap-069` | .5 | The flights passed; the agent booked the cheapest Toronto stay, not the expected listing |
| `wap-079` | 0 | Stopped at checkout without paying |
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

Found by reading the transcripts after the run. Counts are from this run only. B1 and the `browser.parallel` result shape were reproduced on local fixture pages with the same runtime (main `0a8ada9`, isolated headless Firefox).

### Bugs

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| B1 | [#666](https://github.com/junyeong-nero/kitsune/issues/666) | `tab.fill_form` does not take snapshot refs, which every other action does, and it does not match the label that the snapshot and `tab.forms()` show for a field with an unassociated `<label>` (#655). Every key is `Not found`, the call fails with `No field was filled`, and there is no hint. | `wap-140`, `wap-344` (1 call each) |

### Enhancements

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| E1 | [#667](https://github.com/junyeong-nero/kitsune/issues/667) | The direct no-content hint names `browser_wait_for(content=true)`. The code-first surface does not expose that tool, and the agent's next call is a script, so it sleeps. | 5 of 5 `browser_tabs` hints were followed by `time.sleep(1); print(tab.snapshot())`. 91 of 290 scripts sleep, 190 s in all |
| E2 | [#668](https://github.com/junyeong-nero/kitsune/issues/668) | A `NameError` from a variable of an earlier script gets the general hint "Earlier operations may have taken effect", although nothing ran. It does not say that variables do not carry over. | 3 of 4 `script_error`s (`wap-069`, `wap-140` twice) |
| E3 | [#669](https://github.com/junyeong-nero/kitsune/issues/669) | `browser.parallel` is hard to use from a script: `help()` is one line, the action is `pageText` and not `text`, the text is at `r['results'][0][seq][step]['text']`, a failed step does not raise, and a timeout loses everything not yet printed. | `wap-247` (six calls to learn it, one script's results lost) |
| E4 | [#670](https://github.com/junyeong-nero/kitsune/issues/670) | The snapshot's `[action="/bookmark/t836"]` still leads to `button[action=…]`. The #653 hint recovers, but the failed call remains. | `wap-261`, in two runs out of two |
| – | [#634](https://github.com/junyeong-nero/kitsune/issues/634) (comment) | TravelMap serves pages about one at a time: 7 tabs took 2.4 s per page and 3 tabs 2.5 s, against 3.2 s on one tab, and the site stopped answering for about a minute and a half after the 7-tab script. | `wap-247` |

## Protocol and exclusions

- Command: `python3 benchmark.py --execute --harness claude-api --arm kitsune --allow-api-billing`, the 26 cells in matrix order. Every `api_key_source` was `ANTHROPIC_API_KEY`.
- Runner `7f83e5f`. Kitsune main `0a8ada9` ran from a separate runtime checkout (`uv sync --locked`) with isolated headless Firefox. Model: `claude-opus-5-5`, Claude Code 2.1.331.
- Sites and Core: WebArena-Pro `42f4a076` in a Codespace, restarted for this run, with container egress blocked again after the restart. Ports were forwarded over SSH (`-L`). Each attempt recreated its sites and signed in before measurement.
- Grading is unchanged: `backend_state` and `answer_match`, with no working LLM judge. A rubric that escalates to `llm_judge` fails with `configuration_error`, as intended.
- No attempt was excluded. The four-way runner does not save the bridge audit, so the timings for #634 come from transcript timestamps. Raw evidence remains private.
