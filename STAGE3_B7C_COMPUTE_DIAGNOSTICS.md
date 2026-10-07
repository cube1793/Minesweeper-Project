# Stage-3 B7-C Controlled Compute Diagnostics

Status: CONTROLLED QUALIFICATION EVIDENCE; not a final 100k performance claim.

Protocol declared before measurement: 2026-10-07T23:34:25.526185+09:00 (Asia/Seoul).
Branch: `feature/stage3-implementation`; HEAD: `de9d1dccd8eb30d6efa71805032546d260cd671a`; `git_dirty=true`.
Approved B1–B6 production semantics remain unchanged. Instrumentation only forwards and observes actual production calls.

## Fixed corpus and protocol

EXPERT_GENERAL_V1 exact `[0,1000)`; 30×16 / 99 mines; first click and initial cursor `(0,0)`.
one serial fresh-engine in-memory approved Stage-3 per-game path; no warmup games, no repeats, no concurrent tests/benchmarks; uninstrumented B7 1000 DB is reference
Read-only uninstrumented reference: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\stage3_1000.sqlite3`.
Reference SHA-256: `5eb0c754e8f554cdb5e74b27329e2fc71c74d814faa2745f162acd15bdbe707a`.
No production telemetry DB is written by this diagnostic run. Engine setup/evaluator retain hidden-board access; selection and instrumentation receive public production arguments only.

## Source and frozen model identity

Complete approved source manifest: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\source_manifest_b7.json`.
Manifest SHA-256: `567d1f09df1293257fe94c80faa73cd7df8f3ed4d776d837884c9dd0a99d8b90`.
Tracked diff SHA-256: `de52bf85374d30dd2bf715af275ebdf3002a7306f47e0af1a90a9bf45b37596e`.
The pilot report lists every approved untracked implementation/test hash; the full manifest retains every relevant tracked/untracked source/test/spec file hash.

| Diagnostic source/test | SHA-256 |
|---|---|
| `stage3_compute_diagnostics.py` | `c345cb56687d260753962a9ce6f077cdcd41893bc2cd4a89a7fbf1c916d5a4d0` |
| `tests/test_stage3_compute_diagnostics.py` | `70c9dd941d720f4133080161305dedaa3154d529b8fef16fd4418cdde267ab14` |
| measurement driver | `e8491dc8a9914394285d8ae3e97a9f6952c8e918b248aa0db6fe0c767d7f01f8` |

Algorithm spec v1 canonical LF SHA-256: `6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33`.
Frozen Model C facts authenticated before measurement:

```json
{
  "initial_cursor": [
    0,
    0
  ],
  "physical_model_id": "overlap_floor_log2_distance_v1",
  "physical_profile_version": 1,
  "physical_profile_sha256": "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",
  "timing_table_sha256": "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b",
  "timing_unit": "us"
}
```

## Environment and measurement boundaries

```json
{
  "python_implementation": "CPython",
  "python_version": "3.12.14",
  "platform": "Windows-11-10.0.26200-SP0",
  "machine": "AMD64",
  "cpu_count": 12,
  "cpu_identifier": "AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD",
  "sqlite_version": "3.53.1",
  "perf_counter": {
    "implementation": "QueryPerformanceCounter()",
    "monotonic": true,
    "adjustable": false,
    "resolution": 1e-07
  }
}
```

Clock: `time.perf_counter_ns`; authoritative units: integer nanoseconds.
nearest rank ceil(p*N); P50 is diagnostic median convention, not midpoint interpolation; empty population has count=0 and None/N/A percentiles; zero duration is a valid actual sample

