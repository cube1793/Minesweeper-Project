# Stage-3 Extended — Program K Research Specification

## 1. SPEC STATUS

**Program K — FROZEN / ACCEPTED research specification.**

Content freeze accepted by final ChatGPT adjudication; repository materialization: **2026-10-20 (Asia/Seoul)**.

PRIMARY remains **Program K**.

FALLBACK remains **Program L — Local Completion / Target Ordering restricted to existing V1-admissible certainty alternatives**.

This specification incorporates:

- Required corrections R-1 through R-6.
- Optional clarifications O-1, O-2, O-3 and O-6.
- All eight protocol-required obligations P-1 through P-8.
- Explicit deferral of O-4, O-5 and O-7.

Final content verdict: **BLOCKER 0 / REQUIRED 0 / PROTOCOL-REQUIRED 8 / OPTIONAL / DEFER 3 / CONTENT FREEZE PASS**.

This artifact materializes the accepted complete final pre-freeze candidate. The specification freeze itself **does not authorize implementation, experiments, production integration, official benchmark reruns or holdout access**. Program K has not been implemented. Gate R remains the next separate authorization gate; Gate P remains the later production-integration gate.

Execution authority is variant-specific:

| Variant | Physical-action authority | Role of K reasoning |
|---|---|---|
| **CONTROL** | Unchanged frozen V1 selection and execution contract | None |
| **K-CONTROL** | Exact frozen V1 selection and execution contract | Shadow semantics and diagnostics only |
| **K-P0** | K-C semantics and the specified K-P0 policy | Treatment decision authority |

No shadow-K result may veto, replace, reorder or require an additional action before a valid frozen V1 action.

## 2. AUTHORITY RECOVERY

Read-only live Git inspection immediately before this documentation materialization recorded:

| Item | Verified pre-edit value |
|---|---|
| Repository | `C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project` |
| Branch | `main` |
| HEAD | `23177852dba59d1e1ce31c2cc19a9dc8aa980f68` |
| Commit subject | `docs: close fixed-exemplar interpretation` |
| Locally available `origin/main` | Same commit |
| Ahead / behind | `0 / 0` |
| Worktree / index | Clean before authorized documentation edits |

This is the **2026-10-20 pre-edit baseline**, not a claim that the documentation worktree remains clean or a prediction of a later commit. No fetch was performed. The accepted semantic source is the complete corrected final pre-freeze candidate in the preceding design work; this materialization changes only status/provenance wording and repository-relative authority links.

Authority order remains:

1. Current source.
2. Current tests.
3. Preserved accepted executable evidence.
4. Frozen specifications, final adjudications and closeouts.
5. Navigation and handoff documentation.
6. Prior AI interpretation.

The recovered documentary authorities include:

- [CURRENT_HANDOFF.md](../CURRENT_HANDOFF.md)
- [Fixed-exemplar interpretation closeout](STAGE3_FIXED_EXEMPLAR_INTERPRETATION_CLOSEOUT.md)
- [Stage-3 V1 final adjudication](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Stage-3 algorithm specification](../../STAGE3_ALGORITHM_SPEC_v1.md)
- [Telemetry and benchmark specification](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Extension backlog](../../STAGE3_EXTENSION_BACKLOG.md)
- [Architecture](../../ARCHITECTURE.md)

Relevant implementation authorities include the recovered inference, decision, exact-probability, planner, runner, physical-cost and telemetry source; Engine terminal behavior; and relevant complete tests.

The following boundaries remain authoritative:

- V1 has no separate persistent logical-known-mine state.
- Physical flags participate in V1 inference and probability accounting.
- V1 can already select some direct safe OPENs before FLAGs.
- Frozen planning uses first-reveal templates, exact routing, dominance and E-FIRST.
- Frozen §22 FLAG fallback belongs to V1.
- WIN may automatically flag remaining mines.
- LOSS observations may expose `EXPLODED`, `MINE` and `FALSE_FLAG` terminal glyphs.

The fixed-exemplar interpretation milestone remains closed. B/B2 provide qualitative motivation; D provides a preservation constraint. Those exemplars do not establish population frequency or numerical benefit.

The final adjudicated corrections are incorporated in this frozen research contract. No new executable evidence is claimed by the documentation freeze.

## 3. PROGRAM NAME AND RESEARCH QUESTION

**PROGRAM K: LOGICAL KNOWN-MINE CAPABILITY + SELECTIVE PHYSICAL MATERIALIZATION**

“Selective” refers only to the bounded K-P0 policy below. Physical FLAG remains legitimate and sometimes necessary.

The exact research question is:

> Can a bounded, public-information-derived logical-known-mine capability, exercised through the minimal K-P0 materialization policy, remove unnecessary physical-marking dependencies and reduce complete-run frozen Model C time while preserving sound certainty, exact public-information probability semantics, exact minimum-risk selection with the existing `(y,x)` tie policy when an uncertain guess is genuinely required, certainty-before-uncertainty under K logical accounting, deterministic execution, useful physical FLAG/CHORD behavior, and outcome integrity sufficient for a defensible Stage-3 comparison?

**Certainty-before-uncertainty under K accounting** means:

- No uncertain guess while unaccounted logical certainty or current safe certainty remains actionable.
- A mine already accounted for in `M` is resolved certainty even while physically HIDDEN.

The contract intentionally does not preserve mandatory physical FLAG-before-guess ordering or materialization of every certain mine before probability work.

Nevertheless, corresponding exhausted-certainty guess checkpoints are **expected to be informationally identical** between CONTROL and K-P0. This is a mandatory research hypothesis to test, not an established production theorem.

## 4. SCOPE / NON-GOALS

The research includes:

- Retained identities of publicly proven mines.
- Local and exact-global acquisition of those identities.
- Sound logical/physical accounting.
- Materialized-equivalence validation.
- Direct safe OPEN admissibility enabled by logical mine substitution.
- Minimal physical materialization under frozen first-reveal planning.
- Controlled evidence and paired evaluation against frozen V1.

K retains **only proven mine identities across physical actions**. Their origins may be:

- Direct local mine certainty.
- Exact-global probability-one certainty.

K does not retain across physical actions:

- Safe-cell identities.
- Probability-zero safe pools.
- Probability values.
- World counts.
- Component results.
- Arbitrary constraint relations.
- General exact-analysis state.
- Other retained global facts.

Experimental archives may preserve such information for independent evidence review. Archived analysis is not additional live decision state.

Program K intentionally incorporates the narrow **“previously proven 100% mine” portion of backlog P2 Retained Certainty**. It does not adopt retained 0% safe cells or broader P2 content.

The initial executable scope remains canonical complete games under the frozen board-generation and initial-input contract. A new game begins with empty `M`. Frozen initialization, including the initial cursor and opening input, remains unchanged.

Arbitrary imported partial games, external human flags and unproved supplied knowledge are outside the initial experiment. Synthetic cases must declare independently verifiable public premises.

