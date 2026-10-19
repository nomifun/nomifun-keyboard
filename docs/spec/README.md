# Technical Contracts

English | [简体中文](README.zh.md)

The single product scope is defined in the [final product design](../design/nomifun-native-keyboard.md): OS microphone, dual ASR, a standalone transparent editable subtitle overlay, caret insertion / direct continuation, adjustable font size, a true top-center capture indicator, and a glyph polish glow. The main workspace stays at 880×600; keeping other apps in the foreground is not a phase-one acceptance requirement.

- [Hardware and recovery](hardware.md)
- [Four-key / NONE / Display USB protocol](usb-protocol.md)
- [Operating-system audio](input-audio.md)
- [Nomi status screen](screen-status.md)
- [Firmware structure](firmware.md)

The keyboard only emits the four keys, is permanently NONE, and shows fixed states. Factory recovery material, images actually flashed to hardware, and not-yet-flashed new builds are recorded separately; there is exactly one final firmware plus the NomiFun native implementation.
