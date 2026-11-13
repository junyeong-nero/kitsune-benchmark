"""Claude subscription replication of scripting core vs the new unset-CAPS default.

Same c698d40 checkout, 20 tasks, seed/variants and 80-attempt ABBA schedule as the
separate Codex cohort. Both arms enable scripting and expose 14 tools. No API-key
billing. Request counts, first-request input and list-price cost are observed in
Claude stream-json; the latter is an estimate, not a subscription charge.

  run --kitsune-project DIR --kitsune-sha SHA --out DIR --continue-unstarted
  analyze --out DIR

Stops on quota/execution/telemetry/source/catalog errors; preserves failed rows.
See docs/experiments/2026-11-12-claude-caps-and-main.md.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("subscription_ab", ROOT / "scripts/run-codex-scripting-ab.py")
suite = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(suite)

_ORIGINAL_PLAN = suite.ab.plan()
ARMS = {"core": {"KITSUNE_SCRIPTING": "1", "KITSUNE_CAPS": "core"},
        "default": {"KITSUNE_SCRIPTING": "1"}}


def plan():
    names = {"legacy": "core", "scripting": "default"}
    return [{**run, "arm": names[run["arm"]]} for run in _ORIGINAL_PLAN]


suite.BENCHMARK = "kitsune-claude-scripting-caps-ab-v1"
suite.HARNESS = "claude"
suite.UNAVAILABLE = []
suite.CATALOG_LIMIT = "Claude init inventory for every run, plus relay inventory for personal/gallery."
suite.ab.ARMS = ARMS
suite.ab.EXPECTED_TOOLS = {arm: 14 for arm in ARMS}
suite.ab.plan = plan
suite.RUNNER_FILES += (Path(__file__),)
suite.__doc__ = __doc__

if __name__ == "__main__":
    raise SystemExit(suite.main())
