# Stage-3 Telemetry / Benchmark Integration Specification
## v1 — FROZEN

> **Project:** Minesweeper graduation project  
> **Stage:** Stage 3 — Speed-focused Algorithm  
> **Slice:** B0 — telemetry / benchmark integration contract  
> **Date:** 2026-10-07 (Asia/Seoul)  
> **Status:** STAGE-3 TELEMETRY / BENCHMARK INTEGRATION SPECIFICATION v1 — FROZEN  
> **Freeze date:** 2026-10-07 (Asia/Seoul)  
> **Implementation:** APPROVED AS THE FROZEN SLICE-B IMPLEMENTATION CONTRACT.

---

# 0. Authority and evidence order

## Freeze provenance — v1

This frozen specification promotes the approved r1 document-only revision that
responded to R-1 through R-4 of `STAGE3_B0_INDEPENDENT_DESIGN_AUDIT.md`
(2026-10-07), together with the narrow text/test-boundary clarifications O-1
through O-4. It does not create a new Stage-3 algorithm version or alter the
Stage-2 telemetry semantic contract.

The source baseline reviewed for freeze is commit
`feaa68d1fa5dd3a9b71c30495c8217e0ca770172` on
`feature/stage3-implementation`. The targeted read-only re-review re-fetched the
branch and confirmed the same HEAD, so no source drift occurred between the
preceding audit and the freeze decision.

Document identities before promotion:

```text
original draft SHA-256 = d34f824ddb1ec8efde2f3cc12133f202f0b6d93c2080bec1c0aa7fc527d2e865
approved r1 SHA-256     = 9bb75055d794658ee5c2ad52b8a550fe75d53bf6bd5d01720e06cf084ed8a418
```

The targeted re-review resolved R-1 through R-4 and found no new blocking
finding:

```text
BLOCKER = 0
REQUIRED BEFORE FREEZE = 0
STAGE-3 TELEMETRY / BENCHMARK INTEGRATION SPEC v1 — FREEZE PASS
```

The original drafts and audit evidence remain review artifacts. This promotion
changes only specification status/provenance; it does not modify production
source, existing tests/fixtures, the frozen algorithm/profile, or the accepted
Stage-2 database.

This document integrates the already-frozen Stage-3 algorithm with the accepted
Pre-Stage3 telemetry / benchmark infrastructure. It does **not** reopen either
the Stage-3 algorithm or the accepted Stage-2 baseline.

When a statement depends on existing behavior, use this order:

1. qualified current source and tests on `feature/stage3-implementation`
2. executable verification when useful
3. `STAGE3_ALGORITHM_SPEC_v1.md`
4. `STAGE3_HANDOFF.md`
5. `PRE_STAGE3_TELEMETRY_SPEC_v2.md`
6. `ARCHITECTURE.md` / `README.md`
7. prior AI interpretation or audit prose

Agreement between reviewers is not proof. Disputed findings return to source,
tests, frozen specifications and executable evidence.

The accepted Stage-2 100k baseline remains immutable. Its accepted database
SHA-256 is:

```text
8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f
```

The Stage-2 qualified source baseline remains commit:

```text
30b50575b7f8a807cb9f8573f8068f5294b75219
```

---

# 1. Scope

Slice B integrates the already-approved Stage-3 Production Slice A into the
existing benchmark and telemetry infrastructure.

Required outcomes:

```text
Stage-3 run identity
Stage-3 telemetry adaptation
Stage-3 benchmark execution/persistence
exact modeled-time reconstruction
same-board Stage-2 ↔ Stage-3 pairing
outcome-aware paired statistics
Stage-2 drift protection
100-game and 1,000-game pilot qualification
```

This slice does **not**:

- change Stage-3 algorithm semantics;
- change Stage-2 solver semantics;
- change the accepted Stage-2 baseline database;
- implement P0/P1/P2 Stage-3 algorithm extensions;
- add UI comparison screens;
- add a solver registry, EventBus, plugin framework or general DI framework;
- turn compute time into the Stage-3 optimization objective;
- make a final 100k Stage-3 performance claim.

---

# 2. Frozen inputs

## 2.1 Stage-3 algorithm identity

Production Stage-3 behavior remains governed by:

```text
STAGE3_ALGORITHM_SPEC_v1.md
algorithm spec version = 1
canonical LF-content SHA-256 =
6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33
```

The Windows CRLF working-copy hash observed during Slice A qualification is
provenance only and is **not** the platform-independent algorithm identity.

## 2.2 Frozen physical profile

The Stage-3 physical model remains:

```text
model_id                 = overlap_floor_log2_distance_v1
physical_profile_version = 1
profile SHA-256          = 52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b
timing-table SHA-256     = 7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b
timing unit              = us
timing tick              = 1_us
grid                      = 30 × 16
```

Runtime cost uses the frozen integer table. Fitted coefficients and the formula
are provenance only and must not regenerate the production table.

## 2.3 Stage-3 execution assumptions

Stage-3 V1 full benchmark execution uses:

```text
initial public position = entirely HIDDEN
initial OPEN            = (0, 0)
initial cursor          = (0, 0)
one actual action       → fresh public observation → complete replan
```

The initial policy OPEN is not a solver inference and has no decision compute
timing.

---

# 3. Versioning decision

## 3.1 Physical SQLite schema

**KEEP: physical schema V1.**

```text
PHYSICAL_SCHEMA_VERSION = 1
```

No table or column migration is required for Slice B.

The existing DDL already supports:

- OPEN / FLAG / CHORD action types;
- nullable selector candidate count;
- nullable target mine probability;
- nullable minimum available mine probability;
- nullable decision compute timing;
- existing per-game action/category summaries.

The accepted Stage-2 database is never migrated.

## 3.2 Telemetry semantic versions

The persisted `benchmark_runs.telemetry_schema_version` remains the run-level
**telemetry semantic version**, independent of physical SQLite DDL.

Stage 2 remains:

```text
telemetry_schema_version = 1
solver_stage             = STAGE_2
solver_policy            = SIMPLE_MINIMUM_RISK
```

