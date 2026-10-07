# Stage-3 B7 Qualification Pilot Evidence

Status: QUALIFICATION EVIDENCE; not an official final benchmark or final 100k performance claim.

Source captured: 2026-10-07T23:11:31.242309+09:00 (Asia/Seoul).
Branch: `feature/stage3-implementation`. HEAD: `de9d1dccd8eb30d6efa71805032546d260cd671a`. `git_dirty=true`.
The approved B1–B6 working tree is deliberately uncommitted. Both pilot calls use `official=False`.

## Source provenance

`git diff --binary HEAD` SHA-256: `de52bf85374d30dd2bf715af275ebdf3002a7306f47e0af1a90a9bf45b37596e`.
Initial `git diff --check`: PASS (empty output).

```text
 M benchmark_runner.py
 M benchmark_statistics.py
 M telemetry_model.py
 M telemetry_schema.py
 M tests/test_benchmark_statistics.py
 M tests/test_simple_telemetry.py
 M tests/test_telemetry_collector.py
?? benchmark_comparison.py
?? benchmark_modeled_time.py
?? stage3_benchmark_runner.py
?? stage3_telemetry.py
?? tests/test_benchmark_comparison.py
?? tests/test_benchmark_modeled_time.py
?? tests/test_benchmark_pairing_sources.py
?? tests/test_stage3_benchmark_continuation.py
?? tests/test_stage3_benchmark_runner.py
?? tests/test_stage3_telemetry.py
```

Full source/test/file manifest: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\source_manifest_b7.json`.
The manifest hashes tracked source/tests/specs/configuration plus every relevant untracked Python file. Raw working-copy bytes are used; the algorithm identity separately uses canonical LF content.

| Approved untracked implementation/test file | SHA-256 |
|---|---|
| `benchmark_comparison.py` | `c3b54370d1a7b40fb3549cc2554a3e49ce1be7c4a2c79600e9aa7831cedef136` |
| `benchmark_modeled_time.py` | `13bd1b4d715248577ef65b85f78ff397ff02c62594b503ca384cea53ba7d8994` |
| `stage3_benchmark_runner.py` | `b6f5c8eef5bcc3aa7ad96686eab0cfb10b7f3f5463d199b04bd0a25189d39377` |
| `stage3_telemetry.py` | `dc82dd9f55613d585d81855ced817fea854e5e9239703d9cded3d84c6d654c05` |
| `tests/test_benchmark_comparison.py` | `5165980e517be0cf08ed68f2de3ce4e7bbaf515dc94a33220fbae84377caf666` |
| `tests/test_benchmark_modeled_time.py` | `b77c693ddc72090b4f48ce02cc856e6f5b792a0b69f350698539b2ed3792d912` |
| `tests/test_benchmark_pairing_sources.py` | `4b289c91b4238bc87ddc50649f5d53c147f999624a9a99cfb2486a9d29eeb06a` |
| `tests/test_stage3_benchmark_continuation.py` | `f4b966eb4566f4b91ab123419a8f0c70df1f715f25054470c7db603c7e1f0623` |
| `tests/test_stage3_benchmark_runner.py` | `6449c92caeb514042e02964f7db7182004763c1a81081230babf781d94d59b03` |
| `tests/test_stage3_telemetry.py` | `64d8a27bdb15ee5583be12ca63d05e54b70e2df4a1b7e6a6692c957bf04a3e03` |

## Frozen model and environment

Algorithm spec v1 canonical LF SHA-256: `6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33`.
Model: `overlap_floor_log2_distance_v1`, profile version 1, unit `us`, initial cursor `(0,0)`.
Profile SHA-256: `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
Table SHA-256: `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b`.
Actual preserved profile bytes, metadata and stored integer table were authenticated by the production loader.
Both pilot runs store this exact canonical Stage-3 solver config:

```json
{
  "algorithm_spec_sha256": "6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",
  "algorithm_spec_version": 1,
  "initial_cursor": [
    0,
    0
  ],
  "initial_open": [
    0,
    0
  ],
  "physical_model_id": "overlap_floor_log2_distance_v1",
  "physical_profile_sha256": "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",
  "physical_profile_version": 1,
  "timing_table_sha256": "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b",
  "timing_unit": "us"
}
```

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

