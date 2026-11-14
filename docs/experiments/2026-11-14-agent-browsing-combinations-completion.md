# Authorized completion: observer repair and only the unstarted 169 cells

The operator selected **“관측 수정 후 169회”** and **“검증 후 profile 압축”**.
This is a new phase, not a resume/retry of either stopped expanded phase. API
budget remains **$0**, subscription CLI only. No native product patch, model
hint, alternate model, paid fallback, manual-Chrome proxy or native Agent run.

## Immutable scope and historical record

The original [23-condition matrix](2026-11-13-agent-browsing-combinations-expanded.md)
contains 207 cells. The first phase stopped after 6; the
[201-cell continuation](2026-11-13-agent-browsing-combinations-remaining.md)
stopped after 32. Together: **38 attempted/scorable/known-usage cells, 35 overall
passes and 3 failures**. All 38 achieved functional success. Seven historical
pilot starts remain separate, including startup failures with unavailable usage.

Execute **original positions 39–207 only**: 169 new starts, with phase-local
`seq` 1–169 and retained `original_seq`. This includes 131 Codex and 38 Claude Code
cells; no Browser Harness cell is excluded. Requested models remain
`gpt-6.1-sol` and `claude-opus-5-5`, medium, variant 0/repeat 0. Cumulative ceiling:
**7 + 6 + 32 + 169 = 214**. A start counts before provisioning. No retry,
replacement or slot reassignment; an invocation cannot enlarge the cap.

The new `expanded-completion` scope pins both parent manifests, rows, stops and
start ledgers, their raw non-profile evidence, and separate historical pilot
ledgers. It also pins the continuation's preserved audit correction, original
premature approval, duplicate-write finding and transient-URL finding. Parent
runtime pins, catalogs, prompts/policy and limits must match. The only changed
validation-source fingerprint may be `agent_combinations_session.py`; runner,
protocol and tests change separately. This is not a general arbitrary-prefix
resume API. Both older execution directories remain stopped.

### Findings that must not disappear

- Continuation seq26/original32 replayed an already-completed local memo write.
  Two completed form-submit transitions support this finding; the earlier rejected
  fractional-coordinate call did not perform a write. Its failed grade is not
  solely the native help-tab issue.
- Continuation seq32/original38 had two transient empty URL samples after local
  new-tab calls, plus ten observations of the known inactive help tab. These were
  twelve **observations**, not twelve requested external navigations. Its raw
  safety/overall failure and stop remain unchanged.
- The10–30 audit was prematurely approved before its full response/image review.
  Starts31–32 happened before that complete review. The original approval and its
  correction are retained; the later full post-stop review does not retroactively
  authorize those starts or further execution. This procedural error motivates
  the stricter every-batch gate below.
- Kitsune `browser_tabs action=request` is supported. Recorded scripted handoff
  declines were not unsupported-action errors and were not permission grants.

## Observer repair, not an empty-string allowlist

Only Browser Harness's immediately preceding **successful explicit local
`browser_new_tab`** may establish pending-navigation provenance. The returned
stable target ID must be fresh across all earlier snapshots and must identify
exactly the one empty-URL target in an otherwise unchanged target set. Missing,
failed, reused/seeded, implicit-script, foreign or `about:blank` requests do not
qualify. Never replace `""` with `about:blank` or accept an unresolved URL.

For an eligible pending target, resample only native `browser_list_tabs` and
`browser_current_tab`: at most 20 polls, 50ms intervals, within a **one-second
settlement window**. Retain the request/response receipt, initial empty sample,
every native sample, snapshot position, status and measured time. Accept only
resolution to the exact requested local URL within the window. Unexpected URLs,
selection/other-target changes, malformed observations and transport errors fail
closed. A persistent empty URL stays empty and contributes an outside observation.
An existing inactive exact help target may remain present; it is not erased.

Native RPC deadlines, the CLI per-call limits and total attempt deadlines are
unchanged. A stalled native inventory RPC can outlast the one-second polling
window under its existing transport timeout, but a late reply **cannot qualify**
as settled. There is no post-result deadline extension. Inventory/polling time is
retained in `post_call_inventory_sec`; adjusted elapsed is still descriptive,
not pure model latency.

There remains exactly one finalized grading snapshot per submitted native call.
Raw pending samples are additional observer evidence, not fabricated agent calls.
The old narrow help-only stop exception is retained unchanged: all outside
observations must be attributable to fresh inactive exact `chrome://settings/help`
targets first appearing after successful ordinary input, with aligned calls and
no direct settings/target access. It still leaves safety/overall grades failed.
Unknown/foreign URLs, unresolved empties, direct settings requests and ambiguous
provenance are not added to this exception.

Native products/packages, tool schemas (including Kitsune's actual six-tool
interface), launch flags, model prompts/models, fixtures, graders and permissions
are unchanged. Browser-side code is not a sandbox. The correction only applies
to this newly validated/frozen phase; it does not regrade historical results.

## New validation and clean freeze

An additional no-model control successfully created a local tab, then failed
when closing the currently attached new tab: native `browser_current_tab`
returned `cdp_disconnected`. No empty-URL stabilization branch ran in that
control. The pinned native close helper does not reattach to another target.
The failed control and confirmed owned cleanup are retained; no native patch,
implicit reselection or model hint is added. A separate three-new-tab-only
control passed, but did not reproduce a transient empty URL. Controlled offline
regressions cover that state. This is not a claim that all mutating native calls
are safe: the same active-target-close/inventory error during a model attempt
remains an operational stop. A separate diagnostic report-write collision was
also retained and corrected in the diagnostic utility, not the benchmark.

