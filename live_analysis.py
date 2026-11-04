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


def present_flag_preparation(policy, target, retained, removable, scope) -> LiveAnalysis:
    x, y = target
    status = (f"{policy} 깃발 확인/정리 | 미확인 깃발 해제 ({x}, {y}) · "
              f"확인한 지뢰 유지 {retained}개 · 해제 {removable}개 | "
              f"미확인 깃발은 실제 지뢰여도 해제될 수 있습니다. {scope}")
    return LiveAnalysis(None, SimpleMove(Action.FLAG, x, y), status,
                        {target: CellOverlay(recommended=True)})


def present_v1_proposal(proposal) -> LiveAnalysis:
    """Project the worker's existing evidence and selected first input only."""
    if proposal.is_flag_review:
        review = proposal.review
        # A preparation toggle is neither an OPEN nor a frozen selected move.
        # In particular it must not display pre-review flag-conditioned certainty.
        return present_flag_preparation("V1", (proposal.x, proposal.y), len(review.proved_mine),
                                        len(review.removable), "공개 단서·총수의 직접 추론 범위입니다.")
    overlays = {}
    recommended = (proposal.x, proposal.y)
    for cell in proposal.overlays:
        probability = None
        if cell.mine_worlds is not None:
            probability = CellProbability((cell.x, cell.y), cell.mine_worlds, cell.total_worlds)
        overlays[(cell.x, cell.y)] = CellOverlay(
            OverlayKind(cell.kind) if cell.kind is not None else None,
            (cell.x, cell.y) == recommended,
            probability,
        )
    # CHORD's selected target is a revealed clue, not a HIDDEN evidence cell.
    previous = overlays.get(recommended, CellOverlay())
    overlays[recommended] = CellOverlay(previous.kind, True, previous.probability)
    prefix = "첫 입력" if proposal.kind == "initial" else ("추측" if proposal.is_guess else "확정 수")
    status = f"Stage3 V1 | {prefix}: {proposal.action} ({proposal.x}, {proposal.y})"
    selected = overlays[recommended].probability
    if selected is not None and 0 < selected.mine_worlds < selected.total_worlds:
        status += f" | 지뢰 확률 {format_mine_probability(selected)}"
    return LiveAnalysis(None, proposal.move, status, overlays)


def present_k_proposal(proposal) -> LiveAnalysis:
    """Display the actual retained K-family choice, without another analysis."""
    from live_k_policy import policy_label
    label = policy_label(proposal.snapshot.policy_id)
    if proposal.is_preparation:
        summary = proposal.snapshot.bootstrap
        return present_flag_preparation(label, (proposal.x, proposal.y), len(summary.retained),
                                        len(summary.removable), "K native local 확인 범위입니다.")
    prefix = "첫 입력" if proposal.initial else "추측" if proposal.is_guess else "확정 수"
    status = f"{label} | {prefix}: {proposal.action} ({proposal.x}, {proposal.y})"
    recommended = (proposal.x, proposal.y)
    overlays = {cell: CellOverlay(OverlayKind.SAFE) for cell in proposal.safe_cells}
    for x, y in proposal.preinput_m:
        if proposal.snapshot.observation[y][x] == CellState.HIDDEN:
            overlays[(x, y)] = CellOverlay(OverlayKind.MINE)
    exact = proposal.probabilities
    if exact is not None:
        for x, y, numerator in exact.cells:
            coordinate = (x, y)
            kind = (OverlayKind.GUESS_CANDIDATE if coordinate in exact.minimum_risk_cells
                    else OverlayKind.UNCERTAIN)
            overlays[coordinate] = CellOverlay(
                kind, coordinate == recommended, CellProbability(coordinate, numerator, exact.total_worlds))
        status += f" | 지뢰 확률 {format_mine_probability(overlays[recommended].probability)}"
    # A revealed CHORD target gets a border only. A selected HIDDEN FLAG target
    # keeps its logical mine color; neither color writes a physical FLAG.
    previous = overlays.get(recommended, CellOverlay())
    overlays[recommended] = CellOverlay(previous.kind, True, previous.probability)
    return LiveAnalysis(None, proposal.move, status, overlays)
