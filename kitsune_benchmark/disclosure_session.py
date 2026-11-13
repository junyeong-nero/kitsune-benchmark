"""Opt-in experimental relay; production personal_session remains unchanged.

Enrichment is UI-only, and its extra RPCs are recorded as role=disclosure.
Run as an absolute script from the isolated model workspace.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.personal_session import NativeSession


class DisclosureSession(NativeSession):
    def __init__(self, config):
        super().__init__(config)
        self.policy = config.get("disclosure_policy", "native")
        if self.policy not in {"native", "rich"}:
            raise ValueError("Unknown disclosure policy")
        if config["target"] != "kitsune":
            raise ValueError("Disclosure experiment is Kitsune-only")

    def native_request(self, method, params=None, **kwargs):
        return super().request(method, params, **kwargs)

    def request(self, method, params=None, *, notify=None, role="harness"):
        if self.policy != "rich" or role != "agent" or method != "tools/call":
            return self.native_request(method, params, notify=notify, role=role)
        effective = copy.deepcopy(params)
        name = effective.get("name")
        args = effective.setdefault("arguments", {})
        if name == "browser_tabs" and args.get("action", "list") == "list":
            args["include_active"] = True
        elif name == "browser_snapshot":
            args["text"] = True
        if effective != params:
            self.diagnostic("disclosure_override", tool=name,
                            original_arguments=params.get("arguments", {}), effective_arguments=args)
        result = self.native_request(method, effective, notify=notify, role=role)
        if name != "browser_page_text" or "error" in result or result.get("result", {}).get("isError"):
            return result
        snapshot_args = {"text": False}
        if "tab_id" in args:
            snapshot_args["tab_id"] = args["tab_id"]
        supplement = self.native_request("tools/call", {
            "name": "browser_snapshot", "arguments": snapshot_args}, notify=notify, role="disclosure")
        extra = supplement.get("result", {})
        failed = "error" in supplement or bool(extra.get("isError"))
        output = copy.deepcopy(result)
        original = output.setdefault("result", {})
        contents = original.setdefault("content", [])
        contents.append({"type": "text", "text":
            "Additional actionable context (fresh snapshot refs; original page text retained):"
            if not failed else "Additional actionable context unavailable; original page text retained."})
        contents.extend(copy.deepcopy(extra.get("content", [])))
        if isinstance(original.get("structuredContent"), dict):
            original["structuredContent"]["additional_actionable_context"] = {
                "failed": failed, "content": copy.deepcopy(extra.get("content", []))}
        self.diagnostic("disclosure_delivered", tool=name, supplement_failed=failed,
                        delivered_text_bytes=sum(len(c.get("text", "").encode())
                                                 for c in contents if c.get("type") == "text"))
        return output


def main():
    session = DisclosureSession(json.loads(Path(sys.argv[1]).read_text()))
    def emit(message):
        print(json.dumps(message, ensure_ascii=False), flush=True)
    try:
        session.start()
        for line in sys.stdin:
            if line.strip():
                session.forward(json.loads(line), emit)
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        session.evidence["error"] = "disclosure_session_failed"
        session.save()
        print("Disclosure session failed; inspect private artifacts.", file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
