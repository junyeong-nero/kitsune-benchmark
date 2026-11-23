# Coexistence draft: user-seeded personal tasks and a typing user (Kitsune v0.3.1)

[Results index](README.md) · [By Kitsune version](kitsune-versions.md) · [Track protocol](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/coexistence.md)

**An observation, not a hypothesis verdict.** This is the first model run of the draft
[coexistence track](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/coexistence.md). There is one attempt per task, variant 0,
fixed order (Playwright first). The track is not frozen. Its v3 contracts are new
and are not compared against `taskset-v1` scores.

## Setup

- Date: 2026-10-23 23:12–23:46 KST.
- Benchmark: `57da967` plus the uncommitted coexistence track. Manifests record it as
  `taskset-v1.2-2-g57da967-dirty`. Personal fixtures, graders and the 23-tool
  allowlist are those of `taskset-v1.2`, imported unchanged.
- Model `claude-opus-5-5`, effort medium, Claude Code `2.1.303`, `--harness claude-api`
  (`--bare`), `--max-budget-usd-per-run 1`.
- Kitsune `4ad65ee` (`v0.3.1`, clean pinned clone). Playwright MCP `0.0.83`, Firefox
  `firefox-1553`. Both browsers ran with the user channel (WebDriver BiDi,
  `remote.prefs.recommended=false`). The Kitsune default `KITSUNE_PROTECT_USER_TABS`
  was off.
- Runs:
  - `coexistence --all-personal`: 24 pairs, 48 runs, all scorable, $2.70.
  - `coexistence --task co-typing-01`: two pairs. The first is invalid (see
    [Harness defect](#harness-defect-found-and-fixed)). The valid one cost $0.13.
- Spend (list-price estimate): $2.83 valid, $3.03 including the invalid pair ($0.20).

## Outcomes: 24 personal tasks, user-seeded

| Contract | Playwright | Kitsune |
| --- | ---: | ---: |
| v1 strict close (the personal grade) | 24/24 | 24/24 |
| v2 agent-tab cleanup | 24/24 | 24/24 |
| **v3 user view** (v1, and the shown tab never left the starting tab) | **2/24** | **24/24** |
| Starting tabs listed as agent-owned | n/a | 0 in every run |

Of the 24 Playwright runs, 22 moved the user's view. It was away from the starting
tab in 129 of 204 after-call samples, and was not back on it at the end in 16
runs. The only two runs that kept it never left one tab: `pb-current-01` and
`pb-safe-03`.

Kitsune never moved the view: 0 of 279 samples and 0 sampler transitions.

The mechanism is the documented tool behavior, not a model choice. Playwright MCP
shows a tab when it selects or opens it (`bringToFront`), and every task that
writes to or reads another tab needs one of those. Kitsune 0.3.1's `select` moves
only its tool cursor, and `new` opens in the background.

`pb-account-01`, Kitsune's only personal failure in the
[v0.3.1 full suite](2026-10-23-opus-full-v0.3.1.md), passed here. With one
attempt this says nothing about the earlier failure.

## Outcome: `co-typing-01` (typing user)

| | Playwright | Kitsune |
| --- | --- | --- |
| v1 | pass | pass |
| v3 user view / v3 user input | fail / fail | pass / pass |
| Keystrokes typed into the user's journal | 24 | 84 |
| Keystrokes that went to another tab | 87 (memo, notice) | 0 |
| Calls, elapsed, cost | 12, 27.1 s, $0.091 | 9, 19.5 s, $0.040 |
| Tool errors | 0 | 0 |

When Playwright selected the notice and memo tabs, the user's typing followed the
view into those pages. The agent then filled and saved the memo a second time and
ended with the correct date. Kitsune read and wrote the background tabs while the
user kept typing in the journal.

## Cost and tokens (24 personal pairs)

All runs, summed per target. Input includes cache reads and writes.

| Target | Cost | Input | Output | MCP calls | Median run s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Playwright | $1.23 | 1,307,081 | 20,541 | 204 | 23.0 |
| Kitsune | $1.47 | 1,743,303 | 26,864 | 279 | 27.0 |
| Kitsune ÷ Playwright | 1.19 | 1.33 | 1.31 | 1.37 | 1.17 |

These ratios are close to the v0.3.1 full suite's personal track. There they were
1.21 for cost, 1.35 for input and 1.41 for calls, on 71 joint successes. The user
channel added 30.0 s (Playwright) and 24.7 s (Kitsune) of driver time across 24
runs. That time is inside elapsed, but it is not an MCP call.

So in this run the coexistence behavior costs Kitsune about 1.2× in cost and 1.37×
in calls. The benefit, a user view that was never disturbed, is visible only under
the v3 contract. Whether the extra calls come from the coexistence design or from
the snapshot gaps listed in the v0.3.1 report is not isolated here.

## Harness defect found and fixed

The first `co-typing-01` pair (`20261023T141237Z-c246aefc1a`) is **invalid** for
Playwright. That run's typing user sent keys with content-side BiDi
`input.performActions`. A no-model probe then showed that this, and a content
sandbox `script.evaluate`, permanently break Playwright's Juggler-instrumented
pages: later `browser_snapshot` calls fail with `utilityScript is undefined` or
`Cannot read properties of undefined (reading 'filter')`, even on fresh pages.
Chrome-scope BiDi calls do not cause this.

The typing user now presses keys through the chrome window's
`nsITextInputProcessor` (trusted, into the shown tab's focused element). The user's
field uses `autofocus`. Page content is read only after the agent finishes.

The native no-model tests now assert that the scripted reference agent sees no
tool errors on either server. They also check that the new input still triggers
Kitsune `user_active`.

The valid pair above, and all 24 personal pairs, had 0 Playwright tool errors. The
personal pairs have no typing user.

## Limits

- One attempt per task, fixed order, variant 0. v1 is at its ceiling on both
  targets.
- v3 measures a property Playwright MCP was not designed for. Its isolated browser
  has no user. The result shows what it costs to share an automation browser with
  a person; it does not claim a Playwright defect.
- View samples are taken after each call and every 0.25 s, so sub-interval flicker
  is not counted. The typing user follows one fixed pattern.
- `KITSUNE_PROTECT_USER_TABS=1` (the protection arm) has not been run.

## Artifacts

- `artifacts/coexistence/20261023T142049Z-eaef9dc4d8/suite-summary.json`: the 24
  user-seeded pairs.
- `artifacts/coexistence/20261023T141931Z-4cbb8c75e8/`: the valid `co-typing-01`
  pair.
- `artifacts/coexistence/20261023T141237Z-c246aefc1a/`: the invalid first
  `co-typing-01` pair, kept for the defect record.
