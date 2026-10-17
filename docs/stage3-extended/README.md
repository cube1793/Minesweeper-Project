# Stage 3 Extended

## Status

Stage-3 V1은 **FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED**이며 frozen baseline이다.
ZiNi Improvement도 **CLOSED / V1 RETAINED**이고 미개봉 최종 holdout은 그대로 유지한다.
**Stage-3 Extended는 ACTIVE**다. 이 문서는 의존 관계에 따른 roadmap이며 고정 구현 일정이 아니다.

**Representative-board Demonstrations / Timeline Analytics — FINAL ACCEPTANCE
PASS / CLOSED** (2026-10-17). **Slices 0–4 COMPLETE / ACCEPTED**, internal 3A/3B 포함;
**BLOCKER 0 / REQUIRED 0**. Qualified source candidate는
`4c488e033dd045f1c203ff500d824cfaffb7cc67`이며 이후 documentation-only commit과 구분한다.
Focused/frozen **386 PASS**, full source **2184 PASS**, failures/errors/skips 모두 0.
[최종 closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)과
[수용 계약](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md)을 보존한다.
**CURRENT — Selected Exemplar Board-State Reconstruction / Human Interpretation
Viewer: ACTIVE, Slices 0–3 FINAL PASS — COMPLETE / ACCEPTED by ChatGPT final review**
(2026-10-18). 각 slice **BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
[Viewer 계약](STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md)의 discovery는 ChatGPT
**PASS / BLOCKER 0 / REQUIRED 0**로 수용했다. **CURRENT / AUTHORIZED — Slice 4:
Acceptance / Closeout**.
Independent pre-closeout audit is complete and the required production
correction has been accepted. Final Slice-4 acceptance gates remain pending.
Viewer는 고정 exemplar의 human/domain
해석을 지원하며, 첫 실제 Extended 알고리즘 연구 방향의 선택·명세와 연구/구현 승인은
별도의 명시적 scope/specification 결정이다.

첫 milestone **Execution / Playback / Visualizer Foundation**은
**FINAL ADJUDICATION PASS / CLOSED (2026-10-14)**다.
자동 검증과 실제 Windows worker/profile/startup, 사용자의 packaged interactive
acceptance, 독립 Claude 감사 및 ChatGPT 최종 판정이 모두 PASS다.
[최종 판정](STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)에 종료 범위와 F-1/F-2 처분을 기록했다. [Slice 5 수용 기록](STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)에
수동 tester/date, 네 terminal path의 PID·job-directory cleanup 및 controls PASS를 기록했다.
Foundation 판정은 해당 milestone만 닫으며 Stage-3 Extended 전체는 계속 active다.

## Foundation — closed / integrated

- Execution integration audit: 구현에 반영되어 완료.
- Slice 1 — Execution Context + Pure Trace Playback (`cf7544b`).
- Slice 2 — Subprocess Execution Worker (`d100a49`).
- Slice 3 — Read-only Stage-3 Visualizer Window (`490a8cf`).
- Slice 4 — Application Integration + Process Lifecycle (`b9af830`; pre-Slice-5 baseline).
- Slice 5 — Acceptance / Packaging / Documentation Closeout (`18964ad`): **CLOSED**, committed/merged/pushed.

Full commit identities and the dated Git baselines are in the acceptance and final
adjudication records. `18964add02c508d67429ef29cb59ce879c01017d` is the Slice 5
documentation closeout / independent-audit baseline, not a permanent latest HEAD.
Current components are `Stage3Execution`, worker, parent-owned `Stage3ExecutionJob`,
launcher, pure `Stage3TracePlayer` / `Stage3ModeledPlayback` and execution-only viewer. Indexed
`EXPERT_GENERAL_V1` execution is independent of the current Live/Replay board.

## Foundation final adjudication — CLOSED

Historical 2026-10-14 Foundation acceptance and user-performed packaged manual acceptance are complete.
Normal success, Cancel, launcher-close and main-close during active jobs passed,
with each owned worker gone and job directory removed. Parent PID 5352 also exited
on main close. Playback, responsiveness and retained-result reopen passed.
The Foundation documentation closeout changed no production Python, profile or playback-seek behavior.
Source tests: **1628 passed, 0 failures/errors/skips** in the development environment.
The independent audit also passed: focused **122**, frozen protection **92**,
Stage-2 / ZiNi / Replay / Stage-3 benchmark boundary **86**, full suite **1628**
with **0 failures/errors/skips**, and packaged-worker deterministic equivalence.
ChatGPT final adjudication: **BLOCKER 0 / REQUIRED production 0**.
F-1 is the required documentation-only historical/current-state correction,
addressed by this closeout; it is not an implementation blocker.
F-2 remains **OPTIONAL / DEFER** for future worker/release transport hardening.
That Foundation closeout published no release/tag.

## Version / Settings Identity Separation — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**.
[Closeout evidence](STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md) records the live
implementation baseline, 376 focused / 1639 full tests (zero failures/errors/skips),
fresh Windows package/profile/worker equivalence and user-performed native GUI PASS.

- Public Fixed Identities (`858dc1a`): immutable fixed V1 algorithm identity,
  physical-owner identity descriptor and unchanged benchmark snapshot consumers.
- Identity-backed Visualizer Labels (`e04d4e8`): separate Algorithm / Physical
  labels and a current `Playback: Index · N ms/step (presentation)` label.

