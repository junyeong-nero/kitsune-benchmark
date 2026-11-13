"""Opt-in representation-only relay: no extra native requests or ref generation."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.personal_session import NativeSession
from kitsune_benchmark.target_view import format_result


def text_bytes(message):
    return sum(len(x.get("text", "").encode()) for x in message.get("result", {}).get("content", [])
               if x.get("type") == "text")


class TargetViewSession(NativeSession):
    def __init__(self, config):
        super().__init__(config)
        self.view = config.get("target_view", "native")
        if self.view not in {"native", "catalog"} or config["target"] != "kitsune":
            raise ValueError("Invalid target-view experiment configuration")

    def native_request(self, method, params=None, **kwargs):
        return super().request(method, params, **kwargs)

    def request(self, method, params=None, *, notify=None, role="harness"):
        message = self.native_request(method, params, notify=notify, role=role)
        if role != "agent" or method != "tools/call":
            return message
        started = time.perf_counter()
        if self.view == "catalog":
            output, counts = format_result(message)
        else:
            output, counts = message, {}
        self.diagnostic("target_view_delivered", view=self.view, tool=(params or {}).get("name"),
                        native_text_bytes=text_bytes(message), delivered_text_bytes=text_bytes(output),
                        formatter_sec=time.perf_counter() - started, **counts)
        return output


def main():
    session = TargetViewSession(json.loads(Path(sys.argv[1]).read_text()))
    def emit(message):
        print(json.dumps(message, ensure_ascii=False), flush=True)
    try:
        session.start()
        for line in sys.stdin:
            if line.strip():
                session.forward(json.loads(line), emit)
        return 0
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        session.evidence["error"] = "target_view_session_failed"
        session.save()
        print("Target-view session failed; inspect private artifacts.", file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
