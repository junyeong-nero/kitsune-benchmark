# Shared-browser stress comparison

**`stress-compare-v1` / `shared-browser-v1`** compares two supported deployments,
without model calls:

```text
Kitsune:    N stdio MCP processes -> one bridge -> one Firefox
Playwright: N HTTP MCP sessions  -> one MCP server -> one Firefox
```

This is an end-to-end deployment comparison, not a pure browser-engine or
transport microbenchmark. The process count and transport intentionally follow
those deployments. Both use the same private Firefox executable, headless mode,
and one shared browser context. They do not attach to everyday profiles.

It is independent of both the graded **taskset-v3** and Kitsune-only **stress-v1**.
Do not pool their data: the comparison adds HTTP sessions, a two-tab baseline,
sharing proofs, response sizes, observer metrics and a different order/repeat plan.
No taskset-v3.1 tag is needed or created.

## Run

Existing setup: `uv sync --locked`, `npm ci --ignore-scripts`,
`npm run setup:firefox`, and a clean Kitsune checkout (default `../kitsune`).

```sh
# No browser/model execution.
uv run --locked python -m kitsune_benchmark stress-compare --profile shared-browser-v1

# Fixed paired run, about 20 minutes on the observed machine, no model calls.
uv run --locked python -m kitsune_benchmark stress-compare \
  --profile shared-browser-v1 --kitsune-project /path/to/pinned-kitsune --execute

# Short custom integration check; not the fixed-profile cohort.
uv run --locked python -m kitsune_benchmark stress-compare \
  --clients 1,2 --duration 2 --idle 0.5 --warmup 0.5 --cooldown 0.2 --execute
```

In an otherwise authorized full-suite invocation, **`--stress-comparison` replaces**
the Kitsune-only pre-model stress track with this comparison. It does not run both.
The default stays Kitsune-only `stress-v1`; `--skip-stress` remains an explicit
opt-out and is mutually exclusive with `--stress-comparison`. A failed, stopped or
incomplete stress result stops the suite before model usage. The separate `stress`
summary never affects task-success denominators.

## Frozen plan

`configs/benchmarks/stress-compare-v1.json` declares:

- 1, 2, 4, 8, 16, 32 concurrent clients, two repeats per target per level.
- 3 s warmup, 3 s connected idle, 30 s measured load, 3 s cooldown after each arm.
- 10 s request timeout; 60 s initialization/probe timeout; 250 ms sampling wait.
- Memory stop thresholds: host available <512 MiB, owned summed RSS >4096 MiB.
- 24 arms, executed sequentially; 12 complete comparison pairs.
- Repeat 1 ascends levels, alternating KP/PK by level (K=Kitsune, P=Playwright).
  Repeat 2 descends levels and reverses each level's target order. Every concurrency
  therefore has one KP and one PK pair. There is no concurrent competing arm.

The fixed profile refuses overrides; custom plans are labeled separately. Two
repeats support descriptive medians/ranges, not strong statistical claims.
Future workload, topology or measurement-contract changes require a new comparison
protocol; schedule/limit changes require a new profile. Keep current task scores
and their frozen taskset independent.

## Topology and readiness verification

Playwright MCP 0.0.83 is launched with `--shared-browser-context`, **without
`--isolated`**, and with a private `--user-data-dir`, explicit Firefox binary,
loopback bind and private HTTP port. In this pinned build, `--isolated` creates
per-client contexts even when the browser process is shared. The HTTP client uses
one independent MCP session and persistent TCP connection per worker; it does not
follow redirects, use proxies, reconnect or retry failed requests. The HTTP Host
header follows the advertised `localhost:<port>` endpoint while connecting to
127.0.0.1, retaining the server's host validation.

Each arm starts a fresh browser/server. The harness:

1. For Kitsune, waits for extension hello/version and an unchanged connected
   generation for a full second (bounded to 40 s). A transient web-ext startup
   connection alone is not readiness.
