# Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer — Closeout

**FINAL ACCEPTANCE PASS / CLOSED — 2026-10-18 (Asia/Seoul).**
**Slices 0–4 COMPLETE / ACCEPTED. BLOCKER 0 / REQUIRED 0.**
ChatGPT accepted final qualification at the exact source candidate below. This
documentation closeout records that evidence; it does not rerun verification.
Stage-3 Extended remains **ACTIVE**.

## Scope and qualified source

The [final contract](STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md) governs standalone
inspection of exactly four accepted Stage-2/Stage-3 category exemplars. This is
human/domain interpretation support, not new selection, solver execution or
algorithm adjudication.

| Identity | Value |
| --- | --- |
| Qualified branch | `feature/stage3-exemplar-board-viewer` |
| Final qualified source | `ff6358ae62b6f343bda36069d7164bda9aebee74` |
| Qualified subject | `test: preserve frozen E/L pilot source provenance` |
| Production usability commit | `29af53b15d1fff144df5873b62fcec4af91adaaa` |
| Production subject | `feat: improve exemplar viewer inspection usability` |

`ff6358a` contains only the reviewed E/L historical-source provenance repair in
`experiments/stage3_e_l_policy_pilot.py` and its test module. Viewer/application
production bytes are unchanged from `29af53b`, the user-native accepted production
tree. Qualification began and ended with HEAD equal to origin, clean worktree and
index. Later documentation commits do not replace this qualified source identity.

## Evidence lineage

All roots below are preserved ignored local evidence, not tracked repository
deliverables. No official DB copies are duplicated in the qualification root.

| Stage | Evidence root | Disposition |
| --- | --- | --- |
| First qualification at `29af53b` | `results/stage3-exemplar-board-viewer-final-acceptance/20261018T091846923796Z/` | Permanent historical **HOLD** |
| Reviewed E/L repair | `results/stage3-e-l-source-compatibility-repair/20261018T093614465991Z/` | Repair evidence; subsequently committed as `ff6358a` |
| Fresh qualification at `ff6358a` | `results/stage3-exemplar-board-viewer-final-acceptance/20261018T094900066913Z/` | **PASS / accepted by ChatGPT** |

The earlier `1f90becc5ac7b4f9196ef48221a245f09990104d` qualification is superseded
pre-usability-revision evidence. Neither it nor the first HOLD root is relabeled
as the final pass. The final [acceptance summary](../../results/stage3-exemplar-board-viewer-final-acceptance/20261018T094900066913Z/acceptance-summary.json)
links source, test, reconstruction, presentation, package, native and hygiene records.

**R-2 CLOSED:** final verification was run at the exact committed `ff6358a` source
and this record identifies that SHA, production lineage and fresh evidence root.
Earlier precommit Slice-3 checks remain historical slice evidence. R-1 was
previously satisfied at `2c9ba42fb394ee528a035a85c3a2c8146b86a7f9`; no Claude
re-audit after that correction is claimed. O-1/O-2/O-6 remain satisfied;
O-3/O-4 remain nonblocking DEFER; O-7/O-8 remain NO CHANGE. **O-5 CLOSED** by the
exact Model C presentation definition below.

## Implementation and accepted usability revision

- The accepted loader authenticates two exact immutable/read-only sources and
  one eligible run per role, decodes only selected details, authenticates board
  fingerprints/Model C and composes `project_timeline()` with `reconstruct_board()`.
- Reconstruction executes each recorded stream once and publishes N+1 immutable
  public frames, safe-reveal sets and aligned counter snapshots. The public
  `completed_ops` field is additive. `FinalCounterSummary` remains compatible;
  no Engine or live DB connection is retained.
- One board, four exemplar choices and Stage-2/Stage-3 selection retain eight
  independent inspection positions and modeled playheads. One Action ordinal
  entry commits only with Return/Enter or Go; no Frame entry remains. Direct
  slider track seek and ordinary handle drag coexist with Initial/Before/After.
- The 17 Counters describe the displayed frame: 3BV/Ops, click strings,
  Efficiency/IOE/Thrp/Corr, board ZiNi, WIN-only ZNE/ZNT and explicitly labeled
  `Time (Model C)`, `Est Time (Model C)`, `3BV/s (Model C)`, `CPS (Model C)`.
