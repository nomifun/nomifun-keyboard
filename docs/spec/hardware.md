# Hardware Contract

English | [简体中文](hardware.zh.md)

The target board is an ESP32-S3 with 16 MiB Flash and 8 MiB PSRAM. Device identity, photos, wiring, partitions, and the factory-backup mapping are consolidated in [DEVICE.md](../../DEVICE.md). USB VID/PID `303A:1001` only discovers candidate devices; after connecting you must verify the native v1 protocol and the stable ID — a serial port name is not a device identity.

The four keys use GPIO0/18/17/16, pulled up and active-low. The NV3007 panel is 428×142 RGB565 on MOSI21, CLK14, CS11, DC13, RESET12, with backlight on GPIO9. The firmware initializes only the four keys, USB, and the status screen; product audio comes from the operating-system microphone, and onboard audio, the LED strip, and wireless links are never initialized.

The screen only shows fixed states, the Nomi face, and four-key hints — it never receives user text. Driver, backlight, and host-state synchronization are covered by the [screen contract](screen-status.md).

Full factory flash images, device-private data, and flashed images never enter Git or a product package. Flashing requires checking the current device MAC, the actual partition table, the image descriptor/hash, and the matching factory backup, plus explicit authorization for the write scope; ordinary app updates do not modify the bootloader, partition table, NVS, OTA metadata, storage, or eFuse. A full restore uses the factory backup of the same MAC — backups must never be swapped between devices.