- **complete**: COMPLETE / inclusive: original stage3_planner.plan_position via stage3_runner.plan_position alias; includes frozen table validation, nested Stage-2 analysis, Stage-3 planning and nested diagnostic wrapper overhead. Excludes engine action, telemetry, persistence, comparisons, reporting and outer-wrapper post-call bookkeeping.
- **analysis**: ANALYSIS / inclusive nested: stage3_planner.analyze_position alias; all original simple_decision.analyze_position work, including constraints/public mine budget, local inference, applicable probability and Stage-2 selector plus their nested wrapper overhead.
- **local_inference**: LOCAL INFERENCE / nested: actual simple_decision.infer_deterministic(constraints) calls only. Constraint building and selectors are outside this subcall and remain in analysis.
- **probability_analysis**: PROBABILITY ANALYSIS / nested: actual simple_decision.calculate_probabilities(observation,num_mines) calls only; no sample at all when not called.
- **planner_only**: PLANNER-ONLY / same-invocation attributed remainder: complete_ns minus that invocation's one analysis_ns. Includes table validation, public cursor/dimension checks, certainty/planning, candidate generation, dominance, selection/fallback, result creation and wrapper residue outside the analysis timer. Never subtract independent runs, never clamp negative values.
- **candidate_generation**: CANDIDATE GENERATION / inclusive nested: actual stage3_planner.generate_reveal_plans call; candidate construction, nested exact routing, deduplication and ordering. Absent for guesses.
- **exact_routing**: EXACT ROUTING / nested within candidate generation: every actual stage3_planner.exact_route call, including direct zero-setup routes and bounded setup routes.

Local/probability are nested in analysis; exact routing is nested in inclusive candidate generation. Never add inclusive/nested populations as disjoint total phases.

`planner_only[i] = complete[i] - analysis[i]` for the same successful invocation. Independent-run subtraction and negative clamping are forbidden; negative attribution stops qualification.
The runner's diagnostic execution compute telemetry includes wrapper bookkeeping; it is excluded from semantic equality and is not the timing population reported here.

## Results

Verdict: **PASS**.
Measured 2026-10-07T23:34:56.957851+09:00 → 2026-10-07T23:43:46.911828+09:00; wall elapsed 529954304100 ns including setup/evaluation/reference checks outside planning timers.
Protocol SHA-256: `01521da1858f1cf37eeca7012908ebf7afd3874de5aad291a1331d1e0c653ee0`.

All table values below are exact integer **ns**. P50 uses nearest-rank diagnostic median.

| Population | Count | P50 | P90 | P95 | P99 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| complete | 141958 | 1347300 | 2168800 | 3176600 | 6945300 | 1325712600 |
| analysis | 141958 | 957000 | 1739800 | 2863500 | 5834000 | 1325540700 |
| local_inference | 141958 | 19100 | 27100 | 30300 | 44600 | 76764700 |
| probability_analysis | 15052 | 1668400 | 4119100 | 7775600 | 68343300 | 1324483900 |
| planner_only | 141958 | 303000 | 658800 | 802900 | 1117500 | 165826100 |
| candidate_generation | 138323 | 174000 | 506100 | 641800 | 939200 | 165507800 |
| exact_routing | 1993100 | 5700 | 14600 | 22800 | 52700 | 165122300 |

