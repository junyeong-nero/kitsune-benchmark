# WebArena-Pro: Kitsune main (`c7149a8`) on Claude Code (API key)

**24 November 2026 · 26 attempts · Kitsune arm only · one repeat per cell.** Kitsune main at `c7149a8`, which merges the fixes for #613–#619, passed 13/26 (test 7/19, dev 6/7) on the `claude-api` harness. The [v0.8.2 check](2026-11-23-kitsune-0.8.2-claude-api.md) on the same harness passed 12/26. The only change in the pass set was `wap-077`, where the model read the task differently, so a tool change did not cause it. Total input fell 18% and tool errors fell from 15 to 7. **No grade in this run was decided by a Kitsune bug.** The README figure was not updated.

[Public per-attempt metrics (CSV)](2026-11-24-kitsune-main-c7149a8-claude-api.csv) · [Running guide](../running.md). Recompute with `python3 summary.py docs/results/2026-11-24-kitsune-main-c7149a8-claude-api.csv`. The CSV omits prompts, answers, tool payloads, credentials and transcripts.

## Comparison with v0.8.2

Same harness (`claude-api`), model, task order and site pins. This is still one repeat per cell, not a controlled A/B.

| Run | Kitsune | Test /19 | Dev /7 | Mean score | Total calls | Tool errors | Median seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-11-24 `claude-api` | main (`c7149a8`) | 7 | 6 | .644 | 334 | 7 | 53.2 |
| 2026-11-23 `claude-api` | v0.8.2 (`9a777eb`) | 6 | 6 | .606 | 369 | 15 | 46.6 |

| Run | Total input | Cached input | Output | Input on common passes | Calls on common passes |
|---|---:|---:|---:|---:|---:|
| 2026-11-24 | 5,811,881 | 5,379,026 | 66,457 | 1,244,864 | 103 |
| 2026-11-23 | 7,118,982 | 6,633,179 | 72,182 | 1,453,809 | 104 |

Input includes cache reads and cache creation. Both runs report usage on 25/26 attempts; the `wap-247` timeout reports none. The common passes are the same 12 tasks in both runs.

