# Kitsune shared-browser stress: stress-v1 / release-v1

## Scope and provenance

Model-free, Kitsune-only load test. No Playwright comparison, agent inference,
subscription usage or API billing. This is a capacity observation on one machine,
not a Kitsune release-improvement claim or a long-running reliability guarantee.
The graded taskset stays **taskset-v3**; this is a separately versioned performance
track, excluded from personal/gallery success denominators.

- Kitsune: clean `5425050fe804de7ee8f7b3e1b77c83414495abba`,
  `v0.7.0-4-g5425050` (**not** the exact v0.7.0 tag used in the model report).
- Benchmark parent: `8a74a1ebe4eb1b1fd992af5ad4dc6ccc50833d16`, with the
  uncommitted stress implementation; manifest describes it as
  `taskset-v3-3-g8a74a1e-dirty`. It does not claim execution from the exact v3 tag.
- Protocol/profile: `stress-v1` / `release-v1`; resource probe `single-table-v1`.
- Host: macOS 26.5.1, arm64, 8 logical/physical cores, 8 GiB RAM.
- Firefox 156.0, Python 3.13.5, psutil 7.2.2, Node v26.12.0, uv 0.7.20.
- Fresh private headless Firefox, bridge and independent stdio MCP processes per
  level; each client continuously calls `browser_tabs(action=list)`, one in flight.
- Levels: 1, 2, 4, 8, 16, 32; three repeats in forward/reverse/forward order.
  Warmup 3 s, connected-idle 3 s, load 30 s, inter-level cooldown 3 s.
  Request timeout 10 s; nominal sampling wait 250 ms.
- Safety stops: host available memory <512 MiB or owned summed RSS >4096 MiB.
- Private evidence: `artifacts/stress/20261026T112108Z-ddefded3/`.

Reproduce on the same Kitsune revision and machine, after installing the private
Firefox and pinned dependencies:

```sh
uv run --locked python -m kitsune_benchmark stress \
  --profile release-v1 --kitsune-project /path/to/pinned-kitsune --execute
```

### Integrity

18/18 levels completed, three valid repeats per concurrency; **77,334 measured
requests, zero request errors/timeouts**, zero resource sampling errors and no
detected surviving owned processes. No safety stops or cadence warnings. Total
wall time from manifest to summary: 844.6 s (about 14m05s). Warmup probes are not
included in the request total. No model suite was executed in this experiment.

Key SHA-256 values (remaining dependency/instrumentation hashes in the manifest):

| File | SHA-256 |
| --- | --- |
| `configs/benchmarks/stress-v1.json` | `f444db6dcbc4c2f4d6c0a93dcd45ec8a05a4884bd5acec83c04cf8c245af7f49` |
| `kitsune_benchmark/stress.py` | `5747615b22138644134de28b69ed70068e8f468a42ba4332a087bef020149517` |
| `kitsune_benchmark/stress_resources.py` | `97f27b089a51251ec10127e1592243db3bda14ec351ac9343636336d85108bc8` |

## Load curve

Figures are **medians of three run-level metrics**, not percentiles pooled across
all requests. Ranges show the three run-level extrema. CPU includes owned MCP,
bridge, browser and launcher processes, on a **one-core basis** (100% = one core).
RSS is summed process RSS, not unique physical footprint; shared pages can be
counted more than once and macOS reclamation/compression affects residency.

| Clients | Successful req/s, median (range) | p95 ms | p99 ms | Mean CPU % | Mean RSS MiB | Max sampled RSS MiB across repeats |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 49.7 (43.8–68.7) | 30.8 | 44.0 | 94.2 | 368 | 1160 |
| 2 | 91.4 (78.7–124.8) | 30.0 | 38.2 | 187.6 | 445 | 1259 |
| 4 | 154.8 (135.0–185.8) | 35.3 | 45.9 | 367.2 | 694 | 1150 |
| 8 | 196.8 (183.4–220.3) | 62.7 | 93.1 | 546.6 | 851 | 1520 |
| 16 | 203.5 (192.6–233.0) | 137.9 | 186.0 | 576.1 | 1247 | 1531 |
| 32 | 145.1 (110.8–152.6) | 441.9 | 580.2 | 493.8 | 1813 | 2818 |

On this workload and host, going from 8 to 16 clients adds about 3.4% median
throughput while more than doubling median run-level p95. At 32, median throughput
falls about 28.7% from 16 and p95 rises about 3.2×. This suggests diminishing returns
around 8–16 **for this measured configuration**, not a proven bridge bottleneck or
maximum supported connection count. All 32 clients continued receiving replies.

