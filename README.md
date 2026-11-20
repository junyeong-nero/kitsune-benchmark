# Kitsune browser benchmark

One benchmark: **26 WebArena-Pro tasks × two subscription models × four browser tools = 208 attempts**. Run Claude Code (`claude-opus-5-5`) first, then Codex (`gpt-6.1-sol`). Each gets one attempt with Aside CLI REPL, EgoLite CLI, Playwright MCP and Kitsune MCP. Attempts are serial; starting arm rotates by task. The first 19 tasks are test, the last seven dev.

[Latest report: results, tokens and tool calls for both models](docs/results/2026-11-20-webarena-pro-four-way.md) · [Past reports](docs/results/README.md) · [Retired harnesses and their instructions](https://github.com/junyeong-nero/kitsune-benchmark/tree/1ef91e1)

```sh
python3 benchmark.py                                 # print the plan; no model/browser/site access
python3 benchmark.py --execute                       # after setup: all 208, output under runs/
python3 benchmark.py --execute --task wap-199 --out runs/smoke  # optional 8-cell smoke
```

`npm run benchmark -- --execute` is equivalent. Each execution creates a **new** output directory, with a plan, private transcripts and a flushed `results.jsonl`. A recorded task failure or 600-second agent timeout does not stop the matrix. Infrastructure and other agent errors stop it for inspection; never interpret a partial run as 208 failures. No automatic quota retry or resume. Do not publish the raw directory: it may contain site data and auth material.

## Setup

**Agent host (tested on macOS).** Install Python 3.10+, Node/npm, and authenticated `claude` and `codex` CLIs with access to the models above. Install/open the signed Aside and EgoLite apps and ensure `aside` and `ego-browser` are on PATH. These two arms **use the active app profiles**; use a dedicated OS account. The Codex CLI arms need `danger-full-access` to reach the local apps; their UI-only restriction is an instruction, not an OS sandbox. Use only trusted benchmark sites. Playwright and Kitsune launch isolated headless Firefox. Do not start a second benchmark on the same sites/profiles.

```sh
npm ci && npm run setup:firefox
# A separate checkout, not the user's running Kitsune installation:
git clone https://github.com/junyeong-nero/kitsune.git ../kitsune-bench-runtime
git -C ../kitsune-bench-runtime checkout 4e6d6fb
uv sync --locked --directory ../kitsune-bench-runtime
export BENCH_KITSUNE_CHECKOUT="$(cd ../kitsune-bench-runtime && pwd)"
export BENCH_PLAYWRIGHT="$PWD/node_modules/.bin/playwright-mcp"
```

**Site host.** Use a disposable Linux Docker host with `uv`, preferably separate from a memory-constrained agent host. Site resets destroy changes. Use the upstream revision below and disable **container internet egress** on this host while allowing localhost/forwarded clients to access the sites. The flight-search backend otherwise geolocates the host; prepare rejects an environment other than US/USD.

```sh
git clone https://github.com/McGill-NLP/webarena-pro.git
git -C webarena-pro checkout 42f4a076
cd webarena-pro/webarena-pro-core
uv sync --python 3.12 --locked
PLAYWRIGHT_SKIP_BROWSER_GC=1 uv run python -m playwright install firefox
WP_URL_MODE=port uv run webarena-pro env start flight-search jobportal minerva-lite password-manager pipedrive thunderbird travelmap x-lite --wait-timeout 300
export BENCH_WAP_CORE="$PWD"  # set this on the agent host too, to this site-host path
```

On a disposable Linux Docker host using the default `172.17.0.0/16` bridge and iptables backend, the run used these forwarding rules (adapt to your actual bridge; reapply after a host restart). They affect containers on that bridge, not just the selected apps:

```sh
sudo iptables -I DOCKER-USER -s 172.17.0.0/16 -m conntrack --ctstate NEW ! -d 10.0.0.0/8 -j REJECT
sudo iptables -I DOCKER-USER -s 172.17.0.0/16 -d 172.16.0.0/12 -j RETURN
sudo iptables -I DOCKER-USER -s 172.17.0.0/16 -d 192.168.0.0/16 -j RETURN
```

For local Core, put `uv` on PATH and leave `BENCH_WAP_SSH` unset. For a Codespace, install Core and start the sites there, then on the agent host:

```sh
export CS=your-codespace-name
gh codespace cp four-way/framework/wap_core.py "remote:/tmp/wap_core.py" -c "$CS"
export BENCH_WAP_SSH="gh codespace ssh -c $CS --" BENCH_WAP_SCRIPT=/tmp/wap_core.py
export BENCH_WAP_CORE=/absolute/remote/path/to/webarena-pro-core
gh codespace ports forward 3001:3001 4601:4601 4701:4701 5201:5201 7001:7001 7101:7101 9101:9101 3201:3201 -c "$CS"  # leave running in another terminal
```

Check credentials/quota, site availability, disk and memory **before** a full run. The runner does not start, pay for, or stop a Codespace. Stop forwarding and stop/delete the disposable site host and its private `/tmp/wap-bench/` auth states when finished.

## Measurement

Every attempt recreates its sites from seed and signs the assigned browser in **before** starting the timer. Core grades final server state and/or the `FINAL ANSWER:` value. No credit from agent claims or a trajectory judge. `agent_seconds` excludes setup and grading. `input` includes cache reads; `cached_input` is a subset, not additional tokens. Do not equate tool calls with individual clicks: CLI scripts and Kitsune Python calls can batch operations. See the [task manifest](four-way/testset/webarena-pro.json) and report for selection criteria and limitations.

To summarize a new run and export shareable metrics without transcripts: `python3 summary.py runs/<timestamp>/results.jsonl --csv metrics.csv`.

Offline checks: `python3 -m unittest discover -s tests -v`. No agent, browser or network credentials required.
