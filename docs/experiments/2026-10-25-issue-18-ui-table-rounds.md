# Issue #18: extra Kitsune model rounds on `ui-table` — offline round analysis

[Results index](../results/README.md) · [Source cohort](../results/2026-10-25-v0.4.1-model-validation.md) ·
[A4 triage](../results/2026-10-25-v0.4.1-issue-candidates.md#a4--table-token-cost-tracks-model-rounds-not-just-tool-call-count)

Steps 1–3 of benchmark issue #18, using **existing private transcripts only**:
no model, browser or benchmark command was run. The cohort is the 16 `ui-table`
runs of the v0.4.1 model validation (Kitsune v0.4.1 `83acfe9` vs Playwright MCP
0.0.83, `claude-opus-5-5` medium, Claude Code subscription, variant 0, four
counterbalanced pairs per layout, all 16 jointly successful).

## Summary

- **The issue's figures reproduce exactly** from the transcripts. Isolated:
  input 358,410 / 456,430 (**+27.3%**), calls 60 / 53 (**−11.7%**), requests
  25 / 36 (**+44.0%**), Kitsune more requests in **4/4** pairs, no tool errors.
  Crowded: input **+4.4%**, calls −8.8%, requests 41 / 50 (+22.0%), Kitsune more
  requests in 3/4 pairs; Playwright had 5 tool errors in 3/4 runs.
- **Both targets issued the same number of observation calls** (snapshot + find:
  isolated 24 / 24, crowded 29 / 29). The extra Kitsune requests come from
  *where* those calls are issued. Playwright put 20 of 24 isolated observation
  calls in the same request as preceding clicks; Kitsune issued 19 of 24 as
  separate observation-only requests.
- **Pattern:** Kitsune collapses repeated table rows ("N more similar items;
  snapshot eX to list all"). In isolated runs it returned 29 collapsed results.
  The model then spent separate rounds expanding a container that was still
  collapsed (8 expansion snapshots, all in observation-only rounds) or checking
  hidden rows. Of the 9 isolated (11 crowded) observation-only rounds directly
  after an action, 7 (7) started from a page with a collapsed container. The
  other 2 isolated ones read cell values on the uncollapsed last page.
  Playwright had no such follow-up rounds in isolated runs.
- **Action results:** Playwright's click results never carry an inline snapshot
  (0 refs in 36 isolated clicks). The model therefore always plans a
  snapshot/find after the click, in the same request (16 of 17 action rounds).
  Each Kitsune click returns a delta (145 refs in 29 clicks). That delta is
  enough to confirm a toggled checkbox, but not to choose rows on a new page: it
  omits the cell values and collapses rows. So a follow-up read is needed, and it
  usually came as a new round.
- **Smaller snapshots do not offset the extra rounds; they help cause them.**
  Kitsune's isolated observations are 46% smaller per call and its input per
  request is 11.6% lower. But 11 extra requests re-send the ≈9.2k-token fixed
  prefix: prefix × requests **+100,855** tokens vs total input **+98,020**
  (estimated non-prefix/history difference −2,835; this covers all accumulated
  context, not only observations). Truncating snapshots further would target
  the part of input that is already smaller, and could add expansion rounds.

This is an observational association from 4 pairs of one variant. The causal
test is the [draft hypothesis](#draft-hypothesis-not-opened-as-an-issue) below.

## Method

`scripts/analyze-model-rounds.py` reads each run's `events.jsonl` (Claude Code
stream-json) and groups events into **rounds**: one round is one deduplicated
model request (assistant message id), the same unit as `token_attribution.requests`.
Claude Code `num_turns` is a different count and is not used. For each round the
script reports:

- Tool calls, in order. Calls are *parallel* when one request issues more than
  one. Calls are classed as observation (`snapshot`, `find`, screenshot,
  console/network reads) or action (every other tool).
- Round kind: observation-only, action, action+observation, or answer (no
  tools). A **follow-up observation** is an observation-only round right after
  an action round. A **chained observation** follows another observation-only
  round. **In-batch observation** is an observation call placed after an action
  call in the same request.
- Model-visible result characters/bytes, snapshot refs returned and how many are
  new. It also detects Kitsune collapsed-list hints, and **expansion reads**:
  snapshots of a container that is collapsed in the current state. The state is
  tracked in call order: an observation result adds its hints, and an action
  result replaces them with its own. So a page turn whose delta has no hint
  clears the earlier page's hints. A follow-up **on a collapsed state** starts
  while some container is collapsed.
- Per-request input as cache read + cache write + uncached tokens, plus a
  prefix × requests vs estimated non-prefix/history split (as in
  `token_attribution`). The non-prefix part is total input minus the first
  request × requests. It includes assistant text, tool calls and tool results,
  so it is not an observation token count.

Cross-check: per run, the script's requests, total input, cache read/write and
uncached input, calls, failed calls, result characters, prefix × requests and
result output tokens equal the harness summaries for **16/16 runs**. Two
supporting facts below come from an ad-hoc private transcript check rather than
the script: what the click deltas contain, and what some follow-up finds and
snapshots were reading. They are labelled where used.

Reproduce (private artifacts; no inference):

```sh
uv run --locked python scripts/analyze-model-rounds.py \
  artifacts/issue-model-validation-v0.4.1/1[3-9]-table-*.json \
  artifacts/issue-model-validation-v0.4.1/2[0-8]-table-*.json --rounds
```

## Round structure

Totals over the four runs per layout and target. Per-run requests are listed in
repeat order r0–r3 (target order PW/K, K/PW, K/PW, PW/K).

| | Isolated PW | Isolated K | Crowded PW | Crowded K |
| --- | ---: | ---: | ---: | ---: |
| Model requests (per run) | 25 (7, 6, 6, 6) | **36** (10, 9, 7, 10) | 41 (10, 8, 13, 10) | **50** (11, 14, 12, 13) |
| MCP calls / calls per request | 60 / 2.40 | 53 / 1.47 | 68 / 1.66 | 62 / 1.24 |
| Requests with parallel calls | 16 | 12 | 24 | 12 |
| Rounds before first action | 4 | **10** | 4 | **8** |
| Action-containing rounds | 17 | 13 | 29 | 18 |
| … with in-batch observation after action | 16 | 5 | 20 | 0 |
| Observation-only rounds | 4 | **19** | 8 | **28** |
| … follow-up after an action round | 0 | **9** | 4 | **11** |
| … … starting from a collapsed state | 0 | 7 | 0 | 7 |
| … chained after an observation round | 0 | 6 | 0 | 13 |
| Answer rounds | 4 | 4 | 4 | 4 |
| Observation calls (snapshot + find) | 24 (12 + 12) | 24 (20 + 4) | 29 (13 + 16) | 29 (16 + 13) |
| Collapsed results / hidden items | 0 / 0 | 29 / 83 | 0 / 0 | 28 / 124 |
| Expansion reads | 0 | 8 | 0 | 8 |
| Tool errors | 0 | 0 | 5 (3/4 runs) | 0 |

Isolated Kitsune has 11 more requests: **+6** observation rounds before the
first action, **+9** observation-only rounds after actions, and **−4** action
rounds. The pre-action rounds are the 4 expansions of the collapsed table (one
per run), plus 2 re-reads that returned no new refs. The 9 follow-ups are 4
expansions, 2 snapshots that returned no new refs, and 3 `find` checks. The
ad-hoc check shows the 2 snapshots read cell values on the last page (which has
too few rows to collapse), and the finds test whether rows hidden by a collapsed
delta stayed selected. In repeats r1 and r2 the model also batched a container
snapshot after the clicks, twice per run. After the first page turn, that
snapshot came back collapsed, and a follow-up expansion round came next. After
the turn to the last page, the delta had no collapse hint. The batched snapshot
read the cell values (ad-hoc check; not an expansion), and no follow-up round came next. In
r0 and r3 the same last-page read was a separate follow-up round. So batching
the read saved a round only where the new page was not collapsed.

Crowded Kitsune has 9 more requests: +4 pre-action rounds (expansions), +16
post-action observation-only rounds, and −11 action rounds. The +16 includes
chains of `find` calls that returned no new refs (9 of 12 post-action finds).
Playwright's crowded runs include recovery from 5 tool errors (2 of its 4
follow-up rounds come right after a round with an error), so crowded is the
noisier comparison. In 1 of 4 crowded pairs, Playwright used more requests.

## Do action results carry enough observation to skip a follow-up?

| | Playwright 0.0.83 | Kitsune v0.4.1 |
| --- | --- | --- |
| Click result content | Executed code, tabs, page URL, link to a snapshot file; **no inline refs** (0 in 36 isolated / 39 crowded clicks) | Delta snapshot: **145** refs in 29 isolated clicks (100 new) and 180 in 33 crowded clicks |
| Enough to confirm a toggled checkbox? | No; the model checked selections with `find` | Yes; the delta shows the new checked state |
| Enough to select rows after a page turn? | No; the model batched `snapshot`/`find` after the click in 16 of 17 isolated action rounds | No. The ad-hoc check found 0 of 62 Kitsune click deltas with row cell values, and 21 of 29 isolated deltas were collapsed. The read usually came as a separate round (9 follow-ups) |
| Mean result chars per click | 463 isolated / 419 crowded | 371 / 402 |

Neither target's click result is a complete post-action observation for this
task. The difference is round placement. Playwright's results are opaque, so the
model plans the read inside the same request. Kitsune's results are partial, so
the model reads the delta first, then requests the missing part.

## Observation size and reuse

| | Isolated PW | Isolated K | Crowded PW | Crowded K |
| --- | ---: | ---: | ---: | ---: |
| First snapshot chars | 3,410 | 1,226 | 27,991 | 19,075 |
| Observation chars (mean per call) | 43,675 (1,820) | 23,660 (986) | 147,632 (5,091) | 97,337 (3,356) |
| All result chars (bytes) | 60,331 (64,463) | 34,427 (39,091) | 163,978 (187,808) | 110,610 (134,934) |
| Refs returned / first seen | 1,003 / 839 | 295 / 176 | 2,527 / 2,276 | 1,065 / 947 |
| Input tokens | 358,410 | 456,430 (+27.3%) | 1,165,768 | 1,217,095 (+4.4%) |
| Input per request | 14,336 | 12,679 (−11.6%) | 28,433 | 24,342 (−14.4%) |
| Prefix × requests | 229,177 | 330,032 (+100,855) | 375,815 | 458,326 (+82,511) |
| Estimated non-prefix/history (input − prefix × requests) | 129,233 | 126,398 (−2,835) | 789,953 | 758,769 (−31,184) |
| Cache read / cache write | 310,760 / 47,600 | 421,064 / 35,294 | 1,056,395 / 109,291 | 1,129,278 / 87,717 |
| Uncached input | 50 | 72 | 82 | 100 |
| Output (result event) | 4,465 | 4,113 | 5,155 | 5,207 |

Paired K/PW input ratios, r0–r3: isolated 1.247, 1.377, 0.988, 1.494
(median **1.312**); crowded 0.955, 1.632, 0.745, 1.105 (median 1.030).
Requests PW/K: isolated 7/10, 6/9, 6/7, 6/10; crowded 10/11, 8/14, 13/12, 10/13.

The isolated input difference is almost all cache reads: +110,304 read, −12,306
write and +22 uncached tokens. Each request has 2 uncached tokens on both
targets. A Kitsune expansion read returns rows already returned by the collapsed
snapshot, plus the hidden ones. In isolated runs, 60% of the refs Kitsune
returned were new, vs 84% for Playwright. Both tools renumber re-rendered rows,
so "new ref" undercounts re-reading of the same content.

## Answers to the issue's questions

1. **Which state changes trigger another round?** Page turns. In isolated
   runs, a turn to a collapsed page led to an expansion round (4 follow-ups).
   A turn to the uncollapsed last page led to a cell-value read (2). A return
   to an earlier page led to `find` checks of rows the delta collapsed (3).
   7 of 9 isolated (7 of 11 crowded) Kitsune follow-ups started from a
   collapsed state. No isolated Playwright round was a follow-up. Playwright
   returns no collapsed results; 2 of its 4 crowded follow-ups come right
   after a tool error.
2. **Do smaller snapshots cause the extra rounds?** The data supports this
   direction for this fixture. Collapsing makes each observation smaller, but
   creates expansion and verification reads that the model mostly issues as
   separate rounds. Kitsune's observations are 46% smaller in characters. The
   estimated non-prefix/history difference is only −2,835 tokens, against
   +100,855 for the extra prefix re-sends. Observation tokens were not
   measured separately. Further truncation is not supported.
3. **Hypothesis:** below. Nothing here shows that removing the collapse would
   lower total input. Expanded lists make every request larger, so this needs
   the A/B.

## Limits

- 4 pairs per layout, one data variant (8 rows per page, 5 visible before the
  collapse), one model/effort and the subscription Claude Code harness. Model
  batching behaviour may differ with other models, harnesses or variants.
- Observational: no factor was varied. "Follow-up" and "expansion" are
  structural labels, not the model's stated reasons.
- Usage per request is taken from the first streamed event of each message.
  Input reconciles exactly with the result event; per-request output tokens in
  stream-json are streaming snapshots, so only the run's final output total is
  reported. The answer round's input is included and nothing follows it.
- Sizes are model-visible characters/bytes of tool results, not tokens. Tool
  classes come from tool names. Click-delta content and the purpose of the finds
  come from an ad-hoc private check, not the committed script.
- Expansion reads assume that an action delta repeats the hint of a container
  that stays collapsed. A delta that omits it would undercount expansions.
- Crowded comparisons include Playwright error recovery and a much larger page.
  The first snapshot is 8.2× the isolated size for Playwright and 15.6× for
  Kitsune.

## Draft hypothesis (not opened as an issue)

**H18:** On paginated tables, Kitsune's collapsed-list summaries in snapshots
and action deltas cause separate expansion/verification model rounds. Listing
the collapsed items reduces model requests per successful run, and lowers total
input, because avoided prefix re-sends outweigh larger observations.

- **Arms:** baseline Kitsune v0.4.1 `83acfe9`, and the same revision with exactly
  one change: no similar-item collapse when the hidden remainder is at most a
  threshold fixed before the run, in both snapshots and action deltas. Same
  tool names, descriptions, schemas, refs semantics and prompt. No instruction
  to batch calls. Playwright 0.0.83 may run as an unchanged reference, not an
  arm. Including row cell values in page-turn deltas is a separate factor, for
  a later experiment.
- **Cells:** `ui-table` variants 0–2 × crowded/isolated. Guard cells: two
  collapse-heavy non-table tasks (e.g. `ui-infinite` and one personal list
  task), to detect input growth elsewhere.
- **Design:** the same model, effort, harness, Claude Code and MCP pins, and
  180 s timeout. Sequential targets; 4 repeats per arm per table cell in
  ABBA/BAAB order; 3 per guard cell. No automatic retries; unscorable runs
  are reported, not replaced.
- **Identical contracts:** `taskset-v2` (`component-gallery-v2` grader), `v1_strict_close` and
  `v2_agent_tab_cleanup` success and safety. Selected rows equal the expected
  ids (row/value correctness). No increase in stale/wrong-ref errors (reference
  correctness).
- **Counted per run:** model requests, input split into cache read / cache
  write / uncached and prefix × requests vs non-prefix/history, output, MCP calls,
  observation-only / follow-up / chained rounds, expansion reads, result
  chars, tool errors and those recovered within the run, failures and
  unscorable runs.
- **Estimands (fixed before execution):** a *pair* is the baseline and
  intervention run of one cell and repeat. It is *jointly successful* when
  both runs are scorable and pass the primary (v2) `task_success`.
  - *Request ratio:* the median, over all jointly successful isolated table
    pairs pooled across variants (up to 12), of intervention requests /
    baseline requests. It is not a median of per-cell medians.
  - *Table input ratio:* Σ intervention input / Σ baseline input over all
    jointly successful table pairs, both layouts (up to 24). *Guard input
    ratio:* the same per guard cell.
  - Failed or unscorable runs drop their pair from every ratio and are listed.
    With fewer than 10 of 12 isolated or 20 of 24 table pairs jointly
    successful, the verdict is inconclusive regardless of the ratios.
  - *Gates, separate from the ratios:* over all attempts per cell and arm,
    successes (an unscorable run counts as no success), v1/v2 safety failures
    and recovered tool errors.
- **Predeclared decision:**
  - **Support** requires all of: in every cell, intervention successes ≥
    baseline and safety failures ≤ baseline; request ratio ≤ 0.85; table
    input ratio ≤ 0.95; every guard input ratio ≤ 1.05; recovered errors
    not higher in total.
  - **Reject** if the request ratio is > 0.95 or the table input ratio is
    > 1.00.
  - Anything else is **inconclusive**, with no adoption claim.
- **Out of scope:** parallelizing state-dependent clicks or writes, prompt or
  description changes that steer batching, and further snapshot truncation.