| Identity | Current ownership / meaning |
| --- | --- |
| Application/release | Release/tag/build documentation; no runtime version constant, and current main is not historical v0.2.0 |
| Stage-3 algorithm | `stage3_identity.STAGE3_V1_IDENTITY`; distinct from telemetry semantic version and execution configuration |
| Physical model/profile/table | `stage3_physical.MODEL_C_V1_IDENTITY` and substantive authentication; `Model C` alias is separate |
| Playback/presentation | Viewer-local Index/Modeled-Time; Index 20..5000 ms, default 200 ms; modeled default 1×; no QSettings or presentation version |

`Stage3Execution(spec, board, result)`, worker transport and all frozen semantics
remain unchanged. No migration, algorithm/profile selectors, registry or new runtime app version.

## Modeled-Time Playback / Synthetic Smooth Cursor Presentation — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**.
[Closeout evidence](STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md) records Slice 1–3 commits,
254 focused / 1699 full tests with zero failures/errors/skips, a fresh package,
frozen profile equality, packaged worker equivalence and the project user's
native packaged GUI report **"A–K passed"**.

- TracePlayer uses failure-atomic incremental `next()`; arbitrary seek and previous
  retain reconstruction from index 0.
- The Qt-independent controller owns exact partial modeled time, monotonic anchoring,
  pause/resume, speed and multi-action catch-up using recorded durations.
- Index remains default, 20..5000 ms/step, default 200. Modeled-Time uses
  0.25× / 0.5× / 1× / 2× / 4× / 8×, default 1×, without persistence.
- The UI requests frames every 16 ms; the controller clock is authoritative.
  Partial frames update only the overlay; catch-up refreshes the board once.
- Straight smoothstep `q = u²(3 - 2u)` uses rendered cell centers. Same-cell actions
  stay stationary; no separate dwell model. Actions commit at modeled boundaries.
  Pause preserves partial progress; manual navigation and mode changes cancel it.

The synthetic cursor is presentation, not an actual OS trajectory or physical
acceleration model. Rates/easing never alter recorded costs, Model C or planner input.

## Human Mouse Trace / Path Visualization — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-16)**.
[Closeout evidence](STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md) records qualified
implementation/package SHA `e32145fa5c114e1ce500ad2e837ef6000cc49cca`,
**627 focused / 1825 full source PASS**, fresh-environment **1800 PASS / 25 optional
skips**, packaged workers/native GUI/Replay v2 verification and final user native PASS.

- Actual Live-board event samples use board-local Qt logical pixels, exact subpixel
  positions and an independent monotonic trace clock. No timer sampling,
  min-distance filtering or semantic point dropping; continuity breaks form segments.
- Recording defaults ON per application/session and locks at the first committed
  timed human OPEN/FLAG. OPEN observes L release; FLAG observes R press.
  Untimed pre-start CHORD does not start trace. Recording OFF at the lock point,
  an actual Auto action or Replay append failure after a committed human action
  invalidates the Human trace.
- Action markers reference actual ReplayEvent indices. Replay v2 carries the
  separate trace attachment; v1 remains readable and trace-free. Display is optional.
- Physical gesture fidelity includes independent Mode-A/C R-press FLAG and
  origin-independent Mode-B BOTH, first-release CHORD at the current target,
  repeated overlaps and FLAGGED-center neighborhood preview.
- Primitive recorder storage, pre-start gating, transformed-geometry caching and
  a **16 MiB** bounded raster cache/fallback preserve exact samples. User testing
  accepted trace ON after hardening and found no noticeable final-package regression;
  this is not a zero-overhead claim.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human trace is pointer presentation data, not OS-global tracking, synthetic Stage-3
motion, Model C calibration evidence or solver input. Frozen V1 and official 100k
results retain their original identity and meaning.

## Roadmap

1. **CLOSED** — Execution / Playback / Visualizer Foundation.
2. **CLOSED** — Version / Settings Identity Separation.
3. **CLOSED** — Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **CLOSED** — Human Mouse Trace / Path Visualization.
5. **CLOSED** — Same-board Human / Stage-2 / Stage-3 Comparison (Slices 0–5 COMPLETE / ACCEPTED).
6. **CLOSED** — Representative-board Demonstrations / Timeline Analytics;
   Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 1 — Pure timeline analytics COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE / ACCEPTED.
   Internal Slice 3A — accepted-evidence opening correction / preflight COMPLETE / ACCEPTED.
   Internal Slice 3B — selection / selected-action report COMPLETE / ACCEPTED.
   Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED.
7. **ACTIVE — interpretation support** — Selected Exemplar Board-State Reconstruction /
   Human Interpretation Viewer; **Slices 0–3 COMPLETE / ACCEPTED by ChatGPT final review;
   each BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**. **Slice 4 CURRENT / AUTHORIZED —
   Acceptance / Closeout**; independent audit complete, R-1 ACCEPTED, final gates pending.
   Human/domain interpretation of
   fixed exemplars supports a later choice/specification of the first actual Extended
   algorithm research direction; research/implementation requires separate approval.

For later algorithm research, nearest exact-minimum-risk guess selection among equal-risk
candidates using movement cost remains a candidate, not an adopted policy or
authorization to modify V1. External screen-recording tools remain the default.

## Selected Exemplar Board-State Viewer — CURRENT / Slice 4

The [consolidated contract](STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md) is **Slice 0
COMPLETE / ACCEPTED by ChatGPT final review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
Its unchanged accepted scope freezes admission to
**73758, 73024, 93557 and 1**, preserving closed Timeline memberships. No selection,
ranking, substitution, arbitrary-ID browsing or algorithm research is authorized.
Live Git verified on 2026-10-18 (Asia/Seoul), before this documentation refresh:
branch `feature/stage3-exemplar-board-viewer`, HEAD
`2c9ba42fb394ee528a035a85c3a2c8146b86a7f9` — `fix: prevent exemplar viewer focus-loss navigation`.
The worktree was clean, nothing staged, and HEAD matched the local
`origin/feature/stage3-exemplar-board-viewer` ref (ahead 0 / behind 0);
no remote fetch was performed. Main baseline remains
`50a8fee544ed6779dbcd7dd2fbb422c07cce59de`.
This correction commit is the current live implementation candidate, **not a
final qualified SHA**. Qualification requires final Slice-4 verification at the
chosen committed SHA. Live Git overrides these dated recovery facts.

