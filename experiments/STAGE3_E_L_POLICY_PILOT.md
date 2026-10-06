# EXPERIMENTAL / RESEARCH — Stage-3 E/L policy pilot

This is a development-only evidence harness, not a production Stage-3 solver or
an official benchmark. Production code must never import `experiments`.
The Stage-3 algorithm specification remains unfrozen. No production solver,
benchmark runner, telemetry schema, calibration, or Stage-2 semantics are changed.

Use the repository CPython 3.12.14 environment from the repository root:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_stage3_e_l_policy_pilot
.venv/Scripts/python.exe -m experiments.stage3_e_l_policy_pilot --phase smoke100
```

Later, only when authorized:

```powershell
.venv/Scripts/python.exe -m experiments.stage3_e_l_policy_pilot --phase invariants1000
.venv/Scripts/python.exe -m experiments.stage3_e_l_policy_pilot --phase evidence10000
```

These fixed phases cover [100000,100100), [100000,101000), [100000,110000).
The generator/config is EXPERT_GENERAL_V1, seed equals game index, without
filtering or retrying boards. The first OPEN and initial cursor are (0,0).
There is no arbitrary range/count option. Every run uses a new directory under
`results/stage3_e_l_policy_pilot/`; `--output` can select a new child directory
for a reproducibility run. Existing directories are never overwritten/resumed.

The frozen profile's whole-file and separately encoded timing-table SHA-256 are
pinned and verified before generating a board. Costs use the integer table
directly for all OPEN/FLAG/CHORD inputs; Model C is never refit or regenerated.
Six qualified Stage-2 source files are also hash-checked (CRLF normalized to LF).
They were verified unchanged against qualified commit
`30b50575b7f8a807cb9f8573f8068f5294b75219`. Manifest hashes include supporting
engine/replay modules, harness, tests and source specifications.

The explicit pilot instructions and extension backlog supersede the older draft's
physical formula, E-equivalence wording and nearest-minimum-risk guess proposal.
E comparisons use integer cross-products with zero tolerance. Guesses execute
the exact Stage-2 selected OPEN, including the (y,x) tie. Local certainty prevents
probability enumeration. There are no retained facts or virtual probability calls.

Candidates and execution

- Direct current-safe OPEN has R=1, regardless of possible flood expansion.
- Each positive revealed clue supplies a direct CHORD when its actual flags
  satisfy the clue and at least one hidden neighbor remains; R is that count.
- For each clue, intersect its hidden neighbors with the current-certain mine
  pool. If flagging that entire local set satisfies the clue, generate a plan
  for each remaining terminal OPEN and, for positive clues, terminal CHORD.
  No unrelated FLAG detours or recursive virtual-mine inference are introduced.
  A proper subset cannot satisfy that clue; another clue may supply another
  setup set for the same OPEN. Duplicate physical plans are removed.
- Each local required set is routed exactly by Held-Karp, minimizing table cost
  from the current cursor through all setup FLAGs and the terminal input.
  At most seven setup mines surround a reveal-capable clue; this is structural,
  not a configured cap. Equal-cost routes use lexicographic (y,x) setup order.
- Dominance removes L>=other L and R<=other R with at least one strict inequality.
  Equal L/R plans remain. E-FIRST chooses E, L; L-FIRST chooses L, E.
  Both then use terminal (y,x,Action enum value), followed by the lexicographic
  setup coordinate sequence. Action count is not a tie objective.
- If no reveal plan exists, use the certain FLAG with minimum table cost,
  followed by (y,x). If no certainty exists, use the unchanged Stage-2 guess.
- Commit only the first physical action. Obtain a fresh public observation and
  completely replan after every input, including FLAG. Validate that first OPEN,
  FLAG or CHORD has current execution evidence. Virtual-only safe OPEN cannot
  execute directly. Planner arguments contain no engine, layout or board ID.

Hard gates and measurement

The two policy engines advance independently to each next guess/terminal boundary.
Before either guess is committed, compare the entire public observation (not only
its digest), reduced exact minimum probability and selected coordinate. Terminal
result and total guess count must also match. Guess count/position mismatches,
including one policy terminating while the other requests a guess, invalidate the
run. Any error stops the corpus; exit code is 2 and primary result stays null.
`failure.json` contains mismatched checkpoints where available. No mismatched
games are dropped, retried or included in a speed winner claim.

The 1000 phase additionally executes actual frozen `run_simple` on every board,
collecting checkpoints via its existing observer. Both policies are checked
against that reference. The 10000 phase repeats that check on its first 1000 games.
The 100 phase does not run the reference corpus; a focused test cross-checks one
real development board and small execution fixtures separately.

Whole-game time is the sum of actual physical action costs from canonical first
OPEN through terminal input. Each cursor destination is the physical target,
including CHORD. Engine auto-win flags contribute no inputs/cost. Predicted plan
L values overlap across replans and must never be summed as whole-game time.
Only a VALID full 10000 phase publishes the primary exact integer SUM comparison.
Smoke totals are descriptive; they do not close the policy gate.

Artifacts and diagnostic definitions

All outputs are canonical ASCII JSON/JSONL: sorted keys, compact separators, LF,
integers and reduced rational objects, with no float timing, wall-clock fields,
absolute paths or timestamps. Identical sources/runtime/config produce identical
bytes. No GUI, video, SQLite, production telemetry, or baseline DB is used.

- `manifest.json`: fixed protocol, source/profile/table hashes and provenance.
- `actions.jsonl`: actual physical stream, per-input table cost and cumulative
  time, public-state digest, candidate/dominance counts, both policies' chosen
  plans on the same visited state, exact selection ties and latency tradeoffs.
- `checkpoints.jsonl`: both policies' full public observations immediately before
  guesses, exact probabilities/coordinates and final results/counts.
- `stage2_reference.jsonl`: reference checkpoints when required (empty for 100).
- `games.jsonl`: paired per-game E-minus-L time delta, totals, action counts,
  fingerprint, seed, result, guess counts and gate status.
- `summary.json`: artifact hashes, invariant coverage, aggregate diagnostics and
  primary policy result (null until valid 10000-game evidence).

E-win/L-win/tie counts mean lower/equal whole-game modeled time, not game outcome.
Game WON/LOST counts are separate. L, R, setup distributions describe the chosen
plan at every reveal-planning invocation, including replans after setup FLAGs.
P50/P95/P99 use integer nearest-rank quantiles; histograms permit full inspection.

Policy decision divergence counts compare both selectors on the *same observation
and cursor*, separately along each actual policy trajectory. They count visited
decision occurrences, not unique states or comparisons of equal action indices
after trajectories diverge. Plan and committed-first-action divergence are both
reported. Do not add these two trajectory counts as a unique-state count.

Exact E tie counts mean more than one plan survives the E criterion at its policy
position (all survivors for E-FIRST, minimum-L survivors for L-FIRST). Final
fallback counts mean more than one plan remains after both criteria. FLAG fallback
ties are recorded separately. E-longer-latency delta/ratio distributions compare
the E choice against the L choice on the same visited state; the action records
retain each case. Actual E-FIRST trajectory diagnostics describe what E executed.

Python compute time is intentionally excluded from reproducible policy evidence;
this harness makes no compute-performance claim. The full policy SUM objective
includes all 10000 paired outcomes only after strict guess/result equality passes.
