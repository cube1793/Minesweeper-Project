"""Independent presentation clocks over completed exhibition results only."""

from fractions import Fraction
from time import monotonic_ns

from experiments.random_expert_exhibition_model import ExhibitionTrace
from stage3_modeled_playback import Stage3ModeledPlayback, SUPPORTED_SPEEDS


INTERVAL_MODE, MODEL_C_MODE = "interval", "model_c"
INTERVALS_MS = (250, 200, 500)
MIN_INTERVAL_MS, MAX_INTERVAL_MS = 20, 10000


def _rate_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Fraction)):
        raise ValueError("관람 속도는 유한한 숫자여야 합니다.")
    try:
        # Decimal input intent, rather than the binary approximation of a float.
        return Fraction(str(value)) if isinstance(value, float) else Fraction(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("관람 속도는 유한한 숫자여야 합니다.") from exc


class ExhibitionPlayer:
    def __init__(self, trace):
        if type(trace) is not ExhibitionTrace:
            raise TypeError("Expected a completed ExhibitionTrace.")
        self.trace = trace
        self._current_index = 0

    @property
    def current_index(self):
        return self._current_index

    @property
    def step_count(self):
        return len(self.trace.actions)

    @property
    def current_frame(self):
        return self.trace.frame(self.current_index)

    @property
    def pending_action(self):
        return self.trace.actions[self.current_index] if self.current_index < self.step_count else None

    @property
    def completed_route(self):
        return tuple(a.target for a in self.trace.actions[:self.current_index])

    def go_to(self, index):
        frame = self.trace.frame(index)
        self._current_index = index
        return frame

    def next(self):
        if self.current_index == self.step_count:
            return False
        self.go_to(self.current_index + 1)
        return True


class ExhibitionPlayback(Stage3ModeledPlayback):
    """Narrow clock bridge, with genuine exhibition types and no fake execution.

The base consumes durations and calls next() only at completed boundaries.
In interval mode its internal interval units are presentation microseconds.
Committed Model C is always the exact integer in current_frame, in either mode.
Mode/interval changes sample the old clock and preserve the partial fraction.
An explicit seek discards partial motion and selects exactly the chosen frame.
"""

    def __init__(self, player, *, clock=monotonic_ns):
        super().__init__(player, clock=clock)
        self._mode = INTERVAL_MODE
        self._interval_us = Fraction(250_000)

    @property
    def mode(self):
        return self._mode

    @property
    def interval_ms(self):
        return self._interval_us / 1000

    @property
    def interval_us(self):
        return self._interval_us

    @property
    def cps(self):
        return 1_000_000 / self._interval_us

    @property
    def pending_trace(self):
        return self._player.pending_action

    @property
    def pending_duration_us(self):
        if self.pending_trace is None:
            return None
        return self.interval_us if self.mode == INTERVAL_MODE else super().pending_duration_us

    @property
    def speed(self):
        return Fraction(1) if self.mode == INTERVAL_MODE else super().speed

    @property
    def model_speed(self):
        return super().speed

    def set_mode(self, mode):
        if mode not in (INTERVAL_MODE, MODEL_C_MODE):
            raise ValueError("Unknown exhibition playback mode.")
        self.update()
        fraction = self.progress
        self._mode = mode
        self._partial_modeled_us = fraction * (self.pending_duration_us or 0)

    def set_interval(self, milliseconds):
        value = _rate_number(milliseconds)
        if not MIN_INTERVAL_MS <= value <= MAX_INTERVAL_MS:
            raise ValueError("관람 간격은 20~10000 ms 범위입니다.")
        self._set_interval_us(value * 1000)

    def set_cps(self, cps):
        value = _rate_number(cps)
        if not Fraction(1, 10) <= value <= 50:
            raise ValueError("관람 속도는 0.1~50 CPS 범위입니다.")
        self._set_interval_us(1_000_000 / value)

    def _set_interval_us(self, duration):
        self.update()
        fraction = self.progress
        self._interval_us = duration
        self._partial_modeled_us = fraction * (self.pending_duration_us or 0)

    def seek(self, index):
        self._player.trace.frame(index)  # reject invalid seeks without changing state
        self.cancel_partial()
        return self._player.go_to(index)

    @property
    def cursor(self):
        pending = self.pending_trace
        if pending is None or (not self.running and not self.partial_modeled_us):
            return self._player.current_frame.cursor
        fraction = float(self.progress)
        start, end = pending.cursor_before, pending.target
        return tuple(a + fraction * (b - a) for a, b in zip(start, end))

    @property
    def target(self):
        if self.pending_trace is not None and (self.running or self.partial_modeled_us):
            return self.pending_trace.target
        index = self._player.current_index
        return self._player.trace.actions[index - 1].target if index else None
