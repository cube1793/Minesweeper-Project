"""Experimental S3D2-A / PROVEN_OPENING_V1 over one K-LC1 selection.

K-LC1 stays the baseline. A HIDDEN current-safe cell whose every neighbour is
a revealed number or another current-safe cell is proven to show 0; opening it
makes the Engine flood reveal a guaranteed set. That guaranteed count lives
only in the records below. RevealPlan.reveals and KCandidate.reveal_cells keep
their meaning: one cell for an OPEN, the whole V for a CHORD.

The override reads the ORIGINAL native candidates before pruning, because a
one-reveal OPEN is pruned whenever any cheaper plan exists. It replaces the
K-LC1 choice b only by a direct OPEN whose guaranteed set covers every cell b
would reveal and whose cost per guaranteed cell is strictly lower. No
inference, candidate generation, routing, pruning or persistent cache. This
public geometry neither bounds whole-game Model C nor resolves overlap with a
CHORD that appears later. Experimental copy only.
"""

from dataclasses import dataclass
from fractions import Fraction

from core_engine import Action, CellState
from experiments.program_k_lc0_policy import route_distance
from experiments.program_k_lc1_policy import (
    SingletonSelection, select_singleton_policy, validate_singleton_selection,
)
from experiments.program_k_policy import KCandidate, KPolicyIntegrityError
from simple_algorithm import SimpleMove
from stage3_planner import RevealPlan, _final_tie_key


CANDIDATE_ID = "S3D2-A"
CANDIDATE_DEFINITION = "PROVEN_OPENING_V1"
APPLIED_CATEGORY = "PROVEN_OPENING_OPEN"
CONDITIONS = ("EXTRA_REVEAL", "COVERS_BASELINE", "GAIN")
EXACT, LOWER_BOUND = "EXACT", "LOWER_BOUND"


@dataclass(frozen=True)
class OpeningRegion:
    """One 8-connected component of ZERO_PROVEN cells and its guaranteed flood.

    Every member opens the same guaranteed set, so members are alternatives and
    the count is taken once. ``undetermined`` members may or may not show 0;
    cells beyond them are possible reveals only and are never credited.
    """

    cells: frozenset[tuple[int, int]]
    guaranteed: frozenset[tuple[int, int]]
    undetermined: frozenset[tuple[int, int]]
    bound_kind: str

    @property
    def guaranteed_count(self) -> int:
        return len(self.guaranteed)


@dataclass(frozen=True)
class GuaranteedReveal:
    """Guaranteed set of one input's directly opened cells; not a plan's R."""

    direct: frozenset[tuple[int, int]]
    guaranteed: frozenset[tuple[int, int]]
    undetermined: frozenset[tuple[int, int]]
    bound_kind: str

    @property
    def guaranteed_count(self) -> int:
        return len(self.guaranteed)


@dataclass(frozen=True)
class OpeningAssessment:
    """Projection of one region's representative original native direct OPEN.

    native_survivor and g_dominated are diagnostics, never conditions.
    gain_lhs = L_w * Rg(b) and gain_rhs = L_b * Rg(w); GAIN is lhs < rhs.
    """

    region: OpeningRegion
    candidate: KCandidate
    target: tuple[int, int]
    native_survivor: bool
    g_dominated: bool
    distance: float
    gain_lhs: int
    gain_rhs: int
    failures: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class OpeningSelection:
    """K-LC1 record, public opening diagnostics and the one authorised input.

    When nothing applies, the K-LC1 selection object itself is the choice.
    When ``applied`` is set, the input is a native direct OPEN that need not be
    a native survivor; it has no PolicySelection and needs the separate
    execution validator of the S3D2-A runner.
    """

    inner: SingletonSelection
    zero_proven: frozenset[tuple[int, int]]
    baseline_reveal: GuaranteedReveal | None
    assessments: tuple[OpeningAssessment, ...]
    applied: OpeningAssessment | None
    move: SimpleMove
    category: str
    reason: str

    @property
    def policy_id(self) -> str:
        return CANDIDATE_ID

    @property
    def policy_definition(self) -> str:
        return CANDIDATE_DEFINITION

    @property
    def override_applied(self) -> bool:
        return self.applied is not None

    @property
    def selected(self):
        """The unchanged K-LC1 PolicySelection, or None for an applied opening."""
        return None if self.applied is not None else self.inner.selected


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise KPolicyIntegrityError("PROVEN_OPENING_SELECTION", detail)


def _reading(cell):
    return cell[1], cell[0]


def _neighbors(cell, width, height):
    x, y = cell
    return tuple((nx, ny)
                 for ny in range(max(0, y - 1), min(height, y + 2))
                 for nx in range(max(0, x - 1), min(width, x + 2))
                 if (nx, ny) != cell)


