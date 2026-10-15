# Human Mouse Trace / Path Visualization — Closeout

Date: **2026-10-16 (Asia/Seoul)**. Status: **FINAL ACCEPTANCE PASS / CLOSED**.
Stage-3 Extended remains **ACTIVE**. Next: **Same-board Human / Stage-2 / Stage-3
Comparison**, not yet implemented.

## Qualified implementation and evidence

Implementation/package SHA: **`e32145fa5c114e1ce500ad2e837ef6000cc49cca`**.
Before this documentation-only preparation, live Git verified clean `main`,
HEAD == `origin/main` == live remote main, with no remaining Human Mouse Trace /
physical gesture feature branches. Documentation branch:
`docs/human-mouse-trace-closeout`. These are dated identities, not a latest-HEAD claim.

Final technical evidence:
`results/human-mouse-trace-final-acceptance/20261016-003839/acceptance-summary.json`.
That preserved summary ends at **READY FOR USER CHECK**; the project user's later
final native/manual PASS closes the milestone here. The JSON is not rewritten.

The earlier `results/human-mouse-trace-final-acceptance/20261015-215537/` is valid
historical post-performance-hardening evidence at
`6fe61866681612060bbb3d57940c726de4f224b3`. It is not the final candidate because
physical gesture semantics changed afterward. Both artifact roots are preserved.

## Accepted feature and recording contract

Human Mouse Trace is actual sampled Live-board pointer **presentation data** in
board-local Qt logical-pixel coordinates. Event-driven accepted samples retain
exact subpixel positions; there is no timer sampling, min-distance filtering or
semantic point dropping. Only consecutive identical non-action positions within
a segment deduplicate; action samples and continuity breaks remain represented.
An independent monotonic clock supplies trace elapsed µs. Discontinuities break
segments instead of drawing fabricated continuity.

Recording defaults **ON per application/session** and is editable only before
the first committed timed human OPEN/FLAG. First OPEN observes physical **L release**;
first FLAG/UNFLAG observes **R press**. The observation is obtained before synchronous
engine/ZiNi/Replay processing and, after successful Replay append, anchors trace
elapsed time at **0 µs**. Untimed pre-start CHORD never starts trace. Mode-A CHORD
uses L release; Mode-B CHORD uses the first release consuming the overlap.

Recording OFF locks and invalidates the trace at the first committed timed human
OPEN/FLAG. A committed Auto action invalidates Human eligibility; merely enabling
Auto does not. Replay append failure after a committed human action invalidates
the trace. Marker semantics come from the actual **ReplayEvent index**, not a new
action type or independent interpretation of clicks.

The separate Mouse Trace model can be carried by **Replay schema v2**; v1 remains
readable and trace-free. Display is optional on the completed Live board or in
Replay, whose seeks retain the whole attachment. Physical gesture correction
did not change ReplayEvent or the v2/MouseTraceData schemas.

## Physical Mouse Gesture Fidelity

Core Engine still receives semantic **OPEN / FLAG / CHORD** and owns game rules
and active/wasted accounting. Physical button policy belongs to the UI.

| Mode | Accepted physical behavior |
| --- | --- |
| A | R press immediately FLAGs/UNFLAGs at the press target; R release adds no FLAG. L release selects OPEN or revealed-number CHORD. R actions remain independent during L hold, and R hold does not disable L-release CHORD. |
| B | Standalone R press immediately FLAGs/UNFLAGs. R joining held L suppresses FLAG and arms BOTH; L joining held R arms BOTH without undoing the earlier FLAG. Origins need not match. |
| C | Same immediate R-press FLAG and inert R release as A, normal hidden L-release OPEN, no CHORD from revealed targets or overlap. |

