# Program K Research Trace Visualization / Comparison Closeout

Recorded: **2026-11-01 (Asia/Seoul)**. This is a non-frozen closeout record.

**PROGRAM K RESEARCH TRACE VISUALIZATION / COMPARISON — FINAL ACCEPTANCE PASS / CLOSED**

## 1. Scope and acceptance authority

This closes the separately authorized D0–D5 research/demo path: read preserved
accepted E1 executions, project immutable presentation data, replay completed K
traces, show logical-known mines, and compare CONTROL with K-P0 on the exact same
board. No new K or CONTROL game was needed to produce the demo.

Implementation authority is current committed source/tests at
`fb59d5fa253f04f50ea57c6a9e863aa1999a517e`. The final package records establish
automated qualification. The project user's subsequent **A–H PASS** report,
explicitly supplied with the 2026-11-01 documentation-refresh authorization,
establishes final native packaged acceptance.

The generated [D5 acceptance record](../../results/program-k-trace-demo-final-acceptance/20261031-230251/acceptance.json)
truthfully retains `D5_AUTOMATED_PACKAGE_PASS` and `PENDING USER` from its creation.
It has **not** been edited or relabeled. This tracked closeout records the later
user acceptance; source-native R2 approval alone was not package approval.

## 2. Scientific boundary

| Boundary | Final current state |
| --- | --- |
| Phase-1 final disposition | **PHASE1_INCONCLUSIVE_TRANSFER** |
| Phase-1 Attempt #2 execution/integrity | **PASS** |
| Measurement quality | **PASS** |
| Phase 2 | **NOT AUTHORIZED** |
| R0-B | **NOT RUN / NOT AUTHORIZED** |
| Actual E2 | **NOT RUN / NOT AUTHORIZED** |
| Program K effectiveness | **NOT ESTABLISHED** |
| Current de-dup remediation-class timing profiling | **STOP / DEFER** |
| Project-path reason | **UNBOUNDED_RESEARCH_RISK** |
| Production K integration | **NOT STARTED** |
| Gate P | **NOT PASSED / NOT AUTHORIZED** |

This is neither `PHASE1_NO_GO`, an Actual E2 failure, nor proof that Program K is
ineffective or impossible. Demo acceptance establishes no statistical superiority,
speedup, production readiness or official Stage-3 replacement.

Fresh R0-A V2 Attempt #2 remains accepted operational evidence: static storage
blocker resolved, timing regressed, overall remediation **PARTIAL SUCCESS**.
Profiling Attempt #1 stopped on `MONITOR_GAP`; its decomposition is partial
diagnostic evidence. After monitor remediation/qualification, Attempt #2 completed
with accepted execution/integrity and measurement quality, followed by the
inconclusive transfer adjudication above. Continuing the current de-dup class is
deferred for unbounded research risk, not resumed for reassurance.

The local external timing-profile package is a recovery aid at
`C:\Users\User\.codex\visualizations\2026\10\30\01a18cf8-cb06-7f51-baab-bc05c6fcc53d\program-k-timing-profile-v1`.
Attempt #1 is `phase1-2a3e6bf1b5fc424ba719d13b23afaa3d`; Attempt #2 is
`phase1-3a840bf767e146cf8c2bcad5d9004e3b`. The latter's driver/supervisor records
say `MEASURED_REVIEW_REQUIRED`, with `ELIGIBLE_FOR_MODEL_REVIEW_ONLY` measurement
quality and `implementation_review_go = false`; these raw statuses are not an
effectiveness verdict. The final disposition and STOP/DEFER decision above are
the accepted adjudications supplied by the user. AI agreement is not proof.

## 3. Source lineage and frozen authorities

| Identity | Role |
| --- | --- |
| `6106f730320c35e7123a75526f34dbeadeef3c5d` | Historical Actual E1 technical baseline |
| `fba3da048d4639dd16cecd41c7f9da21869bd70a` | Historical E1 execution-time documentation HEAD |
| `48f6ebc97e6c4d3ed4a746a92a8d169783803bf9` | Qualified remediation/R0-A technical anchor; not the demo's final source identity |
| `a7abce49f4f98d2db02695943c299f86a212344d` | Recorded Fresh R0-A V2 Attempt #2 / profiling source HEAD |
| `05920abeaec541a52fd22753dadec66f5cb98bca` | Historical first committed D1–D4.2 visualization source / earlier package qualification |
| `fb59d5fa253f04f50ea57c6a9e863aa1999a517e` | Final R1/R2 exhibition source and fresh D5 package source |

