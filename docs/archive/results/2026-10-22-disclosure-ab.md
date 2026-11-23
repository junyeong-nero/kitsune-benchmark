# Disclosure × expect: 72-run Kitsune mechanism experiment

[Reports](README.md) · [Pre-execution plan](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/experiments/2026-10-22-disclosure-plan.md) ·
[0.3.0 comparison](2026-10-22-kitsune-0.3.0.md)

## Decision summary

**Do not introduce a paid small-model disclosure selector yet.** This experiment
finds a conditional benefit from richer observations plus action guidance, but
not a general benefit from returning more information. More importantly, it
identifies two concrete interface problems that a small model would otherwise
have to work around:

1. **Observation can invalidate action references.** Adding a snapshot to a
   seemingly read-only page-text response replaces existing refs, even without
   a page change. A no-model controlled probe reproduces this.
2. **Valid `expect` syntax does not mean a grounded postcondition.** Guidance
   removed invalid expectation formats, but models then waited for guessed CSS
   selectors or the wrong field. A no-model probe confirms that semantic input
   `type: text` does not imply a literal `[type="text"]` HTML attribute.

The evidence supports **freshness-aware, task-sufficient observation design**
and **action-target-bound validation** before a learned routing layer. It does
not establish that a `jev-like` model is necessary or cost-effective. No such
model was selected or invoked; the operator's specific model family remains
unspecified.

## Experiment and validity

- Pre-execution plan: linked above; treatment definitions and task selection were
  written before these model runs.
- Clean Kitsune **v0.3.0 `99a90d22c83d6e931814b3c3dadd96c08c633820`**, explicit
  **lean**, same 14 exposed tool definitions in every arm.
- Claude Code **2.1.303**, **Haiku 5.5**, effort medium, **claude-api bare**;
  private Firefox build 1553, isolated profile and synthetic fixture per run.
- Six tasks: `pb-current-01`, `pb-current-02`, `pb-tabs-01`, `pb-research-01`,
  `pb-account-01`, `pb-handoff-01`, variant 0. Three repeats per task/arm:
  **18 matched task-repetition blocks × four arms = 72 runs**.
- Rotating Williams orders: ABDC, BCAD, CDBA, DACB, indexed by task + repetition.
  No simultaneous browser runs. The 18 blocks do not perfectly balance four
  possible orders; no controllable sampling seed or cache reset.
- **72/72 scorable, no task execution timeouts, retries or model fallback.**
  All 72 achieved functional success; failures below are protocol/safety failures.
- **$0.150824 client-estimated API cost**, below the $2 cap. Not invoice-verified.
  Suite wall time was 2,276.3 s; summed instrumented agent elapsed 1,663.1 s.
- Initial launch errors occurred before inference: exclusive JSON creation was
  incorrectly used for status updates; the custom runner initially inherited
  the generic Codex executable default; a detached launch also inherited a
  deleted sandbox temp directory. Fixed, regression-tested, and preflight
  artifacts retained separately. None is a replaced model attempt.
- Final validation: **125 tests run, 5 skipped, no failures**, including the
  opt-in real-Firefox enrichment test. All 72 runs have zero execution-audit
  violations, one identical exposed-tool catalog hash, unchanged experiment
  implementation hashes and a clean constant Kitsune revision. Audit validity
  is separate from the task safety/protocol failures reported below.

### Treatments

| Arm | Observation response | Prompt |
| --- | --- | --- |
| **A** | Native | Original |
| **B** | Rich bundle | Original |
| **C** | Native | Original + expect guidance |
| **D** | Rich bundle | Original + expect guidance |

The rich relay forces `include_active=True` for inventory lists and `text=True`
for snapshots. A successful `page_text` result is retained and supplemented with
a native actionable snapshot for the same tab. No new tool, JS, cookies, source
inspection or evaluator data is exposed. Native text caps remain. Original
scopes/depth are retained. All extra RPCs are measured as `role=disclosure`.

Guidance gives selector/value, same-URL-save and new-tab examples, warns against
replaying a dispatched write, and says not to duplicate sufficient confirmation.
It adds about **358 first-request input tokens**. It does not force shorter
waits or remove agent-supplied expectations.

