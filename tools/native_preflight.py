#!/usr/bin/env python3
"""Offline binding/image/recovery preflight. Never opens a serial port or writes Flash.

Only public chip identity, partition-table and application metadata are reported.
The full original backup remains private; no data partition is interpreted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from inspect_flash import inspect_app, inspect_flash


def mac(log: str) -> str:
    values = re.findall(r"MAC: ([0-9a-fA-F:]{17})", log)
    if not values or len(set(value.lower() for value in values)) != 1:
        raise ValueError("ROM log does not prove one stable MAC")
    return values[0].lower()


def run(args: argparse.Namespace) -> dict:
    original = args.backup.read_bytes()
    image = args.image.read_bytes()
    identity = json.loads(args.identity.read_text(encoding="utf-8"))
    rom_mac = mac(args.rom_log.read_text(encoding="utf-8"))
    read_log = args.read_log.read_text(encoding="utf-8")
    if mac(read_log) != rom_mac:
        raise ValueError("Flash read and ROM identity refer to different chips")
    if identity["usb"]["serial_number"].lower() != rom_mac:
        raise ValueError("USB identity and current ROM MAC do not match")
    if rom_mac.replace(":", "") not in str(args.backup.resolve()).lower():
        raise ValueError("Recovery path is not bound to current chip MAC")
    if len(original) != 0x1000000 or "Read 16777216 bytes at 0x00000000" not in read_log:
        raise ValueError("Full 16 MiB recovery backup not proven complete")
    security = args.security_log.read_text(encoding="utf-8")
    if "Secure Boot: Disabled" not in security or "Flash Encryption: Disabled" not in security:
        raise ValueError("Security policy requires a different recovery review")
    flash = inspect_flash(original, str(args.backup.resolve()))
    if not flash["partition_table"]["valid"]:
        raise ValueError("Original partition table failed validation")
    captured = args.partition_capture.read_bytes()
    if captured != original[0x8000:0x9000]:
        raise ValueError("Independent actual partition read does not match backup")
    source = []
    for line in args.partition_source.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        values = [value.strip() for value in line.split(",")]
        source.append((values[0], int(values[3], 0), int(values[4], 0)))
    actual = [(p["name"], p["offset"], p["size"]) for p in flash["partitions"]]
    if source != actual:
        raise ValueError("Current actual partition layout differs from build source")
    candidate = inspect_app(image, 0, len(image))
    if not candidate["valid"] or candidate["descriptor"]["version"] != "0.3-screen.2":
        raise ValueError("Candidate image descriptor/checksum/hash invalid")
    slot = next(p for p in flash["partitions"] if p["name"] == "ota_0")
    if slot["offset"] != 0x20000 or len(image) > slot["size"]:
        raise ValueError("Candidate does not fit the actual application slot")
    if not slot.get("app", {}).get("valid"):
        raise ValueError("Original application recovery image is invalid")
    applications = [{"name": p["name"], "offset": p["offset"], "size": p["size"],
                     "valid": p.get("app", {}).get("valid", False),
                     "empty": p.get("app", {}).get("empty", False),
                     "descriptor": p.get("app", {}).get("descriptor"),
                     "sha256": p.get("app", {}).get("sha256")}
                    for p in flash["partitions"] if p["type"] == 0]
    return {"status": "ready_for_explicit_flash_approval", "device_written": False,
            "mac": rom_mac, "port": identity["usb"]["port"],
            "current_firmware": identity["device_info"]["firmware_version"],
            "native_protocol_available": identity["device_info"].get("native_keyboard_protocol") == 1,
            "recovery_backup": {"path": str(args.backup.resolve()), "bytes": len(original),
                                "sha256": hashlib.sha256(original).hexdigest()},
            "partition_table_md5_valid": True, "partition_source_matches_actual": True,
            "independent_partition_read_matches": True, "applications": applications,
            "candidate": {"path": str(args.image.resolve()), "bytes": len(image),
                          "sha256": hashlib.sha256(image).hexdigest(),
                          "descriptor": candidate["descriptor"],
                          "application_offset": slot["offset"], "slot_bytes": slot["size"]},
            "security": {"secure_boot": False, "flash_encryption": False},
            "preserve": ["bootloader", "partition_table", "nvs", "nvs_keys", "otadata", "storage", "efuse"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("backup", "image", "identity", "rom-log", "security-log", "read-log", "partition-capture", "partition-source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = run(args)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output.resolve() in {args.backup.resolve(), args.image.resolve()}:
        raise ValueError("Report must not overwrite an image")
    args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()



