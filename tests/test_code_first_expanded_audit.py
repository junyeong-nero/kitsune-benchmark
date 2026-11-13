"""Offline usage accounting must not turn missing timeout usage into a saving."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("expanded_audit_test", ROOT / "scripts/audit-code-first-expanded-ab.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ExpandedAuditTests(unittest.TestCase):
    def test_missing_usage_is_separate_from_reported_zero(self):
        rows = [{"input": 100}, {"input": 0}, {"input": None}, {}]
        self.assertEqual(audit.coverage(rows)["input"], {
            "known_total": 100, "reported_attempts": 2, "missing_attempts": 2})
        self.assertIsNone(rows[2]["input"])
        self.assertNotIn("input", rows[3])

    def test_timeout_time_and_requests_do_not_impute_final_usage(self):
        result = audit.coverage([{"elapsed": 180.918, "requests": 8, "calls": 7,
                                  "request_input_tokens": 58179}])
        self.assertEqual(result["elapsed"], {
            "known_total": 180.918, "reported_attempts": 1, "missing_attempts": 0})
        self.assertEqual(result["requests"]["known_total"], 8)
        for key in ("input", "cached_input", "output", "cost"):
            self.assertEqual(result[key]["reported_attempts"], 0)
            self.assertEqual(result[key]["missing_attempts"], 1)

    def test_empty_selection_has_no_reported_attempts(self):
        self.assertTrue(all(value == {"known_total": 0, "reported_attempts": 0, "missing_attempts": 0}
                            for value in audit.coverage([]).values()))


if __name__ == "__main__":
    unittest.main()
