# Agent-browsing combinations: token-efficiency comparison

**Status: RESTART STOPPED AT START 6 / FIVE SCORED CODEX RESULTS / MAIN RUN ON HOLD.**
See the [partial first-nine report](../results/2026-11-13-agent-browsing-combinations-first-nine.md).
Browser Harness fixture setup failed; the last three authorized configurations
were not started. The restarted cohort is stopped, not resumable without review
and renewed authorization.
The first counted CLI start failed during MCP initialization; no model turn or
usage was recorded. See the [stopped pilot report](../results/2026-11-13-agent-browsing-combinations-pilot.md).
Do not resume that manifest or erase its counted start. After the correction, the
operator explicitly selected **only the first nine starts of a new cohort**.
That authorization capped cumulative CLI starts at **10 including the prior
failure**; actual cumulative starts are **7** (one old failure plus six restarted
starts). The frozen restart manifest sets `authorized_cli_starts: 9`. The remaining
18 and the main comparison were not authorized, and neither stopped cohort may
be automatically retried.
The operator subsequently authorized merging the benchmark work into `main` and
running this diagnostic **before a separately authorized main comparison**. Local
merge `527aea0` integrates the preparation scaffold with updated upstream `main`;
no remote push or product-repository merge is implied. The selected CLI models,
medium effort, maximum 33 starts and **zero paid API budget** remain unchanged.
Manual operation in the user's Chrome profile is not authorization for automated
attachment. No-inference evidence and a clean frozen manifest are required before
CLI inference; the manual Chrome track remains separately pending.

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
  pooling old cohorts. The newly authorized merge is benchmark-only. No product
  merge, release, tag or everyday-browser restart is part of this work.

## Approved pilot design — final validation and manifest freeze required

### A. CLI-backed combinations

Use two separate model panels. The selected CLI matrix is seven Codex
combinations plus a paired Kitsune/Playwright Claude Code comparison, rather than
multiplying every candidate by every model before establishing feasibility.

| ID | Outer agent | Browser interface | Browser/runtime | State |
| --- | --- | --- | --- | --- |
| codex-kitsune-zen | Codex | Kitsune, six tools | Private Zen | One scored pass in the stopped restart; explicit private Zen |
| codex-playwright | Codex | Microsoft Playwright MCP | Private Chrome (Chromium) | One scored pass in the stopped restart; owned Chrome |
| codex-aside | Codex | Aside native MCP REPL | Aside app | One scored pass; fresh REPL context, not a fresh profile |
| codex-ego | Codex | EgoLite script wrapper | EgoLite app | One scored pass; fresh TaskSpace, not a fresh profile |
| codex-devtools | Codex | Chrome DevTools MCP | Private Chrome | One scored pass; owned Chrome, native schemas |
| codex-browser-harness | Codex | Browser Harness MCP | Private Chrome | Actual CLI fixture setup failed at start 6; unscorable |
| codex-agent-browser | Codex | agent-browser MCP | Private Chrome | No-model preflight passed; not started after the stop |
| claude-kitsune-zen | Claude Code | Kitsune, six tools | Private Zen | Not started after the stop; shares validated Zen runtime |
| claude-playwright | Claude Code | Microsoft Playwright MCP | Private Chrome (Chromium) | Not started after the stop; shares validated Chrome runtime |

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
**1.0.1022.1**, EgoLite **0.6.3.12** during the original preparation. Before the
executable freeze, the installed EgoLite bundle reports **0.6.3.14**; use the
source-matched preflight's before/after runtime hashes, not the old observation.
Installed bundle versions are not independent attestations of a running vendor
process. No everyday browser was restarted to normalize versions. These checks
do not prove isolated profiles or matching viewports. No personal login store or
unrelated tab inventory was inspected.

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

## Implemented CLI policy and observability limits

`scripts/run-agent-combinations.py` freezes the three-condition schedule from the
offline plan; it never expands that registry. Native browser-side Python/JS/CDP
may inspect **rendered DOM text, geometry and visible state**, and perform normal
UI input. The common prompt prohibits hidden application variables, task/grader
source, storage/cookies, host files, response/network bodies, direct HTTP, script
injection, permission changes, readonly/disabled bypass and unrelated tabs.
This is a declared action policy, **not a sandbox or equal permission boundary**.
Aside receives its prepared `tabs`/`page` handles; Ego resumes exactly its prepared
TaskSpace. Neither is allowed to discover unrelated app contexts. Kitsune's
published tools remain its actual six controls; setup uses the existing gateway.

Personal/gallery whole-attempt limits are 180/240 seconds. MCP call limits are
45 seconds for Kitsune/Playwright and 130 seconds for the other native interfaces;
upstream native deadlines also apply. All CLI attempts are sequential. The first
invocation stops after at most nine starts even when its requested limit is 27.
Further starts require a reviewed `first-nine-audit.json` whose SHA256 matches the
first nine persisted rows. A counted start with partial/missing evidence is never
automatically retried. Usage is saved before grading/catalog checks can fail.

Preflight covers 21 runtime/fixture cells, three independent positive UI controls,
and seven no-model replays of the **actual stdio/filter/image/EOF-cleanup path**.
These are not model attempts or evidence that a model understood an image. The
manifest captures source/lock hashes, browser and CLI executable pins, native
guides/catalogs and preflight identity. It rejects source/runtime/catalog drift.
The relay survives the CLI's process-group stop to close native fixture contexts;
the runner requires its close acknowledgement, with a bounded owned-process
cleanup fallback. Unknown cleanup is a stop, not a success.

