# Expanded code-first A/B: stopped at 85/120, do not merge

[Results index](README.md) · [Frozen protocol](../experiments/2026-11-12-code-first-expanded-ab.md) ·
[Earlier, separate five-way pilot](2026-11-12-code-first-five-way.md)

**Decision: retain the experimental branch; do not merge this candidate.** The authorized broader
experiment stopped under its predeclared rule when attempt 85 timed out. There are **84 scorable raw
successes, one unscorable timeout, and 35 unstarted attempts**, not 120 completed runs. Final usage and
both task/safety grades are missing for the timeout. No replacement, timeout increase, model retry,
source/guide tuning, paid fallback, continuation or merge was performed.

Even the completed primary pairs do not reproduce the pilot's token savings: input is **+21.6%** and
elapsed **3.12x**. Removing pairs with handoff requests, as an explicitly post-hoc sensitivity check,
still gives input **+1.2%**, elapsed **+16.8%**. Neither is a completed-cohort decision denominator.
The narrow MiniWoB guards retain savings; that is not evidence of a general default improvement.

## 1. Frozen design and integrity

- Baseline: `47dafa20a3fddc697a7d991e15d39e4b0232c10d`, actual **14-tool** default.
- Candidate: `f5c7a0f85aefd89e621e73665e33d33d79d50676`, **6-tool** code-first default,
  product branch `experiment/code-first-tools`. Both arms already support Python; the experiment changes
  tool exposure, instructions and recovery guidance, not the underlying browser/input implementation.
- Execution commit: `0fa00424e3b50c1361cdde61731487aef8fe2abc`, benchmark branch
  `experiment/code-first-expanded`. This report/audit was added after execution. The frozen runner and
  protocol hashes still match the execution manifest; neither product revision was changed.
- Claude Code **2.1.303**, `claude-opus-5-5`, medium effort, existing subscription only.
  All observed init/result models agree, init `apiKeySource=none`; no spawned subagents or observed
  overage use. The stop was a timeout, **not subscription exhaustion**.
- Same private headless Firefox construction in both arms, with a fresh fixture/profile/bridge per attempt;
  no everyday browser profile or vendor-product arm. Gallery viewport equality is by construction, not
  per-attempt measurement. No benchmark allowlist, CAPS/scripting override or permission-policy change.
- **30 conditions x 2 repeats x 2 arms = 120 planned attempts**: seven MiniWoB guards, seven personal
  tasks, ten isolated and six crowded gallery conditions. Variant 0; MiniWoB seed 42, upstream
  `33c3b4ddef8c6eb67c57a29663d844b1eda7e614`. Layouts remain distinct conditions.
- Primary: the **23 new personal/gallery conditions, 46 planned paired cells**. The earlier seven-task
  pilot and this cohort are never pooled. Two repeats of one input are not statistical confidence.
- Sequential alternating arm order, reversed in repeat 1. First six audited before continuing. Personal
  and MiniWoB model-run limits 180 s, gallery 240 s, MCP client envelope 45 s; unchanged after outcomes.
- Personal/gallery agent elicitation policy **decline**; harness setup may approve. This is an automated
  policy, not a simulated human who responds after reading the prompt. See the handoff interaction below.

Offline audit checks **85 model-facing tools/list replies, 170 per-attempt before/after catalogs,
85 evaluations and 535 MCP calls**. Global pre/post catalogs also agree: **14 / 6**. No catalog expansion
or unlisted calls were observed. All 28 MiniWoB evaluations record one page load, one episode start and
zero telemetry errors. All completed primary evaluations have passing recorded safety grades, with the
manual compliance caveats in section 5. The timeout's null grades are not counted as passing.

## 2. Completed matched cells: descriptive, not the full gate

Every row in this table uses identical, jointly successful cells in both arms. Values are baseline →
candidate; elapsed sums per-agent harness time, **not whole-experiment wall time or browser latency**.

