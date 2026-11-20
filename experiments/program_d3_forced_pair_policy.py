"""Experimental S3D3-A / GUESS_STRUCTURE_V1, stage 1 only: FORCED_PAIR_ONLY_V1.

K-LC1 stays the baseline. On an EXACT_GUESS decision, two unresolved cells are
a forced 50/50 only when (F1) both are unresolved, (F2) exactly one of them is
a mine by one clue's residual or by the last mine, and (F3) every in-board cell
adjacent to exactly one of them is a current certain mine. A current risk of
1/2 alone never makes a pair. A proven pair is opened first, by Model C input
cost and then reading order, even when a lower-risk guess exists.

This stage implements NO look-ahead: no S_v, S_c, Z_f and no hypothetical
probability call. That is recorded as NOT_IMPLEMENTED_STAGE1, never as zero
scores and never as a candidate limit. Nothing here infers, enumerates worlds,
caches or keeps state; the exact counts are read from the K decision record.
The whole-game win-rate effect of the pre-emption is not verified here.
Experimental copy only.
"""

from dataclasses import dataclass
from fractions import Fraction

from core_engine import Action, CellState
from experiments.program_k_capability import reading_order
from experiments.program_k_lc1_policy import (
    SingletonSelection, select_singleton_policy, validate_singleton_selection,
)
from experiments.program_k_policy import KPolicyIntegrityError
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, validate_timing_table


CANDIDATE_ID = "S3D3-A"
CANDIDATE_DEFINITION = "GUESS_STRUCTURE_V1"
IMPLEMENTATION_SCOPE = "FORCED_PAIR_ONLY_V1"
APPLIED_CATEGORY = "FORCED_5050_GUESS"
FORCED, APPARENT, NOT_A_PAIR, UNSUPPORTED = (
    "FORCED_5050", "APPARENT_5050", "NOT_A_PAIR", "UNSUPPORTED")
PROVEN_MINE, REVEALED_NUMBER, UNRESOLVED_HIDDEN = (
    "PROVEN_MINE", "REVEALED_NUMBER", "UNRESOLVED_HIDDEN")
LOOKAHEAD_NOT_IMPLEMENTED = "NOT_IMPLEMENTED_STAGE1"
LOOKAHEAD_NOT_A_GUESS = "NOT_REQUIRED_NOT_A_GUESS"
LAST_MINE = ("LAST_MINE", None)


@dataclass(frozen=True)
class PairProof:
    """Judgement of one pair (a before b in reading order) on one decision.

    ``bases`` are the supported exactly-one grounds. ``distinguishing`` lists
    every in-board cell, other than a and b, adjacent to exactly one of them,
    with its current state. ``mine_worlds`` are the exact counts of (a, b).
    """

    a: tuple[int, int]
    b: tuple[int, int]
    bases: tuple[tuple, ...]
    distinguishing: tuple[tuple, ...]
    verdict: str
    failed: tuple[str, ...]
    mine_worlds: tuple[int, int] | None
    total_worlds: int | None


@dataclass(frozen=True)
class GuessEvidence:
    """What was established BEFORE one guess input; attached to that input.

    ``risk`` is the risk of the actual target. ``original_*`` describe the
    K-LC1 target g0 and are never presented as the risk actually taken.
    """

    kind: str
    target: tuple[int, int]
    risk: Fraction
    risk_kind: str
    pair: tuple | None
    original_target: tuple[int, int]
    original_risk: Fraction
    is_minimum_risk: bool
    lookahead_status: str


@dataclass(frozen=True)
class GuessSelection:
    """K-LC1 record, pair judgements and the one authorised input.

    When the target is unchanged the K-LC1 selection object itself is the
    choice. A changed target has no PolicySelection and needs the separate
    execution validator of the stage-1 runner.
    """

    inner: SingletonSelection
    implementation_scope: str
    pair_proofs: tuple[PairProof, ...]
    independence: str
    ranking: tuple[tuple, ...]
    original_target: tuple[int, int] | None
    target: tuple[int, int] | None
    target_changed: bool
    move: SimpleMove
    category: str
    selection_reason: str
    rank_basis: str
    lookahead_status: str
    lookahead_set: str
    planned_calls: int
    actual_calls: int
    evidence: GuessEvidence | None

    @property
    def policy_id(self) -> str:
        return CANDIDATE_ID

    @property
    def policy_definition(self) -> str:
        return CANDIDATE_DEFINITION

    @property
    def selected(self):
        """The unchanged K-LC1 PolicySelection, or None for a changed target."""
        return None if self.target_changed else self.inner.selected