Historical E1/R0 records are not relabeled as runs at the final viewer HEAD.
The earlier package root `results/program-k-trace-demo-final-acceptance/20261031-175417/`
remains unchanged historical evidence, not the final package.

Preserved authorities:
[Research Spec](STAGE3_PROGRAM_K_RESEARCH_SPEC.md),
[Gate-R E0/E1 Protocol](STAGE3_PROGRAM_K_GATE_R_PROTOCOL.md),
[Actual E1 closeout](STAGE3_PROGRAM_K_E1_CLOSEOUT.md),
[E2 Effectiveness Protocol](STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md),
[R0 Attribution Amendment](STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md),
[V1.3.1 design](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md) and
[design acceptance](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md).
Their historical authorization/status wording and exact frozen bytes remain intact.

## 4. D0–D5 slice disposition

| Slice | Accepted responsibility | Status |
| --- | --- | --- |
| D0 | Separate read-only research/demo authority; no production/Gate-P substitution | PASS / CLOSED |
| D1 | Immutable accepted-E1 K-P0 evidence admission/projection | PASS / CLOSED |
| D2 | Completed K physical trace viewer and playback | PASS / CLOSED |
| D3 | Committed logical-known-mine layer, public FLAG separation | PASS / CLOSED |
| D4 | CONTROL sibling adapter, exact pair model, independent side-by-side Qt panels | PASS / CLOSED |
| D5 | Final source/package qualification and user A–H acceptance | FINAL ACCEPTANCE PASS / CLOSED |

D4.0 pairing audit, D4.1 evidence/pair model and D4.2 Qt comparison were completed.
D4 is implemented, not a currently deferred comparison proposal. R1/R2 presentation
corrections also received PASS / CLOSED before this final fresh package.

## 5. Implemented algorithm and D1 evidence boundary

The accepted experimental algorithm still exists: K-C logical-known-mine capability
in [program_k_capability.py](../../experiments/program_k_capability.py), K-P0 physical
policy in [program_k_policy.py](../../experiments/program_k_policy.py), and
`run_k_p0()` in [program_k_runner.py](../../experiments/program_k_runner.py).
It executed real OPEN / FLAG / CHORD inputs with logical set M distinct from public
physical FLAG. This viewer does not invoke that runner or its solver/Engine work.

[program_k_trace_adapter.py](../../experiments/program_k_trace_adapter.py) uses
stdlib-only, bounded, byte/hash-pinned admission. `load_accepted_e1_traces()` /
`project_accepted_e1_traces()` return frozen `KTracePresentation`, `KTraceFrame`,
`KActionView`, identity/provenance and terminal-reference records. The reader binds
historical source, schedule, actions, observations, cursors, exact costs and archived
PASS audits; it does not rerun those audits or instantiate historical solver classes.
Corrupt, incomplete or inconsistent inputs fail closed. D1 remains K-P0-only.

The accepted archive retains 18 completed K-P0 results. The launchers select the
four repetition-1 cases below, loading once before UI navigation. No Engine replay,
board generation, evaluator, worker or navigation-time evidence I/O is required.

## 6. D2 presentation and playback

[program_k_trace_viewer.py](../../experiments/program_k_trace_viewer.py) supplies
`KTracePlayer`, `KTracePlayback` and the read-only K board. Public observations are
displayed directly from admitted frames, including terminal LOSS feedback and
automatic WON flags. Frame 0 fabricates no selected action.

First/previous/next/last, direct index seek, play/pause, `Index` and `Model C Time`
operate on immutable in-memory records. Model-C action/cumulative microseconds come
from D1. Model C is not wall time, CPU compute time or recorded human time.
The completed route contains only executed targets. Smooth straight cursor geometry
is synthetic presentation, not a recorded mouse trajectory.

Stable mechanics are reused from `Stage3ModeledPlayback` and the completed-route
painter in `visualization_reference_overlays.py`. K is not coerced into
`Stage3Execution` / `Stage3RunResult`; accepted production playback semantics stay
unchanged.

## 7. D3 logical-known-mine authority

`ordinary HIDDEN != logical-known mine still physically HIDDEN != physical FLAG`.

- Frame 0: M is empty. For k > 0, `frame.logical_mines` is D1's admitted state
  after exactly k physical inputs (`actions[k-1].preinput_M`); no next-action lookup.
- `frame.hidden_logical_mines` supplies the green diamond overlay. It is not
  calculated from terminal `answer_reference` or hidden truth.
