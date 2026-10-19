# Four-Key + Status Screen Firmware

English | [简体中文](README.zh.md)

The only firmware entry is `main/app_main.c`; the current source version is `0.3-screen.2` with just `vk_usb`, `vk_input`, and `nk_screen`. The device is always NONE, emitting only the four key events and fixed screen states — K3 shows `CANCEL`; OS microphone, ASR, subtitles, and editing belong to NomiFun. USB starts first; the screen uses a separate low-priority owner with a 6848-byte DMA strip, and a screen failure degrades independently. The version actually installed on hardware is recorded in local private device records — an offline build does not mean it was flashed.

A transport or queue fault closes the current epoch; the single USB owner returns to awaiting a new handshake only after confirming both the TX task and the driver's send buffer drained, and clearing stale commands and gestures. If the driver is still busy or cannot be proven quiet, the fault persists; recovery still requires a new transport, NONE, and all keys released — stale presses are never replayed.

There is no I2S/AFE/Opus, ESP-SR, LVGL/asset upload, LED strip, agent, OTA, or networking code. JSON keeps only the interfaces current commands use, bounded to a 512-byte input, 128 tokens, and 128-byte strings; full validation and malformed-data rejection remain. The three-component structure is in the [firmware contract](../docs/spec/firmware.md); USB and screen fields are in the [USB contract](../docs/spec/usb-protocol.md) and the [status screen contract](../docs/spec/screen-status.md).

## Build and offline verification

From the repository root run `./tools/build.ps1` (Windows) or `./tools/build.sh` (macOS/Linux/WSL) with ESP-IDF 5.5.3. The output is `firmware/build-native-screen/vibe_keyboard.bin`, after which `firmware/tools/validate_build.py` runs automatically. It checks that production logs/console are disabled, 16 MiB Flash, the actual `ota_0` layout, image size and checksums, and that no disallowed feature symbols are linked. The generated build directory and sdkconfig are local caches — neither source nor a distribution entry.

Inside `firmware/`, run `python3 tests/run_native_tests.py` (requires `cc`; use WSL on Windows). Five C programs plus a panel-failure scenario cover: the four-key/NONE path and final capability fields, epoch/release/idempotence, strict JSON bounds and u32, debounce, the 119-command panel init/window/byte-order/backlight, strip-vs-full-framebuffer pixel equality, and backlight-off on failure/timeout. To get previews, pass an explicit output directory to the test script, then convert with `tools/render_screen_preview.py`; the full framebuffer is used only by offline tests.

## Images and recovery

Build output is the offline product of the current source; it does not mean any hardware was updated. Hardware specs, partitions, and recovery rules are in [DEVICE.md](../DEVICE.md); real identities, installed images, and the factory-backup mapping are recorded in the maintainer's ignored `host/local/device-recovery-record.zh.md`. Full factory backups live outside the repo per MAC; flashed app copies and their licenses sit in `host/local/flashed-images/` and are never a product distribution entry.

Flashing requires per-image, separate verification of authorization, partitions, and the recovery path — never run the all-flash command IDF prints automatically, and never modify the bootloader, partition table, NVS, OTA metadata, storage, or eFuse. Historical flashed images and their licenses are private hardware-tracking material only; they carry no corresponding source and no second product runtime path.
