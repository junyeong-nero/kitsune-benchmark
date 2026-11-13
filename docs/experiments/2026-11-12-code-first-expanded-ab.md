# Expanded code-first A/B: frozen protocol

The operator authorized **120 Kitsune-only model attempts** and conditional merge after reviewing the
70-attempt five-way pilot. Requested decision: repeat with broader coverage once; merge only if token
savings persist without success/safety regression or a material elapsed-time increase.
No vendor-agent delegation, new paid API path, tuning after outcomes, replacement attempts or favorable reruns.

## Fixed treatment

- Current: `47dafa20a3fddc697a7d991e15d39e4b0232c10d`, 14-tool product default.
- Candidate: `f5c7a0f85aefd89e621e73665e33d33d79d50676`, 6-tool code-first default,
  branch `experiment/code-first-tools`.
- Actual published surfaces, no benchmark allowlist, no CAPS or scripting overrides. Existing approval
  settings/user-tab protection retained. The extension/input implementation is unchanged between sources.
- Same private headless Firefox construction per track/arm; private bridge, profile and fixture per attempt.
  No everyday profile, Aside or Ego browser is used in this cohort.
- Claude Code 2.1.303, `claude-opus-5-5`, medium effort, existing claude.ai subscription only. No model
  substitution or paid API fallback. Doctor checks login/configuration, not remaining quota.
- Fixture data variant 0, MiniWoB seed 42 and revision `33c3b4ddef8c6eb67c57a29663d844b1eda7e614`.
  Two independent agent repeats of those inputs, not two data variants or a confidence interval.
- Existing task wording, fixtures and graders retained. Personal/gallery use elicitation **decline**;
  harness setup calls may approve as in the existing relay, agent approval requests are declined.
  Approval acceptance and partial-write recovery are verified separately without model inference.
- Model-run limits remain 180 s for personal/MiniWoB, 240 s gallery; MiniWoB episode 120 s; MCP client
  call envelope 45 s in both arms. Do not raise a timeout after observing a slow/failing result.
- The standard full-suite runner is not used: its forced legacy-ui-23 surface would measure the wrong treatment.

## Conditions: 30 x 2 repeats x 2 arms = 120

### MiniWoB guards: 7 conditions (28 attempts)

`mw-click-test-2`, `mw-click-checkboxes`, `mw-enter-text`, `mw-choose-list`, `mw-login-user`,
`mw-use-autocomplete`, `mw-book-flight`.

These are a new cohort, never pooled with the earlier pilot. The known read-only flight-date fill
semantics remain disclosed, audited and outside the **primary** efficiency estimand.

### New personal tasks: 7 conditions (28 attempts)

`pb-current-01`, `pb-tabs-01`, `pb-research-01`, `pb-account-01`, `pb-handoff-01`, `pb-safe-01`,
`pb-longpage-01`.

Cover current-page extraction, cross-tab comparison, multi-page research, synthetic account lookup,
mail-to-calendar draft, scoped safe mutation, and long-page lookup. User-seeded tabs and protected notes
use the existing user-channel/ownership-aware grading. No real credentials or external account writes.

### New component tasks: 16 conditions (64 attempts)

Isolated layout (10): `ui-table`, `ui-infinite`, `ui-sortable`, `ui-datepicker`, `ui-autocomplete`,
`ui-shadow`, `ui-iframe`, `ui-editor`, `ui-toast`, `mm-chart`.

Crowded layout (6): `ui-table`, `ui-infinite`, `ui-sortable`, `ui-editor`, `ui-autocomplete`, `mm-chart`.

Cover paginated selection, infinite scroll, reordering, calendar, async suggestions, shadow DOM,
iframe, rich text, short-lived feedback and screenshot-based chart reading, including long/noisy pages.
Sorting may be solved by keyboard or pointer; report the actual strategy, do not claim drag coverage
from task success alone. Gallery viewport equality is by construction, not per-run measurement.
The chart tests screenshots; this is not comprehensive canvas, audio/video or all-mouse-input coverage.

### Order and pilot audit

First conditions: MiniWoB click-test-2, personal current-page, isolated infinite scroll; each gets both
arms, so the first **six model attempts** exercise all three fixture families. Then the remaining
conditions in runner order. Arm order alternates per condition and reverses on repeat 1 (ABBA/BAAB).
All runs are sequential. Pause after six to audit catalog, model, grading and actual API use before 114 more.
An ordinary scorable task failure stays in the data and does not itself stop execution.

## Predeclared conditional-merge gate

