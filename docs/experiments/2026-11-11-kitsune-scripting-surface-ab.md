# Protocol: Kitsune legacy tool list vs `KITSUNE_SCRIPTING=1` (kitsune#514/#515)

Frozen before the first counted run. Runner: `scripts/run-scripting-ab.py`.

## Question

On MiniWoB++ the one-tool surfaces of Aside and ego(lite) used 30–42% less input than Kitsune with a similar number of
model requests (37–42). Their first request was 4.8–5.1k tokens against Kitsune's 9.5k, so the gap is the per-request
prefix, mostly tool definitions ([2026-11-11 c0f80a2 cohort](../results/2026-11-11-main-c0f80a2.md) and the same-day
Aside/ego exhibition). Does Kitsune's scripting surface (14 tools including `browser_run_python`, 42% fewer
definition characters) lower input tokens, without losing success?

## Arms

Same clean Kitsune checkout (`362c1fd`, `v0.7.3-29`: `c0f80a2` plus test-only changes for #497; `src/` and
`extension/` identical), Kitsune only, no benchmark allowlist (each arm sees what Kitsune publishes):

| Arm | Environment | Published tools |
| --- | --- | ---: |
| `legacy` | default | 27 |
| `scripting` | `KITSUNE_SCRIPTING=1` | 14 |

`claude-opus-5-5`, medium, Claude Code `2.1.303` on the subscription. Elicitation `decline`.

## Units

20 cells, 2 repeats per arm, ABBA across repeats with the first arm alternating by cell, repeat-major: 80 runs.

- MiniWoB++ (`external-v1`, seed 42): the 7 tasks.
- Personal v0: `pb-current-01`, `pb-tabs-01`, `pb-research-01`, `pb-account-01`, `pb-handoff-01`, `pb-safe-01`,
  `pb-longpage-01` (one per category).
- Gallery v0 isolated: `ui-table`, `ui-autocomplete`, `ui-infinite`, `ui-shadow`, `ui-iframe`, `ui-editor`.

## Estimands (per track and overall)

- **Primary:** scripting/legacy input tokens summed over matched (task, repeat) cells both arms solved.
- **Secondary:** first-request input (median), model requests, MCP calls, list-price cost, success counts, Python
  use (calls, runs).

## Reading

- Supported: overall joint input ratio ≤ 0.90 and successes not lower by more than 1 in any track.
- Not supported: overall ratio ≥ 1.00.
- Otherwise inconclusive. Two repeats; read per-track differences as observations.

## Integrity

- Python runs arbitrary local code in the Kitsune server; the relay cannot block out-of-fixture navigation inside a
  script. The runner records URLs in Python code and MiniWoB reward patterns (`core.`, `endEpisode`, `WOB_`,
  `EPISODE`, `.evaluate(`). Any hit is reported per run.
- Without an allowlist, the `legacy` arm can call `browser_evaluate` and other non-UI tools; tasks still say UI only.
- Not a Playwright comparison; do not pool with head-to-head tracks.

## Stops

Harness error or two unscorable runs in a row; Kitsune revision change or dirty checkout; a published tool count other
than the arm's (27 / 14).

## Smoke (not counted)

Before freezing: `mw-click-test-2` legacy and scripting, `pb-current-01` scripting, all successful. First-request input
10,557 (legacy) vs 7,547 and 7,687 (scripting). Published 27 and 14. No Python call in these three runs.

A first counted start on `c0f80a2` was stopped after 6 runs when main moved to `362c1fd`; those runs are kept in
`artifacts/scripting-ab-c0f80a2-aborted/` and not counted. The counted runs start over on `362c1fd`.
