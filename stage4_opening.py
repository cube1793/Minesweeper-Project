"""Exact public-information evidence for direct OPEN candidates (Stage 4, Unit 1).

``analyze_openings(observation, num_mines, candidates, mode=..., allow_guess=...)``
accepts a rectangular grid of integers 0..8, HIDDEN (-2), and FLAGGED (-3).
Coordinates are (x, y), with deterministic (y, x) reading order. Candidate
duplicates are coalesced. Malformed inputs raise ValueError. An impossible
public position returns INCONSISTENT_INPUT. Other counting failures return
NOT_EVALUATED evidence, with a PARTIAL result when only some queries fail.

All physical flags become HIDDEN in an independent inference copy. Opened
clues and the total mine count are the only constraints. Flags remain excluded
from direct OPEN. A flagged cell can connect proven zeros only after its zero
status is independently proved (the engine's flood fill clears such flags).
The fixed-layout distribution weights every consistent complete placement
equally. It carries no first-click safety promise.

For a hidden candidate x, replace only x by a public zero in a separate grid.
Every original placement in which x and all its in-board neighbors are safe
satisfies this grid. Conversely, every placement satisfying this grid has a
safe x and satisfies its zero clue, while retaining every original clue and
the total mine count. The unchanged mine set gives a bijection. Thus its
world count is the exact, unconditional zero numerator Z, over the original D.

Results contain no executable actions. ``admissible_candidates`` expresses
the selected risk-mode boundary. ``query_order`` prioritizes certain-zero
representatives, then opening probability, mine risk, and reading order.
This is an opening-query order. Total-cost planning, including FLAG/CHORD,
belongs to the caller's future planner. Recompute after every observation
change. The immutable identity binds physical observation, normalization
policy, total mines, candidate set, mode, and guess permission. There is no
persistent cache or accumulated inference state.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from core_engine import CellState
from simple_algorithm import Coordinate, InconsistentObservationError, Observation
from simple_probability import calculate_probabilities


SAFETY_PRESERVING = "safety_preserving"
EFFICIENCY_PRIORITIZED = "efficiency_prioritized"
NORMALIZATION_POLICY = "physical_flags_as_hidden_v1"


def _reading_order(cell: Coordinate) -> tuple[int, int]:
    return cell[1], cell[0]


@dataclass(frozen=True)
class OpeningIdentity:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    candidates: tuple[Coordinate, ...]
    mode: str
    allow_guess: bool
    normalization_policy: str = NORMALIZATION_POLICY


@dataclass(frozen=True)
class OpeningEvidence:
    coordinate: Coordinate
    status: str
    reason: str
    total_worlds: int | None = None
    mine_worlds: int | None = None
    zero_worlds: int | None = None

    def __post_init__(self):
        if self.status == "EXACT":
            counts = (self.total_worlds, self.mine_worlds, self.zero_worlds)
            if any(type(value) is not int for value in counts):
                raise ValueError("Exact world counts must be integers.")
            if not (
                self.total_worlds > 0
                and 0 <= self.zero_worlds
                <= self.total_worlds - self.mine_worlds <= self.total_worlds
            ):
                raise ValueError("Require 0 <= Z <= D - M <= D and D > 0.")

    @property
    def mine_probability(self) -> Fraction | None:
        if self.total_worlds and self.mine_worlds is not None:
            return Fraction(self.mine_worlds, self.total_worlds)
        return None

    @property
    def zero_probability(self) -> Fraction | None:
        if self.total_worlds and self.zero_worlds is not None:
            return Fraction(self.zero_worlds, self.total_worlds)
        return None

    @property
    def certain_safe(self) -> bool:
        return bool(self.total_worlds) and self.mine_worlds == 0

    @property
    def zero_status(self) -> str:
        if self.status != "EXACT":
            return self.status
        if self.zero_worlds == self.total_worlds:
            return "CERTAIN_ZERO"
        if self.zero_worlds == 0:
            return "ZERO_IMPOSSIBLE"
        return "POSSIBLE_ZERO"


@dataclass(frozen=True)
class CertainZeroGroup:
    """Proven zero component with queried members and one first choice.

    Cells can include unqueried, flagged, and already opened zeros, proved
    from the base marginals. A hypothetical zero never supplies a bridge.
    """

    cells: tuple[Coordinate, ...]
    candidate_cells: tuple[Coordinate, ...]
    representative: Coordinate


@dataclass(frozen=True)
class OpeningAnalysis:
    identity: OpeningIdentity
    status: str
    reason: str
    total_worlds: int | None
    evidence: tuple[OpeningEvidence, ...]
    omitted_direct_open: tuple[Coordinate, ...]
    global_minimum_risk: Fraction | None = None
    global_minimum_cells: tuple[Coordinate, ...] = ()
    certain_zero_groups: tuple[CertainZeroGroup, ...] = ()
    admissible_candidates: tuple[Coordinate, ...] = ()
    exploratory_candidates: tuple[Coordinate, ...] = ()
    query_order: tuple[Coordinate, ...] = ()

    @property
    def is_candidate_subset(self) -> bool:
        return bool(self.omitted_direct_open)

    @property
    def decision(self) -> str:
        return "CANDIDATES" if self.query_order else "DEFER"


def _freeze_observation(observation: Observation) -> tuple[tuple[int, ...], ...]:
    # Validate before flag normalization so, for example, float -3.0 cannot
    # silently become a valid HIDDEN integer.
    if not isinstance(observation, Sequence) or not observation:
        raise ValueError("Observation must be a nonempty rectangular grid.")
    rows = []
    width = None
    for row in observation:
        if not isinstance(row, Sequence) or not row:
            raise ValueError("Observation must have nonempty rows.")
        if width is None:
            width = len(row)
        if len(row) != width:
            raise ValueError("Observation rows must have the same width.")
        for value in row:
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or (value not in (CellState.HIDDEN, CellState.FLAGGED)
                    and not 0 <= value <= 8)
            ):
                raise ValueError("Observation contains an unsupported public value.")
        rows.append(tuple(int(value) for value in row))
    return tuple(rows)


def _freeze_candidates(
    candidates: Iterable[Coordinate], width: int, height: int,
) -> tuple[Coordinate, ...]:
    cells = set()
    try:
        for coordinate in candidates:
            x, y = coordinate
            if any(isinstance(value, bool) or not isinstance(value, int)
                   for value in (x, y)):
                raise ValueError("Candidate coordinates must be integer pairs.")
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError("Candidate coordinate is outside the observation.")
            cells.add((int(x), int(y)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Candidates must contain in-board integer (x, y) pairs.") from exc
    return tuple(sorted(cells, key=_reading_order))


def _neighborhood(cell: Coordinate, width: int, height: int) -> set[Coordinate]:
    """The in-board 3x3 neighborhood, including its center."""
    x, y = cell
    return {
        (nx, ny)
        for ny in range(max(0, y - 1), min(height, y + 2))
        for nx in range(max(0, x - 1), min(width, x + 2))
    }


def _zero_groups(identity, marginals, evidence) -> tuple[CertainZeroGroup, ...]:
    grid = identity.observation
    width, height = len(grid[0]), len(grid)
    safe = {(x, y) for y, row in enumerate(grid)
            for x, value in enumerate(row) if value >= 0}
    safe.update(cell for cell, count in marginals.items() if count == 0)
    # In a finite uniform distribution, zero marginal count for every member
    # proves that their union contains no mine. No independence is assumed.
    remaining = {
        cell for cell in safe
        if _neighborhood(cell, width, height) <= safe
    }
    queried_zeros = {item.coordinate for item in evidence
                     if item.zero_status == "CERTAIN_ZERO"}
    groups = []
    while remaining:
        first = min(remaining, key=_reading_order)
        component = {first}
        remaining.remove(first)
        pending = [first]
        while pending:
            adjacent = _neighborhood(pending.pop(), width, height) & remaining
            remaining.difference_update(adjacent)
            component.update(adjacent)
            pending.extend(sorted(adjacent, key=_reading_order))
        members = tuple(sorted(component & queried_zeros, key=_reading_order))
        if members:
            groups.append(CertainZeroGroup(
                tuple(sorted(component, key=_reading_order)), members, members[0],
            ))
    return tuple(sorted(groups, key=lambda group: _reading_order(group.representative)))


def analyze_openings(
    observation: Observation,
    num_mines: int,
    candidates: Iterable[Coordinate],
    *,
    mode: str = SAFETY_PRESERVING,
    allow_guess: bool = False,
) -> OpeningAnalysis:
    """Count exact D/M/Z and return bounded, snapshot-specific candidate evidence.

    All direct OPEN marginals are computed even when only a subset receives
    zero queries. Safety mode therefore compares with the global minimum,
    including safe cells outside the candidate set. Efficiency mode admits
    safe candidates and, when guesses are enabled, risky candidates with Z>0.
    Known mines are always deferred. Excluded physical cells receive a reason
    and no counts. Counting errors preserve any already-known D/M with Z=None.
    """
    grid = _freeze_observation(observation)
    if isinstance(num_mines, bool) or not isinstance(num_mines, int):
        raise ValueError("num_mines must be an integer.")
    if mode not in (SAFETY_PRESERVING, EFFICIENCY_PRIORITIZED):
        raise ValueError("Unsupported opening risk mode.")
    if type(allow_guess) is not bool:
        raise ValueError("allow_guess must be a bool.")
    cells = _freeze_candidates(candidates, len(grid[0]), len(grid))
    identity = OpeningIdentity(grid, int(num_mines), cells, mode, allow_guess)
    direct_open = tuple((x, y) for y, row in enumerate(grid)
                        for x, value in enumerate(row) if value == CellState.HIDDEN)
    requested = set(cells)
    omitted = tuple(cell for cell in direct_open if cell not in requested)
    evidence = []
    for cell in cells:
        value = grid[cell[1]][cell[0]]
        if value == CellState.HIDDEN:
            evidence.append(OpeningEvidence(cell, "NOT_EVALUATED", "BASE_NOT_EVALUATED"))
        else:
            reason = "PHYSICALLY_FLAGGED" if value == CellState.FLAGGED else "ALREADY_OPEN"
            evidence.append(OpeningEvidence(cell, "EXCLUDED", reason))

    normalized = tuple(tuple(CellState.HIDDEN.value if value == CellState.FLAGGED
                             else value for value in row) for row in grid)
    try:
        base = calculate_probabilities(normalized, num_mines)
    except InconsistentObservationError as exc:
        return OpeningAnalysis(identity, "INCONSISTENT_INPUT", str(exc), 0,
                               tuple(evidence), omitted)
    except Exception as exc:
        return OpeningAnalysis(identity, "NOT_EVALUATED", f"{type(exc).__name__}: {exc}",
                               None, tuple(evidence), omitted)

    denominator = base.total_worlds
    marginals = {item.coordinate: item.mine_worlds for item in base.probabilities}
    for index, item in enumerate(evidence):
        if item.status == "EXCLUDED":
            continue
        x, y = item.coordinate
        virtual_zero = tuple(tuple(0 if (nx, ny) == (x, y) else value
                                   for nx, value in enumerate(row))
                             for ny, row in enumerate(normalized))
        try:
            try:
                numerator = calculate_probabilities(virtual_zero, num_mines).total_worlds
            except InconsistentObservationError:
                numerator = 0
            evidence[index] = OpeningEvidence(
                item.coordinate, "EXACT", "PUBLIC_COUNTS", denominator,
                marginals[item.coordinate], numerator,
            )
        except Exception as exc:
            evidence[index] = OpeningEvidence(
                item.coordinate, "NOT_EVALUATED", f"{type(exc).__name__}: {exc}",
                denominator, marginals[item.coordinate], None,
            )

    minimum = min((marginals[cell] for cell in direct_open), default=None)
    minimum_cells = tuple(cell for cell in direct_open if marginals[cell] == minimum)
    minimum_risk = None if minimum is None else Fraction(minimum, denominator)
    exact = [item for item in evidence if item.status == "EXACT"]
    admissible = []
    for item in exact:
        if item.mine_worlds == denominator:
            continue
        if item.mine_worlds > 0 and not allow_guess:
            continue
        if mode == SAFETY_PRESERVING and item.mine_worlds != minimum:
            continue
        if mode == EFFICIENCY_PRIORITIZED and item.mine_worlds > 0 and item.zero_worlds == 0:
            continue
        admissible.append(item)

    groups = _zero_groups(identity, marginals, evidence)
    redundant = {cell for group in groups for cell in group.candidate_cells[1:]}
    ordered = sorted(admissible, key=lambda item: (
        -item.zero_probability, item.mine_probability, *_reading_order(item.coordinate),
    ))
    query_order = tuple(item.coordinate for item in ordered if item.coordinate not in redundant)
    incomplete = any(item.status == "NOT_EVALUATED" for item in evidence)
    reason = "OPENING_QUERY_ORDER"
    if not query_order:
        reason = "NO_ADMISSIBLE_OPENING_CANDIDATE"
        if mode == SAFETY_PRESERVING and minimum_cells and not requested.intersection(minimum_cells):
            reason = "GLOBAL_MINIMUM_NOT_QUERIED"
        elif minimum is not None and minimum > 0 and not allow_guess:
            reason = "GUESS_DISABLED"
    return OpeningAnalysis(
        identity=identity,
        status="PARTIAL" if incomplete else "COMPLETE",
        reason=reason,
        total_worlds=denominator,
        evidence=tuple(evidence),
        omitted_direct_open=omitted,
        global_minimum_risk=minimum_risk,
        global_minimum_cells=minimum_cells,
        certain_zero_groups=groups,
        admissible_candidates=tuple(item.coordinate for item in admissible),
        exploratory_candidates=tuple(item.coordinate for item in ordered if item.mine_worlds > 0),
        query_order=query_order,
    )
