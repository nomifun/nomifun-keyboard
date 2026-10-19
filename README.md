# NomiFun Native Four-Key Subtitle Keyboard

English | [简体中文](README.zh.md)

A four-key keyboard that controls NomiFun: hold K4 to dictate through the system microphone, K2 to polish the full text, K3 to cancel the current unfinished operation, and K1 to show or hide the main window. ASR supports real-time streaming and cloud batch recognition. The transparent subtitle overlay is editable: insert at the caret or replace the selection, keep writing in the same document, adjust the font size, and show a glyph polish glow.

The keyboard provides only the four keys and a fixed status screen; onboard audio capture is permanently NONE. The firmware consists of USB, debounce, and the minimal NV3007/SPI/backlight components. Recording, ASR, subtitles, and settings are managed natively by the NomiFun Rust/Tauri app.

## Usage

The four keys have fixed roles; connect and use. In NomiFun "Settings → Extension Keyboard", pick the system microphone, ASR mode/model, and text model. Hold K4, wait for the teal listening cue, then speak; release to finish the segment. Press K3 to abandon the current segment or polish; previously finalized text is kept. Keep recording or editing, then press K2 to polish. While the subtitle window is focused, use the system Ctrl+C / Command+C to copy the selection, then paste it yourself in the target app. Esc closes and clears the current document; Esc during IME composition goes to the IME first. The next recording creates a new document.

## Development entry points

| Location | Purpose |
| --- | --- |
| `firmware/components/vk_usb/` | USB four-key events, NONE/Display, epoch/lease and release gating |
| `firmware/components/vk_input/` | Four-key debounce |
| `firmware/components/nk_screen/` | Status screen and strip rendering |
| `tools/build.ps1`, `tools/build.sh` | ESP-IDF build and offline image checks |
| `tools/device_probe.py`, `tools/native_diagnostic.py` | Device identity, NONE, key and screen diagnostics |
| `tools/inspect_flash.py`, `tools/native_preflight.py` | Factory image inspection and flash preflight |

See the [product design](docs/design/nomifun-native-keyboard.md) for complete behavior, the [docs index](docs/README.md) for the interface contracts, the [firmware README](firmware/README.md) for build and flashing, [DEVICE.md](DEVICE.md) for hardware and factory recovery, and [SOURCE.md](SOURCE.md) for code provenance. Logs, reports, screenshots, and private recovery material are never committed or distributed.
