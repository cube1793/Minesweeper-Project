import json
import tempfile
import unittest
from copy import deepcopy
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
            self.assertEqual(raw["schema_version"], 1)
            self.assertNotIn("mouse_trace", raw)

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

    def test_load_replay_json_propagates_model_validation_errors(self):
        valid = replay_data_to_dict(self._sample_replay())
        malformed_replays = []

        invalid_width = deepcopy(valid)
        invalid_width["board"]["width"] = 3.5
        malformed_replays.append(invalid_width)

        invalid_mine_coordinate = deepcopy(valid)
        invalid_mine_coordinate["board"]["mine_positions"][0][0] = True
        malformed_replays.append(invalid_mine_coordinate)

        unhashable_mine_coordinate = deepcopy(valid)
        unhashable_mine_coordinate["board"]["mine_positions"][0][0] = [0]
        malformed_replays.append(unhashable_mine_coordinate)

        invalid_event_coordinate = deepcopy(valid)
        invalid_event_coordinate["events"][0]["x"] = 0.5
        malformed_replays.append(invalid_event_coordinate)

        invalid_elapsed_time = deepcopy(valid)
        invalid_elapsed_time["events"][0]["elapsed_time"] = float("nan")
        malformed_replays.append(invalid_elapsed_time)

        decreasing_timestamps = deepcopy(valid)
        decreasing_timestamps["events"][1]["elapsed_time"] = 0.05
        malformed_replays.append(decreasing_timestamps)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "malformed_replay.json"
            for index, replay in enumerate(malformed_replays):
                with self.subTest(case=index):
                    with path.open("w", encoding="utf-8") as file:
                        json.dump(replay, file)
                    with self.assertRaises(ValueError):
                        load_replay_json(path)


class ReplayMouseTraceJsonTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "trace.json"
        # Independent JSON fixture, including a legal pre-start CHORD and two
        # recording sizes. Trace microseconds deliberately differ from Replay time.
        self.document = {
            "schema_version": 2, "source_type": "human",
            "board": {"width": 3, "height": 3, "num_mines": 1, "mine_positions": [[1, 1]]},
            "events": [
                {"elapsed_time": 0, "x": 0, "y": 0, "action": "CHORD"},
                {"elapsed_time": 0.5, "x": 0, "y": 0, "action": "OPEN"},
                {"elapsed_time": 2, "x": 1, "y": 1, "action": "FLAG"},
            ],
            "mouse_trace": {"width": 3, "height": 3, "segments": [
                {"cell_size": 28, "points": [
                    {"elapsed_us": 0, "x": 4, "y": 7.25, "replay_event_index": 1},
                    {"elapsed_us": 100, "x": 14.5, "y": 8, "replay_event_index": None}]},
                {"cell_size": 56, "points": [
                    {"elapsed_us": 100, "x": 80.25, "y": 90, "replay_event_index": 2}]},
            ]},
        }

    def load_document(self, document):
        self.path.write_text(json.dumps(document), encoding="utf-8")
        return load_replay_json(self.path)

    def assert_invalid_at(self, path, values):
        for value in values:
            with self.subTest(path=path, value=value):
                document = deepcopy(self.document)
                target = document
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(ValueError):
                    self.load_document(document)

    def test_v2_text_and_file_round_trip_exact_shape_and_scalar_types(self):
        replay = self.load_document(self.document)
        self.assertEqual(replay_data_to_dict(replay), self.document)
        save_replay_json(replay, self.path)
        self.assertEqual(load_replay_json(self.path), replay)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), self.document)
        first = replay.mouse_trace.segments[0].points[0]
        self.assertIs(type(first.x), int)
        self.assertIs(type(first.y), float)
        self.assertIsNone(replay.mouse_trace.segments[0].points[1].replay_event_index)
        self.assertEqual([s.cell_size for s in replay.mouse_trace.segments], [28, 56])

    def test_v1_text_without_attachment_remains_unchanged(self):
        document = deepcopy(self.document)
        del document["mouse_trace"]
        document["schema_version"] = 1
        replay = self.load_document(document)
        self.assertIsNone(replay.mouse_trace)
        save_replay_json(replay, self.path)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), document)
        self.assertEqual(load_replay_json(self.path), replay)
        del document["schema_version"]
        self.assertEqual(self.load_document(document), replay)

    def test_schema_and_trace_presence_combinations_reject(self):
        self.assert_invalid_at(("schema_version",), (0, 1, 3, 999, True, False, 1.0, 2.0, "2", None))
        missing = deepcopy(self.document)
        del missing["mouse_trace"]
        with self.assertRaises(ValueError):
            self.load_document(missing)
        for version in (1, 2):
            document = deepcopy(self.document)
            document.update(schema_version=version, mouse_trace=None)
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.load_document(document)
        self.assert_invalid_at(("source_type",), ("algorithm", "ai"))

    def test_malformed_nested_containers_reject(self):
        self.assert_invalid_at(("mouse_trace",), (None, [], "trace", 1, True, {}))
        self.assert_invalid_at(("mouse_trace", "segments"), (None, {}, "segments", 1, [], [None], [[]]))
        self.assert_invalid_at(("mouse_trace", "segments", 0), (None, [], "segment", 1, {}))
        self.assert_invalid_at(("mouse_trace", "segments", 0, "points"),
                               (None, {}, "points", 1, [], [None], [[]], [{}]))
        for path in (("mouse_trace", "width"), ("mouse_trace", "height"),
                     ("mouse_trace", "segments"), ("mouse_trace", "segments", 0, "cell_size"),
                     *(("mouse_trace", "segments", 0, "points", 0, key)
                       for key in ("x", "y", "elapsed_us", "replay_event_index"))):
            document = deepcopy(self.document)
            target = document
            for key in path[:-1]:
                target = target[key]
            del target[path[-1]]
            with self.subTest(missing=path), self.assertRaises(ValueError):
                self.load_document(document)

    def test_invalid_dimensions_cell_sizes_and_coordinates_reject(self):
        bad_integer = (0, -1, True, False, 3.0, "3", None, [], {})
        for key in ("width", "height"):
            self.assert_invalid_at(("mouse_trace", key), bad_integer + (4,))
        self.assert_invalid_at(("mouse_trace", "segments", 0, "cell_size"), bad_integer)
        for key in ("x", "y"):
            self.assert_invalid_at(("mouse_trace", "segments", 0, "points", 0, key),
                                   (-1, 84, True, False, "4", None, [], {},
                                    float("nan"), float("inf"), -float("inf")))

    def test_invalid_times_and_action_references_reject(self):
        for key in ("elapsed_us", "replay_event_index"):
            self.assert_invalid_at(("mouse_trace", "segments", 0, "points", 0, key),
                                   (-1, True, False, 1.5, "1", None, [], {}, float("nan"), float("inf")))
        self.assert_invalid_at(("mouse_trace", "segments", 0, "points", 0, "elapsed_us"), (1,))
        # Time reversal across segments; duplicate/reversed/out-of-range references.
        self.assert_invalid_at(("mouse_trace", "segments", 1, "points", 0, "elapsed_us"), (99,))
        self.assert_invalid_at(("mouse_trace", "segments", 1, "points", 0, "replay_event_index"), (0, 1, 3))
        document = deepcopy(self.document)
        document["mouse_trace"]["segments"][0]["points"].append(
            {"elapsed_us": 99, "x": 1, "y": 1, "replay_event_index": None})
        with self.assertRaises(ValueError):
            self.load_document(document)

    def test_unrelated_unknown_fields_remain_ignored(self):
        expected = self.load_document(self.document)
        document = deepcopy(self.document)
        document["future_metadata"] = {"note": "ignored"}
        document["board"]["extra"] = True
        document["events"][0]["extra"] = True
        document["mouse_trace"]["extra"] = True
        document["mouse_trace"]["segments"][0]["extra"] = True
        document["mouse_trace"]["segments"][0]["points"][0]["extra"] = True
        self.assertEqual(self.load_document(document), expected)


if __name__ == "__main__":
    unittest.main()
