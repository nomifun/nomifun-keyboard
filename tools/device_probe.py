#!/usr/bin/env python3
"""Read-only keyboard USB identity and key-event diagnostics.

Default: enumerate serial ports without opening them. ``info`` uses only the
documented transport/get_device_info/ping messages. No flash, configuration,
screen, microphone-control, or OTA command is exposed.

Protocol source: docs/spec/usb-protocol.md; vendor framing from firmware 0.3.8.
Requires pyserial for device enumeration and connections; parser tests do not.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import time
from typing import Any


USB_VID = 0x303A
USB_PID = 0x1001
MAX_FRAME_LENGTH = 4096
READ_SIZE = 512
KEYS = frozenset(("k1", "k2", "k3", "k4"))
BUTTON_EVENTS = frozenset(("button_down", "button_up", "button_click"))
KNOWN_FRAME_TYPES = frozenset((0x01, 0x10, 0x20, 0x21, 0x22, 0x23, 0x30))


class ProtocolLimitError(ValueError):
    """A caller exceeded the parser's fixed receive-buffer bound."""


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _text(value: Any, maximum: int = 128) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and all(character.isprintable() for character in value)
    )


def _uint32(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 0xFFFFFFFF


def sanitize_event(value: Any) -> dict[str, Any] | None:
    """Return only known identity/key fields, never arbitrary device content."""
    if not isinstance(value, dict):
        raise ValueError("JSON event must be an object")
    event = value.get("event")
    if event == "device_info":
        result: dict[str, Any] = {"event": event}
        for key in ("hardware", "firmware_version", "device_id"):
            if key in value:
                if not _text(value[key]):
                    raise ValueError("invalid identity string")
                result[key] = value[key]
        # Other fields, including possible secrets and free-form messages, are
        # deliberately not copied to the diagnostic result.
        if "buttons" in value:
            buttons = value["buttons"]
            if (
                not isinstance(buttons, list)
                or not 1 <= len(buttons) <= 4
                or any(not isinstance(button, str) or button not in KEYS for button in buttons)
                or len(set(buttons)) != len(buttons)
            ):
                raise ValueError("invalid button list")
            result["buttons"] = list(buttons)
        for name in ("native_keyboard_protocol", "epoch"):
            if name in value:
                if not _uint32(value[name]):
                    raise ValueError("invalid native protocol identity")
                result[name] = value[name]
        if not all(key in result for key in ("hardware", "firmware_version")):
            raise ValueError("incomplete identity")
        return result
    if isinstance(event, str) and event in BUTTON_EVENTS:
        button = value.get("button")
        if not isinstance(button, str) or button not in KEYS:
            raise ValueError("unknown button")
        result = {"event": event, "button": button}
        for key in ("duration_ms", "session_id"):
            if key in value:
                if not _uint32(value[key]):
                    raise ValueError("invalid key-event number")
                result[key] = value[key]
        if event != "button_down" and "duration_ms" not in result:
            raise ValueError("missing key duration")
        return result
    if not _text(event, 64):
        raise ValueError("invalid event name")
    return None


class FrameParser:
    """Bounded incremental parser; emits sanitized JSON events only.

    Text logs and invalid headers resynchronize one byte at a time. Audio uses
    ``16 + uint16_le(offset=14)`` and is counted/skipped without exposing its
    contents. Recognized non-JSON vendor frames are also skipped in full.
    """

    def __init__(self, receive_buffer_limit: int = MAX_FRAME_LENGTH) -> None:
        if not 16 <= receive_buffer_limit <= MAX_FRAME_LENGTH:
            raise ValueError("receive_buffer_limit must be between 16 and 4096")
        self.receive_buffer_limit = receive_buffer_limit
        self._buffer = bytearray()
        self.stats: Counter[str] = Counter()

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        if len(data) > self.receive_buffer_limit:
            self.stats["receive_limit_errors"] += 1
            raise ProtocolLimitError("one receive chunk exceeds the buffer limit")
        self.stats["received_bytes"] += len(data)
        events: list[dict[str, Any]] = []
        offset = 0
        while offset < len(data):
            writable = self.receive_buffer_limit - len(self._buffer)
            if writable == 0:
                self.stats["receive_limit_errors"] += 1
                raise ProtocolLimitError("incomplete frame fills the receive buffer")
            count = min(writable, len(data) - offset)
            self._buffer.extend(data[offset : offset + count])
            offset += count
            events.extend(self._drain())
        return events

    def _discard(self, reason: str) -> None:
        del self._buffer[0]
        self.stats["discarded_bytes"] += 1
        self.stats[reason] += 1

    def _drain(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while len(self._buffer) >= 4:
            if self._buffer[0] != 1:
                self._discard("invalid_version_bytes")
                continue
            frame_type = self._buffer[1]
            if frame_type not in KNOWN_FRAME_TYPES:
                self._discard("unknown_type_headers")
                continue
            body_length = struct.unpack_from("<H", self._buffer, 2)[0]
            if frame_type == 0x01:
                if body_length != 16:
                    self._discard("invalid_audio_headers")
                    continue
                if len(self._buffer) < 16:
                    break
                total_length = 16 + struct.unpack_from("<H", self._buffer, 14)[0]
            else:
                total_length = 4 + body_length
            if total_length > MAX_FRAME_LENGTH:
                self._discard("oversize_headers")
                continue
            if total_length > self.receive_buffer_limit:
                self.stats["receive_limit_errors"] += 1
                raise ProtocolLimitError("declared frame exceeds the receive buffer limit")
            if len(self._buffer) < total_length:
                break
            self.stats["frames"] += 1
            if frame_type == 0x01:
                self.stats["audio_frames_skipped"] += 1
                self.stats["audio_bytes_skipped"] += total_length - 16
                del self._buffer[:total_length]
                continue
            if frame_type != 0x10:
                self.stats["other_frames_skipped"] += 1
                del self._buffer[:total_length]
                continue
            body = bytes(self._buffer[4:total_length])
            del self._buffer[:total_length]
            self.stats["json_frames"] += 1
            try:
                value = json.loads(
                    body.decode("utf-8", errors="strict"),
                    object_pairs_hook=_unique_object,
                    parse_constant=_reject_json_constant,
                )
                event = sanitize_event(value)
            except (ValueError, UnicodeError, RecursionError):
                self.stats["invalid_json_events"] += 1
                continue
            if event is None:
                self.stats["other_events_skipped"] += 1
            else:
                events.append(event)
        return events

    def finish(self) -> None:
        """Discard the incomplete tail without logging its contents."""
        if self._buffer:
            self.stats["trailing_bytes"] += len(self._buffer)
            self._buffer.clear()


def encode_command(name: str) -> bytes:
    commands = {
        "transport": {"event": "transport", "kind": "usb"},
        "get_device_info": {"event": "get_device_info"},
        "ping": {"event": "ping"},
    }
    if name not in commands:
        raise ValueError("only transport, get_device_info, and ping are supported")
    body = json.dumps(commands[name], separators=(",", ":")).encode("utf-8")
    return b"\x01\x10" + struct.pack("<H", len(body)) + body


def enumerate_candidates() -> list[dict[str, Any]]:
    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise RuntimeError("pyserial is required: python -m pip install pyserial") from error
    return [
        {
            "port": port.device,
            "vid": "303A",
            "pid": "1001",
            "serial_number": port.serial_number,
        }
        for port in sorted(list_ports.comports(), key=lambda item: item.device)
        if (port.vid, port.pid) == (USB_VID, USB_PID)
    ]


def select_candidate(candidates: list[dict[str, Any]], port: str | None) -> dict[str, Any]:
    if port:
        for candidate in candidates:
            if candidate["port"].casefold() == port.casefold():
                return candidate
        raise ValueError("the requested port is not an enumerated 303A:1001 device")
    if not candidates:
        raise ValueError("no 303A:1001 serial device is connected")
    if len(candidates) != 1:
        raise ValueError("multiple 303A:1001 devices are connected; specify --port")
    return candidates[0]


def probe_device(
    candidate: dict[str, Any], timeout: float = 5.0, listen_seconds: float = 0.0
) -> dict[str, Any]:
    import serial

    parser = FrameParser()
    report: dict[str, Any] = {
        "status": "identity_timeout",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "usb": dict(candidate),
        "device_info": None,
        "button_events": [],
    }
    # The baud value satisfies pyserial/Windows DCB setup; this built-in USB
    # CDC protocol has no documented baud-rate requirement. Disable modem-line
    # flow control, set both lines before open, and never toggle/reset them.
    connection = serial.Serial(
        port=None,
        baudrate=115200,
        timeout=0.1,
        write_timeout=min(1.0, timeout),
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )
    connection.dtr = False
    connection.rts = False
    connection.port = candidate["port"]
    started = time.monotonic()
    identity_deadline = started + timeout
    total_deadline = identity_deadline + listen_seconds
    listen_deadline: float | None = None
    next_ping = started + 2.0

    def send(name: str) -> None:
        frame = encode_command(name)
        offset = 0
        while offset < len(frame):
            deadline = listen_deadline if listen_deadline is not None else identity_deadline
            remaining = min(deadline, total_deadline) - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("session deadline")
            connection.write_timeout = min(1.0, remaining)
            written = connection.write(frame[offset:])
            if not written:
                raise TimeoutError("serial write made no progress")
            offset += written

    try:
        connection.open()
        send("transport")
        send("get_device_info")
        while True:
            now = time.monotonic()
            deadline = listen_deadline if listen_deadline is not None else identity_deadline
            if now >= min(deadline, total_deadline):
                break
            if now >= next_ping:
                send("ping")
                next_ping = time.monotonic() + 2.0
            data = connection.read(min(max(connection.in_waiting, 1), READ_SIZE))
            for event in parser.feed(data):
                if event["event"] == "device_info" and report["device_info"] is None:
                    report["device_info"] = event
                    report["status"] = (
                        "ok" if event["hardware"] == "vibe_keyboard" else "hardware_mismatch"
                    )
                    report["hardware_confirmed"] = event["hardware"] == "vibe_keyboard"
                    listen_deadline = min(time.monotonic() + listen_seconds, total_deadline)
                elif event["event"] in BUTTON_EVENTS and listen_seconds > 0:
                    if len(report["button_events"]) < 4096:
                        report["button_events"].append(event)
                    else:
                        parser.stats["button_events_dropped"] += 1
            if report["device_info"] is not None and listen_seconds == 0:
                break
    except KeyboardInterrupt:
        report["status"] = "interrupted"
    except (serial.SerialException, OSError, TimeoutError, ProtocolLimitError) as error:
        report["status"] = "serial_or_protocol_error"
        # Never include exception text derived from received data.
        report["error_type"] = type(error).__name__
    finally:
        try:
            connection.close()
        except (serial.SerialException, OSError) as error:
            report["status"] = "serial_or_protocol_error"
            report["close_error_type"] = type(error).__name__
        finally:
            parser.finish()
            report["statistics"] = dict(sorted(parser.stats.items()))
            report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return report


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("command", nargs="?", choices=("list", "info"), default="list")
    cli.add_argument("--port", help="select an enumerated 303A:1001 port, for example COM3")
    cli.add_argument("--timeout", type=float, default=5.0, help="identity timeout in seconds (0.2-30)")
    cli.add_argument("--listen-seconds", type=float, default=0.0, help="listen for keys after identity (0-300)")
    cli.add_argument("--output", type=Path, help="save the same sanitized JSON result locally")
    args = cli.parse_args(argv)
    if not 0.2 <= args.timeout <= 30 or not 0 <= args.listen_seconds <= 300:
        cli.error("--timeout must be 0.2-30 and --listen-seconds must be 0-300")
    if args.command != "info" and args.listen_seconds:
        cli.error("--listen-seconds requires the info command")
    exit_code = 0
    try:
        candidates = enumerate_candidates()
        if args.command == "list":
            selected = select_candidate(candidates, args.port) if args.port or len(candidates) == 1 else None
            report = {
                "status": "enumerated",
                "candidates": candidates,
                "selected_port": selected["port"] if selected else None,
                "selection_required": len(candidates) > 1 and not args.port,
            }
        else:
            selected = select_candidate(candidates, args.port)
            report = probe_device(selected, args.timeout, args.listen_seconds)
            exit_code = 0 if report["status"] == "ok" else 1
    except (ValueError, RuntimeError) as error:
        report = {"status": "error", "message": str(error)}
        exit_code = 1
    rendered = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    sys.stdout.write(rendered)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        except OSError:
            sys.stderr.write("Could not save --output JSON.\n")
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
