# Windows release build

The historical v0.2.0 release uses a Windows x64 PyInstaller **onedir / windowed**
bundle. Current main uses the same build method but is not labeled v0.2.0; its
source identity is the actual Git commit. No runtime app-version constant,
QApplication version or version resource has been added. Extract the
entire release ZIP and run `Minesweeper/Minesweeper.exe`; keep `_internal` beside
the executable. Python does not need to be installed on the target machine.

## Build and test

Use 64-bit Python 3.12 on Windows. Create the build environment in an **ASCII
path**: Qt 5.15.2 can report a corrupted plugin path when its installation path
contains Korean characters. The source checkout and output can contain Korean
characters. Run these commands from the repository root:

```powershell
$buildId = Get-Date -Format 'yyyyMMdd-HHmmss'
$buildEnv = Join-Path $env:TEMP "minesweeper-release-build-$buildId"
$buildRoot = Join-Path (Get-Location) "results/release-build/$buildId"
if ((Test-Path -LiteralPath $buildEnv) -or (Test-Path -LiteralPath $buildRoot)) {
    throw 'Choose a new build ID; preserve existing environments and artifacts.'
}
if ($buildEnv -match '[^\x00-\x7F]') { throw 'Choose an ASCII-only build environment path.' }
New-Item -ItemType Directory -Path $buildRoot | Out-Null
py -3.12 -m venv $buildEnv
$buildPython = Join-Path $buildEnv 'Scripts/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $buildPython -m pip install PyQt5==5.15.11 PyQt5-Qt5==5.15.2 PyQt5-sip==12.19.0 pyinstaller==6.22.3 pyqtgraph==0.14.0 numpy==2.5.3 colorama==0.4.6
$env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $buildEnv 'Lib/site-packages/PyQt5/Qt5/plugins/platforms'
& $buildPython -B -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; do not package.' }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $buildRoot 'pyinstaller-cache'
$profile = (Resolve-Path 'calibration/stage3_physical_profile_v1.json').Path
& $buildPython -B -m PyInstaller --noconfirm --clean --onedir --windowed --name Minesweeper --distpath "$buildRoot/dist" --workpath "$buildRoot/build" --specpath "$buildRoot" --add-data "${profile};calibration" main.py
```

Inspect the chosen build environment and output directories before reuse.
Acceptance requires a fresh ASCII-path environment and isolated environment,
dist/work/spec/cache paths. Foundation used
`results/stage3-visualizer-acceptance/<run-id>/`; Identity Separation used
`results/stage3-identity-separation-acceptance/<run-id>/`; Modeled-Time Playback uses
`results/stage3-modeled-playback-acceptance/<run-id>/`; Human Mouse Trace uses
`results/human-mouse-trace-final-acceptance/<run-id>/`. Do not overwrite previous
release/evidence output or change the normal development environment. `results/` is ignored; generated artifacts are
not source files to commit.

The plotting dependencies above are required by the existing Benchmark Statistics
UI and match the versions exercised on 2026-10-14. The original Qt/PyInstaller
pins are unchanged. Record `pip freeze`, Python version and architecture per build.
The normal development environment is the authority for full source regression:
`C:\venvs\minesweeper\Scripts\python.exe -m unittest discover -s tests -v`.
The clean app build environment can skip optional image/video replay-validation
tests when their separate dependencies are absent; record those skips explicitly.
Do not treat skipped tests as passed or omit required app/UI dependencies.

Use an **absolute source profile path** with `--add-data`: when `--specpath` is
under `results`, PyInstaller resolves relative data paths against that spec
directory. Slice 5 reproduced a missing-profile build failure with the former
relative command; `Resolve-Path` fixes the build configuration without changing
profile bytes or production code.

The build uses the normal Python import graph; no hidden import or worker script
data copy is required. The ZiNi worker requires no separate data file. The
Stage-3 execution worker uses the frozen physical profile: the `--add-data`
option above bundles the existing `calibration/stage3_physical_profile_v1.json`
at the same relative path. Preserve its exact bytes and frozen SHA-256 contract;
do not regenerate or edit the profile for packaging.

