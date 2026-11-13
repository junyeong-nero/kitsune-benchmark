# Expanded four-way: Codex Sol 6.1, separate frozen cohort

The operator selected a **new four-way 184-attempt experiment**, then authorized using Codex Sol 6.1
instead of consuming substantial Claude subscription quota. The entire new cohort uses Codex; no
model attempts occurred before that switch. The interrupted 85-row Opus A/B is preserved unchanged.
This is a product comparison, **not renewed authorization to merge the code-first candidate**.

## Treatment and workload

| Arm | Product revision / tool interface |
| --- | --- |
| Kitsune default | `47dafa20a3fddc697a7d991e15d39e4b0232c10d`, actual 14-tool default |
| Kitsune code-first | `f5c7a0f85aefd89e621e73665e33d33d79d50676`, actual six-tool default |
| Aside | Installed native MCP `repl` only, native description/schema unchanged |
| EgoLite | Installed CLI `nodejs` through `run_script`, unedited vendor guide plus documented image transport |

Neither Kitsune product checkout changes. No CAPS/scripting/permission override or benchmark tool
allowlist is applied to either Kitsune arm. Aside `exec`, profile/memory discovery and vendor-agent
inference are not available. Ego has no native MCP: the wrapper forwards the requested script to its
CLI. No subagent, alternative network/host access, or product-specific answer hint is supplied.

**23 conditions x two agent repeats x four arms = 184 attempts**, all variant 0:

- Personal (7): `pb-current-01`, `pb-tabs-01`, `pb-research-01`, `pb-account-01`, `pb-handoff-01`,
  `pb-safe-01`, `pb-longpage-01`.
- Gallery isolated (10): `ui-table`, `ui-infinite`, `ui-sortable`, `ui-datepicker`, `ui-autocomplete`,
  `ui-shadow`, `ui-iframe`, `ui-editor`, `ui-toast`, `mm-chart`.
- Gallery crowded (6): `ui-table`, `ui-infinite`, `ui-sortable`, `ui-editor`, `ui-autocomplete`, `mm-chart`.

No MiniWoB rerun or historical pooling. Isolated and crowded are distinct conditions, never treated
as repeats of one task. Existing fixture data, task wording and graders remain, with common UI-only
restrictions and the vendor-specific prepared-context/image handoff instructions described below.
Two repeats of one variant do not establish statistical significance.

## Model, execution order and limits

- **Codex CLI 0.163.0**, requested model **`gpt-6.1-sol`**, explicitly **medium** effort (not its default low).
  The local model catalog advertises medium and text/image input; actual service acceptance is first
  exercised by a counted attempt, not an extra uncounted model probe.
- Existing **ChatGPT subscription login only**. Child environments exclude model API credentials and
  provider overrides. `forced_login_method=chatgpt`, provider openai, no API fallback. The parent process
  may have API credentials: standalone doctor flags those; the actual sanitized child environment must
  pass doctor/preflight. Credential values never enter reports or source control.
- Codex runs ephemerally outside the repositories with user config/rules, skills, shell, built-in search,
  image generation, memories, hooks and delegation disabled. Only the browser MCP surface is supplied.
  These restrictions do not sandbox trusted Python/Node browser-code tools.
- All attempts sequential. Rotate the four arm order by condition; reverse that order in repeat 1.
  The first two conditions are personal current-page and isolated infinite scroll: **first eight attempts**
  cover all arms and both fixture families. Stop there for integrity audit before the remaining 176.
- Personal whole-run limit **180 s**, gallery **240 s**. Existing MCP envelopes: Kitsune **45 s**,
  vendor script tools **130 s**, with vendor runtimes' own **120 s** script limits. These differing
  per-tool limits are disclosed, not silently treated as equal action latency.
- Freeze benchmark commit, protocol/helper hashes, product SHAs, vendor CLI/app versions and native
  guide/catalogs before inference. Check sources and actual catalogs before/after every attempt.
  Never upgrade a vendor app or tune a guide, policy, timeout, fixture or tool after observing outcomes.

## Preparation, permissions and instrumentation

### Kitsune

Fresh private headless Firefox, bridge and fixture each attempt, same construction for both arms.
Personal tabs are user-seeded through the existing BiDi channel and remain read-only to the agent.
Gallery uses the existing harness-owned task tab. No change to extension input or approval logic.

**New cohort's scripted decline:** the relay waits **two seconds**, then answers agent elicitation
`{"action":"decline"}`. Harness setup may approve its own setup operations as before. This makes the
negative response settle the request instead of triggering the product's existing sub-one-second
client-policy fallback to a browser popup. It is a deterministic simulated response, **not proof of
human approval/refusal**. It applies identically to both Kitsune revisions and is tested against both
before inference. The two-second wait stays in agent runtime; it is not subtracted as instrumentation.
The earlier Opus cohort used immediate decline, so its timings cannot be pooled with this one.

### Aside and EgoLite

Fresh native Aside MCP/REPL session or uniquely named Ego TaskSpace per attempt, using the installed
browser apps. **These are not fresh profiles.** Caches, locale, browser engine and app state can differ
from Kitsune. Do not inspect/change profiles or clear shared browser data.

The harness opens only synthetic fixture pages, loads the fixture's normal bootstrap URL to establish
its test login, and records initial tabs/selection and later inventories. It does not inspect real-user
page content or hand the model unrelated tabs. Aside's scoped `tabs`/`page` are prepopulated; the agent
is told not to use global tab/profile/memory discovery. Ego is given its already-created TaskSpace
name and must resume it, not create/claim another space or finish/hand it off before grading. Harness
cleanup is separate from agent actions and does not rewrite the final recorded inventory.

