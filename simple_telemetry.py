"""Translate existing Stage 2 decision evidence into exact telemetry facts.

Only the final selector pool is reconstructed; no inference or probability
analysis is rerun. Policy initial OPENs and execution timing belong to the
runner/collection boundary, not this adapter.
"""

from dataclasses import dataclass
from fractions import Fraction

from core_engine import Action
from simple_decision import DecisionKind, SimpleDecision
from telemetry_model import InferenceCategory


_INFERENCE_CATEGORIES = {
    DecisionKind.LOCAL_DETERMINISTIC: InferenceCategory.LOCAL_DETERMINISTIC,
    DecisionKind.GLOBAL_CERTAINTY: InferenceCategory.GLOBAL_CERTAINTY,
    DecisionKind.PROBABILITY_GUESS: InferenceCategory.PROBABILITY_GUESS,
}


@dataclass(frozen=True)
class DecisionTelemetry:
    """Final competition count and exact risk for one analyzed Stage 2 move."""

    inference_category: InferenceCategory
    selection_candidate_count: int
    target_mine_probability: Fraction | None
    minimum_available_mine_probability: Fraction | None


def decision_to_telemetry(decision: SimpleDecision) -> DecisionTelemetry:
    """Adapt computed evidence, raising ValueError on selector-semantic drift.

    FLAG candidates beat safe OPEN candidates. Guesses consider every entry
    in ProbabilityResult.probabilities, including unconstrained cells. Every
    final pool uses the Stage 2 (y, x) tie-break. This accepts a SimpleDecision;
    the policy initial OPEN's decision=None is handled by the caller later.
    """
    try:
        category = _INFERENCE_CATEGORIES[decision.kind]
    except KeyError as error:
        raise ValueError(f"Unsupported decision kind: {decision.kind!r}.") from error

    coordinate = (decision.move.x, decision.move.y)
    deterministic = decision.deterministic_result
    minimum_probability = None

    if decision.kind == DecisionKind.LOCAL_DETERMINISTIC:
        if deterministic.mine_cells:
            action, pool = Action.FLAG, deterministic.mine_cells
            target_probability = Fraction(1, 1)
        else:
            action, pool = Action.OPEN, deterministic.safe_cells
            target_probability = Fraction(0, 1)
    else:
        if deterministic.mine_cells or deterministic.safe_cells:
            raise ValueError("Local candidates must take priority over probability decisions.")
        result = decision.probability_result
        if result is None or not result.probabilities:
            raise ValueError("Probability decisions require nonempty probability evidence.")

        certain_mines = frozenset(
            cell.coordinate for cell in result.probabilities
            if cell.mine_worlds == cell.total_worlds
        )
        certain_safe = frozenset(
            cell.coordinate for cell in result.probabilities if cell.mine_worlds == 0
        )
        if decision.kind == DecisionKind.GLOBAL_CERTAINTY:
            if certain_mines:
                action, pool = Action.FLAG, certain_mines
                target_probability = Fraction(1, 1)
            else:
                action, pool = Action.OPEN, certain_safe
                target_probability = Fraction(0, 1)
        else:
            if certain_mines or certain_safe:
                raise ValueError("PROBABILITY_GUESS cannot bypass certainty candidates.")
            # ProbabilityResult covers all selectable HIDDEN cells. Region
            # metadata must not restrict the final competition to the frontier.
            probabilities = {
                cell.coordinate: Fraction(cell.mine_worlds, cell.total_worlds)
                for cell in result.probabilities
            }
            minimum_probability = min(probabilities.values())
            action = Action.OPEN
            pool = frozenset(
                cell for cell, probability in probabilities.items()
                if probability == minimum_probability
            )
            if coordinate not in probabilities:
                raise ValueError("Selected coordinate is absent from probability evidence.")
            target_probability = probabilities[coordinate]
            if target_probability != minimum_probability:
                raise ValueError("Guess target probability does not equal the exact minimum.")

    if not pool:
        raise ValueError("Decision has no candidates in the derived final pool.")
    if decision.move.action != action:
        raise ValueError("Selected action does not match the derived selector action.")
    if coordinate not in pool:
        raise ValueError("Selected coordinate is outside the derived final pool.")
    if coordinate != min(pool, key=lambda cell: (cell[1], cell[0])):
        raise ValueError("Selected coordinate violates the (y, x) tie-break.")

    return DecisionTelemetry(
        inference_category=category,
        selection_candidate_count=len(pool),
        target_mine_probability=target_probability,
        minimum_available_mine_probability=minimum_probability,
    )
