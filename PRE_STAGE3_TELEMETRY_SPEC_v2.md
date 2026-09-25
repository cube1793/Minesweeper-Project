# PRE_STAGE3_TELEMETRY_SPEC

> **Version:** Official Revision 2 — frozen implementation specification  
> **Status:** FROZEN FOR PRE-STAGE 3 IMPLEMENTATION  
> **Implementation status:** IMPLEMENTATION MAY PROCEED UNDER THIS SPECIFICATION  
> **Purpose:** Define the minimum telemetry, reproducible benchmark, persistence, and statistics infrastructure required to measure the Stage 2 solver fairly before Stage 3 begins.

---

## 0. Review rule and authority

This revision was produced after two independent full audits of the previous draft against the current `main` source, tests, and executable checks, adjudication of those findings, and a final independent delta review by both reviewers.

Evidence priority remains:

1. Current `main` source code
2. Current tests
3. Executable verification when useful
4. `ARCHITECTURE.md`
5. This document
6. Reviewer interpretation

Revision 2 is now **FROZEN FOR PRE-STAGE 3 IMPLEMENTATION**. The delta reviews found no implementation blocker. Four non-blocking documentation/contract clarifications were accepted before freeze:

- exact prefix-digest bytes and SHA-256 algorithm;
- a complete `git_dirty` / official-baseline eligibility rule;
- explicit SQL restrictions for canonical rational TEXT;
- a benchmark-domain-bounded exact probability round-trip requirement rather than a literal unlimited decimal-string claim.

If this document conflicts with current source/tests, determine whether the difference is:

- an intentional proposed change explicitly identified here; or
- a specification defect.

Do not reopen a frozen design choice merely because another valid style is possible. Reopen it only for demonstrated correctness, consistency, testability, or scope defects.

## 0.1 Project context

This is a staged Minesweeper graduation project.

The current project progression is:

```text
Stage 1 — UI/UX + Replay
    Playable PyQt5 Minesweeper application
    Replay recording / save / load / playback / seeking / speed control
    Existing game statistics and related UI foundations

Stage 2 — Simple Algorithm
    Local deterministic inference
    Exact complete-board probability analysis
    Observation-only decision pipeline
    Synchronous execution through the current runner
    Minimum-risk guessing when no certain move exists

Pre-Stage 3 — current work
    Reproducible telemetry
    Fixed benchmark boards
    SQLite benchmark storage
    Statistics / graph foundation
    Trustworthy Stage 2 baseline

Stage 3 — next implementation target
    Speed-focused algorithm
```

Stage 3 is **not** primarily about making Python execute faster.

Its intended objective is to preserve the Stage 2 risk discipline while choosing and ordering actions so that the game can be played faster in modeled physical Minesweeper time.

Stage 3 should model an **idealized but human-feasible Minesweeper player**. Its physical execution should resemble realistic human mouse movement and input timing as closely as practical, rather than assuming instantaneous cursor relocation, zero movement cost, or unlimited action rate. The goal is **not** to reproduce human mistakes, hesitation, random jitter, or fatigue. Instead, Stage 3 should preserve realistic human physical constraints while optimizing play speed.

Later Stage 3 work is expected to consider factors such as:

- cursor movement distance and path;
- cell size / target width;
- movement-time models;
- OPEN / FLAG / CHORD physical input costs;
- realistic inter-action timing and CPS limits/bursts;
- action ordering and short-horizon routing;
- replay-calibrated timing and movement behavior.

Human replay data and controlled pointing experiments may later be used to **calibrate and validate** this physical model. They are evidence for realistic timing and movement constraints, not exact ground truth that the algorithm must imitate frame-for-frame.

Therefore this Pre-Stage 3 work exists to establish a trustworthy Stage 2 measurement baseline **before Stage 3 changes are introduced**.

The reviewers must judge this specification in that project context. They should not redesign Stage 2, prematurely implement Stage 3, or generalize the system into a research framework beyond what is required to support fair Stage 2 → Stage 3 comparison.

---

## 0.2 Engineering principles

All review findings and later implementation decisions must respect the project-wide software-engineering principles below.

### Core principles

- **Single Responsibility Principle (SRP):** each module/class should have one clear reason to change.
- **Separation of Concerns (SoC):** game rules, solver reasoning, execution, telemetry, persistence, statistics, and UI should remain separate where their responsibilities differ.
- **Extensibility:** Stage 3/4 should be able to reuse the measurement infrastructure without forcing speculative abstractions today.
- **Maintainability:** favor explicit, understandable contracts over clever or highly coupled designs.
- **Testability:** important semantics and invariants must be independently testable.
- **Backward compatibility:** existing Stage 1/2 behavior and public contracts should not be broken unless a proposed change is explicitly justified and tested.
- **Minimal necessary abstraction:** future possibilities alone are not sufficient justification for introducing generic frameworks, interfaces, registries, services, or plugin systems.
- **Evidence before optimization:** optimize only after pilot measurement identifies a real cost or bottleneck.

### Rule for apparently redundant or unnecessary elements

If a field, model, abstraction, or module appears unnecessary or redundant, a reviewer must **not** simply recommend deleting it.

The reviewer must state:

1. why it may be unnecessary or redundant;
2. what information, convenience, validation power, future compatibility, or clarity would be lost by removing it;
3. whether the best choice is:
   - **KEEP NOW**
   - **DEFER / REVISIT AFTER PILOT**
   - **REMOVE**

This requirement applies in particular to intentional denormalization and duplicated summary fields.

The goal is not to maximize abstraction or minimize file count. The goal is to preserve clear responsibilities with the smallest structure that is justified by the current research and implementation needs.

---

## 0.3 Revision 2 audit resolution

The following decisions are resolved in this revision and are no longer open design questions:

```text
exact SQLite probability
    → canonical reduced rational TEXT, always "n/d"

board fingerprint
    → frozen canonical binary encoding + SHA-256 lowercase hex

Generator V1
    → local random.Random(seed).sample(...)
    → CPython 3.12.14 reference runtime
    → golden fingerprints + prefix digest + pair-time fingerprint validation

fixed-board runner integration
    → keyword-only initial_open + optional observer
    → one Stage 2 execution loop remains authoritative

SQLite operating mode
    → WAL + synchronous=FULL initially
    → NORMAL only after pilot evidence justifies it

v1 committed game outcome
    → result is authoritative and NOT NULL
    → per-game termination_reason/error_code are deferred
```

Other adjudicated changes in this revision include:

- `benchmark_set_id` is required for benchmark runs;
- official baseline runs require a clean non-ignored Git working tree and record `git_dirty`;
- `safe_cells_opened_delta` includes `FLAGGED → safe-number` reveals;
- `explicit_flag_delta` excludes Engine automatic flag/unflag effects;
- Stage 2 adapter performs selector-semantic self-checks;
- paired comparison requires explicit coverage and rejects missing/mismatched pairs rather than silently dropping them;
- DB failure can prevent even the `FAILED` status update, so failure finalization is best-effort;
- `action_events` uses `WITHOUT ROWID` in v1;
- custom PRNG, resume, chunking, no-replay mode, parallelism, and Stage 3 physical telemetry remain deferred until evidence requires them.

---

# 1. Goal

Pre-Stage 3 exists to create a trustworthy Stage 2 baseline before speed-focused Stage 3 work begins.

The minimum required pipeline is:

```text
fixed benchmark set
→ reproducible board
→ Stage 2 game execution
→ per-action telemetry
→ per-game summary
→ SQLite persistence
→ aggregate statistics
→ basic graphs
→ Stage 2 baseline
```

The infrastructure must support fair paired comparison of Stage 2, Stage 3, and later stages on the **same boards**.

The infrastructure is not a general research platform.

---

# 2. Scope boundary

## 2.1 Required now

The first implementation scope is limited to:

- deterministic benchmark-board generation
- fixed benchmark-set semantics
- Stage 2 one-game instrumentation
- per-action telemetry
- per-game summary telemetry
- one-run metadata
- SQLite persistence
- transactional integrity
- basic aggregate statistics
- small pilot runs
- basic statistics/graph UI after backend validation
- eventual 10k / 100k Stage 2 baseline runs

## 2.2 Explicitly deferred

Do **not** implement the following merely because this document mentions future compatibility:

- parallel benchmark workers
- multi-process SQLite writer
- database sharding
- database archival/compaction
- resumable interrupted runs
- sophisticated migration framework
- plugin/event-bus architecture
- general dependency-injection framework
- generic planner telemetry for all future stages
- per-frame board snapshots
- full candidate-list logging in standard telemetry
- Stage 3 cursor/timing fields
- Stage 3 physical-action planner
- held-button planning
- risk-band/aggressive-speed policy
- exact mouse-down/up timing capture
- benchmark cancellation inside probability enumeration
- automatic recovery of stale `RUNNING` runs
- custom stable PRNG implementation unless later required by evidence

These items may be designed later when there is a concrete need.

---

# 3. Existing architecture that must remain intact

The current project separates:

```text
core_engine.py
    rules / state transition / timer / click accounting

simple_algorithm.py
    local deterministic inference

simple_probability.py
    exact complete-board probability

simple_decision.py
    pure position analysis

simple_runner.py
    synchronous execution

Replay modules
    recording / playback / analysis / statistics

board_snapshot.py
board_analyzer.py
    immutable static board representation / 3BV / Ops
```

Pre-Stage 3 must preserve these boundaries unless this document explicitly proposes a small extension.

Hard architectural constraints:

- Solver decision logic must not read the hidden mine layout.
- `analyze_position()` must remain observation-only.
- Telemetry persistence must not be added to `MinesweeperEngine`.
- SQLite must not be accessed from solver logic.
- UI must not directly contain SQL/statistics semantics.
- Replay events and telemetry events remain separate models.
- Benchmark code must not duplicate Stage 2 inference rules.

---

# 4. Current first-click semantics

The current Engine policy is:

```text
fresh game
→ mines_placed == False

first valid OPEN(x, y)
→ place mines while excluding only (x, y)
→ surrounding 8 cells remain valid mine candidates
→ compute adjacency / static analysis
→ reveal (x, y)
```

Therefore:

- the first OPEN cell is guaranteed safe;
- the first OPEN is **not** guaranteed to reveal `0`;
- the surrounding 8 cells are **not** guaranteed safe.

If the first action is `FLAG`, mines are placed without a safe OPEN cell. Removing that flag later does not regenerate the board.

`reset_with_mines()` is different: it installs an already-finalized layout and sets `mines_placed=True`.

---

# 5. Benchmark first-click policy

The primary benchmark policy is:

```text
FIRST_CLICK_FIXED_0_0
```

The benchmark generator must generate boards such that `(0, 0)` is not a mine.

The exclusion rule must reproduce the fresh Engine policy:

```text
exclude (0, 0) only
do NOT exclude its surrounding 8 cells
```

The primary benchmark game then executes:

```text
ActionEvent #0 = OPEN(0, 0)
```

without treating it as a solver inference.

For action 0:

```text
inference_category = NULL
selection_candidate_count = NULL
target_mine_probability = NULL
minimum_available_mine_probability = NULL
decision_compute_ns = NULL
```

The result of the OPEN, including flood reveal and terminal state, is still recorded normally.

---

# 6. `simple_runner` extension for fixed benchmark boards

## 6.1 Current conflict

Current `run_simple()` intentionally behaves differently for an already-placed all-hidden board:

```text
all hidden + mines_placed=False
→ special first OPEN policy

all hidden + mines_placed=True
→ normal analyze_position()
```

A benchmark board loaded through `reset_with_mines()` is already `mines_placed=True`.

Therefore:

```text
reset_with_mines(...)
run_simple(...)
```

does **not** reproduce the fresh-game first-OPEN policy. This is a real integration issue.

## 6.2 Frozen API direction

Extend `run_simple()` additively with keyword-only options:

```python
run_simple(
    engine,
    *,
    accept_guesses=False,
    initial_open=None,
    observer=None,
)
```

Default behavior with `initial_open=None` and `observer=None` must remain backward-compatible with the current runner.

Primary benchmark use:

```python
run_simple(
    engine,
    accept_guesses=True,
    initial_open=(0, 0),
    observer=...,
)
```

`initial_open` is an execution policy, not a solver decision.

When `initial_open` is specified, the runner must validate **before mutating the Engine** that:

- the coordinate is a two-integer `(x, y)` pair; booleans are not accepted as integers;
- the Engine is `PLAYING`;
- the starting observation is entirely `HIDDEN`;
- the coordinate is in bounds;
- the target is `HIDDEN`.

The runner then executes that OPEN without calling `analyze_position()` for it.

The runner must not inspect hidden mine positions to decide whether the explicit initial cell is safe. The benchmark generator/evaluator is responsible for ensuring the benchmark first click is safe.

If `initial_open` is specified, it takes precedence over the runner's existing implicit fresh-game `(0,0)` first-open policy for that invocation.

## 6.3 Observer contract

`observer` is intentionally a small optional callback, **not** a generic EventBus.

Conceptually:

```text
observer(SimpleActionTrace)
```

The observer receives immutable execution facts only. It must not be passed the Engine or hidden board layout.

For each successfully executed action, the order is:

```text
move selected / explicit initial OPEN chosen
→ engine.step()
→ Replay event recorded
→ replay board captured if needed
→ fresh public observation obtained
→ action-effect deltas derived
→ runner progress/invariant checks pass
→ observer(trace) exactly once
```

Rules:

- terminal actions still produce exactly one trace;
- a pending guess that was not executed produces no trace;
- a terminal Engine receives no new action and no trace;
- observer exceptions propagate and are not swallowed;
- observer code must not mutate game state through external references;
- `observer=None` adds no telemetry behavior to the normal runner path.

The trace is a small runner-to-observer DTO. It is not a database model and does not make `SimpleRunResult` a telemetry container.

## 6.4 Rejected alternatives for v1

Do not create a second complete Stage 2 game loop inside `benchmark_runner.py`.

Do not add fixed-layout/deferred-placement modes to `MinesweeperEngine` merely for benchmarking.

Do not replace the optional observer with a generic event system.

A return-all-traces design is technically valid, but Revision 2 keeps the observer boundary because it preserves runner result semantics and keeps telemetry consumption outside `SimpleRunResult` while adding only one small opt-in callback.

---

# 7. Benchmark board generation

Create a small benchmark-board module, tentatively:

```text
benchmark_board.py
```

It owns benchmark board generation and board identity. It must not contain solver logic or persistence logic.

## 7.1 Benchmark set

Primary corpus:

```text
EXPERT_GENERAL_V1
```

Semantics:

```text
width = 30
height = 16
num_mines = 99
first_click = (0, 0)
unfiltered general boards
generator version = V1
```

`GENERAL` means no filtering by solver result, guess occurrence, 3BV, opening size, probability pattern, board difficulty, or Stage 2 win/loss.

Filtered/adversarial corpora require a different benchmark-set ID.

## 7.2 Stream and run-range semantics

`EXPERT_GENERAL_V1` is a deterministic prefix stream.

For V1:

```text
game_index == seed
```

Examples:

```text
100-game pilot      → game_index 0..99
1,000-game pilot    → 0..999
10,000-game run     → 0..9,999
100,000-game run    → 0..99,999
```

Therefore:

```text
100 ⊂ 1,000 ⊂ 10,000 ⊂ 100,000
```

A v1 `BenchmarkRun` always represents the exact prefix:

```text
game_index ∈ [0, requested_games)
```

A `COMPLETED` run must contain exactly that index set with no missing or extra game indices.

`game_index` and `seed` are both retained even though equal in this set because their meanings differ: corpus position versus generator input.

Chunked/non-prefix runs and a `first_game_index` field are deferred. The 10k pilot determines whether 100k operational risk justifies adding them.

## 7.3 Generator V1

Reference algorithm:

```python
rng = random.Random(seed)

candidates = [
    (x, y)
    for y in range(height)
    for x in range(width)
    if (x, y) != first_click
]

mines = rng.sample(candidates, num_mines)
```

Requirements:

- local `random.Random(seed)` only;
- never call global `random.seed(seed)`;
- fixed row-major candidate order;
- exclude only the first-click cell;
- do not exclude its surrounding 8 cells;
- do not filter generated boards after generation.

### Reference-runtime contract

Generator V1's reference runtime is:

```text
CPython 3.12.14
```

The benchmark must record the actual Python implementation/version in `environment_snapshot`.

Python's seeded PRNG is intentionally deterministic for reproducibility, but this specification does **not** assume that `random.sample()` output is guaranteed identical across every future Python implementation/version.

Therefore V1 compatibility is protected by golden tests (§9) and by actual fingerprint verification during paired comparison (§10).

If a new runtime breaks the V1 golden corpus:

- do **not** silently update the existing golden values;
- use the reference runtime to reproduce V1, or
- define a new generator/set version such as V2.

