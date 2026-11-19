# Four-way browser benchmark

The same model, through Claude Code or Codex on a subscription, completes the same local web tasks with
**Aside CLI REPL, EgoLite CLI, Playwright MCP and Kitsune MCP**. The grader checks the values the fixture server
actually received, not the model's reply. This is an end-to-end comparison: it includes each browser and tool
interface, not only browser speed.

- `framework/`: loopback fixture server, adapters that start and clean up the four tools, transcript parser
- `testset/`: the original local UIs, prompts, expected submissions and tests
- `scripts/run.py`: plans and runs attempts, rotates arm order, writes JSONL results and raw transcripts
- `scripts/analyze.py`: report on success, tool calls, token usage, recurring tool errors and failure causes
- `scripts/publish.py`: builds the test set and run logs as a Hugging Face dataset and uploads it
- `scripts/figure.py`: renders the summary SVG from `summary.json`, with icons from `figure-icons/`
- `scripts/kitsune_runtime.py`: starts a private Kitsune bridge and headless Firefox for a given checkout
- `framework/wap_core.py`, `framework/wap_login.js`: WebArena-Pro reset, sign-in and grading (see below)

Run every command from this directory. Results: [2026-11-19 report](../docs/results/2026-11-19-four-way-12-task.md).

## Test set

