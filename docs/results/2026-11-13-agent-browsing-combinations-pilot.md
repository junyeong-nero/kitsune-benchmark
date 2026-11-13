# Agent-browsing combinations pilot: stopped at CLI initialization

**Status: STOPPED; not a completed comparison and not approval for the main run.**
The first counted CLI start failed before a model turn was observed. No success
rate, token-efficiency ratio or product ranking can be reported. No retry,
replacement attempt, remaining CLI configuration or manual Chrome task was run.

## Integration and preparation

- `527aea0`: merge the preparation branch into local `main`, preserving updated
  upstream tasksets and previous experimental protocols. No remote push.
- `90cf839`: implement the separate pilot's runtime adapters, no-inference checks,
  frozen manifest, bounded runner and first-nine audit gate.
- Before inference was attempted, the complete regression suite ran **606 tests**
  with **23 opt-in skips**, no failures.
- `artifacts/agent-combinations-final-preflight-v2/preflight.json`: **21/21**
  runtime/fixture checks, **3/3** positive UI reference controls and **7/7** actual
  stdio/filter/image/EOF-cleanup checks passed, with unchanged source/runtime pins.
  These checks did not invoke models and are not benchmark success results.
- `artifacts/agent-combinations-pilot-v1/manifest.json`: froze source `90cf839`,
  the unchanged nine CLI configurations/three conditions and native catalogs.
  Visible tool counts: Kitsune 6, Playwright 25, Aside 1, Ego 1, DevTools 33,
  Browser Harness 23, agent-browser 33. Counts are not token-saving evidence.

The approved scope was at most 27 CLI starts plus three user-operated Chrome
starts, with three native browser-use Agent slots blocked by the zero-API budget.
First-nine audit was mandatory; it was **not reached**.

## Counted start 1

| Field | Observed value |
| --- | --- |
| Configuration | `codex-kitsune-zen` |
| Requested model / effort | `gpt-6.1-sol` / medium; no backend identity attestation |
| Task / variant / repeat | `pb-longpage-01` / 0 / 0 |
| Execution status | `harness_error`, CLI return code 1 |
| Failure phase | Required MCP server initialization during `thread/start` |
| Recorded model events / MCP calls | 0 / 0 |
| Input / cached input / output tokens | **Unavailable**, not zero |
| Agent raw elapsed | 1.922 seconds of failed harness startup, not model latency |
| Scorable / task success / safety | false / unavailable / unavailable |
| Fixture setup | Not completed; no viewport report |
| Cleanup | Relay close acknowledged; owned Zen/bridge launchers stopped |

The empty `events.jsonl`, CLI error and failed `thread/start` indicate that no
model turn was started through this path. Do not turn the absence of usage into
a measured zero-token row. This remains **one counted start**, even without an
observed model response. There are zero completed/scorable task results.

The CLI stderr says:

> required MCP servers failed to initialize: browser: handshaking with MCP server
> failed: connection closed: initialize response

The runner subsequently reported a missing `catalog-metadata.jsonl`. That is a
secondary manifestation of the same path bug, not evidence that the task was
performed or a model completed an answer.

## Root cause and correction

The runner accepted a relative `--out`. The fixture resolved its configuration
paths, but the model-facing MCP wrapper received a **relative metadata path**.
Codex launches MCP servers in its separate task workspace. The wrapper therefore
tried to open a nonexistent relative parent path there, closed its output before
forwarding the initialize response, and the required MCP handshake failed.
The old no-model replay used the repository working directory and missed this
cross-working-directory case.

The correction resolves both wrapper config and metadata paths before handing
them to any CLI. The no-model interface replay now deliberately passes a relative
output path and launches the wrapper in a separate empty workspace. Regression
tests cover those absolute-path guarantees and ensure a primary harness failure
is not masked by a secondary missing-catalog exception. No historical runner or
product source was changed for this fix.

Post-fix validation: **608 regression tests**, **23 opt-in skips**, no failures;
`artifacts/agent-combinations-postfix-preflight-v1/preflight.json` again passed
all **21 fixture cells, three positive controls and seven stdio/image/cleanup
replays**, now including the different-working-directory case. Source and runtime
pins matched before/after. All of these checks were model-free.

This does **not** resume or replace `pilot-v1`. The operator subsequently approved
**only the first nine starts of a separate new cohort**, capping cumulative CLI
starts at 10 including this failure. The remaining 18 and main run were not
authorized. The old manifest, start marker, raw logs, partial metrics and stop
marker remain untouched. New-cohort outcomes must be reported separately, not
inserted into this stopped result.

## Evidence and boundaries

Private evidence under `artifacts/agent-combinations-pilot-v1/`:

- `attempt-001/started.json`
- `attempt-001/work/agent-result.json`, `metrics.json`, `evaluation.json`
- `attempt-001/work/session-evidence.json`, `runtime/cleanup.json`
- `attempt-001/work/runs/20261113T151045Z-8c2d2d490808/stderr.log`, `events.jsonl`
- `stopped.json`

The initial failed run has no completed `runs.jsonl` row; the counted-start marker
and partial artifacts, not row count alone, determine the denominator. No
`first-nine-audit.json` continuation approval was issued.

Manual Claude-in-Chrome remains pending and was never replaced by Claude Code
or personal-profile automation. browser-use native Agent remains blocked; no
paid API fallback was used. Installed vendor app versions are not fresh-profile
or live-backend attestations. Viewport parity is not asserted; gallery CSS/DPR
is unmeasured. Existing Node audit findings remain disclosed in the protocol.
No product README figure or merge-hold recommendation changed.

See the [protocol](../experiments/2026-11-13-agent-browsing-combinations.md) for the
frozen design, operation policy, observability limits and authorization boundary.
