"""ltchiptool-mcp server -- stdio transport.

Same shape as pm3-mcp's server.py: TOOL_DEFINITIONS, classify-then-dispatch,
_confirmed gate for approval-write tools (none in MVP, kept for symmetry).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ltchiptool_mcp.safety import classify_tool, SafetyTier
from ltchiptool_mcp import tools

logger = logging.getLogger("ltchiptool-mcp")

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ENGAGEMENTS_DIR = Path(
    os.environ.get("PIDEV_ENGAGEMENTS_DIR", str(_PACKAGE_ROOT / "engagements"))
)

app = Server("ltchiptool-mcp")


_FAMILY_PROP = {
    "type": "string",
    "description": "Chip family (e.g. bk7231n, bk7231t). Use list_supported_families to see registered.",
}
_PORT_PROP = {
    "type": "string",
    "description": "Serial device path (e.g. /dev/ttyUSB0). FT232 dongles typically appear here. /dev/ttyACM* are reserved for BP6/PM3.",
}
_ENGAGEMENT_PATH_PROP = {
    "type": "string",
    "description": "Path to an engagement folder (from project-mcp). When provided, writes to <engagement_path>/uart/ instead of standalone engagement.",
}
_ENGAGEMENT_NAME_PROP = {
    "type": "string",
    "description": "Standalone engagement name. Mutually optional with engagement_path; one is required for output-producing tools.",
}


# Duration class convention (consistent across pidev-sec tool MCPs):
#   instant    -- <1 s wall clock, foregroundable always
#   fast       -- 1-10 s, foregroundable
#   slow       -- 10 s-2 min, background-dispatch recommended (or required if
#                 the agent has parallel work like a yank to fire mid-window)
#   very-slow  -- >2 min, background-dispatch effectively required


TOOL_DEFINITIONS = [
    Tool(
        name="prepare_chip_info",
        description=(
            "Validate args and return operator instructions for the yank-restore. "
            "No subprocess. Pair with start_chip_info. "
            "[read-only] [Duration: instant.]"
        ),
        inputSchema={
            "type": "object",
            "properties": {"serial_port": _PORT_PROP, "family": _FAMILY_PROP},
            "required": ["serial_port", "family"],
        },
    ),
    Tool(
        name="start_chip_info",
        description=(
            "Run `ltchiptool flash info`. Blocks during the HITL window. Returns "
            "structured chip info dict (chip type, MAC, encryption key, flash size). "
            "[allowed-write] [Duration: slow (~13-25 s -- HITL retry window). "
            "Orchestration: when pairing with psu-mcp.yank_restore to enter "
            "bootloader, dispatch THIS call in a background subagent FIRST, then "
            "wait ~10 s for the subprocess to actually open the port, then fire "
            "yank_restore from the main agent. ltchiptool opens/closes the port "
            "per retry -- do NOT poll fuser to sync; use a blind sleep. See "
            "skills/ltchiptool-probe.md section 3a.]"
        ),
        inputSchema={
            "type": "object",
            "properties": {"serial_port": _PORT_PROP, "family": _FAMILY_PROP},
            "required": ["serial_port", "family"],
        },
    ),
    Tool(
        name="prepare_flash_read",
        description=(
            "Validate args, resolve output path, return operator instructions. "
            "No subprocess. Pair with start_flash_read. "
            "[read-only] [Duration: instant.]"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "serial_port": _PORT_PROP,
                "family": _FAMILY_PROP,
                "output_name": {"type": "string", "description": "Optional dump filename"},
                "state_label": {"type": "string", "description": "Optional label like factory_a, paired"},
                "engagement_path": _ENGAGEMENT_PATH_PROP,
                "engagement_name": _ENGAGEMENT_NAME_PROP,
            },
            "required": ["serial_port", "family"],
        },
    ),
    Tool(
        name="start_flash_read",
        description=(
            "Run `ltchiptool flash read`. Long-running (~3-5 min for 2 MiB; "
            "measured 195 s on a Gosund SP112). Returns dump path, actual size, "
            "expected size, duration. "
            "[allowed-write] [Duration: very-slow (>2 min). Background-dispatch "
            "required unless the agent has nothing else to do. Same HITL "
            "orchestration as start_chip_info if the chip isn't already in "
            "bootloader. Once it locks, the read runs to completion without "
            "further yank.]"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "serial_port": _PORT_PROP,
                "family": _FAMILY_PROP,
                "output_name": {"type": "string"},
                "state_label": {"type": "string"},
                "engagement_path": _ENGAGEMENT_PATH_PROP,
                "engagement_name": _ENGAGEMENT_NAME_PROP,
            },
            "required": ["serial_port", "family"],
        },
    ),
    Tool(
        name="dissect_dump",
        description=(
            "Run the family's dissect command (e.g. bk7231tools dissect_dump -e). "
            "Decrypts and extracts partitions from a flash dump. No HITL. "
            "[allowed-write] [Duration: slow (~30-90 s on a 2 MiB dump). "
            "Foregroundable; background-dispatch only if the agent has other "
            "work to do during.]"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "dump_path": {"type": "string", "description": "Path to the .bin produced by start_flash_read"},
                "family": _FAMILY_PROP,
                "state_label": {"type": "string"},
                "engagement_path": _ENGAGEMENT_PATH_PROP,
                "engagement_name": _ENGAGEMENT_NAME_PROP,
            },
            "required": ["dump_path", "family"],
        },
    ),
    Tool(
        name="list_supported_families",
        description=(
            "Return the strategy registry of MCP-validated families. Authoritative "
            "for 'will end-to-end work?'. "
            "[read-only] [Duration: instant (in-memory).]"
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="list_boards",
        description=(
            "Return all boards ltchiptool knows about, each with vendor/product/family. "
            "Useful for module-name to family resolution. "
            "[read-only] [Duration: fast (~1-2 s -- spawns ltchiptool subprocess).]"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional substring filter on board names"},
            },
            "required": [],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_DEFINITIONS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name in {"prepare_flash_read", "start_flash_read", "dissect_dump"} and "project_path" in arguments:
        return [TextContent(type="text", text=json.dumps(
            {"error": "renamed_argument",
             "message": "project_path was renamed to engagement_path in v0.3; "
                        "pass engagement_path instead."}, default=str))]
    tier = classify_tool(name)  # raises on unknown

    # _confirmed gate kept for symmetry with other MCPs. No MVP tool uses it.
    if tier == SafetyTier.APPROVAL_WRITE:
        if not arguments.get("_confirmed", False):
            return [TextContent(
                type="text",
                text=json.dumps({
                    "confirmation_required": True,
                    "tool": name,
                    "arguments": arguments,
                    "message": "APPROVAL REQUIRED. Re-call with _confirmed=true to execute.",
                }),
            )]
        arguments = {k: v for k, v in arguments.items() if k != "_confirmed"}

    try:
        if name == "prepare_chip_info":
            result = await tools.tool_prepare_chip_info(
                serial_port=arguments["serial_port"],
                family=arguments["family"],
            )
        elif name == "start_chip_info":
            result = await tools.tool_start_chip_info(
                serial_port=arguments["serial_port"],
                family=arguments["family"],
            )
        elif name == "prepare_flash_read":
            result = await tools.tool_prepare_flash_read(
                serial_port=arguments["serial_port"],
                family=arguments["family"],
                output_name=arguments.get("output_name"),
                state_label=arguments.get("state_label"),
                engagement_path=arguments.get("engagement_path"),
                engagement_name=arguments.get("engagement_name"),
            )
        elif name == "start_flash_read":
            result = await tools.tool_start_flash_read(
                serial_port=arguments["serial_port"],
                family=arguments["family"],
                output_name=arguments.get("output_name"),
                state_label=arguments.get("state_label"),
                engagement_path=arguments.get("engagement_path"),
                engagement_name=arguments.get("engagement_name"),
            )
        elif name == "dissect_dump":
            result = await tools.tool_dissect_dump(
                dump_path=arguments["dump_path"],
                family=arguments["family"],
                state_label=arguments.get("state_label"),
                engagement_path=arguments.get("engagement_path"),
                engagement_name=arguments.get("engagement_name"),
            )
        elif name == "list_supported_families":
            result = await tools.tool_list_supported_families()
        elif name == "list_boards":
            result = await tools.tool_list_boards(query=arguments.get("query"))
        else:
            raise ValueError(f"Unknown tool: {name}")
    except KeyError as exc:
        result = {"error": "missing_argument", "message": str(exc)}

    return [TextContent(type="text", text=json.dumps(result, default=str))]


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())
