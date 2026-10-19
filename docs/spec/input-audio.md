# OS Recording and Key Input Contract

English | [简体中文](input-audio.zh.md)

This contract supplements the [final product design](../design/nomifun-native-keyboard.md). Audio comes from the computer's default or user-selected system microphone; the device only provides the four keys and the status screen, is permanently NONE, and takes no part in audio capture.

## Recording identity and readiness

A K4 down makes Rust create the host recording/operation ID, confirm subtitle edits and the UTF-16 insertion position first, then prepare the selected ASR and the native input. The matching up ends the same segment; click never re-starts. A physical press has three states — Released/Waiting/Consumed — separate from the previous segment's audio/recognition state; while busy, keeping the key held continues after the previous segment settles, and releasing while waiting withdraws. Releasing before the start counts as a cancel; close and explicit actions do not inherit a not-yet-started press. Every callback binds the document ID, revision, recording ID, operation ID, and activation generation.

Use the input's actual sample rate, channel count, and format, converting incrementally to 16 kHz mono PCM. Default/selected devices must handle permission, switching, loss, and open failures — never fall back to an output device or fake a successful input.

Only this session's first valid non-empty native input callback proves capture started; all-zero data still proves the callback arrived. Do not claim "listening" from a `play()` return, K4 down, document recording state, an ASR partial, or `audioState=starting`. The actor publishes `capturing` after re-checking `handle.input_ready()`. The preparing cue covers editing/IME, ASR connection, and native starting together; only `capturing` shows the teal continuous listening animation — preparing is amber, finishing/recognizing is violet — all centered at the top.

Native startup uses a dedicated short-lived relay to avoid queueing behind the shared blocking pool; the first-callback wait is 5 seconds, and the native driver/permission plus actor startup bound is 15 seconds. A timeout closes admission while keeping the unfinished owner and continues cancel/stop coordination. Startup errors never join unboundedly, drop the owner, or fabricate a stop proof.

ASR prewarm is managed by a cancellable owned task. When the first K4 meets an unfinished prewarm, truly cancel the old future/connection and create a fresh prepare request for this hold. A 20-second absolute deadline covers queueing and connection; completion, panic, cancellation, and timeout each retire the task once. Ready must re-check generation, deadline, document, and hold authorization — an old task must not clear a new request or reopen the mic.

## Modes and submission

| Mode | Input and upload | Text submission |
| --- | --- | --- |
| Real-time streaming | Incremental upload per the vendor's real protocol; partial shown provisionally | Submit once only after native capture stop and the complete final are both in |
| Cloud batch ASR | Buffer this segment in memory while recording; wrap PCM16 WAV after the stop receipt and submit through the existing file/async ASR path | Settle only on a complete Transcript; Pending polls the same job/context without re-uploading |

Batch mode caps at 9.6M samples (16 kHz, 10 minutes); beyond that it stops and reports an error. Never fabricate partials, never save audio by default. Cancel permanently closes this segment's buffer admission and clears its content. The user explicitly picks one of the two modes in settings; errors never auto-retry across modes.

A normal stop closes the native stream, waits for in-flight callbacks, delivers the captured tail, then sends the one streaming end-of-input or submits one batch recognition. The streaming end signal seals the audio queue independently and is not lost when a pending send future is cancelled; the worker drains the PCM queued before the seal, then submits a single EOS/commit while fairly handling audio vs vendor messages. Terminal states close input admission; the next segment must not reuse a sealed or exited session. Explicit cancel and internal processing failures settle separately; every terminal state clears the current operation and lets a new legal press recover. During an active recording K2 takes this path first and polishes after the text finalizes; an active recording wins over an empty-body check.

K3 cancels the current unfinished operation during prepare, recording, finishing/recognizing, or polishing — without waiting for final, without submitting the cancelled segment, and without closing the window. Cancelling a recording truly stops the system input and drops the tail and buffer; a batch ASR not yet uploaded is never uploaded, and one already submitted has its request/polling revoked with late results rejected. Already-uploaded streaming audio cannot be recalled, but the local session is terminated and its later results rejected. Cancel keeps previously finalized text, revokes pending polish and a waiting hold intent; if K4 is still held it must be released before a new segment can start. K3 while idle changes neither text nor window. A normal K4 release still runs the selected recognition — no volume threshold replaces the explicit cancel.

Stop, cancel, close, disabling K4/the master switch, mode/input switching, device disconnect, lock/sleep, and quit all enter the same stop coordinator. Cancel drops the segment; a stop failure keeps the true state and the owner — never claim capture stopped by just dropping audio, halting uploads, or closing the UI. The device NONE receipt only proves onboard capture is off; it cannot substitute for an OS capture-stop proof.

Queues are bounded by audio duration and wait time. Only statistics like samples/nonzero/peak/sum_squares are kept for per-segment duration and level diagnosis — no audio content is retained. All-zero input is an explicit error; low volume, missing speech, or a missing final never auto-infer success.

## Body text and editing

Insert at the subtitle caret when one is valid, replace an explicit selection, otherwise append at the end of the body. Offsets bind this segment's identity as UTF-16 and reject out-of-range positions or half a surrogate pair; the insertion point is fixed once started. A partial never modifies finalized text, and an empty final never deletes the selection. The host injects no newlines or separators between recordings or between a streaming vendor's internal segments; existing CRLF/whitespace is preserved, and soft wraps never enter the copy result.

After finalizing, the caret advances to the end of the new text; it is only restored while the same subtitle editor still has focus and no IME composition is active — no extra focus calls. K4 never selects-all and never gives the subtitle a full-frame focus ring. Closing clears the round and the caret; a new document inherits no old position. Cancel-without-close keeps the finalized text. Late edit, audio, final, model, or window replies must not modify a new document or close a new window.

While the subtitle is focused, keep the system Ctrl+C / Command+C selection copy; do not bind hardware copy, auto-select-all, or auto-copy-all. The user pastes in the target app themselves — it never goes through NomiFun's action or injection paths. Esc enters the same close path and clears the round after real capture stop; Esc during IME composition first completes the composition without also closing the window.

## Platform and model boundaries

Windows uses native system input; macOS uses CoreAudio with the purpose declaration, permission, and audio-input entitlement configured; Linux records the actual ALSA/PulseAudio/PipeWire stack and session permissions. Native permission and session behavior are checked on the target platforms; build and deploy steps are in the NomiFun technical docs.

ASR, text models, language, dictionaries, and credentials reuse the existing NomiFun configuration; the device service holds neither audio nor credentials. K2 only sends the full body plus the polish instruction — it never creates an AgentSession, loads skills/MCP, or calls tools. Stage logs record only state, timing, generation, error class, and boolean gates — never text, audio, or credentials. Failure messages stay separate from sample-duration/level statistics; the subtitle shows only a short recoverable state with details on explicit expansion.

K2 uses the native single-shot text-transform API on the shared connection pool — no project config loading, no auto-retry, no model switching; pick the lowest available thinking tier per the exact model capability and cap the output budget. A candidate may stream as a provisional preview, and the body is replaced only after complete protocol success; failure or cancel restores the original. StepFun streaming ASR does not force-enable second-pass commit correction — it uses the vendor's default (off) when unconfigured; either way, the text is submitted only on a matching complete `completed`. Windows may initialize the COM enumerator early to shorten the first prepare, but must not open the mic early or loosen the true stop proof.
