# Agent-browsing combinations: token-efficiency comparison

**Status: PILOT SCOPE APPROVED / PREFLIGHT PENDING / NOT YET EXECUTABLE.** The
operator selected the previous CLI models at medium effort, a maximum 33-start
diagnostic and **no paid API usage**. After login failed in the dedicated Chrome
profile, the operator selected **manual execution in their own Chrome profile**;
there is no authorization for an automated attachment to that profile. Runtime
pins, adapters and measurement evidence must pass
no-inference preflight before freezing an executable plan. No model attempt
belongs to this proposal yet. Candidate availability is not adapter support.

## Confirmed scope

- Keep Kitsune at its actual **six-tool** code-first surface. Do not include a
  14-tool Kitsune arm, add a benchmark allowlist, or change product permissions.
- Compare practical agent/browser combinations, not relabeled historical runs.
- Keep product names in the README figure legend. Use a token-efficiency and
  completion-rate framing, not product-targeted superiority headlines/callouts.
- Include **the Chrome extension's own side-panel agent**, not a silent substitute
  using `claude --chrome`.
- Investigate **browser-use native Agent and Browser Harness MCP separately**.
- Support adding baselines without rewriting historical experiment runners or
  pooling old cohorts. No merge, release, tag or everyday-browser restart is
  part of this work.

## Approved pilot design — runtime preflight pending

### A. CLI-backed combinations

Use two separate model panels. The selected CLI matrix is seven Codex
combinations plus a paired Kitsune/Playwright Claude Code comparison, rather than
multiplying every candidate by every model before establishing feasibility.

| ID | Outer agent | Browser interface | Browser/runtime | State |
| --- | --- | --- | --- | --- |
| codex-kitsune-zen | Codex | Kitsune, six tools | Private Zen | Existing Firefox adapter needs an explicit Zen launch and validation |
| codex-playwright | Codex | Microsoft Playwright MCP | Private Chrome (Chromium) | Existing adapter uses Firefox; new explicit browser configuration needed |
| codex-aside | Codex | Aside native MCP REPL | Aside app | Existing relay; revalidate current app/catalog and isolation limits |
| codex-ego | Codex | EgoLite script wrapper | EgoLite app | Existing relay; current app differs from historical pin |
| codex-devtools | Codex | Chrome DevTools MCP | Private Chrome | New adapter, telemetry and lifecycle checks required |
| codex-browser-harness | Codex | Browser Harness MCP | Private Chrome | New adapter; must not attach its default CDP port to an everyday browser |
| codex-agent-browser | Codex | agent-browser MCP | Private Chrome | New adapter; current upstream documents an MCP entry point |
| claude-kitsune-zen | Claude Code | Kitsune, six tools | Private Zen | Same product/browser treatment as Codex Kitsune |
| claude-playwright | Claude Code | Microsoft Playwright MCP | Private Chrome (Chromium) | Same browser/tool treatment as Codex Playwright |

Selected CLI model pins are `gpt-6.1-sol` and `claude-opus-5-5`, both medium,
using existing subscription logins. These are requests, not independent backend
identity attestations. There is no API fallback. CLI versions observed locally:
Codex **0.163.0**, Claude Code **2.1.303**.

### B. Native agents, reported separately

| ID | Configuration | Outstanding requirements |
| --- | --- | --- |
| chrome-sidepanel | Claude in Chrome's own side panel, manually operated in the user's profile | No automated profile attachment or cookie/tab inspection. Record operator-reported extension version, Cowork/classic mode, selected model and permission mode; prepare fixture-only instructions and document unavailable per-attempt usage/timing/custody evidence |
| browser-use-agent | Pinned browser-use Python Agent with explicitly local browser | **Blocked for execution: API budget is zero.** Keep it as a separate candidate; no gateway/cloud call, CLI-OAuth repurposing or replacement model |

