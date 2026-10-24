# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Durable recovery state for a new chat or context-loss event.
> Updated: 2026-10-24 (Asia/Seoul)

---

## 1. Authority / evidence order

When current state or implementation facts are disputed:

1. current Git source
2. current tests
3. executable verification
4. frozen specifications / final adjudications / current closeouts / this handoff
5. README / ARCHITECTURE / documentation index
6. prior AI interpretation or memory

Agreement between AIs is not proof.

The user performs Git manually. Do not claim an edit was staged/committed/pushed unless
the user reports it or live Git proves it.

---

## 2. Repository / environment

Repository:

`C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project`

Approved Python:

`C:\venvs\minesweeper\Scripts\python.exe -B`

Required execution environment for Program-K qualification/rehearsal work:

`PYTHONDONTWRITEBYTECODE=1`

Live Git / current implementation authority:

- The user reported the R0 Attribution Amendment v1 freeze procedure and its
  documentation commit/push completed before this recovery refresh.
- Do **not** guess the resulting latest HEAD SHA from this document. Verify live
  `main`, locally known `origin/main`, ahead/behind, worktree/index and
  `git diff --check` first.
- The accepted pre-R0-PRE implementation parent is
  `9071469e2e4a884722ea02e2faea3441d916876c`
  — `feat: add Program K E2 I8 readiness admission`.
- The current R0-PRE worktree intentionally contains an unaccepted eight-file
  observational candidate; do not reset, restore or discard it merely to obtain
  a clean tree.

Accepted Program K E2 implementation lineage:

| Slice | Accepted implementation commit |
| --- | --- |
| I1 | `aa687d2627dceeb037a6f79e1f4a7017e38c13f7` |
| I2 | `441e165acea308ba885615c25b7cd244b6a5f3ef` |
| I3 | `9c8acef772cc71de0dae09e4e238ed42bf05a1e4` |
| I4 | `f9a213b15e990cc50dedad6c8c10c42519593af7` |
| I5 | `bbc2d0ada1e42e1770085a7d5454f0f0d1929fbe` |
| I6 | `9fe69da293293ab22ad5c7a25cc3341863a10584` |
| I7 | `1e6355ecfc9497338d75ef3e723fddf2445d378b` |
| I8 / accepted pre-R0-PRE parent | `9071469e2e4a884722ea02e2faea3441d916876c` |

**I1–I8 = 8/8 COMPLETE / ACCEPTED.** I0 remains accepted architecture
mapping/boundary discovery and is excluded from the eight-slice denominator.
This does **not** mean R0 or Actual E2 is ready: the later accepted R0 Attribution
Amendment v1 defines normative R0 accounting/readiness semantics that the current
readiness/R0-PRE implementation must still be corrected to satisfy.

The frozen/accepted R0 Attribution Amendment v1 identity is:

- path:
  `docs/stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md`
- exact byte length: `58,052`
- SHA-256:
  `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`
- independent exact-byte re-audit:
  **PASS — BLOCKER 0 / REQUIRED 0 / OPTIONAL 5**
- disposition:
  **CONTENT-FROZEN / ACCEPTED**

The amendment file may intentionally retain its historical
`CANDIDATE — NOT CONTENT-FROZEN / NOT ACCEPTED` authoring header. The external
freeze/acceptance receipt is the live freeze-state authority; editing the
content-frozen bytes would require a new exact-byte audit and freeze.

The historical E1 qualified technical baseline remains
`6106f730320c35e7123a75526f34dbeadeef3c5d`
(`fix: bound Program K E1 evaluator phase`); its documentation closeout is
`c0ba2b55fa49bba1003578360f72fc8447cc73b9`. Only the three navigation docs and
the E1 closeout changed between those two E1 anchors; the later E2 implementation
commits above are separate. The E1 historical final full-source gate was `3359 / 3359 PASS`,
failures/errors/skips `0 / 0 / 0`, test retries `0`; it was not rerun for this
documentation-only midpoint update.

Current accepted E1 source/composite identities at that baseline:

- Slice 1 / plan:
  `8f60ef5ff1590f855562d5d6c58e0b3333f213da267ad742c1bf9e98b6edcb24`
- Slice 2 / execution:
  `45b1e40ad36f473a4682f36a152fea2904bcf0b58d0fb4c7016e7930356aac82`
- Slice 3 / audit:
  `b6cc2964e3b75b5d85889b9d69957ede6cf1789fb5d511618bbd747e36a5b211`
- Slice 4 / suite:
  `edd1943499bfecdedb3a64fca2489db58ffb84593651dd61cde04266e875ff24`
- Slice 5 / operational:
  `c538ef92a751e5cbb3d6cafd2a5a9cf8c0a154151161c797a77f340f372a78d5`
- Slice 6 / qualification:
  `939664757a5c308f599b6cf80eb0ac07081998e1fead5f465f5706ebe7071906`

Relevant current raw source identities:

- `experiments/program_k_e1_evaluator.py`:
  `254632b04ff445d6146fc039f4a4e89e63f47a19a7c652a8c7f1ba9587288b7d`
  / `30243 B`
- `experiments/program_k_e1_operational.py`:
  `1eb1e3b8e35d849c0306434253d05f5158fa41a993581cc4f84f1c55a404c935`
  / `56839 B`
