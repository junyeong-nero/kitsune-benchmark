# Prepare a worker for four-surface-v1

**Goal:** qualify a new worker for the [32-start pilot](four-surface.md#schedule-and-denominators) without starting a model. This is an operator runbook, not an installer or evidence that a worker passed. On the development Mac, EgoLite could see a temporary grader-private file. No file contents were read. A fresh profile or an empty VM running everything as one unrestricted user does not fix that boundary.

## 1. Set up the boundary before signing in

Use a disposable **macOS** machine/VM with a GUI session for the installed vendor apps. Do not migrate a home directory, enable browser/iCloud sync, mount a personal disk or forward a keychain/SSH agent. A workable layout to qualify is two non-admin identities on the same OS, with OS-enforced file and network policy:

| Side | Must have | Must not have |
| --- | --- | --- |
| Controller | Private benchmark/product checkouts, fixtures, graders, evidence, Codex and Claude Code. Only the subscription clients need provider egress during a run. | Vendor scripts running with controller privileges. |
| Browser/tool runtime | Fresh benchmark browser profiles, vendor IPC, the current local fixture and required private browser-control channels. | Controller home, grader source/state, transcripts, CLI logins, unrelated local services or internet egress. |
| PNG handoff | One initially empty, access-controlled directory at the same absolute path on both sides; EgoLite writes a disposable PNG and the relay reads it. | Other files, symlinks, evidence directories or a shared home. Do not share all of `/tmp`. |

The runner uses stdio subprocesses and ephemeral `127.0.0.1` fixture ports. It does **not** configure identities, sandbox rules, a remote MCP transport or VM forwarding. Keep the fixture loopback reachable from the browser without exposing it on the LAN. Use an administrator-managed execution boundary for the **actual native script interpreter and its children**, not just the GUI: launching `ego-browser nodejs` as the controller still exposes its files. The controller calls the explicitly supplied `--aside-cli` executable with `mcp --host local --profile …`. The EgoLite probe and scored relay use the **same** explicitly supplied `--ego-cli` executable and `--ego-server-name`. Neither comparison route uses an implicit executable or retries on the default service. The native commands receive a minimal environment, not the controller's credentials. If the route is a restricted launcher, it must set the intended runtime identity/home and policy, preserve arguments, stdio and the native catalog, and not grant a general privileged shell. Names, file hashes and environment filtering alone do not enforce isolation. Verify the effective identities and policy on the deployed worker. If that integration is unavailable, **stop here**; `--dedicated-worker` is an attestation, not an isolation switch.

## 2. Stage and freeze the software

In the controller's **new, private** work directory, use Bash. Set `BENCH_REV` to the reviewed full benchmark commit, not a moving branch. Install Git, `jq`, Python 3.11+, uv, Node/npm and the approved vendor app builds before restricting runtime egress. The runner expects `/Applications/Aside.app` (`1.0.1116.2`) and `/Applications/ego lite.app` (`0.6.3.14`). Run `check-install` before any vendor launch: both bundles must pass `codesign --verify --strict` and match `vendor_gui_versions` in the registry. This is an integrity/version check, not proof of process identity or isolation. If it fails, obtain a verified vendor distribution of the pinned build. Do not strip metadata, bypass verification, re-sign, or substitute a newer release. Record app/CLI builds, executable hashes and any launcher/policy version privately; do not auto-update between pilot and main.

```bash
set -euo pipefail
umask 077
: "${BENCH_REV:?set the reviewed benchmark commit SHA}"
git clone https://github.com/junyeong-nero/kitsune-benchmark.git kitsune-benchmark
git clone https://github.com/junyeong-nero/kitsune.git kitsune
cd kitsune-benchmark
git switch --detach "$BENCH_REV"
test "$(git rev-parse HEAD)" = "$BENCH_REV"
registry=configs/benchmarks/four-surface-v1.json
git -C ../kitsune switch --detach "$(jq -r .kitsune "$registry")"
uv sync --locked
(cd ../kitsune && uv sync --locked)
npm ci --ignore-scripts --no-audit --no-fund
npm run setup:firefox
test -z "$(git status --porcelain)"
test -z "$(git -C ../kitsune status --porcelain)"
```

Only for the separate release A/B, create another clean product checkout: `git -C ../kitsune worktree add --detach ../kitsune-v0.8.0 "$(jq -r .release_base "$registry")"` and run `uv sync --locked` there. Do not move the candidate checkout. Reserve space for **both** the cell outputs and `artifacts/four-surface-v1/` raw evidence, plus the PNG drop. The runner stops below 2 GiB on either evidence filesystem; that floor is not a capacity estimate for 320 starts. Size from the retained pilot before starting main.

Install Codex `0.170.0` and Claude Code `2.1.327` on the controller PATH. Sign in there through their supported **subscription** flows, not through the vendor test profiles. No API keys, provider overrides, alternate models or copies of an existing login database. From a clean shell, check versions and login status locally (`codex --version`, `codex login status`, `claude --version`, `claude auth status`). Do not publish account details. CLI login is not a guarantee of model access or quota. The runner separately enforces the version pins for `gpt-6.2-sol` and `claude-opus-5-5` at medium effort.

In each vendor app, create **one new local test profile** with no sync, data imports, unrelated accounts, extensions or pre-existing work. Record those two IDs privately as `BENCH_ASIDE_PROFILE` and `BENCH_EGO_PROFILE`; do not enumerate everyday profiles to find one. Set `BENCH_ASIDE_BIN` and `EGO_BROWSER_BIN` to the absolute verified local CLI/launcher paths and `BENCH_EGO_SERVICE` to the non-default service name of the confirmed disposable browser. The CLI's `--host local` is **not** proof that its daemon belongs to that instance: verify ownership before attaching. Set `BENCH_PNG_DROP` to the dedicated directory above, outside the repository and all evidence roots, with runtime write and controller read/cleanup rights. The same resolved routes, profiles and drop are pinned across pilot/main. These variables supply the [execution arguments](four-surface.md#execution-and-publication); they do not start a daemon, create profiles or grant permissions.

## 3. Acceptance checks — zero inference

From the benchmark checkout, on the **same launch paths and policy** intended for the pilot:

```bash
B=(uv run --locked python scripts/run-four-surface.py)
"${B[@]}" check-install
"${B[@]}" check-worker --ego-cli "$EGO_BROWSER_BIN" --ego-server-name "$BENCH_EGO_SERVICE" --image-drop "$BENCH_PNG_DROP"
for scope in pilot main release; do
  "${B[@]}" plan --scope "$scope" | jq -r '[.scope, (.cells | length)] | @tsv'
done
uv run --locked python -m unittest tests.test_four_surface tests.test_four_surface_contracts tests.test_personal tests.test_personal_fixtures tests.test_gallery
KITSUNE_PROJECT="$(cd ../kitsune && pwd)" FOUR_SURFACE_NATIVE_TEST=1 \
  uv run --locked python -m unittest -v tests.test_four_surface_native
```

| Gate | Evidence required to proceed |
| --- | --- |
| Grader isolation | `check-worker` exits 0: the named EgoLite helper cannot access a synthetic private file in `artifacts/` and its native script writes the expected synthetic PNG to the separate drop. A visible file, missing/invalid PNG, unrecognized result or unreachable helper is a stop. This is not a screenshot or a browser rendering test; it does not qualify Aside, the network or a separate evidence mount. Verify those boundaries under the actual runtime identities using **disposable markers**, never real secrets, and retain the access-denial evidence privately. |
| Network and routing | From each actual browser/runtime, a harmless local test fixture loads; an operator-controlled destination outside the allowlist is denied by policy (confirm with the policy log). The controller's subscription login checks still work. Do not probe third-party sites. No localhost-wide or internet-wide exception to make the checks pass. |
| Profiles and PNG | Verify only the new test contexts are in use. In addition to the synthetic `check-worker` transfer, capture a screenshot of the rendered fixture via the actual isolated EgoLite browser path and verify the PNG reaches the controller. Use a separate disposable marker to confirm that the runtime cannot read or write the evidence directory. Remove only the test files. Neither profile ID, file path nor screenshot belongs in the PR. |
| Protocol | Plan counts are **32 / 320 / 12** in the order above. All 20 graders pass state and custody controls. Both opt-in native tests run (not skipped): all eight selected gallery goals, and the four pilot goals through each Kitsune/Playwright MCP relay with the starting cursor, catalog and tab custody checked. These are not vendor qualification or model scores. |

For the routing check, the operator can serve an empty temporary directory with `python3 -m http.server PORT --bind 127.0.0.1 --directory EMPTY_DIR`. Use one assigned fixture-test port and a second, deliberately disallowed test port under your control. Verify the first page renders in the designated profile and the second is blocked **while the listener is running**, not merely absent. Stop both temporary servers after the check. An additional deny rule for off-host traffic must cover the browser **and** native script processes; a failed loopback request alone does not establish that rule.

## 4. Handoff and stop rules

Give the operator the worker route, test profile IDs and absolute PNG path **privately**, not passwords, tokens or raw auth output. Record the reviewed benchmark and product SHAs, CLI and app builds, free space, and dated pass/fail evidence for each gate. An unknown gate means **not qualified**. Do not copy existing cohorts, change user profiles or relax the checks to obtain a pass.

After all gates pass, follow the [pilot → main commands](four-surface.md#execution-and-publication) using fresh private outputs. The main run needs a 32/32 measured, safe pilot on the same pins and profiles; task failures are retained and need not all be successes. If an attempt starts then fails instrumentation, preserve its directory and stop; never replace it. The 12-start Kitsune release check is separate, and the optional second dataset is not implicit. Only after reviewing all 320 measured main cells and their safety evidence should a separate Kitsune PR change `assets/benchmark-efficiency.svg`, its README caption and `docs/benchmark.md`. Do not tag a release as part of worker setup.
