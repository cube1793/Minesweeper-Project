"""Exact base counts for one bounded, public Minesweeper observation.

A single cooperative budget covers preparation, search, combination and publication.
Only propagated component subproblems are memoized, for the life of that component.
"""
from dataclasses import dataclass, fields
from fractions import Fraction
from hashlib import sha256
import json
from math import comb, isfinite
from time import perf_counter_ns

from stage4_belief import BaseResult, CellCount, NORMALIZATION_POLICY, PRIOR_ID, _grid, exact_json


MATH_VERSION = "public_full_placements_v1"
API_VERSION = "standalone_count_request_v1"
BACKEND_VERSION = "residual_component_counts_v2"
WORK_ACCOUNTING_VERSION = "summed_visits_v1"

_PRIMARY = ("forced_assignments", "branch_attempts", "dp_products")
_AUXILIARY = ("preparation_visits", "constraint_visits", "constraint_cell_visits",
              "memo_operations", "histogram_updates", "publish_visits")


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _payload_values(payload, cls):
    if type(payload) is not dict:
        raise TypeError("Public payload must be a dictionary")
    if payload.keys() - {f.name for f in fields(cls)}:
        raise ValueError("Unknown public payload field")
    return dict(payload)


@dataclass(frozen=True, slots=True)
class CountLimits:
    max_cells: int = 480
    max_total_work: int = 200_000
    max_seconds: float = 2.0
    memo_entries: int = 16_384
    memo_scalars: int = 1_000_000

    def __post_init__(self):
        for name, cap in (("max_cells", 480), ("max_total_work", 200_000),
                          ("memo_entries", 16_384), ("memo_scalars", 1_000_000)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= cap:
                raise ValueError(f"{name} must be an integer in 0..{cap}")
        seconds = self.max_seconds
        if type(seconds) not in (int, float) or not 0 <= seconds <= 2 or not isfinite(seconds):
            raise ValueError("max_seconds must be a finite number in 0..2")
        object.__setattr__(self, "max_seconds", float(seconds) if seconds else 0.0)

    def to_payload(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_payload(cls, payload):
        return cls(**_payload_values(payload, cls))


@dataclass(frozen=True, slots=True)
class CountRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    prior_id: str = PRIOR_ID
    limits: CountLimits = CountLimits()

    def __post_init__(self):
        grid = _grid(self.observation)
        if type(self.num_mines) is not int or not 0 <= self.num_mines <= len(grid) * len(grid[0]):
            raise ValueError("num_mines must be an integer within the board size")
        if type(self.prior_id) is not str or type(self.limits) is not CountLimits:
            raise TypeError("A string prior_id and CountLimits are required")
        object.__setattr__(self, "observation", grid)

    @property
    def problem_id(self):
        return _digest((MATH_VERSION, NORMALIZATION_POLICY, self.observation,
                        self.num_mines, self.prior_id))

    @property
    def request_id(self):
        return _digest((API_VERSION, self.to_payload()))

    def to_payload(self):
        return {"observation": self.observation, "num_mines": self.num_mines,
                "prior_id": self.prior_id, "limits": self.limits.to_payload()}

    @classmethod
    def from_payload(cls, payload):
        values = _payload_values(payload, cls)
        if "limits" in values:
            values["limits"] = CountLimits.from_payload(values["limits"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ComponentMemo:
    component: int
    entries_at_release: int
    scalars_at_release: int


@dataclass(frozen=True, slots=True)
class CountDiagnostics:
    forced_assignments: int
    branch_attempts: int
    dp_products: int
    preparation_visits: int
    constraint_visits: int
    constraint_cell_visits: int
    memo_operations: int
    histogram_updates: int
    publish_visits: int
    primary_work: int
    auxiliary_work: int
    units_total: int
    checkpoints: int
    elapsed_seconds: float
    last_stage: str
    blocked_family: str | None
    component_sizes: tuple[int, ...]
    floating_count: int | None
    memo_lookups: int
    memo_hits: int
    memo_stores: int
    memo_skips: int
    memo_entries_peak: int
    memo_scalars_peak: int
    component_memo: tuple[ComponentMemo, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class CountResult:
    problem_id: str
    request_id: str
    backend_version: str
    work_accounting_version: str
    status: str
    reason: str
    base: BaseResult
    diagnostics: CountDiagnostics

    def to_dict(self):
        return exact_json(self)


class _Stop(Exception):
    def __init__(self, status, reason, error=None):
        super().__init__(reason)
        self.status, self.reason, self.error = status, reason, error


class _Contradiction(Exception):
    pass


class _Budget:
    def __init__(self, limits, cancelled):
        self.started = perf_counter_ns()
        self.deadline = self.started + int(limits.max_seconds * 1_000_000_000)
        self.limits, self.cancelled = limits, cancelled
        self.units = dict.fromkeys(_PRIMARY + _AUXILIARY, 0)
        self.total = self.checkpoints = 0
        self.stage = "support"
        self.blocked = self.floating = None
        self.sizes = []
        self.components = []
        self.lookups = self.hits = self.stores = self.skips = 0
        self.peak_entries = self.peak_scalars = 0

    def check(self):
        self.checkpoints += 1
        if self.cancelled is not None:
            try:
                answer = self.cancelled()
                if type(answer) is not bool:
                    raise TypeError("Cancellation callback must return bool")
            except Exception as exc:
                raise _Stop("ERROR", "CANCEL_CALLBACK_ERROR", f"{type(exc).__name__}: {exc}") from exc
            if answer:
                raise _Stop("CANCELLED", "CANCELLED")
        if perf_counter_ns() >= self.deadline:
            raise _Stop("INSUFFICIENT", "TIME_LIMIT")

    def spend(self, family, amount=1):
        if type(amount) is not int or amount < 0:
            raise ValueError("Work amount must be a nonnegative integer")
        self.check()
        if self.total + amount > self.limits.max_total_work:
            self.blocked = family
            raise _Stop("INSUFFICIENT", "WORK_LIMIT")
        self.units[family] += amount
        self.total += amount

    def diagnostics(self, error):
        return CountDiagnostics(**self.units,
            primary_work=sum(self.units[k] for k in _PRIMARY),
            auxiliary_work=sum(self.units[k] for k in _AUXILIARY), units_total=self.total,
            checkpoints=self.checkpoints, elapsed_seconds=(perf_counter_ns()-self.started)/1e9,
            last_stage=self.stage, blocked_family=self.blocked, component_sizes=tuple(self.sizes),
            floating_count=self.floating, memo_lookups=self.lookups, memo_hits=self.hits,
            memo_stores=self.stores, memo_skips=self.skips, memo_entries_peak=self.peak_entries,
            memo_scalars_peak=self.peak_scalars, component_memo=tuple(self.components), error=error)


def _bits(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def _prepare(grid, budget):
    width, height = len(grid[0]), len(grid)
    closed, constraints, memberships = [], [], {}
    for y, row in enumerate(grid):
        budget.spend("preparation_visits", width)
        for x, clue in enumerate(row):
            if clue < 0:
                closed.append(y * width + x)
                continue
            xs = range(max(0, x-1), min(width, x+2))
            ys = range(max(0, y-1), min(height, y+2))
            budget.spend("preparation_visits", len(xs) * len(ys))
            mask = 0
            for ny in ys:
                for nx in xs:
                    if grid[ny][nx] < 0:
                        mask |= 1 << (ny * width + nx)
            if clue > mask.bit_count():
                raise _Contradiction
            if mask:
                index = len(constraints)
                constraints.append((mask, clue))
                budget.spend("constraint_cell_visits", mask.bit_count())
                for cell in _bits(mask):
                    memberships.setdefault(cell, []).append(index)

    components, floating = [], []
    seen_cells, seen_constraints = set(), set()
    budget.spend("preparation_visits", len(closed))
    for start in closed:
        if start not in memberships:
            floating.append(start)
            continue
        if start in seen_cells:
            continue
        pending, residual, free = [start], [], 0
        seen_cells.add(start)
        while pending:
            budget.spend("preparation_visits")
            cell = pending.pop()
            free |= 1 << cell
            budget.spend("preparation_visits", len(memberships[cell]))
            for index in memberships[cell]:
                if index in seen_constraints:
                    continue
                seen_constraints.add(index)
                mask, clue = constraints[index]
                residual.append((mask, clue))
                budget.spend("constraint_cell_visits", mask.bit_count())
                for neighbor in _bits(mask):
                    if neighbor not in seen_cells:
                        seen_cells.add(neighbor)
                        pending.append(neighbor)
        components.append((free, residual))
        budget.sizes.append(free.bit_count())
    budget.floating = len(floating)
    return closed, components, floating


def _canonical(residual, budget):
    unique = {}
    for mask, need in residual:
        budget.spend("constraint_visits")
        if not 0 <= need <= mask.bit_count() or (mask in unique and unique[mask] != need):
            raise _Contradiction
        if mask:
            unique[mask] = need
    budget.spend("constraint_visits", len(unique))
    return tuple(sorted(unique.items()))


def _propagate(free, residual, budget):
    assigned = ones = 0
    constraints = _canonical(residual, budget)
    while True:
        zero = one = 0
        budget.spend("constraint_visits", len(constraints))
        for mask, need in constraints:
            if need == 0:
                zero |= mask
            elif need == mask.bit_count():
                one |= mask
        if zero & one:
            raise _Contradiction
        forced = zero | one
        if not forced:
            return free, constraints, assigned, ones
        budget.spend("forced_assignments", forced.bit_count())
        free &= ~forced
        assigned |= forced
        ones |= one
        budget.spend("constraint_visits", len(constraints))
        reduced = [(mask & ~forced, need - (mask & one).bit_count()) for mask, need in constraints]
        constraints = _canonical(reduced, budget)


@dataclass(frozen=True, slots=True)
class _Counts:
    # Histograms are only mutated while building a new result, never after publication to memo.
    ways: dict
    mines: dict


def _lift(core, assigned, ones, budget):
    if not assigned or not core.ways:
        return core
    shift = ones.bit_count()

    def shifted(histogram):
        budget.spend("histogram_updates", len(histogram))
        return {k + shift: n for k, n in histogram.items()}

    ways = shifted(core.ways)
    budget.spend("histogram_updates", len(core.mines))
    mines = {cell: shifted(hist) for cell, hist in core.mines.items()}
    budget.spend("histogram_updates", assigned.bit_count())
    for cell in _bits(assigned):
        mines[cell] = ways if ones & (1 << cell) else {}
    return _Counts(ways, mines)


class _ComponentCounter:
    def __init__(self, budget):
        self.budget = budget
        limits = budget.limits
        self.memo = {} if limits.memo_entries and limits.memo_scalars else None
        self.scalars = 0

    def store(self, key, core):
        budget = self.budget
        budget.spend("memo_operations")  # capacity check, including an entry-cap skip
        if len(self.memo) >= budget.limits.memo_entries:
            budget.skips += 1
            return
        size = 1 + 2 * len(key[1]) + 2 * len(core.ways)
        budget.spend("memo_operations", size)
        for hist in core.mines.values():
            budget.spend("memo_operations")  # marginal cell
            terms = 2 * len(hist)
            budget.spend("memo_operations", terms)
            size += 1 + terms
        if self.scalars + size > budget.limits.memo_scalars:
            budget.skips += 1
            return
        budget.spend("memo_operations")
        self.memo[key] = core
        self.scalars += size
        budget.stores += 1
        budget.peak_entries = max(budget.peak_entries, len(self.memo))
        budget.peak_scalars = max(budget.peak_scalars, self.scalars)

    def solve(self, free, residual):
        budget = self.budget
        try:
            free, constraints, assigned, ones = _propagate(free, residual, budget)
        except _Contradiction:
            return _Counts({}, {})
        if self.memo is not None:
            budget.spend("memo_operations")
            key = free, constraints
            budget.lookups += 1
            core = self.memo.get(key)
            if core is not None:
                budget.hits += 1
                return _lift(core, assigned, ones, budget)
        if free:
            core = self.branch(free, constraints)
        else:
            budget.spend("histogram_updates")
            core = _Counts({0: 1}, {})
        if self.memo is not None:
            self.store(key, core)
        return _lift(core, assigned, ones, budget)

    def branch(self, free, constraints):
        budget = self.budget
        budget.spend("preparation_visits", free.bit_count())
        ranks = {cell: (481, 0) for cell in _bits(free)}
        budget.spend("constraint_visits", len(constraints))
        for mask, _ in constraints:
            size = mask.bit_count()
            budget.spend("constraint_cell_visits", size)
            for cell in _bits(mask):
                narrowest, negative_degree = ranks[cell]
                ranks[cell] = min(narrowest, size), negative_degree - 1
        budget.spend("preparation_visits", len(ranks))
        chosen = min(ranks, key=lambda cell: (ranks[cell], cell))
        bit = 1 << chosen
        budget.spend("histogram_updates", len(ranks))
        ways, mines = {}, {cell: {} for cell in ranks}
        for value in (0, 1):
            budget.spend("branch_attempts")
            mine_bit = bit if value else 0
            budget.spend("constraint_visits", len(constraints))
            reduced = [(mask & ~bit, need - bool(mask & mine_bit)) for mask, need in constraints]
            branch = _lift(self.solve(free & ~bit, reduced), bit, mine_bit, budget)
            budget.spend("histogram_updates", len(branch.ways))
            for k, n in branch.ways.items():
                ways[k] = ways.get(k, 0) + n
            budget.spend("histogram_updates", len(branch.mines))
            for cell, hist in branch.mines.items():
                target = mines[cell]
                budget.spend("histogram_updates", len(hist))
                for k, n in hist.items():
                    target[k] = target.get(k, 0) + n
        return _Counts(ways, mines)


def _convolve(left, right, budget):
    result = {}
    budget.spend("preparation_visits", len(left))
    for a, n in left.items():
        for b, m in right.items():
            budget.spend("dp_products")
            term = n * m
            budget.spend("histogram_updates")
            result[a+b] = result.get(a+b, 0) + term
    return result


def _weighted(ways, floating, mines, budget):
    total = 0
    for k, n in ways.items():
        budget.spend("preparation_visits")
        remaining = mines - k
        choices = comb(floating, remaining) if 0 <= remaining <= floating else 0
        budget.spend("dp_products")
        term = n * choices
        budget.spend("histogram_updates")
        total += term
    return total


def _base(request, budget):
    budget.stage = "prepare"
    closed, components, floating = _prepare(request.observation, budget)
    if request.num_mines > len(closed):
        raise _Contradiction
    counts = []
    for index, (free, constraints) in enumerate(components):
        budget.stage = f"component.{index}"
        budget.spend("preparation_visits")
        counter = _ComponentCounter(budget)
        try:
            local = counter.solve(free, constraints)
        finally:
            entries = len(counter.memo) if counter.memo is not None else 0
            budget.components.append(ComponentMemo(index, entries, counter.scalars))
            del counter  # Other components cannot reach its memo, even on interruption.
        if not local.ways:
            raise _Contradiction
        counts.append(local)

    budget.stage = "combine"
    prefix = [{0: 1}]
    budget.spend("preparation_visits", len(counts))
    for local in counts:
        prefix.append(_convolve(prefix[-1], local.ways, budget))
    budget.spend("preparation_visits", len(counts)+1)
    suffix = [None] * (len(counts)+1)
    suffix[-1] = {0: 1}
    budget.spend("preparation_visits", len(counts))
    for index in reversed(range(len(counts))):
        suffix[index] = _convolve(counts[index].ways, suffix[index+1], budget)
    denominator = _weighted(prefix[-1], len(floating), request.num_mines, budget)
    if not denominator:
        raise _Contradiction

    budget.stage = "marginals"
    mine_counts = {}
    budget.spend("preparation_visits", len(counts))
    for index, local in enumerate(counts):
        others = _convolve(prefix[index], suffix[index+1], budget)
        budget.spend("histogram_updates", len(local.ways))
        weights = {k: _weighted(others, len(floating), request.num_mines-k, budget) for k in local.ways}
        budget.spend("histogram_updates", len(local.mines))
        for cell, hist in local.mines.items():
            mine_count = 0
            for k, n in hist.items():
                budget.spend("dp_products")
                term = n * weights[k]
                budget.spend("histogram_updates")
                mine_count += term
            mine_counts[cell] = mine_count
    if floating:
        n = _weighted(prefix[-1], len(floating)-1, request.num_mines-1, budget)
        budget.spend("histogram_updates", len(floating))
        for cell in floating:
            mine_counts[cell] = n

    budget.stage = "publish.before"
    budget.check()
    budget.stage = "publish.rows"
    rows, sum_mines = [], 0
    width = len(request.observation[0])
    for cell in closed:
        budget.spend("publish_visits")
        n = mine_counts[cell]
        if not 0 <= n <= denominator:
            raise ArithmeticError("Marginal outside denominator")
        rows.append(CellCount((cell % width, cell // width), n, Fraction(n, denominator)))
        sum_mines += n
    if sum_mines != request.num_mines * denominator:
        raise ArithmeticError("Marginals do not conserve mine count")
    return BaseResult("EXACT", "PUBLIC_COUNTS", denominator, tuple(rows))


def count_base(request, *, cancelled=None):
    """Count every closed cell atomically, under this request's fresh budget."""
    if type(request) is not CountRequest:
        raise TypeError("CountRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable or None")
    budget = _Budget(request.limits, cancelled)
    problem_id, request_id = request.problem_id, request.request_id
    error = None
    try:
        if len(request.observation) * len(request.observation[0]) > request.limits.max_cells:
            raise _Stop("UNSUPPORTED", "CELL_LIMIT")
        if request.prior_id != PRIOR_ID:
            raise _Stop("UNSUPPORTED", "PRIOR_UNSUPPORTED")
        budget.stage = "start"
        budget.check()
        if request.limits.max_total_work == 0:
            raise _Stop("INSUFFICIENT", "WORK_LIMIT")
        try:
            base = _base(request, budget)
        except _Contradiction:
            budget.stage = "contradiction.final"
            budget.check()
            status, reason = "INCONSISTENT_INPUT", "NO_CONSISTENT_PLACEMENTS"
            base = BaseResult(status, reason, 0)
        else:
            budget.stage = "publish.final"
            budget.check()
            status, reason = "COMPLETE", "PUBLIC_COUNTS"
    except _Stop as stop:
        status, reason, error = stop.status, stop.reason, stop.error
        base = BaseResult(status, reason)
    except Exception as exc:
        status, reason, error = "ERROR", "INTERNAL_ERROR", f"{type(exc).__name__}: {exc}"
        base = BaseResult(status, reason)
    return CountResult(problem_id, request_id, BACKEND_VERSION, WORK_ACCOUNTING_VERSION,
                       status, reason, base, budget.diagnostics(error))
