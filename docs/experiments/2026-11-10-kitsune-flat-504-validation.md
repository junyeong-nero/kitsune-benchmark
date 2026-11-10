# #504 preregistration validation and acceptance scope

2026-11-10. This is a **methods-only milestone**, not completion of Kitsune #504,
new runner validation or approval to spend quota. Protocol:
[flat-504-v1](2026-11-10-kitsune-flat-504-protocol.md).

## Checks performed

| Check | Result | Scope |
| --- | --- | --- |
| `uv run --locked python -m unittest discover -s tests -p test_flat_protocol.py -v` | **7 passed** | Frozen input coverage, all personal units, C/D configuration, four-period Williams positions/carryover, deterministic schedule, no process/network execution or approval, rejected drift and outside paths |
| `uv run --locked python -m unittest discover -s tests -q` | **419 tests / 18 skips / zero failures/errors**, 280.254 s | Python 3.13.5; expected negative CLI argument messages are test output, not failed tests |
| `uv run --locked python -m kitsune_benchmark.flat_protocol` | **31 units, 29 primary, 496 runs, 124/arm** | model_invoked=false, execution_supported=false, execution_approved=false; execution prerequisites remain explicit |
| Frozen inputs | **15 hashes matched** | No task, fixture, grader, existing benchmark config or dependency-lock changes |
| `git diff --check` | Passed | No whitespace errors |
| Browser/model/default/merge/release | **Not performed** | Skips are not native-browser passes; this PR has no execution entry point |

The schedule's canonical SHA-256 is
`3108c47786bc8b992417ac3459fa080da31eb016ec12afe082c5e4588bab5c93`.
The planner also prints canonical protocol-JSON and raw document hashes; record
those with the clean commit in the later execution lock. It deliberately has no
`--execute` option and returns false approval even if a caller supplies an approval
boolean. That is a non-execution property, not a runtime sandbox or authentication
implementation.

Baseline prerequisite PR #144 (`cadeae3`) remains OPEN. Its actual native evidence
is in [the preflight report](../results/2026-11-10-native-preflight.md). It is not
silently treated as a merged main or as candidate conformance. Kitsune PR #506
(`9ae8549`) remains a design artifact; this work does not alter that repository.

## Design-stage self-review

- **Selection bias:** keep all 28 personal units, including simple and known awkward
  tasks; reuse the full-native units without weakening their fixtures/graders.
  One canonical variant and four stochastic repeats have explicit generalization
  limits. This is not a claim of statistical power or comprehensive capability parity.
- **Order:** the test verifies positions and all 12 directed adjacent arm pairs
  for each unit, not just alternating the first arm. Sequential fresh runs avoid
  cross-arm shared load; provider caching/weight drift remain limitations.
- **Causal scope:** compare C/D as offering composition, not only successful scripts;
  A/B remain wider product references. All guide/code/discovery overhead is charged.
- **Authority versus inspection:** the old relay cannot inspect arbitrary code or
  establish host/egress confinement. Before paid/quota runs, external fixtures-only
  fences must also cover legacy evaluation/file paths; private HOME and text review
  alone are insufficient. No attempt to solve this by widening grants or using real
  personal accounts is permitted.
- **Evidence quality:** gallery state is page-JS-reported and kept outside positive
  primary efficiency decisions; safety/integrity incidents still stop the cohort.
  Authoritative operation receipts and application/user-channel state are required.
- **No cheap-failure win:** per-unit success counts, absolute success, joint coverage,
  all-attempt spending per success, simple-work and wall-time guards precede a go.
  Undefined ratios/missing measurements are not zero; disagreement across repeats
  or unsupported uncertainty bounds is inconclusive.
- **Measurement holes:** the existing audit has no exact code-token split. Its
  measurement method must be resolved and disclosed before model approval; the
  full code-bearing response is not mislabelled as code-only tokens. Opaque legacy
  evaluation internals are not guessed from source statements.
- **Billing honesty:** $45–$90 is a historical list-price planning range, not a bill
  or hard cap. OAuth does not prove zero incremental charge if extra usage is enabled.
  Quota/extra usage and the $100/12 h review stops require explicit approval.
- **No fictional readiness:** a candidate commit, instrumented executor/analyzer,
  host/dependency lock, conformance and user approval do not yet exist. Their pins
  may be filled later without changing methods; substantive changes need a visible
  pre-execution amendment. Known blockers cannot be papered over by a manifest flag.

## Kitsune #504 acceptance tracking

| Issue acceptance | Current status |
| --- | --- |
| Protocol states arms/differences, units, order/repeats, budgets/stops and decision rules before execution | **Methods milestone delivered**; JSON/doc + tested offline schedule. Final execution pins/measurement closure/approval remain required. |
| No-model policy/lifecycle checks; #136/#137 baseline defects resolved or bounded | Baseline fixes/evidence in #144; **new candidate suite pending #500–#502** |
| Instrumentation below script boundary | Requirement specified; **implementation/evidence pending** |
| Matched repeated runs/private reproducible artifacts/code integrity review | **Not run; no model approval exists** |
| Reproducible report separates simplification/composition and supported/rejected/inconclusive findings | Decision/report contract specified; **report pending** |
| Explicit default go/no-go and JS parity gate | **Not reached**; no default, merge, release or JS-support approval implied |

Next: #500 authority/isolation feasibility, then #501 runner and #502 opt-in candidate;
finish the benchmark executor/telemetry and private no-model preflight before the
user is asked to approve the actual model campaign. If any required boundary or
measurement cannot be established, stop at that gate and ask rather than run.
