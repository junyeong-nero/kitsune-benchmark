"""Offline review of a full-suite output directory: audit, outcomes, Kitsune/Playwright ratios, outliers, tool errors
and agent-behaviour signals. No model or browser calls.

usage: uv run --locked python scripts/analyze-release.py artifacts/opus-subscription-v0.7.1 \\
           [--compare artifacts/opus-subscription-v0.7.0/full] [--outlier 1.10] [--json out.json] > review.md

Units are (track entry without its target, task); for example ("gallery-crowded-v0", "ui-shadow"). Ratios are
Kitsune/Playwright totals over units both targets solved. With --compare, the same ratios are computed on the units
the two suites share, so a lite run can be compared with the matching units of a full run. Kitsune's holds (calls kept
for the user's approval, and declined writes redone in another tab) are recomputed per entry from session evidence, and
each group's ratio is split by units whose Kitsune run held a call and units whose run did not.

Kitsune with read-only user tabs (kitsune#395) holds nothing; it refuses writes and `select` on the user's tabs with
`user_tab_read_only`, and the agent then opens a copy of the user's tab (a `tabs new` with a starting tab's URL) to read
or write in. Refusals are counted from the agents' tool results, copies from the starting tabs the user opened (session
evidence `seeding`), per entry and per group (#101). A copy is a copy to write when the agent writes in it (`click`,
`type`, ...) before its next `tabs new` or `tabs select`, else a copy to read (#113): since kitsune#450 any tab can be
read, so copies to write are the normal write path and copies to read are reopening. Each group's ratio is also split
by units whose Kitsune run had a refusal or a copy to read and units whose run had neither, and --compare shows how
often runs had refusals, copies to write and copies to read then and now.

A Kitsune-only coexistence arm (coexistence-local-v2's unprotected arm, with user tabs writable, or v1's protect arm)
is compared with default Kitsune on the user-seeded entry, task by task: what protection costs the agent (refusals,
copies, input, calls) against what it buys the user (the view left alone, `v3_user_view`).

Each suite's elicitation policy (how the relay answered Kitsune's approval prompts) is read from its
suite-manifest.json, else from what its pairs recorded (summary, pair manifest, session evidence). Ratios under
different policies, or against a suite that recorded none, are not comparable: --compare still computes them and the
report warns. An earlier suite that recorded none and ran a Kitsune from before its holds (kitsune#364) had no prompt
to answer: the report says "no holds then (Kitsune < #364)" instead of warning.

Cost beyond tokens (#108), per group and target on joint successes: Kitsune's cold-start setup and warm-ready time, CPU
and sampled peak RSS (the pair's owner-filtered `setup` and `ready` phases, as in cost_metrics.pair_lifecycle), task
CPU and time-weighted RSS (resources_task), and input excluding cache reads next to total input. The caveats of
docs/resources.md apply: summed RSS is not unique memory, and concurrent targets share load.

A suite of several attempts (run-full-suite.py --attempts 2 --order abba --sequential, #107): the audit covers every
attempt and the other sections read the first. "Attempts and execution orders" then gives, per group, successes and
ratios in each execution order (ab: Playwright first, ba: Kitsune first) and over all attempts, and a claim only when
ab and ba agree (ratios on the same side of 1, Kitsune's successes minus Playwright's on the same side of 0), plus each
unit's spread between attempts: whether its success changed and its Kitsune/Playwright input ratio in each attempt where
both targets succeeded.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import re
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.cost_metrics import (load_pair_resource_phases, normalized_usage, resource_cost,  # noqa: E402
                                            total)
from kitsune_benchmark.holds import DECISIONS, DETAILS, aggregate_holds, hold_metrics  # noqa: E402
from kitsune_benchmark.holds import NAVIGATIONS as BROWSER_NAVIGATIONS  # noqa: E402

TARGETS = ("playwright", "kitsune")
ACTIONS = ("click", "type", "fill_form", "select_option", "press_key", "hover", "drag")
OBSERVATIONS = ("snapshot", "find", "wait_for", "take_screenshot")
# kitsune#364, Kitsune's first hold, is 561719a: `git describe --tags` v0.7.1-10-g561719a on Kitsune main.
HOLDS_SINCE = ((0, 7, 1), 10)
NAVIGATIONS = tuple(name.replace("browser_", "") for name in BROWSER_NAVIGATIONS)
WRITES = ("click", "type", "fill_form", "select_option", "press_key", "drag") + NAVIGATIONS
# Calls that make a copy of a user tab a copy to write (#113).
COPY_WRITES = ("click", "type", "fill_form", "select_option", "press_key", "drag", "drop", "file_upload")
# Session evidence `seeding` of runs whose starting tabs the user opened: personal (#70) and coexistence.
USER_SEEDINGS = ("user_channel", "user_bidi")
# Kitsune-only coexistence arms, compared with default Kitsune on the user-seeded entry: coexistence-local-v2's
# unprotected arm (user tabs writable) and coexistence-local-v1's protect arm.
KITSUNE_ARMS = ("coexistence-unprotected", "coexistence-protect")
MIB = 1024 * 1024
# Kitsune/Playwright ratios compared across execution orders (#107).
ORDER_METRICS = ("input", "output", "mcp_calls", "elapsed")
SIGNAL_COUNTS = ("runs", "runs_second_call_tabs_select", "runs_own_tab_before_first_write",
                 "snapshots_after_navigation_same_request", "snapshots_after_navigation_next_request",
                 "snapshot_after_navigation_chars", "unchanged_since", "wait_for_text", "wait_for_text_under_50ms",
                 "wait_for_with_delta", "wait_for_without_delta")


def group_of(entry: str) -> str | None:
    """The ratio group of a suite entry; None for Kitsune-only arms."""
    if entry.startswith(KITSUNE_ARMS):
        return None
    for prefix in ("personal", "gallery-crowded", "gallery-isolated", "coexistence-user-seeded", "coexistence-typing",
                   "external", "miniwob"):
        if entry.startswith(prefix):
            return prefix
    return entry


def suite_attempts(suite_dir: str | Path) -> dict:
    """{attempt: execution orders} from suite-log.jsonl. Entries before #16 have no attempt and are attempt 1; an
    entry's order is ab (Playwright first), ba (Kitsune first) or None (targets in parallel)."""
    attempts: dict = {}
    for line in (Path(suite_dir) / "suite-log.jsonl").read_text().splitlines():
        entry = json.loads(line)
        orders = attempts.setdefault(entry.get("attempt") or 1, [])
        if entry.get("order") not in orders:
            orders.append(entry.get("order"))
    return dict(sorted(attempts.items()))


def load(suite_dir: str | Path, attempt: int | None = None) -> dict:
    """{(entry, task): {target: run}} from suite-log.jsonl and the per-track suite summaries, over one attempt when
    given. Each run records its entry's attempt and execution order."""
    units: dict = collections.defaultdict(dict)
    for line in (Path(suite_dir) / "suite-log.jsonl").read_text().splitlines():
        entry = json.loads(line)
        path = entry.get("suite_summary_path")
        if not path or (attempt is not None and (entry.get("attempt") or 1) != attempt):
            continue
        summary = json.loads(Path(path).read_text())
        for pair in summary.get("pairs", []):
            task = (pair.get("personal_task") or pair.get("gallery_task") or pair.get("coexistence_task")
                    or pair.get("external_task") or "?")
            for target, run in pair["results"].items():
                units[(entry["name"], task)][target] = {**run, "pair_dir": pair.get("pair_dir"),
                                                        "pair_lifecycle": pair_lifecycle(pair, target),
                                                        "attempt": entry.get("attempt") or 1,
                                                        "order": entry.get("order")}
    return units


