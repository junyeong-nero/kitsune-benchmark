"""Fixture relay for the new combinations pilot, not a historical-run override.

Native schemas are retained. Browser Harness's screenshot path is delivered as an
MCP image using the same bounded file-to-image handoff as the EgoLite adapter.
The relay is instrumentation, not a sandbox for native Python/JS/CDP tools.
"""
from __future__ import annotations

from contextlib import redirect_stderr
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
import urllib.request

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.adapter import write_json
from kitsune_benchmark.agent_combinations import KITSUNE_TOOLS
from kitsune_benchmark.expanded_ego_mcp import attach_images
from kitsune_benchmark.expanded_session import ExpandedSession
from kitsune_benchmark.personal_session import NativeSession, elicitation_kind, error_detail
from kitsune_benchmark.user_driver import UserDriver

CHROME_SURFACES = {"devtools", "browser-harness", "agent-browser"}
PENDING_URL_SECONDS = 1.0
PENDING_URL_POLLS = 20


def text_json(result):
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except ValueError:
                pass
    raise ValueError("Missing native JSON observation")


def browser_harness_image(result, directory, started_ns):
    value = text_json(result)
    if not isinstance(value, dict) or not isinstance(value.get("path"), str):
        raise ValueError("Browser Harness screenshot has no path")
    bridged = attach_images({"content": [{"type": "text", "text": json.dumps({"screenshot": value["path"]})}]},
                            Path(directory), started_ns)
    return {**result, "content": [*result.get("content", []), *bridged["content"][1:]],
            **({"isError": True} if bridged.get("isError") else {})}


