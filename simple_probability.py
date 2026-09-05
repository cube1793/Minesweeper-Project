"""Stage 2-2 exact probabilities from an observation and public mine count.

Every complete board consistent with the opened clues, flags (assumed mines),
and num_mines has equal weight. Only numbers 0..8, HIDDEN and FLAGGED are
accepted, using Stage 2-1's observation validation and Constraint model.
Coordinates are (x, y); returned cells are in (y, x) reading order.

Future runner integration, after its separate first-click policy:
    constraints = build_constraints(observation)
    move = choose_deterministic_move(infer_deterministic(constraints))
    if move is None:
        result = calculate_probabilities(observation, num_mines)
        move = choose_probability_move(result)

The runner must obtain a fresh observation after each action. This module
neither executes actions nor inspects an engine or a hidden answer board.
On a completely unopened grid the fixed-layout probability is num_mines / H;
this does not represent the engine's first-OPEN safety guarantee.

Enumeration is exact, with no sampling, cutoff, or approximate fallback.
Large connected constraint components can still require exponential time.
"""

from dataclasses import dataclass
from fractions import Fraction
from math import comb

from core_engine import Action, CellState
from simple_algorithm import (
    Constraint,
    Coordinate,
    InconsistentObservationError,
    Observation,
    SimpleMove,
    build_constraints,
)


def _reading_order(cell: Coordinate) -> tuple[int, int]:
    return cell[1], cell[0]


@dataclass(frozen=True)
class CellProbability:
    """Unreduced complete-board counts; probability exposes their exact ratio."""

    coordinate: Coordinate
    mine_worlds: int
    total_worlds: int

    def __post_init__(self):
        object.__setattr__(self, "coordinate", tuple(self.coordinate))
        for count in (self.mine_worlds, self.total_worlds):
            if isinstance(count, bool) or not isinstance(count, int):
                raise ValueError("World counts must be integers.")
        if self.total_worlds <= 0 or not 0 <= self.mine_worlds <= self.total_worlds:
            raise ValueError(
                "Require 0 <= mine_worlds <= total_worlds and total_worlds > 0."
            )

    @property
    def probability(self) -> Fraction:
        return Fraction(self.mine_worlds, self.total_worlds)


@dataclass(frozen=True)
class ProbabilityResult:
    """All HIDDEN cells, with one common denominator and ordered region metadata.

    Solver results list probabilities, frontier_cells and unconstrained_cells
    in (y, x) order. With no HIDDEN cells a consistent board has total_worlds=1
    and empty tuples, so the move selector returns None.
    """

    total_worlds: int
    probabilities: tuple[CellProbability, ...]
    frontier_cells: tuple[Coordinate, ...]
    unconstrained_cells: tuple[Coordinate, ...]

    def __post_init__(self):
        object.__setattr__(self, "probabilities", tuple(self.probabilities))
        for field in ("frontier_cells", "unconstrained_cells"):
            cells = tuple(tuple(cell) for cell in getattr(self, field))
            object.__setattr__(self, field, cells)
        if (
            isinstance(self.total_worlds, bool)
            or not isinstance(self.total_worlds, int)
            or self.total_worlds <= 0
        ):
            raise ValueError("total_worlds must be a positive integer.")
        if any(cell.total_worlds != self.total_worlds for cell in self.probabilities):
            raise ValueError("All cell counts must share the result's total_worlds.")


@dataclass(frozen=True)
class _ConstraintComponent:
    cells: tuple[Coordinate, ...]
    constraints: tuple[Constraint, ...]


@dataclass
class _ComponentCounts:
    # Sparse integer histograms: absent mine counts have zero configurations.
    ways: dict[int, int]
    mine_ways: dict[Coordinate, dict[int, int]]


def _split_components(
    constraints: tuple[Constraint, ...],
) -> tuple[_ConstraintComponent, ...]:
    """Traverse the cell/constraint incidence graph, ignoring empty constraints."""
    cell_constraints: dict[Coordinate, list[int]] = {}
    for index, constraint in enumerate(constraints):
        for cell in sorted(constraint.hidden_cells, key=_reading_order):
            cell_constraints.setdefault(cell, []).append(index)

    seen_cells = set()
    seen_constraints = set()
    components = []
    for start in sorted(cell_constraints, key=_reading_order):
        if start in seen_cells:
            continue
        pending = [start]
        seen_cells.add(start)
        cells = []
        indices = []
        while pending:
            cell = pending.pop()
            cells.append(cell)
            for index in cell_constraints[cell]:
                if index in seen_constraints:
                    continue
                seen_constraints.add(index)
                indices.append(index)
                neighbors = sorted(constraints[index].hidden_cells, key=_reading_order)
                for neighbor in neighbors:
                    if neighbor not in seen_cells:
                        seen_cells.add(neighbor)
                        pending.append(neighbor)
        components.append(
            _ConstraintComponent(
                cells=tuple(sorted(cells, key=_reading_order)),
                constraints=tuple(constraints[index] for index in sorted(indices)),
            )
        )
    return tuple(components)


