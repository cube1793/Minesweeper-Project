# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Durable recovery state for a new chat or context-loss event.
> Updated: 2026-10-19 (Asia/Seoul)

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

Last reported integrated Git state after Visualization Usability Polish closeout:

- branch: `main`
- HEAD / `origin/main`: `22e544a` — `docs: close visualization usability polish`
- working tree: clean at the reported closeout point
- obsolete closed feature branches were deleted locally/remotely

Always re-check live Git at recovery time; a later commit may legitimately advance `main`.
Documentation-only commits do not replace qualified technical source identities.

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
8. Visualization Usability Polish

Useful accepted identities:

- Human Mouse Trace qualified SHA:
  `e32145fa5c114e1ce500ad2e837ef6000cc49cca`
- Same-board Comparison qualified source/package SHA:
  `a59d0d963bdf1544a03968163b884342e2797ee0`
- Timeline Analytics qualified implementation SHA:
  `4c488e033dd045f1c203ff500d824cfaffb7cc67`
- Viewer final qualified source:
  `ff6358ae62b6f343bda36069d7164bda9aebee74`
- Visualization Usability Polish qualified implementation:
  `31630dd6ffa2301c41534fca3b003838d865f313`

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

## 6. Visualization Usability Polish — FINAL ACCEPTANCE PASS / CLOSED

Final status:

**Same-board Comparison usability ACCEPTED; Stage-3 Visualizer reference overlays ACCEPTED.**
**BLOCKER 0 / REQUIRED 0.**

Qualified implementation:

`31630dd6ffa2301c41534fca3b003838d865f313`
— `feat: add visualizer reference overlays`

Integrated documentation closeout on `main`:

`22e544a` — `docs: close visualization usability polish`

Qualification / acceptance summary:

- full source `2484 / 2484 PASS`, zero failures/errors/skips
- focused `453 / 453 PASS`, zero failures/errors/skips
- fresh Windows package build PASS; AMD64 / PE32+ GUI
- package EXE SHA-256:
  `26cfb55bbbe75bad29bb0461bf39eed6a2b3b203512b9144751dcd770530a08f`
- PROJECT USER source-GUI Same-board A–M: ALL PASS
- PROJECT USER source-GUI Visualizer V-A–V-I: ALL PASS
- packaged feature-native acceptance was not claimed

Closeout:

`docs/stage3-extended/STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md`

### 6.1 Accepted Same-board presentation boundary

- playback applies to selected run only
- Human timing modes: `Index` / actual `Replay Time`
- Stage 2 / Stage 3 timing modes: `Index` / `Model C Time`
- no shared synchronized Human/S2/S3 clock, playhead or normalized progress
- Index interval `20 .. 5000 ms`, default `200 ms`, minimum display `Max (20 ms)`
- Time speed uses exact quarter steps `0.25x .. 8x`
- direct logical-index track seek + native handle drag
- cumulative completed action-target route
- accepted smooth synthetic action-target cursor
- Human first synthetic anchor = first action target; no fabricated pre-first origin
- actual Human Mouse Trace remains the entire independent recording
- hidden-answer and action-target-route controls default OFF
- route contains committed targets only; pending/future targets are excluded
- selected target / route / synthetic cursor / actual Human trace remain distinct
- no solver/result recomputation from presentation-only updates

Human Replay elapsed and solver Model C remain different time authorities.

### 6.2 Accepted smooth-cursor semantics

- presentation refresh request around 16 ms; this is not semantic timing authority or guaranteed FPS
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

Do not claim Minesweeper Online motion physics were copied; only a similar smooth replay feel
was the user-facing visual target.

### 6.3 Accepted Stage-3 Visualizer presentation boundary

- existing direct slider seek and native handle drag preserved
- First / Previous / Next / Last and Index playback preserved
- existing Model C Time playback and modeled smooth cursor preserved
- six speeds remain `0.25x / 0.5x / 1x / 2x / 4x / 8x`
- NO Index smooth interpolation added
- hidden-answer and action-target-route controls default OFF
- route contains executed targets only through the committed step
- pending target is excluded until commit; planned/future suffix is never a route source
- selected segment / route / synthetic cursor remain distinct

