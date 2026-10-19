# NomiFun Native Four-Key Subtitle Keyboard — Product Design

English | [简体中文](nomifun-native-keyboard.zh.md)

Status: the single current product design; 2026-10-19, Asia/Shanghai.

The project is split into the `keyboard` firmware and the `nomifun-desktop` desktop app. This document defines product behavior; protocol, platform, and build details are covered by the technical documents below.

## Positioning and scope

A four-key keyboard controls NomiFun's native voice-subtitle tool. Audio comes from the computer's default or selected OS microphone; the keyboard provides four key events and the Nomi status screen. The runtime chain is Rust/Tauri and is installed, updated, and uninstalled with NomiFun.

The core flow: hold K4, wait for the teal listening cue, speak → release to recognize and finalize → edit, or press K2 to polish the full text → select text in the subtitle and take it with the system copy shortcut. K3 cancels the current unfinished operation at any time while keeping previously finalized text. Streaming recognition shows provisional subtitles while speaking; cloud batch ASR recognizes after release. This cycle does not include custom system hotkeys, cross-app text injection, agent workflows, onboard keyboard recording, or a USB Audio microphone.

Windows, macOS, and Linux are supported. The main workspace keeps the 880×600 contract, and the subtitle is a separate small window. Keeping other apps foregrounded continuously is not a phase-one acceptance requirement; the existing least-activating display approach continues, and explicit editing plus K1 focus behavior follow this document.

## Key roles and body-text lifecycle

| Key | Fixed behavior |
| --- | --- |
| K1 | If the main app is not running: launch and show it; if the main window is in the background: show and focus it; if in the foreground: hide to tray |
| K2 | Polish the current complete finalized text with the configured tool-free text model |
| K3 | Cancel the current prepare/record/recognize/polish, revoke pending actions, keep finalized text and the subtitle window; no side effect when idle |
| K4 | Press to save subtitle edits and the selection, then prepare and start the OS microphone; release to stop the segment, collect the tail and the recognition result, and submit once |

Physical keys k1–k4 map fixed to K1–K4 — no calibration or custom mapping. K1–K3 consume click; K4 consumes the matched down/up pair, and the same gesture's click does not restart recording. K1's window toggle does not interrupt subtitles or background recording. The K2/K3 per-key switches only update host-side operation authorization; they do not reset device press state, and an active K4 recording still ends on its key release. The physical K4 hold intent is independent of the previous segment's recognition finishing: holding again during finishing waits and auto-starts when the previous segment ends; releasing while waiting withdraws — an already-released tap is never replayed. Once a recording is truly established, the hold is consumed once; repeated down/up create no extra recordings. Releasing before listening counts as a cancel. Cancel, stop, polish, close, disable, and reconnect revoke the corresponding waits; closing an old document never carries a not-yet-started hold into the new one.

The first recording creates a new document. Later recordings into the same document follow these rules:

- The user placed a caret inside the subtitle: insert there; text explicitly selected: replace the selection.
- No valid position: append directly at the end of the body — never add newlines, spaces, or other separators for the new recording.
- Whitespace, CRLF, and line breaks from the user or ASR are kept as-is; multiple internal segments of a vendor stream are concatenated in order. Visual wrapping depends on window width and never enters the copy result.

The selection binds the document ID, body revision, edit identity, and this recording as UTF-16 offsets; out-of-range positions and split emoji surrogate pairs are rejected. Once recording starts the insertion point is fixed; partials are only a provisional preview and never change finalized text. The segment is submitted once after both the stop proof and the ASR final are present; an empty result never deletes selected original text. On completion the caret advances to the end of the new content.

When idle and system recording has stopped, the user may explicitly click into the body to edit — Chinese IMEs, Unicode, line breaks, and selections are supported, and an empty body may be saved. Edits bump the revision and become the baseline for later polish and restore-original; saving the same text does not reset the baseline. In-progress IME composition and unfinished saves are coordinated in order; K2/K4 wait for the current edit to confirm before using the new full text; K3 cancel does not depend on edit-saving or model results and immediately revokes the current unfinished operation. A failed or timed-out save revokes automatic actions and keeps this round's draft; close, cancel, document switch, and reconnect revoke pending actions — stale replies must not occupy a new document's edit task.

