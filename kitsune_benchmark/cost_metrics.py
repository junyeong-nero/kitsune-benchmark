"""Coverage-aware cost summaries for recorded synthetic task attempts."""
from __future__ import annotations

import json
from pathlib import Path


USAGE_KEYS = ("input_tokens", "uncached_input_tokens", "cached_input_tokens",
              "cache_creation_input_tokens", "output_tokens")


def normalized_usage(run: dict) -> dict:
    usage = dict(run.get("usage") or {})
    if usage.get("uncached_input_tokens") is None and all(
            usage.get(key) is not None for key in ("input_tokens", "cached_input_tokens")):
        usage["uncached_input_tokens"] = (usage["input_tokens"] - usage["cached_input_tokens"]
                                           - (usage.get("cache_creation_input_tokens") or 0))
    return usage


def total(values: list) -> dict:
    reported = [v for v in values if v is not None]
    return {"total": sum(reported) if reported else None,
            "reported_runs": len(reported), "missing_runs": len(values) - len(reported)}


def resource_cost(buckets: list[dict | None]) -> dict:
    def values(key):
        return [b.get(key) if b else None for b in buckets]
    cpu = [b["observed_cpu_user_sec"] + b["observed_cpu_system_sec"]
           if b and all(b.get(k) is not None for k in ("observed_cpu_user_sec", "observed_cpu_system_sec"))
           else None for b in buckets]
    peaks = [v for v in values("sampled_peak_rss_bytes") if v is not None]
    weighted = [(b["time_weighted_mean_rss_bytes"], b["duration_sec"]) for b in buckets
                if b and b.get("time_weighted_mean_rss_bytes") is not None and b.get("duration_sec", 0) > 0]
    duration = sum(d for _, d in weighted)
    cpu_total = total(cpu)
    return {"attempted": len(buckets), "duration_sec": total(values("duration_sec")),
            "runs_with_resources": sum(b is not None for b in buckets),
            "runs_missing_resources": sum(b is None for b in buckets),
            "observed_cpu_sec": cpu_total,
            "observed_cpu_sec_per_measured_task": cpu_total["total"] / cpu_total["reported_runs"]
                if cpu_total["reported_runs"] else None,
            "sampled_peak_rss_bytes": max(peaks) if peaks else None,
            "mean_task_sampled_peak_rss_bytes": sum(peaks) / len(peaks) if peaks else None,
            "runs_with_peak_rss": len(peaks),
            "time_weighted_mean_rss_bytes": sum(m * d for m, d in weighted) / duration if duration else None,
            "rss_observed_duration_sec": duration if weighted else None,
            "runs_with_mean_rss": len(weighted)}


def attempt_cost(runs: list[dict]) -> dict:
    usage = [normalized_usage(r) for r in runs]
    return {"attempted": len(runs),
            "usage": {key: total([u.get(key) for u in usage])
                      for key in sorted(set(USAGE_KEYS) | {k for u in usage for k in u})},
            "elapsed_sec": total([r.get("elapsed_sec") for r in runs]),
            "timing": {key: total([(r.get("timing") or {}).get(key) for r in runs])
                       for key in ("relay_setup_sec", "elapsed_minus_relay_setup_sec", "agent_native_rpc_sec")},
            "resources_task": resource_cost([(r.get("resources") or {}).get("task") for r in runs])}


def successful(run: dict) -> bool:
    evaluation = run.get("benchmark_evaluation") or {}
    return bool(evaluation.get("scorable") and evaluation.get("task_success") is True)


def aggregate_costs(pairs: list[dict]) -> dict:
    result = {}
    paired_attempts = sum(all(t in p["results"] for t in ("playwright", "kitsune")) for p in pairs)
    for target in ("playwright", "kitsune"):
        runs = [p["results"][target] for p in pairs if target in p["results"]]
        successes = [r for r in runs if successful(r)]
        same = [p["results"][target] for p in pairs if all(
            t in p["results"] and successful(p["results"][t]) for t in ("playwright", "kitsune"))]
        failed = [r for r in runs if (r.get("benchmark_evaluation") or {}).get("task_success") is False]
        unknown = [r for r in runs if not successful(r)
                   and (r.get("benchmark_evaluation") or {}).get("task_success") is not False]
        lifecycle_pairs = [p for p in pairs if target in p["results"] or (
            target == "kitsune" and (p.get("timing") or {}).get("kitsune_cold_start_setup_sec") is not None)]
        phases = [p.get("resource_phases", {}).get(target, {}) for p in lifecycle_pairs]
        result[target] = {"paired_attempts": paired_attempts,
                          "all_attempts": attempt_cost(runs), "successful_tasks": attempt_cost(successes),
                          "same_successful_tasks": attempt_cost(same), "failed_attempts": attempt_cost(failed),
                          "unscored_or_unknown_attempts": attempt_cost(unknown),
                          "pair_lifecycle": {
                              "cold_start_setup_elapsed_sec": total([
                                  (p.get("timing") or {}).get("kitsune_cold_start_setup_sec") if target == "kitsune" else None
                                  for p in lifecycle_pairs]),
                              **{phase: resource_cost([p.get(phase) for p in phases]) for phase in ("setup", "ready")}},
                          "user_interventions": {"count": 0, "status": "none_by_protocol"}}
    return result


def pair_resource_phases(summary: dict, targets) -> dict:
    metrics = summary.get("metrics", {})
    return {target: {phase: metrics.get(f"phase/{phase}/owner/{target}")
                     for phase in ("setup", "ready")} for target in targets}


def run_timing(directory: Path, target: str, run: dict) -> dict:
    path = directory / f"{target}-native-rpc.jsonl"
    records = []
    if path.is_file():
        for line in path.read_text().splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    setup = next((r["duration_sec"] for r in records if r.get("kind") == "setup_completed"), None)
    elapsed = run.get("elapsed_sec")
    return {"relay_setup_sec": setup,
            "elapsed_minus_relay_setup_sec": elapsed - setup if elapsed is not None and setup is not None else None,
            "agent_native_rpc_sec": sum(r["duration_sec"] for r in records if r.get("kind") == "rpc_completed"
                                         and r.get("role") == "agent" and r.get("method") == "tools/call")
                if records else None}


def load_pair_resource_phases(pair: dict) -> dict:
    if "resource_phases" in pair:
        return pair
    path = pair.get("resource_summary_path")
    if path and Path(path).is_file():
        targets = set(pair["results"])
        if (pair.get("timing") or {}).get("kitsune_cold_start_setup_sec") is not None:
            targets.add("kitsune")
        return {**pair, "resource_phases": pair_resource_phases(json.loads(Path(path).read_text()), targets)}
    return pair
