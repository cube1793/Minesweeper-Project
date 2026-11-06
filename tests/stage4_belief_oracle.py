"""Independent small-board bitmask oracle. No production counter imports."""

from dataclasses import dataclass


@dataclass
class OracleBudget:
    states: int = 0
    placements_examined: int = 0


def count_small(observation, num_mines, events, budget):
    """Events are primitive (safe_cells, mine_cells) pairs, independent of DTOs.

    Every bitmask on the closed cells is charged, including masks rejected by
    the total mine count. This intentionally differs from component counting.
    """
    closed = [(x, y) for y, row in enumerate(observation)
              for x, value in enumerate(row) if value in (-2, -3)]
    if len(closed) > 12 or budget.states >= 48:
        raise ValueError("Small-oracle state limit")
    masks = 1 << len(closed)
    if budget.placements_examined + masks > 200_000:
        raise ValueError("Small-oracle placement limit")
    budget.states += 1
    budget.placements_examined += masks
    denominator = 0
    marginals = {cell: 0 for cell in closed}
    numerators = [0] * len(events)
    for mask in range(masks):
        if mask.bit_count() != num_mines:
            continue
        mines = {cell for index, cell in enumerate(closed) if mask & (1 << index)}
        valid = True
        for y, row in enumerate(observation):
            for x, value in enumerate(row):
                if value >= 0:
                    number = sum(abs(mx - x) <= 1 and abs(my - y) <= 1 for mx, my in mines)
                    if number != value:
                        valid = False
        if not valid:
            continue
        denominator += 1
        for cell in mines:
            marginals[cell] += 1
        for index, (safe, required_mines) in enumerate(events):
            if not mines.intersection(safe) and set(required_mines) <= mines:
                numerators[index] += 1
    return {"D": denominator, "M": marginals, "W": numerators, "examined": masks}