The body is read-only while recording and during model processing. K4 never selects-all and never draws a full-frame focus ring on the subtitle; while the subtitle editor still has focus it shows a thin caret hint. On completion the caret is restored only if the same document and the real editor focus are still valid and no IME composition is active — it never steals focus to restore a position.

The close button, or Esc while the subtitle is focused, ends the round: revoke processing and pending actions, and after a real capture stop and successful hide, clear the body, the original text, candidates, the caret, and all operation identities. The next recording is a new document. K3 and the toolbar cancel only end the unfinished operation, keeping finalized text and the window; cancelled segments, provisional subtitles, candidates, and late results must never be written back. After K3 cancels a recording, even a still-held K4 does not auto-restart — it must be released and pressed again. Body text and recordings are not persisted by default and do not survive restarts or rounds.

## Standalone subtitle window

Default size 720×112, minimum 360×80, both in Tauri logical units. The window is transparent, with no system shadow, persistent title, hint card, or maximize/minimize entry. By default it shows only light-pink body text with a thin outline; the full text is selectable and scrollable. It first sits bottom-centered in the current screen's work area; once dragged it remembers its position, and on restore it is clamped into the visible area given the current work area, multi-monitor layout, and scaling.

Body text uses the system UI font, default 14, settable to integers 12–32. Font size only affects rendering and caret-position measurement — never the body, offset semantics, model input, or the copy result; older settings missing this field use the default.

On hover, or when the window has focus, a translucent gray interaction layer with an icon toolbar appears; it is hidden by default. The toolbar offers drag, stop, cancel, polish, restore-original, pin-on-top, and close, all keyboard-operable. Buttons and physical keys enter the same Rust operation coordinator.

While the subtitle is focused, copy uses the system `Ctrl+C` (`Command+C` on macOS) with system selection semantics; the user pastes in the target app themselves. With no selection it does not silently switch to copy-all; no app-level clipboard command or cross-app paste is created. `Esc` closes and clears the subtitle; during IME composition Esc first cancels the composition without also closing the window. These shortcuts apply only while the subtitle is focused — no global hotkeys are registered.

The status cue is fixed top-center with room left for the toolbar, overlapping neither at minimum nor default width. Failures use a short cue outside the body text; details appear only on explicit expansion, and diagnostic statistics are never concatenated into the body or the copy result. The settings page only shows feedback for local config requests, system input, and tests initiated from that page — it does not repeat historical failures of subtitle documents.

| State | Expression | True meaning |
| --- | --- | --- |
| Preparing | Amber waiting cue | Waiting for the previous segment's finish, an edit/IME save, ASR connect, or input-device startup; capture not yet confirmed |
| Listening | Teal animated bars with a short cue | This session's first valid non-empty native input callback arrived; the actor confirmed capture ready |
| Finishing/recognizing | Violet cue | Stopping and draining capture, or waiting for the selected ASR's complete result |
| Error | Short diagnosable error | Never fabricate success; keep recoverable text and operation entries |

The bars express the capture lifecycle — they do not impersonate real sound pressure or voice activity. All-zero samples can still prove the input callback started, but an all-zero recording cannot manufacture a successful recognition. Stop or cancel is available while preparing; on key release, stop, cancel, or error the listening animation is withdrawn immediately — the cue disappearing is not a stop proof. Cues are never written into the body, model requests, or the clipboard, and no sounds are played.

During K2 processing the original body stays; the glyph cores brighten while a magenta tight halo and a soft ice-blue outer glow breathe smoothly — only one real copy of the text is drawn. The effect stays around the glyphs — no full-window veil or rectangular glow frame; with reduced motion a static glow remains. The body is replaced only on complete success; finishing or cancelling restores default text; the model or submission is never delayed for the animation.

