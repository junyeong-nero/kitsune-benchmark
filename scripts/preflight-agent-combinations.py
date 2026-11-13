"""Validate the pilot's 21 distinct runtime/fixture cells without model calls.

Checks subscription login metadata, native catalogs, initial tabs, real image
transport, noncompletion grading, three independent UI reference controls and
owned-runtime cleanup. Passing is necessary, not sufficient to freeze inference.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import chdir
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kitsune_benchmark.adapter import harness_environment, harness_preflight, resolve, write_json
from kitsune_benchmark.agent_combinations import CLI_SURFACES, CONDITIONS, KITSUNE_TOOLS, MODELS, plan
from kitsune_benchmark.agent_combinations_fixture import await_relay_close, prepared_fixture, reference_control, relay_server, screenshot
from kitsune_benchmark.agent_combinations_runtime import runtime_pins, validation_fingerprint
from kitsune_benchmark.agent_combinations_session import CombinationsSession
from kitsune_benchmark.personal_session import NativeSession, error_detail
from kitsune_benchmark.runtime import BASE_ENV


def initialize(session):
    reply = session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {"elicitation": {"form": {}}},
        "clientInfo": {"name": "combinations-no-inference-preflight", "version": "1"}})
    if "error" in reply:
        raise ValueError("MCP initialization failed")
    session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools, cursors, params = [], set(), {}
    while True:
        reply = session.request("tools/list", params)
        result = reply.get("result", {})
        if "error" in reply or not isinstance(result.get("tools"), list):
            raise ValueError("Invalid native tool catalog")
        tools.extend(result["tools"])
        cursor = result.get("nextCursor")
        if cursor is None:
            break
        if not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise ValueError("Repeated/invalid catalog cursor")
        cursors.add(cursor)
        params = {"cursor": cursor}
    names = [t["name"] for t in tools]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate native tools")
    return tools


def image_evidence(result):
    images = []
    for item in result.get("content", []):
        if item.get("type") != "image":
            continue
        data = base64.b64decode(item["data"], validate=True)
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            images.append({"mime_type": item["mimeType"], "width": image.width, "height": image.height,
                           "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return images


def probe_fixture(out, condition, surface, project):
    with prepared_fixture(condition, surface, out, project) as (fixture, task, config, _):
        session = CombinationsSession(config)
        try:
            session.start()
            tools = initialize(session)
            if surface == "kitsune-zen" and {t["name"] for t in tools} != set(KITSUNE_TOOLS):
                raise ValueError("Kitsune six-tool catalog changed")
            session.prepare()
            control_result = {"execution_status": "completed_unscored", "mcp_calls": 0}
            grade = fixture.evaluate(config["target"], control_result)
            write_json(out / "noncompletion-control.json", grade)
            if grade.get("scorable") is not True or grade.get("task_success") is not False:
                raise ValueError("Unchanged grader must score noncompletion as failure")
            result = screenshot(session)
            write_json(out / "fixture-screenshot.json", result)
            images = image_evidence(result)
            if not images:
                raise ValueError("No image delivered from the real fixture")
            reference = None
            if surface == "playwright":
                trial = fixture.trials[fixture.by_target[config["target"]]]
                write_json(out / "reference-ui-response.json", reference_control(session, condition, trial))
                reference = fixture.evaluate(config["target"], control_result)
                write_json(out / "reference-control.json", reference)
                if reference.get("scorable") is not True or reference.get("task_success") is not True:
                    raise ValueError("Deterministic UI reference control did not pass the unchanged grader")
            result = {"model_invoked": False, "surface": surface, "unit": condition["unit"],
                "setup_complete": True, "noncompletion_control": "passed", "images": images,
                "reference_control": "passed" if reference else None,
                "initial_tabs": session.evidence["initial_tabs"],
                "viewport": fixture.viewport_reports(config["target"]) if condition["track"] == "personal" else None}
            write_json(out / "fixture-check.json", result)
            return result
        except Exception as error:
            session.evidence.update(error="preflight_fixture_failed", error_detail=error_detail(error))
            raise
        finally:
            session.save()
            session.close()
            if session.evidence.get("teardown_error"):
                raise ValueError("Fixture cleanup failed; inspect session-evidence.json")


def probe_interface(out, surface, project):
    """Replay the actual model-facing stdio/filter/image/EOF path with no model."""
    with prepared_fixture(CONDITIONS[2], surface, out, project) as (_, _, config, path):
        server = relay_server(config, path, Path(os.path.relpath(out)))
        workspace = out / "cli-workspace"
        workspace.mkdir(mode=0o700)
        client = NativeSession({"target": config["target"], "upstream": [server.command, *server.args]})
        try:
            with chdir(workspace):
                client.start(env={k: v for k, v in os.environ.items() if k in BASE_ENV})
            tools = initialize(client)  # Includes lazy fixture setup behind the real relay.
            proxy = SimpleNamespace(config=config, tool=client.tool,
                inventory=lambda: json.loads(Path(config["evidence_path"]).read_text())["initial_tabs"],
                code=lambda code: client.tool("repl" if config["target"] == "aside" else "run_script",
                    {"code": code, **({"title": "No-model image delivery check"} if config["target"] == "aside" else {})}))
            response = screenshot(proxy)
            write_json(out / "delivered-image.json", response)
            images = image_evidence(response)
            if not images:
                raise ValueError("No image traversed the actual model-facing relay")
        finally:
            client.close()
            await_relay_close(config, out)
        evidence = json.loads(Path(config["evidence_path"]).read_text())
        if evidence.get("error") or evidence.get("teardown_error") or evidence.get("session_closed") is not True:
            raise ValueError("Model-facing relay setup/cleanup failed")
        return {"model_invoked": False, "images": images, "session_closed": True, "tools": [t["name"] for t in tools]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--surface", choices=tuple(CLI_SURFACES), help="Debug one adapter; partial checks never approve inference")
    parser.add_argument("--kitsune-project", type=Path, default=ROOT.parent / "kitsune")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    report = {"model_invoked": False, "execution_ready": False, "plan": plan(), "checks": {}, "interfaces": {},
              "source_sha256": validation_fingerprint()}
    try:
        report["pins"] = runtime_pins()
        report["auth"] = {h: harness_preflight(h, resolve(h, h),
            harness_environment(h, resolve(h, h)), model=m) for h, m in MODELS.items()}
        write_json(out / "auth.json", report["auth"])
        for condition in CONDITIONS:
            for surface in ((args.surface,) if args.surface else CLI_SURFACES):
                key = condition["unit"] + "--" + surface
                print("No-model fixture: " + key, flush=True)
                report["checks"][key] = probe_fixture(out / key, condition, surface, args.kitsune_project)
        for surface in ((args.surface,) if args.surface else CLI_SURFACES):
            print("No-model stdio/cleanup: " + surface, flush=True)
            report["interfaces"][surface] = probe_interface(out / ("interface--" + surface), surface, args.kitsune_project)
        report["pins_after"] = runtime_pins()
        if validation_fingerprint() != report["source_sha256"] or report["pins"] != report["pins_after"]:
            raise ValueError("Sources/runtime pins changed during no-inference validation")
        report["status"] = "fixture_setup_images_noncompletion_passed_remaining_gates_pending"
        return 0
    except Exception as error:
        report["status"] = "blocked_before_inference"
        report["error"] = {"type": type(error).__name__, "message": error_detail(error)}
        return 2
    finally:
        write_json(out / "preflight.json", report)
        print(json.dumps({"status": report.get("status"), "model_invoked": False,
                          "execution_ready": False, "evidence": str(out / "preflight.json")}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
