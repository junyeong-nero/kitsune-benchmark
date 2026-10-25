# Results by Kitsune version

[Documentation index](../README.md) · [All result reports](README.md)

The same reports as the [dated list](README.md), grouped by the Kitsune source
each run used. Revisions come from each report and its `kitsune_source`
artifact; `git describe` is relative to the
[Kitsune tags](https://github.com/junyeong-nero/kitsune/tags). Reports within
one version still differ in model, harness, tasks and tool policy, so they are
not one leaderboard. Comparing across versions only isolates the Kitsune change
when model, harness and tasks match.

| Kitsune | Revisions | Reports |
| --- | --- | --- |
| **v0.4.1** | `83acfe9` (tag) | Subscription full suite + coexistence (2026-10-25), completed after startup correction and one explicit setup retry; earlier incomplete attempt retained |
| v0.4.0 | `a03df44` (tag) | Opus full suite + coexistence (2026-10-24; API harness) |
| v0.3.1 | `4ad65ee` (tag) | Opus full suite (2026-10-23; `taskset-v1.2`) |
| v0.3.0 | `99a90d2` (tag); `d616c50` = v0.3.0 + docs/agents only (`server.py` comment change) | Opus full suite (2026-10-23; `taskset-v1`), 2026-10-22 rerun, disclosure, target view, Sonnet/Opus, integrated startup, tool usage |
| v0.2.1 → v0.3.0 (main) | `9d36c57`, `1045a5e`, `cf24851`, `56bd5d9`, `753406b` | 2026-10-21 personal 24, token efficiency, gallery |
| v0.1.0 → v0.2.0 (main) | `967dfdf`, `68f7e97` | 2026-10-18 smoke and MiniWoB, 2026-10-19 personal pilots |

No report ran on exactly the v0.1.0, v0.2.0 or v0.2.1 tags.

## Frozen taskset

Version comparisons only mean something on an unchanged taskset. Tasksets are
git tags of this repository:

| Tag | Change | Reports |
| --- | --- | --- |
| `taskset-v1` (`f1ff9fa`) | First freeze | 2026-10-23 Opus full suite |
| `taskset-v1.1` | Requests of `pb-research-02` (both evidence links) and `pb-account-03` (overlapping titles only) now state what their graders check. Graders, fixtures and gallery unchanged | None |
| **`taskset-v1.2`** (current) | Harness only, for Kitsune v0.3.1's Playwright-named core tools: both targets get the same allowlist, Playwright MCP 0.0.83's 25 default tools minus `browser_evaluate` and `browser_run_code_unsafe` (23). Setup reads Kitsune's index-addressed `browser_tabs` (`current` = Playwright's `(current)`). Tasks, graders and fixtures as v1.1 | Opus full suite on v0.3.1 |
| `taskset-v2` (pending tag) | Three changes vs v1.2. (1) #8: `pb-research-02` asks for the actual Saturday operating hours as an interval, "실제 운영 시간(시작–종료)", and its memo field is renamed `개장 시간` → `운영 시간`; the `Hours` grader still requires both times. (2) #9: ownership-aware cleanup (`contracts.v2_agent_tab_cleanup`) is the primary `task_success`/`safety_pass` in personal and gallery evaluations (`benchmark` and config ids `personal-browsing-local-v2`, `component-gallery-v2`) and the base of the coexistence v3 contracts. It follows each starting tab by identity (`seeded_tab_custody`, from the relay's new `tab_calls` record), so closing an original or navigating it to another URL fails, even if refused and even while a duplicate stays open; a reload is allowed and counted. Custody is `kept`, `violated` (with separate `attempted` and `lost`) or `unknown` (ambiguous alignments, misaligned call records, alignment budget); unknown is neither a violation nor unscorable, leaves a functional success without a primary verdict (`null`) and is counted as `custody_unknown`. Strict v1 stays in `contracts.v1_strict_close` with its URL rule, and `close_only_failure` marks a functionally successful v2 pass that v1 failed only for closing a tab; summaries add `successes_v1_strict_close`, `safety_failures_v1_strict_close`, `v1_close_only_failures` and `functional_successes`. (3) #10: gallery `mm-text` (distorted, CAPTCHA-like code) is replaced by `mm-label` (serial number on a product-label photo), and gallery evaluations add `failure_class`. Harness as v1.2; the relay only adds the hidden `tab_calls` record | None |

