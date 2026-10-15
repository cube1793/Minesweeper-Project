# Modeled-Time Playback / Synthetic Smooth Cursor Presentation — Closeout

Date: **2026-10-15 (Asia/Seoul)**. Status: **FINAL ACCEPTANCE PASS / CLOSED**.
Stage-3 Extended remains **ACTIVE**. A roadmap decision made after closeout
preparation inserts **Human Mouse Trace / Path Visualization (not implemented)**
as the next active small milestone, followed by **Same-board Human / Stage-2 /
Stage-3 Comparison**, then representative demonstrations / Timeline Analytics
and first actual Extended algorithm research.

The planned Mouse Trace scope is actual movement sampled only over the Live game
board, with pixel-space points/timestamps and actual action/click markers stored
separately from Replay, then visualized over the board after game completion.
It excludes OS-global hooks, Stage-3 synthetic cursor reuse, physical-model
calibration/refit and advanced path analytics. This correction changes planning
only; it adds no implementation/spec document and leaves acceptance evidence unchanged.
`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human Mouse Trace is actual sampled Live-board cursor presentation data, not
Stage-3 synthetic movement or Model-C calibration evidence.

## Scope and implementation identity

This milestone presents an already-completed Stage-3 trace using its opaque
recorded `modeled_action_us` durations and a synthetic cursor. It adds no solver
behavior or physical timing model. Slice 4 changes documentation only.

Before closeout preparation, live Git verified the expected repository,
`main`, a clean non-bare working tree, and
`HEAD == origin/main == 82c61d5447bf7cffc3c1d4fbcd392ef2945efa04`.
No fetch was performed; the comparison used the local remote-tracking ref.
The closeout branch is `docs/stage3-modeled-playback-closeout`.
This is a dated baseline; live Git/source/tests override this record.

| Slice | Integrated implementation commit | Result |
| --- | --- | --- |
| 1 | `b4ab1c8e9bbd9552d27daed884d97cf36d00aef6` | Failure-atomic incremental forward TracePlayer |
| 2 | `01d91b397cc285825cf7083c88724328bbe6c587` | Pure modeled-time playback controller |
| 3 | `82c61d5447bf7cffc3c1d4fbcd392ef2945efa04` | Visualizer modes and synthetic smooth cursor |

## Accepted architecture and presentation

| Owner | Responsibility |
| --- | --- |
| `Stage3TracePlayer` | Committed integer index, reconstructed board, cursor/current trace and exact cumulative µs. `next()` copies the current engine, applies/validates one pending recorded action and publishes only on success. Arbitrary `go_to()` still reconstructs from zero; `previous()` retains that path. |
| `Stage3ModeledPlayback` | Qt-independent monotonic clock anchoring, exact Fraction partial µs, running state, six speeds, pause/resume, zero-duration handling and ordered boundary catch-up. `cancel_partial()` stops and clears partial time without navigating. |
| `Stage3VisualizerWindow` | Widgets, 16 ms PreciseTimer frame requests, rendered cell-center geometry, easing and cursor overlay. Fraction-to-float conversion occurs only at the rendering edge. |

Index remains the construction/reopen default: 20..5000 ms/step, default 200,
one action per timeout, integer slider, no wraparound. Modeled-Time defaults to
1× and offers 0.25× / 0.5× / 1× / 2× / 4× / 8×. Both rate labels explicitly say
`(presentation)`; mode, interval and multiplier are not persisted.

During a pending interval the board stays at committed index k. At its exact
duration boundary the recorded action is applied once. A late update consumes
every crossed boundary in order and stops exactly at N. Partial frames update
only the overlay; an index change refreshes the resulting board once after catch-up.

The pending trace supplies cursor-before A and target B. Raw timeline progress u
becomes `q = u² * (3 - 2u)` and `P = A + q * (B - A)`, using rendered cell centers
rather than calibration pixel size. The path is straight with no separate dwell,
overshoot, curves or jitter. Same-cell positive-duration actions remain stationary;
game 0 begins with `(0,0) → (0,0)` for **126,005 µs**. The detail panel continues
to describe the last applied trace.

Pause accounts for time through the request, then freezes partial progress.
Resume re-anchors without counting paused time. A speed change first accounts
for elapsed time at the old speed. Manual navigation stops the timer, cancels
partial progress, then performs the existing integer navigation; unsampled wall
time is not consumed first. Same-index slider interaction cancels partial playback;
programmatic slider synchronization does not. Mode switches retain the committed
index and remain paused. Failure/close stops playback; final Play does not rewind.

The earlier representative **120-fps Minesweeper Online replay-reference inspection**
supported straight paths with mild endpoint easing and no separate visible dwell
phase. This was a presentation reference, not a reconstruction of actual OS mouse
motion or proof of the website's exact easing function. It informed the fixed
smoothstep convention and **was not used to refit Model C**.

- QTimer frame request != modeled-time authority; 16 ms is not a measured FPS claim.
- Presentation speed != Model C parameter.
- Smoothstep easing != physical acceleration model.
- Synthetic cursor != actual OS trajectory.
- Replay elapsed time != Stage-3 modeled time.
- `decision_compute_ns != modeled physical time`.

## Preserved Slice-1 performance evidence

Repeated prefix reconstruction motivated the incremental forward path. The
accepted game-0 source diagnostics are preserved here, not rerun in Slice 4:

| Measurement | Before | After |
| --- | --- | --- |
| Complete sequential traversal | ~4.07–4.32 s | ~0.209–0.215 s |
| Median `next()` | ~18–19 ms | ~0.88–0.90 ms |
| P95 `next()` | ~30–33 ms | ~1.17–1.25 ms |
| Late `next()` | ~31–35 ms | ~0.95–1.11 ms |

These are bounded game-0 forward-player diagnostics, not general application,
arbitrary-seek or native packaged FPS measurements. Native acceptance below is
qualitative responsiveness/visual usability only.

## Final source regression

Development interpreter: `C:\venvs\minesweeper\Scripts\python.exe`,
CPython 3.12.10 / Windows x64. Commands ran from the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m unittest tests.test_stage3_modeled_playback tests.test_stage3_trace_player tests.test_stage3_execution tests.test_stage3_visualizer_ui tests.test_stage3_visualizer_launcher tests.test_stage3_execution_job tests.test_stage3_identity tests.test_stage3_physical tests.test_stage3_runner tests.test_stage3_execution_worker tests.test_zini_worker_dispatch -v
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m unittest discover -s tests -v
```

