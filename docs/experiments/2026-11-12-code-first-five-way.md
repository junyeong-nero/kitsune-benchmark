# Code-first Python five-way experiment — 2026-11-12

Operator approved a Python-based implementation and **7 MiniWoB tasks × 5 arms × 2 repeats = 70 attempts**.
Do not merge or discard the implementation: the operator will decide after reviewing the results.
This is a new cohort; do not pool historical samples or tune implementation after seeing outcomes.

## Fixed sources and treatment

- Kitsune baseline: `47dafa20a3fddc697a7d991e15d39e4b0232c10d`, actual default fourteen tools.
- Kitsune code-first: `f5c7a0f85aefd89e621e73665e33d33d79d50676`, branch `experiment/code-first-tools`.
- Same Python/bridge/extension API. The treatment changes the default list and guidance, not the browser engine.
- Six tools: Python execution, tabs, screenshot, ask-user, resume, and a direct recovery dispatcher.
- The dispatcher describes a named direct tool when arguments are omitted; an explicit object executes it.
  Old direct names remain callable for compatibility. Catalog visibility is not authorization.
- Ordinary observation/input/waits use Python. Known actions may be grouped; unknown targets must be observed.
  The compact guide shows actual API signatures, including snapshot(text=True), scrolling and keyboard input.
- A script stops on action approval, never replays previous work, and names a direct recovery tool.
  Normal existing elicitation and non-eliciting token fallback remain in that dispatcher. No new sandbox,
  persistent REPL, automatic script continuation, page-JS capability, or permissions bypass is introduced.
- Kitsune settings are unchanged in both arms, including default tool approvals and read-only user tabs.

| Arm | Source/configuration | Initial tools |
| --- | --- | ---: |
| kitsune-default | baseline, scripting unset, no benchmark allowlist | 14 |
| kitsune-code-first | implementation, scripting unset, no benchmark allowlist | 6 |
| playwright | installed pinned MCP, standard UI allowlist | 23 |
| ego | installed browser + vendor guide, run_script only | 1 |
| aside | installed native MCP, repl only; no delegated-agent exec | 1 |

Vendor versions, guide digest and catalogs are acquired without model inference, frozen in preflight,
and rechecked before/after each attempt. The runner manifest records the benchmark commit and sources.

## Constants and stopping rules

Reuse the existing five-way machinery, not new grading or task prompts:

- Claude Code 2.1.303, `claude-opus-5-5`, medium, claude.ai subscription. No paid-model API fallback,
  no vendor-agent delegation, no subagents. Doctor checks credentials/configuration, not remaining quota.
- MiniWoB `33c3b4ddef8c6eb67c57a29663d844b1eda7e614`, seed 42. Seven tasks:
  click-test-2, click-checkboxes, enter-text, choose-list, login-user, use-autocomplete, book-flight.
- Two repeats; sequential rotated arm order, reversed per task on repeat 1. No episode retries/replacements.
- 120-second episodes / 180-second harness limit; existing MCP envelopes remain 45 seconds for
  Kitsune/Playwright and 130 for vendor script tools. Report this difference, do not attribute it to language.
- Shared unique fresh-context instruction for every arm, prefix `bm-code-first-20261112-v1-SEQ`.
  Do not close/claim unrelated contexts or change signed-in browser state to make tests pass.
- Run first five attempts and audit them before the remaining 65. After a normal no-start attempt with
  no telemetry errors, `--continue-unstarted` may proceed to the next cell; that attempt stays unscorable
  and included. Quota, execution, source/catalog drift or other unscorable errors stop for review.
- No silent quota retry, model substitution, cost-path change, implementation tuning or benchmark rerun.

Kitsune/Playwright use fresh private headless Firefox; Aside/ego use installed warm browsers, not isolated
profiles. Do not purge/update them. Engine, viewport, cache and profile differences preclude a causal
cross-product comparison. The two Kitsune arms are the primary same-environment comparison.

## Product validation before inference

- 172 related Python unit/in-memory MCP tests passed, including approval rejection, no replay, direct
  recovery, compatibility, schemas, Python transport and user-tab protection.
- Three actual stdio MCP tests passed on a private headless Zen profile, including approval-stop draft
  preservation and direct non-eliciting recovery. The first launch used a nonexistent Firefox app path
  and failed before any test; corrected to the installed Zen binary, then all three passed.
- tab_handoff.cjs, tab_handoff_races.cjs, popup.cjs passed. diff whitespace check passed.
- Negative-path MCP cancellation/late-response diagnostics and the existing Python gather cancellation
  warning can be logged while assertions pass; no full product-suite certification is claimed.

## Commands

From the clean benchmark branch `experiment/code-first-efficiency`:

```sh
uv run --locked python -m kitsune_benchmark doctor --harness claude --json
uv run --locked python scripts/run-code-first-five-way.py preflight \
  --out artifacts/claude-code-first-five-way
uv run --locked python scripts/run-code-first-five-way.py run \
  --out artifacts/claude-code-first-five-way --continue-unstarted --limit 5
# Audit those five attempts, then only unattempted cells:
uv run --locked python scripts/run-code-first-five-way.py run \
  --out artifacts/claude-code-first-five-way --continue-unstarted
uv run --locked python scripts/run-code-first-five-way.py analyze \
  --out artifacts/claude-code-first-five-way
```

## Required analysis

Report attempted/unstarted/scorable/success counts, all-attempt input including cache, cached input,
output, model requests, MCP calls, script errors, elapsed harness time and list-price estimates
(not subscription bills). Compare identical joint-success task/repeat sets; keep failed effort in totals.
Also report all-five joint successes and per-task variability, not just total tokens or average time.

Audit code/arguments for page evaluate, reward/source/timer access, DOM mutation, wrong targets,
TaskSpace reuse, direct compatibility calls and recovery dispatcher use. Regex flags are not a compliance
or confinement guarantee. Disclose any remaining approval/client UX limitations and benchmark coverage gaps:
these seven tasks do not cover scrolling, dragging, user handoff or mid-script approval end-to-end.
Do not claim Python-vs-JS causality, general superiority, or statistical confidence from fourteen runs/arm.
