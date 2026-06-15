"""Shared ZiNi board fixtures and replay helpers."""

from board_snapshot import BoardSnapshot
from zini_core import (
    _ZiniBoardState,
    _apply_premium_candidate,
    _build_premium_context,
    _click_fallback_cell,
    _find_fallback_click_targets,
    _find_premium_candidates,
)


def _move_signature(result):
    return tuple(
        (move.action, move.x, move.y, move.premium, move.clicks_added)
        for move in result.moves
    )


def _advanced_search_snapshot():
    return BoardSnapshot(
        width=4,
        height=4,
        num_mines=3,
        mines_placed=True,
        mines=frozenset({(2, 0), (2, 2), (3, 3)}),
        adjacent=(
            (0, 1, 0, 1),
            (0, 2, 2, 2),
            (0, 1, 0, 2),
            (0, 1, 2, 0),
        ),
    )


def _board_c_snapshot():
    return BoardSnapshot(
        width=9,
        height=9,
        num_mines=10,
        mines_placed=True,
        mines=frozenset(
            {
                (1, 0),
                (6, 0),
                (3, 1),
                (8, 2),
                (0, 3),
                (5, 4),
                (2, 5),
                (7, 6),
                (4, 7),
                (0, 8),
            }
        ),
        adjacent=(
            (1, 0, 2, 1, 1, 1, 0, 1, 0),
            (1, 1, 2, 0, 1, 1, 1, 2, 1),
            (1, 1, 1, 1, 1, 0, 0, 1, 0),
            (0, 1, 0, 0, 1, 1, 1, 1, 1),
            (1, 2, 1, 1, 1, 0, 1, 0, 0),
            (0, 1, 0, 1, 1, 1, 2, 1, 1),
            (0, 1, 1, 2, 1, 1, 1, 0, 1),
            (1, 1, 0, 1, 0, 1, 1, 1, 1),
            (0, 1, 0, 1, 1, 1, 0, 0, 0),
        ),
    )


def _replay_zini_result(snapshot, result):
    state = _ZiniBoardState.create(snapshot)
    context = _build_premium_context(snapshot)

    for expected in result.moves:
        candidates = _find_premium_candidates(state, context)
        best_premium = max(
            (candidate.premium for candidate in candidates),
            default=None,
        )
        coord = (expected.x, expected.y)

        if expected.action == "fallback_click":
            if best_premium is not None and best_premium >= 0:
                raise AssertionError(
                    "Fallback move used with non-negative Premium."
                )
            if coord not in _find_fallback_click_targets(state, context):
                raise AssertionError("Fallback move target is unavailable.")
            actual = _click_fallback_cell(state, coord, context)
        else:
            matching = tuple(
                candidate
                for candidate in candidates
                if candidate.coord == coord
            )
            if len(matching) != 1:
                raise AssertionError("Premium move target is unavailable.")
            actual = _apply_premium_candidate(state, matching[0], context)

        if actual != expected:
            raise AssertionError("Replayed move does not match result trace.")

    return state


_EXPERT_SEED1003_MINES = frozenset(
    {
        (0, 0), (12, 0), (13, 0), (16, 0), (0, 1), (1, 1),
        (2, 1), (3, 1), (14, 1), (19, 1), (7, 2), (8, 2),
        (9, 2), (11, 2), (16, 2), (2, 3), (10, 3), (11, 3),
        (13, 3), (23, 3), (26, 3), (27, 3), (2, 4), (3, 4),
        (8, 4), (10, 4), (11, 4), (17, 4), (18, 4), (1, 5),
        (13, 5), (21, 5), (23, 5), (24, 5), (25, 5), (4, 6),
        (6, 6), (13, 6), (14, 6), (17, 6), (18, 6), (20, 6),
        (26, 6), (27, 6), (8, 7), (10, 7), (11, 7), (12, 7),
        (18, 7), (21, 7), (22, 7), (27, 7), (3, 8), (14, 8),
        (17, 8), (19, 8), (20, 8), (21, 8), (5, 9), (6, 9),
        (9, 9), (11, 9), (12, 9), (16, 9), (27, 9), (28, 9),
        (17, 10), (26, 10), (29, 10), (13, 11), (16, 11),
        (19, 11), (20, 11), (22, 11), (25, 11), (27, 11),
        (7, 12), (9, 12), (12, 12), (20, 12), (26, 12),
        (1, 13), (4, 13), (17, 13), (26, 13), (1, 14),
        (11, 14), (25, 14), (27, 14), (1, 15), (9, 15),
        (12, 15), (13, 15), (14, 15), (18, 15), (21, 15),
        (22, 15), (23, 15), (28, 15),
    }
)


