"""
board_analyzer.py
Pure board analysis helpers for static Minesweeper metrics.

The analyzer consumes an immutable BoardSnapshot and returns immutable analysis
data.  It does not know about UI state, click counters, timers, or game flow.
"""

from collections import deque
from dataclasses import dataclass
from enum import IntEnum

from board_snapshot import BoardSnapshot


class CellClass(IntEnum):
    """Static safe-cell classification used by 3BV/Ops analysis."""

    OPENING = 0
    BORDER = 1
    ISOLATED = 2


CellClassGrid = tuple[tuple[CellClass | None, ...], ...]
OpeningIdGrid = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class BoardAnalysis:
    """Immutable result of static board analysis."""

    opening_id: OpeningIdGrid
    cell_class: CellClassGrid
    total_3bv: int
    total_ops: int


def analyze_board(snapshot: BoardSnapshot) -> BoardAnalysis:
    """
    Analyze a finalized board and calculate static 3BV/Ops denominators.

    Raises:
        ValueError: if mines have not been placed yet.
    """
    if not snapshot.mines_placed:
        raise ValueError("Cannot analyze a board before mines are placed.")

    opening_id = [[-1] * snapshot.width for _ in range(snapshot.height)]
    cell_class = [[None] * snapshot.width for _ in range(snapshot.height)]

    group_id = 0
    for y in range(snapshot.height):
        for x in range(snapshot.width):
            if (x, y) in snapshot.mines:
                continue
            if snapshot.adjacent[y][x] != 0:
                continue
            if opening_id[y][x] != -1:
                continue
            _flood_mark_opening(snapshot, opening_id, x, y, group_id)
            group_id += 1

    total_ops = group_id

    isolated_count = 0
    for y in range(snapshot.height):
        for x in range(snapshot.width):
            if (x, y) in snapshot.mines:
                cell_class[y][x] = None
                continue
            if snapshot.adjacent[y][x] == 0:
                cell_class[y][x] = CellClass.OPENING
                continue

            touches_opening = any(
                snapshot.adjacent[ny][nx] == 0 and (nx, ny) not in snapshot.mines
                for nx, ny in _neighbors(snapshot, x, y)
            )
            if touches_opening:
                cell_class[y][x] = CellClass.BORDER
            else:
                cell_class[y][x] = CellClass.ISOLATED
                isolated_count += 1

    return BoardAnalysis(
        opening_id=tuple(tuple(row) for row in opening_id),
        cell_class=tuple(tuple(row) for row in cell_class),
        total_3bv=total_ops + isolated_count,
        total_ops=total_ops,
    )


def _flood_mark_opening(
    snapshot: BoardSnapshot,
    opening_id: list[list[int]],
    start_x: int,
    start_y: int,
    group_id: int,
):
    """Mark one connected zero-adjacent opening group using 8-way BFS."""
    queue = deque([(start_x, start_y)])
    opening_id[start_y][start_x] = group_id
    while queue:
        x, y = queue.popleft()
        for nx, ny in _neighbors(snapshot, x, y):
            if (nx, ny) in snapshot.mines:
                continue
            if snapshot.adjacent[ny][nx] != 0:
                continue
            if opening_id[ny][nx] != -1:
                continue
            opening_id[ny][nx] = group_id
            queue.append((nx, ny))


def _neighbors(snapshot: BoardSnapshot, x: int, y: int):
    """Yield in-bounds 8-way neighbor coordinates."""
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < snapshot.width and 0 <= ny < snapshot.height:
                yield nx, ny
