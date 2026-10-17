# Representative-board Demonstrations / Timeline Analytics — Contract

Status: **FINAL ACCEPTANCE PASS / CLOSED — Slices 0–4 COMPLETE / ACCEPTED.**
Stage-3 Extended remains **ACTIVE**; only this milestone closes.
Date: **2026-10-17 (Asia/Seoul)**.
ChatGPT adjudication of the preceding read-only discovery:
**STAGE-3 EXTENDED TIMELINE ANALYTICS — DISCOVERY PASS**.
Final contract adjudication:
**STAGE-3 EXTENDED TIMELINE ANALYTICS — SLICE 0 CONTRACT PASS**.
**Slice 0 — Contract COMPLETE / ACCEPTED.**
**Slice 1 — Pure timeline analytics COMPLETE / ACCEPTED by ChatGPT final review.**
Final Slice-1 adjudication: **STAGE-3 EXTENDED TIMELINE ANALYTICS — SLICE 1 PASS**;
**BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT
final review.** Final Slice-2 adjudication:
**STAGE-3 EXTENDED TIMELINE ANALYTICS — SLICE 2 PASS**;
**BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Internal Slice 3A — accepted-evidence opening correction / preflight COMPLETE /
ACCEPTED by ChatGPT final review.** Final adjudication:
**STAGE-3 EXTENDED TIMELINE ANALYTICS — SLICE 3A CORRECTION / PREFLIGHT PASS**;
**BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Internal Slice 3B COMPLETE / ACCEPTED by ChatGPT final adjudication:**
**STAGE-3 EXTENDED TIMELINE ANALYTICS — SLICE 3B FINAL PASS**;
**BLOCKER 0 / REQUIRED 0 / OPTIONAL 5**.
**Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE /
ACCEPTED as a whole.**
**Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED.** Final adjudication:
**STAGE-3 EXTENDED TIMELINE ANALYTICS — FINAL ACCEPTANCE PASS / CLOSED**;
**BLOCKER 0 / REQUIRED 0**. See the [final closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md).
Qualified implementation/source candidate: `4c488e033dd045f1c203ff500d824cfaffb7cc67`
(`feat: add timeline analytics report`); a later documentation-only commit does
not replace this qualified identity.

Accepted Slice-1 implementation: [`timeline_analytics.py`](../../timeline_analytics.py)
and [`tests/test_timeline_analytics.py`](../../tests/test_timeline_analytics.py).
Verification: **28 focused PASS; 257 bounded existing regressions PASS**.
Four existing solver/Engine execution cases were intentionally excluded from
that bounded regression set; **no full suite is claimed**. The pure projection
and focused tests used in-memory synthetic facts with no DB access; existing
regressions used synthetic SQLite fixtures only. No official benchmark DB or
artifact was accessed, no actual exemplar IDs were selected, and no solver runs,
benchmarks, builds or GUI were used. Frozen V1 / Model C are unchanged;
Human remains deferred.

Accepted Slice-2 implementation: [`representative_boards.py`](../../representative_boards.py)
and [`tests/test_representative_boards.py`](../../tests/test_representative_boards.py).
Verification: **29 focused PASS; 28 Slice-1 timeline PASS; 75 bounded existing
comparison/statistics regressions PASS. Total reported verification: 132 PASS.**
All Slice-2 selector fixtures were synthetic/in-memory; existing regressions used
synthetic SQLite fixtures. No official DB/G4 artifact was accessed and no actual
official exemplar ID was selected. No solver, benchmark, build, GUI or full-suite
execution occurred. Frozen V1 / Model C are unchanged; Human remains deferred.

Accepted Slice-3A correction: [`telemetry_repository.py`](../../telemetry_repository.py)
and [`tests/test_telemetry_repository.py`](../../tests/test_telemetry_repository.py).
`connect_database_readonly(path, *, immutable=False)` preserves default `mode=ro`
behavior and supports explicit `mode=ro&immutable=1` for authenticated stable
preserved artifacts. `immutable=True` is the caller's assertion that the source
will not change during the connection lifetime; it is not for live sources.
Verification: **67 complete telemetry-repository PASS; 238 bounded relevant
regressions PASS; total 305 PASS**. Four existing solver/Engine execution tests
were intentionally excluded; **no full suite is claimed**.

