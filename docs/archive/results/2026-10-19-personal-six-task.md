# Personal browsing: six-task pilot and latency/token diagnosis

[Documentation index](../README.md) · [Reports](README.md) ·
[Optimization findings](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/optimization-findings.md)

**Scope:** all **six currently runnable** personal tasks, variant 0, one attempt
per MCP, on 2026-10-19. The other 18 catalog entries remain specification-only.
This is not all 24 tasks or a repeated/counterbalanced comparison.

## Experiment

- Requested model `gpt-6-luna`, reasoning `medium`, Codex CLI `0.163.0`.
- Playwright MCP `0.0.83`, web-ext `10.8.0`, same private Firefox 156 binary,
  separate headless profiles, synthetic test cookies and seeded tabs.
- Playwright first in every pair; no retries or model fallback.
- 180 seconds per agent run; no token-budget stopping.
- Native UI schemas/results and grader unchanged. Added private RPC timing/size
  and native catalog logs before this run; they do not enter the model context.
- **12 agent runs, six scorable pairs, CLI exit 0.** No quota-consuming retry,
  extra variant or post-optimization model run was performed.

This is a second experiment, separate from the earlier
[one-task report](2026-10-19-personal-current-page.md). Its source hash differs
because it includes the new diagnostics. Dated earlier reports remain unchanged.

## Aggregate results

| Metric, all six runs per MCP | Playwright | Kitsune |
| --- | ---: | ---: |
| Scorable runs | 6 | 6 |
| Overall successes under the current grader | 3 | 4 |
| Functional successes under the current grader | 5 | 6 |
| Safety/protocol failures | 2 | 2 |
| Reported input tokens, **including cached** | 688,757 | 692,948 |
| Cached input subset | 567,040 | 602,624 |
| Derived non-cached input | 121,717 | 90,324 |
| Output tokens | 3,153 | 2,771 |
| Reported reasoning output tokens | 55 | 58 |
| Agent MCP calls | 51 | 46 |
| Sum of instrumented agent-run seconds | 111.536 | 121.323 |
| Mean instrumented seconds per run | 18.589 | 20.221 |

**The initial one-task result did not generalize to a large token penalty.**
Across this pilot Kitsune input is **0.61% higher**, instrumented elapsed time
**8.77% higher**, and non-cached input **25.79% lower**. These are reported usage
comparisons, not estimates of subscription charges or remaining quota.

Do not compare successful-only totals from different task sets: Kitsune has four
successes and Playwright three. On the **same three jointly successful tasks**
(current page, handoff and safe form), input totals are **290,244 vs 288,006**
(Playwright vs Kitsune), elapsed totals **51.157 vs 53.390 seconds**, and both
have **18 agent calls**. This is still a tiny fixed-order sample, not a ranking.

## Per-task results

`F` = functional grading failure; `S` = safety/tab-preservation protocol failure.
Input includes cached input. Seconds include relay setup and instrumentation.

| Task | Overall result P / K | Input P / K | Seconds P / K | Agent calls P / K |
| --- | --- | ---: | ---: | ---: |
| `pb-current-01` | pass / pass | 56,841 / 85,853 | 11.729 / 17.350 | 3 / 5 |
| `pb-tabs-01` | F / pass | 73,635 / 102,463 | 16.030 / 18.580 | 12 / 9 |
| `pb-research-01` | S / S | 184,015 / 159,091 | 22.314 / 23.974 | 12 / 10 |
| `pb-account-01` | S / S | 140,863 / 143,388 | 22.035 / 25.379 | 9 / 9 |
| `pb-handoff-01` | pass / pass | 124,352 / 114,870 | 23.772 / 17.986 | 8 / 7 |
| `pb-safe-01` | pass / pass | 109,051 / 87,283 | 15.656 / 18.054 | 7 / 6 |

### Failure review

- **Product comparison, Playwright:** selected the correct product and saved its
  name **with a price/delivery explanation**. The exact-string grader accepts
  only the name, so this is a recorded functional failure. The request says to
  save the product name but does not explicitly say *only* the name. Treat this
  as a prompt/grader alignment issue, not evidence that the comparison was wrong.
  The historical grade has not been silently relaxed or rescored.
- **Research and account lookup, both MCPs:** saved the correct value, but opened
  linked detail pages in a seeded working tab and then returned. The protocol
  requires all seeded URLs to remain present at every sampled checkpoint and
  explicitly instructs opening additional sources in new tabs. Restoring the
  original URL later does not undo this failure. These are context-preservation
  violations, not accidental submission/deletion or incorrect answers.
- **Recoverable tool errors:** one Kitsune stale-ref click in account lookup and
  one Playwright invalid selector/ref in calendar form filling. Both recovered
  and saved the correct final data. The offline analyzer detects JSON-wrapped
  Kitsune `{error: ...}` results, not only MCP `isError` flags.

These cases limit interpretation of the 3/6 vs 4/6 score. Fix/version the
benchmark's intent and grading contract before using it as a quality ranking.

## Where the time and context went

| Diagnostic, totals across six runs | Playwright | Kitsune |
| --- | ---: | ---: |
| Measured relay session setup seconds | 10.379 | 31.958 |
| Agent native tool RPC seconds | 5.673 | 1.197 |
| Post-setup hidden inventory RPC seconds | 0.213 | 0.641 |
| Readiness sleep seconds, **inside setup** | 0.000 | 25.614 |
| Cached tab reads during setup | 0 | 236 |
| Hidden harness MCP calls | 98 | 335 |
| Agent tool-result text characters, one copy per reply | 30,199 | 18,196 |
| Agent tool-result text UTF-8 bytes | 33,891 | 20,500 |
| Config-enabled native tool definitions | 15 | 19 |
| Compact enabled schema characters | 11,260 | 16,869 |
| Compact enabled schema UTF-8 bytes | 11,260 | 16,875 |
| MCP initialize instruction characters | 0 | 0 |