| Run | Discovered | Passed | Failures | Errors | Skips | Duration | Exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Focused | 254 | 254 | 0 | 0 | 0 | 29.048 s | 0 |
| Full discovery | 1699 | 1699 | 0 | 0 | 0 | 130.978 s | 0 |

The suite count is unchanged from accepted Slice 3. Pure fake-clock tests remain
authoritative for timing semantics; offscreen UI tests cover integration and
presentation boundaries. No 100k benchmark was run.

## Fresh package and profile

New ignored acceptance root:

`results/stage3-modeled-playback-acceptance/20261015-113435/`

The accepted [BUILDING.md method](../../BUILDING.md#build-and-test) was used with
a new ASCII-path `build-env` and isolated dist/work/spec/cache beneath this root.
Foundation, Identity Separation and historical release artifacts were preserved.
The normal development environment was unchanged.

Pins: PyQt5 5.15.11, PyQt5-Qt5 5.15.2, PyQt5-sip 12.19.0,
PyInstaller 6.22.3, pyqtgraph 0.14.0, numpy 2.5.3 and colorama 0.4.6.
`pip-freeze.txt` and `python-version.txt` record the complete build environment.

The resolved invocation used these values (full absolute arguments are also in
`build-command.json`):

```powershell
$repo = 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$acceptanceRoot = Join-Path $repo 'results\stage3-modeled-playback-acceptance\20261015-113435'
$buildPython = Join-Path $acceptanceRoot 'build-env\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $acceptanceRoot 'build-env\Lib\site-packages\PyQt5\Qt5\plugins\platforms'
$env:PYINSTALLER_CONFIG_DIR = Join-Path $acceptanceRoot 'pyinstaller-cache'
$profile = (Resolve-Path -LiteralPath 'calibration\stage3_physical_profile_v1.json').Path
$profileData = $profile + ';calibration'
& $buildPython -B -m PyInstaller --noconfirm --clean --onedir --windowed --name Minesweeper --distpath "$acceptanceRoot\dist" --workpath "$acceptanceRoot\build" --specpath "$acceptanceRoot" --add-data $profileData main.py
```

Build: **exit 0**, **83.6817627 s**. PE inspection confirmed machine `0x8664`,
PE32+ `0x20b`, GUI subsystem `2` and the native `qwindows.dll` plugin.
Archive inspection confirmed the controller, viewer, player, execution/worker/job,
launcher, identities/physical module and ZiNi worker.

Warning review found no missing `stage3_modeled_playback`, `stage3_visualizer_ui`
or `stage3_trace_player`. The 233 module-warning entries are retained for review;
the build also reported optional unused `pyqtgraph.opengl` / missing `OpenGL`.
No evidence required an extra hidden import or data rule. The controller is a
normal Python import; the existing absolute frozen-profile bundling remains required.

Source `calibration/stage3_physical_profile_v1.json` and bundle
`dist/Minesweeper/_internal/calibration/stage3_physical_profile_v1.json` are
**byte-identical**, both with the required SHA-256:

`52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`

## Packaged worker equivalence

The fresh `dist/Minesweeper/Minesweeper.exe` ran with
`--stage3-execution-worker <absolute payload.pkl> <absolute result.pkl>` from an
unrelated temporary directory, with a 60-second bound. Payload:
`{"token": 415001, "game_index": 0}`.

- Exit **0**; exact token/execution/error envelope, matching integer token, error `None`.
- Unpickled `Stage3Execution` retains exactly `spec / board / result`.
- **WON**, **227 traces**, **39,987,084 modeled µs**; first action **126,005 µs**.
- Board fingerprint:
  `fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053`.
- Complete deterministic source/package dataclass equality after excluding trace
  `decision_compute_ns`. Wall runtime and object identity are not compared.
- The process was reaped and unrelated temporary directory cleaned.

This is compatibility evidence, not a new performance claim.

## Native packaged GUI acceptance

Tester: **project user**, **2026-10-15 (Asia/Seoul)**. Direct response to the
required fresh-package A–K checklist: **"A–K passed"**.

Executable: `results/stage3-modeled-playback-acceptance/20261015-113435/dist/Minesweeper/Minesweeper.exe`.
Autonomous native interaction was unavailable; these results are user-reported
native acceptance, distinct from automated source/offscreen tests.

| Check | User-accepted result |
| --- | --- |
| A — Open | Fresh package opens Stage-3 Visualizer and runs game 0. |
| B — Index | Default Index / 200 ms; ordinary Play/Pause/navigation works. |
| C — Controls | Modeled-Time default 1×; proper active/inactive rate controls and presentation label. |
| D — Same-cell first action | Stationary cursor; no immediate OPEN; action commits after its interval. |
| E — Movement | Straight, smooth enough, slower endpoints/faster middle, no obvious ordinary boundary jumps, target understandable. |
| F — Pause/Resume | Cursor freezes while waiting and resumes without an obvious jump. |
| G — Navigation | Next/slider during movement discard partial animation and snap to integer state. |
| H — Mode switching | Committed step retained, partial cleared, paused; no rewind/autostart. |
| I — Rates | 0.25× slower, 1× normal modeled presentation, 8× completes without logical/UI failure. |
| J — Final | WON, Step 227 / 227, total 39,987,084 µs unchanged by speed. |
| K — Close/reopen | Retained result reopens at Index / 200 ms / modeled 1×; clean close, no persistence. |

This accepts presentation usability. It does not measure physical mouse motion,
physical acceleration, human timing accuracy or FPS.

## Evidence, compatibility and deferred scope

The ignored acceptance root contains `baseline.json`, `regression-commands.json`,
`regression-summary.json`, focused/full logs, build environment/version records,
`build-command.json`, build log/result, `package-format.json`,
`build-warning-audit.json`, `packaged-worker-profile.json` and
`native-gui-acceptance.json`. These are local acceptance artifacts, not tracked release output.
The tracked closeout preserves their essential results.

Unchanged: Stage-3 V1 semantics; `STAGE3_V1_IDENTITY` / `MODEL_C_V1_IDENTITY`;
Model C timing/profile/table and SHA; `Stage3Execution(spec, board, result)`;
worker pickle transport; benchmark `solver_config_snapshot`; official 100k evidence;
Replay schema/semantics; ZiNi; database/schema; QSettings.
Slice 4 changes no production Python, tests, frozen specs/evidence or build configuration.

Still **DEFERRED / evidence-triggered**:

- Arbitrary-seek checkpoint/cache optimization; modeled-time slider/sub-action scrubbing.
- 120-fps UI target, easing selector, click pulse and persistent Stage-3 presentation settings.
- Runtime app version, selectable algorithm/profile and durable cross-version execution transport.
- Richer physical model / Model C successor/refit, movement/click decomposition,
  action-specific OPEN/FLAG/CHORD timing, CPS/burst/minimum inter-action constraints,
  anisotropy, physical CHORD variants and human cognitive timing.
- Built-in screen recording unless later justified.
- Foundation **F-2 remains OPTIONAL / DEFER**; no new evidence promotes it.

Documentation validation: **7 documents, 95 local links and 20 anchor references**
checked with no broken targets/anchors; external URLs were excluded.
`git diff --check` and the new closeout whitespace check passed.
The final scope is six modified documents plus this one new record;
`documentation-checks.json` preserves the counts and scope result.

No app/release version change, release tag, ZIP or GitHub release was published.
No files were staged, committed or pushed during closeout preparation.
See the [current handoff](../CURRENT_HANDOFF.md) and [Extended roadmap](README.md).

**STAGE-3 EXTENDED MODELED-TIME PLAYBACK /
SYNTHETIC SMOOTH CURSOR PRESENTATION —
FINAL ACCEPTANCE PASS / CLOSED**
