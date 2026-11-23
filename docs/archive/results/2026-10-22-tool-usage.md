# Existing-run tool usage: candidates for a smaller default surface

[Reports](README.md) · [Opus/Sonnet follow-up](2026-10-22-sonnet-opus-target-view.md)

## Scope and counting

Offline analysis of **196 existing Kitsune v0.3.0 runs**, with **2,084 agent tool
calls**, across six separately reported cohorts. No new model/browser calls.

| Cohort | Runs | Agent tool calls |
| --- | ---: | ---: |
| Haiku personal, bare descriptions | 24 | 227 |
| Haiku personal, full descriptions | 24 | 253 |
| Haiku disclosure experiment | 72 | 769 |
| Haiku target-view experiment | 60 | 694 |
| Sonnet selected cases, native + catalog | 8 | 65 |
| Opus selected cases, native + catalog | 8 | 76 |

All have the same **14 advertised tools**. Here “full descriptions” does **not**
mean the Kitsune full tool preset: the actual exposed catalog is still lean.

Counts come from unique assistant `tool_use` IDs in `events.jsonl`; completions
and `is_error` come from matching `tool_result` IDs. They match every run's
existing audited `mcp_calls` and the **2,084 agent-role native RPCs**. There are
no missing results. Excluded: **3,853 harness calls** (setup, grading, cleanup)
and **80 disclosure-enrichment calls**, which were not agent selections.

Exposure is reconstructed from each run's native tools/list intersected with
its enabled tools. Unadvertised tools do not get a fictitious 0% use rate.

The pooled data deliberately combines repeated/selected tasks and experimental
conditions. It is useful for finding candidates, **not an estimate of production
frequency or a controlled model comparison**. The JSON also splits each
experiment by arm; both arms are combined in the tables below for inventory.

## Counts by cohort

Each cell is **calls / runs using the tool**. The denominators are in headings.

| Tool | Haiku bare, 24 runs | Haiku full descriptions, 24 | Sonnet, 8 | Opus, 8 |
| --- | ---: | ---: | ---: | ---: |
| `browser_page_text` | 52 / 21 | 55 / 18 | 4 / 3 | 8 / 7 |
| `browser_tabs` | 43 / 24 | 45 / 24 | 4 / 2 | 4 / 2 |
| `browser_snapshot` | 46 / 22 | 52 / 21 | 10 / 8 | 12 / 8 |
| `browser_click` | 28 / 23 | 31 / 23 | 19 / 8 | 21 / 8 |
| `browser_type` | 22 / 15 | 22 / 12 | 4 / 4 | 6 / 4 |
| `browser_screenshot` | 0 / 0 | 1 / 1 | 19 / 5 | 17 / 4 |
| `browser_forms` | 11 / 9 | 18 / 9 | 0 / 0 | 1 / 1 |
| `browser_navigate` | 7 / 5 | 6 / 6 | 2 / 2 | 0 / 0 |
| `browser_form_fill` | 9 / 8 | 13 / 11 | 0 / 0 | 0 / 0 |
| `browser_dom` | 7 / 7 | 5 / 5 | 0 / 0 | 3 / 2 |
| `browser_find` | 1 / 1 | 2 / 2 | 3 / 2 | 4 / 4 |
| `browser_page_info` | 0 / 0 | 1 / 1 | 0 / 0 | 0 / 0 |
| `browser_select_option` | 1 / 1 | 2 / 1 | 0 / 0 | 0 / 0 |
| `browser_status` | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

Two useful counterexamples to frequency-only pruning:

- Screenshot appears almost unused in the 48 personal runs (**1 call**), but
  Opus makes **17 calls** in just eight runs once chart/video tasks are included.
- Find is uncommon in the broad personal Haiku cohort (**3/48 runs**) but used
  in **4/8 Opus runs**. The task sets also differ, so this is not a causal model
  effect; it does show why the small personal cohort is insufficient for pruning.

## Pooled inventory: 196 runs

| Tool | Calls | Runs used / 196 | Tool-result errors |
| --- | ---: | ---: | ---: |
| `browser_page_text` | 391 | 164 | 0 |
| `browser_tabs` | 349 | 184 | 0 |
| `browser_snapshot` | 332 | 170 | 3 |
| `browser_click` | 309 | 194 | 104 |
| `browser_type` | 215 | 123 | 96 |
| `browser_screenshot` | 164 | 38 | 6 |
| `browser_forms` | 120 | 80 | 0 |
| `browser_navigate` | 66 | 54 | 1 |
| `browser_form_fill` | 52 | 45 | 28 |
| `browser_dom` | 42 | 35 | 2 |
| `browser_find` | 32 | 26 | 0 |
| `browser_page_info` | 8 | 8 | 0 |
| `browser_select_option` | 3 | 2 | 1 |
| `browser_status` | 1 | 1 | 0 |

There are **no universally unused tools among the 14 advertised tools** across
this entire corpus. The low-use tail is status, select-option and page-info.