Operations that isolate a failure cause (dates, selection, autocomplete) follow the
[MiniWoB++ environment list](https://miniwob.farama.org/environments/list/). Grading shopping and collaboration
tasks by their final state follows [WebArena](https://arxiv.org/abs/2307.13854). The 12 tasks are original and
small; they are not data or official scores from either benchmark.

| Task | Ability tested | Passes when |
|---|---|---|
| `dispatch` | a date plus different form controls | contact, date and delivery match; insurance unchecked |
| `preferences` | editing existing state, clearing defaults | the saved notification set matches exactly |
| `directory` | dynamic autocomplete, similar names | the selected branch ID matches, not the typed query |
| `catalog` | combining price, stock and warranty | the cheapest eligible lamp is reserved once, not bought |
| `ticket` | similar records, copying values to another form | the incident's current owner and checkpoint are saved |
| `mail` | reading a correction, draft vs send | a draft only, to the right recipient with the revised code |
| `pager` | client-side pagination, near-duplicate rows | the page-3 order ID with the right amount is refunded |
| `confirm` | native `confirm()` dialog | only Beta is archived |
| `lazy` | waiting for content delayed 2.5 s | a claim for the delayed Busan shipment |
| `shadow` | controls inside an open shadow root | the Team annual plan is subscribed |
| `frame` | a form inside a same-origin iframe | email entered, terms accepted, account created |
| `wizard` | a multi-step wizard with hidden steps | the booking has the right room, guests and breakfast |

Each attempt gets a new server and an empty submission log. An attempt passes only if it submits the correct state
**exactly once**; recovering after a wrong submission is still a failure. One repeat is 12 × 4 = 48 attempts, and
the starting arm rotates per task and repeat. Repeating fixed data checks reliability; it does not add tasks. The
results do not generalize to visual reasoning, real logins or long web navigation.

## WebArena-Pro subset (`--suite webarena-pro`)

The 12 fixtures are near the ceiling: frontier agents pass almost all of them, so they separate tools mainly by cost.
The second suite uses [WebArena-Pro](https://arxiv.org/abs/2611.17955) (NeurIPS 2026 E&D, released 2026-11-13,
[code](https://github.com/McGill-NLP/webarena-pro) MIT). It has 400 human-validated tasks on 20 self-hosted apps
modeled on services such as Pipedrive, Google Flights and Airbnb. Its best published result is 62.3%, from Claude Code
with Opus 5.5 and Codex with GPT 6.1 Sol driving Playwright MCP: the same agents and one of the same tools as here.

`testset/webarena-pro.json` lists **26 tasks (19 test, 7 dev)** chosen so that grading cannot depend on the tool:

- every site is one of the 8 apps whose images are under 150 MB (flight-search, jobportal, minerva-lite,
  password-manager, pipedrive, thunderbird, travelmap, x-lite), so the suite fits a laptop VM;
- every rubric node starts with an authoritative `backend_state` or `answer_match` check. The other tasks need UI
  evidence recorded by WebArena-Pro's own Playwright browser or an LLM judge, which would favor the Playwright arm.

The tasks are multi-step and some span sites, e.g. book the cheapest June weekend trip with flights and lodging, register
for a course that fits a schedule, or reply to every unread email.

### Setup

```sh
brew install colima docker            # Apple Silicon: amd64 images run under Rosetta
colima start --vm-type vz --vz-rosetta --cpu 4 --memory 5 --disk 30
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
git clone https://github.com/McGill-NLP/webarena-pro.git && cd webarena-pro/webarena-pro-core
uv sync --python 3.12 --locked
PLAYWRIGHT_SKIP_BROWSER_GC=1 uv run python -m playwright install firefox   # without the flag it deletes other Firefox builds
WP_URL_MODE=port uv run webarena-pro env start flight-search jobportal minerva-lite password-manager \
  pipedrive thunderbird travelmap x-lite --wait-timeout 300
export BENCH_WAP_CORE="$PWD"
```

Kitsune runs against a private bridge and headless Firefox loading a given checkout's extension. Start one and export
the `BENCH_KITSUNE_*` variables from its `env.json`:

```sh
python3 scripts/kitsune_runtime.py ../../kitsune /tmp/kitsune-rt &   # prints "ready <revision>"
eval "$(python3 -c "import json;d=json.load(open('/tmp/kitsune-rt/env.json'));print(' '.join(f'export {k}={v}' for k,v in d.items() if k.startswith('BENCH_')))")"
uv run --directory "$BENCH_WAP_CORE" python "$PWD/framework/wap_core.py" control /tmp/wap-control   # every task must fail
python3 scripts/run.py --suite webarena-pro --execute --browser-mode existing-profile \
  --arm-mode playwright=isolated --arm-mode kitsune=isolated --harness claude --model claude-opus-5-5 \
  --out runs/wap/claude.jsonl
```

### Per attempt

1. Each of the task's sites is recreated from its seed image. In-place restore is not used: pipedrive's
   `restore-seed-if-empty` keeps earlier attempts' records. Core then signs in the task's user with Playwright Firefox
   and saves a storage state.
2. The harness signs the arm's browser in before the agent starts, as in the paper:

   | Arm | Sign-in |
   |---|---|
   | Playwright MCP | `--storage-state` with the saved cookies |
   | Kitsune | `cookies.set` through the private bridge |
   | EgoLite | CDP `Network.setCookie` in the TaskSpace page |
   | Aside | the site's login form, through the REPL (`framework/wap_login.js`); the REPL exposes no cookie or CDP API |

3. The prompt gives the intent, the site URLs, a UI-only rule and asks for a final `FINAL ANSWER: <answer>` line
   (`done` for action-only tasks). The default timeout is 600 s, the paper's wall budget.
4. `framework/wap_core.py grade` runs the task's evaluation DAG with that answer as `send_msg_to_user(...)`.
   `pass` requires a full score. Each row records `score`, `answer` and the per-rubric `rubrics` trail.

Limits:

- **No LLM judge or UI evidence.** A rubric that the backend check does not prove falls through to strategies that
  get no evidence here, so it fails. This is stricter than the paper, and scores are not comparable to its 62.3%.
- No step budget is enforced, only the wall time. Media tools are not offered (the subset has no media tasks).
- minerva-lite, travelmap and x-lite all use a cookie named `session` on `localhost`, so a browser can be signed in to
  only one of them at a time; no selected task uses two of them.
- Aside and EgoLite use the operator's profiles, so `localhost` cookies remain there and Aside fixture tabs stay open.

## Running

Planning and tests need only the Python 3.10+ standard library.

```sh
python3 scripts/run.py                         # plan only: no login, browser or model calls
python3 -m unittest testset.test_benchmark    # BENCH_TEST_FIREFOX=1 also drives the 12 UIs in real Firefox
```

Execution needs the chosen harness (`claude` or `codex`) installed and logged in, plus the selected tools. In every
mode the browser must reach `127.0.0.1` on this host.

### Existing user profile: `--browser-mode existing-profile`

Uses each product's normal local connection instead of a dedicated test profile or port.

- **Aside**: the app opens the fixture tab (`open -g -a Aside`), and the `./browser` wrapper attaches it with
  `attachBrowserTab` before every call. A one-shot `aside repl` session closes the tabs it opened, so variables and
  snapshot refs do not survive between calls. The REPL cannot close an attached tab, so fixture tabs remain open.
- **EgoLite**: creates a new TaskSpace on the default service. On macOS the installed app must pass
  `codesign --verify` and Gatekeeper (`spctl -a`). `--strict` is not used because Finder xattrs alone fail it.
- **Playwright**: `--extension` needs the Playwright MCP Bridge extension in Chrome or Edge. If a connection prompt
  appears, choose an empty tab, not a personal one.
- **Kitsune**: uses the profile connected to the default bridge, with existing user tabs `read-only`.

```sh
python3 scripts/run.py --browser-mode existing-profile --execute --task dispatch \
  --harness claude --model claude-opus-5-5 --out runs/profile-opus.jsonl
python3 scripts/run.py --browser-mode existing-profile --execute --task dispatch \
  --harness codex --model gpt-6.1-sol --out runs/profile-sol.jsonl
```

MCP agents are told to open a new tab first and not to read or change existing tabs. This is an instruction, not
technical isolation: product metadata can include open tabs, so close sensitive tabs first. The operator cleans up
MCP fixture tabs; the browser is never quit. EgoLite cleans up only the TaskSpace it created. `browser_mode` in the
results tells the modes apart. This compares products including browser engine and profile state; it does not
score whether existing tabs were preserved.

To change one arm's mode, pass `--arm-mode`, for example `--arm-mode playwright=isolated` to run only Playwright in
an isolated Firefox when the Chrome bridge extension is not installed.

### Isolated: `--browser-mode isolated` (default)

Never attaches a personal profile or the default bridge.

| Tool | Setup |
|---|---|
| Aside | Not supported by this harness: the app opens the fixture tab in its current profile, which `--profile` sessions do not see. |
| EgoLite | Install `ego-browser`, start a dedicated named service and set `BENCH_EGO_SERVICE`. The runner creates and finishes a TaskSpace per attempt. |
| Playwright | For example `npm install --prefix /tmp/pw-bench @playwright/mcp@0.0.83`, then `/tmp/pw-bench/node_modules/.bin/playwright install firefox`, and set `BENCH_PLAYWRIGHT=/tmp/pw-bench/node_modules/.bin/playwright-mcp`. Isolated headless Firefox per attempt. |
| Kitsune | Start a **separate test profile and bridge** with the extension connected. Set that bridge's `BENCH_KITSUNE_HTTP_PORT` (not the default 47651), `BENCH_KITSUNE_TOKEN` and `BENCH_KITSUNE_HOME`. If `kitsune` is not on PATH, set `BENCH_KITSUNE` to an absolute path. The operator owns the browser lifetime and leftover tabs. |

```sh
# Check one connection first. This uses real subscription quota.
python3 scripts/run.py --execute --arm playwright --task dispatch \
  --model "$MODEL_ID" --out runs/smoke.jsonl

# Compare all four tools with the same exact model ID
python3 scripts/run.py --execute --repeat 2 --timeout 180 \
  --model "$MODEL_ID" --out runs/four-way.jsonl
```

To compare models, run each with the same `--task` and `--repeat` and separate output files, for example
`--harness claude --model claude-opus-5-5` and `--harness codex --model gpt-6.1-sol`. A model comparison also
includes harness differences. Codex does not load existing MCP settings. Its MCP arms use the `exec` read-only
sandbox. Its CLI arms run without an OS sandbox, as under Claude Code, because seatbelt blocks localhost, the
keychain (Aside) and LaunchServices (EgoLite). CLI arms are instructed to use only the given `./browser` command.

`.env` is never read. The two CLI arms pass JavaScript only through the given executable from Bash; the two MCP arms
enable only the given stdio server. The CLI guide is given to the model. Staying within the UI is an agent rule,
not a security sandbox against a malicious agent.

## Logs, analysis and Hugging Face

Each attempt's raw event stream (Claude `stream-json`, Codex `--json`) is saved in `<out>.transcripts/`, and the
Git revision and product versions in `<out>.meta.json`. Each JSONL row has `tool_calls`, per-tool `tools`,
`tool_errors`, `tokens` (`input` including cache, `cached_input`, `output`), `turns`, `cost_usd` (Claude only) and
the final message. For CLI arms one tool call is one `./browser` script, which may batch several actions.

```sh
python3 scripts/analyze.py runs/v1/*.jsonl --out runs/v1/analysis     # report.md + summary.json
python3 scripts/figure.py runs/v1/analysis/summary.json ../docs/assets/2026-11-19-four-way.svg
python3 scripts/publish.py runs/v1/*.jsonl --notes findings.md --repo junyeong-nero/kitsune-browser-bench
```

JSONL rows are written after each attempt and existing files are never overwritten. `pass`/`fail` come from the
submissions. `error` means a timeout, tool setup failure or agent failure, and errors stay in the success
denominator. `agent_seconds` excludes fixture setup and cleanup but includes the model's tool calls and navigation.
CLI arms start on a prepared tab and MCP arms from their first navigation, so this is not a pure browser latency
comparison. When sharing results, record the Git revision, product, browser and CLI versions, and the model ID.