- A physically flagged known mine keeps the physical FLAG as the primary glyph;
  logical provenance remains in its details. Explicit flags and automatic WIN
  flags stay separately identified.
- Partial synthetic motion keeps public board, logical M, completed route and
  cumulative Model C at the committed frame. Only cursor/target presentation moves.
- Automatic WIN flags and terminal answer disclosure do not manufacture K knowledge.
  Hidden-answer/reference truth is a separate concept; this demo has no answer toggle.
- Layer order is public cells → mouse-transparent logical marker → completed route
  → target → synthetic cursor. Marker visibility changes presentation only.

## 8. D4 exact pairs and independent panels

CONTROL is unchanged frozen V1 physical execution (`run_control_capture()`);
K-CONTROL is V1 physical execution with detached K shadow analysis and is excluded;
K-P0 is the actual Program K physical-action policy.

[program_k_control_trace_adapter.py](../../experiments/program_k_control_trace_adapter.py)
admits separate `ControlTracePresentation` records using archived V1, public-effect
and Model-C cost audits. Empty CONTROL `replay_audits` is correct. CONTROL is never
cast into a fake K model and has no logical M, K category or shadow knowledge.

[program_k_trace_comparison.py](../../experiments/program_k_trace_comparison.py)
constructs immutable `ProgramKComparisonPair` objects. Admission checks fixed
schedule/repetition, source/fixture identity, the same registration/materialization,
dimensions, first click, fingerprint and exact terminal mine layout, with distinct
operations/results. Partial admission publishes no pair set.

| Internal case | Visible name / board | CONTROL ↔ K-P0 schedule | Repetition |
| --- | --- | --- | --- |
| S-LIFECYCLE | 기본 예제 · 4×1 / 지뢰 1 | 6 ↔ 8 | 1 |
| S-REPLAN | 복합 동작 예제 · 6×4 / 지뢰 5 | 12 ↔ 14 | 1 |
| S-LOSS | 패배 예제 · 5×1 / 지뢰 2 | 18 ↔ 20 | 1 |
| X-0 | 상급 보드 예제 · 30×16 / 지뢰 99 | 24 ↔ 26 | 1 |

[program_k_trace_comparison_ui.py](../../experiments/program_k_trace_comparison_ui.py)
consumes admitted pairs only. Each panel owns its player, playback controller,
timer/clock, index, mode, interval, rate and partial motion. There is no shared
action index, normalized progress, race clock or synchronized semantic position.
Pair changes stop both panels, discard partial motion and reset to frame 0 from
memory. CONTROL has a public-only board; K preserves D3.

`RecordedDifference` means **K-P0 minus CONTROL**, descriptive arithmetic only.
OPEN/FLAG/CHORD counts below are executed physical inputs, not automatic WIN flags.

| Case | CONTROL: inputs; O/F/C; outcome; Model C µs | K-P0: inputs; O/F/C; outcome; Model C µs | Difference: inputs; O/F/C; Model C µs |
| --- | --- | --- | --- |
| S-LIFECYCLE | 4; 2/1/1; WON; 504,020 | 3; 3/0/0; WON; 432,614 | -1; +1/-1/-1; -71,406 |
| S-REPLAN | 15; 5/5/5; WON; 2,469,364 | 14; 8/2/4; WON; 2,382,644 | -1; +3/-3/-1; -86,720 |
| S-LOSS | 3; 2/1/0; LOST; 378,015 | 2; 2/0/0; LOST; 306,609 | -1; 0/-1/0; N/A |
| X-0 | 227; 42/99/86; WON; 39,987,084 | 180; 75/48/57; WON; 31,586,418 | -47; +33/-51/-29; -8,400,666 |

S-LOSS `model_c_us is None`: not applicable for speed-to-win interpretation. Its
two termination costs remain separate diagnostics, with Korean “비교하지 않음”.

## 9. Final R1/R2 exhibition wording

Title: **지뢰찾기 알고리즘 비교 — 기존 방식 vs 개선 방식 (Program K)**.
Panels: **기존 방식** / **개선 방식 (Program K)**.
The difference heading is **이 사례의 기록상 차이 (개선 방식 − 기존 방식)**,
with a sentence explaining that a negative value means a smaller recorded value.
“개선 방식” names the project-developed variant; it is not a proven performance claim.

