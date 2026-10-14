# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Recover the current project state safely when a chat is restarted or reaches its maximum length.  
> Updated: 2026-10-14 (Asia/Seoul)

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

Live Git verified on 2026-10-14, before this documentation refresh:

- branch: `main`
- HEAD = local `origin/main`: `b9af830495ce97552f2058ef91b59a4fd495222b`
- latest commit: `feat: integrate stage3 visualizer execution lifecycle`
- inside work tree: true; bare: false; Slices 1–3 verified ancestors of main
- acceptance work branch: `feature/stage3-visualizer-acceptance` (created after checks)
- working tree: clean before the documentation edits

This is a dated snapshot of live Git, not a permanent HEAD pin. Recheck branch,
HEAD, `origin/main` and working-tree status when recovering a later chat.
The integrated Slice 4 commit is the latest local `main` / `origin/main` baseline;
Slices 1–4 are accepted, merged and pushed per the supplied closeout state and
verified local refs. No remote fetch was performed. Slice 5 documentation changes
remain uncommitted for review; no commit, merge or push was performed.

Live Slice identities:

- Slice 1: `cf7544b6dbc059594750f0798eca8878ddf2ea66`
- Slice 2: `d100a493445c7118b5347fdbe2ec0f7243719f17`
- Slice 3: `490a8cf3df1939ae9930e0735665e77120912995`
- Slice 4: `b9af830495ce97552f2058ef91b59a4fd495222b`

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
come from historical completion records. Slice 5's new source/package results
are recorded separately below and do not relabel historical smoke as newly run.
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

**Active milestone: Stage-3 Extended.** Stage-3 V1 remains **CLOSED / FROZEN**;
ZiNi Improvement and the listed maintenance milestones remain **CLOSED**.

**Execution / Playback / Visualizer Foundation — ACCEPTANCE PASS / READY FOR REVIEW.**
Execution integration audit and Slices 1–4 are closed/integrated. The project user
completed packaged manual acceptance on **2026-10-14 (Asia/Seoul)** after the
automated checks. **This foundation and Slice 5 acceptance are CLOSED**;
documentation remains uncommitted for review. Stage-3 Extended as a whole remains active.

Implemented components: indexed `Stage3Execution`, Qt-independent subprocess
worker, parent-owned `Stage3ExecutionJob`, `Stage3VisualizerLauncherWindow`,
pure `Stage3TracePlayer`, and read-only `Stage3VisualizerWindow`. Main UI owns
only the launcher; launcher owns job/viewer. This is independent of Live/Replay.

New executable evidence on 2026-10-14:

- Development full suite: **1628 passed, 0 failures/errors/skips**, 103.709 s.
- Explicit Extended: **122 passed**; frozen Stage-3 protection: **92 passed**.
- Fresh Windows x64 Python 3.12.10 / PyInstaller 6.22.3 onedir/windowed build: PASS.
- Frozen profile byte/SHA identity, packaged Stage-3 game 0 and deterministic
  source equivalence: PASS; **WON / 227 traces / 39,987,084 modeled µs**.
- Packaged ZiNi known-board regression and native GUI startup/liveness/clean close: PASS.
- Source-parent/real-frozen-worker success, cancel, launcher-close, main-close:
  owned children reaped and job directories removed. This is supplemental,
  not an automated packaged interactive GUI result.
- Fresh app build environment: 1628 discovered, **1603 passed / 25 optional
  image/video replay-validation skips**, 0 failures/errors, 90.505 s. Normal
  development verification above ran all 1628 without skips.

User-performed packaged manual acceptance on 2026-10-14: **PASS**. Main PID
5352; normal-success worker 8940, Cancel worker 6300, launcher-close worker 5124,
main-close worker 19188. Each reported WorkerGone=True and JobDirGone=True; main
5352 also had MainGone=True on main close. Startup, launcher, Run, responsiveness,
auto-open, First/Next/Last, slider click/drag and seek stopping autoplay, Play/Pause,
interval editing and retained-result reopen all passed. Exact job paths and
manual tester/provenance are recorded separately from automated evidence below.

Acceptance evidence and deferred UX observations:
[Foundation acceptance](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md).
Only documentation changed; frozen production semantics and profile bytes did not.

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

Review the seven documentation-only Slice 5 changes. Automated and user-reported
packaged manual acceptance are complete; no manual gate remains. Preserve the
existing generated build/evidence outputs as the earlier automated snapshot.

The foundation is CLOSED and ready for review. **Version/settings identity
separation** remains the recommended next milestone; no next implementation is
authorized here. Deferred, nonblocking UX observations include clearer Run/new
execution versus 결과 열기/retained-result labels, smooth synthetic cursor motion,
and Modeled-Time Playback. A future cursor path must remain explicitly synthetic/
interpolated, never an actual OS mouse trajectory. Final WON with Step 0/current
PLAYING, the intentional 20–5000 ms presentation range, and manual seek stopping
autoplay are accepted behavior. Incremental-forward player optimization waits for
modeled-time/smooth-animation requirements or measured lag; it is not implemented.

