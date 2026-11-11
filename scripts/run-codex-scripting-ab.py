"""Codex subscription replication of the Kitsune legacy/scripting A/B (80 runs).

Reuse the original tasks, ABBA order, fixtures and pinned checkout. Codex does not
report per-request usage, model request counts or dollar cost; leave them unavailable.
Personal/gallery relays record the actual tool catalog. MiniWoB has no relay, so
its catalog is checked separately by importing the pinned server without a browser.

  run --kitsune-project DIR --kitsune-sha SHA --out DIR [--limit N]
  analyze --out DIR

Stops on any execution/unscorable failure or changed source/catalog. Explicit
--continue-unstarted preserves zero-start MiniWoB attempts and continues; the
original manifest/rows stay unchanged and continuation.json records this policy.
Other failures still require review. Never mix Claude results.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("scripting_ab", ROOT / "scripts/run-scripting-ab.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

from kitsune_benchmark import external, gallery, personal
from kitsune_benchmark.adapter import harness_pins, resolve, write_json
from kitsune_benchmark.claude_harness import claude_environment
from kitsune_benchmark.full_native import agent_calls, published_tools
from kitsune_benchmark.runtime import codex_environment
from kitsune_benchmark.smoke import rewrite_json

BENCHMARK = "kitsune-codex-scripting-ab-v1"
HARNESS = "codex"  # The Claude wrapper selects the other subscription-only harness.
CATALOG_LIMIT = "MiniWoB catalog is server preflight only, not client inventory attestation."
UNAVAILABLE = ["model_requests", "first_request_input_tokens", "list_price_cost_usd"]
RUNNER_FILES = (Path(__file__), ROOT / "scripts/run-scripting-ab.py")


def model() -> str:
    models = {harness_pins(module.config(), HARNESS)[0] for module in (external, personal, gallery)}
    if len(models) != 1:
        raise ValueError(f"All tracks must use the same {HARNESS} model.")
    return models.pop()


def catalogs(project: str) -> dict:
    """No inference/browser: inspect each arm in an isolated Python process, not the client's catalog."""
    env = (claude_environment if HARNESS == "claude" else codex_environment)(resolve(HARNESS))
    code = "import asyncio,json; from kitsune.server import mcp; print(json.dumps([t.name for t in asyncio.run(mcp.list_tools())]))"
    result = {}
    for arm, settings in ab.ARMS.items():
        probe = subprocess.run(["uv", "run", "--locked", "--project", project, "python", "-c", code],
                               env={**env, **settings}, capture_output=True, text=True, check=True, timeout=60)
        result[arm] = sorted(json.loads(probe.stdout))
        if len(result[arm]) != ab.EXPECTED_TOOLS[arm]:
            raise ValueError(f"Unexpected {arm} server catalog: {len(result[arm])} tools")
        if ("browser_run_python" in result[arm]) != (settings.get("KITSUNE_SCRIPTING") == "1"):
            raise ValueError(f"Unexpected Python availability in {arm}")
    return result


def metrics(pair: dict) -> dict:
    result = pair["results"]["kitsune"]
    evaluation = result.get("benchmark_evaluation") or {}
    usage = result.get("usage") or {}
    calls = agent_calls(Path(result["run_dir"]) / "events.jsonl")
    python = [call for call in calls if call["tool"] == "browser_run_python"]
    scripts = [json.dumps(call["arguments"], ensure_ascii=False) for call in python]
    published = published_tools(Path(pair["pair_dir"]))
    row = {"scorable": evaluation.get("scorable") is True,
            "success": evaluation.get("task_success") is True,
            "execution_status": result.get("execution_status"),
            "input": usage.get("input_tokens"), "output": usage.get("output_tokens"),
            "cached_input": usage.get("cached_input_tokens"),
            "calls": result.get("mcp_calls"), "elapsed": result.get("elapsed_sec"),
            "run_dir": result["run_dir"], "pair_dir": pair["pair_dir"],
            "published": len(published) if published is not None else None,
            "tools": dict(Counter(call["tool"] for call in calls)),
            "tool_errors": dict(Counter(call["tool"] for call in calls if call["error"])),
            "python_calls": len(python), "python_errors": sum(bool(call["error"]) for call in python),
            "tamper_hits": sum(len(ab.TAMPER.findall(code)) for code in scripts),
            "python_urls": [url for code in scripts for url in ab.URL.findall(code)]}
    if HARNESS == "claude":
        observed = ab.metrics(pair)
        row.update({key: observed[key] for key in ("requests", "first_input", "cost")})
        row.update(relay_published=row["published"], published=observed["published"])
    return row


