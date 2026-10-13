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
4. frozen specifications / final adjudications / handoff documents
5. README / ARCHITECTURE / documentation index
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
- HEAD = local `origin/main`: `3622eed852c4e6808269b1b7815fc462359f65d7`
- latest commit: `feat: add zini explorer answer display`
- working tree: clean before the documentation edits

This is a dated snapshot of live Git, not a permanent HEAD pin. Recheck branch,
HEAD, `origin/main` and working-tree status when recovering a later chat.
The accepted closeout reports record the recent UI work as committed, merged
and pushed to `main`; the corresponding commits are present in local
`main` and `origin/main`. No remote fetch was performed for this refresh.

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
come from the supplied completion records; this documentation-only refresh did
not rerun tests or desktop smoke. Commit identities were read from live Git.

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

**Active milestone: Stage-3 Extended.**

**Immediate task: Stage-3 execution integration audit (read-only).**

Stage-3 V1, ZiNi Improvement, ASCII path migration, mouse-release input semantics,
Usability Batch 1 and ZiNi Explorer Answer Display are all **CLOSED**.

The existing `run_stage3()`, `Stage3ActionTrace` and `Stage3RunResult` belong
to accepted V1 execution. Current `main.py` / `ui_manager.py` do not connect
them to a Stage-3 execution UI or Visualizer. No Stage-3 Extended production
implementation has been accepted at the verified HEAD.

The present audit determines the minimal integration boundary; it is not
authorization to change production code or frozen V1 behavior.

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
**Replay != ZiNi Trace**; similar controls do not justify merging their models.

---

## 6. Next action

Continue the **read-only Stage-3 execution integration audit** against current
source/tests. Determine the smallest boundary connecting:

`run_stage3()`
→ `Stage3ActionTrace / Stage3RunResult`
→ one-game Stage-3 execution
→ step-based board playback / Visualizer
→ OPEN / FLAG / CHORD and cursor position / movement visualization
→ First / Previous / Play-Pause / Next / Last.

Inspect these existing seams first:

- `stage3_runner.py`: synchronous canonical all-HIDDEN run, initial cursor and
  OPEN at `(0,0)`, frozen board/profile limits, one executed action per trace,
  and observer callback. Preserve replan-after-action and public-evidence rules.
- `Stage3ActionTrace` already carries the move, cursor before the action,
  modeled action cost, decision timing and effect/status data.
  `Stage3RunResult` retains the ordered traces and modeled total; it does not
  contain a board snapshot or a ready-made board player.
- `core_engine.py`, `board_snapshot.py`, `benchmark_board.py`: determine
  board identity/capture and state reconstruction for one completed execution.
  Answer-layout data used for reconstruction must not become planner evidence.
- Stage-2 and Replay modules: inspect execution/recording/playback boundaries
  without weakening their contracts. ZiNi Explorer/Trace is a temporary
  reference for controls and rendering, not a shared execution data model.

The audit should select the playback model/controller boundary: reuse/adapt
existing Replay concepts or use a dedicated Stage-3 playback model. Neither
option is decided yet. Identify UI ownership/lifecycle boundaries and focused
verification needs before proposing implementation. Do not rerun planning merely
to seek through an already recorded run.

Do not reopen closed mouse/usability/ZiNi work or consume the reserved ZiNi
final quality holdout.

---

## 7. Stage-3 Extended roadmap and boundaries

Stage-3 Extended is the **active milestone**, separate from frozen V1.

Natural dependency roadmap — not a rigid chronological schedule:

1. **Current:** read-only execution integration audit.
2. **Execution / playback / Visualizer foundation:** one-game Stage-3 execution
   reusing `run_stage3 / Stage3ActionTrace`, the playback boundary selected by
   the audit, board step playback, OPEN / FLAG / CHORD, cursor position/movement,
   and First / Previous / Play-Pause / Next / Last.
3. **Version/settings identity separation as concrete UI requirements emerge:**
   application version, Stage-3 algorithm version, physical model/profile
   version, and playback/display settings.
4. **Same-board Human / Stage2 / Stage3 comparison.**
5. **Representative-board demonstrations and Timeline Analytics where useful.**
6. **First Stage-3 Extended algorithm extension.** The current likely first
   candidate is nearest equal-risk guess selection using physical movement cost
   among equal minimum-risk candidates; it is not yet an accepted algorithm change.

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
the existing Extended README/backlog remains planning context, not proof of
accepted production implementation.

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
이 채팅은 ChatGPT Project `졸업프로젝트`의
Minesweeper 졸업프로젝트 작업을 이어가는 새 채팅입니다.

저장소: C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project
Python: C:\venvs\minesweeper\Scripts\python.exe

기억이나 과거 AI 답변으로 현재 상태를 추정하지 마세요.
먼저 live Git의 branch / HEAD / origin/main / working tree를 확인하고,
docs/CURRENT_HANDOFF.md, docs/README.md와 관련 최신 source/tests를 읽으세요.
Project 첨부 파일은 현재 저장소와 일치하는지 확인해야 합니다.

증거 우선순위:
현재 Git source → tests → 실행 가능한 검증 결과
→ frozen specification / final adjudication / handoff
→ README / ARCHITECTURE / index → 과거 AI 해석과 기억.

2026-10-14 복원 기준:
- Stage-3 V1, ZiNi Improvement, ASCII path migration,
  Mouse-release input semantics, Usability Batch 1,
  ZiNi Explorer Answer Display는 CLOSED입니다.
- 현재 active milestone = Stage-3 Extended.
- 즉시 작업 = Stage-3 execution integration audit (read-only).
- 검증 당시 main HEAD = origin/main =
  3622eed852c4e6808269b1b7815fc462359f65d7이며 문서 갱신 전 작업 트리는 clean.
- 최신 accepted full unittest는 1506/1506 PASS,
  failures/errors/skips 0, desktop smoke PASS입니다. 새 실행 결과로 오인하지 마세요.
- 이 시점에 수용된 Stage-3 Extended production 구현은 없습니다.

첫 Visualizer 목표:
기존 run_stage3() → Stage3ActionTrace / Stage3RunResult를 재사용하는
한 게임 실행 → step-based 보드 재생 → OPEN / FLAG / CHORD,
커서 위치·이동 표시 → First / Previous / Play-Pause / Next / Last.
먼저 source를 읽고 최소 통합 경계를 정리하세요.

Stage-3 V1은 frozen이며 UI 편의를 위해 semantics를 바꾸지 마세요.
Replay elapsed time != modeled physical time.
Playback/display settings != planner inputs.
Generic solver registry / EventBus / plugin framework는 도입하지 마세요.
Human vs Stage2 vs Stage3 비교, Timeline Analytics와 첫 Extended algorithm은 후순위입니다.
ZiNi V1 품질 정책과 미개봉 최종 holdout을 유지하며 연구를 재개하지 마세요.

SRP / Separation of Concerns, maintainability / extensibility / testability,
backward compatibility, KISS / YAGNI, evidence before optimization,
minimum necessary abstraction을 유지하세요.
제거 제안은 이유·잃는 것·KEEP / DEFER / REMOVE를 먼저 설명하세요.

역할: ChatGPT = 설계/review/최종 판정,
Codex = 구현/실행/검증, Claude Code = 필요 시 독립 read-only audit.

최신 Git/source가 더 진행됐다면 위 날짜의 상태보다 최신 증거를 우선하세요.
처음에는 복원 상태, 현재 milestone, 직전 완료, 다음 한 단계,
남은 불확실성을 짧게 정리하고 이미 확인 가능한 내용은 다시 묻지 마세요.
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