Other non-goals are:

- Subset inference, safe substitution or arbitrary stronger inference.
- Hypothetical clues, future outcomes or future reveal simulation.
- Longer planning horizons or richer reveal valuation.
- Locality or target-order changes.
- Sophisticated flag timing or speculative future CHORD value.
- Prospective robustness optimization.
- Nearest Minimum-Risk Guess.
- Probability approximation or changed probability weights.
- New Model C parameters or a combined CPU/physical-time objective.
- Production telemetry, Replay or Viewer redesign.
- Reopening accepted gameplay interpretation, regenerating accepted reports, official benchmark execution or ZiNi holdout access.

Requiring broader retained facts is a hard-stop or specification-level scope-expansion condition.

## 5. CAPABILITY VS POLICY SEPARATION

| Layer | Responsibility | Boundary |
|---|---|---|
| **K-C — Logical Known-Mine Capability** | Represent publicly proven mines without requiring physical flags; preserve sound accounting, inference and exact probability | Does not decide whether physical materialization is worthwhile |
| **K-P0 — Minimal Materialization Policy** | Expose immediate physical-time consequences using frozen first-reveal planning | No speculative future value or broader flag-timing policy |
| **Downstream F** | Potential later research into sophisticated selective flagging and timing | **Remains downstream and EXCLUDED from this experiment** |

K-C can make a direct safe OPEN admissible. K-P0 decides among admissible immediate plans using frozen speed-based mechanics.

K-C’s persistent inference content is mine identity only, including the permitted exact-global probability-one portion of P2. It does not carry forward safe pools or exact-analysis results.

Runtime semantics require `M` and the minimal information necessary for valid ownership, use and consistency checking. Rich certificates, antecedent chains and replayable verification records belong to the research evidence layer unless a minimal subset is necessary for runtime correctness.

This distinction does not weaken independent verification or prescribe implementation classes.

CONTROL versus K-P0 measures the **K-C + K-P0 package**. K-CONTROL and structured evidence support semantic checking and mechanism attribution. They do not establish an additive numerical split between “capability savings” and “policy savings.”

## 6. LOGICAL-KNOWN-MINE STATE SEMANTICS

`M` contains mine identities established from permitted public evidence during the current game.

A coordinate may enter `M` only through:

1. **Direct local certainty:** a valid normalized clue has a nonempty unresolved neighborhood whose size equals its residual mine count.
2. **Exact global certainty:** a legitimately reached exact computation has positive total world count and assigns the coordinate probability exactly one.

Rounded probabilities, confidence thresholds and approximate results are insufficient.

Acquisition must not use the proposed fact as its own premise. Valid earlier logical facts and properly supported physical-flag premises may support later facts.

| Event | Required semantics |
|---|---|
| New game | Initialize empty `M`; no cross-game facts |
| Valid acquisition during PLAYING | Add a newly proven mine identity |
| Physical input followed by PLAYING | Validate retained `M` against the fresh public PLAYING state |
| K-P0 materialization of a logical mine | Preserve the identity in `M`; materialization does not consume it |
| Physical/logical overlap | Count the coordinate once |
| Additional proof for an existing identity | May supplement research evidence; does not create another mine |
| Unexpected safe revelation of a member of `M` during PLAYING | Integrity failure; no demotion or repair |
| Unexpected unflagging, board change or observation regression | Integrity failure |
| WON | Stop K reasoning; archive the last legitimate `M` unchanged |
| LOST | Stop K reasoning; archive the last legitimate `M` unchanged |

Within a valid PLAYING session, `M` is monotonic.

**Validate retained `M`** means checking consistency. Validation does not edit, demote, reconcile or repair existing facts. New acquisition is a separate operation.

Terminal glyphs cannot acquire, correct, demote, extend or validate `M`. The separate evaluator-only falsification permission in Section 14 does not alter this lifecycle.

K-CONTROL shadow acquisition follows the declared K rules. A V1-selected FLAG is not inserted into shadow `M` merely to force agreement. Its resulting physical flag may subsequently serve as a separately supported physical premise.

Conceptually, the K-P0 decision function depends on:

- Current public PLAYING observation.
- Public total mine count and dimensions as required.
- Cursor.
- Authenticated frozen timing table and policy identity.
- Retained logical mine set `M`.

`M` is itself a deterministic function of the permitted public history. Rich research archives are not additional decision inputs.

## 7. MATERIALIZED-EQUIVALENCE CONTRACT

For a valid public PLAYING state with physical flags `P` and logical mines `M`, construct an informational reference state that:

- Preserves revealed clues.
- Preserves actual physical flags.
- Treats physically HIDDEN members of `M` as correctly flagged for inference/accounting.
- Preserves the public total mine count and other relevant public premises.

This reference is an oracle input, not an Engine observation. It must never be used as actual physical state for CHORD execution.

Two separate obligations apply.

**Acquisition soundness**

Every acquired identity must be a mine in every world consistent with its admissible public premises. That world set must be nonempty.

Projecting an unproved coordinate as flagged and obtaining consistent calculations does not prove acquisition soundness.

**Representation equivalence**

Given sound logical facts and valid physical-flag premises, logical and corresponding informationally materialized states must agree on:

- Local unresolved neighborhoods and residual mine counts.
- Global remaining mine budget.
- Direct safe/mine deductions on corresponding unresolved cells.
- Consistent-world assignments and weights.
- Exact world counts and unresolved-cell mine counts.
- Exact probabilities and fixed-mine certainty.
- Minimum-risk value and equal-risk candidate set.
- Certainty classification.
- Guess/no-guess boundary under the declared K schedule.

Comparisons must be **phase matched**, including the same reached inference layers and same-decision evidence.

A fresh frozen V1 analysis after every acquisition is not the sole oracle: a different scheduling path can omit previously reached same-decision global safe evidence.

No physical equivalence is required for:

- Actual glyphs.
- Actual FLAG counts or CHORD eligibility.
- Cursor position.
- Physical cost already paid.
- Action history.
- Available physical plans or selected physical sequence.

Independent acquisition verification and independent representation checking are both mandatory. Protocol items P-1 and P-2 fix their precise oracle points, snapshots and independence requirements.

Hidden answer truth is not an input to either obligation.

## 8. MINE ACCOUNTING

For a PLAYING state, define:

- `P`: actual physically flagged cells.
- `H`: actual physically HIDDEN cells.
- `M`: logical known mines.
- `J = P ∪ M`: distinct fixed-mine identities.
- `U = H \ M`: hidden cells not fixed as mines.
- `S ⊆ U`: current-decision certain safe cells.

“Unresolved” means not fixed as a mine. It does not necessarily mean uncertain.

Current safe cells remain in `U` and in the relevant clue neighborhoods. They are not substituted out to derive stronger mine deductions.

Required relationships are:

