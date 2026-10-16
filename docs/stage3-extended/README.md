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

## Human Mouse Trace / Path Visualization — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-16)**.
[Closeout evidence](STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md) records qualified
implementation/package SHA `e32145fa5c114e1ce500ad2e837ef6000cc49cca`,
**627 focused / 1825 full source PASS**, fresh-environment **1800 PASS / 25 optional
skips**, packaged workers/native GUI/Replay v2 verification and final user native PASS.

- Actual Live-board event samples use board-local Qt logical pixels, exact subpixel
  positions and an independent monotonic trace clock. No timer sampling,
  min-distance filtering or semantic point dropping; continuity breaks form segments.
- Recording defaults ON per application/session and locks at the first committed
  timed human OPEN/FLAG. OPEN observes L release; FLAG observes R press.
  Untimed pre-start CHORD does not start trace. Recording OFF at the lock point,
  an actual Auto action or Replay append failure after a committed human action
  invalidates the Human trace.
- Action markers reference actual ReplayEvent indices. Replay v2 carries the
  separate trace attachment; v1 remains readable and trace-free. Display is optional.
- Physical gesture fidelity includes independent Mode-A/C R-press FLAG and
  origin-independent Mode-B BOTH, first-release CHORD at the current target,
  repeated overlaps and FLAGGED-center neighborhood preview.
- Primitive recorder storage, pre-start gating, transformed-geometry caching and
  a **16 MiB** bounded raster cache/fallback preserve exact samples. User testing
  accepted trace ON after hardening and found no noticeable final-package regression;
  this is not a zero-overhead claim.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human trace is pointer presentation data, not OS-global tracking, synthetic Stage-3
motion, Model C calibration evidence or solver input. Frozen V1 and official 100k
results retain their original identity and meaning.

## Roadmap

1. **CLOSED** — Execution / Playback / Visualizer Foundation.
2. **CLOSED** — Version / Settings Identity Separation.
3. **CLOSED** — Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **CLOSED** — Human Mouse Trace / Path Visualization.
5. **ACTIVE pending Slice 5 closeout — Slices 0–4 COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B; NEXT Slice 5 (not begun)** — Same-board Human / Stage-2 / Stage-3 Comparison.
6. **LATER** — Representative-board demonstrations / Timeline Analytics.
7. **LATER** — First actual Extended algorithm research.

For the last item, nearest exact-minimum-risk guess selection among equal-risk
candidates using movement cost remains a candidate, not an adopted policy or
authorization to modify V1. External screen-recording tools remain the default.

## Active milestone — Same-board Human / Stage-2 / Stage-3 Comparison

**Slice 0 — contract documentation COMPLETE / ACCEPTED.** The active
[comparison contract](STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md) governs exact
same-layout execution, first-open qualification, admission, identity, metric
separation and acceptance.

**Slice 1 — Comparison domain and admission COMPLETE / ACCEPTED** by ChatGPT
final review. The pure Qt-independent
[`same_board_comparison.py`](../../same_board_comparison.py) and its
[focused tests](../../tests/test_same_board_comparison.py) preserve the original
Human Replay and separate Mouse Trace attachment. Admission requires both
`source_type == SOURCE_HUMAN` and explicit `declared_full_game_human=True`;
neither metadata, declaration nor successful reconstruction proves exclusively
Human historical provenance. Identity uses exact layout equality and the existing
canonical fingerprint. Full-stream reconstruction rejects incomplete and
post-terminal streams; opening qualification remains factual, without implying
controlled experimental conditions.

Reported Slice 1 verification: **29 focused passed; 202 relevant regression
passed; combined reported total: 231 passed**, zero failures/errors/skips.
No full suite, package or native GUI run was performed for Slice 1.

**Slice 2 — Isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT final review.
**Slice 2A — Pure isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT
final review. [`same_board_runner.py`](../../same_board_runner.py) runs unchanged
Stage 2 (`accept_guesses=True`, `initial_open=(0,0)`, observer traces) and frozen
Stage 3 on separate fresh fixed-layout engines using the exact admitted Human
layout and authenticated Model C. Mined-origin immediate losses remain legitimate;
no regeneration or retry. Native result/Replay/trace authorities remain separate;
the Qt-independent immutable execution result/metric layer retains no live Engine
or fabricated benchmark identity.

Accepted `benchmark_modeled_time.evaluate_ordered_actions()` reuses existing
authenticated validation/cost logic for complete canonical ordered inputs,
including initial and terminal/losing costs, without DB, GameRecord or fabricated
telemetry/benchmark identity. Existing evaluator callers are preserved.
Human Replay elapsed seconds, each solver's Model C microseconds and each solver's
decision-compute nanoseconds remain separate. No Human Model C time, generic speed
field, winner, ratio or Timeline Analytics is added.

Reported Slice 2A verification: **31 new Slice 2A passed; 29 Slice 1 passed;
274 relevant regression passed; combined reported verification: 334 passed**,
zero failures/errors/skips. No full suite, package or native GUI run for Slice 2A.

