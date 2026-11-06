"""Independent raw-bitmask and static-metric oracles for Unit 6 tests.

No production modules are imported. Hooks allow the isolated driver to record
all attempted masks, including rejected assignments.
"""

CONSUME = lambda name, count=1: None
EMIT = lambda lane, value: None


def neighbors(width, height, x, y):
    return [(nx, ny) for ny in range(height) for nx in range(width)
            if (nx, ny) != (x, y) and abs(nx - x) <= 1 and abs(ny - y) <= 1]


def raw_worlds(grid, num_mines):
    height, width = len(grid), len(grid[0])
    unknown = [(x, y) for y in range(height) for x in range(width) if grid[y][x] < 0]
    worlds = []
    for bits in range(1 << len(unknown)):
        CONSUME("small_masks", 1)
        if bits.bit_count() != num_mines:
            continue
        mines = frozenset(cell for i, cell in enumerate(unknown) if bits & (1 << i))
        consistent = True
        for y in range(height):
            for x in range(width):
                if grid[y][x] >= 0 and sum(cell in mines for cell in neighbors(width, height, x, y)) != grid[y][x]:
                    consistent = False
        if consistent:
            worlds.append(mines)
    return tuple(worlds)


def consistent(grid, num_mines, mines):
    mines = set(mines)
    if len(mines) != num_mines:
        return False
    height, width = len(grid), len(grid[0])
    if any(not (0 <= x < width and 0 <= y < height) for x, y in mines):
        return False
    return all((x, y) not in mines
               and sum(cell in mines for cell in neighbors(width, height, x, y)) == value
               for y, row in enumerate(grid) for x, value in enumerate(row) if value >= 0)


def static_bbbv(width, height, mines):
    mines = set(mines)
    safe = {(x, y) for y in range(height) for x in range(width)} - mines
    zero = {cell for cell in safe if not (set(neighbors(width, height, *cell)) & mines)}
    unvisited, groups = set(zero), 0
    while unvisited:
        groups += 1
        pending = [unvisited.pop()]
        while pending:
            cell = pending.pop()
            found = unvisited & set(neighbors(width, height, *cell))
            unvisited -= found
            pending.extend(found)
    isolated = sum(not (set(neighbors(width, height, *cell)) & zero) for cell in safe - zero)
    return groups + isolated


def matrix_summary(values, target):
    from fractions import Fraction
    if any(value is None for value in values):
        return None
    return (sum(values, Fraction(0)) / len(values),
            Fraction(sum(value > 0 for value in values), len(values)),
            Fraction(sum(value >= target for value in values), len(values)))
