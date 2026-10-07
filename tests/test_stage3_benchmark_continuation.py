"""Stage-3 continuation admits only authenticated, unchanged official prefixes."""

import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

import benchmark_runner as lifecycle
import stage3_benchmark_runner as runner
import stage3_physical as physical
import telemetry_repository as repository
import telemetry_schema as schema
from benchmark_board import EXPERT_GENERAL_V1, generate_board
from tests.test_telemetry_repository import CREATED_AT, STARTED_AT, run_inputs


COMMIT = "1234567890abcdef" * 2 + "12345678"
CANONICAL_CONFIG = {
    "initial_open": [0, 0],
    "initial_cursor": [0, 0],
    "algorithm_spec_version": 1,
    "algorithm_spec_sha256": "6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",
    "physical_model_id": "overlap_floor_log2_distance_v1",
    "physical_profile_version": 1,
    "physical_profile_sha256": "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",
    "timing_table_sha256": "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b",
    "timing_unit": "us",
}


class Stage3BenchmarkContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Three real complete expert games, reused only to install persisted prefixes.
        cls.games = [runner._play_game(EXPERT_GENERAL_V1, index) for index in range(3)]
        cls.environment = lifecycle._capture_environment()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "continuation.sqlite3"
        self.fixture_index = 0
        self.provenance = self.enterContext(patch.object(
            lifecycle, "_capture_git_provenance", return_value=(COMMIT, False),
        ))
        self.capture_environment = self.enterContext(patch.object(
            lifecycle, "_capture_environment", return_value=self.environment,
        ))

    def prefix(self, processed=1, requested=3, **overrides):
        self.fixture_index += 1
        self.database = self.directory / f"continuation-{self.fixture_index}.sqlite3"
        values = run_inputs(
            telemetry_schema_version=2, git_commit=COMMIT,
            solver_stage="STAGE_3", solver_policy="E_FIRST_FIRST_REVEAL_V1",
            solver_config_snapshot=CANONICAL_CONFIG,
            width=30, height=16, num_mines=99, benchmark_set_id="EXPERT_GENERAL_V1",
            requested_games=requested, environment_snapshot=self.environment,
            started_at=STARTED_AT, run_status="RUNNING",
            app_version="preserved-app", difficulty_name="preserved-difficulty",
        )
        values.update(overrides)
        with closing(repository.connect_database(self.database)) as connection:
            self.run_id = repository.create_run(connection, **values)
            for record, events in self.games[:processed]:
                repository.persist_completed_game(connection, self.run_id, record, events)
        return self.run_id

    def rows(self, table, order):
        with closing(repository.connect_database_readonly(self.database)) as reader:
            return [dict(row) for row in reader.execute(f"SELECT * FROM {table} ORDER BY {order}")]

    def run_row(self):
        with closing(repository.connect_database_readonly(self.database)) as reader:
            return dict(repository.fetch_run(reader, self.run_id))

    def snapshot(self):
        with closing(repository.connect_database_readonly(self.database)) as reader:
            return tuple(reader.iterdump())

    def mutate(self, sql, parameters=()):
        with closing(repository.connect_database(self.database)) as connection:
            connection.execute(sql, parameters)

    def assert_failed(self, code, processed):
        row = self.run_row()
        self.assertEqual((row["run_status"], row["failure_code"], row["processed_games"]),
                         ("FAILED", code, processed))
        self.assertIsNotNone(row["finished_at"])
        games = self.rows("games", "game_index")
        self.assertEqual([game["game_index"] for game in games], list(range(processed)))
        self.assertEqual(len(self.rows("action_events", "game_id, action_index")),
                         sum(game["total_actions"] for game in games))

    def assert_rejected(self, message, *, run_id=None, error=ValueError, **kwargs):
        before_dump = self.snapshot()
        before_bytes = self.database.read_bytes()
        statements, closed_states = [], []

        class ObservedConnection(sqlite3.Connection):
            def close(connection):
                closed_states.append((connection.total_changes, connection.in_transaction))
                super().close()

        connect = sqlite3.connect

        def observe(*args, **options):
            connection = connect(*args, **options, factory=ObservedConnection)
            connection.set_trace_callback(statements.append)
            return connection

        with (
            patch.object(repository.sqlite3, "connect", side_effect=observe),
            patch.object(repository, "connect_database_for_continuation") as writer,
            patch.object(repository, "connect_database") as fresh,
            patch.object(schema, "initialize_schema") as initialize,
            patch.object(repository, "update_run_status") as update,
            patch.object(repository, "persist_completed_game") as persist,
            patch.object(runner, "_play_game") as play,
            self.assertRaisesRegex(error, message),
        ):
            runner.continue_stage3_benchmark(
                self.database, self.run_id if run_id is None else run_id, **kwargs,
            )
        for operation in (writer, fresh, initialize, update, persist, play):
            operation.assert_not_called()
        self.assertTrue(all(state == (0, False) for state in closed_states))
        self.assertTrue(all(sql.startswith("SELECT ") or sql in {
            "PRAGMA foreign_keys = ON", "PRAGMA foreign_keys", "PRAGMA user_version",
            "PRAGMA quick_check", "PRAGMA foreign_key_check",
        } for sql in statements), statements)
        self.assertEqual(self.database.read_bytes(), before_bytes)
        self.assertEqual(self.snapshot(), before_dump)

    def test_continues_exact_prefix_and_preserves_committed_rows_and_original_metadata(self):
        run_id = self.prefix(requested=3)
        before_run = self.run_row()
        before_games = self.rows("games", "game_index")
        before_events = self.rows("action_events", "game_id, action_index")
        progress, writers = [], []
        connect = repository.connect_database_for_continuation

        def capture(path):
            connection = connect(path)
            writers.append(connection)
            return connection

        def report(identity, processed, requested):
            self.assertFalse(writers[0].in_transaction)
            with closing(repository.connect_database_readonly(self.database)) as reader:
                self.assertEqual(repository.fetch_run(reader, identity)["processed_games"], processed)
                self.assertEqual(repository.fetch_game_indices(reader, identity), tuple(range(processed)))
            progress.append((identity, processed, requested))

        with (
            patch.object(repository, "connect_database_for_continuation", side_effect=capture),
            patch.object(repository, "create_run") as create,
            patch.object(schema, "initialize_schema") as initialize,
            patch.object(runner, "generate_board", wraps=generate_board) as generate,
        ):
            self.assertEqual(runner.continue_stage3_benchmark(self.database, run_id, progress=report), run_id)
        create.assert_not_called()
        initialize.assert_not_called()
        self.provenance.assert_called_once_with(Path(runner.__file__).resolve().parent)
        self.capture_environment.assert_called_once_with()
        self.assertEqual([call.args for call in generate.call_args_list],
                         [(EXPERT_GENERAL_V1, 1), (EXPERT_GENERAL_V1, 2)])
        self.assertEqual(progress, [(run_id, 2, 3), (run_id, 3, 3)])
        after = self.run_row()
        self.assertEqual((after["run_status"], after["processed_games"]), ("COMPLETED", 3))
        self.assertIsNotNone(after["finished_at"])
        for field, value in before_run.items():
            if field not in {"run_status", "processed_games", "finished_at"}:
                self.assertEqual(after[field], value, field)
        games = self.rows("games", "game_index")
        self.assertEqual(games[:1], before_games)
        self.assertEqual([row["game_index"] for row in games], [0, 1, 2])
        self.assertEqual([row["seed"] for row in games], [0, 1, 2])
        self.assertEqual(self.rows("action_events", "game_id, action_index")[:len(before_events)], before_events)
        with self.assertRaises(sqlite3.ProgrammingError):
            writers[0].execute("SELECT 1")

    def test_continued_games_equal_uninterrupted_semantics_excluding_compute_timing(self):
        run_id = self.prefix(requested=3)
        runner.continue_stage3_benchmark(self.database, run_id)
        continued = self.database
        reference = self.directory / "reference.sqlite3"
        runner.run_stage3_benchmark(reference, 3, official=True)

        def facts(path, table, order, excluded):
            with closing(repository.connect_database_readonly(path)) as reader:
                return [{key: row[key] for key in row.keys() if key not in excluded}
                        for row in reader.execute(f"SELECT * FROM {table} ORDER BY {order}")]

        for table, order, excluded in (
            ("games", "game_index", {"compute_time_total_ns", "compute_time_max_ns"}),
            ("action_events", "game_id, action_index", {"decision_compute_ns"}),
        ):
            self.assertEqual(facts(continued, table, order, excluded),
                             facts(reference, table, order, excluded))

    def test_empty_prefix_starts_at_zero(self):
        run_id = self.prefix(processed=0, requested=1)
        with patch.object(runner, "generate_board", wraps=generate_board) as generate:
            runner.continue_stage3_benchmark(self.database, run_id)
        generate.assert_called_once_with(EXPERT_GENERAL_V1, 0)
        self.assertEqual(self.run_row()["run_status"], "COMPLETED")

    def test_finalize_only_preserves_all_rows_and_completion_precedes_stop(self):
        run_id = self.prefix(processed=3, requested=3)
        before = self.snapshot()
        stop, progress = Mock(return_value=True), Mock()
        with patch.object(runner, "_play_game") as play:
            runner.continue_stage3_benchmark(self.database, run_id, stop_requested=stop, progress=progress)
        play.assert_not_called()
        stop.assert_not_called()
        progress.assert_not_called()
        unchanged = lambda dump: tuple(sql for sql in dump if not sql.startswith('INSERT INTO "benchmark_runs"'))
        self.assertEqual(unchanged(before), unchanged(self.snapshot()))
        row = self.run_row()
        self.assertEqual((row["run_status"], row["processed_games"], row["requested_games"]),
                         ("COMPLETED", 3, 3))
        self.assertEqual((row["created_at"], row["started_at"]), (CREATED_AT, STARTED_AT))
        self.assertIsNotNone(row["finished_at"])

    def test_missing_path_is_rejected_before_any_sqlite_connection(self):
        with patch.object(repository.sqlite3, "connect") as connect, self.assertRaisesRegex(ValueError, "existing"):
            runner.continue_stage3_benchmark(self.database, 1)
        connect.assert_not_called()
        self.assertFalse(self.database.exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_unknown_and_invalid_run_ids_are_rejected_without_writes(self):
        self.prefix()
        self.assert_rejected("Unknown run_id", run_id=self.run_id + 1)
        for run_id in (0, -1, True, "1", 1.0, 1 << 63):
            with self.subTest(run_id=run_id):
                self.assert_rejected("run_id", run_id=run_id)

    def test_other_runs_and_their_games_and_events_are_untouched(self):
        run_id = self.prefix(requested=2)
        with closing(repository.connect_database(self.database)) as connection:
            other = repository.create_run(connection, **run_inputs())
            other_game = repository.persist_completed_game(connection, other, *self.games[0])
            before = dict(repository.fetch_run(connection, other))
        before_games = [row for row in self.rows("games", "game_id") if row["run_id"] == other]
        before_events = [row for row in self.rows("action_events", "game_id, action_index")
                         if row["game_id"] == other_game]
        runner.continue_stage3_benchmark(self.database, run_id)
        with closing(repository.connect_database_readonly(self.database)) as reader:
            self.assertEqual(dict(repository.fetch_run(reader, other)), before)
            self.assertEqual(reader.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 2)
        self.assertEqual([row for row in self.rows("games", "game_id") if row["run_id"] == other], before_games)
        self.assertEqual([row for row in self.rows("action_events", "game_id, action_index")
                          if row["game_id"] == other_game], before_events)

    def test_stage2_run_is_rejected_by_stage3_and_stage3_run_by_stage2(self):
        self.prefix(telemetry_schema_version=1, solver_stage="STAGE_2",
                    solver_policy="SIMPLE_MINIMUM_RISK",
                    solver_config_snapshot={"accept_guesses": True, "initial_open": [0, 0]})
        self.assert_rejected("telemetry_schema_version")
        self.prefix()
        before = self.snapshot()
        with patch.object(repository, "connect_database_for_continuation") as writer, \
                self.assertRaisesRegex(ValueError, "telemetry_schema_version"):
            lifecycle.continue_benchmark(self.database, self.run_id)
        writer.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_every_persisted_identity_field_requires_canonical_value(self):
        mismatches = {
            "telemetry_schema_version": 1, "solver_stage": "STAGE_2", "solver_policy": "OTHER_POLICY",
            "benchmark_set_id": "CUSTOM_V1", "width": 31, "height": 17, "num_mines": 98,
            "first_click_policy": "FIRST_CLICK_FIXED_1_0", "board_generator_version": "V2",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                self.prefix()
                self.mutate(f"UPDATE benchmark_runs SET {field} = ?", (value,))
                self.assert_rejected(field)

    def test_config_authentication_identity_and_strict_json_types_are_exact(self):
        mismatches = [
            {**CANONICAL_CONFIG, "initial_open": [1, 0]},
            {**CANONICAL_CONFIG, "initial_cursor": [0, 1]},
            {**CANONICAL_CONFIG, "initial_open": [False, 0]},
            {**CANONICAL_CONFIG, "initial_cursor": [0.0, 0]},
            {**CANONICAL_CONFIG, "algorithm_spec_version": True},
            {**CANONICAL_CONFIG, "physical_profile_version": 1.0},
            {**CANONICAL_CONFIG, "extra": 0},
            {key: value for key, value in CANONICAL_CONFIG.items() if key != "timing_unit"},
        ]
        for field in ("algorithm_spec_sha256", "physical_model_id", "physical_profile_sha256",
                      "timing_table_sha256", "timing_unit"):
            mismatches.append({**CANONICAL_CONFIG, field: "wrong"})
        for config in mismatches + ["invalid JSON"]:
            with self.subTest(config=config):
                self.prefix()
                encoded = config if isinstance(config, str) else json.dumps(config)
                self.mutate("UPDATE benchmark_runs SET solver_config_snapshot = ?", (encoded,))
                self.assert_rejected("solver_config_snapshot")

    def test_actual_profile_and_table_are_authenticated_before_writer(self):
        self.prefix()
        corrupt_profile = self.directory / "corrupt-profile.json"
        corrupt_profile.write_bytes(physical.PROFILE_PATH.read_bytes() + b" ")
        with patch.object(runner, "load_timing_table", side_effect=lambda: physical.load_timing_table(corrupt_profile)):
            self.assert_rejected("physical profile SHA-256")

        profile = json.loads(physical.PROFILE_PATH.read_bytes())
        profile["timing_table_us"][0][0] += 1
        raw = json.dumps(profile).encode("utf-8")
        corrupt_profile.write_bytes(raw)
        # Authenticate these supplied bytes, then independently detect their wrong table.
        with (
            patch.object(physical, "PROFILE_SHA256", hashlib.sha256(raw).hexdigest()),
            patch.object(runner, "load_timing_table", side_effect=lambda: physical.load_timing_table(corrupt_profile)),
        ):
            self.assert_rejected("timing table SHA-256")

    def test_stored_dirty_failure_and_finished_metadata_are_rejected(self):
        for field, value in (("git_dirty", 1), ("failure_code", "PRIOR_FAILURE"),
                             ("finished_at", "2026-09-26T00:01:00Z")):
            with self.subTest(field=field):
                self.prefix()
                self.mutate(f"UPDATE benchmark_runs SET {field} = ?", (value,))
                self.assert_rejected("RUNNING")

    def test_every_nonrunning_status_is_rejected(self):
        for status in ("CREATED", "COMPLETED", "ABORTED", "INTERRUPTED", "FAILED"):
            with self.subTest(status=status):
                self.prefix(processed=3, requested=3)
                self.mutate("UPDATE benchmark_runs SET run_status = ?", (status,))
                self.assert_rejected("RUNNING")

    def test_current_dirty_tree_commit_and_environment_mismatch_are_rejected(self):
        self.prefix()
        for provenance, message in (((COMMIT, True), "clean Git working tree"),
                                    (("f" * 40, False), "original git_commit")):
            with self.subTest(provenance=provenance):
                self.provenance.return_value = provenance
                self.assert_rejected(message)
        self.provenance.return_value = (COMMIT, False)
        for field in self.environment:
            with self.subTest(field=field):
                self.capture_environment.return_value = {**self.environment, field: "different"}
                self.assert_rejected("environment_snapshot")
        self.capture_environment.return_value = {
            **self.environment, "perf_counter": {**self.environment["perf_counter"], "monotonic": 1},
        }
        self.assert_rejected("environment_snapshot")

    def test_current_environment_key_order_is_normalized_but_stored_snapshot_is_exact(self):
        self.prefix(requested=2)
        canonical = self.run_row()["solver_config_snapshot"]
        self.mutate("UPDATE benchmark_runs SET solver_config_snapshot = ?",
                    (json.dumps(dict(reversed(list(CANONICAL_CONFIG.items())))),))
        self.assert_rejected("solver_config_snapshot")
        self.mutate("UPDATE benchmark_runs SET solver_config_snapshot = ?", (canonical,))
        self.capture_environment.return_value = dict(reversed(list(self.environment.items())))
        runner.continue_stage3_benchmark(self.database, self.run_id)
        self.assertEqual(self.run_row()["run_status"], "COMPLETED")

    def test_missing_shifted_gapped_extra_and_wrong_count_prefixes_reject(self):
        corruptions = (
            "DELETE FROM games WHERE game_index = 0",
            "DELETE FROM games WHERE game_index = 1",
            "DELETE FROM games WHERE game_index = 2",
            "UPDATE games SET game_index = game_index + 10",
            "UPDATE games SET game_index = 4 WHERE game_index = 1",
            "UPDATE benchmark_runs SET processed_games = 2",
            "UPDATE benchmark_runs SET processed_games = 4",
        )
        for sql in corruptions:
            with self.subTest(sql=sql):
                self.prefix(processed=3, requested=4)
                self.mutate(sql)
                self.assert_rejected("exact stored processed prefix")

    def test_processed_and_requested_bounds_and_types_are_not_repaired(self):
        for field, value in (("processed_games", -1), ("processed_games", 4),
                             ("processed_games", 1.5), ("requested_games", 3.5)):
            with self.subTest(field=field, value=value):
                self.prefix()
                with closing(repository.connect_database(self.database)) as connection:
                    connection.execute("PRAGMA ignore_check_constraints = ON")
                    connection.execute(f"UPDATE benchmark_runs SET {field} = ?", (value,))
                self.assert_rejected("Invalid")

    def test_finalize_only_runs_all_preflight_checks_including_physical_authentication(self):
        self.prefix(processed=3, requested=3)
        self.capture_environment.return_value = {"different": True}
        self.assert_rejected("environment_snapshot")
        self.capture_environment.return_value = self.environment
        with patch.object(runner, "load_timing_table", side_effect=ValueError("profile rejected")):
            self.assert_rejected("profile rejected")

    def test_rejection_preserves_delete_journal_mode(self):
        self.prefix()
        with closing(sqlite3.connect(self.database, isolation_level=None)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0], "delete")
        self.provenance.return_value = (COMMIT, True)
        self.assert_rejected("clean Git working tree")
        with closing(sqlite3.connect(self.database)) as reader:
            self.assertEqual(reader.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_preflight_capture_errors_do_not_mark_run_failed(self):
        self.prefix()
        for name in ("_capture_git_provenance", "_capture_environment"):
            with self.subTest(name=name), patch.object(lifecycle, name, side_effect=RuntimeError("capture failed")):
                self.assert_rejected("capture failed", error=RuntimeError)

    def test_requested_count_spec_provenance_and_identity_cannot_be_overridden(self):
        self.prefix()
        for kwargs in ({"requested_games": 4}, {"spec": EXPERT_GENERAL_V1},
                       {"repository_root": self.directory}, {"official": False},
                       {"solver_config_snapshot": CANONICAL_CONFIG}):
            with self.subTest(kwargs=kwargs):
                self.assert_rejected("unexpected keyword argument", error=TypeError, **kwargs)
        for kwargs in ({"stop_requested": False}, {"progress": 1}):
            with self.subTest(kwargs=kwargs):
                self.assert_rejected("callable", **kwargs)

    def test_stop_before_next_game_aborts_at_existing_prefix(self):
        self.prefix()
        with patch.object(runner, "_play_game") as play:
            runner.continue_stage3_benchmark(self.database, self.run_id, stop_requested=lambda: True)
        play.assert_not_called()
        row = self.run_row()
        self.assertEqual((row["run_status"], row["processed_games"]), ("ABORTED", 1))
        self.assertIsNone(row["failure_code"])
        self.assertIsNotNone(row["finished_at"])

    def test_midgame_stop_waits_for_commit_and_last_game_completion_wins(self):
        for requested, status in ((3, "ABORTED"), (2, "COMPLETED")):
            with self.subTest(requested=requested):
                self.prefix(requested=requested)
                stop = False
                play = runner._play_game

                def playing(*args):
                    nonlocal stop
                    stop = True
                    return play(*args)

                with patch.object(runner, "_play_game", side_effect=playing) as played:
                    runner.continue_stage3_benchmark(self.database, self.run_id, stop_requested=lambda: stop)
                played.assert_called_once_with(EXPERT_GENERAL_V1, 1)
                self.assertEqual((self.run_row()["run_status"], self.run_row()["processed_games"]), (status, 2))

    def test_execution_and_callback_failures_use_shared_codes_after_admission(self):
        self.prefix()
        error = RuntimeError("execution failed")
        with patch.object(runner, "_play_game", side_effect=error), self.assertRaises(RuntimeError) as raised:
            runner.continue_stage3_benchmark(self.database, self.run_id)
        self.assertIs(raised.exception, error)
        self.assert_failed("GAME_EXECUTION_FAILED", 1)
        for callback, code, committed in (("stop_requested", "STOP_REQUEST_FAILED", 1),
                                           ("progress", "PROGRESS_CALLBACK_FAILED", 2)):
            with self.subTest(callback=callback):
                self.prefix()
                with self.assertRaisesRegex(RuntimeError, "callback failed"):
                    runner.continue_stage3_benchmark(
                        self.database, self.run_id, **{callback: Mock(side_effect=RuntimeError("callback failed"))},
                    )
                self.assert_failed(code, committed)

    def test_finalize_only_failure_is_fatal_after_admission(self):
        self.prefix(processed=3, requested=3)
        update = repository.update_run_status

        def fail_completion(connection, run_id, status, **kwargs):
            if status == "COMPLETED":
                raise RuntimeError("finalization failed")
            return update(connection, run_id, status, **kwargs)

        with patch.object(repository, "update_run_status", side_effect=fail_completion), \
                self.assertRaisesRegex(RuntimeError, "finalization failed"):
            runner.continue_stage3_benchmark(self.database, self.run_id)
        self.assert_failed("RUN_FINALIZATION_FAILED", 3)

    def test_failed_update_is_best_effort_and_retains_primary_exception(self):
        self.prefix()
        error = RuntimeError("primary")
        before = self.snapshot()
        with (
            patch.object(runner, "_play_game", side_effect=error),
            patch.object(repository, "update_run_status", side_effect=sqlite3.OperationalError("unwritable")),
            self.assertRaises(RuntimeError) as raised,
        ):
            runner.continue_stage3_benchmark(self.database, self.run_id)
        self.assertIs(raised.exception, error)
        self.assertIn("Best-effort FAILED update failed", error.__notes__[0])
        self.assertEqual(self.snapshot(), before)

    def test_keyboard_interrupt_system_exit_preserve_running_and_resume_absolute_index(self):
        for exception in (KeyboardInterrupt, SystemExit):
            for boundary in ("game", "progress"):
                with self.subTest(exception=exception, boundary=boundary):
                    self.prefix()
                    error = exception("interrupted")
                    kwargs = {"progress": Mock(side_effect=error)} if boundary == "progress" else {}
                    with patch.object(repository, "update_run_status", wraps=repository.update_run_status) as update:
                        if boundary == "game":
                            with patch.object(runner, "_play_game", side_effect=error), self.assertRaises(exception):
                                runner.continue_stage3_benchmark(self.database, self.run_id)
                        else:
                            with self.assertRaises(exception):
                                runner.continue_stage3_benchmark(self.database, self.run_id, **kwargs)
                    update.assert_not_called()
                    row = self.run_row()
                    self.assertEqual(row["run_status"], "RUNNING")
                    self.assertIsNone(row["failure_code"])
                    self.assertIsNone(row["finished_at"])
                    expected = 1 if boundary == "game" else 2
                    self.assertEqual(row["processed_games"], expected)
                    with patch.object(runner, "generate_board", wraps=generate_board) as generate:
                        runner.continue_stage3_benchmark(self.database, self.run_id)
                    self.assertEqual(generate.call_args_list[0].args, (EXPERT_GENERAL_V1, expected))

    def test_uncommitted_game_rolls_back_all_rows_and_increment_then_replays_only_that_game(self):
        for exception in (KeyboardInterrupt, SystemExit, RuntimeError):
            with self.subTest(exception=exception):
                self.prefix(requested=2)
                before = self.snapshot()
                error = exception("before commit")
                statements, closed_states = [], []
                connect = sqlite3.connect

                class InterruptingConnection(sqlite3.Connection):
                    def execute(connection, sql, parameters=()):
                        cursor = super().execute(sql, parameters)
                        if sql.startswith("UPDATE benchmark_runs SET processed_games = processed_games + 1"):
                            self.assertTrue(connection.in_transaction)
                            self.assertEqual(repository.fetch_run(connection, self.run_id)["processed_games"], 2)
                            self.assertEqual(repository.fetch_game_indices(connection, self.run_id), (0, 1))
                            with closing(repository.connect_database_readonly(self.database)) as reader:
                                self.assertEqual(repository.fetch_run(reader, self.run_id)["processed_games"], 1)
                                self.assertEqual(repository.fetch_game_indices(reader, self.run_id), (0,))
                            raise error
                        return cursor

                    def close(connection):
                        closed_states.append(connection.in_transaction)
                        super().close()

                def interrupting_connect(*args, **kwargs):
                    if "mode=rw" in str(args[0]):
                        kwargs["factory"] = InterruptingConnection
                    connection = connect(*args, **kwargs)
                    connection.set_trace_callback(statements.append)
                    return connection

                with patch.object(repository.sqlite3, "connect", side_effect=interrupting_connect), \
                        self.assertRaises(exception) as raised:
                    runner.continue_stage3_benchmark(self.database, self.run_id)
                self.assertIs(raised.exception, error)
                self.assertIn("ROLLBACK", statements)
                self.assertEqual(closed_states, [False])
                if exception is RuntimeError:
                    self.assert_failed("GAME_PERSISTENCE_FAILED", 1)
                else:
                    self.assertEqual(self.snapshot(), before)
                    with patch.object(runner, "generate_board", wraps=generate_board) as generate:
                        runner.continue_stage3_benchmark(self.database, self.run_id)
                    generate.assert_called_once_with(EXPERT_GENERAL_V1, 1)
                    self.assertEqual(self.run_row()["run_status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
