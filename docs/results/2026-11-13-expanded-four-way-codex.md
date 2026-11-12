# Expanded four-way: 184/184 raw successes, task-dependent efficiency

[Results index](README.md) · [Frozen protocol](../experiments/2026-11-13-expanded-four-way-codex.md) ·
[Earlier interrupted Opus A/B, kept separate](2026-11-12-code-first-expanded-ab.md)

**All four configurations completed 46/46 attempts with passing functional/task and recorded safety
scores.** There were no unscorable attempts, missing final token records, quota stops, replacements or
harness retries. This is the newly authorized **184-attempt Codex cohort**, not the continuation of
the stopped 85-row Opus experiment. No new Claude inference or paid API fallback was used.

**Conclusion:** Aside is particularly efficient on isolated UI tasks; Kitsune is more competitive on
the crowded layouts. EgoLite completes the work but has higher aggregate input and time in its tested
native environment. The code-first candidate reduces total input by only **2.9%**, with **4.8% more
instrumentation-adjusted time**, versus Kitsune default. **Keep the existing merge hold and 14-tool
default.** This comparison does not justify a universal single-tool/code-first default or a JS-vs-Python
language verdict. Native browsers, permissions, images and effective viewport behavior differ.

## 1. Frozen cohort and audit coverage

- Execution commit **`e5db230a78ad006cfb8a12fbee6621b087a03e07`**, benchmark branch
  `experiment/code-first-expanded-four-way`, taskset description **`taskset-v3.5-42-ge5db230`**.
  Report/audit additions are post-execution; the execution
  runner, protocol, adapters and their frozen hashes are unchanged.
- Kitsune default **`47dafa20a3fddc697a7d991e15d39e4b0232c10d`**, actual **14 tools**;
  code-first **`f5c7a0f85aefd89e621e73665e33d33d79d50676`**, actual **six tools**. Both already support
  Python. No product changes, CAPS/scripting overrides, benchmark allowlist or merge.
- Aside CLI/native MCP **1.26.1107.24**, app **1.0.1022.1**, native **`repl` only**.
  EgoLite CLI/app **0.6.2.9**, Chromium **156.0.8078.74**, Node **v24.22.1**, **`run_script` only**;
  native guide plus the predeclared screenshot attachment bridge. No vendor-agent delegation.
- **Codex CLI 0.163.0**, requested **`gpt-6.1-sol`**, **medium**, ChatGPT subscription login. The switch
  from planned Opus execution happened before any counted attempt. Every run manifest records the
  same requested model/effort, forced ChatGPT auth and passing sanitized-environment preflight.
  Codex JSONL does **not** independently attest the backend model identity or report Claude-style
  request/first-request usage maps. Do not infer them from MCP calls.
- **23 conditions x two repeats x four arms**, variant 0: seven personal, ten isolated gallery and six
  crowded gallery conditions, listed individually below. No MiniWoB or Playwright arm. The two layouts
  are distinct conditions. Fixture nonces and generated report-confirmation codes remain per-trial,
  not hard-coded answers shared across attempts.
- Sequential rotated arm order, reversed in repeat 1. First **eight** attempts audited before the other
  **176**. Personal limit **180 s**, gallery **240 s**; MCP envelope Kitsune **45 s**, vendors **130 s**
  around their native **120 s** script limits. No post-outcome changes or favorable reruns.
- Audit checks **184 actual model-facing catalogs**, **368 before/after catalogs**, **184 evaluations**,
  usage against final JSONL, source/config fingerprints, and **1,369 MCP calls / 817 script calls**.
  Actual catalogs remain **14 / 6 / 1 / 1**. All 926 task-specific normalized argument groups covering
  those calls were reviewed, together with reported errors and selected result traces.
- Ego used **46 distinct prepared TaskSpaces, IDs 48–93**. Its one numeric TaskSpace reference, in
  attempt 103, matches that attempt's prepared ID 73. Aside used fresh scoped REPL tab sets. There
  were no recorded cleanup errors. These contexts are **not isolated browser profiles**.

