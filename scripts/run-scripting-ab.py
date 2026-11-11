"""Kitsune tool-surface A/B: legacy tool list vs KITSUNE_SCRIPTING=1 (minimal 14 tools + browser_run_python).

Question: does the smaller per-request tool prefix of the scripting surface (kitsune#514/#515) lower input tokens,
as Aside's and ego(lite)'s one-tool surfaces do, without losing success? Kitsune only, no benchmark allowlist (each
arm sees what Kitsune publishes), same Kitsune checkout for both arms. Protocol:
docs/experiments/2026-11-11-kitsune-scripting-surface-ab.md.

  plan     print the run order; no browser or model calls
  run      execute the runs not yet logged (resumable); consumes subscription usage
  analyze  per-track estimands from the log; no browser or model calls

usage: uv run --locked python scripts/run-scripting-ab.py plan
       uv run --locked python scripts/run-scripting-ab.py run --kitsune-project DIR --kitsune-sha SHA [--out DIR]
       uv run --locked python scripts/run-scripting-ab.py analyze [--out DIR]

Stops (exit 2) on: a harness error or two unscorable runs in a row, a Kitsune revision change or dirty checkout,
or a published tool count other than the arm's expected count.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ARMS = {"legacy": {}, "scripting": {"KITSUNE_SCRIPTING": "1"}}
EXPECTED_TOOLS = {"legacy": 27, "scripting": 14}
REPEATS = 2
MINIWOB = ["mw-click-test-2", "mw-click-checkboxes", "mw-enter-text", "mw-choose-list", "mw-login-user",
           "mw-use-autocomplete", "mw-book-flight"]
PERSONAL = ["pb-current-01", "pb-tabs-01", "pb-research-01", "pb-account-01", "pb-handoff-01", "pb-safe-01",
            "pb-longpage-01"]
GALLERY = ["ui-table", "ui-autocomplete", "ui-infinite", "ui-shadow", "ui-iframe", "ui-editor"]
LAYOUT = "isolated"
MCP_PREFIX = "mcp__browser__"
# Code that reaches MiniWoB's client-side reward, or any page JavaScript.
TAMPER = re.compile(r"core\.|endEpisode|WOB_|EPISODE|\.evaluate\(")
URL = re.compile(r"https?://[^\s'\"]+")


def cells() -> list[tuple[str, str]]:
    return ([("miniwob", t) for t in MINIWOB] + [("personal", t) for t in PERSONAL] +
            [("gallery", t) for t in GALLERY])


def plan() -> list[dict]:
    """Repeat-major; per cell ABBA across the two repeats, the first arm alternating by cell."""
    runs = []
    for repeat in range(REPEATS):
        for index, (track, task) in enumerate(cells()):
            first = ("legacy", "scripting") if index % 2 == 0 else ("scripting", "legacy")
            for arm in (first if repeat % 2 == 0 else first[::-1]):
                runs.append({"seq": len(runs) + 1, "track": track, "task": task, "repeat": repeat, "arm": arm})
    return runs


def git(path, *args) -> str:
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True).stdout.strip()


def run_one(run: dict, project: str) -> dict:
    from kitsune_benchmark import external, gallery, personal
    from kitsune_benchmark.adapter import with_claude_overrides
    from kitsune_benchmark.full_native import full_native_relay
    from kitsune_benchmark.miniwob import BenchmarkServer
    from kitsune_benchmark.smoke import run_pair

    env = ARMS[run["arm"]]
    tag = {"benchmark": "kitsune-scripting-surface-ab-v1", "arm": run["arm"], "kitsune_env": env,
           "tool_policy": "no_benchmark_allowlist"}
    common = dict(execute=True, kitsune_project=project, executable="claude", harness="claude",
                  enabled_tools=None, targets=("kitsune",), kitsune_env=env, artifact_scope="scripting-ab")
    if run["track"] == "miniwob":
        spec = with_claude_overrides(external.config(), None, None, None)
        task = external.selected_tasks([run["task"]])[0]
        source = ROOT / spec["source_directory"]
        external.verify_source(source, spec["source_revision"])
        experiment = {**spec, "selected_task": task, "timeout_sec": spec["timeout_sec"], "scripting_ab": tag}
        with BenchmarkServer(source, spec, task) as fixture:
            return run_pair(**common, experiment_spec=experiment, task_for_target=fixture.begin,
                            evaluate=fixture.evaluate)
    module = personal if run["track"] == "personal" else gallery
    spec = with_claude_overrides(module.config(), None, None, None)
    common.update(kitsune_firefox_prefs=personal.USER_CHANNEL_PREFS, equalize_kitsune_viewport=True)
    if run["track"] == "personal":
        task = personal.selected_tasks([run["task"]])[0]
        experiment = {**spec, "selected_task": task, "variant": 0, "layout": None, "elicitation": "decline",
                      "scripting_ab": tag}
        with personal.PersonalServer(task, 0, report_viewport=True, elicitation="decline",
                                     user_channel=True) as fixture:
            return run_pair(**common, experiment_spec=experiment, task_for_target=fixture.begin,
                            prepare_server=full_native_relay(fixture.prepare_server), evaluate=fixture.evaluate,
                            viewport_reports=fixture.viewport_reports,
                            kitsune_firefox_args=personal.user_channel_args(fixture.bidi_ports["kitsune"]))
    task = gallery.select([run["task"]])[0]
    experiment = {**spec, "selected_task": {"id": task.id, "category": task.category}, "variant": 0,
                  "layout": LAYOUT, "elicitation": "decline", "scripting_ab": tag}
    with gallery.GalleryServer(task, 0, LAYOUT, "decline") as fixture:
        return run_pair(**common, experiment_spec=experiment, task_for_target=fixture.begin,
                        prepare_server=full_native_relay(fixture.prepare_server), evaluate=fixture.evaluate,
                        kitsune_firefox_args=personal.user_channel_args(fixture.kitsune_bidi_port))


def metrics(pair: dict) -> dict:
    """One run: grade, usage, requests, first-request input, published tools and the Python it ran."""
    result = pair["results"]["kitsune"]
    evaluation = result.get("benchmark_evaluation") or {}
    usage = result.get("usage") or {}
    row = {"scorable": bool(evaluation.get("scorable")), "success": evaluation.get("task_success") is True,
           "input": usage.get("input_tokens"), "output": usage.get("output_tokens"),
           "calls": result.get("mcp_calls"), "elapsed": result.get("elapsed_sec"),
           "cost": result.get("list_price_cost_usd"), "run_dir": result.get("run_dir"),
           "requests": 0, "first_input": None, "published": None, "tools": collections.Counter(),
           "python_calls": 0, "python_chars": 0, "tamper_hits": 0, "python_urls": []}
    seen = set()
    for line in (Path(result["run_dir"]) / "events.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event.get("type") == "system" and event.get("subtype") == "init" and row["published"] is None:
            row["published"] = sum(str(t).startswith(MCP_PREFIX) for t in event.get("tools") or [])
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        if message.get("id") not in seen:
            seen.add(message.get("id"))
            if row["first_input"] is None:
                u = message.get("usage") or {}
                row["first_input"] = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                                      + u.get("cache_creation_input_tokens", 0))
        for block in message.get("content") or []:
            if block.get("type") != "tool_use":
                continue
            name = str(block.get("name", "")).removeprefix(MCP_PREFIX)
            row["tools"][name] += 1
            if name == "browser_run_python":
                code = json.dumps(block.get("input"), ensure_ascii=False)
                row["python_calls"] += 1
                row["python_chars"] += len(code)
                row["tamper_hits"] += len(TAMPER.findall(code))
                row["python_urls"] += URL.findall(code)
    row["requests"] = len(seen)
    row["tools"] = dict(row["tools"])
    return row


def load_log(out: Path) -> list[dict]:
    path = out / "runs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def do_run(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    project = str(Path(args.kitsune_project).resolve())
    done = {r["seq"] for r in load_log(out)}
    unscorable = 0
    for run in plan():
        if run["seq"] in done:
            continue
        if git(project, "rev-parse", "HEAD") != args.kitsune_sha or git(project, "status", "--porcelain"):
            print("stop: Kitsune revision changed or dirty", file=sys.stderr)
            return 2
        print(f"[{run['seq']}/{len(plan())}] {run['track']} {run['task']} r{run['repeat']} {run['arm']}", flush=True)
        try:
            pair = run_one(run, project)
        except Exception as error:  # noqa: BLE001 - record and stop; no further quota after a setup failure
            print(f"stop: {type(error).__name__}: {error}", file=sys.stderr)
            return 2
        row = {**run, "pair_dir": pair.get("pair_dir"), **metrics(pair)}
        with (out / "runs.jsonl").open("a") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"    success={row['success']} input={row['input']} req={row['requests']} calls={row['calls']} "
              f"published={row['published']} python={row['python_calls']}", flush=True)
        if row["published"] != EXPECTED_TOOLS[run["arm"]]:
            print(f"stop: {run['arm']} published {row['published']} tools, expected {EXPECTED_TOOLS[run['arm']]}",
                  file=sys.stderr)
            return 2
        unscorable = 0 if row["scorable"] else unscorable + 1
        if unscorable >= 2:
            print("stop: two unscorable runs in a row", file=sys.stderr)
            return 2
    return 0


def ratio(a, b):
    return round(a / b, 3) if b else None


def analyze(out: Path) -> dict:
    rows = load_log(out)
    report = {"runs": len(rows), "tracks": {}}
    for track in ("miniwob", "personal", "gallery", "all"):
        sub = [r for r in rows if track == "all" or r["track"] == track]
        arms = {}
        for arm in ARMS:
            a = [r for r in sub if r["arm"] == arm]
            arms[arm] = {"runs": len(a), "successes": sum(r["success"] for r in a),
                         "input": sum(r["input"] or 0 for r in a), "output": sum(r["output"] or 0 for r in a),
                         "requests": sum(r["requests"] for r in a), "calls": sum(r["calls"] or 0 for r in a),
                         "elapsed": round(sum(r["elapsed"] or 0 for r in a), 1),
                         "cost": round(sum(r["cost"] or 0 for r in a), 3),
                         "first_input_median": statistics.median([r["first_input"] for r in a]) if a else None,
                         "python_calls": sum(r["python_calls"] for r in a),
                         "runs_with_python": sum(r["python_calls"] > 0 for r in a),
                         "tamper_hits": sum(r["tamper_hits"] for r in a)}
        # Matched (task, repeat) cells where both arms succeeded.
        by = collections.defaultdict(dict)
        for r in sub:
            by[(r["task"], r["repeat"])][r["arm"]] = r
        joint = [v for v in by.values() if all(v.get(arm, {}).get("success") for arm in ARMS)]
        cell_ratios = [v["scripting"]["input"] / v["legacy"]["input"] for v in joint]
        report["tracks"][track] = {
            "arms": arms, "joint_cells": len(joint),
            "joint_input_ratio": ratio(sum(v["scripting"]["input"] for v in joint),
                                       sum(v["legacy"]["input"] for v in joint)),
            "joint_requests_ratio": ratio(sum(v["scripting"]["requests"] for v in joint),
                                          sum(v["legacy"]["requests"] for v in joint)),
            "joint_cost_ratio": ratio(sum(v["scripting"]["cost"] or 0 for v in joint),
                                      sum(v["legacy"]["cost"] or 0 for v in joint)),
            "cell_input_ratio_median": round(statistics.median(cell_ratios), 3) if cell_ratios else None,
            "cells_scripting_lower": sum(x < 1 for x in cell_ratios)}
    report["per_task"] = {}
    for r in rows:
        t = report["per_task"].setdefault(r["task"], {arm: [] for arm in ARMS})
        t[r["arm"]].append({k: r[k] for k in ("success", "input", "requests", "calls", "python_calls")})
    report["python_urls"] = sorted({u for r in rows for u in r["python_urls"]})
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    run = sub.add_parser("run")
    run.add_argument("--kitsune-project", required=True)
    run.add_argument("--kitsune-sha", required=True)
    run.add_argument("--out", default="artifacts/scripting-ab")
    an = sub.add_parser("analyze")
    an.add_argument("--out", default="artifacts/scripting-ab")
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
