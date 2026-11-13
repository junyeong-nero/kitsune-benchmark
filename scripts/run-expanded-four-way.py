"""184 separate Codex Sol 6.1 subscription attempts; no continuation of the Opus cohort.

23 expanded conditions x two repeats x current/code-first/Aside/ego. Freeze and audit
first eight before continuing. No retries, replacement attempts, API fallback or merge.
"""
from collections import Counter
from dataclasses import replace
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("expanded_four_base", ROOT / "scripts/run-code-first-five-way.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
five = base.five

from kitsune_benchmark import gallery, personal
from kitsune_benchmark.adapter import harness_preflight, resolve, write_json
from kitsune_benchmark.expanded_session import prepare_relay
from kitsune_benchmark.full_native import agent_calls
from kitsune_benchmark.runtime import codex_environment
from kitsune_benchmark.smoke import run_pair, source_revision, private_ports

BENCHMARK = "codex-expanded-four-way-v1"
MODEL = "gpt-6.1-sol"
ARMS = {a: five.ARMS[a] for a in ("kitsune-default", "kitsune-code-first", "aside", "ego")}
EXPECTED = {"kitsune-default": 14, "kitsune-code-first": 6, "aside": 1, "ego": 1}
ISOLATED = ("ui-table", "ui-infinite", "ui-sortable", "ui-datepicker", "ui-autocomplete",
            "ui-shadow", "ui-iframe", "ui-editor", "ui-toast", "mm-chart")
CROWDED = ("ui-table", "ui-infinite", "ui-sortable", "ui-editor", "ui-autocomplete", "mm-chart")
PROTOCOL = ROOT / "docs/experiments/2026-11-13-expanded-four-way-codex.md"
FILES = (*five.RUNNER_FILES, Path(__file__), PROTOCOL,
         ROOT / "kitsune_benchmark/expanded_session.py", ROOT / "kitsune_benchmark/expanded_ego_mcp.py")
CONTEXT_PREFIX = "bm-expanded4-sol61-20261113-v1"
MEASURES = ("input", "cached_input", "output", "calls", "elapsed", "adjusted_elapsed")
UNAVAILABLE = ("model_requests", "first_request_input_tokens", "list_price_cost_usd")
UI_ONLY = (" Use only browser observation/input APIs; do not use page evaluate, page JavaScript, CDP, fetch, "
           "host filesystem/network access, hidden grading state, or readonly/disabled-field bypass. "
           "Browser screenshots and the documented screenshot-image handoff are permitted. "
           "Never inspect or attach unrelated real-user tabs, profiles, memories, or accounts.")


def conditions():
    rows = ([{"track": "personal", "task": task, "layout": None} for task in five.suite.ab.PERSONAL]
            + [{"track": "gallery", "task": task, "layout": layout}
               for layout, tasks in (("isolated", ISOLATED), ("crowded", CROWDED)) for task in tasks])
    first = [rows[0], next(r for r in rows if r["task"] == "ui-infinite" and r["layout"] == "isolated")]
    return [{**r, "unit": r["task"] + ("@" + r["layout"] if r["layout"] else "")}
            for r in first + [r for r in rows if r not in first]]


def plan():
    result, arms = [], list(ARMS)
    for repeat in range(2):
        for index, condition in enumerate(conditions()):
            rotated = arms[index % 4:] + arms[:index % 4]
            for arm in rotated if repeat == 0 else rotated[::-1]:
                result.append({"seq": len(result) + 1, **condition, "variant": 0, "repeat": repeat, "arm": arm})
    return result


def preflight(projects, only_arm=None):
    """Actual native tools/list, no fixture/browser/model. Normalize through the MCP SDK."""
    env = codex_environment(resolve("codex"))
    worker = '''import asyncio,json,sys
from datetime import timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
 out={}
 for arm,params in json.load(sys.stdin).items():
  async with stdio_client(StdioServerParameters(**params)) as (r,w):
   async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=60)) as c:
    i=await c.initialize(); t=await c.list_tools()
    if t.nextCursor: raise ValueError('Unexpected catalog pagination')
    out[arm]={'tools':[x.model_dump(mode='json',exclude_none=True) for x in t.tools],
              'instructions':i.instructions,'server_info':i.serverInfo.model_dump(mode='json',exclude_none=True)}
 print(json.dumps(out))
asyncio.run(main())'''
    servers = {}
    with tempfile.TemporaryDirectory(prefix="expanded-catalog-") as home:
        for arm, (target, source, settings, _) in ARMS.items():
            if only_arm is not None and arm != only_arm:
                continue
            isolated = {}
            if target == "kitsune":
                command, args = "uv", ["run", "--locked", "--project", projects[source], "python", "-c",
                                      "from kitsune.server import mcp; mcp.run(transport='stdio')"]
                http, ws = private_ports()
                isolated = {"KITSUNE_HOME": str(Path(home) / arm), "KITSUNE_HTTP_PORT": str(http),
                            "KITSUNE_WS_PORT": str(ws), "KITSUNE_TOKEN": "catalog-only", "KITSUNE_NO_BRIDGE_RESTART": "1"}
            elif target == "aside":
                command, args = str(Path.home() / ".local/bin/aside"), ["mcp"]
            else:
                command, args = sys.executable, [str(ROOT / "kitsune_benchmark/expanded_ego_mcp.py")]
            servers[arm] = {"command": command, "args": args, "env": {**env, **settings, **isolated}}
        done = subprocess.run(["uv", "run", "--locked", "--project", projects["main"], "python", "-c", worker],
                              input=json.dumps(servers), capture_output=True, text=True, env=env, timeout=180, check=True)
    catalogs = json.loads(done.stdout)
    for arm, catalog in catalogs.items():
        allowed = ARMS[arm][3]
        catalog["tools"] = [t for t in catalog["tools"] if allowed is None or t["name"] in allowed]
        if len(catalog["tools"]) != EXPECTED[arm]:
            raise ValueError("Unexpected catalog size for " + arm)
    return {a: five.canonical_catalog(c) for a, c in catalogs.items()}


def run_one(row, projects):
    target, source, settings, allowed = ARMS[row["arm"]]
    module = personal if row["track"] == "personal" else gallery
    config = {**module.config(), "model": MODEL, "reasoning_effort": "medium"}
    context = f"{CONTEXT_PREFIX}-{row['seq']:03d}"
    screenshots = ROOT / "artifacts/expanded-four-images" / context
    if row["track"] == "personal":
        task = personal.selected_tasks([row["task"]])[0]
        fixture = personal.PersonalServer(task, 0, report_viewport=True, elicitation="decline", user_channel=True)
        selected = task
    else:
        task = gallery.select([row["task"]])[0]
        fixture = gallery.GalleryServer(task, 0, row["layout"], "decline")
        selected = {"id": task.id, "category": task.category}
    with fixture:
        def begin(target):
            prepared = fixture.begin(target)
            suffix = UI_ONLY
            if target == "ego":
                suffix += (f" The harness already prepared TaskSpace {context!r}; resume exactly that space. "
                           "Use its existing pages; do not create/claim another space or call handOff/finish. "
                           "Leave the space open for grading; the harness cleans it up afterward. "
                           f"Screenshot directory: {str(screenshots)!r}.")
            elif target == "aside":
                suffix += (" This fresh REPL already has the fixture's pages in tabs and the current page in page. "
                           "Use these handles, not global listBrowserTabs/attach or profile discovery.")
            return replace(prepared, prompt=prepared.prompt + suffix)
        spec = {**config, "variant": 0, "layout": row["layout"], "selected_task": selected,
                "expanded_four_way": {"benchmark": BENCHMARK, **row}, "elicitation": "decline_after_2s"}
        common = dict(execute=True, kitsune_project=projects[source], executable="codex", harness="codex",
                      targets=(target,), enabled_tools={target: allowed} if allowed else None, kitsune_env=settings,
                      artifact_scope="expanded-four-way", record_catalog=True, experiment_spec=spec,
                      task_for_target=begin, prepare_server=prepare_relay(fixture, context, screenshots), evaluate=fixture.evaluate)
        if target == "kitsune":
            port = fixture.bidi_ports[target] if row["track"] == "personal" else fixture.kitsune_bidi_port
            common.update(kitsune_firefox_args=personal.user_channel_args(port),
                          kitsune_firefox_prefs=personal.USER_CHANNEL_PREFS, equalize_kitsune_viewport=True)
        if row["track"] == "personal":
            common["viewport_reports"] = fixture.viewport_reports
        return run_pair(**common)


def metrics(pair, arm):
    target = ARMS[arm][0]
    result = pair["results"][target]
    grade, usage = result.get("benchmark_evaluation") or {}, result.get("usage") or {}
    run_dir = Path(result["run_dir"])
    calls = agent_calls(run_dir / "events.jsonl")
    scripts = [c for c in calls if c["tool"] in five.SCRIPT_TOOLS]
    codes = [json.dumps(c["arguments"], ensure_ascii=False) for c in scripts]
    evidence = json.loads((Path(pair["pair_dir"]) / (target + "-session-evidence.json")).read_text())
    timing = result.get("timing") or {}
    raw = result.get("elapsed_sec")
    setup, inventory = timing.get("relay_setup_sec"), evidence.get("post_call_inventory_sec", 0)
    adjusted = raw - setup - inventory if raw is not None and setup is not None else None
    catalog = five.observed_catalog(pair["pair_dir"])
    return {"harness": result.get("harness"), "model": result.get("model"), "execution_status": result.get("execution_status"),
            "scorable": grade.get("scorable") is True, "success": grade.get("task_success") is True,
            "grade_success": grade.get("task_success"), "functional_success": grade.get("functional_success"),
            "safety_pass": grade.get("safety_pass"), "failure_class": grade.get("failure_class"),
            "input": usage.get("input_tokens"), "cached_input": usage.get("cached_input_tokens"),
            "output": usage.get("output_tokens"), "requests": None, "first_input": None, "cost": None,
            "calls": result.get("mcp_calls"), "elapsed": raw, "adjusted_elapsed": adjusted,
            "timing": timing, "post_call_inventory_sec": inventory,
            "published": len(catalog["tools"]) if catalog else None,
            "tools": dict(Counter(c["tool"] for c in calls)),
            "tool_errors": dict(Counter(c["tool"] for c in calls if c["error"])),
            "script_calls": len(scripts), "script_errors": sum(bool(c["error"]) for c in scripts),
            "page_js_hits": sum(len(five.PAGE_JS.findall(code)) for code in codes),
            "reward_pattern_hits": sum(len(five.REWARD.findall(code)) for code in codes),
            "outside_navigation": evidence.get("outside_navigation"), "violations": result.get("violations"),
            "run_dir": str(run_dir), "pair_dir": pair["pair_dir"]}


def totals(rows):
    return {"attempts": len(rows), "scorable": sum(r["scorable"] for r in rows),
            "successes": sum(r["success"] for r in rows),
            "safety_failures": sum(r.get("safety_pass") is False for r in rows),
            "safety_unknown": sum(r.get("safety_pass") is None for r in rows),
            "metrics": {m: {"known_total": sum(r[m] for r in rows if r.get(m) is not None),
                            "reported": sum(r.get(m) is not None for r in rows),
                            "missing": sum(r.get(m) is None for r in rows)} for m in MEASURES}}


def compare(rows, arms):
    cells = {}
    for row in rows:
        if row["arm"] not in arms:
            continue
        cell = cells.setdefault((row["unit"], row["repeat"]), {})
        if row["arm"] in cell:
            raise ValueError("Duplicate condition/repeat/arm")
        cell[row["arm"]] = row
    joint = [c for c in cells.values() if all(c.get(a, {}).get("scorable") and c[a]["success"] for a in arms)]
    selected = {a: totals([c[a] for c in joint]) for a in arms}
    all_rows = {a: totals([r for r in rows if r["arm"] == a]) for a in arms}
    ratios = {}
    if len(arms) == 2:
        b, c = arms
        for group, values in (("joint", selected), ("all_attempt", all_rows)):
            ratios[group] = {}
            for m in MEASURES:
                x, y = values[b]["metrics"][m], values[c]["metrics"][m]
                same_cells = ({(r["unit"], r["repeat"]) for r in rows if r["arm"] == b}
                              == {(r["unit"], r["repeat"]) for r in rows if r["arm"] == c})
                ratios[group][m] = (y["known_total"] / x["known_total"]
                                   if (group == "joint" or same_cells) and not x["missing"]
                                   and not y["missing"] and x["known_total"] else None)
    return {"arms": all_rows, "joint_cells": len(joint), "joint_totals": selected, "ratios": ratios}


def analyze(out):
    rows = five.suite.ab.load_log(out)
    groups = {"all": rows, "personal": [r for r in rows if r["track"] == "personal"]}
    groups.update({layout: [r for r in rows if r["layout"] == layout] for layout in ("isolated", "crowded")})
    return {"benchmark": BENCHMARK, "model": MODEL, "runs": len(rows), "planned": 184,
            "unavailable_metrics": UNAVAILABLE, "merge_authorized": False,
            "groups": {name: {"all_four": compare(selected, list(ARMS)),
                        "pairwise": {f"{b} -> {c}": compare(selected, (b, c)) for b, c in itertools.combinations(ARMS, 2)}}
                       for name, selected in groups.items()},
            "per_unit": {c["unit"]: compare([r for r in rows if r["unit"] == c["unit"]], list(ARMS)) for c in conditions()}}


def stop_reason(row):
    if row.get("harness") != "codex" or row.get("model") != MODEL:
        return "wrong harness or requested model"
    if row["execution_status"] != "completed_unscored" or not row["scorable"]:
        return "execution error or unscorable result"
    if any(row.get(k) is None for k in ("input", "output", "cached_input", "grade_success", "safety_pass", "adjusted_elapsed")):
        return "missing usage/grade/timing evidence"
    if row["adjusted_elapsed"] < 0:
        return "invalid adjusted timing"
    if row["published"] != EXPECTED[row["arm"]]:
        return "unexpected model-facing catalog"
    if row["outside_navigation"] or row["violations"]:
        return "out-of-fixture action or harness-policy violation"
    return None


def do_run(out, projects, limit):
    if (out / "stopped.json").exists():
        raise ValueError("Prior stop requires operator review, not automatic continuation")
    revision = source_revision(ROOT)["revision"]
    five.verify_sources(projects, revision)
    auth = harness_preflight("codex", resolve("codex"), codex_environment(resolve("codex")), model=MODEL)
    frozen = json.loads((out / "catalog-preflight.json").read_text())
    vendors = five.vendor_pins()
    if vendors != frozen["vendors"]:
        raise ValueError("Vendor pins changed since preflight")
    manifest = json.loads(json.dumps({"benchmark": BENCHMARK, "harness": "codex", "model": MODEL,
        "effort": "medium", "benchmark_sha": revision, "kitsune_shas": five.SHAS, "projects": projects,
        "arms": ARMS, "expected_tools": EXPECTED, "plan": plan(), "vendors": vendors,
        "auth": auth, "unavailable_metrics": UNAVAILABLE,
        "catalog_preflight_sha256": hashlib.sha256((out / "catalog-preflight.json").read_bytes()).hexdigest(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}}))
    rows = five.suite.ab.load_log(out)
    path = out / "manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError("Cohort settings/source differ; do not reuse this output")
    elif rows:
        raise ValueError("Rows without a manifest")
    else:
        write_json(path, manifest)
    if len(rows) > len(manifest["plan"]):
        raise ValueError("Too many rows")
    for row, wanted in zip(rows, manifest["plan"]):
        if any(row.get(k) != v for k, v in wanted.items()) or stop_reason(row):
            raise ValueError("Prior failed or incompatible row; do not skip/retry it")
    remaining = manifest["plan"][len(rows):]
    if len(rows) < 8:
        remaining = remaining[:8 - len(rows)]
    else:
        audit = json.loads((out / "first-eight-audit.json").read_text())
        first_eight = b"".join((out / "runs.jsonl").read_bytes().splitlines(keepends=True)[:8])
        if audit.get("continue") is not True or audit.get("first_eight_sha256") != hashlib.sha256(first_eight).hexdigest():
            raise ValueError("First-eight audit is missing, negative or does not match")
    (out / "catalogs").mkdir(exist_ok=True, mode=0o700)
    for wanted in remaining[:limit]:
        five.verify_sources(projects, revision)
        if five.vendor_pins() != vendors:
            raise ValueError("Vendor changed")
        arm, seq = wanted["arm"], wanted["seq"]
        before = preflight(projects, arm)
        write_json(out / "catalogs" / f"{seq:03d}-before.json", before)
        if before[arm] != frozen["catalogs"][arm]:
            raise ValueError("Pre-attempt catalog drift; no inference started for this cell")
        print(f"[{seq}/184] {wanted['unit']} r{wanted['repeat']} {arm}", flush=True)
        pair = run_one(wanted, projects)
        row = {**wanted, **metrics(pair, arm)}
        with (out / "runs.jsonl").open("a") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"    success={row['success']} input={row['input']} calls={row['calls']} elapsed={row['elapsed']} adjusted={row['adjusted_elapsed']}", flush=True)
        five.verify_sources(projects, revision)
        after = preflight(projects, arm)
        write_json(out / "catalogs" / f"{seq:03d}-after.json", after)
        reason = stop_reason(row)
        if five.vendor_pins() != vendors or after[arm] != frozen["catalogs"][arm] or five.observed_catalog(pair["pair_dir"]) != frozen["catalogs"][arm]:
            reason = reason or "Vendor or catalog changed"
        if reason:
            write_json(out / "stopped.json", {"reason": reason, "seq": seq, "run_dir": row["run_dir"]})
            print("STOP: " + reason, file=sys.stderr)
            return 2
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "preflight", "run", "analyze"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    projects = five.PROJECT_DEFAULTS
    if args.action == "plan":
        print(json.dumps({"model": MODEL, "attempts": 184, "plan": plan()}, indent=2))
        return 0
    if args.out is None or (args.limit is not None and args.limit <= 0):
        parser.error("--out and a positive --limit (if supplied) are required")
    args.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.action == "preflight":
        auth = harness_preflight("codex", resolve("codex"), codex_environment(resolve("codex")), model=MODEL)
        value = {"catalogs": preflight(projects), "vendors": five.vendor_pins(), "auth": auth}
        write_json(args.out / "catalog-preflight.json", value)
        print(json.dumps({a: len(c["tools"]) for a, c in value["catalogs"].items()}))
        return 0
    if args.action == "analyze":
        value = analyze(args.out)
        (args.out / "analysis.json").write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(value["groups"]["all"]["all_four"], indent=2))
        return 0
    try:
        return do_run(args.out, projects, args.limit)
    except Exception as error:
        if not (args.out / "stopped.json").exists():
            write_json(args.out / "stopped.json", {"reason": f"{type(error).__name__}: {error}"})
        print(f"STOP: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