- `experiments/program_k_e1_qualification.py`:
  `a7d4bc01220a1cf294909d1a5a02b7ba7cd2ec31687ad499b241e972fb5940c9`
  / `38455 B`

Host used for accepted E0/R3/F1 readiness and Actual E1 work:

- runtime: `Windows-11-10.0.26200-SP0`
- machine: `DESKTOP-OV6N603`
- Python: `3.12.10`, 64-bit AMD64

Verify live Git/runtime before separately authorized future work. Actual E1 is
accepted and must not be rerun for recovery. Do not reset to a remembered SHA
blindly if the repository has legitimately advanced.
---

## 3. Closed baselines

### Stage 1
- playable PyQt5 UI/UX
- Replay save/load/current-game replay
- Index/Time replay controls and speed control
- board analysis / 3BV / Ops
- ZiNi / Explorer foundations

### Stage 2
- Simple Algorithm
- exact probability fallback
- runner / Replay instrumentation

### Pre-Stage3
- deterministic benchmark-board infrastructure
- telemetry model/schema/repository/statistics
- official 100,000-game Stage-2 baseline
- architecture / engineering audit

### Stage-3 V1 — CLOSED / FROZEN

Qualified implementation / official 100k source:

`611984133b83be11bcd2105f401ecdddcfd68a15`

Official corpus:

`EXPERT_GENERAL_V1`, exact `[0,100000)`, first click `(0,0)`

Accepted final result under frozen Model C:

- WW/WL/LW/LL = `37702 / 0 / 0 / 62298`
- Stage-2 WW modeled total = `2,069,761,852,010 us`
- Stage-3 WW modeled total = `1,446,988,223,039 us`
- reduction ≈ `30.089144234937%`

This is a frozen modeled-physical-time result, not a 30% claim about human play or CPU time.

Official identities:

- Stage-2 DB: `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f`
- Stage-3 DB: `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e`
- Model C profile: `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`
- Model C timing table: `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b`

Do not reopen V1 merely because Extended work proposes cleaner behavior.

### ZiNi Improvement — CLOSED / V1 RETAINED

The advanced search work is closed as recorded in `docs/zini-improvement/`.
The final quality holdout `2,010,000 .. 2,010,099` remains unopened.

---

## 4. Stage-3 Extended milestone map

Stage-3 Extended remains **ACTIVE**.

Closed:

1. Execution / Playback / Visualizer Foundation
2. Version / Settings Identity Separation
3. Modeled-Time Playback / Synthetic Smooth Cursor Presentation
4. Human Mouse Trace / Path Visualization
5. Same-board Human / Stage-2 / Stage-3 Comparison
6. Representative-board Demonstrations / Timeline Analytics
7. Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer
8. Visualization Usability Polish
9. Fixed-Exemplar Human/Domain Interpretation

Milestone **10 — Program K: Logical Known-Mine Capability + Selective Physical
Materialization** is the active research milestone.

The Program-K research specification and Gate-R E0/E1 protocol remain
**FROZEN / ACCEPTED**. Current source/evidence establish the accepted qualification state:

- bounded experimental Program-K implementation exists;
- full P-8 is **PASS / ACCEPTED**;
- actual E0 is **E0_PASS / E0_QUALIFIED / ACCEPTED**;
- R-1 and R-2 readiness corrections are **CLOSED / ACCEPTED**;
- R3 Expert-scale non-E1 feasibility work is **CLOSED / ACCEPTED**;
- R3-C1 audit-feasibility correction is **CLOSED / ACCEPTED**;
- F1 compact post-hoc evaluator correction is **CLOSED / ACCEPTED**;
- independent F1 targeted re-audit is **PASS — BLOCKER 0 / REQUIRED 0**;
- Expert-scale compact evaluator rehearsal is **PASS — BLOCKER 0 / REQUIRED 0**;
- post-F1 full-source gate is **PASS — 3359 / 3359**;
- final E1 operating envelope is **ACCEPTED**;
- **Actual E1 is E1_PASS / E1_QUALIFIED / ACCEPTED; progression_allowed = true.**
- **Gate-R E0/E1 implementation qualification is CLOSED / ACCEPTED.**

Actual E1 state at this handoff:

- one `execute_e1` call; retries/resumes `0 / 0`;
- scheduled operations: `54 / 54 COMPLETE`; post-hoc evaluators: `18 / 18 COMPLETE`;
- all 72 operation exit codes: `0`;
- publication/readback: once each, successful, all ten consistency checks true;
- durable artifact: `results/program_k_research/e1-20261022T003214Z-fba3da048d46/`.

[Gate-R E1 closeout](stage3-extended/STAGE3_PROGRAM_K_E1_CLOSEOUT.md):
**FINAL PASS / ACCEPTED — BLOCKER 0 / REQUIRED 0**. This closes Gate-R E0/E1
implementation qualification; Program K effectiveness is **NOT ESTABLISHED**.

The [E2 Effectiveness Protocol](stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md)
is **FROZEN / ACCEPTED — CONTENT FREEZE PASS / BLOCKER 0 / REQUIRED 0**.
Program K E2 implementation slices **I1–I8 are 8/8 COMPLETE / ACCEPTED**; I0 is
accepted architecture mapping and is excluded from the denominator.

The [R0 Attribution Amendment v1](stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md)
is now **CONTENT-FROZEN / ACCEPTED** at exactly `58,052` bytes,
SHA-256 `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`.
Independent exact-byte re-audit: **PASS — BLOCKER 0 / REQUIRED 0 / OPTIONAL 5**.

