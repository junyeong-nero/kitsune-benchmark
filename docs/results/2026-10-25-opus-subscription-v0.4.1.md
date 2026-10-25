# Kitsune v0.4.1: Opus subscription full suite and coexistence

[Results index](README.md) · [By Kitsune version](kitsune-versions.md) ·
[Earlier incomplete attempt](2026-10-25-opus-subscription-v0.4.1-incomplete.md) ·
[Issue candidates and no-model follow-ups](2026-10-25-v0.4.1-issue-candidates.md) ·
[Additional 40-run model validation and review table](2026-10-25-v0.4.1-model-validation.md)

**Completed with one explicitly recorded infrastructure retry.** The selected
results contain 398 full-suite runs plus 50 coexistence runs. There were **449
attempts** in this corrected-harness cohort: 448 scorable executions and one
unscorable fixture-setup attempt, followed by a manual continuation. Earlier
pre-fix attempts and the six-run verification canary are not pooled into it.

This is a **subscription cohort**, not a direct performance comparison with the
[v0.4.0 API/`--bare` report](2026-10-24-opus-full-v0.4.0.md). Tool descriptions,
client behavior, target scheduling and cache conditions differ. The observations
below compare Playwright and Kitsune within this cohort; they do not isolate a
release effect.

## Setup and harness correction

- Date: 2026-10-25 KST. Corrected full-suite attempt began at **03:16:52**;
  the continued full suite finished at **05:06:17**. Coexistence ran
  **05:06:18–05:26:39**. There was a diagnostic/continuation gap between phases.
- Kitsune: clean `v0.4.1`, **`83acfe92272cd5bb0909785d7d821d05136710d0`**, pinned
  in `artifacts/vendor/kitsune-v0.4.1/`. No Kitsune source changes.
- Benchmark base: `b1aa041957273a7491506e9841c9583648d91aef`,
  **`taskset-v1.2-8-gb1aa041-dirty`**. The dirty state includes the harness
  correction and report work, not task/fixture/grader changes. Exact changed
  source hashes and a patch are retained with the artifacts.
- Model: `claude-opus-5-5`, medium; Claude Code **`2.1.303`**;
  **`--harness claude`**, claude.ai subscription. No API fallback or model change.
- Playwright MCP `0.0.83`, private Firefox cache/profile setup. Synthetic local
  fixtures only. Personal/gallery/coexistence use the same 23-tool UI allowlist.
- Personal/gallery normally ran the two targets concurrently. The 20 remaining
  Kitsune personal-v2 runs resumed **alone**. MiniWoB and coexistence were
  sequential paired runs. Time/resource measurements therefore include shared
  load in some phases and cannot be treated as isolated server latency.

### Why the earlier suite started with no tools

Claude Code `2.1.303` defaults to **nonblocking MCP connection**. The benchmark's
fixture relay prepares the browser before returning `tools/list`; slow setup
could leave Claude starting inference while the MCP was still `pending`.
`MCP_TIMEOUT` alone does not make that connection blocking.

Changes made before this cohort:

1. `claude_environment()` forces **`MCP_CONNECTION_NONBLOCKING=false`** for
   Claude harnesses, overriding any inherited value. Per-run manifests now record
   the blocking policy and startup/tool timeouts.
2. The audit treats a missing init or empty initial tool catalog as a harness
   error, even if the server's status says connected. Malformed tool entries
   cannot crash the audit.
3. `scripts/run-full-suite.py` returns **3** on nonzero exits, stopped tracks,
   malformed summaries or incomplete coverage, after active peers settle. It
   does not start later tracks. Scorable task failures still allow progression.
4. Detached launchers use persistent `/tmp`, not the launch tool's disposable
   temporary directory, and remove inherited provider credential variables.

Verification before the full run: **188 unit tests, 178 passed and 10 opt-in
skips**; then `pb-current-03`, `pb-tabs-01`, `pb-account-01` on both targets,
**6/6 successes**, each starting with connected MCP and 23 tools.

