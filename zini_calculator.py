"""
zini_calculator.py
G.ZiNi calculator scaffolding for immutable board snapshots.

This module intentionally stays outside MinesweeperEngine.  It will grow into
the dynamic G.ZiNi simulation layer, while BoardSnapshot and board_analyzer keep
providing the static board facts.
"""

from dataclasses import dataclass

from board_snapshot import BoardSnapshot


@dataclass(frozen=True)
class ZiniMove:
    """Minimal trace entry for tests and manual reference-site validation."""

    action: str
    x: int
    y: int
    premium: int | None
    clicks_added: int


@dataclass(frozen=True)
class ZiniResult:
    """Result returned by G.ZiNi calculations."""

    clicks: int
    moves: tuple[ZiniMove, ...] = ()


def calculate_g_zini(snapshot: BoardSnapshot) -> ZiniResult:
    """
    Calculate G.ZiNi for a finalized board snapshot.

    The full premium/reveal/flag/chord simulation is intentionally left for
    later, smaller diffs.  This first scaffold establishes the public API and
    the finalized-board validation contract.

    Raises:
        ValueError: if mines have not been placed yet.
    """
    if not snapshot.mines_placed:
        raise ValueError("Cannot calculate G.ZiNi before mines are placed.")

    return ZiniResult(clicks=0)
