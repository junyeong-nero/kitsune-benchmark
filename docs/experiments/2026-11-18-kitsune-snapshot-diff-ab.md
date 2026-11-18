# Kitsune A/B: repeated script snapshots show only changes

Third follow-up to the [five-surface comparison](2026-11-17-five-surface.md), after the
[default script tab](2026-11-18-kitsune-default-tab-ab.md) was merged (kitsune#552).

## Treatment

| Arm | Kitsune | `tab.snapshot()` in `browser_run_python` |
| --- | --- | --- |
| base | `26d91a1` (main with #552) | the whole tree every time |
| diff | `132a3d4` (`feat/python-snapshot-diff`) | the host remembers each scope's last snapshot (tab, target, depth, text) per MCP session; a repeat prints or returns only `+`/`-` lines (or a one-line "unchanged") when that is under 70% of the tree. The returned `str` is still the whole tree (`.full`), so slicing and `find` are unchanged. |

This mirrors Aside, whose `snapshot(page)` prints the diff since the scope's previous snapshot.
The matrix is the same as the earlier A/Bs: Codex `gpt-6.1-sol` and Opus, × 23 conditions
× 2 arms = 92 attempts, A/B order alternating, agent-owned personal tabs.

## Result (`artifacts/diff-ab-v1`): not supported

All 92 attempts were scorable. Success: Codex 22/23 in both arms (`ui-toast` in both),
Opus 23/23 in both.

| Model | personal | isolated | crowded | all: median / geomean input | calls | results shown as diff / unchanged |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex | 1.00 | 1.00 | 1.20 | 1.01 / 1.06 | 128 → 128 | 10 / 10 of 128 |
| Opus | 1.01 | 1.01 | 1.02 | 1.01 / 1.00 | 91 → 91 | 1 / 0 of 91 |

The feature rarely triggers. Agents seldom re-read the same scope; they read new scopes,
`query` or `text` instead. Opus got a diff once in 91 calls. Where it did trigger,
it helped. In Codex `ui-infinite@crowded`, 6 diffs and 2 "unchanged" results went with
input 0.47 and calls 25 → 13. The other Codex crowded pairs (`ui-sortable` 2.07,
`mm-chart` 2.31) saw no or one diff, so those ratios are single-repeat variance, not the
feature. The decision rule (≤ 0.90) is not met; do not merge. It could return as a narrow
fix for scroll-and-reread loops if those become a measured cost.

## Note

Kitsune main is now `26d91a1`. The five-surface `main` and `kitsune-owned` scopes and
the first two A/Bs pin `14d9ceb`. Rerun them with `--kitsune-project` pointing at a
`14d9ceb` checkout.