`main.py` dispatches `--zini-metric-worker`, `--stage3-execution-worker` and
`--same-board-execution-worker` independently before Qt setup and GUI imports.
Source entry points are `python zini_metric_worker.py <payload.pkl> <result.pkl>`,
`python stage3_execution_worker.py <payload.pkl> <result.pkl>` and
`python same_board_execution_worker.py <payload.pkl> <result.pkl>`; the bundle uses
`Minesweeper.exe --zini-metric-worker <payload.pkl> <result.pkl>`,
`Minesweeper.exe --stage3-execution-worker <payload.pkl> <result.pkl>` and
`Minesweeper.exe --same-board-execution-worker <payload.pkl> <result.pkl>`.
Same-board dispatch is implemented; Slice 2B included no fresh package or native
GUI acceptance. The existing
ZiNi polling and cancellation protocol is unchanged. `Stage3ExecutionJob` now
owns Stage-3 process/token/polling/cancel/reap and the whole private job directory.
The launcher owns this job and the read-only viewer; the main UI owns the launcher.
Source job commands use the absolute `__file__`-relative worker path; frozen jobs
use `sys.executable` and the worker flag. Both dispatch before Qt setup. PyInstaller's
[runtime documentation](https://pyinstaller.org/en/stable/runtime-information.html)
describes `sys.frozen` and `sys.executable` in a bundle.

## Release checks

- Run focused physical mouse input, Mouse Trace recorder/UI/overlay, Replay,
  ZiNi worker dispatch and Stage-3 execution/Visualizer tests, then full discovery
  with PyQt installed. Record counts, skips and interpreter versions.
- Run the built worker on a known board and confirm its token/result and exit code;
  check invalid arguments and a calculation error. Use a separate working directory.
- Verify the packaged Stage-3 worker with trusted-local `{"token": 503001,
  "game_index": 0}` from an unrelated working directory and an explicit timeout.
  Require exit 0, matching token, no error, a complete `Stage3Execution`, exact
  benchmark/board identity, terminal WON/LOST, nonempty traces and integer modeled
  costs. Compare deterministic fields to source, excluding `decision_compute_ns`.
  Check wrong arity (exit 2), invalid index (failure envelope), owned PID reaping
  and temporary-directory cleanup. Do not depend on console stderr from a windowed EXE.
- Compare repository profile bytes to
  `Minesweeper/_internal/calibration/stage3_physical_profile_v1.json`.
  Both must have frozen SHA-256
  `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
  Inspect warnings and verify lazy Stage-3 modules, both workers and Qt plugins.
- Launch the complete onedir GUI, verify native Qt startup/liveness, then exercise
  launcher Run/Cancel, auto-open, retained-result reopen, playback, launcher-close
  and main-close during active jobs. Track only owned child PIDs and directories.
  If packaged interaction cannot be automated reliably, require recorded human
  packaged acceptance; source/offscreen GUI results do not replace it.
- Launch the built GUI, play a game to completion and wait for a numeric ZiNi.
  Reset or close during a pending calculation; check that the child exits and its
  payload/result files are removed. Check Replay loading and analysis.
- Verify Human Mouse Trace recording/display, physical gesture behavior and a
  trace-bearing Replay v2 load/seek/save round-trip. `mouse_trace` and
  `mouse_trace_ui` use normal imports; no new data file or hidden import is required.
- Ship the complete onedir folder with `LICENSE`, user documentation, and dependency
  notices/licenses. Provide the corresponding tagged source alongside the binary.
- For a separately authorized release, ZIP the folder, record its SHA-256 and
  publish it with its matching source tag. The historical `v0.2.0` tag does
  not identify current main or the acceptance package below.

The v0.2.0 release identity is unchanged by this documentation closeout. Current
source includes the accepted telemetry/benchmark implementation and Stage-3 V1;
historical release binaries should be identified by their own source tag.
ZiNi remains bounded best-so-far, not a proven minimum.

## Slice 5 acceptance evidence (2026-10-14)

The real Windows x64 onedir/windowed build, profile identity, Stage-3 worker,
source/package semantic equivalence, narrow ZiNi worker smoke and native GUI
startup passed. The project user completed packaged manual acceptance on
2026-10-14, including playback, retained-result reopen and all four success/cancel/
active-close cleanup paths. Slice 5 documentation was committed, merged and
pushed at `18964add02c508d67429ef29cb59ce879c01017d`, also the independent-audit
baseline; this is a dated identity, not a permanent latest-HEAD claim.
Independent Claude audit: **PASS**. ChatGPT final adjudication:
**FINAL ADJUDICATION PASS / CLOSED** for Execution / Playback / Visualizer
Foundation. Stage-3 Extended remains **ACTIVE**. See the
[acceptance record and manual evidence](docs/stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)
and [final adjudication](docs/stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md).

**F-2 — OPTIONAL / DEFER:** packaged windowed worker transport exceptions may
surface through PyInstaller's uncaught-exception dialog instead of immediately
exiting. There is no false success; Cancel, launcher close and main close retain
ownership and reap the worker. This environmental transport-failure case remains
future worker/release hardening. It was not fixed here: changing production would
invalidate accepted package/source identity and reopen packaging acceptance.

Existing generated evidence remains the earlier automated snapshot and was not
rewritten by either documentation-only signoff. The accepted package was not
rebuilt; no release version change, tag, publication or distribution ZIP was made.

## Identity Separation package verification (2026-10-15)

A fresh Windows x64 onedir/windowed package was built from
`e04d4e8292338f53b0a3a0f88e999992b9ac80ec` using the same accepted build command,
documented dependency pins and absolute `--add-data` profile source. The isolated
environment, dist/work/spec/cache and new evidence are under
`results/stage3-identity-separation-acceptance/20261015-012718/`; historical
Foundation output was not reused or overwritten.

`stage3_identity.py` is a normal import: no new hidden-import or data rule is
needed. Exact frozen profile bundling remains required. Build exit 0, bundled
profile byte/SHA equality and packaged game-0 deterministic source equivalence
passed. The project user also passed the concise native packaged GUI smoke:
separate identity labels, game-0 viewer, dynamic presentation interval label,
unchanged modeled total and clean close. See the
[Identity Separation closeout](docs/stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md)
for commands, counts, environment and automated/manual evidence.
No release version, runtime application-version claim, version resource, tag or
distribution ZIP was added. This fresh verification is distinct from the
historical Foundation evidence above.

## Modeled-Time Playback package verification (2026-10-15)

A fresh Windows x64 onedir/windowed package was built from
`82c61d5447bf7cffc3c1d4fbcd392ef2945efa04` using the accepted method above:
Python 3.12.10 / 64-bit, documented dependency pins and the absolute profile
`--add-data` path. Its new environment, dist/work/spec/cache and evidence are under
`results/stage3-modeled-playback-acceptance/20261015-113435/`.
Foundation, Identity Separation and historical release output were preserved.

Build **exit 0**, **83.6817627 s**. Archive inspection confirms
`stage3_modeled_playback`, `stage3_visualizer_ui` and `stage3_trace_player` are bundled;
they use normal Python imports with no additional hidden-import/data rule.
Warnings contain no missing playback module; the optional unused
`pyqtgraph.opengl` / `OpenGL` warning remains. Frozen profile bundling is still required.

Source regression: **254 focused / 1699 full passed**, zero failures/errors/skips.
Source/bundled profile bytes and required SHA-256 match. The packaged game-0 worker
passed from an unrelated cwd with deterministic source equivalence. The project
user reported **"A–K passed"** for the fresh native package: Index regression,
modeled controls, stationary first action, synthetic movement, pause/resume,
navigation, mode/rate changes, terminal total and close/reopen defaults.

See the [Modeled-Time closeout](docs/stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md)
for exact commands and evidence. No application/release version, build configuration,
profile bytes or worker transport changed. No tag, release or ZIP was published;
current main is not relabeled historical v0.2.0.

## Human Mouse Trace final package acceptance (2026-10-16)

Qualified implementation/package SHA:
`e32145fa5c114e1ce500ad2e837ef6000cc49cca`.
The fresh isolated acceptance root is
`results/human-mouse-trace-final-acceptance/20261016-003839/`.
Its `acceptance-summary.json` records the exact command, versions, test results,
package hashes, both worker checks and automated native GUI smoke. Final user
native/manual acceptance subsequently passed; see the
[Human Mouse Trace closeout](docs/stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md).

Python 3.12.10 x64, pip 25.0.1 and the pinned stack above produced an onedir/windowed
AMD64 / PE32+ / GUI-subsystem package: build exit **0**, **60.658 s**.
Source tests: **627 focused / 1825 full PASS**, zero failures/errors/skips.
Fresh build environment: **1800 PASS / 25 optional image/video validation skips**,
zero failures/errors; skip identities match the historical accepted category.
Bundled Qt, both workers and frozen profile/table identities passed. Replay v2
with Mouse Trace survived packaged GUI load/seek/save with exact JSON equality.

EXE SHA-256: `d73e25b4f21306a951ddf3e90727b337f42a2a04a4678d19d0b7f8f6eb00c787`.
The earlier `results/human-mouse-trace-final-acceptance/20261015-215537/` remains
historical post-hardening evidence at `6fe61866681612060bbb3d57940c726de4f224b3`;
it is not the final package because physical gesture semantics changed afterward.
Both roots remain untouched. No new application version, tag or release is declared.
