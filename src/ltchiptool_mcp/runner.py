"""Single owner of subprocess.run for ltchiptool and bk7231tools.

Tools call into here, never subprocess directly. Same pattern as
connection.py in pm3-mcp and session.py in mitm-mcp.

All functions return dicts with stdout/stderr/returncode/duration_s.
On exceptional failure (timeout, missing binary), the dict has an
'error' key. Callers check for that before parsing stdout.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from typing import Any

log = logging.getLogger(__name__)


class LtchiptoolNotFoundError(RuntimeError):
    """Raised when the ltchiptool binary cannot be located."""


def _find_ltchiptool() -> str:
    found = shutil.which("ltchiptool")
    if found:
        return found
    raise LtchiptoolNotFoundError(
        "ltchiptool not found on PATH. Install with: pip install ltchiptool"
    )


def run_ltchiptool(args: list[str], timeout: int) -> dict[str, Any]:
    """Run `ltchiptool <args>`. Returns dict with stdout/stderr/returncode/duration_s."""
    binary = _find_ltchiptool()
    argv = [binary, *args]
    log.info("running: %s", " ".join(argv))

    start = time.monotonic()
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "returncode": -1,
            "duration_s": time.monotonic() - start,
            "error": f"Timeout after {timeout}s",
        }
    except OSError as exc:
        return {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "duration_s": time.monotonic() - start,
            "error": f"OSError: {exc}",
        }

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "duration_s": time.monotonic() - start,
    }


def run_dissect(
    cmd_template: list[str],
    output_dir: str,
    dump_path: str,
    timeout: int,
) -> dict[str, Any]:
    """Run a family's dissect command (e.g. bk7231tools dissect_dump -e).

    cmd_template: argv prefix from FamilyStrategy.dissect_command.
                  If it begins with 'python', substitute the current interpreter.
    output_dir:   value passed via -O (trailing slash added).
    dump_path:    final positional argument.
    """
    argv = list(cmd_template)
    if argv and argv[0] == "python":
        argv[0] = sys.executable

    out = output_dir.rstrip("/") + "/"
    argv.extend(["-O", out, dump_path])

    log.info("running: %s", " ".join(argv))
    start = time.monotonic()
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "returncode": -1,
            "duration_s": time.monotonic() - start,
            "error": f"Timeout after {timeout}s",
        }
    except OSError as exc:
        return {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "duration_s": time.monotonic() - start,
            "error": f"OSError: {exc}",
        }

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "duration_s": time.monotonic() - start,
    }


def run_list_boards(timeout: int = 10) -> dict[str, Any]:
    """Run `ltchiptool list boards`."""
    return run_ltchiptool(["list", "boards"], timeout=timeout)
