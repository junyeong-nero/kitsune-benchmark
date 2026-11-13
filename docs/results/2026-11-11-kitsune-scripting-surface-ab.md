# Kitsune tool surface A/B: legacy list vs `KITSUNE_SCRIPTING=1`

[Results index](README.md) · [Protocol](../experiments/2026-11-11-kitsune-scripting-surface-ab.md) ·
[Same-day cohort: Kitsune main `c0f80a2`](2026-11-11-main-c0f80a2.md)

**Bottom line:**

- **Supported by the protocol's rule, but cost went up.** Both arms solved 40/40. Input on matched cells, scripting
  over legacy: **0.893** (rule: ≤ 0.90). Model requests 1.129, output 1.11, list-price cost **1.087**, elapsed 1.17.
- **The smaller prefix works.** Median first request 10,582 → **7,574** tokens (−28%). In the 31 cells where the
  agent did not call Python, input is **0.764** with 154 → 157 requests, and cost 0.966.
- **Python, as published now, costs more than it saves.** In the 9 cells where the agent called it, input is 1.239,
  requests 56 → 80 and cost 1.407. **12 of 24 `browser_run_python` calls failed**, both on the tool's own description:
  - 8 × `capability_restricted`: the description offers `tab.query(...)`, which needs the `read` group, and the default
    `KITSUNE_CAPS=core` leaves it off;
  - 4 × `AttributeError: 'dict' object has no attribute 'snapshot'` (or `'query'`): `browser.tabs()` returns dicts,
    but the description reads as if it returned tab objects.
  After the failure the agent went back to direct tools and did the task as legacy does, so the Python calls were
  extra requests.
- **MiniWoB:** 0.756, no Python call. Per run: legacy 61.6k, scripting **46.6k**. The same-day exhibition: Aside 40.5k,
  ego 33.8k. Kitsune in the head-to-head (23-tool allowlist): 58.2k. Different runs, so these are rough.
- **Integrity:** no MiniWoB reward pattern in any Python code, and no URL in any Python code.

Two repeats per arm; read per-track differences as observations.

## Setup