## 2. Complete, identical comparison denominator

All-attempt and all-four-joint-success sets are identical: **46 condition/repeat cells, 184 attempts**.
Every pairwise comparison also has all 46 cells. No failure is excluded to create a favorable subset.

| Configuration | Raw task success | Input incl. cache | Cached input | Output | MCP calls | Raw elapsed, s | Adjusted elapsed, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kitsune default | 46/46 | 5,901,946 | 5,132,160 | 19,516 | 514 | 1,333.899 | 1,264.414 |
| Kitsune code-first | 46/46 | **5,730,439** | 5,072,896 | 20,758 | 333 | 1,396.084 | 1,324.975 |
| Aside | 46/46 | 5,923,875 | 5,267,840 | 22,983 | 261 | 1,444.198 | **1,242.744** |
| EgoLite | 46/46 | 7,775,055 | 6,708,096 | 26,925 | 261 | 1,627.307 | 1,478.044 |

Input includes cached input; it is **not a subscription charge or a quota-percentage estimate**.
Model request count, first-request input, monetary cost and remaining subscription allowance are
unavailable, not zero. Total reported input across the experiment is 25,331,315; output is 90,182.

The predeclared adjustment is **raw per-agent elapsed minus relay setup minus post-call inventory**:

| Configuration | Relay setup, s | Post-call inventory, s |
| --- | ---: | ---: |
| Kitsune default | 66.845 | 2.640 |
| Kitsune code-first | 69.410 | 1.699 |
| Aside | 197.636 | 3.818 |
| EgoLite | 108.891 | 40.373 |

Both timing columns sum individual agent runs. Neither is whole-experiment wall time or pure browser
latency. Browser provisioning, catalog checks and audit pauses are outside raw agent elapsed. Hidden
fixture setup costs differ substantially: **Aside is 8.3% slower than default on raw time but 1.7%
faster after the predeclared adjustment**. This small adjusted difference is not a robust global speed
victory. Keeping both columns prevents benchmark setup from being silently attributed to the agent.

### Pairwise ratios, numerator / denominator

| Comparison | Input | MCP calls | Raw time | Adjusted time |
| --- | ---: | ---: | ---: | ---: |
| Code-first / default | **0.971** | 0.648 | 1.047 | **1.048** |
| Aside / default | **1.004** | 0.508 | 1.083 | **0.983** |
| EgoLite / default | **1.317** | 0.508 | 1.220 | **1.169** |
| Aside / code-first | 1.034 | 0.784 | 1.034 | 0.938 |
| EgoLite / code-first | 1.357 | 0.784 | 1.166 | 1.116 |
| EgoLite / Aside | 1.313 | 1.000 | 1.127 | 1.189 |

Few MCP calls do not mean few browser actions or model requests. A script can contain many actions,
observations and loops. Baseline uses **63 Python calls in nine attempts**, candidate **232**; this is
not Python versus no Python. Candidate reduces MCP calls **35.2%**, but only **16/46** cells use fewer input tokens and
**14/46** have lower adjusted time; median paired ratios are **1.091 / 1.080**, respectively.

Aside uses fewer input tokens than default in **37/46** cells (median paired ratio **0.870**) and is
faster after adjustment in **27/46** (median **0.959**). Its expensive recovery cases erase that typical
input advantage in the pooled total. Against candidate, Aside wins input in **36/46**, adjusted time in
**35/46**. These are descriptive counts, not statistical significance from two repeats.

## 3. Task strata

Each cell below is **input tokens / adjusted seconds**, summed over identical cells in every arm.

