# Agent-browsing combinations: authorized 23-condition benchmark

**Status at freeze: model-free validation passed; no expanded model start yet.**
The operator selected **the expanded 23 conditions, each once, across the existing
nine CLI combinations**: at most **207 new starts**. This is a new authorization
and cohort, not a continuation of either stopped pilot. Their seven counted
starts remain separate; the cumulative ceiling including those starts is 214.
No retry or replacement slot is added to the new 207.

## Fixed scope

Registry: `kitsune_benchmark/agent_combinations_expanded.py`.

- Seven Codex `gpt-6.1-sol` / medium combinations: Kitsune six-tool + private Zen,
  Microsoft Playwright MCP + private Chrome, Aside native REPL, EgoLite script
  wrapper, Chrome DevTools MCP + private Chrome, Browser Harness MCP + private
  Chrome, agent-browser MCP + private Chrome.
- Two Claude Code `claude-opus-5-5` / medium combinations: Kitsune/Zen and
  Playwright/Chrome. Selected model strings are requests, not independent backend
  identity attestations. Subscription logins only; **API budget is $0**.
- Variant **0**, repeat **0**, one fresh fixture/context per cell. No inherited
  conversation, prior task answer, historical result or pilot row is reused.
- No automated personal Chrome, native sidepanel proxy, browser-use native Agent,
  paid gateway, alternate model or manual-track start is included.

| Track | Conditions |
| --- | --- |
| Personal (7) | `pb-current-01`, `pb-tabs-01`, `pb-research-01`, `pb-account-01`, `pb-handoff-01`, `pb-safe-01`, `pb-longpage-01` |
| Isolated gallery (10) | `ui-table`, `ui-infinite`, `ui-sortable`, `ui-datepicker`, `ui-autocomplete`, `ui-shadow`, `ui-iframe`, `ui-editor`, `ui-toast`, `mm-chart` |
| Crowded gallery (6) | `ui-table`, `ui-infinite`, `ui-sortable`, `ui-editor`, `ui-autocomplete`, `mm-chart` |

The schedule begins with `pb-current-01`, then `ui-infinite@isolated`, then the
remaining conditions in registry order. For each condition, rotate the seven
Codex and two Claude combinations within their separate groups; alternate which
model group goes first. Run sequentially, not concurrently. Exactly **161 Codex +
46 Claude Code starts** are planned; these are task starts, not provider-request
counts or quota estimates.

## Readiness and the prior Browser Harness blocker

The previous start-6 failure did not preserve the mismatching final inventory;
its exact historical cause cannot be retrospectively established. The pinned
Browser Harness `new_tab(nonblank)` may reuse a target still reported as blank
while navigation is in flight. A deterministic delayed/stale-target test makes
the old setup fail with the same tab-mismatch exception.

The new setup explicitly creates a **fresh blank target**, rejects reused IDs,
then navigates and waits up to **five seconds total** for that exact target's URL
and load completion. Bootstrap navigation gets the same synchronization. Native
tool schemas are unchanged; these operations are harness-only. Setup RPC results,
last native inventories and inventories immediately before validation are now
retained. The final required URLs/tab contract and graders are not relaxed.
The deterministic regression plus real no-model fixture/stdio checks must pass;
that is not a claim that a new model run repaired the old result.

Before freezing, validate **161 runtime/fixture cells** (23 × seven runtime
surfaces), including real image transport and noncompletion failures, plus **23
positive UI reference controls through private Playwright**. Reference answers
are used only in no-model controls, never in later model prompts/catalogs.
Each runtime also replays its actual stdio/filter/image/EOF-close interface from
a separate empty working directory, with pre/post catalog probes matching the
runner sequence. Keep all failed diagnostic evidence in separate directories.

Freeze only clean benchmark and pinned Kitsune source checkouts. Record source,
lock, executable, installed-app/guide and native catalog fingerprints before and
after validation. Verify them before/after every model attempt. The old pilot
plan remains bounded to its old scope; only an explicit expanded manifest may
permit 207 starts. A smaller manifest authorization cap is also enforced.

Validated evidence: `artifacts/agent-combinations-expanded-preflight-v1/preflight.json`
contains **161 passing cells, 23 positive controls and seven stdio replays**, with
unchanged source/runtime fingerprints. All **621 regression tests** completed
with **23 opt-in skips and no failures**. The earlier partial Playwright control
probe is retained: its source-tab opener left the memo page in the background,
so the no-model reference now explicitly foregrounds that page before input.
All 23 controls then passed in both the Playwright-only and complete preflights.
No model start or grader change was used to diagnose that control failure.

## Policy, limits and outcomes

