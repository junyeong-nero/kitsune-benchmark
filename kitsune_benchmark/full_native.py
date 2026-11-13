"""Full-native track (#109): Kitsune's own tool groups, Kitsune only, reported apart from the head-to-head.

Every other model track runs the 23-tool UI allowlist both servers share, so Kitsune's `automation`, `read`,
`network` groups and `browser_evaluate` were never measured with a model. This track runs two Kitsune arms on the
same units, with no benchmark allowlist (each arm sees what Kitsune publishes) and no Playwright arm:

- `core`: KITSUNE_CAPS=core, Kitsune's default 27 core tools.
- `gateway`: KITSUNE_CAPS=all and KITSUNE_PUBLISH=core, the core tools plus the gateway tools
  (browser_tools_search, browser_tools_call, browser_tools_publish) that reach every other group, as Kitsune's
  README recommends.

Units are existing tasks where orchestration should pay, unchanged: personal `research`, `handoff_draft` and
`long_page_lookup` (pb-longpage-*), and gallery `ui-table` (select rows across pages) on both layouts. Each run is a
Kitsune-only pair with a fresh fixture, browser and bridge; the arm order alternates by unit. Graded by the tracks'
own graders; the analysis adds gateway use, container (batch) steps and capability errors from the run's events.

Plan-only by default. Execution consumes subscription quota or API credit.
`python -m kitsune_benchmark.full_native SUITE_SUMMARY` recomputes the analysis offline, without a model.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

from . import gallery, personal
from .adapter import claude_budget, harness_pins, with_claude_overrides, write_json
from .cost_metrics import normalized_usage
from .full_native_session import GATEWAY_CALL, OUTSIDE_NAVIGATION, agent_call
from .personal_session import ELICITATION_POLICIES
from .smoke import ROOT, run_pair, source_revision
from .specs import Server, Task

BENCHMARK = "kitsune-full-native-v1"
# Arm name -> the KITSUNE_* settings of its bridge and MCP server (the bridge enforces KITSUNE_CAPS too).
ARMS = {"core": {"KITSUNE_CAPS": "core"},
        "gateway": {"KITSUNE_CAPS": "all", "KITSUNE_PUBLISH": "core"}}
PERSONAL_CATEGORIES = ("research", "handoff_draft", "long_page_lookup")
GALLERY_UNITS = (("ui-table", "crowded"), ("ui-table", "isolated"))
GATEWAY_TOOLS = ("browser_tools_search", GATEWAY_CALL, "browser_tools_publish")


def command_steps(command) -> int:
    """The commands one batch-shaped command packs: a nested `parallel` counts the commands of its sequences, a
    nested `retry` its wrapped command, any other command (malformed ones included) one."""
    if isinstance(command, dict) and command.get("action") == "parallel":
        return sequences_steps(command.get("sequences"))
    if isinstance(command, dict) and command.get("action") == "retry" and isinstance(command.get("command"), dict):
        return command_steps(command["command"])
    return 1


def commands_steps(commands) -> int:
    return sum(command_steps(command) for command in commands) if isinstance(commands, list) else 0


def sequences_steps(sequences) -> int:
    return sum(commands_steps(sequence) for sequence in sequences) if isinstance(sequences, list) else 0


# Kitsune container tools (automation group) and the commands the agent packed into one call. A workflow runs a named
# file whose steps the call does not show, so it counts as a container call without steps.
CONTAINER_STEPS = {
    "browser_batch": lambda a: commands_steps(a.get("commands")),
    "browser_parallel": lambda a: sequences_steps(a.get("sequences")),
    "browser_retry": lambda a: command_steps(a.get("command")) if isinstance(a.get("command"), dict) else 1,
    "browser_broadcast": lambda a: 1,
    "browser_workflow": lambda a: 0,
}
# Error codes a Kitsune result names when the configuration, not the page, stopped the call.
CAPABILITY_CODES = ("capability_restricted", "tool_not_published", "not_supported")
CAPABILITY_CODE = re.compile(r'"code"\s*:\s*"(' + "|".join(CAPABILITY_CODES) + ')"')
INTEGRITY = ("Kitsune only, two KITSUNE_CAPS/KITSUNE_PUBLISH arms on the same synthetic local units, graded by the "
             "personal and gallery graders unchanged. No benchmark allowlist: browser_evaluate and the automation "
             "tools are reachable, so the tasks' UI-only instruction is a request, not an enforced boundary. "
             "Not a Playwright comparison; do not pool with head-to-head tracks.")


def units() -> list[dict]:
    rows = [{"unit": task["id"], "track": "personal", "task": task["id"], "category": task["category"], "layout": None}
            for task in personal.catalog()["tasks"]
            if task["status"] == "runnable" and task["category"] in PERSONAL_CATEGORIES]
    rows += [{"unit": f"{task}/{layout}", "track": "gallery", "task": task, "category": gallery.BY_ID[task].category,
              "layout": layout} for task, layout in GALLERY_UNITS]
    return rows


def select_units(ids: list[str] | None = None) -> list[dict]:
    rows = units()
    if ids is None:
        return rows
    by_id = {row["unit"]: row for row in rows}
    if not ids or len(set(ids)) != len(ids) or any(key not in by_id for key in ids):
        raise ValueError("Select unique full-native units: " + ", ".join(by_id))
    return [by_id[key] for key in ids]


def schedule(selected: list[dict]) -> list[dict]:
    """Both arms per unit, back to back; the first arm alternates by unit (core first on even positions)."""
    arms = tuple(ARMS)
    return [{**unit, "arm": arm, "position": j}
            for i, unit in enumerate(selected) for j, arm in enumerate(arms if i % 2 == 0 else arms[::-1])]


def track_spec(track: str, claude_model, max_budget_usd_per_run, codex_model) -> dict:
    module = personal if track == "personal" else gallery
    return with_claude_overrides(module.config(), claude_model, max_budget_usd_per_run, codex_model)


def full_native_relay(prepare_server):
    """The fixture's prepare_server, with its relay script (the frozen personal_session.py) replaced by
    full_native_session.py, which runs the same session plus the gateway accounting; the relay config is unchanged."""
    def prepare(target: str, server: Server, task: Task, pair_dir: Path) -> Server:
        relay = prepare_server(target, server, task, pair_dir)
        if Path(relay.args[0]).name != "personal_session.py":
            raise ValueError("Unexpected fixture relay.")
        return replace(relay, args=(str(ROOT / "kitsune_benchmark/full_native_session.py"), *relay.args[1:]))
    return prepare


def run_unit(item: dict, spec: dict, *, variant: int, elicitation: str, kitsune_project, executable, harness) -> dict:
    provenance = {}
    if item["track"] == "personal":
        task = selected = personal.selected_tasks([item["task"]])[0]
        provenance = {"catalog_sha256": hashlib.sha256((ROOT / spec["catalog"]).read_bytes()).hexdigest()}
    else:
        task = gallery.select([item["task"]])[0]
        selected = {"id": task.id, "category": task.category}
    experiment = {**spec, **provenance, "selected_task": selected, "variant": variant, "layout": item["layout"],
                  "elicitation": elicitation,
                  "full_native": {"benchmark": BENCHMARK, "unit": item["unit"], "arm": item["arm"],
                                  "kitsune_env": ARMS[item["arm"]], "tool_policy": "no_benchmark_allowlist"}}
    common = dict(execute=True, kitsune_project=kitsune_project, executable=executable, experiment_spec=experiment,
                  artifact_scope="full-native", enabled_tools=None, harness=harness, targets=("kitsune",),
                  kitsune_env=ARMS[item["arm"]], kitsune_firefox_prefs=personal.USER_CHANNEL_PREFS,
                  equalize_kitsune_viewport=True)
    if item["track"] == "personal":
        with personal.PersonalServer(task, variant, report_viewport=True, elicitation=elicitation,
                                     user_channel=True) as fixture:
            return run_pair(**common, task_for_target=fixture.begin,
                            prepare_server=full_native_relay(fixture.prepare_server), evaluate=fixture.evaluate,
                            viewport_reports=fixture.viewport_reports,
                            kitsune_firefox_args=personal.user_channel_args(fixture.bidi_ports["kitsune"]))
    with gallery.GalleryServer(task, variant, item["layout"], elicitation) as fixture:
        return run_pair(**common, task_for_target=fixture.begin,
                        prepare_server=full_native_relay(fixture.prepare_server), evaluate=fixture.evaluate,
                        kitsune_firefox_args=personal.user_channel_args(fixture.kitsune_bidi_port))


def run_full_native(*, execute: bool = False, unit_ids: list[str] | None = None, variant: int = 0,
                    kitsune_project: str | None = None, executable: str = "claude", harness: str = "claude",
                    budget_usd: float | None = None, claude_model: str | None = None,
                    max_budget_usd_per_run: float | None = None, codex_model: str | None = None,
                    elicitation: str = "decline") -> dict:
    if type(variant) is not int or variant not in range(3):
        raise ValueError("Variant must be 0, 1 or 2.")
    if elicitation not in ELICITATION_POLICIES:
        raise ValueError("Unknown elicitation policy.")
    selected = select_units(unit_ids)
    plan = schedule(selected)
    specs = {track: track_spec(track, claude_model, max_budget_usd_per_run, codex_model)
             for track in ("personal", "gallery")}
    model, _ = harness_pins(specs["personal"], harness)
    if harness_pins(specs["gallery"], harness)[0] != model:
        raise ValueError("Personal and gallery configs pin different models.")
    per_run = claude_budget(specs["personal"], harness)
    if budget_usd is not None and (per_run is None or isinstance(budget_usd, bool)
                                   or not isinstance(budget_usd, (int, float)) or budget_usd <= 0):
        raise ValueError("--budget-usd needs a positive amount and an API-key harness (claude-api or claude-api-full).")
    header = {"benchmark": BENCHMARK, "harness": harness, "model": model, "variant": variant,
              "elicitation": elicitation, "arms": ARMS, "targets": ["kitsune"],
              "tool_policy": "no_benchmark_allowlist", "integrity": INTEGRITY}
    if not execute:
        return {"mode": "full_native_plan_only", "model_invoked": False, **header, "units": selected,
                "schedule": plan, "planned_model_runs": len(plan), "max_budget_usd_per_run": per_run,
                "suite_budget_usd": budget_usd, "worst_case_usd": len(plan) * per_run if per_run else None,
                "next": "Use full-native --execute explicitly; consumes subscription quota or API credit."}
    project = Path(kitsune_project).expanduser().resolve() if kitsune_project else ROOT.parent / "kitsune"
    source = source_revision(project)
    runs, spent, stopped = [], 0.0, None
    for item in plan:
        if budget_usd is not None and spent + per_run > budget_usd:
            stopped = "suite_budget"
            break
        if runs and source_revision(project) != source:
            stopped = "kitsune_revision_changed"
            break
        pair = run_unit(item, specs[item["track"]], variant=variant, elicitation=elicitation,
                        kitsune_project=kitsune_project, executable=executable, harness=harness)
        entry = {**item, "variant": variant, "pair": pair, "kitsune_source_after": source_revision(project)}
        write_json(Path(pair["pair_dir"]) / "full-native-summary.json", entry)
        runs.append(entry)
        if per_run is not None:
            # A missing cost report counts as the full cap, so the running total never undercounts.
            cost = pair["results"].get("kitsune", {}).get("list_price_cost_usd")
            spent += cost if isinstance(cost, (int, float)) else per_run
        if entry["kitsune_source_after"] != source:
            stopped = "kitsune_revision_changed"
            break
        if not personal.pair_complete(pair, ("kitsune",)):
            stopped = personal.incomplete_stop(pair)
            break  # No further quota after a harness/setup failure. Ordinary task failure is still scorable.
    if not runs:
        raise ValueError("Suite budget is smaller than one run's worst case; nothing was run.")
    summary_path = Path(runs[0]["pair"]["pair_dir"]) / "suite-summary.json"
    summary = {"mode": "full_native_executed", "model_invoked": True, **header, "kitsune_source": source,
               "requested_runs": len(plan), "attempted_runs": len(runs), "stopped_reason": stopped,
               "completed_runs": sum(personal.pair_complete(r["pair"], ("kitsune",)) for r in runs),
               "estimated_cost_usd": round(spent, 6) if per_run is not None else None,
               "suite_budget_usd": budget_usd, "max_budget_usd_per_run": per_run,
               "runs": runs, "analysis": analyze(runs), "suite_summary_path": str(summary_path)}
    write_json(summary_path, summary)
    return summary


# --------------------------------------------------------------------------- analysis (no model, no browser)
def result_text(content) -> str:
    """A result's text items; a result without text is read from its structuredContent, so a code both carry is
    read once."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        text = result_text(content.get("content"))
        return text or (json.dumps(content["structuredContent"]) if "structuredContent" in content else "")
    if isinstance(content, list):
        return "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
    return ""


