"""Taskset-v3 contract tests: deterministic state, not model answers."""
import copy
from http.cookiejar import CookieJar
import hashlib
import json
import os
import sys
import time
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from kitsune_benchmark.personal import (CSP, LATER_CATEGORIES, PersonalServer, PersonalTrial, aggregate_results, catalog,
                                        config, run_personal)
from kitsune_benchmark.personal_fixtures import LongPage
from kitsune_benchmark.cost_metrics import observation_volume
from kitsune_benchmark.coexistence import run_coexistence
from kitsune_benchmark.gallery import config as gallery_config, run_gallery
from kitsune_benchmark.personal_session import NativeSession
from kitsune_benchmark.smoke import ROOT
from kitsune_benchmark.viewport import (CONTENT_HEIGHT, CONTENT_WIDTH, FIREFOX_CHROME_HEIGHT, REPORT_PATH,
                                        observed_viewport, parse_report, report_script, viewport_record)

# Every page (status, CSP header, body with the trial base URL as BASE) served for the 24
# taskset-v2 tasks x 3 variants, as produced by the taskset-v2 tag (39b58c3).
V2_PAGES_SHA256 = "c6aec2d5687674605ec1065a58e2ffbdac3c6f87407b7ab0da0955f7aa99156b"
REPORT = {"innerWidth": "1280", "innerHeight": "720", "outerWidth": "1280", "outerHeight": "805", "devicePixelRatio": "1"}


def client(trial):
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
    opener.open(trial.url("/start")).close()
    return opener


def post(opener, trial, path, values):
    try:
        with opener.open(Request(trial.url(path), data=urlencode(values).encode())) as response:
            return response.status
    except HTTPError as error:
        return error.code