Use the existing native browser APIs and their unmodified schemas/guides.
Browser-side code may read **rendered DOM text, geometry and visible state**, or
perform ordinary UI input. Do not inspect hidden application/source/grader state,
cookies/storage, host files, network/response bodies or unrelated tabs; do not
make direct HTTP shortcuts, inject scripts, bypass readonly/disabled inputs,
change permissions/settings, replay completed writes or invoke another model.
Starting tabs and URLs must be preserved. Native Python/JS/CDP is **not a sandbox**.

- Whole-attempt limits: personal **180 s**, gallery **240 s**.
- MCP startup: **60 s**. Per-call: Kitsune/Playwright **45 s**, others **130 s**;
  native runtime deadlines still apply. No timeout relaxation after results.
- Stop before another start if less than **2 GiB** free disk remains; do not
  delete historical or failed-run evidence to make space automatically.
- Count starts before provisioning; preserve partial starts even when no model
  turn or usage appears. Never rerun a counted cell or splice another cohort.
- First **nine** starts must be reviewed before continuation; the approval is
  bound to their persisted-row SHA256. The full 207 are authorized only after
  readiness and this evidence gate, not by deleting a stop marker.

**For this expanded benchmark, a scorable wrong answer or synthetic task-safety
violation is a measured task failure and does not by itself stop other cells.**
Examples are changing a protected synthetic note, pressing a fake forbidden
submission button, or breaking the starting-tab contract *within the owned local
fixture*. The model still receives the same prohibitions, the unchanged grader
still fails the task, and all violations remain reported. This differs from the
diagnostic pilot's whole-cohort safety-failure stop; it is declared before any
expanded inference, not chosen after an unfavorable outcome.

Stop the cohort on actual out-of-fixture navigation, harness/builtin-tool boundary
violations, quota/auth/provider errors, setup/transport failure, unscorable or
missing required evidence, cleanup uncertainty, source/runtime/catalog drift, or
an invalid timing/usage record. Timeouts remain unscorable under the unchanged
fixture contract and stop this cohort; do not convert them into favorable graded
rows. There is no automatic model retry, paid fallback or silent baseline drop.

## Measurement and limitations

Keep raw requested-model/harness status, externally graded functional and safety
outcomes, input/cache/output tokens, raw elapsed, measured relay setup and
post-call inventory overhead. Include failures, recoveries and known in-flight
usage; missing is unavailable, never zero. Input already includes cache reads.
Tokens are not subscription cost or quota remaining. Raw elapsed excludes
external browser provisioning, pre-catalog probes and final runtime cleanup;
subtracting recorded setup/inventory is descriptive, not pure model latency.

Report the Codex and Claude cohorts separately. Any paired ratio requires the
same task/variant/repeat and known usage. Report explicit attempted/completed/
scorable/usage denominators; a stopped subset is not a complete 23-task result.
One repeat per condition does not estimate run-to-run variance. Keep per-task
results alongside aggregates; do not present an overall winner across tokenizers.

Zen/Chrome have owned fresh profiles. Aside/Ego use fresh native contexts in
installed apps, not equivalent fresh-profile isolation. Installed bundle versions
are not independent live-process/backend attestations. CSS viewport/DPR differ
(and can change during a run); personal-page beacons record them, gallery CSS/DPR
remain unavailable. No viewport or permission parity is asserted. Browser and UI
differences prevent a pure MCP-transport causal claim.

The Browser Harness image bridge preserves its native receipt and attaches only
fresh PNGs in the attempt's image directory. A path is not a delivered image.
First-nine text-task results alone do not establish multimodal performance.
Retain native/output size errors and recovery cost, including Kitsune's bounded
Python output, without dropping unfavorable rows.

Known inherited Node audit findings remain disclosed in the
[pilot protocol](2026-11-13-agent-browsing-combinations.md); no claim of a clean
security audit, product release, README figure replacement or lifted product
merge hold is made by this authorization.

## Commands

```sh
# Offline plan; never invokes a browser/model.
uv run --locked python -m kitsune_benchmark.agent_combinations_expanded

# New private evidence directory; no model calls.
uv run --locked python scripts/preflight-agent-combinations.py \
  --scope expanded --out artifacts/<expanded-preflight>

# Only after readiness and a clean commit.
uv run --locked python scripts/run-agent-combinations.py freeze --scope expanded \
  --limit 207 --preflight artifacts/<expanded-preflight>/preflight.json \
  --out artifacts/<expanded-cohort>
uv run --locked python scripts/run-agent-combinations.py run \
  --out artifacts/<expanded-cohort> --limit 207
# Stops after nine; audit raw evidence before issuing continuation approval.
```

All work and reports stay in `kitsune-benchmark`. Prior pilots and historical
cohorts remain immutable and separate. No remote push is implied.
