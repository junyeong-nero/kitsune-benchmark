# Scripting guide rerun (kitsune#519 / #520): legacy vs `KITSUNE_SCRIPTING=1`

[Protocol](../experiments/2026-11-11-kitsune-scripting-surface-ab.md) ·
[Rerun addendum](../experiments/2026-11-11-kitsune-scripting-guide-ab.md) ·
[Previous run (362c1fd)](2026-11-11-kitsune-scripting-surface-ab.md)

**Bottom line:**

- **Both arms 40/40.** Matched input, scripting / legacy: **0.884** (rule ≤ 0.90: supported). Requests 1.094,
  list-price cost **1.072**, output 1.101, elapsed 1.103. Previous run: 0.893 / 1.129 / 1.087.
- **The two guide errors are mostly gone.** Python calls 29, failed **5** (previously 24 calls, 12 failed):
  - `capability_restricted`: **1** (was 8). It came from `tab.text()`, which the guide does not mention; the
    agent found it through `help(browser.tab(1))`. `query` was not called.
  - `AttributeError` on a tab dict: **0** (was 4). The remaining `AttributeError` is `Tab.press_key`, a method
    that does not exist.
  - Other failures: `find(regex=...)` (TypeError) and twice `tab.evaluate("expression")` instead of a function.
- **Python still costs more than it saves.** In the 8 cells that used Python, input 1.261, requests 52 → 72,
  cost 1.366. In the 32 cells without Python, input **0.754**, requests 160 → 160, cost 0.966. Python mostly
  served as an extra read step (several tab snapshots) before the same direct actions; legacy reads the same
  tabs with parallel direct calls in fewer requests.
- **Integrity:** no URL in Python code. 15 reward/page-JS pattern hits, all `.evaluate(` in `ui-editor`.
  In `ui-editor` r1 the scripting run inserted text with `document.execCommand('insertText')`, which is not UI
  input. Legacy ran `browser_evaluate` 4× in both `ui-editor` repeats too (the protocol's known limitation; the
  detector checks only Python). Without `ui-editor`: input 0.835, requests 194 → 205, cost 1.035.

Two repeats per arm; read per-track differences as observations.

## Setup

- Kitsune snapshot `20838b68e5e3afb494e38d91a403167b0e007eb1` (main `89d883a` + the #519/#520 guide patch),
  clean, in `artifacts/vendor/kitsune-scripting-guide-519-520-20261111/`. Both arms ran it; legacy's surface
  is unchanged by the patch. The previous run used `362c1fd`, so the comparison with it is descriptive.
- Runner, tasks, order and stops unchanged (`scripts/run-scripting-ab.py`). `claude-opus-5-5`, medium,
  Claude Code 2.1.303, subscription. 80/80 scorable, no stop, published 27 / 14 on every run.
- A first smoke attempt at 16:44 KST stopped on `usage_limit_reached` (0 tokens, kept at
  `artifacts/scripting-ab/20261111T074432Z-06dfdad193/`). After the 17:00 reset the three uncounted smokes
  passed, then the 80 counted runs ran 17:02–17:35 KST.

## Results

| Track | Cells | Successes L / S | Input | Requests | Cost | Cells with less S input | First request L → S |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| MiniWoB | 14 | 14 / 14 | **0.735** | 0.973 | 0.954 | 14/14 | 10,558 → 7,616 |
| Personal | 14 | 14 / 14 | 0.955 | 1.145 | 1.124 | 10/14 | 10,715 → 7,772 |
| Gallery | 12 | 12 / 12 | 0.968 | 1.175 | 1.129 | 11/12 | 10,581 → 7,639 |
| All | 40 | 40 / 40 | **0.884** | 1.094 | 1.072 | 35/40 | 10,581 → 7,639 |

The patch adds about 65 tokens to the scripting first request (7,574 → 7,639).

| Cells | n | Input | Requests L → S | Cost |
| --- | ---: | ---: | --- | ---: |
| No Python call | 32 | **0.754** | 160 → 160 | 0.966 |
| Python called | 8 | 1.261 | 52 → 72 | 1.366 |

Python cells (input ratio, requests): `pb-tabs-01` 1.21 / 1.71 (5 → 8 both), `pb-longpage-01` 1.12 / 1.16,
`pb-safe-01` 0.98 / 0.99, `ui-editor` 2.45 (8 → 19) / 0.59 (10 → 8).

## Reading for the issues

- **#519:** the guide no longer names `query` under `core`; no `query` refusal. The issue's literal rerun
  check (no `capability_restricted` in Python results) is not met: one call to an unadvertised `read` method.
- **#520:** met. No `AttributeError` on tab dicts; every tab loop wrapped `t['id']` with `browser.tab(...)`.
- **#521:** the prefix saving holds where Python is not used (0.754 input, cost 0.966). The cost overrun now
  comes from extra Python request rounds, not from failures. Moving more direct tools into Python would push
  more work into that path, so this run does not support removing direct tools. A smaller prefix by trimming
  retained-tool schemas in the scripting surface only would need its own A/B.

## Artifacts

`artifacts/scripting-guide-ab-519-520/{runs.jsonl,analysis.json,driver.log}`; per-run directories under
`artifacts/scripting-ab/` (listed in `runs.jsonl`).
