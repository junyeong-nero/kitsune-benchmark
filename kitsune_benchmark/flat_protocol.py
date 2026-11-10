"""#504 preregistration checker/scheduler only. No browser, model, executor or approval authority."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "configs/experiments/kitsune-flat-504-v1.json"
DOCUMENT = ROOT / "docs/experiments/2026-11-10-kitsune-flat-504-protocol.md"
FROZEN_INPUTS = frozenset((
    "tasks/personal/catalog.json", "tasks/coexistence/catalog.json",
    "kitsune_benchmark/personal.py", "kitsune_benchmark/personal_fixtures.py",
    "kitsune_benchmark/gallery.py", "kitsune_benchmark/gallery_media.py",
    "kitsune_benchmark/gallery_static/gallery.css", "kitsune_benchmark/gallery_static/gallery.js",
    "kitsune_benchmark/coexistence.py", "kitsune_benchmark/coexistence_fixtures.py",
    "configs/benchmarks/personal.json", "configs/benchmarks/gallery.json",
    "configs/benchmarks/coexistence.json", "package-lock.json", "uv.lock",
))


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def load() -> dict:
    return json.loads(CONFIG.read_text())


def input_errors(hashes: dict, root: Path = ROOT) -> list[str]:
    errors = []
    for name, expected in hashes.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append(f"Input outside repository: {name}")
            continue
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f"Frozen input changed or missing: {name}")
    return errors


def validate(spec: dict, root: Path = ROOT) -> None:
    """Validate this fixed experiment, not a general workflow/configuration language."""
    if (spec["schema_version"] != 1 or spec["id"] != "kitsune-flat-504-v1"
            or spec["status"] != "methods_preregistered_not_executable"):
        raise ValueError("Expected #504 v1 methods-only preregistration, not execution approval.")
    if set(spec["frozen_inputs"]) != FROZEN_INPUTS:
        raise ValueError("The full fixture/grader/configuration hash set is required.")
    errors = input_errors(spec["frozen_inputs"], root)
    if errors:
        raise ValueError("; ".join(errors))
    catalog = json.loads((root / "tasks/personal/catalog.json").read_text())
    runnable = [task["id"] for task in catalog["tasks"] if task["status"] == "runnable"]
    if spec["personal_units"] != runnable:
        raise ValueError("Use all personal units in frozen catalog order; no favorable subset.")
    extra = spec["additional_units"]
    if ([(u["id"], u["track"], u["task"], u["layout"], u["primary"]) for u in extra]
            != [("co-typing-01", "coexistence", "co-typing-01", None, True),
                ("ui-table/crowded", "gallery", "ui-table", "crowded", False),
                ("ui-table/isolated", "gallery", "ui-table", "isolated", False)]):
        raise ValueError("Typing is primary; both fixed gallery layouts are separate diagnostics.")
    model = spec["model"]
    if model != {"harness": "claude", "id": "claude-opus-5-5", "effort": "medium",
                 "cli_version": "2.1.303", "api_billing": False, "fallback": False, "bare": False}:
        raise ValueError("Model, rendering and subscription authentication must match preregistration.")
    for track in ("personal", "coexistence", "gallery"):
        config = json.loads((root / f"configs/benchmarks/{track}.json").read_text())
        if (config["claude_code"]["model"], config["claude_code"]["effort"], config["claude_code"]["version"]
                ) != (model["id"], model["effort"], model["cli_version"]):
            raise ValueError("Existing track model pins differ.")
    if spec["common_env"] != {"KITSUNE_MODE": "act", "KITSUNE_USER_TABS": "read-only",
                              "KITSUNE_PROTECT_USER_TABS": None, "KITSUNE_HOLD_VIEWED_TAB": None}:
        raise ValueError("No user-tab permission widening or mode change.")
    arms = spec["arms"]
    if set(arms) != set("ABCD"):
        raise ValueError("Four named arms are required.")
    for arm in "AB":
        if arms[arm] != {"source": "baseline", "env": {
                "KITSUNE_CAPS": "core" if arm == "A" else "all", "KITSUNE_PUBLISH": None if arm == "A" else "core",
                "KITSUNE_INTERFACE": None, "KITSUNE_SCRIPTING": None}}:
            raise ValueError("Legacy core/gateway reference configuration changed.")
    for arm in "CD":
        if arms[arm] != {"source": "candidate", "env": {"KITSUNE_CAPS": None, "KITSUNE_PUBLISH": None,
                "KITSUNE_INTERFACE": "flat", "KITSUNE_SCRIPTING": "off" if arm == "C" else "python"}}:
            raise ValueError("C/D must share one candidate/configuration except scripting.")
    design = spec["design"]
    if (type(design["variant"]) is not int or design["variant"] != 0
            or type(design["repetitions"]) is not int or design["repetitions"] != 4
            or design["sequential"] is not True or design["automatic_retries"] != 0
            or design["elicitation"] != "decline"):
        raise ValueError("Variant 0, four sequential repetitions, decline and no retries are fixed.")
    orders = design["arm_orders"]
    if (len(orders) != 4 or any(len(order) != 4 or set(order) != set("ABCD") for order in orders)
            or any(set(order[p] for order in orders) != set("ABCD") for p in range(4))
            or Counter(pair for order in orders for pair in zip(order, order[1:]))
            != Counter((a, b) for a in "ABCD" for b in "ABCD" if a != b)):
        raise ValueError("Orders must balance every position and directed adjacent pair.")
    if not spec["pending_execution_lock"]:
        raise ValueError("Missing execution pins/evidence/approval must remain explicit.")


def units(spec: dict, root: Path = ROOT) -> list[dict]:
    catalog = json.loads((root / "tasks/personal/catalog.json").read_text())
    by_id = {task["id"]: task for task in catalog["tasks"]}
    return [{"id": task, "track": "personal", "task": task, "layout": None,
             "category": by_id[task]["category"], "primary": True} for task in spec["personal_units"]] + spec["additional_units"]


def schedule(spec: dict, selected: list[dict]) -> list[dict]:
    rows = []
    design = spec["design"]
    for repetition in range(design["repetitions"]):
        def order_key(index):
            unit = selected[index]["id"]
            key = f"{design['unit_order_seed']}:{repetition}:{unit}".encode()
            return hashlib.sha256(key).hexdigest(), unit
        for index in sorted(range(len(selected)), key=order_key):
            unit = selected[index]
            order = design["arm_orders"][(repetition + index) % 4]
            for position, arm in enumerate(order):
                rows.append({**unit, "repetition": repetition, "variant": design["variant"],
                             "arm": arm, "position": position, "order": order,
                             "timeout_sec": design["timeouts_sec"][unit["track"]]})
    return rows


def plan(spec: dict | None = None) -> dict:
    spec = load() if spec is None else spec
    validate(spec)
    selected = units(spec)
    jobs = schedule(spec, selected)
    return {"protocol": spec["id"], "mode": "plan_only", "model_invoked": False,
            "execution_supported": False, "execution_approved": False,
            "protocol_json_sha256": digest(spec), "protocol_document_sha256": hashlib.sha256(DOCUMENT.read_bytes()).hexdigest(),
            "model": spec["model"], "units": len(selected), "primary_units": sum(u["primary"] for u in selected),
            "planned_model_runs": len(jobs), "runs_per_arm": dict(Counter(job["arm"] for job in jobs)),
            "agent_deadline_sum_hours": sum(job["timeout_sec"] for job in jobs) / 3600,
            "schedule_sha256": digest(jobs), "schedule": jobs,
            "pending_execution_lock": spec["pending_execution_lock"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", action="store_true", help="include every planned job; still no execution")
    args = parser.parse_args(argv)
    try:
        result = plan()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if not args.schedule:
        result.pop("schedule")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
