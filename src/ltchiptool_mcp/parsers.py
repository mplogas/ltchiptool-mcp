"""Text parsers for ltchiptool and bk7231tools output.

Each parser is pure: input is the captured stdout text, output is a
structured dict. No subprocess access, no I/O.
"""

from __future__ import annotations

import re


def parse_bk7231_chip_info(stdout: str) -> dict:
    """Parse `ltchiptool flash info bk7231n` output into a structured dict.

    Looks for the table between the `+----+` borders. Returns keys:
      - chip_type           (e.g. "BK7231N")
      - bootloader          (e.g. "BK7231N 1.0.1")
      - chip_id             (e.g. "0x7231c")
      - mac_address         (XX:XX:XX:XX:XX:XX)
      - flash_id            (3 hex bytes space-separated)
      - flash_size_bytes    (int)
      - encryption_key      (4 hex words space-separated)
    """
    rows = _extract_table_rows(stdout)
    if not rows:
        raise ValueError(
            "No chip info table found in output. "
            "Did ltchiptool actually connect?"
        )

    info: dict = {}
    for key, value in rows.items():
        norm = key.lower().strip()
        if norm == "chip type":
            info["chip_type"] = value
        elif norm == "bootloader type":
            info["bootloader"] = value
        elif norm == "chip id":
            info["chip_id"] = value
        elif norm == "mac address":
            info["mac_address"] = value
        elif norm == "flash id":
            info["flash_id"] = value
        elif norm == "flash size (detected)":
            info["flash_size_bytes"] = _parse_flash_size(value)
        elif norm == "encryption key":
            info["encryption_key"] = value

    return info


def _extract_table_rows(stdout: str) -> dict[str, str]:
    """Extract key/value rows from the bordered table ltchiptool prints.

    Format:
        +-----------------------+-------------------------------------+
        | Name                  | Value                               |
        +-----------------------+-------------------------------------+
        | Chip Type             | BK7231N                             |
        ...

    Returns {key: value} skipping blank rows.
    """
    rows: dict[str, str] = {}
    pattern = re.compile(r"\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|")
    for line in stdout.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        key, value = m.group(1).strip(), m.group(2).strip()
        if not key or key.lower() == "name":
            continue
        if not value:
            continue
        rows[key] = value
    return rows


def _parse_flash_size(text: str) -> int:
    """Parse '2 MiB' / '4 MiB' into bytes."""
    m = re.match(r"(\d+)\s*MiB", text)
    if m:
        return int(m.group(1)) * 1024 * 1024
    m = re.match(r"(\d+)\s*KiB", text)
    if m:
        return int(m.group(1)) * 1024
    raise ValueError(f"Cannot parse flash size: {text!r}")


def parse_bk7231_dissect_dump(stdout: str) -> dict:
    """Stub -- implemented in the dissect_dump task."""
    raise NotImplementedError("Filled in by the dissect_dump parser task.")


def parse_list_boards(stdout: str) -> list[dict]:
    """Stub -- implemented in the list_boards parser task."""
    raise NotImplementedError("Filled in by the list_boards parser task.")