During internal Slice 3A, the exact four official artifact hashes were
reauthenticated. Fresh Stage-2 and Stage-3 run identity/coverage checks **PASS**;
both runs are official-eligible exact
`EXPERT_GENERAL_V1 [0,100000)`. Model C authentication and **100,000 paired-prefix
identity validation PASS**. Independently read outcomes reconcile:
**WW 37,702 / WL 0 / LW 0 / LL 62,298**. The independently derived WW index set
exactly equals the authenticated G4 paired-delta index set: **37,702; missing 0;
extra 0**. Official artifact bytes/timestamps remained unchanged; no new sidecars
remained. No solver, Engine, board generator, official benchmark rerun, detailed
selected-action loading, report/chart generation, Human data or ZiNi holdout was
used. No actual official exemplar ID was selected or disclosed during Slice 3A.

### Accepted Slice-3B implementation and evidence

Accepted implementation: [`scripts/stage3_timeline_report.py`](../../scripts/stage3_timeline_report.py)
and [`tests/test_stage3_timeline_report.py`](../../tests/test_stage3_timeline_report.py).
Final focused verification after R-1: **34 report + 29 representative selector +
28 timeline analytics + 67 telemetry repository = 158 PASS**; **174 bounded
regressions PASS; reported total 332 PASS**. Four existing solver/Engine execution
tests were intentionally excluded. **No full-suite result was claimed at Slice 3B**;
final Slice-4 regression results are recorded below.

Independent Claude Code read-only audit inspected the actual pre-correction
report, independently authenticated/recomputed selection, and independently
reproduced all **1,508 action rows and 16 SVGs with 0 mismatch**. Claude's audit
verdict was **BLOCKER 0 / REQUIRED 0**, with OPTIONAL O-1..O-6. ChatGPT promoted
O-1 to REQUIRED R-1 for report provenance/semantic wording. R-1 was subsequently
corrected and accepted; **O-1 is SATISFIED**. Remaining dispositions:

| Finding | Disposition |
| --- | --- |
| O-2 — Chart common-scale change | DEFER |
| O-3 — Parse-hashed-bytes TOCTOU hardening | NONBLOCKING |
| O-4 — Selected-action SQL-test hardening | DEFER |
| O-5 — Additional synthetic failure branches | DEFER |
| O-6 — Extended run/git/config provenance | DEFER / NONBLOCKING |

Final accepted **deterministically selected category exemplars**, not a
statistically representative sample:

| Category | Accepted `game_index` | Exact WW `delta_us` |
| --- | --- | --- |
| Maximum Stage-3 WW advantage | 73758 | -27009085 |
| Median-delta WW exemplar | 73024 | -16487355 |
| Closest-to-zero Stage-3 WW advantage | 93557 | -7877513 |
| Stage-2 WW advantage | EMPTY | — |
| Exact WW tie | EMPTY | — |
| WL | EMPTY | — |
| LW | EMPTY | — |
| LL | 1 | — |

Lower-median zero-based rank: **18850 of 37702 WW**. Unique selected games:
**1, 73024, 73758, 93557**. No visual/manual substitution occurred. These results
are fixed; acceptance/closeout does not replace or rerun exemplar selection.

| Game | Outcomes | Stage-2 / Stage-3 actions | Stage-2 / Stage-3 Model C us | Reconciliation / interpretation |
| --- | --- | --- | --- | --- |
| 1 | LL | 4 / 4 | 720354 / 720354 | Termination costs only, not time-to-win |
| 73024 | WW | 313 / 207 | 53655374 / 37168019 | Exact G4 delta -16487355 us |
| 73758 | WW | 320 / 177 | 57365067 / 30355982 | Exact G4 delta -27009085 us |
| 93557 | WW | 279 / 204 | 47034727 / 39157214 | Exact G4 delta -7877513 us |

Final corrected report:
`results/stage3-timeline-analytics/20261017T113748060625Z-99dafa139703/report.html`.
Size: **470817 bytes**. SHA-256:
`b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3`.
Corrected report-script SHA-256:
`50f9d88e80b971596de59eadae1bb3bf96ee0d4da88d252684a7cbf0a15eb387`.
The earlier
`results/stage3-timeline-analytics/20261017T103913620889Z-54082dd14870/report.html`
is preserved as historical pre-final 3B evidence. Both reports are ignored local
evidence; **do not overwrite or delete either report**. No further report
generation is part of this acceptance record.

Accepted R-1 semantics: both displayed solver timelines are **post-hoc Model C
evaluations of persisted actions**. Stage 2 did not natively declare Model C;
Stage-3 collection declared it and checked its native total, but the reduced
persisted report events retain no native per-action costs/cursor fields.
Stage-2 compute scope is analysis; Stage-3 scope is analysis plus planning;
historical scopes/environments differ and no cross-stage compute-speed winner
is inferred. Stage-2 guess candidate count is exact-minimum-risk tie multiplicity /
final selector pool size. Official Stage-3 candidate count remains unavailable,
including on guesses. Missing native cursor/action-cost fields, Replay timestamps,
full probability coordinate maps and chosen plans are not fabricated.

