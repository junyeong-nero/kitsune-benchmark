# Sonnet / Opus follow-up: is the target-view result Haiku-specific?

[Reports](README.md) · [Pre-execution plan](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/experiments/2026-10-22-sonnet-opus-plan.md) ·
[Haiku target-view experiment](2026-10-22-target-view-ab.md)

## Answer

**There is a model-sensitive signal, but this is not simply a Haiku problem.**
On the four deliberately selected regression cases, the catalog arm reduced
requests and instrumented time with both Sonnet and Opus, unlike the historical
Haiku result on those same cases. Yet it still increased estimated cost, and
precise media observation remained unreliable.

A new no-model probe establishes a concrete **Kitsune v0.3.0 screenshot contract
failure**: a freshly observed video ref fails in `browser_screenshot(ref=...)`,
while `browser_screenshot(selector="video")` succeeds on the same tab. Opus
attempted ref-based cropping in both arms and fell back to page images. That
behavior cannot be explained solely by a weak model failing to choose a crop.

Do not reject interaction/media-oriented presentation based on Haiku alone;
do not adopt this formatter globally based on four one-shot pairs either.
Fix the demonstrated screenshot-ref failure, preserve local control context,
and then repeat the representation comparison with a stronger model.

## API, design and limits

- Authenticated free GET of Anthropic `/v1/models` confirmed
  **`claude-sonnet-5-5`** and **`claude-opus-5-5`**. Every assistant event in the
  resulting traces identifies the exact requested model. No alias substitution.
  This checks availability, **not remaining account credit**.
- Claude Code **2.1.303**, medium effort, **claude-api bare**, clean Kitsune
  **v0.3.0 `99a90d22c83d6e931814b3c3dadd96c08c633820`**, lean, same 14 tools,
  private Firefox build 1553. Original task prompts/graders and the exact
  preceding formatter were retained; known presentation limitations were not
  fixed during the comparison.
- Four cases: personal `pb-research-01`; crowded `ui-rowmenu`; isolated
  `mm-chart` and `mm-video`, variant 0. Native **A** vs catalog **B**, once each:
  **8 runs/model, 16 total**. Opposite AB/BA orders across models.
- Models ran **in parallel**, each sequential internally, with separate
  profiles/ports/fixtures/output folders. Shared host/API capacity confounds
  intrinsic speed comparisons between models.
- Hard execution window 18 minutes; 120-second agent cap (shorter than the
  previous 180/240-second caps). $0.50/run and $4/model caps. No timeout,
  unscorable run, retry or fallback occurred.
- **Both workers completed in 277.0 seconds: 4 min 37 sec.** This is the
  benchmark execution time, not documentation/test time. The bounded design
  met the requested sub-30-minute experiment goal.
- Estimated API spend: **Sonnet $0.241199 + Opus $0.572363 = $0.813562**,
  below the $8 cap. Client estimates, not invoice-verified charges.

The Haiku reference is historical: three repetitions per selected case from the
previous cohort. Selection deliberately targets its regressions. There is no
contemporaneous Haiku control and only one stronger-model repetition, so these
are mechanism clues, **not statistical confirmation or a general leaderboard**.

## Within-model results

Four runs per arm for each stronger model. Input already includes cached input.

| Metric | Sonnet A | Sonnet B | Opus A | Opus B |
| --- | ---: | ---: | ---: | ---: |
| Scorable | 4 | 4 | 4 | 4 |
| Functional successes | 4 | 4 | 4 | 4 |
| Strict v1 successes | 3 | 3 | 4 | 4 |
| v2 successes | 3 | 3 | 4 | 4 |
| Model requests | 29 | 25 | 34 | 30 |
| Input tokens | 221,483 | 231,766 | 262,840 | 266,280 |
| Output tokens | 2,848 | 2,804 | 3,952 | 3,264 |
| Failed tool calls | 2 | 1 | 4 | 3 |
| Instrumented elapsed, seconds | 83.458 | 76.360 | 116.716 | 96.535 |
| Client-estimated USD | 0.112131 | 0.129068 | 0.268073 | 0.304290 |

The catalog's **B vs A** effects on exactly the selected cases:

