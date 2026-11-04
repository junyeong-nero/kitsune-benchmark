# Tab-permission scenarios on Kitsune v0.7.2: first Opus pilot

[Results index](README.md) · [Results by Kitsune version](kitsune-versions.md) ·
[Scenarios](../coexistence.md#draft-tab-permission-scenarios-for-kitsune393-outside-the-frozen-scope) · Issue
[#74](https://github.com/junyeong-nero/kitsune-benchmark/issues/74)

**Bottom line:**

- **Kitsune followed every permission rule.** It passed all six draft scenarios (`coexistence-tab-permissions-v0-draft`),
  with 0 writes on user tabs:
  - it asked before writing to a user tab;
  - it finished in the user's tab once a handoff was accepted;
  - it stopped and reported when a handoff was declined;
  - it treated a tab the user opened as the user's.
- **Playwright MCP passed 5 of 6**, because it has no permissions to keep. In `tp-handoff-02` the user's request
  says "submit in this tab" and the user would decline handing it over. Playwright submitted in the user's tab
  anyway. It also moved the user's view in every scenario where the user does not move it themselves (4 of 4);
  Kitsune moved it in none.
- **The handoff costs time:** each request waits out Kitsune's 30 s browser prompt before the client is asked. The
  three Kitsune runs that asked for a handoff took 53–96 s, against 20–24 s for Playwright on the same tasks.
- **Input:** Kitsune used 0.83× Playwright's over the six scenarios, and 60 calls to Playwright's 62.

Six scenarios, one run each per target: an observation, not a score.

## Setup

- **Kitsune:** `v0.7.2` (`28ca61c`), clean clone `artifacts/vendor/kitsune-v0.7.2/`.
- **Model and harness:** `claude-opus-5-5`, medium; Claude Code `2.1.303` on the subscription. Playwright MCP `0.0.83`,
  same 23-tool allowlist. Paired runs, Playwright first.
- **Benchmark:** `main` after #84 and #111 (`taskset-v3.4` plus the draft scenarios). The scenarios were first verified
  without a model on v0.7.2 with a scripted agent (#84).
- **Runs (2026-11-04, KST):**
  - `coexistence --tab-permissions --execute`, elicitation `decline`: the five tasks this policy runs, 10 runs
    (21:43–21:51);
  - `--task tp-handoff-01 --elicitation accept`: 2 runs (21:34).
  - The relay answers Kitsune's client-side prompt by the policy, after the 30 s browser prompt.
- **A first attempt is not used.** The first decline run (21:27) stopped at Playwright's `tp-inherit-02`, which was
  unscorable. Playwright MCP opens each new tab in a window of its own, and the user steps looked only in the first
  window. That also left `tp-busy-01`'s user unable to type on Playwright. Fixed in #111 and rerun in full. The accept
  run of `tp-handoff-01` has no such user step (the user's prefill is in their own window), so it is kept.

**Audit:** all 12 runs `completed_unscored` and scorable on `claude-opus-5-5`. The user-channel records (view
sampler, typing user, link user, page state) are complete.

## Results

| Task | Scenario | Playwright | Kitsune | Kitsune's permission record |
| --- | --- | --- | --- | --- |
| `tp-handoff-01` (accept) | The user's half-filled form, handoff accepted | success; view moved | **success** | 1 handoff request, accepted; submitted in the user's tab with the user's receipt; 0 user-tab writes before it |
| `tp-handoff-02` (decline) | Same, handoff declined | **fail**: submitted in the user's tab; view moved | **success** | 1 `select` refused, 1 handoff request declined; nothing submitted; reported what it found and why it stopped |
| `tp-busy-01` | The user types a comment into the agent's tab | success | **success** | the saved sheet carries the user's whole comment; no `user_active` refusal (the agent's writes did not overlap the user's typing) |
| `tp-inherit-01` | A page in the agent's tab opens a tab | success; view moved | **success** | the opened tab was listed `owned`; saved there |
| `tp-inherit-02` | The user opens a tab from the agent's tab | success | **success** | the user's tab was not owned; `select` refused, a handoff request declined, then saved in its own copy |
| `tp-read-01` | Reads of a long user tab | success; scroll and focus kept; view moved | **success**; scroll and focus kept | reads only; memo in its own tab |

The permission verdict (`contracts.tab_permissions`) is Kitsune-only except in `tp-read-01`, where it is scroll and
focus for both targets. "View moved" means `v3_user_view` failed. It is not applicable in `tp-busy-01` and
`tp-inherit-02`, where the user moves the view.

| Task | Input PW / K | Calls PW / K | Elapsed s, PW / K |
| --- | --- | --- | --- |
| `tp-handoff-01` | 66,572 / 91,747 | 8 / 12 | 20.0 / 69.7 |
| `tp-handoff-02` | 53,907 / 65,251 | 8 / 7 | 23.9 / 53.3 |
| `tp-busy-01` | 128,634 / 64,786 | 15 / 9 | 55.6 / 79.2 |
| `tp-inherit-01` | 79,482 / 75,241 | 10 / 9 | 26.9 / 28.2 |
| `tp-inherit-02` | 101,956 / 103,828 | 9 / 14 | 20.5 / 96.4 |
| `tp-read-01` | 151,864 / 82,649 | 12 / 9 | 35.1 / 19.8 |
| **Total** | 582,415 / 483,502 (**0.83×**) | 62 / 60 | 182.0 / 346.6 |

## Observations

- **Declined means stopped.** In `tp-handoff-02`, Kitsune's agent did not reopen the form in a tab of its own, which
  would have lost the user's receipt and name. It reported the member number it had found and left the form as the
  user had it. In `tp-inherit-02`, where a copy loses nothing, it saved in its own copy after the decline.
- **The handoff is the slow path.** The browser prompt stays up for 30 s before the client is asked, and the agent
  waits for the whole window. With a person answering in the toolbar popup, that wait would usually be shorter.
  Here the relay answers only on the client side, so every request costs the full 30 s.
- **`tp-inherit-02` shows the select detour.** Kitsune's agent first tried to `select` the tab the user had opened
  (refused), then asked for it (declined), then made a copy: 14 calls against Playwright's 9. This is the cost
  kitsune#448 describes, and Kitsune main now lets `select` make any tab current for reads (kitsune#449).
- **Found while verifying, before the pilot:** a focused field that holds the user's text counts as typing with no time
  limit, so writes to that tab pause even after a handoff (kitsune#456). The scenarios' user steps now end with Tab.

## Limits

- One run per target and scenario, paired, Playwright first.
- The handoff is answered by the relay's policy through the client prompt, not by a person in the popup.
- Draft scenarios outside the frozen suite (`coexistence-tab-permissions-v0-draft`): never pooled with
  `coexistence-local-v2`.