Vendor starting tabs are **harness-created, agent-accessible**. They are not asserted to have Kitsune's
user-tab ownership/refusal semantics. Task-level preservation, forbidden actions and outside-navigation
checks still apply, but a passing vendor safety grade is not evidence of equivalent tab protection.
Compare functional work/efficiency separately from permissions and refusal handling.

Requested viewport is **1280x720 CSS pixels**. Aside uses its native viewport setter; Ego setup uses
per-page CDP device metrics and front selection, invisible to the agent. Kitsune uses the existing
Firefox construction. Record available viewport evidence and disclose device scale/screenshot and
new-tab behavior differences; do not assert universal pixel equality from configuration alone.
Aside selection in inventories means the native REPL-selected `page`; Ego uses its active-tab flag.

### Images and observation policy

Aside's native `display(await page.screenshot())` emits MCP images, sometimes **JPEG**, not always PNG.
Ego's documented screenshot API returns a file path and expects an image viewer. The new experimental
wrapper attaches a PNG when the agent prints one JSON line `{"screenshot":"/absolute/path.png"}`.
It accepts only newly written PNGs within this attempt's supplied screenshot directory, max 8 MB;
no general file-read tool is added. The guide gains a short image-transport paragraph, with a stable
catalog description. Native screenshot capture remains an agent action and counts in tool runtime.
The older MiniWoB wrapper is not changed. Validate actual MCP image bytes before inference.

For every arm, use browser observation/input APIs, not page evaluation, DOM mutation, raw CDP,
fixture/source/grading reads, direct network access or readonly/disabled input bypass. Screenshot
capture/transport is permitted. Vendor guides mention escape hatches; emitted use is audited as a
policy deviation, not silently accepted because the task grader returns success.

The unchanged grader follows stable tab identities across **post-MCP-call** inventories. It does not
observe every operation within a script, attempted no-effect closes, or a temporary navigation away
and back. Review all scripts/tool calls alongside this telemetry. Native code runtimes are trusted,
not confinement boundaries. Regex scans and passing task grades do not certify compliant behavior.

## Measures and comparison denominators

Report for every arm:

- All attempts, scorable grades, functional/strict task successes, safety failures/unknowns and errors.
- Total input, cached input and output, MCP calls, raw per-agent elapsed, preparation/inventory overhead.
  Codex input includes cached input. Missing usage stays missing, never zero or an inferred saving.
- **Model request counts, first-request usage and dollar cost are unavailable** in this Codex JSONL
  harness. Do not infer them from MCP calls or apply Claude pricing; subscription use is not a bill.
- Primary cross-product timing: **raw elapsed minus measured relay setup minus measured post-call
  harness inventory time**. These hidden checks call the respective vendor API and can otherwise
  distort timing. Also always publish raw elapsed; neither is whole-experiment wall time or isolated
  browser-action latency. The two-second scripted decline and actual agent tool/image work remain.
- All-attempt totals include failed effort. Paired ratios require identical condition/repeat sets and
  known usage. Report all-four joint successes and every pairwise joint-success comparison, with exact
  denominators, separately by personal/isolated/crowded and per condition. Do not select a favorable
  survivor subset without labeling it. Unknown grade/time/model evidence prevents a complete verdict.
- Page-JS, readonly/disabled shortcuts, wrong-target errors, approval/refusal, repeated completed writes,
  outside-fixture access and screenshot strategies get manual review. UI-only sensitivity subsets are
  labeled secondary; do not change raw grades or erase noncompliant attempts afterward.

Model configuration is evidenced by the requested CLI model, forced auth/effort settings, pins and
recorded command/manifest. Codex JSONL does not provide the Claude-style init/result model-usage map;
do not claim server-side model identity attestation that the trace does not expose.

## Stopping and first-eight audit

An ordinary scorable task failure remains and does not itself stop execution. Stop on quota/transport,
setup/execution failure, missing required usage/grade/timing, source/catalog drift, forbidden harness
items or observed outside-fixture actions. Preserve the attempt and all error evidence. No automatic
retry, substitution, relaxed limits, replacement, paid API fallback or new cohort. Incomplete attempts
are not quietly omitted from a success rate or spending total.

The runner caps the initial invocation at eight attempts even without `--limit`. Continuing requires
`first-eight-audit.json` with an affirmative integrity decision and SHA-256 of those exact first eight
rows. This records the supervisor audit, not outcome-based permission to tune. A negative audit stops
for operator review. Additional focused no-model tests before freezing are not model attempts.

Previous product regression tests are retained because the product source is unchanged. Before this
cohort, validate the new relay and Codex runner, both product declines, all seven vendor personal
initial states, scorable noncompletion, and actual image delivery. Record failed development checks
and their resolutions (e.g. Aside's valid JPEG vs an initially PNG-only test assertion).

## Commands

From a clean frozen benchmark checkout, after no-model validation:

```sh
uv run --locked python scripts/run-expanded-four-way.py plan
uv run --locked python scripts/run-expanded-four-way.py preflight \
  --out artifacts/codex-expanded-four-way-v1
uv run --locked python scripts/run-expanded-four-way.py run \
  --out artifacts/codex-expanded-four-way-v1 --limit 8
# Review all first-eight evidence and record the matching audit before continuing.
uv run --locked python scripts/run-expanded-four-way.py run \
  --out artifacts/codex-expanded-four-way-v1
uv run --locked python scripts/run-expanded-four-way.py analyze \
  --out artifacts/codex-expanded-four-way-v1
```

The analyze command is offline. Raw logs, screenshots, trial identifiers and session files remain
private artifacts; only reviewed summaries and source/test/protocol files are committed.