| Model / cohort | Requests | Input | Elapsed | Estimated cost |
| --- | ---: | ---: | ---: | ---: |
| Historical Haiku, 3 repeats | **+15.5%** | +40.0% | **+21.4%** | +40.3% |
| Sonnet, 1 repeat | **−13.8%** | +4.6% | **−8.5%** | +15.1% |
| Opus, 1 repeat | **−11.8%** | +1.3% | **−17.3%** | +13.5% |

Do not compare the stronger models to the earlier *all-ten-task* Haiku delta;
that is a different task mix. The table above filters Haiku to the same four
units before computing its within-model ratio.

Sonnet's three jointly strict-successful cases: requests −18.2%, input +4.4%,
elapsed −12.0%, estimated cost +29.1%. Opus has four joint successes. Thus the
request/time reduction is not merely one arm failing early.

### Costs are sensitive to cache creation and history

Despite fewer requests, catalog input did not decrease. Cache-creation input:

- Sonnet A/B: **25,574 / 32,392**; cache-read input **195,843 / 199,316**.
- Opus A/B: **28,370 / 38,645**; cache-read input **234,394 / 227,567**.

The larger catalog/history and differing screenshot choices contribute to
context growth, while warm/cold prefix order also matters. Cache state was not
normalized. The observed +13–15% dollar difference is therefore not an intrinsic
price multiplier for the formatter; it is the actual client estimate in this
small, ordered experiment. No speculative normalized-price estimate is used.

## Case-level findings

### Chart: stronger models used a better fallback in the catalog arm

| Chart metric | Sonnet A/B | Opus A/B |
| --- | ---: | ---: |
| Requests | 7 / **4** | 7 / **4** |
| Input | 43,296 / **22,587** | 45,881 / **23,684** |
| Seconds | 23.791 / **9.859** | 25.036 / **14.082** |
| Wrong submissions before success | 2 / **0** | 1 / **0** |

The native observation omits the sixth radio option via repeated-item
compaction; `e18` identifies the **confirmation button**, not that missing radio.

Observed action traces:

- Sonnet A clicked `e18` before selecting the correct radio, then recovered with
  `selector='input[value="6월"]'`.
- Opus A supplied both `ref=e18` and a selector for the sixth radio. The action
  used the ref, so it hit confirmation; it then retried with the correct selector.
- **Both B runs used the screenshot and clicked coordinates `(450, 493)` to
  select the intended radio, then clicked the confirmation ref.** No wrong
  submission occurred.

This supports a concrete hypothesis: the role-grouped representation can help
stronger models distinguish an omitted target from the next visible ref and
switch to visual grounding. It is not proof from a single attempt. It also does
not mean the formatter restored the omitted radio or exposed the missing chart
image: those tool-coverage limitations remain.

### Crowded row menu: fewer requests, mixed cost

- Sonnet: **9 → 6 requests**, 99,635 → 68,117 input, 22.837 → 17.592 s.
- Opus: **7 → 6 requests**, but 75,631 → 88,335 input; 22.026 → 18.103 s.

Both catalog runs succeeded without tool errors. Sonnet's native run attempted
an unsuccessful precise screenshot before recovering. The catalog can aid
selection here, but Opus's extra context still raises cost. One run cannot
establish that global role grouping is better than a locality-preserving view.

### Research: formatting does not repair the safety/action contracts

Sonnet was functionally correct but changed a starting tab URL in **both** arms,
so both fail v1 and v2. Both also incurred an unmet save-text expectation.
Opus kept starting tabs and passed both arms, but each run encountered two
stale refs after native `browser_dom` replaced the reference map.

These errors are distinct from the previous hidden-enrichment ref invalidation:
this formatter makes no extra browser calls. Native observations can still
replace refs, and stronger models can still misuse the existing contract.
The one-task safety difference is not a general Opus safety ranking.

### Video: stronger models do not automatically choose cheaper observation

Sonnet:

- A: 1 page image + 3 video crops; **38,488 input, 16.671 s**.
- B: 11 page images, no crop; **98,609 input, 28.243 s**.

Opus:

- A: a failed ref crop, then 5 page images; **74,586 input, 39.480 s**.
- B: a failed ref crop, then 6 page images; **89,668 input, 30.702 s**.

