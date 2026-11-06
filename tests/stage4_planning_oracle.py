"""Independent small-board oracle for the registered progress-preparation family.

No product imports. Boolean assignments, bit-mask transitions and connected
components provide the reference. The global expansion cap applies to the
whole test process, including deliberate clairvoyant counterexamples.
"""

from fractions import Fraction
from itertools import product


ORACLE_NODES = 0


def _tick():
    global ORACLE_NODES
    ORACLE_NODES += 1
    if ORACLE_NODES > 200_000:
        raise RuntimeError("Registered oracle expansion budget exceeded")


def indices(mask):
    result = []
    while mask:
        low = mask & -mask
        result.append(low.bit_length() - 1)
        mask -= low
    return result


class Oracle:
    def __init__(self, grid, mines, mode="M", guess=True, target=None, depth=12):
        self.width = len(grid[0])
        self.height = len(grid)
        self.initial = tuple(v for row in grid for v in row)
        self.mine_count = mines
        self.mode = mode
        self.guess = guess
        self.target = target
        self.depth = depth
        self.adjacent = []
        for i in range(len(self.initial)):
            x, y = i % self.width, i // self.width
            mask = 0
            for j in range(len(self.initial)):
                if i != j and max(abs(x - j % self.width), abs(y - j // self.width)) <= 1:
                    mask |= 1 << j
            self.adjacent.append(mask)
        closed = [i for i, value in enumerate(self.initial) if value < 0]
        if len(closed) > 8:
            raise ValueError("Oracle supports eight closed cells")
        self.boards = []
        for assignment in product((0, 1), repeat=len(closed)):
            if sum(assignment) != mines:
                continue
            mask = sum(bit << i for bit, i in zip(assignment, closed))
            numbers = tuple((neighbors & mask).bit_count() for neighbors in self.adjacent)
            if all(v < 0 or v == numbers[i] for i, v in enumerate(self.initial)):
                self.boards.append((mask, numbers, self._bbbv(mask, numbers)))
        if len(self.boards) > 256:
            raise ValueError("Oracle world limit exceeded")
        self.memo = {}

    def _bbbv(self, mines, numbers):
        zero_cells = {i for i, n in enumerate(numbers) if n == 0 and not mines & (1 << i)}
        components = [{i} for i in zero_cells]
        changed = True
        while changed:
            changed = False
            for left in range(len(components)):
                for right in range(left + 1, len(components)):
                    if any(self.adjacent[i] & (1 << j) for i in components[left] for j in components[right]):
                        components[left] |= components.pop(right)
                        changed = True
                        break
                if changed:
                    break
        isolated = 0
        for i, number in enumerate(numbers):
            if number and not mines & (1 << i) and not any(self.adjacent[i] & (1 << j) for j in zero_cells):
                isolated += 1
        return len(components) + isolated

    def step(self, cells, board, move):
        mines, numbers, _ = board
        kind, x, y = move
        if not (0 <= x < self.width and 0 <= y < self.height):
            return cells, None
        cell = y * self.width + x
        opened = sum((value >= 0) << i for i, value in enumerate(cells))
        flagged = sum((value == -3) << i for i, value in enumerate(cells))
        exploded = 0

        def expose(start, revealed, flags, explosions):
            bit = 1 << start
            if bit & (revealed | flags):
                return revealed, flags, explosions
            if bit & mines:
                return revealed | bit, flags, explosions | bit
            frontier = bit
            while frontier:
                fresh = frontier & ~revealed
                if not fresh:
                    break
                revealed |= fresh
                flags &= ~fresh
                frontier = 0
                for i in indices(fresh):
                    if numbers[i] == 0:
                        frontier |= self.adjacent[i]
            return revealed, flags, explosions

        if kind == "FLAG" and not opened & (1 << cell):
            flagged ^= 1 << cell
        if kind == "OPEN":
            opened, flagged, exploded = expose(cell, opened, flagged, exploded)
        if kind == "CHORD" and cells[cell] > 0 and (flagged & self.adjacent[cell]).bit_count() == cells[cell]:
            for i in indices(self.adjacent[cell]):
                opened, flagged, exploded = expose(i, opened, flagged, exploded)
        outcome = None
        if exploded:
            outcome = "LOST"
        elif opened.bit_count() == len(cells) - self.mine_count:
            outcome = "WON"
            flagged |= mines
        result = []
        for i, number in enumerate(numbers):
            bit = 1 << i
            if bit & exploded:
                value = -4
            elif bit & opened:
                value = number
            elif bit & flagged:
                value = -6 if outcome == "LOST" and not bit & mines else -3
            elif outcome == "LOST" and bit & mines:
                value = -5
            else:
                value = -2
            result.append(value)
        return tuple(result), outcome

    def programs(self, cells, boards):
        hidden = [i for i, v in enumerate(cells) if v < 0]
        risk = {i: sum(bool(board[0] & (1 << i)) for board in boards) for i in hidden}
        safe = any(v == 0 for v in risk.values())
        if not safe and not self.guess:
            return None
        safe_only = not self.guess or (self.mode == "S" and safe)
        smallest = min(risk.values(), default=0)
        result = []
        for i in hidden:
            if risk[i] == len(boards) or (safe_only and risk[i]):
                continue
            if self.mode == "S" and not safe and risk[i] != smallest:
                continue
            opening = ("OPEN", i % self.width, i // self.width)
            result.append((("FLAG", opening[1], opening[2]), opening) if cells[i] == -3 else (opening,))
        if self.mode == "S" and not safe:
            return result
        for pivot, clue in enumerate(cells):
            if clue < 1:
                continue
            neighbors = [i for i in indices(self.adjacent[pivot]) if cells[i] < 0]
            for mask in range(1 << len(neighbors)):
                if mask.bit_count() != clue:
                    continue
                final_flags = {i for j, i in enumerate(neighbors) if mask & (1 << j)}
                targets = set(neighbors) - final_flags
                changes = [i for i in neighbors if (cells[i] == -3) != (i in final_flags)]
                if not targets or (changes and len(targets) < 2):
                    continue
                target_bits = sum(1 << i for i in targets)
                survives = sum(not board[0] & target_bits for board in boards)
                if survives == 0 or (safe_only and survives < len(boards)):
                    continue
                edits = tuple(("FLAG", i % self.width, i // self.width) for i in changes)
                result.append(edits + (("CHORD", pivot % self.width, pivot // self.width),))
        return result

    def rank(self, score, survival, action):
        action_priority = {"OPEN": 0, "CHORD": 1, "FLAG": 2}
        common = (score[0], score[1], survival, -action_priority[action[0]], -action[2], -action[1])
        return (score[2],) + common if self.mode == "R" else common

    def terminal(self, outcome, boards, c):
        if outcome == "LOST":
            return (Fraction(0), Fraction(0), Fraction(0), Fraction(1), Fraction(0))
        if outcome == "GUESS_BLOCKED":
            return (Fraction(0), Fraction(0), Fraction(0), Fraction(0), Fraction(1))
        scores = [Fraction(board[2], c) for board in boards]
        reach = sum(v >= self.target for v in scores) if self.target is not None else 0
        return (sum(scores) / len(boards), Fraction(1), Fraction(reach, len(boards)), Fraction(0), Fraction(0))

    def solve(self, c=0, cells=None, boards=None, depth=None):
        cells = self.initial if cells is None else cells
        boards = tuple(self.boards) if boards is None else boards
        depth = self.depth if depth is None else depth
        # The posterior is uniquely fixed by the public evidence within one call.
        # Clairvoyant experiments use fresh Oracle instances for singleton worlds.
        key = (cells, c, depth)
        if key in self.memo:
            return self.memo[key]
        _tick()
        if sum(v >= 0 for v in cells) == len(cells) - self.mine_count:
            return {"action": None, "score": self.terminal("WON", boards, c), "candidates": {}}
        programs = self.programs(cells, boards)
        if programs is None:
            return {"action": None, "score": self.terminal("GUESS_BLOCKED", boards, c), "candidates": {}}
        candidates = {}
        for program in programs:
            if len(program) > depth:
                raise RuntimeError("Oracle atomic depth exhausted")
            grouped = {}
            first_survivors = 0
            for board in boards:
                after = cells
                terminal = None
                for index, action in enumerate(program):
                    if terminal:
                        raise AssertionError("Program continues after terminal")
                    after, terminal = self.step(after, board, action)
                    if index == 0 and terminal != "LOST":
                        first_survivors += 1
                grouped.setdefault((after, terminal), []).append(board)
            for _ in program:
                _tick()
            average = [Fraction(0) for _ in range(5)]
            for (after, terminal), posterior in grouped.items():
                if terminal:
                    score = self.terminal(terminal, posterior, c + len(program))
                else:
                    score = self.solve(c + len(program), after, tuple(posterior), depth - len(program))["score"]
                for i in range(5):
                    average[i] += Fraction(len(posterior), len(boards)) * score[i]
            score = tuple(average)
            survival = Fraction(first_survivors, len(boards))
            rank = self.rank(score, survival, program[0])
            if program[0] not in candidates or rank > candidates[program[0]]["rank"]:
                candidates[program[0]] = {"score": score, "survival": survival, "rank": rank, "program": program}
        action = max(candidates, key=lambda move: candidates[move]["rank"])
        result = {"action": action, "score": candidates[action]["score"], "candidates": candidates}
        self.memo[key] = result
        return result
