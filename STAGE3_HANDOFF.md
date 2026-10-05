# STAGE 3 HANDOFF

> **Project:** Minesweeper graduation project  
> **Purpose:** Authoritative ChatGPT Project handoff from completed Pre-Stage3 work into Stage 3 design  
> **Status:** Pre-Stage3 complete; Stage 3 design may begin  
> **Qualified baseline commit:** `30b50575b7f8a807cb9f8573f8068f5294b75219`  
> **Qualified branch at handoff:** `feature/pre-stage3-telemetry`

---

## 1. Current gate status

Pre-Stage3 is officially closed.

The following sequence has been completed:

- Stage 1 playable UI/UX, Replay, board analysis, and ZiNi-related work
- Stage 2 Simple Algorithm
- Pre-Stage3 deterministic benchmark-board infrastructure
- telemetry model / schema / repository / statistics infrastructure
- pilot progression
- official 100,000-game Stage-2 baseline
- post-run audit
- final architecture / engineering audit by Codex
- independent final architecture / engineering audit by Claude Code
- final ChatGPT adjudication against the qualified source, tests, frozen specification, and available executable evidence

Final gate result:

```text
BLOCKER = 0
REQUIRED FIX BEFORE STAGE 3 DESIGN = 0

PRE-STAGE3 FINAL AUDIT PASS — READY TO BEGIN STAGE 3 DESIGN
```

This does **not** mean that Stage 3 is already designed.

It means that no source change is required merely to make Stage 3 design permissible.

Do not reopen Pre-Stage3 frozen choices merely because another design style looks cleaner.

---

## 2. Evidence priority

When a Stage-3 design question depends on an existing fact, use this priority:

1. qualified source at commit `30b50575b7f8a807cb9f8573f8068f5294b75219`
2. tests at that commit
3. executable verification when useful
4. frozen `PRE_STAGE3_TELEMETRY_SPEC_v2.md`
5. `ARCHITECTURE.md` / `README.md`
6. prior AI interpretation or audit prose

Agreement between multiple AI reviews is not proof by itself.

For important or disputed claims, verify the source/test contract directly.

---

## 3. Accepted Stage-2 baseline

The official Stage-2 baseline is accepted and must be treated as a frozen comparison reference.

### 3.1 Official 100k run

Accepted run:

```text
benchmark set : EXPERT_GENERAL_V1
games         : 100,000
range         : [0, 100000)
result        : COMPLETED
official      : eligible
```

Accepted aggregate results:

```text
WIN   = 37,702
LOSS  = 62,298
win rate = 37.702%

total action events          = 20,143,304
local deterministic actions  = 18,504,755
global certainty actions     = 1,169,157
probability guesses          = 369,392
games containing guesses     = 94,943

average 3BV = 173.86388
average Ops = 13.35630
```

Accepted original database SHA-256:

```text
8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f
```

The accepted original database is an immutable baseline artifact.

Do not:

- append Stage-3 runs to the original file
- migrate it
- repair it
- vacuum it
- checkpoint it
- rewrite it
- use it as an ordinary mutable working database

Use a verified physical copy or an explicitly appropriate immutable read path when analysis requires SQLite access.

### 3.2 Baseline timing evidence

Accepted Stage-2 decision timing is diagnostic elapsed timing around analysis/selection only.

Stored 100k evidence includes approximately:

```text
decision compute total = 21,887.0705349 s
decision count         = 20,043,304
mean                    = 1.091989 ms
P50                     = 0.7980 ms
P90                     = 1.2445 ms
P95                     = 2.1734 ms
P99                     = 3.7722 ms
max                     = 94.1627336 s
```

The heavy tail is real Stage-2 behavior, especially around exact probability work.

Do not interpret stored Stage-2 elapsed compute timing as a future Stage-3 physical-play-time baseline.

---

## 4. Frozen benchmark corpus

The primary benchmark corpus remains:

```text
EXPERT_GENERAL_V1
width  = 30
height = 16
mines  = 99

first click = (0, 0)
first-click policy = FIRST_CLICK_FIXED_0_0

game_index == seed
generator version = V1
reference runtime = CPython 3.12.14
```

The corpus is an unfiltered deterministic prefix stream.

Examples:

```text
100      -> [0, 100)
1,000    -> [0, 1000)
10,000   -> [0, 10000)
100,000  -> [0, 100000)
```

Representative frozen fingerprints include seeds:

```text
0
1
2
42
999
99999
```

Frozen first-1000 fingerprint digest:

```text
93852d335a46af9420dbdcdf0e256bb9149778f33602f6a4facdf0295677777c
```

Stage 3 must use the same corpus when making paired Stage-2 ↔ Stage-3 claims.

---

## 5. Frozen Stage-2 solver semantics

Stage 2 is the reference solver.

Do not redesign its semantics merely to make Stage 3 integration easier.

Important Stage-2 behavior includes:

- observation-only inference
- public total mine count may be used
- local deterministic inference first
- exact complete-board probability only when local deterministic selection is unavailable
- confirmed mine `FLAG` has priority over confirmed-safe `OPEN`
- minimum-risk `OPEN` for uncertain guesses
- exact rational probability semantics
- `(y, x)` screen-reading tie-break
- one semantic action
- execute that action
- obtain a fresh public observation
- re-analyze
- primary benchmark uses `accept_guesses=True`
- primary benchmark uses explicit `initial_open=(0, 0)`

Stage-2 `run_simple` and its solver semantics are frozen reference behavior.

---

## 6. Hidden-information boundary

This boundary is mandatory for Stage 3 unless a later stage is explicitly defined as an answer-aware evaluator rather than a solver.

Solver/planner decision inputs may use public game information such as:

- public observation
- public total mine count
- already executed public action history when explicitly part of the Stage-3 model
- cursor / physical execution state introduced by Stage 3

They must not use hidden answer information to choose actions.

Forbidden as decision oracle inputs include:

- hidden mine layout
- answer-sensitive `BoardSnapshot` mine data
- board fingerprint as a source of answer knowledge
- static answer-derived 3BV / Ops values
- future terminal information
- evaluator-only knowledge

Hidden layout remains valid for:

- engine execution
- benchmark identity validation
- replay reconstruction
- post-hoc evaluation
- static board metrics

Evaluation data must not feed back into solver action selection.

---

## 7. Existing Stage-2 timing boundary

The accepted Stage-2 timing field has a frozen meaning.

For an analyzed action:

```python
t0 = perf_counter_ns()
decision = analyze_position(observation, engine.num_mines)
t1 = perf_counter_ns()

decision_compute_ns = t1 - t0
```

It excludes:

- engine step
- replay work
- telemetry observer / collector
- SQLite persistence
- board generation
- static board analysis
- modeled physical cursor movement or clicking time

Initial explicit benchmark OPEN is untimed solver policy:

```text
decision = None
decision_compute_ns = None
```

Stage 3 must not silently reuse the field with a materially different boundary.

---

## 8. Stage 3 objective

Stage 3 is **Speed-focused Algorithm**.

It is not primarily “make the Python program execute faster.”

The intended goal is:

> Preserve the Stage-2 risk discipline while choosing and ordering actions so that modeled physical Minesweeper play time is reduced.

The intended player model is idealized but human-feasible.

Potential physical factors include:

- cursor movement distance and path
- cell size / target width
- pointing / movement-time model
- OPEN input cost
- FLAG input cost
- CHORD input cost
- inter-action timing
- realistic CPS / burst constraints
- action ordering
- short-horizon routing
- possibly replay-calibrated physical parameters

The model is not intended to reproduce:

- mistakes
- random jitter
- hesitation
- fatigue

The following metrics must remain conceptually separate:

- game result / win rate / risk
- semantic action count
- Python decision/planning compute time
- benchmark process wall time
- modeled physical play time

A solver must not be called “faster” merely because losing games terminate earlier.

---

## 9. Stage 3 vs Stage 4 boundary

Stage 3 is speed-focused.

Its primary concern is physical execution time under the chosen risk discipline.

Stage 4 is efficiency-focused and should remain conceptually distinct.

Do not let Stage 3 silently become a general-purpose “optimize every metric” algorithm.

If a proposed optimization changes the primary optimization target from speed to click/3BV-style efficiency, classify whether it belongs in Stage 4 instead.

Some techniques may help both stages, but their purpose and evaluation criteria must remain explicit.

---

## 10. Final-audit design agenda: S3-01 through S3-08

These items are **not pre-design bugs**.

They are Stage-3 design / integration questions.

### S3-01 — Stage-3 solver integration seam

Current `benchmark_runner.py` is intentionally Stage-2-specific.

It directly owns / references Stage-2 execution and identity assumptions.

During Stage-3 design:

- determine the smallest seam necessary to run Stage 3 under equivalent lifecycle/provenance guarantees
- preserve Stage-2 default behavior
- do not introduce a speculative generic solver framework
- do not create a plugin registry / EventBus / general DI framework merely for future possibilities

### S3-02 — Modeled physical time

Define the Stage-3 physical-time model before adding telemetry fields.

First determine:

- model inputs
- state carried between actions
- movement model
- action costs
- whether an existing action stream is enough to compute the metric post hoc
- whether cursor path / press-release / hold state requires new data
- versioning of the physical model

Only add schema fields if the selected model cannot be truthfully reconstructed from existing semantic data plus declared configuration.

### S3-03 — Telemetry meaning

Review V1 fields one by one against actual Stage-3 semantics.

Important questions include:

- what counts as an inference category
- candidate-count meaning
- target/minimum mine probability meaning
- CHORD representation
- planning one action vs multiple actions
- exact vs approximate risk
- attribution of planning compute time

Keep V1 when it remains truthful.

Do not create V2 simply because Stage 3 exists.

