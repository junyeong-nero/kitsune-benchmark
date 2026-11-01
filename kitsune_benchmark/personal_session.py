"""Stdio MCP relay: seed an isolated session, preserve native schemas/results.

Runs as an absolute-path script from the private Codex cwd. No model calls.
Harness tab queries are hidden from the model and counted separately. Their
wall time IS included in the agent run; this is not an uninstrumented latency
benchmark. Only newline-delimited stdio MCP servers are supported.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kitsune_benchmark.bidi import BidiError  # noqa: E402
from kitsune_benchmark.user_driver import UserDriver  # noqa: E402

# How the relay answers the prompts Kitsune sends through MCP elicitation during the agent's turn (kitsune#376):
# session config "elicitation", default "decline", so a run measures whether the agent stops and reports. The relay
# declares form elicitation at initialize and answers every prompt itself; none reaches the agent's client, so
# results do not depend on it. The harness's own calls are approved as the user.
ELICITATION_POLICIES = ("decline", "accept")
# Why Kitsune held a call, by the phrase its approval prompt names it with (server.py _HELD_BECAUSE).
HELD_BECAUSE = {"you are viewing this tab": "user_viewing", "the agent did not open this tab": "user_tab",
                "ask-before-act": "confirmation_required"}


def elicitation_kind(params: dict) -> tuple[str | None, str | None]:
    """The reason and detail of a Kitsune prompt: "approval" (server.py APPROVAL_SCHEMA) with the held call's detail
    from the prompt's "Held because" line, "agent_request" (browser_ask_user, ASK_USER_SCHEMA), else None."""
    schema = params.get("requestedSchema")
    properties = schema.get("properties") if isinstance(schema, dict) else None
    properties = properties if isinstance(properties, dict) else {}
    choices = lambda field: (properties.get(field) or {}).get("enum") or []
    if "Approve" in choices("decision"):
        lines = str(params.get("message", "")).splitlines()
        detail = next((detail for line in lines for phrase, detail in HELD_BECAUSE.items()
                       if line.startswith("Held because " + phrase)), None)
        return "approval", detail
    if "Done" in choices("answer"):
        return "agent_request", None
    return None, None


def result_json(result: dict, key: str):
    """`key` of a native result's structured content, else of its first JSON text item that has it."""
    sources = [result.get("structuredContent")]
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                sources.append(json.loads(item.get("text", "")))
            except ValueError:
                pass
    return next((source[key] for source in sources if isinstance(source, dict) and key in source), None)


def held_refusal(result: dict) -> dict | None:
    """A refusal only the user can lift: code needs_user with state.reason approval (kitsune#376; state.detail names
    the hold, state.decision the prompt's answer), or Kitsune 0.7's user_tab code. Else None."""
    if not result.get("isError"):
        return None
    code, state = result_json(result, "code"), result_json(result, "state")
    state = state if isinstance(state, dict) else {}
    if code == "user_tab":
        return {"code": code, "detail": "user_tab", "decision": None}
    if code == "needs_user" and state.get("reason") == "approval":
        return {"code": code, "detail": state.get("detail"), "decision": state.get("decision")}
    return None


