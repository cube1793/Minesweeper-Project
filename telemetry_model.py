"""Immutable in-memory telemetry facts, independent of solver decision types."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core_engine import Action, GameStatus


class InferenceCategory(Enum):
    LOCAL_DETERMINISTIC = "local_deterministic"
    GLOBAL_CERTAINTY = "global_certainty"
    PROBABILITY_GUESS = "probability_guess"


def _require_integer(name: str, value: int, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")


def _require_probability(name: str, value: Fraction) -> None:
    if not isinstance(value, Fraction) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a Fraction in [0, 1].")


@dataclass(frozen=True)
class ActionEvent:
    """One executed action; the Collector validates public action/status enums.

    Null inference metadata explicitly denotes an unanalyzed policy action;
    index zero alone does not. Only metadata structure and numeric domains are
    checked here, never solver priorities, certainty values or minimum-risk
    selection. Public Engine types are annotations only at model import time.
    """

    action_index: int

    inference_category: InferenceCategory | None
    selection_candidate_count: int | None
    target_mine_probability: Fraction | None
    minimum_available_mine_probability: Fraction | None
    decision_compute_ns: int | None

    action_type: "Action"
    x: int
    y: int

    status_after: "GameStatus"
    safe_cells_opened_delta: int
    explicit_flag_delta: int

    def __post_init__(self):
        for name in ("action_index", "x", "y", "safe_cells_opened_delta"):
            _require_integer(name, getattr(self, name))
        _require_integer("explicit_flag_delta", self.explicit_flag_delta, -1)
        if self.explicit_flag_delta > 1:
            raise ValueError("explicit_flag_delta must be -1, 0 or 1.")

        if self.inference_category is None:
            if any(value is not None for value in (
                self.selection_candidate_count, self.target_mine_probability,
                self.minimum_available_mine_probability, self.decision_compute_ns,
            )):
                raise ValueError("Unanalyzed actions require all inference metadata to be None.")
            return

        if not isinstance(self.inference_category, InferenceCategory):
            raise ValueError("inference_category must be an InferenceCategory or None.")
        _require_integer("selection_candidate_count", self.selection_candidate_count, 1)
        _require_integer("decision_compute_ns", self.decision_compute_ns)
        _require_probability("target_mine_probability", self.target_mine_probability)
        if self.inference_category == InferenceCategory.PROBABILITY_GUESS:
            _require_probability(
                "minimum_available_mine_probability", self.minimum_available_mine_probability,
            )
        elif self.minimum_available_mine_probability is not None:
            raise ValueError("Certainty metadata requires minimum probability to be None.")


@dataclass(frozen=True)
class GameRecord:
    """One completed game; raw-derived values are supplied by the Collector.

    This model checks same-record consistency. The Collector owns the raw
    sequence and derives every action summary from it, accepting no caller
    overrides. Board identity and static metrics are opaque evaluation inputs.
    """

    game_index: int
    seed: int
    board_fingerprint: str

    first_click_x: int
    first_click_y: int

    result: Literal["WIN", "LOSS"]

    total_actions: int
    open_count: int
    flag_count: int
    chord_count: int

    local_deterministic_count: int
    global_certainty_count: int
    probability_guess_count: int

    had_probability_guess: bool
    first_guess_action_index: int | None

    board_3bv: int
    board_ops: int

    compute_time_total_ns: int
    compute_time_max_ns: int | None

    def __post_init__(self):
        for name in (
            "game_index", "seed", "first_click_x", "first_click_y", "open_count",
            "flag_count", "chord_count", "local_deterministic_count",
            "global_certainty_count", "probability_guess_count", "board_3bv",
            "board_ops", "compute_time_total_ns",
        ):
            _require_integer(name, getattr(self, name))
        _require_integer("total_actions", self.total_actions, 1)
        if not isinstance(self.board_fingerprint, str) or not self.board_fingerprint:
            raise ValueError("board_fingerprint must be a nonempty string.")
        if self.result not in ("WIN", "LOSS"):
            raise ValueError("result must be WIN or LOSS.")
        if self.total_actions != self.open_count + self.flag_count + self.chord_count:
            raise ValueError("Physical action counts must sum to total_actions.")

        analyzed_count = (
            self.local_deterministic_count + self.global_certainty_count
            + self.probability_guess_count
        )
        if analyzed_count > self.total_actions:
            raise ValueError("Inference counts cannot exceed total_actions.")
        if not isinstance(self.had_probability_guess, bool):
            raise ValueError("had_probability_guess must be a bool.")
        if self.had_probability_guess != (self.probability_guess_count > 0):
            raise ValueError("Guess count and had_probability_guess disagree.")
        if self.had_probability_guess:
            _require_integer("first_guess_action_index", self.first_guess_action_index)
            if self.first_guess_action_index >= self.total_actions:
                raise ValueError("first_guess_action_index must point into the event sequence.")
        elif self.first_guess_action_index is not None:
            raise ValueError("A game without guesses requires first_guess_action_index=None.")

        if analyzed_count == 0:
            if self.compute_time_total_ns != 0 or self.compute_time_max_ns is not None:
                raise ValueError("A game without analyzed decisions requires total=0 and max=None.")
        else:
            _require_integer("compute_time_max_ns", self.compute_time_max_ns)
            if not (
                self.compute_time_max_ns <= self.compute_time_total_ns
                <= analyzed_count * self.compute_time_max_ns
            ):
                raise ValueError("Compute total and maximum are inconsistent.")
