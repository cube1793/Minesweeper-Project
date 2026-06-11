"""
zini_calculator.py
G.ZiNi calculator scaffolding for immutable board snapshots.

This module intentionally stays outside MinesweeperEngine.  It will grow into
the dynamic G.ZiNi simulation layer, while BoardSnapshot and board_analyzer keep
providing the static board facts.
"""

from dataclasses import dataclass

from board_analyzer import CellClass, analyze_board
from board_snapshot import BoardSnapshot, Coordinate


_UNIT_OPENING = "opening"
_UNIT_ISOLATED = "isolated"


TopLeftKey = tuple[int, int]


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


@dataclass(frozen=True)
class _Static3BvUnit:
    """One static 3BV unit used as input for future G.ZiNi simulation."""

    kind: str
    representative: Coordinate
    cells: frozenset[Coordinate]
    opening_id: int | None = None


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

    _extract_static_3bv_units(snapshot)

    return ZiniResult(clicks=0)


def _extract_static_3bv_units(snapshot: BoardSnapshot) -> tuple[_Static3BvUnit, ...]:
    """
    Extract static 3BV units from a finalized board snapshot.

    Opening units are represented by the top-leftmost zero cell in the opening.
    The cells stored here are only the zero-cell group that identifies the 3BV
    unit; future reveal simulation must still reveal the surrounding border
    ring when an opening is clicked.  Border numbers are not independent 3BV
    units and are intentionally excluded.
    """
    analysis = analyze_board(snapshot)

    opening_cells_by_id: dict[int, list[Coordinate]] = {}
    isolated_units: list[_Static3BvUnit] = []

    for y in range(snapshot.height):
        for x in range(snapshot.width):
            cell_class = analysis.cell_class[y][x]
            coord = (x, y)

            if cell_class == CellClass.OPENING:
                opening_id = analysis.opening_id[y][x]
                opening_cells_by_id.setdefault(opening_id, []).append(coord)
            elif cell_class == CellClass.ISOLATED:
                isolated_units.append(
                    _Static3BvUnit(
                        kind=_UNIT_ISOLATED,
                        representative=coord,
                        cells=frozenset({coord}),
                    )
                )

    opening_units = [
        _Static3BvUnit(
            kind=_UNIT_OPENING,
            representative=min(cells, key=_top_left_key),
            cells=frozenset(cells),
            opening_id=opening_id,
        )
        for opening_id, cells in opening_cells_by_id.items()
    ]

    return tuple(
        sorted(
            [*opening_units, *isolated_units],
            key=lambda unit: _top_left_key(unit.representative),
        )
    )


def _top_left_key(coord: Coordinate) -> TopLeftKey:
    """Return row-major sorting key for a coordinate stored as (x, y)."""
    x, y = coord
    return y, x
