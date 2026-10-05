# STAGE3_EXTENSION_BACKLOG

> **Status:** Living backlog — NOT part of the Stage-3 V1 frozen algorithm specification  
> **Purpose:** Record Stage-3 extension ideas that are intentionally deferred from V1 so they are not forgotten, while keeping V1 small, comparable to Stage 2, and easy to validate.
>
> This document is **not** an implementation requirement list.  
> Each item must be re-evaluated against evidence before implementation.

---

## 0. Backlog policy

Stage 3 V1 intentionally preserves a conservative comparison boundary with Stage 2.

V1 should first establish that:

- Stage-2 public-information risk discipline is preserved;
- certainty actions can be reordered/routed safely;
- cursor-aware routing and CHORD can reduce modeled physical play time;
- E-first / L-first or related local selection policy is chosen using paired total modeled-time evidence;
- physical-time comparison is deterministic under a frozen integer timing profile.

Ideas deferred here fall into four groups:

- **P0 — First extensions after V1:** already judged valuable, deliberately deferred mainly to keep V1 comparison clean.
- **P1 — Evidence-triggered physical-model extensions:** likely useful, but should be added only if calibration or replay evidence justifies them.
- **P2 — Larger planner/solver-state extensions:** potentially valuable, but increase algorithmic state or planning complexity.
- **Experimental / Stage-boundary items:** may intentionally change risk discipline or belong to Stage 4 rather than standard Stage 3.

For every extension, record:

1. what it changes;
2. why V1 defers it;
3. expected benefit;
4. added complexity / risk;
5. evidence required before implementation;
6. whether it remains Stage 3 or crosses into Stage 4 / experimental policy.

---

# 1. P0 — Known-Mine / No-Flag execution

## Idea

A cell may be known with certainty to be a mine without requiring an immediate physical FLAG input.

Conceptually:

```text
solver-known certain mine
!=
physically flagged cell
```

The planner may retain a public-information-derived known-mine fact and continue playing without placing every unnecessary flag.

## Why V1 defers it

Stage 2 uses physical FLAG state directly in its `N-F` constraints and gives certain-mine FLAG priority before safe OPEN / probability work.

Keeping this behavior in V1 makes Stage-2 ↔ Stage-3 comparison much cleaner:

- same local-first structure;
- same certainty closure;
- same guess points when guess tie-break is also preserved;
- speed differences can be attributed mainly to routing, action ordering, and CHORD.

Removing mandatory FLAG behavior would require a distinction between:

```text
physical FLAG state
known-mine logical state
```

and therefore introduces additional solver/planner state beyond the current Stage-2 execution model.

## Expected benefit

- remove unnecessary physical FLAG clicks;
- reduce cursor travel to mines that never need to be physically marked;
- better resemble high-level / NF-style Minesweeper play;
- potentially reduce total modeled physical time substantially in some positions.

## Added complexity / risk

- known-mine state must stay public-information-safe;
- local constraints may need to treat known-but-unflagged mines as logical mines without mutating the actual observation;
- exact probability enumeration may need an explicit contract for logical known mines;
- careless implementation could accidentally create a stronger inference engine or hidden-information leak;
- compute cost may change because physically unflagged certain mines can remain inside probability components.

## Evidence required

Before implementation:

- quantify V1 time spent on mandatory/fallback FLAG actions;
- identify boards where omitted FLAGs would actually save modeled time;
- measure exact-probability compute impact if known mines are not physically removed from constraints;
- define tests proving risk and probability equivalence to the corresponding physically flagged state.

## Classification

**Stage 3 extension.**

This remains speed-focused as long as the purpose is reducing physical execution time rather than minimizing clicks as an independent objective.

## Priority

**P0 — highest priority after V1.**

---

# 2. P0 — Nearest Minimum-Risk Guess

## Idea

When guessing is unavoidable, keep the exact Stage-2 risk floor:

```text
p(candidate) == p_min
```

but choose the candidate with the lowest modeled physical OPEN cost from the current cursor rather than Stage-2 `(y, x)` reading order.

## Why V1 defers it

Two cells can have exactly the same mine probability but different actual answers on a fixed board.

