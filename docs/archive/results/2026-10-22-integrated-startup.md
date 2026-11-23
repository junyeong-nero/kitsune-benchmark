# Integrated Opus startup: first paid attempt stopped

This is a setup diagnostic, not a benchmark success/failure comparison.

- Approved total estimated spend cap: $30.
- Initial local allocation: $20; remaining phases reserved $10.
- One attempted Kitsune MiniWoB `click-test-2` run, model `claude-opus-5-5`.
- Estimated spend **$0.01058**; zero agent tool calls; no page load or episode start.
- Verdict **harness_error / unscorable**. The controller stopped automatically;
  no other paid attempt was made in this launch.

## Cause

The newly added MiniWoB metadata/session wrapper reused personal-session setup
and attempted `browser_navigate(about:blank)`. That setup call failed after about
15 seconds. No tools/list page was delivered; the model's init record had an
empty tool list and a pending MCP server. Its output described imaginary tool
calls/completion, but independent reward telemetry remained empty. Do not use
this attempt as evidence against Opus task capability, the full tool catalog,
or Kitsune's action-error correctness. It is an experiment-harness defect.

## Correction and free validation

Added `integrated_session.BlankSession`: verify the already-open blank tab via
inventory only, without navigating it. The agent remains responsible for opening
and selecting the actual MiniWoB task tab.

`python scripts/probe-integrated-ready.py` now checks each native server without
inference: session ready, expected UI tool exposure, opening/selecting the task
page, and visibility of START. Results: **Kitsune 27 tools / Playwright 17 tools**,
one setup inventory call each, task page visible on both. Two earlier free-probe
attempts exposed an overly strict readiness assertion and missing explicit tab
selection in the probe; those probe problems were corrected and retained in
separate logs. No model retries were hidden in those checks.

Seven focused unit tests pass. The operator explicitly declined paid resumption
and requested a stop. No corrected paid run was launched, and no integrated
runner process remains active. Further paid execution requires fresh approval.
Any resumption must preserve this failed attempt and subtract its $0.01058 from
the shared authorization. The corrected local allocation can be at most
**$19.98942**, with $10 still reserved for online/revision-control work.

Evidence:
- `artifacts/integrated-opus-20261022-local/{plan,summary}.json`
- Per-run directory referenced by that summary.
- `artifacts/integrated-preflight-20261022/ready-probe-3.stdout.json`
- Earlier free-probe logs under the same preflight folder.

Online execution/evaluation and #69 matched revision controls are not yet
implemented/executed. Current-revision raw action traces remain available for
later error-contract analysis, but this startup attempt has no agent actions.
