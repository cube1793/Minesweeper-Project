# Same-board Human / Stage-2 / Stage-3 Comparison Contract

Status: **ACTIVE — Slice 0 (contract documentation only), 2026-10-16**.
Implementation has not begun. This contract governs the first Comparison
milestone; Stage-3 V1 and Model C remain frozen.

## 1. Purpose and scope

Compare one user-declared Human/full-game Replay with independent Stage-2 and
Stage-3 executions on its exact finalized mine layout. Preserve each run's
existing semantics and report factual outcomes, actions and separately labeled
timing. This milestone does not establish a general Human-versus-solver speed
winner or automatically constitute a controlled speed experiment.

Slice 0 changes only this contract and the Extended README. It introduces no
implementation, schema changes, test changes or test execution.

## 2. Authoritative meaning of "same board"

**Exact same mine layout, independently executed under each run's existing
semantics.** The admitted Human Replay's finalized layout is the authority;
neither solver generates a replacement. Equal dimensions, mine count and mine
coordinates, plus matching recomputed canonical fingerprints, are required.

Same mine layout, same benchmark entry, same first-click policy and same
execution semantics are four separate properties. Verify and label them
separately; do not treat them as equivalent. In particular, same layout does not
imply identical first-click conditions.

## 3. Execution semantics

| Run | Required execution contract |
| --- | --- |
| Human | Reconstruct the original Replay event stream exactly, in order, from its fixed hidden board. Preserve event types, targets, timestamps, legitimate prelude and wasted actions. Optional Human Mouse Trace remains a separate attachment. |
| Stage 2 | Create a fresh isolated all-HIDDEN fixed-layout engine using `reset_with_mines()`. Call the unchanged `run_simple()` with `accept_guesses=True` and explicit `initial_open=(0,0)`. Do not rely on its default opening policy. |
| Stage 3 | Create a different fresh isolated all-HIDDEN fixed-layout engine using `reset_with_mines()`. Run unchanged frozen Stage-3 V1, including its canonical first `OPEN(0,0)` and unchanged Model C. |

Human reconstruction and solver playback use their own reconstruction state;
no run continues the Live board, another run or a playback engine. Layout truth
and fingerprints belong to setup, identity verification, reconstruction and
result qualification only. Solver inference/move selection receives only its
existing public observations and permitted configuration, never hidden mines,
the Human stream, Mouse Trace or another run's future actions.

## 4. Fresh-game first-click safety versus fixed-layout execution

In an ordinary fresh game whose mines are not yet placed, the first OPEN is
safe because the Engine excludes that OPEN target when placing mines. This is
a mine-placement rule, not a guarantee for an already placed board.

Comparison solver execution installs the Human Replay's exact finalized layout
with `reset_with_mines()` before either solver acts. If the Human originally
opened a different cell, `(0,0)` may contain a mine. Stage 2 or Stage 3 opening
`(0,0)` may therefore lose immediately without violating fresh-game first-OPEN
safety.

The comparison must not relocate mines or regenerate the board to restore
first-click safety. An immediate loss at `(0,0)` is a legitimate factual result:
it must not be filtered, retried, relocated or hidden.

## 5. First-open qualification

The result and UI must distinguish at least:

- verified same mine layout;
- Human first recorded event (action and target), and first OPEN with its event
  position, or an explicit absence; retain any preceding actions;
- Stage-2 canonical first action `OPEN(0,0)`;
- Stage-3 canonical first action `OPEN(0,0)`;
- whether the recorded opening conditions match, with the reason;
- whether solver origin `(0,0)` is a mine, explicitly when it explains a loss.

Assess opening conditions from the unfiltered stream and reconstructed state.
A Human first OPEN at `(0,0)` after prelude actions is not by itself proof of a
common start. An initial Human event `OPEN(0,0)` on the same all-HIDDEN board can
qualify as a matching recorded start; this does not prove identical historical
mine-placement policy, execution semantics or timing authority. Qualification
describes evidence, not Human provenance or experimental control. It never
changes admission or solver actions to manufacture a match. Exact UI wording
is left to implementation.

## 6. Admission requirements

An admitted recording must:

1. Provide a valid Replay board/layout and valid events under existing Replay
   rules, including coordinates, order and elapsed-time constraints.
2. Fit frozen Stage-3 supported dimensions: `1 <= width <= 30` and
   `1 <= height <= 16`, without resizing, transposing or refitting Model C.