| Stratum | Cells per arm | Kitsune default | Code-first | Aside | EgoLite |
| --- | ---: | ---: | ---: | ---: | ---: |
| Personal | 14 | 1,377,266 / 330.860 | 1,555,253 / 412.460 | 1,301,545 / 345.165 | 1,412,919 / 327.536 |
| Isolated UI | 20 | 2,233,388 / 531.667 | 1,985,848 / 507.481 | **1,705,507 / 447.635** | 2,485,581 / 562.751 |
| Crowded UI | 12 | 2,291,292 / **401.887** | **2,189,338** / 405.034 | 2,916,823 / 449.943 | 3,876,555 / 587.756 |

- **Personal:** candidate/default input **+12.9%**, adjusted time **+24.7%**. Aside input **−5.5%**,
  adjusted time **+4.3%**; Ego input **+2.6%**, adjusted time **−1.0%**. Permission differences make
  this a workflow comparison, not equivalent protected-user-tab performance.
- **Isolated:** Aside/default input **−23.6%**, adjusted time **−15.8%** (raw time **−3.2%**).
  Aside/candidate input **−14.1%**, adjusted time **−11.8%** (raw time **+1.0%**). Candidate improves
  over default here: input **−11.1%**, adjusted time **−4.5%**, but not on the whole workload.
- **Crowded:** Aside/default input **+27.3%**, adjusted time **+12.0%**; Ego/default **+69.2% / +46.3%**.
  Candidate/default input **−4.5%**, adjusted time **+0.8%**. Scope/observation and recovery costs matter
  more than advertised tool count alone.

### Repeats and influence, not a replacement result

Input in repeats 0 / 1:

| Arm | Repeat 0 | Repeat 1 |
| --- | ---: | ---: |
| Default | 2,777,728 | 3,124,218 |
| Code-first | 2,733,842 | 2,996,597 |
| Aside | 3,350,075 | 2,573,800 |
| EgoLite | 3,810,526 | 3,964,529 |

Aside's first crowded editor attempt uses **713,828** input versus **236,296** on its second. As an
explicit post-hoc influence check, dropping each entire condition in turn yields Aside/default input
ratios **0.896–1.042** across the 23 leave-one-condition-out selections. The minimum drops crowded
editor; the maximum drops product comparison. **Do not substitute the favorable 0.896 for 1.004.**
Code-first/default spans **0.940–1.003**, so even these selections do not establish a 10% overall saving.

## 4. What the call audit explains

MCP-reported tool errors: **16 default / 15 candidate / 18 Aside / 3 EgoLite**. All recover within their
original attempt. These are MCP error flags, not a count of every failed inner operation: for example,
Aside 121 catches a failed locator read inside JavaScript, so that call is not an MCP error.

- **Long-page lookup:** default uses `browser_find`, totaling **186,881 input / 42.649 adjusted s**.
  Candidate uses large text/snapshot reads and CSS queries: **356,227 / 95.349**, including three
  16-KB script output-limit errors across the two attempts and an invalid `:has-text` query.
  Aside totals **454,056 / 86.483** after unavailable `allTextContents`, unsupported scoped selectors,
  and locator-based search; one call loops over 180 headings. Ego totals **349,602 / 61.867**, reading
  and filtering full-page snapshots. Small advertised catalogs do not remove these exploration costs.
- **Editor:** candidate's targeted Python `type`/keyboard batching is effective, e.g. isolated input
  **148,085** versus default **335,772**. Default initially replaces rather than appends, then uses
  undo, same-URL reloads and `slowly`/`insert` recovery. Aside also struggles with caret/end-of-document
  behavior, uses repeated undo/ArrowRight and screenshot-coordinate recovery. In the crowded first
  repeat it additionally encounters stale refs and an unsupported snapshot selector. Ego is efficient
  on the isolated editor but needs caret recovery on crowded layouts.
- **Sorting:** all arms use keyboard sorting, **not dragging**. Candidate sometimes sends untargeted
  ArrowUp after a targeted Space and only completes after targeting the ref on subsequent keypresses.
  Candidate isolated input is **180,337**, default **105,248**, Aside **92,597**, Ego **133,820**.
