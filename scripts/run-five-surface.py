"""Five-surface comparison: Kitsune, Playwright MCP, Aside, EgoLite, Claude in Chrome.

  plan                         print the 207-attempt matrix (no model calls)
  run --out DIR [--limit N]    run sequentially; resumable, never retries a started attempt
  summary --out DIR            per-arm table from runs.jsonl

Subscription CLIs only (Codex `gpt-6.1-sol`, Claude Code `claude-opus-5-5`, medium).
Runs continue automatically; they stop on a usage-limit error or three consecutive
operational failures (setup/harness/runner errors). Task failures do not stop a run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import statistics
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kitsune_benchmark import adapter
from kitsune_benchmark.agent_combinations import KITSUNE_SHA
from kitsune_benchmark.agent_combinations_runtime import runtime_pins
from kitsune_benchmark.five_surface import AB_CANDIDATES, BENCHMARK, SURFACES, plan, run_attempt
from kitsune_benchmark.smoke import source_revision

OPERATIONAL = {"setup_failed", "harness_error", "runner_error", "interrupted", "permission_blocked"}


def load_rows(out: Path) -> list[dict]:
    path = out / "runs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def append_row(out: Path, row: dict) -> None:
    with (out / "runs.jsonl").open("a") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def usage_limited(row: dict) -> bool:
    text = json.dumps([row.get("api_error"), row.get("error")]).lower()
    return any(word in text for word in ("usage_limit", "rate_limit", "quota", "usage limit"))


def ensure_manifest(out: Path, project: Path, scope: str = "main", candidate: Path | None = None) -> dict:
    treatment = plan(scope)
    path = out / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest["plan"] != json.loads(json.dumps(treatment)):
            raise ValueError("Matrix changed since this output directory was created")
        return manifest
    if source_revision(project) != {"revision": KITSUNE_SHA, "dirty": False}:
        raise ValueError(f"Kitsune checkout must be clean at {KITSUNE_SHA}")
    if scope in AB_CANDIDATES:
        sha = AB_CANDIDATES[scope][4]
        candidate = candidate or ROOT.parent / AB_CANDIDATES[scope][5]
        if source_revision(candidate) != {"revision": sha, "dirty": False}:
            raise ValueError(f"--candidate-project must be a clean checkout at {sha}")
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest = {"benchmark": BENCHMARK, "created_at": datetime.now(timezone.utc).isoformat(),
                "benchmark_revision": source_revision(ROOT), "kitsune_project": str(project.resolve()),
                "kitsune_sha": KITSUNE_SHA, "pins": runtime_pins(), "plan": treatment, "api_budget_usd": 0,
                "scope": scope, **({"candidate_project": str(candidate.resolve())} if scope in AB_CANDIDATES else {})}
    adapter.write_json(path, manifest)
    return manifest


def do_run(out: Path, project: Path, limit: int | None, arms: set[str] | None, scope: str = "main",
           candidate: Path | None = None) -> int:
    manifest = ensure_manifest(out, project, scope, candidate)
    total = len(manifest["plan"]["attempts"])
    done = {r["seq"] for r in load_rows(out)}
    pending = [r for r in manifest["plan"]["attempts"]
               if r["seq"] not in done and (arms is None or r["arm"] in arms)]
    consecutive, started = 0, 0
    for row in pending:
        if limit is not None and started >= limit:
            break
        folder = out / f"attempt-{row['seq']:03d}"
        if folder.exists():
            # Started earlier but never recorded: keep it as a failure, never retry.
            append_row(out, {**row, "execution_status": "interrupted", "scorable": False})
            continue
        if shutil.disk_usage(out).free < 2 * 1024 ** 3:
            print("STOP: less than 2 GiB free", file=sys.stderr)
            return 2
        folder.mkdir(mode=0o700)
        adapter.write_json(folder / "started.json", row)
        started += 1
        print(f"[{row['seq']}/{total}] {row['arm']} {row['unit']}", flush=True)
        try:
            candidate_sha = manifest["plan"].get("candidate_sha")
            project = manifest["candidate_project" if candidate_sha and row.get("kitsune_sha") == candidate_sha
                               else "kitsune_project"]
            result = run_attempt(row, folder / "work", Path(project))
        except Exception as error:  # Record and decide below; never retry the cell.
            (folder / "error.txt").write_text(traceback.format_exc())
            result = {**row, "execution_status": "runner_error", "scorable": False,
                      "error": type(error).__name__ + ": " + str(error)[:500]}
        append_row(out, result)
        print(f"  status={result['execution_status']} functional={result.get('functional_success')} "
              f"success={result.get('success')} input={result.get('input')} elapsed={result.get('elapsed')}", flush=True)
        if usage_limited(result):
            adapter.write_json(out / f"stopped-{row['seq']:03d}.json", {"seq": row["seq"], "reason": "usage limit"})
            print("STOP: usage limit; resume later with the same command", file=sys.stderr)
            return 3
        if result["execution_status"] == "permission_blocked":
            adapter.write_json(out / f"stopped-{row['seq']:03d}.json", {"seq": row["seq"], "reason": "permission prompt"})
            print("STOP: Claude in Chrome asked for site permission; allow 127.0.0.1 in the extension", file=sys.stderr)
            return 2
        consecutive = consecutive + 1 if result["execution_status"] in OPERATIONAL else 0
        if consecutive >= 3:
            adapter.write_json(out / f"stopped-{row['seq']:03d}.json",
                               {"seq": row["seq"], "reason": "three consecutive operational failures"})
            print("STOP: three consecutive operational failures", file=sys.stderr)
            return 2
    return 0


def median(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return statistics.median(values) if values else None


def fmt(value, digits=0):
    if value is None:
        return "–"
    return f"{value:,.{digits}f}"


def summary(out: Path) -> str:
    rows = load_rows(out)
    treatment = json.loads((out / "manifest.json").read_text())["plan"]
    arms = treatment["arms"]
    lines = ["| Model | Surface | Runs | Scorable | Functional success | Task success (v2) | "
             "Median input | Median output | Median calls | Median time (s) |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for arm in arms:
        mine = [r for r in rows if r["arm"] == arm["id"]]
        scorable = [r for r in mine if r.get("scorable")]
        functional = sum(r.get("functional_success") is True for r in scorable)
        success = sum(r.get("success") is True for r in scorable)
        lines.append(f"| {arm['model']} | {arm.get('label') or SURFACES[arm['surface']]} | {len(mine)} | {len(scorable)} | "
                     f"{functional}/{len(scorable)} | {success}/{len(scorable)} | "
                     f"{fmt(median(r.get('input') for r in scorable))} | {fmt(median(r.get('output') for r in scorable))} | "
                     f"{fmt(median(r.get('calls') for r in scorable), 1)} | "
                     f"{fmt(median(r.get('adjusted_elapsed') for r in scorable), 1)} |")
    tracks = ["| Model | Surface | personal | isolated | crowded |", "| --- | --- | ---: | ---: | ---: |"]
    for arm in arms:
        cells = []
        for track, layout in (("personal", None), ("gallery", "isolated"), ("gallery", "crowded")):
            mine = [r for r in rows if r["arm"] == arm["id"] and r["track"] == track and r.get("layout") == layout]
            cells.append(f"{sum(r.get('functional_success') is True for r in mine)}/{len(mine)}")
        tracks.append(f"| {arm['model']} | {arm.get('label') or SURFACES[arm['surface']]} | " + " | ".join(cells) + " |")
    statuses = {}
    for r in rows:
        statuses[r["execution_status"]] = statuses.get(r["execution_status"], 0) + 1
    return ("\n".join(lines) + "\n\nFunctional success by track:\n\n" + "\n".join(tracks)
            + f"\n\nAttempts recorded: {len(rows)}/{len(treatment['attempts'])}. Execution status: {json.dumps(statuses)}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("plan", "run", "summary"))
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/five-surface-v1")
    parser.add_argument("--kitsune-project", type=Path, default=ROOT.parent / "kitsune")
    parser.add_argument("--limit", type=int, help="maximum new attempts in this invocation")
    parser.add_argument("--arms", help="comma-separated arm ids (default: all nine)")
    parser.add_argument("--scope", choices=("main", "kitsune-owned", *AB_CANDIDATES), default="main",
                        help="kitsune-owned: Kitsune personal re-run with agent-owned starting tabs; "
                             "repl-ab / tabs-ab: Kitsune A/Bs against main")
    parser.add_argument("--candidate-project", type=Path,
                        help="A/B scopes: clean Kitsune checkout of the candidate (default: sibling worktree)")
    args = parser.parse_args()
    if args.action == "plan":
        print(json.dumps(plan(args.scope), indent=2, ensure_ascii=False))
        return 0
    if args.action == "summary":
        text = summary(args.out)
        (args.out / "summary.md").write_text(text)
        print(text)
        return 0
    arms = set(args.arms.split(",")) if args.arms else None
    if arms and arms - {a["id"] for a in plan(args.scope)["arms"]}:
        parser.error("Unknown arm id")
    return do_run(args.out, args.kitsune_project, args.limit, arms, args.scope, args.candidate_project)


if __name__ == "__main__":
    raise SystemExit(main())
