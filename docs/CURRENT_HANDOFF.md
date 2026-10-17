# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Recover the current project state safely when a chat is restarted or reaches its maximum length.  
> Updated: 2026-10-18 (Asia/Seoul)

---

## 1. Authority / evidence order

When current state or implementation facts are disputed, use this order:

1. current Git source code
2. current tests
3. executable verification
4. frozen Stage-3 V1 specifications / final adjudication
5. current tracked documentation, including handoff / README / ARCHITECTURE / index
6. prior ChatGPT / Codex / Claude interpretations or remembered summaries

Agreement between multiple AI reviews is not proof by itself.

---

## 2. Current stable baseline

Repository:

`C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project`

Approved development interpreter:

`C:\venvs\minesweeper\Scripts\python.exe`

Timeline Analytics qualified implementation/source candidate, accepted on 2026-10-17:

- `4c488e033dd045f1c203ff500d824cfaffb7cc67` — `feat: add timeline analytics report`
- qualified branch at acceptance: `feature/stage3-timeline-analytics`
- **FINAL ACCEPTANCE PASS / CLOSED; Slices 0–4 COMPLETE / ACCEPTED**
- **386 focused/frozen / 2184 full source PASS**, zero failures/errors/skips
- [Final closeout](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)

This qualified implementation identity remains fixed after any later documentation-only
closeout commit. Live Git is authoritative for current branch/HEAD/integration state.
Stage-3 Extended remains ACTIVE. Current scope is **Selected Exemplar Board-State
Reconstruction / Human Interpretation Viewer — Slices 0–3 COMPLETE / ACCEPTED
by ChatGPT final review; each BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**CURRENT / AUTHORIZED: Slice 4 — Acceptance / Closeout.**
Independent pre-closeout audit is complete and the required production
correction has been accepted. Final Slice-4 acceptance gates remain pending.
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
Previously audited Slice-3 candidate: `d338dcffa212e52efb23af9d9db41841348ade96`;
Claude verdict CONDITIONAL / BLOCKER 0 / REQUIRED 2. R-1 is now SATISFIED at the
current correction commit, with 111 correction tests PASS and no remaining
REQUIRED production correction. R-2 remains the final provenance closeout task.
The viewer supports domain interpretation before separately scoping algorithm research.

Historical Same-board acceptance baseline, verified on 2026-10-17:

- qualified development branch at acceptance: `feature/stage3-same-board-comparison`;
  clean tracked baseline, nothing staged at that verification
- at acceptance, HEAD matched local `origin/feature/stage3-same-board-comparison`:
  `a59d0d963bdf1544a03968163b884342e2797ee0`
- qualified source/package candidate: `test: fix replay statistics UI fixture`
- preceding accepted Slice-4 implementation/docs:
  `d81caa95fc0e181d199fdf4c770873241f0f1eac` — `feat: add same-board comparison UI`
- `a59d0d9` changes only `tests/test_replay_statistics.py`; no production behavior change

The qualified package/source SHA remains the historical acceptance identity.
Read live Git for current branch existence, latest HEAD, remote refs and merge
state; later Git integration does not replace the qualified candidate identity.
Earlier Extended implementation identities remain in their linked closeout records.

Important Stage-3 V1 identities, verified in live Git:

- qualified implementation/evidence commit: `611984133b83be11bcd2105f401ecdddcfd68a15`
- V1 closeout/archive state before Extended workspace: `3e60c6bc41260c094a868841cd7df179d46ad6c1`
- Stage-3 V1 implementation branch was merged into `main` and its job is finished.

On 2026-10-13, the local top-level project root moved from
`C:\Users\User\Desktop\졸프` to `C:\Projects\GraduationProject`.
The internal directory structure was not intentionally changed. Historical
audit/evidence documents retain the paths that were true when produced.

If live Git disagrees with this section, trust live Git and update the handoff
rather than forcing Git back to these values.

---

## 3. Closed milestones

The following are closed baselines, not work-in-progress:

### Stage 1
- playable UI/UX
- Replay save/load/current-game replay
- Replay controls, Index/Time playback, speed controls
- board analysis / 3BV / Ops
- existing ZiNi functionality

### Stage 2
- Simple Algorithm
- exact probability fallback
- runner / replay instrumentation

### Pre-Stage3
- deterministic benchmark-board infrastructure
- telemetry model/schema/repository/statistics
- official 100,000-game Stage-2 baseline
- final architecture/engineering audit

### Stage 3 V1 — CLOSED
- frozen speed-focused algorithm and physical Model C
- telemetry / benchmark integration
- official 100,000-game Stage-3 run and G0–G5 validation
- independent Claude final audit and ChatGPT final adjudication
- closeout / evidence preservation / housekeeping / main merge / remote push

Final technical verdict:

`FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED`

Accepted official result under frozen Model C:

- corpus: `EXPERT_GENERAL_V1`, exact `[0,100000)`
- both-win games: `37,702`
- Stage-3 modeled time-to-win aggregate reduction vs Stage 2: about `30.089144%`
- this is a frozen modeled-time result, not a claim of 30% faster human play or CPU execution.

Do not reopen Stage-3 V1 merely because an Extended design looks cleaner.

### ZiNi Improvement — CLOSED (2026-10-13)

- TYPE S semantics-preserving optimizations accepted.
- Post-hoc Trace backend, transport/controller and ZiNi Explorer UI implemented.
- V2 quality research closed without adoption; **V1 RETAINED**.
- C3 fresh quality: **NO-SIGNAL**; C4 Family A: **NO-GO**.
- Final `EXPERT_GENERAL_V1` holdout, indices 2,010,000..2,010,099 (100 boards),
  remains unopened: not generated/fingerprinted/calculated/inspected for final
  quality adjudication. Development failed before authorization, so it was
  deliberately not consumed.

See [final adjudication](zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md).
The accepted closeout at `aa0b252aa7c1510b313b511729034e5e74062b5b`
recorded **1414/1414 tests PASS** and **final manual GUI smoke PASS**, then
merge/push to `main`.

### Recent maintenance / usability — CLOSED (2026-10-13)

These are concise accepted closeouts. Test counts and desktop smoke results below
come from historical completion records. Current Human Mouse Trace acceptance
is recorded separately below and does not relabel historical smoke as newly run.
Commit identities were read from live Git.

- **ASCII path migration:** moved to the current ASCII root; **1414/1414 PASS**,
  **0 failures / 0 errors / 0 skips**, and post-migration normal-desktop smoke
  **PASS**, including Replay. Documentation closeout: `9a5f144`.