**Slice 2B — Worker/process integration COMPLETE / ACCEPTED** by ChatGPT final review.
The dedicated PyQt-independent worker receives only a request token and fixed
ReplayBoard; Human Replay/Mouse Trace remain parent-owned. It executes the accepted
solver path once, without regeneration/retry or fabricated LOSS on failure.
`SameBoardExecutionJob` owns one child/private directory, cancellation/escalation,
reaping and cleanup; success attaches evidence to the exact original Human context.
Source/frozen dispatch is separate, with `--same-board-execution-worker` before Qt.
Parent validation rechecks comparison/outcome-bearing facts without recursively
walking nested decision evidence; native evidence remains retained unchanged.
See the [current handoff](../CURRENT_HANDOFF.md#4-current-milestone) for the accepted
lifecycle/validation boundary, corrected audit finding and qualified responsiveness
measurements (not zero GUI-thread blocking or frozen algorithm-performance evidence).

Reported final Slice 2B verification: **84 Slice 2B passed; 31 Slice 2A passed;
29 Slice 1 passed; 374 relevant regressions passed; combined reported verification:
518 passed**, zero failures/errors/skips. No full suite, fresh package or native
GUI acceptance was run for Slice 2B.

Slices 2A/2B remain internal parts of official Slice 2, not new roadmap milestones.

**Slice 3 — Pure playback coordination COMPLETE / ACCEPTED** by ChatGPT final review.
Pure Qt-independent [`same_board_playback.py`](../../same_board_playback.py) retains
three distinct runs (`HUMAN`, `STAGE2`, `STAGE3`): original Human and native Stage-2
Replays use existing `ReplayPlayer`; Stage 3 uses its fixed-layout trace player
without fabricated benchmark identity. Only recorded `trace.move` executes, never
planner evidence or plan suffixes. No solver/planner/worker/Model-C rerun occurs.

Each run retains its own action index/range; switching restores that index without
changing another run. Index 0 is the fixed all-HIDDEN board; n applies exactly n
inputs. Current `status` and final outcome remain separate, including PLAYING at
index 0 then LOST at index 1 for a legitimate first-action solver loss. Sources,
Mouse Trace attachment and metrics remain unchanged. No common timeline, clamping,
index mapping, normalized progress, lockstep, synchronized three-board playback,
generic time/speed/progress authority or universal player/registry was introduced.
Slice 3 includes no Mouse Trace playback/transformation, autoplay, Qt timer,
interpolation or UI. See the [handoff](../CURRENT_HANDOFF.md#4-current-milestone)
for the accepted playback boundary.

Reported Slice 3 verification: **29 focused; 84 Slice 2B; 31 Slice 2A; 29 Slice 1;
139 existing player/Engine/Replay/Mouse Trace/fingerprint regressions; combined
reported verification: 312 passed**, zero failures/errors/skips. No full suite,
package or native GUI run for Slice 3.

**Slice 4 — Read-only comparison UI COMPLETE / ACCEPTED** by ChatGPT final
adjudication, including internal **4A — Read-only Comparison Result Viewer** and
**4B — Launcher + Main UI Integration / Lifecycle**, both **COMPLETE / ACCEPTED**.
4A/4B are parts of official Slice 4, not new roadmap milestones.

4A [`same_board_comparison_ui.py`](../../same_board_comparison_ui.py) consumes one
completed execution, owns one `SameBoardPlayback` and no worker/job/process/timer.
One public-observation-only board, three-run selector, independent remembered
indices and manual First / Previous / Next / Last / selected-run slider preserve
current status versus final outcome. Factual summary/first-open qualification
does not imply controlled conditions. The optional full immutable Human Mouse
Trace is Human-only and independent of index. No autoplay/time coordination.
Metrics stay separate: Human Replay elapsed seconds; Stage-2 and Stage-3 Model C
cost through termination µs; Stage-2 and Stage-3 decision compute ns. No generic
time/speed winner, ranking or ratio; the Stage-3 Visualizer remains separate.

4B [`same_board_comparison_launcher.py`](../../same_board_comparison_launcher.py)
captures one admitted context from either a completed Live game or the entire
retained original Replay, regardless of displayed index, using existing sources.
**Compare as full-game Human Replay…** declares caller intent, not provenance;
Human metadata remains mandatory. No new loader. Later main source changes cannot
retarget the launcher; **Open Comparison…** only raises the existing owner.
It owns one unchanged job and retained result/viewer; Run requires no active token
and an idle job, and normal Run/Cancel do not wait. Solver LOSS is a valid result;
viewer reopen does not rerun execution. Shutdown permanently disables execution,
retains ownership on failure and supports close retry. Job shutdown precedes
viewer close; main close orders Comparison before Stage-3 before remaining
teardown, stopping on Comparison close failure.

Independent Claude Code read-only audit: **BLOCKER 0 / REQUIRED 0 / OPTIONAL 4 /
PASS**; Claude did not execute/rerun tests. ChatGPT independently reviewed
source/tests and accepted without production correction. Optional O-1–O-4 remain
deferred/evidence-triggered or optional Slice 5 work, not blockers; see the
[handoff acceptance record](../CURRENT_HANDOFF.md#4-current-milestone) for dispositions.

Reported Slice 4 verification: **55 new 4B (31 launcher / 24 main UI); 32 4A;
29 Slice 3; 84 Slice 2B; 31 Slice 2A; 29 Slice 1; 370 relevant existing regressions;
combined reported verification: 630 passed**, zero failures/errors/skips.
No full suite, fresh package or native GUI acceptance for Slice 4 is claimed.

**NEXT — Slice 5: Acceptance and closeout.** Not begun. Comparison remains ACTIVE,
not closed. Remaining gates are full source/frozen-boundary regression, fresh
Windows package and packaged worker verification, native/manual UI and real
Run/Cancel/reopen/close ownership, compatibility/frozen-evidence preservation and
final documentation/housekeeping. Feature → main merge/push follows final
acceptance only; see [handoff next action](../CURRENT_HANDOFF.md#6-next-action).
Frozen Stage-3 V1 / Model C remain unchanged. Timeline Analytics and Extended
algorithm research remain deferred and unauthorized. This milestone does not
establish a general Human-versus-solver speed winner.

Earlier closeouts retain their dated next-milestone statements as historical
records; the roadmap above and [current handoff](../CURRENT_HANDOFF.md) describe
the current state.

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

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`. The viewer never supplies solver
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
