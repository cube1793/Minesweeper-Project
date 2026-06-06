import unittest

from board_snapshot import BoardSnapshot
from core_engine import Action
from replay_model import ACTION_CHORD, ACTION_FLAG, ACTION_OPEN, SOURCE_AI
from replay_recorder import ReplayRecorder


class ReplayRecorderTests(unittest.TestCase):
    def _placed_snapshot(self):
        return BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=(
                (1, 1, 1),
                (1, 0, 1),
                (1, 1, 1),
            ),
        )

    def _unplaced_snapshot(self):
        return BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=(
                (0, 0, 0),
                (0, 0, 0),
                (0, 0, 0),
            ),
        )

    def test_new_recorder_starts_empty(self):
        recorder = ReplayRecorder(width=3, height=3, num_mines=1)

        self.assertEqual(recorder.width, 3)
        self.assertEqual(recorder.height, 3)
        self.assertEqual(recorder.num_mines, 1)
        self.assertEqual(recorder.events, ())
        self.assertIsNone(recorder.board)
        self.assertIsNone(recorder.mine_positions)

    def test_record_event_accumulates_replay_events(self):
        recorder = ReplayRecorder(width=3, height=3, num_mines=1)

        first = recorder.record_event(0.1, 0, 0, Action.OPEN)
        second = recorder.record_event(0.2, 1, 0, ACTION_FLAG)
        third = recorder.record_event(0.3, 1, 1, 2)

        self.assertEqual(recorder.events, (first, second, third))
        self.assertEqual(first.action, ACTION_OPEN)
        self.assertEqual(second.action, ACTION_FLAG)
        self.assertEqual(third.action, ACTION_CHORD)

    def test_capture_board_confirms_replay_board_from_snapshot(self):
        recorder = ReplayRecorder(width=3, height=3, num_mines=1)

        board = recorder.capture_board(self._placed_snapshot())

        self.assertEqual(recorder.board, board)
        self.assertEqual(board.width, 3)
        self.assertEqual(board.height, 3)
        self.assertEqual(board.num_mines, 1)
        self.assertEqual(board.mine_positions, frozenset({(1, 1)}))
        self.assertEqual(recorder.mine_positions, frozenset({(1, 1)}))

    def test_capture_board_rejects_unplaced_snapshot(self):
        recorder = ReplayRecorder(width=3, height=3, num_mines=1)

        with self.assertRaises(ValueError):
            recorder.capture_board(self._unplaced_snapshot())

    def test_to_replay_data_rejects_uncaptured_board(self):
        recorder = ReplayRecorder(width=3, height=3, num_mines=1)
        recorder.record_event(0.1, 0, 0, Action.OPEN)

        with self.assertRaises(ValueError):
            recorder.to_replay_data()

    def test_to_replay_data_returns_replay_data_after_capture(self):
        recorder = ReplayRecorder(
            width=3,
            height=3,
            num_mines=1,
            source_type=SOURCE_AI,
        )
        event = recorder.record_event(0.1, 0, 0, Action.OPEN)
        board = recorder.capture_board(self._placed_snapshot())

        replay_data = recorder.to_replay_data()

        self.assertEqual(replay_data.board, board)
        self.assertEqual(replay_data.events, (event,))
        self.assertEqual(replay_data.source_type, SOURCE_AI)
        self.assertEqual(replay_data.board.mine_positions, frozenset({(1, 1)}))

    def test_reset_clears_events_and_captured_board(self):
        recorder = ReplayRecorder(width=3, height=3, num_mines=1)
        recorder.record_event(0.1, 0, 0, Action.OPEN)
        recorder.capture_board(self._placed_snapshot())

        recorder.reset(width=4, height=4, num_mines=2, source_type=SOURCE_AI)

        self.assertEqual(recorder.width, 4)
        self.assertEqual(recorder.height, 4)
        self.assertEqual(recorder.num_mines, 2)
        self.assertEqual(recorder.source_type, SOURCE_AI)
        self.assertEqual(recorder.events, ())
        self.assertIsNone(recorder.board)


if __name__ == "__main__":
    unittest.main()
