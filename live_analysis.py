"""UI-only projection of existing Simple Algorithm evidence (no solver calls).

Coordinates and probabilities keep their public API meaning: (x, y), P(mine).
Nothing here reads an engine, executes moves, or changes an observation.
"""

from dataclasses import dataclass
from enum import Enum

from core_engine import Action, CellState
from simple_algorithm import Coordinate, Observation, SimpleMove
from simple_decision import DecisionKind, SimpleDecision
from simple_probability import CellProbability


class OverlayKind(Enum):
    SAFE = "safe"
    MINE = "mine"
    GUESS_CANDIDATE = "guess_candidate"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class CellOverlay:
    kind: OverlayKind | None = None
    recommended: bool = False
    probability: CellProbability | None = None


@dataclass(frozen=True)
class LiveAnalysis:
    decision: SimpleDecision | None
    move: SimpleMove | None
    status_text: str
    overlays: dict[Coordinate, CellOverlay]


def format_mine_probability(cell: CellProbability, *, compact: bool = False) -> str:
    """Integer cell percentages, or one decimal for text; never round to certainty."""
    numerator, denominator = cell.mine_worlds, cell.total_worlds
    if numerator == 0:
        return "0%"
    if numerator == denominator:
        return "100%"
    scale = 100 if compact else 1000
    if numerator * scale < denominator:
        return "<1%" if compact else "<0.1%"
    if numerator * scale > (scale - 1) * denominator:
        return ">99%" if compact else ">99.9%"
    rounded = (2 * numerator * scale + denominator) // (2 * denominator)
    if compact:
        return f"{rounded}%"
    return f"{rounded // 10}.{rounded % 10}%"


def is_all_hidden(observation: Observation) -> bool:
    return bool(observation and observation[0]) and all(
        len(row) == len(observation[0])
        and all(value == CellState.HIDDEN for value in row)
        for row in observation
    )


def first_click_presentation() -> LiveAnalysis:
    # Safety belongs to this action's game policy, not every fixed-board cell.
    return LiveAnalysis(
        decision=None,
        move=SimpleMove(Action.OPEN, 0, 0),
        status_text="첫 클릭 추천: OPEN (0, 0)",
        overlays={(0, 0): CellOverlay(recommended=True)},
    )


def present_decision(
    observation: Observation, decision: SimpleDecision | None,
) -> LiveAnalysis:
    """Reuse computed evidence; never reselect the decision's recommended move."""
    if decision is None:
        return LiveAnalysis(None, None, "추천 가능한 수가 없습니다.", {})

    hidden = {
        (x, y) for y, row in enumerate(observation) for x, value in enumerate(row)
        if value == CellState.HIDDEN
    }
    move = decision.move
    recommended = (move.x, move.y)
    overlays = {}
    status = f"추천: {move.action.name} ({move.x}, {move.y})"

    if decision.kind == DecisionKind.LOCAL_DETERMINISTIC:
        for cells, kind in (
            (decision.deterministic_result.safe_cells, OverlayKind.SAFE),
            (decision.deterministic_result.mine_cells, OverlayKind.MINE),
        ):
            for coordinate in cells & hidden:
                overlays[coordinate] = CellOverlay(kind, coordinate == recommended)
    elif decision.probability_result is not None:
        probabilities = [
            cell for cell in decision.probability_result.probabilities
            if cell.coordinate in hidden
        ]
        minimum = min(
            (cell.probability for cell in probabilities
             if 0 < cell.mine_worlds < cell.total_worlds),
            default=None,
        ) if decision.kind == DecisionKind.PROBABILITY_GUESS else None
        for cell in probabilities:
            if cell.mine_worlds == 0:
                kind = OverlayKind.SAFE
            elif cell.mine_worlds == cell.total_worlds:
                kind = OverlayKind.MINE
            elif minimum is not None and cell.probability == minimum:
                kind = OverlayKind.GUESS_CANDIDATE
            else:
                kind = OverlayKind.UNCERTAIN
            overlays[cell.coordinate] = CellOverlay(
                kind, cell.coordinate == recommended, cell,
            )

    if recommended in hidden and recommended not in overlays:
        overlays[recommended] = CellOverlay(recommended=True)
    safe_count = sum(cell.kind == OverlayKind.SAFE for cell in overlays.values())
    mine_count = sum(cell.kind == OverlayKind.MINE for cell in overlays.values())
    if safe_count or mine_count:
        status = f"확정 안전 {safe_count}칸, 확정 지뢰 {mine_count}칸 | {status}"
    selected = overlays.get(recommended)
    if selected is not None and selected.probability is not None:
        cell = selected.probability
        if 0 < cell.mine_worlds < cell.total_worlds:
            status += f" | 지뢰 확률 {format_mine_probability(cell)}"
    return LiveAnalysis(decision, move, status, overlays)


def reduced_number(observation: Observation, x: int, y: int) -> int:
    """Display N-F only; callers must keep the original value for cell state."""
    flags = sum(
        observation[ny][nx] == CellState.FLAGGED
        for ny in range(max(0, y - 1), min(len(observation), y + 2))
        for nx in range(max(0, x - 1), min(len(observation[0]), x + 2))
        if (nx, ny) != (x, y)
    )
    return observation[y][x] - flags