---

## 7. Current NEXT — fixed-exemplar human/domain interpretation

This is the active Stage-3 Extended work unit. It is **interpretation, not implementation**.
Use the accepted Viewer / Timeline evidence to inspect the already-fixed Stage-2 and Stage-3
executions from the user's Minesweeper/domain perspective.

Fixed exemplars — **do not re-rank, re-select or visually substitute**:

- `73758` — maximum Stage-3 WW modeled advantage, delta `-27009085 us`
- `73024` — lower-median WW delta exemplar, delta `-16487355 us`
- `93557` — closest-to-zero Stage-3 WW advantage, delta `-7877513 us`
- `1` — LL control; termination cost only, not time-to-win

Accepted board references:

- `73758`: 3BV `172` / Ops `16` / isolated `156`
- `73024`: 3BV `177` / Ops `13` / isolated `164`
- `93557`: 3BV `140` / Ops `14` / isolated `126`
- `1`: 3BV `175` / Ops `12` / isolated `163`

These are deterministic category exemplars, **not a statistically representative sample**.

Authoritative Timeline report:

`results/stage3-timeline-analytics/20261017T113748060625Z-99dafa139703/report.html`

SHA-256:

`b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3`

Viewer final evidence root:

`results/stage3-exemplar-board-viewer-final-acceptance/20261018T094900066913Z/`

Interpret each exemplar by separating at least:

- observed Stage-2 behavior
- observed Stage-3 behavior
- action-count / route / modeled-time pattern
- routing / CHORD / FLAG / guess-location / repeated-movement factors that appear relevant
- the user's expert judgment of what feels strategically natural or unnatural
- confidence and the exact evidence supporting the interpretation
- any improvement idea only as a **candidate hypothesis**, never as adopted policy

Do NOT during this work unit:

- modify planner/solver policy
- adopt a new algorithm policy from one or a few exemplars
- infer causality from modeled-time difference alone
- treat Model C as human speed
- treat ZiNi as the Stage-3 speed objective
- fabricate Human Replay/mouse behavior where none exists
- call the action-target route a recorded OS cursor trajectory
- generalize the four exemplars into a statistically representative sample
- rerun the official 100k merely to start interpretation
- open the ZiNi final quality holdout `2,010,000 .. 2,010,099`

After interpretation:

1. synthesize recurring strengths, weaknesses and candidate hypotheses
2. make a separate Extended algorithm-research direction/specification decision
3. only after that decision and explicit authorization, implement research

No new Extended algorithm policy is currently adopted.
`Nearest exact-minimum-risk guess using movement cost` remains a candidate/backlog idea only.

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
2. read `docs/CURRENT_HANDOFF.md`, `docs/README.md` and `docs/stage3-extended/README.md`
3. read `STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md` as the just-closed boundary
4. read Viewer closeout + contract and Timeline closeout + contract before interpreting exemplars
5. confirm fixed IDs `73758 / 73024 / 93557 / 1`; do not reselect them
6. start with interpretation/evidence logging, not production edits
7. inspect exact source/tests only when a concrete interpretation or behavior question requires them
8. do not rerun closed Viewer/Polish qualification merely to begin interpretation
9. do not rerun official 100k or open the ZiNi final holdout without a new explicit protocol
10. after interpretation, stop for a separate research-direction/specification decision before algorithm work

Recommended immediate document/evidence set:

- `docs/stage3-extended/STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md`
- `docs/stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md`
- `docs/stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md`
- `docs/stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md`
- `docs/stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md`
- final accepted Timeline report and accepted Viewer evidence only as interpretation needs them

If a concrete technical meaning is disputed, then inspect the relevant current source/tests;
do not preload large source sets merely because they exist.

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
