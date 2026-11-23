# Benchmark documentation

[Project README](../README.md)

| Page | Contents |
| --- | --- |
| [running.md](running.md) | Four-way setup, billing order and guards, output handling, measurement rules; the local fixture track on macOS / Windows; analysis and tests |
| [results/](results/README.md) | Reports from the current `four-way/` suite |
| [archive/](archive/README.md) | Reports from retired harnesses, kept as records |

Source layout:

| Path | Role |
| --- | --- |
| `benchmark.py` | Plans or executes the four-way matrix |
| `local.py` | Plans or executes the local fixture track (macOS, Linux, Windows) |
| `local-tasks/` | The 12 loopback fixtures, their server and a model-free Firefox check |
| `four-way/framework/` | One attempt: site reset and login, browser arm, Claude Code invocation, transcript parsing, grading; shared by `local.py` |
| `four-way/testset/webarena-pro.json` | Frozen 26-task manifest |
| `summary.py` | Summaries and shareable CSV from `results.jsonl` |
| `tests/` | Offline tests |