- Index playback accepts 20..5000 ms/action, default 200; minimum displays
  `Max (20 ms)`. Committed out-of-range text clamps. Compact native-style/font
  sizing fits both Max and 5000 ms labels without a generic sizeHint width floor.
- Model C Time playback uses exact integer microseconds with 0.25x..8x speed.
  The approximately 16 ms presentation refresh is neither Index interval
  authority nor Model C timing authority. Pause/resume preserves partial motion;
  late ticks catch up without changing the recorded stream.
- The synthetic action-target cursor uses straight rendered cell-center geometry
  and `q = u^2(3 - 2u)` smoothstep. Same-target actions stay stationary. It is
  synthetic presentation, not recorded mouse/OS trajectory or calibrated
  acceleration; Model C costs are unchanged. Partial motion updates overlays,
  slider/status only, without board/counter recomputation.
- The cumulative **Action-target route — not recorded cursor trajectory** is
  default OFF and uses `actions[:displayed_frame]`. BEFORE excludes the pending
  action from that route while permitting its separate inspection preview.
  Repeated targets remain; no initial-cursor-to-first-target route is fabricated.
  Final route style: main alpha **165**, width **2.0**; white under-stroke alpha
  **100**, width **3.5**, below selected context and the synthetic cursor.
- Answer Overlay remains default OFF, renderer-only, HIDDEN-only, approximately
  0.35 opacity, with blank zero cells. Actual terminal Engine feedback is retained.
- Reference/Counters/Model C/Action fact tabs avoid the former tall desktop
  sidebar; Expert desktop fit and 800x600/640x480 scroll fallback passed.
- PyQt-independent `ZiniMetricJob` owns the shared Counter config and subprocess
  lifecycle; the worker owns calculation. The Viewer owns one active board job,
  fingerprint-keyed successful-result cache and presentation. Same-board solver
  switches reuse the job/result; navigation/playback/toggles never restart it.
  Main UI retains its own live/replay eligibility and Explorer policy.

ZiNi uses `standard_seeded_chain_v1`, maximum 1000 evaluations, standard phase
500, seed 0, no elapsed/stall cutoff: **bounded best-so-far, not exact/optimal**.
Pending/failure values remain `-`. Available ZiNi is board-constant for either
outcome; ZNE/ZNT use displayed total/active clicks only for a recorded WIN, with
zero denominators unavailable. No tracked JSON/precomputed exemplar ZiNi exists.

## Model C and Counter authority

**displayed Model C seconds = integer microseconds / 1,000,000**.
Integer microseconds remain authority; exact quotient/remainder seconds rendering
is presentation, not binary-floating timing authority. Counter summaries use
three decimal seconds; detailed time fields retain exact us and six-decimal seconds.

Selected action cost follows the inspected action. Cumulative time and Counter
time follow the last completed displayed frame. A continuous playback playhead
may be between completions without changing that frame or its Counters. Final
run cost/rates remain full-stream facts regardless of navigation.

For prefix cost `C` us, completed 3BV `B`, total board 3BV `T`, completed actions
`K`: current modeled rates are `B*1000000/C` and `K*1000000/C`; estimated seconds
are `T*C/(B*1000000)`. Zero `C` masks rates/estimate; zero `B` masks estimate.
WIN final estimate reconciles with final modeled time. LOSS final cost is
**through termination**; its estimate is prefix extrapolation, not observed
gameplay time, predicted solver finish or time-to-win. Reconstruction elapsed
time and decision-compute diagnostics never become playback/time authority.

## Real four-board / eight-stream acceptance

One actual loader invocation produced **2 immutable/read-only SQLite opens**,
four generated boards, eight selected streams/timelines/reconstructions and
**1,508 freshly counted actions**. Exactly one admitted COMPLETED, official-eligible
run per source had requested/processed/stored = 100000/100000/100000 and exact
`[0,100000)` coverage. No `run_id=1` assumption was used.

| Game | Deterministic category | 3BV | Ops | Isolated |
| ---: | --- | ---: | ---: | ---: |
| 73758 | Maximum Stage-3 WW advantage | 172 | 16 | 156 |
| 73024 | Lower-median WW delta exemplar | 177 | 13 | 164 |
| 93557 | Closest-to-zero Stage-3 WW advantage | 140 | 14 | 126 |
| 1 | LL exemplar | 175 | 12 | 163 |

