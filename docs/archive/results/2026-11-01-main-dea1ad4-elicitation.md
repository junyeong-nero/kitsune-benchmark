# Kitsune main `dea1ad4`: lite suite under the decline and accept elicitation policies

[Results index](README.md) · [Results by Kitsune version](kitsune-versions.md) ·
[Previous: v0.7.1 release cohort](2026-10-29-opus-subscription-v0.7.1.md)

**Bottom line:**

- **Successes:** Kitsune main solves every lite unit under both policies (306/306 scorable runs each). Playwright
  misses one `co-typing-01` unit in the accept run.
- **Holds:** Kitsune main holds the agent's writes on the tab the user is viewing (kitsune#364). Under **decline**
  the agent opened the page in its own tab and redid the write in all 28 runs with a declined hold. Under
  **accept** the held writes ran, and no run redid one.
- **Input, Kitsune/Playwright, units with a hold:** v0.7.1 0.945, decline **1.389**, accept **0.909**. Units without a
  hold are flat (0.803 / 0.835 / 0.863). The cost of the holds comes from the declines, not from the holds.
- **Prompts:** a run with a hold asked the user 1.3 times under decline and **2.1 times under accept**: the agent
  keeps writing in the viewed tab, and each write (type, then click) asks again.
- **Coexistence:** unchanged from v0.7.1. User view 2/28 Playwright vs 28/28 Kitsune; typing input 0/3 vs 3/3.

One attempt per policy, no order counterbalancing; read differences as observations.

## Setup

- **Kitsune:** main **`dea1ad4`** (`v0.7.1-21-gdea1ad4`), clean clone in `artifacts/vendor/kitsune-main-dea1ad4/`. It
  adds #364 (viewed-tab hold), #371 (user-tab navigation protection by default), #376–#381 (`needs_user`,
  approval through MCP elicitation, `browser_resume`) and #348–#350 (post-action deltas, `navigated`).
- **Model and harness:** `claude-opus-5-5`, medium; Claude Code `2.1.303` on the subscription. Playwright MCP
  `0.0.83`, same 23-tool allowlist.
- **Tasks:** personal, gallery, coexistence and external tasks, fixtures, graders and configs are those of
  `taskset-v3.1.1`. Only the harness differs from the v0.7.1 cohort: benchmark `main` before #55 cannot set up
  sessions on Kitsune main (its setup navigate is held), so both runs use #55's relay, which answers Kitsune's
  approval prompts.

