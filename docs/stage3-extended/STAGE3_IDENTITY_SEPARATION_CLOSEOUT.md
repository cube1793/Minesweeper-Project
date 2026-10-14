# Stage-3 Version / Settings Identity Separation Closeout

Date: **2026-10-15 (Asia/Seoul)**.
Milestone: **Stage-3 Extended — Version / Settings Identity Separation**.

## Acceptance status

**STAGE-3 EXTENDED VERSION / SETTINGS IDENTITY SEPARATION —
FINAL ACCEPTANCE PASS / CLOSED**
Stage-3 Extended remains **ACTIVE**; Stage-3 V1 / Model C remain **CLOSED / FROZEN**.
[Foundation final adjudication](STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)
remains historical and closed.

## Live implementation baseline

Live Git before preparation: clean `main`, HEAD == local `origin/main` ==
`e04d4e8292338f53b0a3a0f88e999992b9ac80ec`. No fetch was performed.
This is a dated baseline, not a permanent latest-HEAD claim.

| Integrated slice | Commit |
| --- | --- |
| 1 — Public Fixed Identities | `858dc1aa3bdac69cff85bb6bbb6ac352bac5f37b` |
| 2 — Identity-backed Visualizer Labels | `e04d4e8292338f53b0a3a0f88e999992b9ac80ec` |

Closeout branch: `docs/stage3-identity-separation-closeout`.
Production and tests are unchanged in this slice. Documentation awaits user
review; no commit, merge, push, tag or release publication was performed here.

## Architecture outcome

`Application/release != algorithm identity != physical model/profile != playback/presentation`.

| Owner / consumer | Final responsibility |
| --- | --- |
| Release/tag/build documentation | Application identity; no runtime app-version constant, QApplication version or version resource. Current main is not historical `v0.2.0`. |
| `stage3_identity.STAGE3_V1_IDENTITY` | Immutable fixed V1 algorithm spec version/hash and solver stage/policy. Reuses existing telemetry constants; telemetry semantic version and initial OPEN/cursor configuration remain separate. |
| `stage3_physical.MODEL_C_V1_IDENTITY` | Semantic model ID, concrete profile identity and exact table identity. Actual byte/hash/metadata/table authentication and costs remain unchanged. `MODEL_C_DISPLAY_NAME` is a separate presentation alias. |
| Benchmark producer/evaluator | Consume authoritative identities; preserve all nine snapshot keys, values, types, canonical serialization and rejection/admission rules. |
| Launcher/viewer | Read-only identity consumers. Launcher corpus comes from `EXPERT_GENERAL_V1`; viewer run information comes from execution. |
| `stage3_visualizer_ui` | Local Index interval state/constants: 20..5000 ms, default 200 ms; no persistence or presentation version. |

Normal labels: `Benchmark: EXPERT_GENERAL_V1`, `Algorithm: Stage-3 V1`,
`Physical: Model C · profile v1`. Viewer title: `Stage-3 Visualizer`;
`Playback: Index · N ms/step (presentation)` reflects the current interval.
Run identity and fingerprint remain visible.

