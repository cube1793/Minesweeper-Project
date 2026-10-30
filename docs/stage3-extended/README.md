# Stage 3 Extended

## Status

Stage-3 V1은 **FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED**이며 frozen baseline이다.
ZiNi Improvement도 **CLOSED / V1 RETAINED**이고 미개봉 최종 holdout은 그대로 유지한다.
**Stage-3 Extended는 ACTIVE**다. 이 문서는 의존 관계에 따른 roadmap이며 고정 구현 일정이 아니다.

Current state: **2026-10-31 (Asia/Seoul), PRE-ACTUAL-E2 — FRESH R0-A V2 ACCEPTED / REMEDIATION PARTIAL SUCCESS / TIMING PROFILING FIX REQUIRED BEFORE EXECUTION**.
At this refresh's read-only preflight, `main` / locally known `origin/main` both
resolved to pre-refresh documentation HEAD `a7abce49f4f98d2db02695943c299f86a212344d`;
ahead/behind **0/0**, clean index/worktree. Qualified technical anchor remains
`48f6ebc97e6c4d3ed4a746a92a8d169783803bf9`; the intervening change is docs-only.
Fresh Attempt #2 records `a7abce49...` with the same technical closure.
[CURRENT_HANDOFF](../CURRENT_HANDOFF.md) is the primary durable current-state authority;
this document is the current Stage-3 Extended roadmap/index.
Historical R0-A run/review source remains `c0bc270bce1996797f9ecec80e79ea8998d3205d`.
Accepted technical harness ancestor:
`7e7f847816fedb77cef67b576eab665afabfbfbf`
— `feat: add Program K E2 R0 harness`; its direct parent is
`e6593f7a99af2f0dd941eda7ee53a5164c79a2bd`.

**Representative-board Demonstrations / Timeline Analytics — FINAL ACCEPTANCE
PASS / CLOSED** (2026-10-17). **Slices 0–4 COMPLETE / ACCEPTED**, internal 3A/3B 포함;
**BLOCKER 0 / REQUIRED 0**. Qualified source candidate는
`4c488e033dd045f1c203ff500d824cfaffb7cc67`이며 이후 documentation-only commit과 구분한다.
Focused/frozen **386 PASS**, full source **2184 PASS**, failures/errors/skips 모두 0.
[최종 closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)과
[수용 계약](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md)을 보존한다.
**Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer —
FINAL ACCEPTANCE PASS / CLOSED** (2026-10-18), **Slices 0–4 COMPLETE / ACCEPTED;
BLOCKER 0 / REQUIRED 0**. Qualified source `ff6358ae62b6f343bda36069d7164bda9aebee74`.
See the [final closeout](STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md) and
[final contract](STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md).
**Visualization Usability Polish — FINAL ACCEPTANCE PASS / CLOSED** (2026-10-18).
Qualified implementation `31630dd6ffa2301c41534fca3b003838d865f313`; see the
[closeout](STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md).
**Fixed-Exemplar Human/Domain Interpretation — FINAL ACCEPTANCE PASS / CLOSED**
(2026-10-19), **BLOCKER 0 / REQUIRED 0**; see the
[closeout](STAGE3_FIXED_EXEMPLAR_INTERPRETATION_CLOSEOUT.md).
Gameplay inspection is COMPLETE; additional gameplay required: NONE.
Milestones **1–9 remain CLOSED**. Milestone **10** selected **Program K**; its
[research specification](STAGE3_PROGRAM_K_RESEARCH_SPEC.md) and
[Gate-R E0/E1 research protocol](STAGE3_PROGRAM_K_GATE_R_PROTOCOL.md) are
**FROZEN / ACCEPTED**. Gate-R E0/E1 implementation qualification is
**CLOSED / ACCEPTED**; Actual E1 is **E1_PASS / E1_QUALIFIED / ACCEPTED** with
`progression_allowed = true`; see the
[E1 final closeout](STAGE3_PROGRAM_K_E1_CLOSEOUT.md).

The [E2 Effectiveness Protocol](STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md) is
**FROZEN / ACCEPTED — CONTENT FREEZE PASS / BLOCKER 0 / REQUIRED 0**.
Program K E2 implementation slices **I1–I8 are 8/8 COMPLETE / ACCEPTED**; I0 is
accepted architecture mapping/discovery and is excluded from that denominator.

The [R0 Attribution Amendment v1](STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md)
is **CONTENT-FROZEN / ACCEPTED** at exactly **58,052 bytes**, SHA-256
`5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`;
final independent exact-byte re-audit:
**PASS — BLOCKER 0 / REQUIRED 0**.

Amendment conformance (`cdba3513`), exact N=10000 target counts/synthetic
selection, and setup-containment repair (`e6593f7`) are complete/accepted.
**R0 harness at `7e7f847`: FINAL ACCEPTANCE PASS / COMMITTED / PUSHED;
BLOCKER 0 / REQUIRED 0 / OPTIONAL 0.**

**Historical Real R0-A: COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED; no rerun.**
Its post-run integrity review and static follow-on review are complete. The
accepted observations establish two independent static blocks: the frozen
execution-admission projection exceeds 12 hours at every candidate N/concurrency,
and the required synthetic R0-B family minima exceed the 16 GiB archive ceiling.
Both remain **STATICALLY BLOCKED; historical proof preserved** for the old
source/representation; they are not Program K effectiveness results.
Remediation engineering investigation: **CLOSED / ACCEPTED**. The
[exact remediation design V1.3.1](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md) is
**FINAL DESIGN ACCEPTED / FROZEN BY EXACT TRACKED BYTES**; the
[live acceptance receipt](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md)
records **BLOCKER 0 / REQUIRED 0 at the design boundary; design phase CLOSED**.
Remediation **1A–1W: 23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED**.
**FRESH R0-A FINAL PREFLIGHT — PASS** at the exact technical source above;
**BLOCKER 0 / REQUIRED 0 / OPTIONAL 1**. Accepted USER-host focused E2 regression:
**1513/1513 PASS**, failures/errors/skips **0/0/0**, process exit **0**.
These are accepted preflight results, not checks rerun for this documentation refresh.
**Fresh R0-A V2 Attempt #2: COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED**
as operational calibration evidence. Overall remediation is **PARTIAL SUCCESS**:
the historical static whole-archive blocker is resolved by the Fresh representation,
but all 18 comparable route walls regressed and realized R0-B constructibility is
not yet established. Current c4 P/O-only B1000 already exceeds the launcher ceiling.
Historical evidence/proofs remain unchanged for their original source/representation.

