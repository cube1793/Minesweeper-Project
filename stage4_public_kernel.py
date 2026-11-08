"""Draft public subset-constraint kernel; no engine, probabilities or actions.

COMPLETE means a fixed point of normalization, extremes and strict subsets.
Physical flags are unknown variables. Every published fact has a public DAG.
"""
from dataclasses import dataclass, fields
from time import perf_counter

from stage4_belief import BeliefRequest, PRIOR_ID, exact_json
from stage4_posterior import neighbor_indices, public_digest
from stage4_exact_pilot import (
    _backend_grid_check, _grid_payload, _integer_payload, _payload_fields,
    _seconds_payload, _validate_integer_limits, _validate_seconds, UNIT10_SUMMED,
)

PRODUCER = "STAGE4_PUBLIC_KERNEL"
VERSION = "public_subset_constraints_v1"
WORK_VERSION = "prepaid_bounded_bitsets_v1"


@dataclass(frozen=True, slots=True)
class KernelLimits:
    max_cells: int = 480
    max_constraints: int = 2048
    max_derived: int = 1024
    max_work: int = 500_000
    max_seconds: float = 2.0

    def __post_init__(self):
        _validate_integer_limits(self, (("max_cells", 480), ("max_constraints", 2048),
            ("max_derived", 1024), ("max_work", 500_000)))
        _validate_seconds(self.max_seconds, 2.0)
        object.__setattr__(self, "max_seconds", float(self.max_seconds))

    @classmethod
    def from_payload(cls, payload):
        return cls(**{k: (_seconds_payload(v) if k == "max_seconds" else _integer_payload(v))
                      for k, v in _payload_fields(payload, cls).items()})


@dataclass(frozen=True, slots=True)
class KernelRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int = 0
    prior_id: str = PRIOR_ID
    version: str = VERSION
    limits: KernelLimits = KernelLimits()

    def __post_init__(self):
        _backend_grid_check(UNIT10_SUMMED, self.observation)
        public = BeliefRequest(self.observation, self.num_mines, prior_id=self.prior_id)
        object.__setattr__(self, "observation", public.observation)
        if type(self.num_mines) is not int or type(self.counted_inputs) is not int or self.counted_inputs < 0:
            raise ValueError("Exact public integer counts required")
        if type(self.limits) is not KernelLimits or type(self.version) is not str:
            raise TypeError("KernelLimits and version string required")

    def to_payload(self):
        return exact_json(self)

    @property
    def identity(self):
        return public_digest((PRODUCER, self.to_payload()))

    @classmethod
    def from_payload(cls, payload):
        v = _payload_fields(payload, cls)
        if "observation" in v:
            _backend_grid_check(UNIT10_SUMMED, v["observation"])
            v["observation"] = _grid_payload(v["observation"])
        for k in ("num_mines", "counted_inputs"):
            if k in v:
                v[k] = _integer_payload(v[k])
        if "limits" in v:
            v["limits"] = KernelLimits.from_payload(v["limits"])
        return cls(**v)


@dataclass(frozen=True, slots=True)
class ConstraintProof:
    cells: tuple[int, ...]
    mines: int
    rule: str
    parents: tuple[int, ...] = ()
    source: int | None = None


@dataclass(frozen=True, slots=True)
class KernelResult:
    producer: str
    version: str
    request_id: str
    status: str
    reason: str
    proven_safe: tuple[int, ...]
    proven_mines: tuple[int, ...]
    constraints: tuple[ConstraintProof, ...]
    proof_id: str | None
    work: int
    work_by_family: tuple[tuple[str, int], ...]
    work_version: str
    constraint_count: int
    derived_count: int
    rounds: int
    elapsed_seconds: float
    error: str | None = None

    def to_payload(self):
        return exact_json(self)


class _Stop(Exception):
    pass


class _Meter:
    def __init__(self, limits, cancelled):
        self.start = perf_counter()
        self.deadline = self.start + limits.max_seconds
        self.limits, self.cancelled = limits, cancelled
        self.families = dict(preparation=0, variables=0, constraints=0,
                             subset_checks=0, differences=0, publication=0)
        self.work = 0

    def check(self):
        if self.cancelled is not None:
            value = self.cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _Stop("CANCELLED")
        if perf_counter() >= self.deadline:
            raise _Stop("TIME_LIMIT")

    def spend(self, family, amount=1):
        self.check()
        if self.work + amount > self.limits.max_work:
            raise _Stop("WORK_LIMIT")
        self.work += amount
        self.families[family] += amount


def _cells(mask):
    result = []
    while mask:
        bit = mask & -mask
        result.append(bit.bit_length() - 1)
        mask ^= bit
    return tuple(result)


def _mask(cells):
    return sum(1 << c for c in cells)


def _proof_identity(request, safe, mines, nodes):
    return public_digest((PRODUCER, VERSION, request.identity, safe, mines, nodes))


