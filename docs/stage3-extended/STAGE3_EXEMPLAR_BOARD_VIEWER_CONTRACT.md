# Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer — Contract

Status: **ACTIVE — Slices 0–3 FINAL PASS — COMPLETE / ACCEPTED by ChatGPT final review.**
Each slice: **BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.** Date: **2026-10-18 (Asia/Seoul)**.
**CURRENT / AUTHORIZED — Slice 4: Acceptance / Closeout.**
Acceptance work is **NOT YET BEGUN** at this documentation transition.
The preceding read-only discovery is **COMPLETE / ACCEPTED** by ChatGPT:
**STAGE-3 EXTENDED — SELECTED EXEMPLAR BOARD-STATE VIEWER DISCOVERY PASS;
BLOCKER 0 / REQUIRED 0**. Discovery and contract acceptance remain distinct from
the separately accepted Slice-1, Slice-2 and Slice-3 implementations below. This
turn records the status transition only and does not perform Slice-4 acceptance.

Live Git verified for this transition: branch `feature/stage3-exemplar-board-viewer`,
HEAD `35069307ce34b53f8e42a850e29ee810ccd4a1a7`
(`feat: add accepted exemplar board evidence loader`); main baseline
`50a8fee544ed6779dbcd7dd2fbb422c07cce59de`. These are dated recovery facts;
live Git remains authoritative for current branch/HEAD. Accepted Slice-3 source,
launcher and tests are untracked at this transition; no Slice-3 commit identity is assigned.

Stage-3 Extended remains **ACTIVE**. [Timeline Analytics](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)
remains **FINAL ACCEPTANCE PASS / CLOSED**, with its qualified implementation
identity `4c488e033dd045f1c203ff500d824cfaffb7cc67` unchanged. This is a separate
interpretation-viewer scope, not a reopening of the closed Timeline contract.

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
are the exemplar admission authority; the future loader must preserve them.

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
label. Reconstructed final counters are also allowed under current Engine
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
appear in the separately labeled final summary below; their mechanical names are
not strategic judgments. Reconstructed Engine elapsed time and rewards are not
historical solver measurements. No reconstruction timing fills historical Time,
Est Time, 3BV/s or CPS rows.

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

## 7. UI ownership and navigation

First version: ONE board, fixed exemplar selector and Stage 2 / Stage 3 selector.
Keep an independent remembered position for every `(game, solver)` pair; switching
restores that pair without seeking or clamping another pair. No shared playhead,
index mapping, normalized progress or synchronized side-by-side display.

Keep First / Previous / Next / Last, integer action-index slider, direct integer
ordinal/index entry, explicit Before / After inspection and Answer Overlay
checkbox. Reject bool/noninteger/out-of-range entry. Independent side-by-side
panels and autoplay are deferred; no playback timer or modeled-time animation in V1.

Navigation must explicitly distinguish selected action ordinal `j` from displayed
frame `k`. Ordinary frame navigation selects `k` in `0..N`, shows After and, for
`k>0`, selects action `j=k`. First selects initial frame 0 with no selected action.
Before/After for selected `j` displays frame `j-1` / `j` without applying any input;
labels show both numbers. Direct action selection admits `j` in `1..N` and starts
in After. Buttons/slider follow completed-frame indices, never a percentage axis.
Remember the selected action/view side (or initial mode); derive the displayed
frame from that state rather than maintaining a second mutable index authority.

At frame 0 there is no applied action/decision/risk/compute metadata. If Before
action 1 is selected, its original action metadata may appear only as explicitly
labeled **selected recorded action 1 (not yet applied)**; it must not be attributed
to frame 0. Initial mode has no selected-action metadata. Cumulative cost follows
the displayed frame; selected action cost is separately labeled. Navigation and
overlay toggles are pure presentation/lookups, with no Engine or DB execution.
Static board references and the explicitly labeled FINAL run summary may remain
visible while inspecting any frame, including 0; they are not facts about actions
already applied at that frame. They do not change when navigation/overlay changes.

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

