"""Claude subscription: 7 MiniWoB tasks x 5 arms x 2 repeats (70 attempts).

Kitsune main's standard 23-tool UI surface, patched scripting's 14 tools,
Playwright's standard 23 tools, ego lite's run_script, and Aside's repl.
All ratios compare jointly solved task/repeat cells; no pooling of old runs.
Installed Aside/ego browsers are NOT fresh private Firefox profiles.
See docs/experiments/2026-11-12-five-way-miniwob.md.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("claude_caps", ROOT / "scripts/run-claude-scripting-caps-ab.py")
claude = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(claude)
suite = claude.suite

from kitsune_benchmark import external, ego_mcp
from kitsune_benchmark.adapter import resolve, write_json
from kitsune_benchmark.claude_harness import claude_environment
from kitsune_benchmark.full_native import agent_calls
from kitsune_benchmark.miniwob import BenchmarkServer
from kitsune_benchmark.smoke import rewrite_json, run_pair, source_revision

BENCHMARK = "claude-five-way-miniwob-v1"
SHAS = {"main": "883d80eee2c85f81410352ea8f86b81e11a2b682",
        "scripting": "c698d408d1c77eb708e853649bde4085a0d87ac8"}
ARMS = {"kitsune-main": ("kitsune", "main", {}, external.TOOLS["kitsune"]),
        "kitsune-scripting": ("kitsune", "scripting", {"KITSUNE_SCRIPTING": "1"}, None),
        "playwright": ("playwright", "main", {}, external.TOOLS["playwright"]),
        "ego": ("ego", "main", {}, external.TOOLS["ego"]),
        "aside": ("aside", "main", {}, external.TOOLS["aside"])}
EXPECTED = dict(zip(ARMS, (23, 14, 23, 1, 1)))
suite.ab.EXPECTED_TOOLS = EXPECTED
SCRIPT_TOOLS = {"browser_run_python", "run_script", "repl"}
REWARD = re.compile(r"core\.|endEpisode|WOB_|EPISODE")
PAGE_JS = re.compile(r"\.evaluate\s*\(|Runtime\.(?:evaluate|callFunctionOn)")
MEASURES = ("input", "output", "cached_input", "requests", "calls", "elapsed", "cost", "script_calls", "script_errors")


def plan():
    names = list(ARMS)
    return [{"seq": i + 1, **row} for i, row in enumerate(
        {"track": "miniwob", "task": task, "repeat": repeat, "arm": arm}
        for repeat in range(2) for index, task in enumerate(suite.ab.MINIWOB)
        for arm in ((names[index % 5:] + names[:index % 5])[::1 if repeat == 0 else -1]))]


def vendor_pins():
    """Metadata only; never execute a browser script or call a vendor's own agent."""
    aside = str(Path.home() / ".local/bin/aside")
    ego = ego_mcp.find_binary()
    versions = {}
    for name, binary in (("aside_cli", aside), ("ego_cli", ego)):
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, check=True, timeout=30)
        versions[name] = (result.stdout + result.stderr).strip()
    files = {"aside_cli": Path(aside).resolve(), "ego_cli": Path(ego).resolve(),
             "aside_app": Path("/Applications/Aside.app/Contents/Info.plist"),
             "ego_app": Path("/Applications/ego lite.app/Contents/Info.plist")}
    for name in ("aside_app", "ego_app"):
        versions[name] = plistlib.loads(files[name].read_bytes())["CFBundleShortVersionString"]
    return {"versions": versions,
            "files": {name: {"path": str(p), "size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns}
                      for name, p in files.items()},
            "ego_guide_sha256": hashlib.sha256(ego_mcp.describe(ego).encode()).hexdigest()}


def preflight(projects):
    """Use the existing Kitsune MCP SDK in a worker; the benchmark has no MCP dependency."""
    env = claude_environment(resolve("claude"))
    commands = {
        "kitsune-main": ("uv", ["run", "--locked", "--project", projects["main"], "kitsune"]),
        "kitsune-scripting": ("uv", ["run", "--locked", "--project", projects["scripting"], "kitsune"]),
        "playwright": ("node", [str(ROOT / "node_modules/@playwright/mcp/cli.js"), "--browser", "firefox", "--isolated", "--headless"]),
        "ego": (sys.executable, [str(ROOT / "kitsune_benchmark/ego_mcp.py")]),
        "aside": (str(Path.home() / ".local/bin/aside"), ["mcp"]),
    }
    worker = '''import asyncio, json, sys
from datetime import timedelta
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    result = {}
    for arm, server in json.load(sys.stdin).items():
        async with stdio_client(StdioServerParameters(**server)) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=60)) as client:
                init = await client.initialize()
                listed = await client.list_tools()
                if listed.nextCursor:
                    raise ValueError("Unexpected paginated catalog: " + arm)
                result[arm] = {"tools": [t.model_dump(mode="json") for t in listed.tools],
                               "instructions": init.instructions, "server_info": init.serverInfo.model_dump(mode="json")}
    print(json.dumps(result))
asyncio.run(main())
'''
    servers = {arm: {"command": command, "args": args, "env": {**env, **ARMS[arm][2]}}
               for arm, (command, args) in commands.items()}
    done = subprocess.run(["uv", "run", "--locked", "--project", projects["main"], "python", "-c", worker],
                          input=json.dumps(servers), env=env, capture_output=True, text=True, timeout=180)
    if done.returncode:
        raise ValueError("Catalog preflight failed: " + done.stderr)
    result = json.loads(done.stdout)
    for arm, catalog in result.items():
        catalog["tools"] = [t for t in catalog["tools"] if ARMS[arm][3] is None or t["name"] in ARMS[arm][3]]
        if len(catalog["tools"]) != EXPECTED[arm]:
            raise ValueError(f"Unexpected preflight {arm} catalog size: {len(catalog['tools'])}")
    return result


def verify_sources(projects, benchmark_sha):
    for name, path in projects.items():
        if source_revision(path) != {"revision": SHAS[name], "dirty": False}:
            raise ValueError(f"Changed/dirty Kitsune {name} checkout")
    if source_revision(ROOT) != {"revision": benchmark_sha, "dirty": False}:
        raise ValueError("Changed/dirty benchmark checkout")


def run_one(row, projects):
    target, source, env, tools = ARMS[row["arm"]]
    spec = external.config()
    task = external.selected_tasks([row["task"]])[0]
    upstream = ROOT / spec["source_directory"]
    external.verify_source(upstream, spec["source_revision"])
    experiment = {**spec, "selected_task": task, "five_way": {"benchmark": BENCHMARK, **row},
                  "upstream_task_sha256": external.task_sha256(upstream, task["task_id"])}
    with BenchmarkServer(upstream, spec, task) as fixture:
        return run_pair(execute=True, kitsune_project=projects[source], executable="claude", harness="claude",
                        targets=(target,), kitsune_env=env, enabled_tools={target: tools} if tools else None,
                        artifact_scope="five-way-miniwob", experiment_spec=experiment,
                        task_for_target=fixture.begin, evaluate=fixture.evaluate)


def metrics(pair, arm):
    target = ARMS[arm][0]
    normalized = {"pair_dir": pair["pair_dir"], "results": {"kitsune": pair["results"][target]}}
    row = suite.metrics(normalized)
    scripts = [c for c in agent_calls(Path(row["run_dir"]) / "events.jsonl") if c["tool"] in SCRIPT_TOOLS]
    code = [json.dumps(c["arguments"], ensure_ascii=False) for c in scripts]
    row.update(target=target, script_calls=len(scripts), script_errors=sum(bool(c["error"]) for c in scripts),
               reward_pattern_hits=sum(len(REWARD.findall(s)) for s in code),
               page_js_hits=sum(len(PAGE_JS.findall(s)) for s in code),
               script_urls=[url for s in code for url in suite.ab.URL.findall(s)])
    return row


def do_run(args):
    projects = {"main": str(Path(args.main_project).resolve()), "scripting": str(Path(args.scripting_project).resolve())}
    benchmark_sha = suite.ab.git(ROOT, "rev-parse", "HEAD")
    verify_sources(projects, benchmark_sha)
    vendors = vendor_pins()
    out = Path(args.out)
    if (out / "stopped.json").exists():
        raise ValueError("Prior runner exception requires review; use a separate deliberate continuation")
    catalog_path = out / "catalog-preflight.json"
    if json.loads(catalog_path.read_text())["vendors"] != vendors:
        raise ValueError("Vendor preflight differs from current installation")
    manifest = {"benchmark": BENCHMARK, "harness": "claude", "model": suite.model(), "effort": "medium",
                "benchmark_sha": benchmark_sha, "projects": projects, "kitsune_shas": SHAS,
                "arms": ARMS, "expected_tools": EXPECTED, "plan": plan(), "vendors": vendors,
                "continue_unstarted": args.continue_unstarted,
                "catalog_preflight_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
                "limitations": ["Aside/ego use installed browsers, not fresh isolated profiles.",
                                "MiniWoB does not attest equal viewports or browser engines.",
                                "Code-execution tools are trusted local code, not an anti-cheating sandbox.",
                                "Pair headless/browser_binary fields describe Firefox setup, not the vendor browsers."],
                "runner_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (*suite.RUNNER_FILES, Path(__file__))}}
    # Canonicalize tuples before comparing to a stored JSON manifest.
    manifest = json.loads(json.dumps(manifest))
    path = out / "manifest.json"
    rows = suite.ab.load_log(out)
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Output belongs to different settings/source/vendor versions; use a new --out")
    if rows and not path.exists():
        raise ValueError("Prior rows have no manifest")
    for expected, row in zip(manifest["plan"], rows):
        if any(row.get(k) != v for k, v in expected.items()) or row.get("harness") != "claude" or suite.stop_reason(row, args.continue_unstarted):
            raise ValueError("Prior failed/incompatible attempt requires review, not automatic skipping")
    if len(rows) > len(manifest["plan"]):
        raise ValueError("Too many previous rows")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        write_json(path, manifest)
    remaining = manifest["plan"][len(rows):]
    for run in remaining[:args.limit] if args.limit is not None else remaining:
        verify_sources(projects, benchmark_sha)
        if vendor_pins() != vendors:
            raise ValueError("Vendor version/guide changed; stop for review")
        print(f"[{run['seq']}/70] {run['task']} r{run['repeat']} {run['arm']}", flush=True)
        pair = run_one(run, projects)
        row = {**run, "harness": "claude", "model": manifest["model"], **metrics(pair, run["arm"])}
        with (out / "runs.jsonl").open("a") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"    success={row['success']} input={row['input']} requests={row['requests']} calls={row['calls']} "
              f"tools={row['published']} scripts/errors={row['script_calls']}/{row['script_errors']}", flush=True)
        verify_sources(projects, benchmark_sha)
        if vendor_pins() != vendors:
            raise ValueError("Vendor version/guide changed during attempt; raw evidence retained")
        reason = suite.stop_reason(row, args.continue_unstarted)
        if reason:
            print(f"stop: {reason}; inspect {row['run_dir']}", file=sys.stderr)
            return 2
    return 0


def analyze(out):
    rows = suite.ab.load_log(out)
    by = defaultdict(dict)
    totals = {}
    for row in rows:
        by[(row["task"], row["repeat"])][row["arm"]] = row
    for arm in ARMS:
        selected = [r for r in rows if r["arm"] == arm]
        first = [r["first_input"] for r in selected if r["first_input"] is not None]
        totals[arm] = {"attempts": len(selected), "scorable": sum(r["scorable"] for r in selected),
                       "successes": sum(r["success"] for r in selected),
                       "unstarted": sum(suite.unstarted(r) for r in selected),
                       "first_input_median": statistics.median(first) if first else None,
                       **{key: round(sum(r[key] or 0 for r in selected), 6) for key in MEASURES},
                       "tool_errors": dict(sum((Counter(r["tool_errors"]) for r in selected), Counter())),
                       **{key: sum(r[key] for r in selected) for key in ("reward_pattern_hits", "page_js_hits")}}
    comparisons = {}
    for baseline in ("kitsune-main", "kitsune-scripting"):
        comparisons[baseline] = {}
        for arm in ARMS:
            joint = [v for v in by.values() if all(v.get(a, {}).get("scorable") and v[a]["success"] for a in (baseline, arm))]
            comparisons[baseline][arm] = {"joint_cells": len(joint), **{
                key: suite.ab.ratio(sum(v[arm][key] for v in joint), sum(v[baseline][key] for v in joint))
                for key in ("input", "output", "requests", "calls", "elapsed", "cost")}}
    return {"runs": len(rows), "harness": "claude", "arms": totals, "paired_ratios": comparisons,
            "all_five_joint_cells": sum(all(v.get(a, {}).get("success") and v[a]["scorable"] for a in ARMS) for v in by.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    probe = sub.add_parser("preflight")
    for child in (run, probe):
        child.add_argument("--main-project", default=str(ROOT / "artifacts/vendor/kitsune-main-883d80e"))
        child.add_argument("--scripting-project", default=str(ROOT.parent / "kitsune-scripting-caps-default"))
    run.add_argument("--limit", type=int)
    run.add_argument("--continue-unstarted", action="store_true")
    for child in (run, probe, sub.add_parser("analyze")):
        child.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.cmd == "preflight":
        catalogs = preflight({"main": args.main_project, "scripting": args.scripting_project})
        Path(args.out).mkdir(parents=True, exist_ok=True, mode=0o700)
        write_json(Path(args.out) / "catalog-preflight.json", {"vendors": vendor_pins(), "catalogs": catalogs})
        print(json.dumps({arm: len(value["tools"]) for arm, value in catalogs.items()}))
        return 0
    if args.cmd == "analyze":
        report = analyze(Path(args.out))
        rewrite_json(Path(args.out) / "analysis.json", report)
        print(json.dumps(report, indent=2))
        return 0
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    try:
        return do_run(args)
    except Exception as error:
        message = f"{type(error).__name__}: {error}"
        stopped = Path(args.out) / "stopped.json"
        if (Path(args.out) / "manifest.json").exists() and not stopped.exists():
            write_json(stopped, {"reason": message, "policy": "No automatic resume after a runner exception."})
        print(f"stop: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