**CURRENT NEXT:** correct and qualify the accepted I8 readiness layer plus the
existing eight-file R0-PRE candidate so they conform to the frozen amendment.
This is implementation/readiness work, not a new research slice and not Actual E2.
Real protocol-seed `U_KD / I_OD / I_OK` counts remain forbidden until the
amendment-conforming implementation is qualified and committed.

R0-A/R0-B are **NOT RUN**. No final N/concurrency or E2 Operating Envelope is
frozen. Actual E2 is **NOT AUTHORIZED / NOT RUN** and no effectiveness
PASS/FAIL/DEFER exists. Production modification/integration remains **NONE**.
Milestone 10 and Stage-3 Extended remain **ACTIVE**.

Useful accepted historical identities:

- Human Mouse Trace qualified SHA:
  `e32145fa5c114e1ce500ad2e837ef6000cc49cca`
- Same-board Comparison qualified source/package SHA:
  `a59d0d963bdf1544a03968163b884342e2797ee0`
- Timeline Analytics qualified implementation SHA:
  `4c488e033dd045f1c203ff500d824cfaffb7cc67`
- Viewer final qualified source:
  `ff6358ae62b6f343bda36069d7164bda9aebee74`
- Visualization Usability Polish qualified implementation:
  `31630dd6ffa2301c41534fca3b003838d865f313`

Historical acceptance identities remain historical even if later maintenance changes the branch.
---

## 5. Selected Exemplar Viewer — FINAL ACCEPTANCE PASS / CLOSED

Final status:

**FINAL ACCEPTANCE PASS — SELECTED EXEMPLAR BOARD-STATE RECONSTRUCTION / HUMAN INTERPRETATION VIEWER CLOSED**

**Slices 0–4 COMPLETE / ACCEPTED — BLOCKER 0 / REQUIRED 0**

Qualified source:

`ff6358ae62b6f343bda36069d7164bda9aebee74`
— `test: preserve frozen E/L pilot source provenance`

Production usability source:

`29af53b15d1fff144df5873b62fcec4af91adaaa`
— `feat: improve exemplar viewer inspection usability`

`ff6358a` changed only the reviewed experimental E/L provenance/test boundary after
the production usability commit; Viewer/application production bytes remained those
accepted by the user in native source-GUI testing.

Evidence lineage:

- historical pre-usability `1f90bec...` acceptance: superseded
- first final qualification at `29af53b`:
  `results/stage3-exemplar-board-viewer-final-acceptance/20261018T091846923796Z/`
  → permanent HOLD
- E/L repair:
  `results/stage3-e-l-source-compatibility-repair/20261018T093614465991Z/`
- final fresh PASS:
  `results/stage3-exemplar-board-viewer-final-acceptance/20261018T094900066913Z/`

Final qualification:

- focused `892 / 892 PASS`
- full `2390 / 2390 PASS`
- zero failures/errors/skips in development suite
- exact accepted real proof: 4 boards / 8 streams / 1508 actions
- fingerprint/order/type/target/status/safe-reveal/explicit-FLAG/terminal/result mismatch = 0
- two immutable/read-only SQLite opens
- package/build gate PASS
- packaged EXE SHA-256:
  `8f64ca07d6b86cb03839e3b6f7f86b4b1510adabc901292a921f1a8c872d7530`
- user native source-GUI acceptance on production tree `29af53b`: PASS

Closeout:

`docs/stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md`

Fixed exemplars:

- `73758` — maximum Stage-3 WW modeled advantage
- `73024` — lower-median WW delta exemplar
- `93557` — closest-to-zero Stage-3 WW advantage
- `1` — LL control

They are deterministic category exemplars, not a statistically representative sample.

---

## 6. Visualization Usability Polish — FINAL ACCEPTANCE PASS / CLOSED

Final status:

**Same-board Comparison usability ACCEPTED; Stage-3 Visualizer reference overlays ACCEPTED.**
**BLOCKER 0 / REQUIRED 0.**

Qualified implementation:

`31630dd6ffa2301c41534fca3b003838d865f313`
— `feat: add visualizer reference overlays`

Integrated documentation closeout on `main`:

`22e544a` — `docs: close visualization usability polish`

Qualification / acceptance summary:

- full source `2484 / 2484 PASS`, zero failures/errors/skips
- focused `453 / 453 PASS`, zero failures/errors/skips
- fresh Windows package build PASS; AMD64 / PE32+ GUI
- package EXE SHA-256:
  `26cfb55bbbe75bad29bb0461bf39eed6a2b3b203512b9144751dcd770530a08f`
- PROJECT USER source-GUI Same-board A–M: ALL PASS
- PROJECT USER source-GUI Visualizer V-A–V-I: ALL PASS
- packaged feature-native acceptance was not claimed

Closeout:

`docs/stage3-extended/STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md`

### 6.1 Accepted Same-board presentation boundary

