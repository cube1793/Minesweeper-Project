"""Unconnected common-posterior S/M/R model followed by a fixed public F.

Values describe only the declared shortlist, common bank and fixed F. They
are neither full-game optima nor expectations of subsequent S/M/R replanning.
The evaluator owns sampled layouts; F never receives a layout or reward.
"""
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass, fields, replace
from fractions import Fraction
from time import perf_counter

from stage4_belief import PRIOR_ID, exact_json
from stage4_candidates import CandidateLimits, CandidateRequest, analyze_candidates
from stage4_efficiency_plan import PlanLimits, plan_safe
from stage4_exact_pilot import (ExactLimits, ExactPilot, ExactRequest, ExactResult,
    UNIT10_SUMMED, _integer_payload, _payload_fields, _seconds_payload,
    _validate_integer_limits, _validate_seconds, q_pilot_id)
from stage4_objective_pilot import _complete_scores
from stage4_policy import _shortlist, _validate_root, model_order
from stage4_posterior import PosteriorRequest, SamplerLimits, public_digest, sample_posterior
from stage4_public_kernel import KernelLimits, KernelRequest, infer_public
from stage4_runtime_kernel import WORK_VERSION, infer_public_indexed
from stage4_rollout import VirtualBoard

MODEL_ID = "RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V2_FIXED_LIMITS"
F_ID = "PUBLIC_F_INDEXED_COVER_UNIT10_V1:" + WORK_VERSION
V1_F_ID = "PUBLIC_F_V1_COVER_UNIT10_V1:prepaid_bounded_bitsets_v1"
_MODEL_ACTIVE = ContextVar("stage4_runtime_model_active", default=False)
_F_ACTIVE = ContextVar("stage4_runtime_followup_active", default=False)
_KERNEL_RESOURCE = {"CELL_LIMIT", "CONSTRAINT_LIMIT", "DERIVED_LIMIT", "WORK_LIMIT", "TIME_LIMIT"}
_PLAN_RESOURCE = {"NO_SAFE_PROGRESS", "SUBSET_LIMIT", "TIME_LIMIT"}


