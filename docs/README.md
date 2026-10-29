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
| **Personal browsing** | Existing tabs, test sessions, lookup, drafts and safe mutations | 28 original specifications (`personal-browsing-local-v3`), all runnable local fixtures, each with three data variants | Opus subscription on Kitsune v0.7.0, 28 × 3 (2026-10-26): 83/84 Playwright vs 84/84 Kitsune ([report](results/2026-10-26-opus-subscription-v0.7.0.md)) |
| **Coexistence** (frozen `coexistence-local-v1`) | Kitsune philosophy: the user is in the browser too | 28 personal tasks under `user-seeded`, the Kitsune `protect-user-tabs` arm and `co-typing-01`; 25 delegation/recovery/coexistence tasks specified only in [`tasks/coexistence/catalog.json`](../tasks/coexistence/catalog.json) | Opus subscription on Kitsune v0.7.0, frozen plan (2026-10-28): v3 user view 2/28 Playwright vs 28/28 Kitsune; `co-typing-01` user input 0/3 vs 3/3; protect arm 28/28 ([report](results/2026-10-28-new-tracks-v0.7.0.md)) |
| **External** (`external-v1`) | Tasks not written for these fixtures | 7 pinned MiniWoB++ tasks graded by the upstream reward + 3 live public-web tasks recorded, never graded ([protocol](external.md)) | Opus subscription on Kitsune v0.7.0 (2026-10-28): MiniWoB 7/7 both; live tasks completed by both ([report](results/2026-10-28-new-tracks-v0.7.0.md)) |
| **Read-only smoke** | Browser/MCP connectivity and native-tool smoke | Example Domain task; no external task-success grader | One completed historical `gpt-6.1-sol` pair, 2026-10-18 |
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
| [Coexistence track](coexistence.md) | Frozen `coexistence-local-v1`: user channel over WebDriver BiDi, user-owned seeding, view/input contracts, run plan and comparability; spec catalog for coexistence, delegation and recovery |
| [Component gallery](gallery.md) | Modern components, multimodal puzzles and a hand-off judgement task on one local page |
| [Personal-state track](personal-state.md) | Specification only: tasks that need a personal profile's history, bookmarks or logins |
| [Task catalog](../tasks/personal/catalog.json) | Per-task requests, initial state, success/safety criteria, implementation status |
| [Personal execution config](../configs/benchmarks/personal.json) | Model/pins, default pilot selection and wall-clock budget |
| [Codex integration](codex-harness.md) | Authentication, isolation, native tool policy, process lifecycle and trace audit |
| [Local resource methodology](resources.md) | CPU/RSS sampling scope, attribution and interpretation |
| [Optimization findings](optimization-findings.md) | Causal cache evidence, token/observation candidates, native diagnostic logging and offline analysis |
| [Hostile-UI capability matrix](hostile.md) | Draft, no model: real-web defenses and real UI libraries × tool strategies, per MCP server; opt-in OS input |
| [External track](external.md) | `external-v1`: pinned MiniWoB++ tasks, reward instrumentation, live-task recording and non-standard track limits |
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
