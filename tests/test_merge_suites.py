"""merge-suites.py on synthetic suite directories. No model, browser or network calls."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("merge_suites", SCRIPTS / "merge-suites.py")
merge_suites = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(merge_suites)
RELEASE_SPEC = importlib.util.spec_from_file_location("analyze_release", SCRIPTS / "analyze-release.py")
release = importlib.util.module_from_spec(RELEASE_SPEC)
RELEASE_SPEC.loader.exec_module(release)

MANIFEST = {"model": "claude-opus-5-5", "harness": "claude", "plan": "lite", "elicitation": "decline",
            "targets_in_parallel": True, "attempts": 1, "order_policy": None,
            "kitsune": {"revision": "514b5b7"}, "taskset": {"tag": "taskset-v3"},
            "commands": ["personal-v0", "gallery-crowded-v0", "external"]}


def write_suite(folder: Path, manifest: dict, entries: list[dict]) -> Path:
    folder.mkdir(parents=True)
    (folder / "suite-manifest.json").write_text(json.dumps(manifest))
    (folder / "suite-log.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    return folder


def entry(name, target, exit_code=0):
    return {"name": name, "target": target, "exit": exit_code, "attempt": 1, "order": None}


class MergeSuitesTests(unittest.TestCase):
    def run_main(self, *argv):
        with patch.object(sys, "argv", ["merge-suites.py", *argv]), redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()):
            return merge_suites.main()

    def test_retry_replaces_both_targets_of_the_rerun_entry(self):
        with tempfile.TemporaryDirectory() as root:
            first = write_suite(Path(root) / "first", MANIFEST, [
                entry("personal-v0", "playwright"), entry("personal-v0", "kitsune"),
                entry("gallery-crowded-v0", "playwright"), entry("gallery-crowded-v0", "kitsune", 3)])
            retry_entries = [entry("gallery-crowded-v0", "playwright"), entry("gallery-crowded-v0", "kitsune"),
                             entry("external", "playwright"), entry("external", "kitsune")]
            retry = write_suite(Path(root) / "retry", {**MANIFEST, "commands": ["gallery-crowded-v0", "external"],
                                                       "resumed_from": "gallery-crowded-v0",
                                                       "previous_suite": str(Path(root) / "first")}, retry_entries)
            merged = Path(root) / "merged"
            self.assertEqual(self.run_main(str(first), str(retry), "--out", str(merged)), 0)
            entries = [json.loads(line) for line in (merged / "suite-log.jsonl").read_text().splitlines()]
            manifest = json.loads((merged / "suite-manifest.json").read_text())
            self.assertEqual(release.elicitation_policy(merged), ("decline", "suite-manifest"))
        self.assertEqual(entries, [entry("personal-v0", "playwright"), entry("personal-v0", "kitsune")] + retry_entries)
        self.assertEqual(manifest["replaced"], ["gallery-crowded-v0"])
        self.assertEqual(manifest["commands"], MANIFEST["commands"])
        self.assertEqual([source["manifest"].get("resumed_from") for source in manifest["sources"]],
                         [None, "gallery-crowded-v0"])

    def test_refuses_suites_that_are_not_one_cohort(self):
        for change in ({"elicitation": "accept"}, {"plan": "full"}, {"model": "claude-sonnet-5-5"},
                       {"kitsune": {"revision": "dea1ad4"}}, {"taskset": {"tag": "taskset-v2"}}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                first = write_suite(Path(root) / "first", MANIFEST, [entry("personal-v0", "kitsune", 3)])
                retry = write_suite(Path(root) / "retry", {**MANIFEST, **change}, [entry("personal-v0", "kitsune")])
                merged = Path(root) / "merged"
                with self.assertRaises(SystemExit):
                    self.run_main(str(first), str(retry), "--out", str(merged))
                self.assertFalse(merged.exists())

    def test_refuses_nonempty_output_and_missing_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            first = write_suite(Path(root) / "first", MANIFEST, [])
            retry = write_suite(Path(root) / "retry", MANIFEST, [])
            occupied = Path(root) / "occupied"
            occupied.mkdir()
            (occupied / "evidence.json").write_text("original")
            with self.assertRaises(SystemExit):
                self.run_main(str(first), str(retry), "--out", str(occupied))
            self.assertEqual([p.name for p in occupied.iterdir()], ["evidence.json"])
            with self.assertRaises(SystemExit):
                self.run_main(str(first), str(Path(root) / "absent"), "--out", str(Path(root) / "merged"))
            self.assertFalse((Path(root) / "merged").exists())


if __name__ == "__main__":
    unittest.main()
