"""File-backed repository boundaries with immutable, already-executed facts."""

import ast
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import telemetry_repository as repository
import telemetry_schema as schema
from core_engine import Action, GameStatus
from telemetry_collector import TelemetryCollector
from telemetry_model import InferenceCategory


CREATED_AT = "2026-09-26T00:00:00Z"
STARTED_AT = "2026-09-26T00:00:01+00:00"
FINISHED_AT = "2026-09-26T00:00:02.123456Z"


def run_inputs(**overrides):
    values = dict(
        telemetry_schema_version=1,
        created_at=CREATED_AT,
        git_commit="abc123",
        git_dirty=False,
        solver_stage="STAGE_2",
        solver_policy="test-policy",
        solver_config_snapshot={"z": False, "a": {"y": 2, "x": 1}},
        width=8,
        height=6,
        num_mines=7,
        first_click_policy=schema.FIRST_CLICK_FIXED_0_0,
        board_generator_version=schema.BOARD_GENERATOR_V1,
        benchmark_set_id="TEST_SET_V1",
        requested_games=3,
        environment_snapshot={"sqlite": "test-version", "python": "test-version"},
    )
    values.update(overrides)
    return values


def completed_game(game_index=0, status=GameStatus.WON):
    """Collector facts exercise every action/category without running a solver."""
    collector = TelemetryCollector()
    collector.record_action(
        action_type=Action.OPEN, x=0, y=0, status_after=GameStatus.PLAYING,
        safe_cells_opened_delta=2, explicit_flag_delta=0,
    )
    collector.record_action(
        action_type=Action.FLAG, x=2, y=1, status_after=GameStatus.PLAYING,
        safe_cells_opened_delta=0, explicit_flag_delta=1,
        inference_category=InferenceCategory.LOCAL_DETERMINISTIC,
        selection_candidate_count=3, target_mine_probability=Fraction(1),
        decision_compute_ns=7,
    )
    collector.record_action(
        action_type=Action.CHORD, x=3, y=2, status_after=GameStatus.PLAYING,
        safe_cells_opened_delta=3, explicit_flag_delta=0,
        inference_category=InferenceCategory.GLOBAL_CERTAINTY,
        selection_candidate_count=2, target_mine_probability=Fraction(0),
        decision_compute_ns=0,
    )
    collector.record_action(
        action_type=Action.OPEN, x=4, y=3, status_after=status,
        safe_cells_opened_delta=1 if status == GameStatus.WON else 0,
        explicit_flag_delta=0,
        inference_category=InferenceCategory.PROBABILITY_GUESS,
        selection_candidate_count=4,
        # Deliberately different: minimum-risk selection belongs to the adapter.
        target_mine_probability=Fraction(10**100 + 1, 3 * 10**100),
        minimum_available_mine_probability=Fraction(1, 3),
        decision_compute_ns=11,
    )
    record = collector.finalize(
        game_index=game_index, seed=42, board_fingerprint="ab" * 32,
        board_3bv=19, board_ops=5,
    )
    return record, collector.events


class ClosingConnection(sqlite3.Connection):
    closed = False

    def close(self):
        self.closed = True
        super().close()


class RefusedPragmaConnection(ClosingConnection):
    refused_pragma = ""
    refused_value = None

    def execute(self, sql, parameters=()):
        normalized = sql.strip().rstrip(";").lower()
        if normalized.startswith("pragma " + self.refused_pragma):
            return super().execute("SELECT ?", (self.refused_value,))
        return super().execute(sql, parameters)


class RepositoryTestCase(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "telemetry.sqlite3"
        self.connection = repository.connect_database(self.database_path)
        self.addCleanup(self.connection.close)

    def create_run(self, **overrides):
        return repository.create_run(self.connection, **run_inputs(**overrides))

    def persist(self, run_id, game_index=0, status=GameStatus.WON):
        record, events = completed_game(game_index, status)
        return repository.persist_completed_game(self.connection, run_id, record, events)

    def counts(self, run_id):
        row = self.connection.execute(
            "SELECT processed_games, "
            "(SELECT COUNT(*) FROM games WHERE run_id = ?) AS games, "
            "(SELECT COUNT(*) FROM action_events e JOIN games g USING (game_id) "
            "WHERE g.run_id = ?) AS events "
            "FROM benchmark_runs WHERE run_id = ?", (run_id, run_id, run_id),
        ).fetchone()
        return tuple(row)

    def assert_empty_run(self, run_id):
        self.assertEqual(self.counts(run_id), (0, 0, 0))
        self.assertFalse(self.connection.in_transaction)


class RepositoryConnectionTests(RepositoryTestCase):
    def test_file_connection_verifies_modes_and_initializes_schema(self):
        self.assertIsNone(self.connection.isolation_level)
        self.assertIs(self.connection.row_factory, sqlite3.Row)
        self.assertFalse(self.connection.in_transaction)
        expected = {"foreign_keys": 1, "journal_mode": "wal", "synchronous": 2,
                    "user_version": schema.PHYSICAL_SCHEMA_VERSION}
        for pragma, value in expected.items():
            with self.subTest(pragma=pragma):
                self.assertEqual(self.connection.execute("PRAGMA " + pragma).fetchone()[0], value)
        tables = {
            row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertEqual(tables, {"benchmark_runs", "games", "action_events"})
        ddl = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'action_events'"
        ).fetchone()[0]
        self.assertIn("WITHOUT ROWID", ddl)

    def test_reopen_reestablishes_modes_and_preserves_committed_rows(self):
        run_id = self.create_run()
        game_id = self.persist(run_id)
        self.connection.close()
        raw = sqlite3.connect(self.database_path, isolation_level=None)
        try:
            self.assertEqual(raw.execute("PRAGMA journal_mode = DELETE").fetchone()[0], "delete")
            raw.execute("PRAGMA synchronous = OFF")
        finally:
            raw.close()
        reopened = repository.connect_database(str(self.database_path))
        self.addCleanup(reopened.close)
        for pragma, value in (("foreign_keys", 1), ("journal_mode", "wal"), ("synchronous", 2)):
            self.assertEqual(reopened.execute("PRAGMA " + pragma).fetchone()[0], value)
        self.assertEqual(repository.fetch_run(reopened, run_id)["processed_games"], 1)
        self.assertEqual(reopened.execute(
            "SELECT COUNT(*) FROM action_events WHERE game_id = ?", (game_id,),
        ).fetchone()[0], 4)

    def test_unknown_physical_schema_version_propagates_and_closes_connection(self):
        self.connection.execute("PRAGMA user_version = 99")
        self.connection.close()
        real_connect = sqlite3.connect
        opened = []

        def connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs, factory=ClosingConnection)
            opened.append(connection)
            return connection

        with patch.object(repository.sqlite3, "connect", side_effect=connect):
            with self.assertRaises(ValueError):
                repository.connect_database(self.database_path)
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)

    def test_required_effective_modes_cannot_be_silently_refused(self):
        for pragma, refused_value in (("foreign_keys", 0), ("journal_mode", "delete"),
                                      ("synchronous", 1)):
            with self.subTest(pragma=pragma):
                connection = sqlite3.connect(
                    self.database_path, isolation_level=None, factory=RefusedPragmaConnection,
                )
                self.addCleanup(connection.close)
                connection.refused_pragma = pragma
                connection.refused_value = refused_value
                with patch.object(repository.sqlite3, "connect", return_value=connection):
                    with self.assertRaises(RuntimeError):
                        repository.connect_database(self.database_path)
                self.assertTrue(connection.closed)

    def test_memory_database_is_rejected_instead_of_weakening_wal(self):
        with self.assertRaises(RuntimeError):
            repository.connect_database(":memory:")


