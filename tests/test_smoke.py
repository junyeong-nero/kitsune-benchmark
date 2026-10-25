import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.specs import Task
from kitsune_benchmark.viewport import viewport_record
from kitsune_benchmark.smoke import ROOT, WS_SETTING, benchmark_source, copy_extension, tool_surface, experiment, private_ports, run_pair


class SmokeTests(unittest.TestCase):
    def test_tool_surface_reports_unpublished_allowlisted_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kitsune-native-metadata.json"
            path.write_text(json.dumps({"enabled_tools": [], "tools_pages": [
                {"tools": [{"name": "browser_click"}, {"name": "browser_snapshot"}]}, {"tools": [{"name": "browser_js"}]}]}))
            surface = tool_surface(path, ("browser_snapshot", "browser_keypress", "browser_click"))
            self.assertEqual(surface["missing"], ["browser_keypress"])
            self.assertEqual(surface["exposed"], ["browser_click", "browser_snapshot"])
            self.assertEqual(surface["published_count"], 3)
            self.assertIsNone(tool_surface(Path(tmp) / "absent.json", ("browser_click",)))

    def test_benchmark_source_names_the_taskset_tag(self):
        source = benchmark_source()
        self.assertRegex(source["revision"], r"^[0-9a-f]{40}$")
        self.assertTrue(source["taskset"].startswith("taskset-v"))

    def test_exact_requested_model_and_reasoning_pin(self):
        spec = experiment()
        self.assertEqual(spec["model"], "gpt-6-luna")
        self.assertEqual(spec["reasoning_effort"], "medium")

    def test_default_plan_has_no_process_or_browser_side_effects(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no model or browser")):
            result = run_pair()
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["mode"], "smoke_plan_only")

    def test_run_pair_records_live_timing_and_phases_even_if_first_target_stops(self):
        spec = experiment()
        for stop_early, targets in ((False, ("playwright", "kitsune")), (True, ("playwright", "kitsune")),
                                    (False, ("kitsune", "playwright"))):
            with self.subTest(stop_early=stop_early), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                for filename in ("project/extension/manifest.json", "node_modules/.bin/web-ext",
                                 "node_modules/@playwright/mcp/cli.js", "firefox"):
                    path = root / filename
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                collector = MagicMock()
                collector.__enter__.return_value = collector
                setup, ready = {"duration_sec": 4}, {"duration_sec": 1}
                collector.summary = {"metrics": {"phase/setup/owner/kitsune": setup,
                                                  "phase/ready/owner/kitsune": ready}}
                def fake_run(server, task, model, **kwargs):
                    run_dir = Path(kwargs["output_root"]) / server.id
                    run_dir.mkdir(parents=True)
                    records = [{"kind": "setup_completed", "duration_sec": 2},
                               {"kind": "rpc_completed", "role": "agent", "method": "tools/call",
                                "duration_sec": .5}]
                    (run_dir.parent.parent / f"{server.id}-native-rpc.jsonl").write_text(
                        "\n".join(json.dumps(r) for r in records) + '\n{"truncated":')
                    return {"run_dir": str(run_dir), "elapsed_sec": 10,
                            "execution_status": "error" if stop_early else "completed_unscored"}
                evaluation = {"scorable": True, "task_success": True}
                with patch("kitsune_benchmark.smoke.ROOT", root), \
                        patch("kitsune_benchmark.smoke.resolve", return_value="fake-codex"), \
                        patch("kitsune_benchmark.smoke.harness_environment", return_value={}), \
                        patch("kitsune_benchmark.smoke.harness_preflight"), \
                        patch("kitsune_benchmark.smoke.copy_extension", return_value={}), \
                        patch("kitsune_benchmark.smoke.source_revision", return_value={}), \
                        patch("kitsune_benchmark.smoke.benchmark_source", return_value={}), \
                        patch("kitsune_benchmark.smoke.private_ports", return_value=(51234, 51235)), \
                        patch("kitsune_benchmark.smoke.subprocess.run", return_value=MagicMock(stdout=str(root / "firefox"))), \
                        patch("kitsune_benchmark.smoke.subprocess.Popen") as popen, \
                        patch("kitsune_benchmark.smoke.await_bridge"), \
                        patch("kitsune_benchmark.smoke.terminate_group"), \
                        patch("kitsune_benchmark.smoke.ResourceCollector", return_value=collector), \
                        patch("kitsune_benchmark.smoke.time.monotonic", side_effect=[100, 104]), \
                        patch("kitsune_benchmark.smoke.time.sleep"), \
                        patch("kitsune_benchmark.smoke.run", side_effect=fake_run) as run, \
                        patch("kitsune_benchmark.smoke.os.environ", {}):
                    summary = run_pair(execute=True, kitsune_project=str(root / "project"),
                                       experiment_spec=spec, task_for_target=lambda target: Task("test", "test"),
                                       evaluate=lambda target, result: evaluation, targets=targets)
                saved = json.loads((Path(summary["pair_dir"]) / "pair-summary.json").read_text())
                manifest = json.loads((Path(summary["pair_dir"]) / "pair-manifest.json").read_text())
                self.assertEqual(manifest["targets"], list(targets))
                self.assertEqual([call.args[0].id for call in run.call_args_list], list(targets)[:1] if stop_early else list(targets))
                self.assertEqual(manifest["viewport"], saved["viewport"])
                self.assertEqual(manifest["viewport"]["playwright"]["configured"]["viewport_size"], {"width": 1280, "height": 720})
                self.assertEqual(manifest["viewport"]["kitsune"]["configured"]["window_size"], {"width": 1280, "height": 720})
                self.assertTrue(manifest["viewport"]["kitsune"]["configured"]["headless"])
                for target, result in saved["results"].items():
                    self.assertEqual(result["viewport"], manifest["viewport"][target])
                    self.assertIsNone(result["viewport"]["effective"])
                    self.assertFalse(result["viewport"]["content_viewport_equality_asserted"])
                for call in run.call_args_list:
                    self.assertEqual(call.kwargs["viewport"], manifest["viewport"][call.args[0].id])
                self.assertEqual(saved["timing"], {"kitsune_cold_start_setup_sec": 4})
                self.assertEqual(saved["resource_phases"]["kitsune"], {"setup": setup, "ready": ready})
                self.assertEqual(popen.call_count, 2)
                self.assertEqual(run.call_count, 1 if stop_early else 2)
                self.assertEqual(set(saved["results"]), {"playwright"} if stop_early else {"playwright", "kitsune"})
                for result in saved["results"].values():
                    self.assertEqual(result["timing"], {"relay_setup_sec": 2, "elapsed_minus_relay_setup_sec": 8,
                                                        "agent_native_rpc_sec": .5})
                    self.assertEqual(result["benchmark_evaluation"], evaluation)
                    self.assertEqual(json.loads((Path(result["run_dir"]) / "evaluation.json").read_text()), evaluation)
                self.assertEqual([call.args[0] for call in collector.set_phase.call_args_list],
                                 ["setup", "ready"] + ["task_" + t for t in (targets[:1] if stop_early else targets)]
                                 + ["cleanup", "cleanup", "cleanup"])

    def test_viewport_records_parse_actual_args_and_do_not_guess(self):
        pw = viewport_record("playwright", ("--viewport-size", "900x600"))
        kit = viewport_record("kitsune", (), ("-headless", "--width=900", "--height=650"))
        self.assertEqual(pw["configured"]["viewport_size"], {"width": 900, "height": 600})
        self.assertEqual(kit["configured"]["window_size"], {"width": 900, "height": 650})
        for record in (pw, kit, viewport_record("kitsune")):
            self.assertIsNone(record["effective"])
            self.assertEqual(record["effective_unavailable_reason"], "not_observable_without_agent_visible_calls")
        self.assertIsNone(viewport_record("playwright")["configured"])
        conflicting = ("--width=1280", "--height=720", "--height=900")
        record = viewport_record("kitsune", (), conflicting)
        self.assertIsNone(record["configured"])
        self.assertEqual(record["configured_args"], list(conflicting))

    def test_cli_smoke_default_is_safe(self):
        output = io.StringIO()
        with patch("subprocess.Popen", side_effect=AssertionError("no model")), redirect_stdout(output):
            self.assertEqual(main(["smoke"]), 0)
        self.assertFalse(json.loads(output.getvalue())["model_invoked"])

    def test_cli_smoke_custom_task_is_validated_and_plan_only(self):
        task = ROOT / "tasks/live/steam-goty-2025-negative-100h.json"
        with patch("subprocess.Popen", side_effect=AssertionError("no browser or inference")), \
                redirect_stdout(io.StringIO()) as out:
            code = main(["smoke", "--harness", "claude-api", "--task", str(task), "--ui-tools", "--targets", "kitsune"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out.getvalue())["model_invoked"])
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            bad = Path(folder) / "task.json"
            bad.write_text(json.dumps({"id": "x", "prompt": ""}))
            self.assertEqual(main(["smoke", "--task", str(bad)]), 2)

    def test_extension_patch_only_changes_copy_endpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            (source / "background").mkdir(parents=True)
            original = "// header\n" + WS_SETTING + "\n// trailer\n"
            (source / "background/background.js").write_text(original)
            (source / "manifest.json").write_text('{"name":"test"}')
            destination = root / "private"
            result = copy_extension(source, destination, 51234)
            self.assertEqual((source / "background/background.js").read_text(), original)
            self.assertEqual((destination / "background/background.js").read_text(),
                             original.replace("47652", "51234"))
            self.assertEqual((destination / "manifest.json").read_bytes(), (source / "manifest.json").read_bytes())
            self.assertNotEqual(result["original_background_sha256"], result["patched_background_sha256"])
            with self.assertRaises(ValueError):
                copy_extension(source, root / "bad", 47652)
            with self.assertRaises(ValueError):
                copy_extension(source, root / "bad", 80)
            (source / "background/background.js").write_text("unexpected format")
            with self.assertRaises(ValueError):
                copy_extension(source, root / "bad", 51234)

    def test_private_ports_are_distinct_and_not_user_defaults(self):
        ports = private_ports()
        self.assertNotEqual(*ports)
        self.assertFalse(set(ports) & {47651, 47652})


if __name__ == "__main__":
    unittest.main()
