# Code-first Python: current Kitsune, Playwright, EgoLite and Aside

**V2 completed 70/70 planned attempts, all scorable; 68 raw task successes.** Both Kitsune arms,
Playwright and Aside scored **14/14**; EgoLite **12/14**. This is the operator-selected seven-task
MiniWoB exhibition, not a full standard-lite suite. **No merge or discard decision has been made.**

## Findings for the decision

- **Code-first vs current Kitsune:** input **−18.5%**, output **−8.8%**, model requests **−6.9%**,
  MCP calls **−36.4%**, CLI list-price estimate **−8.4%**. Both have 14/14 raw successes. Input is lower
  in all 14 matched cells. The code-first agent actually used Python: **42 calls, zero reported errors**.
- **No elapsed-time improvement:** summed agent runtime **210.536 → 212.818 seconds (+1.1%)**.
  Code-first is faster in only 6/14 cells. Fewer MCP calls do not imply proportionally fewer model
  round trips or faster execution. This supports token efficiency on these tasks, not a speed claim.
- **Not an overall win over Aside:** full-cohort input is nearly tied (code-first −0.6%), and code-first
  elapsed is −11.2%. But Aside's difficult first `book-flight` run dominates this difference. On the
  **12 cells successful for every arm**, Aside uses **12.5% less input** and **5.0% less time** than
  code-first. This does not establish Python-versus-JS superiority in either direction.
- **Raw grade is not UI-only compliance:** vendor page-JS code appears in 9 ego and 1 Aside attempts.
  Separately, code-first fills a **read-only date field** in one `book-flight` run through Kitsune's
  existing native-value setter; baseline also invokes the fill path on that field in one run.
  See the manual audit. These observations are not hidden by a zero page-JS regex count.
- **Recommendation:** retain the branch as a promising token-efficiency candidate. These data alone
  do not establish that replacing the default surface is worthwhile for broader workloads, approval
  recovery or all-input coverage. The operator decides whether to merge, extend the evaluation or discard.

## Frozen implementation and execution

[Protocol](../experiments/2026-11-12-code-first-five-way.md).
Execution runner: `scripts/run-code-first-five-way.py`.
Benchmark execution commit: **`3c3ef92b5e8a24e84620365a429571aad24f2f0a`**.
The audit/report are post-execution, offline additions; no product or guide tuning occurred mid-cohort.

| Arm | Frozen source/configuration | Initial tools |
|---|---|---:|
| Current Kitsune | `47dafa20a3fddc697a7d991e15d39e4b0232c10d`, scripting unset, no allowlist | 14 |
| Code-first Kitsune | `f5c7a0f85aefd89e621e73665e33d33d79d50676`, scripting unset, no allowlist | 6 |
| Playwright | `@playwright/mcp@0.0.83`, standard UI allowlist | 23 |
| EgoLite | CLI/app `0.6.2.9`, Chromium `156.0.8078.74`, Node `v24.22.1`; vendor-guide `run_script` | 1 |
| Aside | CLI/native MCP `1.26.1107.24`, app `1.0.1022.1`; `repl` only, no agent `exec` | 1 |

Implementation branch: **`experiment/code-first-tools`** in `kitsune`.
Benchmark/report branch: **`experiment/code-first-efficiency`** in `kitsune-benchmark`.
The product treatment changes tool exposure, guidance and recovery hints, **not the browser engine**.
The six tools are `browser_run_python`, `browser_tabs`, `browser_take_screenshot`, `browser_ask_user`,
`browser_resume`, and `browser_tools_call`. Ordinary reads/input/waits move to Python. The last tool
can describe a named recovery tool without executing it, or execute explicit arguments through existing
validation and approvals. Unadvertised old direct names remain callable for compatibility.

Approval stops name the direct recovery operation; previously completed work is never automatically
replayed. This is **not** a persistent REPL, sandbox, new JS runtime or automatic script continuation.
Python still has trusted local host access. Catalog visibility is not a security boundary.

- Claude Code **2.1.303**, **`claude-opus-5-5`**, medium effort, claude.ai subscription only. No paid API
  fallback. All observed init/result models match; `apiKeySource=none`, no spawned subagents or observed
  overage use. Estimates below are not subscription charges.