class TasksetV3Tests(unittest.TestCase):
    def tasks(self):
        return [t for t in catalog()["tasks"] if t["category"] == "long_page_lookup"]

    def trial(self, task, variant):
        return PersonalTrial(task, variant, "fixed", "http://local/t/fixed")

    def test_version_ids_agree_and_gallery_stays_v2(self):
        # taskset-v4 adds two families and keeps every v3 contract below (tests/test_taskset_v4.py).
        self.assertEqual(config()["id"], "personal-browsing-local-v4")
        self.assertEqual(catalog()["suite"], config()["id"])
        self.assertEqual(gallery_config()["id"], "component-gallery-v2")
        self.assertEqual(len(self.tasks()), 4)

    def test_long_pages_are_deterministic_deep_and_have_near_misses(self):
        for task in self.tasks():
            variants = []
            for v in range(3):
                with self.subTest(task=task["id"], variant=v):
                    trial = self.trial(task, v)
                    fixture = trial.impl
                    self.assertIsInstance(fixture, LongPage)
                    page = fixture.pages()["/directory"][1]
                    self.assertEqual(page, self.trial(task, v).impl.pages()["/directory"][1])
                    self.assertEqual(page.count("<section>"), 180)
                    self.assertGreater(len(page), 35000)
                    answer_pos = page.index(next(iter(fixture.expected.values())))
                    self.assertGreater(answer_pos, len(page) * .8)
                    for value in fixture.distractor.values():
                        self.assertIn(value, page[:answer_pos])
                    variants.append((page, fixture.expected))
            self.assertEqual(len({json.dumps(v, ensure_ascii=False) for v in variants}), 3)

    def test_each_grader_checks_saved_state_correct_distractor_and_wrong(self):
        for task in self.tasks():
            for v in range(3):
                trial = self.trial(task, v)
                fixture = trial.impl
                tabs = [{"id": i, "url": trial.url(p), "active": i == 0} for i, p in enumerate(trial.paths)]
                evidence = {"setup_complete": True, "initial_tabs": tabs, "snapshots": [copy.deepcopy(tabs)], "tab_calls": []}
                for note, expected in ((fixture.expected, True), (fixture.distractor, False),
                                       ({k: "wrong" for k in fixture.note_fields}, False)):
                    with self.subTest(task=task["id"], variant=v, note=note):
                        trial.mutate("/note", note)
                        result = trial.evaluate({"execution_status": "completed_unscored", "final_message": fixture.expected}, evidence)
                        self.assertEqual(result["task_success"], expected)
                        self.assertEqual(result["benchmark"], config()["id"])
                        self.assertEqual(result["primary_contract"], "v2_agent_tab_cleanup")
                # Every individual field is required, and extra facts cannot smuggle the right value in.
                for field in fixture.note_fields:
                    for value in ("", fixture.distractor[field], fixture.expected[field] + " extra"):
                        fixture.mutate("/note", dict(fixture.expected, **{field: value}))
                        self.assertFalse(fixture.correct({}))
                fixture.mutate("/note", {k: " " + v + " " for k, v in fixture.expected.items()})
                self.assertTrue(fixture.correct({}))
                self.assertEqual(self.trial(task, v).impl.saved_state(), {k: "" for k in fixture.note_fields})

    def test_requests_state_exactly_the_note_fields_and_lookup_filters(self):
        for task in self.tasks():
            fixture = self.trial(task, 0).impl
            for field in fixture.note_fields:
                self.assertIn(field, task["request"])
            for phrase in ("조회 조건이 모두 일치", "현행", "같은 이름 칸", "값만 그대로 복사", "폐지", "다른 구역"):
                self.assertIn(phrase, task["request"])
            self.assertEqual(set(fixture.expected), set(fixture.note_fields))

    def test_v2_task_pages_stay_byte_identical(self):
        """Uninstrumented, and in v3 runs apart from the report script and its CSP, the 24 tasks serve taskset-v2's pages."""
        pages = {False: [], True: []}
        for task in catalog()["tasks"]:
            if task["category"] in LATER_CATEGORIES:
                continue
            for variant in range(3):
                with PersonalServer(task, variant) as server:
                    for report_viewport, target in ((False, "playwright"), (True, "kitsune")):
                        server.report_viewport = report_viewport
                        server.begin(target)
                        trial = server.trials[server.by_target[target]]
                        script, digest = report_script(trial.url(REPORT_PATH))
                        opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
                        for path in ["/start", *trial.paths]:
                            with opener.open(trial.url(path)) as response:
                                body, csp = response.read().decode(), response.headers["Content-Security-Policy"]
                            if report_viewport:
                                self.assertEqual(body.count("<script"), 1)
                                self.assertLess(body.index(f"<script>{script}</script>"), body.index("<body>"))
                                self.assertEqual(csp, f"default-src 'none'; script-src {digest}; connect-src 'self'; "
                                                      "form-action 'self'; base-uri 'none'")
                                body, csp = body.replace(f"<script>{script}</script>", ""), CSP
                            pages[report_viewport].append([task["id"], variant, path, response.status, csp,
                                                           body.replace(trial.base, "BASE")])
                        visits = list(trial.visits)
                        if report_viewport:
                            # Reports from the original tasks are recorded, never as visits, writes or forbidden actions.
                            self.assertEqual(post(opener, trial, REPORT_PATH, REPORT), 204)
                            self.assertEqual(server.viewport_reports(target), [parse_report(REPORT)])
                        else:
                            # Without reporting no endpoint exists: same 400 as any unknown write, nothing recorded.
                            self.assertEqual(post(opener, trial, REPORT_PATH, REPORT), 400)
                            self.assertEqual(trial.viewport_reports, [])
                            self.assertIsNone(server.viewport_reports(target))
                        self.assertEqual((trial.visits, trial.mutations, trial.forbidden), (visits, [], []))
        for served in pages.values():
            self.assertEqual(len(served), 303)
            self.assertEqual(hashlib.sha256(json.dumps(served, ensure_ascii=False).encode()).hexdigest(), V2_PAGES_SHA256)

    def test_long_pages_report_viewport_invisibly(self):
        task = self.tasks()[0]
        with PersonalServer(task, 0, report_viewport=True) as server:
            server.begin("kitsune")
            trial = server.trials[server.by_target["kitsune"]]
            self.assertEqual(server.viewport_reports("kitsune"), [])
            opener = client(trial)
            for path in trial.paths:
                with opener.open(trial.url(path)) as response:
                    html, csp = response.read().decode(), response.headers["Content-Security-Policy"]
                script, digest = report_script(trial.url(REPORT_PATH))
                # The only change: one inline script in <head> (before <body>), allowed by its hash alone.
                self.assertEqual(html.count("<script"), 1)
                self.assertLess(html.index(f"<script>{script}</script>"), html.index("<body>"))
                self.assertEqual(csp, f"default-src 'none'; script-src {digest}; connect-src 'self'; "
                                      "form-action 'self'; base-uri 'none'")
                title, body = trial.render(path)
                self.assertEqual(html.replace(f"<script>{script}</script>", ""),
                                 f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>{title}</title>'
                                 f'<body><h1>{title}</h1>{body}</body></html>')
            visits = list(trial.visits)
            self.assertEqual(post(opener, trial, REPORT_PATH, REPORT), 204)
            self.assertEqual(post(opener, trial, REPORT_PATH, dict(REPORT, innerHeight="635")), 204)
            for bad in (dict(REPORT, innerWidth="wide"), {**REPORT, "extra": "1"}):
                self.assertEqual(post(opener, trial, REPORT_PATH, bad), 400)
            self.assertEqual(server.viewport_reports("kitsune"), [
                {"innerWidth": 1280, "innerHeight": 720, "outerWidth": 1280, "outerHeight": 805, "devicePixelRatio": 1},
                {"innerWidth": 1280, "innerHeight": 635, "outerWidth": 1280, "outerHeight": 805, "devicePixelRatio": 1}])
            # Reports are excluded from visits, writes and forbidden actions; grading is unchanged.
            self.assertEqual((trial.visits, trial.mutations, trial.forbidden), (visits, [], []))
            tabs = [{"id": i, "url": trial.url(p), "active": i == 0} for i, p in enumerate(trial.paths)]
            evaluation = trial.evaluate({"execution_status": "completed_unscored"},
                                        {"setup_complete": True, "initial_tabs": tabs, "snapshots": [tabs], "tab_calls": []})
            self.assertEqual(evaluation["forbidden_actions"], [])
            self.assertEqual(evaluation["saved_state"], {k: "" for k in trial.impl.note_fields})
            self.assertTrue(evaluation["safety_pass"])
            self.assertFalse(evaluation["task_success"])

    def test_personal_runs_record_reports_and_equalize_kitsune(self):
        # Every v3 personal run reports, the default pilot (original tasks) included.
        for task_ids in (None, [self.tasks()[0]["id"]]):
            with self.subTest(task_ids=task_ids), tempfile.TemporaryDirectory() as directory:
                pair = {"pair_dir": directory, "results": {}}
                with patch("kitsune_benchmark.personal.run_pair", return_value=pair) as run_pair, \
                        patch("kitsune_benchmark.personal.source_revision", return_value={}):
                    run_personal(execute=True, task_ids=task_ids, targets=("playwright",))
                kwargs = run_pair.call_args.kwargs
                self.assertEqual(kwargs["experiment_spec"]["selected_task"]["id"],
                                 (task_ids or config()["pilot_tasks"])[0])
                self.assertTrue(kwargs["equalize_kitsune_viewport"])
                self.assertEqual(kwargs["viewport_reports"].__func__, PersonalServer.viewport_reports)
                self.assertTrue(kwargs["viewport_reports"].__self__.report_viewport)

    def test_gallery_and_coexistence_equalize_kitsune(self):
        # gallery imports run_pair/source_revision from smoke at call time; coexistence at module load.
        for module, run, task in (("smoke", run_gallery, "ui-table"), ("coexistence", run_coexistence, "pb-current-01")):
            with self.subTest(track=run.__name__), tempfile.TemporaryDirectory() as directory:
                pair = {"pair_dir": directory, "results": {}}
                with patch(f"kitsune_benchmark.{module}.run_pair", return_value=pair) as run_pair, \
                        patch(f"kitsune_benchmark.{module}.source_revision", return_value={}):
                    run(execute=True, task_ids=[task], targets=("playwright",))
                self.assertTrue(run_pair.call_args.kwargs["equalize_kitsune_viewport"])

    def test_personal_summary_surfaces_long_page_success_tokens_and_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            run = {"benchmark_evaluation": {"scorable": True, "task_success": True},
                   "usage": {"input_tokens": 100}, "observation_volume": {"response_text_chars": 30,
                       "response_text_bytes": 60, "serialized_response_bytes": 90}}
            pair = {"pair_dir": directory, "results": {"playwright": run}}
            with patch("kitsune_benchmark.personal.run_pair", return_value=pair), \
                    patch("kitsune_benchmark.personal.source_revision", return_value={}):
                summary = run_personal(execute=True, task_ids=[self.tasks()[0]["id"]], targets=("playwright",))
            saved = json.loads((Path(directory) / "suite-summary.json").read_text())
            category = saved["by_category"]["long_page_lookup"]["playwright"]
            self.assertEqual(category["successes"], 1)
            self.assertEqual(category["reported_usage_all_runs"]["input_tokens"], 100)
            volume = category["cost_metrics"]["all_attempts"]["observation_volume"]
            self.assertEqual(volume["response_text_bytes"]["total"], 60)
            self.assertEqual(summary["by_category"], saved["by_category"])

    def test_observation_volume_reuses_agent_counters_and_tracks_coverage(self):
        agent = {"kind": "rpc_completed", "role": "agent", "method": "tools/call",
                 "response_text_chars": 10, "response_text_bytes": 20, "serialized_response_bytes": 40}
        volume = observation_volume([agent, dict(agent, role="harness"), dict(agent, method="tools/list")])
        self.assertEqual(volume, {"response_text_chars": 10, "response_text_bytes": 20, "serialized_response_bytes": 40})
        run = {"benchmark_evaluation": {"scorable": True, "task_success": True},
               "observation_volume": volume, "usage": {"input_tokens": 100}}
        pairs = [{"results": {"playwright": run}}, {"results": {"playwright": {}}}]
        totals = aggregate_results(pairs)["playwright"]
        measured = totals["cost_metrics"]["all_attempts"]["observation_volume"]
        self.assertEqual(measured["response_text_chars"], {"total": 10, "reported_runs": 1, "missing_runs": 1})
        self.assertEqual(totals["reported_usage_all_runs"]["input_tokens"], 100)
        self.assertEqual(totals["successes"], 1)
        self.assertTrue(all(v is None for v in observation_volume([]).values()))
        self.assertIsNone(observation_volume([{k: v for k, v in agent.items() if k != "response_text_bytes"}])["response_text_bytes"])


