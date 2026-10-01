# Stage 3 Replay Validation Protocol V1.1 — Terminal-Tail PTS Amendment

> **Status:** REVIEW CANDIDATE — freeze only after focused + regression verification  
> **Scope:** Capture-integrity gate only  
> **Unchanged:** frozen physical profile, timing table, corpus ranks, event boundary, cursor rules, P/H definitions, OBS 0/0 declaration

## 1. Reason for reopening V1

During FINAL corpus acquisition, otherwise valid 1920×1080 / 120 fps OBS recordings repeatedly showed a single long PTS interval entering the final decoded frame after replay completion. The anomaly occurs in the recording tail after the operator intentionally waits 3–5 seconds before stopping OBS.

This issue was identified from capture-integrity inspection before examining FINAL-corpus P/H, MODEL_BELOW / FRAME_AMBIGUOUS / MODEL_ABOVE results. The amendment therefore does not use model-validation outcomes to select or relax evidence.

V1 rejected any PTS anomaly anywhere in the file. That rule is stricter than the timing evidence actually consumed by V1: event timing is based on click-counter event frame indices, and cursor fallback uses only ±4 frames around each event.

## 2. V1.1 authoritative rule

Whole-file PTS diagnostics remain mandatory. A video is timing-compatible when either:

1. every decoded frame has PTS and every adjacent decoded-frame interval is exactly `1/120 s`; or
2. **exactly one** PTS issue exists and all of the following hold:
   - the issue is a non-CFR interval, not missing PTS;
   - its endpoint is the **final decoded frame**;
   - the interval is **longer** than `1/120 s`;
   - that final frame is **strictly later than `last_event_frame + 4`**.

Case 2 is recorded as `COMPATIBLE_WITH_TERMINAL_TAIL_EXCEPTION`. It is non-blocking and does not modify any event timestamp, frame interval, physical prediction, human displayed time, or uncertainty calculation.

## 3. Still blocking

The following remain incompatible:

- missing PTS anywhere, including the final frame;
- any PTS anomaly before the final decoded frame;
- more than one PTS anomaly;
- a final interval equal to or shorter than `1/120 s` when non-CFR;
- a long final interval whose endpoint is at or before `last_event_frame + 4`;
- incompatible dimensions or average FPS;
- any existing reconstruction/layout/counter/cursor/capture-declaration failure.

No video may be transcoded, retimed, frame-generated, or otherwise repaired to satisfy this rule. Validation applies to the original OBS recording.

## 4. Collection helper

`check_cfr.py` remains a non-authoritative capture-only precheck and intentionally does **not** reconstruct events or calculate P/H. It may emit `PASS_WITH_TERMINAL_TAIL_NOTE` for exactly one long interval entering the final decoded frame so the operator does not discard the recording prematurely.

That helper result is only a **candidate** exception. The production validator must later confirm the authoritative `last_event_frame + 4` condition.

## 5. Evidence preservation

V1.1 output retains:

- all PTS issue frame indices;
- blocking PTS issue frame indices;
- exact PTS issue kind and rational interval delta;
- the accepted terminal-tail exception record, if any;
- source video SHA-256.

Previously captured whole-file-exact-CFR videos remain fully valid under V1.1.

## 6. Required verification before freeze

At minimum verify:

- exact-CFR synthetic video remains `RECONSTRUCTED` with unchanged authoritative P;
- middle PTS anomaly remains `INCOMPATIBLE_INPUT`;
- single long final interval beyond `last_event + 4` is authoritative and explicitly diagnosed;
- same anomaly inside the ±4 guard is rejected;
- short/backward final interval is rejected;
- missing/multiple PTS issues are rejected;
- FINAL capture declaration still requires OBS rendering-lag = 0 and encoding-lag = 0;
- existing replay-validation focused suite and full project regression remain green.

Only after those checks should the tooling be re-frozen and committed as V1.1.
