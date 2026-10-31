"""analyze-release.py on a synthetic suite directory. No model or browser."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("analyze_release", Path(__file__).resolve().parents[1] / "scripts/analyze-release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def events(path, calls):
    lines = []
    for i, (name, args, text, error) in enumerate(calls):
        lines.append({"message": {"content": [{"type": "tool_use", "id": str(i), "name": "mcp__browser__browser_" + name, "input": args}]}})
        lines.append({"message": {"content": [{"type": "tool_result", "tool_use_id": str(i), "content": text, "is_error": error}]}})
    path.mkdir(parents=True, exist_ok=True)
    (path / "events.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines))
    return str(path)


def run(folder, name, success, tokens, calls, graded=True, **extra):
    ev = {"scorable": True, "task_success": success if graded else None, **({} if graded else {"graded": False})}
    return {"run_dir": events(Path(folder) / name, calls), "usage": {"input_tokens": tokens, "output_tokens": tokens // 100},
            "mcp_calls": len(calls), "elapsed_sec": 10, "execution_status": "completed_unscored", "model": "m",
            "benchmark_evaluation": ev, **extra}


class ReleaseReviewTests(unittest.TestCase):
    def suite(self, folder):
        click = ("click", {"target": "e1"}, '{"ok":true}', False)
        snap = ("snapshot", {}, '{"snapshot":"x"}', False)
        wait = ("wait_for", {"time": 1}, '{"ok":true}', False)
        error = ("fill_form", {}, '{"error":"stale ref","code":"stale_ref"}', True)
        summaries = {
            "personal-v0": [{"personal_task": "pb-a", "results": {
                "playwright": run(folder, "pa-p", True, 1000, [snap, click]),
                "kitsune": run(folder, "pa-k", True, 1500, [click, snap, wait, error])}},
                {"personal_task": "pb-b", "results": {
                "playwright": run(folder, "pb-p", True, 1000, [snap]),
                "kitsune": run(folder, "pb-k", False, 500, [snap])}}],
            "external": [{"external_task": "live-x", "results": {
                "playwright": run(folder, "lx-p", None, 100, [snap], graded=False),
                "kitsune": run(folder, "lx-k", None, 80, [snap], graded=False)}}],
            "coexistence-protect": [{"coexistence_task": "pb-a", "pair_dir": str(Path(folder) / "cp"), "results": {
                "kitsune": run(folder, "cp-k", True, 900, [snap])}}],
        }
        # A write held on the user's tab, declined, then done in a new tab on the same page (#58).
        user = [{"id": 0, "active": True, "url": "http://l/t/memo"}]
        own = user + [{"id": 1, "active": False, "url": "http://l/t/memo"}]
        (Path(folder) / "cp").mkdir()
        (Path(folder) / "cp/kitsune-session-evidence.json").write_text(json.dumps({
            "tab_calls": [{"tool": "browser_type", "error": True}, {"tool": "browser_tabs", "action": "new", "error": False},
                          {"tool": "browser_type", "error": False}],
            "snapshots": [user, user, [{**own[0], "active": False}, {**own[1], "active": True}], own],
            "elicitations": [{"tool": "browser_type", "reason": "approval", "detail": "user_viewing", "action": "decline",
                              "decision": "declined"}],
            "held_refusals": [{"call": 0, "tool": "browser_type", "code": "needs_user", "detail": "user_viewing",
                               "decision": "declined"}]}))
        log = []
        for name, pairs in summaries.items():
            path = Path(folder) / f"{name}.json"
            path.write_text(json.dumps({"pairs": pairs}))
            log.append({"name": name, "suite_summary_path": str(path)})
        (Path(folder) / "suite-log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log))
        return folder

    def test_outcomes_ratios_outliers_and_behaviour(self):
        with tempfile.TemporaryDirectory() as folder:
            report = release.review(self.suite(folder), threshold=1.10)
            self.assertEqual(report["audit"]["runs"], 7)
            personal = report["outcomes"]["personal"]
            self.assertEqual((personal["playwright"], personal["kitsune"]), (2, 1))
            self.assertEqual(report["outcomes"]["external"]["kitsune"], 1, "an ungraded completed run counts")
            self.assertIsNone(report["outcomes"]["coexistence-protect"]["playwright"])
            self.assertEqual(report["ratios"]["personal"]["joint"], 1)
            self.assertEqual(report["ratios"]["personal"]["input"], 1.5)
            self.assertNotIn("coexistence-protect", report["ratios"])
            self.assertEqual([o["task"] for o in report["outliers"]], ["pb-a"])
            k = report["behaviour"]["kitsune"]
            self.assertEqual((k["blind_waits"], k["actions"], k["actions_followed_by_observation"]), (1, 2, 1))
            self.assertIn("fill_form: ", next(iter(k["tool_errors"])))
            text = release.markdown(report, 1.10)
            self.assertIn("| coexistence-protect | 1 | — | 1 |", text)
            held = report["holds"]["coexistence-protect"]
            self.assertEqual((held["runs"], held["runs_with_declined_hold"], held["runs_redo_after_decline"]), (1, 1, 1))
            self.assertEqual(report["holds"]["personal-v0"]["runs"], 0, "no session evidence, no hold record")
            self.assertIn("| coexistence-protect | 1 | 1 | 1 | 1 / 0 / 0 | 0 / 1 / 0 / 0 | 1 | 1 |", text)
            self.assertNotIn("| personal-v0 | 0 |", text)
            (Path(folder) / "cp/kitsune-session-evidence.json").write_text('{"tab_calls": [')
            self.assertEqual(release.review(folder)["holds"]["coexistence-protect"]["runs"], 0, "truncated evidence")
            compared = release.review(folder, compare=folder)
            self.assertEqual(compared["compare"]["shared_units"], 4)

    def test_compare_warns_when_elicitation_policies_differ_or_are_not_recorded(self):
        # #59: a suite's policy comes from its suite-manifest.json; suites before #59 recorded none.
        with tempfile.TemporaryDirectory() as now, tempfile.TemporaryDirectory() as then:
            self.suite(now)
            self.suite(then)
            for policy_now, policy_then, warned in (("decline", "decline", None), ("accept", "accept", None),
                                                    ("accept", "decline", "different policies"),
                                                    ("decline", None, "none recorded then"),
                                                    (None, "accept", "none recorded now"),
                                                    (None, None, "none recorded now")):
                with self.subTest(now=policy_now, then=policy_then):
                    for folder, policy in ((now, policy_now), (then, policy_then)):
                        manifest = Path(folder) / "suite-manifest.json"
                        manifest.write_text(json.dumps({"plan": "lite", **({"elicitation": policy} if policy else {})}))
                    report = release.review(now, compare=then)
                    self.assertEqual((report["elicitation"], report["compare"]["elicitation"]), (policy_now, policy_then))
                    text = release.markdown(report, 1.10)
                    self.assertIn(f"- Elicitation policy: {policy_now or 'none recorded'}", text)
                    self.assertIn(f"Elicitation policy: {policy_now or 'none recorded'} now, "
                                  f"{policy_then or 'none recorded'} then.", text)
                    if warned is None:
                        self.assertIsNone(report["compare"]["warning"])
                        self.assertNotIn("Warning", text)
                    else:
                        self.assertIn(warned, report["compare"]["warning"])
                        self.assertIn("> **Warning:** elicitation policy", text)

    def test_policy_without_suite_manifest_falls_back_to_pair_records(self):
        # Suites before #59 have no policy in suite-manifest.json, or no manifest at all; #55's relay still wrote
        # elicitation_policy into each run's session evidence.
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(release.elicitation_policy(empty), (None, None), "no manifest, no suite log")
        with tempfile.TemporaryDirectory() as folder:
            self.suite(folder)
            self.assertFalse((Path(folder) / "suite-manifest.json").exists())
            report = release.review(folder)
            self.assertEqual((report["elicitation"], report["elicitation_source"]), (None, None))
            self.assertIn("- Elicitation policy: none recorded", release.markdown(report, 1.10))
            summary = Path(folder) / "personal-v0.json"
            pairs = json.loads(summary.read_text())["pairs"]
            for i, pair in enumerate(pairs):
                pair["pair_dir"] = str(Path(folder) / f"pair-{i}")
                Path(pair["pair_dir"]).mkdir()
            (Path(pairs[0]["pair_dir"]) / "kitsune-session-evidence.json").write_text(
                json.dumps({"elicitation_policy": "decline"}))
            (Path(pairs[1]["pair_dir"]) / "pair-manifest.json").write_text(json.dumps({"experiment": {}}))
            (Path(pairs[1]["pair_dir"]) / "playwright-session-evidence.json").write_text("not json")
            (Path(pairs[1]["pair_dir"]) / "kitsune-session-evidence.json").write_text(
                json.dumps({"elicitation_policy": "decline"}))
            summary.write_text(json.dumps({"pairs": pairs}))
            report = release.review(folder)
            self.assertEqual((report["elicitation"], report["elicitation_source"]), ("decline", "pair records"))
            self.assertIn("- Elicitation policy: decline (from pair records)", release.markdown(report, 1.10))
            # A pair manifest's experiment, then a pair summary's own field, come before session evidence.
            (Path(pairs[1]["pair_dir"]) / "pair-manifest.json").write_text(
                json.dumps({"experiment": {"elicitation": "accept"}}))
            self.assertEqual(release.elicitation_policy(folder), ("mixed", "pair records"))
            pairs[0]["elicitation"] = "accept"
            summary.write_text(json.dumps({"pairs": pairs}))
            self.assertEqual(release.elicitation_policy(folder), ("accept", "pair records"))
            # The manifest's policy wins, and mixed pair records always warn.
            (Path(folder) / "suite-manifest.json").write_text(json.dumps({"elicitation": "decline"}))
            self.assertEqual(release.elicitation_policy(folder), ("decline", "suite-manifest"))
            self.assertIn("different policies", release.policy_warning("mixed", "mixed"))


if __name__ == "__main__":
    unittest.main()
