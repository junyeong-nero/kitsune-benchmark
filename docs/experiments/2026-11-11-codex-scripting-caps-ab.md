# Codex: scripting core vs the new unset-CAPS default

Frozen before model execution. Follow-up to the [legacy/scripting cohort](../results/2026-11-11-codex-scripting-ab.md).

## Question and implementation

Does enabling ordinary Python browser functionality without enlarging the MCP tool list remove the observed
capability failures, and does that improve task success/efficiency?

Kitsune commit `c698d408d1c77eb708e853649bde4085a0d87ac8` changes only default selection: with
`KITSUNE_SCRIPTING=1` and `KITSUNE_CAPS` absent, use `all`; explicit CAPS values always win, including empty.
Legacy still defaults to `core`, scripting remains opt-in, `storage/history` remain excluded from `all`, and
user-tab, mode, approval and bridge-auth protections are unchanged. Tests/docs accompany that change.

## Arms and fixed conditions

Both arms use that same clean patched checkout:

| Arm | Environment | Expected published tools |
| --- | --- | ---: |
| `core` | `KITSUNE_SCRIPTING=1`, `KITSUNE_CAPS=core` | 14, including Python |
| `default` | `KITSUNE_SCRIPTING=1`, **CAPS unset** | 14, including Python |

This isolates the new default while holding implementation revision constant. The Python tool's existing guide
is capability-aware: `default` also advertises its enabled `read` example and group names. That is part of the
configuration's real behavior, not an independently varied prompt change. No method signatures or task prompts
are modified. No benchmark tool allowlist is added.

- Codex `0.163.0`, `gpt-6-luna`, medium, ChatGPT subscription; no API-key billing.
- Same 20 tasks, seed/variant, fixtures, graders, timeouts and original ABBA ordering as the preceding experiment:
  7 MiniWoB seed 42, 7 personal variant 0, 6 isolated-gallery variant 0; 2 repeats per arm, **80 attempts**.
- Fresh private Firefox and bridge per attempt. No normal user profile or real account.
- Actual published catalogs from the personal/gallery relay; MiniWoB only has no-model server preflight, not
  client inventory attestation. Record that limitation rather than inventing a published count.

## Outcomes and stopping policy

Primary mechanism check: inspect Python failures by error code, especially `capability_restricted` on `/api/scroll`,
`/api/page-text` and `/api/page-info`, plus `ui-infinite` completion in both repeats. Verify safety remains intact.
Report every attempted task's outcome, not only successes. This short run does not establish statistical superiority.

Efficiency: matched (task, repeat) cells both arms solved, ratios **default / core** for input/output tokens,
MCP calls and elapsed. Input includes cache hits; report cache totals separately. Do not use lower token spend
from early failures as an efficiency win. Codex has no model-request/first-request-input/dollar-cost metrics here.

Retain the operator-approved policy from the preceding cohort: a normally completed MiniWoB attempt with zero
episode starts, zero telemetry errors and `no_terminal_reward` is preserved as unstarted/unscorable, not retried,
and does not stop the cohort. Other execution, quota, unscorable, source or catalog failures stop for review.
No automatic model substitution or source fix while counted attempts are running. Existing script URL/reward
pattern audit is reviewed after execution; it is not a hardened anti-cheating boundary.

## Run

```sh
uv run --locked python scripts/run-codex-scripting-caps-ab.py run \
  --kitsune-project ../kitsune-scripting-caps-default \
  --kitsune-sha c698d408d1c77eb708e853649bde4085a0d87ac8 \
  --out artifacts/codex-scripting-caps-default-c698d40 --continue-unstarted

uv run --locked python scripts/run-codex-scripting-caps-ab.py analyze \
  --out artifacts/codex-scripting-caps-default-c698d40
```

The runner reuses the prior Codex implementation with explicit arm environments, labels and both tool counts at 14.
Manifests preserve source and runner hashes. The older Claude/Codex cohorts are not rewritten or pooled with this one.
