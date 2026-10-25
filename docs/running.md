# Running benchmarks safely

[Documentation index](README.md) · [Personal task protocol](personal-browsing.md) ·
[Results](results/README.md)

## Setup

Prerequisites: Python 3.11+, uv, Node/npm, a supported Codex ChatGPT subscription
login and the Kitsune source checkout (normally sibling `../kitsune`). The
current harness pins Codex CLI `0.163.0`; execution configs request
`gpt-6-luna` with reasoning `medium`.

```sh
uv sync --locked
npm ci --ignore-scripts --no-audit --no-fund
npm run setup:firefox
```

The browser helper installs to the private `artifacts/browsers` cache with
shared-cache garbage collection disabled. Automated pair commands use isolated
headless profiles and private bridge ports, not an everyday Firefox/Zen session.
Use `--kitsune-project /absolute/path/to/kitsune` if the checkout is not the
sibling directory; `--codex /path/to/codex` disambiguates CLI discovery.

Do not import real account credentials or attach a normal browser profile.
Personal tasks use synthetic local app state and test cookies. See
[authentication and isolation](codex-harness.md#authentication-and-isolation).

## Check without inference

```sh
# Version/help/login checks only, not a model-availability or quota test.
uv run --locked python -m kitsune_benchmark doctor --json

# Exact one-pair plan: no browser, model, login check or fixture server.
uv run --locked python -m kitsune_benchmark personal \
  --task pb-current-01 --variant 0
```

`doctor` flags inherited model API credentials. Actual execution uses a restricted
child environment that strips them. To run a standalone subscription-only doctor
check when the shell has such variables, omit them only for that child command:

```sh
env -u OPENAI_API_KEY -u CODEX_API_KEY -u OPENAI_AUTH_TOKEN -u AZURE_OPENAI_API_KEY \
  uv run --locked python -m kitsune_benchmark doctor --json
```

No command edits the user's Codex authentication/configuration. The CLI alone
reads its existing login; there is no API-key or alternate-model fallback.

## Choose the smallest relevant run

| Command | What is selected | Maximum requested agent runs |
| --- | --- | ---: |
| `personal --task pb-current-01 --execute` | One current-page task pair, variant 0 | 2 |
| `personal --execute` | Six-task personal pilot, one variant | 12 |
| `personal --all --execute` | All 28 personal tasks, one variant | 56 |
| Three separate `personal --variant N --execute` commands for N=0,1,2 | Six tasks across three data variants | 36 total |
| `benchmark --execute` | One MiniWoB++ `click-test-2` pair, seed 42 | 2 |
| `smoke --execute` | One read-only Example Domain pair | 2 |

These are **agent run counts**, not LLM turn counts, token caps or prices. One
agent run can contain many model/tool interactions. There is no `full-test`
command that automatically executes every upstream benchmark.

### Default harness: Claude Code on the subscription

`smoke`, `benchmark`, `personal`, `gallery`, `coexistence`, `doctor` and
`scripts/run-full-suite.py` default to **`--harness claude`**. It runs **Claude Code
`2.1.303`** on the existing **claude.ai subscription login**, with the model/effort
from each config's `claude_code` block (default `claude-opus-5-5`, effort `medium`;
`--claude-model` overrides it). Usage
counts against the plan's limits, **not API credit**, and there is no dollar cap.
`ANTHROPIC_*`/provider variables are never inherited, so the `.env` key is not used.

```sh
uv run --locked python -m kitsune_benchmark doctor          # checks the claude.ai login, no inference
uv run --locked python -m kitsune_benchmark personal --execute   # claude-opus-5-5 by default
```

Without `--bare` (which would disable the subscription login), Claude Code sends
each MCP tool description in full. Reports up to 2026-10-24 used `--harness claude-api`
(`--bare`, first paragraph only), so subscription runs are a **separate cohort**:
compare versions within one harness, never across. `--harness codex` (ChatGPT login)
remains available.

The Claude harness forces `MCP_CONNECTION_NONBLOCKING=false`: Claude Code
`2.1.303` otherwise may start inference while a slow fixture's MCP catalog is
still pending. `MCP_TIMEOUT` alone does not make connection blocking. Each run
manifest records this startup policy and its timeouts. A missing/empty initial
tool catalog or a pending/failed MCP connection is a harness error, not a task
failure. This startup correction is a harness change; keep pre-fix incomplete
attempts separate from corrected runs.

