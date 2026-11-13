"""Explicit fixture/runtime wiring for the bounded pilot, without model invocation."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import time
import uuid

import psutil

from . import gallery, personal
from .adapter import write_json
from .agent_combinations_runtime import ROOT, chrome_runtime, zen_runtime
from .runtime import BASE_ENV
from .specs import Server


@contextmanager
def prepared_fixture(condition, surface, folder, project):
    """Yield a fresh fixture and a relay configuration. Setup remains no-inference."""
    folder = Path(folder).resolve()
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    target = "kitsune" if surface == "kitsune-zen" else surface
    if condition["track"] == "personal":
        fixture = personal.PersonalServer(personal.selected_tasks([condition["task"]])[0], 0,
                                           report_viewport=True, user_channel=target == "kitsune")
    else:
        fixture = gallery.GalleryServer(gallery.select([condition["task"]])[0], 0, condition["layout"])
    with fixture:
        task = fixture.begin(target)
        trial = fixture.trials[fixture.by_target[target]]
        port = ((fixture.bidi_ports[target] if condition["track"] == "personal" else fixture.kitsune_bidi_port)
                if target == "kitsune" else None)
        context = "bm-combinations-" + uuid.uuid4().hex
        images = folder / "images"
        images.mkdir(mode=0o700)

        browser_record = {}

        @contextmanager
        def runtime():
            if target == "kitsune":
                with zen_runtime(folder / "runtime", project, bidi_port=port) as (command, env):
                    yield command, env
            elif target in {"aside", "ego"}:
                command = ([str(Path.home() / ".local/bin/aside"), "mcp"] if target == "aside" else
                    [sys.executable, str(ROOT / "kitsune_benchmark/expanded_ego_mcp.py"), "--screenshots", str(images)])
                yield command, {k: v for k, v in os.environ.items() if k in BASE_ENV}
            else:
                with chrome_runtime(folder / "runtime", surface) as (command, env, record):
                    browser_record.update(record)
                    if target == "browser-harness":
                        # Default screenshot files must be in this attempt's image-only directory.
                        env["BH_TMP_DIR"] = str(images)
                    yield command, env

        with runtime() as (command, env):
            evidence = folder / "session-evidence.json"
            fixture.evidence_paths[target] = evidence
            config = {"target": target, "upstream": command, "upstream_env": env, "context": context,
                "chrome_ws_url": browser_record.get("ws_url"),
                "images": str(images), "upstream_stderr": str(folder / "upstream.log"),
                "bootstrap_url": trial.url("/start"),
                "urls": [trial.url(p) for p in trial.paths], "active_index": trial.active_index,
                "origin": fixture.origin, "evidence_path": str(evidence), "elicitation": "decline",
                "enabled_tools": ["repl"] if target == "aside" else ["run_script"] if target == "ego" else [],
                "diagnostics_path": str(folder / (target + "-native-rpc.jsonl")),
                "metadata_path": str(folder / (target + "-native-metadata.json"))}
            if target == "kitsune":
                config["user_driver"] = {"bidi_url": f"ws://127.0.0.1:{port}"}
                if condition["track"] == "personal":
                    config["seeding"] = "user_channel"
                else:
                    config["task_tab"] = "agent"
            elif target == "playwright" and condition["track"] == "gallery":
                config["task_tab"] = "agent"
            path = folder / "session-config.json"
            write_json(path, config)
            yield fixture, task, config, path


def relay_server(config, config_path, folder):
    target = config["target"]
    command = (str(ROOT / "kitsune_benchmark/mcp_tool_filter.py"),
        json.dumps(config["enabled_tools"] or None), "--metadata", str(folder / "catalog-metadata.jsonl"), "--",
        sys.executable, str(ROOT / "kitsune_benchmark/agent_combinations_session.py"), str(config_path))
    return Server(target, sys.executable, command, (), 60, 45 if target in {"kitsune", "playwright"} else 130)


def await_relay_close(config, folder):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if json.loads(Path(config["evidence_path"]).read_text()).get("session_closed") is True:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    record_path = folder / "relay-process.json"
    if record_path.exists():
        record = json.loads(record_path.read_text())
        try:
            process = psutil.Process(record["pid"])
            if (process.create_time() != record["created"] or record["config"] not in process.cmdline()
                    or os.getpgid(process.pid) != process.pid):
                raise ValueError("Relay process identity changed; refusing to signal")
            os.killpg(process.pid, 15)
            try:
                process.wait(timeout=3)
            except psutil.TimeoutExpired:
                if process.create_time() == record["created"]:
                    os.killpg(process.pid, 9)
                    process.wait(timeout=3)
        except psutil.NoSuchProcess:
            pass
    raise ValueError("Relay cleanup was not confirmed; raw usage retained, no automatic continuation")


def reference_control(session, condition, trial):
    """Independent grader-positive control using Playwright UI actions, never an agent hint.

    Expected values belong only to this no-model control and are not included in
    model tasks, catalogs or the later fresh trials.
    """
    if session.config["target"] != "playwright":
        raise ValueError("Reference controls use the explicit private Playwright path")
    if condition["task"] == "pb-longpage-01":
        code = (f"const p=page.context().pages().find(p=>p.url()==={json.dumps(trial.url('/memo'))}); await p.bringToFront(); "
                f"for(const [name,value] of Object.entries({json.dumps(trial.impl.expected, ensure_ascii=False)})) "
                "await p.getByLabel(name,{exact:true}).fill(value); "
                "await p.getByRole('button',{name:'저장',exact:true}).click();")
    elif condition["task"] == "ui-table":
        data = json.dumps(trial.mine, ensure_ascii=False)
        code = ("await page.getByRole('button',{name:'필수만 허용'}).click(); "
                f"const d={data}; const names=Object.fromEntries(d.rows.map(r=>[r.id,r.name])); "
                "const pages=await page.locator('#sec-stock-table .pager button').count(); "
                "for(let i=0;i<pages;i++){await page.locator('#sec-stock-table .pager button').nth(i).click(); "
                "for(const id of d.expected){const box=page.getByRole('checkbox',{name:names[id]+' 선택',exact:true}); "
                "if(await box.count()) await box.check();}}")
    elif condition["task"] == "mm-chart":
        answer = json.dumps(trial.mine["answer"], ensure_ascii=False)
        code = (f"await page.locator('#sec-mm-chart input[value='+JSON.stringify({answer})+']').check(); "
                "await page.locator('#sec-mm-chart .puzzle-submit').click();")
    else:
        raise ValueError("No reference control for an unapproved task")
    result = session.tool("browser_run_code_unsafe", {"code": "async (page) => {" + code + " await page.waitForTimeout(500); }"})
    session.evidence["snapshots"].append(session.inventory())
    session.evidence["tab_calls"].append({"tool": "browser_run_code_unsafe", "error": False})
    session.evidence["tab_ids"] = "index"
    session.save()
    return result


def screenshot(session):
    """Use each native observation interface; no extra model-visible screenshot tool."""
    target = session.config["target"]
    if target in {"kitsune", "playwright"}:
        return session.tool("browser_take_screenshot", {})
    if target == "devtools":
        page = next(t for t in session.inventory() if t["active"])
        return session.tool("take_screenshot", {"pageId": page["id"]})
    if target == "browser-harness":
        return session.tool("browser_screenshot", {})
    if target == "agent-browser":
        return session.tool("agent_browser_screenshot", {})
    if target == "aside":
        return session.code("await display(await page.screenshot());")
    path = json.dumps(str(Path(session.config["images"]) / "preflight.png"))
    context = json.dumps(session.config["context"])
    return session.code(f"const t=await taskSpace({context}); const p=(await t.tabs()).find(x=>x.active).page; "
                        f"console.log(JSON.stringify({{screenshot:await p.screenshot({{path:{path}}})}}));")
