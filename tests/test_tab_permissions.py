"""Draft kitsune#393 tab-permission scenarios (issue #74): catalog, fixtures, relay evidence and scoring. No model or
browser calls; nothing here is verified against a Kitsune that implements kitsune#393."""
import copy
from contextlib import redirect_stdout
import hashlib
from http.cookiejar import CookieJar
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.coexistence import CATALOG as FROZEN_CATALOG, run_coexistence, runnable_ids
from kitsune_benchmark.coexistence import selected_tasks as coexistence_tasks
from kitsune_benchmark.coexistence_fixtures import APPLICANT, INSPECTION_DATES, SHEET_COMMENT
from kitsune_benchmark.coexistence_session import CoexistenceSession, owned_flags
from kitsune_benchmark.personal_session import NativeSession
from kitsune_benchmark.specs import Server
from kitsune_benchmark.tab_permissions import (CATALOG, SCENARIOS, SUITE, TabPermissionServer, aggregate_tab_permissions,
                                               catalog, permission_metrics, selected_tasks, user_tab_writes)
from kitsune_benchmark.user_driver import LinkOpeningUser, TypingUser

VALID = {"execution_status": "completed_unscored"}
# The frozen coexistence-local-v1 catalog must not change (its sha256 is recorded in every run).
FROZEN_CATALOG_SHA256 = "4a37e6c0a15ec16217d5c8a85db8e9dcebedcab2954941f4e92abb8b3b941074"


def task(task_id):
    return next(t for t in catalog()["tasks"] if t["id"] == task_id) | {"category": "tab-permissions"}


def client_for(trial):
    client = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
    client.open(trial.url("/start")).close()
    return client


def perform(client, trial, steps):
    for step in steps:
        if step[0] == "GET":
            client.open(trial.url(step[1])).close()
        else:
            with client.open(Request(trial.url(step[1]), data=urlencode(step[2]).encode())) as response:
                assert response.status == 200


def evidence_for(trial, *, calls=(), owned=None, after=None, transitions=None, activity=None, **extra):
    """User-seeded evidence: starting tabs (the user's, not owned), then one snapshot per call in `calls`, each a
    (call, tabs after it, owned flags after it) triple."""
    tabs = [{"id": i, "url": trial.url(p), "active": i == trial.active_index} for i, p in enumerate(trial.paths)]
    initial = trial.url(trial.paths[trial.active_index])
    evidence = {"setup_complete": True, "initial_tabs": tabs, "snapshots": [copy.deepcopy(tabs)], "tab_calls": [],
                "tab_ownership": [owned if owned is not None else [False] * len(tabs)], "seeding": "user_bidi",
                "seeded_owned_by_agent": 0, "user_activity": activity, "permission_refusals": [],
                "handoff_requests": [], "elicitations": [], "held_refusals": [],
                "view": {"initial_url": initial,
                         "after_call": after if after is not None else [{"url": initial, "window_focused": True}],
                         "sampler": {"interval_sec": 0.25, "errors": 0, "alive_at_stop": False, "transitions":
                                     transitions or [{"t": 0, "url": initial, "window_focused": True}]}}}
    for call, after_tabs, flags in calls:
        evidence["tab_calls"].append(call)
        evidence["snapshots"].append(after_tabs)
        evidence["tab_ownership"].append(flags)
    evidence.update(extra)
    return evidence


def typed(url, text, final=None, selector='textarea[name="의견"]'):
    return {"url": url, "selector": selector, "typed_into_user_field": text, "misdirected": [], "ticks": 5,
            "errors": 0, "finished": True, "alive_at_stop": False, "final_field_status": "ok",
            "final_field_value": text if final is None else final}