These are deterministic category exemplars, **not a statistically representative
sample**. All generated/persisted/fixed fingerprints matched the contract.
Fingerprint, action order/type/target, status, safe-reveal, explicit-FLAG,
terminal and result mismatch counts were each **0**; counter and Model C
mismatches were also **0**. N+1 immutable frames/counters, final public counters,
terminal-final-event and exact per-action/cumulative/total costs reconciled.
Automatic WIN flags were not counted as explicit FLAG inputs.

| Game | S2 / S3 actions | Outcomes | S2 / S3 Model C us |
| ---: | --- | --- | --- |
| 73758 | 320 / 177 | WIN / WIN | 57365067 / 30355982 |
| 73024 | 313 / 207 | WIN / WIN | 53655374 / 37168019 |
| 93557 | 279 / 204 | WIN / WIN | 47034727 / 39157214 |
| 1 | 4 / 4 | LOSS / LOSS | 720354 / 720354; through termination |

The final root retains the full eight-run counter/model table. Real-bundle
offscreen guards observed no navigation/playback DB reopening, board generation,
Engine replay, reconstruction, timeline projection, Model C authentication,
solver/planner/selection or frame-driven ZiNi lifecycle work. UI lifecycle probes
used explicit fake ZiNi receipts; no real Expert ZiNi values are claimed by them.
Shared-job source/package tests separately exercised real bounded tiny boards.

## Fresh committed-candidate tests

Environment: **Python 3.12.10, 64-bit Windows AMD64, PyQt 5.15.11, Qt 5.15.2**.
Approved interpreter: `C:\venvs\minesweeper\Scripts\python.exe`; `-B`,
`PYTHONDONTWRITEBYTECODE=1`, `QT_QPA_PLATFORM=offscreen` where applicable.

| Suite | Discovered / PASS | Failures / errors / skips | Unittest / process seconds |
| --- | --- | --- | --- |
| 29 complete focused/frozen modules | 892 / 892 | 0 / 0 / 0 | 33.912 / 34.736 |
| Full development source suite | 2390 / 2390 | 0 / 0 / 0 | 150.087 / 152.087 |

Full command: `C:\venvs\minesweeper\Scripts\python.exe -B -m unittest discover -s tests -v`.
The root's `test-manifest.txt`, `focused-tests.txt`, `focused-result.json`,
`full-tests.txt` and `full-result.json` retain exact commands/modules/results.
Main/Replay/Explorer checks covered retained live Engine identity, replay-owned
Engine, prefix/completed/incomplete statistics, snapshot ownership, lazy trace
construction, stale job/window invalidation and cleanup. No source tests ran
during this documentation closeout.

## Package / build regression

The package gate was required because `29af53b` also changed main/shared-worker
infrastructure. A fresh isolated environment and the current tracked BUILDING
workflow produced an onedir/windowed package in **77.012 s**.

Build-environment prerequisite: **2365 PASS / 25 documented optional image/video
dependency skips / 0 failures / 0 errors**. Missing optional `cv2`/`av` skips
are individually listed in `build-skip-disposition.json` under BUILDING's explicit
allowance; they are not PASS. The development full suite had **0 skips**.

EXE SHA-256: `8f64ca07d6b86cb03839e3b6f7f86b4b1510adabc901292a921f1a8c872d7530`.
AMD64 / PE32+, GUI subsystem, required workers/Qt resources and exact frozen
profile bytes were verified. Normal packaged startup/close exited **0**.
Packaged ZiNi success/error/arity/dispatch, one-result delivery, token and cleanup
checks passed, as did the prescribed bounded Stage-3 worker/source comparison.
That bounded regression was not official benchmark evidence generation.
No dedicated packaged Exemplar Viewer launcher is claimed.

## User-native source-GUI acceptance

**PROJECT USER** tested the exact production tree subsequently committed as
`29af53b`: A–F, P1 Index, P2 Model C Time, route/max interval, V1 route/interval,
V2 Index synthetic smooth cursor, V3 Model C synthetic smooth cursor, and final
interval/route micro-polish all passed. User statement:

> 내 기준을 완전히 충족했어.

`ff6358a` changes only experimental provenance/tests, so this production native
acceptance remains applicable. This is **user-performed native source-GUI**
evidence, not Codex-native Viewer acceptance or packaged Viewer-native acceptance.
Codex's separate packaged main-app startup/close smoke has only that bounded scope.

## E/L HOLD → repair → PASS

