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

Live Git verified on 2026-10-16 before Human Mouse Trace documentation closeout:

- branch: `main`; clean working tree
- HEAD = local `origin/main` = live remote main:
  `e32145fa5c114e1ce500ad2e837ef6000cc49cca`
- this is the qualified implementation/package SHA, including physical gesture fidelity
- no Human Mouse Trace / physical gesture feature branches remained locally or remotely

This SHA is the qualified implementation/package baseline, not necessarily the
latest main HEAD. Documentation-only closeout may advance main beyond it without
replacing that implementation identity. Always read live Git for the latest HEAD.
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

**Stage-3 Extended remains ACTIVE. Active milestone:
Same-board Human / Stage-2 / Stage-3 Comparison.**
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
real job terminal contract does not produce that path); **O-2 DEFER to Slice 5**,
launcher coverage using real-job success/cancel; **O-3 optional Slice 5 coverage**,
minor adjacent gaps where useful; **O-4 optional/deferred**, captured-source wording
polish. None is a production acceptance blocker.

Reported Slice 4 verification: **55 new 4B passed (31 launcher / 24 main UI);
32 4A viewer; 29 Slice 3; 84 Slice 2B; 31 Slice 2A; 29 Slice 1; 370 relevant existing
regressions; combined reported verification: 630 passed**, zero failures/errors/skips.
No full suite, fresh package or native GUI acceptance has been completed for
Slice 4; those remain Slice 5 evidence, not independent-audit test results.

**NEXT — Slice 5: Acceptance and closeout.** Not begun (section 6). Stage-3 Extended
and the Comparison milestone remain ACTIVE pending Slice 5 closeout; the milestone
is not closed.

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

