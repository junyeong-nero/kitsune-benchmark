"""Coexistence relay: the personal relay, but the *user* seeds the session and watches the view.

Differences from `personal_session.py`:

- Starting tabs are opened through the user channel (`user_driver.py`, WebDriver BiDi),
  not with the MCP server's `browser_tabs new`. Kitsune therefore lists them as user tabs.
  Setup fails (unscorable) if the MCP server reports any starting tab as agent-owned.
- Tab order is the personal track's: the user opens the starting tabs in order, then
  clicks the task's active tab, which is the tab they see. One hidden `browser_tabs select`
  still pins the tool cursor there, as in the personal relay, so its graders keep their meaning.
- After every agent call, and every `sampler_interval` seconds in between, the shown tab and
  window focus are recorded (`evidence["view"]`). The agent never sees this channel.
- An optional typing user (`config["user_activity"]`) types into a field of their tab during
  the run; keystrokes that land elsewhere because the view moved are recorded.

Driver calls are counted separately from harness MCP calls (`driver_calls`, `driver_seconds`).
Agent calls that Kitsune refuses with code `user_tab` (the protect-user-tabs arm) are counted
in `user_tab_refusals`.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kitsune_benchmark.bidi import BidiError  # noqa: E402
from kitsune_benchmark.personal_session import NativeSession  # noqa: E402
from kitsune_benchmark.user_driver import TypingUser, UserDriver, ViewSampler  # noqa: E402


def owned_urls(target: str, result: dict) -> list[str] | None:
    """URLs Kitsune lists as agent-owned; None for servers without an ownership notion."""
    if target != "kitsune":
        return None
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                tabs = json.loads(item["text"]).get("tabs")
            except (ValueError, AttributeError):
                continue
            if isinstance(tabs, list):
                return [tab.get("url") for tab in tabs if tab.get("owned")]
    raise ValueError("Unrecognized Kitsune tab list.")


def user_tab_refusal(response: dict) -> bool:
    """A Kitsune tool error with code user_tab: protection refused to navigate a user's tab."""
    result = response.get("result") or {}
    if not result.get("isError"):
        return False
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                if json.loads(item["text"]).get("code") == "user_tab":
                    return True
            except (ValueError, AttributeError):
                continue
    return False