All four official artifact hashes, run/prefix/paired identity and selected WW G4
deltas revalidated. Official artifact bytes, sizes and modification timestamps
remained unchanged; no new DB sidecars appeared. No solver, Engine, board
generation, official 100k rerun, Human data or ZiNi holdout was used.

### Final Slice-4 acceptance

**COMPLETE / ACCEPTED; FINAL ACCEPTANCE PASS / CLOSED; BLOCKER 0 / REQUIRED 0.**
Approved interpreter: `C:\venvs\minesweeper\Scripts\python.exe`, Python 3.12.10,
64-bit AMD64. Focused/frozen **386 discovered / 386 PASS**, 0 failures/errors/skips,
6.198 s unittest / 6.935 s process. Full source **2184 discovered / 2184 PASS**,
0 failures/errors/skips, 141.186 s unittest / 144.019 s process, using
`C:\venvs\minesweeper\Scripts\python.exe -B -m unittest discover -s tests -v`.
Ordinary tests included solver/Engine execution; no official benchmark/evidence
rerun occurred. Source/report reconciliation and final report/document inspection
passed. No fresh package/build/native GUI gate was required or run because no
production GUI/package surface changed.

Ignored local evidence: `results/stage3-timeline-analytics-closeout/20261017T131224859Z/`
contains `focused-tests.txt`, `full-tests.txt` and `acceptance-summary.json`.
All four official artifact and frozen Model C hashes reauthenticated; artifact
bytes/timestamps and both reports were unchanged, with no DB sidecars. The final
report's generation HEAD `c32e34c...` / `git_dirty=True` is accepted provenance:
its script SHA matches the exact script committed in qualified candidate `4c488e...`.
Full identities and report preservation are in the [closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md).
No Claude re-audit after R-1 is claimed or required; ChatGPT/Codex verified its
wording-only correction through source/tests/report. O-6 remains DEFER / NONBLOCKING:
current artifact/run/model/script provenance is sufficient and does not justify
regenerating an accepted report.

**NEXT — evidence-guided human/domain interpretation of the accepted fixed
exemplars and report**, to choose/specify the first actual Extended algorithm
research direction. Any algorithm change or research implementation requires a
separate explicit scope/specification decision; none is authorized by closeout.

Stage-3 V1 / Model C remain **CLOSED / FROZEN**. Same-board Human / Stage-2 /
Stage-3 Comparison remains **FINAL ACCEPTANCE PASS / CLOSED**. ZiNi Improvement
remains **CLOSED**; its unopened final holdout must not be used.

## 1. Purpose and authorization boundary

Produce reproducible, outcome-aware, read-only demonstrations from the already
accepted official Stage-2 / Stage-3 benchmark evidence. Show where recorded
physical-model cost, action effects, risk metadata and compute diagnostics occur,
so later Extended algorithm research can be chosen from evidence.

This milestone does **not** implement a new algorithm. Its demonstrations are
reports with bounded static timeline visualization, not synchronized gameplay or
a new production Qt viewer. Existing Same-board and Stage-3 Visualizer features
retain their accepted responsibilities and behavior.

Slice 0 drafting was documentation-only; that temporary task authorization is
historical. **Slices 0, 1 and 2 are COMPLETE / ACCEPTED by ChatGPT final review.**
**Slice 3 — Read-only accepted-evidence report / static visualization, including
internal Slices 3A and 3B, is COMPLETE / ACCEPTED.** **Slice 4 is COMPLETE /
ACCEPTED; this milestone is FINAL ACCEPTANCE PASS / CLOSED.** The module and
technical boundaries below remain unchanged. Preserve accepted selection and
both report runs. Next work is human/domain interpretation to specify a research
direction; actual algorithm implementation requires separate explicit scope approval.

**Slice 3 was the FIRST scope authorized to authenticate and read the exact accepted
official Stage-2/Stage-3 DB and G4 artifacts.** Internal Slice 3A completed that
preflight without exemplar selection. **Internal Slice 3B first selected and
disclosed actual official exemplar IDs**, using **only the
already-accepted deterministic rules**.
No visual/manual substitution is allowed after selection. **Read-only/report
output only:** do not rerun the official 100k or any solver, and do not modify
frozen official evidence. Slices 0–2 accessed no official evidence and selected
no actual official exemplar IDs.

The qualified implementation was accepted on `feature/stage3-timeline-analytics`.
Live Git remains authoritative for current branch/HEAD and integration state;
a later documentation-only commit does not replace the qualified candidate.

The roadmap is:

