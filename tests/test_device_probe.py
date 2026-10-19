"""Offline tests. These never enumerate or open a real serial port."""

import importlib.util
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "device_probe.py"
SPEC = importlib.util.spec_from_file_location("device_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def json_frame(value):
    body = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return b"\x01\x10" + struct.pack("<H", len(body)) + body


def audio_frame(payload):
    return struct.pack("<BBHIIBBH", 1, 1, 16, 23, 7, 1, 0, len(payload)) + payload


IDENTITY = {
    "event": "device_info",
    "hardware": "vibe_keyboard",
    "firmware_version": "0.3.8",
    "buttons": ["k1", "k2", "k3", "k4"],
}


class FrameParserTests(unittest.TestCase):
    def test_every_split_and_one_byte_fragments(self):
        frame = json_frame(IDENTITY)
        for split in range(len(frame) + 1):
            parser = probe.FrameParser()
            self.assertEqual(parser.feed(frame[:split]) + parser.feed(frame[split:]), [IDENTITY])
            self.assertEqual(parser.buffered_bytes, 0)
        parser = probe.FrameParser()
        actual = []
        for byte in frame:
            actual.extend(parser.feed(bytes([byte])))
        self.assertEqual(actual, [IDENTITY])

    def test_fragmented_audio_uses_payload_length_and_is_not_exposed(self):
        # A valid-looking JSON frame embedded inside audio must never dispatch.
        payload = json_frame({"event": "button_down", "button": "k4"}) + b"private audio"
        data = audio_frame(payload) + json_frame(IDENTITY)
        parser = probe.FrameParser()
        actual = []
        for offset in range(0, len(data), 7):
            actual.extend(parser.feed(data[offset : offset + 7]))
        self.assertEqual(actual, [IDENTITY])
        self.assertEqual(parser.stats["audio_frames_skipped"], 1)
        self.assertEqual(parser.stats["audio_bytes_skipped"], len(payload))
        self.assertEqual(parser.buffered_bytes, 0)

    def test_logs_unknown_versions_and_types_resynchronize(self):
        parser = probe.FrameParser()
        data = b"I (42) boot: ready\r\n" + b"\x02\x10\x00\x00\x01\xfe\x00\x00"
        self.assertEqual(parser.feed(data + json_frame(IDENTITY)), [IDENTITY])
        self.assertGreater(parser.stats["invalid_version_bytes"], 0)
        self.assertEqual(parser.stats["unknown_type_headers"], 1)

    def test_oversize_json_and_audio_recover_before_next_frame(self):
        parser = probe.FrameParser()
        bad_json = b"\x01\x10\xfd\x0f"  # 4 + 4093 = 4097
        bad_audio = struct.pack("<BBHIIBBH", 1, 1, 16, 0, 3, 1, 0, 4081)
        events = parser.feed(bad_json + bad_audio + json_frame(IDENTITY))
        self.assertEqual(events, [IDENTITY])
        self.assertEqual(parser.stats["oversize_headers"], 2)

    def test_maximum_frame_and_combined_reads_stay_bounded(self):
        parser = probe.FrameParser()
        maximum = audio_frame(b"a" * (4096 - 16))
        self.assertEqual(parser.feed(maximum[:4000]), [])
        self.assertLessEqual(parser.buffered_bytes, 4096)
        self.assertEqual(parser.feed(maximum[4000:] + json_frame(IDENTITY)), [IDENTITY])
        self.assertEqual(parser.stats["audio_frames_skipped"], 1)
        with self.assertRaises(probe.ProtocolLimitError):
            parser.feed(b"a" * 4097)
        self.assertEqual(parser.stats["receive_limit_errors"], 1)

    def test_unknown_fields_events_and_known_opaque_frames_are_not_leaked(self):
        parser = probe.FrameParser()
        private = dict(
            IDENTITY,
            device_secret="private",
            message="private message",
            replacement_protocol=1,
            ui_states=["unused"],
            interaction_modes=["unused"],
        )
        hidden = json_frame({"event": "unknown", "device_secret": "private"})
        # Known OTA-state frames must be skipped as a unit even when their body
        # contains a valid-looking key event. The probe never sends such frames.
        embedded = json_frame({"event": "button_down", "button": "k3"})
        opaque = b"\x01\x30" + struct.pack("<H", len(embedded)) + embedded
        self.assertEqual(parser.feed(json_frame(private) + hidden + opaque), [IDENTITY])
        self.assertEqual(parser.stats["other_events_skipped"], 1)
        self.assertEqual(parser.stats["other_frames_skipped"], 1)

    def test_invalid_json_schema_and_truncated_tail(self):
        parser = probe.FrameParser()
        invalid = [
            {"event": "button_up", "button": "k5", "duration_ms": 10},
            {"event": "button_up", "button": "k1", "duration_ms": True},
            {"event": "button_up", "button": "k1"},
            {"event": "device_info", "hardware": "x"},
        ]
        for event in invalid:
            self.assertEqual(parser.feed(json_frame(event)), [])
        duplicate = b'{"event":"button_down","event":"device_info"}'
        self.assertEqual(parser.feed(b"\x01\x10" + struct.pack("<H", len(duplicate)) + duplicate), [])
        self.assertEqual(parser.stats["invalid_json_events"], 5)
        self.assertEqual(parser.feed(json_frame(IDENTITY)[:9]), [])
        parser.finish()
        self.assertEqual(parser.stats["trailing_bytes"], 9)
        self.assertEqual(parser.buffered_bytes, 0)

    def test_key_event_retains_only_valid_known_fields(self):
        parser = probe.FrameParser()
        event = {"event": "button_up", "button": "k2", "duration_ms": 42, "session_id": 0}
        self.assertEqual(parser.feed(json_frame(dict(event, secret="hidden"))), [event])


class SelectionAndCommandsTests(unittest.TestCase):
    def test_multiple_devices_require_explicit_port(self):
        candidates = [{"port": "COM3"}, {"port": "COM4"}]
        with self.assertRaisesRegex(ValueError, "specify --port"):
            probe.select_candidate(candidates, None)
        self.assertEqual(probe.select_candidate(candidates, "com4"), candidates[1])
        with self.assertRaises(ValueError):
            probe.select_candidate(candidates, "COM8")

    def test_only_three_identification_session_commands_are_encodable(self):
        for name in ("transport", "get_device_info", "ping"):
            frame = probe.encode_command(name)
            self.assertEqual(frame[:2], b"\x01\x10")
            self.assertEqual(struct.unpack_from("<H", frame, 2)[0], len(frame) - 4)
            self.assertEqual(json.loads(frame[4:])["event"], name)
        for name in ("ui_state", "voice_key", "provision", "vk_update_begin"):
            with self.assertRaises(ValueError):
                probe.encode_command(name)


class SerialSessionTests(unittest.TestCase):
    def fake_module(self, fail_read=False):
        instances = []

        class FakeSerial:
            def __init__(self, **kwargs):
                self.settings = kwargs
                self.writes = []
                self.closed = False
                self.in_waiting = len(json_frame(IDENTITY))
                instances.append(self)

            def open(self):
                self.lines_at_open = (self.dtr, self.rts)

            def write(self, data):
                self.writes.append(data)
                return len(data)

            def read(self, count):
                if fail_read:
                    raise OSError("device disconnected")
                self.in_waiting = 0
                return json_frame(IDENTITY)

            def close(self):
                self.closed = True

        return SimpleNamespace(Serial=FakeSerial, SerialException=OSError), instances

    def test_session_disables_lines_before_open_and_sends_only_identification(self):
        module, instances = self.fake_module()
        with patch.dict(sys.modules, {"serial": module}):
            report = probe.probe_device({"port": "COM_TEST"})
        connection = instances[0]
        self.assertEqual(connection.lines_at_open, (False, False))
        self.assertIsNone(connection.settings["port"])
        self.assertFalse(connection.settings["rtscts"])
        self.assertFalse(connection.settings["dsrdtr"])
        self.assertEqual(connection.writes, [probe.encode_command("transport"), probe.encode_command("get_device_info")])
        self.assertTrue(connection.closed)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["device_info"], IDENTITY)

    def test_serial_error_still_closes_without_exposing_exception_text(self):
        module, instances = self.fake_module(fail_read=True)
        with patch.dict(sys.modules, {"serial": module}):
            report = probe.probe_device({"port": "COM_TEST"})
        self.assertTrue(instances[0].closed)
        self.assertEqual(report["status"], "serial_or_protocol_error")
        self.assertEqual(report["error_type"], "OSError")
        self.assertNotIn("device disconnected", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
