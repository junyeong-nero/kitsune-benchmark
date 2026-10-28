# External track (`external-v1`): MiniWoB++ and live sites

[Documentation index](README.md) · [Running guide](running.md) ·
[Task catalog](../tasks/external/catalog.json) ·
[Historical MiniWoB result](results/2026-10-18-miniwob.md)

**Scope:** 10 tasks that were not written for this repository's fixtures.

- **7 MiniWoB++ tasks**, graded by the pinned upstream reward.
- **3 live public-web tasks**, recorded but **never graded**.

This track replaces the one-task MiniWoB pilot (`miniwob-mcp-ui-pilot`, `click-test-2` only). Its scores are
never pooled with that pilot's results or with other suites. For work on existing tabs, sessions and safe
drafts, use the [personal browsing track](personal-browsing.md).

## Tasks

| ID | Kind | Skill |
| --- | --- | --- |
| `mw-click-test-2` | MiniWoB | Click the named one of two buttons |
| `mw-click-checkboxes` | MiniWoB | Select exactly the named checkboxes, then submit |
| `mw-enter-text` | MiniWoB | Type a given string into a field and submit |
| `mw-choose-list` | MiniWoB | Pick an item from a native select dropdown |
| `mw-login-user` | MiniWoB | Fill a username/password login form and submit |
| `mw-use-autocomplete` | MiniWoB | Type a prefix and choose the matching autocomplete suggestion |
| `mw-book-flight` | MiniWoB | Multi-field search form with autocomplete and a date picker, then pick the flight |
| `live-steam-goty-2025-negative-100h` | Live | Find a Steam store page and apply in-page review filters |
| `live-wikipedia-firefox-release` | Live | Wikipedia site search, open the right article, read an infobox field |
| `live-mdn-array-at-firefox` | Live | MDN site search, then read a client-rendered compatibility table |

`mw-login-user` is a synthetic login form inside MiniWoB. It is not a real account, OAuth, 2FA or
session-recovery evaluation. None of the live tasks log in.

## Why these environments

WebArena-Verified needs a substantial self-hosted Docker environment, which this machine does not have,
and it has not been installed implicitly. MiniWoB++ provides small original HTML tasks with their own reward
code, which can be hosted locally in the already isolated Firefox setups. The live tasks add real public
sites, with their real layouts, search boxes and lazily rendered content. No local fixture reproduces those.

This is an **external source/task/evaluator integration**, not a standard MiniWoB++ leaderboard
submission. It uses an agent CLI + Firefox + native MCP UI tools, not the standard
Chrome/Selenium/Gym action and observation interface.

## Pinned source and settings

Configuration: `configs/benchmarks/external.json`; task list: `tasks/external/catalog.json`.

- **Source:** https://github.com/Farama-Foundation/miniwob-plusplus at revision
  `33c3b4ddef8c6eb67c57a29663d844b1eda7e614`. Each run records the SHA-256 of its task HTML.
- **Seed:** 42 for every MiniWoB task, applied through `Math.seedrandom(String(seed))` before the
  episode is generated.
- **Episode budget:** 120000 ms. Upstream HTML defaults to 10000 ms. This deliberate difference means the
  results must not be read as standard default-budget scores.
- **Agent wall-clock limit:** 180 s per MiniWoB run, 300 s per live run.
- **Model:** the default harness is Claude Code on the subscription (`claude-opus-5-5`, medium). Codex
  (`gpt-6-luna`) is still available.

The vendor checkout lives under the gitignored `artifacts/vendor/miniwob`. Its HEAD must match the pin and
its working tree must be clean. The upstream license stays in that checkout; this project does not
redistribute the upstream source in its tracked files.

## Commands

```sh
# Source download only; no model.
uv run --locked python -m kitsune_benchmark external --fetch

# Plan only: no browsers, no model.
uv run --locked python -m kitsune_benchmark external
uv run --locked python -m kitsune_benchmark external --kind miniwob
uv run --locked python -m kitsune_benchmark external --task mw-login-user --task live-wikipedia-firefox-release

# Execution: 20 agent runs for all 10 tasks. Live tasks reach public sites.
uv run --locked python -m kitsune_benchmark external --execute
```

`benchmark` remains an alias of `external`. Selection works as in the other tracks: repeat `--task`, or
use `--kind miniwob|live`. `--budget-usd` applies only to API-key harnesses.

