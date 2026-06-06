"""
replay_model.py
Pure data models for one-game Minesweeper replay data.

This module only describes replay data.  It does not read/write JSON, control
the UI, or execute game actions.
"""

from dataclasses import dataclass


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
        mine_positions = frozenset(self.mine_positions)
        object.__setattr__(self, "mine_positions", mine_positions)

        if self.width <= 0 or self.height <= 0:
            raise ValueError("Replay board dimensions must be positive.")
        if self.num_mines != len(mine_positions):
            raise ValueError("num_mines must match the number of mine positions.")
        if self.num_mines >= self.width * self.height:
            raise ValueError("num_mines must be smaller than the number of cells.")

        for x, y in mine_positions:
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise ValueError("Mine position is out of board bounds.")


@dataclass(frozen=True)
class ReplayEvent:
    """One click event in a replay."""

    elapsed_time: float
    x: int
    y: int
    action: ReplayAction

    def __post_init__(self):
        if self.elapsed_time < 0:
            raise ValueError("elapsed_time must be non-negative.")
        if self.x < 0 or self.y < 0:
            raise ValueError("Replay event coordinates must be non-negative.")
        if self.action not in VALID_REPLAY_ACTIONS:
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

        for event in self.events:
            if not (0 <= event.x < self.board.width and 0 <= event.y < self.board.height):
                raise ValueError("Replay event is out of board bounds.")
