"""Exact, Qt-independent timing over an already-recorded Stage-3 trace.

The player owns committed board states. This controller owns only the partial
modeled interval and wall-clock anchor; queries never advance playback.
"""

from collections.abc import Callable
from fractions import Fraction
from time import monotonic_ns
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stage3_runner import Stage3ActionTrace
    from stage3_trace_player import Stage3TracePlayer


SUPPORTED_SPEEDS = tuple(Fraction(value) for value in (0.25, 0.5, 1, 2, 4, 8))


class Stage3ModeledPlayback:
    """Consume recorded durations using an injectable monotonic nanosecond clock.

    Call cancel_partial() before navigating the shared player externally.
    A failed action stops at its pending boundary (progress 1 for a positive
    duration), retaining earlier commits and discarding time beyond that failed
    boundary. Only an explicit play() retries it. Clock failures instead preserve
    the last sampled position and stop playback.
    """

    def __init__(
        self, player: "Stage3TracePlayer", *, clock: Callable[[], int] = monotonic_ns,
    ):
        self._player = player
        self._clock = clock
        self._running = False
        self._speed = Fraction(1)
        self._partial_modeled_us = Fraction(0)
        self._last_clock_ns: int | None = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def speed(self) -> Fraction:
        return self._speed

    @property
    def pending_trace(self) -> "Stage3ActionTrace | None":
        if self._player.current_index == self._player.step_count:
            return None
        return self._player.execution.result.traces[self._player.current_index]

    @property
    def pending_duration_us(self) -> int | None:
        trace = self.pending_trace
        if trace is None:
            return None
        duration = trace.modeled_action_us
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
            raise ValueError("Pending modeled_action_us must be a nonnegative integer.")
        return duration

    @property
    def partial_modeled_us(self) -> Fraction:
        """Exact elapsed modeled microseconds within the pending action."""
        return self._partial_modeled_us

    @property
    def progress(self) -> Fraction:
        """Raw linear fraction; zero when there is no positive-duration interval."""
        duration = self.pending_duration_us
        return self.partial_modeled_us / duration if duration else Fraction(0)

    def play(self) -> None:
        """Start/resume without rewinding, consuming any immediately due actions."""
        if self.running or self.pending_trace is None:
            return
        self._last_clock_ns = self._read_clock()
        self._running = True
        self._consume(Fraction(0))

    def update(self) -> None:
        """Account for actual elapsed wall time and every crossed boundary."""
        if not self.running:
            return
        now = self._read_clock()
        elapsed = Fraction(now - self._last_clock_ns, 1000) * self.speed
        self._last_clock_ns = now
        self._consume(elapsed)

    def pause(self) -> None:
        """Account for time through this request, then freeze the exact position."""
        self.update()
        self._running = False

    def set_speed(self, speed: int | float | Fraction) -> None:
        """Apply elapsed time at the old rate before installing a supported rate."""
        if isinstance(speed, bool) or not isinstance(speed, (int, float, Fraction)):
            raise ValueError("Playback speed must be one of 0.25, 0.5, 1, 2, 4, 8.")
        if speed not in SUPPORTED_SPEEDS:
            raise ValueError("Playback speed must be one of 0.25, 0.5, 1, 2, 4, 8.")
        self.update()
        self._speed = Fraction(speed)

    def cancel_partial(self) -> None:
        """Stop and discard partial/unsampled time, keeping the committed index."""
        self._running = False
        self._partial_modeled_us = Fraction(0)

    def _read_clock(self) -> int:
        try:
            now = self._clock()
            if isinstance(now, bool) or not isinstance(now, int):
                raise ValueError("Monotonic clock must return integer nanoseconds.")
            if self._last_clock_ns is not None and now < self._last_clock_ns:
                raise ValueError("Monotonic clock moved backwards.")
            return now
        except Exception:
            self._running = False
            raise

    def _consume(self, elapsed: Fraction) -> None:
        remaining = self.partial_modeled_us + elapsed
        try:
            while self.pending_trace is not None:
                duration = self.pending_duration_us
                if remaining < duration:
                    self._partial_modeled_us = remaining
                    return
                # Publish the failed boundary if next() raises. Slice 1 keeps
                # the player's committed board/index unchanged on that failure.
                self._partial_modeled_us = Fraction(duration)
                if not self._player.next():
                    raise RuntimeError("Pending Stage-3 action did not advance.")
                remaining -= duration
                self._partial_modeled_us = Fraction(0)
            self._running = False
        except Exception:
            self._running = False
            raise
