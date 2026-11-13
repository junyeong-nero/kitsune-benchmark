# Protocol: scripting guide fixes (kitsune#519 / #520)

Frozen before counted runs. Completed 2026-11-11, 80/80: [results](../results/2026-11-11-kitsune-scripting-guide-ab.md). Reuse `scripts/run-scripting-ab.py` and the
[original surface A/B protocol](2026-11-11-kitsune-scripting-surface-ab.md), without changing its runner,
tasks, scoring, order or stopping rules.

## Source and scope

- Kitsune validation snapshot: `20838b68e5e3afb494e38d91a403167b0e007eb1`, a local detached commit in
  `artifacts/vendor/kitsune-scripting-guide-519-520-20261111/`.
- Parent: main `89d883a145f705152f5a6727b0e2e14df61cacd6`.
- Snapshot changes only the Python tool guide, its regression tests and documentation. Browser API return
  types, capabilities, modes, default tool definitions and the minimal tool selection are unchanged.
- The guide uses execution capabilities (not publication capabilities), omits query without `read`, omits
  fill in read mode, and explicitly describes `browser.tabs()` as dicts with actual IDs.
- The operator's original Kitsune working tree is not committed or switched; the snapshot is not pushed.
- Benchmark code: `5191c8a176446120ddf48f98adc46bad21c423ac`; this added protocol does not change execution.
- Previous counted A/B used `362c1fd`. Current main additionally includes #494/#496's concurrent handoff
  work. Both new arms use the same new snapshot; historical comparisons are descriptive, not an isolated
  estimate of the guide patch's effect.

## Arms and units

Same clean snapshot for both arms. Legacy has 27 tools; scripting sets `KITSUNE_SCRIPTING=1` and has 14.
No benchmark allowlist. Default `KITSUNE_CAPS=core`, act mode and read-only user tabs are retained.

Claude Opus 5.5 (`claude-opus-5-5`), medium, Claude Code `2.1.303`, subscription authentication;
no API-key fallback. Private Firefox, extension copy, bridge home and ports. No user's browser profile
or default bridge is used.

20 tasks × 2 repeats × 2 arms = 80 runs, in the original repeat-major ABBA order:

- 7 MiniWoB++ tasks, external-v1 seed 42, source `33c3b4ddef8c6eb67c57a29663d844b1eda7e614`.
- 7 personal v0 tasks: current, tabs, research, account, handoff, safe, longpage.
- 6 gallery v0 isolated tasks: table, autocomplete, infinite, shadow, iframe, editor.
- Elicitation: decline.

Smoke, not counted: mw-click-test-2 in each arm and pb-current-01 in scripting. Do not start counted
runs if a smoke has a setup failure, is unscorable, fails its task or exposes the wrong tool count.

## Estimands and decision

Retain the original primary estimand: summed scripting / legacy input on matched (task, repeat) cells
both arms solved. Secondary: success, first-request input, model requests, MCP calls, elapsed time and
list-price cost (a comparison metric, not an API bill for the subscription).

Original support rule: input ratio ≤ 0.90 with successes not lower by more than one in any track;
ratio ≥ 1.00 is not supported; otherwise inconclusive.

For #519/#520 also inspect every Python call and corresponding result:

- `capability_restricted` failures;
- dict-related `AttributeError` failures;
- any other Python failures, including those replacing the original errors;
- how many runs actually exercise Python. No Python use is not evidence of a corrected execution path.

Keep the original URL/reward-pattern integrity audit. No automatic retries or substitutions of model,
harness, tasks or capabilities. Stop on harness errors, two consecutive unscorable runs, a dirty/changed
Kitsune snapshot or a tool-count mismatch. Keep any incomplete run artifacts.

Decide #521 only after this evidence: do not remove more direct tools merely to shrink the prefix.
Judge overall requests and cost as well as input and success; two repeats remain a small descriptive sample.

## Artifacts

Counted log and analysis: `artifacts/scripting-guide-ab-519-520/{runs.jsonl,analysis.json}`.
The unchanged runner stores uniquely named per-run directories under `artifacts/scripting-ab/`;
the new log identifies which ones belong to this rerun. Existing artifacts are not overwritten.
