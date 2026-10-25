# Kitsune v0.4.1 subscription suite — incomplete

[Results index](README.md) · [By Kitsune version](kitsune-versions.md)

A [subsequent corrected-harness run completed](2026-10-25-opus-subscription-v0.4.1.md)
with 448 selected scorable executions and one separately recorded setup retry.
This report preserves the earlier attempt; its results are not pooled into that run.

**No full-suite score or version comparison is available from this attempt.** The requested run
was stopped after an unscorable Kitsune run exposed a subscription-harness MCP
startup problem. Missing tools are not counted as an ordinary task failure.

## Setup

- Date: 2026-10-25 KST (artifact IDs use UTC).
- Kitsune: clean pinned `v0.4.1`,
  `83acfe92272cd5bb0909785d7d821d05136710d0`, in
  `artifacts/vendor/kitsune-v0.4.1/`.
- Benchmark: `b1aa041957273a7491506e9841c9583648d91aef`,
  `taskset-v1.2-8-gb1aa041`, clean at launch. No task/fixture/grader changes
  were made for this run.
- Model: `claude-opus-5-5`, effort medium, Claude Code `2.1.303`.
- Harness: **`claude`, claude.ai subscription**, not API-key billing. Provider
  credential variables were removed from child environments. The sanitized
  doctor passed; inspected agent init events report `apiKeySource: none`.
- Playwright MCP: `0.0.83`; isolated benchmark browser profiles and synthetic
  local tasks only.
- Requested: 398 full-suite agent runs, then 48 user-seeded personal coexistence
  runs and 2 typing-user runs. The two targets ran concurrently within each
  personal/gallery track; MiniWoB and coexistence were to follow.
- This is a **different harness cohort** from the v0.4.0 API/`--bare` report.
  Do not infer version improvements or regressions from their token/time totals.

## Completed first-track evidence

The fixed-launch attempt started at 02:51:39 KST. Its first track was personal
variant 0, all 24 tasks selected for each target:

| Target | Requested | Attempted | Scorable | Successes | Unscorable |
| --- | ---: | ---: | ---: | ---: | ---: |
| Playwright | 24 | 24 | 24 | 24 | 0 |
| Kitsune v0.4.1 | 24 | 3 | 2 | 2 | 1 |

Kitsune passed `pb-current-01` and `pb-current-02`. `pb-current-03` was
`harness_error`, with external `scorable: false` and `task_success: null`.
**This is not a 2/24 task score**, and the unequal coverage does not support
aggregate efficiency comparisons.

The full-suite driver logs a failed track but starts the next one rather than
stopping the whole suite. Personal variant 1 had therefore started when the
first-track summaries were inspected. Its process tree was explicitly stopped;
its partial files are excluded from the table. No gallery, MiniWoB or coexistence
result is claimed. No automatic retry, model substitution or API fallback was
used by the suite driver.

## Two startup problems, kept separate

### 1. Detached launch inherited a disposable temporary directory

The first launch used the tool sandbox's `TMPDIR`. The directory was removed
when the launch call returned. Kitsune's bridge log recorded an `uv` filesystem
error referring to that deleted directory. That launch also produced an
unscorable Playwright run with no tools, although its exact failure mechanism
was not independently isolated.

The private launcher was changed to use persistent `/tmp` for `TMPDIR`, `TMP`
and `TEMP`. A separate sequential `pb-current-01` canary then passed for both
MCPs, with all 23 allowlisted tools exposed. This canary is not added to the
first-track totals above. The interrupted launch was retained separately.

### 2. Tools still pending during inference after the temporary-path fix

In the fixed-launch Kitsune `pb-current-03` run:

- Firefox loaded the v0.4.1 extension and the bridge reported it connected.
- Native metadata recorded a successful MCP initialize response but
  `tools_pages: []`.
- Claude's init event had `mcp_servers: [{name: "browser", status: "pending",
  source: "dynamic"}]` and `tools: []`.
- The audited run made **zero MCP calls**. Its final text contained apparent
  tool invocations and claimed success, but these were not actual tool calls
  and do not establish task completion.

The stable temporary directory did **not** resolve this second problem. The
precise cause of incomplete initialization remains unisolated; possible client
startup timing and fixture readiness must be investigated before resuming.
It is not evidence of a Kitsune task-capability regression.

## Checks and next step

The no-model harness test suite completed: **182 tests, 10 skipped, no failures**
(172 executed tests passed). This does not validate subscription MCP startup
under real model execution.

Before rerunning the 448-run cohort, establish that the subscription client
waits for the MCP catalog and fixture readiness before starting inference, and
that an unavailable tool surface stops the suite without continuing later
tracks. Keep the taskset fixed; record any harness correction as a separate
experimental change. The v0.4.1 release's checkbox, collapsed-row and selector
fixes have **not** been verified by this incomplete full-suite attempt.

## Private artifacts

- Root: `artifacts/opus-subscription-v0.4.1/`.
- `full/`: initial invalid launch; `aborted-*.log` retain its orchestration logs.
- `canary.json`: successful two-target canary with persistent temporary paths.
- `full-valid/`: **attempt label only, not an assertion that all runs are valid**;
  contains the fixed-launch manifest, first-track summaries, suite log and
  interrupted variant-1 output files.
- `execution-status.json`: blocked state; `run.py`: private launcher.
- First-track Playwright summary:
  `artifacts/personal/20261024T175140Z-f8dd7834e9/suite-summary.json`.
- First-track Kitsune summary:
  `artifacts/personal/20261024T175140Z-04f365720a/suite-summary.json`.
- Unscorable Kitsune pair:
  `artifacts/personal/20261024T175224Z-87182b38d1/`.
- Unit-test log: `artifacts/preflight-v0.4.1-tests.log`.

Raw profiles, credentials and unreviewed transcripts remain private.
