# Target/action catalog vs native snapshot: 60-run A/B

[Reports](README.md) · [Pre-execution plan](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/experiments/2026-10-22-target-view-plan.md) ·
[Previous disclosure experiment](2026-10-22-disclosure-ab.md)

## Recommendation

**Follow-up:** the [targeted Sonnet/Opus experiment](2026-10-22-sonnet-opus-target-view.md)
finds a different request/time trend on four selected cases, with higher cost,
and reproduces a native screenshot-ref failure. The recommendation below is
specific to this Haiku cohort, not a model-independent rejection of the direction.

**Do not replace the default snapshot with this global role-bucketed catalog.**
The representation is losslessly reconstructable and does not regenerate refs,
but it did not produce an overall efficiency win: requests **−2.2%**, input
**+6.0%**, elapsed **+2.9%**, estimated API cost **+10.0%**, equal strict success.

The useful next direction is narrower:

- Explore an **opt-in, locally scoped interaction view**, preserving nearby
  form/row/section context rather than globally separating every control from
  its explanation. The personal-task signal is weak and task-dependent.
- A **real asset inventory plus a precise asset-observation operation** needs
  more than reformatting existing snapshots. In the chart task, the underlying
  snapshot did not contain the image, so the MEDIA group was empty. In video
  runs, page-sized captures rather than asset crops drove much larger visual
  inputs despite fewer screenshots.
- Do not add a learned selector yet. These are observable interface/coverage
  gaps; this experiment did not test adaptive selection or a small model.

This is a negative result for **this prototype**, not proof that every
interaction/media-oriented interface is ineffective.

## Design and controls

The plan was written before inference. Kitsune-only comparison:

- **A:** native result strings.
- **B:** existing snapshot strings reorganized as INTERACTIONS / MEDIA /
  CONTEXT, with role-derived candidate actions and original line/parent indices.
- Same clean **v0.3.0 `99a90d22c83d6e931814b3c3dadd96c08c633820`**, explicit
  lean, identical 14 exposed tools, original prompts and graders. No expect
  guidance from the previous experiment.
- Claude Code **2.1.303**, **Haiku 5.5**, medium, **claude-api bare**; private
  Firefox build 1553, fresh profile/fixture each run, variant 0.
- Six personal tasks, two crowded UI tasks (`ui-select`, `ui-rowmenu`), and
  two isolated media tasks (`mm-chart`, `mm-video`), three repetitions each:
  **30 matched blocks / 60 runs**, 15 AB and 15 BA blocks.
- All **60 externally scorable**, no retries/fallback/early stops. All runs
  functionally successful; safety/protocol distinctions remain below.
- Client-estimated cost **$0.147376**, below the $2 cap; not invoice-verified.
  Suite wall time **1,881.9 s**; summed instrumented agent elapsed **1,352.8 s**.

This is a representation bundle: ordering, grouping, role hints and line/parent
notation changed together. It is not an isolated test of any single label or
of a smaller token budget. It is also not a new asset extractor.

### What stayed unchanged

The relay calls the native server **exactly once per agent tool call**, with
unchanged arguments. No extra snapshot, image, DOM read, selector generation,
model or evaluator access. Native setup/inventory logic is unchanged. Image
payloads and all non-snapshot fields are untouched; snapshots in action and
active-tab results are formatted as well as explicit snapshot responses.

Each original snapshot line occurs once, including names, refs, values, flags,
indentation and omission markers. Sort by source line number to recover the
exact native string. Explicit parent links are added for recognized node rows;
opaque lines retain their original text/indentation rather than being parsed
as nodes. Role hints are candidates, not verified actionability claims.

**Presentation limitation:** opaque omission markers are placed in CONTEXT and
receive parent 0. Although their original position and indentation are
recoverable, their visual association with the corresponding controls is not
preserved. This falls short of the intended *easy-to-read contextual* parent
preservation; lossless reconstruction alone is not sufficient usability.

No-model real-Firefox checks on personal, crowded UI and video fixtures verified
exact reconstruction, unchanged tabs, one native request per call and successful
reuse of an existing ref after formatting. Unlike the previous rich adapter,
**formatting alone does not invalidate refs**.

## Aggregate results

| Metric | A native | B catalog |
| --- | ---: | ---: |
| Runs / scorable | 30 / 30 | 30 / 30 |
| Functional success | 30 | 30 |
| Strict v1 success | 28 | 28 |
| v2 cleanup success | 29 | 30 |
| Model requests | 279 | 273 |
| Input tokens, including cached | 2,155,787 | 2,284,383 |
| Output tokens | 52,057 | 51,673 |
| Agent/native tool calls | 346 | 348 |
| Failed tool calls | 42 | 37 |
| Instrumented elapsed, seconds | 666.841 | 686.001 |
| Client-estimated cost, USD | 0.070169 | 0.077207 |
| Native text bytes delivered to model | 219,373 | 298,547 |
| Explicit snapshot calls | 55 | 37 |
| Screenshot calls | 61 | 58 |
| Stale-ref errors | 7 | 2 |