Independent Claude read-only audit of `d338dcffa212e52efb23af9d9db41841348ade96`:
**CONDITIONAL / BLOCKER 0 / REQUIRED 2**. **R-1 SATISFIED** by the current correction;
ChatGPT final correction review PASS / ACCEPTED. Focus loss/Tab no longer navigate;
initial and BEFORE positions survive. Return/Enter commits exactly once and Go
uses the same helpers; `_Position` remains authoritative.
Reported correction verification: **45 viewer UI module + 32 reconstruction +
34 evidence-loader = 111 PASS; 0 failures / 0 errors / 0 skips**; no full-suite claim.
Only `exemplar_board_viewer_ui.py` and `tests/test_exemplar_board_viewer_ui.py`
changed for the correction. **No REQUIRED production correction remains.**

**R-2 OPEN — closeout provenance**, not a production defect: identify the final
qualified committed SHA and perform final verification at that SHA. Earlier
precommit Slice-3 evidence below remains historical accepted slice evidence,
not retroactively commit-qualified final acceptance.
**O-1/O-2/O-6 SATISFIED; O-3/O-4 DEFER; O-5 DEFER TO CLOSEOUT** (Model C seconds
= exact microseconds / 1_000_000 in the final record); **O-7/O-8 NO CHANGE**.
No Claude re-audit after R-1 is required or claimed.
**Final Slice-4 acceptance gates have not yet been run.**

**Slice 1 — Qt-independent Pure Reconstruction COMPLETE / ACCEPTED by ChatGPT final
review; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.** Accepted files:
[`exemplar_board_reconstruction.py`](../../exemplar_board_reconstruction.py) and
[`tests/test_exemplar_board_reconstruction.py`](../../tests/test_exemplar_board_reconstruction.py).
Reported verification: **32 new focused reconstruction + 28 timeline analytics +
27 Engine regression + 4 board analyzer + 9 Replay player = 100 PASS**;
**0 failures / 0 errors / 0 skips**. No full suite is claimed; this documentation
transition does not rerun tests.

The accepted layer consumes an already-finalized `BoardSnapshot` and already-validated
`TimelineAnalytics`; returns immutable N+1 public frames and exact new-safe sets;
preserves terminal feedback and separates explicit FLAG from automatic effects.
Static 3BV/Ops/isolated references and final public Engine counter summary remain
separate; original `TimelineAnalytics` retains Model C / geometry / metadata
authority, with no Engine retained. Bounded synthetic Slice-1 fixtures used no DB,
official exemplar inputs, benchmark-board generation, Qt/UI, ZiNi, solver/planner
or algorithm research.

**Slice 2 — Accepted-Evidence Loader COMPLETE / ACCEPTED by ChatGPT final review;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.** Accepted files:
[`exemplar_board_evidence.py`](../../exemplar_board_evidence.py) and
[`tests/test_exemplar_board_evidence.py`](../../tests/test_exemplar_board_evidence.py).
Reported verification: **34 new focused evidence-loader tests + 173 bounded
existing regressions = 207 PASS; 0 failures / 0 errors / 0 skips**. No full-suite
claim; no verification is rerun by this documentation transition.

The accepted boundary authenticates the exact two DB sources, owns immutable
read-only connections and admits exactly one accepted run per role. Fixed-four
admission, selected-only GameRecord/ActionEvent decoding and explicit enum mappings
preserve Fraction/None/zero exactly. Admitted-board generation requires
generated/persisted/fixed fingerprint equality. Authenticated frozen Model C,
existing `project_timeline()` and accepted Slice-1 `reconstruct_board()` produce
an immutable bundle with no live DB connection or Engine. No G4/HTML runtime input,
selection/ranking/arbitrary browsing, Qt/UI, ZiNi, solver/planner or algorithm research.

Accepted bounded real-evidence smoke: exact accepted DB hashes authenticated,
exact accepted runs discovered, requested/processed/stored **100000 / 100000 /
100000** per source and exact official coverage PASS. Exactly **four boards**
generated, **eight selected streams** loaded/projected/reconstructed, all fixed
fingerprints and accepted action/outcome/Model-C totals matched. All **1,508
persisted actions** reconciled with **0 status / 0 safe-reveal / 0 explicit-FLAG
mismatches**. Source hashes/sizes/mtimes were unchanged after close; no sidecars
or output artifacts; no solver/planner, selection, G4 or report rerun. This is
accepted Slice-2 implementation evidence, **not final viewer closeout**.

**Slice 3 — Standalone Inspection UI COMPLETE / ACCEPTED by ChatGPT final review;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.** Accepted files:
[`exemplar_board_viewer_ui.py`](../../exemplar_board_viewer_ui.py),
[`scripts/exemplar_board_viewer.py`](../../scripts/exemplar_board_viewer.py) and
[`tests/test_exemplar_board_viewer_ui.py`](../../tests/test_exemplar_board_viewer_ui.py).
Reported verification: **33 viewer UI + 4 launcher + 34 accepted evidence-loader +
32 accepted reconstruction + 6 selected Stage-3 visualizer rendering + 5 selected
ZiNi Explorer rendering + 2 adapted unchanged Same-board navigation assertions =
116 PASS; 0 failures / 0 errors / 0 skips**. Same-board assertions ran unchanged
with hand-recorded synthetic setup replacing solver-producing setup. No full-suite
claim; no verification is rerun by this documentation transition.