Probability samples include only actual probability calls; absent decisions add no zero sample. Exact routing includes each real call, including repeated candidates before deduplication and zero-setup routes.
Successful complete invocations: 141958; negative remainders: 0; same-invocation attribution verified for every sample.
Instrumented/reference semantic equality: **1000/1000 PASS**, mismatches=0.
Every game compares seed/fingerprint/result and all non-timing GameRecord fields, ordered action types/targets/categories/exact risk metadata/public deltas, and independently reconstructed integer physical modeled cost. Initial policy events are included in equality but excluded from analyzed timing populations. Every instrumented analyzed action has exactly one complete planning sample.
Reference, accepted original and analysis-copy hashes are unchanged. Approved B1–B6 source hashes and tracked diff match the pre-pilot manifest.
Raw integer samples: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\b7c_samples_ns.json.gz`; SHA-256 `8506f2ad207ae5a15045648e2e312288552f585052310e7cb5dbd15c6ea19fe5`.
Per-game equality evidence: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\b7c_game_equality.json`.
Full results: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\b7c_results.json`.

## Limitations and findings

Python forwarding wrappers and clock reads affect measured distributions; attribution is same-execution, not overhead-free CPU time. OS scheduling/GC/other host activity are uncontrolled. No historical Stage-2 compute-speed claim and no mixing compute ns with modeled physical us.
One serial invocation per actual decision in one fixed-prefix run; no repetitions or confidence interval. Inclusive phase percentiles are not additive and do not establish causality. Instrumentation uses scoped process-global aliases, requiring no concurrent planner users.
Under this controlled diagnostic protocol, Stage-3 planning phases showed the distributions above. No historical Stage-2 compute-speed comparison is made. Physical modeled microseconds are not compute nanoseconds.
B5 duplicate model authentication: KEEP NOW; optimization DEFER/REVISIT. Its independent evaluator work is outside the complete planning timer, and this run does not isolate its cost. No concrete isolated bottleneck justifies removing the correctness boundary.
BLOCKER=0 / REQUIRED=0 in completed checks. OPTIONAL: repeatability studies and isolated authentication-cost measurement require a separately declared protocol; no optimization was performed.
B8/B9, final Stage-3 100k, GUI/charting, Stage4 and final graduation/performance claims are deferred. No production policy change, SQL column, schema migration, commit or push.

## Verification appendix

Actual unittest-reported runs (counts are not added across overlapping runs):

| Run | Total | PASS | FAIL | ERROR | SKIP |
|---|---:|---:|---:|---:|---:|
| Before B7: Stage-2 golden | 3 | 3 | 0 | 0 | 0 |
| Before B7: B1-B6 integrated | 524 | 524 | 0 | 0 | 0 |
| New B7-C test first run | 24 | 21 | 2 | 1 | 0 |
| New B7-C corrected tests | 24 | 24 | 0 | 0 | 0 |
| After B7-C: expanded non-UI | 1120 | 1120 | 0 | 0 | 0 |

The initial new diagnostic test failure was a fixture expectation error: the zero-clue fixture makes two real routing calls before deduplication, not one. The clock fixture was also one call short. Only these tests were corrected; production/harness policy and real semantic-equality tests were unchanged. This was not an approved-source regression or qualification execution failure.
Stage-2 accepted absolute EXPERT_GENERAL_V1 `[0,2)` golden: PASS before pilots and in the final expanded run; fixture/digest unchanged.
Expanded non-UI: 1120 tests PASS in 59.954s; FAIL/ERROR/SKIP=0. UI/Qt modules were not run in this qualification. No full discovery/full-suite PASS claim is made. Existing Qt initialization limitations were not worked around through UI source changes.
Excluded UI modules: test_benchmark_statistics_ui, test_live_analysis, test_live_auto, test_replay_analysis_ui, test_replay_statistics, test_stage3_calibration_tool, test_zini_worker_dispatch.

Exact commands (the diagnostic command was run twice):

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_stage2_semantic_golden -v
```

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_telemetry_collector tests.test_simple_telemetry tests.test_stage2_semantic_golden tests.test_stage3_telemetry tests.test_stage3_runner tests.test_stage3_planner tests.test_stage3_physical tests.test_benchmark_runner tests.test_benchmark_continuation tests.test_stage3_benchmark_runner tests.test_stage3_benchmark_continuation tests.test_telemetry_repository tests.test_telemetry_repository_codec tests.test_telemetry_schema tests.test_benchmark_statistics tests.test_benchmark_statistics_presentation tests.test_benchmark_modeled_time tests.test_benchmark_pairing_sources tests.test_benchmark_comparison -v
```

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_stage3_compute_diagnostics -v
```

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_benchmark_board tests.test_benchmark_continuation tests.test_benchmark_runner tests.test_benchmark_statistics tests.test_benchmark_statistics_presentation tests.test_benchmark_modeled_time tests.test_benchmark_pairing_sources tests.test_benchmark_comparison tests.test_board_analyzer tests.test_engine_regression tests.test_replay_analysis tests.test_replay_json tests.test_replay_model tests.test_replay_player tests.test_replay_recorder tests.test_simple_algorithm tests.test_simple_decision tests.test_simple_probability tests.test_simple_probability_oracle tests.test_simple_runner tests.test_simple_runner_instrumentation tests.test_simple_telemetry tests.test_stage2_semantic_golden tests.test_stage3_benchmark_runner tests.test_stage3_benchmark_continuation tests.test_stage3_calibration tests.test_stage3_calibration_analysis tests.test_stage3_e_l_policy_pilot tests.test_stage3_physical tests.test_stage3_planner tests.test_stage3_replay_validation tests.test_stage3_runner tests.test_stage3_telemetry tests.test_stage3_compute_diagnostics tests.test_telemetry_collector tests.test_telemetry_repository tests.test_telemetry_repository_codec tests.test_telemetry_schema tests.test_zini_advanced tests.test_zini_calculator tests.test_zini_core
```

## Final preservation and workspace audit

Verified at 2026-10-07T23:48:32.465529+09:00 (Asia/Seoul).
Every B1–B6 file in the pre-pilot manifest and the exact tracked diff hash still match. Diagnostic source/test/driver hashes match the declared pre-measurement protocol. Frozen source/spec/profile/table, planner/runner/solver, physical schema V1 and golden fixture are unchanged.
Accepted original and analysis copy final SHA-256: `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f`.
Both pilot DB hashes still match their audited hashes. No original SQLite connection, original/copy mutation, migration, new SQL timing column or action policy change occurred.
New reviewable files in this task: `stage3_compute_diagnostics.py` (observation-only harness), `tests/test_stage3_compute_diagnostics.py` (24 contract tests), `STAGE3_B7_PILOT_REPORT.md` and `STAGE3_B7C_COMPUTE_DIAGNOSTICS.md` (separate evidence reports).
All large artifacts, manifests, raw samples, comparison/equality evidence and final verification JSON are in `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007` outside the Git worktree. One-off orchestration scripts are retained in ignored `results/stage3_b7_qualification/` and archived in the artifact directory for review/reproduction; they are not production integration.
`git diff --check`: PASS, empty output. `git diff --stat` below is the approved tracked B1–B6 diff; Git does not include untracked files in this stat.

```text
 benchmark_runner.py                | 63 +++++++++++++++++++++++++++++++++-----
 benchmark_statistics.py            | 47 ++++++++++++++++++++++------
 telemetry_model.py                 | 11 +++++--
 telemetry_schema.py                |  3 ++
 tests/test_benchmark_statistics.py |  2 +-
 tests/test_simple_telemetry.py     |  5 ++-
 tests/test_telemetry_collector.py  | 48 +++++++++++++++++++++++------
 7 files changed, 147 insertions(+), 32 deletions(-)
