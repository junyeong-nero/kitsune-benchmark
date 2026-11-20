# Benchmark documentation

## Current

- [Run the WebArena-Pro four-way matrix](../README.md): setup, commands and measurement rules
- [Latest report: WebArena-Pro, two agents, four tools](results/2026-11-20-webarena-pro-four-way.md) and its [per-attempt CSV](results/2026-11-20-webarena-pro-four-way.csv)
- [All result reports](results/README.md), newest first

## Historical records

Everything below documents retired harnesses. These pages are records, not instructions for the current runner: their commands and paths refer to files that no longer exist on `main`. To reproduce a retired experiment, use the revision named in its report or the [last pre-migration source tree](https://github.com/junyeong-nero/kitsune-benchmark/tree/1ef91e1).

**Tracks**

| Page | Topic |
| --- | --- |
| [personal-browsing.md](personal-browsing.md) | Personal browsing tasks inside an existing session (taskset v3/v4) |
| [coexistence.md](coexistence.md) | Agent and user sharing one browser (`coexistence-local-v3`) |
| [gallery.md](gallery.md) | Component gallery, crowded and isolated pages |
| [external.md](external.md) | MiniWoB++ and live sites (`external-v1`) |
| [hostile.md](hostile.md) | Hostile-UI capability matrix (draft) |
| [full-native.md](full-native.md) | Kitsune-only native tool groups |
| [personal-state.md](personal-state.md) | Personal-state track (specification only, never implemented) |
| [stress.md](stress.md) · [stress-comparison.md](stress-comparison.md) | Model-free shared-browser load tests |

**Harness and analysis notes**

| Page | Topic |
| --- | --- |
| [running.md](running.md) | Running guide for the retired harness |
| [codex-harness.md](codex-harness.md) | Codex harness integration |
| [resources.md](resources.md) | Local process resource collection |
| [optimization-findings.md](optimization-findings.md) | Token and latency investigation |
| [comparison-candidates.md](comparison-candidates.md) | Browser MCP candidates considered for comparison |
| [results/kitsune-versions.md](results/kitsune-versions.md) | Reports grouped by Kitsune revision |
| [experiments/](experiments/) | Pre-registered A/B and cohort protocols |
