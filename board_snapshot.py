"""
board_snapshot.py
Immutable read-only board snapshot for analysis modules.

This module intentionally has no PyQt5 dependency.  It gives future analysis
code, such as 3BV/Ops extraction or ZiNi calculators, a stable input object
without exposing mutable engine internals.
"""

from dataclasses import dataclass


Coordinate = tuple[int, int]
AdjacentGrid = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class BoardSnapshot:
    """
    Immutable snapshot of the static board state.

    When mines have not been placed yet, ``mines_placed`` is False, ``mines`` is
    empty, and ``adjacent`` reflects the engine's current zero-filled grid.  Such
    a snapshot is useful as a read-only state description, but analysis modules
    that require a finalized mine layout should explicitly check
    ``mines_placed`` before calculating metrics.
    """

    width: int
    height: int
    num_mines: int
    mines_placed: bool
    mines: frozenset[Coordinate]
    adjacent: AdjacentGrid

    def __post_init__(self):
        object.__setattr__(self, "mines", frozenset(self.mines))
        object.__setattr__(
            self,
            "adjacent",
            tuple(tuple(row) for row in self.adjacent),
        )
