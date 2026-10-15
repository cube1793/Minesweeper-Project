# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Recover the current project state safely when a chat is restarted or reaches its maximum length.  
> Updated: 2026-10-15 (Asia/Seoul)

---

## 1. Authority / evidence order

When current state or implementation facts are disputed, use this order:

1. current Git source code
2. current tests
3. executable verification
4. frozen Stage-3 V1 specifications / final adjudication
5. current tracked documentation, including handoff / README / ARCHITECTURE / index
6. prior ChatGPT / Codex / Claude interpretations or remembered summaries

Agreement between multiple AI reviews is not proof by itself.

---

## 2. Current stable baseline

Repository:

`C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project`

Approved development interpreter:

`C:\venvs\minesweeper\Scripts\python.exe`

Live Git verified on 2026-10-15 before Modeled-Time Playback closeout preparation:

- branch: `main`; clean, inside work tree, non-bare
- HEAD = local `origin/main`: `82c61d5447bf7cffc3c1d4fbcd392ef2945efa04`
- commit: `feat: add stage3 modeled-time visualizer playback`
- Slice 1: `b4ab1c8e9bbd9552d27daed884d97cf36d00aef6` — incremental TracePlayer
- Slice 2: `01d91b397cc285825cf7083c88724328bbe6c587` — pure modeled-time controller
- Slice 3: `82c61d5447bf7cffc3c1d4fbcd392ef2945efa04` — Visualizer / synthetic cursor

This is a dated preparation baseline, not a permanent latest-HEAD claim.
No fetch was performed. Closeout branch: `docs/stage3-modeled-playback-closeout`.
Documentation is awaiting user review; this preparation session has not staged,
committed, merged or pushed it. Determine later integration state from live Git.

Identity Separation closeout is integrated at
`9a2b721f5fa4786b4b513a20984f5667949e2a95`; its implementation identities remain in
the [Identity closeout](stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md).
Foundation final documentation is integrated at
`16ba355701744ec9827a73291546a656bed67980`; its historical Slice 1–5 identities
remain in the [Foundation record](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md).

Important Stage-3 V1 identities, verified in live Git:

- qualified implementation/evidence commit: `611984133b83be11bcd2105f401ecdddcfd68a15`
- V1 closeout/archive state before Extended workspace: `3e60c6bc41260c094a868841cd7df179d46ad6c1`
- Stage-3 V1 implementation branch was merged into `main` and its job is finished.

On 2026-10-13, the local top-level project root moved from
`C:\Users\User\Desktop\졸프` to `C:\Projects\GraduationProject`.
The internal directory structure was not intentionally changed. Historical
audit/evidence documents retain the paths that were true when produced.

If live Git disagrees with this section, trust live Git and update the handoff
rather than forcing Git back to these values.

---

## 3. Closed milestones

The following are closed baselines, not work-in-progress:

### Stage 1
- playable UI/UX
- Replay save/load/current-game replay
- Replay controls, Index/Time playback, speed controls
- board analysis / 3BV / Ops
- existing ZiNi functionality

### Stage 2
- Simple Algorithm
- exact probability fallback
- runner / replay instrumentation

### Pre-Stage3
- deterministic benchmark-board infrastructure
- telemetry model/schema/repository/statistics
- official 100,000-game Stage-2 baseline
- final architecture/engineering audit

### Stage 3 V1 — CLOSED
- frozen speed-focused algorithm and physical Model C
- telemetry / benchmark integration
- official 100,000-game Stage-3 run and G0–G5 validation
- independent Claude final audit and ChatGPT final adjudication
- closeout / evidence preservation / housekeeping / main merge / remote push

Final technical verdict:

`FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED`

Accepted official result under frozen Model C:

- corpus: `EXPERT_GENERAL_V1`, exact `[0,100000)`
- both-win games: `37,702`
- Stage-3 modeled time-to-win aggregate reduction vs Stage 2: about `30.089144%`
- this is a frozen modeled-time result, not a claim of 30% faster human play or CPU execution.

Do not reopen Stage-3 V1 merely because an Extended design looks cleaner.

### ZiNi Improvement — CLOSED (2026-10-13)

