"""Per-tool comparison of Playwright and Kitsune agent calls in a full-suite output directory. No model/browser calls.

Kitsune v0.3.1 publishes Playwright MCP's tool names, so each tool is compared name for name: agent calls, errors,
latency (native RPC duration), response size, and grouped error texts from the model-visible tool results.

usage: uv run --locked python scripts/analyze-per-tool.py artifacts/opus-full-v0.3.1 [--json out.json]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.cost_metrics import aggregate_costs, load_pair_resource_phases, run_timing

TARGETS = ("playwright", "kitsune")


def pairs(suite_dir: Path):
    for line in (suite_dir / "suite-log.jsonl").read_text().splitlines():
        entry = json.loads(line)
        path = entry.get("suite_summary_path")
        if not path:
            continue
        summary = json.loads(Path(path).read_text())
        for pair in summary.get("pairs", []):
            yield entry["name"], pair


def error_text(block) -> str:
    raw = block.get("content", "")
    if isinstance(raw, list):
        raw = " ".join(item.get("text", "") for item in raw if isinstance(item, dict))
    text = re.sub(r"\s+", " ", str(raw))
    text = re.sub(r"\be\d+\b", "eN", text)  # snapshot refs
    text = re.sub(r"\d+", "N", text)
    return text[:160]


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def cost_report(recorded_pairs) -> dict:
    grouped = collections.defaultdict(list)
    for track, pair in recorded_pairs:
        pair = load_pair_resource_phases(pair)
        pair = {**pair, "results": {t: {**r, "timing": r.get("timing") or run_timing(Path(pair["pair_dir"]), t, r)}
                                    for t, r in pair["results"].items()}}
        grouped[track.rsplit("-v", 1)[0]].append(pair)
    # Parallel targets have separate fixtures, not a paired same-success trial.
    return {group: aggregate_costs(items) for group, items in grouped.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite_dir", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    stats = collections.defaultdict(lambda: {"calls": 0, "errors": 0, "durations": [], "chars": [],
                                             "runs": set(), "error_texts": collections.Counter()})
    outcomes = collections.defaultdict(lambda: collections.Counter())
    failures = []
    recorded_pairs = list(pairs(args.suite_dir))
    for track, pair in recorded_pairs:
        task = pair.get("personal_task") or pair.get("gallery_task") or "miniwob"
        group = track.rsplit("-v", 1)[0]
        for target in TARGETS:
            run = pair.get("results", {}).get(target)
            if not run:
                continue
            evaluation = run.get("benchmark_evaluation") or {}
            success = evaluation.get("task_success")
            outcomes[group][(target, success)] += 1
            if success is False:
                failed = [key for key, value in evaluation.items() if value is False and key != "task_success"]
                failures.append({"track": track, "task": task, "target": target, "failed_checks": failed,
                                 "reason": evaluation.get("failure_reason") or evaluation.get("reason"),
                                 "run_dir": run["run_dir"]})
            rpc = Path(pair["pair_dir"]) / f"{target}-native-rpc.jsonl"
            if rpc.exists():
                for line in rpc.read_text().splitlines():
                    event = json.loads(line)
                    if event.get("kind") != "rpc_completed" or event.get("role") != "agent" or not event.get("tool"):
                        continue
                    s = stats[(target, event["tool"])]
                    s["durations"].append(event["duration_sec"])
                    s["chars"].append(event.get("response_text_chars") or 0)
            events = Path(run["run_dir"]) / "events.jsonl"
            names = {}
            for line in events.read_text().splitlines():
                event = json.loads(line)
                content = event.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if block.get("type") == "tool_use":
                        names[block["id"]] = block["name"].split("__")[-1]
                    elif block.get("type") == "tool_result" and block.get("tool_use_id") in names:
                        s = stats[(target, names[block["tool_use_id"]])]
                        s["calls"] += 1
                        s["runs"].add(run["run_dir"])
                        if block.get("is_error"):
                            s["errors"] += 1
                            s["error_texts"][error_text(block)] += 1
    tools = sorted({name for _, name in stats}, key=lambda n: -sum(stats[(t, n)]["calls"] for t in TARGETS))
    report = {"outcomes": {group: {f"{t}:{s}": n for (t, s), n in counts.items()} for group, counts in outcomes.items()},
              "cost_metrics": cost_report(recorded_pairs), "failures": failures, "tools": {}}
    print(f"{'tool':28} {'target':10} {'calls':>6} {'runs':>5} {'err%':>6} {'p50 s':>7} {'p90 s':>7} {'p50 ch':>7} {'mean ch':>8}")
    for name in tools:
        for target in TARGETS:
            s = stats[(target, name)]
            row = {"calls": s["calls"], "runs": len(s["runs"]), "errors": s["errors"],
                   "error_rate": s["errors"] / s["calls"] if s["calls"] else None,
                   "p50_sec": percentile(s["durations"], 0.5), "p90_sec": percentile(s["durations"], 0.9),
                   "p50_chars": percentile(s["chars"], 0.5),
                   "mean_chars": statistics.fmean(s["chars"]) if s["chars"] else None,
                   "top_errors": s["error_texts"].most_common(6)}
            report["tools"].setdefault(name, {})[target] = row
            fmt = lambda v, f: format(v, f) if v is not None else "-"
            print(f"{name:28} {target:10} {row['calls']:6} {row['runs']:5} "
                  f"{fmt(row['error_rate'] and 100 * row['error_rate'], '6.1f')} {fmt(row['p50_sec'], '7.2f')} "
                  f"{fmt(row['p90_sec'], '7.2f')} {fmt(row['p50_chars'], '7')} {fmt(row['mean_chars'], '8.0f')}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