A custom project-owned PRNG/sampling algorithm remains deferred unless long-term runtime-independent regeneration becomes a concrete requirement.

---

# 8. Benchmark board identity

Tentative pure model:

```text
BenchmarkSetSpec
- benchmark_set_id
- width
- height
- num_mines
- first_click_x
- first_click_y
- board_generator_version
- seed_scheme

BenchmarkBoard
- game_index
- seed
- mine_positions
- board_fingerprint
```

Do not add a separate `board_id` in v1.

## 8.1 Frozen canonical fingerprint encoding

The fingerprint identifies the **actual mine layout**, not generation metadata.

Canonical payload:

```python
payload = (
    b"MSLAYOUT1\0"
    + struct.pack(">III", width, height, num_mines)
    + b"".join(
        struct.pack(">II", x, y)
        for x, y in sorted(mine_positions, key=lambda c: (c[1], c[0]))
    )
)

board_fingerprint = hashlib.sha256(payload).hexdigest()
```

Contract:

- integer encoding is unsigned 32-bit big-endian;
- coordinates are stored as `(x, y)` values but ordered by `(y, x)` reading order;
- the payload contains exactly `num_mines` distinct in-bounds coordinates;
- the domain tag is exactly the 10 bytes `b"MSLAYOUT1\0"`;
- the persisted fingerprint is exactly 64 lowercase hexadecimal characters.

Do not include seed, benchmark-set ID, generator version, first-click policy, solver stage, or solver policy in the fingerprint payload.

Consequences:

- equal layouts have equal fingerprints even if generated differently;
- fingerprint is not UNIQUE;
- duplicate layouts remain separate corpus entries by `game_index`.

Changing the encoding requires a new fingerprint/generator compatibility contract; existing golden values must not be silently rewritten.

## 8.2 Hidden-information rule

`mine_positions` and `board_fingerprint` are evaluation/environment information.

They must never be passed to `analyze_position()`, Stage 2 move selection, or future Stage 3 move selection.

The solver receives only public observation and public mine count.

---

# 9. Golden reproducibility tests

Generator V1 must have reproducibility checks at more than one scale.

## 9.1 Representative seed fingerprints

For `EXPERT_GENERAL_V1` under the frozen Generator V1 and fingerprint contracts, the following expected lowercase SHA-256 fingerprints are authoritative:

```text
seed 0      fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053
seed 1      007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e
seed 2      58b8e6399a435371a430a75bd0a51035614242662b53015c61eb61292ccdd28a
seed 42     9a86f62d6fcc7bd8a19f53308a84d0710c8238b5fbf72ea5041fa38e4603f2ac
seed 999    45f1236c061ece7041aba1312f16137ee68f2c43da2d7c0b9f2065c37877cace
seed 99999  9a5903f41835faa195d0c1e457ee5721cd93f514c503043b6b08492b4425a0af
```

These values are readable seed → board identity fixtures. They were independently reproduced during Revision 2 delta review on the reference runtime CPython 3.12.14.

## 9.2 Prefix digest

Generate fingerprints for the exact prefix:

```text
game_index 0..999
```

in index order.

The digest algorithm is frozen as:

```python
hashlib.sha256(
    b"
".join(fp.encode("ascii") for fp in fingerprints)
).hexdigest()
```

Contract:

- `fingerprints` contains exactly 1,000 entries for `game_index 0..999` in ascending index order;
- each entry is the 64-character lowercase hexadecimal board fingerprint from §8;
- separator is exactly one LF byte `0x0A`;
- there is no trailing separator/newline;
- the outer digest algorithm is SHA-256.

The authoritative first-1,000 prefix digest is:

```text
93852d335a46af9420dbdcdf0e256bb9149778f33602f6a4facdf0295677777c
```

This digest is a compact whole-prefix compatibility check.

## 9.3 Engine-equivalence check

Representative tests must prove that Generator V1's first-click exclusion and mine sampling reproduce the Engine's current fresh-game placement policy when the Engine uses the same deterministic sample result.

## 9.4 Golden policy

If a supported environment produces different V1 golden output, treat it as a compatibility break. Do not update goldens merely to make the test pass.

Actual Stage comparisons must still verify every compared game's fingerprint. Golden tests are an early warning; pair-time identity validation is the final protection.

---

# 10. Paired comparison rule

Paired comparison must be explicit about both **identity** and **coverage**.

## 10.1 Official comparison eligibility

Official baseline comparisons require completed runs. A partial/aborted/failed run may be inspected diagnostically, but it must not silently masquerade as a full paired baseline.

Before comparing, verify compatible run-level facts:

```text
benchmark_set_id
width
height
num_mines
first_click_policy
board_generator_version
telemetry semantic version compatibility
```

`solver_stage`, `solver_policy`, and solver configuration are expected to differ when they are the comparison target.

Compute-time comparisons additionally require compatible execution environments; see §34 and §38.

## 10.2 Explicit comparison range

The caller/statistics layer must select an explicit prefix:

```text
[0, N)
```

Both runs must contain every index in that range.

Do not use a SQL inner join that silently drops missing games.

## 10.3 Per-game identity

For every compared `game_index`, require equality of:

```text
benchmark_set_id
game_index
seed
board_fingerprint
first_click_x
first_click_y
```

Any missing row or mismatch makes the requested pair/range invalid and must be reported.

Duplicate fingerprints are allowed and remain distinct corpus entries by `game_index`.

Pilots are nested prefixes; do not add a 100-game and a 1,000-game prefix together and describe them as 1,100 independent boards.

---

# 11. Telemetry principles

Core principle:

> Raw events first, summaries second.

Standard telemetry is event-based, not frame-based.

Do not store a board snapshot after every action in standard telemetry.

Standard telemetry must be small enough for tens/hundreds of thousands of games.

Debug/full telemetry may later be added for selected seeds only.

---

# 12. Generic telemetry models

Tentative module:

```text
telemetry_model.py
```

Models should be immutable where practical.

Database-generated IDs are **not** part of pure telemetry models.

In particular:

- Python `BenchmarkRun` does not require `run_id`;
- Python `GameRecord` does not require `game_id` or `run_id`;
- Python `ActionEvent` does not require `game_id`.

Repository code attaches relational IDs at persistence time.

---

# 13. Generic inference category

Do not make generic telemetry depend on Stage 2's `DecisionKind`.

Define a telemetry-level enum conceptually:

```text
InferenceCategory
- LOCAL_DETERMINISTIC
- GLOBAL_CERTAINTY
- PROBABILITY_GUESS
```

Stage 2 adapter code maps:

```text
DecisionKind → InferenceCategory
```

This duplication is intentional.

Reason:

- Stage 2 decision types are solver implementation details;
- telemetry is intended to survive into Stage 3/4.

Mapping completeness must be tested.

---

# 14. Stage 2 decision telemetry adapter

Tentative module:

```text
simple_telemetry.py
```

It converts existing `SimpleDecision` evidence into generic telemetry facts.

Tentative immutable model:

```text
DecisionTelemetry
- inference_category
- selection_candidate_count
- target_mine_probability
- minimum_available_mine_probability
```

`decision_compute_ns` does **not** belong in `DecisionTelemetry`; timing is execution infrastructure responsibility.

## 14.1 Candidate-count semantics

`selection_candidate_count` means:

> Number of cells that actually competed in the final selector class after the solver's priority rules were applied.

It is not all hidden cells and categories are not directly comparable.

### LOCAL_DETERMINISTIC

If the selected action is FLAG:

```text
pool = deterministic_result.mine_cells
candidate_count = len(pool)
target probability = 1
minimum available probability = NULL
```

Otherwise deterministic OPEN is selected only when the mine pool is empty:

```text
pool = deterministic_result.safe_cells
candidate_count = len(pool)
target probability = 0
minimum available probability = NULL
```

### GLOBAL_CERTAINTY

If exact probability selects certain-mine FLAG:

```text
pool = all HIDDEN cells with mine_worlds == total_worlds
candidate_count = len(pool)
target probability = 1
minimum available probability = NULL
```

Otherwise global certain-safe OPEN is selected when no certain-mine pool wins priority:

```text
pool = all HIDDEN cells with mine_worlds == 0
candidate_count = len(pool)
target probability = 0
minimum available probability = NULL
```

### PROBABILITY_GUESS

The pool includes both frontier and unconstrained/floating HIDDEN cells:

```text
minimum_available_mine_probability
    = exact minimum mine probability across all selectable HIDDEN cells

pool
    = every selectable HIDDEN cell tied at that exact minimum

selection_candidate_count
    = len(pool)

target_mine_probability
    = exact probability of decision.move
```