If V1 cannot truthfully represent a new semantic meaning, explicitly version or extend it.

### S3-04 — Paired comparison

Stage-2 and Stage-3 comparisons must validate the same explicit prefix.

At minimum preserve:

- `game_index`
- `seed`
- board fingerprint
- first-click policy / coordinate
- benchmark-set identity
- generator version
- exact `[0, N)` coverage

The accepted original 100k DB remains immutable.

If Stage-2 and Stage-3 are stored in separate files, add the smallest safe two-source pairing path needed by the actual comparison workflow.

### S3-05 — Absolute Stage-2 semantic-action golden

Current corpus goldens freeze board identity, but the accepted Expert Stage-2 semantic action stream does not have a dedicated absolute regression golden.

Before Stage-3 implementation first modifies a shared benchmark execution path:

- choose a small accepted Expert prefix
- freeze outcome / semantic action evidence
- exclude environment-sensitive timing from the digest
- add an absolute regression oracle sufficient to detect Stage-2 behavioral drift

This is not required before Stage-3 design begins.

### S3-06 — Compute-time comparison protocol

Stored elapsed compute timing is environment-sensitive.

Do not compare a future Stage-3 run naively against an old 100k Stage-2 timing total.

If Python compute performance becomes a claim:

- define a same-session or otherwise controlled reference protocol
- consider paired Stage-2 reference subsets
- report distribution and tail, not only mean
- keep the timing boundary explicit

Modeled physical time remains a separate metric.

### S3-07 — Immutable baseline access

Ordinary SQLite read-only access can still create WAL/SHM sidecars depending on the database/journal state.

For accepted artifacts:

- avoid ordinary production access to the original baseline directory when preservation matters
- prefer verified copies for analysis
- use `immutable=1` only when its assumptions are actually satisfied
- keep the original accepted hash and artifact unchanged

### S3-08 — Metric comparison rules

Do not collapse correctness and speed into one misleading average.

Report the whole common prefix for game outcomes.

For time comparisons, define appropriate conditional analyses such as:

- both solvers win
- time-to-win
- modeled physical time
- paired per-game deltas

Do not let early losses artificially appear “fast.”

Do not directly compare solver-specific inference/candidate-count metrics unless the semantics are truly compatible.

---

## 11. Non-blocking debt that remains deferred

The final audit did not make these Stage-3 entry blockers:

- synchronous UI exact-analysis work
- Replay v1 limitations
- Replay seek/checkpoint cost
- UI responsibility concentration
- ZiNi worker lifecycle coverage
- ZiNi internal helper coupling
- canonical JSON duplication that currently fails closed
- FAILED status being best-effort
- missing game-level timestamps
- documentation drift that does not change executable behavior

Do not fix these merely because Stage 3 starts.

Only reopen one when Stage-3 requirements create a concrete dependency.

---

## 12. Stage-3 design principles

Continue to apply:

- Single Responsibility Principle
- Separation of Concerns
- maintainability
- extensibility
- testability
- backward compatibility
- DRY where it removes meaningful duplication
- KISS
- YAGNI
- evidence before optimization
- minimum necessary abstraction

When an existing field/model/module appears unnecessary, do not remove it immediately.

Explicitly state:

1. why it may be unnecessary
2. what would be lost by removing it
3. whether to `KEEP`, `DEFER`, or `REMOVE`

---

## 13. Recommended Stage-3 design order

Do not begin by editing `benchmark_runner.py`.

Recommended order:

```text
A. Define Stage-3 objective and success criteria
B. Define modeled physical-time model
C. Define Stage-3 action strategy
D. Decide CHORD / action ordering / routing scope
E. Define how Stage-2 risk discipline is preserved
F. Decide one-action vs short-horizon planning semantics
G. Map Stage-3 semantics to telemetry
H. Define paired benchmark and timing protocol
I. Define tests and Stage-2 drift protection
J. Define the minimum integration seam
K. Only then create implementation / commit plan
```

The first design question is:

> What exactly is the Stage-3 Speed-focused Algorithm?

---

## 14. Implementation workflow after design freeze

Once Stage-3 design is sufficiently frozen:

```text
ChatGPT
    design / specification / review

Codex
    implementation and focused verification

ChatGPT
    source/test review and adjudication

Claude Code
    independent read-only audit when the milestone warrants it
```

Do not ask Codex to commit/push until implementation review passes.

For disputed findings, return to source/tests rather than choosing an AI by reputation.

---

## 15. Immediate starting instruction for a new Stage-3 chat

Start with design only.

Do not write implementation code yet.

Clarify:

- what Stage 2 is reused unchanged
- what Stage 3 adds
- exact optimization objective
- minimum physical-time model
- OPEN / FLAG / CHORD scope
- cursor-state and movement assumptions
- one-action vs short-horizon planning
- preservation of risk discipline
- Stage 3 vs Stage 4 boundary

S3-01 through S3-08 are design constraints and integration questions, not a repair checklist that must be completed before the design discussion.