These semantics were checked by source inspection on 2026-10-18, without running
application code, tests, Discovery, board generation or official-evidence reads. Authority is
current source before tests, executable evidence, accepted specifications/records,
documentation and AI interpretation. No formula conflict was found; the public
raw-counter API limit below is an explicit implementation boundary.

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

KEEP the full familiar row set from [`ui_manager.STAT_ROWS`](../../ui_manager.py):
**Time, Est Time, 3BV, 3BV/s, Clicks, Left, Right, Chord, CPS, Efficiency, IOE,
Ops, Thrp, Corr, ZiNi, ZNE, ZNT.** A row's existence does not grant a value.

Label the nonhistorical execution summary **Reconstructed Counters — current
Engine semantics; FINAL RUN SUMMARY**. Capture it once after complete validated
replay. These values are not persisted benchmark telemetry fields. They stay fixed
while browsing earlier frames; no new per-frame interpretation of final Counters
is introduced. Mechanical active/wasted classification is not a claim that an
action was strategically good/bad. Some classification uses the known answer
(for example, a FLAG on an actual mine), so it is reconstruction/reference evidence,
not solver-visible information.

Reuse [`MinesweeperEngine`](../../core_engine.py)'s public seams:

- `get_counter_snapshot()` supplies status, raw total active clicks, raw total
  wasted clicks and completed/effective 3BV.
- Terminal `get_stats()` supplies exact final Clicks/Left/Right/Chord formatting:
  `active + wasted`, omitting `+ wasted` when wasted is zero. It also supplies
  completed/total 3BV and completed/total Ops. Preserve those final-state strings.
- The public snapshot currently does **not** expose raw per-button active/wasted
  breakdowns or raw completed Ops. Static totals are available from BoardAnalysis;
  final Ops and per-button presentation are available from `get_stats()`. Do not
  read private Engine attributes, recreate counter classification, or parse
  formatted strings into a replacement raw-counter authority. If implementation
  truly needs additional raw values, report the need for a narrow public seam
  before widening source scope. Slice 0 authorizes no such API change.
- Read only the non-time fields needed from `get_stats()`; its replay-generated
  elapsed-time/rate values must not escape into the viewer's historical rows.

Engine handlers classify each valid input once. A mine-hit OPEN is active; CHORD
classification uses the Engine's actual reveal-change rule, not a newly invented
productivity rule. Automatic flags are not extra clicks. Preserve current Engine
definitions, including completed 3BV/Ops accounting, without shadow logic.

Let `A = active_clicks`, `W = wasted_clicks`, `T = A + W`,
`B = completed_3bv`, and `Z = available board ZiNi`. The verified current
`_counter_metric_values()` / formatting semantics are:

| Row | Exact ratio/source | Existing presentation and availability |
| --- | --- | --- |
| Clicks / Left / Right / Chord | Engine final statistics | Active + wasted, zero wasted omitted |
| 3BV / Ops | Engine completed/effective over total | Completed/total, including LOSS partial completion |
| Efficiency | B / T | Percentage, 0 decimal places |
| IOE | B / T | Decimal, 4 places |
| Thrp | B / A | Decimal, 4 places |
| Corr | A / T | Decimal, 4 places |
| ZiNi | Z from existing bounded reference path | Integer when available, WON or LOST |
| ZNE | Z / T | Decimal, 4 places; WON with available Z only |
| ZNT | Z / A | Decimal, 4 places; WON with available Z only |

Ratio denominator zero displays `-`, not zero or infinity. The current application
masks the seven Efficiency/IOE/Thrp/Corr/ZiNi/ZNE/ZNT metrics during PLAYING; here
the panel explicitly describes the already-completed run, independently of the
displayed historical frame. On LOSS, Efficiency/IOE/Thrp/Corr and available ZiNi
remain defined by the rules above, but **ZNE and ZNT remain unavailable**. A missing,
pending or failed ZiNi result remains unavailable. Match the existing formatting
without instantiating a main-app window or duplicating Engine counter logic.

**Historical elapsed time unavailable:** Time, Est Time, 3BV/s and CPS retain
unavailable markers (`—` or the existing `-`). ActionEvents provide no authoritative
historical gameplay clock. Engine `perf_counter` during reconstruction is not that
clock. Neither Model C nor decision compute may fill those ordinary rows.

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