```

Final `git status --short`:

```text
 M benchmark_runner.py
 M benchmark_statistics.py
 M telemetry_model.py
 M telemetry_schema.py
 M tests/test_benchmark_statistics.py
 M tests/test_simple_telemetry.py
 M tests/test_telemetry_collector.py
?? STAGE3_B7C_COMPUTE_DIAGNOSTICS.md
?? STAGE3_B7_PILOT_REPORT.md
?? benchmark_comparison.py
?? benchmark_modeled_time.py
?? stage3_benchmark_runner.py
?? stage3_compute_diagnostics.py
?? stage3_telemetry.py
?? tests/test_benchmark_comparison.py
?? tests/test_benchmark_modeled_time.py
?? tests/test_benchmark_pairing_sources.py
?? tests/test_stage3_benchmark_continuation.py
?? tests/test_stage3_benchmark_runner.py
?? tests/test_stage3_compute_diagnostics.py
?? tests/test_stage3_telemetry.py
```

BLOCKER: none. REQUIRED: none. OPTIONAL: duplicate model authentication remains KEEP NOW, optimization DEFER/REVISIT pending isolated evidence; no correctness boundary was removed.
Deferred: B8 adjudication, B9 external audit, final Stage-3 100k, final performance/graduation claim, independent controlled Stage-2 compute comparison, optimization, GUI/charting and Stage4.
Confirmation: no commit, no push, no reset, no clean, no restore, no temporary clean commit.
