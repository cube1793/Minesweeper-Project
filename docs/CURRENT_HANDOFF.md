# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Durable recovery state for a new chat or context-loss event.
> Updated: 2026-10-28 (Asia/Seoul)

---

## 1. Authority / evidence order

When current state or implementation facts are disputed:

1. current Git source
2. current tests
3. executable verification / accepted Final Preflight evidence
4. frozen specifications / final adjudications / accepted closeouts
5. current recovery/navigation documentation, starting with this handoff
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

- At the accepted Final Preflight boundary and before this documentation refresh,
  live `main` and locally known `origin/main` both resolve to
  `48f6ebc97e6c4d3ed4a746a92a8d169783803bf9`;
  ahead/behind `0/0`, clean worktree/index,
  no nonignored untracked files, and `git diff --check` PASS.
- The historical source/documentation baseline used by the accepted Real R0-A
  execution and follow-on static review remains
  `c0bc270bce1996797f9ecec80e79ea8998d3205d`. The accepted technical harness
  ancestor remains `7e7f847816fedb77cef67b576eab665afabfbfbf`
  — `feat: add Program K E2 R0 harness`. Its direct parent is the accepted
  setup-containment repair
  `e6593f7a99af2f0dd941eda7ee53a5164c79a2bd`
  — `fix: retain R0 setup containment observations`.
- **R0 harness implementation: COMPLETE / ACCEPTED / COMMITTED / PUSHED.**
  **Historical Real R0-A: COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED.**
  The accepted evidence and static follow-on blocks are recorded in §7.1.
- Remediation **1A–1W: 23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED**.
  **FRESH R0-A FINAL PREFLIGHT — PASS**, at the exact technical source above.
  **Fresh R0-A: NOT RUN / NOT YET EXECUTION-AUTHORIZED**; no Fresh R0-A measurement
  exists. Eligibility and the recovery checkpoint are recorded below.
- Recheck live Git before future work. **ChatGPT final documentation CONTENT
  review: PASS.** This five-file documentation-only candidate is **authorized for
  USER commit/push**. If publication is incomplete, USER completes the remaining
  commit/push steps; live Git establishes whether publication has occurred.
  After committed/pushed publication, CURRENT NEXT is the narrow
  post-documentation authority re-anchor, then separate Fresh R0-A execution
  authorization, then only after that authorization Fresh R0-A execution.
  A later documentation-only HEAD does not replace the qualified technical source
  identity `48f6ebc97e6c4d3ed4a746a92a8d169783803bf9`.

### Post-1W / pre-Fresh-R0A recovery checkpoint

Accepted technical source:
`48f6ebc97e6c4d3ed4a746a92a8d169783803bf9`
— `feat: add Program K V2 R0-A run lifecycle`.

The accepted 23-slice implementation chain is present in Git through this source:

| Slice | Accepted implementation commit |
| --- | --- |
| 1A | `223442f955b610ff3ffdf4c2f150364b2ade4cff` |
| 1B | `22e9f7a1345d575cccf9ba6266c5a8d22560a464` |
| 1C | `a9f4d686d709aa436fc29789c5fd5a2c86e765b3` |
| 1D | `ebf44e7aef3953ce5361c393ac76ef7b9f8f3267` |
| 1E | `172f7aea6d088377665e5746791d9a76256d46f7` |
| 1F | `a2a4712748fd1250a911bb490c2e4816d1aa7a61` |
| 1G | `e003c556ae91c9f76408cbe8d6942c5fb0b94d1a` |
| 1H | `a3f64ff86c0390c4514be4b76fa9eb6dff851c4c` |
| 1I | `16230a09300880c97cfb29e0084f980ea8865a39` |
| 1J | `a296dc7cf3f66edf60567f2f09e29121e713b5d6` |
| 1K | `a68e3e98e888e2083ab7ef00d17c161cf21e4c7f` |
| 1L | `29618e26eba6248090de44575b8451bfd6915166` |
| 1M | `43f1baf939815a38750fe7b141132f857b2fde22` |
| 1N | `aa1a89b3600b3f8ace01ad2db1b7bcb90719307a` |
| 1O | `7c40230c8223cc47dbac96392b6b0a2cb9da0234` |
| 1P | `ff0a19b9f96309b5fa18045e337c007130a9b9ef` |
| 1Q | `2883a891838c96f1f8d8767a61312851998ffa2e` |
| 1R | `97c07fedc8de125a19ff9bf38171735c5b71065e` |
| 1S | `787f597bd8f47b88a1a3446c5ffa4d60cf10f22d` |
| 1T | `210fb40925c7687159d4b43d5746b967287dfcea` |
| 1U | `14ab5660da0a270ed9e5ffef9b16b8fb398ce3ea` |
| 1V | `f3b53c0e8bad8439691b1e4be0ad9a67c0c5d43d` |
| 1W | `48f6ebc97e6c4d3ed4a746a92a8d169783803bf9` |

**Slices 1A–1W: 23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED.**
**PROGRAM K REMEDIATION SLICE 1W — FINAL ACCEPTANCE PASS**;
**BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.