- **Historical mouse input work (`7b5ba45`):** accepted held preview and stale-input
  safeguards. Its physical gesture policy was superseded by the accepted
  [Physical Mouse Gesture Fidelity correction](../ARCHITECTURE.md#physical-mouse-input)
  at `e32145f`; use the current contract below.
- **Usability Batch 1:** persistent Replay default directory; Simple Auto
  interval **0..2000 ms**, default **180 ms**, **0 = "최대 속도"**; pending
  single-shot timer safely reschedules. Final full suite **1492/1492 PASS** and
  desktop smoke **PASS**; merged/pushed to `main` at `81c3d86`.
- **ZiNi Explorer Answer Display:** unopened-answer display defaults **ON**;
  safe numbers/mines appear faintly while cells remain covered, and **OFF**
  restores the old hidden representation. Revealed/unopened numbers share
  **Arial 14 Bold** typography/color; unopened answers use **35% opacity**.
  Slider track clicks seek directly to the clicked logical index; manual
  seeking stops autoplay. Trace/controller semantics are unchanged.
  Explorer UI **50/50 PASS**, related ZiNi/UI **422/422 PASS**, full unittest
  **1506/1506 PASS**, **0 failures / 0 errors / 0 skips**, desktop smoke **PASS**.
  Committed/pushed/merged to `main` at `3622eed`, with final Git state checked.

---

## 4. Current milestone

**ACTIVE — Selected Exemplar Board-State Reconstruction / Human Interpretation
Viewer. Slices 0–3 — FINAL PASS — COMPLETE / ACCEPTED by ChatGPT final review
(2026-10-18); each BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.**
See the [viewer contract](stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md).
ChatGPT accepted the preceding **DISCOVERY PASS; BLOCKER 0 / REQUIRED 0**.
**CURRENT / AUTHORIZED — Slice 4: Acceptance / Closeout**.
Independent pre-closeout audit is complete and the required production
correction has been accepted. Final Slice-4 acceptance gates remain pending.
No algorithm research is authorized.

### Independent pre-closeout audit and accepted R-1 correction

Claude Code independently audited committed Slice-3 candidate
`d338dcffa212e52efb23af9d9db41841348ade96` (`feat: add exemplar board inspection viewer`).
Verdict: **INDEPENDENT AUDIT CONDITIONAL — BLOCKER 0 / REQUIRED 2**.

**R-1 SATISFIED — ChatGPT final correction review PASS / ACCEPTED.** The
`QSpinBox.editingFinished` focus-loss signal could reinterpret a mirrored entry
value as navigation. Current correction commit `2c9ba42fb394ee528a035a85c3a2c8146b86a7f9`
(`fix: prevent exemplar viewer focus-loss navigation`) changed only
`exemplar_board_viewer_ui.py` and `tests/test_exemplar_board_viewer_ui.py`.
Ordinary focus loss and Tab no longer navigate; initial mode and BEFORE positions
survive focus changes. Return/Enter commits explicitly exactly once; Go buttons
use the same helpers. `_Position` remains the navigation authority.

Reported correction verification: **45 tests.test_exemplar_board_viewer_ui +
32 tests.test_exemplar_board_reconstruction + 34 tests.test_exemplar_board_evidence
= 111 PASS; 0 failures / 0 errors / 0 skips**. No full suite is claimed or rerun
by this documentation refresh. **No REQUIRED production correction remains.**

**R-2 OPEN — Slice-4 documentation / provenance closeout task**, not a remaining
production defect. Closeout must identify the final qualified committed SHA and
run final Slice-4 verification at that SHA. The earlier Slice-3 verification and
offscreen evidence were gathered before its commit; they remain accepted slice
evidence, not retroactively commit-qualified final acceptance evidence.

Audit dispositions: **O-1 label-test hardening, O-2 literal ratio-oracle hardening
and O-6 neutral ZiNi wording SATISFIED**; **O-3 / O-4 DEFER**; **O-5 DEFER TO
CLOSEOUT** (define/display Model C seconds as exact microseconds / 1_000_000 in
the final record); **O-7 / O-8 NO CHANGE**. No Claude re-audit after R-1 is required
or claimed. Final Slice-4 acceptance gates have not yet been run.

Accepted Slice-1 implementation:
[`exemplar_board_reconstruction.py`](../exemplar_board_reconstruction.py) and
[`tests/test_exemplar_board_reconstruction.py`](../tests/test_exemplar_board_reconstruction.py).
Reported verification: **32 new focused reconstruction + 28 timeline analytics +
27 Engine regression + 4 board analyzer + 9 Replay player = 100 PASS**;
**0 failures / 0 errors / 0 skips**. No full suite is claimed; no tests are rerun
by this documentation transition.

Accepted boundary: Qt-independent, already-finalized `BoardSnapshot` plus
already-validated `TimelineAnalytics`; immutable N+1 public frames and exact
newly-revealed-safe coordinate sets; terminal Engine feedback preserved; explicit
FLAG separated from automatic effects; static 3BV/Ops/isolated references and
final public Engine counter summary only. Original `TimelineAnalytics` retains
Model C / geometry / metadata authority; no Engine is retained. Slice 1 used
bounded synthetic fixtures only, with no DB/official exemplar inputs,
benchmark-board generation, Qt/UI, ZiNi, solver/planner or algorithm research.

**Slice 2 — Accepted-Evidence Loader COMPLETE / ACCEPTED by ChatGPT final review;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.** Accepted implementation:
[`exemplar_board_evidence.py`](../exemplar_board_evidence.py) and
[`tests/test_exemplar_board_evidence.py`](../tests/test_exemplar_board_evidence.py).
Reported verification: **34 new focused evidence-loader tests + 173 bounded
existing regressions = 207 PASS; 0 failures / 0 errors / 0 skips**. No full-suite
claim. This documentation transition reruns neither tests nor evidence smoke.

Accepted boundary: exact two-DB source authentication; immutable read-only
lifecycle; exactly one accepted run per role; fixed-four admission; selected-only
GameRecord/ActionEvent decoding with explicit enum and exact Fraction/None/zero
preservation; admitted-board generation and generated/persisted/fixed fingerprint
equality; authenticated frozen Model C; existing `project_timeline()` authority
and accepted Slice-1 `reconstruct_board()` composition. The bundle is immutable,
with no live DB connection or Engine. No G4/HTML runtime input, selection/ranking,
arbitrary browsing, Qt/UI, ZiNi, solver/planner or algorithm research.

Accepted bounded real-evidence smoke authenticated exact accepted DB hashes and
discovered exact accepted runs. Each source had requested/processed/stored
**100000 / 100000 / 100000**, exact official coverage PASS. Exactly **four boards**
were generated and **eight selected streams** loaded/projected/reconstructed.
All fixed fingerprints and accepted action/outcome/Model-C totals matched;
**1,508 persisted actions**, **0 status / 0 safe-reveal / 0 explicit-FLAG mismatches**.
Source hashes/sizes/mtimes remained unchanged after close; no sidecars or output
artifacts. No solver/planner, selection, G4 or report rerun. This is accepted
Slice-2 implementation evidence, **not final viewer closeout**.

**Slice 3 — Standalone Inspection UI COMPLETE / ACCEPTED by ChatGPT final review;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.** Accepted implementation:
[`exemplar_board_viewer_ui.py`](../exemplar_board_viewer_ui.py),
[`scripts/exemplar_board_viewer.py`](../scripts/exemplar_board_viewer.py) and
[`tests/test_exemplar_board_viewer_ui.py`](../tests/test_exemplar_board_viewer_ui.py).
Reported verification: **33 viewer UI + 4 launcher + 34 accepted evidence-loader +
32 accepted reconstruction + 6 selected Stage-3 visualizer rendering + 5 selected
ZiNi Explorer rendering + 2 adapted unchanged Same-board navigation assertions =
116 PASS; 0 failures / 0 errors / 0 skips**. The two Same-board assertions used
hand-recorded synthetic setup instead of solver-producing setup; assertions were
unchanged. No full-suite claim; no verification is rerun by this transition.

Accepted bounded real-evidence offscreen smoke loaded exact accepted Stage-2 /
Stage-3 sources through the Slice-2 API: **2 DB opens during initial load only,
4 board generations, 8 selected-action streams, 8 timeline projections and
8 reconstructions**. All eight game/solver pairs were inspected at initial,
middle and final states. Before/After, Answer Overlay ON/OFF, first-action and
LOSS terminal presentation were exercised; same-target and long-transition
presentation were checked where present. After initial load, navigation/selection/
toggles caused **0 DB opens / 0 board generations / 0 Engine reconstructions /
0 timeline projections / 0 solver/planner/selection calls**. Source hashes/sizes/
mtimes were unchanged; no sidecars or output artifacts. This is accepted Slice-3
evidence, **not final native/manual acceptance**.

Accepted boundary: standalone Qt UI, explicit accepted-loader-based launcher,
one board, four fixed exemplars, Stage-2/Stage-3 selector and eight independent
remembered inspection positions. First/Previous/Next/Last, integer frame slider,
direct frame/action entry and Before/After use immutable frames. Default-OFF
HIDDEN-only Answer Overlay, exact terminal Engine feedback, new-safe AFTER-only
highlighting and recorded previous/current target geometry remain separate; no
first-action origin path is fabricated. All 17 classic Counters rows remain;
historical Time/Est Time/3BV/s/CPS are unavailable and Efficiency/IOE/Thrp/Corr use
accepted final facts. **ZiNi/ZNE/ZNT rows remain; calculation is DEFERRED** because
there is no narrow public reusable job owner. Only immediate reference numbers
are omitted; the private main-UI lifecycle is not duplicated. Separate Model C
and exact persisted Action Context remain. No DB/Engine/reconstruction on
navigation, autoplay/timer/modeled animation, shared/common playhead, normalized
progress, solver/planner/selection/ranking, algorithm research or main-app integration.

The accepted consolidated Slice-0 contract includes the following unchanged scope:

- Fixed admission: **73758, 73024, 93557, 1**, with frozen Timeline memberships.
  No new selection, ranking, substitution or arbitrary-ID browsing.
- Minimum future inputs: exact accepted Stage-2/Stage-3 DBs plus tracked fixed
  exemplar identities and authenticated frozen Model C. G4/HTML remain historical
  provenance references, not required viewer inputs or freshly reauthenticated claims.
- Authenticate layout before applying original persisted ActionEvents. Each solver
  owns independent immutable frames; frame 0 is all hidden, frame n follows n inputs.
- Public View retains **Terminal Engine feedback**. Default-OFF Answer Overlay
  decorates only HIDDEN cells at about 0.35 opacity and never changes public state.
- One board with game/solver selectors, independent remembered positions and
  Before/After inspection. No solver/planner, Human comparison, shared clock,
  normalized progress, autoplay or modeled-time animation in the first version.
- Accepted source-checked references: static **answer-derived 3BV/Ops/isolated
  count**, **Reconstructed Counters — current Engine semantics; FINAL RUN SUMMARY**,
  and the full 17 classic Counters rows. Historical Time/Est Time/3BV/s/CPS stay
  unavailable. Engine public APIs supply total active/wasted and completed 3BV
  plus formatted final per-button/3BV/Ops values; extra raw breakdowns require a
  separately reported public-seam need, never private-state duplication.
- Keep exact existing Efficiency/IOE/Thrp/Corr formulas and ZiNi availability:
  bounded best-so-far ZiNi reference when available on WON/LOST; ZNE/ZNT only WON.
  Optional ZiNi calculation belongs to a separate reference/UI owner, not Slice 1
  or navigation; the accepted Slice-3 implementation explicitly defers calculation.
  Mechanical active/wasted and ZiNi are references, not strategic/speed judgments.
- Stage 2 selects **OPEN/FLAG on HIDDEN only**; CHORD absence is structural, not
  a decision to reject CHORD. Stage 3 recorded action space is OPEN/FLAG/CHORD.
- Explicit Model C fields: selected action cost, cumulative/final modeled time,
  Modeled 3BV/s and Modeled CPS. Exact authenticated integer table is authority,
  no action-type cost dimension or coefficient regeneration; both displayed streams
  are post-hoc evaluation. No historical-time, compute-speed or Human-speed claim.
- Selected target arrow and exact dx/dy/d² are **Action-target transition — not
  recorded cursor trajectory**. No first-action prior target is fabricated; Model C
  origin is separate. Five factual areas separate board/solver references, final
  Counters, Model C, action context and board presentation. Human interpretation
  owns route/strategy judgments; no automatic quality classifier or new algorithm.
- Accepted discovery regenerated exactly four matching fingerprints and replayed
  all eight streams / **1508 actions**, with **0 status / 0 safe-reveal /
  0 explicit-FLAG mismatches**, terminal exactly at the final persisted event.
  No solver/planner/runner calls; official artifacts unchanged. This is discovery
  evidence, not viewer implementation acceptance; Slice 0 does not repeat the proof.
- Slices: **0 Contract → 1 Pure reconstruction → 2 Accepted-evidence loader →
  3 Standalone inspection UI → 4 Acceptance / Closeout**. Slices 0–3 COMPLETE /
  ACCEPTED; Slice 4 CURRENT / AUTHORIZED, audit complete and R-1 ACCEPTED;
  final acceptance gates pending.
  Slices 0–3 technical semantics remain frozen.
- Remaining Slice-4 gates: focused/frozen verification, final source/full regression,
  bounded real four-case proof, source preservation checks, bounded native/manual
  presentation inspection, final closeout documentation including R-2 provenance
  and milestone closure adjudication. This refresh runs no final acceptance gates
  and adds no viewer features; the milestone stays ACTIVE.
- The accepted viewer excludes direct DB reads outside the loader, regeneration/reconstruction
  on navigation, solver/planner or selection/ranking reruns, arbitrary browsing,
  shared/common playhead, normalized progress, synchronized side-by-side, autoplay
  and modeled-time animation. No fabricated historical elapsed time or cursor
  trajectory/speed, automatic route/quality/causal judgment, frozen Model C/V1
  alteration or algorithm research.
- Preserve frozen V1/Model C, closed Timeline/Same-board/ZiNi, both Timeline report
  runs, official 100k and the unopened ZiNi final holdout.

### Closed Timeline Analytics baseline — preserved acceptance

**FINAL ACCEPTANCE PASS / CLOSED — Representative-board Demonstrations / Timeline Analytics. Slice 0 —
Contract COMPLETE / ACCEPTED by ChatGPT final review (2026-10-17, Asia/Seoul).**
ChatGPT adjudicated the read-only discovery **DISCOVERY PASS**. The accepted
[Timeline Analytics contract](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md)
records the scope and boundaries. **Slice 1 — Pure timeline analytics COMPLETE /
ACCEPTED by ChatGPT final review: SLICE 1 PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.**
**Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT
final review: SLICE 2 PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.**
**Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE /
ACCEPTED as a whole. Internal Slice 3A — accepted-evidence opening correction / preflight
COMPLETE / ACCEPTED by ChatGPT final review: SLICE 3A CORRECTION / PREFLIGHT PASS;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.**
**Internal Slice 3B COMPLETE / ACCEPTED: STAGE-3 EXTENDED TIMELINE ANALYTICS —
SLICE 3B FINAL PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 5.**
**Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED; BLOCKER 0 / REQUIRED 0.**
Only this milestone closes; Stage-3 Extended remains ACTIVE. Qualified source
candidate: `4c488e033dd045f1c203ff500d824cfaffb7cc67`. The
[final closeout](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) records acceptance.

Accepted Slice-1 implementation: [`timeline_analytics.py`](../timeline_analytics.py)
and [`tests/test_timeline_analytics.py`](../tests/test_timeline_analytics.py).
Verification: **28 focused PASS; 257 bounded existing regressions PASS**.
Four existing solver/Engine execution cases were intentionally excluded from
that bounded regression set; **no full suite is claimed**. The projection and
focused tests used in-memory synthetic facts with no DB access; the existing
regressions used synthetic SQLite fixtures only. No official benchmark DB or
artifact was accessed, no actual exemplar IDs were selected, and no solver runs,
benchmarks, builds or GUI were used. Frozen V1 / Model C are unchanged;
Human remains deferred.

Accepted Slice-2 implementation: [`representative_boards.py`](../representative_boards.py)
and [`tests/test_representative_boards.py`](../tests/test_representative_boards.py).
Verification: **29 focused PASS; 28 Slice-1 timeline PASS; 75 bounded existing
comparison/statistics regressions PASS. Total reported verification: 132 PASS.**
All Slice-2 selector fixtures were synthetic/in-memory; existing regressions used
synthetic SQLite fixtures. No official DB/G4 artifact was accessed and no actual
official exemplar ID was selected. No solver, benchmark, build, GUI or full-suite
execution occurred. Frozen V1 / Model C are unchanged; Human remains deferred.

Accepted Slice-3A correction: [`telemetry_repository.py`](../telemetry_repository.py)
and [`tests/test_telemetry_repository.py`](../tests/test_telemetry_repository.py).
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
[`scripts/stage3_timeline_report.py`](../scripts/stage3_timeline_report.py) and
[`tests/test_stage3_timeline_report.py`](../tests/test_stage3_timeline_report.py).
Final verification after R-1: **34 report + 29 representative selector + 28 timeline
analytics + 67 telemetry repository = 158 focused PASS; 174 bounded regressions
PASS; reported total 332 PASS**. Four solver/Engine execution tests were
intentionally excluded; **no full-suite claim was made at Slice 3B**.

Independent Claude Code read-only audit inspected the actual pre-correction report,
independently authenticated/recomputed selection, and reproduced all **1,508 action
rows and 16 SVGs with 0 mismatch**. Claude's verdict was **BLOCKER 0 / REQUIRED 0**,
with OPTIONAL O-1..O-6. ChatGPT promoted O-1 to REQUIRED R-1 for provenance/semantic
wording; the correction is accepted and **O-1 SATISFIED**. **O-2 DEFER** (chart
common scale), **O-3 NONBLOCKING** (parse-hashed-bytes TOCTOU hardening), **O-4 DEFER**
(selected-action SQL-test hardening), **O-5 DEFER** (additional synthetic failure
branches), **O-6 DEFER / NONBLOCKING** (extended run/git/config provenance).
Existing artifact/run/model/script identity is sufficient; added detail does not
justify regenerating an accepted report. No Claude re-audit after R-1 is claimed
or required; ChatGPT/Codex subsequently verified the wording-only correction
through source/tests/report.

Fixed accepted exemplars: maximum Stage-3 WW advantage **73758 / -27009085 us**;
median-delta WW **73024 / -16487355 us**, lower-median zero-based rank **18850 of
37702 WW**; closest-to-zero Stage-3 WW advantage **93557 / -7877513 us**;
Stage-2 WW advantage, exact WW tie, WL and LW are **EMPTY**; LL is **game 1**.
Unique selected games: **1, 73024, 73758, 93557**. No visual/manual substitution
occurred. Detailed actions were read only for these games from both sources;
all selected WW deltas exactly reconcile with G4. The
[accepted Slice-3B evidence record](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md#accepted-slice-3b-implementation-and-evidence)
contains the exact action counts and modeled totals. LL cost is through
termination, not time-to-win.

Final corrected report:
`results/stage3-timeline-analytics/20261017T113748060625Z-99dafa139703/report.html`,
**470817 bytes**, SHA-256
`b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3`.
Corrected script SHA-256:
`50f9d88e80b971596de59eadae1bb3bf96ee0d4da88d252684a7cbf0a15eb387`.
Preserve the earlier
`results/stage3-timeline-analytics/20261017T103913620889Z-54082dd14870/report.html`
as historical pre-final 3B evidence. Both reports are ignored local evidence;
do not overwrite/delete either, rerun/replace selection or generate another report
as part of this documentation update.

Accepted R-1 wording explicitly identifies both displayed timelines as post-hoc
Model C evaluations of persisted actions. Stage 2 did not natively declare Model C;
Stage-3 collection declared it and checked its native total, but persisted report
events retain no native per-action cost/cursor fields. Compute scopes are Stage-2
analysis versus Stage-3 analysis plus planning; no cross-stage compute-speed winner.
Stage-2 guess candidate count means exact-minimum-risk tie multiplicity / final
selector pool; official Stage-3 candidate count stays unavailable. Missing native
cursor/action-cost fields, Replay timestamps, full probability coordinate maps and
chosen plans are not fabricated. Official artifacts remained unchanged with no
new sidecars. No solver, Engine, board generation, official 100k rerun, Human data
or ZiNi holdout was used.

Final Slice-4 acceptance: `C:\venvs\minesweeper\Scripts\python.exe`, Python 3.12.10,
64-bit AMD64. **386 discovered / 386 PASS** focused/frozen, 0 failures/errors/skips,
6.198 s unittest / 6.935 s process. Full command:
`C:\venvs\minesweeper\Scripts\python.exe -B -m unittest discover -s tests -v`;
**2184 discovered / 2184 PASS**, 0 failures/errors/skips, 141.186 s unittest /
144.019 s process. Ordinary tests included Engine/solver execution; no official
benchmark/solver evidence rerun occurred. Final source/report/document checks PASS.
No fresh package/build/native GUI gate was required or run for this unchanged surface.

Ignored local closeout evidence:
`results/stage3-timeline-analytics-closeout/20261017T131224859Z/`
contains `focused-tests.txt`, `full-tests.txt` and `acceptance-summary.json`.
Final official artifact/model reauthentication PASS; hashes/sizes/mtimes unchanged,
no DB sidecars. Both reports remain preserved. The final report records generation
HEAD `c32e34c...`, `git_dirty=True`; its script SHA matches the byte-identical
committed `4c488e...` script, so this is accepted provenance, not a mismatch.

At Timeline closeout, the next direction was human/domain interpretation of
the fixed exemplars/report. The current viewer contract above supports that work;
actual algorithm research/implementation still requires a separate explicit
scope/specification decision.

The first implementation is a read-only report from exact accepted official
Stage-2 / Stage-3 artifacts, with deterministically selected category exemplars
(not a statistically representative sample), independent completed-action-count
timelines and bounded static visualization. Human adapters and interactive GUI
are deferred. No algorithm, Model C, schema or telemetry changes are in scope.
**Slice 3 was the FIRST scope authorized to authenticate and read the exact accepted
official Stage-2/Stage-3 DB and G4 artifacts.** Internal 3A completed the preflight.
**Internal Slice 3B first selected and disclosed actual official exemplar IDs**,
using only the already-accepted deterministic rules;
no visual/manual substitution is allowed after selection. **Read-only/report
output only:** do not rerun the official 100k or any solver, and do not modify
frozen official evidence. The implementation
feature branch at acceptance was `feature/stage3-timeline-analytics`. Live Git
remains authoritative for current branch/HEAD and integration state; a later
closeout documentation commit does not replace the qualified source identity.

### Closed Same-board baseline — preserved acceptance

**Stage-3 Extended remains ACTIVE. Same-board Human / Stage-2 / Stage-3 Comparison:
FINAL ACCEPTANCE PASS / CLOSED (2026-10-17, Asia/Seoul).** Slices 0–5 are
COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B. No Same-board
implementation work remains. See the
[final closeout](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md).
Stage-3 V1 / Model C remain CLOSED / FROZEN; ZiNi Improvement remains CLOSED.

**Slice 0 — contract documentation COMPLETE / ACCEPTED.** The
[comparison contract](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md)
has passed ChatGPT review.

**Slice 1 — Comparison domain and admission COMPLETE / ACCEPTED** by ChatGPT
final review. The pure Qt-independent foundation in
[`same_board_comparison.py`](../same_board_comparison.py) and its
[focused tests](../tests/test_same_board_comparison.py) preserve the original
Human Replay and separate Mouse Trace attachment as authorities. Admission
requires both `source_type == SOURCE_HUMAN` and explicit
`declared_full_game_human=True`. Neither Human metadata, caller declaration nor
successful reconstruction proves exclusively-Human historical provenance;
Human-labeled recordings may contain historical Auto input.

Layout identity uses exact layout equality and the existing canonical
fingerprint. Full-stream reconstruction rejects incomplete and post-terminal
streams. Opening qualification is factual, not proof of controlled experimental
conditions.

Reported Slice 1 verification: **29 focused passed; 202 relevant regression
passed; combined reported total: 231 passed**, zero failures/errors/skips.
No full suite, package or native GUI run was performed for Slice 1.

**Slice 2 — Isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT final review.
**Slice 2A — Pure isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT
final review. The pure Qt-independent layer in
[`same_board_runner.py`](../same_board_runner.py) uses separate fresh fixed-layout
Stage-2 and Stage-3 engines on the exact admitted Human layout. Stage 2 calls
unchanged `run_simple(..., accept_guesses=True, initial_open=(0,0), observer=...)`;
Stage 3 calls unchanged frozen `run_stage3()` with authenticated Model C.
Mined `(0,0)` immediate losses remain legitimate; no regeneration or retry occurs.
Native Stage-2 result/Replay/traces and native Stage-3 result/traces remain
authorities alongside the original Human Replay/Mouse Trace. The immutable
execution result/metric layer retains no live Engine or fabricated benchmark identity.

Accepted narrow seam: `benchmark_modeled_time.evaluate_ordered_actions()` reuses
existing authenticated Model C validation/cost logic for canonical ordered
complete inputs, including initial and terminal/losing input costs. It requires
no DB, GameRecord, seed, benchmark index or fabricated telemetry identity and
preserves existing evaluator callers. Stage-3 recorded modeled totals remain
authoritative and must exactly match independent evaluation through this seam.

Metric authorities remain separate: Human Replay elapsed seconds; Stage-2 Model C
microseconds; Stage-3 Model C microseconds; Stage-2 decision-compute nanoseconds;
Stage-3 decision-compute nanoseconds. No Human Model C time, generic speed field,
winner, ratio or Timeline Analytics is added. Frozen Stage-3 V1 / Model C are unchanged.

Reported Slice 2A verification: **31 new Slice 2A passed; 29 Slice 1 passed;
274 relevant regression passed; combined reported verification: 334 passed**,
zero failures/errors/skips. No full suite, package or native GUI run was performed
for Slice 2A.

**Slice 2B — Worker/process integration COMPLETE / ACCEPTED** by ChatGPT final review.
Slices 2A/2B are internal parts of the existing Slice 2, not new roadmap milestones.

The dedicated PyQt-independent [`same_board_execution_worker.py`](../same_board_execution_worker.py)
accepts exactly `{"token": request_token, "board": fixed_ReplayBoard}`. Human Replay
events and Mouse Trace never enter the worker; they remain parent-owned. The worker
executes the accepted solver-only fixed-layout Stage-2 + frozen Stage-3 path once.
Legitimate solver LOSS never triggers regeneration/retry; solver failures remain
failures, never fabricated LOSS. Source execution uses the module-relative worker
script; frozen execution uses `--same-board-execution-worker`, dispatched before
Qt GUI setup independently of the existing ZiNi and Stage-3 flags.

[`SameBoardExecutionJob`](../same_board_execution_job.py) owns one active child and
its private temporary directory. Normal poll/cancel process waits are nonblocking;
terminate -> kill escalation, reap before cleanup, cleanup before terminal success,
and retained ownership on reap/cleanup failure remain enforced. Stale/wrong-type
tokens are rejected. Parent composition attaches solver evidence to the exact
retained original Human context, preserving its Replay/Mouse Trace authorities.

Parent revalidation covers comparison/outcome-bearing facts: recomputed layout
identity, locally reauthenticated Model C, reconstructed/rechecked Stage-2 and
Stage-3 executed streams, terminal outcomes and model totals, relied-upon native
types, trace deltas and the Stage-3 cursor chain. It deliberately does **not**
recursively deep-walk the complete nested decision-evidence graph on every run.
Native decision/probability/plan evidence remains retained unchanged. Transport
is trusted-local/private; this is not a security guarantee for arbitrary pickles.

Independent Claude Code read-only audit: **BLOCKER 0; initially REQUIRED 1** —
avoidable parent-side recursive decision-evidence traversal affected responsiveness.
That REQUIRED finding was corrected and subsequently accepted by ChatGPT; no
independent Claude re-audit of the correction is claimed.

Representative genuine **30x16** evidence measured parent composition median
**681.4 ms before / 92.1 ms after**, after-change range **86.1–96.2 ms**;
separate after-change unpickle median **173.1 ms**. This demonstrates removal of
the avoidable deep-walk stall, **not zero GUI-thread blocking**. No arbitrary
runtime/FPS requirement is introduced; these are responsiveness observations,
not frozen algorithm-performance evidence.

Reported final Slice 2B verification: **84 Slice 2B passed; 31 Slice 2A passed;
29 Slice 1 passed; 374 relevant regressions passed; combined reported verification:
518 passed**, zero failures/errors/skips. No full suite, fresh package or native
GUI acceptance was run for Slice 2B.

**Slice 3 — Pure playback coordination COMPLETE / ACCEPTED** by ChatGPT final review.
The pure Qt-independent [`same_board_playback.py`](../same_board_playback.py)
coordinates exactly three run identities: `HUMAN`, `STAGE2`, `STAGE3`. Human uses
the original admitted Replay through existing `ReplayPlayer`; Stage 2 uses its
native algorithm Replay through another `ReplayPlayer`. Stage 3 uses a dedicated
Same-board fixed-layout trace player: arbitrary Human layouts must not fabricate
benchmark-specific `Stage3Execution` / `BenchmarkBoard` identity. It executes only
recorded `trace.move`; planner evidence and unexecuted plan suffixes are not
executable playback input. Playback invokes no solver/planner/worker and does not
reevaluate Model C.

Index 0 is the exact fixed all-HIDDEN initial board; index n is the state after
exactly the first n semantic inputs of that run. Each run retains its own index
and valid range. Switching restores the selected run's remembered index without
seeking or mutating another run. There is no clamping, index mapping or normalized
progress; equal numeric indices do not mean equivalent game progress.

Current reconstructed `status` is separate from recorded final outcome. A completed
WON/LOST run is still PLAYING at index 0. A legitimate solver first-action LOSS
is PLAYING at index 0 and LOST at index 1; Human outcome remains independently
authoritative.

Navigation does not mutate Human Replay, Mouse Trace, Stage-2 Replay/results/traces,
Stage-3 results/traces or metrics. Mouse Trace remains a separate attachment,
not played/transformed in Slice 3. No generic time/speed/progress authority,
common timeline, lockstep, synchronized three-board playback or universal
player/registry abstraction was introduced. No autoplay, Qt timer, interpolation
or UI was implemented.

Reported Slice 3 verification: **29 Slice 3 focused passed; 84 Slice 2B passed;
31 Slice 2A passed; 29 Slice 1 passed; 139 existing player/Engine/Replay/Mouse Trace/
fingerprint regressions passed; combined reported verification: 312 passed**,
zero failures/errors/skips. No full suite, package or native GUI run for Slice 3.

**Slice 4 — Read-only comparison UI COMPLETE / ACCEPTED** by ChatGPT final
adjudication, without production correction. Internal **4A — Read-only Comparison
Result Viewer** and **4B — Launcher + Main UI Integration / Lifecycle** are both
**COMPLETE / ACCEPTED**; they are subdivisions of official Slice 4, not new milestones.

The presentation-only [`same_board_comparison_ui.py`](../same_board_comparison_ui.py)
consumes one completed `SameBoardExecution` and owns one `SameBoardPlayback`, with
no worker/job/process/timer. One read-only board renderer uses only the selected
run's public observation. Human / Stage 2 / Stage 3 selection preserves independent
remembered indices; First / Previous / Next / Last and the selected-run action-index
slider are manual controls, with no autoplay or time coordination. The compact
three-run summary keeps current reconstructed status separate from final outcome;
first-open/layout qualification is factual, not controlled-experiment proof.
The optional full Human Mouse Trace uses the original immutable attachment, is
Human-only and independent of action index. The Stage-3 Visualizer stays separate.

Displayed authorities remain explicit: Human Replay elapsed seconds; Stage-2
Model C cost through termination µs; Stage-3 Model C cost through termination µs;
Stage-2 decision compute ns; Stage-3 decision compute ns. No Human Model C time
or generic time/speed winner, ranking or ratio is introduced.

[`same_board_comparison_launcher.py`](../same_board_comparison_launcher.py) and the
narrow `ui_manager.py` integration support both completed current Live games and
currently retained Replays through the existing recorder/Replay source path; no
Comparison-specific loader was added. Replay mode takes precedence and supplies
the entire original `ReplayData`, regardless of displayed index. Explicit Tools
action **Compare as full-game Human Replay…** declares
`declared_full_game_human=True`; `source_type == SOURCE_HUMAN` (`"human"`) remains mandatory. Neither
metadata, declaration nor reconstruction proves exclusively-Human historical input.

One launcher retains exactly one admitted `HumanComparisonContext` for its
lifetime. Replay seeks/replacement/exit, reset/new game, difficulty changes and
later Live actions do not retarget it. While it exists, **Open Comparison…** only
raises that owner. The launcher owns one unchanged `SameBoardExecutionJob`, active
token/cancellation intent, one retained completed execution and at most one viewer.
Run requires no active token AND an idle job. Normal Run/Cancel do not wait.
Legitimate solver WON/LOST are successful execution results, not failures. Closing
the viewer retains the completed result; reopening does not rerun solvers.

Launcher close irreversibly begins shutdown and disables execution, then calls
the accepted bounded `job.shutdown()`. Reap/cleanup failure rejects close and
retains ownership for retry. Only successful job shutdown permits viewer closure;
any rejected close leaves the launcher non-runnable, with safe close retry.
Main close order is Comparison launcher, Stage-3 Visualizer launcher, then existing
remaining teardown. Comparison close failure prevents all later teardown.

Independent Claude Code **read-only** audit reported **BLOCKER 0 / REQUIRED 0 /
OPTIONAL 4**, with a **PASS / accept Slice 4 as implemented** recommendation;
Claude did not execute/rerun tests. ChatGPT independently reviewed source/tests
and accepted without production correction. Optional dispositions: **O-1 DEFER /
evidence-triggered**, theoretical matching success after cancellation intent (the
real job contract and acceptance evidence do not expose that path);
**O-2 SATISFIED by Slice 5A**, real packaged-worker/job/launcher lifecycle evidence;
**O-3 NONBLOCKING**, 2085/2085 full development PASS with no new production defect;
**O-4 DEFER**, captured-source wording polish (user acceptance reported no confusion
requiring a correction). None is a production acceptance blocker.

Reported Slice 4 verification: **55 new 4B passed (31 launcher / 24 main UI);
32 4A viewer; 29 Slice 3; 84 Slice 2B; 31 Slice 2A; 29 Slice 1; 370 relevant existing
regressions; combined reported verification: 630 passed**, zero failures/errors/skips.
Those were Slice-4-only counts; full source/package/native acceptance below is
Slice 5 evidence, not independent-audit test results.

**Slice 5 — Acceptance / Packaging / Native Manual Closeout COMPLETE / ACCEPTED.**
Qualified candidate: `a59d0d963bdf1544a03968163b884342e2797ee0`.
Final evidence root: `results/same-board-comparison-final-acceptance/20261017-022243/`;
primary `acceptance-summary.json`, package `dist/Minesweeper/`.

- Source focused: **916 PASS**, 0 failures/errors/skips, **44.286 s**.
- Full development: **2085 PASS**, 0 failures/errors/skips, **118.136 s**.
- Fresh Python 3.12.10 x64 / pip 25.0.1 / documented pins: **2085 discovered,
  2060 PASS, 25 permitted optional image/video replay-validation skips**, 0 failures/errors.
- Fresh onedir/windowed AMD64 / PE32+ / GUI build: **exit 0, 63.789 s**.
  EXE SHA-256: `4893d24e1f9d50e47008f94aff4399188123331f49d3cd8d70ab3bc5eab6a5e8`.
- Frozen profile source/package bytes match SHA-256
  `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
  Specs/runner/planner unchanged; no official 100k regeneration or ZiNi holdout consumption.
- Packaged safe-origin board: **WON/WON, 4 actions / 504,020 µs each**; mined origin:
  **LOST/LOST, one OPEN(0,0) / 126,005 µs each**, no regeneration/retry.
  Deterministic source/package equality excludes runtime decision-compute clocks
  and Stage-2 Replay elapsed engine-clock timestamps, not arbitrary semantic differences.
- Packaged failure boundaries, existing Stage-3/ZiNi dispatch compatibility and
  native startup/normal close PASS. Seven actual packaged-child lifecycle cases
  PASS; `packaged-lifecycle.json` records each PID/private directory, successful
  reap/removal and original Human context/Replay/Mouse Trace identity retention.
- **Project user, 2026-10-17 (Asia/Seoul): packaged native/manual A–L PASS** on this
  exact package: startup, both source routes, Run/result facts, independent indices,
  Human-only full trace, reopen, Cancel, active launcher/main close and existing-feature
  compatibility. This is reported interaction evidence, not inferred from screenshots.
  Human WON / Stage 2 LOST / Stage 3 LOST displayed legitimate results; a loaded
  Replay at another index still supplied its entire stream and viewer Human index 0.

Historical `results/same-board-comparison-final-acceptance/20261017-014937/` remains
**BLOCKED**: 2085 discovered / 2076 passed / 9 fixture errors / 0 failures/skips.
The no-op `_init_ui()` fixture lacked mandatory `same_board_comparison_action`.
Only `tests/test_replay_statistics.py` changed in the accepted correction; verification
was **9/9 affected, 158/158 related, 2085/2085 full PASS**. No production correction.
The final automated root restarted from the new clean candidate. Its JSON remains
the pre-manual snapshot; the [closeout](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md)
records subsequent user PASS without rewriting raw evidence.

Nonblocking UX: standard Comparison slider track page-step is **OPTIONAL / DEFER**;
drag/arbitrary selected-run seek works, exact track jump was not required.
**KEEP** Human recorded Mouse Trace separate from the independent Visualizer's
synthetic Stage-3 cursor; Comparison has no solver overlay. Changing production
would reopen package qualification. No generic speed winner/ranking/ratio is claimed.

- **Execution / Playback / Visualizer Foundation — CLOSED (2026-10-14)**:
  [historical acceptance](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)
  and [final adjudication](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md).
  Accepted process ownership/lifecycle is not reopened.
- **Version / Settings Identity Separation — CLOSED (2026-10-15)**:
  [closeout](stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md).
  Application/release, algorithm, physical model/profile and presentation remain distinct.
- **Modeled-Time Playback / Synthetic Smooth Cursor Presentation —
  FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**:
  [closeout](stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md).
- **Human Mouse Trace / Path Visualization — FINAL ACCEPTANCE PASS / CLOSED
  (2026-10-16)**: [closeout](stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md).
  Includes Physical Mouse Gesture Fidelity and performance hardening; final user
  native acceptance of the final package passed.

Current accepted contracts:

- Human trace records actual Live-board accepted event samples in board-local Qt
  logical pixels, with exact subpixel positions and an independent monotonic clock.
  No timer sampling, distance filtering or semantic point dropping. Continuity
  breaks create segments; marker action semantics come from actual ReplayEvent indices.
- Recording defaults ON per app/session and locks on first committed timed human
  OPEN/FLAG: L release for OPEN, R press for FLAG. Untimed pre-start CHORD cannot
  start trace. OFF at that lock point, a committed Auto action or Replay append
  failure after committed human input invalidates the Human trace.
- Replay v2 can carry the separate Human trace attachment; v1 remains trace-free
  and readable. Display is optional after a Live game or in Replay; seek retains
  the attachment.
- Mode A/C FLAG/UNFLAG commits immediately on R press; R release adds no FLAG.
  Mode A keeps normal L-release OPEN/CHORD and independent R actions during L hold;
  Mode C never CHORDs. Mode B arms on held-button overlap regardless of origins,
  suppresses R FLAG only when L was already held, and never undoes an earlier
  standalone R FLAG. First release attempts CHORD at the current target; trailing
  release is inert, and new overlaps can re-arm with one button still held.
  FLAGGED-center preview preserves the flag and depresses surrounding hidden cells.
- Primitive recorder storage, pre-start gating, geometry cache and **16 MiB**
  bounded raster/fallback preserve sample semantics. Final user testing found no
  noticeable trace performance regression; zero overhead is not claimed.
- Stage-3 synthetic cursor remains presentation only. TracePlayer owns committed
  integer state; the modeled controller owns partial time. Recorded costs, frozen
  V1 / Model C identities and official 100k evidence are unchanged.

Qualified acceptance: **627/627 focused**, **1825/1825 source full** with zero
failures/errors/skips; fresh build environment **1800 passed / 25 optional image/video
validation skips**, zero failures/errors. Fresh AMD64 GUI package, both workers,
native GUI, Replay v2 trace round-trip and final user native check passed; no orphans.
Authoritative technical evidence:
`results/human-mouse-trace-final-acceptance/20261016-003839/acceptance-summary.json`.
The earlier `20261015-215537/` root remains historical performance-hardening evidence,
not the final package. The new closeout records user acceptance after that JSON's
pre-user-check status; neither evidence root is rewritten.

---

## 5. Accepted ZiNi boundaries

- **TYPE S:** implemented core optimizations preserve V1 semantics and are
  protected by reference and frozen golden tests. No speed ratio is claimed here.
- **TYPE Q:** V1 remains the production quality policy. V2 A/B/C policies,
  experimental G6/F-2/K0/N-setupOFF and lambda are not production settings.
  V2 research is closed; no Family A implementation or further lambda/search/
  semantics tuning is authorized by this milestone.
- **Trace / Explorer:** the post-hoc backend, result transport/controller and
  separate Explorer UI are implemented. Trace is built lazily on request from
  the final result, without rerunning search. It is not a full search-tree record.
  The later answer-display closeout changes presentation only.

Replay = playback of actually executed game actions.
ZiNi Trace = playback/explanation of answer-board-based ZiNi simulation choices.
**Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace**; similar controls do not justify merging their models.

---

## 6. Next action

Same-board Comparison is **FINAL ACCEPTANCE PASS / CLOSED**, with Slices 0–5
COMPLETE / ACCEPTED. No Same-board implementation or technical acceptance gate
remains. On recovery, read live Git for the latest branch, HEAD, remote and merge
state. The qualified acceptance SHA is historical identity, not a permanent
branch tip or an instruction to perform further Git integration.

**Representative-board Demonstrations / Timeline Analytics — FINAL ACCEPTANCE
PASS / CLOSED. Slices 0–4 COMPLETE / ACCEPTED**, including internal 3A/3B.
Qualified implementation/source candidate:
`4c488e033dd045f1c203ff500d824cfaffb7cc67`. Final focused/frozen **386 PASS** and
full source **2184 PASS**, zero failures/errors/skips; no GUI/package gate required.
See the [closeout](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) and
[accepted contract](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md).

**CURRENT / NEXT / AUTHORIZED:** Slice 4 — Acceptance / Closeout under
the [accepted viewer contract](stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md),
following Slices 0–3 COMPLETE / ACCEPTED by ChatGPT final review; each
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0. Independent pre-closeout audit is complete;
R-1 is SATISFIED by the accepted correction (111 PASS). No REQUIRED production
correction remains; R-2 final committed-SHA qualification/provenance remains OPEN.
Final Slice-4 acceptance gates remain pending as recorded in the current milestone
section. This refresh performs no final verification or new feature work.
The accepted one-board inspection/navigation and default-OFF
Answer Overlay boundaries remain frozen. Loading uses the accepted Slice-2 API only;
navigation performs no DB/Engine reconstruction. No solver/planner execution,
new selection/ranking, arbitrary-ID browsing or official 100k rerun.
The viewer supports human/domain
interpretation of the fixed exemplars before choosing/specifying an actual
Extended algorithm research direction. No new algorithm research or implementation
is authorized. Timeline has no remaining technical gate; Extended remains ACTIVE.

Preserve fixed category memberships, both report runs and official evidence.
No visual/manual substitution, official 100k/solver rerun or frozen-evidence change.
Human Replay/Mouse Trace adapters remain deferred. The standalone viewer Qt
surface is COMPLETE / ACCEPTED in Slice 3; final native/manual acceptance remains
with Slice 4.
No new Model C, database/schema or telemetry is authorized. Read live Git for current
branch/HEAD state; later documentation commits do not replace qualified source identity.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human Mouse Trace is accepted actual sampled Live-board pointer presentation data,
not Stage-3 synthetic movement, Model C calibration evidence or solver input.
The closed Comparison contract retains these separate models and time authorities.

Keep presentation separate from planner inputs, physical identity and recorded
costs. Retain Step 0/current PLAYING with known final WON, exact action-boundary
commits, integer navigation and non-persistent controls. Synthetic movement and
smoothstep easing do not measure physical mouse motion.

Foundation F-2 remains **OPTIONAL / DEFER**: packaged windowed transport exceptions
may show PyInstaller's uncaught-exception dialog rather than exit immediately.
There is no false success; existing Cancel/close ownership/reaping remains.
No new evidence promotes F-2 to required work.

Preserve historical and new acceptance artifacts. The Same-board closeout created
no release/tag/ZIP; Timeline Slice 0 added no generated evidence, while Slice 3's
accepted corrected report and historical pre-correction report are preserved.
Do not reopen ZiNi work or consume its unopened final quality holdout.

---

## 7. Stage-3 Extended roadmap and boundaries

Stage-3 Extended remains **ACTIVE**, separate from frozen V1.

Natural dependency roadmap — not a rigid chronological schedule:

1. **CLOSED:** Execution / Playback / Visualizer Foundation.
2. **CLOSED:** Version / Settings Identity Separation.
3. **CLOSED:** Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **CLOSED:** Human Mouse Trace / Path Visualization.
5. **CLOSED:** Same-board Human / Stage-2 / Stage-3 Comparison — Slices 0–5
   COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B.
6. **CLOSED:** Representative-board Demonstrations / Timeline Analytics —
   Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 1 — Pure timeline analytics COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE / ACCEPTED.
   Internal Slice 3A — accepted-evidence opening correction / preflight COMPLETE / ACCEPTED.
   Internal Slice 3B — selection / selected-action report COMPLETE / ACCEPTED.
   Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED.
7. **ACTIVE — interpretation support:** Selected Exemplar Board-State Reconstruction /
   Human Interpretation Viewer; **Slices 0–3 COMPLETE / ACCEPTED by ChatGPT final review;
   each BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**. **Slice 4 CURRENT / AUTHORIZED —
   Acceptance / Closeout**; independent audit complete, R-1 correction ACCEPTED,
   final acceptance gates pending.
   This supports evidence-guided
   human/domain interpretation of fixed exemplars/report before choosing/specifying
   the first actual Extended algorithm research direction. Actual algorithm research
   requires separate explicit scope/specification; no candidate policy is adopted.

This is a dependency roadmap, NOT a rigid chronological schedule. If
implementation evidence makes an adjacent task more natural earlier, the order
may change without changing milestone boundaries.

The following remain **DEFERRED / evidence-triggered** candidates, not mandatory work:

- arbitrary-seek checkpoint/cache optimization
- modeled-time slider / sub-action scrubbing
- 120-fps UI target, easing selector and click pulse
- persistent Stage-3 presentation settings; settings dataclass until an external consumer exists
- runtime application/release display or version constant
- selectable algorithms/profiles and durable cross-version Stage3Execution transport
- richer physical model / Model C successor or refit
- action-specific OPEN / FLAG / CHORD timing and physical CHORD variants
- CPS / burst / minimum inter-action constraints, anisotropy and human cognitive timing
- built-in screen recording unless later justified
- logical-known-mine / no-flag execution and richer / longer planning

Boundaries:

- Stage-3 V1 and frozen Model C remain frozen. Do not alter V1 semantics merely
  for UI convenience.
- Prefer existing runner/trace interfaces and minimum necessary abstraction.
  No generic solver registry, EventBus or plugin framework.
- **Replay elapsed time != modeled physical time**; decision compute time is
  separate as well. Display animation is not a new physical-time measurement.
- **Playback/display settings != planner inputs.** Playback speed must not
  change recorded actions, planner decisions or benchmark/model totals.
- Keep application version, algorithm version and physical model/profile
  identity separate. Future algorithm/profile changes require their own
  specifications and evaluation; the backlog does not authorize them now.

Built-in screen recording is not currently a priority; external tools can record
the visualization. New Extended documentation belongs in `docs/stage3-extended/`;
the Extended README distinguishes the closed milestones, including Timeline
Analytics with Slices 0–4 and internal 3A/3B accepted, from the viewer's accepted
Slice-0 contract, Slice-1 reconstruction, Slice-2 loader and Slice-3 standalone UI,
with Slice 4 authorized, independent audit complete and R-1 correction accepted;
final acceptance gates remain pending. These support
domain interpretation before separately scoped algorithm
research. Arbitrary native Stage-3
seeks still rebuild from index 0; incremental forward is implemented,
while arbitrary-seek caching is deferred.

---

## 8. Documentation map

Start from:

- `docs/README.md`
- `docs/stage3-v1/README.md`
- `docs/stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md`
- `docs/stage3-extended/README.md`
- [Selected Exemplar Board-State Viewer — Slices 0–3 accepted; Slice 4 authorized](stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md)
- [Timeline Analytics closeout — FINAL ACCEPTANCE PASS / CLOSED](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)
- [Timeline Analytics contract — Slices 0–4 accepted](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md)
- [Human Mouse Trace closeout](stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md)
- [Modeled-Time Playback closeout](stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md)
- [Identity Separation closeout](stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md)
- [Foundation final adjudication](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)
- [Foundation acceptance evidence](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)
- `STAGE3_ALGORITHM_SPEC_v1.md`
- `STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md`
- `STAGE3_EXTENSION_BACKLOG.md`
- `docs/zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md`
- `README.md`, `ARCHITECTURE.md`, `BUILDING.md`

External recovery/source-panel companions verified on 2026-10-14:

- `C:\Users\User\Desktop\비상시 프롬프트.txt`
- `C:\Users\User\Downloads\PROJECT_SOURCE_REFRESH_PLAN.md`

Both exist **outside this repository**; they are not tracked repository files.
Do not invent repository locations for them or assume Project attachments
automatically match the local originals.

Existing historical documents and frozen/evidence paths remain in place for
provenance. Do not reorganize them merely for visual neatness.

---

## 9. Engineering principles

Continue to apply:

- Single Responsibility Principle
- Separation of Concerns
- maintainability
- extensibility
- testability
- backward compatibility
- DRY only where it removes meaningful duplication
- KISS
- YAGNI
- evidence before optimization
- minimum necessary abstraction

When something appears unnecessary, do not remove it immediately.

First state:

1. why it may be unnecessary
2. what would be lost by removing it
3. whether to `KEEP`, `DEFER`, or `REMOVE`

---

## 10. Working-role convention

For major milestones:

- ChatGPT: design / review / final adjudication
- Codex: implementation / execution / focused verification
- Claude Code: independent read-only audit when warranted

For disputed findings, return to source/tests rather than choosing an AI by reputation.

---

## 11. New-chat recovery prompt

Reconcile recorded milestone status with live Git/source/tests; do not force Git
to match dated prose.

```text
이 채팅은 Minesweeper 졸업프로젝트 작업을 이어가는 새 채팅입니다.
저장소: C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project
Python: C:\venvs\minesweeper\Scripts\python.exe

먼저 live Git의 branch / HEAD / origin/main / working tree를 확인하고
docs/CURRENT_HANDOFF.md, docs/README.md 및 최신 source/tests를 읽으세요.
source → tests → 실행 검증 → frozen specs/final adjudication → current docs
→ 이전 AI summaries 순서로 판단하세요. 날짜가 찍힌 SHA나 prose를 latest로
가정하지 말고 live evidence를 우선하세요.

마지막 기록 상태: Stage-3 V1 / Model C CLOSED/FROZEN, ZiNi Improvement CLOSED.
Execution / Playback / Visualizer Foundation CLOSED.
Version / Settings Identity Separation FINAL ACCEPTANCE PASS / CLOSED.
Modeled-Time Playback / Synthetic Smooth Cursor Presentation FINAL ACCEPTANCE PASS / CLOSED.
Human Mouse Trace / Path Visualization FINAL ACCEPTANCE PASS / CLOSED.
Human Mouse Trace qualified SHA: e32145fa5c114e1ce500ad2e837ef6000cc49cca.
Same-board Human / Stage-2 / Stage-3 Comparison: FINAL ACCEPTANCE PASS / CLOSED.
Slice 0–5 및 내부 2A/2B·4A/4B는 COMPLETE / ACCEPTED입니다.
Qualified source/package SHA: a59d0d963bdf1544a03968163b884342e2797ee0.
Qualified development branch at acceptance: feature/stage3-same-board-comparison.
이후 branch 존재 여부 / 최신 HEAD / merge 상태는 live Git에서 확인하세요.
Closeout: docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md.
Contract: docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md.
최종 evidence: results/same-board-comparison-final-acceptance/20261017-022243/.
Package: 위 root의 dist/Minesweeper/.
EXE SHA-256: 4893d24e1f9d50e47008f94aff4399188123331f49d3cd8d70ab3bc5eab6a5e8.
Source focused 916 / full 2085 PASS, zero failures/errors/skips.
Fresh-env: 2085 discovered / 2060 PASS / optional image-video skips 25, zero failures/errors.
Fresh package exit 0; safe/mined worker·기존 dispatch·7 real packaged lifecycle PASS.
프로젝트 사용자 2026-10-17 native/manual A–L PASS; 정확한 package와 상세 gate는 closeout 참조.
Historical 20261017-014937 root는 BLOCKED (2076 PASS / 9 fixture errors)로 보존합니다.
a59d0d9는 tests/test_replay_statistics.py만 보정했으며 production 변경은 없습니다.
9/9 affected, 158/158 related, 2085/2085 full PASS 후 새 SHA/root에서 수용을 재시작했습니다.
Claude read-only audit: BLOCKER 0 / REQUIRED 0 / OPTIONAL 4 / PASS; 테스트 재실행 없음.
O-1 DEFER/evidence-triggered, O-2 SATISFIED, O-3 NONBLOCKING, O-4 DEFER.
Comparison slider track page-step는 OPTIONAL/DEFER; Human trace/solver synthetic 표현 분리는 KEEP.
Same-board 구현 또는 기술 수용 작업은 남아 있지 않습니다. 수용 SHA는 역사적 identity이며
현재 Git 통합 상태나 후속 Git 작업 지시를 의미하지 않습니다.
Stage-3 Extended는 ACTIVE입니다. Representative-board Demonstrations / Timeline Analytics는
FINAL ACCEPTANCE PASS / CLOSED; BLOCKER 0 / REQUIRED 0입니다.
Slices 0–4 COMPLETE / ACCEPTED이며 internal 3A/3B는 Slice 3의 하위 단계입니다.
Qualified implementation/source candidate: 4c488e033dd045f1c203ff500d824cfaffb7cc67
(feat: add timeline analytics report). 이후 documentation-only commit은 이 수용 identity를 대체하지 않습니다.
Closeout: docs/stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md.
Contract: docs/stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md.
구현: timeline_analytics.py, representative_boards.py, telemetry_repository.py의 immutable read-only 확장,
scripts/stage3_timeline_report.py 및 대응 tests. Model C/V1/schema/telemetry는 변경하지 않았습니다.
Approved interpreter: C:\venvs\minesweeper\Scripts\python.exe; Python 3.12.10, 64-bit AMD64.
최종 focused/frozen: 386 discovered / 386 PASS, failures/errors/skips 0;
6.198 s unittest / 6.935 s process.
최종 full source: 2184 discovered / 2184 PASS, failures/errors/skips 0;
141.186 s unittest / 144.019 s process.
Command: C:\venvs\minesweeper\Scripts\python.exe -B -m unittest discover -s tests -v.
Ordinary unit tests의 Engine/solver 실행은 포함했으며 official benchmark/evidence 재생성은 아닙니다.
Ignored local evidence: results/stage3-timeline-analytics-closeout/20261017T131224859Z/
(focused-tests.txt, full-tests.txt, acceptance-summary.json). Git에 추가하지 마세요.
Production GUI/package surface 변경이 없어 fresh build/package/native GUI gate는 필요하지 않았고 실행하지 않았습니다.
고정 category: max Stage-3 WW 73758/-27009085 us; median WW 73024/-16487355 us
(lower-median zero-based rank 18850/37702); closest negative WW 93557/-7877513 us;
Stage-2 WW advantage/exact tie/WL/LW는 EMPTY; LL은 1. Unique: 1, 73024, 73758, 93557.
Deterministically selected category exemplars이며 statistically representative sample이 아닙니다.
Actions/Model C totals (Stage2/Stage3): game 1 LL 4/4, 720354/720354 us (termination only);
game 73024 WW 313/207, 53655374/37168019 us; game 73758 WW 320/177, 57365067/30355982 us;
game 93557 WW 279/204, 47034727/39157214 us. WW delta는 모두 G4와 정확히 일치합니다.
No visual/manual substitution. 최종 수용 검증에서는 selection을 재실행하지 않았습니다.
최종 report: results/stage3-timeline-analytics/20261017T113748060625Z-99dafa139703/report.html
(470817 bytes; SHA-256 b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3).
Historical report: results/stage3-timeline-analytics/20261017T103913620889Z-54082dd14870/report.html
(469772 bytes; SHA-256 277e6889d9ade1c944eabebeeec7fcca0a4524e496af449cd9b60e73676d6203).
Script SHA-256: 50f9d88e80b971596de59eadae1bb3bf96ee0d4da88d252684a7cbf0a15eb387.
Report generation HEAD c32e34c... / git_dirty=True와 qualified candidate 4c488e...의 차이는
byte-identical script SHA로 검증된 수용 provenance입니다. 두 ignored local report는 overwrite/delete하지 마세요.
Claude pre-correction read-only 감사: selection 인증/재계산, 1,508 action rows 및 16 SVG 재현,
mismatch 0, BLOCKER 0 / REQUIRED 0, OPTIONAL O-1..O-6.
ChatGPT가 O-1을 R-1로 승격 후 SATISFIED. O-2 DEFER, O-3 NONBLOCKING, O-4/O-5 DEFER,
O-6 DEFER/NONBLOCKING. R-1 후 Claude 재감사는 주장하지 않으며 필요하지 않습니다.
ChatGPT/Codex가 wording-only correction을 source/test/report로 검증했습니다.
양쪽 timeline은 persisted actions의 post-hoc Model C 평가이며 retained native action-cost/cursor가 아닙니다.
Stage-2 compute=analysis, Stage-3=analysis+planning; cross-stage compute-speed winner는 없습니다.
Stage-2 guess candidate count=exact-minimum-risk tie multiplicity/final pool; Stage-3 count=unavailable.
누락된 native cursor/action-cost/Replay timestamp/probability-map/plan evidence는 만들지 않습니다.
LOSS는 termination cost이며 time-to-win이 아닙니다. Shared execution clock/normalized progress는 없습니다.
Official artifact/Model C hash 재인증 PASS, bytes/sizes/mtimes 불변, DB sidecar 없음.
Frozen V1/Model C, official 100k, Same-board CLOSED, ZiNi CLOSED 및 미개봉 final holdout을 보존합니다.
Human은 DEFER이며 Human/Replay/solver trace의 clock/authority를 합치지 않습니다.
CURRENT: Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer.
Discovery PASS / BLOCKER 0 / REQUIRED 0 수용.
Slices 0–3 FINAL PASS — COMPLETE / ACCEPTED by ChatGPT final review.
각 slice BLOCKER 0 / REQUIRED 0 / OPTIONAL 0. Slice 4 CURRENT / AUTHORIZED;
Independent pre-closeout audit is complete and the required production
correction has been accepted. Final Slice-4 acceptance gates remain pending.
Claude audited d338dcffa212e52efb23af9d9db41841348ade96:
INDEPENDENT AUDIT CONDITIONAL — BLOCKER 0 / REQUIRED 2.
R-1 focus-loss navigation defect FIXED / ChatGPT PASS / ACCEPTED / SATISFIED at the current correction commit.
Correction verification: 45 viewer UI module + 32 reconstruction + 34 evidence-loader = 111 PASS;
0 failures / 0 errors / 0 skips; no full-suite claim. No REQUIRED production correction remains.
Ordinary focus loss/Tab do not navigate; initial/BEFORE positions survive;
Return/Enter commits exactly once, Go uses the same helpers, _Position remains authority.
O-1/O-2/O-6 SATISFIED; O-3/O-4 DEFER; O-5 DEFER TO CLOSEOUT
(Model C seconds = exact microseconds / 1_000_000); O-7/O-8 NO CHANGE.
R-2 OPEN: final closeout must identify a qualified committed SHA and verify at that SHA.
Earlier precommit Slice-3 evidence is accepted historical slice evidence, not final commit-qualified evidence.
No Claude re-audit after R-1 is required or claimed.
Contract: docs/stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md.
Accepted Slice-1 files: exemplar_board_reconstruction.py / tests/test_exemplar_board_reconstruction.py.
Verification: 32 reconstruction + 28 timeline + 27 Engine + 4 board analyzer + 9 Replay player = 100 PASS;
0 failures / 0 errors / 0 skips, no full-suite claim. 이 문서 전환은 검증을 재실행하지 않습니다.
Finalized BoardSnapshot + validated TimelineAnalytics에서 immutable N+1 public frames/new-safe sets,
terminal feedback, explicit FLAG/automatic-effect separation, static board references와 final public counters를 보존합니다.
원래 TimelineAnalytics가 Model C/geometry/metadata authority이며 Engine은 보유하지 않습니다.
Slice 1은 synthetic only였으며 DB/official exemplar/benchmark generation/Qt/ZiNi/solver/planner/research를 사용하지 않았습니다.
Accepted Slice-2 files: exemplar_board_evidence.py / tests/test_exemplar_board_evidence.py.
Verification: 34 new evidence-loader + 173 bounded regressions = 207 PASS;
0 failures / 0 errors / 0 skips, no full-suite claim.
Accepted bounded smoke: exact two-DB hashes/runs/official coverage PASS;
requested/processed/stored = 100000/100000/100000 per source.
Exactly 4 generated boards / 8 selected loaded/projected/reconstructed streams;
all fixed fingerprints and action/outcome/Model-C totals matched; 1,508 actions,
status/safe-reveal/explicit-FLAG mismatch 0. Source hashes/sizes/mtimes unchanged after close,
no sidecars/output artifacts; no solver/planner/selection/G4/report rerun.
이는 accepted Slice-2 implementation evidence이며 final viewer closeout이 아닙니다.
Slice 2는 exact authentication/immutable lifecycle/one run per role/fixed-four selected-only decoding,
exact enum/Fraction/None/zero, admitted-board fingerprint gate, frozen Model C/project_timeline,
accepted reconstruct_board composition을 구현했습니다. Immutable bundle에 live DB/Engine은 없습니다.
G4/HTML runtime input, selection/ranking/arbitrary browsing, Qt/ZiNi/solver/planner/research는 제외했습니다.
Accepted Slice-3 files: exemplar_board_viewer_ui.py / scripts/exemplar_board_viewer.py /
tests/test_exemplar_board_viewer_ui.py. Slice 3 COMPLETE / ACCEPTED by ChatGPT final review;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.
Verification: 33 viewer UI + 4 launcher + 34 evidence-loader + 32 reconstruction +
6 Stage-3 rendering + 5 ZiNi Explorer rendering + 2 adapted unchanged Same-board
navigation assertions = 116 PASS; 0 failures / 0 errors / 0 skips; no full-suite claim.
Accepted offscreen smoke: exact sources loaded through Slice-2 API; initial load only
2 DB opens / 4 board generations / 8 selected-action streams / 8 projections / 8 reconstructions.
All 8 pairs initial/middle/final, Before/After, Answer Overlay ON/OFF, first-action/LOSS terminal,
same-target/long-transition where present were exercised. After load, navigation/selection/toggles:
0 DB opens / 0 board generation / 0 Engine reconstruction / 0 timeline projection /
0 solver/planner/selection calls. Source hashes/sizes/mtimes unchanged; no sidecars/output artifacts.
이는 accepted Slice-3 evidence이며 final native/manual acceptance가 아닙니다.
Accepted UI: explicit accepted-loader launcher, one board, fixed four/Stage2/Stage3 selectors,
eight independent remembered positions, First/Previous/Next/Last, integer frame slider,
direct frame/action entry, Before/After, default-OFF HIDDEN-only overlay, exact terminal feedback,
AFTER-only new-safe highlighting, recorded targets/transition, no first-action origin path,
17-row Counters with unavailable historical time/rates and accepted final ratios,
separate Model C / exact Action Context. ZiNi/ZNE/ZNT rows retained; calculation DEFERRED.
No public reusable ZiNi job owner exists; only immediate reference numbers are omitted.
CURRENT / AUTHORIZED: Slice 4 — Acceptance / Closeout.
Independent pre-closeout audit complete / R-1 correction accepted; final Slice-4 gates pending.
이 refresh는 문서만 갱신하며 final acceptance를 수행하지 않습니다.
Remaining gates: focused/frozen verification, final source/full regression, bounded real four-case proof,
source preservation, bounded native/manual inspection, R-2 qualified-SHA provenance and final closeout adjudication.
새 viewer feature나 main-app integration을 추가하지 않습니다.
Direct DB reads outside loader, navigation regeneration/reconstruction, solver/planner/selection/ranking,
arbitrary browsing/shared playhead/normalized progress/synchronized side-by-side/autoplay/modeled animation은 금지합니다.
Historical time/cursor trajectory/speed를 만들거나 route/quality/causal 판단, frozen V1/Model C 변경,
algorithm research를 하지 않습니다. Slices 0–3 technical semantics는 frozen입니다.
2026-10-18 refresh 전 확인 branch: feature/stage3-exemplar-board-viewer;
HEAD: 2c9ba42fb394ee528a035a85c3a2c8146b86a7f9
subject: fix: prevent exemplar viewer focus-loss navigation
clean worktree / nothing staged / local origin tracking ref와 ahead 0, behind 0; fetch는 수행하지 않았습니다.
main baseline: 50a8fee544ed6779dbcd7dd2fbb422c07cce59de. 이후 live Git이 우선합니다.
이 correction commit은 current implementation candidate이며 final qualified SHA가 아닙니다.
최종 qualification은 선택된 committed SHA에서 Slice-4 verification을 수행한 뒤 판정합니다.
Admission은 73758/73024/93557/1로 고정하며 selection/ranking/substitution을 하지 않습니다.
두 accepted DB + tracked fixed identities + frozen Model C가 viewer의 필수 입력입니다.
G4/HTML은 historical provenance이며 viewer runtime 필수 입력이나 새 G4 인증 주장이 아닙니다.
독립 immutable frames와 Before/After, Terminal Engine feedback, default-OFF HIDDEN-only Answer Overlay,
one board + game/solver selector를 보존합니다. Loader와 UI 모두 COMPLETE / ACCEPTED입니다.
정적 3BV/Ops/isolated는 answer-derived board reference, 최종 Counters는 current Engine
reconstruction reference입니다. 17개 classic rows를 유지하되 Time/Est Time/3BV/s/CPS는 unavailable.
Engine public snapshot의 raw totals/completed 3BV와 get_stats의 final formatting을 재사용합니다.
추가 raw per-button/Ops seam 필요 시 별도 보고하며 private counter logic을 복제하지 않습니다.
Efficiency/IOE/Thrp/Corr 기존 수식, bounded best-so-far ZiNi의 WON/LOSS availability,
ZNE/ZNT WON-only를 보존합니다. ZiNi는 Slice 1 의존성이 아니며 navigation에서 계산하지 않습니다.
Stage2 OPEN/FLAG-only HIDDEN-target contract이므로 CHORD=0을 CHORD 거부 결정으로 해석하지 않습니다.
Model C selected/cumulative/final time 및 Modeled 3BV/s/CPS는 integer table 기반 별도 authority입니다.
selected action-target arrow/dx/dy/d²는 실제 cursor trajectory가 아니며 첫 previous target을 만들지 않습니다.
자동 route-quality/ZiNi-speed-winner 판단 없이 HUMAN domain interpretation만 지원합니다.
Discovery: 4 fingerprints 일치, 8 streams /1508 actions, status/reveal/explicit-FLAG mismatch 모두 0,
solver/planner/runner calls 없음, official artifacts 불변. 구현 acceptance로 취급하지 마세요.
NEXT는 승인된 Slice 4 Acceptance / Closeout이며 새 알고리즘 연구/구현은 별도 명시적 scope/specification 결정이 필요합니다.
현재 branch/HEAD/integration 상태는 live Git이 authoritative입니다. Closeout은 Git 작업 지시가 아닙니다.
Human Mouse Trace는 Live-board logical-pixel event samples와 독립 clock을 사용하며,
Replay v2 attachment / 선택적 표시 / 성능 hardening / 물리 입력 보정을 수용했습니다.
FLAG는 R press, OPEN은 L release, Mode-B CHORD는 현재 target의 첫 release입니다.
Source focused 627 / full 1825 PASS, fresh-env 1800 PASS + optional skips 25,
최종 package 및 사용자 native/manual 수용 PASS입니다.
후속 기능이 이미 구현됐다고 가정하지 말고 현재 source/tests로 확인하세요.
Closeout: docs/stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md.

Application/release != algorithm != physical model/profile != presentation.
Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace.
Human Mouse Trace는 실제 sampled Live-board pointer presentation data이며,
OS-global tracking, Stage-3 synthetic movement, Model C calibration evidence나 solver 입력이 아닙니다.
Presentation interval, Replay elapsed time, CPU decision time, modeled physical
time은 별개입니다. Stage3Execution은 spec / board / result이며 viewer는 solver 입력이 아닙니다.
Stage-3 설정 persistence와 registry는 없습니다.
Frozen specs/profile, official evidence와 미개봉 ZiNi holdout을 보존하세요.
F-2 packaged transport hardening은 OPTIONAL / DEFER입니다.
현재 상태·남은 gate·다음 한 단계를 짧게 정리하고 이미 확인 가능한 내용은 다시 묻지 마세요.
```

---

## 12. Handoff maintenance rule

Update this file only at meaningful boundaries, for example:

- milestone completed
- branch/baseline changed
- major design decision frozen
- new strategy/version accepted
- current next action materially changed

Do not turn this file into a full changelog or duplicate every audit artifact.
