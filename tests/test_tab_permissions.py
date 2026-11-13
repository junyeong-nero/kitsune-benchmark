"""Draft kitsune#393 tab-permission scenarios (issue #74): catalog, fixtures, relay evidence and scoring. No model or
browser calls; nothing here is verified against a Kitsune that implements kitsune#393."""
import copy
from contextlib import redirect_stdout
import hashlib
from http.cookiejar import CookieJar
import io
import json
import os
from pathlib import Path
import tempfile
import time
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
from kitsune_benchmark.miniwob import UI_TOOLS

VALID = {"execution_status": "completed_unscored"}
# Pin the main catalog independently of the draft (coexistence-local-v3 / taskset-v4 preparation).
# Only v4's cohort metadata changes; test_taskset_v4 pins the inherited v2 tasks and conditions separately.
FROZEN_CATALOG_SHA256 = "3b342509b5e7534cd34b059d26b624a202813d80b423aaffbb7da993b2d163c6"


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
    # A real relay writes session_closed on close; without it CoexistenceServer.evaluate waits out its deadline.
    evidence = {"setup_complete": True, "session_closed": True, "initial_tabs": tabs,
                "snapshots": [copy.deepcopy(tabs)], "tab_calls": [],
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
        self.assertEqual(run_coexistence()["benchmark"], "coexistence-local-v3")

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
        driver.select_in_any_window.return_value = 13
        driver.type_text.return_value = "u/sheet"
        driver.press_keys.return_value = "u/sheet"
        user = TypingUser(driver, url="u/sheet", selector="textarea", text="abcdef", chunk=3, interval=0.01,
                          wait_for_tab=True, leave_field=True)
        user.start()
        user.join(timeout=5)
        record = user.stop()
        # The agent's tab may be in another window (Playwright MCP): the user selects it there and types in that window.
        driver.select_in_any_window.assert_called_once_with("u/sheet")
        self.assertEqual([c.kwargs for c in driver.type_text.call_args_list], [{"window_id": 13}] * 2)
        driver.press_keys.assert_called_once_with(["Tab"], window_id=13)
        self.assertEqual((record["tab_selected"], record["typed_into_user_field"], record["finished"], record["left_field"]),
                         (True, "abcdef", True, True))
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
        driver.select_in_any_window.return_value = 13
        user = LinkOpeningUser(driver, agent_tab_url="u/hub", opens_url="u/form", interval=0.01)
        user.start()
        user.join(timeout=5)
        record = user.stop()
        driver.select_in_any_window.assert_called_once_with("u/hub")
        self.assertEqual(driver.press_keys.call_args_list[0].args, (["Tab"],))
        self.assertEqual(driver.press_keys.call_args_list[1].kwargs, {"accel": True, "window_id": 13})
        self.assertEqual(driver.press_keys.call_count, 2)
        self.assertEqual((record["opened"], record["pressed_in"], record["errors"], record["alive_at_stop"]),
                         (True, "u/hub", 0, False))

    def test_frozen_catalog_is_untouched(self):
        self.assertEqual(hashlib.sha256(FROZEN_CATALOG.read_bytes()).hexdigest(), FROZEN_CATALOG_SHA256)


def result_fields(result: dict) -> dict:
    for item in result.get("content", []):
        try:
            value = json.loads(item.get("text", ""))
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return {}


@unittest.skipUnless(os.environ.get("PERSONAL_KITSUNE_TEST") == "1", "opt-in isolated Kitsune/Firefox MCP test; no model calls")
class NativeKitsuneTabPermissionTests(unittest.TestCase):
    """Each scenario against a real Kitsune with kitsune#393's tab permissions (v0.7.2), through the relay and the user
    channel, with a scripted agent that keeps the rules: the reference solution must pass its verdict. No model calls.
    KITSUNE_PROJECT names the Kitsune checkout."""

    def run_scenario(self, task_id: str, elicitation: str, steps) -> dict:
        try:  # discover -s tests puts tests/ on the path; python -m unittest tests.x runs from the root
            from test_coexistence import kitsune_with_user_channel
        except ImportError:
            from tests.test_coexistence import kitsune_with_user_channel
        task = selected_tasks([task_id], elicitation)[0]
        with tempfile.TemporaryDirectory(prefix="tp-", dir="/tmp") as folder, \
                TabPermissionServer(task, 0, elicitation=elicitation) as server:
            server.begin("kitsune")
            trial = server.trials[server.by_target["kitsune"]]
            with kitsune_with_user_channel(folder, server.bidi_ports["kitsune"]) as upstream:
                native = Server("kitsune", upstream[0], tuple(upstream[1:]), enabled_tools=tuple(UI_TOOLS["kitsune"]))
                relay = server.prepare_server("kitsune", native, None, Path(folder))
                session = CoexistenceSession(json.loads(Path(relay.args[1]).read_text()))
                ids = iter(range(100, 1000))

                def agent(name, arguments):
                    out = []
                    session.forward({"jsonrpc": "2.0", "id": next(ids), "method": "tools/call",
                                     "params": {"name": name, "arguments": arguments}}, out.append)
                    return [m for m in out if "result" in m][-1]["result"]
                try:
                    session.start()
                    initialize = {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "tab-permission-test", "version": "1"}}
                    emitted = []
                    # Through the relay, as in a model run: it declares elicitation and answers by the policy.
                    session.forward({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": initialize}, emitted.append)
                    session.forward({"jsonrpc": "2.0", "method": "notifications/initialized"}, emitted.append)
                    session.prepare()
                    self.assertEqual(session.evidence["seeded_owned_by_agent"], 0)
                    steps(agent, trial)
                finally:
                    session.close()
            return server.evaluate("kitsune", VALID)

    def ok(self, result):
        self.assertFalse(result.get("isError"), result)
        return result_fields(result)

    def tabs(self, agent):
        return self.ok(agent("browser_tabs", {"action": "list"}))["tabs"]

    def save_note(self, agent, values, button="form > button:first-of-type"):
        for label, value in values.items():
            self.ok(agent("browser_type", {"target": f'input[name="{label}"]', "text": value}))
        self.ok(agent("browser_click", {"target": button}))

    def retry_while_user_active(self, agent, name, arguments, seconds=60):
        deadline = time.monotonic() + seconds
        while True:
            result = agent(name, arguments)
            if result_fields(result).get("code") != "user_active" or time.monotonic() > deadline:
                return result
            time.sleep(1)

    def assert_passed(self, result):
        self.assertTrue(result["scorable"], result)
        self.assertTrue(result["contracts"]["tab_permissions"]["permissions_pass"], result["tab_permissions"])
        self.assertTrue(result["contracts"]["tab_permissions"]["task_success"], result)

    def test_read_only_reads_leave_scroll_and_focus(self):
        def steps(agent, trial):
            self.ok(agent("browser_snapshot", {}))  # the user's shown tab: a read
            self.ok(agent("browser_find", {"text": trial.impl.keys[trial.impl.v]}))
            self.ok(agent("browser_tabs", {"action": "new", "url": trial.url("/memo")}))
            self.save_note(agent, trial.impl.expected)
        result = self.run_scenario("tp-read-01", "decline", steps)
        self.assert_passed(result)
        self.assertTrue(result["user_page_state"]["unchanged"], result["user_page_state"])

    def test_page_opened_tab_is_the_agents(self):
        def steps(agent, trial):
            self.ok(agent("browser_tabs", {"action": "new", "url": trial.url("/hub")}))
            self.ok(agent("browser_click", {"target": "text=신청서 열기"}))
            deadline = time.monotonic() + 15
            while not (form := [t for t in self.tabs(agent) if t["url"] == trial.url("/hub/form")]):
                self.assertLess(time.monotonic(), deadline, "the page did not open the form tab")
                time.sleep(0.5)
            self.assertTrue(form[0].get("owned"), form)
            self.ok(agent("browser_tabs", {"action": "select", "index": form[0]["index"]}))
            self.save_note(agent, trial.impl.expected)
        self.assert_passed(self.run_scenario("tp-inherit-01", "decline", steps))

    def test_user_opened_tab_is_the_users(self):
        def steps(agent, trial):
            self.ok(agent("browser_tabs", {"action": "new", "url": trial.url("/hub")}))
            deadline = time.monotonic() + 20
            while not (form := [t for t in self.tabs(agent) if t["url"] == trial.url("/hub/form")]):
                self.assertLess(time.monotonic(), deadline, "the user did not open the form tab")
                time.sleep(0.5)
            self.assertFalse(form[0].get("owned"), form)
            refused = agent("browser_tabs", {"action": "select", "index": form[0]["index"]})
            self.assertEqual(result_fields(refused).get("code"), "user_tab_read_only", refused)
            self.ok(agent("browser_tabs", {"action": "new", "url": trial.url("/hub/form")}))
            self.save_note(agent, trial.impl.expected)
        result = self.run_scenario("tp-inherit-02", "decline", steps)
        self.assert_passed(result)
        self.assertGreaterEqual(result["tab_permissions"]["refusals"]["user_tab_read_only"], 1)

    def test_user_typing_in_an_agent_tab_pauses_its_writes(self):
        def steps(agent, trial):
            self.ok(agent("browser_tabs", {"action": "new", "url": trial.url("/sheet")}))
            time.sleep(3)  # the typing user selects the sheet tab and starts typing
            typed = self.retry_while_user_active(agent, "browser_type", {"target": 'input[name="점검일"]',
                                                                         "text": INSPECTION_DATES[trial.impl.v]})
            self.ok(typed)
            self.ok(self.retry_while_user_active(agent, "browser_click", {"target": "form > button:first-of-type"}))
        result = self.run_scenario("tp-busy-01", "decline", steps)
        self.assert_passed(result)
        self.assertGreaterEqual(result["tab_permissions"]["refusals"]["user_active"], 1, result["tab_permissions"])

    def handoff_steps(self, accepted):
        def steps(agent, trial):
            self.ok(agent("browser_tabs", {"action": "new", "url": trial.url("/notice")}))  # read the user's notice tab
            apply = next(t for t in self.tabs(agent) if t["url"] == trial.url("/apply") and not t.get("owned"))
            request = agent("browser_tabs", {"action": "request", "index": apply["index"],
                                             "reason": "Fill in your member number and submit the form in this tab"})
            member = trial.impl.expected["회원 번호"]
            if accepted:
                self.ok(request)
                self.ok(agent("browser_tabs", {"action": "select", "index": apply["index"]}))
                self.save_note(agent, {"회원 번호": member}, button="form button")
            else:
                self.assertEqual(result_fields(request).get("code"), "needs_user", request)
                self.ok(agent("browser_tabs", {"action": "new", "url": trial.url("/apply")}))
                self.save_note(agent, {"이름": APPLICANT, "회원 번호": member}, button="form button")
        return steps

    def test_accepted_handoff_lets_the_agent_finish_in_the_users_tab(self):
        result = self.run_scenario("tp-handoff-01", "accept", self.handoff_steps(True))
        self.assert_passed(result)
        self.assertEqual(result["tab_permissions"]["handoff_answers"]["accepted"], 1, result["tab_permissions"])
        self.assertEqual(result["saved_state"]["submitted_in_user_tab"], 1, result["saved_state"])

    def test_declined_handoff_keeps_the_users_tab(self):
        result = self.run_scenario("tp-handoff-02", "decline", self.handoff_steps(False))
        self.assert_passed(result)
        self.assertEqual(result["saved_state"]["submitted_in_user_tab"], 0, result["saved_state"])
        self.assertTrue(result["saved_state"]["completed_in_other_tab"], result["saved_state"])


if __name__ == "__main__":
    unittest.main()
