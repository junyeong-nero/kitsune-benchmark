"""Full-native track (#109): plan, wiring, Kitsune-only arms and offline analysis, with fakes. No model or browser."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.full_native import (ARMS, BENCHMARK, analyze, agent_calls, main as analyze_main,
                                           run_full_native, run_metrics, schedule, select_units, units)
from kitsune_benchmark.full_native_session import FullNativeSession
from kitsune_benchmark.specs import Server


def tool_use(call_id, name, arguments):
    return {"type": "assistant", "message": {"id": "m-" + call_id, "content": [
        {"type": "tool_use", "id": call_id, "name": "mcp__browser__" + name, "input": arguments}]}}


def tool_result(call_id, text, error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": call_id, "is_error": error, "content": [{"type": "text", "text": text}]}]}}


GATEWAY_EVENTS = [
    tool_use("1", "browser_tools_search", {"query": "batch"}),
    tool_result("1", '{"tools": [{"name": "browser_batch"}]}'),
    tool_use("2", "browser_tools_call", {"name": "browser_batch", "arguments": {"commands": [
        {"action": "navigate", "url": "http://127.0.0.1/a"}, {"action": "pageText"}, {"action": "cookies"}]}}),
    tool_result("2", '{"results": [{"ok": true}, {"ok": true}, {"error": "cookies needs the storage capability", '
                     '"code": "capability_restricted"}]}'),
    tool_use("3", "browser_tools_call", {"name": "browser_page_text", "arguments": {}}),
    tool_result("3", "page text"),
    tool_use("4", "browser_parallel", {"sequences": [[{"action": "pageText"}], [{"action": "pageText"}, {"action": "x"}]]}),
    tool_result("4", '{"error": "browser_parallel is not published by this MCP server", "code": "tool_not_published"}',
                error=True),
]
CORE_EVENTS = [tool_use("1", "browser_snapshot", {}), tool_result("1", "snapshot"),
               tool_use("2", "browser_click", {"ref": "e1"}), tool_result("2", "clicked")]


def fake_pair(root: Path, name: str, events: list, *, success=True, input_tokens=100, calls=None, requests=3,
              published=("browser_click", "browser_snapshot")) -> dict:
    pair_dir = root / name
    run_dir = pair_dir / "runs" / "kitsune"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    (pair_dir / "kitsune-native-metadata.json").write_text(json.dumps(
        {"enabled_tools": [], "tools_pages": [{"tools": [{"name": n} for n in published]}]}))
    result = {"run_dir": str(run_dir), "execution_status": "completed_unscored",
              "usage": {"input_tokens": input_tokens, "cached_input_tokens": input_tokens // 2, "output_tokens": 5},
              "mcp_calls": len(events) // 2 if calls is None else calls, "nonexistent_tool_calls": 0,
              "token_attribution": {"requests": requests},
              "benchmark_evaluation": {"scorable": True, "task_success": success, "functional_success": success,
                                       "safety_pass": True}}
    return {"pair_dir": str(pair_dir), "results": {"kitsune": result}}


class FullNativePlanTests(unittest.TestCase):
    def test_units_reuse_existing_tasks_and_both_gallery_layouts(self):
        rows = units()
        personal = [r["task"] for r in rows if r["track"] == "personal"]
        self.assertEqual(personal, [f"pb-research-0{i}" for i in range(1, 5)] + [f"pb-handoff-0{i}" for i in range(1, 5)]
                         + [f"pb-longpage-0{i}" for i in range(1, 5)])
        self.assertEqual([r["unit"] for r in rows if r["track"] == "gallery"], ["ui-table/crowded", "ui-table/isolated"])
        self.assertEqual(ARMS, {"core": {"KITSUNE_CAPS": "core"},
                                "gateway": {"KITSUNE_CAPS": "all", "KITSUNE_PUBLISH": "core"}})

    def test_schedule_runs_both_arms_per_unit_and_alternates_the_first(self):
        plan = schedule(select_units(["pb-research-01", "pb-longpage-02", "ui-table/isolated"]))
        self.assertEqual([(p["unit"], p["arm"], p["position"]) for p in plan], [
            ("pb-research-01", "core", 0), ("pb-research-01", "gateway", 1),
            ("pb-longpage-02", "gateway", 0), ("pb-longpage-02", "core", 1),
            ("ui-table/isolated", "core", 0), ("ui-table/isolated", "gateway", 1)])
        for bad in (["pb-current-01"], ["pb-research-01", "pb-research-01"], [], ["ui-table"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                select_units(bad)

    def test_plan_only_never_starts_a_run(self):
        with patch("kitsune_benchmark.full_native.run_pair", side_effect=AssertionError("inference")):
            plan = run_full_native()
        self.assertEqual((plan["mode"], plan["model_invoked"], plan["planned_model_runs"]), ("full_native_plan_only", False, 28))
        self.assertEqual(plan["targets"], ["kitsune"])
        self.assertEqual(plan["tool_policy"], "no_benchmark_allowlist")
        api = run_full_native(harness="claude-api", budget_usd=5)
        self.assertEqual(api["worst_case_usd"], 28 * api["max_budget_usd_per_run"])
        with self.assertRaises(ValueError):
            run_full_native(budget_usd=5)  # the subscription harness has no dollar cap
        with self.assertRaises(ValueError):
            run_full_native(variant=3)

    def test_cli_plan_and_input_errors(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["full-native", "--unit", "ui-table/crowded"]), 0)
        self.assertEqual(json.loads(out.getvalue())["planned_model_runs"], 2)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["full-native", "--unit", "pb-current-01"]), 2)
        with redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            main(["full-native", "--harness", "claude-api", "--execute"])  # API billing needs --allow-api-billing


class FullNativeExecutionTests(unittest.TestCase):
    def test_each_arm_is_a_kitsune_only_run_without_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root, calls = Path(folder), []
            def run_pair(**kwargs):
                calls.append(kwargs)
                target = kwargs["targets"][0]
                task = kwargs["task_for_target"](target)
                wrapped = kwargs["prepare_server"](target, Server(target, "uv", ("kitsune",)), task, root)
                session = json.loads(Path(wrapped.args[-1]).read_text())
                calls[-1]["session"] = session
                calls[-1]["relay"] = Path(wrapped.args[0]).name
                (root / (target + "-session.json")).unlink()
                arm = kwargs["experiment_spec"]["full_native"]["arm"]
                return fake_pair(root, f"{len(calls)}-{arm}", GATEWAY_EVENTS if arm == "gateway" else CORE_EVENTS)
            out = io.StringIO()
            with patch("kitsune_benchmark.full_native.run_pair", side_effect=run_pair), \
                    patch("kitsune_benchmark.full_native.source_revision", return_value={"revision": "abc", "dirty": False}), \
                    redirect_stdout(out):
                code = main(["full-native", "--unit", "pb-handoff-01", "--unit", "ui-table/crowded", "--execute"])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual([c["kitsune_env"] for c in calls], [ARMS["core"], ARMS["gateway"], ARMS["gateway"], ARMS["core"]])
            for call in calls:
                self.assertEqual(call["targets"], ("kitsune",))
                self.assertIsNone(call["enabled_tools"])
                self.assertEqual(call["artifact_scope"], "full-native")
                self.assertTrue(call["equalize_kitsune_viewport"])
                self.assertEqual(call["session"]["enabled_tools"], [])
                self.assertEqual(call["relay"], "full_native_session.py", "the frozen personal relay is not changed")
                self.assertEqual(call["experiment_spec"]["full_native"]["tool_policy"], "no_benchmark_allowlist")
            self.assertEqual(calls[0]["session"]["seeding"], "user_channel")  # personal units seed as the personal track
            self.assertEqual(calls[2]["session"]["task_tab"], "agent")  # gallery units as the gallery track
            self.assertEqual(calls[2]["experiment_spec"]["timeout_sec"], 240)
            self.assertEqual((result["requested_runs"], result["completed_runs"], result["stopped_reason"]), (4, 4, None))
            stored = json.loads(Path(result["suite_summary_path"]).read_text())
            self.assertEqual(stored["benchmark"], BENCHMARK)
            arms = stored["analysis"]["arms"]
            self.assertEqual(arms["gateway"]["runs_using_gateway"], 2)
            self.assertEqual(arms["core"]["runs_using_gateway"], 0)
            self.assertTrue((root / "1-core" / "full-native-summary.json").is_file())

    def test_stops_after_an_unscorable_run_and_on_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pair = {"pair_dir": folder, "results": {"kitsune": {"benchmark_evaluation": {"scorable": False}}}}
            with patch("kitsune_benchmark.full_native.run_pair", return_value=pair) as run, \
                    patch("kitsune_benchmark.full_native.source_revision", return_value={"revision": "abc"}):
                result = run_full_native(execute=True)
            self.assertEqual((run.call_count, result["attempted_runs"], result["stopped_reason"]), (1, 1, "unscorable_pair"))
            costly = fake_pair(root, "costly", CORE_EVENTS)
            costly["results"]["kitsune"]["list_price_cost_usd"] = 0.9
            with patch("kitsune_benchmark.full_native.run_pair", side_effect=lambda **_: costly) as run, \
                    patch("kitsune_benchmark.full_native.source_revision", return_value={"revision": "abc"}), \
                    patch("kitsune_benchmark.full_native.write_json"):
                result = run_full_native(execute=True, harness="claude-api", budget_usd=2.5)
            self.assertEqual((run.call_count, result["stopped_reason"]), (2, "suite_budget"))


class FullNativeAnalysisTests(unittest.TestCase):
    def test_gateway_batch_steps_and_capability_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            row = run_metrics(fake_pair(Path(folder), "g", GATEWAY_EVENTS,
                                        published=("browser_click", "browser_tools_call", "browser_tools_search")))
        native = row["native"]
        self.assertEqual(native["gateway_calls"], {"browser_tools_search": 1, "browser_tools_call": 2,
                                                   "browser_tools_publish": 0})
        self.assertEqual(native["gateway_called_tools"], {"browser_batch": 1, "browser_page_text": 1})
        self.assertEqual(native["container_calls"], {"browser_batch": 1, "browser_parallel": 1})
        self.assertEqual(native["batch_steps"], 6)
        self.assertEqual(native["capability_errors"], {"capability_restricted": 1, "tool_not_published": 1,
                                                       "not_supported": 0})
        self.assertEqual((native["agent_calls"], native["error_results"]), (4, 1))
        self.assertEqual((row["published_tools"], row["gateway_published"], row["model_requests"]), (3, True, 3))

    def test_codex_events_and_missing_events(self):
        with tempfile.TemporaryDirectory() as folder:
            events = Path(folder) / "events.jsonl"
            events.write_text(json.dumps({"type": "item.completed", "item": {
                "type": "mcp_tool_call", "tool": "browser_tools_call", "status": "completed",
                "arguments": {"name": "browser_batch", "arguments": {"commands": [{}, {}]}},
                "result": {"isError": True, "content": [{"type": "text", "text": '{"code":"not_supported"}'}]}}}))
            self.assertEqual(agent_calls(events), [{"tool": "browser_tools_call", "error": True,
                "arguments": {"name": "browser_batch", "arguments": {"commands": [{}, {}]}},
                "text": '{"code":"not_supported"}'}])
            missing = run_metrics({"pair_dir": folder, "results": {"kitsune": {"run_dir": folder + "/none"}}})
        self.assertIsNone(missing["native"], "missing events are unmeasured, not zero use")
        self.assertIsNone(missing["published_tools"])

    def test_joint_successes_keep_failures_out_of_the_ratio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def run(unit, arm, events, **kwargs):
                return {"unit": unit, "arm": arm, "track": "personal", "category": "research",
                        "pair": fake_pair(root, f"{unit}-{arm}", events, **kwargs)}
            runs = [run("a", "core", CORE_EVENTS, input_tokens=100), run("a", "gateway", GATEWAY_EVENTS, input_tokens=150),
                    run("b", "core", CORE_EVENTS, input_tokens=200), run("b", "gateway", GATEWAY_EVENTS, input_tokens=100),
                    run("c", "core", CORE_EVENTS, input_tokens=50),
                    run("c", "gateway", GATEWAY_EVENTS, input_tokens=999, success=False)]
            result = analyze(runs)
            joint = result["joint_successes"]
            self.assertEqual(joint["units"], ["a", "b"])
            self.assertEqual((joint["input_tokens"]["core"]["total"], joint["input_tokens"]["gateway"]["total"]), (300, 250))
            self.assertAlmostEqual(joint["input_tokens"]["ratio_gateway_to_core"], 250 / 300)
            self.assertAlmostEqual(joint["input_tokens"]["unit_ratios_median"], (1.5 + 0.5) / 2)
            gateway = result["arms"]["gateway"]
            self.assertEqual((gateway["runs"], gateway["successes"], gateway["input_tokens"]["total"]), (3, 2, 1249))
            self.assertEqual((gateway["batch_steps"], gateway["capability_errors"]["capability_restricted"]), (18, 3))
            self.assertEqual(result["by_category"]["research"]["core"]["successes"], 3)
            self.assertEqual(result["units"]["c"]["gateway"]["task_success"], False)
            summary = root / "suite-summary.json"
            summary.write_text(json.dumps({"benchmark": BENCHMARK, "runs": runs}))
            output = root / "analysis.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(analyze_main([str(summary), "--output", str(output)]), 0)
                self.assertEqual(json.loads(output.read_text())["joint_successes"]["units"], ["a", "b"])
                with self.assertRaises(FileExistsError):
                    analyze_main([str(summary), "--output", str(output)])
            summary.write_text(json.dumps({"benchmark": "personal-browsing-local-v3", "pairs": []}))
            with redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()):
                self.assertEqual(analyze_main([str(summary)]), 2)


class GatewayRelayTests(unittest.TestCase):
    def test_relay_counts_gateway_calls_as_the_tool_they_run(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {"target": "kitsune", "upstream": [], "bootstrap_url": "http://local/t/start",
                        "urls": ["http://local/t/a"], "active_index": 0,
                        "evidence_path": folder + "/evidence.json", "origin": "http://local"}
            session = FullNativeSession(settings)
            session.evidence["setup_complete"] = True
            sent = []
            def fake_request(method, params=None, **kwargs):
                sent.append(params)
                if params["name"] == "browser_tabs" and params["arguments"].get("action") == "list":
                    return {"result": {"structuredContent": {"tabs": [
                        {"index": 0, "url": "http://local/t/a", "current": True, "active": True}]}}}
                return {"result": {"content": [{"type": "text", "text": "ok"}]}}
            session.request = fake_request
            responses = []
            session.forward({"id": 1, "method": "tools/call", "params": {"name": "browser_tools_call", "arguments": {
                "name": "browser_tabs", "arguments": {"action": "close", "index": 0}}}}, responses.append)
            self.assertEqual(session.evidence["close_attempts"], 1)
            self.assertEqual(session.evidence["tab_calls"], [{"tool": "browser_tabs", "error": False, "action": "close",
                "index": 0, "tab_id": None, "url": None, "via": "browser_tools_call"}])
            self.assertEqual(sent[0]["name"], "browser_tools_call", "the native call is forwarded unchanged")
            for call in ({"name": "browser_batch", "arguments": {"commands": [{"action": "navigate", "url": "https://x.invalid"}]}},
                         {"name": "browser_tools_call", "arguments": {"name": "browser_navigate",
                                                                      "arguments": {"url": "https://x.invalid"}}}):
                session.forward({"id": 2, "method": "tools/call", "params": call}, responses.append)
                self.assertTrue(responses[-1]["result"]["isError"])
            self.assertEqual(session.evidence["outside_navigation"], 2)
            self.assertEqual(len(sent), 2, "the close and its inventory only: blocked calls never reach the browser")
            session.forward({"id": 3, "method": "tools/call", "params": {"name": "browser_tabs", "arguments": {
                "action": "close", "index": 0}}}, responses.append)
            self.assertEqual(session.evidence["close_attempts"], 2, "a direct close is counted once, by the base relay")
            self.assertNotIn("via", session.evidence["tab_calls"][-1])


if __name__ == "__main__":
    unittest.main()
