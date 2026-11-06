"""Versioned presentation-only distance viewing interval; no policy/accounting input.

Descriptive bounded-log fit, not a human motion law. Decimal precision50 and
ROUND_HALF_EVEN for sqrt/ln; exact rational division by rate, then ceil to ns.
No reads of external research/output files occur at runtime.
"""
from dataclasses import dataclass, field
from decimal import Decimal, localcontext, InvalidOperation, ROUND_HALF_EVEN
from fractions import Fraction
from live_pacing import PacingRate, ceil_fraction

DISTANCE = "distance"
PROFILE_ID = "distance_view_log_v1"
CANDIDATES_SHA256 = "412adaf2e434c25685659737cf5b22b1d4495517070f296bf6775fb12544ea40"
FIT_PLAN_SHA256 = "d06712b09f58627d12c1f3b733afac9b4d31e5ce90ad9b76e31ef432950596a2"
FIT_POINTER = "/full_data_descriptive_fit/bounded_log"
A = Decimal("37.55779754656098")
B = Decimal("189.88338306970934")
LOWER_MS = Decimal("91.66666666666667")
UPPER_MS = Decimal("550.0")
DISTANCE_CAP = Decimal(16)
PRECISION = 50


def _distance(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Distance must be finite and nonnegative.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid distance.") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Distance must be finite and nonnegative.")
    return result


def base_ms(distance):
    distance = min(_distance(distance), DISTANCE_CAP)
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        return min(UPPER_MS, max(LOWER_MS, A + B * (1 + distance).ln()))


def target_distance(cursor, target):
    """Read existing public/actual endpoints, never mutate a policy cursor."""
    def coordinate(value):
        if (not isinstance(value, (tuple, list)) or len(value) != 2
                or any(type(n) is not int or n < 0 for n in value)):
            raise ValueError("Expected nonnegative integer cell coordinates.")
        return value
    target = coordinate(target)
    if cursor is None:
        return Decimal(0), "public_actual_cursor_absent"
    cursor = coordinate(cursor)
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        square = sum((a - b) ** 2 for a, b in zip(cursor, target))
        return Decimal(square).sqrt(), None


@dataclass(frozen=True)
class DistanceWait:
    distance: Decimal
    rate: PacingRate
    started_ns: int
    fallback_reason: str | None = None
    duration_ns: int = field(init=False)

    def __post_init__(self):
        if type(self.started_ns) is not int or self.started_ns < 0:
            raise ValueError("Expected a nonnegative integer monotonic start.")
        if not isinstance(self.rate, PacingRate):
            raise ValueError("Expected a validated viewing rate.")
        distance = _distance(self.distance)
        object.__setattr__(self, "distance", distance)
        duration = ceil_fraction(Fraction(base_ms(distance)) * 1_000_000 / self.rate.rate)
        object.__setattr__(self, "duration_ns", max(1, duration))

    @classmethod
    def from_targets(cls, cursor, target, rate, started_ns):
        distance, reason = target_distance(cursor, target)
        return cls(distance, rate, started_ns, reason)

    @property
    def delay_ms(self):
        return (self.duration_ns + 999_999) // 1_000_000

    @property
    def deadline_ns(self):
        return self.started_ns + self.duration_ns

    def remaining_ms(self, now_ns):
        if type(now_ns) is not int or now_ns < 0:
            raise ValueError("Expected a nonnegative integer monotonic time.")
        return max(0, (self.deadline_ns - now_ns + 999_999) // 1_000_000)

    def metadata(self):
        return dict(profile_id=PROFILE_ID, distance_cells=str(self.distance),
                    rate=str(self.rate.rate), started_ns=self.started_ns,
                    duration_ns=self.duration_ns, deadline_ns=self.deadline_ns,
                    fallback_reason=self.fallback_reason)

