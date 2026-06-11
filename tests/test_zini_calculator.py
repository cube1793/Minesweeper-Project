import unittest

from board_snapshot import BoardSnapshot
from zini_calculator import (
    ZiniResult,
    _extract_static_3bv_units,
    _build_premium_context,
    _find_premium_candidates,
    _ZiniBoardState,
    _calculate_premium,
    _select_best_premium_candidate,
    calculate_g_zini,
)


class ZiniCalculatorTests(unittest.TestCase):
    def test_unplaced_snapshot_is_not_calculable(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini(snapshot)

    def test_finalized_snapshot_returns_result_shell(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        result = calculate_g_zini(snapshot)

        self.assertIsInstance(result, ZiniResult)
        self.assertIsInstance(result.clicks, int)
        self.assertIsInstance(result.moves, tuple)

    def test_static_units_empty_board_has_one_opening(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].kind, "opening")
        self.assertEqual(units[0].representative, (0, 0))
        self.assertEqual(units[0].cells, frozenset({(0, 0)}))

    def test_static_units_center_mine_has_eight_isolated_numbers(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 8)
        self.assertTrue(all(unit.kind == "isolated" for unit in units))
        self.assertEqual(
            [unit.representative for unit in units],
            [
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            ],
        )

    def test_static_units_corner_mine_has_one_opening_represented_top_left(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].kind, "opening")
        self.assertEqual(units[0].representative, (2, 0))
        self.assertEqual(
            units[0].cells,
            frozenset({(2, 0), (2, 1), (0, 2), (1, 2), (2, 2)}),
        )
        self.assertEqual(units[0].opening_id, 0)

    def test_dynamic_state_reveals_single_cell_opening_and_completes_board(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(state.revealed, {(0, 0)})
        self.assertTrue(state.all_safe_cells_revealed())

    def test_dynamic_state_reveals_opening_zero_cells_and_border_ring(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(
            state.revealed,
            {
                (1, 0),
                (2, 0),
                (0, 1),
                (1, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            },
        )
        self.assertTrue(state.all_safe_cells_revealed())

    def test_dynamic_state_reveals_isolated_number_only(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(unit.kind, "isolated")
        self.assertEqual(unit.representative, (0, 0))
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertFalse(state.all_safe_cells_revealed())

    def test_dynamic_state_flags_mine_coordinate(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)

        state.flag_mine((1, 0))

        self.assertEqual(state.flagged_mines, {(1, 0)})

    def test_dynamic_state_rejects_non_mine_flag(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)

        with self.assertRaises(ValueError):
            state.flag_mine((0, 0))

    def test_premium_counts_adjacent_unflagged_mines_without_counting_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Adjacent covered isolated cells: (1, 0), (0, 1). The covered
        # isolated candidate (0, 0) is not adjacent to itself and is not
        # counted. Adjacent unflagged mines: (1, 1).
        self.assertEqual(premium, 0)

    def test_premium_ignores_already_flagged_adjacent_mines(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        self.assertEqual(premium, 1)

    def test_premium_deduplicates_multiple_adjacent_zero_cells(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (1, 1), context)

        # Candidate (1, 1) touches several zero cells from the same opening,
        # two covered BORDER numbers, and one unflagged mine. The opening is
        # counted once, BORDER numbers are not independent 3BV, and the covered
        # BORDER candidate receives the non-3BV penalty.
        self.assertEqual(premium, -2)

    def test_premium_excludes_border_only_opening_contact(self):
        snapshot = BoardSnapshot(
            width=4,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 1)}),
            adjacent=((1, 1, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Candidate (0, 0) touches only BORDER numbers from the opening at its
        # east side, not any zero cell from that opening. The opening must not
        # be counted as adjacent covered 3BV. The negative value is intentional
        # and must not be clamped to zero.
        self.assertEqual(premium, -2)

    def test_premium_applies_covered_border_penalty_only_while_covered(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        covered_premium = _calculate_premium(state, (1, 1), context)
        state.revealed.add((1, 1))
        uncovered_premium = _calculate_premium(state, (1, 1), context)

        self.assertEqual(covered_premium, -2)
        self.assertEqual(uncovered_premium, -1)

    def test_premium_excludes_already_revealed_adjacent_3bv(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Only (0, 1) remains as adjacent covered 3BV. The adjacent mine is
        # still unflagged, so the Premium is negative and remains unclamped.
        self.assertEqual(premium, -1)

    def test_select_best_candidate_uses_highest_premium_and_top_left_tie_break(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (1, 0))
        self.assertEqual(candidate.premium, 2)

    def test_select_best_candidate_uses_flagged_mines_in_premium(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (1, 0))
        self.assertEqual(candidate.premium, 3)

    def test_select_best_candidate_tie_breaks_by_y_then_x(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1), (1, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (0, 0))
        self.assertEqual(candidate.premium, 0)

    def test_find_premium_candidates_excludes_covered_zero_cells(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidates = _find_premium_candidates(state, context)

        self.assertEqual(
            {candidate.coord for candidate in candidates},
            {(1, 0), (0, 1), (1, 1)},
        )

    def test_select_best_candidate_allows_negative_premium(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (0, 0))
        self.assertEqual(candidate.premium, -2)

    def test_select_best_candidate_returns_none_when_no_number_candidates_exist(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        self.assertEqual(_find_premium_candidates(state, context), ())
        self.assertIsNone(_select_best_premium_candidate(state, context))

    def test_select_best_candidate_returns_none_when_board_is_solved(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.update(
            (x, y)
            for y in range(snapshot.height)
            for x in range(snapshot.width)
            if (x, y) not in snapshot.mines
        )
        context = _build_premium_context(snapshot)

        self.assertIsNone(_select_best_premium_candidate(state, context))


if __name__ == "__main__":
    unittest.main()