6. **CLOSED — Representative-board Demonstrations / Timeline Analytics**:
   Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 1 — Pure timeline analytics COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE / ACCEPTED.
   Internal Slice 3A — accepted-evidence opening correction / preflight COMPLETE / ACCEPTED.
   Internal Slice 3B — selection / selected-action report COMPLETE / ACCEPTED.
   Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED.
7. **NEXT — evidence-guided interpretation leading to first actual Extended
   algorithm research**. Interpret the fixed exemplars/report before selecting
   a direction; implementation requires a separate explicit scope/specification decision.

## 2. Authoritative input family and artifact identity

The first implementation accepts **only the accepted official Stage-2 / Stage-3
benchmark artifacts**, for `EXPERT_GENERAL_V1`, exact prefix `[0,100000)`, under
the frozen canonical opening/model configuration. Human recordings, arbitrary
benchmark runs and native full-decision execution bundles are not this version's
input family.

Required identities, preserved in the [V1 final adjudication](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md):

| Artifact | Required SHA-256 |
| --- | --- |
| Stage-2 accepted analysis DB | `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` |
| Stage-3 accepted analysis DB | `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e` |
| G4 comparison | `f31226a660eda02a804ee41c66f233513fd950cac6f6123f36bf62578fbf5979` |
| G4 result | `09f228ee9a8ec96a934dbb94656a7cd6f03c7987640df267f5fd6818dd007cc0` |

Before any real-evidence report is accepted, verify **all four exact artifact
hashes** against these identities. A display label, filename, matching size or
matching `run_id` is not authentication. Do not silently substitute another
DB/copy/artifact. Missing or mismatching inputs fail explicitly; do not repair,
backfill or regenerate them. Slice 0 records these requirements; it does not
claim a new four-artifact verification has been performed.

The [V1 evidence location guide](../stage3-v1/README.md) identifies preserved
artifact locations. Paths locate inputs; verified contents establish identity.
The report must retain exact source paths/hashes, source roles, run IDs, solver
and telemetry identities, declared corpus/prefix, paired game identities and
model/evaluation provenance. Source identity must not be reducible to run ID:
the two accepted analysis artifacts can both contain `run_id=1`.

Use completed, stable artifacts. Read-only connections alone do not establish
an atomic snapshot across changing files. Verify lifecycle/coverage and source
stability as well as hashes; keep connection ownership in the report adapter.
Do not initialize/migrate a database, checkpoint official evidence, or create
new telemetry. **The official 100k corpus must not be rerun.**

Frozen Model C remains unchanged. Reuse
[`ModelCEvaluation`](../../benchmark_modeled_time.py) and
[`stage3_physical.py`](../../stage3_physical.py) authentication of actual profile
bytes and stored integer table. The profile SHA-256 remains
`52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`;
the timing-table SHA-256 remains
`7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b`.
Do not regenerate the table from fitted parameters or add a profile selector.

## 3. Evidence and metric authorities

Reuse [`GameRecord` and `ActionEvent`](../../telemetry_model.py) and existing
validators where reasonable. An immutable dataclass alone does not establish
official provenance, complete action order or agreement with game summaries.

| Authority | Meaning and required interpretation |
| --- | --- |
| Recorded event facts | Actual semantic action index/type/target, status after, safe reveal delta and explicit flag delta. Preserve order and recorded values. |
| Recorded decision metadata | Inference category, exact target/minimum probability and candidate count when present; never infer missing values from outcome or hidden layout. |
| Model C action/cumulative cost | Deterministic post-hoc evaluation of persisted targets under authenticated frozen Model C, in integer microseconds. |
| `decision_compute_ns` | Recorded runtime diagnostic, in nanoseconds; separate from modeled execution cost. |
| Action ordinal | Sequence position, not time, equal progress or an equivalent decision across solvers. |
| Safe-cell and explicit flag effects | Recorded execution effects; neither is a time authority or normalized progress measure. |
| Chart geometry and formatting | Presentation only; conversions must not alter exact backend values, selection or totals. |

Neither official SQLite schema retains native `cursor_before`,
`modeled_action_us`, total modeled time, Replay timestamps, full probability
coordinate maps or chosen plans. Both report timelines therefore use **post-hoc
Model C evaluation of persisted actions**. Stage 2's historical telemetry has no
native Model C declaration; Stage 3 declares frozen Model C and its collection
path checked native totals, but its reduced persisted events do not retain those
native cost fields. Preserve that provenance distinction without fabricating
native records or backfilling historical metadata.

Stage-2 compute timing covers decision analysis; Stage-3 timing covers analysis
plus planning. Timing scopes and historical environments differ. Do not publish
a generic compute-speed winner, add compute time to Model C, or treat either as
benchmark wall time or measured Human execution time.