def infer_public(request, *, cancelled=None):
    """Return atomic facts only on COMPLETE; incomplete diagnostics retain work.

Invalid DTOs raise before execution. Callback faults and runtime faults return
ERROR. Limits and cancellation never expose a usable partial fact set.
"""
    if type(request) is not KernelRequest:
        raise TypeError("KernelRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable or None")
    meter = _Meter(request.limits, cancelled)
    nodes, masks, equations = [], [], {}
    safe = mines = derived = rounds = 0
    fact_sources = {}
    error, proof_id = None, None
    published_safe = published_mines = published_nodes = ()

    def add(mask, k, rule, parents=(), source=None):
        nonlocal derived, safe, mines
        meter.spend("constraints")
        if not 0 <= k <= mask.bit_count():
            raise _Stop("INCONSISTENT")
        if mask in equations:
            i = equations[mask]
            if nodes[i].mines != k:
                raise _Stop("INCONSISTENT")
            return i, False
        if len(nodes) >= request.limits.max_constraints:
            raise _Stop("CONSTRAINT_LIMIT")
        if rule == "SUBSET" and derived >= request.limits.max_derived:
            raise _Stop("DERIVED_LIMIT")
        meter.spend("variables", mask.bit_count())
        cells = _cells(mask)
        i = len(nodes)
        nodes.append(ConstraintProof(cells, k, rule, parents, source))
        masks.append(mask)
        equations[mask] = i
        derived += int(rule == "SUBSET")
        if mask and k in (0, len(cells)):
            is_mine = k != 0
            if mask & (safe if is_mine else mines):
                raise _Stop("INCONSISTENT")
            meter.spend("variables", len(cells))
            for c in cells:
                fact_sources.setdefault(c, i)
            if is_mine:
                mines |= mask
            else:
                safe |= mask
        return i, True

    try:
        meter.check()
        n = len(request.observation) * len(request.observation[0])
        if n > request.limits.max_cells:
            raise _Stop("CELL_LIMIT")
        if request.prior_id != PRIOR_ID or request.version != VERSION:
            raise _Stop("UNSUPPORTED")
        # Nine prepaid slots per grid cell: value and eight possible neighbors.
        meter.spend("preparation", 9 * n)
        flat = sum(request.observation, ())
        adj = neighbor_indices(len(request.observation[0]), len(request.observation))
        closed = _mask(c for c, v in enumerate(flat) if v < 0)
        for c, clue in enumerate(flat):
            meter.spend("constraints")
            if clue >= 0:
                meter.spend("variables", len(adj[c]))
                add(_mask(v for v in adj[c] if closed & (1 << v)), clue, "CLUE", source=c)
        add(closed, request.num_mines, "GLOBAL")
        while True:
            meter.check()
            rounds += 1
            before = (len(nodes), safe, mines)
            active = set()
            # Normalize every retained equation. Proof parents precede children.
            for i in range(len(nodes)):
                meter.spend("constraints")
                meter.spend("variables", len(nodes[i].cells))
                mask = masks[i]
                residual = mask & ~(safe | mines)
                k = nodes[i].mines - (mask & mines).bit_count()
                if residual != mask:
                    removed = _cells(mask & (safe | mines))
                    parents = (i,) + tuple(sorted({fact_sources[c] for c in removed}))
                    j, _ = add(residual, k, "NORMALIZE", parents)
                else:
                    j = i
                if masks[j]:
                    active.add(j)
            ordered = sorted(active, key=lambda i: (len(nodes[i].cells), nodes[i].cells, nodes[i].mines))
            for pos, a in enumerate(ordered):
                for b in ordered[pos + 1:]:
                    meter.spend("subset_checks")
                    ma, mb = masks[a], masks[b]
                    if ma != mb and ma & mb == ma:
                        meter.spend("differences", 1 + len(nodes[b].cells))
                        add(mb ^ ma, nodes[b].mines - nodes[a].mines, "SUBSET", (a, b))
            if before == (len(nodes), safe, mines):
                break
        meter.spend("publication", 1 + n + sum(1 + len(p.cells) for p in nodes))
        published_safe, published_mines, published_nodes = _cells(safe), _cells(mines), tuple(nodes)
        proof_id = _proof_identity(request, published_safe, published_mines, published_nodes)
        meter.check()
        status, reason = "COMPLETE", "SUBSET_RULE_FIXED_POINT"
    except _Stop as exc:
        status = reason = str(exc)
    except Exception as exc:
        status, reason, error = "ERROR", "INTERNAL_ERROR", f"{type(exc).__name__}: {exc}"
    if status != "COMPLETE":
        published_safe = published_mines = published_nodes = ()
        proof_id = None
    return KernelResult(PRODUCER, VERSION, request.identity, status, reason,
        published_safe, published_mines, published_nodes, proof_id, meter.work,
        tuple(meter.families.items()), WORK_VERSION, len(nodes), derived, rounds,
        perf_counter() - meter.start, error)


