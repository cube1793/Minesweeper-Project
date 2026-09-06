"""Stage 2-3 synchronous engine runner using the observation-only analyzer.

Replay capture is a separate output path: snapshots go only to ReplayRecorder.
No replay or answer-board data participates in analysis or move selection.
"""

from dataclasses import dataclass
from enum import Enum

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_model import ReplayData, SOURCE_ALGORITHM
from replay_recorder import ReplayRecorder
from simple_algorithm import Observation, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position


class StopReason(Enum):
    WON = "won"
    LOST = "lost"
    GUESS_REQUIRED = "guess_required"


class SimpleRunnerError(RuntimeError):
    """A playing engine cannot advance under the runner's action contract."""


@dataclass(frozen=True)
class SimpleRunResult:
    """Physical actions from this invocation, including its initial OPEN.

    replay_data.events corresponds one-to-one to moves. If started_from_hidden
    is False, it is only a continuation segment: ReplayData v1 has no starting
    observation or earlier click history, so ReplayPlayer alone cannot restore
    the original position. Retain the earlier game recording to compose a full
    replay. No synthetic setup clicks are added to the physical action log.
    """

    status: GameStatus
    stop_reason: StopReason
    moves: tuple[SimpleMove, ...]
    replay_data: ReplayData
    pending_decision: SimpleDecision | None
    started_from_hidden: bool

    def __post_init__(self):
        object.__setattr__(self, "moves", tuple(self.moves))


def _hidden_count(observation: Observation) -> int:
    return sum(value == CellState.HIDDEN for row in observation for value in row)


def _capture_replay_board(engine: MinesweeperEngine, recorder: ReplayRecorder):
    """The only runner path that receives hidden data; used only for recording."""
    if recorder.board is None:
        snapshot = engine.get_board_snapshot()
        if not snapshot.mines_placed:
            raise SimpleRunnerError("Cannot record a replay before mines are placed.")
        recorder.capture_board(snapshot)


def run_simple(
    engine: MinesweeperEngine, *, accept_guesses: bool = False,
) -> SimpleRunResult:
    """Continue the current game until terminal, or pause before an actual guess.

    An all-HIDDEN start always executes OPEN (0, 0), even with guesses disabled.
    On a fresh random game the engine guarantees this click is safe. Fixed
    boards retain their supplied layout and should use a safe (0, 0) fixture.
    Any opened/flagged start goes directly to analysis; terminal engines receive
    no actions or analysis. Existing flags retain the solver's assumed-mine
    semantics; observation/solver errors propagate without a fallback.

    Each decision supplies exactly one physical action, followed by a fresh
    observation. Targets must be HIDDEN and each nonterminal action must reduce
    the HIDDEN count. This proves progress without an arbitrary step limit.

    Like the UI, record the engine's elapsed time AFTER step(), then capture
    the finalized board once. Partial replay data is available on guess pauses;
    see SimpleRunResult for the limitation when joining an existing game.
    """
    if not isinstance(accept_guesses, bool):
        raise ValueError("accept_guesses must be a bool.")

    observation = engine.get_observation()
    hidden_count = _hidden_count(observation)
    started_from_hidden = hidden_count == engine.width * engine.height
    first_open = started_from_hidden
    recorder = ReplayRecorder(
        engine.width, engine.height, engine.num_mines, SOURCE_ALGORITHM,
    )
    moves = []
    pending_decision = None

    while engine.status == GameStatus.PLAYING:
        if first_open:
            move = SimpleMove(Action.OPEN, 0, 0)
            first_open = False
        else:
            decision = analyze_position(observation, engine.num_mines)
            if decision is None:
                raise SimpleRunnerError("Analyzer returned no move while PLAYING.")
            if decision.kind == DecisionKind.PROBABILITY_GUESS and not accept_guesses:
                pending_decision = decision
                break
            move = decision.move

        if (
            move.action not in (Action.OPEN, Action.FLAG)
            or not (0 <= move.x < engine.width and 0 <= move.y < engine.height)
            or observation[move.y][move.x] != CellState.HIDDEN
        ):
            raise SimpleRunnerError("Selected move must OPEN or FLAG a HIDDEN cell.")

        engine.step(move.x, move.y, move.action)
        moves.append(move)
        recorder.record_event(engine.get_elapsed_time(), move.x, move.y, move.action)
        _capture_replay_board(engine, recorder)
        observation = engine.get_observation()
        new_hidden_count = _hidden_count(observation)
        if engine.status == GameStatus.PLAYING and new_hidden_count >= hidden_count:
            raise SimpleRunnerError("Action made no progress: HIDDEN count did not decrease.")
        hidden_count = new_hidden_count

    # Also capture when a progressed/terminal game needs no new physical action.
    _capture_replay_board(engine, recorder)
    stop_reason = (
        StopReason.GUESS_REQUIRED if pending_decision is not None
        else StopReason.WON if engine.status == GameStatus.WON
        else StopReason.LOST
    )
    return SimpleRunResult(
        status=engine.status,
        stop_reason=stop_reason,
        moves=tuple(moves),
        replay_data=recorder.to_replay_data(),
        pending_decision=pending_decision,
        started_from_hidden=started_from_hidden,
    )
