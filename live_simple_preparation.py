"""Public direct-proof FLAG preparation for Simple's existing 100x100 range.

This adapter neither changes the Simple planner nor widens V1's review DTO.
All flags are masked before applying clue/total zero-all witnesses. Unknown
flags can be actual mines. No propagation, enumeration or layout is used.
"""
from dataclasses import dataclass, field

from core_engine import CellState
from simple_algorithm import Constraint, InconsistentObservationError, build_constraints


@dataclass(frozen=True)
class SimpleFlagPreparation:
    observation: tuple
    num_mines: int
    retained: tuple = field(init=False)
    removable: tuple = field(init=False)
    proved_safe: tuple = field(init=False)

    def __post_init__(self):
        grid = self.observation
        if (type(grid) is not tuple or not 1 <= len(grid) <= 100
                or type(grid[0]) is not tuple or not 1 <= len(grid[0]) <= 100
                or any(type(row) is not tuple or len(row) != len(grid[0]) for row in grid)
                or any(type(v) is not int or v not in (-3, -2, 0, 1, 2, 3, 4, 5, 6, 7, 8)
                       for row in grid for v in row)
                or type(self.num_mines) is not int or not 0 <= self.num_mines < len(grid) * len(grid[0])):
            raise ValueError("Invalid Simple public preparation observation.")
        flags = tuple((x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v == -3)
        view = tuple(tuple(-2 if v == -3 else v for v in row) for row in grid)
        hidden = frozenset((x, y) for y, row in enumerate(view) for x, v in enumerate(row) if v == -2)
        safe, mines = set(), set()
        for clue in (*build_constraints(view), Constraint((-1, -1), self.num_mines, hidden)):
            if clue.remaining_mines == 0:
                safe.update(clue.hidden_cells)
            elif clue.remaining_mines == len(clue.hidden_cells):
                mines.update(clue.hidden_cells)
        if safe & mines or len(mines) > self.num_mines or self.num_mines > len(hidden - safe):
            raise InconsistentObservationError("Direct FLAG proofs contradict the public mine total.")
        object.__setattr__(self, 'retained', tuple(cell for cell in flags if cell in mines))
        object.__setattr__(self, 'removable', tuple(cell for cell in flags if cell not in mines))
        object.__setattr__(self, 'proved_safe', tuple(cell for cell in flags if cell in safe))

    def observation_after(self, count):
        if type(count) is not int or not 0 <= count <= len(self.removable):
            raise ValueError("Invalid Simple preparation prefix.")
        removed = set(self.removable[:count])
        return tuple(tuple(int(CellState.HIDDEN) if (x, y) in removed else v
                           for x, v in enumerate(row)) for y, row in enumerate(self.observation))

    def target(self, count, observation):
        if observation != self.observation_after(count) or count == len(self.removable):
            raise ValueError("Simple preparation no longer matches its exact removal prefix.")
        return self.removable[count]


def prepare_flags(observation, num_mines):
    # Keep strict integer/glyph validation instead of silently coercing values.
    grid = tuple(tuple(int(v) if type(v) is CellState else v for v in row) for row in observation)
    return SimpleFlagPreparation(grid, num_mines)
