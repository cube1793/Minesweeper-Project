"""
zini_calculator.py
G.ZiNi calculator scaffolding for immutable board snapshots.

This module intentionally stays outside MinesweeperEngine.  It will grow into
the dynamic G.ZiNi simulation layer, while BoardSnapshot and board_analyzer keep
providing the static board facts.
"""

from dataclasses import dataclass

from board_analyzer import BoardAnalysis, CellClass, analyze_board
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


@dataclass(frozen=True)
class _PremiumContext:
    """Static lookup data used while calculating Premium values."""

    analysis: BoardAnalysis
    opening_units_by_id: dict[int, _Static3BvUnit]
    isolated_cells: frozenset[Coordinate]


@dataclass
class _ZiniBoardState:
    """Dynamic board state used by the G.ZiNi simulation."""

    snapshot: BoardSnapshot
    revealed: set[Coordinate]
    flagged_mines: set[Coordinate]

    @classmethod
    def create(cls, snapshot: BoardSnapshot):
        """Create an empty dynamic state for a finalized snapshot."""
        return cls(snapshot=snapshot, revealed=set(), flagged_mines=set())

    def reveal_unit(self, unit: _Static3BvUnit):
        """
        Reveal one static 3BV unit.

        Opening units reveal their zero-cell group plus the surrounding border
        ring.  Isolated units reveal only their representative number cell.
        """
        if unit.kind == _UNIT_OPENING:
            self.revealed.update(_opening_reveal_cells(self.snapshot, unit))
            return

        if unit.kind == _UNIT_ISOLATED:
            self.revealed.add(unit.representative)
            return

        raise ValueError(f"Unknown 3BV unit kind: {unit.kind}")

    def flag_mine(self, coord: Coordinate):
        """
        Mark a known mine as flagged.

        G.ZiNi has unfair prior knowledge, so this state tracks confirmed mine
        flags only.  Non-mine flags are not part of the 1st-pass algorithm.
        """
        if coord not in self.snapshot.mines:
            raise ValueError("G.ZiNi board state can only flag mine coordinates.")
        self.flagged_mines.add(coord)

    def all_safe_cells_revealed(self) -> bool:
        """Return whether every non-mine cell has been revealed."""
        return all(
            coord in self.revealed
            for coord in _safe_cells(self.snapshot)
        )


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


def _build_premium_context(snapshot: BoardSnapshot) -> _PremiumContext:
    """Build static lookup data for Premium calculation."""
    analysis = analyze_board(snapshot)
    units = _extract_static_3bv_units(snapshot)

    return _PremiumContext(
        analysis=analysis,
        opening_units_by_id={
            unit.opening_id: unit
            for unit in units
            if unit.kind == _UNIT_OPENING and unit.opening_id is not None
        },
        isolated_cells=frozenset(
            unit.representative
            for unit in units
            if unit.kind == _UNIT_ISOLATED
        ),
    )


def _calculate_premium(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
) -> int:
    """
    Calculate the G.ZiNi Premium for one non-mine number candidate.

    Premium is an evaluation value for move selection, not a click count.  It
    must be returned as-is, including negative values.  Covered zero cells are
    not Premium candidates in this first-pass implementation.
    """
    if coord in state.snapshot.mines:
        raise ValueError("Cannot calculate Premium for a mine coordinate.")

    x, y = coord
    if state.snapshot.adjacent[y][x] == 0:
        raise ValueError("Premium candidates must be number cells.")

    premium = (
        _count_adjacent_covered_3bv(state, coord, context)
        - _count_adjacent_unflagged_mines(state, coord)
        - 1
    )
    if _is_covered_non_3bv(state, coord, context):
        premium -= 1
    return premium


def _count_adjacent_covered_3bv(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
) -> int:
    """
    Count distinct covered 3BV units adjacent to a candidate cell.

    Only neighbors are considered, so the candidate itself is never counted.
    Opening units are counted only when an adjacent covered zero cell belongs to
    that opening.  Adjacent covered border numbers do not count as opening 3BV
    by themselves, and repeated zero cells from the same opening count once.

    The later reveal/chord simulation must use the same adjacent-zero rule:
    if Premium counts an opening here, the move must actually reveal that
    opening's zero-cell unit; if Premium does not count it here, later logic
    must not assume the move solved it.
    """
    opening_ids: set[int] = set()
    isolated_cells: set[Coordinate] = set()

    for neighbor in _neighbors(state.snapshot, coord):
        if neighbor in state.revealed or neighbor in state.snapshot.mines:
            continue

        nx, ny = neighbor
        cell_class = context.analysis.cell_class[ny][nx]
        if cell_class == CellClass.OPENING:
            opening_id = context.analysis.opening_id[ny][nx]
            if opening_id in context.opening_units_by_id:
                opening_ids.add(opening_id)
        elif cell_class == CellClass.ISOLATED and neighbor in context.isolated_cells:
            isolated_cells.add(neighbor)

    return len(opening_ids) + len(isolated_cells)


def _count_adjacent_unflagged_mines(
    state: _ZiniBoardState,
    coord: Coordinate,
) -> int:
    """Count adjacent mines that have not already been flagged."""
    return sum(
        1
        for neighbor in _neighbors(state.snapshot, coord)
        if neighbor in state.snapshot.mines and neighbor not in state.flagged_mines
    )


def _is_covered_non_3bv(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
) -> bool:
    """Return whether coord is a covered border number cell."""
    if coord in state.revealed:
        return False

    x, y = coord
    return context.analysis.cell_class[y][x] == CellClass.BORDER


def _top_left_key(coord: Coordinate) -> TopLeftKey:
    """Return row-major sorting key for a coordinate stored as (x, y)."""
    x, y = coord
    return y, x


def _opening_reveal_cells(
    snapshot: BoardSnapshot,
    unit: _Static3BvUnit,
) -> frozenset[Coordinate]:
    """Return zero cells and adjacent safe border cells revealed by an opening."""
    reveal_cells = set(unit.cells)
    for coord in unit.cells:
        for neighbor in _neighbors(snapshot, coord):
            if neighbor not in snapshot.mines:
                reveal_cells.add(neighbor)
    return frozenset(reveal_cells)


def _safe_cells(snapshot: BoardSnapshot):
    """Yield all non-mine coordinates in row-major order."""
    for y in range(snapshot.height):
        for x in range(snapshot.width):
            coord = (x, y)
            if coord not in snapshot.mines:
                yield coord


def _neighbors(snapshot: BoardSnapshot, coord: Coordinate):
    """Yield in-bounds 8-way neighbor coordinates for a coordinate."""
    x, y = coord
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < snapshot.width and 0 <= ny < snapshot.height:
                yield nx, ny
