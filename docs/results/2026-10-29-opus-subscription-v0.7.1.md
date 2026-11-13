# Kitsune v0.7.1: release cohort on `taskset-v3.1.1` (lite plan) and hostile-UI matrix

[Results index](README.md) · [Release cohort protocol](../experiments/2026-10-29-release-cohort-protocol.md) ·
[Results by Kitsune version](kitsune-versions.md)

**Bottom line:**

- **Successes:** v0.7.1 keeps every success the v0.7.0 cohorts had on the same units, except one `mm-audio` refusal of
  the kind seen before.
- **Input, Kitsune/Playwright on jointly solved units:**
  - crowded gallery **0.945 → 0.572**;
  - isolated **1.018 → 0.922**;
  - personal flat (0.815 → 0.829).
- **Coexistence:** unchanged. User view 2/28 Playwright vs 28/28 Kitsune; typing 0/3 vs 3/3.
- **Hostile-UI matrix:** with synthetic input, Kitsune solves **20/26** components (v0.7.0+26 dev build: 18/26).
  Canvas targets and Radix Select now work.

This is one attempt with no order counterbalancing, so read release differences as observations (protocol rules).

## Setup

- **Kitsune:** **`v0.7.1`** (`9f84b25`), clean clone in `artifacts/vendor/kitsune-v0.7.1/`. The revision was
  unchanged across the suite.
