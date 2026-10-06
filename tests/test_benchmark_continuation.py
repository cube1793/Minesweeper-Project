"""Frozen official continuation: passive rejection and committed-prefix execution."""

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

import benchmark_runner as runner
import telemetry_repository as repository
import telemetry_schema as schema
from benchmark_board import EXPERT_GENERAL_V1, generate_board
from benchmark_statistics import get_run_coverage
from tests.test_benchmark_runner import BenchmarkTestCase, COMMIT
from tests.test_telemetry_repository import CREATED_AT, STARTED_AT, run_inputs


class BenchmarkContinuationTests(BenchmarkTestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse real finalized expert games when constructing persisted fixtures.
        cls.games = [runner._play_game(EXPERT_GENERAL_V1, index) for index in range(4)]
        cls.environment = runner._capture_environment()

    def setUp(self):
        super().setUp()
        self.provenance = self.enterContext(patch.object(
            runner, "_capture_git_provenance", return_value=(COMMIT, False),
        ))
        self.capture_environment = self.enterContext(patch.object(
            runner, "_capture_environment", return_value=self.environment,
        ))

    def prefix(self, processed=1, requested=3, **overrides):
        self.execution_count += 1
        self.database = self.directory / f"continuation-{self.execution_count}.sqlite3"
        values = run_inputs(
            git_commit=COMMIT, solver_policy="SIMPLE_MINIMUM_RISK",
            solver_config_snapshot={"accept_guesses": True, "initial_open": [0, 0]},
            width=30, height=16, num_mines=99, benchmark_set_id="EXPERT_GENERAL_V1",
            requested_games=requested, environment_snapshot=self.environment,
            started_at=STARTED_AT, run_status="RUNNING",
            app_version="preserved-app", difficulty_name="preserved-difficulty",
        )
        values.update(overrides)
        with closing(repository.connect_database(self.database)) as connection:
            run_id = repository.create_run(connection, **values)
            for record, events in self.games[:processed]:
                repository.persist_completed_game(connection, run_id, record, events)
        self.run_id = run_id
        return run_id

    def snapshot(self):
        with closing(repository.connect_database_readonly(self.database)) as reader:
            return tuple(reader.iterdump())

    def mutate(self, sql, parameters=()):
        with closing(repository.connect_database(self.database)) as connection:
            connection.execute(sql, parameters)

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
            runner.continue_benchmark(
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

    def test_continues_same_run_absolute_seed_progress_and_preserves_original_rows(self):
        run_id = self.prefix(processed=2, requested=4)
        before_run = dict(self.run_row())
        before_games = [dict(row) for row in self.rows("games", "game_index")]
        before_events = [dict(row) for row in self.rows("action_events", "game_id, action_index")]
        progress = []
        writer_connections = []
        connect = repository.connect_database_for_continuation

        def capture(path):
            connection = connect(path)
            writer_connections.append(connection)
            return connection

        def report(identity, processed, requested):
            self.assertFalse(writer_connections[0].in_transaction)
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
            self.assertEqual(runner.continue_benchmark(self.database, run_id, progress=report), run_id)
        create.assert_not_called()
        initialize.assert_not_called()
        self.provenance.assert_called_once_with(Path(runner.__file__).resolve().parent)
        self.capture_environment.assert_called_once_with()
        self.assertEqual([call.args for call in generate.call_args_list],
                         [(EXPERT_GENERAL_V1, 2), (EXPERT_GENERAL_V1, 3)])
        self.assertEqual(progress, [(run_id, 3, 4), (run_id, 4, 4)])
        after = dict(self.run_row())
        self.assertEqual(after["run_status"], "COMPLETED")
        self.assertEqual(after["processed_games"], 4)
        self.assertIsNotNone(after["finished_at"])
        for field, value in before_run.items():
            if field not in {"run_status", "processed_games", "finished_at"}:
                self.assertEqual(after[field], value, field)
        games = [dict(row) for row in self.rows("games", "game_index")]
        self.assertEqual(games[:2], before_games)
        self.assertEqual([row["game_index"] for row in games], [0, 1, 2, 3])
        self.assertEqual([row["seed"] for row in games], [0, 1, 2, 3])
        events = [dict(row) for row in self.rows("action_events", "game_id, action_index")]
        self.assertEqual(events[:len(before_events)], before_events)
        with closing(repository.connect_database_readonly(self.database)) as reader:
            self.assertTrue(get_run_coverage(reader, run_id).official_eligible)
        with self.assertRaises(sqlite3.ProgrammingError):
            writer_connections[0].execute("SELECT 1")

    def test_continued_games_match_uninterrupted_reference_except_timing(self):
        run_id = self.prefix(processed=1, requested=3)
        runner.continue_benchmark(self.database, run_id)
        continued = self.database
        reference = self.directory / "reference.sqlite3"
        runner.run_benchmark(reference, 3, official=True)

        def facts(path, table, order, excluded):
            with closing(repository.connect_database_readonly(path)) as connection:
                return [{key: row[key] for key in row.keys() if key not in excluded}
                        for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")]

        for table, order, excluded in (
            ("games", "game_index", {"compute_time_total_ns", "compute_time_max_ns"}),
            ("action_events", "game_id, action_index", {"decision_compute_ns"}),
        ):
            self.assertEqual(facts(continued, table, order, excluded),
                             facts(reference, table, order, excluded))

    def test_empty_prefix_starts_at_zero(self):
        run_id = self.prefix(processed=0, requested=1)
        with patch.object(runner, "generate_board", wraps=generate_board) as generate:
            runner.continue_benchmark(self.database, run_id)
        generate.assert_called_once_with(EXPERT_GENERAL_V1, 0)
        self.assertEqual(self.run_row()["run_status"], "COMPLETED")

    def test_finalize_only_preserves_all_games_and_events_and_completion_wins_over_stop(self):
        run_id = self.prefix(processed=3, requested=3)
        before = self.snapshot()
        stop, progress = Mock(return_value=True), Mock()
        with patch.object(runner, "_play_game") as play:
            runner.continue_benchmark(self.database, run_id, stop_requested=stop, progress=progress)
        play.assert_not_called()
        stop.assert_not_called()
        progress.assert_not_called()
        after = self.snapshot()
        # The complete logical database changes only in the existing run row.
        unchanged = lambda dump: tuple(sql for sql in dump if not sql.startswith('INSERT INTO "benchmark_runs"'))
        self.assertEqual(unchanged(before), unchanged(after))
        row = self.run_row()
        self.assertEqual((row["run_status"], row["processed_games"], row["requested_games"]),
                         ("COMPLETED", 3, 3))
        self.assertEqual((row["created_at"], row["started_at"]), (CREATED_AT, STARTED_AT))
        self.assertIsNotNone(row["finished_at"])

    def test_missing_path_is_rejected_before_any_connection(self):
        with patch.object(repository.sqlite3, "connect") as connect, self.assertRaisesRegex(ValueError, "existing"):
            runner.continue_benchmark(self.database, 1)
        connect.assert_not_called()
        self.assertFalse(self.database.exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_invalid_empty_uninitialized_and_wrong_version_files_are_unchanged(self):
        for kind in ("empty", "text", "uninitialized", "version-zero", "version-two", "v1-impostor"):
            with self.subTest(kind=kind):
                path = self.directory / f"{kind}.sqlite3"
                if kind in ("empty", "text"):
                    path.write_bytes(b"" if kind == "empty" else b"This is not a SQLite database.")
                else:
                    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
                        connection.execute("CREATE TABLE unrelated (value TEXT)")
                        if kind == "version-zero":
                            schema.initialize_schema(connection)
                            connection.execute("PRAGMA user_version = 0")
                        elif kind == "version-two":
                            connection.execute("PRAGMA user_version = 2")
                        elif kind == "v1-impostor":
                            for table in ("benchmark_runs", "games", "action_events"):
                                connection.execute(f"CREATE TABLE {table} (fake INTEGER)")
                            connection.execute("PRAGMA user_version = 1")
                before = path.read_bytes()
                with (
                    patch.object(repository, "connect_database") as fresh,
                    patch.object(repository, "connect_database_for_continuation") as writer,
                    patch.object(schema, "initialize_schema") as initialize,
                    self.assertRaises((ValueError, sqlite3.DatabaseError)),
                ):
                    runner.continue_benchmark(path, 1)
                fresh.assert_not_called()
                writer.assert_not_called()
                initialize.assert_not_called()
                self.assertEqual(path.read_bytes(), before)

    def test_existing_run_must_be_explicit_and_present(self):
        self.prefix()
        self.assert_rejected("Unknown run_id", run_id=self.run_id + 1)
        for run_id in (0, -1, True, "1", 1.0, 1 << 63):
            with self.subTest(run_id=run_id):
                self.assert_rejected("run_id", run_id=run_id)

    def test_explicit_target_leaves_other_runs_and_their_games_unchanged(self):
        run_id = self.prefix(requested=2)
        with closing(repository.connect_database(self.database)) as connection:
            other = repository.create_run(connection, **run_inputs())
            repository.persist_completed_game(connection, other, *self.games[0])
            before = dict(repository.fetch_run(connection, other))
        before_games = [dict(row) for row in self.rows("games", "game_id") if row["run_id"] == other]
        other_game = before_games[0]["game_id"]
        before_events = [dict(row) for row in self.rows("action_events", "game_id, action_index")
                         if row["game_id"] == other_game]
        runner.continue_benchmark(self.database, run_id)
        with closing(repository.connect_database_readonly(self.database)) as reader:
            self.assertEqual(dict(repository.fetch_run(reader, other)), before)
            self.assertEqual(reader.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 2)
        self.assertEqual([dict(row) for row in self.rows("games", "game_id") if row["run_id"] == other],
                         before_games)
        self.assertEqual([dict(row) for row in self.rows("action_events", "game_id, action_index")
                          if row["game_id"] == other_game], before_events)

    def test_wrong_table_definition_trigger_and_foreign_key_corruption_reject_passively(self):
        for corruption in ("column", "trigger", "orphan"):
            with self.subTest(corruption=corruption):
                self.prefix()
                with closing(sqlite3.connect(self.database, isolation_level=None)) as connection:
                    if corruption == "column":
                        connection.execute("ALTER TABLE action_events RENAME COLUMN x TO wrong_x")
                    elif corruption == "trigger":
                        connection.execute("CREATE TRIGGER alter_progress AFTER INSERT ON games "
                                           "BEGIN UPDATE benchmark_runs SET processed_games = 0; END")
                    else:
                        connection.execute("UPDATE action_events SET game_id = 999")
                self.assert_rejected({"column": "table definition", "trigger": "trigger",
                                      "orphan": "foreign keys"}[corruption])

    def test_no_requested_total_spec_or_provenance_overrides_are_accepted(self):
        self.prefix()
        for kwargs in ({"requested_games": 4}, {"spec": EXPERT_GENERAL_V1},
                       {"repository_root": self.directory}, {"official": False}):
            with self.subTest(kwargs=kwargs):
                self.assert_rejected("unexpected keyword argument", error=TypeError, **kwargs)
        for kwargs in ({"stop_requested": False}, {"progress": 1}):
            with self.subTest(kwargs=kwargs):
                self.assert_rejected("callable", **kwargs)

    def test_every_nonrunning_state_rejects_without_changes(self):
        for status in ("CREATED", "COMPLETED", "ABORTED", "INTERRUPTED", "FAILED"):
            with self.subTest(status=status):
                self.prefix(processed=3, requested=3)
                self.mutate("UPDATE benchmark_runs SET run_status = ?", (status,))
                self.assert_rejected("RUNNING")

    def test_stored_dirty_failure_and_finish_metadata_reject_without_changes(self):
        for field, value in (("git_dirty", 1), ("failure_code", "PRIOR_FAILURE"),
                             ("finished_at", "2026-09-26T00:01:00Z")):
            with self.subTest(field=field):
                self.prefix()
                self.mutate(f"UPDATE benchmark_runs SET {field} = ?", (value,))
                self.assert_rejected("RUNNING")

    def test_corrupt_processed_bounds_and_types_reject_without_repair(self):
        for field, value in (("processed_games", -1), ("processed_games", 4),
                             ("processed_games", 1.5), ("requested_games", 3.5)):
            with self.subTest(field=field, value=value):
                self.prefix()
                with closing(repository.connect_database(self.database)) as connection:
                    connection.execute("PRAGMA ignore_check_constraints = ON")
                    connection.execute(f"UPDATE benchmark_runs SET {field} = ?", (value,))
                self.assert_rejected("Invalid")

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

    def test_current_dirty_tree_and_commit_mismatch_reject_without_changes(self):
        self.prefix()
        for provenance, message in (((COMMIT, True), "clean Git working tree"),
                                    (("f" * 40, False), "original git_commit")):
            with self.subTest(provenance=provenance):
                self.provenance.return_value = provenance
                self.assert_rejected(message)

    def test_all_persisted_identity_fields_require_exact_canonical_values(self):
        mismatches = {
            "telemetry_schema_version": 2, "benchmark_set_id": "CUSTOM_V1",
            "width": 31, "height": 17, "num_mines": 98,
            "first_click_policy": "FIRST_CLICK_FIXED_1_0", "board_generator_version": "V2",
            "solver_stage": "STAGE_3", "solver_policy": "OTHER_POLICY",
            "solver_config_snapshot": '{"accept_guesses":false,"initial_open":[0,0]}',
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                self.prefix()
                self.mutate(f"UPDATE benchmark_runs SET {field} = ?", (value,))
                self.assert_rejected(field)
        for config in ('{"accept_guesses":1,"initial_open":[0,0]}',
                       '{"accept_guesses":true,"initial_open":[1,0]}',
                       '{"accept_guesses":true,"initial_open":[0,0],"extra":0}', "invalid json"):
            with self.subTest(config=config):
                self.prefix()
                self.mutate("UPDATE benchmark_runs SET solver_config_snapshot = ?", (config,))
                self.assert_rejected("solver_config_snapshot")

    def test_environment_exact_serialization_and_every_snapshot_field_are_checked(self):
        self.prefix()
        for field in self.environment:
            with self.subTest(field=field):
                self.capture_environment.return_value = {**self.environment, field: "different"}
                self.assert_rejected("environment_snapshot")
        # Even bool vs numeric equality must not weaken deterministic JSON equality.
        self.capture_environment.return_value = {
            **self.environment, "perf_counter": {**self.environment["perf_counter"], "monotonic": 1},
        }
        self.assert_rejected("environment_snapshot")
        self.capture_environment.return_value = dict(reversed(list(self.environment.items())))
        runner.continue_benchmark(self.database, self.run_id)
        self.assertEqual(self.run_row()["run_status"], "COMPLETED")

    def test_capture_errors_are_rejections_not_fatal_run_failures(self):
        self.prefix()
        for name in ("_capture_git_provenance", "_capture_environment"):
            with self.subTest(name=name), patch.object(runner, name, side_effect=RuntimeError("capture error")):
                self.assert_rejected("capture error", error=RuntimeError)

    def test_finalize_only_still_requires_all_preflight_checks(self):
        self.prefix(processed=3, requested=3)
        self.capture_environment.return_value = {"different": True}
        self.assert_rejected("environment_snapshot")

    def test_rejected_preflight_does_not_reconfigure_delete_journal_mode(self):
        self.prefix()
        with closing(sqlite3.connect(self.database, isolation_level=None)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0], "delete")
        self.provenance.return_value = (COMMIT, True)
        self.assert_rejected("clean Git working tree")
        with closing(sqlite3.connect(self.database)) as reader:
            self.assertEqual(reader.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_stop_before_next_game_aborts_at_existing_boundary(self):
        run_id = self.prefix()
        with patch.object(runner, "_play_game") as play:
            runner.continue_benchmark(self.database, run_id, stop_requested=lambda: True)
        play.assert_not_called()
        row = self.run_row()
        self.assertEqual((row["run_status"], row["processed_games"]), ("ABORTED", 1))
        self.assertIsNone(row["failure_code"])
        self.assertIsNotNone(row["finished_at"])

    def test_stop_during_game_commits_it_and_completion_wins_on_last_game(self):
        for requested, status in ((3, "ABORTED"), (2, "COMPLETED")):
            with self.subTest(requested=requested):
                run_id = self.prefix(requested=requested)
                stop = False
                play = runner._play_game

                def playing(*args):
                    nonlocal stop
                    stop = True
                    return play(*args)

                with patch.object(runner, "_play_game", side_effect=playing) as played:
                    runner.continue_benchmark(self.database, run_id, stop_requested=lambda: stop)
                played.assert_called_once_with(EXPERT_GENERAL_V1, 1)
                row = self.run_row()
                self.assertEqual((row["run_status"], row["processed_games"]), (status, 2))

    def test_normal_execution_failure_after_preflight_uses_existing_failed_lifecycle(self):
        self.prefix()
        error = RuntimeError("execution failed")
        with patch.object(runner, "_play_game", side_effect=error), self.assertRaises(RuntimeError) as raised:
            runner.continue_benchmark(self.database, self.run_id)
        self.assertIs(raised.exception, error)
        self.assert_failed("GAME_EXECUTION_FAILED", 1)

    def test_callback_failures_retain_committed_prefix_and_existing_failure_codes(self):
        for callback, code, committed in (("stop_requested", "STOP_REQUEST_FAILED", 1),
                                           ("progress", "PROGRESS_CALLBACK_FAILED", 2)):
            with self.subTest(callback=callback):
                self.prefix()
                with self.assertRaisesRegex(RuntimeError, "callback failed"):
                    runner.continue_benchmark(
                        self.database, self.run_id, **{callback: Mock(side_effect=RuntimeError("callback failed"))},
                    )
                self.assert_failed(code, committed)

    def test_finalize_only_failure_is_fatal_after_successful_preflight(self):
        self.prefix(processed=3, requested=3)
        update = repository.update_run_status

        def fail_completion(connection, run_id, status, **kwargs):
            if status == "COMPLETED":
                raise RuntimeError("finalization failed")
            return update(connection, run_id, status, **kwargs)

        with patch.object(repository, "update_run_status", side_effect=fail_completion), \
                self.assertRaisesRegex(RuntimeError, "finalization failed"):
            runner.continue_benchmark(self.database, self.run_id)
        self.assert_failed("RUN_FINALIZATION_FAILED", 3)

    def test_failed_update_remains_best_effort_and_preserves_primary_exception(self):
        self.prefix()
        error = RuntimeError("primary")
        before = self.snapshot()
        with (
            patch.object(runner, "_play_game", side_effect=error),
            patch.object(repository, "update_run_status", side_effect=sqlite3.OperationalError("unwritable")),
            self.assertRaises(RuntimeError) as raised,
        ):
            runner.continue_benchmark(self.database, self.run_id)
        self.assertIs(raised.exception, error)
        self.assertIn("Best-effort FAILED update failed", error.__notes__[0])
        self.assertEqual(self.snapshot(), before)

    def test_keyboard_interrupt_and_system_exit_leave_running_then_allow_continuation(self):
        for exception in (KeyboardInterrupt, SystemExit):
            for boundary in ("game", "progress"):
                with self.subTest(exception=exception, boundary=boundary):
                    self.prefix()
                    error = exception("interrupted")
                    kwargs = {"progress": Mock(side_effect=error)} if boundary == "progress" else {}
                    with patch.object(repository, "update_run_status", wraps=repository.update_run_status) as update:
                        if boundary == "game":
                            with patch.object(runner, "_play_game", side_effect=error), self.assertRaises(exception):
                                runner.continue_benchmark(self.database, self.run_id)
                        else:
                            with self.assertRaises(exception):
                                runner.continue_benchmark(self.database, self.run_id, **kwargs)
                    update.assert_not_called()
                    row = self.run_row()
                    self.assertEqual(row["run_status"], "RUNNING")
                    self.assertIsNone(row["failure_code"])
                    self.assertIsNone(row["finished_at"])
                    expected_index = 1 if boundary == "game" else 2
                    self.assertEqual(row["processed_games"], expected_index)
                    with patch.object(runner, "generate_board", wraps=generate_board) as generate:
                        runner.continue_benchmark(self.database, self.run_id)
                    self.assertEqual(generate.call_args_list[0].args, (EXPERT_GENERAL_V1, expected_index))

    def test_uncommitted_game_rolls_back_with_progress_and_replays_absolute_index(self):
        for exception in (KeyboardInterrupt, SystemExit, RuntimeError):
            with self.subTest(exception=exception):
                self.prefix(requested=2)
                before = self.snapshot()
                error = exception("before commit")
                statements = []
                closed_states = []
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
                    # Only the post-preflight writer gets fault injection.
                    if "mode=rw" in str(args[0]):
                        kwargs["factory"] = InterruptingConnection
                    connection = connect(*args, **kwargs)
                    connection.set_trace_callback(statements.append)
                    return connection

                with patch.object(repository.sqlite3, "connect", side_effect=interrupting_connect), \
                        self.assertRaises(exception) as raised:
                    runner.continue_benchmark(self.database, self.run_id)
                self.assertIs(raised.exception, error)
                self.assertIn("ROLLBACK", statements)
                self.assertEqual(closed_states, [False])
                if exception is RuntimeError:
                    self.assert_failed("GAME_PERSISTENCE_FAILED", 1)
                else:
                    self.assertEqual(self.snapshot(), before)
                    with patch.object(runner, "generate_board", wraps=generate_board) as generate:
                        runner.continue_benchmark(self.database, self.run_id)
                    generate.assert_called_once_with(EXPERT_GENERAL_V1, 1)
                    self.assertEqual(self.run_row()["run_status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
