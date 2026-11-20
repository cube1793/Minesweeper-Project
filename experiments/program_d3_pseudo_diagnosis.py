"""Experimental S3D3-A stage 4, diagnosis only: PAIR_MIRROR_DIAGNOSIS_V1.

On an EXACT_GUESS decision, two unresolved cells g and h within distance 2 are
a mirror pair when, with D = (N(g) ^ N(h)) - {g, h} (in-board cells adjacent
to exactly one of them),

  P1  no revealed number is in D;
  P2  every unresolved cell d of D is a mine in every world in which g is;
  P3  no world has both g and h as mines.

Then every strategy fails to win with probability at least Z_g / Z. That is a
LOWER BOUND of the whole-game loss, not an optimality claim and not a win
rate; nothing here computes or records a win rate.

P1 makes the relation symmetric (and Z_g = Z_h), so pairs are unordered and
one conditional call decides a pair: the hidden M cells and one anchor cell
are flagged in a detached grid and the existing exact kernel is called once
with the same mine total. Its total must equal Z_g; P3 reads Z'_h and P2
reads Z' - Z'_d. All comparisons are integer comparisons.

Pairs, anchors and the call order are fixed before the first call: at most 8
anchors, one call each, shared by every pair of that anchor. A pair left
without an anchor is NOT EXAMINED, a pair beyond distance 2 is not examined
at all, and neither is a "not a mirror" verdict. A failed check or kernel
call is an error and never becomes a verdict.

This module selects nothing: the selection, its reason and the loss
classification of the stage-2 record are only copied. It adds no record
format, storage or reader, changes no existing type, keeps no state and
passes nothing to a later decision. Validation recomputes from the recorded
conditional counts and never calls the kernel; it is no independent
recomputation and no proof of origin. Experimental copy only.
"""

from dataclasses import dataclass, fields, is_dataclass, replace

from core_engine import CellState
from experiments.program_d3_forced_pair_policy import (
    FORCED, PROVEN_MINE, REVEALED_NUMBER, UNRESOLVED_HIDDEN,
)
from experiments.program_d3_lookahead_policy import GuessPremises, LookaheadSelection
from experiments.program_k_capability import reading_order
from experiments.program_k_policy import KPolicyIntegrityError
from simple_algorithm import InconsistentObservationError


DIAGNOSIS_SCOPE = "PAIR_MIRROR_DIAGNOSIS_V1"
PSEUDO_RANGE = 2
PSEUDO_ANCHOR_LIMIT = 8
PSEUDO_CALL_LIMIT = 8  # additional conditional calls of one decision; the stage-2 limit of 72 is separate
MIRROR_PROVEN, CONDITION_FAILED, NOT_EXAMINED = (
    "MIRROR_PROVEN", "CONDITION_FAILED", "NOT_EXAMINED_CALL_LIMIT")
BY_GEOMETRY, BY_MARGINALS, BY_CONDITIONAL, NOT_DECIDED = (
    "GEOMETRY", "MARGINALS", "CONDITIONAL_COUNTS", "NOT_DECIDED")
HOLDS, FAILS, NOT_EVALUATED = "HOLDS", "FAILS", "NOT_EVALUATED"
P2_NO_CELL, P2_HOLDS, P2_FAILS, P2_FAILS_MARGINAL = (
    "HOLDS_NO_UNRESOLVED_CELL", "HOLDS_BY_WORLD_COUNT", "FAILS_BY_WORLD_COUNT", "FAILS_BY_MARGINAL")
P3_HOLDS, P3_FAILS, P3_FAILS_MARGINAL = (
    "HOLDS_BY_WORLD_COUNT", "FAILS_BY_WORLD_COUNT", "FAILS_BY_MARGINAL")
CELL_PROVEN, CELL_REFUTED, CELL_UNDECIDED, CELL_NO_PAIR = (
    "MIRROR_PROVEN", "REFUTED_IN_SUPPORTED_RANGE", "UNDECIDED_CALL_LIMIT", "NO_PAIR_IN_RANGE")
SEARCH_NONE, SEARCH_COMPLETE, SEARCH_PARTIAL = (
    "NO_CANDIDATE_PAIR", "COMPLETE_SUPPORTED_RANGE", "PARTIAL_CALL_LIMIT")