Earlier reports predate the tags and ran on earlier task/grader code. Scores on
v1 and v1.1 are not compared directly: the two personal tasks changed their
requests, so their recorded v1 notes cannot be re-graded as v1.1 answers.
Likewise v1.x and v2 scores are never compared directly: v2 changes a request,
the primary safety rule and one gallery task. Rerun every Kitsune version being
compared on `taskset-v2`. A v1.x report's `task_success` is strict v1; a v2
report's is ownership-aware v2, with strict v1 under `contracts`.
Pair manifests record `benchmark_source.taskset` (e.g. `taskset-v1.1-2-gabc1234`;
a `-dirty` suffix means uncommitted changes).

Frozen in each taskset tag:

- Personal: `tasks/personal/catalog.json`, `kitsune_benchmark/personal_fixtures.py`,
  `personal.py` and `personal_session.py` (fixtures, variants and graders).
- Gallery: `kitsune_benchmark/gallery.py`, `gallery_static/`, `gallery_media.py`.
- MiniWoB: `configs/benchmarks/miniwob.json` (upstream revision, task, seed).
- Harness: Claude Code `2.1.303`, Playwright MCP `0.0.83`, UI tool allowlists,
  per-run timeouts in `configs/benchmarks/`.

Rules:

- Do not change frozen files on `main` for a v1 run. A grader bug fix becomes
  `taskset-v1.1`; rerun the Kitsune versions being compared on it, and never
  compare scores across taskset versions.
- Model, effort and per-run cap may vary per run (`--claude-model`,
  `--max-budget-usd-per-run`); report them, and compare versions only at the same
  model.
- Each report names its taskset tag next to the Kitsune revision.
- A full-suite run on one Kitsune revision is an **observation**. It can
  motivate a `hypothesis` issue but is not that hypothesis's baseline: baseline and candidate are re-run together on the same
  taskset tag, model, attempts and counterbalanced order. A reproducible Kitsune
  failure (same task failing on every variant) is filed as a Kitsune `bug`, and a
  grader or fixture defect as a taskset change here.

### Upgrading with the next Kitsune release

v1 has a ceiling: Haiku already reaches 23/24 personal and 21/21 isolated gallery,
and there is one attempt per task in a fixed order. `taskset-v2` (above) only
bundles the validity fixes of #8, #9 and #10. The harder taskset planned here
moves to a later version, provisionally `taskset-v3`:

1. Run the new release on the current taskset first, for continuity with this table.
2. Freeze `taskset-v3` (harder tasks, repeated trials, counterbalanced order).
   The draft [coexistence track](../coexistence.md) is its candidate content for
   Kitsune's own promises: user-owned seeding and view telemetry over the personal
   tasks, a typing user, and specified delegation/recovery tasks. It imports the
   personal fixtures, graders and relay without changing them. `smoke.run_pair` gained
   opt-in `kitsune_env`/`kitsune_firefox_args`/`kitsune_firefox_prefs` arguments
   whose defaults leave every v1 launch unchanged.
3. Run both the previous release and the new one on the new taskset, so it has
   its own baseline.

Steps 1 and 3 are observations; a claim that the release is better on some metric
still goes through a `hypothesis` issue.

## v0.4.1

