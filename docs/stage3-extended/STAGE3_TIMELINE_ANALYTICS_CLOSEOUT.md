# Representative-board Demonstrations / Timeline Analytics — Closeout

**STAGE-3 EXTENDED TIMELINE ANALYTICS — FINAL ACCEPTANCE PASS / CLOSED**
— **2026-10-17 (Asia/Seoul)**. **BLOCKER 0 / REQUIRED 0**.
**Slices 0–4 COMPLETE / ACCEPTED**, including internal 3A/3B within Slice 3.
**Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED** by ChatGPT final adjudication.

Only this milestone closes; **Stage-3 Extended remains ACTIVE**. The
[accepted contract](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md) retains its technical
boundaries. This closeout records existing verification; it does not rerun tests,
selection, reports or official evidence generation.

## Qualified implementation identity and scope

Qualified implementation/source candidate:
**`4c488e033dd045f1c203ff500d824cfaffb7cc67` — `feat: add timeline analytics report`**.
This remains the qualified source identity after a later documentation-only
closeout commit. No future documentation commit SHA is inferred here. Live Git
is authoritative for current HEAD, branch, remote and integration state.

| Accepted slice | Commit |
| --- | --- |
| 0 — Contract | `b5d5b5acbe29529247bcf14b5751753c4a137d92` |
| 1 — Pure timeline analytics | `91d3bfd10a614126d1ec6667ad7da3741b9dbeed` |
| 2 — Pure deterministic exemplar selection | `72cbe6883816e10ff9a77878cb508e7f37459548` |
| Internal 3A — Immutable evidence opening / preflight | `c32e34c92a945f021a9aee36da2f85597e80b8ce` |
| Internal 3B — Accepted report / qualified candidate | `4c488e033dd045f1c203ff500d824cfaffb7cc67` |

Accepted implementation:

- [timeline_analytics.py](../../timeline_analytics.py) and
  [tests](../../tests/test_timeline_analytics.py): immutable pure per-run projection.
- [representative_boards.py](../../representative_boards.py) and
  [tests](../../tests/test_representative_boards.py): deterministic pure category selection.
- [telemetry_repository.py](../../telemetry_repository.py) and
  [tests](../../tests/test_telemetry_repository.py): explicit immutable read-only extension;
  default `mode=ro` remains unchanged, while authenticated stable preserved artifacts
  may use `mode=ro&immutable=1` through the existing public seam.
- [stage3_timeline_report.py](../../scripts/stage3_timeline_report.py) and
  [tests](../../tests/test_stage3_timeline_report.py): artifact authentication,
  selected-only action loading and a self-contained HTML / inline-SVG report.

No production Qt UI, new plotting dependency, algorithm, Model C, telemetry or
schema change was introduced.

## Final automated acceptance

Approved interpreter: `C:\venvs\minesweeper\Scripts\python.exe`.
Python **3.12.10, 64-bit AMD64**; `PYTHONDONTWRITEBYTECODE=1`.

| Verification | Discovered / run | PASS | Failures | Errors | Skips | unittest duration | Process elapsed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Focused / frozen closeout regression | 386 / 386 | 386 | 0 | 0 | 0 | 6.198 s | 6.935 s |
| Full source regression | 2184 / 2184 | 2184 | 0 | 0 | 0 | 141.186 s | 144.019 s |

The focused set covered report, selector, timeline, repository/codec/schema,
statistics/pairing, modeled-time/comparison and frozen physical/identity/telemetry
modules. Previously excluded solver/Engine cases were included. Ordinary
regression tests may execute Engine/solver code; this was not an official
benchmark or solver-evidence rerun. No skips require a waiver.

Authoritative full command, from repository root:

```text
C:\venvs\minesweeper\Scripts\python.exe -B -m unittest discover -s tests -v
```

Ignored local closeout evidence root:
`results/stage3-timeline-analytics-closeout/20261017T131224859Z/`.
Contents: `focused-tests.txt`, `full-tests.txt`, `acceptance-summary.json`.
The summary preserves commands, interpreter, counts, durations, hashes and
reconciliation. These local files are not tracked and must not be added to Git.

No fresh package/build/native GUI gate was required or run because this milestone
changed no production GUI/package surface.

## Preserved official artifact and model identities

