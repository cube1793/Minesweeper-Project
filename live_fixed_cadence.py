"""Bounded fixed-rate targets, separate from real restart/input timestamps.

Only lateness in [0, P/10] carries the target phase forward. Larger lateness
starts at the actual input plus P; there is no backlog or input authorization.
"""

from dataclasses import dataclass, field
from fractions import Fraction


@dataclass(frozen=True, init=False)
class FixedCadence:
    period_ns: int
    started_ns: int
    target_ns: int = field(init=False)
    last_actual_ns: int | None = field(default=None, init=False)
    transition_reason: str = field(default="explicit_restart", init=False)

    def __init__(self, interval_ms, started_ns):
        """Legacy integer-ms entry point; execution always uses period_ns."""
        if type(interval_ms) is not int or not 0 <= interval_ms <= 2000:
            raise ValueError("Fixed interval must be an integer between 0 and 2000 ms.")
        self._initialize(interval_ms * 1_000_000, started_ns)

    def _initialize(self, period_ns, started_ns):
        if (type(period_ns) is not int
                or (period_ns != 0 and not 1_000_000 <= period_ns <= 2_000_000_000)):
            raise ValueError("Fixed period must be zero or 1–2000 ms in integer ns.")
        if type(started_ns) is not int or started_ns < 0:
            raise ValueError("A nonnegative monotonic nanosecond timestamp is required.")
        object.__setattr__(self, "period_ns", period_ns)
        object.__setattr__(self, "started_ns", started_ns)
        object.__setattr__(self, "target_ns", started_ns + period_ns)
        object.__setattr__(self, "last_actual_ns", None)
        object.__setattr__(self, "transition_reason", "explicit_restart")

    @classmethod
    def from_period_ns(cls, period_ns, started_ns):
        cadence = object.__new__(cls)
        cadence._initialize(period_ns, started_ns)
        return cadence

    @property
    def interval_ms(self):
        """Exact derived unit for legacy readers, never an execution authority."""
        return Fraction(self.period_ns, 1_000_000)

    @property
    def deadline_ns(self):
        return self.target_ns

    @classmethod
    def from_input(cls, interval_ms, actual_ns):
        """A committed input with no valid phase starts a fresh full period."""
        following = cls(interval_ms, actual_ns)
        return following._with_actual(actual_ns)

    @classmethod
    def from_input_ns(cls, period_ns, actual_ns):
        return cls.from_period_ns(period_ns, actual_ns)._with_actual(actual_ns)

    def _with_actual(self, actual_ns):
        following = self
        object.__setattr__(following, "last_actual_ns", actual_ns)
        object.__setattr__(following, "transition_reason", "missing_target_restart")
        return following

    def after_input(self, actual_ns):
        following = self.from_input_ns(self.period_ns, actual_ns)
        period_ns = self.period_ns
        lateness_ns = actual_ns - self.target_ns
        if period_ns == 0:
            reason = "zero_interval"
        elif 0 <= lateness_ns and lateness_ns * 10 <= period_ns:
            object.__setattr__(following, "target_ns", self.target_ns + period_ns)
            reason = "phase_kept"
        elif lateness_ns > 0:
            reason = "late_restart"
        else:
            reason = "invalid_target_restart"
        object.__setattr__(following, "transition_reason", reason)
        return following

    def remaining_ms(self, now_ns):
        return max(0, (self.deadline_ns - now_ns + 999_999) // 1_000_000)
