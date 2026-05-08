# ltchiptool-mcp

MCP server wrapping [ltchiptool](https://github.com/libretiny-eu/ltchiptool) and [bk7231tools](https://github.com/tuya-cloudcutter/bk7231tools) for chip-level firmware extraction. Drives the BK7231 family (Tuya/IoT plugs) over UART, dumps full flash, decrypts and extracts partitions. Exposes operations as [Model Context Protocol](https://modelcontextprotocol.io/) tools over stdio transport.

Built for use with Claude Code on a Raspberry Pi 5, but works with any MCP client and any USB-UART substrate.

## What it does

- **Chip info:** detect chip type, bootloader, MAC, flash size, and per-chip encryption key
- **Flash dump:** full encrypted flash read via UART (yank-restore HITL for the connect window)
- **Partition extraction:** decrypt + dissect into bootloader / app / storage JSON
- **Discovery:** look up boards in ltchiptool's catalog (CB3S, WB3S, CUCO-Z1-N, etc.) to map module silkscreen to chip family
- **Substrate-agnostic:** any USB-UART path works (FT232, BP6 bridge mode, etc.). External 3.3V supply recommended for BK7231 (BP6 onboard PSU trips on inrush).

## Requirements

- Python 3.11+
- User in `dialout` group for serial access (`sudo usermod -aG dialout $USER`)
- A USB-UART dongle (FT232 or similar) and an external 3.3V supply (lab PSU, regulated buck, or Pi GPIO header pin 1)

## Install

```bash
git clone https://github.com/mplogas/ltchiptool-mcp.git
cd ltchiptool-mcp
pip install -e ".[dev]"
```

`bk7231tools` is a transitive dependency of ltchiptool, no separate install needed.

## MCP Client Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "ltchiptool": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "ltchiptool_mcp"],
      "env": {
        "PIDEV_ENGAGEMENTS_DIR": "/path/to/engagements"
      }
    }
  }
}
```

`PIDEV_ENGAGEMENTS_DIR` controls where standalone-engagement output is written. Defaults to `./engagements/` relative to the package root.

## Tools

| Tool | Safety Tier | Description |
|------|-------------|-------------|
| `prepare_chip_info` | read-only | Operator instructions for yank-restore. No subprocess. |
| `start_chip_info` | allowed-write | Run `ltchiptool flash info`. Returns chip info dict (type, MAC, encryption key, flash size). |
| `prepare_flash_read` | read-only | Validate args, resolve output path, return operator instructions. |
| `start_flash_read` | allowed-write | Run `ltchiptool flash read`. Long-running (~3-5 min for 2 MiB). |
| `dissect_dump` | allowed-write | Run family's dissect command. Decrypts + extracts partitions. |
| `list_supported_families` | read-only | Strategy registry of validated families. |
| `list_boards` | read-only | All boards ltchiptool knows about, each with vendor/product/family. |

### prepare/start protocol

`prepare_*` and `start_*` tools come in pairs and are stateless. The natural agent flow:

1. Agent calls `prepare_chip_info(serial_port, family)` -- gets operator instructions
2. Agent relays instructions to operator, waits for "ready"
3. Agent calls `start_chip_info(serial_port, family)` with the same args -- runs ltchiptool

If the HITL window is missed, `start_*` returns `{"error": "hitl_window_missed", ...}` and the agent re-invokes `start_*` (no need to re-prepare). prepare and start are independently callable; calling start without prepare just skips the operator briefing.

## Safety Model

Three tiers enforced at the MCP server boundary:

- **read-only:** full autonomy, no side effects
- **allowed-write:** autonomous execution, all calls logged
- **approval-write:** reserved for future `flash write` wrapper (no MVP tools)

ltchiptool's `flash read` and `flash info` cannot brick the chip -- they are read-only operations from the chip's perspective. The HITL primitive is timing, not safety.

## Architecture

```
mitm-mcp client (Claude Code, etc.)
  |
  stdio transport
  |
ltchiptool-mcp (server.py)
  |
  tools.py -> runner.py -> subprocess.run("ltchiptool ...")
                        -> subprocess.run("bk7231tools ...")
  |
USB serial (UART) -> Target chip
```

`runner.py` is the only module that calls `subprocess`. Everything else routes through it. `parsers.py` handles text-to-dict for ltchiptool's table output and bk7231tools' container/storage output. `families.py` holds the per-family strategy registry.

## Family scope

MVP: BK7231N + BK7231T (Tuya/IoT plug ecosystem, share the same yank-restore procedure).

The architecture supports any ltchiptool family. New families register a `FamilyStrategy` in `families.py` with their own `ltchiptool_arg`, HITL action description, dissect command, and parsers. We do not promise families work until we have target hardware to validate.

## Tests

```bash
pytest                       # all unit tests
pytest -m hardware           # integration, requires real BK7231 target
```

The hardware tests are gated by `pytest.mark.hardware` and skipped by default.

## Why a separate MCP from buspirate-mcp

ESP-class workflows depend on the BP6's bridge mode + esptool, so they live in buspirate-mcp. BK7231-class workflows do not -- the BP6 onboard PSU trips on Beken inrush, so external power is required, and the substrate is whatever USB-UART works. Decoupling the chip-family extraction from the BP6 substrate keeps both submodules focused.
