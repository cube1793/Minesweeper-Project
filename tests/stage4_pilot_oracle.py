"""Independent small-board oracle. No project/product imports are permitted."""

from fractions import Fraction
from itertools import combinations


HIDDEN, FLAGGED = -2, -3
EMIT = lambda lane, value: None
CONSUME = lambda kind, count=1: None


def neighbors(width, height, cell):
    x, y = cell
    return tuple((nx, ny) for ny in range(height) for nx in range(width)
                 if max(abs(nx - x), abs(ny - y)) == 1)


def posterior(observation, num_mines):
    grid = tuple(tuple(row) for row in observation)
    height, width = len(grid), len(grid[0])
    unknown = tuple((x, y) for y in range(height) for x in range(width) if grid[y][x] < 0)
    if len(unknown) > 12:
        raise ValueError("Independent oracle is bounded to twelve unknowns")
    clues = {(x, y): grid[y][x] for y in range(height) for x in range(width) if grid[y][x] >= 0}
    layouts = []
    for positions in combinations(unknown, num_mines):
        CONSUME("oracle_masks")
        mines = frozenset(positions)
        if all(sum(cell in mines for cell in neighbors(width, height, at)) == clue
               for at, clue in clues.items()):
            layouts.append(tuple(positions))
    counts = {cell: sum(cell in mines for mines in layouts) for cell in unknown}
    result = {"grid": grid, "num_mines": num_mines, "layouts": tuple(layouts),
              "D": len(layouts), "M": tuple((cell, counts[cell]) for cell in unknown)}
    EMIT("oracle_counts", result)
    return result


def event_worlds(layouts, safe=(), mines=()):
    return sum(not (set(safe) & set(layout)) and set(mines) <= set(layout) for layout in layouts)


def static_bbbv(width, height, positions):
    mines = set(positions)
    safe = {(x, y) for y in range(height) for x in range(width)} - mines
    zero = {cell for cell in safe if not (set(neighbors(width, height, cell)) & mines)}
    covered, groups = set(), 0
    remaining = set(zero)
    while remaining:
        reached = {min(remaining, key=lambda cell: (cell[1], cell[0]))}
        while True:
            expanded = reached | {n for cell in reached for n in neighbors(width, height, cell) if n in zero}
            if expanded == reached:
                break
            reached = expanded
        groups += 1
        remaining -= reached
        covered |= reached | {n for cell in reached for n in neighbors(width, height, cell)}
    return groups + len(safe - covered)


class World:
    def __init__(self, observation, num_mines, positions):
        self.grid = [list(row) for row in observation]
        self.height, self.width = len(self.grid), len(self.grid[0])
        self.mines = frozenset(tuple(cell) for cell in positions)
        if len(self.mines) != num_mines:
            raise ValueError("Mine count mismatch")
        self.numbers = {(x, y): sum(n in self.mines for n in neighbors(self.width, self.height, (x, y)))
                        for y in range(self.height) for x in range(self.width)}
        if any((x, y) in self.mines or self.numbers[x, y] != value
               for y, row in enumerate(self.grid) for x, value in enumerate(row) if value >= 0):
            raise ValueError("Inconsistent public observation")
        self.outcome = "WON" if sum(v >= 0 for row in self.grid for v in row) == self.width * self.height - num_mines else None

    @property
    def observation(self):
        return tuple(tuple(row) for row in self.grid)

    def _reveal(self, at):
        x, y = at
        if self.grid[y][x] != HIDDEN:
            return
        if at in self.mines:
            self.grid[y][x] = -4
            return
        reached = {at}
        while True:
            expanded = reached | {n for cell in reached if self.numbers[cell] == 0
                                  for n in neighbors(self.width, self.height, cell)
                                  if self.grid[n[1]][n[0]] < 0}
            if reached == expanded:
                break
            reached = expanded
        for nx, ny in reached:
            self.grid[ny][nx] = self.numbers[nx, ny]

    def step(self, move):
        action, x, y = move
        if self.outcome is not None or not (0 <= x < self.width and 0 <= y < self.height):
            return False
        CONSUME("virtual_inputs")
        if action == "OPEN":
            self._reveal((x, y))
        elif action == "FLAG":
            if self.grid[y][x] in (HIDDEN, FLAGGED):
                self.grid[y][x] = FLAGGED if self.grid[y][x] == HIDDEN else HIDDEN
        elif action == "CHORD":
            around = neighbors(self.width, self.height, (x, y))
            if self.grid[y][x] > 0 and sum(self.grid[ny][nx] == FLAGGED for nx, ny in around) == self.grid[y][x]:
                for cell in around:
                    self._reveal(cell)
        else:
            raise ValueError("Unknown oracle action")
        if any(v == -4 for row in self.grid for v in row):
            self.outcome = "LOST"
            for ny, row in enumerate(self.grid):
                for nx, value in enumerate(row):
                    if value == FLAGGED and (nx, ny) not in self.mines:
                        row[nx] = -6
                    elif value == HIDDEN and (nx, ny) in self.mines:
                        row[nx] = -5
        elif sum(v >= 0 for row in self.grid for v in row) == self.width * self.height - len(self.mines):
            self.outcome = "WON"
            for nx, ny in self.mines:
                self.grid[ny][nx] = FLAGGED
        return True


def replay(observation, num_mines, positions, moves, counted_inputs):
    world = World(observation, num_mines, positions)
    records = []
    added = 0
    for move in moves:
        before = world.observation
        counted = world.step(tuple(move))
        added += counted
        records.append({"before": before, "move": move, "after": world.observation,
                        "counted": counted, "C": counted_inputs + added, "outcome": world.outcome})
    value = None
    if world.outcome == "LOST":
        value = Fraction(0)
    elif world.outcome == "WON":
        value = Fraction(static_bbbv(world.width, world.height, positions), counted_inputs + added)
    result = {"records": records, "outcome": world.outcome, "X": value, "added_inputs": added,
              "observation": world.observation}
    EMIT("oracle_replay", result)
    return result


def run_path(observation, num_mines, positions, counted_inputs, choose, *, max_inputs=100):
    """L2's independent transitions. The chooser sees only public grid and C."""
    world = World(observation, num_mines, positions)
    actions, decisions = [], []
    reason = "TERMINAL"
    seen = set()
    while world.outcome is None:
        if world.observation in seen or len(actions) >= max_inputs:
            reason = "PATH_LIMIT"
            break
        seen.add(world.observation)
        decision = choose(world.observation, counted_inputs + len(actions))
        decisions.append(decision)
        if decision["status"] == "DEFER" and decision["terminal_outcome"] == "GUESS_BLOCKED":
            world.outcome = "GUESS_BLOCKED"
            reason = "EXACT_GUESS_BLOCKED"
            break
        if decision["status"] != "READY":
            reason = decision["reason"]
            break
        if not decision["sequence"]:
            raise ValueError("Empty READY sequence")
        for action in decision["sequence"]:
            if not world.step(tuple(action)):
                raise ValueError("Uncounted active input")
            actions.append(tuple(action))
            if world.outcome is not None:
                break
    value = None
    if world.outcome in ("LOST", "GUESS_BLOCKED"):
        value = Fraction(0)
    elif world.outcome == "WON":
        value = Fraction(static_bbbv(world.width, world.height, positions), counted_inputs + len(actions))
    return {"outcome": world.outcome, "reason": reason, "X": value, "actions": tuple(actions),
            "decisions": tuple(decisions), "C": counted_inputs + len(actions)}

