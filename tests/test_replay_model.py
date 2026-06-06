import unittest

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