_EXPERT_SEED1003_120_TRACE = (
    ("click", 19, 14, 5, 1),
    ("click", 5, 7, 3, 1),
    ("click", 8, 9, 5, 1),
    ("flag_chord", 8, 9, 5, 2),
    ("click", 14, 9, 5, 1),
    ("flag_chord", 14, 9, 5, 2),
    ("click", 11, 11, 5, 1),
    ("flag_chord", 11, 11, 5, 2),
    ("flag_chord", 19, 14, 5, 2),
    ("click", 18, 1, 4, 1),
    ("flag_chord", 18, 1, 4, 2),
    ("click", 8, 6, 4, 1),
    ("flag_chord", 8, 6, 4, 2),
    ("click", 11, 5, 3, 1),
    ("flag_chord", 11, 5, 3, 3),
    ("click", 19, 10, 3, 1),
    ("click", 16, 6, 3, 1),
    ("flag_chord", 16, 6, 3, 2),
    ("flag_chord", 5, 7, 3, 3),
    ("flag_chord", 19, 10, 3, 3),
    ("click", 10, 14, 3, 1),
    ("flag_chord", 10, 14, 3, 3),
    ("click", 13, 2, 2, 1),
    ("flag_chord", 15, 8, 0, 2),
    ("flag_chord", 13, 2, 2, 3),
    ("flag_chord", 14, 3, 2, 1),
    ("click", 24, 3, 2, 1),
    ("flag_chord", 24, 3, 2, 2),
    ("click", 19, 4, 2, 1),
    ("flag_chord", 19, 4, 3, 2),
    ("click", 2, 6, 2, 1),
    ("flag_chord", 2, 6, 3, 2),
    ("flag_chord", 8, 10, 2, 1),
    ("flag_chord", 20, 10, 2, 1),
    ("flag_chord", 18, 11, 2, 2),
    ("click", 24, 12, 2, 1),
    ("flag_chord", 24, 12, 3, 2),
    ("click", 15, 0, 1, 1),
    ("flag_chord", 15, 0, 1, 2),
    ("flag_chord", 15, 10, 1, 2),
    ("flag_chord", 11, 13, 1, 1),
    ("click", 25, 15, 1, 1),
    ("flag_chord", 25, 15, 1, 2),
    ("click", 4, 1, 0, 1),
    ("flag_chord", 4, 1, 1, 2),
    ("flag_chord", 4, 2, 0, 1),
    ("flag_chord", 18, 2, 0, 1),
    ("click", 0, 4, 0, 1),
    ("flag_chord", 0, 4, 1, 1),
    ("click", 27, 4, 0, 1),
    ("flag_chord", 27, 4, 0, 3),
    ("flag_chord", 10, 5, 0, 1),
    ("flag_chord", 9, 8, 0, 2),
    ("flag_chord", 16, 10, 0, 1),
    ("click", 28, 11, 0, 1),
    ("flag_chord", 28, 11, 1, 3),
    ("flag_chord", 1, 12, 0, 2),
    ("flag_chord", 2, 12, 0, 1),
    ("flag_chord", 28, 12, 0, 1),
    ("fallback_click", 1, 0, None, 1),
    ("fallback_click", 2, 0, None, 1),
    ("fallback_click", 2, 2, None, 1),
    ("fallback_click", 10, 2, None, 1),
    ("fallback_click", 8, 3, None, 1),
    ("fallback_click", 9, 3, None, 1),
    ("fallback_click", 22, 5, None, 1),
    ("fallback_click", 19, 6, None, 1),
    ("fallback_click", 21, 6, None, 1),
    ("fallback_click", 22, 6, None, 1),
    ("fallback_click", 13, 7, None, 1),
    ("fallback_click", 19, 7, None, 1),
    ("fallback_click", 20, 7, None, 1),
    ("fallback_click", 24, 7, None, 1),
    ("fallback_click", 11, 8, None, 1),
    ("fallback_click", 12, 8, None, 1),
    ("fallback_click", 18, 8, None, 1),
    ("fallback_click", 27, 8, None, 1),
    ("fallback_click", 29, 9, None, 1),
    ("fallback_click", 26, 11, None, 1),
    ("fallback_click", 8, 12, None, 1),
    ("fallback_click", 14, 13, None, 1),
    ("fallback_click", 0, 14, None, 1),
    ("fallback_click", 6, 14, None, 1),
    ("fallback_click", 0, 15, None, 1),
    ("fallback_click", 16, 15, None, 1),
    ("fallback_click", 27, 15, None, 1),
    ("fallback_click", 29, 15, None, 1),
)


def _expert_seed1003_snapshot():
    width = 30
    height = 16
    mines = _EXPERT_SEED1003_MINES

    if len(mines) != 99:
        raise AssertionError("Expert seed 1003 fixture must contain 99 mines.")
    if any(not (0 <= x < width and 0 <= y < height) for x, y in mines):
        raise AssertionError("Expert seed 1003 mine is outside the 30x16 board.")

    adjacent = tuple(
        tuple(
            0
            if (x, y) in mines
            else sum(
                (nx, ny) in mines
                for ny in range(max(0, y - 1), min(height, y + 2))
                for nx in range(max(0, x - 1), min(width, x + 2))
                if (nx, ny) != (x, y)
            )
            for x in range(width)
        )
        for y in range(height)
    )

    return BoardSnapshot(
        width=width,
        height=height,
        num_mines=99,
        mines_placed=True,
        mines=mines,
        adjacent=adjacent,
    )
