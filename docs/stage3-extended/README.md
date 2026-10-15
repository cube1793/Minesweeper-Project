# Stage 3 Extended

## Status

Stage-3 V1은 **FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED**이며 frozen baseline이다.
ZiNi Improvement도 **CLOSED / V1 RETAINED**이고 미개봉 최종 holdout은 그대로 유지한다.
**Stage-3 Extended는 ACTIVE**다. 이 문서는 의존 관계에 따른 roadmap이며 고정 구현 일정이 아니다.

첫 milestone **Execution / Playback / Visualizer Foundation**은
**FINAL ADJUDICATION PASS / CLOSED (2026-10-14)**다.
자동 검증과 실제 Windows worker/profile/startup, 사용자의 packaged interactive
acceptance, 독립 Claude 감사 및 ChatGPT 최종 판정이 모두 PASS다.
[최종 판정](STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)에 종료 범위와 F-1/F-2 처분을 기록했다. [Slice 5 수용 기록](STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)에
수동 tester/date, 네 terminal path의 PID·job-directory cleanup 및 controls PASS를 기록했다.
Foundation 판정은 해당 milestone만 닫으며 Stage-3 Extended 전체는 계속 active다.

## Foundation — closed / integrated

- Execution integration audit: 구현에 반영되어 완료.
- Slice 1 — Execution Context + Pure Trace Playback (`cf7544b`).
- Slice 2 — Subprocess Execution Worker (`d100a49`).
- Slice 3 — Read-only Stage-3 Visualizer Window (`490a8cf`).
- Slice 4 — Application Integration + Process Lifecycle (`b9af830`; pre-Slice-5 baseline).
- Slice 5 — Acceptance / Packaging / Documentation Closeout (`18964ad`): **CLOSED**, committed/merged/pushed.

Full commit identities and the dated Git baselines are in the acceptance and final
adjudication records. `18964add02c508d67429ef29cb59ce879c01017d` is the Slice 5
documentation closeout / independent-audit baseline, not a permanent latest HEAD.
Current components are `Stage3Execution`, worker, parent-owned `Stage3ExecutionJob`,
launcher, pure `Stage3TracePlayer` / `Stage3ModeledPlayback` and execution-only viewer. Indexed
`EXPERT_GENERAL_V1` execution is independent of the current Live/Replay board.

## Foundation final adjudication — CLOSED

Historical 2026-10-14 Foundation acceptance and user-performed packaged manual acceptance are complete.
Normal success, Cancel, launcher-close and main-close during active jobs passed,
with each owned worker gone and job directory removed. Parent PID 5352 also exited
on main close. Playback, responsiveness and retained-result reopen passed.
The Foundation documentation closeout changed no production Python, profile or playback-seek behavior.
Source tests: **1628 passed, 0 failures/errors/skips** in the development environment.
The independent audit also passed: focused **122**, frozen protection **92**,
Stage-2 / ZiNi / Replay / Stage-3 benchmark boundary **86**, full suite **1628**
with **0 failures/errors/skips**, and packaged-worker deterministic equivalence.
ChatGPT final adjudication: **BLOCKER 0 / REQUIRED production 0**.
F-1 is the required documentation-only historical/current-state correction,
addressed by this closeout; it is not an implementation blocker.
F-2 remains **OPTIONAL / DEFER** for future worker/release transport hardening.
That Foundation closeout published no release/tag.

## Version / Settings Identity Separation — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**.
[Closeout evidence](STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md) records the live
implementation baseline, 376 focused / 1639 full tests (zero failures/errors/skips),
fresh Windows package/profile/worker equivalence and user-performed native GUI PASS.

- Public Fixed Identities (`858dc1a`): immutable fixed V1 algorithm identity,
  physical-owner identity descriptor and unchanged benchmark snapshot consumers.
- Identity-backed Visualizer Labels (`e04d4e8`): separate Algorithm / Physical
  labels and a current `Playback: Index · N ms/step (presentation)` label.

| Identity | Current ownership / meaning |
| --- | --- |
| Application/release | Release/tag/build documentation; no runtime version constant, and current main is not historical v0.2.0 |
| Stage-3 algorithm | `stage3_identity.STAGE3_V1_IDENTITY`; distinct from telemetry semantic version and execution configuration |
| Physical model/profile/table | `stage3_physical.MODEL_C_V1_IDENTITY` and substantive authentication; `Model C` alias is separate |
| Playback/presentation | Viewer-local Index/Modeled-Time; Index 20..5000 ms, default 200 ms; modeled default 1×; no QSettings or presentation version |

`Stage3Execution(spec, board, result)`, worker transport and all frozen semantics
remain unchanged. No migration, algorithm/profile selectors, registry or new runtime app version.

