# Stage-3 implementation — Slice A

Date: 2026-10-06 (Asia/Seoul). Branch: `feature/stage3-implementation`.
Starting HEAD: `d9e89ec56374720183b166552f2160796c8a66ef`.
The initial worktree was clean. This slice adds files only; existing tracked
production, experimental, calibration, and specification files are unchanged.
No commit or push was performed.

## Frozen identity and scope

Authoritative specification: `STAGE3_ALGORITHM_SPEC_v1.md`.
Its HEAD blob SHA-256 is
`6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33`.
The Windows working copy has CRLF, with raw SHA-256
`b3bd97fbe0a0da4db73d107ea83678a6f17ff40aa90d639f61ac1d45ffc54f21`.
Replacing CRLF with LF produces exactly the HEAD blob and the requested frozen
SHA. Neither copy was edited.

Physical profile raw SHA-256:
`52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
Timing table SHA-256:
`7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b`.
Both are validated by production code and focused tests.

Frozen algorithm deviations found: **0**. Hidden-information dependencies in
planner decisions or execution-admissibility checks found: **0**. Independent
source review and public-boundary tests support these findings; finite tests
are not a proof over every possible board.

## Added files and responsibilities

| File | Responsibility |
| --- | --- |
| `stage3_physical.py` | Authenticate profile bytes, metadata and independently encoded table; return immutable positive integer 30x16 timing table; exact displacement plus input cost. |
| `stage3_planner.py` | Reuse Stage-2 analysis; generate direct and whole-clue FLAG-setup reveal plans; exact Held-Karp routing, strict dominance, exact E-FIRST selection, nearest certain-FLAG fallback, unchanged Stage-2 guess. |
| `stage3_runner.py` | Canonical first OPEN and cursor; time complete analysis plus planning; validate public execution evidence; execute one action; record public deltas and integer modeled cost; fresh observation and full replan. |
| `tests/test_stage3_physical.py` | Frozen hashes, metadata, ticks, tampering, immutability and absence of coefficient/formula dependencies. |
| `tests/test_stage3_planner.py` | Independent semantic/routing/dominance/selection oracles, information-boundary tests and frozen experimental differential. |
| `tests/test_stage3_runner.py` | Actual execution, first/last cost, setup replanning, CHORD, FLAG, terminal boundaries, deterministic replay, public-only access and Stage-2 delta equivalence. |
| `tests/test_stage2_semantic_golden.py` | Absolute regression check through the existing Stage-2 benchmark execution/adapter path, canonical fixture integrity and minimal-prefix coverage. |
| `tests/fixtures/stage2_semantic_golden_v1.json` | Accepted timing-free Stage-2 board identities, outcomes and complete semantic action evidence. |
| `STAGE3_IMPLEMENTATION_SLICE_A.md` | Qualification results, provenance, limitations and deferred integration assessment. |

`benchmark_runner.py`, `simple_runner.py`, Stage-2 inference, telemetry models,
schema and repository are unchanged. Production Stage-3 modules do not import
experiments or calibration fitting code. There is no production L-FIRST switch.

## Stage-2 absolute golden

Selected exact prefix: **[0,2)**, the smallest prefix meeting all requested
outcome and inference-category coverage.

| game_index / seed | Outcome | LOCAL | GLOBAL | GUESS | Policy OPEN | Total actions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | WIN | 275 | 32 | 10 | 1 | 318 |
| 1 | LOSS | 0 | 1 | 2 | 1 | 4 |

N=1 cannot cover LOSS; N=2 covers WIN/LOSS and all three analyzed categories.
Qualification runtime was approximately 0.45 seconds (a subsequent isolated
run took 0.62 seconds), so a larger prefix was unnecessary for this guard.

Accepted source:
`C:\Users\User\Desktop\Minesweeper-Stage2-100k-20260928\stage2-expert-100000.sqlite3`.
The entire source file and its physical copy matched accepted SHA-256
`8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f`.
WAL, SHM and journal sidecars were absent before and after. The original was
never opened for writing, migrated, checkpointed, repaired or vacuumed.

An initial immutable read preceded the user's instruction to use a copy.
After that instruction, extraction was repeated from a SHA-verified physical
copy using `mode=ro&immutable=1` and `PRAGMA query_only=ON`. The original and copy
hashes were rechecked. The 712,728,576-byte copy remains, untracked and ignored,
at `results/stage2-golden-source/stage2-expert-100000.sqlite3`.

Fixture SHA-256:
`fee9f837b7bd4977e5a910feeeed987bd4c941ce895cdae449e82046cd8a49ff`.
Encoding is UTF-8 JSON with sorted keys, compact separators, ASCII escapes and
no trailing newline. Probabilities use reduced numerator/denominator strings.
Every one of the 322 actions includes action index/type/target, inference
category, selector count, exact target/minimum probabilities, post-action
status and public execution deltas. Game identity includes seed, index,
fingerprint and first click. Compute timing is excluded. CI needs only the
small checked-in fixture, not the external DB.

## Validation results

| Focused group | Tests | Result |
| --- | ---: | --- |
| Physical | 12 | PASS |
| Planner, including differential | 29 | PASS |
| Runner | 22 | PASS |
| Stage-2 golden | 3 | PASS |
| **New total** | **66** | **PASS** |

Relevant regression: **780 tests PASS in 44.012 seconds**, comprising 714
existing tests plus the 66 new tests. There were no failures, errors or skips.
The run used CPython 3.12.14 and covered engine/board analysis, all existing
simple inference/probability/oracle/decision/runner/instrumentation/adapter
tests, benchmark board/runner/continuation/statistics/presentation,
telemetry collector/repository/codec/schema, existing calibration/replay
validation/policy-pilot tests, and all new tests.
Log: `results/stage3-slice-a-relevant-regression.log` (ignored local evidence).

Independent oracles include exhaustive route permutations for setup sizes
0 through 7, an all-pairs dominance implementation, exact `Fraction` ordering,
and hand-authored public candidate fixtures. Runner tests include a real plan
`FLAG(2,1) -> FLAG(1,2) -> CHORD(2,2)` whose next fresh plan instead selects
`OPEN(2,0)` after the first FLAG; the queued suffix is demonstrably not executed.
Delta equivalence is checked against the unchanged Stage-2 helper.

The initial sandbox test run encountered Windows temporary-directory SQLite
permissions. The relevant suite passed after an approved execution outside
the sandbox. A broader all-repository/UI run also encountered the existing
Qt installation-path limitation documented in `BUILDING.md` (the virtualenv
is under a Korean path); that full UI run did not complete. No unrelated
environment or UI source change was made to address it.

## Production versus experimental differential

**759 public states, 0 mismatches**: 10 curated states plus 749 states from
five complete fixed `EXPERT_GENERAL_V1` trajectories:

| Game index | Compared post-first-OPEN states |
| --- | ---: |
| 0 | 226 |
| 1 | 3 |
| 2 | 198 |
| 3 | 136 |
| 100000 | 186 |

Comparisons cover evidence, complete candidate sets, dominance survivors,
selected plan and executed move. Coverage includes WON/LOST, LOCAL/GLOBAL/GUESS
and OPEN/FLAG/CHORD. The test pins the LF-canonical experimental planner source
SHA-256 `a452dc5174f3a7244fd193ef76d9ca44f89e8ef79c1c2f7427109ce3449675fc`,
so checkout line endings do not change its identity. The differential is
additional evidence, not the sole oracle.

## Known limitations and Slice B integration work

The runner deliberately models only a canonical all-HIDDEN start within the
30x16 timing-table grid. Already-terminal input returns no actions; progressed
PLAYING input is rejected. Traces are in-memory public facts, with no SQLite,
UI, replay-file writer or benchmark dispatch integration. No official Stage-3
whole-prefix benchmark, paired statistics, compute-tail performance study or
whole-game speed improvement claim is made by these tests. Detailed analysis
versus planner/routing timing breakdown is deferred; the current trace measures
the complete analysis-plus-planning call separately from modeled physical cost.

Read-only V1 telemetry assessment:

- `telemetry_schema.py:131` allows nullable target probability, and its action
  domain includes CHORD. `tests/test_telemetry_repository.py:65` already stores
  an analyzed CHORD with `Fraction(0)`. Thus structural CHORD storage exists.
- `telemetry_model.py:73` requires a non-null `Fraction` for every analyzed
  action. A CHORD with an inapplicable/absent hidden-target probability cannot
  pass that model. Clearing inference metadata would falsely label it unanalyzed.
- `simple_telemetry.py:33` implements Stage-2 selectable HIDDEN-cell pools,
  action priority and `(y,x)` checks. It cannot be reused for Stage-3 plans.
  Giving the already-open clicked clue probability zero is a true but trivial
  clue fact; it is not a selected hidden cell's probability or a CHORD failure
  probability. Those interpretations must not silently replace one another.

**Conclusion:** V1 can structurally store CHORD, but its existing contract does
not establish a semantics-preserving analyzed-CHORD adapter. A `Fraction(0)`
placeholder alone is insufficient to claim compatibility. Slice B must
explicitly settle and version probability applicability/meaning for CHORD,
and any resulting Python-model/SQL/codec changes, while retaining the accepted
Stage-2 meaning and immutable baseline.

Slice B must also define candidate-count meaning (Stage-2 cells versus Stage-3
plans), analysis-plus-planning versus Stage-2 analysis-only compute boundaries,
integer physical action/total cost and profile/spec identity persistence,
and the smallest benchmark dispatch/adapter seam. It must rerun this absolute
Stage-2 golden before and after shared-path edits and validate paired board
identity and whole-prefix outcomes. None of these integrations, migrations,
statistics or deferred algorithm extensions was implemented in Slice A.