def native_tasks():
    """The default pilot's first (original-family) task and the first long-page task."""
    return [next(t for t in catalog()["tasks"] if t["id"] == config()["pilot_tasks"][0]),
            next(t for t in catalog()["tasks"] if t["category"] == "long_page_lookup")]


def native_viewport(test, target, upstream, record, task):
    """Seed a v3 task with the harness's own tools, then read the pages' reports; no model calls."""
    with PersonalServer(task, 0, report_viewport=True) as server, tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as folder:
        server.begin(target)
        trial = server.trials[server.by_target[target]]
        title = trial.render(trial.paths[trial.active_index])[0]
        session = NativeSession({"target": target, "upstream": upstream(folder), "bootstrap_url": trial.url("/start"),
            "urls": [trial.url(p) for p in trial.paths], "active_index": trial.active_index,
            "evidence_path": folder + "/evidence.json", "origin": server.origin})
        try:
            session.start()
            session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "viewport-test", "version": "1"}})
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.prepare()
            deadline = time.monotonic() + 10
            while len(server.viewport_reports(target)) < 1 + len(trial.paths) and time.monotonic() < deadline:
                time.sleep(0.1)
            snapshot = "\n".join(i.get("text", "") for i in session.tool("browser_snapshot", {})["content"])
            test.assertIn(title, snapshot)
            for marker in ("sendBeacon", "viewport-report", "innerWidth", "devicePixelRatio"):
                test.assertNotIn(marker, snapshot)
            evaluation = trial.evaluate({"execution_status": "completed_unscored"}, session.evidence)
            test.assertTrue(evaluation["scorable"] and evaluation["initial_state_verified"], evaluation)
            test.assertEqual((evaluation["forbidden_actions"], trial.mutations), ([], []))
            test.assertNotIn(REPORT_PATH, trial.visits)
            reports = server.viewport_reports(target)
            test.assertGreaterEqual(len(reports), 1 + len(trial.paths))
            observed = observed_viewport(record, reports)
            print(f"\n{target} {task['id']} configured={observed['configured']} effective={observed['effective']}",
                  file=sys.stderr)
            return observed
        finally:
            session.close()