Mode B's first release of either button consumes one overlap and attempts CHORD
at the **current release target**. An outside-board release also consumes it.
The trailing release adds no action; a new press of the missing button re-arms
while the other remains held. Ordinary L-held preview remains. BOTH preview follows
the current HIDDEN/FLAGGED/revealed target; a FLAGGED center stays visibly flagged
and undepressed while surrounding hidden cells depress. Mode A/C do not open a
cell newly flagged during the same L hold. Reset/rebuild/Replay and other stale-input
safeguards remain in place. See the [architecture contract](../../ARCHITECTURE.md#physical-mouse-input).

## Performance hardening

- Primitive private recorder storage avoids retaining GC-heavy public point objects.
- Irrelevant pre-start movement/press processing stays gated; a candidate first
  FLAG press obtains its required exact observation. Suppressed Mode-B R press
  does not need that pre-start trace observation.
- Overlay caches transformed geometry and a bounded raster with a **16 MiB** budget.
  Oversized rendering uses a bounded visible region or direct cached-geometry fallback.
- No semantics-changing sampling or throttling was introduced.

Native user testing accepted trace ON after hardening. Final packaged user
acceptance found no noticeable Mouse Trace performance regression. These are
qualitative acceptance findings, not zero-overhead or new benchmark claims.

## Automated and fresh-package acceptance

Development interpreter: `C:\venvs\minesweeper\Scripts\python.exe`, Python 3.12.10 x64,
with `PYTHONDONTWRITEBYTECODE=1`. Counts below belong to the qualified implementation;
the documentation-only closeout does not rerun or relabel them.

| Run | Discovered/run | Passed | Failures | Errors | Skips | Duration | Exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Source focused | 627 | 627 | 0 | 0 | 0 | 34.406 s | 0 |
| Source full discovery | 1825 | 1825 | 0 | 0 | 0 | 123.151 s | 0 |
| Fresh build environment full | 1825 | 1800 | 0 | 0 | 25 | 105.578 s | 0 |

Focused coverage includes physical input **59**, Mouse Trace recorder/UI/overlay
**27/68/13**, Replay, Live Auto, engine, ZiNi dispatch and Stage-3 execution/UI.
Fresh-environment skips are the same 25 optional image/video replay-validation
tests as historical acceptance, not omitted app/GUI coverage.

New ASCII-path environment and isolated build/dist/cache used Python **3.12.10 x64**,
pip **25.0.1**, PyInstaller **6.22.3**, PyQt5 **5.15.11**, PyQt5-Qt5 **5.15.2**,
PyQt5-sip **12.19.0**, pyqtgraph **0.14.0**, numpy **2.5.3**, colorama **0.4.6**.
Build exit **0**, **60.658 s**; Windows **AMD64 / PE32+ / GUI subsystem 2**, onedir/windowed.
The accepted EXE is `dist/Minesweeper/Minesweeper.exe` beneath the final root.

| Identity | SHA-256 |
| --- | --- |
| Final EXE | `d73e25b4f21306a951ddf3e90727b337f42a2a04a4678d19d0b7f8f6eb00c787` |
| Frozen raw physical-profile file, source and bundle | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` |
| Frozen canonical timing table | `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b` |

Qt `qwindows.dll`, normal GUI imports, both workers and frozen runtime profile were
present. Nineteen packaged modules matched current source compiled semantics.
Packaged ZiNi and Stage-3 workers passed valid-result, wrong-arity and controlled-error
checks from unrelated working directories without Qt startup. Stage-3 game 0 was
WON, 227 traces, 39,987,084 modeled µs. Worker ownership/reaping/temporary cleanup passed.

Automated native Windows smoke passed startup, board placement, completed game /
ZiNi result, current-game Replay, Stage-3 launcher execution and viewer startup.
A generated Replay v2 with trace was loaded, displayed, sought 0 → 4 → 0 and saved;
saved JSON exactly equaled the fixture. Normal application close exited 0 with
empty stderr, no worker orphans and empty owned temporary storage.
Exact commands, versions, logs, package manifest and warnings remain under the final
acceptance root; [BUILDING.md](../../BUILDING.md) describes the current procedure.

## Final user native acceptance — PASS

Tester: **project user**, final packaged EXE above, reported **2026-10-16**.
This is the user's final acceptance report, separate from automated smoke:

- Normal FLAG/UNFLAG feels correct.
- Mode A physical behavior and Mode B L→R behavior are correct.
- Mode B R→L flagged-center preview is correct.
- First-release CHORD and repeated held-button CHORD cycles are correct.
- Mode C behavior is correct.
- Human Mouse Trace recording/display and Replay with trace are correct.
- Stage-3 Visualizer still works.
- No noticeable Mouse Trace performance regression.

No additional manual scenarios or quantitative performance measurements are claimed.

## Optional limitations and boundaries

**BLOCKER: none. REQUIRED acceptance: passed. OPTIONAL / DEFER:**

- Fresh build environment omits optional image/video validation dependencies;
  its 25 skips are explicit. Unused `pyqtgraph.opengl`/OpenGL build warning and
  missing-module names match historical acceptance; required runtime modules are present.
- Automated native smoke did not separately verify pending-job Cancel/reset or
  Stage-3 viewer playback seek. Cancellation/shutdown used the owner harness driving
  the actual packaged worker; the user's broader statement is only as recorded above.
- Existing Foundation F-2 windowed transport-exception hardening remains deferred.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
No OS-global tracking, Model C calibration/refit, solver decision input, reuse of
synthetic Stage-3 motion as Human data, advanced path analytics or new algorithm
research is accepted here. Stage-3 synthetic cursor remains presentation only.
Frozen Stage-3 V1 specs/profile/table, official 100k results, closed ZiNi policy and
its unopened final holdout retain their identities and interpretation.

Next milestone: **Same-board Human / Stage-2 / Stage-3 Comparison**. Later:
representative-board demonstrations / Timeline Analytics, then first actual Extended
algorithm research. See the [roadmap](README.md) and [current handoff](../CURRENT_HANDOFF.md).
This documentation closeout changes no production Python, tests, frozen specifications
or historical artifacts and creates no release, tag or application version.
The documentation commit does not replace or relabel the qualified implementation/package
SHA `e32145fa5c114e1ce500ad2e837ef6000cc49cca`.

**HUMAN MOUSE TRACE / PATH VISUALIZATION — FINAL ACCEPTANCE PASS / CLOSED**
