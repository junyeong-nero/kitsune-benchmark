"""Offline analysis of the preregistered disclosure experiment; no model calls."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import random
import statistics

READS = {"browser_tabs", "browser_snapshot", "browser_page_text", "browser_forms", "browser_dom",
         "browser_find", "browser_page_info", "browser_screenshot"}


def read_only(call):
    name = call["name"].split("__")[-1]
    return name in READS and (name != "browser_tabs" or call["input"].get("action", "list") == "list")


def trace(path):
    requests = {}
    calls = {}
    failed = set()
    stats = collections.Counter()
    errors = collections.Counter()
    timeout_conditions = collections.Counter()
    for line in path.read_text().splitlines():
        event = json.loads(line)
        message = event.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        if event.get("type") == "assistant":
            req = requests.setdefault(message["id"], {})
            for item in content:
                if item.get("type") == "tool_use":
                    req[item["id"]] = item
                    calls[item["id"]] = item
        for item in content:
            if item.get("type") != "tool_result":
                continue
            raw = item.get("content", "")
            text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            stats["delivered_result_bytes"] += len(text.encode())
            if not item.get("is_error"):
                continue
            failed.add(item.get("tool_use_id"))
            try:
                payload = json.loads(raw) if isinstance(raw, str) else {}
            except ValueError:
                payload = {}
            error = payload.get("error", "") if isinstance(payload, dict) else ""
            if "Expected outcome not observed" in error:
                category = "outcome_timeout"
                expectation = calls.get(item.get("tool_use_id"), {}).get("input", {}).get("expect", {})
                timeout_conditions[",".join(sorted(k for k in expectation if k != "timeout"))] += 1
                if "value" in expectation:
                    found = payload.get("outcome", {}).get("observed", {}).get("found")
                    stats["value_wait_missing"] += found is False
                    stats["value_wait_found"] += found is True
            elif "expect" in error.lower():
                category = "expect_validation"
            elif "stale ref" in text or "not found" in text.lower():
                category = "target_or_ref"
            else:
                category = "other"
            errors[category] += 1
            stats["stale_ref_errors"] += "stale ref" in text
    previous = None
    for req in requests.values():
        items = list(req.values())
        is_read = bool(items) and all(read_only(c) for c in items)
        has_error = any(c["id"] in failed for c in items)
        stats["trace_requests"] += 1
        stats["multi_tool_requests"] += len(items) > 1
        if previous:
            stats["request_after_error"] += previous[1]
            stats["consecutive_reads"] += is_read and previous[0]
            stats["read_after_nonread"] += is_read and not previous[0]
        previous = (is_read, has_error)
        for c in items:
            args = c["input"]
            stats["expect_uses"] += bool(args.get("expect"))
            name = c["name"].split("__")[-1]
            stats["read_calls"] += read_only(c)
            stats["page_text_calls"] += name == "browser_page_text"
            stats["snapshot_calls"] += name == "browser_snapshot"
            stats["disclosure_decisions"] += name in {"browser_snapshot", "browser_page_text"} or (name == "browser_tabs" and args.get("action", "list") == "list")
    for key in ("expect_validation", "outcome_timeout", "target_or_ref", "other"):
        stats["errors_" + key] = errors[key]
    return {**stats, "timeout_conditions": dict(timeout_conditions)}


def run_metrics(entry):
    r = entry["pair"]["results"]["kitsune"]
    e = r["benchmark_evaluation"]
    a = r["token_attribution"]
    result = {k: entry[k] for k in ("arm", "task", "repeat", "position", "block")}
    result.update(scorable=e["scorable"], success=e["task_success"], functional=e["functional_success"],
                  safety=e["safety_pass"], v1=e["contracts"]["v1_strict_close"]["task_success"],
                  v2=e["contracts"]["v2_agent_tab_cleanup"]["task_success"],
                  input=r["usage"]["input_tokens"], output=r["usage"]["output_tokens"],
                  cached=r["usage"]["cached_input_tokens"], requests=a["requests"],
                  prefix=a["prefix_x_requests_tokens"], history=a["history_tokens"],
                  first_input=a["first_request_input_tokens"], calls=r["mcp_calls"],
                  failed_calls=r["failed_mcp_calls"], elapsed=r["elapsed_sec"],
                  cost=r["list_price_cost_usd"], harness_sec=e["harness_seconds"],
                  native_agent_sec=0.0, enrichment_sec=0.0, enrichment_calls=0,
                  enrichment_failures=0, overrides=0, pair_dir=entry["pair"]["pair_dir"])
    result.update(trace(Path(r["run_dir"]) / "events.jsonl"))
    for line in (Path(entry["pair"]["pair_dir"]) / "kitsune-native-rpc.jsonl").read_text().splitlines():
        x = json.loads(line)
        if x["kind"] == "disclosure_override":
            result["overrides"] += 1
        if x["kind"] == "disclosure_delivered":
            result["enrichment_failures"] += x["supplement_failed"]
        if x["kind"] != "rpc_completed" or x.get("method") != "tools/call":
            continue
        if x["role"] == "agent":
            result["native_agent_sec"] += x["duration_sec"]
        if x["role"] == "disclosure":
            result["enrichment_sec"] += x["duration_sec"]
            result["enrichment_calls"] += 1
    assert result["requests"] == result["trace_requests"], "Request count mismatch"
    return result


METRICS = ("input", "output", "requests", "calls", "elapsed", "cost", "delivered_result_bytes",
           "first_input", "prefix", "history", "multi_tool_requests", "consecutive_reads",
           "read_after_nonread", "request_after_error", "expect_uses", "errors_expect_validation",
           "errors_outcome_timeout", "failed_calls", "harness_sec", "native_agent_sec",
           "enrichment_sec", "enrichment_calls", "enrichment_failures", "disclosure_decisions",
           "stale_ref_errors", "value_wait_missing", "value_wait_found")


def aggregate(runs):
    conditions = collections.Counter()
    for run in runs:
        conditions.update(run.get("timeout_conditions", {}))
    return {"timeout_conditions": dict(conditions), "n": len(runs), "success": sum(x["success"] for x in runs),
            "functional": sum(x["functional"] for x in runs), "safety_failures": sum(not x["safety"] for x in runs),
            "v1": sum(x["v1"] for x in runs), "v2": sum(x["v2"] for x in runs),
            **{k: sum(x.get(k, 0) for x in runs) for k in METRICS}}


def paired(rows, left, right):
    lookup = {(r["block"], r["arm"]): r for r in rows}
    pairs = [(r, lookup[r["block"], right]) for r in rows if r["arm"] == left and (r["block"], right) in lookup]
    output = {}
    for scope, selected in (("all", pairs), ("joint_success", [(a, b) for a, b in pairs if a["success"] and b["success"]])):
        metrics = {}
        for metric in ("requests", "input", "elapsed", "cost"):
            before = sum(a[metric] for a, b in selected)
            after = sum(b[metric] for a, b in selected)
            metrics[metric] = {"before": before, "after": after, "pct": (after / before - 1) * 100 if before else None,
                               "improved_blocks": sum(b[metric] < a[metric] for a, b in selected),
                               "tied_blocks": sum(b[metric] == a[metric] for a, b in selected),
                               "median_paired_delta": statistics.median(b[metric] - a[metric] for a, b in selected) if selected else None}
        output[scope] = {"blocks": len(selected), "metrics": metrics}
    # Resample task clusters (all repetitions together), not independent run observations.
    # Exploratory percentile intervals only: six selected tasks is a very small sample.
    clusters = sorted({a["task"] for a, b in pairs})
    rng = random.Random(20261022)
    intervals = {}
    for metric in ("requests", "input", "elapsed", "cost"):
        totals = {task: (sum(a[metric] for a, b in pairs if a["task"] == task),
                         sum(b[metric] for a, b in pairs if a["task"] == task)) for task in clusters}
        draws = []
        for _ in range(5000):
            sample = rng.choices(clusters, k=len(clusters))
            a = sum(totals[t][0] for t in sample)
            b = sum(totals[t][1] for t in sample)
            draws.append((b/a - 1)*100)
        draws.sort()
        intervals[metric] = [draws[125], draws[4874]]
    output["task_cluster_bootstrap_pct_95"] = intervals
    output["per_task"] = {task: {m: sum(b[m] - a[m] for a, b in pairs if a["task"] == task)
                                 for m in ("requests", "input", "elapsed", "cost")}
                          for task in clusters}
    return output


def analyze(path):
    summary = json.loads(path.read_text())
    rows = [run_metrics(e) for e in summary["runs"]]
    return {"source": str(path), "state": summary["state"], "rows": rows,
            "arms": {arm: aggregate([r for r in rows if r["arm"] == arm]) for arm in "ABCD"},
            "contrasts": {f"{a}->{b}": paired(rows, a, b) for a, b in (("A", "B"), ("C", "D"), ("A", "C"), ("B", "D"))},
            "combined_secondary_A_to_D": paired(rows, "A", "D")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.summary.resolve())
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({"arms": result["arms"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