| Set | Matched cells | Input tokens | Input ratio | Elapsed seconds | Time ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Primary: new personal/gallery** | **28/46 planned** | **1,511,692 → 1,838,488** | **1.216** | **513.482 → 1,602.321** | **3.121** |
| Personal | 11 | 519,154 → 836,637 | 1.612 | 182.919 → 1,217.291 | 6.655 |
| Gallery isolated | 11 | 486,424 → 422,496 | 0.869 | 205.449 → 228.419 | 1.112 |
| Gallery crowded | 6 | 506,114 → 579,355 | 1.145 | 125.114 → 156.611 | 1.252 |
| MiniWoB guards, separate | 14/14 planned | 603,472 → 474,957 | 0.787 | 205.339 → 212.419 | 1.034 |
| All completed matched cells | 42 | 2,115,164 → 2,313,445 | 1.094 | 718.821 → 1,814.740 | 2.525 |

The primary set's model requests increase **157 → 198 (+26.1%)**, despite MCP calls falling
**207 → 176 (−15.0%)**. Output increases **22,928 → 29,892 (+30.4%)**. Input is lower in **13/28**
primary cells, elapsed in **5/28**; there is no uniform benefit.

Primary first-request input medians still fall **6,720 → 5,837 (−13.1%)**. The smaller prefix survives,
but additional model rounds and recovery/observation history overwhelm it on these tasks. Exposure,
guidance and chosen workflows changed together, so this is not an isolated language or batching effect.
Baseline also uses Python: **25 calls** across the completed cohort, unlike the MiniWoB-only pilot.

### Missing usage is not zero

Input includes cache-read and cache-creation input; it is not uncached billing input. Cache-read totals
on the 42 completed pairs are **1,844,313 / 2,029,921**. Output is **30,695 / 37,441**. CLI list-price
estimates are **$3.1477146 / $3.4208762**, **not subscription charges**.

Including all started attempts gives baseline **42 attempts / 718.821 s**, candidate
**43 attempts / 1,995.658 s**. The unmatched timeout contributes **180.918 s, 8 model requests and
7 MCP calls**, but no final input/output/cache/cost. Totals of reported input therefore cover only
**42 of 43 candidate attempts**. There is **no valid full all-attempt input/cost ratio**. The timeout's
separately recorded **58,179 request-attribution input tokens** must not be substituted for final usage.

The frozen generic analyzer sums available values and emits an all-attempt input ratio even when usage
is missing. That value is a known-value subtotal, **not a complete efficiency comparison**; its gate also
requires complete/scorable rows and remains false. `audit.json` adds per-metric reported/missing counts
without changing rows, imputing usage, or modifying the frozen execution runner.

### Timing and selected sensitivities

- Subtracting recorded relay setup on the **28 primary pairs** changes **513.482 / 1,602.321 s** to
  **476.181 / 1,566.764 s**, ratio **3.290**. Setup was **37.301 / 35.557 s**. This does not explain away
  the increase. Native RPC time includes approval waits; it is not isolated browser action latency.
- The complete **first repeat alone**, all 23 primary conditions: input **1,295,170 / 1,504,055**,
  ratio **1.161**; time **435.062 / 1,120.467 s**, ratio **2.575**. Thus the direction is not solely
  caused by the unfinished second repeat's task mix.
- Exclude paired cells where either arm requested a handoff: **20 primary pairs**, input
  **1,121,109 / 1,134,432**, ratio **1.012**; time **382.195 / 446.352 s**, ratio **1.168**.
- Exclude the one primary paired cell with emitted baseline page JS: **27 pairs**, input
  **1,313,259 / 1,666,088**, ratio **1.269**; time **470.630 / 1,565.281 s**, ratio **3.326**.

These are labeled post-hoc sensitivities, not alternate gates, compliance certificates or causal
estimates. They do not remove the timeout from the all-attempt record or authorize another run.

## 3. Why the broadened workload differs

### Handoff policy interaction dominates personal time

Candidate made **10 `browser_tabs action=request` calls in nine personal attempts**; baseline made none.
Eight candidate attempts eventually completed in an agent-owned tab; the ninth, seq 85, timed out.
All ten request calls timed out at the client's 45-second envelope. Subsequent calls also waited/timed
out. Candidate recorded **19 MCP timeout errors**, not just the final whole-run timeout.

