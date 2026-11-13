# Claude five-way MiniWoB comparison — frozen 2026-11-12

User-selected scope: **7 shared MiniWoB tasks × 5 arms × 2 repeats = 70 planned agent attempts**.
This is a new cohort, not an extension/pooling of the earlier seven-task exhibition, Codex runs,
Claude CAPS A/B, or the interrupted 98/306 main standard-lite baseline. The latter remains paused.

## Treatments and constants

| Arm | Product source/surface | Published tools |
|---|---|---:|
| `kitsune-main` | clean `883d80eee2c85f81410352ea8f86b81e11a2b682`, scripting OFF, standard external UI allowlist | 23 |
| `kitsune-scripting` | clean `c698d408d1c77eb708e853649bde4085a0d87ac8`, `KITSUNE_SCRIPTING=1`, CAPS absent (new default `all`), no benchmark allowlist | 14 |
| `playwright` | pinned `@playwright/mcp` 0.0.83, standard external UI allowlist | 23 |
| `ego` | installed ego lite 0.6.2.9, Chromium 156.0.8078.74, Node v24.22.1; vendor guide v2.2.0 wrapped verbatim | 1 (`run_script`) |
| `aside` | installed Aside CLI 1.26.1107.24; application bundle 1.0.1022.1; native MCP `repl` only, not its delegated-agent `exec` | 1 (`repl`) |

- Claude Code **2.1.303**, **claude-opus-5-5**, **medium**, claude.ai subscription only.
  No API-key harness, paid fallback, or vendor-agent delegation. CLI dollar figures are list-price estimates,
  **not subscription charges**. Doctor checks authentication/configuration, not remaining quota.
- Existing pinned MiniWoB source `33c3b4ddef8c6eb67c57a29663d844b1eda7e614` and upstream grades.
  Tasks: `mw-{click-test-2,click-checkboxes,enter-text,choose-list,login-user,use-autocomplete,book-flight}`;
  seed 42, 120-second episodes, 180-second harness timeout, unchanged task prompt/grader.
- Sequential execution. For task index `i`, rotate the five-arm order by `i % 5` in repeat 0;
  reverse that exact task's order in repeat 1. Every arm appears once in each task/repeat.
- Both Kitsune checkouts, benchmark HEAD/clean status, vendor CLI/app file identities, versions and ego guide
  digest are checked before/after each attempt. Manifests freeze the schedule, runner hashes, and no-model
  catalog-preflight digest. Claude init catalogs are checked per attempt against 23/14/23/1/1.
- Existing exhibition support was cherry-picked into a separate local branch as `b673ea0`.
  The commit adding this protocol/runner is the execution pin (also recorded in every manifest).

## Run and stop policy

```sh
uv run --locked python scripts/run-five-way-miniwob.py preflight \
  --out artifacts/claude-five-way-miniwob-20261112
uv run --locked python scripts/run-five-way-miniwob.py run \
  --out artifacts/claude-five-way-miniwob-20261112 --continue-unstarted --limit 5
# Inspect the first complete five-arm cell before the remaining 65:
uv run --locked python scripts/run-five-way-miniwob.py run \
  --out artifacts/claude-five-way-miniwob-20261112 --continue-unstarted
uv run --locked python scripts/run-five-way-miniwob.py analyze \
  --out artifacts/claude-five-way-miniwob-20261112
```

No retries or replacement attempts. Preserve all raw grades. A normal model finish with **zero episode starts,
zero telemetry errors, and `no_terminal_reward`** may continue under the previously approved explicit
`--continue-unstarted` policy; it remains unscorable and counted as an attempt. Other execution, quota,
telemetry, source/catalog or runner errors stop for review. Failed rows cannot silently be skipped on resume;
runner exceptions additionally create a stop marker. No automatic API fallback or post-quota resumption.

Preflight initially exposed missing `mcp` in the benchmark venv and missing `psutil` when trying the entire
runner in Kitsune's venv. These **no-inference** test/probe failures were fixed before freezing by keeping
benchmark execution in its own venv and using the existing Kitsune MCP SDK only in a catalog worker.
No dependencies, task contracts, model prompts, product code or grades changed for that repair.
The successful no-model probe preserved full filtered tool schemas and server instructions and confirmed
all five expected tool counts. No browser task was executed by the probe.

## Analysis and limits

Report every arm's attempts/scorable successes/unstarted/execution failures, input including cached tokens,
output/cache input, model requests, MCP calls, elapsed time, median first-request input and CLI list-price
estimate. Compare ratios on **jointly successful identical task/repeat cells** against each Kitsune arm;
also report the all-five joint-success count. Failed task effort remains in all-attempt totals.

Audit all `browser_run_python`, `run_script`, and `repl` arguments/results, including MCP errors,
reward/instrumentation patterns, page-JS/CDP evaluation and literal URLs. Raw passing grades and UI-only
compliance are separate. Legitimate navigation scripts naturally contain the fixture URL. Pattern matches
need manual interpretation; absence of a match does not prove confinement. No score hardening is claimed.

Important non-equivalences:

1. Kitsune/Playwright use fresh private headless Firefox; Aside/ego attach to installed browser environments.
   No profile/cookie/cache purge, unrelated-user-tab operation, or browser upgrade is authorized by this run.
   The common prompt asks for a new task tab. Vendor instructions and connected-session behavior are treatment
   differences, not harmonized prompts. Product browser engines, warm state and geometry are not matched.
2. MiniWoB does not attest equal viewports. For exhibition arms, existing pair `headless`/`browser_binary`
   fields describe the runner's Firefox preparation, **not the attached vendor browser**; use the cohort's
   vendor provenance instead. No private-profile isolation claim applies to Aside/ego.
3. A single script call can contain many browser actions; **MCP calls are not action counts or model requests**.
   Vendor script-call limits are 120 seconds (130-second MCP envelope), versus the existing 45-second
   Kitsune/Playwright MCP envelope. All arms retain the same task/episode deadlines.
4. Kitsune Python and vendor script runtimes are trusted code execution, not sandboxed UI-only enforcement.
   `all` excludes Kitsune storage/history and does not remove ownership/mode/approval protection.
5. Seven tasks, one seed, two repeats do not establish statistical superiority, full-lite performance,
   coexistence safety, or a release/default-switch recommendation. No global scripting change or release.