The following records the accepted USER-host Final Preflight evidence supplied
for this refresh; no preflight, regression or experiment was rerun here:

- **FRESH R0-A FINAL PREFLIGHT — PASS**;
  **BLOCKER 0 / REQUIRED 0 / OPTIONAL 1**.
- Fresh focused E2 regression: **Ran 1513 tests in 2070.996s — OK**;
  passed `1513`, failures/errors/skips `0/0/0`, process exit `0`.
  Post-test Git remained clean and synchronized at the technical source above.
- Approved Python: `C:\venvs\minesweeper\Scripts\python.exe` with `-B`;
  CPython `3.12.10`, `64-bit AMD64`, `Windows-11-10.0.26200-SP0`;
  `PYTHONDONTWRITEBYTECODE=1`, `sys.dont_write_bytecode=True`.
- V2 source closure: **42 source identities / 42 working-file identities**.
- Live qualified V2 codec profile: `qualified = true`, canonical byte length
  **8,555**, SHA-256
  `92fcf41858e2fc961b69a2f9f8fbb09d55591c52d595a343470af55463281193`.
  This is distinct from the frozen Model C physical profile below.

The exact technical source is **ELIGIBLE FOR SEPARATE FRESH R0-A EXECUTION
AUTHORIZATION**. This is eligibility only: **Fresh R0-A has NOT RUN and is NOT YET
EXECUTION-AUTHORIZED; no Fresh R0-A measurement exists**. Documentation CONTENT
review is **PASS** and USER commit/push is authorized. If the refresh is still
uncommitted or unpushed, USER publication is the only remaining documentation step.
**CURRENT NEXT after committed/pushed publication:** narrow post-documentation
authority re-anchor → separate Fresh R0-A execution authorization → only then
Fresh R0-A execution. Do not treat a later
documentation-only HEAD as a replacement qualification or execution identity.

Frozen authority identities remain separate from the live V2 codec profile:

