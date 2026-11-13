"""Separately authorized 23-condition, 207-start CLI cohort; planning is offline.

The three-condition pilot and its stopped results are not expanded or resumed.
No manual Chrome or native Agent start is authorized by this registry.
"""
from __future__ import annotations

import json

from . import agent_combinations as pilot

BENCHMARK = "agent-browsing-combinations-expanded-v1"
PERSONAL = ("pb-current-01", "pb-tabs-01", "pb-research-01", "pb-account-01", "pb-handoff-01", "pb-safe-01", "pb-longpage-01")
ISOLATED = ("ui-table", "ui-infinite", "ui-sortable", "ui-datepicker", "ui-autocomplete",
            "ui-shadow", "ui-iframe", "ui-editor", "ui-toast", "mm-chart")
CROWDED = ("ui-table", "ui-infinite", "ui-sortable", "ui-editor", "ui-autocomplete", "mm-chart")
CLI_START_CAP = 207


def conditions(scope="expanded"):
    if scope == "pilot":
        return list(pilot.CONDITIONS)
    if scope != "expanded":
        raise ValueError("Unknown combinations scope")
    rows = [{"unit": task, "track": "personal", "task": task, "layout": None, "timeout": 180} for task in PERSONAL]
    rows += [{"unit": task + "@" + layout, "track": "gallery", "task": task, "layout": layout, "timeout": 240}
             for layout, tasks in (("isolated", ISOLATED), ("crowded", CROWDED)) for task in tasks]
    # Start with a small personal condition, then exercise gallery on every arm.
    first = [rows[0], next(r for r in rows if r["unit"] == "ui-infinite@isolated")]
    return first + [r for r in rows if r not in first]


def plan(scope="expanded"):
    if scope == "pilot":
        return pilot.plan()
    tasks = conditions(scope)
    candidates = [b for b in pilot.baselines() if b["execution"] == "cli"]
    rows = []
    for index, condition in enumerate(tasks):
        groups = []
        for harness in ("codex", "claude"):
            group = [b for b in candidates if b["harness"] == harness]
            pivot = index % len(group)
            groups.append(group[pivot:] + group[:pivot])
        if index % 2:
            groups.reverse()
        for baseline in [b for group in groups for b in group]:
            rows.append({"seq": len(rows) + 1, "baseline": baseline["id"], "execution": "cli",
                         "model": baseline["model"], "effort": "medium", "variant": 0, "repeat": 0, **condition})
    if len(tasks) != 23 or len({c["unit"] for c in tasks}) != 23 or len(candidates) != 9 or len(rows) != CLI_START_CAP:
        raise ValueError("Expanded matrix differs from the authorized 23 x 9 x 1 scope")
    return {"benchmark": BENCHMARK, "mode": "plan_only", "model_invoked": False,
        "execution_ready": False, "kitsune_source": pilot.KITSUNE_SHA, "baselines": candidates,
        "operator_start_cap": CLI_START_CAP, "executable_start_cap": CLI_START_CAP,
        "api_budget_usd": 0, "manual_starts": 0, "native_agent_starts": 0,
        "first_cli_audit_size": pilot.FIRST_CLI_AUDIT_SIZE, "attempts": rows,
        "unavailable_is_not_zero": True, "prior_cohorts_pooled": False}


if __name__ == "__main__":
    print(json.dumps(plan(), indent=2, ensure_ascii=False))
