# Kitsune main `883d80e`: Claude lite baseline — incomplete at subscription limit

[Results index](README.md) · [Versions](kitsune-versions.md) ·
[Frozen protocol](../experiments/2026-11-12-claude-caps-and-main.md) ·
[Separate completed CAPS experiment](2026-11-12-claude-scripting-caps-ab.md)

**This is a partial personal-track baseline, not a completed lite/release score.**

- Of **306 planned agent runs**, **98 were attempted**: 96 finished with successful, safety-passing grades;
  two stopped with `usage_limit_reached` and remain unscorable harness errors. **208 were not attempted.**
- Personal v0 completed for both targets. Personal v1 stopped on the subscription limit; no gallery, coexistence
  or external track was launched. No retry, API fallback or automatic resumption.
- On **47 completed joint-success personal units**, current Kitsune/Playwright input is **0.831**, calls **0.884**,
  elapsed **0.877**. This scope does not include all 56 personal units, let alone the full suite.
- Against `c0f80a2` on exactly those same 47 units, Kitsune's own input is **+2.6%** and calls **+1.7%**: broadly
  similar observations, not evidence of a statistically established regression.
- Against v0.7.2 on **45 four-way-success units with the changed `pb-tabs-03` excluded**, Kitsune's input is
  **−15.3%** and calls **−18.6%**. This is a historical subset comparison, not a concurrent randomized version A/B.

## Setup

- **Kitsune:** `883d80eee2c85f81410352ea8f86b81e11a2b682`, `v0.7.3-35-g883d80e`, clean pinned checkout
  `artifacts/vendor/kitsune-main-883d80e`. This is main **without** the CAPS patch. Scripting OFF, default core.
- **Benchmark:** `465e8d44e34525c0dcf9e856b0b541db7ef81b28`, `taskset-v3.5-27-g465e8d4`, clean.
  Production task/harness/grader files are unchanged since the `c0f80a2` cohort (`53d6a9b`). Added runners/reports
  and the preflight test-only correction do not alter the measured tasks or execution path.
- **Client/model:** Claude Code `2.1.303`, `claude-opus-5-5`, medium, claude.ai subscription. No provider API-key
  inference, budget or fallback. Playwright MCP `0.0.83`; both targets use the historical **23-tool UI allowlist**.
- **Plan:** standard lite, personal v0/v1, both gallery layouts v0, all coexistence conditions and external.
  One attempt; targets parallel except paired coexistence; elicitation `decline`; `--retry-setup-failures 0`.
  Each run has a fresh private fixture/profile; no real accounts. No normal user profile.
- **When:** 2026-11-12 01:49:46–02:11 KST. The original manifest and every failed attempt are retained.

### Preflight and validation

Claude login/version diagnostics and 93 runner/harness tests passed. The native personal modules initially had
one import-path error; using discovery exposed 22 additional fixture subtest failures from obsolete MCP seeding
of a foreign tab. The production suite already uses user-channel seeding. Only `tests/test_personal_fixtures.py`
was corrected to match that path and assert zero agent-owned starting tabs; no protection was disabled and no
product/harness/grader was modified. Combined native/personal tests then passed **61/61** before model execution.
The initial failures are disclosed in the protocol, not counted as model runs or silently discarded benchmark attempts.

All 98 pair manifests confirm clean pinned source, correct model/effort, no scripting/CAPS override, no API budget,
and the standard allowlist. All 98 Claude init inventories contain 23 browser tools and no Python execution tool.
Personal content viewport equality is asserted in 98/98. JSONL audit violations: 0. The two harness errors are
both the subscription limit; all 96 scorable attempts pass task and safety grades, with no graded task failures.

## Coverage and stop evidence

| Entry | Playwright success / attempted | Kitsune success / attempted | Status |
| --- | ---: | ---: | --- |
| Personal v0 | 28/28 | 28/28 | Complete |
| Personal v1 | 21/22 | 19/20 | Both stopped on subscription limit |
| Gallery, coexistence, external | 0 attempted | 0 attempted | Not started |
| **Total** | **49/50** | **47/48** | **96 successes, 2 unscorable errors** |

