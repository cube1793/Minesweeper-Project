"""Tiny explicit public integration board; no corpus or private K state.

At cursor (1,3), the near one-reveal CHORD costs 126005us. The far
two-reveal CHORD costs 251071us: native g is far, both survive, and the
near route is inside 105%. All mines are publicly proved from row 2.
"""
from core_engine import Action, MinesweeperEngine

DISTANCE_MINES = frozenset((x, y) for y in (1, 3) for x in (1, 3, 5))
DISTANCE_HIDDEN_SAFE = frozenset({(0, 4), (4, 0), (5, 0)})
DISTANCE_PREFIX = tuple(
    ('OPEN', x, y) for y in range(5) for x in range(6)
    if (x, y) not in DISTANCE_MINES | DISTANCE_HIDDEN_SAFE
) + tuple(('FLAG', x, y) for x, y in sorted(DISTANCE_MINES - {(1, 3)}, key=lambda c: (c[1], c[0]))) + (
    ('FLAG', 1, 3),
)
LC0_FIRST = ('CHORD', 0, 3)
P0_FIRST = ('CHORD', 4, 1)


def distance_engine():
    engine = MinesweeperEngine(6, 5, 6)
    engine.reset_with_mines(6, 5, 6, DISTANCE_MINES)
    for action, x, y in DISTANCE_PREFIX:
        engine.step(x, y, Action[action])
    return engine
