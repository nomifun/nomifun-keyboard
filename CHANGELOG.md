# Changelog

English | [简体中文](CHANGELOG.zh.md)

## 0.3-screen.2 — 2026-10-19

First public release.

- Four-key USB keyboard firmware for ESP32-S3: fixed k1–k4 → K1–K4 mapping, 5 ms debounce, down/up/click events with epoch and duration.
- Native v1 serial protocol: `transport`/`get_device_info`/`ping` handshake, nonzero epoch with a 5-second lease, monotone `request_id` with idempotent replays, strict bounded JSON (512-byte input, 128 tokens, 128-byte strings, depth 12).
- Permanent `voice_key:none` policy: no onboard audio path, no audio frames, explicit protocol errors for legacy commands.
- `nk_display`/`nk_display_applied` fixed status screen: NV3007 428×142 RGB565 over SPI2 with a 6848-byte DMA strip, 8 fixed states, Nomi face, per-key feedback, LEDC PWM backlight, independent degradation on failure.
- Offline tooling: five native C test programs, `validate_build.py` image checks, `device_probe.py`/`native_diagnostic.py` read-only diagnostics, `inspect_flash.py`/`native_preflight.py` recovery verification.