FORCED_SAME, FORCED_OUT_OF_RANGE, FORCED_NOT_EXAMINED = (
    "SAME_PAIR_MIRROR_PROVEN", "OUT_OF_RANGE_NOT_EXAMINED", "IN_RANGE_NOT_EXAMINED_CALL_LIMIT")
RISK_MEANING = "CURRENT_INPUT_RISK"
BOUND_MEANING = "WHOLE_GAME_NOT_WIN_LOWER_BOUND_NOT_OPTIMALITY"


@dataclass(frozen=True)
class MirrorCheck:
    """Judgement of one unordered pair (a before b in reading order).

    ``distinguishing`` lists every in-board cell other than a and b adjacent to
    exactly one of them, with its state. ``anchor`` is the cell whose
    conditional call decides the pair (the first one in call order), or None.
    ``p2_rows`` are (d, Z'_d, Z' - Z'_d) for the unresolved cells of D.
    """

    a: tuple
    b: tuple
    distinguishing: tuple
    isolated: bool
    p1: str
    p2: str
    p3: str
    decided_by: str
    anchor: tuple | None
    joint_mine_worlds: int | None
    p2_rows: tuple
    verdict: str


@dataclass(frozen=True)
class ConditionalCounts:
    """Exact counts of the worlds in which ``anchor`` is a mine: Z' and every Z'_c."""

    anchor: tuple
    total_worlds: int
    mine_worlds: tuple


@dataclass(frozen=True)
class CellDiagnosis:
    """One unresolved cell. No status here means "not a pseudo 50/50"."""

    cell: tuple
    mine_worlds: int
    floating: bool
    status: str
    partners: tuple
    pairs_in_range: int
    candidate_pairs: int
    not_examined_pairs: int
    floating_cells_out_of_range: int


@dataclass(frozen=True)
class PairCounts:
    in_range: int
    p1_failed: int
    marginal_failed: int
    candidate: int
    decided: int
    not_examined: int


@dataclass(frozen=True)
class PseudoPlan:
    """Everything fixed before the first call: pairs, anchors, call order."""

    premises: GuessPremises
    actual_target: tuple
    pairs: tuple
    anchors: tuple
    planned_calls: int
    floating: tuple


@dataclass(frozen=True)
class PseudoDiagnosis:
    """Diagnosis of one EXACT_GUESS decision, made before its input. It authorises nothing.

    ``actual_*`` are copied from the selection record and are not decided
    here. ``target_bound`` is (Z_t, Z) only when the actual target is
    MIRROR_PROVEN; it is the lower bound BOUND_MEANING and equals the current
    risk RISK_MEANING only in number.
    """

    scope: str
    premises: GuessPremises
    actual_target: tuple
    actual_selection_reason: str
    actual_kind: str
    original_target: tuple
    limits: tuple
    anchors: tuple
    conditionals: tuple
    checks: tuple
    counts: PairCounts
    cells: tuple
    search_status: str
    planned_calls: int
    actual_calls: int
    target_status: str
    target_bound: tuple | None
    forced_pairs: tuple


def _require(condition: bool, detail: str, code: str = "PSEUDO_PREMISES") -> None:
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


