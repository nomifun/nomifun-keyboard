# Keyboard Hardware and Recovery

English | [简体中文](DEVICE.zh.md)

The product is an ESP32-S3 four-key board that sends key events to NomiFun over USB and shows fixed states plus the Nomi face. Audio is recorded from the computer's operating-system microphone. For the full feature set see the [product design](docs/design/nomifun-native-keyboard.md).

## Board and identity checks

| Item | Supported board |
|---|---|
| USB VID / PID | `303A:1001`, USB Serial/JTAG |
| Chip | ESP32-S3, 40 MHz crystal |
| Flash / PSRAM | 16 MiB Flash / 8 MiB PSRAM |
| Product application | `vibe_keyboard`; source version in the [firmware README](firmware/README.md) |
| Application slot | `ota_0@0x20000`; verify the actual partition table before writing |

Serial port names are assigned by the OS and cannot identify the device; a COM number is not an identity. `303A:1001` is a generic ESP32 identity, so after connecting you must still verify the native protocol, capabilities, and stable ID. ROM MAC, installed-image version/size/hash, security configuration, and backup mapping belong to each physical unit's local records and are not written into public source documentation. Rebuilt output and the installed image must be checked separately — an identical version string does not mean identical binaries.

## Board and wiring

![Four-key PCB: ESP32-S3-WROOM-1 module, USB-C, screen ribbon cable, and four key sockets](docs/images/vibe-keyboard-pcb-2026-10-16.jpg)

| Part | Current firmware wiring |
|---|---|
| Keys | k1=GPIO0, k2=GPIO18, k3=GPIO17, k4=GPIO16; pull-up, pressed = low |
| Keycap glyphs | ○=k1, ★=k2, ×=k3, microphone=k4; fixed to K1–K4, no calibration or remapping |
| Display | NV3007, 428×142, RGB565, y offset 14 |
| Display SPI | MOSI21 / CLK14 / CS11 / DC13 / RESET12 |
| Backlight | GPIO9, LEDC PWM |

Pin definitions come from the [pinned upstream revision](https://github.com/zerob13/vibe-keyboard/tree/019cfa099c2cb3b8d7b9aad665dbc4fd4a09096a), not per-wire electrical measurement. The onboard PDM pins GPIO41/40, the GPIO8 LED strip, the slide switch, and the wireless module are not part of this product; do not infer a microphone model, switch function, battery, or power circuit from appearance. A new board variant must re-verify wiring and panel orientation.

## Flash partitions

The partition table for this board sits at `0x8000`; the source layout is [firmware/partitions.csv](firmware/partitions.csv). Before every write, independently read the actual partition table and compare it — the table below cannot replace checking the physical unit.

| Partition | Offset | Size |
|---|---|---|
| nvs | `0x009000` | `0x004000` |
| nvs_keys | `0x00d000` | `0x003000` |
| phy_init | `0x010000` | `0x001000` |
| otadata | `0x011000` | `0x002000` |
| ota_0 | `0x020000` | `0x500000` |
| ota_1 | `0x520000` | `0x500000` |
| storage | `0xa20000` | `0x5e0000` |

## Recovery material

A complete factory backup for the 16 MiB board should be 16777216 bytes, stored in a private directory outside this repository and kept separate per ROM MAC. The backup contains the unit's NVS, keys, and factory storage. Never flash one device's backup onto another, and never commit it to Git or ship it inside a firmware or NomiFun package.

Local records should capture the ROM MAC, stable ID, backup path and SHA256, the factory app descriptor, the installed app, and independent read-back results. The maintainer's device mapping lives in the ignored `host/local/device-recovery-record.zh.md`, with flashed app copies and their licenses under `host/local/flashed-images/`; `local-*.json` and `host/` are not distributed. Historical probe files may describe a different unit — always work from the current ROM identity and an independent read-back.

## Write and recovery boundaries

Before every write, re-read the ROM MAC, security configuration, and actual partitions; validate the candidate image's descriptor, size, SHA256, and the matching full factory backup for that device. The application image must not exceed the target slot, and after writing it must be independently read back and compared.

Ordinary app updates happen only on an explicitly authorized app partition. The all-flash command printed by ESP-IDF is not authorization; the bootloader, partition table, NVS, OTA metadata, storage, and eFuse are never modified by an app update. A full factory restore overwrites device data — confirm the recovery scope separately and use the complete backup matching that MAC.