- MiniWoB revision **`33c3b4ddef8c6eb67c57a29663d844b1eda7e614`**, seed **42**, seven tasks × two repeats.
  Arm order rotates sequentially and reverses within each task on repeat 1. First five audited before
  continuing. No replacements, episode retries, unstarted attempts or telemetry errors in V2.
- Episode/harness limits **120/180 seconds**. MCP envelope **45 seconds** for Kitsune/Playwright,
  **130 seconds** for vendor scripts. Each attempt has a fresh named context instruction.
- Kitsune/Playwright use fresh private headless Firefox. Aside/ego use installed warm browsers, **not
  isolated profiles**. Engines, effective viewport, locale, cache, API and guides are not matched across
  products. The same-environment Kitsune A/B is the primary comparison.
- V1 stopped on the first baseline request around 21:20 KST with a subscription-limit 429: **zero tokens,
  zero MCP calls, zero episode starts**. The operator explicitly authorized a new cohort after the
  21:30 reset. V1 is preserved separately and is not included in these efficiency/success totals.

## All-attempt totals

Input includes cache-read and cache-creation input, not just newly processed input. Cached input below
is cache-read input. MCP calls are not browser-action counts. Elapsed is summed per-agent harness
runtime, not isolated input latency or total experiment wall time; provisioning, catalog probes and the
first-five audit pause are outside it. Failed work is included, including both ego flight failures.

| Metric | Current Kitsune | Code-first | Playwright | EgoLite | Aside |
|---|---:|---:|---:|---:|---:|
| Raw success / attempts | 14/14 | 14/14 | 14/14 | **12/14** | 14/14 |
| Scorable | 14 | 14 | 14 | 14 | 14 |
| Input tokens | 573,692 | **467,684** | 952,933 | 525,936 | 470,580 |
| Cached input | 502,358 | 400,818 | 864,468 | 455,319 | 408,303 |
| Output tokens | 7,820 | 7,133 | 8,568 | 15,148 | 10,210 |
| Model requests | 72 | **67** | 87 | 84 | 74 |
| MCP calls | 88 | **56** | 110 | 70 | 61 |
| Elapsed seconds | **210.536** | 212.818 | 270.570 | 285.438 | 239.595 |
| CLI list-price estimate | $0.826968 | $0.757216 | $1.051278 | $0.958288 | $0.783485 |
| First-request input median | 6,766.5 | **5,882** | 9,294 | 4,894.5 | 5,129 |
| Python/vendor script calls | 0 | **42** | 0 | 70 | 61 |
| Scripts reporting errors | 0 | **0** | 0 | 9 | 4 |

Code-first vs Playwright on the same 14 raw-success cells: input **−50.9%**, elapsed **−21.3%**.
This is an observed configured-product comparison, not an isolated tool-count experiment.

### Kitsune A/B: consistency and task variation

Ratios are **code-first / current**; less than 1 means less input/time. Each row sums two repeats.

| Task | Input ratio | Elapsed ratio | Current seconds | Code-first seconds |
|---|---:|---:|---:|---:|
| click-test-2 | 0.694 | 0.923 | 26.692 | 24.640 |
| click-checkboxes | 0.755 | 1.081 | 25.725 | 27.799 |
| enter-text | 0.903 | 1.107 | 23.981 | 26.548 |
| choose-list | 0.670 | 0.869 | 28.406 | 24.698 |
| login-user | 0.854 | 1.075 | 27.476 | 29.545 |
| use-autocomplete | 0.790 | 0.892 | 32.860 | 29.315 |
| book-flight | 0.947 | 1.107 | 45.396 | 50.273 |

- All 14 cells use fewer input tokens: median ratio **0.847**, range **0.669–0.986**.
- MCP calls decrease in 13/14 cells and tie in one. Model requests decrease in only 6/14.
- Time decreases in 6/14; median cell ratio **1.023**, range **0.733–1.236**. Per-attempt elapsed medians
  are 14.467 seconds current and 13.899 code-first, but the summed/mean time is slightly higher.