- **Kitsune:** main `362c1fd` (`v0.7.3-29`), clean clone in `artifacts/vendor/kitsune-main-362c1fd/`. It is `c0f80a2`
  plus test-only changes (#497); `src/` and `extension/` are identical.
- **Arms:** `legacy` (default, 27 tools published) and `scripting` (`KITSUNE_SCRIPTING=1`, 14 tools). Kitsune only, no
  benchmark allowlist: each arm sees what Kitsune publishes. The published count was checked on every run.
- **Model and harness:** `claude-opus-5-5`, medium; Claude Code `2.1.303` on the subscription. Elicitation `decline`.
- **Units:** the 7 MiniWoB++ tasks; personal v0 `pb-{current,tabs,research,account,handoff,safe,longpage}-01`; gallery
  v0 isolated `ui-table`, `ui-autocomplete`, `ui-infinite`, `ui-shadow`, `ui-iframe`, `ui-editor`. 20 cells × 2 arms
  × 2 repeats = 80 runs, ABBA, repeat-major.
- **Run:** 2026-11-11, one invocation, 80/80 scorable, no stop. An earlier start on `c0f80a2` was stopped after 6
  runs when main moved; those runs are not counted.

## Results

Matched cells (task, repeat) both arms solved; ratios are scripting / legacy:

| Track | Cells | Successes L / S | Input | Requests | Calls | Cost | Cells with less S input | First request L → S |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| MiniWoB | 14 | 14 / 14 | **0.756** | 1.014 | 0.959 | 0.941 | 14/14 | 10,560 → 7,553 |
| Personal | 14 | 14 / 14 | 1.036 | 1.244 | 1.123 | 1.233 | 8/14 | 10,715 → 7,709 |
| Gallery | 12 | 12 / 12 | 0.870 | 1.117 | 1.195 | 1.049 | 9/12 | 10,582 → 7,574 |
| All | 40 | 40 / 40 | **0.893** | 1.129 | 1.087 | 1.087 | 31/40 | 10,582 → 7,574 |

By whether the scripting run called Python:

| Cells | n | Input | Requests L → S | Cost |
| --- | ---: | ---: | --- | ---: |
| No Python call | 31 | **0.764** | 154 → 157 | 0.966 |
| Python called | 9 | 1.239 | 56 → 80 | 1.407 |

The 9 Python cells are `pb-tabs-01` ×2 (1.67, 1.43), `pb-longpage-01` ×2 (1.40, 1.32), `pb-safe-01` ×2 (1.34, 1.14),
`ui-editor` ×2 (1.09, 1.01) and `ui-infinite` ×1 (0.89). One cell above 1.10 without Python: `ui-iframe` r0 (1.24, 3 → 5
requests).

## Why the Python calls cost requests

`pb-tabs-01` r0, scripting:

1. `browser_tabs list`.
2. `for t in browser.tabs()[:4]: print(browser.tab(t.id).snapshot() if hasattr(t,'id') else '')`: prints the dicts,
   no snapshots.
3. `for i in [1,2,3,4]: print(i, browser.tab(i).snapshot())`: works.
4. `browser.tab(i).query("body", fields=["text"])`: `capability_restricted`, "/api/query needs the read capability".
5. Back to direct tools: `tabs new`, screenshot, three `navigate`s, `type`, `click`. 10 requests against legacy's 5.

`pb-safe-01` r0 and `pb-longpage-01` r0 follow the same path: one `'dict' object has no attribute 'snapshot'`, one working
snapshot loop, one `query` refused, then direct tools.

The `browser_run_python` description (`src/kitsune/server.py`):

```
browser.tabs(), browser.tab(id), browser.new_tab(url);
tab.snapshot(), fill(target, value), query(selector, fields=["text", "href"]).
```

## Issue candidates (Kitsune)

### S1. The Python tool offers `tab.query` when `read` is off (medium)

Filed as [kitsune#519](https://github.com/junyeong-nero/kitsune/issues/519).

- 8 of 24 Python calls, one in each of 8 of the 9 runs that used Python, stopped on `capability_restricted`.
- **Proposal:** build the description from the enabled groups. Under `core`, name only what `core` allows, or name
  `query` with "needs `KITSUNE_CAPS=…,read`". Alternatively let `KITSUNE_SCRIPTING=1` say in its docs which groups
  the description assumes.
- **Acceptance:** with `KITSUNE_CAPS=core`, the description names no method that returns `capability_restricted`.

### S2. `browser.tabs()` returns dicts, and the description reads as tab objects (medium)

Filed as [kitsune#520](https://github.com/junyeong-nero/kitsune/issues/520).

- 4 of 24 Python calls failed with `AttributeError: 'dict' object has no attribute …`.
- **Proposal:** return tab objects from `browser.tabs()`, or say "`browser.tabs()` → list of dicts with `id`; use
  `browser.tab(id)`" in the description.
- **Acceptance:** `for t in browser.tabs(): t.snapshot()` works, or the description says it does not.

### S3. The remaining prefix is still about 2.5k tokens above Aside's (low)

Filed as [kitsune#521](https://github.com/junyeong-nero/kitsune/issues/521).

- Scripting's first request is 7.5k; Aside's 5.05k and ego's 4.8k (same harness and prompt shape). The 13 retained
  direct tools are the difference.
- Only worth doing after S1 and S2, and only with a measurement: the direct tools are what the agent used in 31 of
  40 cells.

## Artifacts

- Runs log and analysis: `artifacts/scripting-ab/runs.jsonl`, `artifacts/scripting-ab/analysis.json`
  (`scripts/run-scripting-ab.py analyze`).
- Driver log: `artifacts/scripting-ab.driver.log`. Smoke runs: `artifacts/scripting-ab-smoke/`. Stopped start on
  `c0f80a2`: `artifacts/scripting-ab-c0f80a2-aborted/`.
