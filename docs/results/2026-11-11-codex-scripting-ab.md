# Codex: Kitsune legacy vs scripting on main `883d80e`

[Results index](README.md) · [Original task/order protocol](../experiments/2026-11-11-kitsune-scripting-surface-ab.md)

**Bottom line: input fell, but this run does not justify making scripting the default yet.**

- **80 attempts completed:** legacy 34 successes, 5 graded failures and 1 unstarted; scripting 32 successes,
  7 graded failures and 1 unstarted. The two unstarted attempts retain their original unscorable grades.
- On the **28 matched task/repeat cells both arms solved**, scripting / legacy input is **0.884**, output
  1.119, MCP calls **1.088**, and elapsed **1.069**. Lower input did not mean fewer calls or faster completion.
- **Python failed in 13 of 32 calls**, across 7 scripting runs. Most clearly, `ui-infinite` failed in both
  scripting repeats after `Tab.scroll()` was refused because the default `core` grant lacks `browse`.
  Legacy solved both repeats using its direct tools.
- MiniWoB used **no Python in either arm**. Its matched input ratio is 0.782.
- This is a separate Codex/ChatGPT-subscription cohort, not a continuation of the paused Claude experiment.
  Codex JSONL does not expose model request counts, first-request input or dollar cost. **The proposed
  cost ≤ 1.0 gate cannot be evaluated here.** No Kitsune default or release was changed.

Two repeats, variant 0 only: these are observations, not a statistically established success-rate regression.

## Setup

- **Kitsune:** clean pinned checkout `883d80eee2c85f81410352ea8f86b81e11a2b682`, at
  `artifacts/vendor/kitsune-main-883d80e`. All 80 pair manifests confirm that revision and a clean checkout.
- **Model/client:** `gpt-6-luna`, medium, Codex CLI `0.163.0`, ChatGPT subscription. No API-key billing or
  fallback. The standard harness strips provider credentials, ignores user config/rules and disables
  built-in shell, browser, skills and subagents. Only the Kitsune MCP is enabled.
- **Arms:** legacy (default environment; 27 tools), scripting (`KITSUNE_SCRIPTING=1`; 14 tools including
  `browser_run_python`). No benchmark tool allowlist. Both retain the default `KITSUNE_CAPS=core`.
- **Tasks:** MiniWoB `mw-{click-test-2,click-checkboxes,enter-text,choose-list,login-user,use-autocomplete,
  book-flight}`; personal `pb-{current,tabs,research,account,handoff,safe,longpage}-01`; isolated gallery
  `ui-{table,autocomplete,infinite,shadow,iframe,editor}`. MiniWoB seed 42, pinned upstream `33c3b4d`;
  personal/gallery variant 0. The existing prompts and graders are unchanged.
- **Order:** original repeat-major ABBA schedule: 20 tasks × 2 arms × 2 repeats. A fresh private Firefox
  profile/bridge per attempt; personal starting tabs are user-seeded through the existing test channel.
  Personal/gallery use the existing full-native relay with elicitation `decline`.
- **When:** 2026-11-11, approximately 21:19–22:12 KST (including the explicit mid-run review).
- **Runner:** `scripts/run-codex-scripting-ab.py`, reusing `run_one` from `scripts/run-scripting-ab.py` with
  an explicit `harness="codex"`. The shared function's default remains Claude. Base benchmark revision
  `e2b8a79`, with these uncommitted runner changes; manifests retain runner hashes.

### Catalog observability

Both arm catalogs were checked without inference by importing the pinned server in separate, allowlisted
processes. The 52 personal/gallery attempts additionally recorded the actual MCP `tools/list` catalogs in
relay metadata, all at 27/14 as expected. MiniWoB has no relay, and Codex does not report the initial tool
list in its JSONL: its `published` field is **null**, not an inferred 27/14. The preflight is not client
inventory attestation. No extra browser action or catalog probe was added to the measured task sessions.

### Explicit stopping-policy change

Attempt 10 (`mw-login-user`, r0 scripting) stopped the original runner as unscorable. The model finished
normally, but interpreted Kitsune's advisory `needs_user.reason=sign_in` on the synthetic password field as
requiring real user login. It called `browser_ask_user`, received a decline, and stopped without clicking
START. The result was `episode_starts=0`, `telemetry_errors=0`, `outcome=no_terminal_reward`.

The operator explicitly approved preserving that attempt and continuing the remaining 70. The opt-in
`--continue-unstarted` records this exception in `continuation.json`, without rewriting `manifest.json`,
prior rows, prompts, model, Kitsune code or grades. Only normally completed MiniWoB attempts with zero
starts, zero telemetry errors and no terminal reward qualify; execution/quota/catalog errors still stop.
Attempt 50 (r1 legacy, the same login task) met the same condition and was also preserved. Neither was retried.
The legacy book-flight attempts **did** start, so their missing terminal rewards remain ordinary graded failures.

## Results

All-attempt totals (the success denominator includes unstarted attempts):

