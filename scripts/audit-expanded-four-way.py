"""Offline integrity audit of the completed 184-attempt Codex cohort.

No browser/model calls. Pattern flags and deduplicated transcripts support manual
review, not a confinement or safety certificate. Frozen execution files are unchanged.
"""
import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import re

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("four_audit", ROOT / "scripts/run-expanded-four-way.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
from kitsune_benchmark.audit import audit_events
from kitsune_benchmark.cost_metrics import run_timing

ROWS_SHA256 = "5ec7b52f3455d02ec74c03ebb465edc23e98e2b9abfb4c8349c1f25a0dd7acc8"
EXECUTION_SHA = "e5db230a78ad006cfb8a12fbee6621b087a03e07"
REVIEW = re.compile(r"\.evaluate\s*\(|\.cdp\s*\(|Runtime\.|\b(?:eval|exec|fetch|require|open)\s*\("
                    r"|\b(?:import|__import__|subprocess|process\.|requests\.|readFile|writeFile|document\.|window\.)"
                    r"|reward|grader|readonly|readOnly|listBrowserTabs|attachTab|handOff|\.finish\s*\(", re.I)


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(arguments):
    """Deduplicate only review text, not source records, metrics or verdicts."""
    text = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
    text = re.sub(r"http://127\.0\.0\.1:\d+/t/[0-9a-f]{32}/", "FIXTURE/", text)
    return re.sub(r"bm-expanded4-sol61-20261113-v1-\d{3}", "ATTEMPT-CONTEXT", text)


def image_evidence(content):
    raw = base64.b64decode(content["data"], validate=True)
    with Image.open(BytesIO(raw)) as image:
        expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}[content["mimeType"]]
        assert image.format == expected
        dimensions = image.size
        image.verify()
    return {"mime_type": content["mimeType"], "bytes": len(raw), "dimensions": dimensions}


