# ZiNi Improvement Final Adjudication

## 1. Status

Date: **2026-10-13 (Asia/Seoul)**.

**ZINI IMPROVEMENT MILESTONE — CLOSED**

**QUALITY POLICY: V1 RETAINED**

**V2 QUALITY RESEARCH: CLOSED / NOT ADOPTED**

This records the final ChatGPT adjudication against the live implementation at
`2595ee67bf1b8e3ae06aae991ca13813a65aacba` on `feature/zini-improvement`.
Local `main` and merge-base at closeout were both
`3213c7f9958b73be77f1739a2d1a68962005c1c2`. The subsequent closeout commit is
documentation only. Closure is distinct from manual GUI verification and merge approval.

## 2. Scope: three independent axes

| Axis | Disposition |
| --- | --- |
| TYPE S — semantics-preserving speed work | Accept the core optimizations present in source and protected by current regression tests. |
| TYPE Q — solution-quality research | Retain V1; no proposed V2 quality policy adopted. |
| Trace / Explorer | Accept the implemented optional post-hoc trace, transport/controller and Explorer UI. |

Speed work does not change ZiNi semantics. Trace visibility does not establish
quality improvement. Mechanism correctness does not establish quality superiority.

## 3. Accepted production changes and Git identities

The complete pre-closeout feature history, oldest first, is:

| Commit | Exact subject | Classification |
| --- | --- | --- |
| `a430d37047401756903510c8cc1987ebf6f47f2b` | test: freeze zini v1 golden regression baseline | Test/golden |
| `2b3ee07ad1be53db0b47b5be5ea6c29690243c35` | perf: precompute static zini premium relationships | Accepted TYPE S + equivalence tests |
| `523e799603464670f838230b8eb291df01ae20c4` | perf: cache zini safe cells for solved checks | Accepted TYPE S + equivalence tests |
| `6540858ea3dfd7baecfddd28e2ebf4cc8f163ab2` | perf: reduce zini premium candidate construction overhead | Accepted TYPE S + equivalence tests |
| `21516efe269dc8e4cbfc4750a43494a50a725498` | feat: add post-hoc zini trace backend | Accepted Trace + tests |
| `7f941931b27a41cf1171766f2fd81898b2e0cf64` | feat: add zini explorer transport controller | Accepted transport/controller + tests |
| `2595ee67bf1b8e3ae06aae991ca13813a65aacba` | feat: add zini explorer ui | Accepted Explorer UI + tests |

No R0/V2-A/B/C experimental implementation is part of these changes.

## 4. Speed-work disposition

[`zini_core.py`](../../zini_core.py) precomputes static Premium relationships,
caches the immutable safe-cell set for solved checks/copies, and constructs
ordered Premium candidates from the precomputed relationships. Candidate order,
Premium values, move semantics and V1 search policy are preserved.

[`test_zini_core.py`](../../tests/test_zini_core.py) compares optimized behavior
with reference calculations, including intermediate states, direct state mutations
and partial openings. [`test_zini_golden.py`](../../tests/test_zini_golden.py)
locks ten workloads' full moves, clicks and non-elapsed search metadata.
These are regression evidence within their tested scope, not universal optimality proofs.
No speed ratio is claimed in this closeout; research acquisition timings are not
accepted production benchmarks.

## 5. Trace / Explorer disposition

- [`zini_trace.py`](../../zini_trace.py) reconstructs and validates the completed
  `ZiniResult` after search. Immutable steps hold revealed/flagged deltas and
  pre-state Premium/tie/selection relationships. Its player uses logical indices.
- [`zini_metric_worker.py`](../../zini_metric_worker.py) returns the existing
  final moves with token/clicks/error after one search.
  [`zini_explorer.py`](../../zini_explorer.py) owns that result and sent snapshot,
  validates transport, and lazily builds/caches the trace on an eligible request.
  Counters do not build a trace or rerun search.
- [`zini_explorer_ui.py`](../../zini_explorer_ui.py) supplies a separate read-only
  board, first/previous/next/last navigation, slider and index autoplay with a
  configurable interval. It displays logical steps, physical click totals,
  selected coordinates, new reveals/flags and pre-state diagnostics.