The native Agent's three possible diagnostic slots are not reallocated. The
currently permitted executable ceiling is **30 starts: 27 CLI + 3 Chrome**, only
if all those adapters pass preflight. The operator reported that Claude login
failed in the dedicated profile, configured their own Chrome profile instead,
and explicitly selected manual execution there. The unused dedicated browser
was stopped after verifying its process identity. Do not copy credentials or
cookies, attach CDP/MCP to the personal profile, enumerate unrelated tabs, or
automate foreground input. The operator alone submits the three frozen tasks in
separate fixture tabs. This is not an isolated-profile or fully instrumented run;
server-observed functional completion does not establish tab custody or safety.
Do not attribute manual waiting/setup to native agent latency.

A native agent is not an equivalent outer-model MCP treatment. Do not place raw
cross-tokenizer counts in one universal efficiency ranking. Missing usage is
`null`/unavailable, not zero, an estimate from text length, or inferred from a
subscription meter. If Chrome usage cannot be measured, report observed task
completion/timing and the usage limitation separately from the token chart.
Do not use a Claude Code Chrome run as a proxy for the selected side panel.

### Candidate inventory and source observations

Reviewed 2026-11-13. These source HEADs are observations for planning, **not yet
frozen executable treatments**; resolve and verify complete dependency/browser
pins during preflight. Do not install `@latest` in the eventual experiment.

| Candidate | Observed upstream HEAD |
| --- | --- |
| browser-use | `48d9fe008bb98a8959279b495518652dfb934d6b` |
| Browser Harness | `389d9c08fe83641b5af924a777d390e9b61aace3` |
| Chrome DevTools MCP | `e49d8264c8ac5b7a3a81b0198cc8996036e31bb7` |
| agent-browser | `4720bc3dd73f2c8f7c84f415adfa560330b924c4` |

The browser-use README recommends exact version `1.0.3`. It describes a native
Python/REPL/CDP agent and defaults to a model gateway plus cloud browser.
`Browser('chromium')` is its explicit fresh-local-profile path; `Browser('chrome')`
and profile-copy modes are not suitable substitutes for isolation.

The 2026-10-18 candidate survey's agent-browser row is historical: current
upstream also documents `agent-browser mcp`. Verify the actual pinned native
catalog; do not invent a common tool schema to make candidates look equivalent.
Other surveyed candidates remain future additions, not implicit executions.

Locally observed app versions: Zen **1.24.2b**, Chrome **157.0.8103.52**, Aside
**1.0.1022.1**, EgoLite **0.6.3.12**. Verify runtime versions, binary hashes and
native catalogs before freezing. This does not prove isolated profiles or matching
viewports. No everyday profile, login store or tab inventory was inspected.

## Workloads and proposed execution caps

Reuse unchanged synthetic task data and graders, but create a new cohort with
new manifests, artifacts and a frozen protocol. Do not resume the stopped Opus
cohort or pool the completed four-way/older MiniWoB results.

Selected initial diagnostic set, chosen before model execution:

1. `pb-longpage-01`: personal browsing and bounded evidence extraction.
2. `ui-table@crowded`: UI actions amid distractors.
3. `mm-chart@isolated`: screenshot delivery and visual interpretation.

One repeat gives **27 CLI attempts** (nine combinations × three conditions),
plus **at most three Chrome attempts** if ready. The operator approved an upper
bound of **33 starts**, but the native Agent's three slots remain unused under
the zero-API policy; the executable ceiling is 30, not 33 guaranteed completions.
No uncounted inference smoke/probe. Any unavailable configuration remains
explicitly pending, never a fabricated measured row. This diagnostic set is not
sufficient for a broad README efficiency claim.

For a future, separately authorized and frozen main comparison, the previously
defined expanded task set offers seven personal, ten isolated and six crowded
conditions. The following full-pool arithmetic is planning only; it does not
authorize paid native-agent slots or either larger main comparison:

| Scope | CLI attempts | Native-agent attempts if ready | Maximum starts |
| --- | ---: | ---: | ---: |
| Three-condition diagnostic, one repeat | 27 | 6 | 33 |
| 23 conditions, one repeat | 207 | 46 | 253 |
| 23 conditions, two repeats | 414 | 92 | 506 |

Only the selected diagnostic scope may become executable after preflight. These
are task starts, not model-request counts or subscription-quota estimates. Rotate combination order
within each model group, reverse it for a second repeat, and predeclare the group
interleaving. If development changes follow a diagnostic, retain that diagnostic
separately; never splice it into the later main results.

Proposed whole-attempt limits: personal 180 seconds; gallery 240 seconds.
Pin and disclose per-tool/runtime limits separately. Count failed attempts and
in-flight usage on cancellation where observable. Stop on quota exhaustion,
transport/setup failure, required-evidence loss, source/catalog drift or
out-of-scope actions. Preserve the stopped attempt; no favorable retry,
replacement, relaxed timeout, automatic new cohort or paid fallback.

## Required implementation and no-inference validation

Use a small explicit baseline registry and reuse the existing `Server`, `Task`,
CLI invocation, fixture and result-accounting pieces where compatible. Browser
lifecycle, fixture seeding, image delivery and native-agent triggering need their
own adapters. Do not build a new general-purpose plugin framework or silently
route every native agent through the existing MCP-only CLI assumptions.

Each candidate must expose an availability state and evidence for:

- Exact agent/model/browser/tool/guide pins and authentication mode.
- Owned processes, temporary HOME/profile/bridge/CDP resources, fixture-only
  access, cleanup and no default-user-port connections. Existing vendor contexts
  are not fresh profiles; investigate isolation and disclose any residual mismatch.
- Actual initial tabs, effective CSS viewport/DPR and screenshot dimensions.
  Configuration values alone are not parity evidence.
- Successful transport of screenshots and other observations to the real agent
  interface; artifact paths alone are not delivered images.
- Unchanged task grading on noncompletion and deterministic reference actions.
- Model-visible catalog before/after, or an explicit native-agent observability
  limitation. Kitsune must advertise exactly its six actual controls.
- Input/cache/output usage coverage, native/nested model calls where exposed,
  raw time and separately measured setup/inventory overhead. No fictional zeros.

Kitsune source proposed for this new cohort:
`14d9ceb29de7611d41d0564f3ed6c343180c276e`. It includes later fixes and is **not**
the historical benchmark candidate `f5c7a0f`. The existing benchmark runner
launches a private Playwright Firefox binary, not Zen; its old rows cannot be
renamed to `Kitsune + Zen`.

The historical relay emits bare protocol `decline`. Current Kitsune correctly
treats that as unknown provenance and retains its bounded popup window. A new
simulated explicit refusal must submit the actual form decision
`{"action":"accept","content":{"decision":"Decline"}}`, where the prompt
schema accepts it, and record that provenance. Preserve historical relay behavior
for old protocols. Simulated refusal is not human-approval coverage.

The UI/observation policy must be frozen by track. CLI MCP tools retain native
schemas and documented guides, with no hidden-grader/source access, direct task
HTTP shortcuts, readonly/disabled-field bypass, unrelated-tab access or replay
of completed writes. Native code agents may expose Python/JS/CDP as their normal
interface; resolve and document the permitted visible-DOM/input operations before
execution rather than claiming the old UI-only policy was automatically enforced.
Trusted host code and post-call inventory are not confinement or complete safety
proofs. Do not introduce new capabilities into Kitsune for benchmark parity.

## Reporting and README

Report success and usage together, including failures and recovery rounds.
Within-model paired ratios require matching task/repeat sets and known usage.
Show the exact denominator and coverage for every metric. Aggregate and
per-condition results can disagree; retain both. Do not select a favorable subset
or keep adding baselines until the intended headline wins.

