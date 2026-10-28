import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from unittest.mock import patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.adapter import settings
from kitsune_benchmark.audit import audit_events
from kitsune_benchmark.external import LiveTask, aggregate, catalog, run_external, selected_tasks
from kitsune_benchmark.miniwob import BenchmarkServer, Trial, UI_TOOLS, bootstrap, config
from kitsune_benchmark.specs import Server


def event(kind="end", raw=1, reward=0.9):
    return {"kind": kind, "task_id": "click-test-2", "seed": 42,
            "timer_budget_ms": 120000, "done": True, "raw_reward": raw, "reward": reward}


class MiniwobTests(unittest.TestCase):
    def test_official_reward_not_agent_answer_is_the_success_label(self):
        for raw, success in ((1, True), (-1, False), (0, False), (0.6, False)):
            with self.subTest(raw=raw):
                trial = Trial("click-test-2", 42, 120000, page_loads=1)
                self.assertTrue(trial.event(event("start")))
                self.assertTrue(trial.event(event(raw=raw)))
                result = trial.evaluate("completed_unscored")
                self.assertTrue(result["scorable"])
                self.assertEqual(result["task_success"], success)
                self.assertEqual(result["positive_reward"], raw > 0)
                self.assertIsNone(trial.evaluate("invalid_trace")["task_success"])

    def test_restart_reload_bad_reward_and_modified_timer_are_not_scorable(self):
        for mutation in ({"seed": 43}, {"timer_budget_ms": 500000},
                         {"raw_reward": float("nan")}, {"raw_reward": True},
                         {"reward": 2}, {"done": False}):
            trial = Trial("click-test-2", 42, 120000, page_loads=1)
            trial.event(event("start"))
            self.assertFalse(trial.event({**event(), **mutation}))
            self.assertFalse(trial.evaluate("completed_unscored")["scorable"])
        trial = Trial("click-test-2", 42, 120000, page_loads=1)
        trial.event(event("start")); trial.event(event("start")); trial.event(event())
        self.assertFalse(trial.evaluate("completed_unscored")["scorable"])
        trial = Trial("click-test-2", 42, 120000, page_loads=2, starts=1)
        self.assertFalse(trial.evaluate("completed_unscored")["scorable"])

    def test_ui_track_hides_code_and_reward_manipulation_surfaces(self):
        for tools in UI_TOOLS.values():
            self.assertFalse(set(tools) & {"browser_js", "browser_evaluate", "browser_run_code",
                                          "browser_parallel", "browser_batch", "browser_workflow"})
        server = Server("x", "mcp", (), enabled_tools=("browser_click",))
        self.assertEqual(settings(server)["mcp_servers"]["browser"]["enabled_tools"], ("browser_click",))

    def test_http_instrumentation_and_reward_route(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            directory = source / "miniwob/html/miniwob"
            directory.mkdir(parents=True)
            original = "<html><body>Original upstream task</body></html>"
            path = directory / "click-test-2.html"
            path.write_text(original)
            spec = config()
            task = {"id": "mw-click-test-2", "kind": "miniwob", "task_id": "click-test-2", "seed": 42}
            with BenchmarkServer(source, spec, task) as server:
                task = server.begin("playwright")
                url = re.search(r"http://\S+", task.prompt).group()
                opener = build_opener(ProxyHandler({}))
                with opener.open(url, timeout=2) as response:
                    page = response.read().decode()
                self.assertIn("Original upstream task", page)
                self.assertIn("core.endEpisode", page)
                self.assertIn("Math.seedrandom", page)
                self.assertEqual(path.read_text(), original)
                parsed = urlsplit(url); token = parse_qs(parsed.query)["trial"][0]
                endpoint = f"http://{parsed.netloc}/__bench/{token}/event"
                for payload in (event("start"), event()):
                    with opener.open(Request(endpoint, data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"}), timeout=2) as response:
                        self.assertEqual(response.status, 204)
                outcome = server.evaluate("playwright", {"execution_status": "completed_unscored"})
                self.assertTrue(outcome["task_success"])
                with self.assertRaises(HTTPError):
                    opener.open(Request(endpoint, data=b'null'), timeout=2)

    def test_external_default_does_not_start_processes(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no processes in plan")):
            result = run_external()
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["config"]["model"], "gpt-6-luna")
        self.assertEqual(result["planned_model_runs"], 20)
        for argv in (["external"], ["benchmark"], ["external", "--kind", "live"],
                     ["external", "--task", "mw-login-user"]):
            with patch("subprocess.Popen", side_effect=AssertionError("no model")), redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)

    def test_catalog_is_seven_pinned_miniwob_plus_three_live(self):
        tasks = catalog()["tasks"]
        self.assertEqual(catalog()["suite"], config()["id"])
        self.assertEqual([t["kind"] for t in tasks].count("miniwob"), 7)
        self.assertEqual([t["kind"] for t in tasks].count("live"), 3)
        self.assertEqual(len({t["id"] for t in tasks}), 10)
        self.assertEqual(len(selected_tasks()), 10)  # loads and id-checks every live task file
        self.assertEqual([t["id"] for t in selected_tasks(kind="live")],
                         [t["id"] for t in tasks if t["kind"] == "live"])
        for bad in (["nope"], ["mw-login-user", "mw-login-user"]):
            with self.assertRaises(ValueError):
                selected_tasks(bad)
        with self.assertRaises(ValueError):
            selected_tasks(["mw-login-user"], kind="live")
        source = Path(__file__).resolve().parents[1] / config()["source_directory"] / "miniwob/html/miniwob"
        if source.is_dir():
            for task in tasks:
                if task["kind"] == "miniwob":
                    self.assertTrue((source / (task["task_id"] + ".html")).is_file(), task["task_id"])

    def test_live_tasks_are_recorded_never_graded(self):
        live = next(t for t in catalog()["tasks"] if t.get("advisory_answer_regex") and "wikipedia" in t["id"])
        fixture = LiveTask(live)
        self.assertEqual(fixture.begin("kitsune").id, live["id"])
        with tempfile.TemporaryDirectory() as folder:
            for text, status, match, scorable in (
                    ("Release: November 9, 2004", "completed_unscored", True, True),
                    ("It was released in 2002.", "completed_unscored", False, True),
                    ("9 November 2004", "timeout", None, False)):
                with self.subTest(text=text, status=status):
                    (Path(folder) / "final.txt").write_text(text)
                    result = fixture.evaluate("kitsune", {"execution_status": status, "run_dir": folder})
                    self.assertIsNone(result["task_success"])
                    self.assertFalse(result["graded"])
                    self.assertEqual(result["scorable"], scorable)
                    self.assertEqual(result["advisory_answer_match"], match)

    def test_aggregate_keeps_miniwob_and_live_apart(self):
        def run(evaluation):
            return {"benchmark_evaluation": evaluation, "mcp_calls": 3, "elapsed_sec": 1.0}
        pairs = [{"external_kind": "miniwob", "results": {"kitsune": run(
                     {"scorable": True, "task_success": False, "positive_reward": True})}},
                 {"external_kind": "live", "results": {"kitsune": run(
                     {"scorable": True, "task_success": None, "advisory_answer_match": True})}}]
        totals = aggregate(pairs)["kitsune"]
        self.assertEqual(totals["miniwob"]["successes"], 0)
        self.assertEqual(totals["miniwob"]["positive_reward"], 1)
        self.assertEqual(totals["live"]["advisory_answer_matches"], 1)
        self.assertNotIn("successes", totals["live"])

    def test_audit_catches_code_tool_or_javascript_navigation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.jsonl"
            for tool, args in (("browser_js", {}), ("browser_navigate", {"url": "javascript:core.endEpisode(1)"})):
                path.write_text(json.dumps({"type": "item.completed", "item": {
                    "id": "call", "type": "mcp_tool_call", "server": "browser", "tool": tool,
                    "status": "completed", "arguments": args}}))
                result = audit_events(path, allowed_tools=("browser_navigate", "browser_click"))
                self.assertTrue(result["violations"])


if __name__ == "__main__":
    unittest.main()