Preserve exact probabilities as `Fraction` values using the existing
[probability codec](../../telemetry_repository.py). Do not use floating-point
approximations or SQL numeric casts of rational text for selection or equality.
Missing values remain absent, not zero. In particular:

- The canonical first OPEN has no analyzed decision or compute measurement.
- A CHORD's target probability is absent; its target is an already-open clue.
- Stage-2 candidate count means the final selector pool size; on a probability
  guess it is the exact-minimum-risk tie multiplicity.
- Official Stage-3 candidate count is absent, including on guesses. Do not copy
  Stage-2 counts into Stage-3 records or reconstruct missing candidate geometry.

Model C cost is **joint movement-plus-target-input cost**, not measured movement
time and not a separately measured movement/click decomposition. Use the frozen
stored table, including positive same-cell cost. The initial cursor is `(0,0)`;
count the canonical first input and every executed input through termination,
including a losing input. Automatic Engine effects are not extra inputs.

For LOSS, modeled cost means **cost through termination**, never time-to-win.
Primary paired speed interpretation remains **WW-only**. Whole-prefix and LOSS
costs may appear only as descriptive/diagnostic facts. A lower termination cost
in WL, LW or LL is not a speed-to-win benefit.

## 4. Independent timeline semantics

There is **no common synchronized execution timeline**. Each solver owns its
own sequence. The first version's horizontal coordinate is:

**completed semantic action count**

- Origin: `0` completed actions, zero cumulative modeled cost and zero cumulative
  safe reveals, with no fabricated event, decision, risk or compute measurement.
- Persisted zero-based `action_index = i`: the after-action point has completed
  semantic action count `i + 1`.
- Per-action status/effects refer to that recorded action's after-state. The
  recorded final outcome is a separate run-level fact.
- Equal Stage-2 / Stage-3 action counts do **not** imply equal board state,
  progress, information or decision effort.

The same authenticated frozen Model C provides a shared **measurement scale**,
not a shared execution clock. Independent rows/small multiples may use comparable
units/scales. Do not introduce a common playhead, ordinal mapping, normalized
progress or wall-clock synchronization.

No Engine reconstruction is needed for this persisted-evidence report. Analytic
and report paths must not call solvers, planners, workers, `Engine.step`, board
generation or hidden-layout recovery to fill missing evidence.

## 5. Deterministically selected category exemplars

Use the precise concept **"deterministically selected category exemplars"**.
They are **not claimed to be a statistically representative sample**. The Korean
roadmap name may continue to say **대표 보드**, subject to this limitation.

These rules must be declared and accepted **before actual exemplar game IDs are
selected**. No actual official exemplar IDs were selected or disclosed in Slices
0–2 or internal Slice 3A; Slice 2 used bounded synthetic fixtures only. Internal
Slice 3B completed the first authorized real accepted-evidence selection and disclosure.
No visually interesting replacement is permitted
afterward. The first outcome letter below is Stage 2; the second is Stage 3.

Define exact signed integer:

`delta_us = Stage3_model_c_us - Stage2_model_c_us`

| Category | Fixed selection rule |
| --- | --- |
| Maximum Stage-3 WW advantage | Among WW with negative delta, select minimum `delta_us`; tie-break lowest `game_index`. If none, EMPTY. |
| Median-delta WW exemplar | Sort all WW by `(delta_us, game_index)`; select zero-based lower-median index `(N - 1) // 2`. If WW is empty, EMPTY. |
| Closest-to-zero Stage-3 WW advantage | Among WW with negative delta, select greatest `delta_us`; tie-break lowest `game_index`. If none, EMPTY. Do not call it "near tie" without a separately defined tolerance. |
| Stage-2 WW advantage | Among WW with positive delta, select largest positive `delta_us`; tie-break lowest `game_index`. Otherwise EMPTY. |
| Exact WW tie | Select lowest `game_index` with `delta_us == 0`. Otherwise EMPTY. |
| WL | Lowest `game_index` in WL, or EMPTY. |
| LW | Lowest `game_index` in LW, or EMPTY. |
| LL | Lowest `game_index` in LL, or EMPTY. |

Selection must be independent of input ordering. If one game satisfies multiple
categories, retain **all category memberships**, load its detailed action streams
once, and do not replace it for visual variety. Report rules, population sizes,
membership, applicable ranks/metric values, tie-breaks and empty categories.

Accepted historical corpus facts are WW **37,702**, WL **0**, LW **0**, LL
**62,298**, with all accepted WW deltas favoring Stage 3. Treat these as accepted
evidence for these exact artifacts, not a universal solver or selector invariant.
Do not manufacture Stage-2-faster, exact-tie or cross-outcome examples.

