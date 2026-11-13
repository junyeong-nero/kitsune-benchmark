# Claude subscription: CAPS replication and main version-comparison baseline

Operator approved both separate experiments before execution: CAPS A/B plus main `883d80e` on the standard lite
suite. Claude Code `2.1.303`, `claude-opus-5-5`, medium, **claude.ai subscription only**; no API-key execution,
API fallback, paid budget or model substitution. Report list-price estimates as estimates, not subscription charges.
Preserve raw failures and unstarted attempts. Stop for quota/execution/integrity errors; no silent retries.

## A. Scripting CAPS A/B (80 attempts)

Replicate the [Codex protocol](2026-11-11-codex-scripting-caps-ab.md) using Claude, without pooling model results:

- Both arms: clean Kitsune `c698d408d1c77eb708e853649bde4085a0d87ac8`, `KITSUNE_SCRIPTING=1`, 14 tools, no benchmark allowlist.
- `core`: explicit `KITSUNE_CAPS=core`; `default`: CAPS absent. Storage/history still excluded from `all`.
- Same 7 MiniWoB seed-42, 7 personal variant-0 and 6 isolated-gallery variant-0 tasks; 2 repeats, original ABBA order.
- Same task prompts, fixtures, graders, timeouts, private Firefox profiles and elicitation `decline`.
- First two counted attempts checked before the remainder. Source/settings stay frozen throughout.
- Normal zero-start MiniWoB completion may continue only with the existing explicit `--continue-unstarted` policy:
  retain its original unscorable grade, zero telemetry errors and `no_terminal_reward`; never retry it automatically.
  Quota, actual execution, other unscorable, telemetry and catalog errors stop the runner.
- Unlike Codex, Claude init logs expose the client tool inventory, including MiniWoB. Personal/gallery also require
  a matching relay catalog. Observe request counts, first-request input and list-price cost from stream-json.
- Primary mechanism: capability refusals and `ui-infinite`. Report all outcomes; matched joint-success input/output,
  model requests, calls, elapsed and list-price cost use **default/core**. Inspect Python error categories and
  script audit flags; broad host Python is not confined by this audit. Two repeats do not establish significance.

```sh
uv run --locked python scripts/run-claude-scripting-caps-ab.py run \
  --kitsune-project ../kitsune-scripting-caps-default \
  --kitsune-sha c698d408d1c77eb708e853649bde4085a0d87ac8 \
  --out artifacts/claude-scripting-caps-default-c698d40 --continue-unstarted
uv run --locked python scripts/run-claude-scripting-caps-ab.py analyze \
  --out artifacts/claude-scripting-caps-default-c698d40
```

The wrapper reuses the source/config/hash/resume checks and grading calls of the Codex runner, selecting only the
Claude subscription harness and adding its measured usage fields. The earlier interrupted main legacy/scripting
Claude cohort and completed Codex cohorts remain untouched and separate.

## B. Main `883d80e` standard lite baseline (306 planned agent runs)

- Clean pinned checkout `artifacts/vendor/kitsune-main-883d80e`, revision
  `883d80eee2c85f81410352ea8f86b81e11a2b682`. Scripting OFF, default core. No CAPS-patch code.
- Existing standard **23-tool UI allowlist** for Kitsune and Playwright MCP `0.0.83`, matching historical lite
  reports. This is a comparable default-product baseline, not an unrestricted 27-tool catalog experiment.
- `run-full-suite.py --plan lite`: personal 28 tasks × v0/v1; gallery 21 tasks × crowded/isolated v0;
  coexistence user-seeded 28, typing v0/v1/v2, Kitsune-only unprotected-user-tabs 28; external 7 MiniWoB + 3 live.
  The unprotected arm is isolated, fixture-only and explicitly part of the historical suite, not a global setting.
- One attempt: targets parallel on personal/gallery/external, paired on coexistence, elicitation `decline`.
  Same ordering/contention policy as `c0f80a2`; elapsed is not standalone native latency. Live tasks are not
  authoritative success grades and website contents can change.
- **No automatic setup retry** (`--retry-setup-failures 0`), unlike the previous report's permitted one retry
  (none occurred there). A failed track settles its already-active peers, then stops before later tracks.
- Historical comparators: `artifacts/opus-subscription-main-c0f80a2` and `artifacts/opus-subscription-v0.7.2`.
  Do not rerun or pool those cohorts. Compare matched units/grades, K/PW ratios and Kitsune's own input, plus
  coexistence user-view/input safety. Separate model/site/time variance and contract changes from code effects.
- At preparation, `git diff 53d6a9b..HEAD -- kitsune_benchmark tasks configs` is empty: since the `c0f80a2` cohort,
  the current benchmark's task/harness package has not changed. The v0.7.2 comparison still needs its documented
  contract/track differences disclosed; historical reports are not a concurrent randomized version A/B.

```sh
uv run --locked python scripts/run-full-suite.py --harness claude --model claude-opus-5-5 \
  --plan lite --elicitation decline --retry-setup-failures 0 \
  --kitsune-project artifacts/vendor/kitsune-main-883d80e \
  --out artifacts/opus-subscription-main-883d80e
```

### Baseline preflight amendment (before any B model invocation)

The optional `test_personal_fixtures` native tests first failed on a short-name import, then on 22 legacy MCP-seeding
subtests (`no_current_tab` followed by `user_tab_read_only`). The production personal track already uses user-channel
seeding. Only that test file was updated to use the same user channel and assert zero agent-owned seeded tabs,
and to support module-name invocation. No Kitsune source, task, production harness, grader or measured run changed.
The combined personal/native modules then passed **61/61**. Initial failed test attempts remain disclosed here;
they are not model runs or silently retried benchmark attempts.

Neither experiment authorizes main merges, remote pushes, releases, issue posting or changes to benchmark tasks.