def agent_calls(events_path: Path) -> list[dict]:
    """The agent's MCP calls in order, with their result's error flag and text, from Claude Code stream-json or
    Codex JSONL events. `listed`: the tool was in Claude Code's latest system-init tool list (always true without
    one, as for Codex). Claude Code refuses an unlisted tool without running it, unless it refreshed its list since."""
    calls, by_id, init_tools = [], {}, None
    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "system" and event.get("subtype") == "init":
            tools = event.get("tools")
            init_tools = {tool for tool in tools if isinstance(tool, str)} if isinstance(tools, list) else set()
            continue
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call":
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            calls.append({"tool": str(item.get("tool", "")).split("__")[-1],
                          "arguments": item.get("arguments") if isinstance(item.get("arguments"), dict) else {},
                          "listed": True, "error": item.get("status") == "failed" or result.get("isError") is True,
                          "text": result_text(result)})
            continue
        content = (event.get("message") or {}).get("content") if isinstance(event.get("message"), dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                call = {"tool": str(block.get("name", "")).split("__")[-1],
                        "arguments": block.get("input") if isinstance(block.get("input"), dict) else {},
                        "listed": init_tools is None or block.get("name") in init_tools, "error": None, "text": ""}
                by_id[block.get("id")] = call
                calls.append(call)
            elif event.get("type") == "user" and block.get("type") == "tool_result" and block.get("tool_use_id") in by_id:
                call = by_id[block["tool_use_id"]]
                call.update(error=block.get("is_error") is True, text=result_text(block.get("content")))
    return calls


def published_tools(pair_dir: Path) -> list[str] | None:
    """Tools the Kitsune server listed to the agent at the start, from the relay's metadata: the first tools/list,
    with its pages up to the first without nextCursor; later listings (after browser_tools_publish) are not included.
    None without metadata."""
    try:
        metadata = json.loads((pair_dir / "kitsune-native-metadata.json").read_text())
    except (OSError, ValueError):
        return None
    names = set()
    for page in metadata.get("tools_pages", []):
        page = page if isinstance(page, dict) else {}
        names.update(tool["name"] for tool in page.get("tools", []) if isinstance(tool, dict) and "name" in tool)
        if not page.get("nextCursor"):
            break
    return sorted(names)


def relay_tab_calls(pair_dir: Path) -> list[dict]:
    """The agent calls the relay sent to Kitsune (evidence `tab_calls`); empty without evidence."""
    try:
        calls = json.loads((pair_dir / "kitsune-session-evidence.json").read_text()).get("tab_calls")
    except (OSError, ValueError, AttributeError):
        return []
    return [call for call in calls if isinstance(call, dict)] if isinstance(calls, list) else []


def relay_key(call: dict) -> tuple:
    """How the relay records an agent call in tab_calls: the tool it runs, and `via` for a gateway call."""
    name, _ = agent_call(call["tool"], call["arguments"])
    return name, GATEWAY_CALL if call["tool"] == GATEWAY_CALL and name != GATEWAY_CALL else None


def mark_ran(calls: list[dict], tab_calls: list[dict]) -> None:
    """Set each call's `ran`: whether it reached Kitsune. The relay refused a call it answered with
    OUTSIDE_NAVIGATION. A listed call ran otherwise. An unlisted call ran only when the relay recorded it, which
    happens after Claude Code refreshed its list: per relay key, the tab_calls the listed calls leave over are the
    unlisted calls that ran, assigned to the latest ones (a refresh follows a browser_tools_publish)."""
    left = Counter((call.get("tool"), call.get("via")) for call in tab_calls)
    for call in calls:
        call["ran"] = call["listed"] and call["text"] != OUTSIDE_NAVIGATION
        if call["ran"]:
            left[relay_key(call)] -= 1
    for call in reversed(calls):
        if not call["listed"] and left[relay_key(call)] > 0:
            call["ran"] = True
            left[relay_key(call)] -= 1


def run_metrics(pair: dict) -> dict:
    """One Kitsune run: grade, input, calls and model requests, and its native use (None when its events are missing):
    gateway calls by gateway tool and the tools browser_tools_call ran, container calls and the commands packed into
    them (`batch_steps`), and capability errors by code, all over the calls that reached Kitsune (mark_ran).
    `unlisted_tool_calls`: unlisted calls that did not run. Gateway calls are unwrapped before counting containers."""
    result = pair.get("results", {}).get("kitsune", {})
    evaluation = result.get("benchmark_evaluation") or {}
    usage = normalized_usage(result)
    published = published_tools(Path(pair["pair_dir"])) if pair.get("pair_dir") else None
    row = {"scorable": evaluation.get("scorable"), "task_success": evaluation.get("task_success"),
           "functional_success": evaluation.get("functional_success"), "safety_pass": evaluation.get("safety_pass"),
           "execution_status": result.get("execution_status"),
           "input_tokens": usage.get("input_tokens"), "uncached_input_tokens": usage.get("uncached_input_tokens"),
           "output_tokens": usage.get("output_tokens"), "mcp_calls": result.get("mcp_calls"),
           "model_requests": (result.get("token_attribution") or {}).get("requests"),
           "unlisted_tool_calls": None,
           "published_tools": len(published) if published is not None else None,
           "gateway_published": bool(set(GATEWAY_TOOLS) & set(published)) if published is not None else None,
           "native": None}
    try:
        calls = agent_calls(Path(result["run_dir"]) / "events.jsonl")
    except (KeyError, OSError, ValueError):
        return row
    mark_ran(calls, relay_tab_calls(Path(pair["pair_dir"])) if pair.get("pair_dir") else [])
    ran = [call for call in calls if call["ran"]]
    row["unlisted_tool_calls"] = sum(not call["listed"] and not call["ran"] for call in calls)
    gateway, via_gateway, containers, codes = Counter(), Counter(), Counter(), Counter()
    steps = 0
    for call in ran:
        if call["tool"] in GATEWAY_TOOLS:
            gateway[call["tool"]] += 1
        name, arguments = agent_call(call["tool"], call["arguments"])
        if call["tool"] == GATEWAY_CALL and name != GATEWAY_CALL:
            via_gateway[name] += 1
        if name in CONTAINER_STEPS:
            containers[name] += 1
            steps += CONTAINER_STEPS[name](arguments)
        codes.update(CAPABILITY_CODE.findall(call["text"]))
    row["native"] = {"agent_calls": len(calls), "ran_calls": len(ran),
                     "error_results": sum(c["error"] is True for c in ran),
                     "gateway_calls": {tool: gateway[tool] for tool in GATEWAY_TOOLS},
                     "gateway_called_tools": dict(sorted(via_gateway.items())),
                     "container_calls": dict(sorted(containers.items())), "batch_steps": steps,
                     "capability_errors": {code: codes[code] for code in CAPABILITY_CODES}}
    return row


def sum_reported(rows: list[dict], key: str) -> dict:
    values = [row[key] for row in rows if row.get(key) is not None]
    return {"total": sum(values) if values else None, "reported_runs": len(values),
            "missing_runs": len(rows) - len(values)}


def arm_totals(rows: list[dict]) -> dict:
    native = [row["native"] for row in rows if row["native"] is not None]
    known = [row for row in rows if row["scorable"] and row["task_success"] is not None]
    def counter(key):
        total = Counter()
        for item in native:
            total.update(item[key])
        return dict(sorted(total.items()))
    return {"runs": len(rows), "scorable": sum(bool(row["scorable"]) for row in rows),
            "successes": sum(row["task_success"] is True for row in rows), "success_known_runs": len(known),
            "scorable_success_rate": sum(row["task_success"] is True for row in known) / len(known) if known else None,
            **{key: sum_reported(rows, key) for key in ("input_tokens", "uncached_input_tokens", "output_tokens",
                                                        "mcp_calls", "model_requests", "unlisted_tool_calls")},
            "runs_with_native_metrics": len(native),
            "runs_using_gateway": sum(any(item["gateway_calls"].values()) for item in native),
            "runs_using_containers": sum(bool(item["container_calls"]) for item in native),
            "gateway_calls": counter("gateway_calls"), "gateway_called_tools": counter("gateway_called_tools"),
            "container_calls": counter("container_calls"),
            "batch_steps": sum(item["batch_steps"] for item in native),
            "capability_errors": counter("capability_errors"),
            "error_results": sum(item["error_results"] for item in native)}


def analyze(runs: list[dict]) -> dict:
    """Per arm, per unit and on joint successes (units both arms solved in this suite). `gateway / core` ratios are
    sums over joint successes; per-unit ratios are listed with their median. Failed and unscored runs stay in the
    per-arm totals and the per-unit rows, never in the joint-success comparison."""
    rows = [{"unit": run["unit"], "arm": run["arm"], "track": run["track"], "category": run["category"],
             "position": run.get("position"), **run_metrics(run["pair"])} for run in runs]
    by_unit: dict[str, dict] = {}
    for row in rows:
        by_unit.setdefault(row["unit"], {})[row["arm"]] = row
    joint = [unit for unit, arms in by_unit.items()
             if all(arms.get(arm, {}).get("scorable") and arms[arm].get("task_success") is True for arm in ARMS)]
    comparison = {"units": joint}
    for key in ("input_tokens", "mcp_calls", "model_requests"):
        totals = {arm: sum_reported([by_unit[unit][arm] for unit in joint], key) for arm in ARMS}
        core, gateway = totals["core"]["total"], totals["gateway"]["total"]
        complete = all(t["missing_runs"] == 0 for t in totals.values())
        ratios = [by_unit[u]["gateway"][key] / by_unit[u]["core"][key] for u in joint
                  if by_unit[u]["core"].get(key) and by_unit[u]["gateway"].get(key) is not None]
        comparison[key] = {**totals, "ratio_gateway_to_core": gateway / core if complete and core else None,
                           "unit_ratios_median": statistics.median(ratios) if ratios else None}
    return {"arms": {arm: arm_totals([row for row in rows if row["arm"] == arm]) for arm in ARMS},
            "by_category": {category: {arm: arm_totals([r for r in rows if r["arm"] == arm and r["category"] == category])
                                       for arm in ARMS}
                            for category in dict.fromkeys(row["category"] for row in rows)},
            "joint_successes": comparison, "units": by_unit}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recompute a full-native suite's analysis offline (no model calls)")
    parser.add_argument("summary", type=Path, help="suite-summary.json of a full-native run")
    parser.add_argument("--output", type=Path, help="Write the analysis here; an existing file is refused")
    args = parser.parse_args(argv)
    summary = json.loads(args.summary.read_text())
    if summary.get("benchmark") != BENCHMARK or not isinstance(summary.get("runs"), list):
        print("Not a full-native suite summary.", file=sys.stderr)
        return 2
    result = analyze(summary["runs"])
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
