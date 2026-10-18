"""Reconstruct one fixed board from an already validated recorded timeline.

This layer owns execution effects, not source authentication, board generation,
decisions, Model C evaluation or presentation. Answer-derived board references
and current-Engine counters are separate from public observations and telemetry.
"""

from dataclasses import dataclass

from board_analyzer import analyze_board
from board_snapshot import BoardSnapshot
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from telemetry_model import ActionEvent, GameRecord
from timeline_analytics import TimelineAction, TimelineAnalytics


@dataclass(frozen=True)
class BoardReferenceMetrics:
    """Static answer-derived reference values, never solver-visible evidence."""

    total_3bv: int
    total_ops: int
    isolated_number_count: int


@dataclass(frozen=True)
class ReconstructedFrame:
    """Public observation after a completed prefix, including terminal feedback."""

    observation: tuple[tuple[int, ...], ...]
    status: GameStatus


@dataclass(frozen=True)
class FrameCounterSummary:
    """Current-Engine prefix facts, without reconstruction time or rates.

    Click strings preserve the public Engine's PLAYING/terminal presentation.
    Raw progress is separate from the Engine's masked PLAYING stats strings.
    """

    status: GameStatus
    active_clicks: int
    wasted_clicks: int
    completed_3bv: int
    completed_ops: int
    clicks_text: str
    left_text: str
    right_text: str
    chord_text: str


@dataclass(frozen=True)
class FinalCounterSummary:
    """Final current-Engine reference facts, not historical solver telemetry.

    Only public raw totals and non-time formatted statistics are retained.
    Mechanical active/wasted names imply no strategic judgment.
    """

    status: GameStatus
    active_clicks: int
    wasted_clicks: int
    completed_3bv: int
    bbbv_text: str
    ops_text: str
    clicks_text: str
    left_text: str
    right_text: str
    chord_text: str


@dataclass(frozen=True)
class ExemplarBoardReconstruction:
    """Immutable lookup data; no mutable Engine or navigation state is retained.

    Action ordinal j uses frames[j-1] and frames[j]. Frame zero has no event.
    The original board holds static answers separately from all public frames.
    Costs, geometry and original event metadata remain solely on timeline.
    """

    board_snapshot: BoardSnapshot
    timeline: TimelineAnalytics
    board_reference: BoardReferenceMetrics
    frames: tuple[ReconstructedFrame, ...]
    frame_counters: tuple[FrameCounterSummary, ...]
    newly_revealed_safe_by_action: tuple[frozenset[tuple[int, int]], ...]
    final_counters: FinalCounterSummary


def _frame(engine: MinesweeperEngine) -> ReconstructedFrame:
    return ReconstructedFrame(
        observation=tuple(tuple(row) for row in engine.get_observation()),
        status=engine.status,
    )


def _frame_counters(engine: MinesweeperEngine) -> FrameCounterSummary:
    counters = engine.get_counter_snapshot()
    stats = engine.get_stats()
    return FrameCounterSummary(
        status=counters["status"], active_clicks=counters["active_clicks"],
        wasted_clicks=counters["wasted_clicks"], completed_3bv=counters["completed_3bv"],
        completed_ops=counters["completed_ops"], clicks_text=stats["clicks"],
        left_text=stats["left"], right_text=stats["right"], chord_text=stats["chord"],
    )