Visible limitation: **저장된 연구 사례를 보여주는 화면이며, 통계적 성능 검증 결과는 아닙니다.**
Short Korean Model-C and diamond explanations remain visible; detailed semantics
and technical CONTROL/K-P0/E1/case/schedule/fingerprint provenance are retained in
tooltips/accessibility. Archived actions/statuses and `Index` / `Model C Time`
controller tokens are unchanged. The comparison launcher calls `showMaximized()`;
scroll fallback and 28 px cells remain.

## 10. Final D5 source/package qualification

At preflight and final preservation, `main`, HEAD and local `origin/main` were
`fb59d5fa253f04f50ea57c6a9e863aa1999a517e`, ahead/behind 0/0 and clean.
The final fresh root is
`results/program-k-trace-demo-final-acceptance/20261031-230251/`.

Environment: Windows 11 `10.0.26200` AMD64, Python 3.12.10, PyInstaller 6.22.3,
PyQt 5.15.11, Qt compiled/runtime 5.15.2, SIP runtime 6.16.0 / PyQt5-sip 12.19.0.
Approved Python was `C:\venvs\minesweeper\Scripts\python.exe -B`, with
`PYTHONDONTWRITEBYTECODE=1`. Build tools were isolated in that fresh ignored root.

Build: **Windows x64 / onedir / windowed**, exit 0, **48.953 s**. The build-only
wrapper imports the committed comparison demo's `main()`; source was not patched.
Exact argv/environment/times are in the
[build record](../../results/program-k-trace-demo-final-acceptance/20261031-230251/evidence/build-result.json).
`Hidden import "sip" not found!` and conditional platform/import-machinery warnings
remain recorded; the required `PyQt5.sip` binary is bundled and native use passed.

The six research modules and required Qt/presentation helpers are present, with
no broad hidden-import rules. Static inclusion of unused V1 code is distinct from
runtime execution. Actual EXE module code matched source after filename-only
normalization. [Semantic equality](../../results/program-k-trace-demo-final-acceptance/20261031-230251/evidence/source-package-semantics.json)
checked all four pairs, labels/provenance, facts/differences, actions and every
committed public/M/flag/route/cursor/cost frame using actual archived code and
bundled data. Native EXE interaction was a separate passing gate.

## 11. Automated verification

These are the fresh final-source D5 results, not tests rerun by this docs refresh.

| Family | PASS | FAIL | ERROR | SKIP |
| --- | ---: | ---: | ---: | ---: |
| [D1 adapter](../../tests/test_program_k_trace_adapter.py) | 27 | 0 | 0 | 0 |
| [D2/D3 viewer](../../tests/test_program_k_trace_viewer.py) | 56 | 0 | 0 | 0 |
| [CONTROL adapter](../../tests/test_program_k_control_trace_adapter.py) | 32 | 0 | 0 | 0 |
| [Pair model](../../tests/test_program_k_trace_comparison.py) | 27 | 0 | 0 | 0 |
| [Comparison UI / R2](../../tests/test_program_k_trace_comparison_ui.py) | 84 | 0 | 0 | 0 |
| Focused total, process-isolated families | **226** | **0** | **0** | **0** |
| Ordinary full source regression | **5,098** | **0** | **0** | **0** |

The project full-source runner selected 5,092 main + 6 isolated tests, with exact
partition/result accounting PASS, process exit 0 and **no excluded tests**.
Elapsed: 3,073.344 s. See
[focused record](../../results/program-k-trace-demo-final-acceptance/20261031-230251/evidence/focused-isolated-regression.json) and
[full record](../../results/program-k-trace-demo-final-acceptance/20261031-230251/evidence/full-source-regression.json).
Ordinary unit-test Engine/solver fixtures were allowed; no new E1/R0/E2, official
100k run or profiling experiment was part of D5.

## 12. Final package identity

Package directory:
`results/program-k-trace-demo-final-acceptance/20261031-230251/dist/ProgramKResearchComparison/`.

[Final executable](../../results/program-k-trace-demo-final-acceptance/20261031-230251/dist/ProgramKResearchComparison/ProgramKResearchComparison.exe):
`ProgramKResearchComparison.exe`, **174 package files**.

EXE SHA-256: `8bdf6113ee2c5c0340d649d6da92137825d66917fe00530aee01e448fa14d669`.

The package starts directly into the Korean comparison UI. It does not require
network, Git, VS Code, the development venv, a source checkout, or the original
external results directory to display the bundled four pairs.

## 13. Runtime data and preservation

