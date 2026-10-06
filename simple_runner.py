"""Stage 2-3 synchronous engine runner using the observation-only analyzer.

First-OPEN policy reads only the public snapshot's mines_placed boolean.
Hidden layout data goes only to ReplayRecorder, never analysis or move selection.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from time import perf_counter_ns

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_model import ReplayData, SOURCE_ALGORITHM
from replay_recorder import ReplayRecorder
from simple_algorithm import Coordinate, Observation, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position


class StopReason(Enum):
    WON = "won"
    LOST = "lost"
    GUESS_REQUIRED = "guess_required"


class SimpleRunnerError(RuntimeError):
    """A playing engine cannot advance under the runner's action contract."""


@dataclass(frozen=True)
class SimpleActionTrace:
    """Execution facts for one action; no Engine or hidden board is exposed."""

    move: SimpleMove
    decision: SimpleDecision | None
    decision_compute_ns: int | None
    status_after: GameStatus
    safe_cells_opened_delta: int
    explicit_flag_delta: int


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


def _action_effect_deltas(
    before: Observation, after: Observation, move: SimpleMove,
) -> tuple[int, int]:
    """Use public transitions and the runner's HIDDEN-target action contract."""
    safe_cells_opened = sum(
        old in (CellState.HIDDEN, CellState.FLAGGED) and 0 <= new <= 8
        for before_row, after_row in zip(before, after)
        for old, new in zip(before_row, after_row)
    )
    # OPEN is zero even when the Engine automatically flags or clears flags.
    explicit_flags = 1 if move.action == Action.FLAG else 0
    return safe_cells_opened, explicit_flags


def _capture_replay_board(engine: MinesweeperEngine, recorder: ReplayRecorder):
    """The only runner path that consumes hidden layout fields, for recording."""
    if recorder.board is None:
        snapshot = engine.get_board_snapshot()
        if not snapshot.mines_placed:
            raise SimpleRunnerError("Cannot record a replay before mines are placed.")
        recorder.capture_board(snapshot)


def run_simple(
    engine: MinesweeperEngine, *, accept_guesses: bool = False,
    initial_open: Coordinate | None = None,
    observer: Callable[[SimpleActionTrace], None] | None = None,
) -> SimpleRunResult:
    """Continue the current game until terminal, or pause before an actual guess.

    An all-HIDDEN start executes the guaranteed-safe OPEN (0, 0) without
    analysis only if mines have not been placed yet. Already placed boards
    (including FLAG then unflag) go directly to normal analysis and obey
    accept_guesses. Opened/flagged starts also go directly to analysis;
    terminal engines receive no actions or analysis. Existing flags retain the
    solver's assumed-mine semantics; solver errors propagate without a fallback.

    initial_open overrides the implicit first-OPEN policy on an all-HIDDEN,
    PLAYING start. Its safety is the caller's responsibility, never checked
    against the hidden layout. Both policy OPENs bypass analysis.

    An optional observer receives immutable execution facts after replay capture,
    fresh observation, effect derivation and progress validation. Only analysis
    is timed, and only with an observer. Observer exceptions propagate; observers
    must not mutate game state through external references.

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
    # started_from_hidden describes the replay's starting observation, not safety.
    if initial_open is not None:
        if (
            not isinstance(initial_open, (tuple, list))
            or len(initial_open) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in initial_open)
        ):
            raise ValueError("initial_open must be a two-integer (x, y) pair.")
        if engine.status != GameStatus.PLAYING:
            raise ValueError("initial_open requires a PLAYING engine.")
        if not started_from_hidden:
            raise ValueError("initial_open requires an entirely HIDDEN observation.")
        x, y = initial_open
        if not (0 <= x < engine.width and 0 <= y < engine.height):
            raise ValueError("initial_open is out of board bounds.")
        if observation[y][x] != CellState.HIDDEN:
            raise ValueError("initial_open target must be HIDDEN.")
        first_move = SimpleMove(Action.OPEN, x, y)
    else:
        first_move = (
            SimpleMove(Action.OPEN, 0, 0)
            if started_from_hidden and not engine.get_board_snapshot().mines_placed
            else None
        )
    recorder = ReplayRecorder(
        engine.width, engine.height, engine.num_mines, SOURCE_ALGORITHM,
    )
    moves = []
    pending_decision = None

    while engine.status == GameStatus.PLAYING:
        decision = None
        decision_compute_ns = None
        if first_move is not None:
            move = first_move
            first_move = None
        else:
            if observer is None:
                decision = analyze_position(observation, engine.num_mines)
            else:
                t0 = perf_counter_ns()
                decision = analyze_position(observation, engine.num_mines)
                t1 = perf_counter_ns()
                decision_compute_ns = t1 - t0
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
        if observer is not None:
            before = observation
        observation = engine.get_observation()
        if observer is not None:
            safe_cells_opened_delta, explicit_flag_delta = _action_effect_deltas(
                before, observation, move,
            )
        new_hidden_count = _hidden_count(observation)
        if engine.status == GameStatus.PLAYING and new_hidden_count >= hidden_count:
            raise SimpleRunnerError("Action made no progress: HIDDEN count did not decrease.")
        hidden_count = new_hidden_count
        if observer is not None:
            observer(SimpleActionTrace(
                move=move,
                decision=decision,
                decision_compute_ns=decision_compute_ns,
                status_after=engine.status,
                safe_cells_opened_delta=safe_cells_opened_delta,
                explicit_flag_delta=explicit_flag_delta,
            ))

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
