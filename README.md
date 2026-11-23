# Kitsune browser benchmark

Four browser tools, two subscription agents, the same 26 [WebArena-Pro](https://github.com/McGill-NLP/webarena-pro) tasks:

| | |
| --- | --- |
| **Tools (arms)** | Aside CLI REPL · EgoLite CLI · Playwright MCP · Kitsune MCP |
| **Agents** | Claude Code (`claude-opus-5-5`), then Codex (`gpt-6.1-sol`) |
| **Tasks** | 26 (first 19 test, last 7 dev), one attempt per tool and agent |
| **Total** | 26 × 4 × 2 = **208 attempts**, serial; the starting arm rotates by task |

[![WebArena-Pro four-way result](docs/assets/2026-11-20-webarena-pro-four-way.svg)](docs/results/2026-11-20-webarena-pro-four-way.md)

**Docs:** [Latest report](docs/results/2026-11-20-webarena-pro-four-way.md) ·
[All reports](docs/results/README.md) · [Documentation index](docs/README.md) ·
[Retired harnesses](https://github.com/junyeong-nero/kitsune-benchmark/tree/1ef91e1)

## Quick start

```sh
python3 benchmark.py                                            # print the plan; no model/browser/site access
python3 benchmark.py --execute                                  # after setup: all 208, output under runs/
python3 benchmark.py --execute --task wap-199 --out runs/smoke  # optional 8-cell smoke
python3 benchmark.py --task wap-238 --harness codex --arm kitsune --arm playwright  # a subset; filters repeat
```

`npm run benchmark -- --execute` is equivalent.

- Each execution creates a **new** output directory with the plan, private transcripts and a flushed `results.jsonl`.
- A recorded task failure or a 600-second agent timeout does not stop the matrix.
- Infrastructure and other agent errors **stop** it for inspection. Never read a partial run as 208 failures.
- There is no automatic quota retry or resume.
- **Do not publish the raw output directory:** it may contain site data and auth material.

## Setup

### 1. Agent host (tested on macOS)

Requirements:

- Python 3.10+ and Node/npm
- Authenticated `claude` and `codex` CLIs with access to the models above
- The signed Aside and EgoLite apps, installed and open, with `aside` and `ego-browser` on `PATH`

```sh
npm ci && npm run setup:firefox
# A separate checkout, not the user's running Kitsune installation:
git clone https://github.com/junyeong-nero/kitsune.git ../kitsune-bench-runtime
git -C ../kitsune-bench-runtime checkout 4e6d6fb
uv sync --locked --directory ../kitsune-bench-runtime
export BENCH_KITSUNE_CHECKOUT="$(cd ../kitsune-bench-runtime && pwd)"
export BENCH_PLAYWRIGHT="$PWD/node_modules/.bin/playwright-mcp"
```

> [!WARNING]
> - The Aside and EgoLite arms **use the active app profiles**. Use a dedicated OS account.
> - The Codex arms need `danger-full-access` to reach the local apps. Their UI-only restriction is an instruction, not an OS sandbox. Use only trusted benchmark sites.
> - Playwright and Kitsune launch isolated headless Firefox.
> - Do not start a second benchmark on the same sites or profiles.

### 2. Site host

Use a disposable Linux Docker host with `uv`, preferably separate from a memory-constrained agent host. Site resets destroy changes.

```sh
git clone https://github.com/McGill-NLP/webarena-pro.git
git -C webarena-pro checkout 42f4a076
cd webarena-pro/webarena-pro-core
uv sync --python 3.12 --locked
PLAYWRIGHT_SKIP_BROWSER_GC=1 uv run python -m playwright install firefox
WP_URL_MODE=port uv run webarena-pro env start flight-search jobportal minerva-lite password-manager pipedrive thunderbird travelmap x-lite --wait-timeout 300
export BENCH_WAP_CORE="$PWD"  # set this on the agent host too, to this site-host path
```

### 3. Block container internet egress

Disable container internet egress on the site host while still allowing localhost and forwarded clients to reach the sites. Otherwise the flight-search backend geolocates the host, and prepare rejects any environment other than US/USD.

On a Docker host with the default `172.17.0.0/16` bridge and the iptables backend, the run used these rules. Adapt them to your bridge and reapply after a host restart. They affect every container on that bridge, not just the selected apps.

```sh
sudo iptables -I DOCKER-USER -s 172.17.0.0/16 -m conntrack --ctstate NEW ! -d 10.0.0.0/8 -j REJECT
sudo iptables -I DOCKER-USER -s 172.17.0.0/16 -d 172.16.0.0/12 -j RETURN
sudo iptables -I DOCKER-USER -s 172.17.0.0/16 -d 192.168.0.0/16 -j RETURN
```

### 4. Connect the agent host to the sites

**Local Core:** put `uv` on `PATH` and leave `BENCH_WAP_SSH` unset.

**Codespace:** install Core and start the sites there, then on the agent host:

```sh
export CS=your-codespace-name
gh codespace cp four-way/framework/wap_core.py "remote:/tmp/wap_core.py" -c "$CS"
export BENCH_WAP_SSH="gh codespace ssh -c $CS --" BENCH_WAP_SCRIPT=/tmp/wap_core.py
export BENCH_WAP_CORE=/absolute/remote/path/to/webarena-pro-core
gh codespace ports forward 3001:3001 4601:4601 4701:4701 5201:5201 7001:7001 7101:7101 9101:9101 3201:3201 -c "$CS"  # leave running in another terminal
```

The runner does not start, pay for or stop a Codespace.

### 5. Before and after a run

- **Before:** check credentials and quota, site availability, disk and memory.
- **After:** stop port forwarding, then stop or delete the disposable site host and its private `/tmp/wap-bench/` auth states.

## Measurement

- Every attempt recreates its sites from seed and signs the assigned browser in **before** the timer starts.
- Core grades the final server state and/or the `FINAL ANSWER:` value. No credit comes from agent claims or a trajectory judge.
- `agent_seconds` excludes setup and grading.
- `input` includes cache reads; `cached_input` is a subset of it, not additional tokens.
- A tool call is not a click: CLI scripts and Kitsune Python calls can batch several operations.

The [task manifest](four-way/testset/webarena-pro.json) and the [report](docs/results/2026-11-20-webarena-pro-four-way.md) give the selection criteria and limitations.

## Analysis and tests

```sh
python3 summary.py runs/<timestamp>/results.jsonl --csv metrics.csv  # summary + shareable metrics, no transcripts
python3 -m unittest discover -s tests -v                             # offline; no agent, browser or credentials
```