def classify_safe_cells(observation, safe, mines):
    """Split current-safe cells into (ZERO_PROVEN, NONZERO_PROVEN).

    ZERO_PROVEN: every in-board neighbour is a revealed number or current-safe.
    NONZERO_PROVEN: some in-board neighbour is a current certain mine.
    The rest is undetermined. Reads at most 30 x 16 cells; infers nothing.
    """
    height, width = len(observation), len(observation[0])
    zero, nonzero = set(), set()
    for cell in safe:
        if observation[cell[1]][cell[0]] != CellState.HIDDEN:
            continue  # A current-safe cell is HIDDEN; anything else is never classified.
        around = _neighbors(cell, width, height)
        if any(other in mines for other in around):
            nonzero.add(cell)
        elif all(0 <= observation[ny][nx] <= 8
                 or (observation[ny][nx] == CellState.HIDDEN and (nx, ny) in safe)
                 for nx, ny in around):
            zero.add(cell)
    return frozenset(zero), frozenset(nonzero)


def opening_regions(observation, safe, mines):
    """Regions in reading order of their first cell; pure public geometry."""
    height, width = len(observation), len(observation[0])
    zero, nonzero = classify_safe_cells(observation, safe, mines)
    remaining, regions = set(zero), []
    while remaining:
        seed = min(remaining, key=_reading)
        remaining.remove(seed)
        cells, todo = {seed}, [seed]
        while todo:
            for other in _neighbors(todo.pop(), width, height):
                if other in remaining:
                    remaining.remove(other)
                    cells.add(other)
                    todo.append(other)
        # A ZERO_PROVEN cell's HIDDEN neighbours are current-safe by definition.
        guaranteed = set(cells)
        for cell in cells:
            guaranteed.update(other for other in _neighbors(cell, width, height)
                              if observation[other[1]][other[0]] == CellState.HIDDEN)
        undetermined = frozenset(guaranteed) - zero - nonzero
        regions.append(OpeningRegion(frozenset(cells), frozenset(guaranteed), undetermined,
                                     LOWER_BOUND if undetermined else EXACT))
    return tuple(regions), zero, nonzero


def guaranteed_reveal(direct, regions, zero, nonzero) -> GuaranteedReveal:
    """Flood credit of one input; each touched region contributes its set once."""
    guaranteed = set(direct)
    for region in regions:
        if region.cells & direct:
            guaranteed |= region.guaranteed
    guaranteed = frozenset(guaranteed)
    undetermined = guaranteed - zero - nonzero
    return GuaranteedReveal(frozenset(direct), guaranteed, undetermined,
                            LOWER_BOUND if undetermined else EXACT)


def _direct_opens(native):
    """Index the original native direct OPEN of every current-safe cell."""
    safe = native.evidence.selection_safe_cells
    width, height = len(native.evidence.observation[0]), len(native.evidence.observation)
    result = {}
    for c in native.candidates:
        _require(type(c) is KCandidate and type(c.plan) is RevealPlan
                 and type(c.plan.latency_us) is int and c.plan.latency_us > 0
                 and type(c.plan.actions) is tuple and bool(c.plan.actions)
                 and all(type(m) is SimpleMove and type(m.action) is Action
                         and type(m.x) is int and type(m.y) is int
                         and 0 <= m.x < width and 0 <= m.y < height for m in c.plan.actions)
                 and type(c.setup_cells) is frozenset and type(c.reveal_cells) is frozenset
                 and bool(c.reveal_cells) and c.reveal_cells <= safe,
                 "Malformed native candidate.")
        if c.category != "DIRECT_SAFE_OPEN":
            continue
        p = c.plan
        target = (p.actions[-1].x, p.actions[-1].y)
        _require(len(p.actions) == 1 and p.actions[0].action is Action.OPEN and not c.setup_cells
                 and p.reveals == 1 and c.reveal_cells == frozenset({target}) and target not in result,
                 "Malformed or duplicate native direct-safe OPEN.")
        result[target] = c
    _require(frozenset(result) == safe,
             "Every current safe cell needs exactly one native direct OPEN candidate.")
    return result


def _baseline(inner):
    b = inner.selected
    matches = tuple(c for c in inner.native.survivors
                    if c.plan == b.plan and c.category == b.category)
    _require(len(matches) == 1, "K-LC1 choice must identify one original survivor.")
    return matches[0]


def _rank(assessment: OpeningAssessment) -> tuple:
    p = assessment.candidate.plan
    return (Fraction(p.latency_us, assessment.region.guaranteed_count), assessment.distance,
            p.latency_us, _final_tie_key(p))


def _evaluate(inner):
    """Recompute every stored diagnostic from the K-LC1 record's current state."""
    native = inner.native
    evidence = native.evidence
    safe, mines = evidence.selection_safe_cells, evidence.after.M
    opens = _direct_opens(native)
    baseline = _baseline(inner)
    regions, zero, nonzero = opening_regions(evidence.observation, safe, mines)
    credit = guaranteed_reveal(baseline.reveal_cells, regions, zero, nonzero)
    cost_b = baseline.plan.latency_us
    projections = tuple(
        (c.plan.latency_us,
         guaranteed_reveal(c.reveal_cells, regions, zero, nonzero).guaranteed_count)
        for c in native.candidates) if regions else ()
    records = []
    for region in regions:
        w = min((opens[cell] for cell in region.cells),
                key=lambda c: (c.plan.latency_us, _final_tie_key(c.plan)))
        cost_w, count_w = w.plan.latency_us, region.guaranteed_count
        lhs, rhs = cost_w * credit.guaranteed_count, cost_b * count_w
        failures = tuple(name for name, ok in (
            ("EXTRA_REVEAL", count_w >= 2),
            ("COVERS_BASELINE", baseline.reveal_cells <= region.guaranteed),
            ("GAIN", lhs < rhs),
        ) if not ok)
        dominated = any(cost <= cost_w and count >= count_w and (cost < cost_w or count > count_w)
                        for cost, count in projections)
        records.append(OpeningAssessment(
            region, w, (w.plan.actions[-1].x, w.plan.actions[-1].y),
            any(w == s for s in native.survivors), dominated,
            route_distance(w.plan, native.cursor), lhs, rhs, failures))
    return zero, credit, tuple(records)