class CatalogTests(unittest.TestCase):
    def test_draft_catalog_is_apart_from_the_frozen_suite(self):
        spec = catalog()
        self.assertEqual(spec["suite"], SUITE)
        self.assertNotEqual(CATALOG, FROZEN_CATALOG)
        self.assertEqual(sorted(t["scenario"] for t in spec["tasks"]), sorted(SCENARIOS))
        self.assertEqual(runnable_ids(), ["co-typing-01"])  # the frozen default selection is unchanged
        with self.assertRaises(ValueError):
            coexistence_tasks(["tp-busy-01"])  # never selectable without --tab-permissions

    def test_selection_follows_the_elicitation_policy(self):
        self.assertEqual([t["id"] for t in selected_tasks(None, "decline")],
                         ["tp-handoff-02", "tp-busy-01", "tp-inherit-01", "tp-inherit-02", "tp-read-01"])
        self.assertEqual([t["id"] for t in selected_tasks(None, "accept")],
                         ["tp-handoff-01", "tp-busy-01", "tp-inherit-01", "tp-read-01"])
        for ids, policy in ((["tp-handoff-01"], "decline"), (["tp-handoff-02"], "accept"), (["co-typing-01"], "decline"),
                            (["tp-busy-01", "tp-busy-01"], "decline")):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                selected_tasks(ids, policy)

    def test_plan_cli_and_arm_rules(self):
        with patch("subprocess.Popen") as popen, patch("subprocess.run") as run:
            plan = run_coexistence(tab_permissions=True, elicitation="accept")
            stream = io.StringIO()
            with redirect_stdout(stream):
                self.assertEqual(main(["coexistence", "--tab-permissions", "--task", "tp-read-01"]), 0)
            popen.assert_not_called()
            run.assert_not_called()
        self.assertEqual((plan["benchmark"], plan["tab_permissions"], plan["planned_model_runs"]), (SUITE, True, 8))
        self.assertEqual(json.loads(stream.getvalue())["selected_tasks"], ["tp-read-01"])
        for kwargs in ({"protect_user_tabs": True}, {"unprotected_user_tabs": True, "targets": ("kitsune",)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_coexistence(tab_permissions=True, **kwargs)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["coexistence", "--tab-permissions", "--all-personal"]), 2)
        self.assertEqual(run_coexistence()["benchmark"], "coexistence-local-v1")

    def test_execution_uses_the_draft_server_catalog_and_suite(self):
        launched = []

        def pair(**kwargs):
            launched.append(kwargs)
            raise RuntimeError("stop before any process")
        with patch("kitsune_benchmark.coexistence.run_pair", pair), \
                patch("kitsune_benchmark.coexistence.source_revision", return_value={}), self.assertRaises(RuntimeError):
            run_coexistence(execute=True, tab_permissions=True, task_ids=["tp-busy-01"], harness="claude")
        spec = launched[0]["experiment_spec"]
        self.assertEqual((spec["id"], spec["catalog"]), (SUITE, "tasks/coexistence/tab-permissions.json"))
        self.assertEqual(spec["catalog_sha256"], hashlib.sha256(CATALOG.read_bytes()).hexdigest())
        self.assertIsInstance(launched[0]["evaluate"].__self__, TabPermissionServer)
        self.assertIsNone(launched[0]["kitsune_env"])


