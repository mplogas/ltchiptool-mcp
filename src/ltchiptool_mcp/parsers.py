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
    """Parse `bk7231tools dissect_dump -e` output into structured info.

    Returns:
      - rbl_containers: list of {name, offset, size, encoding, extracted_to}
      - storage_partition: {offset, size_kib, key_count, keys, json_path} or None
      - user_param_key_present: bool
    """
    result: dict = {
        "rbl_containers": [],
        "storage_partition": None,
        "user_param_key_present": False,
    }

    rbl_pat = re.compile(
        r"^\s*0x([0-9a-fA-F]+):\s+(\w+)\s+-\s+\[encoding_algorithm=(\w+),\s+size=0x([0-9a-fA-F]+)\]"
    )
    extracted_pat = re.compile(r"^\s*extracted to\s+(.+)$")
    storage_header_pat = re.compile(
        r"^\s*0x([0-9a-fA-F]+):\s+(\d+)\s+KiB\s+-\s+(\d+)\s+keys"
    )
    storage_key_pat = re.compile(r"^\s*-\s+'([^']+)'")
    storage_json_pat = re.compile(r"^\s*extracted all keys to\s+(.+)$")
    user_param_present_pat = re.compile(r"^App code `user_param_key`:")
    user_param_not_found_pat = re.compile(r"^\s*-\s+not found!")

    in_storage = False
    pending_container: dict | None = None
    storage: dict | None = None
    saw_user_param_section = False

    for line in stdout.splitlines():
        m = rbl_pat.match(line)
        if m and not in_storage:
            if pending_container is not None:
                result["rbl_containers"].append(pending_container)
            pending_container = {
                "offset": int(m.group(1), 16),
                "name": m.group(2),
                "encoding": m.group(3),
                "size": int(m.group(4), 16),
                "extracted_to": None,
            }
            continue

        m = extracted_pat.match(line)
        if m and pending_container is not None and not in_storage:
            pending_container["extracted_to"] = m.group(1).strip()
            continue

        m = storage_header_pat.match(line)
        if m:
            if pending_container is not None:
                result["rbl_containers"].append(pending_container)
                pending_container = None
            storage = {
                "offset": int(m.group(1), 16),
                "size_kib": int(m.group(2)),
                "key_count": int(m.group(3)),
                "keys": [],
                "json_path": None,
            }
            in_storage = True
            continue

        if in_storage:
            m = storage_key_pat.match(line)
            if m:
                storage["keys"].append(m.group(1))
                continue
            m = storage_json_pat.match(line)
            if m:
                storage["json_path"] = m.group(1).strip()
                in_storage = False
                continue

        if user_param_present_pat.match(line):
            saw_user_param_section = True
            continue
        if saw_user_param_section and user_param_not_found_pat.match(line):
            result["user_param_key_present"] = False
            saw_user_param_section = False
            continue
        if saw_user_param_section and storage_key_pat.match(line):
            # Found a key under user_param_key section means it IS present
            result["user_param_key_present"] = True
            saw_user_param_section = False
            continue

    if pending_container is not None:
        result["rbl_containers"].append(pending_container)

    result["storage_partition"] = storage
    return result


def parse_list_boards(stdout: str) -> list[dict]:
    """Parse `ltchiptool list boards` output into a list of board dicts.

    Output format is a bordered markdown table:
        +---+---+---+---+
        | Name | Code | MCU / Flash / RAM | Family name |
        +---+---+---+---+
        | WB3S Wi-Fi Module | wb3s | BK7231T / 2 MiB / 256 KiB | beken-7231t |
        ...

    Returns dicts with keys: name, code, mcu, flash_size, ram_size,
    ltchiptool_family. The ltchiptool_family field uses ltchiptool's
    internal scheme (beken-7231n, realtek-ambz, lightning-ln882h, ...)
    which is NOT the same as the MCP's family parameter (bk7231n, bk7231t).
    """
    if not stdout.strip():
        return []

    boards: list[dict] = []
    pattern = re.compile(
        r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
    )

    for line in stdout.splitlines():
        if line.startswith("+") or not line.strip().startswith("|"):
            continue
        m = pattern.search(line)
        if not m:
            continue
        name, code, mcu_combined, family = (
            m.group(1).strip(),
            m.group(2).strip(),
            m.group(3).strip(),
            m.group(4).strip(),
        )
        # Filter the header row
        if name.lower() == "name" and code.lower() == "code":
            continue

        # MCU / Flash / RAM is slash-separated with extra whitespace
        parts = [p.strip() for p in mcu_combined.split("/")]
        if len(parts) != 3:
            continue
        mcu, flash_size, ram_size = parts

        boards.append({
            "name": name,
            "code": code,
            "mcu": mcu,
            "flash_size": flash_size,
            "ram_size": ram_size,
            "ltchiptool_family": family,
        })

    return boards