- [`ui_manager.py`](../../ui_manager.py) permits access after Live WON/LOST or
  for a completed Replay, independent of that Replay's current seek position.
  Board/mode reset invalidates the session; closing only the Explorer preserves
  its cached position for reopening.

**Replay != ZiNi Trace.** Replay records actual game actions; Trace explains an
answer-board-based virtual calculation. A logical `flag_chord` can include
several physical clicks. Trace has no recorded game clock, discarded search tree,
beam/RNG provenance or Replay persistence contract. Trace schema and ZiNi semantics
versions remain 1; this closeout changes neither.

## 6. Accepted V1 quality baseline

The production Counters policy remains `standard_seeded_chain_v1`, total
1,000 evaluations, standard phase 500, chain phase 500, seed 0 and no time limit.
Other existing deterministic, min-ties and bounded V1 APIs remain available.
Advanced ZiNi is **bounded best-so-far**, not an exact global minimum.
Lambda is not a production parameter.

## 7. V2 investigation summary

- **R0 / V2-A:** established real representational limitations of the V1
  envelope. This does not imply production V2 quality superiority.
- **B1:** expanded-union search regressed on fresh development boards. This
  failure remains part of the accepted record.
- **B2:** the primary failure mechanism was loss of V1 search coverage as the
  decision/alternative populations expanded. All 30 regressed V1 final paths
  remained legal but were not generated by the candidate; +35 clicks of the
  aggregate regression was already present at standard end. Some extension
  candidates nevertheless had genuine path-level value.
- **C1 / C2:** isolated B/C architecture was made mechanically sound, including
  protected V1 work, legal paid extension and accounting. This was mechanism
  evidence, not fresh quality evidence.
- **C3 / C4:** fresh B/C quality evidence was NO-SIGNAL; the final Family-A
  evidence adjudication was NO-GO.

`G6/F-2/K0/N-setupOFF` describes experimental research semantics only. It is not
an adopted replacement for V1. Family A was never production-implemented or
fresh-quality-tested; C4 did not implement or run a Family-A prototype.

## 8. Fresh-quality evidence

All ranges below are inclusive `EXPERT_GENERAL_V1` development ranges, distinct
from the reserved final holdout. Figures are from the frozen reports, not new runs.

| Phase | Boards | V1 aggregate | Candidate aggregate | Outcome |
| --- | --- | ---: | ---: | --- |
| B1 fresh development | 1,010,000..1,010,049; N=50 | 5,805 | 5,842 | +37 clicks; improved/tied/worse 1/19/30; REGRESSION |
| C3 fresh tuning | 3,010,000..3,010,249; N=250 | 28,949 | best 28,949 | No aggregate improvement |
| C3 fresh internal validation | 3,010,250..3,010,499; N=250 | 29,048 | 29,048 | improved/tied/worse 0/250/0; **NO-SIGNAL** |

C3 selected **lambda=1** from tied minima **1..4**, using the preregistered
smallest-lambda rule before validation. Validation used that frozen policy;
it was not retuned. Lambda=1 is not an improved production setting. Observed
zero paired deltas do not establish zero population improvement or uncertainty.

## 9. Family A final NO-GO

C4 audited the strongest B1 actual-V1 improvement witness, **game1010018**:
actual V1 **121**, extension path **120**. Exact known-path replay and source
analysis established its construction from B/C's **immutable final-standard
handoff**, via **step0 G+F -> step5 G**, within the existing **depth2** kernel.
These step indices are zero-based. Structural reachability does not imply that
fixed RNG or a particular finite lambda actually discovers the path.

Across **22 useful-extension representatives**:

- **9** structurally supported as B/C-reachable;
- **0** proven B/C-unreachable;
- **13** unresolved.

This does **not** show that all useful extension paths are B/C-reachable.
The justified conclusion is that no concrete Family-A-specific mechanism
witness justified further research. Family A **GO/NO-GO = NO-GO**.

## 10. Final holdout status

