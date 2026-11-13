"""Import-only legacy configuration/catalog probe, run in the selected Kitsune environment.

Do not call the Kitsune CLI/main, start MCP sessions, or invoke browser tools. This
worker deliberately has no benchmark-package imports (the project's dependencies differ).
"""
import asyncio
import json
from pathlib import Path


def main():
    from kitsune import server

    print(json.dumps({
        "server_file": str(Path(server.__file__).resolve()),
        "enabled_caps": sorted(server.ENABLED_CAPS),
        "published_caps": sorted(server.PUBLISHED_CAPS),
        # Revisions predating the opt-in scripting surface have no SCRIPTING flag.
        "scripting": getattr(server, "SCRIPTING", False),
        "tools": [tool.model_dump(mode="json", exclude_none=True)
                  for tool in asyncio.run(server.mcp.list_tools())],
    }))


if __name__ == "__main__":
    main()
