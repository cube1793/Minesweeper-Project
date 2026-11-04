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
    def capture(cls, context, overlays, observation):
        hidden = hidden_cells(observation)
        return cls(context,
                   frozenset(c for c, o in overlays.items()
                             if c in hidden and o.kind == OverlayKind.SAFE),
                   frozenset(c for c, o in overlays.items()
                             if c in hidden and o.kind == OverlayKind.MINE))

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


def hidden_cells(observation):
    return frozenset((x, y) for y, row in enumerate(observation)
                     for x, value in enumerate(row) if value == CellState.HIDDEN)