- **Infinite scroll:** all four repeatedly observe newly loaded documents. Candidate still mixes
  selector dialects: selectors accepted by snapshot/action resolution can fail in CSS-only query or
  wait paths. Aside uses scroll-into-view plus repeated snapshots; Ego uses hover/mouse wheel. Default
  spends calls discovering Python scroll helpers; nonexistent `browser.documentation`, `browser.page`,
  `browser.scroll`, `get_element` and `scroll_into_view` generate errors. No authored page JS was used
  to get around these problems in this cohort.
- **State survives a script error:** Ego 162 checks the last-page item, then fails because subtree
  snapshot `root` must be a ref. It next verifies with screenshots instead of toggling the completed
  checkbox again. Aside's crowded sort completes key actions before the snapshot selector fails,
  then observes instead of replaying the sort. MCP error does not mean the earlier actions rolled back.
- **Extra verification is real work:** candidate frequently reloads owned copies to check persistence;
  default's second product-comparison attempt takes four screenshots and uses 245,871 input. Ego takes
  screenshots to verify table checkboxes and shadow preferences. These observations are retained,
  not normalized away after seeing the totals.
- **Native input behavior differs:** Ego reports cookie-overlay pointer interception in two crowded
  attempts and dismisses the overlay before recovering. Success through a high-level browser method
  does not establish OS-native input or identical actionability/occlusion behavior across products.

## 5. Compliance, permissions, images and viewport limits

### Emitted strategy, not a security certificate

Manual review found **no emitted page evaluate/DOM mutation, raw CDP, alternative filesystem/network
access, hidden grading reads, reward writes or delegation**. The eight datepicker attempts use the
calendar UI; no read-only/disabled input bypass was observed. Native screenshot capture into the
per-attempt Ego directory is the documented exception, not arbitrary filesystem access.

Ordinary in-attempt reloads remain in the evidence: default restores unsaved editor text via same-URL
navigation in attempts **59, 150 and 176**; other reloads verify saved notes. No new trial/episode,
replacement model attempt, grader reset or MiniWoB START/restart was performed. The gallery task
allows its page UI and preserves the same starting URL; it is not an immutable-document test.

Every task has a passing recorded safety grade, but the telemetry sees inventories **after MCP calls**,
not every inner-script write/navigation. Python and Node remain trusted host code. These observations
are not proof of confinement, adversarial resistance or equivalent browser/user-account protection.

### No model approval/refusal coverage in this cohort

There were **zero** `browser_tabs action=request`, `browser_ask_user`, `browser_resume` or recovery
`browser_tools_call` calls, and **zero delayed agent declines**. Kitsune writes in owned copies rather
than obtaining control of the user-seeded tabs. Aside/Ego write in their harness-created accessible
starting tabs. Thus 46/46 vendor scores do **not** show that they enforce Kitsune's user-tab permissions.

The new two-second scripted decline was separately tested successfully against both pinned Kitsune
sources before inference. It was **not exercised by the 184 model attempts**, and cannot be credited
as the measured cause of the difference from the older Opus handoff timeout. Nor did this study test
real-human approval/refusal, simultaneous real-user typing, hostile UI or general dragging support.

### Actual image transport and unequal effective geometry

The audit decodes/verifies **54 delivered MCP images**, not just printed file paths:

| Arm | Delivered images | Observed encoded image dimensions |
| --- | ---: | --- |
| Default | 8 PNG | six 1280x720; two chart crops 560x320 |
| Code-first | 4 PNG | two 1280x720; two chart crops 560x320 |
| Aside | 9 JPEG, 2 PNG, 4 WebP | full-page/viewport images mostly 2000x1125; two editor crops 1920x242; two chart crops 1152x672; one 2000x1375 |
| EgoLite | 27 PNG | **all 960x965** |