- `P ∩ H = ∅`.
- `M ⊆ P ∪ H`.
- `S ∩ M = ∅`.
- Members of `J` are excluded from unresolved probability variables and selectable guesses.
- Each fixed mine contributes once globally and once to each adjacent clue equation.

For clue `c`:

\[
U_c=Adj(c)\cap U
\]

\[
r_c=N_c-|Adj(c)\cap J|
\]

For public total mine count `n`:

\[
b=n-|J|
\]

Required bounds include:

\[
0\le r_c\le |U_c|,\qquad 0\le b\le |U|
\]

Overlap is counted by union:

\[
|J|=|P|+|M|-|P\cap M|
\]

One mine touching multiple clues contributes to each applicable clue equation. It is still counted only once in the global budget.

Variant-specific requirements are:

- **K-P0:** every explicit physical FLAG during PLAYING requires prior valid membership in `M`. Under canonical initialization, `P ⊆ M` holds during PLAYING.
- **CONTROL:** no K-state requirement applies.
- **K-CONTROL:** `P ⊆ M` is not required. Valid V1 physical flags may be absent from shadow `M`; shadow accounting still uses `P ∪ M`.

These PLAYING-state relationships are not checked against terminal automatic flags.

## 9. LOCAL INFERENCE CONTRACT

Logical mines contribute as fixed mines in clue equations while remaining physically HIDDEN unless materialized.

Only the direct rules are permitted:

- `r_c = 0`: unresolved neighbors are safe.
- `r_c = |U_c| > 0`: unresolved neighbors are mines.

The local process is bounded:

1. Confirm PLAYING status and obtain the current public observation.
2. Validate retained `M`, domains and accounting.
3. Perform one complete direct-rule pass over the current normalized state.
4. Collect and acquire all newly proven local mines from that pass.
5. Normalize constraints using those acquired identities.
6. Perform a second normalized check, which may unlock additional safe cells.

**The second normalized pass must not acquire a new mine.**

Any proposed new mine on that pass is an invariant failure indicating inconsistent accounting, an incomplete first pass or unauthorized stronger inference.

Safe cells found during the decision remain in `U` and `U_c`. They are not removed as fixed-safe substitutions.

The boundedness follows from the direct-rule algebra. Substituting `k` already proven mines changes `(r,h)` to `(r−k,h−k)`. It can expose residual zero, but cannot newly create `r=h` where that equality was previously false.

There is no repeated mine-closure loop beyond this bounded process.

If the resulting local safe pool is nonempty, select an admissible reveal plan without entering exact probability.

The locally safe cells unlocked by substituting proven mines correspond to the remaining cells that frozen V1 could justify after virtual/physical whole-clue mine setup, restricted to setup mines already proven in `M`.

K changes the execution/admissibility boundary by exposing that information without immediate physical materialization. It does not add subset inference, safe substitution, hypothetical clues or arbitrary constraint propagation.

Exact-global probability-one acquisition remains a separate permitted layer. It is not prohibited by the second-pass local restriction.

## 10. EXACT PROBABILITY CONTRACT

Exact probability operates on `U`, using remaining mine budget:

\[
b=n-|P\cup M|
\]

Required semantics are:

- Fixed mines are removed from the variable domain.
- Each fixed mine is subtracted once from applicable clues and once globally.
- Frontier components and floating cells are constructed from unresolved cells.
- Frozen complete-board weighting and combinatorial semantics remain unchanged.
- Integer counts and exact rational comparisons remain authoritative.
- No approximation or rounding changes certainty or selection.

Logical mines have conceptual probability one but are not selectable probability candidates or guesses.

Exact analysis is reached only when the bounded local process produces no current safe continuation.

Let:

- `G₁` contain all exact-probability-one cells.
- `G₀` contain all exact-probability-zero cells.

Then:

1. Require positive consistent-world count.
2. Acquire all `G₁` into `M`.
3. Define `U′ = U \ G₁`.
4. Preserve every `G₀` cell as a current-decision safe candidate.
5. Restrict the existing exact counts to `U′`; acquiring facts true in every counted world removes no worlds or weights.
6. Do not perform another enumeration merely because `G₁` was acquired.

A normalized local consistency check may supply supplementary certificates. It cannot shrink `G₀`, discover a safe cell outside `G₀`, or discover another mine in `U′`.

The decision evidence must retain the fact that exact analysis was reached. Supplementary local certificates do not erase its exact-global origin.

For every validated PLAYING state submitted to the K-P0 decision process, exactly one action-selection branch must apply:

| Branch | Condition | Required result |
|---|---|---|
| **1** | Local safe pool is nonempty | Select an admissible reveal plan |
| **2** | Otherwise, exact analysis yields nonempty `G₀` | Select an admissible reveal plan from the current exact-safe pool |
| **3** | Otherwise, `U′` is nonempty | Select exact minimum risk over `U′`, breaking equal risks by `(y,x)` |

Integrity failures include:

- `U = ∅` while Engine status is PLAYING.
- `U′ = ∅` after `G₁` acquisition while Engine status is PLAYING.
- Zero consistent worlds.
- Invalid accounting bounds.
- Conflicting classifications.
- Failure to construct an admissible reveal plan when current safe certainty exists.

If `U′` is empty, every unrevealed cell is already a proven mine. A correct Engine should already be WON once all safe cells are revealed.

On an integrity failure, stop the K-P0 treatment run and record the failure. Do not synthesize WIN, add completion flags, use standalone FLAG fallback, guess or switch policy.

After each physical input, safe pools, probability values, world counts and component results expire as decision inputs. Only proven mine identities persist.

## 11. PHYSICAL FLAG / CHORD CONTRACT

Logical knowledge and physical inputs remain distinct.

| Item | Reasoning role | Physical role |
|---|---|---|
| Logical known mine | Supports constraints and exact accounting | Does not count as a physical FLAG |
| Physical FLAG | Supplies an actual flagged state under valid variant-specific evidence | Costs Model C time and may enable actual CHORD |
| Actual CHORD | Requires public certainty of safe opening | Uses actual physical flags only |

For **K-P0**, every explicit FLAG requires:

- A physically HIDDEN target.
- Prior valid logical proof and membership in `M`.
- Selection as the first input of a surviving `SETUP_CHORD` plan.

For **CONTROL and K-CONTROL**, FLAG validity comes from frozen V1’s current-decision evidence and execution contract. Shadow membership is not action authority.

“Retained V1 decision evidence” means evidence supporting that selected input at its observation. It does not introduce new persistent V1 knowledge.

A K-P0 CHORD requires:

- An actual revealed positive clue.
- Actual adjacent physical FLAG count equal to the clue.
- At least one physically HIDDEN cell to open.
- Public certainty that every opened cell is safe.

Required supported cases include:

- Direct OPEN without materialization.
- Useful FLAG→CHORD progression.
- Later materialization of an earlier logical mine when a new immediate plan selects it.
- A logical mine never explicitly materialized.
- Terminal automatic WIN flags, with no physical input cost or logical acquisition.
- Terminal LOSS disclosure, with no solver or public-proof use.

