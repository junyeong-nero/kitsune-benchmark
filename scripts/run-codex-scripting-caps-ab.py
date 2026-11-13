"""Codex A/B of scripting's explicit core limit vs its new unset-CAPS default.

Both arms use KITSUNE_SCRIPTING=1 and the same patched Kitsune checkout. `core`
sets KITSUNE_CAPS=core; `default` leaves it unset (expected all). Both publish 14
tools. Tasks, ABBA order, grades, resume/stop rules and metrics reuse the Codex
scripting runner. All matched ratios are default / core.

  run --kitsune-project DIR --kitsune-sha SHA --out DIR --continue-unstarted
  analyze --out DIR

See docs/experiments/2026-11-11-codex-scripting-caps-ab.md. No API-key billing.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("codex_scripting_ab", ROOT / "scripts/run-codex-scripting-ab.py")
suite = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(suite)

_ORIGINAL_PLAN = suite.ab.plan()
ARMS = {"core": {"KITSUNE_SCRIPTING": "1", "KITSUNE_CAPS": "core"},
        "default": {"KITSUNE_SCRIPTING": "1"}}


def plan():
    names = {"legacy": "core", "scripting": "default"}
    return [{**run, "arm": names[run["arm"]]} for run in _ORIGINAL_PLAN]


suite.BENCHMARK = "kitsune-codex-scripting-caps-ab-v1"
suite.ab.ARMS = ARMS
suite.ab.EXPECTED_TOOLS = {arm: 14 for arm in ARMS}
suite.ab.plan = plan
suite.RUNNER_FILES += (Path(__file__),)
suite.__doc__ = __doc__

if __name__ == "__main__":
    raise SystemExit(suite.main())
