"""Exact, bounded planning over public, already-placed Minesweeper positions.

The declared family is ``progress_preparations_v1``. At each information state
it compares every direct OPEN (including an unflag first), every existing
effective CHORD, and every final neighbor-flag arrangement for a CHORD with
at least two targets. Preparation toggles occur once each in reading order.
Every toggle consumes a separate input and depth unit. Flags outside that
CHORD's neighborhood are left alone. A continuation is selected only after
grouping worlds by their complete public result. Only the first actual input
is returned. Call again with the new public observation and ledger.

This finite family omits advance flags unrelated to the next reveal, edited
one-target chords, no-op inputs, certain-fatal reveals, and flag-only cycles.
No-op inputs and cycles preserve information while increasing C. Delaying
unrelated flag work until it is needed also avoids paying for work erased by
an opening. These exclusions are explicit, rather than an exhaustive-policy
optimality claim. Existing one-target chords remain in the family.

Uniform weight on all placements consistent with the public clues and total
mine count is the sole prior. Physical flags are never inference constraints.
Virtual worlds are internal products of enumeration, never API inputs.
There is no persistent cache. A call-local cache binds the complete public
request, observation, C, and remaining atomic depth. Cutoffs abort ranking.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from math import isfinite
from time import monotonic

from simple_algorithm import InconsistentObservationError
from simple_probability import calculate_probabilities
from stage4_opening import OpeningEvidence


HIDDEN = -2
FLAGGED = -3
PRIOR_ID = "uniform_consistent_placements_v1"
FAMILY_ID = "progress_preparations_v1"
ACTION_ORDER = {"OPEN": 0, "CHORD": 1, "FLAG": 2}
EXCLUSIONS = (
    "NO_OP_INPUTS_AND_FLAG_ONLY_CYCLES",
    "ADVANCE_FLAGS_UNRELATED_TO_NEXT_REVEAL",
    "EDITED_CHORD_WITH_FEWER_THAN_TWO_TARGETS",
    "CERTAIN_FATAL_REVEALS",
    "NONCANONICAL_PREPARATION_PERMUTATIONS",
)


def exact_json(value):
    """JSON-safe public evidence. All integers use decimal strings."""
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


def _digest(value):
    encoded = json.dumps(exact_json(value), sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _grid(observation, *, terminal=False):
    if type(observation) not in (tuple, list) or not observation:
        raise ValueError("A nonempty public grid is required")
    rows = []
    width = None
    allowed = (HIDDEN, FLAGGED, -4, -5, -6) if terminal else (HIDDEN, FLAGGED)
    for row in observation:
        if type(row) not in (tuple, list) or not row:
            raise ValueError("Public rows must be nonempty lists or tuples")
        if width is None:
            width = len(row)
        if len(row) != width:
            raise ValueError("Public grid must be rectangular")
        if any(type(v) is not int or (v not in allowed and not 0 <= v <= 8) for v in row):
            raise ValueError("Unsupported public cell value")
        rows.append(tuple(row))
    return tuple(rows)


def public_observation_id(observation, num_mines):
    """Derive identity solely from public cells and total mines, including loss displays."""
    return _digest((_grid(observation, terminal=True), num_mines))


def _is_id(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True, slots=True)
class Move:
    action: str
    x: int
    y: int

    def __post_init__(self):
        if self.action not in ACTION_ORDER or any(type(v) is not int for v in (self.x, self.y)):
            raise ValueError("Move requires OPEN/CHORD/FLAG and integer coordinates")


@dataclass(frozen=True, slots=True)
class PublicInput:
    action: str
    x: int
    y: int
    counted: bool
    observation_id: str

    def __post_init__(self):
        if self.action not in (*ACTION_ORDER, "UNKNOWN"):
            raise ValueError("Unsupported ledger action")
        if any(type(v) is not int for v in (self.x, self.y)) or type(self.counted) is not bool:
            raise ValueError("Invalid public input fields")
        if not _is_id(self.observation_id) or (self.action == "UNKNOWN" and self.counted):
            raise ValueError("Invalid public input identity or count")


def record_input(ledger, action, x, y, observation, num_mines, *, playing, delivered=True):
    """Append a public receipt using pre-delivery lifecycle and post-input cells.

    A valid, delivered in-board input while PLAYING is counted even if it has
    no effect. Terminal and rejected attempts can be retained as uncounted
    public receipts. No engine counters or cell classifications are read.
    """
    grid = _grid(observation, terminal=True)
    if type(playing) is not bool or type(delivered) is not bool:
        raise ValueError("Lifecycle and delivery must be booleans")
    if any(type(v) is not int for v in (x, y)):
        raise ValueError("Coordinates must be integers")
    known = action in ACTION_ORDER
    counted = playing and delivered and known and 0 <= y < len(grid) and 0 <= x < len(grid[0])
    item = PublicInput(action if known else "UNKNOWN", x, y, counted,
                       public_observation_id(grid, num_mines))
    return tuple(ledger) + (item,)


@dataclass(frozen=True, slots=True)
class Limits:
    max_cells: int = 64
    max_closed: int = 8
    max_worlds: int = 256
    max_depth: int = 12
    max_nodes: int = 50_000
    max_seconds: float = 10.0

    def __post_init__(self):
        caps = {"max_cells": 64, "max_closed": 8, "max_worlds": 256,
                "max_depth": 12, "max_nodes": 50_000}
        for name, cap in caps.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= cap:
                raise ValueError(f"{name} must be an integer in 0..{cap}")
        if (type(self.max_seconds) not in (int, float) or not isfinite(self.max_seconds)
                or not 0 <= self.max_seconds <= 10):
            raise ValueError("max_seconds must be finite and in 0..10")


def _target(value):
    if value is None:
        return None
    if type(value) not in (int, str, Fraction):
        raise ValueError("Target must be an exact integer, fraction string, or Fraction")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid exact target") from exc
    if result <= 0:
        raise ValueError("Target must be positive")
    return result


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    observation: tuple[tuple[int, ...], ...]
    num_mines: int
    ledger: tuple[PublicInput, ...] = ()
    mode: str = "S"
    allow_guess: bool = False
    target: Fraction | None = None
    limits: Limits = Limits()
    prior_id: str = PRIOR_ID
    observation_id: str | None = None

    def __post_init__(self):
        grid = _grid(self.observation)
        if type(self.num_mines) is not int or not 0 <= self.num_mines < len(grid) * len(grid[0]):
            raise ValueError("Total mines must be a valid public count")
        if type(self.ledger) not in (tuple, list) or any(type(v) is not PublicInput for v in self.ledger):
            raise ValueError("Ledger must contain only PublicInput receipts")
        if self.mode not in ("S", "M", "R") or type(self.allow_guess) is not bool:
            raise ValueError("Invalid mode or guess setting")
        if type(self.limits) is not Limits or type(self.prior_id) is not str:
            raise ValueError("Explicit Limits and a prior ID are required")
        identity = public_observation_id(grid, self.num_mines)
        if self.observation_id is not None and self.observation_id != identity:
            raise ValueError("Observation ID must match the canonical public identity")
        if self.ledger and self.ledger[-1].observation_id != identity:
            raise ValueError("Last public receipt must bind the current observation")
        if any(item.counted and not (0 <= item.x < len(grid[0]) and 0 <= item.y < len(grid))
               for item in self.ledger):
            raise ValueError("A counted public receipt must be in bounds")
        object.__setattr__(self, "observation", grid)
        object.__setattr__(self, "ledger", tuple(self.ledger))
        object.__setattr__(self, "target", _target(self.target))
        object.__setattr__(self, "observation_id", identity)

    @property
    def total_c(self):
        return sum(item.counted for item in self.ledger)

    @property
    def identity(self):
        return _digest((FAMILY_ID, self))

    @classmethod
    def from_payload(cls, payload):
        """Strict allowlist decoder. Unknown keys at every level are rejected."""
        if type(payload) is not dict:
            raise ValueError("Public payload must be a dict")
        allowed = {field.name for field in fields(cls)}
        if set(payload) - allowed:
            raise ValueError("Unknown public payload fields")
        values = dict(payload)
        if "ledger" in values:
            values["ledger"] = tuple(PublicInput(**entry) for entry in values["ledger"])
        if "limits" in values:
            values["limits"] = Limits(**values["limits"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class Score:
    expected_x: Fraction = Fraction(0)
    win_probability: Fraction = Fraction(0)
    target_probability: Fraction = Fraction(0)
    lost_probability: Fraction = Fraction(0)
    blocked_probability: Fraction = Fraction(0)

    @property
    def conditional_ioe(self):
        if not self.win_probability:
            return None
        return self.expected_x / self.win_probability

    def to_dict(self):
        return {**exact_json(self), "conditional_ioe": exact_json(self.conditional_ioe)}


def selection_key(score, survival, move, mode):
    """Maximize objective, then the contract's common tie order."""
    common = (score.expected_x, score.win_probability, survival,
              -ACTION_ORDER[move.action], -move.y, -move.x)
    if mode == "R":
        return (score.target_probability,) + common
    return common


