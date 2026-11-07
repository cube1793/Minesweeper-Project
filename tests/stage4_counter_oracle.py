"""Small, independent bitmask oracle over public observations (no product imports)."""
from fractions import Fraction


def observations():
    state = 100711
    for i in range(24):
        cells = []
        for x in range(6):
            if x == i % 6:
                cells.append((i // 6) % 2)
            else:
                state = (1664525 * state + 1013904223) % (2**32)
                cells.append(-3 if state % 4 == 0 else -2)
        yield [cells], 1 + i // 12
    yield [[-3, 2, -2]], 1
    yield [[-2, 1, -2, -2, -2, -2, -2, 1, -2]], 3
    yield [[0, -3, 1]], 1
    yield [[-2, -3], [-2, -2]], 2


def count_masks(grid, num_mines, *, max_masks):
    closed = [(x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v < 0]
    clues = [(x, y, v) for y, row in enumerate(grid) for x, v in enumerate(row) if v >= 0]
    masks = 1 << len(closed)
    if masks > max_masks:
        raise ValueError("Oracle mask reservation too small")
    denominator = 0
    mine_worlds = [0] * len(closed)
    for mask in range(masks):
        mines = {cell for i, cell in enumerate(closed) if mask & (1 << i)}
        if len(mines) != num_mines:
            continue
        if any(sum(max(abs(x-mx), abs(y-my)) == 1 for mx, my in mines) != clue
               for x, y, clue in clues):
            continue
        denominator += 1
        for i, cell in enumerate(closed):
            mine_worlds[i] += cell in mines
    marginals = None
    if denominator:
        marginals = []
        for cell, worlds in zip(closed, mine_worlds):
            prob = Fraction(worlds, denominator)
            marginals.append({"coordinate": list(cell), "mine_worlds": str(worlds),
                              "probability": {"numerator": str(prob.numerator),
                                              "denominator": str(prob.denominator)}})
    return {"masks": masks, "status": "COMPLETE" if denominator else "INCONSISTENT_INPUT",
            "total_worlds": str(denominator), "marginals": marginals}
