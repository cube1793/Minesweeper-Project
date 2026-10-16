"""Pure isolated comparison execution and metrics (Slice 2A).

Run each unchanged solver once on the admitted fixed layout. Human Replay,
Stage-2 result/observer traces and Stage-3 result remain separate authorities.
Model C costs are through termination, including losses, never a speed ranking.
There is no worker, UI, persistence or playback coordination here.
"""

from collections import Counter
from dataclasses import dataclass, fields

from benchmark_modeled_time import (
    ModelCEvaluation, authenticate_model_c, evaluate_ordered_actions,
)
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_model import (
    ACTION_CHORD, ACTION_FLAG, ACTION_OPEN, SOURCE_ALGORITHM,
    ReplayBoard, ReplayData, ReplayEvent,
)
from replay_player import ReplayPlayer
from same_board_comparison import ComparisonLayout, HumanComparisonContext
from simple_algorithm import SimpleMove
from simple_decision import SimpleDecision
from simple_runner import SimpleActionTrace, SimpleRunResult, StopReason, run_simple
from stage3_physical import action_cost, validate_timing_table
from stage3_planner import RevealPlan, Stage3Decision
from stage3_runner import Stage3ActionTrace, Stage3RunResult, run_stage3


class ComparisonExecutionError(ValueError):
    """Execution evidence disagrees with the admitted layout or recorded run."""


@dataclass(frozen=True)
class ActionCounts:
    semantic_action_count: int
    open_count: int
    flag_input_count: int
    chord_count: int


@dataclass(frozen=True)
class HumanMetrics:
    outcome: GameStatus
    actions: ActionCounts
    replay_elapsed_seconds: float


@dataclass(frozen=True)
class SolverMetrics:
    """Stage-2 post-hoc or Stage-3 recorded Model C cost, separately from compute.

    decision_compute_total_ns sums only existing non-None measurements. Zero for
    an immediate terminal first input is an empty sum, not a measured decision.
    Individual traces retain None; their measurement scopes remain unchanged.
    """

    outcome: GameStatus
    actions: ActionCounts
    model_c_total_us: int
    decision_compute_total_ns: int


@dataclass(frozen=True)
class SameBoardExecution:
    """Validated output of run_same_board_comparison, without live engines.

    Retains native result/trace references, not normalized action streams.
    Stage-2 metrics use the authenticated post-hoc evaluator; Stage-3 metrics
    use its frozen runner's recorded total, independently checked by that same
    evaluator. This output container itself does not execute or validate runs.
    """

    context: HumanComparisonContext
    stage2_result: SimpleRunResult
    stage2_traces: tuple[SimpleActionTrace, ...]
    stage3_result: Stage3RunResult
    model_c_evaluation: ModelCEvaluation
    human_metrics: HumanMetrics
    stage2_metrics: SolverMetrics
    stage3_metrics: SolverMetrics

    def __post_init__(self):
        object.__setattr__(self, "stage2_traces", tuple(self.stage2_traces))


@dataclass(frozen=True)
class SolverExecution:
    """Solver-only evidence for the private worker boundary; no Human recording.

    The layout is independently recomputed from the input board. Native action
    streams are retained, not normalized. Like SameBoardExecution this is a
    passive immutable container: composition revalidates comparison/outcome
    facts, not the complete nested decision-evidence graph.
    """

    layout: ComparisonLayout
    stage2_result: SimpleRunResult
    stage2_traces: tuple[SimpleActionTrace, ...]
    stage3_result: Stage3RunResult
    model_c_evaluation: ModelCEvaluation
    stage2_metrics: SolverMetrics
    stage3_metrics: SolverMetrics

    def __post_init__(self):
        object.__setattr__(self, "stage2_traces", tuple(self.stage2_traces))