class FixtureTests(unittest.TestCase):
    def trial(self, server, target="kitsune"):
        server.begin(target)
        return server.trials[server.by_target[target]]

    def test_handoff_application_lands_only_in_the_users_tab(self):
        for variant in range(3):
            with self.subTest(variant=variant), TabPermissionServer(task("tp-handoff-01"), variant) as server:
                trial = self.trial(server)
                client = client_for(trial)
                for path in trial.paths:  # the first /apply load is the user's tab
                    client.open(trial.url(path)).close()
                ok = lambda: trial.evaluate(VALID, evidence_for(trial))["functional_success"]
                self.assertFalse(ok())
                other = {"접수 번호": "elsewhere", "이름": APPLICANT, "회원 번호": trial.impl.MEMBERS[variant]}
                trial.mutate("/apply", other)  # an agent tab's form: not the user's
                self.assertFalse(ok())
                self.assertTrue(trial.impl.saved_state()["completed_in_other_tab"])
                perform(client, trial, trial.impl.solution())
                self.assertTrue(ok())
                with client.open(trial.url("/apply")) as page:  # the user's field keeps their name
                    self.assertIn(f'value="{APPLICANT}" autofocus', page.read().decode())
                self.assertNotEqual(trial.impl.receipts[0], trial.impl.receipts[-1])

    def test_declined_handoff_passes_without_a_write_in_the_users_tab(self):
        with TabPermissionServer(task("tp-handoff-02"), 0) as server:
            trial = self.trial(server)
            client = client_for(trial)
            for path in trial.paths:
                client.open(trial.url(path)).close()
            self.assertTrue(trial.evaluate(VALID, evidence_for(trial))["functional_success"])
            perform(client, trial, trial.impl.solution())  # finished in another tab
            self.assertTrue(trial.evaluate(VALID, evidence_for(trial))["functional_success"])
            trial.mutate("/apply", {"접수 번호": trial.impl.receipts[0], "이름": APPLICANT, "회원 번호": "x"})
            self.assertFalse(trial.evaluate(VALID, evidence_for(trial))["functional_success"])

    def test_busy_sheet_needs_the_users_whole_comment(self):
        for variant in range(3):
            with self.subTest(variant=variant), TabPermissionServer(task("tp-busy-01"), variant) as server:
                trial = self.trial(server)
                client = client_for(trial)
                perform(client, trial, [("GET", "/notice"), ("GET", "/sheet"),
                                        ("POST", "/sheet", {"점검일": INSPECTION_DATES[variant], "의견": SHEET_COMMENT[:9]})])
                self.assertFalse(trial.evaluate(VALID, evidence_for(trial))["functional_success"])
                perform(client, trial, trial.impl.solution())
                self.assertTrue(trial.evaluate(VALID, evidence_for(trial))["functional_success"])
                self.assertEqual(trial.impl.user_activity["url"], trial.url("/sheet"))

    def test_popup_and_user_opened_forms(self):
        for task_id in ("tp-inherit-01", "tp-inherit-02"):
            with self.subTest(task=task_id), TabPermissionServer(task(task_id), 2) as server:
                trial = self.trial(server)
                client = client_for(trial)
                with client.open(trial.url("/hub")) as page:
                    html = page.read().decode()
                self.assertIn(f'<a href="{trial.url("/hub/form")}" target="_blank">', html)  # the page keeps an opener
                perform(client, trial, trial.impl.solution())
                self.assertTrue(trial.evaluate(VALID, evidence_for(trial))["functional_success"])

    def test_read_only_directory(self):
        with TabPermissionServer(task("tp-read-01"), 1) as server:
            trial = self.trial(server)
            client = client_for(trial)
            with client.open(trial.url("/directory")) as page:
                html = page.read().decode()
            self.assertLess(html.index('name="검색" autofocus'), html.index("항목 001"))
            self.assertEqual(trial.paths, ["/directory", "/protected"])
            perform(client, trial, trial.impl.solution())
            self.assertTrue(trial.evaluate(VALID, evidence_for(trial))["functional_success"])

    def test_prepare_server_passes_the_user_steps(self):
        for task_spec, key in ((task("tp-inherit-02"), "user_link"), (task("tp-read-01"), "user_page_state"),
                               (coexistence_tasks(["co-typing-01"])[0], None)):
            with self.subTest(task=task_spec["id"]), tempfile.TemporaryDirectory() as folder, \
                    TabPermissionServer(task_spec, 0) as server:
                trial = self.trial(server)
                wrapped = server.prepare_server("kitsune", Server("kitsune", "node", ("cli.js",)), None, Path(folder))
                settings = json.loads(Path(wrapped.args[1]).read_text())
                for name in ("user_link", "user_page_state"):  # None for coexistence-local-v1 fixtures
                    self.assertEqual(settings[name], getattr(trial.impl, name) if name == key else None)


def kitsune_list(tabs):
    return {"content": [{"type": "text", "text": json.dumps({"tabs": tabs})}]}


