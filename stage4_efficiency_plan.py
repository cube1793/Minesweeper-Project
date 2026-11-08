"""Draft safe-component costs and one-group plans over verified public facts.

Static cover costs exclude future floods and newly observed numbers. Exact
claims apply only to complete, unsplit supported components. No engine inputs.
"""
from dataclasses import dataclass
from fractions import Fraction
from time import perf_counter

from stage4_belief import FLAGGED, exact_json
from stage4_candidates import EvidenceInput
from stage4_posterior import neighbor_indices, public_digest
from stage4_exact_pilot import _validate_integer_limits, _validate_seconds
from stage4_public_kernel import KernelRequest, KernelResult, verify_facts

PRODUCER = "STAGE4_EFFICIENCY_PLAN"
VERSION = "public_fact_cover_v1"


@dataclass(frozen=True, slots=True)
class PlanLimits:
    max_pivots: int = 12
    max_targets: int = 96
    max_subsets: int = 131_072
    max_seconds: float = 1.0

    def __post_init__(self):
        _validate_integer_limits(self, (("max_pivots", 12), ("max_targets", 96), ("max_subsets", 131_072)))
        _validate_seconds(self.max_seconds, 1.0)
        object.__setattr__(self, "max_seconds", float(self.max_seconds))


@dataclass(frozen=True, slots=True)
class SafePivot:
    pivot: int
    targets: tuple[int, ...]
    required_mines: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SafeGroup:
    kind: str
    pivot: int
    targets: tuple[int, ...]
    required_mines: tuple[int, ...]
    sequence: tuple[EvidenceInput, ...]


@dataclass(frozen=True, slots=True)
class SafeCandidate:
    group: SafeGroup
    target_per_input: Fraction
    contains_proven_zero: bool


@dataclass(frozen=True, slots=True)
class ComponentCost:
    pivots: tuple[int, ...]
    targets: tuple[int, ...]
    status: str
    greedy_cost: int
    optimal_cost: int | None
    improvement: int | None
    new_mine_flags: int | None
    selected_pivots: tuple[int, ...]
    audit_groups: tuple[SafeGroup, ...]
    subsets: int


@dataclass(frozen=True, slots=True)
class PlanResult:
    producer: str
    version: str
    request_id: str
    proof_id: str | None
    limits: PlanLimits
    status: str
    reason: str
    provenance: str | None
    group: SafeGroup | None
    candidates: tuple[SafeCandidate, ...]
    components: tuple[ComponentCost, ...]
    subsets: int
    verification_units: int
    planning_visits: int
    elapsed_seconds: float
    plan_id: str
    error: str | None = None

    def to_payload(self):
        return exact_json(self)


def plan_identity(request_id, proof_id, limits, status, reason, provenance, group, candidates, components):
    return public_digest((PRODUCER, VERSION, request_id, proof_id, limits, status, reason,
                          provenance, group, candidates, components))


class _Stop(Exception):
    pass


class _Meter:
    def __init__(self, limits, cancelled):
        self.start = perf_counter()
        self.deadline = self.start + limits.max_seconds
        self.limits, self.cancelled = limits, cancelled
        self.subsets = self.verification = self.visits = 0

    def check(self):
        if self.cancelled is not None:
            value = self.cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _Stop("CANCELLED")
        if perf_counter() >= self.deadline:
            raise _Stop("TIME_LIMIT")

    def visit(self, amount=1):
        self.check()
        self.visits += amount

    def verify(self, amount):
        self.check()
        self.verification += amount

    def subset(self):
        self.check()
        if self.subsets >= self.limits.max_subsets:
            raise _Stop("SUBSET_LIMIT")
        self.subsets += 1


