"""Interruptible exact counts from public Minesweeper observations.

Only opened clues and the public total mine count constrain the uniform prior.
Physical flags remain in request identity and are ordinary unknowns for counting.
The component histogram / prefix-suffix construction follows simple_probability,
with checkpoints inside enumeration and every integer DP term multiplication.
No complete-board assignments, cross-component assignment products, persistent
cache, sampling, engine input, or executable decisions are used here.

A single request budget covers base marginals and all canonical joint events.
Work counts each attempted component variable value and each DP term product.
Checks also bracket bounded preparation, leaf accumulation, and publication.
The monotonic time limit is cooperative. Serialization is outside that limit.
"""

from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
from hashlib import sha256
import json
from math import comb, isfinite
from time import monotonic


HIDDEN = -2
FLAGGED = -3
PRIOR_ID = "uniform_consistent_placements_v1"
NORMALIZATION_POLICY = "physical_flags_as_hidden_v1"
COUNTER_VERSION = "bounded_public_counts_v1"
Coordinate = tuple[int, int]


def exact_json(value):
    """Lossless evidence encoding, with decimal strings for every integer."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Fraction):
        return {"numerator": str(value.numerator), "denominator": str(value.denominator)}
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return value
    if is_dataclass(value):
        return {field.name: exact_json(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): exact_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact_json(item) for item in value]
    raise TypeError("Unsupported evidence value")


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _grid(observation):
    if type(observation) not in (list, tuple) or not observation:
        raise ValueError("A nonempty rectangular public grid is required")
    rows = []
    width = None
    for row in observation:
        if type(row) not in (list, tuple) or not row:
            raise ValueError("Rows must be nonempty lists or tuples")
        if width is None:
            width = len(row)
        if len(row) != width:
            raise ValueError("Public grid must be rectangular")
        if any(not _integer(v) or (v not in (HIDDEN, FLAGGED) and not 0 <= v <= 8)
               for v in row):
            raise ValueError("Unsupported public cell value")
        rows.append(tuple(int(v) for v in row))
    return tuple(rows)


def _cells(values):
    if type(values) not in (list, tuple):
        raise TypeError("Event cells must be a list or tuple")
    result = set()
    for cell in values:
        if type(cell) not in (list, tuple) or len(cell) != 2 or not all(map(_integer, cell)):
            raise ValueError("Coordinates must be integer (x, y) pairs")
        result.add((int(cell[0]), int(cell[1])))
    return tuple(sorted(result, key=lambda cell: (cell[1], cell[0])))


def _in_bounds(cell, grid):
    if not (0 <= cell[0] < len(grid[0]) and 0 <= cell[1] < len(grid)):
        raise ValueError("Event coordinate is outside the observation")


@dataclass(frozen=True, slots=True)
class EventQuery:
    safe_cells: tuple[Coordinate, ...] = ()
    mine_cells: tuple[Coordinate, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "safe_cells", _cells(self.safe_cells))
        object.__setattr__(self, "mine_cells", _cells(self.mine_cells))


def _event_key(event):
    return (tuple((y, x) for x, y in event.safe_cells),
            tuple((y, x) for x, y in event.mine_cells))


@dataclass(frozen=True, slots=True)
class BeliefLimits:
    max_cells: int = 480
    max_events: int = 16
    max_work: int = 200_000
    max_seconds: float = 2.0

    def __post_init__(self):
        for name, cap in (("max_cells", 480), ("max_events", 16), ("max_work", 200_000)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= cap:
                raise ValueError(f"{name} must be an integer in 0..{cap}")
        if (type(self.max_seconds) not in (int, float) or not isfinite(self.max_seconds)
                or not 0 <= self.max_seconds <= 2.0):
            raise ValueError("max_seconds must be finite and in 0..2")
        object.__setattr__(self, "max_seconds", float(self.max_seconds))


@dataclass(frozen=True, slots=True)
class BeliefRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    events: tuple[EventQuery, ...] = ()
    limits: BeliefLimits = BeliefLimits()
    prior_id: str = PRIOR_ID

    def __post_init__(self):
        grid = _grid(self.observation)
        if not _integer(self.num_mines) or not 0 <= self.num_mines <= len(grid) * len(grid[0]):
            raise ValueError("Total mines must be an integer within the board size")
        if type(self.limits) is not BeliefLimits or type(self.prior_id) is not str:
            raise TypeError("Explicit BeliefLimits and a string prior ID are required")
        if type(self.events) not in (list, tuple) or any(type(e) is not EventQuery for e in self.events):
            raise TypeError("Events must contain only EventQuery objects")
        for event in self.events:
            for cell in event.safe_cells + event.mine_cells:
                _in_bounds(cell, grid)
        object.__setattr__(self, "observation", grid)
        object.__setattr__(self, "num_mines", int(self.num_mines))
        object.__setattr__(self, "events", tuple(sorted(set(self.events), key=_event_key)))

    @property
    def identity(self):
        content = (COUNTER_VERSION, NORMALIZATION_POLICY, self)
        encoded = json.dumps(exact_json(content), sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()

    def to_payload(self):
        """Input representation with ordinary small integers, suitable for replay."""
        return {"observation": self.observation, "num_mines": self.num_mines,
                "events": [{"safe_cells": e.safe_cells, "mine_cells": e.mine_cells} for e in self.events],
                "limits": {f.name: getattr(self.limits, f.name) for f in fields(self.limits)},
                "prior_id": self.prior_id}

    @classmethod
    def from_payload(cls, payload):
        if type(payload) is not dict or set(payload) - {field.name for field in fields(cls)}:
            raise ValueError("Unknown public request fields or invalid payload")
        values = dict(payload)
        if "events" in values:
            if type(values["events"]) not in (list, tuple):
                raise TypeError("Events must be a list or tuple")
            if any(type(e) is not dict for e in values["events"]):
                raise TypeError("Event payloads must be dictionaries")
            values["events"] = tuple(EventQuery(**event) for event in values["events"])
        if "limits" in values:
            if type(values["limits"]) is not dict:
                raise TypeError("Limits payload must be a dictionary")
            values["limits"] = BeliefLimits(**values["limits"])
        return cls(**values)


def _neighbors(cell, grid):
    x, y = cell
    return tuple((nx, ny)
                 for ny in range(max(0, y - 1), min(len(grid), y + 2))
                 for nx in range(max(0, x - 1), min(len(grid[0]), x + 2))
                 if (nx, ny) != cell)


def zero_event(observation, cell):
    """Joint safety of a center and its neighbors, including opened/flagged centers."""
    grid = _grid(observation)
    cell = _cells([cell])[0]
    _in_bounds(cell, grid)
    return EventQuery((cell,) + _neighbors(cell, grid))


def existing_chord_event(observation, cell):
    """Joint safety of actual HIDDEN targets, or None for an ineffective CHORD."""
    grid = _grid(observation)
    cell = _cells([cell])[0]
    _in_bounds(cell, grid)
    number = grid[cell[1]][cell[0]]
    neighbors = _neighbors(cell, grid)
    flags = sum(grid[y][x] == FLAGGED for x, y in neighbors)
    targets = tuple((x, y) for x, y in neighbors if grid[y][x] == HIDDEN)
    if number <= 0 or flags != number or not targets:
        return None
    return EventQuery(targets)


@dataclass(frozen=True, slots=True)
class CellCount:
    coordinate: Coordinate
    mine_worlds: int
    probability: Fraction


@dataclass(frozen=True, slots=True)
class BaseResult:
    status: str
    reason: str
    total_worlds: int | None = None
    marginals: tuple[CellCount, ...] | None = None


@dataclass(frozen=True, slots=True)
class EventResult:
    event: EventQuery
    status: str = "NOT_EVALUATED"
    reason: str = "BASE_NOT_EXACT"
    event_worlds: int | None = None
    probability: Fraction | None = None


@dataclass(frozen=True, slots=True)
class StageTrace:
    stage: str
    status: str
    reason: str
    work_start: int
    work_end: int
    elapsed_start: float
    elapsed_end: float
    checkpoints_start: int
    checkpoints_end: int


@dataclass(frozen=True, slots=True)
class Diagnostics:
    work: int
    elapsed_seconds: float
    checkpoints: int
    last_checkpoint: str
    component_sizes: tuple[int, ...]
    unconstrained_count: int | None
    stages: tuple[StageTrace, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class BeliefResult:
    request_id: str
    status: str
    reason: str
    base: BaseResult
    events: tuple[EventResult, ...]
    diagnostics: Diagnostics

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
        self.limits = limits
        self.cancelled = cancelled
        self.started = monotonic()
        self.elapsed = 0.0
        self.work = 0
        self.checkpoints = 0
        self.current_stage = "request"
        self.last_checkpoint = "NOT_STARTED"
        self.traces = []
        self.component_sizes = ()
        self.unconstrained_count = None
        self.error = None

    def check(self):
        self.checkpoints += 1
        self.last_checkpoint = self.current_stage
        if self.cancelled is not None:
            try:
                cancelled = self.cancelled()
                if type(cancelled) is not bool:
                    raise TypeError("Cancellation callback must return bool")
            except Exception as exc:
                self.elapsed = monotonic() - self.started
                raise _Stop("ERROR", "CANCEL_CALLBACK_ERROR", f"{type(exc).__name__}: {exc}") from exc
            self.elapsed = monotonic() - self.started
            if cancelled:
                raise _Stop("CANCELLED", "CANCELLED")
        else:
            self.elapsed = monotonic() - self.started
        if self.elapsed >= self.limits.max_seconds:
            raise _Stop("INSUFFICIENT", "TIME_LIMIT")

    def tick(self):
        self.check()
        if self.work >= self.limits.max_work:
            raise _Stop("INSUFFICIENT", "WORK_LIMIT")
        self.work += 1

    def product(self, left, right):
        self.tick()
        return left * right

    @contextmanager
    def stage(self, name):
        self.current_stage = name
        work, elapsed, checkpoints = self.work, self.elapsed, self.checkpoints
        status, reason = "COMPLETE", "FINISHED"
        try:
            self.check()
            yield
            self.check()
        except _Stop as exc:
            status, reason = exc.status, exc.reason
            self.error = exc.error
            raise
        except _Contradiction:
            status, reason = "INCONSISTENT_INPUT", "NO_CONSISTENT_PLACEMENTS"
            try:
                self.check()
            except _Stop as exc:
                status, reason = exc.status, exc.reason
                self.error = exc.error
                raise
            raise
        except Exception as exc:
            status, reason = "ERROR", "INTERNAL_ERROR"
            self.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.traces.append(StageTrace(name, status, reason, work, self.work,
                                          elapsed, self.elapsed, checkpoints, self.checkpoints))

    def diagnostics(self):
        return Diagnostics(self.work, self.elapsed, self.checkpoints, self.last_checkpoint,
                           self.component_sizes, self.unconstrained_count, tuple(self.traces), self.error)


@dataclass(frozen=True, slots=True)
class _Component:
    cells: tuple[int, ...]
    constraints: tuple[tuple[tuple[int, ...], int], ...]


def _prepare(grid, budget):
    width = len(grid[0])
    closed = tuple(y * width + x for y, row in enumerate(grid)
                   for x, value in enumerate(row) if value < 0)
    constraints = []
    memberships = {}
    for y, row in enumerate(grid):
        budget.check()
        for x, value in enumerate(row):
            if value < 0:
                continue
            cells = tuple(ny * width + nx for nx, ny in _neighbors((x, y), grid) if grid[ny][nx] < 0)
            if value > len(cells):
                raise _Contradiction
            if cells:
                index = len(constraints)
                constraints.append((cells, value))
                for cell in cells:
                    memberships.setdefault(cell, []).append(index)
    components = []
    seen_cells, seen_constraints = set(), set()
    for start in sorted(memberships):
        if start in seen_cells:
            continue
        pending, cells, indices = [start], [], []
        seen_cells.add(start)
        while pending:
            budget.check()
            cell = pending.pop()
            cells.append(cell)
            for index in memberships[cell]:
                if index in seen_constraints:
                    continue
                seen_constraints.add(index)
                indices.append(index)
                for neighbor in constraints[index][0]:
                    if neighbor not in seen_cells:
                        pending.append(neighbor)
                        seen_cells.add(neighbor)
        components.append(_Component(tuple(sorted(cells)), tuple(constraints[i] for i in sorted(indices))))
    floating = tuple(cell for cell in closed if cell not in memberships)
    budget.component_sizes = tuple(len(component.cells) for component in components)
    budget.unconstrained_count = len(floating)
    return closed, tuple(components), floating


def _enumerate(component, forced, budget, *, marginals):
    memberships = {cell: [] for cell in component.cells}
    for index, (cells, _) in enumerate(component.constraints):
        for cell in cells:
            memberships[cell].append(index)
    ordered = sorted(component.cells, key=lambda cell: (-len(memberships[cell]), cell))
    incident = [memberships[cell] for cell in ordered]
    choices = [(forced[cell],) if cell in forced else (0, 1) for cell in ordered]
    targets = [value for _, value in component.constraints]
    remaining = [len(cells) for cells, _ in component.constraints]
    assigned = [0] * len(targets)
    values = [0] * len(ordered)
    next_choice = [0] * len(ordered)
    ways = {}
    mine_ways = {cell: {} for cell in component.cells} if marginals else {}

    def update(depth, value, direction):
        for index in incident[depth]:
            assigned[index] += direction * value
            remaining[index] -= direction

    depth, mines = 0, 0
    while depth >= 0:
        budget.check()
        if next_choice[depth] == len(choices[depth]):
            next_choice[depth] = 0
            depth -= 1
            if depth >= 0:
                update(depth, values[depth], -1)
                mines -= values[depth]
            continue
        budget.tick()
        value = choices[depth][next_choice[depth]]
        next_choice[depth] += 1
        update(depth, value, 1)
        if any(assigned[i] > targets[i] or assigned[i] + remaining[i] < targets[i]
               for i in incident[depth]):
            update(depth, value, -1)
            continue
        values[depth] = value
        mines += value
        if depth + 1 == len(ordered):
            budget.check()
            ways[mines] = ways.get(mines, 0) + 1
            if marginals:
                for cell, is_mine in zip(ordered, values):
                    if is_mine:
                        histogram = mine_ways[cell]
                        histogram[mines] = histogram.get(mines, 0) + 1
            budget.check()
            update(depth, value, -1)
            mines -= value
        else:
            depth += 1
    return dict(sorted(ways.items())), mine_ways


def _convolve(left, right, budget):
    result = {}
    for a, count_a in left.items():
        for b, count_b in right.items():
            result[a + b] = result.get(a + b, 0) + budget.product(count_a, count_b)
    return dict(sorted(result.items()))


def _choose(cells, mines):
    return comb(cells, mines) if 0 <= mines <= cells else 0


def _weighted(ways, floating, mines, budget):
    return sum(budget.product(count, _choose(floating, mines - k)) for k, count in ways.items())


def _base(request, budget):
    with budget.stage("base.prepare"):
        closed, components, floating = _prepare(request.observation, budget)
        if request.num_mines > len(closed):
            raise _Contradiction
    counts = []
    for index, component in enumerate(components):
        with budget.stage(f"base.component.{index}"):
            ways, mine_ways = _enumerate(component, {}, budget, marginals=True)
            if not ways:
                raise _Contradiction
            counts.append((ways, mine_ways))
    with budget.stage("base.combine"):
        prefix = [{0: 1}]
        for ways, _ in counts:
            prefix.append(_convolve(prefix[-1], ways, budget))
        suffix = [{} for _ in range(len(counts) + 1)]
        suffix[-1] = {0: 1}
        for index in range(len(counts) - 1, -1, -1):
            suffix[index] = _convolve(counts[index][0], suffix[index + 1], budget)
        denominator = _weighted(prefix[-1], len(floating), request.num_mines, budget)
        if denominator == 0:
            raise _Contradiction
    with budget.stage("base.marginals"):
        mine_counts = {}
        for index, (ways, mine_ways) in enumerate(counts):
            others = _convolve(prefix[index], suffix[index + 1], budget)
            weights = {k: _weighted(others, len(floating), request.num_mines - k, budget) for k in ways}
            for cell, histogram in mine_ways.items():
                mine_counts[cell] = sum(budget.product(count, weights[k]) for k, count in histogram.items())
        if floating:
            count = _weighted(prefix[-1], len(floating) - 1, request.num_mines - 1, budget)
            mine_counts.update((cell, count) for cell in floating)
    with budget.stage("base.publish"):
        width = len(request.observation[0])
        marginals = tuple(CellCount((cell % width, cell // width), mine_counts[cell],
                                   Fraction(mine_counts[cell], denominator)) for cell in closed)
        result = BaseResult("EXACT", "PUBLIC_COUNTS", denominator, marginals)
    return result, components, floating, counts


def _event_count(event, index, request, denominator, components, floating, counts, budget):
    with budget.stage(f"event.{index}.prepare"):
        grid = request.observation
        width = len(grid[0])
        impossible = bool(set(event.safe_cells) & set(event.mine_cells))
        impossible = impossible or any(grid[y][x] >= 0 for x, y in event.mine_cells)
        forced = {y * width + x: 0 for x, y in event.safe_cells if grid[y][x] < 0}
        forced.update((y * width + x, 1) for x, y in event.mine_cells)
    if impossible:
        return 0
    if not forced:
        return denominator
    conditioned = []
    # Reused base histograms are local to this immutable public request and version.
    # Changed components are independently recounted under their joint conditions.
    for component_index, component in enumerate(components):
        budget.check()
        local = {cell: forced[cell] for cell in component.cells if cell in forced}
        if local:
            with budget.stage(f"event.{index}.component.{component_index}"):
                ways, _ = _enumerate(component, local, budget, marginals=False)
            if not ways:
                return 0
        else:
            ways = counts[component_index][0]
        conditioned.append(ways)
    with budget.stage(f"event.{index}.combine"):
        floating_conditions = [forced[cell] for cell in floating if cell in forced]
        free = len(floating) - len(floating_conditions)
        remaining_mines = request.num_mines - sum(floating_conditions)
        ways = {0: 1}
        for histogram in conditioned:
            ways = _convolve(ways, histogram, budget)
        numerator = _weighted(ways, free, remaining_mines, budget)
    return numerator


def count_public(request, *, cancelled=None):
    """Return COMPLETE, INCONSISTENT_INPUT, INSUFFICIENT, CANCELLED, ERROR or PARTIAL.

    Base counts are published atomically only after all marginals finish. PARTIAL
    preserves that exact base and completed events. Every unfinished count and
    probability is None. Unsupported prior/size/event count has UNSUPPORTED status.
    Malformed input is rejected by the DTO, before calculation starts.
    """
    if type(request) is not BeliefRequest:
        raise TypeError("BeliefRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be a callable or None")
    budget = _Budget(request.limits, cancelled)
    identity = request.identity
    events = [EventResult(event) for event in request.events]
    base = BaseResult("NOT_EVALUATED", "NOT_STARTED")

    def result(status, reason):
        return BeliefResult(identity, status, reason, base, tuple(events), budget.diagnostics())

    unsupported = None
    if len(request.observation) * len(request.observation[0]) > request.limits.max_cells:
        unsupported = "CELL_LIMIT"
    elif len(request.events) > request.limits.max_events:
        unsupported = "EVENT_LIMIT"
    elif request.prior_id != PRIOR_ID:
        unsupported = "PRIOR_UNSUPPORTED"
    if unsupported:
        base = BaseResult("UNSUPPORTED", unsupported)
        return result("UNSUPPORTED", unsupported)
    try:
        base, components, floating, counts = _base(request, budget)
    except _Contradiction:
        base = BaseResult("INCONSISTENT_INPUT", "NO_CONSISTENT_PLACEMENTS", 0)
        return result("INCONSISTENT_INPUT", base.reason)
    except _Stop as exc:
        base = BaseResult(exc.status, exc.reason)
        return result(exc.status, exc.reason)
    except Exception as exc:
        budget.error = f"{type(exc).__name__}: {exc}"
        base = BaseResult("ERROR", "INTERNAL_ERROR")
        return result("ERROR", base.reason)
    events = [EventResult(event, reason="PREVIOUS_EVENT_UNFINISHED") for event in request.events]
    for index, event in enumerate(request.events):
        try:
            numerator = _event_count(event, index, request, base.total_worlds,
                                     components, floating, counts, budget)
            with budget.stage(f"event.{index}.publish"):
                row = EventResult(event, "EXACT", "IMPOSSIBLE_EVENT" if numerator == 0 else "PUBLIC_COUNTS",
                                  numerator, Fraction(numerator, base.total_worlds))
            events[index] = row
        except _Stop as exc:
            events[index] = EventResult(event, exc.status, exc.reason)
            return result("PARTIAL", exc.reason)
        except Exception as exc:
            budget.error = f"{type(exc).__name__}: {exc}"
            events[index] = EventResult(event, "ERROR", "INTERNAL_ERROR")
            return result("PARTIAL", "INTERNAL_ERROR")
    return result("COMPLETE", "PUBLIC_COUNTS")