**Important:** B is a richer-observation *bundle*, not a pure information-volume
intervention: generating supplemental snapshots can change ref state. That
risk was noted in the plan and is a confirmed mechanism below. A negative B
result does not rule out all richer or adaptive disclosure designs.

## Main results (18 runs per arm)

Input includes cached input; cache is not added a second time. Result bytes are
the UTF-8 tool-result content delivered in the agent trace, not exact API tokens.

| Metric | A native | B rich | C expect | D rich + expect |
| --- | ---: | ---: | ---: | ---: |
| Functional successes | 18 | 18 | 18 | 18 |
| Strict v1 successes | 15 | 16 | 16 | 17 |
| v2 cleanup successes | 16 | 16 | 17 | 18 |
| Model requests | 165 | 170 | 166 | **152** |
| Input tokens | 1,120,559 | 1,190,041 | 1,173,590 | **1,102,344** |
| Output tokens | 32,297 | 32,988 | 31,978 | 29,987 |
| Agent MCP calls | 199 | 198 | 196 | 176 |
| Additional enrichment RPCs | 0 | 39 | 0 | 41 |
| Failed agent calls | 29 | 34 | 24 | 18 |
| Instrumented elapsed, s | 417.883 | 418.838 | 431.589 | 394.756 |
| Client-estimated USD | 0.037764 | 0.038750 | 0.037827 | 0.036482 |
| Delivered result bytes | 161,825 | 176,471 | 126,307 | 203,469 |
| Invalid expect-format errors | 4 | 6 | **0** | **0** |
| Outcome timeouts | 17 | 13 | 17 | 14 |
| Stale-ref errors | 1 | 5 | 1 | 2 |
| Adjacent read-only model requests | 23 | 22 | 26 | 22 |
| Requests with multiple tool calls | 43 | 38 | 38 | 29 |

Additional enrichment time was **1.204 s in B / 1.682 s in D**, included in
instrumented elapsed; all 80 supplemental observations succeeded. Counting only
agent calls would hide this extra work: total agent + enrichment calls are
199 / 237 / 196 / 217. A model-request reduction is not necessarily fewer native
browser RPCs.

### Registered matched contrasts

Percentages compare sums over the same 18 task-repetition blocks.

| Change | Requests | Input | Elapsed | Estimated cost |
| --- | ---: | ---: | ---: | ---: |
| **A → B: rich alone** | +3.0% | +6.2% | +0.2% | +2.6% |
| **A → C: guidance alone** | +0.6% | +4.7% | +3.3% | +0.2% |
| **C → D: rich with guidance** | −8.4% | −6.1% | −8.5% | −3.6% |
| **B → D: guidance with rich** | −10.6% | −7.4% | −5.8% | −5.9% |

These point estimates suggest an interaction between useful information and
instructions for using it. They do **not** show that either treatment alone is
a general win. Formal interaction significance was not established.

On the fixed jointly v1-successful blocks of each comparison:

| Change | Joint blocks | Requests | Input | Elapsed |
| --- | ---: | ---: | ---: | ---: |
| A → B | 14 | +0.8% | +3.0% | −1.2% |
| A → C | 15 | −3.8% | −0.4% | +3.5% |
| C → D | 15 | −12.3% | −11.6% | −14.7% |
| B → D | 16 | −13.7% | −11.2% | −9.9% |

These are different joint sets; do not rank their percentages against each other.
Success is treatment-dependent, so the full matched results remain primary.

### Uncertainty and concentration of the apparent combined benefit

Descriptive combined **A → D**: requests **−7.9%**, input **−1.6%**, elapsed
**−5.5%**, estimated cost **−3.4%**. However:

- Only **9/18** matched runs were faster; the median paired elapsed difference
  was **+0.0065 s** (essentially unchanged), despite the aggregate time saving.
- **`pb-current-01` alone saved 28.482 s**, larger than the whole combined saving
  of 23.127 s. Excluding it leaves 353.790 → 359.145 s, **1.5% slower**;
  input becomes 956,739 → 1,001,109, **4.6% higher**.
- Task-cluster percentile bootstrap (5,000 resamples, six task clusters,
  repetitions kept together) for A → D: requests **[−20.4%, +3.8%]**, elapsed
  **[−23.4%, +11.1%]**, input **[−17.3%, +11.7%]**. These are exploratory small-
  sample uncertainty summaries, not a corrected confirmatory test.
