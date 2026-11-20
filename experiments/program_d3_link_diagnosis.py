"""Experimental S3D3-A diagnosis only: PAIR_BUNDLE_RESOLUTION_DIAGNOSIS_V1 ("linked" resolution).

On an EXACT_GUESS decision the accepted pair judgement lists two-cell pairs
(FORCED_5050, APPARENT_5050). Here

  * a BUNDLE is the closure of "two listed pairs share a cell"; one bundle is
    one binary unknown written several times, so its pairs are resolved
    together or not at all;
  * SHARE (two pairs and their common cell) and the directed LINK (a cell of
    pair P is an unresolved distinguishing cell of pair Q) are kept apart, and
    only SHARE builds bundles;
  * for a few ANCHOR cells g (the actual target, the original target when it
    differs, then cells that link into ANOTHER bundle; at most 6 cells and 54
    calls) every number k = m..m+u of g is one exact call on the detached grid
    in which only g shows k. Z(g,k) and every Z_c(g,k) over exactly U - {g}
    are kept, also for cells of no pair;
  * a bundle that does not contain g is RESOLVED in an outcome when all of its
    cells are certain there. A number 0 that would flood and leaves a bundle
    open is FLOOD_NOT_DETERMINED: the real Engine would reveal more than this
    hypothesis, so nothing is claimed.

The fractions R/S and R/Z say how often surviving this one input also settles
that bundle. They are no win rate, are never multiplied across bundles, and
"not resolved" is no proof of independence. A certain cell is still closed;
nothing here opens, flags or adds it to M.

This module SELECTS NOTHING. Target, original target and reason are copied
from the selection record; no result flows back into a selection, a category
or a loss classification. It adds no record format, storage or reader and
changes no existing type. All additional exact calls leave through ``_kernel``;
plan, numbers and call order are fixed before the first call, the 55th call is
refused before it is made, one answer per (cell, number) serves every pair and
bundle, and nothing is kept for a later decision. A failed check or call is an
error and never becomes "not examined", "out of scope" or "no link".
Validation rebuilds everything from the recorded counts and never calls the
kernel; it is no independent recomputation. Experimental copy only.
"""

from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction

from core_engine import CellState
from experiments.program_d3_forced_pair_policy import (
    PROVEN_MINE, UNRESOLVED_HIDDEN, PairProof, pair_proofs_for_state,
)
from experiments.program_d3_lookahead_policy import (
    FORCED_FIRST, KEPT, TIE_LOOKAHEAD, GuessPremises, LookaheadSelection, LookaheadValue, Outcome,
    hypothetical_observation,
)
from experiments.program_k_capability import reading_order
from experiments.program_k_policy import KPolicyIntegrityError
from simple_algorithm import InconsistentObservationError


DIAGNOSIS_SCOPE = "PAIR_BUNDLE_RESOLUTION_DIAGNOSIS_V1"
LINK_ANCHOR_LIMIT = 6
LINK_CALL_LIMIT = 54  # additional exact calls of one decision; the limits 72 (look-ahead) and 8 (pseudo) are separate
SOURCE_RECORD, SOURCE_DECLARED = "K_DECISION_RECORD", "DECLARED_PREMISES"
PLANNED, NO_OTHER_BUNDLE, NO_LISTED_PAIR, UNSUPPORTED = (
    "PLANNED", "NO_OTHER_BUNDLE", "NO_LISTED_PAIR", "UNSUPPORTED")
ROLE_ACTUAL, ROLE_ORIGINAL, ROLE_CROSS, ROLE_EXAMINED = (
    "ACTUAL_TARGET", "ORIGINAL_TARGET", "CROSS_BUNDLE_LINK", "EXAMINED_CELL")
OUT_IN_BUNDLE, OUT_NON_PAIR = "IN_BUNDLE_LINK_ONLY", "NON_PAIR_DISTINGUISHING_CELL"
RESOLVED, UNRESOLVED_ISOLATED, UNRESOLVED_OTHER, FLOOD_NOT_DETERMINED = (
    "RESOLVED", "UNRESOLVED_ISOLATED", "UNRESOLVED_OTHER", "FLOOD_NOT_DETERMINED")
RESOLVED_ALL, RESOLVED_SOME, RESOLVED_SOME_FLOOD_OPEN, NOT_RESOLVED_EXAMINED, UNDETERMINED_FLOOD = (
    "RESOLVED_ALL", "RESOLVED_SOME", "RESOLVED_SOME_FLOOD_OPEN", "NOT_RESOLVED_EXAMINED", "UNDETERMINED_FLOOD")
SUMMARY_LABELS = (RESOLVED_ALL, RESOLVED_SOME, RESOLVED_SOME_FLOOD_OPEN, NOT_RESOLVED_EXAMINED, UNDETERMINED_FLOOD)
LINKED_ALL, LINKED_SOME, UNDETERMINED, NOT_OBSERVED, NOT_APPLICABLE = (
    "LINKED_ALL", "LINKED_SOME", "UNDETERMINED", "NOT_OBSERVED", "NOT_APPLICABLE")