Primary set: **23 new personal/gallery conditions x 2 repeats = 46 paired cells**, not the seven previously
measured MiniWoB tasks. Every layout is a different condition; never collapse isolated/crowded rows.
Input includes cache-read/cache-creation input, as in the pilot. Output/cache/cost are reported separately.

All must hold:

1. Complete all 120 planned rows with scorable, known task grades and intact source/catalog/model evidence.
   At least **37/46 primary cells** (80%) must be jointly successful, to avoid a tiny survivor subset.
2. Primary input-token ratio (candidate/current) **<= 0.90**, both on identical jointly successful cells
   and on all primary attempts including failed effort. Never count an early failure as a token saving.
3. **No per-condition success-count decrease** across the two repeats, including MiniWoB guards.
   Thus an improvement elsewhere cannot offset losing a previously solvable condition.
4. All candidate primary safety grades pass. Manual audit finds no new safety/policy shortcuts,
   outside-fixture/host access, hidden-state manipulation, forbidden page JS, unauthorized writes,
   read-only/disabled field bypass, or replayed completed writes. Unknown evidence means hold, not pass.
   Grader success alone does not certify this; baseline violations must also be disclosed and cannot be
   silently used or removed to manufacture a valid efficiency denominator.
5. Elapsed ratio **<= 1.10** on primary joint successes and on the whole 120-attempt cohort's arm totals.
   Time means per-agent harness runtime (including its lazy relay setup), not browser-only action latency.
   Also report setup-subtracted timing where present, but do not switch the primary measure afterward.
6. Related product and harness tests pass, including real stdio/browser approval acceptance/refusal,
   partial-execution recovery/no replay, user-tab protection and input regressions. Report any tests
   skipped or not applicable; a required untested behavior blocks merge.
7. Before merge, verify the candidate and current main, required CI/checks, conflicts and intervening
   source changes. The experiment's numeric gate never merges automatically. Unresolved safety,
   implementation or evidence problems mean hold even if token totals pass.

The >=10% / nonregression / <=10% time / passing-tests rule was explicitly approved by the operator.
The coverage and per-condition definitions above make that rule conservative and executable. This is a
bounded engineering adoption decision, not statistical proof of general superiority. If any gate fails
or is unclear: **retain the branch and report; do not tune/rerun or merge to make the result pass**.

## Validation, integrity and stopping

- Validate runner plan/count/order/layout separation/gate with no-inference tests before freezing.
- Run related unit/Node/real-browser regressions and no-model fixture smoke checks. Only synthetic
  isolated profiles; no test modifies the user's installed browser/approval preferences.
- Freeze benchmark commit, protocol hash, both product SHAs, configs/fixture files and catalogs before
  inference. Before/after each attempt verify clean sources and exact native/observed catalogs; record
  every tools/list response for offline review. No legacy filtering or guide changes during execution.
- Audit all Python and direct/gateway calls: distinguish script orchestration from page evaluation,
  reported MCP errors from caught errors/wrong targets, and grader success from compliant success.
  Inspect known `readonly` controls in MiniWoB flight and gallery datepicker; do not infer compliance
  from a page-JS regex returning zero. Python has local host access: the protocol is not a sandbox.
- Personal/gallery tab inventories sample after MCP calls, not every inner Python operation. Inspect
  scripts/operation logs for intermediate actions; disclose the instrumentation limit rather than
  promising exhaustive per-action safety telemetry.
- Quota, execution/setup failure, missing usage, source/catalog drift or unscorable result: stop, preserve
  evidence and report. No automatic quota retry, setup replacement, paid fallback or new cohort.
  A limited initial run followed by untouched remaining cells is continuation of this one cohort.
- Do not publish raw session logs, trial tokens, environment secrets or real page contents. Local raw
  artifacts and checksums support the result report; only reviewed summaries enter version control.

## Commands

After runner/regression validation and a clean benchmark commit:

```sh
uv run --locked python scripts/run-code-first-expanded-ab.py plan
uv run --locked python -m kitsune_benchmark doctor --harness claude --json
uv run --locked python scripts/run-code-first-expanded-ab.py preflight \
  --out artifacts/code-first-expanded-ab-v1
uv run --locked python scripts/run-code-first-expanded-ab.py run \
  --out artifacts/code-first-expanded-ab-v1 --limit 6
# Audit six; continue only if source/protocol/setup evidence is valid, no outcome-based tuning:
uv run --locked python scripts/run-code-first-expanded-ab.py run \
  --out artifacts/code-first-expanded-ab-v1
uv run --locked python scripts/run-code-first-expanded-ab.py analyze \
  --out artifacts/code-first-expanded-ab-v1
```