def validate_usage(row, observed):
    for name, source in (("input", "input_tokens"), ("cached_input", "cached_input_tokens"), ("output", "output_tokens")):
        value = observed.get(source)
        assert type(value) is int and value >= 0 and row[name] == value, (row["seq"], source)
    assert row["cached_input"] <= row["input"]
    # Codex does not expose these Claude-specific metrics in this harness.
    assert all(row.get(k) is None for k in ("requests", "first_input", "cost"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    out = parser.parse_args().out
    rows = experiment.five.suite.ab.load_log(out)
    manifest = load(out / "manifest.json")
    assert digest(out / "runs.jsonl") == ROWS_SHA256
    assert len(rows) == 184 and manifest["plan"] == experiment.plan()
    assert manifest["benchmark_sha"] == EXECUTION_SHA
    assert manifest["kitsune_shas"] == experiment.five.SHAS
    assert manifest["model"] == experiment.MODEL and manifest["effort"] == "medium"
    assert not (out / "stopped.json").exists()
    assert manifest["source_sha256"] == {
        str(p.relative_to(ROOT)): digest(p) for p in experiment.FILES}
    assert manifest["catalog_preflight_sha256"] == digest(out / "catalog-preflight.json")
    first = load(out / "first-eight-audit.json")
    assert first["continue"] is True and first["first_eight_sha256"] == hashlib.sha256(
        b"".join((out / "runs.jsonl").read_bytes().splitlines(keepends=True)[:8])).hexdigest()
    frozen = load(out / "catalog-preflight.json")["catalogs"]
    replies = 0
    calls_count, scripts_count, item_types, image_types = Counter(), Counter(), Counter(), Counter()
    errors, handoffs, flags, images, contexts, teardowns, elicitations, viewports = [], [], [], [], [], [], [], []
    transcript, unique = [], defaultdict(dict)
    harness_hashes = set()
    for row, planned in zip(rows, manifest["plan"]):
        assert all(row[k] == v for k, v in planned.items()), row["seq"]
        assert experiment.stop_reason(row) is None, row["seq"]
        arm, seq = row["arm"], row["seq"]
        target, source, _, _ = experiment.ARMS[arm]
        pair_dir, run_dir = Path(row["pair_dir"]), Path(row["run_dir"])
        expected = frozen[arm]
        for when in ("before", "after"):
            assert load(out / "catalogs" / f"{seq:03d}-{when}.json")[arm] == expected, (seq, when)
        assert experiment.five.observed_catalog(pair_dir) == expected, seq
        for event in map(json.loads, (pair_dir / "catalog-metadata.jsonl").read_text().splitlines()):
            if event["method"] == "tools/list":
                listing = event["response"]["result"]
                assert not listing.get("nextCursor") and sorted(listing["tools"], key=lambda t: t["name"]) == expected["tools"], seq
                replies += 1
        m, pair = load(run_dir / "manifest.json"), load(pair_dir / "pair-manifest.json")
        assert m["harness"] == "codex" and m["codex_version"] == "0.163.0", seq
        assert m["model"] == experiment.MODEL and m["reasoning_effort"] == "medium", seq
        assert m["auth_policy"] == "chatgpt_subscription_only" and m["preflight"]["prerequisites_ok"], seq
        assert 'forced_login_method="chatgpt"' in m["argv"], seq
        assert pair["benchmark_source"]["revision"] == EXECUTION_SHA and not pair["benchmark_source"]["dirty"], seq
        assert pair["kitsune_source"]["revision"] == manifest["kitsune_shas"][source] and not pair["kitsune_source"]["dirty"], seq
        assert pair["targets"] == [target], seq
        harness_hashes.add(m["harness_sha256"])
        observed = audit_events(run_dir / "events.jsonl", allowed_tools=tuple(t["name"] for t in expected["tools"]))
        assert observed["turn_completed"] and not observed["violations"] and not observed["harness_error"], seq
        validate_usage(row, observed["usage"])
        assert observed["mcp_calls"] == row["calls"], seq
        for event in map(json.loads, (run_dir / "events.jsonl").read_text().splitlines()):
            item = event.get("item") or {}
            if event.get("type") == "item.completed":
                item_types[item["type"]] += 1
                if item["type"] == "mcp_tool_call":
                    for content in (item.get("result") or {}).get("content", []):
                        if content.get("type") == "image":
                            image_types[content.get("mimeType")] += 1
                            images.append({"seq": seq, "arm": arm, **image_evidence(content)})
        calls = experiment.agent_calls(run_dir / "events.jsonl")
        assert len(calls) == row["calls"], seq
        assert sum(bool(c["error"]) for c in calls) == observed["failed_mcp_calls"], seq
        calls_count[arm] += len(calls)
        for index, call in enumerate(calls, 1):
            name, args = call["tool"], call["arguments"]
            assert name in {t["name"] for t in expected["tools"]}, (seq, name)
            if name in experiment.five.SCRIPT_TOOLS:
                scripts_count[arm] += 1
            encoded = json.dumps(args, ensure_ascii=False)
            summary = {"seq": seq, "unit": row["unit"], "arm": arm, "call": index, "tool": name}
            if call["error"]:
                errors.append({**summary, "arguments": args, "result": call["text"]})
            if name == "browser_tabs" and args.get("action") == "request":
                handoffs.append({**summary, "result": call["text"]})
            if REVIEW.search(encoded):
                flags.append({**summary, "arguments": args})
            if "setViewportSize" in encoded:
                viewports.append({**summary, "arguments": args})
            transcript.append(f"\n### {seq} {row['unit']} {arm} call {index}: {name}, error={call['error']}\n{encoded}\n")
            if call["error"]:
                transcript.append(call["text"] + "\n")
            # Include unit/arm/error in the key so task-dependent targets are not collapsed across tasks.
            key = (row["unit"], name, bool(call["error"]), normalized(args))
            unique[arm].setdefault(key, []).append(f"{seq}.{index}")
        grade = load(run_dir / "evaluation.json")
        assert grade["task_success"] == row["grade_success"] and grade["safety_pass"] == row["safety_pass"], seq
        assert grade["scorable"] and grade["initial_state_verified"], seq
        evidence = load(pair_dir / f"{target}-session-evidence.json")
        assert evidence["setup_complete"] and not evidence.get("error") and not evidence["outside_navigation"], seq
        if target in ("aside", "ego"):
            assert evidence["profile_isolated"] is False and evidence["seeded_owned_by_agent"] is None, seq
            contexts.append({"seq": seq, "arm": arm, "context": evidence["context"], "space_id": evidence.get("space_id")})
            if target == "ego":
                for call in calls:
                    for argument in re.findall(r"taskSpace\(([^)]+)\)", call["arguments"].get("code", "")):
                        assert argument.strip("\"'") in (evidence["context"], str(evidence["space_id"])), (seq, argument)
        if evidence.get("teardown_error"):
            teardowns.append({"seq": seq, "error": evidence["teardown_error"]})
        timing = run_timing(pair_dir, target, {"elapsed_sec": row["elapsed"]})
        assert timing == row["timing"], seq
        adjusted = row["elapsed"] - timing["relay_setup_sec"] - evidence["post_call_inventory_sec"]
        assert adjusted == row["adjusted_elapsed"] and adjusted >= 0, seq
        for record in map(json.loads, (pair_dir / f"{target}-native-rpc.jsonl").read_text().splitlines()):
            if record.get("kind") == "scripted_decline_delay":
                elicitations.append({"seq": seq, **record})
    assert len(harness_hashes) == 1
    assert len({c["context"] for c in contexts}) == len(contexts) == 92
    assert len({c["space_id"] for c in contexts if c["arm"] == "ego"}) == 46
    report = {"rows_sha256": ROWS_SHA256, "execution_sha": EXECUTION_SHA, "attempts": len(rows),
              "scorable": sum(r["scorable"] for r in rows), "successes": sum(r["success"] for r in rows),
              "catalog_replies_checked": replies, "before_after_catalogs_checked": 2 * len(rows),
              "calls_checked": dict(calls_count), "script_calls_checked": dict(scripts_count),
              "completed_item_types": dict(item_types), "image_types": dict(image_types), "images": images,
              "harness_sha256": sorted(harness_hashes), "contexts": contexts, "teardown_errors": teardowns,
              "handoffs": handoffs, "scripted_declines": elicitations, "errors": errors, "review_flags": flags,
              "agent_viewport_changes": viewports,
              "manual_review_required": True,
              "limitations": ["Requested model/auth configuration is not backend model identity attestation.",
                              "Post-call inventory cannot observe all inner-script operations.",
                              "Pattern flags and successful graders are not a confinement or policy certificate."]}
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (out / "call-review.txt").write_text("".join(transcript))
    for arm, groups in unique.items():
        lines = [f"\n### {unit}, {name}, error={error}, calls={','.join(calls)}\n{text}\n"
                 for (unit, name, error, text), calls in groups.items()]
        (out / f"unique-review-{arm}.txt").write_text("".join(lines))
    print(json.dumps({k: v for k, v in report.items() if k not in (
        "contexts", "images", "errors", "handoffs", "scripted_declines", "review_flags")}, indent=2))
    print("Errors", len(errors), "handoffs", len(handoffs), "scripted declines", len(elicitations), "review flags", len(flags))
    print("Unique review groups", {arm: len(groups) for arm, groups in unique.items()})


if __name__ == "__main__":
    main()