- playback applies to selected run only
- Human timing modes: `Index` / actual `Replay Time`
- Stage 2 / Stage 3 timing modes: `Index` / `Model C Time`
- no shared synchronized Human/S2/S3 clock, playhead or normalized progress
- Index interval `20 .. 5000 ms`, default `200 ms`, minimum display `Max (20 ms)`
- Time speed uses exact quarter steps `0.25x .. 8x`
- direct logical-index track seek + native handle drag
- cumulative completed action-target route
- accepted smooth synthetic action-target cursor
- Human first synthetic anchor = first action target; no fabricated pre-first origin
- actual Human Mouse Trace remains the entire independent recording
- hidden-answer and action-target-route controls default OFF
- route contains committed targets only; pending/future targets are excluded
- selected target / route / synthetic cursor / actual Human trace remain distinct
- no solver/result recomputation from presentation-only updates

Human Replay elapsed and solver Model C remain different time authorities.

### 6.2 Accepted smooth-cursor semantics

- presentation refresh request around 16 ms; this is not semantic timing authority or guaranteed FPS
- straight geometry between rendered cell centers
- smoothstep `q = u²(3 - 2u)`
- same-cell actions remain stationary
- action/board commit only at authoritative action boundary
- partial progress updates overlay/presentation only
- pause/resume preserves partial progress
- manual navigation may cancel/align partial presentation to committed state
- late ticks may catch up multiple completed actions once
- synthetic presentation only, not recorded mouse motion / OS trajectory / calibrated acceleration
- easing and presentation rate never change Model C or planner decisions

Do not claim Minesweeper Online motion physics were copied; only a similar smooth replay feel
was the user-facing visual target.

### 6.3 Accepted Stage-3 Visualizer presentation boundary

- existing direct slider seek and native handle drag preserved
- First / Previous / Next / Last and Index playback preserved
- existing Model C Time playback and modeled smooth cursor preserved
- six speeds remain `0.25x / 0.5x / 1x / 2x / 4x / 8x`
- NO Index smooth interpolation added
- hidden-answer and action-target-route controls default OFF
- route contains executed targets only through the committed step
- pending target is excluded until commit; planned/future suffix is never a route source
- selected segment / route / synthetic cursor remain distinct

---

## 7. Fixed-Exemplar Human/Domain Interpretation — CLOSED

**FINAL ACCEPTANCE PASS — FIXED-EXEMPLAR HUMAN/DOMAIN INTERPRETATION CLOSED.**
**BLOCKER 0 / REQUIRED 0.** Gameplay inspection COMPLETE; additional gameplay NONE.
That interpretation closeout adopted no algorithm policy and authorized no
implementation. The later Program K research-specification freeze is recorded
in §7.1; Extended remains ACTIVE.

[Final closeout](stage3-extended/STAGE3_FIXED_EXEMPLAR_INTERPRETATION_CLOSEOUT.md)
records the accepted corrected synthesis, exact evidence identities/totals,
USER judgments and independent audit/final adjudication lineage.

Fixed exemplars remain `73758 / 73024 / 93557 / 1`: deterministic category
exemplars, **not a statistically representative sample**. This is qualitative
interpretation, not statistical validation or a general causal explanation.

The USER evaluates experienced/high-level Minesweeper speed play, not ordinary
human plausibility or human imitation. Machine facts and USER judgments remain separate.

Durable findings:

- **A — RECURRING WEAKNESS CANDIDATE / MEDIUM:** USER-identified incomplete local
  cleanup. Earlier public certainty was not verified for every cell. The 93557
  115→143 and terminal 200→201–203 revisits are not positive mechanical support.
- **B — recurring expert-play gap / HIGH:** USER-preferred direct OPEN versus
  recorded marking/reveal execution. The preferred OPEN may not be V1-admissible;
  do not claim V1 rejected an available direct OPEN.
- **B2 — SUB-PATTERN OF B / MEDIUM:** physical flag accumulation, strongest on
  73024 and 93557; no universal per-action setup/fallback attribution.
- **C — geometry FACT / HIGH; conditional weakness LOW, not independently
  established:** all d² >= 100 destinations are FLAG on the three WW exemplars,
  but several remote moves were rational. Geometry alone does not prove poor routing.
- **D — STRENGTH / HIGH:** productive local FLAG/CHORD progression. Preserve
  useful physical flags enabling CHORD as an evaluation constraint, not a policy adoption.
- **E — RESEARCH QUESTION ONLY / LOW / NOT ADOPTED:** realized-path efficiency
  versus decision robustness before new clues.
- **LL control:** game 1 executions match for four actions and both lose on action 4;
  `720354 us` each is termination cost only, not time-to-win. No meaningful
  support/refutation of A/B/B2/C/D.

Frozen V1 has no separate logical-known-mine state; local inference uses physical
FLAGs. Direct OPEN requires a current-certain safe HIDDEN cell. §12 current-certain
FLAG setup and §22 FLAG-only fallback preserve that boundary. At the interpretation
closeout, deferred P0 Known-Mine / No-Flag was qualitatively motivated by B/B2 but
**NOT ADOPTED**. The later Program K research selection/specification freeze (§7.1)
does not change that historical finding or authorize implementation.
Timeline ActionEvent retains neither Stage3Decision.plan nor an explicit setup/
fallback reason. No exact per-action §22 provenance or No-Flag saving is established.

No statistical prevalence, representative behavior, causal WW-delta explanation
or counterfactual whole-run outcome/cost is established. Nearest exact-minimum-risk
guess using movement cost remains a **separate backlog candidate, neither supported
nor refuted by this interpretation**.

### 7.1 Current Program-K boundary / NEXT

