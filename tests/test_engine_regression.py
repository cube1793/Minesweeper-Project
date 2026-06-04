import unittest
from dataclasses import FrozenInstanceError

from core_engine import Action, CellState, GameStatus, MinesweeperEngine


class MinesweeperEngineRegressionTests(unittest.TestCase):
    def test_new_game_stats_and_snapshot_before_mines_are_placed(self):
        engine = MinesweeperEngine(width=9, height=9, num_mines=10)

        observation = engine.get_observation()
        self.assertEqual(len(observation), 9)
        self.assertTrue(
            all(
                value == CellState.HIDDEN.value
                for row in observation
                for value in row
            )
        )

        stats = engine.get_stats()
        self.assertEqual(stats["bbbv"], "-/-")
        self.assertEqual(stats["ops"], "-/-")
        self.assertEqual(stats["clicks"], "0")
        self.assertEqual(stats["left"], "0")
        self.assertEqual(stats["right"], "0")
        self.assertEqual(stats["chord"], "0")

        snapshot = engine.get_board_snapshot()
        self.assertEqual(snapshot.width, 9)
        self.assertEqual(snapshot.height, 9)
        self.assertEqual(snapshot.num_mines, 10)
        self.assertFalse(snapshot.mines_placed)
        self.assertEqual(snapshot.mines, frozenset())
        self.assertIsInstance(snapshot.mines, frozenset)
        self.assertIsInstance(snapshot.adjacent, tuple)
        self.assertTrue(all(isinstance(row, tuple) for row in snapshot.adjacent))
        self.assertTrue(
            all(value == 0 for row in snapshot.adjacent for value in row)
        )

        with self.assertRaises(FrozenInstanceError):
            snapshot.width = 99
        with self.assertRaises(AttributeError):
            snapshot.mines.add((0, 0))
        with self.assertRaises(TypeError):
            snapshot.adjacent[0][0] = 1

    def test_open_first_action_preserves_basic_flow_and_snapshot_copy(self):
        engine = MinesweeperEngine(width=9, height=9, num_mines=10)

        observation, reward, terminated, truncated, info = engine.step(
            4, 4, Action.OPEN
        )

        self.assertFalse(truncated)
        self.assertEqual(info["status"], engine.status)
        self.assertEqual(terminated, engine.status != GameStatus.PLAYING)
        self.assertIn(engine.status, (GameStatus.PLAYING, GameStatus.WON))
        self.assertEqual(reward, 1.0 if terminated else 0.01)
        self.assertEqual(info["stats"]["clicks"], "1")
        self.assertEqual(info["stats"]["left"], "1")
        self.assertEqual(info["stats"]["right"], "0")
        self.assertEqual(info["stats"]["chord"], "0")

        snapshot = engine.get_board_snapshot()
        self.assertTrue(snapshot.mines_placed)
        self.assertEqual(len(snapshot.mines), 10)
        self.assertEqual(len(snapshot.adjacent), 9)
        self.assertTrue(all(len(row) == 9 for row in snapshot.adjacent))

        safe_zone = {
            (x, y)
            for y in range(3, 6)
            for x in range(3, 6)
        }
        self.assertTrue(safe_zone.isdisjoint(snapshot.mines))
        self.assertEqual(snapshot.adjacent[4][4], 0)
        self.assertEqual(observation[4][4], 0)

        original_snapshot_mines = snapshot.mines
        original_snapshot_adjacent = snapshot.adjacent
        engine.reset()
        self.assertTrue(snapshot.mines_placed)
        self.assertEqual(snapshot.mines, original_snapshot_mines)
        self.assertEqual(snapshot.adjacent, original_snapshot_adjacent)
        self.assertFalse(engine.get_board_snapshot().mines_placed)

    def test_flag_first_action_preserves_counter_flow(self):
        engine = MinesweeperEngine(width=9, height=9, num_mines=10)

        _, _, terminated, truncated, info = engine.step(0, 0, Action.FLAG)

        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertEqual(engine.count_flags(), 1)
        self.assertEqual(info["status"], GameStatus.PLAYING)
        self.assertEqual(info["stats"]["clicks"], "1")
        self.assertEqual(info["stats"]["left"], "0")
        self.assertEqual(info["stats"]["right"], "1")
        self.assertEqual(info["stats"]["chord"], "0")
        self.assertTrue(engine.get_board_snapshot().mines_placed)


if __name__ == "__main__":
    unittest.main()
