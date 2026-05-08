# CLAUDE.md

Guidance for Claude Code when working with code in this repository.

## Project

ltchiptool-mcp is an MCP server wrapping ltchiptool + bk7231tools for chip-level
firmware extraction. Currently supports the BK7231 family (Tuya/IoT plugs);
architecture is extensible to other ltchiptool-supported families.

## Architecture

    MCP client (Claude Code, etc.)
      |
      stdio transport
      |
    ltchiptool-mcp (server.py)
      |
      tools.py -> runner.py -> subprocess.run(ltchiptool, bk7231tools)
      |
    USB serial (UART) -> Target chip

runner.py is the ONLY module that calls subprocess. Everything else routes
through it. Same pattern as connection.py in pm3-mcp and session.py in mitm-mcp.

parsers.py: pure text-to-dict, no I/O.
families.py: per-family strategy registry. Adding a family = adding a
FamilyStrategy entry, no other code changes.

## Safety Model

Three tiers enforced at the MCP server boundary:

- read-only: full autonomy (prepare_chip_info, prepare_flash_read,
  list_supported_families, list_boards)
- allowed-write: autonomous, logged (start_chip_info, start_flash_read,
  dissect_dump). All produce artifacts but cannot damage hardware.
- approval-write: reserved for future flash write wrapper. No MVP tools.

ltchiptool flash read and flash info cannot brick the chip. The HITL
primitive (yank-restore for BK7231) is timing, not safety.

## HITL flow

prepare_* tools return operator instructions. start_* tools run the actual
subprocess. The pair is stateless -- start can be re-called on a missed
window without re-preparing. Skill files document the call sequence; the
MCP itself does not enforce ordering.

## Build and Run

    pip install -e ".[dev]"
    pytest                  # unit tests
    pytest -m hardware      # integration, requires real BK7231 target

## Style

- Python 3.11+
- No emojis, no em-dashes in code, comments, commits, or docs
- Commit messages: short, to the point. No co-author footers.
