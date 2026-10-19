# Final Firmware Structure

English | [简体中文](firmware.zh.md)

The firmware has exactly three components: `vk_usb`, `vk_input`, and `nk_screen`. `app_main` starts USB first, then initializes the screen; there is no alternative runtime entry or business plugin.

`vk_usb`'s single TX owner delivers complete JSON frames through a 16-entry FIFO. The input scanner debounces every 5 ms into a 32-entry queue; the protocol owner handles identity, NONE, Display, keys, epoch, and the 5-second lease. A new handshake and each new NONE wait for stale keys to be released; Display does not reset gestures. The device has no recording thread, audio data, or model credentials.

Host JSON input is capped at 512 bytes, with a 128-token workspace, strings up to 128 UTF-8 bytes, and depth 12; commands only need a flat object. Full JSON validation, duplicate keys, UTF-8, integer ranges, extra fields, and bounds are still enforced; only the read interfaces actually used are exported — the old asset features' generic iteration, boolean, and signed/64-bit getters are gone.

`nk_screen` owns SPI2 exclusively, keeping the fixed 119-command NV3007 init table plus local glyphs/graphics. The real 428×142 frame is submitted as 428×8 strips — the DMA buffer is only 6848 bytes. Fixed states, the Nomi breathe/blink, and key feedback contain no user text; the recording state is decided by the host's true state. A driver failure/timeout turns off the backlight and degrades independently — it must not block the four keys or impersonate an OS capture-stop proof.

The minimal ESP-IDF dependency closure links no I2S/AFE, ESP-SR/Opus, LVGL, asset upload, LED strip, OTA, or network/Bluetooth features. The NomiFun device service holds the serial port separately; subtitles, system recording, ASR, editing, configuration, and install belong to the main app. Full contracts: [USB](usb-protocol.md), [OS audio](input-audio.md), [status screen](screen-status.md). Build, offline tests, and rules protecting physical units are in the [firmware README](../../firmware/README.md).