Stage 3 adds:

```text
telemetry_schema_version = 2
solver_stage             = STAGE_3
solver_policy            = E_FIRST_FIRST_REVEAL_V1
```

Existing Stage-2 constants and behavior must remain backward compatible. Do not
silently change the existing Stage-2 semantic version from `1` to `2`.

A compatible implementation may introduce explicit Stage-2/Stage-3 semantic
version constants while retaining the existing Stage-2 public constant as an
alias for `1` if needed for backward compatibility.

## 3.3 Why no physical V2

A physical-schema V2 would add migration and baseline-compatibility work without
adding information required by the chosen Stage-3 V1 model.

Disposition:

```text
Physical SQLite schema V1          KEEP
Stage-2 telemetry semantics V1     KEEP / IMMUTABLE
Stage-3 telemetry semantics V2     ADD
physical schema migration          DO NOT ADD
```

---

# 4. Stage-3 run identity

Stage-3 `solver_config_snapshot` must persist enough declared configuration to
identify the exact planner and physical model used by the run.

Minimum canonical content:

```json
{
  "initial_open": [0, 0],
  "initial_cursor": [0, 0],
  "algorithm_spec_version": 1,
  "algorithm_spec_sha256": "6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",
  "physical_model_id": "overlap_floor_log2_distance_v1",
  "physical_profile_version": 1,
  "physical_profile_sha256": "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",
  "timing_table_sha256": "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b",
  "timing_unit": "us"
}
```

The repository continues to own canonical JSON serialization.

The benchmark runner must not accept arbitrary caller-supplied identity strings
as authoritative Stage-3 configuration. The identity must be built from frozen
production constants / validated profile facts.

### Apparently redundant fields

`physical_model_id`, profile version and hashes overlap in identity information.

**KEEP NOW.**

Reason: the hashes provide exact artifact identity while the semantic ID/version
make runs inspectable without reverse-mapping opaque hashes. Removing the
human-readable identifiers would lose clarity; removing the hashes would lose
exact artifact identity.

`initial_open` overlaps run-level first-click fields.

**KEEP NOW.**

Reason: it is part of solver execution configuration, matches the existing
Stage-2 config-snapshot pattern, and makes the Stage-3 execution policy explicit.

No timing-table dimensions, fitted coefficients or calibration source-session
metadata are duplicated into the run snapshot in Slice B.

---

# 5. Generic telemetry model boundary

`telemetry_model.ActionEvent` remains the generic persisted in-memory event model.

Slice B must minimally relax only the structural assumptions that prevent a
truthful Stage-3 analyzed CHORD.

## 5.1 Generic analyzed-event structure

For an unanalyzed policy action:

```text
inference_category                  = NULL
selection_candidate_count           = NULL
target_mine_probability             = NULL
minimum_available_mine_probability = NULL
decision_compute_ns                 = NULL
```

This remains unchanged.

For an analyzed action:

```text
inference_category  = required
decision_compute_ns = required non-negative integer
```

`selection_candidate_count` becomes:

```text
NULL or positive integer
```

`target_mine_probability` becomes:

```text
NULL or exact Fraction in [0,1]
```

For `PROBABILITY_GUESS`:

```text
target_mine_probability             = required
minimum_available_mine_probability = required
```

For non-guess categories:

```text
minimum_available_mine_probability = NULL
```

The generic model validates structure and numeric domains, not solver-specific
selector meaning.

## 5.2 Stage-2 strictness is not weakened semantically

Stage-2 V1 still requires its existing exact meanings:

- final selector **cell** count is non-null;
- target probability is exact;
- guess target equals exact minimum probability;
- `(y,x)` selector self-check remains enforced;
- initial policy OPEN remains all-null.

Those Stage-2 semantics remain enforced by `simple_telemetry`, benchmark
integration invariants, the checked-in absolute Stage-2 golden, and existing
tests.

Relaxing the generic container must not redefine Stage-2 V1.

---

# 6. Stage-3 V2 action telemetry semantics

Stage-3 inference category describes the underlying current Stage-2 evidence
layer used by the Stage-3 decision:

```text
DecisionKind.LOCAL_DETERMINISTIC → LOCAL_DETERMINISTIC
DecisionKind.GLOBAL_CERTAINTY    → GLOBAL_CERTAINTY
DecisionKind.PROBABILITY_GUESS   → PROBABILITY_GUESS
```

It does not encode the action type.

## 6.1 `selection_candidate_count`

Stage-2 V1 defines this as the number of cells in the final selector class.

The Stage-3 reveal branch chooses among **plans**. Its probability-guess branch
and FLAG-only fallback select cells instead. Those branch-specific pools are
not one uniform Stage-2 final-selector cell pool.

Reusing the field as a plan count would silently change its meaning.

Therefore Stage-3 V2 uses:

```text
selection_candidate_count = NULL
```

for every analyzed Stage-3 action.

A separate `plan_candidate_count` field is not required for the primary Slice-B
benchmark.

Disposition:

```text
existing selection_candidate_count field   KEEP
Stage-2 V1 meaning                          KEEP / IMMUTABLE
Stage-3 V2 value                            NULL
new plan_candidate_count                    DEFER
```

## 6.2 Target and minimum probability

### Initial policy OPEN

```text
inference_category                  = NULL
target_mine_probability             = NULL
minimum_available_mine_probability = NULL
decision_compute_ns                 = NULL
```

### Current-certain safe OPEN

```text
inference_category      = LOCAL_DETERMINISTIC or GLOBAL_CERTAINTY
target_mine_probability = 0/1
minimum_available_mine_probability = NULL
```

### Current-certain mine FLAG

```text
inference_category      = LOCAL_DETERMINISTIC or GLOBAL_CERTAINTY
target_mine_probability = 1/1
minimum_available_mine_probability = NULL
```

### Exact Stage-2-preserved probability guess OPEN

```text
inference_category                  = PROBABILITY_GUESS
target_mine_probability             = exact probability of executed target
minimum_available_mine_probability = exact global minimum over all selectable HIDDEN cells
target == minimum
```