- TYPE S semantics-preserving optimizations accepted.
- Post-hoc Trace backend, transport/controller and ZiNi Explorer UI implemented.
- V2 quality research closed without adoption; **V1 RETAINED**.
- C3 fresh quality: **NO-SIGNAL**; C4 Family A: **NO-GO**.
- Final `EXPERT_GENERAL_V1` holdout, indices 2,010,000..2,010,099 (100 boards),
  remains unopened: not generated/fingerprinted/calculated/inspected for final
  quality adjudication. Development failed before authorization, so it was
  deliberately not consumed.

See [final adjudication](zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md).
The accepted closeout at `aa0b252aa7c1510b313b511729034e5e74062b5b`
recorded **1414/1414 tests PASS** and **final manual GUI smoke PASS**, then
merge/push to `main`.

### Recent maintenance / usability — CLOSED (2026-10-13)

These are concise accepted closeouts. Test counts and desktop smoke results below
come from historical completion records. Current Modeled-Time Playback acceptance
is recorded separately below and does not relabel historical smoke as newly run.
Commit identities were read from live Git.

- **ASCII path migration:** moved to the current ASCII root; **1414/1414 PASS**,
  **0 failures / 0 errors / 0 skips**, and post-migration normal-desktop smoke
  **PASS**, including Replay. Documentation closeout: `9a5f144`.
- **Mouse-release input semantics:** gameplay commits on release; held preview
  follows the cursor; same-origin BOTH is one CHORD gesture, while
  different-origin LEFT/RIGHT remain independent. Reset/rebuild/Replay
  transitions invalidate stale held input. Final automated verification and
  desktop smoke **PASS**; merged/pushed to `main` at `7b5ba45`.
- **Usability Batch 1:** persistent Replay default directory; Simple Auto
  interval **0..2000 ms**, default **180 ms**, **0 = "최대 속도"**; pending
  single-shot timer safely reschedules. Final full suite **1492/1492 PASS** and
  desktop smoke **PASS**; merged/pushed to `main` at `81c3d86`.
- **ZiNi Explorer Answer Display:** unopened-answer display defaults **ON**;
  safe numbers/mines appear faintly while cells remain covered, and **OFF**
  restores the old hidden representation. Revealed/unopened numbers share
  **Arial 14 Bold** typography/color; unopened answers use **35% opacity**.
  Slider track clicks seek directly to the clicked logical index; manual
  seeking stops autoplay. Trace/controller semantics are unchanged.
  Explorer UI **50/50 PASS**, related ZiNi/UI **422/422 PASS**, full unittest
  **1506/1506 PASS**, **0 failures / 0 errors / 0 skips**, desktop smoke **PASS**.
  Committed/pushed/merged to `main` at `3622eed`, with final Git state checked.

---

## 4. Current milestone

**Stage-3 Extended remains ACTIVE. Next active small milestone:
Human Mouse Trace / Path Visualization (not implemented).**
Same-board Human / Stage-2 / Stage-3 Comparison follows that milestone.
Stage-3 V1 / Model C remain CLOSED / FROZEN; ZiNi Improvement remains CLOSED.

- **Execution / Playback / Visualizer Foundation — CLOSED (2026-10-14)**:
  [historical acceptance](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)
  and [final adjudication](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md).
  Accepted process ownership/lifecycle is not reopened.
- **Version / Settings Identity Separation — CLOSED (2026-10-15)**:
  [closeout](stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md).
  Application/release, algorithm, physical model/profile and presentation remain distinct.
- **Modeled-Time Playback / Synthetic Smooth Cursor Presentation —
  FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**:
  [closeout](stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md).

Accepted ownership and presentation:

- TracePlayer owns committed integer state and exact cumulative µs. `next()` applies
  one action transactionally; arbitrary `go_to()`/`previous()` still rebuild from zero.
- The Qt-independent controller uses monotonic anchoring and exact Fraction partial
  time over opaque recorded durations; it owns pause/resume, speed and boundary catch-up.
- Index remains default, 20..5000 ms/step, default 200. Modeled-Time defaults to 1×,
  with 0.25× / 0.5× / 1× / 2× / 4× / 8× presentation rates and 16 ms Qt frame requests.
  The controller clock, not timer tick count, determines modeled elapsed time.
