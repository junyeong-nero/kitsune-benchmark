"""Code-first Python vs current Kitsune, Playwright, ego lite and Aside (70 attempts).

Fixed sources, actual 14/6-tool Kitsune surfaces; no API billing or delegated agents.
Reuses the frozen five-way protocol, rotated order, catalog checks and stopping policy.
See docs/experiments/2026-11-12-code-first-five-way.md.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("five_way", ROOT / "scripts/run-five-way-miniwob.py")
five = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(five)

five.BENCHMARK = "claude-code-first-five-way-v1"
five.SHAS = {"main": "47dafa20a3fddc697a7d991e15d39e4b0232c10d",
             "scripting": "f5c7a0f85aefd89e621e73665e33d33d79d50676"}
five.ARMS = {
    "kitsune-default": ("kitsune", "main", {}, None),
    "kitsune-code-first": ("kitsune", "scripting", {}, None),
    "playwright": ("playwright", "main", {}, five.external.TOOLS["playwright"]),
    "ego": ("ego", "main", {}, five.external.TOOLS["ego"]),
    "aside": ("aside", "main", {}, five.external.TOOLS["aside"]),
}
five.EXPECTED = dict(zip(five.ARMS, (14, 6, 23, 1, 1)))
five.suite.ab.EXPECTED_TOOLS = five.EXPECTED
five.PROJECT_DEFAULTS = {"main": str(ROOT / "artifacts/vendor/kitsune-code-first-baseline-47dafa2"),
                         "scripting": str(ROOT.parent / "kitsune")}
five.RUNNER_FILES += (Path(__file__),)
five.RECORD_CATALOG = True
five.CONTEXT_PREFIX = "bm-code-first-20261112-v1"
five.__doc__ = __doc__

if __name__ == "__main__":
    raise SystemExit(five.main())