## Accepted Stage-2 baseline

Original: `C:\Users\User\Desktop\졸프\Minesweeper Project\Minesweeper-Project\results\stage2-golden-source\stage2-expert-100000.sqlite3`.
Analysis copy: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\stage2_analysis_copy.sqlite3`.
Original before/after baseline audit and copy SHA-256: `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f`.
The original was opened only as binary file input for SHA-256/copy. All SQLite access used the byte-identical analysis copy with `mode=ro&immutable=1`; no original SQLite connection, checkpoint or configuration change occurred.
Physical schema V1; run 1 COMPLETED; clean provenance; requested=processed=100000; exact `[0,100000)`; official eligible.
Identity: semantic V1 / STAGE_2 / SIMPLE_MINIMUM_RISK; EXPERT_GENERAL_V1; 30×16 / 99; FIRST_CLICK_FIXED_0_0; generator V1.
`solver_config_snapshot={"accept_guesses":true,"initial_open":[0,0]}`.
Accepted outcomes: WIN 37,702; LOSS 62,298; total 100,000. No contradiction found.

## Stage-3 100-game qualification

Gate: **PASS**, audited 2026-10-07T23:14:06.004573+09:00.
New artifact: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\stage3_100.sqlite3`; run 1; SHA-256 `260e8833a27fc8a1524169d75ff1f8227b4d950c8769803e62bd9db3dbea1e14`.
Execution: 2026-10-07T23:13:00.138929+09:00 → 2026-10-07T23:13:44.452913+09:00; wall duration 44314051700 ns (operational evidence, not compute claim).
COMPLETED; requested=processed=100; exact `[0,100)`; failure_code=NULL; 100 complete games.
Semantic V2 / STAGE_3 / E_FIRST_FIRST_REVEAL_V1; exact canonical frozen config; EXPERT_GENERAL_V1 30×16/99.
Stored HEAD `de9d1dccd8eb30d6efa71805032546d260cd671a`, dirty=true. Stage-3 official_eligible=false intentionally.
Stage-2 copy official eligibility checked separately. Higher comparison uses require_official=False because this is deliberately dirty/uncommitted Stage-3 qualification evidence.

| Outcome | Count |
|---|---|
| WW | 38 |
| WL | 0 |
| LW | 0 |
| LL | 62 |

| Solver | Wins | Losses | Exact win rate |
|---|---:|---:|---|
| Stage 2 | 38 | 62 | 19/50 |
| Stage 3 | 38 | 62 | 19/50 |

WW PRIMARY ONLY:

| Metric | Exact value |
|---|---|
| game_count | 38 |
| stage2_total_us | 2055912119 |
| stage3_total_us | 1427225227 |
| total_delta_us | -628686892 |
| ratio | 1427225227/2055912119 |
| reduction | 628686892/2055912119 |
| stage3_faster | 38 |
| stage2_faster | 0 |
| ties | 0 |
| presentation reduction | 30.579463% |

Ratio is Fraction(S3,S2), a ratio of WW totals. Delta is Stage3−Stage2. Fractions and integer microseconds remain authoritative.
Paired deltas summary: `{"count": 38, "sum_us": -628686892, "minimum_us": -21704118, "maximum_us": -11127365, "mean_us": "-314343446/19"}`. Full ordered per-game deltas are retained in `pilot_100_audit.json`.

DIAGNOSTIC ONLY whole-prefix totals:
Stage 2 = 3918158487 us; Stage 3 = 2744970747 us.
Loss termination can bias whole-prefix totals; these are not the primary speed result even when outcome labels happen to agree.

| Source | Action rows | CHORD rows | Guess rows |
|---|---:|---:|---:|
| stage2 | 22199 | 0 | 396 |
| stage3 | 15187 | 5893 | 396 |

Complete-stream reconstruction failures: 0; validated 100 games per source.
First/final inputs included; automatic effects and unexecuted plan suffixes excluded by actual-event reconstruction.
Original and analysis-copy SHA after audit: `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` (unchanged). Pilot SHA before/after reader audit also identical.

## Stage-3 1000-game qualification