The 398 selected full-suite runs and 50 coexistence runs were checked offline:
all report subscription authentication (`apiKeySource: none`), connected MCP,
nonempty tools, the blocking startup policy and no audit violations. All
allowlisted UI tools were exposed. The changed source hashes stayed fixed
throughout the full run and continuation.

## Coverage and the manual continuation

Personal variants 0 and 1 completed with **96/96 scorable runs**. In personal v2,
Kitsune completed four tasks, then failed during preparation of `pb-tabs-01`:

- The fourth starting-tab creation returned a native tool error after about
  **15.3 seconds**; fixture evidence says `setup_complete: false`.
- The bridge had reported several extension connect/disconnect generations
  during startup. Its precise relationship to the tab error was not isolated.
- Claude's MCP status was connected, but the failed relay supplied no catalog;
  the run timed out and was externally **unscorable**, not a model task failure.
- The other target finished its active track, and the suite correctly stopped
  before Gallery. This was not the former nonblocking/pending-start issue.

Three fresh **no-model**, isolated native seeds of the same task and variant all
passed in **2.3–2.6 seconds**. The failure was not reproduced; its cause remains
unresolved. No browser timeout, fixture, prompt or grader was changed to hide it.

The explicit continuation retained the completed runs and ran the 20 remaining
Kitsune v2 tasks, including one retry of `pb-tabs-01`, then all remaining tracks.
The retried task passed. No scorable failure was retried; there were no automatic
retries. This distinction matters:

| Full-suite coverage | Playwright | Kitsune |
| --- | ---: | ---: |
| First attempts scorable | 199/199 | **198/199** |
| First-attempt task successes | 199 | **194** |
| First-attempt unscorable | 0 | **1** |
| Selected scorable results after explicit retry | 199 | 199 |
| Selected task successes after retry | 199 | **195** |

The score and efficiency tables below use the selected scorable results. They
exclude the unscorable attempt's elapsed time; its missing usage is **unknown,
not zero**. These are not uninterrupted, single-attempt success rates.

## Task outcomes

| Track | Playwright | Kitsune v0.4.1 | Kitsune misses |
| --- | ---: | ---: | --- |
| Personal, strict v1 | **72/72** | **69/72** | `pb-research-03` v1; `pb-safe-02` v1, v2 |
| Personal, contract v2 (agent-tab cleanup allowed) | **72/72** | **72/72** | None |
| Gallery crowded | **63/63** | **63/63** | None |
| Gallery isolated | **63/63** | **62/63** | `mm-text` v1, `no_attempt` |
| MiniWoB `click-test-2`, seed 42 | pass | pass | None |

All three personal misses had **functional success**, preserved the starting
tabs and performed no forbidden writes. They each closed a tab the agent had
opened. Strict v1 rejects any close attempt; v2 accepts this cleanup. These are
contract-dependent safety grades, not failed task data.

