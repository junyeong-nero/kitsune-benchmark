# Full-native track (`kitsune-full-native-v1`): Kitsune's own tool groups

[Documentation index](README.md) · [Running guide](running.md) · [Personal browsing](personal-browsing.md) ·
[Component gallery](gallery.md)

**Scope:** a Kitsune-only track, reported apart from the head-to-head
([#109](https://github.com/junyeong-nero/kitsune-benchmark/issues/109), split from
[#4](https://github.com/junyeong-nero/kitsune-benchmark/issues/4)). Every other model track gives both servers the
same 23-tool UI allowlist. So Kitsune's own groups have never been measured with a model: `automation` (batches,
retries, workflows, parallel tabs), `read` (page text, forms, links), `network` and `browser_evaluate`. This track
compares two Kitsune configurations on the same units. It has **no Playwright arm**, because Playwright MCP has
nothing equivalent. Its numbers are never pooled with, or set beside, the Playwright/Kitsune tracks.

## Arms

| Arm | Kitsune settings (bridge and MCP server) | What the agent's `tools/list` shows |
| --- | --- | --- |
| `core` | `KITSUNE_CAPS=core` | Kitsune's default `core` group (27 tools on main `286cfe5`: Playwright MCP's 25, `browser_resume`, `browser_ask_user`) |
| `gateway` | `KITSUNE_CAPS=all`, `KITSUNE_PUBLISH=core` | The same core tools plus the gateway tools `browser_tools_search`, `browser_tools_call` and `browser_tools_publish`, which reach every other group except `storage` and `history` |

`gateway` is the setup Kitsune's README recommends: a small initial tool list, with discovery through the gateway.
Both arms set `KITSUNE_CAPS` explicitly, so neither depends on Kitsune's default. The bridge enforces it too
(capability errors below). The tool gateway arrived in Kitsune v0.4.0 (kitsune#229), so older Kitsune can run only
the `core` arm.

**No benchmark allowlist.** In both arms the agent sees exactly what Kitsune publishes. That includes
`browser_evaluate`, which the head-to-head allowlist leaves out, and in `gateway` every automation, read, network
and inspect tool. The tasks still say to use only the page UI. Here that is a request, not an enforced boundary. The
graders read the fixture servers' state as in their own tracks and are not hardened against an agent that writes
that state through scripts.

## Units

Existing tasks where orchestration should pay, reused unchanged: same catalog, fixtures, prompts and graders. The
frozen taskset files are not modified.

| Units | Tasks | What should pay |
| --- | --- | --- |
| Multi-tab research | `pb-research-01..04` | Several sources in several tabs: parallel reads, page text |
| Research → draft | `pb-handoff-01..04` | Collect from tabs, then fill a draft: batches, form reads |
| Long pages | `pb-longpage-01..04` | Lookup on long pages: page text and Markdown instead of snapshots |
| Batch selection | `ui-table/crowded`, `ui-table/isolated` | Gallery `ui-table`: select every low-stock row across pages, on both layouts |

That is 14 units × 2 arms = **28 agent runs per data variant** (`--variant 0|1|2`, default 0). Personal units run as
on the [personal track](personal-browsing.md): user-channel seeding and viewport reports. Gallery units run as on the
[gallery track](gallery.md): the harness opens the task tab.

## Protocol

- Each run is a Kitsune-only pair (`targets: ["kitsune"]`) with its own fixture server, Firefox profile, bridge and
  ports, because `KITSUNE_CAPS` is read by the bridge at start.
- Both arms of a unit run back to back. The first arm alternates by unit: `core` first on even positions, `gateway`
  first on odd ones. Runs are sequential, never in parallel.
- Model and harness defaults are the personal/gallery configs' (Claude Code on the subscription, `claude-opus-5-5`,
  medium). Time limits are those tracks' too: 180 s personal, 240 s gallery. `--elicitation` and the harness options
  work as on the personal track.
- The track stops, without retry, after an unscorable run (`unscorable_pair`, or `session_limit`), on a Kitsune
  revision change, or at `--budget-usd` (API-key harnesses only). Ordinary task failures continue.
- The runs use `kitsune_benchmark/full_native_session.py`, a subclass of the frozen personal/gallery relay
  (`personal_session.py`, unchanged), with the same setup, inventories and evidence. It counts a
  `browser_tools_call` as the tool it runs: a gateway `browser_tabs close` is a close attempt, and the tab call is
  recorded under that tool with `via: "browser_tools_call"`. It blocks out-of-fixture navigation for every `url` in
  a call's arguments, nested ones included, so container commands (`browser_batch` and the like) cannot leave the
  fixture either. The call itself reaches Kitsune unchanged. It waits up to 330 s for the agent's calls, not the
  frozen relay's 60 s: Kitsune lets a batch, parallel, workflow or resume call run 300 s, plus 30 s to settle and
  report its partial progress. The harness's own setup and inventory calls keep the 60 s limit.

## Measures

Every run's `full-native-summary.json` and the suite's `suite-summary.json` hold `analysis`, computed from the
graders' verdicts and each run's `events.jsonl`:

| Field | Meaning |
| --- | --- |
| `successes`, `scorable_success_rate` | The tracks' own primary verdicts (`task_success`); unscorable runs are reported, not scored |
| `input_tokens`, `uncached_input_tokens`, `output_tokens` | As on the other tracks (total input includes cached input), with `reported_runs`/`missing_runs` |
| `mcp_calls`, `model_requests` | Agent-visible MCP calls; deduplicated model requests (Claude Code `token_attribution.requests`) |
| `agent_calls`, `ran_calls` (per run, in `native`) | The agent's MCP calls in its events, and those that reached Kitsune (see below) |
| `gateway_calls`, `gateway_called_tools`, `runs_using_gateway` | Calls to each gateway tool, and which tools `browser_tools_call` ran |
| `container_calls`, `batch_steps`, `runs_using_containers` | Container calls (direct or through the gateway) and the commands packed into them: `browser_batch` commands, `browser_parallel` commands across sequences, the wrapped command of a `browser_retry`, one per `browser_broadcast`. A nested `parallel` command counts the commands of its sequences and a nested `retry` its wrapped command, at any depth. A `browser_workflow` counts as a call without steps |
| `capability_errors` | Results that name `capability_restricted` (the bridge refused a group), `tool_not_published` or `not_supported`, by code, including failed steps inside container results. A result's text is read, or its `structuredContent` when it has no text, so a code both carry counts once |
| `unlisted_tool_calls` | Calls to a tool not in Claude Code's system-init tool list that did not run: Claude Code refused them |
| `published_tools`, `gateway_published` | Per run, how many tools Kitsune listed to the agent in its first `tools/list` (all its pages, not later listings) and whether the gateway was among them, a check that the arm ran as configured |

Gateway, container, step, capability and error counts cover only the calls that reached Kitsune. Claude Code refuses,
without running it, a call to a tool not in its system-init list, and the relay refuses an out-of-fixture navigation.
A call to a tool in the list ran unless the relay refused it. A call to an unlisted tool ran only if the relay
recorded it (evidence `tab_calls`, with `via` for gateway calls), which happens once Claude Code refreshes its list
after `browser_tools_publish`; such recorded calls go to the latest unlisted calls of the same tool. So a call that
ran after a refresh is not unlisted, and the harness's own `nonexistent_tool_calls`, which reads the init list only,
is not used here.

`analysis.arms` totals each arm over all its runs, failures included. `analysis.by_category` splits them by unit
category. `analysis.units` has one row per unit and arm. `analysis.joint_successes` compares input, calls and model
requests only on units both arms solved in that suite: `ratio_gateway_to_core` divides the summed totals, and
`unit_ratios_median` is the median per-unit ratio. A run without events has `native: null`: unmeasured, not zero use.

## Run

```sh
# Plan: units, arms, schedule, planned runs. No browser or model calls.
uv run --locked python -m kitsune_benchmark full-native

# One unit, both arms: two agent runs on your subscription.
uv run --locked python -m kitsune_benchmark full-native --unit pb-longpage-01 \
  --kitsune-project artifacts/vendor/kitsune-pinned --execute

# All 14 units, both arms, one variant: 28 agent runs.
uv run --locked python -m kitsune_benchmark full-native --variant 0 \
  --kitsune-project artifacts/vendor/kitsune-pinned --execute

# Recompute the analysis of a recorded suite offline (no model, browser or network).
uv run --locked python -m kitsune_benchmark.full_native \
  artifacts/full-native/<first-pair-id>/suite-summary.json --output review.json
```

Artifacts go to `artifacts/full-native/<pair-id>/`, with `full-native-summary.json` per run and `suite-summary.json`
in the first run's directory. The exit code is 0 when every planned run is scorable, 3 otherwise, and 2 on input
errors.

## Reading the results

- This is a within-Kitsune comparison. Do not compare its numbers with Playwright's or with head-to-head Kitsune
  runs. The tool surface, the allowlist and the run order all differ.
- Lead with success on both arms. Read cost only on joint successes, with failures and unscored runs beside it.
- One run per unit and arm is an observation, not an effect. The issue's question, whether orchestration pays, needs
  repeated, counterbalanced runs before any claim.
- Claude Code may or may not refresh its tool list after `browser_tools_publish`. A call to a newly published tool
  it does not list shows up as an `unlisted_tool_calls` count, not as a capability error or container use; one it
  runs after a refresh counts as use.

Not covered yet: repeated attempts (`--attempts`/`--order` as on the full suite), counting container steps that close
or navigate starting tabs as close attempts (custody is still checked from the inventory after every call), and
`network`-specific units.
