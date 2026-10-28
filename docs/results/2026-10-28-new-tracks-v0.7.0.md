# New tracks on Kitsune v0.7.0: `external-v1` and `coexistence-local-v1` (2026-10-28)

[Results index](README.md) · [Coexistence protocol](../coexistence.md) · [External protocol](../external.md)

**Setup:**

- Model and harness: `claude-opus-5-5`, medium, Claude Code `2.1.303` on the subscription.
- Kitsune `v0.7.0`.
- Benchmark source: `e2c9900` (`taskset-v3-8-ge2c9900`, clean). The `taskset-v3.1` tag did not exist
  yet; this checkout is the content it is meant to freeze.
- One attempt, AB order (Playwright first) in one process, no retries.
- 110 agent runs, all scorable. Every track command exited 0.

This is the first run of the two new tracks. For coexistence it follows the
[frozen plan](../coexistence.md#frozen-protocol) for one attempt. It is a single attempt in fixed
order, so it is not a ranking. Do not pool it with the pre-freeze coexistence draft reports.

## External (`external-v1`): 20 runs

| Task | Playwright | Kitsune |
| --- | --- | --- |
| 7 MiniWoB++ tasks (seed 42) | **7/7** full reward | **7/7** full reward |
| MiniWoB calls / elapsed / reported input | 55 / 163.9 s / 457k | 58 / 122.2 s / 449k |
| Live: Steam GOTY review filter | completed (13 calls) | completed (17 calls) |
| Live: Wikipedia first release (advisory) | match | match |
| Live: MDN `Array.prototype.at` Firefox (advisory) | match | match |
| Live calls / elapsed / reported input | 28 / 106.2 s / 295k | 36 / 126.6 s / 573k |

- **MiniWoB.** Both targets solved every task, including `login-user` and the multi-step
  `book-flight`. Kitsune was faster on the seven together, at about the same input.
- **Live.** Kitsune used about 1.9× the input. Most of the gap comes from Steam (257k vs 121k) and
  Wikipedia (235k vs 90k). Live sites change, so this is qualitative evidence, not a score. The
  Steam task has no advisory check; judge it from the transcripts.

## Coexistence (`coexistence-local-v1`): 90 runs

### User-seeded, 28 personal tasks, variant 0

| | Playwright | Kitsune |
| --- | --- | --- |
| Primary (v2) success | 28/28 | 28/28 |
| Strict v1 | 28/28 | 27/28 (`pb-account-01`: closed its own tab) |
| **`v3_user_view` (main verdict)** | **2/28** | **28/28** |
| Runs where the user's view left the starting tab | 26 | 0 |
| Calls / reported input / elapsed, successful runs | 243 / 2.16M / 693 s | 250 / 1.75M / 574 s |

Playwright kept the user's view only on `pb-current-01` and `pb-safe-03`. On joint successes,
Kitsune used 0.81× the input at about the same number of calls. Every one of the 56 runs asserted
the 1280×720 content viewport.

### `co-typing-01`, the typing user, variants 0-2

| Variant | Playwright | Kitsune |
| --- | --- | --- |
| v0 | **functional failure**; 150 misdirected characters | success, `v3_user_input` pass, 0 misdirected |
| v1 | success; `v3_user_input` fail, 51 misdirected | success, pass, 0 misdirected |
| v2 | success; `v3_user_input` fail, 192 misdirected | success, pass, 0 misdirected |

The v0 Playwright failure is the interference itself, not a harness problem:

1. The agent switched the shown tab to work on the memo.
2. The user's keystrokes went into the memo's date field and corrupted it.
3. The agent saw this and stopped. Switching tabs again would have taken more of the user's typing.
4. It asked the user to finish typing first.

The misdirected counts grow with how long a run lasts. Read them per run, not as rates.

### Protection arm (Kitsune + `KITSUNE_PROTECT_USER_TABS=1`), 28 tasks

| | Default Kitsune | Kitsune + protect |
| --- | --- | --- |
| Primary success / `v3_user_view` | 28/28 / 28/28 | 28/28 / 28/28 |
| `user_tab` refusals | 0 | 1 run, 1 refusal (`pb-safe-02`, still succeeded) |
| Calls / reported input, successful runs | 250 / 1.75M | 245 / 1.78M |

Turning protection on cost nothing measurable in this attempt. There was one refusal, the agent
recovered from it, and calls and input stayed within ±2%.

## Limits

- One attempt in a fixed order, and only variant 0 for the 28 user-seeded tasks.
- Live results depend on the sites as they were on 2026-10-28.
- Raw evidence is in private, gitignored `artifacts/new-tracks-20261028/`, `artifacts/external/` and
  `artifacts/coexistence/`.
