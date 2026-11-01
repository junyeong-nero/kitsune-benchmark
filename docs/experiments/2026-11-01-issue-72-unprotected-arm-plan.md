# Viewed-tab hold baseline: the unprotected Kitsune arm on the lite units (#72) — run plan

[Results index](../results/README.md) · [Running guide](../running.md) ·
[Coexistence track](../coexistence.md#unprotected-user-tabs-outside-the-frozen-scope-a-kitsune-arm) ·
[Release cohort protocol](2026-10-29-release-cohort-protocol.md)

This plan is committed before the run. Nothing in it has been executed yet.

## Question

On Kitsune main `514b5b7` (decline cohort, 2026-11-01, #75):

- held personal units cost 1.385× Playwright's input, against 0.841× on the units without a hold;
- coexistence verdicts matched v0.7.1, which had no hold (`v3_user_view` 28/28, `v3_user_input` 3/3).

So no benchmark score yet shows what the viewed-tab hold changes. This run measures Kitsune on the same lite units
with both user-tab protections off (`KITSUNE_PROTECT_USER_TABS=0 KITSUNE_HOLD_VIEWED_TAB=0`, the #58 arm). It records
what the hold costs and what it buys, before kitsune#393 changes the model.

## Scope (87 Kitsune runs, no Playwright)

`scripts/run-full-suite.py --plan unprotected-lite` runs these entries, each as one Kitsune process
(`--unprotected-user-tabs --targets kitsune`), in this order:

| Entry | Child command | Units |
| --- | --- | ---: |
| `personal-v0-unprotected`, `personal-v1-unprotected` | `personal --all --variant 0/1` | 56 |
| `coexistence-user-seeded-unprotected` | `coexistence --all-personal --variant 0` | 28 |
| `coexistence-typing-v{0,1,2}-unprotected` | `coexistence --task co-typing-01 --variant 0/1/2` | 3 |

Each entry has the same child arguments as the lite plan's entry of the same name without `-unprotected`
(`tests/test_full_suite.py` checks this). Gallery, external and the protect arm are not run. The elicitation policy
stays `decline`, as in the baseline. With both protections off, Kitsune should hold nothing, so the policy should not
matter. Holds are still recorded, and any hold that remains is itself a finding.

## Pins

| What | Value |
| --- | --- |
| Kitsune | Current main, in a clean clone at `artifacts/vendor/kitsune-main-<sha>`. If main is still `514b5b7`, reuse `artifacts/vendor/kitsune-main-514b5b7`: the comparison is then on the same revision |
| Benchmark | This branch merged into `main`. The code differs from the baseline's `869551c` (`taskset-v3.1.1-31`) only by the arm option and this plan. Default runs are unchanged |
| Harness / model | Claude Code `2.1.303`, `--harness claude` (subscription), `claude-opus-5-5` medium |
| Elicitation | `decline` |

## Command

Preflight (no model calls):

```sh
uv run --locked python -m kitsune_benchmark doctor --json
uv run --locked python -m unittest discover -s tests
K=$PWD/artifacts/vendor/kitsune-main-<sha>
git -C "$K" status --porcelain    # must be empty
```

The run consumes subscription usage, so start it only when the run is authorized:

```sh
uv run --locked python scripts/run-full-suite.py --plan unprotected-lite \
  --kitsune-project artifacts/vendor/kitsune-main-<sha> --out artifacts/opus-subscription-main-<sha>-unprotected
```

- `suite-manifest.json` records `plan: unprotected-lite`, the Kitsune revision and `elicitation: decline`. Each
  Kitsune run's pair manifest records `kitsune_env`, and summaries carry `unprotected_user_tabs: true`.
- An unscorable or incomplete entry stops the suite with exit 3 (no retries). After a session limit, rerun the
  incomplete entry once from its start, in a fresh output directory, as in the release protocol (#69).
- Plan only, no model calls: run any child command without `--execute`. For example,
  `uv run --locked python -m kitsune_benchmark personal --all --unprotected-user-tabs --targets kitsune` prints
  `planned_model_runs: 28` and `unprotected_user_tabs: true`.

## Comparison with the `514b5b7` decline cohort

The baseline is `artifacts/opus-subscription-main-514b5b7-merged` (lite, decline, Kitsune `514b5b7`). Match the
units by (entry without `-unprotected`, task).

```sh
uv run --locked python scripts/analyze-release.py artifacts/opus-subscription-main-<sha>-unprotected > review-unprotected.md
```

The review gives the audit, Kitsune outcomes per group, and holds per entry (expected 0). It shows no
Kitsune/Playwright ratios, because the arm has no Playwright runs. `--compare` would share no units, because the
entry names differ. Compare these, per group, with the baseline's default-Kitsune column:

| Measure | Unprotected run | `514b5b7` baseline |
| --- | --- | --- |
| Success (primary v2), personal and coexistence | `by_target.kitsune.successes` per entry | the same entries without `-unprotected` |
| K/PW input on formerly held units | unprotected Kitsune `usage.input_tokens` / baseline Playwright input | baseline Kitsune / baseline Playwright (1.385 personal) |
| K/PW input on the other units | same, on units without a baseline hold | 0.841 personal |
| `v3_user_view` | `by_target.kitsune.successes_v3_user_view` (coexistence user-seeded) | 28/28 |
| `v3_user_input` | `by_target.kitsune.successes_v3_user_input` (`co-typing-01`) | 3/3 |
| Misdirected characters | `by_target.kitsune.misdirected_chars` | 0 (Playwright 429) |
| Writes to user tabs | successful write calls on a starting tab (below) | the calls held instead (`holds`, `declined_writes`, `redone_after_decline`) |

- **Formerly held units:** the baseline's Kitsune runs with `benchmark_evaluation.holds.holds > 0`. These are the
  11 personal units of #75; the coexistence units are counted the same way. Both ratios use the baseline's
  Playwright input as the denominator. Report them on units where both baseline Playwright and unprotected Kitsune
  succeeded, plus the paired median.
- **Writes to user tabs:** in each Kitsune run's `kitsune-session-evidence.json`, count the `tab_calls[i]` that
  write (click, type, fill_form, select_option, press_key, hover, drag, navigate) and did not fail, whose current tab
  (the `active` entry of `snapshots[i]`) is one of `initial_tabs`. Report the safety fields beside this count:
  `safety_pass`, `forbidden_actions`, `seeded_tabs_preserved`, and the user-view transitions in `user_view`. This
  count is not scripted yet; state how it was computed.
- Elapsed time and CPU/RSS are not comparable. The baseline's personal entries ran Playwright and Kitsune in
  parallel, while this arm runs Kitsune alone.

## Reporting

This is an **observation**, not a claim. The release protocol's rule applies: a claim needs both arms run on the
same day under the same plan, and it goes through a `hypothesis` issue. Here the ratio's Playwright denominator comes
from another day, so it does not cancel day-to-day model and harness drift. Report the unprotected arm as its own
column, and never pool it with default-Kitsune totals. The report goes in `docs/results/` and links #72 and #75.
