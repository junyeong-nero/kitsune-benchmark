"""Offline review of a full-suite output directory: audit, outcomes, Kitsune/Playwright ratios, outliers, tool errors
and agent-behaviour signals. No model or browser calls.

usage: uv run --locked python scripts/analyze-release.py artifacts/opus-subscription-v0.7.1 \\
           [--compare artifacts/opus-subscription-v0.7.0/full] [--outlier 1.10] [--json out.json] > review.md

Units are (track entry without its target, task); for example ("gallery-crowded-v0", "ui-shadow"). Ratios are
Kitsune/Playwright totals over units both targets solved. With --compare, the same ratios are computed on the units
the two suites share, so a lite run can be compared with the matching units of a full run. Kitsune's holds (calls kept
for the user's approval, and declined writes redone in another tab) are recomputed per entry from session evidence.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.holds import DECISIONS, DETAILS, aggregate_holds, hold_metrics  # noqa: E402

TARGETS = ("playwright", "kitsune")
ACTIONS = ("click", "type", "fill_form", "select_option", "press_key", "hover", "drag")
OBSERVATIONS = ("snapshot", "find", "wait_for", "take_screenshot")


def group_of(entry: str) -> str | None:
    """The ratio group of a suite entry; None for Kitsune-only arms."""
    if entry.startswith("coexistence-protect"):
        return None
    for prefix in ("personal", "gallery-crowded", "gallery-isolated", "coexistence-user-seeded", "coexistence-typing",
                   "external", "miniwob"):
        if entry.startswith(prefix):
            return prefix
    return entry


def load(suite_dir: str | Path) -> dict:
    """{(entry, task): {target: run}} from suite-log.jsonl and the per-track suite summaries."""
    units: dict = collections.defaultdict(dict)
    for line in (Path(suite_dir) / "suite-log.jsonl").read_text().splitlines():
        entry = json.loads(line)
        path = entry.get("suite_summary_path")
        if not path:
            continue
        summary = json.loads(Path(path).read_text())
        for pair in summary.get("pairs", []):
            task = (pair.get("personal_task") or pair.get("gallery_task") or pair.get("coexistence_task")
                    or pair.get("external_task") or "?")
            for target, run in pair["results"].items():
                units[(entry["name"], task)][target] = {**run, "pair_dir": pair.get("pair_dir")}
    return units


def tool_calls(run: dict) -> list[tuple[str, dict, str, bool]]:
    """(tool, arguments, result text, is_error) in order, from the run's Claude Code stream."""
    events = Path(run.get("run_dir") or "") / "events.jsonl"
    if not events.is_file():
        return []
    pending, out = {}, []
    for line in events.read_text(errors="ignore").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_use":
                pending[block["id"]] = (block["name"].split("__")[-1].replace("browser_", ""), block.get("input") or {})
            elif block.get("type") == "tool_result":
                raw = block.get("content")
                text = raw if isinstance(raw, str) else " ".join(i.get("text", "") for i in raw or [] if isinstance(i, dict))
                name, args = pending.pop(block.get("tool_use_id"), ("?", {}))
                out.append((name, args, text, bool(block.get("is_error"))))
    return out


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


def audit(units: dict) -> dict:
    counts = collections.Counter()
    models = collections.Counter()
    for (entry, _), runs in units.items():
        for run in runs.values():
            counts["runs"] += 1
            counts["status:" + str(run.get("execution_status"))] += 1
            counts["scorable"] += evaluation(run).get("scorable") is True
            counts["violations"] += bool(run.get("violations"))
            counts["harness_errors"] += bool(run.get("harness_error"))
            counts["missing_allowlisted_tools"] += bool((run.get("tool_surface") or {}).get("missing"))
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
            for i, (name, args, text, is_error) in enumerate(calls):
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
                    following = calls[i + 1][0] if i + 1 < len(calls) else None
                    m["actions_followed_by_observation"] += following in OBSERVATIONS
    summary = {}
    for target, m in out.items():
        summary[target] = {
            **dict(m),
            "observation_after_action_rate": round(m["actions_followed_by_observation"] / m["actions"], 3) if m["actions"] else None,
            "mean_action_response_chars": round(m["action_chars"] / m["actions"]) if m["actions"] else None,
            "mean_find_chars": round(m["find_chars"] / m["find_calls"]) if m["find_calls"] else None,
            "mean_full_snapshot_chars": round(m["full_snapshot_chars"] / m["full_snapshots"]) if m["full_snapshots"] else None,
            "tool_errors": dict(errors[target].most_common(10)),
        }
    return summary


