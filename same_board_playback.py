"""Pure, independent action-index playback of one accepted comparison.

Human and Stage 2 retain their Replay players; Stage 3 executes recorded trace
moves on the comparison board without inventing a benchmark wrapper. This layer
owns navigation only, not transport admission, solver execution or any clock.
"""

from copy import deepcopy
from enum import Enum

from core_engine import Action, GameStatus, MinesweeperEngine
from replay_model import ReplayBoard, ReplayData
from replay_player import ReplayPlayer
from same_board_comparison import ComparisonLayout, HumanComparisonContext
from same_board_runner import SameBoardExecution
from simple_algorithm import Observation, SimpleMove
from simple_runner import SimpleRunResult
from stage3_runner import Stage3ActionTrace, Stage3RunResult


class ComparisonRun(Enum):
    HUMAN = "human"
    STAGE2 = "stage2"
    STAGE3 = "stage3"


def _require_index(index, count):
    if type(index) is not int or not 0 <= index <= count:
        raise ValueError("Playback index must be an integer in 0..action_count, excluding bool.")


def _require_terminal(status):
    if type(status) is not GameStatus or status not in (GameStatus.WON, GameStatus.LOST):
        raise ValueError("Playback requires a completed WON/LOST run.")


class SameBoardStage3Player:
    """Reconstruct a completed native Stage-3 stream on its exact ReplayBoard.

    Index k means traces[:k]. Seek uses a fresh candidate engine; next applies
    one trace to a copy of the current engine. Neither publishes state on failure.
    Only moves/statuses are consumed. Decision evidence, unexecuted plan suffixes,
    cursor animation, modeled costs and compute measurements are not interpreted.
    Source admission and Model C validation belong to Slice 2, not playback.
    """

    def __init__(self, board: ReplayBoard, result: Stage3RunResult):
        if type(board) is not ReplayBoard or type(result) is not Stage3RunResult:
            raise ValueError("Stage-3 playback requires ReplayBoard and Stage3RunResult.")
        _require_terminal(result.status)
        if type(result.traces) is not tuple or not result.traces:
            raise ValueError("A completed Stage-3 run requires nonempty native traces.")
        self._board = board
        self._result = result
        self._engine = self._new_engine()
        self._current_index = 0

    @property
    def board(self) -> ReplayBoard:
        return self._board

    @property
    def result(self) -> Stage3RunResult:
        return self._result

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def action_count(self) -> int:
        return len(self.result.traces)

    @property
    def status(self) -> GameStatus:
        return self._engine.status

    def get_observation(self) -> Observation:
        return self._engine.get_observation()

    def go_to(self, index: int) -> Observation:
        _require_index(index, self.action_count)
        if index == self.current_index:
            return self.get_observation()
        engine = self._new_engine()
        for action_index in range(1, index + 1):
            self._apply_trace(engine, action_index)
        self._engine = engine
        self._current_index = index
        return self.get_observation()

    def next(self) -> bool:
        if self.current_index == self.action_count:
            return False
        index = self.current_index + 1
        engine = deepcopy(self._engine)
        self._apply_trace(engine, index)
        self._engine = engine
        self._current_index = index
        return True

    def previous(self) -> bool:
        if self.current_index == 0:
            return False
        self.go_to(self.current_index - 1)
        return True

    def _new_engine(self):
        board = self.board
        engine = MinesweeperEngine(board.width, board.height, board.num_mines)
        engine.reset_with_mines(board.width, board.height, board.num_mines, board.mine_positions)
        return engine

    def _apply_trace(self, engine, action_index):
        if engine.status != GameStatus.PLAYING:
            raise ValueError(f"Trace {action_index} follows a terminal board.")
        trace = self.result.traces[action_index - 1]
        if type(trace) is not Stage3ActionTrace or type(trace.move) is not SimpleMove:
            raise ValueError(f"Trace {action_index} requires a native trace and move.")
        move = trace.move
        if (
            type(move.action) is not Action or type(move.x) is not int or type(move.y) is not int
            or not (0 <= move.x < self.board.width and 0 <= move.y < self.board.height)
            or type(trace.status_after) is not GameStatus
        ):
            raise ValueError(f"Trace {action_index} has an invalid move or status.")
        engine.step(move.x, move.y, move.action)
        if engine.status != trace.status_after:
            raise ValueError(f"Trace {action_index} status_after disagrees with reconstruction.")
        if action_index == self.action_count and engine.status != self.result.status:
            raise ValueError("Final reconstruction disagrees with result.status.")


