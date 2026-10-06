"""Canonical Stage-3 execution, one public-evidence action per fresh plan.

This deliberately separate runner neither changes Stage-2 execution nor stores
a pending plan suffix. It consumes only public engine observations, dimensions,
mine count, and status; hidden engine data is needed only by engine.step itself.
"""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter_ns

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from simple_algorithm import Coordinate, Observation, SimpleMove, build_constraints
from simple_decision import DecisionKind
from stage3_physical import TimingTable, action_cost, load_timing_table, validate_timing_table
from stage3_planner import Stage3Decision, certainty_pool, plan_position


class Stage3RunnerError(RuntimeError):
    """A playing engine cannot advance under the Stage-3 action contract."""


@dataclass(frozen=True)
class Stage3ActionTrace:
    """Public execution evidence for exactly one physical input."""

    move: SimpleMove
    decision: Stage3Decision | None
    decision_compute_ns: int | None
    cursor_before: Coordinate
    modeled_action_us: int
    status_after: GameStatus
    safe_cells_opened_delta: int
    explicit_flag_delta: int


@dataclass(frozen=True)
class Stage3RunResult:
    """Immutable action stream; compute timings are separate from modeled cost."""

    status: GameStatus
    traces: tuple[Stage3ActionTrace, ...]

    def __post_init__(self):
        object.__setattr__(self, "traces", tuple(self.traces))

    @property
    def moves(self) -> tuple[SimpleMove, ...]:
        return tuple(trace.move for trace in self.traces)

    @property
    def total_modeled_us(self) -> int:
        return sum(trace.modeled_action_us for trace in self.traces)


def _hidden_count(observation: Observation) -> int:
    return sum(value == CellState.HIDDEN for row in observation for value in row)


def _action_effect_deltas(
    before: Observation, after: Observation, move: SimpleMove,
) -> tuple[int, int]:
    """Public deltas, deliberately matching Stage 2 without refactoring it."""
    safe_cells_opened = sum(
        old in (CellState.HIDDEN, CellState.FLAGGED) and 0 <= new <= 8
        for before_row, after_row in zip(before, after)
        for old, new in zip(before_row, after_row)
    )
    # Automatic win flags (and flag clearing in a flood) are not physical inputs.
    return safe_cells_opened, int(move.action == Action.FLAG)


def _validate_execution(
    observation: Observation, move: SimpleMove, decision: Stage3Decision | None,
) -> None:
    """Check current public execution evidence, never a virtual plan suffix."""
    height, width = len(observation), len(observation[0])
    if (
        type(move.x) is not int or type(move.y) is not int
        or not (0 <= move.x < width and 0 <= move.y < height)
        or move.action not in (Action.OPEN, Action.FLAG, Action.CHORD)
    ):
        raise Stage3RunnerError("Selected action is outside the public board contract.")
    target = observation[move.y][move.x]
    if decision is None:
        if move != SimpleMove(Action.OPEN, 0, 0) or target != CellState.HIDDEN:
            raise Stage3RunnerError("Initial policy must OPEN the HIDDEN origin.")
        return

    evidence = decision.evidence
    if move != decision.move or evidence.constraints != build_constraints(observation):
        raise Stage3RunnerError("Selected action evidence is not for the current observation.")
    safe, mines = certainty_pool(evidence)
    coordinate = (move.x, move.y)
    if move.action == Action.FLAG:
        if target != CellState.HIDDEN or coordinate not in mines:
            raise Stage3RunnerError("FLAG requires a current-certain HIDDEN mine.")
    elif move.action == Action.OPEN:
        if target != CellState.HIDDEN:
            raise Stage3RunnerError("OPEN requires a HIDDEN target.")
        if coordinate not in safe:
            if (
                evidence.kind != DecisionKind.PROBABILITY_GUESS
                or safe or mines or move != evidence.move
            ):
                raise Stage3RunnerError("OPEN requires current safety or the exact Stage-2 guess.")
    else:
        constraint = next((item for item in evidence.constraints if item.source == coordinate), None)
        if (
            not 1 <= target <= 8 or constraint is None
            or constraint.remaining_mines != 0 or not constraint.hidden_cells
            or not constraint.hidden_cells <= safe
        ):
            raise Stage3RunnerError("CHORD requires a satisfied positive clue and current safe neighbors.")


def run_stage3(
    engine: MinesweeperEngine, *, table: TimingTable | None = None,
    observer: Callable[[Stage3ActionTrace], None] | None = None,
) -> Stage3RunResult:
    """Run an all-HIDDEN board from canonical OPEN (0,0) to WON or LOST.

    Initial cursor is (0,0), and the first input always costs T[0][0] without a
    planner decision. Fixed boards are permitted: first-OPEN safety belongs to
    the caller/engine and is never checked using the answer layout. Progressed
    PLAYING starts are rejected because this API models the canonical full run.
    A terminal engine receives no input, observation, or planner call.

    Each subsequent complete analysis+planning call is timed, then its first
    action is checked against current public evidence and executed. A fresh
    observation and a complete replan follow every nonterminal input, including
    FLAG. Each input must reduce HIDDEN count or terminate, proving progress
    without a wall-clock limit. Observers must not mutate the engine.
    """
    if engine.status in (GameStatus.WON, GameStatus.LOST):
        return Stage3RunResult(status=engine.status, traces=())
    table = load_timing_table() if table is None else validate_timing_table(table)
    if not (1 <= engine.width <= 30 and 1 <= engine.height <= 16):
        raise ValueError("Stage-3 board must fit the frozen 30-by-16 timing table.")
    observation = engine.get_observation()
    hidden_count = _hidden_count(observation)
    if hidden_count != engine.width * engine.height:
        raise ValueError("Canonical Stage-3 runner requires an entirely HIDDEN start.")
    cursor = (0, 0)
    traces = []

    while engine.status == GameStatus.PLAYING:
        decision = None
        decision_compute_ns = None
        if not traces:
            move = SimpleMove(Action.OPEN, 0, 0)
        else:
            started_ns = perf_counter_ns()
            decision = plan_position(observation, engine.num_mines, cursor, table)
            decision_compute_ns = perf_counter_ns() - started_ns
            if decision is None:
                raise Stage3RunnerError("Planner returned no action while PLAYING.")
            move = decision.move
        _validate_execution(observation, move, decision)
        modeled_action_us = action_cost(table, cursor, (move.x, move.y))
        engine.step(move.x, move.y, move.action)
        after = engine.get_observation()
        safe_delta, flag_delta = _action_effect_deltas(observation, after, move)
        new_hidden_count = _hidden_count(after)
        if engine.status == GameStatus.PLAYING and new_hidden_count >= hidden_count:
            raise Stage3RunnerError("Action made no progress: HIDDEN count did not decrease.")
        trace = Stage3ActionTrace(
            move=move, decision=decision, decision_compute_ns=decision_compute_ns,
            cursor_before=cursor, modeled_action_us=modeled_action_us,
            status_after=engine.status, safe_cells_opened_delta=safe_delta,
            explicit_flag_delta=flag_delta,
        )
        traces.append(trace)
        cursor = (move.x, move.y)
        observation, hidden_count = after, new_hidden_count
        if observer is not None:
            observer(trace)

    return Stage3RunResult(status=engine.status, traces=tuple(traces))
