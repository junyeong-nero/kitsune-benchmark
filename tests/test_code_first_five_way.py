"""No-inference checks for the code-first experiment's sources, denominators and order."""
from collections import Counter, defaultdict
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("code_first_five_way", ROOT / "scripts/run-code-first-five-way.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
five = experiment.five


class CodeFirstFiveWayTests(unittest.TestCase):
    def test_frozen_sources_and_actual_product_surfaces(self):
        self.assertEqual(five.SHAS, {"main": "47dafa20a3fddc697a7d991e15d39e4b0232c10d",
                                    "scripting": "f5c7a0f85aefd89e621e73665e33d33d79d50676"})
        self.assertEqual(list(five.EXPECTED.values()), [14, 6, 23, 1, 1])
        for arm in ("kitsune-default", "kitsune-code-first"):
            self.assertEqual(five.ARMS[arm][2:], ({}, None), "no allowlist or policy overrides")
        self.assertTrue(five.RECORD_CATALOG)
        self.assertIn(ROOT / "scripts/run-code-first-five-way.py", five.RUNNER_FILES)
        self.assertEqual(five.ARMS["aside"][3], ("repl",))

    def test_seventy_unique_cells_with_reversed_second_repeat(self):
        plan = five.plan()
        self.assertEqual(len(plan), 70)
        self.assertEqual([r["seq"] for r in plan], list(range(1, 71)))
        self.assertEqual(Counter(r["arm"] for r in plan), dict.fromkeys(five.ARMS, 14))
        grouped = defaultdict(list)
        for row in plan:
            grouped[row["task"], row["repeat"]].append(row["arm"])
        self.assertEqual(len(grouped), 14)
        for task in five.suite.ab.MINIWOB:
            self.assertEqual(grouped[task, 1], grouped[task, 0][::-1])

    def test_analysis_uses_both_kitsune_baselines(self):
        with patch.object(five.suite.ab, "load_log", return_value=[]):
            report = five.analyze(Path("unused"))
        self.assertEqual(list(report["paired_ratios"]), ["kitsune-default", "kitsune-code-first"])
        self.assertEqual(report["all_five_joint_cells"], 0)


if __name__ == "__main__":
    unittest.main()