**NEXT — Slice 5: Acceptance and closeout.** Slices 0–4, including internal
2A/2B and 4A/4B, are COMPLETE / ACCEPTED. Slice 5 has not begun. The existing
[milestone acceptance contract](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md#13-milestone-level-acceptance-contract)
remains authoritative. As applicable, remaining acceptance includes:

- full source regression and focused/relevant frozen-boundary regression;
- fresh Windows package/build and packaged Same-board worker verification;
- native/manual Comparison UI acceptance, including real Run / Cancel / result
  reopen / launcher-close / main-close ownership;
- existing Replay, Human Mouse Trace and Stage-3 Visualizer compatibility;
- preservation of frozen Stage-3 V1 / Model C and historical evidence;
- final documentation/housekeeping; feature → main merge/push only after final acceptance.

The Comparison milestone remains ACTIVE until that closeout. No Slice 5 work
is claimed by this documentation sync.
Use live Git/source/tests to determine whether later work has already begun.
Do not treat this roadmap as implementation approval or claim later milestones exist.
No later Timeline Analytics or Extended algorithm research is authorized yet.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human Mouse Trace is accepted actual sampled Live-board pointer presentation data,
not Stage-3 synthetic movement, Model C calibration evidence or solver input.
Comparison acceptance must retain these separate models and time authorities.

Keep presentation separate from planner inputs, physical identity and recorded
costs. Retain Step 0/current PLAYING with known final WON, exact action-boundary
commits, integer navigation and non-persistent controls. Synthetic movement and
smoothstep easing do not measure physical mouse motion.

Foundation F-2 remains **OPTIONAL / DEFER**: packaged windowed transport exceptions
may show PyInstaller's uncaught-exception dialog rather than exit immediately.
There is no false success; existing Cancel/close ownership/reaping remains.
No new evidence promotes F-2 to required work.

Preserve historical and new acceptance artifacts. This milestone created no
release/tag/ZIP. Do not reopen ZiNi work or consume its unopened final quality holdout.

---

## 7. Stage-3 Extended roadmap and boundaries

Stage-3 Extended remains **ACTIVE**, separate from frozen V1.

Natural dependency roadmap — not a rigid chronological schedule:

1. **CLOSED:** Execution / Playback / Visualizer Foundation.
2. **CLOSED:** Version / Settings Identity Separation.
3. **CLOSED:** Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **CLOSED:** Human Mouse Trace / Path Visualization.
5. **ACTIVE pending Slice 5 closeout:** Same-board Human / Stage-2 / Stage-3 Comparison —
   Slices 0–4 COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B.
   **NEXT:** Slice 5 — Acceptance and closeout (not begun).
6. **LATER:** Representative-board demonstrations / Timeline Analytics.
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
Qualified implementation/package SHA: e32145fa5c114e1ce500ad2e837ef6000cc49cca.
Stage-3 Extended 전체는 ACTIVE이며 현재 활성 마일스톤은
Same-board Human / Stage-2 / Stage-3 Comparison입니다.
Slice 0 계약과 Slice 1 — Comparison domain and admission은 COMPLETE / ACCEPTED입니다.
Slice 1은 원본 Human Replay와 별도 Mouse Trace attachment를 보존하는 순수 Qt-independent
domain/admission foundation 및 focused tests이며 상세 수용 조건은 section 4를 보세요.
Contract: docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md.
Slice 1 reported verification: focused 29 / relevant regression 202 / combined 231 passed,
zero failures/errors/skips; Slice 1 full suite/package/native GUI run은 없습니다.
Slice 2 — Isolated execution and metrics는 COMPLETE / ACCEPTED입니다.
내부 Slice 2A — Pure isolated execution and metrics 및
Slice 2B — Worker/process integration도 COMPLETE / ACCEPTED입니다.
정확한 Human layout에서 독립 solver 실행, native result/trace 보존, 분리된 metric과
accepted Model C ordered-action seam의 범위는 section 4를 보세요.
Slice 2A reported verification: new 31 / Slice 1 29 / relevant regression 274 / combined 334 passed,
zero failures/errors/skips; Slice 2A full suite/package/native GUI run은 없습니다.
Slice 2B final reported verification: 2B 84 / 2A 31 / Slice 1 29 / relevant regressions 374 /
combined 518 passed, zero failures/errors/skips; full suite/fresh package/native GUI acceptance는 없습니다.
Parent ownership, corrected validation boundary, audit 및 responsiveness evidence는 section 4를 보세요.
Slice 3 — Pure playback coordination도 COMPLETE / ACCEPTED입니다.
same_board_playback.py는 원본 stream과 독립 action index / 현재 status와 final outcome을 보존합니다.
Slice 3 reported verification: focused 29 / 2B 84 / 2A 31 / Slice 1 29 / relevant regressions 139 /
combined 312 passed, zero failures/errors/skips; full suite/package/native GUI run은 없습니다.
Slice 4 — Read-only comparison UI 및 내부 4A/4B는 COMPLETE / ACCEPTED입니다.
4A viewer와 4B captured-source launcher/main lifecycle의 수용 범위는 section 4를 보세요.
Slice 4 reported verification: 4B 55 (launcher 31 / main UI 24), 4A 32, Slice 3 29,
2B 84, 2A 31, Slice 1 29, relevant regressions 370 / combined 630 passed,
zero failures/errors/skips; full suite/fresh package/native GUI acceptance는 아직 없습니다.
Claude read-only audit: BLOCKER 0 / REQUIRED 0 / OPTIONAL 4 / PASS; 테스트 재실행은 하지 않았습니다.
ChatGPT가 source/tests를 독립 검토하여 production correction 없이 수용했습니다.
NEXT: Slice 5 — Acceptance and closeout (not begun; 남은 gate는 section 6).
Comparison milestone은 Slice 5 closeout 전까지 ACTIVE이며 아직 CLOSED가 아닙니다.
2A/2B와 4A/4B는 각각 Slice 2와 Slice 4 내부 구분이며 새 roadmap milestone이 아닙니다.
Slice 3은 deterministic reconstruction과 각 run의 독립 remembered index만 다루며 UI는 포함하지 않습니다.
frozen Stage-3 V1 / Model C는 변경되지 않았습니다.
Timeline Analytics 및 Extended 알고리즘 연구는 아직 승인되지 않았습니다.
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
