"""H18 A/B (issue #4): Kitsune with vs without listing short similar-item runs in full.

Arms are two clean Kitsune checkouts: A = baseline, B = the same revision plus exactly one change, a
similar-item run that would hide at most five items is listed in full (snapshots and action deltas).
Both arms run the Kitsune target only, on the default subscription harness (Claude Code, the config's
model and effort). The design and the predeclared decision are in
docs/experiments/2026-10-25-issue-18-ui-table-rounds.md (draft hypothesis) and
docs/experiments/2026-10-28-h18-collapse-ab.md (the frozen protocol of this cohort).

  plan     print the run order; no browser or model calls
  run      execute the runs not yet logged (resumable); consumes subscription usage
  analyze  estimands, gates and the verdict from the log; no browser or model calls

usage: uv run --locked python scripts/run-h18.py plan
       uv run --locked python scripts/run-h18.py run --baseline DIR --baseline-sha SHA --intervention DIR \\
           --intervention-sha SHA [--out artifacts/h18]
       uv run --locked python scripts/run-h18.py analyze [--out artifacts/h18]

One harness invocation per agent run. Unscorable runs are logged and not replaced. Stops (exit 2) on: a harness
error without a parseable summary, two unscorable runs in a row, a Kitsune revision change or dirty checkout,
tool surfaces that differ between the arms, a collapse marker hiding at most five items in an intervention
run (the change is not in effect), or navigation outside the fixture (potential real harm).
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analyze_model_rounds", ROOT / "scripts/analyze-model-rounds.py")
rounds_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rounds_script)

ARMS = ("baseline", "intervention")
LISTED_REMAINDER_LIMIT = 5
TABLE_REPEATS, GUARD_REPEATS = 4, 3
# (track, task, variant, layout); table cells first, then guards.
TABLE_CELLS = [("gallery", "ui-table", v, layout) for v in range(3) for layout in ("crowded", "isolated")]
GUARD_CELLS = [("gallery", "ui-infinite", 0, "isolated"), ("gallery", "mm-grid", 0, "isolated"),
               ("personal", "pb-longpage-01", 0, None)]
MARKER = re.compile(r"… (\d+) more similar items; snapshot ")

# Predeclared thresholds (draft H18, unchanged).
SUPPORT_REQUEST_RATIO, SUPPORT_TABLE_INPUT_RATIO, SUPPORT_GUARD_INPUT_RATIO = 0.85, 0.95, 1.05
REJECT_REQUEST_RATIO, REJECT_TABLE_INPUT_RATIO = 0.95, 1.00
MIN_ISOLATED_PAIRS, MIN_TABLE_PAIRS = 10, 20


def cell_key(cell) -> str:
    track, task, variant, layout = cell
    return f"{task}/v{variant}" + (f"/{layout}" if layout else "")


def orders(index: int, repeats: int) -> list[tuple[str, str]]:
    """ABBA / BAAB for four repeats, ABA / BAB for three; the pattern alternates between cells."""
    first = ("baseline", "intervention") if index % 2 == 0 else ("intervention", "baseline")
    flipped = first[::-1]
    pattern = [first, flipped, flipped, first] if repeats == 4 else [first, flipped, first]
    return pattern[:repeats]


def plan() -> list[dict]:
    """Repeat-major, so a drift over the session spreads over every cell."""
    cells = [(c, TABLE_REPEATS, "table") for c in TABLE_CELLS] + [(c, GUARD_REPEATS, "guard") for c in GUARD_CELLS]
    runs = []
    for repeat in range(TABLE_REPEATS):
        for index, (cell, repeats, kind) in enumerate(cells):
            if repeat >= repeats:
                continue
            for arm in orders(index, repeats)[repeat]:
                track, task, variant, layout = cell
                runs.append({"seq": len(runs) + 1, "kind": kind, "cell": cell_key(cell), "track": track, "task": task,
                             "variant": variant, "layout": layout, "repeat": repeat, "arm": arm,
                             "order": "AB" if orders(index, repeats)[repeat][0] == "baseline" else "BA"})
    return runs


def git(path: str, *args: str) -> str:
    return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True).stdout.strip()


def checkout_ok(path: str, sha: str) -> bool:
    return git(path, "rev-parse", "HEAD") == sha and not git(path, "status", "--porcelain")


def markers(run_dir: str | None) -> list[int]:
    events = Path(run_dir or "") / "events.jsonl"
    return [int(n) for n in MARKER.findall(events.read_text(errors="ignore"))] if events.is_file() else []


def execute(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "runs.jsonl"
    projects = {"baseline": (args.baseline, args.baseline_sha), "intervention": (args.intervention, args.intervention_sha)}
    done = {(r["cell"], r["repeat"], r["arm"]): r for r in read_log(log)}
    surfaces = {r["arm"]: r["tool_surface_exposed"] for r in done.values() if r.get("tool_surface_exposed")}
    unscorable_streak = 0
    for run in plan():
        if (run["cell"], run["repeat"], run["arm"]) in done:
            continue
        path, sha = projects[run["arm"]]
        if not all(checkout_ok(*projects[arm]) for arm in ARMS):
            return stop("kitsune_revision_changed", run)
        argv = ["uv", "run", "--locked", "python", "-m", "kitsune_benchmark", run["track"], "--execute",
                "--task", run["task"], "--variant", str(run["variant"]), "--targets", "kitsune",
                "--kitsune-project", path]
        if run["layout"]:
            argv += ["--layout", run["layout"]]
        started = time.time()
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        rec = {**run, "exit": p.returncode, "wall_sec": round(time.time() - started, 3), "stderr_tail": p.stderr[-1500:]}
        try:
            summary = json.loads(p.stdout)
            pair = summary["pairs"][0]
            r = pair["results"]["kitsune"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            rec.update(status="harness_error", error=repr(exc), stdout_tail=p.stdout[-1500:])
            append(log, rec)
            return stop("harness_error", run)
        ev = r.get("benchmark_evaluation") or {}
        contracts = ev.get("contracts") or {}
        surface = (r.get("tool_surface") or {}).get("exposed")
        rec.update(suite=summary.get("suite_summary_path"), pair_dir=pair.get("pair_dir"), run_dir=r.get("run_dir"),
                   kitsune_source=summary.get("kitsune_source"), kitsune_source_after=pair.get("kitsune_source_after"),
                   model=summary.get("model"), harness=summary.get("harness"),
                   scorable=ev.get("scorable"), success=ev.get("task_success"), primary_contract=ev.get("primary_contract"),
                   success_v1=(contracts.get("v1_strict_close") or {}).get("task_success"),
                   safety_v1=(contracts.get("v1_strict_close") or {}).get("safety_pass"),
                   safety_v2=(contracts.get("v2_agent_tab_cleanup") or {}).get("safety_pass"),
                   functional=ev.get("functional_success"), outcome=ev.get("outcome"),
                   failure_class=ev.get("failure_class"), outside_navigation=ev.get("outside_navigation"),
                   usage=r.get("usage"), token_attribution={k: v for k, v in (r.get("token_attribution") or {}).items()
                                                            if k != "per_tool"},
                   mcp_calls=r.get("mcp_calls"), failed_mcp_calls=r.get("failed_mcp_calls"),
                   elapsed_sec=r.get("elapsed_sec"), execution_status=r.get("execution_status"),
                   list_price_cost_usd=r.get("list_price_cost_usd"), tool_surface_exposed=surface,
                   collapse_markers=markers(r.get("run_dir")))
        reason = None
        if rec["scorable"] is not True:
            unscorable_streak += 1
            rec["status"] = "unscorable"
            if unscorable_streak >= 2:
                reason = "two_unscorable_in_a_row"
        else:
            unscorable_streak = 0
            rec["status"] = "ok"
        source = rec["kitsune_source"] or {}
        if source.get("revision") != sha or source.get("dirty") or rec["kitsune_source_after"] != rec["kitsune_source"]:
            reason = "kitsune_revision_changed"
        elif surface is not None and any(s != surface for s in surfaces.values()):
            reason = "tool_surface_differs_between_arms"
        elif run["arm"] == "intervention" and any(n <= LISTED_REMAINDER_LIMIT for n in rec["collapse_markers"]):
            reason = "intervention_not_in_effect"
        elif (rec["outside_navigation"] or 0) > 0:
            reason = "potential_real_harm"
        if surface is not None:
            surfaces.setdefault(run["arm"], surface)
        append(log, rec)
        done[(run["cell"], run["repeat"], run["arm"])] = rec
        usage = rec["usage"] or {}
        print(f"{run['seq']:3d} {run['cell']:24s} r{run['repeat']} {run['arm']:12s} success={rec['success']} "
              f"requests={rec['token_attribution'].get('requests')} in={usage.get('input_tokens')} "
              f"markers={len(rec['collapse_markers'])} {rec['wall_sec']}s", flush=True)
        if reason:
            return stop(reason, run)
    print(json.dumps({"finished": True, "runs": len(done)}))
    return 0


def read_log(log: Path) -> list[dict]:
    if not log.exists():
        return []
    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    # A harness error is retried on resume; a scorable or unscorable run is final.
    return [r for r in rows if r.get("status") in ("ok", "unscorable")]


def append(log: Path, rec: dict) -> None:
    with log.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def stop(reason: str, run: dict) -> int:
    print(json.dumps({"stopped": reason, "run": run}, ensure_ascii=False), flush=True)
    return 2


def input_tokens(rec: dict) -> int:
    return (rec.get("usage") or {}).get("input_tokens") or 0


def analyze(args) -> int:
    out = Path(args.out)
    rows = read_log(out / "runs.jsonl")
    for rec in rows:
        events = Path(rec.get("run_dir") or "") / "events.jsonl"
        if events.is_file():
            s = rounds_script.run_summary(rounds_script.read_events(events))
            rec["rounds"] = {k: v for k, v in s.items() if k != "rounds"}
    by = {(r["cell"], r["repeat"], r["arm"]): r for r in rows}
    cells = [(cell_key(c), "table", c[3]) for c in TABLE_CELLS] + [(cell_key(c), "guard", c[3]) for c in GUARD_CELLS]
    pairs, dropped = [], []
    for key, kind, layout in cells:
        for repeat in range(TABLE_REPEATS if kind == "table" else GUARD_REPEATS):
            a, b = by.get((key, repeat, "baseline")), by.get((key, repeat, "intervention"))
            joint = bool(a and b and a["scorable"] is True and b["scorable"] is True and a["success"] and b["success"])
            entry = {"cell": key, "kind": kind, "layout": layout, "repeat": repeat, "baseline": a, "intervention": b}
            (pairs if joint else dropped).append(entry)

    def requests(rec):
        return (rec.get("token_attribution") or {}).get("requests") or 0

    isolated = [p for p in pairs if p["kind"] == "table" and p["layout"] == "isolated"]
    table = [p for p in pairs if p["kind"] == "table"]
    request_ratio = statistics.median(requests(p["intervention"]) / requests(p["baseline"]) for p in isolated) \
        if isolated else None
    table_input_ratio = (sum(input_tokens(p["intervention"]) for p in table) /
                         sum(input_tokens(p["baseline"]) for p in table)) if table else None
    guard_input_ratio = {}
    for key, kind, _ in cells:
        group = [p for p in pairs if p["cell"] == key]
        if kind == "guard":
            guard_input_ratio[key] = (sum(input_tokens(p["intervention"]) for p in group) /
                                      sum(input_tokens(p["baseline"]) for p in group)) if group else None
    gates = {}
    for key, kind, _ in cells:
        gates[key] = {}
        for arm in ARMS:
            runs = [r for r in rows if r["cell"] == key and r["arm"] == arm]
            gates[key][arm] = {
                "attempts": len(runs),
                "successes": sum(1 for r in runs if r["scorable"] is True and r["success"]),
                "unscorable": sum(1 for r in runs if r["scorable"] is not True),
                "safety_failures_v1": sum(1 for r in runs if r.get("safety_v1") is False),
                "safety_failures_v2": sum(1 for r in runs if r.get("safety_v2") is False),
                "recovered_errors": sum((r.get("failed_mcp_calls") or 0) for r in runs if r["scorable"] is True and r["success"]),
            }
    gate_ok = all(g["intervention"]["successes"] >= g["baseline"]["successes"] and
                  g["intervention"]["safety_failures_v1"] <= g["baseline"]["safety_failures_v1"] and
                  g["intervention"]["safety_failures_v2"] <= g["baseline"]["safety_failures_v2"]
                  for g in gates.values())
    recovered = {arm: sum(g[arm]["recovered_errors"] for g in gates.values()) for arm in ARMS}
    enough = len(isolated) >= MIN_ISOLATED_PAIRS and len(table) >= MIN_TABLE_PAIRS
    verdict = "inconclusive"
    if enough and request_ratio is not None and table_input_ratio is not None:
        if request_ratio > REJECT_REQUEST_RATIO or table_input_ratio > REJECT_TABLE_INPUT_RATIO:
            verdict = "reject"
        elif (gate_ok and request_ratio <= SUPPORT_REQUEST_RATIO and table_input_ratio <= SUPPORT_TABLE_INPUT_RATIO and
              all(v is not None and v <= SUPPORT_GUARD_INPUT_RATIO for v in guard_input_ratio.values()) and
              recovered["intervention"] <= recovered["baseline"]):
            verdict = "support"

    def totals(group, arm):
        recs = [p[arm] for p in group]
        rounds = [r.get("rounds") or {} for r in recs]
        att = [r.get("token_attribution") or {} for r in recs]
        usage = [r.get("usage") or {} for r in recs]
        return {"pairs": len(recs), "requests": sum(requests(r) for r in recs), "input": sum(input_tokens(r) for r in recs),
                "cache_read": sum(u.get("cached_input_tokens") or 0 for u in usage),
                "cache_write": sum(u.get("cache_creation_input_tokens") or 0 for u in usage),
                "uncached": sum(u.get("uncached_input_tokens") or 0 for u in usage),
                "output": sum(u.get("output_tokens") or 0 for u in usage),
                "prefix_x_requests": sum(a.get("prefix_x_requests_tokens") or 0 for a in att),
                "history": sum(a.get("history_tokens") or 0 for a in att),
                "mcp_calls": sum(r.get("mcp_calls") or 0 for r in recs),
                "failed_mcp_calls": sum(r.get("failed_mcp_calls") or 0 for r in recs),
                **{k: sum(x.get(k) or 0 for x in rounds) for k in
                   ("follow_up_observation", "chained_observation", "expansion_reads", "result_chars")},
                "observation_only_rounds": sum((x.get("kinds") or {}).get("observation", 0) for x in rounds),
                "collapse_markers": sum(len(r.get("collapse_markers") or []) for r in recs),
                "elapsed_sec": round(sum(r.get("elapsed_sec") or 0 for r in recs), 1)}

    per_cell = {}
    for key, kind, _ in cells:
        group = [p for p in pairs if p["cell"] == key]
        per_cell[key] = {arm: totals(group, arm) for arm in ARMS}
        per_cell[key]["request_ratios"] = [round(requests(p["intervention"]) / requests(p["baseline"]), 3) for p in group]
        per_cell[key]["input_ratios"] = [round(input_tokens(p["intervention"]) / input_tokens(p["baseline"]), 3)
                                         for p in group]
    groups = {"table_isolated": isolated, "table_crowded": [p for p in table if p["layout"] == "crowded"], "table": table}
    report = {
        "runs_logged": len(rows), "jointly_successful_pairs": {"isolated_table": len(isolated), "table": len(table),
                                                               "all": len(pairs)},
        "dropped_pairs": [{"cell": p["cell"], "repeat": p["repeat"],
                           **{arm: None if not p[arm] else {"scorable": p[arm]["scorable"], "success": p[arm]["success"],
                                                             "outcome": p[arm].get("outcome"),
                                                             "failure_class": p[arm].get("failure_class")}
                              for arm in ARMS}} for p in dropped],
        "request_ratio": request_ratio, "table_input_ratio": table_input_ratio, "guard_input_ratio": guard_input_ratio,
        "gates": gates, "gates_ok": gate_ok, "recovered_errors": recovered, "enough_pairs": enough, "verdict": verdict,
        "totals": {name: {arm: totals(group, arm) for arm in ARMS} for name, group in groups.items()},
        "per_cell": per_cell,
        "orders": dict(collections.Counter(f"{r['arm']}:{r['order']}" for r in rows)),
        "kitsune_sources": {arm: sorted({json.dumps(r.get("kitsune_source"), sort_keys=True) for r in rows
                                         if r["arm"] == arm}) for arm in ARMS},
        "models": sorted({str(r.get("model")) for r in rows}),
        "wall_sec": round(sum(r.get("wall_sec") or 0 for r in rows), 1),
    }
    (out / "analysis.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("per_cell", "totals", "gates")}, indent=1,
                     ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    run = sub.add_parser("run")
    for arm in ARMS:
        run.add_argument(f"--{arm}", required=True, help=f"{arm} Kitsune checkout")
        run.add_argument(f"--{arm}-sha", required=True)
    run.add_argument("--out", default="artifacts/h18")
    an = sub.add_parser("analyze")
    an.add_argument("--out", default="artifacts/h18")
    args = parser.parse_args()
    if args.command == "plan":
        runs = plan()
        for r in runs:
            print(f"{r['seq']:3d} {r['kind']:5s} {r['cell']:24s} r{r['repeat']} {r['order']} {r['arm']}")
        print(json.dumps({"runs": len(runs), **collections.Counter(r["kind"] for r in runs)}))
        return 0
    return execute(args) if args.command == "run" else analyze(args)


if __name__ == "__main__":
    sys.exit(main())
