# Visualization Usability Polish — Closeout

**FINAL ACCEPTANCE PASS / CLOSED — 2026-10-18 (Asia/Seoul).**
**Same-board Comparison usability ACCEPTED; Stage-3 Visualizer reference overlays ACCEPTED.**
**BLOCKER 0 / REQUIRED 0.** Technical qualification passed, the project user
accepted the source GUI, and ChatGPT final review accepted this closeout on
2026-10-18. Stage-3 Extended remains **ACTIVE**.

## Scope and qualified implementation

This milestone adds selected-run timed presentation to Same-board Comparison
and explicit reference overlays to both Comparison and the Stage-3 Visualizer.
It preserves the closed execution, algorithm, physical-model and evidence boundaries.

| Identity | Value |
| --- | --- |
| Branch | `feature/stage3-visualization-usability-polish` |
| Qualified implementation SHA | `31630dd6ffa2301c41534fca3b003838d865f313` |
| Subject | `feat: add visualizer reference overlays` |
| Same-board usability commit | `866ea28f12ef039f243efee8d10030cbc4fe3d8e` |
| Timed foundation commit | `a33c504b245d4b9cf70d20851fa2cdef06cc53f9` |
| Pre-polish documentation baseline | `c13782afb63c1f3386aab454c133f8a8cb7ad503` |
| Qualified Viewer ancestor | `ff6358ae62b6f343bda36069d7164bda9aebee74` |
| Merge-base with main at qualification | `50a8fee544ed6779dbcd7dd2fbb422c07cce59de` |

Live HEAD equaled `origin/feature/stage3-visualization-usability-polish`, with
clean worktree/index and 13 commits ahead of main. All required ancestors were
verified. Tests and package were built before documentation edits. The later
documentation commit must not replace this qualified implementation identity.

The implementation delta from `c13782a` contains only four production files
(`same_board_timed_playback.py`, `same_board_comparison_ui.py`,
`visualization_reference_overlays.py`, `stage3_visualizer_ui.py`) and their four
test modules. This final task changed documentation only; no source/test repair
was needed or authorized, and nothing was staged/committed/pushed.

## Evidence hierarchy and location

Current committed source and tests define behavior. Fresh automated source and
package evidence establish the bounded qualification below; **USER source-GUI**
acceptance establishes the reported native feature checks. Historical closeouts
retain their original acceptance scope and dates.

Fresh ignored root:
`results/stage3-visualization-usability-polish-final-acceptance/20261018T1306330178987Z/`.
The [acceptance summary](../../results/stage3-visualization-usability-polish-final-acceptance/20261018T1306330178987Z/acceptance-summary.json)
links `git-identity.txt`, `environment.txt`, `source-inventory.json`, complete
test logs/results, package build/module/worker/startup records, preservation,
user-native attribution and hygiene. No official DB was copied into this root.

## Same-board accepted presentation contract

- Three independent timed controllers preserve Human, Stage 2 and Stage 3
  presentation states. Only the selected run advances. `SameBoardPlayback`
  remains the committed-index/board authority: index k means k completed inputs.
  There is **no common synchronized Human/S2/S3 clock, playhead or normalized progress**.
- Human offers **Index + Replay Time**, using the original ordered
  `ReplayEvent.elapsed_time` values, represented exactly as stored. Stage 2/3
  offer **Index + Model C Time**. Stage-2 prefixes are projected once from retained
  targets and the already-authenticated table, reconciled to the retained total.
  Stage-3 prefixes use recorded action microseconds and reconcile to its total.
  There is no timing-table lookup or Model C reauthentication per tick.
- Index interval is **20..5000 ms/action**, default **200**; 20 displays
  **Max (20 ms)**. Committed out-of-range text clamps. Native-style/font sizing
  fits Max and 5000 labels. Time speed is the exact quarter-step range
  **0.25x..8x**. Interval/speed changes preserve partial progress through re-anchoring.
- Direct logical-index track seek retains normal handle dragging. Manual
  navigation stops playback and aligns to the actual committed index; errors
  cannot publish a false timed position. Run switching pauses the old run.
