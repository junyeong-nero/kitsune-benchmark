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


class FullSuiteTests(unittest.TestCase):
    def invoke(self, results, *, sequential=False, first="personal-v0"):
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
            if sequential:
                argv.append("--sequential")
            with patch.object(suite.sys, "argv", argv), \
                 patch.object(suite, "git_identity", return_value={}), \
                 patch.object(suite, "commands", return_value=[(first, ["personal"]), ("next", ["personal"])]), \
                 patch.object(suite.subprocess, "Popen", side_effect=popen), redirect_stdout(io.StringIO()):
                code = suite.main()
            entries = [json.loads(line) for line in (Path(directory) / "suite-log.jsonl").read_text().splitlines()]
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

    def test_miniwob_without_suite_counts_and_invalid_json(self):
        # MiniWoB is a single pair. Valid output plus exit zero can advance.
        next_result = {"requested_pairs": 1, "completed_pairs": 1}
        code, launched, _, _ = self.invoke(
            [(0, {"results": {"kitsune": {}}}), (0, next_result)],
            sequential=True, first="miniwob")
        self.assertEqual(code, 0)
        self.assertEqual(len(launched), 2)
        code, launched, _, _ = self.invoke([(0, "not json")], first="miniwob")
        self.assertEqual(code, 3)
        self.assertEqual(len(launched), 1)

    def test_scorable_task_failures_do_not_stop_suite(self):
        result = {"requested_pairs": 24, "completed_pairs": 24,
                  "stopped_reason": None, "by_target": {"kitsune": {"successes": 23}}}
        code, launched, waited, entries = self.invoke([(0, result)] * 4)
        self.assertEqual(code, 0)
        self.assertEqual(len(launched), 4)
        self.assertEqual(len(waited), 4)
        self.assertEqual(entries[-1]["name"], "next")


if __name__ == "__main__":
    unittest.main()