**1280x720 CSS pixels was a setup request, not an achieved all-product invariant.** Kitsune personal
page reports and available screenshots support its configured content size. Aside's ordinary images
are scaled from a DPR-2 browser. Its initial personal page-load reports occur before setup's viewport
setter and can differ from later reports. Ego's initial personal reports are 960x965/DPR 2; all delivered
Ego screenshots are 960x965 despite setup's CDP metrics request. A successful setup command does not
prove a persistent override across native script sessions. Gallery does not emit the personal track's
viewport reports. Do not infer every page's CSS dimensions solely from image dimensions.

Additionally, **Aside attempt 89** explicitly calls `setViewportSize({width:1600,height:1100})` while
recovering chart visibility. Its larger screenshot is retained and disclosed, not silently described
as matched geometry. Removing that **whole four-arm condition/repeat cell** leaves 45 cells: inputs
**5,820,942 / 5,636,378 / 5,801,222 / 7,553,337**, adjusted seconds
**1,243.214 / 1,304.415 / 1,213.646 / 1,439.305**, in default/candidate/Aside/Ego order.
This is a sensitivity check, **not** a remedy for all cross-browser viewport/profile differences.

Accordingly, this is a native-configuration functional comparison with disclosed environment
confounders, **not** an engine-, permission- or viewport-controlled isolation of tool-surface effects.
The two Kitsune arms are more directly comparable to each other than either is to a vendor product.

## 6. Per-condition complete results

Each entry is **two-repeat input sum / adjusted seconds**. All entries have 2/2 raw successes.

| Condition | Default | Code-first | Aside | EgoLite |
| --- | ---: | ---: | ---: | ---: |
| pb-current-01 | 148,574 / 39.240 | 179,288 / 51.121 | 103,726 / 35.136 | 149,409 / 39.985 |
| pb-tabs-01 | 330,991 / 60.331 | 183,160 / 47.505 | 119,659 / 41.792 | 153,183 / 37.624 |
| pb-research-01 | 166,925 / 41.406 | 177,883 / 42.337 | 168,181 / 47.889 | 202,973 / 47.011 |
| pb-account-01 | 197,039 / 51.023 | 240,407 / 59.780 | 166,926 / 46.453 | 185,255 / 47.612 |
| pb-handoff-01 | 181,251 / 46.289 | 224,875 / 63.921 | 143,354 / 46.669 | 186,425 / 45.411 |
| pb-safe-01 | 165,605 / 49.922 | 193,413 / 52.445 | 145,643 / 40.744 | 186,072 / 48.027 |
| pb-longpage-01 | 186,881 / 42.649 | 356,227 / 95.349 | 454,056 / 86.483 | 349,602 / 61.867 |
| ui-table isolated | 254,964 / 58.319 | 240,603 / 55.515 | 162,110 / 47.898 | 340,718 / 86.009 |
| ui-infinite isolated | 474,614 / 88.283 | 485,463 / 81.849 | 357,517 / 68.212 | 453,402 / 95.716 |
| ui-sortable isolated | 105,248 / 33.783 | 180,337 / 53.924 | 92,597 / 29.356 | 133,820 / 32.593 |
| ui-datepicker isolated | 186,484 / 38.604 | 183,929 / 50.822 | 147,551 / 34.880 | 245,183 / 48.655 |
| ui-autocomplete isolated | 160,523 / 38.941 | 147,498 / 39.080 | 139,715 / 34.676 | 215,415 / 55.584 |
| ui-shadow isolated | 160,756 / 39.964 | 121,715 / 41.594 | 115,665 / 32.684 | 311,091 / 58.998 |
| ui-iframe isolated | 104,278 / 31.917 | 121,518 / 33.741 | 91,429 / 31.312 | 148,596 / 32.284 |
| ui-editor isolated | 335,772 / 79.878 | 148,085 / 43.578 | 282,070 / 83.909 | 148,144 / 38.105 |
| ui-toast isolated | 313,537 / 87.786 | 203,502 / 70.487 | 189,526 / 48.670 | 265,834 / 59.876 |
| mm-chart isolated | 137,212 / 34.191 | 153,198 / 36.892 | 127,327 / 36.039 | 223,378 / 54.930 |
| ui-table crowded | 266,824 / 55.249 | 285,580 / 59.137 | 217,964 / 49.394 | 853,109 / 109.152 |
| ui-infinite crowded | 1,168,538 / 158.793 | 1,022,321 / 150.005 | 1,143,052 / 155.434 | 1,186,807 / 187.123 |
| ui-sortable crowded | 163,464 / 41.456 | 197,794 / 53.666 | 158,147 / 36.811 | 331,611 / 51.048 |
| ui-editor crowded | 353,527 / 69.721 | 222,203 / 51.745 | 950,124 / 113.529 | 588,658 / 87.099 |
| ui-autocomplete crowded | 176,792 / 36.111 | 259,637 / 46.972 | 183,695 / 37.719 | 497,233 / 80.373 |
| mm-chart crowded | 162,147 / 40.558 | 201,803 / 43.509 | 263,841 / 57.056 | 419,137 / 72.961 |