2. Initializes all client sessions, then opens two marker tabs from one session.
   Every session must see the shared starting tab and both markers. Setup-only
   bounded polling handles a new tab's URL becoming visible asynchronously.
3. Closes the probe marker and verifies the same two-tab baseline in all sessions:
   `about:blank` and `about:blank#stress-shared-base`. This preserves Kitsune's
   user-owned initial tab instead of bypassing its close protection.
4. Checks distinct HTTP session IDs (stored only as hashes), and exactly one owned
   Firefox process-tree root. At concurrency 1, a second proof-only observer is
   disconnected before warmup/measurement.
5. During measured load, validates **every response** against the two-tab baseline;
   verifies it again afterwards in a separate `verify` resource phase.

These are functional checks for trusted local tools, not a security boundary.
Logical tool-selected tabs and native focus semantics can differ. This track does
not test foreground interference, same-tab writes, isolation between agents or
content viewport equality. Launch defaults for geometry are not equalized; there
is no layout/screenshot workload, and RAM is a whole-deployment observation.

## Metrics and interpretation

Each worker sends `browser_tabs(action=list)` in a closed loop, at most one request
in flight, no think time. Startup, warmup and topology evidence are outside load.
Latency ends when the native MCP response has been received/decoded, before
benchmark validation and size serialization; that overhead still affects achieved
throughput. Throughput includes the completion tail beyond the nominal window.

- Per-request p50/p95/p99, successes/errors, throughput and per-client counts.
- Idle/load CPU and RSS, totals and components. CPU 100% = one core; summed RSS
  may double-count shared pages and is not unique physical memory.
- Mean canonical compact JSON response bytes and text-content UTF-8 bytes.
  These are **not wire bytes**: HTTP/SSE headers/framing and stdio framing are excluded.
  Native response schemas/content are not padded to equal size.
- Driver+sampler CPU during load, and its RSS before/after load (not peak), separate
  from owned deployment totals. This exposes potential load-generator bottlenecks.
- Actual resource sampling gaps and cadence warnings, plus sampling wall-time
  overhead (not sampler CPU time). Sampling errors/surviving owned processes fail
  the arm; a cadence warning is reported separately.
- Per-target run-level medians/ranges and K/P ratios for **complete valid pairs only**.
  Do not pool request percentiles across repeats or call an incomplete sweep complete.

There are no measured-request retries. Errors/timeouts stop the sweep after cleanup;
startup errors remain separate failed evidence. Memory safety stops are host limits,
not proof of a software connection limit. Peaks can occur between samples. Host
swap/available memory include unrelated applications.

Runs since 2026-10-27 also record the [`host-diagnostics-v1` probe](stress.md#host-diagnostics-host-diagnostics-v1):
host model and core types in the manifest, a CPU canary before and after each arm
(`host_canary`, warning `host_cpu_slower`) and whole-machine CPU over each load window
(`host_cpu`). It changes no schedule or metric. A Kitsune arm keeps six or more cores
busy and a Playwright arm under two, so on a fanless host the canary shows whether the
heavier arm slowed the next one. Compare only runs with the same host probe.

This is a saturation test with coordinated omission, not fixed-arrival-rate latency
or normal LLM-agent behavior with think time. It cannot establish general navigation,
DOM extraction, screenshot, user coexistence or task-success superiority. Compare
new release candidates in fresh, paired runs with the same host/runtime/profile;
do not append one tool's new results to another tool's historical numbers.

## Evidence

`artifacts/stress-compare/<run-id>/` contains `manifest.json`, `summary.json`, and
per-arm directories with `topology.json`, native client metadata, initialization
probe responses, `requests-*.jsonl`, resource samples/summaries, and diagnostic logs.
Manifests record source/runtime identities and instrumentation/dependency hashes;
source/hash changes during a sweep invalidate its overall result. Raw evidence
stays private and gitignored. Review before sharing.

[First paired report](results/2026-10-26-shared-browser-stress-comparison.md)
includes all repeats, resource attribution, response sizes, excluded startup
failures, and limitations. No model benchmark was executed to produce it.
