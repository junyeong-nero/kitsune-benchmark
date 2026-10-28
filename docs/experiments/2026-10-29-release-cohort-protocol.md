# Release cohort: the next Kitsune release on `taskset-v3.1` — test protocol

[Results index](../results/README.md) · [Results by Kitsune version](../results/kitsune-versions.md) ·
[Running guide](../running.md)

This protocol fixes how the next Kitsune release is evaluated before any run. It is committed before the first
execution. The report goes in `docs/results/` and is added to `kitsune-versions.md`.

## Purpose

The release after v0.7.0 contains several changes that the benchmark measured or that touch its tracks:

- kitsune#319: snapshot budget and landmarks (#310);
- #318: ARIA sliders and `press_key` repeat (#311);
- #313: the shadow-root `..` step (#312);
- #316/#303: current tab and tab-less writes;
- #317: trusted-click buttons;
- #330: compact `browser_find` (#323), if merged.

This cohort runs the frozen suite once on that release, with the personal and gallery tracks reduced to about 100
units (the `lite` plan below), so the two releases can be compared track by track on the same units.

## Pins

| What | Value |
| --- | --- |
| Kitsune | Release tag `<TAG>` (for example `v0.8.0`). A clean checkout goes to `artifacts/vendor/kitsune-<TAG>/`, and its revision and `git describe` are recorded in `suite-manifest.json` |
| Benchmark | Tag **`taskset-v3.1.1`**, created before the run on `main`: `taskset-v3.1` + kitsune-benchmark#35 (setup compatibility) + #45 (`--plan lite`) (see below). The checkout must be clean |
| Harness | Claude Code `2.1.303`, `--harness claude` (claude.ai subscription, no API credit, no fallback) |
| Model | `claude-opus-5-5`, effort medium |
| Comparison target | Playwright MCP `0.0.83`, the same 23-tool UI allowlist |
| Browser | The private Firefox build in `artifacts/browsers` (`firefox-1553`) |

