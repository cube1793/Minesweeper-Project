"""Bounded public evidence for progress and flag-preparation sequences.

The canonical order describes the declared candidate family. Each sequence is
evidence for a future consumer. This module neither selects nor executes it.
Zero events include survival of every direct reveal target. Their probabilities
overlap and cannot be added to count openings or saved inputs.

The perf_counter deadline is cooperative. DTO construction and serialization
are outside it. Hashing, exact arithmetic and bounded output materialization
are bracketed by checkpoints, including the final publication check. An
interrupted call still materializes its already computed evidence. The public
Unit 4 backend retains its own monotonic-clock granularity.
"""

from dataclasses import dataclass, fields
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from math import isfinite
from time import perf_counter

from stage4_belief import (
    BaseResult, BeliefLimits, BeliefRequest, BeliefResult, COUNTER_VERSION,
    EventQuery, FLAGGED, HIDDEN, NORMALIZATION_POLICY, PRIOR_ID, count_public,
    exact_json,
)


FAMILY_ID = "progress_preparations_evidence_v1"
SCHEMA_VERSION = "candidate_evidence_v1"
EVENT_NORMALIZATION = "closed_safe_cells_row_major_v1"
Coordinate = tuple[int, int]
SafeSet = tuple[Coordinate, ...]


def _digest(value):
    encoded = json.dumps(exact_json(value), sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateLimits:
    max_cells: int = 480
    max_generated: int = 4096
    max_candidates: int = 2048
    max_distinct_events: int = 512
    max_backend_calls: int = 33
    max_total_backend_work: int = 500_000
    max_seconds: float = 10.0

    def __post_init__(self):
        for name, cap in (("max_cells", 480), ("max_generated", 4096),
                          ("max_candidates", 2048), ("max_distinct_events", 512),
                          ("max_backend_calls", 33), ("max_total_backend_work", 500_000)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= cap:
                raise ValueError(f"{name} must be an integer in 0..{cap}")
        if (type(self.max_seconds) not in (int, float)
                or not isfinite(self.max_seconds) or not 0 <= self.max_seconds <= 10):
            raise ValueError("max_seconds must be finite and in 0..10")
        object.__setattr__(self, "max_seconds", float(self.max_seconds))


@dataclass(frozen=True, slots=True)
class CandidateRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    limits: CandidateLimits = CandidateLimits()
    prior_id: str = PRIOR_ID

    def __post_init__(self):
        if type(self.limits) is not CandidateLimits:
            raise TypeError("CandidateLimits required")
        public = BeliefRequest(self.observation, self.num_mines, prior_id=self.prior_id)
        object.__setattr__(self, "observation", public.observation)
        object.__setattr__(self, "num_mines", public.num_mines)

    @property
    def observation_id(self):
        return _digest((EVENT_NORMALIZATION, self.observation, self.num_mines, self.prior_id))

    @property
    def identity(self):
        return _digest((SCHEMA_VERSION, FAMILY_ID, COUNTER_VERSION,
                        NORMALIZATION_POLICY, EVENT_NORMALIZATION, self))

    def to_payload(self):
        return {"observation": self.observation, "num_mines": self.num_mines,
                "limits": {f.name: getattr(self.limits, f.name) for f in fields(self.limits)},
                "prior_id": self.prior_id}

    @classmethod
    def from_payload(cls, payload):
        if type(payload) is not dict or set(payload) - {f.name for f in fields(cls)}:
            raise ValueError("Unknown public request fields or invalid payload")
        values = dict(payload)
        if "limits" in values:
            if type(values["limits"]) is not dict:
                raise TypeError("Limits payload must be a dictionary")
            values["limits"] = CandidateLimits(**values["limits"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    action: str
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Eligibility:
    guess_off: bool | None
    S_guess_on: bool | None
    M_guess_on: bool | None
    R_guess_on: bool | None


@dataclass(frozen=True, slots=True)
class JointEvidence:
    safe_cells: SafeSet
    status: str = "NOT_EVALUATED"
    reason: str = "NOT_REACHED"
    worlds: int | None = None


@dataclass(frozen=True, slots=True)
class ZeroEvidence:
    cell: Coordinate
    event: JointEvidence
    zero_and_survive_probability: Fraction | None
    zero_given_survival_probability: Fraction | None


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    candidate_id: str
    kind: str
    pivot: Coordinate
    final_flags: SafeSet
    targets: SafeSet
    sequence: tuple[EvidenceInput, ...]
    immediate_input_cost: int
    target_count: int
    survival: JointEvidence
    survival_probability: Fraction | None
    zero_targets: tuple[ZeroEvidence, ...]
    survival_weighted_target_floor_per_input: Fraction | None
    eligibility: Eligibility
    status: str


@dataclass(frozen=True, slots=True)
class BackendCall:
    request_id: str
    stage: str
    event_count: int
    work_limit: int
    seconds_limit: float
    status: str
    reason: str
    work: int | None


@dataclass(frozen=True, slots=True)
class CandidateDiagnostics:
    generated: int
    excluded_empty_targets: int
    excluded_edited_single_target: int
    backend_calls: int
    backend_work: int
    work_accounting_complete: bool
    distinct_queried_events: int
    queued_events: int
    event_references: int
    duplicate_event_references: int
    base_proofs: int
    exact_candidates: int
    exact_survivals: int
    exact_zero_targets: int
    elapsed_seconds: float
    checkpoints: int
    last_checkpoint: str
    backend_trace: tuple[BackendCall, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class CandidateResult:
    request_id: str
    observation_id: str
    family_id: str
    schema_version: str
    counter_version: str
    status: str
    reason: str
    stop_stage: str | None
    base: BaseResult
    has_proven_safe_cell: bool | None
    catalogue_complete: bool
    event_collection_complete: bool
    evidence_complete: bool
    candidates: tuple[CandidateEvidence, ...]
    events: tuple[JointEvidence, ...]
    diagnostics: CandidateDiagnostics

    def to_dict(self):
        return exact_json(self)


class _Stop(Exception):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason


class _Budget:
    def __init__(self, limits, cancelled):
        self.limits, self.cancelled = limits, cancelled
        self.started = perf_counter()
        self.elapsed = 0.0
        self.checkpoints = self.generated = self.calls = self.work = 0
        self.stage = "request"
        self.error = None
        self.work_complete = True
        self.pending_stop = None
        self.trace = []

    def check(self, stage=None):
        if stage is not None:
            self.stage = stage
        self.checkpoints += 1
        self.elapsed = perf_counter() - self.started
        if self.cancelled is not None:
            try:
                value = self.cancelled()
                if type(value) is not bool:
                    raise TypeError("Cancellation callback must return bool")
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                raise _Stop("ERROR", "CANCEL_CALLBACK_ERROR") from exc
            self.elapsed = perf_counter() - self.started
            if value:
                raise _Stop("CANCELLED", "CANCELLED")
        if self.elapsed >= self.limits.max_seconds:
            raise _Stop("INSUFFICIENT", "TIME_LIMIT")

    def backend_cancelled(self):
        try:
            self.check()
        except _Stop as exc:
            self.pending_stop = exc
            return True
        return False

    def generate(self):
        self.check("catalogue")
        if self.generated >= self.limits.max_generated:
            raise _Stop("INSUFFICIENT", "GENERATED_LIMIT")
        self.generated += 1

    def backend(self, request, events, stage):
        self.check(stage)
        if self.calls >= self.limits.max_backend_calls:
            raise _Stop("INSUFFICIENT", "BACKEND_CALL_LIMIT")
        remaining = self.limits.max_total_backend_work - self.work
        if remaining <= 0:
            raise _Stop("INSUFFICIENT", "BACKEND_WORK_LIMIT")
        limits = BeliefLimits(max_cells=self.limits.max_cells, max_events=16,
                              max_work=min(200_000, remaining),
                              max_seconds=min(2.0, self.limits.max_seconds - self.elapsed))
        query = BeliefRequest(request.observation, request.num_mines, events,
                              limits, request.prior_id)
        self.check(stage)
        self.calls += 1
        work, status, reason = None, "ERROR", "BACKEND_EXCEPTION"
        try:
            reply = count_public(query, cancelled=self.backend_cancelled)
            if type(reply) is not BeliefResult:
                raise ValueError("BeliefResult required from backend")
            work = reply.diagnostics.work
            if type(work) is not int or not 0 <= work <= limits.max_work:
                work = None
                raise ValueError("Invalid backend work accounting")
            self.work += work
            status, reason = reply.status, reply.reason
            if reply.request_id != query.identity:
                raise ValueError("Backend public request binding mismatch")
            return reply
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            raise _Stop("ERROR", "BACKEND_ERROR") from exc
        finally:
            if work is None:
                self.work_complete = False
            self.trace.append(BackendCall(query.identity, stage, len(events), limits.max_work,
                                          limits.max_seconds, status, reason, work))

    def after_backend(self, stage):
        if self.pending_stop is not None:
            raise self.pending_stop
        self.check(stage)


def _neighbors(cell, grid):
    x, y = cell
    return tuple((nx, ny)
                 for ny in range(max(0, y - 1), min(len(grid), y + 2))
                 for nx in range(max(0, x - 1), min(len(grid[0]), x + 2))
                 if (nx, ny) != cell)


def _safe_set(cells, grid):
    return tuple(sorted({(x, y) for x, y in cells if grid[y][x] < 0},
                        key=lambda cell: (cell[1], cell[0])))


@dataclass(frozen=True, slots=True)
class _Spec:
    candidate_id: str
    kind: str
    pivot: Coordinate
    flags: SafeSet
    targets: SafeSet
    sequence: tuple[EvidenceInput, ...]
    zero_sets: tuple[SafeSet, ...]


def _validate_base(base, request):
    if type(base) is not BaseResult or base.status != "EXACT":
        raise ValueError("Exact backend base required")
    denominator = base.total_worlds
    if type(denominator) is not int or denominator <= 0 or type(base.marginals) is not tuple:
        raise ValueError("Invalid exact base denominator or marginals")
    expected = {(x, y) for y, row in enumerate(request.observation)
                for x, value in enumerate(row) if value < 0}
    counts = {}
    for row in base.marginals:
        if row.coordinate in counts or row.coordinate not in expected:
            raise ValueError("Invalid marginal coordinates")
        if (type(row.mine_worlds) is not int or not 0 <= row.mine_worlds <= denominator
                or type(row.probability) is not Fraction
                or row.probability != Fraction(row.mine_worlds, denominator)):
            raise ValueError("Invalid marginal count or probability")
        counts[row.coordinate] = row.mine_worlds
    if set(counts) != expected or sum(counts.values()) != denominator * request.num_mines:
        raise ValueError("Incomplete or inconsistent base marginals")
    return counts


def _base_proof(key, denominator, counts):
    if any(counts[cell] == denominator for cell in key):
        return JointEvidence(key, "EXACT", "BASE_CERTAIN_MINE", 0)
    if all(counts[cell] == 0 for cell in key):
        return JointEvidence(key, "EXACT", "BASE_ALL_SAFE", denominator)
    if len(key) == 1:
        return JointEvidence(key, "EXACT", "BASE_SINGLE_MARGINAL", denominator - counts[key[0]])
    return None


def _eligibility(spec, worlds, denominator, counts, has_safe):
    if worlds is None:
        return Eligibility(None, None, None, None)
    safe = worlds == denominator
    viable = worlds > 0
    s_allowed = safe if has_safe else (spec.kind == "OPEN" and viable
                                      and counts[spec.pivot] == min(counts.values()))
    return Eligibility(safe, s_allowed, viable, viable)


def analyze_candidates(request, *, cancelled=None):
    """Return canonical sequence evidence, exact counts and explicit coverage.

    Zero calls/work/time block the base. Zero generation/candidate limits block
    the first applicable catalogue item. Zero event capacity permits evidence
    provable from the base. Size/prior rejection returns UNSUPPORTED. Resource
    or cancellation stops after an exact base return PARTIAL. Callback/backend
    errors return ERROR, retaining previously committed exact evidence.
    """
    if type(request) is not CandidateRequest:
        raise TypeError("CandidateRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable or None")
    budget = _Budget(request.limits, cancelled)
    identity, observation_id = request.identity, request.observation_id
    grid = request.observation
    base = BaseResult("NOT_EVALUATED", "NOT_STARTED")
    counts, specs, events, queued, queried = {}, [], {}, [], set()
    catalogue_complete = collection_complete = False
    empty_excluded = single_excluded = references = duplicates = 0
    has_safe = None
    status, reason, stop_stage = "COMPLETE", "PUBLIC_CANDIDATE_EVIDENCE", None

    def add_spec(kind, pivot, flags, targets, sequence):
        budget.check("catalogue")
        if len(specs) >= request.limits.max_candidates:
            raise _Stop("INSUFFICIENT", "CANDIDATE_LIMIT")
        zero_sets = tuple(_safe_set(targets + (cell,) + _neighbors(cell, grid), grid)
                          for cell in targets)
        spec = _Spec(_digest((FAMILY_ID, observation_id, sequence)), kind, pivot,
                     flags, targets, sequence, zero_sets)
        budget.check("catalogue")
        specs.append(spec)

    def lookup(key):
        return events.get(key) or _base_proof(key, base.total_worlds, counts) or JointEvidence(key)

    def materialize(spec):
        survival = lookup(spec.targets)
        worlds, denominator = survival.worlds, base.total_worlds
        zero_rows = []
        for cell, key in zip(spec.targets, spec.zero_sets):
            event = lookup(key)
            if worlds == 0:
                event = JointEvidence(key, "EXACT", "ZERO_SURVIVAL", 0)
            if event.worlds is not None and worlds is not None and event.worlds > worlds:
                raise ValueError("Zero event exceeds survival")
            joint = None if event.worlds is None else Fraction(event.worlds, denominator)
            conditional = None
            if worlds is not None and worlds > 0 and event.worlds is not None:
                conditional = Fraction(event.worlds, worlds)
            zero_rows.append(ZeroEvidence(cell, event, joint, conditional))
        complete = worlds is not None and all(row.event.worlds is not None for row in zero_rows)
        cost = len(spec.sequence)
        probability = None if worlds is None else Fraction(worlds, denominator)
        floor = None if worlds is None else Fraction(len(spec.targets) * worlds, denominator * cost)
        return CandidateEvidence(spec.candidate_id, spec.kind, spec.pivot, spec.flags,
                                 spec.targets, spec.sequence, cost, len(spec.targets), survival,
                                 probability, tuple(zero_rows), floor,
                                 _eligibility(spec, worlds, denominator, counts, has_safe),
                                 "EXACT" if complete else "PARTIAL")

    candidates = ()
    try:
        budget.check("request")
        if len(grid) * len(grid[0]) > request.limits.max_cells:
            raise _Stop("UNSUPPORTED", "CELL_LIMIT")
        if request.prior_id != PRIOR_ID:
            raise _Stop("UNSUPPORTED", "PRIOR_UNSUPPORTED")
        reply = budget.backend(request, (), "base")
        if reply.base.status != "EXACT":
            base = reply.base
            if budget.pending_stop is not None:
                raise budget.pending_stop
            if reply.status not in ("INSUFFICIENT", "CANCELLED", "ERROR", "INCONSISTENT_INPUT", "UNSUPPORTED"):
                raise ValueError("Unexpected nonexact base status")
            raise _Stop(reply.status, reply.reason)
        counts = _validate_base(reply.base, request)
        if reply.status != "COMPLETE" or reply.events:
            raise ValueError("Unexpected base response")
        base = reply.base
        has_safe = any(value == 0 for value in counts.values())
        budget.after_backend("base.after")

        for y, row in enumerate(grid):
            for x, value in enumerate(row):
                if value >= 0:
                    continue
                budget.generate()
                prefix = (EvidenceInput("FLAG", x, y),) if value == FLAGGED else ()
                add_spec("OPEN", (x, y), (), ((x, y),), prefix + (EvidenceInput("OPEN", x, y),))
        for y, row in enumerate(grid):
            budget.check("catalogue")
            for x, clue in enumerate(row):
                if clue <= 0:
                    continue
                adjacent = _safe_set(_neighbors((x, y), grid), grid)
                for flags in combinations(adjacent, clue):
                    budget.generate()
                    targets = tuple(cell for cell in adjacent if cell not in flags)
                    changes = tuple((nx, ny) for nx, ny in adjacent
                                    if (grid[ny][nx] == FLAGGED) != ((nx, ny) in flags))
                    if not targets:
                        empty_excluded += 1
                        continue
                    if changes and len(targets) < 2:
                        single_excluded += 1
                        continue
                    sequence = tuple(EvidenceInput("FLAG", nx, ny) for nx, ny in changes)
                    add_spec("CHORD", (x, y), flags, targets,
                             sequence + (EvidenceInput("CHORD", x, y),))
        budget.check("catalogue.after")
        catalogue_complete = True

        for spec in specs:
            for key in (spec.targets,) + spec.zero_sets:
                budget.check("events.collect")
                references += 1
                if key in events:
                    duplicates += 1
                    continue
                proof = _base_proof(key, base.total_worlds, counts)
                if proof is not None:
                    events[key] = proof
                    continue
                if len(queued) >= request.limits.max_distinct_events:
                    raise _Stop("INSUFFICIENT", "DISTINCT_EVENT_LIMIT")
                events[key] = JointEvidence(key, reason="QUEUED")
                queued.append(key)
        budget.check("events.collected")
        collection_complete = True

        for start in range(0, len(queued), 16):
            keys = queued[start:start + 16]
            stage = f"batch.{start // 16}"
            reply = budget.backend(request, tuple(EventQuery(key) for key in keys), stage)
            queried.update(keys)
            if reply.base.status == "EXACT":
                batch_counts = _validate_base(reply.base, request)
                if reply.base.total_worlds != base.total_worlds or batch_counts != counts:
                    raise ValueError("Backend base mismatch between batches")
            elif reply.status in ("INSUFFICIENT", "CANCELLED", "ERROR"):
                budget.after_backend(stage + ".after")
                raise _Stop(reply.status, reply.reason)
            else:
                raise ValueError("Backend lost the exact public base")
            returned = {}
            for row in reply.events:
                key = row.event.safe_cells
                if row.event.mine_cells or key not in keys or key in returned:
                    raise ValueError("Backend event binding mismatch")
                if row.status == "EXACT":
                    if (type(row.event_worlds) is not int or not 0 <= row.event_worlds <= base.total_worlds
                            or type(row.probability) is not Fraction
                            or row.probability != Fraction(row.event_worlds, base.total_worlds)):
                        raise ValueError("Invalid exact event count")
                    proof = _base_proof(key, base.total_worlds, counts)
                    if proof is not None and proof.worlds != row.event_worlds:
                        raise ValueError("Event contradicts base proof")
                elif row.event_worlds is not None or row.probability is not None:
                    raise ValueError("Nonexact event contains numeric evidence")
                returned[key] = JointEvidence(key, row.status, row.reason, row.event_worlds)
            if set(returned) != set(keys):
                raise ValueError("Backend events missing")
            if reply.status not in ("COMPLETE", "PARTIAL", "ERROR", "CANCELLED", "INSUFFICIENT"):
                raise ValueError("Invalid batch status")
            if reply.status == "COMPLETE" and any(row.worlds is None for row in returned.values()):
                raise ValueError("Incomplete events labelled complete")
            # Validate joint-event relationships before committing this batch.
            # An inconsistent reply cannot replace earlier exact evidence.
            def prospective(key):
                return returned.get(key) or lookup(key)
            for spec in specs:
                survival = prospective(spec.targets).worlds
                for key in spec.zero_sets:
                    zero = prospective(key).worlds
                    if survival is not None and zero is not None and zero > survival:
                        raise ValueError("Backend zero event exceeds survival")
            events.update(returned)
            budget.after_backend(stage + ".after")
            if reply.status != "COMPLETE":
                backend_error = reply.status == "ERROR" or any(row.status == "ERROR" for row in returned.values())
                raise _Stop("ERROR" if backend_error else "INSUFFICIENT", reply.reason)

        budget.check("publish.before")
        candidates = tuple(materialize(spec) for spec in specs)
        budget.check("publish.after")
    except _Stop as exc:
        status, reason, stop_stage = exc.status, exc.reason, budget.stage
        if base.status == "EXACT" and status != "ERROR":
            status = "PARTIAL"
    except Exception as exc:
        status, reason, stop_stage = "ERROR", "EVIDENCE_ERROR", budget.stage
        budget.error = f"{type(exc).__name__}: {exc}"

    if not candidates and specs:
        # Output construction preserves completed facts even after a stop.
        # It performs no further backend call or cancellation callback.
        try:
            candidates = tuple(materialize(spec) for spec in specs)
        except Exception as exc:
            status, reason = "ERROR", "EVIDENCE_ERROR"
            budget.error = f"{type(exc).__name__}: {exc}"
            # Discard the inconsistent event batch, retaining base-derived facts.
            events = {key: row for key, row in events.items() if row.reason.startswith("BASE_")}
            candidates = tuple(materialize(spec) for spec in specs)
    exact_candidates = sum(row.status == "EXACT" for row in candidates)
    diagnostics = CandidateDiagnostics(
        budget.generated, empty_excluded, single_excluded, budget.calls, budget.work,
        budget.work_complete, len(queried), len(queued), references, duplicates,
        sum(row.reason.startswith("BASE_") for row in events.values()), exact_candidates,
        sum(row.survival.worlds is not None for row in candidates),
        sum(z.event.worlds is not None for row in candidates for z in row.zero_targets),
        perf_counter() - budget.started, budget.checkpoints, budget.stage,
        tuple(budget.trace), budget.error)
    return CandidateResult(identity, observation_id, FAMILY_ID, SCHEMA_VERSION, COUNTER_VERSION,
                           status, reason, stop_stage, base, has_safe, catalogue_complete,
                           collection_complete, status == "COMPLETE", candidates,
                           tuple(events.values()), diagnostics)
