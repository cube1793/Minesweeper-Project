"""Independent literal-mask oracle for Unit 5 small public observations.

Only raw grids and total mine counts enter this module. Candidate arrangements,
event coordinates, eligibility and all counts are reconstructed here. Product
modules and their candidate/event helpers are deliberately absent.
"""

from fractions import Fraction


H, F = -2, -3
FIXTURES = (
    ("CENTER_ONE", ((H, H, H), (H, 1, H), (H, H, H)), 1),
    ("CENTER_ONE_FLAG", ((F, H, H), (H, 1, H), (H, H, H)), 1),
    ("GLOBAL_MIN_RISK_FLAGGED", ((H, 1, H, F, F, F, F, F),), 2),
    ("ONE_TARGET_EXISTING", ((1, H), (F, 1)), 1),
    ("ZERO_FIXED_ROW", ((H, H, H, H, H),), 0),
    ("TWO_H_ONE", ((H, H),), 1),
    ("ZERO_FLAGS", ((F, H, F, H, H),), 0),
    ("ALL_MINES", ((H, F),), 2),
    ("SAFE_FLAG", ((0, F, H),), 0),
    ("FORCED_MINE", ((1, H, H),), 1),
    ("FORCED_MINE_FLAG", ((1, F, H),), 1),
    ("ONE_TARGET_EDITED", ((1, H), (H, 1)), 1),
    ("CENTER_TWO", ((H, H, H), (H, 2, H), (H, H, H)), 2),
    ("CENTER_ONE_OVERFLAGS", ((F, F, H), (H, 1, H), (H, H, H)), 1),
    ("ROW_MULTI", ((H, 1, H, 1, H),), 1),
    ("ROW_SPLIT", ((H, 1, H, H, 1, H),), 2),
    ("CONTRADICTING_CLUES", ((H, 1, H), (H, 2, H)), 2),
    ("SHARED_PIVOTS", ((H, H, H), (1, H, 1), (H, H, H)), 2),
    ("ALL_OPEN", ((0, 0),), 0),
    ("INCONSISTENT_TOTAL", ((1, H),), 0),
    ("INCONSISTENT_ZERO", ((0, H),), 1),
    ("HIDDEN_TEN", ((H,) * 10,), 3),
    ("RECT_HIDDEN", ((H, H, H), (H, H, H)), 2),
    ("CORNER_ONE", ((1, H, H), (H, H, H), (H, H, H)), 2),
)

PREFIXES = {
    "CENTER_ONE": (("OPEN", 1, 1),),
    "CENTER_ONE_FLAG": (("OPEN", 1, 1), ("FLAG", 0, 0)),
    "GLOBAL_MIN_RISK_FLAGGED": (("OPEN", 1, 0),) + tuple(("FLAG", x, 0) for x in range(3, 8)),
    "ONE_TARGET_EXISTING": (("OPEN", 0, 0), ("OPEN", 1, 1), ("FLAG", 0, 1)),
    "ZERO_FIXED_ROW": (),
}


def analyze_grid(grid, num_mines, consume=lambda name, count: None):
    """Count every closed-cell bitmask, then profile the independent catalogue."""
    height, width = len(grid), len(grid[0])
    cells = tuple(range(width * height))
    closed = tuple(i for i in cells if grid[i // width][i % width] < 0)
    if len(closed) > 10:
        raise ValueError("Small oracle supports at most ten closed cells")
    consume("oracle_states", 1)
    neighbors = {i: {j for j in cells if j != i and
                     max(abs(i % width - j % width), abs(i // width - j // width)) == 1}
                 for i in cells}
    worlds = []
    for mask in range(1 << len(closed)):
        consume("oracle_masks", 1)
        if mask.bit_count() != num_mines:
            continue
        mines = frozenset(closed[bit] for bit in range(len(closed)) if mask & (1 << bit))
        if all(len(neighbors[i] & mines) == grid[i // width][i % width]
               for i in cells if i not in closed):
            worlds.append(mines)
    denominator = len(worlds)
    counts = {i: sum(i in world for world in worlds) for i in closed}
    xy = lambda i: (i % width, i // width)
    result = {"D": denominator, "M": {xy(i): counts[i] for i in closed},
              "layouts": tuple(tuple(xy(i) for i in sorted(w)) for w in worlds),
              "has_proven_safe_cell": None, "candidates": (), "generated": 0,
              "empty_excluded": 0, "single_excluded": 0}
    if not denominator:
        return result
    result["has_proven_safe_cell"] = any(value == 0 for value in counts.values())
    structures = []
    for i in closed:
        result["generated"] += 1
        prefix = (("FLAG", i),) if grid[i // width][i % width] == F else ()
        structures.append(("OPEN", i, (), (i,), prefix + (("OPEN", i),)))
    for pivot in cells:
        clue = grid[pivot // width][pivot % width]
        if clue <= 0:
            continue
        adjacent = tuple(sorted(neighbors[pivot] & set(closed)))
        arrangements = []
        for flag_mask in range(1 << len(adjacent)):
            if flag_mask.bit_count() == clue:
                arrangements.append(tuple(adjacent[j] for j in range(len(adjacent))
                                          if flag_mask & (1 << j)))
        for flags in sorted(arrangements):
            result["generated"] += 1
            targets = tuple(i for i in adjacent if i not in flags)
            edits = tuple(i for i in adjacent if (grid[i // width][i % width] == F) != (i in flags))
            if not targets:
                result["empty_excluded"] += 1
            elif edits and len(targets) == 1:
                result["single_excluded"] += 1
            else:
                sequence = tuple(("FLAG", i) for i in edits) + (("CHORD", pivot),)
                structures.append(("CHORD", pivot, flags, targets, sequence))
    profiles = []
    for kind, pivot, flags, targets, sequence in structures:
        consume("oracle_profiles", len(worlds))
        survivors = [world for world in worlds if not set(targets) & world]
        ws = len(survivors)
        zeros = []
        for target in targets:
            safe_event = (set(targets) | {target} | neighbors[target]) & set(closed)
            zt = sum(not safe_event & world for world in worlds)
            assert 0 <= zt <= ws <= denominator
            zeros.append({"cell": xy(target), "safe_cells": tuple(xy(i) for i in sorted(safe_event)),
                          "worlds": zt, "joint": Fraction(zt, denominator),
                          "conditional": Fraction(zt, ws) if ws else None})
        guaranteed = ws == denominator
        if result["has_proven_safe_cell"]:
            s_allowed = guaranteed
        else:
            s_allowed = kind == "OPEN" and ws > 0 and counts[pivot] == min(counts.values())
        profiles.append({"kind": kind, "pivot": xy(pivot), "final_flags": tuple(map(xy, flags)),
                         "targets": tuple(map(xy, targets)),
                         "sequence": tuple({"action": action, "x": xy(i)[0], "y": xy(i)[1]}
                                           for action, i in sequence),
                         "cost": len(sequence), "survival_worlds": ws,
                         "survival_probability": Fraction(ws, denominator), "zero_targets": tuple(zeros),
                         "target_count": len(targets),
                         "floor": Fraction(len(targets) * ws, denominator * len(sequence)),
                         "eligibility": {"guess_off": guaranteed, "S_guess_on": s_allowed,
                                         "M_guess_on": ws > 0, "R_guess_on": ws > 0}})
    result["candidates"] = tuple(profiles)
    return result