- Pending actions keep the pre-action board until their boundary. UI uses rendered
  cell centers and straight smoothstep `q = u²(3 - 2u)`, without a separate dwell model.
  Same-cell actions stay stationary. Partial frames update the overlay only;
  catch-up refreshes the resulting committed board once.
- Pause preserves partial progress; manual navigation or mode switching discards it.
  The slider stays integer-based. Reopen defaults are Index / 200 ms / modeled 1×,
  with no QSettings persistence. Synthetic motion is not an actual OS trajectory.

Final acceptance with development Python 3.12.10 / 64-bit:

- Focused: **254 passed**, **29.048 s**, **0 failures / 0 errors / 0 skips**.
- Full discovery: **1699 passed**, **130.978 s**, **0 failures / 0 errors / 0 skips**.
- Fresh Windows x64 onedir/windowed PyInstaller 6.22.3 build:
  **exit 0**, **83.6817627 s**, accepted absolute profile bundling.
- Source/bundled profile bytes identical; both SHA-256
  `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
- Packaged worker from unrelated cwd: exit 0, valid token/envelope, no error,
  **WON / 227 traces / 39,987,084 µs**; first action **126,005 µs**.
  Deterministic source equivalence excludes decision CPU timing/runtime/object identity.
- **Native packaged GUI PASS, project user, 2026-10-15: "A–K passed"**.
  This covers Index, modeled controls, same-cell timing, smooth straight movement,
  pause/resume, navigation, mode/rate changes, final total and close/reopen defaults.
  It is qualitative UX acceptance, not a measured FPS or physical-model claim.

New ignored package/evidence root:
`results/stage3-modeled-playback-acceptance/20261015-113435/`.
Exact commands, fingerprint, warning review and manual provenance are in the closeout.

`Stage3Execution(spec, board, result)`, worker pickle transport, benchmark
`solver_config_snapshot`, identities/profile/table, official 100k evidence, Replay,
ZiNi, database/schema and QSettings remain unchanged. Slice 4 changes documentation
only; no 100k rerun, new feature, release/version/tag/ZIP or physical-model redesign.

---

## 5. Accepted ZiNi boundaries

- **TYPE S:** implemented core optimizations preserve V1 semantics and are
  protected by reference and frozen golden tests. No speed ratio is claimed here.
- **TYPE Q:** V1 remains the production quality policy. V2 A/B/C policies,
  experimental G6/F-2/K0/N-setupOFF and lambda are not production settings.
  V2 research is closed; no Family A implementation or further lambda/search/
  semantics tuning is authorized by this milestone.
- **Trace / Explorer:** the post-hoc backend, result transport/controller and
  separate Explorer UI are implemented. Trace is built lazily on request from
  the final result, without rerunning search. It is not a full search-tree record.
  The later answer-display closeout changes presentation only.

Replay = playback of actually executed game actions.
ZiNi Trace = playback/explanation of answer-board-based ZiNi simulation choices.
**Replay != Stage-3 Trace Playback != ZiNi Trace**; similar controls do not justify merging their models.

---

## 6. Next action

Review/integrate this documentation closeout, then design **Human Mouse Trace /
Path Visualization (not implemented)**. This roadmap insertion was decided after
Modeled-Time closeout preparation and changes planning only; no Mouse Trace
implementation or new specification document is part of this closeout.
**Same-board Human / Stage-2 / Stage-3 Comparison** comes after Mouse Trace.
Use live Git/source/tests to determine whether later work has already begun.

Initial planned scope:

- Record actual mouse movement only while the cursor is over the Live game board.
- Store sampled pixel-space cursor points/timestamps separately from Replay.
- Retain actual action/click markers and visualize the recorded path over the board
  after game completion.
- No OS-global mouse hook or Stage-3 synthetic cursor reuse.
- No physical-model calibration/refit or advanced path analytics yet.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human Mouse Trace is planned actual sampled Live-board cursor presentation data,
not Stage-3 synthetic movement or Model-C calibration evidence.

Keep presentation separate from planner inputs, physical identity and recorded
costs. Retain Step 0/current PLAYING with known final WON, exact action-boundary
commits, integer navigation and non-persistent controls. Synthetic movement and
smoothstep easing do not measure physical mouse motion.

Foundation F-2 remains **OPTIONAL / DEFER**: packaged windowed transport exceptions
may show PyInstaller's uncaught-exception dialog rather than exit immediately.
There is no false success; existing Cancel/close ownership/reaping remains.
No new evidence promotes F-2 to required work.

Preserve historical and new acceptance artifacts. No release/tag/ZIP or commit/
push was performed in this preparation session. Do not reopen ZiNi work or consume
its unopened final quality holdout.

---

## 7. Stage-3 Extended roadmap and boundaries

Stage-3 Extended is the **active milestone**, separate from frozen V1.

Natural dependency roadmap — not a rigid chronological schedule:

1. **CLOSED:** Execution / Playback / Visualizer Foundation.
2. **CLOSED:** Version / Settings Identity Separation.
3. **CLOSED:** Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **NEXT:** Human Mouse Trace / Path Visualization (not implemented).
5. **NEXT AFTER THAT:** Same-board Human / Stage-2 / Stage-3 Comparison.
6. **LATER:** Representative demonstrations / Timeline Analytics.
7. **LATER:** First actual Extended algorithm research; nearest equal-minimum-risk
   guess selection using movement cost is a candidate, not an adopted policy.

This is a dependency roadmap, NOT a rigid chronological schedule. If
implementation evidence makes an adjacent task more natural earlier, the order
may change without changing milestone boundaries.

The following remain **DEFERRED / evidence-triggered** candidates, not mandatory work:

- arbitrary-seek checkpoint/cache optimization
- modeled-time slider / sub-action scrubbing
- 120-fps UI target, easing selector and click pulse
- persistent Stage-3 presentation settings; settings dataclass until an external consumer exists
- runtime application/release display or version constant
- selectable algorithms/profiles and durable cross-version Stage3Execution transport
- richer physical model / Model C successor or refit
- action-specific OPEN / FLAG / CHORD timing and physical CHORD variants
- CPS / burst / minimum inter-action constraints, anisotropy and human cognitive timing
- built-in screen recording unless later justified
- logical-known-mine / no-flag execution and richer / longer planning

Boundaries:

- Stage-3 V1 and frozen Model C remain frozen. Do not alter V1 semantics merely
  for UI convenience.
- Prefer existing runner/trace interfaces and minimum necessary abstraction.
  No generic solver registry, EventBus or plugin framework.
- **Replay elapsed time != modeled physical time**; decision compute time is
  separate as well. Display animation is not a new physical-time measurement.
- **Playback/display settings != planner inputs.** Playback speed must not
  change recorded actions, planner decisions or benchmark/model totals.
- Keep application version, algorithm version and physical model/profile
  identity separate. Future algorithm/profile changes require their own
  specifications and evaluation; the backlog does not authorize them now.

Built-in screen recording is not currently a priority; external tools can record
the visualization. New Extended documentation belongs in `docs/stage3-extended/`;
the Extended README distinguishes the finally adjudicated closed foundation,
the next active milestone and later planning. Arbitrary Stage-3 seeks still rebuild from
index 0; incremental forward is implemented, while arbitrary-seek caching is deferred.

---

## 8. Documentation map

Start from:

- `docs/README.md`
- `docs/stage3-v1/README.md`
- `docs/stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md`
- `docs/stage3-extended/README.md`
- [Modeled-Time Playback closeout](stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md)
- [Identity Separation closeout](stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md)
- [Foundation final adjudication](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)
- [Foundation acceptance evidence](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)
- `STAGE3_ALGORITHM_SPEC_v1.md`
- `STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md`
- `STAGE3_EXTENSION_BACKLOG.md`
- `docs/zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md`
- `README.md`, `ARCHITECTURE.md`, `BUILDING.md`

External recovery/source-panel companions verified on 2026-10-14:

- `C:\Users\User\Desktop\비상시 프롬프트.txt`
- `C:\Users\User\Downloads\PROJECT_SOURCE_REFRESH_PLAN.md`

Both exist **outside this repository**; they are not tracked repository files.
Do not invent repository locations for them or assume Project attachments
automatically match the local originals.

Existing historical documents and frozen/evidence paths remain in place for
provenance. Do not reorganize them merely for visual neatness.

---

## 9. Engineering principles

Continue to apply:

- Single Responsibility Principle
- Separation of Concerns
- maintainability
- extensibility
- testability
- backward compatibility
- DRY only where it removes meaningful duplication
- KISS
- YAGNI
- evidence before optimization
- minimum necessary abstraction

When something appears unnecessary, do not remove it immediately.

First state:

1. why it may be unnecessary
2. what would be lost by removing it
3. whether to `KEEP`, `DEFER`, or `REMOVE`

---

## 10. Working-role convention

For major milestones:

- ChatGPT: design / review / final adjudication
- Codex: implementation / execution / focused verification
- Claude Code: independent read-only audit when warranted

For disputed findings, return to source/tests rather than choosing an AI by reputation.

---

## 11. New-chat recovery prompt

Reconcile recorded milestone status with live Git/source/tests; do not force Git
to match dated prose.

```text
이 채팅은 Minesweeper 졸업프로젝트 작업을 이어가는 새 채팅입니다.
저장소: C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project
Python: C:\venvs\minesweeper\Scripts\python.exe

