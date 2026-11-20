"""Experimental S3D3-A / GUESS_STRUCTURE_V1, stage 2: FORCED_PAIR_AND_TIE_LOOKAHEAD_V1.

K-LC1 stays the baseline and the stage-1 pair judgement is used unchanged.
On an EXACT_GUESS decision this module adds, for a small candidate set only,

  S_v(g) = sum_k [Z(g,k) / Z] * Q(g,k)   value of the virtual state in which
                                          only g's own number k is revealed;
  Z_f(g) = Z(g,0) when g has an unresolved neighbour (a flood would follow);
  S_c(g) = S_v(g) - Z_f(g) / Z            the same without the flood share.

Q is 1 when the game ends or a certain safe cell exists, otherwise one minus
the conditional minimum risk. The candidate set is every cell of the proven
forced pairs when one exists, otherwise the minimum-risk ties; it is computed
only for 2..8 cells and at most 72 hypothetical calls, decided before the
first call. A forced-pair cell is ranked by S_c, input cost, reading order; a
tie target changes only when S_c(x) > S_v(g0).

S_c <= S2 <= S_v holds for the next input of the K-LC1 line. These values are
NOT this policy's own two-input survival probability and NOT a whole-game win
rate. No flood states are enumerated, no S2/S3/W is computed, no cell outside
the set is evaluated, nothing is cached or reused by a later decision, and no
pseudo-5050 judgement exists here. A failure after the first call is an error
with no input; it never falls back to K-LC1. Experimental copy only.
"""

from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction

from core_engine import Action, CellState
from experiments.program_d3_forced_pair_policy import (
    APPLIED_CATEGORY, CANDIDATE_DEFINITION, CANDIDATE_ID, FORCED, find_pairs, independence_of,
    pair_proofs_for_state,
)
from experiments.program_k_capability import reading_order
from experiments.program_k_lc1_policy import (
    SingletonSelection, select_singleton_policy, validate_singleton_selection,
)
from experiments.program_k_policy import KPolicyIntegrityError
from simple_algorithm import InconsistentObservationError, SimpleMove
from stage3_physical import action_cost, validate_timing_table


IMPLEMENTATION_SCOPE = "FORCED_PAIR_AND_TIE_LOOKAHEAD_V1"
CELL_LIMIT = 8
CALL_LIMIT = 72  # D3's additional hypothetical calls of one decision; K's own exact call is separate.
FORCED_CATEGORY = APPLIED_CATEGORY
TIE_CATEGORY = "TIE_LOOKAHEAD_GUESS"
KEPT_GUESS_CATEGORY = "EXACT_MINIMUM_RISK_GUESS"
NOT_A_GUESS, FORCED_FIRST, TIE_LOOKAHEAD, KEPT = (
    "NOT_A_GUESS", "FORCED_5050_FIRST", "TIE_LOOKAHEAD", "K_LC1_GUESS_KEPT")
STATUS_NOT_A_GUESS, STATUS_SINGLE, STATUS_COMPUTED, STATUS_LIMIT = (
    "NOT_REQUIRED_NOT_A_GUESS", "NOT_REQUIRED_SINGLE", "COMPUTED", "NOT_COMPUTED_CANDIDATE_LIMIT")
SET_NONE, SET_PAIR_CELLS, SET_TIES = "NONE", "FORCED_PAIR_CELLS", "MIN_RISK_TIES"
RANK_NONE, RANK_S, RANK_COST = "NOT_APPLICABLE", "S_COST_READING", "COST_READING"
IMPOSSIBLE, GAME_ENDS, SAFE_CELL_EXISTS, MIN_RISK_GUESS = (
    "IMPOSSIBLE", "GAME_ENDS", "SAFE_CELL_EXISTS", "MIN_RISK_GUESS")
OUTSIDE_NOT_COMPUTED = "NOT_COMPUTED"