class RepositoryRunTests(RepositoryTestCase):
    def test_run_integer_fields_reject_non_integers_before_sql(self):
        for field in ("telemetry_schema_version", "width", "height", "num_mines", "requested_games"):
            for value in (True, False, 2.0, 2.5, "2", "abc", "1,000", "v1",
                          b"2", Decimal(2), Fraction(2), None):
                with self.subTest(field=field, value=value):
                    statements = []
                    self.connection.set_trace_callback(statements.append)
                    try:
                        with self.assertRaisesRegex(ValueError, field):
                            self.create_run(**{field: value})
                    finally:
                        self.connection.set_trace_callback(None)
                    self.assertEqual(statements, [])
                    self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 0)

    def test_run_text_fields_reject_affinity_conversion_and_blob_inputs(self):
        required = ("git_commit", "solver_stage", "solver_policy", "first_click_policy",
                    "board_generator_version", "benchmark_set_id")
        nullable = ("app_version", "difficulty_name", "failure_code")
        for field in required + nullable:
            invalid_values = (True, False, 0, 2.5, b"abc", bytearray(b"abc"),
                              memoryview(b"abc"), Decimal(2), Fraction(2))
            if field in required:
                invalid_values += (None,)
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, field):
                        self.create_run(**{field: value})
                    self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 0)
        # TEXT identity and nullability do not imply a nonempty-string policy.
        run_id = self.create_run(**dict.fromkeys(required + nullable, ""))
        row = repository.fetch_run(self.connection, run_id)
        for field in required + nullable:
            self.assertEqual(row[field], "")

    def test_public_run_ids_reject_boolean_and_coercible_identities_before_sql(self):
        run_id = self.create_run()
        self.assertEqual(run_id, 1)  # True would otherwise address this row.
        record, events = completed_game()
        operations = (
            lambda value: repository.fetch_run(self.connection, value),
            lambda value: repository.update_run_status(self.connection, value, schema.RUN_STATUS_RUNNING),
            lambda value: repository.persist_completed_game(self.connection, value, record, events),
        )
        for index, operation in enumerate(operations):
            for value in (True, False, 1.0, 1.5, "1", "abc", b"1", Decimal(1), Fraction(1), None):
                with self.subTest(operation=index, value=value):
                    statements = []
                    self.connection.set_trace_callback(statements.append)
                    try:
                        with self.assertRaisesRegex(ValueError, "run_id"):
                            operation(value)
                    finally:
                        self.connection.set_trace_callback(None)
                    self.assertEqual(statements, [])
                    self.assert_empty_run(run_id)
        self.assertEqual(repository.fetch_run(self.connection, run_id)["run_status"], schema.RUN_STATUS_CREATED)

    def test_status_failure_code_requires_nullable_text(self):
        run_id = self.create_run(failure_code="original")
        for value in (True, 0, 2.5, b"abc", bytearray(b"abc"), memoryview(b"abc")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "failure_code"):
                    repository.update_run_status(
                        self.connection, run_id, schema.RUN_STATUS_FAILED, failure_code=value,
                    )
                row = repository.fetch_run(self.connection, run_id)
                self.assertEqual((row["run_status"], row["failure_code"]), (schema.RUN_STATUS_CREATED, "original"))
                self.assertFalse(self.connection.in_transaction)
        for value in ("", None):
            repository.update_run_status(
                self.connection, run_id, schema.RUN_STATUS_FAILED, failure_code=value,
            )
            self.assertEqual(repository.fetch_run(self.connection, run_id)["failure_code"], value)

    def test_all_run_fields_and_generated_identity_persist(self):
        values = run_inputs(
            started_at=STARTED_AT, finished_at=FINISHED_AT,
            run_status=schema.RUN_STATUS_FAILED, git_dirty=True,
            app_version="0.1-test", difficulty_name="test", failure_code="test-failure",
        )
        run_id = repository.create_run(self.connection, **values)
        row = repository.fetch_run(self.connection, run_id)
        self.assertIs(type(run_id), int)
        self.assertGreater(run_id, 0)
        expected = dict(values, run_id=run_id, processed_games=0, git_dirty=1)
        for name in ("solver_config_snapshot", "environment_snapshot"):
            expected[name] = json.dumps(expected[name], sort_keys=True, separators=(",", ":"))
        self.assertEqual(dict(row), expected)
        self.assertFalse(self.connection.in_transaction)

    def test_default_creation_and_duplicate_provenance_have_distinct_primary_keys(self):
        first = self.create_run()
        second = self.create_run()
        self.assertNotEqual(first, second)
        row = repository.fetch_run(self.connection, first)
        self.assertEqual(row["run_status"], schema.RUN_STATUS_CREATED)
        self.assertEqual(row["processed_games"], 0)
        for name in ("started_at", "finished_at", "app_version", "difficulty_name", "failure_code"):
            self.assertIsNone(row[name])
        self.assertIsNone(repository.fetch_run(self.connection, second + 1000))

    def test_snapshot_serialization_is_compact_deterministic_json(self):
        first = self.create_run(
            solver_config_snapshot={"z": 2, "a": {"y": 4, "b": [True, None]}},
            environment_snapshot={"z": 2, "a": 1},
        )
        second = self.create_run(
            solver_config_snapshot={"a": {"b": [True, None], "y": 4}, "z": 2},
            environment_snapshot={"a": 1, "z": 2},
        )
        for name, expected in (
            ("solver_config_snapshot", '{"a":{"b":[true,null],"y":4},"z":2}'),
            ("environment_snapshot", '{"a":1,"z":2}'),
        ):
            self.assertEqual(repository.fetch_run(self.connection, first)[name], expected)
            self.assertEqual(repository.fetch_run(self.connection, second)[name], expected)

    def test_invalid_snapshots_have_no_partial_run(self):
        for field in ("solver_config_snapshot", "environment_snapshot"):
            for value in ({"nonfinite": float("nan")}, {"nonfinite": float("inf")}, object()):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        self.create_run(**{field: value})
                    self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 0)
                    self.assertFalse(self.connection.in_transaction)

    def test_structural_creation_failure_leaves_previous_run_durable(self):
        first = self.create_run()
        for invalid in (dict(width=0), dict(height=0), dict(num_mines=48),
                        dict(requested_games=0), dict(benchmark_set_id=None),
                        dict(run_status=schema.RUN_STATUS_COMPLETED)):
            with self.subTest(invalid=invalid):
                with self.assertRaises((ValueError, sqlite3.IntegrityError)):
                    self.create_run(**invalid)
                self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 1)
                self.assert_empty_run(first)

    def test_unknown_status_and_non_boolean_git_dirty_are_rejected(self):
        for invalid in (dict(run_status="UNKNOWN"), dict(run_status=1),
                        dict(git_dirty=1), dict(git_dirty="false")):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                self.create_run(**invalid)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 0)

    def test_utc_timestamp_strings_are_preserved_without_local_conversion(self):
        for timestamp in (CREATED_AT, STARTED_AT, FINISHED_AT, "2026-09-26T00:00:00+0000",
                          "20260926T000000Z", "2026-W39-6T00:00:00Z",
                          "2026W396T000000+0000", "2026-09-26 00:00:00Z",
                          "2026-09-26T00:00:02,123456Z"):
            with self.subTest(timestamp=timestamp):
                run_id = self.create_run(created_at=timestamp, started_at=timestamp, finished_at=timestamp)
                row = repository.fetch_run(self.connection, run_id)
                for field in ("created_at", "started_at", "finished_at"):
                    self.assertEqual(row[field], timestamp)
                repository.update_run_status(
                    self.connection, run_id, schema.RUN_STATUS_RUNNING,
                    started_at=None, finished_at=None,
                )
                repository.update_run_status(
                    self.connection, run_id, schema.RUN_STATUS_RUNNING,
                    started_at=timestamp, finished_at=timestamp,
                )
                row = repository.fetch_run(self.connection, run_id)
                self.assertEqual((row["started_at"], row["finished_at"]), (timestamp, timestamp))
        for timestamp in ("2026-09-26", "2026-09-26T09:00:00+09:00", "invalid", None):
            with self.subTest(timestamp=timestamp), self.assertRaises((TypeError, ValueError)):
                self.create_run(created_at=timestamp)

    def test_invalid_timestamp_separators_are_rejected_at_every_write_boundary(self):
        run_id = self.create_run()
        original = dict(repository.fetch_run(self.connection, run_id))
        invalid = [f"2026-09-26{separator}00:00:00Z" for separator in ("X", "é", "\x00", "\n", "\t", "1")]
        invalid += ["2026-09-26T00:00:00Z\n", "2026-09-26T00:00:\x000Z", "2026-02-30T00:00:00Z"]
        for timestamp in invalid:
            for field in ("created_at", "started_at", "finished_at"):
                with self.subTest(timestamp=timestamp, field=field):
                    with self.assertRaises(ValueError):
                        self.create_run(**{field: timestamp})
                    if field != "created_at":
                        with self.assertRaises(ValueError):
                            repository.update_run_status(
                                self.connection, run_id, schema.RUN_STATUS_RUNNING, **{field: timestamp},
                            )
                    self.assertEqual(dict(repository.fetch_run(self.connection, run_id)), original)
                    self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 1)
                    self.assertFalse(self.connection.in_transaction)

    def test_status_update_preserves_omitted_values_and_clears_explicit_none(self):
        run_id = self.create_run()
        repository.update_run_status(
            self.connection, run_id, schema.RUN_STATUS_RUNNING, started_at=STARTED_AT,
        )
        repository.update_run_status(
            self.connection, run_id, schema.RUN_STATUS_FAILED,
            finished_at=FINISHED_AT, failure_code="test-code",
        )
        row = repository.fetch_run(self.connection, run_id)
        self.assertEqual((row["started_at"], row["finished_at"], row["failure_code"]),
                         (STARTED_AT, FINISHED_AT, "test-code"))
        repository.update_run_status(
            self.connection, run_id, schema.RUN_STATUS_ABORTED,
            started_at=None, finished_at=None, failure_code=None,
        )
        row = repository.fetch_run(self.connection, run_id)
        self.assertEqual((row["started_at"], row["finished_at"], row["failure_code"]), (None,) * 3)
        repository.update_run_status(self.connection, run_id, schema.RUN_STATUS_INTERRUPTED)
        self.assertEqual(repository.fetch_run(self.connection, run_id)["run_status"], schema.RUN_STATUS_INTERRUPTED)
        self.assertFalse(self.connection.in_transaction)

    def test_status_update_rejects_unknown_status_missing_run_and_invalid_timestamp(self):
        run_id = self.create_run()
        with self.assertRaises(ValueError):
            repository.update_run_status(self.connection, run_id, "unknown")
        with self.assertRaises(ValueError):
            repository.update_run_status(self.connection, run_id + 1000, schema.RUN_STATUS_FAILED)
        for name in ("started_at", "finished_at"):
            with self.subTest(name=name), self.assertRaises((TypeError, ValueError)):
                repository.update_run_status(
                    self.connection, run_id, schema.RUN_STATUS_RUNNING,
                    **{name: "2026-09-26T09:00:00+09:00"},
                )
        self.assertEqual(repository.fetch_run(self.connection, run_id)["run_status"], schema.RUN_STATUS_CREATED)
        self.assertFalse(self.connection.in_transaction)

    def test_completed_requires_processed_count_but_no_repository_prefix_policy(self):
        run_id = self.create_run(requested_games=1)
        with self.assertRaises((ValueError, sqlite3.IntegrityError)):
            repository.update_run_status(
                self.connection, run_id, schema.RUN_STATUS_COMPLETED, finished_at=FINISHED_AT,
            )
        self.assert_empty_run(run_id)
        self.assertIsNone(repository.fetch_run(self.connection, run_id)["finished_at"])
        self.persist(run_id, game_index=99)
        self.assertEqual(repository.fetch_run(self.connection, run_id)["run_status"], schema.RUN_STATUS_CREATED)
        repository.update_run_status(
            self.connection, run_id, schema.RUN_STATUS_COMPLETED, finished_at=FINISHED_AT,
        )
        self.assertEqual(repository.fetch_run(self.connection, run_id)["run_status"], schema.RUN_STATUS_COMPLETED)