[Architecture](../../ARCHITECTURE.md#stage-3-extended-version--settings-identity-separation)
preserves `Replay != Stage-3 Trace Playback != ZiNi Trace`. Presentation interval,
Replay elapsed time, `decision_compute_ns` and modeled physical time are separate.
Rendered UI cell size is not calibration identity.

## Final automated verification

Development interpreter: `C:\venvs\minesweeper\Scripts\python.exe`,
CPython **3.12.10 / 64-bit**. Commands ran from the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m unittest tests.test_stage3_identity tests.test_stage3_physical tests.test_stage3_benchmark_runner tests.test_stage3_benchmark_continuation tests.test_benchmark_modeled_time tests.test_benchmark_comparison tests.test_stage3_visualizer_launcher tests.test_stage3_visualizer_ui tests.test_stage3_execution tests.test_stage3_trace_player tests.test_stage3_execution_worker tests.test_stage3_execution_job tests.test_stage3_runner tests.test_stage3_planner tests.test_stage3_telemetry tests.test_stage2_semantic_golden tests.test_replay_directory_ui tests.test_replay_player -v
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m unittest discover -s tests -v
```

| Run | Tests / passed | Duration | Failures | Errors | Skips |
| --- | --- | --- | --- | --- | --- |
| Focused | 376 / 376 | 22.160 s | 0 | 0 | 0 |
| Full discovery | 1639 / 1639 | 79.857 s | 0 | 0 | 0 |

Coverage: frozen identity pins, physical authentication, canonical snapshot,
fail-closed continuation/comparison, UI authority substitution, interval/result
isolation, navigation/cursor/autoplay, three-field execution, pickle/job boundary,
frozen Stage-3, Stage-2 semantic golden and Replay/settings isolation.
Expected negative-path ZiNi diagnostics did not fail the suite. No 100k rerun.

## Fresh package verification

Fresh ignored root:
`results/stage3-identity-separation-acceptance/20261015-012718/`.
An isolated ASCII-path `build-env` used the existing [build method](../../BUILDING.md):
PyInstaller **6.22.3**, hooks **2026.8**, PyQt5 **5.15.11**, Qt **5.15.2**,
PyQt5-sip **12.19.0**, pyqtgraph **0.14.0**, numpy **2.5.3**, colorama **0.4.6**.
`pip-freeze.txt`, `python-version.txt` and `environment-install.log` preserve
the actual environment; the normal development environment was not modified.

```powershell
$acceptanceRoot = (Resolve-Path 'results/stage3-identity-separation-acceptance/20261015-012718').Path
$buildPython = Join-Path $acceptanceRoot 'build-env/Scripts/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $acceptanceRoot 'build-env/Lib/site-packages/PyQt5/Qt5/plugins/platforms'
$env:PYINSTALLER_CONFIG_DIR = Join-Path $acceptanceRoot 'pyinstaller-cache'
$profile = (Resolve-Path 'calibration/stage3_physical_profile_v1.json').Path
& $buildPython -B -m PyInstaller --noconfirm --clean --onedir --windowed --name Minesweeper --distpath "$acceptanceRoot/dist" --workpath "$acceptanceRoot/build" --specpath "$acceptanceRoot" --add-data "${profile};calibration" main.py
```

**Build PASS:** exit **0**, **51.0505613 s**, Windows x64 onedir/windowed.
PE machine `0x8664`, GUI subsystem `2`, native `qwindows.dll` present.
The normal import archive includes `stage3_identity`, physical/launcher/viewer
modules and both workers; no new hidden-import/data rule. Warning audit found
platform/optional imports and export names, including unused `pyqtgraph.opengl`
integration; no missing Stage-3 module was listed.

**Profile PASS:** source bytes equal
`dist/Minesweeper/_internal/calibration/stage3_physical_profile_v1.json`.
Both SHA-256 values:
`52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.

**Packaged worker PASS:** `Minesweeper.exe --stage3-execution-worker` used absolute
payload/result paths and an unrelated system temporary working directory, with
a 60-second timeout. Payload `{"token": 315001, "game_index": 0}`; exit **0**,
matching token, no error; result unpickled as `Stage3Execution`.
Complete deterministic spec/board/result/trace/decision values matched source,
excluding `decision_compute_ns`; runtime and object identity were not compared.

| Frozen game-0 equality check | Result |
| --- | --- |
| Status / trace count | WON / 227 |
| Total modeled time | 39,987,084 µs |
| First action modeled time | 126,005 µs |
| Fingerprint | `fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053` |

This is frozen-behavior equivalence, not a new performance claim.
Evidence: `focused-tests.log`, `full-tests.log`, `pyinstaller-build.log`,
`build-result.json`, `build-warning-audit.json`, `package-format.json`,
`packaged-worker-profile.json`, `manual-gui-smoke.json` and trusted-local
game-0 payload/result files.
Historical Foundation artifacts were not overwritten. No release ZIP/tag.

## Native packaged GUI smoke — PASS

**Manual tester: project user. Date: 2026-10-15 (Asia/Seoul).**
The user tested the fresh executable under the acceptance root above and reported
**"All five checks passed"** in this closeout session.

| Native packaged interaction | User-reported result |
| --- | --- |
| Launch application; open Stage-3 Visualizer from Counters | PASS |
| Separate launcher Benchmark / Algorithm / Physical labels | PASS |
| Run game 0; viewer opens as Stage-3 Visualizer with separate Algorithm / Physical labels | PASS |
| Playback starts at 200; changes to 20 and 5000 update the presentation label while total stays 39,987,084 µs | PASS |
| Close application cleanly | PASS |

This is user-performed native packaged acceptance, distinct from automated
offscreen/source tests and the packaged-worker equality check. The computer-use
runtime was unavailable to the agent; no autonomous GUI interaction or screenshot
evidence is claimed. Foundation cancellation/PID/shutdown acceptance was not
repeated because no lifecycle regression appeared.

## Compatibility and deferrals

`Stage3Execution` remains exactly `spec / board / result`; transport is unchanged.
No database migration, Replay format change, ZiNi change, planner-input change,
V1 algorithm change, Model C timing/profile-byte change, persistent Stage-3
setting or generic version/settings registry. Frozen specs, official 100k
artifacts and historical adjudication/evidence remain untouched.

Next active milestone: **Modeled-Time Playback / Synthetic Smooth
Cursor Presentation**; neither feature is implemented here.

Deferred: runtime application/release display/constant; selectable algorithms/
profiles; durable cross-version execution transport; persistent presentation
settings; presentation settings dataclass until an external consumer exists;
same-board Human / Stage-2 / Stage-3; representative boards / Timeline Analytics;
nearest equal-minimum-risk guess research; known-mine/no-flag; action-specific
timing; anisotropy; CPS/burst; richer/longer planning. Synthetic/interpolated motion
must remain presentation-only, never an actual OS trajectory claim.
Foundation F-2 packaged transport hardening remains **OPTIONAL / DEFER**; no new
evidence promotes it. Incremental-forward playback optimization remains deferred.

## Documentation verification

All **90 local Markdown link occurrences**, including **20 anchor references**,
across the seven edited documents resolve. No existing link checker was found;
paths and explicit/GitHub-style heading anchors were checked directly.
External URLs were excluded. Documentation-only scope, unchanged HEAD/profile
and an empty index were verified; `git diff --check` passed.

Final verdict: **STAGE-3 EXTENDED VERSION / SETTINGS IDENTITY SEPARATION —
FINAL ACCEPTANCE PASS / CLOSED**.

- [Current handoff](../CURRENT_HANDOFF.md)
- [Extended roadmap](README.md)
- [Documentation index](../README.md)
