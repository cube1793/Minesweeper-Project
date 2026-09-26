"""Real benchmark integration plus isolated lifecycle and provenance failures."""

import ast
import json
import os
import platform
import sqlite3
import subprocess
import tempfile
import time
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from unittest.mock import Mock, patch

import benchmark_runner as runner
import telemetry_repository as repository
import telemetry_schema as schema
from benchmark_board import BenchmarkSetSpec, calculate_board_fingerprint, generate_board
from board_analyzer import analyze_board
from core_engine import Action, GameStatus, MinesweeperEngine
from simple_runner import StopReason, run_simple
from simple_telemetry import decision_to_telemetry
from telemetry_collector import TelemetryCollector


SMALL_SPEC = BenchmarkSetSpec("TEST_SMALL_V1", 5, 1, 2, 0, 0, "V1", "game_index")
EMPTY_SPEC = BenchmarkSetSpec("TEST_EMPTY_V1", 3, 2, 0, 0, 0, "V1", "game_index")
COMMIT = "1234567890abcdef" * 2 + "12345678"


class BenchmarkTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "benchmark.sqlite3"
        self.execution_count = 0

    def execute(self, requested_games=3, **kwargs):
        self.execution_count += 1
        self.database = self.directory / f"benchmark-{self.execution_count}.sqlite3"
        kwargs.setdefault("spec", SMALL_SPEC)
        return runner.run_benchmark(self.database, requested_games, **kwargs)

    def rows(self, table, order_by):
        with closing(repository.connect_database(self.database)) as connection:
            return connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()

    def run_row(self):
        rows = self.rows("benchmark_runs", "run_id")
        self.assertEqual(len(rows), 1)
        return rows[0]

    def assert_failed(self, code, committed=0):
        row = self.run_row()
        self.assertEqual(row["run_status"], schema.RUN_STATUS_FAILED)
        self.assertEqual(row["failure_code"], code)
        self.assertEqual(row["processed_games"], committed)
        self.assertIsNotNone(row["finished_at"])
        games = self.rows("games", "game_index")
        self.assertEqual([game["game_index"] for game in games], list(range(committed)))
        self.assertEqual(len(self.rows("action_events", "game_id, action_index")),
                         sum(game["total_actions"] for game in games))


