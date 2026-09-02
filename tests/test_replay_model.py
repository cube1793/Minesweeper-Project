import unittest
from math import inf, nan

from board_analyzer import analyze_board
from core_engine import MinesweeperEngine
from replay_model import (
    ACTION_FLAG,
    ACTION_OPEN,
    ReplayBoard,
    ReplayData,
    ReplayEvent,
    SOURCE_HUMAN,
)


class ReplayModelTests(unittest.TestCase):
    def test_replay_data_keeps_source_type_at_game_level(self):
        board = ReplayBoard(
            width=3,
            height=3,
            num_mines=1,
            mine_positions={(1, 1)},
        )
        event = ReplayEvent(
            elapsed_time=0.25,
            x=0,
            y=0,
            action=ACTION_OPEN,
        )

        replay = ReplayData(
            board=board,
            events=[event],
            source_type=SOURCE_HUMAN,
        )

        self.assertEqual(replay.source_type, SOURCE_HUMAN)
        self.assertEqual(replay.events, (event,))
        self.assertFalse(hasattr(event, "source_type"))
        self.assertEqual(board.mine_positions, frozenset({(1, 1)}))

    def test_replay_model_rejects_invalid_action_and_event_bounds(self):
        with self.assertRaises(ValueError):
            ReplayEvent(elapsed_time=0.0, x=0, y=0, action="BAD")

        board = ReplayBoard(
            width=3,
            height=3,
            num_mines=1,
            mine_positions={(1, 1)},
        )
        event = ReplayEvent(
            elapsed_time=0.0,
            x=3,
            y=0,
            action=ACTION_FLAG,
        )

        with self.assertRaises(ValueError):
            ReplayData(board=board, events=(event,))

    def test_replay_board_validates_configuration_types_and_bounds(self):
        valid_zero_mine_board = ReplayBoard(
            width=1,
            height=1,
            num_mines=0,
            mine_positions=(),
        )
        self.assertEqual(valid_zero_mine_board.mine_positions, frozenset())

        invalid_configurations = (
            (True, 3, 1),
            (3, True, 1),
            (3, 3, True),
            (3.5, 3, 1),
            (3, 3.5, 1),
            (3, 3, 1.0),
            ("3", 3, 1),
            (3, "3", 1),
            (3, 3, "1"),
            (0, 3, 1),
            (3, 0, 1),
            (-1, 3, 1),
            (3, -1, 1),
            (3, 3, -1),
            (3, 3, 9),
        )
        for width, height, num_mines in invalid_configurations:
            with self.subTest(
                width=width,
                height=height,
                num_mines=num_mines,
            ):
                with self.assertRaises(ValueError):
                    ReplayBoard(
                        width=width,
                        height=height,
                        num_mines=num_mines,
                        mine_positions=(),
                    )

    def test_replay_board_validates_mine_coordinate_types_bounds_and_count(self):
        invalid_layouts = (
            (1, {(0.5, 1)}),
            (1, {(True, 1)}),
            (1, [([0], 1)]),
            (1, {(-1, 1)}),
            (1, {(3, 1)}),
            (2, {(1, 1)}),
        )
        for num_mines, mine_positions in invalid_layouts:
            with self.subTest(
                num_mines=num_mines,
                mine_positions=mine_positions,
            ):
                with self.assertRaises(ValueError):
                    ReplayBoard(
                        width=3,
                        height=3,
                        num_mines=num_mines,
                        mine_positions=mine_positions,
                    )

    def test_replay_event_validates_coordinates_and_elapsed_time(self):
        integer_time = ReplayEvent(
            elapsed_time=1,
            x=0,
            y=0,
            action=ACTION_OPEN,
        )
        float_time = ReplayEvent(
            elapsed_time=1.5,
            x=0,
            y=0,
            action=ACTION_OPEN,
        )
        self.assertIs(type(integer_time.elapsed_time), int)
        self.assertIs(type(float_time.elapsed_time), float)

        invalid_events = (
            (0.0, True, 0),
            (0.0, 0, True),
            (0.0, 0.5, 0),
            (0.0, 0, 0.5),
            (0.0, -1, 0),
            (0.0, 0, -1),
            (True, 0, 0),
            ("1.0", 0, 0),
            (nan, 0, 0),
            (inf, 0, 0),
            (-inf, 0, 0),
            (-0.1, 0, 0),
        )
        for elapsed_time, x, y in invalid_events:
            with self.subTest(elapsed_time=elapsed_time, x=x, y=y):
                with self.assertRaises(ValueError):
                    ReplayEvent(
                        elapsed_time=elapsed_time,
                        x=x,
                        y=y,
                        action=ACTION_OPEN,
                    )

    def test_replay_event_preserves_very_large_integer_elapsed_time(self):
        elapsed_time = 10**400

        event = ReplayEvent(
            elapsed_time=elapsed_time,
            x=0,
            y=0,
            action=ACTION_OPEN,
        )

        self.assertEqual(event.elapsed_time, elapsed_time)
        self.assertIs(type(event.elapsed_time), int)

    def test_replay_data_allows_equal_and_rejects_decreasing_timestamps(self):
        board = ReplayBoard(
            width=3,
            height=3,
            num_mines=1,
            mine_positions={(1, 1)},
        )
        first = ReplayEvent(2.0, 0, 0, ACTION_OPEN)
        same_time = ReplayEvent(2.0, 1, 0, ACTION_FLAG)
        earlier = ReplayEvent(1.0, 2, 0, ACTION_OPEN)

        replay = ReplayData(board=board, events=(first, same_time))
        self.assertEqual(replay.events, (first, same_time))

        with self.assertRaises(ValueError):
            ReplayData(board=board, events=(first, earlier))

    def test_reset_with_mines_restores_snapshot_adjacency_and_analysis(self):
        engine = MinesweeperEngine(width=9, height=9, num_mines=10)
        mine_positions = {(1, 1)}

        observation = engine.reset_with_mines(
            width=3,
            height=3,
            num_mines=1,
            mine_positions=mine_positions,
        )

        snapshot = engine.get_board_snapshot()
        self.assertEqual(snapshot.width, 3)
        self.assertEqual(snapshot.height, 3)
        self.assertEqual(snapshot.num_mines, 1)
        self.assertTrue(snapshot.mines_placed)
        self.assertEqual(snapshot.mines, frozenset(mine_positions))
        self.assertEqual(
            snapshot.adjacent,
            (
                (1, 1, 1),
                (1, 0, 1),
                (1, 1, 1),
            ),
        )
        self.assertTrue(
            all(value == -2 for row in observation for value in row)
        )

        analysis = analyze_board(snapshot)
        self.assertEqual(engine._total_3bv, analysis.total_3bv)
        self.assertEqual(engine._total_ops, analysis.total_ops)
        self.assertEqual(engine._opening_id, [list(row) for row in analysis.opening_id])
        self.assertEqual(
            engine._cell_class,
            [
                [None if cell_class is None else int(cell_class) for cell_class in row]
                for row in analysis.cell_class
            ],
        )

    def test_reset_with_mines_rejects_invalid_mine_layout(self):
        engine = MinesweeperEngine(width=3, height=3, num_mines=1)

        with self.assertRaises(ValueError):
            engine.reset_with_mines(
                width=3,
                height=3,
                num_mines=1,
                mine_positions={(3, 0)},
            )

        with self.assertRaises(ValueError):
            engine.reset_with_mines(
                width=3,
                height=3,
                num_mines=2,
                mine_positions={(1, 1)},
            )


if __name__ == "__main__":
    unittest.main()
