"""Public exact-probability follow-up Q with bounded, caller-owned count caching.

The fast path uses the reviewed local proof and cost rules with guessing disabled.
Every other decision requires a complete Unit 4 base. Cache entries contain only
complete public bases and live in an explicitly created ExactPilot instance.
"""

from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass, fields
from fractions import Fraction
from math import isfinite
from time import perf_counter, process_time_ns

from stage4_belief import (
    BeliefLimits, BeliefRequest, BeliefResult, COUNTER_VERSION, FLAGGED,
    PRIOR_ID, count_public, exact_json,
)
from stage4_candidates import EvidenceInput, _validate_base
from stage4_posterior import neighbor_indices, public_digest
from stage4_rollout import pilot_p0


Q_ID = "PUBLIC_EXACT_COST_Q_V1"
Q_WORK_ID = "Q_LOCAL_P0_V2_PLUS_CANDIDATE_VISITS_AND_UNIT4_WORK_V1"
_Q_ACTIVE = ContextVar("stage4_exact_pilot_active", default=False)


def _integer_payload(value):
    if type(value) is int:
        return value
    if type(value) is str and str(int(value)) == value:
        return int(value)
    raise ValueError("Expected an exact integer payload")


def _seconds_payload(value):
    return _integer_payload(value) if type(value) is str else value


def _payload_fields(payload, cls):
    if type(payload) is not dict or set(payload) - {field.name for field in fields(cls)}:
        raise ValueError("Unknown or invalid public payload fields")
    return dict(payload)


def _grid_payload(value):
    if type(value) not in (tuple, list):
        raise TypeError("A public grid is required")
    return tuple(tuple(_integer_payload(cell) for cell in row) for row in value)


def _validate_integer_limits(instance, caps):
    for name, cap in caps:
        value = getattr(instance, name)
        if type(value) is not int or not 0 <= value <= cap:
            raise ValueError(f"{name} must be an integer in 0..{cap}")


def _validate_seconds(value, cap):
    if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= cap:
        raise ValueError(f"max_seconds must be finite and in 0..{cap}")


