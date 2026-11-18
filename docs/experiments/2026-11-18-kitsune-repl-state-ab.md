# Kitsune A/B: persistent Python variables in `browser_run_python`

Follow-up to the [five-surface comparison](2026-11-17-five-surface.md). Aside's single
`repl` tool used fewer calls than Kitsune's code-first surface with a catalog of about the
same size. One design difference is state. In Aside, variables, helper functions and page
handles persist between calls. In Kitsune, every `browser_run_python` call starts a fresh
process, so the agent fetches `browser.tab(id)` again and redefines its helpers.

## Treatment

| Arm | Kitsune | `browser_run_python` |
| --- | --- | --- |
| base | `14d9ceb` (main) | fresh process and variables per call |
| repl | `5a9c5fc` (`feat/persistent-python-state`) | one worker per MCP session; variables, functions and Tab handles persist; `tab` and `result` are reset per call |

The candidate keeps the existing stop semantics. A failed browser operation stops even a
catching script: further requests are refused, and the variables are kept. A timeout,
cancellation, output overflow or protocol error kills the worker; the result then carries
`state_reset: true`. The only model-visible change is two sentences in the tool description.

## Matrix

Codex `gpt-6.1-sol` and Claude Code `claude-opus-5-5` (medium), × the 23 expanded
conditions × 2 arms = **92 attempts**, one repeat. A/B order alternates per condition.
Personal starting tabs are agent-owned in both arms (`kitsune_seeding="agent"`), so the
user-tab protection does not confound the comparison. Same private Zen runtime, relay
and graders as the five-surface cohort.

## Hypothesis and decision rule

H: within each model, repl/base median paired input ≤ 0.90 and calls ≤ base, with no loss
of success. Report personal / isolated / crowded separately. Count how often a later call
actually reuses a name defined earlier. Without reuse, a difference is not attributable
to the feature. One repeat: treat differences within ±10% as inconclusive.

## Result (2026-11-18, `artifacts/repl-ab-v1`): not supported

All 92 attempts ran; 91 were scorable (one base Codex `pb-handoff-01` timed out at 180 s).
Success: Codex base 21/22, repl 22/23; Opus 23/23 both. The only shared miss is `ui-toast`
in both Codex arms. Paired repl/base input on jointly scorable conditions:

| Model | personal | isolated | crowded | all (median / geomean) | Δ calls (sum) | runs reusing a name |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex | 1.14 | 1.00 | 0.87 | 1.00 / 1.00 | −3 | 1/23 (1 of 108 calls) |
| Opus | 0.83 | 1.21 | 1.03 | 1.00 / 1.02 | +3 | 9/23 (21 of 102 calls) |

Codex almost never used the persisted state. Opus reused variables in 9 runs; the
clearest case is `ui-infinite@crowded`, which reused a list collected in the previous
call (6 calls vs 15 for base). Per-track ratios move in both directions without reuse, so
they are single-repeat variance. No `state_reset` occurred. The decision rule (≤ 0.90) is
not met: as exposed, persistence changes no efficiency. The models do not plan around the
state, and Kitsune's per-call overhead is not dominated by re-fetching handles.

```sh
uv run --locked python scripts/run-five-surface.py run --scope repl-ab --out artifacts/repl-ab-v1
uv run --locked python scripts/run-five-surface.py summary --out artifacts/repl-ab-v1
```