def unstarted(row: dict) -> bool:
    """A normal model finish without starting MiniWoB, not a harness/telemetry failure."""
    if row["track"] != "miniwob" or row["scorable"] or row["execution_status"] != "completed_unscored":
        return False
    try:
        grade = json.loads((Path(row["run_dir"]) / "evaluation.json").read_text())
    except (OSError, ValueError):
        return False
    return (grade.get("episode_starts") == 0 and grade.get("telemetry_errors") == 0
            and grade.get("outcome") == "no_terminal_reward")


def stop_reason(row: dict, continue_unstarted: bool = False) -> str | None:
    if row["execution_status"] != "completed_unscored" or not (row["scorable"] or
                                                              (continue_unstarted and unstarted(row))):
        return "execution error or unscorable run"
    if row["input"] is None or row["output"] is None:
        return "missing token usage"
    if HARNESS == "claude":
        if not row.get("requests") or row.get("first_input") is None or row.get("cost") is None:
            return "missing Claude request/cost metrics"
        if row["published"] != ab.EXPECTED_TOOLS[row["arm"]]:
            return "unexpected Claude init catalog"
        if row["track"] != "miniwob" and row.get("relay_published") != row["published"]:
            return "missing or inconsistent relay catalog"
    if row["published"] is None:
        if row["track"] != "miniwob":
            return "missing relay catalog"
    elif row["published"] != ab.EXPECTED_TOOLS[row["arm"]]:
        return "unexpected relay catalog"
    return None