def tabs_from_result(target: str, result: dict, held_view_current: bool = False) -> list[dict]:
    """held_view_current: Kitsune after kitsune#390 does not mark the current tab `current` while it is an active tab
    the agent did not open (its writes are held for the user's view). With the flag, a list with no `current` tab
    reads its single active, not owned tab as current, which is exactly the tab #390 hides."""
    if result.get("isError"):
        raise ValueError("Tab inventory failed.")
    texts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
    if target == "playwright":
        tabs = []
        for text in texts:
            for line in text.splitlines():
                match = re.fullmatch(r"- (\d+): (\(current\) )?\[(.*)\]\((.*)\)", line)
                if match:
                    tabs.append({"id": int(match[1]), "active": bool(match[2]), "title": match[3], "url": match[4]})
    elif target == "kitsune":
        data = result.get("structuredContent")
        if not isinstance(data, dict) or not isinstance(data.get("tabs"), list):
            data = None
            for text in texts:
                try:
                    candidate = json.loads(text)
                    if isinstance(candidate, dict) and isinstance(candidate.get("tabs"), list):
                        data = candidate
                        break
                except ValueError:
                    continue
        # Kitsune >= 0.3.1 mirrors Playwright's browser_tabs: index-addressed, and `current` (the tab its tools
        # act on) plays the role of Playwright's "(current)" marker. Older Kitsune lists tab ids and `active`.
        listed = data["tabs"] if data else []
        hidden = None
        if held_view_current and not any(tab.get("current") for tab in listed):
            held = [i for i, tab in enumerate(listed) if tab.get("active") and not tab.get("owned")]
            hidden = held[0] if len(held) == 1 else None
        tabs = [{"id": tab["index"], "active": bool(tab.get("current")) or i == hidden, "title": tab.get("title") or "",
                 "url": tab["url"]} if "index" in tab else
                {"id": tab["id"], "active": tab["active"], "title": tab.get("title", ""), "url": tab["url"]}
                for i, tab in enumerate(listed)]
    else:
        raise ValueError("Unknown MCP target.")
    if (not tabs or any(type(tab["id"]) is not int or type(tab["active"]) is not bool
                        or not isinstance(tab["url"], str) for tab in tabs)
            or len({t["id"] for t in tabs}) != len(tabs)):
        raise ValueError("Unrecognized native tab inventory schema.")
    return tabs


