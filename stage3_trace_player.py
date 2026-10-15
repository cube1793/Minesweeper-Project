"""Pure action-index reconstruction of recorded Stage-3 execution.

Only trace.move is applied; planner evidence and unexecuted plan suffixes are
never interpreted. Modeled microseconds come directly from the recorded traces,
independently of the reconstruction engine's elapsed-time bookkeeping.
"""

from copy import deepcopy

from core_engine import GameStatus, MinesweeperEngine
from simple_algorithm import Coordinate, Observation
from stage3_execution import Stage3Execution
from stage3_runner import Stage3ActionTrace


class Stage3TracePlayer:
    """Play one fixed execution, with index k meaning exactly traces[:k].

    Seeking rebuilds from the fixed layout, as ReplayPlayer.go_to does. Forward
    advancement applies one trace to an isolated copy of the current engine.
    Both paths publish only after validation, leaving the previous observation,
    index, cursor and time intact on failure.
    """

    def __init__(self, execution: Stage3Execution):
        self._execution = execution
        self._engine = self._new_engine()
        self._current_index = 0
        self._cumulative_modeled_us = 0
        if self.step_count == 0 and self.status != execution.result.status:
            raise ValueError("Empty trace stream does not match result.status.")

    @property
    def execution(self) -> Stage3Execution:
        """The immutable source bundle retained for all seeks."""
        return self._execution

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def step_count(self) -> int:
        return len(self.execution.result.traces)

    @property
    def current_trace(self) -> Stage3ActionTrace | None:
        """Last applied trace, or None before any physical input."""
        if self.current_index == 0:
            return None
        return self.execution.result.traces[self.current_index - 1]

    @property
    def current_cursor(self) -> Coordinate:
        trace = self.current_trace
        return (0, 0) if trace is None else (trace.move.x, trace.move.y)

    @property
    def cumulative_modeled_us(self) -> int:
        """Exact integer sum of the applied traces' recorded modeled costs."""
        return self._cumulative_modeled_us

    @property
    def status(self) -> GameStatus:
        return self._engine.status

    def get_observation(self) -> Observation:
        return self._engine.get_observation()

    def go_to(self, index: int) -> Observation:
        """Restore traces[:index] and return the observation, including index 0."""
        if (
            isinstance(index, bool) or not isinstance(index, int)
            or not 0 <= index <= self.step_count
        ):
            raise ValueError("Stage-3 trace index must be an integer in 0..step_count.")
        if index == self.current_index:
            return self.get_observation()

        engine = self._new_engine()
        cumulative_us = 0
        for action_index in range(1, index + 1):
            cumulative_us += self._apply_trace(engine, action_index)
        self._engine = engine
        self._current_index = index
        self._cumulative_modeled_us = cumulative_us
        return self.get_observation()

    def next(self) -> bool:
        """Apply the next trace; return False at the final index."""
        if self.current_index == self.step_count:
            return False
        index = self.current_index + 1
        engine = deepcopy(self._engine)
        cumulative_us = self.cumulative_modeled_us + self._apply_trace(engine, index)
        self._engine = engine
        self._current_index = index
        self._cumulative_modeled_us = cumulative_us
        return True

    def previous(self) -> bool:
        """Move back one trace; return False at index 0."""
        if self.current_index == 0:
            return False
        self.go_to(self.current_index - 1)
        return True

    def _apply_trace(self, engine: MinesweeperEngine, action_index: int) -> int:
        """Apply and validate one recorded action on an unpublished candidate."""
        trace = self.execution.result.traces[action_index - 1]
        if engine.status != GameStatus.PLAYING:
            raise ValueError(f"Trace {action_index} follows a terminal board.")
        if (
            isinstance(trace.modeled_action_us, bool)
            or not isinstance(trace.modeled_action_us, int)
            or trace.modeled_action_us < 0
        ):
            raise ValueError(f"Trace {action_index} modeled_action_us must be a nonnegative integer.")
        engine.step(trace.move.x, trace.move.y, trace.move.action)
        if engine.status != trace.status_after:
            raise ValueError(f"Trace {action_index} status_after does not match reconstructed status.")
        if action_index == self.step_count and engine.status != self.execution.result.status:
            raise ValueError("Final reconstructed status does not match result.status.")
        return trace.modeled_action_us

    def _new_engine(self) -> MinesweeperEngine:
        spec, board = self.execution.spec, self.execution.board
        engine = MinesweeperEngine(spec.width, spec.height, spec.num_mines)
        engine.reset_with_mines(spec.width, spec.height, spec.num_mines, board.mine_positions)
        return engine
