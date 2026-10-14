# Windows release build

v0.2.0 uses a Windows x64 PyInstaller **onedir / windowed** bundle. Extract the
entire release ZIP and run `Minesweeper/Minesweeper.exe`; keep `_internal` beside
the executable. Python does not need to be installed on the target machine.

## Build and test

Use 64-bit Python 3.12 on Windows. Create the build environment in an **ASCII
path**: Qt 5.15.2 can report a corrupted plugin path when its installation path
contains Korean characters. The source checkout and output can contain Korean
characters. Run these commands from the repository root:

```powershell
$buildEnv = Join-Path $env:TEMP 'minesweeper-release-build'
python -m venv $buildEnv
$buildPython = Join-Path $buildEnv 'Scripts/python.exe'
& $buildPython -m pip install PyQt5==5.15.11 PyQt5-Qt5==5.15.2 PyQt5-sip==12.19.0 pyinstaller==6.22.3
$env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $buildEnv 'Lib/site-packages/PyQt5/Qt5/plugins/platforms'
& $buildPython -m unittest discover -s tests -v
$env:PYINSTALLER_CONFIG_DIR = Join-Path (Get-Location) 'results/pyinstaller-cache'
& $buildPython -m PyInstaller --noconfirm --clean --onedir --windowed --name Minesweeper --distpath results/dist --workpath results/build --specpath results --add-data "calibration/stage3_physical_profile_v1.json;calibration" main.py
```

The build uses the normal Python import graph; no hidden import or worker script
data copy is required. The ZiNi worker requires no separate data file. The
Stage-3 execution worker uses the frozen physical profile: the `--add-data`
option above bundles the existing `calibration/stage3_physical_profile_v1.json`
at the same relative path. Preserve its exact bytes and frozen SHA-256 contract;
do not regenerate or edit the profile for packaging.

`main.py` dispatches both `--zini-metric-worker` and `--stage3-execution-worker`
before Qt setup and GUI imports. Source entry points are
`python zini_metric_worker.py <payload.pkl> <result.pkl>` and
`python stage3_execution_worker.py <payload.pkl> <result.pkl>`; the bundle uses
`Minesweeper.exe --zini-metric-worker <payload.pkl> <result.pkl>` and
`Minesweeper.exe --stage3-execution-worker <payload.pkl> <result.pkl>`. The existing
ZiNi polling and cancellation protocol is unchanged. Stage-3 currently provides
only the child execution boundary; parent lifecycle ownership belongs to the
Visualizer slice. PyInstaller's
[runtime documentation](https://pyinstaller.org/en/stable/runtime-information.html)
describes `sys.frozen` and `sys.executable` in a bundle.

## Release checks

- Run the focused `test_zini_worker_dispatch.py` tests and the full suite with PyQt installed.
- Run the built worker on a known board and confirm its token/result and exit code;
  check invalid arguments and a calculation error. Use a separate working directory.
- Perform the packaged Stage-3 execution worker smoke at final Extended acceptance,
  before closing the first Visualizer milestone. Verify the bundled frozen profile
  loads and the complete execution unpickles from an unrelated working directory.
- Launch the built GUI, play a game to completion and wait for a numeric ZiNi.
  Reset or close during a pending calculation; check that the child exits and its
  payload/result files are removed. Check Replay loading and analysis.
- Ship the complete onedir folder with `LICENSE`, user documentation, and dependency
  notices/licenses. Provide the corresponding tagged source alongside the binary.
- ZIP the folder, record its SHA-256, then publish it with the matching `v0.2.0` tag.

Pre-Stage 3 telemetry SPEC v2 is frozen documentation; telemetry is not implemented
by this release. ZiNi remains bounded best-so-far, not a proven minimum.