## Modeled-Time Playback / Synthetic Smooth Cursor Presentation — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**.
[Closeout evidence](STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md) records Slice 1–3 commits,
254 focused / 1699 full tests with zero failures/errors/skips, a fresh package,
frozen profile equality, packaged worker equivalence and the project user's
native packaged GUI report **"A–K passed"**.

- TracePlayer uses failure-atomic incremental `next()`; arbitrary seek and previous
  retain reconstruction from index 0.
- The Qt-independent controller owns exact partial modeled time, monotonic anchoring,
  pause/resume, speed and multi-action catch-up using recorded durations.
- Index remains default, 20..5000 ms/step, default 200. Modeled-Time uses
  0.25× / 0.5× / 1× / 2× / 4× / 8×, default 1×, without persistence.
- The UI requests frames every 16 ms; the controller clock is authoritative.
  Partial frames update only the overlay; catch-up refreshes the board once.
- Straight smoothstep `q = u²(3 - 2u)` uses rendered cell centers. Same-cell actions
  stay stationary; no separate dwell model. Actions commit at modeled boundaries.
  Pause preserves partial progress; manual navigation and mode changes cancel it.

The synthetic cursor is presentation, not an actual OS trajectory or physical
acceleration model. Rates/easing never alter recorded costs, Model C or planner input.

## Roadmap

1. **CLOSED** — Execution / Playback / Visualizer Foundation.
2. **CLOSED** — Version / Settings Identity Separation.
3. **CLOSED** — Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **NEXT** — Human Mouse Trace / Path Visualization (not implemented).
5. **NEXT AFTER THAT** — Same-board Human / Stage-2 / Stage-3 Comparison.
6. **LATER** — Representative demonstrations / Timeline Analytics.
7. **LATER** — First actual Extended algorithm research.

For the last item, nearest exact-minimum-risk guess selection among equal-risk
candidates using movement cost remains a candidate, not an adopted policy or
authorization to modify V1. External screen-recording tools remain the default.

## Next planned milestone — Human Mouse Trace / Path Visualization

**Not implemented.** This small milestone was inserted after Modeled-Time closeout
preparation; it precedes Same-board Human / Stage-2 / Stage-3 Comparison.
This closeout changes planning/documentation only and creates no implementation/spec document.

Initial scope:

- Record actual mouse movement only while the cursor is over the Live game board.
- Store sampled pixel-space cursor points/timestamps separately from Replay.
- Retain actual action/click markers.
- After game completion, visualize the recorded cursor path over the board.
- No OS-global mouse hook and no Stage-3 synthetic cursor reuse.
- No physical-model calibration/refit or advanced path analytics yet.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human Mouse Trace is actual sampled Live-board cursor movement presentation data,
not Stage-3 synthetic movement and not Model-C calibration evidence.

## Deferred / evidence-triggered

- Arbitrary-seek checkpoint/cache optimization.
- Modeled-time slider / sub-action scrubbing.
- 120-fps UI target, easing selector and click pulse.
- Persistent Stage-3 presentation settings; settings dataclass until an external consumer exists.
- Runtime application/release display or version constant.
- Selectable algorithms/profiles and durable cross-version Stage3Execution transport.
- Richer physical model / Model C successor or refit.
- Action-specific OPEN / FLAG / CHORD timing and physical CHORD variants.
- CPS / burst / minimum inter-action constraints, anisotropy and human cognitive timing.
- Built-in screen recording unless later justified.
- Known-mine / no-flag execution and richer / longer planning.

Revisit only with evidence and a separate specification/evaluation contract.
Incremental forward is implemented; arbitrary seeks still rebuild from index 0.
Clearer Run/new-execution versus 결과 열기/retained-result labels remain a nonblocking
UX follow-up. Final WON with Step 0/current PLAYING and manual seek stopping autoplay
remain correct. Foundation F-2 stays **OPTIONAL / DEFER**; this closeout supplies no
new evidence to promote that transport-hardening item.

## Boundaries and references

`Replay != Stage-3 Trace Playback != ZiNi Trace`. The viewer never supplies solver
decision input. Playback interval is not Model C time, CPU speed or human speed.
V1 official 100k results, algorithm, profile and qualification remain frozen.
Extended is separate scope and does not reopen accepted V1 or closed ZiNi work.

- [V1 final adjudication](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Frozen algorithm](../../STAGE3_ALGORITHM_SPEC_v1.md)
- [Frozen telemetry/benchmark specification](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Historical extension backlog](../../STAGE3_EXTENSION_BACKLOG.md)
- [ZiNi final adjudication](../zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md)
- [Documentation index](../README.md)
- [Current handoff](../CURRENT_HANDOFF.md)

New Extended records belong here. Existing frozen specs, audit/evidence paths,
official 100k artifacts and historical decisions retain their identities and locations.
