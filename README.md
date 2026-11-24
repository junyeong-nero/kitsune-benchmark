# Kitsune browser benchmark

Two agent-driven browser benchmarks. Both grade what the site or fixture server actually received, not the agent's reply.

| | Four-way (WebArena-Pro) | Local fixtures |
| --- | --- | --- |
| **Purpose** | Compare browser tools on realistic web apps | Find browser-tool bugs on any desktop OS |
| **Tools (arms)** | Aside CLI REPL · EgoLite CLI · Playwright MCP · Kitsune MCP | Playwright MCP · Kitsune MCP |
| **Agent** | Claude Code on `claude-opus-5-5`, run twice: `claude-api` (API key) first, then `claude` (subscription) | Claude Code on `claude-opus-5-5`, `claude` (subscription) only |
| **Tasks** | 26 [WebArena-Pro](https://github.com/McGill-NLP/webarena-pro) tasks (19 test, 7 dev) | 12 original loopback fixtures |
| **Total** | 26 × 4 × 2 = **208 attempts** | 12 × 2 = **24 attempts** |
| **Hosts** | macOS agent host + Linux Docker site host | macOS, Linux or Windows; nothing else |

Attempts run serially and the starting arm rotates by task. Codex is in neither matrix.

## How to run

Read the [running guide](docs/running.md) first: it covers setup, billing guards, output handling and measurement rules.

### Four-way (macOS)

```sh
python3 benchmark.py                                                     # print the plan; no model, browser or site access
python3 benchmark.py --execute --harness claude-api --allow-api-billing  # step 1: 104 API-key cells
python3 benchmark.py --execute --harness claude                          # step 2: 104 subscription cells
```

Execution needs an agent host, a site host and a few environment variables: see [setup](docs/running.md#setup).

### Local fixtures (macOS / Windows)

Needs Node/npm, `uv`, a signed-in native `claude` CLI and a Kitsune checkout synced with `uv sync --locked`
([details](docs/running.md#local-fixture-track-macos--windows)).

```sh
# macOS
npm ci && PLAYWRIGHT_SKIP_BROWSER_GC=1 npx playwright install firefox
export BENCH_KITSUNE_CHECKOUT=/path/to/kitsune
python3 local.py --execute --task confirm    # 2-cell smoke; drop --task for all 24
```

```powershell
# Windows (PowerShell)
npm ci; $env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"; npx playwright install firefox
$env:BENCH_KITSUNE_CHECKOUT = "C:\path\to\kitsune"
uv run --no-project python local.py --execute --task confirm
```

Offline tests: `python3 -m unittest discover -s tests -v`.

## Results

### Four-way, WebArena-Pro

The last full run (2026-11-20) predates the current matrix: it compared Claude Code (subscription) with Codex.

[![WebArena-Pro four-way result](docs/assets/2026-11-20-webarena-pro-four-way.svg)](docs/results/2026-11-20-webarena-pro-four-way.md)

| Tool | Claude Code passes /26 | Codex passes /26 | Mean input per attempt (Claude / Codex) | Mean tool calls (Claude / Codex) |
| --- | ---: | ---: | ---: | ---: |
| Kitsune MCP | 13 | 12 | 283k / 414k | 14.0 / 15.8 |
| Playwright MCP | 13 | 12 | 660k / 809k | 29.8 / 35.1 |
| Aside CLI | 12 | 12 | 463k / 512k | 16.1 / 15.6 |
| EgoLite CLI | 12 | 12 | 360k / 622k | 12.8 / 17.5 |

Kitsune and Playwright passed the same tasks under each model. On the 12 tasks every tool solved, Kitsune used
39% (Claude) and 87% (Codex) of Playwright's input; this is not a general success-rate or latency advantage.

[Kitsune v0.8.2 release check](docs/results/2026-11-23-kitsune-0.8.2-claude-api.md) (2026-11-23, Kitsune arm
only, `claude-api`): 12/26 vs 13/26 on 2026-11-20. Only `wap-077` changed, and input and calls were within 1–2%: no
material change.

[Kitsune main `c7149a8` check](docs/results/2026-11-24-kitsune-main-c7149a8-claude-api.md) (2026-11-24, Kitsune arm only,
`claude-api`), after the #613–#619 fixes: 13/26. Only `wap-077` changed (the agent's reading); input fell 18% and tool errors
fell from 15 to 7. Transcript review filed [Kitsune #627–#635](https://github.com/junyeong-nero/kitsune/issues/627).

### Local fixtures

[First full run](docs/results/2026-11-23-local-windows.md) (2026-11-23, Windows 11, Claude Code `claude` subscription,
Kitsune `c957c5f`):

| Tool | Passed | Mean calls | Mean input per attempt | Tool errors | Median seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kitsune MCP | 12/12 | 3.3 | 32.5k | 0 | 16.0 |
| Playwright MCP | 12/12 | 7.3 | 65.7k | 0 | 18.6 |

No Windows-specific bug: every Kitsune bridge command succeeded and no browser or bridge process outlived its attempt.
The fixtures are near the ceiling for this model, so this is a compatibility check, not a tool ranking.

## Docs

- [Running guide](docs/running.md)
- [Result reports](docs/results/README.md)
- [Documentation index](docs/README.md), including the [archive](docs/archive/README.md) of reports from retired harnesses
