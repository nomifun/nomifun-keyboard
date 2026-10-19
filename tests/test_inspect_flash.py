"""Synthetic bounds, integrity and privacy tests for offline flash inspection."""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "inspect_flash.py"
SPEC = importlib.util.spec_from_file_location("inspect_flash", MODULE_PATH)
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)


def make_app(*, append_hash=True, descriptor_magic=0xABCD5432):
    header = bytearray(24)
    header[0:4] = bytes((0xE9, 2, 2, 0x2F))
    struct.pack_into("<I", header, 4, 0x40370000)
    struct.pack_into("<H", header, 12, 9)
    header[23] = int(append_hash)
    descriptor = bytearray(256)
    struct.pack_into("<I", descriptor, 0, descriptor_magic)
    descriptor[16:21] = b"1.2.3"
    descriptor[48:62] = b"vibe-keyboard\0"
    descriptor[80:88] = b"12:34:56"
    descriptor[96:107] = b"Oct 15 2026"
    descriptor[112:118] = b"v5.4.1"
    # Deliberately use an odd payload length to exercise checksum padding.
    payloads = [bytes(descriptor), b"\x01\x02\x03\x04\x05"]
    image = header
    checksum = 0xEF
    for index, payload in enumerate(payloads):
        image += struct.pack("<II", 0x3C000020 + index * 0x1000, len(payload)) + payload
        for value in payload:
            checksum ^= value
    image += b"\0" * ((15 - len(image)) % 16) + bytes((checksum,))
    if append_hash:
        image += hashlib.sha256(image).digest()
    return bytes(image)


def partition(name, kind, subtype, offset, size, flags=0):
    return struct.pack("<HBBII16sI", 0x50AA, kind, subtype, offset, size, name.encode(), flags)


def make_flash(image=None, *, app_size=0x10000, md5=True, entries=None):
    image = make_app() if image is None else image
    data = bytearray(b"\xff" * 0x30000)
    records = entries if entries is not None else [
        partition("nvs", 1, 2, 0x9000, 0x6000, flags=1),
        partition("factory", 0, 0, 0x10000, app_size),
    ]
    table = b"".join(records)
    if md5:
        table += b"\xeb\xeb" + b"\xff" * 14 + hashlib.md5(table).digest()
    data[0x8000 : 0x8000 + len(table)] = table
    data[0x10000 : 0x10000 + len(image)] = image
    private_payload = b"WIFI_PASSWORD=private-secret!"
    data[0x9000 : 0x9000 + len(private_payload)] = private_payload
    return bytes(data)


