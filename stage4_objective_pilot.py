"""Bounded objective pilot G. Each candidate is evaluated with Q as its follow-up.

Returned model values describe the declared shortlist and the common posterior
bank followed by Q. Repeated G planning belongs to the external small evaluator.
"""

from contextvars import ContextVar
from dataclasses import dataclass, fields, replace
from fractions import Fraction
from time import perf_counter, process_time_ns

from stage4_belief import PRIOR_ID, exact_json
from stage4_candidates import CandidateLimits, CandidateRequest, analyze_candidates
from stage4_exact_pilot import (
    Q_ID, ExactLimits, ExactPilot, ExactRequest, _Q_ACTIVE, _grid_payload,
    _integer_payload, _payload_fields, _seconds_payload, _validate_integer_limits,
    _validate_seconds,
)
from stage4_policy import ModelScore, _shortlist, _validate_root, model_order
from stage4_posterior import PosteriorRequest, SamplerLimits, public_digest, sample_posterior
from stage4_rollout import VirtualBoard


G_ID = "PUBLIC_OBJECTIVE_PILOT_G_V1"
MODEL_MEANING = "DECLARED_SHORTLIST_COMMON_PUBLIC_BANK_THEN_Q"
_G_ACTIVE = ContextVar("stage4_objective_pilot_active", default=False)


@dataclass(frozen=True, slots=True)
class ObjectiveLimits:
    max_cells: int = 480
    samples: int = 16
    shortlist: int = 6
    exact_work: int = 20_000_000
    local_work: int = 10_000_000
    sampler_work: int = 2_000_000
    backend_calls: int = 2_000
    q_calls: int = 5_000
    virtual_inputs: int = 50_000
    rows: int = 96
    inputs_per_rollout: int = 2_000
    cache_entries: int = 256
    max_seconds: float = 30.0
    root: CandidateLimits = CandidateLimits()

    def __post_init__(self):
        _validate_integer_limits(self, (
            ("max_cells", 480), ("samples", 16), ("shortlist", 6),
            ("exact_work", 60_000_000), ("local_work", 30_000_000),
            ("sampler_work", 2_000_000), ("backend_calls", 2_000), ("q_calls", 5_000),
            ("virtual_inputs", 50_000), ("rows", 96), ("inputs_per_rollout", 2_000),
            ("cache_entries", 256)))
        _validate_seconds(self.max_seconds, 30)
        if type(self.root) is not CandidateLimits:
            raise TypeError("CandidateLimits required")

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        for name in values:
            if name == "root":
                root = _payload_fields(values[name], CandidateLimits)
                root = {key: (_seconds_payload(value) if key == "max_seconds"
                              else _integer_payload(value)) for key, value in root.items()}
                values[name] = CandidateLimits(**root)
            elif name == "max_seconds":
                values[name] = _seconds_payload(values[name])
            else:
                values[name] = _integer_payload(values[name])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ObjectiveRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int
    mode: str
    allow_guess: bool
    target: Fraction | None = None
    planning_seed: int | str = 0
    prior_id: str = PRIOR_ID
    limits: ObjectiveLimits = ObjectiveLimits()

    def __post_init__(self):
        public = ExactRequest(self.observation, self.num_mines, self.counted_inputs,
                              self.allow_guess, self.prior_id)
        object.__setattr__(self, "observation", public.observation)
        if type(self.mode) is not str or self.mode not in ("S", "M", "R"):
            raise ValueError("mode must be S, M or R")
        if self.target is not None and (type(self.target) is not Fraction or self.target <= 0):
            raise ValueError("target must be a positive Fraction or None")
        if type(self.planning_seed) not in (int, str):
            raise TypeError("planning_seed must be a public integer or string")
        if type(self.limits) is not ObjectiveLimits:
            raise TypeError("ObjectiveLimits required")

    def to_payload(self):
        payload = exact_json(self)
        payload["planning_seed"] = {
            "kind": "integer" if type(self.planning_seed) is int else "string",
            "value": str(self.planning_seed),
        }
        return payload

    @property
    def identity(self):
        return public_digest((G_ID, self.to_payload()))

    @classmethod
    def from_payload(cls, payload):
        values = _payload_fields(payload, cls)
        if "observation" in values:
            values["observation"] = _grid_payload(values["observation"])
        for name in ("num_mines", "counted_inputs"):
            if name in values:
                values[name] = _integer_payload(values[name])
        if "limits" in values:
            values["limits"] = ObjectiveLimits.from_payload(values["limits"])
        if values.get("target") is not None:
            target = values["target"]
            if type(target) is not dict or set(target) != {"numerator", "denominator"}:
                raise ValueError("Expected an exact target payload")
            values["target"] = Fraction(_integer_payload(target["numerator"]),
                                        _integer_payload(target["denominator"]))
        if "planning_seed" in values:
            seed = values["planning_seed"]
            if type(seed) is not dict or set(seed) != {"kind", "value"}:
                raise ValueError("Expected a typed public seed")
            if seed["kind"] == "integer":
                values["planning_seed"] = _integer_payload(seed["value"])
            elif seed["kind"] == "string" and type(seed["value"]) is str:
                values["planning_seed"] = seed["value"]
            else:
                raise ValueError("Invalid public seed kind")
        return cls(**values)