class RepositoryGameTests(RepositoryTestCase):
    def test_distinct_coordinates_and_counts_detect_game_column_swaps(self):
        _, templates = completed_game()
        collector = TelemetryCollector()
        # OPEN/FLAG/CHORD = 4/1/2; LOCAL/GLOBAL/GUESS = 1/2/3.
        sequence = (templates[0], templates[1], templates[2], templates[2],
                    templates[3], templates[3], templates[3])
        for index, template in enumerate(sequence):
            values = asdict(template)
            values.pop("action_index")
            values["status_after"] = GameStatus.WON if index == len(sequence) - 1 else GameStatus.PLAYING
            if index == 0:
                values.update(x=1, y=2)
            collector.record_action(**values)
        record = collector.finalize(
            game_index=6, seed=42, board_fingerprint="cd" * 32, board_3bv=19, board_ops=5,
        )
        self.assertEqual((record.first_click_x, record.first_click_y), (1, 2))
        self.assertEqual((record.open_count, record.flag_count, record.chord_count), (4, 1, 2))
        self.assertEqual((record.local_deterministic_count, record.global_certainty_count,
                          record.probability_guess_count), (1, 2, 3))
        run_id = self.create_run()
        game_id = repository.persist_completed_game(self.connection, run_id, record, collector.events)
        expected = dict(asdict(record), run_id=run_id, game_id=game_id,
                        result=schema.GAME_RESULT_WIN, had_probability_guess=1)
        row = self.connection.execute("SELECT * FROM games WHERE game_id = ?", (game_id,)).fetchone()
        self.assertEqual(dict(row), expected)
        self.assertEqual(self.counts(run_id), (1, 1, 7))

    def test_every_game_and_event_field_uses_stable_exact_persistence(self):
        run_id = self.create_run(requested_games=2)
        action_mapping = {Action.OPEN: schema.ACTION_OPEN, Action.FLAG: schema.ACTION_FLAG,
                          Action.CHORD: schema.ACTION_CHORD}
        category_mapping = {
            None: None,
            InferenceCategory.LOCAL_DETERMINISTIC: schema.INFERENCE_LOCAL_DETERMINISTIC,
            InferenceCategory.GLOBAL_CERTAINTY: schema.INFERENCE_GLOBAL_CERTAINTY,
            InferenceCategory.PROBABILITY_GUESS: schema.INFERENCE_PROBABILITY_GUESS,
        }
        status_mapping = {
            GameStatus.PLAYING: schema.STATUS_AFTER_PLAYING,
            GameStatus.WON: schema.STATUS_AFTER_WON, GameStatus.LOST: schema.STATUS_AFTER_LOST,
        }
        self.assertEqual(set(action_mapping), set(Action))
        self.assertEqual(set(category_mapping) - {None}, set(InferenceCategory))
        self.assertEqual(set(status_mapping), set(GameStatus))
        for index, status in enumerate((GameStatus.WON, GameStatus.LOST)):
            record, events = completed_game(index, status)
            with patch.object(Fraction, "__float__", side_effect=AssertionError("No float encoding")):
                game_id = repository.persist_completed_game(self.connection, run_id, record, events)
            self.assertIs(type(game_id), int)
            game_row = self.connection.execute("SELECT * FROM games WHERE game_id = ?", (game_id,)).fetchone()
            expected_game = asdict(record)
            expected_game.update(
                run_id=run_id, game_id=game_id, had_probability_guess=1,
                result=schema.GAME_RESULT_WIN if status == GameStatus.WON else schema.GAME_RESULT_LOSS,
            )
            self.assertEqual(dict(game_row), expected_game)
            rows = self.connection.execute(
                "SELECT * FROM action_events WHERE game_id = ? ORDER BY action_index", (game_id,),
            ).fetchall()
            self.assertEqual(len(rows), len(events))
            for row, event in zip(rows, events):
                expected_event = asdict(event)
                expected_event.update(
                    game_id=game_id, action_type=action_mapping[event.action_type],
                    inference_category=category_mapping[event.inference_category],
                    status_after=status_mapping[event.status_after],
                )
                for name in ("target_mine_probability", "minimum_available_mine_probability"):
                    value = expected_event[name]
                    expected_event[name] = None if value is None else f"{value.numerator}/{value.denominator}"
                self.assertEqual(dict(row), expected_event)
                self.assertNotEqual(row["action_type"], event.action_type.value)
                self.assertNotEqual(row["status_after"], event.status_after.value)
            self.assertEqual(self.connection.execute(
                "SELECT typeof(target_mine_probability), typeof(minimum_available_mine_probability) "
                "FROM action_events WHERE game_id = ? AND action_index = 3", (game_id,),
            ).fetchone()[:], ("text", "text"))
        self.assertEqual(self.counts(run_id), (2, 2, 8))

    def test_zero_decision_game_preserves_nullable_summaries_and_policy_metadata(self):
        collector = TelemetryCollector()
        collector.record_action(
            action_type=Action.OPEN, x=0, y=0, status_after=GameStatus.WON,
            safe_cells_opened_delta=1, explicit_flag_delta=0,
        )
        record = collector.finalize(
            game_index=0, seed=0, board_fingerprint="0" * 64, board_3bv=1, board_ops=0,
        )
        run_id = self.create_run()
        game_id = repository.persist_completed_game(self.connection, run_id, record, collector.events)
        game_row = self.connection.execute("SELECT * FROM games WHERE game_id = ?", (game_id,)).fetchone()
        self.assertEqual(game_row["had_probability_guess"], 0)
        self.assertIsNone(game_row["first_guess_action_index"])
        self.assertEqual(game_row["compute_time_total_ns"], 0)
        self.assertIsNone(game_row["compute_time_max_ns"])
        event_row = self.connection.execute("SELECT * FROM action_events WHERE game_id = ?", (game_id,)).fetchone()
        for name in ("inference_category", "selection_candidate_count", "target_mine_probability",
                     "minimum_available_mine_probability", "decision_compute_ns"):
            self.assertIsNone(event_row[name])

    def test_analyzed_first_action_is_allowed_without_stage_two_policy(self):
        collector = TelemetryCollector()
        collector.record_action(
            action_type=Action.FLAG, x=2, y=1, status_after=GameStatus.WON,
            safe_cells_opened_delta=0, explicit_flag_delta=-1,
            inference_category=InferenceCategory.LOCAL_DETERMINISTIC,
            selection_candidate_count=1, target_mine_probability=Fraction(2, 5),
            decision_compute_ns=0,
        )
        record = collector.finalize(
            game_index=0, seed=0, board_fingerprint="0" * 64, board_3bv=9, board_ops=2,
        )
        run_id = self.create_run()
        game_id = repository.persist_completed_game(self.connection, run_id, record, collector.events)
        row = self.connection.execute("SELECT * FROM action_events WHERE game_id = ?", (game_id,)).fetchone()
        self.assertEqual((row["action_index"], row["action_type"], row["explicit_flag_delta"]),
                         (0, schema.ACTION_FLAG, -1))
        self.assertEqual(row["target_mine_probability"], "2/5")

    def test_multiple_games_commit_independently_and_are_visible_to_another_connection(self):
        run_id = self.create_run()
        reader = repository.connect_database(self.database_path)
        self.addCleanup(reader.close)
        committed_ids = []
        for index in range(3):
            committed_ids.append(self.persist(run_id, index))
            self.assertEqual(self.counts(run_id), (index + 1, index + 1, 4 * (index + 1)))
            self.assertFalse(self.connection.in_transaction)
            self.assertEqual(repository.fetch_run(reader, run_id)["processed_games"], index + 1)
            self.assertEqual([row[0] for row in reader.execute(
                "SELECT game_id FROM games WHERE run_id = ? ORDER BY game_index", (run_id,),
            )], committed_ids)
            for game_id in committed_ids:
                self.assertEqual([row[0] for row in reader.execute(
                    "SELECT action_index FROM action_events WHERE game_id = ? ORDER BY action_index", (game_id,),
                )], [0, 1, 2, 3])
        self.assertEqual(repository.fetch_run(reader, run_id)["run_status"], schema.RUN_STATUS_CREATED)

    def test_explicit_transaction_contains_game_events_progress_and_one_commit(self):
        run_id = self.create_run()
        statements = []
        self.connection.set_trace_callback(statements.append)
        self.persist(run_id)
        self.connection.set_trace_callback(None)
        normalized = [statement.strip().upper() for statement in statements]
        self.assertEqual(normalized[0], "BEGIN")
        self.assertEqual(normalized[-1], "COMMIT")
        self.assertEqual(normalized.count("BEGIN"), 1)
        self.assertEqual(normalized.count("COMMIT"), 1)
        game_insert = next(i for i, sql in enumerate(normalized) if sql.startswith("INSERT INTO GAMES"))
        action_inserts = [i for i, sql in enumerate(normalized) if sql.startswith("INSERT INTO ACTION_EVENTS")]
        progress_update = next(i for i, sql in enumerate(normalized) if sql.startswith("UPDATE BENCHMARK_RUNS"))
        self.assertEqual(len(action_inserts), 4)
        self.assertLess(game_insert, min(action_inserts))
        self.assertLess(max(action_inserts), progress_update)

    def test_model_and_immutable_event_boundary_rejects_inappropriate_inputs(self):
        run_id = self.create_run()
        record, events = completed_game()
        for invalid_record, invalid_events in ((object(), events), (record, list(events)),
                                               (record, (object(),) * len(events)),
                                               (record, events[:-1])):
            with self.subTest(record=invalid_record, events=invalid_events):
                with self.assertRaises((TypeError, ValueError)):
                    repository.persist_completed_game(self.connection, run_id, invalid_record, invalid_events)
                self.assert_empty_run(run_id)

    def test_unsupported_domain_values_do_not_persist_by_integer_coincidence(self):
        run_id = self.create_run()
        record, events = completed_game()
        for field, value in (("action_type", 1), ("action_type", True),
                             ("action_type", GameStatus.WON), ("status_after", 1),
                             ("status_after", Action.FLAG), ("inference_category", 1)):
            with self.subTest(field=field, value=value):
                bad_event = copy.copy(events[1])
                # Exercise the defensive codec even for a forged frozen model.
                object.__setattr__(bad_event, field, value)
                with self.assertRaises((TypeError, ValueError)):
                    repository.persist_completed_game(
                        self.connection, run_id, record, (events[0], bad_event, *events[2:]),
                    )
                self.assert_empty_run(run_id)
        bad_record = copy.copy(record)
        object.__setattr__(bad_record, "result", 1)
        with self.assertRaises((TypeError, ValueError)):
            repository.persist_completed_game(self.connection, run_id, bad_record, events)
        self.assert_empty_run(run_id)


