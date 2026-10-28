# Codex harness integration

[Documentation index](README.md) · [Running guide](running.md) · [Results](results/README.md)

This document describes execution/authentication boundaries. Track-specific
reset and grading contracts live in the [personal](personal-browsing.md) and
[external track](external.md) guides; observed measurements live in dated reports.

## Fixed configuration and boundaries

- Codex CLI `0.163.0`, model `gpt-6-luna`, reasoning effort `medium`.
- Supported ChatGPT subscription login; no custom model API client, API-key
  fallback, credential extraction/copying, or automatic model substitution.
- Model calls consume subscription quota. Reported usage is not a billing API;
  cached-input fields do not establish subscription charges or remaining quota.
- Both MCPs use one server name, `browser`, and their native tool schemas/results.
- Python runtime uses pinned psutil for collection. Install with `uv sync --locked`.

Commands:

| Command | Behavior |
| --- | --- |
| `doctor` | Version/help/login checks; no inference |
| `plan` | Show a single-run command/config; no Codex invocation |
| `run` | Execute one operator-provisioned task/browser configuration |
| `smoke` | Plan; `--execute` runs an isolated read-only pair |
| `benchmark` | Plan; `--fetch` downloads pinned source; `--execute` runs the external pilot |
| `personal` | Plan; `--execute` runs selected local personal-session task pairs (six runnable of 24 specs) |

The personal track has a bounded sequential multi-task runner. No generalized
randomized/repeated scheduler/statistics, WebArena reset/deployment, token-budget
termination, or complete tool/prompt attestation is implemented. See
[external track](external.md) and [personal browsing](personal-browsing.md) for separate
tracks, external state evaluation, and their limits.

## Local checks and real validation

On 2026-10-18 the installed CLI was found at
`~/.nvm/versions/node/v26.12.0/bin/codex`, version0.163.0, with ChatGPT login.
Its help supports `--ignore-user-config`, `--ignore-rules`, `--ephemeral`,
`--json`, `--output-last-message`, and `--skip-git-repo-check`. Configuration was
checked against the pinned official schema and metadata commands. Features
showed shell/apps/built-in browser/hooks/plugins/subagents/memory disabled.

Both targets completed isolated smoke and MiniWoB pilot runs with the historical
`gpt-6.1-sol` model on 2026-10-18. See the [smoke report](results/2026-10-18-smoke.md)
and [MiniWoB report](results/2026-10-18-miniwob.md). On 2026-10-19 one personal
`pb-current-01` / variant 0 pair completed on both targets with the configured
`gpt-6-luna` model and passed external grading; see the
[personal report](results/2026-10-19-personal-current-page.md). These final JSONL
traces had no observed forbidden tools; this is not full tool-inventory attestation.
A later [six-task variant-0 personal pilot](results/2026-10-19-personal-six-task.md)
recorded 12 scorable agent runs with the same model and policy. Not all tasks
passed: see its format/preservation caveats. Private native RPC timing/size and
catalog logs were added before that run; [offline analysis](optimization-findings.md)
distinguishes hidden setup, agent RPC and residual elapsed without provider-level
per-request usage. This addition does not make tool/prompt attestation complete.

Executable discovery prefers PATH, then common locations/unambiguous nvm
installations. Ambiguous candidates require `--codex`; shell startup scripts
are not executed. The executable's bin directory is prepended to the child
PATH so npm's Codex launcher uses its associated Node runtime.

## Authentication and isolation

Authentication home precedence: explicit `--codex-home` for generic runs,
inherited `CODEX_HOME`, then `~/.codex`. The official CLI alone accesses its
credentials. Each task uses:

- `--ignore-user-config`: reuse login without loading its `config.toml`.
- `--ignore-rules`: ignore user/project execpolicy rules.
- `--ephemeral`: fresh, non-resumed task session.
- Fresh temporary cwd outside source repositories.
- `model_provider="openai"` and `forced_login_method="chatgpt"`.
- Exactly one MCP configuration, explicit model/effort, common developer prompt.
- Zero project instruction budget; bundled/catalog skill instructions and host
  skill discovery disabled. No normal memory/plugin/hook/subagent features.
- Shell, built-in browser/search, apps, and local image tools disabled.
- `default_tools_approval_mode="approve"` for the selected trusted MCP, with
  noninteractive `approval_policy="never"`. This authorizes MCP tools without
  enabling shell or globally bypassing the sandbox.

The unstable feature warning is suppressed in per-run config only. Real JSONL
error items remain harness errors. Organization-managed policies may still
apply; an auth home is not a hermetic operating-system boundary.

The execution environment allowlists basic OS variables and declared MCP
`env_vars`. Model API keys/provider overrides/preload variables are not inherited
and cannot be opted back in through that declaration. Values are not written to
manifests; do not put secrets in argv, prompt text, or server specs.

Standalone `doctor` reports inherited API credential variables as a prerequisite
failure, while actual runs strip them before checking/executing:

```sh
uv run --locked python -m kitsune_benchmark doctor --json

# Optional subscription-only check if the parent shell contains API variables:
env -u OPENAI_API_KEY -u CODEX_API_KEY -u OPENAI_AUTH_TOKEN -u AZURE_OPENAI_API_KEY \
  uv run --locked python -m kitsune_benchmark doctor --json
```

A dedicated auth home is optional and has not been set up. If desired, log in
manually with `CODEX_HOME=/absolute/private/path codex login` and choose ChatGPT,
not `--with-api-key`. The benchmark never edits ordinary user config.

## Individual-run inputs

Server JSON: `id`, `command`, `args`, optional `env_vars`, `enabled_tools`,
`startup_timeout_sec`, `tool_timeout_sec`. Inline secret `env` and arbitrary
Codex config overrides are unsupported. Local project arguments should be
absolute because cwd is temporary.

