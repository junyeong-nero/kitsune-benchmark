"""No-model native MCP catalog checks, before a pair's agents are launched."""
from __future__ import annotations

from pathlib import Path

from .personal_session import NativeSession
from .specs import Server

STANDARD_UI_PROFILE = "legacy-ui-23"


def preflight_catalog(server: Server, expected: tuple[str, ...], env: dict[str, str], path: Path) -> dict:
    """List only; never seed a fixture, call a browser tool or approve a prompt.

    Validate the names exposed by the configured allowlist, retaining full native schemas and
    initialization metadata for review. This is a separate native connection, not an attestation
    that a dynamic server cannot change its catalog later in the model's session.
    """
    if path.exists():
        raise ValueError(f"Catalog evidence already exists: {path}")
    session = NativeSession({"target": server.id, "upstream": [server.command, *server.args],
                             "enabled_tools": list(server.enabled_tools), "metadata_path": str(path)})
    session.metadata.update(model_invoked=False, expected_tools=sorted(expected), catalog_valid=False)
    try:
        session.start(env=env)
        initialized = session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "benchmark-catalog-preflight", "version": "1"}}, role="agent")
        if "error" in initialized:
            raise ValueError(f"Catalog initialize failed for {server.id}")
        session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        params, cursors, names = {}, set(), []
        while True:
            response = session.request("tools/list", params, role="agent")
            result = response.get("result", {})
            tools = result.get("tools")
            if "error" in response or not isinstance(tools, list):
                raise ValueError(f"Invalid catalog for {server.id}")
            for tool in tools:
                if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not tool["name"]:
                    raise ValueError(f"Invalid tool name for {server.id}")
                names.append(tool["name"])
            cursor = result.get("nextCursor")
            if cursor is None:
                break
            if not isinstance(cursor, str) or not cursor or cursor in cursors:
                raise ValueError(f"Invalid/repeated catalog cursor for {server.id}")
            cursors.add(cursor)
            params = {"cursor": cursor}
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate catalog tool names for {server.id}")
        exposed = sorted(n for n in names if not server.enabled_tools or n in server.enabled_tools)
        missing, unexpected = sorted(set(expected) - set(exposed)), sorted(set(exposed) - set(expected))
        session.metadata.update(exposed_tools=exposed, missing_tools=missing, unexpected_tools=unexpected)
        if missing or unexpected:
            raise ValueError(f"Catalog mismatch for {server.id}: missing={missing}, unexpected={unexpected}; no model started")
        session.metadata["catalog_valid"] = True
        return session.metadata
    except (OSError, ValueError, KeyError, TypeError) as error:
        session.metadata["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        session.close()
        session.write_private_json(path, session.metadata)
