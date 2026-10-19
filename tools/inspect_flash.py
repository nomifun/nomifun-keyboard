#!/usr/bin/env python3
"""Inspect a local ESP-IDF flash backup without decoding private storage.

Only the partition table at 0x8000 and app partitions are interpreted. App
extraction includes the ESP image header, segments, checksum padding and optional
SHA-256 trailer; unused partition space and data partitions are never exported.
This tool does not access serial ports or change a connected device.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any


PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_LENGTH = 0xC00
PARTITION_TABLE_SECTOR_LENGTH = 0x1000
PARTITION_ENTRY_SIZE = 32
PARTITION_MAGIC = 0x50AA
PARTITION_MD5_MAGIC = 0xEBEB
IMAGE_HEADER_SIZE = 24
IMAGE_MAX_SEGMENTS = 16
APP_DESCRIPTOR_SIZE = 256
APP_DESCRIPTOR_MAGIC = 0xABCD5432


def _text(value: bytes) -> str:
    return value.split(b"\0", 1)[0].decode("utf-8", errors="replace")


def _app_descriptor(payload: bytes) -> dict[str, Any]:
    if len(payload) < APP_DESCRIPTOR_SIZE:
        return {"valid": False, "error": "First segment is too short for an app descriptor"}
    magic = struct.unpack_from("<I", payload, 0)[0]
    if magic != APP_DESCRIPTOR_MAGIC:
        return {"valid": False, "magic": magic, "error": "Invalid app descriptor magic"}
    return {
        "valid": True,
        "magic": magic,
        "secure_version": struct.unpack_from("<I", payload, 4)[0],
        "version": _text(payload[16:48]),
        "project_name": _text(payload[48:80]),
        "build_time": _text(payload[80:96]),
        "build_date": _text(payload[96:112]),
        "idf_version": _text(payload[112:144]),
    }


def inspect_app(data: bytes, offset: int, size: int) -> dict[str, Any]:
    """Validate an app using only bytes within its declared partition."""
    result: dict[str, Any] = {"valid": False, "errors": []}
    errors = result["errors"]
    if offset < 0 or size < IMAGE_HEADER_SIZE or offset + size > len(data):
        errors.append("App partition is outside the backup or too small for a header")
        return result
    end = offset + size
    if data[offset] == 0xFF and data[offset:end].count(0xFF) == size:
        result["empty"] = True
        return result
    header = data[offset : offset + IMAGE_HEADER_SIZE]
    if header[0] != 0xE9:
        errors.append("Invalid ESP image magic (expected 0xE9)")
        return result
    segment_count = header[1]
    result["header"] = {
        "magic": header[0],
        "segment_count": segment_count,
        "spi_mode": header[2],
        "spi_speed_size": header[3],
        "entry_address": struct.unpack_from("<I", header, 4)[0],
        "chip_id": struct.unpack_from("<H", header, 12)[0],
        "min_chip_revision": header[14],
        "min_chip_revision_full": struct.unpack_from("<H", header, 15)[0],
        "max_chip_revision_full": struct.unpack_from("<H", header, 17)[0],
        "hash_appended": header[23],
    }
    if not 1 <= segment_count <= IMAGE_MAX_SEGMENTS:
        errors.append("Invalid ESP image segment count")
        return result
    if header[23] not in (0, 1):
        errors.append("Invalid hash_appended flag (expected 0 or 1)")
        return result

    cursor = offset + IMAGE_HEADER_SIZE
    checksum = 0xEF
    segments = []
    for index in range(segment_count):
        if cursor + 8 > end:
            errors.append(f"Segment {index} header exceeds the app partition")
            return result
        load_address, length = struct.unpack_from("<II", data, cursor)
        cursor += 8
        if cursor + length > end:
            errors.append(f"Segment {index} data exceeds the app partition")
            return result
        payload = data[cursor : cursor + length]
        if index == 0:
            result["descriptor"] = _app_descriptor(payload)
            if not result["descriptor"]["valid"]:
                errors.append(result["descriptor"]["error"])
        for value in payload:
            checksum ^= value
        segments.append({"index": index, "load_address": load_address, "length": length})
        cursor += length
    result["segments"] = segments

    # The checksum is the last byte of a 16-byte image block. Alignment is
    # relative to the image start, even when a malformed partition is unaligned.
    checksum_offset = offset + ((cursor - offset) | 15)
    if checksum_offset >= end:
        errors.append("Image checksum padding exceeds the app partition")
        return result
    result["checksum"] = {
        "stored": data[checksum_offset],
        "computed": checksum,
        "valid": data[checksum_offset] == checksum,
    }
    if not result["checksum"]["valid"]:
        errors.append("ESP image XOR checksum mismatch")
    image_end = checksum_offset + 1
    if header[23]:
        if image_end + 32 > end:
            errors.append("Appended SHA-256 exceeds the app partition")
            return result
        stored_hash = data[image_end : image_end + 32].hex()
        computed_hash = hashlib.sha256(data[offset:image_end]).hexdigest()
        result["appended_sha256"] = {
            "stored": stored_hash,
            "computed": computed_hash,
            "valid": stored_hash == computed_hash,
        }
        if stored_hash != computed_hash:
            errors.append("Appended SHA-256 mismatch")
        image_end += 32
    result["image_size"] = image_end - offset
    result["sha256"] = hashlib.sha256(data[offset:image_end]).hexdigest()
    result["valid"] = not errors
    return result


def inspect_flash(data: bytes, source: str = "<memory>") -> dict[str, Any]:
    """Return metadata only; never decode NVS or search flash for strings."""
    table: dict[str, Any] = {
        "offset": PARTITION_TABLE_OFFSET,
        "length_limit": PARTITION_TABLE_LENGTH,
        "valid": False,
        "md5": {"present": False, "valid": None},
        "errors": [],
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "input": {"path": source, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "partition_table": table,
        "partitions": [],
    }
    errors = table["errors"]
    table_end = PARTITION_TABLE_OFFSET + PARTITION_TABLE_LENGTH
    if len(data) < table_end:
        errors.append("Backup is too short for the partition table at 0x8000")
        return report

    ended = False
    for position in range(PARTITION_TABLE_OFFSET, table_end, PARTITION_ENTRY_SIZE):
        entry = data[position : position + PARTITION_ENTRY_SIZE]
        if entry == b"\xff" * PARTITION_ENTRY_SIZE:
            ended = True
            if any(value != 0xFF for value in data[position:table_end]):
                errors.append("Unexpected non-erased data after partition-table terminator")
            break
        magic = struct.unpack_from("<H", entry)[0]
        if magic == PARTITION_MD5_MAGIC:
            ended = True
            stored = entry[16:].hex()
            computed = hashlib.md5(data[PARTITION_TABLE_OFFSET:position]).hexdigest()
            table["md5"] = {"present": True, "valid": stored == computed, "stored": stored, "computed": computed}
            if entry[:16] != b"\xeb\xeb" + b"\xff" * 14:
                errors.append("Invalid partition-table MD5 record prefix")
            if stored != computed:
                errors.append("Partition-table MD5 mismatch")
            if any(value != 0xFF for value in data[position + PARTITION_ENTRY_SIZE : table_end]):
                errors.append("Unexpected non-erased data after partition-table MD5")
            break
        if magic != PARTITION_MAGIC:
            errors.append(f"Invalid partition magic at flash offset 0x{position:x}")
            break
        _, kind, subtype, offset, size, name, flags = struct.unpack("<HBBII16sI", entry)
        partition: dict[str, Any] = {
            "index": len(report["partitions"]),
            "name": _text(name),
            "type": kind,
            "type_name": {0: "app", 1: "data"}.get(kind, "custom"),
            "subtype": subtype,
            "offset": offset,
            "size": size,
            "flags": flags,
            "valid": True,
            "errors": [],
        }
        if size == 0:
            partition["errors"].append("Partition size is zero")
        if offset < PARTITION_TABLE_OFFSET + PARTITION_TABLE_SECTOR_LENGTH:
            partition["errors"].append("Partition overlaps the bootloader or partition-table area")
        if offset + size > len(data):
            partition["errors"].append("Partition exceeds the backup length")
        report["partitions"].append(partition)
    if not ended and not errors:
        errors.append("Partition table has no terminator or MD5 record")
    if not report["partitions"]:
        errors.append("Partition table has no entries")

    partitions = report["partitions"]
    for index, left in enumerate(partitions):
        for right in partitions[index + 1 :]:
            if left["offset"] < right["offset"] + right["size"] and right["offset"] < left["offset"] + left["size"]:
                left["errors"].append(f"Partition overlaps entry {right['index']}")
                right["errors"].append(f"Partition overlaps entry {left['index']}")
    for partition in partitions:
        partition["valid"] = not partition["errors"]
        if not partition["valid"]:
            errors.append(f"Partition {partition['index']} has invalid bounds or overlaps")
    table["valid"] = not errors

    # An untrusted or damaged partition table must never direct extraction.
    if table["valid"]:
        for partition in partitions:
            if partition["type"] == 0:
                partition["app"] = inspect_app(data, partition["offset"], partition["size"])
    return report


def extract_apps(data: bytes, report: dict[str, Any], destination: Path) -> list[Path]:
    """Export validated app image bytes, refusing to overwrite existing files."""
    if not report["partition_table"]["valid"]:
        raise ValueError("Refusing extraction from an invalid partition table")
    destination = destination.resolve()
    paths = []
    for partition in report["partitions"]:
        app = partition.get("app", {})
        if partition["type"] != 0 or not partition["valid"] or not app.get("valid"):
            continue
        offset, length = partition["offset"], app["image_size"]
        if length <= 0 or length > partition["size"] or offset < 0 or offset + length > len(data):
            raise ValueError("Refusing extraction of an out-of-bounds app image")
        payload = data[offset : offset + length]
        if hashlib.sha256(payload).hexdigest() != app["sha256"]:
            raise ValueError("App image changed since inspection")
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", partition["name"]).strip(".") or "app"
        filename = f"{partition['index']:02d}_{offset:08x}_{safe_name}.bin"
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / filename
        with path.open("xb") as handle:
            handle.write(payload)
        app["extracted_path"] = str(path)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path, help="Local full-flash binary backup")
    parser.add_argument("--output", type=Path, help="Write the JSON metadata report to this file")
    parser.add_argument("--extract-apps", type=Path, metavar="DIRECTORY", help="Export only validated application images")
    args = parser.parse_args(argv)
    try:
        source = args.backup.resolve()
        data = source.read_bytes()
        report = inspect_flash(data, str(source))
        if args.extract_apps:
            extract_apps(data, report, args.extract_apps)
        output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            if args.output.resolve() == source:
                raise ValueError("The report path must differ from the input backup")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        valid = report["partition_table"]["valid"] and all(
            partition.get("app", {}).get("valid", True) or partition.get("app", {}).get("empty", False)
            for partition in report["partitions"]
        )
        return 0 if valid else 2
    except (OSError, ValueError) as error:
        print(f"inspect_flash: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