Accepted bounded real-evidence offscreen smoke: exact accepted Stage-2 / Stage-3
sources loaded through the Slice-2 API; **2 DB opens during initial load only,
4 board generations, 8 selected-action streams, 8 timeline projections and
8 reconstructions**. All eight game/solver pairs were inspected at initial,
middle and final states; Before/After, Answer Overlay ON/OFF, first-action
presentation and LOSS terminal rendering were exercised. Same-target and
long-transition presentation were checked where present. After initial load,
navigation/selection/toggles caused **0 DB opens / 0 board generations / 0 Engine
reconstructions / 0 timeline projections / 0 solver/planner/selection calls**.
Source hashes/sizes/mtimes were unchanged; no sidecars or output artifacts.
This is accepted Slice-3 evidence, **not final native/manual acceptance**.

Accepted UI boundary: standalone Qt viewer and explicit accepted-loader-based
launcher; one board, four fixed exemplars, Stage-2/Stage-3 selector and eight
independently remembered positions; First/Previous/Next/Last, integer frame slider,
direct frame/action entry and Before/After. Default-OFF HIDDEN-only Answer Overlay,
exact terminal Engine feedback, new-safe AFTER-only highlights and recorded
previous/current targets remain separate; no fabricated first-action origin path.
All 17 classic Counters rows remain, historical Time/Est Time/3BV/s/CPS are
unavailable, and Efficiency/IOE/Thrp/Corr use accepted final facts. **ZiNi/ZNE/ZNT
rows remain; calculation is explicitly DEFERRED** because no narrow public
reusable job owner exists. Only immediate reference numbers are omitted; no
private main-UI lifecycle is duplicated. Model C and exact persisted Action
Context have separate groups. No DB/Engine/reconstruction during navigation,
autoplay/timer/modeled animation, shared/common playhead, normalized progress,
solver/planner/selection/ranking, algorithm research or main-app integration.

Required future inputs are the two exact accepted analysis DBs, tracked fixed
exemplar identities and authenticated frozen Model C. G4/HTML remain historical
provenance; they are not required viewer runtime inputs. Authenticate generated
layout fingerprints against both sources before replaying persisted actions.

One board, game/solver selectors and independent remembered indices inspect
immutable before/after public frames. Public View keeps **Terminal Engine feedback**;
**Show hidden answers — reference overlay** defaults OFF and decorates only HIDDEN
cells at about 0.35 opacity. No fake Replay/native traces, solver/planner calls,
shared clock, normalized progress, Human overlay, autoplay or modeled animation.

The accepted consolidated contract keeps five separate factual areas: **Board / Solver
Reference; Classic Counters / Final Run Summary; Model C; Action Context; Board
Presentation**. Static total 3BV/Ops/isolated count are answer-derived board
references. Final reconstructed counters use current Engine public APIs and
mechanical definitions, not historical telemetry or strategic judgments. All 17
classic rows remain; historical Time/Est Time/3BV/s/CPS remain unavailable.
Raw total active/wasted/completed 3BV and final formatted per-button/3BV/Ops values
have public seams; extra raw breakdown requirements must be reported separately.

Stage-2 OPEN/FLAG-only HIDDEN-target policy is explicitly labeled: CHORD=0 is an
action-space boundary, not a choice to reject CHORD. Exact current Efficiency/IOE/
Thrp/Corr formulas remain. ZiNi is the existing bounded best-so-far answer-derived
efficiency reference, available on WON/LOST when calculated; ZNE/ZNT are WON-only.
Its optional reference/UI calculation is outside Slice-1 reconstruction/navigation
and is explicitly deferred in the accepted Slice-3 implementation.

Selected/cumulative/final Model C time and Modeled 3BV/s/CPS use the authenticated
integer table, not replay runtime or refitted coefficients. V1 has no action-type
cost dimension; both displayed streams are post-hoc evaluations. A selected
target-transition arrow and exact dx/dy/d² expose geometry, not recorded cursor
trajectory. Human experts interpret strategy, routes or apparent external-video
speed; the viewer produces no automatic quality or ZiNi-as-speed-winner verdict.

Accepted discovery: four exact regenerated fingerprints; eight streams / **1508
actions**; **0 status / 0 safe-reveal / 0 explicit-FLAG mismatches**, terminal at the
final persisted event, no solver/planner/runner calls, official artifacts unchanged.
This is feasibility evidence, not implementation acceptance. Slice 0 is documentation
only and does not repeat DB reads or board generation.

Slices: **0 Contract → 1 Pure reconstruction → 2 Accepted-evidence loader →
3 Standalone inspection UI → 4 Acceptance / Closeout**. **Slices 0–3 COMPLETE / ACCEPTED**.
**NEXT / CURRENT / AUTHORIZED — Slice 4: Acceptance / Closeout**;
Independent pre-closeout audit is complete and the required production
correction has been accepted. Final Slice-4 acceptance gates remain pending.
Slices 0–3 technical semantics remain frozen. Remaining Slice-4 gates are
focused/frozen verification, final source/full regression, bounded real four-case
proof, source preservation checks, bounded native/manual presentation inspection,
R-2 provenance and final closeout documentation/adjudication. This refresh runs
none of those gates and adds no viewer features; the milestone remains ACTIVE.
No direct DB reads outside the loader or regeneration/reconstruction on navigation;
no solver/planner or selection/ranking rerun, arbitrary browsing, shared/common
playhead, normalized progress, synchronized side-by-side, autoplay or modeled-time
animation. Do not fabricate historical elapsed time or cursor trajectory/speed,
make automatic route/quality/causal judgments, alter frozen Model C/V1 or perform
algorithm research.
Frozen V1/Model C, closed Timeline/Same-board/ZiNi, both Timeline
reports, official 100k and unopened ZiNi holdout remain preserved.