class CombinationsSession(ExpandedSession):
    def start(self, *, env=None):
        env = self.config["upstream_env"] if env is None else env
        if self.config.get("upstream_stderr"):
            path = Path(self.config["upstream_stderr"])
            with path.open("x") as log, redirect_stderr(log):
                path.chmod(0o600)
                super().start(env=env)
        else:
            super().start(env=env)

    def tool(self, name, arguments, refusal_codes=()):
        # Setup also uses the product's real six-tool interface, never unlisted direct calls.
        if self.config["target"] == "kitsune" and name not in KITSUNE_TOOLS:
            return super().tool("browser_tools_call", {"name": name, "arguments": arguments}, refusal_codes)
        return super().tool(name, arguments, refusal_codes)

    def answer_elicitation(self, params, role, tool):
        choices = ((params.get("requestedSchema") or {}).get("properties", {}).get("decision") or {}).get("enum", [])
        if role == "agent" and self.elicitation == "decline" and "Decline" in choices:
            reason, detail = elicitation_kind(params)
            self.evidence["elicitations"].append({"tool": tool, "reason": reason, "detail": detail,
                "action": "accept", "decision": "Decline", "provenance": "simulated_form_decision",
                "message": params.get("message")})
            self.diagnostic("elicitation_answered", role=role, tool=tool, action="accept", decision="Decline",
                            provenance="simulated_form_decision")
            return {"action": "accept", "content": {"decision": "Decline"}}
        return NativeSession.answer_elicitation(self, params, role, tool)

    def request(self, method, params=None, *, notify=None, role="harness"):
        started = time.time_ns()
        response = super().request(method, params, notify=notify, role=role)
        if self.config["target"] == "browser-harness" and role == "agent" and method == "tools/call":
            self.pending_tab_receipt = {"request": params, "response": response}
        if role == "harness" and method == "tools/call" and not self.evidence["setup_complete"]:
            self.evidence.setdefault("setup_rpc", []).append({"request": params, "response": response})
        if (self.config["target"] == "browser-harness" and method == "tools/call"
                and (params or {}).get("name") == "browser_screenshot"
                and "error" not in response and not response.get("result", {}).get("isError")):
            response = {**response, "result": browser_harness_image(response["result"], self.config["images"], started)}
        return response

    def browser_harness_tabs(self):
        listed = text_json(self.tool("browser_list_tabs", {}))
        current = text_json(self.tool("browser_current_tab", {}))
        self.evidence["last_native_inventory"] = {"listed": listed, "current": current}
        active = current.get("targetId", current.get("target_id"))
        tabs = [{"id": t["targetId"], "url": t["url"], "title": t.get("title", ""),
                 "active": t["targetId"] == active} for t in listed]
        if (not tabs or len({t["id"] for t in tabs}) != len(tabs)
                or sum(t["active"] for t in tabs) != 1 or any(not isinstance(t["url"], str) for t in tabs)):
            raise ValueError("Invalid Browser Harness tab inventory/selection")
        return tabs

    def stabilize_pending_url(self, tabs):
        # Only the immediately preceding successful explicit local new-tab request
        # can establish provenance. Never reinterpret an empty URL as about:blank.
        receipt = getattr(self, "pending_tab_receipt", None)
        self.pending_tab_receipt = None
        if not self.evidence["setup_complete"] or not any(t["url"] == "" for t in tabs):
            return tabs
        started = time.monotonic()
        record = {"snapshot_index": len(self.evidence["snapshots"]), "receipt": receipt,
                  "window_sec": PENDING_URL_SECONDS, "max_polls": PENDING_URL_POLLS,
                  "samples": [{"elapsed_sec": 0.0, "tabs": tabs,
                               "native_inventory": self.evidence.get("last_native_inventory")}], "status": "ineligible"}
        self.evidence.setdefault("pending_url_observations", []).append(record)
        params, response = (receipt or {}).get("request") or {}, (receipt or {}).get("response") or {}
        url = (params.get("arguments") or {}).get("url")
        try:
            created = text_json(response.get("result", {})).get("targetId")
        except (ValueError, AttributeError):
            created = None
        previous = self.evidence["snapshots"]
        seen = {t["id"] for snapshot in previous for t in snapshot}
        prior_help = {t["id"] for t in (previous[-1] if previous else [])
                      if t["url"] == "chrome://settings/help" and not t["active"]}
        if (params.get("name") != "browser_new_tab" or "error" in response
                or response.get("result", {}).get("isError") or not isinstance(created, str) or created in seen
                or not isinstance(url, str) or not url.startswith(self.config["origin"] + "/")
                or not previous or {t["id"] for t in tabs} != {t["id"] for t in previous[-1]} | {created}
                or [t["id"] for t in tabs if t["url"] == ""] != [created]
                or any(t["url"] and t["url"] != "about:blank"
                       and not t["url"].startswith(self.config["origin"] + "/")
                       and not (t["id"] in prior_help and t["url"] == "chrome://settings/help" and not t["active"])
                       for t in tabs)):
            return tabs
        stable = {t["id"]: (t["url"], t["active"]) for t in tabs if t["id"] != created}
        created_active = next(t["active"] for t in tabs if t["id"] == created)
        record.update(status="pending", target_id=created, requested_url=url)
        try:
            for _ in range(PENDING_URL_POLLS):
                remaining = PENDING_URL_SECONDS - (time.monotonic() - started)
                if remaining <= 0:
                    break
                time.sleep(min(0.05, remaining))
                if time.monotonic() - started >= PENDING_URL_SECONDS:
                    break
                observed = self.browser_harness_tabs()
                elapsed = time.monotonic() - started
                record["samples"].append({"elapsed_sec": elapsed, "tabs": observed,
                                          "native_inventory": self.evidence.get("last_native_inventory")})
                # A slow native RPC retains its existing transport deadline, but
                # a reply outside this observation window cannot qualify as settled.
                if elapsed > PENDING_URL_SECONDS:
                    raise ValueError("Pending URL observation exceeded its window")
                if ({t["id"]: (t["url"], t["active"]) for t in observed if t["id"] != created} != stable
                        or not any(t["id"] == created and t["active"] == created_active for t in observed)):
                    raise ValueError("Ambiguous inventory change during pending URL observation")
                resolved = next(t["url"] for t in observed if t["id"] == created)
                if resolved == url:
                    record["status"] = "settled"
                    return observed
                if resolved:
                    raise ValueError("Pending target resolved to an unexpected URL")
            record["status"] = "unresolved"
            return tabs  # The unchanged empty URL remains an outside observation.
        except (OSError, ValueError, KeyError, TypeError) as error:
            record.update(status="failed", error_detail=error_detail(error),
                          failure_inventory=self.evidence.get("last_native_inventory"))
            raise
        finally:
            record["elapsed_sec"] = time.monotonic() - started

    def inventory(self):
        target = self.config["target"]
        if target not in CHROME_SURFACES:
            return super().inventory()
        started = time.monotonic()
        try:
            if target == "devtools":
                result = self.tool("list_pages", {})
                self.evidence["last_native_inventory"] = result
                tabs = []
                for item in result.get("content", []):
                    for line in item.get("text", "").splitlines():
                        match = re.fullmatch(r"(\d+): (.*?)( \[selected\])?", line)
                        if match:
                            titled = re.fullmatch(r"(.*) \(((?:https?://|about:).*)\)", match[2])
                            tabs.append({"id": int(match[1]), "url": titled[2] if titled else match[2],
                                         "title": titled[1] if titled else "", "active": bool(match[3])})
            elif target == "browser-harness":
                tabs = self.stabilize_pending_url(self.browser_harness_tabs())
            else:
                response = self.tool("agent_browser_tab_list", {})["structuredContent"]["response"]
                if response.get("success") is not True:
                    raise ValueError("agent-browser inventory failed")
                tabs = [{"id": t["targetId"], "tab_id": t["tabId"], "url": t["url"],
                         "title": t.get("title", ""), "active": t["active"]} for t in response["data"]["tabs"]]
            self.evidence["last_native_tabs"] = tabs
            if (not tabs or len({t["id"] for t in tabs}) != len(tabs)
                    or sum(t["active"] is True for t in tabs) != 1):
                raise ValueError("Invalid native tab inventory/selection")
            if self.evidence["setup_complete"]:
                self.evidence["outside_navigation"] += sum(
                    t["url"] != "about:blank" and not t["url"].startswith(self.config["origin"] + "/") for t in tabs)
            return tabs
        finally:
            if self.evidence["setup_complete"]:
                self.evidence["post_call_inventory_sec"] = self.evidence.get("post_call_inventory_sec", 0) + time.monotonic() - started

    def select_tab(self, tab):
        target = self.config["target"]
        name, args = {"devtools": ("select_page", {"pageId": tab["id"], "bringToFront": True}),
            "browser-harness": ("browser_switch_tab", {"target": str(tab["id"])}),
            "agent-browser": ("agent_browser_tab_switch", {"tab": str(tab["id"])})}[target]
        self.tool(name, args)

    def navigate(self, url, tab):
        target = self.config["target"]
        name, args = {"devtools": ("navigate_page", {"pageId": tab["id"], "url": url}),
            "browser-harness": ("browser_goto", {"url": url}),
            "agent-browser": ("agent_browser_open", {"url": url})}[target]
        self.tool(name, args)
        if target == "browser-harness":
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                observed = text_json(self.tool("browser_current_tab", {}))
                if observed.get("targetId") == tab["id"] and observed.get("url") == url:
                    remaining = deadline - time.monotonic()
                    if remaining > 0 and text_json(self.tool("browser_wait_for_load", {"timeout": remaining})).get("ok") is True:
                        return
                    break
                time.sleep(0.05)
            raise ValueError("Browser Harness setup navigation did not settle: " + url)

    def user_closes_initial_tab(self, initial_url, task):
        if initial_url != "about:blank":
            return super().user_closes_initial_tab(initial_url, task)
        driver = UserDriver(self.config["user_driver"]["bidi_url"])
        try:
            driver.select(task)
            # Zen's internal zen-empty-tab placeholder is absent from WebExtension tabs.
            # Leave that internal object alone; close exactly one real initial blank tab.
            count = driver.chrome("""(() => {
                const tabs=gBrowser.tabs.filter(t=>t.linkedBrowser.currentURI.spec==='about:blank'
                    && !t.hasAttribute('zen-empty-tab'));
                if(tabs.length===1) gBrowser.removeTab(tabs[0]);
                return tabs.length;
            })()""")
            self.evidence["zen_real_initial_blank_count"] = count
            if count != 1:
                raise ValueError("Zen real initial blank tab is missing or ambiguous")
        finally:
            self.evidence.update(driver_calls=self.evidence.get("driver_calls", 0) + driver.calls,
                                 driver_seconds=self.evidence.get("driver_seconds", 0) + driver.seconds)
            driver.close()

    def prepare(self):
        target = self.config["target"]
        if target not in CHROME_SURFACES:
            return super().prepare()
        if self.evidence["setup_complete"]:
            return
        started = time.monotonic()
        self.diagnostic("setup_started")
        if target == "agent-browser":
            self.tool("agent_browser_open", {"url": "about:blank"})
        tabs = self.inventory()
        if any(t["url"] != "about:blank" for t in tabs):
            raise ValueError("Expected only fresh owned blank tabs")
        self.evidence["browser_initial_tabs"] = tabs
        if target in {"browser-harness", "agent-browser"}:
            endpoint = urlsplit(self.config["chrome_ws_url"])
            if endpoint.scheme != "ws" or endpoint.hostname != "127.0.0.1" or endpoint.port in {9222, 9223, 47651, 47652}:
                raise ValueError("Not an explicitly owned private Chrome endpoint")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(f"http://127.0.0.1:{endpoint.port}/json/list", timeout=5) as response:
                owned = {t["id"] for t in json.load(response) if t["type"] == "page"}
            if not {t["id"] for t in tabs} <= owned:
                raise ValueError("Native targets do not belong to the owned Chrome")
            self.evidence["owned_target_ids_verified"] = True
        current = next(t for t in tabs if t["active"])
        # Browser Harness creates an additional owned blank tab on connection.
        for tab in tabs:
            if tab["id"] != current["id"]:
                name, args = {"devtools": ("close_page", {"pageId": tab["id"]}),
                    "browser-harness": ("browser_close_tab", {"target": str(tab["id"])}),
                    "agent-browser": ("agent_browser_tab_close", {"tab": str(tab["id"])})}[target]
                self.tool(name, args)
        self.select_tab(current)
        self.navigate(self.config["bootstrap_url"], current)
        self.navigate(self.config["urls"][0], current)
        known_ids = {t["id"] for t in tabs}
        for url in self.config["urls"][1:]:
            name = {"devtools": "new_page", "browser-harness": "browser_new_tab",
                    "agent-browser": "agent_browser_tab_new"}[target]
            if target == "browser-harness":
                # Native new_tab(nonblank) can reuse a stale blank target. Force
                # distinct creation, then navigate and wait for that exact target.
                created = text_json(self.tool(name, {"url": "about:blank"}))["targetId"]
                if created in known_ids:
                    raise ValueError("Browser Harness reused a fixture target")
                known_ids.add(created)
                self.navigate(url, {"id": created})
            else:
                self.tool(name, {"url": url})
        tabs = self.inventory()
        self.evidence["fixture_tabs_before_validation"] = tabs
        if sorted(t["url"] for t in tabs) != sorted(self.config["urls"]):
            raise ValueError("Fixture starting tabs do not match")
        desired = self.config["urls"][self.config["active_index"]]
        self.select_tab(next(t for t in tabs if t["url"] == desired))
        tabs = self.inventory()
        self.evidence["fixture_selection_before_validation"] = tabs
        if not any(t["url"] == desired and t["active"] for t in tabs):
            raise ValueError("Fixture starting selection does not match")
        self.evidence.update(setup_complete=True, initial_tabs=tabs, snapshots=[tabs], tab_ids="stable",
                             profile_isolated=True, seeded_owned_by_agent=None, seeding="owned_chrome_native_tools")
        self.save()
        self.diagnostic("setup_completed", duration_sec=time.monotonic() - started)

    def close(self):
        super().close()
        self.evidence["session_closed"] = True
        self.save()


def main():
    config_path = Path(sys.argv[1])
    if os.environ.get("AGENT_COMBINATIONS_DETACHED") != "1":
        # Like the coexistence relay: survive the CLI's MCP process-group stop,
        # finish on pipe EOF, and let the parent enforce an owned-process deadline.
        child = subprocess.Popen([sys.executable, *sys.argv],
            env={**os.environ, "AGENT_COMBINATIONS_DETACHED": "1"}, start_new_session=True)
        write_json(config_path.parent / "relay-process.json", {"pid": child.pid,
            "created": psutil.Process(child.pid).create_time(), "config": str(config_path.resolve())})
        return child.wait()
    session = CombinationsSession(json.loads(config_path.read_text()))
    try:
        session.start()
        for line in sys.stdin:
            if line.strip():
                session.forward(json.loads(line), lambda response: print(json.dumps(response, ensure_ascii=False), flush=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        session.evidence.update(error="combinations_session_failed", error_detail=error_detail(error))
        session.save()
        print("Combinations fixture relay failed; inspect private evidence.", file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
