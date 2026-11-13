"""Approved, bounded pilot plan. Importing or planning never invokes a model.

This is a new cohort, not a continuation of any historical experiment. Runtime
readiness and a frozen manifest are required separately before execution.
"""
from __future__ import annotations

import json

BENCHMARK = "agent-browsing-combinations-pilot-v1"
KITSUNE_SHA = "14d9ceb29de7611d41d0564f3ed6c343180c276e"
KITSUNE_TOOLS = (
    "browser_ask_user", "browser_resume", "browser_run_python", "browser_tabs",
    "browser_take_screenshot", "browser_tools_call",
)
MODELS = {"codex": "gpt-6.1-sol", "claude": "claude-opus-5-5"}
CLI_SURFACES = {
    "kitsune-zen": {"label": "Kitsune + Zen", "browser": "private Zen", "tools": KITSUNE_TOOLS},
    "playwright": {"label": "Microsoft Playwright MCP", "browser": "private Chrome"},
    "aside": {"label": "Aside MCP REPL", "browser": "Aside app, scoped fixture tabs"},
    "ego": {"label": "EgoLite script wrapper", "browser": "EgoLite app, fixture TaskSpace"},
    "devtools": {"label": "Chrome DevTools MCP", "browser": "private Chrome"},
    "browser-harness": {"label": "Browser Harness MCP", "browser": "private Chrome"},
    "agent-browser": {"label": "agent-browser MCP", "browser": "private Chrome"},
}
CONDITIONS = (
    {"unit": "pb-longpage-01", "track": "personal", "task": "pb-longpage-01", "layout": None, "timeout": 180},
    {"unit": "ui-table@crowded", "track": "gallery", "task": "ui-table", "layout": "crowded", "timeout": 240},
    {"unit": "mm-chart@isolated", "track": "gallery", "task": "mm-chart", "layout": "isolated", "timeout": 240},
)
OPERATOR_START_CAP = 33
EXECUTABLE_START_CAP = 30
API_BUDGET_USD = 0
FIRST_CLI_AUDIT_SIZE = 9


def baselines() -> list[dict]:
    rows = []
    for harness, surfaces in (("codex", tuple(CLI_SURFACES)), ("claude", ("kitsune-zen", "playwright"))):
        for surface in surfaces:
            rows.append({"id": harness + "-" + surface, "harness": harness, "surface": surface,
                         "model": MODELS[harness], "effort": "medium", "execution": "cli",
                         "state": "preflight_pending", **CLI_SURFACES[surface]})
    rows += [
        {"id": "chrome-sidepanel", "execution": "manual", "model": None, "effort": None,
         "label": "Claude in Chrome side panel", "state": "manual_setup_pending",
         "browser": "operator's personal Chrome profile; no automated attachment",
         "usage": None, "exact_agent_elapsed": None, "tab_custody": None},
        {"id": "browser-use-agent", "execution": "native", "model": None, "effort": None,
         "label": "browser-use native Agent", "state": "blocked_no_api_budget",
         "reason": "No paid API, default cloud/gateway, OAuth repurposing or substitute model authorized"},
    ]
    return rows


def plan() -> dict:
    candidates = baselines()
    cli = [b for b in candidates if b["execution"] == "cli"]
    rows = []
    for index, condition in enumerate(CONDITIONS):
        groups = []
        for harness in ("codex", "claude"):
            group = [b for b in cli if b["harness"] == harness]
            pivot = index % len(group)
            groups.append(group[pivot:] + group[:pivot])
        if index % 2:
            groups.reverse()
        for baseline in [b for group in groups for b in group]:
            rows.append({"seq": len(rows) + 1, "baseline": baseline["id"], "execution": "cli",
                         "model": baseline["model"], "effort": baseline["effort"],
                         "variant": 0, "repeat": 0, **condition})
    for condition in CONDITIONS:
        rows.append({"seq": len(rows) + 1, "baseline": "chrome-sidepanel", "execution": "manual",
                     "model": None, "effort": None, "variant": 0, "repeat": 0, **condition})
    if len(rows) != EXECUTABLE_START_CAP or len(rows) > OPERATOR_START_CAP:
        raise ValueError("Pilot matrix differs from the authorized limits")
    return {"benchmark": BENCHMARK, "mode": "plan_only", "model_invoked": False,
            "execution_ready": False, "kitsune_source": KITSUNE_SHA, "baselines": candidates,
            "operator_start_cap": OPERATOR_START_CAP, "executable_start_cap": EXECUTABLE_START_CAP,
            "api_budget_usd": API_BUDGET_USD, "unused_native_agent_slots": 3,
            "first_cli_audit_size": FIRST_CLI_AUDIT_SIZE, "attempts": rows,
            "unavailable_is_not_zero": True,
            "next": "Validate runtimes, freeze evidence and implement the bounded runner; do not invoke historical run commands."}


if __name__ == "__main__":
    print(json.dumps(plan(), indent=2, ensure_ascii=False))