def do_run(args) -> int:
    project = str(Path(args.kitsune_project).resolve())
    if ab.git(project, "rev-parse", "HEAD") != args.kitsune_sha or ab.git(project, "status", "--porcelain"):
        raise ValueError("Kitsune revision changed or dirty")
    manifest = {"benchmark": BENCHMARK, "harness": HARNESS, "model": model(), "effort": "medium",
                "kitsune_sha": args.kitsune_sha, "arms": ab.ARMS,
                "plan": ab.plan(), "catalog_preflight": catalogs(project),
                "unavailable_metrics": UNAVAILABLE,
                "catalog_limit": CATALOG_LIMIT,
                "runner_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RUNNER_FILES}}
    out = Path(args.out)
    rows = ab.load_log(out)
    path = out / "manifest.json"
    if path.exists():
        previous = json.loads(path.read_text())
        comparable = lambda m: {k: v for k, v in m.items() if k != "runner_sha256"}
        if previous != manifest and not (args.continue_unstarted and comparable(previous) == comparable(manifest)):
            raise ValueError("Output belongs to a different experiment; use a new --out")
    elif rows:
        raise ValueError(f"Existing rows have no {HARNESS.title()} manifest; use a new --out")
    done = set()
    for row in rows:
        if row.get("harness") != HARNESS or stop_reason(row, args.continue_unstarted):
            raise ValueError("Prior failed/incompatible run requires review, not automatic skipping")
        done.add(row["seq"])
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        write_json(path, manifest)
    if args.continue_unstarted:
        continuation = {"policy": "Preserve and count unstarted MiniWoB attempts; stop on other unscorable/errors.",
                        "original_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "runner_sha256": manifest["runner_sha256"]}
        continuation_path = out / "continuation.json"
        if continuation_path.exists():
            if json.loads(continuation_path.read_text()) != continuation:
                raise ValueError("Continuation runner changed; review before resuming")
        else:
            write_json(continuation_path, continuation)
    launched = 0
    for run in manifest["plan"]:
        if run["seq"] in done:
            continue
        if args.limit is not None and launched >= args.limit:
            break
        if ab.git(project, "rev-parse", "HEAD") != args.kitsune_sha or ab.git(project, "status", "--porcelain"):
            raise ValueError("Kitsune revision changed or dirty")
        print(f"[{run['seq']}/80] {run['track']} {run['task']} r{run['repeat']} {run['arm']}", flush=True)
        pair = ab.run_one(run, project, BENCHMARK, harness=HARNESS)
        row = {**run, "harness": HARNESS, "model": manifest["model"], **metrics(pair)}
        with (out / "runs.jsonl").open("a") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        launched += 1
        print(f"    success={row['success']} input={row['input']} calls={row['calls']} "
              f"published={row['published']} python={row['python_calls']} errors={row['python_errors']}", flush=True)
        reason = stop_reason(row, args.continue_unstarted)
        if unstarted(row):
            print("    unstarted attempt retained (raw grade remains unscorable)", flush=True)
        if ab.git(project, "rev-parse", "HEAD") != args.kitsune_sha or ab.git(project, "status", "--porcelain"):
            reason = "Kitsune revision changed or dirty"
        if reason:
            print(f"stop: {reason}; inspect {row['run_dir']}", file=sys.stderr)
            return 2
    return 0


def analyze(out: Path) -> dict:
    baseline, candidate = ab.ARMS
    rows = ab.load_log(out)
    report = {"runs": len(rows), "harness": HARNESS, "unavailable_metrics": UNAVAILABLE, "tracks": {}}
    measured = ("input", "output", "calls", "elapsed") + (("requests", "cost") if HARNESS == "claude" else ())
    for track in ("miniwob", "personal", "gallery", "all"):
        sub = [r for r in rows if track == "all" or r["track"] == track]
        arms = {}
        for arm in ab.ARMS:
            selected = [r for r in sub if r["arm"] == arm]
            arms[arm] = {"runs": len(selected), "scorable": sum(r["scorable"] for r in selected),
                         "unstarted": sum(unstarted(r) for r in selected),
                         "successes": sum(r["success"] for r in selected),
                         **{k: round(sum(r[k] or 0 for r in selected), 3) for k in
                            (*measured, "cached_input", "python_calls", "python_errors")}}
            if HARNESS == "claude":
                first = [r["first_input"] for r in selected if r["first_input"] is not None]
                arms[arm]["first_input_median"] = statistics.median(first) if first else None
        by = defaultdict(dict)
        for row in sub:
            by[(row["task"], row["repeat"])][row["arm"]] = row
        joint = [v for v in by.values() if all(v.get(arm, {}).get("scorable") and
                                             v[arm]["success"] for arm in ab.ARMS)]
        report["tracks"][track] = {"arms": arms, "joint_cells": len(joint),
            **{f"joint_{k}_ratio": ab.ratio(sum(v[candidate][k] for v in joint),
                                           sum(v[baseline][k] for v in joint))
               for k in measured}}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--kitsune-project", required=True)
    run.add_argument("--kitsune-sha", required=True)
    run.add_argument("--limit", type=int, help="Run at most N additional cells, then resume with the same --out")
    run.add_argument("--continue-unstarted", action="store_true",
                     help="Explicitly retain zero-start MiniWoB attempts and continue; other errors still stop")
    for child in (run, sub.add_parser("analyze")):
        child.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.cmd == "run":
        if args.limit is not None and args.limit <= 0:
            parser.error("--limit must be positive")
        try:
            return do_run(args)
        except Exception as error:
            print(f"stop: {type(error).__name__}: {error}", file=sys.stderr)
            return 2
    report = analyze(Path(args.out))
    rewrite_json(Path(args.out) / "analysis.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