For Stage 2:

```text
target_mine_probability == minimum_available_mine_probability
```

must hold exactly.

This equality is a Stage 2 adapter/test invariant, **not** a generic Collector invariant. Future Stage 3 risk policies are not authorized by this sentence; any risk-band policy requires a separate explicit Stage 3 specification.

## 14.2 Drift self-check

Because the adapter re-derives the final pool from Stage 2 evidence, it must fail fast if its interpretation drifts from the real selector.

At minimum, assert that:

```text
derived action type == decision.move.action
decision.move coordinate is in the derived final pool
decision.move coordinate == min(pool, key=(y,x))
```

and, for Stage 2 guesses:

```text
target probability == exact minimum probability
```

The adapter must not use hidden layout to perform these checks.

---

# 15. Probability type inside Python telemetry

Stage 2 probability is exact and based on arbitrary-size integer world counts.

Do not lose information at the collection boundary.

Python representation:

```text
Fraction | None
```

for:

- `target_mine_probability`
- `minimum_available_mine_probability`

Rules:

- initial policy OPEN → both `None`;
- deterministic/global certainty → target is exact `Fraction(0,1)` or `Fraction(1,1)`, minimum is `None`;
- probability guess → target and minimum are exact `Fraction` values in `(0,1)` for normal uncertain guesses.

SQLite persistence uses the canonical rational TEXT codec frozen in §31.

---

# 16. `simple_runner` instrumentation

Use the optional observer from §6 rather than duplicating the runner.

Small immutable trace contract:

```text
SimpleActionTrace
- move
- decision
- decision_compute_ns
- status_after
- safe_cells_opened_delta
- explicit_flag_delta
```

This is a runner-to-observer execution DTO. It is not persisted directly and is not a replacement for `ActionEvent`.

## 16.1 Compute-time boundary

For Stage 2, measure only the existing analysis/selection call:

```python
t0 = perf_counter_ns()
decision = analyze_position(observation, engine.num_mines)
t1 = perf_counter_ns()

decision_compute_ns = t1 - t0
```

Do not include Engine step, observer, Collector, Replay recording, SQLite, board generation, or static board analysis.

Initial explicit benchmark OPEN has:

```text
decision = None
decision_compute_ns = None
```

The measurement is elapsed wall time around analysis/selection, not pure CPU time and not modeled physical play time. OS scheduling and environment can affect it.

Future Stage 3 may reuse the field name only if it measures the complete decision/planning boundary from a fresh public observation to selection of the semantic action. If Stage 3 uses a materially different narrower/wider boundary, it must define a separate timing field rather than making invalid direct comparisons.

## 16.2 Observer timing

The exact observer call order is defined in §6.3.

No trace is emitted for a decision that was analyzed but never executed, such as a pending guess when `accept_guesses=False`.

Primary Stage 2 baseline uses `accept_guesses=True`, so normal benchmark games execute through terminal state.

---

# 17. Action-effect semantics

Action-effect fields are derived only from the semantic action and public observations before/after execution. They do not feed hidden information back into solver decisions.

## 17.1 `safe_cells_opened_delta`

Definition:

> Number of coordinates whose pre-action public state was `HIDDEN` or `FLAGGED` and whose post-action public state is a safe number `0..8`.

Formally:

```text
safe_cells_opened_delta = count of (x,y) where
    before[y][x] ∈ {HIDDEN, FLAGGED}
    and
    after[y][x] ∈ {0,1,2,3,4,5,6,7,8}
```

Examples:

```text
single number OPEN   → 1
flood OPEN           → >1 possible
FLAG                 → 0
CHORD                 → >1 possible
mine OPEN             → 0
losing CHORD          → count safe cells opened by that action only
```

Including `FLAGGED → safe` is intentional because current Engine flood/chord behavior can clear a wrongly flagged safe cell and reveal it.

Terminal mine-display states (`EXPLODED`, `MINE`, `FALSE_FLAG`) are never counted as safe reveals.

For a correctly instrumented completed game, this field can be summed as an additional consistency check, but Engine-internal revealed counters are not the authoritative telemetry definition.

## 17.2 `explicit_flag_delta`

Do **not** calculate this as raw `count_flags(after) - count_flags(before)`.

Definition:

> Direct flag-state change caused by the semantic input action itself, excluding automatic Engine side effects.

Generic action semantics:

```text
FLAG on HIDDEN   → +1
FLAG on FLAGGED  → -1
OPEN             → 0
CHORD            → 0
```

Current Stage 2 runner selects only HIDDEN targets, so its normal FLAG trace is `+1` and OPEN is `0`.

Excluded automatic effects include:

- win-time automatic flagging of remaining mines;
- flood/chord behavior that automatically clears a wrongly placed safe flag.

The Engine currently uses `Action.FLAG` as a toggle. Baseline Stage 3 excludes semantic UNFLAG, so no separate UNFLAG action type is added now. If a future policy intentionally unflags, `explicit_flag_delta=-1` preserves that effect without redefining current fields.

---

# 18. ActionEvent

Tentative generic Python model:

```text
ActionEvent
- action_index

- inference_category
- selection_candidate_count
- target_mine_probability
- minimum_available_mine_probability
- decision_compute_ns

- action_type
- x
- y

- status_after
- safe_cells_opened_delta
- explicit_flag_delta
```

Coordinate naming follows the existing project:

```text
(x, y)
observation[y][x]
```

Do not introduce `row/col` unless a concrete interoperability need appears.

## 18.1 Initial event

Benchmark initial OPEN is event index `0`.

It has no inference metadata.

## 18.2 Event index ownership

Collector owns the index:

```text
action_index = len(events)
```

Indices must be contiguous:

```text
0..N-1
```

No separate event ID is needed in the Python model.

---

# 19. TelemetryCollector

Tentative module:

```text
telemetry_collector.py
```

Collector is one-game in-memory state.

Responsibilities:

- accept already-executed action facts
- create immutable ActionEvents
- reject events after terminal
- maintain contiguous event sequence
- finalize one GameRecord from the raw event list
- validate summary ↔ raw consistency

Collector must **not**:

- call solver
- execute Engine actions
- read SQLite
- calculate Stage 2 selector semantics
- become a second game-rules engine

---

# 20. GameRecord

Tentative summary:

```text
GameRecord
- game_index
- seed
- board_fingerprint

- first_click_x
- first_click_y

- result

- total_actions
- open_count
- flag_count
- chord_count

- local_deterministic_count
- global_certainty_count
- probability_guess_count

- had_probability_guess
- first_guess_action_index

- board_3bv
- board_ops

- compute_time_total_ns
- compute_time_max_ns
```

`termination_reason` and per-game `error_code` are intentionally **deferred from v1**. Under the v1 fail-fast policy, committed games are normal WIN/LOSS outcomes; technical-failure games are rolled back rather than persisted. If future policy stores technical/aborted game rows, those fields may be added then.

Summary values should be derived from immutable raw ActionEvents during finalization where practical.

## 20.1 Required invariants

```text
total_actions
= open_count + flag_count + chord_count
= len(ActionEvents)
```

For the primary Stage 2 baseline, which has exactly one policy initial OPEN followed by analyzed decisions:

```text
local_deterministic_count
+ global_certainty_count
+ probability_guess_count
= total_actions - 1
```

This is a Stage 2 benchmark validation rule, not a universal database invariant for every future solver.

Guess invariant:

```text
guess_count == 0
↔ had_probability_guess == false
↔ first_guess_action_index == NULL
```

and:

```text
guess_count > 0
↔ had_probability_guess == true
↔ first_guess_action_index points to first guess event
```

Compute invariant:

```text
compute_time_total_ns
= sum(non-null event decision_compute_ns)
```

```text
compute_time_max_ns
= max(non-null event decision_compute_ns)
```

If there are no analyzed decisions:

```text
compute_time_total_ns = 0
compute_time_max_ns = NULL
```

---

# 21. Game result semantics

Committed v1 game rows have exactly one authoritative outcome:

```text
WIN
LOSS
```

Mapping:

```text
Engine WON  → WIN
Engine LOST → LOSS
```

A normal probability-guess mine hit is a committed LOSS.

Technical solver/Engine/telemetry/repository failures must **not** be counted as losses. Under v1 fail-fast behavior:

```text
technical failure
→ rollback current game's persistence transaction if open
→ do not persist a technical-error GameRecord
→ stop starting new games
→ fail the BenchmarkRun
```

Technical failure detail belongs to run-level `failure_code` when it can be persisted.