| Authority | Bytes | SHA-256 |
| --- | ---: | --- |
| E2 Effectiveness Protocol | 57,841 | `10b1055a6e1bcab8e03ab504755c9c9d655d5457800318396afb6e31497ba2fa` |
| R0 Attribution Amendment v1 | 58,052 | `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf` |
| Frozen Model C physical profile | 6,059 | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` |
| Accepted selection receipt (§7.1) | 7,364 | `72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c` |

The accepted V1.3.1 design working-file identity is **29,284 bytes**, SHA-256
`48322762e2b7e883ddd0baa0114d3a7286dad790d8db9ce4ed7b67c5122bc878`.
Its LF-normalized Git blob is **28,475 bytes**, SHA-256
`4cc90077861b9caa3fa0147ebcc8c2539f96bc9834bfbec73d72785a3ef4ac30`.
CRLF-to-LF normalization exactly explains the difference; no semantic drift
occurred. Keep these byte representations distinct and preserve the frozen files.

### Earlier accepted implementation lineage

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
| I8 | `9071469e2e4a884722ea02e2faea3441d916876c` |

**I1–I8 = 8/8 COMPLETE / ACCEPTED.** I0 remains accepted architecture
mapping/boundary discovery and is excluded from the eight-slice denominator.
The later amendment-conformance implementation, setup-containment repair and R0
harness are also accepted. Historical R0-A evidence is accepted and closed; R0-B is
NOT RUN / NOT AUTHORIZED. Complete R0 adjudication and the final E2 Operating
Envelope remain outstanding. The two confirmed static follow-on feasibility
blocks remain historical findings for the old source/representation. Neither
implementation nor historical R0-A acceptance authorizes Actual E2.

The frozen/accepted R0 Attribution Amendment v1 identity is:

- path:
  `docs/stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md`
- exact byte length: `58,052`
- SHA-256:
  `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`
- independent exact-byte re-audit:
  **PASS — BLOCKER 0 / REQUIRED 0**
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
documentation-only refresh.

Historical accepted E1 source/composite identities at that baseline:

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

Historical E1 raw source identities at that baseline:

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

### Stage 1 — CLOSED

- playable PyQt5 UI/UX
- Replay save/load/current-game replay
- Index/Time replay controls and speed control
- board analysis / 3BV / Ops
- ZiNi / Explorer foundations

### Stage 2 — CLOSED

- Simple Algorithm
- exact probability fallback
- runner / Replay instrumentation

### Pre-Stage3 — CLOSED

- deterministic benchmark-board infrastructure
- telemetry model/schema/repository/statistics
- official 100,000-game Stage-2 baseline
- architecture / engineering audit

### Stage-3 V1 — FINAL ADJUDICATION PASS / CLOSED / FROZEN

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
The final quality holdout `2,010,000 .. 2,010,099` remains forbidden/unopened.

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

Program K is the whole research program; E2 is its effectiveness experiment.
Gate P is later production/integration qualification after E2 and any required E3.
The current position is **PRE-ACTUAL-E2**; no milestone 11+ is frozen.

The Program-K research specification and Gate-R E0/E1 protocol remain
**FROZEN / ACCEPTED**. Current source/evidence establish the accepted qualification state:

- bounded experimental Program-K implementation exists;
- full P-8 is **PASS / ACCEPTED**;
- actual E0 is **E0_PASS / E0_QUALIFIED / ACCEPTED / CLOSED**;
- R-1 and R-2 readiness corrections are **CLOSED / ACCEPTED**;
- R3 Expert-scale non-E1 feasibility work is **CLOSED / ACCEPTED**;
- R3-C1 audit-feasibility correction is **CLOSED / ACCEPTED**;
- F1 compact post-hoc evaluator correction is **CLOSED / ACCEPTED**;
- independent F1 targeted re-audit is **PASS — BLOCKER 0 / REQUIRED 0**;
- Expert-scale compact evaluator rehearsal is **PASS — BLOCKER 0 / REQUIRED 0**;
- post-F1 full-source gate is **PASS — 3359 / 3359**;
- final E1 operating envelope is **ACCEPTED**;
- **Actual E1 is E1_PASS / E1_QUALIFIED / ACCEPTED / CLOSED; progression_allowed = true.**
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
Independent exact-byte re-audit: **PASS — BLOCKER 0 / REQUIRED 0**.

Amendment conformance (`cdba3513`), the accepted N=10000 target counts/synthetic
selection, setup-containment repair (`e6593f7`) and R0 harness (`7e7f847`) are
complete/accepted. The harness is committed/pushed; see the exact authorities,
receipt and qualification history in §7.1.

**Historical Real R0-A is COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED; do not
rerun it merely for reassurance.** Its post-run integrity review and the separate
read-only follow-on static feasibility review are complete. Execution-wall
admission under the old source and R0-B minimum whole-archive feasibility under
the old representation remain **STATICALLY BLOCKED; historical proof preserved**.

Remediation engineering investigation is **CLOSED / ACCEPTED**. The
[remediation design V1.3.1](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md)
is **FINAL DESIGN ACCEPTED / FROZEN BY EXACT TRACKED BYTES**;
[acceptance receipt](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md):
**BLOCKER 0 / REQUIRED 0 at the design boundary; design phase CLOSED**.
Remediation **1A–1W: 23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED**.
**FRESH R0-A FINAL PREFLIGHT — PASS** at technical source
`48f6ebc97e6c4d3ed4a746a92a8d169783803bf9`; **BLOCKER 0 / REQUIRED 0 / OPTIONAL 1**.
That source is **ELIGIBLE FOR SEPARATE FRESH R0-A EXECUTION AUTHORIZATION**.
**Fresh R0-A: NOT RUN / NOT YET EXECUTION-AUTHORIZED; no measurement exists.**
**CURRENT NEXT after committed/pushed publication: narrow post-documentation
authority re-anchor → separate Fresh R0-A execution authorization → only then
Fresh R0-A execution.** Documentation CONTENT review is PASS; if publication is
pending, USER completes the authorized commit/push first. See §2 for the accepted evidence.
Historical R0-A and both static blocks remain evidence for the old
source/representation; fresh operational evidence is still required.
Real R0-B is **NOT RUN / NOT AUTHORIZED**; no executed R0-B
failure is claimed. Complete R0 adjudication is **NOT DONE**. No final N/concurrency
or E2 Operating Envelope is selected/frozen. Actual E2 is **NOT RUN / NOT
AUTHORIZED**, E2 PASS/FAIL/DEFER is **NONE**, and effectiveness is **NOT ESTABLISHED**.
E3 is conditional/not triggered; Gate P, production integration and native visual
acceptance have not started. Program K final closeout is not done; milestone 10
and Stage-3 Extended remain **ACTIVE**.

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

The supervised execution wall was **6,617.328 s (approximately 1h50m17s)**.
The complete launcher took approximately **28 h** because substantial assessment,
persistence, readback, reconstruction and report work followed execution. The
28 h is neither modeled gameplay time nor supervised execution time. This and
missing authoritative postprocessing progress remain historical **NONBLOCKING
performance/observability debt**; they do not reopen E1. Accepted E2/R0 machinery
now provides bounded postprocessing and admission paths. Real R0-A operational
evidence is accepted; R0-B postprocessing remains unrun and statically blocked.
E1 and R0-A do **not** establish Program K effectiveness.

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
- I8
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
  **PASS — BLOCKER 0 / REQUIRED 0** (historical audit also recorded OPTIONAL 5)
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

#### Amendment conformance — COMPLETE / ACCEPTED

Accepted commit: `cdba3513c23df77ba44449af1e551889a6954768`
— `feat: conform Program K R0 readiness to frozen amendment`.
The former eight-file R0-PRE candidate is historical; amendment-conforming
implementation has been qualified and committed. There is no current unaccepted
R0-PRE worktree candidate to recover.

Historical pre-amendment qualification remains historical: 255 focused; I3 95;
I5 89; I6 124; I7 56; I8 55; E2/Program-K 1521; Stage3/Model-C 726; full source
4005 total, all zero failure/error/skip. That earlier gate did not itself qualify
amendment conformance.

Accepted conformance qualification:

- focused `386/386 PASS`;
- complete Program-K E2 `666/666 PASS`;
- related Stage-3 / Model-C `116/116 PASS`;
- full source isolation-aware gate `4025/4025 PASS`: `4019 MAIN + 6 ISOLATED`.

Ordinary combined discovery exposed the known `ProgramKSlice7SupervisorTests`
coordinator-memory accumulation interaction. The accepted isolation-aware runner
includes every discovered test exactly once. This accepted boundary is closed;
do not rerun monolithic discovery merely to reproduce that interaction.

#### Accepted target counts / synthetic selection

The [accepted selection receipt](../results/program-k-e2-r0-selection/20261024T122548.464267Z-9fb5a7c7/selection-receipt.json)
is `7,364` bytes, SHA-256
`72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c`.
Its historical selection HEAD is `cdba3513c23df77ba44449af1e551889a6954768`,
separate from the current accepted harness HEAD. The receipt retains its original
candidate wording; subsequent acceptance does not rewrite those evidence bytes.

| Count | Real exact N=10000 | Selected synthetic 10k | Dominance margin |
| --- | ---: | ---: | ---: |
| U_KD | 505 | 506 | +1 |
| I_OD | 2 | 4 | +2 |
| I_OK | 3 | 4 | +1 |

No other real N was counted. Selected synthetic ordinal: **5**; exact range:
**[2,000,000,050,000, 2,000,000,060,000)**; digest:
`b78485dc50dc051d42645059bb86c39c1d4ca9db6cc3ba3be9d9290413831efb`.
No auxiliary O∩D/O∩K fixture was required. Selection was outcome-blind and
included no real R0 or Actual E2. These accepted counts/selection must not be
recounted or re-searched for recovery. The synthetic workload is outside
research/rehearsal/holdout domains; numeric dominance targets do not authorize
opening the Actual-E2 corpus.

#### Setup-containment observation repair — FINAL ACCEPTANCE PASS

Accepted commit: `e6593f7a99af2f0dd941eda7ee53a5164c79a2bd`
— `fix: retain R0 setup containment observations`.
**BLOCKER 0 / REQUIRED 0**.

This closed the first harness discovery blocker by retaining independent setup
observations for `K`, `D`, `O_K_SETUP` and `O_D_SETUP`. Setup boundaries and
memory peaks are observed directly, not reinterpreted from parent component
maxima. The immutable operational facts are consumed by the accepted harness.

Historical qualification: Operational `86/86 PASS`; complete E2 family
`676/676 PASS`; related Stage-3 / Model-C `739/739 PASS`; full isolation-aware
source gate `4035/4035 PASS`.

#### R0 harness — FINAL ACCEPTANCE PASS / COMMITTED / PUSHED

Accepted commit: **`7e7f847816fedb77cef67b576eab665afabfbfbf`**
— `feat: add Program K E2 R0 harness`.
**BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.

Historical final accepted candidate identities at the harness commit:

| Path | SHA-256 |
| --- | --- |
| `experiments/program_k_e2_r0_harness.py` | `d6dd01e512ae654e2024990d0ae2b26a801173b9ea98c1a0672e30f7c67b2778` |
| `tests/test_program_k_e2_r0_harness.py` | `3db501ee0ad753195304fdd2d2c02d1fff9b885fc224a8cc5f60e7010fdc6183` |
| `experiments/program_k_e2_qualification.py` | `2f7a4f603bf6d81e6ff0efb64529cd244bbc19aa24b8a16583f475057ad5306a` |
| `tests/test_program_k_e2_qualification.py` | `2a194361287a71b9804508d241658bdeceb3e1c8b808754b4b0ffa9871eda2c5` |
| `tests/test_program_k_e2_readiness.py` | `219f94368a6e80314330100b526782da99a1d9adcf2c19788a7e03135cc2103b` |

Final qualification root:
`results/program-k-e2-r0-harness-qualification/20261024T165944.7530305Z-e2118d4d/`.
The [saved qualification summary](../results/program-k-e2-r0-harness-qualification/20261024T165944.7530305Z-e2118d4d/qualification-summary.json)
records the pre-commit candidate qualification; subsequent ChatGPT acceptance and
the committed HEAD above establish the final accepted state.

| Historical qualification gate | Result |
| --- | --- |
| Readiness module | 66/66 PASS |
| Complete E2 family | 758/758 PASS |
| Related Stage-3 / Model-C / provenance | 739/739 PASS |
| Full source isolation-aware gate | 4117/4117 PASS |
| MAIN | 4111/4111 PASS |
| ISOLATED | 6/6 PASS |

All discovered tests were included exactly once; failures, errors, skips,
expected failures and unexpected successes were all `0`. Full-gate process
elapsed: `1,173.994 s`. These are accepted historical results, not tests rerun by
this documentation refresh. No independent Claude re-audit was required after
ChatGPT final source/test review.

The qualification HOLD was a historical `SourceReviewTests` fixture coupling
issue. The accepted test-only repair explicitly mocks the historical I7/I8
positive candidate and retains later/harness worktree rejection. The production
readiness historical review guard was not broadened; current harness provenance
is separate.

Recovery-level harness capabilities:

- strict exact accepted receipt authentication, distinct historical selection
  HEAD/current harness HEAD, and committed-clean-source/ancestry launch gates;
- explicit `R0_A` / `R0_B` authorization before operational I/O or execution;
- exact first-64 R0-A plans at `c = 1,2,4`, six operational measurement routes,
  independent `O_K_SETUP` / `O_D_SETUP` containment, immutable evidence/readback;
- exact selected synthetic 10k R0-B workload, six attributable durable families,
  zero-row Oracle handling, supporting streams and fixed-allowance enforcement;
- full frozen `10,000`-replicate production R0-B bootstrap, five bounded
  postprocessing phases, and manifest/provenance/failure-atomic publication.

R0 evidence itself grants no Actual-E2 or final-envelope authority and is not
Program K effectiveness evidence.

#### Historical Real R0-A — COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED

The single separately authorized initial calibration run is accepted. R0-A work
and its post-run integrity review are **CLOSED / COMPLETE**. Do not rerun R0-A or
any unit merely for reassurance. This is
**OPERATIONAL_NON_EFFECTIVENESS_R0_EVIDENCE**, not Program K effectiveness evidence.

Existing root:
`results/program-k-e2-real-r0a/20261024T193317.738335Z-2af3a8ca/`.
Run and review source HEAD: `c0bc270bce1996797f9ecec80e79ea8998d3205d`.
The exact accepted selection receipt remains the 7,364-byte receipt linked above.

| Retained artifact within the R0-A root | Bytes | SHA-256 |
| --- | ---: | --- |
| `manifest.json` | 19,256,799 | `60adb78437d6edce767d05f7a9cb79fead0fcedf0a8b349559ab7cbd1da19edb` |
| `COMPLETE.json` | 422 | `1ecea386f404f54ddc875ccf17398cc1c48e86ed40d43a76f834d95c2cf6954e` |
| `r0a-observations.json` | 19,826,611 | `cf624bdc88f601d22f7ab9f52e630374b9b17ec0085584cb19796684142adb7c` |

- Source identity digest covering 37 bound files:
  `1db7293ec43835b44542c1373e5ce55424e3cc06e0d10f39dab2430b2d7cb163`.
- First-64 corpus identity digest:
  `bb1202fad3ed2f3d89026aed071a1a9c1e7140b09f2cdf326a52c86cec3f2a78`.
- Frozen protocol/amendment identities are the exact hashes recorded above;
  both bindings, the selection binding and current-source provenance passed.
- Launcher start: **2026-10-25 04:33:17.772727 KST**.
- Launcher return: **2026-10-26 04:18:00.538514 KST**.
- Wrapper elapsed: **85,482,777,754,500 ns = 23h 44m 42.7777545s**; exit code **0**.
- `COMPLETE.json` records `COMPLETED`; `FAILED.json` is absent. The retained
  `INCOMPLETE.json` state `INCOMPLETE_AT_CREATION` is expected historical evidence;
  do not delete, relabel or repair it.
- Accepted run status:
  `COMPLETE_FOR_INDEPENDENT_REVIEW_NOT_ENVELOPE_ADMISSION`.
- Manifest/inventory/completion hashes, exact observation readback and adapter
  reproducibility passed; no unexpected archive drift was found.
- c=1,2,4 each completed P, K, O, D, O_K_BIND and O_D_REPEAT: **18/18 routes,
  64/64 positions per route**, the same first-64 identities and distinct run IDs.
- Required prerequisite/setup coverage and watchdog/resource/cleanup/progress/
  readback evidence are complete; recorded watchdog/resource breaches **0**.
- No initial calibration cap was breached. Highest measured utilization:
  **combined memory 36.6940%**. This does not freeze the final E2 envelope.

The wrapper elapsed is the whole R0-A operator session, not any single component
wall or measured/projected Actual-E2 runtime. R0-A component job/launcher caps and
the frozen Actual-E2 admission ceiling have different scopes.

#### Historical follow-on static feasibility review — COMPLETE / TWO CONFIRMED BLOCKS

The separate source/arithmetic review reused accepted R0-A evidence and the exact
receipt at the same source HEAD. It performed no R0-A rerun, R0-B, Actual E2,
board/solver/bootstrap/materialization, target recount or synthetic re-search.
No source/test/docs/evidence mutation occurred during that read-only review.
Current source and the frozen amendment agreed on the governing rules.

**A. EXECUTION-WALL ADMISSION: STATIC FEASIBILITY BLOCKED.**

The frozen amended six-term execution projection is:

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

For every allowed N in **{1000, 2500, 5000, 10000}**, both K/D multipliers use
`min(N,256) = 256`. Therefore the necessary lower bound is
**L(c) = 8 * (K64(c) + D64(c))**, without a further division by c or a new subset
count. The frozen Actual-E2 launcher admission ceiling is **43,200 seconds = 12 h**.

| c | Exact K+D admission lower bound, ns | Hours | Stronger N=1000 P+K+D+Oracle-primary lower bound, h |
| ---: | ---: | ---: | ---: |
| 1 | 115,091,421,316,800 | 31.9698392547 | 45.4706941160 |
| 2 | 88,150,611,100,000 | 24.4862808611 | 34.9850789298 |
| 4 | 74,918,532,917,600 | 20.8107035882 | 29.3375792716 |

K+D alone exceed 12 h for **every measured c and every allowed N**. Omitted P,
Oracle and postprocessing terms are nonnegative; the stronger bound still omits
intersection terms and postprocessing. These are frozen-admission projection
lower bounds, **not measured Actual-E2 runtimes**. Do not invent zero actual
intersection counts or subtract setup from the accepted K/D complete standalone
walls: the amendment intentionally requires that conservative full scope.

**B. R0-B MINIMUM WHOLE-ARCHIVE FEASIBILITY: STATICALLY BLOCKED.**

The accepted pure `derive_r0b_sizing_plan(...)` result uses observed maximum
attributable unit sizes across all measured c and the exact selected synthetic
counts. Oracle sizing takes the maximum across primary/repeat observations;
reference sizing covers every required R64 setup route.

| Family | Observed max B | ceil(3/2 max) B | Count | Minimum family subtotal B |
| --- | ---: | ---: | ---: | ---: |
| primary | 3,744,932 | 5,617,398 | 10,000 | 56,173,980,000 |
| k_control | 19,723,787 | 29,585,681 | 256 | 7,573,934,336 |
| oracle_primary | 5,698,786 | 8,548,179 | 128 | 1,094,166,912 |
| oracle_repeat | 5,698,786 | 8,548,179 | 4 | 34,192,716 |
| determinism | 15,238,396 | 22,857,594 | 256 | 5,851,544,064 |
| reference | 4,373,733 | 6,560,600 | 506 | 3,319,663,600 |
| **Total** | | | | **74,047,481,628** |

- Required minimum attributable total: **74,047,481,628 B ≈ 68.9621 GiB**.
- Frozen whole-archive cap: **17,179,869,184 B = 16 GiB**.
- Minimum/cap: **4.310131x**; minimum excess: **56,867,612,444 B**.
- Primary alone: **56,173,980,000 B ≈ 52.32 GiB**, already above the entire cap.
- Supporting/report/finalization overhead is unmeasured because R0-B has not run;
  omitted overhead is nonnegative. The fixed allowance is not negative budget credit.
- Minimum per-unit composite payloads **do fit** the **67,108,864 B** payload cap.
  Largest minimum: determinism + oracle_repeat = **31,405,773 B**, **46.7982%**.
  This is minimum-sizing feasibility, not a realized-payload acceptance result.
- The demonstrated block is the **whole synthetic archive**, not minimum
  per-unit payload fit. The launcher has no early minimum-total-archive preflight;
  cumulative writing and final accounting still enforce the archive cap.

The 74,047,481,628 B figure is a required minimum calculation, **not an archive
that was written**. No real R0-B failure occurred: R0-B was never run. Both static
blocks leave R0-A evidence integrity/acceptance valid and Program K effectiveness
untested. No final N, concurrency or envelope can be approved from these findings.

#### Exact current state / current next and conditional future path

| Item | Current post-1W / pre-Fresh-R0A state, 2026-10-28 |
| --- | --- |
| Stage-3 Extended milestones 1–9 | CLOSED |
| Milestone 10 / Program K | ACTIVE |
| E2 I1–I8 | COMPLETE / ACCEPTED |
| R0 preparation lineage | Amendment conformance / counts / selection / setup repair ACCEPTED |
| R0 harness implementation | COMPLETE / ACCEPTED / COMMITTED / PUSHED |
| Historical Real R0-A execution / integrity | COMPLETE / PASS |
| Historical Real R0-A evidence / work | ACCEPTED / CLOSED; DO NOT RERUN merely for reassurance |
| Historical R0-A post-run integrity review | COMPLETE |
| Historical R0 follow-on static feasibility review | COMPLETE |
| Historical execution-wall admission / old source | STATICALLY BLOCKED; historical proof preserved |
| Historical R0-B minimum archive / old representation | STATICALLY BLOCKED; historical proof preserved |
| Remediation engineering investigation | CLOSED / ACCEPTED |
| Remediation design V1.3.1 | FINAL DESIGN ACCEPTED / FROZEN BY EXACT TRACKED BYTES |
| Design boundary | BLOCKER 0 / REQUIRED 0; design phase CLOSED |
| Remediation implementation 1A–1W | 23/23 COMPLETE / ACCEPTED / COMMITTED / PUSHED |
| Slice 1W final acceptance | PASS; BLOCKER 0 / REQUIRED 0 / OPTIONAL 0 |
| Fresh R0-A Final Preflight | PASS at technical source `48f6ebc`; BLOCKER 0 / REQUIRED 0 / OPTIONAL 1 |
| Exact qualified technical source | ELIGIBLE FOR SEPARATE FRESH R0-A EXECUTION AUTHORIZATION; full identity in §2 |
| Documentation CONTENT review / publication | PASS; USER commit/push authorized; if publication is pending, USER completes the remaining steps |
| Current next after committed/pushed publication | Narrow post-documentation authority re-anchor → separate Fresh R0-A execution authorization → only then execution |
| Fresh R0-A | NOT RUN / NOT YET EXECUTION-AUTHORIZED; no measurement exists |
| Real R0-B | NOT RUN / NOT AUTHORIZED; no executed failure claimed |
| Complete R0 adjudication | NOT DONE |
| Final N / final concurrency | NOT SELECTED / NOT SELECTED |
| Final E2 Operating Envelope | NOT SELECTED / NOT FROZEN |
| Actual E2 | NOT RUN / NOT AUTHORIZED |
| E2 PASS/FAIL/DEFER | NONE |
| Program K effectiveness | NOT ESTABLISHED |
| E3 | CONDITIONAL ONLY / NOT TRIGGERED |
| Gate P | NOT STARTED |
| Program K production integration | NOT STARTED |
| Native K visual acceptance | NOT STARTED |
| Program K final closeout | NOT DONE |
| Stage-3 Extended | ACTIVE |

**CURRENT NEXT after committed/pushed publication: narrow post-documentation
authority re-anchor before separate Fresh R0-A execution authorization.**
The [exact V1.3.1 design](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md)
and [live acceptance receipt](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md)
record final design acceptance and the execution boundary. The design retains its
historical pre-re-audit wording; the receipt records the subsequent closure re-audit
PASS and ChatGPT/user final design acceptance. Its implementation-not-started
wording describes that historical design boundary; the accepted implementation
and Final Preflight checkpoint is now §2. Preserve the receipt's exact bytes.

Documentation CONTENT review is **PASS**; this candidate is **authorized for USER
commit/push**. If it is still uncommitted or unpushed, USER completes the remaining
publication steps. Once committed/pushed:

1. Perform a narrow post-documentation authority re-anchor, retaining `48f6ebc`
   as the qualified technical source and identifying the later documentation HEAD
   separately; this re-anchor has not yet been performed.
2. Obtain separate Fresh R0-A execution authorization.
3. Only then execute Fresh R0-A.

Historical scope of the now **CLOSED / ACCEPTED** engineering investigation:

- Time: investigate K/D complete standalone costs, prerequisite setup versus
  remaining complete-wall cost, reference preparation, encoding/transport/IPC,
  worker/coordinator validation/admission, persistence/readback/cleanup, and
  O_K_BIND handling with weak/negative concurrency scaling. Its measured walls
  at c=1,2,4 were 3018.3200812 / 2995.5455936 / 3075.1226738 s. Do not infer an
  exact bottleneck cause or pure solver time from these aggregate intervals.
- Bytes: investigate the primary max attributable unit of **3,744,932 B**
  (approximately 3.745 MB), semantically required evidence versus incidental
  operational representation, possible semantically equivalent compact
  representation, and the missing early minimum-total-archive preflight.
- Do not begin by raising the 16 GiB cap or 12-hour ceiling, reducing the 3/2
  sizing factor, weakening subset sizes, changing the N ladder or attribution
  formula, or changing Program K policy/effectiveness thresholds. Any contract
  change requires separate adjudication; no such change is accepted here.

The historical R0-A evidence and both static blocks above remain unchanged for the
old source/representation. Remediation implementation and Final Preflight are
accepted at the technical source in §2, but fresh R0 evidence does not yet exist.
The preflight PASS establishes eligibility only. After the sequence above,
Fresh R0-A and fresh admission/constructibility review must precede any separate
R0-B authorization. Complete R0
adjudication must precede final N/concurrency/envelope selection and freeze.
Actual E2 still needs separate authorization; E3 remains conditional
on its frozen trigger. Gate P, production integration, native K visual acceptance,
Program K closeout and Extended closeout remain later conditional work.
These are program boundaries, not newly frozen roadmap milestones 11+.

#### Planned Program K visual acceptance — NOT STARTED

After Gate P / production integration and before Program K final closeout, the
existing Stage-3 visualization architecture should support inspection of an
actual completed K trace replay, not live streaming. Planned acceptance should
show logical-known-mine state distinctly from ordinary `HIDDEN` and physical
`FLAG`, with action target, route and synthetic cursor also distinguishable.
Prefer the normal user-facing/native application flow for exhibition use.
A later optional same-board Human / Stage-2 / V1 / K comparison may reuse the
existing independent-playhead architecture. This is future acceptance scope;
no K visual implementation or native acceptance is claimed here.

#### Preservation / still forbidden

Do not:

- edit the frozen E2 protocol or content-frozen amendment bytes;
- rerun the official 100k;
- rerun E/L;
- rerun P-8/E0/E1/R3/F1 merely for reassurance;
- access ZiNi holdout `2,010,000 .. 2,010,099`;
- recount accepted real target counts or re-search the selected synthetic corpus;
- rerun historical accepted/closed R0-A or any unit merely for reassurance;
- execute Fresh R0-A without the separate authorization following the sequence above;
- delete, relabel or repair the retained `INCOMPLETE_AT_CREATION` marker;
- launch R0-B while its static blockers remain unresolved/unadjudicated or
  without separate explicit authorization;
- run Actual E2 before accepted R0 evidence + frozen Operating Envelope +
  separate authorization;
- execute conditional E3 without the frozen trigger;
- perform Gate P / production integration before their later qualification and
  authorization boundaries.

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
2. read this `docs/CURRENT_HANDOFF.md` as the durable current recovery authority;
   then read the [Stage-3 Extended README](stage3-extended/README.md) for the
   current roadmap/index. Continue with the
   [frozen E2 protocol](stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md)
   and the
   [frozen R0 Attribution Amendment v1](stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md),
   then the [exact V1.3.1 design](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md)
   and its [live acceptance receipt](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md);
3. authenticate the amendment exact identity before relying on its normative
   semantics: `58,052` bytes,
   SHA-256 `5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf`;
4. recover accepted E2 **I1–I8**, amendment conformance `cdba3513`, setup repair
   `e6593f7`, and committed/pushed harness
   `7e7f847816fedb77cef67b576eab665afabfbfbf`; retain the run/review source baseline
   `c0bc270bce1996797f9ecec80e79ea8998d3205d` separately from those technical anchors;
5. authenticate the exact accepted selection receipt in §7.1. Use its existing
   N=10000 counts and ordinal-5 synthetic selection without recount/re-search;
   keep its historical selection HEAD separate from the current harness HEAD;
6. recover the retained historical R0-A root and exact evidence identities in §7.1:
   **COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED**. Reuse the accepted
   integrity review; do not rerun the workload or repair its historical creation
   marker. The evidence is operational non-effectiveness evidence only;
7. recover both completed static proofs: K+D admission lower bounds exceed 12 h
   for every allowed N/c, and the 74,047,481,628 B minimum R0-B attributable archive
   exceeds 16 GiB even before overhead. No R0-B execution failure is claimed;
8. recover **V1.3.1 FINAL DESIGN ACCEPTED / FROZEN BY EXACT TRACKED BYTES** and
   **BLOCKER 0 / REQUIRED 0** at the design boundary. Engineering investigation
   and design are closed. Recover the accepted **1A–1W: 23/23 COMPLETE / ACCEPTED /
   COMMITTED / PUSHED** chain and **FRESH R0-A FINAL PREFLIGHT — PASS** at
   `48f6ebc97e6c4d3ed4a746a92a8d169783803bf9` from §2, including the USER-host
   1513-test result and the separate V2 codec / frozen Model C identities.
   This source is eligible for separate execution authorization only.
   **Fresh R0-A: NOT RUN / NOT YET EXECUTION-AUTHORIZED; no measurement exists.**
   Documentation CONTENT review is **PASS**; USER commit/push is authorized.
   Check live Git: if publication is pending, USER completes it first.
   **CURRENT NEXT after committed/pushed publication:** narrow post-documentation
   authority re-anchor → separate Fresh R0-A execution authorization → only then
   execution. A later documentation
   HEAD does not replace the qualified technical source. Preserve both historical
   proofs for the old source/representation;
9. R0-B remains NOT RUN / NOT AUTHORIZED, complete R0 adjudication is NOT DONE,
   and no final N/concurrency or E2 Operating Envelope is selected/frozen.
   Actual E2 remains NOT RUN / NOT AUTHORIZED; E2 PASS/FAIL/DEFER is NONE;
   effectiveness is NOT ESTABLISHED. E3 is conditional/not triggered;
10. Gate P, production integration and native K visual acceptance have not started;
    Program K and Stage-3 Extended closeout remain future work;
11. read the [Gate-R E1 closeout](stage3-extended/STAGE3_PROGRAM_K_E1_CLOSEOUT.md)
    only when exact E1 history/evidence is needed; do not repeat E0/E1 execution,
    E2-D0/protocol/amendment audits, official 100k, E/L, P-8/R3/F1 or closed
    Viewer/Timeline/Polish work merely for recovery;
12. never open the ZiNi final holdout `2,010,000 .. 2,010,099`.

Relevant source/evidence retained from the accepted engineering investigation:

- `experiments/program_k_e2_r0_harness.py`
- `experiments/program_k_e2_readiness.py`
- `experiments/program_k_e2_operational.py`
- `experiments/program_k_e2_qualification.py`
- `experiments/program_k_e2_identity.py`
- `experiments/program_k_e2_records.py`
- `experiments/program_k_e2_store.py`
- current relevant Program-K E2 tests
- frozen E2 protocol + frozen R0 Attribution Amendment v1
- accepted selection receipt + saved harness qualification summary linked above
- retained accepted R0-A observations/manifest/completion and the completed static
  feasibility findings in §7.1

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