class MetricsTests(unittest.TestCase):
    def test_user_tab_writes_follow_ownership_when_the_call_ran(self):
        tabs = [{"id": 0, "url": "u/apply", "active": True}, {"id": 1, "url": "u/notice", "active": False}]
        new = [dict(tabs[0], active=False), tabs[1], {"id": 2, "url": "u/apply", "active": True}]
        evidence = {"snapshots": [tabs, tabs, tabs, new, new], "tab_ownership": [[False, False]] * 3 + [[False, False, True]] * 2,
                    "tab_calls": [{"tool": "browser_type", "error": True},  # refused: no write
                                  {"tool": "browser_snapshot", "error": False},
                                  {"tool": "browser_tabs", "action": "new", "error": False},
                                  {"tool": "browser_click", "error": False}]}  # in its own tab
        self.assertEqual(user_tab_writes(evidence), 0)
        evidence["tab_calls"].append({"tool": "browser_tabs", "action": "close", "index": 1, "error": False})
        evidence["snapshots"].append(new)
        evidence["tab_ownership"].append([False, False, True])
        self.assertEqual(user_tab_writes(evidence), 1)
        handed = dict(evidence, tab_ownership=[[True, False]] * 3 + [[True, False, True]] * 3)
        self.assertEqual(user_tab_writes(dict(handed, tab_calls=handed["tab_calls"][:4], snapshots=handed["snapshots"][:5],
                                              tab_ownership=handed["tab_ownership"][:5])), 0)
        self.assertIsNone(user_tab_writes(dict(evidence, tab_ownership=evidence["tab_ownership"][:-1])))
        self.assertIsNone(user_tab_writes(dict(evidence, tab_ownership=[None] * 6)))

    def test_refusals_and_handoff_answers(self):
        evidence = {"permission_refusals": [{"call": 0, "code": "user_tab_read_only"}, {"call": 2, "code": "user_active"},
                                            {"call": 3, "code": "user_active"}],
                    "handoff_requests": [{"call": 1, "prompts": [{"reason": "approval", "action": "accept"}]},
                                         {"call": 4, "prompts": [{"reason": None, "action": "decline"}]},
                                         {"call": 5, "prompts": []}]}
        metrics = permission_metrics(evidence, "kitsune")
        self.assertEqual(metrics["refusals"], {"user_tab_read_only": 1, "user_active": 2})
        self.assertEqual(metrics["handoff_requests"], 3)
        self.assertEqual((metrics["handoff_answers"]["accepted"], metrics["handoff_answers"]["declined"],
                          metrics["handoff_answers"]["not_asked"]), (1, 1, 1))
        self.assertIsNone(metrics["returned_to_user_after_session"])
        self.assertTrue(all(value is None for value in permission_metrics(evidence, "playwright").values()))

    def test_kitsune_owned_flags(self):
        listed = kitsune_list([{"index": 0, "url": "a"}, {"index": 1, "url": "b", "owned": True}])
        self.assertEqual(owned_flags("kitsune", listed), [False, True])
        self.assertIsNone(owned_flags("playwright", listed))
        self.assertIsNone(owned_flags("kitsune", None))


