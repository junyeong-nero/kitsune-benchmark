# Kitsune Benchmark

Compare **Playwright MCP vs Kitsune MCP** on everyday browser tasks, using a
fixed Codex/model configuration, external task evidence, token usage and local
CPU/RAM measurements.

**Start here:** [Documentation](docs/README.md) · [Running guide](docs/running.md) ·
[Personal browsing taskset](docs/personal-browsing.md) · [Results](docs/results/README.md)

## Current focus and status

Latest release check: [Kitsune v0.7.0 on Opus subscription, full suite + coexistence](docs/results/2026-10-26-opus-subscription-v0.7.0.md),
the first `taskset-v3` cohort: 480 scorable runs, no retries (422 `taskset-v3` runs plus 58 pre-freeze coexistence-draft runs). Personal: Playwright
83/84 vs Kitsune 84/84; crowded gallery 63/63 vs 62/63, isolated both 63/63. On
joint successes Kitsune used 19% / 16% / 5% less input at about the same call count.
Not comparable with the earlier v1.x/v2 reports.

The primary track evaluates **personal browsing**: continuing work in existing
tabs and a pre-established test session, gathering information, transferring it
to drafts, and respecting do-not-submit/preserve-context boundaries.

| Track | Implemented scope | Actual model evidence |
| --- | --- | --- |
| **Personal browsing** | 28 original specifications, **all runnable** local tasks (six-task pilot default, `--all` for 28); three data variants each; frozen as `taskset-v3` | Opus subscription on Kitsune v0.7.0, 28 × 3 (2026-10-26): 83/84 Playwright, 84/84 Kitsune ([report](docs/results/2026-10-26-opus-subscription-v0.7.0.md)). Earlier: 24 variant-0 Haiku pairs 21/24 vs 23/24; six-task Codex pilot 3/6 vs 4/6 |
| **Coexistence** (frozen `coexistence-local-v1`, `taskset-v3.1`) | The user is in the browser too: user-owned starting tabs, view telemetry, a typing user ([protocol](docs/coexistence.md)). 28 personal tasks user-seeded, the Kitsune `protect-user-tabs` arm and `co-typing-01`; 25 more specified only | No frozen cohort yet. Pre-freeze draft on Kitsune v0.7.0, Opus subscription (2026-10-26): v2 28/28 both, v3 user view 2/28 Playwright vs 28/28 Kitsune, `co-typing-01` 48 vs 0 misdirected characters ([report](docs/results/2026-10-26-opus-subscription-v0.7.0.md)) |
| **External** (`external-v1`) | 7 pinned MiniWoB++ tasks graded by the upstream reward (incl. a `login-user` form) + 3 live public-web tasks (Steam, Wikipedia, MDN), recorded but never graded ([protocol](docs/external.md)) | No full cohort yet. Earlier one-task pilot (`click-test-2` only): both passed in every full-suite report |
| Read-only smoke | Example Domain, no external task-success grader | One completed historical `gpt-6.1-sol` pair on 2026-10-18 |