Gate: **PASS**, audited 2026-10-07T23:22:41.116847+09:00.
New artifact: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-qualification-20261007\stage3_1000.sqlite3`; run 1; SHA-256 `5eb0c754e8f554cdb5e74b27329e2fc71c74d814faa2745f162acd15bdbe707a`.
Execution: 2026-10-07T23:14:36.841967+09:00 → 2026-10-07T23:21:40.029207+09:00; wall duration 423187902100 ns (operational evidence, not compute claim).
COMPLETED; requested=processed=1000; exact `[0,1000)`; failure_code=NULL; 1000 complete games.
Semantic V2 / STAGE_3 / E_FIRST_FIRST_REVEAL_V1; exact canonical frozen config; EXPERT_GENERAL_V1 30×16/99.
Stored HEAD `de9d1dccd8eb30d6efa71805032546d260cd671a`, dirty=true. Stage-3 official_eligible=false intentionally.
Stage-2 copy official eligibility checked separately. Higher comparison uses require_official=False because this is deliberately dirty/uncommitted Stage-3 qualification evidence.

| Outcome | Count |
|---|---|
| WW | 405 |
| WL | 0 |
| LW | 0 |
| LL | 595 |

| Solver | Wins | Losses | Exact win rate |
|---|---:|---:|---|
| Stage 2 | 405 | 595 | 81/200 |
| Stage 3 | 405 | 595 | 81/200 |

WW PRIMARY ONLY:

| Metric | Exact value |
|---|---|
| game_count | 405 |
| stage2_total_us | 22190613910 |
| stage3_total_us | 15531739386 |
| total_delta_us | -6658874524 |
| ratio | 7765869693/11095306955 |
| reduction | 3329437262/11095306955 |
| stage3_faster | 405 |
| stage2_faster | 0 |
| ties | 0 |
| presentation reduction | 30.007617% |

Ratio is Fraction(S3,S2), a ratio of WW totals. Delta is Stage3−Stage2. Fractions and integer microseconds remain authoritative.
Paired deltas summary: `{"count": 405, "sum_us": -6658874524, "minimum_us": -23904622, "maximum_us": -9593503, "mean_us": "-6658874524/405"}`. Full ordered per-game deltas are retained in `pilot_1000_audit.json`.

DIAGNOSTIC ONLY whole-prefix totals:
Stage 2 = 36691007550 us; Stage 3 = 25829890996 us.
Loss termination can bias whole-prefix totals; these are not the primary speed result even when outcome labels happen to agree.

| Source | Action rows | CHORD rows | Guess rows |
|---|---:|---:|---:|
| stage2 | 208720 | 0 | 3635 |
| stage3 | 142958 | 55743 | 3635 |

Complete-stream reconstruction failures: 0; validated 1000 games per source.
First/final inputs included; automatic effects and unexecuted plan suffixes excluded by actual-event reconstruction.
Original and analysis-copy SHA after audit: `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` (unchanged). Pilot SHA before/after reader audit also identical.

## Deterministic Stage-3 prefix and preservation

First-100 check: **PASS**, 100 games.
All game identity/result/summary semantics, ordered action types/targets/categories/exact risk metadata/public deltas, and independently reconstructed modeled totals match. Elapsed compute timing, run provenance and surrogate IDs are excluded.
This is same-Stage-3 reproducibility evidence, not a Stage2↔Stage3 outcome-equality invariant.

## Scope and limitations

Qualification only. No final Stage-3 100k run, final performance claim, historical Stage-2 compute comparison, B8 adjudication or B9 audit was performed.
Both pilot databases are separate new artifacts; the 100-game request was never extended or continued to 1000.
No production semantics, physical profile/table, schema, SQL columns or accepted baseline were modified. No commit/push.
B5 duplicate per-game model authentication: KEEP NOW; optimization DEFER/REVISIT. No isolated evidence establishes a concrete bottleneck, and the independent validation boundary is retained.
Initial regression: Stage-2 golden 3 PASS; B1–B6 integrated 524 PASS; FAIL/ERROR/SKIP=0. Final regression is recorded in the verification appendix below.
B7 overall verdict: PASS. The 100 gate passed before the separate 1000 run; both qualification gates and first-100 reproducibility passed. B7-C is reported separately in STAGE3_B7C_COMPUTE_DIAGNOSTICS.md.
Findings: BLOCKER=0, REQUIRED=0. B8/B9 remain deferred.

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
