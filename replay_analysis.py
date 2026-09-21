"""Read-only, on-demand analysis of a replay's current public position.

Index i means events[:i] have been applied; events[i] is only consulted after
the recommendation is computed. No engine, snapshot or ReplayBoard is accepted.
Schema v1 has no initial-state/segment metadata: index 0 + all HIDDEN follows
the full-game fresh-start policy, even for a Stage 2-3 continuation/suffix replay
whose original starting position cannot be reconstructed from that segment.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from core_engine import CellState, GameStatus
from live_analysis import (
    LiveAnalysis, OverlayKind, first_click_presentation, is_all_hidden,
    present_decision,
)
from replay_model import ACTION_FLAG, ACTION_OPEN, ReplayEvent
from simple_algorithm import Observation
from simple_decision import DecisionKind, analyze_position


class ReplayComparisonKind(Enum):
    EXACT_RECOMMENDATION = "exact_recommendation"
    EQUIVALENT_CANDIDATE = "equivalent_candidate"
    DIFFERENT = "different"
    UNSUPPORTED_ACTUAL = "unsupported_actual"
    NO_NEXT_ACTION = "no_next_action"


@dataclass(frozen=True)
class ReplayStepAnalysis:
    current_index: int
    # None means terminal: there is no solver recommendation/presentation.
    presentation: LiveAnalysis | None
    next_event: ReplayEvent | None
    comparison_kind: ReplayComparisonKind
    comparison_text: str

    @property
    def status_text(self) -> str:
        if self.presentation is None:
            return "게임 종료"
        return f"{self.presentation.status_text}\n{self.comparison_text}"


def compare_replay_action(
    observation: Observation,
    presentation: LiveAnalysis | None,
    actual: ReplayEvent | None,
) -> ReplayComparisonKind:
    """Compare existing evidence, without selecting a move or running a solver."""
    kind = ReplayComparisonKind
    if actual is None:
        return kind.NO_NEXT_ACTION
    if presentation is None or actual.action not in (ACTION_OPEN, ACTION_FLAG):
        return kind.UNSUPPORTED_ACTUAL
    if not (0 <= actual.y < len(observation)
            and 0 <= actual.x < len(observation[actual.y])):
        return kind.UNSUPPORTED_ACTUAL
    if observation[actual.y][actual.x] != CellState.HIDDEN:
        # FLAG on FLAGGED means UNFLAG. Opened/flagged targets are also outside
        # the solver's hidden-cell OPEN/FLAG action contract (wasted actions).
        return kind.UNSUPPORTED_ACTUAL
    move = presentation.move
    if move is not None and (actual.action, actual.x, actual.y) == (
        move.action.name, move.x, move.y,
    ):
        return kind.EXACT_RECOMMENDATION
    overlay = presentation.overlays.get((actual.x, actual.y))
    if overlay is not None:
        if actual.action == ACTION_OPEN and overlay.kind == OverlayKind.SAFE:
            return kind.EQUIVALENT_CANDIDATE
        if actual.action == ACTION_FLAG and overlay.kind == OverlayKind.MINE:
            return kind.EQUIVALENT_CANDIDATE
        if (actual.action == ACTION_OPEN
                and overlay.kind == OverlayKind.GUESS_CANDIDATE
                and presentation.decision is not None
                and presentation.decision.kind == DecisionKind.PROBABILITY_GUESS):
            return kind.EQUIVALENT_CANDIDATE
    # FIRST_CLICK has no SAFE evidence: another opening is simply different
    # from Stage 2's deterministic OPEN (0, 0) baseline, never called a mistake.
    return kind.DIFFERENT


def _comparison_text(observation, presentation, actual, kind) -> str:
    if actual is None:
        return "다음 실제 수 없음"
    label = actual.action
    if (label == ACTION_FLAG and actual.y < len(observation)
            and actual.x < len(observation[actual.y])
            and observation[actual.y][actual.x] == CellState.FLAGGED):
        label = "FLAG (UNFLAG)"
    message = {
        ReplayComparisonKind.EXACT_RECOMMENDATION: "추천과 일치",
        ReplayComparisonKind.DIFFERENT: "추천과 다름",
        ReplayComparisonKind.UNSUPPORTED_ACTUAL: "Simple Algorithm 비교 대상 아님",
    }.get(kind)
    if kind == ReplayComparisonKind.EQUIVALENT_CANDIDATE:
        overlay = presentation.overlays[(actual.x, actual.y)]
        message = {
            OverlayKind.SAFE: "동등한 확정 안전",
            OverlayKind.MINE: "동등한 확정 지뢰",
            OverlayKind.GUESS_CANDIDATE: "동등한 최소 위험 후보",
        }[overlay.kind]
    return f"실제 다음 수: {label} ({actual.x}, {actual.y}) | {message}"


def analyze_replay_step(
    observation: Observation,
    num_mines: int,
    *,
    current_index: int,
    events: Sequence[ReplayEvent],
    status: GameStatus,
) -> ReplayStepAnalysis:
    """Analyze events[:current_index], then compare events[current_index].

    The caller supplies the corresponding public observation/status. Errors are
    propagated for the UI to contain; no inputs are mutated and no moves executed.
    Local certainty reuses analyze_position's probability-free path unchanged.
    """
    if (isinstance(current_index, bool) or not isinstance(current_index, int)
            or not 0 <= current_index <= len(events)):
        raise ValueError("Replay index is out of range.")
    if status not in (GameStatus.PLAYING, GameStatus.WON, GameStatus.LOST):
        raise ValueError("Unsupported replay status.")
    if status != GameStatus.PLAYING:
        presentation = None
    elif current_index == 0 and is_all_hidden(observation):
        presentation = first_click_presentation()
    else:
        decision = analyze_position(observation, num_mines)
        presentation = present_decision(observation, decision)

    actual = events[current_index] if current_index < len(events) else None
    kind = compare_replay_action(observation, presentation, actual)
    return ReplayStepAnalysis(
        current_index, presentation, actual, kind,
        _comparison_text(observation, presentation, actual, kind),
    )