### CHORD

A CHORD targets an already revealed clue, not a selectable HIDDEN cell.

Therefore:

```text
target_mine_probability             = NULL
minimum_available_mine_probability = NULL
```

Do **not** store `0/1` as a placeholder merely because the revealed clue itself
is known safe. That is not the selected-hidden-target probability represented by
the existing field.

A Stage-3 CHORD remains analyzed and retains the actual current inference
category and decision compute timing. NULL here means that the selected-HIDDEN-
target probability is not applicable, not that CHORD safety is unknown.

Under the frozen production fresh-inference path, an executable positive CHORD
has a satisfied clue with nonempty HIDDEN neighbors. The local zero-remaining
rule therefore supplies safe cells before the probability path, so this
executed CHORD is reached through LOCAL evidence. A virtual plan terminal or a
generic model's ability to represent a category does not establish that the same
category is reachable for a real executed CHORD. Do not force the global path or
alter the algorithm merely to produce a GLOBAL CHORD coverage case.

---

# 7. Stage-3 telemetry adapter

Add a dedicated `stage3_telemetry.py`.

Its responsibility is only:

```text
Stage3Decision / Stage3ActionTrace
        ↓
truthful generic telemetry metadata
```

It must:

- map `decision.evidence.kind` to generic `InferenceCategory`;
- emit `selection_candidate_count=None`;
- emit exact `0/1` for current-certain safe OPEN;
- emit exact `1/1` for current-certain mine FLAG;
- preserve exact guess probability and exact global minimum for guess OPEN;
- emit probability `NULL/NULL` for CHORD;
- pass through the already-measured `decision_compute_ns`;
- fail closed on unsupported or internally inconsistent decision/action evidence.

For certainty actions, adapt the public support for the actually executed
`decision.move`, which may differ from `decision.evidence.move`. For a guess,
verify that the executed OPEN is exactly the Stage-2 `evidence.move` for that
same current observation, in addition to exact target/minimum risk equality.
Do not use an unexecuted plan suffix or the Stage-2 certainty recommendation as
a substitute for the executed action.

It must not:

- call the solver again;
- execute an Engine action;
- receive or inspect hidden mine layout;
- use `BoardSnapshot`;
- use board fingerprint as decision evidence;
- reinterpret Stage-2 `(y,x)` selector semantics as Stage-3 plan semantics.

`simple_telemetry.py` remains the Stage-2 adapter and is not generalized into a
solver registry.

---

# 8. Stage-3 game telemetry invariants

For the canonical Stage-3 benchmark:

1. Event 0 is exactly policy `OPEN(0,0)`.
2. Event 0 has all inference metadata and decision timing `NULL`.
3. Every later action has a non-null inference category and decision timing.
4. Every later action has `selection_candidate_count=NULL`.
5. `PROBABILITY_GUESS` events are OPEN actions with exact target/minimum
   probability.
6. CHORD events have target/minimum probability `NULL`.
7. CHORD is never a probability-guess action in Stage-3 V1.
8. `local + global + guess == total_actions - 1`.
9. The terminal event status agrees with runner and Engine terminal status.
10. Per-action public deltas retain the existing definitions.
11. No event is emitted for an action that was not actually executed.

The generic `TelemetryCollector` remains solver-agnostic and derives the
`GameRecord` from immutable raw events.

---

# 9. Decision compute-time boundary

The existing database column name `decision_compute_ns` is reused because
Stage-3 V2 satisfies the previously reserved complete decision/planning meaning.

Stage-2 V1:

```python
t0 = perf_counter_ns()
decision = analyze_position(observation, engine.num_mines)
t1 = perf_counter_ns()
decision_compute_ns = t1 - t0
```

Stage-3 V2:

```python
t0 = perf_counter_ns()
decision = plan_position(observation, engine.num_mines, cursor, table)
t1 = perf_counter_ns()
decision_compute_ns = t1 - t0
```

The Stage-3 boundary therefore includes the complete current production
`plan_position()` call, including Stage-2 analysis and Stage-3 planning work
performed inside it.

Under approved Slice A, this also includes work currently performed by
`plan_position()` to validate the frozen timing table. That cost is truthful
within the V2 boundary and is not silently subtracted.

The field excludes:

- execution-admissibility checking after selection;
- selected-action physical cost lookup after planning;
- `engine.step()`;
- fresh observation retrieval after the action;
- telemetry adapter / collector;
- SQLite persistence;
- board generation;
- static board analysis;
- modeled physical time itself.

The initial policy OPEN remains untimed.

Do not directly claim Python compute improvement/regression by comparing the
historical Stage-2 100k timing aggregate with a new Stage-3 run. A compute-time
performance claim requires a same-session or otherwise controlled reference
protocol and must report tail distributions as well as central tendency.


## 9.1 Required controlled compute diagnostics — B7-C

Database persistence of planner sub-phase timing remains deferred. The actual
controlled measurements required by frozen Algorithm Spec §26 are **not**
waived or deferred indefinitely.

Assign them to **B7-C — Controlled Compute Diagnostics**, a diagnostic subgate
of Slice B's B7 qualification, owned by the Slice-B implementation/validation
work. It must be completed and reviewed before final B8/B9 acceptance of Slice B
and before any final Stage-3 acceptance or compute-performance claim. The
ordinary 100/1,000-game persisted pilots alone do not close B7-C.

Use a separate diagnostic harness/report; do not add telemetry SQL columns or
change frozen action policy, timing-table authentication, or the §9 production
`decision_compute_ns` boundary just to collect a breakdown.

The diagnostic protocol must declare its fixed corpus/prefix and measurement
boundaries before execution. Report sample counts, median, P90/P95/P99 and
maximum for applicable measurements, including:

- the complete decision/planning call;
- actual probability-analysis calls, separately from local-inference calls;
- planner-only overhead, with its exact included work stated;
- candidate-generation and exact-routing timing/tails.

