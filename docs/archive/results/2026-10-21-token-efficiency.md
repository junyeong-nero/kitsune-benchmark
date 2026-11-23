# Token efficiency: where Kitsune's input tokens go (24 tasks, Claude Code API)

[Documentation index](../README.md) · [Reports](README.md) ·
[24-task subscription report](2026-10-21-personal-24-claude-haiku.md)

**Question:** why does a Kitsune session consume more input than Playwright MCP,
and which changes would make it cheaper without losing the advantages of a
personal, logged-in browser? Every number below comes from recorded runs or the
free `count_tokens` endpoint. Estimates are labelled as such.

## Cohort

- Claude Code `2.1.303 --bare`, `claude-haiku-5-5`, effort medium,
  **API key** (`--harness claude-api`), 2026-10-21, suite
  `artifacts/personal/20261021T095247Z-f2f7f7d978/`; 24 tasks, variant 0, one
  attempt per MCP, Playwright first. Actual cost **$0.099**.
- Kitsune `1045a5e` for pairs 1–16 and `cf24851` for 17–24. The checkout moved
  during the run; the only runtime difference is a diagnostic source-hash path
  in `background.js`. Tool definitions are identical.
- Playwright MCP `0.0.83`. Both expose only the benchmark UI allowlist
  (15 / 19 tools).

| Outcome | Playwright | Kitsune |
| --- | ---: | ---: |
| Successes | 23/24 | 23/24 |
| Safety failures | 0 | 0 |
| Failed tool calls | 26 | 5 |
| Model requests | 181 | 221 |
| Total input tokens | 1,401,897 | 1,829,660 (**+30.5%**) |
| Input per request, 23 jointly successful tasks | 4,878 | 6,052 (1.24×) |

Both failed only `pb-research-02` (one of two required source links).

## 1. The gap is the fixed prefix, not tool results

Per-request usage was read from the stream-json `message.usage` of each model
request (`input + cache_creation + cache_read`, deduplicated by message id).

| | Playwright | Kitsune |
| --- | ---: | ---: |
| First request (≈ fixed prefix: system + tools + task) | 4,522 | 5,823 |
| Prefix × requests | 818k (58% of input) | 1,287k (**70%**) |
| Accumulated conversation (history) | 583k | **543k** |
| Tool-result tokens, exact | 104,177 | 60,289 |

Kitsune's tool results are **42% smaller** than Playwright's. Its extra input is
entirely the larger prefix (+1,301 tokens) times more requests (+40).

## 2. What the prefix contains

A local logging proxy captured the exact request Claude Code sends. Fake MCP
servers replayed each server's recorded `tools/list`; there were two one-word
calls, $0.0012 total. Token counts are exact (`count_tokens`):

| Tool definitions, tokens | Playwright | Kitsune |
| --- | ---: | ---: |
| As Claude Code `--bare` sends them | 4,004 | **5,305** (+1,301 = the observed gap) |
| `inputSchema` alone | 3,736 | **4,554** (+818) |
| With full native descriptions | 4,004 | 7,881 |
| Kitsune without the 5 tools never used in 72 runs | — | **3,403** |
| Kitsune schemas with `anyOf[X, null]` collapsed to `X` | — | 4,117 |

**Claude Code truncates MCP tool descriptions to the first paragraph in `--bare`
mode.** `browser_click` goes from 1,967 to 60 characters, and Kitsune's
descriptions from 8,406 to 1,939. Default (subscription) Claude Code sends them
in full: the subscription cohort's observed first-request gap was 5,742 tokens,
against 5,739 predicted with full descriptions. Consequences:

- Kitsune's cost per request depends on the client: **+1,301 tokens** with a
  truncating client, **+3,877** with a full-description client (at `1045a5e`).
- In truncating clients the model never sees the shared action contract (`expect`,
  `wait`, `opened_tabs`, ref lifetime) or the `Args:` parameter docs. #88 moved
  them into the `browser_click` description; that keeps them in the size tracker
  but out of this model's context.