- Repeat 0 input: **292,904 → 228,117**; time **106.957 → 107.053** seconds.
  Repeat 1 input: **280,788 → 239,567**; time **103.579 → 105.765** seconds.
  This is descriptive variation, not statistical confidence from two repeats of the same seed.

The smaller first-request input (−13.1%) and observed batching are both plausible contributors. For
example, the code-first login script groups two fills, a click and a snapshot. But exposure, guidance,
observation choices and batching changed together; this cohort cannot assign a causal share to each.
Neither call reduction nor Python worker overhead alone explains the measured time without finer timing.

## One identical jointly successful set

**12 task/repeat cells are successful for all five arms:** both repeats of the six tasks other than
`book-flight`. This is a task-selected comparison, not a replacement for the failed-effort-inclusive table.

| Arm | Input tokens | Output | Requests | MCP calls | Elapsed seconds |
|---|---:|---:|---:|---:|---:|
| Current Kitsune | 429,435 | 5,792 | 56 | 65 | 165.140 |
| Code-first | 331,141 | 5,198 | 50 | 40 | 162.545 |
| Playwright | 713,172 | 6,206 | 69 | 77 | 212.134 |
| EgoLite | 380,074 | 10,729 | 65 | 53 | 203.281 |
| Aside | **289,769** | 5,975 | 50 | **38** | **154.373** |

On these cells, code-first/current input **−22.9%**, time **−1.6%**; code-first/Aside input **+14.3%**,
time **+5.3%**. Excluding both flight cells also removes the observed read-only-date shortcut from the
Kitsune A/B. The input-saving direction remains; this still does not certify UI-only compliance.

For a separate sensitivity, remove vendor page-JS-emitting cells and require both compared grades to
succeed. Code-first/ego has **5 cells**: input **132,293 / 165,052**, time **66.554 / 83.714** seconds.
Code-first/Aside has **13 cells**: input **405,072 / 354,500**, time **186.735 / 189.466** seconds.
These small selected subsets are not a causal measure of page-JS cost or a security guarantee.

## Audit and failure mechanisms

Offline audit checked **70 evaluations**, **84 model-facing tools/list replies**, and **385 calls**.
Every evaluation has one page load, one episode start, zero telemetry errors and an official terminal
reward. Per-attempt before/actual/after catalogs and global pre/post catalogs match; no tool publication
or guide expansion was observed. Ego used **14 distinct TaskSpaces** (24–37); Aside opened a new tab
in each first call. This does not establish private-profile isolation.

All **173 Python/vendor script calls** were manually inspected, including flight results and errors.
Code-first used exactly **14 `browser_tabs` + 42 `browser_run_python`**, with **zero dispatcher,
compatibility-direct or recovery calls**. Current Kitsune used no Python. Thus this experiment observes
ordinary code-first use, not benchmark-model discovery or successful handling of an approval stop.

### EgoLite: both flight failures are wrong-target selection

- **Seq 33, r0:** after recovering a nonexistent page-label error, the agent correctly identified the
  shortest flight, **3h 45m / $812**. It clicked
  `xpath=(//div[contains(@class,"flight")]//button)[2]`. The broad match also includes the header's
  Back button, so the second matched button is the **first flight, 4h 58m / $444**.
- **Seq 68, r1:** likewise identified the right flight, then clicked `.flight:nth-of-type(2) button`.
  A preceding `div.flight-header` makes this the **first flight**, not the second.

Both ended with reward/raw reward **−1/−1**, not timeouts or infrastructure failures, and acknowledged
failure without restarting. Selector behavior was checked offline against the pinned upstream markup;
this explanation was not supplied to the agent. A command succeeding is not proof of correct intent.

Ego's **nine reported script errors** comprise five invalid `[ref=N]` CSS selectors, three nonexistent
page labels and one ambiguous `text=Submit` locator. Aside's **four** comprise two non-Element locator
errors and an unsupported `getByPlaceholder` method in flight r0, plus a read-only date-fill error in r1.
Aside recovered both episodes and scored 2/2, but used **50.129 and 35.093 seconds**, versus code-first's
**26.083 and 24.190**. Caught errors/ineffective operations are not all reflected in MCP error flags.

