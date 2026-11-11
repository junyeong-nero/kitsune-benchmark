"""Kitsune scripting-surface schema-text A/B (kitsune#521, PR kitsune#523).

Both arms run KITSUNE_SCRIPTING=1 (14 tools). `base` is Kitsune main; `trim` is the same main plus PR #523, which
publishes shorter parameter descriptions and no `$schema` for the 11 retained Playwright tools on that surface
only. Does the smaller prefix lower input without more argument errors, requests or cost? Tasks, order, metrics
and stops reuse scripts/run-scripting-ab.py. Protocol: docs/experiments/2026-11-11-kitsune-521-schema-trim-ab.md.

usage: uv run --locked python scripts/run-schema-trim-ab.py plan
       uv run --locked python scripts/run-schema-trim-ab.py run --base-project DIR --base-sha SHA \
           --trim-project DIR --trim-sha SHA [--out DIR] [--smoke]
       uv run --locked python scripts/run-schema-trim-ab.py analyze [--out DIR]
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("scripting_ab", ROOT / "scripts" / "run-scripting-ab.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

BENCHMARK = "kitsune-521-schema-trim-ab-v1"
ARMS = {"base": {"KITSUNE_SCRIPTING": "1"}, "trim": {"KITSUNE_SCRIPTING": "1"}}
EXPECTED_TOOLS = 14
# Argument errors: Claude Code's schema check and the server's pydantic validation.
VALIDATION = re.compile(r"InputValidationError|validation error", re.I)
SMOKE = [{"seq": 0, "track": "miniwob", "task": "mw-click-test-2", "repeat": -1, "arm": arm} for arm in ARMS] + [
    {"seq": 0, "track": "personal", "task": "pb-current-01", "repeat": -1, "arm": "trim"}]

ab.ARMS = ARMS  # run_one reads its arm's environment from here


def plan() -> list[dict]:
    """The original repeat-major ABBA order with base in legacy's place and trim in scripting's."""
    names = {"legacy": "base", "scripting": "trim"}
    return [{**run, "arm": names[run["arm"]]} for run in ab.plan()]


def errors(run_dir: str) -> dict:
    """Failed tool results by tool, and those that are argument-validation errors."""
    names, failed, validation = {}, collections.Counter(), collections.Counter()
    for line in (Path(run_dir) / "events.jsonl").read_text().splitlines():
        event = json.loads(line)
        for block in (event.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                names[block.get("id")] = str(block.get("name", "")).removeprefix(ab.MCP_PREFIX)
            elif block.get("type") == "tool_result" and block.get("is_error") is True:
                name = names.get(block.get("tool_use_id"), "?")
                failed[name] += 1
                if VALIDATION.search(json.dumps(block.get("content"), ensure_ascii=False)):
                    validation[name] += 1
    return {"tool_errors": dict(failed), "validation_errors": dict(validation)}


def do_run(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    projects = {"base": (str(Path(args.base_project).resolve()), args.base_sha),
                "trim": (str(Path(args.trim_project).resolve()), args.trim_sha)}
    log = out / ("smoke.jsonl" if args.smoke else "runs.jsonl")
    runs = SMOKE if args.smoke else plan()
    done = set() if args.smoke else {r["seq"] for r in ab.load_log(out)}
    unscorable = 0
    for run in runs:
        if run["seq"] in done:
            continue
        for project, sha in projects.values():
            if ab.git(project, "rev-parse", "HEAD") != sha or ab.git(project, "status", "--porcelain"):
                print(f"stop: Kitsune revision changed or dirty: {project}", file=sys.stderr)
                return 2
        project, sha = projects[run["arm"]]
        print(f"[{run['seq']}/{len(runs)}] {run['track']} {run['task']} r{run['repeat']} {run['arm']}", flush=True)
        try:
            pair = ab.run_one(run, project, BENCHMARK)
        except Exception as error:  # noqa: BLE001 - record and stop; no further quota after a setup failure
            print(f"stop: {type(error).__name__}: {error}", file=sys.stderr)
            return 2
        metrics = ab.metrics(pair)
        row = {**run, "kitsune_sha": sha, "pair_dir": pair.get("pair_dir"), **metrics, **errors(metrics["run_dir"])}
        with log.open("a") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"    success={row['success']} input={row['input']} first={row['first_input']} req={row['requests']} "
              f"published={row['published']} python={row['python_calls']} errors={row['tool_errors']} "
              f"validation={row['validation_errors']}", flush=True)
        if row["published"] != EXPECTED_TOOLS:
            print(f"stop: {run['arm']} published {row['published']} tools, expected {EXPECTED_TOOLS}", file=sys.stderr)
            return 2
        if args.smoke and not (row["scorable"] and row["success"]):
            print("stop: smoke unscorable or failed", file=sys.stderr)
            return 2
        unscorable = 0 if row["scorable"] else unscorable + 1
        if unscorable >= 2:
            print("stop: two unscorable runs in a row", file=sys.stderr)
            return 2
    return 0


def _sum(rows, key):
    return sum(r[key] or 0 for r in rows)


def _errors(rows, key):
    return sum(sum(r[key].values()) for r in rows)


def analyze(out: Path) -> dict:
    rows = ab.load_log(out)
    report = {"runs": len(rows), "tracks": {}}
    for track in ("miniwob", "personal", "gallery", "all"):
        sub = [r for r in rows if track == "all" or r["track"] == track]
        arms = {}
        for arm in ARMS:
            a = [r for r in sub if r["arm"] == arm]
            arms[arm] = {"runs": len(a), "successes": sum(r["success"] for r in a),
                         **{k: _sum(a, k) for k in ("input", "output", "requests", "calls")},
                         "elapsed": round(_sum(a, "elapsed"), 1), "cost": round(_sum(a, "cost"), 3),
                         "first_input_median": statistics.median([r["first_input"] for r in a]) if a else None,
                         "python_calls": _sum(a, "python_calls"),
                         "runs_with_python": sum(r["python_calls"] > 0 for r in a),
                         "tool_errors": _errors(a, "tool_errors"),
                         "validation_errors": _errors(a, "validation_errors"),
                         "tamper_hits": _sum(a, "tamper_hits")}
        by = collections.defaultdict(dict)
        for r in sub:
            by[(r["task"], r["repeat"])][r["arm"]] = r
        joint = [v for v in by.values() if all(v.get(arm, {}).get("success") for arm in ARMS)]
        ratios = [v["trim"]["input"] / v["base"]["input"] for v in joint]
        report["tracks"][track] = {
            "arms": arms, "joint_cells": len(joint),
            **{f"joint_{k}_ratio": ab.ratio(sum(v["trim"][k] or 0 for v in joint), sum(v["base"][k] or 0 for v in joint))
               for k in ("input", "requests", "cost", "output")},
            "cell_input_ratio_median": round(statistics.median(ratios), 3) if ratios else None,
            "cells_trim_lower": sum(x < 1 for x in ratios)}
    report["per_task"] = {}
    for r in rows:
        t = report["per_task"].setdefault(r["task"], {arm: [] for arm in ARMS})
        t[r["arm"]].append({k: r[k] for k in ("success", "input", "requests", "calls", "python_calls",
                                               "tool_errors", "validation_errors")})
    report["python_urls"] = sorted({u for r in rows for u in r["python_urls"]})
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    run = sub.add_parser("run")
    for arm in ARMS:
        run.add_argument(f"--{arm}-project", required=True)
        run.add_argument(f"--{arm}-sha", required=True)
    run.add_argument("--out", default="artifacts/schema-trim-ab-521")
    run.add_argument("--smoke", action="store_true", help="the three uncounted smokes, logged to smoke.jsonl")
    an = sub.add_parser("analyze")
    an.add_argument("--out", default="artifacts/schema-trim-ab-521")
    args = parser.parse_args()
    if args.cmd == "plan":
        runs = plan()
        print(json.dumps({"runs": len(runs), "arms": ARMS, "expected_tools": EXPECTED_TOOLS, "plan": runs}, indent=1))
        return 0
    if args.cmd == "run":
        return do_run(args)
    report = analyze(Path(args.out))
    (Path(args.out) / "analysis.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "per_task"}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