Pattern D preservation requires both legal productive behavior and Model C regression evidence. Counts alone do not establish preservation.

## 12. MINIMAL K-P0 MATERIALIZATION POLICY

**Selected policy:** retain the frozen first-reveal horizon, exact routing, dominance, E-FIRST and deterministic ties; expand admissibility through K-C; provide no standalone FLAG fallback after certainty is logically accounted for.

For each PLAYING decision:

**Direct safe candidates**

Every current certain-safe physically HIDDEN cell permits `DIRECT_SAFE_OPEN(v)` with guaranteed reveal count `R = 1`.

Do not credit predicted flood expansion.

**Whole-clue setup candidates**

For an eligible clue, define:

- `B`: adjacent physically HIDDEN logical mines requiring materialization.
- `V`: remaining physically HIDDEN neighbors after excluding `B`.

Require:

- `|B| = clue value − actual adjacent physical FLAG count`.
- `V` is nonempty.
- Every member of `V` is currently certain safe.

Generate eligible exact-route `FLAG(B) → CHORD(clue)` candidates.

Frozen `FLAG(B) → OPEN(v)` templates may remain generated, but their nonempty setup forms are dominated as specified below.

An empty `B` permits direct CHORD when actual physical conditions hold. Empty-setup OPEN forms are equivalent to direct OPEN and may be deduplicated.

**SETUP_OPEN dominance**

For any `v ∈ V`:

- `DIRECT_SAFE_OPEN(v)` exists.
- It has the same guaranteed reveal count `R = 1` as `FLAG(B) → OPEN(v)`.
- A nonempty setup includes additional positive-cost physical inputs.

Subject to P-8’s authenticated full-table detour invariant, the nonempty setup has strictly greater latency than direct OPEN to the same target. It is therefore strictly dominated in `(L,R)` and must be pruned before E-FIRST selection.

Consequently:

- Nonempty SETUP_OPEN may be generated for candidate-vocabulary continuity.
- It must not survive dominance pruning or be selected.
- Generating versus omitting those dominated templates must not change behavior.
- A surviving or selected nonempty SETUP_OPEN is an invariant failure.
- K-P0’s explicit FLAGs occur only as first inputs of selected SETUP_CHORD plans.

This CHORD-directed flag use follows from frozen dominance/E-FIRST mechanics. It does not adopt downstream Program F.

The timing property must not be presumed from geometric intuition or additional input cost alone. **P-8 requires exhaustive verification over the authenticated full frozen timing table before relying on this dominance claim.**

If P-8 fails, do not conceal the failure by deleting templates, changing ranking or modifying the timing model. The specification’s premise has failed and requires a separate decision.

**Selection and execution**

- Deduplicate equivalent physical sequences.
- Preserve frozen strict `(L,R)` dominance.
- Preserve exact E-FIRST comparison of `L/R`.
- Preserve frozen latency and deterministic coordinate, action-rank and route tie rules.
- Include all proposed physical movements and inputs in plan latency.
- Use no action-count objective, unrelated FLAG detour, partial setup policy or speculative future reward.
- Execute exactly one physical input.
- Discard the suffix and replan after the status-first boundary.

The existing seven-FLAG setup maximum follows from eight neighbors and at least one remaining reveal cell.

A selected setup FLAG has CHORD-enabling intent. It does not guarantee that the original suffix will later execute; fresh replanning remains mandatory.

K-P0 has no standalone materialization fallback. CONTROL and K-CONTROL retain frozen V1’s §22 fallback.

Decision totality and integrity handling follow Section 10.

## 13. FRESH-REPLAN / PERSISTENT-FACT BOUNDARY

K reasoning may begin only while Engine status is PLAYING.

After every physical input:

1. Obtain the Engine status/effect result required by the runner.
2. **If PLAYING:**
   - Obtain/use the fresh public PLAYING observation.
   - Validate retained `M` without editing or repairing it.
   - Discard prior safe pools, probability availability and physical suffixes.
   - Recompute the next decision.
3. **If WON or LOST:**
   - Record the outcome and permitted executed-action/public-effect evidence.
   - Stop all K and shadow-K reasoning immediately.
   - Archive the last legitimate `M` and proof history unchanged.
   - Do not perform local inference, probability, materialized-equivalence or public-proof validation using the terminal observation.
   - Do not invoke another K planner.

Persistence is limited to valid mine identities on a static board. It does not authorize retained-safe reuse or execution of an unverified suffix.

The terminal guard applies equally to K-P0 and K-CONTROL shadow processing. Actual Engine termination ends the run; it is not a shadow-K veto.

A separate evaluator may later perform the one-way falsification audit defined in Section 14. That is not continued solver reasoning or terminal validation of `M`.

## 14. PUBLIC-INFORMATION SAFETY

K and shadow K may use only permitted current public information, valid retained mine identities and legitimate same-decision inference.

The following must never enter solver/shadow state, selection, acquisition, public-proof validation or materialized-equivalence inputs:

- Hidden answer layout.
- Future clues or outcomes.
- Answer-derived ZiNi or other answer-derived efficiency information.
- Viewer answer overlays.
- Reconstructed future states.
- Fixed-board answer knowledge.
- Terminal revealed truth.
- Evaluator-only answer knowledge.

Public proof must be independently verifiable from premises available at or before acquisition. Antecedents must be ordered and non-circular.

Rich proof records belong to the evidence layer unless a minimal subset is required for runtime correctness. A digest alone is insufficient if the underlying public premises cannot otherwise be reconstructed.

**Permitted evaluator-only falsification**

A strictly separated evaluator may perform a post-hoc comparison of:

- Archived `M`.
- Targets classified as certainty OPENs.
- Cells actually opened by CHORD.

The comparison may use the hidden board or terminal record.

Its interpretation is one-way:

- **Mismatch:** may FAIL G1.
- **Match:** does not prove, confirm, upgrade, strengthen or repair `M` or its provenance.

This audit does not turn uncertain guesses into certainty assertions.

Its result must never feed into:

- Solver state.
- Shadow state.
- Action selection.
- Logical proof.
- Materialized-equivalence inputs.
- Later run configuration, policy tuning or case selection.

The evaluator may report a failure and thereby stop or withhold research progression. It may not supply answer knowledge to repair the algorithm’s facts or influence later run decisions.

Evaluator records must remain segregated from solver-facing public prefixes and proof certificates. Public acquisition soundness still requires independent verification from public premises.

A correctly isolated falsification audit is not itself a G3 violation. Hidden truth reaching K reasoning or **public-proof validation** is.

## 15. TELEMETRY / RESEARCH EVIDENCE CONTRACT

Use experimental evidence without redesigning production telemetry, Replay or visualization schemas.

