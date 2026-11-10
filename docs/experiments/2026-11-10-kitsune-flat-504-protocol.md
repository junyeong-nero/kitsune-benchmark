# Kitsune #504: flat direct tools and bounded Python — preregistration v1

**Methods registered before product implementation and model execution. No execution
is authorized by this document.** Parent [Kitsune #498](https://github.com/junyeong-nero/kitsune/issues/498),
contract [#499 / PR #506](https://github.com/junyeong-nero/kitsune/pull/506), gate
[#504](https://github.com/junyeong-nero/kitsune/issues/504). Benchmark prerequisite
[PR #144](https://github.com/junyeong-nero/kitsune-benchmark/pull/144) repairs #136/#137;
this branch is stacked on it, not on an assumed merged main.

Machine-readable choices: `configs/experiments/kitsune-flat-504-v1.json`.
`python -m kitsune_benchmark.flat_protocol` checks frozen inputs and prints a plan;
it has **no execution path**. Neither the existing `full-native --execute` nor the
release-suite driver implements this four-arm protocol. [Validation and acceptance
scope](2026-11-10-kitsune-flat-504-validation.md) distinguishes this methods milestone
from the still-pending implementation and execution acceptance.

## 1. Questions, estimands and scope

1. C versus A describes the new direct **product configuration**, not scripting.
2. D versus C tests offering bounded Python composition alongside the **same** direct
   operations, policy, observations and fixture access. D may choose direct tools;
   intention-to-treat includes runs that never use Python. Do not restrict analysis
   to runs where the model chose scripts.
3. D versus A/B asks whether the proposed default is worth considering against
   today's core and authorized gateway/automation configurations. A/B are references,
   not capability-matched controls. No Playwright arm or pooled earlier cohort.

The Aside/ego exhibition was not a controlled scripting experiment. Smaller tool
counts, characters or outer MCP-call counts are not a verdict. The candidate's
73 operator-only dispositions among 109 legacy registrations are a material
coverage limitation, not equivalent agent usability. The full #499 map must be
reviewed alongside results before any default decision; this workload does not
exercise every privileged feature.

## 2. Arms and delivered context

| Arm | Product revision | Startup settings | Context |
| --- | --- | --- | --- |
| A | `fd9b90e1cfae702b8470fcfca5d1bd178dba2c94` | `CAPS=core`; PUBLISH unset | Actual core definitions and initialization instructions |
| B | same A | `CAPS=all`, `PUBLISH=core` | Core + gateway, later discovery/publication charged |
| C | one clean future candidate commit | `INTERFACE=flat`, `SCRIPTING=off`; CAPS/PUBLISH unset | Actual flat definitions + common guide |
| D | exactly C | `INTERFACE=flat`, `SCRIPTING=python`; CAPS/PUBLISH unset | Exactly C + runner definition + complete SDK guide |

Settings above abbreviate `KITSUNE_*`. JSON null means **unset**, not an empty
string. A/B also unset proposed INTERFACE/SCRIPTING flags: the old revision does
not implement them. Every arm sets MODE=act and USER_TABS=read-only; old writable
aliases are cleared. No storage/history grant, user-tab opt-out, page-evaluation
permission for C/D, or agent-accessible approval credential is introduced.

No additional benchmark tool-name allowlist; expose exactly the arm's tools. B
includes capabilities outside C/D, notably evaluation and older containers; some
are intentionally excluded from the pilot. A/B receive no new SDK guide. All arms
receive the unchanged task prompt/suffix. No benchmark-specific strategy hints or
solutions beyond the frozen operation/SDK guides; their generic API examples are
part of the measured context. C/D get the common guide once through initialization and D the complete
SDK guide once; capture what the client really supplies, not just server source.
No second hidden onboarding message. Optional reference lookup is charged if used.

The design reference is Kitsune `9ae8549`, `docs/design/499-*`; actual served
metadata/guide bytes must be frozen in the execution lock. At design review, act
initial component characters were A 22,284, B 24,637, C 20,091, D 24,143. These are
not tokenizer counts and actual binding metadata may differ. Record full versus
first-paragraph rendering and client list-refresh behavior. D must retain all C
operation definitions unchanged; only its outer runner and SDK guide may differ.
Different underlying capabilities or observation/redaction semantics invalidate a
causal scripting interpretation; do not silently relabel a failed parity preflight.

## 3. Workloads, repetitions and order

Use **all 28** runnable personal tasks, not a favorable subset. Include
`co-typing-01` and the existing `ui-table/crowded` and `ui-table/isolated` units.
This reuses all 14 full-native units and adds easy/account/safety/typing work.
Do not add specification-only coexistence tasks as if they already worked.

- Canonical data **variant 0**, four fresh attempts per unit per arm: **31 × 4 × 4
  = 496 runs** (124/arm). This controls model variation on one fixed data variant,
  not robustness across variants; no claim about variants 1/2 or live websites.
- Primary outcomes: 28 personal tasks plus typing (116 runs/arm). The two gallery
  layouts (8 runs/arm) are separately reported diagnostics: page-JS-reported state
  is weaker evidence than application-server state and cannot supply a positive
  efficiency verdict by itself. A confirmed safety/integrity violation still matters.
- Preserve catalogs, fixtures, prompts and graders byte-for-byte under recorded
  SHA-256 values. Personal primary remains v2_agent_tab_cleanup, strict v1 beside
  it; typing additionally requires v3_user_input and v3_user_view. Never re-grade
  old results under a new contract. #94's viewed-tab correction is already in this
  freeze; the older v0.7.2 report remains unchanged.
- Four Williams orders: `ABDC`, `BCAD`, `CDBA`, `DACB`. For zero-based repetition r
  and canonical unit index i use row `(r+i) mod 4`. Each unit has every arm in every
  position once, and each ordered adjacent arm pair once across its four repeats.
- Within repetition r, sort units by SHA-256 of
  `kitsune-flat-504-v1-order:r:unit-id` (UTF-8), tie-break by unit id. Keep all four
  arms of a unit adjacent. Repetitions run 0..3. Save the complete schedule before
  execution. No reshuffling, per-task retries or choosing the better attempt.
- One agent run at a time, fresh client conversation/fixture/browser/profile/bridge.
  No shared-load arm execution. B's own authorized containers may parallelize;
  initial D scripts remain sequential. Ordinary multi-tool model messages are not
  counted as several model requests.

Simple stratum: all four `pb-current-*` units. Composition stratum: all four
`pb-handoff-*` and four `pb-longpage-*` units. Research and existing-tabs are also
reported separately; do not move tasks between strata after seeing results.

## 4. Model, environment, permission and timing pins

- **Claude Code 2.1.303**, subscription harness `claude`, nominal model
  **claude-opus-5-5**, effort **medium**, no `--bare`, no API billing/fallback.
  No built-in Bash/Read/Web/Task, hooks, skills, extra MCP servers or persistent
  session. Keep the existing restricted environment and blocking MCP startup.
  Availability/authentication checks are not evidence that the model was invoked.
- Record the resolved model id on every request/run, UTC times and auth source.
  Stop on detectable model/client drift. Provider weights and sampling seed are
  not controllable through this CLI; same nominal id is not proof of frozen weights.
- Private Firefox `firefox-1553`; frozen npm/uv locks; headless window 1280×805,
  required **observed content 1280×720, DPR 1**. Pin host/OS/CPU/RAM, Python/Node, binary and
  extension hashes, fonts, timezone Asia/Seoul and locale en-US before execution.
  If these locale choices are not actually enforceable/observable, resolve the
  lock before running rather than inferring them from environment names.
- Fresh private HOME/profile and bridge ports; synthetic sessions only. Starting
  tabs use the real user channel and retain user ownership. No writable-user-tabs
  arm. Preserve the user's own browser, workspace and bridge.
- Model approval policy **decline**, including ask_user. Setup-only approvals remain
  outside the model channel and cannot be replayed as agent approval. Successful,
  denied and expired approvals are covered by deterministic conformance separately.
- All arms are confined to their fixture origin/about:blank. Enforce the fence on
  the trusted side; recursively inspecting `url` arguments is **not** sufficient
  for B evaluation/containers or D code. A/B cannot weaken an external fence using
  browser_set_policy. Validate constructed URL, redirect and raw-network attempts
  with a denied local canary endpoint before execution; do not test against public
  services. Legacy file/evaluation APIs must likewise not expose host credentials,
  benchmark/grader files or private state outside the fixture. Test denied file
  canaries through those paths; private HOME alone is not a filesystem sandbox.
  This common external task boundary is disclosed, not a claim that A/B themselves
  implement delegated isolation. If effective fences cannot be provided, stop and
  ask, not run anyway.
- Independent user channel observes viewport and tab identity; typing/view sampler
  remains 0.25 s. Sub-interval flicker can be missed. Do not inject new page scripts
  or change frozen graders to improve observability. Add private observer evidence
  alongside the existing verdict, including observations during script execution.
- Agent deadline: 180 s personal/typing, 240 s gallery; startup 120 s and cleanup
  30 s separately. Deadlines run through tools, not just model thinking. No queued
  writes after cancellation; preserve unknown outcomes and partial effects.
- Dependencies installed before the cohort; no per-arm install/network download.
  Fresh processes per run, ordinary warmed OS file cache (no privileged cache
  flushing). Record process startup versus runner first invocation and later
  invocations. Also run 10 no-model fresh-binding and 10 repeated-invocation probes
  per C/D binding on the same local fixture. C has no script worker; measure its
  direct dispatch baseline. D additionally reports worker initialization/cleanup
  and repeated script-invocation costs; no persistent Python locals/REPL.
  Report install size/time separately, not hidden in warm timings.

## 5. Before any model call: required evidence

The execution lock must include clean exact executor/analyzer and candidate commits,
this JSON + document hashes, full schedule hash, host/binary/dependency pins, supplied
context and effective permission hashes, and conformance artifact references.
The candidate commit cannot exist at preregistration time: filling these pins later
is allowed **only without changing methods, tasks, thresholds or hiding differences**.
Any substantive contract or protocol change gets a dated amendment before model
execution and renewed approval where its scope changes. A prefilled boolean is not
approval, and a manifest validator cannot replace a security or integrity review.
The planner's JSON/schedule hashes use UTF-8 compact JSON with sorted keys and
ensure_ascii=False; the document hash uses raw file bytes.

Required actual-entry-point preflight (no model, signed-extension path where applicable):

| Obligation | Evidence required |
| --- | --- |
| Baseline/native setup | #144 native coexistence and viewport checks pass on A/B and adapted C/D; skips do not count |
| Same C/D operations | Direct and injected Python traces agree on mode, tab/ref identity, strict resolution, defaults, result/errors, truncation and actual MCP image blocks |
| Read/draft boundaries | Disallowed actions, raw calls and newly constructed connections denied; no implicit act/grant escalation |
| Authority | User-tab ownership, user typing/takeover mid-script, URL/redaction/file rules, missing/revoked grants and policy forgery tested below SDK |
| Approval | External allow/deny/expiry/cancel, scope binding, caller mismatch and credential/continuation reuse; coordinate final #496 implementation |
| Recovery | Stale refs after navigation, ambiguous selectors, disconnect/timeout after write, partial completion, unknown receipt and no duplicate replay |
| Lifecycle | Syntax/runtime failure, cancellation/deadline, output/source/image/operation bounds, cleanup and orphan-process coverage |
| Isolation | Host file/env/credential access, raw network, protocol/ledger spoofing, self-approval and child process escape attempts rejected under declared threat model |
| Integrity and measurement | Generated-code artifacts captured; trusted operation ids and telemetry reconcile; fixture/grader and out-of-origin bypass attempts fail or block the cohort |

Use real fixture server counters, user-channel state and trusted receipts, not
`emit({success: true})`, final prose, a mock SDK or script exit status. The existing
full-native relay only walks structured arguments and approximates packed steps;
it is **not** the new runner's security or operation-count boundary. A new relay/
observer adapter belongs here, reusing frozen fixtures/graders rather than modifying
them. Observational hooks must be equivalent in C/D and checked for unchanged
results/policy; any hook on the pinned baseline is separately versioned/disclosed.

## 6. Units, attribution and reports

For every run retain raw private artifacts and produce a row with scheduled key,
source/metadata/guide hashes, external grades, safety, setup/model/runtime errors,
scorable status, missing evidence, timing and resources. Include every attempted
run; distinguish unattempted jobs after stopping. No replacing a failed row.

- **Model requests:** unique provider message/request id within a run, deduplicating
  repeated event fragments. Missing ids/usage are unknown, not zero. Count retries
  and model requests containing no tools; report provider-internal invisible work
  as a limitation. Reconcile with CLI totals.
- **MCP calls:** model-attempted calls and those reaching server separately, keyed
  by call id; discovery, help, publication and recovery separately. A script is one
  outer call, not one underlying operation. Preserve unlisted/refused calls.
- **Underlying operations:** trusted admitted/requested logical operations and
  actual native leaf dispatches/completions, with outer-call/run linkage, kind,
  target/authority lineage, timestamps and not_dispatched/dispatched/observed/unknown.
  Record internal observations and setup/observer work with separate roles. Never
  estimate executed operations by counting source statements or packed commands.
  Legacy evaluate is one opaque evaluation dispatch, **not proof of one DOM action**;
  any inner activity that cannot be observed stays explicitly unknown. Only C/D
  share a directly comparable typed-operation vocabulary.
- **Tokens:** total input = uncached + cache write + cache read; cache read is a
  subset, not an extra charge on total input. Report output, image input coverage,
  complete supplied definitions/guides and optional lookups separately. Record code
  source characters/UTF-8 bytes, JSON wrapper bytes, invocations, syntax/runtime
  errors and output tokens on code-bearing requests. Code tokens are a subset of
  output, never added again. The current Claude audit has no exact code-token split:
  freeze a justified tokenizer/measurement method with provenance before approval;
  label any estimate and its limits, never relabel characters/4 or entire request
  output as exact code tokens. Unavailable required coverage prevents a full verdict
  until the user resolves the measurement limitation before execution.
- **Cost:** CLI list-price estimate and its pricing provenance versus actual billing
  (subscription quota, no API credit). Freeze the estimation/pricing method; report
  missing cost rather than zero. No claims about the user's subscription dollar ROI.
- **Time/resources:** wall time from per-run launch through fixture finalization,
  plus setup, model phase, native work, first/warm runner invocation, output and
  cleanup spans. Track browser/bridge/runner/client process trees, CPU, sampled peak
  and time-weighted RSS, coverage/errors and leaked processes. Summed RSS is not
  unique memory; correlated/overlapping spans must not be added as if disjoint.
- **Integrity audit:** review all generated Python and legacy evaluation/container
  content for fixture/reward bypass and prohibited access. AST/text review is
  supplemental, not confinement. A/B's broader APIs make configuration comparisons
  noncausal; successful page-JS reward forgery is not a success to retain silently.

Report all-attempt totals and cost/time per successful primary task (including
failed-attempt spending in the numerator), then paired **joint-success** ratios on
the same unit/repetition keys. Pair-specific A/C, C/D, A/D and B/D sets are distinct;
also show the four-way intersection. Do not pool gallery into primary ratios.
Show every task's four outcomes/metrics, order effects, medians, ranges and outliers.
A low-cost early failure is not an efficiency improvement. Joint-success ratios
condition on observed outcomes and can have selection bias when success changes;
they alone are not an unconditional causal cost effect. Keep the all-attempt,
intention-to-treat results and success discordances beside every conditional claim.

## 7. Frozen decision rule (operational pilot gate, not universal inference)

All gates apply; no trading safety or success for tokens. Thresholds are engineering
minimums selected before results, not fitted confidence or power claims. The 5%
default cost improvement avoids calling negligible drift a win; 10% composition
improvement must justify the added runtime. 5–10% overhead guards protect B parity,
simple tasks and wall time. Four repeats on one variant are limited evidence.

1. **Evidence/integrity:** complete 496-run schedule, unchanged pins and valid
   required telemetry/grades; all deterministic preflights pass. Missing/incomplete
   evidence → **inconclusive**, not zero-cost success. Confirmed candidate safety
   violation → **no-go** even if other evidence is incomplete.
2. **Safety:** zero C/D unauthorized/wrong-target writes, user input loss, blind
   replay/duplicate uncertain writes, credential/approval escape or out-of-fixture
   effects. Typing must preserve input/view on all four C/D runs. Attempted actions
   correctly refused are reported, not confused with successful unauthorized writes.
   Wrong-target safety events mean identity misrouting, stale/foreign-handle fallback
   or protected-tab effects. A model choosing the wrong allowed control/value is
   separately a task error unless it breaks an explicit fixture safety rule; do
   not redefine these categories after seeing which arm errs.
3. **Success:** C and D each solve at least 95% of 116 primary runs. For **each primary
   unit**, C succeeds at least as often as A; D at least as often as A, B and C,
   over four repeats (zero allowed count loss). Report all discordant paired outcomes too.
   Use unchanged task_success, and v3_user_input/view for typing. A loss → no-go,
   not rescued by a higher total elsewhere. Gallery results remain disclosed diagnostics.
4. **Coverage for efficiency:** each compared pair has joint success on at least
   90% of primary keys, covers all eight categories, all four simple units and all
   eight composition units, with at least one joint success for every primary unit.
   Zero denominator (including per-repeat ratios) or inadequate coverage → inconclusive.
5. **Default value:** primary joint-success list-price ratio D/A ≤0.95, D/B ≤1.05.
   **Composition value:** composition-stratum D/C ≤0.90, all-primary D/C ≤1.05.
   Simple-stratum D/A and D/C ≤1.10; primary end-to-end wall D/A and D/C ≤1.10.
   Also require all-attempt primary cost per successful task D/A and D/C ≤1.05.
   Do not replace these metrics with MCP calls, characters or a favorable median.
6. **Variation:** for the two claimed improvements (primary D/A and composition
   D/C), ratio <1 in at least three of four repetitions and the one-sided 95%
   cluster-bootstrap upper bound <1. Resample unit ids with replacement 10,000
   times, preserving all paired repeats of each unit: reset Python random.Random(504)
   separately for each comparison, sort eligible unit ids lexicographically and
   draw len(ids) entries with rng.choices(ids, k=len(ids)) per replicate. For D/C use
   only the eight composition units. Ratio = sum D costs / sum comparator costs.
   Use sorted bootstrap index
   ceil(0.95*N)-1, no favorable seed selection. Report intervals for other ratios
   descriptively. Passing point thresholds but failing direction/interval support
   is **inconclusive**; a measured guardrail/point threshold failure is **no-go**.

A complete pass is **go for a separately approved default proposal**, not permission
to merge/release/change the user's environment. Positive Python feasibility and the
applicable #504 gate precede JS implementation; JS then has separate parity/lifecycle/
real-browser smoke requirements. No-go/inconclusive stops the affected goal gate:
show evidence and options to the user; do not relax criteria, silently add runs or
force either default rollout or JS expansion.

## 8. Budget, stops and approval packet

Proposed subscription allocation: **at most 496 model runs**, no retries or hidden
paid pilot; first scheduled block is the first data, not a disposable warm-up.
Stop starting new runs at **12 active campaign hours** or **$100 accumulated CLI
list-price estimate**. These are review stops, not subscription billing caps; the
last in-flight run may cross them. Per-run/startup/cleanup deadlines still apply.
The current subscription harness has no hard dollar cap; do not pretend its
API-only `--budget-usd` flag enforces one. No API/model/account fallback.
The summed agent deadlines are 25.33 h, longer than the 12 h campaign review stop;
completion within budget is not guaranteed. A stopped cohort is inconclusive.

Stop immediately for a safety/integrity incident, unexplained telemetry/pin drift,
unscorable run (including timeout/quota/client failure), cleanup leak or environment
loss. Ordinary scorable task failures continue to the fixed end; no early success
stopping. No automatic quota-reset wait/resume or retry. Preserve every attempted
row and artifacts; further execution/replacement campaigns require user approval
and must not erase the interrupted cohort.

**Planning estimate, not new run evidence:** existing v0.7.2 subscription records
for these 31 v0 units cost $2.8298714 at CLI list price (median $0.086047, max
$0.1487208), with 816.896 s agent elapsed (median 25.157 s, max 62.469 s). Multiplying
by 16 gives **$45.28** and **3.63 h agent elapsed**, before full startup/cleanup.
Allow **$45–$90 list-price equivalent and roughly 4–8 h** as a provisional planning
range, not a confidence interval or hard upper bound: old runs used a narrower
UI allowlist and partly shared load, while B/D add discovery/runtime/guide costs.
API-key credit spending is disabled by the proposed auth configuration, but the
496 runs consume subscription quota whose remaining capacity is not known.
Subscription **extra-usage billing** has not been checked: it must be disabled or
separately approved before running. Do not claim that all incremental charges are
necessarily $0 merely because the client uses OAuth.
Refresh the estimate and request approval after the candidate and telemetry gates.

Provenance: `artifacts/opus-subscription-v0.7.2-merged/suite-log.jsonl`, Kitsune entries
personal-v0, both gallery-v0 layouts (ui-table only), coexistence-typing-v0. Private
source summaries and SHA-256:

| Summary relative to artifacts/ | SHA-256 |
| --- | --- |
| personal/20261103T232045Z-0d75d35acd/suite-summary.json | `7ecdbf5da4b769c16b3eb99c750c50f288b1723eeab217af7d98d4aa2c8e1c20` |
| gallery/20261103T234904Z-10845e7144/suite-summary.json | `28252d71e993450258dd2633118ff0d3da4660eb310f0db7727086bbf972cc72` |
| gallery/20261104T011308Z-33a55c0b91/suite-summary.json | `fdb24f245aa8e881b0cc3a13d2227f5c71b811134121231526c5fdaa736a9789` |
| coexistence/20261104T003659Z-bf68298ee0/suite-summary.json | `61b423cbb10101721bf169e5e476625f2964ae14f795fa3cdb637b08b2b7517c` |

Approval must identify protocol+execution-lock hashes, model/harness/auth, 496-run
scope and order, estimated cost/quota/time, review stops, unresolved limitations
(including code-token attribution), and prohibition of unapproved retries. It does
not approve defaults, merge or release. Runtime hashes/conformance and approval are
currently absent; this registration prepares them, never fabricates readiness.