## Operation coordination and failure semantics

| Current state | K2 | K3 | K4 |
| --- | --- | --- | --- |
| Idle, empty body | Cue "nothing to polish" | No side effect | Start a new segment |
| Preparing | Revoke the not-yet-started capture, then process finalized text | Revoke prepare and pending actions | Release revokes the prepare |
| Recording | Stop the segment, wait for tail/final, then polish | Truly stop capture, drop the segment, cancel its ASR | Release ends the segment normally |
| Finishing/recognizing | Register one polish-on-complete intent | Revoke the request and the polish intent, drop the segment's provisional results | Still held: continue after completion; release withdraws the wait |
| Body ready | Polish the full text | No side effect | Insert at selection or append |
| Polishing | Merge repeated presses, no duplicate requests | Cancel the candidate and the request, keep pre-polish text | Wait for completion or cancel |

An active recording wins over an empty-body check. At most one polish intent is registered during finishing; K3 revokes it immediately without waiting for the ASR final or the polish to succeed. Cancel never submits the segment, triggers a new recognition, copies, or closes the window; already-uploaded streaming audio cannot be recalled, but the local session is terminated and its later results rejected. In batch mode a not-yet-uploaded buffer is simply cleared; a submitted one has its local request or polling cancelled, and a late completion is not written into the body. A normal release still runs the selected ASR — silence thresholds never guess that the user wanted to cancel.

Polish calls the native single-shot text-transform API directly, passing only the current full text and the polish instruction, requiring preservation of meaning, facts, names, numbers, dates, code, and proper nouns. It loads no agent session, skills, or project config, never auto-retries or switches models; it picks the lowest available thinking tier per the exact model declaration, with the output budget bounded by both body size and the model cap. Candidates preview provisionally in-place inside the existing text and glow, and are committed only on complete success. Failure, cancel, or truncation keeps the original, which can be restored.

Document ID, revision, recording ID, operation ID, and activation generation isolate all callbacks, edit tasks, model candidates, and window requests. A cross-side cancel generation voids actions queued behind a UI edit save while keeping the draft — a late save cannot restart a cancelled polish or recording. Cancel and close are accepted per the current document ID; a revision bump from saving the same document does not block control; a new document is strictly isolated and old cancel generations do not affect new operations. Body edits and model results still check the matching revision. Duplicate keys, cancels, reconnects, window rebuilds, old-document closes, and late results must not duplicate requests, duplicate appends, or close a new document. A native stop failure keeps the owner and a diagnosable state — ignoring audio or clearing the UI must never pose as "stopped".

## Settings and models

"Settings → Extension Keyboard" centrally provides:

- Device connection, device identity/serial port, and firmware version. The internal protocol handshake and the NONE safety state are managed by the native service and are not user settings.
- The "Enable K2–K4" master switch plus three per-key switches. The master switch does not affect K1, and toggling it preserves per-key preferences.
- Default or selected system microphone, permission/capture state, ASR mode, the corresponding model, language, dictionary, and a recording test.
- Text model and the whole-text polish instruction; subtitle pin-on-top, position reset, open, and font size.
- Launch-at-login, background-service state, and exit-all-services.

Switches take effect through the existing settings path; model, input, and window preferences are saved/reverted on the settings page. Disabling K2/K3 blocks the corresponding new hardware actions; disabling K4 or the master switch must cancel the current segment, truly stop system input, and block new recordings while keeping finalized text. The master switch also revokes unfinished hardware actions and pending polish. Overlay buttons and the in-subtitle system edit shortcuts remain available for explicit user actions.

ASR and text models reuse NomiFun's existing model directory, vendor connections, and credentials; settings store only existing model references — no second key store or model directory is built. K2 is a tool-free text transform: it creates no AgentSession and loads no skills, MCP, or tools.

The user explicitly picks one of the two ASR modes; a streaming failure is never silently turned into another possibly billable request:

| Mode | Capture and submission | UI / completion condition |
| --- | --- | --- |
| Streaming | Native PCM incrementally converted and uploaded per the vendor's real streaming protocol; stop sends end-of-input once | Partial preview in real time; settles when final and capture-stop are both present |
| Cloud batch ASR | Buffer the segment's PCM in memory; wrap WAV after a real capture stop and submit once through the existing file/async ASR interface | Recording clearly says "recognize after release", fabricates no partial; accepts only a complete Transcript |

Batch mode is capped at 10 minutes; beyond that capture stops with an error. Async recognition polls along the same submitted job/context — never re-uploads. Cancel clears the buffer and does not save the recording by default. After capture ends, diagnostic statistics like duration and level may be kept — never the audio content; failure, truncation, cancel, and timeout never land in the document.

## Native audio and the prepare phase

The main app enumerates and holds the single OS input stream, handles the actual sample rate, channels, and format, and converts incrementally to 16 kHz mono PCM. Only the first valid non-empty native callback proves this capture started — readiness is never inferred from a K4 down, document-recording state, a `play()` return, or an ASR partial.

Audio startup reaches the single owner through a dedicated short-lived relay instead of queueing behind the shared blocking pool. The first-callback wait is 5 seconds; native driver/permission waits and the actor startup bound are 15 seconds. A timeout revokes admission, keeps the unfinished owner, and keeps waiting for the real stop receipt — error paths never join unboundedly.

The Windows main app may pre-arm the existing COM runtime and device enumerator in the background without creating or playing a microphone stream early. StepFun does not force-enable second-pass commit correction; unconfigured uses the vendor's default (off), while an explicit config is honored — and either way, only a matching complete `completed` finalizes text. Time bounds are failure boundaries, not fixed waits; anonymous stage timings record mic-open, stop, config parse, response headers, first text, and completion separately, without blending vendor time into UI state.

A background ASR prewarm must be a cancellable task with a start time. When the first K4 hold meets an unfinished prewarm, truly cancel the old future, then build an independent request for this hold — the user does not need to release and re-press. The 20-second absolute deadline covers queueing, config, and connect; Ready must still re-check deadline, document, activation generation, and the current hold state. Completion, panic, error, and timeout each retire the task and release the connection — never merely ignore the result or let an old task clear a new task's handle. An idle-prewarm failure only backs off and reconnects — it does not touch the body, edit/polish tasks, or existing errors; user-triggered connect and record failures keep a localized reason with retry guidance and coordinate a real capture stop.

A normal stop closes the native stream, waits for in-flight callbacks, delivers the captured tail, then ends the streaming input or submits the batch ASR. Cancel, close, disable, mode/device switching, lock/sleep, input loss, device disconnect, and quit all stop system capture and revoke pending actions; recovery requires pressing a key again. Queues are bounded by audio duration and wait time; stage logs record only state, durations, generations, and boolean gates — never text, sound, or credentials.

## Device service, firmware, and the status screen

A lightweight Rust device service enters standalone mode before the normal main window and single-instance init, solely owns the serial port, and sends keys and device state over authenticated local IPC. It holds no model credentials, subtitle text, or OS recording. With no main app it waits for K1 to launch it, throttling starts to avoid a press-storm. The service always takes cold-start requests on k1 and stores no key mapping.

K4 is not admitted before the main app is ready; on every connect, service recovery, and wake-from-sleep, `voice_key:none` is applied and only the real confirmation, cleared stale gestures, and released old keys allow arming. The final protocol requires native v1, system audio source, and NONE with zero session; an onboard audio frame is an explicit protocol error and never reaches ASR. Device identity cannot be inferred from the generic VID/PID or a port name alone.

The current firmware source version is `0.3-screen.2`; the version installed on hardware is recorded separately in local private records per the rules in [DEVICE.md](../../DEVICE.md). The minimal ESP-IDF firmware contains only four-key debounce, strictly bounded USB JSON/identity/epoch/lease/NONE/release gating, and the necessary status screen. The components are `vk_input`, `vk_usb`, and `nk_screen` — no onboard I2S/AFE/Opus, LVGL asset upload, LED, networking, agent, or OTA features.