@dataclass(frozen=True)
class GuessPremises:
    """Public premises of one EXACT_GUESS decision; nothing hidden is in here.

    ``mines`` is the owner's current M and ``unresolved`` the hidden cells
    outside it. ``mine_worlds`` are the exact counts of exactly those cells in
    reading order, out of ``total_worlds``. A real record builds this from the
    K decision; a test may declare it, which is then no K inference at all.
    """

    observation: tuple
    num_mines: int
    mines: frozenset
    unresolved: frozenset
    total_worlds: int
    mine_worlds: tuple
    original_target: tuple
    cursor: tuple


@dataclass(frozen=True)
class Outcome:
    """One number k of one candidate. ``worlds`` is Z(g,k); 0 means impossible.

    ``minimum_mine_worlds`` and ``safe_cells`` are the grounds of Q among the
    remaining unresolved cells. An impossible number has no Q and no share.
    """

    number: int
    worlds: int
    q_kind: str
    q: Fraction | None
    minimum_mine_worlds: int | None
    safe_cells: int
    flood: bool


@dataclass(frozen=True)
class LookaheadValue:
    """Look-ahead of one candidate: every number outcome, Z_f, S_v and S_c."""

    cell: tuple
    mine_worlds: int
    total_worlds: int
    mine_neighbors: int
    unresolved_neighbors: int
    outcomes: tuple
    flood_worlds: int
    s_v: Fraction
    s_c: Fraction
    calls: int


@dataclass(frozen=True)
class LookaheadEvidence:
    """What was established BEFORE one guess input; attached to that input.

    ``risk`` is the risk of the actual target; ``original_*`` describe the
    K-LC1 target g0. ``target_s_c`` / ``original_s_v`` are None when that cell
    was not computed; a missing value is never written as zero.
    """

    kind: str
    target: tuple
    risk: Fraction
    risk_kind: str
    pair: tuple | None
    original_target: tuple
    original_risk: Fraction
    is_minimum_risk: bool
    lookahead_status: str
    target_s_c: Fraction | None
    original_s_v: Fraction | None


@dataclass(frozen=True)
class LookaheadSelection:
    """K-LC1 record, pair judgements, look-ahead values and the one input.

    ``inner`` is None only for a decision made from declared premises, which
    can be neither validated nor executed. When the target is unchanged the
    K-LC1 selection object itself is the choice. Cells outside
    ``lookahead_cells`` are not computed (``outside_set_lookahead``).
    """

    inner: SingletonSelection | None
    implementation_scope: str
    premises: GuessPremises | None
    pair_proofs: tuple
    independence: str
    lookahead_set: str
    lookahead_cells: tuple
    lookaheads: tuple
    outside_set_lookahead: str
    ranking: tuple
    rank_basis: str
    original_target: tuple | None
    target: tuple | None
    target_changed: bool
    move: SimpleMove
    category: str
    selection_reason: str
    lookahead_status: str
    planned_calls: int
    actual_calls: int
    evidence: LookaheadEvidence | None

    @property
    def policy_id(self) -> str:
        return CANDIDATE_ID

    @property
    def policy_definition(self) -> str:
        return CANDIDATE_DEFINITION

    @property
    def selected(self):
        """The unchanged K-LC1 PolicySelection, or None for a changed target."""
        return None if self.target_changed or self.inner is None else self.inner.selected


def _require(condition: bool, detail: str, code: str = "LOOKAHEAD_SELECTION") -> None:
    if not condition:
        raise KPolicyIntegrityError(code, detail)


def _is_cell(value) -> bool:
    return type(value) is tuple and len(value) == 2 and all(type(v) is int for v in value)


def _around(cell, width, height):
    x, y = cell
    return frozenset((nx, ny)
                     for ny in range(max(0, y - 1), min(height, y + 2))
                     for nx in range(max(0, x - 1), min(width, x + 2))
                     if (nx, ny) != cell)


def _kernel(observation, num_mines):
    """The one seam through which D3's additional hypothetical calls leave."""
    from simple_probability import calculate_probabilities
    return calculate_probabilities(observation, num_mines)