def pair_lifecycle(pair: dict, target: str) -> dict:
    """A target's share of its pair's lifecycle, as in cost_metrics.pair_lifecycle: Kitsune's cold-start setup wall time
    (`timing.kitsune_cold_start_setup_sec`) and the owner-filtered `setup` and `ready` phase resources. Old pairs
    without inline phases are read from their resource-summary.json; absent files and fields stay None."""
    try:
        phases = (load_pair_resource_phases(pair).get("resource_phases") or {}).get(target) or {}
    except (OSError, ValueError):
        phases = {}
    cold_start = (pair.get("timing") or {}).get("kitsune_cold_start_setup_sec") if target == "kitsune" else None
    return {"cold_start_setup_sec": cold_start, "setup": phases.get("setup"), "ready": phases.get("ready")}


def pair_policy(pair: dict) -> str | None:
    """A pair's elicitation policy: its summary's, else its manifest experiment's, else a run's session evidence."""
    if pair.get("elicitation") or not pair.get("pair_dir"):
        return pair.get("elicitation")
    folder = Path(pair["pair_dir"])
    try:
        policy = json.loads((folder / "pair-manifest.json").read_text()).get("experiment", {}).get("elicitation")
    except (OSError, ValueError, AttributeError):
        policy = None
    for evidence in [] if policy else sorted(folder.glob("*-session-evidence.json")):
        try:
            policy = json.loads(evidence.read_text()).get("elicitation_policy")
        except (OSError, ValueError, AttributeError):
            continue
        if policy:
            break
    return policy


def elicitation_policy(suite_dir: str | Path) -> tuple[str | None, str | None]:
    """(policy, source). The suite manifest's policy; for suites before #59, the policy its pairs recorded (#55's
    relay writes elicitation_policy into session evidence), "mixed" if they differ; else (None, None)."""
    try:
        manifest = json.loads((Path(suite_dir) / "suite-manifest.json").read_text())
    except (OSError, ValueError):
        manifest = None
    if isinstance(manifest, dict) and manifest.get("elicitation"):
        return manifest["elicitation"], "suite-manifest"
    policies = set()
    try:
        lines = (Path(suite_dir) / "suite-log.jsonl").read_text().splitlines()
    except OSError:
        lines = []
    for line in lines:
        path = json.loads(line).get("suite_summary_path")
        try:
            summary = json.loads(Path(path).read_text()) if path else {}
        except (OSError, ValueError):
            continue
        policies |= {pair_policy(pair) for pair in summary.get("pairs", [])} - {None}
    if not policies:
        return None, None
    return (policies.pop() if len(policies) == 1 else "mixed"), "pair records"


def before_holds(suite_dir: str | Path) -> bool:
    """Whether the suite's Kitsune predates kitsune#364, from the clean `git describe` in its suite-manifest.json;
    False when the manifest, the describe or a clean checkout is missing."""
    try:
        manifest = json.loads((Path(suite_dir) / "suite-manifest.json").read_text())
    except (OSError, ValueError):
        return False
    kitsune = manifest.get("kitsune") if isinstance(manifest, dict) else None
    describe = kitsune.get("describe") if isinstance(kitsune, dict) else None
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)(?:-(\d+)-g[0-9a-f]+)?", describe or "")
    if not match:
        return False
    major, minor, patch, ahead = match.groups()
    return ((int(major), int(minor), int(patch)), int(ahead or 0)) < HOLDS_SINCE


def policy_warning(now: str | None, then: str | None, no_holds_then: bool = False) -> str | None:
    if now is not None and then is None and no_holds_then:
        return None
    if now is None or then is None:
        return (f"elicitation policy {now or 'none recorded'} now, {then or 'none recorded'} then: a suite without a "
                "recorded policy may predate the relay's answers (#55) or Kitsune's holds (kitsune#364), so its "
                "ratios are not comparable")
    if now != then or now == "mixed":
        return f"elicitation policy {now} now, {then} then: ratios under different policies are not comparable"
    return None


def policy_label(policy: str | None, source: str | None) -> str:
    return "none recorded" if policy is None else policy if source == "suite-manifest" else f"{policy} (from {source})"