Reuse the accepted G4 per-WW delta list for ranking. Load and validate paired
game summaries independently so missing identities cannot disappear through an
inner join. Load detailed action rows **only for selected games**; do not rerun
the all-action official comparison merely to select examples. Reconcile selected
game cost totals exactly with their accepted G4 deltas. For WL/LW/LL, retain
outcomes and descriptive termination costs without a speed-to-win interpretation.

## 6. Kept analytics

### Per-action facts and derived values

- Action ordinal/type/target and status after.
- Integer Model C action cost and cumulative Model C cost.
- Signed target displacement `dx`/`dy` from the previous target, initially `(0,0)`.
- Geometric displacement where clearly labeled as cell-center geometry, not an
  observed Human or OS cursor trajectory; use an explicit geometric definition.
- Recorded `safe_cells_opened_delta` and cumulative safe reveals.
- Recorded `explicit_flag_delta`, separate from automatic Engine effects.
- Recorded inference category.
- Exact stored target/minimum probability when present.
- Stage-2 selection candidate count when present.
- Recorded `decision_compute_ns` when present, separately labeled diagnostic.

### Summary and report views

- Total semantic action count and OPEN/FLAG/CHORD input counts.
- Cumulative Model C cost and cumulative safe-reveal curves on each run's own
  completed-action-count axis.
- Model C action-cost spikes and long target transitions.
- Certainty-FLAG cost exposure: cost assigned to executed certainty FLAG inputs,
  with outcome and denominator explicit if a share of total cost is shown.
- FLAG/CHORD sequence facts and actual CHORD reveal effects.
- Guess locations and exact stored risk metadata.
- Stage-2 minimum-risk tie multiplicity on recorded guess events.
- Per-run compute diagnostic spikes, without a cross-stage compute-speed winner.

Any spike/long-transition ranking, display limit or threshold must be documented
and deterministic; it must not change the exemplar categories. Exact row facts
remain available beneath presentation summaries.

Certainty-FLAG exposure is **not recoverable savings** from removing flags.
Sequence adjacency does not establish causal FLAG-to-CHORD payoff. Actual CHORD
reveal deltas are not a planner's predicted reveal value. No new counterfactual
or causal algorithm claim follows from these descriptive analytics.

## 7. Human data, deferred scope and non-goals

Human Replay / Human Mouse Trace are **DEFERRED from the first implementation**
because this version is an official benchmark evidence report for later Stage-3
algorithm research. This loses Human timeline demonstrations in this version,
not the accepted Human recording or Same-board Comparison functionality.

Do not fabricate benchmark identity for Human data, Human Model C time, Human
decision category or a Human/solver shared clock. Layout equality alone does not
establish benchmark membership. Existing authorities remain separate:

`Human Replay elapsed != Human Mouse Trace clock != solver Model C cost != decision compute != UI presentation time`.

| Disposition | Scope |
| --- | --- |
| DEFER | Human timeline adapter and Human path analytics |
| DEFER | Native full decision/probability/plan adapter; official Stage-3 candidate geometry/count recovery |
| DEFER | Causal FLAG-to-CHORD payoff and avoidable-backtracking classifier |
| DEFER | Nearest-risk counterfactual whole-run savings and Known-Mine/No-Flag savings |
| DEFER | Planner phase attribution |
| DEFER | Interactive timeline GUI and solver cursor/path overlay |
| DEFER | Analytics export framework; one bounded report artifact remains in scope |
| REJECT FOR THIS MILESTONE | Synchronized Human/Stage-2/Stage-3 timeline; normalized progress; generic speed winner |
| REJECT FOR THIS MILESTONE | DB/schema changes and new telemetry |
| REJECT FOR THIS MILESTONE | Model C changes/refit; algorithm/profile selection; actual Extended algorithm implementation |
| REJECT FOR THIS MILESTONE | Hidden-layout solver analysis or recovery of absent inference evidence |

Deferring native decision adapters omits full candidate geometry, chosen-plan
internals and related explanations; do not synthesize them from reduced events.
Recorded Stage-2 candidate counts do not establish Stage-3 candidate pools.

Existing Same-board standard QSlider track-click UX remains **OPTIONAL / DEFER**.
Human recorded trace versus synthetic solver movement remains **KEEP** as separate
authorities. This milestone supplies no reason to change either disposition or
reopen the [closed Same-board contract](STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md).
The [extension backlog](../../STAGE3_EXTENSION_BACKLOG.md) is historical/provisional,
not authorization to implement an extension.

## 8. Module and ownership boundary