def _validated_layout(board: ReplayBoard) -> ComparisonLayout:
    # Pickle does not call dataclass constructors. Reapply the existing board
    # validation and recompute identity, never trust a transported fingerprint.
    _require_native(board, ReplayBoard)
    if type(board.mine_positions) is not frozenset or any(
        type(value) is not int for value in (board.width, board.height, board.num_mines)
    ):
        raise ComparisonExecutionError("An immutable ReplayBoard is required.")
    for coordinate in board.mine_positions:
        _validate_coordinate(coordinate, board)
    ReplayBoard(board.width, board.height, board.num_mines, board.mine_positions)
    if not (1 <= board.width <= 30 and 1 <= board.height <= 16):
        raise ComparisonExecutionError("Comparison board must fit frozen Stage-3 dimensions.")
    return ComparisonLayout(board)


def _require_native(value, expected_type) -> None:
    """Check one relied-upon native object's type/field names, without recursion.

    Class defaults are legitimate (notably ModelCEvaluation's frozen identity).
    Decision-internal constraint/probability contents are trusted-local evidence;
    neither their contents nor their immutability are exhaustively revalidated.
    """
    if type(value) is not expected_type:
        raise ComparisonExecutionError(f"Exact native {expected_type.__name__} is required.")
    names = {field.name for field in fields(expected_type)}
    present = vars(value).keys()
    if present - names or any(not hasattr(expected_type, name) for name in names - present):
        raise ComparisonExecutionError("Unexpected or missing attributes in native solver evidence.")


def _validate_coordinate(coordinate, board) -> None:
    if (
        type(coordinate) is not tuple or len(coordinate) != 2
        or any(type(value) is not int for value in coordinate)
        or not (0 <= coordinate[0] < board.width and 0 <= coordinate[1] < board.height)
    ):
        raise ComparisonExecutionError("Coordinate must be a tuple of two exact in-bounds integers.")


def _validate_move(move, board) -> None:
    _require_native(move, SimpleMove)
    if type(move.action) is not Action:
        raise ComparisonExecutionError("Native Action is required.")
    _validate_coordinate((move.x, move.y), board)


def _validate_trace_types(traces, trace_type, decision_type, board):
    for index, trace in enumerate(traces):
        _require_native(trace, trace_type)
        _validate_move(trace.move, board)
        if type(trace.status_after) is not GameStatus:
            raise ComparisonExecutionError("Native status evidence is required.")
        if any(type(value) is not int or value < 0 for value in (
            trace.safe_cells_opened_delta, trace.explicit_flag_delta,
        )):
            raise ComparisonExecutionError("Trace deltas must be exact nonnegative integers, excluding bool.")
        if trace_type is Stage3ActionTrace:
            _validate_coordinate(trace.cursor_before, board)
        if index == 0:
            if trace.decision is not None:
                raise ComparisonExecutionError("Canonical first input must have no decision.")
            continue
        _require_native(trace.decision, decision_type)
        _validate_move(trace.decision.move, board)
        if trace.decision.move != trace.move:
            raise ComparisonExecutionError("Recorded decision and executed move disagree.")
        if decision_type is Stage3Decision:
            _require_native(trace.decision.evidence, SimpleDecision)
            if trace.decision.plan is not None:
                _require_native(trace.decision.plan, RevealPlan)


def _counts(actions) -> ActionCounts:
    counts = Counter(actions)
    return ActionCounts(
        sum(counts.values()), counts[ACTION_OPEN], counts[ACTION_FLAG], counts[ACTION_CHORD],
    )


def _compute_total(traces) -> int:
    if traces[0].decision_compute_ns is not None or traces[0].decision is not None:
        raise ComparisonExecutionError("Canonical first input must have no decision measurement.")
    total = 0
    for trace in traces:
        measured = trace.decision_compute_ns
        if measured is not None:
            if type(measured) is not int or measured < 0:
                raise ComparisonExecutionError("Decision compute measurements must be nonnegative integer ns.")
            total += measured
    return total