def _require(condition: bool, detail: str, code: str = "FORCED_PAIR_SELECTION") -> None:
    if not condition:
        raise KPolicyIntegrityError(code, detail)


def _neighbors(cell, width, height):
    x, y = cell
    return frozenset((nx, ny)
                     for ny in range(max(0, y - 1), min(height, y + 2))
                     for nx in range(max(0, x - 1), min(width, x + 2))
                     if (nx, ny) != cell)


def _pair_key(cells):
    a, b = sorted(cells, key=reading_order)
    return a, b


def _clue_pairs(observation, mines, unresolved):
    """{pair: [clue sources]} for revealed numbers with exactly two unresolved
    neighbours and residual 1. Pure public geometry; at most 30 x 16 cells."""
    height, width = len(observation), len(observation[0])
    result = {}
    for y, row in enumerate(observation):
        for x, value in enumerate(row):
            if not 0 <= value <= 8:
                continue
            around = _neighbors((x, y), width, height)
            cells = around & unresolved
            if len(cells) == 2 and value - len(around & mines) == 1:
                result.setdefault(_pair_key(cells), []).append((x, y))
    return result


def _pair_proofs(observation, mines, unresolved, budget, counts, total):
    """Every pair with a supported exactly-one ground, normalised and judged."""
    height, width = len(observation), len(observation[0])
    for y, row in enumerate(observation):
        for x, value in enumerate(row):
            cell = (x, y)
            # A flag is a mine only through M; a hidden cell is in M or unresolved.
            _require((value == CellState.HIDDEN and (cell in mines) != (cell in unresolved))
                     or (value == CellState.FLAGGED and cell in mines and cell not in unresolved)
                     or (0 <= value <= 8 and cell not in mines and cell not in unresolved),
                     f"Cell {cell} disagrees with the current M / unresolved accounting.",
                     "FORCED_PAIR_ACCOUNTING")
    grounds = {pair: [("CLUE", source) for source in sources]
               for pair, sources in _clue_pairs(observation, mines, unresolved).items()}
    if budget == 1 and len(unresolved) == 2:
        grounds.setdefault(_pair_key(unresolved), []).append(LAST_MINE)
    proofs = []
    for a, b in sorted(grounds, key=lambda pair: (reading_order(pair[0]), reading_order(pair[1]))):
        only_one = (_neighbors(a, width, height) ^ _neighbors(b, width, height)) - {a, b}
        states = []
        for cell in sorted(only_one, key=reading_order):
            value = observation[cell[1]][cell[0]]
            states.append((cell, PROVEN_MINE if cell in mines else
                           REVEALED_NUMBER if 0 <= value <= 8 else UNRESOLVED_HIDDEN))
        isolated = all(state == PROVEN_MINE for _, state in states)
        _require(a in counts and b in counts, "Missing exact counts of a pair cell.",
                 "FORCED_PAIR_WORLD_COUNT")
        if isolated:
            # A proven forced pair must agree with the exact counts; otherwise
            # this judgement or the exact evidence is wrong. Never a silent keep.
            _require(2 * counts[a] == total == 2 * counts[b],
                     f"Forced pair {(a, b)} disagrees with the exact world counts.",
                     "FORCED_PAIR_WORLD_COUNT")
        proofs.append(PairProof(a, b, tuple(grounds[(a, b)]), tuple(states),
                                FORCED if isolated else APPARENT, () if isolated else ("F3",),
                                (counts[a], counts[b]), total))
    return tuple(proofs)


def pair_proofs_for_state(observation, mines, num_mines, exact):
    """Judge the pairs of an actual public state with the owner's current M.

    Used immediately before an input: the grid and M are the live ones; only
    the exact counts come from the decision record that the caller has bound.
    """
    hidden = frozenset((x, y) for y, row in enumerate(observation)
                       for x, value in enumerate(row) if value == CellState.HIDDEN)
    flags = frozenset((x, y) for y, row in enumerate(observation)
                      for x, value in enumerate(row) if value == CellState.FLAGGED)
    return _pair_proofs(observation, mines, hidden - mines, num_mines - len(flags | mines),
                        dict(exact.mine_worlds), exact.total_worlds)


