# H323: compact `browser_find` results — Kitsune A/B

[Results index](README.md) · [Frozen protocol](../experiments/2026-10-29-h323-find-compact-ab.md) ·
[kitsune#323](https://github.com/junyeong-nero/kitsune/issues/323)

**Verdict: support** under the predeclared rule, by a small margin.

| Measure | Result | Threshold |
| --- | --- | --- |
| Primary input ratio, 16/16 joint pairs | **0.878** | ≤ 0.90 |
| Pooled guard input ratio | 0.963 | ≤ 1.05 |
| Gates | every gate holds: all 44 runs succeeded; advisory matches 8/8 on both arms for Wikipedia and MDN | |

- **Live cells alone:** input ratio 0.841.
- **`browser_find` result characters:** 164,998 → 112,410 (0.68).

The gain is concentrated where results were large. MDN and the long personal page cost more on B; see
[Per cell](#per-cell).

## Setup

- **Arms:**
  - A: Kitsune main `5dbcaff`.
  - B: `exp/find-compact` `2459e95`, which changes only core `browser_find`'s inline result.
  - Both were clean worktrees, with revisions checked before every run.
- **Harness:** Claude Code `2.1.303` on the subscription, `claude-opus-5-5`, medium, Kitsune target only.
- **Benchmark source:** main `615cd26`. The protocol was frozen in kitsune-benchmark#41 before the first run.
- **Runs:** 44, repeat-major, ABBA/BAAB per cell. No unscorable run, no stop, no retry.
- **In effect:** every find result on B had the new format and every result on A the old one. The driver would have
  stopped otherwise.

## Per cell

| Cell | Input A → B | Ratio | Requests A → B | Find calls A → B | Find chars A → B | Per-pair input ratios |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Wikipedia (live) | 480,156 → 298,382 | **0.62** | 37 → 26 | 23 → 14 | 66,083 → 53,186 | 0.98, 0.36, 0.70, 0.66 |
| Steam (live) | 982,628 → 827,131 | **0.84** | 57 → 59 | 30 → 30 | 78,110 → 42,602 | 0.64, 0.86, 0.88, 1.07 |
| MDN (live) | 317,042 → 371,642 | 1.17 | 28 → 33 | 12 → 14 | 14,108 → 9,435 | 1.14, 0.97, 1.02, 1.54 |
| `pb-longpage-01` (graded) | 296,123 → 324,660 | 1.10 | 25 → 27 | 6 → 8 | 6,697 → 7,187 | 1.20, 1.20, 1.00, 1.00 |
| **Primary, pooled** | 2,075,949 → 1,821,815 | **0.878** | 147 → 145 | 71 → 66 | 164,998 → 112,410 | |
| Guard isolated `ui-shadow` | 134,273 → 123,517 | 0.92 | 13 → 12 | 0 → 0 | | 0.79, 1.00, 1.00 |
| Guard isolated `ui-select` | 121,360 → 122,675 | 1.01 | 12 → 12 | 0 → 0 | | 1.00, 1.00, 1.04 |

Other totals over the primary pairs (A → B):

- MCP calls 162 → 162;
- elapsed 541 s → 492 s;
- output tokens 16,484 → 15,784;
- recovered tool errors 0 → 1.

## What the traces show

- **Wikipedia:** B's results were cut at 8k and still contained the answer. The agents needed fewer follow-up
  searches: 23 → 14 find calls, 37 → 26 requests.
- **Steam:** the same number of searches, with about half the find characters. Each later request re-sends less.
- **MDN** (find results are already small, about 1–3k):
  - The extra cost comes from model paths, not from result size. In the 1.54 pair, B's first `/Firefox/` search
    returned 0 matches before the compatibility table had rendered. The agent then searched, clicked and waited.
  - A also takes such detours on this page, but with only four pairs each arm's share of them is chance.
- **`pb-longpage-01`:**
  - On both arms the first `"R17"` result holds the same lines: B's single merged block, A's four windows.
  - In 3 of 4 runs on B, against 1 of 4 on A, the agent made one more search to check the following item before
    saving.
  - With four pairs this cannot be told apart from model variance. Whether merged windows without per-match
    boundaries prompt that check is untested.

## Interpretation and limits

- **Where it helps:** compact results help most where `browser_find` results are large, which is typical of real
  content pages (Wikipedia, Steam). On pages where they are already small, the change is neutral by construction, and
  the model's path dominates the cost.
- **Margin:** the verdict depends on four cells with four pairs each, and the support threshold was met by 0.022.
  A repeat cohort, or more live pages, would show whether 0.88 holds.
- **Risk not exercised:** B no longer shows a non-matched link's URL in a window. No run here needed one; in the
  2026-10-28 runs, one Steam run navigated by such a URL.
- **Scope:** one model, effort and harness; Kitsune only; live pages as of 2026-10-29.
- **Raw evidence** is private: `artifacts/h323/`, with pair directories under `artifacts/external`,
  `artifacts/personal` and `artifacts/gallery`.

## Reproduce

```sh
uv run --locked python scripts/run-h323.py analyze   # from artifacts/h323/runs.jsonl; no browser or model
```