@dataclass(frozen=True, slots=True)
class QCall:
    request: ExactRequest
    result: object


@dataclass(frozen=True, slots=True)
class ModelRow:
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
    q_call_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ObjectiveUsage:
    exact_work: int
    backend_work: int
    sampler_work: int
    local_work: int
    backend_calls: int
    q_calls: int
    cache_hits: int
    started_rows: int
    virtual_inputs: int
    work_accounting_complete: bool


@dataclass(frozen=True, slots=True)
class ObjectiveResult:
    pilot_id: str
    followup_id: str
    request_id: str
    status: str
    reason: str
    sequence: tuple
    basis: str | None
    terminal_outcome: str | None
    selected_candidate_id: str | None
    model_meaning: str
    root: object | None
    shortlist: tuple
    posterior: object | None
    expected_rows: int
    records: tuple[ModelRow, ...]
    q_calls: tuple[QCall, ...]
    scores: tuple[ModelScore, ...]
    usage: ObjectiveUsage
    elapsed_seconds: float
    cpu_nanoseconds: int
    error: str | None

    def to_dict(self):
        return exact_json(self)


class _Stop(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class _Budget:
    def __init__(self, request, cancelled):
        self.request, self.cancelled = request, cancelled
        self.started = perf_counter()
        self.cpu_started = process_time_ns()
        self.pending = None
        self.work_accounting_complete = True
        self.backend_work = self.sampler_work = self.local_work = 0
        self.backend_calls = self.cache_hits = self.started_rows = self.virtual_inputs = 0

    @property
    def exact_work(self):
        return self.backend_work + self.sampler_work

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

    def remaining(self):
        self.check()
        return max(0.0, self.request.limits.max_seconds - (perf_counter() - self.started))

    def require(self, used, cap, reason):
        self.check()
        if used >= cap:
            raise _Stop("INSUFFICIENT", reason)

    def usage(self, calls):
        return ObjectiveUsage(self.exact_work, self.backend_work, self.sampler_work,
                              self.local_work, self.backend_calls, calls, self.cache_hits,
                              self.started_rows, self.virtual_inputs, self.work_accounting_complete)


def _run_row(request, candidate, sample, sample_index, budget, pilot, calls):
    actions, call_indices = [], []
    virtual_b, value, hit = None, None, None
    outcome, reason = "NOT_STARTED", "NOT_REACHED"
    stopped = None
    try:
        budget.require(budget.started_rows, request.limits.rows, "ROW_LIMIT")
        budget.started_rows += 1
        outcome, reason = "UNRESOLVED", "NOT_FINISHED"
        board = VirtualBoard(request.observation, request.num_mines, sample.mines)
        virtual_b = board.static_bbbv()
        sequence = candidate.sequence
        visited = set()
        while board.outcome is None:
            before = board.observation
            if before in visited:
                raise ValueError("Repeated public state in Q rollout")
            visited.add(before)
            for action in sequence:
                budget.require(budget.virtual_inputs, request.limits.virtual_inputs, "VIRTUAL_INPUT_LIMIT")
                budget.require(len(actions), request.limits.inputs_per_rollout, "ROW_INPUT_LIMIT")
                transition = board.step(action)
                if not transition.counted:
                    raise ValueError("An active model input was not counted")
                actions.append(action)
                budget.virtual_inputs += 1
                if board.outcome is not None:
                    break
            if board.outcome is not None:
                break
            if sum(v >= 0 for row in board.observation for v in row) <= sum(
                    v >= 0 for row in before for v in row):
                raise ValueError("Q macro did not reveal a new cell")
            budget.require(len(calls), request.limits.q_calls, "Q_CALL_LIMIT")
            budget.require(budget.backend_calls, request.limits.backend_calls, "BACKEND_CALL_LIMIT")
            budget.require(budget.exact_work, request.limits.exact_work, "EXACT_WORK_LIMIT")
            budget.require(budget.local_work, request.limits.local_work, "LOCAL_WORK_LIMIT")
            query = ExactRequest(
                board.observation, request.num_mines, request.counted_inputs + len(actions),
                request.allow_guess, request.prior_id,
                ExactLimits(request.limits.max_cells,
                            min(20_000, request.limits.local_work - budget.local_work),
                            min(200_000, request.limits.exact_work - budget.exact_work),
                            min(2.0, budget.remaining())))
            decision = pilot.choose(query, cancelled=budget.relay)
            call_indices.append(len(calls))
            calls.append(QCall(query, decision))
            budget.backend_work += decision.exact_work
            budget.local_work += decision.local_work
            budget.backend_calls += decision.backend_calls
            budget.cache_hits += decision.cache_hit
            budget.work_accounting_complete &= decision.work_accounting_complete
            if not budget.work_accounting_complete:
                raise ValueError("Incomplete Q work accounting")
            budget.check()
            if decision.terminal_outcome == "GUESS_BLOCKED" and decision.status == "DEFER":
                outcome, reason = "GUESS_BLOCKED", "EXACT_NO_SAFE_CELL"
                break
            if decision.status != "READY":
                status = "ERROR" if decision.status in ("ERROR", "INCONSISTENT_INPUT") else "INSUFFICIENT"
                if decision.status == "CANCELLED":
                    status = "CANCELLED"
                raise _Stop(status, "Q_" + decision.reason)
            if not decision.sequence:
                raise ValueError("READY Q requires a macro")
            sequence = decision.sequence
        if board.outcome is not None:
            outcome, reason = board.outcome, "TERMINAL"
        if outcome == "WON":
            denominator = request.counted_inputs + len(actions)
            if denominator <= 0:
                raise ValueError("WON requires positive counted inputs")
            value = Fraction(virtual_b, denominator)
        elif outcome in ("LOST", "GUESS_BLOCKED"):
            value = Fraction(0)
        if value is not None and request.target is not None:
            hit = outcome == "WON" and value >= request.target
        budget.check()
    except _Stop as exc:
        stopped = exc
        reason = exc.reason
    except Exception as exc:
        stopped = exc
        reason = "MODEL_ERROR"
    row = ModelRow(candidate.candidate_id, sample_index, sample.rank, outcome, reason,
                   value, hit, virtual_b, len(actions), tuple(actions), tuple(call_indices))
    return row, stopped


def _complete_scores(chosen, samples, rows, target):
    expected = [(candidate.candidate_id, index, sample.rank)
                for candidate in chosen for index, sample in enumerate(samples)]
    actual = [(row.candidate_id, row.sample_index, row.rank) for row in rows]
    if actual != expected or not samples:
        raise ValueError("Model matrix binding mismatch")
    for row in rows:
        if row.outcome not in ("WON", "LOST", "GUESS_BLOCKED") or type(row.value_x) is not Fraction:
            raise ValueError("Complete model requires every terminal reward")
        if row.outcome != "WON" and row.value_x != 0:
            raise ValueError("Failure reward must be zero")
        if row.outcome == "WON" and (row.virtual_b is None or row.value_x <= 0):
            raise ValueError("Invalid winning reward")
        expected_hit = row.outcome == "WON" and row.value_x >= target if target is not None else None
        if row.hit is not expected_hit:
            raise ValueError("Target reward mismatch")
    scores = []
    for index, candidate in enumerate(chosen):
        group = rows[index * len(samples):(index + 1) * len(samples)]
        mean = sum((row.value_x for row in group), Fraction(0)) / len(group)
        win = Fraction(sum(row.outcome == "WON" for row in group), len(group))
        hit = Fraction(sum(row.hit is True for row in group), len(group)) if target is not None else None
        scores.append(ModelScore(candidate.candidate_id, mean, win, hit, len(group), len(group), Q_ID))
    return tuple(scores)


def choose_objective(request, *, cancelled=None):
    """Return a complete macro only after a complete common-bank Q comparison."""
    if type(request) is not ObjectiveRequest:
        raise TypeError("ObjectiveRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable or None")
    budget = _Budget(request, cancelled)
    identity = request.identity
    root = posterior = None
    entries, rows, calls, scores = (), [], [], ()
    sequence, basis, terminal, selected_id = (), None, None, None
    expected_rows = 0
    status, reason, error = "INSUFFICIENT", "NOT_STARTED", None
    token = None
    pilot = ExactPilot(request.limits.cache_entries)
    try:
        if _G_ACTIVE.get() or _Q_ACTIVE.get():
            raise _Stop("ERROR", "RECURSIVE_G_FORBIDDEN")
        token = _G_ACTIVE.set(True)
        budget.check()
        if request.mode == "R" and request.target is None:
            raise _Stop("TARGET_REQUIRED", "POSITIVE_EXPLICIT_TARGET_REQUIRED")
        if request.prior_id != PRIOR_ID:
            raise _Stop("UNSUPPORTED", "PRIOR_UNSUPPORTED")
        if len(request.observation) * len(request.observation[0]) > request.limits.max_cells:
            raise _Stop("UNSUPPORTED", "CELL_LIMIT")
        budget.require(0, request.limits.exact_work, "EXACT_WORK_LIMIT")
        budget.require(0, request.limits.local_work, "LOCAL_WORK_LIMIT")
        budget.require(0, request.limits.backend_calls, "BACKEND_CALL_LIMIT")
        root_limits = replace(
            request.limits.root,
            max_cells=min(request.limits.max_cells, request.limits.root.max_cells),
            max_backend_calls=min(request.limits.backend_calls, request.limits.root.max_backend_calls),
            max_total_backend_work=min(request.limits.exact_work,
                                       request.limits.root.max_total_backend_work),
            max_seconds=min(request.limits.root.max_seconds, budget.remaining()))
        query = CandidateRequest(request.observation, request.num_mines, root_limits, request.prior_id)
        root = analyze_candidates(query, cancelled=budget.relay)
        budget.backend_work += root.diagnostics.backend_work
        budget.backend_calls += root.diagnostics.backend_calls
        budget.check()
        _validate_root(root, query, budget)
        budget.work_accounting_complete = root.diagnostics.work_accounting_complete
        if not root.diagnostics.work_accounting_complete:
            raise ValueError("Incomplete root work accounting")
        if root.status != "COMPLETE":
            status = "INSUFFICIENT" if root.status in ("PARTIAL", "INSUFFICIENT") else root.status
            raise _Stop(status, "ROOT_" + root.reason)
        viable = any(row.mine_worlds < root.base.total_worlds for row in root.base.marginals)
        if not viable:
            raise _Stop("DEFER", "NO_VIABLE_OPEN")
        eligible, chosen, entries = _shortlist(root, request)
        if not eligible:
            if not request.allow_guess and root.has_proven_safe_cell is False:
                budget.check()
                terminal = "GUESS_BLOCKED"
                basis = "UNIT5_EXACT_BASE"
                raise _Stop("DEFER", "GUESS_BLOCKED")
            raise _Stop("DEFER", "NO_ELIGIBLE_CANDIDATE")
        if not chosen:
            raise _Stop("INSUFFICIENT", "EMPTY_SHORTLIST")
        expected_slots = min(request.limits.samples, root.base.total_worlds)
        expected_rows = len(chosen) * expected_slots
        rows = [ModelRow(candidate.candidate_id, index, None)
                for candidate in chosen for index in range(expected_slots)]
        budget.require(budget.exact_work, request.limits.exact_work, "EXACT_WORK_LIMIT")
        sampler_query = PosteriorRequest(
            request.observation, request.num_mines, request.counted_inputs,
            request.planning_seed, request.limits.samples,
            SamplerLimits(request.limits.max_cells,
                          min(request.limits.sampler_work, request.limits.exact_work - budget.exact_work),
                          min(10.0, budget.remaining())))
        posterior = sample_posterior(sampler_query, cancelled=budget.relay)
        budget.sampler_work += posterior.diagnostics.work
        budget.check()
        if posterior.seed_id != sampler_query.seed_id:
            raise ValueError("Posterior public seed mismatch")
        if posterior.total_worlds is not None and posterior.total_worlds != root.base.total_worlds:
            raise ValueError("Posterior/root denominator mismatch")
        if posterior.status != "COMPLETE":
            status = "INSUFFICIENT" if posterior.status == "INSUFFICIENT" else "ERROR"
            raise _Stop(status, "SAMPLER_" + posterior.reason)
        if not expected_slots or len(posterior.samples) != expected_slots:
            raise _Stop("INSUFFICIENT", "EMPTY_OR_INCOMPLETE_BANK")
        if any(type(sample.rank) is not int or not 0 <= sample.rank < root.base.total_worlds
               for sample in posterior.samples):
            raise ValueError("Invalid posterior rank")
        rows = [ModelRow(candidate.candidate_id, index, sample.rank)
                for candidate in chosen for index, sample in enumerate(posterior.samples)]
        for candidate_index, candidate in enumerate(chosen):
            for sample_index, sample in enumerate(posterior.samples):
                row, stopped = _run_row(request, candidate, sample, sample_index, budget, pilot, calls)
                rows[candidate_index * expected_slots + sample_index] = row
                if stopped is not None:
                    raise stopped
        scores = _complete_scores(chosen, posterior.samples, rows, request.target)
        fallback_indices = {row.candidate_id: index for index, row in enumerate(eligible)}
        by_id = {score.candidate_id: score for score in scores}
        selected = max(chosen, key=lambda row: model_order(
            by_id[row.candidate_id], row.survival_probability, fallback_indices[row.candidate_id], request.mode))
        budget.check()
        sequence, selected_id = selected.sequence, selected.candidate_id
        basis = MODEL_MEANING
        status, reason = "READY", "COMPLETE_COMMON_BANK"
    except _Stop as exc:
        status, reason = exc.status, exc.reason
        sequence, scores, selected_id = (), (), None
        if terminal != "GUESS_BLOCKED":
            basis, terminal = None, None
    except Exception as exc:
        status, reason, error = "ERROR", "OBJECTIVE_PILOT_ERROR", f"{type(exc).__name__}: {exc}"
        sequence, scores, selected_id, basis, terminal = (), (), None, None, None
    finally:
        pilot.clear()
        if token is not None:
            _G_ACTIVE.reset(token)
    return ObjectiveResult(G_ID, Q_ID, identity, status, reason, sequence, basis, terminal,
                           selected_id, MODEL_MEANING, root, entries, posterior, expected_rows,
                           tuple(rows), tuple(calls), scores, budget.usage(len(calls)),
                           perf_counter() - budget.started, process_time_ns() - budget.cpu_started, error)