`timeline_analytics.py` and `representative_boards.py` are implemented and accepted
in Slices 1 and 2 respectively. The report entry point
[`scripts/stage3_timeline_report.py`](../../scripts/stage3_timeline_report.py) is
implemented and accepted in Slice 3B; the ownership boundaries are unchanged:

| Component | Responsibility and exclusions |
| --- | --- |
| `timeline_analytics.py` | Pure, Qt-independent projection from one validated `GameRecord`, ordered `ActionEvent` stream and explicit authenticated `ModelCEvaluation` into immutable per-run analytics. No DB, clock, Engine, solver or UI ownership. |
| `representative_boards.py` | Pure deterministic selection over validated paired outcome/delta facts using section 5. No artifact I/O or solver execution. |
| Thin report entry point under `scripts/` | Accepted artifact path/hash verification, read-only DB connection lifetime, run/source identity validation, paired summary loading, selected-game action loading only, and report/static visualization output. |

Reuse existing authoritative models and validators where reasonable:

- [`telemetry_model.py`](../../telemetry_model.py): immutable event/game facts.
- [`telemetry_repository.py`](../../telemetry_repository.py): read-only connection
  and exact probability codec; never use writer/migration paths for this report.
- [`benchmark_statistics.py`](../../benchmark_statistics.py): source-aware pairing,
  exact prefix coverage and official lifecycle eligibility.
- [`benchmark_modeled_time.py`](../../benchmark_modeled_time.py): model/run identity
  and complete ordered-action validation/cost reconstruction.
- [`benchmark_comparison.py`](../../benchmark_comparison.py): established delta,
  outcome and WW interpretation; reuse preserved results without an all-action rerun.

Validate selected raw stream/summary agreement, not just dataclass construction.
Preserve original events and source/run/game/evaluation provenance. Completed
action count is derived from the validated index; no duplicate authoritative
counter or universal event hierarchy is necessary. An existing validator's
structural checks do not constitute a fresh proof of every historical inference.

Do not create a universal event model, solver registry, EventBus, universal
playback abstraction or analytics database. Do not fabricate native execution
objects to fit an existing viewer. The pure analytics layer does not load profiles;
its caller supplies explicit already-authenticated evaluation configuration.

## 9. Report and output boundary

**No production Qt UI is required or included.** The final reproducible report
must contain:

- Exact source/artifact/model and evaluation provenance.
- Declared selection population, rules, selected category memberships and EMPTY
  categories, without claiming statistical representativeness.
- Outcomes and action summaries.
- Per-run independent timeline tables and bounded static timeline visualization.
- Cumulative Model C cost and cumulative safe reveals.
- Separately labeled inference/risk/compute diagnostics.
- Explicit unavailable/missing evidence and interpretation limitations.

Generated report/evidence belongs under a **new ignored `results/` location**,
such as a new run directory under `results/stage3-timeline-analytics/`. Do not
overwrite frozen official evidence or existing report runs. No such output is
generated in Slice 0.

Do not add a plotting dependency merely for convenience. Exact rendering
technology remains an implementation detail unless needed for truthful
reproducibility. Preserve exact backend values; chart conversions are presentation
only. Reproducibility covers declared inputs/rules, selected membership and exact
analytical values; record rendering details needed to reproduce the display.

## 10. Slice plan and gates

| Slice | Deliverable and gate |
| --- | --- |
| 0 — Contract | COMPLETE / ACCEPTED by ChatGPT final review. This document and current milestone status establish the accepted contract before implementation or actual exemplar-ID selection. |
| 1 — Pure timeline analytics | COMPLETE / ACCEPTED by ChatGPT final review. Immutable single-game projection in `timeline_analytics.py` and focused tests in `tests/test_timeline_analytics.py`; 28 focused PASS and 257 bounded existing regressions PASS, with four execution cases intentionally excluded and no full-suite claim. No actual exemplar IDs selected. |
| 2 — Pure deterministic exemplar selection | COMPLETE / ACCEPTED by ChatGPT final review. `representative_boards.py` and `tests/test_representative_boards.py`; 29 focused, 28 Slice-1 timeline and 75 bounded comparison/statistics regressions PASS, total 132 PASS. Selector fixtures were synthetic/in-memory; no official evidence access or actual official exemplar-ID selection. |
| 3 — Read-only accepted-evidence report / static visualization | COMPLETE / ACCEPTED as a whole, including internal 3A and 3B. No official 100k/solver rerun or frozen-evidence modification. |
| 3A — Internal opening correction / preflight | COMPLETE / ACCEPTED by ChatGPT final review. Explicit immutable read-only seam and accepted-evidence identity/coverage/pairing/outcome/WW-set checks PASS; 67 repository + 238 bounded regressions = 305 PASS, four execution tests excluded, no full-suite claim. No actual exemplar IDs selected or disclosed. |
| 3B — Internal selection / selected-action loading / report | COMPLETE / ACCEPTED; SLICE 3B FINAL PASS, BLOCKER 0 / REQUIRED 0 / OPTIONAL 5. Fixed selection, selected-only detail loading and corrected static report accepted; 158 focused + 174 bounded regressions = 332 PASS, four execution tests excluded, no full-suite claim at Slice 3B. |
| 4 — Acceptance / closeout | COMPLETE / ACCEPTED. Final source/report/document reconciliation and frozen/full regressions PASS: 386 focused / 2184 full, zero failures/errors/skips. FINAL ACCEPTANCE PASS / CLOSED. No fresh package/build/native GUI gate required or run. |

