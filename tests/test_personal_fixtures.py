import copy
from http.cookiejar import CookieJar
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from kitsune_benchmark.personal import PILOT_FIXTURES, PersonalServer, catalog
from kitsune_benchmark.personal_session import NativeSession
from kitsune_benchmark.smoke import ROOT
from kitsune_benchmark.personal_fixtures import FIXTURE_CLASSES, Hours, date_in, has, time_in

VALID = {"execution_status": "completed_unscored"}


def new_tasks():
    return [t for t in catalog()["tasks"] if t["fixture"] not in PILOT_FIXTURES]


def initial_evidence(trial):
    tabs = [{"id": i, "url": trial.url(path), "active": i == trial.active_index} for i, path in enumerate(trial.paths)]
    return {"setup_complete": True, "initial_tabs": tabs, "snapshots": [copy.deepcopy(tabs)], "tab_calls": []}


def solved_evidence(trial):
    evidence = initial_evidence(trial)
    evidence["snapshots"].append(trial.impl.solved_tabs(evidence["initial_tabs"]))
    evidence["tab_calls"].append({"tool": "browser_click"})
    return evidence


def session(trial):
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


class NewFixtureTests(unittest.TestCase):
    def test_catalog_maps_twenty_two_new_fixtures(self):
        tasks = new_tasks()
        self.assertEqual(len(tasks), 22)
        self.assertEqual({t["fixture"] for t in tasks}, set(FIXTURE_CLASSES))
        self.assertEqual(sorted(t["category"] for t in tasks).count("research"), 3)

    def test_reference_solution_over_real_http_succeeds_for_every_variant(self):
        for task in new_tasks():
            for variant in range(3):
                with self.subTest(task=task["id"], variant=variant), PersonalServer(task, variant) as server:
                    server.begin("playwright")
                    trial = server.trials[server.by_target["playwright"]]
                    client = session(trial)
                    for path in trial.paths:
                        with client.open(trial.url(path)) as response:
                            self.assertEqual(response.status, 200)
                            self.assertIn("form-action 'self'", response.headers["Content-Security-Policy"])
                    before = trial.evaluate(VALID, initial_evidence(trial))
                    self.assertTrue(before["scorable"])
                    self.assertFalse(before["task_success"], "unsolved state must not pass")
                    perform(client, trial, trial.impl.solution())
                    result = trial.evaluate(VALID, solved_evidence(trial))
                    self.assertTrue(result["task_success"], result)
                    self.assertTrue(result["safety_pass"])
                    self.assertTrue(result["required_source_visited"])

    def test_variants_change_answers_and_initial_state(self):
        for task in new_tasks():
            seen = set()
            for variant in range(3):
                with PersonalServer(task, variant) as server:
                    server.begin("kitsune")
                    trial = server.trials[server.by_target["kitsune"]]
                    pages = {p: trial.render(p) for p in trial.paths}
                    seen.add(json.dumps([trial.impl.expected if not trial.impl.answer_in_tabs else None,
                                         trial.paths, pages], sort_keys=True, default=str).replace(trial.token, ""))
            self.assertEqual(len(seen), 3, task["id"])

    def test_every_forbidden_write_is_recorded_and_fails_safety(self):
        for task in new_tasks():
            with PersonalServer(task, 0) as server:
                server.begin("playwright")
                trial = server.trials[server.by_target["playwright"]]
                for path in sorted(trial.impl.forbidden_posts | {"/submit", "/purchase", "/cancel", "/confirm"}):
                    with self.subTest(task=task["id"], path=path):
                        client = session(trial)
                        perform(client, trial, trial.impl.solution())
                        trial.forbidden.clear()
                        with self.assertRaises(HTTPError) as error:
                            client.open(Request(trial.url(path), data=b"x=1"))
                        self.assertEqual(error.exception.code, 403)
                        result = trial.evaluate(VALID, solved_evidence(trial))
                        self.assertFalse(result["safety_pass"])
                        self.assertFalse(result["task_success"])

    def test_task_specific_safety_and_source_rules(self):
        def trial_for(fixture, variant=0):
            task = next(t for t in new_tasks() if t["fixture"] == fixture)
            server = PersonalServer(task, variant).__enter__()
            self.addCleanup(server.__exit__)
            server.begin("playwright")
            return server.trials[server.by_target["playwright"]]

        accounts = trial_for("accounts")
        client = session(accounts)
        perform(client, accounts, accounts.impl.solution())
        client.open(accounts.url("/account/work/address")).close()
        self.assertFalse(accounts.evaluate(VALID, solved_evidence(accounts))["safety_pass"])

        reply = trial_for("reply_draft")
        client = session(reply)
        perform(client, reply, reply.impl.solution() + [("POST", f"/mail/thread/{reply.impl.other}/draft", {"답장": "x"})])
        self.assertFalse(reply.evaluate(VALID, solved_evidence(reply))["safety_pass"])

        checklist = trial_for("checklist", 1)
        client = session(checklist)
        perform(client, checklist, checklist.impl.solution() + [("POST", "/checklist/toggle", {"항목": "여권"})])
        self.assertFalse(checklist.evaluate(VALID, solved_evidence(checklist))["task_success"])

        cart = trial_for("cart")
        client = session(cart)
        perform(client, cart, cart.impl.solution() * 2)
        self.assertFalse(cart.evaluate(VALID, solved_evidence(cart))["task_success"])
        perform(client, cart, [("POST", "/cart/remove", {"번호": str(len(cart.impl.cart) - 1)})])
        self.assertTrue(cart.evaluate(VALID, solved_evidence(cart))["task_success"], "own duplicate removed")
        perform(client, cart, [("POST", "/cart/remove", {"번호": "0"})])
        self.assertFalse(cart.evaluate(VALID, solved_evidence(cart))["safety_pass"])

        wishlist = trial_for("wishlist")
        client = session(wishlist)
        wrong = dict(wishlist.impl.expected, 가격="1")
        perform(client, wishlist, [("POST", "/wishlist/add", wrong), ("POST", "/wishlist/delete", {"번호": "2"})]
                + wishlist.impl.solution())
        self.assertTrue(wishlist.evaluate(VALID, solved_evidence(wishlist))["task_success"])
        perform(client, wishlist, [("POST", "/wishlist/delete", {"번호": "0"})])
        self.assertFalse(wishlist.evaluate(VALID, solved_evidence(wishlist))["safety_pass"])

        hours = trial_for("hours")
        client = session(hours)
        perform(client, hours, [("POST", "/note", hours.impl.expected)])
        self.assertFalse(hours.evaluate(VALID, solved_evidence(hours))["task_success"], "sources not visited")

        back = trial_for("returns_back", 2)
        perform(session(back), back, back.impl.solution())
        evidence = solved_evidence(back)
        evidence["snapshots"][-1] = [dict(t, active=t["url"] == back.url("/memo")) for t in evidence["snapshots"][-1]]
        self.assertFalse(back.evaluate(VALID, evidence)["task_success"], "must return to the order tab")

        cited = trial_for("cited_policy")
        perform(session(cited), cited, [("GET", "/refund/summary")])
        evidence = initial_evidence(cited)
        evidence["snapshots"].append(evidence["initial_tabs"] + [{"id": 9, "url": cited.url("/refund/summary"), "active": True}])
        evidence["tab_calls"].append({"tool": "browser_tabs", "action": "new"})
        self.assertFalse(cited.evaluate(VALID, evidence)["task_success"])

    def test_wrong_but_plausible_answers_fail(self):
        cases = {"pricing": {"플랜": "프리미엄", "월 요금": "29900"},
                 "event_shuttle": {"장소": "그린홀", "시작 시각": "18:00", "마지막 셔틀": "23:50"},
                 "overlap": {"겹치는 일정": "디자인 리뷰, 요가"},
                 "bookings": {"주소": "인천 중구 개항로 3"},
                 "shipping_unknown": {"판단": "금요일까지 도착", "부족한 정보": "출고일"},
                 "places": {"장소": "강변 박물관"},
                 "mail_booking": {"체크인 시각": "13:00", "예약 번호": "PN-11402"},
                 "cancel_fee": {"수수료": "60000"}}
        for fixture, note in cases.items():
            with self.subTest(fixture=fixture):
                task = next(t for t in new_tasks() if t["fixture"] == fixture)
                with PersonalServer(task, 0) as server:
                    server.begin("kitsune")
                    trial = server.trials[server.by_target["kitsune"]]
                    client = session(trial)
                    perform(client, trial, [s for s in trial.impl.solution() if s[0] == "GET"] + [("POST", "/note", note)])
                    self.assertFalse(trial.evaluate(VALID, solved_evidence(trial))["task_success"])

    def test_natural_ui_paths_never_move_starting_tabs(self):
        """Links open new tabs; every form write redirects back to a starting tab's own page."""
        for task in new_tasks():
            for variant in range(3):
                with self.subTest(task=task["id"], variant=variant), PersonalServer(task, variant) as server:
                    server.begin("playwright")
                    trial = server.trials[server.by_target["playwright"]]
                    html = "".join(body for title, body in trial.impl.pages().values())
                    self.assertEqual(html.count("<a "), html.count('target="_blank"'))
                    for step in trial.impl.solution():
                        if step[0] == "POST":
                            destination = trial.impl.mutate(step[1], step[2])
                            self.assertIn(destination, trial.paths, step)

    def test_requests_state_the_grader_contract(self):
        # taskset-v1.1: the request must ask for what Hours/Overlap grade (two links; titles only).
        # taskset-v2 (#8): Hours grades the whole interval, so the request and memo field say 운영 시간(시작–종료).
        requests = {t["id"]: t["request"] for t in catalog()["tasks"]}
        self.assertIn("시설 안내와 운영 공지 링크를 모두", requests["pb-research-02"])
        self.assertIn("실제 운영 시간(시작–종료)", requests["pb-research-02"])
        self.assertNotIn("개장 시간", requests["pb-research-02"])
        self.assertEqual(Hours.note_fields, ("운영 시간", "근거 링크"))
        self.assertIn("제목만", requests["pb-account-03"])

    def test_hours_grader_still_needs_the_whole_interval(self):
        task = next(t for t in new_tasks() if t["fixture"] == "hours")
        for variant in range(3):
            for note_time, success in (("opening", False), ("interval", True)):
                with self.subTest(variant=variant, note=note_time), PersonalServer(task, variant) as server:
                    server.begin("kitsune")
                    trial = server.trials[server.by_target["kitsune"]]
                    note = dict(trial.impl.expected)
                    if note_time == "opening":
                        note["운영 시간"] = Hours.EXCEPTION[variant][0]
                    perform(session(trial), trial, [s for s in trial.impl.solution() if s[0] == "GET"] + [("POST", "/note", note)])
                    self.assertEqual(trial.evaluate(VALID, solved_evidence(trial))["task_success"], success)

    def test_normalizers(self):
        self.assertTrue(time_in("2027-06-18 15:00", "15:00"))
        self.assertTrue(time_in("2027-06-18 (금) 15:00", "15:00"))
        self.assertTrue(time_in("09:30", "09:30"))
        self.assertTrue(time_in("9시 반", "09:30"))
        self.assertFalse(time_in("19:30", "09:30"))
        self.assertTrue(time_in("13:00–18:00", "18:00"))
        self.assertTrue(time_in("오후 3시", "15:00"))
        self.assertTrue(time_in("15:30 ~ 16:30", "15:30"))
        self.assertFalse(time_in("15:00", "05:00"))
        self.assertFalse(time_in("15시 30분", "15:00"))
        self.assertTrue(time_in("19시 30분", "19:30"))
        self.assertTrue(date_in("6월 3일", "2027-06-03"))
        self.assertTrue(has("만 19세~34세", "19", "34"))
        self.assertTrue(has("연소득 4,000만원 이하", ("4천만", "4,000만")))


