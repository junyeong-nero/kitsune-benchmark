"""CLI: model execution requires `run` or an explicit `--execute`."""

from __future__ import annotations

import argparse
import json
import subprocess

from .adapter import API_HARNESSES, HARNESSES, plan, run, with_claude_overrides
from . import claude_harness
from .doctor import diagnose
from .specs import load_server, load_task
from .smoke import experiment as smoke_experiment, run_pair
from .miniwob import UI_TOOLS
from pathlib import Path
from .external import run_external
from .gallery import run_gallery
from .personal import config as personal_config, pair_complete, run_personal, runnable_ids
from .personal_session import ELICITATION_POLICIES
from .coexistence import run_coexistence
from .hostile import run_hostile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kitsune browser MCP benchmark tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="Check Codex prerequisites without a model call")
    doctor.add_argument("--codex", default="codex", help="Codex executable name or path")
    doctor.add_argument("--codex-home", help="Existing Codex home to check; no credentials are copied")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    doctor.add_argument("--harness", choices=HARNESSES, default="claude")
    doctor.add_argument("--claude", default="claude", help="Claude Code executable name or path")
    for name in ("plan", "run"):
        child = subparsers.add_parser(name, help=(
            "Print configuration without invoking Codex" if name == "plan"
            else "Invoke Codex; consumes subscription usage"))
        child.add_argument("--server", required=True, help="Server JSON configuration")
        child.add_argument("--task", required=True, help="Task JSON configuration")
        child.add_argument("--model", required=True, help="Explicit subscription-accessible model ID")
        child.add_argument("--codex", default="codex")
        child.add_argument("--timeout", type=int, default=300, help="Wall-clock seconds per run")
        if name == "run":
            child.add_argument("--codex-home", help="Auth home; its config.toml is ignored")
            child.add_argument("--output-root", default="runs")
            child.add_argument("--confirm-isolated-browser", action="store_true",
                               help="Confirm a dedicated test browser/profile, not your everyday session")
    smoke = subparsers.add_parser("smoke", help="Plan or explicitly execute the isolated smoke pair")
    smoke.add_argument("--execute", action="store_true", help="Start private browsers and consume subscription quota")
    smoke.add_argument("--codex", default="codex")
    smoke.add_argument("--kitsune-project", help="Kitsune source checkout; defaults to sibling directory")
    smoke.add_argument("--timeout", type=int, help="Wall-clock seconds per agent run")
    smoke.add_argument("--task", dest="task_file", help="Task JSON ({id, prompt}) instead of the default read-only smoke task")
    smoke.add_argument("--ui-tools", action="store_true", help="Expose only the benchmark UI tool allowlist to each MCP")
    smoke.add_argument("--targets", default="playwright,kitsune", help="Comma-separated MCPs to run")
    benchmark = subparsers.add_parser("external", aliases=["benchmark"], help="External track: 7 MiniWoB++ tasks "
                                      "(upstream reward) + 3 ungraded live public-web tasks; plan by default")
    benchmark.add_argument("--execute", action="store_true", help="Run selected pairs; consumes quota or API credit")
    benchmark.add_argument("--fetch", action="store_true", help="Download the pinned upstream source, without inference unless --execute")
    benchmark.add_argument("--task", action="append", dest="task_ids", help="External task ID; repeatable; default all 10")
    benchmark.add_argument("--kind", choices=("miniwob", "live"), help="Only MiniWoB or only live tasks")
    benchmark.add_argument("--codex", default="codex")
    benchmark.add_argument("--kitsune-project")
    benchmark.add_argument("--targets", default="playwright,kitsune")
    benchmark.add_argument("--budget-usd", type=float)
    personal = subparsers.add_parser("personal", help="Personal browsing: 28 runnable local tasks (six-task pilot by default); plan by default")
    personal.add_argument("--execute", action="store_true", help="Run selected pairs; consumes subscription quota")
    personal.add_argument("--task", action="append", dest="task_ids", help="Runnable task ID; repeat to select several; default: six pilot tasks")
    personal.add_argument("--all", action="store_true", help="Select all 28 runnable tasks (56 agent runs with --execute)")
    personal.add_argument("--variant", type=int, choices=(0, 1, 2), default=0)
    personal.add_argument("--codex", default="codex")
    personal.add_argument("--kitsune-project")
    personal.add_argument("--kitsune-preset", help="Set KITSUNE_TOOL_PRESET for Kitsune (e.g. lean) for A/B arms")
    personal.add_argument("--targets", default="playwright,kitsune",
                          help="Comma-separated MCPs to run: playwright,kitsune (default both)")
    personal.add_argument("--unprotected-user-tabs", action="store_true",
                          help="Kitsune arm with KITSUNE_PROTECT_USER_TABS=0 KITSUNE_HOLD_VIEWED_TAB=0, outside "
                               "personal-browsing-local-v3 (reported separately)")
    personal.add_argument("--budget-usd", type=float,
                          help="claude-api only: stop before a pair whose worst case would exceed this total")
    gallery = subparsers.add_parser("gallery", help="Component gallery + multimodal puzzles (21 tasks); plan by default")
    gallery.add_argument("--execute", action="store_true", help="Run selected tasks; consumes quota or API credit")
    gallery.add_argument("--task", action="append", dest="task_ids", help="Gallery task ID; repeatable; default all 21")
    gallery.add_argument("--category", choices=("ui", "multimodal", "judgement"))
    gallery.add_argument("--layout", choices=("crowded", "isolated"), default="crowded")
    gallery.add_argument("--variant", type=int, choices=(0, 1, 2), default=0)
    gallery.add_argument("--codex", default="codex")
    gallery.add_argument("--kitsune-project")
    gallery.add_argument("--kitsune-preset")
    gallery.add_argument("--targets", default="playwright,kitsune")
    gallery.add_argument("--budget-usd", type=float)
    coexistence = subparsers.add_parser("coexistence", help="Coexistence track (coexistence-local-v1): user-seeded tabs, a simulated "
                                        "user and view telemetry; plan by default")
    coexistence.add_argument("--execute", action="store_true", help="Run selected pairs; consumes quota or API credit")
    coexistence.add_argument("--task", action="append", dest="task_ids",
                             help="Runnable co-* task, or a personal pb-* task to run user-seeded; repeatable; "
                                  "default: runnable co-* tasks")
    coexistence.add_argument("--all-personal", action="store_true", help="All 28 personal tasks under the user-seeded condition")
    coexistence.add_argument("--protect-user-tabs", action="store_true",
                             help="Kitsune arm with KITSUNE_PROTECT_USER_TABS=1 (reported separately)")
    coexistence.add_argument("--unprotected-user-tabs", action="store_true",
                             help="Kitsune arm with KITSUNE_PROTECT_USER_TABS=0 KITSUNE_HOLD_VIEWED_TAB=0, outside "
                                  "coexistence-local-v1 (reported separately)")
    coexistence.add_argument("--variant", type=int, choices=(0, 1, 2), default=0)
    coexistence.add_argument("--codex", default="codex")
    coexistence.add_argument("--kitsune-project")
    coexistence.add_argument("--targets", default="playwright,kitsune")
    coexistence.add_argument("--budget-usd", type=float)
    hostile = subparsers.add_parser("hostile", help="Hostile-UI capability matrix: real-web components x tool strategies, "
                                    "no model calls; plan by default")
    hostile.add_argument("--execute", action="store_true", help="Start isolated browsers and run the matrix (no model)")
    hostile.add_argument("--component", action="append", dest="component_ids", help="Component ID; repeatable")
    hostile.add_argument("--targets", default="playwright,kitsune")
    hostile.add_argument("--kitsune-project")
    hostile.add_argument("--headed", action="store_true", help="Show the browser windows")
    hostile.add_argument("--trusted", action="store_true",
                         help="Also run OS-input strategies (browser_trusted_click, Kitsune only); needs --headed and "
                              "moves the real pointer")
    hostile.add_argument("--out", help="Output directory (default artifacts/hostile/runs/<UTC time>)")
    for child in (personal, gallery, coexistence):
        child.add_argument("--elicitation", choices=ELICITATION_POLICIES, default="decline",
                           help="How the relay answers Kitsune's approval prompts during the agent's turn: decline "
                                "(default) or accept; browser_ask_user prompts are always declined. Results under "
                                "different policies are not comparable")
    for child in (smoke, benchmark, personal, gallery, coexistence):
        child.add_argument("--harness", choices=HARNESSES, default="claude",
                           help="Agent CLI. Default claude (Claude Code on the claude.ai subscription login; "
                                "no API credit). codex (ChatGPT login). claude-api (Claude Code --bare, "
                                "ANTHROPIC_API_KEY from .env; billed per token) or claude-api-full (same key, no "
                                "--bare: full tool descriptions); both need --allow-api-billing to execute")
        child.add_argument("--allow-api-billing", action="store_true",
                           help="Confirm that an API-key harness may spend ANTHROPIC_API_KEY credit")
        child.add_argument("--claude", default="claude", help="Claude Code executable name or path")
        child.add_argument("--claude-model", help="Claude harnesses only: override the config's claude_code.model "
                           "(e.g. claude-opus-5-5); the override is recorded in each run's manifest")
        child.add_argument("--max-budget-usd-per-run", type=float,
                           help="claude-api harnesses only: override claude_code.max_budget_usd_per_run")
        child.add_argument("--codex-model", help="Codex harness only: override the config's model "
                           "(e.g. gpt-6.1-sol); the override is recorded in each run's manifest")
    doctor.add_argument("--claude-model", help="Model ID to validate with the claude-api harnesses")
    args = parser.parse_args(argv)
    claude = getattr(args, "harness", "codex").startswith("claude")
    executable = getattr(args, "claude", None) if claude else getattr(args, "codex", None)
    overrides = {"claude_model": getattr(args, "claude_model", None),
                 "max_budget_usd_per_run": getattr(args, "max_budget_usd_per_run", None)}
    if args.command != "doctor" and not claude and any(value is not None for value in overrides.values()):
        parser.error("--claude-model/--max-budget-usd-per-run need a Claude harness (--harness claude*).")
    if getattr(args, "codex_model", None) is not None:
        if claude:
            parser.error("--codex-model needs --harness codex.")
        overrides["codex_model"] = args.codex_model
    if (getattr(args, "execute", False) and getattr(args, "harness", None) in API_HARNESSES
            and not args.allow_api_billing):
        parser.error(f"--harness {args.harness} bills API credit (ANTHROPIC_API_KEY). The default --harness claude "
                     "uses the claude.ai subscription; pass --allow-api-billing to spend API credit deliberately.")
    try:
        if args.command == "doctor":
            if claude:
                api = args.harness in ("claude-api", "claude-api-full")
                model = (args.claude_model or personal_config()["claude_code"]["model"]) if api else None
                report = claude_harness.diagnose(args.claude, api=api, model=model)
            else:
                report = diagnose(args.codex, args.codex_home)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                for check in report["checks"]:
                    print(f"{'OK' if check['passed'] else 'FAIL'} {check['name']}: {check['detail']}")
                print("No model invoked. These checks do not certify benchmark readiness.")
            return 0 if report["prerequisites_ok"] else 2
        if args.command == "personal":
            if args.all and args.task_ids:
                raise ValueError("Use either --all or --task.")
            result = run_personal(execute=args.execute, task_ids=runnable_ids() if args.all else args.task_ids, variant=args.variant,
                                  executable=executable, kitsune_project=args.kitsune_project,
                                  harness=args.harness, budget_usd=args.budget_usd,
                                  kitsune_preset=args.kitsune_preset, targets=tuple(args.targets.split(",")),
                                  elicitation=args.elicitation, unprotected_user_tabs=args.unprotected_user_tabs,
                                  **overrides)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            return 0 if result["completed_pairs"] == result["requested_pairs"] and all(
                pair_complete(pair, tuple(result["targets"])) for pair in result["pairs"]) else 3
        if args.command == "coexistence":
            if args.all_personal and args.task_ids:
                raise ValueError("Use either --all-personal or --task.")
            result = run_coexistence(execute=args.execute, task_ids=runnable_ids() if args.all_personal else args.task_ids,
                                     variant=args.variant, kitsune_project=args.kitsune_project, executable=executable,
                                     harness=args.harness, budget_usd=args.budget_usd,
                                     protect_user_tabs=args.protect_user_tabs, elicitation=args.elicitation,
                                     unprotected_user_tabs=args.unprotected_user_tabs,
                                     targets=tuple(args.targets.split(",")), **overrides)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            return 0 if result["completed_pairs"] == result["requested_pairs"] else 3
        if args.command == "hostile":
            result = run_hostile(execute=args.execute, component_ids=args.component_ids,
                                 targets=tuple(args.targets.split(",")), kitsune_project=args.kitsune_project,
                                 headed=args.headed, trusted=args.trusted, out=args.out)
            if args.execute:
                print(result["matrix"])
                print(f"results: {result['out_dir']}")
            else:
                print(json.dumps({k: v for k, v in result.items() if k != "plan"}, indent=2))
            return 0
        if args.command == "gallery":
            result = run_gallery(execute=args.execute, task_ids=args.task_ids, category=args.category, variant=args.variant,
                                 layout=args.layout, kitsune_project=args.kitsune_project, executable=executable,
                                 harness=args.harness, budget_usd=args.budget_usd, kitsune_preset=args.kitsune_preset,
                                 targets=tuple(args.targets.split(",")), elicitation=args.elicitation, **overrides)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            return 0 if result["completed_pairs"] == result["requested_pairs"] else 3
        if args.command in ("external", "benchmark"):
            result = run_external(execute=args.execute, fetch=args.fetch, task_ids=args.task_ids, kind=args.kind,
                                  executable=executable, kitsune_project=args.kitsune_project,
                                  harness=args.harness, budget_usd=args.budget_usd,
                                  targets=tuple(args.targets.split(",")), **overrides)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            return 0 if result["completed_pairs"] == result["requested_pairs"] else 3
        if args.command == "smoke":
            spec = with_claude_overrides(smoke_experiment(), overrides["claude_model"],
                                         overrides["max_budget_usd_per_run"], overrides.get("codex_model"))
            if args.task_file:
                load_task(args.task_file)  # validate before any process starts
                spec = {**spec, "task": str(Path(args.task_file).resolve())}
            targets = tuple(args.targets.split(","))
            result = run_pair(execute=args.execute, kitsune_project=args.kitsune_project,
                              executable=executable, timeout=args.timeout, harness=args.harness,
                              experiment_spec=spec, targets=targets,
                              enabled_tools=UI_TOOLS if args.ui_tools else None)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            results = result["results"]
            return 0 if len(results) == len(targets) and all(
                item["execution_status"] == "completed_unscored" for item in results.values()) else 3
        server, task = load_server(args.server), load_task(args.task)
        if args.command == "plan":
            result = plan(server, task, args.model, args.codex, args.timeout)
        else:
            result = run(server, task, args.model, executable=args.codex,
                         codex_home=args.codex_home, timeout=args.timeout,
                         output_root=args.output_root,
                         confirm_isolated_browser=args.confirm_isolated_browser)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "plan" or result["execution_status"] == "completed_unscored":
            return 0
        return 3
    except (OSError, ValueError, subprocess.SubprocessError):
        # JSON/OS exceptions may include config lines, paths, or secrets.
        # Do not echo raw exception text to automated logs.
        print("Preflight/input error. Check CLI location/login, input schema, explicit model, "
              "required environment, and isolated-browser confirmation. No API fallback.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
