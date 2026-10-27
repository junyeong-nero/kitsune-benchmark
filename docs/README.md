# Documentation

This project compares **native browser MCP configurations under a fixed Codex
model**, with externally checked task outcomes and local resource measurements.
The current product-oriented focus is **personal browsing**: continuing work in
already-open tabs and a pre-established test session.

## Start here

1. [Run safely](running.md): setup, plan-only checks, one-pair execution, quotas,
   tests and where results are written.
2. [Personal browsing taskset](personal-browsing.md): the 24-task catalog,
   six implemented tasks, session/reset protocol, grading and limitations.
3. [Latest six-task result](results/2026-10-19-personal-six-task.md): all six
   implemented tasks, variant 0, with token/time breakdown and grading caveats.
4. [Optimization findings](optimization-findings.md): confirmed tab-cache delay,
   observation/schema opportunities, diagnostic logs and no-quota analysis commands.
5. [All result reports](results/README.md): dated evidence with the model and
   scope of each experiment. Historical reports are not relabeled to today's model.
6. [Results by Kitsune version](results/kitsune-versions.md): the frozen
   `taskset-v1` and how the taskset is upgraded with the next Kitsune release.

## Tracks and current evidence

| Track | Purpose | Implementation | Observed evidence |
| --- | --- | --- | --- |
| **Personal browsing** | Existing tabs, test sessions, lookup, drafts and safe mutations | 24 original specifications, all runnable local fixtures, each with three data variants | 24 variant-0 pairs on Claude Code + `claude-haiku-5-5`: 21/24 Playwright vs 23/24 Kitsune, 2026-10-21; six-task Codex `gpt-6-luna` pilot 3/6 vs 4/6, 2026-10-19 |
| **Coexistence (draft)** | Kitsune philosophy: the user is in the browser too; delegation and recovery specs | 24 personal tasks under `user-seeded` + `co-typing-01` runnable; 25 tasks specified in [`tasks/coexistence/catalog.json`](../tasks/coexistence/catalog.json) | Opus, 2026-10-23: user-seeded v1 24/24 both, v3 user view 2/24 Playwright vs 24/24 Kitsune; `co-typing-01` 87 vs 0 misdirected keystrokes ([report](results/2026-10-23-coexistence-user-seeded.md)) |
| **MiniWoB++ UI pilot** | Small upstream-task/original-reward integration check | Only `click-test-2`, seed 42; not the complete MiniWoB++ suite | One pair passed with historical `gpt-6.1-sol`, 2026-10-18 |
| **Read-only smoke** | Browser/MCP connectivity and native-tool smoke | Example Domain task; no external task-success grader | One completed historical `gpt-6.1-sol` pair, 2026-10-18 |
| **Model-free stress** | Concurrent MCP clients sharing one private browser; independent `stress-v1` protocol | Fixed `release-v1` profile, CPU/RSS and latency/throughput; included once in full-suite driver | 1–32 clients × 3 repeats, 77,334 measured requests, 0 errors on Kitsune v0.7.0+4; [report and limitations](results/2026-10-26-kitsune-stress-v1.md) |
| **Shared-browser stress comparison** | Supported shared-browser deployments under concurrent read load, independent `stress-compare-v1` | One Firefox/context per target, topology proofs, KP/PK order, response/observer metrics | 24 arms, 280,008 measured requests, no errors; Playwright higher throughput/lower p95 in all 12 pairs for tab listing; [report and limits](results/2026-10-26-shared-browser-stress-comparison.md) |
| **WebArena / live personal accounts** | Future realistic/multi-step tracks | Not provisioned or implemented | No results |

Execution defaults to **Claude Code on the claude.ai subscription** (`--harness claude`, no
API credit); API billing is opt-in (`--harness claude-api --allow-api-billing`). The Codex harness
(`gpt-6-luna`, CLI `0.163.0`) remains available. Model availability and quota can change. A completed simple task
pair is not a general success rate, tool ranking or security certification.

## Guides and source of truth