| Run | Policy | Benchmark | Started (KST) | Wall time |
| --- | --- | --- | --- | --- |
| decline | `decline` (#55 default) | `dc0db32` (#55 head, `taskset-v3.1.1-10`) | 2026-11-01 02:22 | 1 h 33 min |
| accept | `accept` (#59 `--elicitation accept`) | `2cbc91a` (main after #54–#64, `taskset-v3.1.1-30`) | 2026-11-01 11:25 | 1 h 36 min |

Both: `scripts/run-full-suite.py --plan lite`, 306 agent runs, no retries; personal, gallery and external ran the
two targets concurrently, coexistence ran paired.

- **Harness approvals:** in both runs the relay approves the harness's own held setup calls (two `browser_navigate`
  per personal pair, `user_tab`), never the agent's under decline.
- **Between the runs:** #57 (setup approvals with a token fallback), #56 (no model request after a failed setup), #58
  (hold counters), #59 (policy option) and #60 (hostile strategies) were merged. None changes what the agent sees.
- **A first decline attempt on benchmark `main`** failed setup on the first Kitsune pair and was stopped
  (#56, #57). It is not part of these results.

**Offline audit, both runs:** 306/306 runs `completed_unscored` and scorable; every run used `claude-opus-5-5`; no
audit violations, harness errors or missing allowlisted tools; 112/112 personal runs asserted the 1280×720 content
viewport.

## Outcomes (lite units)

| Track | Units | Playwright decline / accept | Kitsune decline / accept |
| --- | ---: | --- | --- |
| Personal v0–v1 | 56 | 56 / 56 | 56 / 56 |
| Gallery crowded v0 | 21 | 21 / 21 | **21 / 21** (v0.7.1: 20/21) |
| Gallery isolated v0 | 21 | 21 / 21 | 21 / 21 |
| Coexistence user-seeded | 28 | 28 / 28 | 28 / 28 |
| Coexistence `co-typing-01` v0–v2 | 3 | 3 / 2 | 3 / 3 |
| Coexistence protect arm (Kitsune) | 28 | — | 28 / 28 |
| External (7 MiniWoB + 3 live) | 10 | 10 / 10 | 10 / 10 |

## Kitsune holds

From `scripts/analyze-release.py` (#58), counted per run from the relay's evidence.

| Run | Runs with a hold | Holds (all `user_viewing`) | Decision | Runs that redid a declined write |
| --- | ---: | ---: | --- | ---: |
| decline | 28 (personal 12, coexistence 16) | 37 | 37 declined | **28** |
| accept | 27 (personal 13, coexistence 14) | 58 | 58 accepted | 0 |

- Under decline, holds hit 8 of the 28 personal tasks, ones that write into the starting tab (`pb-current-01`,
  `pb-safe-01/02/03`, `pb-research-01`, `pb-account-01`, `pb-handoff-04`, and `pb-tabs-01` in coexistence). Gallery
  runs in a harness-opened agent tab (#54) and had no holds.
- **Redo after decline** (decline run): the agent opened the same page with `browser_tabs new` and repeated the write
  there, as the declined result's hint suggests (kitsune#383). By tool, 37 declined writes were 17 type, 13 click and
  7 fill_form; 4 runs (`pb-safe-03`) count as redone on a click match alone, the loosest case of the rule.
- When the agent opened its own tab before writing, it was never held (for example `pb-account-01` personal v1 under
  decline).

## Tokens, calls and elapsed time (joint successes, Kitsune / Playwright)

| Track | Joint (decline / accept) | Input v0.7.1 | Input decline | Input accept | MCP calls decline / accept | Elapsed decline / accept |
| --- | --- | ---: | ---: | ---: | --- | --- |
| Personal | 56 / 56 | 0.829 | 0.943 | **0.878** | 1.072 / 0.980 | 0.921 / 0.881 |
| Gallery crowded | 21 / 21 | 0.572 | 0.704 | 0.709 | 0.940 / 0.922 | 0.820 / 0.946 |
| Gallery isolated | 21 / 21 | 0.922 | 0.859 | 0.963 | 0.746 / 0.764 | 0.859 / 0.876 |
| Coexistence user-seeded | 28 / 28 | 0.841 | 0.946 | **0.864** | 1.096 / 0.944 | 0.969 / 0.866 |
| External | 10 / 10 | 1.193 | 1.165 | 1.060 | 1.000 / 0.976 | 1.101 / 1.023 |

Personal and coexistence units, split by whether Kitsune's run had a hold:

| Units | v0.7.1 | decline | accept |
| --- | ---: | ---: | ---: |
| With a hold (20 under decline, 21 under accept) | 0.945 | **1.389** | **0.909** |
| Without a hold (64 / 63) | 0.803 | 0.835 | 0.863 |

- **The declines cost the tokens.** Each declined write costs a new tab, a snapshot and the write again. With the
  writes approved, units with a hold cost what they cost on v0.7.1.
- **Gallery crowded (0.572 → about 0.71)** is not a Kitsune change. There were no holds in gallery. Kitsune's crowded
  input total moved 2.09M → 2.15M (+3%) between v0.7.1 and the accept run, while Playwright's fell 3.73M → 3.03M
  (−19%): v0.7.1's Playwright run had a 49-call, 687k-token `ui-editor`.
- **Units #348–#350 targeted improved** (decline run vs v0.7.1): `mw-book-flight` 2.21 → 1.30, `mw-use-autocomplete`
  1.25 → 1.05, `live-steam` 1.48 → 1.18, `ui-shadow` isolated 1.36 → 1.01.
- **Navigated results are sent twice** (kitsune#384): in the decline run, 102 of 119 actions that returned
  `navigated` were followed by an observation, 100 of them sent in the same turn as the action.
- **`ui-editor` crowded** took 28 calls (one `press_key` per syllable) under decline and 8 under accept, so the
  per-character typing in kitsune#385 does not happen every run; the editor's text is missing from Kitsune's
  snapshots in both.
- **`coexistence-typing`** ratios (decline 1.025, accept 0.255 on 2 units) rest on one to three runs; Playwright failed
  `co-typing-01` v0 under accept.

## Coexistence (frozen plan)

| | v0.7.1 | decline | accept |
| --- | --- | --- | --- |
| User view kept (v3), PW / K | 2/28 / 28/28 | 2/28 / 28/28 | 2/28 / 28/28 |
| Typing user's input kept, PW / K | 0/3 / 3/3 | 0/3 / 3/3 | 0/3 / 3/3 |
| Protect arm (K) | 28/28 | 28/28 | 28/28 |

On Kitsune main the protect arm equals the default (kitsune#371); `--unprotected-user-tabs` (#58) is the arm without
protection and was not run.

## Hostile-UI matrix (no model, synthetic input)

- **Shared strategies** (run `20261031T185533Z`): Playwright 23/26, Kitsune **21/26** (v0.7.1: 20/26).
  `cross-origin-iframe` is now solved (kitsune#343, #354).
- **Kitsune-only strategies** (#60, run `issue60-main-dea1ad4-ec46530`): `long_press` (`hold_ms: 700`) solves
  `long-press` and `hover_intent` (`duration_ms: 500, steps: 5`) solves `hover-intent`, so Kitsune solves 23/26 with
  them. `css-hover-menu` stays unsolved: synthetic moves do not apply CSS `:hover`. On v0.7.1 both strategies report
  `unsupported`.

## Limits

- One attempt per policy, Kitsune and Playwright concurrent; elapsed times are under shared load.
- **Neither policy is a real user.** Decline answers no to every prompt; accept says yes to every approval prompt,
  and `browser_ask_user` prompts are declined in both. A real user approves some and declines some, and takes time to
  answer, which neither run measures.
- The decline run's suite manifest predates #59; its policy is read from the pairs' session evidence (286/286
  `decline`).
- The live tasks in external are ungraded.

## Artifacts (private)

- `artifacts/opus-subscription-main-dea1ad4-pr55/` (decline) and `artifacts/opus-subscription-main-dea1ad4-accept/`
  (accept), with `artifacts/review-decline.md` and `artifacts/review-accept.md`.
- Hostile: `artifacts/hostile/runs/20261031T185533Z/`, `artifacts/hostile/runs/issue60-main-dea1ad4-ec46530/` and
  `issue60-v0.7.1-ec46530/`.

Related: #55–#64; kitsune#364, #371, #376, #383, #384, #385.
