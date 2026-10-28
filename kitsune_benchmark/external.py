"""External track (external-v1): seven pinned MiniWoB++ tasks plus three live public-web tasks.

MiniWoB tasks are graded only by the upstream client-side reward (see miniwob.py). Live tasks run against
sites that change without notice, so they are recorded, never graded: their evaluation is scorable when the
execution completed, task_success stays None, and an optional advisory regex over the final answer is
reported separately. Final chat text never decides a MiniWoB verdict.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .adapter import claude_budget, harness_pins, with_claude_overrides, write_json
from .cost_metrics import normalized_usage
from .miniwob import UI_TOOLS, BenchmarkServer, config, fetch_source, task_sha256, verify_source
from .smoke import ROOT, TARGETS, run_pair, source_revision
from .specs import identifier, load_task

KINDS = ("miniwob", "live")
LIVE_INTEGRITY = ("Live public site: content, layout and availability change without notice. Recorded, not graded; "
                  "advisory_answer_match reads the agent's final text and is not a success label.")


def catalog() -> dict:
    return json.loads((ROOT / config()["catalog"]).read_text())


def task_ids() -> list[str]:
    return [task["id"] for task in catalog()["tasks"]]


def selected_tasks(ids: list[str] | None = None, kind: str | None = None) -> list[dict]:
    tasks = catalog()["tasks"]
    if kind is not None:
        if kind not in KINDS:
            raise ValueError("kind must be miniwob or live.")
        tasks = [task for task in tasks if task["kind"] == kind]
    if ids:
        known = {task["id"]: task for task in tasks}
        if len(set(ids)) != len(ids) or set(ids) - set(known):
            raise ValueError("Unknown or repeated external task ID.")
        tasks = [known[i] for i in ids]
    for task in tasks:
        identifier(task["id"])
        if task["kind"] == "live":
            loaded = load_task(ROOT / task["task_file"])
            if loaded.id != task["id"]:
                raise ValueError("Live task file id must match its catalog id.")
    return tasks


class LiveTask:
    """No fixture server: the task prompt is fixed and the evaluation only records the run."""

    def __init__(self, task: dict) -> None:
        self.task = task
        self.prompt = load_task(ROOT / task["task_file"])

    def begin(self, target: str):
        return self.prompt

    def evaluate(self, target: str, result: dict) -> dict:
        completed = result["execution_status"] == "completed_unscored"
        final = Path(result["run_dir"]) / "final.txt"
        pattern = self.task.get("advisory_answer_regex")
        match = None
        if completed and pattern and final.is_file():
            match = re.search(pattern, final.read_text(errors="replace")) is not None
        return {"benchmark": "live", "track": "external-v1", "task_id": self.task["id"],
                "site": self.task.get("site"), "graded": False, "scorable": completed, "task_success": None,
                "advisory_answer_match": match, "integrity": LIVE_INTEGRITY}


def pair_complete(pair: dict, targets: tuple[str, ...] = TARGETS) -> bool:
    return set(pair["results"]) == set(targets) and all(
        r.get("benchmark_evaluation", {}).get("scorable") for r in pair["results"].values())


def aggregate(pairs: list[dict]) -> dict:
    totals = {}
    for target in TARGETS:
        entry = {}
        for kind in KINDS:
            runs = [p["results"][target] for p in pairs if p["external_kind"] == kind and target in p["results"]]
            scorable = [r for r in runs if r.get("benchmark_evaluation", {}).get("scorable")]
            usage = [normalized_usage(r) for r in runs if r.get("usage")]
            entry[kind] = {"attempted": len(runs), "scorable": len(scorable),
                "mcp_calls": sum(r.get("mcp_calls", 0) for r in runs),
                "elapsed_sec": round(sum(r.get("elapsed_sec", 0) for r in runs), 3),
                "input_tokens_reported": sum(u.get("input_tokens", 0) for u in usage), "runs_with_usage": len(usage)}
            if kind == "miniwob":
                entry[kind]["successes"] = sum(r["benchmark_evaluation"].get("task_success") is True for r in scorable)
                entry[kind]["positive_reward"] = sum(
                    r["benchmark_evaluation"].get("positive_reward") is True for r in scorable)
            else:
                entry[kind]["advisory_answer_matches"] = sum(
                    r["benchmark_evaluation"].get("advisory_answer_match") is True for r in scorable)
        totals[target] = entry
    return totals


def run_external(*, execute: bool = False, fetch: bool = False, task_ids: list[str] | None = None,
                 kind: str | None = None, kitsune_project: str | None = None, executable: str = "codex",
                 harness: str = "codex", budget_usd: float | None = None, targets: tuple[str, ...] = TARGETS,
                 claude_model: str | None = None, max_budget_usd_per_run: float | None = None,
                 codex_model: str | None = None) -> dict:
    spec = with_claude_overrides(config(), claude_model, max_budget_usd_per_run, codex_model)
    tasks = selected_tasks(task_ids, kind)
    model, _ = harness_pins(spec, harness)
    per_run = claude_budget(spec, harness)
    targets = tuple(targets)
    if not targets or len(set(targets)) != len(targets) or set(targets) - set(TARGETS):
        raise ValueError("targets must be a non-empty subset of playwright, kitsune.")
    if budget_usd is not None and (per_run is None or isinstance(budget_usd, bool)
                                   or not isinstance(budget_usd, (int, float)) or budget_usd <= 0):
        raise ValueError("--budget-usd needs a positive amount and an API-key harness (claude-api or claude-api-full).")
    source = fetch_source(spec) if fetch else ROOT / spec["source_directory"]
    if not execute:
        return {"mode": "external_plan_only", "model_invoked": False, "config": spec, "harness": harness,
                "model": model, "targets": list(targets), "selected_tasks": tasks,
                "planned_model_runs": len(targets) * len(tasks), "source_present": source.exists(),
                "max_budget_usd_per_run": per_run, "suite_budget_usd": budget_usd,
                "worst_case_usd": len(targets) * len(tasks) * per_run if per_run else None,
                "ui_tools": UI_TOOLS,
                "next": "Use external --execute explicitly; live tasks reach public sites, and execution consumes "
                        "subscription quota or API credit."}
    if any(task["kind"] == "miniwob" for task in tasks):
        verify_source(source, spec["source_revision"])
    project = Path(kitsune_project).expanduser().resolve() if kitsune_project else ROOT.parent / "kitsune"
    kitsune = source_revision(project)
    catalog_sha = hashlib.sha256((ROOT / spec["catalog"]).read_bytes()).hexdigest()
    pairs, spent, stopped = [], 0.0, None
    for task in tasks:
        if budget_usd is not None and spent + len(targets) * per_run > budget_usd:
            stopped = "suite_budget"
            break
        if pairs and source_revision(project) != kitsune:
            stopped = "kitsune_revision_changed"
            break
        experiment = {**spec, "selected_task": task, "catalog_sha256": catalog_sha,
                      "timeout_sec": spec["live_timeout_sec"] if task["kind"] == "live" else spec["timeout_sec"]}
        if task["kind"] == "miniwob":
            experiment["upstream_task_sha256"] = task_sha256(source, task["task_id"])
            with BenchmarkServer(source, spec, task) as fixture:
                pair = run_pair(execute=True, kitsune_project=kitsune_project, executable=executable,
                    experiment_spec=experiment, artifact_scope="external", task_for_target=fixture.begin,
                    evaluate=fixture.evaluate, enabled_tools=UI_TOOLS, harness=harness, targets=targets)
        else:
            fixture = LiveTask(task)
            pair = run_pair(execute=True, kitsune_project=kitsune_project, executable=executable,
                experiment_spec=experiment, artifact_scope="external", task_for_target=fixture.begin,
                evaluate=fixture.evaluate, enabled_tools=UI_TOOLS, harness=harness, targets=targets)
        pair["external_task"] = task["id"]
        pair["external_kind"] = task["kind"]
        write_json(Path(pair["pair_dir"]) / "external-summary.json", pair)
        pairs.append(pair)
        if per_run is not None:
            spent += sum(r.get("list_price_cost_usd") if isinstance(r.get("list_price_cost_usd"), (int, float))
                         else per_run for r in pair["results"].values())
        if not pair_complete(pair, targets):
            stopped = "unscorable_pair"
            break  # No further quota after a harness/setup failure; an ordinary task failure is still scorable.
    if not pairs:
        raise ValueError("Suite budget is smaller than one pair's worst case; nothing was run.")
    summary_path = Path(pairs[0]["pair_dir"]) / "suite-summary.json"
    summary = {"mode": "external_executed", "model_invoked": True, "suite": catalog()["suite"],
               "harness": harness, "model": model, "targets": list(targets), "kitsune_source": kitsune,
               "requested_pairs": len(tasks), "attempted_pairs": len(pairs), "stopped_reason": stopped,
               "completed_pairs": sum(pair_complete(p, targets) for p in pairs),
               "estimated_cost_usd": round(spent, 6) if per_run is not None else None,
               "suite_budget_usd": budget_usd, "max_budget_usd_per_run": per_run,
               "pairs": pairs, "by_target": aggregate(pairs), "suite_summary_path": str(summary_path),
               "integrity": {"miniwob": "Client-side upstream reward instrumentation; not hardened against "
                                        "malicious agents. Not a standard Gym score.", "live": LIVE_INTEGRITY}}
    write_json(summary_path, summary)
    return summary
