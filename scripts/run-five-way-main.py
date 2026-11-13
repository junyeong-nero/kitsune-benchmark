"""Claude five-way MiniWoB on main 79eb955: actual default vs actual legacy opt-out.

Both Kitsune arms use the same checkout, no benchmark allowlist (30 legacy / 14 default).
PW/ego/Aside retain their 23/1/1 allowlists. Every attempt gets a unique context name,
model-facing catalog logging and before/after catalog checks. No model API billing.
See docs/experiments/2026-11-12-five-way-main-79eb955.md.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("five_way", ROOT / "scripts/run-five-way-miniwob.py")
five = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(five)

SHA = "79eb95594eee57bf429c1594c883f1995294dbc8"
five.BENCHMARK = "claude-five-way-main-79eb955-v1"
five.SHAS = {"main": SHA, "scripting": SHA}
five.ARMS = {
    "kitsune-legacy": ("kitsune", "main", {"KITSUNE_SCRIPTING": "0"}, None),
    "kitsune-default": ("kitsune", "scripting", {}, None),
    "playwright": ("playwright", "main", {}, five.external.TOOLS["playwright"]),
    "ego": ("ego", "main", {}, five.external.TOOLS["ego"]),
    "aside": ("aside", "main", {}, five.external.TOOLS["aside"]),
}
five.EXPECTED = dict(zip(five.ARMS, (30, 14, 23, 1, 1)))
five.suite.ab.EXPECTED_TOOLS = five.EXPECTED
five.PROJECT_DEFAULTS = {key: str(ROOT / "artifacts/vendor/kitsune-main-79eb955") for key in five.SHAS}
five.RUNNER_FILES += (Path(__file__),)
five.RECORD_CATALOG = True
five.CONTEXT_PREFIX = "bm-79eb955-20261112-v1"
five.__doc__ = __doc__

if __name__ == "__main__":
    raise SystemExit(five.main())