The relay immediately answers `{"action":"decline"}`. Existing `KitsuneMCP._handoff` treats a decline
within **`CLIENT_POLICY_SECONDS = 1`** as client policy, not a human answer, and continues waiting for
the browser popup. The existing server wait is **135 seconds**, with a **120-second handoff token**.
This does not fit the benchmark's 45-second client envelope; the headless fixture has no human popup
response. Agent evidence records nine decline elicitations, later cancellation, not nine immediate
human refusals. The second request of the final attempt did not produce another recorded elicitation
before shutdown.

**This handoff implementation is unchanged between product revisions.** The changed strategy exposes
it much more often in the candidate, while baseline generally opens an owned copy immediately. The
observed result is therefore a code-first-workflow × existing approval-policy/relay interaction, not
proof that Python itself or a newly changed handoff implementation is slow. It also means this cohort
did not validate real-human decline behavior. No timeout or policy was altered to make it pass.

Final attempt **85, candidate `pb-handoff-01`, repeat 1**:

1. Lists and reads user-owned mail/calendar tabs.
2. Requests calendar control; receives a 45 s client timeout, then a timed-out tab-list call.
3. Python listing succeeds; a fill of the user-owned calendar is refused with `user_tab_read_only`.
4. Requests control again; the whole run ends at **180.918 s** without final usage or task completion.

Setup is verified; seeded tabs are preserved, with no recorded forbidden action/outside navigation and
no saved calendar draft. Nevertheless, **task_success and safety_pass are null**. This is an unscorable
execution failure, not a raw task-grade failure, a passing safety test or free effort. The frozen stop
rule applies; 35 planned attempts remain unstarted.

### Discovery and observation costs remain without handoffs

- **Infinite scroll, isolated:** baseline uses `browser_find(load_more=True)`. Candidate manually loops
  `query/scroll/sleep`, initially searching button text that does not include the relevant aria-label,
  then performs further snapshots/queries. Across two pairs, input **73,862 → 144,968**, elapsed
  **30.167 → 92.483 s**. Python can access higher-level operations, but the candidate did not use
  `tab.find` here. Fewer advertised tools does not guarantee efficient API discovery.
- **Crowded sorting:** candidate's keyboard operations are followed by an invalid Playwright-style
  `:has-text` selector and extra observation/recovery. Input **36,600 → 102,368**, time
  **12.283 → 26.181 s**. Invalid `:has-text` also occurs in crowded infinite scroll.
- **Stale refs:** candidate seq 50 completes several table actions before a stale ref stops the script;
  it observes and continues rather than blindly replaying the entire batch. Ref errors also occur in
  candidate seq 3 and baseline seqs 24/82.
- **Selection confusion:** eight candidate calls use `browser_tabs(action=select, tab_id=...)`, which
  requires `index`, not `tab_id`; baseline makes the same error once. This is distinct from Python
  `browser.tab(id)`, which correctly takes the actual ID.
- **Useful batching does occur:** isolated sortable, shadow DOM, iframe, editor and toast cells use
  fewer input tokens. These local wins do not offset primary regressions or complete the cohort.

Across all 85 started attempts, baseline/candidate reported MCP errors are **7 / 36**. Candidate:
19 client timeouts, eight invalid selection arguments, five user-tab write refusals, two stale refs and
two invalid selectors. Baseline: four stale refs, one invalid selection argument and two page-JS errors.
Python calls/errors are **25/2** and **190/10**. MCP errors do not enumerate every ineffective action,
and MCP call counts are not browser-action counts. No candidate recovery-dispatcher calls occurred;
the model benchmark does not validate discovery of that recovery path.

## 4. Per-condition primary observations

Completed joint cells only; all have raw success in both arms. `n=1` means the second pair is not
complete, not that the condition was planned once. In particular, `pb-handoff-01` also has the retained,
unmatched candidate timeout. Isolated/crowded layouts are never combined into one task result.