def reconstruct_board(
    board_snapshot: BoardSnapshot, timeline: TimelineAnalytics,
) -> ExemplarBoardReconstruction:
    """Apply original events to a finalized fixed board, or raise ValueError.

    The caller supplies a complete TimelineAnalytics from project_timeline();
    model authentication, costs and recorded summaries are not reevaluated here.
    Local board consistency, public effects and termination are checked here.
    All work stays local until success; neither caller-owned input is mutated.
    This is not official source/fingerprint authentication or exemplar admission.
    """
    if not isinstance(board_snapshot, BoardSnapshot) or board_snapshot.mines_placed is not True:
        raise ValueError("board_snapshot must be a finalized BoardSnapshot.")
    if not isinstance(timeline, TimelineAnalytics) or not isinstance(timeline.record, GameRecord):
        raise ValueError("timeline must be a validated TimelineAnalytics with a GameRecord.")
    if (
        not isinstance(timeline.actions, tuple)
        or not timeline.actions
        or len(timeline.actions) != timeline.record.total_actions
    ):
        raise ValueError("timeline must contain the complete ordered action tuple.")

    engine = MinesweeperEngine()
    engine.reset_with_mines(
        board_snapshot.width, board_snapshot.height,
        board_snapshot.num_mines, board_snapshot.mines,
    )
    if (
        any(type(value) is not int for row in board_snapshot.adjacent for value in row)
        or engine.get_board_snapshot() != board_snapshot
    ):
        raise ValueError("Fixed Engine board disagrees with supplied BoardSnapshot adjacency/layout.")

    analysis = analyze_board(board_snapshot)
    if analysis.total_3bv != timeline.record.board_3bv:
        raise ValueError("Board total_3bv disagrees with GameRecord.board_3bv.")
    if analysis.total_ops != timeline.record.board_ops:
        raise ValueError("Board total_ops disagrees with GameRecord.board_ops.")
    reference = BoardReferenceMetrics(
        analysis.total_3bv, analysis.total_ops, analysis.total_3bv - analysis.total_ops,
    )

    frames = [_frame(engine)]
    frame_counters = [_frame_counters(engine)]
    new_safe_sets = []
    for index, item in enumerate(timeline.actions):
        if not isinstance(item, TimelineAction) or not isinstance(item.event, ActionEvent):
            raise ValueError(f"Action {index + 1} must retain an original ActionEvent.")
        event = item.event
        if event.action_index != index:
            raise ValueError("Action indices must be consecutive and ordered from zero.")
        if not isinstance(event.action_type, Action) or not isinstance(event.status_after, GameStatus):
            raise ValueError(f"Action {index + 1} requires public Action/GameStatus enums.")
        if not (0 <= event.x < board_snapshot.width and 0 <= event.y < board_snapshot.height):
            raise ValueError(f"Action {index + 1} target is outside the supplied board.")
        if engine.status != GameStatus.PLAYING:
            raise ValueError(f"Action {index + 1} follows terminal state.")

        before = frames[-1]
        expected_flag_delta = 1 if event.action_type == Action.FLAG else 0
        if event.explicit_flag_delta != expected_flag_delta:
            raise ValueError(f"Action {index + 1} has incompatible explicit_flag_delta.")
        if event.action_type == Action.FLAG and before.observation[event.y][event.x] != CellState.HIDDEN:
            raise ValueError(f"Action {index + 1} FLAG target must be HIDDEN; UNFLAG is unsupported.")

        engine.step(event.x, event.y, event.action_type)
        after = _frame(engine)
        if after.status != event.status_after:
            raise ValueError(f"Action {index + 1} reconstructed status disagrees with status_after.")
        if event.action_type == Action.FLAG and after.observation[event.y][event.x] != CellState.FLAGGED:
            raise ValueError(f"Action {index + 1} did not produce the recorded explicit FLAG.")

        new_safe = frozenset(
            (x, y)
            for y, (old_row, new_row) in enumerate(zip(before.observation, after.observation))
            for x, (old, new) in enumerate(zip(old_row, new_row))
            if old in (CellState.HIDDEN, CellState.FLAGGED) and 0 <= new <= 8
        )
        if len(new_safe) != event.safe_cells_opened_delta:
            raise ValueError(f"Action {index + 1} reconstructed safe reveal delta disagrees with telemetry.")
        frames.append(after)
        frame_counters.append(_frame_counters(engine))
        new_safe_sets.append(new_safe)

    expected_status = {"WIN": GameStatus.WON, "LOSS": GameStatus.LOST}[timeline.record.result]
    if engine.status not in (GameStatus.WON, GameStatus.LOST) or engine.status != expected_status:
        raise ValueError("Final reconstructed outcome disagrees with the terminal GameRecord.")

    counters = engine.get_counter_snapshot()
    stats = engine.get_stats()
    final = FinalCounterSummary(
        status=counters["status"], active_clicks=counters["active_clicks"],
        wasted_clicks=counters["wasted_clicks"], completed_3bv=counters["completed_3bv"],
        bbbv_text=stats["bbbv"], ops_text=stats["ops"], clicks_text=stats["clicks"],
        left_text=stats["left"], right_text=stats["right"], chord_text=stats["chord"],
    )
    return ExemplarBoardReconstruction(
        board_snapshot=board_snapshot, timeline=timeline, board_reference=reference,
        frames=tuple(frames), frame_counters=tuple(frame_counters),
        newly_revealed_safe_by_action=tuple(new_safe_sets),
        final_counters=final,
    )