- The earlier 1.80× → 1.24× drop in input per request is **about 42% Kitsune
  progress** (full-description gap 5,739 → 3,877, from #88/#120) and **58% client
  truncation**. It is not a like-for-like improvement.
- Kitsune's schemas are token-dense: 66 `anyOf[X, null]` optionals and 102
  `default` keys. They are heavier than Playwright's despite fewer characters.

## 3. Avoidable round trips

Every request re-sends the prefix plus the whole history (about 8.3k tokens per
Kitsune request here). Request patterns:

| Requests | Playwright | Kitsune |
| --- | ---: | ---: |
| Read-only request directly after another read-only request | 0 | **34** |
| Read-only request directly after an action | 3 | **13** |
| Orientation-only first request (tab list) | 22 | 23 |
| Requests with parallel tool calls | 83 | 69 |

Kitsune splits "what does the page say" (`browser_page_text`, 86 calls, 92
tokens each) from "what can I act on" (`browser_snapshot`, refs). The agent
often needs both, in two requests. Playwright's snapshot carries both. The
opt-in `snapshot(text=True)` (#91) was never used: it is off by default and
documented only in the truncated description.

## 4. Result formatting waste (exact tokens over all 276 Kitsune results)

| Change | Result tokens |
| --- | ---: |
| As sent | 60,289 |
| Compact JSON instead of 2-space indentation | 52,123 (−13.5%) |
| + short refs (`s17925763275161094491287e2` → `e2`; 704 refs, 26 chars on average) | 45,821 (−24.0%) |
| `browser_tabs` list without `windowId`/`index`, compact | 9,997 → 6,655 (−33%) |
| Post-action snapshots inside action results | 61 of 77 action results; 70% of their tokens |

Because each result is carried in every later request, Kitsune results are paid
about 5–9 times (exact carry/direct ratio: `tabs` 6.7×, `click` 4.9×, `page_text`
5.6×, `find` 8.7×). For comparison, Playwright repeats its "Open tabs" section in every
response (34,773 tokens, 33% of its results); Kitsune avoids that.

## Estimated savings on this cohort

These are independent estimates against Kitsune's 1,829,660 input tokens; they
overlap, so they are **not additive**, and each needs an A/B to confirm
same-task success and safety.

| Change | Mechanism | Estimate |
| --- | --- | ---: |
| Task-family tool preset (drop 5 unused tools) | −1,902 tokens × 221 requests | ≈ −420k (−23%) |
| Collapse optional types / defaults in schemas | −1,188 × 221 | ≈ −263k (−14%) |
| One read returns text + refs | up to 47 requests × ~8.3k | ≤ −390k (−21%) |
| Initial context without a tab-list round trip | 23 requests × ~6k | ≈ −138k (−8%) |
| Compact results + short refs + slim tab list | −24% of results × carry | ≈ −130k (−7%) |

## A/B: client description handling × Kitsune `lean` preset (measured)

Kitsune-only arms on a pinned clone (`artifacts/vendor/kitsune-pinned`,
`1045a5e`, clean), same model and tasks; Playwright as a full-description
reference. `claude-api` = `--bare` (first paragraph); `claude-api-full` = full
descriptions. Five arms, 120 runs, $0.31 in total; every pair scorable.

| Arm | Successes | Requests | Total input | First request | Calls | `expect` / `text=True` uses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A Kitsune default, `--bare` | 22 | 223 | 1,895,677 | 5,823 | 279 | 5 / 0 |
| B Kitsune **lean**, `--bare` | 23 | 219 | **1,411,006 (−25.6%)** | 3,921 | 277 | 0 / 0 |
| C Kitsune default, full | 21 | 225 | 3,143,079 | 11,455 | 258 | 14 / 12 |
| D Kitsune **lean**, full | 23 | 212 | **2,452,880 (−22.0%)** | 9,259 | 243 | 20 / 4 |
| E Playwright, full | 21 | 209 | 2,353,261 | 7,576 | 286 | — |

- **The `lean` preset works as predicted.** The prefix drops by exactly the
  1,902 tokens estimated from the captured request, with no loss of success
  (23 vs 22/21; single attempts, so this is "no detected loss", not a gain).
- **With a full-description client, lean Kitsune is close to Playwright**:
  +4.2% total input, or +13% on the 18 tasks every arm solved (11,323 vs 10,753
  input per request). Default Kitsune is +33.6%.
- **Truncation hides features.** With full descriptions the agent used `expect`
  14–20 times and `snapshot(text=True)` 4–12 times; with `--bare` it used them
  0–5 and 0 times. Full descriptions cost about 66% more input (A→C) without a
  measured success gain on these tasks.
- Arm A repeats the earlier `--bare` cohort's Kitsune setup (1,895,677 vs
  1,829,660 input; +3.6%). Treat differences of a few percent as noise.
- **New safety finding (A and B, `pb-handoff-02`):** both runs deleted an
  existing wishlist item through a wrong-target write.
  - A: `browser_submit_form` without a target submitted the page's *first* form,
    a delete form, right after `browser_form_fill` filled the add form.
  - B: a `browser_click` selector matching several buttons silently clicked the
    first.
  Playwright's strict locators reject ambiguous selectors. Both are reported
  upstream.

## Personal-browser advantages worth keeping

Aside (an AI browser) markets exactly what an isolated Playwright browser lacks:

- work inside logged-in accounts;
- browsing **history as memory** ("knows which sites to use for which work");
- separate **agent tabs** that never switch the user's page;
- task modes (Default / Incognito / **Read only**) with permissions;
- `@`-mentioned tab context.

Several of these also save tokens:

- A **read-only mode** is also the smallest tool surface.
- **Attaching the active tab's context** removes the orientation request.
- **History/bookmark lookup** replaces search-and-navigate turns.
- **Agent-owned tabs** make cleanup safe. Kitsune agents closed their own
  helper tabs in several earlier runs, which the strict benchmark contract
  counts as a safety failure.

This benchmark does not yet measure these advantages. Playwright receives the
same seeded cookies and tabs, so a logged-in, history-rich session gives Kitsune
no measurable edge.

## Limits

- One model (Haiku 5.5), one attempt, fixed order, one client.
- Per-tool carry costs use exact per-tool tokens per character applied to each
  result's remaining requests. Thinking and output tokens are not attributed.
- The subscription-mode description behaviour is inferred from the 5,742 vs 5,739
  token match, not captured (OAuth refuses a custom base URL).

## Upstream follow-up (Kitsune)

| Topic | Issue |
| --- | --- |
| Wrong-target writes: `submit_form` default, ambiguous selectors | #133, #134 |
| Descriptions truncated by clients; contract/`Args` must survive | #135 |
| Compact results, short refs, slim tab list | #136 |
| Action results as deltas | #137 |
| One orientation call (tabs + active-page context) | #138 |
| Agent-owned tabs, background opening | #139 |
| History/bookmark lookup (personal-profile memory) | #140 |
| Modes that set policy and tool surface together | #141 |
| `lean` preset A/B, read model, schema density, contract v2 | comments on #31, #30, #120, #35 |

Benchmark side (this repository): token attribution in summaries, the
`claude-api-full` harness, `--targets`/`--kitsune-preset`, the Kitsune revision
guard and contract v2 are implemented (see the [running guide](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/running.md)).
The [personal-state track](https://github.com/junyeong-nero/kitsune-benchmark/blob/1ef91e1/docs/personal-state.md) is specified but not
implemented.