class BenchmarkRunnerTests(BenchmarkTestCase):
    def setUp(self):
        super().setUp()
        # General execution tests do not depend on the developer working tree.
        provenance = patch.object(runner, "_capture_git_provenance", return_value=(COMMIT, False))
        self.provenance = provenance.start()
        self.addCleanup(provenance.stop)

    def test_real_generated_prefix_persists_complete_games_and_policy_events(self):
        run_id = self.execute()
        row = self.run_row()
        self.assertEqual(row["run_id"], run_id)
        self.assertEqual(row["run_status"], schema.RUN_STATUS_COMPLETED)
        self.assertEqual((row["requested_games"], row["processed_games"]), (3, 3))
        self.assertEqual(row["benchmark_set_id"], SMALL_SPEC.benchmark_set_id)
        self.assertEqual(row["board_generator_version"], "V1")
        self.assertEqual(row["first_click_policy"], schema.FIRST_CLICK_FIXED_0_0)
        self.assertEqual((row["width"], row["height"], row["num_mines"]), (5, 1, 2))
        self.assertEqual(json.loads(row["solver_config_snapshot"]),
                         {"accept_guesses": True, "initial_open": [0, 0]})
        self.assertEqual(row["git_commit"], COMMIT)
        self.assertEqual(row["git_dirty"], 0)
        self.assertIsNone(row["app_version"])
        self.assertIsNone(row["failure_code"])
        timestamps = [datetime.fromisoformat(row[key])
                      for key in ("created_at", "started_at", "finished_at")]
        self.assertTrue(all(stamp.utcoffset() == timedelta(0) for stamp in timestamps))
        self.assertEqual(timestamps, sorted(timestamps))

        games = self.rows("games", "game_index")
        self.assertEqual([game["game_index"] for game in games], [0, 1, 2])
        events = self.rows("action_events", "game_id, action_index")
        for game in games:
            board = generate_board(SMALL_SPEC, game["game_index"])
            self.assertEqual(game["seed"], game["game_index"])
            self.assertEqual(game["board_fingerprint"], board.board_fingerprint)
            own = [event for event in events if event["game_id"] == game["game_id"]]
            self.assertEqual([event["action_index"] for event in own],
                             list(range(game["total_actions"])))
            first = own[0]
            self.assertEqual((first["action_type"], first["x"], first["y"]),
                             (schema.ACTION_OPEN, 0, 0))
            for key in ("inference_category", "selection_candidate_count",
                        "target_mine_probability", "minimum_available_mine_probability",
                        "decision_compute_ns"):
                self.assertIsNone(first[key], key)
            self.assertTrue(all(event["inference_category"] is not None for event in own[1:]))
            self.assertEqual(game["local_deterministic_count"] + game["global_certainty_count"]
                             + game["probability_guess_count"], game["total_actions"] - 1)

    def test_real_probability_guess_mine_hit_is_a_committed_loss(self):
        self.execute(2)
        lost = self.rows("games", "game_index")[1]
        self.assertEqual(lost["result"], schema.GAME_RESULT_LOSS)
        self.assertEqual(lost["probability_guess_count"], 1)
        self.assertEqual(lost["first_guess_action_index"], 2)
        guess = [event for event in self.rows("action_events", "game_id, action_index")
                 if event["game_id"] == lost["game_id"]][-1]
        self.assertEqual(guess["inference_category"], schema.INFERENCE_PROBABILITY_GUESS)
        self.assertEqual((guess["action_type"], guess["x"], guess["y"]),
                         (schema.ACTION_OPEN, 3, 0))
        self.assertEqual(guess["status_after"], schema.STATUS_AFTER_LOST)
        self.assertEqual(guess["selection_candidate_count"], 2)
        self.assertEqual(guess["target_mine_probability"], "1/2")
        self.assertEqual(guess["minimum_available_mine_probability"], "1/2")
        self.assertEqual(repository.decode_probability(guess["target_mine_probability"]),
                         Fraction(1, 2))

    def test_fresh_engines_installed_identity_and_existing_boundaries_are_used(self):
        engines, collectors, fingerprints, decisions = [], [], [], []

        def engine_factory(*args, **kwargs):
            engine = MinesweeperEngine(*args, **kwargs)
            engines.append(engine)
            return engine

        def collector_factory():
            collector = TelemetryCollector()
            collectors.append(collector)
            return collector

        def execute_game(engine, **kwargs):
            self.assertTrue(kwargs["accept_guesses"])
            self.assertEqual(kwargs["initial_open"], (0, 0))
            snapshot = engine.get_board_snapshot()
            self.assertTrue(snapshot.mines_placed)
            fingerprints.append(calculate_board_fingerprint(
                snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines))
            observer = kwargs["observer"]

            def observe(trace):
                if trace.decision is not None:
                    decisions.append(trace.decision)
                observer(trace)

            return run_simple(engine, **{**kwargs, "observer": observe})

        with (
            patch.object(runner, "MinesweeperEngine", side_effect=engine_factory) as engine_mock,
            patch.object(runner, "TelemetryCollector", side_effect=collector_factory),
            patch.object(runner, "generate_board", wraps=generate_board) as generate,
            patch.object(runner, "run_simple", side_effect=execute_game) as execute,
            patch.object(runner, "decision_to_telemetry", wraps=decision_to_telemetry) as adapt,
            patch.object(runner, "analyze_board", wraps=analyze_board) as analyze,
            patch.object(repository, "persist_completed_game", wraps=repository.persist_completed_game) as persist,
        ):
            self.execute()
        self.assertEqual(len({id(engine) for engine in engines}), 3)
        self.assertEqual(len({id(collector) for collector in collectors}), 3)
        self.assertEqual([call.args for call in generate.call_args_list],
                         [(SMALL_SPEC, index) for index in range(3)])
        self.assertEqual((engine_mock.call_count, execute.call_count, analyze.call_count,
                          persist.call_count), (3, 3, 3, 3))
        self.assertEqual(adapt.call_count, len(decisions))
        for call, decision in zip(adapt.call_args_list, decisions):
            self.assertIs(call.args[0], decision)
        self.assertEqual(fingerprints,
                         [game["board_fingerprint"] for game in self.rows("games", "game_index")])
        for index, snapshot_call in enumerate(analyze.call_args_list):
            self.assertEqual(snapshot_call.args[0].mines, generate_board(SMALL_SPEC, index).mine_positions)
            metrics = analyze_board(snapshot_call.args[0])
            game = self.rows("games", "game_index")[index]
            self.assertEqual((game["board_3bv"], game["board_ops"]),
                             (metrics.total_3bv, metrics.total_ops))

    def test_nonorigin_first_click_and_dimensions_come_from_spec(self):
        spec = replace(EMPTY_SPEC, first_click_x=2, first_click_y=1)
        self.execute(1, spec=spec)
        row = self.run_row()
        self.assertEqual(row["first_click_policy"], "FIRST_CLICK_FIXED_2_1")
        self.assertEqual(json.loads(row["solver_config_snapshot"])["initial_open"], [2, 1])
        game = self.rows("games", "game_index")[0]
        self.assertEqual((game["first_click_x"], game["first_click_y"]), (2, 1))
        first = self.rows("action_events", "game_id, action_index")[0]
        self.assertEqual((first["action_type"], first["x"], first["y"]),
                         (schema.ACTION_OPEN, 2, 1))

    def test_zero_decision_initial_win_has_no_adapter_or_compute_metadata(self):
        with patch.object(runner, "decision_to_telemetry", wraps=decision_to_telemetry) as adapt:
            self.execute(1, spec=EMPTY_SPEC)
        adapt.assert_not_called()
        game = self.rows("games", "game_index")[0]
        self.assertEqual((game["total_actions"], game["compute_time_total_ns"]), (1, 0))
        self.assertIsNone(game["compute_time_max_ns"])
        self.assertEqual(game["result"], schema.GAME_RESULT_WIN)

    def test_lifecycle_creation_and_running_are_committed_before_play(self):
        create_run = repository.create_run
        seen = []

        def create(connection, **kwargs):
            run_id = create_run(connection, **kwargs)
            row = repository.fetch_run(connection, run_id)
            seen.append(row["run_status"])
            self.assertEqual(row["processed_games"], 0)
            self.assertIsNone(row["started_at"])
            self.assertIsNone(row["finished_at"])
            self.assertFalse(connection.in_transaction)
            return run_id

        def execute(engine, **kwargs):
            row = self.run_row()
            seen.append(row["run_status"])
            self.assertIsNotNone(row["started_at"])
            self.assertIsNone(row["finished_at"])
            return run_simple(engine, **kwargs)

        with patch.object(repository, "create_run", side_effect=create), \
                patch.object(runner, "run_simple", side_effect=execute):
            self.execute(1)
        seen.append(self.run_row()["run_status"])
        self.assertEqual(seen, ["CREATED", "RUNNING", "COMPLETED"])

    def test_solver_has_no_transaction_and_progress_sees_commits_from_another_connection(self):
        connect = repository.connect_database
        connections, progress = [], []

        def capture(path):
            connection = connect(path)
            connections.append(connection)
            return connection

        def execute(engine, **kwargs):
            self.assertFalse(connections[0].in_transaction)
            self.assertIsNone(connections[0].isolation_level)
            for pragma, value in (("foreign_keys", 1), ("journal_mode", "wal"), ("synchronous", 2)):
                self.assertEqual(connections[0].execute("PRAGMA " + pragma).fetchone()[0], value)
            return run_simple(engine, **kwargs)

        def report(run_id, processed, requested):
            self.assertFalse(connections[0].in_transaction)
            with closing(connect(self.database)) as reader:
                row = repository.fetch_run(reader, run_id)
                indices = repository.fetch_game_indices(reader, run_id)
            self.assertEqual(row["processed_games"], processed)
            self.assertEqual(indices, tuple(range(processed)))
            self.assertEqual(row["run_status"], schema.RUN_STATUS_RUNNING)
            progress.append((run_id, processed, requested))

        with patch.object(repository, "connect_database", side_effect=capture), \
                patch.object(runner, "run_simple", side_effect=execute):
            run_id = self.execute(progress=report)
        self.assertEqual(progress, [(run_id, 1, 3), (run_id, 2, 3), (run_id, 3, 3)])
        self.assertEqual(len(connections), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connections[0].execute("SELECT 1")

    def test_stop_during_game_finishes_and_commits_before_aborting(self):
        stop = False
        in_game = False
        calls, progress = [], []

        def requested():
            self.assertFalse(in_game)
            calls.append(stop)
            return stop

        def execute(engine, **kwargs):
            nonlocal stop, in_game
            stop = in_game = True
            try:
                return run_simple(engine, **kwargs)
            finally:
                in_game = False

        with patch.object(runner, "run_simple", side_effect=execute) as execute_mock:
            run_id = self.execute(stop_requested=requested,
                                  progress=lambda *values: progress.append(values))
        self.assertEqual(execute_mock.call_count, 1)
        self.assertTrue(calls[-1])
        self.assertEqual(progress, [(run_id, 1, 3)])
        row = self.run_row()
        self.assertEqual((row["run_status"], row["processed_games"]), ("ABORTED", 1))
        self.assertIsNone(row["failure_code"])
        self.assertEqual(len(self.rows("games", "game_index")), 1)

    def test_stop_after_final_commit_completes_without_another_stop_check(self):
        stop = False

        def requested():
            if stop:
                raise AssertionError("The complete prefix must win over a stop request.")
            return False

        def report(*args):
            nonlocal stop
            stop = True

        self.execute(1, stop_requested=requested, progress=report)
        self.assertTrue(stop)
        self.assertEqual(self.run_row()["run_status"], "COMPLETED")

    def test_stop_before_first_game_aborts_with_empty_prefix(self):
        with patch.object(runner, "generate_board", wraps=generate_board) as generate:
            self.execute(stop_requested=lambda: True)
        generate.assert_not_called()
        self.assertEqual(self.run_row()["run_status"], "ABORTED")
        self.assertEqual(self.run_row()["processed_games"], 0)
        self.assertEqual(self.rows("games", "game_index"), [])

    def test_installed_board_mismatch_is_rejected_before_solver_and_persistence(self):
        class WrongLayoutEngine(MinesweeperEngine):
            def reset_with_mines(self, width, height, num_mines, mine_positions):
                return super().reset_with_mines(width, height, num_mines, {(1, 0), (3, 0)})

        with (
            patch.object(runner, "MinesweeperEngine", WrongLayoutEngine),
            patch.object(runner, "run_simple", wraps=run_simple) as execute,
            patch.object(repository, "persist_completed_game", wraps=repository.persist_completed_game) as persist,
            self.assertRaises(runner.BenchmarkInvariantError),
        ):
            self.execute()
        execute.assert_not_called()
        persist.assert_not_called()
        self.assert_failed("GAME_EXECUTION_FAILED")

    def test_unplaced_or_wrong_dimension_snapshot_is_rejected_before_play(self):
        for changes in ({"mines_placed": False}, {"width": 6}, {"num_mines": 1}):
            with self.subTest(changes=changes):
                class WrongSnapshotEngine(MinesweeperEngine):
                    ready = False

                    def reset_with_mines(inner, *args):
                        observation = super().reset_with_mines(*args)
                        inner.ready = True
                        return observation

                    def get_board_snapshot(inner):
                        snapshot = super().get_board_snapshot()
                        return replace(snapshot, **changes) if inner.ready else snapshot

                with patch.object(runner, "MinesweeperEngine", WrongSnapshotEngine), \
                        patch.object(runner, "run_simple") as execute, \
                        self.assertRaises(runner.BenchmarkInvariantError):
                    self.execute()
                execute.assert_not_called()
                self.assert_failed("GAME_EXECUTION_FAILED")

    def test_policy_trace_cannot_carry_decision_compute_time(self):
        def execute(engine, **kwargs):
            observer = kwargs["observer"]

            def observe(trace):
                if trace.decision is None:
                    trace = replace(trace, decision_compute_ns=1)
                observer(trace)

            return run_simple(engine, **{**kwargs, "observer": observe})

        with patch.object(runner, "run_simple", side_effect=execute), \
                self.assertRaises(runner.BenchmarkInvariantError):
            self.execute()
        self.assert_failed("GAME_EXECUTION_FAILED")

    def test_unexpected_guess_required_fails_and_does_not_start_another_game(self):
        def stop_at_guess(engine, **kwargs):
            return run_simple(engine, **{**kwargs, "accept_guesses": False})

        with patch.object(runner, "run_simple", side_effect=stop_at_guess) as execute, \
                self.assertRaises(runner.BenchmarkInvariantError):
            self.execute()
        execute.assert_called_once()
        self.assert_failed("GAME_EXECUTION_FAILED")

    def test_result_stop_reason_status_and_terminal_trace_must_agree(self):
        for changes in ({"stop_reason": StopReason.LOST}, {"status": GameStatus.LOST},
                        {"status": GameStatus.PLAYING}):
            with self.subTest(changes=changes):
                def execute(engine, **kwargs):
                    return replace(run_simple(engine, **kwargs), **changes)

                with patch.object(runner, "run_simple", side_effect=execute), \
                        self.assertRaises(runner.BenchmarkInvariantError):
                    self.execute(1)
                self.assert_failed("GAME_EXECUTION_FAILED")

    def test_initial_event_and_stage_two_analyzed_count_are_integration_invariants(self):
        # These modified collectors still produce structurally valid generic facts.
        for mode in ("coordinate", "initial_flag", "extra_policy_action"):
            class AlteredCollector(TelemetryCollector):
                def record_action(inner, **kwargs):
                    if not inner.events:
                        if mode == "coordinate":
                            kwargs["x"] = 1
                        elif mode == "initial_flag":
                            kwargs.update(action_type=Action.FLAG, explicit_flag_delta=1,
                                          safe_cells_opened_delta=0)
                    elif mode == "extra_policy_action":
                        for name in ("inference_category", "selection_candidate_count",
                                     "target_mine_probability", "minimum_available_mine_probability",
                                     "decision_compute_ns"):
                            kwargs[name] = None
                    return super().record_action(**kwargs)

            with self.subTest(mode=mode), patch.object(runner, "TelemetryCollector", AlteredCollector), \
                    self.assertRaises(runner.BenchmarkInvariantError):
                self.execute()
            self.assert_failed("GAME_EXECUTION_FAILED")

    def test_execution_failures_propagate_original_exception_without_persisting_or_retry(self):
        boundaries = ((runner, "generate_board"), (runner, "MinesweeperEngine"),
                      (MinesweeperEngine, "reset_with_mines"), (runner, "analyze_board"),
                      (runner, "run_simple"), (runner, "decision_to_telemetry"),
                      (TelemetryCollector, "record_action"), (TelemetryCollector, "finalize"))
        for target, name in boundaries:
            with self.subTest(boundary=name):
                error = RuntimeError("Primary execution failure")
                with patch.object(target, name, side_effect=error) as failing, \
                        patch.object(repository, "persist_completed_game") as persist, \
                        self.assertRaises(RuntimeError) as raised:
                    self.execute()
                self.assertIs(raised.exception, error)
                failing.assert_called_once()
                persist.assert_not_called()
                self.assert_failed("GAME_EXECUTION_FAILED")

    def test_failure_in_second_game_keeps_first_commit_and_stops_prefix(self):
        error = RuntimeError("Second game failed")

        def generate(spec, index):
            if index == 1:
                raise error
            return generate_board(spec, index)

        progress = []
        with patch.object(runner, "generate_board", side_effect=generate) as generate_mock, \
                self.assertRaises(RuntimeError) as raised:
            self.execute(progress=lambda *values: progress.append(values))
        self.assertIs(raised.exception, error)
        self.assertEqual(generate_mock.call_count, 2)
        self.assertEqual([values[1] for values in progress], [1])
        self.assert_failed("GAME_EXECUTION_FAILED", 1)

    def test_persistence_failure_rolls_back_game_events_and_progress_then_fails_separately(self):
        connect, update = repository.connect_database, repository.update_run_status
        sql, statuses, errors, progress = [], [], [], []

        def capture(path):
            connection = connect(path)
            connection.execute("""
                CREATE TRIGGER reject_second_progress BEFORE UPDATE OF processed_games ON benchmark_runs
                WHEN NEW.processed_games = 2
                BEGIN SELECT RAISE(ABORT, 'injected progress write failure'); END
            """)
            connection.set_trace_callback(sql.append)
            return connection

        def update_status(connection, run_id, status, **kwargs):
            self.assertFalse(connection.in_transaction)
            statuses.append(status)
            return update(connection, run_id, status, **kwargs)

        persist = repository.persist_completed_game

        def capture_error(*args, **kwargs):
            try:
                return persist(*args, **kwargs)
            except Exception as error:
                errors.append(error)
                raise

        with (
            patch.object(repository, "connect_database", side_effect=capture),
            patch.object(repository, "update_run_status", side_effect=update_status),
            patch.object(repository, "persist_completed_game", side_effect=capture_error),
            patch.object(runner, "generate_board", wraps=generate_board) as generate,
            self.assertRaises(sqlite3.IntegrityError) as raised,
        ):
            self.execute(progress=lambda *values: progress.append(values))
        self.assertIs(raised.exception, errors[0])
        self.assertEqual(generate.call_count, 2)
        self.assertEqual([values[1] for values in progress], [1])
        self.assertEqual(statuses, ["RUNNING", "FAILED"])
        rollback = next(index for index, statement in enumerate(sql) if statement == "ROLLBACK")
        failure_update = next(index for index, statement in enumerate(sql)
                              if "run_status = 'FAILED'" in statement)
        self.assertLess(rollback, failure_update)
        self.assertIn("BEGIN", sql[rollback + 1:failure_update])
        self.assertIn("COMMIT", sql[failure_update + 1:])
        self.assert_failed("GAME_PERSISTENCE_FAILED", 1)

    def test_failed_update_failure_preserves_original_and_leaves_running(self):
        primary = RuntimeError("Primary solver failure")
        cleanup = sqlite3.OperationalError("Cannot update failed status")
        update = repository.update_run_status

        def update_status(connection, run_id, status, **kwargs):
            if status == schema.RUN_STATUS_FAILED:
                raise cleanup
            return update(connection, run_id, status, **kwargs)

        with patch.object(runner, "run_simple", side_effect=primary) as execute, \
                patch.object(repository, "update_run_status", side_effect=update_status), \
                self.assertRaises(RuntimeError) as raised:
            self.execute()
        self.assertIs(raised.exception, primary)
        execute.assert_called_once()
        self.assertEqual(self.run_row()["run_status"], "RUNNING")
        self.assertEqual(self.run_row()["processed_games"], 0)
        self.assertEqual(self.rows("games", "game_index"), [])

    def test_progress_failure_keeps_just_committed_game_and_is_fatal(self):
        error = RuntimeError("Progress consumer failed")
        with patch.object(runner, "generate_board", wraps=generate_board) as generate, \
                self.assertRaises(RuntimeError) as raised:
            self.execute(progress=Mock(side_effect=error))
        self.assertIs(raised.exception, error)
        generate.assert_called_once()
        self.assert_failed("PROGRESS_CALLBACK_FAILED", 1)

    def test_stop_callback_failure_is_visible_and_marks_failed(self):
        error = RuntimeError("Stop consumer failed")
        with patch.object(runner, "generate_board", wraps=generate_board) as generate, \
                self.assertRaises(RuntimeError) as raised:
            self.execute(stop_requested=Mock(side_effect=error))
        self.assertIs(raised.exception, error)
        generate.assert_not_called()
        self.assert_failed("STOP_REQUEST_FAILED")

    def test_malformed_persisted_prefix_cannot_complete_even_with_matching_processed_count(self):
        persist = repository.persist_completed_game
        for corruption in ("shifted", "missing", "extra"):
            def corrupt(connection, run_id, record, events):
                game_id = persist(connection, run_id, record, events)
                if record.game_index == 1:
                    if corruption == "shifted":
                        connection.execute("UPDATE games SET game_index = 2 WHERE game_id = ?", (game_id,))
                    elif corruption == "missing":
                        connection.execute("DELETE FROM games WHERE game_id = ?", (game_id,))
                    else:
                        connection.execute("UPDATE benchmark_runs SET processed_games = 1 WHERE run_id = ?", (run_id,))
                        persist(connection, run_id, replace(record, game_index=2, seed=2), events)
                return game_id

            with self.subTest(corruption=corruption), \
                    patch.object(repository, "persist_completed_game", side_effect=corrupt), \
                    self.assertRaises(runner.BenchmarkInvariantError):
                self.execute(2, official=True)
            row = self.run_row()
            self.assertEqual(row["processed_games"], row["requested_games"])
            self.assertEqual(row["git_dirty"], 0)
            self.assertEqual(row["run_status"], "FAILED")
            self.assertEqual(row["failure_code"], "RUN_FINALIZATION_FAILED")

    def test_completion_status_write_failure_is_fatal_and_original_is_preserved(self):
        error = sqlite3.OperationalError("Completion update failed")
        update = repository.update_run_status

        def fail_completion(connection, run_id, status, **kwargs):
            if status == "COMPLETED":
                raise error
            return update(connection, run_id, status, **kwargs)

        with patch.object(repository, "update_run_status", side_effect=fail_completion), \
                self.assertRaises(sqlite3.OperationalError) as raised:
            self.execute(1)
        self.assertIs(raised.exception, error)
        self.assert_failed("RUN_FINALIZATION_FAILED", 1)

    def test_abort_status_write_failure_is_fatal_and_original_is_preserved(self):
        error = sqlite3.OperationalError("Abort update failed")
        update = repository.update_run_status

        def fail_abort(connection, run_id, status, **kwargs):
            if status == "ABORTED":
                raise error
            return update(connection, run_id, status, **kwargs)

        with patch.object(repository, "update_run_status", side_effect=fail_abort), \
                self.assertRaises(sqlite3.OperationalError) as raised:
            self.execute(stop_requested=lambda: True)
        self.assertIs(raised.exception, error)
        self.assert_failed("RUN_FINALIZATION_FAILED")

    def test_keyboard_interrupt_and_system_exit_propagate_without_normal_failed_lifecycle(self):
        for error in (KeyboardInterrupt("interrupt"), SystemExit(7)):
            with self.subTest(error=type(error).__name__), \
                    patch.object(runner, "run_simple", side_effect=error) as execute, \
                    patch.object(repository, "update_run_status", wraps=repository.update_run_status) as update, \
                    self.assertRaises(type(error)) as raised:
                self.execute()
            self.assertIs(raised.exception, error)
            execute.assert_called_once()
            self.assertEqual([call.args[2] for call in update.call_args_list], ["RUNNING"])
            self.assertEqual(self.run_row()["run_status"], "RUNNING")
            self.assertEqual(self.rows("games", "game_index"), [])

    def test_running_transition_failure_leaves_created_and_does_not_execute(self):
        error = sqlite3.OperationalError("Cannot enter running")
        with patch.object(repository, "update_run_status", side_effect=error) as update, \
                patch.object(runner, "generate_board") as generate, \
                self.assertRaises(sqlite3.OperationalError) as raised:
            self.execute()
        self.assertIs(raised.exception, error)
        update.assert_called_once()
        generate.assert_not_called()
        self.assertEqual(self.run_row()["run_status"], "CREATED")

    def test_invalid_caller_configuration_is_rejected_before_provenance_or_database(self):
        cases = [dict(requested_games=value) for value in (0, -1, True, 1.5, "1")]
        cases += [dict(spec=None), dict(official=1), dict(stop_requested=False), dict(progress=0)]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), patch.object(repository, "connect_database") as connect, \
                    self.assertRaises((ValueError, TypeError)):
                self.execute(**kwargs)
            connect.assert_not_called()
        self.provenance.assert_not_called()

    def test_provenance_or_environment_failure_creates_no_database_lifecycle(self):
        for name in ("_capture_git_provenance", "_capture_environment"):
            error = RuntimeError("Cannot capture run metadata")
            with self.subTest(boundary=name), patch.object(runner, name, side_effect=error), \
                    patch.object(repository, "connect_database") as connect, \
                    self.assertRaises(RuntimeError) as raised:
                self.execute()
            self.assertIs(raised.exception, error)
            connect.assert_not_called()

    def test_environment_snapshot_persists_real_standard_library_facts(self):
        self.execute(1, spec=EMPTY_SPEC)
        environment = json.loads(self.run_row()["environment_snapshot"])
        self.assertEqual(environment["python_implementation"], platform.python_implementation())
        self.assertEqual(environment["python_version"], platform.python_version())
        self.assertEqual(environment["platform"], platform.platform())
        self.assertEqual(environment["machine"], platform.machine())
        self.assertEqual(environment["cpu_count"], os.cpu_count())
        self.assertEqual(environment["cpu_identifier"], platform.processor() or None)
        self.assertEqual(environment["sqlite_version"], sqlite3.sqlite_version)
        clock = time.get_clock_info("perf_counter")
        self.assertEqual(environment["perf_counter"], {
            "implementation": clock.implementation, "monotonic": clock.monotonic,
            "adjustable": clock.adjustable, "resolution": clock.resolution,
        })