class _CallBudget:
    """Counts D3's hypothetical calls of one decision; checked before each call."""

    __slots__ = ("used",)

    def __init__(self, used: int = 0):
        self.used = used

    def spend(self) -> None:
        _require(self.used < CALL_LIMIT,
                 f"Hypothetical call {self.used + 1} would exceed the limit of {CALL_LIMIT}.",
                 "LOOKAHEAD_CALL_LIMIT")
        self.used += 1


def hypothetical_observation(observation, mines, cell, number):
    """Detached grid: hidden M cells as flags and only ``cell`` showing ``number``.

    Same materialisation of M as the K exact path. No flood is applied and the
    input rows are never modified.
    """
    _require(_is_cell(cell) and cell not in mines and type(number) is int and 0 <= number <= 8
             and observation[cell[1]][cell[0]] == CellState.HIDDEN,
             "A hypothetical number needs an unresolved hidden cell and a number 0..8.")
    return tuple(
        tuple(number if (x, y) == cell
              else int(CellState.FLAGGED) if value == CellState.HIDDEN and (x, y) in mines
              else int(value)
              for x, value in enumerate(row))
        for y, row in enumerate(observation))


def _outcome(number, worlds, minimum, safe_cells, unresolved_neighbors) -> Outcome:
    """Q and its kind from the grounds of one number outcome; pure arithmetic."""
    _require(type(number) is int and type(worlds) is int and worlds >= 0
             and (minimum is None or type(minimum) is int)
             and type(safe_cells) is int and safe_cells >= 0,
             "Malformed number outcome.", "LOOKAHEAD_ARITHMETIC")
    flood = number == 0 and unresolved_neighbors > 0
    if worlds == 0:
        _require(minimum is None and safe_cells == 0,
                 "An impossible number has no ground of Q.", "LOOKAHEAD_ARITHMETIC")
        return Outcome(number, 0, IMPOSSIBLE, None, None, 0, flood)
    if minimum is None or minimum == worlds:
        # Nothing unresolved is left, or only certain mines are: the game is won.
        _require(safe_cells == 0 and not flood,
                 "A finished game has no safe cell left and is no flood.", "LOOKAHEAD_ARITHMETIC")
        return Outcome(number, worlds, GAME_ENDS, Fraction(1), minimum, 0, flood)
    _require(0 <= minimum < worlds and (safe_cells > 0) == (minimum == 0),
             "Grounds of Q disagree with each other.", "LOOKAHEAD_ARITHMETIC")
    if minimum == 0:
        return Outcome(number, worlds, SAFE_CELL_EXISTS, Fraction(1), 0, safe_cells, flood)
    # A revealed 0 makes its unresolved neighbours safe, so a flood is never a guess.
    _require(not flood, "A flood outcome must have a certain safe cell.", "LOOKAHEAD_ARITHMETIC")
    return Outcome(number, worlds, MIN_RISK_GUESS, 1 - Fraction(minimum, worlds), minimum, 0, flood)