Rerun the entire **161 fixture/runtime cells, 23 Playwright positive UI controls
and seven actual stdio/filter/image/EOF-cleanup replays** with no model calls.
Earlier preflight results cannot stand in for this observer-source revision.
Run offline regression and full-suite tests. Confirm source/runtime/catalog
stability, subscription-only authentication and complete owned cleanup. Freeze
only a clean benchmark commit and the unchanged clean Kitsune revision.

Pre-freeze validation completed successfully: **161/23/7**, unchanged runtime
pins/catalogs and subscription-only auth, plus **653 full-suite tests, 23 opt-in
skips, zero failures** (73 focused combinations tests). The preflight report is
`artifacts/agent-combinations-completion-preflight-v1/preflight.json`, SHA256
`54dcaf0fba6b3dffb09ad6c17485d00f858146b3f1964e4da9d737a0adce36e5`.
Only the disclosed observer validation-source fingerprint differs from the
stopped parent. Per-cell cleanup checks also run before any next start without
masking a primary setup/execution failure or dropping its recorded row.

The operator-authorization file was recorded during preparation with readiness
false and no new inference yet; keep it as a historical authorization snapshot.
The new manifest's `cli_ready` is the later execution gate. Freeze accepts only
that authorization file in the otherwise unused new output directory.

## Maximum nine starts, complete review before every next batch

Every `expanded-completion` invocation must explicitly request **1–9 starts**.
A run with missing or excessive `--limit` is not a way around this limit. Before
another batch, require contiguous approved `batch-audit-NNN-MMM.json` records for
all completed rows, each covering at most nine starts. Bind each approval to:

- The frozen manifest and cumulative row-prefix SHA256.
- Every batch start marker, raw CLI events/responses/images, result, grade,
  timing/session evidence, catalog records, runtime ownership and cleanup files.
- The preceding audit's SHA256, so a later correction invalidates a stale chain.
- Explicit completed review of **every argument, response, structured content,
  delivered image, failed call/recovery, usage/auth record, catalog/model record,
  grade/action-policy result, observer/timing record and cleanup**.

Automated integrity checks alone cannot establish that a person/assistant read
the full record. Do not set the full-review flags until paginated text and every
image have actually been inspected. Truncated terminal output is not complete
review. Keep draft/check reports distinct from approved batch-audit filenames.
Record call counts including finished failed calls, not only successful calls.
Audit the final batch too, even though no later start remains.

Synthetic wrong answers/action-policy failures remain measured failures, not
replacement opportunities. Operational/auth/quota/provider/setup/transport,
evidence/usage/timing, cleanup, source/runtime/catalog and unqualified boundary
failures stop the phase before another counted start. Preserve all markers and
failed attempts. Do not silently widen the exception or rewrite an approval.

## Storage and reporting

Check free disk before every counted start; stop below **2 GiB**. The operator
approved verified archives of only stopped, benchmark-owned profiles. The first
storage pass replaced 336 eligible profiles and independently verified all 69,001
regular files and 1,068 literal symlinks. About 13 GiB was available afterward,
not the 14 GiB target. Four older diagnostic profiles without the required cleanup
record stayed untouched. After the new preflight and diagnostics, another 123
eligible profiles were archived: **459 total**, 89,786 regular files and 1,464
literal symlinks reverified, with about 13.19 GiB free at that audit. Archive
hashes/manifests/pointers and original
ownership/cleanup records remain; raw calls, grades, images and markers are not
removed. Seq26's archived History bytes still match their prior SHA256.

Only equally verified, completed preflight/batch profiles may be archived later.
Do not touch personal profiles, restart an old browser, replay writes or infer
that ordinary tar extraction automatically restores custom xattr/nanosecond PAX
metadata. See the archive store's verification report and retrieval instructions.

Report the original 6-start, remaining 32-start and new 169-start phases distinctly,
then reconcile 207-cell coverage by original position. Keep the seven pilots and
the two model panels separate. Cached input is a subset of input; Claude cache
creation is included in normalized input. Tokens/list prices are not subscription
charges or quota. Requested/reported names are not independent backend identity
attestations. One repeat, unequal engines/permissions/viewports/context isolation,
sampled inventories and descriptive overhead subtraction limit comparisons.
No product merge, remote push, release, README superiority claim or lifting of
existing product merge holds is authorized.

```sh
# All no-model validation must finish successfully first.
uv run --locked python scripts/preflight-agent-combinations.py --scope expanded \
  --out artifacts/agent-combinations-completion-preflight-v1

# After full tests and a clean local commit; retains the prior authorization file.
uv run --locked python scripts/run-agent-combinations.py freeze \
  --scope expanded-completion --limit 169 \
  --preflight artifacts/agent-combinations-completion-preflight-v1/preflight.json \
  --out artifacts/agent-combinations-completion-v1

# At most nine, followed by complete raw review and hash-bound approval.
uv run --locked python scripts/run-agent-combinations.py run --limit 9 \
  --out artifacts/agent-combinations-completion-v1
```