KEEP a separate **Model C** group with these explicit names:

| Field | Authority |
| --- | --- |
| Selected Action Model C Cost | Exact table cost of the selected recorded action; unavailable in initial mode |
| Cumulative Model C Time | Exact prefix sum through the displayed completed frame; 0 at frame 0 |
| Final Model C Time | Exact full persisted-stream total |
| Modeled 3BV/s | Final reconstructed completed_3bv / final Model C seconds |
| Modeled CPS | Persisted semantic action count / final Model C seconds |

Retain integer microseconds and exact ratio inputs; decimal rendering is
presentation only. For example, `30,355,982 us = 30.355982 s`. The rates can be
represented as `B * 1000000 / final_us` and `N * 1000000 / final_us`; never use
reconstruction runtime as denominator. Final rates/total remain constant during
navigation. They are not measured Human rates, Minesweeper Online elapsed-time
statistics, Replay elapsed time or CPU decision speed. Do not invent a modeled
Est Time. On LOSS, final modeled time and these descriptive rates cover only the
terminated prefix, never time-to-win or an extrapolated winning result.

### 8.5 ZiNi reference boundary

KEEP **answer-derived efficiency references** ZiNi/ZNE/ZNT, with the availability
rules above. Reuse the project's current Counters computation, not a new ZiNi
variant or Speff score. Current [`zini_metric_worker.calculate_counter_zini()`](../../zini_metric_worker.py)
uses [`calculate_g_zini_neighborhood_beam_bounded()`](../../zini_calculator.py).
The UI's current `ZINI_COUNTER_CONFIG` uses `standard_seeded_chain_v1`, 1000 maximum
evaluations, 500 standard-phase evaluations, seed 0 and no elapsed/stall cutoff,
with the existing remaining configuration defaults. This is a bounded heuristic
best-so-far reference, **not a proven minimum/optimum**. Preserve that semantics
and configuration; do not silently substitute another calculator or policy.

ZiNi is not a Slice-1 reconstruction dependency. A later UI/reference owner may
use the existing bounded worker/calculator seam on the authenticated immutable
board, retaining one board reference for both solvers. No Explorer model/controller/
trace dependency is needed. Reference-job lifecycle is separate from replay and
navigation; slider/Before/After/overlay changes do not start calculation. A worker
completion poll, if needed, is not a playback timer or autoplay. Missing/failing
calculation leaves unavailable rows and does not change accepted replay facts.

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
Full-run paths, recent trails and heat maps are deferred to avoid clutter; numerical
cursor velocity/easing/acceleration cannot be recovered from these events.

External Minesweeper Online Replay/video may inform a HUMAN qualitative impression
of apparent speed or smoothness, efficient-looking progression or conspicuous
jumps. It supplies no authoritative numerical cursor-speed trace here. Do not
calibrate human-equivalent speed, fabricate an external pointer path, generate
route-quality labels or add annotation persistence for this purpose. Board state,
target geometry and modeled cost enable human interpretation without turning it
into an automated benchmark fact.

### 8.7 First-version information grouping

| Area | Required contents and authority |
| --- | --- |
| Board / Solver Reference | Game/category, solver, answer-derived total 3BV/Ops/isolated count, static action-space note and available ZiNi reference |
| Classic Counters / Final Run Summary | All 17 familiar rows; reconstructed final counters labeled; historical Time/Est Time/3BV/s/CPS unavailable; ZiNi availability preserved |
| Model C | Selected action cost, cumulative and final modeled time, Modeled 3BV/s and Modeled CPS, explicitly distinct from historical time |
| Action Context | Displayed frame/selected ordinal, current status/final outcome, action/target/previous target, dx/dy/d², stored inference/probabilities/candidate count, reveal/explicit flag deltas and reconstructed new-safe count |
| Board Presentation | Public Before/After, target markers/transition, new-safe highlight, optional HIDDEN-only Answer Overlay and genuine terminal feedback |