**Program K research specification and Gate-R E0/E1 research protocol remain
FROZEN / ACCEPTED.** They remain the semantic/protocol authorities; current
source/tests and accepted execution evidence determine implementation status.

Gate-R E0/E1 implementation qualification is **CLOSED / ACCEPTED**. The
[E1 closeout](stage3-extended/STAGE3_PROGRAM_K_E1_CLOSEOUT.md) holds the detailed
accepted execution, receipt, hashes and procedural notes. The readiness records
below are accepted historical provenance, not instructions to repeat qualification.

#### Accepted P-8 / E0

Full P-8:

- status: `PASS / ACCEPTED`
- evidence digest:
  `9ccffab72d34173181dd84170cf442156f2df888f03d87c1571660ba7774137d`

Actual E0:

- `E0_PASS / E0_QUALIFIED / ACCEPTED`
- artifact:
  `results/program_k_research/e0-20261020T091707Z-a64907341e6c/`
- qualification SHA-256:
  `71ee9b3a9dc0a24de7471be996da5069f5c77ed750485a84b298ee74b7065576`
  / `1,762,287 B`
- COMPLETE SHA-256:
  `a664e8dfdc5e6aa8a6fe02d6fabe84da3df901829c8291558d5d874d646eb522`
  / `520 B`

Do not rerun P-8 or E0 absent a real identity invalidation.

#### R-1 / R-2 / R3 — CLOSED

The independent readiness audit at historical baseline `88a366f...` found the
R-1 bounded external-FLAG qualification gap and R-2 exponential
`ExternalV1FlagProvenance.prior_flags` DAG expansion.

Current accepted disposition:

- **R-1 CLOSED:** >16-variable external frozen-V1 exact FLAG may qualify at E1 only
  through the accepted exact V1 validation + archived certainty + public
  Oracle-B/shared-kernel representation evidence path; raw independent
  Oracle-A result remains truthfully `NOT_EVALUATED`; raw FAIL is never upgraded.
- **R-2 CLOSED:** DAG-aware/memoized E1 qualification plus deterministic
  value-semantic suite/persistence codecs; structural scale coverage includes
  `k=16/32/64/98`.
- **R3-C1 CLOSED:** exact-history arithmetic reuse removed the O(P²+QP) audit
  feasibility defect without weakening evidence semantics.
- Accepted R3 Attempt 3 root:
  `results/program_k_research/r3-20261021T124332Z-4a74bbe2d1dd/`
- R3 Attempt 3 inventory SHA-256:
  `042550eed92b3401c37a6c7fca53ee6079a6238ba9f549769041db38c2e54d98`
- R3 accepted max operation wall:
  `202.141 s`
- R3 accepted max same-operation combined memory:
  `1,116,086,272 B`
- R3 max physical inputs:
  `207`
- repeated-max 54-scheduled descriptive projection:
  `6,772.23 s`

R3 is feasibility evidence, not actual E1 or effectiveness evidence.

#### F1 compact evaluator — CLOSED

Claude's final-readiness audit later promoted the old live evaluator architecture
to REQUIRED F1 because each of 18 evaluator targets repeatedly rebuilt/hashed/
transported the whole 54-run suite.

Accepted correction commit:

`6106f730320c35e7123a75526f34dbeadeef3c5d`
— `fix: bound Program K E1 evaluator phase`

Current live architecture:

`54 scheduled results -> aggregate once -> compact admission once -> 18 compact requests`

Per evaluator target there is no whole-suite rebuild/hash/transfer on the live path.
Hidden truth remains worker-only.

Independent Claude targeted re-audit:

**PASS — BLOCKER 0 / REQUIRED 0 — READY FOR EXPERT-SCALE EVALUATOR REHEARSAL.**

Its one procedural deviation was a read-only text search into preserved R3 evidence
for old digest locations; no R3 execution or mutation occurred. The verdict remains accepted.

Expert-scale evaluator rehearsal root:

`results/program_k_research/f1-evaluator-rehearsal-20261021T160656Z-6106f730320c/`

Accepted rehearsal facts:

- primary compact evaluators: `18 / 18 COMPLETE`
- total evaluator whole-call wall: `48.516 s`
- max evaluator whole-call wall: `3.796 s`
- max primary combined memory: `165,232,640 B`
- coordinator-retention challenge combined peak:
  `1,431,109,632 B`
- optional 1000-boundary stress:
  `15.250 s`, `COMPLETE`, combined `503,877,632 B`
- conservative projected archive usage after scheduled basis + evaluators:
  `252,166,662 / 536,870,912 B = 46.969701%`

#### Final full-source gate — CLOSED

Evidence root:

`results/program_k_research/f1-final-source-gate-20261021T234111Z-6106f730320c/`

Isolation-aware runner:

`C:\venvs\minesweeper\Scripts\python.exe -B scripts/run_source_unittest_isolated.py`

Result:

- MAIN: `3353 / 3353 PASS`
- ISOLATED: `6 / 6 PASS`
- combined: `3359 / 3359 PASS`
- failures/errors/skips: `0 / 0 / 0`
- retries: `0`
- process elapsed: `911.273551 s`

Exactly one isolated class remains:
`test_program_k_harness.ProgramKSlice7SupervisorTests`.

#### Final E1 operating envelope — ACCEPTED

Historical operating envelope used for the accepted Actual E1:

```text
max_decision_wall_ms         = 30000
max_case_wall_ms             = 420000
max_job_wall_ms              = 14400000
shadow_timeout_ms            = 1000
max_physical_inputs_per_case = 1000
memory_cap_bytes             = 4294967296
archive_cap_bytes            = 536870912
monitor_interval_ms          = 25
monitoring_policy            = WINDOWS_JOB_MEMORY_AND_STACK_SAMPLING_WATCHDOG_V1
```

F2 is **CLOSED** by widening the provisional case cap from `300 s` to `420 s`.
This is operational containment, not an effectiveness threshold and never
action-substitution authority.

#### Actual E1 — FINAL PASS / ACCEPTED

Authorization reference:

`CHATGPT_FINAL_E1_AUTHORIZATION_2026-10-22_FBA3DA0_CASE420S`

Accepted result:

- run_id: `e1-20261022T003214Z-fba3da048d46`;
- `E1_PASS / E1_QUALIFIED`; `progression_allowed = true`;
- final ChatGPT adjudication: **GATE-R E1 FINAL PASS / ACCEPTED**,
  **BLOCKER 0 / REQUIRED 0**;
- one external READY preflight, one execution, zero retries/resumes;
- `54` scheduled and `18` post-hoc evaluator operations COMPLETE, all exit `0`;
- publication/readback once each and successful; all ten consistency checks true;
- G1–G7/G9/G10 PASS; **G8 NOT_APPLICABLE**: Model-C diagnostics only,
  effectiveness belongs to E2;
- final phase `COMPLETED`, STOP `2026-10-23 13:36:14 KST`.

Primary report:
`results/program_k_research/e1-launch-20261022T003214Z-fba3da048d46/final-report.json`.
The [E1 closeout](stage3-extended/STAGE3_PROGRAM_K_E1_CLOSEOUT.md) preserves the
durable artifact identities and final adjudication. No new execute/assess/persist/
readback call or new run_id is authorized by recovery.

The approximately 28-hour launcher duration versus the recorded 6,617.328-second
supervised job, and missing authoritative postprocessing progress, are explicit
**NONBLOCKING performance/observability debt**. They do not reopen E1. The frozen
E2 protocol now requires bounded streaming/postprocessing, progress visibility and
operational admission checks. These are future implementation/readiness obligations;
documentation freeze does not repair the debt or authorize optimization.

#### E2 Effectiveness Protocol — FROZEN / ACCEPTED

The [frozen E2 protocol](stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md)
records final content adjudication **CONTENT FREEZE PASS / BLOCKER 0 / REQUIRED 0**
under `CHATGPT_PROGRAM_K_E2_PROTOCOL_CONTENT_FREEZE_2026-10-23_V2`.
E2-D0, the v0 audit, the v1 re-audit and the six bounded v2 corrections are complete;
no further independent v2 audit is claimed. Detailed lineage remains in the protocol.

- Frozen protocol commit: `6d3eb456d72632d24e9cab14bdeea0cffd279092`
- Git blob: `3351017f0f0116be00917be3ff95312120f43117`
- SHA-256: `10b1055a6e1bcab8e03ab504755c9c9d655d5457800318396afb6e31497ba2fa`

#### E2 implementation I1–I8 — COMPLETE / ACCEPTED

| Slice | Scope | State |
| --- | --- | --- |
| I0 | Architecture mapping / boundary discovery | ACCEPTED; excluded from implementation denominator |
| I1 | Identity + immutable evidence records | COMPLETE / ACCEPTED |
| I2 | Streaming append-only durable store | COMPLETE / ACCEPTED |
| I3 | Aggregate effectiveness analysis + shared bootstrap + verdict/report core | COMPLETE / ACCEPTED |
| I4 | Per-game CONTROL/K-P0 projection + full P-3 + G5 provenance + durable decision/plan/M projection | COMPLETE / ACCEPTED |
| I5 | Certificate/evaluator/Oracle-B/determinism audit adapters | COMPLETE / ACCEPTED |
| I6 | Execution/coordinator + operational/resource layer | COMPLETE / ACCEPTED |
| I7 | Integration qualification | COMPLETE / ACCEPTED |
| I8 | Readiness / R0 admission layer | COMPLETE / ACCEPTED |

**I1–I8 = 8/8 COMPLETE / ACCEPTED (100% implementation denominator).**
This closes the planned E2 implementation slices only. It does not establish
Program K effectiveness and does not authorize real R0 or Actual E2.

Accepted technical anchors:

- I1 `aa687d2627dceeb037a6f79e1f4a7017e38c13f7`
- I2 `441e165acea308ba885615c25b7cd244b6a5f3ef`
- I3 `9c8acef772cc71de0dae09e4e238ed42bf05a1e4`
- I4 `f9a213b15e990cc50dedad6c8c10c42519593af7`
- I5 `bbc2d0ada1e42e1770085a7d5454f0f0d1929fbe`
- I6 `9fe69da293293ab22ad5c7a25cc3341863a10584`
- I7 `1e6355ecfc9497338d75ef3e723fddf2445d378b`
- I8 / accepted pre-R0-PRE parent
  `9071469e2e4a884722ea02e2faea3441d916876c`

I8 provides readiness/R0-admission machinery only. It does not itself run R0,
choose the final N, freeze an Operating Envelope or authorize Actual E2.