@dataclass(frozen=True, slots=True)
class ExactLimits:
    max_cells: int = 480
    local_work: int = 20_000
    exact_work: int = 200_000
    max_seconds: float = 2.0

    def __post_init__(self):
        _validate_integer_limits(self, (
            ("max_cells", 480), ("local_work", 20_000), ("exact_work", 200_000)))
        _validate_seconds(self.max_seconds, 2.0)

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        for name in values:
            values[name] = (_seconds_payload(values[name]) if name == "max_seconds"
                            else _integer_payload(values[name]))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ExactRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int
    allow_guess: bool
    prior_id: str = PRIOR_ID
    limits: ExactLimits = ExactLimits()

    def __post_init__(self):
        public = BeliefRequest(self.observation, self.num_mines, prior_id=self.prior_id)
        object.__setattr__(self, "observation", public.observation)
        if type(self.num_mines) is not int:
            raise TypeError("num_mines must be an integer")
        if type(self.counted_inputs) is not int or self.counted_inputs < 0:
            raise ValueError("counted_inputs must be a nonnegative integer")
        if type(self.allow_guess) is not bool or type(self.limits) is not ExactLimits:
            raise TypeError("Explicit guess setting and ExactLimits required")

    @property
    def identity(self):
        return public_digest((Q_ID, self.to_payload()))

    def to_payload(self):
        return exact_json(self)

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        if "observation" in values:
            values["observation"] = _grid_payload(values["observation"])
        for name in ("num_mines", "counted_inputs"):
            if name in values:
                values[name] = _integer_payload(values[name])
        if "limits" in values:
            values["limits"] = ExactLimits.from_payload(values["limits"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ExactResult:
    pilot_id: str
    request_id: str
    status: str
    reason: str
    sequence: tuple[EvidenceInput, ...]
    basis: str | None
    terminal_outcome: str | None
    mine_probability: Fraction | None
    local_result: object | None
    base_result: BeliefResult | None
    proven_safe: tuple[int, ...]
    proven_mines: tuple[int, ...]
    local_work: int
    exact_work: int
    backend_calls: int
    cache_hit: bool
    cache_entries: int
    elapsed_seconds: float
    cpu_nanoseconds: int
    work_accounting_complete: bool
    error: str | None

    def to_dict(self):
        return exact_json(self)


class _Stop(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class _Meter:
    def __init__(self, request, cancelled):
        self.request, self.cancelled = request, cancelled
        self.started = perf_counter()
        self.cpu_started = process_time_ns()
        self.local_work = 0
        self.pending = None

    def check(self):
        if self.pending is not None:
            raise self.pending
        if self.cancelled is not None:
            value = self.cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _Stop("CANCELLED", "CANCELLED")
        if perf_counter() - self.started >= self.request.limits.max_seconds:
            raise _Stop("INSUFFICIENT", "TIME_LIMIT")

    def relay(self):
        try:
            self.check()
        except Exception as exc:
            self.pending = exc
            return True
        return False

    def tick(self, amount=1):
        self.check()
        if self.local_work + amount > self.request.limits.local_work:
            raise _Stop("INSUFFICIENT", "LOCAL_WORK_LIMIT")
        self.local_work += amount

    def remaining(self):
        self.check()
        return max(0.0, self.request.limits.max_seconds - (perf_counter() - self.started))


def _safe_sequence(grid, safe, mines, meter):
    """Preserve P0 V2's safe-candidate key, using exact facts after a stalled proof."""
    width = len(grid[0])
    flat = tuple(value for row in grid for value in row)
    adjacent = neighbor_indices(width, len(grid))
    closed = frozenset(cell for cell, value in enumerate(flat) if value < 0)
    candidates = []

    def move(action, cell):
        return EvidenceInput(action, cell % width, cell // width)

    def add(kind, pivot, targets, sequence):
        meter.tick(len(targets) + 1)
        zero = any(all(n not in closed or n in safe for n in adjacent[t]) for t in targets)
        key = (-Fraction(len(targets), len(sequence)), -int(zero), len(sequence),
               ("OPEN", "CHORD").index(kind), pivot,
               tuple((m.action, m.y, m.x) for m in sequence))
        candidates.append((key, sequence))

    for cell in sorted(safe):
        prefix = (move("FLAG", cell),) if flat[cell] == FLAGGED else ()
        add("OPEN", cell, (cell,), prefix + (move("OPEN", cell),))
    for pivot, clue in enumerate(flat):
        meter.tick()
        if clue <= 0:
            continue
        cells = tuple(n for n in adjacent[pivot] if n in closed)
        flags = set(cells) & mines
        targets = tuple(n for n in cells if n not in flags)
        if len(flags) != clue or not targets or not set(targets) <= safe:
            continue
        changes = tuple(n for n in cells if (flat[n] == FLAGGED) != (n in flags))
        if changes and len(targets) < 2:
            continue
        add("CHORD", pivot, targets,
            tuple(move("FLAG", n) for n in changes) + (move("CHORD", pivot),))
    meter.tick()
    return min(candidates, key=lambda item: item[0])[1]


class ExactPilot:
    """A bounded public-base cache. G creates one instance for each G request."""

    def __init__(self, cache_entries=256):
        if type(cache_entries) is not int or not 0 <= cache_entries <= 256:
            raise ValueError("cache_entries must be in 0..256")
        self._capacity = cache_entries
        self._cache = OrderedDict()

    def clear(self):
        self._cache.clear()

    def choose(self, request, *, cancelled=None):
        if type(request) is not ExactRequest:
            raise TypeError("ExactRequest required")
        if cancelled is not None and not callable(cancelled):
            raise TypeError("cancelled must be callable or None")
        meter = _Meter(request, cancelled)
        identity = request.identity
        local = base = None
        safe, mines = (), ()
        sequence, basis, terminal, probability = (), None, None, None
        exact_work = backend_calls = 0
        cache_hit = False
        error = None
        work_accounting_complete = True
        token = None
        status, reason = "INSUFFICIENT", "NOT_STARTED"
        try:
            if _Q_ACTIVE.get():
                raise _Stop("ERROR", "RECURSIVE_Q_FORBIDDEN")
            token = _Q_ACTIVE.set(True)
            meter.check()
            if request.prior_id != PRIOR_ID:
                raise _Stop("UNSUPPORTED", "PRIOR_UNSUPPORTED")
            if len(request.observation) * len(request.observation[0]) > request.limits.max_cells:
                raise _Stop("UNSUPPORTED", "CELL_LIMIT")
            if request.limits.local_work == 0 or request.limits.exact_work == 0:
                raise _Stop("INSUFFICIENT", "ZERO_WORK_LIMIT")
            local = pilot_p0(request.observation, request.num_mines, request.counted_inputs,
                             False, max_work=request.limits.local_work, cancelled=meter.relay)
            meter.local_work = local.work
            meter.check()
            safe, mines = local.proven_safe, local.proven_mines
            if local.status == "ERROR":
                if local.reason == "ValueError: Contradictory public local constraints":
                    raise _Stop("INCONSISTENT_INPUT", "LOCAL_CONTRADICTION")
                raise ValueError("Local proof failed: " + local.reason)
            if local.status == "READY":
                sequence, basis, probability = local.sequence, "BASIC_RULES", Fraction(0)
                status, reason = "READY", "PROVEN_SAFE_COST"
            else:
                if local.reason == "PILOT_WORK_LIMIT":
                    raise _Stop("INSUFFICIENT", "LOCAL_WORK_LIMIT")
                key = (COUNTER_VERSION, request.prior_id, request.observation, request.num_mines)
                base = self._cache.get(key)
                if base is None:
                    query = BeliefRequest(
                        request.observation, request.num_mines,
                        limits=BeliefLimits(max_cells=request.limits.max_cells,
                                            max_events=0, max_work=request.limits.exact_work,
                                            max_seconds=min(2.0, meter.remaining())),
                        prior_id=request.prior_id)
                    backend_calls = 1
                    work_accounting_complete = False
                    base = count_public(query, cancelled=meter.relay)
                    if type(base) is not BeliefResult or base.request_id != query.identity:
                        raise ValueError("Exact base request binding mismatch")
                    exact_work = base.diagnostics.work
                    if type(exact_work) is not int or not 0 <= exact_work <= request.limits.exact_work:
                        raise ValueError("Invalid exact work accounting")
                    work_accounting_complete = True
                else:
                    cache_hit = True
                meter.check()
                if base.status != "COMPLETE":
                    if base.status not in ("INSUFFICIENT", "CANCELLED", "ERROR",
                                           "INCONSISTENT_INPUT", "UNSUPPORTED"):
                        raise ValueError("Unexpected base-only result status")
                    raise _Stop(base.status, "BASE_" + base.reason)
                counts = _validate_base(base.base, request)
                if base.events:
                    raise ValueError("A base-only result is required")
                if self._capacity and not cache_hit:
                    self._cache[key] = base
                    if len(self._cache) > self._capacity:
                        self._cache.popitem(last=False)
                width = len(request.observation[0])
                total = base.base.total_worlds
                safe = tuple(sorted(y * width + x for (x, y), count in counts.items() if count == 0))
                mines = tuple(sorted(y * width + x for (x, y), count in counts.items() if count == total))
                viable = [(count, 2 if request.observation[y][x] == FLAGGED else 1, y, x)
                          for (x, y), count in counts.items() if count < total]
                if not viable:
                    raise _Stop("DEFER", "NO_VIABLE_OPEN")
                if safe:
                    sequence = _safe_sequence(request.observation, set(safe), set(mines), meter)
                    basis, probability = "UNIT4_EXACT_BASE", Fraction(0)
                    status, reason = "READY", "EXACT_SAFE_COST"
                elif not request.allow_guess:
                    terminal = "GUESS_BLOCKED"
                    basis = "UNIT4_EXACT_BASE"
                    raise _Stop("DEFER", "GUESS_BLOCKED")
                else:
                    meter.tick(len(viable) + 1)
                    count, _, y, x = min(viable)
                    prefix = (EvidenceInput("FLAG", x, y),) if request.observation[y][x] == FLAGGED else ()
                    sequence = prefix + (EvidenceInput("OPEN", x, y),)
                    probability = Fraction(count, total)
                    basis = "UNIT4_EXACT_BASE"
                    status, reason = "READY", "EXACT_MINIMUM_RISK_OPEN"
            meter.check()
        except _Stop as exc:
            status, reason = exc.status, exc.reason
            sequence, probability = (), None
            if terminal != "GUESS_BLOCKED":
                basis, terminal = None, None
        except Exception as exc:
            status, reason = "ERROR", "EXACT_PILOT_ERROR"
            sequence, probability, basis, terminal = (), None, None, None
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if token is not None:
                _Q_ACTIVE.reset(token)
        return ExactResult(Q_ID, identity, status, reason, sequence, basis, terminal, probability,
                           local, base, safe, mines, meter.local_work, exact_work, backend_calls,
                           cache_hit, len(self._cache), perf_counter() - meter.started,
                           process_time_ns() - meter.cpu_started, work_accounting_complete, error)


def choose_exact(request, *, cancelled=None):
    """Stateless Q entry point. The instance form enables explicit bounded reuse."""
    return ExactPilot(cache_entries=0).choose(request, cancelled=cancelled)