Name inclusive versus exclusive timings explicitly: routing may be nested in
candidate generation, so overlapping inclusive measurements must not be added
as though they were disjoint. Attribute phase work within the same diagnostic
execution; do not manufacture planner overhead by subtracting independently
timed runs. Mark populations with no applicable calls as N/A, not measured zero.
Declare the percentile convention and timing/instrumentation limitations.

Retain a separate B7-C report with the commit/configuration/profile/table
identities, environment, exact corpus/prefix, instrumentation protocol, eligible
sample counts and distributions. Check that the instrumented execution has the
same action sequence, outcomes and integer modeled costs as its uninstrumented
Stage-3 reference, excluding elapsed timing from that equality check.
Instrumentation may observe work but must not choose actions or enable a timeout,
new inference path, route heuristic, or algorithm extension.

This gate does not authorize direct comparison against historical Stage-2 100k
elapsed totals. Diagnostic phase timings are distinct from production run
telemetry and modeled physical time. Missing B7-C evidence leaves the acceptance
gate open; it must not be reported as completed merely because aggregate
`decision_compute_ns` is available.

---

# 10. Modeled physical time persistence decision

Do **not** add:

```text
modeled_action_us
game_total_modeled_us
cursor_before
```

to SQLite in Slice B.

The value is exactly reconstructable from:

```text
the preserved actual timing table, authenticated against the declared identity
explicit initial cursor = (0,0)
a validated complete ordered stream of persisted action targets
```

For action targets `a_i=(x_i,y_i)` and cursor `c_0=(0,0)`:

```text
cost_i = T[abs(x_i-c_i.x)][abs(y_i-c_i.y)]
c_(i+1) = a_i

game_modeled_us = sum(cost_i)
```

Because the frozen V1 model pools OPEN/FLAG/CHORD execution costs, no additional
action-specific physical parameter is required.

### Existing Slice-A trace fields

`Stage3ActionTrace.cursor_before` and `modeled_action_us` remain in memory.

**KEEP NOW.**

They are useful execution evidence and allow independent equivalence checks
against reconstruction. Their presence does not justify database duplication.

### Required consistency checks

Before persistence / in integration tests:

```text
run_stage3().total_modeled_us
==
independent reconstruction from the corresponding generic action-event stream
```

End-to-end benchmark tests and pilots must additionally reconstruct from the
persisted DB rows and obtain the same total.

If a future physical model cannot be reconstructed from action targets plus
declared run configuration, that future version may justify schema extension.
V1 does not.


## 10.1 Complete-stream precondition for derived modeled time

Passing board/run identity pairing does not prove that a game's raw actions are
complete. The modeled-time reader, or its explicitly validated input boundary,
must check each included game before publishing a cost:

1. The game is complete with a supported WIN/LOSS result, and
   `row_count == GameRecord.total_actions > 0`.
2. The actions are read in execution order and `action_index` is exactly
   `0 .. total_actions-1`, without gaps, duplicates, or extra rows.
3. Action/status values are recognized under the unchanged persistence mapping.
   Coordinates and indices are integers with valid domains, and coordinates
   lie within the run's board. Do not accept bool or an out-of-range coordinate
   as a valid in-memory input merely because it is integer-coercible.
4. For this canonical Stage-2/Stage-3 comparison the first event is `OPEN(0,0)`;
   its target agrees with run configuration and game first-click fields.
5. Every pre-final status is PLAYING. The final status is WON for a WIN record
   and LOST for a LOSS record. No post-terminal action is included.
6. Initial cursor, model/profile/table identity and units are explicit and
   validated as described in §10.2.

These are structural action-stream checks, not a replay/simulation proof of
legality or authenticity. Do not rerun the solver or inspect hidden layout in
the time reader. Do not move solver simulation into the existing board-pairing
function or retrofit raw-action scans into unrelated old statistics queries.

An invalid stream invalidates the requested modeled comparison: raise a clear
validation error. Never convert a missing/truncated game to zero microseconds,
repair its rows, or silently drop it from WW or another paired subset. A genuine
empty *outcome subset* follows §15.1.1; a missing raw stream for a stored game
is not an empty subset.

For every valid stream include the initial input cost `T[0][0]`, every actual
input thereafter, and the final terminal input. Do not add synthetic actions or
costs for automatic mine flags or flood-fill flag clearing. Sum actual executed
actions, not predicted plan latencies or unexecuted setup suffixes.

Storage integration tests must compare ordered action types and targets between
runner traces, produced ActionEvents, and read-back DB rows, in addition to
integer total equality. Several different displacements can have equal table
costs; a scalar total match alone is not proof of action-stream identity.

## 10.2 Authentication of the reconstruction model

A recorded SHA string identifies data; it does not recreate the timing table.
The reconstruction boundary must obtain the preserved actual profile bytes,
verify their declared SHA-256 and required metadata, and independently verify
the stored integer table's encoding/hash. Never regenerate the table from fitted
coefficients or silently substitute a different or "latest" profile. Missing or
mismatching model data is a validation failure, not a zero-cost/default model.

A Stage-3 V2 run supplies its declared model identity and initial cursor through
§4. Accepted Stage-2 V1 runs do not contain that later physical configuration.
For Stage-2 reconstruction, explicitly declare the comparison's frozen Stage-3
Model-C profile/table and canonical cursor `(0,0)` as the **evaluation model**;
do not pretend these were stored in the historical run and do not backfill the
accepted DB. Verify the Stage-2 corpus/first-click assumptions before using that
model. Both streams use the same authenticated table and initial cursor.

## 10.3 Stable sources for an official modeled comparison

Official comparisons operate on completed artifacts or verified stable snapshots
that are not being written during the comparison. The caller owns this
operational precondition and each connection. Independent read-only SELECTs do
not by themselves create one atomic snapshot across two live databases.

Use verified analysis copies when preserving accepted artifacts. Do not add a
cross-database transaction/locking framework or change caller connection state
as an implicit side effect. Live/partial observations remain explicitly
diagnostic and cannot be promoted to an official complete-artifact result.

---

# 11. Benchmark integration seam

Current Stage-2 public APIs remain behaviorally unchanged.

Keep explicit public entry points:

```text
run_benchmark(...)              # existing Stage 2
continue_benchmark(...)         # existing Stage 2

run_stage3_benchmark(...)       # new Stage 3
continue_stage3_benchmark(...)  # new Stage 3
```

Do not add a public solver registry or generic strategy framework.

The shared private seam should be limited to lifecycle/provenance/exact-prefix
work actually common to both stages, for example an internal execution helper
that receives the concrete per-game executor.

Conceptually:

```text
shared benchmark lifecycle
    ├─ Stage-2 identity + Stage-2 play_game
    └─ Stage-3 identity + Stage-3 play_game
```

Stage-2 defaults, identity and execution semantics must remain unchanged.

Before and after the first shared-path edit, the checked-in Stage-2 absolute
semantic golden for `EXPERT_GENERAL_V1 [0,2)` must match exactly, excluding
environment-sensitive compute timing as already frozen.


## 11.1 Stage-3 narrow official-run continuation

`continue_stage3_benchmark()` normatively inherits the narrow continuation
contract of `PRE_STAGE3_TELEMETRY_SPEC_v2.md` §47.2.1. Substitute only the
Stage-3 identity/configuration and concrete Stage-3 per-game executor for the
Stage-2-specific counterparts. Do not generalize resume or loosen the existing
Stage-2 continuation contract.

### Admission and preserved identity

Only an explicitly selected existing file and existing canonical
`EXPERT_GENERAL_V1` run may continue. It must preserve the original `run_id`,
`requested_games`, committed games/events, `created_at`, `started_at`,
`git_commit`, `git_dirty`, environment, and solver configuration. No caller
replacement of the requested count, benchmark spec, physical profile, solver
identity or provenance root is accepted.

Before opening a write-capable lifecycle or starting a new game, verify:

```text
run_status == RUNNING
stored git_dirty == false
failure_code IS NULL
finished_at IS NULL
0 <= processed_games <= requested_games
stored game indices are exactly [0, processed_games)

current module-root Git working tree is clean
current module-root git_commit == stored git_commit
current environment_snapshot == stored environment_snapshot

telemetry semantic version == 2
solver_stage == STAGE_3
solver_policy == E_FIRST_FIRST_REVEAL_V1
canonical EXPERT_GENERAL_V1 corpus/first-click/generator identity
canonical Stage-3 solver_config_snapshot == the §4 identity
actual frozen profile/table passes authentication
```

Use the existing strict configuration/environment comparison convention; loose
Python coercion must not make JSON true, 1 and 1.0 interchangeable. Validate the
existing physical V1 schema/integrity through the passive existing-schema
boundary, not by initializing or migrating an input file. Authenticate all
required frozen inputs during preflight, including on a finalize-only path.

A Stage-2 V1 run is rejected even though its physical SQLite schema is also V1.
CREATED, COMPLETED, ABORTED, INTERRUPTED, and FAILED are not continuable in this
contract. A dirty development pilot is not converted into an official-clean run.

### Rejection is not fatal execution

Missing/invalid files, wrong run identity, failed provenance/environment/profile
checks, and other preflight failures are side-effect-free rejections. Do not
create a missing database, initialize/migrate its schema, reconfigure its journal
mode, repair data, mark a run FAILED, or change any persisted run/game/event
metadata on rejection. Finish preflight using passive reads before obtaining
the write connection. Opening the approved writer must not recreate a missing
file if the file disappeared after preflight.

The operator must first confirm the previous writer is no longer running and
maintain single-writer exclusivity. Do not add persistent owner/lease/heartbeat
fields or automatic process-liveness infrastructure.

### Continued execution and completion

Start at stored `processed_games`, using the Stage-3 executor. Previously
committed games/events are not rewritten. An interrupted uncommitted game is
re-executed from its canonical initial state; this is not mid-action resume.
When `processed_games == requested_games`, perform full admission checks and
finalize without playing an extra game.

After successful admission, reuse the existing transaction, stop/progress,
exact-prefix completion and best-effort FAILED rules. One game, its events and
progress increment commit atomically. Check stop only before a new game;
progress reports absolute committed counts. Completing the requested prefix
wins over a later stop request. Ordinary execution failures may enter the
existing FAILED handling; process interruptions are not silently recast as a
successful completion or a different requested prefix.

There is no generic recovery, no extension of a shorter run into a longer one,
and no new physical schema or run-status value.

---

# 12. Stage-3 per-game benchmark flow

Stage-3 benchmark execution follows:

```text
generate deterministic BenchmarkBoard
↓
fresh MinesweeperEngine
↓
reset_with_mines()
↓
validate installed dimensions / mine placement / fingerprint      evaluator only
↓
validate benchmark first click is safe                            evaluator only
↓
static 3BV/Ops analysis                                            evaluator only
↓
run_stage3(engine)                                                 public solver boundary
↓
Stage3ActionTrace → stage3_telemetry adapter
↓
TelemetryCollector
↓
Stage-3 event/game invariants
↓
modeled-time reconstruction equality check
↓
atomic game persistence
```

Hidden board data may be used by benchmark/evaluator code before or after the
solver call for board identity and static metrics.

It must never be passed into:

- `plan_position`;
- Stage-3 telemetry semantics;
- action admissibility as an answer oracle.

Stage-3 benchmark specs must use first click `(0,0)` because approved
`run_stage3()` owns canonical `OPEN(0,0)`. Test corpora may use smaller
dimensions only when they still fit the frozen timing table and retain the same
canonical first click.

The official corpus remains `EXPERT_GENERAL_V1`.

---

# 13. Database policy

Official Stage-3 benchmark runs use a new database artifact.

Do not:

- append Stage-3 runs to the accepted original Stage-2 100k database;
- migrate the accepted baseline;
- checkpoint, vacuum, repair or rewrite the accepted baseline;
- use the accepted original as an ordinary mutable working DB.

The same physical V1 schema may be initialized in the new Stage-3 DB.

For comparison against the accepted Stage-2 baseline, use a verified physical
copy or an explicitly safe immutable read path. The accepted original hash must
remain unchanged.

---