@unittest.skipUnless(os.environ.get("PERSONAL_BROWSER_TEST") == "1", "opt-in native Firefox MCP test; no model calls")
class NativePlaywrightViewportTests(unittest.TestCase):
    def test_playwright_content_viewport_is_reported_invisibly(self):
        args = ("--browser", "firefox", "--isolated", "--headless", "--viewport-size", f"{CONTENT_WIDTH}x{CONTENT_HEIGHT}")
        cli = str(ROOT / "node_modules/@playwright/mcp/cli.js")
        with tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as sockets, \
                patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": str(ROOT / "artifacts/browsers"),
                                        "PLAYWRIGHT_SKIP_BROWSER_GC": "1", "PWTEST_SOCKETS_DIR": sockets}):
            for task in native_tasks():
                with self.subTest(task=task["id"]):
                    observed = native_viewport(self, "playwright", lambda _: ["node", cli, *args],
                                               viewport_record("playwright", (cli, *args)), task)
                    self.assertTrue(observed["content_viewport_equality_asserted"], observed)


@unittest.skipUnless(os.environ.get("PERSONAL_KITSUNE_TEST") == "1", "opt-in isolated Kitsune/Firefox MCP test; no model calls")
class NativeKitsuneViewportTests(unittest.TestCase):
    def test_kitsune_window_is_equalized_to_the_content_viewport(self):
        from test_personal import isolated_kitsune
        pilot, long_page = native_tasks()
        for equalized, task in ((False, long_page), (True, long_page), (True, pilot)):
            height = CONTENT_HEIGHT + (FIREFOX_CHROME_HEIGHT if equalized else 0)
            record = viewport_record("kitsune", (), ("-headless", f"--width={CONTENT_WIDTH}", f"--height={height}"),
                                     equalized=equalized)
            with self.subTest(height=height, task=task["id"]), tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as folder, \
                    isolated_kitsune(folder, height) as upstream:
                observed = native_viewport(self, "kitsune", lambda _: upstream, record, task)
                self.assertEqual(observed["effective"]["innerWidth"], CONTENT_WIDTH)
                self.assertEqual(observed["content_viewport_equality_asserted"], equalized, observed)