def tool_calls(run: dict) -> list[tuple[str, dict, str, bool, str | None]]:
    """(tool, arguments, result text, is_error, request) in order, from the run's Claude Code stream. The request is
    the model request that sent the call: its assistant message id, as in analyze-model-rounds.py, or the event's line
    for a message without an id."""
    events = Path(run.get("run_dir") or "") / "events.jsonl"
    if not events.is_file():
        return []
    pending, out = {}, []
    for number, line in enumerate(events.read_text(errors="ignore").splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") or {}
        content = message.get("content")
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_use":
                pending[block["id"]] = (block["name"].split("__")[-1].replace("browser_", ""), block.get("input") or {},
                                        message.get("id") or f"line {number}")
            elif block.get("type") == "tool_result":
                raw = block.get("content")
                text = raw if isinstance(raw, str) else " ".join(i.get("text", "") for i in raw or [] if isinstance(i, dict))
                name, args, request = pending.pop(block.get("tool_use_id"), ("?", {}, None))
                out.append((name, args, text, bool(block.get("is_error")), request))
    return out


def same_request(before: tuple, call: tuple) -> bool:
    """Whether two calls went out in the same model request, so the second cannot have seen the first's result."""
    return before[4] is not None and before[4] == call[4]


def result_fields(text: str) -> dict:
    """A tool result's JSON fields; {} for text that is not a JSON object, such as Playwright MCP's markdown."""
    try:
        value = json.loads(text)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def tabs_action(call: tuple) -> str | None:
    return call[1].get("action") if call[0] == "tabs" else None


def navigating(call: tuple) -> bool:
    """Whether a call loads a page: a navigation, a `tabs new` with a URL, or a call whose Kitsune result has
    `navigated` (a click that navigated; Playwright's results do not say)."""
    return (call[0] in NAVIGATIONS or (tabs_action(call) == "new" and bool(call[1].get("url")))
            or "navigated" in result_fields(call[2]))


def evaluation(run: dict) -> dict:
    return run.get("benchmark_evaluation") or {}


def solved(run: dict | None) -> bool:
    """Graded success; for ungraded tasks (live sites) a completed, scorable run."""
    if not run:
        return False
    ev = evaluation(run)
    if ev.get("graded") is False:
        return ev.get("scorable") is True
    return ev.get("task_success") is True


def input_tokens(run: dict) -> int:
    return (run.get("usage") or {}).get("input_tokens") or 0


def input_excl_cache_read_tokens(run: dict) -> int | None:
    """Input excluding cache reads: total input minus cache reads, so Claude's cache writes count. Codex's
    `uncached_input_tokens` (total minus cached); for Claude, `uncached_input_tokens` (input after the last cache
    breakpoint, a few tokens) plus `cache_creation_input_tokens` (cache writes). Not `uncached_input_tokens` itself
    (personal_analysis's `noncached_input_tokens`), which leaves out Claude's cache writes. None when the run reported
    neither."""
    usage = normalized_usage(run)
    if usage.get("uncached_input_tokens") is None:
        return None
    return usage["uncached_input_tokens"] + (usage.get("cache_creation_input_tokens") or 0)


def audit(units: dict) -> dict:
    counts = collections.Counter()
    models = collections.Counter()
    for key, runs in units.items():
        entry = key[0]
        for run in runs.values():
            counts["runs"] += 1
            counts["status:" + str(run.get("execution_status"))] += 1
            counts["scorable"] += evaluation(run).get("scorable") is True
            counts["violations"] += bool(run.get("violations"))
            counts["harness_errors"] += bool(run.get("harness_error"))
            counts["missing_allowlisted_tools"] += bool((run.get("tool_surface") or {}).get("missing"))
            counts["no_allowlisted_tools"] += (run.get("tool_surface") or {}).get("no_allowlisted_tools") is True
            models[str(run.get("model"))] += 1
            if entry.startswith("personal"):
                counts["personal_runs"] += 1
                counts["personal_viewport_asserted"] += (run.get("viewport") or {}).get(
                    "content_viewport_equality_asserted") is True
    return {**counts, "models": dict(models)}


def outcomes(units: dict) -> dict:
    out = {}
    for (entry, task), runs in units.items():
        group = group_of(entry) or entry
        row = out.setdefault(group, {"units": 0, **{t: None for t in TARGETS}, "misses": {t: [] for t in TARGETS}})
        row["units"] += 1
        for target in TARGETS:
            if target not in runs:
                continue
            row[target] = row[target] or 0
            if solved(runs[target]):
                row[target] += 1
            else:
                row["misses"][target].append(f"{task} ({entry}): {evaluation(runs[target]).get('outcome') or 'failed'}")
    return out


def ratios(units: dict, keys=None) -> dict:
    groups = collections.defaultdict(list)
    for key, runs in units.items():
        group = group_of(key[0])
        if group and (keys is None or key in keys) and all(solved(runs.get(t)) for t in TARGETS):
            groups[group].append(runs)
    out = {}
    for group, joint in groups.items():
        def total(target, field):
            return sum(field(runs[target]) for runs in joint)
        def ratio(field):
            pw = total("playwright", field)
            return round(total("kitsune", field) / pw, 3) if pw else None
        paired = [input_tokens(r["kitsune"]) / input_tokens(r["playwright"]) for r in joint if input_tokens(r["playwright"])]
        out[group] = {"joint": len(joint), "input": ratio(input_tokens),
                      "output": ratio(lambda r: (r.get("usage") or {}).get("output_tokens") or 0),
                      "mcp_calls": ratio(lambda r: r.get("mcp_calls") or 0),
                      "elapsed": ratio(lambda r: r.get("elapsed_sec") or 0),
                      "paired_input_median": round(statistics.median(paired), 3) if paired else None,
                      "units_less_kitsune_input": sum(p < 1 for p in paired)}
    return out


def costs(units: dict) -> dict:
    """Per group and target, on joint successes: Kitsune's cold-start setup time and its pair's `setup` and `ready`
    phase resources (pair_lifecycle; Playwright starts its browser inside the task window and has neither), the task
    window's resources (resources_task), total input and input excluding cache reads, with coverage, and the
    execution orders the runs came from (ab, ba, or parallel for targets run concurrently)."""
    groups = collections.defaultdict(list)
    for key, runs in units.items():
        group = group_of(key[0])
        if group and all(solved(runs.get(t)) for t in TARGETS):
            groups[group].append(runs)
    out = {}
    for group, joint in groups.items():
        out[group] = {}
        for target in TARGETS:
            runs = [unit[target] for unit in joint]
            lifecycle = [run.get("pair_lifecycle") or {} for run in runs]
            out[group][target] = {
                "joint": len(runs),
                "cold_start_setup_sec": total([phases.get("cold_start_setup_sec") for phases in lifecycle]),
                "setup": resource_cost([phases.get("setup") for phases in lifecycle]),
                "ready": resource_cost([phases.get("ready") for phases in lifecycle]),
                "resources_task": resource_cost([(run.get("resources") or {}).get("task") for run in runs]),
                "input_tokens": total([(run.get("usage") or {}).get("input_tokens") for run in runs]),
                "input_excl_cache_read_tokens": total([input_excl_cache_read_tokens(run) for run in runs]),
                "orders": sorted({run.get("order") or "parallel" for run in runs})}
    return out


def outliers(units: dict, threshold: float) -> list[dict]:
    rows = []
    for (entry, task), runs in units.items():
        if not group_of(entry) or not all(t in runs for t in TARGETS) or not input_tokens(runs["playwright"]):
            continue
        ratio = input_tokens(runs["kitsune"]) / input_tokens(runs["playwright"])
        if ratio > threshold:
            rows.append({"entry": entry, "task": task, "input_ratio": round(ratio, 2),
                         "input": {t: input_tokens(runs[t]) for t in TARGETS},
                         "mcp_calls": {t: runs[t].get("mcp_calls") for t in TARGETS},
                         "kitsune_calls": [n for n, *_ in tool_calls(runs["kitsune"])]})
    return sorted(rows, key=lambda r: -r["input_ratio"])


def behaviour(units: dict) -> dict:
    out = {t: collections.Counter() for t in TARGETS}
    errors = {t: collections.Counter() for t in TARGETS}
    for (entry, _), runs in units.items():
        if not group_of(entry):
            continue
        for target in TARGETS:
            if target not in runs:
                continue
            calls = tool_calls(runs[target])
            m = out[target]
            m["runs"] += 1
            if calls and calls[0][0] == "tabs" and calls[0][1].get("action") == "list":
                m["runs_starting_with_tabs_list"] += 1
            for i, (name, args, text, is_error, _) in enumerate(calls):
                m["calls"] += 1
                if is_error:
                    errors[target][f"{name}: {text[:90]}"] += 1
                if name == "wait_for" and set(args) == {"time"}:
                    m["blind_waits"] += 1
                if name == "find":
                    m["find_calls"] += 1
                    m["find_chars"] += len(text)
                if name == "snapshot" and not args.get("target"):
                    m["full_snapshots"] += 1
                    m["full_snapshot_chars"] += len(text)
                    m["truncated_full_snapshots"] += '"truncated":true' in text or '"truncated": true' in text
                if name in ACTIONS:
                    m["actions"] += 1
                    m["action_chars"] += len(text)
                    following = calls[i + 1] if i + 1 < len(calls) else None
                    observed = following is not None and following[0] in OBSERVATIONS
                    together = observed and same_request(calls[i], following)
                    m["actions_followed_by_observation_same_request"] += together
                    m["actions_followed_by_observation_next_request"] += observed and not together
    summary = {}
    for target, m in out.items():
        summary[target] = {
            **dict(m),
            **{f"observation_after_action_{when}_rate": round(m[f"actions_followed_by_observation_{when}"] / m["actions"], 3)
               if m["actions"] else None for when in ("same_request", "next_request")},
            "mean_action_response_chars": round(m["action_chars"] / m["actions"]) if m["actions"] else None,
            "mean_find_chars": round(m["find_chars"] / m["find_calls"]) if m["find_calls"] else None,
            "mean_full_snapshot_chars": round(m["full_snapshot_chars"] / m["full_snapshots"]) if m["full_snapshots"] else None,
            "tool_errors": dict(errors[target].most_common(10)),
        }
    return summary


def signals(units: dict) -> dict:
    """Per group and target: runs whose 2nd call is `tabs select` (kitsune#399); runs that open a tab before their first
    write (kitsune#393); bare snapshots right after a navigating call (navigating), sent in the same model request as
    that call or in the next one (#124), and their characters and `unchanged_since` answers (kitsune#400,
    kitsune#401); `wait_for {text}` answered in under 50 ms and `wait_for` results with and without a
    `snapshot_delta` (kitsune#402, kitsune#403); the median first request, the fixed prefix (kitsune#405). Navigations
    seen in results, `unchanged_since`, `elapsed` and `snapshot_delta` are Kitsune result fields."""
    counts = collections.defaultdict(lambda: {t: collections.Counter() for t in TARGETS})
    first_requests = collections.defaultdict(lambda: {t: [] for t in TARGETS})
    for (entry, _), runs in units.items():
        group = group_of(entry)
        if not group:
            continue
        for target in TARGETS:
            if target not in runs:
                continue
            calls = tool_calls(runs[target])
            m = counts[group][target]
            m["runs"] += 1
            m["runs_second_call_tabs_select"] += len(calls) > 1 and tabs_action(calls[1]) == "select"
            first_write = next((i for i, call in enumerate(calls) if call[0] in WRITES), None)
            m["runs_own_tab_before_first_write"] += first_write is not None and any(
                tabs_action(call) == "new" for call in calls[:first_write])
            for before, call in zip(calls, calls[1:]):
                name, args, text = call[:3]
                if name == "snapshot" and not args and navigating(before) and not before[3]:
                    m["snapshots_after_navigation_" + ("same_request" if same_request(before, call)
                                                       else "next_request")] += 1
                    m["snapshot_after_navigation_chars"] += len(text)
                    m["unchanged_since"] += "unchanged_since" in result_fields(text)
            for name, args, text, *_ in calls:
                if name != "wait_for":
                    continue
                fields = result_fields(text)
                m["wait_for_with_delta" if fields.get("snapshot_delta") else "wait_for_without_delta"] += 1
                if "text" in args:
                    m["wait_for_text"] += 1
                    elapsed = fields.get("elapsed")
                    m["wait_for_text_under_50ms"] += isinstance(elapsed, (int, float)) and elapsed < 50
            first = (runs[target].get("token_attribution") or {}).get("first_request_input_tokens")
            if first:
                first_requests[group][target].append(first)
    return {group: {target: {**{key: m[key] for key in SIGNAL_COUNTS}, "median_first_request_input_tokens":
                             statistics.median(first_requests[group][target]) if first_requests[group][target] else None}
                    for target, m in by_target.items()}
            for group, by_target in counts.items()}


def session_evidence(run: dict) -> dict | None:
    """The Kitsune session evidence of the run's pair; None when it is missing or truncated."""
    pair_dir = run.get("pair_dir")
    try:
        evidence = json.loads((Path(pair_dir) / "kitsune-session-evidence.json").read_text()) if pair_dir else None
    except (OSError, ValueError):
        evidence = None
    return evidence if isinstance(evidence, dict) else None


def run_holds(run: dict) -> dict | None:
    """A Kitsune run's holds from its pair's session evidence (holds.py); None when the evidence is missing or truncated."""
    evidence = session_evidence(run)
    return hold_metrics(evidence) if evidence is not None else None


def writes_in_copy(after: list[tuple]) -> bool:
    """Whether the calls after a copy write (COPY_WRITES) before the agent leaves the copy (its next `tabs new` or
    `tabs select`) or the run ends."""
    for call in after:
        if tabs_action(call) in ("new", "select"):
            return False
        if call[0] in COPY_WRITES:
            return True
    return False


def run_read_only(run: dict) -> dict:
    """A Kitsune run's `user_tab_read_only` refusals, by call (`tabs select`, `type`, ...), and its copies of the user's
    starting tabs (`tabs new` calls whose URL is a starting tab's), split into copies to write and copies to read
    (writes_in_copy). Copies are None when the session evidence does not say the user opened the starting tabs (seeding
    user_channel or user_bidi)."""
    calls = tool_calls(run)
    refused = collections.Counter(" ".join(filter(None, (call[0], tabs_action(call))))
                                  for call in calls if result_fields(call[2]).get("code") == "user_tab_read_only")
    evidence = session_evidence(run) or {}
    copies_to_write = copies_to_read = None
    if evidence.get("seeding") in USER_SEEDINGS:
        starting = {tab.get("url") for tab in evidence.get("initial_tabs") or []}
        copies = [i for i, call in enumerate(calls) if tabs_action(call) == "new" and call[1].get("url") in starting]
        copies_to_write = sum(writes_in_copy(calls[i + 1:]) for i in copies)
        copies_to_read = len(copies) - copies_to_write
    return {"refusals": sum(refused.values()), "refused_calls": dict(refused), "copies_to_write": copies_to_write,
            "copies_to_read": copies_to_read}


def read_only_totals(rows: list[dict]) -> dict:
    refused = collections.Counter()
    for row in rows:
        refused.update(row["refused_calls"])
    seeded = [row for row in rows if row["copies_to_write"] is not None]
    return {"runs": len(rows), "runs_with_refusal": sum(bool(row["refusals"]) for row in rows),
            "refusals": sum(row["refusals"] for row in rows), "refused_calls": dict(refused.most_common()),
            "user_seeded_runs": len(seeded),
            "runs_with_copy_to_write": sum(bool(row["copies_to_write"]) for row in seeded),
            "copies_to_write": sum(row["copies_to_write"] for row in seeded),
            "runs_with_copy_to_read": sum(bool(row["copies_to_read"]) for row in seeded),
            "copies_to_read": sum(row["copies_to_read"] for row in seeded)}


def read_only(units: dict, by=lambda entry: entry, keys=None) -> dict:
    """Kitsune refusals and copies to write and to read per entry (or per `by(entry)`, such as group_of), over `keys` when given."""
    rows = collections.defaultdict(list)
    for key, runs in units.items():
        name = by(key[0])
        if name and "kitsune" in runs and (keys is None or key in keys):
            rows[name].append(run_read_only(runs["kitsune"]))
    return {name: read_only_totals(values) for name, values in rows.items()}


def read_only_split(units: dict) -> dict:
    """Per group, Kitsune/Playwright input on joint successes whose Kitsune run had a refusal or a copy to read and on
    those whose run had neither; groups with neither in any joint success are left out."""
    split = collections.defaultdict(lambda: {"with": [], "without": []})
    for (entry, _), runs in units.items():
        group = group_of(entry)
        if not group or not all(solved(runs.get(t)) for t in TARGETS):
            continue
        row = run_read_only(runs["kitsune"])
        split[group]["with" if row["refusals"] or row["copies_to_read"] else "without"].append(runs)

    def side(joint):
        pw = sum(input_tokens(runs["playwright"]) for runs in joint)
        return {"units": len(joint),
                "input": round(sum(input_tokens(runs["kitsune"]) for runs in joint) / pw, 3) if pw else None}
    return {group: {"with_refusal_or_copy_to_read": side(row["with"]), "without": side(row["without"])}
            for group, row in split.items() if row["with"]}


def holds(units: dict) -> dict:
    """Kitsune holds per entry, from each run's session evidence (holds.py); entries without Kitsune runs are left out."""
    metrics = collections.defaultdict(list)
    for (entry, _), runs in units.items():
        if "kitsune" in runs:
            metrics[entry].append(run_holds(runs["kitsune"]))
    return {entry: aggregate_holds(values) for entry, values in metrics.items()}


def hold_split(units: dict) -> dict:
    """Per group, Kitsune/Playwright input on joint successes whose Kitsune run held a call and on those whose run did
    not; joint successes without a hold record are counted apart, and groups with no record are left out."""
    split = collections.defaultdict(lambda: {"with_hold": [], "without_hold": [], "no_record": 0})
    for (entry, _), runs in units.items():
        group = group_of(entry)
        if not group or not all(solved(runs.get(t)) for t in TARGETS):
            continue
        record = run_holds(runs["kitsune"])
        if record is None:
            split[group]["no_record"] += 1
        else:
            split[group]["with_hold" if record["holds"] else "without_hold"].append(runs)

    def side(joint):
        pw = sum(input_tokens(runs["playwright"]) for runs in joint)
        return {"units": len(joint),
                "input": round(sum(input_tokens(runs["kitsune"]) for runs in joint) / pw, 3) if pw else None}
    return {group: {"with_hold": side(row["with_hold"]), "without_hold": side(row["without_hold"]),
                    "no_record": row["no_record"]}
            for group, row in split.items() if row["with_hold"] or row["without_hold"]}


def moved_view(run: dict) -> bool:
    return ((evaluation(run).get("user_view") or {}).get("view_left_initial_after_calls") or 0) > 0


def kitsune_arms(units: dict) -> dict:
    """Each Kitsune-only coexistence arm against default Kitsune on the user-seeded entry, task by task: successes,
    `v3_user_view`, runs that moved the user's view, runs with a read-only refusal, a copy of a user tab to write or a
    copy to read, and the arm's input and agent calls over default Kitsune's on units both solved."""
    default = {task: runs["kitsune"] for (entry, task), runs in units.items()
               if entry == "coexistence-user-seeded" and "kitsune" in runs}
    out = {}
    for arm in KITSUNE_ARMS:
        pairs = [(default[task], runs["kitsune"]) for (entry, task), runs in units.items()
                 if entry == arm and "kitsune" in runs and task in default]
        if not pairs:
            continue

        def side(i):
            runs = [pair[i] for pair in pairs]
            rows = [run_read_only(run) for run in runs]
            return {"successes": sum(solved(run) for run in runs),
                    "v3_user_view": sum(((evaluation(run).get("contracts") or {}).get("v3_user_view") or {})
                                        .get("task_success") is True for run in runs),
                    "runs_moved_view": sum(moved_view(run) for run in runs),
                    "runs_with_refusal": sum(bool(row["refusals"]) for row in rows),
                    "runs_with_copy_to_write": sum(bool(row["copies_to_write"]) for row in rows),
                    "runs_with_copy_to_read": sum(bool(row["copies_to_read"]) for row in rows)}
        joint = [pair for pair in pairs if solved(pair[0]) and solved(pair[1])]

        def ratio(field):
            base = sum(field(pair[0]) for pair in joint)
            return round(sum(field(pair[1]) for pair in joint) / base, 3) if base else None
        out[arm] = {"units": len(pairs), "default": side(0), "arm": side(1), "joint": len(joint),
                    "input": ratio(input_tokens), "mcp_calls": ratio(lambda run: run.get("mcp_calls") or 0)}
    return out


def successes(units: dict) -> dict:
    """Per group, the units and each target's successes; a unit missing a target counts as that target's miss."""
    out = {}
    for key, runs in units.items():
        group = group_of(key[0])
        if not group:
            continue
        row = out.setdefault(group, {"units": 0, **{t: 0 for t in TARGETS}})
        row["units"] += 1
        for target in TARGETS:
            row[target] += solved(runs.get(target))
    return out


def agreement(ab: float | None, ba: float | None, pivot: float, below: str, above: str) -> str | None:
    """The side of `pivot` both orders' values are on; None when they disagree, one sits on it or one is missing."""
    if ab is None or ba is None:
        return None
    if ab < pivot and ba < pivot:
        return below
    if ab > pivot and ba > pivot:
        return above
    return None


def orders(pooled: dict) -> dict:
    """Per group, successes and Kitsune/Playwright ratios on joint successes in each execution order (ab: Playwright
    first, ba: Kitsune first, parallel: targets at once) and over all attempts, and the claims both orders agree on:
    the ab and ba ratios on the same side of 1, or Kitsune's successes minus Playwright's on the same side of 0. A claim
    is None when the orders disagree or one of them did not run."""
    by_order: dict = collections.defaultdict(dict)
    for key, runs in pooled.items():
        by_order[next(iter(runs.values()))["order"] or "parallel"][key] = runs
    tables = {order: (successes(units), ratios(units)) for order, units in sorted(by_order.items())}
    tables["all attempts"] = (successes(pooled), ratios(pooled))
    out = {}
    for group in tables["all attempts"][0]:
        rows = {order: {**counts[group], "ratios": joint.get(group)}
                for order, (counts, joint) in tables.items() if group in counts}
        ab, ba = rows.get("ab"), rows.get("ba")

        def difference(row):
            return row["kitsune"] - row["playwright"] if row else None

        def ratio(row, metric):
            return (row["ratios"] or {}).get(metric) if row else None
        claims = {"successes": agreement(difference(ab), difference(ba), 0, "kitsune fewer", "kitsune more"),
                  **{metric: agreement(ratio(ab, metric), ratio(ba, metric), 1, "kitsune lower", "kitsune higher")
                     for metric in ORDER_METRICS}}
        out[group] = {"by_order": rows, "claims": claims}
    return out


def spread(pooled: dict) -> dict:
    """Per unit run in more than one attempt: each target's success, the Kitsune/Playwright input ratio in each
    attempt where both targets succeeded (None otherwise), and the ratio's spread (largest minus smallest). Per group:
    those units, the units whose success changed between attempts, by target, and the median and largest spread."""
    by_unit: dict = collections.defaultdict(dict)
    for (entry, task, attempt), runs in pooled.items():
        by_unit[(entry, task)][attempt] = runs
    units, groups = [], {}
    for (entry, task), attempts in by_unit.items():
        group = group_of(entry)
        if not group or len(attempts) < 2:
            continue
        ordered = [attempts[attempt] for attempt in sorted(attempts)]
        input_ratio = [round(input_tokens(runs["kitsune"]) / input_tokens(runs["playwright"]), 3)
                       if all(solved(runs.get(t)) for t in TARGETS) and input_tokens(runs["playwright"]) else None
                       for runs in ordered]
        measured = [value for value in input_ratio if value is not None]
        row = {"entry": entry, "task": task, "attempts": sorted(attempts),
               "orders": [next(iter(runs.values()))["order"] for runs in ordered],
               "success": {t: [solved(runs.get(t)) for runs in ordered] for t in TARGETS},
               "input_ratio": input_ratio,
               "input_ratio_spread": round(max(measured) - min(measured), 3) if len(measured) > 1 else None}
        units.append(row)
        summary = groups.setdefault(group, {"units": 0, "success_changed": {t: 0 for t in TARGETS}, "spreads": []})
        summary["units"] += 1
        for target in TARGETS:
            summary["success_changed"][target] += len(set(row["success"][target])) > 1
        if row["input_ratio_spread"] is not None:
            summary["spreads"].append(row["input_ratio_spread"])
    for summary in groups.values():
        values = summary.pop("spreads")
        summary["median_input_ratio_spread"] = round(statistics.median(values), 3) if values else None
        summary["max_input_ratio_spread"] = max(values) if values else None
    return {"groups": groups, "units": units}


def review(suite_dir, compare=None, threshold=1.10) -> dict:
    attempts = suite_attempts(suite_dir)
    units = load(suite_dir, next(iter(attempts), None))
    policy, source = elicitation_policy(suite_dir)
    report = {"suite": str(suite_dir), "elicitation": policy, "elicitation_source": source, "audit": audit(units),
              "outcomes": outcomes(units), "ratios": ratios(units), "costs": costs(units),
              "outliers": outliers(units, threshold), "behaviour": behaviour(units), "signals": signals(units),
              "holds": holds(units), "hold_split": hold_split(units),
              "read_only": read_only(units), "read_only_split": read_only_split(units),
              "kitsune_arms": kitsune_arms(units)}
    if len(attempts) > 1:
        # Every section but the audit reads the first attempt; this one reads them all.
        pooled = {(*key, attempt): runs for attempt in attempts for key, runs in load(suite_dir, attempt).items()}
        report["audit"] = audit(pooled)
        report["attempts"] = {"orders": attempts, "groups": orders(pooled), "spread": spread(pooled)}
    if compare:
        old = load(compare, next(iter(suite_attempts(compare)), None))
        shared = set(units) & set(old)
        then, then_source = elicitation_policy(compare)
        no_holds = then is None and before_holds(compare)
        report["compare"] = {"suite": str(compare), "elicitation": then, "elicitation_source": then_source,
                             "no_holds": no_holds, "warning": policy_warning(report["elicitation"], then, no_holds),
                             "shared_units": len(shared),
                             "ratios_now": ratios(units, shared), "ratios_then": ratios(old, shared),
                             "read_only_now": read_only(units, group_of, shared),
                             "read_only_then": read_only(old, group_of, shared)}
    return report


def mean_cell(value: dict, digits: int = 1) -> str:
    """A total's mean per reporting run, with its coverage when runs are missing; — when no run reported."""
    if value["total"] is None:
        return "—"
    reported = value["reported_runs"]
    cell = f"{value['total'] / reported:,.{digits}f}"
    return cell if not value["missing_runs"] else f"{cell} ({reported}/{reported + value['missing_runs']})"


def rss_cell(value: float | None, runs: int, attempted: int) -> str:
    if value is None:
        return "—"
    return f"{value / MIB:,.0f}" + (f" ({runs}/{attempted})" if runs < attempted else "")


def cost_lines(costs: dict) -> list[str]:
    lines = ["", "## Cost beyond tokens on joint successes", "",
             "Means per joint success. Cold-start setup is Kitsune's launch, bridge and browser readiness wall time; "
             "warm-ready is the pair's `ready` phase, an idle wait of about one second with the browser and bridge "
             "already running. Their CPU and sampled peak RSS are the pair's `setup` and `ready` phases filtered to the "
             "target's processes. Playwright starts its browser inside the task window and has no such phases (—). Task "
             "CPU is user + system CPU per measured task; task RSS is the task windows' mean RSS weighted by their "
             "duration. Input excl. cache reads is total input minus cache reads, so cache writes count: Codex "
             "`uncached_input_tokens`; Claude `uncached_input_tokens` + `cache_creation_input_tokens`. It is not "
             "`uncached_input_tokens`, which for Claude leaves out cache writes. (n/m): only n of m runs reported the "
             "value.", "",
             "| Group | Target | Joint | Cold-start setup s | Warm-ready s | Setup / ready CPU s | "
             "Setup / ready peak RSS MiB | Task CPU s | Task RSS MiB | Input | Input excl. cache reads |",
             "| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |"]
    for group, by_target in costs.items():
        for target, c in by_target.items():
            setup, ready, task = c["setup"], c["ready"], c["resources_task"]
            both = lambda first, second: "—" if first == second == "—" else f"{first} / {second}"
            peak = lambda phase: rss_cell(phase["sampled_peak_rss_bytes"], phase["runs_with_peak_rss"], phase["attempted"])
            lines.append(f"| {group} | {target} | {c['joint']} | {mean_cell(c['cold_start_setup_sec'])} | "
                         f"{mean_cell(ready['duration_sec'])} | "
                         f"{both(mean_cell(setup['observed_cpu_sec']), mean_cell(ready['observed_cpu_sec']))} | "
                         f"{both(peak(setup), peak(ready))} | {mean_cell(task['observed_cpu_sec'])} | "
                         f"{rss_cell(task['time_weighted_mean_rss_bytes'], task['runs_with_mean_rss'], task['attempted'])} | "
                         f"{mean_cell(c['input_tokens'], digits=0)} | "
                         f"{mean_cell(c['input_excl_cache_read_tokens'], digits=0)} |")
    orders = {group: sorted({order for c in by_target.values() for order in c["orders"]})
              for group, by_target in costs.items()}
    concurrent = [group for group, seen in orders.items() if "parallel" in seen]
    ordered = [f"{group} ({' / '.join(o for o in seen if o != 'parallel')})"
               for group, seen in orders.items() if any(o != "parallel" for o in seen)]
    layout = ([f"{', '.join(concurrent)} ran both targets concurrently, so CPU and time are measured under shared "
               "load."] if concurrent else []) + ([
        f"{', '.join(ordered)} ran the targets one after the other in the given order, without shared load, so "
        "their CPU and time are not comparable with concurrent runs'."] if ordered else [])
    return lines + ["", " ".join([
        "Caveats (docs/resources.md): RSS is summed over the target's processes and counts shared memory more than "
        "once; it is not unique memory (PSS, USS or physical footprint). Peaks are sampled peaks, the largest of the "
        "runs'.", *layout, "Kitsune's task window includes its already-running browser and bridge, Playwright's "
        "includes its browser launch: this is not a cold-versus-reused-session comparison. Remote model inference is "
        "not measured."])]


def attempt_lines(attempts: dict) -> list[str]:
    lines = ["", "## Attempts and execution orders", "",
             "Attempts: " + "; ".join(f"{attempt} " + ", ".join(order or "parallel" for order in orders)
                                     for attempt, orders in attempts["orders"].items())
             + ". ab runs Playwright first, ba Kitsune first (coexistence always runs paired). Successes count every "
             "unit of the order; ratios are Kitsune/Playwright on its joint successes. A claim is stated only when ab "
             "and ba agree: both ratios on the same side of 1, or Kitsune's successes minus Playwright's on the same "
             "side of 0 in both; otherwise there is no claim.", "",
             "| Group | Order | Units | Successes PW / K | Joint | Input | Output | MCP calls | Elapsed |",
             "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for group, row in attempts["groups"].items():
        for order, o in row["by_order"].items():
            r = o["ratios"] or {}
            lines.append(f"| {group} | {order} | {o['units']} | {o['playwright']} / {o['kitsune']} | {r.get('joint', 0)} | "
                         + " | ".join(str(r.get(metric)) for metric in ORDER_METRICS) + " |")
    lines += ["", "Claims both orders agree on:", "", "| Group | Successes | Input | Output | MCP calls | Elapsed |",
              "| --- | --- | --- | --- | --- | --- |"]
    for group, row in attempts["groups"].items():
        lines.append(f"| {group} | " + " | ".join(row["claims"][key] or "no claim" for key in ("successes", *ORDER_METRICS))
                     + " |")
    s = attempts["spread"]
    lines += ["", "Per-unit spread between attempts: the Kitsune/Playwright input ratio of each attempt where both "
              "targets succeeded, largest minus smallest; — where one of them failed.", "",
              "| Group | Units in more than one attempt | Success changed PW / K | Median input-ratio spread | Largest |",
              "| --- | ---: | --- | ---: | ---: |"]
    for group, g in s["groups"].items():
        changed = g["success_changed"]
        lines.append(f"| {group} | {g['units']} | {changed['playwright']} / {changed['kitsune']} | "
                     f"{g['median_input_ratio_spread']} | {g['max_input_ratio_spread']} |")
    widest = sorted((u for u in s["units"] if u["input_ratio_spread"] is not None),
                    key=lambda u: -u["input_ratio_spread"])[:10]
    shown = widest + [u for u in s["units"] if u not in widest and any(len(set(v)) > 1 for v in u["success"].values())]
    lines += ["", "The 10 units with the widest spread, and every unit whose success changed between attempts:", "",
              "| Unit | Orders | Input ratio by attempt | Spread | Success PW | Success K |",
              "| --- | --- | --- | ---: | --- | --- |"]
    for u in shown:
        yes = lambda values: " / ".join("yes" if value else "no" for value in values)
        lines.append(f"| {u['task']} ({u['entry']}) | {' / '.join(o or 'parallel' for o in u['orders'])} | "
                     f"{' / '.join('—' if v is None else str(v) for v in u['input_ratio'])} | "
                     f"{'—' if u['input_ratio_spread'] is None else u['input_ratio_spread']} | "
                     f"{yes(u['success']['playwright'])} | {yes(u['success']['kitsune'])} |")
    return lines


def markdown(report: dict, threshold: float) -> str:
    a = report["audit"]
    lines = [f"# Release review: `{report['suite']}`", "",
             "Observations right after an action and bare snapshots right after navigating are split by model request "
             "(assistant message id): one sent in the same request as the call before it had not seen that call's result "
             "and cost no request; one in the next request cost a request. Reviews before #124 counted both together and "
             "did not count `tabs new` with a URL as navigating, so their numbers are not comparable with these.", "",
             "## Audit" + (" (all attempts)" if "attempts" in report else ""), "",
             f"- Elicitation policy: {policy_label(report['elicitation'], report['elicitation_source'])}",
             f"- Runs: {a.get('runs', 0)}; scorable {a.get('scorable', 0)}; "
             + ", ".join(f"{k.split(':', 1)[1]} {v}" for k, v in a.items() if k.startswith("status:")),
             f"- Audit violations {a.get('violations', 0)}, harness errors {a.get('harness_errors', 0)}, runs missing "
             f"allowlisted tools {a.get('missing_allowlisted_tools', 0)} (none published "
             f"{a.get('no_allowlisted_tools', 0)}); models {a['models']}",
             f"- Personal content viewport asserted: {a.get('personal_viewport_asserted', 0)}/{a.get('personal_runs', 0)}",
             *([f"- Attempts: {len(report['attempts']['orders'])}. This audit pools every attempt; the other sections "
                f"read attempt {next(iter(report['attempts']['orders']))} only, except \"Attempts and execution "
                "orders\", which reads them all."] if "attempts" in report else []),
             "", "## Outcomes", "", "| Group | Units | Playwright | Kitsune | Misses |", "| --- | ---: | ---: | ---: | --- |"]
    for group, row in report["outcomes"].items():
        misses = "; ".join(f"{t[0].upper()} {m}" for t in TARGETS for m in row["misses"][t]) or "none"
        cell = lambda t: "—" if row[t] is None else row[t]
        lines.append(f"| {group} | {row['units']} | {cell('playwright')} | {cell('kitsune')} | {misses} |")
    lines += ["", "## Kitsune / Playwright on joint successes", "",
              "| Group | Joint | Input | Paired median | Units with less K input | Output | MCP calls | Elapsed |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for group, r in report["ratios"].items():
        lines.append(f"| {group} | {r['joint']} | {r['input']} | {r['paired_input_median']} | "
                     f"{r['units_less_kitsune_input']}/{r['joint']} | {r['output']} | {r['mcp_calls']} | {r['elapsed']} |")
    lines += cost_lines(report["costs"])
    if "attempts" in report:
        lines += attempt_lines(report["attempts"])
    if "compare" in report:
        c = report["compare"]
        then_label = ("no holds then (Kitsune < #364)" if c["no_holds"]
                      else f"{policy_label(c['elicitation'], c['elicitation_source'])} then")
        lines += ["", f"## Compared with `{c['suite']}` on {c['shared_units']} shared units", "",
                  f"Elicitation policy: {policy_label(report['elicitation'], report['elicitation_source'])} now, "
                  f"{then_label}.", ""]
        if c["warning"]:
            lines += [f"> **Warning:** {c['warning']}.", ""]
        lines += ["| Group | Input then | Input now | Calls then | Calls now |", "| --- | ---: | ---: | ---: | ---: |"]
        for group, now in c["ratios_now"].items():
            then = c["ratios_then"].get(group, {})
            lines.append(f"| {group} | {then.get('input')} | {now['input']} | {then.get('mcp_calls')} | {now['mcp_calls']} |")
        lines += ["", "Kitsune runs on the shared units with a `user_tab_read_only` refusal, and with a copy of a user's "
                  "starting tab to write or to read (of the runs whose starting tabs the user opened):", "",
                  "| Group | Runs with a refusal then | Now | Runs with a copy to write then | Now | "
                  "Runs with a copy to read then | Now |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for group, now in c["read_only_now"].items():
            then = c["read_only_then"].get(group)
            refusal = lambda r: f"{r['runs_with_refusal']}/{r['runs']}" if r else "—"
            copy = lambda r, kind: (f"{r['runs_with_copy_' + kind]}/{r['user_seeded_runs']}"
                                    if r and r["user_seeded_runs"] else "—")
            lines.append(f"| {group} | {refusal(then)} | {refusal(now)} | {copy(then, 'to_write')} | "
                         f"{copy(now, 'to_write')} | {copy(then, 'to_read')} | {copy(now, 'to_read')} |")
    lines += ["", f"## Units where Kitsune input exceeds {threshold}× Playwright", "",
              "| Unit | Ratio | Input PW / K | Calls PW / K | Kitsune calls |", "| --- | ---: | --- | --- | --- |"]
    for o in report["outliers"]:
        lines.append(f"| {o['task']} ({o['entry']}) | {o['input_ratio']} | {o['input']['playwright']} / {o['input']['kitsune']} | "
                     f"{o['mcp_calls']['playwright']} / {o['mcp_calls']['kitsune']} | {' '.join(o['kitsune_calls'])} |")
    lines += ["", "## Behaviour", "", "| Signal | Playwright | Kitsune |", "| --- | ---: | ---: |"]
    b = report["behaviour"]
    for key, label in (("calls", "Tool calls"),
                       ("observation_after_action_same_request_rate", "Observation right after an action, same request"),
                       ("observation_after_action_next_request_rate", "Observation right after an action, next request"),
                       ("mean_action_response_chars", "Mean action response (chars)"), ("blind_waits", "`wait_for {time}` only"),
                       ("runs_starting_with_tabs_list", "Runs starting with `tabs list`"),
                       ("mean_find_chars", "Mean `find` result (chars)"), ("mean_full_snapshot_chars", "Mean full snapshot (chars)"),
                       ("truncated_full_snapshots", "Truncated full snapshots")):
        lines.append(f"| {label} | {b['playwright'].get(key)} | {b['kitsune'].get(key)} |")
    lines += ["", "Tool errors (Kitsune): " + (", ".join(f"{v}× {k}" for k, v in b["kitsune"]["tool_errors"].items()) or "none")]
    lines += ["", "## Tabs, snapshots after navigation, waits and first request by group", "",
              "| Group | Runs PW / K | 2nd call `tabs select` PW / K | Own tab before first write PW / K | "
              "Median first request input PW / K | Bare snapshots right after navigating, same request PW / K | "
              "Next request PW / K | K chars of those snapshots, same + next request | "
              "K `unchanged_since`, same + next request | K `wait_for {text}` under 50 ms / all | K `wait_for` with / without delta |",
              "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- |"]
    for group, s in report["signals"].items():
        pw, k = s["playwright"], s["kitsune"]
        both = lambda key: f"{pw[key]} / {k[key]}"
        lines.append(f"| {group} | {both('runs')} | {both('runs_second_call_tabs_select')} | "
                     f"{both('runs_own_tab_before_first_write')} | {both('median_first_request_input_tokens')} | "
                     f"{both('snapshots_after_navigation_same_request')} | "
                     f"{both('snapshots_after_navigation_next_request')} | "
                     f"{k['snapshot_after_navigation_chars']} | {k['unchanged_since']} | "
                     f"{k['wait_for_text_under_50ms']} / {k['wait_for_text']} | "
                     f"{k['wait_for_with_delta']} / {k['wait_for_without_delta']} |")
    lines += ["", "## Kitsune holds", "",
              "| Entry | Runs | Runs with a hold | Holds | " + " / ".join(DETAILS) + " | " + " / ".join(DECISIONS)
              + " | Runs with a declined hold | Runs that redid a declined write |",
              "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |"]
    for entry, h in report["holds"].items():
        if not h["runs"]:
            continue
        by = h["holds_by_detail"]
        lines.append(f"| {entry} | {h['runs']} | {h['runs_with_hold']} | {h['holds']} | "
                     + " / ".join(str(sum(by[d].values())) for d in DETAILS) + " | "
                     + " / ".join(str(sum(by[d][c] for d in DETAILS)) for c in DECISIONS)
                     + f" | {h['runs_with_declined_hold']} | {h['runs_redo_after_decline']} |")
    unrecorded = sum(h["runs"] - h["runs_refusals_recorded"] for h in report["holds"].values())
    if unrecorded:
        lines += ["", f"{unrecorded} Kitsune runs have evidence from before refusals were recorded: their holds are "
                  "counted from approval prompts only; refusals without a prompt (such as Kitsune 0.7's user_tab) are not seen."]
    lines += ["", "## Kitsune / Playwright input on joint successes, by Kitsune hold", "",
              "| Group | Units with a hold | Input | Units without a hold | Input |", "| --- | ---: | ---: | ---: | ---: |"]
    for group, h in report["hold_split"].items():
        lines.append(f"| {group} | {h['with_hold']['units']} | {h['with_hold']['input']} | "
                     f"{h['without_hold']['units']} | {h['without_hold']['input']} |")
    no_record = sum(h["no_record"] for h in report["hold_split"].values())
    if no_record:
        lines += ["", f"{no_record} joint successes have no readable Kitsune session evidence and are left out of the split."]
    lines += ["", "## Kitsune on read-only user tabs", "",
              "Refusals are `user_tab_read_only` results; a copy is a `tabs new` with the URL of a starting tab the user "
              "opened (counted only for runs whose session evidence says so). A copy to write is one the agent writes in "
              "(" + ", ".join(f"`{name}`" for name in COPY_WRITES) + ") before its next `tabs new` or `tabs select`; "
              "any other copy is a copy to read.", "",
              "| Entry | Runs | Runs with a refusal | Refusals | Refused calls | User-seeded runs | "
              "Runs with a copy to write | Copies to write | Runs with a copy to read | Copies to read |",
              "| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for entry, r in report["read_only"].items():
        calls = ", ".join(f"{n}× {call}" for call, n in r["refused_calls"].items()) or "none"
        lines.append(f"| {entry} | {r['runs']} | {r['runs_with_refusal']} | {r['refusals']} | {calls} | "
                     f"{r['user_seeded_runs']} | {r['runs_with_copy_to_write']} | {r['copies_to_write']} | "
                     f"{r['runs_with_copy_to_read']} | {r['copies_to_read']} |")
    lines += ["", "## Kitsune / Playwright input on joint successes, by refusal or copy to read", "",
              "| Group | Units with a refusal or copy to read | Input | Units with neither | Input |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for group, s in report["read_only_split"].items():
        refusal_or_read = s["with_refusal_or_copy_to_read"]
        lines.append(f"| {group} | {refusal_or_read['units']} | {refusal_or_read['input']} | "
                     f"{s['without']['units']} | {s['without']['input']} |")
    for arm, a in report["kitsune_arms"].items():
        d, x = a["default"], a["arm"]
        lines += ["", f"## Default Kitsune vs `{arm}` on {a['units']} user-seeded units", "",
                  "| Signal | Default Kitsune | Arm |", "| --- | ---: | ---: |"]
        for key, label in (("successes", "Successes (primary)"), ("v3_user_view", "`v3_user_view`"),
                           ("runs_moved_view", "Runs that moved the user's view"),
                           ("runs_with_refusal", "Runs with a `user_tab_read_only` refusal"),
                           ("runs_with_copy_to_write", "Runs with a copy of a user tab to write"),
                           ("runs_with_copy_to_read", "Runs with a copy of a user tab to read")):
            lines.append(f"| {label} | {d[key]} | {x[key]} |")
        lines += ["", f"On the {a['joint']} units both solved, the arm's input is {a['input']}× and its agent calls "
                  f"{a['mcp_calls']}× default Kitsune's."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("suite")
    parser.add_argument("--compare")
    parser.add_argument("--outlier", type=float, default=1.10)
    parser.add_argument("--json")
    args = parser.parse_args()
    report = review(args.suite, args.compare, args.outlier)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    if report.get("compare", {}).get("warning"):
        print("warning: " + report["compare"]["warning"], file=sys.stderr)
    print(markdown(report, args.outlier), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