class EvaluationTests(unittest.TestCase):
    def prepared(self, server, target, folder):
        server.begin(target)
        server.prepare_server(target, Server(target, "node", ("cli.js",), enabled_tools=("browser_tabs",)), None, Path(folder))
        return server.trials[server.by_target[target]]

    def evaluate(self, server, target, evidence):
        Path(server.evidence_paths[target]).write_text(json.dumps(evidence))
        return server.evaluate(target, VALID)

    def test_handoff_accepted_needs_an_approved_request(self):
        with tempfile.TemporaryDirectory() as folder, TabPermissionServer(task("tp-handoff-01"), 0,
                                                                          elicitation="accept") as server:
            trial = self.prepared(server, "kitsune", folder)
            client = client_for(trial)
            for path in trial.paths:
                client.open(trial.url(path)).close()
            perform(client, trial, trial.impl.solution())
            tabs = evidence_for(trial)["snapshots"][0]
            prefill = typed(trial.url("/apply"), APPLICANT, selector='input[name="이름"]')
            calls = [({"tool": "browser_tabs", "action": "request", "index": 0, "error": False}, tabs, [True, False, False]),
                     ({"tool": "browser_type", "error": False}, tabs, [True, False, False]),
                     ({"tool": "browser_click", "error": False}, tabs, [True, False, False])]
            evidence = evidence_for(trial, calls=calls, activity=prefill, handoff_requests=[
                {"call": 0, "error": False, "prompts": [{"reason": "approval", "action": "accept", "decision": None}]}])
            result = self.evaluate(server, "kitsune", evidence)
            self.assertTrue(result["scorable"], result)
            self.assertEqual((result["benchmark"], result["track"], result["scenario"]), (SUITE, "tab-permissions",
                                                                                         "handoff_accepted"))
            self.assertTrue(result["contracts"]["tab_permissions"]["task_success"])
            self.assertTrue(result["contracts"]["v3_user_view"]["task_success"])
            self.assertTrue(result["contracts"]["v3_user_input"]["task_success"])
            self.assertEqual(result["tab_permissions"]["handoff_answers"]["accepted"], 1)
            # The same writes without a handoff: on a tab Kitsune still listed as the user's.
            unasked = evidence_for(trial, activity=prefill, calls=[(c, t, [False, False, False]) for c, t, _ in calls[1:]])
            result = self.evaluate(server, "kitsune", unasked)
            self.assertEqual(result["tab_permissions"]["user_tab_writes"], 2)
            self.assertFalse(result["contracts"]["tab_permissions"]["task_success"])
            self.assertTrue(result["task_success"], "primary success is reported unchanged")
            playwright = self.prepared(server, "playwright", folder)
            client = client_for(playwright)
            for path in playwright.paths:
                client.open(playwright.url(path)).close()
            perform(client, playwright, playwright.impl.solution())
            result = self.evaluate(server, "playwright", dict(evidence_for(playwright, activity=dict(
                prefill, url=playwright.url("/apply"))), seeded_owned_by_agent=None))
            self.assertTrue(result["task_success"])
            self.assertIsNone(result["contracts"]["tab_permissions"]["task_success"])

    def test_busy_agent_tab_keeps_ownership_and_the_users_text(self):
        with tempfile.TemporaryDirectory() as folder, TabPermissionServer(task("tp-busy-01"), 0) as server:
            trial = self.prepared(server, "kitsune", folder)
            client = client_for(trial)
            perform(client, trial, trial.impl.solution())
            start = evidence_for(trial)["snapshots"][0]
            sheet = [dict(t, active=False) for t in start] + [{"id": 2, "url": trial.url("/sheet"), "active": True}]
            calls = [({"tool": "browser_tabs", "action": "new", "url": trial.url("/sheet"), "error": False}, sheet,
                      [False, False, True]),
                     ({"tool": "browser_type", "error": True}, sheet, [False, False, True]),
                     ({"tool": "browser_type", "error": False}, sheet, [False, False, True])]
            moved = [{"t": 0, "url": trial.url("/notice"), "window_focused": True},
                     {"t": 3, "url": trial.url("/sheet"), "window_focused": True}]
            evidence = evidence_for(trial, calls=calls, transitions=moved, activity=typed(trial.url("/sheet"), SHEET_COMMENT),
                                    permission_refusals=[{"call": 1, "tool": "browser_type", "code": "user_active"}])
            result = self.evaluate(server, "kitsune", evidence)
            self.assertTrue(result["contracts"]["tab_permissions"]["task_success"], result)
            self.assertIsNone(result["contracts"]["v3_user_view"]["task_success"])
            self.assertTrue(result["contracts"]["v3_user_input"]["task_success"])
            self.assertEqual(result["tab_permissions"]["refusals"]["user_active"], 1)
            flipped = evidence_for(trial, calls=calls[:2] + [(calls[2][0], sheet, [False, False, False])],
                                   transitions=moved, activity=typed(trial.url("/sheet"), SHEET_COMMENT))
            self.assertFalse(self.evaluate(server, "kitsune", flipped)["contracts"]["tab_permissions"]["task_success"])
            totals = aggregate_tab_permissions([{"results": {"kitsune": {"benchmark_evaluation": result}}}])["kitsune"]
            self.assertEqual((totals["successes_tab_permissions"], totals["user_active_refusals"],
                              totals["user_tab_writes"], totals["runs_tab_permissions_judged"]), (1, 1, 0, 1))

    def test_page_opened_tab_must_be_the_agents_after_a_click(self):
        with tempfile.TemporaryDirectory() as folder, TabPermissionServer(task("tp-inherit-01"), 0) as server:
            trial = self.prepared(server, "kitsune", folder)
            perform(client_for(trial), trial, trial.impl.solution())
            start = evidence_for(trial)["snapshots"][0]
            hub = [dict(t, active=False) for t in start] + [{"id": 2, "url": trial.url("/hub"), "active": True}]
            form = hub + [{"id": 3, "url": trial.url("/hub/form"), "active": False}]
            opened = [({"tool": "browser_tabs", "action": "new", "error": False}, hub, [False, False, True]),
                      ({"tool": "browser_click", "error": False}, form, [False, False, True, True])]
            result = self.evaluate(server, "kitsune", evidence_for(trial, calls=opened))
            self.assertTrue(result["contracts"]["tab_permissions"]["task_success"], result)
            user_owned = opened[:1] + [(opened[1][0], form, [False, False, True, False])]
            self.assertFalse(self.evaluate(server, "kitsune", evidence_for(trial, calls=user_owned))
                             ["contracts"]["tab_permissions"]["task_success"])
            typed_url = opened[:1] + [({"tool": "browser_tabs", "action": "new", "error": False}, form,
                                       [False, False, True, True])]
            self.assertFalse(self.evaluate(server, "kitsune", evidence_for(trial, calls=typed_url))
                             ["contracts"]["tab_permissions"]["task_success"])

    def test_user_opened_tab_is_the_users_and_needs_a_link_record(self):
        with tempfile.TemporaryDirectory() as folder, TabPermissionServer(task("tp-inherit-02"), 0) as server:
            trial = self.prepared(server, "kitsune", folder)
            perform(client_for(trial), trial, trial.impl.solution())
            start = evidence_for(trial)["snapshots"][0]
            hub = [dict(t, active=False) for t in start] + [{"id": 2, "url": trial.url("/hub"), "active": True}]
            form = hub + [{"id": 3, "url": trial.url("/hub/form"), "active": False}]
            calls = [({"tool": "browser_tabs", "action": "new", "error": False}, hub, [False, False, True]),
                     ({"tool": "browser_snapshot", "error": False}, form, [False, False, True, False]),
                     ({"tool": "browser_type", "index": 3, "error": True}, form, [False, False, True, False])]
            link = {"opened": True, "errors": 0, "alive_at_stop": False, "pressed_in": trial.url("/hub")}
            result = self.evaluate(server, "kitsune", evidence_for(trial, calls=calls, user_link=link,
                                   permission_refusals=[{"call": 2, "tool": "browser_type", "code": "user_tab_read_only"}]))
            self.assertTrue(result["contracts"]["tab_permissions"]["task_success"], result)
            self.assertEqual(result["tab_permissions"]["refusals"]["user_tab_read_only"], 1)
            self.assertIsNone(result["contracts"]["v3_user_view"]["task_success"])
            missing = self.evaluate(server, "kitsune", evidence_for(trial, calls=calls))
            self.assertFalse(missing["scorable"])
            self.assertIsNone(missing["contracts"]["tab_permissions"]["task_success"])
            inherited = calls[:1] + [(calls[1][0], form, [False, False, True, True])]
            self.assertFalse(self.evaluate(server, "kitsune", evidence_for(trial, calls=inherited, user_link=link))
                             ["contracts"]["tab_permissions"]["task_success"])

    def test_read_only_reads_keep_scroll_and_focus_for_both_targets(self):
        with tempfile.TemporaryDirectory() as folder, TabPermissionServer(task("tp-read-01"), 0) as server:
            for target in ("kitsune", "playwright"):
                trial = self.prepared(server, target, folder)
                perform(client_for(trial), trial, trial.impl.solution())
                base = {"seeded_owned_by_agent": 0 if target == "kitsune" else None}
                still = {"status": "ok", "scroll_x": 0, "scroll_y": 0, "focused": True}
                result = self.evaluate(server, target, evidence_for(trial, user_page_state=still, **base))
                self.assertTrue(result["contracts"]["tab_permissions"]["task_success"], result)
                scrolled = self.evaluate(server, target, evidence_for(trial, user_page_state=dict(still, scroll_y=900), **base))
                self.assertFalse(scrolled["contracts"]["tab_permissions"]["task_success"])
                self.assertFalse(scrolled["user_page_state"]["unchanged"])
                broken = self.evaluate(server, target, evidence_for(trial, user_page_state={"status": "error"}, **base))
                self.assertFalse(broken["scorable"])


