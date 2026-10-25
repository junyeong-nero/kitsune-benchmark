"""Per-model-request round structure of Claude Code stream-json runs. No model/browser calls.

A round is one deduplicated model request (assistant message id), as in token_attribution. For each round:
tool calls issued (parallel when more than one), observation vs action tools, model-visible result size,
snapshot refs returned and how many are new, whether an observation-only round follows an action round
or another observation-only round, Kitsune's collapsed-list hints ("N more similar items; snapshot eX to
list all") and the snapshots that expand a container still collapsed in the current state, and the
request's input split into cache read, cache write and uncached tokens. Per-message output tokens in stream-json are a streaming snapshot, so only the result
event's output total is reported.

usage: uv run --locked python scripts/analyze-model-rounds.py RUN_DIR_OR_JOB_JSON... [--rounds] [--json out.json]

A job JSON is a gallery/personal summary with pairs[].results[target].run_dir; its runs are grouped by
layout and target.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

MCP_PREFIX = "mcp__browser__"
OBSERVATION_TOOLS = frozenset({"browser_snapshot", "browser_find", "browser_take_screenshot",
                               "browser_console_messages", "browser_network_requests", "browser_network_request"})
REF = re.compile(r"\[ref=([A-Za-z0-9_]+)\]")
ELISION = re.compile(r"(\d+) more similar items; snapshot ([A-Za-z0-9_]+) to list all")
USAGE_KEYS = ("cache_read_input_tokens", "cache_creation_input_tokens", "input_tokens")


def read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def result_text(block: dict) -> str:
    body = block.get("content")
    if isinstance(body, str):
        return body
    return "".join(item.get("text", "") for item in body if isinstance(item, dict)) if isinstance(body, list) else ""


def model_rounds(events: list[dict]) -> list[dict]:
    rounds: list[dict] = []
    by_message: dict[str, dict] = {}
    by_call: dict[str, dict] = {}
    for event in events:
        message = event.get("message")
        if event.get("type") not in {"assistant", "user"} or not isinstance(message, dict):
            continue
        content = message.get("content") if isinstance(message.get("content"), list) else []
        if event["type"] == "assistant":
            current = by_message.get(message.get("id"))
            if current is None:
                usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                tokens = {key: v if type(v := usage.get(key)) is int and v >= 0 else 0 for key in USAGE_KEYS}
                current = {"index": len(rounds), "calls": [], "input_tokens": sum(tokens.values()),
                           "cache_read_input_tokens": tokens["cache_read_input_tokens"],
                           "cache_creation_input_tokens": tokens["cache_creation_input_tokens"],
                           "uncached_input_tokens": tokens["input_tokens"]}
                by_message[message.get("id")] = current
                rounds.append(current)
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                    tool = block["name"].removeprefix(MCP_PREFIX)
                    arguments = block.get("input") if isinstance(block.get("input"), dict) else {}
                    call = {"tool": tool, "kind": "observation" if tool in OBSERVATION_TOOLS else "action",
                            "target": arguments.get("target"), "result_chars": 0, "result_bytes": 0, "refs": set(),
                            "hinted": set(), "elided_items": 0, "error": False}
                    current["calls"].append(call)
                    by_call[block.get("id")] = call
        else:
            for block in content:
                call = by_call.get(block.get("tool_use_id")) if isinstance(block, dict) else None
                if call is None or block.get("type") != "tool_result":
                    continue
                text = result_text(block)
                hints = ELISION.findall(text)
                call.update(result_chars=len(text), result_bytes=len(text.encode()), refs=set(REF.findall(text)),
                            hinted={ref for _, ref in hints}, elided_items=sum(int(n) for n, _ in hints),
                            error=block.get("is_error") is True)
    seen: set[str] = set()
    # Containers collapsed in the current state, in call order. An action result describes the state after the
    # action, so it replaces the set: a page turn whose delta has no hint clears the earlier page's hints.
    collapsed: set[str] = set()
    previous_kinds: set[str] = set()
    for current in rounds:
        calls = current["calls"]
        kinds = {call["kind"] for call in calls}
        returned = set().union(*(call["refs"] for call in calls)) if calls else set()
        collapsed_before = bool(collapsed)
        expansions = 0
        for call in calls:
            call["new_refs"] = len(call["refs"] - seen)
            seen |= call["refs"]
            # A snapshot of a container whose latest state is collapsed with a "snapshot eX to list all" hint.
            expansions += call["tool"] == "browser_snapshot" and call["target"] in collapsed
            collapsed = set(call["hinted"]) if call["kind"] == "action" else collapsed | call["hinted"]
        follow_up = kinds == {"observation"} and "action" in previous_kinds
        current.update(
            tools=[call["tool"] for call in calls],
            kind="answer" if not calls else "+".join(sorted(kinds)),
            parallel=len(calls) > 1,
            # The model asks only for an observation right after acting: the action results did not suffice.
            follow_up_observation=follow_up,
            # The follow-up starts from a state with a collapsed container, not e.g. an uncollapsed last page.
            follow_up_on_collapsed=follow_up and collapsed_before,
            chained_observation=kinds == {"observation"} and previous_kinds == {"observation"},
            expansion_reads=expansions,
            elided_results=sum(bool(call["hinted"]) for call in calls),
            elided_items=sum(call["elided_items"] for call in calls),
            # Observation calls placed after an action in the same batch see post-action state without a round.
            in_batch_observation_after_action=any(call["kind"] == "observation" and any(
                c["kind"] == "action" for c in calls[:i]) for i, call in enumerate(calls)),
            result_chars=sum(call["result_chars"] for call in calls),
            result_bytes=sum(call["result_bytes"] for call in calls),
            observation_chars=sum(call["result_chars"] for call in calls if call["kind"] == "observation"),
            action_result_chars=sum(call["result_chars"] for call in calls if call["kind"] == "action"),
            action_result_refs=sum(len(call["refs"]) for call in calls if call["kind"] == "action"),
            # Refs first seen in an action result: the action revealed new elements, e.g. a page turn.
            action_new_refs=sum(call["new_refs"] for call in calls if call["kind"] == "action"),
            refs_returned=len(returned), new_refs=sum(call["new_refs"] for call in calls),
            errors=sum(call["error"] for call in calls))
        previous_kinds = kinds
        for call in calls:
            call["refs"] = len(call["refs"])
            call["hinted"] = sorted(call["hinted"])
    return rounds


ROUND_FLAGS = ("parallel", "follow_up_observation", "follow_up_on_collapsed", "chained_observation",
               "in_batch_observation_after_action")
ROUND_TOTALS = ("errors", "result_chars", "result_bytes", "observation_chars", "action_result_chars",
                "action_result_refs", "action_new_refs", "refs_returned", "new_refs", "elided_results", "elided_items",
                "expansion_reads", "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
                "uncached_input_tokens")


def run_summary(events: list[dict]) -> dict:
    rounds = model_rounds(events)
    result = next((e for e in events if e.get("type") == "result"), {})
    first_action = next((r["index"] for r in rounds if "action" in r["kind"]), len(rounds))
    # As in token_attribution: the first request approximates the fixed prefix re-sent with every request.
    prefix_x_requests = rounds[0]["input_tokens"] * len(rounds) if rounds else 0
    return {
        "requests": len(rounds), "calls": sum(len(r["calls"]) for r in rounds),
        "prefix_x_requests_tokens": prefix_x_requests,
        "history_tokens": max(sum(r["input_tokens"] for r in rounds) - prefix_x_requests, 0),
        "rounds_before_first_action": first_action,
        "kinds": dict(collections.Counter(r["kind"] for r in rounds)),
        "tools": dict(collections.Counter(t for r in rounds for t in r["tools"])),
        **{flag: sum(r[flag] for r in rounds) for flag in ROUND_FLAGS},
        **{key: sum(r[key] for r in rounds) for key in ROUND_TOTALS},
        "result_output_tokens": (result.get("usage") or {}).get("output_tokens"),
        "rounds": rounds,
    }


def runs_from(path: Path):
    """Yield (layout, target, run_dir) for a run dir or every run of a job summary JSON."""
    if path.is_dir():
        yield None, None, path
        return
    job = json.loads(path.read_text())
    for pair in job.get("pairs", []):
        for target, run in pair.get("results", {}).items():
            yield job.get("layout"), target, Path(run["run_dir"])


def group_summary(runs: list[dict]) -> dict:
    keys = ("requests", "calls", "prefix_x_requests_tokens", "history_tokens", "rounds_before_first_action",
            *ROUND_FLAGS, *ROUND_TOTALS, "result_output_tokens")
    out = {"runs": len(runs), **{key: sum(r[key] or 0 for r in runs) for key in keys}}
    out["per_run_requests"] = [r["requests"] for r in runs]
    out["kinds"] = dict(sum((collections.Counter(r["kinds"]) for r in runs), collections.Counter()))
    out["tools"] = dict(sum((collections.Counter(r["tools"]) for r in runs), collections.Counter()))
    out["calls_per_request"] = round(out["calls"] / out["requests"], 2) if out["requests"] else None
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--rounds", action="store_true", help="print every round")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for path in args.paths:
        for layout, target, run_dir in runs_from(path):
            summary = run_summary(read_events(run_dir / "events.jsonl"))
            summary["label"] = f"{path.stem if path.is_file() else run_dir.name}:{target or '-'}"
            groups[(layout, target)].append(summary)
            print(f"{summary['label']:42} requests {summary['requests']:3} calls {summary['calls']:3} "
                  f"follow-up obs {summary['follow_up_observation']:2} chained obs {summary['chained_observation']:2} "
                  f"expansions {summary['expansion_reads']:2} result chars {summary['result_chars']:7} "
                  f"input {summary['input_tokens']:8}")
            if args.rounds:
                for r in summary["rounds"]:
                    print(f"  r{r['index']:<3} {r['kind']:19} {'+'.join(r['tools']) or '-':70} "
                          f"chars {r['result_chars']:6} refs {r['refs_returned']:3} new {r['new_refs']:3} "
                          f"act-refs {r['action_result_refs']:3} elided {r['elided_items']:2}"
                          f"{' FOLLOW-UP' if r['follow_up_observation'] else ''}"
                          f"{'(collapsed)' if r['follow_up_on_collapsed'] else ''}"
                          f"{' CHAINED' if r['chained_observation'] else ''}"
                          f"{' EXPANSION' if r['expansion_reads'] else ''}"
                          f"{' IN-BATCH' if r['in_batch_observation_after_action'] else ''} "
                          f"in {r['input_tokens']} (read {r['cache_read_input_tokens']}, "
                          f"write {r['cache_creation_input_tokens']}, uncached {r['uncached_input_tokens']})")
    report = {f"{layout}:{target}": {**group_summary(runs), "run_details": runs}
              for (layout, target), runs in groups.items()}
    print(json.dumps({group: {k: v for k, v in summary.items() if k != "run_details"}
                      for group, summary in report.items()}, indent=1, ensure_ascii=False))
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