def find_pairs(evidence) -> tuple[PairProof, ...]:
    """Pairs with a supported ground on one EXACT_GUESS decision record."""
    _require(evidence.continuation == "EXACT_GUESS" and evidence.phase_e is not None,
             "Pair judgement needs an EXACT_GUESS decision.")
    after = evidence.after
    proofs = pair_proofs_for_state(evidence.observation, after.M, evidence.num_mines, evidence.phase_e)
    # "A clue of the current accounting": the recorded constraints must agree
    # with what the public grid and M give.
    recorded = {(clue.source, _pair_key(clue.Uc)) for clue in after.constraints
                if len(clue.Uc) == 2 and clue.rc == 1}
    scanned = {(basis[1], (p.a, p.b)) for p in proofs for basis in p.bases if basis[0] == "CLUE"}
    last = [(p.a, p.b) for p in proofs if LAST_MINE in p.bases]
    _require(recorded == scanned
             and last == ([_pair_key(after.U)] if after.b == 1 and len(after.U) == 2 else []),
             "Recorded accounting disagrees with the public grid.", "FORCED_PAIR_ACCOUNTING")
    return proofs


def judge_pair(evidence, a, b) -> PairProof:
    """Judgement of two named cells: FORCED_5050, APPARENT_5050 or NOT_A_PAIR.

    NOT_A_PAIR means the supported grounds do not make it a pair; it is not a
    proof that the two cells can be told apart.
    """
    proofs = find_pairs(evidence)
    unresolved = evidence.after.U
    if a == b or a not in unresolved or b not in unresolved:
        return PairProof(a, b, (), (), NOT_A_PAIR, ("F1",), None, None)
    key = _pair_key((a, b))
    for proof in proofs:
        if (proof.a, proof.b) == key:
            return proof
    counts = dict(evidence.phase_e.mine_worlds)
    return PairProof(key[0], key[1], (), (), NOT_A_PAIR, ("F2",),
                     (counts[key[0]], counts[key[1]]), evidence.phase_e.total_worlds)


def judge_structure(evidence, cells) -> str:
    """Verdict for a named cell set. Only two-cell pairs are judged in stage 1."""
    cells = frozenset(cells)
    if len(cells) != 2:
        return UNSUPPORTED
    return judge_pair(evidence, *sorted(cells, key=reading_order)).verdict


def independence_of(proofs) -> str:
    """Independence is recorded only among proven forced pairs that share no cell."""
    forced = [p for p in proofs if p.verdict == FORCED]
    if len(forced) < 2:
        return "NOT_APPLICABLE"
    cells = [cell for p in forced for cell in (p.a, p.b)]
    return "INDEPENDENT_PROVEN" if len(set(cells)) == len(cells) else "OVERLAPPING_NOT_CLAIMED"


def rank_cells(forced, cursor, table) -> tuple:
    """Cells of the proven pairs by Model C input cost, then reading order (y, x)."""
    cells = {cell for p in forced for cell in (p.a, p.b)}
    return tuple(sorted(((cell, action_cost(table, cursor, cell)) for cell in cells),
                        key=lambda item: (item[1], item[0][1], item[0][0])))


def _build(inner, table) -> GuessSelection:
    """Recompute the whole record from one K-LC1 record; no validation here."""
    native, kept = inner.native, inner.selected
    evidence = native.evidence
    if native.continuation != "EXACT_GUESS":
        return GuessSelection(inner, IMPLEMENTATION_SCOPE, (), "NOT_APPLICABLE", (), None, None, False,
                              kept.move, kept.category, "NOT_A_GUESS", "NOT_APPLICABLE",
                              LOOKAHEAD_NOT_A_GUESS, "NONE", 0, 0, None)
    proofs = find_pairs(evidence)
    forced = tuple(p for p in proofs if p.verdict == FORCED)
    exact = evidence.phase_e
    counts, total = dict(exact.mine_worlds), exact.total_worlds
    g0 = evidence.guess_target
    g0_risk = Fraction(counts[g0], total)
    if not forced:
        proof = GuessEvidence("MIN_RISK", g0, g0_risk, "COMPUTED_EXACT_MINIMUM", None, g0, g0_risk,
                              True, LOOKAHEAD_NOT_IMPLEMENTED)
        return GuessSelection(inner, IMPLEMENTATION_SCOPE, proofs, independence_of(proofs), (), g0, g0,
                              False, kept.move, kept.category, "K_LC1_GUESS_KEPT", "NOT_APPLICABLE",
                              LOOKAHEAD_NOT_IMPLEMENTED, "NONE", 0, 0, proof)
    ranking = rank_cells(forced, native.cursor, table)
    target = ranking[0][0]
    pair = next((p.a, p.b) for p in forced if target in (p.a, p.b))
    risk = Fraction(counts[target], total)  # the risk actually taken, never g0's
    proof = GuessEvidence("FORCED_5050", target, risk, "PROVEN_BY_PAIR_SYMMETRY", pair, g0, g0_risk,
                          risk == exact.minimum_risk, LOOKAHEAD_NOT_IMPLEMENTED)
    changed = target != g0
    return GuessSelection(inner, IMPLEMENTATION_SCOPE, proofs, independence_of(proofs), ranking, g0,
                          target, changed,
                          SimpleMove(Action.OPEN, *target) if changed else kept.move,
                          APPLIED_CATEGORY if changed else kept.category,
                          "FORCED_5050_FIRST", "COST_READING", LOOKAHEAD_NOT_IMPLEMENTED, "NONE", 0, 0,
                          proof)


