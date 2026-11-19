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
python3 scripts/publish.py runs/v1/*.jsonl --notes findings.md --repo junyeong-nero/kitsune-browser-bench
```

JSONL rows are written after each attempt and existing files are never overwritten. `pass`/`fail` come from the
submissions. `error` means a timeout, tool setup failure or agent failure, and errors stay in the success
denominator. `agent_seconds` excludes fixture setup and cleanup but includes the model's tool calls and navigation.
CLI arms start on a prepared tab and MCP arms from their first navigation, so this is not a pure browser latency
comparison. When sharing results, record the Git revision, product, browser and CLI versions, and the model ID.
