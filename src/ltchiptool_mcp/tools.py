# src/ltchiptool_mcp/tools.py
"""MCP tool implementations for ltchiptool-mcp.

Each public function is async, returns a dict, and delegates subprocess
work to runner.py. Family-specific knobs come from families.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from ltchiptool_mcp.families import get_strategy, is_supported, list_strategies
from ltchiptool_mcp.parsers import parse_list_boards
from ltchiptool_mcp.runner import run_dissect, run_list_boards, run_ltchiptool


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


def _validate_args(serial_port: str, family: str) -> dict | None:
    """Common validation. Returns an error dict or None if everything checks out."""
    if not is_supported(family):
        supported = sorted({s.name for s in list_strategies()})
        return {
            "error": "unsupported_family",
            "message": f"Family {family!r} is not in the supported list: {supported}",
        }
    if not Path(serial_port).exists():
        return {
            "error": "port_not_found",
            "message": f"Serial port {serial_port!r} does not exist",
        }
    return None


async def tool_prepare_chip_info(serial_port: str, family: str) -> dict:
    """Validate args and return operator instructions for the yank-restore.

    No subprocess. The agent calls this, relays operator_instructions to the
    operator, waits for 'go', then calls tool_start_chip_info with the same args.
    """
    err = _validate_args(serial_port, family)
    if err is not None:
        return err
    s = get_strategy(family)
    return {
        "operator_instructions": (
            f"Power up the target. Within {s.hitl_window_seconds} seconds of the "
            f"connect attempt, perform: {s.hitl_action}"
        ),
        "action": "yank_vcc",
        "window_seconds": s.hitl_window_seconds,
        "next_tool": "start_chip_info",
        "ready_to_start": True,
    }


async def tool_start_chip_info(serial_port: str, family: str) -> dict:
    """Run `ltchiptool flash info <family> -d <port>` and parse the chip info table."""
    err = _validate_args(serial_port, family)
    if err is not None:
        return err
    s = get_strategy(family)
    timeout = s.hitl_window_seconds + 5

    result = run_ltchiptool(
        ["flash", "info", s.ltchiptool_arg, "-d", serial_port],
        timeout=timeout,
    )
    if "error" in result or result["returncode"] != 0:
        # Differentiate HITL miss (timeout / connecting failure) from other errors.
        stderr = result.get("stderr", "")
        if (
            result["returncode"] == -1
            or "timeout" in stderr.lower()
            or "timeout" in (result.get("error") or "").lower()
            or result["duration_s"] >= timeout - 1
        ):
            return {
                "error": "hitl_window_missed",
                "message": (
                    "ltchiptool did not lock onto the chip within the connect "
                    "window. Retry start_chip_info with the same args after "
                    "the operator is ready to yank again."
                ),
                "stderr": stderr,
                "duration_s": result["duration_s"],
            }
        return {
            "error": "ltchiptool_failed",
            "message": stderr or "ltchiptool returned a non-zero exit code",
            "returncode": result["returncode"],
        }

    try:
        chip_info = s.chip_info_parser(result["stdout"])
    except ValueError as exc:
        return {
            "error": "parse_failed",
            "message": str(exc),
            "stdout_excerpt": result["stdout"][:500],
        }

    return {
        "chip_info": chip_info,
        "family": family,
        "serial_port": serial_port,
        "duration_s": result["duration_s"],
    }


def _resolve_uart_subpath(
    project_path: str | None,
    engagement_name: str | None,
    subdir: str,  # "raw" or "decrypted/<state>" or "logs"
) -> Path:
    """Resolve the target uart/<subdir>/ directory.

    Priority: project_path > engagement_name > error.
    Creates the directory if it does not exist.
    """
    if project_path:
        base = Path(project_path) / "uart" / subdir
    elif engagement_name:
        engagements_dir = Path(
            os.environ.get(
                "PIDEV_ENGAGEMENTS_DIR",
                str(Path(__file__).resolve().parents[2] / "engagements"),
            )
        )
        base = engagements_dir / engagement_name / "uart" / subdir
    else:
        raise ValueError("Either project_path or engagement_name is required")

    base.mkdir(parents=True, exist_ok=True)
    return base


async def tool_prepare_flash_read(
    serial_port: str,
    family: str,
    output_name: str | None = None,
    state_label: str | None = None,
    project_path: str | None = None,
    engagement_name: str | None = None,
) -> dict:
    err = _validate_args(serial_port, family)
    if err is not None:
        return err
    if not project_path and not engagement_name:
        return {
            "error": "no_target_dir",
            "message": "Either project_path or engagement_name is required",
        }

    try:
        raw_dir = _resolve_uart_subpath(project_path, engagement_name, "raw")
    except ValueError as exc:
        return {"error": "path_invalid", "message": str(exc)}

    if not output_name:
        output_name = f"flash_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.bin"
    out_path = raw_dir / output_name

    s = get_strategy(family)
    return {
        "operator_instructions": (
            f"Power up the target. Within {s.hitl_window_seconds} seconds of the "
            f"connect attempt, perform: {s.hitl_action} "
            f"After lock-on, the read takes ~3-5 minutes for 2 MiB."
        ),
        "action": "yank_vcc",
        "window_seconds": s.hitl_window_seconds,
        "resolved_paths": {"output": str(out_path)},
        "expected_size_bytes": s.flash_size_bytes,
        "next_tool": "start_flash_read",
        "ready_to_start": True,
    }


async def tool_start_flash_read(
    serial_port: str,
    family: str,
    output_name: str | None = None,
    state_label: str | None = None,
    project_path: str | None = None,
    engagement_name: str | None = None,
) -> dict:
    err = _validate_args(serial_port, family)
    if err is not None:
        return err
    if not project_path and not engagement_name:
        return {
            "error": "no_target_dir",
            "message": "Either project_path or engagement_name is required",
        }

    try:
        raw_dir = _resolve_uart_subpath(project_path, engagement_name, "raw")
    except ValueError as exc:
        return {"error": "path_invalid", "message": str(exc)}

    if not output_name:
        output_name = f"flash_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.bin"
    out_path = raw_dir / output_name

    s = get_strategy(family)
    result = run_ltchiptool(
        ["flash", "read", s.ltchiptool_arg, "-d", serial_port, str(out_path)],
        timeout=600,
    )

    if "error" in result or result["returncode"] != 0:
        stderr = result.get("stderr", "")
        if (
            "timeout" in stderr.lower()
            or "timeout" in (result.get("error") or "").lower()
        ):
            return {
                "error": "hitl_window_missed",
                "message": (
                    "ltchiptool did not lock onto the chip. Retry start_flash_read "
                    "with the same args after operator is ready to yank again."
                ),
                "stderr": stderr,
                "duration_s": result["duration_s"],
            }
        return {
            "error": "flash_read_failed",
            "message": stderr or "ltchiptool returned a non-zero exit code",
            "returncode": result["returncode"],
        }

    actual_size = out_path.stat().st_size if out_path.exists() else 0
    return {
        "dump_path": str(out_path),
        "size_bytes": actual_size,
        "expected_size_bytes": s.flash_size_bytes,
        "size_ok": actual_size == s.flash_size_bytes,
        "duration_s": result["duration_s"],
        "family": family,
    }


async def tool_dissect_dump(
    dump_path: str,
    family: str,
    state_label: str | None = None,
    project_path: str | None = None,
    engagement_name: str | None = None,
) -> dict:
    if not is_supported(family):
        supported = sorted({s.name for s in list_strategies()})
        return {
            "error": "unsupported_family",
            "message": f"Family {family!r} is not in the supported list: {supported}",
        }
    if not Path(dump_path).exists():
        return {
            "error": "input_not_found",
            "message": f"Dump file {dump_path!r} does not exist",
        }
    if not project_path and not engagement_name:
        return {
            "error": "no_target_dir",
            "message": "Either project_path or engagement_name is required",
        }

    label = state_label or "default"
    try:
        out_dir = _resolve_uart_subpath(
            project_path, engagement_name, f"decrypted/{label}"
        )
    except ValueError as exc:
        return {"error": "path_invalid", "message": str(exc)}

    s = get_strategy(family)
    result = run_dissect(
        cmd_template=s.dissect_command,
        output_dir=str(out_dir),
        dump_path=dump_path,
        timeout=90,
    )
    if "error" in result or result["returncode"] != 0:
        return {
            "error": "dissect_command_failed",
            "message": result.get("error") or result.get("stderr") or "non-zero exit",
            "returncode": result["returncode"],
        }

    # bk7231tools exits 0 and prints a NOTE on stdout when pycryptodome is
    # missing, then silently skips storage decryption. Treat as a hard error
    # so callers do not accept a partial result and theorize about why
    # _storage.json is absent.
    if "skipping storage decryption" in result["stdout"].lower():
        return {
            "error": "missing_storage_crypto_dep",
            "message": (
                "bk7231tools skipped storage decryption: pycryptodome is "
                "not installed in the runtime environment. Install with: "
                "pip install pycryptodome (or reinstall ltchiptool-mcp; "
                "pycryptodome is now a hard dep)."
            ),
            "stdout_excerpt": result["stdout"][:500],
        }

    try:
        parsed = s.dissect_parser(result["stdout"])
    except Exception as exc:
        return {
            "error": "parse_failed",
            "message": str(exc),
            "stdout_excerpt": result["stdout"][:500],
        }

    return {
        "family": family,
        "state_label": label,
        "dump_path": dump_path,
        "output_dir": str(out_dir),
        "rbl_containers": parsed["rbl_containers"],
        "storage_partition": parsed["storage_partition"],
        "user_param_key_present": parsed["user_param_key_present"],
        "duration_s": result["duration_s"],
    }