def make_value(cell, mine_worlds, total_worlds, mine_neighbors, unresolved_neighbors,
               outcomes) -> LookaheadValue:
    """Z_f, S_v and S_c of one candidate from its number outcomes; pure arithmetic.

    Integers and Fractions only. The numbers must be exactly m..m+u, and their
    world counts must add up to the candidate's safe worlds Z - Z_g.
    """
    _require(_is_cell(cell) and all(type(v) is int for v in (
        mine_worlds, total_worlds, mine_neighbors, unresolved_neighbors))
             and total_worlds > 0 and 0 <= mine_worlds <= total_worlds
             and mine_neighbors >= 0 and unresolved_neighbors >= 0
             and mine_neighbors + unresolved_neighbors <= 8
             and type(outcomes) is tuple and all(type(o) is Outcome for o in outcomes),
             "Malformed look-ahead input.", "LOOKAHEAD_ARITHMETIC")
    _require(tuple(o.number for o in outcomes)
             == tuple(range(mine_neighbors, mine_neighbors + unresolved_neighbors + 1)),
             f"Number outcomes of {cell} are missing, duplicated or out of range.",
             "LOOKAHEAD_ARITHMETIC")
    _require(sum(o.worlds for o in outcomes) == total_worlds - mine_worlds,
             f"Number outcomes of {cell} do not add up to its safe worlds.", "LOOKAHEAD_WORLD_COUNT")
    flood_worlds = sum(o.worlds for o in outcomes if o.flood)
    s_v = sum((Fraction(o.worlds, total_worlds) * o.q for o in outcomes if o.worlds), Fraction(0))
    s_c = s_v - Fraction(flood_worlds, total_worlds)
    _require(0 <= s_c <= s_v <= 1 - Fraction(mine_worlds, total_worlds),
             f"Look-ahead of {cell} violates 0 <= S_c <= S_v <= 1 - Z_g/Z.", "LOOKAHEAD_ARITHMETIC")
    return LookaheadValue(cell, mine_worlds, total_worlds, mine_neighbors, unresolved_neighbors,
                          outcomes, flood_worlds, s_v, s_c, len(outcomes))


def _check_premises(premises) -> None:
    _require(type(premises) is GuessPremises, "Expected the premises of one guess decision.")
    grid = premises.observation
    _require(type(grid) is tuple and bool(grid) and all(
        type(row) is tuple and len(row) == len(grid[0]) and bool(row)
        and all(type(v) is int for v in row) for row in grid),
             "Premises need a detached rectangular integer grid.")
    width, height = len(grid[0]), len(grid)
    inside = lambda cell: _is_cell(cell) and 0 <= cell[0] < width and 0 <= cell[1] < height
    hidden = frozenset((x, y) for y, row in enumerate(grid) for x, v in enumerate(row)
                       if v == CellState.HIDDEN)
    _require(type(premises.num_mines) is int and type(premises.mines) is frozenset
             and type(premises.unresolved) is frozenset
             and all(inside(cell) for cell in premises.mines)
             and premises.unresolved == hidden - premises.mines and bool(premises.unresolved),
             "Premises disagree with their own grid.")
    counts = premises.mine_worlds
    _require(type(premises.total_worlds) is int and premises.total_worlds > 0
             and type(counts) is tuple
             and all(type(item) is tuple and len(item) == 2 and _is_cell(item[0])
                     and type(item[1]) is int and 0 <= item[1] <= premises.total_worlds
                     for item in counts)
             and tuple(cell for cell, _ in counts)
             == tuple(sorted(premises.unresolved, key=reading_order)),
             "Exact counts must cover exactly the unresolved cells, in reading order.",
             "LOOKAHEAD_WORLD_COUNT")
    _require(premises.original_target in premises.unresolved and inside(premises.cursor),
             "Premises need the original target among the unresolved cells and a cursor.")


def _geometry(premises, cell):
    """(m, u): certain-mine and unresolved neighbours of one cell."""
    grid = premises.observation
    around = _around(cell, len(grid[0]), len(grid))
    return len(around & premises.mines), len(around & premises.unresolved)


def _read_kernel(result, remaining):
    """(Z(g,k), {cell: mine worlds}) of one hypothetical call, fully checked."""
    total = getattr(result, "total_worlds", None)
    _require(type(total) is int and total > 0, "Hypothetical world count must be a positive integer.",
             "LOOKAHEAD_KERNEL_RESULT")
    counts = {}
    for item in getattr(result, "probabilities", ()):
        cell = item.coordinate
        _require(_is_cell(cell) and cell in remaining and cell not in counts
                 and type(item.mine_worlds) is int and 0 <= item.mine_worlds <= total
                 and item.total_worlds == total,
                 "Invalid or duplicate hypothetical marginal.", "LOOKAHEAD_KERNEL_RESULT")
        counts[cell] = item.mine_worlds
    _require(counts.keys() == remaining, "Hypothetical result omitted unresolved cells.",
             "LOOKAHEAD_KERNEL_RESULT")
    return total, counts