| Metric | Legacy | Scripting |
| --- | ---: | ---: |
| Attempts | 40 | 40 |
| Scorable | 39 | 39 |
| Successes / attempts | 34/40 | 32/40 |
| Graded failures | 5 | 7 |
| Unstarted, unscorable | 1 | 1 |
| Input tokens, including cache hits | 5,255,146 | 4,748,534 |
| Cached input tokens | 4,522,368 | 4,085,376 |
| Output tokens | 17,321 | 20,444 |
| MCP calls | 235 | 269 |
| Summed agent elapsed | 889.242 s | 987.676 s |
| Python calls / failed Python calls | 0 / 0 | 32 / 13 |

Do not use the raw input total as an efficiency ratio: early failures can spend fewer tokens. On matched
(task, repeat) cells **both arms solved**, ratios below are scripting / legacy:

| Track | Successes L / S (attempts each) | Matched cells | Input | Output | Calls | Elapsed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MiniWoB | 11 / 13 (14) | 10 | 0.782 | 1.085 | 0.960 | 1.022 |
| Personal | 13 / 11 (14) | 11 | 0.959 | 1.192 | 1.164 | 1.130 |
| Gallery | 10 / 8 (12) | 7 | 0.876 | 0.977 | 1.120 | 1.014 |
| **All** | **34 / 32 (40)** | **28** | **0.884** | **1.119** | **1.088** | **1.069** |

The 25 matched cells without Python have input 0.830 and calls 1.032. The 3 matched cells using Python have
input 1.191 and calls 1.391. This is descriptive selection by agent behavior, not a randomized Python-only A/B.
Elapsed includes client/model/network and, on personal/gallery, hidden relay work; it is not native tool latency.

## Python and failure observations

Python was used in `pb-tabs-01` ×2, `pb-longpage-01` ×2, `pb-safe-01` r0, and `ui-infinite` ×2.

| Python error category | Calls | Examples |
| --- | ---: | --- |
| `capability_restricted` | 4 | `text()` and `info()` need `read`; `scroll()` needs `browse` (twice) |
| `AttributeError` | 5 | `browser.help()`, `tab.help()`, `tab.locator()`, and treating a tab dict as an object |
| `TypeError` | 2 | `snapshot(depth=...)`, `find(load_more=True)` |
| `NameError` | 1 | Reusing `t` from a previous script invocation |
| `invalid_tab_id` | 1 | Passing list index 0 as a real tab ID |

`ui-infinite` is the clearest actionable scripting observation: both attempts ended after the Python scroll
capability refusal. The agent's final answer explicitly reported that it could not scroll. This is a mismatch
between the attempted Python replacement and default grants, not evidence that all scrolling routes are absent.
No capability or tool description was changed during the experiment.

Other failures should not all be attributed to Python:

- `pb-tabs-01`: scripting failed twice and legacy once. Each saved the correct product name **plus explanatory
  text**, but this fixture requires an exact saved string (`personal.py`, `self.note.strip() == expected["answer"]`).
  These are recorded contract/format failures, not proof that the product lookup itself was wrong.
- `pb-current-01` scripting r1 left the note empty after requesting permission instead of completing the task in
  its own writable tab.
- `ui-table`: legacy failed twice, scripting once. The saved component outcome was `not_done`; the final chat
  answer is not the grade. `ui-shadow` scripting r1 submitted but did not establish the requested field values.
- Legacy `mw-book-flight` failed both repeats after reporting no results and stopping. Scripting solved both.
- The two login-task unstarted cases occurred in opposite arms/repeats, not only scripting.

All 80 client executions ended `completed_unscored`, with no harness errors or audit violations. All 52
personal/gallery runs passed their safety checks. Python scripts had no matches for the existing reward/page-JS
pattern audit and no URLs; this limited audit is not a hardened anti-cheating proof.

## Reproduce and artifacts

```sh
uv run --locked python scripts/run-codex-scripting-ab.py run \
  --kitsune-project artifacts/vendor/kitsune-main-883d80e \
  --kitsune-sha 883d80eee2c85f81410352ea8f86b81e11a2b682 \
  --out artifacts/codex-scripting-ab-main-883d80e --continue-unstarted

uv run --locked python scripts/run-codex-scripting-ab.py analyze \
  --out artifacts/codex-scripting-ab-main-883d80e

uv run --locked python -m unittest tests.test_codex_scripting_ab tests.test_adapter \
  tests.test_claude_harness tests.test_full_native tests.test_full_suite
```

85 targeted tests passed. Fresh experiments need a fresh `--out`; resuming validates the recorded configuration.
The historical cohort began without `--continue-unstarted` and resumed with it after the operator's approval.

Private artifacts: `artifacts/codex-scripting-ab-main-883d80e/{manifest.json,continuation.json,runs.jsonl,analysis.json}`.
Each row points to its isolated pair and raw events under `artifacts/scripting-ab/`. Raw local fixture content is
not published here. The earlier Claude cohort remains paused and separate.