Reserved final holdout: `EXPERT_GENERAL_V1`, indices
**2,010,000..2,010,099**, **100 boards**.

It **remained unopened**: it was not generated, fingerprinted, calculated or
inspected for final quality adjudication. Development failed before authorization
to use it, so it was deliberately not consumed. This is part of the experiment
design record. This closeout performs no holdout operation.

## 11. What was accepted

The implemented TYPE S optimizations, V1 golden/regression protection, Trace
backend/controller/Explorer, V1 production quality policy, and the bounded
research findings and negative results recorded above.

## 12. What was not adopted

No V2 experimental A/B/C production policy, production lambda parameter,
expanded research semantics or Family-A implementation. No further lambda,
search or semantics tuning is authorized by this milestone.

## 13. What is proven

Within the cited source/tests and frozen evidence: implemented production
boundaries; tested preservation of V1 outputs; genuine V1 representational
limits and some extension path value; B1 regression and B2 coverage-loss
diagnosis; C1/C2 mechanism correctness; C3's reported sample results; C4's
primary two-edge construction and nine supported representatives.

## 14. What is not proven

V2 is not proven mathematically impossible; V1 is not proven globally optimal;
G/F/K are not proven valueless; Family A is not proven incapable of improvement.
Global B/C reachability, fixed-budget discovery of every supported path,
generalization, exact zero population improvement and exact global-minimum ZiNi
are not established. The 13 unresolved reachabilities and untested Family-A
quality remain research limitations, **not TODO items** for this milestone.

## 15. Final milestone decision

Under the investigated fixed-budget search designs and the completed
development evidence, no V2 policy established sufficient general quality
improvement to justify production adoption or further research within the
current milestone. V1 therefore remains the accepted production quality policy.

**FINAL V2 ADJUDICATION — RESEARCH CLOSED.**
No Family A implementation, further lambda/search/semantics tuning or final
holdout use follows this decision.

## 16. Next project milestone

**DEFERRED TO LATER MILESTONE: Stage-3 Extended**, now the next active milestone:
application execution integration; a unified execution/replay/visualization
surface; same-board Human / Stage-2 / Stage-3 comparison; representative-board
demonstrations; useful timeline analytics; algorithm/version and physical-model
configuration separation. Playback settings remain distinct from planning inputs.
See [Extended direction](../stage3-extended/README.md). No Extended implementation
is part of this closeout; frozen Stage-3 V1 identities and documents remain intact.

## 17. Compact provenance

Primary research source: `V2_C4_FINAL_REPORT.txt`, dated 2026-10-13,
terminal label **V2-C4 NO-GO — NO DEFENSIBLE FAMILY-A-SPECIFIC CONTINUATION EVIDENCE**.
Supporting exact figures: `V2_B1_FINAL_REPORT.txt`, `V2_B2_FINAL_REPORT.txt`,
`V2_C3_FINAL_REPORT.txt`. Earlier R0/V2-A/C1/C2 findings above are summarized
by C4; this closeout does not rerun their experiments or independently recertify
the complete bulk evidence archive.

| External artifact | SHA256 provenance |
| --- | --- |
| C4 final report | `cd15b4cfd0b480a23167baf21eb2603340f1f73df2cb6c1970b09294dc32fe55` — read and hashed at closeout |
| C3 final report | `19eff900bbf1151efdd6bd548151cbe3ad55f09817936026016cfa11a02c1379` — read and rehashed; matches C4 |
| B2 final report | `60c621e64bf5620805485ed04ebbd0a8d2600bf87e460c14059029aa122f5391` — identity recorded by C4 |
| C3 board manifest | `5523d000610663d6b795512f2e6cf91453373b5205e62aa116412d394a27745a` — identity recorded by C3 |
| C3 selected lambda | `577a1577c317f1e71a6b8a14b001e30a4758d096c5c510f1f470f1ea0288819a` — identity recorded by C3 |

Reports, original manifests, multi-GB raw runs and diagnostic ZIPs remain external.
No bulk evidence, experimental prototype or temporary visualization tree is added
to Git. Source/test/executable evidence takes precedence over historical reports.
