# Four-way, 12 tasks: Aside, EgoLite, Playwright MCP and Kitsune under Claude Code and Codex

[Results index](README.md) · [Suite and running guide](../../four-way/README.md)

![Four-way benchmark, 12 local tasks, 96 attempts. Success, Claude Code / Codex: Aside 12/12 and 12/12; EgoLite 12/12 and 11/12; Playwright MCP 12/12 and 10/12; Kitsune 11/12 and 10/12. Mean input tokens per attempt, Claude / Codex: Aside 53k / 79k; EgoLite 71k / 76k; Playwright 65k / 93k; Kitsune 31k / 66k. Mean tool calls: Aside 4.7 / 4.8; EgoLite 4.0 / 3.5; Playwright 7.1 / 5.9; Kitsune 3.2 / 2.9.](../assets/2026-11-19-four-way.svg)

## Summary

- **Success was near the ceiling:** 90 of 96 attempts passed. Claude Code passed 47/48 and Codex 43/48.
- **Kitsune used the fewest tool calls and the least input under both agents.** Mean input per attempt was 31k
  (Claude) and 66k (Codex). The next lowest were Aside at 53k under Claude and EgoLite at 76k under Codex. Under
  Claude, Kitsune used 47% of Playwright MCP's input and cost 79% as much.
- **The comparison holds on tasks every arm solved.** Claude: 11 tasks, total input Kitsune 315k, Aside 601k,
  Playwright 726k, EgoLite 815k. Codex: 7 tasks, Kitsune 396k, EgoLite 471k, Aside 523k, Playwright 639k.
- **Kitsune failed the native `confirm()` task under both agents.** The open dialog blocked the click until it timed
  out. `browser_handle_dialog` then set a policy for later dialogs (`"dialogs": []`) and did not accept the open
  one, so nothing was submitted. The other three arms passed this task under both agents.
- **Problems in the other tools:**
  - EgoLite's snapshot does not show whether a checkbox is checked.
  - Aside's one-shot REPL sessions lose snapshot refs between calls (22 `RefStaleError`s).
  - Playwright MCP made the most tool calls (7.1 per attempt under Claude) and had no tool errors.
- **Codex reported success falsely twice; Claude never did.** Grading reads the server's submissions, so both were
  counted as failures.

These are single attempts per task and agent. Read differences of one task as observations, not a ranking.

## Setup