#### R0 Attribution Amendment v1 — CONTENT-FROZEN / ACCEPTED

A later R0 boundary audit found that the original four-component R0 attribution
model did not fully account for shared rank-0 `control_maintenance`, repeat
Oracle-B and Oracle-caused downstream validation/IPC work. The accepted amendment
repairs the R0 accounting contract without changing treatment/research semantics.

Frozen amendment:

- path:
  `docs/stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md`
- exact bytes: `58,052`
- SHA-256:
  `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`
- independent final exact-byte re-audit:
  **PASS — BLOCKER 0 / REQUIRED 0 / OPTIONAL 5**
- final ChatGPT/user disposition:
  **CONTENT FREEZE PASS / ACCEPTED**

Key accepted amendment semantics include:

- base E2 protocol §2 authority order remains intact;
- prospective exact digest use for outcome-blind admission/count targets;
- symbolic real target counts
  `U_KD(N)`, `I_OD(N)`, `I_OK(N)`;
- complete standalone P/K/D wall boundaries;
- route-specific Oracle wall accounting:
  primary, O∩K K-bind, O∩D D-repeat;
- strict non-overlapping P/K/D/O/R bundle-stream byte ownership;
- fixed-allowance ownership/checking for supporting operational/provenance bytes;
- zero-row Oracle support;
- R64 maximum across every setup route that can produce rank-0 CM;
- R0-B synthetic-domain dominance rather than exact research-position matching;
- fail-closed payload, containment and fixed-allowance checks;
- external freeze receipt and downstream amendment provenance binding.

The amendment is normative only after its accepted freeze. Current source/tests
remain factual authority for what the implementation currently does; any mismatch
with the accepted replacement semantics is implementation nonconformance to repair,
not a reason to reinterpret the amendment.

#### Current unaccepted R0-PRE candidate

Before amendment freeze, an observational R0-PRE candidate was built in exactly
eight modified files:

- `experiments/program_k_e2_analysis.py`
- `experiments/program_k_e2_audit.py`
- `experiments/program_k_e2_execution.py`
- `experiments/program_k_e2_operational.py`
- `tests/test_program_k_e2_analysis.py`
- `tests/test_program_k_e2_audit.py`
- `tests/test_program_k_e2_execution.py`
- `tests/test_program_k_e2_operational.py`

Those files are **not accepted implementation**. Preserve them; do not discard
them merely because they predate the amendment. The candidate already contains
useful observational seams such as direct Oracle-B timing facts and shared
bootstrap progress, but its R0 attribution/readiness semantics must be revised to
the frozen amendment before qualification.

Entry SHA-256 values for the preserved eight-file candidate:

| Path | SHA-256 |
| --- | --- |
| `experiments/program_k_e2_analysis.py` | `5a60a9f68bb21a0f2ca12bd9c720a6e4931021339741c454fb055c5754f4d9e7` |
| `experiments/program_k_e2_audit.py` | `f6ba6a06a76c749a5a5ab9d52eaf1e21ba079888f33374b6f597097b4ef05bbd` |
| `experiments/program_k_e2_execution.py` | `099ca9d76166af7a50abf1a41c0a4862219431f5352ddf97367c0f1ded5e083e` |
| `experiments/program_k_e2_operational.py` | `a46f380567bbf0b2151ef78e4f713f0374f4d8f5e989e3aa26f0fa1bbdf0fec3` |
| `tests/test_program_k_e2_analysis.py` | `303babfc75065ca443f9c40b0a0f8a359e40950a7774e51e876c6597218f33b3` |
| `tests/test_program_k_e2_audit.py` | `de65634d6e9f46d52fc52ea2f35df046c20e4022c69bf3b1e7c9d476ddc9e4d9` |
| `tests/test_program_k_e2_execution.py` | `00ed698e341dd6ef1456da38d316826707e967cfc9f1866939f52e34e662c814` |
| `tests/test_program_k_e2_operational.py` | `ae8a0b631b8443804652171420211c3ef4dae936ce9dc258ecd78e05e8378da3` |

Historical pre-amendment candidate verification was strong
(255 focused; I3 95; I5 89; I6 124; I7 56; I8 55; E2/Program-K 1521;
Stage3/Model-C 726; full 4005 total, all zero fail/error/skip), but that evidence
does **not** qualify amendment conformance.

#### Current next work — amendment-conformance implementation correction

**NEXT: accepted amendment → readiness / R0-PRE implementation correction +
qualification.**

This work should minimally update the owning readiness/R0-PRE implementation and
tests so that the frozen amendment is executable, including route-specific Oracle
walls, `I_OK`, zero-byte Oracle observations, strict byte attribution, synthetic
R0-B dominance/search rules, payload/containment/fixed-allowance pass conditions
and amendment provenance.

Required order after the implementation correction:

1. qualify the amendment-conforming implementation;
2. commit it under the user's Git control;
3. only then compute real protocol-seed `U_KD(10000) / I_OD(10000) / I_OK(10000)`
   through the already-qualified deterministic rule;
4. accept/qualify the real R0 harness;
5. separately authorize and execute R0-A/R0-B;
6. adjudicate final N/concurrency and freeze the E2 Operating Envelope;
7. only then separately authorize Actual E2;
8. conditional E3 only if the frozen E2 trigger requires it;
9. Gate P remains a separate production decision.

