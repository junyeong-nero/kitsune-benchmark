"""Configured browser geometry is not a measurement of the content viewport."""
from __future__ import annotations

import re


def viewport_record(target: str, server_args=(), firefox_args=()) -> dict:
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
                          "source": "firefox_launch_args"}
    return {"configured": configured,
            "configured_args": list(server_args if target == "playwright" else firefox_args),
            "effective": None,
            "effective_unavailable_reason": "not_observable_without_agent_visible_calls",
            "content_viewport_equality_asserted": False}