### UI-only and read-only-field caveats

The page-JS scan finds **21 expressions in 9 ego attempts** and **14 in 1 Aside attempt**. These count
emitted expressions, including some not reached after an earlier failure. The inspected code reads DOM
instructions, options, values, date/flight text, START geometry and visible result feedback. No authored
page-JS DOM mutation, hidden reward-variable access, reward write, timer manipulation or fixture-source
read was observed. The narrow reward regex has zero hits, but ego explicitly reads `#reward-last` and
`#episode-id`; zero regex hits do not mean no reward-related reads. Visible feedback is different from
changing or consulting hidden grading state. Page JS violates the requested observation-tool-only strategy.

**Kitsune has a separate existing action-semantics issue:** `book-flight`'s date input is `readonly`.
In seq 31, code-first executes `tab.fill('e3', '12/23/2016')` successfully, then searches without the date
picker. `extension/content/content.js`'s `fillField` uses the native value setter without rejecting
`readOnly`. The baseline's seq 35 `browser_type` (without `slowly`) also takes this fill path, although
it subsequently clicks the date in the picker. The content implementation is identical in both pinned
Kitsune revisions; this is **not a newly introduced extension change**, but it prevents describing the
raw score as strictly human-equivalent UI success. Aside instead rejects read-only fill and recovers
with the picker. No post-outcome code fix, regrading or rerun was performed. The 12-cell table above
provides a matched comparison without either flight episode.

No alternate filesystem/network/CDP access or vendor-agent delegation was observed in the emitted
scripts. These are observational claims, **not confinement or comprehensive safety proofs**. Python
remains unrestricted host code, and the client-side MiniWoB reward instrumentation is not hardened
against arbitrary code. These scores are not a standard Gym leaderboard result.

## Validation and remaining scope

Before inference: **172 related Python/unit/in-memory MCP tests**, **3 real stdio MCP tests** with an
isolated headless Zen profile, and Node `tab_handoff.cjs`, `tab_handoff_races.cjs`, `popup.cjs` passed.
The stdio tests cover approval-stop draft preservation, direct recovery and foreign-tab write refusal.
An initial launch used a missing Firefox application path and failed before any test; the corrected
Zen launch passed. Post-analysis, **62 offline runner/harness tests** and the 70-row audit assertions
passed; negative-path unit tests intentionally print stop messages. These are targeted checks, not full
product-suite certification, and do not add model attempts to the cohort.

Seven short MiniWoB tasks do not cover scrolling/infinite lists, drag/canvas input, long repetitive forms,
real-site navigation, screenshots, login handoff or mid-script approval/refusal recovery. The direct
recovery dispatcher was not needed by the model here. Existing approval decisions still depend on the
MCP host correctly presenting the choice; schema validation alone cannot prove a human supplied a valid
approval. Test the broader task families and interrupted writes before treating this as a general default
replacement. That would require a separately authorized experiment, not silently extending this cohort.

## Reproduction and retained evidence

Primary local artifacts: `artifacts/claude-code-first-five-way-v2/`, including `manifest.json`, `runs.jsonl`,
`analysis.json`, `audit.json`, frozen catalogs, and a private `script-review.txt`. Run/pair directories are
referenced from each row. V1 remains at `artifacts/claude-code-first-five-way/`.

`runs.jsonl` SHA-256: **`d198e8f20816744fa051a5fd8f8933071b92e5374767a0c7a7bf6a0e0b4dc3ca`**.
Raw browser/model logs and local trial identifiers remain private artifacts, not committed public logs.

Recompute metrics and audit **without model calls or browser actions**:

```sh
uv run --locked python scripts/run-code-first-five-way.py analyze \
  --out artifacts/claude-code-first-five-way-v2
uv run --locked python scripts/audit-code-first-five-way.py \
  artifacts/claude-code-first-five-way-v2
```

Use the frozen protocol for a separately authorized reproduction; do not pool V1, this V2 cohort or older
five-way reports. Both implementation and benchmark branches are retained for the operator's decision.
