"""Post-hoc Level A+B analysis and playback of a completed ZiNi path.

Build a trace only after search has returned its final ZiniResult. This module
never runs search, samples alternatives, or changes the supplied result. Level A
replays the selected logical moves; Level B describes each move relative to its
pre-state's Premium candidates and deterministic greedy choice. Neither level
records search provenance (discarded paths, generations, beam history, or RNG).

ZiNi moves are not gameplay ReplayEvents: flag_chord can cost several physical
clicks. Playback here uses virtual-state deltas, without an engine or a clock.
"""

from dataclasses import dataclass
from enum import Enum

from board_snapshot import BoardSnapshot, Coordinate
from zini_calculator import ZiniMove, ZiniResult
from zini_core import (
    _ACTION_CLICK,
    _ACTION_FALLBACK_CLICK,
    _ACTION_FLAG_CHORD,
    _ZiniBoardState,
    _apply_premium_candidate,
    _build_premium_context,
    _click_fallback_cell,
    _find_fallback_click_targets,
    _find_premium_candidates,
    _top_left_key,
)


TRACE_SCHEMA_VERSION = 1
# V1 means the Premium/move/fallback semantics frozen by Slice 1 in
# tests/zini_v1_golden.py, preserved by Slices 2-4. It is independent of search
# strategy/version and of this trace schema; it is not a Git revision.
ZINI_SEMANTICS_VERSION = 1


class ZiniTraceSelection(str, Enum):
    """Schema-v1 pre-state comparisons, never search provenance.

    GREEDY is the top-left maximum-Premium candidate; MAX_TIE_ALT is another
    maximum; BELOW_MAX has a lower Premium. Fallback classes compare against
    the top-left unresolved static 3BV target. No class implies a particular
    search policy, Premium window, generation, phase, or random choice.
    """

    GREEDY = "greedy"
    MAX_TIE_ALT = "max_tie_alt"
    BELOW_MAX = "below_max"
    FALLBACK_GREEDY = "fallback_greedy"
    FALLBACK_ALT = "fallback_alt"


@dataclass(frozen=True)
class ZiniTraceStep:
    """One zero-based logical step and its row-major state deltas.

    best_premium and tie_count describe ALL number-cell candidates before the
    move, including already revealed cells and negative maxima in fallback
    states. With no candidates they are None and 0. tie_count never counts
    fallback targets. Physical click cost remains in move.clicks_added.
    """

    step_index: int
    move: ZiniMove
    newly_revealed: tuple[Coordinate, ...]
    newly_flagged: tuple[Coordinate, ...]
    best_premium: int | None
    tie_count: int
    selection: ZiniTraceSelection

    def __post_init__(self):
        # Copy collection inputs, including coordinate pairs, so frozen models
        # cannot retain a caller's mutable lists.
        for name in ("newly_revealed", "newly_flagged"):
            object.__setattr__(
                self, name, tuple((x, y) for x, y in getattr(self, name)),
            )


@dataclass(frozen=True)
class ZiniTrace:
    """Immutable in-memory trace; use build_zini_trace for semantic validation.

    Move count is len(steps); cumulative clicks at index N are the sum of
    steps[:N]'s move.clicks_added. No per-step board snapshots are retained.
    This model does not define a persistence or worker transport format.
    """

    snapshot: BoardSnapshot
    total_clicks: int
    steps: tuple[ZiniTraceStep, ...]
    schema_version: int = TRACE_SCHEMA_VERSION
    semantics_version: int = ZINI_SEMANTICS_VERSION

    def __post_init__(self):
        object.__setattr__(self, "steps", tuple(self.steps))
        if self.schema_version != TRACE_SCHEMA_VERSION:
            raise ValueError("Unsupported ZiNi trace schema version.")
        if self.semantics_version != ZINI_SEMANTICS_VERSION:
            raise ValueError("Unsupported ZiNi trace semantics version.")


