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
    """A Claude Code stream of (tool, arguments, result, is_error[, request]) calls; calls with the same request share
    an assistant message id, and a call without one is sent in a message without an id."""
    lines = []
    for i, (name, args, text, error, *request) in enumerate(calls):
        lines.append({"message": {**({"id": request[0]} if request else {}), "content": [
            {"type": "tool_use", "id": str(i), "name": "mcp__browser__browser_" + name, "input": args}]}})
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
            self.assertEqual((k["blind_waits"], k["actions"], k["actions_followed_by_observation_next_request"],
                              k["actions_followed_by_observation_same_request"]), (1, 2, 1, 0))
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
            # Calls in messages without an id are each their own request.
            self.assertEqual((k["snapshots_after_navigation_next_request"], k["snapshots_after_navigation_same_request"],
                              k["unchanged_since"]), (2, 0, 1))
            self.assertEqual(k["snapshot_after_navigation_chars"], len(unchanged[2]) + len(snap[2]))
            self.assertEqual((pw["snapshots_after_navigation_next_request"], pw["unchanged_since"]), (1, 0))
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
            self.assertIn("| personal | 3 / 3 | 1 / 1 | 0 / 2 | 910 / 1020 | 0 / 0 | 1 / 2 | "
                          f"{len(unchanged[2]) + len(snap[2])} | 1 | 0 / 0 | 0 / 0 |", text)
            self.assertIn("| gallery-isolated | 1 / 1 | 0 / 0 | 0 / 0 | 800 / 1100 | 0 / 0 | 0 / 0 | 0 | 0 | 1 / 2 | 1 / 3 |",
                          text)
            self.assertIn("| personal | 1 | 3.0 | 1 | 0.5 |", text)
            self.assertIn("1 joint successes have no readable Kitsune session evidence", text)

    def test_signals_split_by_model_request(self):
        # #124: a call sent in the same model request (assistant message id) as the call before it had not seen its
        # result; `tabs new` with a URL navigates.
        with tempfile.TemporaryDirectory() as folder:
            unchanged = '{"snapshot":"unchanged","unchanged_since":"browser_tabs"}'
            after_click = '{"snapshot":"x"}'
            kitsune = [("tabs", {"action": "new", "url": "http://l/a"}, '{"ok":true}', False, "k1"),
                       ("snapshot", {}, unchanged, False, "k1"),
                       ("click", {"target": "e2"}, '{"ok":true,"navigated":{"url":"http://l/b"}}', False, "k2"),
                       ("snapshot", {}, after_click, False, "k3"),
                       ("click", {"target": "e3"}, '{"ok":true}', False, "k4"),
                       ("find", {"text": "code"}, '{"matches":[]}', False, "k4"),
                       ("click", {"target": "e4"}, '{"ok":true}', False, "k5"),
                       ("snapshot", {"target": "e5"}, '{"snapshot":"y"}', False, "k6"),
                       ("tabs", {"action": "new"}, '{"ok":true}', False, "k7"),
                       ("snapshot", {}, '{"snapshot":"about:blank"}', False, "k7")]
            playwright = [("navigate", {"url": "http://l/a"}, "### Ran Playwright code", False, "p1"),
                          ("snapshot", {}, "### Page state", False, "p1"),
                          ("click", {"target": "e2"}, "### Ran Playwright code", False, "p2"),
                          ("snapshot", {}, "### Page state", False, "p3")]
            summary = Path(folder) / "personal-v0.json"
            summary.write_text(json.dumps({"pairs": [{"personal_task": "pb-a", "results": {
                "playwright": run(folder, "a-p", True, 1000, playwright),
                "kitsune": run(folder, "a-k", True, 1000, kitsune)}}]}))
            (Path(folder) / "suite-log.jsonl").write_text(json.dumps({"name": "personal-v0",
                                                                      "suite_summary_path": str(summary)}) + "\n")

            report = release.review(folder)
            k, pw = report["signals"]["personal"]["kitsune"], report["signals"]["personal"]["playwright"]
            # After `tabs new url` in its request and after a navigated click in the next; not after `tabs new` alone.
            self.assertEqual((k["snapshots_after_navigation_same_request"], k["snapshots_after_navigation_next_request"],
                              k["unchanged_since"]), (1, 1, 1))
            # Playwright's click result does not say it navigated.
            self.assertEqual((pw["snapshots_after_navigation_same_request"],
                              pw["snapshots_after_navigation_next_request"]), (1, 0))
            k, pw = report["behaviour"]["kitsune"], report["behaviour"]["playwright"]
            self.assertEqual((k["actions"], k["actions_followed_by_observation_same_request"],
                              k["actions_followed_by_observation_next_request"]), (3, 1, 2))
            self.assertEqual((k["observation_after_action_same_request_rate"],
                              k["observation_after_action_next_request_rate"]), (0.333, 0.667))
            self.assertEqual((pw["actions_followed_by_observation_same_request"],
                              pw["actions_followed_by_observation_next_request"]), (0, 1))
            text = release.markdown(report, 1.10)
            self.assertIn("Reviews before #124 counted both together", text.split("## Audit")[0])
            self.assertIn("| Observation right after an action, same request | 0.0 | 0.333 |", text)
            self.assertIn("| Observation right after an action, next request | 1.0 | 0.667 |", text)
            self.assertIn("| personal | 1 / 1 | 0 / 0 | 0 / 1 | None / None | 1 / 1 | 0 / 1 | "
                          f"{len(unchanged) + len(after_click)} | 1 | 0 / 0 | 0 / 0 |", text)

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

    def test_compare_says_no_holds_then_for_a_suite_without_a_policy_before_kitsune_364(self):
        # #73: kitsune#364 (v0.7.1-10-g561719a) added Kitsune's holds; a suite on an earlier Kitsune had no prompt to answer.
        with tempfile.TemporaryDirectory() as now, tempfile.TemporaryDirectory() as then:
            self.suite(now)
            self.suite(then)
            for describe, no_holds in (("v0.7.1", True), ("v0.7.1-9-g5f3deb8", True), ("v0.3.0-4-gd616c50", True),
                                       ("v0.7.1-10-g561719a", False), ("v0.7.1-21-gdea1ad4", False),
                                       ("v0.7.1-dirty", False), (None, False)):
                with self.subTest(describe=describe):
                    (Path(now) / "suite-manifest.json").write_text(json.dumps({"elicitation": "decline"}))
                    (Path(then) / "suite-manifest.json").write_text(json.dumps({"kitsune": {"describe": describe}}))
                    self.assertEqual(release.before_holds(then), no_holds)
                    report = release.review(now, compare=then)
                    self.assertEqual(report["compare"]["no_holds"], no_holds)
                    text = release.markdown(report, 1.10)
                    if no_holds:
                        self.assertIsNone(report["compare"]["warning"])
                        self.assertIn("Elicitation policy: decline now, no holds then (Kitsune < #364).", text)
                        self.assertNotIn("Warning", text)
                    else:
                        self.assertIn("not comparable", report["compare"]["warning"])
                        self.assertIn("Elicitation policy: decline now, none recorded then.", text)
            # A recorded policy then, or none now, keeps the policy label and the warning.
            (Path(then) / "suite-manifest.json").write_text(json.dumps({"kitsune": {"describe": "v0.7.1"},
                                                                        "elicitation": "accept"}))
            report = release.review(now, compare=then)
            self.assertFalse(report["compare"]["no_holds"])
            self.assertIn("different policies", report["compare"]["warning"])
            (Path(then) / "suite-manifest.json").write_text(json.dumps({"kitsune": {"describe": "v0.7.1"}}))
            (Path(now) / "suite-manifest.json").unlink()
            report = release.review(now, compare=then)
            self.assertIn("none recorded now", report["compare"]["warning"])
            self.assertIn("Elicitation policy: none recorded now, no holds then (Kitsune < #364).",
                          release.markdown(report, 1.10))
        with tempfile.TemporaryDirectory() as empty:
            self.assertFalse(release.before_holds(empty), "no manifest")

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

    def test_read_only_refusals_copies_and_their_split(self):
        # #101: Kitsune with read-only user tabs refuses `select` (user_tab_read_only) and the agent copies the user's tab.
        with tempfile.TemporaryDirectory() as folder:
            memo, article = "http://l/t/memo", "http://l/t/article"
            listing = ("tabs", {"action": "list"}, '{"tabs":[]}', False)
            refused = ("tabs", {"action": "select", "index": 1},
                       '{"error":"Tab 2 is read-only for this client","code":"user_tab_read_only"}', True)
            refused_type = ("type", {"target": "e3", "text": "x"}, '{"error":"read-only","code":"user_tab_read_only"}', True)
            copy = ("tabs", {"action": "new", "url": memo}, '{"ok":true}', False)
            other_tab = ("tabs", {"action": "new", "url": "http://l/t/source"}, '{"ok":true}', False)
            click = ("click", {"target": "e1"}, '{"ok":true}', False)

            def pair_dir(name, seeding):
                path = Path(folder) / name
                path.mkdir()
                (path / "kitsune-session-evidence.json").write_text(json.dumps(
                    {"seeding": seeding, "initial_tabs": [{"id": 0, "active": True, "url": article},
                                                         {"id": 1, "active": False, "url": memo}]}))
                return str(path)

            summaries = {
                "personal-v0": [
                    {"personal_task": "pb-copy", "pair_dir": pair_dir("c", "user_channel"), "results": {
                        "playwright": run(folder, "c-p", True, 1000, [listing, click]),
                        "kitsune": run(folder, "c-k", True, 1500, [listing, refused, refused_type, copy, click])}},
                    {"personal_task": "pb-plain", "pair_dir": pair_dir("p", "user_channel"), "results": {
                        "playwright": run(folder, "p-p", True, 1000, [listing, click]),
                        "kitsune": run(folder, "p-k", True, 800, [listing, other_tab, click])}}],
                "gallery-isolated-v0": [{"gallery_task": "ui-x", "pair_dir": pair_dir("g", None), "results": {
                    "playwright": run(folder, "g-p", True, 1000, [click]),
                    "kitsune": run(folder, "g-k", True, 900, [copy, click])}}],
            }
            log = []
            for name, pairs in summaries.items():
                path = Path(folder) / f"{name}.json"
                path.write_text(json.dumps({"pairs": pairs}))
                log.append({"name": name, "suite_summary_path": str(path)})
            (Path(folder) / "suite-log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log))

            report = release.review(folder)
            personal = report["read_only"]["personal-v0"]
            self.assertEqual(personal, {"runs": 2, "runs_with_refusal": 1, "refusals": 2,
                                        "refused_calls": {"tabs select": 1, "type": 1}, "user_seeded_runs": 2,
                                        "runs_with_copy_to_write": 1, "copies_to_write": 1,
                                        "runs_with_copy_to_read": 0, "copies_to_read": 0})
            # Gallery's starting tabs are the harness's, not the user's: a tab at their URL is not a copy.
            gallery = report["read_only"]["gallery-isolated-v0"]
            self.assertEqual((gallery["user_seeded_runs"], gallery["copies_to_write"], gallery["copies_to_read"]),
                             (0, 0, 0))
            self.assertEqual(report["read_only_split"], {"personal": {"with_refusal_or_copy_to_read": {"units": 1, "input": 1.5},
                                                                    "without": {"units": 1, "input": 0.8}}})
            text = release.markdown(report, 1.10)
            self.assertIn("| personal-v0 | 2 | 1 | 2 | 1× tabs select, 1× type | 2 | 1 | 1 | 0 | 0 |", text)
            self.assertIn("| personal | 1 | 1.5 | 1 | 0.8 |", text)
            compared = release.review(folder, compare=folder)
            self.assertEqual(compared["compare"]["read_only_now"]["personal"]["runs_with_copy_to_write"], 1)
            self.assertIn("| personal | 1/2 | 1/2 | 1/2 | 1/2 | 0/2 | 0/2 |", release.markdown(compared, 1.10))
            self.assertIn("| gallery-isolated | 0/1 | 0/1 | — | — | — | — |", release.markdown(compared, 1.10))

    def test_copies_to_write_and_copies_to_read(self):
        # #113: a copy is a copy to write when the agent writes in it before its next `tabs new` or `tabs select`.
        with tempfile.TemporaryDirectory() as folder:
            memo, article = "http://l/t/memo", "http://l/t/article"
            copy = ("tabs", {"action": "new", "url": memo}, '{"ok":true}', False)
            other_tab = ("tabs", {"action": "new", "url": "http://l/t/source"}, '{"ok":true}', False)
            select = ("tabs", {"action": "select", "index": 0}, '{"ok":true}', False)
            snap = ("snapshot", {}, '{"snapshot":"x"}', False)
            find = ("find", {"text": "code"}, '{"matches":[]}', False)
            fill = ("fill_form", {"fields": []}, '{"ok":true}', False)
            click = ("click", {"target": "e1"}, '{"ok":true}', False)
            evidence = {"seeding": "user_channel", "initial_tabs": [{"id": 0, "active": True, "url": article},
                                                                   {"id": 1, "active": False, "url": memo}]}
            cases = {
                "pb-write": [copy, snap, fill, click],
                "pb-read": [copy, snap, find],
                "pb-select": [copy, snap, select, click],
                "pb-new": [copy, snap, other_tab, click],
            }
            pairs = []
            for task, calls in cases.items():
                path = Path(folder) / task
                path.mkdir()
                (path / "kitsune-session-evidence.json").write_text(json.dumps(evidence))
                pairs.append({"personal_task": task, "pair_dir": str(path), "results": {
                    "playwright": run(folder, task + "-p", True, 1000, [snap, click]),
                    "kitsune": run(folder, task + "-k", True, 2000 if task == "pb-write" else 1500, calls)}})
            summary = Path(folder) / "personal-v0.json"
            summary.write_text(json.dumps({"pairs": pairs}))
            (Path(folder) / "suite-log.jsonl").write_text(json.dumps({"name": "personal-v0",
                                                                      "suite_summary_path": str(summary)}) + "\n")

            units = release.load(folder)
            rows = {task: release.run_read_only(units[("personal-v0", task)]["kitsune"]) for task in cases}
            self.assertEqual({task: (row["copies_to_write"], row["copies_to_read"]) for task, row in rows.items()},
                             {"pb-write": (1, 0), "pb-read": (0, 1), "pb-select": (0, 1), "pb-new": (0, 1)})
            report = release.review(folder)
            personal = report["read_only"]["personal-v0"]
            self.assertEqual((personal["runs_with_copy_to_write"], personal["copies_to_write"],
                              personal["runs_with_copy_to_read"], personal["copies_to_read"]), (1, 1, 3, 3))
            # Only copies to read put a unit on the "refusal or copy to read" side.
            self.assertEqual(report["read_only_split"]["personal"],
                             {"with_refusal_or_copy_to_read": {"units": 3, "input": 1.5},
                              "without": {"units": 1, "input": 2.0}})
            text = release.markdown(report, 1.10)
            self.assertIn("| personal-v0 | 4 | 0 | 0 | none | 4 | 1 | 1 | 3 | 3 |", text)
            self.assertIn("## Kitsune / Playwright input on joint successes, by refusal or copy to read", text)
            self.assertIn("| personal | 3 | 1.5 | 1 | 2.0 |", text)
            compared = release.markdown(release.review(folder, compare=folder), 1.10)
            self.assertIn("| personal | 0/4 | 0/4 | 1/4 | 1/4 | 3/4 | 3/4 |", compared)

    def test_kitsune_arm_against_default_kitsune(self):
        # coexistence-local-v2: the unprotected arm (user tabs writable) beside default Kitsune on the same user-seeded units.
        with tempfile.TemporaryDirectory() as folder:
            refused = ("tabs", {"action": "select", "index": 1}, '{"error":"read-only","code":"user_tab_read_only"}', True)
            click = ("click", {"target": "e1"}, '{"ok":true}', False)

            def coexistence_run(name, success, tokens, calls, moved=0):
                result = run(folder, name, success, tokens, calls)
                result["benchmark_evaluation"].update(contracts={"v3_user_view": {"task_success": success and not moved}},
                                                      user_view={"view_left_initial_after_calls": moved})
                return result
            summaries = {
                "coexistence-user-seeded": [
                    {"coexistence_task": "pb-a", "results": {"playwright": coexistence_run("a-p", True, 1000, [click], 2),
                                                            "kitsune": coexistence_run("a-k", True, 1200, [refused, click])}},
                    {"coexistence_task": "pb-b", "results": {"playwright": coexistence_run("b-p", True, 1000, [click]),
                                                            "kitsune": coexistence_run("b-k", False, 900, [click])}}],
                "coexistence-unprotected": [
                    {"coexistence_task": "pb-a", "results": {"kitsune": coexistence_run("a-u", True, 600, [click], 1)}},
                    {"coexistence_task": "pb-b", "results": {"kitsune": coexistence_run("b-u", True, 800, [click])}}],
            }
            log = []
            for name, pairs in summaries.items():
                path = Path(folder) / f"{name}.json"
                path.write_text(json.dumps({"pairs": pairs}))
                log.append({"name": name, "suite_summary_path": str(path)})
            (Path(folder) / "suite-log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log))

            report = release.review(folder)
            self.assertNotIn("coexistence-unprotected", report["ratios"], "a Kitsune-only arm has no Playwright ratio")
            arm = report["kitsune_arms"]["coexistence-unprotected"]
            self.assertEqual((arm["units"], arm["joint"], arm["input"], arm["mcp_calls"]), (2, 1, 0.5, 0.5))
            self.assertEqual(arm["default"], {"successes": 1, "v3_user_view": 1, "runs_moved_view": 0,
                                              "runs_with_refusal": 1, "runs_with_copy_to_write": 0,
                                              "runs_with_copy_to_read": 0})
            self.assertEqual(arm["arm"], {"successes": 2, "v3_user_view": 1, "runs_moved_view": 1,
                                          "runs_with_refusal": 0, "runs_with_copy_to_write": 0,
                                          "runs_with_copy_to_read": 0})
            text = release.markdown(report, 1.10)
            self.assertIn("## Default Kitsune vs `coexistence-unprotected` on 2 user-seeded units", text)
            self.assertIn("| Runs that moved the user's view | 0 | 1 |", text)
            self.assertIn("the arm's input is 0.5× and its agent calls 0.5× default Kitsune's.", text)

    def test_cost_beyond_tokens_on_joint_successes(self):
        # #108: cold-start and warm-ready phases, task resources and input excluding cache reads per group and target.
        with tempfile.TemporaryDirectory() as folder:
            mib = 1024 * 1024
            snap = ("snapshot", {}, '{"snapshot":"x"}', False)

            def bucket(duration, cpu, peak, mean):
                return {"duration_sec": duration, "observed_cpu_user_sec": cpu / 2, "observed_cpu_system_sec": cpu / 2,
                        "sampled_peak_rss_bytes": peak * mib, "time_weighted_mean_rss_bytes": mean * mib}

            def target_run(name, success, usage, task):
                result = run(folder, name, success, usage["input_tokens"], [snap], resources={"task": task})
                result["usage"] = usage
                return result
            # Claude: input includes cache reads (cached_input_tokens) and writes; Codex reports total and cached only.
            claude = {"input_tokens": 1000, "cached_input_tokens": 800, "cache_creation_input_tokens": 150,
                      "uncached_input_tokens": 50, "output_tokens": 10}
            codex = {"input_tokens": 1000, "cached_input_tokens": 600, "output_tokens": 10}
            # A pair from before inline phases: its setup and ready phases are read from its resource-summary.json.
            old_summary = Path(folder) / "old-resource-summary.json"
            old_summary.write_text(json.dumps({"metrics": {"phase/setup/owner/kitsune": bucket(2, 1, 6, 2),
                                                           "phase/ready/owner/kitsune": bucket(1, 0.5, 4, 3)}}))
            playwright_lifecycle = {"timing": {"kitsune_cold_start_setup_sec": None},
                                    "resource_phases": {"playwright": {"setup": None, "ready": None}}}
            pairs = [
                {"personal_task": "pb-a", **playwright_lifecycle,
                 "results": {"playwright": target_run("a-p", True, codex, bucket(10, 8, 900, 600))}},
                {"personal_task": "pb-a", "timing": {"kitsune_cold_start_setup_sec": 4},
                 "resource_phases": {"kitsune": {"setup": bucket(4, 3, 5, 2), "ready": bucket(1, 0.5, 3, 3)}},
                 "results": {"kitsune": target_run("a-k", True, claude, bucket(10, 4, 1000, 700))}},
                {"personal_task": "pb-b", **playwright_lifecycle,
                 "results": {"playwright": target_run("b-p", True, codex, bucket(30, 6, 800, 900))}},
                {"personal_task": "pb-b", "resource_summary_path": str(old_summary),
                 "results": {"kitsune": target_run("b-k", True, claude, bucket(30, 2, 1200, 1100))}},
                {"personal_task": "pb-c", **playwright_lifecycle,
                 "results": {"playwright": target_run("c-p", True, codex, bucket(10, 99, 9000, 9000))}},
                {"personal_task": "pb-c", "timing": {"kitsune_cold_start_setup_sec": 99},
                 "resource_phases": {"kitsune": {"setup": bucket(99, 99, 9000, 9000), "ready": None}},
                 "results": {"kitsune": target_run("c-k", False, claude, bucket(10, 99, 9000, 9000))}}]
            path = Path(folder) / "personal-v0.json"
            path.write_text(json.dumps({"pairs": pairs}))
            (Path(folder) / "suite-log.jsonl").write_text(json.dumps({"name": "personal-v0", "suite_summary_path": str(path)}) + "\n")

            report = release.review(folder)
            kitsune, playwright = report["costs"]["personal"]["kitsune"], report["costs"]["personal"]["playwright"]
            self.assertEqual(kitsune["joint"], 2, "pb-c is not a joint success")
            self.assertEqual(kitsune["cold_start_setup_sec"], {"total": 4, "reported_runs": 1, "missing_runs": 1})
            self.assertEqual((kitsune["setup"]["observed_cpu_sec"]["total"], kitsune["setup"]["sampled_peak_rss_bytes"]),
                             (4, 6 * mib))
            self.assertEqual(kitsune["ready"]["duration_sec"]["total"], 2)
            self.assertEqual(kitsune["resources_task"]["observed_cpu_sec_per_measured_task"], 3)
            self.assertEqual(kitsune["resources_task"]["time_weighted_mean_rss_bytes"], 1000 * mib, "weighted by duration")
            self.assertEqual((kitsune["input_tokens"]["total"], kitsune["input_excl_cache_read_tokens"]["total"]),
                             (2000, 400), "Claude: uncached input plus cache writes")
            self.assertEqual(playwright["input_excl_cache_read_tokens"]["total"], 800, "Codex: total minus cached input")
            self.assertIsNone(playwright["cold_start_setup_sec"]["total"])
            self.assertIsNone(playwright["setup"]["observed_cpu_sec"]["total"])
            text = release.markdown(report, 1.10)
            self.assertIn("## Cost beyond tokens on joint successes", text)
            self.assertIn("| Input | Input excl. cache reads |", text)
            self.assertIn("| personal | playwright | 2 | — | — | — | — | 7.0 | 825 | 1,000 | 400 |", text)
            self.assertIn("| personal | kitsune | 2 | 4.0 (1/2) | 1.0 | 2.0 / 0.5 | 6 / 4 | 3.0 | 1,000 | 1,000 | 200 |", text)
            self.assertIn("counts shared memory more than once", text)


if __name__ == "__main__":
    unittest.main()
