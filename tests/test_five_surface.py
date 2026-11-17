import json
from pathlib import Path
import tempfile
import unittest

from kitsune_benchmark import five_surface
from kitsune_benchmark.claude_harness import audit_events


class FiveSurfacePlanTest(unittest.TestCase):
    def test_matrix(self):
        plan = five_surface.plan()
        rows = plan["attempts"]
        self.assertEqual(len(rows), 207)
        self.assertEqual([r["seq"] for r in rows], list(range(1, 208)))
        ids = {a["id"] for a in plan["arms"]}
        self.assertEqual(ids, {"codex-kitsune-zen", "codex-playwright", "codex-aside", "codex-ego",
                               "claude-kitsune-zen", "claude-playwright", "claude-aside", "claude-ego",
                               "claude-in-chrome"})
        for arm in ids:
            self.assertEqual(sum(r["arm"] == arm for r in rows), 23)
        self.assertEqual({r["model"] for r in rows if r["harness"] == "codex"}, {"gpt-6.1-sol"})
        self.assertEqual({r["model"] for r in rows if r["harness"] == "claude"}, {"claude-opus-5-5"})

    def test_chrome_audit_prefix(self):
        events = [
            {"type": "system", "subtype": "init", "apiKeySource": "none",
             "tools": ["mcp__claude-in-chrome__navigate"],
             "mcp_servers": [{"name": "claude-in-chrome", "status": "connected"}]},
            {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 5}, "content": [
                {"type": "tool_use", "id": "c1", "name": "mcp__claude-in-chrome__navigate",
                 "input": {"url": "https://example.com/"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "c1", "content": "ok"}]}},
            {"type": "result", "subtype": "success", "is_error": False, "result": "done",
             "usage": {"input_tokens": 5, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                       "output_tokens": 1}},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.jsonl"
            path.write_text("\n".join(json.dumps(e) for e in events))
            audit = audit_events(path, expected_key_source="none", prefix=five_surface.CHROME_PREFIX,
                                 server_name="claude-in-chrome")
            self.assertEqual(audit["violations"], [])
            self.assertEqual(audit["mcp_calls"], 1)
            self.assertEqual(five_surface.outside_urls(path, "http://127.0.0.1:1"), ["https://example.com/"])


if __name__ == "__main__":
    unittest.main()
