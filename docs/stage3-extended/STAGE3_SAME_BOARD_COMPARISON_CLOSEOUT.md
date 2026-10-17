# Same-board Human / Stage-2 / Stage-3 Comparison — Closeout

**FINAL ACCEPTANCE PASS / CLOSED — 2026-10-17 (Asia/Seoul).**
Slices 0–5 are **COMPLETE / ACCEPTED**. ChatGPT accepted automated Slice 5A and
the project user's packaged native/manual Slice 5B. Stage-3 Extended remains
**ACTIVE**; Stage-3 V1 / Model C remain **CLOSED / FROZEN**.

This record preserves the qualified implementation/package and final acceptance.
Later branch existence, merge history and latest HEAD must be read from live Git.
This closeout creates no release, tag or ZIP. See the
[accepted contract](STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md).

## Qualified identity and scope

- Qualified development branch at acceptance: `feature/stage3-same-board-comparison`.
- Qualified source/package candidate: `a59d0d963bdf1544a03968163b884342e2797ee0`
  — `test: fix replay statistics UI fixture` (test-only; no production behavior change).
- Accepted Slice-4 implementation/docs: `d81caa95fc0e181d199fdf4c770873241f0f1eac`
  — `feat: add same-board comparison UI`.
- Final automated evidence: `results/same-board-comparison-final-acceptance/20261017-022243/`.
  [acceptance-summary.json](../../results/same-board-comparison-final-acceptance/20261017-022243/acceptance-summary.json)
  retains exact commands, counts, skip identities, logs, hashes and process evidence.
- Accepted package: `results/same-board-comparison-final-acceptance/20261017-022243/dist/Minesweeper/`.
  Keep the complete onedir directory, including `_internal`, with `Minesweeper.exe`.

| Slice | Accepted scope |
| --- | --- |
| 0 | Engineering contract |
| 1 | Pure domain/admission, canonical layout identity, full-stream reconstruction and opening qualification |
| 2 | Isolated execution/metrics and parent-owned worker lifecycle; internal 2A/2B complete |
| 3 | Pure deterministic playback with independent remembered indices |
| 4 | Read-only result viewer and captured-source launcher/main integration; internal 4A/4B complete |
| 5 | Automated source/package/lifecycle acceptance, user native/manual acceptance and documentation closeout |

Internal subdivisions are not new roadmap milestones. The preserved Human
finalized layout is executed independently by unchanged Stage 2 and frozen
Stage-3 V1. Canonical solver `OPEN(0,0)` may legitimately lose on an already-fixed
board; no relocation, regeneration or retry restores fresh-game placement safety.
Human metadata, declaration and valid terminal reconstruction do not prove
exclusively-Human history or controlled experimental conditions.

The launcher retains one immutable context from a completed Live game or the
entire retained Replay, independent of displayed index. Only token + fixed board
enter the worker. Human Replay/Mouse Trace, native solver streams and separately
labeled metrics remain authorities. Playback never reruns solvers; each run owns
its index. Current reconstructed status is distinct from final outcome.

## Automated source and package acceptance