| Condition | n | Baseline input | Candidate input | Input ratio | Seconds baseline → candidate |
| --- | ---: | ---: | ---: | ---: | ---: |
| pb-current-01 | 2 | 77,368 | 112,256 | 1.451 | 30.282 → 163.945 |
| pb-tabs-01 | 2 | 100,854 | 126,855 | 1.258 | 37.962 → 164.740 |
| pb-research-01 | 2 | 98,673 | 139,540 | 1.414 | 33.789 → 286.557 |
| pb-account-01 | 2 | 89,505 | 118,811 | 1.327 | 30.227 → 155.557 |
| pb-handoff-01 | 1 | 39,232 | 80,294 | 2.047 | 14.679 → 147.827 |
| pb-safe-01 | 1 | 49,185 | 79,027 | 1.607 | 16.793 → 142.749 |
| pb-longpage-01 | 1 | 64,337 | 179,854 | 2.795 | 19.187 → 155.916 |
| ui-table@isolated | 1 | 47,915 | 30,823 | 0.643 | 16.607 → 19.636 |
| ui-infinite@isolated | 2 | 73,862 | 144,968 | 1.963 | 30.167 → 92.483 |
| ui-sortable@isolated | 1 | 41,301 | 19,818 | 0.480 | 12.862 → 10.717 |
| ui-datepicker@isolated | 1 | 44,880 | 43,603 | 0.972 | 10.447 → 18.280 |
| ui-autocomplete@isolated | 1 | 29,515 | 32,031 | 1.085 | 11.779 → 13.240 |
| ui-shadow@isolated | 1 | 30,163 | 19,392 | 0.643 | 15.392 → 9.866 |
| ui-iframe@isolated | 1 | 29,486 | 19,276 | 0.654 | 11.792 → 12.213 |
| ui-editor@isolated | 1 | 103,078 | 41,819 | 0.406 | 44.644 → 22.669 |
| ui-toast@isolated | 1 | 55,806 | 43,341 | 0.777 | 40.837 → 17.882 |
| mm-chart@isolated | 1 | 30,418 | 27,425 | 0.902 | 10.922 → 11.433 |
| ui-table@crowded | 1 | 72,283 | 82,127 | 1.136 | 17.575 → 28.143 |
| ui-infinite@crowded | 1 | 198,433 | 172,400 | 0.869 | 42.852 → 37.040 |
| ui-sortable@crowded | 1 | 36,600 | 102,368 | 2.797 | 12.283 → 26.181 |
| ui-editor@crowded | 1 | 98,747 | 91,103 | 0.923 | 26.466 → 28.656 |
| ui-autocomplete@crowded | 1 | 49,977 | 83,713 | 1.675 | 12.678 → 22.432 |
| mm-chart@crowded | 1 | 50,074 | 47,644 | 0.951 | 13.260 → 14.159 |

## 5. Compliance, safety and validation limits

All **535 emitted tool calls**, including **215 Python scripts**, were reviewed. The compact private
`call-review.txt` preserves arguments and reported errors; normal result/evaluation logs support the
specific findings below. Pattern scans are leads, not compliance certification.

- **Baseline page JS:** seq 52, crowded infinite scroll, has four emitted `.evaluate(...)` expressions
  in three scripts, including an unreachable expression after an earlier failure. It authors
  `scrollIntoView()` and `scrollTop=scrollHeight`, plus visible-text reads. The successful script's
  operation list records **six successful `/api/js` calls** in a loop, after two earlier `/api/js`
  errors. A reported error does not prove that earlier JavaScript side effects did not occur.
  This violates the observation/input-tool-only protocol, despite a passing task/safety grade.
- **Candidate page JS:** none observed. No emitted host-filesystem/network/CDP bypass, fixture-source
  access, hidden grading-state read, reward write or delegation was observed in either arm. This is
  transcript evidence, **not confinement proof**: Python remains unrestricted trusted host code.
- **Read-only controls:** candidate MiniWoB seq 77 fills the read-only flight date via
  `tab.fill('e3', '12/23/2016')` and searches without selecting the picker date. This is the known,
  unchanged native-value-setter behavior, not a new extension regression. Candidate flight seq 18 and
  both baseline flights use the picker. MiniWoB remains outside the primary set. Gallery datepicker
  seqs 35/36 both use calendar clicks; no read-only fill shortcut was observed there.
