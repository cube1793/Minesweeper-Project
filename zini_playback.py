"""Click-level playback units derived from a builder-validated ZiNi trace.

A logical ZiNi move can cost several physical clicks: flag_chord places each
new flag and then chords. Playback here shows one unit per physical click while
keeping one integer position as the only cursor. Logical-step views are derived
from that position; nothing here stores a separate logical index.

Units come only from stored trace data (action, coordinate, clicks_added,
newly_revealed, newly_flagged). There is no Premium recalculation, search, RNG,
engine access, or answer data beyond what the trace already holds.

Flags inside one move follow the trace's newly_flagged order, which is the
row-major top-left order (y, x). That is a display order, not a reconstruction
of a real click order.
"""

from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum

from board_snapshot import Coordinate
from zini_trace import ZiniTrace, ZiniTraceStep


class ZiniPlaybackUnitKind(str, Enum):
    CLICK = "click"
    FALLBACK_CLICK = "fallback_click"
    FLAG = "flag"
    CHORD = "chord"


@dataclass(frozen=True)
class ZiniPlaybackUnit:
    """One physical-click playback unit.

    position is 1-based: the playback position (cumulative clicks) after this
    unit. FLAG targets the flagged cell; other kinds target the move's cell.
    flag_number is k (1..flag_count) for FLAG and 0 otherwise; flag_count is
    the move's new-flag count (0 for click and fallback_click).
    """

    position: int
    step_index: int
    kind: ZiniPlaybackUnitKind
    target: Coordinate
    flag_number: int
    flag_count: int


def derive_playback_units(trace: ZiniTrace) -> tuple[ZiniPlaybackUnit, ...]:
    """Expand logical moves into click units; reject inconsistent click costs."""
    units = []
    for step in trace.steps:
        move = step.move
        coord = (move.x, move.y)
        flags = step.newly_flagged
        if move.action in ("click", "fallback_click"):
            if move.clicks_added != 1 or flags:
                raise ValueError(
                    f"ZiNi playback step {step.step_index}: {move.action} must "
                    "cost one click without new flags."
                )
            kind = (ZiniPlaybackUnitKind.CLICK if move.action == "click"
                    else ZiniPlaybackUnitKind.FALLBACK_CLICK)
            units.append(ZiniPlaybackUnit(
                len(units) + 1, step.step_index, kind, coord, 0, 0,
            ))
        elif move.action == "flag_chord":
            if move.clicks_added != len(flags) + 1:
                raise ValueError(
                    f"ZiNi playback step {step.step_index}: flag_chord clicks "
                    "must equal new flags plus one chord."
                )
            for number, flag in enumerate(flags, 1):
                units.append(ZiniPlaybackUnit(
                    len(units) + 1, step.step_index, ZiniPlaybackUnitKind.FLAG,
                    flag, number, len(flags),
                ))
            units.append(ZiniPlaybackUnit(
                len(units) + 1, step.step_index, ZiniPlaybackUnitKind.CHORD,
                coord, 0, len(flags),
            ))
        else:
            raise ValueError(
                f"ZiNi playback step {step.step_index}: unsupported action "
                f"{move.action!r}."
            )
    if len(units) != trace.total_clicks:
        raise ValueError("ZiNi playback units do not match the trace click total.")
    return tuple(units)


def _valid_index(value: object, upper: int) -> bool:
    return (not isinstance(value, bool) and isinstance(value, int)
            and 0 <= value <= upper)


class ZiniPlaybackPlayer:
    """Single-cursor playback over click units with derived logical views.

    The only mutable state is the playback position p (0..unit count).
    Logical views use floor(p): the number of moves whose every unit is
    applied. Logical navigation lands on move boundaries; a query never moves.
    """

    def __init__(self, trace: ZiniTrace):
        self._trace = trace
        self._units = derive_playback_units(trace)
        boundaries = [0]
        for step in trace.steps:
            boundaries.append(boundaries[-1] + step.move.clicks_added)
        self._boundaries = tuple(boundaries)
        self._position = 0

    @property
    def trace(self) -> ZiniTrace:
        return self._trace

    @property
    def units(self) -> tuple[ZiniPlaybackUnit, ...]:
        return self._units

    # Playback (click-unit) views.

    @property
    def playback_position(self) -> int:
        return self._position

    @property
    def playback_count(self) -> int:
        return len(self._units)

    @property
    def playback_unit(self) -> ZiniPlaybackUnit | None:
        return self._units[self._position - 1] if self._position else None

    @property
    def playback_step(self) -> ZiniTraceStep | None:
        unit = self.playback_unit
        return None if unit is None else self._trace.steps[unit.step_index]

    @property
    def playback_revealed(self) -> frozenset[Coordinate]:
        # Reveals happen only on a move's last unit, which is a boundary.
        return self.revealed

    @property
    def playback_flagged_mines(self) -> frozenset[Coordinate]:
        index = self.current_index
        partial = self._position - self._boundaries[index]
        flags = set(self.flagged_mines)
        if partial:
            flags.update(self._trace.steps[index].newly_flagged[:partial])
        return frozenset(flags)

    @property
    def playback_newly_revealed(self) -> frozenset[Coordinate]:
        unit = self.playback_unit
        if unit is None or unit.kind == ZiniPlaybackUnitKind.FLAG:
            return frozenset()
        return frozenset(self._trace.steps[unit.step_index].newly_revealed)

    @property
    def playback_newly_flagged(self) -> frozenset[Coordinate]:
        unit = self.playback_unit
        if unit is None or unit.kind != ZiniPlaybackUnitKind.FLAG:
            return frozenset()
        return frozenset({unit.target})

    def seek_playback(self, position: int) -> None:
        """Move to 0..playback_count; invalid input leaves state unchanged."""
        if not _valid_index(position, self.playback_count):
            raise ValueError("ZiNi playback position is out of range.")
        self._position = position

    def next_playback(self) -> bool:
        if self._position == self.playback_count:
            return False
        self._position += 1
        return True

    def previous_playback(self) -> bool:
        if self._position == 0:
            return False
        self._position -= 1
        return True

    # Logical-step views, all derived from the playback position.

    @property
    def current_index(self) -> int:
        return bisect_right(self._boundaries, self._position) - 1

    @property
    def step_count(self) -> int:
        return len(self._trace.steps)

    @property
    def current_step(self) -> ZiniTraceStep | None:
        index = self.current_index
        return self._trace.steps[index - 1] if index else None

    @property
    def revealed(self) -> frozenset[Coordinate]:
        return frozenset(
            cell for step in self._trace.steps[:self.current_index]
            for cell in step.newly_revealed
        )

    @property
    def flagged_mines(self) -> frozenset[Coordinate]:
        return frozenset(
            cell for step in self._trace.steps[:self.current_index]
            for cell in step.newly_flagged
        )

    def go_to(self, index: int) -> None:
        """Move to logical boundary P(index); invalid input changes nothing."""
        if not _valid_index(index, self.step_count):
            raise ValueError("ZiNi trace index is out of range.")
        self._position = self._boundaries[index]

    def next(self) -> bool:
        index = self.current_index
        if index == self.step_count:
            return False
        self._position = self._boundaries[index + 1]
        return True

    def previous(self) -> bool:
        index = self.current_index
        if index == 0:
            return False
        self._position = self._boundaries[index - 1]
        return True