`enabled_tools` filters native tools without translating their schemas. It is
omitted for the full native smoke and specified for the MiniWoB and personal
UI-only tracks.
The audit checks that observed tool names match the supplied allowlist and
rejects JavaScript/data/file navigation URLs in that restricted track.

```sh
uv run --locked python -m kitsune_benchmark plan \
  --server configs/servers/playwright.json \
  --task tasks/smoke/example-domain.json --model gpt-6-luna
```

Generic `run` additionally requires `--confirm-isolated-browser`. That flag is an
operator assertion, not browser provisioning or proof. The generic Kitsune local
config would otherwise attach to its normal default bridge; **do not use it with
a normal signed-in session**. Use the automated pair runner for the tested setup.
Generic Playwright config may also need machine-specific socket/cache variables;
the tested pair runner handles them explicitly.

## Pair setup and lifecycle

```sh
uv sync --locked
npm ci --ignore-scripts --no-audit --no-fund
npm run setup:firefox
uv run --locked python -m kitsune_benchmark smoke       # plan, no inference
uv run --locked python -m kitsune_benchmark smoke --execute
```

The setup helper downloads to `artifacts/browsers` with
`PLAYWRIGHT_SKIP_BROWSER_GC=1`. The pinned npm tools are MCP0.0.83 (Playwright
1.64.0-alpha-1790635538000) and web-ext10.8.0. The current Firefox binary is156.0.

The pair runner creates a private bridge HTTP/WS port pair (never47651/47652),
private `KITSUNE_HOME`, and ephemeral token, and waits for the extension connection.
web-ext installs a private extension copy in a fresh temporary profile. Only
its WebSocket URL changes; original/patched hashes and source revision/dirty
state are recorded. Playwright uses a separate isolated headless profile with
the same Firefox executable. A short private `/tmp/bmb-*` socket directory avoids
the macOS Unix-domain path limit. Existing Zen profiles are never attached.

The pair is fixed order, Playwright first. It stops after an execution integration
failure or unscorable external evaluation rather than silently changing models
or continuing to spend quota. Task success/failure from the external evaluator
is separate from execution status; a scorable task failure can still be a valid
measurement. The personal track adds a native stdio relay for preloaded tabs,
test-session setup and post-call inventory evidence; its hidden work and timing
limits are described in the [personal protocol](personal-browsing.md#artifacts-and-metrics).

## Artifacts and resource collection

Each agent directory contains `manifest.json`, `events.jsonl`, `stderr.log`,
`final.txt` when emitted, `summary.json`, `resources.jsonl`, and
`resource-summary.json`. External trials also have `evaluation.json`.
Pair directories have their own lifecycle resource trace and target summaries.
MiniWoB pairs additionally save `benchmark-summary.json`; personal pairs save
`personal-summary.json`, session evidence, and a `suite-summary.json` in the
first attempted pair directory. See the [artifact map](running.md#inspect-outcomes-and-usage).

Directories are private0700 and run artifact files0600. Raw logs may contain
page data/images/reasoning; artifacts are gitignored, not automatically redacted.
Review before sharing. Manifests record model/settings/task/source hash and
explicitly label missing capabilities. No API cost estimate is fabricated.

Resource sampling includes Codex/MCP/browser trees plus explicitly registered
separate Kitsune bridge/browser roots. Per-run externally managed roots can
remain alive until pair cleanup without being mistaken for leaked processes.
Pair-level phases record setup, ready, target work, and cleanup. See
[resources](resources.md) for RSS double-counting, sampled peaks, CPU baselines,
PID reuse, observer scope, and conditional component means.

## Cleanup, audit, and exit codes

Wall-clock timeouts/interruptions terminate the owned POSIX process group,
including observed non-detached MCP children. Pair setup also owns the private
bridge/web-ext lifecycle. Temporary cwd/socket/profile resources are removed.
A bounded check handles macOS EPERM only if no live group member survives;
remaining live processes remain an error. Independently detached/shared services
and browser/site mutations cannot generally be undone by generic `run`.

JSONL audit deduplicates MCP calls, checks the server name and optional tool
policy, and records errors/usage. Shell/file changes/built-in search, foreign MCPs,
unknown schema items, and malformed logs invalidate the trace. It is a conservative
post-run audit, not a real-time or cryptographically complete security boundary.

Execution statuses: `completed_unscored`, `incomplete`, `invalid_trace`,
`harness_error`, `timeout`, `interrupted`. External evaluation remains a separate
object, not a replacement for execution evidence. Quota/auth failures are not
converted into externally graded task failures.

CLI exit0: successful plan/check, completed unscored run/pair, or a scorable
external selection whose requested pairs are all scorable (including valid task
failures). Exit2: prerequisite/input error.
Exit3: other execution/unscorable outcomes.

## Setup side effect and tests

Before the private helper existed, one plain Playwright installation removed four
unused shared Chromium cache directories (1187/1243 and their headless shells).
Those were automation caches, not profiles. They may need re-downloading for
older automation installations. Subsequent setup uses a private cache with GC
disabled; the side effect is also recorded in the first smoke report.

```sh
uv run --locked python -m unittest discover -s tests -v
```

Offline tests use fake Codex processes and isolated child processes. Browser/task
readiness checks and actual model executions are reported separately, not hidden
inside the unit suite.

## References

- https://developers.openai.com/codex/noninteractive/
- https://developers.openai.com/codex/auth/
- https://developers.openai.com/codex/mcp/
- https://raw.githubusercontent.com/openai/codex/rust-v0.163.0/codex-rs/core/config.schema.json