Each pair uses fresh private browser profiles and private bridge ports, home and token. MiniWoB pairs also
get their own localhost-only HTTP server. The suite stops at the first pair that cannot be scored. An
ordinary task failure is still scored.

## MiniWoB: setup, reward and success

For each target, each task gets a new trial token and page with the same original task and seed. The prompt
tells the agent to:

- open that page;
- click START exactly once;
- follow the instruction shown on the page.

Each trial keeps its own load, start and result counters.

The original files are not edited. When the server sends the page, it adds a script before `</body>` that:

1. seeds the existing RNG and sets the declared episode duration;
2. calls the original `core.startEpisodeReal`, then records the episode start;
3. calls the original `core.endEpisode`, then forwards the original `WOB_RAW_REWARD_GLOBAL`,
   `WOB_REWARD_GLOBAL` and reason if that call ended an active episode.

The script does not replace the task's handlers and does not generate rewards. The server:

- accepts bounded event payloads only for active trials;
- validates the seed, task and time budget, and requires finite rewards;
- records only the first terminal result.

A reload or a second episode start makes the trial unscorable.

**Success is the full upstream reward:** `task_success` holds only when the raw reward is `1`.
`click-checkboxes` gives partial credit (`r / elems`, between -1 and 1), so any positive reward is reported
separately as `positive_reward` and never counted as success. The pilot counted `raw_reward > 0`. For
`click-test-2` the two rules give the same result.

## Live tasks: recorded, never graded

Live sites change content, layout and availability without notice, so live results are **not success
labels**.

- `scorable` is true when the execution completed.
- `task_success` is always `null`, and `graded` is `false`.
- `advisory_answer_match` checks a regex against the agent's final text, for two of the three tasks. It
  only helps spot obviously wrong answers. It is not a verdict, and a page change can break it.

Summaries report live tasks under `by_target.<target>.live`, separately from MiniWoB. Read live runs as
qualitative evidence: transcripts, tool calls, elapsed time and token use. The Steam task, for example,
exposed Kitsune issues kitsune#152 (`browser_find` ignored natural-language queries) and kitsune#137
(post-action snapshots from the top of the page).

## Tool policy and integrity limits

Both targets get the same UI allowlist (`UI_TOOLS`), which excludes code execution (`browser_evaluate`,
`browser_run_code_unsafe`), workflows, batches, the filesystem, the shell and raw network access. Observed
tool names and unsafe navigation schemes are audited after each run.

The reason: MiniWoB rewards are client-side JavaScript state, so an agent with arbitrary page JS could call
`core.endEpisode` or change the reward globals instead of solving the task.

**This is not a hardened anti-cheating boundary.** The reward comes from browser-side upstream code, not a
privileged independent service. A malicious agent that found an unexpected tool or browser surface could
still forge it. Do not use this track to evaluate adversarial agents or to claim a standard MiniWoB score.

## Artifacts

Outputs go to `artifacts/external/<pair-id>/` (private, gitignored):

- `pair-manifest.json`, `pair-summary.json`, `external-summary.json` (with `external_task`/`external_kind`);
- per-run `evaluation.json`, agent logs, final text and resource files;
- `suite-summary.json` in the first pair's directory, with `by_target.<target>.miniwob` (successes,
  positive rewards) and `.live` (completions, advisory matches).

See [resources](resources.md) before interpreting RAM/CPU values.

## History

The 2026-10-18 pilot ran `click-test-2` once per target with `gpt-6.1-sol`. Both targets got the original
raw reward 1 ([report](results/2026-10-18-miniwob.md)). Later full-suite reports ("MiniWoB both pass")
ran that same single pair. Those results belong to `miniwob-mcp-ui-pilot` and are not `external-v1`
scores.

Validation on 2026-10-28 (Opus subscription, Kitsune v0.7.0; a check, not a cohort):

- `mw-login-user` and `mw-click-checkboxes` got raw reward 1 on both targets.
- On `live-wikipedia-firefox-release`, both agents answered November 9, 2004. The run then exposed
  a prompt bug: it asked for an "Initial release" label, but the infobox labels the row "Release"
  (`released = 2004-11-09`). The prompt and the advisory regex were fixed before the freeze.

Still needed before making comparative claims: repeated and counterbalanced attempts, more seeds per task,
and confidence intervals.

References:

- https://miniwob.farama.org/
- https://github.com/Farama-Foundation/miniwob-plusplus
- https://github.com/ServiceNow/webarena-verified