**Slices 0–4, including internal Slices 3A and 3B, are COMPLETE / ACCEPTED;
FINAL ACCEPTANCE PASS / CLOSED.** Stage-3 Extended remains ACTIVE. Preserve
accepted exemplar memberships and both report runs. Internal 3A/3B subdivide
Slice 3; they do not create new milestones.
Do not mark a slice accepted without its review/evidence.
Package/native GUI acceptance is conditional on a later GUI/package-surface change,
not a requirement of this report boundary.

## 11. Acceptance contract

### Pure analytics and authority checks

- Exact integer Model C action/cumulative reconstruction, including first and
  terminal/losing inputs; exact final totals and nonempty completed streams.
- Exact zero-based event-index/completed-count semantics and origin without a
  fabricated action, risk, category or compute measurement.
- Contiguous ordered actions, supported domains, no early/post-terminal tail,
  final outcome/status agreement and selected raw-event/game-summary consistency.
- Safe-reveal/explicit-flag effects remain recorded facts; automatic Engine effects
  are not extra inputs. No source mutation or missing-value-to-zero coercion.
- Exact `Fraction` preservation; nullable metadata and differing compute scopes
  remain explicit; no generic time or compute-speed winner.
- No solver/planner/worker/`Engine.step` calls, board generation or hidden-layout
  recovery in analytics/report paths, including attempts to fill missing evidence.

### Selection and provenance checks

- Deterministic selection independent of input ordering, signed-delta convention,
  lower median, exact ties, EMPTY categories and retained duplicate memberships.
- Positive/negative/zero deltas and WW/WL/LW/LL covered with bounded fixtures;
  current historical empty categories are not hardcoded universal invariants.
- Exact four-artifact hash checks, model authentication and explicit missing or
  mismatching input failures without substitution or mutation.
- Source identity is not `run_id` alone; compatible role/config/corpus/opening and
  independent full-prefix summary coverage/pair identities are checked.
- Real report acceptance reads complete selected-game action streams only and
  reconciles selected-game totals exactly with accepted G4 deltas where supplied
  for WW. Non-WW costs retain diagnostic termination semantics.
- Report documents rules, source population, memberships, emptiness, unavailable
  evidence and the absence of statistical-representativeness/causal claims.

### Regression and presentation acceptance

- Run relevant frozen V1 / Model C, telemetry, pairing and comparison regressions;
  preserve frozen profile/table and historical evidence identities.
- Run full source regression at closeout using the approved project interpreter.
- Test report/static-rendering output as appropriate and inspect exact labels,
  independent axes, curves, tables and outcome-specific wording.
- No production Qt UI tests or fresh package/native GUI acceptance are required
  for this report-only scope. Add those gates only if the production GUI/package
  surface later changes under a separately accepted scope decision.
- Do not rerun the official 100k, generate new solver evidence, use the unopened
  ZiNi holdout or overwrite accepted artifacts for acceptance.

Slice 0 validation is documentation-only: inspect diffs, run `git diff --check`,
validate local Markdown links where practical, confirm only the intended contract
and current-state documents changed, and confirm nothing staged. It makes no new
test, benchmark, package, GUI or real-report acceptance claim.

## 12. References and preserved decisions

- [Final closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)
- [Current handoff](../CURRENT_HANDOFF.md)
- [Extended roadmap](README.md)
- [V1 final adjudication and artifact identities](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Frozen telemetry/benchmark specification](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Same-board contract](STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md)
- [Same-board closeout and deferred UX](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md)
- [Historical/provisional extension backlog](../../STAGE3_EXTENSION_BACKLOG.md)

Historical closeouts retain their dated status and evidence. This contract and
the current handoff/Extended roadmap record accepted Slices 0–4, including
internal 3A/3B, and the closed Timeline milestone without rewriting historical
closeouts. Next work is interpretation; no new algorithm implementation is authorized.
