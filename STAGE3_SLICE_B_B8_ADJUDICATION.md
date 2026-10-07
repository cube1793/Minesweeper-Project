# Stage-3 Production Slice B — B8 Source / Test / Evidence Adjudication

Date: 2026-10-08. Repository: `cube1793/Minesweeper-Project`.
Branch: `feature/stage3-implementation`.
Committed base: `de9d1dccd8eb30d6efa71805032546d260cd671a`.

## Executive verdict

**STAGE-3 PRODUCTION SLICE B — B8 SOURCE/TEST/EVIDENCE ADJUDICATION PASS**

- BLOCKER: 0
- REQUIRED: 0
- OPTIONAL: 2, retained below
- Prior supplemental baseline aggregate evidence finding: RESOLVED
- Next gate: B9 independent Claude Code audit
- No commit/push authorization. B8 is not final Slice-B acceptance or a final 100k performance claim.

This is an evidence-based cumulative adjudication, not a blind review. Earlier B1–B6 source/test reviews are carried forward after checking all 17 changed files against the pre-pilot manifest. New B7-C code/tests and the supplied B7/B7-C evidence were inspected directly. Counts in implementation reports are not treated as independently executed tests.

## 1. Evidence identity and preservation

The remote branch HEAD was read through the GitHub connector and still resolves to the committed base above. The implementation under review is the deliberately dirty working-copy artifact, not that commit alone.

All 10 previously declared review files match their actual uploaded SHA-256 against the supplemental before/after manifest. The supplemental file itself matches the separately reported digest. Thus all 11 newly supplied review artifacts match their declared bytes. The five earlier qualification/report drivers also match the archived driver hashes in `final_verification.json`.

Key digests:

| Artifact | SHA-256 |
|---|---|
| source_manifest_b7.json | 567d1f09df1293257fe94c80faa73cd7df8f3ed4d776d837884c9dd0a99d8b90 |
| b7c_protocol.json | 01521da1858f1cf37eeca7012908ebf7afd3874de5aad291a1331d1e0c653ee0 |
| b7c_samples_ns.json.gz | 8506f2ad207ae5a15045648e2e312288552f585052310e7cb5dbd15c6ea19fe5 |
| baseline_aggregate_crosscheck.json | fc6f364e21954a427f4729c77935bc65a2f920ee7d5114987d50d699395bf221 |

All 17 B1–B6 changed source/test files match `source_manifest_b7.json`; both new B7-C source/test files match the declared protocol. Nineteen implementation/test files and five qualification drivers parse successfully. The isolated verification tree contains 44 files matched to the manifest/protocol; copy-side line-ending selection was used only where an older attachment had LF rather than the manifest's CRLF bytes. No uploaded input was overwritten. All 11 supplied review artifacts remained unchanged after verification.

The actual frozen physical profile bytes and the independently encoded integer timing table both match the recorded hashes. The algorithm's §26 and integration specification §§9.1,17.9,18 were checked for the required measurement and acceptance boundaries.

## 2. Supplemental baseline finding

`baseline_aggregate_crosscheck.json` records the missing exact aggregates, the selected run, read-only SQL, identical before/after hashes, and preservation of the earlier reports/evidence. Its actual/expected values and arithmetic are consistent:

`18,504,755 + 1,169,157 + 369,392 + 100,000 = 20,143,304`.

`17,386,388 / 100,000 = 173.86388` and `1,335,630 / 100,000 = 13.35630` were independently recomputed as exact fractions. This closes the prior evidence-completeness finding. Existing B7 reports need not be rewritten: the addendum intentionally follows the earlier final-verification artifact.

This is direct inspection and arithmetic verification of the supplied SQL-result evidence, not a new query of the user's absent 100k SQLite file. Original/copy DB preservation on the user's machine remains supported by the preserved execution evidence and is a direct local B9 verification item.

## 3. B7-C instrumentation source/test adjudication

