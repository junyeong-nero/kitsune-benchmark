# Hostile-UI capability matrix (draft)

[Documentation index](README.md) · [Catalog](../tasks/hostile/catalog.json) ·
[First results](results/2026-10-29-hostile-headless.md)

**Purpose.** Simple HTML pages accept almost any input. Real sites often do not: handlers check `isTrusted`, menus
open on `pointerdown` or CSS `:hover`, editors read only `beforeinput`, widgets use pointer capture, and content
sits in canvases, closed shadow roots or cross-origin frames. This track measures which **tool strategies** such
components accept, per MCP server, **without a model**. It answers "can the tools do it at all?" before a model A/B
asks "does an agent find the way?".

## Components

Two layers in [`tasks/hostile/catalog.json`](../tasks/hostile/catalog.json):

- **Defense catalog (17):** hand-written pages in `kitsune_benchmark/hostile_pages.py`. Each page isolates one
  mechanism, so a failure names its cause:
  - `isTrusted` checks, pointer sequences, `elementFromPoint` hit tests;
  - menus that open on `mousedown` or CSS `:hover`, and hover intent;
  - framework-style controlled inputs, `beforeinput`-only editors, `KeyboardEvent.code` shortcuts, keyup-only
    filters;
  - pointer-capture drags, long-press, double-click-only rows;
  - user activation, closed shadow roots, cross-origin iframes, and canvas hit-testing.
- **Real libraries (9):** React 19 controlled input, react-select, Radix DropdownMenu, Radix Select, Radix Slider,
  dnd-kit sortable, TipTap (ProseMirror), CodeMirror 6 and react-day-picker. They are bundled locally from
  `fixtures/hostile` (pinned versions, own `package-lock.json`) into `artifacts/hostile/bundle`.

**Success** is reported by the component's own handler (`__hostile.done`), for example React's `onChange`, Radix's
`onValueChange` or ProseMirror's update. The fixture server records it. Tool responses never decide success.

`report.js` also counts every input event the page received by type, `isTrusted` and `pointerType`. A failure
therefore shows what arrived, for example `click:synthetic` against an `isTrusted` check.

## Strategies and targets

Each component lists strategies (`click`, `hover_then_click`, `type`, `type_slowly`, `fill_form`,
`click_then_keys`, `select_option`, `drag`, `slider_fill`, `slider_keys`, `sortable_keys`, …). Each strategy is a
fixed sequence of core tool calls, the same tool names and arguments for both servers.

- **Targets:** named by role and accessible name. They are resolved to each server's ref from a fresh
  `browser_snapshot` before every step.
- **`target_not_found`:** the server's snapshot did not expose the element with a ref. That is an observation-layer
  result, not a resolver error.
- **Fresh pages:** every strategy runs on a fresh page (new trial token).

**Kitsune-only strategies.** The catalog's `kitsune_only` strategies pass parameters that Kitsune's core tools accept
beyond Playwright MCP's schema (junyeong-nero/kitsune#351):

- `long_press`: `browser_click` with `hold_ms: 700` (on `long-press`, which needs 600 ms);
- `hover_intent`: `browser_hover` with `duration_ms: 500, steps: 5`, then a click on the revealed item (on
  `hover-intent`, and on `css-hover-menu`, where synthetic moves still do not apply CSS `:hover`).

They run on Kitsune only and form a second table in `matrix.md`, with `n/a` for Playwright: not a failure, the
parameter does not exist there. Records in `results.json` carry `kitsune_only: true`, and the summary lists the
strategy names. A Kitsune without these parameters ignores them (v0.7.1) or reports `extension_version_mismatch`
with `hold_unsupported` or `sustained_hover_unsupported` (a newer server with an older extension). The runner
checks that the result has `held_ms` or `moves`; when it does not, the step is marked `unsupported`, the strategy
stops, and its outcome is `unsupported` unless the page accepted it anyway.

## Running

```sh
# Once: build the library bundles (no network at run time).
npm --prefix fixtures/hostile ci --ignore-scripts && npm --prefix fixtures/hostile run build

uv run --locked python -m kitsune_benchmark hostile                         # plan only
uv run --locked python -m kitsune_benchmark hostile --execute \
  --kitsune-project ../worktrees/kitsune-<rev>                               # about 10 min, no model
uv run --locked python -m kitsune_benchmark hostile --execute --component lib-radix-select --targets kitsune
```

- **Outputs:** `artifacts/hostile/runs/<time>/results.json` (every step, error, response size and latency, the page's
  event counts) and `matrix.md`.
- **Pinning:** the Kitsune revision is recorded before and after the run. A change during the run fails it, so run
  it on a pinned worktree.

**OS input (opt-in).** `--trusted` adds the strategies that use `browser_trusted_click` (Kitsune only;
`KITSUNE_CAPS=core,browse`). It requires `--headed`:

- the browser windows are shown;
- **the real pointer moves**;
- on macOS the bridge needs Accessibility permission.

Run it only while nobody uses the machine. On macOS the Kitsune MCP server and bridge are started with the
project's `macos` extra (pyobjc Quartz), installed only into the Kitsune checkout's environment.

**Kitsune environment.** The bridge gets an allowlisted environment. The Kitsune MCP server inherits the runner's,
without `VIRTUAL_ENV`, `VIRTUAL_ENV_PROMPT`, `UV_PROJECT_ENVIRONMENT`, `PYTHONHOME` and `PYTHONPATH`: the
benchmark's own virtual environment is not the Kitsune checkout's, and `uv run --project` would warn about it.

**Step pause.** The runner waits 0.3 s between the steps of a strategy, on every server. An agent's own latency
between calls is longer; without the pause a snapshot taken right after a real pointer move can precede the frame
that applies CSS `:hover`.

## Limits

- One scripted sequence per strategy. A model might find another way, for example scrolling, keyboard focus or
  waiting.
- Timing-based defenses (hover intent, long-press) are sensitive to how fast the tools send events. The shared
  strategies send one move or an instant press; only the Kitsune-only strategies hold or keep moving.
- The cross-origin frame uses `localhost` vs `127.0.0.1` on one server.
- Playwright MCP runs with `--isolated --headless`. Kitsune runs in headless Firefox through its extension, as in the
  benchmark tracks.
