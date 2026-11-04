"""Exact, presentation-only pacing for one already selected Live input.

No policy selection, profile loading, model accounting or Qt dependencies.
The frozen one-cell reference is a unit conversion, not a measured game CPS.
"""

from dataclasses import dataclass, field
from fractions import Fraction
from re import fullmatch


FIXED = "fixed"
MODEL_C = "model_c"
REFERENCE_US = 126005
MIN_RATE = Fraction(1, 20)
MAX_RATE = Fraction(8)


def exact_value(value):
    """Parse an explicit decimal edit without a binary-float round trip."""
    if type(value) not in (str, int, Fraction):
        raise ValueError("A finite decimal or exact fraction is required.")
    if isinstance(value, str):
        value = value.strip()
        if len(value) > 64 or not fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+|\d+/\d+)", value):
            raise ValueError("A decimal or integer fraction is required.")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("A finite decimal or exact fraction is required.") from exc


def interval_ms_from_cps(value):
    """Convert fixed-interval CPS to integer ms, rounding exact halves up."""
    cps = exact_value(value)
    if not Fraction(1, 2) <= cps <= 1000:
        raise ValueError("Fixed-interval CPS must be between 0.5 and 1000.")
    interval = 1000 / cps
    return (2 * interval.numerator + interval.denominator) // (2 * interval.denominator)


def cps_from_interval_ms(interval):
    """Return the applied interval's exact CPS; zero ms means maximum speed."""
    if type(interval) is not int or not 0 <= interval <= 2000:
        raise ValueError("Fixed interval must be an integer between 0 and 2000 ms.")
    return Fraction(1000, interval) if interval else None


@dataclass(frozen=True)
class FixedPeriod:
    """One execution period; source/requested only preserve the user's display."""
    source: str
    requested: Fraction
    period_ns: int = field(init=False)

    def __post_init__(self):
        value = exact_value(self.requested)
        if self.source == "cps":
            if not Fraction(1, 2) <= value <= 1000:
                raise ValueError("Target CPS must be between 0.5 and 1000.")
            period = 1_000_000_000 / value
        elif self.source == "ms":
            if value != 0 and not 1 <= value <= 2000:
                raise ValueError("Interval must be zero or between 1 and 2000 ms.")
            period = value * 1_000_000
        else:
            raise ValueError("Fixed input source must be cps or ms.")
        object.__setattr__(self, "requested", value)
        object.__setattr__(self, "period_ns", ceil_fraction(period))

    @property
    def interval_ms(self):
        return Fraction(self.period_ns, 1_000_000)

    @property
    def target_cps(self):
        if not self.period_ns:
            return None
        return self.requested if self.source == "cps" else Fraction(1_000_000_000, self.period_ns)


@dataclass(frozen=True)
class PacingRate:
    rate: Fraction = Fraction(1)

    def __post_init__(self):
        rate = exact_value(self.rate)
        if not MIN_RATE <= rate <= MAX_RATE:
            raise ValueError("Rate must be between 0.05 and 8.")
        object.__setattr__(self, "rate", rate)

    @classmethod
    def from_cps(cls, value):
        return cls(exact_value(value) * REFERENCE_US / 1_000_000)

    @property
    def cps(self):
        return self.rate * 1_000_000 / REFERENCE_US

    def duration_us(self, modeled_action_us):
        if type(modeled_action_us) is not int or modeled_action_us <= 0:
            raise ValueError("One input's positive integer Model C cost is required.")
        return modeled_action_us / self.rate


def ceil_fraction(value):
    return -(-value.numerator // value.denominator)


def decimal_display(value, places=6):
    """Return rounded text and whether it is approximate; never feed it back."""
    scale = 10 ** places
    rounded = round(value * scale)
    whole, part = divmod(rounded, scale)
    text = f"{whole}.{part:0{places}d}".rstrip("0").rstrip(".")
    return text, Fraction(rounded, scale) != value


@dataclass(frozen=True)
class PacingWait:
    modeled_action_us: int
    rate: PacingRate
    started_ns: int

    @property
    def exact_us(self):
        return self.rate.duration_us(self.modeled_action_us)

    @property
    def delay_ms(self):
        return max(1, ceil_fraction(self.exact_us / 1000))

    @property
    def deadline_ns(self):
        # Gate on the same quantized execution delay given to the cursor.
        return self.started_ns + self.delay_ms * 1_000_000

    def remaining_ms(self, now_ns):
        return max(0, (self.deadline_ns - now_ns + 999_999) // 1_000_000)
