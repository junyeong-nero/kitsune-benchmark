"""Offline-only tests of the exact169 suffix, immutable lineage and every-batch gate."""
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("completion_runner", ROOT / "scripts/run-agent-combinations.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
SCOPE = r.COMPLETION_SCOPE


def result(row, *args):
    return {**row, "harness": "claude_code" if row["baseline"].startswith("claude-") else "codex",
        "reported_model": row["model"], "execution_status": "completed_unscored", "scorable": True,
        "success": True, "safety_pass": True, "input": 100, "cached_input": 80, "output": 10,
        "elapsed": 20, "adjusted_elapsed": 18}


def raw_files(row, manifest, work):
    # Deliberately synthetic unit-test files; no browser, CLI or model is launched.
    for name in ("agent-result.json", "evaluation.json", "metrics.json", "session-config.json", "session-evidence.json",
                 "before-catalog.json", "after-catalog.json", "catalog-metadata.jsonl", "fake-native-rpc.jsonl",
                 "fake-native-metadata.json", "runs/unit-test/events.jsonl", "runtime/cleanup.json"):
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"unit_test_only": True, "seq": row["seq"], "session_closed": True,
                                    "owned_chrome_stopped": True, "owned_launchers_stopped": True}))
    return result(row)


def manifest(out):
    value = {"scope": SCOPE, "plan": r.treatment_plan(SCOPE), "cli_ready": True,
             "api_budget_usd": 0, "authorized_cli_starts": 169}
    (out / "manifest.json").write_text(json.dumps(value))
    return value


def approval(out, first, last):
    previous = sorted(out.glob("batch-audit-*-*.json"))
    value = {"from_seq": first, "through_seq": last, "continue": True,
        "automated_checks_passed": True, "full_argument_response_image_review": True,
        "reviewed": {key: True for key in r.BATCH_REVIEW_FIELDS},
        "prior_audit_sha256": r.digest(previous[-1]) if previous else None,
        "manifest_sha256": r.digest(out / "manifest.json"),
        "rows_prefix_sha256": hashlib.sha256(b"".join((out / "runs.jsonl").read_bytes().splitlines(keepends=True)[:last])).hexdigest(),
        "evidence_sha256": r.batch_evidence(out, first, last)}
    path = out / f"batch-audit-{first:03d}-{last:03d}.json"
    path.write_text(json.dumps(value))
    return path, value