**API-key billing is opt-in (`--harness claude-api`, `claude-api-full`).** These
spend `ANTHROPIC_API_KEY` credit from the repository `.env` and refuse to execute
without **`--allow-api-billing`**. Same Claude Code isolation, authenticated only by
that key, with `--bare` so OAuth/keychain credentials are never read. User keys
(`sk-ant-usr…`) also need a workspace: `ANTHROPIC_WORKSPACE_ID` in `.env`, or the
key's only active workspace. Each run is capped by Claude Code `--max-budget-usd`, by model from
`claude_code.max_budget_usd_per_run_by_model`: **Opus $1.00, Sonnet $0.50, Haiku $0.10**,
just above the largest single run recorded through 2026-10-24 (Opus $0.76, Haiku $0.06;
Sonnet scaled from 8 runs, max $0.06). `--max-budget-usd-per-run` overrides it; a model without
an entry needs it and the audit requires
`apiKeySource: ANTHROPIC_API_KEY`. `--budget-usd` stops before any pair whose
worst case would exceed the suite total. `doctor --harness claude-api` validates
the key, workspace and model with free `GET` requests.

```sh
uv run --locked python -m kitsune_benchmark doctor --harness claude-api
uv run --locked python -m kitsune_benchmark personal --harness claude-api --allow-api-billing \
  --all --budget-usd 30 --execute
```

`total_cost_usd` is Claude Code's client-side estimate; the Console usage page is
the billing source.

**Client description handling matters.** Claude Code `--bare` sends only the first
paragraph of each MCP tool description; without `--bare` it sends them in full.
`--harness claude-api-full` uses the same `.env` key and caps without `--bare`,
so both client behaviours can be measured. Report them as separate cohorts.

**Model and per-run cap overrides.** `--claude-model ID` replaces the config's
`claude_code.model` and `--max-budget-usd-per-run N` its per-run cap for one
command; the config files stay unchanged and each run's manifest records the
values actually used. `doctor --claude-model ID` validates that model for free.
`scripts/run-full-suite.py` runs every graded track (personal 28 × 3 variants,
gallery 21 × 3 variants × 2 layouts, MiniWoB) under one total `--budget-usd`, and
writes `suite-manifest.json` with the Kitsune revision and `git describe` so the
result can be filed under [its Kitsune version](results/kitsune-versions.md).
By default each personal/gallery track runs Playwright and Kitsune as two
concurrent `--targets` processes with half the remaining budget each (about half
the wall time; elapsed and CPU/RSS are then measured under shared load, and the
suite log has one entry per target). `--sequential` restores paired,
Playwright-first runs in one process. A Playwright-only process starts no Kitsune
bridge or browser. `scripts/analyze-per-tool.py <out>` compares the two targets
tool by tool (calls, errors, latency, response size, grouped error texts).
The full-suite driver exits **3** after an invalid/incomplete track (nonzero exit,
stopped reason, malformed summary, or incomplete coverage), once its active
target processes have settled. It does not start later tracks or retry. Ordinary
scorable task failures still allow the suite to continue. Use a fresh output
directory for each suite invocation; nonempty output directories are rejected.

```sh
# Subscription (default): no API credit, no dollar cap.
uv run --locked python scripts/run-full-suite.py --model claude-opus-5-5 \
  --kitsune-project artifacts/vendor/kitsune-pinned --out artifacts/opus-full
# API credit, explicitly:
uv run --locked python scripts/run-full-suite.py --harness claude-api --allow-api-billing \
  --budget-usd 60 --kitsune-project artifacts/vendor/kitsune-pinned --out artifacts/opus-full
```

### Repeated, predeclared order (taskset-v3)

`--attempts N` (default 1) repeats every track/variant/layout unit using fresh
fixture sessions and unique pair/run artifacts. Driver stdout/stderr go into
`attempt-001/`, `attempt-002/`, etc. when N > 1. The suite manifest declares the
plan before any runs; `suite-log.jsonl` and `suite-summary.json` preserve results
by attempt and by order, including failed/incomplete entries. Fail-fast applies
across all attempts: no implicit retry after invalid evidence.

