# Benchmark documentation

[Project README](../README.md)

| Page | Contents |
| --- | --- |
| [running.md](running.md) | Setup, billing order and guards, output handling, measurement rules, analysis and tests |
| [results/](results/README.md) | Reports from the current `four-way/` suite |
| [archive/](archive/README.md) | Reports from retired harnesses, kept as records |

Source layout:

| Path | Role |
| --- | --- |
| `benchmark.py` | Plans or executes the matrix |
| `four-way/framework/` | One attempt: site reset and login, browser arm, Claude Code invocation, transcript parsing, grading |
| `four-way/testset/webarena-pro.json` | Frozen 26-task manifest |
| `summary.py` | Summaries and shareable CSV from `results.jsonl` |
| `tests/` | Offline tests |
