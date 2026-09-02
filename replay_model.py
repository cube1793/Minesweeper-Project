"""
replay_model.py
Pure data models for one-game Minesweeper replay data.

This module only describes replay data.  It does not read/write JSON, control
the UI, or execute game actions.
"""

from dataclasses import dataclass
from math import isfinite


Coordinate = tuple[int, int]
MinePositions = frozenset[Coordinate]
ReplayAction = str

ACTION_OPEN = "OPEN"
ACTION_FLAG = "FLAG"
ACTION_CHORD = "CHORD"
VALID_REPLAY_ACTIONS = frozenset({ACTION_OPEN, ACTION_FLAG, ACTION_CHORD})

SOURCE_HUMAN = "human"
SOURCE_ALGORITHM = "algorithm"
SOURCE_AI = "ai"
VALID_SOURCE_TYPES = frozenset({SOURCE_HUMAN, SOURCE_ALGORITHM, SOURCE_AI})


@dataclass(frozen=True)
class ReplayBoard:
    """Static board data required to reproduce a single game."""

    width: int
    height: int
    num_mines: int
    mine_positions: MinePositions

    def __post_init__(self):
        for name, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"Replay board {name} must be an integer.")
            if value <= 0:
                raise ValueError(f"Replay board {name} must be positive.")

        if isinstance(self.num_mines, bool) or not isinstance(self.num_mines, int):
            raise ValueError("Replay board num_mines must be an integer.")
        if self.num_mines < 0:
            raise ValueError("Replay board num_mines must be non-negative.")
        if self.num_mines >= self.width * self.height:
            raise ValueError("num_mines must be smaller than the number of cells.")

        try:
            mine_positions = frozenset(self.mine_positions)
        except (TypeError, ValueError) as exc:
            raise ValueError("Replay board mine_positions must be coordinates.") from exc
        object.__setattr__(self, "mine_positions", mine_positions)

        for position in mine_positions:
            try:
                x, y = position
            except (TypeError, ValueError) as exc:
                raise ValueError("Mine position must be an (x, y) pair.") from exc
            if any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in (x, y)
            ):
                raise ValueError("Mine position coordinates must be integers.")
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise ValueError("Mine position is out of board bounds.")

        if self.num_mines != len(mine_positions):
            raise ValueError("num_mines must match the number of mine positions.")


@dataclass(frozen=True)
class ReplayEvent:
    """One click event in a replay."""

    elapsed_time: float
    x: int
    y: int
    action: ReplayAction

    def __post_init__(self):
        if isinstance(self.elapsed_time, bool) or not isinstance(
            self.elapsed_time,
            (int, float),
        ):
            raise ValueError("elapsed_time must be an integer or float.")
        if not isfinite(self.elapsed_time):
            raise ValueError("elapsed_time must be finite.")
        if self.elapsed_time < 0:
            raise ValueError("elapsed_time must be non-negative.")

        for name, value in (("x", self.x), ("y", self.y)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"Replay event {name} must be an integer.")
            if value < 0:
                raise ValueError(f"Replay event {name} must be non-negative.")

        if not isinstance(self.action, str) or self.action not in VALID_REPLAY_ACTIONS:
            raise ValueError("Replay event action is not supported.")


@dataclass(frozen=True)
class ReplayData:
    """Replay data for one game."""

    board: ReplayBoard
    events: tuple[ReplayEvent, ...]
    source_type: str = SOURCE_HUMAN
    schema_version: int = 1

    def __post_init__(self):
        object.__setattr__(self, "events", tuple(self.events))

        if self.source_type not in VALID_SOURCE_TYPES:
            raise ValueError("Replay source_type is not supported.")
        if self.schema_version != 1:
            raise ValueError("Unsupported replay schema_version.")

        previous_elapsed_time = None
        for event in self.events:
            if not (0 <= event.x < self.board.width and 0 <= event.y < self.board.height):
                raise ValueError("Replay event is out of board bounds.")
            if (
                previous_elapsed_time is not None
                and event.elapsed_time < previous_elapsed_time
            ):
                raise ValueError("Replay event times must be nondecreasing.")
            previous_elapsed_time = event.elapsed_time