| Evidence group | Minimum content |
|---|---|
| Run identity | Variant, source/policy identity, corpus and generator identity, authenticated Model C identity, initial conditions |
| Decision identity | Decision index, next input index, PLAYING observation or lossless reconstruction, whether exact analysis was reached |
| Logical facts | Acquisitions, retained references, local/exact origin, public premises, ordered antecedents, `M` snapshots |
| Accounting | Physical flags, overlap, unresolved domain, residual constraints and global budget |
| Candidates | Eligible candidates or sufficient reconstruction data, setup sets, targets, guaranteed reveals, latency, pruning and ranking |
| Execution | Action, target, cursor transition, physical cost, status/effect and execution authority |
| Probability | Exact domain/count evidence, selected risk, minimum-risk comparison and tie result |
| Validation | Public-proof and equivalence results, control comparisons and classified discrepancies |
| Compute | Required decision work distinguished from shadow, probe and evidence overhead |
| Termination | Outcome and unchanged preterminal logical-state reference |
| Evaluator falsification | Segregated comparison scope and counterexamples, with no proof-upgrade or feedback semantics |

Minimum physical-selection categories remain:

- `POLICY_INITIAL_OPEN`
- `DIRECT_SAFE_OPEN`
- `DIRECT_CHORD`
- `SETUP_CHORD`
- `V1_FLAG_FALLBACK`
- `EXACT_MINIMUM_RISK_GUESS`

`SETUP_OPEN` may identify generated/pruned candidates and applicable frozen V1 behavior. A **nonempty** SETUP_OPEN is not a valid surviving or selected K-P0 plan.

`V1_FLAG_FALLBACK` is valid only for CONTROL and K-CONTROL.

Keep separate:

- Logical acquisition reason.
- Selected-plan reason.
- Actual first-input reason.
- Intended setup outcome.
- Realized later execution.

For K-CONTROL, record V1 action authority and supporting current-decision evidence separately from shadow evidence.

A valid V1 FLAG absent from shadow `M` may be a benign scheduling discrepancy, such as `V1_VALID_FLAG_NOT_IN_SHADOW_M`. It is not an unproved V1 action.

**SHADOW-SOUNDNESS INVARIANT**

At a valid frozen V1 `PROBABILITY_GUESS` decision:

- V1 has exhausted exact-zero and exact-one selectable certainty.
- Exact-certain mines have already been physically materialized.
- Sound shadow fixed-mine knowledge cannot create extra genuine safe certainty outside the corresponding exact-zero set.

Therefore, a shadow claim of current safe certainty at that state must be classified as:

`SHADOW_SOUNDNESS_VIOLATION`

This is a zero-tolerance semantic/equivalence failure for shadow evidence. It is not a benign disagreement.

The violation still must not veto, replace, reorder or otherwise alter the valid V1 action. Stale evidence presented as current is also a defect.

Matched-state diagnostic probes may distinguish:

- `ALREADY_V1_DIRECT_ADMISSIBLE`
- `NEWLY_K_DIRECT_ADMISSIBLE`
- `NOT_EVALUATED`

“Newly K direct-admissible” does not mean V1 lacked a setup alternative.

Probes must not influence selection. Their timing is separate.

Logical events and automatic terminal flags are not physical inputs. No historical V1 provenance may be fabricated.

## 16. EXPERIMENTAL VARIANTS

| Variant | Required behavior | Purpose |
|---|---|---|
| **CONTROL** | Frozen V1 physical decisions and validation | Baseline |
| **K-CONTROL** | Exact frozen V1 physical decisions with shadow K-C | Semantic and instrumentation negative control |
| **K-P0** | K-C plus the single specified K-P0 policy | Treatment |

K-CONTROL is required.

Its forced action is validated from V1’s own current-decision evidence and execution contract. Shadow K has no physical-action authority.

A valid V1 FLAG may be absent from shadow `M` because the reasoning schedules differ before certainty exhaustion. This remains a permissible diagnostic discrepancy.

By contrast, shadow current safe certainty at a valid V1 probability-guess state is a `SHADOW_SOUNDNESS_VIOLATION`. It fails shadow semantic qualification but must leave V1 execution unchanged.

CONTROL/K-CONTROL identity requires matching:

- Ordered action types and targets.
- Actual public effects.
- Cursor sequence.
- Physical Model C costs.
- Guess sequence.
- Terminal outcome.

Compute time is excluded from identity because shadow work adds overhead.

P-5 must prospectively define continuation, containment and evidence invalidity following a shadow failure. It cannot grant shadow K action authority.

A materialize-all K variant is not an acceptable replacement for K-CONTROL because it can change V1 ordering and cursor movement.

K-CONTROL does not cover every K-P0 state. Independent semantic tests must also cover treatment-only states.

CONTROL versus K-P0 measures the complete treatment package. Same-state probes and event evidence support explanation without creating additional policy variants.

## 17. CORRECTNESS TEST OBLIGATIONS

These are future requirements. No tests are created or executed by this specification.

| Family | Required invariant |
|---|---|
| **A. Synthetic local witnesses** | Permitted direct rules only; logical mine substitution unlocks safe OPEN |
| **B. Physical/logical overlap** | One-count accounting; treatment proof requirements; valid K-CONTROL `P \ M` |
| **C. Logical mine → safe OPEN** | Safe opening becomes admissible while the mine remains physically HIDDEN |
| **D. Logical mine → FLAG → CHORD** | Actual flags enable actual CHORD; logical flags do not |
| **E. Multiple mines around one clue** | Exact residual and domain accounting |
| **F. One mine touching multiple clues** | Correct per-clue contribution without duplicate global subtraction |
| **G. Global budget** | Correct overlap, zero-budget and empty-domain handling |
| **H. Exact probability** | Exact components, floating-cell weights and global counts remain equivalent |
| **I. Certainty before uncertainty** | No treatment guess while mine certainty is unaccounted or current safe certainty is actionable |
| **J. Genuine guess boundary** | Accounted unmaterialized mines do not block exact minimum-risk `(y,x)` selection |
| **K. Terminal lifecycle** | Status-first cutoff; unchanged archived facts; no terminal truth in solver/public-proof processing |
| **L. Inconsistency and totality** | Detect invalid bounds, conflicts, zero worlds, `U=∅/PLAYING`, and `U′=∅/PLAYING`; fail closed |
| **M. Determinism** | Identical semantic inputs produce identical facts and actions, excluding timing noise |
| **N. Information isolation** | Hidden/evaluator knowledge cannot affect reasoning, proof, selection or later configuration |
| **O. Materialized differential oracle** | Independent phase-matched representation and acquisition checks |
| **P. Productive physical progression** | Useful FLAG/CHORD remains available and selectable |
| **Q. Frozen planning mechanics** | Exact routing, dominance, E-FIRST, ties and fresh replanning remain frozen |
| **R. Control/shadow integrity** | Valid V1 execution remains unchanged despite shadow discrepancies or injected shadow faults |

Additional explicit obligations are:

