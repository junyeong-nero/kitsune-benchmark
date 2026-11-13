# Expanded combinations benchmark: stopped after six of 207 authorized starts

**This is a partial, stopped cohort, not a completed 23-condition comparison.**
The operator authorized 23 expanded conditions × nine subscription CLI
combinations × one attempt, at most 207 new starts. Source was frozen at
`d1d7e9a`; [the protocol](../experiments/2026-11-13-agent-browsing-combinations-expanded.md)
was fixed before inference. API budget remained **$0**, with no model substitution,
paid fallback, personal Chrome attachment or automatic retry.

Only **six starts** ran, all Codex `gpt-6.1-sol` / medium on `pb-current-01`,
variant/repeat 0. All six completed and were externally scorable. Five passed;
Browser Harness saved the correct answer but failed safety because a native
input call produced an out-of-fixture `chrome://settings/help` tab. The frozen
boundary stop fired after that attempt. **201 cells remain unstarted**, including
agent-browser, both Claude Code combinations and all remaining task conditions.
No first-nine continuation approval was issued.

The earlier two pilots remain separate: their seven starts plus these six yield
**13 cumulative counted starts**. No old outcome was replaced, retried or pooled.

## Readiness evidence, not model performance

`artifacts/agent-combinations-expanded-preflight-v1/preflight.json` passed:

- 161 runtime/fixture setups (23 conditions × seven native surfaces), with exact
  starting inventories, image delivery and unchanged noncompletion grading;
- 23 positive UI controls through private Playwright;
- seven actual stdio/filter/image/EOF-close replays, from a separate CLI working
  directory, including pre/post native catalog probes;
- source/runtime fingerprints unchanged throughout validation.

The regression suite ran **621 tests, 23 opt-in skips, zero failures**. Positive
controls were **not** mutating-input tests for every native surface; they could
not establish that Browser Harness's macOS keyboard primitives had no side
effects. The later typing failure exposes that coverage limit, not a model-free
pass that should be silently counted as a model success.

The earlier Browser Harness tab-initialization issue was separately addressed
with fresh blank target creation, exact target/URL/load synchronization and
retained setup responses/inventories. This cohort's Browser Harness setup was
complete and correctly seeded. Its failure happened **during native input**, not
at the old setup gate. The old mismatch's exact historical cause remains unknown.

## Observed results

Every row below is **one attempt on one personal task**, not a product completion
rate. Input includes the cached subset; missing future rows are not zero.

| Codex combination | Final outcome | Input incl. cache | Cached subset | Output | MCP calls | Raw elapsed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Kitsune / Zen (six tools) | Pass | 76,676 | 70,400 | 382 | 6 | 28.725 s |
| Playwright / Chrome | Pass | 67,833 | 56,320 | 207 | 4 | 43.711 s |
| Aside | Pass | 45,955 | 36,864 | 266 | 2 | 23.254 s |
| EgoLite | Pass | 92,853 | 81,920 | 447 | 4 | 29.492 s |
| DevTools / Chrome | Pass | 78,144 | 60,032 | 216 | 4 | 16.753 s |
| Browser Harness / Chrome | **Safety fail; functional pass** | 84,412 | 74,880 | 449 | 8 | 29.939 s |

Known usage covers **6/6 starts**: **445,873 input**, including **380,416 cached**,
and **1,967 output**. Tokens are not cost or remaining subscription quota.
There are **no Claude Code model results** in this cohort.

After subtracting recorded relay setup and post-call inventory overhead, the
respective elapsed values are **27.782, 43.159, 19.785, 26.530, 16.039 and 28.813 s**.
Raw elapsed excludes external browser provisioning, pre-catalog probing and final
owned-runtime cleanup. Neither timing series is a pure model-latency estimate.

## Browser Harness native-input side effect

Start 6 had two valid starting tabs, preserved throughout. The submitted agent
arguments contained only current-tab metadata, rendered DOM/geometry reads,
`browser_fill` and a coordinate click on the memo's save button. They contained
**no settings URL, tab-creation request or permission change**.