Keep these authorities separate; never collapse them into a generic performance
score. Answer-derived references remain separately labeled even while overlay is
OFF; OFF removes hidden-cell decorations, not the explicitly identified reference
panel. The Public View board itself remains exactly the public observation.

## 9. Minimum architecture

| Owner | Responsibility |
| --- | --- |
| Narrow authenticated evidence loader | DB/source/run/config admission, selected-only exact decoding, board generation/fingerprint gate and stability/provenance |
| Qt-independent immutable reconstruction model | Original validated GameRecord/events/TimelineAnalytics, authenticated board identity, N+1 immutable public frames, new-safe sets, static board references and final counter snapshot/presentation from existing public Engine seams; no ZiNi dependency |
| Thin standalone Qt viewer | One public board, separated reference/counter/Model C/action areas, independent remembered positions, target transition and answer decoration; separate existing ZiNi reference-job lifecycle if used |
| Thin standalone launch entry point, if required | Explicit evidence paths, load/validate before presentation, window lifetime; no main-app/package integration implied |

Retain enough immutable static answer information for the renderer-only overlay,
separate from normal public-frame access. Retain original models rather than
copying their metadata into a universal event hierarchy. Keep answer-derived board
references and reconstructed final counters outside public observations and original
action metadata. Reconstruct once, capture the final non-time summary through
public APIs and discard the mutable Engine before presentation. All eight streams total
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
| 4 | Acceptance / Closeout | CURRENT / AUTHORIZED; acceptance work NOT YET BEGUN at this transition |

### Accepted Slice-1 implementation and verification

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
research. These accepted implementation and contract semantics remain unchanged.

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

The full 17-row classic Counters panel retains unavailable historical Time /
Est Time / 3BV/s / CPS, with Efficiency / IOE / Thrp / Corr from accepted final
facts. **ZiNi / ZNE / ZNT rows are retained; calculation is explicitly DEFERRED**:
no narrow public reusable job owner exists, and copying the private main-UI
lifecycle is outside this optional reference scope. Only immediate reference
numbers are omitted. Model C has its own group; Action Context preserves exact
persisted facts. No DB/Engine/reconstruction work during navigation, autoplay,
timer, modeled animation, shared/common playhead, normalized progress,
solver/planner/selection/ranking, algorithm research or main-app integration.
Slices 0–3 technical semantics remain frozen.

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

### Qt tests

Offscreen Qt tests cover independent remembered positions for all game/solver
pairs, Before/After/frame labels, direct navigation and boundaries, default-OFF
overlay, HIDDEN-only decoration, OFF exact public rendering and unchanged flags,
revealed/terminal cells. Check no click-to-play, unavailable labels and no playback
timer/autoplay. Navigation/toggle must perform no Engine, DB, solver or planner work;
answer content must never enter public observation or recorded decision metadata.

Verify the full Counters row set, FINAL RUN SUMMARY labeling and exact existing
Efficiency/IOE/Thrp/Corr formulas, rounding and denominator-zero behavior. Current
ZiNi semantics/configuration and WON/LOSS availability must be unchanged: available
ZiNi for either terminal outcome, ZNE/ZNT only on WON; unavailable values never
become zero. Use bounded synthetic/stub reference results for UI tests; no official
board computation is an ordinary unit-test fixture. ZiNi never enters reconstruction,
solver evidence or speed-winner labels; job completion cannot change replay frames.

Test navigation/overlay invariance of board references, final summary, static
OPEN/FLAG-only Stage-2 policy note and final modeled rates. No UI quality conclusion
follows CHORD absence or mechanical wasted counts. Verify Model C seconds/rates
derive only from exact integer time and final numerator facts: no reconstruction
elapsed time in either historical or modeled fields, no modeled Est Time, LOSS
through-termination wording, selected-versus-cumulative/frame labels, and optional
distance conversion as presentation only. Arrow/markers must match original targets,
change no model state and never be labeled actual cursor trajectory.

### Final acceptance