All four solved the video without wrong submissions. Sonnet B reproduces the
full-page observation inefficiency seen in Haiku. Opus actually attempted the
more precise ref route; the tool rejected it before it fell back. The runtime
comparison is noisy (media playback/frame timing and parallel activity), but
the crop choices and dimensions are directly recorded.

## Confirmed no-model bug: screenshot(ref) vs screenshot(selector)

On v0.3.0, `browser_screenshot` explicitly documents element capture by
**ref/selector** (`src/kitsune/server.py`, function at line 691 in the pinned
revision). In both Opus video runs, a fresh snapshot exposed:

```text
- video "" [ref=e10] [... duration=8 ...]
```

Then `browser_screenshot(ref="e10")` returned:

```json
{"error":"No element matches: e10"}
```

A separate deterministic probe, with **no model** and an explicit identical
`tab_id`, confirms:

| Request | Result |
| --- | --- |
| Fresh native snapshot → screenshot(ref="e10") | `isError:true`, `No element matches: e10` |
| Same page → screenshot(selector="video") | Success, **320×180** image |

Tabs remain unchanged. No formatter is involved in this probe. Thus at least
this observed fallback is a **tool implementation/contract problem, not model
incapacity or catalog formatting**. The probe does not establish every possible
cause in the screenshot pipeline or every element type; it establishes the
observable ref-vs-selector discrepancy for this video fixture.

Reproduce without inference:

```sh
uv run --locked python scripts/probe-media-ref.py
```

Evidence: `artifacts/target-models-20261022/media-ref-probe.json`.

## Revised direction

1. **Fix and regression-test screenshot(ref) first.** A supported precise
   observation path must work before adding another asset API or blaming the
   agent for falling back to the whole page. Keep selector/ref identity and
   stale-generation behavior consistent.
2. Retain the interaction/media-oriented view as an **experimental option**, not
   a replacement default. Stronger-model results justify continued exploration;
   Haiku-only negatives should not settle the design.
3. Preserve local form/row context and attach omission/expansion markers to their
   control group. Do not solve usability by adding ever more line bookkeeping.
4. Provide actual asset coverage and crop identity where native snapshots omit
   images; classification alone cannot recover absent information.
5. After the ref-capture fix, repeat these same cases with Sonnet/Opus and a
   contemporaneous Haiku control. Measure time, cost and safety separately;
   fewer requests does not guarantee lower spend.

No evidence here requires a small selector model. The new finding strengthens
the case for fixing deterministic target-to-observation links first.

## Validation and artifacts

- Parallel coordinator: `kitsune_benchmark/target_model_experiment.py`.
- Offline analysis: `kitsune_benchmark/target_model_analysis.py`.
- Root evidence: `artifacts/target-models-20261022/plan.json`, `status.json`,
  `analysis.json`; independent `sonnet/summary.json`, `opus/summary.json`.
- Native/agent runs: `artifacts/target-models-sonnet/` and
  `artifacts/target-models-opus/`.
- Tests: **145 run, 5 optional skips, no failures**. Model-specific controls,
  deadline reserve, unchanged global config, opposite schedules and one-shot
  pairing have focused regression tests. The Firefox ref probe reproduced the
  expected error; it is intentionally a diagnostic, not a claim the bug is fixed.

```sh
# No inference: inspect the exact plan.
uv run --locked python -m kitsune_benchmark.target_model_experiment

# API-consuming repeat; fresh output directory, same 18-minute / $8 bounds.
uv run --locked python -m kitsune_benchmark.target_model_experiment \
  --output artifacts/target-models-repeat-new --execute

# Offline analysis of recorded runs.
uv run --locked python -m kitsune_benchmark.target_model_analysis \
  artifacts/target-models-20261022 --output /tmp/target-model-analysis-new.json
```

Do not generalize four selected one-shot cases to all browsing or all models.
Historical Haiku, opposite-but-unrepeated order, cache state, concurrency,
shorter timeout caps and media timing remain confounders. These results narrow
mechanisms and revise the design recommendation; they do not prove that larger
models universally resolve the interface problems.