def _distance(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _kernel(observation, num_mines):
    """The one seam through which the conditional calls of this module leave."""
    from simple_probability import calculate_probabilities
    return calculate_probabilities(observation, num_mines)


class _CallBudget:
    """Counts the conditional calls of one decision; checked before each call."""

    __slots__ = ("used",)

    def __init__(self):
        self.used = 0

    def spend(self) -> None:
        _require(self.used < PSEUDO_CALL_LIMIT,
                 f"Conditional call {self.used + 1} would exceed the limit of {PSEUDO_CALL_LIMIT}.",
                 "PSEUDO_CALL_LIMIT")
        self.used += 1


def mine_hypothesis_observation(observation, mines, cell):
    """Detached grid: hidden M cells and ``cell`` as flags, everything else unchanged.

    Same materialisation of M as the K exact path. No number is written and no
    flood is applied; the input rows are never modified.
    """
    _require(_is_cell(cell) and cell not in mines
             and 0 <= cell[1] < len(observation) and 0 <= cell[0] < len(observation[0])
             and observation[cell[1]][cell[0]] == CellState.HIDDEN,
             "A mine hypothesis needs an unresolved hidden cell.")
    return tuple(
        tuple(int(CellState.FLAGGED)
              if value == CellState.HIDDEN and ((x, y) in mines or (x, y) == cell) else int(value)
              for x, value in enumerate(row))
        for y, row in enumerate(observation))


def _check_premises(premises, actual_target) -> None:
    """Public premises of one guess decision: grid, accounting, exact counts."""
    _require(type(premises) is GuessPremises, "Expected the premises of one guess decision.")
    grid = premises.observation
    _require(type(grid) is tuple and bool(grid) and all(
        type(row) is tuple and len(row) == len(grid[0]) and bool(row)
        and all(type(v) is int and (v in (CellState.HIDDEN, CellState.FLAGGED) or 0 <= v <= 8) for v in row)
        for row in grid), "Premises need a detached rectangular public grid.")
    width, height = len(grid[0]), len(grid)
    inside = lambda cell: _is_cell(cell) and 0 <= cell[0] < width and 0 <= cell[1] < height
    hidden = frozenset((x, y) for y, row in enumerate(grid) for x, v in enumerate(row)
                       if v == CellState.HIDDEN)
    flags = frozenset((x, y) for y, row in enumerate(grid) for x, v in enumerate(row)
                      if v == CellState.FLAGGED)
    _require(type(premises.num_mines) is int and type(premises.mines) is frozenset
             and type(premises.unresolved) is frozenset
             and all(inside(cell) for cell in premises.mines),
             "Premises need an integer mine total and frozen cell sets.")
    # A flag is a mine only through M; a hidden cell is in M or unresolved.
    _require(flags <= premises.mines and premises.mines <= flags | hidden
             and premises.unresolved == hidden - premises.mines and bool(premises.unresolved),
             "The grid disagrees with the current M / unresolved accounting.", "PSEUDO_ACCOUNTING")
    budget = premises.num_mines - len(premises.mines)
    _require(1 <= budget <= len(premises.unresolved), "Invalid remaining mine budget.", "PSEUDO_ACCOUNTING")
    counts, total = premises.mine_worlds, premises.total_worlds
    _require(type(total) is int and total > 0 and type(counts) is tuple
             and all(type(item) is tuple and len(item) == 2 and _is_cell(item[0]) and type(item[1]) is int
                     for item in counts)
             and tuple(cell for cell, _ in counts) == tuple(sorted(premises.unresolved, key=reading_order)),
             "Exact counts must cover exactly the unresolved cells, in reading order.")
    _require(all(0 < count < total for _, count in counts),
             "A guess decision has only strictly uncertain cells.")
    _require(sum(count for _, count in counts) == budget * total,
             "The exact counts do not add up to the remaining mines of every world.", "PSEUDO_WORLD_COUNT")
    _require(_is_cell(actual_target) and actual_target in premises.unresolved
             and premises.original_target in premises.unresolved,
             "The actual and the original target must be unresolved cells.")


def _partners(cell, unresolved):
    """Unresolved cells within the supported distance that come after ``cell`` in reading order."""
    x, y = cell
    span = range(-PSEUDO_RANGE, PSEUDO_RANGE + 1)
    found = ((x + dx, y + dy) for dy in span for dx in span if (dx, dy) != (0, 0))
    return sorted((other for other in found
                   if other in unresolved and reading_order(other) > reading_order(cell)),
                  key=reading_order)


def plan_pseudo(premises: GuessPremises, actual_target) -> PseudoPlan:
    """Pairs in range, geometry, marginal exclusions, candidate pairs, anchors and call order.

    No kernel call is made here. A candidate pair's ``anchor`` is the first
    anchor in call order that contains it; a candidate without one stays
    NOT EXAMINED.
    """
    _check_premises(premises, actual_target)
    grid, mines, unresolved = premises.observation, premises.mines, premises.unresolved
    width, height = len(grid[0]), len(grid)
    counts, total = dict(premises.mine_worlds), premises.total_worlds
    ordered = tuple(sorted(unresolved, key=reading_order))
    around = {cell: _around(cell, width, height) for cell in ordered}

    def state(cell):
        value = grid[cell[1]][cell[0]]
        return PROVEN_MINE if cell in mines else REVEALED_NUMBER if 0 <= value <= 8 else UNRESOLVED_HIDDEN

    floating = tuple(cell for cell in ordered
                     if not any(0 <= grid[y][x] <= 8 for x, y in around[cell]))
    pairs = []
    for a in ordered:
        for b in _partners(a, unresolved):
            distinguishing = tuple((cell, state(cell)) for cell in
                                   sorted((around[a] ^ around[b]) - {a, b}, key=reading_order))
            revealed = [cell for cell, kind in distinguishing if kind == REVEALED_NUMBER]
            uncertain = [cell for cell, kind in distinguishing if kind == UNRESOLVED_HIDDEN]
            isolated = not revealed and not uncertain
            if revealed:
                pairs.append(MirrorCheck(a, b, distinguishing, isolated, FAILS, NOT_EVALUATED,
                                         NOT_EVALUATED, BY_GEOMETRY, None, None, (), CONDITION_FAILED))
                continue
            # P1 holds: swapping a and b maps "only a" worlds onto "only b" worlds.
            _require(counts[a] == counts[b],
                     f"P1 holds for {(a, b)} but their exact counts differ.", "PSEUDO_WORLD_COUNT")
            p3 = P3_FAILS_MARGINAL if 2 * counts[a] > total else NOT_EVALUATED
            p2 = (P2_FAILS_MARGINAL if any(counts[cell] < counts[a] for cell in uncertain)
                  else NOT_EVALUATED)
            if p3 != NOT_EVALUATED or p2 != NOT_EVALUATED:
                pairs.append(MirrorCheck(a, b, distinguishing, isolated, HOLDS, p2, p3, BY_MARGINALS,
                                         None, None, (), CONDITION_FAILED))
            else:
                pairs.append(MirrorCheck(a, b, distinguishing, isolated, HOLDS, NOT_EVALUATED,
                                         NOT_EVALUATED, NOT_DECIDED, None, None, (), NOT_EXAMINED))
    of_cell = {}
    for index, check in enumerate(pairs):
        if check.verdict == NOT_EXAMINED:
            of_cell.setdefault(check.a, []).append(index)
            of_cell.setdefault(check.b, []).append(index)
    g0 = premises.original_target
    first = (actual_target,) if g0 == actual_target else (actual_target, g0)
    priority = first + tuple(sorted((cell for cell in ordered if cell not in first),
                                    key=lambda cell: (counts[cell], *reading_order(cell))))
    anchors, representative = [], {}
    for cell in priority:
        if len(anchors) == PSEUDO_ANCHOR_LIMIT:
            break
        fresh = [index for index in of_cell.get(cell, ()) if index not in representative]
        if fresh:
            anchors.append(cell)
            for index in fresh:
                representative[index] = cell
    pairs = tuple(replace(check, anchor=representative[index]) if index in representative else check
                  for index, check in enumerate(pairs))
    _require(len(anchors) <= PSEUDO_CALL_LIMIT, "More anchors than conditional calls allowed.",
             "PSEUDO_CALL_LIMIT")
    return PseudoPlan(premises, actual_target, pairs, tuple(anchors), len(anchors), floating)


def _check_conditional(conditional, premises) -> None:
    """Shape, exact types and the integer relations of one conditional count record."""
    _require(type(conditional) is ConditionalCounts and _is_cell(conditional.anchor)
             and conditional.anchor in premises.unresolved,
             "A conditional record needs an unresolved anchor.", "PSEUDO_RECORD")
    total, rows = conditional.total_worlds, conditional.mine_worlds
    remaining = tuple(sorted(premises.unresolved - {conditional.anchor}, key=reading_order))
    _require(type(total) is int and total > 0 and type(rows) is tuple
             and all(type(row) is tuple and len(row) == 2 and _is_cell(row[0]) and type(row[1]) is int
                     and 0 <= row[1] <= total for row in rows)
             and tuple(cell for cell, _ in rows) == remaining,
             "Conditional counts must be exact integers over exactly the other unresolved cells.",
             "PSEUDO_RECORD")
    counts = dict(premises.mine_worlds)
    _require(total == counts[conditional.anchor],
             f"The conditional world count of {conditional.anchor} is not its mine world count.",
             "PSEUDO_WORLD_COUNT")
    _require(all(count <= counts[cell] for cell, count in rows),
             "A joint mine world count exceeds the marginal count.", "PSEUDO_WORLD_COUNT")
    budget = premises.num_mines - len(premises.mines)
    _require(sum(count for _, count in rows) == (budget - 1) * total,
             "Conditional counts do not add up to the remaining mines of every world.",
             "PSEUDO_WORLD_COUNT")


def _read_conditional(result, premises, cell) -> ConditionalCounts:
    """One kernel result as exact integers over exactly U - {cell}; anything else is an error."""
    total = getattr(result, "total_worlds", None)
    _require(type(total) is int and total > 0,
             "Conditional world count must be a positive integer.", "PSEUDO_KERNEL_RESULT")
    remaining = premises.unresolved - {cell}
    counts = {}
    for item in getattr(result, "probabilities", ()):
        other = getattr(item, "coordinate", None)
        _require(_is_cell(other) and other in remaining and other not in counts
                 and type(item.mine_worlds) is int and 0 <= item.mine_worlds <= total
                 and type(item.total_worlds) is int and item.total_worlds == total,
                 "Invalid, duplicate or foreign conditional marginal.", "PSEUDO_KERNEL_RESULT")
        counts[other] = item.mine_worlds
    _require(counts.keys() == remaining, "The conditional result omitted unresolved cells.",
             "PSEUDO_KERNEL_RESULT")
    conditional = ConditionalCounts(
        cell, total, tuple((other, counts[other]) for other in sorted(counts, key=reading_order)))
    _check_conditional(conditional, premises)
    return conditional


def _conditional(premises, cell, budget) -> ConditionalCounts:
    """The one conditional call of an anchor. A world must exist because Z_cell > 0."""
    grid = mine_hypothesis_observation(premises.observation, premises.mines, cell)
    budget.spend()  # immediately before the call: a call over the limit never leaves
    try:
        result = _kernel(grid, premises.num_mines)
    except InconsistentObservationError as error:
        raise KPolicyIntegrityError(
            "PSEUDO_ZERO_WORLDS",
            f"The kernel found no world with {cell} as a mine although its mine world count is positive.",
        ) from error
    return _read_conditional(result, premises, cell)


def _judge(check, conditional):
    """(Z_gh, p2 rows, P2, P3, verdict) of one candidate pair from one endpoint's conditional counts."""
    counts = dict(conditional.mine_worlds)
    other = check.b if conditional.anchor == check.a else check.a
    joint = counts[other]
    rows = tuple((cell, counts[cell], conditional.total_worlds - counts[cell])
                 for cell, kind in check.distinguishing if kind == UNRESOLVED_HIDDEN)
    p2_holds = all(row[2] == 0 for row in rows)
    p2 = P2_NO_CELL if not rows else P2_HOLDS if p2_holds else P2_FAILS
    p3 = P3_HOLDS if joint == 0 else P3_FAILS
    return joint, rows, p2, p3, MIRROR_PROVEN if joint == 0 and p2_holds else CONDITION_FAILED


def _forced_relations(forced_pairs, by_pair, unresolved):
    """How each existing FORCED_5050 pair relates to this diagnosis; never a verdict of its own."""
    _require(type(forced_pairs) is tuple and all(
        type(pair) is tuple and len(pair) == 2 and all(_is_cell(cell) and cell in unresolved for cell in pair)
        and reading_order(pair[0]) < reading_order(pair[1]) for pair in forced_pairs)
             and len(set(forced_pairs)) == len(forced_pairs),
             "Forced pairs must be distinct pairs of unresolved cells in reading order.")
    rows = []
    for a, b in forced_pairs:
        if _distance(a, b) > PSEUDO_RANGE:
            rows.append((a, b, FORCED_OUT_OF_RANGE))  # outside the supported range: not examined
            continue
        check = by_pair[(a, b)]
        _require(check.verdict in (MIRROR_PROVEN, NOT_EXAMINED),
                 f"The examined forced pair {(a, b)} does not satisfy the mirror conditions.",
                 "PSEUDO_FORCED_PAIR")
        rows.append((a, b, FORCED_SAME if check.verdict == MIRROR_PROVEN else FORCED_NOT_EXAMINED))
    return tuple(rows)


def _assemble(plan, conditionals, selection_reason, kind, forced_pairs) -> PseudoDiagnosis:
    """The whole record from the plan and the conditional counts; pure arithmetic, no kernel call."""
    premises, target = plan.premises, plan.actual_target
    _require(type(selection_reason) is str and type(kind) is str,
             "The copied selection reason and kind must be text.")
    _require(tuple(conditional.anchor for conditional in conditionals) == plan.anchors,
             "Conditional records must be exactly those of the planned anchors, in call order.",
             "PSEUDO_CALL_COUNT")
    by_anchor = {conditional.anchor: conditional for conditional in conditionals}
    judged = []
    for check in plan.pairs:
        if check.anchor is not None:
            joint, rows, p2, p3, verdict = _judge(check, by_anchor[check.anchor])
            other = check.b if check.anchor == check.a else check.a
            if other in by_anchor:
                # Both endpoints were anchors: the second count must tell the same story.
                again = _judge(check, by_anchor[other])
                _require((again[0], again[2], again[3], again[4]) == (joint, p2, p3, verdict),
                         f"The two conditional counts of {(check.a, check.b)} disagree.",
                         "PSEUDO_WORLD_COUNT")
            check = replace(check, p2=p2, p3=p3, decided_by=BY_CONDITIONAL, joint_mine_worlds=joint,
                            p2_rows=rows, verdict=verdict)
        judged.append(check)
    counts, total = dict(premises.mine_worlds), premises.total_worlds
    floating = frozenset(plan.floating)
    of_cell = {}
    for check in judged:
        of_cell.setdefault(check.a, []).append(check)
        of_cell.setdefault(check.b, []).append(check)
    cells = []
    for cell in sorted(premises.unresolved, key=reading_order):
        own = of_cell.get(cell, [])
        partners = tuple(sorted((check.b if check.a == cell else check.a
                                 for check in own if check.verdict == MIRROR_PROVEN), key=reading_order))
        waiting = sum(1 for check in own if check.verdict == NOT_EXAMINED)
        status = (CELL_PROVEN if partners else CELL_NO_PAIR if not own
                  else CELL_UNDECIDED if waiting else CELL_REFUTED)
        far = (sum(1 for other in plan.floating if other != cell and _distance(cell, other) > PSEUDO_RANGE)
               if cell in floating else 0)
        cells.append(CellDiagnosis(
            cell, counts[cell], cell in floating, status, partners, len(own),
            sum(1 for check in own if check.decided_by in (BY_CONDITIONAL, NOT_DECIDED)), waiting, far))
    tally = PairCounts(
        len(judged), sum(1 for check in judged if check.p1 == FAILS),
        sum(1 for check in judged if check.decided_by == BY_MARGINALS),
        sum(1 for check in judged if check.decided_by in (BY_CONDITIONAL, NOT_DECIDED)),
        sum(1 for check in judged if check.decided_by == BY_CONDITIONAL),
        sum(1 for check in judged if check.verdict == NOT_EXAMINED))
    search = (SEARCH_NONE if tally.candidate == 0 else
              SEARCH_PARTIAL if tally.not_examined else SEARCH_COMPLETE)
    g0 = premises.original_target
    recorded = tuple(check for check in judged
                     if check.p1 == HOLDS or target in (check.a, check.b) or g0 in (check.a, check.b))
    forced = _forced_relations(forced_pairs, {(check.a, check.b): check for check in judged},
                               premises.unresolved)
    target_status = next(row.status for row in cells if row.cell == target)
    return PseudoDiagnosis(
        DIAGNOSIS_SCOPE, premises, target, selection_reason, kind, g0,
        (PSEUDO_RANGE, PSEUDO_ANCHOR_LIMIT, PSEUDO_CALL_LIMIT), plan.anchors, tuple(conditionals),
        recorded, tally, tuple(cells), search, plan.planned_calls, len(conditionals), target_status,
        (counts[target], total) if target_status == CELL_PROVEN else None, forced)


def diagnose_premises(premises: GuessPremises, *, actual_target, selection_reason, kind,
                      forced_pairs=()) -> PseudoDiagnosis:
    """Diagnosis of one set of premises. With declared premises this is a calculation,
    not K inference. The kernel is called once per planned anchor and never more."""
    plan = plan_pseudo(premises, actual_target)
    budget = _CallBudget()
    conditionals = tuple(_conditional(premises, cell, budget) for cell in plan.anchors)
    _require(budget.used == plan.planned_calls,
             f"{budget.used} conditional calls were made but {plan.planned_calls} were planned.",
             "PSEUDO_CALL_COUNT")
    return _assemble(plan, conditionals, selection_reason, kind, forced_pairs)


def _forced_pairs_of(selection) -> tuple:
    return tuple((proof.a, proof.b) for proof in selection.pair_proofs if proof.verdict == FORCED)


def diagnose_pseudo(selection: LookaheadSelection) -> PseudoDiagnosis | None:
    """Diagnosis of the decision behind one stage-2 selection record; None when it is no guess.

    Target, reason and kind are read from the record and copied. The record
    is not modified and nothing here authorises its input.
    """
    _require(type(selection) is LookaheadSelection, "Expected a stage-2 selection record.")
    if selection.evidence is None:
        _require(selection.premises is None, "A certainty decision has no guess premises.")
        return None
    _require(selection.premises is not None, "A guess selection needs its premises.")
    return diagnose_premises(
        selection.premises, actual_target=selection.target,
        selection_reason=selection.selection_reason, kind=selection.evidence.kind,
        forced_pairs=_forced_pairs_of(selection))


def _shape(value):
    """Exact nested types of a record, so a list, set, bool or float cannot pass as equal."""
    if is_dataclass(value) and not isinstance(value, type):
        return type(value), tuple(_shape(getattr(value, field.name)) for field in fields(value))
    if isinstance(value, (tuple, list)):
        return type(value), tuple(_shape(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return type(value), frozenset(_shape(item) for item in value)
    return type(value)


def _same(left, right) -> bool:
    return left == right and _shape(left) == _shape(right)


def validate_pseudo_diagnosis(diagnosis: PseudoDiagnosis, selection: LookaheadSelection) -> None:
    """Recheck a diagnosis against the premises of its selection record; decide nothing anew.

    Plan, cross-checks and verdicts are rebuilt from the RECORDED conditional
    counts and compared in value and exact type. The conditional counts
    themselves are trusted as recorded: NO kernel call is made here. This
    binds nothing to live state and authorises no input.
    """
    _require(type(diagnosis) is PseudoDiagnosis and type(selection) is LookaheadSelection
             and selection.evidence is not None and selection.premises is not None,
             "Expected a diagnosis and the guess selection record it belongs to.", "PSEUDO_RECORD")
    _require(_same(diagnosis.premises, selection.premises),
             "The diagnosis was made from other premises than this selection.", "PSEUDO_RECORD")
    plan = plan_pseudo(selection.premises, selection.target)
    _require(type(diagnosis.conditionals) is tuple
             and all(type(conditional) is ConditionalCounts for conditional in diagnosis.conditionals)
             and tuple(conditional.anchor for conditional in diagnosis.conditionals) == plan.anchors,
             "Conditional records must be exactly those of the planned anchors, in call order.",
             "PSEUDO_RECORD")
    for conditional in diagnosis.conditionals:
        _check_conditional(conditional, selection.premises)
    expected = _assemble(plan, diagnosis.conditionals, selection.selection_reason,
                         selection.evidence.kind, _forced_pairs_of(selection))
    _require(_same(diagnosis, expected),
             "The diagnosis disagrees with the plan, the checks or the verdicts of this decision.",
             "PSEUDO_RECORD")
