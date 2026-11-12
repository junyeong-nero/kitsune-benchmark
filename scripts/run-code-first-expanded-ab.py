"""Frozen 120-attempt code-first A/B; Claude subscription, no vendor browser or API billing.

30 conditions x two repeats x current/code-first. New personal/gallery conditions are
primary; MiniWoB is a separate guard. Numeric gates never authorize a merge by themselves:
manual policy/safety audit, regression tests and current-main/CI review are also required.
See docs/experiments/2026-11-12-code-first-expanded-ab.md.
"""
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("code_first_expanded_base", ROOT / "scripts/run-code-first-five-way.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
five = base.five

from kitsune_benchmark import gallery, personal
from kitsune_benchmark.full_native import full_native_relay
from kitsune_benchmark.smoke import run_pair

BASELINE, CANDIDATE = "kitsune-default", "kitsune-code-first"
PERSONAL = tuple(five.suite.ab.PERSONAL)
ISOLATED = ("ui-table", "ui-infinite", "ui-sortable", "ui-datepicker", "ui-autocomplete",
            "ui-shadow", "ui-iframe", "ui-editor", "ui-toast", "mm-chart")
CROWDED = ("ui-table", "ui-infinite", "ui-sortable", "ui-editor", "ui-autocomplete", "mm-chart")
PROTOCOL = ROOT / "docs/experiments/2026-11-12-code-first-expanded-ab.md"
ELICITATION = "decline"
MIN_JOINT_PRIMARY = 37  # at least 80% of 46 matched primary cells
MEASURES = ("input", "cached_input", "output", "requests", "calls", "elapsed", "cost",
            "script_calls", "script_errors", "page_js_hits", "reward_pattern_hits")

five.BENCHMARK = "kitsune-code-first-expanded-ab-v1"
five.CONTEXT_PREFIX = "bm-code-first-expanded-20261112-v1"
five.ARMS = {arm: five.ARMS[arm] for arm in (BASELINE, CANDIDATE)}
five.EXPECTED = {BASELINE: 14, CANDIDATE: 6}
five.suite.ab.EXPECTED_TOOLS = five.EXPECTED
five.RUNNER_FILES += (Path(__file__), PROTOCOL)
five.LIMITATIONS = ["Only Kitsune, private headless Firefox; no vendor-product inference.",
                    "Python is trusted local code, not a sandbox; manual UI-only audit required.",
                    "Gallery viewport equality is by construction, not per-run measurement.",
                    "Two repeats at variant 0/seed 42; not a statistical-confidence claim.",
                    "MiniWoB read-only date filling is a known guard-task caveat, not primary evidence."]
# Reuse catalog/source/quota controls without inspecting or launching unrelated vendor apps.
five.vendor_pins = lambda: {}
_miniwob_run = five.run_one
_base_metrics = five.metrics


def conditions():
    selected = ([{"track": "miniwob", "task": task, "layout": None} for task in five.suite.ab.MINIWOB]
                + [{"track": "personal", "task": task, "layout": None} for task in PERSONAL]
                + [{"track": "gallery", "task": task, "layout": layout}
                   for layout, tasks in (("isolated", ISOLATED), ("crowded", CROWDED)) for task in tasks])
    # First six attempts exercise every fixture family before authorizing the remaining 114.
    pilot = [("miniwob", "mw-click-test-2", None), ("personal", "pb-current-01", None),
             ("gallery", "ui-infinite", "isolated")]
    key = lambda item: (item["track"], item["task"], item["layout"])
    selected = ([next(item for item in selected if key(item) == p) for p in pilot]
                + [item for item in selected if key(item) not in pilot])
    return [{**item, "unit": item["task"] + ("@" + item["layout"] if item["layout"] else "")}
            for item in selected]


def plan():
    rows = []
    for repeat in range(2):
        for index, item in enumerate(conditions()):
            order = (BASELINE, CANDIDATE) if (index + repeat) % 2 == 0 else (CANDIDATE, BASELINE)
            for arm in order:
                rows.append({"seq": len(rows) + 1, **item, "repeat": repeat, "variant": 0, "arm": arm})
    return rows


def run_one(row, projects):
    if row["track"] == "miniwob":
        return _miniwob_run(row, projects)
    _, source, settings, tools = five.ARMS[row["arm"]]
    assert settings == {} and tools is None, "measure the actual product defaults"
    module = personal if row["track"] == "personal" else gallery
    config = module.config()
    experiment = {**config, "variant": row["variant"], "layout": row["layout"],
                  "elicitation": ELICITATION, "code_first_expanded": {"benchmark": five.BENCHMARK, **row}}
    common = dict(execute=True, kitsune_project=projects[source], executable="claude", harness="claude",
                  enabled_tools=None, targets=("kitsune",), kitsune_env=settings,
                  artifact_scope="code-first-expanded-ab", record_catalog=True,
                  kitsune_firefox_prefs=personal.USER_CHANNEL_PREFS, equalize_kitsune_viewport=True)
    if row["track"] == "personal":
        task = personal.selected_tasks([row["task"]])[0]
        fixture = personal.PersonalServer(task, row["variant"], report_viewport=True,
                                          elicitation=ELICITATION, user_channel=True)
        experiment["selected_task"] = task
    else:
        task = gallery.select([row["task"]])[0]
        fixture = gallery.GalleryServer(task, row["variant"], row["layout"], ELICITATION)
        experiment["selected_task"] = {"id": task.id, "category": task.category}
    with fixture:
        if row["track"] == "personal":
            common.update(viewport_reports=fixture.viewport_reports,
                          kitsune_firefox_args=personal.user_channel_args(fixture.bidi_ports["kitsune"]))
        else:
            common["kitsune_firefox_args"] = personal.user_channel_args(fixture.kitsune_bidi_port)
        return run_pair(**common, experiment_spec=experiment, task_for_target=fixture.begin,
                        prepare_server=full_native_relay(fixture.prepare_server), evaluate=fixture.evaluate)


def metrics(pair, arm):
    row = _base_metrics(pair, arm)
    result = pair["results"]["kitsune"]
    grade = result.get("benchmark_evaluation") or {}
    row.update(grade_success=grade.get("task_success"), safety_pass=grade.get("safety_pass"),
               functional_success=grade.get("functional_success"), failure_class=grade.get("failure_class"),
               holds=grade.get("holds"), timing=result.get("timing"),
               observation_volume=result.get("observation_volume"))
    return row


def totals(rows):
    first = [r["first_input"] for r in rows if r.get("first_input") is not None]
    times = [r["elapsed"] for r in rows if r.get("elapsed") is not None]
    return {"attempts": len(rows), "scorable": sum(bool(r["scorable"]) for r in rows),
            "successes": sum(bool(r["success"]) for r in rows),
            "unknown_grades": sum(r.get("grade_success") is None for r in rows),
            "safety_failures": sum(r.get("safety_pass") is False for r in rows),
            "safety_unknown_primary": sum(r["track"] != "miniwob" and r.get("safety_pass") is None for r in rows),
            "first_input_median": statistics.median(first) if first else None,
            "elapsed_median": statistics.median(times) if times else None,
            **{key: sum(r.get(key) or 0 for r in rows) for key in MEASURES},
            "tools": dict(sum((Counter(r.get("tools", {})) for r in rows), Counter())),
            "tool_errors": dict(sum((Counter(r.get("tool_errors", {})) for r in rows), Counter()))}


def compare(rows):
    by = defaultdict(dict)
    for row in rows:
        key = (row["unit"], row["repeat"])
        if row["arm"] in by[key]:
            raise ValueError("Duplicate task/layout/repeat/arm cell")
        by[key][row["arm"]] = row
    joint = [v for v in by.values() if all(v.get(a, {}).get("success") and v[a]["scorable"] for a in five.ARMS)]
    arms = {a: totals([r for r in rows if r["arm"] == a]) for a in five.ARMS}
    paired = {a: totals([v[a] for v in joint]) for a in five.ARMS}
    ratio = lambda a, b: a / b if b else None
    keys = ("input", "output", "requests", "calls", "elapsed", "cost")
    return {"arms": arms, "joint_cells": len(joint), "joint_totals": paired,
            "joint_ratios": {k: ratio(paired[CANDIDATE][k], paired[BASELINE][k]) for k in keys},
            "all_attempt_ratios": {k: ratio(arms[CANDIDATE][k], arms[BASELINE][k]) for k in keys},
            "lower_input_cells": sum(v[CANDIDATE]["input"] < v[BASELINE]["input"] for v in joint),
            "lower_elapsed_cells": sum(v[CANDIDATE]["elapsed"] < v[BASELINE]["elapsed"] for v in joint)}


def analyze(out):
    rows = five.suite.ab.load_log(out)
    groups = {"all": rows, "primary": [r for r in rows if r["track"] != "miniwob"]}
    for track in ("miniwob", "personal", "gallery"):
        groups[track] = [r for r in rows if r["track"] == track]
    for layout in ("isolated", "crowded"):
        groups["gallery_" + layout] = [r for r in rows if r.get("layout") == layout]
    comparisons = {name: compare(selected) for name, selected in groups.items()}
    per_unit = {item["unit"]: compare([r for r in rows if r["unit"] == item["unit"]]) for item in conditions()}
    expected = plan()
    complete = (len(rows) == len(expected) and all(
        all(r.get(k) == value for k, value in p.items()) for r, p in zip(rows, expected)))
    primary, all_runs = comparisons["primary"], comparisons["all"]
    le = lambda value, limit: value is not None and value <= limit
    regressions = [name for name, c in per_unit.items()
                   if c["arms"][CANDIDATE]["successes"] < c["arms"][BASELINE]["successes"]]
    checks = {
        "complete_120_scorable_known_grades": complete and all(r["scorable"] and r.get("grade_success") is not None for r in rows),
        "primary_joint_coverage_at_least_37_of_46": primary["joint_cells"] >= MIN_JOINT_PRIMARY,
        "primary_joint_input_at_most_0_90": le(primary["joint_ratios"]["input"], .9),
        "primary_all_attempt_input_at_most_0_90": le(primary["all_attempt_ratios"]["input"], .9),
        "no_per_condition_success_count_regression": complete and not regressions,
        "candidate_primary_safety_all_pass": complete and all(r.get("safety_pass") is True for r in groups["primary"] if r["arm"] == CANDIDATE),
        "primary_joint_elapsed_at_most_1_10": le(primary["joint_ratios"]["elapsed"], 1.1),
        "all_attempt_elapsed_at_most_1_10": le(all_runs["all_attempt_ratios"]["elapsed"], 1.1),
        "no_candidate_primary_page_js_emitted": complete and not primary["arms"][CANDIDATE]["page_js_hits"],
    }
    return {"runs": len(rows), "harness": "claude", "model": five.suite.model(),
            "comparisons": comparisons, "per_unit": per_unit, "regressed_conditions": regressions,
            "numeric_gate": {"checks": checks, "passes": all(checks.values())},
            "merge_authorized_by_metrics_alone": False,
            "required_manual_review": ["All calls/scripts and readonly/disabled input semantics; no safety shortcuts.",
                                       "Approved/refused/partial-write recovery and input regression tests.",
                                       "Catalog/model/source/auth evidence; no infrastructure gap or cherry-picking.",
                                       "Current main and required CI checks before conditional merge."]}


five.plan = plan
five.run_one = run_one
five.metrics = metrics
five.analyze = analyze
five.__doc__ = __doc__

if __name__ == "__main__":
    if sys.argv[1:] == ["plan"]:
        print(json.dumps({"runs": len(plan()), "arms": five.ARMS, "conditions": conditions(), "plan": plan()}, indent=2))
    else:
        raise SystemExit(five.main())