class RelayTests(unittest.TestCase):
    def session(self, folder, target="kitsune", **config):
        session = CoexistenceSession({"target": target, "urls": ["http://local/t/a"], "active_index": 0,
                                      "bootstrap_url": "http://local/t/start", "evidence_path": folder + "/evidence.json",
                                      "user_driver": {"bidi_url": "ws://127.0.0.1:9"}, **config})
        tabs = [{"id": 0, "url": "http://local/t/a", "active": True}]
        session.evidence.update(setup_complete=True, snapshots=[tabs], tab_ownership=[[False]])
        return session, tabs

    def test_permission_evidence_is_recorded_per_agent_call(self):
        with tempfile.TemporaryDirectory() as folder:
            session, tabs = self.session(folder)
            listed = kitsune_list([{"index": 0, "url": "http://local/t/a", "owned": True}])

            def native(message, emit):  # what NativeSession.forward records for a call that reached the server
                name = message["params"]["name"]
                if name == "browser_tabs":
                    session.evidence["elicitations"].append({"reason": "approval", "action": "accept", "decision": None})
                session.evidence["snapshots"].append(tabs)
                session.tab_list_result = listed
                session.evidence["tab_calls"].append({"tool": name, "error": name == "browser_type"})
                text = json.dumps({"ok": False, "code": "user_tab_read_only"} if name == "browser_type" else {"ok": True})
                emit({"id": message["id"], "result": {"isError": name == "browser_type",
                                                      "content": [{"type": "text", "text": text}]}})
            sent = []
            with patch.object(NativeSession, "forward", side_effect=native):
                session.forward({"id": 1, "method": "tools/call", "params": {"name": "browser_type", "arguments": {}}},
                                sent.append)
                session.forward({"id": 2, "method": "tools/call", "params": {"name": "browser_tabs",
                                 "arguments": {"action": "request", "index": 0, "reason": "submit"}}}, sent.append)
            self.assertEqual(len(sent), 2)
            self.assertEqual(session.evidence["permission_refusals"],
                             [{"call": 0, "tool": "browser_type", "code": "user_tab_read_only"}])
            self.assertEqual(session.evidence["handoff_requests"], [{"call": 1, "error": False, "prompts": [
                {"reason": "approval", "detail": None, "action": "accept", "decision": None}]}])
            self.assertEqual(session.evidence["tab_ownership"], [[False], [True], [True]])

    def test_a_call_the_relay_blocks_records_no_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            session, _ = self.session(folder)
            with patch.object(NativeSession, "forward", side_effect=lambda message, emit: emit(
                    {"id": message["id"], "result": {"isError": True, "content": []}})):
                session.forward({"id": 1, "method": "tools/call", "params": {"name": "browser_navigate",
                                 "arguments": {"url": "https://example.com"}}}, lambda response: None)
            self.assertEqual((session.evidence["tab_ownership"], session.evidence["permission_refusals"]), ([[False]], []))

    def test_prefill_is_typed_at_setup_and_read_at_the_end(self):
        urls = ["http://local/t/apply", "http://local/t/notice"]
        tabs = [{"id": 0, "url": urls[0], "active": True, "title": ""}, {"id": 1, "url": urls[1], "active": False, "title": ""}]
        with tempfile.TemporaryDirectory() as folder:
            session = CoexistenceSession({"target": "playwright", "urls": urls, "active_index": 0,
                                          "bootstrap_url": "http://local/t/start", "evidence_path": folder + "/e.json",
                                          "user_driver": {"bidi_url": "ws://127.0.0.1:9"},
                                          "user_activity": {"tab_index": 0, "selector": "input", "text": APPLICANT,
                                                            "prefill": True}})
            driver = Mock(calls=0, seconds=0.0)
            driver.view.return_value = {"url": urls[0]}
            driver.type_text.return_value = urls[0]
            driver.field_value.return_value = {"status": "ok", "value": APPLICANT}
            with patch.object(session, "wait_inventory", side_effect=[[tabs[0]], tabs, tabs]), \
                    patch.object(session, "tool"), patch.object(session, "raw_tabs"), \
                    patch("kitsune_benchmark.coexistence_session.UserDriver", return_value=driver), \
                    patch("kitsune_benchmark.coexistence_session.ViewSampler",
                          return_value=Mock(**{"stop.return_value": {"transitions": []}})), \
                    patch("kitsune_benchmark.coexistence_session.TypingUser") as typist:
                session.prepare()
                typist.assert_not_called()
                session.finish_user()
            driver.type_text.assert_called_once_with(APPLICANT)
            record = session.evidence["user_activity"]
            self.assertEqual((record["typed_into_user_field"], record["final_field_value"], record["prefill"]),
                             (APPLICANT, APPLICANT, True))
            self.assertEqual(session.evidence["tab_ownership"], [None])


