"""The simulated user of the coexistence track, over WebDriver BiDi. No model calls.

Firefox runs with `--remote-debugging-port` and `--remote-allow-system-access`, so this
driver can act in the browser chrome the way a person does: open and select tabs and type
with trusted input. It never touches page content while the agent works. Nothing here goes through the MCP server under test, so:

- tabs it opens are the user's (Kitsune omits `owned`, i.e. not owned), not agent tabs;
- its keystrokes are trusted events (`isTrusted: true`), which is what Kitsune's
  user-activity detection counts;
- `view()` reads the tab the user actually sees (`gBrowser.selectedTab`) and whether the
  window has focus, instead of an MCP server's tool cursor.

It is a privileged local channel. The agent's tool policy exposes only MCP UI tools; it
has no shell or network tool that could reach the port.
"""
from __future__ import annotations

import json
import threading
import time

from .bidi import Bidi, BidiError

SYSTEM = "{triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()"

TABS_JS = """(() => [...Services.wm.getEnumerator('navigator:browser')].map(w => ({
  focused: Services.focus.activeWindow === w,
  tabs: w.gBrowser.tabs.map(t => ({url: t.linkedBrowser.currentURI.spec, selected: t.selected,
    container: Number(t.getAttribute('usercontextid') || 0),
    loading: t.linkedBrowser.webProgress ? t.linkedBrowser.webProgress.isLoadingDocument : false}))})))()"""


class UserDriver:
    def __init__(self, url: str, connect_timeout: float = 30):
        deadline = time.monotonic() + connect_timeout
        while True:
            try:
                self.bidi = Bidi(url)
                break
            except (OSError, BidiError):
                if time.monotonic() >= deadline:
                    raise BidiError("User channel (WebDriver BiDi) did not come up.")
                time.sleep(0.25)
        self.lock = threading.RLock()
        self.calls = 0
        self.seconds = 0.0

    def _timed(self, function, *args, **kwargs):
        with self.lock:
            started = time.monotonic()
            try:
                return function(*args, **kwargs)
            finally:
                self.calls += 1
                self.seconds += time.monotonic() - started

    def chrome(self, expression: str):
        def run():
            windows = self.bidi.command("browsingContext.getTree", {"maxDepth": 0, "moz:scope": "chrome"})["contexts"]
            if not windows:
                raise BidiError("No browser window.")
            return self.bidi.evaluate(windows[0]["context"], expression)
        return self._timed(run)

    def windows(self) -> list[dict]:
        return self.chrome(TABS_JS)

    def view(self) -> dict:
        """The tab the user sees: the selected tab of the focused window (else the first window)."""
        windows = self.windows()
        shown = next((w for w in windows if w["focused"]), windows[0] if windows else None)
        selected = next((t for t in (shown or {}).get("tabs", []) if t["selected"]), None)
        return {"url": selected["url"] if selected else None,
                "window_focused": bool(shown and shown["focused"]), "windows": len(windows),
                "tabs": sum(len(w["tabs"]) for w in windows)}

    def wait(self, predicate, timeout: float = 15, what: str = "user tab state"):
        deadline = time.monotonic() + timeout
        while True:
            windows = self.windows()
            if predicate(windows):
                return windows
            if time.monotonic() >= deadline:
                raise BidiError(f"Timed out waiting for {what}.")
            time.sleep(0.1)

    @staticmethod
    def all_tabs(windows: list[dict]) -> list[dict]:
        return [tab for window in windows for tab in window["tabs"]]

    def navigate_shown(self, url: str) -> None:
        """Like typing a URL into the address bar of the tab the user sees."""
        self.chrome(f"void gBrowser.selectedBrowser.fixupAndLoadURIString({json.dumps(url)}, {SYSTEM}}})")
        self.wait(lambda w: any(t["selected"] and t["url"] == url and not t["loading"] for t in self.all_tabs(w)),
                  what="the user's navigation")

    def open_tab(self, url: str, *, background: bool = True) -> None:
        """Like the user opening a tab (Ctrl+T, then a URL), in the shown tab's container."""
        self.chrome(f"void gBrowser.addTab({json.dumps(url)}, {SYSTEM}, inBackground: {json.dumps(background)},"
                    " userContextId: Number(gBrowser.selectedTab.getAttribute('usercontextid') || 0)})")
        self.wait(lambda w: any(t["url"] == url and not t["loading"] for t in self.all_tabs(w)),
                  what="the user's new tab")

    def select(self, url: str) -> None:
        """Like clicking a tab in the tab strip. The URL must name exactly one tab."""
        found = self.chrome(f"""(() => {{ const tabs = gBrowser.tabs.filter(t => t.linkedBrowser.currentURI.spec === {json.dumps(url)});
            if (tabs.length !== 1) return tabs.length; gBrowser.selectedTab = tabs[0]; return 1; }})()""")
        if found != 1:
            raise BidiError("The user's tab to select is missing or ambiguous.")
        self.wait(lambda w: any(t["selected"] and t["url"] == url for t in self.all_tabs(w)), what="tab selection")

    def type_text(self, text: str) -> str:
        """Trusted key presses into whatever has focus in the shown tab, like a real keyboard.
        Returns the URL of the tab that received them, read in the same chrome call.

        Uses the chrome window's nsITextInputProcessor, not BiDi `input.performActions`:
        content-side BiDi input permanently breaks Playwright's Juggler-instrumented pages
        (probe, 2026-10-23), which would fault one target and not the other.
        """
        result = self.chrome(f"""(() => {{ const tip = Cc['@mozilla.org/text-input-processor;1']
            .createInstance(Ci.nsITextInputProcessor);
          // A person's keys go to the page they look at, not the address bar.
          if (document.activeElement !== gBrowser.selectedBrowser) gBrowser.selectedBrowser.focus();
          if (!tip.beginInputTransactionForTests(window)) return null;
          const shown = gBrowser.selectedBrowser.currentURI.spec;
          for (const key of {json.dumps(text)}) {{ const event = new window.KeyboardEvent('', {{key}});
            tip.keydown(event); tip.keyup(event); }}
          return shown; }})()""")
        if not isinstance(result, str):
            raise BidiError("The keyboard is busy.")
        return result

    def field_value(self, url: str, selector: str) -> dict:
        """Reads a field through a content sandbox. Only after the agent has finished (see type_text).

        `lost` (no tab at the URL any more) and `ambiguous` (several) are agent outcomes: the user
        never navigates or duplicates their tab. A channel failure raises instead."""
        contexts = [c for c in self._timed(self.bidi.top_contexts) if c["url"] == url]
        if len(contexts) != 1:
            return {"status": "lost" if not contexts else "ambiguous", "value": None}
        return {"status": "ok", "value": self._timed(self.bidi.evaluate, contexts[0]["context"],
                f"(document.querySelector({json.dumps(selector)}) || {{}}).value ?? null")}

    def close(self) -> None:
        with self.lock:
            self.bidi.close()