The first qualification at `29af53b` remained HOLD because historical E/L pilot
preflight required current `core_engine.py` to match its historical source bytes.

| LF-normalized Engine identity | SHA-256 |
| --- | --- |
| Historical frozen pilot | `1a6ad25ef80ca30c3bb0ecbe80fd5ca7e09b60e1ae086e5c65de3703dea52e08` |
| Explicit compatible current source | `8a624ef322ca8fc2a9b3ec39774263eaaa310a4fc85c4252f7c4391d0369249d` |

The sole addition was the reviewed observational public field
`"completed_ops": self._effective_ops,`. The repair retained the old hash,
allowed only the exact compatible Engine hash, rejected unknown future drift,
separated historical/compatible/actual manifest identities, and proved the
whole-file inverse delta. It did not change application/algorithm behavior.
Precommit repair verification: **28/28 E/L, 335/335 semantic/golden, 2390/2390
full suite PASS**. Final qualification then restarted freshly at `ff6358a`.
The historical 10k pilot was **not rerun or relabeled**; its original provenance
and the failed qualification root remain intact.

## Preservation

| Preserved authority | SHA-256 |
| --- | --- |
| Stage-2 accepted DB | `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` |
| Stage-3 accepted DB | `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e` |
| Model C profile | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` |
| Model C integer timing table | `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b` |
| G4 comparison | `f31226a660eda02a804ee41c66f233513fd950cac6f6123f36bf62578fbf5979` |
| G4 result | `09f228ee9a8ec96a934dbb94656a7cd6f03c7987640df267f5fd6818dd007cc0` |

DB bytes/sizes/mtimes were unchanged before/after, with no WAL/SHM/journal.
Known Model C values remained 126005, 126005, 144891, 559131, 559226 for
T[0][0], T[1][0], T[1][1], T[29][0], T[29][1]. No refit/regeneration occurred.
Both Timeline reports remain unchanged: final `20261017T113748060625Z-99dafa139703`
SHA `b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3`, historical
`20261017T103913620889Z-54082dd14870` SHA
`277e6889d9ade1c944eabebeeec7fcca0a4524e496af449cd9b60e73676d6203` under
`results/stage3-timeline-analytics/`, each `report.html`.
G4/HTML are preservation/provenance artifacts, not Viewer runtime inputs.

Final qualification left clean Git, no staged/generated tracked files, no orphan
worker/private ZiNi job directory, and preserved historical evidence. Isolated
build outputs/environment remain under the documented build policy.
ZiNi final quality holdout **2,010,000 .. 2,010,099** remains unopened:
**final holdout accessed = NO**.

## Limitations and mandatory next work

No arbitrary browsing, re-selection, official 100k rerun, new solver policy,
probability/plan reconstruction, common synchronized playhead or automatic
route/quality/causal/speed-winner judgment is established. Stage-3 V1 / Model C
and ZiNi Improvement remain CLOSED/FROZEN; Extended itself is not closed.

**Visualization Usability Polish — QUEUED / MUST COMPLETE BEFORE ALGORITHM RESEARCH.**
This is follow-up maintenance on closed surfaces, not invalidation of their
historical acceptance:

- **Same-board Comparison:** direct logical-index track seek; selected-run
  playback only; Human Index + actual Replay Time, Stage2/Stage3 Index + Model C
  Time; 0.25x..8x speed; Index 20..5000 ms, default 200, `Max (20 ms)`;
  cumulative action-target route and the accepted synthetic smooth cursor.
  Keep actual Human Mouse Trace separate. **No common synchronized Human/S2/S3
  clock or playhead.**
- **Stage-3 Visualizer:** cumulative recorded action-target route through the
  current completed step, future targets hidden by default; retain its **existing
  direct slider seek** and selected-segment/synthetic-cursor distinctions.

After that polish, human/domain interpretation of the fixed exemplars precedes
a separate decision/specification for actual Extended algorithm research.
Nearest exact-minimum-risk guessing with movement cost remains a backlog
candidate, not an adopted policy. This closeout implements none of that queued work.

## Final verdict

**FINAL ACCEPTANCE PASS —**
**SELECTED EXEMPLAR BOARD-STATE RECONSTRUCTION /**
**HUMAN INTERPRETATION VIEWER CLOSED**

**SLICES 0–4 COMPLETE / ACCEPTED**

**BLOCKER 0 / REQUIRED 0**