def verify_facts(request, result, *, checkpoint=None):
    """Replay the public proof DAG and check fixed-point and request binding.

No external proven set is accepted without its complete public certificate.
checkpoint receives a prepaid verification-unit count before bounded work.
Raises ValueError on invalid provenance; cancellation belongs to the caller.
"""
    def check(ok, reason):
        if not ok:
            raise ValueError(reason)

    def tick(n=1):
        if checkpoint is not None:
            checkpoint(n)

    check(type(request) is KernelRequest and type(result) is KernelResult, "FACT_DTO")
    check(result.status == "COMPLETE" and result.error is None, "FACTS_INCOMPLETE")
    check(result.producer == PRODUCER and result.version == request.version == VERSION and
          request.prior_id == PRIOR_ID and result.request_id == request.identity, "FACT_IDENTITY")
    check(result.work_version in (WORK_VERSION, "prepaid_indexed_immutable_relations_v1") and 0 <= result.work <= request.limits.max_work and
          result.work == sum(v for _, v in result.work_by_family), "FACT_ACCOUNTING")
    check(len(result.constraints) == result.constraint_count <= request.limits.max_constraints and
          result.derived_count == sum(p.rule == "SUBSET" for p in result.constraints) <= request.limits.max_derived,
          "FACT_CONSTRAINT_CAP")
    flat = sum(request.observation, ())
    tick(9 * len(flat))
    adj = neighbor_indices(len(request.observation[0]), len(request.observation))
    closed = {c for c, v in enumerate(flat) if v < 0}
    roots = {(tuple(n for n in adj[c] if n in closed), v) for c, v in enumerate(flat) if v >= 0}
    roots.add((tuple(sorted(closed)), request.num_mines))
    seen_roots, equations, masks = set(), {}, []
    safe, mines = set(), set()
    for i, p in enumerate(result.constraints):
        tick(1 + len(p.cells) + len(p.parents))
        check(type(p) is ConstraintProof and p.cells == tuple(sorted(set(p.cells))) and
              set(p.cells) <= closed and type(p.mines) is int and 0 <= p.mines <= len(p.cells), "PROOF_EQUATION")
        check(all(type(j) is int and 0 <= j < i for j in p.parents), "PROOF_PARENT")
        if p.rule in ("CLUE", "GLOBAL"):
            check(not p.parents, "ROOT_PARENTS")
            if p.rule == "GLOBAL":
                check(p.source is None and p.cells == tuple(sorted(closed)) and p.mines == request.num_mines,
                      "GLOBAL_PROOF")
            else:
                check(type(p.source) is int and 0 <= p.source < len(flat) and flat[p.source] >= 0 and
                      p.mines == flat[p.source] and p.cells == tuple(n for n in adj[p.source] if n in closed),
                      "CLUE_PROOF")
            seen_roots.add((p.cells, p.mines))
        elif p.rule == "SUBSET":
            check(p.source is None and len(p.parents) == 2, "SUBSET_PARENTS")
            a, b = (result.constraints[j] for j in p.parents)
            check(set(a.cells) < set(b.cells) and set(p.cells) == set(b.cells) - set(a.cells) and
                  p.mines == b.mines - a.mines, "SUBSET_PROOF")
        elif p.rule == "NORMALIZE":
            check(p.source is None and len(p.parents) >= 2, "NORMALIZE_PARENTS")
            base = result.constraints[p.parents[0]]
            rs, rm = set(), set()
            for j in p.parents[1:]:
                f = result.constraints[j]
                tick(len(f.cells))
                check(bool(f.cells) and f.mines in (0, len(f.cells)), "NORMALIZE_FACT_PARENT")
                (rm if f.mines else rs).update(f.cells)
            check(not rs & rm and set(p.cells) == set(base.cells) - rs - rm and
                  p.mines == base.mines - len(set(base.cells) & rm), "NORMALIZE_PROOF")
        else:
            raise ValueError("UNKNOWN_PROOF_RULE")
        check(p.cells not in equations, "DUPLICATE_EQUATION")
        equations[p.cells] = p.mines
        masks.append(_mask(p.cells))
        if p.mines == 0:
            safe.update(p.cells)
        elif p.mines == len(p.cells):
            mines.update(p.cells)
    check(roots <= seen_roots and not safe & mines, "ROOT_COVERAGE_OR_CONTRADICTION")
    check(result.proven_safe == tuple(sorted(safe)) and result.proven_mines == tuple(sorted(mines)), "FACT_PROJECTION")
    normalized = {}
    sm, mm = _mask(safe), _mask(mines)
    for p, m in zip(result.constraints, masks):
        tick(1 + len(p.cells))
        residual, k = m & ~(sm | mm), p.mines - (m & mm).bit_count()
        check(0 <= k <= residual.bit_count(), "FINAL_CONTRADICTION")
        check(not residual or 0 < k < residual.bit_count(), "UNPROPAGATED_FACT")
        check(residual not in normalized or normalized[residual] == k, "FINAL_DUPLICATE_CONFLICT")
        normalized[residual] = k
    keys = sorted(normalized, key=lambda m: (m.bit_count(), m))
    for pos, a in enumerate(keys):
        for b in keys[pos + 1:]:
            tick()
            if a and a != b and a & b == a:
                check(normalized.get(b ^ a) == normalized[b] - normalized[a], "NOT_SUBSET_FIXED_POINT")
    tick(1 + len(flat) + sum(len(p.cells) for p in result.constraints))
    check(result.proof_id == _proof_identity(request, result.proven_safe, result.proven_mines,
                                            result.constraints), "PROOF_HASH")
    return True