This simple result domain is deliberate. Per-game error/aborted outcomes may be added later only if the run policy changes to persist such games.

---

# 22. Board 3BV / Ops

`board_3bv` and `board_ops` are static evaluation-only metrics.

Current architecture defines:

```text
Ops = number of 8-connected zero regions
3BV = Ops + isolated number cells
```

The benchmark may run `analyze_board(snapshot)` for evaluation even though `reset_with_mines()` already performs static Engine analysis internally.

This duplicates computation.

The duplication is accepted initially because avoiding it would require changing Engine public API or returning internal static analysis data.

Measure it in the pilot before optimizing.

---

# 23. BenchmarkRunner

Tentative module:

```text
benchmark_runner.py
```

Responsibilities:

- create a BenchmarkRun
- iterate requested game indices
- generate deterministic BenchmarkBoard
- create fresh Engine per game in v1
- `reset_with_mines()`
- validate installed board identity
- create Collector
- invoke the one-game executor
- translate Stage 2 decision traces through adapter
- finalize GameRecord
- persist complete game transaction
- expose progress
- finalize run status

BenchmarkRunner must not duplicate inference logic.

---

# 24. Fresh Engine policy

v1 should create a fresh `MinesweeperEngine` per benchmark game.

Reason:

- strongest state isolation;
- simplest correctness model;
- avoids accidental cross-game state leakage.

If pilot profiling proves Engine construction materially expensive, reuse may be considered later.

Solver `decision_compute_ns` is unaffected because Engine creation is outside the measured boundary.

---

# 25. Stage 2 baseline solver configuration

Primary Stage 2 baseline must allow actual guesses:

```text
accept_guesses = True
initial_open = (0, 0)
```

Otherwise the fixed-board run would either stop before real guesses or fail to reproduce the fresh-game first-click policy.

`solver_config_snapshot` must record at least these policy values together with any other Stage 2 configuration that can affect decisions.

The baseline reports:

- Win Rate
- Guess Game Rate
- Guess Count
- Guess probabilities
- inference categories
- decision compute time

If the benchmark executor unexpectedly returns `GUESS_REQUIRED` under this configuration, treat it as a benchmark invariant failure.

---

# 26. Run lifecycle

States:

```text
CREATED
RUNNING
COMPLETED
ABORTED
INTERRUPTED
FAILED
```

Expected normal transition:

```text
CREATED → RUNNING → COMPLETED
```

Intentional stop:

```text
RUNNING → ABORTED
```

Caught fatal benchmark failure:

```text
RUNNING → FAILED
```

`INTERRUPTED` is reserved for a stale run later identified as having died without normal finalization, such as process kill, crash, or power loss. Automatic stale-run recovery is deferred.

A database failure can make even the final `FAILED` status update impossible. Therefore fatal-failure behavior is:

```text
rollback current game transaction when possible
→ do not start another game
→ best-effort mark run FAILED in a separate transaction
→ propagate the failure
```

If that status update also fails, a persisted `RUNNING` row may remain. This is an acknowledged v1 limitation tied to deferred stale-run recovery, not a reason to implement a recovery framework now.

---

# 27. Stop behavior

Do not add cancellation checks inside exact probability enumeration in v1.

If stop is requested while more games remain:

```text
finish current game
→ commit current completed game
→ do not start another game
→ mark run ABORTED
```

If the requested range has already been fully completed by the time the stop request is observed, finalize as `COMPLETED`, not `ABORTED`.

A very expensive single decision may therefore delay stop. Immediate/deep cancellation remains deferred because it would expand scope into solver internals.

---

# 28. BenchmarkRun

Tentative pure model fields:

```text
telemetry_schema_version

created_at
started_at
finished_at
run_status

git_commit
git_dirty
app_version

solver_stage
solver_policy
solver_config_snapshot

width
height
num_mines
difficulty_name

first_click_policy
board_generator_version
benchmark_set_id

requested_games
processed_games

environment_snapshot
failure_code
```

Requirements:

- `git_commit` is required;
- `git_dirty` is required;
- `benchmark_set_id` is required for benchmark runs;
- `git_dirty` is computed once at run start from the non-ignored Git working tree as defined in §34.1;
- official baseline execution requires `git_dirty == false`;
- development pilots may be dirty, but must retain that fact and are not official-baseline eligible.

Do not store wins/losses/rates directly in BenchmarkRun v1; derive them from games.

`processed_games` intentionally means:

> Number of complete game transactions successfully committed for this run.

Invariant:

```text
processed_games == COUNT(games for run_id)
```

`COMPLETED` requires:

```text
processed_games == requested_games
```

and, for v1 prefix runs, exact game-index coverage `{0, ..., requested_games-1}`.

---

# 29. SQLite architecture

Tentative modules:

```text
telemetry_schema.py
telemetry_repository.py
```

`telemetry_schema.py` owns:

- DDL;
- physical schema version;
- stable persistence enum/string constants;
- minimal schema initialization / minimal migration boundary.

`telemetry_repository.py` owns:

- connections and PRAGMA initialization;
- transactions;
- inserts;
- run-status updates;
- persistence queries;
- model ↔ persistence codecs, including exact rational TEXT.

`benchmark_statistics.py` may issue read-only aggregation queries directly or through repository query helpers, but it must import persistence constants rather than duplicating magic integer/string values.

Repository must not contain game legality rules, Stage 2 inference semantics, or 3BV calculation.

---

# 30. SQLite table relationships

v1 uses three main tables:

```text
benchmark_runs
    1 ───── N games
                1 ───── N action_events
```

Foreign keys:

```text
games.run_id
→ benchmark_runs.run_id
ON DELETE CASCADE

action_events.game_id
→ games.game_id
ON DELETE CASCADE
```

Enable on every connection:

```sql
PRAGMA foreign_keys = ON;
```

---

# 31. Probability persistence representation — RESOLVED

Python telemetry remains exact `Fraction`.

SQLite authoritative representation is canonical reduced rational `TEXT` for both probability fields.

## 31.1 Canonical codec

Every non-null probability is stored exactly as:

```text
"numerator/denominator"
```

Examples:

```text
Fraction(0,1) → "0/1"
Fraction(1,1) → "1/1"
Fraction(1,3) → "1/3"
```

Canonical requirements:

- numerator is a base-10 nonnegative integer with no sign or leading zeros except `0`;
- denominator is a base-10 positive integer with no leading zeros;
- fraction is reduced to lowest terms;
- denominator is positive;
- value must satisfy `0 <= p <= 1`;
- serialization of a parsed value must reproduce the exact stored string.

The repository codec should construct/validate with Python `Fraction` and an explicit canonical formatter. Do not rely on permissive `Fraction(text)` parsing alone.

## 31.2 Nullability semantics

```text
initial policy OPEN
    target = NULL
    minimum = NULL

deterministic/global certainty
    target = "0/1" or "1/1"
    minimum = NULL

probability guess
    target = exact rational TEXT
    minimum = exact rational TEXT
```

For Stage 2 guesses the two exact values are equal, but both columns are retained because they preserve risk-discipline auditability and future policy comparison.

## 31.3 Rejected/deferred representations

Do not use `REAL` as the authoritative probability because exactness cannot be recovered from it.

Do not use SQLite INTEGER numerator/denominator as the general exact representation because Stage 2 world counts can exceed SQLite's signed 64-bit integer range.

A derived approximate `REAL` analytics column is deferred. It may be added later from the exact TEXT source if profiling/query requirements justify it.

A custom BLOB codec is also deferred because current evidence does not justify the extra complexity.

The v1 codec is required to round-trip every probability value reachable in the benchmark domain exactly, including values well beyond SQLite signed 64-bit INTEGER range and representative values around the theoretical Expert-board world-count scale. It does **not** claim unlimited decimal-string conversion independent of CPython's integer-string safety limits. The codec must not change the process-global `sys.set_int_max_str_digits()` setting.

## 31.4 SQL semantics of rational TEXT

Canonical rational TEXT is an **opaque exact persistence value** to SQLite, not a numeric SQL type.

Safe SQL operations include exact identity/grouping operations whose meaning depends only on canonical string equality, such as:

```text
=
!=
DISTINCT
GROUP BY
COUNT
```

Do **not** use the probability TEXT directly for numeric ordering or arithmetic, including:

```text
< / > / <= / >=
ORDER BY probability as numeric order
MIN / MAX
AVG / SUM
CAST(... AS REAL)
arithmetic expressions
```