class SameBoardPlayback:
    """Coordinate exactly three players, each retaining its own action index.

    The input must already be an accepted SameBoardExecution. Construction checks
    source types, completed outcomes and exact layout consistency only; it does
    not repeat transport validation, traverse decision evidence or evaluate costs.
    Selecting a run only selects its existing player. Equal numeric indices are
    not an alignment of progress, decisions or time across runs.
    """

    def __init__(self, execution: SameBoardExecution):
        if (
            type(execution) is not SameBoardExecution
            or type(execution.context) is not HumanComparisonContext
            or type(execution.context.layout) is not ComparisonLayout
            or type(execution.stage2_result) is not SimpleRunResult
        ):
            raise ValueError("Playback requires an accepted SameBoardExecution.")
        context, stage2 = execution.context, execution.stage2_result
        for replay in (context.human_replay, stage2.replay_data):
            if (
                type(replay) is not ReplayData or type(replay.board) is not ReplayBoard
                or ComparisonLayout(replay.board) != context.layout
            ):
                raise ValueError("Replay board must match the exact comparison layout.")
        _require_terminal(context.terminal_status)
        _require_terminal(stage2.status)
        if stage2.started_from_hidden is not True:
            raise ValueError("Stage-2 playback requires a complete hidden-start Replay.")
        self._execution = execution
        self._human = ReplayPlayer(context.human_replay)
        self._stage2 = ReplayPlayer(stage2.replay_data)
        self._stage3 = SameBoardStage3Player(context.layout.board, execution.stage3_result)
        self._selected_run = ComparisonRun.HUMAN

    @property
    def execution(self) -> SameBoardExecution:
        return self._execution

    @property
    def selected_run(self) -> ComparisonRun:
        return self._selected_run

    def _player(self, run):
        # Explicit closed dispatch, not a player registry or universal protocol.
        if run is ComparisonRun.HUMAN:
            return self._human
        if run is ComparisonRun.STAGE2:
            return self._stage2
        if run is ComparisonRun.STAGE3:
            return self._stage3
        raise ValueError("Run must be HUMAN, STAGE2 or STAGE3 from ComparisonRun.")

    def select(self, run: ComparisonRun) -> None:
        self._player(run)  # Validate without seeking, advancing or rebuilding.
        self._selected_run = run

    @property
    def current_index(self) -> int:
        return self.index_for(self.selected_run)

    def index_for(self, run: ComparisonRun) -> int:
        return self._player(run).current_index

    def action_count(self, run: ComparisonRun | None = None) -> int:
        run = self.selected_run if run is None else run
        player = self._player(run)
        return player.action_count if run is ComparisonRun.STAGE3 else player.event_count

    @property
    def status(self) -> GameStatus:
        """Current reconstructed state, which can be PLAYING for a finished run."""
        player = self._player(self.selected_run)
        return player.status if self.selected_run is ComparisonRun.STAGE3 else player.engine.status

    def final_outcome(self, run: ComparisonRun | None = None) -> GameStatus:
        """Recorded completed outcome; navigation never changes this authority."""
        run = self.selected_run if run is None else run
        self._player(run)
        if run is ComparisonRun.HUMAN:
            return self.execution.context.terminal_status
        if run is ComparisonRun.STAGE2:
            return self.execution.stage2_result.status
        return self.execution.stage3_result.status

    def get_observation(self) -> Observation:
        return self._player(self.selected_run).get_observation()

    def go_to(self, index: int) -> Observation:
        # ReplayPlayer's historical bool acceptance is unchanged outside here.
        _require_index(index, self.action_count())
        return self._player(self.selected_run).go_to(index)

    def next(self) -> bool:
        return self._player(self.selected_run).next()

    def previous(self) -> bool:
        return self._player(self.selected_run).previous()
