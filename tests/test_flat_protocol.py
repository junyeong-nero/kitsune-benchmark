"""#504 method pins and balanced plan; no browser, model, quota or credentials."""
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark import flat_protocol as protocol


class FlatProtocolTests(unittest.TestCase):
    def setUp(self):
        self.spec = protocol.load()

    def test_frozen_inputs_and_all_catalog_units(self):
        protocol.validate(self.spec)
        units = protocol.units(self.spec)
        self.assertEqual(len(units), 31)
        self.assertEqual(sum(u["primary"] for u in units), 29)
        self.assertEqual(len({u["id"] for u in units}), 31)
        self.assertEqual(len({u["category"] for u in units if u["primary"]}), 8)
        self.assertEqual({u["layout"] for u in units if not u["primary"]}, {"crowded", "isolated"})
        self.assertEqual(protocol.input_errors(self.spec["frozen_inputs"]), [])

    def test_each_unit_balances_positions_and_directed_carryover(self):
        jobs = protocol.plan()["schedule"]
        self.assertEqual(len(jobs), 496)
        self.assertEqual(Counter(j["arm"] for j in jobs), dict.fromkeys("ABCD", 124))
        keys = {(j["id"], j["variant"], j["repetition"], j["arm"]) for j in jobs}
        self.assertEqual(len(keys), 496)
        for unit in protocol.units(self.spec):
            rows = [j for j in jobs if j["id"] == unit["id"]]
            self.assertEqual(Counter((j["arm"], j["position"]) for j in rows),
                             Counter((arm, p) for arm in "ABCD" for p in range(4)))
            orders = [j["order"] for j in rows if j["position"] == 0]
            self.assertEqual(Counter(pair for order in orders for pair in zip(order, order[1:])),
                             Counter((a, b) for a in "ABCD" for b in "ABCD" if a != b))
        for i in range(0, len(jobs), 4):
            block = jobs[i:i+4]
            self.assertEqual(len({j["id"] for j in block}), 1)
            self.assertEqual([j["position"] for j in block], [0, 1, 2, 3])
            self.assertEqual("".join(j["arm"] for j in block), block[0]["order"])

    def test_schedule_is_deterministic_and_hashes_are_reproducible(self):
        first, second = protocol.plan(), protocol.plan(deepcopy(self.spec))
        self.assertEqual(first, second)
        self.assertEqual(first["schedule_sha256"], protocol.digest(first["schedule"]))
        self.assertEqual(first["protocol_json_sha256"], protocol.digest(self.spec))
        self.assertEqual(first["protocol_document_sha256"], hashlib.sha256(protocol.DOCUMENT.read_bytes()).hexdigest())
        self.assertAlmostEqual(first["agent_deadline_sum_hours"], 25.333333333333332)

    def test_plan_cannot_start_process_network_or_claim_approval(self):
        self.spec["execution_approved"] = True  # untrusted input is not an approval or executor
        with patch("subprocess.Popen", side_effect=AssertionError("process")), \
                patch("socket.socket", side_effect=AssertionError("network")):
            result = protocol.plan(self.spec)
        self.assertFalse(result["model_invoked"])
        self.assertFalse(result["execution_supported"])
        self.assertFalse(result["execution_approved"])
        self.assertTrue(result["pending_execution_lock"])

    def test_rejects_policy_model_coverage_and_order_drift(self):
        cases = []
        for change in (
            lambda s: s["personal_units"].pop(),
            lambda s: s["additional_units"][1].update(primary=True),
            lambda s: s["model"].update(api_billing=True),
            lambda s: s["model"].update(id="different-model"),
            lambda s: s["common_env"].update(KITSUNE_USER_TABS="writable"),
            lambda s: s["arms"]["D"]["env"].update(KITSUNE_CAPS="all"),
            lambda s: s["arms"]["B"]["env"].update(KITSUNE_PUBLISH=""),
            lambda s: s["design"].update(variant=False),
            lambda s: s["design"].update(repetitions=8),
            lambda s: s["design"].update(sequential=False),
            lambda s: s["design"].update(automatic_retries=1),
            lambda s: s["design"].update(elicitation="accept"),
            lambda s: s["design"].update(arm_orders=["ABCD", "BCDA", "CDAB", "DABC"]),
            lambda s: s["frozen_inputs"].pop("kitsune_benchmark/personal.py"),
            lambda s: s.update(pending_execution_lock=[]),
            lambda s: s.update(status="approved"),
        ):
            changed = deepcopy(self.spec)
            change(changed)
            cases.append(changed)
        for i, changed in enumerate(cases):
            with self.subTest(case=i), self.assertRaises(ValueError):
                protocol.validate(changed)

    def test_changed_missing_and_outside_inputs_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "fixture.txt").write_text("frozen")
            hashes = {"fixture.txt": hashlib.sha256(b"frozen").hexdigest()}
            self.assertEqual(protocol.input_errors(hashes, root), [])
            (root / "fixture.txt").write_text("changed")
            self.assertEqual(len(protocol.input_errors(hashes, root)), 1)
            self.assertEqual(len(protocol.input_errors({"missing.txt": "0" * 64}, root)), 1)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("outside read")):
                self.assertIn("outside repository", protocol.input_errors({"../secret": "0" * 64}, root)[0])

    def test_cli_only_prints_plan_and_has_no_execute_flag(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(protocol.main([]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["planned_model_runs"], 496)
        self.assertNotIn("schedule", result)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            protocol.main(["--execute"])
        self.assertEqual(error.exception.code, 2)
        with redirect_stderr(io.StringIO()), patch.object(protocol, "load", return_value={}):
            self.assertEqual(protocol.main([]), 2)


if __name__ == "__main__":
    unittest.main()