## 7. Decision, validation and reproduction

Keep the **14-tool default** and retain the candidate separately. Its 2.9% whole-cohort input saving
still does not meet the earlier requested 10% threshold. A favorable isolated-UI stratum is not a
replacement for that whole-workload requirement, and this independent comparison did not authorize
reversing the old merge hold. Neither product source was changed or merged.

The actionable evidence is workflow-specific: consistent selector syntax, bounded long-page
observations, discoverable scroll/find APIs, caret semantics and preserving completed writes after
an error deserve attention. This report does not implement those changes or claim they would improve
an unseen evaluation. No latest-main/CI merge review was advanced because no merge is proposed.

Validation:

- Before inference: **158 passed / six opt-in skipped** in 164 selected tests. Separate no-model live
  checks covered seven personal initial states for both vendors (14 setups), actual image delivery for
  both vendors, and settled scripted declines for both Kitsune revisions. An initial test incorrectly
  required Aside PNG; it was corrected to accept its valid JPEG and revalidated before freezing.
- Post-execution: **163 passed / six opt-in skipped** in 169 selected tests; five added audit tests cover
  known-zero vs missing usage, rejected fabricated metrics, safe review normalization and PNG/JPEG/WebP
  verification. All 54 actual image payloads were decoded and checked offline. No additional inference.
- Frozen source/protocol/catalog hashes still match. `git diff --check` passes. Product regression
  evidence remains the earlier targeted Python/Node/real-browser checks on unchanged product sources,
  not a new full-product-suite certification.

Private cohort: `artifacts/codex-expanded-four-way-v1/`; detailed pairs under
`artifacts/expanded-four-way/`, screenshots under `artifacts/expanded-four-images/`.
`runs.jsonl` SHA-256: **`5ec7b52f3455d02ec74c03ebb465edc23e98e2b9abfb4c8349c1f25a0dd7acc8`**.
The first-eight audit remains keyed to its original eight raw rows. Raw prompts, trial/session tokens,
image bytes and call transcripts are private artifacts, not committed.

Offline only, from the benchmark checkout:

```sh
uv run --locked python scripts/run-expanded-four-way.py analyze \
  --out artifacts/codex-expanded-four-way-v1
uv run --locked python scripts/audit-expanded-four-way.py artifacts/codex-expanded-four-way-v1
PYTHONPATH=tests uv run --locked python -m unittest \
  test_expanded_four_way_audit test_expanded_four_way test_expanded_session \
  test_adapter test_doctor test_cost_metrics test_codex_scripting_ab \
  test_codex_scripting_caps_ab test_full_native test_personal test_gallery \
  test_ego_mcp test_mcp_tool_filter -q
```

The audit intentionally expects this completed cohort. It never executes the model/browser, and its
`manual_review_required` flag remains true: rerunning a pattern scan cannot reproduce human/contextual
judgment or certify a safe runtime. Two repeats of variant 0 support descriptive findings only.