B has fewer explicit snapshots and slightly fewer requests, but those savings
did not offset larger accumulated context. Same 27 jointly v1-successful blocks:
requests **−1.3%**, input **+8.5%**, elapsed **+4.1%**, cost **+12.4%**.

Only **13/30** paired runs were faster with B; median paired elapsed difference
was **+0.531 s**. Exploratory 5,000-resample task-cluster percentile intervals
(ten task units, repetitions kept together): requests **[−13.5%, +13.5%]**,
input **[−12.6%, +28.7%]**, elapsed **[−8.6%, +18.2%]**, cost
**[−6.4%, +29.7%]**. These are small-sample uncertainty summaries, not a
confirmatory significance claim.

### Formatting cost vs changed agent behavior

For B's *actual native responses*, formatting expanded text from **242,681 to
298,547 bytes (+23.0%)**. The cross-arm delivered-byte gap is **+36.1%**, which
also includes different subsequent tool choices and results; it is not pure
formatter overhead.

B transformed **138 snapshot strings**, with **3 unrecognized/empty snapshots
passed through unchanged**. Total formatter CPU wall time was **0.080 s** over
all 30 runs. Processing the format is not the execution-time bottleneck; the
model's context and subsequent calls matter more.

First-request input totals are essentially equal (134,439 vs 134,449); this is
not a tool-schema reduction. Prefix × request accounting decreases
1,254,162 → 1,226,399, but remaining history increases **901,625 → 1,057,984**.
That history includes visual context and agent conversation, not just formatted
text. It cannot all be attributed to the extra headings/indices.

## Results by task family

Percentages are B relative to A; groups contain different tasks/contracts and
must not be treated as independent large-sample benchmarks.

| Group | Runs per arm | Strict successes A/B | Requests | Input | Elapsed | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Personal | 18 | 16 / 16 | −5.8% | −6.4% | −4.5% | −4.9% |
| Crowded UI | 6 | 6 / 6 | −12.8% | +9.9% | +5.1% | +24.5% |
| Isolated media | 6 | 6 / 6 | +20.4% | +45.6% | +30.0% | +41.6% |

### Personal: a weak, concentrated positive signal

Personal elapsed is 457.341 → 436.922 s, input 1,350,111 → 1,264,170.
However, `pb-account-01` alone saves **134,173 input tokens and 23.139 s**, more
than the total personal improvement. Excluding it leaves input
926,779 → 975,011 (**+5.2%**) and elapsed 341.554 → 344.274 (**+0.8%**).
The personal task-cluster interval for requests is [−17.8%, +10.3%]; elapsed
[−15.2%, +7.6%]. Do not describe this as an established form-browsing advantage.

### Crowded UI: fewer requests is not automatically cheaper

- `ui-select`: 18 → 14 requests, input −37,247, elapsed −2.448 s over three
  repetitions. Two of three runs improved; this is a promising small example.
- `ui-rowmenu`: 21 → 20 requests, but input **+79,564**, elapsed **+7.248 s**.
  Repeated controls still require row context, and the whole crowded page is
  still present. There is no task-relevance filtering in the catalog.

A no-model crowded snapshot contained **132 interaction entries**. Simply
collecting controls into one global list does not make 132 choices small. A
heading/region/row-scoped view is a different, still-unmeasured intervention.

## Media findings: separation is not yet an asset interface

### 1. The chart image never reached the snapshot-derived asset list

The fixture contains a real `<img>` with alt text describing a monthly-sales
bar chart. Nevertheless, across the chart traces, the native snapshot strings
contain **no img/image/media node**. B's MEDIA section is therefore empty.
Reformatting cannot recover information omitted by the native observation.

Both arms must use screenshots to read the chart. B made extra attempts to crop
with guessed selectors (`svg, canvas, .chart` and `#mm-chart, .chart, svg`), both
of which failed. Across three repeats:

| Chart metric | A | B |
| --- | ---: | ---: |
| Model requests | 17 | 28 |
| Screenshot requests | 4 | 8 |
| Successful image results | 4 | 6 |
| Wrong puzzle submissions before eventual success | 0 | 2 |
| Elapsed seconds | 36.342 | 67.521 |

In the initial observations, the correct radio option is hidden by native repeated-item compaction:
`… 1 more similar items`. B moves this opaque marker into CONTEXT, away from
the radio list. In two B runs the agent clicked confirmation before selecting
the correct radio, and later recovered. These traces identify concrete recovery
work; they do **not** establish that marker placement caused every error or that
all media catalogs would behave this way.

**Implication:** a useful asset view needs native image identity/metadata and an
exact way to inspect that asset, not merely a MEDIA heading. Omitted control
options also need a discoverable expansion path near their group.

### 2. Fewer video screenshots produced much more image data

Video succeeded in all six runs. Screenshot traces differ materially:

| Video observation metric | A | B |
| --- | ---: | ---: |
| Screenshot requests | 52 | 46 |
| Successful images | 51 | 46 |
| Asset-sized images, 320×180 | 51 | 29 |
| Page-sized images, 1280×635 | 0 | 17 |
| Total decoded image pixels | 2,937,600 | 15,488,000 (**5.27×**) |
| Image file bytes | 693,705 | 1,004,826 |
| Total input tokens | 268,767 | 338,901 |

