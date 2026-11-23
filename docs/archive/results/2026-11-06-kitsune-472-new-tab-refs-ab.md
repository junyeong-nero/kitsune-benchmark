# kitsune#472: say a copy tab has new refs in the read-only hints, Kitsune A/B

[Results index](README.md) · [Results by Kitsune version](kitsune-versions.md) ·
[Source cohort: main `286cfe5`](2026-11-05-main-286cfe5.md) · Upstream: kitsune#472, kitsune#476

**Bottom line:**

- **Not supported.** Neither acceptance condition of kitsune#472 holds.
- **The batched stale write is still there.** On the issue units, a write sent in the same request as the copy tab's
  navigation failed with `stale_ref` (`other_document`) in 2 of 16 B runs (4 errors), against 3 of 16 in A (3 errors).
- **The hint may add requests elsewhere.** B sent `tabs select` and `snapshot` in separate requests in the 2
  `pb-handoff-04` v1 personal runs and in 1 `pb-tabs-01` run, which A sent together. Requests per unit: B used more in
  4 units, fewer in 4. Totals were 162 for B and 160 for A.
- Input is unchanged: B/A **1.001** overall (paired median 0.993). Success, scorability and safety were 32/32 in both
  arms.

## Question

In the [`286cfe5` cohort](2026-11-05-main-286cfe5.md), Kitsune opened its own tab on the user tab's URL to write, and
in 3 runs sent the `tabs new` or `navigate` in the same request as the write, using refs from the user tab's snapshot.
Refs are per document, so the write failed with `stale_ref` (`other_document`) and cost one request (kitsune#472).
The question was whether saying, in the read-only hints, that the new tab has new refs stops the batched write.

## Arms

- **A:** Kitsune main `c0ea723` (`v0.7.3-8`).
- **B:** `c0ea723` + `9bc1731` (kitsune#476, cherry-picked locally as `f048f0f`). Both read-only hints, in
  `browser_tabs list` and `browser_tabs select`, end with "The new tab's result lists the page with new refs; refs from
  this tab do not apply there." Nothing else changes. The kitsune#476 branch itself is 8 commits behind main, so it was
  not used as is.

## Design

- **Setup:** Kitsune only, benchmark `taskset-v3.5-4-g9f2be91`. Model `claude-opus-5-5`, effort medium, Claude Code
  `2.1.303` on the subscription. Elicitation `decline`.
- **Issue units:** `pb-research-01` and `pb-handoff-04`, in personal and coexistence (user-seeded).
- **Guard units**, personal only, to check that the hint adds no request elsewhere: `pb-current-01`, `pb-safe-01`,
  `pb-tabs-01` and `pb-account-01`.
- **Runs:** variants 0 and 1, two attempts, so 32 runs per arm. Each round ran both arms at once on the same track and
  variant, so they shared host load.
- **Measures:**
  - batched stale writes: `other_document` errors on a write sent in the same request (assistant message id) as an
    earlier `tabs new` or `navigate`;
  - model requests with tool calls;
  - Kitsune input tokens;
  - success, scorability and safety as guards.
- **When:** 2026-11-06, 16:06–16:25 KST.

## Results

| | A `c0ea723` | B hint |
| --- | ---: | ---: |
| Success / scorable / safety pass | 32 / 32 / 32 | 32 / 32 / 32 |
| Runs with a batched stale write, issue units | 3 / 16 | **2 / 16** |
| Batched stale writes, issue units | 3 | 4 |
| Requests, issue units | 92 | 92 |
| Requests, guard units | 68 | 70 |
| Input, issue units | 1,259,345 | 1,242,814 (0.987×) |
| Input, guard units | 936,315 | 954,664 (1.020×) |

- **Where the batched writes were:**
  - A: personal `pb-research-01` a2v0, coexistence `pb-research-01` a1v0 and coexistence `pb-handoff-04` a1v0;
  - B: personal and coexistence `pb-research-01` a1v1, a `type` and a `click` each.
- **B's agent had read the hint.** In B's personal `pb-research-01` a1v1 run, it read the `tabs list` hint and had
  already opened one copy tab, whose result listed new refs (`e8`). It then sent
  `tabs new …/search` + `type e6` + `click e7` + `snapshot` in one request.
- **What a batched write cost:** each of A's failures was followed by a request that only retried the write (for
  example `pb-research-01`: 6 requests against 5 without the failure). B's two failures cost no request, because the failing request ended with a `snapshot` and the retry went out with the next planned write. Two
  runs cannot tell whether that comes from the hint.
- **Separate select and snapshot:** in personal `pb-handoff-04` v1, both B attempts used 7 requests against A's 6.
  - A: `snapshot + tabs select + snapshot`;
  - B: `snapshot + tabs select`, then `snapshot` on its own.

  `pb-tabs-01` a1v1 shows the same split (B 8, A 6). The new sentence in the `select` hint may make the agent wait
  for the result, but this sample cannot confirm it.

Kitsune input and requests per issue unit (four runs per arm: a1v0, a1v1, a2v0, a2v1; batched stale writes in brackets):

| Track, task | A | B |
| --- | --- | --- |
| personal `pb-research-01` | 66k/5, 66k/5, 66k/5 [1], 66k/5 | 65k/5, 67k/5 [2], 65k/5, 65k/5 |
| personal `pb-handoff-04` | 97k/7, 85k/6, 85k/6, 85k/6 | 83k/6, 94k/7, 83k/6, 94k/7 |
| coexistence `pb-research-01` | 79k/6 [1], 65k/5, 66k/5, 65k/5 | 65k/5, 67k/5 [2], 65k/5, 65k/5 |
| coexistence `pb-handoff-04` | 100k/7 [1], 85k/6, 95k/7, 82k/6 | 95k/7, 81k/6, 96k/7, 84k/6 |

## Limits

- **Rare event.** The pattern hit 3 of 16 A runs. A 3 vs 2 difference is well within noise.
- **One model, one policy** (`decline`), and two attempts per unit.
- **Requests** count model requests that sent at least one tool call, the same way in both arms. The final answer
  request is not counted.
- **Branch base.** B is a local cherry-pick on `c0ea723`, not the kitsune#476 branch.

## Artifacts (private)

- `artifacts/ab-472-new-tab-refs/`: `run.sh`, `analyze.py`, `analysis.txt` and the per-round JSON.
- `artifacts/vendor/kitsune-main-c0ea723/` and `artifacts/vendor/kitsune-ab-472-hint/` (`f048f0f`).