Failed runs, not ordinary task failures:

- Playwright `pb-safe-02` v1: `artifacts/personal/20261111T171114Z-3e73ad5055/runs/20261111T171116Z-c449308abd0c`.
- Kitsune `pb-handoff-04` v1: `artifacts/personal/20261111T171113Z-772f68707a/runs/20261111T171118Z-0fd6bad5d87d`.

Both have `execution_status=harness_error`, `api_error=usage_limit_reached`, and final text:

> You've hit your session limit · resets 4:20am (Asia/Seoul)

The driver waited for already-active peers to settle, then exited 3 without starting later tracks. The displayed
reset is **2026-11-12 04:20 KST**, not a guarantee of future capacity. No scheduler or automatic resumption was set.
The baseline task remains incomplete pending a deliberate continuation that preserves these failed attempts.

## Like-for-like version comparisons (personal only)

A unit is `(personal-vN, task_id)`. Each row below uses **one identical set where both targets succeeded in both
cohorts**, not each cohort's entire successful subset. Current-vs-`c0f80a2`: 28 v0 + 19 v1 = 47 units.
Current-vs-v0.7.2: 27 v0 + 18 v1 = 45 units, excluding both `pb-tabs-03` variants, whose grading changed from
agent-current tab to user-shown tab in taskset-v3.3. The other personal task/page/grader definitions are unchanged;
setup retry/error reporting evolved, but no setup retry occurred here.

| Historical cohort | Matched units | K/PW input then → now | Kitsune own input now/then | Kitsune own calls now/then | PW own input now/then |
| --- | ---: | --- | ---: | ---: | ---: |
| main `c0f80a2` | 47 | 0.817 → 0.831 | **1.026** | **1.017** | 1.009 |
| v0.7.2 | 45 | 0.990 → 0.831 | **0.847** | **0.814** | 1.009 |

Audit-friendly totals on those matched sets:

| Matched comparison | Kitsune input then → now | PW input then → now | Kitsune calls then → now | Kitsune requests then → now |
| --- | --- | --- | --- | --- |
| `c0f80a2`, 47 units | 2,904,270 → 2,980,686 | 3,555,966 → 3,587,305 | 351 → 357 | 263 → 270 |
| v0.7.2, 45 units | 3,364,376 → 2,849,774 | 3,399,508 → 3,431,481 | 419 → 341 | 297 → 258 |

Input includes cache reads and writes. The current 47-unit K/PW output ratio is 1.008. Parallel target elapsed
includes shared host load and model/network latency; neither it nor these historical deltas isolates a code effect.
One attempt and incomplete task coverage prevent an overall release/default recommendation. In particular, no
claim about gallery efficiency or coexistence input/view protection can be made from this partial cohort.

## Reproduce and artifacts

```sh
uv run --locked python scripts/analyze-release.py artifacts/opus-subscription-main-883d80e \
  --compare artifacts/opus-subscription-main-c0f80a2 \
  --json artifacts/opus-subscription-main-883d80e/review-c0f80a2.json
```

The generic review intersects available unit keys before applying each cohort's success filter. Its comparison
section therefore has different success denominators in this incomplete case. The matched table above additionally
requires four successful/scorable, normally completed runs per key before summing; do not substitute the generic
50-shared-key comparison or a full historical-suite ratio for these 47/45-unit numbers.

Suite artifacts: `artifacts/opus-subscription-main-883d80e/{suite-manifest.json,suite-log.jsonl,suite-summary.json}`,
per-entry output/error files, and `review-c0f80a2.json`. Each suite-log entry points to the immutable per-track pair
summaries/raw events under `artifacts/personal/`. Historical suites are
`artifacts/opus-subscription-main-c0f80a2` and `artifacts/opus-subscription-v0.7.2`; no historical rows were rewritten.
The complete 80-run CAPS experiment is separate. No main merge, push, issue posting, default-on change or release.
