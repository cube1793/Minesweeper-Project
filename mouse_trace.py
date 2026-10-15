"""Sampled human board-pointer data, independent of Qt and gameplay actions.

Positions are board-local logical pixels, with a cell size on each segment.
Event indices refer to the game's existing Replay events; no action semantics
or Replay timestamps are copied here. Trace time has its own monotonic origin.
"""

from dataclasses import dataclass
from math import isfinite
from time import monotonic_ns
from typing import Callable


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")


@dataclass(frozen=True)
class MouseTracePoint:
    elapsed_us: int
    x: float
    y: float
    replay_event_index: int | None = None

    def __post_init__(self):
        _integer(self.elapsed_us, "elapsed_us")
        for name, value in (("x", self.x), ("y", self.y)):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or value < 0 or (isinstance(value, float) and not isfinite(value))):
                raise ValueError(f"{name} must be a finite non-negative position.")
        if self.replay_event_index is not None:
            _integer(self.replay_event_index, "replay_event_index")


@dataclass(frozen=True)
class MouseTraceSegment:
    cell_size: int
    points: tuple[MouseTracePoint, ...]

    def __post_init__(self):
        _integer(self.cell_size, "cell_size", 1)
        object.__setattr__(self, "points", tuple(self.points))
        if not self.points or any(not isinstance(p, MouseTracePoint) for p in self.points):
            raise ValueError("A segment must contain trace points.")
        if any(a.elapsed_us > b.elapsed_us for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Segment times must be nondecreasing.")


@dataclass(frozen=True)
class MouseTraceData:
    width: int
    height: int
    segments: tuple[MouseTraceSegment, ...]

    def __post_init__(self):
        _integer(self.width, "width", 1)
        _integer(self.height, "height", 1)
        object.__setattr__(self, "segments", tuple(self.segments))
        if not self.segments or any(not isinstance(s, MouseTraceSegment) for s in self.segments):
            raise ValueError("A trace must contain nonempty segments.")
        first = self.segments[0].points[0]
        if first.elapsed_us != 0 or first.replay_event_index is None:
            raise ValueError("A trace starts with an action-associated point at 0 us.")
        previous_time = 0
        previous_event = -1
        for segment in self.segments:
            for point in segment.points:
                if not (point.x < self.width * segment.cell_size
                        and point.y < self.height * segment.cell_size):
                    raise ValueError("Trace position is outside the board.")
                if point.elapsed_us < previous_time:
                    raise ValueError("Trace segments must be in timestamp order.")
                previous_time = point.elapsed_us
                if point.replay_event_index is not None:
                    if point.replay_event_index <= previous_event:
                        raise ValueError("Action references must be unique and increasing.")
                    previous_event = point.replay_event_index


class MouseTraceRecorder:
    """Append observations; start only on a caller-confirmed human action.

    The caller owns board visibility, human/Auto classification, and action commit.
    No clock is read for unstarted hover. snapshot() returns None before start or
    after invalidate(); a frozen started trace remains available. reset() begins
    a fresh eligible session. Snapshots never share mutable lists with the recorder.
    """

    def __init__(self, width: int, height: int, *, clock_ns: Callable[[], int] = monotonic_ns):
        self._clock_ns = clock_ns
        self.reset(width, height)

    def reset(self, width: int, height: int) -> None:
        _integer(width, "width", 1)
        _integer(height, "height", 1)
        self.width = width
        self.height = height
        self._segments: list[tuple[int, list[MouseTracePoint]]] = []
        self._segment_open = False
        self._origin_ns = None
        self._last_ns = None
        self._last_event_index = -1
        self._eligible = True
        self._frozen = False

    @property
    def started(self) -> bool:
        return self._origin_ns is not None

    @property
    def eligible(self) -> bool:
        return self._eligible

    @property
    def frozen(self) -> bool:
        return self._frozen

    def break_segment(self) -> None:
        """End continuity without adding an invented boundary observation."""
        self._segment_open = False

    def freeze(self) -> None:
        """Stop accepting observations while retaining any captured data."""
        self.break_segment()
        self._frozen = True

    def invalidate(self) -> None:
        """Discard capture for a mixed/abandoned game until the next reset."""
        self.freeze()
        self._eligible = False
        self._segments.clear()
        self._origin_ns = None
        self._last_ns = None

    def observation_time_ns(self) -> int:
        """Timestamp a candidate without starting or changing the trace.

        A caller may retain this with a release position across synchronous
        gameplay processing, then link it only after a successful commit.
        """
        now = self._clock_ns()
        self._validate_observation_time(now)
        return now

    def _validate_observation_time(self, now):
        if isinstance(now, bool) or not isinstance(now, int):
            raise ValueError("The monotonic clock must return integer nanoseconds.")
        if self._last_ns is not None and now < self._last_ns:
            raise ValueError("The monotonic clock moved backwards.")

    def record_position(self, x, y, cell_size: int, *, observed_ns=None) -> MouseTracePoint | None:
        if not self.started or not self.eligible or self.frozen:
            return None
        return self._append(x, y, cell_size, None, observed_ns)

    def record_action(self, x, y, cell_size: int, replay_event_index: int,
                      *, observed_ns=None) -> MouseTracePoint | None:
        """Link a committed event using the release's earlier observation time.

        Omit observed_ns only when observation and linking happen together.
        """
        if not self.eligible or self.frozen:
            return None
        _integer(replay_event_index, "replay_event_index")
        if replay_event_index <= self._last_event_index:
            raise ValueError("Action references must be unique and increasing.")
        return self._append(x, y, cell_size, replay_event_index, observed_ns)

    def _append(self, x, y, cell_size, event_index, observed_ns=None):
        _integer(cell_size, "cell_size", 1)
        # Validate before changing any state, including the clock origin.
        MouseTracePoint(0, x, y, event_index)
        if not (x < self.width * cell_size and y < self.height * cell_size):
            raise ValueError("Trace position is outside the board.")
        same_segment = self._segment_open and self._segments[-1][0] == cell_size
        if same_segment and event_index is None:
            last = self._segments[-1][1][-1]
            if (x, y) == (last.x, last.y):
                return None
        now = self.observation_time_ns() if observed_ns is None else observed_ns
        if observed_ns is not None:
            self._validate_observation_time(now)
        origin = now if self._origin_ns is None else self._origin_ns
        point = MouseTracePoint((now - origin) // 1000, x, y, event_index)
        if not same_segment:
            self._segments.append((cell_size, []))
        self._segments[-1][1].append(point)
        self._segment_open = True
        self._origin_ns = origin
        self._last_ns = now
        if event_index is not None:
            self._last_event_index = event_index
        return point

    def snapshot(self) -> MouseTraceData | None:
        if not self.eligible or not self.started:
            return None
        return MouseTraceData(self.width, self.height, tuple(
            MouseTraceSegment(size, tuple(points)) for size, points in self._segments
        ))