`ComputeDiagnostics` forwards the original production call once and returns its actual result. It does not perform an extra inference or select an action. Only declared imported aliases are wrapped. The complete timer surrounds the actual planner invocation, retaining timing-table validation. Nested analysis/local/probability/candidate/route measurements correspond to actual calls.

The invocation-local stack verifies parent relationships. Each successful decision requires one analyzer and one local-inference call. Probability/candidate generation each occur at most once. No-call probability remains absent, not a fabricated zero. Failed invocations propagate their exception and do not become successful zero-cost samples; the qualification driver does not swallow those failures.

`planner_only = complete - analysis` is calculated within the same invocation. Negative remainders raise an error rather than being clamped. Parent measurements include nested wrapper overhead as declared. Routing is nested in candidate generation, and their inclusive values are not disjoint totals. Original aliases are restored on normal and exceptional context exit. Serial, process-global instrumentation is documented; this is not a concurrent production profiling facility.

The 24 supplied diagnostic tests were directly rerun unchanged and passed. The zero-clue fixture genuinely makes two route calls before candidate deduplication. Its corrected 12-clock-read fixture matches the production call graph. Historical initial failing test source/logs were not supplied, so the complete earlier edit history is not independently certified; the final fixtures and behavior are verified.

## 4. Raw samples independently recomputed

The compressed raw file contains **2,714,307 entries across seven overlapping timing populations**, not that many independent decisions. The reviewer script did not call the production `summarize_samples()` function. All values are non-negative integers, and the declared nearest-rank count/P50/P90/P95/P99/maximum fields match exactly.

| Population | Count | P50 ns | P90 ns | P95 ns | P99 ns | Maximum ns |
|---|---:|---:|---:|---:|---:|---:|
| Complete | 141958 | 1347300 | 2168800 | 3176600 | 6945300 | 1325712600 |
| Analysis | 141958 | 957000 | 1739800 | 2863500 | 5834000 | 1325540700 |
| Local inference | 141958 | 19100 | 27100 | 30300 | 44600 | 76764700 |
| Probability | 15052 | 1668400 | 4119100 | 7775600 | 68343300 | 1324483900 |
| Planner-only | 141958 | 303000 | 658800 | 802900 | 1117500 | 165826100 |
| Candidate generation | 138323 | 174000 | 506100 | 641800 | 939200 | 165507800 |
| Exact routing | 1993100 | 5700 | 14600 | 22800 | 52700 | 165122300 |

All 141,958 aligned COMPLETE/ANALYSIS/PLANNER_ONLY samples satisfy the exact same-invocation subtraction with no negative remainder. Local timing is within its corresponding analyzer timing. The complete count equals 142,958 physical actions minus 1,000 initial policy actions. Candidate-generation count equals 141,958 analyzed actions minus the reported 3,635 guesses.

Protocol declaration precedes measurement in the retained timestamps. These are one serial instrumented run's distributions, not overhead-free CPU costs, population-independent guarantees, or a historical Stage-2 compute-speed comparison. Percentiles must not be added or subtracted to create phase contributions.

## 5. Game evidence and independent bounded semantic probes

The full `b7c_game_equality.json` was parsed programmatically. It has exact indices `[0,1000)`, valid results, positive action counts/costs, and valid digest encodings. Independently aggregated Stage-3 facts are:

| Prefix | Wins / Losses | Actions | WIN modeled us | Whole-prefix modeled us |
|---|---|---:|---:|---:|
| [0,100) | 38 / 62 | 15187 | 1427225227 | 2744970747 |
| [0,1000) | 405 / 595 | 142958 | 15531739386 | 25829890996 |

These agree with the pilot report. Using its Stage-2 WW totals, exact ratios/reductions also recompute correctly:

- 100: ratio `1427225227/2055912119`, reduction `628686892/2055912119` = approximately 30.579463%.
- 1000: ratio `7765869693/11095306955`, reduction `3329437262/11095306955` = approximately 30.007617%.