A = Playwright, B = Kitsune (not baseline/candidate Kitsune versions).
`--sequential --order ab` or `ba` fixes the target order for every attempt.
`--sequential --attempts 2 --order abba` declares AB for attempt 1 and BA for
attempt 2 (alternates for larger even N; odd N is rejected). Order includes
MiniWoB. Default parallel personal/gallery mode has **no target order** and
rejects `--order`; its MiniWoB pair remains AB. Default `--attempts 1` retains
the previous parallel behavior, or AB with `--sequential`.

```sh
# Authorized model execution only; run both Kitsune revisions separately on the same frozen tag.
uv run --locked python scripts/run-full-suite.py --sequential --attempts 2 --order abba \
  --kitsune-project artifacts/vendor/kitsune-pinned --out artifacts/v3-repeated
```

Every pair/run manifest records configured geometry read from launch/server args:
Playwright `viewport_size` 1280×720 (content) and the Kitsune headless Firefox
`window_size` (a window, not a content area). Configured window height is never
`innerHeight`: the native check below measured 85 CSS px of Firefox toolbars.

**Effective content viewport (#21).** Every page of a `personal-browsing-local-v3`
run (`kitsune_benchmark personal`, all 28 tasks including the default pilot)
serves one inline `<head>` script, allowed only by its CSP hash, that
`navigator.sendBeacon`s `innerWidth`, `innerHeight`, `outerWidth`, `outerHeight`
and `devicePixelRatio` to the fixture server on every page load. It renders
nothing and adds no accessibility node or snapshot text; the server keeps the
reports apart from visits, form writes and forbidden actions, so grading is
unchanged. No agent-visible call or resize is involved. Apart from that script
and its CSP header, the 24 original tasks serve the same pages as `taskset-v2`;
reproduce v2 results from the `taskset-v2` checkout. Gallery, MiniWoB, coexistence
and the experiments that reuse personal fixtures serve uninstrumented pages and
are not measured. The personal, gallery and coexistence tracks launch Kitsune's
window at 1280×805 (720 + 85) so its content viewport is 1280×720 by construction
(verified per run only on personal pages); MiniWoB and the older experiments keep
the 1280×720 window. Pair manifests show `content_viewport_construction`.

After each run, `viewport.effective` (first report, `reports`,
`later_reports_differed`) is written beside the unchanged `configured` record into
the run's `manifest.json`, `<target>-summary.json`, `pair-manifest.json`,
`pair-summary.json` and the personal summaries. A target that never ran keeps
`effective: null` (`not_observed`). Without observations the reason is
`no_report_received` (a personal run) or `track_pages_do_not_report` (gallery and
every other track: an unsupported measurement, not a parity result).
`content_viewport_equality_asserted` is true only when every report in the run
agrees and equals the shared `reference` (1280×720 at `devicePixelRatio` 1) that
both targets are measured against. A cohort parity claim needs it true on the
personal runs of both targets; it says nothing about tracks without reports.

Native no-model check (Kitsune `v0.4.1-15-g2110a32`, Playwright MCP 0.0.83 Firefox build 1553,
headless, macOS): Playwright `--viewport-size 1280x720` → inner 1280×720,
outer 1280×805, DPR 1. Kitsune `--width=1280 --height=720` → inner 1280×635,
outer 1280×720, DPR 1. Kitsune `--height=805` → inner 1280×720, outer
1280×805, DPR 1. Rerun it after a Firefox or Kitsune upgrade:

```sh
PERSONAL_BROWSER_TEST=1 PERSONAL_KITSUNE_TEST=1 KITSUNE_PROJECT=../kitsune \
  uv run --locked python -m unittest discover -s tests -p test_taskset_v3.py -k Native
```

`taskset-v3` (tag at `4d73130`) adds four long-page personal
tasks (28 total); gallery's benchmark ID remains v2, and the seeded-tab custody
contract is unchanged. Compare only reruns on the same v3 freeze, never v3
scores with v1.x/v2. Personal summaries report success, tokens and existing
response-byte/character counters per category (see [protocol](personal-browsing.md#long-page-lookup-taskset-v3)).

**A/B arms and a pinned Kitsune checkout.**

```sh
# A dedicated clone, so other work in ../kitsune cannot move it mid-suite.
git clone https://github.com/junyeong-nero/kitsune.git artifacts/vendor/kitsune-pinned
uv run --locked python -m kitsune_benchmark personal --all \
  --kitsune-project artifacts/vendor/kitsune-pinned --targets kitsune --execute
```

`--targets` selects which MCPs run (default `playwright,kitsune`). `--kitsune-preset`
sets `KITSUNE_TOOL_PRESET` for the Kitsune server. A suite stops with
`stopped_reason: kitsune_revision_changed` if the Kitsune checkout's revision or
dirty state changes between pairs.

**Live-site tasks.** `smoke --task FILE` runs any `{id, prompt}` task in the same
isolated browsers without a grader. Add `--ui-tools` for the benchmark UI allowlist
and `--targets` to pick MCPs. Live sites change, so judge results from the trace and
screenshots, and never treat them as benchmark scores.

```sh
uv run --locked python -m kitsune_benchmark smoke \
  --task tasks/live/steam-goty-2025-negative-100h.json --ui-tools --targets kitsune \
  --kitsune-project artifacts/vendor/kitsune-pinned --timeout 300 --execute
```

**Token attribution.** Claude Code runs record `token_attribution`: requests,
first-request input (≈ fixed prefix), prefix × requests, history, and per tool the
result characters and `carry_chars` (characters × later requests that re-send
them). Suite summaries sum it per target as `token_attribution_all_runs`.

**Grading contracts.** Since `taskset-v2`, `task_success`/`safety_pass` use
contract v2 (`primary_contract: "v2_agent_tab_cleanup"`), which allows closing
tabs the agent opened while still requiring every starting tab, followed by
identity (`seeded_tab_custody`), on its URL at every checkpoint. Strict v1 (any `browser_tabs close` fails safety, the `taskset-v1.x`
primary) stays in `contracts.v1_strict_close`, with `close_only_failure` for a
functionally successful v2 pass that v1 failed only for closing a tab.
Summaries add `successes_v1_strict_close`, `safety_failures_v1_strict_close`,
`v1_close_only_failures` and `functional_successes`, plus `custody_unknown`
(custody could not be established) and `success_known_runs`, the denominator of
`scorable_success_rate`. Never relabel v1 results as
v2 or the reverse; `taskset-v1.x` reports keep their v1 scores.

Isolation: `--setting-sources ""` (no user/project settings or hooks),
`--strict-mcp-config` with the single `browser` server, `--tools ""` (no
built-in tools), `--permission-mode dontAsk`, no session persistence. Because
`--allowedTools` only pre-approves, `mcp_tool_filter.py` hides non-allowlisted
tools from `tools/list`, matching Codex `enabled_tools`. Upstream exit or stdout
EOF closes the relay even while client stdin stays open, preserving upstream
failure status; cleanup escalates from stdin EOF to terminate and then kill.
The stream-json audit reports `input_tokens` as total input
(`cached_input_tokens` = cache reads, a subset) and `list_price_cost_usd`, which
is Claude Code's list-price estimate, not the subscription charge. Results
from different harnesses/models are separate experiments, not one leaderboard.

### Personal browsing: recommended starting point

```sh
# One explicit quota-consuming pair.
uv run --locked python -m kitsune_benchmark personal \
  --task pb-current-01 --variant 0 --execute

# Larger pilot: only run after inspecting a small pair and agreeing the quota budget.
uv run --locked python -m kitsune_benchmark personal --execute

# Select tasks explicitly; repeat --task for each selection.
uv run --locked python -m kitsune_benchmark personal \
  --task pb-tabs-01 --task pb-safe-01 --variant 1 --execute
```

There are **28 runnable specifications**, with six selected by the default
pilot and all 28 selected by `--all`. Unknown, duplicate and specification-only
IDs fail validation before inference. The
first real one-pair result is documented
[here](results/2026-10-19-personal-current-page.md); do not count it as a full
six-task pilot. A separate [six-task variant-0 pilot](results/2026-10-19-personal-six-task.md)
is now recorded, including unsuccessful tasks and diagnostic breakdowns.
See the [catalog and protocol](personal-browsing.md#catalog) for eligible tasks and scope.

### Other tracks

```sh
# Read-only connectivity/tool smoke; no external success grader.
uv run --locked python -m kitsune_benchmark smoke
uv run --locked python -m kitsune_benchmark smoke --execute

# Draft coexistence track (docs/coexistence.md): plan, then the typing-user fixture pair.
uv run --locked python -m kitsune_benchmark coexistence
uv run --locked python -m kitsune_benchmark coexistence --execute

# MiniWoB source fetch only: network/download, but no model inference.
uv run --locked python -m kitsune_benchmark benchmark --fetch
uv run --locked python -m kitsune_benchmark benchmark
uv run --locked python -m kitsune_benchmark benchmark --execute
```

MiniWoB is the small [upstream task/reward integration](miniwob.md), not the
personal-session evaluation and not the complete MiniWoB++ suite. Generic
`plan`/`run` are advanced operator-provisioned commands; `run` requires
`--confirm-isolated-browser` and **does not provision an isolated browser**.
Read [individual-run inputs](codex-harness.md#individual-run-inputs) first.

## Quota and stopping

- Without `--execute`, paired track commands plan only. The separate generic
  `run` command executes by definition.
- Execution consumes **ChatGPT subscription usage**. The project has no direct
  model API integration, remaining-quota monitor or dollar-cost estimator.
- Current per-agent wall-clock limit is **180 seconds** in the paired configs.
  **There is no token-budget stop.** A timeout is not a fixed token allowance.
- Setup/execution/unscorable failures stop further targets/tasks. Ordinary
  scorable task failures do not. No automatic retry or model substitution occurs.
- Fixed order is Playwright then Kitsune. Data variants are not repeated
  identical trials or order counterbalancing.

## Inspect outcomes and usage

The CLI prints the summary. Raw evidence is private and gitignored:

| Track | Artifact root | Main summaries |
| --- | --- | --- |
| Personal | `artifacts/personal/<pair-id>/` | `personal-summary.json`; `suite-summary.json` in the first attempted pair |
| Gallery | `artifacts/gallery/<pair-id>/` | `gallery-summary.json`; `suite-summary.json` in the first attempted pair |
| Coexistence | `artifacts/coexistence/<pair-id>/` | `coexistence-summary.json`; `suite-summary.json` in the first attempted pair |
| MiniWoB | `artifacts/miniwob/<pair-id>/` | `benchmark-summary.json` |
| Smoke | `artifacts/smoke/<pair-id>/` | `pair-summary.json` |

Per-run `summary.json` retains execution audit and `usage`; external tracks add
`evaluation.json` and `benchmark_evaluation` in the target result.

Read in this order:

1. **Coverage:** requested/attempted/completed pairs; which targets actually ran.
2. **Validity:** `execution_status` and external `scorable`. Missing setup
   evidence or model/transport errors are not ordinary task failures.
3. **Outcome:** external `task_success`, `functional_success` and `safety_pass`
   where available. Final chat claims do not establish success.
4. **Usage:** `input_tokens`, `uncached_input_tokens`, `cached_input_tokens`,
   `output_tokens` and optional `reasoning_output_tokens`. Total input includes
   cache reads and cache creation. Claude's `uncached_input_tokens` excludes
   both; Codex's is derived as total minus cached input (and cache creation if
   reported). Cache creation is reported separately, not silently counted as
   Claude uncached input. Missing usage is not zero consumption. Subscription-limit
   accounting cannot be reconstructed from these fields.
5. **Efficiency:** personal/gallery/coexistence `by_target.cost_metrics` separates
   `all_attempts`, `successful_tasks`, `same_successful_tasks`, `failed_attempts`
   (explicit false verdict), and `unscored_or_unknown_attempts`. Same-success
   means both targets succeeded **in the same pair**, not unrelated variants or
   parallel single-target fixtures. `paired_attempts` counts pairs containing both
   target results: zero means the same-success scope is not applicable; a positive
   count with zero same-success attempts means no joint successes were observed.
   Each scope includes total and uncached input
   together in `usage`, `elapsed_sec`, `timing`, and `resources_task`. Scalar totals
   have `reported_runs`/`missing_runs`; no observations yields null, not zero.
   Partial totals are not complete costs. Successful-task resource means use
   measured successful tasks only; failure and unknown costs remain separate.
   The full-suite log retains `by_target`; `analyze-per-tool.py --json <new.json>`
   also emits these cost aggregates by track. Existing summary totals remain for
   compatibility; use the coverage-aware fields for reporting.
6. **Instrumentation:** personal `harness_mcp_calls`/`harness_seconds` are hidden
   setup/readiness/inventory work, separate from agent calls. Raw elapsed time
   includes that work and cleanup, and is not clean MCP latency. `pair_lifecycle`
   separates Kitsune browser/bridge cold-start setup and warm-ready idle resources
   from per-run task costs. Per-run `timing.relay_setup_sec` is taken from native
   setup diagnostics; `elapsed_minus_relay_setup_sec` subtracts it **once**, but
   still includes harness startup, model/network, inventory and cleanup. Agent RPC
   is a nested diagnostic, not extra elapsed. Neither RPC durations nor readiness
   sleeps should be added to setup or elapsed. See [resource limits](resources.md).
7. **User interventions:** an intervention would be a human correction, approval,
   or recovery action during an agent attempt. Synthetic personal/gallery/coexistence
   tracks have no interactive human-in-the-loop protocol and report
   `user_interventions: {count: 0, status: "none_by_protocol"}`. Fixture seeding,
   scripted coexistence typing/view activity, and grader/harness calls are not
   interventions; this is not a measured real-user burden estimate.

CPU/RAM are local process observations, not remote inference or API charges.
Summed RSS can double-count shared memory; see [resource methodology](resources.md).
Review/redact raw artifacts before sharing them; do not publish profiles or tokens.

### Tools the server did not publish

With an allowlist (UI tracks), each run records `tool_surface`: the allowlisted
tools the native server actually published (`exposed`) and those it did not
(`missing`), and the runner prints a warning. Kitsune's default `lean` preset
publishes 14 of the 22 allowlisted Kitsune tools (`browser_keypress`,
`browser_drag` and others are missing), so a Kitsune failure that needs them is a
tool-surface result, not a capability verdict. Suite summaries count
`runs_missing_allowlisted_tools` per target. Use `--kitsune-preset full` (and
`KITSUNE_CAPS` for devtools tools) for a full-surface arm.

### Exit status is not the task grade

| Exit | Meaning |
| --- | --- |
| `0` | Successful plan/check; completed generic/smoke execution; or all selected external pairs scorable, even if a task failed |
| `2` | Input/prerequisite error |
| `3` | Execution incomplete, failed or externally unscorable |

`completed_unscored` is the generic adapter's completion label. A successful
external task can retain it alongside `benchmark_evaluation.task_success: true`.

## Tests without model usage

```sh
# Default tests: no real LLM calls; native browser integration tests skipped.
uv run --locked python -m unittest discover -s tests -v

# Real isolated Firefox UI fixture tests for both native MCPs, still no inference.
PERSONAL_BROWSER_TEST=1 PERSONAL_KITSUNE_TEST=1 \
  uv run --locked python -m unittest discover -s tests -p 'test_personal.py' -v
```

The opt-in tests require installed private browser/npm tools and the sibling
Kitsune checkout. They use deterministic drivers, not Codex agent execution;
passing them is not a model benchmark score. The full suite including both
native-browser tests passed 65 tests when the personal track was introduced.
After adding offline diagnostic-analysis tests, default discovery runs 69 tests
(67 pass, two opt-in native-browser tests skipped).

## Analyze existing logs without inference

New personal runs also record private `{target}-native-rpc.jsonl` (RPC start/end,
agent vs harness role, sizes, cache/setup/wait markers) and
`{target}-native-metadata.json` (initialize/catalog/configured allowlist).
Codex raw payloads and final usage remain in `runs/<id>/events.jsonl`.

```sh
# Reads already recorded evidence. No model, browser or network request.
uv run --locked python -m kitsune_benchmark.personal_analysis \
  artifacts/personal/20261019T104926Z-ef986c9a42/suite-summary.json \
  --output artifacts/personal/20261019T104926Z-ef986c9a42/analysis-review.json
```

Use a new output filename; overwrite is refused. Old runs without native logs
have missing/null diagnostics, not measured zero timings. See
[optimization findings](optimization-findings.md) for log coverage, confirmed
cache behavior, the no-model browser probe and remaining per-request usage gaps.
