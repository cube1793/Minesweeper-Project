"""Bounded public rollout selection with exact root eligibility.

Model values describe a shortlisted candidate followed by fixed P0. Continuation
consumption is scoped to one caller-owned RolloutPolicy instance.
"""

from dataclasses import dataclass, fields, replace
from fractions import Fraction
from math import isfinite
from threading import Lock
from time import perf_counter
from uuid import uuid4

from stage4_belief import BeliefRequest, FLAGGED, HIDDEN, exact_json
from stage4_candidates import CandidateLimits, CandidateRequest, EvidenceInput, analyze_candidates
from stage4_posterior import PosteriorRequest, SamplerLimits, public_digest, sample_posterior
from stage4_rollout import PILOT_ID, RolloutLimits, evaluate_rollouts


POLICY_ID = "BOUNDED_PUBLIC_ROLLOUT_V1"


@dataclass(frozen=True, slots=True)
class PolicyLimits:
    max_cells: int = 480
    samples: int = 16
    shortlist: int = 6
    sampler_work: int = 2_000_000
    virtual_inputs: int = 50_000
    pilot_work: int = 10_000_000
    rollouts: int = 768
    inputs_per_rollout: int = 2_000
    max_seconds: float = 30.0
    root: CandidateLimits = CandidateLimits()

    def __post_init__(self):
        for name, cap in (("max_cells", 480), ("samples", 64), ("shortlist", 12),
                          ("sampler_work", 2_000_000), ("virtual_inputs", 50_000),
                          ("pilot_work", 30_000_000), ("rollouts", 768),
                          ("inputs_per_rollout", 2_000)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= cap:
                raise ValueError(f"{name} must be in 0..{cap}")
        if (type(self.max_seconds) not in (float, int) or not isfinite(self.max_seconds)
                or not 0 <= self.max_seconds <= 30):
            raise ValueError("max_seconds must be in 0..30")
        if type(self.root) is not CandidateLimits:
            raise TypeError("CandidateLimits required")


@dataclass(frozen=True, slots=True)
class Continuation:
    session_key: str
    serial: int
    episode_key: str
    settings_id: str
    original_grid: tuple[tuple[int, ...], ...]
    original_c: int
    sequence: tuple[EvidenceInput, ...]
    issued: int
    expected_grid: tuple[tuple[int, ...], ...]
    expected_c: int

    def __post_init__(self):
        for name in ("session_key", "episode_key", "settings_id"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise ValueError("Continuation IDs must be nonempty strings")
        for name in ("serial", "original_c", "issued", "expected_c"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError("Continuation counts must be nonnegative integers")
        for name in ("original_grid", "expected_grid"):
            grid = BeliefRequest(getattr(self, name), 0).observation
            object.__setattr__(self, name, grid)
        if (type(self.sequence) not in (tuple, list)
                or any(type(move) is not EvidenceInput for move in self.sequence)):
            raise TypeError("Continuation requires atomic inputs")
        object.__setattr__(self, "sequence", tuple(self.sequence))
        if not 1 <= self.issued < len(self.sequence) <= 9:
            raise ValueError("Invalid continuation prefix")


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int
    mode: str = "S"
    allow_guess: bool = False
    target: Fraction | None = None
    planning_seed: int | str = 0
    episode_key: str = "public-episode"
    limits: PolicyLimits = PolicyLimits()
    continuation: Continuation | None = None

    def __post_init__(self):
        public = BeliefRequest(self.observation, self.num_mines)
        object.__setattr__(self, "observation", public.observation)
        object.__setattr__(self, "num_mines", public.num_mines)
        if type(self.counted_inputs) is not int or self.counted_inputs < 0:
            raise ValueError("counted_inputs must be a nonnegative integer")
        if self.mode not in ("S", "M", "R") or type(self.allow_guess) is not bool:
            raise ValueError("Invalid public mode or guess setting")
        if type(self.planning_seed) not in (str, int):
            raise TypeError("planning_seed must be a public string or integer")
        if type(self.episode_key) is not str or not self.episode_key:
            raise ValueError("episode_key must be a nonempty public string")
        if self.target is not None:
            if type(self.target) not in (Fraction, int, str):
                raise TypeError("target must be an exact rational")
            value = Fraction(self.target)
            if value <= 0:
                raise ValueError("target must be positive")
            object.__setattr__(self, "target", value)
        if type(self.limits) is not PolicyLimits:
            raise TypeError("PolicyLimits required")
        if self.continuation is not None and type(self.continuation) is not Continuation:
            raise TypeError("Continuation required")

    @property
    def settings_id(self):
        return public_digest((self.num_mines, self.mode, self.allow_guess, self.target,
                              self.planning_seed, self.limits))

    @property
    def identity(self):
        return public_digest((POLICY_ID, self))

    @classmethod
    def from_payload(cls, payload):
        if type(payload) is not dict or set(payload) - {f.name for f in fields(cls)}:
            raise ValueError("Unknown policy request fields")
        values = dict(payload)
        if "limits" in values:
            if type(values["limits"]) is not dict:
                raise TypeError("limits must be a dictionary")
            limits = dict(values["limits"])
            if "root" in limits:
                if type(limits["root"]) is not dict:
                    raise TypeError("root limits must be a dictionary")
                limits["root"] = CandidateLimits(**limits["root"])
            values["limits"] = PolicyLimits(**limits)
        if isinstance(values.get("target"), dict):
            target = values["target"]
            if set(target) != {"numerator", "denominator"}:
                raise ValueError("Unknown target fields")
            if any(type(value) not in (int, str) for value in target.values()):
                raise TypeError("Target numerator and denominator must be exact integers")
            values["target"] = Fraction(int(target["numerator"]), int(target["denominator"]))
        if values.get("continuation") is not None:
            if type(values["continuation"]) is not dict:
                raise TypeError("continuation must be a dictionary")
            continuation = dict(values["continuation"])
            continuation["sequence"] = tuple(EvidenceInput(**move) for move in continuation["sequence"])
            values["continuation"] = Continuation(**continuation)
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ShortlistEntry:
    candidate_id: str
    included: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ModelScore:
    candidate_id: str
    rollout_mean_x: Fraction | None
    rollout_win_rate: Fraction | None
    rollout_hit_rate: Fraction | None
    sample_count: int
    terminal_count: int
    pilot_id: str = PILOT_ID


def model_order(score, survival, fallback_index, mode):
    """Exact arithmetic ordering of complete model scores, also used by tests."""
    if score.rollout_mean_x is None or score.rollout_win_rate is None:
        raise ValueError("Complete model scores required")
    common = (score.rollout_mean_x, score.rollout_win_rate, survival, -fallback_index)
    if mode == "R":
        if score.rollout_hit_rate is None:
            raise ValueError("Explicit target evaluation required")
        return (score.rollout_hit_rate,) + common
    return common


@dataclass(frozen=True, slots=True)
class PolicyResult:
    policy_id: str
    request_id: str
    status: str
    reason: str
    action: EvidenceInput | None
    continuation: Continuation | None
    selection_basis: str | None
    target_status: str
    selected_candidate_id: str | None
    root: object | None
    shortlist: tuple[ShortlistEntry, ...]
    posterior: object | None
    rollouts: object | None
    scores: tuple[ModelScore, ...]
    elapsed_seconds: float
    error: str | None

    def to_dict(self):
        return exact_json(self)


class _PolicyStop(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class _Budget:
    def __init__(self, seconds, cancelled):
        self.started = perf_counter()
        self.seconds, self.cancelled, self.pending = seconds, cancelled, None

    def check(self):
        if self.pending is not None:
            raise self.pending
        if self.cancelled is not None:
            value = self.cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _PolicyStop("CANCELLED", "GLOBAL_CANCELLED")
        if perf_counter() - self.started >= self.seconds:
            raise _PolicyStop("INSUFFICIENT", "GLOBAL_TIME_LIMIT")

    def relay(self):
        try:
            self.check()
        except Exception as exc:
            self.pending = exc
            return True
        return False

    def remaining(self):
        self.check()
        return max(0.0, self.seconds - (perf_counter() - self.started))


def _eligible(candidate, request):
    if not request.allow_guess:
        return candidate.eligibility.guess_off
    return getattr(candidate.eligibility, request.mode + "_guess_on")


def _validate_root(root, query, budget):
    if root.request_id != query.identity:
        raise ValueError("Root request binding mismatch")
    if root.status != "COMPLETE":
        return
    if not (root.catalogue_complete and root.event_collection_complete and root.evidence_complete):
        raise ValueError("Incomplete root labelled complete")
    denominator = root.base.total_worlds
    if root.base.status != "EXACT" or type(denominator) is not int or denominator <= 0:
        raise ValueError("Invalid exact root base")
    counts = {row.coordinate: row.mine_worlds for row in root.base.marginals}
    expected = {(x, y) for y, row in enumerate(query.observation)
                for x, value in enumerate(row) if value < 0}
    if set(counts) != expected or len(counts) != len(root.base.marginals):
        raise ValueError("Invalid root marginals")
    for row in root.base.marginals:
        if (type(row.mine_worlds) is not int or not 0 <= row.mine_worlds <= denominator
                or row.probability != Fraction(row.mine_worlds, denominator)):
            raise ValueError("Invalid root probability")
    if sum(counts.values()) != query.num_mines * denominator:
        raise ValueError("Invalid root mine total")
    has_safe = any(value == 0 for value in counts.values())
    if root.has_proven_safe_cell is not has_safe:
        raise ValueError("Invalid root safety flag")
    identities = set()
    for candidate in root.candidates:
        budget.check()
        if candidate.candidate_id in identities:
            raise ValueError("Duplicate root candidate")
        identities.add(candidate.candidate_id)
        worlds, cost = candidate.survival.worlds, candidate.immediate_input_cost
        if (candidate.status != "EXACT" or candidate.survival.status != "EXACT"
                or type(worlds) is not int or not 0 <= worlds <= denominator
                or not 1 <= cost <= 9 or cost != len(candidate.sequence)
                or candidate.target_count != len(candidate.targets) or not candidate.targets
                or candidate.survival_probability != Fraction(worlds, denominator)
                or candidate.survival_weighted_target_floor_per_input
                != Fraction(worlds * candidate.target_count, denominator * cost)):
            raise ValueError("Invalid root candidate evidence")
        if (candidate.sequence[-1].action != candidate.kind
                or candidate.kind not in ("OPEN", "CHORD")
                or any(move.action != "FLAG" for move in candidate.sequence[:-1])
                or len(set(candidate.sequence[:-1])) != cost - 1):
            raise ValueError("Invalid root atomic sequence")
        safe, viable = worlds == denominator, worlds > 0
        s_allowed = safe if has_safe else (candidate.kind == "OPEN" and viable
                                           and counts[candidate.pivot] == min(counts.values()))
        if (candidate.eligibility.guess_off is not safe
                or candidate.eligibility.S_guess_on is not s_allowed
                or candidate.eligibility.M_guess_on is not viable
                or candidate.eligibility.R_guess_on is not viable):
            raise ValueError("Invalid exact eligibility")
        for zero in candidate.zero_targets:
            z = zero.event.worlds
            if (zero.event.status != "EXACT" or type(z) is not int or not 0 <= z <= worlds
                    or zero.zero_and_survive_probability != Fraction(z, denominator)):
                raise ValueError("Invalid zero-event probability")


def _shortlist(root, request):
    catalogue = list(root.candidates)
    indices = {row.candidate_id: i for i, row in enumerate(catalogue)}

    def opening(row):
        return max((z.zero_and_survive_probability for z in row.zero_targets), default=Fraction(0)) / row.immediate_input_cost

    def fallback(row):
        return (-opening(row), -row.survival_weighted_target_floor_per_input,
                -row.survival_probability, row.immediate_input_cost, indices[row.candidate_id])

    eligible = sorted((row for row in catalogue if _eligible(row, request)), key=fallback)
    chosen, reasons = [], {}

    def add(row, reason):
        if row is not None and row.candidate_id not in reasons and len(chosen) < request.limits.shortlist:
            chosen.append(row)
            reasons[row.candidate_id] = reason

    direct = [row for row in eligible if row.kind == "OPEN"]
    if direct:
        add(min(direct, key=lambda row: (-row.survival_probability, fallback(row))), "SURVIVAL_OPEN_ANCHOR")
    if eligible:
        add(min(eligible, key=lambda row: (-opening(row), fallback(row))), "OPENING_ANCHOR")
        add(min(eligible, key=lambda row: (-row.survival_weighted_target_floor_per_input, fallback(row))), "TARGET_FLOOR_ANCHOR")
    for row in eligible:
        add(row, "FALLBACK_ORDER_FILL")
    entries = tuple(ShortlistEntry(row.candidate_id, row.candidate_id in reasons,
                                  reasons.get(row.candidate_id, "SHORTLIST_LIMIT" if _eligible(row, request)
                                              else "EXACT_INELIGIBLE")) for row in catalogue)
    return eligible, chosen, entries


def _scores(candidates, samples, batch, target):
    expected = {(c.candidate_id, i): sample.rank for c in candidates for i, sample in enumerate(samples)}
    rows = {}
    for row in batch.records:
        key = (row.candidate_id, row.sample_index)
        if key not in expected or key in rows or row.rank != expected[key]:
            raise ValueError("Rollout bank/candidate binding mismatch")
        if row.outcome in ("WON", "LOST"):
            if type(row.value_x) is not Fraction or row.value_x < 0:
                raise ValueError("Invalid terminal model reward")
            if row.outcome == "LOST" and row.value_x != 0:
                raise ValueError("Loss reward must equal zero")
            hit = row.outcome == "WON" and row.value_x >= target if target is not None else None
            if row.hit is not hit:
                raise ValueError("Invalid model hit")
        elif row.value_x is not None or row.hit is not None:
            raise ValueError("Unresolved model reward must be null")
        rows[key] = row
    if rows.keys() != expected.keys():
        raise ValueError("Rollout matrix is incomplete")
    complete = batch.status == "COMPLETE" and all(r.outcome in ("WON", "LOST") for r in rows.values())
    if batch.status == "COMPLETE" and not complete:
        raise ValueError("Unfinished rollout labelled complete")
    scores = []
    for candidate in candidates:
        group = [rows[(candidate.candidate_id, i)] for i in range(len(samples))]
        terminal = sum(row.outcome in ("WON", "LOST") for row in group)
        mean = sum((row.value_x for row in group), Fraction(0)) / len(group) if complete else None
        win = Fraction(sum(row.outcome == "WON" for row in group), len(group)) if complete else None
        hit = Fraction(sum(row.hit is True for row in group), len(group)) if complete and target is not None else None
        scores.append(ModelScore(candidate.candidate_id, mean, win, hit, len(samples), terminal))
    return tuple(scores)


class RolloutPolicy:
    """Computational session for single-use public FLAG continuations.

    There are no UI handles, game engines, worker owners or global registries.
    Use the same instance throughout a public episode.
    """

    def __init__(self):
        self._lock = Lock()
        self._session_key = uuid4().hex
        self._serial = 0
        self._pending = None
        self._last_emitted_position = None

    def select_next(self, request, *, cancelled=None):
        if type(request) is not PolicyRequest:
            raise TypeError("PolicyRequest required")
        budget = _Budget(request.limits.max_seconds, cancelled)
        root = posterior = rollouts = action = continuation = None
        entries, scores = (), ()
        selected_id = basis = error = None
        status, reason = "INSUFFICIENT", "NOT_SELECTED"
        target_status = "TARGET_NOT_EVALUATED" if request.mode == "R" else "NOT_APPLICABLE"
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return PolicyResult(POLICY_ID, request.identity, "BUSY", "CALL_IN_PROGRESS", None, None,
                                None, target_status, None, None, (), None, None, (), 0.0, None)
        pending, self._pending = self._pending, None
        try:
            budget.check()
            position = (request.episode_key, request.observation, request.counted_inputs)
            if position == self._last_emitted_position:
                raise _PolicyStop("STALE", "INPUT_NOT_OBSERVED_OR_DUPLICATE")
            token = request.continuation
            if pending is not None or token is not None:
                if (pending is None or token != pending or token.session_key != self._session_key
                        or token.episode_key != request.episode_key or token.settings_id != request.settings_id
                        or token.expected_grid != request.observation or token.expected_c != request.counted_inputs):
                    raise _PolicyStop("STALE", "CONTINUATION_MISMATCH")
            if request.mode == "R" and request.target is None:
                raise _PolicyStop("TARGET_REQUIRED", "POSITIVE_EXPLICIT_TARGET_REQUIRED")
            cells = len(request.observation) * len(request.observation[0])
            if cells > request.limits.max_cells:
                raise _PolicyStop("UNSUPPORTED", "CELL_LIMIT")
            if request.num_mines == cells:
                raise _PolicyStop("UNSUPPORTED", "NO_SAFE_CELLS_CONFIGURATION")
            query = CandidateRequest(request.observation, request.num_mines,
                                     replace(request.limits.root, max_seconds=min(request.limits.root.max_seconds,
                                                                                 budget.remaining())))
            root = analyze_candidates(query, cancelled=budget.relay)
            budget.check()
            _validate_root(root, query, budget)
            if root.status != "COMPLETE":
                status = "ERROR" if root.status == "ERROR" else root.status
                raise _PolicyStop(status, "ROOT_" + root.reason)
            if sum(v >= 0 for row in request.observation for v in row) == cells - request.num_mines:
                raise _PolicyStop("PUBLIC_COMPLETE", "ALL_SAFE_CELLS_PUBLIC")
            eligible, chosen, entries = _shortlist(root, request)
            if not eligible:
                if not request.allow_guess and root.has_proven_safe_cell is False:
                    raise _PolicyStop("DEFER", "GUESS_DISABLED")
                raise _PolicyStop("NO_CANDIDATE", "NO_EXACT_ELIGIBLE_CANDIDATE")
            if token is not None:
                remaining = token.sequence[token.issued:]
                selected = next((row for row in eligible if row.sequence == remaining), None)
                if selected is None:
                    raise _PolicyStop("STALE", "CONTINUATION_NO_LONGER_ELIGIBLE")
                basis = "EXACT_REVALIDATED_CONTINUATION"
            else:
                selected = eligible[0]
                if not chosen:
                    raise _PolicyStop("INSUFFICIENT", "EMPTY_SHORTLIST")
                sampler_query = PosteriorRequest(
                    request.observation, request.num_mines, request.counted_inputs, request.planning_seed,
                    request.limits.samples, SamplerLimits(request.limits.max_cells, request.limits.sampler_work,
                                                          min(10.0, budget.remaining())))
                posterior = sample_posterior(sampler_query, cancelled=budget.relay)
                budget.check()
                if posterior.status not in ("COMPLETE", "INSUFFICIENT", "ERROR", "INCONSISTENT_INPUT", "UNSUPPORTED", "CANCELLED"):
                    raise ValueError("Unknown sampler status")
                if posterior.seed_id != sampler_query.seed_id:
                    raise ValueError("Sampler public seed binding mismatch")
                if posterior.status in ("ERROR", "INCONSISTENT_INPUT", "UNSUPPORTED", "CANCELLED"):
                    raise _PolicyStop("ERROR", "MODEL_" + posterior.reason)
                if posterior.total_worlds is not None and posterior.total_worlds != root.base.total_worlds:
                    raise ValueError("Sampler/root denominator mismatch")
                basis = "HEURISTIC_FALLBACK"
                reason = "SAMPLER_" + posterior.reason
                if posterior.status == "COMPLETE":
                    expected_count = min(request.limits.samples, root.base.total_worlds)
                    if not expected_count or len(posterior.samples) != expected_count:
                        raise ValueError("Complete sampler returned an invalid bank size")
                    if any(type(sample.rank) is not int or not 0 <= sample.rank < root.base.total_worlds
                           for sample in posterior.samples):
                        raise ValueError("Sampler returned an invalid rank")
                    rollout_limits = RolloutLimits(
                        request.limits.rollouts, request.limits.virtual_inputs, request.limits.inputs_per_rollout,
                        request.limits.pilot_work, budget.remaining())
                    rollouts = evaluate_rollouts(
                        request.observation, request.num_mines, request.counted_inputs, request.allow_guess,
                        posterior.samples, chosen, target=request.target, limits=rollout_limits,
                        cancelled=budget.relay)
                    budget.check()
                    if rollouts.status not in ("COMPLETE", "INCOMPLETE", "ERROR", "CANCELLED"):
                        raise ValueError("Unknown rollout status")
                    if rollouts.status in ("ERROR", "CANCELLED"):
                        raise _PolicyStop("ERROR", "MODEL_" + rollouts.reason)
                    scores = _scores(chosen, posterior.samples, rollouts, request.target)
                    reason = "ROLLOUT_" + rollouts.reason
                    if rollouts.status == "COMPLETE":
                        fallback_indices = {row.candidate_id: i for i, row in enumerate(eligible)}
                        by_id = {score.candidate_id: score for score in scores}
                        selected = max(chosen, key=lambda row: model_order(
                            by_id[row.candidate_id], row.survival_probability,
                            fallback_indices[row.candidate_id], request.mode))
                        basis, reason = "MODEL_SELECTED", "COMPLETE_COMMON_BANK"
                        if request.mode == "R":
                            target_status = "MODEL_EVALUATED"
                            if by_id[selected.candidate_id].rollout_hit_rate == 0:
                                target_status = "MODEL_ZERO_HITS"
            budget.check()
            action = selected.sequence[0]
            selected_id = selected.candidate_id
            if action.action == "FLAG":
                grid = [list(row) for row in request.observation]
                value = grid[action.y][action.x]
                if value not in (HIDDEN, FLAGGED):
                    raise ValueError("FLAG continuation requires an unknown cell")
                grid[action.y][action.x] = FLAGGED if value == HIDDEN else HIDDEN
                self._serial += 1
                original_grid = token.original_grid if token is not None else request.observation
                original_c = token.original_c if token is not None else request.counted_inputs
                sequence = token.sequence if token is not None else selected.sequence
                issued = token.issued + 1 if token is not None else 1
                continuation = Continuation(self._session_key, self._serial, request.episode_key,
                                            request.settings_id, original_grid, original_c, sequence, issued,
                                            tuple(tuple(row) for row in grid), request.counted_inputs + 1)
            budget.check()
            self._pending = continuation
            self._last_emitted_position = position
            status = "READY"
            if basis == "EXACT_REVALIDATED_CONTINUATION":
                reason = "CURRENT_EXACT_SEQUENCE_MATCH"
        except _PolicyStop as exc:
            status, reason = exc.status, exc.reason
            action = continuation = None
        except Exception as exc:
            status, reason = "ERROR", "POLICY_ERROR"
            error = f"{type(exc).__name__}: {exc}"
            action = continuation = None
        finally:
            self._lock.release()
        return PolicyResult(POLICY_ID, request.identity, status, reason, action, continuation,
                            basis, target_status, selected_id, root, entries, posterior, rollouts, scores,
                            perf_counter() - budget.started, error)
