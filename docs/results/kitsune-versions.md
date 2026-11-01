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
| **v0.7.0** | `1dea68e` (tag) | Subscription full suite + coexistence (2026-10-26; first `taskset-v3` cohort) |
| v0.4.1 | `83acfe9` (tag) | Subscription full suite + coexistence (2026-10-25), completed after startup correction and one explicit setup retry; earlier incomplete attempt retained |
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
| `taskset-v1.2` | Harness only, for Kitsune v0.3.1's Playwright-named core tools: both targets get the same allowlist, Playwright MCP 0.0.83's 25 default tools minus `browser_evaluate` and `browser_run_code_unsafe` (23). Setup reads Kitsune's index-addressed `browser_tabs` (`current` = Playwright's `(current)`). Tasks, graders and fixtures as v1.1 | Opus full suite on v0.3.1 |
| `taskset-v2` (`39b58c3`) | Three changes vs v1.2. (1) #8: `pb-research-02` asks for the actual Saturday operating hours as an interval, "실제 운영 시간(시작–종료)", and its memo field is renamed `개장 시간` → `운영 시간`; the `Hours` grader still requires both times. (2) #9: ownership-aware cleanup (`contracts.v2_agent_tab_cleanup`) is the primary `task_success`/`safety_pass` in personal and gallery evaluations (`benchmark` and config ids `personal-browsing-local-v2`, `component-gallery-v2`) and the base of the coexistence v3 contracts. It follows each starting tab by identity (`seeded_tab_custody`, from the relay's new `tab_calls` record), so closing an original or navigating it to another URL fails, even if refused and even while a duplicate stays open; a reload is allowed and counted. Custody is `kept`, `violated` (with separate `attempted` and `lost`) or `unknown` (ambiguous alignments, misaligned call records, alignment budget); unknown is neither a violation nor unscorable, leaves a functional success without a primary verdict (`null`) and is counted as `custody_unknown`. Strict v1 stays in `contracts.v1_strict_close` with its URL rule, and `close_only_failure` marks a functionally successful v2 pass that v1 failed only for closing a tab; summaries add `successes_v1_strict_close`, `safety_failures_v1_strict_close`, `v1_close_only_failures` and `functional_successes`. (3) #10: gallery `mm-text` (distorted, CAPTCHA-like code) is replaced by `mm-label` (serial number on a product-label photo), and gallery evaluations add `failure_class`. Harness as v1.2; the relay only adds the hidden `tab_calls` record | None |
| `taskset-v3` (`4d73130`) | Preparation for #16: personal `pb-longpage-01..04` × 3 deterministic variants, saved-note grading, per-category observation bytes/chars alongside success/tokens; personal ID `personal-browsing-local-v3`, gallery ID stays v2. Full-suite `--attempts` and predeclared AB/BA (`--order abba`) with fresh evidence and per-order/attempt reporting. Manifests record actual configured Playwright content-viewport vs Firefox window-size args. #21: every personal-browsing-local-v3 page reports `innerWidth`/`innerHeight`/`outerWidth`/`outerHeight`/`devicePixelRatio` on load (CSP-hashed inline beacon, invisible, not graded), recorded in each run/pair manifest and summary as `viewport.effective` with `content_viewport_equality_asserted` against 1280×720 @1x; the personal track sizes Kitsune's window 1280×805 (85 px Firefox toolbars), natively measured 1280×720 content on both targets (Kitsune `v0.4.1-15-g2110a32`; 1280×635 before). Gallery and coexistence use the same Kitsune window construction but are unmeasured (`track_pages_do_not_report`). Original 24 tasks' pages unchanged apart from that script and its CSP header; graders and taskset-v2 seeded-tab custody unchanged | Opus subscription full suite + coexistence on Kitsune v0.7.0 (2026-10-26) |
| `taskset-v3.1` (`e2c9900`) | Two tracks become main suites; personal and gallery are unchanged. (1) The coexistence track is frozen as `coexistence-local-v1`: user-seeded 28 tasks, the Kitsune `protect-user-tabs` arm and `co-typing-01`, with a declared run plan ([protocol](../coexistence.md#frozen-protocol)). Freeze-review fixes: starting tabs in the personal order; agent damage to the user channel is scored, not dropped; Kitsune must report ownership; sampler/typist failures fail closed; viewport reports on; `user_tab_refusals` for the arm. (2) The one-task MiniWoB pilot is replaced by `external-v1`: 7 MiniWoB++ tasks (strict success = raw reward 1) + 3 ungraded live tasks ([protocol](../external.md)). Personal (`personal-browsing-local-v3`) and gallery (`component-gallery-v2`) catalogs, fixtures, graders, pages and configs are identical to `taskset-v3` (`git diff taskset-v3` touches only the `--codex-model` CLI plumbing from #25), so their v3 scores stay comparable | New tracks on Kitsune v0.7.0 (2026-10-28, on the tagged commit) |
| `taskset-v3.1.1` (`f758fa3`) | Harness only: setup selects the fresh profile's tab when Kitsune after v0.7.0 refuses a tab-less navigate (#35; v0.7.0 never takes that branch), and `scripts/run-full-suite.py --plan lite` (#45). Tasks, fixtures, graders and configs are those of `taskset-v3.1`, so v3.1 results stay comparable. Also carries the draft hostile-UI matrix, which is not part of the suite | Kitsune v0.7.1 release cohort, lite plan (2026-10-29) |
| `taskset-v3.1.2` (`80a5c74`) | Harness only, for Kitsune main with holds (kitsune#364 … #390). The relay answers Kitsune's approval prompts with a recorded elicitation policy (#55, #61); the gallery task runs in a harness-opened tab (#54); the agent is stopped before its model request when relay setup fails (#64); holds are counted from session evidence (#63); setup reads the current tab that #390 no longer lists while the user views it (#68). Catalogs, pages and graders are those of `taskset-v3.1.1`; the hostile-UI catalog (not part of the suite) gains Kitsune-only strategies (#62) | Kitsune main `514b5b7` lite suite (2026-11-01, on `869551c`, the same code); the `dea1ad4` cohorts ran on earlier commits between v3.1.1 and v3.1.2 |
| **`taskset-v3.2`** (current) | Personal track seeding (#70): the user opens the starting tabs through the [user channel](../coexistence.md#the-user-channel) (WebDriver BiDi), so Kitsune lists them, including the protected note, as the user's and applies its user-tab rules (kitsune#393, kitsune#394). Before, they were opened with the MCP server's own `browser_tabs new` and listed as agent-owned. Setup is unscorable if Kitsune lists a starting tab as owned. Tasks, pages and graders are unchanged and the ID stays `personal-browsing-local-v3`, but **Kitsune personal results are not comparable with earlier tags**; Playwright has no tab ownership. Other experiments that reuse the personal fixtures still seed through the MCP server. Also carries `run-full-suite.py --from` and `merge-suites.py` (#69) and the new `analyze-release.py` signals (#71, #73) | None yet |

Earlier reports predate the tags and ran on earlier task/grader code. Scores on
v1 and v1.1 are not compared directly: the two personal tasks changed their
requests, so their recorded v1 notes cannot be re-graded as v1.1 answers.
Likewise v1.x and v2 scores are never compared directly: v2 changes a request,
the primary safety rule and one gallery task. Rerun every Kitsune version being
compared on the same frozen taskset. v3 scores likewise must never be compared
with v1.x/v2: rerun every compared Kitsune version on `taskset-v3` after its
owner creates the tag. A v1.x report's `task_success` is strict v1; a v2
report's is ownership-aware v2, with strict v1 under `contracts`.
Pair manifests record `benchmark_source.taskset` (e.g. `taskset-v1.1-2-gabc1234`;
a `-dirty` suffix means uncommitted changes).

Frozen in each taskset tag:

- Personal: `tasks/personal/catalog.json`, `kitsune_benchmark/personal_fixtures.py`,
  `personal.py` and `personal_session.py` (fixtures, variants and graders).
- Gallery: `kitsune_benchmark/gallery.py`, `gallery_static/`, `gallery_media.py`.
- Coexistence (from `taskset-v3.1`): `tasks/coexistence/catalog.json`,
  `configs/benchmarks/coexistence.json`, `kitsune_benchmark/coexistence.py`,
  `coexistence_fixtures.py`, `coexistence_session.py`, `user_driver.py` and `bidi.py`.
- External (from `taskset-v3.1`): `configs/benchmarks/external.json`,
  `tasks/external/catalog.json`, `tasks/live/*.json`, `kitsune_benchmark/external.py` and
  `miniwob.py` (upstream revision, tasks, seeds). Up to `taskset-v3`:
  `configs/benchmarks/miniwob.json` (one task, `click-test-2`).
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

`taskset-v3` (above, tagged at `4d73130`) adds the long-page family and repeated,
counterbalanced full-suite planning. The first v3 cohort ran on Kitsune v0.7.0
(2026-10-26); rerun earlier releases on v3 before comparing versions. Effective content viewports are measured on
every personal run (#21). The Kitsune window is equalized (1280×805) for the
personal, gallery and coexistence tracks; gallery and coexistence are equalized by
construction but not measured.

1. Review/freeze this preparation and have the owner create `taskset-v3`.
2. Rerun both the previous and new Kitsune release on that exact tag with the
   same model, harness, caps and predeclared attempt/order plan (for example,
   `--sequential --attempts 2 --order abba`). Keep each revision's output in a
   fresh directory. Do not reuse historical v1.x/v2 scores as a v3 baseline.
3. Report success and tokens together with response bytes/chars for the new
   long-page category, per-order/per-attempt results, and whether
   `viewport.content_viewport_equality_asserted` held on the personal runs of
   both targets. Rerun the native viewport check first after a Firefox or Kitsune
   upgrade; configured Firefox window size is not a measured content viewport.

These are observations; a release-improvement claim still goes through a
`hypothesis` issue. The coexistence runs in this cohort used the pre-freeze draft
(`coexistence-v0-draft`); from `taskset-v3.1` the frozen
[coexistence track](../coexistence.md) is part of the full suite. The taskset-v2
user-seeded tab custody contract is retained unchanged.

## main `dea1ad4` → main `514b5b7` (pre-release main)

`514b5b7652a2e0a7ac4a3fb07e602a793f732e36` (`v0.7.1-27-g514b5b7`). 6 commits after `dea1ad4`:

- a declined viewed-tab hold means "not in this tab", and the viewed tab is no longer listed current (#390, for #383);
- a repeated snapshot after a full action result answers `unchanged` (#391, for #384);
- contenteditable text in snapshots, no false `no_visible_change` (#392, for #385);
- shorter `needs_user` instructions (#389), typed text on a stale-ref Enter (#388), agent-tab popup (#382).

Needs benchmark #68's setup fix (`869551c`, tagged as `taskset-v3.1.2`), which reads the current tab #390 no longer lists.

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-11-01 | [Lite suite under decline](2026-11-01-main-514b5b7.md) | `claude-opus-5-5`, Claude Code subscription | `514b5b7` | 306 scorable runs; coexistence and external rerun after a session-limit stop and merged. Kitsune solves every lite unit; PW crowded 20/21 (`mm-audio`). K/PW input (`dea1ad4` decline → `514b5b7`): personal 0.943 → 0.934, crowded 0.704 → 0.627, isolated 0.859 → 0.910, coexistence 0.946 → 0.992, external 1.165 → 0.960. One prompt per held run (27 runs), all redone in another tab; personal held units 1.385 vs 0.841 without. Coexistence unchanged |

## v0.7.1 → main `dea1ad4` (pre-release main)

`dea1ad4b71a8669c9a9f2f103e2c7ea831f29e34`. 21 commits after v0.7.1. The changes this benchmark measured:

- the viewed-tab hold and user-tab navigation protection by default (#364, #371);
- `needs_user`, approval through MCP elicitation and `browser_resume` (#376–#381);
- post-action deltas that wait for the page, `navigated`, hover deltas (#348–#350);
- cross-origin frames (#343, #354); `hold_ms` and sustained hover (#351, #365).

Needs the relay of benchmark #55 (merged), which answers Kitsune's approval prompts; its elicitation policy is part
of the run (#59).

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-11-01 | [Lite suite under decline and accept](2026-11-01-main-dea1ad4-elicitation.md) | `claude-opus-5-5`, Claude Code subscription | `dea1ad4` | 2 × 306 scorable runs, no retries; Kitsune solves every lite unit under both policies (crowded 21/21). K/PW input, units with a hold: v0.7.1 0.945, **decline 1.389, accept 0.909**; without a hold ≈0.83–0.86. Decline: 28/28 held runs redid the write in a new tab. Accept: 2.1 prompts per held run. Coexistence unchanged. Hostile (no model): K 21/26 shared, 23/26 with Kitsune-only strategies |

## v0.7.1

`9f84b255dcd9fe77d3cca9930e1dd397b2b72176`. 29 commits after v0.7.0. The changes this benchmark measured:

- snapshot budget fills `main` first and compacts link URLs (#319, for #310);
- ARIA sliders and `press_key` repeat (#318);
- the shadow-root `..` step (#313);
- current-tab and tab-less-write changes (#309/#316, which need setup compatibility #35);
- compact `browser_find` (#330, for #323);
- pointer approach and addressable snapshot targets (#344, for #340–#342).

First release cohort on `taskset-v3.1.1` with the lite plan. Compare it with v0.7.0 on the same units, as
observations.

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-29 | [Release cohort + hostile-UI matrix](2026-10-29-opus-subscription-v0.7.1.md) | `claude-opus-5-5`, Claude Code subscription | `9f84b25` (`v0.7.1`) | 306 scorable runs, no retries. Lite units: personal 56/56 both; crowded PW 21/21 vs K 20/21 (`mm-audio` no_attempt); isolated 21/21 both. K/PW input on joint units: personal 0.829 (v0.7.0 0.815), **crowded 0.572 (0.945)**, isolated 0.922 (1.018). Coexistence view 2/28 vs 28/28, typing input 0/3 vs 3/3. Hostile matrix (no model): K 20/26 vs PW 23/26 |

## v0.7.0

`1dea68e452dbe24755fc6a0801454e76bac4345c`. v0.5.0–v0.7.0 add a Python API on the
shared bridge, move the tools into `kitsune.tools` and split the PyPI
distributions (`kitsune-browser`, `kitsune-browser-mcp`). The benchmark launch
command is unchanged. First cohort on `taskset-v3`; no earlier Kitsune version
has v3 results yet, so this is an observation, not a release comparison.

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-28 | [New tracks: external-v1 + coexistence-local-v1](2026-10-28-new-tracks-v0.7.0.md) | `claude-opus-5-5`, Claude Code subscription | `v0.7.0` | 110 scorable runs on `e2c9900` (`taskset-v3.1`): MiniWoB 7/7 both; coexistence v3 view 2/28 vs 28/28, typing user-input 0/3 vs 3/3, protect arm 28/28 |
| 2026-10-26 | [Full suite + coexistence, subscription](2026-10-26-opus-subscription-v0.7.0.md) | `claude-opus-5-5`, Claude Code subscription | `1dea68e` (`v0.7.0`) | 480 scorable runs, no retries; personal 83/84 PW vs 84/84 K, crowded 63/63 vs 62/63, isolated both 63/63; coexistence v3 view 2/28 vs 28/28. An earlier `gpt-6.1-sol`/Codex attempt stopped on model timeouts and is not pooled |

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