| | |
| --- | --- |
| Date | 2026-11-19 |
| Agents | Claude Code 2.1.327, `claude-opus-5-5` (subscription); Codex CLI 0.163.0, `gpt-6.1-sol` (ChatGPT login)\* |
| Aside | CLI 1.26.1107.24, `aside repl --host local`, existing profile |
| EgoLite | `ego-browser` 0.6.3.14 (Chromium 156), `nodejs`, existing profile, new TaskSpace per attempt |
| Playwright MCP | 0.0.83, `--browser firefox --isolated --headless`\*\* |
| Kitsune | `kitsune-browser` 0.8.0, main `bc372d1`, existing profile (Firefox), user tabs `read-only` |
| Tasks | 12 original local fixtures ([list](../../four-way/README.md#test-set)), 1 repeat, 240 s timeout |
| Plan | 12 tasks × 4 arms × 2 agents = 96 attempts; the starting arm rotates per task |
| Grading | the fixture server's received form posts; pass = exactly one correct submission |

\* `gpt-6.2-sol` is not available with this ChatGPT login (HTTP 400), so Codex used `gpt-6.1-sol`.
\*\* Playwright's existing-profile mode needs the Chrome bridge extension, which was not installed. Playwright ran
in an isolated headless Firefox; the other three arms drove the operator's browser.

The runs used an uncommitted working tree. Its code is the `four-way/` suite in this repository; only the
repository-relative paths and the suite README changed when it was committed.

## Results

| Agent | Arm | Pass | Fail | Error | Median s | Tool calls | Tool errors | Input tok | Cached | Output tok | Cost $ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude | Aside | 12 | 0 | 0 | 24.3 | 4.7 | 1.1 | 53,105 | 45,378 | 675 | 0.084 |
| Claude | EgoLite | 12 | 0 | 0 | 17.0 | 4.0 | 0.2 | 71,376 | 58,744 | 784 | 0.128 |
| Claude | Playwright | 12 | 0 | 0 | 17.6 | 7.1 | 0.0 | 65,167 | 60,152 | 654 | 0.065 |
| Claude | **Kitsune** | 11 | 1 | 0 | **15.6** | **3.2** | 0.2 | **30,927** | 26,337 | **468** | **0.051** |
| Codex | Aside | 12 | 0 | 0 | 35.5 | 4.8 | 1.1 | 79,096 | 64,512 | 385 | – |
| Codex | EgoLite | 11 | 1 | 0 | **22.9** | 3.5 | 0.0 | 75,616 | 61,621 | 316 | – |
| Codex | Playwright | 10 | 0 | 2 | 32.4 | 5.9 | 0.0 | 92,710 | 79,373 | 287 | – |
| Codex | **Kitsune** | 10 | 1 | 1 | 24.1 | **2.9** | 0.2 | **65,627** | 55,471 | 303 | – |

How to read the table:

- All values except Pass, Fail and Error are means per attempt; Median s is the median agent time.
- Input includes cached input. Cost is the list-price estimate Claude Code reports; Codex reports none.
- Codex reports usage only when a turn completes. Its three timed-out attempts therefore have no token counts and
  are left out of the token means, but they stay in the success denominator.
- **Tool calls are not the same unit for every arm.** For Aside and EgoLite, one call is one `./browser` JavaScript
  script, which can batch several page actions. For Playwright and Kitsune, one call is one MCP tool call.
- **Fixed context differs by arm.** The median first-request context under Claude was Kitsune 6.6k, Aside 8.6k,
  Playwright 10.3k and EgoLite 13.3k tokens. It includes the CLI guide or the MCP tool schemas, and every later
  request carries it again.

### Per task

Cells: outcome / tool calls / input kTok / seconds.

**Claude Code, `claude-opus-5-5`**

| Task | Aside | EgoLite | Playwright | Kitsune |
| --- | --- | --- | --- | --- |
| dispatch | PASS / 4 / 46k / 21s | PASS / 3 / 56k / 14s | PASS / 6 / 68k / 17s | PASS / 3 / 29k / 13s |
| preferences | PASS / 4 / 46k / 25s | PASS / 7 / 117k / 31s | PASS / 6 / 45k / 12s | PASS / 3 / 29k / 16s |
| directory | PASS / 5 / 56k / 27s | PASS / 4 / 70k / 17s | PASS / 8 / 57k / 17s | PASS / 4 / 36k / 16s |
| catalog | PASS / 4 / 46k / 22s | PASS / 3 / 57k / 15s | PASS / 6 / 71k / 19s | PASS / 2 / 22k / 11s |
| ticket | PASS / 7 / 79k / 32s | PASS / 7 / 119k / 30s | PASS / 7 / 56k / 17s | PASS / 2 / 21k / 11s |
| mail | PASS / 4 / 46k / 24s | PASS / 3 / 56k / 14s | PASS / 8 / 92k / 23s | PASS / 3 / 30k / 19s |
| pager | PASS / 5 / 57k / 25s | PASS / 4 / 75k / 17s | PASS / 9 / 76k / 20s | PASS / 3 / 33k / 15s |
| confirm | PASS / 3 / 36k / 23s | PASS / 2 / 41k / 11s | PASS / 5 / 56k / 14s | **FAIL** / 6 / 56k / 52s |
| lazy | PASS / 5 / 55k / 28s | PASS / 3 / 56k / 18s | PASS / 9 / 91k / 22s | PASS / 3 / 29k / 17s |
| shadow | PASS / 4 / 46k / 22s | PASS / 3 / 55k / 13s | PASS / 6 / 79k / 19s | PASS / 3 / 29k / 11s |
| frame | PASS / 4 / 46k / 23s | PASS / 5 / 85k / 21s | PASS / 5 / 33k / 12s | PASS / 2 / 21k / 11s |
| wizard | PASS / 7 / 78k / 34s | PASS / 4 / 70k / 17s | PASS / 10 / 59k / 18s | PASS / 4 / 37k / 18s |

**Codex, `gpt-6.1-sol`**

| Task | Aside | EgoLite | Playwright | Kitsune |
| --- | --- | --- | --- | --- |
| dispatch | PASS / 4 / 68k / 39s | PASS / 3 / 67k / 24s | PASS / 5 / 100k / 32s | PASS / 3 / 60k / 24s |
| preferences | PASS / 4 / 69k / 37s | **FAIL** / 6 / 120k / 49s | PASS / 5 / 100k / 38s | PASS / 2 / 47k / 25s |
| directory | PASS / 5 / 82k / 29s | PASS / 4 / 83k / 21s | **ERR** timeout / 7 / – / 240s | PASS / 4 / 81k / 40s |
| catalog | PASS / 4 / 69k / 32s | PASS / 2 / 50k / 16s | PASS / 4 / 86k / 23s | PASS / 2 / 47k / 24s |
| ticket | PASS / 5 / 83k / 36s | PASS / 4 / 84k / 21s | PASS / 6 / 85k / 25s | PASS / 2 / 47k / 22s |
| mail | PASS / 4 / 69k / 31s | PASS / 3 / 67k / 36s | PASS / 7 / 101k / 42s | PASS / 3 / 60k / 23s |
| pager | PASS / 6 / 99k / 35s | PASS / 4 / 88k / 27s | PASS / 8 / 106k / 32s | PASS / 4 / 77k / 27s |
| confirm | PASS / 6 / 96k / 36s | PASS / 3 / 66k / 31s | PASS / 4 / 72k / 24s | **FAIL** / 6 / 125k / 61s |
| lazy | PASS / 5 / 82k / 38s | PASS / 4 / 84k / 51s | **ERR** timeout / 5 / – / 240s | PASS / 4 / 73k / 28s |
| shadow | PASS / 4 / 68k / 30s | PASS / 3 / 66k / 18s | PASS / 5 / 100k / 38s | PASS / 3 / 59k / 21s |
| frame | PASS / 4 / 68k / 30s | PASS / 2 / 49k / 17s | PASS / 5 / 60k / 24s | PASS / 2 / 46k / 21s |
| wizard | PASS / 6 / 97k / 45s | PASS / 4 / 84k / 21s | PASS / 10 / 117k / 31s | **ERR** timeout / 0 / – / 240s |

### Tool usage

| Agent | Arm | Calls by tool (all 12 tasks) |
| --- | --- | --- |
| Claude | Aside | `./browser` 56 |
| Claude | EgoLite | `./browser` 48 |
| Claude | Playwright | snapshot 38, click 21, tabs 12, fill_form 5, type 4, select_option 3, handle_dialog 1, wait_for 1 |
| Claude | Kitsune | run_python 23, tabs 12, tools_call 2, take_screenshot 1 |
| Codex | Aside | `./browser` 57 |
| Codex | EgoLite | `./browser` 42 |
| Codex | Playwright | snapshot 24, click 22, tabs 12, type 6, fill_form 3, select_option 3, handle_dialog 1 |
| Codex | Kitsune | run_python 21, tabs 11, tools_call 3 |

- Kitsune agents usually opened the fixture with `browser_tabs` and did the rest in one or two
  `browser_run_python` calls.
- Playwright agents called `browser_snapshot` after most actions. That explains the higher call count and, under
  Codex, the highest input.

## Problems found

### Kitsune: an open native dialog blocks the tab (both agents failed)

1. `tab.click('Archive Beta')` opens `confirm()`. The click does not return, and the script stops with
   `script_operation_failed` / `timeout`.
2. `browser_snapshot` also times out while the dialog is open.
3. `browser_handle_dialog(accept=true)` returns `{"policy": {"accept": true}, "dialogs": []}`. It sets a policy for
   later dialogs and does not act on the open one. A later snapshot shows the page unchanged, and the server
   received nothing.

Claude reported that it could not confirm the archive. Codex reported "Clicked Archive Beta and accepted the
confirmation dialog", which was false. Other arms handled the same page:
- Playwright MCP accepted the open dialog with `browser_handle_dialog`.
- Aside agents registered a `page.on('dialog')` handler before clicking.
- EgoLite's click result reported the open dialog (`r.dialog`), and `page.acceptDialog()` accepted it.

Possible fixes:
- Report a pending dialog in the click result and in snapshots, as EgoLite does.
- Let `browser_handle_dialog` act on the open dialog.
- Or tell agents to set the dialog policy before an action that may open one.

### EgoLite: snapshots omit checkbox state

The `preferences` snapshot lists `checkbox [ref=3]` / `text "SMS"` but does not say whether the box is checked.
Codex clicked Email and Weekly digest and saved, leaving the pre-checked SMS and Push on. It then reported success.
Claude worked around the gap with a screenshot and `:checked` selector probes and passed, but this was its most
expensive EgoLite attempt (7 calls, 117k input). Other EgoLite errors: `<html> intercepts pointer events` (fill
timeout) and `element is not focusable`, once each.

### Aside: state does not survive between one-shot REPL calls

`aside repl --file -` closes the tabs it opened when the session ends. The harness therefore lets the app open the
fixture tab, and the wrapper re-attaches it with `attachBrowserTab` before every call. Refs from an earlier
snapshot are invalid in the next call: 10 `RefStaleError`s under Claude and 12 under Codex, all recovered with a
new snapshot. This is a cost of using the CLI one call at a time; a persistent interactive REPL would probably avoid
it.

Other Aside issues:
- Both models called the Playwright-style `page.once` in `confirm`, which Aside does not provide (`TypeError`),
  then recovered.
- The REPL cannot close an attached tab: `closeTab` only detaches it.
- `goto('about:blank')` and `goto('data:…')` time out on Aside's readiness wait, so fixture tabs were left open.

### Playwright MCP

No tool errors under either agent. Both Codex errors were Codex stalls after successful tool calls:
- In `directory`, the correct value had already been submitted.
- In `lazy`, the claim form had been filled but not submitted.

In both cases no event arrived for the rest of the 240 s, so neither is attributed to Playwright.

### Agents

- **Codex stalls:** three timeouts with no new events. Two followed a completed tool call (above). The third
  (`wizard` on Kitsune) stopped right after its first message, before any tool call.
- **False success claims:** Codex 2 (Kitsune `confirm`, EgoLite `preferences`), Claude 0.
- **Codex used more input than Claude on every arm,** from 1.06× (EgoLite) to 2.12× (Kitsune), and took longer.

## Limits

- One attempt per task and agent. Differences of one task are within noise; use `--repeat 3` or more for claims.
- Browser engines, profiles and isolation differ: Playwright ran an isolated headless Firefox, and the other three
  ran the operator's browsers. This is a product comparison, not a browser-engine comparison.
- The CLI arms ran without an OS sandbox under both agents, because Codex's seatbelt blocks localhost, the keychain
  and LaunchServices. Tool restrictions were instructions.
- The tasks are small and deterministic. They do not measure long navigation, real logins or visual reasoning.
- Most tasks were solved by every arm, so the suite separates tools mainly by cost, not by success.

## Reproduce

From `four-way/`:

```sh
python3 scripts/run.py --browser-mode existing-profile --arm-mode playwright=isolated --execute \
  --harness claude --model claude-opus-5-5 --timeout 240 --out runs/v1/claude-opus-5-5.jsonl
python3 scripts/run.py --browser-mode existing-profile --arm-mode playwright=isolated --execute \
  --harness codex --model gpt-6.1-sol --timeout 240 --out runs/v1/codex-gpt-6.1-sol.jsonl
python3 scripts/analyze.py runs/v1/*.jsonl --out runs/v1/analysis
python3 scripts/figure.py runs/v1/analysis/summary.json ../docs/assets/2026-11-19-four-way.svg
```

The figure's icons (`four-way/figure-icons/`) are original drawings, not the products' logos.

Data: the per-attempt rows, raw transcripts, run metadata and the generated report are in the private Hugging Face
dataset `junyeong-nero/kitsune-browser-bench`.
