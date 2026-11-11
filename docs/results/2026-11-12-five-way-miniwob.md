# Claude: Kitsune main/scripting, Playwright, ego lite and Aside — 70 MiniWoB attempts

**Completed 2026-11-12, approximately 06:32–07:01 KST.** Seven tasks × five arms × two repeats;
all **70 normally completed and scorable**, with **69 recorded successes**. No quota errors,
unstarted episodes, replacement attempts, or episode retries. This new subscription cohort is separate from all
older exhibition, Codex, CAPS A/B and standard-lite runs.

**Takeaway:** the one-tool exhibition arms used less input and fewer MCP calls than Kitsune scripting,
but not fewer model requests or less elapsed time in the primary matched comparisons. Kitsune scripting
reduced input versus its main 23-tool surface without using Python at all. This is not an unrestricted
product leaderboard: page-JS use, unequal browser state/engines, **Aside's changing tool description**,
and **ego TaskSpace reuse** materially limit attribution.

## Setup and provenance

[Predeclared protocol](../experiments/2026-11-12-five-way-miniwob.md).
Execution benchmark pin: **`7b7abca52d7e93f2ccc326f05a4cd65a0ff5e26c`**, clean.
Claude Code **2.1.303**, **claude-opus-5-5**, medium, claude.ai subscription only.
All 70 init records show `apiKeySource=none`; no overage-use event or model delegation was observed.
Dollar figures below are **CLI list-price estimates, not subscription charges**.

| Arm | Source/version | Published surface |
|---|---|---|
| Kitsune main | `883d80eee2c85f81410352ea8f86b81e11a2b682`, clean | scripting OFF, standard 23-tool UI allowlist |
| Kitsune scripting | `c698d408d1c77eb708e853649bde4085a0d87ac8`, clean | scripting ON, CAPS absent → new `all` default, 14 tools without benchmark filtering |
| Playwright | `@playwright/mcp` 0.0.83 | standard 23-tool UI allowlist |
| ego lite | 0.6.2.9, Chromium 156.0.8078.74, Node v24.22.1; guide v2.2.0 | `run_script`, CLI wrapper with vendor guide |
| Aside | CLI/native MCP 1.26.1107.24; installed application bundle 1.0.1022.1 | native `repl` only; delegated-agent `exec` excluded |

Tasks, seed 42, upstream MiniWoB revision and original reward grading are unchanged. Task order was
`click-test-2`, `click-checkboxes`, `enter-text`, `choose-list`, `login-user`, `use-autocomplete`,
`book-flight`. Each task's five-arm order was rotated in repeat 0 and reversed in repeat 1. Sequential,
not target-parallel. The first five attempts were reviewed before the remaining 65; all are retained.

No global scripting-default switch, main merge, release, remote push or issue posting was performed.
The earlier **main standard-lite baseline remains 98/306 attempted**, not resumed by this experiment.

## All-attempt results

Input includes cached input. Elapsed is the sum of harness run time, not the entire cohort's wall clock
or all browser provisioning/cleanup. Every column has 14 attempts; ego's failed task effort remains included.

| Metric | Kitsune main | Kitsune scripting | Playwright | ego lite | Aside |
|---|---:|---:|---:|---:|---:|
| Recorded successes / attempts | **14/14** | **14/14** | **14/14** | **13/14** | **14/14** |
| Scorable | 14 | 14 | 14 | 14 | 14 |
| Input tokens, incl. cache | 825,404 | 580,577 | 885,259 | 477,783 | 439,242 |
| Cached input | 746,752 | 508,863 | 799,037 | 411,150 | 374,000 |
| Output tokens | 8,294 | 8,081 | 8,396 | 11,938 | 9,715 |
| Model requests | 75 | 72 | 81 | 78 | 74 |
| MCP calls | 101 | 96 | 108 | 64 | 60 |
| Elapsed, seconds | 254.309 | 234.356 | 278.285 | 280.666 | 259.525 |
| CLI list-price estimate | $0.944 | $0.837 | $1.017 | $0.853 | $0.790 |
| Median first-request input | 9,489.5 | 6,725.5 | 9,221 | 4,819 | 5,055.5 |
| Script calls / MCP-flagged errors | 0 / 0 | **0 / 0** | 0 / 0 | 64 / 8 | 60 / 5 |

All six simpler tasks pass both repeats in all five arms. Only ego `book-flight` repeat 0 fails.
“Recorded success” is the upstream grade, **not a certificate of UI-only compliance**.

## Matched-success comparisons