class CompletionTests(unittest.TestCase):
    def test_exact169_original39_through207_with_unchanged_treatments(self):
        with patch("subprocess.Popen", side_effect=AssertionError("offline only")):
            plan = r.treatment_plan(SCOPE)
            original = r.scoped_plan("expanded")["attempts"]
        self.assertEqual(plan["operator_start_cap"], 169)
        self.assertEqual(plan["cumulative_start_ceiling"], 214)
        self.assertEqual([row["seq"] for row in plan["attempts"]], list(range(1, 170)))
        self.assertEqual([row["original_seq"] for row in plan["attempts"]], list(range(39, 208)))
        self.assertEqual(sum(row["baseline"].startswith("codex-") for row in plan["attempts"]), 131)
        for row, old in zip(plan["attempts"], original[38:]):
            self.assertEqual({**{k: v for k, v in row.items() if k != "original_seq"}, "seq": row["original_seq"]}, old)

    def test_settled_pending_sample_keeps_help_exception_and_failed_grade_separate(self):
        origin = "http://127.0.0.1:5000"
        seed = {"id": "seed", "url": origin + "/task", "active": True}
        help_tab = {"id": "help", "url": r.HELP_URL, "active": False}
        new = {"id": "new", "url": origin + "/detail", "active": True}
        calls = [{"tool": "browser_fill", "arguments": {"selector": "input", "text": "2"}},
                 {"tool": "browser_new_tab", "arguments": {"url": new["url"]}}]
        evidence = {"target": "browser-harness", "initial_tabs": [seed],
            "snapshots": [[seed], [seed, help_tab], [{**seed, "active": False}, help_tab, new]],
            "tab_calls": [{"tool": call["tool"], "error": False} for call in calls], "outside_navigation": 2,
            "pending_url_observations": [{"status": "settled", "samples": [{"tabs": [{**new, "url": ""}]}]}]}
        classified = r.native_help_side_effect(evidence, calls, origin)
        self.assertEqual(classified["observations"], 2)
        row = next(row for row in r.treatment_plan(SCOPE)["attempts"] if row["baseline"] == "codex-browser-harness")
        failed = {**result(row), "success": False, "safety_pass": False, "outside_navigation": 2,
                  "native_help_side_effect": classified}
        self.assertIsNone(r.stop_reason(failed, SCOPE))
        self.assertFalse(failed["success"] or failed["safety_pass"])
        evidence["snapshots"][-1][-1]["url"] = ""
        evidence["outside_navigation"] = 3
        self.assertIsNone(r.native_help_side_effect(evidence, calls, origin))
        self.assertIsNotNone(r.stop_reason({**failed, "outside_navigation": 3, "native_help_side_effect": None}, SCOPE))

    def test_invalid_batch_limits_and_caps_cannot_start_a_cell(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), patch.object(r, "run_one") as run:
            out = Path(directory)
            value = manifest(out)
            for limit in (0, 10, 207, True):
                with self.assertRaisesRegex(ValueError, "at most nine"):
                    r.do_run(out, limit)
            for cap in (None, 168, 170, 214, True):
                (out / "manifest.json").write_text(json.dumps({**value, "authorized_cli_starts": cap}))
                with self.assertRaisesRegex(ValueError, "authorization cap"):
                    r.do_run(out, 9)
            run.assert_not_called()
            self.assertFalse(list(out.glob("attempt-*")))

    def test_every_batch_requires_review_even_after_the_first_nine(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=raw_files) as run, redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            r.do_run(out, 9)
            with self.assertRaisesRegex(ValueError, "audit required"):
                r.do_run(out, 9)
            self.assertEqual(run.call_count, 9)
            approval(out, 1, 9)
            r.do_run(out, 9)
            with self.assertRaisesRegex(ValueError, "audit required"):
                r.do_run(out, 9)
            self.assertEqual(run.call_count, 18)
            approval(out, 10, 18)
            r.do_run(out, 2)
            self.assertEqual(run.call_count, 20)
            with self.assertRaisesRegex(ValueError, "audit required"):
                r.do_run(out, 1)
            approval(out, 19, 20)
            r.do_run(out, 1)
            self.assertEqual(run.call_count, 21)

    def test_cap169_cannot_grow_with_new_invocations_or_reclaim_old_starts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=result) as run, \
                patch.object(r, "batch_evidence", return_value={"synthetic-unit-test": "hash"}), \
                patch.object(r, "completion_cleanup"), redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            first = 1
            while first <= 169:
                r.do_run(out, 9)
                last = min(first + 8, 169)
                approval(out, first, last)
                first = last + 1
            self.assertEqual(run.call_count, 169)
            r.require_batch_audits(out, 169)
            r.do_run(out, 9)
            self.assertEqual(run.call_count, 169)
            self.assertEqual(len(list(out.glob("attempt-*/started.json"))), 169)
            self.assertFalse((out / "attempt-170").exists())

    def test_missing_review_fields_false_approval_or_stale_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=raw_files), redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            r.do_run(out, 1)
            path, valid = approval(out, 1, 1)
            for key in ("continue", "automated_checks_passed", "full_argument_response_image_review"):
                path.write_text(json.dumps({**valid, key: False}))
                with self.assertRaisesRegex(ValueError, "batch audit"):
                    r.require_batch_audits(out, 1)
            for field in r.BATCH_REVIEW_FIELDS:
                changed = copy.deepcopy(valid)
                del changed["reviewed"][field]
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "batch audit"):
                    r.require_batch_audits(out, 1)
            path.write_text(json.dumps(valid))
            (out / "attempt-001/work/runs/unit-test/events.jsonl").write_text("changed response")
            with self.assertRaisesRegex(ValueError, "stale"):
                r.require_batch_audits(out, 1)

    def test_approval_chain_detects_later_correction_of_an_earlier_audit(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=raw_files), redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            r.do_run(out, 1)
            first, value = approval(out, 1, 1)
            r.do_run(out, 1)
            approval(out, 2, 2)
            first.write_text(json.dumps({**value, "new_annotation": "changed after approval"}))
            with self.assertRaisesRegex(ValueError, "stale"):
                r.require_batch_audits(out, 2)

    def test_profile_archival_does_not_unbind_raw_logs_or_owned_cleanup(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=raw_files), redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            r.do_run(out, 1)
            runtime = out / "attempt-001/work/runtime"
            profile = runtime / "chrome-unit/profile"
            profile.mkdir(parents=True)
            (profile / "History").write_bytes(b"unit test synthetic profile")
            before = r.batch_evidence(out, 1, 1)
            shutil.rmtree(profile)
            (profile.parent / "profile.archive.json").write_text("unit test archive pointer")
            self.assertEqual(r.batch_evidence(out, 1, 1), before)
            (runtime / "cleanup.json").write_text(json.dumps({"owned_chrome_stopped": False}))
            with self.assertRaisesRegex(ValueError, "cleanup"):
                r.batch_evidence(out, 1, 1)
            (out / "attempt-001/work/catalog-metadata.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Incomplete raw"):
                r.batch_evidence(out, 1, 1)

    def test_cleanup_failure_stops_before_another_cell_and_retains_raw_result(self):
        def failed_cleanup(row, frozen, work):
            value = raw_files(row, frozen, work)
            (work / "runtime/cleanup.json").write_text(json.dumps({"owned_chrome_stopped": False}))
            return value
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=failed_cleanup) as run, redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            with self.assertRaisesRegex(ValueError, "cleanup"):
                r.do_run(out, 9)
            self.assertEqual(run.call_count, 1)
            self.assertTrue((out / "attempt-001/started.json").exists())
            self.assertTrue((out / "attempt-001/work/agent-result.json").exists())
            self.assertFalse((out / "attempt-002").exists())

    def test_primary_setup_failure_is_saved_before_secondary_cleanup_checks(self):
        def failed_setup(row, frozen, work):
            value = raw_files(row, frozen, work)
            (work / "session-evidence.json").write_text(json.dumps({"error": "setup failed", "session_closed": True}))
            return {**value, "execution_status": "setup_failed", "scorable": False, "success": None, "input": None}
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=failed_setup) as run, redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            self.assertEqual(r.do_run(out, 9), 2)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(r.load_rows(out)[0]["execution_status"], "setup_failed")
            self.assertEqual(json.loads((out / "stopped.json").read_text())["reason"], "execution error or unscorable attempt")
            self.assertFalse((out / "attempt-002").exists())

    def test_start_marker_tampering_is_rejected_before_another_start(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "verify"), \
                patch.object(r, "run_one", side_effect=raw_files) as run, redirect_stdout(io.StringIO()):
            out = Path(directory)
            manifest(out)
            r.do_run(out, 1)
            approval(out, 1, 1)
            (out / "attempt-001/started.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "start ledger"):
                r.do_run(out, 1)
            self.assertEqual(run.call_count, 1)

    def test_both_stopped_parents_pilots_and_observer_only_delta_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, remaining = root / "original", root / "remaining"
            original.mkdir()
            remaining.mkdir()
            with patch.object(r, "ROOT", root), patch.object(r, "PRIOR_COHORT", original), \
                    patch.object(r, "REMAINING_COHORT", remaining), patch.object(r, "batch_evidence", return_value={"raw": "hash"}):
                base = {"source_sha256": {r.OBSERVER_SOURCE: "old", "fixture": "same"},
                        "pins": {}, "catalogs": {}, "policy": r.POLICY, "limits": {"personal": 180}}
                for out, scope, count in ((original, "expanded", 6), (remaining, r.REMAINING_SCOPE, 32)):
                    plan = r.treatment_plan(scope)
                    (out / "manifest.json").write_text(json.dumps({**base, "plan": plan}))
                    (out / "runs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in plan["attempts"][:count]))
                    (out / "stopped.json").write_text(json.dumps({"seq": count, "reason": "retained stop"}))
                    for row in plan["attempts"][:count]:
                        path = out / f"attempt-{row['seq']:03d}/started.json"
                        path.parent.mkdir()
                        path.write_text(json.dumps(row))
                hashes6 = {name: r.digest(original / name) for name in r.PRIOR_FILES}
                with patch.object(r, "PRIOR_FILES", hashes6):
                    parent = json.loads((remaining / "manifest.json").read_text())
                    parent["prior_phase"] = r.prior_phase(base)
                    (remaining / "manifest.json").write_text(json.dumps(parent))
                    hashes32 = {name: r.digest(remaining / name) for name in ("manifest.json", "runs.jsonl", "stopped.json")}
                    for name, count in (("agent-combinations-pilot-v1", 1), ("agent-combinations-pilot-v2-first-nine", 6)):
                        path = root / "artifacts" / name
                        path.mkdir(parents=True)
                        for filename in ("manifest.json", "stopped.json"):
                            (path / filename).write_text("{}")
                        for seq in range(1, count + 1):
                            marker = path / f"attempt-{seq:03d}/started.json"
                            marker.parent.mkdir()
                            marker.write_text("{}")
                    new = {**base, "source_sha256": {**base["source_sha256"], r.OBSERVER_SOURCE: "new"}}
                    with patch.object(r, "REMAINING_FILES", hashes32):
                        lineage = r.completion_lineage(new)
                        self.assertEqual(lineage["prior_expanded_starts"], 38)
                        self.assertEqual(sum(p["counted_starts"] for p in lineage["pilots_separate"].values()), 7)
                        with self.assertRaisesRegex(ValueError, "observer source"):
                            r.completion_lineage({**new, "source_sha256": {**new["source_sha256"], "fixture": "changed"}})
                        with self.assertRaisesRegex(ValueError, "runtime differs"):
                            r.completion_lineage({**new, "pins": {"changed": True}})
                        marker = remaining / "attempt-032/started.json"
                        saved = marker.read_text()
                        marker.write_text("{}")
                        with self.assertRaisesRegex(ValueError, "parent ledger"):
                            r.completion_lineage(new)
                        marker.write_text(saved)
                        (original / "stopped.json").write_text("{}")
                        with self.assertRaisesRegex(ValueError, "six-start prior"):
                            r.completion_lineage(new)


if __name__ == "__main__":
    unittest.main()
