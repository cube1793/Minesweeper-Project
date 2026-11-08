"""Unconnected indexed implementation of the public subset closure.

Only the physical work schedule changes. Proof equations are immutable; a
normalization creates (or finds) a different equation ID. Retired equations
remain in the certificate, never in the active relation index. Each pair of
simultaneously active immutable equations is visited on the later insertion.
No mutable-fact-dependent pair memo is used.
"""
from collections import deque
from time import perf_counter

from stage4_belief import PRIOR_ID
from stage4_posterior import neighbor_indices
from stage4_public_kernel import (
    PRODUCER, VERSION, KernelRequest, KernelResult, ConstraintProof,
    _Stop, _cells, _mask, _proof_identity, verify_facts,
)

WORK_VERSION = "prepaid_indexed_immutable_relations_v1"


class _Meter:
    def __init__(self, limits, cancelled):
        self.limits, self.cancelled = limits, cancelled
        self.start = perf_counter()
        self.deadline = self.start + limits.max_seconds
        self.work = 0
        self.families = dict(preparation=0, constraints=0, variables=0,
                             queue=0, index=0, subset_checks=0, differences=0,
                             publication=0, verification=0)

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


def infer_public_indexed(request, *, cancelled=None):
    """Same DTO/rules/caps as v1, with prepaid bounded indices and atomic output.

With C retained constraints and N cells, postings contain at most N*C IDs,
anchor postings at most C, active IDs at most C, and each queue at most C.
The deduplicated temporary relation set contains at most C IDs. There is no
unbounded relation memo. Verification and proof publication are prepaid too.
"""
    if type(request) is not KernelRequest:
        raise TypeError("KernelRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable or None")
    meter = _Meter(request.limits, cancelled)
    nodes, masks, equations = [], [], {}
    pending, queued = deque(), set()
    active, postings, anchors = set(), {}, {}
    fact_sources = {}
    safe = mines = derived = dequeues = 0
    error = proof_id = None
    published_safe = published_mines = published_nodes = ()

    def enqueue(i):
        meter.spend("queue", 2)
        if i not in queued:
            queued.add(i)
            pending.append(i)

    def add(mask, k, rule, parents=(), source=None):
        nonlocal safe, mines, derived
        meter.spend("constraints", 2)
        if not 0 <= k <= mask.bit_count():
            raise _Stop("INCONSISTENT")
        previous = equations.get(mask)
        if previous is not None:
            if nodes[previous].mines != k:
                raise _Stop("INCONSISTENT")
            return previous
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
        enqueue(i)
        if mask and k in (0, len(cells)):
            is_mine = k != 0
            if mask & (safe if is_mine else mines):
                raise _Stop("INCONSISTENT")
            fresh = mask & ~(safe | mines)
            meter.spend("variables", 2 * len(cells))
            for c in cells:
                fact_sources.setdefault(c, i)
            if is_mine:
                mines |= mask
            else:
                safe |= mask
            # Only equations indexed before these facts need invalidating.
            meter.spend("index", fresh.bit_count())
            for c in _cells(fresh):
                meter.spend("index", 1 + len(postings.get(c, ())))
                for j in postings.get(c, ()):
                    if j in active:
                        meter.spend("index")
                        active.remove(j)
                        enqueue(j)
        return i

    def normalize(i):
        meter.spend("variables", 2 + len(nodes[i].cells))
        mask = masks[i]
        removed = mask & (safe | mines)
        if not removed:
            return i
        # All supporting extremes precede the new immutable residual node.
        meter.spend("variables", removed.bit_count())
        parents = (i,) + tuple(sorted({fact_sources[c] for c in _cells(removed)}))
        return add(mask & ~(safe | mines), nodes[i].mines - (mask & mines).bit_count(),
                   "NORMALIZE", parents)

    try:
        meter.check()
        n = len(request.observation) * len(request.observation[0])
        if n > request.limits.max_cells:
            raise _Stop("CELL_LIMIT")
        if request.prior_id != PRIOR_ID or request.version != VERSION:
            raise _Stop("UNSUPPORTED")
        meter.spend("preparation", 9 * n)
        flat = sum(request.observation, ())
        adjacent = neighbor_indices(len(request.observation[0]), len(request.observation))
        closed = _mask(c for c, v in enumerate(flat) if v < 0)
        for c, clue in enumerate(flat):
            meter.spend("constraints")
            if clue >= 0:
                meter.spend("variables", len(adjacent[c]))
                add(_mask(v for v in adjacent[c] if closed & (1 << v)), clue, "CLUE", source=c)
        add(closed, request.num_mines, "GLOBAL")
        while pending:
            meter.spend("queue", 2)
            i = pending.popleft()
            queued.remove(i)
            dequeues += 1
            j = normalize(i)
            if j != i or not masks[i]:
                continue
            meter.spend("index")
            if i in active:
                continue
            cells, mask = nodes[i].cells, masks[i]
            # Every nonempty subset has an anchor in these cells. Supersets
            # must occur in every posting, so the shortest posting suffices.
            meter.spend("index", 2 * len(cells))
            anchor = min(cells, key=lambda c: len(postings.get(c, ())))
            possible = set()
            for c in cells:
                meter.spend("index", 1 + len(anchors.get(c, ())))
                possible.update(anchors.get(c, ()))
            meter.spend("index", 1 + len(postings.get(anchor, ())))
            possible.update(postings.get(anchor, ()))
            meter.spend("index", len(possible))
            # Integer IDs make traversal reproducible; ordering is not a rule.
            for other in sorted(possible):
                meter.spend("subset_checks")
                if other not in active:
                    continue
                a, b = (other, i) if len(nodes[other].cells) < len(cells) else (i, other)
                ma, mb = masks[a], masks[b]
                if ma != mb and ma & mb == ma:
                    meter.spend("differences", 1 + len(nodes[b].cells))
                    add(mb ^ ma, nodes[b].mines - nodes[a].mines, "SUBSET", (a, b))
                if mask & (safe | mines):
                    # Fresh facts require a new normalized relation identity.
                    enqueue(i)
                    break
            if mask & (safe | mines):
                continue
            meter.spend("index", 2 + len(cells))
            active.add(i)
            anchors.setdefault(cells[0], []).append(i)
            for c in cells:
                postings.setdefault(c, []).append(i)
        meter.spend("publication", 1 + n + sum(1 + len(p.cells) + len(p.parents) for p in nodes))
        published_safe, published_mines, published_nodes = _cells(safe), _cells(mines), tuple(nodes)
        proof_id = _proof_identity(request, published_safe, published_mines, published_nodes)
        certificate = KernelResult(PRODUCER, VERSION, request.identity, "COMPLETE",
            "SUBSET_RULE_FIXED_POINT", published_safe, published_mines, published_nodes,
            proof_id, meter.work, tuple(meter.families.items()), WORK_VERSION,
            len(nodes), derived, dequeues, perf_counter() - meter.start)
        verify_facts(request, certificate, checkpoint=lambda count: meter.spend("verification", count))
        meter.check()
        status = "COMPLETE"
        reason = "SUBSET_RULE_FIXED_POINT"
    except _Stop as exc:
        status = reason = str(exc)
    except Exception as exc:
        status, reason, error = "ERROR", "INTERNAL_ERROR", f"{type(exc).__name__}: {exc}"
    if status != "COMPLETE":
        published_safe = published_mines = published_nodes = ()
        proof_id = None
    return KernelResult(PRODUCER, VERSION, request.identity, status, reason,
        published_safe, published_mines, published_nodes, proof_id, meter.work,
        tuple(meter.families.items()), WORK_VERSION, len(nodes), derived, dequeues,
        perf_counter() - meter.start, error)
