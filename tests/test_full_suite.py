"""No model, browser or network calls: orchestration must fail closed."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "run_full_suite", Path(__file__).resolve().parents[1] / "scripts/run-full-suite.py")
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)



def suite_config_model():
    from kitsune_benchmark.personal import config
    return config()["model"]


class FullSuiteTests(unittest.TestCase):
    def invoke(self, results, *, sequential=False, first="personal-v0", extra=(), tracks=None):
        launched = []
        waited = []
        with tempfile.TemporaryDirectory() as directory:
            def popen(command, stdout, stderr):
                index = len(launched)
                launched.append(command)
                code, result = results[index]
                stdout.write(result if isinstance(result, str) else json.dumps(result))
                class Process:
                    def wait(self):
                        waited.append(index)
                        return code
                return Process()
            argv = ["run-full-suite.py", "--kitsune-project", directory, "--out", directory]
            argv.extend(extra)
            if sequential:
                argv.append("--sequential")
            with patch.object(suite.sys, "argv", argv), \
                 patch.object(suite, "git_identity", return_value={}), \
                 patch.object(suite, "commands", return_value=tracks if tracks is not None else
                              [(first, ["personal"]), ("next", ["personal"])]), \
                 patch.object(suite.subprocess, "Popen", side_effect=popen), redirect_stdout(io.StringIO()):
                code = suite.main()
            entries = [json.loads(line) for line in (Path(directory) / "suite-log.jsonl").read_text().splitlines()]
            self.manifest = json.loads((Path(directory) / "suite-manifest.json").read_text())
            self.summary = json.loads((Path(directory) / "suite-summary.json").read_text())
            self.outputs = [str(p.relative_to(directory)) for p in Path(directory).rglob("*.json")]
        return code, launched, waited, entries

    def test_failed_target_stops_later_tracks_after_active_peers(self):
        ok = {"requested_pairs": 24, "completed_pairs": 24}
        bad = {"requested_pairs": 24, "completed_pairs": 2, "stopped_reason": "unscorable_pair"}
        for results in ([(0, ok), (3, bad)], [(3, bad), (0, ok)]):
            code, launched, waited, entries = self.invoke(results)
            self.assertEqual(code, 3)
            self.assertEqual(len(launched), 2)
            self.assertEqual(waited, [0, 1])
            self.assertEqual(len(entries), 2)
            self.assertTrue(all(entry["name"] == "personal-v0" for entry in entries))

    def test_zero_exit_is_not_enough_for_valid_track(self):
        for result in ("not json", "[]", "{}", {"requested_pairs": 24, "completed_pairs": 2},
                       {"requested_pairs": 24, "completed_pairs": 24, "stopped_reason": "budget"}):
            with self.subTest(result=result):
                code, launched, _, _ = self.invoke([(0, result)], sequential=True)
                self.assertEqual(code, 3)
                self.assertEqual(len(launched), 1)

    def test_external_needs_suite_counts_like_other_tracks(self):
        # The old single-pair MiniWoB output (results only, no counts) no longer advances the suite.
        code, launched, _, _ = self.invoke([(0, {"results": {"kitsune": {}}})], sequential=True, first="external")
        self.assertEqual(code, 3)
        self.assertEqual(len(launched), 1)
        ok = {"requested_pairs": 10, "completed_pairs": 10}
        code, launched, _, _ = self.invoke([(0, ok), (0, ok)], sequential=True, first="external")
        self.assertEqual(code, 0)
        self.assertEqual(len(launched), 2)

    def test_scorable_task_failures_do_not_stop_suite(self):
        result = {"requested_pairs": 24, "completed_pairs": 24,
                  "stopped_reason": None, "by_target": {"kitsune": {"successes": 23}}}
        code, launched, waited, entries = self.invoke([(0, result)] * 4)
        self.assertEqual(code, 0)
        self.assertEqual(len(launched), 4)
        self.assertEqual(len(waited), 4)
        self.assertEqual(entries[-1]["name"], "next")
        self.assertEqual(entries[-1]["by_target"], result["by_target"])

    def test_default_child_commands_and_root_outputs(self):
        tracks = [(f"personal-v{v}", ["personal", "--all", "--variant", str(v)]) for v in range(3)]
        tracks += [(f"gallery-{layout}-v{v}", ["gallery", "--layout", layout, "--variant", str(v)])
                   for layout in ("crowded", "isolated") for v in range(3)]
        tracks.append(("coexistence-user-seeded", ["coexistence", "--all-personal", "--variant", "0"]))
        tracks += [(f"coexistence-typing-v{v}", ["coexistence", "--task", "co-typing-01", "--variant", str(v)])
                   for v in range(3)]
        tracks.append(("coexistence-protect", ["coexistence", "--all-personal", "--variant", "0",
                                               "--protect-user-tabs", "--targets", "kitsune"]))
        tracks.append(("external", ["external"]))
        self.assertEqual(suite.commands(), tracks)
        result = {"requested_pairs": 1, "completed_pairs": 1, "results": {"kitsune": {}}}
        for sequential in (False, True):
            with self.subTest(sequential=sequential):
                code, launched, _, entries = self.invoke([(0, result)] * 31,
                                                         sequential=sequential, tracks=suite.commands())
                self.assertEqual(code, 0)
                project = launched[0][launched[0].index("--kitsune-project") + 1]
                expected, outputs = [], []
                for name, argv in tracks:
                    base = [suite.sys.executable, "-m", "kitsune_benchmark", *argv, "--harness", "claude",
                            "--claude-model", "claude-opus-5-5", "--kitsune-project", project, "--execute"]
                    if name.startswith("coexistence"):  # always paired in one process; the arm fixes its target
                        expected.append(base + ([] if "--targets" in argv else ["--targets", "playwright,kitsune"]))
                        outputs.append(f"{name}.json")
                        continue
                    targets = ("playwright", "kitsune") if not sequential else ("playwright,kitsune",)
                    for target in targets:
                        expected.append(base + ["--targets", target])
                        outputs.append(f"{name}-{target}.json" if len(targets) == 2 else f"{name}.json")
                self.assertEqual(launched, expected)
                self.assertCountEqual(self.outputs, outputs + ["suite-manifest.json", "suite-summary.json"])
                self.assertEqual(self.manifest["attempts"], 1)
                self.assertTrue(all(entry["attempt"] == 1 for entry in entries))

    def test_lite_plan_keeps_every_task_with_fewer_variants(self):
        lite = suite.commands("lite")
        names = [name for name, _ in lite]
        self.assertEqual([n for n in names if n.startswith("personal")], ["personal-v0", "personal-v1"])
        self.assertEqual([n for n in names if n.startswith("gallery")], ["gallery-crowded-v0", "gallery-isolated-v0"])
        full = suite.commands()
        self.assertEqual([c for c in lite if not c[0].startswith(("personal", "gallery"))],
                         [c for c in full if not c[0].startswith(("personal", "gallery"))])
        self.assertTrue(all("--all" in argv for name, argv in lite if name.startswith("personal")))
        # 4 personal/gallery entries and external in parallel (2 processes each), 5 coexistence entries paired.
        code, launched, _, _ = self.invoke([(0, {"requested_pairs": 1, "completed_pairs": 1})] * 15,
                                           tracks=lite, extra=("--plan", "lite"))
        self.assertEqual(code, 0)
        self.assertEqual(len(launched), 15)
        self.assertEqual(self.manifest["plan"], "lite")

    def test_codex_harness_passes_and_records_its_model(self):
        result = {"requested_pairs": 1, "completed_pairs": 1, "results": {"kitsune": {}}}
        for extra, model in ((("--harness", "codex", "--model", "gpt-6.1-sol"), "gpt-6.1-sol"),
                             (("--harness", "codex"), suite_config_model())):
            with self.subTest(extra=extra):
                code, launched, _, _ = self.invoke([(0, result)] * 31, tracks=suite.commands(), extra=extra)
                self.assertEqual(code, 0)
                self.assertTrue(all(cmd[cmd.index("--codex-model") + 1] == model and "--claude-model" not in cmd
                                    for cmd in launched))
                self.assertEqual(self.manifest["model"], model)

    def test_attempt_plan_and_invalid_parallel_order(self):
        self.assertEqual(suite.attempt_plan(1, None, False), [{"attempt": 1, "order": None}])
        self.assertEqual([p["order"] for p in suite.attempt_plan(4, "abba", True)], ["ab", "ba", "ab", "ba"])
        for attempts, order, sequential in ((0, None, False), (-1, None, True), (2, "ab", False), (1, "abba", True)):
            with self.subTest(attempts=attempts, order=order), self.assertRaises(ValueError):
                suite.attempt_plan(attempts, order, sequential)

    def test_repeated_counterbalanced_attempts_keep_evidence_and_report_order(self):
        result = {"requested_pairs": 28, "completed_pairs": 28, "by_target": {"kitsune": {"successes": 27}}}
        code, launched, waited, entries = self.invoke([(0, result)] * 4, sequential=True,
                                                     extra=("--attempts", "2", "--order", "abba"))
        self.assertEqual(code, 0)
        self.assertEqual(waited, [0, 1, 2, 3])
        self.assertEqual([cmd[cmd.index("--targets") + 1] for cmd in launched],
                         ["playwright,kitsune"] * 2 + ["kitsune,playwright"] * 2)
        self.assertEqual([e["attempt"] for e in entries], [1, 1, 2, 2])
        self.assertEqual([e["order"] for e in entries], ["ab", "ab", "ba", "ba"])
        self.assertEqual(len({e["output_path"] for e in entries}), 4)
        self.assertIn("attempt-001/personal-v0.json", self.outputs)
        self.assertIn("attempt-002/personal-v0.json", self.outputs)
        self.assertEqual(self.manifest["attempt_plan"], [{"attempt": 1, "order": "ab"}, {"attempt": 2, "order": "ba"}])
        self.assertEqual(self.summary["by_order"]["ba"], entries[2:])
        self.assertEqual(self.summary["by_attempt"]["1"], entries[:2])
        self.assertEqual(entries[-1]["by_target"], result["by_target"])

    def test_repeated_attempts_stop_on_first_invalid_track(self):
        bad = {"requested_pairs": 28, "completed_pairs": 1, "stopped_reason": "unscorable_pair"}
        code, launched, _, entries = self.invoke([(0, bad)], sequential=True,
                                                extra=("--attempts", "2", "--order", "abba"))
        self.assertEqual(code, 3)
        self.assertEqual(len(launched), 1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(self.summary["entries"], entries)

    def test_external_receives_ba_order(self):
        ok = {"requested_pairs": 10, "completed_pairs": 10}
        code, launched, _, entries = self.invoke([(0, ok), (0, ok)],
                                                sequential=True, first="external", extra=("--order", "ba"))
        self.assertEqual(code, 0)
        self.assertEqual(launched[0][launched[0].index("--targets") + 1], "kitsune,playwright")
        self.assertEqual(entries[0]["order"], "ba")

    def test_refuses_nonempty_output_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "evidence.json"
            sentinel.write_text("original")
            argv = ["run-full-suite.py", "--kitsune-project", directory, "--out", directory]
            with patch.object(suite.sys, "argv", argv), patch.object(suite.subprocess, "Popen") as launch, \
                    patch.object(suite.sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
                suite.main()
            launch.assert_not_called()
            self.assertEqual(sentinel.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
