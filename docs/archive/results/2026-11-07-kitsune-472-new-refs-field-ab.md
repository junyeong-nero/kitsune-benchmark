# kitsune#472: a `new_refs` field in the `browser_tabs action=new` result, Kitsune A/B

[Results index](README.md) · [Results by Kitsune version](kitsune-versions.md) ·
[First A/B: the hint sentence](2026-11-06-kitsune-472-new-tab-refs-ab.md) · Upstream: kitsune#472

**Bottom line:**

- **Not supported.** Neither acceptance condition of kitsune#472 holds.
- **The batched stale write is still there.** On the issue units, a write sent in the same request as the copy tab's
  navigation failed with `stale_ref` (`other_document`) in 3 of 16 B runs (4 errors), against 0 of 16 in A.
- **In all 3 B runs the agent had already read a `new_refs: true` result** from an earlier `tabs new` in the same run.
  It then sent the copy's navigation and a write with the user tab's refs in one request. In 2 of them the
  navigation was a `navigate` in its own tab, which the field does not cover.
- **The field may add requests on the issue units.** B used 91 requests against A's 87 there (more in 4 units,
  fewer in none). On the guard units B used 67 against 70. Input is unchanged overall: B/A **1.004** (issue 1.038,
  guard 0.962). Success, scorability and safety were 32/32 in both arms.

## Question

The [first A/B](2026-11-06-kitsune-472-new-tab-refs-ab.md) found that one sentence in the read-only hints did not
stop agents from batching a write with the copy tab's navigation. kitsune#472 then proposed stating it in a
structured field of the `browser_tabs action=new` result instead of in hint prose. This A/B asks whether that field
stops the batched write.

## Arms

- **A:** Kitsune main `c0ea723` (`v0.7.3-8`), the same checkout as the first A/B's A arm.
- **B:** `c0ea723` + `dc7dc06` (local branch `feat/472-new-refs-field`). When the `browser_tabs action=new` result
  carries the page's snapshot (a `url` was given), it adds `"new_refs": true`. Hints, tool schemas and everything
  else are unchanged.

## Design

The same as the first A/B:

- **Setup:** Kitsune only, benchmark `taskset-v3.5-6-gbf08938` (docs-only changes since `taskset-v3.5-4`). Model
  `claude-opus-5-5`, effort medium, Claude Code `2.1.303` on the subscription. Elicitation `decline`.
- **Issue units:** `pb-research-01` and `pb-handoff-04`, in personal and coexistence (user-seeded).
- **Guard units**, personal only: `pb-current-01`, `pb-safe-01`, `pb-tabs-01` and `pb-account-01`.
- **Runs:** variants 0 and 1, two attempts, so 32 runs per arm. Each round ran both arms at once on the same track and
  variant.
- **Measures:** batched stale writes (`other_document` errors on a write sent in the same request as an earlier
  `tabs new` or `navigate`), model requests with tool calls, Kitsune input tokens, and success, scorability and
  safety as guards.
- **When:** 2026-11-07, 12:01–12:17 KST.

## Results

| | A `c0ea723` | B `new_refs` |
| --- | ---: | ---: |
| Success / scorable / safety pass | 32 / 32 / 32 | 32 / 32 / 32 |
| Runs with a batched stale write, issue units | 0 / 16 | **3 / 16** |
| Batched stale writes, issue units | 0 | 4 |
| Batched stale writes, guard units | 2 (1 run) | 0 |
| Requests, issue units | 87 | 91 |
| Requests, guard units | 70 | 67 |
| Input, issue units | 1,191,792 | 1,237,257 (1.038×) |
| Input, guard units | 961,440 | 924,628 (0.962×) |

- **Where the batched writes were:**
  - A: personal `pb-account-01` a2v0 (guard), `navigate …/orders` + `type e6` + `click e7` + `snapshot`;
  - B: personal `pb-research-01` a1v0 (`tabs new …/search` + `type e6`), personal `pb-research-01` a2v0
    (`navigate …/search` + `type e6` + `click e7` + `snapshot`) and personal `pb-handoff-04` a2v0
    (`navigate …/mail/thread/0` + `type e4`).
- **B's agent had seen the field.** In each B run above, request 3 was a `tabs new` on another page whose result had
  `"new_refs": true`. Request 4 was the batch.
- **What a batched write cost:** the retries of `pb-research-01` went out with the next planned write (5 requests,
  as in the runs without a failure). `pb-handoff-04` a2v0 needed a retry-only request (6 requests; A's a2v0 used 5).
- **Requests on the issue units:** B used one more request in 4 units: personal `pb-handoff-04` a1v0 and a2v0,
  coexistence `pb-handoff-04` a1v0 and a2v1. Only one of them had a batched write.

Kitsune input and requests per issue unit (a1v0, a1v1, a2v0, a2v1; batched stale writes in brackets):

| Track, task | A | B |
| --- | --- | --- |
| personal `pb-research-01` | 65k/5, 66k/5, 65k/5, 66k/5 | 66k/5 [1], 66k/5, 68k/5 [2], 65k/5 |
| personal `pb-handoff-04` | 85k/6, 96k/7, 71k/5, 82k/6 | 96k/7, 94k/7, 84k/6 [1], 84k/6 |
| coexistence `pb-research-01` | 66k/5, 65k/5, 66k/5, 65k/5 | 65k/5, 66k/5, 65k/5, 66k/5 |
| coexistence `pb-handoff-04` | 69k/5, 86k/6, 84k/6, 85k/6 | 84k/6, 85k/6, 80k/6, 95k/7 |

## Reading

- **The pattern is rare and noisy.** On the same A checkout it hit 3 of 16 issue runs in the first A/B and 0 of 16
  here; pooled, 3 of 32. B's 3 of 16 is within that noise, so this A/B cannot show the field makes it worse. It does
  show the field does not stop it.
- **The field arrives too late.** The agent plans the batch before it reads the copy tab's result. A field in that
  result can only teach for later batches, and in all 3 B runs an earlier `new_refs: true` did not.
- **`navigate` is not covered.** In 3 of the 4 runs with a batched write here (A's one, two of B's), the copy's
  navigation was a `navigate` in the agent's own tab, not a `tabs new`.

## Limits

- **Rare event**, one model, one policy (`decline`), two attempts per unit.
- **Requests** count model requests that sent at least one tool call. The final answer request is not counted.
- **Branch.** B is a local branch, not a pull request.

## Artifacts (private)

- `artifacts/ab-472-new-refs-field/`: `run.sh`, `analyze.py` (the first A/B's, unchanged), `analysis.txt` and the
  per-round JSON.
- `artifacts/vendor/kitsune-main-c0ea723/` and `artifacts/vendor/kitsune-ab-472-new-refs-field/` (`dc7dc06`).