def holds(units: dict) -> dict:
    """Kitsune holds per entry, from each run's session evidence (holds.py); entries without Kitsune runs are left out."""
    metrics = collections.defaultdict(list)
    for (entry, _), runs in units.items():
        if "kitsune" in runs:
            pair_dir = runs["kitsune"].get("pair_dir")
            try:  # missing or truncated evidence: no hold record for the run
                evidence = json.loads((Path(pair_dir) / "kitsune-session-evidence.json").read_text()) if pair_dir else None
            except (OSError, ValueError):
                evidence = None
            metrics[entry].append(hold_metrics(evidence) if isinstance(evidence, dict) else None)
    return {entry: aggregate_holds(values) for entry, values in metrics.items()}


def review(suite_dir, compare=None, threshold=1.10) -> dict:
    units = load(suite_dir)
    report = {"suite": str(suite_dir), "audit": audit(units), "outcomes": outcomes(units), "ratios": ratios(units),
              "outliers": outliers(units, threshold), "behaviour": behaviour(units), "holds": holds(units)}
    if compare:
        old = load(compare)
        shared = set(units) & set(old)
        report["compare"] = {"suite": str(compare), "shared_units": len(shared),
                             "ratios_now": ratios(units, shared), "ratios_then": ratios(old, shared)}
    return report


def markdown(report: dict, threshold: float) -> str:
    a = report["audit"]
    lines = [f"# Release review: `{report['suite']}`", "",
             "## Audit", "",
             f"- Runs: {a.get('runs', 0)}; scorable {a.get('scorable', 0)}; "
             + ", ".join(f"{k.split(':', 1)[1]} {v}" for k, v in a.items() if k.startswith("status:")),
             f"- Audit violations {a.get('violations', 0)}, harness errors {a.get('harness_errors', 0)}, runs missing "
             f"allowlisted tools {a.get('missing_allowlisted_tools', 0)}; models {a['models']}",
             f"- Personal content viewport asserted: {a.get('personal_viewport_asserted', 0)}/{a.get('personal_runs', 0)}",
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
    if "compare" in report:
        c = report["compare"]
        lines += ["", f"## Compared with `{c['suite']}` on {c['shared_units']} shared units", "",
                  "| Group | Input then | Input now | Calls then | Calls now |", "| --- | ---: | ---: | ---: | ---: |"]
        for group, now in c["ratios_now"].items():
            then = c["ratios_then"].get(group, {})
            lines.append(f"| {group} | {then.get('input')} | {now['input']} | {then.get('mcp_calls')} | {now['mcp_calls']} |")
    lines += ["", f"## Units where Kitsune input exceeds {threshold}× Playwright", "",
              "| Unit | Ratio | Input PW / K | Calls PW / K | Kitsune calls |", "| --- | ---: | --- | --- | --- |"]
    for o in report["outliers"]:
        lines.append(f"| {o['task']} ({o['entry']}) | {o['input_ratio']} | {o['input']['playwright']} / {o['input']['kitsune']} | "
                     f"{o['mcp_calls']['playwright']} / {o['mcp_calls']['kitsune']} | {' '.join(o['kitsune_calls'])} |")
    lines += ["", "## Behaviour", "", "| Signal | Playwright | Kitsune |", "| --- | ---: | ---: |"]
    b = report["behaviour"]
    for key, label in (("calls", "Tool calls"), ("observation_after_action_rate", "Observation right after an action"),
                       ("mean_action_response_chars", "Mean action response (chars)"), ("blind_waits", "`wait_for {time}` only"),
                       ("runs_starting_with_tabs_list", "Runs starting with `tabs list`"),
                       ("mean_find_chars", "Mean `find` result (chars)"), ("mean_full_snapshot_chars", "Mean full snapshot (chars)"),
                       ("truncated_full_snapshots", "Truncated full snapshots")):
        lines.append(f"| {label} | {b['playwright'].get(key)} | {b['kitsune'].get(key)} |")
    lines += ["", "Tool errors (Kitsune): " + (", ".join(f"{v}× {k}" for k, v in b["kitsune"]["tool_errors"].items()) or "none")]
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
    print(markdown(report, args.outlier), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
