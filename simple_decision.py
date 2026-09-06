"""Stage 2-3 pure analysis of one visible position, reusable without a runner.

Only the observation and public total mine count enter this module. Flags are
assumed to be mines, as in both solver cores. A completely HIDDEN observation
uses fixed-layout probabilities; first-OPEN safety belongs to the runner.
"""

from dataclasses import dataclass
from enum import Enum

from core_engine import CellState
from simple_algorithm import (
    Constraint,
    InconsistentObservationError,
    InferenceResult,
    Observation,
    SimpleMove,
    build_constraints,
    choose_deterministic_move,
    infer_deterministic,
)
from simple_probability import (
    ProbabilityResult,
    calculate_probabilities,
    choose_probability_move,
)


class DecisionKind(Enum):
    LOCAL_DETERMINISTIC = "local_deterministic"
    GLOBAL_CERTAINTY = "global_certainty"
    PROBABILITY_GUESS = "probability_guess"


@dataclass(frozen=True)
class SimpleDecision:
    """One recommendation and the evidence already computed for this position."""

    kind: DecisionKind
    move: SimpleMove
    constraints: tuple[Constraint, ...]
    deterministic_result: InferenceResult
    probability_result: ProbabilityResult | None

    def __post_init__(self):
        object.__setattr__(self, "constraints", tuple(self.constraints))


def analyze_position(
    observation: Observation, num_mines: int,
) -> SimpleDecision | None:
    """Recommend one move without executing it or changing the observation.

    Local inference always takes priority and skips probability enumeration.
    Otherwise, retain the exact complete-board probability result and classify
    the selected cell by integer world counts, never rounded probabilities.
    None means the probability selector has no HIDDEN cell to select.

    Solver validation errors propagate. Validate clues through Stage 2-1 and
    the public flag/hidden mine budget before local inference. Complete-board
    enumeration is performed only on the Stage 2-2 path.
    Obtain a fresh observation and call again after every physical action.
    """
    if isinstance(num_mines, bool) or not isinstance(num_mines, int):
        raise ValueError("num_mines must be an integer.")
    constraints = build_constraints(observation)
    flag_count = sum(value == CellState.FLAGGED for row in observation for value in row)
    hidden_count = sum(value == CellState.HIDDEN for row in observation for value in row)
    remaining_mines = num_mines - flag_count
    if not 0 <= remaining_mines <= hidden_count:
        raise InconsistentObservationError(
            f"num_mines={num_mines}, flag_count={flag_count}: remaining_mines="
            f"{remaining_mines} must be between 0 and {hidden_count} hidden cells."
        )

    deterministic = infer_deterministic(constraints)
    move = choose_deterministic_move(deterministic)
    if move is not None:
        return SimpleDecision(
            kind=DecisionKind.LOCAL_DETERMINISTIC,
            move=move,
            constraints=constraints,
            deterministic_result=deterministic,
            probability_result=None,
        )

    probabilities = calculate_probabilities(observation, num_mines)
    move = choose_probability_move(probabilities)
    if move is None:
        return None

    selected = next(
        cell for cell in probabilities.probabilities
        if cell.coordinate == (move.x, move.y)
    )
    kind = (
        DecisionKind.GLOBAL_CERTAINTY
        if selected.mine_worlds in (0, selected.total_worlds)
        else DecisionKind.PROBABILITY_GUESS
    )
    return SimpleDecision(
        kind=kind,
        move=move,
        constraints=constraints,
        deterministic_result=deterministic,
        probability_result=probabilities,
    )