- C → D reduced requests in five of six task totals; its request interval is
  [−13.4%, −3.4%], but elapsed [−22.0%, +1.5%] and input [−14.0%, +0.9%]
  still include no improvement. Multiple exploratory comparisons and selected
  tasks prevent a broad significance claim.

Thus the most defensible result is a **conditional request-reduction signal**,
not a proven general latency or dollar-cost advantage.

## Mechanism 1: richer reading can invalidate the agent's context

Observed B / `pb-current-01` / repeat 1 sequence:

1. Inventory with active-page context returned refs **e6–e10**.
2. `page_text` was supplemented with a new snapshot containing **e11–e15**.
3. The agent used the earlier **e9** for typing and **e10** for clicking.
4. Both failed with stale refs, causing recovery work.

The enriched response explicitly says its refs are fresh, but the agent reused
older identifiers anyway. Merely sending more information did not ensure it
reconciled state correctly. B has five stale-ref errors vs A's one; not every
stale error has this same cause, so do not attribute all four extra errors to
this mechanism without individual trace review.

### Controlled no-model reproduction

`scripts/probe-disclosure-refs.py` runs fresh identical fixtures:

- Native snapshot → native `page_text` → reuse old ref as snapshot subtree:
  **succeeds**.
- Native snapshot → rich `page_text` (extra snapshot) → reuse old ref:
  **fails**, `state.reason="snapshot_replaced"`, with a `currentRef` mapping.
- Starting tabs remain unchanged; no page write or model inference is involved.

This directly establishes the **ref-lifetime side effect of this rich adapter**.
It is not proof that all production observation enrichment has this problem.

**Implication:** disclosure policy must consider reference freshness and cached
observation identity, not just relevance and token budget. Before a learned
selector, investigate reusing a still-valid snapshot, explicit observation IDs,
or preserving references for unchanged elements under a carefully tested safety
contract. Never silently remap old write targets without identity validation.

## Mechanism 2: syntactically valid expectations can be ungrounded

Guidance reduced invalid expect formats from **10 errors across 36 runs in A+B
to 0 errors across 36 runs in C+D**, but outcome timeouts changed only **30 → 31**. It changed the *kind* of
mistake, not simply removed waiting.

| Timeout condition | A | B | C | D |
| --- | ---: | ---: | ---: | ---: |
| selector + value | 2 | 0 | 12 | 9 |
| text | 5 | 5 | 3 | 5 |
| URL changed | 5 | 4 | 0 | 0 |
| new tab | 2 | 2 | 2 | 0 |
| other selector conditions | 3 | 2 | 0 | 0 |

Of C+D's **21 selector/value timeouts**, **20 report `found:false`**. The last
matched a field, but expected the literal value `"x"` after filling real answer
text; its observed value correctly differed from that expectation. Examples include guessed
`#title`, `input[name='title']`, `textarea`, and `input[type=text]` selectors.
These are not evidence of a model needing more prose from the page.

### Controlled no-model reproduction

`scripts/probe-disclosure-targets.py`, actual `pb-current-02` memo page:

- `browser_forms` reports inputs with semantic **`type:"text"`**.
- HTML is `<input name="…" value="…">`: no literal `type` attribute.
- `snapshot(selector='form input[type="text"]')`: **selector not found**.
- `snapshot(selector='form input')` and a real `input[name="…"]`: **succeed**.
- The form report also gives both fields the same broad generated selector
  `form > p > label > input`; they do have distinct refs/names. That selector
  alone is not a unique identity for either field.

The native value-expect implementation resolves the first selector match. An
agent can correctly address the action by ref, then invent a separate selector
for its postcondition and wait on the wrong or nonexistent element.

**Implication:** prefer an explicit opt-in **same-action-target value check**
whose identity is resolved by the server, or return verified unique observation
locators. Preserve redaction, document replacement and dispatch/outcome semantics.
This reduces the agent's need to translate semantic UI state into CSS. Better
format descriptions alone do not solve that grounding problem.

## Does this justify a small-model disclosure selector?

### What is supported

- Useful observation and action policy interact; returning the smallest response
  is not always best.
- Different task/phase needs are plausible. Text reading, action targeting,
  postcondition checks and stale-context recovery are different problems.