- **Benchmark:** tag **`taskset-v3.1.1`** (`f758fa3`) = `taskset-v3.1` + setup compatibility (#35) + `--plan lite`
  (#45). Tasks, fixtures, graders and configs are those of `taskset-v3.1`.
- **Model and harness:** `claude-opus-5-5`, medium; Claude Code `2.1.303` on the subscription. Playwright MCP
  `0.0.83`, same 23-tool allowlist.
- **Run:** 2026-10-29, 15:04–16:28 KST (1 h 24 min), `scripts/run-full-suite.py --plan lite`, 306 agent runs, no
  retries.
  - Personal, gallery and external ran the two targets concurrently.
  - Coexistence ran paired, Playwright first.
- **Preflight** (protocol step 2), all passed:
  - 297 benchmark tests;
  - `doctor` (subscription login, no API key);
  - the crowded probe: 21/21 task sections in Kitsune's first snapshot;
  - one `pb-current-01` pair, both successful, with `setup_selected_initial_tab: true` on Kitsune.

**Offline audit:** 306/306 runs `completed_unscored` and scorable. Every run used `claude-opus-5-5`. There were no
audit violations, no harness errors and no missing allowlisted tools. All 112 personal runs asserted the 1280×720
content viewport on both targets.

## Outcomes (lite units)

| Track | Units | Playwright | Kitsune v0.7.1 | Misses |
| --- | ---: | ---: | ---: | --- |
| Personal v0–v1, primary (v2) | 56 | 56/56 | **56/56** | none (strict v1 also 56/56 both) |
| Gallery crowded v0 | 21 | 21/21 | 20/21 | K `mm-audio`: `no_attempt` |
| Gallery isolated v0 | 21 | 21/21 | 21/21 | none |
| External MiniWoB (full reward) | 7 | 7/7 | 7/7 | none |
| External live (completed; advisory matches) | 3 | 3/3; 2/2 | 3/3; 2/2 | not graded |

On `mm-audio`, Kitsune's agent said it could not play the audio and declined to guess, so no attempt was spent. The
2026-10-26 v0.7.0 cohort had the same failure class on that task (crowded v1).

## Tokens, calls and elapsed time (lite units, joint successes, Kitsune / Playwright)

| Track | Joint | Input v0.7.0 → **v0.7.1** | Paired input median | Units with less K input | Output | MCP calls | Elapsed |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Personal | 56 | 0.815 → **0.829** | 0.844 | 48/56 | 0.943 | 0.980 | 0.826 |
| Crowded | 20 | 0.945 → **0.572** | 0.561 | 17/20 | 0.757 | 0.806 | 0.766 |
| Isolated | 21 | 1.018 → **0.922** | 0.956 | 13/21 | 0.868 | 0.877 | 0.761 |

- **Raw input, v0.7.1 joint units (Playwright / Kitsune):**
  - personal 4,403,099 / 3,649,923;
  - crowded 3,613,788 / 2,066,112;
  - isolated 1,467,833 / 1,353,571.
- **v0.7.0 reference:** the same lite units of the 2026-10-26 cohort, recomputed as in the protocol.
- **Crowded:** the drop matches what the benchmark measured for #319 (snapshot budget: main first, compact link URLs)
  and #330 (compact `browser_find`). Kitsune also needs fewer calls than Playwright here now: 0.806, against 1.216 on
  v0.7.0.
- **Per tool:** Kitsune's mean `browser_find` result is 891 characters against Playwright's 8,501 (#330). Its mean
  snapshot is 883 against 5,849.

## Coexistence (frozen plan)

| | Playwright | Kitsune v0.7.1 | v0.7.0 (2026-10-28) |
| --- | ---: | ---: | --- |
| User-seeded primary success | 28/28 | 28/28 | 28/28 both |
| **`v3_user_view`** | **2/28** | **28/28** | 2/28 vs 28/28 |
| `co-typing-01` v0–2: success | 3/3 | 3/3 | PW 2/3, K 3/3 |
| **`v3_user_input`** | **0/3** | **3/3** | 0/3 vs 3/3 |
| Misdirected characters (per run; not a rate) | 189, 51, 39 | 0, 0, 0 | 150, 51, 192 vs 0 |
| Protect-user-tabs arm | — | 28/28, `v3_user_view` 28/28, 0 refusals | 28/28, 1 refusal |

## External

- **MiniWoB:** 7/7 both. Kitsune's MiniWoB input is 620,287 against 505,352 for Playwright. Almost all of the
  difference is one run: `mw-book-flight` took 302,882 input and 33 calls (v0.7.0: 138,732 and 18).
  - After the destination was typed, the autocomplete list did not appear (`find "(EAT)"` returned 0 matches), and the
    agent retyped several times before it showed.
  - One run each cannot separate a regression from variance; it is listed for follow-up.
- **Live:** completions 3/3 and advisory matches 2/2 for both. Kitsune input on Wikipedia was 52,846 (v0.7.0 run:
  234,645), consistent with #330. Steam: 207,056 (v0.7.0: 257,212). MDN: 77,894.

## Hostile-UI matrix on v0.7.1 (no model, synthetic input)

[Track](../hostile.md). The same 26 components and strategies as
[2026-10-29](2026-10-29-hostile-headless.md), headless, clean `v0.7.1`.

**Components solved: Playwright 23/26, Kitsune 20/26.** The dev build `57c56a7` solved 18/26.

| Change since `57c56a7` | Cause |
| --- | --- |
| `canvas-button` click: `target_not_found` → **accepted** | #341: the `role="img"` canvas now has a ref |
| `lib-radix-select` option click: `not_accepted` → **accepted** | #340: the pointer approaches before the press |
| `pointer-capture-drag` drag: `target_not_found` → `not_accepted` | #341: the drop mark has a ref now. The page reports `setPointerCapture: Invalid pointer id`; a synthetic pointer is not one the browser tracks, so it cannot be captured |
| `hover-intent`: still not accepted, now past the hover step | #342: the tile has a ref; the widget needs sustained movement, and Playwright fails it too |

**Still Playwright-only:**

- `trusted-click` and `css-hover-menu`: synthetic-input limits that `browser_trusted_click` covers (opt-in run,
  2026-10-29);
- `pointer-capture-drag` (above);
- `cross-origin-iframe` (#343, open).

**Kitsune-only:** `closed-shadow`.

## Limits

- **Single attempt:** one attempt, Playwright-first pairing in coexistence, and concurrent targets elsewhere, so elapsed
  time and resources are measured under shared load.
- **Lite plan:** 21 units per gallery layout; one unit moves a layout's success rate by about 5 points.
- **Different days:** the v0.7.0 references are from 2026-10-26 (personal and gallery) and 2026-10-28 (coexistence,
  external). Live pages change between runs.
- **Raw evidence (private):**
  - `artifacts/opus-subscription-v0.7.1/` (suite manifest, log and per-track outputs);
  - pair directories under `artifacts/personal`, `gallery`, `coexistence` and `external`;
  - `artifacts/hostile/runs/headless-v0.7.1/`.
