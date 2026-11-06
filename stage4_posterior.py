"""Bounded integer-rank sampling of the uniform public posterior.

Only component histograms and requested component assignments are retained.
Physical flags are unknowns. No engine, actual layout, or board seed is read.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from math import comb, isfinite
from random import Random
from time import perf_counter

from stage4_belief import BeliefRequest, FLAGGED, HIDDEN, PRIOR_ID, exact_json


SAMPLER_ID = "INTEGER_RANK_POSTERIOR_V1"


def public_digest(value):
    encoded = json.dumps(exact_json(value), sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def neighbor_indices(width, height):
    return tuple(
        tuple(ny * width + nx
              for ny in range(max(0, y - 1), min(height, y + 2))
              for nx in range(max(0, x - 1), min(width, x + 2))
              if (nx, ny) != (x, y))
        for y in range(height) for x in range(width)
    )


@dataclass(frozen=True, slots=True)
class SamplerLimits:
    max_cells: int = 480
    max_work: int = 2_000_000
    max_seconds: float = 10.0

    def __post_init__(self):
        for name, cap in (("max_cells", 480), ("max_work", 2_000_000)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= cap:
                raise ValueError(f"{name} must be an integer in 0..{cap}")
        if (type(self.max_seconds) not in (int, float)
                or not isfinite(self.max_seconds) or not 0 <= self.max_seconds <= 10):
            raise ValueError("max_seconds must be finite and in 0..10")


@dataclass(frozen=True, slots=True)
class PosteriorRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    counted_inputs: int = 0
    planning_seed: int | str = 0
    samples: int = 16
    limits: SamplerLimits = SamplerLimits()

    def __post_init__(self):
        public = BeliefRequest(self.observation, self.num_mines)
        object.__setattr__(self, "observation", public.observation)
        object.__setattr__(self, "num_mines", public.num_mines)
        if type(self.counted_inputs) is not int or self.counted_inputs < 0:
            raise ValueError("counted_inputs must be a nonnegative integer")
        if type(self.planning_seed) not in (str, int):
            raise TypeError("planning_seed must be a public string or integer")
        if type(self.samples) is not int or not 0 <= self.samples <= 64:
            raise ValueError("samples must be in 0..64")
        if type(self.limits) is not SamplerLimits:
            raise TypeError("SamplerLimits required")

    @property
    def seed_id(self):
        normalized = tuple(tuple(HIDDEN if v == FLAGGED else v for v in row)
                           for row in self.observation)
        return public_digest((SAMPLER_ID, PRIOR_ID, normalized, self.num_mines,
                              self.counted_inputs, self.planning_seed))


@dataclass(frozen=True, slots=True)
class PosteriorSample:
    rank: int
    mines: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class SamplerDiagnostics:
    work: int
    work_by_stage: tuple[tuple[str, int], ...]
    checkpoints: int
    last_stage: str
    component_sizes: tuple[int, ...]
    histograms: tuple[tuple[tuple[int, int], ...], ...]
    floating_count: int
    recovered_assignments: int
    elapsed_seconds: float
    error: str | None


@dataclass(frozen=True, slots=True)
class PosteriorResult:
    status: str
    reason: str
    sampler_id: str
    seed_id: str
    total_worlds: int | None
    sampling_kind: str | None
    samples: tuple[PosteriorSample, ...]
    unique_layout_count: int
    diagnostics: SamplerDiagnostics

    def to_dict(self):
        return exact_json(self)


class _Stop(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class _Meter:
    def __init__(self, limits, cancelled):
        self.limits, self.cancelled = limits, cancelled
        self.started = perf_counter()
        self.work = self.checkpoints = 0
        self.stage = "prepare"
        self.counts = {name: 0 for name in
                       ("prepare", "histogram", "dp", "comb", "rng", "unrank", "recovery")}

    def check(self):
        self.checkpoints += 1
        if self.cancelled is not None:
            value = self.cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _Stop("CANCELLED", "CANCELLED")
        if perf_counter() - self.started >= self.limits.max_seconds:
            raise _Stop("INSUFFICIENT", "TIME_LIMIT")

    def tick(self, stage):
        self.stage = stage
        self.check()
        if self.work >= self.limits.max_work:
            raise _Stop("INSUFFICIENT", "WORK_LIMIT")
        self.work += 1
        self.counts[stage] += 1

    def choose(self, size, mines):
        self.tick("comb")
        value = comb(size, mines) if 0 <= mines <= size else 0
        self.check()
        return value


@dataclass(frozen=True, slots=True)
class _Component:
    cells: tuple[int, ...]
    constraints: tuple[tuple[tuple[int, ...], int], ...]


def _components(grid, meter):
    flat = tuple(v for row in grid for v in row)
    adjacent = neighbor_indices(len(grid[0]), len(grid))
    closed = tuple(i for i, value in enumerate(flat) if value < 0)
    constraints, memberships = [], {}
    for cell, clue in enumerate(flat):
        meter.tick("prepare")
        if clue < 0:
            continue
        cells = tuple(i for i in adjacent[cell] if flat[i] < 0)
        if clue > len(cells):
            raise _Stop("INCONSISTENT_INPUT", "NO_CONSISTENT_PLACEMENTS")
        if cells:
            index = len(constraints)
            constraints.append((cells, clue))
            for unknown in cells:
                memberships.setdefault(unknown, []).append(index)
    components, seen, seen_constraints = [], set(), set()
    for start in sorted(memberships):
        meter.check()
        if start in seen:
            continue
        pending, cells, indices = [start], [], []
        seen.add(start)
        while pending:
            meter.tick("prepare")
            cell = pending.pop()
            cells.append(cell)
            for index in memberships[cell]:
                if index in seen_constraints:
                    continue
                seen_constraints.add(index)
                indices.append(index)
                for other in constraints[index][0]:
                    if other not in seen:
                        pending.append(other)
                        seen.add(other)
        components.append(_Component(tuple(sorted(cells)),
                                     tuple(constraints[i] for i in sorted(indices))))
    return closed, tuple(components), tuple(i for i in closed if i not in memberships)


def _assignments(component, meter, stage):
    """Iterative bounded DFS. A leaf is transient, never a stored global world."""
    memberships = {cell: [] for cell in component.cells}
    for index, (cells, _) in enumerate(component.constraints):
        meter.check()
        for cell in cells:
            memberships[cell].append(index)
    ordered = sorted(component.cells, key=lambda cell: (-len(memberships[cell]), cell))
    incident = [memberships[cell] for cell in ordered]
    remaining = [len(cells) for cells, _ in component.constraints]
    target = [value for _, value in component.constraints]
    assigned = [0] * len(target)
    values = [0] * len(ordered)
    next_value = [0] * len(ordered)

    def update(depth, value, direction):
        for index in incident[depth]:
            assigned[index] += direction * value
            remaining[index] -= direction

    depth, mines = 0, 0
    while depth >= 0:
        meter.check()
        if next_value[depth] == 2:
            next_value[depth] = 0
            depth -= 1
            if depth >= 0:
                update(depth, values[depth], -1)
                mines -= values[depth]
            continue
        meter.tick(stage)
        value = next_value[depth]
        next_value[depth] += 1
        update(depth, value, 1)
        if any(assigned[i] > target[i] or assigned[i] + remaining[i] < target[i]
               for i in incident[depth]):
            update(depth, value, -1)
            continue
        values[depth] = value
        mines += value
        if depth + 1 == len(ordered):
            meter.check()
            cells = None
            if stage == "recovery":
                cells = tuple(cell for cell, present in zip(ordered, values) if present)
            yield mines, cells
            update(depth, value, -1)
            mines -= value
        else:
            depth += 1


def _floating_unrank(cells, remaining, rank, meter):
    selected = []
    for offset, cell in enumerate(cells):
        meter.tick("unrank")
        if remaining == 0:
            break
        block = meter.choose(len(cells) - offset - 1, remaining - 1)
        if rank < block:
            selected.append(cell)
            remaining -= 1
        else:
            rank -= block
    if remaining or rank:
        raise ValueError("Invalid floating rank")
    return tuple(selected)


def sample_posterior(request, *, cancelled=None, ranks=None):
    """Sample with replacement, or enumerate all worlds when D <= N.

    Explicit ranks are a bounded diagnostic interface. Their order and repeats
    are preserved and clearly labelled separately from random sampling.
    """
    if type(request) is not PosteriorRequest:
        raise TypeError("PosteriorRequest required")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable")
    if ranks is not None:
        if (type(ranks) not in (tuple, list) or len(ranks) > 64
                or any(type(rank) is not int or rank < 0 for rank in ranks)):
            raise ValueError("Explicit ranks must contain at most 64 nonnegative integers")
        ranks = tuple(ranks)
    meter = _Meter(request.limits, cancelled)
    components, histograms, floating = (), [], ()
    denominator, kind, bank, error = None, None, (), None
    recovered_count = 0
    status, reason = "COMPLETE", "UNIFORM_PUBLIC_POSTERIOR"
    try:
        meter.check()
        if len(request.observation) * len(request.observation[0]) > request.limits.max_cells:
            raise _Stop("UNSUPPORTED", "CELL_LIMIT")
        closed, components, floating = _components(request.observation, meter)
        if request.num_mines > len(closed):
            raise _Stop("INCONSISTENT_INPUT", "NO_CONSISTENT_PLACEMENTS")
        for component in components:
            histogram = {}
            for mines, _ in _assignments(component, meter, "histogram"):
                histogram[mines] = histogram.get(mines, 0) + 1
            if not histogram:
                raise _Stop("INCONSISTENT_INPUT", "NO_CONSISTENT_PLACEMENTS")
            histograms.append(dict(sorted(histogram.items())))
        suffix = [{} for _ in range(len(components) + 1)]
        suffix[-1] = {k: meter.choose(len(floating), k)
                      for k in range(min(len(floating), request.num_mines) + 1)}
        for index in range(len(components) - 1, -1, -1):
            for mines, count in histograms[index].items():
                for rest, ways in suffix[index + 1].items():
                    meter.tick("dp")
                    total = mines + rest
                    if total <= request.num_mines:
                        suffix[index][total] = suffix[index].get(total, 0) + count * ways
        denominator = suffix[0].get(request.num_mines, 0)
        if denominator == 0:
            raise _Stop("INCONSISTENT_INPUT", "NO_CONSISTENT_PLACEMENTS")
        if ranks is not None:
            kind = "EXPLICIT_RANKS"
            if any(rank >= denominator for rank in ranks):
                raise ValueError("Explicit rank is outside the posterior")
        elif denominator <= request.samples:
            kind, ranks = "SMALL_POSTERIOR_ENUMERATED", tuple(range(denominator))
        else:
            kind = "WITH_REPLACEMENT"
            generator = Random(int(request.seed_id, 16))
            drawn = []
            for _ in range(request.samples):
                meter.tick("rng")
                drawn.append(generator.randrange(denominator))
                meter.check()
            ranks = tuple(drawn)
        if not ranks:
            raise _Stop("INSUFFICIENT", "NO_SAMPLES")
        requests = [set() for _ in components]
        decoded = []
        for rank in ranks:
            remainder, rest_rank, picks = request.num_mines, rank, []
            for index, histogram in enumerate(histograms):
                for mines, count in histogram.items():
                    meter.tick("unrank")
                    ways = suffix[index + 1].get(remainder - mines, 0)
                    block = count * ways
                    if rest_rank >= block:
                        rest_rank -= block
                        continue
                    assignment, rest_rank = divmod(rest_rank, ways)
                    pick = (mines, assignment)
                    picks.append(pick)
                    requests[index].add(pick)
                    remainder -= mines
                    break
                else:
                    raise ValueError("Invalid component rank")
            tail = _floating_unrank(floating, remainder, rest_rank, meter)
            decoded.append((tuple(picks), tail))
        recovered = []
        for index, component in enumerate(components):
            wanted, found, counts = requests[index], {}, {}
            for mines, cells in _assignments(component, meter, "recovery"):
                occurrence = counts.get(mines, 0)
                counts[mines] = occurrence + 1
                key = (mines, occurrence)
                if key in wanted:
                    found[key] = cells
                    recovered_count += 1
                if len(found) == len(wanted):
                    break
            if len(found) != len(wanted):
                raise ValueError("Histogram/recovery mismatch")
            recovered.append(found)
        width = len(request.observation[0])
        result = []
        for rank, (picks, tail) in zip(ranks, decoded):
            meter.check()
            cells = list(tail)
            for index, pick in enumerate(picks):
                cells.extend(recovered[index][pick])
            if len(cells) != request.num_mines or len(set(cells)) != len(cells):
                raise ValueError("Decoded layout has an invalid mine count")
            result.append(PosteriorSample(rank, tuple((i % width, i // width) for i in sorted(cells))))
        meter.check()
        bank = tuple(result)
    except _Stop as exc:
        status, reason = exc.status, exc.reason
        if status == "INCONSISTENT_INPUT":
            denominator = 0
    except Exception as exc:
        status, reason, error = "ERROR", "SAMPLER_ERROR", f"{type(exc).__name__}: {exc}"
    diagnostics = SamplerDiagnostics(
        meter.work, tuple(meter.counts.items()), meter.checkpoints, meter.stage,
        tuple(len(c.cells) for c in components),
        tuple(tuple(h.items()) for h in histograms), len(floating), recovered_count,
        perf_counter() - meter.started, error)
    return PosteriorResult(status, reason, SAMPLER_ID, request.seed_id, denominator,
                           kind, bank, len({sample.rank for sample in bank}), diagnostics)