- A second normalized local pass must not acquire a new mine.
- Current safe cells remain in `U/U_c`; safe substitution is rejected.
- Exact-global `G₁` acquisition is distinguished from prohibited second-pass local acquisition.
- `U′=∅` while PLAYING triggers failure, with no completion flag, synthetic WIN, guess or policy switch.
- Every K-P0 explicit FLAG has prior valid `M` proof and belongs to a selected SETUP_CHORD plan.
- Generated-versus-omitted nonempty SETUP_OPEN templates produce identical behavior after P-8.
- A surviving nonempty SETUP_OPEN is detected as an invariant failure.
- P-8 is checked exhaustively against the authenticated full timing table.

Terminal tests must separately prove:

- WIN automatic flags cannot create logical facts.
- LOSS disclosures cannot create, correct or validate logical facts.
- No post-terminal K/shadow inference or planning call.
- Evaluator-terminal truth cannot enter public-proof validation.
- Archival does not mutate `M`.

Evaluator-falsification tests must establish both one-way directions:

- A counterexample can fail G1.
- A match cannot upgrade proof validity or repair state.
- Neither result feeds solver state or later run configuration.

Family R must include:

- A valid V1 FLAG absent from shadow `M`.
- Valid V1 §22 fallback despite K-P0’s prohibition.
- A deliberately invalid or fault-injected shadow claiming safe certainty at a valid V1 probability-guess state.
- Detection of `SHADOW_SOUNDNESS_VIOLATION`.
- Unchanged V1 action despite that violation.

The safe-at-V1-guess test must not imply that a sound natural witness exists.

## 18. RESEARCH-AUTHORIZATION VS PRODUCTION-AUTHORIZATION

**GATE R — RESEARCH IMPLEMENTATION AUTHORIZATION**

After specification freeze and the required independent review, explicit authorization may permit a bounded experimental implementation and harness.

The applicable protocol must define the relevant stage’s evidence, cases, identities, stopping rules and acceptance criteria before its execution/results.

Gate R permits collecting the evidence needed to judge K. It does not require complete empirical benefit evidence before a prototype can exist.

It does not authorize production integration or alteration of frozen V1.

**GATE P — PRODUCTION INTEGRATION AUTHORIZATION**

Only after research passes its required semantic, attribution, outcome, speed, regression, compute and scope gates may a separate decision authorize production design and integration.

Production compatibility, evidence ownership, version identities and qualification remain separate work.

This specification grants neither authorization.

## 19. EXPERIMENTAL EVALUATION LADDER

| Stage | Purpose and evidence | STOP / GO boundary | Not yet claimed |
|---|---|---|---|
| **E0 — Semantics and synthetic validation** | Acquisition soundness, accounting, phase-matched equivalence, terminal isolation, bounded inference, totality, timing dominance | Required semantic and P-8 checks must pass; unresolved violations stop progression | Representative speed or outcome benefit |
| **E1 — Small controlled complete cases** | End-to-end execution, control identity, checkpoint comparison, productive CHORD and evidence integrity | Proceed only with attributable behavior and resolved correctness/control obligations | Population-level effectiveness |
| **E2 — Bounded representative paired corpus** | WW physical time, outcome/checkpoint equality, opportunity frequency, regression and compute burden | Registered PASS/FAIL/DEFER criteria | Universal benefit or production readiness |
| **E3 — Larger or independent confirmation** | Resolve justified uncertainty or confirm supported E2 findings | Proceed only under predeclared justification and stopping rules | Automatic official qualification |
| **E4 — Production/final qualification** | Separately authorized integration and qualification | Requires research PASS and Gate P authorization | Replacement of frozen history |

No arbitrary corpus sizes or numerical thresholds are assigned here.

Before relevant results, protocols must fix corpus rules, sample-size rationale, endpoints, practical benefit, uncertainty, regression, resource criteria and stopping rules.

P-7 must map G1–G10 to stages and identify which stage issues research PASS/FAIL/DEFER. The ladder alone does not declare every completed stage a research PASS.

The fixed exemplars may serve only as separately authorized qualitative references/regressions. They are not the sole effectiveness corpus.

The ZiNi final holdout is excluded. No ladder stage automatically authorizes the official 100k.

## 20. OUTCOME / SPEED EVALUATION CONTRACT

Pair identical board/session identities under CONTROL and K-P0.

**Expected guess-checkpoint equality**

Under the declared semantics:

- CONTROL and K-P0 reveal only publicly certain-safe cells through certainty actions before an uncertain guess.
- CONTROL physically materializes exact-certain mines.
- K-P0 accounts for those exact-certain mines in `M`.
- Both reach an uncertain guess only after certainty is exhausted.
- Both use exact complete-board probability.
- Both select exact minimum risk with the existing `(y,x)` tie.

Therefore, corresponding uncertain-guess checkpoints are expected to be informationally identical and to select the same guess.

Physical glyphs for known mines, cursor paths and prior action counts may differ. Those differences do not establish different information at an exhausted-certainty checkpoint.

P-3 must define prospective checkpoint correspondence and comparison, including sufficient normalized information, exact-risk and target evidence. Missing comparisons must not be treated as equality.

This expectation must be tested. It is not promoted to an untested production theorem.

| Outcome class | Meaning | Evaluation |
|---|---|---|
| **WW** | Both win | Primary complete-run modeled time-to-win comparison |
| **WL** | CONTROL wins, K-P0 loses | Outcome mismatch; not a speed result |
| **LW** | CONTROL loses, K-P0 wins | Outcome mismatch; not interchangeable with WW speed |
| **LL** | Both lose | Termination cost is diagnostic only |

Never pool cost-through-termination across outcome classes as though faster losses were improvements.

For WW pair `i`:

\[
\Delta_i=C_{K,i}-C_{V1,i}
\]

Negative values favor K-P0.

Report preregistered paired distributions and aggregate totals. A ratio of total WW time may be reported consistently as:

\[
\frac{\sum C_K}{\sum C_{V1}}
\]

Required reporting includes:

- WW/WL/LW/LL counts.
- Win counts/rates.
- Registered guess-checkpoint comparisons.
- Exact risks, ties and selected targets where relevant.
- WW per-game deltas and aggregate/distributional summaries.
- Faster/slower/tied WW counts.
- Failures, resource aborts, incomplete runs and missing evidence.
- Compute diagnostics separately.

Do not discard failures silently or recode harness errors as ordinary losses.

**Initial outcome gate**

PASS requires:

- `WL = 0`.
- `LW = 0`.
- No unresolved registered guess-checkpoint divergence.

DEFER applies to any WL/LW or checkpoint divergence still under diagnosis.

FAIL applies to:

- A diagnosed correctness, semantic or harness defect.
- Failure of a separately prospectively approved outcome criterion.

No WL/LW or checkpoint mismatch may be accepted merely as an “explained legitimate trajectory divergence” under this frozen contract.

A proposal that such divergence is legitimate requires a specification-level decision, not retrospective relaxation. Explaining a defect does not turn the affected evidence into a PASS.