def _move(kind, c, width):
    return EvidenceInput(kind, c % width, c // width)


def _group(kind, pivot, targets, mines, flags, width):
    changes = sorted((set(mines) - flags) | (set(targets) & flags))
    return SafeGroup(kind, pivot, tuple(sorted(targets)), tuple(sorted(mines)),
                     tuple(_move("FLAG", c, width) for c in changes) + (_move(kind, pivot, width),))


def _candidates(ps, u, flags, zeros, width, meter, opened=frozenset()):
    rows = []
    for c in sorted(u - opened):
        meter.visit()
        g = _group("OPEN", c, {c}, set(), flags, width)
        rows.append(SafeCandidate(g, Fraction(1, len(g.sequence)), c in zeros))
    for p in ps:
        meter.visit()
        targets = set(p.targets) - opened
        if not targets:
            continue
        g = _group("CHORD", p.pivot, targets, p.required_mines, flags, width)
        rows.append(SafeCandidate(g, Fraction(len(targets), len(g.sequence)), bool(targets & zeros)))
    return tuple(sorted(rows, key=_candidate_key))


def _candidate_key(c):
    g = c.group
    return (-c.target_per_input, -int(c.contains_proven_zero), len(g.sequence),
            ("OPEN", "CHORD").index(g.kind), g.pivot,
            tuple((m.action, m.y, m.x) for m in g.sequence))


def _greedy(ps, u, initial_flags, zeros, width, meter):
    flags, opened, groups = set(initial_flags), set(), []
    while opened != u:
        rows = _candidates(ps, u, flags, zeros, width, meter, opened)
        # Unit18's one-target/preparation CHORD is dominated by its OPEN.
        eligible = [c for c in rows if not (c.group.kind == "CHORD" and
                    len(c.group.sequence) > 1 and len(c.group.targets) < 2)]
        g = eligible[0].group
        for m in g.sequence[:-1]:
            flags.symmetric_difference_update({m.y * width + m.x})
        opened.update(g.targets)
        groups.append(g)
    return tuple(groups)


def _compile(ps, u, selected, initial_flags, width):
    flags, opened, groups = set(initial_flags), set(), []
    for i in selected:
        p = ps[i]
        targets = set(p.targets) - opened
        if not targets:
            raise ValueError("REDUNDANT_OPTIMUM")
        g = _group("CHORD", p.pivot, targets, p.required_mines, flags, width)
        for m in g.sequence[:-1]:
            flags.symmetric_difference_update({m.y * width + m.x})
        opened.update(p.targets)
        groups.append(g)
    for c in sorted(u - opened):
        groups.append(_group("OPEN", c, {c}, set(), flags, width))
    return tuple(groups)


def plan_safe(request, facts, *, limits=PlanLimits(), cancelled=None):
    """Verify facts, cost all components, and return only the next safe group.

Non-READY results carry no executable group. Large components retain a greedy
cost with UNSUPPORTED_SIZE; no exact cost is assigned to a fragment.
"""
    if type(request) is not KernelRequest or type(facts) is not KernelResult or type(limits) is not PlanLimits:
        raise TypeError("KernelRequest, KernelResult and PlanLimits required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable or None")
    meter = _Meter(limits, cancelled)
    components, candidates = [], ()
    group = provenance = error = None
    try:
        meter.check()
        if facts.status != "COMPLETE":
            raise _Stop("FACTS_INCOMPLETE")
        verify_facts(request, facts, checkpoint=meter.verify)
        flat = sum(request.observation, ())
        width, height = len(request.observation[0]), len(request.observation)
        meter.visit(9 * len(flat))
        adj = neighbor_indices(width, height)
        safe, mines = set(facts.proven_safe), set(facts.proven_mines)
        flags = {c for c, v in enumerate(flat) if v == FLAGGED}
        zeros = {c for c in safe if all(flat[n] >= 0 or n in safe for n in adj[c])}
        ps = []
        for c, clue in enumerate(flat):
            meter.visit()
            if clue > 0:
                closed = {n for n in adj[c] if flat[n] < 0}
                t, f = closed & safe, closed & mines
                if t and closed <= safe | mines and len(f) == clue:
                    ps.append(SafePivot(c, tuple(sorted(t)), tuple(sorted(f))))
        candidates = _candidates(ps, safe, flags, zeros, width, meter)
        pending = set(range(len(ps)))
        while pending:
            indices = {min(pending)}
            pending -= indices
            frontier = sorted(indices)
            while frontier:
                i = frontier.pop()
                for j in sorted(pending):
                    meter.visit()
                    if (set(ps[i].targets) & set(ps[j].targets) or
                            set(ps[i].required_mines) & set(ps[j].required_mines)):
                        pending.remove(j)
                        indices.add(j)
                        frontier.append(j)
            component = tuple(ps[i] for i in sorted(indices))
            u = set().union(*(set(p.targets) for p in component))
            greedy = _greedy(component, u, flags, zeros, width, meter)
            greedy_cost = sum(len(g.sequence) for g in greedy)
            pivots = tuple(p.pivot for p in component)
            if len(component) > limits.max_pivots or len(u) > limits.max_targets:
                components.append(ComponentCost(pivots, tuple(sorted(u)), "UNSUPPORTED_SIZE", greedy_cost,
                    None, None, None, (), greedy, 0))
                continue
            best = chosen = None
            before = meter.subsets
            for mask in range(1 << len(component)):
                meter.subset()
                selected = tuple(i for i in range(len(component)) if mask & (1 << i))
                t = set().union(*(set(component[i].targets) for i in selected))
                f = set().union(*(set(component[i].required_mines) for i in selected))
                new_flags = len(f - flags)
                cost = new_flags + len(u & flags) + len(selected) + len(u - t)
                key = (cost, new_flags, len(selected), tuple(component[i].pivot for i in selected))
                if best is None or key < best:
                    best, chosen = key, selected
            groups = _compile(component, u, chosen, flags, width)
            if sum(len(g.sequence) for g in groups) != best[0] or best[0] > greedy_cost:
                raise ValueError("COVER_COST_MISMATCH")
            components.append(ComponentCost(pivots, tuple(sorted(u)), "EXACT", greedy_cost, best[0],
                greedy_cost - best[0], best[1], best[3], groups, meter.subsets - before))
        positive = [c for c in components if c.status == "EXACT" and c.improvement > 0]
        if positive:
            choice = min(positive, key=lambda c: (-c.improvement, c.new_mine_flags, c.optimal_cost, c.pivots))
            group = next(g for g in choice.audit_groups if g.kind == "CHORD")
            provenance, reason = "EXACT_COMPONENT_COVER", "LARGEST_POSITIVE_STATIC_IMPROVEMENT"
        elif candidates:
            group = candidates[0].group
            large = any(c.status == "UNSUPPORTED_SIZE" and set(group.targets) & set(c.targets) for c in components)
            provenance = "GLOBAL_RATIO_LARGE_COMPONENT" if large else "GLOBAL_SAFE_RATIO"
            reason = "NO_POSITIVE_SUPPORTED_COVER"
        else:
            reason = "NO_SAFE_PROGRESS"
        meter.check()
        status = "READY" if group else "NO_SAFE_PROGRESS"
    except _Stop as exc:
        status = reason = str(exc)
    except Exception as exc:
        status, reason, error = "ERROR", "INVALID_FACTS_OR_INTERNAL_ERROR", f"{type(exc).__name__}: {exc}"
    if status not in ("READY", "NO_SAFE_PROGRESS"):
        group = provenance = None
        # No partially evaluated collection is presented as a completed ranking.
        candidates, components = (), []
    meter_elapsed = perf_counter() - meter.start
    components = tuple(components)
    identity = plan_identity(request.identity, facts.proof_id, limits, status, reason,
                             provenance, group, candidates, components)
    return PlanResult(PRODUCER, VERSION, request.identity, facts.proof_id, limits, status, reason,
                      provenance, group, candidates, components, meter.subsets, meter.verification,
                      meter.visits, meter_elapsed, identity, error)
