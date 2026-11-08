"""Unconnected public policy API; the caller alone executes returned inputs.

One instance owns one active episode/settings generation and at most one
unconsumed proposal. claim() consumes the whole proposal exactly once. The
output harness additionally guards every atomic prefix using the R1 contract.
"""
from dataclasses import dataclass, fields, replace
from fractions import Fraction
from threading import Event, Lock
from time import perf_counter
from uuid import uuid4

from stage4_belief import PRIOR_ID, exact_json
from stage4_exact_pilot import _integer_payload, _payload_fields, _seconds_payload, _validate_seconds
from stage4_posterior import public_digest
from stage4_runtime_model import (MODEL_ID, F_ID, V1_F_ID, ModelLimits, ModelRequest,
    RuntimeUsage, FollowupLimits, FollowupRequest, evaluate_model, choose_followup)

POLICY_ID = "UNCONNECTED_RUNTIME_SMR_V1"


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    model: ModelLimits = ModelLimits()
    max_seconds: float = 35.0
    max_model_attempts: int = 8
    model_interval_counted: int = 16

    def __post_init__(self):
        if type(self.model) is not ModelLimits or self.model.diagnostic:
            raise ValueError("Runtime policy requires ordinary model limits")
        _validate_seconds(self.max_seconds, 35.0)
        if type(self.max_model_attempts) is not int or not 0 <= self.max_model_attempts <= 8:
            raise ValueError("max_model_attempts must be in0..8")
        if type(self.model_interval_counted) is not int or not 16 <= self.model_interval_counted <= 512:
            raise ValueError("model_interval_counted must be in16..512")

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        if "model" in values:
            values["model"] = ModelLimits.from_payload(values["model"])
        for k in ("max_model_attempts", "model_interval_counted"):
            if k in values:
                values[k] = _integer_payload(values[k])
        if "max_seconds" in values:
            values["max_seconds"] = _seconds_payload(values["max_seconds"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class RuntimeRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int
    mode: str = "S"
    allow_guess: bool = False
    target: Fraction | None = None
    planning_seed: int | str = 0
    episode_key: str = "public-episode"
    settings_id: str = "public-settings"
    instance_id: str = "public-instance"
    generation: int = 0
    prior_id: str = PRIOR_ID
    limits: RuntimeLimits = RuntimeLimits()

    def __post_init__(self):
        if type(self.limits) is not RuntimeLimits:
            raise TypeError("RuntimeLimits required")
        model = ModelRequest(self.observation, self.num_mines, self.counted_inputs, self.mode,
            self.allow_guess, self.target, self.planning_seed, self.prior_id, self.limits.model)
        object.__setattr__(self, "observation", model.observation)
        object.__setattr__(self, "target", model.target)
        for k in ("episode_key", "settings_id", "instance_id"):
            if type(getattr(self, k)) is not str or not getattr(self, k):
                raise ValueError("Nonempty public identity required:"+k)
        if type(self.generation) is not int or self.generation < 0:
            raise ValueError("Nonnegative integer generation required")

    def to_payload(self):
        value = exact_json(self)
        value["planning_seed"] = {"kind":"int" if type(self.planning_seed) is int else "str",
                                  "value":str(self.planning_seed)}
        return value

    @property
    def identity(self):
        return public_digest((POLICY_ID, self.to_payload()))

    @property
    def settings_fingerprint(self):
        return public_digest((self.settings_id, self.mode, self.allow_guess, self.target,
                              self.to_payload()["planning_seed"], self.prior_id, self.limits,
                              self.num_mines, self.instance_id, self.generation))

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        model_values = {k:v for k, v in values.items() if k in {f.name for f in fields(ModelRequest)} and k != "limits"}
        model = ModelRequest.from_payload(model_values)
        for k in model_values:
            values[k] = getattr(model, k)
        if "generation" in values:
            values["generation"] = _integer_payload(values["generation"])
        if "limits" in values:
            values["limits"] = RuntimeLimits.from_payload(values["limits"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    policy_id: str
    request_id: str
    status: str
    reason: str
    sequence: tuple
    decision_source: str | None
    model_status: str
    model_attempted: bool
    model_attempts_used: int
    model: object | None
    followup: object | None
    usage: RuntimeUsage
    proposal_id: str | None
    session_id: str
    settings_fingerprint: str
    expires_at: float
    elapsed_seconds: float
    error: str | None = None

    def to_payload(self):
        return exact_json(self)


def _sum_usage(a, b):
    return RuntimeUsage(**{f.name:(a.accounting_complete and b.accounting_complete if f.name == "accounting_complete"
        else max(a.cache_peak, b.cache_peak) if f.name == "cache_peak" else getattr(a, f.name)+getattr(b, f.name))
        for f in fields(RuntimeUsage)})


class RuntimePolicy:
    def __init__(self):
        self.session_id = uuid4().hex
        self._lock = Lock()
        self._cancel = Event()
        self._closed = False
        self._scope = self._settings = self._pending = None
        self._attempts = 0
        self._last_attempt_count = None
        self._seen = set()
        self._consumed = set()
        self._serial = 0

    def cancel(self):
        self._cancel.set()
        self._pending = None

    def close(self):
        self._closed = True
        self.cancel()

    def terminal(self):
        self.close()

    @property
    def attempts_used(self):
        return self._attempts

    def choose(self, request, *, cancelled=None):
        if type(request) is not RuntimeRequest:
            self.cancel()
            raise TypeError("RuntimeRequest required")
        if cancelled is not None and not callable(cancelled):
            self.cancel()
            raise TypeError("cancelled must be callable")
        started = perf_counter()
        deadline = started + request.limits.max_seconds
        model = followup = None
        usage = RuntimeUsage()
        attempted = False
        model_status = "SKIPPED"
        source = proposal_id = error = None
        sequence = ()

        def result(status, reason):
            return RuntimeResult(POLICY_ID, request.identity, status, reason, sequence, source,
                model_status, attempted, self._attempts, model, followup, usage, proposal_id,
                self.session_id, request.settings_fingerprint, deadline, perf_counter()-started, error)

        if not self._lock.acquire(blocking=False):
            self.cancel()  # BUSY invalidates any pending/in-flight proposal.
            return result("BUSY", "ANOTHER_DECISION_ACTIVE")
        try:
            self._pending = None
            if self._closed:
                return result("CANCELLED", "POLICY_CLOSED")
            token = Event()
            self._cancel = token

            def check():
                if token.is_set() or self._closed:
                    return "CANCELLED"
                if cancelled is not None:
                    answer = cancelled()
                    if type(answer) is not bool:
                        raise TypeError("Cancellation callback must return bool")
                    if answer:
                        return "CANCELLED"
                return "PARENT_EXPIRED" if perf_counter() >= deadline else None

            def relay():
                return check() is not None

            stopped = check()
            if stopped:
                return result("CANCELLED" if stopped == "CANCELLED" else "RESOURCE_LIMIT", stopped)
            scope = (request.episode_key, request.instance_id)
            if scope != self._scope:
                self._scope, self._attempts, self._last_attempt_count = scope, 0, None
                self._seen.clear()
                self._consumed.clear()
            self._settings = request.settings_fingerprint
            if request.identity in self._seen:
                return result("RESOURCE_LIMIT", "REQUEST_ALREADY_DECIDED_NO_NEW_QUOTA")
            if len(self._seen) >= 384:
                return result("RESOURCE_LIMIT", "EPISODE_DECISION_LIMIT")
            self._seen.add(request.identity)
            if request.mode == "R" and request.target is None:
                return result("TARGET_REQUIRED", "POSITIVE_EXPLICIT_TARGET_REQUIRED")
            if sum(v >= 0 for row in request.observation for v in row) == len(request.observation)*len(request.observation[0])-request.num_mines:
                self.terminal()
                return result("NO_INFORMATION", "PUBLIC_TERMINAL")
            eligible_time = self._last_attempt_count is None or request.counted_inputs-self._last_attempt_count >= request.limits.model_interval_counted
            model_seconds = min(request.limits.model.max_seconds, max(0.0, deadline-perf_counter()-5.0))
            should_model = (request.counted_inputs >= 1 and self._attempts < request.limits.max_model_attempts
                            and eligible_time and model_seconds > 0)
            if should_model:
                self._attempts += 1
                self._last_attempt_count = request.counted_inputs
                attempted = True
                mr = ModelRequest(request.observation, request.num_mines, request.counted_inputs,
                    request.mode, request.allow_guess, request.target, request.planning_seed,
                    request.prior_id, replace(request.limits.model, max_seconds=model_seconds))
                model = evaluate_model(mr, cancelled=relay)
                usage = _sum_usage(usage, model.usage)
                model_status = model.status
                stopped = check()
                if stopped:
                    return result("CANCELLED" if stopped == "CANCELLED" else "RESOURCE_LIMIT", stopped)
                if model.request_id != mr.identity or model.model_id != MODEL_ID or not usage.accounting_complete:
                    raise ValueError("MODEL_BINDING_OR_UNKNOWN_ACCOUNTING")
                if model.status == "COMPLETE":
                    if not model.sequence or not model.scores:
                        raise ValueError("EMPTY_COMPLETE_MODEL")
                    sequence, source = model.sequence, "MODEL"
                    status = "NO_INFORMATION" if model.information == "COMPLETE_ALL_ZERO" else "MODEL_SELECTED"
                    reason = model.information+":"+model.target_status
                elif model.status == "RESOURCE_LIMIT":
                    pass  # Ordinary model resource exhaustion may use fresh F.
                elif model.status == "GUESS_BLOCKED":
                    return result("NO_INFORMATION", "GUESS_BLOCKED")
                else:
                    return result(model.status if model.status in ("TARGET_REQUIRED", "CANCELLED", "ERROR")
                                  else "ERROR", "MODEL_BLOCKED:"+model.reason)
            if not sequence:
                stopped = check()
                if stopped:
                    return result("CANCELLED" if stopped == "CANCELLED" else "RESOURCE_LIMIT", stopped)
                fq = FollowupRequest(request.observation, request.num_mines, request.counted_inputs,
                    request.allow_guess, request.prior_id, FollowupLimits(
                        max_seconds=min(5.0, max(0.0, deadline-perf_counter())),
                        kernel_kind=request.limits.model.kernel_kind))
                followup = choose_followup(fq, cancelled=relay)
                usage = _sum_usage(usage, followup.usage)
                stopped = check()
                if stopped:
                    return result("CANCELLED" if stopped == "CANCELLED" else "RESOURCE_LIMIT", stopped)
                if followup.request_id != fq.identity or not usage.accounting_complete:
                    raise ValueError("F_BINDING_OR_UNKNOWN_ACCOUNTING")
                if followup.status == "READY":
                    sequence, source = followup.sequence, "F"
                    status, reason = "HEURISTIC_FALLBACK", "MODEL_"+model_status+":"+followup.reason
                elif followup.status in ("GUESS_BLOCKED", "DEFER", "NO_INFORMATION"):
                    return result("NO_INFORMATION", followup.reason)
                else:
                    return result("RESOURCE_LIMIT" if followup.status == "RESOURCE_LIMIT" else
                                  "CANCELLED" if followup.status == "CANCELLED" else "ERROR", "F_BLOCKED:"+followup.reason)
            stopped = check()
            if stopped:
                sequence, source = (), None
                return result("CANCELLED" if stopped == "CANCELLED" else "RESOURCE_LIMIT", stopped)
            self._serial += 1
            proposal_id = public_digest((POLICY_ID, self.session_id, self._serial, request.identity,
                                         request.settings_fingerprint, sequence))
            finished = result(status, reason)
            self._pending = finished
            return finished
        except Exception as exc:
            self._pending = None
            sequence, source, proposal_id = (), None, None
            error = f"{type(exc).__name__}: {exc}"
            return result("ERROR", "RUNTIME_POLICY_ERROR")
        finally:
            self._lock.release()

    def claim(self, proposal, current_request, *, cancelled=None):
        """Consume once before delivery. Every input still needs an R1 guard."""
        if not self._lock.acquire(blocking=False):
            self.cancel()
            return ()
        try:
            current = self._pending
            self._pending = None
            if (self._closed or self._cancel.is_set() or type(proposal) is not RuntimeResult or
                    type(current_request) is not RuntimeRequest or current is not proposal or
                    proposal.session_id != self.session_id or not proposal.proposal_id or
                    proposal.proposal_id in self._consumed or proposal.request_id != current_request.identity or
                    proposal.settings_fingerprint != current_request.settings_fingerprint or
                    perf_counter() >= proposal.expires_at):
                return ()
            if cancelled is not None:
                value = cancelled()
                if type(value) is not bool or value:
                    return ()
            self._consumed.add(proposal.proposal_id)
            return proposal.sequence
        except Exception:
            self._pending = None
            return ()
        finally:
            self._lock.release()
