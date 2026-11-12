"""Offline audit of the frozen code-first cohort; never starts a browser or a model.

Writes bounded public metrics plus a private script transcript for manual review. Pattern
flags locate code to review; they are not a sandbox, UI-only compliance or safety proof.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("code_first", ROOT / "scripts/run-code-first-five-way.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
five = experiment.five


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    out = args.out
    rows = five.suite.ab.load_log(out)
    assert len(rows) == 70 and all(r["scorable"] for r in rows)
    frozen = json.loads((out / "catalog-preflight.json").read_text())
    post = json.loads((out / "postflight/catalog-preflight.json").read_text())
    assert frozen == post, "global catalog/vendor drift"
    tool_counts = defaultdict(Counter)
    flags, transcript = [], []
    init_models, auth, finished_models = set(), set(), set()
    checks, call_count = 0, 0
    spaces = {}
    by = defaultdict(dict)
    for row in rows:
        arm, seq = row["arm"], row["seq"]
        by[row["task"], row["repeat"]][arm] = row
        expected = frozen["catalogs"][arm]
        for when in ("before", "after"):
            captured = json.loads((out / "catalogs" / f"{seq:03d}-{when}.json").read_text())
            assert captured[arm] == expected, (seq, when)
        assert five.observed_catalog(row["pair_dir"]) == expected, seq
        metadata = [json.loads(s) for s in (Path(row["pair_dir"]) / "catalog-metadata.jsonl").read_text().splitlines()]
        for item in metadata:
            if item["method"] == "tools/list":
                listing = item["response"]["result"]
                assert not listing.get("nextCursor"), seq
                assert sorted(listing["tools"], key=lambda t: t["name"]) == expected["tools"], seq
                checks += 1
        evaluation = json.loads((Path(row["run_dir"]) / "evaluation.json").read_text())
        assert (evaluation["page_loads"], evaluation["episode_starts"], evaluation["telemetry_errors"]) == (1, 1, 0), seq
        assert evaluation["official_reward"]["done"] and evaluation["task_success"] == row["success"], seq
        events_path = Path(row["run_dir"]) / "events.jsonl"
        events = [json.loads(s) for s in events_path.read_text().splitlines()]
        for event in events:
            if event.get("type") == "system" and event.get("subtype") == "init":
                init_models.add(event["model"])
                auth.add(event.get("apiKeySource"))
            if event.get("type") == "result":
                finished_models.update(event.get("modelUsage", {}))
                assert not event.get("subagent_stats", {}).get("spawned", 0), seq
                assert not event.get("is_error"), seq
            if event.get("type") == "rate_limit_event":
                assert not event.get("rate_limit_info", {}).get("isUsingOverage"), seq
        calls = five.agent_calls(events_path)
        assert len(calls) == row["calls"] and all(c["error"] is not None and c["listed"] for c in calls), seq
        call_count += len(calls)
        if arm == "ego":
            ids = set(re.findall(r'space "bm-code-first-20261112-v2-\d+"\((\d+)\)', "\n".join(c["text"] for c in calls)))
            assert len(ids) == 1, (seq, ids)
            spaces[seq] = ids.pop()
        if arm == "aside":
            assert "openTab(" in calls[0]["arguments"]["code"] and "Opened a new tab" in calls[0]["text"], seq
        for index, call in enumerate(calls, 1):
            tool_counts[arm][call["tool"]] += 1
            code = json.dumps(call["arguments"], ensure_ascii=False)
            if call["tool"] in five.SCRIPT_TOOLS or call["error"]:
                transcript.append(f"\n### seq {seq} {arm} {row['task']} r{row['repeat']} call {index}, error={call['error']}\n{code}\n")
                if call["error"] or row["task"] == "mw-book-flight":
                    transcript.append("RESULT:\n" + call["text"] + "\n")
            if five.PAGE_JS.search(code) or five.REWARD.search(code) or call["error"]:
                flags.append({"seq": seq, "arm": arm, "task": row["task"], "call": index,
                              "error": call["error"], "page_js": bool(five.PAGE_JS.search(code))})
    assert len(spaces) == len(set(spaces.values())) == 14, "TaskSpace reuse"
    arms = list(five.ARMS)
    assert len(by) == 14 and all(set(v) == set(arms) for v in by.values()), "missing or duplicate cells"
    assert init_models == finished_models == {"claude-opus-5-5"}, "model drift"
    assert auth == {"none"}, "unexpected API key source"
    joint = [v for v in by.values() if all(v[a]["success"] for a in arms)]
    sums = lambda cells, arm: {key: sum(v[arm][key] for v in cells)
                              for key in ("input", "output", "requests", "calls", "elapsed", "cost")}
    tasks = {}
    for task in five.suite.ab.MINIWOB:
        cells = [v for (name, _), v in by.items() if name == task]
        tasks[task] = {arm: sums(cells, arm) for arm in arms}
    deltas = [{key: v["kitsune-code-first"][key] / v["kitsune-default"][key]
               for key in ("input", "elapsed", "calls", "requests")} for v in by.values()]
    sensitivity = {}
    for arm in ("ego", "aside"):
        cells = [v for v in by.values() if v[arm]["success"] and not v[arm]["page_js_hits"]]
        sensitivity[arm] = {"cells": len(cells), "code_first": sums(cells, "kitsune-code-first"), "vendor": sums(cells, arm)}
    report = {"rows_sha256": hashlib.sha256((out / "runs.jsonl").read_bytes()).hexdigest(),
              "catalog_rows_checked": len(rows), "tools_list_replies_checked": checks,
              "calls_checked": call_count, "ego_task_spaces": spaces,
              "page_js_attempts": dict(Counter(r["arm"] for r in rows if r["page_js_hits"])),
              "init_models": sorted(init_models), "result_models": sorted(finished_models),
              "auth_sources": sorted(auth), "tool_counts": dict(tool_counts), "flags": flags,
              "joint_cells": len(joint), "joint_totals": {arm: sums(joint, arm) for arm in arms},
              "per_task": tasks, "page_js_excluded_sensitivity": sensitivity,
              "code_first_vs_default_cellwise": {key: {"wins": sum(d[key] < 1 for d in deltas),
                                                        "median_ratio": statistics.median(d[key] for d in deltas),
                                                        "min_ratio": min(d[key] for d in deltas),
                                                        "max_ratio": max(d[key] for d in deltas)}
                                                    for key in deltas[0]}}
    (out / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "script-review.txt").write_text("".join(transcript))
    print(json.dumps({k: v for k, v in report.items() if k not in ("per_task", "flags")}, indent=2))


if __name__ == "__main__":
    main()
