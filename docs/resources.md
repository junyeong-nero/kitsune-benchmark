# Local process resource collection

[Documentation index](README.md) · [Running guide](running.md) · [Results](results/README.md)

`run` and paired `smoke`, `benchmark`, `personal`, `gallery`, and `coexistence` executions sample local
resources with pinned psutil 7.2.2. This document covers process CPU/RAM, not
model tokens or subscription billing; see the
[usage inspection guide](running.md#inspect-outcomes-and-usage) for those fields.
Use `uv sync --locked` / `uv run --locked ...`; the Python runtime is no longer
standard-library-only. No model API SDK has been added.

## Scope

The collector receives explicit process roots, identifies each by PID **and
creation time**, and follows descendants. Previously observed children continue
to be followed after reparenting. It does not enumerate unrelated app command
lines or collect environment variables. The observer process is outside owned
roots, so its own RSS/CPU are not charged to the target process totals.

Roles: `harness`, `mcp`, `bridge`, `browser`, and `browser_launcher`. Role assignment
for discovered descendants uses process names/inheritance; this is a heuristic,
not a claim of perfect executable attribution. Kitsune's web-ext launcher is
reported separately as test infrastructure. Owner tags separate Playwright and
Kitsune even when both have processes alive in the paired setup.

The per-run collector includes Codex and descendants. For Kitsune, it also
receives the separately started private bridge/web-ext process roots. Those
external roots are expected to remain alive until the pair ends, so they are
not mislabeled as leaked processes at the end of an individual agent run.
The pair-level collector measures their full lifecycle and checks final cleanup.

## Files and metrics

Each run and each paired-track directory contains:

- `resources.jsonl`: timestamps, phase, PID/creation-time/parent/name/state,
  role/owner, RSS bytes, CPU user/system counters and deltas, one-core CPU
  percentage, and aggregate groups.
- `resource-summary.json`: sampled peak RSS, time-weighted mean RSS,
  observed CPU user/system deltas, peak process count, sample/error counts,
  collector wall-time overhead, and live identities at the end.

Groups include `all`, `owner/<target>`, and `component/<target>/<role>`, plus
`phase/<phase>/<group>`. Per-run phases are `baseline`, `task`, `cleanup`.
Pair phases additionally include `setup`, `ready`, `task_playwright`, and
`task_kitsune`. Phase transitions force boundary samples. Normal interval is
one second; each record has the actual elapsed timestamp.

System context records total/available RAM, swap used, and logical CPU count.
These are machine-wide reference values affected by unrelated applications;
they must not be presented as target-only resource consumption. No dedicated
macOS memory-pressure or compressed-memory metric is collected.

Means use left-rectangle time integration between observations. Per-component
means cover observed component windows, not a complete inferred process lifetime.
Existing processes' CPU counters are baselined when first observed; a newly born
process's initial observed CPU is included. The `cpu_percent_one_core` value
may exceed 100% for multithreaded work.

## Suite cost aggregates

Personal, gallery and coexistence all use the same pair/per-run collectors.
`by_target.cost_metrics` in suite summaries (and offline analysis) reports task
resources for all attempts, successful tasks, same-pair joint successes, explicit
failures, and unscored/unknown attempts separately. `resources_task` contains:

- `observed_cpu_sec`: summed user + system CPU deltas, with reporting coverage;
  `observed_cpu_sec_per_measured_task` divides by measured tasks in that scope
  (successful tasks in `successful_tasks`), not by unobserved attempts.
- `sampled_peak_rss_bytes`: maximum of task-window sampled peaks;
  `mean_task_sampled_peak_rss_bytes`: arithmetic mean of those task peaks.
  Peaks are not summed across sequential tasks or divided by success count.
- `time_weighted_mean_rss_bytes`: task means weighted by each observed
  `duration_sec`, not a mean of means; `rss_observed_duration_sec` is its denominator.
- Counts of missing resources and of runs with peak/mean RSS. No observations
  yields null. Missing or zero-duration means are not zero memory consumption.

`pair_lifecycle.setup` and `.ready` use owner-filtered pair phase buckets, never
pair `all` or overlapping pair task phases. New pairs additionally record
`timing.kitsune_cold_start_setup_sec` (launch/bridge/browser readiness wall time),
aggregated as `pair_lifecycle.cold_start_setup_elapsed_sec` for Kitsune only,
even when the pair stops before the Kitsune task runs.
The one-second ready sleep is outside that setup timer; ready-phase sampled
resources cover this idle wait and writing the first target's session config.
Fixture seeding is part of per-run `relay_setup_sec`, inside the task window.
An already-running browser/bridge therefore has nonzero measured warm-ready
RSS/CPU, not a zero-cost assumption. Per-run task windows include those external
roots while the agent runs, as well as harness/MCP/relay work.

These are **not a cold-versus-reused-session experiment**: every pair starts a
fresh private Kitsune browser/bridge. Playwright launches inside the per-run
window; relay setup diagnostics capture fixture/browser preparation but do not
isolate every launcher/startup cost. `timing.relay_setup_sec` and
`elapsed_minus_relay_setup_sec` separate known relay setup from remaining elapsed
only; the latter is not pure warm agent time. There are no existing general
`setup_seconds`/`agent_seconds` run fields. Readiness sleeps and native RPC durations
are nested diagnostics, never added to setup/elapsed totals. Task-window resources
cannot currently be split at relay setup boundaries. Old runs without inline
pair phases can be analyzed from their existing `resource-summary.json`; absent
files/fields remain missing, and cold-start wall time is unavailable historically.

## Interpretation and limits

- **Summed RSS can double-count shared memory.** It is not PSS, USS, or macOS
  physical footprint. Use absolute bytes/MiB rather than RAM percentage as the
  primary metric.
- Peaks are **sampled peaks**, not guaranteed instantaneous maximums.
- Short-lived children and final CPU tails between observations may be missed.
  New orphaned children that were never observed cannot be recovered reliably.
- Sampling permission/race failures are exposed as counters; do not treat a
  degraded measurement as complete resource coverage.
- CPU percentages and totals are local. Remote GPT inference RAM/CPU/GPU is
  not measured.
- End-of-run live process lists are observations, not automatic proof of a
  leak. Externally managed roots are listed explicitly. Final pair cleanup is
  the relevant leak check for the private Kitsune browser/bridge.
- Pair-level `all` includes idle Kitsune resources while Playwright executes.
  For target comparisons use each **per-run** summary or filter by owner.
- Timing/startup asymmetry and fixed order remain across the current tracks;
  resource collection does not turn a single pair into a fair leaderboard.
- Personal-track process scope includes its stdio relay and native browser
  setup/readiness/inventory work. This is instrumented session-task execution,
  not directly comparable to older smoke/MiniWoB resource windows without that
  relay. Hidden work is counted separately in the personal evaluation but is
  still included in raw elapsed time and sampled process resources.

## Observed validation

First historical paired `gpt-6.1-sol` smoke with collection:

`artifacts/smoke/20261018T080844Z-2d61acf8c1/`

Both runs completed unscored. The pair captured 64 boundary/periodic samples,
reported zero sampling errors, and no unexpected live processes at final stop.
All expected component groups were present, including the separately started
Kitsune bridge/browser/launcher. These numbers are setup validation, not a
resource efficiency ranking. See the [historical smoke report](results/2026-10-18-smoke.md).

The [2026-10-19 personal report](results/2026-10-19-personal-current-page.md)
contains a later `gpt-6-luna` one-task pair with per-run task-phase resources,
53 pair-lifecycle samples, zero sampling errors and no unexpected survivors.
Its relay setup/inventory overhead is explicitly separate from agent calls;
this does not remove startup/order/sampling confounders.

## Tests

```sh
uv run --locked python -m unittest discover -s tests -v
```

Coverage includes time weighting, CPU baselines, PID reuse, owner separation,
process-name attribution, permission failures, actual child-process sampling,
private file modes, and exclusion of the observer process.
