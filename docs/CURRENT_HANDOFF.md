# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Recover the current project state safely when a chat is restarted or reaches its maximum length.  
> Updated: 2026-10-17 (Asia/Seoul)

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

Historical Same-board acceptance baseline, verified on 2026-10-17:

- qualified development branch at acceptance: `feature/stage3-same-board-comparison`;
  clean tracked baseline, nothing staged at that verification
- at acceptance, HEAD matched local `origin/feature/stage3-same-board-comparison`:
  `a59d0d963bdf1544a03968163b884342e2797ee0`
- qualified source/package candidate: `test: fix replay statistics UI fixture`
- preceding accepted Slice-4 implementation/docs:
  `d81caa95fc0e181d199fdf4c770873241f0f1eac` — `feat: add same-board comparison UI`
- `a59d0d9` changes only `tests/test_replay_statistics.py`; no production behavior change

The qualified package/source SHA remains the historical acceptance identity.
Read live Git for current branch existence, latest HEAD, remote refs and merge
state; later Git integration does not replace the qualified candidate identity.
Earlier Extended implementation identities remain in their linked closeout records.

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
come from historical completion records. Current Human Mouse Trace acceptance
is recorded separately below and does not relabel historical smoke as newly run.
Commit identities were read from live Git.

- **ASCII path migration:** moved to the current ASCII root; **1414/1414 PASS**,
  **0 failures / 0 errors / 0 skips**, and post-migration normal-desktop smoke
  **PASS**, including Replay. Documentation closeout: `9a5f144`.