`83acfe92272cd5bb0909785d7d821d05136710d0`. Checkbox/core capability and early-refusal
fixes (#242), collapsed-row reachability (#243), selector forms (#245). Subscription
results below are a separate cohort, **not** a version-performance comparison
with the earlier API cohort. The first attempt's startup problem was corrected
by forcing blocking MCP connection in the benchmark harness.

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-25 | [Full suite + coexistence, subscription](2026-10-25-opus-subscription-v0.4.1.md) | `claude-opus-5-5`, Claude Code subscription | `83acfe9` (`v0.4.1`) | 448 selected scorable runs after one explicit setup retry; personal 72/72 PW vs 69/72 K (v2 both 72/72), crowded both 63/63, isolated 63/63 vs 62/63; coexistence v3 view 2/24 vs 23/24 |
| 2026-10-25 | [Subscription attempt — incomplete](2026-10-25-opus-subscription-v0.4.1-incomplete.md) | `claude-opus-5-5`, Claude Code subscription | `83acfe9` (`v0.4.1`) | Personal v0: PW 24 successes; Kitsune 2 successes + 1 unscorable, then stopped. MCP still pending with no tools at inference start; no full-suite score |

## v0.4.0

`a03df442f92d74de47d0c500de2b625d34765e27`. Snapshot text/link URLs restored, Playwright selector forms,
hover scroll (#226); capability groups regrouped (#228); tool gateway (#229); `KITSUNE_CAPS` enforced on
bridge routes (#231); tab-less tools run on the current tab (#233).

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-24 | [Opus full suite + coexistence](2026-10-24-opus-full-v0.4.0.md) | `claude-opus-5-5`, Claude Code API bare | `a03df44` (`v0.4.0`) | `taskset-v1.2` (upgrade step 1); personal 72/72 vs 69/72, gallery crowded 63/63 vs 62/63, isolated 62/63 vs 60/63 (Playwright vs Kitsune); `fill_form` checkbox regression; coexistence v3 user view 2/24 vs 23/24 |

## v0.3.1

`4ad65ee5023803a1757541dacafcd049ebf6fa9f`. Publishes Playwright MCP 0.0.83's 25 default tools under
their names and schemas; tool presets removed.

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-23 | [Opus full suite](2026-10-23-opus-full-v0.3.1.md) | `claude-opus-5-5`, Claude Code API bare | `4ad65ee` (`v0.3.1`) | `taskset-v1.2`; personal 72/72 vs 71/72, gallery crowded 63/63 vs 61/63, isolated 62/63 vs 60/63 (Playwright vs Kitsune) |
| 2026-10-23 | [Coexistence draft](2026-10-23-coexistence-user-seeded.md) | `claude-opus-5-5`, Claude Code API bare | `4ad65ee` (`v0.3.1`) | Draft track (not a taskset tag): user-seeded personal v1 24/24 both, v3 user view 2/24 vs 24/24; `co-typing-01` 87 vs 0 misdirected keystrokes |

## v0.3.0

`99a90d22c83d6e931814b3c3dadd96c08c633820`, default tool preset **lean** (14 tools).

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-23 | [Opus full suite](2026-10-23-opus-full-v0.3.0.md) | `claude-opus-5-5`, Claude Code API bare | `d616c50` (`v0.3.0-4`) | `taskset-v1`; personal 67/72 vs 68/72, gallery crowded 63/63 vs 60/63, isolated 63/63 vs 57/63 (Playwright vs Kitsune) |
| 2026-10-22 | [Tool usage inventory](2026-10-22-tool-usage.md) | Offline | v0.3.0 | 196 existing v0.3.0 runs |
| 2026-10-22 | [Sonnet / Opus targeted follow-up](2026-10-22-sonnet-opus-target-view.md) | Sonnet 5.5 / Opus 5.5, API bare | `99a90d2` | 16 runs, lean |
| 2026-10-22 | [Target/action view A/B](2026-10-22-target-view-ab.md) | Haiku 5.5, API bare | `99a90d2` | 60 runs |
| 2026-10-22 | [Disclosure × expect A/B](2026-10-22-disclosure-ab.md) | Haiku 5.5, API bare | `99a90d2` | 72 Kitsune-only runs |
| 2026-10-22 | [Integrated Opus startup](2026-10-22-integrated-startup.md) | Opus 5.5, API | `99a90d2` | Harness-error diagnostic, not a score |
| 2026-10-22 | [Kitsune 0.3.0 rerun](2026-10-22-kitsune-0.3.0.md) | Haiku 5.5, API bare / full | `99a90d2` | Personal 24; compares against `1045a5e` |

## v0.2.1 → v0.3.0 (pre-release main)

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-21 | [Component gallery](2026-10-21-gallery.md) | Haiku 5.5, API | `56bd5d9` (`v0.2.1-134`) | No-model re-check of failures on `753406b` (`v0.2.1-164`) |
| 2026-10-21 | [Token efficiency analysis](2026-10-21-token-efficiency.md) | Haiku 5.5, API bare | `1045a5e` pairs 1–16, `cf24851` pairs 17–24 (`v0.2.1-132/133`) | Checkout moved mid-suite; led to the revision guard |
| 2026-10-21 | [All 24 personal tasks](2026-10-21-personal-24-claude-haiku.md) | Haiku 5.5, Claude Code subscription | `9d36c57` (`v0.2.1-37`) | |

## v0.1.0 → v0.2.0 (pre-release main)

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-19 | [Six-task personal pilot](2026-10-19-personal-six-task.md) | `gpt-6-luna`, Codex | `68f7e97` (`v0.1.0-5`) | |
| 2026-10-19 | [Personal current-page pair](2026-10-19-personal-current-page.md) | `gpt-6-luna`, Codex | `68f7e97` (`v0.1.0-5`) | |
| 2026-10-18 | [MiniWoB++ pilot](2026-10-18-miniwob.md) | `gpt-6.1-sol`, Codex | `967dfdf` (`v0.1.0-2`) | |
| 2026-10-18 | [Read-only smoke](2026-10-18-smoke.md) | `gpt-6.1-sol`, Codex | `967dfdf` (`v0.1.0-2`) | |

## Adding a report

Record the full Kitsune revision and `git -C <kitsune> describe --tags` in the
report, then add a row under that version. `scripts/run-full-suite.py` writes both
to `suite-manifest.json`.