**Why `taskset-v3.1.1`.** Kitsune after v0.7.0 (#303) refuses a tab-less `browser_navigate` with `no_current_tab`
until a tab is selected. The personal relay's setup starts with exactly that call. kitsune-benchmark#35 lets setup
select the fresh profile's only tab and retry, but only when that refusal occurs. It is the only change to
`kitsune_benchmark/` since `taskset-v3.1`. #45 only adds the `lite` plan to `scripts/run-full-suite.py`. Together:

- Kitsune v0.7.0 never takes that branch, so its results are reproducible on `taskset-v3.1.1` unchanged.
- Setup calls are harness calls, not recorded in `tab_calls`, so grading is unaffected.
- Tasks, fixtures, graders, configs and catalogs are identical to `taskset-v3.1`.

## Scope (one attempt, `--plan lite`, 306 agent runs)

`scripts/run-full-suite.py --plan lite` runs, in this order:

| Track | Entries | Units | Agent runs |
| --- | --- | ---: | ---: |
| Personal | `personal --all --variant 0/1`: all 28 tasks, data variants 0 and 1 | 56 | 112 |
| Gallery | `gallery --layout crowded/isolated --variant 0`: all 21 tasks, both layouts, variant 0 | 42 | 84 |
| Coexistence (frozen plan) | user-seeded 28 tasks v0; `co-typing-01` v0–2; Kitsune protect-user-tabs arm 28 tasks v0 | 59 | 90 |
| External | 7 MiniWoB++ + 3 live tasks | 10 | 20 |

The `lite` plan keeps every personal and gallery task and both gallery layouts. Only data variants are dropped:
98 of the 210 personal and gallery units. The full plan (`--plan full`, 530 runs) stays available. Coexistence and
external are the same in both plans.

- **Personal, gallery and external:** Playwright and Kitsune run as two concurrent processes (the default), so elapsed
  time and resources are measured under shared load.
- **Coexistence:** always runs paired in one process, Playwright first.
- **Duration:** expected about 1.5–2 h. The 2026-10-26 cohort took 2 h 17 min for 480 runs.

## Procedure

1. **Pin.** Clone `<TAG>` into `artifacts/vendor/kitsune-<TAG>`, then check that `git describe --tags` equals `<TAG>`
   and the worktree is clean. Create and push the benchmark tag `taskset-v3.1.1` at the commit with #35, and check it
   out clean.
2. **Preflight** (no model calls; any failure stops here):

   ```sh
   uv run --locked python -m kitsune_benchmark doctor --json      # subscription login, no API key
   uv run --locked python -m unittest discover -s tests           # all pass
   K=$PWD/artifacts/vendor/kitsune-<TAG>
   uv run --locked python scripts/probe-snapshot-budget.py $K artifacts/preflight-<TAG> --layout crowded
   ```

   - The probe must complete all 21 crowded gallery tasks. This proves that personal-style setup works against the
     release.
   - Record how many task sections the first snapshot keeps. #319 should make it 21/21.
   - Then run one paired task, `personal --task pb-current-01 --variant 0 --execute` (2 runs). Check that both runs
     are scorable and that `setup_selected_initial_tab` is `true` for Kitsune.
3. **Run:**

   ```sh
   uv run --locked python scripts/run-full-suite.py --plan lite --kitsune-project artifacts/vendor/kitsune-<TAG> \
     --out artifacts/opus-subscription-<TAG>
   ```

   - **No retries:** an unscorable or incomplete track stops the suite with exit 3, and that is reported as it is.
   - **Session limit:** if the subscription session limit stops the suite, the incomplete track is rerun from its
     start once, in a fresh output directory, after the limit resets, and the report lists the retry.
4. **Audit** (offline):
   - every run has subscription authentication, `claude-opus-5-5` and no harness error;
   - there are no audit violations and no missing allowlisted tools;
   - personal runs assert the 1280×720 content viewport on both targets;
   - Kitsune's revision is unchanged across the suite.
5. **Analyse and report** (see below).

## Reported measures

Per track and per target, all runs included:

- success, under the primary contract (v2), strict v1, functional and safety;
- for coexistence, the main verdicts (`v3_user_view`, `v3_user_input`) and the protect-user-tabs arm as a third column;
- for external, MiniWoB full-reward successes, plus live completions and advisory answer matches, which are never
  graded.

On joint successes, as Kitsune/Playwright ratios:

- input (including cache reads and writes);
- output;
- MCP calls;
- elapsed time;
- the paired input-ratio median.

Also reported:

- per-tool calls, errors and result characters (`scripts/analyze-per-tool.py`);
- `browser_find` result characters, and truncated first snapshots on crowded pages;
- failures with their cause.

## Comparison with v0.7.0

| Track | v0.7.0 reference cohort | Comparable |
| --- | --- | --- |
| Personal 28 × v0–v1, gallery 21 × 2 layouts × v0 | The same units of [2026-10-26](../results/2026-10-26-opus-subscription-v0.7.0.md), `taskset-v3`: content identical to `taskset-v3.1` | Success and K/PW ratios on the same units: yes, as observations |
| Coexistence (frozen plan), external MiniWoB | [2026-10-28](../results/2026-10-28-new-tracks-v0.7.0.md), `taskset-v3.1` | Yes |
| External live tasks | 2026-10-28 | Qualitative only: the sites change |

v0.7.0 reference values on the `lite` units, recomputed from the 2026-10-26 runs. The same computation over all units
reproduces that report's 0.807 / 0.840 / 0.954.

| Track (lite units) | Units | Successes PW / K | K/PW input, joint successes | Paired input-ratio median | K/PW MCP calls |
| --- | ---: | --- | ---: | ---: | ---: |
| Personal v0–v1 | 56 | 56 / 56 | **0.815** | 0.824 | 1.002 |
| Gallery crowded v0 | 21 | 21 / 21 | **0.945** | 0.957 | 1.216 |
| Gallery isolated v0 | 21 | 21 / 21 | **1.018** | 0.981 | 1.065 |

Compare only with these values. Gallery's variant 0 alone differs a lot from all three variants (0.840 and 0.954).

Rules:

- Compare Kitsune/Playwright ratios across versions, not raw token totals. The ratio cancels part of the day-to-day
  model and harness drift.
- A difference between releases is an observation, not a release-improvement claim. A claim needs both versions run
  on the same day under the same plan, or a frozen A/B such as H310 or H323, and it goes through a `hypothesis` issue.
- The 2026-10-26 personal and gallery runs used the v0.7.0 setup path. On the new release, setup selects the initial
  tab first (#35). That is a harness step outside the agent's calls, but the report notes it.

## Limits

- One attempt, fixed process layout, no order counterbalancing: this is not a ranking.
- The `lite` plan has 21 units per gallery layout. One unit moves a layout's success rate by about 5 points.
- Live-site tasks depend on the pages as they are on the run date.
- Resource measures are taken under concurrent load and are not comparable with sequential runs.