Development interpreter: `C:\venvs\minesweeper\Scripts\python.exe`.
Both development and fresh ASCII-path build environments used Python **3.12.10 x64**;
fresh pip was **25.0.1**, with the [documented pinned stack](../../BUILDING.md#build-and-test).

| Verification | Discovered | Passed | Failures | Errors | Skips | Test duration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Source focused | 916 | 916 | 0 | 0 | 0 | 44.286 s |
| Full development suite | 2085 | 2085 | 0 | 0 | 0 | 118.136 s |
| Fresh-environment full suite | 2085 | 2060 | 0 | 0 | 25 | 110.595 s |

Full discovery used `python.exe -B -m unittest discover -s tests -v` under the
respective interpreter. The 25 fresh-environment skips are only the previously
accepted optional image/video replay-validation dependency category, not passes.

Fresh PyInstaller onedir/windowed build: **exit 0, 63.789 s**; AMD64 / PE32+ / GUI
subsystem. Required Same-board, Replay, Mouse Trace and Stage-3 modules were
verified in the archive through normal imports; `qwindows.dll` was present. No
hidden-import rule was added. Full warnings are retained; the optional unused
`pyqtgraph.opengl` / missing `OpenGL` collection warning did not block acceptance.

- EXE SHA-256: `4893d24e1f9d50e47008f94aff4399188123331f49d3cd8d70ab3bc5eab6a5e8`.
- Frozen profile SHA-256: `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
- Bundled `calibration/stage3_physical_profile_v1.json` is byte-identical to source.

### Packaged workers and equivalence

`--same-board-execution-worker` ran from an unrelated cwd with distinctive large
integer tokens. Exact envelopes, fixed layout/fingerprint, native results/traces,
separate metrics and integer Model C totals passed validation; Human history and
Mouse Trace were not transported.

| Fixed board | Stage 2 / Stage 3 | Actions per solver | Model C cost through termination per solver |
| --- | --- | ---: | ---: |
| `ReplayBoard(4, 1, 1, {(1,0)})` | WON / WON | 4 | 504,020 µs |
| `ReplayBoard(2, 2, 1, {(0,0)})` | LOST / LOST | 1, canonical `OPEN(0,0)` | 126,005 µs |

The mined-origin losses were successful execution results, without regeneration
or retry. Source/package deterministic layout, action/status streams, outcomes,
modeled costs and counts matched. Runtime-dependent decision-compute measurements
and Stage-2 Replay elapsed **engine-clock timestamps** were excluded from strict
equality, with exact values/reasons retained. This is a runtime-clock boundary,
not an arbitrary mismatch waiver or use of Replay elapsed as modeled time.

Wrong arity (exit 2), malformed/missing payload, invalid request and unsupported
board checks passed with no fabricated solver outcome. Atomic temporary files
were absent; owned children were reaped and private probe directories removed.
Existing dispatches remained independent: packaged Stage-3 game 0 matched source
with **227 traces / 39,987,084 µs**; ZiNi known-board output matched source. Their
invalid-input/arity checks also passed. These are compatibility checks, not new
algorithm qualification.

### Real packaged-worker ownership and native startup

Actual production Qt owners used actual packaged children via an ignored external
harness; no production change was made. Exact directories and terminal records
are in [packaged-lifecycle.json](../../results/same-board-comparison-final-acceptance/20261017-022243/packaged-lifecycle.json).

| Case | Owned PID | Terminal path |
| --- | ---: | --- |
| Job safe success | 30496 | succeeded |
| Job mined-origin success | 5696 | succeeded |
| Job Cancel | 14588 | cancelled |
| Launcher success / result reopen | 27568 | succeeded; reopen without rerun |
| Launcher Cancel | 13520 | cancelled |
| Active launcher close | 33728 | shutdown/close |
| Active main close | 31532 | main-close shutdown |

All seven passed: child reaped and exact owned job directory removed. Success
retained the original Human context, Replay and Mouse Trace attachment identities.
Cancellation/close cases observed a live child before the operation.

Separately, the fresh native package exposed a responsive real window with its
packaged `qwindows.dll` loaded, closed normally with exit 0 and left no owned
orphan process. This was startup/liveness smoke, not manual feature acceptance.
Observation retries are recorded in the evidence; no package rebuild was needed.

## User packaged native/manual acceptance

**Tester: project user; date: 2026-10-17 (Asia/Seoul); exact package: the fresh
`20261017-022243/dist/Minesweeper/` directory above.** ChatGPT accepted the user's
reported interaction evidence. Screenshots alone are not asserted to prove these gates.

| Gate | User-reported result |
| --- | --- |
| A — Native startup | PASS |
| B — Completed Live Human source | PASS |
| C — Normal Run / automatic result viewer | PASS |
| D — Result facts and separated metrics | PASS |
| E — Independent remembered Human / Stage 2 / Stage 3 indices | PASS |
| F — Human-only complete Mouse Trace | PASS |
| G — Retained result reopen without rerun | PASS |
| H — Loaded Replay captures the entire Replay regardless of displayed index | PASS |
| I — Cancel | PASS |
| J — Launcher close during active run | PASS |
| K — Main close during active Comparison | PASS |
| L — Existing Replay / Mouse Trace / Stage-3 Visualizer compatibility | PASS |

Observed example: **Human WON / Stage 2 LOST / Stage 3 LOST**. Both solver losses
were shown as legitimate completed comparison results, not execution failures.
Loading a Replay at another displayed index still captured its complete original
stream; the new result viewer began at Human index 0.

The ignored automated summary remains its original **READY FOR USER PACKAGED
MANUAL ACCEPTANCE** snapshot. This tracked closeout records the subsequent manual
PASS and final verdict; raw evidence was not rewritten to imply prior manual testing.

## Historical blocked attempt and correction

Preserve `results/same-board-comparison-final-acceptance/20261017-014937/` as
**historical BLOCKED**: 2085 discovered, 2076 passed, 9 errors, 0 failures/skips.
The isolated `MinesweeperUIEngineOwnershipTests` fixture bypassed `_init_ui()`
without supplying the newly mandatory `same_board_comparison_action`.

The correction changed only `tests/test_replay_statistics.py`: its local UI stub
supplies a `Mock` action while the real state-update helper still runs. Production
required no correction. Review verification passed **9/9** affected ownership
tests, **158/158** related regressions and **2085/2085** full source tests, all with
zero failures/errors/skips. Commit `a59d0d9` superseded `d81caa9` as the clean
acceptance candidate, and 5A restarted in a new root; the blocked attempt was not
erased or relabeled.

## Audit disposition and nonblocking UX

Independent Claude Code read-only Slice-4 audit: **BLOCKER 0 / REQUIRED 0 /
OPTIONAL 4 / PASS**. Claude did not rerun tests. ChatGPT independently reviewed
source/tests and accepted without production correction.

- **O-1 — DEFER / evidence-triggered:** theoretical matching success after cancel
  intent; the current real job contract and acceptance evidence do not expose it.
- **O-2 — SATISFIED:** Slice 5A supplies real packaged-worker/job/launcher lifecycle evidence.
- **O-3 — NONBLOCKING:** 2085/2085 development tests pass; no further production defect emerged.
- **O-4 — DEFER:** captured-source wording polish; manual acceptance reported no
  confusion requiring production to be reopened.

**Comparison slider track click — OPTIONAL / DEFER.** Standard `QSlider` track
clicks page-step rather than jump exactly to the click. Drag and arbitrary
selected-run seek work correctly; exact track-click jumping was not a Slice-4
requirement. A later narrow JumpSlider-style change could retain the same playback
authority. Changing production now would invalidate the accepted package candidate.

**Human versus solver path presentation — KEEP intentional separation.** Human
Mouse Trace is recorded pointer presentation data; the independent Stage-3
Visualizer's cursor is synthetic/model-based. Stage 2 has no Comparison cursor
overlay, and Comparison does not add either solver overlay. Removing this
distinction would lose truthful authority labels. Any future solver-path display
requires explicit synthetic/modeled labeling, never a Human Mouse Trace label.

## Preservation and next roadmap state

Stage-3 V1 specs, runner/planner, Model C profile/table and historical evidence
remain unchanged. No official 100k benchmark was regenerated and no reserved ZiNi
holdout was consumed. No release/tag/ZIP was created; generated artifacts remain
ignored under `results/` and temporary build paths.

There is no remaining Same-board implementation task. Stage-3 Extended remains
**ACTIVE**. The next roadmap candidate is **Representative-board demonstrations /
Timeline Analytics — NEXT CANDIDATE / NOT BEGUN**; first actual Extended algorithm
research remains **LATER**. Closure does not authorize analytics implementation,
algorithm research, a new physical model, Comparison solver cursor overlays or
provenance schema expansion. The [current handoff](../CURRENT_HANDOFF.md) owns recovery state.