def _verify_engine_layout(engine: MinesweeperEngine, layout: ComparisonLayout) -> None:
    snapshot = engine.get_board_snapshot()
    installed = ComparisonLayout(ReplayBoard(
        snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines,
    ))
    if not snapshot.mines_placed or installed != layout:
        raise ComparisonExecutionError("Solver engine layout differs from the admitted exact layout.")


def _fixed_engine(layout: ComparisonLayout) -> MinesweeperEngine:
    board = layout.board
    engine = MinesweeperEngine(board.width, board.height, board.num_mines)
    engine.reset_with_mines(board.width, board.height, board.num_mines, board.mine_positions)
    _verify_engine_layout(engine, layout)
    if engine.status != GameStatus.PLAYING or any(
        cell != CellState.HIDDEN for row in engine.get_observation() for cell in row
    ):
        raise ComparisonExecutionError("Comparison solver requires a fresh all-HIDDEN PLAYING board.")
    return engine


def _modeled_total(traces, result_status, total_actions, board, evaluation) -> int:
    return evaluate_ordered_actions(
        ((index, trace.move.action, trace.move.x, trace.move.y, trace.status_after)
         for index, trace in enumerate(traces)),
        total_actions=total_actions, terminal_status=result_status,
        width=board.width, height=board.height, evaluation=evaluation,
    )


def _validate_stage2(layout, result, traces, evaluation, engine=None) -> int:
    _require_native(result, SimpleRunResult)
    if (
        type(result.status) is not GameStatus or type(result.stop_reason) is not StopReason
        or result.status not in (GameStatus.WON, GameStatus.LOST)
        or result.stop_reason != (StopReason.WON if result.status == GameStatus.WON else StopReason.LOST)
        or result.pending_decision is not None or result.started_from_hidden is not True
    ):
        raise ComparisonExecutionError("Stage 2 must complete its hidden-start run, without a guess pause.")
    replay = result.replay_data
    _require_native(replay, ReplayData)
    if (
        type(replay) is not ReplayData or type(replay.events) is not tuple
        or type(result.moves) is not tuple or type(traces) is not tuple
        or replay.source_type != SOURCE_ALGORITHM or replay.mouse_trace is not None
        or any(type(event) is not ReplayEvent for event in replay.events)
    ):
        raise ComparisonExecutionError("Stage-2 native algorithm Replay and immutable streams are required.")
    if _validated_layout(replay.board) != layout:
        raise ComparisonExecutionError("Stage-2 Replay layout differs from the admitted exact layout.")
    events = replay.events
    if len(traces) != len(result.moves) or len(events) != len(traces):
        raise ComparisonExecutionError("Stage-2 result, Replay and trace action counts disagree.")
    _validate_trace_types(traces, SimpleActionTrace, SimpleDecision, layout.board)
    # Recheck native Replay structure after pickle without replacing its authority.
    for event in replay.events:
        _require_native(event, ReplayEvent)
        ReplayEvent(event.elapsed_time, event.x, event.y, event.action)
    ReplayData(replay.board, replay.events, replay.source_type, replay.schema_version, replay.mouse_trace)
    for move, trace, event in zip(result.moves, traces, events):
        _validate_move(move, layout.board)
        if move != trace.move or (event.action, event.x, event.y) != (move.action.name, move.x, move.y):
            raise ComparisonExecutionError("Stage-2 result, Replay and trace action order disagree.")
    total_us = _modeled_total(traces, result.status, len(result.moves), layout.board, evaluation)

    # Independently reconstruct the native Replay and check every trace status.
    player = ReplayPlayer(result.replay_data)
    for trace in traces:
        player.next()
        if player.engine.status != trace.status_after:
            raise ComparisonExecutionError("Stage-2 status disagrees with Replay reconstruction.")
    if engine is not None:
        _verify_engine_layout(engine, layout)
        if engine.status != result.status or engine.get_observation() != player.get_observation():
            raise ComparisonExecutionError("Stage-2 execution and reconstructed terminal state disagree.")
    return total_us


