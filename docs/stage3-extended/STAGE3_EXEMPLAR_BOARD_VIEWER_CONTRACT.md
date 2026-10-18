# Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer — Contract

Status: **FINAL ACCEPTANCE PASS / CLOSED — Slices 0–4 COMPLETE / ACCEPTED.**
**BLOCKER 0 / REQUIRED 0. Date: 2026-10-18 (Asia/Seoul).**
ChatGPT accepted final qualification at
`ff6358ae62b6f343bda36069d7164bda9aebee74` —
`test: preserve frozen E/L pilot source provenance`.
Production usability commit: `29af53b15d1fff144df5873b62fcec4af91adaaa` —
`feat: improve exemplar viewer inspection usability`.

Live Git before this documentation closeout: branch
`feature/stage3-exemplar-board-viewer`; HEAD and local origin tracking ref both
matched the qualified SHA, with clean worktree/index. No fetch was performed.
`ff6358a` changed only the reviewed historical E/L provenance/test boundary;
Viewer/application production bytes remain unchanged from `29af53b`.
Later documentation commits do not replace the qualified source identity.

Final PASS evidence: `results/stage3-exemplar-board-viewer-final-acceptance/20261018T094900066913Z/`.
Preserve first qualification `20261018T091846923796Z/` in that parent as **HOLD**;
repair evidence remains `results/stage3-e-l-source-compatibility-repair/20261018T093614465991Z/`.
**R-2 CLOSED; O-5 CLOSED.** The [final closeout](STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md)
records source/evidence lineage, fresh verification, package and user-native attribution.

This consolidated final contract supersedes the initial manual-only/final-counter
UI dispositions through the explicitly accepted usability revision. Historical
slice evidence below remains dated evidence, not a replacement for final qualification.
Stage-3 Extended remains **ACTIVE**; Timeline Analytics and prior milestones remain
CLOSED. Next mandatory work is Visualization Usability Polish, then fixed-exemplar
human interpretation before separately scoped algorithm research.

## 1. Purpose and fixed admission

Provide a standalone read-only tool for human/domain interpretation of accepted
Stage-2 and Stage-3 visible board progression. Admit ONLY these already-selected
**deterministically selected category exemplars**, not a statistically
representative sample:

| Game index | Frozen category | Accepted WW delta_us (Stage 3 minus Stage 2) |
| ---: | --- | ---: |
| 73758 | Maximum Stage-3 WW advantage | -27009085 |
| 73024 | Median-delta WW; lower-median zero-based rank 18850 of 37702 | -16487355 |
| 93557 | Closest-to-zero Stage-3 WW advantage | -7877513 |
| 1 | LL control | Not applicable; termination cost only |

The closed Timeline selection remains authoritative. Stage-2 WW advantage,
exact WW tie, WL and LW categories remain EMPTY. Do not rerank, call
`select_exemplars()`, substitute for visual interest or browse arbitrary IDs.

This is not a solver rerun, planner replay, benchmark rerun, new selection,
synchronized cross-solver timeline, normalized progress, algorithm research or
Human comparison. Interpretation does not establish causal or counterfactual
claims and does not authorize any new solver policy or algorithm implementation.

The human expert may inspect visible progression, board structure, action
composition, FLAG/CHORD/OPEN behavior, execution counters, Model C modeled physical
time and target-to-target geometry. The viewer supplies facts for HUMAN domain
interpretation; it does not classify moves as good/bad, optimal/inefficient,
necessary/unnecessary, avoidable backtracking or causal FLAG-to-CHORD payoff.

## 2. Required inputs and provenance decision

**Required official source inputs: the two exact accepted analysis DBs.** Supply
their paths explicitly; authenticate the role and exact bytes before opening.
Do not silently substitute another source. The fixed identities/memberships in
this tracked contract and the [closed Timeline record](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)
are the exemplar admission authority; the accepted loader preserves them.

| Required source | SHA-256 |
| --- | --- |
| Stage-2 accepted analysis DB | `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` |
| Stage-3 accepted analysis DB | `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e` |

Also authenticate installed frozen Model C through
[`authenticate_model_c()`](../../benchmark_modeled_time.py); it supplies the
post-hoc cost authority, not board identity:

| Model fact | Required value |
| --- | --- |
| Physical model / profile version | `overlap_floor_log2_distance_v1` / 1 |
| Profile SHA-256 | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` |
| Timing-table SHA-256 | `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b` |
| Timing unit / initial cursor | `us` / `(0,0)` |

**G4 comparison/result and generated Timeline HTML are not required runtime
inputs.** They established the already-accepted selection and reference totals;
they supply no additional layout or executed-action data needed for this viewer.
Omitting them loses fresh G4 gate/provenance reauthentication during a viewer
session, not reconstruction capability. Do not claim fresh G4 authentication
when they were not read. Label the table above and reference totals below as
accepted Timeline facts; newly evaluated selected totals must match those exact
references, without recalculating whole-population deltas or selection.

G4 lineage remains preserved in the closed record: comparison SHA-256
`f31226a660eda02a804ee41c66f233513fd950cac6f6123f36bf62578fbf5979`;
result SHA-256 `09f228ee9a8ec96a934dbb94656a7cd6f03c7987640df267f5fd6818dd007cc0`.
Do not scrape the HTML as an action source or weaken the closed report's separate
four-artifact acceptance contract.

### Read-only lifecycle and run identity

- Record source paths/roles, hashes, sizes, modification timestamps and sidecar
  state before opening. Require stable completed preserved sources without
  unexpected `-wal`, `-shm` or `-journal` sidecars.
- Open independently via
  [`connect_database_readonly(path, immutable=True)`](../../telemetry_repository.py).
  This explicitly uses `mode=ro&immutable=1`; caller owns close. No ATTACH, writer,
  migration, checkpoint, conversion, copy/repair or writable fallback.
- Discover the matching run from metadata; do not assume `run_id=1`. Reject zero
  or multiple matches. Identity includes source role/hash plus run/configuration,
  not `run_id` alone.
- Require COMPLETED, clean, official-eligible exact `[0,100000)` coverage;
  requested/processed/stored counts all 100000. Existing summary/index coverage
  reads are allowed; detailed event reads are limited to the four admitted IDs.
- Require `EXPERT_GENERAL_V1`, 30 x 16, 99 mines, `FIRST_CLICK_FIXED_0_0`, generator
  V1 and seed scheme `game_index`. Require each selected seed equals its game index.
- Use the existing modeled-time run validator for exact solver/config/telemetry
  identity: Stage 2 `STAGE_2` / `SIMPLE_MINIMUM_RISK` / semantic version 1;
  Stage 3 `STAGE_3` / `E_FIRST_FIRST_REVEAL_V1` / semantic version 2. Physical
  SQLite schema remains version 1. Do not repair mismatching metadata.
- Read each selected summary independently; match seed, fingerprint and canonical
  first click `(0,0)` across sources. Load complete selected action streams only,
  ordered by `action_index`; each unique selected game is loaded once per source.
- Close connections and recheck hashes/sizes/mtimes/sidecars before publishing a
  usable reconstructed bundle. Fail closed on change. UI navigation/toggling
  owns no live DB connection or source reads.
- Retain actual source/run/config/model provenance and reconstruction source Git
  identity/interpreter version. These reconstructed observations are not persisted
  historical snapshots.

## 3. Board and action authority

Use [`generate_board(EXPERT_GENERAL_V1, game_index)`](../../benchmark_board.py)
only for admitted IDs. Require generated seed/configuration and canonical
`calculate_board_fingerprint()` equality with BOTH persisted fingerprints and
the fixed reference below, before Engine replay. No replacement, retry on a
different seed or first-click relocation is permitted.

The canonical fingerprint is SHA-256 of `MSLAYOUT1\0`, big-endian uint32
width/height/mine count and mine coordinates sorted by `(y,x)`. It does not encode
seed, corpus, generator or first-click policy; validate those separately. The
generator's documented reference runtime does not replace the fingerprint gate.

Decode persisted rows into original [`GameRecord` / `ActionEvent`](../../telemetry_model.py).
Use explicit [`telemetry_schema`](../../telemetry_schema.py) mappings for action,
status, result and inference category; SQL integer values are not Engine enum
values. Reuse `decode_probability()` for exact Fractions. Preserve SQL NULL as
None and integer zero as zero; never infer missing evidence.

Reuse [`project_timeline()`](../../timeline_analytics.py) for complete-stream,
summary and Model C validation. Keep original event references. Its structural
checks do not establish board-state effects; the reconstruction layer adds those.

Initialize [`MinesweeperEngine.reset_with_mines()`](../../core_engine.py) with the
authenticated layout, then apply ONLY each original event's OPEN / FLAG / CHORD
target in exact order. No Stage-2/Stage-3 decision analysis, planner, solver, worker or
`run_expert_stage3_execution()` call. No hidden answer is used to choose actions.
The Engine necessarily holds the layout internally for execution; its existing
static `board_analyzer` setup for 3BV/Ops is not solver decision recomputation.
Finalized-board reference metrics are allowed under their separate answer-derived
label. Reconstructed displayed-frame counters are also allowed under current Engine
semantics, never as persisted historical solver evidence or automatic judgments.
The separate optional ZiNi reference calculation described below is not part of
action reconstruction and never chooses or changes a recorded action.

Reject invalid types/bounds, missing/duplicate/shifted indices, incomplete streams,
premature termination and post-terminal input. Require per-event status and final
WIN/LOSS agreement; Engine's silent no-op behavior is not sufficient validation.
Publish no partial reconstruction on failure.

## 4. Immutable frames and before/after facts

For N recorded semantic inputs:

- `frames[0]`: exact fixed board, all HIDDEN, no inputs applied; Engine status PLAYING.
- `frames[n]`: after exactly n persisted inputs, for `0 <= n <= N`.
- Selected action ordinal `j` is `event.action_index + 1`; its before/after frames
  are `j-1` / `j`. There is no action at ordinal zero.
- Each solver owns its sequence and index. Equal indices or relative positions
  establish neither equal board state nor equal progress.

Return immutable public observations and per-action immutable coordinate sets.
Newly revealed SAFE cells are exactly coordinates whose public value changes
from HIDDEN or FLAGGED to 0..8. Reconcile their count with each recorded
`safe_cells_opened_delta`. Highlight safe cells, not terminal mine disclosure,
under that label. Preserve exact before/after observations, recorded action/type,
previous recorded target, explicit flag delta and reconstructed status transition.

The first action has no previous recorded target. Model C's `(0,0)` origin is
separately labeled as its initial cursor; it is not a synthetic prior action.

Reconcile explicit FLAG effects under the accepted solver hidden-target contract:
FLAG records +1; other inputs record 0. Validate the actual target transition;
do not equate total board flag-count change with executed FLAG inputs. Automatic
WIN flags and flood-related flag clearing remain Engine effects. Accepted example:
game 73758 Stage 3 final action produces 23 automatic visible flags while its
persisted `explicit_flag_delta` is 0. No extra events are created.

## 5. Public View and terminal feedback

Public View is the default authoritative interpretation view, rendered from the
reconstructed public observation, with covered cells, ordinary flags and revealed
0..8. Current-action/previous-target markers are recorded-target decorations;
they do not assert a native cursor trajectory. After-view highlighting identifies
newly revealed safe coordinates for the selected action.

**KEEP actual Engine terminal feedback.** On LOSS the public observation may
contain EXPLODED, MINE, FALSE_FLAG, retained correct FLAGGED cells and revealed
safe cells. Label the terminal state **Terminal Engine feedback**. Do not mask
these symbols back into HIDDEN. They are genuine terminal public output, not
Answer Overlay. For pre-loss reasoning inspect frame `N-1`. Automatic WIN flags
are also retained as Engine effects, separately from executed FLAG counts.

No board click executes any game action. Reconstructed active/wasted counters may
appear in separately labeled displayed-frame Counters; their mechanical names
are not strategic judgments. Engine reconstruction elapsed time/rewards are not
historical solver measurements and supply no time/rate value. The final Viewer
labels time rows explicitly as Model C; it claims no historical elapsed clock.

## 6. Answer Overlay

**KEEP; default OFF.** Label: **Show hidden answers — reference overlay**.
Use a separate answer-glyph layer at approximately **0.35 opacity** only where
the public cell is HIDDEN: faint mine glyph, faint nonzero safe number, blank zero.
The covered-cell appearance stays dominant. FLAGGED cells remain ordinary flags;
revealed cells and terminal symbols retain ordinary public rendering.

The overlay is answer/reference presentation, never solver-visible evidence.
It must not change or enter public observations, replay/reconstruction, inference
or probability metadata, Model C costs, solver input or navigation state.
Turning OFF removes answer decorations and restores pure Public View exactly,
including tooltips/accessibility content. OFF still retains terminal public mines.

Reuse the separate faint glyph rendering IDEA from
[`zini_explorer_ui.py`](../../zini_explorer_ui.py), not its default-ON policy,
model/controller/search/trace or logical-state semantics for this overlay. The
separate Counters ZiNi reference seam below does not couple the viewer to Explorer.
Do not merge the tools.
Keep static answer information separate from public frame data; `BoardSnapshot`
is hidden static truth, not a public observation.

## 7. UI ownership, navigation and playback

ONE board, fixed exemplar and Stage-2/Stage-3 selectors. Each of the eight pairs
remembers its own `_Position` and exact modeled playhead. No common playhead,
normalized progress, index mapping or synchronized side-by-side display.

Keep First / Previous / Play-Pause / Next / Last, Before / After, direct-seek
slider and ONE Action ordinal entry + Go action. There is no editable Frame box;
displayed frame is a read-only fact. Return/Enter or Go explicitly commits action
`j` in `1..N` and starts AFTER. Focus loss/Tab never commits the action entry.
Initial = frame 0 / no selected action; AFTER j = frame j; BEFORE j = frame j-1.
Frame navigation to k>0 selects action k AFTER. Selected action metadata remains
inspection context, not evidence that the action has already been applied.

Track click seeks directly; native handle dragging remains. Index slider range
is `0..N`; Model C Time slider is `0..total_modeled_us`, validated against Qt's
integer range. Time seeks retain the exact playhead and use an immutable
cumulative tuple/bisect to show the last completed frame, including exact boundaries.

Index interval: **20..5000 ms/action, default 200**, minimum `Max (20 ms)` and
status `Index — Max (20 ms/action)`. Committed below/above-range text clamps;
Up from minimum gives 21 ms. Font/style-owned sizing fits Max and 5000 ms labels
without an oversized generic sizeHint floor or stretching with the row.
Index playback completes one action per interval; BEFORE j completes j next.
Partial progress pauses/resumes and active interval changes re-anchor coherently.

**Model C Time** uses authenticated integer cumulative action microseconds,
0.25x..8x presentation speed and a monotonic wall anchor. It never recomputes
Model C, uses compute/Replay/reconstruction time, or creates intermediate board
states. BEFORE j begins at completion j-1 and waits action j's modeled duration.
Pause preserves exact between-action time; speed change re-anchors without a
jump. Late ticks catch up all due boundaries; terminal time stops playback.
Mode switches preserve the accepted completed-frame position; Model C-to-Index
aligns to the last completed frame and discards incompatible partial animation.

Approximately **16 ms presentation refresh** supports smooth cursor motion, not
Index duration authority, Model C cost authority or a guaranteed FPS claim.
Manual navigation and pair switching stop playback; mode/interval/speed changes
may continue it. Answer Overlay and route toggles leave playback/position alone.
Navigation, partial refresh and toggles are immutable lookup/presentation only:
no DB, Engine, reconstruction, solver/planner, Model C authentication or ZiNi
restart. Board selection alone manages the separate board-reference job.

## 8. Factual context and time authorities

Context contains exemplar/category, solver, displayed frame index/total actions,
selected action ordinal, reconstructed current status, recorded final outcome,
action type/target, previous target, dx/dy/d², post-hoc Model C action cost and
cumulative cost, inference category, exact target/minimum probabilities, persisted
candidate count, recorded safe reveal delta, explicit flag delta and reconstructed
new-safe-coordinate count. Missing facts remain **unavailable**. Retain nullable
compute diagnostics in original events; no frame-zero diagnostic is fabricated.

Both solvers' displayed costs are post-hoc frozen Model C evaluations of persisted
targets, not measured movement time. Stage 2 historically declared no Model C;
Stage 3 declared it at collection but these reduced events retain neither native
per-action modeled costs nor native cursor fields. Engine replay elapsed time,
historical compute diagnostics and Model C costs remain different authorities.
If compute is displayed, state S2 analysis versus S3 analysis+planning and differing
historical environments/scopes; infer no cross-stage compute-speed winner.

Stage-2 probability-guess candidate count is exact-minimum-risk tie multiplicity /
final selector pool size. Stage-3 count remains unavailable. Do not reconstruct
candidate geometry/counts, full probability maps, chosen plans, planner phases,
Replay timestamps or counterfactual alternatives. LOSS cost is cost through
termination, not time-to-win; no generic winner or causal good/bad judgment.

### 8.1 Source-checked board reference metrics

Initial Slice-0 source inspection checked these board semantics without executing
application code. Final qualification separately verified them at ff6358a. The
accepted additive public completed-Ops seam is specified in section 8.3; no
private counter access or shadow classification is authorized.

**Board Reference Metrics — answer-derived, not solver-visible.** After layout
authentication, reuse [`board_analyzer.analyze_board()`](../../board_analyzer.py)
on the exact finalized immutable board. KEEP static `total_3bv`, `total_ops` and
`isolated_number_count = total_3bv - total_ops`. Ops counts connected zero-cell
opening groups; 3BV adds isolated-number cells under the existing analyzer rules.
The same game has exactly the same static reference values for both solvers.

These are answer-derived board facts, not public observations, recorded decisions,
solver input, Model C time or causal explanations. Navigation and overlay cannot
alter them. Do not encode low-3BV implies OPEN-only, high-3BV implies FLAG+CHORD,
or any 3BV-based automatic explanation of a solver advantage. Human interpretation
owns those questions. Opening IDs, OPENING/BORDER/ISOLATED coloring and 3BV-region
overlays are deferred; omission loses local spatial illustration, not aggregates.

### 8.2 Solver action-space reference

[`run_simple()`](../../simple_runner.py) accepts only **OPEN / FLAG on HIDDEN
targets**. [`simple_algorithm`](../../simple_algorithm.py) and
[`simple_decision`](../../simple_decision.py) provide that decision boundary;
CHORD is not a selectable Stage-2 solver action. Surface this static note:
**Stage 2 action contract: OPEN / FLAG only — CHORD is not selected by this solver.**
Stage-2 CHORD=0 in these streams is structural, not evidence of evaluating and
rejecting CHORD. **Stage 3 recorded action space: OPEN / FLAG / CHORD.**

The note is unaffected by frame/overlay. Do not call Stage 3 better for using CHORD
or Stage 2 worse for its absence. Action-space differences versus ordering,
routing and board structure are questions for human interpretation.

### 8.3 Classic Counters and final reconstructed summary

The final 17-row structure is **Time (Model C), Est Time (Model C), 3BV,
3BV/s (Model C), Clicks, Left, Right, Chord, CPS (Model C), Efficiency, IOE,
Ops, Thrp, Corr, ZiNi, ZNE, ZNT**. Label:
**Reconstructed Counters — displayed frame; current Engine semantics**.
The initial final-run-only panel is superseded by the accepted usability revision.

A frozen counter entry is captured for every frame during the existing single
replay: status, raw total active/wasted clicks, completed 3BV and Ops, and
Clicks/Left/Right/Chord strings. `get_counter_snapshot()` exposes the additive
`completed_ops` field; existing keys retain their meanings. Public `get_stats()`
supplies PLAYING cumulative integer counts and terminal active+wasted formatting.
No private counter dictionaries or raw per-button classification are duplicated.
All elapsed-time/rate values from reconstruction are discarded.
`FinalCounterSummary` is retained unchanged as terminal compatibility surface;
last-frame entries reconcile with it. No mutable Engine escapes.

For displayed-frame `A=active`, `W=wasted`, `T=A+W`, `B=completed_3bv`:

| Row | Source | Presentation |
| --- | --- | --- |
| Clicks / Left / Right / Chord | Public Engine strings at this frame | PLAYING integer counts; terminal active+wasted with zero wasted omitted |
| 3BV / Ops | Completed over static total | Prefix progression, including partial LOSS |
| Efficiency | B/T | Integer percent |
| IOE | B/T | 4 decimals |
| Thrp | B/A | 4 decimals |
| Corr | A/T | 4 decimals |
| ZiNi | Successful bounded board reference Z | Numeric for either recorded final outcome |
| ZNE / ZNT | Z/T and Z/A | 4 decimals, recorded final WIN only |

Zero denominators and pending/failed references show `-`. A completed WIN stream
may show prefix ZNE/ZNT while its displayed frame is PLAYING; LOSS keeps both
unavailable. These are post-hoc mechanical/reference metrics, not strategy grades.
Automatic flags are not extra inputs. Active/wasted definitions and completed
3BV/Ops accounting remain the Engine's authority.

For prefix `C` Model C us, board total `TOTAL_B`, frame index `K`:
Time (Model C) = C/1000000 (3 decimals, Initial 0.000);
Est Time (Model C) = TOTAL_B*C/(B*1000000) (3 decimals, `-` if C or B is zero);
3BV/s (Model C) = B*1000000/C and CPS (Model C) = K*1000000/C (4 decimals,
`-` if C is zero). For C>0/B=0, modeled 3BV/s is 0.0000.
One pure prefix calculation supplies both Counters and Model C detail rows.
No historical elapsed clock is claimed or fabricated.

### 8.4 Model C physical-time authority and explicitly modeled rates

Frozen identity is `overlap_floor_log2_distance_v1`, unit microseconds (`us`).
The [frozen profile](../../calibration/stage3_physical_profile_v1.json) records the
conceptual calibration formula:

```text
T_us(dx,dy) = max(c_us, k_us * log2(1 + sqrt(dx*dx + dy*dy)))
c_us approximately 126004.7
k_us approximately 113948.2223
```

Those coefficients explain calibration only. Production/evaluation MUST use the
authenticated frozen integer **30 x 16** table through existing
[`stage3_physical.action_cost()`](../../stage3_physical.py) and
[`benchmark_modeled_time`](../../benchmark_modeled_time.py) seams:
`cost = timing_table_us[abs(dx)][abs(dy)]`. Never regenerate costs from coefficients.
Initial cursor `(0,0)`, first canonical OPEN, positive same-cell cost and the
terminal input all count. There is no action-type dimension: identical target
displacement has identical OPEN/FLAG/CHORD cost. V1 does not separately measure
the physical difficulty of those input types.

Model C describes physical execution of an already-selected/pre-presented target:
ordinary motor preparation, cursor movement, pooled LEFT/RIGHT button selection
and target press/input. It excludes board reading, safe/mine inference, probability
reasoning and strategic deliberation. It does not model hesitation, fatigue,
human mistakes or random cursor jitter; do not interpret this as a claim that
historical calibration measurements contained no human variability. It predicts
no actual trajectory, velocity or acceleration.

Stage 2 does not use Model C to choose actions. Stage-3 V1 uses the frozen table
and current target cursor in its speed-planning boundary (see
[`stage3_runner`](../../stage3_runner.py) / [`stage3_planner`](../../stage3_planner.py));
no planner is rerun by the viewer. Both displayed timelines are post-hoc evaluation
of persisted targets, because reduced official Stage-3 events do not retain native
per-action costs/cursor fields. Preserve historical model use versus displayed
reconstruction as distinct provenance.

KEEP a separate **Model C** tab:

| Field | Authority |
| --- | --- |
| Selected Action Model C Cost | Selected recorded action's exact authenticated cost; unavailable in Initial |
| Cumulative Model C Time | Prefix sum through the completed displayed frame; 0 initially |
| Current Modeled Est Time | Total 3BV extrapolated at the displayed prefix's modeled 3BV/s |
| Current Modeled 3BV/s / Current Modeled CPS | Completed 3BV / completed-frame Model C seconds; completed actions / those seconds |
| Final Model C Time | Full persisted-stream total |
| Final Modeled 3BV/s / Final Modeled CPS | Final completed 3BV / final modeled seconds; total actions / those seconds |
| Initial Model C cursor | Authenticated `(0,0)`, not a previous recorded action |

**displayed Model C seconds = integer microseconds / 1,000,000**.
Exact us remain authority. Detailed cumulative/final fields use integer
quotient/remainder conversion, e.g. `30355982 us (30.355982 s)`; no binary-floating
timing authority is introduced. Current estimates use six decimal seconds;
rates use four decimals. Formula inputs/availability are those in section 8.3.

The continuous playback playhead can lie between actions; it is separate from
completed-frame cumulative/Counter time. Final totals/rates remain constant on
navigation. WIN final estimate reconciles with final modeled total. On LOSS,
final cost is through termination; current estimate extrapolates from the prefix.
Neither is historical gameplay elapsed time, a predicted finish or time-to-win.
Decision compute, Replay time and reconstruction runtime remain separate.

### 8.5 ZiNi reference boundary

KEEP **answer-derived efficiency references** ZiNi/ZNE/ZNT, with the availability
rules above. Reuse the project's current Counters computation, not a new ZiNi
variant or Speff score. Current [`zini_metric_worker.calculate_counter_zini()`](../../zini_metric_worker.py)
uses [`calculate_g_zini_neighborhood_beam_bounded()`](../../zini_calculator.py).
The shared job's `ZINI_COUNTER_CONFIG` uses `standard_seeded_chain_v1`, 1000 maximum
evaluations, 500 standard-phase evaluations, seed 0 and no elapsed/stall cutoff,
with the existing remaining configuration defaults. This is a bounded heuristic
best-so-far reference, **not a proven minimum/optimum**. Preserve that semantics
and configuration; do not silently substitute another calculator or policy.

ZiNi is not a reconstruction dependency. Shared PyQt-independent
[`ZiniMetricJob`](../../zini_metric_job.py) owns the single Counter configuration,
source/frozen subprocess transport, token validation, nonblocking polling,
cancellation/termination/reaping and private-file cleanup. `ui_manager` and the
Viewer each own their own timer/presentation/eligibility policy; the worker owns
calculation. Source uses the worker script; frozen main dispatches
`--zini-metric-worker`. No algorithm/config semantics changed.

The Viewer starts one asynchronous job for the selected immutable board and
caches successful results in memory by board fingerprint/identity. Same-board
solver switches reuse the job/result. A different board cancels pending work
and starts its job or reuses a completed cache. Frame/playback/route/overlay changes
never manage that lifecycle. Close stops polling, cancels/reaps and cleans files.
Pending: `ZiNi: calculating...`; ready: bounded best-so-far board reference;
failure: unavailable. No Explorer or persistent/precomputed JSON artifact is added.

Stage-2/Stage-3 comparison is speed-focused; frozen Stage-3's objective is modeled
physical play time. Click efficiency can be a means toward speed, not the objective.
Closer-to-ZiNi or higher ZNE/ZNT is not automatically a better speed result: a run
may have lower click efficiency and lower Model C time. Human speed-oriented/
speff-style interpretation may recognize that tradeoff; the viewer generates no
score or adjudication. ZiNi references never become solver evidence, optimization
targets or automatic winner metrics. No ZiNi algorithm research is authorized.

### 8.6 Executed-target geometry and human cursor interpretation

KEEP previous/current target markers and a simple selected-action line/arrow from
the previous recorded target to the current one. Label it **Action-target
transition — not recorded cursor trajectory**. Expose exact signed dx/dy and
`d² = dx*dx + dy*dy`, plus exact selected Model C cost. Optional displayed Euclidean
cell distance is a presentation conversion; integer d² remains exact authority.

For the first action there is no previous recorded target and no fabricated arrow
from a prior action. The Model C origin `(0,0)` is separately identified; first
cost/displacement use that physical-model origin, not an invented action. Same-cell
targets have zero displacement but positive Model C cost; use target markers
without inventing a visible travel path. Geometry is unaffected by Before/After.

The arrow establishes consecutive-target geometry only, not an actual straight-line
cursor path, velocity, acceleration, pauses, overshoot or OS pointer movement.
The accepted cumulative **Action-target route — not recorded cursor trajectory**
is a separate default-OFF polyline through `actions[:displayed_frame]`. Initial
has no point; AFTER 1 has one point and no segment; BEFORE j excludes j. Repeated
same-target points are retained without invented detours or origin segments.
Main alpha 165/width 2.0 and white under-stroke alpha 100/width 3.5 keep it below
selected markers/transition and the synthetic cursor. Toggle is renderer-only.
Heat maps remain deferred; actual motion cannot be recovered from these events.

**Synthetic action-target cursor** is visible by default. It uses the accepted
Stage-3 Visualizer's straight cell-center geometry and smoothstep
`q=u*u*(3-2*u)`: quarter values 0.15625/0.84375, midpoint 0.5, exact endpoints.
Initial/BEFORE 1 uses the declared Model C cursor; AFTER j uses target j;
BEFORE j uses target j-1. The selected pending-target preview stays independent.
Index uses its configured interval as segment duration; Model C Time uses the
pending action's exact cost interval. Same-target actions remain stationary.
Partial motion never commits an action early or exposes it in the historical
route. Approximately 16 ms refresh updates cursor/slider/status only until a
boundary changes the completed frame. Pause/resume preserves partial progress.
This is synthetic smooth interpolation, not recorded mouse motion, OS trajectory,
Human Mouse Trace or calibrated physical acceleration. Traversing the whole
modeled action duration is presentation, not a measurement of movement-only time.
Model C costs remain unchanged.

External Minesweeper Online Replay/video may inform a HUMAN qualitative impression
of apparent speed or smoothness, efficient-looking progression or conspicuous
jumps. It supplies no authoritative numerical cursor-speed trace here. Do not
calibrate human-equivalent speed, fabricate an external pointer path, generate
route-quality labels or add annotation persistence for this purpose. Board state,
target geometry and modeled cost enable human interpretation without turning it
into an automated benchmark fact.

### 8.7 Final information grouping

| Area | Required contents and authority |
| --- | --- |
| Reference tab | Game/category, solver, static answer-derived 3BV/Ops/isolated totals and action-space note |
| Counters tab | 17 displayed-frame rows, explicit Model C time labels, async ZiNi status/reference |
| Model C tab | Selected/cumulative/current/final modeled facts; continuous playback status remains separate |
| Action tab | Displayed frame/selected ordinal, status/outcome, exact original event metadata and target geometry |
| Main board presentation | Public Before/After, terminal feedback, new-safe AFTER highlight, independent answer/route overlays, selected context and synthetic cursor |

Concise notes belong visibly to their group; detailed provenance is in tooltips.
The initial window is bounded by available screen geometry. Fact tabs prevent
unnecessary desktop global scrolling; per-area scroll fallback supports small
screens. Board cells remain public observations; overlays never change their
text, tooltip/accessibility or logical state. No generic performance score.

## 9. Minimum architecture

| Owner | Responsibility |
| --- | --- |
| Narrow authenticated evidence loader | DB/source/run/config admission, selected-only exact decoding, board generation/fingerprint gate and stability/provenance |
| Qt-independent immutable reconstruction model | Original validated GameRecord/events/TimelineAnalytics, authenticated board identity, N+1 immutable public frames and aligned frame counters, new-safe sets, static board references and retained final counter snapshot/presentation from existing public Engine seams; no ZiNi dependency |
| Thin standalone Qt viewer | One public board, separated reference/counter/Model C/action areas, independent positions/playheads, presentation playback/cursor/route, answer decoration and board-keyed shared ZiNi-job policy |
| Thin standalone launch entry point | Explicit evidence paths, load/validate before presentation, window lifetime; no dedicated packaged Viewer launcher |
| Shared PyQt-independent ZiNi job / calculation worker | One Counter config and subprocess/token/temp lifecycle reused by main and Viewer; worker computes, each UI owns its policy |

Retain enough immutable static answer information for the renderer-only overlay,
separate from normal public-frame access. Retain original models rather than
copying their metadata into a universal event hierarchy. Keep answer-derived board
references and reconstructed frame counters outside public observations and original
action metadata. Reconstruct once, capture aligned non-time counter entries and
the final compatibility summary through public APIs, then discard the Engine. All eight streams total
1516 frames including initial states, so bounded eager observations are sufficient.

No fake ReplayData, native Stage-3 trace/result wrapper or Replay clock. Existing
Replay/Same-board navigation and public rendering patterns may inform the UI;
their Human/native-execution ownership must not be imported. Do not call the
Timeline report's selection/collection/render pipeline to obtain viewer inputs.
Reuse public repository/model/validation seams and a minimal selected-only row
adapter. Exact module names are implementation details within these owners.

No universal event abstraction, solver registry, EventBus, analytics database or
generic mutable player/checkpoint/cache framework. Existing accepted production
modules are not refactoring targets merely to make this viewer more generic.

## 10. Slice plan and acceptance

| Slice | Scope | Current state |
| --- | --- | --- |
| 0 | Contract | COMPLETE / ACCEPTED by ChatGPT final review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0 |
| 1 | Qt-independent Pure Reconstruction | COMPLETE / ACCEPTED by ChatGPT final review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0 |
| 2 | Accepted-Evidence Loader | COMPLETE / ACCEPTED by ChatGPT final review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0 |
| 3 | Standalone Inspection UI | COMPLETE / ACCEPTED by ChatGPT final review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0 |
| 4 | Acceptance / Closeout | COMPLETE / ACCEPTED; qualified ff6358a; final PASS; R-2/O-5 CLOSED |

### Accepted Slice-1 implementation and verification

Historical initial-slice record: the later accepted additive frame-counter revision
extends this surface; final semantics are sections 8.3–9.

[`exemplar_board_reconstruction.py`](../../exemplar_board_reconstruction.py) and
[`tests/test_exemplar_board_reconstruction.py`](../../tests/test_exemplar_board_reconstruction.py)
are **COMPLETE / ACCEPTED by ChatGPT final review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
Reported verification: **32 new focused reconstruction + 28 timeline analytics +
27 Engine regression + 4 board analyzer + 9 Replay player = 100 PASS**;
**0 failures / 0 errors / 0 skips**. No full suite is claimed. This documentation
transition does not rerun verification.

The accepted Qt-independent boundary consumes an already-finalized `BoardSnapshot`
and already-validated `TimelineAnalytics`. It retains immutable N+1 public frames,
exact newly-revealed-safe coordinate sets, terminal Engine feedback, explicit FLAG
effects separated from automatic Engine effects, static 3BV/Ops/isolated references
and a final public Engine counter summary only. Original `TimelineAnalytics`
remains the Model C / geometry / metadata authority; no Engine is retained.
Slice 1 used bounded synthetic fixtures only: no DB/official exemplar inputs,
benchmark-board generation, Qt/UI, ZiNi, solver/planner execution or algorithm
research. Original authority boundaries remain; the final revision adds aligned
immutable counter entries without removing the final compatibility summary.

### Accepted Slice-2 implementation and verification

[`exemplar_board_evidence.py`](../../exemplar_board_evidence.py) and
[`tests/test_exemplar_board_evidence.py`](../../tests/test_exemplar_board_evidence.py)
are **COMPLETE / ACCEPTED by ChatGPT final review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
Reported verification: **34 new focused evidence-loader tests + 173 bounded
existing regressions = 207 PASS; 0 failures / 0 errors / 0 skips**.
No full suite is claimed. This documentation transition does not rerun tests or
the accepted bounded real-evidence smoke.

The accepted loader authenticates the exact two DB sources, owns the immutable
read-only lifecycle and requires exactly one accepted run per role. Fixed-four
admission and selected-only GameRecord/ActionEvent decoding preserve explicit
enum mappings, exact Fraction values, None and integer zero. Only admitted boards
are generated, with generated/persisted/fixed fingerprint equality. Frozen Model C
authentication, existing `project_timeline()` validation and accepted Slice-1
`reconstruct_board()` composition produce an immutable bundle; no live DB
connection or Engine is retained. No G4/HTML runtime input, selection/ranking,
arbitrary browsing, Qt/UI, ZiNi, solver/planner or algorithm research is included.

**Accepted bounded Slice-2 real-evidence smoke:** exact accepted Stage-2/Stage-3
hashes authenticated; exact accepted runs discovered; requested/processed/stored
counts **100000 / 100000 / 100000** per source and exact official coverage PASS.
Exactly **four boards** were generated and **eight selected streams** were
loaded/projected/reconstructed. All fixed fingerprints matched; all **1,508
persisted actions** reconciled with **0 status / 0 safe-reveal / 0 explicit-FLAG
mismatches**. Accepted action/outcome/Model-C totals matched. Source hashes,
sizes and mtimes were unchanged after close; no sidecars or output artifacts.
No solver/planner, selection, G4 or report rerun occurred. This is accepted
Slice-2 implementation evidence, **not final viewer closeout**.

### Accepted Slice-3 implementation and verification

**Historical first-version acceptance.** Its direct Frame entry, final-only Counters,
ZiNi defer and manual-only presentation below were **SUPERSEDED BY ACCEPTED USABILITY
REVISION** at 29af53b. Current behavior is specified in sections 7–9 and 11.

**Slice 3 — Standalone Inspection UI COMPLETE / ACCEPTED by ChatGPT final review;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.** Accepted implementation:
[`exemplar_board_viewer_ui.py`](../../exemplar_board_viewer_ui.py),
[`scripts/exemplar_board_viewer.py`](../../scripts/exemplar_board_viewer.py) and
[`tests/test_exemplar_board_viewer_ui.py`](../../tests/test_exemplar_board_viewer_ui.py).

Reported verification: **33 viewer UI + 4 launcher + 34 accepted evidence-loader +
32 accepted reconstruction + 6 selected Stage-3 visualizer rendering + 5 selected
ZiNi Explorer rendering + 2 adapted unchanged Same-board navigation assertions =
116 PASS; 0 failures / 0 errors / 0 skips**. The two Same-board assertions ran
unchanged with hand-recorded synthetic setup replacing solver-producing setup.
No full-suite claim. This documentation transition does not rerun verification.

**Accepted bounded Slice-3 real-evidence offscreen smoke:** exact accepted Stage-2 /
Stage-3 sources loaded through the Slice-2 API; **2 DB opens during initial load
only, 4 board generations, 8 selected-action streams, 8 timeline projections and
8 reconstructions**. All eight game/solver pairs were inspected at initial,
middle and final states. Before/After, Answer Overlay ON/OFF, first-action
presentation and LOSS terminal rendering were exercised; same-target and
long-transition presentation were checked where present. After initial load,
navigation/selection/toggles caused **0 DB opens / 0 board generations / 0 Engine
reconstructions / 0 timeline projections / 0 solver/planner/selection calls**.
Source hashes/sizes/mtimes remained unchanged; no sidecars or output artifacts.
This is accepted Slice-3 evidence, **not final native/manual acceptance**.

The accepted standalone Qt UI and explicit accepted-loader-based launcher retain
one board, four fixed exemplar choices, Stage-2/Stage-3 selection and eight
independently remembered inspection positions. First/Previous/Next/Last, integer
frame slider, direct frame/action entry and Before/After use immutable lookups.
Default-OFF HIDDEN-only Answer Overlay, exact terminal Engine feedback, new-safe
AFTER-only highlighting and recorded previous/current target geometry remain
separate; there is no fabricated first-action origin path.

In this historical first version, the 17-row Counters panel left historical
Time / Est Time / 3BV/s / CPS unavailable and used final-run ratio facts. ZiNi /
ZNE / ZNT rows were retained with calculation DEFERRED because no public shared
job owner existed then. These dispositions are superseded by the accepted
frame-counter/Model C/shared-ZiNi revision described above. Only immediate reference
numbers were omitted then. Model C had its own group; Action Context preserved
exact persisted facts. That initial slice included no autoplay/timer/modeled animation or shared
main-app job extraction. Its no-domain-work-on-navigation boundary remains;
playback and shared ZiNi ownership were added by the accepted usability revision.
Common playheads, normalized progress, selection/ranking and algorithm research
remain excluded.
The original evidence/reconstruction authority boundaries remain preserved; UI
and counter presentation were subsequently extended under explicit user approval.

### Independent pre-closeout audit and accepted R-1 correction

Claude Code independently audited committed Slice-3 candidate
`d338dcffa212e52efb23af9d9db41841348ade96` (`feat: add exemplar board inspection viewer`).
Verdict: **INDEPENDENT AUDIT CONDITIONAL — BLOCKER 0 / REQUIRED 2**.

**R-1 SATISFIED — ChatGPT final correction review PASS / ACCEPTED.** The
`QSpinBox.editingFinished` focus-loss signal could reinterpret a mirrored entry
value as navigation. Historical correction commit `2c9ba42fb394ee528a035a85c3a2c8146b86a7f9`
(`fix: prevent exemplar viewer focus-loss navigation`) changed only
`exemplar_board_viewer_ui.py` and `tests/test_exemplar_board_viewer_ui.py`.
Ordinary focus loss and Tab no longer navigate; initial mode and BEFORE positions
survive focus changes. Return/Enter commits explicitly exactly once; Go buttons
use the same helpers. `_Position` remains the navigation authority.

Reported correction verification: **45 tests.test_exemplar_board_viewer_ui +
32 tests.test_exemplar_board_reconstruction + 34 tests.test_exemplar_board_evidence
= 111 PASS; 0 failures / 0 errors / 0 skips**. No full suite is claimed or rerun
by this documentation refresh. **No REQUIRED production correction remains.**

**R-2 CLOSED** by fresh qualification at
`ff6358ae62b6f343bda36069d7164bda9aebee74` and this closeout's exact lineage.
Earlier precommit Slice-3 evidence remains historical, not retroactively qualified.
Audit O-1/O-2/O-6 SATISFIED; O-3/O-4 DEFER; **O-5 CLOSED**:
displayed Model C seconds = integer microseconds / 1,000,000.
O-7/O-8 NO CHANGE. No Claude re-audit after R-1 is required or claimed.
Final Slice-4 verification and user-native attribution are recorded in the
[closeout](STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md).

### Pure tests

Use bounded synthetic fixtures for fixed-board reconstruction, frame 0/n,
before/after, OPEN/FLAG/CHORD, terminal LOSS and full terminal public symbols.
Check exact new-safe coordinates, recorded reveal/explicit-FLAG reconciliation,
automatic WIN flags, flood clearing and losing CHORD continuation. Reject malformed,
post-terminal and incomplete streams before publishing; prove immutable nested
outputs and preservation of original metadata. No solver/planner calls.

Check static 3BV/Ops against existing analyzer semantics, isolated count as their
difference, identical board references for both solvers and exclusion from public
observations/action metadata. Final counter totals/presentation must match direct
current-Engine replay through public seams: active/wasted, Left/Right/Chord and
completed/total 3BV/Ops. No private-counter read or duplicated classification.
Verify that reconstructed counters carry their provenance rather than causal labels;
Slice-1 imports/execution must not depend on any ZiNi calculation.

### Evidence tests

Use synthetic temporary evidence for ordinary tests: fixed-four admission, exact
source/hash/run/config identity, deterministic generation, fingerprint mismatch
fail-closed, selected-only detail reads, exact enum/Fraction/None/zero decoding,
immutable read-only opening, no mutation/sidecars and closed connections.
Verify wrong-role/wrong-config/missing or ambiguous runs fail; no re-selection,
solver/planner calls or arbitrary-game layout generation.

Check exact authenticated Model C lookup, consecutive target chain and separately
labeled first origin `(0,0)`, positive same-cell cost, exact prefix/final totals,
and exact dx/dy/d². No cursor trajectory object or previous action at ordinal zero.

### Qt tests and final acceptance

Final qualification covered complete Viewer tests plus real immutable-bundle
offscreen checks: independent positions/playheads, explicit Action entry,
Before/After, direct slider seek/drag, overlay/terminal feedback, completed-route
membership, smoothstep endpoints/quarter points, same-target motion, both playback
modes, pause/resume/re-anchor/catch-up, Max interval clamp/width and desktop/small
layout. Partial cursor progress performs no board/counter refresh or domain work.
ZiNi lifecycle/cache/zero-denominator/WIN-only ratio policies use bounded fakes
in UI tests and separate real tiny-board worker tests. No Expert ZiNi result is
claimed by the real-bundle fake-receipt policy probe.

**Final Slice 4 COMPLETE / ACCEPTED at ff6358a.** Fresh 892/892 focused and
2390/2390 full source PASS, zero failures/errors/skips; real 4-board/8-stream/
1508-action proof with all mismatch categories zero; exact source preservation;
package regression and USER native source-GUI acceptance all passed. The package
gate was required by the accepted main/shared-worker changes, superseding the
initial no-package assumption. Build environment: 2365 PASS + 25 individually
documented optional image/video skips, zero failures/errors; build 77.012 s.
No official 100k/selection/report rerun or final holdout use occurred.

See [final closeout](STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md) for exact commands,
SHA-256 identities, eight-run reconciliation, historical HOLD/repair lineage,
package versus user-native attribution and remaining work. This documentation
closeout itself reruns no tests, DB proof, package build or search.

## 11. KEEP / DEFER / REJECT

Final dispositions below supersede the initial first-version manual-only design.
Autoplay/full route/model-time animation deferrals or rejection are historical,
**SUPERSEDED BY ACCEPTED USABILITY REVISION**; they are not current prohibitions.

| Element | Disposition | Reason and loss if omitted |
| --- | --- | --- |
| Fixed four exemplars; fingerprint gate | KEEP | Required admission/identity; omission would lose trusted board correspondence |
| Independent indices; direct ordinal/index navigation | KEEP | Required inspection without unsupported cross-run mapping |
| Public before/after; terminal Engine feedback | KEEP | Required actual progression, effects and final-state interpretation |
| Answer Overlay default OFF; hidden answers only in overlay | KEEP | Explicit reference mode with public authority preserved |
| Immutable frames | KEEP | Reconstruction once makes inspection deterministic; omission loses stable lookup-only navigation |
| Static 3BV/Ops/isolated reference | KEEP | Human board-structure context; omission loses aggregate reference facts |
| Stage-2 OPEN/FLAG-only action-space note | KEEP | Explains the structural CHORD boundary without judging it |
| Full 17 Counters; immutable displayed-frame values | KEEP | Prefix 3BV/Ops/clicks/ratios, explicit Model C time labels and board ZiNi; final summary compatibility retained |
| Explicit Model C fields and modeled rates | KEEP | Separates physical-model cost from historical elapsed time; omission loses labeled time/rate context |
| ZiNi as efficiency reference when available | KEEP | Existing answer-derived reference, outside pure reconstruction; omission loses click-efficiency context, not a speed verdict |
| Selected action-target transition; dx/dy/d² | KEEP | Exact target geometry helps human inspection without inventing a cursor trace |
| Independent side-by-side panels | DEFER | One board needs less ownership/UI; omission loses simultaneous comparison convenience |
| Index and Model C Time playback | KEEP — supersedes Autoplay DEFER | Independent presentation only; explicit interval/speed, exact boundaries and partial pause/resume |
| Annotations/bookmarks | DEFER | No persistence framework needed; loses saved commentary/positions |
| Jump-to-range framework | DEFER | Direct ordinal entry suffices; loses one-click named-range navigation |
| Export/screenshots | DEFER | No output/sharing contract needed; loses integrated capture/export |
| Opening IDs, OPENING/BORDER/ISOLATED colors, 3BV-region overlays | DEFER | Aggregates suffice initially; loses local structural visualization convenience, not board reference totals |
| Cumulative completed action-target route | KEEP — supersedes recent/full-run route DEFER | Default OFF; no future targets, invented origin or recorded-mouse claim |
| Movement heat maps | DEFER | No aggregation/rendering policy needed now; loses a spatial frequency overview |
| Exact external replay cursor-speed measurement; velocity/acceleration/easing reconstruction | DEFER | Current inputs lack an authoritative motion trace; loses numerical external-motion comparison, requiring separately scoped new evidence |
| Full probability maps | DEFER | Not persisted; omission loses spatial risk inspection, not available evidence |
| Stage-3 chosen-plan display | DEFER | Not persisted; omission loses plan inspection; never fabricate historical plans |
| Stage-3 candidate geometry/count | DEFER | Not persisted; omission loses alternative-pool inspection; no reconstruction authorized |
| Synchronized side-by-side, common playhead/index mapping | REJECT | No state-alignment authority; omission loses only synchronized navigation convenience |
| Normalized progress | REJECT | Would imply unsupported progress equivalence; loses percentage-based cross-run navigation |
| Model C Time and synthetic smooth cursor | KEEP — supersedes first-version animation REJECT | Integer-us timing unchanged; smoothstep is presentation only, not actual trajectory |
| Fabricated actual cursor trajectory | REJECT | Targets are not sampled motion; loses only an unsupported path reconstruction |
| Fabricated historical elapsed time | REJECT | No historical clock exists; populated time/rate rows explicitly say Model C |
| Human trace overlay | REJECT | No Human input authority here; loses unrelated Human comparison |
| Counterfactual nearest-risk visualization | REJECT | Requires other evidence/experiment scope; loses hypothetical alternative comparison |
| Causal good/bad labels | REJECT | Unsupported by replay; omission leaves interpretation to the human |
| Automatic route-quality judgment | REJECT | Geometry alone proves no optimality/avoidability; omission leaves qualitative route assessment to the human |
| ZiNi-as-speed-winner judgment | REJECT | Click efficiency is not physical time; omission loses an unsupported automatic verdict |
| Fake Replay/native trace wrappers | REJECT | Would invent authority; loses existing wrapper/control convenience only |
| Generic cache/checkpoint framework | REJECT | Bounded immutable frames suffice; loses scaling optimization for unadmitted long runs |
| Reconstruction runtime as historical timing evidence | REJECT | Engine perf_counter measures reconstruction, not solver play; loses misleading time/rate reuse |

Deferred unavailable evidence needs a separate acquisition/specification decision,
not merely UI work. None of these dispositions authorizes algorithm research.

## 12. Accepted discovery evidence only

The preceding accepted read-only proof used Python 3.12.10, 64-bit, generated ONLY
the four admitted boards and replayed eight selected streams. Exact fingerprints
matched both persisted sources before replay:

| Game / seed | Matched fingerprint |
| ---: | --- |
| 73758 | `7fe223012a42cdfb32ca5a493097920cd192b74869a58f1a008dc7e1efbc7f2d` |
| 73024 | `4c3d414489f684c83fb7358c5a479e797493ad456b8ae12f8e4b7b44b6bcf8d8` |
| 93557 | `22d9a199f0e1839ecdcc5be84b8054abe366be7b85b770b440be8484887ae2c3` |
| 1 | `007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e` |

Values below are Stage 2 / Stage 3; modeled totals are accepted Timeline reference
facts also reconciled by discovery, not fresh G4 acceptance by a Viewer session.

| Game | Actions | Safe reveals | Explicit FLAG sum | Outcome | Model C us |
| ---: | --- | --- | --- | --- | --- |
| 73758 | 320 / 177 | 381 / 381 | 99 / 76 | WIN / WIN | 57365067 / 30355982 |
| 73024 | 313 / 207 | 381 / 381 | 98 / 98 | WIN / WIN | 53655374 / 37168019 |
| 93557 | 279 / 204 | 381 / 381 | 98 / 98 | WIN / WIN | 47034727 / 39157214 |
| 1 | 4 / 4 | 5 / 5 | 1 / 1 | LOSS / LOSS | 720354 / 720354; termination only |

Across all 8 streams / **1508 persisted actions**: **status mismatch 0,
safe-reveal mismatch 0, explicit-FLAG mismatch 0**; terminal exactly at the final
persisted event; no solver/planner/runner calls. Official artifacts remained
unchanged and no sidecars appeared. These are **discovery feasibility evidence,
not implementation acceptance**. No proof, DB access or board regeneration is
performed as part of Slice 0 drafting.

## 13. Preservation and next boundary

Viewer **FINAL ACCEPTANCE PASS / CLOSED; Slices 0–4 COMPLETE / ACCEPTED**.
Preserve exact qualified source/evidence identities in the
[closeout](STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md), frozen Stage-3 V1 / Model C,
official 100k, Timeline/Same-board closeouts, ZiNi Improvement and unopened holdout.
No DB reads outside the accepted loader; no regeneration/reconstruction or search
on navigation. No selection/ranking, arbitrary browsing, synchronized common
playhead, normalized progress, fabricated historical time/trajectory or automatic
strategy judgment. No algorithm policy was adopted.

**NEXT REQUIRED: Visualization Usability Polish**, as detailed in the
[closeout queue](STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md#limitations-and-mandatory-next-work).
Same-board selected-run direct seek/playback, route and synthetic cursor preserve
actual Human Replay/Mouse Trace versus Model C authority. Stage-3 Visualizer gains
completed-target cumulative route while retaining its existing direct seek.
These are separate maintenance tasks on closed surfaces. After polish comes
fixed-exemplar human/domain interpretation, then a separately scoped algorithm
research decision. Stage-3 Extended remains ACTIVE.

See the [current handoff](../CURRENT_HANDOFF.md#4-current-milestone) and
[Extended roadmap](README.md#roadmap). Historical closeouts retain their own dated
boundaries and acceptance identities.