def _enumerate_component(component: _ConstraintComponent) -> _ComponentCounts:
    """Backtrack with per-constraint bounds, accumulating counts only at leaves.

    Variables with more incident constraints come first, then (y, x); each
    tries 0 before 1. Explicit depth/undo state avoids Python's recursion limit.
    No complete assignments are retained or multiplied across components.
    """
    memberships: dict[Coordinate, list[int]] = {cell: [] for cell in component.cells}
    for index, constraint in enumerate(component.constraints):
        for cell in constraint.hidden_cells:
            memberships[cell].append(index)
    ordered_cells = sorted(
        component.cells,
        key=lambda cell: (-len(memberships[cell]), *_reading_order(cell)),
    )
    incident = [memberships[cell] for cell in ordered_cells]
    targets = [constraint.remaining_mines for constraint in component.constraints]
    unassigned = [len(constraint.hidden_cells) for constraint in component.constraints]
    assigned = [0] * len(component.constraints)
    values = [0] * len(ordered_cells)
    next_values = [0] * len(ordered_cells)
    ways: dict[int, int] = {}
    mine_ways: dict[Coordinate, dict[int, int]] = {cell: {} for cell in component.cells}

    def update(depth: int, value: int, direction: int):
        for index in incident[depth]:
            assigned[index] += direction * value
            unassigned[index] -= direction

    depth = 0
    mine_count = 0
    while depth >= 0:
        if next_values[depth] == 2:
            # This variable is exhausted: reset it and undo its parent choice.
            next_values[depth] = 0
            depth -= 1
            if depth >= 0:
                update(depth, values[depth], -1)
                mine_count -= values[depth]
            continue

        value = next_values[depth]
        next_values[depth] += 1
        update(depth, value, 1)
        if any(
            assigned[index] > targets[index]
            or assigned[index] + unassigned[index] < targets[index]
            for index in incident[depth]
        ):
            update(depth, value, -1)
            continue

        values[depth] = value
        mine_count += value
        if depth + 1 == len(ordered_cells):
            ways[mine_count] = ways.get(mine_count, 0) + 1
            for cell, is_mine in zip(ordered_cells, values):
                if is_mine:
                    histogram = mine_ways[cell]
                    histogram[mine_count] = histogram.get(mine_count, 0) + 1
            update(depth, value, -1)
            mine_count -= value
        else:
            depth += 1

    if not ways:
        raise InconsistentObservationError(
            f"Constraint component containing {component.cells[0]} "
            "has no valid assignment."
        )
    return _ComponentCounts(
        ways=dict(sorted(ways.items())),
        mine_ways={
            cell: dict(sorted(counts.items())) for cell, counts in mine_ways.items()
        },
    )


def _convolve(left: dict[int, int], right: dict[int, int]) -> dict[int, int]:
    """Combine independent regions by mine count, never by assignment product."""
    result: dict[int, int] = {}
    for left_mines, left_ways in left.items():
        for right_mines, right_ways in right.items():
            mines = left_mines + right_mines
            result[mines] = result.get(mines, 0) + left_ways * right_ways
    return dict(sorted(result.items()))


def _combinations(cells: int, mines: int) -> int:
    """Invalid residual mine budgets have zero ways, including U=0 boundaries."""
    return comb(cells, mines) if 0 <= mines <= cells else 0


