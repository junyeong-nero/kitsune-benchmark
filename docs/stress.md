# Model-free shared-browser load test

`stress` runs N independent stdio MCP processes against **one private Kitsune bridge
and one private headless Firefox**. There are no agents, inference calls, API keys,
or subscription usage. It never attaches to your daily browser. Kitsune is the
only target; this is not a Playwright comparison. For fresh paired evidence, use
the independent [shared-browser comparison protocol](stress-comparison.md),
`stress-compare-v1` / `shared-browser-v1`; do not pool the two tracks.

## Run

Use the existing setup (`uv sync --locked`, `npm ci --ignore-scripts`,
`npm run setup:firefox`) and the sibling `../kitsune` checkout, or specify
`--kitsune-project /absolute/path`.

```sh
# Validate and show the plan; no processes launched.
uv run --locked python -m kitsune_benchmark stress

# Small integration check.
uv run --locked python -m kitsune_benchmark stress --execute \
  --clients 1,2 --duration 2 --idle 0.5

# Fixed release benchmark: 18 levels, no model calls (roughly 15 minutes; host-dependent).
uv run --locked python -m kitsune_benchmark stress --profile release-v1 --execute

# Custom exploration; not labeled as release-v1 results.
uv run --locked python -m kitsune_benchmark stress --execute \
  --clients 1,2,4,8,16 --duration 30 --idle 3 --interval 0.25 --timeout 10
```

Start small: each client is a real MCP process and consumes RAM. Concurrency is
bounded to 128, at most 16 levels. Repeated levels are allowed (`--clients 4,4,4`).
Each level creates a fresh browser/bridge, connects clients, performs initialize
and a probe, then repeated warmup requests (default 3 seconds), measures
connected-idle resources, then starts workers together. Clients are launched sequentially and initialized concurrently; this
is **not** a simultaneous cold bridge startup/race test.

## Versioning and release integration

**`stress-v1` is independent of `taskset-v3`.** Adding this performance track does
not alter task requests, fixtures, graders, or their score denominators; do not
create `taskset-v3.1` just for this addition. A report names both the graded taskset
and stress protocol/profile, plus the actual Kitsune source revision. No git tag
is created by this tool.

`configs/benchmarks/stress-v1.json` fixes `release-v1`:

- 1, 2, 4, 8, 16, 32 clients; three repeats, forward / reverse / forward.
- Per level: 3 s warmup, 3 s connected idle, 30 s load; 3 s cooldown between levels.
- 10 s request timeout and 250 ms resource sampling.
- Stop below 512 MiB host available memory or above 4096 MiB owned summed RSS.
- Clean committed Kitsune checkout required; source identity checked before/after levels.

