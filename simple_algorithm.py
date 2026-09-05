"""
Stage 2-1 deterministic inference using only the visible observation.

Coordinates are (x, y); observation rows are indexed as observation[y][x].
Only opened numbers 0..8, HIDDEN and FLAGGED are accepted. Flags are treated
as mines for inference; their correctness cannot be checked from hidden data.

Usage for one observation:
    constraints = build_constraints(observation)
    result = infer_deterministic(constraints)
    move = choose_deterministic_move(result)

The caller must obtain a new observation and repeat this pipeline after each
action. No actions are executed or queued here. None means these two rules
cannot choose a move, including on a completely unopened board; it is the
future Stage 2-2 probability solver's entry point.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from core_engine import Action, CellState


Coordinate = tuple[int, int]
Observation = Sequence[Sequence[int]]


class InconsistentObservationError(ValueError):
    """Visible clues or their direct inferences contradict each other."""


@dataclass(frozen=True)
class Constraint:
    """One opened clue: exactly remaining_mines of hidden_cells are mines."""

    source: Coordinate
    remaining_mines: int
    hidden_cells: frozenset[Coordinate]

    def __post_init__(self):
        object.__setattr__(self, "hidden_cells", frozenset(self.hidden_cells))
        if isinstance(self.remaining_mines, bool) or not isinstance(
            self.remaining_mines, int
        ):
            raise ValueError("remaining_mines must be an integer.")
        if not 0 <= self.remaining_mines <= len(self.hidden_cells):
            raise InconsistentObservationError(
                f"Constraint at {self.source}: remaining_mines="
                f"{self.remaining_mines} must be between 0 and "
                f"{len(self.hidden_cells)} hidden cells."
            )


@dataclass(frozen=True)
class InferenceResult:
    """All direct safe/mine facts for one observation, without duplicates."""

    safe_cells: frozenset[Coordinate]
    mine_cells: frozenset[Coordinate]

    def __post_init__(self):
        object.__setattr__(self, "safe_cells", frozenset(self.safe_cells))
        object.__setattr__(self, "mine_cells", frozenset(self.mine_cells))
        overlap = self.safe_cells & self.mine_cells
        if overlap:
            coordinates = sorted(overlap, key=lambda cell: (cell[1], cell[0]))
            raise InconsistentObservationError(
                f"Cells inferred as both safe and mine: {coordinates}."
            )


@dataclass(frozen=True)
class SimpleMove:
    """One selected OPEN or FLAG action; selecting it does not execute it."""

    action: Action
    x: int
    y: int


def build_constraints(observation: Observation) -> tuple[Constraint, ...]:
    """
    Build N-F constraints for every opened number, in screen reading order.

    The observation must be a nonempty rectangular sequence containing only
    integer numbers 0..8, HIDDEN or FLAGGED. Unsupported values (including
    game-over cell states) and malformed grids raise ValueError. Impossible
    clue counts raise InconsistentObservationError, even when H is empty.
    """
    if not isinstance(observation, Sequence) or not observation:
        raise ValueError("Observation must be a nonempty rectangular grid.")
    if not isinstance(observation[0], Sequence) or not observation[0]:
        raise ValueError("Observation must have nonempty rows.")

    width, height = len(observation[0]), len(observation)
    for y, row in enumerate(observation):
        if not isinstance(row, Sequence) or len(row) != width:
            raise ValueError("Observation rows must have the same width.")
        for x, value in enumerate(row):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or (
                    value not in (CellState.HIDDEN, CellState.FLAGGED)
                    and not 0 <= value <= 8
                )
            ):
                raise ValueError(f"Unsupported observation value at {(x, y)}: {value!r}.")

    constraints = []
    for y, row in enumerate(observation):
        for x, number in enumerate(row):
            if not 0 <= number <= 8:
                continue

            flags = 0
            hidden_cells = set()
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if (nx, ny) == (x, y):
                        continue
                    neighbor = observation[ny][nx]
                    if neighbor == CellState.FLAGGED:
                        flags += 1
                    elif neighbor == CellState.HIDDEN:
                        hidden_cells.add((nx, ny))

            constraints.append(
                Constraint(
                    source=(x, y),
                    remaining_mines=number - flags,
                    hidden_cells=frozenset(hidden_cells),
                )
            )
    return tuple(constraints)


def infer_deterministic(constraints: Iterable[Constraint]) -> InferenceResult:
    """
    Union facts from only the zero-remaining and all-hidden-are-mines rules.

    Facts are not propagated into other constraints within this observation.
    Only invalid individual constraints and direct safe/mine conflicts are
    detected; this is not a general constraint satisfiability check.
    """
    safe_cells = set()
    mine_cells = set()
    for constraint in constraints:
        if constraint.remaining_mines == 0:
            safe_cells.update(constraint.hidden_cells)
        elif constraint.remaining_mines == len(constraint.hidden_cells):
            mine_cells.update(constraint.hidden_cells)
    return InferenceResult(
        safe_cells=frozenset(safe_cells),
        mine_cells=frozenset(mine_cells),
    )


def choose_deterministic_move(result: InferenceResult) -> SimpleMove | None:
    """Select one FLAG before OPEN, breaking ties by (y, x); else return None."""
    if result.mine_cells:
        action, candidates = Action.FLAG, result.mine_cells
    elif result.safe_cells:
        action, candidates = Action.OPEN, result.safe_cells
    else:
        return None

    x, y = min(candidates, key=lambda cell: (cell[1], cell[0]))
    return SimpleMove(action=action, x=x, y=y)
