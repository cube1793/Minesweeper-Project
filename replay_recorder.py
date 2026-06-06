"""
replay_recorder.py
In-memory recorder for one-game Minesweeper replay data.

The recorder only accumulates click events and captures a finalized board
snapshot. It does not know about PyQt5, JSON, UI controls, or replay playback.
"""

from board_snapshot import BoardSnapshot
from replay_model import (
    ACTION_CHORD,
    ACTION_FLAG,
    ACTION_OPEN,
    ReplayBoard,
    ReplayData,
    ReplayEvent,
    SOURCE_HUMAN,
    VALID_REPLAY_ACTIONS,
    VALID_SOURCE_TYPES,
)


_ACTION_VALUE_TO_NAME = {
    0: ACTION_OPEN,
    1: ACTION_FLAG,
    2: ACTION_CHORD,
}


class ReplayRecorder:
    """Collect click events and build ReplayData after the board is known."""

    def __init__(
        self,
        width: int,
        height: int,
        num_mines: int,
        source_type: str = SOURCE_HUMAN,
    ):
        self.width = width
        self.height = height
        self.num_mines = num_mines
        self.source_type = source_type
        self._events = []
        self._board = None
        self.reset(width, height, num_mines, source_type)

    @property
    def events(self) -> tuple[ReplayEvent, ...]:
        """Recorded events as an immutable tuple."""
        return tuple(self._events)

    @property
    def board(self) -> ReplayBoard | None:
        """Captured board, or None if mines are not finalized yet."""
        return self._board

    @property
    def mine_positions(self):
        """Captured mine positions, or None if the board is not finalized yet."""
        if self._board is None:
            return None
        return self._board.mine_positions

    def reset(
        self,
        width: int | None = None,
        height: int | None = None,
        num_mines: int | None = None,
        source_type: str | None = None,
    ) -> None:
        """Start recording a new game and clear existing replay state."""
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height
        if num_mines is not None:
            self.num_mines = num_mines
        if source_type is not None:
            self.source_type = source_type

        self._validate_game_config()
        self._events = []
        self._board = None

    def record_event(self, elapsed_time: float, x: int, y: int, action) -> ReplayEvent:
        """Record one click event and return the created ReplayEvent."""
        event = ReplayEvent(
            elapsed_time=elapsed_time,
            x=x,
            y=y,
            action=to_replay_action(action),
        )
        if not (0 <= event.x < self.width and 0 <= event.y < self.height):
            raise ValueError("Replay event is out of recorder board bounds.")

        self._events.append(event)
        return event

    def capture_board(self, snapshot: BoardSnapshot) -> ReplayBoard:
        """Capture mine positions from a finalized BoardSnapshot."""
        if not snapshot.mines_placed:
            raise ValueError("Cannot capture replay board before mines are placed.")
        if (
            snapshot.width != self.width
            or snapshot.height != self.height
            or snapshot.num_mines != self.num_mines
        ):
            raise ValueError("Snapshot dimensions do not match recorder settings.")

        self._board = ReplayBoard(
            width=snapshot.width,
            height=snapshot.height,
            num_mines=snapshot.num_mines,
            mine_positions=snapshot.mines,
        )
        return self._board

    def to_replay_data(self) -> ReplayData:
        """Build ReplayData from the captured board and recorded events."""
        if self._board is None:
            raise ValueError("Cannot create ReplayData before the board is captured.")

        return ReplayData(
            board=self._board,
            events=tuple(self._events),
            source_type=self.source_type,
        )

    def _validate_game_config(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Recorder board dimensions must be positive.")
        if self.num_mines < 0 or self.num_mines >= self.width * self.height:
            raise ValueError("Recorder num_mines is out of range.")
        if self.source_type not in VALID_SOURCE_TYPES:
            raise ValueError("Recorder source_type is not supported.")


def to_replay_action(action) -> str:
    """Convert an engine Action or replay action string to a replay action."""
    if isinstance(action, str):
        replay_action = action.upper()
        if replay_action in VALID_REPLAY_ACTIONS:
            return replay_action
        raise ValueError("Replay action string is not supported.")

    action_name = getattr(action, "name", None)
    if action_name in VALID_REPLAY_ACTIONS:
        return action_name

    if isinstance(action, int) and action in _ACTION_VALUE_TO_NAME:
        return _ACTION_VALUE_TO_NAME[action]

    raise ValueError("Action cannot be converted to a replay action.")
