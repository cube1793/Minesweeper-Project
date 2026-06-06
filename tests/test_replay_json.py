import json
import tempfile
import unittest
from pathlib import Path

from replay_json import (
    load_replay_json,
    replay_data_from_dict,
    replay_data_to_dict,
    save_replay_json,
)
from replay_model import (
    ACTION_CHORD,
    ACTION_FLAG,
    ACTION_OPEN,
    ReplayBoard,
    ReplayData,
    ReplayEvent,
    SOURCE_ALGORITHM,
)


class ReplayJsonTests(unittest.TestCase):
    def _sample_replay(self):
        return ReplayData(
            board=ReplayBoard(
                width=4,
                height=3,
                num_mines=2,
                mine_positions={(2, 0), (0, 2)},
            ),
            events=(
                ReplayEvent(
                    elapsed_time=0.10,
                    x=1,
                    y=1,
                    action=ACTION_OPEN,
                ),
                ReplayEvent(
                    elapsed_time=1.25,
                    x=2,
                    y=0,
                    action=ACTION_FLAG,
                ),
                ReplayEvent(
                    elapsed_time=2.50,
                    x=1,
                    y=1,
                    action=ACTION_CHORD,
                ),
            ),
            source_type=SOURCE_ALGORITHM,
        )

    def test_replay_data_to_dict_round_trip(self):
        replay = self._sample_replay()

        data = replay_data_to_dict(replay)
        restored = replay_data_from_dict(data)

        self.assertEqual(restored, replay)
        self.assertEqual(data["source_type"], SOURCE_ALGORITHM)
        self.assertEqual(data["board"]["mine_positions"], [[0, 2], [2, 0]])
        self.assertEqual(restored.board.mine_positions, replay.board.mine_positions)

    def test_replay_json_file_round_trip(self):
        replay = self._sample_replay()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample_replay.json"
            save_replay_json(replay, path)
            restored = load_replay_json(path)

            self.assertEqual(restored, replay)
            self.assertEqual(restored.source_type, SOURCE_ALGORITHM)
            self.assertEqual(restored.board.mine_positions, replay.board.mine_positions)

            with path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
            self.assertEqual(raw["board"]["mine_positions"], [[0, 2], [2, 0]])

    def test_replay_data_from_dict_rejects_invalid_structure(self):
        with self.assertRaises(ValueError):
            replay_data_from_dict([])

        with self.assertRaises(ValueError):
            replay_data_from_dict({"events": []})

        replay = replay_data_to_dict(self._sample_replay())

        invalid_events = dict(replay)
        invalid_events["events"] = {"not": "a list"}
        with self.assertRaises(ValueError):
            replay_data_from_dict(invalid_events)

        invalid_mines = dict(replay)
        invalid_mines["board"] = dict(replay["board"])
        invalid_mines["board"]["mine_positions"] = [[0, 2, 9]]
        with self.assertRaises(ValueError):
            replay_data_from_dict(invalid_mines)

    def test_replay_data_from_dict_uses_model_validation(self):
        replay = replay_data_to_dict(self._sample_replay())

        invalid_source = dict(replay)
        invalid_source["source_type"] = "robot"
        with self.assertRaises(ValueError):
            replay_data_from_dict(invalid_source)

        invalid_action = dict(replay)
        invalid_action["events"] = [dict(replay["events"][0])]
        invalid_action["events"][0]["action"] = "BAD"
        with self.assertRaises(ValueError):
            replay_data_from_dict(invalid_action)

        invalid_bounds = dict(replay)
        invalid_bounds["events"] = [dict(replay["events"][0])]
        invalid_bounds["events"][0]["x"] = replay["board"]["width"]
        with self.assertRaises(ValueError):
            replay_data_from_dict(invalid_bounds)


if __name__ == "__main__":
    unittest.main()