- The green/hollow synthetic action-target cursor uses straight rendered
  cell-center geometry and smoothstep `q = u^2(3 - 2u)`. The roughly 16 ms refresh
  requests presentation only, not guaranteed FPS or timing authority. Same-target
  segments remain stationary. Pause/resume preserves partial motion; late ticks
  catch up boundaries and refresh the resulting board once. Close stops motion.
- Human has no authoritative pre-first-action pointer origin: its first
  synthetic anchor is the first action target and stays there during any initial
  Replay-Time delay. It never borrows a Mouse Trace sample or Model C origin.
  Solver synthetic origins remain their retained Model C initial cursor.
- Actual **Human Mouse Trace** remains an independent overlay of the **entire
  recorded attachment**, available only for Human. It is not prefix-limited or
  replaced by the action-target route or synthetic cursor.
- **Show hidden answers** and **Show action-target route** default OFF. Answers
  derive once from `execution.context.layout.board`. Only currently public
  HIDDEN cells receive faint mine/nonzero-clue references; zero stays blank.
  Public flags, revealed/terminal glyphs, text, tooltips and accessibility remain
  authoritative. Truth is presentation/reference data, never decision input.
- The route is exactly `targets[:k]`: completed recorded targets, repeated points
  retained, no future/pending target and no fabricated initial-cursor segment.
  A partial synthetic traversal does not commit the pending action or extend the route.
- Toggles are independent and do not navigate or stop playback. Desktop Expert
  presentation and reachable 800x600 / 640x480 scroll fallback were checked.

Partial-only refresh and reference toggles do no Engine, solver, planner,
probability, generation, execution, worker or Model C work. Ordinary committed
navigation may reconstruct through the **existing** SameBoardPlayback Engine path;
this closeout does not claim all navigation is Engine-free.

## Stage-3 Visualizer accepted presentation contract

The two new default-OFF controls are **Show hidden answers** and
**Show action-target route**. Immutable answer clues derive once from retained
`Stage3Execution.board.mine_positions` and spec dimensions. The public HIDDEN
mask controls decoration; no terminal or visible state is overwritten.
The route uses only executed native trace targets through the current committed
step. Pending targets stay excluded during modeled partial motion; planned
suffixes are never a route source. Selected segment, route and synthetic cursor
remain distinct.

Existing direct track seek, native handle drag, First/Previous/Next/Last, Index
interval range/default and Index playback are preserved. **No Index smooth
interpolation was added.** Existing Model C playback, modeled smooth cursor,
approximately 16 ms modeled presentation refresh, pause/resume and the six
speeds **0.25x, 0.5x, 1x, 2x, 4x, 8x** remain unchanged. Stage3TracePlayer and
Stage3ModeledPlayback retain ownership and source identity.

Toggles do not navigate, alter playhead or stop playback. Partial modeled
presentation leaves the public board, answer mask and route at the committed
prefix. It adds no board refresh, Engine step/reset, solver/planner/probability,
generation, worker, Model C authentication/refit or action-cost recomputation.
Finalized answer truth never enters planner input, admissibility or executed choice.

## Neutral helper and visual separation

`visualization_reference_overlays.py` owns only immutable clue derivation from
caller-supplied fixed truth, hidden-answer painting from the caller's public
HIDDEN mask, and route painting from supplied points. It owns no truth acquisition,
prefix selection, playback, clock, Engine, solver/planner, Model C or job lifecycle.
Both UIs depend on this small painter module; neither imports the other feature UI.

Layering is public board → answer reference → completed route → actual Human
Mouse Trace where available → selected context → synthetic cursor. Overlays
are mouse-transparent. Answer opacity is 0.35. The purple route has alpha **165**,
width **2.0**, and a white under-stroke alpha **100**, width **3.5**.
The route means **action-target route — not recorded cursor trajectory**.

## Fresh source qualification

Environment: **Python 3.12.10, 64-bit Windows AMD64, PyQt 5.15.11, Qt 5.15.2**.
Interpreter `C:\venvs\minesweeper\Scripts\python.exe -B`, with
`PYTHONDONTWRITEBYTECODE=1` and `QT_QPA_PLATFORM=offscreen`.