SELECTION_REASONS = (FORCED_FIRST, TIE_LOOKAHEAD, KEPT)


@dataclass(frozen=True)
class LinkPair:
    """One listed pair in normal order (a before b in reading order) and the number of its bundle."""

    a: tuple
    b: tuple
    verdict: str
    distinguishing: tuple
    bundle: int


@dataclass(frozen=True)
class LinkBundle:
    """Pairs joined by shared cells. ``cells`` (reading order) identify the bundle; ``pairs`` are pair numbers."""

    cells: tuple
    pairs: tuple


@dataclass(frozen=True)
class LinkRelation:
    """Directed LINK: ``cells`` of pair ``source`` are unresolved distinguishing cells of pair ``target``."""

    source: int
    target: int
    cells: tuple
    same_bundle: bool


@dataclass(frozen=True)
class LinkAnchor:
    cell: tuple
    role: str
    mine_neighbors: int
    unresolved_neighbors: int
    calls: int


@dataclass(frozen=True)
class LinkPlan:
    """Everything fixed before the first call. ``calls`` is the call order as (cell, number).

    ``not_examined_limit`` are link cells left out by the anchor limit; ``out_of_scope`` are (cell, reason)
    for cells the first support does not use as anchors. Neither means "no link".
    """

    status: str
    pairs: tuple
    bundles: tuple
    shares: tuple
    links: tuple
    anchors: tuple
    calls: tuple
    planned_calls: int
    not_examined_limit: tuple
    out_of_scope: tuple


@dataclass(frozen=True)
class LinkOutcome:
    """One number k of one opened cell g. ``worlds`` is Z(g,k); 0 is the impossible number.

    ``mine_worlds`` are (cell, Z_c(g,k)) over exactly U - {g} in reading order, cells of no pair included.
    The impossible number has ONE form: no counts, no certain cells, no minimum.
    """

    number: int
    worlds: int
    flood: bool
    mine_worlds: tuple
    safe_cells: tuple
    mine_cells: tuple
    minimum_mine_worlds: int | None


@dataclass(frozen=True)
class OutcomeTally:
    """Units kept apart for one surviving outcome; the opened cell itself is in none of them."""

    number: int
    certain_cells: int
    certain_pair_cells: int
    certain_other_cells: int
    resolved_pairs: int
    resolved_bundles: int
    all_cells_certain: bool


@dataclass(frozen=True)
class LinkCandidate:
    """Every number outcome of one opened cell; ``own_bundle`` is its bundle number or None."""

    cell: tuple
    role: str
    mine_worlds: int
    total_worlds: int
    mine_neighbors: int
    unresolved_neighbors: int
    own_bundle: int | None
    outcomes: tuple
    tallies: tuple
    calls: int


@dataclass(frozen=True)
class BundleResult:
    """One bundle that does not contain the opened cell. R + N + F = S = Z - Z_g; fractions are R/S and R/Z."""

    anchor: tuple
    bundle: int
    per_outcome: tuple
    resolved_worlds: int
    unresolved_worlds: int
    flood_undetermined_worlds: int
    survival_worlds: int
    label: str
    conditional: Fraction
    unconditional: Fraction


@dataclass(frozen=True)
class CellExamination:
    """Outcomes and bundle results of ONE named cell, planned or not. Used by no selection and no runner."""

    candidate: LinkCandidate
    results: tuple


@dataclass(frozen=True)
class LinkDiagnosis:
    """Diagnosis of one EXACT_GUESS decision, made before its input. It authorises nothing.

    ``actual_target``, ``original_target`` and ``selection_reason`` are copied from the selection record.
    ``premise_source`` says whether the premises come from a K decision record or were declared.
    ``target_label`` describes the actual target only and is no selection condition.
    """

    scope: str
    premise_source: str
    premises: GuessPremises
    actual_target: tuple
    original_target: tuple
    selection_reason: str
    limits: tuple
    plan: LinkPlan
    candidates: tuple
    results: tuple
    target_label: str
    planned_calls: int
    actual_calls: int
    lookahead_checked: tuple


def _require(condition: bool, detail: str, code: str = "LINK_PREMISES") -> None:
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


class _ExactType:
    """One type object for comparison: equal to another ``_ExactType`` only when both hold the SAME type.

    Identity alone decides; no ``__eq__`` of a type, no name and no text is consulted (the principle of
    the accepted record type fix).
    """

    __slots__ = ("kind",)

    def __init__(self, kind):
        self.kind = kind

    def __eq__(self, other):
        return type(other) is _ExactType and self.kind is other.kind

    __hash__ = None