- **`wap-077` fail → pass:** the agent answered `DL6387` this time. The 23 November failure was the agent's reading of the task, so this is one-sample variance rather than a tool change.
- **`wap-341` is still a fail, but no longer because of a tool bug.** With #613 fixed, `tab.text()` read every listing, and the agent picked the expected city, Toronto. It then priced the trip at $197 from search-page fares instead of the expected `$206.54`, which failed `exact_match`.
- **Recovery cost is gone on `wap-144` and `wap-233`:** input went from 340k to 126k and from 336k to 153k, with no `stale_ref` or `script_operation_limit` errors (#616, #618). `wap-069` halved its input, from 1.87M to 0.94M.
- **`wap-261` input grew from 232k to 601k.** The agent spent about six calls finding an icon-only bookmark button (E4 below).
- **`wap-247` timed out at 600 seconds again.** It hit `script_timeout` twice. The second script used `try/finally` and still returned the 36 city counts it had collected (#618), but reading about 135 cities page by page does not fit the budget (E6).
- **The `operations` share of tool results fell** from 20.1% to 7.9% of all tool-result characters, and from 75% to 16% of failed results (#617).
- **Tool errors:**
  - `not_found` 3
  - `script_timeout` 2
  - `unsupported_selector` 1
  - `needs_user` 1

  All three `not_found` errors were wrong selectors written by the agent. Two of them are explained by E2 below.
- **Cost:** Claude Code estimated $4.57 for the run. The Anthropic Console is the billing source.

## Effect of the #613–#619 fixes

| Issue | Seen in this run |
|---|---|
| #613 page text | `wap-341` read all listings and picked the right city |
| #614 date inputs | Snapshots show `[type=date min=… max=…]`; no date was silently rejected |
| #615 dialogs | `wap-096` result lists the `confirm()` with `response: true`; calls 22 → 14 |
| #616 stale field refs | 0 `stale_ref` errors (4 before) |
| #617 operations summary | 7.9% of result characters (20.1% before) |
| #618 script budget | `wap-247` kept partial output via `finally`; no `script_operation_limit` errors |
| #619 schema errors | none occurred |

## Why the 13 tasks failed

None of these grades came from a tool defect.

| Task | Score | Cause |
|---|---:|---|
| `wap-065` | 0 | The answer named the right flight but left out the flight numbers the rubric requires |
| `wap-069` | .5 | The flights passed; the agent booked the cheapest Toronto stay, not the expected listing |
| `wap-079` | 0 | Stopped on the fare page without booking |
| `wap-095` | 0 | Applied to the contract role instead of Backend Engineer (Go) |
| `wap-096` | 0 | Kept "Intern (Part-Time)" in the new titles; the rubric expects "Product Design" and "Data Science" |
| `wap-139` | 0 | Registered a course instead of answering that the student was already registered |
| `wap-140` | .5 | Used a placeholder card instead of the password manager's card; payment failed and the agent asked the user |
| `wap-247` | 0 | 600 s timeout (see E6) |
| `wap-258` | .75 | Did not follow City Desk |
| `wap-260`, `wap-261` | .67 | Bookmark count off by 2. All four arms got the same .67 on 20 November, so this is likely the rubric or the seed, not the tool |
| `wap-341` | 0 | Right city, wrong total (see above) |
| `wap-344` | .67 | Used a placeholder card instead of the password manager's card; payment failed |

## Bug and enhancement leads from the transcripts

Found by reading all 26 transcripts after the run. Counts are from this run only. B1, B2 and E2 were then reproduced on a local fixture page with the same runtime (main `c7149a8`, isolated headless Firefox).

### Bugs

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| B1 | [#627](https://github.com/junyeong-nero/kitsune/issues/627) | `tab.text()` serves page text cached for up to 5 s. The bridge caches `getPageText` for `CACHE_TTL = 5` s, and only bridge write actions clear it, so a change the page makes itself stays invisible. `wait_for(text_gone='Loading...')` did succeed (at 2.5 s in the reproduction), but the `text()` straight after it still held `Loading...`, while `query` and `markdown` already showed the new content. | `wap-229`, `wap-231` (wait `ok`, then a stale `Loading...`); `wap-233` (still stale after `sleep(1.5)`) |
| B2 | [#629](https://github.com/junyeong-nero/kitsune/issues/629) | When a query clips a field, the warning says "read one element in full with `tab.markdown(target)`". For a `<textarea>`, Markdown collapses the line breaks: the query value had `analytics.\n\nAbout the role`, and `markdown()` returned `analytics. About the role`. The hint therefore leads to lossy reads of form values. `tab.forms()` keeps the value intact. | `wap-096` (the agent rebuilt the newlines by hand) |

### Enhancements

| # | Kitsune issue | Finding | Evidence |
|---|---|---|---|
| E1 | [#630](https://github.com/junyeong-nero/kitsune/issues/630) | Inside `browser_run_python`, `tab.text()` is capped at 20,000 characters (`PAGE_TEXT_LIMIT`), even though a script's reads are not shown to the model and its output has its own 16 KB cap. Scans of long result lists read only part of the page. | 15 "Page text was cut" warnings in 5 tasks; `wap-069`'s fare scan read 176 of 200 fares on each search |
| E2 | [#628](https://github.com/junyeong-nero/kitsune/issues/628) | The snapshot lists `article` for `role="article"` divs, but the CSS selector `article` matches only the tag. `query('article')` returned `[]` with no warning, and `click('article >> nth=0')` returned `not_found`. A zero-match hint naming `role=article` would have saved these calls. | `wap-341` (3 times), `wap-140` (once) |
| E3 | [#631](https://github.com/junyeong-nero/kitsune/issues/631) | `navigate` and `new_tab` return once the DOM is ready (#601), so single-page apps are often read mid-render: an empty `snapshot`, an empty `text()`, or `Loading...`. Agents then add `sleep(1–3)` and read again. A hint when the body is nearly empty, or an optional wait for content, would remove the retry. | 7 tasks: flight-search new tabs, PipeCRM deal pages, Vaultwise |
| E4 | [#632](https://github.com/junyeong-nero/kitsune/issues/632) | Icon-only buttons appear as `button ""` inside `form ""`, with no form `action` or `data-testid`, so the agent cannot tell bookmark from like. In the transcripts, `query('form', fields=['action'])` showed `/bookmark/t835` at once. | `wap-261` (about 6 calls), `wap-260` (1 call through `html`) |
| E5 | [#633](https://github.com/junyeong-nero/kitsune/issues/633) | `query` noise and silence: a field that is not supported, such as `outerHTML`, is read as an attribute and silently left out. The "results were truncated" warning also fires when the caller set a small `limit` on purpose (`limit=1`, `3`, `5`). | 12 truncation warnings; `wap-261` `outerHTML` |
| E6 | [#634](https://github.com/junyeong-nero/kitsune/issues/634) | Page-by-page work does not fit the script budget. One TravelMap `navigate` took about 3 s. Four threads on four tabs did 24 navigations in 83 s, no faster than one tab. Whether the bottleneck is the site, the port forward or the bridge's scheduling is not measured. | `wap-247` (timeout in both runs) |
| E7 | [#635](https://github.com/junyeong-nero/kitsune/issues/635) | `a.delete, #rcmbtn_delete, text=Delete` failed with `unsupported_selector`. The hint lists the accepted forms but does not say that a selector list cannot mix CSS with `text=`. | `wap-239` (1 error, then recovered) |

## Protocol and exclusions

- Command: `python3 benchmark.py --execute --harness claude-api --arm kitsune --allow-api-billing`, the 26 cells in matrix order. Every `api_key_source` was `ANTHROPIC_API_KEY`.
- Runner `ba0bfc2`. Kitsune main `c7149a8` ran from a separate runtime checkout (`uv sync --locked`) with isolated headless Firefox. Model: `claude-opus-5-5`, Claude Code 2.1.331.
- Sites and Core: WebArena-Pro `42f4a076` in a Codespace, with container egress blocked again after the Codespace restarted. Unlike 23 November, ports were forwarded over SSH (`-L`), as the [running guide](../running.md#4-connect-the-agent-host-to-the-sites) recommends. Each attempt recreated its sites and signed in before measurement.
- Grading is unchanged: `backend_state` and `answer_match`, with no working LLM judge. A rubric that escalates to `llm_judge` fails with `configuration_error`, as intended.
- No attempt was excluded. The four-way runner does not save the bridge audit, so E6 rests on the transcripts alone. Raw evidence remains private.
