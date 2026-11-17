# Five-surface comparison: Kitsune, Playwright MCP, Aside, EgoLite, Claude in Chrome

A new cohort (`five-surface-v1`), not a continuation of the stopped
agent-combinations phases. Nothing is pooled with earlier results.

## Matrix

| Model (CLI, medium) | Kitsune + Zen | Playwright MCP | Aside | EgoLite | Claude in Chrome |
| --- | :-: | :-: | :-: | :-: | :-: |
| `gpt-6.1-sol` (Codex 0.163.0) | ✓ | ✓ | ✓ | ✓ | n/a |
| `claude-opus-5-5` (Claude Code 2.1.303) | ✓ | ✓ | ✓ | ✓ | ✓ |

Claude in Chrome is an Anthropic extension reachable only through `claude --chrome`,
so it has no Codex arm. 9 arms × the 23 expanded conditions (7 personal, 10 isolated
gallery, 6 crowded gallery; variant 0, one repeat) = **207 attempts**. Arm order rotates
per condition within each model group; group order alternates. Subscription logins
only, no API budget.

## Arms

- **Kitsune / Playwright / Aside / EgoLite**: the unchanged agent-combinations fixture
  relay (`agent_combinations_fixture.py`, `agent_combinations_session.py`): native
  schemas, harness-seeded starting tabs, inventory after each call. Kitsune `14d9ceb`
  in a private Zen, Playwright MCP on a private Chrome, Aside and EgoLite in their
  running vendor apps (shared, not fresh profiles).
- **Claude in Chrome**: `claude --chrome` in the operator's own Chrome profile, with
  `--permission-mode auto` (the auto-mode classifier's approval replaces the
  extension's per-site prompt, which otherwise blocks an unattended run) and network/
  console/upload/browser-switch tools disallowed. The extension only sees its own
  per-session tab group, so **the agent opens the starting tabs itself** from URLs in
  the prompt. The harness reads only tabs on the attempt's private fixture origin
  (AppleScript), once after the run, then closes them.

## Measures and differences to disclose

- Grading is the fixtures' own server-side state (functional success) plus the v2
  safety contract. Claude in Chrome custody rests on one final snapshot rather than
  per-call inventories, so its safety grade is weaker evidence than the relay arms'.
- Time: relay arms report elapsed minus relay setup and inventory time; Claude in
  Chrome reports raw elapsed, which includes its own tab seeding.
- Tokens are each CLI's reported usage (input includes cache reads). Codex and Claude
  token counts use different tokenizers; compare within a model. Auto-mode classifier
  calls are not in Claude in Chrome's reported usage.
- Viewports differ: private 1280×720 browsers vs vendor apps vs the operator's Chrome window.

## Running

```sh
uv run --locked python scripts/run-five-surface.py plan
uv run --locked python scripts/run-five-surface.py run --out artifacts/five-surface-v1
uv run --locked python scripts/run-five-surface.py summary --out artifacts/five-surface-v1
```

Runs continue without review gates. A started attempt is never retried (an unrecorded
start becomes `interrupted`). The run stops on a usage limit, a Claude in Chrome
permission prompt, or three consecutive operational failures; rerun the same command
to continue.
