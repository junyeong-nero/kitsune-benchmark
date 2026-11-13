# Agent-browsing combinations: bounded first-nine restart

**Status: STOPPED at start 6; five scored Codex results, one setup failure.**
The authorized first nine were not completed. The main comparison remains on
hold. This is a partial diagnostic, not a complete nine-configuration ranking.

## Scope and accounting

After [pilot-v1's initialization failure](2026-11-13-agent-browsing-combinations-pilot.md),
the operator explicitly authorized **only nine starts in a separate cohort**.
Source `7426bd7` and `artifacts/agent-combinations-pilot-v2-first-nine/manifest.json`
freeze the corrected paths, runtime/catalog pins and `authorized_cli_starts: 9`.
A larger `run --limit` cannot exceed that manifest cap. No continuation beyond
nine was authorized, regardless of audit outcome.

All six starts here were scheduled for **`pb-longpage-01`, variant 0, repeat 0**.
They request Codex **`gpt-6.1-sol`, medium**, through the ChatGPT-subscription-only
harness. Requested models are not independent backend identity attestations.
No Claude Code task, gallery task or model-based image task was reached.

| Cohort | Counted CLI starts | Scorable results | Setup/initialization failures |
| --- | ---: | ---: | ---: |
| Stopped pilot-v1 | 1 | 0 | 1 |
| This restart | 6 | 5 | 1 |
| Cumulative start accounting only | **7** | — | — |

Do not pool the cohorts into a performance estimate. The three remaining
first-nine configurations were **not started**: Codex + agent-browser, Claude
Code + Kitsune/Zen, and Claude Code + Playwright/Chrome. The further 18 CLI starts,
manual Chrome sidepanel and blocked browser-use native Agent were not run.
No retry, replacement start, paid API fallback or main comparison occurred.

## Task outcomes and token usage

Five externally graded runs passed functional and safety checks. Each row is
**one run of one task**, not an estimated general completion rate.

| Configuration | Outcome | Input, including cache | Cached input subset | Output | MCP calls |
| --- | --- | ---: | ---: | ---: | ---: |
| Codex + Kitsune six-tool / private Zen | Pass | 198,060 | 176,896 | 648 | 9 |
| Codex + Microsoft Playwright MCP / private Chrome | Pass | 110,008 | 86,272 | 299 | 9 |
| Codex + Aside native REPL / Aside | Pass | 129,899 | 114,432 | 440 | 5 |
| Codex + EgoLite script wrapper / EgoLite | Pass | 114,802 | 94,848 | 576 | 5 |
| Codex + Chrome DevTools MCP / private Chrome | Pass | 165,643 | 140,672 | 328 | 6 |
| Codex + Browser Harness MCP / private Chrome | Setup failed; unscorable | unavailable | unavailable | unavailable | 0 |

Cache reads are already included in input; **do not add the two columns**.
Known usage across five starts is 718,412 input (613,120 cached) and 2,291 output
tokens. Coverage is **5/6 starts**, with the failed start unavailable rather than
zero. These counts are neither billed cost nor remaining subscription quota.

The Kitsune trace retains one failed **read-only** Python call that exceeded the
16,000-byte output limit. It recovered with scoped DOM queries, without observed
replay of completed writes. That recovery is included in its calls, tokens and
time; it is not a replaced or discarded task attempt. Other traces used native
find/snapshot or rendered-DOM queries and ordinary form input. The observed
strategies differ, so catalog size alone does not explain token differences.

## Timing and observation geometry

Seconds, rounded for display:

| Configuration | Raw agent elapsed | Relay setup | Post-call inventory | Raw − measured setup/inventory |
| --- | ---: | ---: | ---: | ---: |
| Kitsune / Zen | 41.856 | 1.145 | 0.048 | 40.663 |
| Playwright / Chrome | 18.623 | 0.489 | 0.042 | 18.092 |
| Aside | 28.618 | 4.248 | 0.054 | 24.316 |
| EgoLite | 34.482 | 2.747 | 0.769 | 30.966 |
| DevTools / Chrome | 21.879 | 0.858 | 0.011 | 21.010 |

Raw time is the agent-harness interval, not total end-to-end provisioning time.
Private browser launch, the separate pre-catalog probe and final owned-runtime
cleanup are outside it; their total duration is not separately summarized here.
The subtraction is an overhead description, not pure model latency. The failed
Browser Harness start took 2.065 seconds of setup; it is not model latency and
has no adjusted-time result.

Effective personal-page viewport reports were **not equal**:

| Configuration | Observed CSS viewport(s) | DPR |
| --- | --- | ---: |
| Kitsune / Zen | 1042×789 | 1 |
| Playwright / Chrome | 1280×813 | 1 |
| Aside | 1440×900 and 1280×720 | 2 |
| EgoLite | 720×1010 and 708×998 | 2 |
| DevTools / Chrome | 1280×813 | 1 |

Native app contexts are not fresh profiles. Browser engines, viewport geometry,
permissions and different native UI APIs confound an MCP-only interpretation.
No model-based screenshot/vision result exists; the successful no-model image
preflight must not be substituted for one.

## Partial evidence audit

`partial-audit.json` records `continue: false`; no first-nine continuation approval
was issued. The audited `runs.jsonl` SHA256 is
`fb85dd6ee1844abcc820b3aebf346c4921a58f037226c02373b7e5a05ee21539`.

- The five scored runs have verified starting fixtures and passing unchanged
  functional/safety graders. All seed tabs were preserved under that contract.
- Their pre-run, actual model-facing and post-run catalogs match the frozen
  native catalogs. Source/runtime pins were verified before writing this report.
- Every reported input/cache/output value matches the raw `turn.completed`
  usage for its run. All five report `chatgpt_subscription_only` authentication.
- Reviewed all **34 finished MCP-call records**, including the one failed
  read. Submitted arguments stayed within fixture DOM/UI operations; no shell,
  host-file, hidden-source, direct-HTTP or other-model action was observed.
  This trace review is not proof of sandbox confinement or permission parity.
- All six relay close acknowledgements were present. Owned private Chrome/Zen
  cleanup completed; native Aside/Ego apps were not globally terminated.
  PIDs flagged by the setup-failure resource sampler were no longer present at
  audit, and no matching owned relay process remained alive.

## Browser Harness blocker

Start 6 stopped with:

> `ValueError: Fixture starting tabs do not match`

It is **`setup_failed`**, not a model-task failure: `model_request_observed: false`,
no model events, no agent MCP calls and no token usage. The failure occurred while
preparing the initial fixture, before the model-facing tool catalog was returned.

The initial inventory had two owned blank tabs. That is expected for this named
Browser Harness daemon, and the adapter already closes the extra blank; it is
**not sufficient evidence that an unhandled extra blank caused the failure**.
The exception occurred after bootstrap/navigation and two native new-tab calls.
Unfortunately the exact mismatching final inventory was not persisted, so the
original artifacts do not establish whether a tab was missing or had a stale URL.

Four additional **model-free** catalog-probe + relay-sequence diagnostics all
produced the correct three fixture tabs. They did not reproduce the failure and
must not be reported as a fix or replacement successful agent run. Evidence is
under `artifacts/agent-combinations-diagnostics/browser-harness-sequence-v1/`
through `browser-harness-sequence-v4/`.

The pinned native helper's `goto_url` returns a CDP `Page.navigate` response,
without an explicit load wait, while `new_tab` may reuse a currently blank tab.
Navigation/new-tab timing is therefore a candidate to investigate, **not a
confirmed root cause of this start**. Before another inference cohort:

1. Retain the exact failing inventory and relevant native setup responses.
2. Reproduce the failure with a bounded delayed-navigation/creation control;
   validate synchronization and distinct-tab creation without relaxing graders,
   required URLs, authorization caps or model deadlines.
3. Revalidate the real runner sequence, including pre-catalog initialization and
   the separate CLI working directory, before seeking new run authorization.

The current pilot is not ready to promote into the main comparison. Do not
resume the stopped cohort or use the unstarted slots for favorable retries.
No product README figure or earlier product merge-hold recommendation changed.

## Reproducibility and files

- [Protocol and limitations](../experiments/2026-11-13-agent-browsing-combinations.md)
- Local merge: `527aea0`; pilot implementation: `90cf839`; path correction:
  `f949af2`; authorized restart cap/frozen source: `7426bd7`.
- Before this cohort: full 608-test regression run, 23 opt-in skips; then all
  30 focused pilot tests passed after adding the explicit nine-start cap.
- No-model preflight: `artifacts/agent-combinations-postfix-preflight-v1/`.
- This cohort: `artifacts/agent-combinations-pilot-v2-first-nine/`, including
  `manifest.json`, `operator-authorization.json`, `runs.jsonl`, `partial-audit.json`,
  `stopped.json` and each attempt's raw events, metrics, grader and cleanup files.
- No remote push. Failed/partial evidence and both cohorts remain separate.
