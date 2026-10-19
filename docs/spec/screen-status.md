# Keyboard Status Screen Contract

English | [简体中文](screen-status.zh.md)

## Picture and states

The panel is an NV3007, 428×142 RGB565. The local C renderer draws the Nomi eyes, fixed state labels, and the four-key hints `K1 MAIN`, `K2 POLISH`, `K3 CANCEL`, `K4 TALK`. No user text, model text, or uploaded assets are transferred. Rendering includes breathing, blinking, and sleeping expressions, plus a brief key highlight and gaze feedback. A K4 highlight only marks a key event; `listening` must be sent explicitly by the host after OS recording is ready.

| Protocol state | Fixed label | Meaning |
|---|---|---|
| connecting | LINKING | Main app connecting or not ready |
| sleeping | SLEEPY | Main app not running or exited |
| ready | READY | Operations accepted |
| starting | MIC START | Preparing to record |
| listening | LISTENING | OS capture is ready |
| recognizing | ONE MOMENT | Finishing or batch-ASR recognition |
| polishing | POLISHING | Text polish in progress |
| error | OOPS! | Operation failed |

## Driver and memory

The USB core starts first; a separate low-priority screen owner initializes the panel and refreshes periodically. The production driver uses a `428×8×2=6848`-byte DMA strip submitted contiguously over the full-frame window; RGB565 goes high byte first with a y offset of 14. A full framebuffer exists only for offline preview and strip-consistency tests.

SPI2 uses MOSI21 / CLK14 / CS11 with DC13 and RESET12 at 40 MHz; the single owner takes the bus with `portMAX_DELAY`. The 119 panel init commands come from the [pinned upstream revision](../../SOURCE.md): flush an initial frame first, then send DISPON and enable the backlight.

The GPIO9 backlight uses LEDC 5 kHz, 8-bit PWM: duty 115/255 normally, 45/255 while sleeping. If init, an SPI commit, or a state apply fails, the screen degrades and its backlight turns off without affecting the four-key USB channel. A state apply waits at most 500 ms for the render confirmation.

## USB and host synchronization

```json
{"event":"nk_display","epoch":1,"request_id":2,"state":"listening"}
{"event":"nk_display_applied","epoch":1,"request_id":2,"state":"listening","applied":true,"frames":42,"backlight_on":true,"pwm_duty":115,"buffer_bytes":6848,"visual_verified":false}
```

Commands use strict keys; the epoch, request_id, and idempotence rules are in the [USB contract](usb-protocol.md). `applied:true` is returned only after the full frame's SPI commit and the backlight update both succeed. `frames` is the driver's commit counter, and `visual_verified:false` makes explicit that a receipt does not prove the physical panel's orientation, colors, brightness, or ribbon state — after changing boards, wiring, or images, the physical display still needs checking.

The capability field is `display:{version:1,available:true,width:428,height:142,privacy:"status_only"}`. When unavailable it returns `available:false` with `reason:"driver_unavailable"`. Availability changes publish adjacent info/capabilities in the same epoch; the host applies NONE only on the first handshake, and a capability refresh does not reset keys already received.

Host IPC uses `Control::Display{state}` and carries no text. The USB owner keeps at most one pending-ack request at a time, with NONE taking priority; pending display requests are merged to the newest state, and a screen request never blocks a K4 release. Error receipts, timeouts, or driver faults only update `DeviceStatus.displayAvailable/displayState/displayDetail`; they never raise the generic Failure that stops OS recording.
