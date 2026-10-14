# Stage-3 Visualizer Foundation Acceptance

## Verdict and scope

**STAGE-3 EXTENDED VISUALIZER FOUNDATION — FINAL ADJUDICATION PASS / CLOSED**

Milestone: **Stage-3 Extended — Execution / Playback / Visualizer Foundation**.
Automated and packaged manual acceptance date: **2026-10-14 (Asia/Seoul)**.
**Manual tester: project user**, who supplied the completed packaged acceptance
report directly in this chat. The manual observations below are user-reported;
they are separate from the earlier automated checks. Slice 5 is packaging,
regression and documentation closeout; no production Python, tests, algorithm
or profile was changed.

Slices 1–5 and the execution integration audit are closed/integrated. Automated
and packaged manual acceptance passed, followed by the independent Claude audit
and ChatGPT final adjudication. **Execution / Playback / Visualizer Foundation
is CLOSED**; Stage-3 Extended as a whole remains **ACTIVE**, and Stage-3 V1 remains
frozen. See the [final adjudication](STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)
for the audit evidence and final F-1 / F-2 dispositions.

At the time this acceptance record was drafted, its documentation status was
**ACCEPTANCE PASS / READY FOR REVIEW**: the changes were uncommitted, this new
record was untracked, and no commit/merge/push had occurred in that drafting
session. Those are historical facts, not the current post-merge state.
Slice 5 documentation was subsequently committed, merged and pushed at
`18964add02c508d67429ef29cb59ce879c01017d`. Neither that signoff nor this final
documentation closeout changes the release version or publishes a tag/release/ZIP.

## Git chronology

Repository: `C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project`.
Development Python: `C:\venvs\minesweeper\Scripts\python.exe`.

At the time this acceptance record was drafted, the **pre-Slice-5 baseline** was
branch `main`, clean working tree, HEAD = local `origin/main` =
`b9af830495ce97552f2058ef91b59a4fd495222b`. Inside work tree was `true`, bare was
`false`, and no remote fetch was performed. The original `git log -12 --oneline`
identified Slice 4 as the latest integrated commit at that time;
`merge-base --is-ancestor` returned 0 for Slices 1–3. The stale desktop cwd was
not used; approved access to the real repository resolved sandbox work-tree
permission errors without changing Git config.

| Slice | Integrated commit | Accepted component |
| --- | --- | --- |
| 1 | `cf7544b6dbc059594750f0798eca8878ddf2ea66` | Execution context + pure trace playback |
| 2 | `d100a493445c7118b5347fdbe2ec0f7243719f17` | Subprocess execution worker |
| 3 | `490a8cf3df1939ae9930e0735665e77120912995` | Read-only Visualizer |
| 4 | `b9af830495ce97552f2058ef91b59a4fd495222b` | Application integration + process lifecycle; pre-Slice-5 baseline |
| 5 | `18964add02c508d67429ef29cb59ce879c01017d` | Acceptance / packaging / documentation closeout |

The original acceptance branch, `feature/stage3-visualizer-acceptance`, was later
deleted after integration; it is historical provenance, not a recovery target.
The **post-merge / independent-audit baseline** was clean `main`, HEAD =
`origin/main` = `18964add02c508d67429ef29cb59ce879c01017d`. This was also verified
before creating `docs/stage3-visualizer-foundation-final-closeout` for the final
documentation correction. It does not claim that `18964ad` remains the latest
HEAD after later documentation commits. Live source/tests/execution take
precedence over stale handoff/build prose.

## Source audit and architecture

Inspected `main.py`, execution/player/worker/job, both Visualizer modules,
`ui_manager.py`, `stage3_physical.py`, `BUILDING.md`, `.gitignore` and `.gitattributes`.

- Both worker dispatches precede Qt setup and GUI imports in `main.py`.
- Frozen job: `sys.executable --stage3-execution-worker payload.pkl result.pkl`.
  Source job: `sys.executable` plus absolute `__file__`-relative worker script.
- The physical profile is file-loaded next to `stage3_physical.__file__` and
  authenticates both exact file bytes and the stored integer timing table.