### Repeats, without hiding variability

Each cell is successful req/s / p95 milliseconds. Repeat 2 ran the levels in
reverse; repeat 3 is not a fully balanced order design.

| Clients | Repeat 1 | Repeat 2 | Repeat 3 |
| ---: | ---: | ---: | ---: |
| 1 | 68.7 / 19.4 | 49.7 / 30.8 | 43.8 / 39.1 |
| 2 | 124.8 / 21.5 | 78.7 / 39.9 | 91.4 / 30.0 |
| 4 | 185.8 / 29.6 | 154.8 / 35.3 | 135.0 / 48.3 |
| 8 | 183.4 / 80.6 | 220.3 / 58.4 | 196.8 / 62.7 |
| 16 | 192.6 / 151.8 | 233.0 / 119.2 | 203.5 / 137.9 |
| 32 | 152.6 / 441.9 | 145.1 / 423.6 | 110.8 / 506.7 |

### Connected-idle resources

Medians of the per-run 3-second idle window, after warmup. Browser startup work
can still occur; these are not steady-state idle/soak measurements. In particular,
short idle RSS can exceed load RSS as pages are reclaimed later.

| Clients | Mean CPU % | Mean RSS MiB |
| ---: | ---: | ---: |
| 1 | 22.6 | 357 |
| 2 | 14.7 | 489 |
| 4 | 16.2 | 1099 |
| 8 | 15.6 | 1248 |
| 16 | 18.2 | 1029 |
| 32 | 10.9 | 1636 |

## Measurement quality and limits

- The machine was not a dedicated, quiescent benchmark host. It already used
  about 4.83 GiB of swap at start; sampled host swap ranged 3.92–5.79 GiB and
  available RAM 1038–2275 MiB. Those are whole-machine values, not attributable
  to Kitsune. They do not establish that swap activity caused any particular stall.
- The resource probe took 131.58 s of accumulated sampling wall time over 791.72 s
  of collector lifetime (all phases), about 16.6%. This is **not sampling CPU time**
  and is not subtracted from latency. The load generator/sampler competes for the
  host but is excluded from owned-process resource totals.
- Across levels, median load sample gaps were 272–470 ms; the maximum gap was
  927 ms. The configured 250 ms is a wait between samples, not guaranteed cadence.
  Raw samples total 3,121 across all phases. Sub-sample RSS peaks can be missed.
- A cadence warning is emitted if the maximum load gap exceeds
  `max(1 second, 4 × configured interval)`, or no intervals are observed. A warning
  is measurement-quality information, not a request failure or a software SLO.
- This closed-loop workload reduces offered load when replies slow; it does not
  measure latency under fixed arrival rate, navigation/DOM/screenshot workloads,
  same-tab correctness, connection churn, or a long-running soak.
- Runtime/host drift and order effects remain. Do not reuse this report as a clean
  release-regression baseline. Rerun both compared builds on the same machine,
  profile, resource probe and runtime, and show variability rather than a single
  winning number. No browser/tool ranking follows from this Kitsune-only result.

## Pre-publication diagnostic run, excluded

The first full attempt, `20261026T105646Z-15729521`, recorded the same proposed
`stress-v1` / `release-v1` labels **before the protocol was published**, but used
repeated per-process child-tree discovery. It made 59,862 successful requests with
no recorded errors. However, at 32 clients its load sample gaps reached 26.24 s,
and one 30-second load window had only four resource samples. Sampling wall time
was 654.7 s over 1000.2 s of collector lifetime. Its CPU/RSS precision and observer
interference were unsuitable for the intended release comparison.

That evidence is preserved, not overwritten, and **none of its requests or
resource figures are pooled into the tables above**. Its `stress.py` SHA-256 is
`076da686256320929ea5294d125672e7244c27622593d3cc085f9c81887dc13c` and it has no
`resource_probe=single-table-v1` manifest field. A stress-only batched process-table
probe was added before publication; the graded tracks' collector was not changed.
A separate 1/32-client five-second check (`20261026T112019Z-99940d66`) verified the
new cadence before the full rerun. That check is also excluded.

Future benchmark suites use the published profile plus `single-table-v1` and keep
this performance track separate from taskset-v3. See [the protocol](../stress.md)
for release integration and version-change rules. No new git tag was created.
