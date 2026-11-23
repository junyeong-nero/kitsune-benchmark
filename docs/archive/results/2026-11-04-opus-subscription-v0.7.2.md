# Kitsune v0.7.2: release cohort on `taskset-v3.2` (lite plan)

[Results index](README.md) · [Results by Kitsune version](kitsune-versions.md) ·
[Previous: `taskset-v3.2` on main `514b5b7`](2026-11-01-taskset-v3.2-main-514b5b7.md)

**Bottom line:**

- **User tabs are read-only, and nothing is held any more.** v0.7.2 refuses writes and `select` on the user's tabs
  with `user_tab_read_only`, without a prompt (kitsune#395, #398). The 16 personal runs that had a viewed-tab hold on
  `514b5b7` are gone. Instead, 33 of 56 personal Kitsune runs had a refused `browser_tabs select` and opened the page
  in a tab of their own.
- **Successes:** 306/306 runs scorable. Kitsune misses one task, `pb-tabs-03` ("note the return period, then go back
  to the order tab"), in all four entries that run it. The order tab never left the front. The grader reads Kitsune's
  `current` tab as the one in front, and Opus left its own memo tab current ([below](#pb-tabs-03)).
- **Input, Kitsune/Playwright on jointly solved units, `514b5b7` → v0.7.2 (167 shared units):**
  - personal 0.973 → 0.985, with fewer calls (1.179 → 1.081);
  - crowded gallery 0.693 → **0.625**;
  - isolated gallery 0.667 → 0.962 (the 0.667 came from one Playwright outlier; without it, 0.900);
  - coexistence 0.977 → 0.936, external 1.023 → 0.936.
- **Coexistence:** unchanged. No Kitsune run moved the user's view (Playwright: 26 of 28 did). The typing user kept
  their input in 3/3 Kitsune runs and 0/3 Playwright runs (0 against 300 misdirected characters).
- **Two harness fixes were needed** (#91, #92). The second removes a setup artifact that v0.7.2's navigate results
  exposed in gallery isolated, which was then rerun ([below](#harness-changes)).

One attempt, no order counterbalancing; read differences as observations.

## Setup

- **Kitsune:** **`v0.7.2`** (`28ca61c`), clean clone in `artifacts/vendor/kitsune-v0.7.2/`.
- **Model and harness:** `claude-opus-5-5`, medium; Claude Code `2.1.303` on the subscription. Playwright MCP
  `0.0.83`, same 23-tool allowlist.
- **Benchmark:** tag `taskset-v3.2` plus harness fixes. The first run is on `d22b0a3` (#91), the isolated rerun on
  `64de4b3` (#92). Tasks, pages and graders are those of `taskset-v3.2`.
- **Plan:** `scripts/run-full-suite.py --plan lite`, elicitation `decline`, 306 agent runs. Personal, gallery and
  external ran the two targets concurrently; coexistence ran paired.

| Run | Entries | Started (KST) | Ended (KST) |
| --- | --- | --- | --- |
| first (`opus-subscription-v0.7.2`, `d22b0a3`) | all 15 entries | 2026-11-04 08:20 | 09:59 |
| retry (`opus-subscription-v0.7.2-retry`, `64de4b3`, `--from gallery-isolated-v0`) | `gallery-isolated-v0`; stopped by the operator when `coexistence-user-seeded` started | 10:13 | 10:21 |

**Merged:** `merge-suites.py` wrote `opus-subscription-v0.7.2-merged`: gallery isolated from the retry, everything
else from the first run. The first run's isolated entry is kept on disk and discussed under
[Harness changes](#harness-changes).

**Preflight:**

- 341 benchmark tests; `doctor` (subscription login, no API key);
- native coexistence tests against v0.7.2: 25/25;
- native personal tests against v0.7.2: 38/39. `test_six_fixtures_seed_and_solve_via_real_kitsune_ui` uses the old
  agent-seeded setup, which navigates the fresh profile's tab. That tab is the user's, so v0.7.2 refuses it. The suite
  seeds personal tabs through the user channel (#70) and is unaffected;
- one `pb-tabs-01` v0 pair, both successful; after #92, one Kitsune `ui-shadow` isolated run, successful.

**Offline audit (merged):** 306/306 runs `completed_unscored` and scorable; every run used `claude-opus-5-5`; no audit
violations, harness errors or missing allowlisted tools; 112/112 personal runs asserted the 1280×720 content viewport.

## Outcomes (lite units)

| Track | Units | Playwright | Kitsune |
| --- | ---: | --- | --- |
| Personal v0–v1 | 56 | 56 | **54** (`pb-tabs-03` v0, v1) |
| Gallery crowded v0 | 21 | 21 | 21 |
| Gallery isolated v0 (retry) | 21 | 21 | 21 |
| Coexistence user-seeded | 28 | 28 | **27** (`pb-tabs-03`) |
| Coexistence `co-typing-01` v0–v2 | 3 | 3 | 3 |
| Coexistence protect arm (Kitsune) | 28 | — | **27** (`pb-tabs-03`) |
| External (7 MiniWoB + 3 live) | 10 | 10 | 10 |

MiniWoB: 7/7 both. Live tasks: completed by both; advisory answer matches 2/3 both.

### `pb-tabs-03`

The request is "참고 문서 탭에서 반품 가능 기간을 메모한 뒤, 지금 보던 주문 탭으로 돌아와 줘." Success needs the right memo
and, at the end, the original order tab as the tab in front.

- In all four Kitsune runs the memo is right and the order tab stayed in front. Kitsune lists it `active` throughout,
  and the coexistence view sampler recorded no change of view.
- v0.7.2 refuses to `select` a user tab. The agent opened the returns page and the memo in tabs of its own, saved the
  memo, and its final `select` of the order tab was refused (`user_tab_read_only`).
- For Kitsune the harness reads the agent's `current` tab as the tab in front, as it reads Playwright's `(current)`
  marker. Kitsune lists the agent's memo tab as current, so the check fails. When no tab is current, the harness reads
  the viewed tab instead: a Codex run (`gpt-6.1-sol`) on main `a51961a` passed v0 that way, by closing its two tabs
  at the end. Opus never closed them.
- This is a mismatch between the grader and read-only user tabs more than a wrong action. Reading Kitsune's `active`
  tab instead would change a grader, which needs a new taskset tag. Not done here.

## Tokens, calls and elapsed time (joint successes, Kitsune / Playwright)

| Track | Joint | Input `514b5b7` → **v0.7.2** | Paired input median | Units with less K input | Output | MCP calls `514b5b7` → v0.7.2 | Elapsed |
| --- | ---: | --- | ---: | ---: | ---: | --- | ---: |
| Personal | 54 | 0.973 → **0.985** | 1.005 | 24/54 | 1.204 | 1.179 → 1.081 | 1.035 |
| Gallery crowded | 21 | 0.693 → **0.625** | 0.695 | 20/21 | 0.791 | 0.895 → 0.772 | 0.768 |
| Gallery isolated | 21 | 0.667 → **0.962** | 0.997 | 11/21 | 0.896 | 0.613 → 0.798 | 0.906 |
| Coexistence user-seeded | 27 | 0.977 → **0.936** | 0.966 | 17/27 | 1.211 | 1.159 → 1.094 | 1.013 |
| Coexistence typing | 3 | 1.003 (2 units) → 0.717 | 1.233 | 1/3 | 0.908 | 1.000 → 0.789 | 0.719 |
| External | 10 | 1.023 → **0.936** | 1.011 | 5/10 | 1.022 | 0.952 → 0.929 | 0.901 |

`514b5b7` values are from `scripts/analyze-release.py --compare` against `opus-subscription-v3.2-main-514b5b7-merged`
on the 167 units both suites share. Claude Code's list-price estimate, Kitsune / Playwright on the same units:
personal 0.970, crowded 0.562, isolated 0.867.

- **Personal: the holds are gone, the detour stays.** On `514b5b7` a held unit cost 1.386 and the others 0.839. v0.7.2
  holds nothing, but reading a background user tab now takes a detour. `browser_tabs select` on it is refused, and the
  core `browser_snapshot` takes no tab, so the agent opens the URL again in a tab of its own. 53 of 56 Kitsune
  personal runs opened their own tab before the first write, against 14 for Playwright. Kitsune's runs end close to
  parity (0.985), with more output (1.204).
- **Gallery isolated** is back in its usual range after #92. On `514b5b7` it was 0.910 on `taskset-v3.1.2` and 0.667
  on `taskset-v3.2`, the latter from one Playwright `mm-video` run (559k input); without that unit it was 0.900.
- **Crowded** keeps its gain from v0.7.1 (0.572) and `514b5b7` (0.627): 20 of 21 units use less Kitsune input.

## Kitsune behaviour

- **No viewed-tab holds** (removed in kitsune#398). Two runs asked for a handoff with `browser_tabs request`
  (personal v0 `pb-handoff-01`, coexistence `pb-current-01`); the relay declined both under the `decline` policy, and
  both runs then solved the task in a tab of their own (input 1.16× and 2.50× Playwright).
- **`user_tab_read_only`:** 75 refusals in 70 of 167 Kitsune runs, every one a `browser_tabs select` of a user tab
  (personal 33/56 runs, coexistence user-seeded 18/28, protect arm 16/28, typing 3/3; none in gallery or external).
- **Observations:** mean full snapshot 988 characters against 2,387 for Playwright (21 Kitsune snapshots truncated);
  mean `browser_find` result 1,046 against 1,385. The agent followed an action right away with an observation call
  34% of the time on Kitsune and 56% on Playwright.
- **Agent tab idle cleanup** (kitsune#420, 5 minutes by default on a fresh profile) could not fire: the longest
  Kitsune run took 62 s.

## Coexistence (frozen plan)

| | `514b5b7` (`taskset-v3.2`) | v0.7.2 |
| --- | --- | --- |
| Runs that moved the user's view, PW / K | 26/28 / 0/28 | 26/28 / 0/28 |
| User view kept (v3, needs task success), PW / K | 2/28 / 28/28 | 2/28 / 27/28 (`pb-tabs-03`) |
| Typing user's input kept, PW / K | 0/3 / 3/3 | 0/3 / 3/3 |
| Misdirected characters, PW / K | 183 / 0 | 300 / 0 |
| Protect arm (K) | 28/28 | 27/28 (`pb-tabs-03`) |

On v0.7.2 the protect arm's `KITSUNE_PROTECT_USER_TABS=1` is a deprecated alias that does not change the default
(read-only), so the arm runs the same configuration as the user-seeded Kitsune runs.

## Harness changes

- **#91 (`d22b0a3`), read-only user tabs:** a refused `select` of a user-seeded tab leaves the viewed tab standing in
  for current (`setup_select_refused_read_only`), and on gallery the user closes the fresh profile's blank tab over
  the user channel when Kitsune refuses the close. Also keeps the coexistence user record when Codex stops the relay.
- **#92 (`64de4b3`), unseen `unchanged_since` in gallery:** v0.7.2 carries a small page's snapshot in a navigate
  result (kitsune#410), and the tab's next whole-page snapshot then answers "unchanged since the browser_navigate
  result" (kitsune#384) instead of the page. The harness navigates the gallery task tab during setup, so in the first
  run 19 of 21 Kitsune isolated runs got that answer to their first snapshot, for a result they never saw, and spent a
  round on `browser_tabs list` and a second snapshot. Isolated input was **1.210** in that run. The crowded pages are
  too large for the navigate snapshot, so crowded was unaffected (0/21). The harness now takes that snapshot itself at
  the end of setup on Kitsune, which drops the record (evidence `setup_snapshot_unchanged_since`). After the rerun:
  0.962.

Kitsune keeps that record per tab, not per client. Another client reading a tab right after this client navigated
it would get the same unseen `unchanged_since`; that is a Kitsune issue candidate.

## Limits

- One attempt; Kitsune and Playwright concurrent in personal, gallery and external, so elapsed times are under
  shared load.
- The isolated rerun used a later harness commit than the rest, which changes only Kitsune's gallery setup.
- Kitsune personal results are comparable only with other `taskset-v3.2` cohorts.

## Follow-ups

- `pb-tabs-03`: done in `taskset-v3.3` ([#94](https://github.com/junyeong-nero/kitsune-benchmark/issues/94)),
  which grades it on the tab the user sees. This cohort's evidence predates that field, so its four misses are not
  re-graded.
- Kitsune: key the `unchanged_since` record by client
  ([kitsune#442](https://github.com/junyeong-nero/kitsune/issues/442)).
- `test_six_fixtures_seed_and_solve_via_real_kitsune_ui`: seeds through the user channel since
  [#95](https://github.com/junyeong-nero/kitsune-benchmark/issues/95).
- Refusals and copies of user tabs are now in `analyze-release.py`
  ([#101](https://github.com/junyeong-nero/kitsune-benchmark/issues/101)); the arms set `KITSUNE_USER_TABS`
  ([#100](https://github.com/junyeong-nero/kitsune-benchmark/issues/100)).