Zen uses a fresh profile/HOME/bridge and `MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1`.
Private Chrome disables component/background updates, uses a mock keychain/basic
password store, and never attaches a default endpoint or personal profile. These
launch flags are treatment details, not stock-browser equivalence. Aside/Ego
context isolation is weaker than profile isolation. Browser Harness's bridge
preserves the native receipt and adds only freshly written PNGs inside the
attempt's own image directory; a file path alone does not count as image delivery.

**Viewport parity is not asserted.** Personal fixture pages report CSS viewport
and DPR; gallery pages do not, so gallery CSS viewport/DPR remain unavailable.
The image preflight records delivered pixel dimensions for all conditions. Earlier
blank-page checks already showed different Zen and Chrome dimensions. Browser
engine, UI, profile/context isolation and permission differences confound any
MCP-only causal interpretation. These are practical combinations, not a pure
transport ablation.

Report raw elapsed time and measured relay setup/post-call inventory separately.
Their subtraction is descriptive overhead adjustment, not pure model latency.
External provisioning and final cleanup lie outside the agent's raw timer. No
missing usage/timing is filled with zero; cross-model tokens remain separate.

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
evidence-supported presentation update. The scaffold is now merged into local
`main`; the original branch was `experiment/agent-browsing-combinations`.

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
- [x] Implement the seven runtime surfaces underlying all nine CLI combinations;
  the 21-cell fixture/image/noncompletion matrix and three UI positive controls
  passed (`artifacts/agent-combinations-fixtures-v8/`).
- [x] Complete final source/runtime-matched preflight: 21 cells, three positive
  UI controls and all seven actual stdio/image/cleanup replays passed in
  `artifacts/agent-combinations-final-preflight-v2/`. The regression suite ran
  606 tests with 23 opt-in skips and no failures.
- [x] Freeze the clean executable manifest at `90cf839` in
  `artifacts/agent-combinations-pilot-v1/manifest.json`.
- [ ] Prepare manual Chrome fixture instructions and observable grading.
- [x] Implement the bounded runner, failure retention and first-nine CLI audit gate.
- [ ] Complete the approved pilot: **stopped after one counted CLI start**;
  all raw failed/partial evidence is retained, no retry or replacement.
- [x] Publish the stopped-at-initialization report; it supports no efficiency,
  completion-rate or product README claim.
- [x] Correct the cross-working-directory metadata path bug. Post-fix: 608 tests
  with 23 opt-in skips, plus all 21 fixture cells/three positive controls/seven
  different-cwd stdio image and cleanup replays passed without models in
  `artifacts/agent-combinations-postfix-preflight-v1/`.
- [x] Obtain authorization for a **separate first-nine-only restart**. Preserve
  the old failed start; cumulative CLI cap is 10, not a fresh unrestricted 27.
- [x] Freeze `7426bd7` with `authorized_cli_starts: 9`; pass 30 focused pilot tests
  including the hard authorization cap and safety-stop checks.
- [ ] Complete that first-nine cohort: **stopped at start 6**, five scored passes
  and one Browser Harness setup failure; three configurations unstarted.
- [x] Audit and report the partial cohort without approving continuation or
  pooling it with the earlier failure. No additional 18 starts.
- [ ] Resolve Browser Harness initialization evidence/synchronization before
  requesting another inference cohort; four no-model replays did not reproduce
  the failure and do not constitute a fix.

Plan-only command (no browser/model):

```sh
uv run --locked python -m kitsune_benchmark.agent_combinations
```

Restart workflow for reference (**both existing cohorts are now stopped; new
inference requires renewed authorization**; `freeze` invokes no model):

```sh
uv run --locked python scripts/preflight-agent-combinations.py --out artifacts/<preflight>
uv run --locked python scripts/run-agent-combinations.py freeze \
  --preflight artifacts/<preflight>/preflight.json --out artifacts/<new-pilot> --limit 9
uv run --locked python scripts/run-agent-combinations.py run --out artifacts/<new-pilot> --limit 9
# pilot-v1 remains stopped. The new manifest hard-caps starts at 9 even if a
# subsequent invocation requests more. Audit the nine, but do not approve continuation.
```

The offline plan command deliberately remains `execution_ready: false`; only a
separate validated manifest authorizes this runner's CLI path. Manual Chrome and
browser-use native Agent are not launched by it.

The original Node lock still reports five npm audit findings (three low, one
moderate, one high). `npm explain` traces the high `node-forge` finding to
`web-ext → @devicefarmer/adbkit`; the other findings are `addons-linter` /
`deepmerge` / `fast-uri`. This pilot uses desktop `web-ext run` with a trusted
pinned local extension, not Android/ADB, package signing or untrusted extension
linting. Native browser network/TLS is not implemented with `node-forge` here.
That path assessment is **not a clean security audit**; the findings remain
unfixed and retained. No automatic `audit fix` or unrelated historical dependency
rewrite was performed. The separately installed additional tool lock reported
zero findings at preparation time.

## Remaining execution gates

1. Resolve the Browser Harness fixture-initialization blocker, retain failing
   inventories, and validate the actual catalog-probe/relay lifecycle without
   inference. Do not claim the four passing replays fixed the observed failure.
   Re-freeze exact catalogs, guides, browser/CLI binaries and owned resources only
   for a newly authorized cohort.
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