def _validate_recorded_move(move: ZiniMove) -> None:
    """Reject malformed values that could compare equal to core integers."""
    if move.action not in (
        _ACTION_CLICK, _ACTION_FLAG_CHORD, _ACTION_FALLBACK_CLICK,
    ):
        raise ValueError(f"Unsupported recorded action: {move.action!r}.")
    for name in ("x", "y", "clicks_added"):
        value = getattr(move, name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Recorded {name} must be an integer.")
    if move.premium is not None and (
        isinstance(move.premium, bool) or not isinstance(move.premium, int)
    ):
        raise ValueError("Recorded premium must be an integer or None.")


def build_zini_trace(snapshot: BoardSnapshot, result: ZiniResult) -> ZiniTrace:
    """Reconstruct and validate a completed path using current V1 semantics.

    Only this fresh virtual state is mutated. No calculator/search is called
    and no RNG is used. Premium candidates are recomputed before each recorded
    move; applying the selected candidate/target must reproduce all five move
    fields exactly. BELOW_MAX imposes no strategy-specific Premium window.
    In particular, a covered negative-Premium click is core-valid when the
    pre-state has a non-negative maximum; negative-Premium chords are not.

    Raises ValueError for an unplaced board, illegal or mismatched move, moves
    after completion, an incomplete path, or an inconsistent click total.
    Step errors include the zero-based index. The BoardSnapshot is assumed to
    describe a valid board, as for the existing calculator APIs.
    """
    if not snapshot.mines_placed:
        raise ValueError("Cannot build a ZiNi trace before mines are placed.")
    if isinstance(result.clicks, bool) or not isinstance(result.clicks, int):
        raise ValueError("ZiNi result clicks must be an integer.")

    context = _build_premium_context(snapshot)
    state = _ZiniBoardState.create(snapshot)
    steps = []

    for step_index, recorded in enumerate(result.moves):
        try:
            _validate_recorded_move(recorded)
            if state.all_safe_cells_revealed():
                raise ValueError("Recorded move occurs after the board is solved.")

            candidates = _find_premium_candidates(state, context)
            greedy = min(
                candidates,
                key=lambda item: (-item.premium, _top_left_key(item.coord)),
                default=None,
            )
            best_premium = None if greedy is None else greedy.premium
            tie_count = sum(
                item.premium == best_premium for item in candidates
            )
            coord = (recorded.x, recorded.y)
            before_revealed = set(state.revealed)
            before_flagged = set(state.flagged_mines)

            if best_premium is None or best_premium < 0:
                if recorded.action != _ACTION_FALLBACK_CLICK:
                    raise ValueError("Fallback state requires a fallback_click.")
                targets = _find_fallback_click_targets(state, context)
                if coord not in targets:
                    raise ValueError("Recorded fallback target is unavailable.")
                selection = (
                    ZiniTraceSelection.FALLBACK_GREEDY
                    if coord == targets[0] else ZiniTraceSelection.FALLBACK_ALT
                )
                actual = _click_fallback_cell(state, coord, context)
            else:
                if recorded.action == _ACTION_FALLBACK_CLICK:
                    raise ValueError("Fallback is invalid with non-negative Premium.")
                matching = tuple(item for item in candidates if item.coord == coord)
                if len(matching) != 1:
                    raise ValueError("Recorded Premium candidate is unavailable.")
                selected = matching[0]
                if recorded.premium != selected.premium:
                    raise ValueError(
                        f"Recorded premium {recorded.premium!r} does not match "
                        f"current Premium {selected.premium}."
                    )
                if coord == greedy.coord:
                    selection = ZiniTraceSelection.GREEDY
                elif selected.premium == best_premium:
                    selection = ZiniTraceSelection.MAX_TIE_ALT
                else:
                    selection = ZiniTraceSelection.BELOW_MAX
                actual = _apply_premium_candidate(state, selected, context)

            if actual != recorded:
                raise ValueError(
                    f"Recorded move does not match current semantics: "
                    f"recorded={recorded!r}, applied={actual!r}."
                )
            newly_revealed = tuple(sorted(
                state.revealed - before_revealed, key=_top_left_key,
            ))
            newly_flagged = tuple(sorted(
                state.flagged_mines - before_flagged, key=_top_left_key,
            ))
            if not newly_revealed and not newly_flagged:
                raise ValueError("Recorded move made no progress.")
        except ValueError as exc:
            raise ValueError(f"ZiNi trace step {step_index}: {exc}") from exc

        steps.append(ZiniTraceStep(
            step_index=step_index,
            move=recorded,
            newly_revealed=newly_revealed,
            newly_flagged=newly_flagged,
            best_premium=best_premium,
            tie_count=tie_count,
            selection=selection,
        ))

    if result.clicks != sum(step.move.clicks_added for step in steps):
        raise ValueError("ZiNi result click total does not match recorded moves.")
    if not state.all_safe_cells_revealed():
        raise ValueError("Incomplete ZiNi trajectory: safe cells remain covered.")
    if not state.flagged_mines <= snapshot.mines:
        raise ValueError("ZiNi trajectory flagged a non-mine cell.")

    return ZiniTrace(snapshot=snapshot, total_clicks=result.clicks, steps=tuple(steps))


class ZiniTracePlayer:
    """Navigate a builder-validated trace by applying only stored deltas.

    Index N means steps[:N] have been applied, not N physical clicks. Seeking
    (including previous) rebuilds from the empty state; next applies one delta.
    There is no Premium recalculation, engine playback, or search here.
    """

    def __init__(self, trace: ZiniTrace):
        self._trace = trace
        self._current_index = 0
        self._revealed: set[Coordinate] = set()
        self._flagged_mines: set[Coordinate] = set()

    @property
    def trace(self) -> ZiniTrace:
        return self._trace

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def step_count(self) -> int:
        return len(self._trace.steps)

    @property
    def current_step(self) -> ZiniTraceStep | None:
        """Last applied logical step, or None at index 0."""
        if self._current_index == 0:
            return None
        return self._trace.steps[self._current_index - 1]

    @property
    def revealed(self) -> frozenset[Coordinate]:
        return frozenset(self._revealed)

    @property
    def flagged_mines(self) -> frozenset[Coordinate]:
        return frozenset(self._flagged_mines)

    def go_to(self, index: int) -> None:
        """Restore index 0..step_count; invalid input leaves state unchanged."""
        if (
            isinstance(index, bool) or not isinstance(index, int)
            or not 0 <= index <= self.step_count
        ):
            raise ValueError("ZiNi trace index is out of range.")
        self._revealed = set()
        self._flagged_mines = set()
        for step in self._trace.steps[:index]:
            self._apply_delta(step)
        self._current_index = index

    def next(self) -> bool:
        """Apply one step; return False without changes at the final index."""
        if self._current_index == self.step_count:
            return False
        self._apply_delta(self._trace.steps[self._current_index])
        self._current_index += 1
        return True

    def previous(self) -> bool:
        """Rebuild the preceding state; return False at the initial index."""
        if self._current_index == 0:
            return False
        self.go_to(self._current_index - 1)
        return True

    def _apply_delta(self, step: ZiniTraceStep) -> None:
        self._revealed.update(step.newly_revealed)
        self._flagged_mines.update(step.newly_flagged)