Complete-run physical cost includes initial and terminal physical inputs. Logical processing and automatic terminal flags are not physical inputs.

## 21. PASS / FAIL / DEFER GATES

All required gates must pass for research PASS. DEFER is not PASS.

| Gate | PASS | FAIL | DEFER |
|---|---|---|---|
| **G1 — Semantic correctness** | Sound facts, bounded inference, accounting, lifecycle and treatment totality | Unsound fact, invalid treatment action, unauthorized inference, silent repair, or evaluator falsification counterexample | Required semantic evidence incomplete |
| **G2 — Materialized equivalence** | Independent phase-matched constraints, counts, probabilities and certainty boundaries agree | Reproducible mismatch, including shadow safe certainty at a valid V1 guess | Oracle independence/coverage insufficient |
| **G3 — Public-information safety** | Public-prefix proofs and solver/evaluator isolation established | Hidden/terminal truth reaches K reasoning or public-proof validation | Isolation cannot be verified |
| **G4 — Probability/risk contract** | Exact probability, genuine minimum-risk guesses, existing `(y,x)` ties and K certainty exhaustion | Probability drift, changed tie, premature or nonminimum-risk treatment guess | Relevant boundaries unverified |
| **G5 — Productive CHORD preservation** | Productive behavior retained and registered Model C regression criteria met | Invalid physical CHORD semantics or unacceptable modeled-time regression | Only count/availability evidence exists |
| **G6 — Experimental attribution** | Control identity, no shadow veto, isolated diagnostics and sufficient provenance | Control contamination, fabricated provenance, policy mixing or shadow-directed V1 change | Mechanisms cannot be distinguished |
| **G7 — Outcome/checkpoint acceptability** | `WL=0`, `LW=0`, no unresolved registered checkpoint divergence | Diagnosed correctness/semantic/harness defect, or failure of a separately prospectively approved criterion | Any mismatch still under diagnosis |
| **G8 — Physical-time benefit** | Defensible WW complete-run Model C improvement meets preregistered criteria | Adequately supported lack of worthwhile benefit or unacceptable regression | Effect/support too uncertain |
| **G9 — Compute burden** | No pathology; registered resource criteria met | Nonprogress, runaway cost or unacceptable burden | Material burden needs further quantified assessment |
| **G10 — Scope containment** | Mine-only K-C plus specified K-P0; frozen identities and exclusions preserved | Requires broader P2, L/F/H/R/G, stronger inference or objective changes | Scope compliance unresolved |

A `SHADOW_SOUNDNESS_VIOLATION` is zero-tolerance semantic/equivalence failure. It does not make shadow K the authority over V1’s physical action.

A properly isolated evaluator-only falsification audit is allowed. Positive answer agreement cannot substitute for G1/G2 public-proof obligations.

P-8 must pass before relying on SETUP_OPEN dominance.

Semantic violations have zero tolerance. Numerical effectiveness, regression and resource thresholds must be justified and prospectively registered.

## 22. COMPUTE-TIME POLICY

Frozen Model C physical time remains the optimization target.

Record:

- Complete treatment decision time.
- Required logical-state validation and acquisition work.
- Bounded local-pass work.
- Exact-analysis call count and duration.
- Planning and exact routing.
- Relevant memory/resource growth.
- Shadow, probe and evidence overhead separately.

Necessary runtime correctness work must not be hidden as optional diagnostics. Rich research-audit overhead must not automatically become a production algorithm requirement.

Use consistent timing boundaries and controlled environments for contemporaneous comparisons.

Qualitative blockers include:

- Nontermination or repeated work without progress.
- Violation of bounded local normalization.
- Pathological decision latency.
- Resource exhaustion.
- Disproportionate state or evidence growth.
- Compute burden disproportionate to physical-time opportunity.

If overhead is material but not plainly pathological, preregister a quantitative gate before acceptance.

Resource aborts are incomplete research runs, not ordinary losses or permission to switch policies.

CPU time must not be silently added to Model C. It remains a separate feasibility and burden diagnostic.

## 23. STAGE-3 VS STAGE-4 BOUNDARY

**Stage 3 optimizes modeled physical speed.**

**Stage 4 makes click/action efficiency itself the optimization objective.**

K cannot claim success merely because:

- FLAG count falls.
- Total action count falls.
- CHORD count changes.
- IOE improves.
- ZiNi-like efficiency improves.
- A replay looks shorter.

Those are diagnostics.

Success requires defensible WW complete-run Model C improvement under semantic, checkpoint/outcome, regression and scope gates.

Useful physical flags remain legitimate. A plan with more inputs may be faster because of movement and productive CHORD.

K-P0’s CHORD-directed materialization follows from frozen dominance and E-FIRST after P-8 verification. It is not an action-count objective or adoption of broader F.

The risk contract preserves exact public probabilities, minimum-risk selection, equal-risk ties and logical certainty exhaustion. It does not preserve mandatory physical marking priority.

## 24. INTERACTION WITH L / F / H / R / G

| Program | Relationship |
|---|---|
| **L — Local completion / target ordering** | Fallback or later independent research restricted to existing V1-admissible certainty alternatives |
| **F — Physical flag timing / selective flagging** | Downstream and excluded; only the specified immediate K-P0 mechanics are included |
| **H — Longer horizon / richer reveal value** | Excluded; first-reveal horizon and guaranteed reveal counting remain frozen |
| **R — Decision robustness** | Excluded as an optimization direction |
| **G — Nearest Minimum-Risk Guess** | Excluded; existing exact-risk `(y,x)` tie remains unchanged |

K intentionally overlaps only the **proven 100%-mine identity portion of backlog P2 Retained Certainty**.

Retained safe identities, zero-probability pools, probability maps, world counts, components and broader retained exact-analysis state are not adopted.

If K requires broader P2 or another program to succeed, stop under the scope gate rather than silently expanding the experiment.

K failure returns the research direction decision to Program L. It does not automatically authorize L implementation.

## 25. FAILURE / HARD-STOP CONDITIONS

Stop K rather than expand scope if:

- Sound accounting requires a substantially larger solver redesign.
- Independent acquisition soundness or materialized equivalence cannot be established.
- Exact probability semantics drift.
- Guess/outcome equality fails through a diagnosed defect.
- A proposed justification for checkpoint divergence requires a different specification.
- Hidden or terminal truth reaches solver reasoning or public-proof validation.
- The required timing-table dominance property fails.
- Productive FLAG/CHORD regression cannot be bounded in Model C terms.
- Opportunities are too rare to justify complexity.
- Complete-run benefit is negligible under registered criteria.
- Compute/evidence burden is disproportionate.
- The remedy requires retained safes, broader P2, stronger inference or longer-horizon policy.

For K-P0 integrity failure:

- Stop the treatment run.
- Record failure.
- Do not repair facts from answers.
- Do not synthesize WIN.
- Do not add completion flags or standalone fallback FLAG.
- Do not guess or switch policy.

