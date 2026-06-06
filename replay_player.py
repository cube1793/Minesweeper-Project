"""
replay_player.py
Action-index based replay playback for one Minesweeper game.

The player restores the saved board through MinesweeperEngine.reset_with_mines()
and reapplies replay events from the beginning. It does not handle UI controls,
file I/O, cursor movement, or time-based autoplay.
"""

from core_engine import Action, MinesweeperEngine
from replay_model import (
    ACTION_CHORD,
    ACTION_FLAG,
    ACTION_OPEN,
    ReplayData,
    ReplayEvent,
)


_REPLAY_ACTION_TO_ENGINE_ACTION = {
    ACTION_OPEN: Action.OPEN,
    ACTION_FLAG: Action.FLAG,
    ACTION_CHORD: Action.CHORD,
}


class ReplayPlayer:
    """Replay one game's click events by action index."""

    def __init__(self, replay_data: ReplayData):
        self.replay_data = replay_data
        self.engine = self._new_engine()
        self.current_index = 0
        self.go_to(0)

    @property
    def event_count(self) -> int:
        """Total number of events in the replay."""
        return len(self.replay_data.events)

    @property
    def current_event(self) -> ReplayEvent | None:
        """Last applied event, or None at the initial state."""
        if self.current_index == 0:
            return None
        return self.replay_data.events[self.current_index - 1]

    @property
    def current_time(self) -> float:
        """Elapsed time of the last applied event, or 0.0 at index 0."""
        event = self.current_event
        if event is None:
            return 0.0
        return event.elapsed_time

    def get_observation(self):
        """Return the current engine observation."""
        return self.engine.get_observation()

    def go_to(self, index: int):
        """
        Restore the replay state after applying events[:index].

        index 0 means the initial fixed board with no clicks applied.
        """
        if not isinstance(index, int) or not (0 <= index <= self.event_count):
            raise ValueError("Replay index is out of range.")

        self.engine = self._new_engine()
        for event in self.replay_data.events[:index]:
            self._apply_event(event)

        self.current_index = index
        return self.get_observation()

    def next(self) -> bool:
        """
        Apply the next event.

        Returns False if the replay is already at the final event.
        """
        if self.current_index >= self.event_count:
            return False

        self._apply_event(self.replay_data.events[self.current_index])
        self.current_index += 1
        return True

    def previous(self) -> bool:
        """
        Move one event backward by restoring from the beginning.

        Returns False if the replay is already at the initial state.
        """
        if self.current_index <= 0:
            return False

        self.go_to(self.current_index - 1)
        return True

    def _new_engine(self) -> MinesweeperEngine:
        board = self.replay_data.board
        engine = MinesweeperEngine(
            width=board.width,
            height=board.height,
            num_mines=board.num_mines,
        )
        engine.reset_with_mines(
            width=board.width,
            height=board.height,
            num_mines=board.num_mines,
            mine_positions=board.mine_positions,
        )
        return engine

    def _apply_event(self, event: ReplayEvent) -> None:
        action = _REPLAY_ACTION_TO_ENGINE_ACTION[event.action]
        self.engine.step(event.x, event.y, action)