The NV3007 screen is 428×142 and shows the Nomi eyes, blink/breathe, four-key feedback, connect/main-app sleep, and the fixed prepare/listen/recognize/polish/error states — K3's hint is `CANCEL`. `listening` is shown only from the host's true capture state; user text is never displayed. A separate screen owner uses small-strip DMA; a screen failure degrades independently and must not block USB, a key release, or a capture stop. Brightness differs between normal and sleeping; key feedback does not mean the mic is open.

A normal main-app quit stops models and OS recording and confirms DesktopStopped to the device service, which keeps waiting for K1; "exit all services", install updates, and uninstall stop the device service through the management endpoint. Before an install replaces files it must confirm GUI capture-stop/exit and serial-owner release — failure or timeout blocks the replacement; uninstall cleans the login registration after stopping services and keeps user data.

Firmware source can be modified and built offline; flashing separately binds the real device MAC, image hash, partitions, the complete factory backup, and the recovery path — no concrete authorization, no flashing. Flashed images, private raw evidence, recovery backups, and licenses are retained; they do not constitute a legacy product runtime path.

## Platform implementation and verification boundaries

| Area | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Login device service | Per-user HKCU Run, install path, stop-service cleanup | Aqua LaunchAgent, real .app path and signing identity | XDG autostart inheriting the graphical session; AppImage uses a persistent path |
| USB | COM enumeration, exclusive, stable identity | /dev/cu.*, exclusive and hot-plug | ttyACM/ttyUSB, udev/uaccess permissions |
| Input | Native system input and permissions | CoreAudio, purpose declaration, audio-input entitlement | Current system audio service, default or selected input |
| Main window/subtitle | Native show/hide/pin-on-top | AppKit main-thread window ops | GTK; X11 and Wayland compositor paths |
| Subtitle editing | WebView2 system selection copy, IME and Esc | WKWebView Command+C, IME and Esc | WebKitGTK system selection copy, IME and Esc |
| Distribution | NSIS install/update/uninstall stop-service hooks | Signed updates and in-package uninstall script | deb/rpm lifecycles, explicit AppImage uninstall script |

Linux X11, GNOME Wayland, and KDE Wayland use their respective window management and WebKitGTK system clipboard paths; the default Wayland window backend is XWayland, with dependencies and udev rules configured per distribution format. Pure Wayland without XWayland is not a current window backend.

macOS uses CoreAudio/AppKit, per-user login services, and signed distribution configuration, supporting arm64/Intel. Native build, permissions, login, subtitle/edit/clipboard, sleep, and install-update checks run on the target Mac — see the NomiFun technical docs for the concrete steps.

## Engineering maintenance

Core regression covers document/operation identity, K3 cancel at each stage and late results, true capture stop, UTF-16 editing and IME, continuous body text, system selection copy/Esc inside the subtitle, settings persistence, dual ASR, the model's tool-free boundary, windows, device NONE/Rearm/auth/single-owner, and the packaging lifecycle. Concrete commands are in the NomiFun technical docs; after touching the renderer run `bun run check:desktop-ui-boundary` and the related checks.

Keep a single implementation for source, tests, and entries. Generated logs, run reports, and screenshots are never committed; factory recovery material and private hardware evidence are kept separately on the maintainer's machine. Product docs only track current behavior and technical contracts.

## Implementation and contract entry points

- [USB protocol](../spec/usb-protocol.md), [OS audio contract](../spec/input-audio.md), [status screen contract](../spec/screen-status.md), [firmware structure](../spec/firmware.md).
- [Device and recovery](../../DEVICE.md), [provenance and licensing](../../SOURCE.md), [build and flash instructions](../../firmware/README.md).
- NomiFun implementation and platform notes: `nomifun-desktop/docs/architecture/native-keyboard.zh.md` (NomiFun repository).