The accepted amendment explicitly keeps R0-B synthetic evidence outside research,
rehearsal and holdout domains. Real target counts are numeric dominance targets
only; they do not authorize generating/using the real E2 corpus during readiness.

**Actual E2 is NOT RUN**; no effectiveness PASS/FAIL/DEFER result exists.
R0-A/R0-B are **NOT RUN**, no final N/concurrency has been selected, and no
Operating Envelope is frozen. Program K effectiveness remains
**NOT YET ESTABLISHED**. Production integration remains **NONE**.

#### Preservation / still forbidden

Do not:

- edit the frozen E2 protocol or content-frozen amendment bytes;
- rerun the official 100k;
- rerun E/L;
- rerun P-8/E0/E1/R3/F1 merely for reassurance;
- access ZiNi holdout `2,010,000 .. 2,010,099`;
- compute real protocol-seed `U_KD/I_OD/I_OK` before amendment-conforming
  implementation qualification + commit;
- run R0-A/R0-B before accepted harness + separate authorization;
- run Actual E2 before accepted R0 evidence + frozen Operating Envelope +
  separate authorization;
- execute conditional E3 without the frozen trigger;
- perform Gate P / production integration.

Stage-3 Extended remains **ACTIVE** until the later research/production closeout path completes.
---

## 8. Authority boundaries

Keep separate:

- application/release identity
- algorithm identity
- physical Model C identity
- presentation settings

Also keep separate:

- Replay
- Human Mouse Trace
- Stage-3 solver trace/playback
- ZiNi Trace

Time authorities:

- Human Replay elapsed seconds
- Stage-2 Model C microseconds
- Stage-3 Model C microseconds
- decision-compute nanoseconds
- UI presentation wall time

Do not collapse them into one generic speed clock.

Human Mouse Trace is actual sampled pointer data. Synthetic solver cursor/route is not.

ZiNi is a click-efficiency reference, not the Stage-3 speed objective.

---

## 9. Engineering principles / roles

Continue:

- SRP / Separation of Concerns
- maintainability
- extensibility
- testability
- backward compatibility
- KISS / YAGNI
- evidence before optimization
- minimum necessary abstraction

If something looks unnecessary, do not remove it immediately. First explain:

1. why it may be unnecessary
2. what would be lost
3. `KEEP / DEFER / REMOVE`

Roles:

- ChatGPT: design / review / final adjudication
- Codex: implementation / execution / verification
- Claude Code: independent read-only audit only when a high-risk milestone warrants it
- User: Git staging / commit / push / merge

Disputed findings return to source/tests/evidence.

---

## 10. New-chat recovery sequence

At a new chat or after context loss:

1. verify live Git branch / HEAD / locally available `origin/main` relationship /
   ahead-behind / worktree / index / `git diff --check`; never reset to a
   remembered SHA blindly;
2. read this `docs/CURRENT_HANDOFF.md`, then
   [Stage-3 Extended README](stage3-extended/README.md), then the
   [frozen E2 protocol](stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md)
   and the
   [frozen R0 Attribution Amendment v1](stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md);
3. authenticate the amendment exact identity before relying on its normative
   semantics: `58,052` bytes,
   SHA-256 `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`;
4. treat Program K E2 **I1–I8 as COMPLETE / ACCEPTED** and the accepted pre-R0-PRE
   parent as `9071469e2e4a884722ea02e2faea3441d916876c`;
5. preserve the current eight-file R0-PRE candidate; it is useful inspection
   material but is **not accepted** and must be corrected to the amendment rather
   than discarded or treated as R0 evidence;
6. **CURRENT NEXT is amendment-conforming readiness/R0-PRE implementation
   correction + qualification**. This recovery sequence does not itself authorize
   source edits, real target-count calculation, R0 or Actual E2;
7. real protocol-seed `U_KD/I_OD/I_OK` remain forbidden until the corrected
   implementation is qualified and committed;
8. R0-A/R0-B remain unrun; no final N/concurrency or Operating Envelope is frozen;
9. Actual E2 remains not authorized/not run; E3 remains conditional/later and
   Gate P remains separate;
10. read the [Gate-R E1 closeout](stage3-extended/STAGE3_PROGRAM_K_E1_CLOSEOUT.md)
    only when exact E1 history/evidence is needed; do not repeat E0/E1 execution,
    E2-D0/protocol/amendment audits, official 100k, E/L, P-8/R3/F1 or closed
    Viewer/Timeline/Polish work merely for recovery;
11. never open the ZiNi final holdout `2,010,000 .. 2,010,099`.

Recommended immediate source set for the next implementation-correction work:

- `experiments/program_k_e2_readiness.py`
- the preserved eight R0-PRE source/test files listed above
- `experiments/program_k_e2_qualification.py`
- `experiments/program_k_e2_identity.py`
- `experiments/program_k_e2_records.py`
- `experiments/program_k_e2_store.py`
- current relevant Program-K E2 tests
- frozen E2 protocol + frozen R0 Attribution Amendment v1

Do not preload or refactor unrelated production source merely to recover context.
---

## 11. Handoff maintenance rule

Update this handoff only at meaningful boundaries:

- milestone closeout
- branch/baseline transition
- major design freeze
- accepted strategy/version
- materially changed next action

Do not turn this file into a complete chronological audit log. Detailed historical facts
belong in their closeout/contract/evidence records.
