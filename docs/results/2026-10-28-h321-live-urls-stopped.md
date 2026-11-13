# H321 (truncated snapshots list no link URLs, live sites) — stopped: the change was never exercised

[Results index](README.md) · [Frozen protocol](../experiments/2026-10-28-h321-live-urls-ab.md) ·
[kitsune#321](https://github.com/junyeong-nero/kitsune/issues/321)

**No verdict.** The operator stopped the cohort after 9 of 36 runs: the 6 live runs and 3 guard runs below. The
protocol did not predeclare this stop. The reason: none of the live runs was exposed to the intervention, so the
primary estimand could only measure noise.

## Why

B changes only a snapshot that is cut for budget and has no target. In all 6 live runs (3 tasks × both arms), the
agent took **no untargeted `browser_snapshot`**:

- It opened the page with `browser_tabs new` and navigated with `browser_find`.
- When it needed a scoped view it used `browser_snapshot` with a `target` (`e24`, `.infobox`, `e107`).
- The driver's in-effect counter saw 0 truncated snapshots on either arm.

The no-model arm check showed the change in effect on the same pages, but only for the first core snapshot. That is
a call these agents do not make on these tasks. The guard runs took full snapshots, as expected for small fixture
pages, which are never cut.

| # | Cell | Arm | Requests | Input | Untargeted snapshots |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | Steam | A | 11 | 185,497 | 0 |
| 2 | Steam | B | 13 | 231,784 | 0 |
| 3 | Wikipedia | B | 6 | 109,806 | 0 |
| 4 | Wikipedia | A | 8 | 91,931 | 0 |
| 5 | MDN | A | 7 | 85,108 | 0 |
| 6 | MDN | B | 7 | 80,973 | 0 |
| 7 | isolated `ui-shadow` | B | 5 | 52,266 | 3 |
| 8 | isolated `ui-shadow` | A | 4 | 41,184 | 3 |
| 9 | isolated `ui-select` | A | 4 | 40,619 | 3 |

These pairs differ by model path only; they say nothing about the change. A tenth run, isolated `ui-select` on B,
was in progress at the stop. It finished, but it is not logged.

## Where the live-task observations go instead

Live runs on Kitsune, measured by tool-result characters: the 6 runs above plus the 3 live runs of
[2026-10-28](2026-10-28-new-tracks-v0.7.0.md).

- **`browser_find` produces 83%** (191,722 of 230,712 characters). Snapshots produce 5%.
- **Large single results:** single `browser_find` results reach 39,630 characters (a broad regex on Wikipedia). A
  text query, `"Winner"` on Steam, returns 12.7–13.7k.
- **Waste inside the 41 `browser_find` results:**
  - 18% of characters repeat the matched line in `match`, although it is already in `lines`;
  - 23% of the context lines duplicate overlapping windows of neighboring matches;
  - 33% of the context characters are `/url` lines;
  - 64 of 368 matches (17%) hit a `/url` line rather than the link's text.

So for this agent on live sites, the size of `browser_find` results is the main lever. Snapshot truncation is not.
This report does not test a change to `browser_find`.

## Follow-up

kitsune#321 was closed as not planned. The `browser_find` lever is kitsune#323. The intervention commit `9608032` is kept as the Kitsune tag `h321-intervention`; its branch `exp/drop-urls-when-truncated` was deleted.

## Raw evidence

Private: `artifacts/h321/` (runs.jsonl, driver logs), with pair directories under `artifacts/external` and
`artifacts/gallery`.