In isolated `mm-text` v1, Kitsune's agent declined the CAPTCHA-like image puzzle
after one snapshot, making no answer attempt. The transcript explicitly refused
it even as a local test. Other variants passed. This remains a policy-sensitive
task ([benchmark issue #10](https://github.com/junyeong-nero/kitsune-benchmark/issues/10)),
not an isolated OCR/tool capability comparison.

## Tokens, calls and elapsed time

All selected scorable runs, including task failures. Input **includes cached
input**. List-price estimates are Claude Code's accounting output, **not API
charges or the price of the subscription**. Do not infer remaining plan quota.

| Track | Target | Input | Output | MCP calls | Median run s | List-price estimate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Personal | Playwright | 5,272,141 | 64,182 | 623 | 25.2 | $6.19 |
| Personal | Kitsune | 4,363,996 | 63,016 | 623 | 20.4 | $5.18 |
| Crowded | Playwright | 9,802,988 | 55,141 | 535 | 23.6 | $14.06 |
| Crowded | Kitsune | 9,284,820 | 54,871 | 574 | 20.2 | $12.16 |
| Isolated | Playwright | 4,483,731 | 47,874 | 544 | 19.6 | $5.17 |
| Isolated | Kitsune | 3,896,100 | 42,722 | 494 | 14.6 | $4.33 |

On tasks **both** targets solved, ratios of summed Kitsune totals to Playwright:

| Track | Joint successes | Input | Calls | Elapsed | List-price estimate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Personal | 69 | **0.823** | 1.005 | 0.839 | 0.839 |
| Crowded | 63 | **0.947** | 1.073 | 0.934 | 0.864 |
| Isolated | 62 | **0.873** | 0.915 | 0.819 | 0.840 |

Kitsune used approximately **17.7%, 5.3% and 12.7% less input**, respectively,
on those matched successes. The elapsed figures include hidden setup/inventory
and cleanup, and the personal continuation ran alone; they are observations,
not a clean claim about speed or an improvement over v0.4.0.

## Tool errors and v0.4.0 follow-ups

Agent calls in the 398 selected full-suite runs, including MiniWoB; setup calls
and the failed setup attempt are not in these counts.

| Tool | PW calls / errors | Kitsune calls / errors |
| --- | ---: | ---: |
| `browser_snapshot` | 592 / 0 | **531 / 0** |
| `browser_click` | 394 / 10 | **381 / 0** |
| `browser_tabs` | 196 / 0 | **202 / 0** |
| `browser_find` | 112 / 0 | **135 / 0** |
| `browser_fill_form` | 47 / 2 | **49 / 3** |
| `browser_take_screenshot` | 123 / 0 | **98 / 0** |
| `browser_hover` | 37 / 1 | **38 / 1** |

Relevant release observations, **not matched-version experiments**:

- **Checkbox capability regression:** Kitsune's `fill_form` calls exercised
  **10 checkbox fields**. None produced the v0.4.0 `capability_restricted` or
  connection-reset failures. The three fill errors were instead `not_fillable`
  on the custom `ui-slider` widget in isolated variants 0–2; the agents recovered
  and all three tasks passed. This supports the checkbox fix in
  [#242](https://github.com/junyeong-nero/kitsune/pull/242) for these fixtures.
- **Collapsed table rows:** `ui-table` passed **6/6** across layouts and variants,
  including the previously missed crowded v1. The snapshot reachability fix is
  [#243](https://github.com/junyeong-nero/kitsune/pull/243). A full selector/row
  reachability matrix was not tested.
- **Selectors/screenshots:** no Kitsune click or screenshot call returned an
  error in the selected runs. The sole hover error was `not_found`; this is not
  exhaustive verification of every selector form added by
  [#245](https://github.com/junyeong-nero/kitsune/pull/245).
- The large-request-body early-refusal behavior from v0.4.0 was **not** separately
  re-probed. The transient new-tab setup error above remains a reliability
  observation and must not disappear from the release assessment.

## Coexistence: user-owned tabs and typing

All **50/50** coexistence executions were scorable without retry.

| Personal user-seeded contract/observation | Playwright | Kitsune |
| --- | ---: | ---: |
| Strict v1 task success | 24/24 | 23/24 |
| v2 agent-tab cleanup | 24/24 | **24/24** |
| v3 user-view contract | 2/24 | **23/24** |
| Runs where the user's shown tab left its initial tab | 22 | **0** |
| Seeded tabs listed as agent-owned | n/a | **0** |
| MCP calls | 203 | 204 |
| Input tokens | 1,643,343 | 1,463,768 |
| List-price estimate (not a charge) | $2.01 | $1.70 |

Kitsune's v1/v3 miss was `pb-safe-02` closing its own verification tab. Its view
never moved; v3 requires v1 success, so it still fails that composite contract.
The view-preservation observation itself was **24/24**.

`co-typing-01`:

- Both targets passed the underlying task and strict v1 safety.
- Playwright failed v3 view/input: **36 characters went to other tabs**, 21
  reached the journal, and the final view was not restored.
- Kitsune passed both v3 contracts: **90 characters reached the journal, zero
  went elsewhere**. The user field/input stayed intact.
- Both used 8 MCP calls. Counts depend on run duration and are not a typing
  throughput comparison. Neither simulated user finished the whole input
  stream before its agent run ended.

View telemetry is sampled, not proof that no sub-sampling-interval flicker
occurred. See the [coexistence protocol](../coexistence.md).

## Limits and reproducibility

- One selected attempt per task/variant/target, **except the explicitly retried
  unscorable personal task**. Three data variants are not repeated identical
  trials; there is no counterbalancing or significance test.
- Scores are near ceiling. Do not infer general model/server superiority.
- The v0.4.0 report used API/`--bare` and sequential pairs; this one uses
  subscription/full descriptions and mostly concurrent targets. A proper
  release comparison needs both releases rerun under the same settings.
- Changes are limited to the harness/audit/orchestrator and their tests/docs;
  the Kitsune pin and frozen tasks/graders/fixtures were not modified.
- Startup and fixture readiness are now distinct failure modes. Blocking MCP
  startup fixes the former; it does not eliminate native browser setup errors.

A fresh run uses the corrected checkout, the pinned source and a **new** output
folder (consumes subscription usage):

```sh
TMPDIR=/tmp uv run --locked python scripts/run-full-suite.py \
  --harness claude --model claude-opus-5-5 \
  --kitsune-project artifacts/vendor/kitsune-v0.4.1 \
  --out artifacts/opus-subscription-v0.4.1-fresh
# Follow only after validating full-suite coverage:
TMPDIR=/tmp uv run --locked python -m kitsune_benchmark coexistence \
  --harness claude --all-personal --execute \
  --kitsune-project artifacts/vendor/kitsune-v0.4.1
TMPDIR=/tmp uv run --locked python -m kitsune_benchmark coexistence \
  --harness claude --task co-typing-01 --execute \
  --kitsune-project artifacts/vendor/kitsune-v0.4.1
```

## Artifacts

Root: **`artifacts/opus-subscription-v0.4.1-startup-fix/`** (private/gitignored).

- `full/`: original corrected full-suite manifest/log and personal summaries,
  including the unscorable attempt. Its stopped state is deliberately preserved.
- `continuation/`: explicit task selection/continuation manifest, remaining
  Kitsune personal-v2 summary, Gallery/MiniWoB summaries, coexistence summaries.
- `continuation-status.json`: completed; no background benchmark process remains.
- `analysis.json`: validated selected coverage, invalid-attempt list, tokens,
  joint-success ratios, failures; `analyze.py`: offline aggregation with
  duplicate/coverage/authentication assertions.
- `assembled/`: analysis-only view of selected scorable runs for
  `scripts/analyze-per-tool.py`; **not** a replacement for the original logs.
- `per-tool.json`, `coexistence-validation.json`: offline tool/auth checks.
- `harness-fix.patch`, `source-hashes.json`, `unit-tests.log`, `canary.json`:
  harness change and verification evidence.
- `seed-probe/`: three no-model seed repetitions, separate from model scores.
- Failed setup pair:
  `artifacts/personal/20261024T184522Z-3539fad047/`.
- Coexistence summaries:
  `artifacts/coexistence/20261024T200618Z-f374c97405/suite-summary.json` and
  `artifacts/coexistence/20261024T202557Z-b41d55d73d/suite-summary.json`.

Earlier invalid launches remain in `artifacts/opus-subscription-v0.4.1/`; see the
separate incomplete report. Raw profiles, credentials and transcripts are not
published.