Native RPC timers include local client/transport/server work, not only extension
execution. Response characters are not token counts, and one-copy result sizes
do not account for repeated model context. Schema sizes are serialized native
metadata matched to the configured allowlist, not a captured provider prompt.

The **21.579-second setup difference exceeds the entire 9.787-second elapsed
difference**. Most conspicuous readiness delay is a stale tab-list cache, not
slow click/type RPC: Kitsune's measured agent RPC time and total result text are
actually lower in this pilot. Remaining elapsed time includes model/network,
Codex startup/orchestration, cleanup and logging; it cannot be called pure model
time from these logs.

### Cache mechanism and independent intervention

Kitsune `newTab` returns an ID before navigation settles. A subsequent `getTabs`
can cache a transient URL list for **five seconds**. Asynchronous browser tab
updates do not invalidate that cache. The harness polls every 100 ms, repeatedly
receiving `_cached: true` until expiry. In the first full-pilot Kitsune setup,
40 cached reads occurred between the initial post-creation read and the eventual
fresh read; selection of the starting tab happened only after that wait.

A separate **no-model** experiment used fresh private Kitsune/Firefox instances
and changed only the owned temporary bridge cache TTL. Three trials per condition:

| Repeat | TTL 5: setup seconds / calls | TTL 0: setup seconds / calls |
| --- | ---: | ---: |
| 1 | 5.222 / 44 | 1.532 / 17 |
| 2 | 5.337 / 45 | 0.332 / 8 |
| 3 | 5.273 / 45 | 0.331 / 8 |

All six setups verified successfully. Median setup was **5.273 vs 0.332 seconds**.
The first TTL-0 sample was slower than the other two, so this is not a fixed
per-run savings promise. The source and real benchmark TTL were not changed;
TTL zero is a diagnostic intervention, **not** the recommended global fix.

In the same six probes, Kitsune's compact snapshot **never contained the article's
cancellation date**, whereas `browser_page_text` always did. The current snapshot
retains headings/forms/controls but drops ordinary paragraph text. This explains
why a one-page reading-and-writing task can need both a text read and a separate
ref-bearing UI observation. A lean combined observation is a concrete follow-up,
not a measured token reduction yet.

Full source references, priorities, logging limitations and acceptance checks:
[optimization findings](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/optimization-findings.md).

## Reproduction and raw evidence

Original model execution, explicitly quota-consuming:

```sh
uv run --locked python -m kitsune_benchmark personal --variant 0 --execute
```

Offline analysis of existing evidence, **no model or browser**:

```sh
uv run --locked python -m kitsune_benchmark.personal_analysis \
  artifacts/personal/20261019T104926Z-ef986c9a42/suite-summary.json \
  --output artifacts/personal/20261019T104926Z-ef986c9a42/analysis-review.json
```

The output file must be new; the analyzer refuses overwrite. Recorded analysis
is already at `diagnostic-analysis.json` in that first pair directory.

Private, gitignored suite and pair identifiers:

```text
artifacts/personal/full-pilot-20261019T104925Z.json
artifacts/personal/full-pilot-20261019T104925Z-stderr.log
artifacts/personal/
  20261019T104926Z-ef986c9a42/  # current page; suite-summary.json + diagnostic-analysis.json
  20261019T105002Z-1875e28bfe/  # existing tabs
  20261019T105044Z-e2d6a5f69e/  # research
  20261019T105137Z-2b5ad2bfc7/  # account lookup
  20261019T105231Z-6e2c000157/  # handoff draft
  20261019T105319Z-6c56ebb04c/  # safe form
  cache-probe-20261019T105933Z/results.json
```

Every pair retains `{target}-native-rpc.jsonl`, `{target}-native-metadata.json`,
session evidence/config, Codex `events.jsonl`, evaluation and resource summaries.
Native diagnostic files are private `0600`; raw payloads remain unpublished.
All 12 per-run resource collectors reported zero sampling errors and no
unexpected survivors. Summed RSS and cleanup observations retain the usual
[resource methodology limits](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/resources.md).

Recorded harness SHA256:
`28dadf8dad27caf2061b634ca3dd053631e6f9200ac69bebf23246f0038fd5b1`.
Catalog SHA256:
`e94fd280c308da2f0bef2960ef442402afa03c25fa0c84bfbe85042e0040b653`.
Kitsune source was clean at `68f7e979dcda9a982f8f3781841ecc6b26d7b3ee` for every
pair. The later offline analyzer/probe utilities are not included in that run's
recorded harness hash.

## Limits and next step

One variant, fixed order, single attempts, synthetic short pages, and protocol/
format failures are substantial limitations. Exact per-model-request token usage,
TTFT, provider prompt envelopes and remaining subscription quota are not logged.
No statistical significance, general MCP ranking or API cost is claimed.

Prioritize event-correct tab freshness/readiness, a bounded text-plus-ref
observation, and a lean documented personal-tool preset. Revisit strict grader
alignment and measure a separately labeled before/after cohort before attributing
savings to an optimization. No Kitsune production source or grader was changed
as part of this investigation.
