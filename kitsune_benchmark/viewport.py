"""Configured browser geometry and the content viewport observed by fixture pages (#21)."""
from __future__ import annotations

import base64
import hashlib
import json
import re

# Playwright's --viewport-size is this content viewport. Headless Firefox's --height is the
# window, whose toolbars took 85 CSS px (inner 1280x635 at --height=720) in the native check of
# the pinned Firefox; the equalized Kitsune window adds them back.
CONTENT_WIDTH, CONTENT_HEIGHT = 1280, 720
FIREFOX_CHROME_HEIGHT = 85
REFERENCE = {"innerWidth": CONTENT_WIDTH, "innerHeight": CONTENT_HEIGHT, "devicePixelRatio": 1}
REPORT_FIELDS = ("innerWidth", "innerHeight", "outerWidth", "outerHeight", "devicePixelRatio")
REPORT_PATH = "/viewport-report"


def report_script(url: str) -> tuple[str, str]:
    """Inline load-time report with no DOM output, and its CSP script hash."""
    script = f"navigator.sendBeacon({json.dumps(url)},new URLSearchParams({{{','.join(REPORT_FIELDS)}}}))"
    return script, "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"


def parse_report(values: dict[str, str]) -> dict | None:
    if set(values) != set(REPORT_FIELDS):
        return None
    report = {}
    for name in REPORT_FIELDS:
        if not re.fullmatch(r"\d{1,5}(\.\d{1,20})?", values[name]):
            return None
        number = float(values[name])
        report[name] = int(number) if number.is_integer() else number
    return report


def viewport_record(target: str, server_args=(), firefox_args=(), *, equalized: bool = False) -> dict:
    def option(args, name):
        values = set()
        for i, arg in enumerate(args):
            if arg.startswith(name + "="):
                values.add(arg[len(name) + 1:])
            if arg == name and i + 1 < len(args):
                values.add(args[i + 1])
        return values.pop() if len(values) == 1 else None
    configured = None
    if target == "playwright":
        size = option(server_args, "--viewport-size")
        match = re.fullmatch(r"(\d+)x(\d+)", size or "")
        if match:
            configured = {"viewport_size": {"width": int(match[1]), "height": int(match[2])},
                          "kind": "content_viewport", "source": "playwright_server_args"}
    elif target == "kitsune":
        width, height = option(firefox_args, "--width"), option(firefox_args, "--height")
        if width and height and width.isdigit() and height.isdigit():
            configured = {"window_size": {"width": int(width), "height": int(height)},
                          "kind": "window", "headless": "-headless" in firefox_args,
                          "source": "firefox_launch_args",
                          "content_viewport_construction": {
                              "content_size": {"width": CONTENT_WIDTH, "height": CONTENT_HEIGHT},
                              "firefox_chrome_height": FIREFOX_CHROME_HEIGHT} if equalized else None}
    return {"configured": configured,
            "configured_args": list(server_args if target == "playwright" else firefox_args),
            "effective": None,
            "effective_unavailable_reason": "not_observed",
            "content_viewport_equality_asserted": False}


def observed_viewport(record: dict, reports: list[dict] | None) -> dict:
    """Add the run's fixture page reports; None means the track's pages do not report.

    Equality is asserted only when every report agrees and matches REFERENCE, the content
    viewport both targets are measured against."""
    if reports is None:
        return {**record, "effective_unavailable_reason": "track_pages_do_not_report"}
    if not reports:
        return {**record, "effective_unavailable_reason": "no_report_received"}
    first = {name: reports[0][name] for name in REPORT_FIELDS}
    differed = any({name: r[name] for name in REPORT_FIELDS} != first for r in reports[1:])
    matches = all(first[name] == value for name, value in REFERENCE.items())
    return {**record, "effective": {**first, "source": "fixture_page_load_report", "reports": len(reports),
                                    "later_reports_differed": differed},
            "effective_unavailable_reason": None,
            "reference": dict(REFERENCE),
            "content_viewport_equality_asserted": matches and not differed}
