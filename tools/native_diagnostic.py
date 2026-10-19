#!/usr/bin/env python3
"""Hardware development CLI: NONE and four-key event diagnostics only.

Never enables the board microphone, calls models or controls UI/clipboard.
The product runtime is Rust. Private evidence stays in the explicit local folder.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import time
import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--screen-states', action='store_true', help='Exercise only fixed status strings, never user text')
    args = parser.parse_args()
    if not 0 <= args.seconds <= 300:
        parser.error('seconds must be between 0 and 300')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = {'status': 'failed', 'observed_at_utc': datetime.now(timezone.utc).isoformat()}
    buffer = bytearray()
    frames = []
    started = ping_at = time.monotonic()
    with (args.output_dir/'raw-usb.bin').open('xb') as raw, (args.output_dir/'events.jsonl').open('x', encoding='utf-8') as log:
        port = serial.Serial()
        port.port, port.baudrate, port.timeout, port.write_timeout = args.port, 115200, 0.05, 1
        port.dtr = port.rts = False
        port.open()
        def record(direction, value):
            log.write(json.dumps({'elapsed_ms': round((time.monotonic()-started)*1000, 3), 'direction': direction, **value}, ensure_ascii=False)+'\n')
            log.flush()
        def send(value):
            data = json.dumps(value, separators=(',', ':')).encode()
            port.write(b'\x01\x10'+struct.pack('<H', len(data))+data)
            record('host', value)
        def read():
            data = port.read(512)
            raw.write(data)
            buffer.extend(data)
            emitted = []
            while len(buffer) >= 4:
                if buffer[0] != 1 or buffer[1] not in (1, 16):
                    del buffer[0]
                    continue
                if buffer[1] == 1:
                    raise ValueError('unexpected USB audio while keyboard must remain NONE')
                length = 4+struct.unpack_from('<H', buffer, 2)[0]
                if length > 4096:
                    raise ValueError('frame exceeds bound')
                if len(buffer) < length:
                    break
                value = json.loads(bytes(buffer[4:length]))
                del buffer[:length]
                if value.get('event', '').startswith('button_') and 'session_id' in value:
                    raise ValueError('unexpected board audio session on key event')
                record('device', value)
                emitted.append(value)
            frames.extend(emitted)
            return emitted
        def wait(predicate, seconds=4):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                for value in read():
                    if predicate(value):
                        return value
            raise TimeoutError('native keyboard receipt timeout')
        try:
            send({'event': 'transport', 'kind': 'usb'})
            send({'event': 'get_device_info'})
            caps = wait(lambda v: v.get('event') == 'nk_capabilities')
            identity = next(v for v in frames if v.get('event') == 'device_info')
            epoch = identity['epoch']
            assert identity['hardware'] == 'vibe_keyboard' and identity['native_keyboard_protocol'] == 1
            assert caps['epoch'] == epoch and caps['protocol'] == 1 and caps['policy_ack'] is True and caps['wait_release'] is True
            command = {'event': 'nk_policy', 'epoch': epoch, 'request_id': 1, 'voice_key': 'none'}
            send(command)
            receipt = wait(lambda v: v.get('request_id') == 1)
            assert receipt['event'] == 'nk_policy_applied' and receipt['voice_key'] == 'none' and receipt['capture_stopped'] is True
            send(command)
            assert wait(lambda v: v.get('request_id') == 1) == receipt
            if args.screen_states:
                caps = next((value for value in reversed(frames) if value.get('event') == 'nk_capabilities' and value.get('display', {}).get('available') is True), caps)
                if caps.get('display', {}).get('available') is not True:
                    caps = wait(lambda v: v.get('event') == 'nk_capabilities' and v.get('display', {}).get('available') is True)
                assert caps['display']['width'] == 428 and caps['display']['height'] == 142 and caps['display']['privacy'] == 'status_only'
                states = ['connecting', 'sleeping', 'ready', 'starting', 'listening', 'recognizing', 'polishing', 'error', 'sleeping']
                results = []
                last_frames = -1
                for request, state in enumerate(states, 2):
                    send({'event': 'nk_display', 'epoch': epoch, 'request_id': request, 'state': state})
                    applied = wait(lambda v: v.get('request_id') == request)
                    assert applied['event'] == 'nk_display_applied' and applied['epoch'] == epoch and applied['state'] == state and applied['applied'] is True, applied
                    assert applied['backlight_on'] is True and applied['pwm_duty'] == (45 if state == 'sleeping' else 115)
                    assert applied['buffer_bytes'] == 6848 and applied['frames'] > last_frames and applied['visual_verified'] is False
                    last_frames = applied['frames']
                    results.append(applied)
                result['panel_driver_states'] = results
                result['panel_visual_verified'] = False
            print('READY: keyboard NONE confirmed; four-key events only.', flush=True)
            deadline = time.monotonic()+args.seconds
            while time.monotonic() < deadline:
                if time.monotonic()-ping_at >= 1.5:
                    send({'event': 'ping'})
                    ping_at = time.monotonic()
                read()
            counts = {}
            for value in frames:
                if value.get('event', '').startswith('button_'):
                    key = value['button']+'/'+value['event']
                    counts[key] = counts.get(key, 0)+1
            result.update(status='passed', identity=identity, none_confirmed=True, duplicate_request_idempotent=True, usb_audio_frames=0, button_counts=counts)
        except Exception as error:
            result['error'] = str(error)
        finally:
            port.close()
    (args.output_dir/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    raise SystemExit(0 if result['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