class RepositoryRollbackTests(RepositoryTestCase):
    def test_keyboard_interrupt_rolls_back_active_game_and_propagates_unchanged(self):
        interruption = KeyboardInterrupt("interrupted after event inserts")

        class InterruptingConnection(sqlite3.Connection):
            interrupt_events = False

            def executemany(connection, sql, parameters):
                cursor = super().executemany(sql, parameters)
                if connection.interrupt_events:
                    self.assertTrue(connection.in_transaction)
                    self.assertEqual(self.counts(run_id), (1, 2, 8))
                    raise interruption
                return cursor

        self.connection.close()
        connection = sqlite3.connect(
            self.database_path, isolation_level=None, factory=InterruptingConnection,
        )
        self.addCleanup(connection.close)
        with patch.object(repository.sqlite3, "connect", return_value=connection):
            self.connection = repository.connect_database(self.database_path)
        run_id = self.create_run()
        previous_id = self.persist(run_id)
        statements = []
        self.connection.set_trace_callback(statements.append)
        self.connection.interrupt_events = True
        try:
            with self.assertRaises(KeyboardInterrupt) as caught:
                self.persist(run_id, 1)
        finally:
            self.connection.interrupt_events = False
            self.connection.set_trace_callback(None)
        self.assertIs(caught.exception, interruption)
        self.assertEqual(statements.count("ROLLBACK"), 1)
        self.assertNotIn("COMMIT", statements)
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.counts(run_id), (1, 1, 4))
        self.assertEqual(self.connection.execute("SELECT game_id FROM games").fetchone()[0], previous_id)
        self.persist(run_id, 1)
        self.assertEqual(self.counts(run_id), (2, 2, 8))

    def test_rollback_failure_preserves_original_error_closes_connection_and_durable_work(self):
        run_id = self.create_run()
        previous_id = self.persist(run_id)
        previous_run = dict(repository.fetch_run(self.connection, run_id))
        previous_events = [tuple(row) for row in self.connection.execute(
            "SELECT * FROM action_events ORDER BY game_id, action_index",
        )]
        self.connection.execute(
            "CREATE TRIGGER reject_progress BEFORE UPDATE OF processed_games ON benchmark_runs "
            "BEGIN SELECT RAISE(ABORT, 'original persistence failure'); END"
        )
        transaction_operations = []

        def refuse_rollback(operation, argument, unused, database, source):
            if operation == sqlite3.SQLITE_TRANSACTION:
                transaction_operations.append(argument)
                if argument == "ROLLBACK":
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.connection.set_authorizer(refuse_rollback)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "original persistence failure") as caught:
            self.persist(run_id, 1)
        self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_CONSTRAINT_TRIGGER)
        self.assertEqual(caught.exception.__notes__, ["SQLite rollback failed: not authorized"])
        self.assertEqual(transaction_operations, ["BEGIN", "ROLLBACK"])
        with self.assertRaisesRegex(sqlite3.ProgrammingError, "closed"):
            self.connection.execute("SELECT 1")
        self.connection = repository.connect_database(self.database_path)
        self.addCleanup(self.connection.close)
        self.assertEqual(dict(repository.fetch_run(self.connection, run_id)), previous_run)
        self.assertEqual(self.counts(run_id), (1, 1, 4))
        self.assertEqual([tuple(row) for row in self.connection.execute(
            "SELECT game_id, game_index FROM games",
        )], [(previous_id, 0)])
        self.assertEqual([tuple(row) for row in self.connection.execute(
            "SELECT * FROM action_events ORDER BY game_id, action_index",
        )], previous_events)

    def test_sqlite_rollback_trigger_skips_second_rollback_and_connection_stays_usable(self):
        run_id = self.create_run()
        previous_id = self.persist(run_id)
        self.connection.execute(
            "CREATE TRIGGER rollback_progress BEFORE UPDATE OF processed_games ON benchmark_runs "
            "BEGIN SELECT RAISE(ROLLBACK, 'SQLite ended the transaction'); END"
        )
        transaction_operations = []

        def observe_transactions(operation, argument, unused, database, source):
            if operation == sqlite3.SQLITE_TRANSACTION:
                transaction_operations.append(argument)
            return sqlite3.SQLITE_OK

        self.connection.set_authorizer(observe_transactions)
        try:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "SQLite ended the transaction") as caught:
                self.persist(run_id, 1)
        finally:
            self.connection.set_authorizer(None)
        self.assertEqual(transaction_operations, ["BEGIN"])
        self.assertFalse(hasattr(caught.exception, "__notes__"))
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.counts(run_id), (1, 1, 4))
        self.assertEqual(self.connection.execute("SELECT game_id FROM games").fetchone()[0], previous_id)
        self.connection.execute("DROP TRIGGER rollback_progress")
        self.persist(run_id, 1)
        self.assertEqual(self.counts(run_id), (2, 2, 8))

    def test_game_insert_failure_rolls_back_without_progress(self):
        run_id = self.create_run()
        record, events = completed_game()
        invalid_record = replace(record, board_fingerprint="not-a-fingerprint")
        with self.assertRaises(sqlite3.IntegrityError):
            repository.persist_completed_game(self.connection, run_id, invalid_record, events)
        self.assert_empty_run(run_id)
        self.persist(run_id)
        self.assertEqual(self.counts(run_id), (1, 1, 4))

    def test_duplicate_game_index_preserves_original_game_events_and_progress(self):
        run_id = self.create_run()
        game_id = self.persist(run_id)
        original = [tuple(row) for row in self.connection.execute(
            "SELECT * FROM action_events WHERE game_id = ? ORDER BY action_index", (game_id,),
        )]
        with self.assertRaises(sqlite3.IntegrityError):
            self.persist(run_id)
        self.assertEqual(self.counts(run_id), (1, 1, 4))
        self.assertEqual(original, [tuple(row) for row in self.connection.execute(
            "SELECT * FROM action_events WHERE game_id = ? ORDER BY action_index", (game_id,),
        )])
        self.assertFalse(self.connection.in_transaction)

    def test_action_insert_failure_rolls_back_game_and_preceding_action_rows(self):
        run_id = self.create_run()
        record, events = completed_game()
        # The second row conflicts only after the game and first event are inserted.
        invalid_events = (events[0], replace(events[1], action_index=0), *events[2:])
        with self.assertRaises(sqlite3.IntegrityError):
            repository.persist_completed_game(self.connection, run_id, record, invalid_events)
        self.assert_empty_run(run_id)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM action_events").fetchone()[0], 0)

    def test_progress_trigger_failure_rolls_back_current_game_only(self):
        run_id = self.create_run()
        previous_id = self.persist(run_id)
        self.connection.execute(
            "CREATE TRIGGER reject_progress BEFORE UPDATE OF processed_games ON benchmark_runs "
            "BEGIN SELECT RAISE(ABORT, 'progress failure'); END"
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "progress failure"):
            self.persist(run_id, 1)
        self.assertEqual(self.counts(run_id), (1, 1, 4))
        self.assertEqual(self.connection.execute("SELECT game_id FROM games").fetchone()[0], previous_id)
        self.assertFalse(self.connection.in_transaction)
        self.connection.execute("DROP TRIGGER reject_progress")
        self.persist(run_id, 1)
        self.assertEqual(self.counts(run_id), (2, 2, 8))

    def test_requested_games_overflow_rolls_back_inserted_game_and_events(self):
        run_id = self.create_run(requested_games=1)
        self.persist(run_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.persist(run_id, 1)
        self.assertEqual(self.counts(run_id), (1, 1, 4))
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT game_index FROM games").fetchone()[0], 0)

    def test_commit_failure_rolls_back_current_game_and_preserves_prior_commit(self):
        run_id = self.create_run()
        previous_id = self.persist(run_id)
        transaction_operations = []

        def refuse_commit(operation, argument, unused, database, source):
            if operation == sqlite3.SQLITE_TRANSACTION:
                transaction_operations.append(argument)
                if argument == "COMMIT":
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.connection.set_authorizer(refuse_commit)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                self.persist(run_id, 1)
        finally:
            self.connection.set_authorizer(None)
        self.assertEqual(transaction_operations, ["BEGIN", "COMMIT", "ROLLBACK"])
        self.assertEqual(self.counts(run_id), (1, 1, 4))
        self.assertEqual(self.connection.execute("SELECT game_id FROM games").fetchone()[0], previous_id)
        self.assertFalse(self.connection.in_transaction)
        self.persist(run_id, 1)
        self.assertEqual(self.counts(run_id), (2, 2, 8))

    def test_failed_status_can_commit_separately_after_game_rollback(self):
        run_id = self.create_run()
        repository.update_run_status(self.connection, run_id, schema.RUN_STATUS_RUNNING, started_at=STARTED_AT)
        record, events = completed_game()
        invalid_events = (events[0], replace(events[1], action_index=0), *events[2:])
        with self.assertRaises(sqlite3.IntegrityError):
            repository.persist_completed_game(self.connection, run_id, record, invalid_events)
        self.assert_empty_run(run_id)
        repository.update_run_status(
            self.connection, run_id, schema.RUN_STATUS_FAILED,
            finished_at=FINISHED_AT, failure_code="TEST_PERSISTENCE_FAILURE",
        )
        row = repository.fetch_run(self.connection, run_id)
        self.assertEqual((row["run_status"], row["finished_at"], row["failure_code"]),
                         (schema.RUN_STATUS_FAILED, FINISHED_AT, "TEST_PERSISTENCE_FAILURE"))
        self.assert_empty_run(run_id)
        reader = repository.connect_database(self.database_path)
        self.addCleanup(reader.close)
        self.assertEqual(repository.fetch_run(reader, run_id)["run_status"], schema.RUN_STATUS_FAILED)

    def test_operations_reject_caller_transaction_without_committing_or_rolling_it_back(self):
        run_id = self.create_run()
        record, events = completed_game()
        self.connection.execute("BEGIN")
        self.connection.execute("UPDATE benchmark_runs SET app_version = 'pending' WHERE run_id = ?", (run_id,))
        operations = (
            lambda: self.create_run(),
            lambda: repository.update_run_status(self.connection, run_id, schema.RUN_STATUS_RUNNING),
            lambda: repository.persist_completed_game(self.connection, run_id, record, events),
        )
        for operation in operations:
            with self.assertRaises(RuntimeError):
                operation()
            self.assertTrue(self.connection.in_transaction)
            self.assertEqual(repository.fetch_run(self.connection, run_id)["app_version"], "pending")
        self.connection.execute("ROLLBACK")
        self.assertIsNone(repository.fetch_run(self.connection, run_id)["app_version"])
        self.assert_empty_run(run_id)

    def test_implicit_sqlite_transaction_mode_is_rejected_before_writing(self):
        run_id = self.create_run()
        raw = sqlite3.connect(self.database_path)
        self.addCleanup(raw.close)
        record, events = completed_game()
        operations = (
            lambda: repository.create_run(raw, **run_inputs()),
            lambda: repository.update_run_status(raw, run_id, schema.RUN_STATUS_RUNNING),
            lambda: repository.persist_completed_game(raw, run_id, record, events),
        )
        for operation in operations:
            with self.assertRaises(RuntimeError):
                operation()
            self.assertFalse(raw.in_transaction)
        self.assert_empty_run(run_id)


class RepositoryForeignKeyTests(RepositoryTestCase):
    def test_missing_run_and_missing_game_are_rejected_by_enabled_foreign_keys(self):
        run_id = self.create_run()
        record, events = completed_game()
        with self.assertRaises(sqlite3.IntegrityError):
            repository.persist_completed_game(self.connection, run_id + 1000, record, events)
        self.assert_empty_run(run_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO action_events "
                "(game_id, action_index, action_type, x, y, status_after, "
                "safe_cells_opened_delta, explicit_flag_delta) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (1000, 0, schema.ACTION_OPEN, 0, 0, schema.STATUS_AFTER_PLAYING, 0, 0),
            )
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM action_events").fetchone()[0], 0)

    def test_same_index_in_different_runs_and_repeated_seed_fingerprint_are_allowed(self):
        first = self.create_run()
        second = self.create_run()
        self.persist(first, 0)
        self.persist(first, 1)
        self.persist(second, 0)
        self.assertEqual(self.counts(first), (2, 2, 8))
        self.assertEqual(self.counts(second), (1, 1, 4))

    def test_run_delete_cascades_games_and_events_while_retaining_other_run(self):
        first = self.create_run()
        second = self.create_run()
        self.persist(first, 0)
        self.persist(first, 1)
        retained_id = self.persist(second, 0)
        self.connection.execute("DELETE FROM benchmark_runs WHERE run_id = ?", (first,))
        self.assertIsNone(repository.fetch_run(self.connection, first))
        self.assertEqual([row[0] for row in self.connection.execute("SELECT game_id FROM games")], [retained_id])
        self.assertEqual(self.counts(second), (1, 1, 4))
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM action_events").fetchone()[0], 4)

    def test_game_delete_cascades_only_its_events(self):
        run_id = self.create_run()
        deleted_id = self.persist(run_id, 0)
        retained_id = self.persist(run_id, 1)
        self.connection.execute("DELETE FROM games WHERE game_id = ?", (deleted_id,))
        self.assertIsNotNone(repository.fetch_run(self.connection, run_id))
        self.assertEqual([row[0] for row in self.connection.execute("SELECT DISTINCT game_id FROM action_events")],
                         [retained_id])
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM action_events").fetchone()[0], 4)


class RepositoryDependencyTests(unittest.TestCase):
    def test_repository_imports_only_standard_library_and_generic_persistence_models(self):
        source = Path(repository.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed_local = {"telemetry_model", "telemetry_schema", "core_engine"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                if node.module == "core_engine":
                    self.assertLessEqual({alias.name for alias in node.names}, {"Action", "GameStatus"})
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                self.assertIn(root, sys.stdlib_module_names | allowed_local)
        self.assertFalse(any(isinstance(node, ast.Attribute) and node.attr == "value" for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