After implementation is separately authorized, repeat a bounded real proof for
ONLY the four fixed cases: exact fingerprints, all 1508 actions, zero status/
safe-reveal/explicit-FLAG mismatches, terminal exactly at the final event and exact
outcomes/counts/selected modeled totals. Preserve source hashes/sizes/mtimes and
sidecar absence. No official 100k rerun, solver evidence generation or Timeline
report regeneration. Focused regression is required for affected boundaries;
final source regression scope is determined at closeout without substituting
discovery results for implementation tests.

Record static total 3BV, total Ops and isolated-number count for each fixed board,
and ZiNi if the existing reference path is available in V1. For each solver/run
record action count; final Left/Right/Chord presentation; raw total active/wasted
counts; completed/total 3BV and Ops; Efficiency, IOE, Thrp, Corr; ZNE/ZNT where
defined; exact final Model C us and displayed seconds; Modeled 3BV/s and Modeled
CPS. Respect the public raw-breakdown boundary in section 8.3. No new numerical
board/counter/ZiNi results are claimed by this documentation correction. This future
table is not an algorithm-winner adjudication; human interpretation follows acceptance.

Offscreen Qt is sufficient for functional implementation-slice checks. A bounded
presentation inspection should assess glyph readability, opacity and clipping.
No package/native GUI gate is assumed unless later integration changes the
packaged/main-app surface; such integration requires separate scope approval.

## 11. KEEP / DEFER / REJECT

| Element | Disposition | Reason and loss if omitted |
| --- | --- | --- |
| Fixed four exemplars; fingerprint gate | KEEP | Required admission/identity; omission would lose trusted board correspondence |
| Independent indices; direct ordinal/index navigation | KEEP | Required inspection without unsupported cross-run mapping |
| Public before/after; terminal Engine feedback | KEEP | Required actual progression, effects and final-state interpretation |
| Answer Overlay default OFF; hidden answers only in overlay | KEEP | Explicit reference mode with public authority preserved |
| Immutable frames | KEEP | Reconstruction once makes inspection deterministic; omission loses stable lookup-only navigation |
| Static 3BV/Ops/isolated reference | KEEP | Human board-structure context; omission loses aggregate reference facts |
| Stage-2 OPEN/FLAG-only action-space note | KEEP | Explains the structural CHORD boundary without judging it |
| Full classic Counters rows; final reconstructed counters | KEEP | Familiar reference context with provenance; unknown historical time rows remain unavailable |
| Explicit Model C fields and modeled rates | KEEP | Separates physical-model cost from historical elapsed time; omission loses labeled time/rate context |
| ZiNi as efficiency reference when available | KEEP | Existing answer-derived reference, outside pure reconstruction; omission loses click-efficiency context, not a speed verdict |
| Selected action-target transition; dx/dy/d² | KEEP | Exact target geometry helps human inspection without inventing a cursor trace |
| Independent side-by-side panels | DEFER | One board needs less ownership/UI; omission loses simultaneous comparison convenience |
| Autoplay | DEFER | Manual inspection suffices; loses passive sequential viewing |
| Annotations/bookmarks | DEFER | No persistence framework needed; loses saved commentary/positions |
| Jump-to-range framework | DEFER | Direct ordinal entry suffices; loses one-click named-range navigation |
| Export/screenshots | DEFER | No output/sharing contract needed; loses integrated capture/export |
| Opening IDs, OPENING/BORDER/ISOLATED colors, 3BV-region overlays | DEFER | Aggregates suffice initially; loses local structural visualization convenience, not board reference totals |
| Recent target trails | DEFER | One exact transition suffices initially; loses immediate multi-action route context |
| Full-run path rendering | DEFER | Avoids path clutter and extra controls; loses simultaneous whole-chain visualization |
| Movement heat maps | DEFER | No aggregation/rendering policy needed now; loses a spatial frequency overview |
| Exact external replay cursor-speed measurement; velocity/acceleration/easing reconstruction | DEFER | Current inputs lack an authoritative motion trace; loses numerical external-motion comparison, requiring separately scoped new evidence |
| Full probability maps | DEFER | Not persisted; omission loses spatial risk inspection, not available evidence |
| Stage-3 chosen-plan display | DEFER | Not persisted; omission loses plan inspection; never fabricate historical plans |
| Stage-3 candidate geometry/count | DEFER | Not persisted; omission loses alternative-pool inspection; no reconstruction authorized |
| Synchronized side-by-side, common playhead/index mapping | REJECT FOR FIRST VERSION | No state-alignment authority; omission loses only synchronized navigation convenience |
| Normalized progress | REJECT FOR FIRST VERSION | Would imply unsupported progress equivalence; loses percentage-based cross-run navigation |
| Modeled-time animation | REJECT FOR FIRST VERSION | Adds clock/animation ownership; loses animated modeled pacing, not exact cost facts |
| Fabricated actual cursor trajectory | REJECT FOR FIRST VERSION | Targets are not sampled motion; loses only an unsupported path reconstruction |
| Fabricated historical elapsed time | REJECT FOR FIRST VERSION | No historical clock exists in these events; ordinary time/rate rows cannot truthfully be populated |
| Human trace overlay | REJECT FOR FIRST VERSION | No Human input authority here; loses unrelated Human comparison |
| Counterfactual nearest-risk visualization | REJECT FOR FIRST VERSION | Requires other evidence/experiment scope; loses hypothetical alternative comparison |
| Causal good/bad labels | REJECT FOR FIRST VERSION | Unsupported by replay; omission leaves interpretation to the human |
| Automatic route-quality judgment | REJECT FOR FIRST VERSION | Geometry alone proves no optimality/avoidability; omission leaves qualitative route assessment to the human |
| ZiNi-as-speed-winner judgment | REJECT FOR FIRST VERSION | Click efficiency is not physical time; omission loses an unsupported automatic verdict |
| Fake Replay/native trace wrappers | REJECT FOR FIRST VERSION | Would invent authority; loses existing wrapper/control convenience only |
| Generic cache/checkpoint framework | REJECT FOR FIRST VERSION | Bounded immutable frames suffice; loses scaling optimization for unadmitted long runs |
| Reconstruction runtime as historical timing evidence | REJECT FOR FIRST VERSION | Engine perf_counter measures reconstruction, not solver play; loses misleading time/rate reuse |

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
facts also reconciled by discovery, not fresh G4 acceptance in the future viewer.

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