## Representative-board Demonstrations / Timeline Analytics — CLOSED

**Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review
(2026-10-17, Asia/Seoul).** Read-only discovery received ChatGPT **DISCOVERY PASS**.
The [accepted contract](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md) records the scope.
**Slice 1 — Pure timeline analytics COMPLETE / ACCEPTED by ChatGPT final review.**
Slice-1 adjudication: **SLICE 1 PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT
final review.** Final Slice-2 adjudication:
**SLICE 2 PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE /
ACCEPTED as a whole. Internal Slice 3A — accepted-evidence opening correction / preflight
COMPLETE / ACCEPTED by ChatGPT final review.** Final adjudication:
**SLICE 3A CORRECTION / PREFLIGHT PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Internal Slice 3B COMPLETE / ACCEPTED: STAGE-3 EXTENDED TIMELINE ANALYTICS —
SLICE 3B FINAL PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 5.**
**Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED. FINAL ACCEPTANCE PASS /
CLOSED; BLOCKER 0 / REQUIRED 0.** Stage-3 Extended remains ACTIVE. The
[final closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) records the qualified
candidate `4c488e033dd045f1c203ff500d824cfaffb7cc67` and final evidence.

Accepted Slice-1 implementation: [`timeline_analytics.py`](../../timeline_analytics.py)
and [`tests/test_timeline_analytics.py`](../../tests/test_timeline_analytics.py).
Verification: **28 focused PASS; 257 bounded existing regressions PASS**.
Four existing solver/Engine execution cases were intentionally excluded from
that bounded regression set; **no full suite is claimed**. The projection and
focused tests used in-memory synthetic facts with no DB access; existing
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
preserved artifacts. `immutable=True` asserts that the source will not change
during the connection lifetime; it is not for live sources.
Verification: **67 complete telemetry-repository PASS; 238 bounded relevant
regressions PASS; total 305 PASS**. Four existing solver/Engine execution tests
were intentionally excluded; **no full suite is claimed**.

During internal Slice 3A, the exact four official artifact hashes were
reauthenticated. Fresh Stage-2 and Stage-3 run identity/coverage checks **PASS**;
both runs are official-eligible exact
`EXPERT_GENERAL_V1 [0,100000)`. Model C authentication and **100,000 paired-prefix
identity validation PASS**. Independent outcomes reconcile:
**WW 37,702 / WL 0 / LW 0 / LL 62,298**. The independently derived WW index set
exactly equals the authenticated G4 paired-delta index set: **37,702; missing 0;
extra 0**. Official artifact bytes/timestamps remained unchanged; no new sidecars
remained. No solver, Engine, board generator, official benchmark rerun, detailed
selected-action loading, report/chart generation, Human data or ZiNi holdout was
used. No actual official exemplar ID was selected or disclosed during Slice 3A.

Accepted Slice-3B implementation:
[`scripts/stage3_timeline_report.py`](../../scripts/stage3_timeline_report.py) and
[`tests/test_stage3_timeline_report.py`](../../tests/test_stage3_timeline_report.py).
Final R-1 verification: **34 report + 29 representative selector + 28 timeline
analytics + 67 telemetry repository = 158 focused PASS; 174 bounded regressions
PASS; reported total 332 PASS**. Four solver/Engine execution tests were
intentionally excluded; **no full-suite claim was made at Slice 3B**.

Independent Claude Code read-only audit inspected the actual pre-correction
report, independently authenticated/recomputed selection, and reproduced all
**1,508 action rows and 16 SVGs with 0 mismatch**. Claude reported **BLOCKER 0 /
REQUIRED 0** and OPTIONAL O-1..O-6. ChatGPT promoted O-1 to REQUIRED R-1 for report
provenance/semantic wording; corrected R-1 is accepted and **O-1 SATISFIED**.
**O-2 DEFER** (chart common scale), **O-3 NONBLOCKING** (parse-hashed-bytes TOCTOU),
**O-4 DEFER** (selected-action SQL tests), **O-5 DEFER** (synthetic failure branches),
**O-6 DEFER / NONBLOCKING** (extended run/git/config provenance). Current identity
is sufficient; added convenience/detail does not justify regenerating the report.
No Claude re-audit after R-1 is claimed or required; its wording-only correction
was subsequently source/test/report verified by ChatGPT/Codex.

