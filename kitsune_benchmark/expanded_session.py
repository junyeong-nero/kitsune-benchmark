"""Fixture relay for the separate expanded four-way experiment; no model calls.

Kitsune keeps the existing user-channel setup and product permissions. Agent declines
are scripted after two seconds so they settle the prompt, rather than masquerading as
an immediate client-policy denial. Vendors use fresh REPL/TaskSpace contexts in their
installed browsers, NOT isolated profiles or equivalent user-tab ownership. Inventory
is sampled after each MCP call; inner-script actions are not fully instrumented.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.full_native_session import FullNativeSession  # noqa: E402
from kitsune_benchmark.personal_session import error_detail  # noqa: E402
from kitsune_benchmark.adapter import write_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DECLINE_DELAY = 2.0
VIEWPORT = {"width": 1280, "height": 720}


def receipt(result, key):
    for item in result.get("content", []):
        for line in item.get("text", "").splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and key in value:
                return value[key]
    raise ValueError("Missing fixture setup/inventory receipt: " + key)


class ExpandedSession(FullNativeSession):
    def answer_elicitation(self, params, role, tool):
        if role == "agent" and self.elicitation == "decline":
            time.sleep(DECLINE_DELAY)
            self.diagnostic("scripted_decline_delay", duration_sec=DECLINE_DELAY)
        return super().answer_elicitation(params, role, tool)

    def inventory(self):
        started = time.monotonic()
        try:
            tabs = self.vendor_inventory() if self.config["target"] in ("aside", "ego") else super().inventory()
            if self.evidence["setup_complete"]:
                self.evidence["outside_navigation"] += sum(
                    t["url"] != "about:blank" and not t["url"].startswith(self.config["origin"] + "/") for t in tabs)
            return tabs
        finally:
            if self.evidence["setup_complete"]:
                self.evidence["post_call_inventory_sec"] = self.evidence.get("post_call_inventory_sec", 0) + time.monotonic() - started

    def code(self, script):
        target = self.config["target"]
        arguments = {"code": script}
        if target == "aside":
            arguments["title"] = "Fixture setup or inventory (not agent work)"
        return self.tool("repl" if target == "aside" else "run_script", arguments)

    def vendor_inventory(self):
        if self.config["target"] == "aside":
            script = """console.log(JSON.stringify({__bm_inventory:await Promise.all(tabs.map(async t=>({
                id:t.targetId,url:await t.url(),title:await t.title(),active:!!page&&t.targetId===page.targetId}))) }));"""
        else:
            context = json.dumps(self.config["context"])
            script = f"""const t=await taskSpace({context});
                console.log(JSON.stringify({{__bm_inventory:(await t.tabs()).map(x=>({{
                    id:x.targetId,url:x.url,title:x.title,active:!!x.active,label:x.label,openedBy:x.openedBy}}))}}));"""
        tabs = receipt(self.code(script), "__bm_inventory")
        if (not isinstance(tabs, list) or any(not isinstance(t.get("id"), str)
                or not isinstance(t.get("url"), str) or type(t.get("active")) is not bool for t in tabs)
                or len({t["id"] for t in tabs}) != len(tabs)):
            raise ValueError("Invalid vendor tab inventory")
        return tabs

    def prepare(self):
        if self.config["target"] not in ("aside", "ego"):
            return super().prepare()
        if self.evidence["setup_complete"]:
            return
        started = time.monotonic()
        self.diagnostic("setup_started")
        urls = json.dumps(self.config["urls"])
        bootstrap = json.dumps(self.config["bootstrap_url"])
        active = self.config["active_index"]
        self.evidence.update(seeding="vendor_context_harness_created", seeded_owned_by_agent=None,
                             profile_isolated=False, context=self.config["context"])
        if self.config["target"] == "aside":
            # tabs is this fresh native MCP server's attached REPL set, never listBrowserTabs().
            self.code(f"""if(tabs.length) throw new Error('Expected a fresh empty REPL');
                await openTab({bootstrap}); await page.goto({urls}[0]);
                for(const u of {urls}.slice(1)) await openTab(u);
                for(const t of tabs) await t.setViewportSize({json.dumps(VIEWPORT)});
                page=tabs[{active}];""")
            self.evidence["active_semantics"] = "native_repl_selected_page"
        else:
            context = json.dumps(self.config["context"])
            created = self.code(f"""if((await listTaskSpaces()).some(s=>s.name==={context}))
                    throw new Error('Fixture TaskSpace name already exists; do not reuse it');
                const t=await taskSpace({context}); console.log(JSON.stringify({{__bm_space:t.spaceId}}));""")
            self.evidence["space_id"] = receipt(created, "__bm_space")
            self.save()
            self.code(f"""const t=await taskSpace({context}); const p=t.page('p1');
                await p.goto({bootstrap}); await p.goto({urls}[0]);
                for(const u of {urls}.slice(1)) {{const n=await t.newPage(); await n.goto(u);}}
                for(const x of await t.tabs()) await x.page.cdp('Emulation.setDeviceMetricsOverride',
                    {{width:1280,height:720,deviceScaleFactor:1,mobile:false}});
                await (await t.tabs())[{active}].page.cdp('Page.bringToFront');""")
            self.evidence["active_semantics"] = "native_taskspace_active_tab"
        tabs = self.inventory()
        if (sorted(t["url"] for t in tabs) != sorted(self.config["urls"])
                or not any(t["active"] and t["url"] == self.config["urls"][active] for t in tabs)):
            raise ValueError("Vendor fixture starting tabs/selection do not match")
        self.evidence.update(setup_complete=True, initial_tabs=tabs, snapshots=[tabs], tab_ids="stable")
        self.save()
        self.diagnostic("setup_completed", duration_sec=time.monotonic() - started)

    def close(self):
        # Teardown is not an agent action and never rewrites the recorded final inventory.
        try:
            if self.process and self.process.poll() is None and self.config["target"] in ("aside", "ego"):
                if self.config["target"] == "aside":
                    prefix = json.dumps(self.config["bootstrap_url"].rsplit("/", 1)[0] + "/")
                    self.code(f"for(const t of [...tabs]) if((await t.url()).startsWith({prefix})) await closeTab(t);")
                elif self.evidence.get("space_id") is not None:
                    context = json.dumps(self.config["context"])
                    self.code(f"const t=await taskSpace({context}); console.log(await t.finish({{keep:[]}}));")
        except (OSError, ValueError, KeyError) as error:
            self.evidence["teardown_error"] = error_detail(error)
            self.save()
        finally:
            super().close()


def prepare_relay(fixture, context: str, screenshots: Path):
    def prepare(target, server, task, pair_dir):
        if target == "kitsune":
            relay = fixture.prepare_server(target, server, task, pair_dir)
            return replace(relay, args=(str(ROOT / "kitsune_benchmark/expanded_session.py"), *relay.args[1:]))
        trial = fixture.trials[fixture.by_target[target]]
        path = pair_dir / (target + "-session.json")
        evidence = pair_dir / (target + "-session-evidence.json")
        fixture.evidence_paths[target] = evidence
        upstream = [server.command, *server.args]
        if target == "ego":
            screenshots.mkdir(parents=True, mode=0o700, exist_ok=False)
            upstream = [sys.executable, str(ROOT / "kitsune_benchmark/expanded_ego_mcp.py"), "--screenshots", str(screenshots)]
        write_json(path, {"target": target, "upstream": upstream, "context": context,
            "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
            "active_index": trial.active_index, "evidence_path": str(evidence), "origin": fixture.origin,
            "enabled_tools": list(server.enabled_tools), "elicitation": "decline",
            "diagnostics_path": str(pair_dir / (target + "-native-rpc.jsonl")),
            "metadata_path": str(pair_dir / (target + "-native-metadata.json"))})
        return replace(server, command=sys.executable,
                       args=(str(ROOT / "kitsune_benchmark/expanded_session.py"), str(path)))
    return prepare


def main():
    session = ExpandedSession(json.loads(Path(sys.argv[1]).read_text()))
    try:
        session.start()
        for line in sys.stdin:
            if line.strip():
                session.forward(json.loads(line), lambda response: print(json.dumps(response, ensure_ascii=False), flush=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        session.evidence.update(error="expanded_session_setup_or_inventory_failed", error_detail=error_detail(error))
        session.save()
        print("Expanded fixture setup/inventory failed; inspect private artifacts.", file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