Preserve Stage-3 V1 / Model C CLOSED/FROZEN, official 100k evidence, Timeline
Analytics CLOSED and both local report runs, Same-board CLOSED, ZiNi Improvement
CLOSED and its unopened final holdout. Keep Human Replay / Mouse Trace / solver
trace / post-hoc Model C / presentation authorities separate. No new telemetry,
schema, physical model, algorithm/profile selection, main-app integration or
release/package work is authorized here.

**NEXT / CURRENT / AUTHORIZED:** Slice 4 — Acceptance / Closeout.
Acceptance work is NOT YET BEGUN at this documentation transition; Slices 0–3
are COMPLETE / ACCEPTED. Future Slice 4 owns independent audit disposition if
performed, focused/frozen verification, final source regression scope, bounded
real four-case proof, source preservation checks, bounded native/manual
presentation inspection, final closeout documentation and milestone closure
adjudication. This transition performs none of that acceptance work and adds no
viewer features. The milestone remains ACTIVE pending closeout.

The accepted viewer must not read DBs outside the accepted loader or regenerate/reconstruct
on navigation. No solver/planner or selection/ranking rerun, arbitrary browsing,
shared/common playhead, normalized progress, synchronized side-by-side, autoplay
or modeled-time animation. Do not fabricate historical elapsed time or cursor
trajectory/speed, make automatic route/quality/causal judgments, alter frozen
Model C/V1 or perform algorithm research. Slices 0–3 technical semantics remain
frozen; this status transition changes no accepted contract requirement.
The viewer supports human/domain interpretation; choosing/specifying any actual
Extended algorithm research direction remains a separate explicit decision.

See the [current handoff](../CURRENT_HANDOFF.md#4-current-milestone) and
[Extended roadmap](README.md#roadmap). Historical closeouts retain their own dated
boundaries and acceptance identities.