Each row below is **arm / Kitsune scripting**, summing identical successful task/repeat cells in both arms.
A lower ratio is less of that resource. The ego comparison excludes the `book-flight` r0 cell from **both**
sides, not just ego's failure. Aside's first/cold-description attempt is retained in the primary result.

| Arm / Kitsune scripting | Joint cells | Input | Output | Requests | MCP calls | Elapsed | List-price estimate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kitsune main | 14 | 1.422 | 1.026 | 1.042 | 1.052 | 1.085 | 1.128 |
| Playwright | 14 | 1.525 | 1.039 | 1.125 | 1.125 | 1.187 | 1.216 |
| ego lite | 13 | **0.809** | 1.421 | **1.095** | **0.667** | **1.146** | 0.977 |
| Aside | 14 | **0.757** | 1.202 | **1.028** | **0.625** | **1.107** | 0.945 |

- Scripting/main on all 14 cells: input **0.703** (−29.7%), requests **0.960**, calls **0.950**,
  elapsed **0.922**, estimated cost **0.886**. The smaller observed first-request prefix is consistent with
  the smaller tool surface. **There were zero Python calls**, so this does not demonstrate a batching
  benefit from Python, or exercise the new CAPS grant. It also compares 23 vs 14 tools, not the earlier
  unrestricted 27-vs-14 legacy experiment.
- Aside versus scripting: input **−24.3%**, calls **−37.5%**, but requests **+2.8%**, elapsed **+10.7%**.
  ego versus scripting on 13 jointly solved cells: input **−19.1%**, calls **−33.3%**, requests **+9.5%**,
  elapsed **+14.6%**. Fewer MCP calls do **not** imply fewer model requests; direct tools can be issued
  together in one request, while a script call can contain several actions.
- Against main, Aside input/calls/requests/elapsed are **0.532 / 0.594 / 0.987 / 1.021** on 14 cells;
  ego **0.563 / 0.636 / 1.045 / 1.055** on 13. Neither establishes a general latency improvement.
- There are **13 all-five joint-success cells**. Input totals on that identical set are main **715,432**,
  scripting **497,762**, Playwright **766,039**, ego **402,608**, Aside **382,057**. Complete totals are in
  `audit.json`; the primary pairwise table deliberately shows its differing denominators.

## Failure and script audit

All **124** vendor script calls were inspected; Kitsune made no Python calls. The tool-error counts are
MCP error flags, not every ineffective statement: Aside's first two `return`-style calls produced no output
without an MCP error flag.

- **ego: eight errors**, all invalid CSS-style `[ref=N]` selectors copied from snapshot notation. Valid
  `ref=N`/ordinary CSS alternatives recovered within the same episode. No attempt was restarted.
- **Aside: five errors.** First attempt #5: undefined `pg`, undefined `context`, a null `page.url()`, and
  redeclaration of persistent `const t`. Attempt #67: filling a read-only date input; it recovered using
  the date picker. The first attempt also listed existing tab metadata during API discovery; raw logs
  are private and are not published as a real-page transcript.
- **ego failure #33**, `book-flight` r0: official raw reward **−1**, one page load/start, zero telemetry
  errors. It identified the correct shortest flight but `.flight:nth-of-type(2) button` selected the
  wrong sibling. The final answer acknowledged the wrong booking. This is an ordinary graded failure,
  not quota trouble or an unstarted episode.

Page-JS flags (counts are expressions/attempts, including ones that did not execute):

| Arm / sequence | Task | Page-JS expressions | Recorded grade | Observed use |
|---|---|---:|---|---|
| Aside #5 | click-test-2 r0 | 6 | pass | attempted/successful DOM text observations; three successful `body.innerText` reads |
| ego #8 | click-checkboxes r0 | 1 | pass | read checkbox labels/checked state |
| ego #25 | login-user r0 | 2 | pass | read instruction and body text |
| ego #33 | book-flight r0 | 5 | fail | read instructions, flight rows, DOM sibling positions and visible reward widget |
| ego #68 | book-flight r1 | 6 | pass | DOM observations **plus assigning an ID to the intended booking button** before clicking it |

The successful ego booking in #68 is **not a strict UI-only completion**: it changed the DOM to target the
button. The other page-JS observations also sit outside the direct UI-only allowlist used for main/PW.
These are disclosed rather than regraded or silently discarded.

The limited `core.`, `endEpisode`, `WOB_`, `EPISODE` scan had zero matches. This does **not** mean there were
no reward-related reads: ego explicitly read the **visible `#reward-last` DOM widget** after booking.
All literal URLs in executed script arguments were their own local fixture URLs. No observed script used
host filesystem access, alternative `fetch`/CDP traffic, or vendor-agent delegation. These audits are
observational, not sandbox/confinement proofs; client-side reward instrumentation is not adversarially hardened.

