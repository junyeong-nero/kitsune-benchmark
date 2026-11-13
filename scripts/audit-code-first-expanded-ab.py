"""Offline audit of the interrupted expanded A/B; never runs a browser or model.

Keep missing final usage missing, retain the timeout, and expose matched denominators.
Private transcripts support manual review; pattern scans do not certify UI-only behavior.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("expanded_audit", ROOT / "scripts/run-code-first-expanded-ab.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
five = experiment.five


def coverage(rows):
    return {key: {"known_total": sum(r[key] for r in rows if r.get(key) is not None),
                  "reported_attempts": sum(r.get(key) is not None for r in rows),
                  "missing_attempts": sum(r.get(key) is None for r in rows)}
            for key in ("input", "cached_input", "output", "cost", "elapsed", "calls", "requests")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    out = parser.parse_args().out
    rows = five.suite.ab.load_log(out)
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(manifest["plan"]) == 120 and len(rows) == 85
    assert manifest["kitsune_shas"] == five.SHAS
    assert manifest["runner_sha256"] == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in five.RUNNER_FILES}
    assert manifest["catalog_preflight_sha256"] == hashlib.sha256(
        (out / "catalog-preflight.json").read_bytes()).hexdigest()
    assert all(all(row[k] == value for k, value in planned.items())
               for row, planned in zip(rows, manifest["plan"]))
    assert all(r["scorable"] and r["success"] and r["input"] is not None for r in rows[:-1])
    assert rows[-1]["execution_status"] == "timeout" and rows[-1]["input"] is None
    frozen = json.loads((out / "catalog-preflight.json").read_text())
    assert frozen == json.loads((out / "postflight/catalog-preflight.json").read_text())
    replies = 0
    calls_count = Counter()
    errors, handoffs, flags, transcript = [], [], [], []
    result_models, init_models = set(), set()
    for row in rows:
        arm, seq = row["arm"], row["seq"]
        expected = frozen["catalogs"][arm]
        for when in ("before", "after"):
            captured = json.loads((out / "catalogs" / f"{seq:03d}-{when}.json").read_text())
            assert captured[arm] == expected, (seq, when)
        assert five.observed_catalog(row["pair_dir"]) == expected, seq
        for item in map(json.loads, (Path(row["pair_dir"]) / "catalog-metadata.jsonl").read_text().splitlines()):
            if item["method"] == "tools/list":
                listing = item["response"]["result"]
                assert not listing.get("nextCursor"), seq
                assert sorted(listing["tools"], key=lambda t: t["name"]) == expected["tools"], seq
                replies += 1
        path = Path(row["run_dir"]) / "events.jsonl"
        for event in map(json.loads, path.read_text().splitlines()):
            if event.get("type") == "system" and event.get("subtype") == "init":
                init_models.add(event["model"])
                assert event.get("apiKeySource") == "none", seq
            if event.get("type") == "result":
                result_models.update(event["modelUsage"])
                assert not event.get("is_error") and not event.get("subagent_stats", {}).get("spawned"), seq
            if event.get("type") == "rate_limit_event":
                assert not event.get("rate_limit_info", {}).get("isUsingOverage"), seq
        calls = five.agent_calls(path)
        assert len(calls) == row["calls"] and all(c["listed"] and c["error"] is not None for c in calls), seq
        calls_count[arm] += len(calls)
        for index, call in enumerate(calls, 1):
            name, args = call["tool"], call["arguments"]
            encoded = json.dumps(args, ensure_ascii=False)
            summary = {"seq": seq, "unit": row["unit"], "arm": arm, "call": index, "tool": name}
            if call["error"]:
                errors.append({**summary, "arguments": args, "result": call["text"]})
            if name == "browser_tabs" and args.get("action") == "request":
                handoffs.append({**summary, "error": call["error"], "result": call["text"]})
            if five.PAGE_JS.search(encoded) or five.REWARD.search(encoded):
                flags.append({**summary, "arguments": args})
            # All calls, not just scripts: direct tools can bypass readonly controls too.
            transcript.append(f"\n### {seq} {row['unit']} {arm} call {index}: {name}, error={call['error']}\n{encoded}\n")
            if call["error"]:
                transcript.append(call["text"] + "\n")
        grade = json.loads((Path(row["run_dir"]) / "evaluation.json").read_text())
        assert grade["task_success"] == row["grade_success"], seq
        if row["track"] != "miniwob" and row["scorable"]:
            assert grade["safety_pass"] is True, seq
        elif row["track"] == "miniwob":
            assert (grade["page_loads"], grade["episode_starts"], grade["telemetry_errors"]) == (1, 1, 0), seq
    assert init_models == result_models == {"claude-opus-5-5"}
    request_cells = {(r["unit"], r["repeat"]) for r in rows if any(h["seq"] == r["seq"] for h in handoffs)}
    page_js_cells = {(r["unit"], r["repeat"]) for r in rows if r["page_js_hits"]}
    primary = [r for r in rows if r["track"] != "miniwob"]
    report = {"rows_sha256": hashlib.sha256((out / "runs.jsonl").read_bytes()).hexdigest(),
              "execution_commit": manifest["benchmark_sha"], "attempts": len(rows), "scorable": 84,
              "unattempted": 120 - len(rows), "catalog_replies_checked": replies,
              "calls_checked": dict(calls_count), "init_models": sorted(init_models),
              "result_models": sorted(result_models),
              "usage_coverage": {arm: coverage([r for r in rows if r["arm"] == arm]) for arm in five.ARMS},
              "first_repeat_primary": experiment.compare([r for r in primary if r["repeat"] == 0]),
              "no_handoff_request_sensitivity": experiment.compare(
                  [r for r in primary if (r["unit"], r["repeat"]) not in request_cells]),
              "no_page_js_sensitivity": experiment.compare(
                  [r for r in primary if (r["unit"], r["repeat"]) not in page_js_cells]),
              "handoff_calls": handoffs, "page_js_flags": flags, "errors": errors}
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (out / "call-review.txt").write_text("".join(transcript))
    print(json.dumps({k: v for k, v in report.items() if k not in (
        "first_repeat_primary", "no_handoff_request_sensitivity", "no_page_js_sensitivity", "errors", "handoff_calls", "page_js_flags")}, indent=2))
    for name in ("first_repeat_primary", "no_handoff_request_sensitivity", "no_page_js_sensitivity"):
        print(name, report[name]["joint_cells"], report[name]["joint_ratios"])
    print("handoff calls", len(handoffs), "reported errors", len(errors), "page-JS flagged calls", len(flags))


if __name__ == "__main__":
    main()
