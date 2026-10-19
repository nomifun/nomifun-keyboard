# Contributing

English | [简体中文](CONTRIBUTING.zh.md)

## Repository layout

| Path | Contents |
| --- | --- |
| `firmware/` | ESP-IDF 5.5.3 project: `main/` entry plus the `vk_usb`, `vk_input`, `nk_screen` components |
| `firmware/tests/` | Offline native C tests that run on the host compiler (`cc`) |
| `firmware/tools/validate_build.py` | Post-build checks for config, partition layout, image integrity, and banned symbols |
| `tools/` | Host-side build scripts and diagnostic/preflight tools (Python, `tools/requirements.txt`) |
| `tests/` | Python unit tests for the tools |
| `docs/` | Product design and technical contracts, in English and Chinese |
| `DEVICE.md` / `SOURCE.md` | Hardware/recovery rules and code provenance |

## Build and test

- Firmware build: `./tools/build.ps1` (Windows) or `./tools/build.sh` (macOS/Linux/WSL). Requires ESP-IDF 5.5.3; output lands in `firmware/build-native-screen/` and is validated automatically.
- Native C tests: `cd firmware && python3 tests/run_native_tests.py`.
- Python tool tests: `python -m unittest discover tests` from the repository root.
- Python tools need `pip install -r tools/requirements.txt` (pyserial for serial access).

## Conventions

- One implementation per feature — no parallel/alternate paths. Keep the firmware limited to the three components; do not link audio, LVGL, LED, OTA, network, or Bluetooth code.
- Protocol parsing stays strictly bounded; reject malformed data instead of guessing.
- Never commit generated logs, reports, screenshots, build output, `sdkconfig`, device backups, flashed images, or per-device records — see `.gitignore`.
- Never flash a device without the per-device authorization and recovery checks in [DEVICE.md](DEVICE.md).
- Documentation is bilingual: when you change a `.md` file, update its `.zh.md` counterpart in the same commit (and vice versa).