def _validate_stage3(layout, result, evaluation, engine=None) -> None:
    _require_native(result, Stage3RunResult)
    if type(result.traces) is not tuple:
        raise ComparisonExecutionError("Stage-3 traces must be an immutable tuple.")
    _validate_trace_types(result.traces, Stage3ActionTrace, Stage3Decision, layout.board)
    evaluated_us = _modeled_total(result.traces, result.status, len(result.traces), layout.board, evaluation)
    cursor = (0, 0)
    # Validation only: no benchmark-shaped wrapper or playback controller.
    reconstructed = _fixed_engine(layout)
    for trace in result.traces:
        if trace.cursor_before != cursor or type(trace.modeled_action_us) is not int or trace.modeled_action_us <= 0:
            raise ComparisonExecutionError("Invalid Stage-3 recorded cursor or modeled cost.")
        if trace.modeled_action_us != action_cost(evaluation.table, cursor, (trace.move.x, trace.move.y)):
            raise ComparisonExecutionError("Stage-3 recorded action cost differs from independent evaluation.")
        reconstructed.step(trace.move.x, trace.move.y, trace.move.action)
        if reconstructed.status != trace.status_after:
            raise ComparisonExecutionError("Stage-3 status disagrees with fixed-board reconstruction.")
        cursor = (trace.move.x, trace.move.y)
    if evaluated_us != result.total_modeled_us:
        raise ComparisonExecutionError("Stage-3 recorded Model C total differs from independent evaluation.")
    if engine is not None:
        _verify_engine_layout(engine, layout)
        if engine.status != result.status or engine.get_observation() != reconstructed.get_observation():
            raise ComparisonExecutionError("Stage-3 execution and reconstructed terminal state disagree.")


def run_fixed_layout_solvers(board: ReplayBoard) -> SolverExecution:
    """Run each solver once from a validated board, without any Human input.

    Layout truth is confined to engine setup and result validation. The unchanged
    solver boundaries receive only their own engines and existing options; no
    Human actions, Mouse Trace, fingerprint or benchmark metadata is supplied.
    Exceptions propagate; losses are returned without retries or regeneration.
    """
    layout = _validated_layout(board)
    evaluation = authenticate_model_c()
    stage2_engine = _fixed_engine(layout)
    collected = []
    stage2 = run_simple(
        stage2_engine, accept_guesses=True, initial_open=(0, 0), observer=collected.append,
    )
    stage2_traces = tuple(collected)
    stage2_us = _validate_stage2(layout, stage2, stage2_traces, evaluation, stage2_engine)
    stage2_compute_ns = _compute_total(stage2_traces)

    stage3_engine = _fixed_engine(layout)
    stage3 = run_stage3(stage3_engine, table=evaluation.table)
    _validate_stage3(layout, stage3, evaluation, stage3_engine)
    stage3_compute_ns = _compute_total(stage3.traces)

    return SolverExecution(
        layout=layout, stage2_result=stage2, stage2_traces=stage2_traces,
        stage3_result=stage3, model_c_evaluation=evaluation,
        stage2_metrics=SolverMetrics(
            stage2.status, _counts(trace.move.action.name for trace in stage2_traces),
            stage2_us, stage2_compute_ns,
        ),
        stage3_metrics=SolverMetrics(
            stage3.status, _counts(trace.move.action.name for trace in stage3.traces),
            stage3.total_modeled_us, stage3_compute_ns,
        ),
    )


def _compose_validated(context, execution) -> SameBoardExecution:
    """Retain native evidence and the exact original parent-owned Human context."""
    return SameBoardExecution(
        context=context, stage2_result=execution.stage2_result,
        stage2_traces=execution.stage2_traces, stage3_result=execution.stage3_result,
        model_c_evaluation=execution.model_c_evaluation,
        human_metrics=HumanMetrics(
            context.terminal_status, _counts(event.action for event in context.human_replay.events),
            context.human_replay.events[-1].elapsed_time,
        ),
        stage2_metrics=execution.stage2_metrics, stage3_metrics=execution.stage3_metrics,
    )