먼저 live Git의 branch / HEAD / origin/main / working tree를 확인하고
docs/CURRENT_HANDOFF.md, docs/README.md 및 최신 source/tests를 읽으세요.
source → tests → 실행 검증 → frozen specs/final adjudication → current docs
→ 이전 AI summaries 순서로 판단하세요. 날짜가 찍힌 SHA나 prose를 latest로
가정하지 말고 live evidence를 우선하세요.

마지막 기록 상태: Stage-3 V1 / Model C CLOSED/FROZEN, ZiNi Improvement CLOSED.
Execution / Playback / Visualizer Foundation CLOSED.
Version / Settings Identity Separation FINAL ACCEPTANCE PASS / CLOSED.
Modeled-Time Playback / Synthetic Smooth Cursor Presentation FINAL ACCEPTANCE PASS / CLOSED.
Stage-3 Extended 전체는 ACTIVE이며 다음 작은 마일스톤은
Human Mouse Trace / Path Visualization (아직 미구현)입니다.
그다음은 Same-board Human / Stage-2 / Stage-3 Comparison입니다.
Mouse Trace 초기 계획: Live 보드 위의 실제 이동만 pixel-space points/timestamps로
sample하여 실제 action/click markers와 함께 Replay와 별도로 보관하고, 게임 종료 후
보드 위에 경로를 표시합니다. OS-global hook, Stage-3 synthetic cursor 재사용,
physical-model calibration/refit, advanced path analytics는 초기 범위에서 제외합니다.
이번 closeout은 planning/docs만 수정하며 Mouse Trace를 구현하지 않습니다.
후속 기능이 이미 구현됐다고 가정하지 말고 현재 source/tests로 확인하세요.
Playback closeout: docs/stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md.

Application/release != algorithm != physical model/profile != presentation.
Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace.
Human Mouse Trace는 실제 sampled Live-board cursor presentation data의 계획이며,
Stage-3 synthetic movement나 Model-C calibration evidence가 아닙니다.
Presentation interval, Replay elapsed time, CPU decision time, modeled physical
time은 별개입니다. Stage3Execution은 spec / board / result이며 viewer는 solver 입력이 아닙니다.
Stage-3 설정 persistence와 registry는 없습니다.
Frozen specs/profile, official evidence와 미개봉 ZiNi holdout을 보존하세요.
F-2 packaged transport hardening은 OPTIONAL / DEFER입니다.
사용자 review 전 commit/merge/push하지 마세요.
현재 상태·남은 gate·다음 한 단계를 짧게 정리하고 이미 확인 가능한 내용은 다시 묻지 마세요.
```

---

## 12. Handoff maintenance rule

Update this file only at meaningful boundaries, for example:

- milestone completed
- branch/baseline changed
- major design decision frozen
- new strategy/version accepted
- current next action materially changed

Do not turn this file into a full changelog or duplicate every audit artifact.