Execution defaults to **Claude Code `2.1.303` on the claude.ai subscription** (`--harness claude`; no API credit). API-key billing needs `--harness claude-api --allow-api-billing`. The Codex harness (`gpt-6-luna`, Codex CLI `0.163.0`) remains available.
Subscription runs consume plan usage, not API credit, and have no dollar cap; there is
never an API-key fallback. See the [running guide](docs/running.md#default-harness-claude-code-on-the-subscription).

The [six-task report](docs/results/2026-10-19-personal-six-task.md) records all
12 agent runs. Kitsune's total input was only 0.61% higher, while its raw elapsed
was 8.77% higher; a no-model intervention identified stale tab-list cache polling
as a major setup delay. See [optimization findings and logs](docs/optimization-findings.md).
This is one fixed-order variant, **not a general ranking**; strict output-format
and tab-preservation grading affect scores. The [first one-task report](docs/results/2026-10-19-personal-current-page.md)
remains a separate historical experiment.

## Setup

Requires Python 3.11+, uv, Node/npm, a supported Codex ChatGPT login and the
Kitsune source checkout (normally sibling `../kitsune`).

```sh
uv sync --locked
npm ci --ignore-scripts --no-audit --no-fund
npm run setup:firefox
```

npm pins Playwright MCP `0.0.83` and web-ext `10.8.0`; Python uses locked psutil.
Firefox is installed in a **private cache with shared-cache GC disabled**.
Automated paired commands use the same private Firefox binary, separate fresh
profiles and private Kitsune bridge ports. No everyday Firefox/Zen profile or
real personal account is connected. Personal fixtures preload synthetic tabs,
data and test-session cookies before agent tool use.

## Start small

```sh
# CLI/version/login diagnostics only; no inference.
uv run --locked python -m kitsune_benchmark doctor --json

# Plan one personal task pair; no browser or model calls.
uv run --locked python -m kitsune_benchmark personal --task pb-current-01 --variant 0

# Explicitly consumes subscription usage: at most two agent runs.
uv run --locked python -m kitsune_benchmark personal \
  --task pb-current-01 --variant 0 --execute
```

A separately budgeted six-task pilot is `personal --execute` (**up to 12 agent
runs**, not all 28 specs). Do not start it just to inspect configuration.
Use `--kitsune-project` or `--codex` for non-default paths. See the
[running guide](docs/running.md) for track commands, input validation, quota,
stopping behavior, exit codes and evidence inspection.

## Tests

```sh
# No real model calls. Native browser integration tests are opt-in.
uv run --locked python -m unittest discover -s tests -v

# Real native MCP/Firefox fixture tests, still no model inference.
PERSONAL_BROWSER_TEST=1 PERSONAL_KITSUNE_TEST=1 \
  uv run --locked python -m unittest discover -s tests -p 'test_personal.py' -v

# Coexistence user channel (WebDriver BiDi) through both real MCP servers; no model.
PERSONAL_BROWSER_TEST=1 PERSONAL_KITSUNE_TEST=1 \
  uv run --locked python -m unittest discover -s tests -p 'test_coexistence.py' -v
```

## Layout and detailed docs

| Path | Purpose |
| --- | --- |
| `configs/benchmarks/personal.json` | Model/pins, default six-task pilot selection, time budget |
| `tasks/personal/catalog.json` | All 28 task specifications, implementation status and source references |
| `kitsune_benchmark/` | Codex execution/audit, paired lifecycle, fixtures, evaluators and resource collection |
| `artifacts/` | Private, gitignored raw evidence and browser/vendor resources |
| [Documentation index](docs/README.md) | Guide map, track status and source-of-truth boundaries |
| [Results by Kitsune version](docs/results/kitsune-versions.md) | Reports per Kitsune revision, frozen `taskset-v1` and upgrade rules |
| [Personal protocol](docs/personal-browsing.md) | Catalog, session/reset setup, state-based grading and provenance |
| [Coexistence track](docs/coexistence.md) | Frozen `coexistence-local-v1`: user channel, v3 contracts, run plan, comparability; delegation/recovery specs |
| [Codex harness](docs/codex-harness.md) | Authentication, tool policy, generic runs and process cleanup |
| [Resource methodology](docs/resources.md) | CPU/RSS scope, attribution and sampling caveats |
| [Optimization findings](docs/optimization-findings.md) | Evidence-backed cache/observation/schema targets, RPC logs and offline analysis |
| [External track](docs/external.md) | `external-v1`: 7 MiniWoB++ tasks (upstream reward) + 3 ungraded live-site tasks |
| [MCP candidates](docs/comparison-candidates.md) | Future server/browser cohorts, not implemented benchmark adapters |

## Interpretation and safety

- The evaluation unit is **model + Codex + MCP configuration**, not an intrinsic
  model/server score. Current reports are fixed-order, single-attempt pairs.
- Read external `scorable` and `task_success`, not just exit status or the final
  chat answer. Generic `completed_unscored` and an external success can coexist.
- Input usage **includes cached input**. Do not add cached tokens again or infer
  subscription charges/remaining quota from token counts.
- Personal elapsed time includes hidden setup/readiness/inventory calls;
  these are counted separately from agent calls. Startup asymmetry, cache effects
  and effective viewport equivalence outside the personal track's measured
  runs (gallery and coexistence are equalized by construction but unmeasured)
  remain confounders.
- Local summed RSS is not unique physical memory; remote inference is not measured.
- The personal catalog is newly authored with benchmark design references, not
  imported WebArena/WebVoyager/AssistantBench tasks or official upstream scores.
  All implemented apps are synthetic and local.
- MCP servers are trusted code. Codex's read-only workspace does not make browser
  mutations read-only. Use controlled test data; keep raw logs/profiles/tokens
  private and review/redact before sharing. User auth/config is never edited.

WebArena, live personal accounts, complete tool/prompt attestation, repeated and
counterbalanced statistics, and token-budget stopping remain future work.
