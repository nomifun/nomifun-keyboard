# Source Provenance and Licensing

English | [简体中文](SOURCE.zh.md)

The current firmware implements four-key USB, a permanent NONE policy, and the fixed status screen. OS recording, model calls, subtitles, and editing are implemented natively by NomiFun; see the [product design](docs/design/nomifun-native-keyboard.md) for features and module boundaries.

## Firmware provenance

| Content | Source and usage |
|---|---|
| Four-key debounce, strictly bounded JSON parsing | `zerob13/vibe-keyboard` commit `019cfa099c2cb3b8d7b9aad665dbc4fd4a09096a`, trimmed to the current protocol; MIT notice in [LICENSE](LICENSE) |
| NV3007 init table | `firmware/components/vk_board/vk_nv3007_init.inc` at the same commit, keeping all 119 commands; current file is [nv3007_init.inc](firmware/components/nk_screen/nv3007_init.inc), SHA256 `6c36dd6c317468a18bf59dd95fc2f828a1433f3f827dd32c492fae4d43fb385f` |
| Panel wiring and data format | GPIO definitions, y=14 window offset, and RGB565 byte order from the same upstream revision |
| USB owner, screen owner, Nomi face and font primitives | Implemented locally |

The build uses the minimal ESP-IDF 5.5.3 dependency closure and does not link onboard audio, ESP-SR/Opus, LVGL, LED strip, OTA, networking, or Bluetooth features. Python is used only by ESP-IDF and the diagnostic/recovery tools — it takes no part in the product runtime. The actual dependency and symbol boundary is checked by [validate_build.py](firmware/tools/validate_build.py).

## License tracking for private recovery images

Privately retained historical flashed images used ESP-SR 2.1.4, micro-opus 0.4.1, and Opus. Their notices are kept alongside those images in the ignored `host/local/flashed-images/third-party-notices/` directory for license tracking of recovery material; these components are not current dependencies and have no source, build entry, or product runtime path here.

Full factory backups and installed app images are kept private per device MAC and are neither product source nor a distribution entry. General recovery rules are in [DEVICE.md](DEVICE.md); concrete devices, image hashes, and paths live in local private records.
