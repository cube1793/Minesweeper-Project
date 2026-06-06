import unittest

from core_engine import CellState
from replay_model import (
    ACTION_CHORD,
    ACTION_FLAG,
    ACTION_OPEN,
    ReplayBoard,
    ReplayData,
    ReplayEvent,
)
from replay_player import ReplayPlayer


class ReplayPlayerTests(unittest.TestCase):
    def _sample_replay(self):
        return ReplayData(
            board=ReplayBoard(
                width=3,
                height=3,
                num_mines=1,
                mine_positions={(1, 1)},
            ),
            events=(
                ReplayEvent(
                    elapsed_time=0.1,
                    x=0,
                    y=0,
                    action=ACTION_OPEN,
                ),
                ReplayEvent(
                    elapsed_time=0.2,
                    x=1,
                    y=1,
                    action=ACTION_FLAG,
                ),
                ReplayEvent(
                    elapsed_time=0.3,
                    x=0,
                    y=0,
                    action=ACTION_CHORD,
                ),
            ),
        )

    def assert_all_hidden(self, observation):
        self.assertTrue(
            all(
                value == CellState.HIDDEN.value
                for row in observation
                for value in row
            )
        )

    def test_player_starts_at_index_zero(self):
        player = ReplayPlayer(self._sample_replay())

        self.assertEqual(player.current_index, 0)
        self.assertEqual(player.current_time, 0.0)
        self.assertIsNone(player.current_event)
        self.assertEqual(player.event_count, 3)

    def test_initial_observation_is_all_hidden(self):
        player = ReplayPlayer(self._sample_replay())

        self.assert_all_hidden(player.get_observation())

    def test_go_to_zero_restores_initial_state(self):
        player = ReplayPlayer(self._sample_replay())
        player.go_to(2)

        observation = player.go_to(0)

        self.assertEqual(player.current_index, 0)
        self.assert_all_hidden(observation)

    def test_go_to_one_restores_first_event_state(self):
        player = ReplayPlayer(self._sample_replay())

        observation = player.go_to(1)

        self.assertEqual(player.current_index, 1)
        self.assertEqual(player.current_time, 0.1)
        self.assertEqual(player.current_event, self._sample_replay().events[0])
        self.assertEqual(observation[0][0], 1)
        self.assertEqual(observation[1][1], CellState.HIDDEN.value)

    def test_go_to_final_index_applies_all_events(self):
        player = ReplayPlayer(self._sample_replay())

        observation = player.go_to(player.event_count)

        self.assertEqual(player.current_index, 3)
        self.assertEqual(player.current_time, 0.3)
        self.assertEqual(observation[0][0], 1)
        self.assertEqual(observation[0][1], 1)
        self.assertEqual(observation[1][0], 1)
        self.assertEqual(observation[1][1], CellState.FLAGGED.value)

    def test_next_increments_index_and_applies_event(self):
        player = ReplayPlayer(self._sample_replay())

        self.assertTrue(player.next())
        self.assertEqual(player.current_index, 1)
        self.assertEqual(player.get_observation()[0][0], 1)

        self.assertTrue(player.next())
        self.assertEqual(player.current_index, 2)
        self.assertEqual(player.get_observation()[1][1], CellState.FLAGGED.value)

        self.assertTrue(player.next())
        self.assertEqual(player.current_index, 3)
        self.assertFalse(player.next())
        self.assertEqual(player.current_index, 3)

    def test_previous_decrements_index_and_restores_previous_state(self):
        player = ReplayPlayer(self._sample_replay())
        player.go_to(3)

        self.assertTrue(player.previous())
        observation = player.get_observation()

        self.assertEqual(player.current_index, 2)
        self.assertEqual(player.current_time, 0.2)
        self.assertEqual(observation[0][0], 1)
        self.assertEqual(observation[1][1], CellState.FLAGGED.value)
        self.assertEqual(observation[0][1], CellState.HIDDEN.value)
        self.assertEqual(observation[1][0], CellState.HIDDEN.value)

        self.assertTrue(player.previous())
        self.assertEqual(player.current_index, 1)
        self.assertEqual(player.get_observation()[1][1], CellState.HIDDEN.value)

        self.assertTrue(player.previous())
        self.assertEqual(player.current_index, 0)
        self.assertFalse(player.previous())

    def test_go_to_rejects_invalid_index(self):
        player = ReplayPlayer(self._sample_replay())

        with self.assertRaises(ValueError):
            player.go_to(-1)
        with self.assertRaises(ValueError):
            player.go_to(player.event_count + 1)
        with self.assertRaises(ValueError):
            player.go_to(1.5)


if __name__ == "__main__":
    unittest.main()