For numeric probability statistics, decode through the repository codec to Python `Fraction` and compute/order in `benchmark_statistics.py` or the equivalent statistics layer.

Example that must be covered by tests:

```text
"1/3" and "2/9"
```

Lexicographic SQL `MIN` is not the mathematical minimum, and SQLite numeric coercion/casting of `"n/d"` is not a valid fraction conversion.

# 32. SQLite physical schema

## 32.1 Schema version

Use:

```sql
PRAGMA user_version
```

for SQLite physical schema version.

Keep it separate from `telemetry_schema_version`, which describes telemetry semantics.

A separate schema metadata table is not required for v1.

## 32.2 `benchmark_runs`

Conceptual columns:

```text
run_id INTEGER PRIMARY KEY

telemetry_schema_version INTEGER NOT NULL

created_at TEXT NOT NULL
started_at TEXT NULL
finished_at TEXT NULL

run_status TEXT NOT NULL

git_commit TEXT NOT NULL
git_dirty INTEGER NOT NULL
app_version TEXT NULL

solver_stage TEXT NOT NULL
solver_policy TEXT NOT NULL
solver_config_snapshot TEXT NOT NULL

width INTEGER NOT NULL
height INTEGER NOT NULL
num_mines INTEGER NOT NULL
difficulty_name TEXT NULL

first_click_policy TEXT NOT NULL
board_generator_version TEXT NOT NULL
benchmark_set_id TEXT NOT NULL

requested_games INTEGER NOT NULL
processed_games INTEGER NOT NULL DEFAULT 0

environment_snapshot TEXT NOT NULL
failure_code TEXT NULL
```

Structural checks include:

```text
width > 0
height > 0
0 <= num_mines < width*height
requested_games > 0
0 <= processed_games <= requested_games
git_dirty IN (0,1)
COMPLETED → processed_games=requested_games
```

## 32.3 `games`

Conceptual columns:

```text
game_id INTEGER PRIMARY KEY

run_id INTEGER NOT NULL
game_index INTEGER NOT NULL
seed INTEGER NOT NULL

board_fingerprint TEXT NOT NULL

first_click_x INTEGER NOT NULL
first_click_y INTEGER NOT NULL

result INTEGER NOT NULL

total_actions INTEGER NOT NULL
open_count INTEGER NOT NULL
flag_count INTEGER NOT NULL
chord_count INTEGER NOT NULL

local_deterministic_count INTEGER NOT NULL
global_certainty_count INTEGER NOT NULL
probability_guess_count INTEGER NOT NULL

had_probability_guess INTEGER NOT NULL
first_guess_action_index INTEGER NULL

board_3bv INTEGER NOT NULL
board_ops INTEGER NOT NULL

compute_time_total_ns INTEGER NOT NULL
compute_time_max_ns INTEGER NULL
```

Required uniqueness:

```text
UNIQUE(run_id, game_index)
```

Do not require seed or fingerprint uniqueness.

Persisted `board_fingerprint` must satisfy the 64-character lowercase-hex contract. Python validates the complete codec; DB may enforce stable shape checks such as length/lowercase/hex domain.

Stable same-row arithmetic checks may include:

```text
total_actions = open_count + flag_count + chord_count
had_probability_guess IN (0,1)
probability_guess_count = 0 → had_probability_guess = 0 and first_guess_action_index IS NULL
probability_guess_count > 0 → had_probability_guess = 1 and first_guess_action_index IS NOT NULL
```

Cross-row/raw-event consistency remains Python/repository-test responsibility.

## 32.4 `action_events`

Conceptual columns:

```text
game_id INTEGER NOT NULL
action_index INTEGER NOT NULL

inference_category INTEGER NULL
selection_candidate_count INTEGER NULL

target_mine_probability TEXT NULL
minimum_available_mine_probability TEXT NULL

decision_compute_ns INTEGER NULL

action_type INTEGER NOT NULL
x INTEGER NOT NULL
y INTEGER NOT NULL

status_after INTEGER NOT NULL

safe_cells_opened_delta INTEGER NOT NULL
explicit_flag_delta INTEGER NOT NULL

PRIMARY KEY(game_id, action_index)
```

v1 uses:

```sql
WITHOUT ROWID
```

for `action_events` because `(game_id, action_index)` is the natural key and current evidence shows a meaningful storage reduction without a demonstrated insert bottleneck.

Do not add an event surrogate ID.

Stable structural range/domain checks belong in SQL. Stage 2 selector semantics, action-0 null patterns, exact candidate-pool meaning, and `target==minimum` remain Python/adapter validation rather than SQL CHECK logic.

---

# 33. Persistence enum mapping

Do not persist implementation enum numeric values implicitly.

Stable persistence mappings/constants are owned by `telemetry_schema.py` and shared by repository/statistics code.

Freeze v1 mappings:

```text
Action
1 = OPEN
2 = FLAG
3 = CHORD

InferenceCategory
1 = LOCAL_DETERMINISTIC
2 = GLOBAL_CERTAINTY
3 = PROBABILITY_GUESS

StatusAfter
1 = PLAYING
2 = WON
3 = LOST

GameResult
1 = WIN
2 = LOSS
```

Run status and policy identifiers are persisted as explicit stable strings rather than Python enum `.value` by accident.

Core Engine enum ordering must never silently determine DB meaning.

---

# 34. Timestamps, provenance, and snapshots

Store timestamps as UTC ISO-8601 text. UI may render local time.

`solver_config_snapshot` and `environment_snapshot` are deterministic JSON serialized to TEXT, e.g.:

```python
json.dumps(value, sort_keys=True, separators=(",", ":"))
```

## 34.1 Source provenance

Record:

```text
git_commit
git_dirty
```

`git_dirty` is computed **once at run start**.

For Revision 2, the canonical clean-tree check is equivalent to:

```bash
git status --porcelain=v1 --untracked-files=all
```

`git_dirty = false` only when that command produces no entries. Therefore staged changes, unstaged changes, and non-ignored untracked files all make the run dirty. Ignored generated outputs such as benchmark databases, caches, or build artifacts do not make the run dirty; files that are legitimate generated outputs should be covered by `.gitignore` rather than special-cased in telemetry code.

Minimum official-baseline eligibility is a **derived predicate**, not another database column:

```text
run_status == COMPLETED
AND git_dirty == false
AND exact requested v1 prefix coverage is verified
```

Official execution mode must reject a dirty working tree before creating the benchmark run row. Development pilots may be dirty, but they retain `git_dirty=true` and are not official-baseline eligible.

This rule intentionally favors a simple reproducible provenance contract over trying to classify which individual untracked source files are "execution-relevant."

## 34.2 Minimum environment snapshot

Include at least:

```text
Python implementation
Python version
platform / OS
machine architecture
CPU count
CPU identifier/model when readily available
SQLite version
perf_counter clock information
```

Also record relevant application version metadata when available.

Do not turn environment capture into a hardware inventory framework.

Compute-time comparisons should be treated as directly comparable only when the relevant environment/provenance keys are compatible. Modeled Stage 3 physical time is a separate metric and must not be conflated with Python elapsed compute time.

---

# 35. Game transaction boundary

One completed game is the atomic persistence unit.

Do not hold a SQLite transaction open while the solver is playing the game.

After a game has completed and its `GameRecord`/events are finalized:

```text
BEGIN

INSERT games(...)
→ get game_id

bulk INSERT action_events(game_id, ...)

UPDATE benchmark_runs
SET processed_games = processed_games + 1

COMMIT
```

On any failure inside that transaction:

```text
ROLLBACK
```

The DB must not contain:

- a partial action stream for a committed game;
- action rows without the game;
- a committed game without its corresponding processed-count increment.

Use batch insertion (`executemany` or equivalent), never one transaction per action.

If a persistence failure makes the database unwritable, the later best-effort run-status update may also fail; §26 defines that limitation.

---

# 36. SQLite operating mode

Every connection must initialize and verify:

```sql
PRAGMA foreign_keys = ON;
```