3. Be declared as a full-game Human recording for comparison purposes.
4. Reconstruct deterministically from the fixed all-HIDDEN board to `WON` or
   `LOST`, applying every recorded event under existing Engine semantics.
5. Contain no event after the first terminal state. Reject an extra event even
   if the ordinary Engine/Replay path would ignore it after termination.
6. Preserve all legitimate prelude and wasted actions, including no-effect
   inputs and flag/unflag activity; never silently filter them for admission.

Incomplete, inconsistent or post-terminal streams receive a comparison-specific
rejection with a reason. This does not invalidate the file for ordinary Replay
use or tighten Replay v1/v2 rules. Existing recordings remain usable when they
meet these requirements. Matching canonical starts and a Mouse Trace attachment
are not mandatory admission requirements; a mine at `(0,0)` is not a rejection.

## 7. Layout identity rules

Reuse only
[`benchmark_board.calculate_board_fingerprint()`](../../benchmark_board.py).
Validate dimensions, distinct in-bounds mine coordinates and count, and recompute
the canonical fingerprint from each installed/reconstructed layout. Equality
requires all four: dimensions, mine count, exact mine-coordinate set and
recomputed fingerprint. A supplied hash alone is insufficient. There is no new
fingerprint format or first-cell-safety condition on layout identity.

An arbitrary Human Replay layout has no implied benchmark index, seed or
benchmark-set membership. Leave those absent unless independently established;
never invent placeholder identities to fit an existing benchmark wrapper. A
layout match alone does not establish the same benchmark entry. Existing
benchmark specifications, identity records and evidence remain untouched.

## 8. Provenance limitation

Current Replay `source_type="human"` does not independently prove exclusively
Human historical input. Use the neutral contract concept of a **user-declared
Human/full-game recording**. Successful reconstruction proves the recorded
stream is structurally executable to terminal state; it does not mathematically
prove its historical origin or exclusively Human provenance, including for old
Replay files. This milestone does not expand the Replay provenance schema.

## 9. Metric and time authority separation

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.

Permitted separately labeled per-run facts include outcome, total semantic
action count, OPEN count, FLAG input count, CHORD count, action sequence and
terminal reconstructed state. Count actual recorded/executed semantic inputs,
including legitimate wasted actions; FLAG input count includes unflag toggles.
Automatic Engine effects such as flood opening or automatic flags are not extra
inputs. These counts do not measure equivalent progress or decision effort.

| Authority | Meaning and boundary |
| --- | --- |
| Human Replay elapsed time | Original Replay event elapsed-time authority; not modeled physical time or a replacement clock reconstructed during playback. |
| Human Mouse Trace elapsed microseconds | Separate attachment clock for observed pointer samples; not interchangeable with Replay elapsed time. |
| Stage-2 modeled Model C time | Evaluation of the actual Stage-2 action sequence using the unchanged authenticated Model C profile/table and initial cursor `(0,0)`; not Stage-2 compute time. |
| Stage-3 modeled Model C time | Frozen Model C cost of actual executed Stage-3 inputs; not measured Human movement. |
| Stage-2 decision compute time | Existing decision-analysis measurement scope, explicitly labeled with units; not physical execution time. |
| Stage-3 decision compute time | Existing analysis/planning measurement scope, explicitly labeled with units; not physical execution time. |
| UI/playback animation timing | Presentation only, including intervals, rates and interpolation; never a run-performance metric. |

Solver modeled totals include the initial input cost `T[0][0]` and every executed
input through termination, including the losing input. For losses this is
**cost through termination**, not "time-to-win". Do not include unexecuted plans
or add Engine-generated effects. Canonical first inputs involve no solver
decision; do not invent decision-compute measurements for them.

Human Mouse Trace is observation/presentation data, not solver input, Model C
calibration evidence or Stage-3 synthetic cursor data. Synthetic Stage-3 cursor
animation is not measured movement. Any Human-versus-modeled-time display must
retain differing authorities and units explicitly; no generic `time`, `speed`,
combined performance field or single speed-winner summary is permitted.

## 10. Playback and index rules

Each run owns an independent remembered action index: index `0` is its fixed
hidden initial state, and index `n` is the state after its first `n` semantic
inputs. Reconstruct deterministically using the exact corresponding stream;
Human Replay events and Stage-3 trace records retain their separate models.
ZiNi Trace is unrelated.