# 14. Paired comparison

## 14.1 Existing same-source API

The existing `validate_paired_prefix(connection, ...)` behavior remains
available for callers that store both runs in one compatible database.

## 14.2 Required two-source path

Slice B must add the smallest safe two-source pairing path because the accepted
Stage-2 baseline and the new Stage-3 run are expected to live in separate files.

Conceptually:

```python
validate_paired_prefix_sources(
    left_connection,
    left_run_id,
    right_connection,
    right_run_id,
    prefix_games,
    *,
    require_official=False,
)
```

The exact internal function name is implementation-level, but no `ATTACH`
requirement or cross-database mutation is introduced.

The existing one-connection API may delegate to the same internal logic with the
same connection supplied on both sides.

## 14.3 Compatibility fields

Strict equality remains required for:

```text
benchmark_set_id
width
height
num_mines
first_click_policy
board_generator_version
```

Per-game explicit `[0,N)` coverage and identity still require:

```text
game_index
seed
board_fingerprint
first_click_x
first_click_y
```

Missing rows or mismatches invalidate the requested comparison.

## 14.4 Telemetry semantic compatibility

`telemetry_schema_version` is no longer a strict equality field.

Slice B explicitly recognizes these semantic-version pairs:

```text
(1,1)
(1,2)
(2,1)
(2,2)
```

Unknown semantic versions fail closed until a later specification explicitly
defines compatibility.

Cross-version pairing validates common run/game identity. It does **not** imply
that every telemetry field is directly comparable.

## 14.5 Official Stage-2 ↔ Stage-3 identity

A higher-level official Stage-2 ↔ Stage-3 comparison must additionally verify
that the intended runs are actually the expected solver identities:

```text
Stage 2:
    semantic version = 1
    solver_stage      = STAGE_2
    solver_policy     = SIMPLE_MINIMUM_RISK

Stage 3:
    semantic version = 2
    solver_stage      = STAGE_3
    solver_policy     = E_FIRST_FIRST_REVEAL_V1
    frozen Stage-3 solver_config_snapshot identity matches §4
```

Board pairing and solver-identity validation are separate concerns. Neither
substitutes for the complete raw-stream/model checks in §10.1–10.2 when a
modeled-time result is produced. Official modeled comparisons additionally use
the stable-source precondition in §10.3.

Two-source reports must distinguish the sources as well as run IDs: both files
may validly contain `run_id=1`. Keep explicit left/right source labels or artifact
identities in the report/export; do not introduce another database column for
this presentation identity.

---

# 15. Paired statistics and speed-claim rules

Correctness/risk outcomes and speed must remain separate.

For every requested prefix, first report the complete outcome contingency:

```text
WW = Stage 2 WIN  / Stage 3 WIN
WL = Stage 2 WIN  / Stage 3 LOSS
LW = Stage 2 LOSS / Stage 3 WIN
LL = Stage 2 LOSS / Stage 3 LOSS
```

Also report total wins/losses and win rates for each stage.

## 15.1 Primary official speed metric

The primary speed comparison is the **WW subset**:

> boards that both Stage 2 and Stage 3 win.

For WW games, reconstruct both action streams under the same frozen Stage-3
physical timing table and report at least:

```text
WW game count
Stage-2 total modeled time-to-win
Stage-3 total modeled time-to-win
total delta
ratio / percent reduction
paired Stage-3-faster count
paired Stage-2-faster count
ties
paired per-game deltas
```

This prevents a solver from looking faster merely because it loses earlier.
The result is conditional on the common-win subset and must not be presented
as a claim of overall solver superiority or unchanged win rate. Always show the
whole-prefix contingency and each solver's win rate alongside the WW result.

### 15.1.1 Exact primary formulas and empty-subset policy

Let `C2(g)` and `C3(g)` be each game's validated integer-microsecond cost under
the same authenticated evaluation model, including first and final inputs. For
the explicit paired prefix, define:

```text
W = {g | Stage 2 WIN and Stage 3 WIN}
S2 = sum(C2(g) for g in W)
S3 = sum(C3(g) for g in W)

paired_delta(g) = C3(g) - C2(g)
total_delta = S3 - S2

if len(W) > 0:
    primary_ratio = Fraction(S3, S2)
    primary_reduction = 1 - primary_ratio
else:
    primary_ratio = None
    primary_reduction = None
```

For a nonempty WW subset the validated complete streams and positive timing
entries make `S2 > 0`. This primary ratio is the **ratio of totals**, not the mean
of per-game ratios. It describes total common-win workload and gives longer
Stage-2 games greater weight. A mean or median per-game ratio may be separately
labelled as a supplementary statistic; it must not replace the primary ratio.

```text
paired_delta < 0  -> Stage 3 faster
paired_delta > 0  -> Stage 2 faster
paired_delta == 0 -> exact tie; no epsilon
Stage3_faster + Stage2_faster + ties == WW_count
```

`primary_reduction` is an exact fraction; the presentation percentage is
`100 * primary_reduction`. A negative reduction denotes a slowdown and must not
be clamped to zero. Convert units/round values only for presentation, not for
selection of faster/tie counts or authoritative aggregation.

If `WW_count == 0`, empty sums and faster/tie counts are zero, the per-game delta
collection is empty, and all averages/ratios/reductions requiring a nonzero
population or denominator are `None/N/A`. This is not a zero-time win, 100%
improvement, or evidence of equal performance. Apply the same empty-population
rule to other conditional subsets. A structurally invalid game follows §10.1
and invalidates the comparison instead of becoming an empty subset.

Whole-prefix sums and WL/LW/LL values remain diagnostic under §15.2–15.3; they
do not change the WW primary formulas or authorize a mixed risk/speed score.

## 15.2 Whole-prefix modeled totals

Whole-prefix modeled totals may be reported as **descriptive / diagnostic**
evidence, but they are not the primary speed claim because LOSS termination can
make shorter play appear beneficial.

This remains true even when Stage-2 and Stage-3 happen to have identical
WIN/LOSS labels on the whole prefix: LL games can still reward an earlier loss
if folded into a single speed total.

