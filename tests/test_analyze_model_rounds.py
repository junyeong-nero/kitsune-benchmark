import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "analyze_model_rounds", Path(__file__).resolve().parents[1] / "scripts/analyze-model-rounds.py")
rounds_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rounds_script)


def request(message_id, *calls, read=100, write=10, uncached=2):
    """One assistant event per tool_use block, all sharing the message id and usage, as Claude Code streams them."""
    usage = {"input_tokens": uncached, "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
             "output_tokens": 5}
    blocks = [{"type": "tool_use", "id": call_id, "name": f"mcp__browser__{tool}", "input": arguments}
              for call_id, tool, arguments in calls] or [{"type": "text", "text": "done"}]
    return [{"type": "assistant", "message": {"id": message_id, "content": [block], "usage": usage}}
            for block in blocks]


def result(call_id, text, error=False):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": call_id, "is_error": error,
                                                      "content": [{"type": "text", "text": text}]}]}}


HINT = "… 3 more similar items; snapshot e13 to list all"
# Playwright-like: action results carry no refs, the snapshot is batched after the page-turn click.
BATCHED = [
    *request("m1", ("s1", "browser_snapshot", {}), read=90, write=20),
    result("s1", "- checkbox [ref=f1e1]\n- checkbox [ref=f1e2]\n- button [ref=f1e3]"),
    *request("m2", ("c1", "browser_click", {"target": "f1e1"}), ("c2", "browser_click", {"target": "f1e3"}),
             ("s2", "browser_snapshot", {"target": "f1e0"})),
    result("c1", "### Ran code"), result("c2", "### Ran code"),
    result("s2", "- checkbox [ref=f1e4]\n- button [ref=f1e3]"),
    *request("m3"),
    {"type": "result", "usage": {"output_tokens": 42}},
]
# Kitsune-like: collapsed snapshots and click deltas, each expanded in a separate observation-only round.
SEQUENTIAL = [
    *request("k1", ("s1", "browser_snapshot", {})),
    result("s1", f"- checkbox [ref=e5]\n- {HINT}\n- button [ref=e11]"),
    *request("k2", ("s2", "browser_snapshot", {"target": "e13"})),
    result("s2", "- checkbox [ref=e5]\n- checkbox [ref=e6]"),
    *request("k3", ("c1", "browser_click", {"target": "e5"}), ("c2", "browser_click", {"target": "e11"})),
    result("c1", "- checkbox [ref=e5] checked=true"), result("c2", f"- checkbox [ref=e17]\n- {HINT}"),
    *request("k4", ("s3", "browser_snapshot", {"target": "e13"})),
    result("s3", "- checkbox [ref=e17]\n- checkbox [ref=e18]"),
    *request("k5", ("f1", "browser_find", {"text": "x"})),
    result("f1", "not found", error=True),
    *request("k6"),
]
# Page turns to an uncollapsed page: the earlier e13 hint is stale, so container snapshots read cell values.
PAGE_TURNS = [
    *request("p1", ("s1", "browser_snapshot", {})),
    result("s1", f"- checkbox [ref=e5]\n- {HINT}\n- button [ref=e11]"),
    *request("p2", ("c1", "browser_click", {"target": "e11"})),
    result("c1", "- checkbox [ref=e17]\n- button [ref=e11]"),
    *request("p3", ("s2", "browser_snapshot", {"target": "e13"})),
    result("s2", "- checkbox [ref=e17]"),
    *request("p4", ("c2", "browser_click", {"target": "e17"}), ("c3", "browser_click", {"target": "e11"}),
             ("s3", "browser_snapshot", {"target": "e13"})),
    result("c2", f"- checkbox [ref=e17] checked=true\n- {HINT}"), result("c3", "- checkbox [ref=e20]"),
    result("s3", "- checkbox [ref=e20]"),
    *request("p5"),
]


