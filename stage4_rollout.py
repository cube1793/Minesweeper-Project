"""A sampled-world evaluator and a fixed, public-input-only pilot.

Virtual layouts and static 3BV belong to the evaluator. The module-level P0
function receives only public observations, public counts and resource controls.
"""

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from time import perf_counter

from board_analyzer import analyze_board
from board_snapshot import BoardSnapshot
from stage4_belief import BeliefRequest, FLAGGED, HIDDEN, exact_json
from stage4_candidates import EvidenceInput
from stage4_posterior import neighbor_indices, public_digest


PILOT_ID = "PUBLIC_LOCAL_COST_P0_V1"


@dataclass(frozen=True, slots=True)
class VirtualStep:
    observation: tuple[tuple[int, ...], ...]
    outcome: str | None
    counted: bool


class VirtualBoard:
    """Evaluator-owned state, with no reference to the actual game engine."""

    def __init__(self, observation, num_mines, mines):
        public = BeliefRequest(observation, num_mines)
        self.width = len(public.observation[0])
        self.height = len(public.observation)
        if self.width * self.height > 480:
            raise ValueError("Virtual board exceeds 480 cells")
        coordinates = tuple(mines)
        if any(type(cell) is not tuple or len(cell) != 2
               or any(type(value) is not int for value in cell)
               or not (0 <= cell[0] < self.width and 0 <= cell[1] < self.height)
               for cell in coordinates):
            raise ValueError("Invalid sampled mine coordinates")
        self._mines = frozenset(y * self.width + x for x, y in coordinates)
        if len(self._mines) != num_mines or len(coordinates) != num_mines:
            raise ValueError("Sampled mine count mismatch")
        self._neighbors = neighbor_indices(self.width, self.height)
        self._numbers = tuple(sum(n in self._mines for n in adjacent)
                              for adjacent in self._neighbors)
        self._cells = [v for row in public.observation for v in row]
        for cell, value in enumerate(self._cells):
            if value >= 0 and (cell in self._mines or value != self._numbers[cell]):
                raise ValueError("Sample contradicts the public observation")
        self.outcome = None
        if sum(v >= 0 for v in self._cells) == len(self._cells) - num_mines:
            self.outcome = "WON"

    @property
    def observation(self):
        return tuple(tuple(self._cells[start:start + self.width])
                     for start in range(0, len(self._cells), self.width))

    def static_bbbv(self):
        """Evaluator-only reward denominator, never an input to P0."""
        snapshot = BoardSnapshot(
            self.width, self.height, len(self._mines), True,
            frozenset((i % self.width, i // self.width) for i in self._mines),
            tuple(tuple(self._numbers[start:start + self.width])
                  for start in range(0, len(self._cells), self.width)))
        return analyze_board(snapshot).total_3bv

    def _reveal(self, start):
        if self._cells[start] != HIDDEN:
            return
        if start in self._mines:
            self._cells[start] = -4
            return
        pending = deque([start])
        while pending:
            cell = pending.popleft()
            if self._cells[cell] >= 0 or self._cells[cell] == -4:
                continue
            self._cells[cell] = self._numbers[cell]
            if self._numbers[cell] == 0:
                pending.extend(n for n in self._neighbors[cell] if self._cells[n] < 0)

    def step(self, move):
        if (type(move) is not EvidenceInput or move.action not in ("OPEN", "FLAG", "CHORD")
                or type(move.x) is not int or type(move.y) is not int):
            raise ValueError("A valid atomic EvidenceInput is required")
        if self.outcome is not None or not (0 <= move.x < self.width and 0 <= move.y < self.height):
            return VirtualStep(self.observation, self.outcome, False)
        at = move.y * self.width + move.x
        if move.action == "OPEN":
            self._reveal(at)
        elif move.action == "FLAG" and self._cells[at] in (HIDDEN, FLAGGED):
            self._cells[at] = FLAGGED if self._cells[at] == HIDDEN else HIDDEN
        elif (move.action == "CHORD" and self._cells[at] > 0
              and sum(self._cells[n] == FLAGGED for n in self._neighbors[at]) == self._cells[at]):
            for neighbor in self._neighbors[at]:
                self._reveal(neighbor)
        if -4 in self._cells:
            self.outcome = "LOST"
            for i, value in enumerate(self._cells):
                if value == FLAGGED and i not in self._mines:
                    self._cells[i] = -6
                elif value == HIDDEN and i in self._mines:
                    self._cells[i] = -5
        elif sum(v >= 0 for v in self._cells) == len(self._cells) - len(self._mines):
            self.outcome = "WON"
            for cell in self._mines:
                self._cells[cell] = FLAGGED
        return VirtualStep(self.observation, self.outcome, True)


@dataclass(frozen=True, slots=True)
class PilotResult:
    status: str
    reason: str
    sequence: tuple[EvidenceInput, ...]
    work: int
    inference_complete: bool
    proven_safe: tuple[int, ...]
    proven_mines: tuple[int, ...]
    risk_hint: Fraction | None = None


class _PilotCap(Exception):
    pass


def pilot_p0(observation, num_mines, counted_inputs, allow_guess, *, max_work=20_000, cancelled=None):
    """Public local rules and cost ordering. Density hints are heuristic only."""
    public = BeliefRequest(observation, num_mines)
    if type(counted_inputs) is not int or counted_inputs < 0 or type(allow_guess) is not bool:
        raise ValueError("Invalid public C or guess setting")
    if type(max_work) is not int or not 0 <= max_work <= 20_000:
        raise ValueError("Pilot max_work must be in 0..20000")
    if len(public.observation) * len(public.observation[0]) > 480:
        raise ValueError("Pilot exceeds 480 cells")
    grid = public.observation
    width = len(grid[0])
    flat = tuple(v for row in grid for v in row)
    adjacent = neighbor_indices(width, len(grid))
    closed = frozenset(i for i, value in enumerate(flat) if value < 0)
    safe, mines, candidates = set(), set(), []
    work, inference_complete = 0, False

    def tick(amount=1):
        nonlocal work
        if cancelled is not None:
            value = cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _PilotCap("CANCELLED")
        if work + amount > max_work:
            raise _PilotCap("PILOT_WORK_LIMIT")
        work += amount

    def move(action, cell):
        return EvidenceInput(action, cell % width, cell // width)

    def result(status, reason, sequence=(), hint=None):
        return PilotResult(status, reason, sequence, work, inference_complete,
                           tuple(sorted(safe)), tuple(sorted(mines)), hint)

    try:
        tick()
        constraints = []
        for cell, clue in enumerate(flat):
            tick()
            if clue >= 0:
                constraints.append((tuple(n for n in adjacent[cell] if n in closed), clue))
        constraints.append((tuple(sorted(closed)), num_mines))
        inference_work = 0
        while True:
            previous = len(safe) + len(mines)
            capped = False
            for cells, total in constraints:
                cost = len(cells) + 1
                if inference_work + cost > 5_000:
                    capped = True
                    break
                tick(cost)
                inference_work += cost
                unknown = set(cells) - safe - mines
                remaining = total - len(set(cells) & mines)
                if remaining < 0 or remaining > len(unknown):
                    raise ValueError("Contradictory public local constraints")
                if remaining == 0:
                    safe.update(unknown)
                elif remaining == len(unknown):
                    mines.update(unknown)
            if capped:
                break
            if previous == len(safe) + len(mines):
                inference_complete = True
                break

        def add_candidate(kind, pivot, targets, sequence):
            tick(len(targets) + 1)
            zero = any(all(n not in closed or n in safe for n in adjacent[t]) for t in targets)
            key = (-Fraction(len(targets), len(sequence)), -int(zero), len(sequence),
                   ("OPEN", "CHORD").index(kind), pivot,
                   tuple((m.action, m.y, m.x) for m in sequence))
            candidates.append((key, sequence))

        for cell in sorted(safe):
            prefix = (move("FLAG", cell),) if flat[cell] == FLAGGED else ()
            add_candidate("OPEN", cell, (cell,), prefix + (move("OPEN", cell),))
        for pivot, clue in enumerate(flat):
            tick()
            if clue <= 0:
                continue
            cells = tuple(n for n in adjacent[pivot] if n in closed)
            flags = set(cells) & mines
            targets = tuple(n for n in cells if n not in flags)
            if len(flags) != clue or not targets or not set(targets) <= safe:
                continue
            changes = tuple(n for n in cells if (flat[n] == FLAGGED) != (n in flags))
            if changes and len(targets) < 2:
                continue
            sequence = tuple(move("FLAG", n) for n in changes) + (move("CHORD", pivot),)
            add_candidate("CHORD", pivot, targets, sequence)
        if candidates:
            tick()
            return result("READY", "PROVEN_SAFE_COST", min(candidates, key=lambda item: item[0])[1])
        if not allow_guess:
            return result("PILOT_UNRESOLVED", "LOCAL_RULES_STALLED_GUESS_OFF")
        guesses = []
        residual = closed - safe - mines
        for cell in sorted(closed - mines):
            tick()
            hint = Fraction(num_mines - len(mines), len(residual)) if residual else Fraction(0)
            for cells, total in constraints[:-1]:
                tick(len(cells) + 1)
                if cell in cells:
                    unknown = set(cells) - safe - mines
                    if unknown:
                        hint = max(hint, Fraction(total - len(set(cells) & mines), len(unknown)))
            cost = 2 if flat[cell] == FLAGGED else 1
            guesses.append(((hint, cost, cell), cell))
        if not guesses:
            return result("PILOT_UNRESOLVED", "NO_VIABLE_LOCAL_OPEN")
        key, cell = min(guesses)
        prefix = (move("FLAG", cell),) if flat[cell] == FLAGGED else ()
        return result("READY", "LOCAL_DENSITY_HEURISTIC", prefix + (move("OPEN", cell),), key[0])
    except _PilotCap as exc:
        return result("PILOT_UNRESOLVED", str(exc))
    except Exception as exc:
        return result("ERROR", f"{type(exc).__name__}: {exc}")


@dataclass(frozen=True, slots=True)
class RolloutLimits:
    max_rollouts: int = 768
    max_virtual_inputs: int = 50_000
    max_inputs_per_rollout: int = 2_000
    max_pilot_work: int = 10_000_000
    max_seconds: float = 30.0

    def __post_init__(self):
        for name, cap in (("max_rollouts", 768), ("max_virtual_inputs", 50_000),
                          ("max_inputs_per_rollout", 2_000), ("max_pilot_work", 10_000_000)):
            if type(getattr(self, name)) is not int or not 0 <= getattr(self, name) <= cap:
                raise ValueError(f"{name} must be in 0..{cap}")
        if (type(self.max_seconds) not in (int, float) or not isfinite(self.max_seconds)
                or not 0 <= self.max_seconds <= 30):
            raise ValueError("Rollout time must be in 0..30")


@dataclass(frozen=True, slots=True)
class RolloutRecord:
    candidate_id: str
    sample_index: int
    rank: int
    outcome: str
    reason: str
    value_x: Fraction | None
    hit: bool | None
    virtual_b: int | None
    added_inputs: int
    actions: tuple[EvidenceInput, ...]
    pilot_request_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RolloutBatch:
    status: str
    reason: str
    pilot_id: str
    records: tuple[RolloutRecord, ...]
    started_rollouts: int
    virtual_inputs: int
    pilot_work: int
    pilot_calls: int
    elapsed_seconds: float
    error: str | None

    def to_dict(self):
        return exact_json(self)


class _RolloutStop(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class _RolloutMeter:
    def __init__(self, limits, cancelled):
        self.limits, self.cancelled = limits, cancelled
        self.started = perf_counter()
        self.rollouts = self.inputs = self.work = self.pilot_calls = 0
        self.pending = None

    def check(self):
        if self.pending is not None:
            raise self.pending
        if self.cancelled is not None:
            value = self.cancelled()
            if type(value) is not bool:
                raise TypeError("Cancellation callback must return bool")
            if value:
                raise _RolloutStop("CANCELLED", "CANCELLED")
        if perf_counter() - self.started >= self.limits.max_seconds:
            raise _RolloutStop("INCOMPLETE", "ROLLOUT_TIME_LIMIT")

    def pilot_cancelled(self):
        try:
            self.check()
        except _RolloutStop as exc:
            self.pending = exc
            return True
        return False


def evaluate_rollouts(observation, num_mines, counted_inputs, allow_guess,
                      samples, candidates, *, target=None, limits=RolloutLimits(), cancelled=None):
    """Run each candidate against the same ordered bank. Preserve all null rows."""
    meter = _RolloutMeter(limits, cancelled)
    records = [RolloutRecord(c.candidate_id, index, sample.rank, "NOT_STARTED", "NOT_REACHED",
                             None, None, None, 0, (), ())
               for c in candidates for index, sample in enumerate(samples)]
    status, reason, error = "COMPLETE", "ALL_TERMINAL", None
    try:
        meter.check()
        if not samples or not candidates:
            raise ValueError("A nonempty bank and shortlist are required")
        for candidate_index, candidate in enumerate(candidates):
            for sample_index, sample in enumerate(samples):
                record_index = candidate_index * len(samples) + sample_index
                actions, pilot_ids, virtual_b = [], [], None
                outcome, row_reason, value_x, hit = "UNRESOLVED", "NOT_FINISHED", None, None
                try:
                    meter.check()
                    if meter.rollouts >= limits.max_rollouts:
                        raise _RolloutStop("INCOMPLETE", "ROLLOUT_COUNT_LIMIT")
                    meter.rollouts += 1
                    board = VirtualBoard(observation, num_mines, sample.mines)
                    virtual_b = board.static_bbbv()
                    meter.check()
                    sequence = candidate.sequence
                    visited = set()
                    while board.outcome is None:
                        before = board.observation
                        if before in visited:
                            raise ValueError("Repeated public state in pilot")
                        visited.add(before)
                        for action in sequence:
                            meter.check()
                            if meter.inputs >= limits.max_virtual_inputs:
                                raise _RolloutStop("INCOMPLETE", "VIRTUAL_INPUT_LIMIT")
                            if len(actions) >= limits.max_inputs_per_rollout:
                                raise _RolloutStop("INCOMPLETE", "ROLLOUT_INPUT_LIMIT")
                            transition = board.step(action)
                            if not transition.counted:
                                raise ValueError("An active rollout input was not counted")
                            actions.append(action)
                            meter.inputs += 1
                            if board.outcome is not None:
                                break
                        if board.outcome is not None:
                            break
                        if (sum(v >= 0 for row in board.observation for v in row)
                                <= sum(v >= 0 for row in before for v in row)):
                            raise ValueError("Pilot sequence did not reveal a new cell")
                        meter.check()
                        remaining_work = limits.max_pilot_work - meter.work
                        if remaining_work <= 0:
                            raise _RolloutStop("INCOMPLETE", "PILOT_WORK_LIMIT")
                        public_grid = board.observation
                        public_c = counted_inputs + len(actions)
                        pilot_ids.append(public_digest((PILOT_ID, public_grid, num_mines,
                                                        public_c, allow_guess)))
                        meter.pilot_calls += 1
                        decision = pilot_p0(public_grid, num_mines, public_c, allow_guess,
                                            max_work=min(20_000, remaining_work),
                                            cancelled=meter.pilot_cancelled)
                        meter.work += decision.work
                        meter.check()
                        if decision.status == "ERROR":
                            raise ValueError("Public pilot error: " + decision.reason)
                        if decision.status != "READY":
                            outcome, row_reason = "PILOT_UNRESOLVED", decision.reason
                            raise _RolloutStop("INCOMPLETE", decision.reason)
                        sequence = decision.sequence
                    outcome, row_reason = board.outcome, "TERMINAL"
                    if outcome == "WON":
                        if counted_inputs + len(actions) <= 0:
                            raise ValueError("WON reward requires positive total C")
                        value_x = Fraction(virtual_b, counted_inputs + len(actions))
                    else:
                        value_x = Fraction(0)
                    hit = outcome == "WON" and value_x >= target if target is not None else None
                    meter.check()
                except _RolloutStop as exc:
                    row_reason = exc.reason
                    raise
                finally:
                    records[record_index] = RolloutRecord(
                        candidate.candidate_id, sample_index, sample.rank, outcome, row_reason,
                        value_x, hit, virtual_b, len(actions), tuple(actions), tuple(pilot_ids))
        meter.check()
    except _RolloutStop as exc:
        status, reason = exc.status, exc.reason
    except Exception as exc:
        status, reason, error = "ERROR", "MODEL_ERROR", f"{type(exc).__name__}: {exc}"
    return RolloutBatch(status, reason, PILOT_ID, tuple(records), meter.rollouts,
                        meter.inputs, meter.work, meter.pilot_calls,
                        perf_counter() - meter.started, error)