For shadow failure in K-CONTROL:

- Detect and classify it.
- Mark the affected shadow evidence invalid under P-5.
- Preserve V1’s physical-action authority.
- Do not turn the shadow failure into a veto or replacement.

Research advancement may be withheld because shadow semantics failed.

An authorized implementation defect repair within the frozen contract may be requalified later. Failed evidence must remain visible.

If the direction fails, **STOP K and return to Program L as the selected fallback**. Rescue proposals remain backlog items unless separately authorized.

## 26. SUCCESS / PRODUCTION BOUNDARY

Research PASS establishes K as a supported **Stage-3 Extended candidate**.

It does not authorize:

- Production integration.
- Replacement of frozen V1.
- Changes to official benchmark identities.
- Reopening previous closeouts.
- Regeneration of accepted reports.
- Merge, deployment or official qualification execution.

Frozen V1 remains historical authority. The fixed-exemplar interpretation closeout remains valid.

Production design, integration and qualification require Gate P and separate authorization.

## 27. SPEC COMPLETENESS AUDIT

| Principle | Assessment |
|---|---|
| **SRP / separation of concerns** | Capability, minimal policy, V1 authority, shadow diagnostics, public proof and evaluator falsification are distinct |
| **Maintainability** | Mine-only persistence; explicit bounded inference, lifecycle and failure behavior |
| **Extensibility without speculation** | Broader P2 and downstream programs remain outside scope |
| **Testability** | Independent acquisition and representation oracles plus named test obligations |
| **Backward compatibility** | Frozen V1 behavior and historical identities preserved |
| **KISS / YAGNI** | One treatment policy; no retained-safe state or broader solver |
| **Determinism** | Explicit semantic inputs, exact arithmetic and frozen ranking/ties |
| **Evidence before optimization** | Semantics, attribution and timing premises precede benefit claims |
| **Information isolation** | Status-first cutoff and one-way evaluator boundary |
| **Stage-3 objective** | Complete-run Model C remains primary |

Final correction self-audit:

1. **R-1 through R-6 incorporated — Yes.**
   Expected checkpoint equality and G7 are corrected; shadow safe-at-guess is a semantic violation; SETUP_OPEN dominance is conditional on P-8; evaluator-only falsification is allowed; narrow P2 overlap is explicit; decision totality includes `U′=∅/PLAYING`.

2. **O-1, O-2, O-3 and O-6 incorporated without expansion — Yes.**
   Bounded normalization, nonrepairing validation, deterministic inputs and the execution-boundary explanation are explicit.

3. **P-1 through P-8 preserved — Yes.**
   All appear in Section 28 as mandatory prospective protocol obligations.

4. **O-4, O-5 and O-7 remain deferred — Yes.**
   None is made a core semantic requirement.

5. **Can shadow K veto frozen V1? — No.**
   Benign disagreement and zero-tolerance shadow failure both leave V1 action authority unchanged.

6. **Can hidden/terminal truth enter solver reasoning? — No.**
   The prohibition covers K, shadow K, selection, public-proof validation, acquisition and equivalence inputs.

7. **Can evaluator truth prove or repair a fact? — No.**
   It can only supply a falsifying counterexample and fail G1; it cannot upgrade proof or affect later run configuration.

8. **Is K-P0 total for validated PLAYING decision states? — Yes, by contract.**
   It selects local-safe reveal, exact-safe reveal or exact minimum-risk guess; inconsistent states fail closed.

9. **Can nonempty SETUP_OPEN be selected under verified P-8 and frozen mechanics? — No.**
   It is strictly dominated. Survival/selection is an invariant failure, not an alternative policy; either the required timing premise or its implementation has failed.

10. **Is another direction or production authorization introduced? — No.**
    Program boundaries and Gate R/Gate P remain unchanged.

These are specification-level conclusions. They do not claim that future executable obligations have already passed.

## 28. PROTOCOL-REQUIRED CARRY-FORWARD / OPTIONAL DEFER

The following **eight items are mandatory before the relevant experiment stages/results**. They do not block specification freeze.

| ID | Protocol-required obligation |
|---|---|
| **P-1** | Define E0 phase-matched oracle points and exact `M` snapshots, including local normalization and exact acquisition boundaries |
| **P-2** | Define independent oracle(s), including one independent of K accounting code, and separate acquisition-soundness verification from representation equivalence |
| **P-3** | Define CONTROL/K-P0 guess-checkpoint correspondence, normalized information comparison, exact-risk/target comparison and missing-evidence handling |
| **P-4** | Define productive-CHORD regression assessment in Model C terms; FLAG/CHORD/action counts remain diagnostic |
| **P-5** | Define K-CONTROL shadow-failure continuation, containment and evidence invalidity while preserving unchanged V1 execution authority |
| **P-6** | Define corpus identities, overlap, reuse and exclusion rules; explicitly exclude the ZiNi final holdout |
| **P-7** | Map G1–G10 to E0/E1/E2/E3 and identify which registered stage issues research PASS/FAIL/DEFER |
| **P-8** | Exhaustively authenticate and verify the full frozen timing table’s valid detour-dominance property before relying on SETUP_OPEN dominance |

P-8 must verify that every valid detour through a distinct FLAG target costs strictly more than the corresponding direct target movement under the exact frozen conventions. Partial table sampling, assumed triangle inequalities or intuitive geometry are insufficient.

Protocols must also prospectively supply the needed corpus-size rationale, practical-effect criteria, uncertainty treatment, resource limits and stopping rules. No unsupported numbers are assigned here.

The following remain **OPTIONAL / DEFER**:

| ID | Deferred item |
|---|---|
| **O-4** | Possible extension of CONTROL/K-CONTROL identity evidence to full V1 decision evidence and immutable shadow inputs |
| **O-5** | Optional reached-layer labels such as `LOCAL_DIRECT`, `LOCAL_NORMALIZED` and `GLOBAL_EXACT`; required semantic provenance does not mandate these names |
| **O-7** | Optional implementation/source explanatory note about terminal observation reads, observer callbacks and the WIN status-check barrier |

The semantic contract does not depend on adopting these three additions.

## 29. SPECIFICATION FREEZE STATUS

**BLOCKER:** 0

**REQUIRED:** 0

**PROTOCOL-REQUIRED:** 8 — P-1 through P-8; mandatory before relevant experiment stages/results, not blockers to the accepted specification freeze.

**OPTIONAL / DEFER:** 3 — O-4, O-5 and O-7.

**CONTENT VERDICT:** CONTENT FREEZE PASS

**SPECIFICATION STATUS:** FROZEN / ACCEPTED

**IMPLEMENTATION AUTHORIZATION:** NOT GRANTED

**NEXT:** Gate R preparation — E0/E1 research protocol design and authorization; design the bounded research protocol/harness authorization contract before any implementation or experiment.