def _evaluate(premises, cell, budget) -> LookaheadValue:
    """Every number m..m+u of one candidate; each is one kernel call, also when impossible."""
    mine_neighbors, unresolved_neighbors = _geometry(premises, cell)
    remaining = premises.unresolved - {cell}
    outcomes = []
    for number in range(mine_neighbors, mine_neighbors + unresolved_neighbors + 1):
        grid = hypothetical_observation(premises.observation, premises.mines, cell, number)
        budget.spend()  # immediately before the call: a call over the limit never leaves
        try:
            result = _kernel(grid, premises.num_mines)
        except InconsistentObservationError:
            # Only "no world has this number" becomes Z(g,k) = 0; anything else propagates.
            outcomes.append(_outcome(number, 0, None, 0, unresolved_neighbors))
            continue
        worlds, counts = _read_kernel(result, remaining)
        outcomes.append(_outcome(number, worlds, min(counts.values(), default=None),
                                 sum(1 for count in counts.values() if count == 0),
                                 unresolved_neighbors))
    return make_value(cell, dict(premises.mine_worlds)[cell], premises.total_worlds,
                      mine_neighbors, unresolved_neighbors, tuple(outcomes))


def _rebuild_values(premises, cells, recorded):
    """Recorded values rebuilt from their primitive grounds; no kernel call."""
    _require(type(recorded) is tuple and len(recorded) == len(cells)
             and all(type(value) is LookaheadValue and type(value.outcomes) is tuple
                     and all(type(o) is Outcome for o in value.outcomes) for value in recorded)
             and tuple(value.cell for value in recorded) == cells,
             "Missing, duplicate or partial look-ahead values.")
    counts, values = dict(premises.mine_worlds), []
    for cell, value in zip(cells, recorded):
        mine_neighbors, unresolved_neighbors = _geometry(premises, cell)
        values.append(make_value(
            cell, counts[cell], premises.total_worlds, mine_neighbors, unresolved_neighbors,
            tuple(_outcome(o.number, o.worlds, o.minimum_mine_worlds, o.safe_cells,
                           unresolved_neighbors) for o in value.outcomes)))
    return tuple(values)


def _rank_pair_cells(cells, by_cell, cursor, table) -> tuple:
    """Forced-pair cells: S_c (larger first) when computed, then cost, then reading order.

    S_v is never a rank key. Rows are (cell, S_c or None, Model C input cost).
    """
    rows = [(cell, by_cell[cell].s_c if by_cell else None, action_cost(table, cursor, cell))
            for cell in cells]
    if by_cell:
        return tuple(sorted(rows, key=lambda row: (-row[1], row[2], row[0][1], row[0][0])))
    return tuple(sorted(rows, key=lambda row: (row[2], row[0][1], row[0][0])))