class ModelRoundsTests(unittest.TestCase):
    def test_parallel_calls_with_trailing_observation_stay_one_round(self):
        rounds = rounds_script.model_rounds(BATCHED)
        self.assertEqual([r["kind"] for r in rounds], ["observation", "action+observation", "answer"])
        self.assertEqual(rounds[1]["tools"], ["browser_click", "browser_click", "browser_snapshot"])
        self.assertTrue(rounds[1]["parallel"])
        self.assertTrue(rounds[1]["in_batch_observation_after_action"])
        self.assertFalse(any(r["follow_up_observation"] for r in rounds))
        self.assertEqual((rounds[1]["action_result_refs"], rounds[1]["refs_returned"], rounds[1]["new_refs"]), (0, 2, 1))
        self.assertEqual(rounds[1]["action_result_chars"], 2 * len("### Ran code"))

    def test_usage_is_counted_once_per_message_id(self):
        summary = rounds_script.run_summary(BATCHED)
        self.assertEqual(summary["requests"], 3)
        self.assertEqual(summary["calls"], 4)
        self.assertEqual(summary["input_tokens"], 112 + 2 * 112)
        self.assertEqual((summary["cache_read_input_tokens"], summary["cache_creation_input_tokens"],
                          summary["uncached_input_tokens"]), (90 + 200, 20 + 20, 6))
        self.assertEqual(summary["prefix_x_requests_tokens"], 112 * 3)
        self.assertEqual(summary["history_tokens"], 0)
        self.assertEqual(summary["result_output_tokens"], 42)
        self.assertEqual(summary["rounds_before_first_action"], 1)

    def test_collapsed_results_and_expansion_rounds(self):
        rounds = rounds_script.model_rounds(SEQUENTIAL)
        self.assertEqual([r["kind"] for r in rounds],
                         ["observation", "observation", "action", "observation", "observation", "answer"])
        self.assertEqual([r["chained_observation"] for r in rounds], [False, True, False, False, True, False])
        self.assertEqual([r["follow_up_observation"] for r in rounds], [False, False, False, True, False, False])
        self.assertEqual([r["expansion_reads"] for r in rounds], [0, 1, 0, 1, 0, 0])
        self.assertEqual([r["elided_items"] for r in rounds], [3, 0, 3, 0, 0, 0])
        self.assertEqual((rounds[2]["action_result_refs"], rounds[2]["action_new_refs"]), (2, 1))
        self.assertEqual(rounds[1]["new_refs"], 1)
        self.assertEqual(rounds[4]["errors"], 1)
        summary = rounds_script.run_summary(SEQUENTIAL)
        self.assertEqual(summary["rounds_before_first_action"], 2)
        self.assertEqual(summary["kinds"], {"observation": 4, "action": 1, "answer": 1})
        self.assertEqual(summary["tools"], {"browser_snapshot": 3, "browser_click": 2, "browser_find": 1})
        self.assertEqual((summary["parallel"], summary["elided_results"], summary["expansion_reads"]), (1, 2, 2))

    def test_stale_hint_after_page_turn_is_not_an_expansion(self):
        rounds = rounds_script.model_rounds(PAGE_TURNS)
        self.assertEqual([r["expansion_reads"] for r in rounds], [0, 0, 0, 0, 0])
        self.assertEqual([r["follow_up_observation"] for r in rounds], [False, False, True, False, False])
        self.assertFalse(rounds[2]["follow_up_on_collapsed"])
        self.assertEqual(rounds_script.model_rounds(SEQUENTIAL)[3]["follow_up_on_collapsed"], True)

    def test_job_json_runs_are_grouped_by_layout_and_target(self):
        with tempfile.TemporaryDirectory() as root:
            runs = {}
            for target, events in (("playwright", BATCHED), ("kitsune", SEQUENTIAL)):
                run_dir = Path(root) / target
                run_dir.mkdir()
                (run_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
                runs[target] = {"run_dir": str(run_dir)}
            job = Path(root) / "job.json"
            job.write_text(json.dumps({"layout": "isolated", "pairs": [{"results": runs}]}))
            found = list(rounds_script.runs_from(job))
            self.assertEqual([(layout, target) for layout, target, _ in found],
                             [("isolated", "playwright"), ("isolated", "kitsune")])
            self.assertEqual(list(rounds_script.runs_from(Path(root) / "kitsune")),
                             [(None, None, Path(root) / "kitsune")])
            summaries = [rounds_script.run_summary(rounds_script.read_events(run_dir / "events.jsonl"))
                         for _, _, run_dir in found]
        group = rounds_script.group_summary(summaries)
        self.assertEqual((group["runs"], group["requests"], group["calls"]), (2, 9, 10))
        self.assertEqual(group["per_run_requests"], [3, 6])
        self.assertEqual(group["follow_up_observation"], 1)
        self.assertEqual(group["calls_per_request"], 1.11)


if __name__ == "__main__":
    unittest.main()
