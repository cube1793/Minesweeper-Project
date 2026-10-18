# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Durable recovery state for a new chat or context-loss event.
> Updated: 2026-10-18 (Asia/Seoul)

---

## 1. Authority / evidence order

When current state or implementation facts are disputed:

1. current Git source
2. current tests
3. executable verification
4. frozen specifications / final adjudications / current closeouts / this handoff
5. README / ARCHITECTURE / documentation index
6. prior AI interpretation or memory

Agreement between AIs is not proof.

The user performs Git manually. Do not claim an edit was staged/committed/pushed unless
the user reports it or live Git proves it.

---

## 2. Repository / environment

Repository:

`C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project`

Approved Python:

`C:\venvs\minesweeper\Scripts\python.exe`

The user completed the Viewer documentation closeout commit/push after the technical
qualification. The exact later documentation-only HEAD SHA is intentionally not guessed
here; live Git is authoritative at recovery time.

Qualified technical source identities below remain fixed even if HEAD later advances by
documentation-only commits.

---

## 3. Closed baselines

### Stage 1
- playable PyQt5 UI/UX
- Replay save/load/current-game replay
- Index/Time replay controls and speed control
- board analysis / 3BV / Ops
- ZiNi / Explorer foundations

### Stage 2
- Simple Algorithm
- exact probability fallback
- runner / Replay instrumentation

### Pre-Stage3
- deterministic benchmark-board infrastructure
- telemetry model/schema/repository/statistics
- official 100,000-game Stage-2 baseline
- architecture / engineering audit

### Stage-3 V1 — CLOSED / FROZEN

Qualified implementation / official 100k source:

`611984133b83be11bcd2105f401ecdddcfd68a15`

Official corpus:

`EXPERT_GENERAL_V1`, exact `[0,100000)`, first click `(0,0)`

Accepted final result under frozen Model C:

- WW/WL/LW/LL = `37702 / 0 / 0 / 62298`
- Stage-2 WW modeled total = `2,069,761,852,010 us`
- Stage-3 WW modeled total = `1,446,988,223,039 us`
- reduction ≈ `30.089144234937%`

This is a frozen modeled-physical-time result, not a 30% claim about human play or CPU time.

Official identities:

- Stage-2 DB: `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f`
- Stage-3 DB: `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e`
- Model C profile: `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`
- Model C timing table: `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b`

Do not reopen V1 merely because Extended work proposes cleaner behavior.

### ZiNi Improvement — CLOSED / V1 RETAINED

The advanced search work is closed as recorded in `docs/zini-improvement/`.
The final quality holdout `2,010,000 .. 2,010,099` remains unopened.

---

## 4. Stage-3 Extended milestone map

Stage-3 Extended remains **ACTIVE**.

Closed:

1. Execution / Playback / Visualizer Foundation
2. Version / Settings Identity Separation
3. Modeled-Time Playback / Synthetic Smooth Cursor Presentation
4. Human Mouse Trace / Path Visualization
5. Same-board Human / Stage-2 / Stage-3 Comparison
6. Representative-board Demonstrations / Timeline Analytics
7. Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer

Useful accepted identities:

- Human Mouse Trace qualified SHA:
  `e32145fa5c114e1ce500ad2e837ef6000cc49cca`
- Same-board Comparison qualified source/package SHA:
  `a59d0d963bdf1544a03968163b884342e2797ee0`
- Timeline Analytics qualified implementation SHA:
  `4c488e033dd045f1c203ff500d824cfaffb7cc67`
- Viewer final qualified source:
  `ff6358ae62b6f343bda36069d7164bda9aebee74`

Historical acceptance identities remain historical even if later maintenance changes the branch.

---

## 5. Selected Exemplar Viewer — FINAL ACCEPTANCE PASS / CLOSED

Final status:

**FINAL ACCEPTANCE PASS — SELECTED EXEMPLAR BOARD-STATE RECONSTRUCTION / HUMAN INTERPRETATION VIEWER CLOSED**

**Slices 0–4 COMPLETE / ACCEPTED — BLOCKER 0 / REQUIRED 0**

Qualified source:

`ff6358ae62b6f343bda36069d7164bda9aebee74`
— `test: preserve frozen E/L pilot source provenance`

Production usability source:

`29af53b15d1fff144df5873b62fcec4af91adaaa`
— `feat: improve exemplar viewer inspection usability`

`ff6358a` changed only the reviewed experimental E/L provenance/test boundary after
the production usability commit; Viewer/application production bytes remained those
accepted by the user in native source-GUI testing.

Evidence lineage:

- historical pre-usability `1f90bec...` acceptance: superseded
- first final qualification at `29af53b`:
  `results/stage3-exemplar-board-viewer-final-acceptance/20261018T091846923796Z/`
  → permanent HOLD
- E/L repair:
  `results/stage3-e-l-source-compatibility-repair/20261018T093614465991Z/`
- final fresh PASS:
  `results/stage3-exemplar-board-viewer-final-acceptance/20261018T094900066913Z/`

Final qualification:

- focused `892 / 892 PASS`
- full `2390 / 2390 PASS`
- zero failures/errors/skips in development suite
- exact accepted real proof: 4 boards / 8 streams / 1508 actions
- fingerprint/order/type/target/status/safe-reveal/explicit-FLAG/terminal/result mismatch = 0
- two immutable/read-only SQLite opens
- package/build gate PASS
- packaged EXE SHA-256:
  `8f64ca07d6b86cb03839e3b6f7f86b4b1510adabc901292a921f1a8c872d7530`
- user native source-GUI acceptance on production tree `29af53b`: PASS

Closeout:

`docs/stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md`

Fixed exemplars:

- `73758` — maximum Stage-3 WW modeled advantage
- `73024` — lower-median WW delta exemplar
- `93557` — closest-to-zero Stage-3 WW advantage
- `1` — LL control