class NativeSession:
    def __init__(self, config: dict):
        self.config = config
        self.process = None
        self.pending = queue.Queue()
        self.serial = 0
        self.tab_indexed = False
        self.held_view_current = False  # kitsune#390: see tabs_from_result and select_starting_tab
        self.tab_list_result = None  # the latest inventory, as the native server listed it
        self.started_mono = time.monotonic()
        self.elicitation = config.get("elicitation", "decline")
        if self.elicitation not in ELICITATION_POLICIES:
            raise ValueError("Unknown elicitation policy.")
        if config.get("seeding") not in (None, "user_channel") or (config.get("seeding") and config.get("task_tab")):
            raise ValueError("Unknown seeding, or user channel seeding with a harness task tab.")
        self.metadata = {"enabled_tools": config.get("enabled_tools", []), "tools_pages": []}
        self.evidence = {"setup_complete": False, "target": config.get("target"), "initial_tabs": [], "snapshots": [], "tab_calls": [],
                         "harness_calls": 0, "harness_seconds": 0.0,
                         "close_attempts": 0, "outside_navigation": 0,
                         "elicitation_policy": self.elicitation, "elicitations": [], "harness_elicitations": [],
                         "held_refusals": []}

    def start(self):
        self.process = subprocess.Popen(self.config["upstream"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=sys.stderr, bufsize=0)

        def read():
            try:
                for line in self.process.stdout:
                    if line.strip():
                        self.pending.put(json.loads(line))
            except (ValueError, OSError):
                pass
            finally:
                self.pending.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, message: dict):
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
        self.process.stdin.flush()

    def diagnostic(self, kind: str, **values):
        path = self.config.get("diagnostics_path")
        if path:
            entry = {"kind": kind, "time_utc": datetime.now(timezone.utc).isoformat(),
                     "offset_sec": time.monotonic() - self.started_mono, **values}
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def record_response(self, method: str, params: dict | None, message: dict,
                        role: str, request_id: str, started: float):
        result = message.get("result", {})
        texts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
        cached = False
        for text in texts:
            try:
                value = json.loads(text)
                cached = cached or (isinstance(value, dict) and value.get("_cached") is True)
            except ValueError:
                pass
        self.diagnostic("rpc_completed", request_id=request_id, role=role, method=method,
            tool=(params or {}).get("name"), action=(params or {}).get("arguments", {}).get("action"),
            duration_sec=time.monotonic() - started, cached=cached,
            serialized_response_bytes=len(json.dumps(message, ensure_ascii=False).encode()),
            response_text_chars=sum(len(text) for text in texts),
            response_text_bytes=sum(len(text.encode()) for text in texts),
            is_error="error" in message or result.get("isError") is True)
        if self.config.get("metadata_path") and method in {"initialize", "tools/list"}:
            if method == "initialize":
                self.metadata["initialize"] = result
            else:
                self.metadata["tools_pages"].append(result)
            self.write_private_json(Path(self.config["metadata_path"]), self.metadata)

    def request(self, method: str, params: dict | None = None, *, notify=None, role="harness") -> dict:
        self.serial += 1
        request_id = "personal-harness-" + str(self.serial)
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        started = time.monotonic()
        self.diagnostic("rpc_started", request_id=request_id, role=role, method=method,
                        tool=(params or {}).get("name"), action=(params or {}).get("arguments", {}).get("action"))
        self.send(request)
        deadline = time.monotonic() + 60
        while True:
            try:
                message = self.pending.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise ValueError("Native MCP request timed out.") from exc
            if message is None:
                raise ValueError("Native MCP closed before replying.")
            if message.get("id") == request_id and ("result" in message or "error" in message):
                self.record_response(method, params, message, role, request_id, started)
                return message
            if "method" in message and "id" not in message:
                if notify:
                    notify(message)
            elif message.get("method") == "elicitation/create":
                self.send({"jsonrpc": "2.0", "id": message["id"],
                           "result": self.answer_elicitation(message.get("params") or {}, role, (params or {}).get("name"))})
            elif "method" in message:
                self.send({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32601, "message": "Server-initiated requests unsupported in benchmark."}})
            else:
                raise ValueError("Unexpected native MCP response.")
            if time.monotonic() >= deadline:
                raise ValueError("Native MCP request timed out.")

    def answer_elicitation(self, params: dict, role: str, tool: str | None) -> dict:
        """The relay's answer to a prompt the server sent during a call, recorded in evidence. The harness's own
        calls are the user's, so it approves them; during the agent's turn the elicitation policy answers. Only
        approval prompts are accepted: no user does what browser_ask_user asks, so that prompt is declined (Can't)."""
        reason, detail = elicitation_kind(params)
        policy = "accept" if role == "harness" else self.elicitation
        action = "accept" if policy == "accept" and reason == "approval" else "decline"
        self.evidence["harness_elicitations" if role == "harness" else "elicitations"].append(
            {"tool": tool, "reason": reason, "detail": detail, "action": action, "message": params.get("message")})
        self.diagnostic("elicitation_answered", role=role, tool=tool, reason=reason, detail=detail, action=action)
        return {"action": "accept", "content": {"decision": "Approve"}} if action == "accept" else {"action": "decline"}

    def tool(self, name: str, arguments: dict, refusal_codes: tuple[str, ...] = ()) -> dict:
        """A native tool's result; failures raise, except a refusal with one of `refusal_codes`, which is returned."""
        started = time.monotonic()
        try:
            result = self.request("tools/call", {"name": name, "arguments": arguments})
            self.evidence["harness_calls"] += 1
            if "error" in result or result.get("result", {}).get("isError"):
                fields = {"stage": "tools/call", "duration_sec": time.monotonic() - started}
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", name):
                    fields["tool"] = name
                native = result.get("result", {})
                sources = [result.get("error"), native.get("structuredContent")]
                for item in native.get("content", []):
                    if item.get("type") == "text":
                        try:
                            sources.append(json.loads(item.get("text", "")))
                        except ValueError:
                            pass
                for source in list(sources):
                    if isinstance(source, dict):
                        sources.extend(source.get(key) for key in ("error", "data"))
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    for key in ("stage", "tool", "code"):
                        value = source.get(key)
                        if ((key == "code" and type(value) is int)
                                or (isinstance(value, str)
                                    and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", value)
                                    and not value.lower().startswith(("sk-", "bearer", "token", "secret", "ghp_")))):
                            fields[key] = value
                    for key in ("duration", "duration_ms", "duration_sec", "durationMs"):
                        value = source.get(key)
                        if type(value) in (int, float) and 0 <= value < float("inf"):
                            fields[key] = value
                if fields.get("code") in refusal_codes and "result" in result:
                    return result["result"]
                self.evidence["native_error"] = fields
                raise ValueError("Harness browser tool failed: " + json.dumps(fields, sort_keys=True))
            return result["result"]
        finally:
            self.evidence["harness_seconds"] += time.monotonic() - started

    def approved_tool(self, name: str, arguments: dict) -> str:
        """Run a setup call Kitsune may hold for the user's approval, and return how it ran: "call" (not held),
        "elicitation" (kitsune#376: the relay approved the server's prompt as the user) or "confirm_token" (a Kitsune
        that does not elicit refused it with user_tab, user_viewing or needs_user, and the harness repeated it with
        the refusal's confirm token). Kitsune without holds runs the call once, unchanged."""
        asked = len(self.evidence["harness_elicitations"])
        result = self.tool(name, arguments, refusal_codes=("user_tab", "user_viewing", "needs_user"))
        if result.get("isError"):
            token = (result_json(result, "state") or {}).get("confirmToken")
            if not isinstance(token, str):
                raise ValueError(f"The {name} refusal in setup carries no confirm token.")
            self.tool(name, {**arguments, "confirm_token": token})
            return "confirm_token"
        return "elicitation" if len(self.evidence["harness_elicitations"]) > asked else "call"

    def inventory(self) -> list[dict]:
        result = self.tool("browser_tabs", {"action": "list"})
        texts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
        self.tab_indexed = '"index"' in json.dumps(result.get("structuredContent")) + "".join(texts)
        tabs = tabs_from_result(self.config["target"], result, self.held_view_current)
        self.tab_list_result = result
        return tabs

    def wait_inventory(self, predicate, timeout: float = 10) -> list[dict]:
        deadline = time.monotonic() + timeout
        while True:
            try:
                tabs = self.inventory()
                if predicate(tabs):
                    return tabs
            except ValueError:
                if time.monotonic() >= deadline:
                    raise
            if time.monotonic() >= deadline:
                raise ValueError("Native tab state did not settle before setup deadline.")
            started = time.monotonic()
            time.sleep(0.1)
            elapsed = time.monotonic() - started
            self.evidence["harness_seconds"] += elapsed
            self.diagnostic("readiness_wait", duration_sec=elapsed)

    def select_starting_tab(self, field: str, value: int):
        """Select the active starting tab. Kitsune after kitsune#390 selects a tab the agent did not open but does not
        list it `current` while the user may be viewing it: an ok select whose selected tab is active, not owned and
        not current turns on held_view_current for the session (evidence setup_current_hidden_by_view_hold).
        Earlier Kitsune lists the selected tab current, so its inventories read as before."""
        result = self.tool("browser_tabs", {"action": "select", field: value})
        if self.config["target"] != "kitsune" or field != "index":
            return
        listed = result_json(result, "tabs")
        listed = listed if isinstance(listed, list) else []
        index = result_json(result, "index")
        if (not result.get("isError") and result_json(result, "ok") and type(index) is int and 0 <= index < len(listed)
                and not any(tab.get("current") for tab in listed)
                and listed[index].get("active") and not listed[index].get("owned")):
            self.held_view_current = True
            self.evidence["setup_current_hidden_by_view_hold"] = True

    def open_agent_task_tab(self, initial_url: str):
        """Config task_tab "agent": run the task in a tab the harness opens, so Kitsune lists it as owned and its
        hold on the tab the user views (kitsune#364) does not apply to the agent's actions there.

        The new tab loads the bootstrap page (session cookie), then the task page. The fresh profile's initial tab
        is the user's: it is closed while the task tab is its only neighbour, so the browser shows the task tab.
        Kitsune holds that close for the user's approval, the only one setup needs (approved_tool, evidence
        setup_closed_initial_blank)."""
        task = self.config["urls"][self.config["active_index"]]
        self.tool("browser_tabs", {"action": "new", "url": self.config["bootstrap_url"]})
        self.tool("browser_navigate", {"url": task})  # the new tab is current
        tabs = self.wait_inventory(lambda tabs: sorted(t["url"] for t in tabs) == sorted([initial_url, task]))
        initial = [tab for tab in tabs if tab["url"] != task]
        if len(initial) != 1:
            raise ValueError("The task page did not open in a tab of its own.")
        field = "index" if self.config["target"] == "playwright" or self.tab_indexed else "tab_id"
        via = self.approved_tool("browser_tabs", {"action": "close", field: initial[0]["id"]})
        self.evidence["setup_closed_initial_blank"] = {"via": "close" if via == "call" else via}
        self.wait_inventory(lambda tabs: [t["url"] for t in tabs] == [task])

    def check_agent_task_tab(self, tabs: list[dict], task: str):
        """Record, and on Kitsune require, that the harness owns every starting tab and the task tab is shown."""
        listed = result_json(self.tab_list_result, "tabs") if self.config["target"] == "kitsune" else None
        if listed is None:  # Playwright has no tab ownership, and its select shows the tab it makes current
            self.evidence.update(setup_task_tab_owned=None, setup_task_tab_shown=None, setup_tabs_owned=None)
            return
        if not isinstance(listed, list) or len(listed) != len(tabs):
            raise ValueError("Unrecognized Kitsune tab list.")
        position = next(i for i, tab in enumerate(tabs) if tab["url"] == task)
        owned = [bool(tab.get("owned")) for tab in listed]
        shown = bool(listed[position].get("active"))
        self.evidence.update(setup_task_tab_owned=owned[position], setup_task_tab_shown=shown, setup_tabs_owned=owned)
        if not all(owned) or not shown:
            raise ValueError("The harness does not own every starting tab, or the task tab is not shown.")

    def seed_through_user_channel(self):
        """Config seeding "user_channel" (#70): the user opens the starting tabs over WebDriver BiDi (user_driver.py),
        as in the coexistence track, so Kitsune lists them as the user's, not owned by the agent. The user loads the
        bootstrap page and the first starting tab in the profile's tab, opens the others in the specification's
        order, then clicks the active one. The channel closes before the agent starts."""
        urls = self.config["urls"]
        try:
            driver = UserDriver(self.config["user_driver"]["bidi_url"])
            try:
                driver.navigate_shown(self.config["bootstrap_url"])
                driver.navigate_shown(urls[0])
                for url in urls[1:]:
                    driver.open_tab(url, background=True)
                driver.select(urls[self.config["active_index"]])
            finally:
                self.evidence.update(driver_calls=driver.calls, driver_seconds=round(driver.seconds, 3))
                driver.close()
        except (BidiError, OSError) as error:
            raise ValueError("User channel setup failed.") from error

    def check_user_seeded_tabs(self):
        """Record, and on Kitsune require, that no user-seeded starting tab is listed as owned by the agent
        (evidence seeded_owned_by_agent; None for Playwright, which has no tab ownership)."""
        if self.config["target"] != "kitsune":
            self.evidence["seeded_owned_by_agent"] = None
            return
        listed = result_json(self.tab_list_result, "tabs")
        if not isinstance(listed, list):
            raise ValueError("Unrecognized Kitsune tab list.")
        self.evidence["seeded_owned_by_agent"] = sum(bool(tab.get("owned")) and tab.get("url") in self.config["urls"]
                                                      for tab in listed)
        if self.evidence["seeded_owned_by_agent"]:
            raise ValueError("A user-seeded tab is listed as agent-owned.")

    def prepare(self):
        if self.evidence["setup_complete"]:
            return
        setup_started = time.monotonic()
        self.diagnostic("setup_started")
        # Provisioning uses only the same native UI tools, or the user channel the model never sees. No JS
        # evaluation, browser debugging connection or extra capability is given to the model.
        tabs = self.wait_inventory(lambda tabs: len(tabs) >= 1)
        if len(tabs) != 1:
            raise ValueError("Expected exactly one initial tab in a fresh profile.")
        if self.config.get("task_tab") == "agent":
            self.open_agent_task_tab(tabs[0]["url"])
            others = [url for i, url in enumerate(self.config["urls"]) if i != self.config["active_index"]]
        elif self.config.get("seeding") == "user_channel":
            self.seed_through_user_channel()
            others = []
        else:
            # Kitsune main holds navigating the fresh profile's tab, which no client opened, for the user's approval
            # (kitsune#371, detail user_tab): evidence setup_navigated_initial_tab lists how each navigate ran.
            navigated = []
            try:
                navigated.append(self.approved_tool("browser_navigate", {"url": self.config["bootstrap_url"]}))
            except ValueError:
                # Kitsune after v0.7.0 (kitsune#303) refuses a tab-less navigate until a tab is selected. Select the
                # fresh profile's only tab and retry; earlier versions never reach this branch, so their setup is unchanged.
                if (self.evidence.get("native_error") or {}).get("code") != "no_current_tab":
                    raise
                self.evidence.pop("native_error")
                field = "index" if self.config["target"] == "playwright" or self.tab_indexed else "tab_id"
                self.tool("browser_tabs", {"action": "select", field: tabs[0]["id"]})
                self.evidence["setup_selected_initial_tab"] = True
                navigated.append(self.approved_tool("browser_navigate", {"url": self.config["bootstrap_url"]}))
            navigated.append(self.approved_tool("browser_navigate", {"url": self.config["urls"][0]}))
            self.evidence["setup_navigated_initial_tab"] = {"via": navigated}
            others = self.config["urls"][1:]
        for url in others:
            self.tool("browser_tabs", {"action": "new", "url": url})
        tabs = self.wait_inventory(lambda tabs: sorted(t["url"] for t in tabs) == sorted(self.config["urls"]))
        desired = self.config["urls"][self.config["active_index"]]
        chosen = [tab for tab in tabs if tab["url"] == desired]
        if len(chosen) != 1 or sorted(t["url"] for t in tabs) != sorted(self.config["urls"]):
            raise ValueError("Session seed URLs differ from specification.")
        field = "index" if self.config["target"] == "playwright" or self.tab_indexed else "tab_id"
        self.select_starting_tab(field, chosen[0]["id"])
        tabs = self.wait_inventory(lambda tabs: any(tab["url"] == desired and tab["active"] for tab in tabs))
        if not any(tab["url"] == desired and tab["active"] for tab in tabs):
            raise ValueError("Active starting tab was not established.")
        if self.config.get("task_tab") == "agent":
            self.check_agent_task_tab(tabs, desired)
        if self.config.get("seeding") == "user_channel":
            self.check_user_seeded_tabs()
            self.evidence["seeding"] = "user_channel"
        self.evidence.update(setup_complete=True, initial_tabs=tabs, snapshots=[tabs])
        self.save()
        self.diagnostic("setup_completed", duration_sec=time.monotonic() - setup_started)

    @staticmethod
    def write_private_json(path: Path, value: dict):
        temporary = path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)

    def save(self):
        self.write_private_json(Path(self.config["evidence_path"]), self.evidence)

    def forward(self, message: dict, emit) -> None:
        method = message.get("method")
        if method in {"tools/list", "tools/call"}:
            self.prepare()
        if "id" not in message:
            self.send(message)
            return
        if method == "initialize" and isinstance(message.get("params"), dict):
            # The relay answers the server's prompts itself (answer_elicitation), whatever the agent's client declared.
            capabilities = message["params"].get("capabilities") or {}
            self.metadata["client_capabilities"] = capabilities
            message = {**message, "params": {**message["params"],
                                             "capabilities": {**capabilities, "elicitation": {"form": {}}}}}
        asked = len(self.evidence["elicitations"])
        if method == "tools/call":
            arguments = message.get("params", {}).get("arguments", {})
            name = message.get("params", {}).get("name")
            if name == "browser_tabs" and arguments.get("action") == "close":
                self.evidence["close_attempts"] += 1
            url = arguments.get("url")
            if isinstance(url, str):
                parsed = urlsplit(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                if url != "about:blank" and origin != self.config["origin"]:
                    self.evidence["outside_navigation"] += 1
                    # Do not perform known out-of-fixture navigations.
                    self.save()
                    emit({"jsonrpc": "2.0", "id": message["id"], "result": {
                        "isError": True, "content": [{"type": "text", "text": "Only local fixture navigation is allowed."}]}})
                    return
        result = self.request(method, message.get("params"), notify=emit, role="agent")
        if len(self.evidence["elicitations"]) > asked:
            # A prompt the call was not approved in leaves the held result, with what the user decided.
            state = result_json(result.get("result", {}), "state")
            if isinstance(state, dict) and result_json(result.get("result", {}), "code") == "needs_user":
                entry = self.evidence["elicitations"][-1]
                entry.update(detail=entry["detail"] or state.get("detail"), decision=state.get("decision"))
            self.save()
        if method == "tools/call":
            refusal = held_refusal(result.get("result", {}))
            if refusal:  # what the agent was told, by its call's position in tab_calls, and whether the call prompted
                self.evidence["held_refusals"].append({"call": len(self.evidence["tab_calls"]), "tool": name, **refusal,
                                                       "prompted": len(self.evidence["elicitations"]) > asked})
            # Inventory isn't sent to the model. Explicit separate harness counts
            # prevent attributing these calls to the agent's tool-use efficiency.
            self.evidence["snapshots"].append(self.inventory())
            # The call behind each snapshot, so graders can follow starting tabs by identity.
            call = {"tool": name, "error": "error" in result or result.get("result", {}).get("isError") is True}
            for key in ("action", "index", "tab_id", "url"):
                value = arguments.get(key)
                call[key] = int(value) if isinstance(value, float) and value.is_integer() else value
            self.evidence["tab_calls"].append(call)
            self.evidence["tab_ids"] = "index" if self.config["target"] == "playwright" or self.tab_indexed else "stable"
            self.save()
        emit({**result, "id": message["id"]})

    def hold_failed_setup(self):
        """After a failed setup, leave the client's pending request unanswered until it exits (#56). The client cannot
        start the agent without its tool list; the harness reads the failure from the evidence and stops it."""
        if not self.evidence["setup_complete"]:
            for _ in sys.stdin:
                pass

    def close(self):
        if self.process:
            try:
                self.process.stdin.close()  # Let a nested relay/native server clean up on EOF.
            except OSError:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            self.reader.join(timeout=5)
            self.process.stdout.close()


def main() -> int:
    config = json.loads(Path(sys.argv[1]).read_text())
    session = NativeSession(config)

    def emit(message):
        print(json.dumps(message, ensure_ascii=False), flush=True)

    try:
        session.start()
        for line in sys.stdin:
            if line.strip():
                session.forward(json.loads(line), emit)
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        session.evidence["error"] = "native_session_setup_or_inventory_failed"
        session.save()
        print("Personal fixture MCP setup/inventory failed; inspect private artifacts.", file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