Switching runs restores that run's index; it does not advance another run or
map indices between streams. Playback controls affect only the selected run.
Equal action indices across Human, Stage 2 and Stage 3 imply neither equivalent
game progress nor equivalent decision states. Seeking, playback rate, overlays
and animation cannot change solver behavior, source records or recorded/model
totals. Terminal outcome remains distinct from the currently displayed step.

## 11. Minimum first-version UI boundary

Provide a separate read-only comparison window with one board renderer, a
Human / Stage 2 / Stage 3 selector, a compact three-run summary, independent
remembered indices and selected-run playback controls. Show the first-open
qualifications in section 5 and explicitly labeled metrics from section 9.
An optional Human Mouse Trace overlay is available only for the Human run.
Comparison failures and execution/cancellation state must be explicit rather
than presented as fabricated game outcomes. The existing Stage-3 Visualizer
remains valid and independent.

## 12. Non-goals and deferred work

The following are outside Slice 0 and the first implementation unless later
evidence and a separate decision promote them:

- Mandatory strict common-start Human admission; forcing Stage 3 to use the
  Human first click; noncanonical Stage-3 opening policies; a predetermined
  benchmark-board Human collection workflow or later controlled protocol.
- Three simultaneous synchronized boards; shared ordinal timeline; normalized
  progress; common elapsed-time slider; semantic milestone alignment.
- Timeline Analytics; Human path-length analytics; comparison persistence,
  export or database; Replay provenance schema expansion.
- Generic solver registry; EventBus; universal playback abstraction.
- New algorithm research or physical model; nearest equal-minimum-risk guess;
  logical-known-mine / no-flag; action-specific timing; longer planning horizon.

## 13. Milestone-level acceptance contract

**Correctness:** verify exact layout identity; prevent hidden-layout solver
leakage; use fresh isolated solver engines; reconstruct actions deterministically;
report outcomes truthfully, including `(0,0)` first-action losses. Do not mutate
source Replay/results, relocate mines, retry-to-win, regenerate boards or
silently filter inputs.

**Separation:** preserve Replay, its separate optional Mouse Trace attachment,
Stage-3 trace and unrelated ZiNi Trace. Keep every time authority explicit.
Presentation controls cannot affect solver behavior or recorded/model totals.

**Backward compatibility:** preserve Replay v1/v2, Human Mouse Trace, Stage-2
default and explicit-opening behavior, frozen Stage-3 V1, frozen Model C and
the existing Stage-3 Visualizer. Leave benchmark/evidence artifacts untouched.

**Later testing expectations (not executed in Slice 0):**

- Pure comparison-domain/admission tests; exact-layout identity and mismatch
  tests, including recomputation rather than trusting supplied hashes.
- Fixed-board Stage-2/Stage-3 tests for safe `(0,0)` and mined `(0,0)`, isolated
  engines, no layout leakage, exact first actions and truthful terminal costs.
- Replay/trace reconstruction, prelude/wasted-action preservation, incomplete
  stream rejection and events-after-terminal rejection; source immutability.
- Independent action indices, selector/playback isolation, Human-only overlay
  and presentation-independent results/totals.
- Worker lifecycle, cancellation and cleanup, including window/main close;
  failures/cancellation must not become wins/losses or leak workers/resources.
- Full regression and native/manual acceptance of the completed integration,
  including existing Replay, Mouse Trace and Stage-3 Visualizer behavior.

No arbitrary FPS or latency requirement is introduced. Implementation slices
must provide the relevant evidence before milestone acceptance.

## 14. Proposed implementation slices after Slice 0

1. **Comparison domain and admission:** immutable layout/run context, canonical
   identity validation, full-stream reconstruction and opening qualification;
   pure tests, without fabricated benchmark metadata.
2. **Isolated execution and metrics:** fixed-layout Stage-2/Stage-3 orchestration,
   unchanged runners/Model C, separated timing and result validation; worker
   ownership, cancellation/cleanup and fixed-board tests.
3. **Pure playback coordination:** retain existing distinct stream models,
   deterministic reconstruction and independent remembered indices; focused
   reconstruction/isolation tests, without a universal playback abstraction.
4. **Read-only comparison UI:** single renderer, selector, summary and selected
   controls; Human-only optional Mouse Trace overlay; UI/lifecycle tests.
5. **Acceptance and closeout:** full regression, native/manual validation,
   compatibility and frozen-evidence checks, then milestone documentation.

These are proposed boundaries for later authorization, not work performed or
implementation acceptance in Slice 0.