Fixed category exemplars: maximum Stage-3 WW advantage **73758 / -27009085 us**;
median-delta WW **73024 / -16487355 us**, lower-median zero-based rank **18850 of
37702 WW**; closest-to-zero Stage-3 WW advantage **93557 / -7877513 us**;
Stage-2 WW advantage, exact WW tie, WL and LW **EMPTY**; LL **game 1**.
Unique selected games: **1, 73024, 73758, 93557**; no visual/manual substitution.
Exact selected action counts, modeled totals and G4 reconciliation are in the
[accepted Slice-3B evidence record](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md#accepted-slice-3b-implementation-and-evidence).

Final corrected report:
`results/stage3-timeline-analytics/20261017T113748060625Z-99dafa139703/report.html`,
**470817 bytes**, SHA-256
`b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3`.
Corrected script SHA-256:
`50f9d88e80b971596de59eadae1bb3bf96ee0d4da88d252684a7cbf0a15eb387`.
Preserve the earlier
`results/stage3-timeline-analytics/20261017T103913620889Z-54082dd14870/report.html`
as historical pre-final 3B evidence. Both reports are ignored local evidence;
do not overwrite/delete either or rerun/replace selection.

Accepted R-1 semantics: both displayed timelines evaluate persisted actions
post-hoc under authenticated Model C. Stage 2 had no native Model C declaration;
Stage-3 collection declared Model C and checked its native total, but persisted
report events retain no native per-action cost/cursor fields. Compute scopes are
Stage-2 analysis versus Stage-3 analysis plus planning, with no cross-stage
compute-speed winner. Stage-2 guess candidate count is exact-minimum-risk tie
multiplicity / final selector pool; official Stage-3 count remains unavailable.
Missing native cursor/action-cost fields, Replay timestamps, full probability
coordinate maps and chosen plans are not fabricated. Official artifacts remained
unchanged with no new sidecars. No solver, Engine, board generation, official
100k rerun, Human data or ZiNi holdout was used.

The first implementation uses only exact accepted official Stage-2 / Stage-3
benchmark artifacts. All four accepted DB/G4 artifact hashes must be verified
before real-evidence report acceptance. Fixed selection rules identify
**deterministically selected category exemplars**, not a statistically
representative sample (the roadmap term 대표 보드 retains this limitation).
Rules must be accepted before selecting IDs; no replacement for visual variety.

Each solver's horizontal coordinate is its own completed semantic action count:
origin 0, persisted `action_index i` maps to `i + 1`. Equal counts do not imply
equal progress. Frozen Model C supplies a common measurement scale, not a shared
execution clock. Compute timings remain separate diagnostics; paired speed
interpretation is WW-only, while LOSS cost is cost through termination.

The accepted pure `timeline_analytics.py` and `representative_boards.py` implement
the Slice-1 and Slice-2 boundaries. The thin read-only evidence/report entry point
`scripts/stage3_timeline_report.py` is implemented and accepted in Slice 3B.
The report includes independent
tables and bounded static timelines,
with output in a new ignored `results/` location. No production Qt UI or new
plotting dependency merely for convenience. Human/native-decision adapters and
interactive GUI are deferred; no algorithm, Model C, schema or telemetry changes.
Official 100k artifacts remain unchanged; the unopened ZiNi holdout remains unused.

Slices: **0 Contract → 1 Pure timeline analytics → 2 Pure deterministic exemplar
selection → 3 Read-only accepted-evidence report / static visualization →
4 Acceptance / closeout**. **Slices 0–4 COMPLETE / ACCEPTED**. Internal 3A/3B
subdivide Slice 3, not the roadmap. Final Slice-4 verification used
`C:\venvs\minesweeper\Scripts\python.exe` (Python 3.12.10, 64-bit AMD64):
**386 discovered / 386 PASS** focused/frozen, 6.198 s unittest / 6.935 s process;
**2184 discovered / 2184 PASS** full source, 141.186 s unittest / 144.019 s process;
**zero failures/errors/skips** in both. Official artifact/model identities,
source/report reconciliation and final document/report inspection PASS. Ordinary
unit tests included Engine/solver execution; no official evidence rerun occurred.
Ignored local evidence: `results/stage3-timeline-analytics-closeout/20261017T131224859Z/`.
No fresh package/build/native GUI gate was required or run because no production
GUI/package surface changed. The final report's earlier `c32e34c...` / dirty generation
state is accepted: its script SHA matches the exact committed `4c488e...` script.
See the [closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) for commands and full identities.
Slice 3A completed exact accepted official Stage-2/Stage-3 DB/G4 authentication and
preflight. **Internal Slice 3B first selected and disclosed actual official exemplar
IDs**, using only the already-accepted deterministic
rules. No visual/manual substitution is allowed after selection.
**Read-only/report output only:** do not rerun the official 100k or any solver,
and do not modify frozen official evidence. The implementation
feature branch at acceptance was `feature/stage3-timeline-analytics`. Live Git
remains authoritative for current branch/HEAD and integration state; later
closeout documentation does not replace the qualified implementation identity.

## Same-board Human / Stage-2 / Stage-3 Comparison — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-17, Asia/Seoul).** Slices 0–5 are
COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B. Qualified source/package
candidate: `a59d0d963bdf1544a03968163b884342e2797ee0`. The
[final closeout](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md) records automated and
user packaged native/manual acceptance, chronology and nonblocking dispositions.

**Slice 0 — contract documentation COMPLETE / ACCEPTED.** The accepted
[comparison contract](STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md) governs exact
same-layout execution, first-open qualification, admission, identity, metric
separation and acceptance.

**Slice 1 — Comparison domain and admission COMPLETE / ACCEPTED** by ChatGPT
final review. The pure Qt-independent
[`same_board_comparison.py`](../../same_board_comparison.py) and its
[focused tests](../../tests/test_same_board_comparison.py) preserve the original
Human Replay and separate Mouse Trace attachment. Admission requires both
`source_type == SOURCE_HUMAN` and explicit `declared_full_game_human=True`;
neither metadata, declaration nor successful reconstruction proves exclusively
Human historical provenance. Identity uses exact layout equality and the existing
canonical fingerprint. Full-stream reconstruction rejects incomplete and
post-terminal streams; opening qualification remains factual, without implying
controlled experimental conditions.

Reported Slice 1 verification: **29 focused passed; 202 relevant regression
passed; combined reported total: 231 passed**, zero failures/errors/skips.
No full suite, package or native GUI run was performed for Slice 1.

**Slice 2 — Isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT final review.
**Slice 2A — Pure isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT
final review. [`same_board_runner.py`](../../same_board_runner.py) runs unchanged
Stage 2 (`accept_guesses=True`, `initial_open=(0,0)`, observer traces) and frozen
Stage 3 on separate fresh fixed-layout engines using the exact admitted Human
layout and authenticated Model C. Mined-origin immediate losses remain legitimate;
no regeneration or retry. Native result/Replay/trace authorities remain separate;
the Qt-independent immutable execution result/metric layer retains no live Engine
or fabricated benchmark identity.

Accepted `benchmark_modeled_time.evaluate_ordered_actions()` reuses existing
authenticated validation/cost logic for complete canonical ordered inputs,
including initial and terminal/losing costs, without DB, GameRecord or fabricated
telemetry/benchmark identity. Existing evaluator callers are preserved.
Human Replay elapsed seconds, each solver's Model C microseconds and each solver's
decision-compute nanoseconds remain separate. No Human Model C time, generic speed
field, winner, ratio or Timeline Analytics is added.

Reported Slice 2A verification: **31 new Slice 2A passed; 29 Slice 1 passed;
274 relevant regression passed; combined reported verification: 334 passed**,
zero failures/errors/skips. No full suite, package or native GUI run for Slice 2A.

**Slice 2B — Worker/process integration COMPLETE / ACCEPTED** by ChatGPT final review.
The dedicated PyQt-independent worker receives only a request token and fixed
ReplayBoard; Human Replay/Mouse Trace remain parent-owned. It executes the accepted
solver path once, without regeneration/retry or fabricated LOSS on failure.
`SameBoardExecutionJob` owns one child/private directory, cancellation/escalation,
reaping and cleanup; success attaches evidence to the exact original Human context.
Source/frozen dispatch is separate, with `--same-board-execution-worker` before Qt.
Parent validation rechecks comparison/outcome-bearing facts without recursively
walking nested decision evidence; native evidence remains retained unchanged.
See the [current handoff](../CURRENT_HANDOFF.md#4-current-milestone) for the accepted
lifecycle/validation boundary, corrected audit finding and qualified responsiveness
measurements (not zero GUI-thread blocking or frozen algorithm-performance evidence).

Reported final Slice 2B verification: **84 Slice 2B passed; 31 Slice 2A passed;
29 Slice 1 passed; 374 relevant regressions passed; combined reported verification:
518 passed**, zero failures/errors/skips. No full suite, fresh package or native
GUI acceptance was run for Slice 2B.

Slices 2A/2B remain internal parts of official Slice 2, not new roadmap milestones.

**Slice 3 — Pure playback coordination COMPLETE / ACCEPTED** by ChatGPT final review.
Pure Qt-independent [`same_board_playback.py`](../../same_board_playback.py) retains
three distinct runs (`HUMAN`, `STAGE2`, `STAGE3`): original Human and native Stage-2
Replays use existing `ReplayPlayer`; Stage 3 uses its fixed-layout trace player
without fabricated benchmark identity. Only recorded `trace.move` executes, never
planner evidence or plan suffixes. No solver/planner/worker/Model-C rerun occurs.

Each run retains its own action index/range; switching restores that index without
changing another run. Index 0 is the fixed all-HIDDEN board; n applies exactly n
inputs. Current `status` and final outcome remain separate, including PLAYING at
index 0 then LOST at index 1 for a legitimate first-action solver loss. Sources,
Mouse Trace attachment and metrics remain unchanged. No common timeline, clamping,
index mapping, normalized progress, lockstep, synchronized three-board playback,
generic time/speed/progress authority or universal player/registry was introduced.
Slice 3 includes no Mouse Trace playback/transformation, autoplay, Qt timer,
interpolation or UI. See the [handoff](../CURRENT_HANDOFF.md#4-current-milestone)
for the accepted playback boundary.

Reported Slice 3 verification: **29 focused; 84 Slice 2B; 31 Slice 2A; 29 Slice 1;
139 existing player/Engine/Replay/Mouse Trace/fingerprint regressions; combined
reported verification: 312 passed**, zero failures/errors/skips. No full suite,
package or native GUI run for Slice 3.

**Slice 4 — Read-only comparison UI COMPLETE / ACCEPTED** by ChatGPT final
adjudication, including internal **4A — Read-only Comparison Result Viewer** and
**4B — Launcher + Main UI Integration / Lifecycle**, both **COMPLETE / ACCEPTED**.
4A/4B are parts of official Slice 4, not new roadmap milestones.

4A [`same_board_comparison_ui.py`](../../same_board_comparison_ui.py) consumes one
completed execution, owns one `SameBoardPlayback` and no worker/job/process/timer.
One public-observation-only board, three-run selector, independent remembered
indices and manual First / Previous / Next / Last / selected-run slider preserve
current status versus final outcome. Factual summary/first-open qualification
does not imply controlled conditions. The optional full immutable Human Mouse
Trace is Human-only and independent of index. No autoplay/time coordination.
Metrics stay separate: Human Replay elapsed seconds; Stage-2 and Stage-3 Model C
cost through termination µs; Stage-2 and Stage-3 decision compute ns. No generic
time/speed winner, ranking or ratio; the Stage-3 Visualizer remains separate.

4B [`same_board_comparison_launcher.py`](../../same_board_comparison_launcher.py)
captures one admitted context from either a completed Live game or the entire
retained original Replay, regardless of displayed index, using existing sources.
**Compare as full-game Human Replay…** declares caller intent, not provenance;
Human metadata remains mandatory. No new loader. Later main source changes cannot
retarget the launcher; **Open Comparison…** only raises the existing owner.
It owns one unchanged job and retained result/viewer; Run requires no active token
and an idle job, and normal Run/Cancel do not wait. Solver LOSS is a valid result;
viewer reopen does not rerun execution. Shutdown permanently disables execution,
retains ownership on failure and supports close retry. Job shutdown precedes
viewer close; main close orders Comparison before Stage-3 before remaining
teardown, stopping on Comparison close failure.

Independent Claude Code read-only audit: **BLOCKER 0 / REQUIRED 0 / OPTIONAL 4 /
PASS**; Claude did not execute/rerun tests. ChatGPT independently reviewed
source/tests and accepted without production correction. Final dispositions:
O-1 DEFER/evidence-triggered; O-2 SATISFIED by real packaged-worker lifecycle
acceptance; O-3 NONBLOCKING after 2085/2085 full source PASS; O-4 DEFER (manual
acceptance did not expose wording confusion). See the
[closeout audit record](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md#audit-disposition-and-nonblocking-ux).

Reported Slice 4 verification: **55 new 4B (31 launcher / 24 main UI); 32 4A;
29 Slice 3; 84 Slice 2B; 31 Slice 2A; 29 Slice 1; 370 relevant existing regressions;
combined reported verification: 630 passed**, zero failures/errors/skips.
No full suite, fresh package or native GUI acceptance for Slice 4 is claimed.

**Slice 5 — Acceptance / Packaging / Native Manual Closeout COMPLETE / ACCEPTED.**
Final root: `results/same-board-comparison-final-acceptance/20261017-022243/`.
Source: **916 focused / 2085 full PASS**, zero failures/errors/skips. Fresh-env:
**2085 discovered / 2060 PASS / 25 permitted optional image/video skips**, zero
failures/errors. Fresh onedir/windowed build: **exit 0, 63.789 s**; frozen profile
bytes match. Safe/mined packaged worker results, deterministic source equivalence,
existing dispatches, native startup and seven real packaged-child lifecycle cases
passed. The project user reported **A–L PASS** on that exact package, including a
Human WON / Stage 2 LOST / Stage 3 LOST comparison and full loaded-Replay capture.

The historical `20261017-014937/` root stays **BLOCKED**: nine isolated fixture
errors, corrected only in `tests/test_replay_statistics.py` at `a59d0d9` after
accepted Slice-4 commit `d81caa9`. The final acceptance restarted from the new
clean SHA; raw evidence remains unchanged. Full identity/hashes and manual gates
are in the [closeout](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md).

Standard Comparison slider track page-step behavior is **OPTIONAL / DEFER**;
normal drag/seek is correct. Separate Human recorded trace versus Stage-3
Visualizer synthetic cursor authorities are **KEEP**; Comparison adds no solver
cursor overlay. No general Human-versus-solver speed winner is established.

Stage-3 Extended remains ACTIVE; frozen V1 / Model C remain unchanged.
**Representative-board Demonstrations / Timeline Analytics is FINAL ACCEPTANCE
PASS / CLOSED — Slices 0–4 COMPLETE / ACCEPTED**, including internal 3A/3B.
The [closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) and
[accepted contract](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md) preserve the fixed
exemplars and both report runs. No visual/manual substitution, official
100k/solver rerun or frozen-evidence modification. Final source regression and
source/report/document reconciliation PASS; no GUI/package gate was required.
**CURRENT — viewer Slice 4 Acceptance / Closeout authorized following Slices 0–3
COMPLETE / ACCEPTED; audit complete, R-1 ACCEPTED, final acceptance gates pending**, as recorded
above. Timeline remains CLOSED. Choosing/specifying the first actual Extended
algorithm research direction follows interpretation; algorithm research or
implementation requires a separate explicit scope/specification decision.
The Same-board closeout itself authorizes no analytics implementation, new physical model, Comparison
solver overlay or provenance schema expansion. No Same-board implementation work remains.

Earlier closeouts retain their dated next-milestone statements as historical
records; the roadmap above and [current handoff](../CURRENT_HANDOFF.md) describe
the current state.

## Deferred / evidence-triggered

- Arbitrary-seek checkpoint/cache optimization.
- Modeled-time slider / sub-action scrubbing.
- 120-fps UI target, easing selector and click pulse.
- Persistent Stage-3 presentation settings; settings dataclass until an external consumer exists.
- Runtime application/release display or version constant.
- Selectable algorithms/profiles and durable cross-version Stage3Execution transport.
- Richer physical model / Model C successor or refit.
- Action-specific OPEN / FLAG / CHORD timing and physical CHORD variants.
- CPS / burst / minimum inter-action constraints, anisotropy and human cognitive timing.
- Built-in screen recording unless later justified.
- Known-mine / no-flag execution and richer / longer planning.

Revisit only with evidence and a separate specification/evaluation contract.
Incremental forward is implemented; arbitrary seeks still rebuild from index 0.
Clearer Run/new-execution versus 결과 열기/retained-result labels remain a nonblocking
UX follow-up. Final WON with Step 0/current PLAYING and manual seek stopping autoplay
remain correct. Foundation F-2 stays **OPTIONAL / DEFER**; this closeout supplies no
new evidence to promote that transport-hardening item.

## Boundaries and references

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`. The viewer never supplies solver
decision input. Playback interval is not Model C time, CPU speed or human speed.
V1 official 100k results, algorithm, profile and qualification remain frozen.
Extended is separate scope and does not reopen accepted V1 or closed ZiNi work.

- [V1 final adjudication](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Frozen algorithm](../../STAGE3_ALGORITHM_SPEC_v1.md)
- [Frozen telemetry/benchmark specification](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Historical extension backlog](../../STAGE3_EXTENSION_BACKLOG.md)
- [ZiNi final adjudication](../zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md)
- [Documentation index](../README.md)
- [Current handoff](../CURRENT_HANDOFF.md)

New Extended records belong here. Existing frozen specs, audit/evidence paths,
official 100k artifacts and historical decisions retain their identities and locations.