class TypingUser(threading.Thread):
    """Keeps typing into one field of their tab, like a person writing while the agent works.

    Each tick types the next chunk into whatever tab is shown. The user's field has
    `autofocus`, and Firefox restores a tab's focus when it is shown again. If the agent
    took the view away, the chunk goes to that tab's focused element instead (a
    misdirected keystroke), as it would for a real person, and is recorded as such.
    Nothing here touches page content while the agent works.
    """

    def __init__(self, driver: UserDriver, *, url: str, selector: str, text: str,
                 chunk: int = 3, interval: float = 0.6):
        super().__init__(daemon=True)
        self.driver, self.url, self.selector, self.text = driver, url, selector, text
        self.chunk, self.interval = chunk, interval
        self.stop_event = threading.Event()
        self.record = {"url": url, "selector": selector, "typed_into_user_field": "", "misdirected": [],
                       "ticks": 0, "errors": 0, "finished": False}

    def run(self) -> None:
        position = 0
        while not self.stop_event.is_set() and position < len(self.text):
            piece = self.text[position:position + self.chunk]
            try:
                shown = self.driver.type_text(piece)
                if shown == self.url:
                    self.record["typed_into_user_field"] += piece
                else:
                    self.record["misdirected"].append({"url": shown, "text": piece})
                position += len(piece)
            except Exception:  # noqa: BLE001 - any failure is counted; the run cannot be scored as clean
                self.record["errors"] += 1
            self.record["ticks"] += 1
            self.stop_event.wait(self.interval)
        self.record["finished"] = position >= len(self.text)

    def stop(self) -> dict:
        self.stop_event.set()
        self.join(timeout=10)
        return {**self.record, "alive_at_stop": self.is_alive()}


class ViewSampler(threading.Thread):
    """Records every change of the shown tab or window focus, between and during agent calls."""

    def __init__(self, driver: UserDriver, interval: float = 0.25):
        super().__init__(daemon=True)
        self.driver, self.interval = driver, interval
        self.stop_event = threading.Event()
        self.started = time.monotonic()
        self.transitions: list[dict] = []
        self.errors = 0

    def run(self) -> None:
        last = None
        while not self.stop_event.is_set():
            try:
                view = self.driver.view()
                key = (view["url"], view["window_focused"], view["windows"])
                if key != last:
                    self.transitions.append({"t": round(time.monotonic() - self.started, 3), **view})
                    last = key
            except Exception:  # noqa: BLE001 - a silent sampler outage must not look like a still view
                self.errors += 1
            self.stop_event.wait(self.interval)

    def stop(self) -> dict:
        self.stop_event.set()
        self.join(timeout=5)
        return {"interval_sec": self.interval, "transitions": self.transitions, "errors": self.errors,
                "alive_at_stop": self.is_alive()}