Accepted E1 root: `results/program_k_research/e1-20261022T003214Z-fba3da048d46/`.
The onedir package preserves this layout under `_internal`, with the profile in
`_internal/calibration/`. Actual bundled bytes and original bytes matched before
and after package use.

| Runtime file | SHA-256 |
| --- | --- |
| `qualification.json` | `1f2a6ee1801f8ea498d4f8844df80d5b4f8f481752e874c5bff67f2da41da05a` |
| `COMPLETE.json` | `bb6301b2245d5affec9604568b49557100227436946b0934b94d972d53a7e544` |
| `calibration/stage3_physical_profile_v1.json` | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` |

Native use from `C:\Windows` with development Python/Qt environment cleared passed
startup, four-case interaction and normal close (exit 0). The external qualification
process observer saw **zero descendants**; no application-owned algorithm job was
created. File observation saw **zero write/sidecar events** on package/original
evidence paths. Final hashes preserved all 174 package files and all 2,039 files
in the historical acceptance/review roots. See
[native checks](../../results/program-k-trace-demo-final-acceptance/20261031-230251/evidence/native-checks.json) and
[preservation record](../../results/program-k-trace-demo-final-acceptance/20261031-230251/evidence/final-preservation.json).

## 14. Final user native packaged acceptance

The project user reported **A–H PASS for this final packaged binary**, after the
automated record was written. This closes the former user-acceptance hold.

| Item | Accepted observation |
| --- | --- |
| A | Startup / maximized Korean exhibition surface |
| B | Four-case switching |
| C | Independent CONTROL/K navigation |
| D | K logical diamond versus physical FLAG |
| E | Independent playback, modes and rates |
| F | S-LOSS “비교하지 않음” semantics |
| G | Expert readability and scroll fallback |
| H | Clean close |

Current observed machine: **1920×1080, 96 DPI / 100%**. Both 30×16 boards fit
horizontally at maximized startup with **28 px cells**; restored/smaller windows
retain independent scroll fallback. Diamond, FLAG, route, target and cursor are
distinguishable. This is not a universal DPI compatibility claim.

## 15. Historical native/harness anomaly

The earlier custom-combined focused run at the historical qualification produced
**83 successful test outputs**, then terminated with Windows **0xC0000374**.
The root cause is unresolved. It was **not counted as PASS**. Its
[original log](../../results/program-k-trace-demo-final-acceptance/20261031-175417/logs/focused-regression.log)
and failure record remain unchanged. Subsequent process-isolated focused tests,
ordinary full regression and native package qualification passed. Those later
passes do not manufacture a causal explanation or erase the historical failure;
without new evidence it is not a current closeout blocker.

## 16. Production and Gate-P boundary

D0's separate research/demo authorization does not reinterpret the historical
Gate-R scope as GUI/production permission. The accepted path is a standalone
read-only evidence viewer, not a normal application algorithm selector or a new
execution surface. Production modules must not import Program-K experimental
modules. Research presentation may reuse stable production presentation helpers.

No frozen specification, Stage-3 V1 semantics, production Same-board schema,
algorithm policy, benchmark identity or effectiveness threshold is weakened.
Production integration remains NOT STARTED; Gate P is not passed. K-CONTROL,
Human/S2/K universal comparison, proof panels and new solver execution are outside
this accepted surface.

## 17. Final verdict

**PROGRAM K RESEARCH TRACE VISUALIZATION / COMPARISON — FINAL ACCEPTANCE PASS / CLOSED**

**BLOCKER 0 / REQUIRED 0 / OPTIONAL 0 at the D0–D5 acceptance boundary.**
Automated D5 PASS plus the later user's final packaged A–H PASS close this demo
subpath only. Program K effectiveness remains NOT ESTABLISHED.

## 18. Next project step

**Stage-3 Extended: ACTIVE pending explicit project-closeout adjudication.**
Milestones 1–9 are CLOSED; the Program K exhibition/demo subpath is CLOSED;
effectiveness research is DEFERRED / unresolved.

**NEXT: explicit Stage-3 Extended project-closeout adjudication / Stage 4 transition.**
That decision must determine whether the completed project scope is sufficient.
This document does not declare Extended globally closed or start Stage 4.
Reopening effectiveness work requires new evidence and separate bounded
authorization; do not resume the stopped timing path or R0-B/E2 merely for reassurance.
Current recovery starts at [CURRENT_HANDOFF](../CURRENT_HANDOFF.md), then the
[Extended roadmap](README.md) and the source/tests/evidence for disputed facts.
