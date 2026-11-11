# Claude: scripting core vs new unset-CAPS default `c698d40`

[Results index](README.md) · [Frozen protocol](../experiments/2026-11-12-claude-caps-and-main.md) ·
[Separate Codex result](2026-11-12-codex-scripting-caps-ab.md)

**Claude favors the broader default in this small cohort; the Codex finding does not generalize to Claude.**
Both arms have **40/40 successful recorded grades**, with no unstarted or execution failures. Default/core input
is **0.885**, model requests **0.943**, calls **0.931**, elapsed **0.947**, list-price estimate **0.889**.
Python capability refusals fall **3 → 0**. However, two runs contain page-JS attempts outside the UI-only task
instruction, including one successful editor DOM write in core. These are not 80 fully conforming UI-only runs.
On the **38 matched cells with neither arm script-audit-flagged**, input is **0.935**, requests **0.976**, calls
**0.955**, elapsed **0.977**, list-price estimate **0.924**. This is a disclosed sensitivity analysis, not a
replacement for the frozen all-grade analysis or proof that the remaining scripts are confined.

## Setup and integrity

- Kitsune `c698d408d1c77eb708e853649bde4085a0d87ac8`, clean patched checkout in both arms. Scripting enabled;
  `core` explicitly sets CAPS=core, `default` leaves CAPS absent (all except storage/history). Both expose 14 tools.
  No benchmark allowlist. Explicit grants and user-tab/mode/approval protections remain intact.
- Claude Code `2.1.303`, `claude-opus-5-5`, medium, claude.ai subscription. Provider API keys are stripped; no API
  budget or fallback. The dollar figures below are CLI list-price estimates, **not subscription charges**.
- Benchmark `2fc4ae9`, clean, with `scripts/run-claude-scripting-caps-ab.py`; same 20 tasks × 2 arms × 2 repeats,
  original ABBA order, MiniWoB seed 42, personal/gallery variant 0 and isolated gallery as the Codex cohort.
  Task prompts/graders are unchanged. Same private Firefox fixtures and decline elicitation policy.
- 2026-11-12 approximately 00:53–01:26 KST. First two counted attempts checked, then the remaining 78; no retries.
- All 80 pair manifests confirm correct clean source/config/model and no allowlist/API budget. Every Claude init
  catalog has 14 tools; all 52 personal/gallery relay catalogs also have 14. Unlike Codex, MiniWoB inventory is
  observed in Claude init. Runner hashes and the complete 80-attempt schedule were verified after execution.
- All 80 executions: `completed_unscored`, no harness error/audit violation; all 52 personal/gallery safety grades
  pass. These checks do not enforce the UI-only instruction within arbitrary Python; see the separate script audit.

## Results

All 40 task/repeat cells have successful recorded grades in both arms.

| Metric | Core | Default |
| --- | ---: | ---: |
| Attempts / scorable / successful grades | 40 / 40 / 40 | 40 / 40 / 40 |
| Input tokens, including cache hits | 2,013,555 | 1,781,656 |
| Cached input tokens | 1,768,160 | 1,565,922 |
| Output tokens | 30,807 | 28,387 |
| Model requests | 230 | 217 |
| MCP calls | 291 | 271 |
| Summed agent elapsed | 775.713 s | 734.480 s |
| CLI list-price estimate | $2.931 | $2.605 |
| Median first-request input | 6,698 | 6,750 |
| Python calls / failed calls | 19 / 3 | 20 / 1 |

The wider capability guide slightly increases the initial prefix; the total input gain is not a smaller tool list.
Ratios are default/core. Cost ratios use unrounded per-run estimates, not rounded table totals. Elapsed includes
client/model/network and hidden relay work, not just native tools; MCP calls do not count each script operation.

| Track | Successful grades per arm | Input | Output | Requests | Calls | Elapsed | List-price cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MiniWoB | 14/14 | 0.938 | 0.982 | 0.947 | 0.939 | 0.968 | 0.967 |
| Personal | 14/14 | 0.916 | 0.968 | 1.000 | 0.974 | 1.006 | 0.883 |
| Gallery | 12/12 | 0.787 | 0.788 | 0.868 | 0.859 | 0.852 | 0.818 |
| **All** | **40/40** | **0.885** | **0.921** | **0.943** | **0.931** | **0.947** | **0.889** |

## Errors, script audit and limits

- Core: `pb-longpage-01` r0 `text()` refused without read; `ui-editor` r1 `html()` and `forms()` likewise refused.
  All three are capability errors, and the agent recovered to passing state grades. Default has **zero capability
  errors** and one `user_tab_read_only` refusal of page JS in `pb-longpage-01` r0. That protection is intended.
- `ui-infinite` passes **2/2 in both arms without Python**. Claude found a direct-tool route; the scroll permission
  failure observed with Codex is not exercised here. Do not claim broader CAPS improved this task for Claude.
- Script audit: default `pb-longpage-01` r0 (attempt 27) tries `evaluate("document.body.innerText")`, which is
  refused on a user tab. Core `ui-editor` r0 (attempt 40) makes **five evaluate calls**, including a successful
  `innerHTML` / `document.execCommand` edit. Both violate the UI-only task instruction; the latter's passing grade
  must not be presented as a UI-only completion. No literal Python URLs or MiniWoB reward-pattern hits were found.
- The primary table preserves all raw grades; no flagged run was retried, dropped or relabeled. Removing both
  affected matched cells leaves the 38-cell sensitivity above. Pattern matching is limited; Python has ordinary
  host filesystem/network access and is not a sandbox.
- Two repeats, one seed/variant and one model: the cost/request direction supports this configuration for Claude
  in this cohort, not a universal benefit or a statistically established task-success improvement. The separate
  Codex cohort had input 1.151 and calls 1.116 on jointly solved cells. Never pool those cohorts or infer a
  model-independent scripting-default decision from either alone.

## Reproduction and artifacts

```sh
uv run --locked python scripts/run-claude-scripting-caps-ab.py analyze \
  --out artifacts/claude-scripting-caps-default-c698d40
uv run --locked python -m unittest tests.test_codex_scripting_ab tests.test_codex_scripting_caps_ab \
  tests.test_claude_scripting_caps_ab tests.test_adapter tests.test_claude_harness tests.test_full_native tests.test_full_suite
```

93 targeted tests passed before execution. See the protocol for the run command; use a fresh output directory
for another cohort. Existing failed rows cannot be automatically skipped during resume.

Artifacts: `artifacts/claude-scripting-caps-default-c698d40/{manifest.json,continuation.json,runs.jsonl,analysis.json}`;
rows point to their private raw pair/event/grade directories under `artifacts/scripting-ab/`.
`runs.jsonl` SHA-256: `63f3bfbc732008b55a6e197d8ed4dbc0689849e376c3363be5c54948bb279bd5`.
No raw session URLs or credentials are published here. The additional main `883d80e` standard-lite baseline is a
separate experiment, not part of these 80 attempts. No default-on switch, main merge, push, issue or release.