| Suite | Discovered | PASS | Failures / errors / skips | Unittest / process seconds |
| --- | ---: | ---: | --- | --- |
| Full development discovery | 2484 | 2484 | 0 / 0 / 0 | 141.629 / 144.042 |
| 13 complete focused modules | 453 | 453 | 0 / 0 / 0 | 20.236 / 21.211 |

Full command: `C:\venvs\minesweeper\Scripts\python.exe -B -m unittest discover -s tests -v`.
Focused command uses the same interpreter with `-m unittest -v` and all modules:

```text
tests.test_same_board_timed_playback tests.test_same_board_playback
tests.test_same_board_comparison tests.test_same_board_comparison_ui
tests.test_same_board_comparison_launcher tests.test_same_board_main_ui
tests.test_mouse_trace_overlay tests.test_mouse_trace_ui
tests.test_visualization_reference_overlays tests.test_stage3_visualizer_ui
tests.test_stage3_modeled_playback tests.test_stage3_trace_player
tests.test_stage3_visualizer_launcher
```

These cover exact timeline authority, independent run state, direct seek/drag,
clamping/font fit, partial pause/re-anchor/catch-up, prefix-only routes,
HIDDEN-only references, trace separation, layering, lifecycle/layout and guarded
partial refresh. Full discovery also reconfirmed frozen/model and ordinary app
regressions. No unexpected skip or source/test failure was waived.

## Bounded package regression

The new statically imported helper and changed Qt surfaces required this gate.
Current [BUILDING.md](../../BUILDING.md) explicitly requires a fresh ASCII-path
environment for acceptance, so its pinned Windows x64 PyInstaller procedure was
used with isolated dist/work/spec/cache. Environment:
`C:\Users\User\AppData\Local\Temp\minesweeper-release-build-20261018T1306330178987Z`.
Pinned dependencies and full `pip freeze` are retained in the evidence root.

Build prerequisite: **2484 discovered / 2459 PASS / 25 documented optional
image/video dependency skips / 0 failures / 0 errors**; unittest **126.544 s**,
process **128.920 s**. The 25 individual skip identities/reasons match the
established BUILDING allowance and are recorded in `build-skip-disposition.json`.
They are not PASS. Development source discovery had **zero skips**.

Build used that environment's Python with:

```text
-B -m PyInstaller --noconfirm --clean --onedir --windowed --name Minesweeper
--distpath <acceptance-root>/dist --workpath <acceptance-root>/build
--specpath <acceptance-root>
--add-data "<absolute-repository>/calibration/stage3_physical_profile_v1.json;calibration" main.py
```

Exact expanded command is in `package-build-proof.txt` / `pyinstaller-build-result.json`.
**Build exit 0; 59.085 s.** Executable:
`<acceptance-root>/dist/Minesweeper/Minesweeper.exe`, **6,275,065 bytes**.
SHA-256: `26cfb55bbbe75bad29bb0461bf39eed6a2b3b203512b9144751dcd770530a08f`.
Verified **AMD64 / PE32+ / GUI subsystem**; Qt Windows plugin, required worker/UI
modules, neutral helper and exact frozen profile bytes are present. Archive
extraction and native main-window startup produced no required import failure.
PyInstaller optional/platform warnings are preserved, not described as zero warnings.

All **12 packaged worker/job cases PASS**: known small-board ZiNi success and
error/arity dispatch; prescribed bounded Stage-3 game-0 deterministic source
comparison and invalid-index/arity dispatch; Same-board safe/mined fixed-board
source equivalence and invalid-request/board/arity envelopes; real frozen shared
ZiNi job one-result delivery and cleanup. Runtime compute diagnostics and Stage-2
Replay elapsed clocks were excluded from deterministic equality, not rewritten.
All owned children were reaped and private payload/result directories removed.
These small package regressions are not new official benchmark evidence.

