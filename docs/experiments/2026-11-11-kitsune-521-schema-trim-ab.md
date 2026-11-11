# Protocol: scripting-surface schema text (kitsune#521, PR kitsune#523)

Frozen before counted runs. Completed 2026-11-11, 80/80: [results](../results/2026-11-11-kitsune-521-schema-trim-ab.md). Runner: `scripts/run-schema-trim-ab.py`, which reuses the tasks, order, metrics and
stops of `scripts/run-scripting-ab.py` ([original protocol](2026-11-11-kitsune-scripting-surface-ab.md)).

## Question

The [#519/#520 rerun](../results/2026-11-11-kitsune-scripting-guide-ab.md) found the scripting surface's prefix
saving holds where Python is not used, and did not support moving more direct tools into Python. The remaining
#521 candidate is shorter schema text for the retained tools on the scripting surface only. PR #523 does that:
the 11 retained Playwright tools publish shorter parameter descriptions and no `$schema`; names, types, enums,
`required`, defaults and `additionalProperties` are unchanged, and the legacy list stays verbatim. Tool
definitions: 12,589 → 9,647 compact JSON characters. Does it lower input without more argument errors,
requests or cost?

## Arms

Both `KITSUNE_SCRIPTING=1`, 14 published tools, default `KITSUNE_CAPS=core`, act mode, read-only user tabs, no
benchmark allowlist.

| Arm | Kitsune | Snapshot |
| --- | --- | --- |
| `base` | main `7b089d9fba9294e433f883bd8fe7874889548d03` | `artifacts/vendor/kitsune-521-base-7b089d9/` |
| `trim` | PR #523 `695fdd80b8ffaaef0a0b8c93f3daee573003bf57` (main + one commit) | `artifacts/vendor/kitsune-521-trim-695fdd8/` |

`git diff 7b089d9 695fdd8` touches only `src/kitsune/server.py` (the scripting schema text), a test and docs.

`claude-opus-5-5`, medium, Claude Code `2.1.303`, subscription. Elicitation `decline`.

## Units

The same 20 cells (7 MiniWoB++, 7 personal v0, 6 gallery v0 isolated) × 2 repeats × 2 arms = 80 runs, in the
original repeat-major ABBA order with `base` in legacy's place and `trim` in scripting's.

## Estimands

- **Primary:** trim / base input tokens summed over matched (task, repeat) cells both arms solved.
- **Secondary:** success, first-request input (median), requests, MCP calls, output, list-price cost, Python use.
- **Risk:** failed tool results per arm, and argument-validation errors (`InputValidationError` or
  `validation error` in a failed result) per arm and tool.

## Reading

- Supported: overall joint input ratio ≤ 0.95, successes not lower by more than 1 in any track, joint cost ratio
  ≤ 1.00, and trim validation errors not above base + 2.
- Not supported: input ratio ≥ 1.00, or cost ratio > 1.05, or more than 2 extra validation errors.
- Otherwise inconclusive. The expected prefix saving is about 2.9k characters (roughly 0.7–0.8k tokens) per
  request, about 7–9% of input, close to repeat-to-repeat noise; two repeats are a small descriptive sample.

## Integrity and stops

Keep the original URL / reward-pattern audit of Python code. Stop on a harness error, two unscorable runs in a
row, either snapshot's revision changing or becoming dirty, or a published tool count other than 14. No retries
or substitutions.

## Smoke (not counted)

`mw-click-test-2` in each arm and `pb-current-01` in `trim`, logged to `smoke.jsonl`. Do not start counted runs
if one fails, is unscorable or publishes other than 14 tools.

## Artifacts

`artifacts/schema-trim-ab-521/{runs.jsonl,smoke.jsonl,analysis.json,driver.log}`; per-run directories under
`artifacts/scripting-ab/`.