Therefore changing only the tie-break can change:

- which boards are won or lost;
- subsequent observations;
- later action traces;
- total modeled time.

That makes an initial V1 comparison less clean because routing-policy effects and outcome changes become mixed together.

V1 therefore keeps the Stage-2 `(y, x)` guess tie-break as a comparison control.

## Expected benefit

- remove unnecessary long cursor moves during uncertain play;
- make Stage 3 optimize physical speed even at guess points;
- preserve decision-local minimum risk while improving physical execution.

## Added complexity / risk

The mine probability does not increase, but fixed-board outcomes can differ.

A faster loss must never be reported as a speed improvement.

## Evidence required

Compare at least:

- whole-prefix WIN / LOSS outcomes;
- both-win modeled time;
- time-to-win;
- paired per-game modeled-time deltas where comparison is meaningful;
- outcome transitions:
  - Stage2/V1 win -> nearest loss;
  - Stage2/V1 loss -> nearest win;
- identical `p_min` verification for every changed guess.

## Classification

**Stage 3 extension.**

It remains within the same minimum-risk discipline.

## Priority

**P0 — highest priority after V1.**

---

# 3. P1 — Action-specific input costs

## Idea

Replace the V1 common baseline:

```text
c_OPEN = c_FLAG = c_CHORD = c
```

with calibrated action-specific costs, for example:

```text
c_OPEN
c_FLAG
c_CHORD
```

or an equivalent action-dependent timing table.

## Why V1 defers it

V1 deliberately avoids overfitting to a particular mouse/input implementation before controlled calibration demonstrates a meaningful difference.

A common baseline keeps the first model small and platform-independent.

## Expected benefit

- more realistic modeled physical time;
- more accurate OPEN vs FLAG vs CHORD route selection;
- better reproduction of real human input timing.

## Added complexity / risk

- calibration protocol becomes action-specific;
- CHORD physical gesture must be fixed or modeled explicitly;
- platform/input-method dependence increases.

## Evidence required

Controlled calibration samples separated by:

- OPEN / left click;
- FLAG / right click;
- CHORD gesture;
- representative movement distances.

Add action-specific cost only if observed differences are stable and materially affect policy or total modeled time.

## Classification

**Stage 3 physical-model extension.**

## Priority

**P1 — evidence-triggered.**

---

# 4. P1 — CPS / burst / minimum inter-action interval

## Idea

Add a physical execution constraint such as:

- sustained CPS limit;
- burst CPS behavior;
- minimum inter-action interval;
- short refractory term between rapid actions.

## Why V1 defers it

V1 already has positive action cost, so actions are not instantaneous.

No numeric CPS limit should be invented without evidence.

## Expected benefit

Prevent unrealistic sequences such as extremely rapid:

```text
FLAG -> CHORD -> FLAG -> CHORD
```

when the basic pointing model underestimates real human input timing.

## Added complexity / risk

- introduces temporal state between actions;
- calibration becomes more complicated;
- arbitrary caps can distort the planner.

## Evidence required

Use calibrated/replay data to check whether V1 systematically predicts unrealistically dense action bursts.

Only add a limiter if that pathology is observed.

## Classification

**Stage 3 physical-model extension.**

## Priority

**P1 — evidence-triggered.**

---

# 5. P1 — Direction-dependent / anisotropic movement model

## Idea

Allow movement cost to depend on direction or axis, rather than only Euclidean cell offset magnitude.

Possible examples:

- horizontal vs vertical difference;
- diagonal movement characteristics;
- device-specific anisotropy.

## Why V1 defers it

No current evidence shows that directional effects are large enough to justify extra parameters.

The V1 lookup table already captures distance deterministically with minimal complexity.

## Expected benefit

Potentially improve realism if controlled calibration reveals stable directional differences.

## Added complexity / risk

- larger calibration space;
- more parameters;
- greater device/environment dependence;
- easier to overfit noise.

## Evidence required

Controlled pointing data showing stable, reproducible directional effects large enough to affect route choice or modeled time.

## Classification

**Stage 3 physical-model extension.**

## Priority

**P1 — evidence-triggered.**

---