- A freshness-aware rule can plausibly avoid gratuitous snapshot regeneration.
  This rule is a candidate, not a measured win from these runs.

### What is not supported

- That missing page context was the main cause of the original extra requests.
  Rich-only did not improve requests, and its ref side effect confounds an
  information-volume-only interpretation.
- That an adaptive policy beats a fixed policy: **no adaptive arm was executed**.
- That a learned selector beats rules, or that a specific `jev-like` model pays
  for its cost. No model-specific price, latency, quality or privacy evaluation
  was performed.
- That the best arm chosen retrospectively per task would generalize. No such
  oracle is reported as an implemented router.

### Economic and latency headroom (illustrative, not a guarantee)

Even if the noisy A → D point estimate held, savings are only **$0.001282 over
18 runs**, about **$0.000071 per task**, with **1.285 s mean elapsed saved per
task**. D contains 81 eligible disclosure decisions:

- A selector called for every decision would need to fit below roughly
  **$0.0000158 and 0.286 s per decision** just to preserve those point-estimate
  gains, before its own mistakes or extra prompt history.
- A once-per-task selector has the larger per-task ceiling above, but cannot
  respond to every page-state change.
- These are break-even **upper bounds relative to A**, not a measured marginal
  budget for adding a selector to D. A selector must still beat D (or a simpler
  rule) to justify its incremental cost.
- The latency median is essentially unchanged and uncertainty spans regression;
  there is **no established positive headroom**. A more expensive main model
  could change the economics, but was not tested.

Given the cheap Haiku baseline, a remote paid routing model on every browser
call is premature. Local/very-small models may have different economics, but
need their own measurements; local inference is not automatically free or fast.

## Recommended next experiment — not executed here

1. **Fix observation coherence first.** Do not regenerate refs merely to append
   information already covered by a valid observation. Make freshness explicit.
2. **Add target-bound postconditions.** Compare against agent-generated CSS
   expectations on the same fill/save cases; do not just disable validation.
3. Test **native vs coherent-rich vs deterministic adaptive disclosure**, with
   new held-out tasks and repeated/counterbalanced runs. Use only current UI/
   action state, no fixture IDs, answers or hindsight.
4. Only if the rule-based adaptive arm wins, test a small model **on ambiguous
   decisions only**. Count its input/output, latency, cache effects, errors and
   privacy exposure. Keep raw page text untrusted and redact before routing.
5. Require unchanged functional/safety outcomes and improved total cost/time,
   not merely fewer result bytes or a retrospectively selected best arm.

A practical selector output would choose a bounded content scope and level,
not freely summarize facts or invent refs. Its features should include whether
current refs remain valid and whether the last action was dispatched. This is
more grounded than a generic "compress context" model.

## Evidence and reproduction

Private artifacts: `artifacts/disclosure-experiment-20261022/`:

- `plan.json`, `summary.json`: schedule, implementation/prompt hashes, 72 run
  references, per-run evidence and costs.
- `analysis.json`: per-run metrics, matched contrasts, task-cluster intervals.
- `target-probe.json`, `ref-probe.json`: no-model mechanism probes.
- Per-run browser/agent/RPC evidence under `artifacts/disclosure/<run-id>/`.

No model calls to inspect the plan or analyze existing evidence:

```sh
uv run --locked python -m kitsune_benchmark.disclosure_experiment
uv run --locked python -m kitsune_benchmark.disclosure_analysis \
  artifacts/disclosure-experiment-20261022/summary.json \
  --output /tmp/disclosure-analysis-new.json
```

Explicit API-consuming reproduction (fresh output directory required):

```sh
uv run --locked python -m kitsune_benchmark.disclosure_experiment \
  --output artifacts/disclosure-repeat-new --budget-usd 2 --execute
```

No-model native probes:

```sh
uv run --locked python scripts/probe-disclosure-targets.py
uv run --locked python scripts/probe-disclosure-refs.py
```

Production personal benchmark behavior is unchanged: all interventions live in
separate opt-in experiment/relay modules. Do not silently use these responses
as "native Kitsune" evidence. The six selected short synthetic tasks, one
model, three repetitions, imperfect order balance, uncontrolled API caching,
and stateful enrichment limit generalization. This is not a live-browser,
long-document, multimodal or general selector-model benchmark.
