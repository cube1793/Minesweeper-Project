"""Legacy P0 semantic reference copied from Unit 6, commit 3670542d.

Source SHA256 2f02c6a26d86b6c9f9d9e3743a45ed4a4cd27bd808d35d91af870a5420ff89dd.
The only algorithm-body changes permit max_work through 2,000,000 for tests.
The default remains 20,000 and inference retains its 5,000 subcap.
This copied reference shares the original rules and is not an independent oracle.
"""

from dataclasses import dataclass
from fractions import Fraction

from stage4_belief import BeliefRequest, FLAGGED
from stage4_candidates import EvidenceInput
from stage4_posterior import neighbor_indices

PILOT_ID = "PUBLIC_LOCAL_COST_P0_V1"


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
    if type(max_work) is not int or not 0 <= max_work <= 2_000_000:
        raise ValueError("Reference max_work must be in 0..2000000")
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