v1 database mode:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
```

Rationale:

- WAL supports the intended local writer + statistics-reader workflow;
- current profiling does not identify SQLite insertion as the Stage 2 bottleneck;
- therefore v1 starts with the more conservative durability setting rather than trading durability for unneeded speed.

`synchronous=NORMAL` is **not rejected forever**. Reconsider it after representative pilot measurement if database durability sync is shown to be a material bottleneck and the reduced recent-commit durability is acceptable.

UI/statistics readers should keep read transactions short enough not to unnecessarily delay WAL checkpointing. Do not build a custom checkpoint-management framework without evidence.

---

# 37. Index policy

Start minimal.

Existing keys already support:

- run lookup
- per-run game order
- per-game action order

Do not preemptively create indexes on every statistic field.

After pilot, use `EXPLAIN QUERY PLAN` to guide additional indexes.

Avoid index bloat on the high-volume action table without evidence.

---

# 38. Statistics layer

Tentative module:

```text
benchmark_statistics.py
```

It owns derived benchmark statistics, not UI presentation.

## 38.1 Coverage first

Every statistics result must identify the run status and coverage used.

Official baseline statistics require a valid completed requested prefix. Diagnostic statistics from partial runs may be shown, but must visibly report requested/processed coverage and must not be silently treated as complete.

## 38.2 Initial definitions

At minimum report:

- processed games;
- wins;
- losses;
- win rate;
- games with probability guess;
- guess-game rate;
- mean/distribution of guess count;
- probability-guess event distribution;
- local/global/guess action counts;
- total actions;
- OPEN/FLAG/CHORD counts;
- compute-time total/mean/max and useful percentiles;
- 3BV distributions.

Definitions:

```text
win_rate = WIN / (WIN + LOSS)

guess_game_rate = games_with_guess / (WIN + LOSS)

mean_guess_count
    = mean probability_guess_count across all WIN/LOSS games
      including zero-guess games

mean_decision_compute_ns
    = sum(non-null decision_compute_ns)
      / count(non-null decision_compute_ns)
```

If there are no analyzed decisions, mean decision compute time is `NULL`, not zero.

The default probability distribution observation unit is one `PROBABILITY_GUESS` ActionEvent. If a different unit is reported, label it explicitly.

## 38.3 Interpretation boundaries

The primary corpus is conditional on `FIRST_CLICK_FIXED_0_0`, which guarantees only that first cell is safe, not that it is a zero opening. Reported win/guess statistics must retain that corpus condition and should not be presented as directly representative of every Minesweeper first-click policy.

Compute-time comparisons are diagnostic and environment-sensitive. They are not the Stage 3 modeled physical-play objective.

Technical failures are never reclassified as losses.

---

# 39. Graph/UI direction

The graph layer remains a Pre-Stage 3 / Stage 1 statistics-expansion deliverable, but it is **not part of the proof that the benchmark backend is correct**.

Implement it only after backend pilot data and aggregation semantics are validated.

Preferred in-app plotting library:

```text
PyQtGraph
```

Matplotlib may later be used for report/export-quality static figures if needed; do not implement both initially.

UI must consume aggregation results rather than calculate SQL/statistics semantics itself.

Avoid growing `ui_manager.py` into a statistics/plotting monolith. A small dedicated presentation/widget module is preferred once the UI step begins.

---

# 40. Human history vs solver benchmark

Human player history and solver benchmark telemetry do not need to share the same database schema.

They may share aggregation concepts, graph widgets, and visual presentation patterns.

Do not force a single generalized schema merely for apparent reuse.

---

# 41. Replay separation

`ReplayEvent` and `ActionEvent` remain distinct.

Replay purpose:

> reproduce a game

Telemetry purpose:

> measure solver decisions, inference, effects, and performance

Do not merge them.

The current Stage 2 runner always records replay information. For very large benchmark runs, replay construction overhead may later be profiled.

Do not add a `record_replay=False` optimization until pilot evidence shows meaningful cost.

If such an option is later added, existing default replay behavior must remain backward-compatible and tested.

---

# 42. Standard vs debug telemetry

v1 standard telemetry:

- one ActionEvent per semantic action
- one GameRecord per game
- no board snapshot per event
- no full candidate list per decision

Future debug telemetry may include full candidates, additional probability evidence, or board-state checkpoints for selected seeds only.

Do not store debug-scale data for the full 100k corpus by default.

---

# 43. Validation ownership

## Database

Enforce stable structural facts:

- FK integrity;
- unique `(run_id, game_index)`;
- primary `(game_id, action_index)`;
- stable enum/domain values;
- basic numeric ranges;
- processed/requested bounds;
- same-row summary arithmetic suitable for stable CHECK constraints.

Do not encode solver-selection semantics into SQL CHECK constraints.

## Python model / Collector

Enforce:

- structural nullability rules;
- action-index continuity;
- no events after terminal;
- summary/raw consistency;
- guess-summary consistency;
- compute aggregation consistency;
- initial policy event null pattern;
- complete terminal game finalization.

## Stage 2 adapter/tests

Enforce:

- complete `DecisionKind → InferenceCategory` mapping;
- exact final competition pool/candidate count;
- FLAG-priority semantics;
- deterministic/global probability `0/1` semantics;
- Stage 2 guess `target == exact minimum`;
- adapter drift self-check against actual `decision.move` and `(y,x)` selector tie-break.

These checks use public decision evidence, not hidden layout.

## Benchmark evaluator / integration tests

May use the known fixed board **after/beside solver execution** to audit evaluation facts such as generated board identity and representative certainty soundness. Hidden layout must never become solver input.

## Engine / Runner

Enforce:

- action legality;
- target-visibility contract;
- explicit initial-open preconditions;
- fresh observation after action;
- progress contract;
- terminal handling;
- observer ordering.

Do not duplicate responsibilities across layers without a concrete reason.

---

# 44. File boundary — tentative

Expected new files:

```text
benchmark_board.py
telemetry_model.py
simple_telemetry.py
telemetry_collector.py
telemetry_schema.py
telemetry_repository.py
benchmark_runner.py
benchmark_statistics.py
```

Expected existing modification:

```text
simple_runner.py
```

Potentially no initial changes required in:

```text
core_engine.py
simple_algorithm.py
simple_probability.py
simple_decision.py
board_snapshot.py
board_analyzer.py
Replay modules
ui_manager.py
```

`ui_manager.py` changes belong to the later graph/statistics UI step.

This file split is a design target, not a command to create every file before its responsibility is needed.

---

# 45. No unnecessary generic abstractions

Do not create these preemptively:

```text
TelemetryService
generic EventBus
generic Solver interface hierarchy
generic DecisionResult replacing SimpleDecision
generic GameSession framework
plugin telemetry registry
generic storage backend interface
```

A new abstraction should be introduced only when it has a concrete current responsibility or a second real implementation pressure.

`simple_telemetry.py` is justified only as the Stage 2 → generic telemetry semantic adapter.

---

# 46. Pilot strategy

Before the full baseline:

```text
unit/integration fixtures
→ ~100 games
→ ~1,000 games
→ 10,000 games
```

Validate and record:

- reproducibility/golden checks;
- event/summary invariants;
- paired identity behavior;
- DB and WAL growth;
- transaction/failure behavior;
- exact probability codec;
- per-game action/event counts;
- game wall-duration distribution;
- decision compute-time distribution and maximum/tail cases;
- basic aggregation;
- query plans;
- replay overhead if still relevant;
- duplicate static-analysis cost if still relevant.

After the 10k run, explicitly decide whether the expected 100k operational duration justifies adding chunked/non-prefix run support or resume. Do not add those mechanisms before evidence.

Then proceed to:

```text
100,000-game baseline
```

provided the same core data model remains stable.

1M games is not a v1 completion requirement.

---

# 47. Completion and Stage 3 readiness criteria

## 47.1 Backend validation gate

The Stage 2 benchmark backend is validated when:

- Generator V1 is deterministic under its reference contract and golden-tested;
- canonical fingerprint encoding is frozen and verified;
- same benchmark indices reproduce matching fingerprints;
- explicit first OPEN policy is reproduced correctly;
- hidden layout cannot enter solver decisions;
- Stage 2 baseline executes guesses through terminal state;
- ActionEvents run contiguously from index 0 through terminal action;
- GameRecord summaries match raw events;
- exact probability survives persistence round-trip;
- one game is one atomic DB transaction;
- run progress matches committed games and exact prefix coverage;
- paired-comparison mismatch/missing rows are rejected;
- core aggregate statistics and denominators are validated;
- representative 100/1k/10k runs are operationally stable;
- baseline provenance includes commit/config/environment and official baselines satisfy the §34.1 clean-tree eligibility rule.

Reaching this gate means the **measurement design is trustworthy enough to freeze its schema/semantics**. It does not yet mean the full Pre-Stage 3 work is finished.

## 47.2 Full Stage 2 baseline

The intended full Stage 2 baseline target is:

```text
100,000 games of EXPERT_GENERAL_V1
```

If the 10k pilot proves a concrete operational need for chunking/resume, resolve that narrowly before the 100k run rather than redesigning the telemetry model.

The completed full baseline must retain its database/results together with commit, configuration, environment, benchmark-set identity, and specification version.

## 47.3 Graph/UI completion

Basic statistics/graph UI remains part of Pre-Stage 3 project work, but it is **not part of the proof that the backend measurements are correct**.

Implement it only after validated backend aggregation exists, using the same statistics layer. Do not change Stage 2 benchmark semantics merely to make graph implementation easier.

## 47.4 Stage 3-A transition

Project-level Pre-Stage 3 is complete when:

- the validated backend/schema is frozen;
- the intended full Stage 2 baseline has been completed and preserved;
- basic statistics/graph presentation can consume the validated aggregation results.

Only then should Stage 3-A implementation begin changing solver/action-selection behavior, unless the project explicitly records a later decision to change this stage boundary.

Stage 3-A must compare against the frozen Stage 2 baseline on explicitly paired boards.

---

# 48. Required tests — high level

At minimum, add tests for:

## Benchmark board

- first-click coordinate never mined;
- surrounding cells remain eligible mines;
- deterministic seed output;
- representative golden fingerprints for 0/1/2/42/999/99999;
- first-1,000 fingerprint prefix digest equals `93852d335a46af9420dbdcdf0e256bb9149778f33602f6a4facdf0295677777c` under the exact §9.2 SHA-256/LF contract;
- canonical fingerprint encoding independent of input set/iteration order;
- duplicate fingerprint allowed;
- generator does not mutate global RNG;
- Generator V1 representative placement is equivalent to current Engine first-open exclusion policy.

## Runner instrumentation

- default current semantics remain unchanged;
- `initial_open` validation happens before Engine mutation;
- explicit benchmark initial OPEN executes exactly once;
- explicit initial OPEN bypasses solver;
- initial trace has `decision=None` / null inference/compute metadata;
- compute timer wraps only `analyze_position()`;
- observer called exactly once per successful executed action after fresh observation and runner validation;
- terminal action is observed once;
- pending/unexecuted guess produces no trace;
- observer exception propagates;
- terminal Engine receives no extra action/trace;
- hidden board is not consulted for initial-open safety;
- guess behavior remains unchanged outside benchmark configuration.

## Stage 2 adapter

- local safe and local mine pool counts;
- global 0% and 100% pool counts;
- exact minimum guess tie count including unconstrained/floating cells;
- exact Fraction preserved;
- mapping exhaustiveness;
- derived pool/action matches actual `decision.move`;
- `(y,x)` tie-break self-check;
- Stage 2 guess target equals exact minimum.

## Collector/model

- contiguous indices;
- terminal event blocks later records;
- counts derived correctly;
- initial-event nullable pattern;
- guess summary correct;
- compute total/max correct;
- zero-decision game uses total=0/max=NULL;
- `safe_cells_opened_delta` counts `FLAGGED → safe`;
- automatic win flags/flood unflags do not corrupt `explicit_flag_delta`.

## Probability persistence

- canonical `0/1`, `1/1`, and ordinary fraction round-trip;
- exact round-trip for values beyond SQLite signed 64-bit INTEGER range and representative ~100-digit benchmark-domain values;
- noncanonical/malformed values rejected;
- codec does not mutate process-global `sys.set_int_max_str_digits()`;
- rational TEXT is never treated as numeric SQL: the `"1/3"` / `"2/9"` fixture proves numeric ordering/aggregation must decode to `Fraction`;
- authoritative comparisons never use derived float approximation.

## Repository

- FK enabled and verified for every connection;
- WAL/FULL initialization;
- one-game atomic transaction;
- rollback on game/action/progress failure;
- processed count increments in the same transaction;
- `(run_id, game_index)` uniqueness;
- required `benchmark_set_id`;
- stable enum mapping;
- `WITHOUT ROWID` action table schema;
- cascading delete behavior;
- completed-run processed-count invariant;
- best-effort FAILED path behavior tested where practical.

## Statistics / pairing

- completed prefix coverage validation;
- missing pair rejected rather than silently dropped;
- fingerprint/seed/first-click mismatch rejected;
- win/guess denominators correct;
- mean guess count includes zero-guess games;
- partial run statistics display coverage and are not treated as official full baselines.

## Integration

- generated board → Engine → explicit initial OPEN → Stage 2 runner → telemetry → DB;
- persisted fingerprint matches actual played board;
- primary baseline stores ActionEvent 0 as policy OPEN with null inference metadata;
- official paired runs retrieve and validate every requested identity field;
- provenance test covers staged, unstaged, and non-ignored untracked files; official mode rejects dirty state before run creation; eligibility is derived from COMPLETED + clean tree + exact prefix coverage.

---

# 49. Revision 2 delta-review closure

Revision 2 received two independent delta reviews after the earlier full-audit/adjudication cycle.

Both reviewers concluded:

```text
Ready to freeze for implementation: YES
```

No implementation blocker remained.

The accepted final corrections before freeze were:

1. freeze §9.2 as SHA-256 over LF (`0x0A`) joined lowercase fingerprint ASCII bytes with no trailing newline, and include verified golden values;
2. define `git_dirty` over the complete non-ignored Git working tree and define official-baseline eligibility as a derived predicate;
3. state explicitly that canonical rational TEXT is opaque to SQLite numeric semantics and must be decoded to `Fraction` for numeric statistics;
4. scope exact probability round-trip to the benchmark domain, including values beyond SQLite 64-bit INTEGER range, without changing CPython's global integer-string safety setting.

These corrections clarify already-adjudicated choices. They do not redesign Stage 1/2, change the selected persistence representation, or add a new framework.

# 50. Freeze record

Revision 2 is frozen for Pre-Stage 3 implementation.

Freeze basis:

```text
reviewed main commit:
f11bc199e093e54cdda1d258d5977fe4cb14a261

