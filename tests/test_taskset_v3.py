"""Taskset-v3 contract tests: deterministic state, not model answers."""
import copy
import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from kitsune_benchmark.personal import PersonalTrial, aggregate_results, catalog, config, run_personal
from kitsune_benchmark.personal_fixtures import LongPage
from kitsune_benchmark.cost_metrics import observation_volume
from kitsune_benchmark.gallery import config as gallery_config


class TasksetV3Tests(unittest.TestCase):
    def tasks(self):
        return [t for t in catalog()["tasks"] if t["category"] == "long_page_lookup"]

    def trial(self, task, variant):
        return PersonalTrial(task, variant, "fixed", "http://local/t/fixed")

    def test_version_ids_agree_and_gallery_stays_v2(self):
        self.assertEqual(config()["id"], "personal-browsing-local-v3")
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