# 6. P1 — Physical CHORD variants

## Idea

Model different physical CHORD gestures separately, for example:

- opened-number left-click CHORD;
- both-button CHORD.

## Why V1 defers it

The V1 semantic planner needs one CHORD action, not a platform-specific input taxonomy.

V1 should first validate the benefit of semantic CHORD routing under one canonical physical gesture.

## Expected benefit

- better correspondence with actual UI/input configuration;
- potentially different input latency and movement behavior.

## Added complexity / risk

- configuration-dependent results;
- calibration must identify exactly which gesture is being modeled;
- comparison can become less portable.

## Evidence required

Measured differences between supported CHORD gestures and a concrete need to represent them separately.

## Classification

**Stage 3 physical-model extension.**

## Priority

**P1 — evidence-triggered.**

---

# 7. P2 — Retained certainty / persistent known-fact state

## Idea

Retain certain public facts from a previous exact probability computation across later decisions when they remain valid, instead of discarding them whenever a fresh local decision path is taken.

Examples:

- previously proven 0% cells;
- previously proven 100% cells.

## Why V1 defers it

V1 intentionally follows fresh-observation reanalysis and current-evidence planning.

Retaining solver facts introduces persistent logical state and raises validity/invalidation questions after each reveal.

## Expected benefit

- reduce repeated exact-probability work;
- reduce cursor backtracking caused by temporarily losing access to previously known facts;
- possibly enable better routing continuity.

## Added complexity / risk

- must prove when a retained fact remains valid;
- state invalidation becomes a correctness concern;
- risks turning Stage 3 into a substantially stronger stateful solver rather than a speed planner.

## Evidence required

Measure in V1:

- how often previously known 0% / 100% facts disappear from the current pool;
- how often exact probability is recomputed for equivalent information;
- compute-time and movement-time cost of this behavior.

Only proceed if the cost is material.

## Classification

**Stage 3 extension, but close to solver-strength boundary.**

## Priority

**P2.**

---

# 8. P2 — Longer planning horizon

## Idea

Plan beyond the V1 first-reveal boundary.

Possible future forms:

- multiple reveal actions in one virtual plan;
- deeper certainty-routing sequences;
- limited multi-reveal receding-horizon search.

## Why V1 defers it

V1 intentionally uses:

```text
think several certainty/setup actions
execute one
stop virtual plan at first information-revealing OPEN/CHORD
fresh observation
replan
```

A reveal can:

- flood-fill;
- expose new clues;
- create new certainty;
- enable CHORD;
- end the game.

Planning beyond that point requires assumptions about newly revealed information.

## Expected benefit

Could reduce short-sighted routing and avoid local choices that cause later backtracking.

## Added complexity / risk

- much larger search space;
- future-observation modeling;
- danger of using information not yet publicly available;
- harder reproducibility and testing.

## Evidence required

First show a meaningful V1 pathology where first-reveal receding horizon repeatedly causes avoidable total-time loss.

## Classification

**Stage 3 planner extension.**

## Priority

**P2.**

---

# 9. P2 — More sophisticated local reveal value

## Idea

Replace V1's conservative reveal count:

```text
safe OPEN -> R = 1
safe CHORD -> R = directly opened hidden non-flagged neighbors
```

with richer estimates of downstream reveal value.

Potential examples:

- infer likely/guaranteed opening expansion;
- account for known structural consequences;
- use additional public-information-only local value.

## Why V1 defers it

V1 deliberately avoids predicting flood/opening expansion or future clue information.

Keeping OPEN `R=1` makes the local heuristic simple and prevents hidden-answer-sensitive scoring.

## Expected benefit

Better distinguish OPENs that are locally similar but have different guaranteed downstream utility.

## Added complexity / risk

- easy to drift into stronger inference;
- harder to define "guaranteed" reveal value;
- possible overlap with Stage 4 efficiency concepts.

## Evidence required

Demonstrate recurring cases where V1's conservative R causes significant modeled-time loss and define a public-information-only replacement.

## Classification

**Stage 3 only if the metric remains speed-driven.**

If it becomes primarily about minimizing clicks / maximizing 3BV-style efficiency, move it to Stage 4.