def _decide(premises, table, inner=None, recorded=None) -> LookaheadSelection:
    """Pair judgement, candidate set, limits, values, rank and target of one decision.

    With ``recorded`` the values come from a record and are only re-checked
    arithmetically, so validation never calls the kernel.
    """
    _check_premises(premises)
    counts, total = dict(premises.mine_worlds), premises.total_worlds
    proofs = pair_proofs_for_state(premises.observation, premises.mines, premises.num_mines, premises)
    forced = tuple(p for p in proofs if p.verdict == FORCED)
    minimum = min(counts.values())
    ties = tuple(sorted((cell for cell, count in counts.items() if count == minimum), key=reading_order))
    g0 = ties[0]
    _require(g0 == premises.original_target and 0 < minimum < total,
             "The original target must be the first minimum-risk cell of an uncertain guess.")
    if forced:
        cells = tuple(sorted({cell for p in forced for cell in (p.a, p.b)}, key=reading_order))
        which = SET_PAIR_CELLS
    else:
        cells, which = ties, SET_TIES
    # The status is fixed here, before any hypothetical call.
    status = (STATUS_SINGLE if len(cells) == 1 else
              STATUS_LIMIT if len(cells) > CELL_LIMIT else STATUS_COMPUTED)
    planned = actual = 0
    values = ()
    if status == STATUS_COMPUTED:
        planned = sum(_geometry(premises, cell)[1] + 1 for cell in cells)
        _require(planned <= CALL_LIMIT,
                 f"{planned} planned hypothetical calls exceed the limit of {CALL_LIMIT}.",
                 "LOOKAHEAD_CALL_LIMIT")
        if recorded is None:
            budget = _CallBudget()
            values = tuple(_evaluate(premises, cell, budget) for cell in cells)
            actual = budget.used
        else:
            values = _rebuild_values(premises, cells, recorded)
            actual = sum(value.calls for value in values)
        _require(actual == planned and len(values) == len(cells),
                 f"{actual} hypothetical calls were made but {planned} were planned.",
                 "LOOKAHEAD_CALL_COUNT")
    else:
        _require(recorded is None or (type(recorded) is tuple and not recorded),
                 "No look-ahead value may be recorded when nothing was computed.")
    by_cell = {value.cell: value for value in values}
    if forced:
        ranking = _rank_pair_cells(cells, by_cell, premises.cursor, table)
        basis = RANK_S if by_cell else RANK_COST
        target, reason, kind = ranking[0][0], FORCED_FIRST, "FORCED_5050"
        risk_kind = "PROVEN_BY_PAIR_SYMMETRY"
        pair = next((p.a, p.b) for p in forced if target in (p.a, p.b))
    else:
        ranking, basis, pair = (), RANK_NONE, None
        target, reason, kind, risk_kind = g0, KEPT, "MIN_RISK", "COMPUTED_EXACT_MINIMUM"
        if by_cell:
            # A-conservative rule: only a cell whose S_c beats S_v(g0); equality keeps g0.
            better = [value for value in values if value.s_c > by_cell[g0].s_v]
            if better:
                best = max(value.s_c for value in better)
                target = min((value.cell for value in better if value.s_c == best), key=reading_order)
                reason, kind = TIE_LOOKAHEAD, "TIE_LOOKAHEAD"
    changed = target != g0
    evidence = LookaheadEvidence(
        kind, target, Fraction(counts[target], total), risk_kind, pair, g0, Fraction(counts[g0], total),
        counts[target] == minimum, status,
        by_cell[target].s_c if target in by_cell else None,
        by_cell[g0].s_v if g0 in by_cell else None)
    if changed:
        move, category = SimpleMove(Action.OPEN, *target), FORCED_CATEGORY if forced else TIE_CATEGORY
    elif inner is not None:
        move, category = inner.selected.move, inner.selected.category
    else:
        move, category = SimpleMove(Action.OPEN, *g0), KEPT_GUESS_CATEGORY
    return LookaheadSelection(
        inner, IMPLEMENTATION_SCOPE, premises, proofs, independence_of(proofs), which, cells, values,
        OUTSIDE_NOT_COMPUTED, ranking, basis, g0, target, changed, move, category, reason, status,
        planned, actual, evidence)


def decide(premises: GuessPremises, table) -> LookaheadSelection:
    """Decision from premises alone (``inner`` is None). For declared premises
    this is a calculation, not K inference, and its record cannot be executed."""
    return _decide(premises, validate_timing_table(table))


def _premises_for_state(observation, mines, num_mines, exact, original_target, cursor) -> GuessPremises:
    """Premises of an actual public state with the owner's current M."""
    grid = tuple(tuple(int(value) for value in row) for row in observation)
    hidden = frozenset((x, y) for y, row in enumerate(grid) for x, value in enumerate(row)
                       if value == CellState.HIDDEN)
    return GuessPremises(grid, num_mines, mines, hidden - mines, exact.total_worlds,
                         exact.mine_worlds, original_target, cursor)