@dataclass(frozen=True, slots=True)
class _World:
    mines: frozenset[int]
    numbers: tuple[int, ...]
    bbbv: int


def _neighbors(width, height):
    return tuple(tuple(ny * width + nx
                       for ny in range(max(0, y - 1), min(height, y + 2))
                       for nx in range(max(0, x - 1), min(width, x + 2))
                       if (nx, ny) != (x, y))
                 for y in range(height) for x in range(width))


def _make_world(mines, neighbors):
    mines = frozenset(mines)
    numbers = tuple(sum(n in mines for n in adjacent) for adjacent in neighbors)
    zeros = {i for i, number in enumerate(numbers) if not number and i not in mines}
    remaining = set(zeros)
    groups = 0
    while remaining:
        groups += 1
        pending = [remaining.pop()]
        while pending:
            found = remaining.intersection(neighbors[pending.pop()])
            remaining.difference_update(found)
            pending.extend(found)
    isolated = sum(i not in mines and numbers[i] > 0 and not zeros.intersection(adjacent)
                   for i, adjacent in enumerate(neighbors))
    return _World(mines, numbers, groups + isolated)


@dataclass(frozen=True, slots=True)
class _Transition:
    observation: tuple[int, ...]
    outcome: str | None
    counted: bool


def _transition(observation, world, move, neighbors, width, outcome=None):
    """One virtual input with the same guards, flood, and terminal display as the engine."""
    if outcome is not None or not (0 <= move.x < width and 0 <= move.y < len(observation) // width):
        return _Transition(observation, outcome, False)
    cells = list(observation)
    at = move.y * width + move.x

    def reveal(start):
        if cells[start] != HIDDEN:
            return
        if start in world.mines:
            cells[start] = -4
            return
        pending = deque([start])
        while pending:
            cell = pending.popleft()
            if cells[cell] >= 0 or cells[cell] == -4:
                continue
            cells[cell] = world.numbers[cell]
            if world.numbers[cell] == 0:
                pending.extend(n for n in neighbors[cell] if cells[n] < 0)

    if move.action == "OPEN":
        reveal(at)
    elif move.action == "FLAG" and cells[at] in (HIDDEN, FLAGGED):
        cells[at] = FLAGGED if cells[at] == HIDDEN else HIDDEN
    elif (move.action == "CHORD" and cells[at] > 0
          and sum(cells[n] == FLAGGED for n in neighbors[at]) == cells[at]):
        for neighbor in neighbors[at]:
            reveal(neighbor)
    if -4 in cells:
        outcome = "LOST"
        for i, value in enumerate(cells):
            if value == FLAGGED and i not in world.mines:
                cells[i] = -6
            elif value == HIDDEN and i in world.mines:
                cells[i] = -5
    elif sum(value >= 0 for value in cells) == len(cells) - len(world.mines):
        outcome = "WON"
        for i in world.mines:
            cells[i] = FLAGGED
    return _Transition(tuple(cells), outcome, True)


class _ResourceLimit(Exception):
    pass


class _UnsupportedSize(Exception):
    pass


class _Search:
    def __init__(self, request):
        self.request = request
        self.request_identity = request.identity
        self.started = monotonic()
        self.width = len(request.observation[0])
        self.neighbors = ()
        self.nodes = 0
        self.max_atomic_depth_used = 0
        self.cache = {}
        self.trace = {}
        self.evidence = ()
        self.world_count = None
        self.cutoff = None

    def check(self, *, expand=False):
        if monotonic() - self.started >= self.request.limits.max_seconds:
            self.cutoff = "TIME"
            raise _ResourceLimit
        if expand:
            if self.nodes >= self.request.limits.max_nodes:
                self.cutoff = "NODES"
                raise _ResourceLimit
            self.nodes += 1

    def infer(self):
        observation = tuple(v for row in self.request.observation for v in row)
        closed = tuple(i for i, value in enumerate(observation) if value < 0)
        limits = self.request.limits
        if len(observation) > limits.max_cells or len(closed) > limits.max_closed:
            raise _UnsupportedSize
        self.check()
        self.neighbors = _neighbors(self.width, len(self.request.observation))
        # Reuse the established public API, with physical flags normalized.
        normalized = tuple(tuple(HIDDEN if value == FLAGGED else value for value in row)
                           for row in self.request.observation)
        public = calculate_probabilities(normalized, self.request.num_mines)
        self.check()
        if public.total_worlds > limits.max_worlds:
            raise _UnsupportedSize
        worlds = []
        for placement in combinations(closed, self.request.num_mines):
            self.check()
            world = _make_world(placement, self.neighbors)
            if all(value < 0 or value == world.numbers[i] for i, value in enumerate(observation)):
                worlds.append(world)
        if not worlds:
            raise InconsistentObservationError("No consistent placement")
        counts = {i: sum(i in world.mines for world in worlds) for i in closed}
        if public.total_worlds != len(worlds) or any(
                item.mine_worlds != counts[item.coordinate[1] * self.width + item.coordinate[0]]
                for item in public.probabilities):
            raise RuntimeError("Public count and virtual enumeration disagree")
        self.world_count = len(worlds)
        self.evidence = tuple(OpeningEvidence(
            (i % self.width, i // self.width), "EXACT", "ENUMERATED_PUBLIC_POSTERIOR",
            len(worlds), counts[i],
            sum(i not in world.mines and world.numbers[i] == 0 for world in worlds),
        ) for i in closed)
        return observation, tuple(worlds)

    def routes(self, observation, worlds):
        closed = tuple(i for i, value in enumerate(observation) if value < 0)
        counts = {i: sum(i in world.mines for world in worlds) for i in closed}
        safe_exists = any(count == 0 for count in counts.values())
        minimum = min(counts.values(), default=0)
        if not safe_exists and not self.request.allow_guess:
            return (), True, ()
        safe_only = not self.request.allow_guess or (self.request.mode == "S" and safe_exists)
        minimum_only = self.request.mode == "S" and not safe_exists
        routes = []
        excluded = []
        for i in closed:
            move = Move("OPEN", i % self.width, i // self.width)
            permitted = counts[i] < len(worlds)
            permitted = permitted and (not safe_only or counts[i] == 0)
            permitted = permitted and (not minimum_only or counts[i] == minimum)
            if not permitted:
                excluded.append({"move": move, "reason": "RISK_RULE_OR_CERTAIN_MINE"})
                continue
            prefix = (Move("FLAG", move.x, move.y),) if observation[i] == FLAGGED else ()
            routes.append(prefix + (move,))
        for pivot, clue in enumerate(observation):
            if clue <= 0:
                continue
            adjacent = tuple(i for i in self.neighbors[pivot] if observation[i] < 0)
            if clue >= len(adjacent):
                continue
            for flagged in combinations(adjacent, clue):
                self.check()
                flagged = frozenset(flagged)
                targets = set(adjacent) - flagged
                changes = tuple(i for i in adjacent if (observation[i] == FLAGGED) != (i in flagged))
                if changes and len(targets) < 2:
                    continue
                survives = sum(not world.mines.intersection(targets) for world in worlds)
                if minimum_only or survives == 0 or (safe_only and survives != len(worlds)):
                    continue
                prefix = tuple(Move("FLAG", i % self.width, i // self.width) for i in sorted(changes))
                routes.append(prefix + (Move("CHORD", pivot % self.width, pivot // self.width),))
        return tuple(routes), False, tuple(excluded)

    def terminal_score(self, outcome, worlds, total_c):
        if outcome == "LOST":
            return Score(lost_probability=Fraction(1))
        if outcome == "GUESS_BLOCKED":
            return Score(blocked_probability=Fraction(1))
        if total_c <= 0:
            raise ValueError("A completed board requires a positive public input count")
        values = tuple(Fraction(world.bbbv, total_c) for world in worlds)
        hit = Fraction(0)
        if self.request.target is not None:
            hit = Fraction(sum(value >= self.request.target for value in values), len(values))
        return Score(sum(values, Fraction(0)) / len(values), Fraction(1), hit)

    def evaluate(self, observation, worlds, total_c, depth):
        key = (self.request_identity, observation, total_c, depth)
        if key in self.cache:
            self.check()
            return self.cache[key]
        self.check(expand=True)
        node_id = _digest(key)
        node = {"observation": self.rows(observation), "total_c": total_c,
                "remaining_atomic_depth": depth, "world_count": len(worlds),
                "status": "EVALUATING", "routes": []}
        self.trace[node_id] = node
        if sum(v >= 0 for v in observation) == len(observation) - self.request.num_mines:
            score = self.terminal_score("WON", worlds, total_c)
            node.update(status="WON", score=score.to_dict())
            answer = (score, None, node_id, "WON")
            self.cache[key] = answer
            return answer
        routes, blocked, excluded = self.routes(observation, worlds)
        node["excluded"] = excluded
        if blocked:
            score = self.terminal_score("GUESS_BLOCKED", worlds, total_c)
            node.update(status="GUESS_BLOCKED", score=score.to_dict())
            answer = (score, None, node_id, "GUESS_BLOCKED")
            self.cache[key] = answer
            return answer
        if not routes:
            raise RuntimeError("Nonterminal unblocked state has no progress route")
        by_first = {}
        for route in routes:
            self.check()
            if len(route) > depth:
                self.cutoff = "DEPTH"
                node["unresolved_route"] = route
                raise _ResourceLimit
            self.max_atomic_depth_used = max(
                self.max_atomic_depth_used, self.request.limits.max_depth - depth + len(route))
            current = [(world, observation, None) for world in worlds]
            atomic = []
            first_survives = 0
            for index, move in enumerate(route):
                self.check(expand=True)
                updated = []
                results = defaultdict(int)
                for world, cells, outcome in current:
                    transition = _transition(cells, world, move, self.neighbors, self.width, outcome)
                    if not transition.counted:
                        raise RuntimeError("A preparation route continued after termination")
                    updated.append((world, transition.observation, transition.outcome))
                    results[(transition.observation, transition.outcome)] += 1
                    if index == 0 and transition.outcome != "LOST":
                        first_survives += 1
                current = updated
                atomic.append({"input": move, "cost": 1, "total_c": total_c + index + 1,
                               "public_results": tuple({"observation": self.rows(cells),
                                                        "outcome": outcome, "worlds": count}
                                                       for (cells, outcome), count in results.items())})
            grouped = defaultdict(list)
            for world, cells, outcome in current:
                grouped[(cells, outcome)].append(world)
            weighted = [Fraction(0) for _ in fields(Score)]
            branches = []
            for (cells, outcome), group in grouped.items():
                probability = Fraction(len(group), len(worlds))
                child = None
                if outcome is None:
                    score, _, child, _ = self.evaluate(cells, tuple(group), total_c + len(route), depth - len(route))
                else:
                    score = self.terminal_score(outcome, tuple(group), total_c + len(route))
                for index, field in enumerate(fields(Score)):
                    weighted[index] += probability * getattr(score, field.name)
                branches.append({"probability": probability, "observation": self.rows(cells),
                                 "outcome": outcome, "child": child, "score": score.to_dict()})
            score = Score(*weighted)
            survival = Fraction(first_survives, len(worlds))
            row = {"inputs": route, "atomic_cost": len(route), "atomic_transitions": atomic,
                   "branches": branches, "survival": survival, "score": score.to_dict()}
            node["routes"].append(row)
            rank = selection_key(score, survival, route[0], self.request.mode)
            previous = by_first.get(route[0])
            if previous is None or rank > previous[0]:
                by_first[route[0]] = (rank, score, row)
        best_move, best = max(by_first.items(), key=lambda item: item[1][0])
        node.update(status="EXACT", selected=best_move, score=best[1].to_dict(),
                    candidates=tuple({"move": move, "score": item[1].to_dict(),
                                      "survival": item[2]["survival"], "route": item[2]["inputs"]}
                                     for move, item in by_first.items()))
        answer = (best[1], best_move, node_id, None)
        self.cache[key] = answer
        return answer

    def rows(self, observation):
        return tuple(observation[i:i + self.width] for i in range(0, len(observation), self.width))


def plan_next(request):
    """Return exact public evidence and at most one executable input.

    Node budget counts one uncached public belief plus each candidate's atomic
    transition batch over its worlds. Cached beliefs do not consume a node.
    Time is checked through inference, candidate generation, and expansion.
    No score or action is returned if any required branch remains unresolved.
    Elapsed time is diagnostic only and is kept outside the deterministic trace.
    """
    if type(request) is not PlanningRequest:
        raise TypeError("plan_next accepts only PlanningRequest")
    search = _Search(request)
    result = {
        "identity": request.identity, "observation_id": request.observation_id,
        "mode": request.mode, "allow_guess": request.allow_guess, "target": exact_json(request.target),
        "prefix_c": str(request.total_c), "prior_id": request.prior_id,
        "family_id": FAMILY_ID, "family_exclusions": list(EXCLUSIONS),
        "limits": exact_json(request.limits), "status": None, "reason": None,
        "terminal_outcome": None, "action": None, "score": None, "exactness": None,
        "target_status": None, "root": None,
    }
    try:
        if request.mode == "R" and request.target is None:
            result.update(status="TARGET_REQUIRED", reason="TARGET_REQUIRED")
        elif request.prior_id != PRIOR_ID:
            result.update(status="INSUFFICIENT", reason="UNSUPPORTED_PRIOR")
        else:
            observation, worlds = search.infer()
            score, action, root, terminal = search.evaluate(
                observation, worlds, request.total_c, request.limits.max_depth)
            status, reason = "OK", "EXACT_WITHIN_DECLARED_FAMILY"
            if terminal == "GUESS_BLOCKED":
                status, reason = "DEFER", "GUESS_DISABLED"
            elif terminal == "WON":
                status, reason = "TERMINAL", "WON"
            result.update(status=status, reason=reason, terminal_outcome=terminal,
                          action=exact_json(action), score=score.to_dict(), root=root,
                          exactness="EXACT_WITHIN_DECLARED_FAMILY")
            if request.target is not None:
                result["target_status"] = "REACHABLE" if score.target_probability else "TARGET_UNREACHABLE"
    except _UnsupportedSize:
        result.update(status="INSUFFICIENT", reason="UNSUPPORTED_SIZE")
    except _ResourceLimit:
        result.update(status="INSUFFICIENT", reason="RESOURCE_LIMIT")
    except InconsistentObservationError:
        result.update(status="INCONSISTENT_INPUT", reason="NO_CONSISTENT_PLACEMENT")
    except Exception as exc:
        # Exception text can contain arbitrary data supplied by a dependency.
        result.update(status="ERROR", reason="INFERENCE_FAILED", error_type=type(exc).__name__)
    result.update(world_count=exact_json(search.world_count), evidence=exact_json(search.evidence),
                  trace=exact_json(search.trace), resources={
                      "expanded_nodes": str(search.nodes), "cutoff": search.cutoff,
                      "atomic_depth_used": str(search.max_atomic_depth_used),
                      "elapsed_seconds": monotonic() - search.started,
                  })
    if result["exactness"] and result["resources"]["elapsed_seconds"] >= request.limits.max_seconds:
        result.update(status="INSUFFICIENT", reason="RESOURCE_LIMIT", terminal_outcome=None,
                      action=None, score=None, exactness=None, target_status=None)
        result["resources"]["cutoff"] = "TIME"
    return result