No selector, new algorithm or next milestone implementation belongs in Slice 5.
No commit/merge/push is authorized by this closeout. Do not reopen ZiNi work or
consume its reserved final quality holdout.

---

## 7. Stage-3 Extended roadmap and boundaries

Stage-3 Extended is the **active milestone**, separate from frozen V1.

Natural dependency roadmap — not a rigid chronological schedule:

1. **Closed:** execution integration audit and Slices 1–4 implementation.
2. **Closed / ready for review:** Slice 5 automated and packaged manual acceptance;
   only the Execution / Playback / Visualizer Foundation is closed. Current action
   is review of the uncommitted documentation.
3. **Next after review — version/settings identity separation:**
   application version, Stage-3 algorithm version, physical model/profile
   version, and playback/display settings.
4. **Same-board Human / Stage2 / Stage3 comparison.**
5. **Representative-board demonstrations and Timeline Analytics where useful.**
6. **First Stage-3 Extended algorithm extension.** The current likely first
   candidate is nearest exact-minimum-risk guess selection using physical movement cost
   among exactly equal minimum-risk candidates; it is not yet an accepted algorithm change.

This is a dependency roadmap, NOT a rigid chronological schedule. If
implementation evidence makes an adjacent task more natural earlier, the order
may change without changing milestone boundaries.

The following remain **DEFERRED / evidence-triggered** candidates, not mandatory work:

- logical-known-mine / no-flag execution
- action-specific OPEN / FLAG / CHORD timing
- anisotropic movement
- CPS / burst constraints
- richer / longer planning

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
the Extended README distinguishes the closed foundation, review-ready
documentation and later planning. Arbitrary Stage-3 seeks still rebuild from
index 0; Slice 5 does not optimize playback.

---

## 8. Documentation map

Start from:

- `docs/README.md`
- `docs/stage3-v1/README.md`
- `docs/stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md`
- `docs/stage3-extended/README.md`
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

Use this dated starting point, then reconcile it with live Git and source.

```text
이 채팅은 Minesweeper 졸업프로젝트 작업을 이어가는 새 채팅입니다.
저장소: C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project
Python: C:\venvs\minesweeper\Scripts\python.exe

먼저 live Git의 branch / HEAD / origin/main / working tree를 확인하고
docs/CURRENT_HANDOFF.md, docs/README.md 및 최신 source/tests를 읽으세요.
기억보다 source → tests → 실행 검증 → frozen specs/final adjudication
→ current docs → 이전 AI summaries를 우선하세요. Git을 오래된 prose에 맞춰 되돌리지 마세요.

2026-10-14 Slice 5 기준 main = origin/main =
b9af830495ce97552f2058ef91b59a4fd495222b (Slice 4 통합).
feature/stage3-visualizer-acceptance에는 review 대기 중인 미커밋 문서 변경이 있습니다.
Stage-3 V1 CLOSED/FROZEN, ZiNi Improvement CLOSED/V1 RETAINED.
Stage-3 Extended active; integration audit와 Slices 1–4는 CLOSED/integrated.
Execution / Playback / Visualizer Foundation은 CLOSED / ACCEPTANCE PASS / READY FOR REVIEW.
2026-10-14 사용자가 packaged manual acceptance를 완료했으며 문서 review만 남았습니다.
Stage-3 Extended 전체를 CLOSED로 기록하지 마세요.

Development full suite: 1628 PASS, failures/errors/skips 0.
Actual package: profile SHA, game 0 worker (WON, 227 traces, 39,987,084 µs),
source equivalence, ZiNi worker, native GUI startup/clean close PASS.
사용자의 packaged manual interaction/cleanup도 PASS입니다 (main PID 5352;
workers 8940/6300/5124/19188; 모든 WorkerGone/JobDirGone 및 main-close MainGone=True).
다음은 docs/stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md를 포함한
문서 review입니다. 기존 generated evidence는 갱신하지 않았습니다.
이후 version/settings identity 분리가 next 후보이며 UX 관찰은 비차단 후속 작업으로 보류합니다.

Main UI → launcher → parent-owned job/subprocess → Stage3Execution → player/viewer.
현재 Live/Replay 보드와 독립적이며 viewer는 solver 입력이 아닙니다.
Replay != Stage-3 Trace Playback != ZiNi Trace.
Presentation interval != Model C time; arbitrary seek는 index 0부터 재구성합니다.
Frozen source/profile과 Stage-2/Replay/ZiNi semantics를 유지하고 새 알고리즘은 구현하지 마세요.
사용자 review 전 commit/merge/push하지 마세요. 미개봉 ZiNi holdout도 유지하세요.

최신 Git/source가 더 진행됐다면 날짜가 찍힌 이 문서보다 live evidence를 우선하세요.
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
