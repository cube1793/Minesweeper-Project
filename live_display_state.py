"""Disposable certainty pixels, never a source of execution authority."""
from dataclasses import dataclass

from core_engine import CellState
from live_analysis import CellOverlay, OverlayKind


@dataclass(frozen=True)
class DisplayContext:
    game: str
    policy: str
    run: str
    generation: int
    owner: int
    revision: int
    history_digest: str
    observation_digest: str


@dataclass(frozen=True)
class CertaintyFrame:
    context: DisplayContext
    safe: frozenset
    mines: frozenset

    @classmethod
    def capture(cls, context, overlays, observation, carried=None):
        """Colors of this result, plus earlier proofs it does not dispute.

        ``carried`` must already have been advanced into this exact context by
        the recorded input. A proof stays valid while public information only
        grows, so a later result that omits a still-HIDDEN cell does not retract
        it. A result that colors a carried cell differently discredits all of it.
        """
        hidden = hidden_cells(observation)
        safe = frozenset(c for c, o in overlays.items()
                         if c in hidden and o.kind == OverlayKind.SAFE)
        mines = frozenset(c for c, o in overlays.items()
                          if c in hidden and o.kind == OverlayKind.MINE)
        if (type(carried) is CertaintyFrame and context is not None and carried.context == context
                and type(carried.safe) is frozenset and type(carried.mines) is frozenset
                and not carried.safe & carried.mines):
            kept = ((carried.safe & hidden, OverlayKind.SAFE), (carried.mines & hidden, OverlayKind.MINE))
            if all(c not in overlays or overlays[c].kind in (None, kind)
                   for cells, kind in kept for c in cells):
                safe, mines = safe | kept[0][0], mines | kept[1][0]
        return cls(context, safe, mines)

    def advance(self, previous, current, observation):
        if (previous != self.context or current is None
                or type(self.safe) is not frozenset or type(self.mines) is not frozenset):
            return None
        # A single recorded input in the same display epoch is the only bridge.
        if (current.game, current.policy, current.run, current.generation, current.owner,
                current.revision - 1) != (
                previous.game, previous.policy, previous.run, previous.generation,
                previous.owner, previous.revision):
            return None
        hidden = hidden_cells(observation)
        return CertaintyFrame(current, self.safe & hidden, self.mines & hidden)

    def overlays(self):
        if type(self.safe) is not frozenset or type(self.mines) is not frozenset:
            return {}
        return {**{c: CellOverlay(OverlayKind.SAFE) for c in self.safe},
                **{c: CellOverlay(OverlayKind.MINE) for c in self.mines}}

    def overlays_with(self, current):
        """Draw the current result; kept proofs color only what it leaves uncolored.

        Recommendation, probability and status always come from ``current``.
        """
        merged = dict(current)
        for cell, kept in self.overlays().items():
            stated = merged.get(cell)
            if stated is None:
                merged[cell] = kept
            elif stated.kind is None:
                merged[cell] = CellOverlay(kept.kind, stated.recommended, stated.probability)
        return merged


def hidden_cells(observation):
    return frozenset((x, y) for y, row in enumerate(observation)
                     for x, value in enumerate(row) if value == CellState.HIDDEN)