class FlashInspectionTests(unittest.TestCase):
    def test_valid_image_reports_descriptor_and_hash(self):
        data = make_flash()
        report = inspector.inspect_flash(data)
        self.assertTrue(report["partition_table"]["valid"])
        self.assertTrue(report["partition_table"]["md5"]["valid"])
        self.assertEqual(report["input"]["sha256"], hashlib.sha256(data).hexdigest())
        app = report["partitions"][1]["app"]
        self.assertTrue(app["valid"], app["errors"])
        self.assertEqual(app["header"]["chip_id"], 9)
        self.assertEqual(app["descriptor"]["project_name"], "vibe-keyboard")
        self.assertEqual(app["descriptor"]["version"], "1.2.3")
        self.assertEqual(app["descriptor"]["idf_version"], "v5.4.1")
        self.assertEqual(app["descriptor"]["build_date"], "Oct 15 2026")
        self.assertEqual(app["image_size"], len(make_app()))
        self.assertNotIn("private-secret", json.dumps(report))
        self.assertNotIn("app", report["partitions"][0])

    def test_app_extraction_excludes_private_storage_and_partition_slack(self):
        image = make_app()
        data = make_flash(image)
        report = inspector.inspect_flash(data)
        with tempfile.TemporaryDirectory() as folder:
            paths = inspector.extract_apps(data, report, Path(folder))
            self.assertEqual(len(paths), 1)
            self.assertEqual(paths[0].read_bytes(), image)
            self.assertEqual(list(Path(folder).iterdir()), paths)
            with self.assertRaises(FileExistsError):
                inspector.extract_apps(data, report, Path(folder))

    def test_old_table_and_image_without_appended_hash(self):
        report = inspector.inspect_flash(make_flash(make_app(append_hash=False), md5=False))
        self.assertTrue(report["partition_table"]["valid"])
        self.assertFalse(report["partition_table"]["md5"]["present"])
        self.assertTrue(report["partitions"][1]["app"]["valid"])

    def test_damaged_table_md5_blocks_app_parsing_and_extraction(self):
        data = bytearray(make_flash())
        data[0x8000 + 64 + 16] ^= 1
        report = inspector.inspect_flash(bytes(data))
        self.assertFalse(report["partition_table"]["valid"])
        self.assertNotIn("app", report["partitions"][1])
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                inspector.extract_apps(bytes(data), report, Path(folder))
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_truncated_flash_and_out_of_bounds_partition(self):
        report = inspector.inspect_flash(b"\xff" * 0x8010)
        self.assertFalse(report["partition_table"]["valid"])
        report = inspector.inspect_flash(make_flash(app_size=0x30000))
        self.assertFalse(report["partitions"][1]["valid"])
        self.assertNotIn("app", report["partitions"][1])

    def test_overlap_between_app_and_nvs_blocks_extraction(self):
        entries = [
            partition("nvs", 1, 2, 0x10000, 0x6000),
            partition("factory", 0, 0, 0x10000, 0x10000),
        ]
        report = inspector.inspect_flash(make_flash(entries=entries))
        self.assertFalse(report["partition_table"]["valid"])
        self.assertFalse(report["partitions"][0]["valid"])
        self.assertFalse(report["partitions"][1]["valid"])

    def test_bad_descriptor_checksum_and_appended_hash_are_rejected(self):
        bad_descriptor = make_app(descriptor_magic=0)
        report = inspector.inspect_flash(make_flash(bad_descriptor))
        self.assertFalse(report["partitions"][1]["app"]["valid"])
        image = bytearray(make_app())
        image[-33] ^= 1
        report = inspector.inspect_flash(make_flash(bytes(image)))
        self.assertFalse(report["partitions"][1]["app"]["checksum"]["valid"])
        image = bytearray(make_app())
        image[-1] ^= 1
        report = inspector.inspect_flash(make_flash(bytes(image)))
        self.assertFalse(report["partitions"][1]["app"]["appended_sha256"]["valid"])
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(inspector.extract_apps(make_flash(bytes(image)), report, Path(folder)), [])

    def test_segment_length_cannot_read_past_partition_into_other_storage(self):
        image = bytearray(make_app())
        struct.pack_into("<I", image, 28, 0xFFFFFFFC)
        report = inspector.inspect_flash(make_flash(bytes(image)))
        app = report["partitions"][1]["app"]
        self.assertFalse(app["valid"])
        self.assertIn("Segment 0 data exceeds", app["errors"][0])
        self.assertNotIn("descriptor", app)

    def test_image_checksum_and_hash_must_fit_partition(self):
        image = make_app()
        # Calling the bounded image parser directly allows exact byte boundaries
        # without changing the enclosing flash layout.
        for length in (23, 27, len(image) - 33, len(image) - 1):
            with self.subTest(length=length):
                app = inspector.inspect_app(image, 0, length)
                self.assertFalse(app["valid"])
        self.assertTrue(inspector.inspect_app(image, 0, len(image))["valid"])

    def test_erased_ota_slot_is_empty_and_is_not_exported(self):
        entries = [
            partition("ota_0", 0, 16, 0x10000, 0x10000),
            partition("ota_1", 0, 17, 0x20000, 0x10000),
        ]
        data = make_flash(entries=entries)
        report = inspector.inspect_flash(data)
        app = report["partitions"][1]["app"]
        self.assertTrue(app["empty"])
        self.assertEqual(app["errors"], [])
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(len(inspector.extract_apps(data, report, Path(folder))), 1)

    def test_cli_writes_json_and_keeps_backup_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "flash.bin"
            source.write_bytes(make_flash())
            before = source.read_bytes()
            report_path = root / "report.json"
            code = inspector.main([str(source), "--output", str(report_path), "--extract-apps", str(root / "apps")])
            self.assertEqual(code, 0)
            self.assertEqual(source.read_bytes(), before)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["partitions"][1]["app"]["valid"])
            self.assertEqual(len(list((root / "apps").glob("*.bin"))), 1)


if __name__ == "__main__":
    unittest.main()