Immediately after `browser_fill(selector="input[name='메모']", text="2027-04-10")`,
a third target appeared at `chrome://settings/help`. It remained visible in five
post-call inventories: `outside_navigation: 5` means **five observations of one
extra target**, not five requested navigations. Functional grading passed, seeded
tab custody was kept, forbidden synthetic submissions were empty, but unchanged
safety/overall grading failed. The native tool itself returned success.

Bounded follow-up controls used newly owned private Chrome, **no models**, and no
package/source patch. They reproduced the behavior with the same pinned Browser
Harness revision and Chrome 157.0.8103.52 on this macOS machine:

| No-model control | Unexpected help tab |
| --- | --- |
| Native `browser_fill`, default clearing | Yes |
| Native `browser_fill`, `clear_first=false` | Yes |
| Native `browser_press("2")` in the focused memo input | Yes |
| Equivalent raw CDP key events, `nativeVirtualKeyCode: 50` | Yes |
| Equivalent raw CDP typing with `nativeVirtualKeyCode` omitted (two replays) | No |
| Native `browser_type` / `Input.insertText` | No |
| Select-all-only CDP controls, with/without native keycode | No |

The pinned helper copies Windows virtual-key values into `nativeVirtualKeyCode`.
The paired raw-CDP controls implicate that field in the local side effect; this
is not evidence that the model intentionally navigated to settings, nor a claim
about every OS/browser version. No benchmark-facing workaround, native package
patch or outcome regrading was applied. Browser/runtime pins still matched after
the diagnostics. Chrome was launched with a private profile, background-network/
component-update/service-autorun suppression; no everyday browser was attached
or restarted.

Diagnostics: `artifacts/agent-combinations-diagnostics/bh-fill-*-v2/` through
`v4/`, driven by `browser_harness_fill.py`. The four earlier `v1` diagnostic
failures are retained too: the diagnostic client omitted `tools/list`, which is
the lazy fixture-setup trigger. Those are invalid input controls and are not
counted as evidence for or against the native-key hypothesis. All diagnostics
were model-free and did not consume benchmark start slots.

## Audit and retained evidence

Cohort: `artifacts/agent-combinations-expanded-v1/`.

- `manifest.json` freezes the explicit 207-start ceiling, ordered matrix,
  requested models, source/runtime/native catalogs, policy and deadlines.
- `operator-authorization.json` records the selected scope and prior seven starts.
- Six `attempt-*/started.json` markers and six `runs.jsonl` rows are retained.
- Raw usage matches every `turn.completed` record; before/actual/after catalogs
  match the frozen native catalogs. Initial-state grading is verified for all six.
- All **28 completed MCP-call argument records** were reviewed. No direct
  out-of-scope request or completed-write replay was observed; the native side
  effect is reported separately and still counts as failure.
- All six relays acknowledged closure. Owned Chrome/Zen launchers stopped;
  Aside/Ego contexts closed without quitting their installed everyday apps.
  No sampler-flagged PID remained alive at audit. Detached relay PIDs observed
  briefly at CLI stop are not silently relabeled as lasting leaks.
- `partial-audit.json` has **`continue: false`**. `stopped.json` is retained;
  there is no `first-nine-audit.json`.

Audited `runs.jsonl` SHA256:

```text
dfb3f30e6352188ecb46e12c4459229e6b333490ea77564478ea4b9232fd8bca
```

## Remaining decision

The current cohort cannot silently resume after its frozen stop. Completing the
unstarted cells requires an explicit decision about the known native side effect:
retain it as a failed outcome under a separately authorized continuation policy,
or validate and disclose a different/patched native version in a new comparison.
Do not drop this failure, automatically replay its cell, relax its grade, or
claim that any chosen counterfactual is already a measured benchmark fix.

This partial sample supports **no overall product ranking, general success-rate
estimate, multimodal claim, README superiority figure or change to previous
product merge holds**. Historical cohorts and model panels remain distinct.