def _shape(value, premises=None):
    """Exact nested types, so a list, a bool or a float cannot pass as an equal tuple or integer.

    ``premises`` is the one premises object both sides must hold: it is compared by identity, not by shape.
    """
    if premises is not None and value is premises:
        return "PREMISES"
    if is_dataclass(value) and not isinstance(value, type):
        return _ExactType(type(value)), tuple(_shape(getattr(value, field.name), premises) for field in fields(value))
    if isinstance(value, (tuple, list)):
        return _ExactType(type(value)), tuple(_shape(item, premises) for item in value)
    return _ExactType(type(value))


def _same(left, right, premises=None) -> bool:
    return left == right and _shape(left, premises) == _shape(right, premises)


def _kernel(observation, num_mines):
    """The one seam through which the exact calls of this module leave."""
    from simple_probability import calculate_probabilities
    return calculate_probabilities(observation, num_mines)


class _CallBudget:
    """Counts the linked calls of one decision; checked before each call."""

    __slots__ = ("used",)

    def __init__(self):
        self.used = 0

    def spend(self) -> None:
        _require(self.used < LINK_CALL_LIMIT,
                 f"Linked call {self.used + 1} would exceed the limit of {LINK_CALL_LIMIT}.", "LINK_CALL_LIMIT")
        self.used += 1