They are deterministic category exemplars, not a statistically representative sample.

---

## 6. Current milestone — Visualization Usability Polish

**NEXT REQUIRED before algorithm research.**

This is maintenance on already-closed visualization surfaces; it does not invalidate
their historical acceptance.

### 6.1 Same-board Comparison — do first

**Same-board usability ACCEPTED; Stage-3 Visualizer reference overlays ACCEPTED.**
**BLOCKER 0 / REQUIRED 0. ChatGPT final review PASS (2026-10-18).**
- playback applies to selected run only
- Human timing modes:
  - `Index`
  - actual `Replay Time`
- Stage 2 / Stage 3 timing modes:
  - `Index`
  - `Model C Time`
- time speed `0.25x .. 8x`
- Index interval `20 .. 5000 ms`
- default `200 ms`
- minimum display `Max (20 ms)`
- typed below-min value clamps to 20 on commit
- cumulative completed action-target route
- same accepted smooth synthetic action-target cursor as Viewer/Stage-3 Visualizer
- actual Human Mouse Trace remains separate from route/synthetic cursor
- selected target / route / synthetic cursor / actual Human trace must remain distinct
- no solver/result recomputation; read-only
- no common synchronized Human/S2/S3 clock or playhead

Human Replay elapsed and solver Model C are different time authorities.

Historical Same-board UI used a plain `QSlider` whose distant track click followed Qt
page-step behavior. Fix that exact usability issue; do not mistake Stage-3 Visualizer,
which already has direct seek, as having the same bug.

Prefer the smallest UI-side timing extension. Historical `SameBoardPlayback` deliberately
owned index navigation rather than a generic cross-run clock. Do not introduce a general
synchronized playback framework unless current source evidence makes it necessary.

### 6.2 Accepted smooth-cursor semantics

Use the accepted Viewer / Stage-3 Visualizer semantics:

- presentation refresh request around 16 ms
- refresh cadence is not semantic timing authority and not guaranteed FPS
- straight geometry between rendered cell centers
- smoothstep `q = u²(3 - 2u)`
- same-cell actions remain stationary
- action/board commit only at authoritative action boundary
- partial progress updates overlay/presentation only
- pause/resume preserves partial progress
- manual navigation may cancel/align partial presentation to committed state
- late ticks may catch up multiple completed actions once
- synthetic presentation only, not recorded mouse motion / OS trajectory / calibrated acceleration
- easing and presentation rate never change Model C or planner decisions

Do not claim Minesweeper Online motion physics were copied. Only a similar smooth replay feel
was the user-facing visual target.

### 6.3 Stage-3 Visualizer — after Same-board

Required:

- cumulative recorded action-target route through current completed step
- future targets hidden by default
- preserve existing direct slider seek
- preserve selected-segment / synthetic-cursor distinction
- do not reopen its accepted timing/Model C semantics

Do NOT state that Stage-3 Visualizer lacks direct seek.

---

## 7. After visualization polish

Order is fixed:

1. finish Same-board polish
2. finish Stage-3 Visualizer route polish
3. perform human/domain interpretation of the fixed exemplars
4. decide/spec actual Extended algorithm-research direction
5. only then implement research if explicitly authorized

No Extended algorithm policy is currently adopted.

`Nearest exact-minimum-risk guess using movement cost` remains a candidate/backlog idea,
not an accepted next algorithm.

---

## 8. Authority boundaries

Keep separate:

- application/release identity
- algorithm identity
- physical Model C identity
- presentation settings

Also keep separate:

- Replay
- Human Mouse Trace
- Stage-3 solver trace/playback
- ZiNi Trace

Time authorities:

- Human Replay elapsed seconds
- Stage-2 Model C microseconds
- Stage-3 Model C microseconds
- decision-compute nanoseconds
- UI presentation wall time

Do not collapse them into one generic speed clock.

Human Mouse Trace is actual sampled pointer data. Synthetic solver cursor/route is not.

ZiNi is a click-efficiency reference, not the Stage-3 speed objective.

---

## 9. Engineering principles / roles

Continue:

- SRP / Separation of Concerns
- maintainability
- extensibility
- testability
- backward compatibility
- KISS / YAGNI
- evidence before optimization
- minimum necessary abstraction

If something looks unnecessary, do not remove it immediately. First explain:

1. why it may be unnecessary
2. what would be lost
3. `KEEP / DEFER / REMOVE`

Roles:

- ChatGPT: design / review / final adjudication
- Codex: implementation / execution / verification
- Claude Code: independent read-only audit only when a high-risk milestone warrants it
- User: Git staging / commit / push / merge

Disputed findings return to source/tests/evidence.

---

## 10. New-chat recovery sequence

At a new chat:

1. inspect live Git branch / HEAD / origin tracking / worktree
2. read `docs/CURRENT_HANDOFF.md`
3. read `docs/README.md`
4. read Viewer closeout only as the just-closed milestone boundary
5. read current Same-board source/tests before proposing implementation
6. summarize current state and exact next slice
7. do not rerun closed Viewer qualification merely to begin Same-board maintenance

Recommended immediate source set:

- `same_board_comparison_ui.py`
- `same_board_playback.py`
- `same_board_comparison.py`
- `same_board_comparison_launcher.py`
- `tests/test_same_board_comparison_ui.py`
- `tests/test_same_board_playback.py`
- related Replay/Mouse Trace/Model C tests only as needed

---

## 11. Handoff maintenance rule

Update this handoff only at meaningful boundaries:

- milestone closeout
- branch/baseline transition
- major design freeze
- accepted strategy/version
- materially changed next action

Do not turn this file into a complete chronological audit log. Detailed historical facts
belong in their closeout/contract/evidence records.