**Sensitivity only:** additionally removing page-JS-flagged cells from each successful pair gives ego
**10** cells (input **0.762**, requests **1.043**, calls **0.661**, elapsed **1.092**, estimate **0.960**)
and Aside **13** cells (input **0.704**, requests **0.926**, calls **0.549**, elapsed **0.993**, estimate
**0.924**), all relative to scripting. This is not the primary result or a new cohort. The Aside exclusion
also removes its first/cold-description attempt, so it cannot isolate the effect of page JS.

## Important environment and catalog findings

1. **Aside tool description was not constant.** The no-model preflight returned a **66-character** `repl`
   description. Postflight returned **6,312 characters**, now explaining `openTab`, `snapshot`, persistent
   variables and `console.log`. Only that description changed; native server version, binary/app identity,
   tool name and input schema were unchanged. First-request input was **3,378** in the first Aside attempt,
   then **5,051–5,060** for the remaining 13. This is consistent with runtime initialization/loading of
   guidance, but the exact transition was not captured by per-run full-schema logging. The runner checked
   init **names/counts**, so it did not detect this text change during execution. Preserve the entire cohort;
   do **not** describe Aside as a frozen-description treatment or remove its expensive first attempt.
2. **ego reused TaskSpaces/pages.** No generated script called `finish()`. Six repeat-1 tasks resumed the
   same named space and `p1` used in repeat 0 (IDs 2, 3, 4, 5, 6, 8); autocomplete used a new name/ID 9.
   Every run navigated to its own fresh fixture URL and had one episode start, but this was **not a fresh
   tab/profile reset** and did not literally satisfy the new-tab instruction for those repeats.
3. Kitsune/PW use private headless Firefox. Aside/ego connect to installed browsers without profile reset;
   engine, locale, viewport and warm state differ. MiniWoB does not attest viewport equality. Existing
   exhibition runner fields `headless`, `browser_binary` and run-level
   `isolated_browser_confirmed_by_operator=true` are inherited Firefox metadata, **not valid isolation
   attestations for Aside/ego**. This report and the cohort limitations supersede that misleading implication;
   raw manifests have not been rewritten. No unrelated tabs were intentionally modified or cleared.
4. No safety/coexistence track ran here. Seven tasks/one seed/two repeats, dynamic vendor state and page-JS
   involvement do not support statistical superiority, full-lite safety claims or a `0.8.0` release decision.
   In particular, small surface, low token use and permission safety are different claims.

## Evidence and reproduction

Private artifact root: `artifacts/claude-five-way-miniwob-20261112/`:

- `manifest.json`, `catalog-preflight.json`, `postflight/catalog-preflight.json`;
- `runs.jsonl`, `analysis.json`;
- offline `audit.py`, `audit.json`, `script-calls.txt`; per-run `manifest.json`, `events.jsonl`,
  `evaluation.json`, `summary.json`, `final.txt` under `artifacts/five-way-miniwob/`.

`runs.jsonl` SHA-256: **`17efac201d7b6404c6f89b2c0772427461b758868178b98b8e0c7c6d792930ff`**.
All 70 manifests/grades/init inventories, model/effort/auth, null API budget, source/runner pins and
schedule keys were checked. Grades: **69 true, 1 false**, with one start and zero telemetry errors each.
Source cleanliness and vendor identities held; catalog **text** stability did not hold for Aside as above.
Targeted preparation tests: **96 passed**; final regression including the MCP tool-filter tests:
**105 passed**. Early no-inference venv import failures and their repair are recorded in the protocol;
no model attempt is hidden by that repair.

For a fresh replication, use the frozen benchmark commit and a **new output directory**, preserving the
original 70 rows. The frozen runner's `preflight`, `run` and `analyze` commands are in the protocol.
Offline analysis alone is:

```sh
uv run --locked python scripts/run-five-way-miniwob.py analyze \
  --out artifacts/claude-five-way-miniwob-20261112
uv run --locked python artifacts/claude-five-way-miniwob-20261112/audit.py --brief
```

**Next inference:** Kitsune's direct-tool prefix remains larger than the one-tool arms, while Python
composition was never chosen here. Any next optimization should separately test prefix size, batching
choice and API/ref usability with genuinely reset vendor contexts and observed per-run schemas. This
cohort is useful directional evidence, not authorization to change defaults or launch another experiment.
