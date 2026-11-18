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

```sh
uv run --locked python scripts/run-five-surface.py run --scope repl-ab --out artifacts/repl-ab-v1
uv run --locked python scripts/run-five-surface.py summary --out artifacts/repl-ab-v1
```