## Priority

**P2.**

---

# 10. Experimental — Risk-speed trade-off variant

## Idea

Permit a candidate with risk slightly above exact minimum if it provides a sufficiently large modeled-time advantage.

Conceptually:

```text
p(candidate) <= p_min + allowed_risk_band
```

or another explicit risk budget.

## Why V1 defers it

This changes the core risk discipline.

Stage 3 V1 is designed to preserve Stage-2 risk selection, not trade survival probability for speed.

## Expected benefit

Could produce more aggressive speed play.

## Added complexity / risk

- policy becomes multi-objective;
- win-rate changes become intentional;
- requires a defensible risk budget;
- evaluation becomes much harder.

## Evidence required

A separate experimental specification must define:

- allowed risk increase;
- outcome reporting;
- non-inferiority / risk budget criteria;
- paired comparison protocol.

## Classification

**Experimental Stage-3 variant only.**

Do not merge into standard V1/V1.x without an explicit policy decision.

## Priority

**Experimental / deferred.**

---

# 11. Stage 4 boundary — click-efficiency-first ideas

The following should **not** silently enter Stage 3 merely because they can sometimes reduce time:

- optimizing raw action count as the primary objective;
- flag-investment strategies justified mainly by future click reduction;
- 3BV / click-efficiency optimization as the final selector;
- fewer-action tie-breaks with no demonstrated speed benefit;
- general minimum-click routing.

These belong to **Stage 4 — Efficiency-Focused Algorithm** unless their use is explicitly justified by measured Stage-3 physical-time reduction.

Stage 3 may use an efficiency technique as an instrument for speed, but **speed must remain the primary objective**.

---

# 12. Evidence-triggered items to revisit after V1 pilot/calibration

After the first validated Stage-3 V1 pilot, explicitly revisit this checklist:

- [ ] How much modeled time is spent on mandatory certainty FLAGs?
- [ ] Would Known-Mine / No-Flag materially reduce total modeled time?
- [ ] How often do exact-minimum guesses have multiple tied candidates?
- [ ] How much modeled time could nearest-minimum-risk selection save?
- [ ] How often would nearest-minimum-risk change board outcome?
- [ ] Are OPEN / FLAG / CHORD input costs measurably different?
- [ ] Does V1 produce unrealistic FLAG/CHORD bursts?
- [ ] Is there meaningful direction-dependent pointing behavior?
- [ ] Are previously known 0% / 100% facts frequently recomputed or lost?
- [ ] Does first-reveal receding horizon cause measurable backtracking?
- [ ] Does conservative OPEN `R=1` cause recurring poor plan selection?
- [ ] Are planner compute tails large enough to justify structural pruning?
- [ ] Is any proposed "speed" optimization actually an efficiency-first Stage-4 idea?

---

# 13. Current priority order

Recommended order after Stage-3 V1 is validated:

```text
P0-1  Known-Mine / No-Flag execution
P0-2  Nearest Minimum-Risk Guess

then, only if evidence supports them:

P1    Action-specific input costs
P1    CPS / burst constraints
P1    Direction-dependent movement
P1    Physical CHORD variants

then:

P2    Retained certainty state
P2    Longer planning horizon
P2    Richer local reveal value

separate experiment:

EXP   Risk-speed trade-off

separate stage:

S4    Click/action-efficiency-first optimization
```

This ordering is provisional. Evidence may reorder P1/P2 items.

---

# 14. Relationship to Stage-3 V1 specification

The Stage-3 V1 specification should reference this document only briefly.

Suggested wording:

> Several speed-oriented extensions are intentionally deferred from V1 to preserve a clean Stage-2 comparison boundary and keep the initial planner small and deterministic. These include known-mine/no-flag execution, nearest minimum-risk guess selection, richer physical input models, persistent certainty state, and longer planning horizons. They are tracked separately in `STAGE3_EXTENSION_BACKLOG.md` and are not part of the V1 freeze unless explicitly promoted by a later design decision.

The existence of this backlog must **not** be interpreted as approval to implement every item.

Each extension requires a new evidence-based decision before entering the implementation plan.