- **Historical mouse input work (`7b5ba45`):** accepted held preview and stale-input
  safeguards. Its physical gesture policy was superseded by the accepted
  [Physical Mouse Gesture Fidelity correction](../ARCHITECTURE.md#physical-mouse-input)
  at `e32145f`; use the current contract below.
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

**ACTIVE — Representative-board Demonstrations / Timeline Analytics. Slice 0 —
Contract COMPLETE / ACCEPTED by ChatGPT final review (2026-10-17, Asia/Seoul).**
ChatGPT adjudicated the read-only discovery **DISCOVERY PASS**. The accepted
[Timeline Analytics contract](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md)
records the scope and boundaries. **Implementation has NOT begun; no actual
exemplar game IDs have been selected.** **NEXT / now authorized implementation
scope — Slice 1: Pure timeline analytics.**

The first implementation is a read-only report from exact accepted official
Stage-2 / Stage-3 artifacts, with deterministically selected category exemplars
(not a statistically representative sample), independent completed-action-count
timelines and bounded static visualization. Human adapters and interactive GUI
are deferred. No algorithm, Model C, schema or telemetry changes are in scope.
Slice 1 — Pure timeline analytics is the now-authorized implementation scope,
but has NOT begun. No actual exemplar IDs may be selected in Slice 1; exemplar
selection remains in the accepted Slice 2/3 scope. The implementation feature
branch `feature/stage3-timeline-analytics` must exist and remain active **before
and during Slice-1 implementation**. Live Git remains authoritative for current
branch/HEAD state; do not infer a commit identity from this document.

### Closed Same-board baseline — preserved acceptance

**Stage-3 Extended remains ACTIVE. Same-board Human / Stage-2 / Stage-3 Comparison:
FINAL ACCEPTANCE PASS / CLOSED (2026-10-17, Asia/Seoul).** Slices 0–5 are
COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B. No Same-board
implementation work remains. See the
[final closeout](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md).
Stage-3 V1 / Model C remain CLOSED / FROZEN; ZiNi Improvement remains CLOSED.

**Slice 0 — contract documentation COMPLETE / ACCEPTED.** The
[comparison contract](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md)
has passed ChatGPT review.

**Slice 1 — Comparison domain and admission COMPLETE / ACCEPTED** by ChatGPT
final review. The pure Qt-independent foundation in
[`same_board_comparison.py`](../same_board_comparison.py) and its
[focused tests](../tests/test_same_board_comparison.py) preserve the original
Human Replay and separate Mouse Trace attachment as authorities. Admission
requires both `source_type == SOURCE_HUMAN` and explicit
`declared_full_game_human=True`. Neither Human metadata, caller declaration nor
successful reconstruction proves exclusively-Human historical provenance;
Human-labeled recordings may contain historical Auto input.

Layout identity uses exact layout equality and the existing canonical
fingerprint. Full-stream reconstruction rejects incomplete and post-terminal
streams. Opening qualification is factual, not proof of controlled experimental
conditions.

Reported Slice 1 verification: **29 focused passed; 202 relevant regression
passed; combined reported total: 231 passed**, zero failures/errors/skips.
No full suite, package or native GUI run was performed for Slice 1.

**Slice 2 — Isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT final review.
**Slice 2A — Pure isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT
final review. The pure Qt-independent layer in
[`same_board_runner.py`](../same_board_runner.py) uses separate fresh fixed-layout
Stage-2 and Stage-3 engines on the exact admitted Human layout. Stage 2 calls
unchanged `run_simple(..., accept_guesses=True, initial_open=(0,0), observer=...)`;
Stage 3 calls unchanged frozen `run_stage3()` with authenticated Model C.
Mined `(0,0)` immediate losses remain legitimate; no regeneration or retry occurs.
Native Stage-2 result/Replay/traces and native Stage-3 result/traces remain
authorities alongside the original Human Replay/Mouse Trace. The immutable
execution result/metric layer retains no live Engine or fabricated benchmark identity.

Accepted narrow seam: `benchmark_modeled_time.evaluate_ordered_actions()` reuses
existing authenticated Model C validation/cost logic for canonical ordered
complete inputs, including initial and terminal/losing input costs. It requires
no DB, GameRecord, seed, benchmark index or fabricated telemetry identity and
preserves existing evaluator callers. Stage-3 recorded modeled totals remain
authoritative and must exactly match independent evaluation through this seam.

Metric authorities remain separate: Human Replay elapsed seconds; Stage-2 Model C
microseconds; Stage-3 Model C microseconds; Stage-2 decision-compute nanoseconds;
Stage-3 decision-compute nanoseconds. No Human Model C time, generic speed field,
winner, ratio or Timeline Analytics is added. Frozen Stage-3 V1 / Model C are unchanged.

Reported Slice 2A verification: **31 new Slice 2A passed; 29 Slice 1 passed;
274 relevant regression passed; combined reported verification: 334 passed**,
zero failures/errors/skips. No full suite, package or native GUI run was performed
for Slice 2A.

**Slice 2B — Worker/process integration COMPLETE / ACCEPTED** by ChatGPT final review.
Slices 2A/2B are internal parts of the existing Slice 2, not new roadmap milestones.

The dedicated PyQt-independent [`same_board_execution_worker.py`](../same_board_execution_worker.py)
accepts exactly `{"token": request_token, "board": fixed_ReplayBoard}`. Human Replay
events and Mouse Trace never enter the worker; they remain parent-owned. The worker
executes the accepted solver-only fixed-layout Stage-2 + frozen Stage-3 path once.
Legitimate solver LOSS never triggers regeneration/retry; solver failures remain
failures, never fabricated LOSS. Source execution uses the module-relative worker
script; frozen execution uses `--same-board-execution-worker`, dispatched before
Qt GUI setup independently of the existing ZiNi and Stage-3 flags.

[`SameBoardExecutionJob`](../same_board_execution_job.py) owns one active child and
its private temporary directory. Normal poll/cancel process waits are nonblocking;
terminate -> kill escalation, reap before cleanup, cleanup before terminal success,
and retained ownership on reap/cleanup failure remain enforced. Stale/wrong-type
tokens are rejected. Parent composition attaches solver evidence to the exact
retained original Human context, preserving its Replay/Mouse Trace authorities.

Parent revalidation covers comparison/outcome-bearing facts: recomputed layout
identity, locally reauthenticated Model C, reconstructed/rechecked Stage-2 and
Stage-3 executed streams, terminal outcomes and model totals, relied-upon native
types, trace deltas and the Stage-3 cursor chain. It deliberately does **not**
recursively deep-walk the complete nested decision-evidence graph on every run.
Native decision/probability/plan evidence remains retained unchanged. Transport
is trusted-local/private; this is not a security guarantee for arbitrary pickles.

Independent Claude Code read-only audit: **BLOCKER 0; initially REQUIRED 1** —
avoidable parent-side recursive decision-evidence traversal affected responsiveness.
That REQUIRED finding was corrected and subsequently accepted by ChatGPT; no
independent Claude re-audit of the correction is claimed.

Representative genuine **30x16** evidence measured parent composition median
**681.4 ms before / 92.1 ms after**, after-change range **86.1–96.2 ms**;
separate after-change unpickle median **173.1 ms**. This demonstrates removal of
the avoidable deep-walk stall, **not zero GUI-thread blocking**. No arbitrary
runtime/FPS requirement is introduced; these are responsiveness observations,
not frozen algorithm-performance evidence.

Reported final Slice 2B verification: **84 Slice 2B passed; 31 Slice 2A passed;
29 Slice 1 passed; 374 relevant regressions passed; combined reported verification:
518 passed**, zero failures/errors/skips. No full suite, fresh package or native
GUI acceptance was run for Slice 2B.

**Slice 3 — Pure playback coordination COMPLETE / ACCEPTED** by ChatGPT final review.
The pure Qt-independent [`same_board_playback.py`](../same_board_playback.py)
coordinates exactly three run identities: `HUMAN`, `STAGE2`, `STAGE3`. Human uses
the original admitted Replay through existing `ReplayPlayer`; Stage 2 uses its
native algorithm Replay through another `ReplayPlayer`. Stage 3 uses a dedicated
Same-board fixed-layout trace player: arbitrary Human layouts must not fabricate
benchmark-specific `Stage3Execution` / `BenchmarkBoard` identity. It executes only
recorded `trace.move`; planner evidence and unexecuted plan suffixes are not
executable playback input. Playback invokes no solver/planner/worker and does not
reevaluate Model C.

Index 0 is the exact fixed all-HIDDEN initial board; index n is the state after
exactly the first n semantic inputs of that run. Each run retains its own index
and valid range. Switching restores the selected run's remembered index without
seeking or mutating another run. There is no clamping, index mapping or normalized
progress; equal numeric indices do not mean equivalent game progress.

Current reconstructed `status` is separate from recorded final outcome. A completed
WON/LOST run is still PLAYING at index 0. A legitimate solver first-action LOSS
is PLAYING at index 0 and LOST at index 1; Human outcome remains independently
authoritative.

Navigation does not mutate Human Replay, Mouse Trace, Stage-2 Replay/results/traces,
Stage-3 results/traces or metrics. Mouse Trace remains a separate attachment,
not played/transformed in Slice 3. No generic time/speed/progress authority,
common timeline, lockstep, synchronized three-board playback or universal
player/registry abstraction was introduced. No autoplay, Qt timer, interpolation
or UI was implemented.

Reported Slice 3 verification: **29 Slice 3 focused passed; 84 Slice 2B passed;
31 Slice 2A passed; 29 Slice 1 passed; 139 existing player/Engine/Replay/Mouse Trace/
fingerprint regressions passed; combined reported verification: 312 passed**,
zero failures/errors/skips. No full suite, package or native GUI run for Slice 3.

**Slice 4 — Read-only comparison UI COMPLETE / ACCEPTED** by ChatGPT final
adjudication, without production correction. Internal **4A — Read-only Comparison
Result Viewer** and **4B — Launcher + Main UI Integration / Lifecycle** are both
**COMPLETE / ACCEPTED**; they are subdivisions of official Slice 4, not new milestones.

The presentation-only [`same_board_comparison_ui.py`](../same_board_comparison_ui.py)
consumes one completed `SameBoardExecution` and owns one `SameBoardPlayback`, with
no worker/job/process/timer. One read-only board renderer uses only the selected
run's public observation. Human / Stage 2 / Stage 3 selection preserves independent
remembered indices; First / Previous / Next / Last and the selected-run action-index
slider are manual controls, with no autoplay or time coordination. The compact
three-run summary keeps current reconstructed status separate from final outcome;
first-open/layout qualification is factual, not controlled-experiment proof.
The optional full Human Mouse Trace uses the original immutable attachment, is
Human-only and independent of action index. The Stage-3 Visualizer stays separate.

Displayed authorities remain explicit: Human Replay elapsed seconds; Stage-2
Model C cost through termination µs; Stage-3 Model C cost through termination µs;
Stage-2 decision compute ns; Stage-3 decision compute ns. No Human Model C time
or generic time/speed winner, ranking or ratio is introduced.

[`same_board_comparison_launcher.py`](../same_board_comparison_launcher.py) and the
narrow `ui_manager.py` integration support both completed current Live games and
currently retained Replays through the existing recorder/Replay source path; no
Comparison-specific loader was added. Replay mode takes precedence and supplies
the entire original `ReplayData`, regardless of displayed index. Explicit Tools
action **Compare as full-game Human Replay…** declares
`declared_full_game_human=True`; `source_type == SOURCE_HUMAN` (`"human"`) remains mandatory. Neither
metadata, declaration nor reconstruction proves exclusively-Human historical input.

One launcher retains exactly one admitted `HumanComparisonContext` for its
lifetime. Replay seeks/replacement/exit, reset/new game, difficulty changes and
later Live actions do not retarget it. While it exists, **Open Comparison…** only
raises that owner. The launcher owns one unchanged `SameBoardExecutionJob`, active
token/cancellation intent, one retained completed execution and at most one viewer.
Run requires no active token AND an idle job. Normal Run/Cancel do not wait.
Legitimate solver WON/LOST are successful execution results, not failures. Closing
the viewer retains the completed result; reopening does not rerun solvers.

Launcher close irreversibly begins shutdown and disables execution, then calls
the accepted bounded `job.shutdown()`. Reap/cleanup failure rejects close and
retains ownership for retry. Only successful job shutdown permits viewer closure;
any rejected close leaves the launcher non-runnable, with safe close retry.
Main close order is Comparison launcher, Stage-3 Visualizer launcher, then existing
remaining teardown. Comparison close failure prevents all later teardown.

Independent Claude Code **read-only** audit reported **BLOCKER 0 / REQUIRED 0 /
OPTIONAL 4**, with a **PASS / accept Slice 4 as implemented** recommendation;
Claude did not execute/rerun tests. ChatGPT independently reviewed source/tests
and accepted without production correction. Optional dispositions: **O-1 DEFER /
evidence-triggered**, theoretical matching success after cancellation intent (the
real job contract and acceptance evidence do not expose that path);
**O-2 SATISFIED by Slice 5A**, real packaged-worker/job/launcher lifecycle evidence;
**O-3 NONBLOCKING**, 2085/2085 full development PASS with no new production defect;
**O-4 DEFER**, captured-source wording polish (user acceptance reported no confusion
requiring a correction). None is a production acceptance blocker.

Reported Slice 4 verification: **55 new 4B passed (31 launcher / 24 main UI);
32 4A viewer; 29 Slice 3; 84 Slice 2B; 31 Slice 2A; 29 Slice 1; 370 relevant existing
regressions; combined reported verification: 630 passed**, zero failures/errors/skips.
Those were Slice-4-only counts; full source/package/native acceptance below is
Slice 5 evidence, not independent-audit test results.

**Slice 5 — Acceptance / Packaging / Native Manual Closeout COMPLETE / ACCEPTED.**
Qualified candidate: `a59d0d963bdf1544a03968163b884342e2797ee0`.
Final evidence root: `results/same-board-comparison-final-acceptance/20261017-022243/`;
primary `acceptance-summary.json`, package `dist/Minesweeper/`.

- Source focused: **916 PASS**, 0 failures/errors/skips, **44.286 s**.
- Full development: **2085 PASS**, 0 failures/errors/skips, **118.136 s**.
- Fresh Python 3.12.10 x64 / pip 25.0.1 / documented pins: **2085 discovered,
  2060 PASS, 25 permitted optional image/video replay-validation skips**, 0 failures/errors.
- Fresh onedir/windowed AMD64 / PE32+ / GUI build: **exit 0, 63.789 s**.
  EXE SHA-256: `4893d24e1f9d50e47008f94aff4399188123331f49d3cd8d70ab3bc5eab6a5e8`.
- Frozen profile source/package bytes match SHA-256
  `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
  Specs/runner/planner unchanged; no official 100k regeneration or ZiNi holdout consumption.
- Packaged safe-origin board: **WON/WON, 4 actions / 504,020 µs each**; mined origin:
  **LOST/LOST, one OPEN(0,0) / 126,005 µs each**, no regeneration/retry.
  Deterministic source/package equality excludes runtime decision-compute clocks
  and Stage-2 Replay elapsed engine-clock timestamps, not arbitrary semantic differences.
- Packaged failure boundaries, existing Stage-3/ZiNi dispatch compatibility and
  native startup/normal close PASS. Seven actual packaged-child lifecycle cases
  PASS; `packaged-lifecycle.json` records each PID/private directory, successful
  reap/removal and original Human context/Replay/Mouse Trace identity retention.
- **Project user, 2026-10-17 (Asia/Seoul): packaged native/manual A–L PASS** on this
  exact package: startup, both source routes, Run/result facts, independent indices,
  Human-only full trace, reopen, Cancel, active launcher/main close and existing-feature
  compatibility. This is reported interaction evidence, not inferred from screenshots.
  Human WON / Stage 2 LOST / Stage 3 LOST displayed legitimate results; a loaded
  Replay at another index still supplied its entire stream and viewer Human index 0.

Historical `results/same-board-comparison-final-acceptance/20261017-014937/` remains
**BLOCKED**: 2085 discovered / 2076 passed / 9 fixture errors / 0 failures/skips.
The no-op `_init_ui()` fixture lacked mandatory `same_board_comparison_action`.
Only `tests/test_replay_statistics.py` changed in the accepted correction; verification
was **9/9 affected, 158/158 related, 2085/2085 full PASS**. No production correction.
The final automated root restarted from the new clean candidate. Its JSON remains
the pre-manual snapshot; the [closeout](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md)
records subsequent user PASS without rewriting raw evidence.

Nonblocking UX: standard Comparison slider track page-step is **OPTIONAL / DEFER**;
drag/arbitrary selected-run seek works, exact track jump was not required.
**KEEP** Human recorded Mouse Trace separate from the independent Visualizer's
synthetic Stage-3 cursor; Comparison has no solver overlay. Changing production
would reopen package qualification. No generic speed winner/ranking/ratio is claimed.

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
- **Human Mouse Trace / Path Visualization — FINAL ACCEPTANCE PASS / CLOSED
  (2026-10-16)**: [closeout](stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md).
  Includes Physical Mouse Gesture Fidelity and performance hardening; final user
  native acceptance of the final package passed.

Current accepted contracts:

- Human trace records actual Live-board accepted event samples in board-local Qt
  logical pixels, with exact subpixel positions and an independent monotonic clock.
  No timer sampling, distance filtering or semantic point dropping. Continuity
  breaks create segments; marker action semantics come from actual ReplayEvent indices.
- Recording defaults ON per app/session and locks on first committed timed human
  OPEN/FLAG: L release for OPEN, R press for FLAG. Untimed pre-start CHORD cannot
  start trace. OFF at that lock point, a committed Auto action or Replay append
  failure after committed human input invalidates the Human trace.
- Replay v2 can carry the separate Human trace attachment; v1 remains trace-free
  and readable. Display is optional after a Live game or in Replay; seek retains
  the attachment.
- Mode A/C FLAG/UNFLAG commits immediately on R press; R release adds no FLAG.
  Mode A keeps normal L-release OPEN/CHORD and independent R actions during L hold;
  Mode C never CHORDs. Mode B arms on held-button overlap regardless of origins,
  suppresses R FLAG only when L was already held, and never undoes an earlier
  standalone R FLAG. First release attempts CHORD at the current target; trailing
  release is inert, and new overlaps can re-arm with one button still held.
  FLAGGED-center preview preserves the flag and depresses surrounding hidden cells.
- Primitive recorder storage, pre-start gating, geometry cache and **16 MiB**
  bounded raster/fallback preserve sample semantics. Final user testing found no
  noticeable trace performance regression; zero overhead is not claimed.
- Stage-3 synthetic cursor remains presentation only. TracePlayer owns committed
  integer state; the modeled controller owns partial time. Recorded costs, frozen
  V1 / Model C identities and official 100k evidence are unchanged.

Qualified acceptance: **627/627 focused**, **1825/1825 source full** with zero
failures/errors/skips; fresh build environment **1800 passed / 25 optional image/video
validation skips**, zero failures/errors. Fresh AMD64 GUI package, both workers,
native GUI, Replay v2 trace round-trip and final user native check passed; no orphans.
Authoritative technical evidence:
`results/human-mouse-trace-final-acceptance/20261016-003839/acceptance-summary.json`.
The earlier `20261015-215537/` root remains historical performance-hardening evidence,
not the final package. The new closeout records user acceptance after that JSON's
pre-user-check status; neither evidence root is rewritten.

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
**Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace**; similar controls do not justify merging their models.

---

## 6. Next action

Same-board Comparison is **FINAL ACCEPTANCE PASS / CLOSED**, with Slices 0–5
COMPLETE / ACCEPTED. No Same-board implementation or technical acceptance gate
remains. On recovery, read live Git for the latest branch, HEAD, remote and merge
state. The qualified acceptance SHA is historical identity, not a permanent
branch tip or an instruction to perform further Git integration.

**ACTIVE — Representative-board Demonstrations / Timeline Analytics. Slice 0 —
Contract COMPLETE / ACCEPTED by ChatGPT final review.** The
[accepted contract](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md) governs
the next step. **Implementation has NOT begun. No actual exemplar game IDs have
been selected. NEXT / now authorized implementation scope — Slice 1: Pure
timeline analytics** over existing solver telemetry. No actual exemplar IDs may
be selected in Slice 1. Exemplar selection remains in the accepted Slice 2/3
scope: pure selector work in Slice 2 and accepted-evidence selection/report
integration in Slice 3.

Exact accepted Stage-2 DB, Stage-3 DB, G4 comparison and G4 result hashes are
required before real-evidence report acceptance. Reuse accepted G4 deltas, load
only selected games' detailed actions, and never rerun the official 100k. Human
Replay/Mouse Trace adapters and production Qt UI are deferred; no new algorithm,
Model C, database/schema or telemetry is authorized. First actual Extended
algorithm research remains LATER. The implementation feature branch
`feature/stage3-timeline-analytics` must exist and remain active **before and
during Slice-1 implementation**. Live Git remains authoritative for current
branch/HEAD state. Slice-0 drafting restrictions are historical task boundaries,
not the post-acceptance implementation authorization.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human Mouse Trace is accepted actual sampled Live-board pointer presentation data,
not Stage-3 synthetic movement, Model C calibration evidence or solver input.
The closed Comparison contract retains these separate models and time authorities.

Keep presentation separate from planner inputs, physical identity and recorded
costs. Retain Step 0/current PLAYING with known final WON, exact action-boundary
commits, integer navigation and non-persistent controls. Synthetic movement and
smoothstep easing do not measure physical mouse motion.

Foundation F-2 remains **OPTIONAL / DEFER**: packaged windowed transport exceptions
may show PyInstaller's uncaught-exception dialog rather than exit immediately.
There is no false success; existing Cancel/close ownership/reaping remains.
No new evidence promotes F-2 to required work.

Preserve historical and new acceptance artifacts. The Same-board closeout created
no release/tag/ZIP; Timeline Slice 0 adds no generated evidence. Do not reopen ZiNi
work or consume its unopened final quality holdout.

---

## 7. Stage-3 Extended roadmap and boundaries

Stage-3 Extended remains **ACTIVE**, separate from frozen V1.

Natural dependency roadmap — not a rigid chronological schedule:

1. **CLOSED:** Execution / Playback / Visualizer Foundation.
2. **CLOSED:** Version / Settings Identity Separation.
3. **CLOSED:** Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **CLOSED:** Human Mouse Trace / Path Visualization.
5. **CLOSED:** Same-board Human / Stage-2 / Stage-3 Comparison — Slices 0–5
   COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B.
6. **ACTIVE:** Representative-board Demonstrations / Timeline Analytics —
   Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review.
   Implementation has NOT begun. NEXT / now authorized implementation scope —
   Slice 1: Pure timeline analytics.
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
the Extended README distinguishes the closed milestones, active Timeline Analytics
Slice-0 contract and later algorithm research. Arbitrary Stage-3 seeks still rebuild from
index 0; incremental forward is implemented, while arbitrary-seek caching is deferred.

---

## 8. Documentation map

Start from:

- `docs/README.md`
- `docs/stage3-v1/README.md`
- `docs/stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md`
- `docs/stage3-extended/README.md`
- [Timeline Analytics contract — Slice 0 accepted](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md)
- [Human Mouse Trace closeout](stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md)
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
Human Mouse Trace / Path Visualization FINAL ACCEPTANCE PASS / CLOSED.
Human Mouse Trace qualified SHA: e32145fa5c114e1ce500ad2e837ef6000cc49cca.
Same-board Human / Stage-2 / Stage-3 Comparison: FINAL ACCEPTANCE PASS / CLOSED.
Slice 0–5 및 내부 2A/2B·4A/4B는 COMPLETE / ACCEPTED입니다.
Qualified source/package SHA: a59d0d963bdf1544a03968163b884342e2797ee0.
Qualified development branch at acceptance: feature/stage3-same-board-comparison.
이후 branch 존재 여부 / 최신 HEAD / merge 상태는 live Git에서 확인하세요.
Closeout: docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md.
Contract: docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md.
최종 evidence: results/same-board-comparison-final-acceptance/20261017-022243/.
Package: 위 root의 dist/Minesweeper/.
EXE SHA-256: 4893d24e1f9d50e47008f94aff4399188123331f49d3cd8d70ab3bc5eab6a5e8.
Source focused 916 / full 2085 PASS, zero failures/errors/skips.
Fresh-env: 2085 discovered / 2060 PASS / optional image-video skips 25, zero failures/errors.
Fresh package exit 0; safe/mined worker·기존 dispatch·7 real packaged lifecycle PASS.
프로젝트 사용자 2026-10-17 native/manual A–L PASS; 정확한 package와 상세 gate는 closeout 참조.
Historical 20261017-014937 root는 BLOCKED (2076 PASS / 9 fixture errors)로 보존합니다.
a59d0d9는 tests/test_replay_statistics.py만 보정했으며 production 변경은 없습니다.
9/9 affected, 158/158 related, 2085/2085 full PASS 후 새 SHA/root에서 수용을 재시작했습니다.
Claude read-only audit: BLOCKER 0 / REQUIRED 0 / OPTIONAL 4 / PASS; 테스트 재실행 없음.
O-1 DEFER/evidence-triggered, O-2 SATISFIED, O-3 NONBLOCKING, O-4 DEFER.
Comparison slider track page-step는 OPTIONAL/DEFER; Human trace/solver synthetic 표현 분리는 KEEP.
Same-board 구현 또는 기술 수용 작업은 남아 있지 않습니다. 수용 SHA는 역사적 identity이며
현재 Git 통합 상태나 후속 Git 작업 지시를 의미하지 않습니다.
Stage-3 Extended는 ACTIVE; Representative-board Demonstrations / Timeline Analytics는
ACTIVE이며 Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review입니다.
Read-only discovery는 ChatGPT DISCOVERY PASS입니다.
Contract: docs/stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md.
구현은 시작하지 않았고 실제 exemplar game ID도 선택하지 않았습니다.
NEXT / now authorized implementation scope — Slice 1: Pure timeline analytics.
Slice 1은 승인된 다음 구현 범위이지만 아직 시작하지 않았습니다.
Slice 1에서는 실제 exemplar ID를 선택하면 안 됩니다. Exemplar selection은 accepted
Slice 2/3 범위이며 Slice 2는 pure selector, Slice 3는 accepted-evidence selection/report 통합입니다.
implementation feature branch feature/stage3-timeline-analytics는 Slice 1 구현 시작 전부터
구현 중에도 존재하고 active 상태를 유지해야 합니다. 현재 branch/HEAD 상태는 live Git이
authoritative이며 이 문서에서 commit identity를 추정하지 마세요.
첫 구현 입력은 exact accepted official Stage-2/Stage-3 DB 및 G4 evidence뿐입니다.
계약의 네 artifact hash를 real-report 수용 전에 검증하고, official 100k는 재실행하지 않습니다.
독립 completed-action-count timeline과 static report이며 Human adapter/interactive GUI는 DEFER입니다.
새 algorithm/Model C/schema/telemetry는 범위 밖이고 첫 Extended algorithm research는 LATER입니다.
Human Mouse Trace는 Live-board logical-pixel event samples와 독립 clock을 사용하며,
Replay v2 attachment / 선택적 표시 / 성능 hardening / 물리 입력 보정을 수용했습니다.
FLAG는 R press, OPEN은 L release, Mode-B CHORD는 현재 target의 첫 release입니다.
Source focused 627 / full 1825 PASS, fresh-env 1800 PASS + optional skips 25,
최종 package 및 사용자 native/manual 수용 PASS입니다.
후속 기능이 이미 구현됐다고 가정하지 말고 현재 source/tests로 확인하세요.
Closeout: docs/stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md.

Application/release != algorithm != physical model/profile != presentation.
Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace.
Human Mouse Trace는 실제 sampled Live-board pointer presentation data이며,
OS-global tracking, Stage-3 synthetic movement, Model C calibration evidence나 solver 입력이 아닙니다.
Presentation interval, Replay elapsed time, CPU decision time, modeled physical
time은 별개입니다. Stage3Execution은 spec / board / result이며 viewer는 solver 입력이 아닙니다.
Stage-3 설정 persistence와 registry는 없습니다.
Frozen specs/profile, official evidence와 미개봉 ZiNi holdout을 보존하세요.
F-2 packaged transport hardening은 OPTIONAL / DEFER입니다.
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
