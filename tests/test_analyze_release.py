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

    def test_signals_and_hold_split(self):
        # #71: tab, snapshot, wait_for and first-request signals per group, and K/PW input split by Kitsune holds.
        with tempfile.TemporaryDirectory() as folder:
            def tabs(action):
                return ("tabs", {"action": action}, '{"ok":true}', False)
            listing, select, new = tabs("list"), tabs("select"), tabs("new")
            click = ("click", {"target": "e1"}, '{"ok":true}', False)
            held = ("click", {"target": "e1"}, '{"error":"The user is viewing tab 0","code":"needs_user"}', True)
            navigated = ("click", {"target": "e2"}, '{"ok":true,"navigated":{"url":"http://l/memo"},"snapshot":"x"}', False)
            navigate = ("navigate", {"url": "http://l/a"}, '{"ok":true}', False)
            failed_navigate = ("navigate", {"url": "http://l/b"}, '{"error":"timeout"}', True)
            snap = ("snapshot", {}, '{"snapshot":"- text \\"a\\""}', False)
            unchanged = ("snapshot", {}, '{"snapshot":"unchanged","unchanged_since":"browser_click"}', False)
            targeted = ("snapshot", {"target": "e3"}, '{"snapshot":"y"}', False)
            fast = ("wait_for", {"text": "code"}, '{"ok":true,"text":"code","elapsed":6}', False)
            slow = ("wait_for", {"text": "done"}, '{"ok":true,"text":"done","elapsed":800}', False)
            gone = ("wait_for", {"textGone": "busy"}, '{"ok":true,"text_gone":"busy","elapsed":25}', False)
            delta = ("wait_for", {"time": 2}, '{"ok":true,"slept":2.0,"snapshot":"z","snapshot_delta":true}', False)
            pw_wait = ("wait_for", {"text": "code"}, "### Result\nWaited for code", False)

            def first(tokens):
                return {"token_attribution": {"first_request_input_tokens": tokens}}

            def pair_dir(name, evidence):
                path = Path(folder) / name
                path.mkdir()
                (path / "kitsune-session-evidence.json").write_text(json.dumps(evidence))
                return str(path)

            no_hold = {"snapshots": [], "elicitations": [], "held_refusals": []}
            one_hold = {"snapshots": [], "elicitations": [{"reason": "approval", "detail": "user_viewing",
                                                           "action": "decline", "decision": "declined"}],
                        "held_refusals": []}
            summaries = {
                "personal-v0": [
                    {"personal_task": "pb-held", "pair_dir": pair_dir("h", one_hold), "results": {
                        "playwright": run(folder, "h-p", True, 1000, [listing, select, click], **first(900)),
                        "kitsune": run(folder, "h-k", True, 3000, [listing, select, held, new, click], **first(1000))}},
                    {"personal_task": "pb-own", "pair_dir": pair_dir("o", no_hold), "results": {
                        "playwright": run(folder, "o-p", True, 1000, [listing, navigate, snap], **first(910)),
                        "kitsune": run(folder, "o-k", True, 500, [listing, new, navigate, unchanged, navigated, snap,
                                                                   navigated, targeted, failed_navigate, snap], **first(1020))}},
                    {"personal_task": "pb-unrecorded", "results": {
                        "playwright": run(folder, "u-p", True, 1000, [listing, new], **first(920)),
                        "kitsune": run(folder, "u-k", True, 1000, [new, listing, click], **first(1040))}}],
                "gallery-isolated-v0": [{"gallery_task": "ui-toast", "results": {
                    "playwright": run(folder, "g-p", True, 1000, [click, pw_wait], **first(800)),
                    "kitsune": run(folder, "g-k", True, 2000, [click, fast, slow, gone, delta], **first(1100))}}],
            }
            log = []
            for name, pairs in summaries.items():
                path = Path(folder) / f"{name}.json"
                path.write_text(json.dumps({"pairs": pairs}))
                log.append({"name": name, "suite_summary_path": str(path)})
            (Path(folder) / "suite-log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log))

            report = release.review(folder)
            personal = report["signals"]["personal"]
            k, pw = personal["kitsune"], personal["playwright"]
            self.assertEqual((k["runs"], k["runs_second_call_tabs_select"], pw["runs_second_call_tabs_select"]), (3, 1, 1))
            # pb-own and pb-unrecorded open a tab before their first write; Playwright's pb-unrecorded writes nothing.
            self.assertEqual((k["runs_own_tab_before_first_write"], pw["runs_own_tab_before_first_write"]), (2, 0))
            # After navigate and after a navigated click; not a targeted snapshot, nor one after a failed navigate.
            self.assertEqual((k["snapshots_after_navigation"], k["unchanged_since"]), (2, 1))
            self.assertEqual(k["snapshot_after_navigation_chars"], len(unchanged[2]) + len(snap[2]))
            self.assertEqual((pw["snapshots_after_navigation"], pw["unchanged_since"]), (1, 0))
            self.assertEqual((k["median_first_request_input_tokens"], pw["median_first_request_input_tokens"]), (1020, 910))
            gallery = report["signals"]["gallery-isolated"]
            k, pw = gallery["kitsune"], gallery["playwright"]
            self.assertEqual((k["wait_for_text"], k["wait_for_text_under_50ms"]), (2, 1), "textGone is not a text wait")
            self.assertEqual((k["wait_for_with_delta"], k["wait_for_without_delta"]), (1, 3))
            self.assertEqual((pw["wait_for_text"], pw["wait_for_text_under_50ms"], pw["wait_for_without_delta"]), (1, 0, 1))

            split = report["hold_split"]
            self.assertEqual(split["personal"], {"with_hold": {"units": 1, "input": 3.0},
                                                 "without_hold": {"units": 1, "input": 0.5}, "no_record": 1})
            self.assertNotIn("gallery-isolated", split, "no hold record in the group")
            text = release.markdown(report, 1.10)
            self.assertIn("| personal | 3 / 3 | 1 / 1 | 0 / 2 | 910 / 1020 | 2 | "
                          f"{len(unchanged[2]) + len(snap[2])} | 1 | 0 / 0 | 0 / 0 |", text)
            self.assertIn("| gallery-isolated | 1 / 1 | 0 / 0 | 0 / 0 | 800 / 1100 | 0 | 0 | 0 | 1 / 2 | 1 / 3 |", text)
            self.assertIn("| personal | 1 | 3.0 | 1 | 0.5 |", text)
            self.assertIn("1 joint successes have no readable Kitsune session evidence", text)

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