def _verify_metrics(actual, expected):
    _require_native(actual, SolverMetrics)
    _require_native(actual.actions, ActionCounts)
    if (
        type(actual) is not SolverMetrics or type(actual.actions) is not ActionCounts
        or type(actual.outcome) is not GameStatus
        or any(type(value) is not int for value in (
            actual.model_c_total_us, actual.decision_compute_total_ns,
            actual.actions.semantic_action_count, actual.actions.open_count,
            actual.actions.flag_input_count, actual.actions.chord_count,
        ))
        or actual != expected
    ):
        raise ComparisonExecutionError("Transported solver metrics disagree with native execution evidence.")


def compose_same_board_execution(
    context: HumanComparisonContext, execution: SolverExecution,
) -> SameBoardExecution:
    """Validate private transported solver facts and attach the retained context.

    Reauthenticate Model C locally, recompute exact layout identity and reconstruct
    both native streams; no solver is rerun and no Human context is reconstructed.
    Validation covers comparison/outcome-bearing facts and shallow decision types
    and relationships. Native constraint/probability/plan evidence is preserved,
    but its complete nested graph is not traversed on the parent/Qt thread.
    This is trusted-local transport, not exhaustive decision reanalysis or an
    immutability/security proof for arbitrary pickles.
    """
    if not isinstance(context, HumanComparisonContext):
        raise ComparisonExecutionError("An admitted HumanComparisonContext is required.")
    _require_native(execution, SolverExecution)
    _require_native(execution.layout, ComparisonLayout)
    layout = _validated_layout(execution.layout.board)
    if layout != execution.layout or layout != context.layout:
        raise ComparisonExecutionError("Solver execution layout differs from the retained Human layout.")
    evaluation = authenticate_model_c()
    transported = execution.model_c_evaluation
    _require_native(transported, ModelCEvaluation)
    if type(transported) is not ModelCEvaluation or any(
        type(getattr(transported, item.name)) is not type(getattr(evaluation, item.name))
        or getattr(transported, item.name) != getattr(evaluation, item.name)
        for item in fields(ModelCEvaluation)
    ):
        raise ComparisonExecutionError("Transported Model C differs from locally authenticated Model C.")
    if any(type(row) is not tuple for row in transported.table) or any(
        type(coordinate) is not int for coordinate in transported.initial_cursor
    ):
        raise ComparisonExecutionError("Transported Model C must retain immutable integer values.")
    validate_timing_table(transported.table)
    stage2_us = _validate_stage2(
        layout, execution.stage2_result, execution.stage2_traces, evaluation,
    )
    _validate_stage3(layout, execution.stage3_result, evaluation)
    for traces, status, modeled_us, metrics in (
        (execution.stage2_traces, execution.stage2_result.status, stage2_us, execution.stage2_metrics),
        (execution.stage3_result.traces, execution.stage3_result.status,
         execution.stage3_result.total_modeled_us, execution.stage3_metrics),
    ):
        _verify_metrics(metrics, SolverMetrics(
            status, _counts(trace.move.action.name for trace in traces),
            modeled_us, _compute_total(traces),
        ))
    return _compose_validated(context, execution)


def run_same_board_comparison(context: HumanComparisonContext) -> SameBoardExecution:
    """Compatible synchronous convenience path; execute and validate each run once.

    Locally produced evidence has already passed the same reconstruction checks.
    The transport composition entry point additionally reauthenticates incoming
    Model C and rechecks the serialized result; no transport is used here.
    """
    if not isinstance(context, HumanComparisonContext):
        raise ComparisonExecutionError("An admitted HumanComparisonContext is required.")
    return _compose_validated(context, run_fixed_layout_solvers(context.layout.board))
