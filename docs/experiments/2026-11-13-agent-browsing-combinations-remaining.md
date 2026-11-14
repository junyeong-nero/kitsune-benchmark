# Authorized continuation: only the unstarted 201 combination cells

The operator explicitly selected **“남은 201회 진행”** after reviewing the
[stopped six-start phase](../results/2026-11-13-agent-browsing-combinations-expanded.md)
and its no-model native-input controls. This authorization does **not** resume
that stopped directory, retry its six cells, patch Browser Harness, change a
model, or approve another 207 starts.

## Exact scope and lineage

- Original ordered matrix: the [23-condition protocol](2026-11-13-agent-browsing-combinations-expanded.md),
  nine CLI combinations, variant/repeat 0, medium, unchanged requested models.
- Execute original positions **7–207 only**, with a new phase-local `seq` 1–201
  and retained `original_seq` 7–207. No alternative ordering or replacement slot.
- The first six outcomes, all start markers and their stop marker remain intact.
  The runner pins their exact manifest/rows/stop hashes and rechecks their start
  ledger, fixture source, model-facing catalogs, runtime pins and model policy.
- Prior pilot starts: seven, still separate. Original expanded phase: six.
  New phase ceiling: **201**. Cumulative ceiling remains **7 + 6 + 201 = 214**.
- Subscription CLI only, **API budget $0**. No automatic retry, paid fallback,
  native Agent inference, manual Chrome proxy or personal-profile automation.

The runner's explicit `expanded-remaining` scope is specific to this authorized
prefix. It is not a general arbitrary-prefix skip/filter/resume facility. A
manifest cannot increase its 201 cap via an invocation's `--limit`.

## Narrow stop-policy amendment; grades are unchanged

Continue after the already reproduced **unrequested Browser Harness input side
effect** only when the retained evidence establishes all of the following:

1. The baseline is Codex + Browser Harness in its owned private Chrome.
2. Every observed out-of-fixture URL is exactly **`chrome://settings/help`**.
3. Each such target is newly created, was never an existing/seeded target, remains
   inactive in the native current-target inventory, and first appears immediately
   after a successful normal `browser_fill` or non-shortcut `browser_press` call.
4. Completed call records, native call order and every post-call inventory align.
   The count of these observations accounts for the entire outside-navigation
   counter; a separately refused external navigation cannot hide in that count.
5. Submitted arguments contain no direct help-page request or inspection of its
   target. Closing that newly created spurious target is permitted cleanup, not
   settings inspection. Function keys/modified shortcuts, explicit navigation,
   target access or ambiguous provenance do not qualify.

Record the classification, target IDs, creation-call positions and observation
count. **Do not remove the tab from grading evidence, reset outside-navigation
counts, regrade the old failure, or turn a failed task into a pass.** Functional,
safety and overall grading stay unchanged. The exception only permits the next
cell to start after this known failure has been retained.

No model-facing hint/workaround is added. Native tools, guides, Python packages,
browser launch flags, fixture code, permission policy and time limits stay the
same. The helper's keycode behavior is **not patched**. This is a documented
continuation-policy change, not a new successful Browser Harness implementation.

All other original stop gates remain: quota/auth/provider/setup/transport errors,
missing/unscorable evidence, source/runtime/catalog drift, cleanup uncertainty,
actual external navigation, direct settings access and other boundary violations.
Scorable synthetic task failures remain failures and may proceed as already
specified for the expanded matrix. Native code is not a sandbox; argument and
provenance checks do not replace raw-log review.

## Verification and audit gates

Only the scheduler/stop-policy script and this protocol change for the new phase;
fixture, adapters, graders, models and native packages do not. Reuse the complete
161-cell/23-positive-control/seven-stdio preflight **only if** its exact fixture
source fingerprints and runtime pins still match, every catalog remains valid,
and the pinned original phase confirms the same treatment. Freeze the modified
runner/protocol separately in a clean commit. Do not claim that reused evidence
was freshly rerun under a different implementation.

Regression tests cover the precise 201-cell suffix, prior-file/start-ledger drift,
cap enforcement, known-input classification and rejection of other URLs, active
help tabs, existing-target navigation, explicit help requests, failed/misaligned
provenance and unrelated baseline exceptions. The frozen old expanded policy
still stops on the same row; the exception is limited to `expanded-remaining`.
Validation before this phase's freeze: **630 tests, 23 opt-in skips, zero
failures** (50 focused combinations tests). Read-only replay classified the
retained original failure as five observations of the one target first seen
after call 4. Original fixture fingerprints and all runtime pins still matched;
no original raw row, grade or stop marker was edited.

Execute the new phase's first **nine starts** and audit raw usage, catalogs,
functional/safety grades, arguments and cleanup before writing a hash-bound
continuation approval. That batch includes the previously unstarted agent-browser
and both Claude Code combinations, plus the beginning of the gallery condition.
Keep reviewing later batches, including every classified native side effect.
Stop rather than silently widening this exception if new behavior appears.

## Reporting

Preserve phase provenance and report the six-start phase and this 201-cell phase
separately. The original 207-cell coverage can be reconciled by `original_seq`
without retrying/dropping the failed cell. Label any planned-matrix summary as a
two-phase result with a stop-policy amendment; do not pretend it was an unbroken,
single-freeze run or pool the earlier seven pilot starts into it. Report model
panels separately and preserve unknown denominators/usage as unavailable.

All earlier measurement caveats still apply: cached input is a subset, tokens
are not cost or quota, recorded overhead subtraction is not pure model latency,
viewports/permissions/profiles differ, and one repeat does not measure variance.
No README superiority claim, release, remote push or change to product merge
holds is implied.

```sh
# Uses the unchanged, complete expanded fixture validation; no new model start.
uv run --locked python scripts/run-agent-combinations.py freeze \
  --scope expanded-remaining --limit 201 \
  --preflight artifacts/agent-combinations-expanded-preflight-v1/preflight.json \
  --out artifacts/<remaining-phase>

# First nine only, then raw-evidence review and hash-bound approval.
uv run --locked python scripts/run-agent-combinations.py run \
  --out artifacts/<remaining-phase> --limit 9
```
