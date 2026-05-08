# src/ltchiptool_mcp/tools.py
"""MCP tool implementations for ltchiptool-mcp.

Each public function is async, returns a dict, and delegates subprocess
work to runner.py. Family-specific knobs come from families.py.
"""

from __future__ import annotations

from ltchiptool_mcp.families import list_strategies
from ltchiptool_mcp.parsers import parse_list_boards
from ltchiptool_mcp.runner import run_list_boards


async def tool_list_supported_families() -> dict:
    """Return the registered family strategies."""
    families = []
    for s in list_strategies():
        families.append({
            "name": s.name,
            "ltchiptool_arg": s.ltchiptool_arg,
            "hitl_action": s.hitl_action,
            "hitl_window_seconds": s.hitl_window_seconds,
            "flash_size_bytes": s.flash_size_bytes,
        })
    return {"families": families, "count": len(families)}


async def tool_list_boards(query: str | None = None) -> dict:
    """Return all boards ltchiptool knows about, optionally filtered by query."""
    result = run_list_boards(timeout=10)
    if result["returncode"] != 0 or "error" in result:
        return {
            "error": "list_boards_failed",
            "message": result.get("error") or result.get("stderr", ""),
            "returncode": result["returncode"],
        }
    boards = parse_list_boards(result["stdout"])
    if query:
        q = query.lower()
        boards = [b for b in boards if q in b.get("name", "").lower()]
    return {"boards": boards, "count": len(boards)}