All A images were cropped to the video. B used full-page/viewport captures 17
times. The relay never changes an image; these are **agent-selected observation
paths** after seeing the different representation. Video request count falls
32 → 31, but input rises 26.1% and elapsed rises 4.5%.

Pixels and encoded bytes are not exact vision-token/cost attribution: provider
resizing and reuse across requests also matter. Still, the traces explain why
"fewer screenshot calls" alone is a misleading efficiency metric.

**Implication:** link an asset entry to a verified crop/observation operation.
An example future interface is `inspect(asset_ref)` with a clearly stated scope;
this is a proposal, not an implemented Kitsune API. Do not make the agent invent
a CSS selector or repeatedly capture the entire page to inspect one asset.

## Safety and integrity

Four v1 failures, all functionally successful:

- A `pb-research-01`, repeat 2: starting tab URL changed; also fails v2.
- A `pb-account-01`, repeat 2: four helper-tab closes; passes v2.
- B `pb-account-01`, repeats 1 and 2: four/three helper-tab closes; pass v2.

All gallery runs meet their task-specific safety requirements. Equal strict
success (28/30) and a one-run v2 difference are not evidence of a general safety
improvement.

Every run passed execution audit and retained the clean pinned source and
experiment implementation hashes. All 60 exposed tool catalogs have the same
hash and 14 tools. Every audited agent call corresponds to one native call;
there are no hidden enrichment calls. The 138 formatted snapshot strings in the
agent logs reconstruct successfully. Final validation ran **139 tests**, with
**5 optional tests skipped and no failures**; real-Firefox format/ref probes
also passed. This checks data preservation, not that agents find the new
representation cognitively easier.

## Product decision and next design

| Proposal | Evidence-based decision |
| --- | --- |
| Replace native snapshot globally with this catalog | **No-go for now:** no overall cost/time win, extra formatting/history weight |
| Offer an opt-in interaction view for a selected region/form | Worth a follow-up, **not validated here**; avoid interpreting one account-task gain as general evidence |
| Keep explanatory text next to its controls/row | Strong design concern from the prototype's context separation; test a locality-preserving format |
| Add a real image/video asset inventory | The chart coverage gap establishes a need if this feature is pursued; performance benefit remains untested |
| Link assets to precise cropped observation | Supported as a concrete optimization target by the recorded crop/full-page divergence; no causal A/B of that operation yet |
| Add a learned disclosure/asset selector | Not justified by these runs; fix deterministic identity/coverage/observation contracts first |

A better next prototype would be **scope-first**, not global-role-first:

```text
Region: order row / form / selected section
  Context: the nearby label and explanation
  Targets: exact refs, role/state, candidate interaction
  Assets: exact asset identity, description, crop/inspect scope
  Omitted: counts and an explicit expansion route, attached to this region
```

Keep expensive full structure available as an expansion/debug view. Avoid
repeating line-number/parent bookkeeping on every small action delta. Scope
selection belongs to the agent or an explicit caller policy; it should not be
hidden task-answer-aware filtering inside the tool.

This next prototype must be tested separately: it changes both locality and
asset coverage, unlike the representation-only intervention reported here.
There is no claim that its proposed API or efficiency has already been measured.

## Artifacts and reproduction

- Plan: `docs/experiments/2026-10-22-target-view-plan.md`.
- Private cohort: `artifacts/target-view-experiment-20261022/plan.json`,
  `summary.json`, `analysis.json`, `media-analysis.json`.
- Individual runs: `artifacts/target-view/<run-id>/`.
- No-model snapshots: `artifacts/target-view-probes-20261022/`.
- Implementation: `target_view.py`, `target_view_session.py`,
  `target_view_experiment.py`, `target_view_analysis.py` under `kitsune_benchmark/`.

```sh
# No inference: inspect the exact schedule/configuration.
uv run --locked python -m kitsune_benchmark.target_view_experiment

# No inference: real-Firefox representation/ref check.
uv run --locked python scripts/probe-target-view.py

# No inference: analyze recorded evidence; output must be a new file.
uv run --locked python -m kitsune_benchmark.target_view_analysis \
  artifacts/target-view-experiment-20261022/summary.json \
  --output /tmp/target-view-analysis-new.json
uv run --locked python scripts/analyze-target-view-media.py

# Explicitly consumes API credit: 60 new runs, fresh output directory required.
uv run --locked python -m kitsune_benchmark.target_view_experiment \
  --output artifacts/target-view-repeat-new --budget-usd 2 --execute
```

Production personal/gallery behavior remains unchanged. Limits: one model,
ten selected task/layout units, three repeats, uncontrolled cache/vision
preprocessing, synthetic local pages, no audio/drag/scroll-discovery task, and a
lossless-but-not-locality-preserving prototype. The isolated-media subgroup has
only two distinct tasks; its clustered intervals must not be generalized to
multimodal browsing as a whole.