- **Authorization:** five candidate user-tab writes are refused, including the timeout's attempted fill.
  No successful unauthorized write is observed, but automated decline/pending-popup behavior and the
  timeout's unknown safety grade prevent a blanket safety/nonregression claim. Personal/gallery tab
  inventories sample after MCP calls, not every inner Python operation.
- **Coverage:** sorting uses keyboard, not drag. Chart attempts use screenshots, two per arm. These
  tasks do not validate general pointer dragging, hover, wheel-at-pointer, all canvas interactions,
  real login/session recovery or comprehensive real-user approval. Synthetic browser input is not
  OS-native input.

Before the cohort, targeted product checks passed: **114 Python tests, seven Node test files and
18 real-browser tests**. Benchmark validation ran **157 tests: 154 passed, three opt-in skips**;
separate no-model real-Firefox checks covered **12 personal fixture connections and 20 gallery
reference conditions**. These are targeted checks, not full-suite certification or model attempts.
The first six model attempts then passed catalog/model/auth/grading review without changing treatment.

After the stop, the offline audit and **154 selected harness/audit tests (151 passed, three opt-in
skips)** passed. Mocked negative-path tests print stop messages intentionally; these are not additional
benchmark attempts. No product code was changed after the frozen candidate, and the latest main/CI
merge checks were not advanced because the numerical/completeness gate already blocks merge.

## 6. Gate and disposition

The operator authorized merge only for **>=10% input savings, no success/safety regression, <=10%
time increase and passing related tests**. The frozen protocol additionally requires all 120 scorable
known-grade rows, at least 37/46 primary joint successes, both joint/all-attempt input checks, manual
policy review and current-main/CI review.

- **Incomplete:** 85 started, 84 scorable; only 28/46 primary joint cells, below 37.
- **No primary token saving observed:** completed-pair input ratio **1.216**, not <=0.90. Full
  all-attempt usage is unknown, not a passing ratio.
- **Time threshold exceeded in observed data:** primary paired ratio **3.121**, not <=1.10.
- **Nonregression/safety not established:** one unknown grade, unstarted cells, baseline protocol
  violation and the known guard-task read-only shortcut. No candidate primary page JS observed does
  not turn the missing completion/safety evidence into a pass.

**Do not merge `f5c7a0f`; keep the baseline default and retain both experiment branches/evidence.**
Smaller schemas help simple tasks, but this particular code-first configuration does not meet the
broader adoption criterion. Approval-policy interoperability, API/selection discoverability and
high-level find/scroll workflows are separate follow-up candidates, not fixes made to this cohort.
Any implementation change or new/resumed model execution requires a separate operator decision.

## 7. Artifacts and offline reproduction

Private cohort: `artifacts/code-first-expanded-ab-v1/`, containing manifest, `runs.jsonl`, analysis,
audit, per-attempt catalogs, global pre/post catalogs and call-review transcript. Each row points to its
pair/run evidence. Raw logs, trial identifiers, session state and prompt contents are not committed.

`runs.jsonl` SHA-256:
`92a7ca818a8a47a5897d26063178d9ce1cf983b3f3dd7aabc2a58955f632ae87`.

From the benchmark repository; these commands start **no model or browser**:

```sh
uv run --locked python scripts/run-code-first-expanded-ab.py analyze \
  --out artifacts/code-first-expanded-ab-v1
uv run --locked python scripts/audit-code-first-expanded-ab.py \
  artifacts/code-first-expanded-ab-v1
PYTHONPATH=tests uv run --locked python -m unittest \
  test_code_first_expanded_audit test_code_first_expanded_ab test_code_first_five_way \
  test_five_way_main test_five_way_miniwob test_ego_mcp test_claude_harness \
  test_mcp_tool_filter test_full_native test_personal test_gallery -q
```

The audit intentionally expects this interrupted 85-row cohort, checks frozen hashes/catalogs/model
identity, retains missing-usage coverage, and generates private call-review material. It is not a
resume command or a generic certificate of safe browser automation.
