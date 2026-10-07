"""Adapt one executed Stage-3 trace using its already-computed public evidence.

The runner owns current-observation validation, including a CHORD's positive
revealed clue: neither Constraint nor Stage3ActionTrace retains its value.
This adapter checks the retained evidence, never reanalyzes a board, executes
an action, or emits an unexecuted plan suffix. Timing is passed through.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from core_engine import Action
from simple_algorithm import SimpleMove
from simple_decision import DecisionKind
from simple_telemetry import decision_to_telemetry
from stage3_planner import Stage3PlanningError, certainty_pool
from telemetry_model import InferenceCategory

if TYPE_CHECKING:
    from stage3_runner import Stage3ActionTrace


_INFERENCE_CATEGORIES = {
    DecisionKind.LOCAL_DETERMINISTIC: InferenceCategory.LOCAL_DETERMINISTIC,
    DecisionKind.GLOBAL_CERTAINTY: InferenceCategory.GLOBAL_CERTAINTY,
    DecisionKind.PROBABILITY_GUESS: InferenceCategory.PROBABILITY_GUESS,
}


@dataclass(frozen=True)
class Stage3ActionTelemetry:
    """Semantic V2 metadata for one executed action, including policy OPEN."""

    inference_category: InferenceCategory | None
    selection_candidate_count: None
    target_mine_probability: Fraction | None
    minimum_available_mine_probability: Fraction | None
    decision_compute_ns: int | None


def trace_to_telemetry(trace: "Stage3ActionTrace") -> Stage3ActionTelemetry:
    """Translate retained evidence, failing closed on semantic inconsistency.

    Certainty describes the executed move, which can differ from Stage 2's
    recommendation. Only guesses retain the Stage-2 selector contract. The
    runner supplies execution provenance; this API does not prove it again
    from an observation or from a future outcome. Game ordering and event
    collection remain outside this single-action metadata adapter.
    """
    move = trace.move
    if (
        not isinstance(move.action, Action)
        or move.action not in (Action.OPEN, Action.FLAG, Action.CHORD)
        or any(isinstance(value, bool) or not isinstance(value, int) or value < 0
               for value in (move.x, move.y))
    ):
        raise ValueError("Trace move must be a public action at nonnegative integer coordinates.")

    decision = trace.decision
    timing = trace.decision_compute_ns
    if decision is None:
        if move != SimpleMove(Action.OPEN, 0, 0) or timing is not None:
            raise ValueError("Policy trace requires OPEN (0, 0) and no decision timing.")
        return Stage3ActionTelemetry(None, None, None, None, None)

    if isinstance(timing, bool) or not isinstance(timing, int) or timing < 0:
        raise ValueError("Analyzed trace requires nonnegative integer decision_compute_ns.")
    if move != decision.move:
        raise ValueError("Trace move does not match the executed decision move.")
    if decision.plan is not None and decision.plan.actions[0] != move:
        raise ValueError("Executed decision move does not match the plan's first action.")

    evidence = decision.evidence
    if not isinstance(evidence.kind, DecisionKind):
        raise ValueError(f"Unsupported decision kind: {evidence.kind!r}.")
    category = _INFERENCE_CATEGORIES[evidence.kind]
    result = evidence.probability_result
    if result is not None and (
        len({cell.coordinate for cell in result.probabilities}) != len(result.probabilities)
    ):
        raise ValueError("Probability evidence must contain unique selectable coordinates.")

    if evidence.kind == DecisionKind.PROBABILITY_GUESS:
        if move.action != Action.OPEN or move != evidence.move or decision.plan is not None:
            raise ValueError("Guess requires the exact Stage-2 OPEN and no reveal plan.")
        # Reuse only the guess selector check: all HIDDEN probabilities,
        # exact minimum, Stage-2 priority and (y, x) tie-break. No analysis runs.
        metadata = decision_to_telemetry(evidence)
        return Stage3ActionTelemetry(
            category, None, metadata.target_mine_probability,
            metadata.minimum_available_mine_probability, timing,
        )

    if evidence.kind == DecisionKind.GLOBAL_CERTAINTY and (
        evidence.deterministic_result.safe_cells or evidence.deterministic_result.mine_cells
    ):
        raise ValueError("GLOBAL evidence cannot bypass current local certainty.")
    try:
        safe, mines = certainty_pool(evidence)
    except Stage3PlanningError as error:
        raise ValueError(str(error)) from error
    coordinate = (move.x, move.y)
    if move.action == Action.OPEN:
        if coordinate not in safe:
            raise ValueError("Executed OPEN is absent from current public safe evidence.")
        target_probability = Fraction(0, 1)
    elif move.action == Action.FLAG:
        if coordinate not in mines:
            raise ValueError("Executed FLAG is absent from current public mine evidence.")
        target_probability = Fraction(1, 1)
    else:
        clues = tuple(item for item in evidence.constraints if item.source == coordinate)
        if (
            evidence.kind != DecisionKind.LOCAL_DETERMINISTIC
            or decision.plan is None or len(clues) != 1
            or clues[0].remaining_mines != 0 or not clues[0].hidden_cells
            or not clues[0].hidden_cells <= safe or coordinate in safe | mines
        ):
            raise ValueError("CHORD requires current LOCAL zero-remaining safe-neighbor evidence.")
        # The executed target is a revealed clue, not a selectable HIDDEN cell.
        target_probability = None

    return Stage3ActionTelemetry(category, None, target_probability, None, timing)