- Main owns only the launcher; launcher owns job and viewer. Job owns subprocess,
  token, poll/cancel/reap and its entire private temporary directory.
- Viewer takes only a completed `Stage3Execution`; player reconstructs recorded
  moves, with no planner invocation or decision input from the viewer.
- Literal lazy imports are discoverable: generated PYZ inspection confirmed all
  six Extended modules, Stage-3 runner/planner/physical, both worker entries,
  Benchmark Statistics UI, PyQtGraph and NumPy.

```text
indexed EXPERT_GENERAL_V1 → frozen run_stage3 → Stage3Execution
                                      (inside subprocess worker)
main/UI → launcher → Stage3ExecutionJob ╰─ worker
             ╰─ completed execution → viewer → Stage3TracePlayer
```

Execution is independent of the live/Replay board. `Replay != Stage-3 Trace
Playback != ZiNi Trace`. Exact modeled µs, CPU decision timings and presentation
interval remain separate. Arbitrary seeks still rebuild from index 0.
See [architecture](../../ARCHITECTURE.md) and [user controls](../../README.md#stage-3-visualizer).

## Source regressions

| Environment / suite | Result | unittest elapsed |
| --- | --- | --- |
| Normal development, `-m unittest discover -s tests -v` | **1628 passed; 0 failures/errors/skips** | 103.709 s |
| Explicit six Extended modules | **122 passed; 0 failures/errors/skips** | 9.668 s |
| Explicit runner/planner/physical/telemetry protection | **92 passed; 0 failures/errors/skips** | 2.621 s |
| Fresh app build environment, full discovery | **1603 passed; 25 skipped; 0 failures/errors**, 1628 total | 90.505 s |

Development command:

```powershell
& 'C:\venvs\minesweeper\Scripts\python.exe' -m unittest discover -s tests -v
```

Explicit focused modules: `tests.test_stage3_execution`, `tests.test_stage3_trace_player`,
`tests.test_stage3_execution_worker`, `tests.test_stage3_visualizer_ui`,
`tests.test_stage3_execution_job`, `tests.test_stage3_visualizer_launcher`; protection:
`tests.test_stage3_runner`, `tests.test_stage3_planner`, `tests.test_stage3_physical`,
`tests.test_stage3_telemetry`, all via `python -m unittest -v`.
Full discovery includes ZiNi worker/Explorer, Replay UI/control, Live Auto/input,
benchmark statistics UI and frozen Stage-2 regression coverage. No tests were weakened.

The clean build environment's 25 skips are the optional image/video
replay-validation cases (`FixedImageTests`, `SyntheticVideoTests`), not app GUI or
Stage-3 Extended tests. All ran in the normal environment without skips. Wall
times including interpreter/setup were 105.498, 10.189, 2.905 and 91.481 seconds
respectively. Simulated ZiNi-error warnings in test logs belong to passing failure-path tests.

## Build and warnings

Fresh environment: `results/stage3-visualizer-acceptance/20261014/build-env/`.
No repo-local `.venv` was reused and the development environment was not modified.
Python **3.12.10**, MSC v.1943, Windows **11 / 10.0.26200**, **AMD64 / 64-bit**.
PyInstaller **6.22.3**, hooks **2026.8**, PyQt5 **5.15.11**, Qt **5.15.2**,
PyQt5-sip **12.19.0**; PyQtGraph **0.14.0**, NumPy **2.5.3**, colorama **0.4.6**.
The complete dependency inventory is preserved in `build-pip-freeze.txt`.

Two build-documentation corrections were proven without production edits:

1. Add the existing project's plotting dependencies, absent from the old build
   install command but required by `requirements.txt` / Benchmark Statistics UI.
2. Use an absolute profile source for `--add-data`. The first build failed because
   the relative path was resolved under `--specpath`. Its failed log is preserved.

Successful command/config, run from the repository root:

```powershell
$a = 'results/stage3-visualizer-acceptance/20261014'
$buildPython = Join-Path (Get-Location) "$a/build-env/Scripts/python.exe"
$profile = Join-Path (Get-Location) 'calibration/stage3_physical_profile_v1.json'
$env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path (Get-Location) "$a/build-env/Lib/site-packages/PyQt5/Qt5/plugins/platforms"
$env:PYINSTALLER_CONFIG_DIR = Join-Path (Get-Location) "$a/pyinstaller-cache"
& $buildPython -m PyInstaller --noconfirm --clean --onedir --windowed --name Minesweeper --distpath results/stage3-visualizer-acceptance/20261014/dist --workpath results/stage3-visualizer-acceptance/20261014/build --specpath results/stage3-visualizer-acceptance/20261014 --add-data "${profile};calibration" main.py
```

Exit **0**, wall time **71.053 s**, actual x64 `runw.exe` onedir/windowed bundle.
Output: `results/stage3-visualizer-acceptance/20261014/dist/Minesweeper/`.
The target was absent before creation; no unrelated evidence was deleted.

All **233** missing/excluded entries in `warn-Minesweeper.txt` were classified:

| Category | Count | Evidence / meaning |
| --- | --- | --- |
| Dynamic/re-exported attributes | 186 | NumPy core, multiprocessing, Qt/PyQtGraph and asyncio attributes verified in the clean environment |
| Other-platform / legacy alternatives | 23 | POSIX/macOS/Java/Python-2 paths, alternate Qt bindings; actual `PyQt5.sip` imports |
| Frozen runtime supplied | 3 | `_frozen_importlib*`, `pyimod02_importers`; frozen processes ran |
| Optional unused dependency paths | 21 | Scientific/export/GPU/testing/typing extras; clean plotting and NumPy random imports passed |
| Unclassified | 0 | No unexplained entry left |

The build log's `pyqtgraph.opengl` / missing `OpenGL` warning is an optional 3D
path; the app uses 2D plotting. No missing Stage-3 or worker entry module was
reported. The required modules were found in PYZ, and bundled `qwindows.dll`
was actually loaded by the native GUI smoke. Optional libraries were not
installed merely to silence warnings.

## Packaged profile and worker semantics

Source: `calibration/stage3_physical_profile_v1.json`.
Bundled: `results/stage3-visualizer-acceptance/20261014/dist/Minesweeper/_internal/calibration/stage3_physical_profile_v1.json`.
Source bytes = bundled bytes = frozen V1 identity. Both SHA-256 values:

```text
52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b
```

Ran `Minesweeper.exe --stage3-execution-worker payload.pkl result.pkl` with
absolute trusted-local pickle paths, 120-second timeout and unrelated cwd
`C:\Users\User\AppData\Local\Temp\minesweeper_slice5_worker_wtuaz84h\unrelated-cwd`.
Qt/Python path overrides were removed from child environment. Results:

| Case | Owned PID | Result |
| --- | --- | --- |
| Token 503001, game index 0 | 20400 | Exit 0 in 1.553 s; complete `Stage3Execution`, error None |
| Token 503002, game index -1 | 27584 | Exit 0; execution None; `ValueError('game_index must be an integer >= 0.')`, matching source |
| Worker flag with wrong arity | 20840 | Exit 2; no result; console stderr not required |
| ZiNi known 3×3 zero-mine board, token 503003 | 20804 | Exit 0; error None; 1 click / one `fallback_click` at (0,0), equals source |

Stage-3 identity: `EXPERT_GENERAL_V1`, game index **0**, seed **0**, **99** mines,
fingerprint `fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053`.
Final status **WON**, **227** nonempty traces, last status **WON**, exact total
**39,987,084 µs** (first action **126,005 µs**). Player reconstruction reaches the
same status and exact sum. This proves the packaged worker authenticated/loaded
the frozen physical profile, not only that the data file exists.

Source/package equality passed for spec, board index, seed, fingerprint, mine
layout, moves/action sequence, status sequence, every modeled-action integer,
total, final status and all retained deterministic decisions/trace fields.
Only `decision_compute_ns`, wall-clock runtime and object identity were excluded.
This is packaging equivalence for game 0, not a new algorithm qualification.

Each direct worker PID was waited/reaped, no atomic `.tmp` remained, and the
harness-owned payload/result directories were removed after result inspection.
The worker itself does not own parent cleanup. No pickle or worker temp artifact
is retained or tracked, and no arbitrary `%TEMP%` directory was swept.

## GUI and lifecycle evidence

**Actual packaged native GUI startup: PASS.** PID **27448**, title `지뢰찾기`,
window handle **2820508**; bundled
`_internal/PyQt5/Qt5/plugins/platforms/qwindows.dll` loaded. No offscreen override.
The window/process remained responsive through eight seconds of liveness, then
`CloseMainWindow()` succeeded and exit code was **0**. No children existed before
or after close; no forced kill was needed. This is native initialization/process
evidence, not a screenshot or interactive Visualizer claim.

Supplemental **source Qt parent + actual frozen worker** (offscreen) checks:

| Terminal path | Child PID | Exit / cleanup |
| --- | --- | --- |
| Job success | 22120 | 0; reaped; job directory removed; 95 Qt heartbeat ticks |
| Job cancel | 28084 | 1 after requested terminate; reaped; job directory removed |
| Source launcher close during active job | 27856 | 1 after terminate; reaped; job directory removed |
| Source main close during active job | 1076 | 1 after terminate; reaped; job directory removed |

Every child was alive before the terminal action. Cancellation/close was tested
soon after launch, not at every computation phase. The unchanged production
lifecycle owners did the cleanup; only their runtime executable selector was
adapted in the external harness to point to the real EXE. Owned directories were
under one uniquely created temporary root, which was also removed. This does
not independently prove packaged interaction; the user's manual evidence below
provides that separate acceptance.

## Packaged manual acceptance — PASS (2026-10-14)

**Tester:** project user. **Evidence source:** the user's manual packaged acceptance
report supplied in this chat on 2026-10-14 (Asia/Seoul). These are human observations,
not automated GUI results. The earlier automation session lacked the supported
computer-use runtime; the user has now completed the packaged interaction checks.

Main application PID: **5352**. Worker executable:
`results/stage3-visualizer-acceptance/20261014/dist/Minesweeper/Minesweeper.exe`.
The job directories below are under `C:\Users\User\AppData\Local\Temp`.

| Manual terminal path | Worker PID | Exact job directory name | WorkerGone | JobDirGone | Result |
| --- | --- | --- | --- | --- | --- |
| Normal success | 8940 | `minesweeper_stage3_job_s4psvw61` | True | True | PASS |
| Cancel while active | 6300 | `minesweeper_stage3_job_l_vzbzxc` | True | True | PASS |
| Launcher close while active | 5124 | `minesweeper_stage3_job_8i0zv7il` | True | True | PASS |
| Main-app close while active | 19188 | `minesweeper_stage3_job_valyvwtb` | True | True | PASS |

- **Normal success:** packaged Visualizer opened automatically with
  `EXPERT_GENERAL_V1`, game index **0**, **WON**, **227 steps**, total modeled time
  **39,987,084 µs**. Playback controls were manually verified.
- **Cancel:** launcher displayed **취소됨**; no new Visualizer opened.
- **Launcher close:** launcher was closed while the worker was active; the main
  application remained alive and usable.
- **Main-app close:** the worker and job directory were gone, and main PID
  **5352** had **MainGone = True**.

Additional packaged manual checks, all **PASS**:

| Area | Verified behavior |
| --- | --- |
| Startup and execution | Main startup; launcher opens; Run; main remains responsive during execution; automatic Visualizer open |
| Index playback | First / Next / Last; slider click and drag; manual slider seek stops autoplay |
| Presentation controls | Play/Pause; interval editing |
| Retained result | Closing viewer, then **결과 열기**, reopens the retained completed execution |
| Active-job lifecycle | Cancel; launcher-close; main-close, with the PID/directory evidence above |

The required packaged manual gate is complete. At the time this acceptance
record was drafted, documentation review remained; the record was subsequently
integrated at `18964add02c508d67429ef29cb59ce879c01017d`. The independent audit and
final adjudication now also pass. No release publication is implied.

## Manual UX observations — accepted behavior and deferred follow-up

These observations are **nonblocking**, are **not Slice-5 implementations**, and
do not reopen foundation acceptance:

- **Labels:** Run starts a new execution; **결과 열기** reopens the retained completed
  execution. Their semantics are distinct and accepted; clearer labels are deferred.
- **Status:** final result **WON** while Step 0/current reconstructed status is
  **PLAYING** is correct trace semantics: no recorded actions have been applied yet.
- **Interval:** the current **20–5000 ms** range is intentional presentation timing,
  independent of Model C action durations.
- **Cursor endpoints / straight line:** the current cell-center displacement
  presentation is accepted modeled geometry, not an actual OS mouse trajectory.
- **Smooth cursor:** synthetic/interpolated cursor motion is desirable for later
  presentation work. It must remain explicitly labeled synthetic/interpolated and
  must never be claimed as an actual OS mouse trajectory.
- **Modeled-Time Playback:** desirable later so recorded Model-C action durations
  can be visually inspected; it is not implemented by this closeout.
- **Manual seek:** stopping autoplay is accepted behavior.
- **Incremental forward playback:** `Stage3TracePlayer` optimization remains deferred
  until justified by modeled-time/smooth-animation requirements or measured lag.
  Existing reconstruction semantics remain unchanged; no quantitative lag result
  was supplied with the manual report.

## Evidence, hygiene and remaining scope

Ignored evidence root: `results/stage3-visualizer-acceptance/20261014/`.
Contains `source-full.log`, `source-extended-focused.log`, `source-frozen-focused.log`,
`build-env-full.log`, timing summaries, install logs, `build-pip-freeze.txt`,
`pyinstaller-attempt1.log`, `pyinstaller-build.log`, generated spec/build/archive,
`build-warning-audit.json`, `packaged-workers.json`, `packaged-gui-startup.json`,
`source-parent-frozen-worker-lifecycle.json`, and the external acceptance harness.
These are local evidence, not tracked release artifacts. Keep the complete dist
folder as accepted package evidence; no release ZIP/tag/publication is implied.

At the time this acceptance record was drafted, its seven documentation changes
were root README, ARCHITECTURE, BUILDING, docs index, CURRENT_HANDOFF, Extended
README and this new record. The drafting-session checks were
**`git diff --check` PASS; 71 local documentation paths/anchors PASS**.
Profile bytes matched HEAD and the bundle; production/tests were unchanged.
Nothing was staged, and this record was then untracked pending review.
Those historical checks are not claimed as validation of later documentation edits.

The two pre-existing tracked historical files under `results/stage3_replay_validation/`
remain preserved. `final-hygiene.json`, `final-git-status.txt` and
`final-git-diff.patch` preserve the earlier automated closeout snapshot, including
its then-pending manual status. Generated evidence and build outputs were not
rewritten for the manual signoff or this final-adjudication documentation closeout.
The seven Slice 5 documents were subsequently committed/merged/pushed at
`18964add02c508d67429ef29cb59ce879c01017d`.

Automated and user-reported packaged manual acceptance are complete. Independent
Claude audit and ChatGPT final adjudication also pass; see the
[final adjudication](STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md) for the exact
independent evidence and F-1 documentation-only closeout. F-2 packaged windowed
transport-failure hardening remains **OPTIONAL / DEFER** and was not implemented.
There is no implementation blocker or required production change.

Optional image/video tooling was absent only from the isolated build environment.
No quantitative packaged seek latency result is claimed; reconstruction from
index 0 remains the accepted implementation.

Next active milestone: **Version / Settings Identity Separation** (application,
algorithm, physical profile, presentation). Later: Modeled-Time Playback /
synthetic smooth cursor, same-board Human / Stage-2 / Stage-3, representative
boards / Timeline Analytics, and first real Extended algorithm research, likely
nearest exact-minimum-risk guess.
Known-mine/no-flag, action-specific timing, anisotropy, CPS/burst and richer/longer
planning remain evidence-triggered. This is a dependency roadmap, not a fixed schedule.
