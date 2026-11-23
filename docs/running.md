# Running the benchmark

[Documentation index](README.md) · [Project README](../README.md)

Two runners: the [four-way WebArena-Pro matrix](#setup) (`benchmark.py`, macOS agent host + Linux site host) and the
[local fixture track](#local-fixture-track-macos--windows) (`local.py`, macOS, Linux or Windows).

`benchmark.py` plans or executes one serial matrix: 26 WebArena-Pro tasks × 4 browser arms × 2 billing modes of
Claude Code on `claude-opus-5-5`, **208 attempts**. Codex is not in the matrix.

| Harness | Billing | Order |
| --- | --- | --- |
| `claude-api` | `ANTHROPIC_API_KEY` (pay as you go) | first 104 cells |
| `claude` | claude.ai subscription | last 104 cells |

Both harnesses run the same Claude Code command, prompt, tools and timeout; only the credential differs.
Within each harness the starting arm rotates by task (Aside → EgoLite → Playwright MCP → Kitsune).

## Setup

### 1. Agent host (tested on macOS)

- Python 3.10+ and Node/npm
- A `claude` CLI signed in to a subscription with access to `claude-opus-5-5`
- `ANTHROPIC_API_KEY` exported for the `claude-api` cells
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
gh codespace ssh -c "$CS" -- 'cat > /tmp/wap_core.py' < four-way/framework/wap_core.py
export BENCH_WAP_SSH="gh codespace ssh -c $CS --" BENCH_WAP_SCRIPT=/tmp/wap_core.py
export BENCH_WAP_CORE=/absolute/remote/path/to/webarena-pro-core
gh codespace ssh -c "$CS" -- -N $(for p in 3001 4601 4701 5201 7001 7101 9101 3201; do printf -- '-L %s:localhost:%s ' $p $p; done)  # leave running in another terminal
```

The runner does not start, pay for or stop a Codespace.

> [!WARNING]
> Forward the ports over SSH (`-L`), not with `gh codespace ports forward`. Under parallel load, that
> forwarder drops requests: in four tabs walking Travelmap pages, 6–7 of 189 page requests never reached the
> site and timed out after 15 s, in each of two runs. Over SSH it was 0 of 189, also twice (kitsune#605).
> `gh codespace cp` fails on a remote `/tmp` path, hence the `ssh … cat` copy above.

## Run

Run the two billing modes as separate steps, and check the cost of step 1 before starting step 2.

```sh
python3 benchmark.py                                                      # print the 208-cell plan; no model/browser/site access
python3 benchmark.py --execute --allow-api-billing --task wap-199 --out runs/smoke  # optional 8-cell smoke (4 API + 4 subscription)
python3 benchmark.py --execute --harness claude-api --allow-api-billing   # step 1: 104 API-key cells
python3 benchmark.py --execute --harness claude                           # step 2: 104 subscription cells
```

`--task`, `--harness` and `--arm` repeat and combine; a subset keeps the full matrix's order.
`npm run benchmark -- <args>` is equivalent.

**Billing guards**

- Any plan containing `claude-api` cells refuses to execute without `--allow-api-billing` and `ANTHROPIC_API_KEY`.
- `claude` cells never receive `ANTHROPIC_API_KEY`; `claude-api` cells never receive `CLAUDE_CODE_OAUTH_TOKEN`.
- Each cell records Claude Code's `apiKeySource` as `api_key_source`: it must be `ANTHROPIC_API_KEY` for `claude-api`
  and `none` for `claude`. A mismatch is recorded as `billing_mismatch` and stops the run. The check runs after the
  attempt, so that one attempt has already been billed.
- There is no per-attempt spending cap. `cost_usd` is Claude Code's client-side estimate; the Anthropic Console is the billing source.

**Output and stopping**

- Each execution creates a **new** directory (default `runs/<timestamp>`) with `plan.json`, one private transcript per cell
  and a flushed `results.jsonl`.
- A graded failure or a 600-second agent timeout does not stop the matrix.
- Infrastructure errors, other agent errors and `billing_mismatch` **stop** it for inspection. Never read a partial run as failures.
- There is no automatic quota retry or resume; rerun the remaining cells with filters into a new `--out`.
- **Do not publish the raw output directory:** it may contain site data and auth material.

**Before and after**

- **Before:** check credentials, API balance and subscription quota, site availability, disk and memory.
- **After:** stop port forwarding, then stop or delete the disposable site host and its private `/tmp/wap-bench/` auth states.

## Measurement

- Every attempt recreates its sites from seed and signs the assigned browser in **before** the timer starts.
- Core grades the final server state and/or the `FINAL ANSWER:` value. No credit comes from agent claims or a trajectory judge.
- `agent_seconds` excludes setup and grading.
- `input` includes cache reads; `cached_input` is a subset of it, not additional tokens.
- A tool call is not a click: CLI scripts and Kitsune Python calls can batch several operations.
- `claude-api` and `claude` are reported as separate cohorts, even though the harness is identical.

The [task manifest](../four-way/testset/webarena-pro.json) gives the selection criteria.

## Local fixture track (macOS / Windows)

`local.py` plans or executes a smaller matrix for finding browser-tool bugs on any desktop OS, without the site host,
Aside or EgoLite: **12 original loopback fixtures × Playwright MCP and Kitsune MCP = 24 attempts**, under Claude Code
on `claude-opus-5-5` with the `claude` subscription only (no `claude-api`, no Codex), 300-second timeout, starting arm
alternating by task.

The fixtures cover dates, autocomplete, pagination, `confirm()`, delayed content, shadow DOM, iframes and a wizard
([tasks](../local-tasks/tasks.json), [pages](../local-tasks/pages.py)). Each attempt gets a new fixture server, and it
passes only if that server received the expected form submission **exactly once**. These tasks are near the ceiling
for frontier agents: read failures as bug leads to inspect, not as tool scores. Linux works the same way as macOS.

### Requirements

- Python 3.10+, Node/npm and `uv`
- A **native** `claude` CLI signed in to a subscription. Check it with `claude auth status` (`"loggedIn": true`).
- A Kitsune checkout synced with `uv sync --locked`. This is the Kitsune under test; it does not need to be the
  four-way pin. Before any Kitsune cell runs, `local.py` checks `uv sync --locked --check` and stops on a stale
  `.venv` (one without the Windows-only `psutil` broke `browser_run_python` in the first Windows smoke).

### macOS

```sh
npm ci
PLAYWRIGHT_SKIP_BROWSER_GC=1 npx playwright install firefox
uv sync --locked --directory /path/to/kitsune
export BENCH_KITSUNE_CHECKOUT=/path/to/kitsune
python3 local.py                                  # print the 24-cell plan only
python3 local.py --execute --task confirm         # 2-cell smoke
python3 local.py --execute                        # all 24, output under runs/local-<timestamp>/
```

### Windows (PowerShell)

Install Claude Code with the native installer (`irm https://claude.ai/install.ps1 | iex`, which puts
`%USERPROFILE%\.local\bin\claude.exe` on `PATH`), then run `claude` once and `/login`. A Claude Desktop sign-in does
not sign in the CLI.

```powershell
npm ci
$env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"; npx playwright install firefox
uv sync --locked --directory C:\path\to\kitsune
$env:BENCH_KITSUNE_CHECKOUT = "C:\path\to\kitsune"
uv run --no-project python local.py --execute --task confirm   # or `python` from a real install
uv run --no-project python local.py --execute
```

- If `claude` resolves to an npm `claude.cmd` shim, set `BENCH_CLAUDE` to a `claude.exe`. `cmd.exe` cannot pass
  the multi-line prompt.
- `npm run setup:firefox` and `npm run benchmark` use POSIX shell syntax; use the commands above instead.

### Output and stopping

- Both arms run isolated headless Firefox. Kitsune gets a private bridge, home, token and ports per attempt; the
  user's own Kitsune bridge and profiles are not touched.
- Each Kitsune attempt keeps `<attempt>-runtime/` next to its transcript: `bridge.log`, `firefox.log` and
  `audit.json` (the bridge's command audit, without typed values or secrets). Start there when a cell fails.
- `--task` and `--arm` repeat and combine. Stopping rules match the four-way runner; `api_key_source` must be `none`,
  otherwise the cell is recorded as `billing_mismatch` and the run stops.
- **Do not publish the raw output directory.**

## Analysis and tests

```sh
python3 summary.py runs/<timestamp>/results.jsonl --csv metrics.csv  # summary + shareable metrics, no transcripts
python3 -m unittest discover -s tests -v                             # offline; no agent, browser or credentials
BENCH_TEST_FIREFOX=1 python3 -m unittest discover -s tests -p test_local.py  # also solve every fixture in Firefox, no model
```
