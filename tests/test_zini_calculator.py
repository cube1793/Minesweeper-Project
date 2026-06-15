import unittest

from board_snapshot import BoardSnapshot
from zini_calculator import (
    ZiniResult,
    ZiniSearchResult,
    calculate_g_zini,
    calculate_g_zini_min_ties,
    calculate_g_zini_min_ties_bounded,
)
from tests.zini_fixtures import _move_signature


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

    def test_calculate_g_zini_empty_board_returns_one_fallback_click(self):
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
        self.assertIsInstance(result.moves, tuple)
        self.assertEqual(result.clicks, 1)
        self.assertEqual(len(result.moves), 1)
        self.assertEqual(_move_signature(result), (("fallback_click", 0, 0, None, 1),))
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_two_cell_mine_board_uses_negative_premium_fallback(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )

        result = calculate_g_zini(snapshot)

        self.assertEqual(result.clicks, 1)
        self.assertEqual(len(result.moves), 1)
        self.assertEqual(_move_signature(result), (("fallback_click", 0, 0, None, 1),))
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_center_mine_board_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )

        result = calculate_g_zini(snapshot)

        self.assertEqual(result.clicks, 5)
        self.assertEqual(len(result.moves), 4)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 1, 0, 2, 1),
                ("flag_chord", 1, 0, 2, 2),
                ("flag_chord", 0, 1, 1, 1),
                ("flag_chord", 2, 1, 0, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )
        self.assertTrue(all(move.clicks_added > 0 for move in result.moves))

    def test_calculate_g_zini_corner_opening_board_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )

        result = calculate_g_zini(snapshot)

        self.assertEqual(result.clicks, 1)
        self.assertEqual(len(result.moves), 1)
        self.assertEqual(
            _move_signature(result),
            (
                ("fallback_click", 2, 0, None, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )
        self.assertTrue(all(move.clicks_added > 0 for move in result.moves))

    def test_calculate_g_zini_min_ties_rejects_unplaced_snapshot(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties(snapshot)

    def test_calculate_g_zini_min_ties_d1_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=5,
            height=5,
            num_mines=2,
            mines_placed=True,
            mines=frozenset({(1, 0), (1, 3)}),
            adjacent=(
                (1, 0, 1, 0, 0),
                (1, 1, 1, 0, 0),
                (1, 1, 1, 0, 0),
                (1, 0, 1, 0, 0),
                (1, 1, 1, 0, 0),
            ),
        )

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 6)
        self.assertEqual(len(result.moves), 5)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 0, 2, 2, 1),
                ("flag_chord", 0, 2, 2, 2),
                ("flag_chord", 0, 3, 1, 1),
                ("fallback_click", 0, 0, None, 1),
                ("fallback_click", 3, 0, None, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_min_ties_d2_matches_expected_trace(self):
        snapshot = BoardSnapshot(
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

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 5)
        self.assertEqual(len(result.moves), 3)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 2, 1, 0, 1),
                ("flag_chord", 2, 1, 0, 3),
                ("flag_chord", 1, 2, 1, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_min_ties_d3_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=4,
            height=4,
            num_mines=3,
            mines_placed=True,
            mines=frozenset({(3, 0), (2, 1), (2, 3)}),
            adjacent=(
                (0, 1, 2, 0),
                (0, 1, 0, 2),
                (0, 2, 2, 2),
                (0, 1, 0, 1),
            ),
        )

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 5)
        self.assertEqual(len(result.moves), 3)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 1, 1, 0, 1),
                ("flag_chord", 1, 1, 1, 2),
                ("flag_chord", 2, 2, 1, 2),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_min_ties_board_c_matches_expected_trace(self):
        snapshot = BoardSnapshot(
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

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 16)
        self.assertEqual(len(result.moves), 13)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 1, 1, 3, 1),
                ("flag_chord", 1, 1, 3, 2),
                ("click", 4, 6, 2, 1),
                ("flag_chord", 4, 6, 2, 2),
                ("flag_chord", 5, 7, 2, 1),
                ("click", 4, 1, 1, 1),
                ("flag_chord", 4, 1, 2, 2),
                ("flag_chord", 2, 2, 0, 1),
                ("flag_chord", 3, 7, 0, 1),
                ("fallback_click", 8, 0, None, 1),
                ("fallback_click", 7, 4, None, 1),
                ("fallback_click", 0, 5, None, 1),
                ("fallback_click", 8, 6, None, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_bounded_min_ties_finishes_exactly_on_small_board(self):
        snapshot = BoardSnapshot(
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

        search = calculate_g_zini_min_ties_bounded(snapshot)

        self.assertIsInstance(search, ZiniSearchResult)
        self.assertTrue(search.exact)
        self.assertFalse(search.timed_out)
        self.assertFalse(search.state_limited)
        self.assertEqual(search.result.clicks, 5)
        self.assertEqual(search.best_clicks, 5)
        self.assertEqual(search.deterministic_clicks, 6)
        self.assertGreaterEqual(search.elapsed_seconds, 0)
        self.assertGreater(search.unique_states, 0)
        self.assertGreater(search.search_calls, 0)
        self.assertEqual(
            search.result.clicks,
            sum(move.clicks_added for move in search.result.moves),
        )

    def test_bounded_min_ties_stops_at_state_limit(self):
        snapshot = BoardSnapshot(
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

        search = calculate_g_zini_min_ties_bounded(snapshot, max_states=1)

        self.assertFalse(search.exact)
        self.assertFalse(search.timed_out)
        self.assertTrue(search.state_limited)
        self.assertEqual(search.unique_states, 1)
        self.assertLessEqual(
            search.result.clicks,
            search.deterministic_clicks,
        )

    def test_bounded_min_ties_stops_at_time_limit(self):
        snapshot = BoardSnapshot(
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

        search = calculate_g_zini_min_ties_bounded(snapshot, max_seconds=0.0)

        self.assertFalse(search.exact)
        self.assertTrue(search.timed_out)
        self.assertFalse(search.state_limited)
        self.assertEqual(search.unique_states, 0)
        self.assertLessEqual(
            search.result.clicks,
            search.deterministic_clicks,
        )

    def test_bounded_min_ties_rejects_unplaced_snapshot(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties_bounded(snapshot)

    def test_bounded_min_ties_rejects_negative_seconds(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties_bounded(snapshot, max_seconds=-1)

    def test_bounded_min_ties_rejects_negative_states(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties_bounded(snapshot, max_states=-1)


if __name__ == "__main__":
    unittest.main()
