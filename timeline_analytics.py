"""Pure per-game projection of completed solver telemetry under frozen Model C.

Each game owns its action sequence. Model C is a measurement scale, not a
shared execution clock; equal action counts imply no equivalent board progress.
Recorded effects and decision metadata are retained without replay or inference.
"""

from collections import Counter
from dataclasses import dataclass

import benchmark_modeled_time as modeled
from core_engine import Action
import stage3_physical as physical
from telemetry_model import ActionEvent, GameRecord, InferenceCategory


@dataclass(frozen=True)
class TimelineAction:
    """One original event plus exact derived cost, geometry and reveal facts.

    modeled_action_us is joint movement-plus-target-input Model C cost, not
    measured movement time. Geometry uses cell centers and cell units.
    """

    event: ActionEvent
    modeled_action_us: int
    cumulative_modeled_us: int
    dx: int
    dy: int
    cumulative_safe_cells_opened: int

    @property
    def completed_action_count(self) -> int:
        return self.event.action_index + 1

    @property
    def squared_displacement(self) -> int:
        """Exact squared cell-center displacement; no rounded square root."""
        return self.dx * self.dx + self.dy * self.dy


@dataclass(frozen=True)
class TimelineAnalytics:
    """One completed game with its original facts and authenticated model.

    evaluation retains the physical model ID, profile version/hash, timing
    table hash and unit without inventing source or run identity. For LOSS,
    total_modeled_us is cost through termination, never time-to-win.
    """

    record: GameRecord
    actions: tuple[TimelineAction, ...]
    evaluation: modeled.ModelCEvaluation
    total_modeled_us: int

    @property
    def cumulative_modeled_curve(self) -> tuple[tuple[int, int], ...]:
        """(Completed actions, Model C microseconds), including a curve origin."""
        return ((0, 0),) + tuple(
            (item.completed_action_count, item.cumulative_modeled_us)
            for item in self.actions
        )

    @property
    def cumulative_safe_reveal_curve(self) -> tuple[tuple[int, int], ...]:
        """(Completed actions, cumulative safe reveals); origin is not an event."""
        return ((0, 0),) + tuple(
            (item.completed_action_count, item.cumulative_safe_cells_opened)
            for item in self.actions
        )


def _validate_event_summaries(record: GameRecord, events: tuple[ActionEvent, ...]) -> None:
    """Check raw-derived summaries outside reconstruct_game's physical boundary."""
    action_counts = Counter(event.action_type for event in events)
    category_counts = Counter(event.inference_category for event in events)
    first_guess = next((
        event.action_index for event in events
        if event.inference_category == InferenceCategory.PROBABILITY_GUESS
    ), None)
    timings = tuple(
        event.decision_compute_ns for event in events
        if event.decision_compute_ns is not None
    )
    expected = {
        "open_count": action_counts[Action.OPEN],
        "flag_count": action_counts[Action.FLAG],
        "chord_count": action_counts[Action.CHORD],
        "local_deterministic_count": category_counts[InferenceCategory.LOCAL_DETERMINISTIC],
        "global_certainty_count": category_counts[InferenceCategory.GLOBAL_CERTAINTY],
        "probability_guess_count": category_counts[InferenceCategory.PROBABILITY_GUESS],
        "had_probability_guess": first_guess is not None,
        "first_guess_action_index": first_guess,
        "compute_time_total_ns": sum(timings),
        "compute_time_max_ns": max(timings, default=None),
    }
    for name, value in expected.items():
        if getattr(record, name) != value:
            raise ValueError(f"GameRecord {name} disagrees with the action events.")


def project_timeline(
    record: GameRecord, events: tuple[ActionEvent, ...], *,
    width: int, height: int, evaluation: modeled.ModelCEvaluation,
) -> TimelineAnalytics:
    """Validate and project one complete ordered stream without I/O or execution.

    The caller supplies an already-authenticated evaluation. reconstruct_game
    owns model/structural validation, including total_actions, canonical first
    OPEN/click, enum domains, bounds, indices and terminal WIN/LOSS agreement.
    Additional summaries are checked against raw events here. Invalid inputs
    raise ValueError (including the existing ModeledTimeValidationError).

    No hidden layout or decision correctness is inferred. Nullable metadata and
    exact Fractions remain on the original events; compute diagnostics never
    contribute to Model C cost. Automatic effects never add physical actions.
    """
    if not isinstance(record, GameRecord):
        raise ValueError("record must be a GameRecord.")
    if not isinstance(events, tuple) or any(not isinstance(event, ActionEvent) for event in events):
        raise ValueError("events must be an ordered tuple of ActionEvent objects.")
    reconstructed = modeled.reconstruct_game(
        record, events, width=width, height=height, evaluation=evaluation,
    )
    _validate_event_summaries(record, events)

    cursor = evaluation.initial_cursor
    cumulative_cost = 0
    cumulative_safe = 0
    actions = []
    for event in events:
        target = (event.x, event.y)
        cost = physical.action_cost(evaluation.table, cursor, target)
        cumulative_cost += cost
        cumulative_safe += event.safe_cells_opened_delta
        actions.append(TimelineAction(
            event=event, modeled_action_us=cost, cumulative_modeled_us=cumulative_cost,
            dx=event.x - cursor[0], dy=event.y - cursor[1],
            cumulative_safe_cells_opened=cumulative_safe,
        ))
        cursor = target

    if cumulative_cost != reconstructed.total_modeled_us:
        raise ValueError("Timeline Model C total disagrees with reconstruct_game.")
    return TimelineAnalytics(
        record=record, actions=tuple(actions), evaluation=evaluation,
        total_modeled_us=reconstructed.total_modeled_us,
    )