def calculate_probabilities(
    observation: Observation, num_mines: int,
) -> ProbabilityResult:
    """Count every publicly consistent complete board and each HIDDEN marginal.

    Flags are fixed mines, so R = num_mines - global flag count. Frontier cells
    occur in at least one nonempty clue constraint; all other HIDDEN cells are
    unconstrained (floating), including those far from every opened number.

    Invalid input types/grids raise ValueError as in Stage 2-1. Impossible
    clues, flag/hidden mine budgets, unsatisfiable components, and zero globally
    consistent worlds raise InconsistentObservationError. No first-click state
    or answer-board argument is accepted.
    """
    if isinstance(num_mines, bool) or not isinstance(num_mines, int):
        raise ValueError("num_mines must be an integer.")
    constraints = build_constraints(observation)
    hidden_cells = tuple(
        (x, y)
        for y, row in enumerate(observation)
        for x, value in enumerate(row)
        if value == CellState.HIDDEN
    )
    flag_count = sum(value == CellState.FLAGGED for row in observation for value in row)
    remaining_mines = num_mines - flag_count
    if not 0 <= remaining_mines <= len(hidden_cells):
        raise InconsistentObservationError(
            f"num_mines={num_mines}, flag_count={flag_count}: remaining_mines="
            f"{remaining_mines} must be between 0 and {len(hidden_cells)} hidden cells."
        )

    components = _split_components(constraints)
    frontier = {cell for component in components for cell in component.cells}
    frontier_cells = tuple(cell for cell in hidden_cells if cell in frontier)
    unconstrained_cells = tuple(cell for cell in hidden_cells if cell not in frontier)
    floating_count = len(unconstrained_cells)
    counts = tuple(_enumerate_component(component) for component in components)

    # Prefix/suffix DPs let each component be excluded without enumerating any
    # cross-component assignments, or rebuilding all other regions one by one.
    prefix = [{0: 1}]
    for component_counts in counts:
        prefix.append(_convolve(prefix[-1], component_counts.ways))
    suffix: list[dict[int, int]] = [{} for _ in range(len(counts) + 1)]
    suffix[-1] = {0: 1}
    for index in range(len(counts) - 1, -1, -1):
        suffix[index] = _convolve(counts[index].ways, suffix[index + 1])

    all_ways = prefix[-1]
    total_worlds = sum(
        ways * _combinations(floating_count, remaining_mines - mines)
        for mines, ways in all_ways.items()
    )
    if total_worlds == 0:
        raise InconsistentObservationError(
            "No complete board satisfies the observation and total num_mines."
        )

    mine_worlds: dict[Coordinate, int] = {}
    for index, component_counts in enumerate(counts):
        other_ways = _convolve(prefix[index], suffix[index + 1])
        # For each k in this component, count every possible completion outside
        # it. Reuse those exact weights for all its cells' mine histograms.
        completion_weights = {
            mines: sum(
                ways * _combinations(
                    floating_count, remaining_mines - mines - other_mines
                )
                for other_mines, ways in other_ways.items()
            )
            for mines in component_counts.ways
        }
        for cell, histogram in component_counts.mine_ways.items():
            mine_worlds[cell] = sum(
                ways * completion_weights[mines] for mines, ways in histogram.items()
            )

    if floating_count:
        floating_mine_worlds = sum(
            ways * _combinations(floating_count - 1, remaining_mines - mines - 1)
            for mines, ways in all_ways.items()
        )
        mine_worlds.update((cell, floating_mine_worlds) for cell in unconstrained_cells)

    return ProbabilityResult(
        total_worlds=total_worlds,
        probabilities=tuple(
            CellProbability(cell, mine_worlds[cell], total_worlds)
            for cell in hidden_cells
        ),
        frontier_cells=frontier_cells,
        unconstrained_cells=unconstrained_cells,
    )


def choose_probability_move(result: ProbabilityResult) -> SimpleMove | None:
    """FLAG a certain mine first; otherwise OPEN the exact minimum-risk cell.

    Certainty uses exact world counts; OPEN risk uses exact fractions. Both
    actions break ties by (y, x). Certain mines take priority over 0% safe
    cells, matching Stage 2-1's FLAG-before-OPEN certainty policy.
    The caller gives deterministic moves priority and handles the first click.
    This selector executes no actions and returns None only for an empty result.
    """
    if not result.probabilities:
        return None
    certain_mines = [
        cell for cell in result.probabilities
        if cell.mine_worlds == cell.total_worlds
    ]
    if certain_mines:
        selected = min(certain_mines, key=lambda cell: _reading_order(cell.coordinate))
        x, y = selected.coordinate
        return SimpleMove(action=Action.FLAG, x=x, y=y)

    safest = min(
        result.probabilities,
        key=lambda cell: (cell.probability, *_reading_order(cell.coordinate)),
    )
    x, y = safest.coordinate
    return SimpleMove(action=Action.OPEN, x=x, y=y)
