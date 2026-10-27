# Kitsune vs Playwright: shared-browser load comparison

## Result in one paragraph

For this **read-only tab-inventory saturation workload**, Playwright MCP's shared
HTTP deployment delivered higher throughput and lower p95 latency in **every one
of the 12 counter-ordered pairs**. Depending on concurrency, its ratio of median
throughput to Kitsune was 1.91–6.14×. Both completed all measured requests without
errors. Kitsune's CPU was concentrated in its per-client MCP processes, not in the
Firefox or bridge components. This is a deployment/workload result, **not** a
browser-automation, task-success or user-coexistence ranking.

## Protocol and provenance

- Independent **`stress-compare-v1` / `shared-browser-v1`**; not taskset-v3.1 and
  not pooled with the earlier Kitsune-only stress-v1 report.
- Kitsune: clean `5425050fe804de7ee8f7b3e1b77c83414495abba`, `v0.7.0-4-g5425050`.
- Playwright MCP **0.0.83**, Playwright **1.64.0-alpha-1790635538000**.
- Same private Firefox **156.0** executable, headless. Kitsune uses N independent
  stdio MCP processes + shared bridge; Playwright uses N independent Streamable HTTP
  MCP sessions + one shared server, `--shared-browser-context`, no `--isolated`,
  and a fresh private user-data-dir. One Firefox process-tree root per arm.
- Benchmark parent `8a74a1ebe4eb1b1fd992af5ad4dc6ccc50833d16`, dirty with this
  implementation (`taskset-v3-3-g8a74a1e-dirty`); no claim of running the exact v3 tag.
