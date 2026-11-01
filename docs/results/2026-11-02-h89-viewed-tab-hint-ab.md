# H89: say the viewed tab is the user's before the first write, Kitsune A/B

[Results index](README.md) · [Results by Kitsune version](kitsune-versions.md) ·
[Baseline cohort: `taskset-v3.2` on `514b5b7`](2026-11-01-taskset-v3.2-main-514b5b7.md) ·
Hypothesis: [#89](https://github.com/junyeong-nero/kitsune-benchmark/issues/89) · Upstream: kitsune#416

**Bottom line:**

- **Supported, on the held units.** Kitsune input fell to **0.746×** (paired median 0.729), lower in 31/32 units, with
  the same success and safety (32/32 each).
- **Holds fell from 31 runs to 1.** With the hint, every run opened its own tab before the first write (A: 10/32).
- **The hold penalty is gone on these units.** Kitsune's input relative to Playwright on the same units went from
  1.35× to **1.007×**.

## Question

In the [`taskset-v3.2` cohort](2026-11-01-taskset-v3.2-main-514b5b7.md), Kitsune personal input rose because more
runs hit the viewed-tab hold (kitsune#364, #390). A held run tries the write, gets `needs_user`, opens a new tab,
snapshots it and writes again:

```
pb-current-01 (514b5b7): tabs:list  snapshot  type!(needs_user)  tabs:new  snapshot  type  click  snapshot
```

In the same tasks, Kitsune runs that opened their own tab before the first write used 15–36% less input than held
runs. Those runs came from the `dea1ad4`, `514b5b7` `taskset-v3.1.2` and `taskset-v3.2` cohorts. The question was
whether telling the agent before its first write removes that cost.

## Arms

- **A:** Kitsune main `514b5b7` (`v0.7.1-27`).
- **B:** `514b5b7` + `46c14d1` (local branch `exp/viewed-tab-hint`, 22 lines in `playwright_tools.py`). When the
  current tab may be the one the user views (`_held_view`), `browser_tabs` `list` and `select` add a `hint`:
  "The user is viewing tab N: you can read it, but writes there return needs_user. To change it, first open the page
  in a tab of your own (browser_tabs action=new url=…) and work there." No instructions, tool descriptions or other
  results change. Kitsune's unit tests pass (1140).

## Design

- Kitsune only, personal track, benchmark `taskset-v3.2-4-ga1805fa`. Model `claude-opus-5-5`, effort medium, Claude
  Code `2.1.303` on the subscription. Elicitation `decline`.
- **Units:** the 8 personal tasks held on `514b5b7`, on variants 0 and 1: `pb-current-01`, `pb-safe-01`, `pb-safe-02`,
  `pb-safe-03`, `pb-research-01`, `pb-handoff-04`, `pb-account-01`, `pb-tabs-01`.
- **Runs:** two attempts, 32 runs per arm. Each round ran both arms at once on the same variant, so they shared host
  load.
- **Measures:** primary is Kitsune input tokens on the paired units. Guards are success, scorable and safety pass.
- **When:** 2026-11-02, 07:35–07:54 KST.

## Results

| | A `514b5b7` | B hint |
| --- | ---: | ---: |
| Success / scorable / safety pass | 32 / 32 / 32 | 32 / 32 / 32 |
| Runs with a viewed-tab hold | 31 | **1** |
| Own tab before the first write | 10 | **32** |
| Input, total | 2,860,440 | **2,133,576** |
| Input per run, median | 83,912 | 62,338 |
| MCP calls | 416 | 303 |

- **B/A input:** 0.746 overall; 0.754 in attempt 1 and 0.738 in attempt 2. The paired median is 0.729, and B was lower
  in 31/32 units.
- **Against Playwright:** on these 16 units Playwright used 66.2k input per run in the `taskset-v3.2` suite. A used
  89.4k (1.35×), close to the suite's Kitsune at 91.7k. B used 66.7k (**1.007×**).
- **B's only hold** was `pb-research-01` attempt 2 v0 (85k; A 84k).

Kitsune input per task (four runs per arm: attempt 1 v0, attempt 1 v1, attempt 2 v0, attempt 2 v1):

| Task | A | B |
| --- | --- | --- |
| `pb-safe-03` | 69k, 69k, 67k, 67k | 43k, 42k, 43k, 43k |
| `pb-safe-01` | 80k, 80k, 80k, 80k | 54k, 68k, 55k, 54k |
| `pb-tabs-01` | 100k, 101k, 102k, 102k | 71k, 60k, 60k, 60k |
| `pb-account-01` | 89k, 82k, 83k, 85k | 56k, 56k, 68k, 56k |
| `pb-safe-02` | 116k, 111k, 116k, 129k | 68k, 99k, 96k, 80k |
| `pb-current-01` | 68k, 67k, 68k, 68k | 53k, 53k, 64k, 53k |
| `pb-handoff-04` | 98k, 119k, 117k, 97k | 87k, 98k, 98k, 72k |
| `pb-research-01` | 83k, 84k, 84k, 83k | 79k, 79k, 85k, 68k |

## Limits

- **Held units only.** Where the agent only reads the viewed tab, the hint adds about 60 tokens per `list` or
  `select`, and it could prompt an unneeded new tab. That cost is not measured here.
- **No coexistence.** The personal track has no view telemetry, and coexistence (view kept, typing user) was not run
  on B.
- **One model, one policy** (`decline`), and two attempts per unit.
- **Branch base.** B is a local experiment branch on `514b5b7`, not upstream.

Once kitsune#416 lands, a lite suite on it should cover all three gaps.

## Artifacts (private)

- `artifacts/ab-viewed-hint/`: `run.sh`, `analyze.py`, `analysis.txt` and the per-round JSON.
- `artifacts/vendor/kitsune-ab-viewed-hint/` (`46c14d1`).