External timing-profile-v1: **PREPARED / NOT EXECUTED**; independent review
**FIX REQUIRED BEFORE EXECUTION**, mandatory **B1 + R1–R3**. Both phases are
**NOT AUTHORIZED**, with no profiling measurement. Intended next work is minimal
external corrections → new pins → independent delta review → separately authorized
production-import-free Job isolation dry check, before considering Phase 1 approval.
Phase 2 P/O needs a separate evidence-supported hash-bound gate; see the
[current Program K boundary](#current-program-k-boundary) below. This documentation
refresh grants **no execution authority**. A separately approved docs-only
commit/push does not change the qualified technical anchor or authorize timing
profiling, R0-B, Actual E2, or any other experiment.
Real R0-B is
**NOT RUN / NOT AUTHORIZED**; this is not a failed R0-B run. Complete R0
adjudication is **NOT DONE**. Final N/concurrency are **NOT SELECTED**, and the
final E2 Operating Envelope is **NOT SELECTED / NOT FROZEN**.
Actual E2 is **NOT RUN / NOT AUTHORIZED**; effectiveness is **NOT ESTABLISHED**.
E3 is conditional/not triggered; Gate P, production integration and native K visual
acceptance are not started. Program K final closeout is not done; milestone 10
research remains **ACTIVE**.

첫 milestone **Execution / Playback / Visualizer Foundation**은
**FINAL ADJUDICATION PASS / CLOSED (2026-10-14)**다.
자동 검증과 실제 Windows worker/profile/startup, 사용자의 packaged interactive
acceptance, 독립 Claude 감사 및 ChatGPT 최종 판정이 모두 PASS다.
[최종 판정](STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)에 종료 범위와 F-1/F-2 처분을 기록했다. [Slice 5 수용 기록](STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)에
수동 tester/date, 네 terminal path의 PID·job-directory cleanup 및 controls PASS를 기록했다.
Foundation 판정은 해당 milestone만 닫으며 Stage-3 Extended 전체는 계속 active다.

## Foundation — closed / integrated

- Execution integration audit: 구현에 반영되어 완료.
- Slice 1 — Execution Context + Pure Trace Playback (`cf7544b`).
- Slice 2 — Subprocess Execution Worker (`d100a49`).
- Slice 3 — Read-only Stage-3 Visualizer Window (`490a8cf`).
- Slice 4 — Application Integration + Process Lifecycle (`b9af830`; pre-Slice-5 baseline).
- Slice 5 — Acceptance / Packaging / Documentation Closeout (`18964ad`): **CLOSED**, committed/merged/pushed.

Full commit identities and the dated Git baselines are in the acceptance and final
adjudication records. `18964add02c508d67429ef29cb59ce879c01017d` is the Slice 5
documentation closeout / independent-audit baseline, not a permanent latest HEAD.
Current components are `Stage3Execution`, worker, parent-owned `Stage3ExecutionJob`,
launcher, pure `Stage3TracePlayer` / `Stage3ModeledPlayback` and execution-only viewer. Indexed
`EXPERT_GENERAL_V1` execution is independent of the current Live/Replay board.

## Foundation final adjudication — CLOSED

Historical 2026-10-14 Foundation acceptance and user-performed packaged manual acceptance are complete.
Normal success, Cancel, launcher-close and main-close during active jobs passed,
with each owned worker gone and job directory removed. Parent PID 5352 also exited
on main close. Playback, responsiveness and retained-result reopen passed.
The Foundation documentation closeout changed no production Python, profile or playback-seek behavior.
Source tests: **1628 passed, 0 failures/errors/skips** in the development environment.
The independent audit also passed: focused **122**, frozen protection **92**,
Stage-2 / ZiNi / Replay / Stage-3 benchmark boundary **86**, full suite **1628**
with **0 failures/errors/skips**, and packaged-worker deterministic equivalence.
ChatGPT final adjudication: **BLOCKER 0 / REQUIRED production 0**.
F-1 is the required documentation-only historical/current-state correction,
addressed by this closeout; it is not an implementation blocker.
F-2 remains **OPTIONAL / DEFER** for future worker/release transport hardening.
That Foundation closeout published no release/tag.

## Version / Settings Identity Separation — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**.
[Closeout evidence](STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md) records the live
implementation baseline, 376 focused / 1639 full tests (zero failures/errors/skips),
fresh Windows package/profile/worker equivalence and user-performed native GUI PASS.

- Public Fixed Identities (`858dc1a`): immutable fixed V1 algorithm identity,
  physical-owner identity descriptor and unchanged benchmark snapshot consumers.
- Identity-backed Visualizer Labels (`e04d4e8`): separate Algorithm / Physical
  labels and a current `Playback: Index · N ms/step (presentation)` label.

| Identity | Current ownership / meaning |
| --- | --- |
| Application/release | Release/tag/build documentation; no runtime version constant, and current main is not historical v0.2.0 |
| Stage-3 algorithm | `stage3_identity.STAGE3_V1_IDENTITY`; distinct from telemetry semantic version and execution configuration |
| Physical model/profile/table | `stage3_physical.MODEL_C_V1_IDENTITY` and substantive authentication; `Model C` alias is separate |
| Playback/presentation | Viewer-local Index/Modeled-Time; Index 20..5000 ms, default 200 ms; modeled default 1×; no QSettings or presentation version |

`Stage3Execution(spec, board, result)`, worker transport and all frozen semantics
remain unchanged. No migration, algorithm/profile selectors, registry or new runtime app version.

## Modeled-Time Playback / Synthetic Smooth Cursor Presentation — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**.
[Closeout evidence](STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md) records Slice 1–3 commits,
254 focused / 1699 full tests with zero failures/errors/skips, a fresh package,
frozen profile equality, packaged worker equivalence and the project user's
native packaged GUI report **"A–K passed"**.

- TracePlayer uses failure-atomic incremental `next()`; arbitrary seek and previous
  retain reconstruction from index 0.
- The Qt-independent controller owns exact partial modeled time, monotonic anchoring,
  pause/resume, speed and multi-action catch-up using recorded durations.
- Index remains default, 20..5000 ms/step, default 200. Modeled-Time uses
  0.25× / 0.5× / 1× / 2× / 4× / 8×, default 1×, without persistence.
- The UI requests frames every 16 ms; the controller clock is authoritative.
  Partial frames update only the overlay; catch-up refreshes the board once.
- Straight smoothstep `q = u²(3 - 2u)` uses rendered cell centers. Same-cell actions
  stay stationary; no separate dwell model. Actions commit at modeled boundaries.
  Pause preserves partial progress; manual navigation and mode changes cancel it.

The synthetic cursor is presentation, not an actual OS trajectory or physical
acceleration model. Rates/easing never alter recorded costs, Model C or planner input.

## Human Mouse Trace / Path Visualization — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-16)**.
[Closeout evidence](STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md) records qualified
implementation/package SHA `e32145fa5c114e1ce500ad2e837ef6000cc49cca`,
**627 focused / 1825 full source PASS**, fresh-environment **1800 PASS / 25 optional
skips**, packaged workers/native GUI/Replay v2 verification and final user native PASS.

- Actual Live-board event samples use board-local Qt logical pixels, exact subpixel
  positions and an independent monotonic trace clock. No timer sampling,
  min-distance filtering or semantic point dropping; continuity breaks form segments.
- Recording defaults ON per application/session and locks at the first committed
  timed human OPEN/FLAG. OPEN observes L release; FLAG observes R press.
  Untimed pre-start CHORD does not start trace. Recording OFF at the lock point,
  an actual Auto action or Replay append failure after a committed human action
  invalidates the Human trace.
- Action markers reference actual ReplayEvent indices. Replay v2 carries the
  separate trace attachment; v1 remains readable and trace-free. Display is optional.
- Physical gesture fidelity includes independent Mode-A/C R-press FLAG and
  origin-independent Mode-B BOTH, first-release CHORD at the current target,
  repeated overlaps and FLAGGED-center neighborhood preview.
- Primitive recorder storage, pre-start gating, transformed-geometry caching and
  a **16 MiB** bounded raster cache/fallback preserve exact samples. User testing
  accepted trace ON after hardening and found no noticeable final-package regression;
  this is not a zero-overhead claim.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human trace is pointer presentation data, not OS-global tracking, synthetic Stage-3
motion, Model C calibration evidence or solver input. Frozen V1 and official 100k
results retain their original identity and meaning.

## Roadmap

1. **CLOSED** — Execution / Playback / Visualizer Foundation.
2. **CLOSED** — Version / Settings Identity Separation.
3. **CLOSED** — Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **CLOSED** — Human Mouse Trace / Path Visualization.
5. **CLOSED** — Same-board Human / Stage-2 / Stage-3 Comparison (Slices 0–5 COMPLETE / ACCEPTED).
6. **CLOSED** — Representative-board Demonstrations / Timeline Analytics;
   Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 1 — Pure timeline analytics COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT final review.
   Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE / ACCEPTED.
   Internal Slice 3A — accepted-evidence opening correction / preflight COMPLETE / ACCEPTED.
   Internal Slice 3B — selection / selected-action report COMPLETE / ACCEPTED.
   Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED.
7. **CLOSED** — Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer;
   Slices 0–4 COMPLETE / ACCEPTED; final qualified source `ff6358a`; R-2/O-5 CLOSED.
8. **CLOSED** — Visualization Usability Polish on Same-board Comparison and
   Stage-3 Visualizer; qualified implementation `31630dd6ffa2301c41534fca3b003838d865f313`.
9. **CLOSED** — Fixed-Exemplar Human/Domain Interpretation;
   [final closeout](STAGE3_FIXED_EXEMPLAR_INTERPRETATION_CLOSEOUT.md).
10. **ACTIVE — Program K: Logical Known-Mine Capability + Selective Physical Materialization** —
    [frozen Program K specification](STAGE3_PROGRAM_K_RESEARCH_SPEC.md),
    [frozen Gate-R E0/E1 protocol](STAGE3_PROGRAM_K_GATE_R_PROTOCOL.md),
    [accepted Actual E1 closeout](STAGE3_PROGRAM_K_E1_CLOSEOUT.md),
    [frozen E2 Effectiveness Protocol](STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md),
    and [frozen R0 Attribution Amendment v1](STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md).
    **I1–I8 = 8/8 COMPLETE / ACCEPTED.** Amendment conformance, target
    counts/synthetic selection, setup repair and R0 harness are accepted.
    **Historical Real R0-A is COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED; no rerun.**
    Remediation investigation is **CLOSED / ACCEPTED**; V1.3.1 is **FINAL DESIGN
    ACCEPTED / FROZEN BY EXACT TRACKED BYTES**. Remediation **1A–1W is 23/23
    COMPLETE / ACCEPTED / COMMITTED / PUSHED**. **Fresh R0-A Final Preflight PASS**
    at technical source `48f6ebc` remains accepted history. **Fresh V2 Attempt #2
    is COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED**, with documentation/
    run source HEAD `a7abce49...`. Remediation is **PARTIAL SUCCESS**: static storage
    blocker resolved, timing worsened. External profiling is **PREPARED / NOT
    EXECUTED / FIX REQUIRED BEFORE EXECUTION**; B1 + R1–R3 correction, re-pinning,
    independent delta review and a separately authorized import-free Job dry check
    precede Phase 1 authorization consideration. Both profiling phases are
    **NOT AUTHORIZED**; Phase 2 never starts automatically. R0-B and Actual E2
    remain **NOT RUN / NOT AUTHORIZED**.
    Final N/concurrency are **NOT SELECTED**; the final E2 Operating Envelope is
    **NOT SELECTED / NOT FROZEN**. No milestone 11+ is frozen.

### Current Program K boundary

Program K is the whole research program; E2 is its effectiveness experiment.
Gate P is later production/integration qualification after E2/any triggered E3.
The current position remains **PRE-ACTUAL-E2**.

The bounded experimental Program K implementation and Gate-R history remain
accepted. Full P-8 is **PASS / ACCEPTED**, Actual E0 is
**PASS / QUALIFIED / ACCEPTED / CLOSED**, and Actual E1 is
**E1_PASS / E1_QUALIFIED / ACCEPTED / CLOSED** with `progression_allowed = true`.
G8 remains **NOT_APPLICABLE** in E1 because effectiveness belongs to E2.
Actual E1 run `e1-20261022T003214Z-fba3da048d46` had a supervised execution wall
of **6,617.328 s ≈ 1h50m17s**. Its complete launcher took about **28 h** because
assessment/persistence/readback/reconstruction/report work followed execution;
28 h is neither modeled gameplay time nor supervised execution time. The
[E1 closeout](STAGE3_PROGRAM_K_E1_CLOSEOUT.md) preserves this historical debt.
E1 does **not** establish Program K effectiveness.

The [E2 Effectiveness Protocol](STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md) is
**FROZEN / ACCEPTED — CONTENT FREEZE PASS / BLOCKER 0 / REQUIRED 0**.

Program K E2 implementation:

| Slice | State | Accepted commit |
| --- | --- | --- |
| I0 | ACCEPTED architecture mapping; excluded from denominator | n/a |
| I1 | COMPLETE / ACCEPTED | `aa687d2627dceeb037a6f79e1f4a7017e38c13f7` |
| I2 | COMPLETE / ACCEPTED | `441e165acea308ba885615c25b7cd244b6a5f3ef` |
| I3 | COMPLETE / ACCEPTED | `9c8acef772cc71de0dae09e4e238ed42bf05a1e4` |
| I4 | COMPLETE / ACCEPTED | `f9a213b15e990cc50dedad6c8c10c42519593af7` |
| I5 | COMPLETE / ACCEPTED | `bbc2d0ada1e42e1770085a7d5454f0f0d1929fbe` |
| I6 | COMPLETE / ACCEPTED | `9fe69da293293ab22ad5c7a25cc3341863a10584` |
| I7 | COMPLETE / ACCEPTED | `1e6355ecfc9497338d75ef3e723fddf2445d378b` |
| I8 | COMPLETE / ACCEPTED | `9071469e2e4a884722ea02e2faea3441d916876c` |

**I1–I8 = 8/8 COMPLETE / ACCEPTED.** This is implementation progress only;
Program K effectiveness remains **NOT YET ESTABLISHED**.

#### R0 Attribution Amendment v1 — frozen authority

The [R0 Attribution Amendment v1](STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md)
was added after R0 boundary auditing exposed attribution gaps that were not
representable by the original readiness projection.

Accepted exact identity:

- byte length: `58,052`
- SHA-256:
  `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`
- final independent exact-byte re-audit:
  **PASS — BLOCKER 0 / REQUIRED 0** (historical audit also recorded OPTIONAL 5)
- final disposition:
  **CONTENT-FROZEN / ACCEPTED**

The amendment preserves the frozen treatment/selector/bootstrap/effect-gate
semantics and changes only enumerated R0 attribution/admission semantics.
Important accepted additions include route-specific Oracle wall accounting,
`I_OK`, rank-0 shared-reference byte ownership, zero-row Oracle support,
fixed-allowance/payload/containment checks and synthetic-domain R0-B dominance.

The authoring header may remain `CANDIDATE — NOT CONTENT-FROZEN / NOT ACCEPTED`;
the external freeze receipt is the live freeze-state authority. Do not edit the
content-frozen bytes merely to change the header.

#### Accepted conformance / selection / setup repair / harness

- **Amendment conformance — COMPLETE / ACCEPTED:**
  `cdba3513c23df77ba44449af1e551889a6954768`. Historical qualification:
  focused `386/386`, E2 `666/666`, related Stage-3/Model-C `116/116`, and full
  isolation-aware `4025/4025 PASS` (`4019 MAIN + 6 ISOLATED`). The earlier
  pre-amendment `4005/4005` candidate gate remains historical. Ordinary combined
  discovery's known `ProgramKSlice7SupervisorTests` coordinator-memory
  accumulation interaction is resolved by the accepted isolation boundary;
  do not reopen it or repeat direct monolithic discovery.
- **Accepted target counts / synthetic selection:** exact real N=10000 only,
  `U_KD = 505`, `I_OD = 2`, `I_OK = 3`. Synthetic ordinal **5**, range
  **[2,000,000,050,000, 2,000,000,060,000)**, digest
  `b78485dc50dc051d42645059bb86c39c1d4ca9db6cc3ba3be9d9290413831efb`;
  `U_KD_SYN = 506`, `I_OD_SYN = 4`, `I_OK_SYN = 4`, dominance **+1 / +2 / +1**.
  No auxiliary O∩D/O∩K fixture was needed; no other real N was counted.
  [Accepted selection receipt](../../results/program-k-e2-r0-selection/20261024T122548.464267Z-9fb5a7c7/selection-receipt.json):
  **7,364 bytes**, SHA-256
  `72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c`.
  Selection performed no real R0 or Actual E2. Do not recount/re-search.
- **Setup-containment repair — FINAL ACCEPTANCE PASS:**
  `e6593f7a99af2f0dd941eda7ee53a5164c79a2bd`,
  `fix: retain R0 setup containment observations`; **BLOCKER 0 / REQUIRED 0**.
  Independent `K`, `D`, `O_K_SETUP`, `O_D_SETUP` facts retain setup timing/memory
  instead of copying parent component maxima. Historical qualification:
  Operational `86/86`, E2 `676/676`, related `739/739`, full isolation-aware
  `4035/4035 PASS`.
- **R0 harness — FINAL ACCEPTANCE PASS / COMMITTED / PUSHED:**
  `7e7f847816fedb77cef67b576eab665afabfbfbf`,
  `feat: add Program K E2 R0 harness`; **BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
  Historical qualification: readiness `66/66`, E2 `758/758`, related
  Stage-3/Model-C/provenance `739/739`, full isolation-aware `4117/4117 PASS`
  (`4111 MAIN + 6 ISOLATED`), every discovered test exactly once; all
  failures/errors/skips/expected failures/unexpected successes `0`.
  Full-gate process elapsed **1,173.994 s**.
  [Final qualification summary](../../results/program-k-e2-r0-harness-qualification/20261024T165944.7530305Z-e2118d4d/qualification-summary.json)
  preserves the pre-commit qualification. ChatGPT final source/test acceptance
  required no independent Claude re-audit. Exact source identities are in the
  [current handoff](../CURRENT_HANDOFF.md).

The harness authenticates the accepted receipt and current committed-clean source
separately from the historical selection HEAD. Explicit `R0_A`/`R0_B`
authorization precedes operational I/O. It supplies first-64 plans at `c=1,2,4`,
six measurement routes, independent Oracle setup containment and immutable R0-A
readback; selected synthetic 10k materialization, six durable families,
zero-row Oracle/supporting-stream/fixed-allowance accounting; and the frozen
10,000-replicate production bootstrap through five bounded postprocessing phases
with manifest/provenance/failure-atomic publication. Real R0-A has now exercised
and closed its authorized measurement scope as recorded below. R0-B capabilities
remain unexecuted; neither implementation acceptance nor R0-A evidence establishes
effectiveness.
The historical readiness source-review guard remains historical; its positive
test fixture was isolated from the later harness worktree without broadening
the production guard.

#### Accepted Real R0-A — complete / integrity pass / closed

The historical separately authorized initial calibration run is **COMPLETE / INTEGRITY
PASS / EVIDENCE ACCEPTED / CLOSED**. Its post-run integrity review and static
follow-on review are **COMPLETE**. Preserve the accepted run; **do not rerun R0-A**.

- Run root:
  [`results/program-k-e2-real-r0a/20261024T193317.738335Z-2af3a8ca/`](../../results/program-k-e2-real-r0a/20261024T193317.738335Z-2af3a8ca/).
- Source at run/review:
  `c0bc270bce1996797f9ecec80e79ea8998d3205d`; 37-file source/provenance digest
  `1db7293ec43835b44542c1373e5ce55424e3cc06e0d10f39dab2430b2d7cb163`.
- Classification: `OPERATIONAL_NON_EFFECTIVENESS_R0_EVIDENCE`;
  review status: `COMPLETE_FOR_INDEPENDENT_REVIEW_NOT_ENVELOPE_ADMISSION`.
- `COMPLETE.json` records `COMPLETED`; `FAILED.json` is absent. The original
  `INCOMPLETE_AT_CREATION` marker is retained as expected creation history, not
  a current failure or incomplete-run verdict.
- All `c=1,2,4` candidates and six routes `P`, `K`, `O`, `D`, `O_K_BIND`,
  `O_D_REPEAT` completed: **18/18 routes, 64/64 positions each**, with the same
  first-64 identities. First-64 corpus digest:
  `bb1202fad3ed2f3d89026aed071a1a9c1e7140b09f2cdf326a52c86cec3f2a78`.
- Manifest/completion, exact readback/adapter reproduction, committed-source,
  receipt, frozen protocol/amendment and all required setup/watchdog/resource/
  cleanup/progress/readback checks passed. Accepted calibration cap breaches: **0**;
  highest measured utilization was combined memory, **36.6940%**.
- Operator start: **2026-10-25 04:33:17.772727 KST**; successful return:
  **2026-10-26 04:18:00.538514 KST**, exit **0**. Observed wrapper elapsed:
  **85,482,777,754,500 ns = 23h44m42.7777545s**. This is the whole operator session,
  not one route wall, an Actual-E2 runtime, or a breach of a per-component 12-hour
  calibration cap.

| Evidence identity | Bytes | SHA-256 |
| --- | ---: | --- |
| Accepted selection receipt linked above | 7,364 | `72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c` |
| Run `manifest.json` | 19,256,799 | `60adb78437d6edce767d05f7a9cb79fead0fcedf0a8b349559ab7cbd1da19edb` |
| Run `COMPLETE.json` | 422 | `1ecea386f404f54ddc875ccf17398cc1c48e86ed40d43a76f834d95c2cf6954e` |
| Run `r0a-observations.json` | 19,826,611 | `cf624bdc88f601d22f7ab9f52e630374b9b17ec0085584cb19796684142adb7c` |

The frozen protocol SHA-256 remains
`10b1055a6e1bcab8e03ab504755c9c9d655d5457800318396afb6e31497ba2fa`;
the amendment remains the exact 58,052-byte identity above. R0-A used explicitly
adjudicated **initial calibration** envelopes, including the 25 ms monitor cadence
and a combined 4 GiB memory ceiling. Its permissive per-component job/launcher/
phase ceilings do not become final E2 envelope values. R0-A evidence is operational
non-effectiveness evidence only; no final concurrency is selected from it.

Measured concurrency comparisons remain descriptive single-run observations:

| Comparison | c=1 | c=2 | c=4 |
| --- | ---: | ---: | ---: |
| O_K_BIND attributed binding wall, seconds | 3,018.3200812 | 2,995.5455936 | 3,075.1226738 |

O_K_BIND wall reduction was **0.7545%** from c=1 to c=2 and **−2.6565%** from
c=2 to c=4. The other five route-wall reductions from c=2 to c=4 were
P **18.7662%**, K **13.2703%**, O **18.8638%**, D **18.4825%** and O_D_REPEAT
**23.2959%**. At c=4, K complete/setup walls were **6,365.4555667 / 1,029.7495051 s**,
and D complete/setup walls were **2,999.361048 / 1,032.7497351 s**. Setup remains
inside those complete standalone K/D walls. These observations establish neither
a causal bottleneck nor a selected concurrency.

#### Static block 1 — frozen execution-admission projection

The accepted six-term execution projection is:

```text
E(N,c) = 2 * (
    P64(c) * N / 64
  + K64(c) * min(N,256) / 64
  + D64(c) * min(N,256) / 64
  + O64_primary(c) * min(N,128) / 64
  + O64_k_bind(c) * I_OK(N) / 64
  + O64_d_repeat(c) * I_OD(N) / 64
)
```

For every frozen candidate **N = 1,000 / 2,500 / 5,000 / 10,000**, the complete
standalone K/D terms alone give `L(c) = 8 * (K64(c) + D64(c))`. All omitted terms
are nonnegative. K/D setup belongs to their complete standalone route walls;
**do not subtract setup to make this bound fit**.

| Concurrency | Exact K+D lower bound, ns | K+D lower bound, hours | Stronger N=1,000 P+K+D+O-primary bound, hours | Frozen ceiling |
| --- | ---: | ---: | ---: | ---: |
| c=1 | 115,091,421,316,800 | 31.9698392547 | 45.4706941160 | 12 h |
| c=2 | 88,150,611,100,000 | 24.4862808611 | 34.9850789298 | 12 h |
| c=4 | 74,918,532,917,600 | 20.8107035882 | 29.3375792716 | 12 h |

Thus **every candidate N/concurrency is statically blocked by execution-admission
time before R0-B postprocessing is added**. These are frozen-formula admission
projection lower bounds derived from R0-A, not measured Actual-E2 runtimes and not
the 23h44m operator session. The descriptive improvement from c=1 to c=4 does not
select a winner or resolve the bound; c=4 still exceeds 12 hours using K+D alone.

#### Static block 2 — required synthetic R0-B cumulative archive

`derive_r0b_sizing_plan()` takes each attributable maximum unit over all candidate
concurrencies and applies exact `ceil(3/2 * maximum)`. Oracle primary/repeat share
one conservative maximum scalar but remain separate families. R uses the maximum
across all reference routes. The already accepted synthetic receipt fixes the
realized family counts below; real target counts must not replace them.

| Required synthetic family | Observed max B | Minimum bytes/unit | Realized synthetic count | Minimum family bytes |
| --- | ---: | ---: | ---: | ---: |
| P primary | 3,744,932 | 5,617,398 | 10,000 | 56,173,980,000 |
| K control | 19,723,787 | 29,585,681 | 256 | 7,573,934,336 |
| Oracle primary | 5,698,786 | 8,548,179 | 128 | 1,094,166,912 |
| Oracle repeat | 5,698,786 | 8,548,179 | 4 | 34,192,716 |
| D determinism | 15,238,396 | 22,857,594 | 256 | 5,851,544,064 |
| R rank-0 reference | 4,373,733 | 6,560,600 | 506 | 3,319,663,600 |
| **Attributable lower bound** | | | | **74,047,481,628** |

The minimum is **68.962091 GiB**, versus the frozen **17,179,869,184-byte / 16 GiB**
archive ceiling: **4.310131 times the cap**, exceeding it by **56,867,612,444 bytes**
before any supporting/provenance/report/manifest bytes. P alone requires
**56,173,980,000 B ≈ 52.32 GiB** and exceeds the cap. Supporting/report/finalization
overhead is unmeasured because R0-B has not run; omitted overhead is nonnegative.
The exact fixed allowance remains **268,435,456 bytes**; it does not enlarge the
archive cap. This is an unavoidable lower-bound conflict under the current sizing,
counts and cap, not a claim that R0-B executed or failed.

Per-unit composite payload is a different constraint:

| Actual synthetic logical unit | Minimum composite bytes |
| --- | ---: |
| PRIMARY: P | 5,617,398 |
| PRIMARY: P + R | 12,177,998 |
| PRIMARY: P + Oracle primary | 14,165,577 |
| PRIMARY: P + R + Oracle primary | 20,726,177 |
| D: D | 22,857,594 |
| D: D + Oracle repeat | **31,405,773** |
| K: K | 29,585,681 |

The largest minimum composite is **31,405,773 bytes**, below the **67,108,864-byte**
per-unit cap by **35,703,091 bytes** (46.798249% utilization). That minimum-fit fact
does not establish realized payload fit after schema framing/padding, and does not
establish cumulative archive feasibility. Do not sum all six families as one unit
or add R again to K/D: their attributable target families already own their copies.

That historical harness used one cumulative evidence sink for all **10,512** logical
workers (10,000 primary + 256 K + 256 D). Final archive accounting requires both
`archive_bytes >= family minimum totals + realized fixed bytes` and
`archive_bytes <= 17,179,869,184`. Its public R0-B boundary checked minimum
composite payload fit before creating a result root, but did not perform this
minimum-total-archive preflight there; cumulative persistence/final accounting
still failed closed. These historical facts were established by source-only/read-only static
inspection and arithmetic, without materialization or a launcher invocation.

#### Fresh R0-A V2 Attempt #2 — accepted evidence / partial remediation success

Root: [`results/program-k-e2-fresh-r0a-v2-48f6ebc-attempt2/`](../../results/program-k-e2-fresh-r0a-v2-48f6ebc-attempt2/).
Recorded source HEAD is `a7abce49...`; qualified technical anchor remains
`48f6ebc...`. Accepted execution completed successfully with **Python exit 0**;
post-run `validate_existing_run_v2` **PASS**, **INTEGRITY PASS / EVIDENCE ACCEPTED**.
Fresh R0-A is **CLOSED as operational calibration evidence**: **18/18 components,
64/64 units each, 1,920/1,920 cases**, no FAILED marker, accepted
provenance/source/profile/corpus/inventory. Preserve the creation marker.
The whole operator elapsed was **49h 56m 6.9099925s**, versus historical
**23h 44m 42.7777545s**; neither is an Actual-E2 runtime or a single route wall.
These are accepted records, not executions or validator checks rerun by this refresh.

| Fresh result | Accepted finding |
| --- | --- |
| Overall remediation | **PARTIAL SUCCESS** |
| Execution / evidence integrity | **SUCCESS / ACCEPTED / CLOSED** |
| Comparable route walls | **18/18 regressed; execution-wall blocker worsened** |
| c4 K64+D64 | **22,959.2643101 s**, against necessary early target **<=5,400 s** |
| c4 K+D projected lower bound | **183,674.1144808 s**, above **43,200 s** ceiling |
| N=1000 current c4 P/O-only bound, K=D=0 | **48,874.331425675 s**, already above ceiling |
| N=1000 full c4 P+K+D+O-primary bound | **232,548.445906475 s** |
| Physical attributable minimum | **74,047,481,628 B historical → 15,385,281,356 B Fresh; approximately 79.22% reduction** |
| Full fixed reservation | **15,385,281,356 + 268,435,456 = 15,653,716,812 B <= 17,179,869,184 B** |
| B_proc | **1,526,152,372 B** |
| Demonstrated historical static whole-archive blocker | **RESOLVED** for Fresh representation |
| Realized R0-B constructibility | **NOT YET ESTABLISHED** |

The necessary screen is
`B1000(c) = 2*(P64(c)*1000/64 + K64(c)*256/64 + D64(c)*256/64 + O64_primary(c)*128/64)`.
O_K_BIND, O_D_REPEAT and postprocess are nonnegative: B1000 above the ceiling
rules out that c. Passing still needs explicit, evidence-supported headroom for
those omitted projected costs. K+D <=5,400 s and historical V1 parity are not
sufficient. Preserve RF02/WB02/qualified codec/dual sizing unless later evidence
forces otherwise; the static sizing improvement does not prove a realized archive.

Codex Fresh adjudication and independent Claude Code audit agree on valid evidence,
resolved static storage blocker, worse timing, and keeping R0-B unrun. Repeated
same-boundary WB02/canonical/legacy validation, coordinator/admission/readback work,
and CPU-heavy/serial validation with weak concurrency benefit are source-supported
profiling hypotheses, not established unprofiled causes. Exact identities and
audit locations are in [CURRENT_HANDOFF](../CURRENT_HANDOFF.md).

#### Timing profiling — prepared, execution blocked

External package:
`C:\Users\User\.codex\visualizations\2026\10\30\01a18cf8-cb06-7f51-baab-bc05c6fcc53d\program-k-timing-profile-v1`.
**PREPARED / NOT EXECUTED**, bounded diagnostic only, **not R0/admission evidence**.
Independent Claude pre-execution verdict: **B. FIX REQUIRED BEFORE EXECUTION**.

- **B1:** approved venv Python is a Windows redirector/launcher; current Job
  `ActiveProcessLimit=1` and assignment cannot guarantee containment of the actual
  base-Python driver. Correct before any execution.
- **R1:** `control.json` replace/read race.
- **R2:** `output_size` TOCTOU on disappearing pending files.
- **R3:** adaptive extension does not respect remaining phase/global budget.

Only B1 + R1–R3 form the mandatory correction set; optional hardening is separate.
**Phase 1 K/D: NOT AUTHORIZED. Phase 2 P/O: NOT AUTHORIZED. No profiling
measurement exists; Phase 2 never starts automatically.**

#### Current execution boundary / accepted remediation design

The [exact V1.3.1 design](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md) is **FINAL DESIGN
ACCEPTED / FROZEN BY EXACT TRACKED BYTES**. Its
[acceptance receipt](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md) is the
live authority for the subsequent closure re-audit PASS and ChatGPT/user final
acceptance: **BLOCKER 0 / REQUIRED 0; design phase CLOSED**. The design's historical
pre-re-audit wording remains unchanged. The receipt's implementation-not-started
wording describes its historical design boundary; the current implementation is
**1A–1W: 23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED**. Preserve the frozen bytes.

**FRESH R0-A FINAL PREFLIGHT — PASS**, **BLOCKER 0 / REQUIRED 0 / OPTIONAL 1**,
qualified the exact technical source
`48f6ebc97e6c4d3ed4a746a92a8d169783803bf9` as
**ELIGIBLE FOR SEPARATE FRESH R0-A EXECUTION AUTHORIZATION** at that historical boundary. The accepted USER-host
focused E2 regression was **1513/1513 PASS**, failures/errors/skips **0/0/0**.
The exact source chain, runtime/profile identities and accepted preflight evidence
are recorded in [CURRENT_HANDOFF](../CURRENT_HANDOFF.md).
Fresh Attempt #2 is now accepted and closed, with the partial-success findings
above. This documentation refresh grants **no execution authority**. A separately
approved docs-only commit/push does not change the qualified technical anchor or
authorize timing profiling, R0-B, Actual E2, or any other experiment.
External-artifact correction and a dry check require separate approval.

**Intended next sequence:** minimal external **B1 + R1–R3 only** corrections →
recompute bytes/SHA pins → independent exact-byte delta review → separately
authorized **production-import-free Windows Job isolation dry check**. Only after
successful review/dry check consider Phase 1 authorization, then bounded K/D
profiling and independent stop/go. If optimistic K+D fails 5,400 s at every
allowed c, stop NO-GO without P/O. Phase 2 P/O requires justified Phase 1 evidence
and its own approved hash-bound gate. Final profiling adjudication precedes any
production timing-remediation design/implementation. After implementation,
bounded performance qualification must show a credible admission path before
any separately authorized new Fresh R0-A. R0-B remains later, separately
authorized after Fresh admission prerequisites pass. See the full 13-step
sequence in [CURRENT_HANDOFF](../CURRENT_HANDOFF.md).
**Do not rerun a large experiment merely to discover whether a timing change helped.**

Historical scope of the now **CLOSED / ACCEPTED** engineering investigation:
candidate investigation areas are K/D setup/reference preparation, encoding/IPC,
worker/coordinator validation, persistence/readback/cleanup and the observed weak
or negative O_K_BIND scaling. For bytes, examine the approximately 3.745 MB primary
maximum unit, required semantic content versus incidental representation, a compact
semantically equivalent representation, and an early minimum-total-archive check.
These were investigation targets, not established causes or approved implementations.

Do not begin by loosening caps, safety factors, subsets, the candidate-N ladder,
attribution, policy or thresholds. Any contract change requires separate explicit
adjudication. The accepted R0-A evidence and both static blocks above remain
historical evidence for the old source/representation. Fresh V2 resolves the
demonstrated static storage blocker but worsens timing; realized constructibility
remains unestablished. This documentation refresh
does not establish effectiveness or authorize execution.

| Boundary | Current status |
| --- | --- |
| Historical Real R0-A execution / integrity / evidence | **COMPLETE / PASS / ACCEPTED; work CLOSED, no rerun** |
| Historical R0-A post-run integrity review | **COMPLETE** |
| Historical R0 follow-on static feasibility review | **COMPLETE** |
| Historical execution-wall admission / old source | **STATICALLY BLOCKED; proof preserved** |
| Historical R0-B minimum archive / old representation | **STATICALLY BLOCKED; proof preserved** |
| Remediation engineering investigation | **CLOSED / ACCEPTED** |
| Remediation design V1.3.1 | **FINAL DESIGN ACCEPTED / FROZEN BY EXACT TRACKED BYTES** |
| Design boundary | **BLOCKER 0 / REQUIRED 0; design phase CLOSED** |
| Remediation implementation 1A–1W | **23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED** |
| Fresh R0-A Final Preflight | **PASS at technical source `48f6ebc`; BLOCKER 0 / REQUIRED 0 / OPTIONAL 1** |
| Qualified technical anchor / pre-refresh documentation HEAD | **`48f6ebc...` / `a7abce49...`; distinct identities recorded at this refresh's read-only preflight** |
| Fresh R0-A V2 Attempt #2 | **COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED** |
| Remediation result | **PARTIAL SUCCESS: static storage blocker resolved; timing regressed** |
| Realized R0-B constructibility | **NOT YET ESTABLISHED** |
| Timing-profile design / artifacts | **PREPARED / NOT EXECUTED** |
| Independent pre-execution review | **FIX REQUIRED BEFORE EXECUTION; B1 + R1–R3** |
| Phase 1 / Phase 2 | **NOT AUTHORIZED / NOT AUTHORIZED; no measurements** |
| This refresh | **No execution authority; separately approved docs-only publication does not change the qualified technical anchor or authorize any experiment** |
| Real R0-B | **NOT RUN / NOT AUTHORIZED; no R0-B failure claimed** |
| Complete R0 adjudication | **NOT DONE** |
| Final N / final concurrency | **NOT SELECTED** |
| Final E2 Operating Envelope | **NOT SELECTED / NOT FROZEN** |
| Actual E2 | **NOT RUN / NOT AUTHORIZED** |
| E2 PASS / FAIL / DEFER | **NONE** |
| Program K effectiveness | **NOT ESTABLISHED** |
| E3 | **CONDITIONAL ONLY / NOT TRIGGERED** |
| Gate P / production integration / native K visual acceptance | **NOT STARTED** |
| Program K final closeout | **NOT DONE** |
| Stage-3 Extended / milestone 10 | **ACTIVE; milestones 1–9 remain CLOSED** |

After the bounded diagnostic/remediation/qualification sequence above, any new
Fresh R0-A and its admission/constructibility review precede separate R0-B authorization.
Complete R0 adjudication must precede final N/concurrency/envelope selection and
freeze. Actual E2 still requires separate authorization. Any E3 required by the frozen trigger,
Gate P, production integration, K trace/native-user acceptance, Program K closeout
and eventual Extended closeout remain conditional later work. This is not an
automatic execution chain, an effectiveness PASS result, or a new frozen milestone.

Planned visual acceptance after Gate P/integration and before Program K closeout
uses an actual completed K trace replay, not live streaming. Logical-known-mine
state should be distinct from `HIDDEN` and physical `FLAG`; action target, route
and synthetic cursor should remain distinguishable. Prefer normal native-user
application flow for exhibition use. Optional later same-board Human / Stage-2 /
V1 / K comparison can reuse the independent-playhead architecture. This scope
has not been implemented/accepted as part of R0.

R0 evidence itself cannot authorize Actual E2 or freeze the final envelope.
The synthetic workload stays outside research/rehearsal/holdout domains; accepted
target counts do not authorize opening the Actual-E2 corpus. Effectiveness is
**NOT ESTABLISHED**. Stage-3 V1 / Model C stay **CLOSED / FROZEN**; the ZiNi final
holdout `2,010,000 .. 2,010,099` remains forbidden/unopened.

Recovery order:
[CURRENT_HANDOFF](../CURRENT_HANDOFF.md) → this roadmap →
[frozen E2 protocol](STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md) →
[frozen R0 Attribution Amendment](STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md) →
[exact V1.3.1 design](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md) /
[design acceptance receipt](STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md) →
current source/tests for disputed implementation facts.
Do not repeat E2-D0, protocol/amendment audits, Gate-R/E0/E1 execution or closed
evidence merely for recovery.

## Fixed-Exemplar Human/Domain Interpretation — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED — BLOCKER 0 / REQUIRED 0** (2026-10-19).
The [closeout](STAGE3_FIXED_EXEMPLAR_INTERPRETATION_CLOSEOUT.md) records the
corrected findings, USER expert speed-play standard and audit/adjudication lineage.
Inspection of fixed `73758 / 73024 / 93557 / 1` is COMPLETE; additional gameplay NONE.
These deterministic category exemplars are not a statistically representative sample.

The interpretation records recurring expert-play concerns and productive local
FLAG/CHORD progression as a strength. C's FLAG-destination geometry is a FACT,
not an independently established routing weakness. At that interpretation closeout,
P0 Known-Mine / No-Flag had qualitative/domain motivation but was **NOT ADOPTED**.
The later Program K research-specification freeze above preserves that historical
boundary and does not authorize implementation. Frozen V1 is not reopened.
Nearest Minimum-Risk Guess (nearest exact-minimum-risk guess using movement cost)
remains a separate backlog candidate **neither supported nor refuted by this
interpretation**. That interpretation adopted no algorithm policy or implementation.
External screen-recording tools remain the default.

## Selected Exemplar Board-State Viewer — CLOSED

**Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer —
FINAL ACCEPTANCE PASS / CLOSED. Slices 0–4 COMPLETE / ACCEPTED; BLOCKER 0 / REQUIRED 0.**
Qualified SHA `ff6358ae62b6f343bda36069d7164bda9aebee74` —
`test: preserve frozen E/L pilot source provenance`.
Production usability SHA `29af53b15d1fff144df5873b62fcec4af91adaaa` —
`feat: improve exemplar viewer inspection usability`.
The repair changed only experimental E/L provenance/tests; production bytes
remain those accepted by the user in native source-GUI checks.

Final root: `results/stage3-exemplar-board-viewer-final-acceptance/20261018T094900066913Z/`.
Fresh **892 focused / 2390 full PASS**, zero failures/errors/skips. Real evidence:
**4 boards / 8 streams / 1508 actions / 2 immutable-read-only DB opens**, all
fingerprint/order/type/target/status/reveal/explicit-FLAG/terminal/result mismatch
counts zero; DB bytes/sizes/mtimes and sidecar absence preserved.
Fresh package 77.012 s, native main-app startup/close exit 0, packaged worker
success/error/dispatch/cleanup PASS. Build-env prerequisite: **2365 PASS + 25
documented optional image/video skips**, zero failures/errors; these are not PASS.
No dedicated packaged Viewer launcher is claimed.

**USER native source-GUI acceptance:** A–F, P1/P2, route/max interval, V1/V2/V3
and final micro-polish PASS; “내 기준을 완전히 충족했어.” This is not Codex Viewer-native
or packaged Viewer-native acceptance. `ff6358a` leaves those production bytes intact.

The first qualification at `29af53b` remains **HOLD**:
`results/stage3-exemplar-board-viewer-final-acceptance/20261018T091846923796Z/`.
E/L repair evidence: `results/stage3-e-l-source-compatibility-repair/20261018T093614465991Z/`.
The historical frozen Engine hash was retained; an explicit Engine-only current
allowance and whole-file inverse-delta proof cover only the observational
`completed_ops` field. Unknown drift still fails closed. The historical 10k pilot
was not rerun. Earlier `1f90bec` acceptance is superseded pre-revision evidence.

**R-2 CLOSED** by committed-source qualification/provenance. **O-5 CLOSED**:
displayed Model C seconds = integer microseconds / 1,000,000. R-1 remains satisfied
at `2c9ba42fb394ee528a035a85c3a2c8146b86a7f9` following the conditional independent
Claude audit of `d338dcffa212e52efb23af9d9db41841348ade96` (BLOCKER 0 / REQUIRED 2).
O-1/O-2/O-6 satisfied; O-3/O-4 nonblocking DEFER; O-7/O-8 NO CHANGE.
No Claude re-audit after R-1 is claimed.

Final UI: one board, fixed four, eight independent positions/playheads, one explicit
Action entry, direct slider seek/drag, Before/After, immutable frame-prefix Counters,
Model C-labeled time/rates, shared asynchronous board ZiNi/WIN-only ZNE/ZNT,
Index 20..5000 ms (default 200; Max 20), Model C Time 0.25x..8x, synthetic smoothstep
cursor, completed-only default-OFF route, default-OFF HIDDEN-only Answer Overlay,
fact tabs and small-screen fallback. The approximately 16 ms presentation cadence
is not semantic interval/cost authority. Navigation/animation is lookup-only;
no DB/Engine/reconstruction, solver/planner or navigation-driven ZiNi search.
No common clock, normalized progress or actual mouse-trajectory claim.

Frozen V1/Model C, G4 and both Timeline reports remain preserved.
**final holdout accessed = NO** (ZiNi 2,010,000 .. 2,010,099).
The historical Viewer documentation closeout reran no technical verification.

[Final closeout](STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md) retains exact authorities,
commands/counts, E/L HOLD→repair→PASS lineage and package/user-native attribution.
[Contract](STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md) retains historical initial-slice
records, marked superseded where the accepted usability revision changed UI policy.

## Visualization Usability Polish — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED — BLOCKER 0 / REQUIRED 0** (2026-10-18).
Qualified implementation `31630dd6ffa2301c41534fca3b003838d865f313`
(`feat: add visualizer reference overlays`), on
`feature/stage3-visualization-usability-polish`. Foundation `a33c504` and Same-board
usability `866ea28` are ancestors. No prior closed milestone is invalidated.

Fresh evidence:
`results/stage3-visualization-usability-polish-final-acceptance/20261018T1306330178987Z/`.
Full **2484/2484 PASS** (141.629 s unittest / 144.042 s process); 13 complete focused
modules **453/453 PASS** (20.236 / 21.211 s); zero failures/errors/skips in both.
Fresh BUILDING-policy package **59.085 s**, AMD64 / PE32+ GUI, required helper/resources
present, 12 worker/job checks PASS, normal packaged startup/close exit 0.
Build prerequisite **2459 PASS / 25 documented optional image/video skips**,
zero failures/errors; skips are not PASS. EXE SHA-256:
`26cfb55bbbe75bad29bb0461bf39eed6a2b3b203512b9144751dcd770530a08f`.

**USER source-GUI native:** Same-board **A–M ALL PASS**, Visualizer **V-A..V-I ALL PASS**.
This is not Codex feature-native or packaged feature-native acceptance. The
[new closeout](STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md) passed ChatGPT
final review on 2026-10-18 and retains exact commands, attribution, preservation and limitations.

- **Same-board:** three independent selected-run timing states; Human Index +
  Replay Time, solvers Index + Model C Time; exact quarter-step 0.25x..8x time speed;
  Index 20..5000 ms, default 200, `Max (20 ms)` and committed text clamping.
  Direct track seek/native drag, smooth synthetic action-target cursor and partial
  pause/resume/catch-up are accepted. Human has no fabricated pre-first cursor origin.
  **No common synchronized Human/S2/S3 clock/playhead.** Entire actual Human
  Mouse Trace stays distinct from the completed route and synthetic cursor.
- **Visualizer:** existing direct seek, Index timing and modeled smooth cursor
  with six speeds (0.25x / 0.5x / 1x / 2x / 4x / 8x) are preserved.
  **No Index smooth interpolation was added.**
- **Both:** default-OFF HIDDEN-only answer reference and completed action-target
  route; pending/future points excluded, repeated targets retained, no fabricated
  initial-cursor route segment. Selected context/cursor remain separate. Fixed
  truth is reference-only. Partial refresh/toggles do no domain work; accepted
  committed seek/reconstruction paths retain their existing ownership.
- **Neutral helper:** `visualization_reference_overlays.py` derives immutable clues
  and paints caller-supplied masks/points; no truth acquisition, prefix selection,
  playback/clock, Engine, solver/planner, Model C or process lifecycle.

At the 2026-10-18 polish closeout, fixed-exemplar interpretation was next.
That interpretation is now CLOSED. Program K's research specification, Gate-R
E0/E1 protocol and E2 Effectiveness Protocol remain FROZEN / ACCEPTED.
E2 implementation is now **I1–I8 = 8/8 COMPLETE / ACCEPTED**, and the
[R0 Attribution Amendment v1](STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md)
is **CONTENT-FROZEN / ACCEPTED**. Conformance, selection, setup repair and the
R0 harness at `7e7f847` are accepted. Historical Real R0-A is COMPLETE / INTEGRITY PASS /
EVIDENCE ACCEPTED / CLOSED. Remediation investigation/design are CLOSED / ACCEPTED;
V1.3.1 is frozen by exact tracked bytes, and remediation 1A–1W is 23/23 COMPLETE /
ACCEPTED / COMMITTED / PUSHED. Qualified technical anchor is `48f6ebc`; Fresh V2
Attempt #2 records documentation/source HEAD `a7abce49...` and is accepted/closed.
Remediation is **PARTIAL SUCCESS**: static storage blocker resolved, timing worse.
Timing-profile artifacts are **PREPARED / NOT EXECUTED / FIX REQUIRED BEFORE
EXECUTION**; both phases are NOT AUTHORIZED. The [current Program K boundary](#current-program-k-boundary)
records B1 + R1–R3 corrections and the separate review/dry-check/authorization sequence.
R0-B and Actual E2 remain NOT RUN / NOT AUTHORIZED; effectiveness is NOT ESTABLISHED.
The historical polish acceptance is unchanged.

## Representative-board Demonstrations / Timeline Analytics — CLOSED

**Slice 0 — Contract COMPLETE / ACCEPTED by ChatGPT final review
(2026-10-17, Asia/Seoul).** Read-only discovery received ChatGPT **DISCOVERY PASS**.
The [accepted contract](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md) records the scope.
**Slice 1 — Pure timeline analytics COMPLETE / ACCEPTED by ChatGPT final review.**
Slice-1 adjudication: **SLICE 1 PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Slice 2 — Pure deterministic exemplar selection COMPLETE / ACCEPTED by ChatGPT
final review.** Final Slice-2 adjudication:
**SLICE 2 PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Slice 3 — Read-only accepted-evidence report / static visualization COMPLETE /
ACCEPTED as a whole. Internal Slice 3A — accepted-evidence opening correction / preflight
COMPLETE / ACCEPTED by ChatGPT final review.** Final adjudication:
**SLICE 3A CORRECTION / PREFLIGHT PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
**Internal Slice 3B COMPLETE / ACCEPTED: STAGE-3 EXTENDED TIMELINE ANALYTICS —
SLICE 3B FINAL PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 5.**
**Slice 4 — Acceptance / Closeout COMPLETE / ACCEPTED. FINAL ACCEPTANCE PASS /
CLOSED; BLOCKER 0 / REQUIRED 0.** Stage-3 Extended remains ACTIVE. The
[final closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) records the qualified
candidate `4c488e033dd045f1c203ff500d824cfaffb7cc67` and final evidence.

Accepted Slice-1 implementation: [`timeline_analytics.py`](../../timeline_analytics.py)
and [`tests/test_timeline_analytics.py`](../../tests/test_timeline_analytics.py).
Verification: **28 focused PASS; 257 bounded existing regressions PASS**.
Four existing solver/Engine execution cases were intentionally excluded from
that bounded regression set; **no full suite is claimed**. The projection and
focused tests used in-memory synthetic facts with no DB access; existing
regressions used synthetic SQLite fixtures only. No official benchmark DB or
artifact was accessed, no actual exemplar IDs were selected, and no solver runs,
benchmarks, builds or GUI were used. Frozen V1 / Model C are unchanged;
Human remains deferred.

Accepted Slice-2 implementation: [`representative_boards.py`](../../representative_boards.py)
and [`tests/test_representative_boards.py`](../../tests/test_representative_boards.py).
Verification: **29 focused PASS; 28 Slice-1 timeline PASS; 75 bounded existing
comparison/statistics regressions PASS. Total reported verification: 132 PASS.**
All Slice-2 selector fixtures were synthetic/in-memory; existing regressions used
synthetic SQLite fixtures. No official DB/G4 artifact was accessed and no actual
official exemplar ID was selected. No solver, benchmark, build, GUI or full-suite
execution occurred. Frozen V1 / Model C are unchanged; Human remains deferred.

Accepted Slice-3A correction: [`telemetry_repository.py`](../../telemetry_repository.py)
and [`tests/test_telemetry_repository.py`](../../tests/test_telemetry_repository.py).
`connect_database_readonly(path, *, immutable=False)` preserves default `mode=ro`
behavior and supports explicit `mode=ro&immutable=1` for authenticated stable
preserved artifacts. `immutable=True` asserts that the source will not change
during the connection lifetime; it is not for live sources.
Verification: **67 complete telemetry-repository PASS; 238 bounded relevant
regressions PASS; total 305 PASS**. Four existing solver/Engine execution tests
were intentionally excluded; **no full suite is claimed**.

During internal Slice 3A, the exact four official artifact hashes were
reauthenticated. Fresh Stage-2 and Stage-3 run identity/coverage checks **PASS**;
both runs are official-eligible exact
`EXPERT_GENERAL_V1 [0,100000)`. Model C authentication and **100,000 paired-prefix
identity validation PASS**. Independent outcomes reconcile:
**WW 37,702 / WL 0 / LW 0 / LL 62,298**. The independently derived WW index set
exactly equals the authenticated G4 paired-delta index set: **37,702; missing 0;
extra 0**. Official artifact bytes/timestamps remained unchanged; no new sidecars
remained. No solver, Engine, board generator, official benchmark rerun, detailed
selected-action loading, report/chart generation, Human data or ZiNi holdout was
used. No actual official exemplar ID was selected or disclosed during Slice 3A.

Accepted Slice-3B implementation:
[`scripts/stage3_timeline_report.py`](../../scripts/stage3_timeline_report.py) and
[`tests/test_stage3_timeline_report.py`](../../tests/test_stage3_timeline_report.py).
Final R-1 verification: **34 report + 29 representative selector + 28 timeline
analytics + 67 telemetry repository = 158 focused PASS; 174 bounded regressions
PASS; reported total 332 PASS**. Four solver/Engine execution tests were
intentionally excluded; **no full-suite claim was made at Slice 3B**.

Independent Claude Code read-only audit inspected the actual pre-correction
report, independently authenticated/recomputed selection, and reproduced all
**1,508 action rows and 16 SVGs with 0 mismatch**. Claude reported **BLOCKER 0 /
REQUIRED 0** and OPTIONAL O-1..O-6. ChatGPT promoted O-1 to REQUIRED R-1 for report
provenance/semantic wording; corrected R-1 is accepted and **O-1 SATISFIED**.
**O-2 DEFER** (chart common scale), **O-3 NONBLOCKING** (parse-hashed-bytes TOCTOU),
**O-4 DEFER** (selected-action SQL tests), **O-5 DEFER** (synthetic failure branches),
**O-6 DEFER / NONBLOCKING** (extended run/git/config provenance). Current identity
is sufficient; added convenience/detail does not justify regenerating the report.
No Claude re-audit after R-1 is claimed or required; its wording-only correction
was subsequently source/test/report verified by ChatGPT/Codex.

Fixed category exemplars: maximum Stage-3 WW advantage **73758 / -27009085 us**;
median-delta WW **73024 / -16487355 us**, lower-median zero-based rank **18850 of
37702 WW**; closest-to-zero Stage-3 WW advantage **93557 / -7877513 us**;
Stage-2 WW advantage, exact WW tie, WL and LW **EMPTY**; LL **game 1**.
Unique selected games: **1, 73024, 73758, 93557**; no visual/manual substitution.
Exact selected action counts, modeled totals and G4 reconciliation are in the
[accepted Slice-3B evidence record](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md#accepted-slice-3b-implementation-and-evidence).

Final corrected report:
`results/stage3-timeline-analytics/20261017T113748060625Z-99dafa139703/report.html`,
**470817 bytes**, SHA-256
`b680e5bdc1e4598bee089a4def67728bb851758f7c4de75a4b9cdc62f57f72d3`.
Corrected script SHA-256:
`50f9d88e80b971596de59eadae1bb3bf96ee0d4da88d252684a7cbf0a15eb387`.
Preserve the earlier
`results/stage3-timeline-analytics/20261017T103913620889Z-54082dd14870/report.html`
as historical pre-final 3B evidence. Both reports are ignored local evidence;
do not overwrite/delete either or rerun/replace selection.

Accepted R-1 semantics: both displayed timelines evaluate persisted actions
post-hoc under authenticated Model C. Stage 2 had no native Model C declaration;
Stage-3 collection declared Model C and checked its native total, but persisted
report events retain no native per-action cost/cursor fields. Compute scopes are
Stage-2 analysis versus Stage-3 analysis plus planning, with no cross-stage
compute-speed winner. Stage-2 guess candidate count is exact-minimum-risk tie
multiplicity / final selector pool; official Stage-3 count remains unavailable.
Missing native cursor/action-cost fields, Replay timestamps, full probability
coordinate maps and chosen plans are not fabricated. Official artifacts remained
unchanged with no new sidecars. No solver, Engine, board generation, official
100k rerun, Human data or ZiNi holdout was used.

The first implementation uses only exact accepted official Stage-2 / Stage-3
benchmark artifacts. All four accepted DB/G4 artifact hashes must be verified
before real-evidence report acceptance. Fixed selection rules identify
**deterministically selected category exemplars**, not a statistically
representative sample (the roadmap term 대표 보드 retains this limitation).
Rules must be accepted before selecting IDs; no replacement for visual variety.

Each solver's horizontal coordinate is its own completed semantic action count:
origin 0, persisted `action_index i` maps to `i + 1`. Equal counts do not imply
equal progress. Frozen Model C supplies a common measurement scale, not a shared
execution clock. Compute timings remain separate diagnostics; paired speed
interpretation is WW-only, while LOSS cost is cost through termination.

The accepted pure `timeline_analytics.py` and `representative_boards.py` implement
the Slice-1 and Slice-2 boundaries. The thin read-only evidence/report entry point
`scripts/stage3_timeline_report.py` is implemented and accepted in Slice 3B.
The report includes independent
tables and bounded static timelines,
with output in a new ignored `results/` location. No production Qt UI or new
plotting dependency merely for convenience. Human/native-decision adapters and
interactive GUI are deferred; no algorithm, Model C, schema or telemetry changes.
Official 100k artifacts remain unchanged; the unopened ZiNi holdout remains unused.

Slices: **0 Contract → 1 Pure timeline analytics → 2 Pure deterministic exemplar
selection → 3 Read-only accepted-evidence report / static visualization →
4 Acceptance / closeout**. **Slices 0–4 COMPLETE / ACCEPTED**. Internal 3A/3B
subdivide Slice 3, not the roadmap. Final Slice-4 verification used
`C:\venvs\minesweeper\Scripts\python.exe` (Python 3.12.10, 64-bit AMD64):
**386 discovered / 386 PASS** focused/frozen, 6.198 s unittest / 6.935 s process;
**2184 discovered / 2184 PASS** full source, 141.186 s unittest / 144.019 s process;
**zero failures/errors/skips** in both. Official artifact/model identities,
source/report reconciliation and final document/report inspection PASS. Ordinary
unit tests included Engine/solver execution; no official evidence rerun occurred.
Ignored local evidence: `results/stage3-timeline-analytics-closeout/20261017T131224859Z/`.
No fresh package/build/native GUI gate was required or run because no production
GUI/package surface changed. The final report's earlier `c32e34c...` / dirty generation
state is accepted: its script SHA matches the exact committed `4c488e...` script.
See the [closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) for commands and full identities.
Slice 3A completed exact accepted official Stage-2/Stage-3 DB/G4 authentication and
preflight. **Internal Slice 3B first selected and disclosed actual official exemplar
IDs**, using only the already-accepted deterministic
rules. No visual/manual substitution is allowed after selection.
**Read-only/report output only:** do not rerun the official 100k or any solver,
and do not modify frozen official evidence. The implementation
feature branch at acceptance was `feature/stage3-timeline-analytics`. Live Git
remains authoritative for current branch/HEAD and integration state; later
closeout documentation does not replace the qualified implementation identity.

## Same-board Human / Stage-2 / Stage-3 Comparison — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-17, Asia/Seoul).** Slices 0–5 are
COMPLETE / ACCEPTED, including internal 2A/2B and 4A/4B. Qualified source/package
candidate: `a59d0d963bdf1544a03968163b884342e2797ee0`. The
[final closeout](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md) records automated and
user packaged native/manual acceptance, chronology and nonblocking dispositions.

The dated slices below record the original Comparison milestone. Its no-autoplay/
no-timer UI dispositions are historical and superseded by the accepted
[Visualization Usability Polish](#visualization-usability-polish--closed) above;
execution/transport and committed-index ownership remain unchanged.

**Slice 0 — contract documentation COMPLETE / ACCEPTED.** The accepted
[comparison contract](STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md) governs exact
same-layout execution, first-open qualification, admission, identity, metric
separation and acceptance.

**Slice 1 — Comparison domain and admission COMPLETE / ACCEPTED** by ChatGPT
final review. The pure Qt-independent
[`same_board_comparison.py`](../../same_board_comparison.py) and its
[focused tests](../../tests/test_same_board_comparison.py) preserve the original
Human Replay and separate Mouse Trace attachment. Admission requires both
`source_type == SOURCE_HUMAN` and explicit `declared_full_game_human=True`;
neither metadata, declaration nor successful reconstruction proves exclusively
Human historical provenance. Identity uses exact layout equality and the existing
canonical fingerprint. Full-stream reconstruction rejects incomplete and
post-terminal streams; opening qualification remains factual, without implying
controlled experimental conditions.

Reported Slice 1 verification: **29 focused passed; 202 relevant regression
passed; combined reported total: 231 passed**, zero failures/errors/skips.
No full suite, package or native GUI run was performed for Slice 1.

**Slice 2 — Isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT final review.
**Slice 2A — Pure isolated execution and metrics COMPLETE / ACCEPTED** by ChatGPT
final review. [`same_board_runner.py`](../../same_board_runner.py) runs unchanged
Stage 2 (`accept_guesses=True`, `initial_open=(0,0)`, observer traces) and frozen
Stage 3 on separate fresh fixed-layout engines using the exact admitted Human
layout and authenticated Model C. Mined-origin immediate losses remain legitimate;
no regeneration or retry. Native result/Replay/trace authorities remain separate;
the Qt-independent immutable execution result/metric layer retains no live Engine
or fabricated benchmark identity.

Accepted `benchmark_modeled_time.evaluate_ordered_actions()` reuses existing
authenticated validation/cost logic for complete canonical ordered inputs,
including initial and terminal/losing costs, without DB, GameRecord or fabricated
telemetry/benchmark identity. Existing evaluator callers are preserved.
Human Replay elapsed seconds, each solver's Model C microseconds and each solver's
decision-compute nanoseconds remain separate. No Human Model C time, generic speed
field, winner, ratio or Timeline Analytics is added.

Reported Slice 2A verification: **31 new Slice 2A passed; 29 Slice 1 passed;
274 relevant regression passed; combined reported verification: 334 passed**,
zero failures/errors/skips. No full suite, package or native GUI run for Slice 2A.

**Slice 2B — Worker/process integration COMPLETE / ACCEPTED** by ChatGPT final review.
The dedicated PyQt-independent worker receives only a request token and fixed
ReplayBoard; Human Replay/Mouse Trace remain parent-owned. It executes the accepted
solver path once, without regeneration/retry or fabricated LOSS on failure.
`SameBoardExecutionJob` owns one child/private directory, cancellation/escalation,
reaping and cleanup; success attaches evidence to the exact original Human context.
Source/frozen dispatch is separate, with `--same-board-execution-worker` before Qt.
Parent validation rechecks comparison/outcome-bearing facts without recursively
walking nested decision evidence; native evidence remains retained unchanged.
See the [historical closeout](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md) for the accepted
lifecycle/validation boundary, corrected audit finding and qualified responsiveness
measurements (not zero GUI-thread blocking or frozen algorithm-performance evidence).

Reported final Slice 2B verification: **84 Slice 2B passed; 31 Slice 2A passed;
29 Slice 1 passed; 374 relevant regressions passed; combined reported verification:
518 passed**, zero failures/errors/skips. No full suite, fresh package or native
GUI acceptance was run for Slice 2B.

Slices 2A/2B remain internal parts of official Slice 2, not new roadmap milestones.

**Slice 3 — Pure playback coordination COMPLETE / ACCEPTED** by ChatGPT final review.
Pure Qt-independent [`same_board_playback.py`](../../same_board_playback.py) retains
three distinct runs (`HUMAN`, `STAGE2`, `STAGE3`): original Human and native Stage-2
Replays use existing `ReplayPlayer`; Stage 3 uses its fixed-layout trace player
without fabricated benchmark identity. Only recorded `trace.move` executes, never
planner evidence or plan suffixes. No solver/planner/worker/Model-C rerun occurs.

Each run retains its own action index/range; switching restores that index without
changing another run. Index 0 is the fixed all-HIDDEN board; n applies exactly n
inputs. Current `status` and final outcome remain separate, including PLAYING at
index 0 then LOST at index 1 for a legitimate first-action solver loss. Sources,
Mouse Trace attachment and metrics remain unchanged. No common timeline, clamping,
index mapping, normalized progress, lockstep, synchronized three-board playback,
generic time/speed/progress authority or universal player/registry was introduced.
Slice 3 includes no Mouse Trace playback/transformation, autoplay, Qt timer,
interpolation or UI. See the [historical closeout](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md)
for the accepted playback boundary.

Reported Slice 3 verification: **29 focused; 84 Slice 2B; 31 Slice 2A; 29 Slice 1;
139 existing player/Engine/Replay/Mouse Trace/fingerprint regressions; combined
reported verification: 312 passed**, zero failures/errors/skips. No full suite,
package or native GUI run for Slice 3.

**Slice 4 — Read-only comparison UI COMPLETE / ACCEPTED** by ChatGPT final
adjudication, including internal **4A — Read-only Comparison Result Viewer** and
**4B — Launcher + Main UI Integration / Lifecycle**, both **COMPLETE / ACCEPTED**.
4A/4B are parts of official Slice 4, not new roadmap milestones.

4A [`same_board_comparison_ui.py`](../../same_board_comparison_ui.py) consumes one
completed execution, owns one `SameBoardPlayback` and no worker/job/process/timer.
One public-observation-only board, three-run selector, independent remembered
indices and manual First / Previous / Next / Last / selected-run slider preserve
current status versus final outcome. Factual summary/first-open qualification
does not imply controlled conditions. The optional full immutable Human Mouse
Trace is Human-only and independent of index. No autoplay/time coordination.
Metrics stay separate: Human Replay elapsed seconds; Stage-2 and Stage-3 Model C
cost through termination µs; Stage-2 and Stage-3 decision compute ns. No generic
time/speed winner, ranking or ratio; the Stage-3 Visualizer remains separate.

4B [`same_board_comparison_launcher.py`](../../same_board_comparison_launcher.py)
captures one admitted context from either a completed Live game or the entire
retained original Replay, regardless of displayed index, using existing sources.
**Compare as full-game Human Replay…** declares caller intent, not provenance;
Human metadata remains mandatory. No new loader. Later main source changes cannot
retarget the launcher; **Open Comparison…** only raises the existing owner.
It owns one unchanged job and retained result/viewer; Run requires no active token
and an idle job, and normal Run/Cancel do not wait. Solver LOSS is a valid result;
viewer reopen does not rerun execution. Shutdown permanently disables execution,
retains ownership on failure and supports close retry. Job shutdown precedes
viewer close; main close orders Comparison before Stage-3 before remaining
teardown, stopping on Comparison close failure.

Independent Claude Code read-only audit: **BLOCKER 0 / REQUIRED 0 / OPTIONAL 4 /
PASS**; Claude did not execute/rerun tests. ChatGPT independently reviewed
source/tests and accepted without production correction. Final dispositions:
O-1 DEFER/evidence-triggered; O-2 SATISFIED by real packaged-worker lifecycle
acceptance; O-3 NONBLOCKING after 2085/2085 full source PASS; O-4 DEFER (manual
acceptance did not expose wording confusion). See the
[closeout audit record](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md#audit-disposition-and-nonblocking-ux).

Reported Slice 4 verification: **55 new 4B (31 launcher / 24 main UI); 32 4A;
29 Slice 3; 84 Slice 2B; 31 Slice 2A; 29 Slice 1; 370 relevant existing regressions;
combined reported verification: 630 passed**, zero failures/errors/skips.
No full suite, fresh package or native GUI acceptance for Slice 4 is claimed.

**Slice 5 — Acceptance / Packaging / Native Manual Closeout COMPLETE / ACCEPTED.**
Final root: `results/same-board-comparison-final-acceptance/20261017-022243/`.
Source: **916 focused / 2085 full PASS**, zero failures/errors/skips. Fresh-env:
**2085 discovered / 2060 PASS / 25 permitted optional image/video skips**, zero
failures/errors. Fresh onedir/windowed build: **exit 0, 63.789 s**; frozen profile
bytes match. Safe/mined packaged worker results, deterministic source equivalence,
existing dispatches, native startup and seven real packaged-child lifecycle cases
passed. The project user reported **A–L PASS** on that exact package, including a
Human WON / Stage 2 LOST / Stage 3 LOST comparison and full loaded-Replay capture.

The historical `20261017-014937/` root stays **BLOCKED**: nine isolated fixture
errors, corrected only in `tests/test_replay_statistics.py` at `a59d0d9` after
accepted Slice-4 commit `d81caa9`. The final acceptance restarted from the new
clean SHA; raw evidence remains unchanged. Full identity/hashes and manual gates
are in the [closeout](STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md).

At the historical Same-board closeout, slider track page-step behavior was
**OPTIONAL / DEFER** and normal drag/seek was correct. Accepted usability polish
now supplies direct track seek and independent synthetic cursors; the original
acceptance remains valid. Actual Human recorded trace versus synthetic cursor/
action-target route authorities remain separate. No general Human-versus-solver
speed winner is established.

Stage-3 Extended remains ACTIVE; frozen V1 / Model C remain unchanged.
**Representative-board Demonstrations / Timeline Analytics is FINAL ACCEPTANCE
PASS / CLOSED — Slices 0–4 COMPLETE / ACCEPTED**, including internal 3A/3B.
The [closeout](STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md) and
[accepted contract](STAGE3_TIMELINE_ANALYTICS_CONTRACT.md) preserve the fixed
exemplars and both report runs. No visual/manual substitution, official
100k/solver rerun or frozen-evidence modification. Final source regression and
source/report/document reconciliation PASS; no GUI/package gate was required.
The Viewer is now **FINAL ACCEPTANCE PASS / CLOSED**, as recorded above.
Visualization Usability Polish and Fixed-Exemplar Human/Domain Interpretation
are also CLOSED. Program K's research specification and Gate-R E0/E1 protocol are
FROZEN / ACCEPTED; its bounded experimental implementation and Gate-R E0/E1
qualification are accepted/closed. The E2 Effectiveness Protocol is FROZEN /
ACCEPTED, E2 implementation is **I1–I8 = 8/8 COMPLETE / ACCEPTED**, and the
R0 Attribution Amendment v1 is **CONTENT-FROZEN / ACCEPTED**. Conformance,
selection, setup repair and R0 harness `7e7f847` are accepted. Historical Real R0-A is COMPLETE /
INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED; no rerun. Remediation investigation/design
are CLOSED / ACCEPTED; V1.3.1 is frozen by exact tracked bytes, and remediation
1A–1W is 23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED. Fresh R0-A V2 Attempt #2
is COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED, with **PARTIAL SUCCESS**:
the static storage blocker is resolved but timing regressed. External timing-profile
artifacts are **PREPARED / NOT EXECUTED / FIX REQUIRED BEFORE EXECUTION**;
Phase 1 and Phase 2 remain NOT AUTHORIZED. Follow the correction/review/dry-check
sequence in the [current Program K boundary](#current-program-k-boundary). R0-B and Actual E2
are NOT RUN / NOT AUTHORIZED; complete R0 adjudication is NOT DONE, final N/concurrency
are NOT SELECTED and the final E2 Operating Envelope is NOT SELECTED / NOT FROZEN.
Effectiveness is NOT ESTABLISHED.
Milestone 10 remains ACTIVE.
The historical Same-board closeout
did not implement the later playback/route/cursor maintenance;
its dated record remains unchanged. No historical acceptance is reopened.

Earlier closeouts retain their dated next-milestone statements as historical
records; the roadmap above and [current handoff](../CURRENT_HANDOFF.md) describe
the current state.

## Deferred / evidence-triggered

- Arbitrary-seek checkpoint/cache optimization.
- Stage-3 Visualizer modeled-time slider / sub-action scrubbing (Viewer time seeking is already accepted; Comparison's accepted slider remains logical-index based).
- 120-fps UI target, easing selector and click pulse.
- Persistent Stage-3 presentation settings; settings dataclass until an external consumer exists.
- Runtime application/release display or version constant.
- Selectable algorithms/profiles and durable cross-version Stage3Execution transport.
- Richer physical model / Model C successor or refit.
- Action-specific OPEN / FLAG / CHORD timing and physical CHORD variants.
- CPS / burst / minimum inter-action constraints, anisotropy and human cognitive timing.
- Built-in screen recording unless later justified.
- Broader Program K selective flagging and richer / longer planning remain deferred;
  accepted E0/E1 qualification does not authorize extensions or production Gate P.

Revisit only with evidence and a separate specification/evaluation contract.
In the Stage-3 Visualizer, incremental forward is implemented; arbitrary seeks
still rebuild from index 0. The Exemplar Viewer uses immutable frame lookup.
Clearer Run/new-execution versus 결과 열기/retained-result labels remain a nonblocking
UX follow-up. Final WON with Step 0/current PLAYING and manual seek stopping autoplay
remain correct. Foundation F-2 stays **OPTIONAL / DEFER**; this closeout supplies no
new evidence to promote that transport-hardening item.

## Boundaries and references

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`. The viewer never supplies solver
decision input. Playback interval is not Model C time, CPU speed or human speed.
V1 official 100k results, algorithm, profile and qualification remain frozen.
Extended is separate scope and does not reopen accepted V1 or closed ZiNi work.

- [V1 final adjudication](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Frozen algorithm](../../STAGE3_ALGORITHM_SPEC_v1.md)
- [Frozen telemetry/benchmark specification](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Historical extension backlog](../../STAGE3_EXTENSION_BACKLOG.md)
- [ZiNi final adjudication](../zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md)
- [Documentation index](../README.md)
- [Current handoff](../CURRENT_HANDOFF.md)

New Extended records belong here. Existing frozen specs, audit/evidence paths,
official 100k artifacts and historical decisions retain their identities and locations.