def apply_forced_pair(inner: SingletonSelection, table) -> GuessSelection:
    """Pure projection of one validated K-LC1 record; K-LC1 is always baseline."""
    validate_singleton_selection(inner)
    return _build(inner, validate_timing_table(table))


def select_guess_policy(evidence, cursor, table) -> GuessSelection:
    """One K-LC1 selection (one native selection), then the pure projection."""
    return apply_forced_pair(select_singleton_policy(evidence, cursor, table), table)


def _coordinate(value) -> bool:
    return type(value) is tuple and len(value) == 2 and all(type(v) is int for v in value)


def _well_typed_proof(p) -> bool:
    return (type(p) is PairProof and _coordinate(p.a) and _coordinate(p.b)
            and type(p.bases) is tuple
            and all(type(g) is tuple and len(g) == 2 and type(g[0]) is str
                    and (g[1] is None or _coordinate(g[1])) for g in p.bases)
            and type(p.distinguishing) is tuple
            and all(type(d) is tuple and len(d) == 2 and _coordinate(d[0]) and type(d[1]) is str
                    for d in p.distinguishing)
            and type(p.verdict) is str and type(p.failed) is tuple
            and all(type(name) is str for name in p.failed)
            and (p.mine_worlds is None or (type(p.mine_worlds) is tuple and len(p.mine_worlds) == 2
                                           and all(type(v) is int for v in p.mine_worlds)))
            and (p.total_worlds is None or type(p.total_worlds) is int))


def _well_typed_evidence(e) -> bool:
    return e is None or (
        type(e) is GuessEvidence and type(e.kind) is str and _coordinate(e.target)
        and type(e.risk) is Fraction and type(e.risk_kind) is str
        and (e.pair is None or (type(e.pair) is tuple and len(e.pair) == 2
                                and all(_coordinate(c) for c in e.pair)))
        and _coordinate(e.original_target) and type(e.original_risk) is Fraction
        and type(e.is_minimum_risk) is bool and type(e.lookahead_status) is str)


def validate_guess_selection(result: GuessSelection, table) -> None:
    """Recheck stored judgements, rank, target, reason and status; select nothing anew.

    The K-LC1 record is checked by its unchanged validator. ``table`` is the
    caller's already authenticated timing table. No inference and no
    probability call. This does not bind the record to live state; the runner
    does that immediately before the one input.
    """
    _require(type(result) is GuessSelection, "Expected an S3D3-A stage-1 selection record.")
    inner = result.inner
    validate_singleton_selection(inner)
    _require(type(result.implementation_scope) is str
             and type(result.pair_proofs) is tuple
             and all(_well_typed_proof(p) for p in result.pair_proofs)
             and type(result.independence) is str and type(result.ranking) is tuple
             and all(type(item) is tuple and len(item) == 2 and _coordinate(item[0])
                     and type(item[1]) is int for item in result.ranking)
             and (result.original_target is None or _coordinate(result.original_target))
             and (result.target is None or _coordinate(result.target))
             and type(result.target_changed) is bool and type(result.move) is SimpleMove
             and all(type(v) is str for v in (result.category, result.selection_reason,
                                              result.rank_basis, result.lookahead_status,
                                              result.lookahead_set))
             and type(result.planned_calls) is int and type(result.actual_calls) is int
             and _well_typed_evidence(result.evidence),
             "Malformed or mutable selection record.")
    expected = _build(inner, table)
    _require(result == expected,
             "Selection record disagrees with the pair judgement, rank or status of this decision.")
    _require(result.target_changed or result.move is inner.selected.move,
             "An unchanged target must keep the K-LC1 selection object itself.")
