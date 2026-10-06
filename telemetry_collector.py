"""Collect already-executed generic action facts for one game, entirely in memory."""

from collections import Counter
from fractions import Fraction

from core_engine import Action, GameStatus
from telemetry_model import ActionEvent, GameRecord, InferenceCategory


class TelemetryCollector:
    """Own a complete game's event sequence, starting with its first action.

    Callers translate solver evidence before recording. No Engine instance,
    observation, board layout, decision object or adapter is accepted here.
    Invalid inputs raise ValueError without advancing collection/finalization.
    """

    def __init__(self):
        self._events: list[ActionEvent] = []
        self._finalized = False

    @property
    def events(self) -> tuple[ActionEvent, ...]:
        """An immutable snapshot; later appends cannot change earlier snapshots."""
        return tuple(self._events)

    def record_action(
        self, *, action_type: Action, x: int, y: int,
        status_after: GameStatus, safe_cells_opened_delta: int, explicit_flag_delta: int,
        inference_category: InferenceCategory | None = None,
        selection_candidate_count: int | None = None,
        target_mine_probability: Fraction | None = None,
        minimum_available_mine_probability: Fraction | None = None,
        decision_compute_ns: int | None = None,
    ) -> ActionEvent:
        """Record supplied facts unchanged, assigning the next contiguous index.

        All-null inference metadata explicitly records an unanalyzed action,
        including the benchmark's initial policy OPEN. Analyzed actions are
        allowed at index zero. Action legality and effect derivation belong to
        the execution boundary, not this Collector.
        """
        if self._events and self._events[-1].status_after in (GameStatus.WON, GameStatus.LOST):
            raise ValueError("Cannot record an action after a terminal event.")
        if not isinstance(action_type, Action):
            raise ValueError("action_type must be an Action.")
        if not isinstance(status_after, GameStatus):
            raise ValueError("status_after must be a GameStatus.")

        event = ActionEvent(
            action_index=len(self._events),
            inference_category=inference_category,
            selection_candidate_count=selection_candidate_count,
            target_mine_probability=target_mine_probability,
            minimum_available_mine_probability=minimum_available_mine_probability,
            decision_compute_ns=decision_compute_ns,
            action_type=action_type, x=x, y=y, status_after=status_after,
            safe_cells_opened_delta=safe_cells_opened_delta,
            explicit_flag_delta=explicit_flag_delta,
        )
        self._events.append(event)
        return event

    def finalize(
        self, *, game_index: int, seed: int, board_fingerprint: str,
        board_3bv: int, board_ops: int,
    ) -> GameRecord:
        """Finalize once after a terminal action; evaluation facts are inputs.

        First-click coordinates mean the first recorded action's (x, y).
        Every summary is derived from the owned immutable events, then checked
        by GameRecord's arithmetic/nullability invariants. No summary overrides
        or Stage 2 baseline assumptions are accepted.
        """
        if self._finalized:
            raise ValueError("This game has already been finalized.")
        if not self._events or self._events[-1].status_after not in (GameStatus.WON, GameStatus.LOST):
            raise ValueError("Cannot finalize without a terminal event.")

        events = self.events
        action_counts = Counter(event.action_type for event in events)
        category_counts = Counter(
            event.inference_category for event in events if event.inference_category is not None
        )
        first_guess = next((
            event.action_index for event in events
            if event.inference_category == InferenceCategory.PROBABILITY_GUESS
        ), None)
        timings = tuple(
            event.decision_compute_ns for event in events if event.decision_compute_ns is not None
        )
        record = GameRecord(
            game_index=game_index, seed=seed, board_fingerprint=board_fingerprint,
            first_click_x=events[0].x, first_click_y=events[0].y,
            result="WIN" if events[-1].status_after == GameStatus.WON else "LOSS",
            total_actions=len(events),
            open_count=action_counts[Action.OPEN],
            flag_count=action_counts[Action.FLAG],
            chord_count=action_counts[Action.CHORD],
            local_deterministic_count=category_counts[InferenceCategory.LOCAL_DETERMINISTIC],
            global_certainty_count=category_counts[InferenceCategory.GLOBAL_CERTAINTY],
            probability_guess_count=category_counts[InferenceCategory.PROBABILITY_GUESS],
            had_probability_guess=first_guess is not None,
            first_guess_action_index=first_guess,
            board_3bv=board_3bv, board_ops=board_ops,
            compute_time_total_ns=sum(timings),
            compute_time_max_ns=max(timings, default=None),
        )
        self._finalized = True
        return record