class _Stop(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason
        super().__init__(reason)


class _Clock:
    def __init__(self, seconds, cancelled):
        self.started = perf_counter()
        self.deadline = self.started + seconds
        self.cancelled, self.pending = cancelled, None

    def check(self):
        if self.pending is not None:
            raise self.pending
        if self.cancelled is not None:
            value = self.cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _Stop("CANCELLED", "CANCELLED")
        if perf_counter() >= self.deadline:
            raise _Stop("RESOURCE_LIMIT", "TIME_LIMIT")

    def remaining(self):
        self.check()
        return max(0.0, self.deadline - perf_counter())

    def relay(self):
        try:
            self.check()
        except Exception as exc:
            self.pending = exc
            return True
        return False


@dataclass(frozen=True, slots=True)
class FollowupLimits:
    kernel: KernelLimits = KernelLimits()
    plan: PlanLimits = PlanLimits()
    q: ExactLimits = ExactLimits()
    max_seconds: float = 5.0
    kernel_kind: str = "indexed"

    def __post_init__(self):
        if type(self.kernel) is not KernelLimits or type(self.plan) is not PlanLimits or type(self.q) is not ExactLimits:
            raise TypeError("Typed followup limits required")
        _validate_seconds(self.max_seconds, 5.0)
        if self.kernel_kind not in ("indexed", "v1"):
            raise ValueError("Unknown followup kernel")

    @property
    def followup_id(self):
        return F_ID if self.kernel_kind == "indexed" else V1_F_ID


@dataclass(frozen=True, slots=True)
class FollowupRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int
    allow_guess: bool
    prior_id: str = PRIOR_ID
    limits: FollowupLimits = FollowupLimits()

    def __post_init__(self):
        public = KernelRequest(self.observation, self.num_mines, self.counted_inputs, self.prior_id)
        object.__setattr__(self, "observation", public.observation)
        if type(self.allow_guess) is not bool or type(self.limits) is not FollowupLimits:
            raise TypeError("Explicit public guess setting and FollowupLimits required")

    @property
    def identity(self):
        return public_digest((self.limits.followup_id, self))

    @property
    def logical_key(self):
        # Wall time controls completion, not a completed logical choice. Results
        # reached through a TIME_LIMIT fallback are explicitly not cacheable.
        caps = tuple((type(part).__name__, tuple((f.name, getattr(part, f.name))
                     for f in fields(part) if f.name != "max_seconds"))
                     for part in (self.limits.kernel, self.limits.plan, self.limits.q))
        return (self.limits.followup_id, self.observation, self.num_mines,
                self.counted_inputs, self.allow_guess, self.prior_id, caps)


@dataclass(frozen=True, slots=True)
class RuntimeUsage:
    kernel_calls: int = 0
    kernel_work: int = 0
    q_calls: int = 0
    q_local: int = 0
    unit10_calls: int = 0
    unit10_units: int = 0
    unit4_calls: int = 0
    unit4_work: int = 0
    sampler_work: int = 0
    f_lookups: int = 0
    f_misses: int = 0
    f_hits: int = 0
    cache_peak: int = 0
    virtual_inputs: int = 0
    started_rows: int = 0
    accounting_complete: bool = True


@dataclass(frozen=True, slots=True)
class Settlement:
    resource: str
    reserved: int
    actual: int | None
    status: str


@dataclass(frozen=True, slots=True)
class FollowupResult:
    followup_id: str
    request_id: str
    request: FollowupRequest
    status: str
    reason: str
    sequence: tuple
    source: str | None
    terminal_outcome: str | None
    kernel_request: object | None
    facts: object | None
    plan: object | None
    q_request: object | None
    q_result: object | None
    usage: RuntimeUsage
    settlements: tuple[Settlement, ...]
    cacheable: bool
    elapsed_seconds: float
    error: str | None = None

    def to_payload(self):
        return exact_json(self)


def _settle(items, resource, reserved, actual):
    if type(actual) is not int or not 0 <= actual <= reserved:
        items.append(Settlement(resource, reserved, None, "UNKNOWN_SPEND"))
        raise ValueError("UNKNOWN_SPEND:" + resource)
    items.append(Settlement(resource, reserved, actual, "SETTLED"))
    return actual


def _settle_group(items, values):
    """Record every reservation, including when an earlier field is unknown."""
    result, unknown = {}, False
    for resource, reserved, actual in values:
        try:
            result[resource] = _settle(items, resource, reserved, actual)
        except ValueError:
            result[resource] = reserved  # conservative charge, never known zero
            unknown = True
    return result, not unknown


def choose_followup(request, *, cancelled=None):
    """Fixed F: kernel -> first verified safe cost group -> exact safe/min-risk Q.

No S/M/R recursion, mode, target, sampled layout, actual seed or static3BV.
All calls reserve before execution and settle even on cancellation/failure.
"""
    if type(request) is not FollowupRequest:
        raise TypeError("FollowupRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable")
    clock = _Clock(request.limits.max_seconds, cancelled)
    kr = facts = plan = qr = reply = None
    sequence, source, terminal = (), None, None
    usage, settlements = RuntimeUsage(), []
    token = None
    error = None
    cacheable = True
    try:
        if _F_ACTIVE.get():
            raise _Stop("ERROR", "RECURSIVE_F_FORBIDDEN")
        token = _F_ACTIVE.set(True)
        clock.check()
        kr = KernelRequest(request.observation, request.num_mines, request.counted_inputs, request.prior_id,
            limits=replace(request.limits.kernel, max_seconds=min(request.limits.kernel.max_seconds, clock.remaining())))
        usage = replace(usage, kernel_calls=1, accounting_complete=False)
        try:
            fn = infer_public_indexed if request.limits.kernel_kind == "indexed" else infer_public
            facts = fn(kr, cancelled=clock.relay)
        finally:
            spent = _settle(settlements, "kernel_work", kr.limits.max_work, getattr(facts, "work", None))
            usage = replace(usage, kernel_work=spent, accounting_complete=True)
        clock.check()
        if facts.request_id != kr.identity or facts.error is not None:
            raise ValueError("F_KERNEL_IDENTITY_OR_ERROR")
        if facts.status == "COMPLETE":
            plan = plan_safe(kr, facts, limits=replace(request.limits.plan,
                max_seconds=min(request.limits.plan.max_seconds, clock.remaining())), cancelled=clock.relay)
            clock.check()
            if plan.request_id != kr.identity or plan.proof_id != facts.proof_id or plan.error is not None:
                raise ValueError("F_PLAN_IDENTITY_OR_ERROR")
            if plan.status == "READY":
                sequence, source = plan.group.sequence, "PUBLIC_KERNEL"
                status, reason = "READY", plan.reason
            elif plan.status not in _PLAN_RESOURCE:
                raise _Stop("ERROR" if plan.status == "ERROR" else plan.status, "PLAN_"+plan.status)
            else:
                cacheable = plan.status != "TIME_LIMIT"
        elif facts.status not in _KERNEL_RESOURCE:
            raise _Stop("INCONSISTENT_INPUT" if facts.status == "INCONSISTENT" else facts.status,
                        "KERNEL_"+facts.status)
        else:
            cacheable = facts.status != "TIME_LIMIT"
        if not sequence:
            qr = ExactRequest(request.observation, request.num_mines, request.counted_inputs, request.allow_guess,
                request.prior_id, replace(request.limits.q,
                max_seconds=min(request.limits.q.max_seconds, clock.remaining())), UNIT10_SUMMED)
            usage = replace(usage, q_calls=1, accounting_complete=False)
            try:
                reply = ExactPilot(cache_entries=0).choose(qr, cancelled=clock.relay)
            finally:
                paid, known = _settle_group(settlements, (
                    ("q_local", qr.limits.local_work, getattr(reply, "local_work", None)),
                    ("unit10_units", qr.limits.counter_units, getattr(reply, "counter_units_total", None)
                     if getattr(reply, "work_accounting_complete", False) else None)))
                usage = replace(usage, **paid, unit10_calls=getattr(reply, "counter_backend_calls", 1),
                                accounting_complete=known)
                if not known:
                    raise ValueError("UNKNOWN_Q_SPEND")
            clock.check()
            if (type(reply) is not ExactResult or reply.request_id != qr.identity or
                    reply.pilot_id != q_pilot_id(UNIT10_SUMMED) or reply.base_backend != UNIT10_SUMMED or
                    reply.exact_work or reply.error is not None or reply.cache_hit or
                    reply.counter_backend_calls not in (0, 1)):
                raise ValueError("F_Q_IDENTITY_OR_ACCOUNTING")
            if reply.status == "READY":
                if not reply.sequence or reply.mine_probability is None:
                    raise ValueError("F_Q_READY_WITHOUT_EVIDENCE")
                sequence, source = reply.sequence, "EXACT_Q"
                status, reason = "READY", reply.reason
            elif reply.status == "DEFER" and reply.terminal_outcome == "GUESS_BLOCKED":
                status, reason, terminal, source = "GUESS_BLOCKED", "EXACT_NO_SAFE_CELL", "GUESS_BLOCKED", "EXACT_Q"
            else:
                status = "RESOURCE_LIMIT" if reply.status == "INSUFFICIENT" else reply.status
                raise _Stop(status, "Q_"+reply.reason)
        clock.check()
    except _Stop as exc:
        status, reason = exc.status, exc.reason
        sequence, source, terminal, cacheable = (), None, None, False
    except Exception as exc:
        status, reason, error = "ERROR", "FOLLOWUP_ERROR", f"{type(exc).__name__}: {exc}"
        sequence, source, terminal, cacheable = (), None, None, False
    finally:
        if token is not None:
            _F_ACTIVE.reset(token)
    return FollowupResult(request.limits.followup_id, request.identity, request, status, reason,
        sequence, source, terminal, kr, facts, plan, qr, reply, usage, tuple(settlements),
        cacheable and status in ("READY", "GUESS_BLOCKED") and usage.accounting_complete,
        perf_counter()-clock.started, error)


@dataclass(frozen=True, slots=True)
class ModelLimits:
    samples: int = 8
    shortlist: int = 4
    rows: int = 32
    sampler_work: int = 2_000_000
    virtual_inputs: int = 20_000
    row_inputs: int = 512
    f_lookups: int = 16_000
    f_misses: int = 4_096
    kernel_work: int = 60_000_000
    q_local: int = 10_000_000
    unit10_units: int = 30_000_000
    cache_entries: int = 2_048
    max_seconds: float = 30.0
    root: CandidateLimits = CandidateLimits()
    diagnostic: bool = False
    kernel_kind: str = "indexed"

    def __post_init__(self):
        _validate_integer_limits(self, (("samples", 64), ("shortlist", 6), ("rows", 384),
            ("sampler_work", 2_000_000), ("virtual_inputs", 20_000), ("row_inputs", 512),
            ("f_lookups", 16_000), ("f_misses", 4_096), ("kernel_work", 60_000_000),
            ("q_local", 10_000_000), ("unit10_units", 30_000_000), ("cache_entries", 2_048)))
        _validate_seconds(self.max_seconds, 30.0)
        if type(self.root) is not CandidateLimits or type(self.diagnostic) is not bool:
            raise TypeError("Typed root limits and diagnostic flag required")
        if not self.diagnostic and (self.samples > 8 or self.shortlist > 4 or self.rows > 32):
            raise ValueError("Expanded matrix is limited to registered tiny exhaustive diagnostics")
        if self.kernel_kind not in ("indexed", "v1"):
            raise ValueError("Unknown F kernel")

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        for name, value in list(values.items()):
            if name == "root":
                data = _payload_fields(value, CandidateLimits)
                values[name] = CandidateLimits(**{k: _seconds_payload(v) if k == "max_seconds"
                    else _integer_payload(v) for k, v in data.items()})
            elif name == "max_seconds":
                values[name] = _seconds_payload(value)
            elif name not in ("diagnostic", "kernel_kind"):
                values[name] = _integer_payload(value)
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int
    mode: str = "S"
    allow_guess: bool = False
    target: Fraction | None = None
    planning_seed: int | str = 0
    prior_id: str = PRIOR_ID
    limits: ModelLimits = ModelLimits()

    def __post_init__(self):
        public = KernelRequest(self.observation, self.num_mines, self.counted_inputs, self.prior_id)
        object.__setattr__(self, "observation", public.observation)
        if self.mode not in ("S", "M", "R") or type(self.allow_guess) is not bool:
            raise ValueError("Invalid mode or guess setting")
        if type(self.planning_seed) not in (int, str) or type(self.limits) is not ModelLimits:
            raise TypeError("Public planning seed and ModelLimits required")
        if self.target is not None:
            if type(self.target) not in (int, str, Fraction):
                raise TypeError("Exact rational target required")
            object.__setattr__(self, "target", Fraction(self.target))
            if self.target <= 0:
                raise ValueError("Positive target required")
        if self.limits.diagnostic and len(public.observation)*len(public.observation[0]) > 16:
            raise ValueError("Diagnostics are limited to at most16 cells")

    @property
    def identity(self):
        return public_digest((MODEL_ID, self))

    def to_payload(self):
        value = exact_json(self)
        value["planning_seed"] = {"kind": "int" if type(self.planning_seed) is int else "str",
                                  "value": str(self.planning_seed)}
        return value

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        if "observation" in values:
            values["observation"] = tuple(tuple(_integer_payload(v) for v in row) for row in values["observation"])
        for name in ("num_mines", "counted_inputs"):
            if name in values:
                values[name] = _integer_payload(values[name])
        if type(values.get("planning_seed")) is dict:
            seed = values["planning_seed"]
            if set(seed) != {"kind", "value"} or seed["kind"] not in ("int", "str") or type(seed["value"]) is not str:
                raise ValueError("Invalid tagged planning seed")
            values["planning_seed"] = _integer_payload(seed["value"]) if seed["kind"] == "int" else seed["value"]
        if "limits" in values:
            values["limits"] = ModelLimits.from_payload(values["limits"])
        if type(values.get("target")) is dict:
            part = values["target"]
            if set(part) != {"numerator", "denominator"}:
                raise ValueError("Invalid target payload")
            values["target"] = Fraction(_integer_payload(part["numerator"]), _integer_payload(part["denominator"]))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class RuntimeRow:
    candidate_id: str
    sample_index: int
    rank: int | None
    outcome: str = "NOT_STARTED"
    reason: str = "NOT_REACHED"
    value_x: Fraction | None = None
    hit: bool | None = None
    virtual_b: int | None = None
    added_inputs: int = 0
    actions: tuple = ()
    f_call_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class FollowupCall:
    request: FollowupRequest
    result: FollowupResult
    cache_hit: bool
    origin_request_id: str


@dataclass(frozen=True, slots=True)
class ModelResult:
    model_id: str
    followup_id: str
    request_id: str
    status: str
    reason: str
    sequence: tuple
    selected_candidate_id: str | None
    root: object | None
    shortlist: tuple
    posterior: object | None
    rows: tuple[RuntimeRow, ...]
    scores: tuple
    calls: tuple[FollowupCall, ...]
    usage: RuntimeUsage
    settlements: tuple[Settlement, ...]
    information: str
    target_status: str
    elapsed_seconds: float
    error: str | None = None

    def to_payload(self):
        return exact_json(self)


class _Budget(_Clock):
    def __init__(self, request, cancelled):
        super().__init__(request.limits.max_seconds, cancelled)
        self.request = request
        self.usage = RuntimeUsage()
        self.settlements = []

    def increment(self, field, cap, amount=1):
        self.check()
        value = getattr(self.usage, field)
        if value + amount > cap:
            raise _Stop("RESOURCE_LIMIT", field.upper()+"_LIMIT")
        self.usage = replace(self.usage, **{field: value+amount})

    def settle(self, field, reserved, value):
        try:
            actual = _settle(self.settlements, field, reserved, value)
            self.usage = replace(self.usage, **{field:getattr(self.usage, field)+actual})
        except Exception:
            self.usage = replace(self.usage, accounting_complete=False)
            raise

    def settle_group(self, values):
        paid, known = _settle_group(self.settlements, values)
        self.usage = replace(self.usage, **{k:getattr(self.usage, k)+v for k, v in paid.items()},
                             accounting_complete=self.usage.accounting_complete and known)
        if not known:
            raise ValueError("UNKNOWN_MODEL_BACKEND_SPEND")


class _FollowupCache:
    """Created and cleared inside a single model call; stores no input permit."""
    def __init__(self, capacity):
        self.capacity, self.entries = capacity, OrderedDict()

    def clear(self):
        self.entries.clear()

    def choose(self, query, budget, calls):
        limits = budget.request.limits
        budget.increment("f_lookups", limits.f_lookups)
        key = query.logical_key
        found = self.entries.get(key)
        if found is not None:
            budget.check()
            if query.limits.max_seconds <= 0:
                raise _Stop("RESOURCE_LIMIT", "CURRENT_F_DEADLINE")
            if (type(found) is not FollowupResult or not found.cacheable or
                    found.status not in ("READY", "GUESS_BLOCKED") or found.error is not None or
                    found.request_id != found.request.identity or
                    found.followup_id != query.limits.followup_id or
                    found.request.logical_key != key or not found.usage.accounting_complete):
                raise ValueError("INVALID_CACHED_F")
            caps = {"kernel_work": found.request.limits.kernel.max_work,
                    "q_local": found.request.limits.q.local_work,
                    "unit10_units": found.request.limits.q.counter_units}
            for item in found.settlements:
                if (item.resource not in caps or item.status != "SETTLED" or
                        type(item.actual) is not int or type(item.reserved) is not int or
                        not 0 <= item.actual <= item.reserved <= caps[item.resource]):
                    raise ValueError("INVALID_CACHED_F_ACCOUNTING")
            for resource in caps:
                actual = getattr(found.usage, resource)
                if (type(actual) is not int or not 0 <= actual <= caps[resource] or
                        sum(s.actual for s in found.settlements if s.resource == resource) != actual):
                    raise ValueError("INVALID_CACHED_F_ACCOUNTING")
            budget.increment("f_hits", limits.f_lookups)
            calls.append(FollowupCall(query, found, True, found.request_id))
            # The result keeps the original certificate/request identity. This
            # is a reuse receipt, never a fabricated new kernel or Q response.
            return found
        # A miss must be able to run the entire registered F. Remaining model
        # resources constrain whether it starts, never F's logical limits.
        budget.check()
        for resource, reserved, reason in (
                ("kernel_work", query.limits.kernel.max_work, "KERNEL_BUDGET"),
                ("q_local", query.limits.q.local_work, "Q_LOCAL_BUDGET"),
                ("unit10_units", query.limits.q.counter_units, "UNIT10_BUDGET")):
            if getattr(limits, resource) - getattr(budget.usage, resource) < reserved:
                raise _Stop("RESOURCE_LIMIT", reason)
        if budget.remaining() < query.limits.max_seconds:
            raise _Stop("RESOURCE_LIMIT", "F_TIME_RESERVATION")
        budget.increment("f_misses", limits.f_misses)
        result = None
        try:
            result = choose_followup(query, cancelled=budget.relay)
        finally:
            u = getattr(result, "usage", None)
            known = u is not None and u.accounting_complete
            if u is not None:
                budget.usage = replace(budget.usage,
                    kernel_calls=budget.usage.kernel_calls+u.kernel_calls,
                    q_calls=budget.usage.q_calls+u.q_calls,
                    unit10_calls=budget.usage.unit10_calls+u.unit10_calls)
            budget.settle_group((("kernel_work", query.limits.kernel.max_work, u.kernel_work if known else None),
                ("q_local", query.limits.q.local_work, u.q_local if known else None),
                ("unit10_units", query.limits.q.counter_units, u.unit10_units if known else None)))
        calls.append(FollowupCall(query, result, False, result.request_id))
        budget.check()
        if result.request_id != query.identity or result.followup_id != query.limits.followup_id:
            raise ValueError("FOLLOWUP_REQUEST_BINDING")
        if self.capacity and result.cacheable:
            self.entries[key] = result
            if len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
            budget.usage = replace(budget.usage, cache_peak=max(budget.usage.cache_peak, len(self.entries)))
        return result


def _row(request, candidate, sample, index, budget, cache, calls):
    actions, indices = [], []
    outcome, reason = "UNRESOLVED", "NOT_FINISHED"
    value = hit = virtual_b = None
    stopped = None
    try:
        budget.increment("started_rows", request.limits.rows)
        board = VirtualBoard(request.observation, request.num_mines, sample.mines)
        sequence = candidate.sequence
        visited = set()
        while board.outcome is None:
            budget.check()
            before = board.observation
            if before in visited:
                raise ValueError("REPEATED_PUBLIC_STATE")
            visited.add(before)
            for move in sequence:
                if len(actions) >= request.limits.row_inputs:
                    raise _Stop("RESOURCE_LIMIT", "ROW_INPUT_LIMIT")
                budget.increment("virtual_inputs", request.limits.virtual_inputs)
                transition = board.step(move)
                if not transition.counted:
                    raise ValueError("UNCOUNTED_MODEL_INPUT")
                actions.append(move)
                if board.outcome is not None:
                    break
            if board.outcome is not None:
                break
            if sum(v >= 0 for r in board.observation for v in r) <= sum(v >= 0 for r in before for v in r):
                raise ValueError("F_GROUP_DID_NOT_PROGRESS")
            query = FollowupRequest(board.observation, request.num_mines, request.counted_inputs+len(actions),
                request.allow_guess, request.prior_id,
                FollowupLimits(kernel_kind=request.limits.kernel_kind))
            call_index = len(calls)
            try:
                decision = cache.choose(query, budget, calls)
            finally:
                if len(calls) > call_index:
                    indices.append(call_index)
            if decision.status == "GUESS_BLOCKED":
                outcome, reason = "GUESS_BLOCKED", decision.reason
                break
            if decision.status != "READY":
                raise _Stop(decision.status, "F_"+decision.reason)
            if not decision.sequence:
                raise ValueError("EMPTY_F_SEQUENCE")
            sequence = decision.sequence
        if board.outcome is not None:
            outcome, reason = board.outcome, "TERMINAL"
        if outcome == "WON":
            virtual_b = board.static_bbbv()  # evaluator-only terminal reward
            denominator = request.counted_inputs + len(actions)
            if denominator <= 0:
                raise ValueError("INVALID_TERMINAL_PREFIX_COST")
            value = Fraction(virtual_b, denominator)
        elif outcome in ("LOST", "GUESS_BLOCKED"):
            value = Fraction(0)
        if value is not None and request.target is not None:
            hit = outcome == "WON" and value >= request.target
        budget.check()
    except Exception as exc:
        stopped = exc
        reason = exc.reason if isinstance(exc, _Stop) else "MODEL_ERROR"
    return RuntimeRow(candidate.candidate_id, index, sample.rank, outcome, reason,
        value, hit, virtual_b, len(actions), tuple(actions), tuple(indices)), stopped


def evaluate_model(request, *, cancelled=None):
    """Direct, forced model evaluation. Scheduling belongs to RuntimePolicy."""
    if type(request) is not ModelRequest:
        raise TypeError("ModelRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable")
    budget = _Budget(request, cancelled)
    cache = _FollowupCache(request.limits.cache_entries)
    root = posterior = None
    entries = scores = sequence = ()
    rows, calls = [], []
    selected_id = token = error = None
    information, target_status = "INCOMPLETE_NO_INFORMATION", "NOT_EVALUATED"
    fid = F_ID if request.limits.kernel_kind == "indexed" else V1_F_ID
    try:
        if _MODEL_ACTIVE.get() or _F_ACTIVE.get():
            raise _Stop("ERROR", "RECURSIVE_MODEL_FORBIDDEN")
        token = _MODEL_ACTIVE.set(True)
        budget.check()
        if request.mode == "R" and request.target is None:
            raise _Stop("TARGET_REQUIRED", "POSITIVE_EXPLICIT_TARGET_REQUIRED")
        if request.prior_id != PRIOR_ID:
            raise _Stop("UNSUPPORTED", "PRIOR_UNSUPPORTED")
        limits = replace(request.limits.root, max_seconds=min(request.limits.root.max_seconds, budget.remaining()))
        query = CandidateRequest(request.observation, request.num_mines, limits, request.prior_id)
        try:
            root = analyze_candidates(query, cancelled=budget.relay)
        finally:
            d = getattr(root, "diagnostics", None)
            known = d is not None and d.work_accounting_complete
            budget.settle_group((("unit4_calls", limits.max_backend_calls, d.backend_calls if known else None),
                ("unit4_work", limits.max_total_backend_work, d.backend_work if known else None)))
        budget.check()
        _validate_root(root, query, budget)
        if root.status != "COMPLETE":
            status = "RESOURCE_LIMIT" if root.status in ("PARTIAL", "INSUFFICIENT") else root.status
            raise _Stop(status, "ROOT_"+root.reason)
        eligible, chosen, entries = _shortlist(root, request)
        if not eligible:
            raise _Stop("GUESS_BLOCKED" if not request.allow_guess and root.has_proven_safe_cell is False
                        else "NO_INFORMATION", "NO_EXACT_ELIGIBLE_CANDIDATE")
        if not chosen:
            raise _Stop("RESOURCE_LIMIT", "EMPTY_SHORTLIST")
        slots = min(request.limits.samples, root.base.total_worlds)
        if not slots or len(chosen)*slots > request.limits.rows:
            raise _Stop("RESOURCE_LIMIT", "MATRIX_LIMIT")
        if request.limits.diagnostic and root.base.total_worlds > request.limits.samples:
            raise _Stop("UNSUPPORTED", "DIAGNOSTIC_REQUIRES_EXHAUSTIVE_BANK")
        rows = [RuntimeRow(c.candidate_id, i, None) for c in chosen for i in range(slots)]
        sq = PosteriorRequest(request.observation, request.num_mines, request.counted_inputs,
            request.planning_seed, request.limits.samples,
            SamplerLimits(max_work=request.limits.sampler_work, max_seconds=min(10.0, budget.remaining())))
        try:
            posterior = sample_posterior(sq, cancelled=budget.relay)
        finally:
            budget.settle("sampler_work", sq.limits.max_work,
                          posterior.diagnostics.work if posterior is not None else None)
        budget.check()
        if posterior.seed_id != sq.seed_id or (posterior.total_worlds is not None and posterior.total_worlds != root.base.total_worlds):
            raise ValueError("POSTERIOR_ROOT_BINDING")
        if posterior.status != "COMPLETE":
            raise _Stop("RESOURCE_LIMIT" if posterior.status == "INSUFFICIENT" else posterior.status,
                        "SAMPLER_"+posterior.reason)
        if len(posterior.samples) != slots:
            raise ValueError("INCOMPLETE_POSTERIOR_BANK")
        rows = [RuntimeRow(c.candidate_id, i, s.rank) for c in chosen for i, s in enumerate(posterior.samples)]
        for ci, candidate in enumerate(chosen):
            for si, sample in enumerate(posterior.samples):
                row, stopped = _row(request, candidate, sample, si, budget, cache, calls)
                rows[ci*slots+si] = row
                if stopped is not None:
                    raise stopped
        scores = _complete_scores(chosen, posterior.samples, rows, request.target, fid)
        fallback_indices = {c.candidate_id:i for i, c in enumerate(eligible)}
        by_id = {s.candidate_id:s for s in scores}
        selected = max(chosen, key=lambda c:model_order(by_id[c.candidate_id], c.survival_probability,
                                                       fallback_indices[c.candidate_id], request.mode))
        budget.check()
        sequence, selected_id = selected.sequence, selected.candidate_id
        information = "COMPLETE_ALL_ZERO" if all(s.rollout_mean_x == 0 for s in scores) else "COMPLETE_NONZERO"
        target_status = ("NOT_REQUESTED" if request.target is None else
            "NO_HIT_EVIDENCE_MEAN_X_TIEBREAK" if all(s.rollout_hit_rate == 0 for s in scores) else "POSITIVE_MODEL_HIT")
        status, reason = "COMPLETE", "COMPLETE_COMMON_BANK_THEN_F"
    except _Stop as exc:
        status, reason = exc.status, exc.reason
        sequence, selected_id, scores = (), None, ()
    except Exception as exc:
        status, reason, error = "ERROR", "MODEL_ERROR", f"{type(exc).__name__}: {exc}"
        sequence, selected_id, scores = (), None, ()
    finally:
        cache.clear()
        if token is not None:
            _MODEL_ACTIVE.reset(token)
    return ModelResult(MODEL_ID, fid, request.identity, status, reason, sequence, selected_id,
        root, entries, posterior, tuple(rows), scores, tuple(calls), budget.usage, tuple(budget.settlements),
        information, target_status, perf_counter()-budget.started, error)