| Accepted authority | SHA-256 |
| --- | --- |
| Stage-2 analysis DB | `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` |
| Stage-3 analysis DB | `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e` |
| G4 comparison | `f31226a660eda02a804ee41c66f233513fd950cac6f6123f36bf62578fbf5979` |
| G4 result | `09f228ee9a8ec96a934dbb94656a7cd6f03c7987640df267f5fd6818dd007cc0` |
| Frozen Model C profile | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` |
| Frozen Model C timing table | `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b` |

Final closeout verification reauthenticated these identities. Official artifact
hashes, sizes and modification timestamps were unchanged; no DB `-wal`, `-shm`
or `-journal` sidecars appeared. The verification phase used hash/stat reads of
official artifacts and existing authoritative Model C authentication, without
opening official DBs or rerunning real selection.

## Final and historical report identities

Final accepted corrected report:
`results/stage3-timeline-analytics/20261017T113748060625Z-99dafa139703/report.html`.
**470817 bytes**; SHA-256:
`b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3`.

Accepted report-script SHA-256:
`50f9d88e80b971596de59eadae1bb3bf96ee0d4da88d252684a7cbf0a15eb387`.
The report records generation HEAD
`c32e34c92a945f021a9aee36da2f85597e80b8ce` with `git_dirty=True`.
Its embedded script SHA matches the byte-identical working file and exact Git
blob committed in qualified candidate `4c488e033dd045f1c203ff500d824cfaffb7cc67`.
This is accepted provenance, not a mismatch or a claim that the report was
generated after that commit.

Historical pre-correction report:
`results/stage3-timeline-analytics/20261017T103913620889Z-54082dd14870/report.html`.
**469772 bytes**; SHA-256:
`277e6889d9ade1c944eabebeeec7fcca0a4524e496af449cd9b60e73676d6203`.

Both reports are ignored local evidence, not tracked repository links. Preserve
both without overwrite/deletion. Final verification inspected the existing
corrected HTML: **1,508 action rows, 16 inline SVGs, no JavaScript or external
assets**, all EMPTY categories visible. Neither report was regenerated.

## Fixed category exemplars and exact totals

These are **deterministically selected category exemplars**, **NOT a statistically
representative sample**. Signed `delta_us = Stage3_model_c_us - Stage2_model_c_us`.

| Category | Fixed game_index | WW delta_us |
| --- | ---: | ---: |
| Maximum Stage-3 WW advantage | 73758 | -27009085 |
| Median-delta WW | 73024 | -16487355 |
| Closest-to-zero Stage-3 WW advantage | 93557 | -7877513 |
| Stage-2 WW advantage | EMPTY | — |
| Exact WW tie | EMPTY | — |
| WL | EMPTY | — |
| LW | EMPTY | — |
| LL | 1 | — |

Lower-median zero-based rank: **18850 of 37702 WW**. Unique games:
**1, 73024, 73758, 93557**. No visual/manual substitution occurred. The selector
remains the authority; closeout verified the fixed report without rerunning it.

| Game | Outcome | Stage-2 / Stage-3 actions | Stage-2 / Stage-3 Model C us | Interpretation / reconciliation |
| --- | --- | ---: | ---: | --- |
| 1 | LL | 4 / 4 | 720354 / 720354 | Termination cost only; not time-to-win |
| 73024 | WW | 313 / 207 | 53655374 / 37168019 | Exact G4 delta -16487355 us |
| 73758 | WW | 320 / 177 | 57365067 / 30355982 | Exact G4 delta -27009085 us |
| 93557 | WW | 279 / 204 | 47034727 / 39157214 | Exact G4 delta -7877513 us |

## Independent audit and correction history

Independent Claude Code read-only audit authenticated and independently recomputed
selection, inspected the actual pre-correction report, and reproduced all **1,508
action rows and 16 SVGs**, with **0 mismatch**. Verdict: **BLOCKER 0 / REQUIRED 0**;
OPTIONAL O-1..O-6. ChatGPT promoted O-1 to REQUIRED R-1 for provenance/semantic
wording, then accepted its correction.

| Finding | Final disposition |
| --- | --- |
| O-1 / R-1 — Report provenance / semantic wording | SATISFIED |
| O-2 — Chart common scale | DEFER |
| O-3 — Parse-hashed-bytes TOCTOU | NONBLOCKING |
| O-4 — Selected-action SQL-test hardening | DEFER |
| O-5 — Additional synthetic failure branches | DEFER |
| O-6 — Extended run/git/config provenance | DEFER / NONBLOCKING |

No Claude re-audit after R-1 is claimed or required. R-1 changed report semantics
wording only and was subsequently source/test/report verified by ChatGPT/Codex.
O-6 would add convenience/detail; existing artifact/run/model/script identity is
sufficient. Regenerating an accepted report for that addition is not justified.

## Preserved semantic and research boundaries

- Both displayed timelines are **post-hoc Model C evaluations of persisted
  executed actions**. Stage 2 did not natively declare Model C. Stage 3 declared
  it during collection and checked its native total, but reduced persisted report
  events retain no native per-action cost or cursor fields.
- Stage-2 `decision_compute_ns` covers decision analysis; Stage-3 covers analysis
  plus planning. Historical scopes/environments differ; no cross-stage
  compute-speed winner is inferred.
- Stage-2 guess candidate count is exact-minimum-risk tie multiplicity / final
  selector pool size. Official Stage-3 candidate count is unavailable, including
  on guesses, and is not reconstructed.
- Missing native `cursor_before`, per-action `modeled_action_us`, Replay timestamps,
  full probability coordinate maps and chosen plans are not fabricated.
- Each run owns its completed-action-count axis; origin `(0,0)` is not an event.
  Equal action counts do not imply equal board state/progress. There is no shared
  execution clock or normalized progress. Model C cost is joint movement-plus-input
  cost, not measured movement time. LOSS cost is cost through termination, not
  time-to-win; paired speed interpretation remains WW-only.
- Human timeline support remains deferred; there is no Human Model C or shared
  Human/solver authority. No causal FLAG→CHORD, recoverable No-Flag savings,
  avoidable movement or other counterfactual savings claim is established.

Stage-3 V1 / Model C remain **CLOSED / FROZEN**. Preserve official 100k evidence,
both Timeline report runs and the closed Same-board feature. ZiNi Improvement
remains **CLOSED** and its final holdout remains unopened. Human Mouse Trace,
Replay, solver trace and presentation authorities remain separate. No official
benchmark rerun, report regeneration, source/test change, release/tag or package
work is part of this documentation closeout.

**NEXT:** human/domain interpretation of the accepted fixed exemplars and report,
to choose and specify the first actual Extended algorithm research direction.
No new algorithm is authorized or implemented by this closeout. Any algorithm
change or research implementation requires a separate explicit scope/specification
decision. See the [current roadmap](README.md#roadmap) and
[current handoff](../CURRENT_HANDOFF.md).