## 15.3 Other outcome subsets

`WL`, `LW` and `LL` must be reported explicitly.

Modeled times for these subsets may be inspected diagnostically, but must not be
silently mixed into the WW speed-improvement claim.

## 15.4 Metrics that must not be directly compared across V1/V2

Do not directly compare:

```text
selection_candidate_count
solver-specific plan/candidate counts
historical Stage-2 decision_compute_ns vs new Stage-3 decision_compute_ns
```

unless a separate controlled protocol defines a truthful comparison.

Action counts may be reported, but Stage 3 is not judged as faster merely because
it uses fewer actions.

---

# 16. Statistics implementation scope

Slice B should add only the backend required for the Stage-3 comparison workflow.

At minimum it must support:

- two-source exact-prefix validation;
- run identity validation for Stage 2 V1 and Stage 3 V2;
- per-game outcome pairing;
- exact integer modeled-time reconstruction from persisted action targets;
- WW primary modeled-time comparison;
- diagnostic whole-prefix totals;
- paired per-game delta counts;
- preserved existing run statistics.

No comparison GUI is required in Slice B. Existing deferred pairing UI remains
deferred until a concrete UI milestone.

Presentation may convert microseconds to seconds or percentages only after exact
integer aggregation.

---

# 17. Required tests and acceptance evidence

## 17.1 Stage-2 protection

Before and after shared benchmark-path edits:

```text
tests/test_stage2_semantic_golden.py
EXPERT_GENERAL_V1 [0,2)
```

must remain exact, timing excluded as frozen.

Preserve the existing Stage-2 benchmark, adapter, repository, statistics and
continuation behaviors and their regression coverage. Keep the Stage-2 golden
fixture/digest unchanged. The generic model's intentional structural expansion
in §5 means its old blanket non-null assertions cannot all remain literally
unchanged: adjust only the affected cases and retain their applicable safety
checks as described in §17.2. This is not permission to remove failing tests
indiscriminately or weaken Stage-2 semantics.

Do **not** add a production invariant that Stage-2 and Stage-3 must always have
the same guess checkpoints or final outcomes. Existing `[0,1000)` agreement is
audit evidence, not a frozen future contract.

## 17.2 Generic telemetry

Tests must prove:

- Stage-2 V1 adapter still emits non-null candidate counts and exact probability
  semantics.
- Generic analyzed LOCAL/GLOBAL events can structurally carry nullable
  candidate/target fields when stage-specific semantics permit it.
- Guess events still require exact target and minimum probabilities.
- Unanalyzed events still require all inference metadata and timing to be null.

When updating former blanket non-null negative tests, map each affected
assertion to the new generic case or the preserved Stage-2 adapter/integration
assertion. Keep type/range, all-null-policy, guess-required-probability and
required-compute-time checks. Do not delete the entire negative-test group.

Keep existing generic statistics import/connection isolation intact. Put
physical-model-aware reconstruction/comparison work at its explicit new
boundary rather than casually weakening existing dependency tests to let
solver/planner logic enter generic statistics.

## 17.3 Stage-3 telemetry adapter

Cover at least:

- LOCAL safe OPEN;
- LOCAL mine FLAG;
- GLOBAL safe OPEN;
- GLOBAL mine FLAG;
- PROBABILITY_GUESS OPEN;
- LOCAL CHORD;
- the LOCAL executed-CHORD reachability described in §6.2; do not alter
  production inference to fabricate GLOBAL CHORD coverage;
- policy initial OPEN;
- unsupported/inconsistent decision failures;
- hidden-information isolation.

Verify:

```text
candidate count = NULL for analyzed Stage-3 events
CHORD probability = NULL / NULL
guess target == exact minimum
OPEN/FLAG certainty risk = 0/1 or 1/1
```

## 17.4 Persistence

Round-trip Stage-3 events, including analyzed CHORD with null probability, through
the unchanged physical V1 DDL.

Verify no migration or physical schema version change.

## 17.5 Benchmark lifecycle

Test:

- new Stage-3 run lifecycle;
- exact requested prefix;
- failure and rollback behavior;
- stop/progress behavior;
- continuation preflight;
- canonical Stage-3 run identity;
- first event policy contract;
- terminal status agreement;
- Stage-2 public APIs unchanged.

Stage-3 continuation tests must cover the full §11.1 admission and preservation
contract: Stage-2-run misrouting; wrong semantic version/config/profile;
side-effect-free rejection; missing-file no-creation; unchanged original
requested count/metadata/committed rows; interrupted versus uninterrupted
semantic equivalence with elapsed timing excluded; finalize-only after full
preflight; and failure/stop/progress behavior after successful admission.

The `[0,2)` golden protects per-game Stage-2 semantic actions; it does not replace
public dispatch, lifecycle, provenance, continuation or rollback tests. A shared
path edit must preserve those tests as well as the absolute golden.

## 17.6 Modeled-time reconstruction

For deterministic test games:

```text
run_stage3().total_modeled_us
==
reconstruction from produced ActionEvents
==
reconstruction from persisted action_events
```

Also reconstruct Stage-2 streams with the same frozen table and explicit
post-hoc evaluation configuration rather than modifying historical metadata.
Verify ordered action type/target equality across trace, ActionEvents and
read-back rows in addition to scalar cost equality.

Negative fixtures must cover missing/all-missing actions, noncontiguous or extra
indices, count mismatch, out-of-bounds/malformed coordinates, unsupported
action/status, incorrect first input, early-terminal/post-terminal rows, terminal
result mismatch, and absent/mismatching model data. A game-row pairing that
passes with deleted action rows must still fail modeled reconstruction. No
fixture may become a zero-cost game or be silently removed from the pair.

Include first-input, final-input, automatic-win-flag exclusion, and equal-cost
but different-target/order cases. Keep this boundary structural; no hidden-board
re-solving is required.

## 17.7 Pairing

Test:

- same-source V1↔V1 compatibility;
- same-source V2↔V2 compatibility;
- V1↔V2 and V2↔V1 compatibility;
- two-source pairing;
- missing index rejection;
- fingerprint mismatch rejection;
- first-click mismatch rejection;
- unknown semantic-version rejection;
- official-eligibility rejection;
- Stage-2/Stage-3 solver-identity rejection when using the higher-level official
  comparison path.

## 17.8 Outcome-aware statistics

Use fixtures with all four:

```text
WW
WL
LW
LL
```

Prove that the primary speed aggregate uses only WW and that an artificially
short early-loss game cannot improve the reported WW speed result.

Test the exact formulas and labels in §15.1.1, including:

- ratio-of-totals versus mean-of-ratios using unequal per-game baselines;
- negative/positive/zero delta and unclamped negative reduction;
- no-WW prefixes and genuinely empty outcome subsets with None/N/A rates;
- a single WW game and exact integer ties;
- identical outcome labels containing LL games that distort whole-prefix sums.

Do not treat validation failures as empty-subset cases.

## 17.9 Pilot progression

After source/test review:

```text
100-game Stage-3 pilot
→ audit / reconstruction / pairing
→ 1,000-game Stage-3 pilot
→ audit / reconstruction / pairing
```

The accepted 100k Stage-2 original remains untouched. Use a verified copy for
cross-source analysis.

The 100/1,000 pilots are qualification evidence, not the final 100k performance
claim. B7 additionally includes **B7-C — Controlled Compute Diagnostics** under
§9.1. Retain its separate declared protocol and report before B8/B9 acceptance;
aggregate benchmark timing is not a substitute for the required phase evidence.
No new sub-phase timing column is introduced.

---

# 18. Implementation and freeze workflow

Recommended order:

```text
B0. This integration contract
B0-R. Independent read-only design audit
B0-F. Adjudicate findings and freeze this specification

B1. Minimal generic telemetry relaxation + stage3_telemetry
B2. Stage-2 golden / regression confirmation
B3. Minimal shared benchmark lifecycle seam
B4. Stage-3 benchmark execution / persistence / continuation
B5. Modeled-time reconstruction + run-identity validation
B6. Two-source pairing + outcome-aware paired statistics
B7. 100-game → 1,000-game pilots
B7-C. Controlled compute diagnostics and separate report (§9.1)
B8. ChatGPT source/test adjudication
B9. Independent Claude Code audit
```

Do not ask the implementation agent to commit or push until B8/B9 findings are
adjudicated and no required fix remains.

---

# 19. Explicitly deferred

The following remain deferred unless Slice B exposes a concrete correctness
dependency:

- `plan_candidate_count` persistence;
- per-action or per-game modeled-time columns;
- planner sub-phase timing columns;
- production SQL persistence of probability-analysis/planner-only breakdown
  (the B7-C controlled diagnostic measurement obligation itself is NOT deferred);
- physical SQLite schema V2;
- comparison GUI;
- Stage-3 P0/P1/P2 algorithm extensions;
- nearest equal-risk guess;
- logical-known-mine / no-flag execution;
- action-specific timing;
- anisotropy;
- CPS/burst constraints;
- general benchmark solver framework;
- historical Stage-2 vs Stage-3 compute-performance claim;
- Stage-2 ↔ Stage-3 outcome equality as a regression invariant.

---

# 20. Decision summary

```text
Physical SQLite schema V1
    KEEP

Stage-2 telemetry semantics V1
    KEEP / IMMUTABLE

Stage-3 telemetry semantics V2
    ADD

Stage-3 dedicated telemetry adapter
    ADD

Generic ActionEvent
    MINIMALLY RELAX STRUCTURE
    DO NOT weaken Stage-2 semantic adapter contract

Stage-3 selection_candidate_count
    NULL

Stage-3 plan_candidate_count
    DEFER

Stage-3 OPEN/FLAG target risk
    exact 0/1, 1/1, or exact guess probability as applicable

Stage-3 CHORD target/minimum probability
    NULL / NULL

decision_compute_ns
    REUSE with versioned boundary
    Stage 2 = analyze_position
    Stage 3 = complete plan_position

frozen Algorithm §26 controlled phase diagnostics
    REQUIRED AT B7-C BEFORE ACCEPTANCE
    NO NEW SQL TIMING COLUMNS

Stage-3 continuation
    INHERIT NARROW §47.2.1 CONTRACT + EXPLICIT STAGE-3 IDENTITY
    PREFLIGHT REJECTION IS SIDE-EFFECT-FREE

modeled_action_us / game_total_modeled_us DB columns
    DO NOT ADD

Stage3ActionTrace cursor/cost
    KEEP in memory

Stage-3 official DB
    NEW ARTIFACT
    DO NOT append to accepted Stage-2 baseline

same-source pairing API
    KEEP

two-source pairing
    ADD MINIMAL PATH

telemetry semantic version equality
    REPLACE with explicit V1/V2 compatibility rule

modeled-time reconstruction
    VALIDATED COMPLETE ACTION STREAM + AUTHENTICATED PRESERVED TABLE
    DO NOT INFER RAW-ACTION COMPLETENESS FROM BOARD PAIRING

primary official speed metric
    paired WW modeled time-to-win
    RATIO OF TOTALS; DELTA = STAGE3 - STAGE2
    EMPTY SUBSET RATES = NONE / N/A

whole-prefix modeled total
    DIAGNOSTIC ONLY

Stage-2 ↔ Stage-3 outcome equality regression invariant
    DO NOT ADD
```

---

# 21. Freeze status

The required read-only design audit and targeted re-review were completed
against `feature/stage3-implementation` at:

```text
feaa68d1fa5dd3a9b71c30495c8217e0ca770172
```

The freeze gate is closed:

```text
BLOCKER = 0
REQUIRED BEFORE FREEZE = 0
```

Final status:

```text
STAGE-3 TELEMETRY / BENCHMARK INTEGRATION SPECIFICATION v1 — FROZEN
```

This document is the authoritative Slice-B implementation contract. Later
implementation findings must be adjudicated against this frozen contract rather
than silently changing its semantics. Any future semantic revision requires an
explicitly versioned specification change.