class CoexistenceSession(NativeSession):
    def __init__(self, config: dict):
        super().__init__(config)
        self.driver: UserDriver | None = None
        self.sampler: ViewSampler | None = None
        self.typist: TypingUser | None = None
        self.evidence.update(seeding=None, seeded_owned_by_agent=None, view=None,
                             user_activity=None, driver_calls=0, driver_seconds=0.0, user_tab_refusals=0)

    def raw_tabs(self) -> dict:
        return self.tool("browser_tabs", {"action": "list"})

    def prepare(self):
        if self.evidence["setup_complete"]:
            return
        setup_started = time.monotonic()
        self.diagnostic("setup_started")
        # The first call starts Playwright's browser; Kitsune's is already running.
        tabs = self.wait_inventory(lambda tabs: len(tabs) >= 1)
        if len(tabs) != 1:
            raise ValueError("Expected exactly one initial tab in a fresh profile.")
        try:
            self.driver = UserDriver(self.config["user_driver"]["bidi_url"])
            urls, active = self.config["urls"], self.config["active_index"]
            # The user opened the starting tabs in the personal track's order, then clicked the active one.
            self.driver.navigate_shown(self.config["bootstrap_url"])
            self.driver.navigate_shown(urls[0])
            for url in urls[1:]:
                self.driver.open_tab(url, background=True)
            self.driver.select(urls[active])
        except BidiError as error:
            raise ValueError("User channel setup failed.") from error
        tabs = self.wait_inventory(lambda tabs: sorted(t["url"] for t in tabs) == sorted(urls))
        if [t["url"] for t in tabs] != list(urls):
            raise ValueError("User-seeded tab order differs from the personal specification.")
        desired = urls[active]
        chosen = [tab for tab in tabs if tab["url"] == desired]
        if len(chosen) != 1:
            raise ValueError("Session seed URLs differ from specification.")
        field = "index" if self.config["target"] == "playwright" or self.tab_indexed else "tab_id"
        self.tool("browser_tabs", {"action": "select", field: chosen[0]["id"]})
        tabs = self.wait_inventory(lambda tabs: any(tab["url"] == desired and tab["active"] for tab in tabs))
        owned = owned_urls(self.config["target"], self.raw_tabs())
        if owned is not None:
            self.evidence["seeded_owned_by_agent"] = sum(url in urls for url in owned)
            if self.evidence["seeded_owned_by_agent"]:
                raise ValueError("A user-seeded tab is listed as agent-owned.")
        try:
            view = self.driver.view()
            if view["url"] != desired:
                raise ValueError("The user's view is not on the active starting tab.")
            self.evidence["view"] = {"initial_url": desired, "after_call": [], "sampler": None}
            self.sampler = ViewSampler(self.driver, float(self.config.get("sampler_interval", 0.25)))
            self.sampler.start()
            activity = self.config.get("user_activity")
            if activity:
                self.typist = TypingUser(self.driver, url=urls[activity["tab_index"]], selector=activity["selector"],
                                         text=activity["text"], chunk=activity.get("chunk", 3),
                                         interval=activity.get("interval", 0.6))
                self.typist.start()
        except RuntimeError as error:  # BidiError, or a thread that could not start
            raise ValueError("User channel setup failed.") from error
        # Complete only once the simulated user runs, so a failure up to here is a setup failure (#56).
        self.evidence.update(seeding="user_bidi", setup_complete=True, initial_tabs=tabs, snapshots=[tabs])
        self.save()
        self.diagnostic("setup_completed", duration_sec=time.monotonic() - setup_started)

    def sample_after_call(self) -> None:
        if self.driver is None or self.evidence.get("view") is None:
            return
        try:
            self.evidence["view"]["after_call"].append(self.driver.view())
        except (BidiError, OSError, StopIteration, ValueError):
            self.evidence["view"]["after_call"].append({"url": None, "error": True})

    def forward(self, message: dict, emit) -> None:
        if message.get("method") != "tools/call" or "id" not in message:
            super().forward(message, emit)
            return

        def answered(response: dict) -> None:
            if response.get("id") == message["id"]:
                if self.config["target"] == "kitsune" and user_tab_refusal(response):
                    self.evidence["user_tab_refusals"] += 1
                self.sample_after_call()
                self.save()
            emit(response)
        super().forward(message, answered)

    def save(self):
        if self.driver is not None:
            self.evidence.update(driver_calls=self.driver.calls, driver_seconds=round(self.driver.seconds, 3))
        super().save()

    def finish_user(self) -> None:
        """Stop the simulated user and read their field before the MCP server (and its browser) exits."""
        if self.typist is not None:
            record = self.typist.stop()
            try:
                field = self.driver.field_value(record["url"], record["selector"])
            except (BidiError, OSError):
                field = {"status": "error", "value": None}
            record.update(final_field_status=field["status"], final_field_value=field["value"])
            self.evidence["user_activity"] = record
            self.typist = None
        if self.sampler is not None:
            self.evidence["view"]["sampler"] = self.sampler.stop()
            self.sampler = None
        if self.driver is not None:
            self.save()
            self.driver.close()
            self.driver = None

    def close(self):
        try:
            self.finish_user()
        except (BidiError, OSError, ValueError):
            self.evidence["user_channel_error"] = True
            self.save()
        super().close()


def main() -> int:
    config = json.loads(Path(sys.argv[1]).read_text())
    session = CoexistenceSession(config)

    def emit(message):
        print(json.dumps(message, ensure_ascii=False), flush=True)

    try:
        session.start()
        for line in sys.stdin:
            if line.strip():
                session.forward(json.loads(line), emit)
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        session.evidence["error"] = "coexistence_session_setup_or_inventory_failed"
        session.save()
        print("Coexistence fixture MCP setup/inventory failed; inspect private artifacts.", file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
