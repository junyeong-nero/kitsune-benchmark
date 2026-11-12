"""Expanded experiment's ego CLI transport, with opt-in screenshot attachment.

The vendor guide and script execution are unchanged. A printed JSON screenshot receipt
is the CLI's documented image-viewer handoff, transported as an MCP image, not as text.
Only new PNGs inside this attempt's supplied screenshot directory are read. This does
not sandbox the vendor's Node runtime. The older MiniWoB wrapper is left unchanged.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark import ego_mcp  # noqa: E402

IMAGE_GUIDE = """

Benchmark image transport: use the screenshot directory supplied in the task. To view a
screenshot, print a JSON line: console.log(JSON.stringify({screenshot: await page.screenshot(
{path: '/absolute/supplied/directory/image.png'})})). The wrapper attaches that PNG as an
image in this tool result. Only PNGs newly written by this call in that directory qualify.
This is an image-viewer bridge, not an extra browser action or permission grant.
"""


def attach_images(result: dict, directory: Path | None, started_ns: int) -> dict:
    if directory is None:
        return result
    content = list(result.get("content", []))
    seen = set()
    for item in list(content):
        if item.get("type") != "text":
            continue
        for line in item.get("text", "").splitlines():
            try:
                receipt = json.loads(line)
            except ValueError:
                continue
            if not isinstance(receipt, dict) or set(receipt) != {"screenshot"} or not isinstance(receipt["screenshot"], str):
                continue
            path = Path(receipt["screenshot"])
            try:
                resolved = path.resolve()
                if (not path.is_absolute() or path.is_symlink() or not resolved.is_relative_to(directory.resolve())
                        or resolved in seen or path.suffix.lower() != ".png"):
                    raise ValueError("Screenshot path is outside the attempt directory or not a PNG.")
                stat = path.stat()
                if stat.st_mtime_ns < started_ns or not 8 <= stat.st_size <= 8_000_000:
                    raise ValueError("Screenshot must be new in this call and at most 8 MB.")
                data = path.read_bytes()
                if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Screenshot receipt does not name a PNG.")
                content.append({"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/png"})
                seen.add(resolved)
            except (OSError, ValueError) as error:
                content.append({"type": "text", "text": "Screenshot attachment failed: " + str(error)})
                result = {**result, "isError": True}
    return {**result, "content": content}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    describe, run_script = ego_mcp.describe, ego_mcp.run_script
    ego_mcp.describe = lambda binary: describe(binary) + IMAGE_GUIDE

    def call(binary, code):
        started = time.time_ns()
        return attach_images(run_script(binary, code), args.screenshots, started)

    ego_mcp.run_script = call
    return ego_mcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