def premises_of(inner: SingletonSelection) -> GuessPremises:
    """Public premises of the EXACT_GUESS decision behind one K-LC1 record."""
    native = inner.native
    evidence = native.evidence
    _require(native.continuation == "EXACT_GUESS" and evidence.phase_e is not None,
             "Look-ahead premises need an EXACT_GUESS decision.")
    return GuessPremises(evidence.observation, evidence.num_mines, evidence.after.M, evidence.after.U,
                         evidence.phase_e.total_worlds, evidence.phase_e.mine_worlds,
                         evidence.guess_target, native.cursor)


def _build(inner, table, recorded=None) -> LookaheadSelection:
    """Recompute the whole record from one K-LC1 record; no validation of ``inner`` here."""
    native, kept = inner.native, inner.selected
    if native.continuation != "EXACT_GUESS":
        _require(recorded is None or (type(recorded) is tuple and not recorded),
                 "A certainty decision has no look-ahead value.")
        return LookaheadSelection(
            inner, IMPLEMENTATION_SCOPE, None, (), "NOT_APPLICABLE", SET_NONE, (), (), "NOT_APPLICABLE",
            (), RANK_NONE, None, None, False, kept.move, kept.category, NOT_A_GUESS, STATUS_NOT_A_GUESS,
            0, 0, None)
    result = _decide(premises_of(inner), table, inner, recorded)
    # "A clue of the current accounting": the stage-1 check against the recorded constraints.
    _require(result.pair_proofs == find_pairs(native.evidence),
             "Pair judgement disagrees with the recorded accounting.")
    return result


def apply_lookahead(inner: SingletonSelection, table) -> LookaheadSelection:
    """Public adapter: one validated K-LC1 record in, one stage-2 record out."""
    validate_singleton_selection(inner)
    return _build(inner, validate_timing_table(table))


def select_lookahead_policy(evidence, cursor, table) -> LookaheadSelection:
    """One K-LC1 selection (one native selection), then the stage-2 adapter."""
    return apply_lookahead(select_singleton_policy(evidence, cursor, table), table)


def _shape(value, inner=None):
    """Exact nested types of a record, so a list, set or float cannot pass as equal."""
    if value is inner:
        return "INNER"
    if is_dataclass(value) and not isinstance(value, type):
        return type(value), tuple(_shape(getattr(value, f.name), inner) for f in fields(value))
    if isinstance(value, (tuple, list)):
        return type(value), tuple(_shape(item, inner) for item in value)
    if isinstance(value, (set, frozenset)):
        return type(value), frozenset(_shape(item, inner) for item in value)
    return type(value)


def _same(left, right, inner=None) -> bool:
    return left == right and _shape(left, inner) == _shape(right, inner)


def validate_lookahead_selection(result: LookaheadSelection, table) -> None:
    """Recheck a stored record against its own decision; select nothing anew.

    The K-LC1 record goes through its unchanged validator. Pair judgement,
    candidate set, status, planned calls, every recorded number outcome (range,
    completeness, world-count sum, Q, Z_f, S_v, S_c), rank, target, reason and
    evidence are rebuilt and compared in value and exact type. The per-number
    world counts themselves are trusted as recorded: NO hypothetical call is
    made here. ``table`` is the caller's already authenticated timing table.
    This does not bind the record to live state; the runner does that.
    """
    _require(type(result) is LookaheadSelection and type(result.inner) is SingletonSelection
             and type(result.lookaheads) is tuple,  # never None: None would mean "compute"
             "Expected an S3D3-A stage-2 selection record with its K-LC1 record.")
    inner = result.inner
    validate_singleton_selection(inner)
    expected = _build(inner, table, recorded=result.lookaheads)
    _require(_same(result, expected, inner),
             "Selection record disagrees with the judgement, look-ahead, rank or status of this decision.")
    _require(result.target_changed or result.move is inner.selected.move,
             "An unchanged target must keep the K-LC1 selection object itself.")