- Host: macOS 26.5.1 arm64, 8 logical cores, 8 GiB RAM (added 2026-10-27, not in
  the manifest: a fanless MacBook Air, Mac14,2, Apple M2 with **4 performance + 4
  efficiency cores**; Kitsune's scaling bends after 4 clients). Driver Python 3.13.5,
  psutil 7.2.2, Node v26.12.0, uv 0.7.20, web-ext 10.8.0. A post-run check of the
  unchanged Kitsune project environment reported Python 3.12.6, httpx 0.28.1 and
  MCP SDK 1.30.0 (distinct from the driver Python version in the manifest).
- Fresh browser/server per arm; stable two-tab baseline (`about:blank`,
  `about:blank#stress-shared-base`). A temporary third marker proves all sessions
  see creation and deletion. HTTP session IDs are distinct; an extra proof-only
  observer at N=1 is removed before measurement.
- 1, 2, 4, 8, 16, 32 clients, two repeats per target. 30 s load, 3 s warmup,
  3 s connected idle, 3 s cooldown; 10 s request timeout and 250 ms nominal
  sampling wait, `single-table-v1` resource probe.
- Repeat 1 ascends levels and alternates KP/PK; repeat 2 descends and reverses the
  target order at each level. Each concurrency has one KP and one PK pair.
- Measured command: `browser_tabs(action=list)`, one in flight per client, no think
  time. Native responses are not normalized to equal schema or size.
- Private evidence: **`artifacts/stress-compare/20261026T133444Z-11e4c249/`**.

```sh
uv run --locked python -m kitsune_benchmark stress-compare \
  --profile shared-browser-v1 --kitsune-project /path/to/pinned-kitsune --execute
```

### Completion and integrity

**24/24 arms, 12/12 valid pairs.** Kitsune: **79,460** measured requests;
Playwright: **200,548**; total **280,008**. Zero request errors/timeouts, resource
sampling errors, detected surviving owned processes, memory stops or cadence
warnings. All 24 arms passed shared-tab and one-Firefox-tree checks. Every measured
response matched the expected two-tab inventory. Warmup/setup calls are excluded.
Total wall time: **1102.3 s (18m22s)**. No LLM/model suite ran.

Key SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `configs/benchmarks/stress-compare-v1.json` | `86fef83df61d62ae8c28be59b12daafc28349189d0880581a07e616b26409e97` |
| `kitsune_benchmark/stress_compare.py` | `8cd9648ae5a479e2031f740ed604197f823efc1256e53a5f11df7667f97062c9` |
| `kitsune_benchmark/stress_http.py` | `0a89236dc029b0df4f9d3fb776c454d4f2be960c79cefe0154851a7f2e0f8697` |
| `kitsune_benchmark/stress_resources.py` | `97f27b089a51251ec10127e1592243db3bda14ec351ac9343636336d85108bc8` |
| Installed Playwright `coreBundle.js` | `cd6730be1bbcff00771a0fc1390f200306d28428ce68e305420ca623cb39cdeb` |

## Throughput and latency

Values below are medians of the **two run-level metrics**, not pooled request
percentiles. With two repeats, the median is the midpoint. These are descriptive
figures, not confidence intervals or a statistical significance claim.

| Clients | Kitsune req/s | Playwright req/s | PW/K throughput | Kitsune p95 ms | Playwright p95 ms |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 68.2 | 418.9 | 6.14× | 20.72 | 2.67 |
| 2 | 135.2 | 525.2 | 3.88× | 20.02 | 4.12 |
| 4 | 230.9 | 578.9 | 2.51× | 25.48 | 8.31 |
| 8 | 315.1 | 600.8 | 1.91× | 37.91 | 19.20 |
| 16 | 325.4 | 623.8 | 1.92× | 86.49 | 33.20 |
| 32 | 246.8 | 590.4 | 2.39× | 253.06 | 74.63 |

Both configurations flatten around 8–16 clients on this workload; Kitsune drops
more at 32. No tested level establishes a maximum supported connection count:
all 32 clients continued receiving valid replies. Model-driven agents usually
have think time and much lower request rates; these ratios are not everyday
agent task speedups.

### All repeats

Each cell: **req/s / p95 ms**. KP and PK identify chronological target order, not
which target is considered a baseline.

| Clients | Repeat 1 order | K repeat 1 | P repeat 1 | Repeat 2 order | K repeat 2 | P repeat 2 |
| ---: | --- | ---: | ---: | --- | ---: | ---: |
| 1 | KP | 70.9 / 19.76 | 427.9 / 2.50 | PK | 65.6 / 21.67 | 409.8 / 2.83 |
| 2 | PK | 136.2 / 19.56 | 520.1 / 4.18 | KP | 134.2 / 20.48 | 530.2 / 4.07 |
| 4 | KP | 247.2 / 21.91 | 582.7 / 7.84 | PK | 214.6 / 29.05 | 575.1 / 8.79 |
| 8 | PK | 330.5 / 35.32 | 610.4 / 19.30 | KP | 299.7 / 40.49 | 591.3 / 19.10 |
| 16 | KP | 326.1 / 86.15 | 626.1 / 33.53 | PK | 324.7 / 86.83 | 621.5 / 32.88 |
| 32 | PK | 239.3 / 255.32 | 552.9 / 85.73 | KP | 254.3 / 250.80 | 627.8 / 63.53 |

The paired PW/K throughput ranges, in client-count order, are 6.04–6.25×,
3.82–3.95×, 2.36–2.68×, 1.85–1.97×, 1.91–1.92× and 2.31–2.47×.
The headline column uses ratios of medians; the artifact also retains each paired ratio.

## CPU and RAM

CPU uses **100% = one core** and excludes the Python load generator/sampler.
It includes owned MCP, bridge, browser and launcher processes. RSS is summed
residency, not unique physical footprint, and is affected by shared pages and
macOS memory reclamation/compression. Peak and per-component data remain in the
resource artifacts. The table reports medians of per-run load means.

| Clients | K CPU % | P CPU % | K mean RSS MiB | P mean RSS MiB | K CPU ms/request | P CPU ms/request |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 95.1 | 118.1 | 655 | 919 | 13.97 | 2.82 |
| 2 | 189.5 | 140.6 | 817 | 953 | 14.03 | 2.68 |
| 4 | 367.7 | 154.0 | 908 | 804 | 16.01 | 2.66 |
| 8 | 654.3 | 162.0 | 1212 | 1060 | 20.82 | 2.70 |
| 16 | 689.1 | 161.9 | 1802 | 925 | 21.22 | 2.60 |
| 32 | 604.0 | 166.8 | 2849 | 803 | 24.53 | 2.84 |

CPU ms/request = observed owned user+system CPU during the load phase divided by
successful measured requests. This accounts for the very different throughput:
at one client Playwright uses more total CPU while doing about six times the work,
but less CPU per request. At higher concurrency, Kitsune uses both more total CPU
and more CPU per request. These are native stack costs, not model inference costs.

RAM does not grow monotonically in every arm and does not prove a leak. Kitsune
has lower mean RSS at 1–2 clients in this cohort; Playwright is lower at 4–32.
Fresh processes, host memory pressure and only two repeats limit generalization.

### Where the CPU went

At **16 clients**, median component CPU was:

| Component | Kitsune CPU % | Playwright CPU % |
| --- | ---: | ---: |
| MCP processes / shared MCP server | **628.7** | **108.0** |
| Bridge | 27.8 | N/A |
| Firefox tree | 32.6 | 53.9 |
| Launcher | approximately 0 | included in server |

Approximately 91% of Kitsune's owned CPU was in the **per-client MCP process
category**. This is evidence for profiling that path first, not proof of a specific
function-level cause. It does **not** support the explanation that Firefox or the
Kitsune bridge alone was consuming most of the CPU.

A concrete follow-up hypothesis: Kitsune's
`src/kitsune/bridge_client.py:271` at this revision calls top-level
`httpx.request(...)` for bridge requests. The installed httpx 0.28.1 top-level API
constructs a Client per call (`httpx/_api.py:102`), rather than reusing a persistent
client. Client construction/connection reuse is therefore worth profiling and
A/B testing. **No Kitsune code was modified and no causal optimization experiment
was performed here.** Header/policy/auth/lifecycle semantics must be preserved in
any candidate; rerun the same paired profile before claiming an improvement.

## Response sizes and measurement quality

- Native canonical JSON responses averaged **312.7–313.6 bytes for Kitsune** vs
  **157.9–159.3 for Playwright**. Text content was 194 vs 81 UTF-8 bytes. Request IDs
  account for some JSON length variation. These exclude HTTP/SSE headers/framing
  and stdio framing; they are not wire sizes. Richer native fields and formatting
  are part of the measured configurations, not proof that response size explains
  the throughput gap.
- Driver+sampler load CPU ranged **6.9–17.2% of one core** in Kitsune arms and
  **12.6–21.4%** in Playwright arms. This did not approach one fully busy core,
  but does not prove the generator has no scheduling/transport overhead.
- Across arms, median sample gaps ranged **268–326 ms**, maximum gap **641 ms**.
  There were 4,204 samples across all phases. Accumulated sampling wall time was
  109.22 s over 1028.29 s of collector lifetime (~10.6%); that is not sampler CPU
  time and is not subtracted from latency.
- Host available memory ranged **1084–2413 MiB** and swap used **5.43–6.62 GiB**.
  These are whole-machine values, not attributable to either tool. The machine
  was not a dedicated quiescent host, and thermal/background effects remain.
- Private headless profiles, Firefox binary, tab URLs/count, load and observer are
  shared conditions. Internal transport, process layout, native focus semantics,
  launch-default geometry and response schemas are **not** forced identical.
  No content viewport equality, live-page correctness or screenshot equivalence
  is asserted. This task has no DOM/layout/rendering workload.
- Closed-loop saturation has coordinated omission. There is no fixed arrival
  rate, queueing SLO, connection churn, soak endurance or same-tab concurrent-write
  test. Findings should not replace the model task/coexistence benchmark results.

## Excluded preparation and failed startup evidence

The first fixed-profile attempt, `20261026T132757Z-12d4fda5`, stopped before any
measured arm completed because a Kitsune initialization probe failed. A dedicated
reproduction, `20261026T133123Z-a08d6916`, preserved `extension_disconnected` replies
and bridge logs showing a transient generation-1 connection/disconnection before
normal generation-2 readiness. The initial harness had accepted the transient
socket as ready. The comparison harness was corrected to require extension
hello/version plus one stable generation for a second; it does not retry measured
requests. The complete run above is a fresh run after that correction.

Earlier custom smokes also corrected setup-only tab-URL settling and HTTP Host
validation, and checked 32 clients. The post-fix startup check
`20261026T133344Z-7cbae19f` passed six short arms. **None** of these attempts, short
checks, the earlier Kitsune-only stress report, or its pre-publication probe
experiment are pooled into the 280,008 measured requests above. All raw evidence
is retained privately.

## Reuse

The fixed profile is available through `stress-compare --profile shared-browser-v1`.
For a future authorized model suite, add **`--stress-comparison`** to
`scripts/run-full-suite.py`; it replaces, rather than duplicates, the Kitsune-only
stress prelude. Taskset-v3 scores and denominators remain unchanged.
See [comparison protocol](../stress-comparison.md) for safety and metric definitions.