Use a neutral title such as **Token use across browser tasks**. Keep exact
combination names in the legend, including the outer agent and browser. Separate
model panels and native-agent results as needed. Publish complete methods and
limitations behind the figure. Cache-inclusive input is neither billed cost nor
subscription quota, and a small tool catalog is not a measured token saving.
Do not fill new rows with old measurements or replace the published figure before
its new claims have evidence.

## Implementation status and TODO

All protocol, runtime, runner, test and results changes for this experiment belong
in **kitsune-benchmark**. The product repository receives only a later,
evidence-supported presentation update. Current development branch:
`experiment/agent-browsing-combinations`.

- [x] Record the selected models, nine CLI combinations, diagnostic task set,
  zero-API policy and manual-only personal Chrome boundary.
- [x] Add the offline registry/plan in `kitsune_benchmark/agent_combinations.py`;
  refuse matrix growth rather than reallocating the three blocked native slots.
- [x] Add and verify the private Chrome lifecycle helper. Eight unit tests and a
  real headless CDP handshake/owned-process cleanup passed. The unused headed
  login browser was stopped; no personal Chrome was attached or stopped.
- [x] Lock additional tools separately under `configs/agent-combinations/`:
  Chrome DevTools MCP 1.13.0, agent-browser 0.43.0, Browser Harness source
  `389d9c0` in its own Python environment. Installation is not adapter validation.
- [x] Pass six offline plan tests, including caps, separate model panels,
  six-tool Kitsune, blocked native slots and unavailable manual-Chrome metrics.
- [ ] Implement and validate all selected CLI runtime/fixture adapters, actual
  native catalogs, screenshot delivery, lifecycle cleanup and grading controls.
- [ ] Prepare manual Chrome fixture instructions and observable grading.
- [ ] Freeze the executable manifest and implement the first-nine CLI audit gate.
- [ ] Run only the approved pilot starts and retain all failed/partial evidence.
- [ ] Audit and publish a reviewed pilot report here; decide separately whether
  further authorized measurement can support a product README figure.

Plan-only command (no browser/model):

```sh
uv run --locked python -m kitsune_benchmark.agent_combinations
```

No execution command or new model result exists yet. The original benchmark
Node lock currently reports five npm audit findings (three low, one moderate,
one high); do not mistake successful installation/tests for a clean audit.
Assess the relevant execution paths before freezing; no automatic `audit fix`
or unrelated historical dependency rewrite was performed. The separately
installed additional Node-tool lock reported zero findings at preparation time.

## Remaining execution gates

1. Implement and validate the nine CLI combinations without inference; pin the
   exact catalogs, guides, browser binaries and owned runtime resources.
2. Prepare manual Chrome fixture instructions and collect operator-reported
   extension/mode/model and permissions. Validate server-side functional grading
   without attaching to the personal profile or issuing a hidden model smoke
   run. Missing usage, exact timing and tab custody remain unavailable. Do not
   substitute a Claude Code run or infer permission parity from completion.
3. Freeze the per-track operation policy, schedule, limits and availability
   manifest. Identify unsupported candidates explicitly before inference rather
   than silently reducing a purported complete denominator.
4. Keep browser-use native Agent execution blocked under zero API budget. A
   different model/provider, subscription bridge, paid API, main-cohort expansion
   or replacement attempt needs renewed authorization.

## Sources

- [Historical independent four-way protocol](2026-11-13-expanded-four-way-codex.md)
- [Candidate survey](../comparison-candidates.md)
- [Browser Use README](https://github.com/browser-use/browser-use)
- [Browser Harness MCP](https://github.com/browser-use/browser-harness/blob/main/docs/MCP.md)
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)
- [agent-browser](https://github.com/vercel-labs/agent-browser)
- [Claude in Chrome overview](https://support.claude.com/en/articles/12012173-get-started-with-claude-in-chrome)
- [Claude Enterprise consumption guide](https://support.claude.com/en/articles/14782391-claude-enterprise-consumption-guide)

Public source documentation is capability evidence, not an inference preflight,
actual token measurement or certification of our local setup.