These order choices are predeclared, not fully counterbalanced across three repeats.
Published measurements use the `single-table-v1` resource probe. It enumerates
process ancestry once per sample, verifies PID/create-time identity, and records
only owned processes. The graded tracks keep their existing collector. Check both
the probe name and instrumentation hashes when comparing artifacts; the
[pre-publication diagnostic run](results/2026-10-26-kitsune-stress-v1.md#pre-publication-diagnostic-run-excluded)
had the proposed version labels but a different, intrusive probe, and is not part
of the published cohort.

The profile cannot be combined with workload overrides. Custom runs record their
full settings but must not be pooled with the fixed profile. Change workload,
measurement semantics or topology under a new stress protocol; use a new profile
ID for changed concurrency/duration/repetitions or safety limits. Do not silently
edit the frozen release-v1 settings after publication. Instrumentation corrections
that alter numerical results require a new protocol revision and rerunning both
compared builds. Earlier ad-hoc smoke runs predate stress-v1 and are not pooled.

`scripts/run-full-suite.py` runs this profile **once before graded model tracks**,
never alongside them. A stress failure, resource stop, or invalid summary stops
the suite before spending model quota. The normal model authorization flags still
apply to the full suite; use the standalone `stress` command for model-free work.
`--stress-comparison` selects the independent Kitsune/Playwright comparison instead
of this prelude (not both). `--skip-stress` is the explicit opt-out (recorded in `suite-manifest.json` and
`suite-summary.json`). Stress repeats do not depend on the graded `--attempts` flag.
Stress evidence is a separate `stress` field, never a task-score entry. Passing
stress is not a new grading criterion for existing personal/gallery tasks.

For each release, keep the same machine, Firefox/runtime, profile and environment;
run baseline and candidate afresh and report each repeat and run-level median/range.
Do not make a regression claim against old single-run or different-machine figures.
A safety stop is **an incomplete measurement on this host**, not a discovered
software connection limit. Publish completed levels and the stop reason, not a
fabricated result for unattempted levels.

## Workload and measurements

Each client repeatedly calls `browser_tabs` with `action=list`, with one request
in flight per client and no think time. This exercises the MCP/bridge/extension
path without external websites, changing content, or model delays. The browser
starts at about:blank. It measures lightweight control traffic, **not** navigation,
screenshots, DOM extraction, or a realistic mixed workload.

- End-to-end request latency: nearest-rank p50/p95/p99, all attempts and successes
  separately; includes stdio, bridge, browser and scheduling delay.
- Successful requests/second, attempts, error rate, error categories, per-client
  attempt counts (to spot starvation).
- Connected-idle and load CPU/RSS: totals and components (MCP, bridge, browser and
  launcher), plus raw process samples. CPU is one-core normalized: 100% means one
  fully busy core, and totals can exceed 100%. RAM is bytes of summed RSS, not
  unique physical memory; shared pages can be counted more than once.
- Timeout/EOF ends that client's stream rather than recycling late responses.
  A level with request errors, sampling errors, detected surviving owned processes,
  or no measured requests for a client stops the remaining sweep and exits 3.
  A sampled memory safety stop also exits 3 (`status=stopped`), including during
  setup. Safety thresholds are not hard OS limits; a brief spike can precede a sample.
  Prerequisite/setup errors exit 2. Ctrl-C tears down
  owned groups after outstanding bounded requests return.

This is a **closed-loop** saturation test: clients wait for replies before sending
again. It does not hold a fixed arrival rate, and it has coordinated-omission bias
relative to an open-loop workload. Request completion may extend beyond the load
window by up to the request timeout; throughput uses actual elapsed time including
that tail. Warmup/setup are excluded from latency samples. Short runs and p99 with
few samples are only integration checks, not stable performance conclusions.

The Python load generator/sampler is excluded from owned-process totals; host
context is recorded separately and includes unrelated apps. Logging and generator
CPU can become bottlenecks. Memory samples can miss brief peaks and short-lived
processes; component means cover observed lifetimes. Inspect sampling errors,
`sampler_wall_overhead_sec` (wall time, not CPU time), and `unexpected_alive_at_stop`
in the resource report. `load_sample_cadence` records actual median/maximum gaps;
`measurement_warnings` flags missing intervals or a maximum gap exceeding
`max(1 second, 4 × interval)`. The configured interval is a wait between samples,
not guaranteed cadence. Warnings do not turn a completed request into an error. Repeat longer runs on a quiet
machine before interpreting the scaling curve.

## Host diagnostics (`host-diagnostics-v1`)

Runs since 2026-10-27 record `host_probe: host-diagnostics-v1` in the manifest. It
changes no workload, schedule, safety limit or measured metric; it adds context for
reading them, because the same build measured on the same machine can differ by tens
of percent between runs:

- `manifest.json` `host`: model identifier, CPU brand, core types (performance and
  efficiency core counts on Apple Silicon), power source, `pmset -g therm` notes and
  load average. Eight logical CPUs can be four performance and four efficiency cores.
- Per level `host_canary`: a fixed single-threaded Python loop timed in the driver
  before the level's processes start and after they are gone (about 0.5 s each,
  outside warmup, idle and load), and its slowdown against the run's first canary.
  More than 15% slower adds the `host_cpu_slower` measurement warning: a slower or
  busier host (thermal limits on a fanless laptop, other applications), not a slower
  target. Wall time well above CPU time means the driver waited for a core; more CPU
  time for the same loop means a slower core.
- Per level `host_cpu`: whole-machine busy CPU over the load window, the driver's
  share, and the remainder after owned processes (`unowned_percent_one_core`), plus
  the same whole-machine figure over the connected-idle window
  (`idle_window_percent_one_core`). The remainder includes the machine's background
  (60–120% of one core on the reporting laptop with a terminal open) and is approximate:
  the owned window differs by milliseconds, owned CPU is sampled, and a calibration
  with 2 and 4 busy loops read about 50% of one core above their expected total. Read
  a large rise over the idle figure as interference, not a small difference.
- `summary.json` `host_canary`: the first canary, the largest slowdown and the number
  of levels with a warning.

Compare runs that have the same host probe. Earlier runs, including the published
2026-10-26 cohort, have none; no slowdown can be inferred for them after the fact.

## Artifacts

`artifacts/stress/<run-id>/` (private, gitignored):

- `manifest.json`: protocol/profile, schedule, source revisions, instrumentation/config
  SHA-256, runtime/browser versions, OS/CPU/RAM context (no hostname or credentials).
- `summary.json`: completed levels, overall status, valid-repeat counts and run-level
  median/min/max aggregates; preserved on failure. Never treat a partial sweep as
  a completed release profile, and never pool its request latencies across repeats.
- `<level>-clients-N/summary.json`: latency, throughput, errors and idle/load resource metrics.
- `requests-<client>.jsonl`: per-request timing/error, no response bodies.
- `resources.jsonl`, `resource-summary.json`: samples and component/phase aggregates.
- `client-*.log`, `bridge.log`, `firefox.log`: diagnostics.

Do not publish private bridge-home files or raw logs without reviewing them.
Each level owns and cleans up its process groups. Private extension copies and
artifacts are intentionally retained for inspection; no source extension or user
configuration is edited.