def apply_proven_opening(inner: SingletonSelection) -> OpeningSelection:
    """Pure projection of one validated K-LC1 record; K-LC1 is always baseline."""
    validate_singleton_selection(inner)
    kept = inner.selected
    if inner.native.continuation == "EXACT_GUESS":
        return OpeningSelection(inner, frozenset(), None, (), None, kept.move, kept.category,
                                "EXACT_GUESS_UNCHANGED")
    zero, credit, assessments = _evaluate(inner)
    eligible = tuple(a for a in assessments if a.eligible)
    if eligible:
        winner = min(eligible, key=_rank)
        return OpeningSelection(inner, zero, credit, assessments, winner,
                                winner.candidate.plan.actions[0], APPLIED_CATEGORY,
                                "PROVEN_OPENING_OVERRIDE")
    return OpeningSelection(inner, zero, credit, assessments, None, kept.move, kept.category,
                            "NO_ELIGIBLE_OPENING" if assessments else "NO_PROVEN_OPENING")


def select_opening_policy(evidence, cursor, table) -> OpeningSelection:
    """One K-LC1 selection (one native selection), then the pure projection."""
    return apply_proven_opening(select_singleton_policy(evidence, cursor, table))


def _cells(value) -> bool:
    return type(value) is frozenset and all(
        type(c) is tuple and len(c) == 2 and all(type(v) is int for v in c) for c in value)


def _immutable_region(value) -> bool:
    return (type(value) is OpeningRegion and _cells(value.cells) and _cells(value.guaranteed)
            and _cells(value.undetermined) and value.bound_kind in (EXACT, LOWER_BOUND))


def validate_opening_selection(result: OpeningSelection) -> None:
    """Recheck stored geometry/arithmetic and bindings; select nothing anew.

    The K-LC1 record is checked by its unchanged validator. This neither
    certifies K inference nor binds the record to live state; the runner does
    that immediately before the one input.
    """
    _require(type(result) is OpeningSelection, "Expected an S3D2-A selection record.")
    inner = result.inner
    validate_singleton_selection(inner)
    kept = inner.selected
    _require(type(result.move) is SimpleMove and type(result.category) is str
             and type(result.reason) is str and type(result.assessments) is tuple
             and _cells(result.zero_proven), "Malformed selection record.")
    if inner.native.continuation == "EXACT_GUESS":
        _require(not result.zero_proven and result.baseline_reveal is None
                 and not result.assessments and result.applied is None
                 and result.move == kept.move and result.category == kept.category
                 and result.reason == "EXACT_GUESS_UNCHANGED",
                 "Guess must keep the K-LC1 selection without evaluation.")
        return
    credit = result.baseline_reveal
    _require(type(credit) is GuaranteedReveal and _cells(credit.direct) and _cells(credit.guaranteed)
             and _cells(credit.undetermined) and credit.bound_kind in (EXACT, LOWER_BOUND),
             "Malformed baseline guaranteed-reveal record.")
    _require(all(type(a) is OpeningAssessment and _immutable_region(a.region)
                 and type(a.candidate) is KCandidate and type(a.target) is tuple
                 and type(a.native_survivor) is bool and type(a.g_dominated) is bool
                 and type(a.distance) is float and type(a.gain_lhs) is int
                 and type(a.gain_rhs) is int and type(a.failures) is tuple
                 for a in result.assessments), "Malformed opening assessment.")
    zero, expected_credit, expected = _evaluate(inner)
    _require(result.zero_proven == zero and credit == expected_credit
             and result.assessments == expected,
             "Opening diagnostics disagree with current state or native candidates.")
    eligible = tuple(a for a in expected if a.eligible)
    if eligible:
        winner = min(eligible, key=_rank)
        _require(type(result.applied) is OpeningAssessment and result.applied == winner
                 and result.move == winner.candidate.plan.actions[0]
                 and result.category == APPLIED_CATEGORY
                 and result.reason == "PROVEN_OPENING_OVERRIDE",
                 "Final input/category/reason violates the opening rank.")
    else:
        _require(result.applied is None and result.move == kept.move
                 and result.category == kept.category
                 and result.reason == ("NO_ELIGIBLE_OPENING" if expected else "NO_PROVEN_OPENING"),
                 "Ineligible opening must retain the K-LC1 selection.")