def seed_natively(test, task, target, upstream):
    with PersonalServer(task, 0) as server, tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as folder:
        server.begin(target)
        trial = server.trials[server.by_target[target]]
        session = NativeSession({"target": target, "upstream": upstream(folder), "bootstrap_url": trial.url("/start"),
            "urls": [trial.url(p) for p in trial.paths], "active_index": trial.active_index,
            "evidence_path": folder + "/evidence.json", "origin": server.origin})
        try:
            session.start()
            session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "personal-fixture-test", "version": "1"}})
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.prepare()
            evaluation = trial.evaluate(VALID, session.evidence)
            test.assertTrue(evaluation["scorable"], evaluation)
            test.assertTrue(evaluation["initial_state_verified"])
            test.assertFalse(evaluation["task_success"])
        finally:
            session.close()


@unittest.skipUnless(os.environ.get("PERSONAL_BROWSER_TEST") == "1", "opt-in native Firefox MCP test; no model calls")
class NativePlaywrightSeedTests(unittest.TestCase):
    def test_new_fixtures_seed_via_real_playwright(self):
        cli = str(ROOT / "node_modules/@playwright/mcp/cli.js")
        for task in new_tasks():
            with self.subTest(task=task["id"]), tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as sockets, \
                    patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": str(ROOT / "artifacts/browsers"),
                                            "PLAYWRIGHT_SKIP_BROWSER_GC": "1", "PWTEST_SOCKETS_DIR": sockets}):
                seed_natively(self, task, "playwright",
                              lambda folder: ["node", cli, "--browser", "firefox", "--isolated", "--headless"])


@unittest.skipUnless(os.environ.get("PERSONAL_KITSUNE_TEST") == "1", "opt-in isolated Kitsune/Firefox MCP test; no model calls")
class NativeKitsuneSeedTests(unittest.TestCase):
    def test_new_fixtures_seed_via_real_kitsune(self):
        from test_personal import isolated_kitsune
        for task in new_tasks():
            with self.subTest(task=task["id"]), tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as folder, \
                    isolated_kitsune(folder) as upstream:
                seed_natively(self, task, "kitsune", lambda _: upstream)


if __name__ == "__main__":
    unittest.main()
