# Native preflight repair: coexistence and viewport

2026-11-10 · fixes #136 and #137 · prerequisite evidence for
[junyeong-nero/kitsune#498](https://github.com/junyeong-nero/kitsune/issues/498).

This is a **no-model test report**, not a model benchmark or a tool-set rollout
verdict. No model requests, API charges, or subscription agent runs were made.
Tasks, fixtures, graders, permissions and production harness code are unchanged.

## Baseline and reproduction

- Benchmark baseline: `53d6a9b4a5dcb8f7d2f617a9e347d6af327d3ec0`.
- Current Kitsune product: `fd9b90e1cfae702b8470fcfca5d1bd178dba2c94`.
  The tested checkout is `cb3bc27`, the test-only repair in
  [Kitsune PR #505](https://github.com/junyeong-nero/kitsune/pull/505).
- Browser: existing private Firefox `firefox-1553`; Playwright MCP `0.0.83`.
- macOS arm64. Each native test uses a fresh profile and private bridge ports.

Before the repair, the two `NativeKitsuneCoexistenceTests` failed because a new-tab
result already included its page snapshot. The following `browser_snapshot`
returned `unchanged_since`, so the scripted reference found neither the `메모`
nor the `점검일` textbox (#136).

`NativeKitsuneViewportTests` errored in all three subtests: its old setup attempted
to navigate the user's tab, first receiving `no_current_tab`, then
`user_tab_read_only` (#137). The combined reproduction ran three tests with two
failures and three subtest errors in 25.718 seconds.

## Repair

- The coexistence reference consumes a full snapshot already returned by its
  new/select call. If none was supplied, it still requests a snapshot. An
  `unchanged_since` marker or a partial delta is not treated as a full tree.
  Two new offline tests cover reuse, fallback, and both Kitsune JSON and
  Playwright Markdown responses.
- The Kitsune viewport check seeds its initial tabs through the existing user
  channel, as the personal track does. It asserts zero agent-owned seeded tabs,
  opens its own tab for observation, and checks that this tab is owned/current.
  No writable-user-tabs setting or capability escalation is used.
- Viewport reports, invisibility assertions, initial-state verification,
  forbidden-action checks and mutation checks remain in place. No task content
  or grader threshold was changed.
- New release-cohort preflights explicitly run the native coexistence and
  viewport tests. The dated addendum does not retroactively claim older cohorts
  passed them.

## Validation

| Check | Result |
| --- | --- |
| Default offline discovery | 412 tests; 18 opt-in skips; no failures/errors; 273.584 s |
| New snapshot helper tests plus native Kitsune/Playwright coexistence and viewport | 8 tests; all passed; 54.865 s |
| Kitsune v0.7.2 (`28ca61c`): both coexistence tests and viewport (three subtests) | 3 tests; all passed; 36.399 s |
| Kitsune `ad04bac`: both coexistence tests and viewport (three subtests) | 3 tests; all passed; 31.942 s |

The current-revision native run overlapped with offline discovery; its elapsed
time is diagnostic, not a runtime comparison. The compatibility runs were
sequential. The native Playwright coexistence tests include negative controls
for user-view/input disturbance: their passing assertions are not a claim that
Playwright preserved user input.

The viewport checks again measured:

| Configuration | Content viewport | Outer window | DPR |
| --- | --- | --- | --- |
| Kitsune window 1280×720 | 1280×635 | 1280×720 | 1 |
| Kitsune window 1280×805 | 1280×720 | 1280×805 | 1 |
| Playwright viewport 1280×720 | 1280×720 | 1280×805 | 1 |

All reports within each checked case agreed. The two Kitsune long-page window
sizes and the equalized original-family task passed on the current product,
v0.7.2, and `ad04bac`. Frozen-task byte-identity and grader tests remained green
in default discovery.

## Reproduce

From the benchmark repository, with an absolute path to the Kitsune checkout:

```sh
uv run --locked python -m unittest discover -s tests -q
PERSONAL_BROWSER_TEST=1 PERSONAL_KITSUNE_TEST=1 KITSUNE_PROJECT="$PWD/../kitsune" \
  uv run --locked python -m unittest discover -s tests -p test_coexistence.py -v
PERSONAL_BROWSER_TEST=1 PERSONAL_KITSUNE_TEST=1 KITSUNE_PROJECT="$PWD/../kitsune" \
  uv run --locked python -m unittest discover -s tests -p test_taskset_v3.py -k Native -v
```

For compatibility checks, set `KITSUNE_PROJECT` to the clean pinned checkout and
select the `NativeKitsune` tests. Installed private browser/npm tools and the
existing isolated Kitsune helper's CLI prerequisites are required. Resolving the
Codex executable in that helper does not execute Codex or make model calls.

This evidence repairs the named baseline checks only. It does not validate the
future delegated runner, turn the relay into a script sandbox, or authorize a
model comparison or default switch for Kitsune #498/#504.
