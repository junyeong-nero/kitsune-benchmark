import unittest
from unittest.mock import patch

from kitsune_benchmark import agent_combinations as pilot


class PilotPlanTests(unittest.TestCase):
    def test_plan_does_not_connect_or_launch_a_process(self):
        with patch("socket.socket.connect", side_effect=AssertionError("network")), \
                patch("subprocess.Popen", side_effect=AssertionError("process")):
            plan = pilot.plan()
        self.assertFalse(plan["model_invoked"])
        self.assertFalse(plan["execution_ready"])
        self.assertEqual(plan["mode"], "plan_only")

    def test_approved_caps_do_not_reallocate_blocked_native_slots(self):
        plan = pilot.plan()
        self.assertEqual(plan["operator_start_cap"], 33)
        self.assertEqual(plan["executable_start_cap"], 30)
        self.assertEqual(plan["unused_native_agent_slots"], 3)
        self.assertEqual(plan["api_budget_usd"], 0)
        rows = plan["attempts"]
        self.assertEqual([r["seq"] for r in rows], list(range(1, 31)))
        self.assertEqual(sum(r["execution"] == "cli" for r in rows), 27)
        self.assertEqual(sum(r["execution"] == "manual" for r in rows), 3)
        self.assertFalse(any(r["baseline"] == "browser-use-agent" for r in rows))

    def test_model_panels_and_actual_six_tool_kitsune_are_explicit(self):
        rows = pilot.baselines()
        self.assertEqual(sum(r.get("harness") == "codex" for r in rows), 7)
        self.assertEqual(sum(r.get("harness") == "claude" for r in rows), 2)
        for row in rows:
            if row["execution"] == "cli":
                self.assertEqual(row["model"], pilot.MODELS[row["harness"]])
                self.assertEqual(row["effort"], "medium")
                self.assertEqual(row["state"], "preflight_pending")
            if row.get("surface") == "kitsune-zen":
                self.assertEqual(len(set(row["tools"])), 6)
                self.assertIn("browser_run_python", row["tools"])
                self.assertNotIn("browser_click", row["tools"])

    def test_each_combination_has_exactly_the_three_frozen_conditions(self):
        plan = pilot.plan()
        expected = {c["unit"] for c in pilot.CONDITIONS}
        for baseline in {r["baseline"] for r in plan["attempts"]}:
            rows = [r for r in plan["attempts"] if r["baseline"] == baseline]
            self.assertEqual(len(rows), 3)
            self.assertEqual({r["unit"] for r in rows}, expected)
            self.assertTrue(all(r["variant"] == r["repeat"] == 0 for r in rows))
        first = plan["attempts"][:plan["first_cli_audit_size"]]
        self.assertEqual(len({r["baseline"] for r in first}), 9)
        self.assertEqual({r["unit"] for r in first}, {"pb-longpage-01"})

    def test_manual_chrome_is_not_an_automated_or_measured_usage_proxy(self):
        chrome = next(r for r in pilot.baselines() if r["id"] == "chrome-sidepanel")
        self.assertEqual(chrome["execution"], "manual")
        for metric in ("usage", "exact_agent_elapsed", "tab_custody"):
            self.assertIsNone(chrome[metric])
        self.assertIn("no automated attachment", chrome["browser"])

    def test_larger_matrix_fails_instead_of_spending_the_remaining_slots(self):
        extra = {**pilot.CLI_SURFACES, "unauthorized": {"label": "new", "browser": "new"}}
        with patch.object(pilot, "CLI_SURFACES", extra), self.assertRaisesRegex(ValueError, "authorized"):
            pilot.plan()


if __name__ == "__main__":
    unittest.main()