Codex observed the normal packaged main window and closed it through normal
Alt+F4; **exit 0**, process reaped. This is bounded startup/close smoke only.
No dedicated Same-board/Visualizer EXE launcher, release/tag/ZIP, or packaged
feature-native acceptance is claimed. Existing release-wide manual procedures
are not relabeled as newly performed by this maintenance gate.

## User-native acceptance

**The PROJECT USER reported source-GUI acceptance**, separately from Codex's
automated/offscreen and bounded packaged-startup checks:

- **Same-board A–M: ALL PASS** — seek/drag; Human Index/Replay Time; Stage-2/3
  Index/Model C Time; 20/200/5000 ms and Max; 0.25/0.75/1/8x; partial pause/resume
  and manual cancellation; entire actual Human trace versus route versus
  synthetic cursor; answers; completed route; desktop/800x600/640x480; close/reopen.
- **Visualizer V-A through V-I: ALL PASS** — existing seek/drag, Index, modeled
  six-speed playback/cursor; answers/route; no pending point before commit;
  readable combined layers; authoritative terminal feedback; both toggles OFF
  on reopen.

These are user source-GUI facts, **not Codex-native feature acceptance and not
packaged-EXE feature acceptance**. The attribution is retained in
`user-native-evidence.json`.

## Preservation and limitations

Live Git blob comparisons confirm unchanged Stage-3 V1 planner/runner policy,
Model C owner/profile, execution workers, committed playback models, Replay schema,
Mouse Trace implementation, ZiNi algorithms and accepted Exemplar Viewer source.
No common comparative clock or Visualizer Index interpolation was introduced.

Read-only byte/stat preservation checks matched the prior accepted evidence
identities, sizes and mtimes; **no SQLite connection was opened**, no sidecars
appeared, and no official DB proof/selection/100k benchmark was regenerated.

| Preserved artifact | SHA-256 |
| --- | --- |
| Stage-2 DB | `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` |
| Stage-3 DB | `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e` |
| Model C profile | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` |
| Frozen timing table, authenticated by source regression | `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b` |
| G4 comparison | `f31226a660eda02a804ee41c66f233513fd950cac6f6123f36bf62578fbf5979` |
| G4 result | `09f228ee9a8ec96a934dbb94656a7cd6f03c7987640df267f5fd6818dd007cc0` |

Both accepted Timeline reports retain their hashes/mtimes in `preservation.json`.
Historical failed Viewer qualification and E/L repair evidence were not altered.
The ZiNi final holdout **2,010,000 .. 2,010,099** remains unopened:
**final holdout accessed = NO**.

Replay Time != Model C Time != presentation refresh time != decision compute
time != human physical mouse trajectory. Smoothstep is not calibrated
acceleration; the synthetic route/cursor is not recorded OS motion. Nothing here
establishes Human/CPU speed improvement, algorithm superiority, route optimality
or hidden-truth influence on solver decisions. Existing committed seek may
reconstruct; no universal Engine-free playback or fixed-FPS claim is made.

## Roadmap after this milestone

The eight Extended milestones through Visualization Usability Polish are CLOSED;
the [current roadmap](README.md#roadmap) preserves each historical closeout.
The Viewer closeout's then-queued polish remains truthful historical provenance.
No frozen milestone is reopened and Stage-3 Extended itself is not globally closed.

**NEXT, in a NEW ChatGPT/Codex work unit:** fixed-exemplar human/domain
interpretation. Only afterward comes a separate algorithm-research
direction/specification decision; actual research/implementation requires that
decision and authorization. No interpretation or algorithm research began here.
Nearest exact-minimum-risk guessing using movement cost remains a backlog
candidate, not an adopted policy. Existing optional Foundation F-2 and unrelated
deferred optimizations are not promoted to new closeout requirements.

## Final verdict

**FINAL ACCEPTANCE PASS —**
**VISUALIZATION USABILITY POLISH CLOSED**

**SAME-BOARD COMPARISON USABILITY — ACCEPTED**
**STAGE-3 VISUALIZER REFERENCE OVERLAYS — ACCEPTED**

**BLOCKER 0 / REQUIRED 0**