| Document or file | Owns |
| --- | --- |
| [Running guide](running.md) | Operational sequence, command selection, cost boundaries, exit codes |
| [Personal browsing protocol](personal-browsing.md) | Personal-session task design, provenance, fixture/evaluation/reset contract |
| [Coexistence track](coexistence.md) | Draft: user channel over WebDriver BiDi, user-owned seeding, view/input contracts, spec catalog for coexistence, delegation and recovery |
| [Component gallery](gallery.md) | Modern components, multimodal puzzles and a hand-off judgement task on one local page |
| [Personal-state track](personal-state.md) | Specification only: tasks that need a personal profile's history, bookmarks or logins |
| [Task catalog](../tasks/personal/catalog.json) | Per-task requests, initial state, success/safety criteria, implementation status |
| [Personal execution config](../configs/benchmarks/personal.json) | Model/pins, default pilot selection and wall-clock budget |
| [Codex integration](codex-harness.md) | Authentication, isolation, native tool policy, process lifecycle and trace audit |
| [Local resource methodology](resources.md) | CPU/RSS sampling scope, attribution and interpretation |
| [Model-free stress](stress.md) | Independent stress-v1 protocol, release profile, resource safety stops and full-suite integration |
| [Shared-browser stress comparison](stress-comparison.md) | Independent stress-compare-v1, shared-browser-v1 profile, HTTP sessions, shared-context proof and paired metrics |
| [Optimization findings](optimization-findings.md) | Causal cache evidence, token/observation candidates, native diagnostic logging and offline analysis |
| [MiniWoB++ integration](miniwob.md) | Pinned upstream task, reward instrumentation and non-standard track limits |
| [MCP comparison candidates](comparison-candidates.md) | Future MCP/browser cohorts; not benchmark task sources or measured adapters |
| [Disclosure experiment plan](experiments/2026-10-22-disclosure-plan.md) | Preregistered 2×2 observation/action-guidance experiment and budget |
| [Disclosure A/B findings](results/2026-10-22-disclosure-ab.md) | 72 repeated runs, ref/expect mechanism probes, and small-model selector decision |
| [Target-view A/B plan](experiments/2026-10-22-target-view-plan.md) | Representation-only experiment, fixed refs/content, personal/UI/media coverage |
| [Target-view A/B findings](results/2026-10-22-target-view-ab.md) | 60 repeated runs, grouping overhead, media-identity/cropping gaps, and adoption decision |
| [Sonnet/Opus follow-up](results/2026-10-22-sonnet-opus-target-view.md) | 16 bounded parallel runs, model-sensitive formatting effects, and confirmed screenshot-ref failure |
| [Tool usage inventory](results/2026-10-22-tool-usage.md) | Offline counts from 196 runs, actual exposure, error categories, and default-surface candidates |
| [Results index](results/README.md) | Dated observations and evidence references |
| [Results by Kitsune version](results/kitsune-versions.md) | The same reports grouped by the Kitsune revision they ran on |

The task catalog and execution configs are executable inputs. Guides describe
their protocol. Dated reports describe what was actually run, not everything
currently possible. Raw JSONL, session state, profiles and resource logs stay in
private, gitignored `artifacts/`; published reports contain reviewed summaries.

## Reading results correctly

- Read **external `task_success` and `scorable`**, not only CLI exit status or
  the agent's final answer. Generic `completed_unscored` can have an attached
  successful external evaluation.
- Input tokens **already include cached input**. No subscription-billing or
  dollar-cost estimator is implemented; missing usage is not zero cost.
- Personal-track time includes hidden setup/readiness/inventory calls, recorded
  separately from agent calls. Do not compare it directly with uninstrumented
  MiniWoB timings.
- Keep model, tool policy, task variant, browser, startup policy and order visible.
  Current fixed-order, single-attempt reports do not justify general rankings.
- All personal fixtures are synthetic local apps. Real logins, durable profile
  history, live-web reliability and prompt-injection robustness remain untested.