def _check_premises(premises) -> None:
    """Public premises of one guess decision: grid, accounting, exact counts, exact types."""
    _require(type(premises) is GuessPremises, "Expected the premises of one guess decision.")
    grid = premises.observation
    _require(type(grid) is tuple and bool(grid) and all(
        type(row) is tuple and bool(row) and len(row) == len(grid[0])
        and all(type(v) is int and (v == CellState.HIDDEN or v == CellState.FLAGGED or 0 <= v <= 8) for v in row)
        for row in grid), "Premises need a detached rectangular public grid of exact integers.")
    width, height = len(grid[0]), len(grid)

    def inside(cell):
        return _is_cell(cell) and 0 <= cell[0] < width and 0 <= cell[1] < height

    hidden = frozenset((x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v == CellState.HIDDEN)
    flags = frozenset((x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v == CellState.FLAGGED)
    _require(type(premises.num_mines) is int and type(premises.mines) is frozenset
             and type(premises.unresolved) is frozenset
             and all(inside(cell) for cell in premises.mines) and all(inside(cell) for cell in premises.unresolved),
             "Premises need an integer mine total and frozen sets of exact cells.")
    # A flag is a mine only through M; a hidden cell is in M or unresolved.
    _require(flags <= premises.mines and premises.mines <= flags | hidden
             and premises.unresolved == hidden - premises.mines and bool(premises.unresolved),
             "The grid disagrees with the current M / unresolved accounting.")
    budget = premises.num_mines - len(premises.mines)
    _require(1 <= budget <= len(premises.unresolved), "Invalid remaining mine budget.")
    counts, total = premises.mine_worlds, premises.total_worlds
    _require(type(total) is int and total > 0 and type(counts) is tuple
             and all(type(item) is tuple and len(item) == 2 and _is_cell(item[0]) and type(item[1]) is int
                     for item in counts)
             and tuple(cell for cell, _ in counts) == tuple(sorted(premises.unresolved, key=reading_order)),
             "Exact counts must be exact integers over exactly the unresolved cells, in reading order.")
    _require(all(0 < count < total for _, count in counts), "A guess decision has only strictly uncertain cells.")
    _require(sum(count for _, count in counts) == budget * total,
             "The exact counts do not add up to the remaining mines of every world.", "LINK_WORLD_COUNT")
    _require(inside(premises.original_target) and premises.original_target in premises.unresolved
             and inside(premises.cursor), "Premises need the original target among the unresolved cells and a cursor.")


def _check_target(premises, cell) -> None:
    _require(_is_cell(cell) and cell in premises.unresolved, "The opened cell must be an exact unresolved cell.")


def _check_reason(premises, actual_target, selection_reason) -> None:
    """The copied reason is one of the three existing ones and agrees with "the target changed"."""
    _require(type(selection_reason) is str and selection_reason in SELECTION_REASONS,
             "The copied selection reason is none of the existing reasons.")
    changed = actual_target != premises.original_target
    _require(not (selection_reason == KEPT and changed) and not (selection_reason == TIE_LOOKAHEAD and not changed),
             "The copied selection reason disagrees with the actual and the original target.")


def _geometry(premises, cell):
    """(m, u): certain-mine and unresolved neighbours of one cell."""
    grid = premises.observation
    around = _around(cell, len(grid[0]), len(grid))
    return len(around & premises.mines), len(around & premises.unresolved)


def _normal_proofs(premises, pair_proofs) -> tuple:
    """The input pairs in the fixed order of the accepted judgement; the input order means nothing.

    The same normal pair twice is an error. Two different pairs sharing a cell are normal and are not
    checked here. Each pair must be, in value and exact type, the accepted judgement of this very state.
    """
    _require(type(pair_proofs) is tuple and all(type(proof) is PairProof for proof in pair_proofs),
             "Expected a tuple of pair judgements.", "LINK_PAIR_INPUT")
    _require(all(_is_cell(proof.a) and _is_cell(proof.b) for proof in pair_proofs),
             "A pair needs two exact cells.", "LINK_PAIR_INPUT")
    keys = [tuple(sorted((proof.a, proof.b), key=reading_order)) for proof in pair_proofs]
    _require(len(set(keys)) == len(keys), "The same pair is listed twice.", "LINK_PAIR_DUPLICATE")
    expected = pair_proofs_for_state(premises.observation, premises.mines, premises.num_mines, premises)
    by_key = {(proof.a, proof.b): proof for proof in expected}
    _require(len(pair_proofs) == len(expected)
             and all((proof.a, proof.b) in by_key and _same(proof, by_key[(proof.a, proof.b)])
                     for proof in pair_proofs),
             "The pairs are not the accepted judgement of this state.", "LINK_PAIR_INPUT")
    return expected


def _structure(premises, pair_proofs) -> tuple:
    """(pairs, bundles, shares, links) in their fixed order. Geometry only; no call."""
    proofs = _normal_proofs(premises, pair_proofs)
    cells = [(proof.a, proof.b) for proof in proofs]
    group = list(range(len(proofs)))

    def find(index):
        while group[index] != index:
            index = group[index]
        return index

    shares = []
    for i in range(len(proofs)):
        for j in range(i + 1, len(proofs)):
            common = sorted(set(cells[i]) & set(cells[j]), key=reading_order)
            if common:
                _require(len(common) == 1, "Two different pairs cannot share both cells.", "LINK_PAIR_INPUT")
                shares.append((i, j, common[0]))
                group[find(j)] = find(i)
    members = {}
    for index in range(len(proofs)):
        members.setdefault(find(index), []).append(index)
    ordered = sorted(members.values(), key=lambda ids: min(reading_order(cell) for i in ids for cell in cells[i]))
    bundles = tuple(LinkBundle(tuple(sorted({cell for i in ids for cell in cells[i]}, key=reading_order)), tuple(ids))
                    for ids in ordered)
    bundle_of_pair = {i: number for number, bundle in enumerate(bundles) for i in bundle.pairs}
    pairs = tuple(LinkPair(proof.a, proof.b, proof.verdict, proof.distinguishing, bundle_of_pair[i])
                  for i, proof in enumerate(proofs))
    links = []
    for i in range(len(pairs)):
        for j in range(len(pairs)):
            if i != j:
                open_cells = {cell for cell, state in pairs[j].distinguishing if state == UNRESOLVED_HIDDEN}
                through = tuple(sorted(set(cells[i]) & open_cells, key=reading_order))
                if through:
                    links.append(LinkRelation(i, j, through, pairs[i].bundle == pairs[j].bundle))
    return pairs, bundles, tuple(shares), tuple(links)


def plan_links(premises: GuessPremises, pair_proofs, actual_target) -> LinkPlan:
    """Bundles, SHARE and LINK relations, anchors, their numbers and the call order. No call is made.

    Anchor order: the actual target, the original target when it differs, then the cells that link into
    another bundle (fewer mine worlds first, then reading order). A cell is an anchor only when some
    bundle does not contain it; a cell is planned once and keeps its first role.
    """
    _check_premises(premises)
    _check_target(premises, actual_target)
    pairs, bundles, shares, links = _structure(premises, pair_proofs)
    counts = dict(premises.mine_worlds)
    in_bundle = {cell for bundle in bundles for cell in bundle.cells}
    cross = {cell for link in links if not link.same_bundle for cell in link.cells}
    inner_only = {cell for link in links if link.same_bundle for cell in link.cells} - cross
    outside = {cell for pair in pairs for cell, state in pair.distinguishing
               if state == UNRESOLVED_HIDDEN} - in_bundle
    original = premises.original_target
    wanted = [(actual_target, ROLE_ACTUAL)] + ([(original, ROLE_ORIGINAL)] if original != actual_target else [])
    wanted += [(cell, ROLE_CROSS) for cell in sorted(cross, key=lambda c: (counts[c], *reading_order(c)))]
    chosen, late, seen = [], [], set()
    for cell, role in wanted:
        if cell in seen or not any(cell not in bundle.cells for bundle in bundles):
            continue
        seen.add(cell)
        (chosen if len(chosen) < LINK_ANCHOR_LIMIT else late).append((cell, role))
    anchors = []
    for cell, role in chosen:
        mine_neighbors, unresolved_neighbors = _geometry(premises, cell)
        anchors.append(LinkAnchor(cell, role, mine_neighbors, unresolved_neighbors, unresolved_neighbors + 1))
    calls = tuple((anchor.cell, number) for anchor in anchors
                  for number in range(anchor.mine_neighbors, anchor.mine_neighbors + anchor.unresolved_neighbors + 1))
    planned = sum(anchor.calls for anchor in anchors)
    _require(planned == len(calls) and planned <= LINK_CALL_LIMIT,
             f"{planned} planned linked calls exceed the limit of {LINK_CALL_LIMIT}.", "LINK_CALL_LIMIT")
    out = [(cell, OUT_IN_BUNDLE) for cell in inner_only - seen] + [(cell, OUT_NON_PAIR) for cell in outside - seen]
    status = PLANNED if anchors else NO_OTHER_BUNDLE if pairs else NO_LISTED_PAIR
    return LinkPlan(status, pairs, bundles, shares, links, tuple(anchors), calls, planned,
                    tuple(cell for cell, _ in late), tuple(sorted(out, key=lambda item: reading_order(item[0]))))


def _outcome_from_counts(number, worlds, unresolved_neighbors, rows) -> LinkOutcome:
    """The record of a surviving number from its counts: certain cells and the minimum are derived, never given."""
    return LinkOutcome(number, worlds, number == 0 and unresolved_neighbors > 0, rows,
                       tuple(cell for cell, count in rows if count == 0),
                       tuple(cell for cell, count in rows if count == worlds),
                       min((count for _, count in rows), default=None))


def _impossible(number, unresolved_neighbors) -> LinkOutcome:
    """The one normal form of a number no world has: Z = 0 and nothing invented."""
    return LinkOutcome(number, 0, number == 0 and unresolved_neighbors > 0, (), (), (), None)


def _read_kernel(result, premises, cell, number, unresolved_neighbors) -> LinkOutcome:
    """One kernel answer as exact integers over exactly U - {cell}; anything else is an error."""
    total = getattr(result, "total_worlds", None)
    _require(type(total) is int and total > 0, "A conditional world count must be a positive exact integer.",
             "LINK_KERNEL_RESULT")
    remaining = premises.unresolved - {cell}
    counts = {}
    for item in getattr(result, "probabilities", ()):
        other = getattr(item, "coordinate", None)
        _require(_is_cell(other) and other in remaining and other not in counts
                 and type(getattr(item, "mine_worlds", None)) is int and 0 <= item.mine_worlds <= total
                 and type(getattr(item, "total_worlds", None)) is int and item.total_worlds == total,
                 "Invalid, duplicate or foreign conditional marginal.", "LINK_KERNEL_RESULT")
        counts[other] = item.mine_worlds
    _require(counts.keys() == remaining, "The answer does not cover exactly the other unresolved cells.",
             "LINK_KERNEL_RESULT")
    return _outcome_from_counts(number, total, unresolved_neighbors,
                                tuple((other, counts[other]) for other in sorted(counts, key=reading_order)))


def _call(premises, cell, number, unresolved_neighbors, budget) -> LinkOutcome:
    """One exact call: only ``cell`` shows ``number``. Only "no world" becomes the impossible number."""
    grid = hypothetical_observation(premises.observation, premises.mines, cell, number)
    budget.spend()  # immediately before the call: a call over the limit never leaves
    try:
        result = _kernel(grid, premises.num_mines)
    except InconsistentObservationError:
        return _impossible(number, unresolved_neighbors)
    return _read_kernel(result, premises, cell, number, unresolved_neighbors)


def _check_outcome(outcome, premises, cell, number, unresolved_neighbors, pairs) -> None:
    """Shape, exact types and every integer relation of one recorded outcome. No call."""
    _require(type(outcome) is LinkOutcome and type(outcome.number) is int and outcome.number == number
             and type(outcome.worlds) is int and outcome.worlds >= 0 and type(outcome.flood) is bool
             and outcome.flood == (number == 0 and unresolved_neighbors > 0)
             and type(outcome.mine_worlds) is tuple and type(outcome.safe_cells) is tuple
             and type(outcome.mine_cells) is tuple,
             f"Malformed outcome of the number {number} of {cell}.", "LINK_RECORD")
    if outcome.worlds == 0:
        _require(outcome.mine_worlds == () and outcome.safe_cells == () and outcome.mine_cells == ()
                 and outcome.minimum_mine_worlds is None,
                 "An impossible number has one normal form and no counts.", "LINK_RECORD")
        return
    rows, worlds = outcome.mine_worlds, outcome.worlds
    _require(all(type(row) is tuple and len(row) == 2 and _is_cell(row[0]) and type(row[1]) is int for row in rows)
             and tuple(row[0] for row in rows) == tuple(sorted(premises.unresolved - {cell}, key=reading_order)),
             "Counts must be exact integers over exactly the other unresolved cells, in reading order.",
             "LINK_RECORD")
    marginal, total = dict(premises.mine_worlds), premises.total_worlds
    _require(worlds <= total - marginal[cell]
             and all(0 <= count <= worlds and count <= marginal[other] for other, count in rows),
             "A conditional count exceeds its world count or its marginal count.", "LINK_WORLD_COUNT")
    _require(sum(count for _, count in rows) == (premises.num_mines - len(premises.mines)) * worlds,
             "Conditional counts do not add up to the remaining mines of every world.", "LINK_WORLD_COUNT")
    _require(_same(outcome, _outcome_from_counts(number, worlds, unresolved_neighbors, rows)),
             "Certain cells or the minimum disagree with the counts.", "LINK_RECORD")
    counts = dict(rows)
    for pair in pairs:
        if cell in (pair.a, pair.b):
            other = pair.b if cell == pair.a else pair.a
            _require(counts[other] == worlds, f"The partner of {cell} in a listed pair is not a certain mine.",
                     "LINK_WORLD_COUNT")
        else:
            _require(counts[pair.a] + counts[pair.b] == worlds,
                     f"The listed pair {(pair.a, pair.b)} is not exactly one mine in every world.",
                     "LINK_WORLD_COUNT")


def _candidate(premises, structure, cell, role, outcomes) -> LinkCandidate:
    """One opened cell from its recorded outcomes: checks, own bundle and the tallies. No call."""
    pairs, bundles = structure[0], structure[1]
    mine_neighbors, unresolved_neighbors = _geometry(premises, cell)
    numbers = tuple(range(mine_neighbors, mine_neighbors + unresolved_neighbors + 1))
    _require(type(outcomes) is tuple and len(outcomes) == len(numbers),
             f"Number outcomes of {cell} are missing or repeated.", "LINK_RECORD")
    for number, outcome in zip(numbers, outcomes):
        _check_outcome(outcome, premises, cell, number, unresolved_neighbors, pairs)
    counts, total = dict(premises.mine_worlds), premises.total_worlds
    _require(sum(outcome.worlds for outcome in outcomes) == total - counts[cell],
             f"Number outcomes of {cell} do not add up to its safe worlds.", "LINK_WORLD_COUNT")
    own = next((number for number, bundle in enumerate(bundles) if cell in bundle.cells), None)
    pair_cells = {other for bundle in bundles for other in bundle.cells}
    tallies = []
    for outcome in outcomes:
        if outcome.worlds == 0:
            continue
        certain = set(outcome.safe_cells) | set(outcome.mine_cells)
        pair_done = [all(other in certain for other in (pair.a, pair.b) if other != cell) for pair in pairs]
        bundle_done = [all(other in certain for other in bundle.cells if other != cell) for bundle in bundles]
        for number, bundle in enumerate(bundles):
            _require(len({pair_done[i] for i in bundle.pairs}) == 1
                     and bundle_done[number] == pair_done[bundle.pairs[0]],
                     "The pairs of one bundle are not resolved together.", "LINK_WORLD_COUNT")
        _require(own is None or bundle_done[own], "The own bundle of the opened cell is not settled.",
                 "LINK_WORLD_COUNT")
        tallies.append(OutcomeTally(outcome.number, len(certain), len(certain & pair_cells),
                                    len(certain - pair_cells), sum(pair_done), sum(bundle_done),
                                    len(certain) == len(outcome.mine_worlds)))
    return LinkCandidate(cell, role, counts[cell], total, mine_neighbors, unresolved_neighbors, own, outcomes,
                         tuple(tallies), len(outcomes))


def summary_label(resolved_worlds, unresolved_worlds, flood_worlds) -> str:
    """The summary of one bundle over the surviving outcomes of one opened cell: R, N, F with R + N + F > 0."""
    values = (resolved_worlds, unresolved_worlds, flood_worlds)
    _require(all(type(value) is int and value >= 0 for value in values) and sum(values) > 0,
             "A summary needs exact non-negative world counts of a cell that can be survived.", "LINK_WORLD_COUNT")
    if unresolved_worlds == 0 and flood_worlds == 0:
        return RESOLVED_ALL
    if resolved_worlds > 0 and unresolved_worlds > 0:
        return RESOLVED_SOME
    if resolved_worlds > 0:
        return RESOLVED_SOME_FLOOD_OPEN
    return NOT_RESOLVED_EXAMINED if flood_worlds == 0 else UNDETERMINED_FLOOD


def target_label(labels) -> str:
    """The label of the actual target from the summary labels of ITS bundle results; () when it is no anchor."""
    _require(type(labels) is tuple and all(type(label) is str and label in SUMMARY_LABELS for label in labels),
             "Expected the summary labels of the actual target.", "LINK_RECORD")
    if not labels:
        return NOT_APPLICABLE
    if RESOLVED_ALL in labels:
        return LINKED_ALL
    if RESOLVED_SOME in labels or RESOLVED_SOME_FLOOD_OPEN in labels:
        return LINKED_SOME
    return UNDETERMINED if UNDETERMINED_FLOOD in labels else NOT_OBSERVED


def _bundle_results(premises, structure, candidate) -> tuple:
    """Every bundle that does not contain the opened cell, in bundle order. Integer comparisons only."""
    pairs, bundles = structure[0], structure[1]
    cell, total = candidate.cell, premises.total_worlds
    survival = total - candidate.mine_worlds
    rows = []
    for number, bundle in enumerate(bundles):
        if cell in bundle.cells:
            continue
        per, resolved, unresolved, flooded = [], 0, 0, 0
        for outcome in candidate.outcomes:
            worlds = outcome.worlds
            if worlds == 0:
                continue  # an impossible number has no status and no share
            counts = dict(outcome.mine_worlds)
            if all(counts[other] in (0, worlds) for other in bundle.cells):
                status, resolved = RESOLVED, resolved + worlds
            elif outcome.flood:
                # The real Engine would reveal more than this hypothesis: nothing is claimed.
                status, flooded = FLOOD_NOT_DETERMINED, flooded + worlds
            else:
                unresolved += worlds
                alone = len(bundle.pairs) == 1 and all(
                    other != cell and (state == PROVEN_MINE
                                       or (state == UNRESOLVED_HIDDEN and counts[other] == worlds))
                    for other, state in pairs[bundle.pairs[0]].distinguishing)
                status = UNRESOLVED_ISOLATED if alone else UNRESOLVED_OTHER
            per.append((outcome.number, status))
        _require(resolved + unresolved + flooded == survival,
                 f"The outcomes of {cell} do not add up to its safe worlds.", "LINK_WORLD_COUNT")
        rows.append(BundleResult(cell, number, tuple(per), resolved, unresolved, flooded, survival,
                                 summary_label(resolved, unresolved, flooded),
                                 Fraction(resolved, survival), Fraction(resolved, total)))
    return tuple(rows)


def _lookahead_table(lookaheads) -> dict:
    """{cell: existing look-ahead value}; the values are only compared with, never changed or reused."""
    _require(type(lookaheads) is tuple and all(type(value) is LookaheadValue for value in lookaheads),
             "Expected the existing look-ahead values of this decision.")
    table = {}
    for value in lookaheads:
        _require(_is_cell(value.cell) and value.cell not in table, "Look-ahead values need distinct exact cells.")
        table[value.cell] = value
    return table


def _check_lookaheads(candidates, lookaheads) -> tuple:
    """Cells whose linked outcomes were compared with the existing look-ahead value of the same cell."""
    table, checked = _lookahead_table(lookaheads), []
    for candidate in candidates:
        value = table.get(candidate.cell)
        if value is None:
            continue
        _require(value.mine_worlds == candidate.mine_worlds and value.total_worlds == candidate.total_worlds
                 and value.mine_neighbors == candidate.mine_neighbors
                 and value.unresolved_neighbors == candidate.unresolved_neighbors
                 and type(value.outcomes) is tuple and len(value.outcomes) == len(candidate.outcomes)
                 and all(type(old) is Outcome and old.number == new.number and old.worlds == new.worlds
                         and old.flood == new.flood and old.minimum_mine_worlds == new.minimum_mine_worlds
                         and old.safe_cells == len(new.safe_cells)
                         for old, new in zip(value.outcomes, candidate.outcomes)),
                 f"The look-ahead value of {candidate.cell} disagrees with the linked outcomes.",
                 "LINK_LOOKAHEAD_MISMATCH")
        checked.append(candidate.cell)
    return tuple(checked)


def _assemble(premises, plan, recorded, actual_target, selection_reason, source, lookaheads) -> LinkDiagnosis:
    """The whole record from the plan and the recorded outcomes; pure arithmetic, no kernel call."""
    structure = (plan.pairs, plan.bundles, plan.shares, plan.links)
    _require(type(recorded) is tuple and len(recorded) == len(plan.anchors),
             "Outcomes must be exactly those of the planned anchors, in call order.", "LINK_CALL_COUNT")
    candidates = tuple(_candidate(premises, structure, anchor.cell, anchor.role, outcomes)
                       for anchor, outcomes in zip(plan.anchors, recorded))
    results = tuple(row for candidate in candidates for row in _bundle_results(premises, structure, candidate))
    actual_calls = sum(candidate.calls for candidate in candidates)
    _require(actual_calls == plan.planned_calls and actual_calls <= LINK_CALL_LIMIT,
             f"{actual_calls} linked calls were made but {plan.planned_calls} were planned.", "LINK_CALL_COUNT")
    label = target_label(tuple(row.label for row in results if row.anchor == actual_target))
    return LinkDiagnosis(DIAGNOSIS_SCOPE, source, premises, actual_target, premises.original_target,
                         selection_reason, (LINK_ANCHOR_LIMIT, LINK_CALL_LIMIT), plan, candidates, results, label,
                         plan.planned_calls, actual_calls, _check_lookaheads(candidates, lookaheads))


def _diagnose(premises, pair_proofs, actual_target, selection_reason, lookaheads, source) -> LinkDiagnosis:
    plan = plan_links(premises, pair_proofs, actual_target)
    _check_reason(premises, actual_target, selection_reason)
    _lookahead_table(lookaheads)
    # Anchors, numbers and the call order are fixed in the plan; from here on only planned calls leave.
    budget = _CallBudget()
    neighbours = {anchor.cell: anchor.unresolved_neighbors for anchor in plan.anchors}
    rows = {anchor.cell: [] for anchor in plan.anchors}
    for cell, number in plan.calls:
        rows[cell].append(_call(premises, cell, number, neighbours[cell], budget))
    _require(budget.used == plan.planned_calls,
             f"{budget.used} linked calls were made but {plan.planned_calls} were planned.", "LINK_CALL_COUNT")
    return _assemble(premises, plan, tuple(tuple(rows[anchor.cell]) for anchor in plan.anchors), actual_target,
                     selection_reason, source, lookaheads)


def diagnose_premises_links(premises: GuessPremises, pair_proofs, *, actual_target, selection_reason,
                            lookaheads=()) -> LinkDiagnosis:
    """Diagnosis of one set of DECLARED premises: a calculation, not K inference. The kernel is called
    once per planned (cell, number) and never more."""
    return _diagnose(premises, pair_proofs, actual_target, selection_reason, lookaheads, SOURCE_DECLARED)


def diagnose_links(selection: LookaheadSelection) -> LinkDiagnosis | None:
    """Diagnosis of the decision behind one stage-2 selection record; None when it is no guess.

    Premises, pairs, target, reason and look-ahead values are read from the record. The record is not
    modified and nothing here authorises its input.
    """
    _require(type(selection) is LookaheadSelection, "Expected a stage-2 selection record.")
    if selection.evidence is None:
        _require(selection.premises is None, "A certainty decision has no guess premises.")
        return None
    _require(selection.premises is not None, "A guess selection needs its premises.")
    return _diagnose(selection.premises, selection.pair_proofs, selection.target, selection.selection_reason,
                     selection.lookaheads, SOURCE_RECORD if selection.inner is not None else SOURCE_DECLARED)


def examine_cell(premises: GuessPremises, pair_proofs, cell) -> CellExamination:
    """Every number outcome of ONE unresolved cell and its bundle results, whether an anchor or not.

    u + 1 calls through the same seam, fixed before the first one. With declared premises this is a
    calculation, not K inference. No selection and no runner uses it.
    """
    _check_premises(premises)
    _check_target(premises, cell)
    structure = _structure(premises, pair_proofs)
    mine_neighbors, unresolved_neighbors = _geometry(premises, cell)
    numbers = tuple(range(mine_neighbors, mine_neighbors + unresolved_neighbors + 1))
    budget = _CallBudget()
    outcomes = tuple(_call(premises, cell, number, unresolved_neighbors, budget) for number in numbers)
    _require(budget.used == len(numbers), f"{budget.used} linked calls were made but {len(numbers)} were planned.",
             "LINK_CALL_COUNT")
    candidate = _candidate(premises, structure, cell, ROLE_EXAMINED, outcomes)
    return CellExamination(candidate, _bundle_results(premises, structure, candidate))


def validate_link_diagnosis(diagnosis: LinkDiagnosis, selection: LookaheadSelection) -> None:
    """Recheck a diagnosis against the selection record of ITS decision; decide nothing anew.

    The premises must be the very object of the selection record, and target, original target and
    reason are compared with the record, never with the diagnosis itself. Plan, checks, statuses,
    summaries, tallies and the label are rebuilt from the RECORDED counts and compared in value and exact
    type. NO kernel call is made here. This binds nothing to live state and authorises no input.
    """
    _require(type(diagnosis) is LinkDiagnosis and type(selection) is LookaheadSelection
             and selection.evidence is not None and selection.premises is not None,
             "Expected a linked diagnosis and the guess selection record it belongs to.", "LINK_RECORD")
    _require(diagnosis.premises is selection.premises,
             "The diagnosis was made from the premises of another decision.", "LINK_BINDING")
    _require(_same((diagnosis.actual_target, diagnosis.original_target, diagnosis.selection_reason),
                   (selection.target, selection.original_target, selection.selection_reason)),
             "The diagnosis names another target or reason than this selection.", "LINK_BINDING")
    plan = plan_links(selection.premises, selection.pair_proofs, selection.target)
    _check_reason(selection.premises, selection.target, selection.selection_reason)
    _require(type(diagnosis.candidates) is tuple
             and all(type(candidate) is LinkCandidate and type(candidate.outcomes) is tuple
                     for candidate in diagnosis.candidates)
             and tuple(candidate.cell for candidate in diagnosis.candidates)
             == tuple(anchor.cell for anchor in plan.anchors),
             "Recorded outcomes must be exactly those of the planned anchors, in call order.", "LINK_RECORD")
    expected = _assemble(selection.premises, plan, tuple(candidate.outcomes for candidate in diagnosis.candidates),
                         selection.target, selection.selection_reason,
                         SOURCE_RECORD if selection.inner is not None else SOURCE_DECLARED, selection.lookaheads)
    _require(_same(diagnosis, expected, selection.premises),
             "The diagnosis disagrees with the plan, the checks or the summaries of this decision.", "LINK_RECORD")