Those are modeled WW results for this qualification prefix. Whole-prefix totals remain diagnostic even when all outcome labels agree. The reported 405/405 faster WW pairs cannot be independently regenerated from the supplied Stage-3-only digest ledger; local B9 must read the paired DB rows/costs directly. No universal Stage2–Stage3 outcome/guess equality invariant is created.

The reviewer additionally executed 13 bounded source-level semantic probes, each uninstrumented and instrumented, in the isolated manifest-matched tree. Selected game indices: `0,1,2,4,7,12,45,137,222,377,612,891,999`. Selection covers fixed boundary/representative cases plus the games containing the supplied COMPLETE and PLANNER_ONLY maxima; it is not a statistical performance sample.

Each pass generated 2,518 physical actions. Every selected game's result, full ordered semantic-event digest, and independently summed target-only modeled cost matches the supplied equality ledger. Instrumented and uninstrumented ordered events also match one another, and all aliases restore correctly. Nested-time arithmetic was checked on the probe's own invocation records. No existing pilot DB or accepted original was opened or changed. This is not a repeat of the 100/1000 B7 persisted pilot and is not timing reproduction on the user's Windows host.

## 6. Direct tests and limits

Reviewer environment: CPython 3.13.5, Linux, SQLite 3.46.1. This differs from the reported Windows/CPython 3.12.14/SQLite 3.53.1 environment; no cross-machine elapsed-time claim is made.

Direct unchanged-test commands (working directory: the isolated runtime copy; bytecode writes disabled):

```text
python -m unittest tests.test_stage3_compute_diagnostics -v
# 24 tests: OK, FAIL=0, ERROR=0, SKIP=0

python -m unittest tests.test_telemetry_collector tests.test_simple_telemetry tests.test_stage3_telemetry tests.test_stage3_compute_diagnostics tests.test_benchmark_statistics tests.test_benchmark_pairing_sources -v
# 164 tests: OK, FAIL=0, ERROR=0, SKIP=0
```

The 24-test run is contained in the 164-test run. Do not add them as 188 distinct tests. The numerical/hash script performed 71 checks, separately from unittest counts. The bounded semantic probes are also reported separately.

Not directly re-executed or re-queried in this B8 environment:

- The user's original/analysis-copy 100k SQLite database and before/after filesystem hashes.
- Both persisted Stage-3 pilot DBs and the full paired Stage-2 per-game modeled comparison.
- The full 1,000-game DB-to-instrumented event comparison; only its supplied ledger, driver and bounded independent probes were inspected/recomputed.
- The reported Windows 1,120-test non-UI run and any full Qt/UI discovery.
- The historical first failing test revision/log.

These limits are explicit; report generation code with hard-coded test summaries is not independent execution proof. The direct local artifact re-query and broad regression belong in B9, whose gate remains open.

## 7. Retained optional/deferred items

1. **Qt/UI full discovery:** unverified environment coverage, not a newly demonstrated B1–B7 correctness defect. Do not weaken or modify UI tests to remove the known initialization problem. Run in an appropriate local environment during/after B9 and state the actual scope.
2. **Duplicate Model C authentication:** KEEP NOW; optimization DEFER/REVISIT. The existing independent validation boundary has value, and these planning measurements do not isolate the evaluator-side authentication cost. No production change is required for B8.

Keep the preserved reports, raw samples, baseline addendum, source manifests, driver archive and existing SQLite artifacts. Do not delete fields/modules or rewrite historical evidence merely to make the artifact set cleaner. No new SQL timing columns, policy changes, outcome-equality regression invariant, or speculative optimization is requested.

## Final gate

```text
Prior baseline evidence finding = RESOLVED
B7 qualification evidence       = ACCEPTED
B7-C measurement gate          = ACCEPTED
B8                             = PASS
BLOCKER                        = 0
REQUIRED                       = 0
B9                             = PENDING
COMMIT / PUSH                   = NOT YET
```

B9 should independently inspect the local dirty implementation, hash-bound artifacts, full stream/WW comparison and diagnostic non-interference. This B8 verdict is an input to that audit, not a substitute for its evidence.