class BenchmarkProvenanceTests(BenchmarkTestCase):
    def setUp(self):
        super().setUp()
        # Git config and inherited GIT_* variables must not change fixture semantics.
        environment = {key: value for key, value in os.environ.items()
                       if not key.upper().startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_ATTR_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
        patcher = patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.git_root = self.directory / "source"
        self.git_root.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.name", "Benchmark Test")
        self.git("config", "user.email", "benchmark-test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        (self.git_root / "tracked.txt").write_text("original\n", encoding="utf-8")
        (self.git_root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        self.git("add", "tracked.txt", ".gitignore")
        self.git("commit", "--quiet", "-m", "Initialize test fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.git_root), *arguments],
                              check=True, capture_output=True, text=True).stdout

    def test_clean_official_run_records_checked_out_commit(self):
        self.assertEqual(runner._capture_git_provenance(self.git_root), (self.commit, False))
        self.execute(1, spec=EMPTY_SPEC, official=True, repository_root=self.git_root)
        row = self.run_row()
        self.assertEqual((row["run_status"], row["git_commit"], row["git_dirty"]),
                         ("COMPLETED", self.commit, 0))

    def test_staged_modification_is_dirty(self):
        (self.git_root / "tracked.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.assertEqual(runner._capture_git_provenance(self.git_root), (self.commit, True))
        self.assert_official_rejected_before_lifecycle()

    def test_unstaged_modification_is_dirty(self):
        (self.git_root / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
        self.assertEqual(runner._capture_git_provenance(self.git_root), (self.commit, True))
        self.assert_official_rejected_before_lifecycle()

    def test_nonignored_untracked_outputs_are_dirty_without_extension_special_cases(self):
        for name in ("notes.md", "benchmark.sqlite3", "run.log", "nested/settings.local.json"):
            with self.subTest(name=name):
                path = self.git_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("untracked\n", encoding="utf-8")
                try:
                    self.assertEqual(runner._capture_git_provenance(self.git_root), (self.commit, True))
                    self.assert_official_rejected_before_lifecycle()
                finally:
                    path.unlink()

    def test_ignored_untracked_output_keeps_official_tree_clean(self):
        ignored = self.git_root / "ignored"
        ignored.mkdir()
        (ignored / "benchmark.sqlite3").write_text("ignored output", encoding="utf-8")
        self.assertEqual(runner._capture_git_provenance(self.git_root), (self.commit, False))
        self.execute(1, spec=EMPTY_SPEC, official=True, repository_root=self.git_root)
        self.assertEqual(self.run_row()["git_dirty"], 0)

    def assert_official_rejected_before_lifecycle(self):
        with closing(repository.connect_database(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 0)
        with patch.object(repository, "connect_database", wraps=repository.connect_database) as connect, \
                patch.object(repository, "create_run", wraps=repository.create_run) as create, \
                self.assertRaises((ValueError, RuntimeError)):
            runner.run_benchmark(self.database, 1, spec=EMPTY_SPEC,
                                 official=True, repository_root=self.git_root)
        create.assert_not_called()
        connect.assert_not_called()
        with closing(repository.connect_database(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0], 0)

    def test_development_dirty_run_is_allowed_and_persists_dirty_fact(self):
        (self.git_root / "tracked.txt").write_text("development changes\n", encoding="utf-8")
        self.execute(1, spec=EMPTY_SPEC, official=False, repository_root=self.git_root)
        row = self.run_row()
        self.assertEqual((row["run_status"], row["git_dirty"]), ("COMPLETED", 1))
        self.assertEqual(row["git_commit"], self.commit)

    def test_provenance_is_captured_once_before_games_even_when_tree_changes(self):
        capture = runner._capture_git_provenance

        def report(run_id, processed, requested):
            (self.git_root / "new-file.txt").write_text("changed after capture\n", encoding="utf-8")

        with patch.object(runner, "_capture_git_provenance", wraps=capture) as provenance:
            self.execute(2, spec=EMPTY_SPEC, official=True,
                         repository_root=self.git_root, progress=report)
        provenance.assert_called_once()
        self.assertEqual(self.run_row()["git_dirty"], 0)
        self.assertEqual(capture(self.git_root), (self.commit, True))


class BenchmarkDependencyTests(unittest.TestCase):
    def test_lower_layers_do_not_import_benchmark_runner(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("core_engine.py", "simple_runner.py", "telemetry_model.py", "telemetry_repository.py"):
            tree = ast.parse((root / name).read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
            self.assertNotIn("benchmark_runner", imports, name)


if __name__ == "__main__":
    unittest.main()