delta-review candidate SPEC SHA-256:
0d138ca2cce23dc2a73eb8ea6903e0be9ca1b61584beb63e8e587d79d5ab2afd

independent delta-review verdicts:
YES / YES

remaining implementation blockers:
none
```

The candidate SPEC hash above identifies the exact pre-freeze document reviewed by both reviewers. This frozen file differs from that candidate only by the accepted non-blocking corrections summarized in §49 and the status/freeze-record updates.

# 51. Revision 2 decisions summary

Frozen design decisions in Revision 2:

```text
SQLite persistence
raw events + derived summaries
fixed reproducible paired boards
EXPERT_GENERAL_V1 prefix stream
seed = game_index
first click fixed at (0,0)
exclude first-click cell only
Generator V1 reference runtime = CPython 3.12.14
SHA-256 canonical layout fingerprint with frozen binary encoding
one ActionEvent per executed semantic action
first OPEN = event 0, not inference
exact Python Fraction probabilities
canonical exact SQLite rational TEXT "n/d"
one GameRecord per committed WIN/LOSS game
one completed game = one DB transaction
processed_games retained intentionally
benchmark_set_id required
fresh Engine per game initially
fail-fast on technical failure
best-effort FAILED run-status persistence
Stage 2 baseline accept_guesses=True
run_simple explicit initial_open + optional observer
action_events WITHOUT ROWID
WAL + synchronous=FULL initially
official baseline requires clean non-ignored Git working tree provenance
explicit paired-prefix coverage validation
PyQtGraph later for in-app graphs
```

Intentional v1 deferrals:

```text
custom stable PRNG/sampling implementation
parallelism / multi-process writer
resume/recovery implementation
chunked/non-prefix run ranges unless 10k pilot justifies them
archive/sharding
per-game technical ERROR rows / termination_reason / error_code
record_replay=False optimization
derived REAL probability column
extra action-table indexes without EXPLAIN evidence
debug snapshots/full candidate lists at scale
deep cancellation inside probability solver
Stage 3 physical timing/planner telemetry
generic research-platform abstractions
```

Items that must be revisited only if pilot evidence demands it:

```text
100k operational chunking/resume
synchronous=NORMAL
additional indexes
Engine reuse
removing duplicate static analysis
replay suppression
```

Revision 2 has completed independent delta review and is frozen for implementation. Further architecture review is not required unless implementation or pilot evidence reveals a concrete defect.

---

# 52. Final principle

The purpose of this infrastructure is not to maximize the amount of telemetry.

It is to make this statement defensible:

> Stage 2 and later stages were evaluated on reproducible paired boards, under explicitly recorded solver policies, with event-level evidence sufficient to reconstruct the reported statistics without giving the solver hidden information.

Anything beyond what is needed to support that statement should require separate justification.
