"""Run every graded track (personal 28×3 variants, gallery 21×3×2 layouts, MiniWoB) under one total budget.

Each track command gets the remaining budget via --budget-usd, so the suite as a whole never starts a pair
whose worst case would exceed it. A failed, stopped, malformed or incomplete track stops the suite
with exit 3 after the active target processes settle; ordinary scorable task failures do not.

By default the personal and gallery tracks run Playwright and Kitsune as two concurrent processes (--targets
playwright / --targets kitsune), each with its own fixture server, ports, profiles and half the remaining budget.
Both targets then share the machine, so elapsed time and CPU/RSS are measured under that contention.
--sequential restores one process per track with paired runs, Playwright-first unless --order selects otherwise.
MiniWoB (one pair) is sequential.

The default harness is `claude`: Claude Code on the claude.ai subscription login, which spends no API
credit and has no dollar cap. API-key harnesses (`claude-api`, `claude-api-full`) bill ANTHROPIC_API_KEY
credit and need --allow-api-billing plus --budget-usd and --max-budget-usd-per-run.

usage: uv run --locked python scripts/run-full-suite.py \
           --kitsune-project artifacts/vendor/kitsune-pinned --out artifacts/opus-full
       uv run --locked python scripts/run-full-suite.py --harness claude-api --allow-api-billing \
           --budget-usd 60 ...   # per-run cap follows the model: opus $1, sonnet $0.5, haiku $0.1
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def commands() -> list[tuple[str, list[str]]]:
    items = [(f"personal-v{v}", ["personal", "--all", "--variant", str(v)]) for v in range(3)]
    items += [(f"gallery-{layout}-v{v}", ["gallery", "--layout", layout, "--variant", str(v)])
              for layout in ("crowded", "isolated") for v in range(3)]
    items.append(("miniwob", ["benchmark"]))
    return items


def attempt_plan(attempts: int, order: str | None, sequential: bool) -> list[dict]:
    if attempts < 1:
        raise ValueError("--attempts must be positive.")
    if order is not None and not sequential:
        raise ValueError("--order requires --sequential; parallel targets have no order.")
    if order == "abba" and attempts % 2:
        raise ValueError("--order abba requires an even --attempts count (AB then BA).")
    return [{"attempt": i + 1, "order": ("ab" if i % 2 == 0 else "ba") if order == "abba"
             else (order or "ab") if sequential else None} for i in range(attempts)]


def suite_summary(entries: list[dict]) -> dict:
    def group(key):
        return {str(value) if value is not None else "parallel": [e for e in entries if e[key] == value]
                for value in dict.fromkeys(e[key] for e in entries)}
    return {"entries": entries, "by_order": group("order"), "by_attempt": group("attempt")}


def git_identity(project: str | Path, match: str | None = None) -> dict:
    """Revision and tag-relative name of a checkout, for grouping results by version."""
    def git(*argv: str) -> str | None:
        done = subprocess.run(["git", "-C", str(project), *argv], capture_output=True, text=True)
        return done.stdout.strip() if done.returncode == 0 else None
    pattern = ("--match", match) if match else ()
    return {"revision": git("rev-parse", "HEAD"), "describe": git("describe", "--tags", *pattern, "--dirty"),
            "tag": git("describe", "--tags", *pattern, "--abbrev=0")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model ID (default: claude-opus-5-5 for Claude harnesses, the config's "
                                         "Codex model for --harness codex)")
    parser.add_argument("--budget-usd", type=float, help="API-key harnesses only: total suite cap")
    parser.add_argument("--max-budget-usd-per-run", type=float,
                        help="API-key harnesses only: per-run cap (default: the model's entry in "
                             "claude_code.max_budget_usd_per_run_by_model)")
    parser.add_argument("--kitsune-project", required=True)
    parser.add_argument("--harness", default="claude", choices=("claude", "codex", "claude-api", "claude-api-full"))
    parser.add_argument("--allow-api-billing", action="store_true",
                        help="Confirm that an API-key harness may spend ANTHROPIC_API_KEY credit")
    parser.add_argument("--out", required=True)
    parser.add_argument("--spent-usd", type=float, default=0.0, help="Already spent toward the budget")
    parser.add_argument("--sequential", action="store_true",
                        help="One process per track running paired targets in turn, instead of the two in parallel")
    parser.add_argument("--attempts", type=int, default=1, help="Fresh attempts per track/variant/layout unit")
    parser.add_argument("--order", choices=("ab", "ba", "abba"),
                        help="A=Playwright, B=Kitsune; abba alternates AB and BA across even attempts; needs --sequential")
    args = parser.parse_args()
    try:
        plan = attempt_plan(args.attempts, args.order, args.sequential)
    except ValueError as exc:
        parser.error(str(exc))
    api = args.harness in ("claude-api", "claude-api-full")
    if args.model is None:
        if args.harness == "codex":
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from kitsune_benchmark.personal import config as personal_config
            args.model = personal_config()["model"]
        else:
            args.model = "claude-opus-5-5"
    if api and not args.allow_api_billing:
        parser.error(f"--harness {args.harness} bills API credit; pass --allow-api-billing, or use the default "
                     "--harness claude (subscription).")
    if api and args.budget_usd is None:
        parser.error("API-key harnesses need --budget-usd.")
    if api and args.max_budget_usd_per_run is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from kitsune_benchmark.adapter import per_run_cap, with_claude_overrides
        from kitsune_benchmark.personal import config as personal_config
        try:
            args.max_budget_usd_per_run = per_run_cap(with_claude_overrides(personal_config(), args.model))
        except ValueError as exc:
            parser.error(str(exc))
    if not api and (args.budget_usd is not None or args.max_budget_usd_per_run is not None):
        parser.error("--budget-usd/--max-budget-usd-per-run apply only to API-key harnesses.")
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        parser.error("--out must be empty; refusing to overwrite suite evidence.")
    out.mkdir(parents=True, exist_ok=True)
    spent = args.spent_usd
    manifest = {"model": args.model, "harness": args.harness, "budget_usd": args.budget_usd,
                "max_budget_usd_per_run": args.max_budget_usd_per_run,
                "kitsune_project": str(Path(args.kitsune_project).resolve()),
                "kitsune": git_identity(args.kitsune_project),
                "taskset": git_identity(Path(__file__).resolve().parent.parent, "taskset-*"),
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "targets_in_parallel": not args.sequential, "attempts": args.attempts,
                "order_policy": args.order, "attempt_plan": plan,
                "order_key": {"a": "playwright", "b": "kitsune"}, "commands": [name for name, _ in commands()]}
    (out / "suite-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    log = out / "suite-log.jsonl"
    all_entries = []
    for attempt in plan:
        attempt_dir = out if args.attempts == 1 else out / f"attempt-{attempt['attempt']:03d}"
        attempt_dir.mkdir(exist_ok=True)
        for name, argv in commands():
            remaining = args.budget_usd - spent if api else None
            worst_pair = 2 * args.max_budget_usd_per_run if api else 0.0
            if api and remaining < worst_pair:
                entries = [{"name": name, "skipped": "budget", "spent_usd": spent}]
            else:
                base = [sys.executable, "-m", "kitsune_benchmark", *argv, "--harness", args.harness,
                        *(["--claude-model", args.model] if args.harness != "codex" else ["--codex-model", args.model]),
                        *(["--max-budget-usd-per-run", str(args.max_budget_usd_per_run), "--allow-api-billing"] if api else []),
                        "--kitsune-project", args.kitsune_project, "--execute"]
                parallel = not args.sequential and name != "miniwob"
                def budget(amount):
                    return ["--budget-usd", str(round(amount, 6))] if api else []
                if parallel:
                    # Each half may start a run only while its own share covers that run's worst case.
                    share = remaining / 2 if api else 0.0
                    jobs = [(f"{name}-{target}", base + ["--targets", target, *budget(share)])
                            for target in ("playwright", "kitsune")]
                else:
                    jobs = [(name, base + ["--targets", "kitsune,playwright" if attempt["order"] == "ba"
                                      else "playwright,kitsune"]
                         + (budget(remaining) if name != "miniwob" else []))]
                started = time.time()
                print(f"[{time.strftime('%H:%M:%S')}] {name}: "
                      + (f"remaining ${remaining:.2f}" if api else "subscription harness, no dollar cap")
                      + (" (targets in parallel)" if parallel else ""), flush=True)
                running = []
                for label, command in jobs:
                    stdout, stderr = (attempt_dir / f"{label}.json").open("x"), (attempt_dir / f"{label}.err").open("x")
                    running.append((label, subprocess.Popen(command, stdout=stdout, stderr=stderr), stdout, stderr))
                entries = []
                for label, process, stdout, stderr in running:
                    code = process.wait()
                    stdout.close()
                    stderr.close()
                    try:
                        result = json.loads((attempt_dir / f"{label}.json").read_text())
                    except (OSError, ValueError):
                        result = {}
                    if not isinstance(result, dict):
                        result = {}
                    cost = result.get("estimated_cost_usd")
                    if cost is None and name == "miniwob" and api:
                        cost = worst_pair  # not reported by the MiniWoB runner; count its worst case
                    spent += cost or 0.0
                    entries.append({"name": name, **({"target": label.rsplit("-", 1)[1]} if parallel else {}),
                                    "exit": code, "summary_valid": bool(result),
                                    "seconds": round(time.time() - started, 1),
                                    "cost_usd": cost, "spent_usd": round(spent, 6),
                                    "attempted_pairs": result.get("attempted_pairs"),
                                    "requested_pairs": result.get("requested_pairs"),
                                    "completed_pairs": result.get("completed_pairs"),
                                    "stopped_reason": result.get("stopped_reason"),
                                    "suite_summary_path": result.get("suite_summary_path"),
                                    "by_target": result.get("by_target", result.get("results")),
                                    "output_path": str(attempt_dir / f"{label}.json")})
            for entry in entries:
                entry.update(attempt=attempt["attempt"], order=attempt["order"] if name != "miniwob" else attempt["order"] or "ab")
                all_entries.append(entry)
                print(json.dumps(entry), flush=True)
                with log.open("a") as handle:
                    handle.write(json.dumps(entry) + "\n")
            (out / "suite-summary.json").write_text(json.dumps(suite_summary(all_entries), indent=2) + "\n")
            # Wait for the active track's peers above, but never consume more model
            # usage on later tracks after an invalid execution. MiniWoB reports a
            # single pair (no suite counts); its nonzero exit signals unscorability.
            failed = [entry for entry in entries if not entry.get("skipped") and (
                entry.get("exit") != 0 or not entry.get("summary_valid") or entry.get("stopped_reason") or
                (name != "miniwob" and (entry.get("requested_pairs") is None or
                 entry.get("completed_pairs") != entry.get("requested_pairs"))))]
            if failed:
                print(f"stopped: incomplete track {name}; no later tracks started", flush=True)
                return 3
    print(f"done; estimated spend ${spent:.2f} of ${args.budget_usd:.2f}" if api
          else "done; subscription harness (usage counts against the plan's limits, not API credit)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
