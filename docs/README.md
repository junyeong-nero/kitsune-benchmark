# Documentation

[Project README](../README.md) · [Results](results/README.md)

This project runs the same browser tasks through Playwright MCP and Kitsune MCP, with the same model and tool
allowlist, and grades them from outside the agent. Pick the guide that matches what you want to do.

## Start here

- **Run something:** the [running guide](running.md) covers setup, plan-only checks, one task pair, a full suite,
  budgets, stopping, exit codes and where results are written.
- **Read results:** the [results index](results/README.md) lists every dated report.
  [Results by Kitsune version](results/kitsune-versions.md) groups them by Kitsune revision and lists the frozen
  taskset tags.
- **Latest release:** [Kitsune v0.7.2, lite plan](results/2026-11-04-opus-subscription-v0.7.2.md) (2026-11-04).
  Release cohorts follow the [release cohort protocol](experiments/2026-10-29-release-cohort-protocol.md).

## Tracks

| Track | Tasks | Latest: Kitsune v0.7.2, Opus 5.5 (2026-11-04) |
| --- | --- | --- |
| [Personal browsing](personal-browsing.md) | 28 tasks in already-open tabs and a signed-in test session (`personal-browsing-local-v3`), three data variants each, on synthetic local apps | Playwright 56/56, Kitsune 54/56 (`pb-tabs-03`, [#94](https://github.com/junyeong-nero/kitsune-benchmark/issues/94)); Kitsune / Playwright input 0.985 |
| [Component gallery](gallery.md) | 21 tasks (custom widgets, shadow DOM, iframes, media puzzles, one hand-off), three variants, on a crowded page and one at a time | 42/42 both; input 0.625 crowded, 0.962 isolated |
| [Coexistence](coexistence.md) (frozen `coexistence-local-v2`) | The 28 personal tasks with tabs the user opened, a Kitsune arm with user tabs writable, and `co-typing-01`; 25 more tasks specified only | User's view moved: Playwright 26/28, Kitsune 0/28. Typing user's input kept: 0/3 vs 3/3 |
| [External](external.md) (`external-v1`) | 7 MiniWoB++ tasks graded by their own reward, 3 live sites recorded but not graded | MiniWoB++ 7/7 both; live tasks completed by both |
| [Full native](full-native.md) (`kitsune-full-native-v1`, Kitsune only) | 14 existing units (personal research, research → draft, long pages; gallery `ui-table` on both layouts) × `KITSUNE_CAPS=core` vs `KITSUNE_CAPS=all` + `KITSUNE_PUBLISH=core`, no allowlist; reported apart from the head-to-head | Not run yet |
| [Hostile UI](hostile.md) (draft, no model) | 26 real-web components that resist automation × scripted tool strategies | Kitsune v0.7.1: Playwright 23/26, Kitsune 20/26 |
| [Personal state](personal-state.md) (specification only) | Tasks that need a personal profile's history, bookmarks or logins | Not implemented |

WebArena-style tasks and real personal accounts are not implemented.

## Reference

| Document or file | Covers |
| --- | --- |
| [Task catalog](../tasks/personal/catalog.json) | Each personal task's request, starting state, success and safety criteria |
| [Personal execution config](../configs/benchmarks/personal.json) | Model and version pins, the default pilot tasks, the time budget |
| [Codex harness](codex-harness.md) | Authentication, isolation, tool policy, process cleanup and trace audit for the Codex harness |
| [Resource methodology](resources.md) | What the CPU/RSS numbers include and how to read them |
| [Optimization findings](optimization-findings.md) | Cache, observation and schema evidence, native RPC logs, offline analysis |
| [MCP comparison candidates](comparison-candidates.md) | Other MCP servers and browsers worth adding; none are adapters yet |
| [Experiment plans](experiments/) | Preregistered A/B plans; their results are in the [results index](results/README.md) |

The catalog and configs are executable inputs, the guides describe the protocol, and dated reports describe what
actually ran. Raw logs, session state, profiles and resource samples stay in the gitignored `artifacts/`; published
reports contain reviewed summaries.

## Reading results correctly

- Look at the grader's `scorable` and `task_success`, not at the exit code or the agent's final answer.
  `completed_unscored` can come with a successful external evaluation.
- Input tokens already include cached input. Cost figures are Claude Code's list-price estimate; missing usage is not
  zero cost.
- Personal and gallery time includes the harness's own setup and inventory calls, recorded apart from the agent's.
  Do not compare it with uninstrumented MiniWoB++ timings.
- Keep the model, tool policy, variant, browser, Kitsune revision and taskset tag in view. Single-attempt reports do
  not support general rankings.
- The fixtures are synthetic. Real logins, long-lived profile history, live-web reliability and prompt-injection
  robustness are untested.