### Tool-result errors are not identical to action failure

Of the **241 error results**:

- **122**: expected outcome not observed;
- **36**: invalid expect specification;
- **57**: target missing;
- **24**: stale ref;
- **1**: ambiguous target;
- **1**: other (non-scriptable HTTP 404 document).

In particular, form-fill's **28/52** error results are **20 outcome-unmet + 8
expect-validation errors**. They do not establish 28 failed form edits. A write
can have been dispatched before outcome verification fails. These categories
are conservative string-based diagnostics, not a semantic replay of each edit.
Do not deprecate an action tool merely because its `is_error` rate looks high.

## Recommendations

### Test removing from the default surface, not deprecating the API

**`browser_status` and `browser_page_info`** are the first default-surface
candidates: 1 and 8 calls respectively, with neither used in the selected
Sonnet/Opus cohort. Keep them available in an opt-in/full/diagnostic surface.

Caveats:

- Benchmarks start from a working connection and provisioned tabs. This excludes
  much of the reason a user might need a connection/status diagnostic.
- Existing traces do not prove that the eight page-info callers would succeed
  without it, nor that its information is redundant in every situation.
- Their raw native definitions are small (287 and 357 compact JSON characters).
  Removing them is not automatically a large token saving. These are **not**
  measured model-input tokens or a forecast of API savings.

### Keep pending relevant coverage

- **`browser_select_option`:** specialized support can be rare but essential for
  native selects. Custom dropdowns solved by click do not test this capability.
  Exercise relevant native-select cases and fallback quality before removal.
- **`browser_form_fill`:** unused in the eight Opus cases, but used in 45/196
  pooled runs. The selected Opus cases are not a multi-field-form benchmark.
  Test its batching value versus repeated type calls, and fix expect behavior.
- **`browser_find`, `browser_dom`, `browser_forms`:** lower counts than basic
  observations do not establish redundancy. Evaluate targeted recovery and
  structured form inspection separately.
- **`browser_navigate`:** Opus's zero count here is not evidence for removal;
  tab creation and pre-opened fixtures can avoid direct navigation.

### No conclusion about tools that were not advertised

The configured allowlist included names such as `browser_scroll`,
`browser_hover`, `browser_keypress`, `browser_check`, `browser_submit_form`,
`browser_focus`, `browser_drag`, and `browser_double_click`, but they were absent
from the native lean tools/list in these runs. They were **not unused choices**;
they were unavailable choices. Some names may also be outside the current core
preset or belong to different capabilities. Check actual availability/version
before making a migration decision.

Other full-preset functionality (e.g. dialogs or file upload) likewise cannot be
judged from a lean-only experiment. The coverage of its use cases matters more
than a zero in an inapplicable table.

## Next Opus full test

Keep the current 14-tool surface unchanged for the first full baseline, then
attach this offline summary. Report per-tool:

1. Calls and **used runs / exposed runs**, by task family and layout.
2. Opus native baseline separately from any formatting experiment.
3. Error categories, recovery behavior, and any unadvertised attempts.
4. Whether the fixture actually presented the relevant affordance, not only
   whether its schema was advertised (this opportunity denominator is **not yet
   implemented** in the current analyzer).
5. A subsequent controlled smaller-surface ablation: success/safety, fallback
   calls, total tokens/time/cost. These counterfactual effects cannot be inferred
   from existing usage logs.

A sensible first ablation is **14 tools vs 12 tools without status/page-info in
the default advertised surface**, while retaining those APIs for diagnostic
clients. Do not apply that reduction before recording the agreed Opus baseline.
Only use deprecation when there is a tested replacement and a migration plan.

## Reusable offline collector

Added `kitsune_benchmark/tool_usage.py`. It accepts existing personal/gallery
suite summaries (`pairs`) or disclosure/target-view summaries (`runs`), and can
analyze either target. It does not change runners, presets or tool availability.

```sh
uv run --locked python -m kitsune_benchmark.tool_usage \
  --cohort opus=artifacts/target-models-20261022/opus/summary.json \
  --output /tmp/opus-tool-usage-new.json \
  --csv /tmp/opus-tool-usage-new.csv
```

Repeat `--cohort LABEL=PATH` for additional independent cohorts. Output paths
must be new. Duplicate run directories across cohorts are rejected to avoid
accidental double counting. Derived reports do not retain arbitrary tool input
arguments or result bodies. Raw traces remain private.

Current artifacts:

- `artifacts/tool-usage-20261022/analysis.json`: exposure, calls, used runs,
  error rates/categories, arm splits, role-separated RPC counts and run manifest.
- `artifacts/tool-usage-20261022/by-cohort.csv`: flat per-cohort/per-tool counts.

Validation: **5 focused unit tests passed**; all 196 run counts reconcile with
existing audits, and all 2,084 agent calls have matched results. No additional
paid experiment or tool removal has been performed.