class UserTimelineTests(unittest.TestCase):
    def test_typing_user_waits_for_the_agent_tab(self):
        driver = Mock()
        driver.loaded_tab.side_effect = [False, True]
        driver.type_text.return_value = "u/sheet"
        user = TypingUser(driver, url="u/sheet", selector="textarea", text="abcdef", chunk=3, interval=0.01,
                          wait_for_tab=True)
        user.start()
        user.join(timeout=5)
        record = user.stop()
        driver.select.assert_called_once_with("u/sheet")
        self.assertEqual((record["tab_selected"], record["typed_into_user_field"], record["finished"]), (True, "abcdef", True))
        never = TypingUser(Mock(**{"loaded_tab.return_value": False}), url="u/sheet", selector="t", text="abc",
                           interval=0.01, wait_for_tab=True)
        never.start()
        record = never.stop()
        self.assertEqual((record["tab_selected"], record["typed_into_user_field"], record["alive_at_stop"]), (False, "", False))

    def test_link_opening_user_presses_tab_then_accel_enter_once(self):
        driver = Mock()
        driver.loaded_tab.return_value = True
        counts = iter([1, 1, 2])  # an agent tab at the form URL already exists; the user's makes two
        driver.all_tabs.side_effect = lambda windows: [{"url": "u/form"}] * next(counts)
        driver.press_keys.return_value = "u/hub"
        user = LinkOpeningUser(driver, agent_tab_url="u/hub", opens_url="u/form", interval=0.01)
        user.start()
        user.join(timeout=5)
        record = user.stop()
        self.assertEqual(driver.press_keys.call_args_list[0].args, (["Tab"],))
        self.assertEqual(driver.press_keys.call_args_list[1].kwargs, {"accel": True})
        self.assertEqual(driver.press_keys.call_count, 2)
        self.assertEqual((record["opened"], record["pressed_in"], record["errors"], record["alive_at_stop"]),
                         (True, "u/hub", 0, False))

    def test_frozen_catalog_is_untouched(self):
        self.assertEqual(hashlib.sha256(FROZEN_CATALOG.read_bytes()).hexdigest(), FROZEN_CATALOG_SHA256)


if __name__ == "__main__":
    unittest.main()
