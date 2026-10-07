"""Stage-3 execution, V1 persistence, and shared lifecycle contract checks."""

import ast
import inspect
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import Mock, patch

import benchmark_runner as lifecycle
import stage3_benchmark_runner as runner
import stage3_physical
import telemetry_repository as repository
import telemetry_schema as schema
from benchmark_board import (
    EXPERT_GENERAL_V1, BenchmarkBoard, BenchmarkSetSpec,
    calculate_board_fingerprint, generate_board,
)
from board_analyzer import analyze_board
from core_engine import Action, GameStatus, MinesweeperEngine
from simple_algorithm import SimpleMove
from stage3_runner import run_stage3
from stage3_telemetry import trace_to_telemetry
from telemetry_collector import TelemetryCollector
from telemetry_model import InferenceCategory


SMALL_SPEC = BenchmarkSetSpec("TEST_STAGE3_SMALL_V1", 5, 1, 2, 0, 0, "V1", "game_index")
EMPTY_SPEC = BenchmarkSetSpec("TEST_STAGE3_EMPTY_V1", 3, 2, 0, 0, 0, "V1", "game_index")
CHORD_SPEC = BenchmarkSetSpec("TEST_STAGE3_CHORD_V1", 4, 1, 1, 0, 0, "V1", "game_index")
SUFFIX_SPEC = BenchmarkSetSpec("TEST_STAGE3_SUFFIX_V1", 6, 4, 5, 0, 0, "V1", "game_index")
COMMIT = "1234567890abcdef" * 2 + "12345678"
CONFIG = {
    "initial_open": [0, 0], "initial_cursor": [0, 0],
    "algorithm_spec_version": 1,
    "algorithm_spec_sha256": "6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",
    "physical_model_id": "overlap_floor_log2_distance_v1",
    "physical_profile_version": 1,
    "physical_profile_sha256": "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",
    "timing_table_sha256": "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b",
    "timing_unit": "us",
}
METADATA_FIELDS = (
    "inference_category", "selection_candidate_count", "target_mine_probability",
    "minimum_available_mine_probability", "decision_compute_ns",
)


def fixed_board(spec, mines):
    """Answers arrange evaluator/setup fixtures, never decision evidence."""
    return BenchmarkBoard(0, 0, frozenset(mines), calculate_board_fingerprint(
        spec.width, spec.height, spec.num_mines, mines,
    ))


class Stage3BenchmarkTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "stage3.sqlite3"
        self.execution_count = 0
        provenance = patch.object(lifecycle, "_capture_git_provenance", return_value=(COMMIT, False))
        self.provenance = provenance.start()
        self.addCleanup(provenance.stop)

    def execute(self, requested_games=3, **kwargs):
        self.execution_count += 1
        self.database = self.directory / f"stage3-{self.execution_count}.sqlite3"
        kwargs.setdefault("spec", SMALL_SPEC)
        return runner.run_stage3_benchmark(self.database, requested_games, **kwargs)

    def rows(self, table, order):
        with closing(repository.connect_database_readonly(self.database)) as reader:
            return reader.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()

    def run_row(self):
        rows = self.rows("benchmark_runs", "run_id")
        self.assertEqual(len(rows), 1)
        return rows[0]

    def assert_failed(self, code, committed=0):
        row = self.run_row()
        self.assertEqual((row["run_status"], row["failure_code"], row["processed_games"]),
                         ("FAILED", code, committed))
        self.assertIsNotNone(row["finished_at"])
        games = self.rows("games", "game_index")
        self.assertEqual([game["game_index"] for game in games], list(range(committed)))
        self.assertEqual(len(self.rows("action_events", "game_id, action_index")),
                         sum(game["total_actions"] for game in games))


class Stage3BenchmarkExecutionTests(Stage3BenchmarkTestCase):
    def test_real_prefix_identity_events_and_derived_summaries(self):
        run_id = self.execute()
        row = self.run_row()
        self.assertEqual((row["run_id"], row["run_status"], row["processed_games"],
                          row["requested_games"]), (run_id, "COMPLETED", 3, 3))
        self.assertEqual((row["telemetry_schema_version"], row["solver_stage"], row["solver_policy"]),
                         (2, "STAGE_3", "E_FIRST_FIRST_REVEAL_V1"))
        self.assertEqual(json.loads(row["solver_config_snapshot"]), CONFIG)
        self.assertEqual((row["git_commit"], row["git_dirty"]), (COMMIT, 0))
        self.assertEqual((row["first_click_policy"], row["board_generator_version"]),
                         ("FIRST_CLICK_FIXED_0_0", "V1"))
        self.assertIsNotNone(row["environment_snapshot"])
        self.assertIsNone(row["failure_code"])
        games = self.rows("games", "game_index")
        self.assertEqual([game["game_index"] for game in games], [0, 1, 2])
        events = self.rows("action_events", "game_id, action_index")
        for game in games:
            own = [event for event in events if event["game_id"] == game["game_id"]]
            self.assertEqual(game["seed"], game["game_index"])
            self.assertEqual(game["board_fingerprint"],
                             generate_board(SMALL_SPEC, game["game_index"]).board_fingerprint)
            self.assertEqual([event["action_index"] for event in own], list(range(len(own))))
            self.assertEqual((own[0]["action_type"], own[0]["x"], own[0]["y"]),
                             (schema.ACTION_OPEN, 0, 0))
            self.assertTrue(all(own[0][field] is None for field in METADATA_FIELDS))
            self.assertTrue(all(event["inference_category"] is not None for event in own[1:]))
            self.assertTrue(all(event["selection_candidate_count"] is None for event in own))
            self.assertEqual(game["total_actions"], len(own))
            for column, action in (("open_count", schema.ACTION_OPEN),
                                   ("flag_count", schema.ACTION_FLAG), ("chord_count", schema.ACTION_CHORD)):
                self.assertEqual(game[column], sum(event["action_type"] == action for event in own))
            for column, category in (("local_deterministic_count", schema.INFERENCE_LOCAL_DETERMINISTIC),
                                     ("global_certainty_count", schema.INFERENCE_GLOBAL_CERTAINTY),
                                     ("probability_guess_count", schema.INFERENCE_PROBABILITY_GUESS)):
                self.assertEqual(game[column], sum(event["inference_category"] == category for event in own))
            self.assertEqual(sum(game[column] for column in (
                "local_deterministic_count", "global_certainty_count", "probability_guess_count",
            )), len(own) - 1)
            guesses = [event for event in own if event["inference_category"] == schema.INFERENCE_PROBABILITY_GUESS]
            self.assertEqual(game["had_probability_guess"], bool(guesses))
            self.assertEqual(game["first_guess_action_index"], guesses[0]["action_index"] if guesses else None)
            times = [event["decision_compute_ns"] for event in own[1:]]
            self.assertEqual(game["compute_time_total_ns"], sum(times))
            self.assertEqual(game["compute_time_max_ns"], max(times, default=None))
            self.assertEqual(own[-1]["status_after"], schema.STATUS_AFTER_WON
                             if game["result"] == schema.GAME_RESULT_WIN else schema.STATUS_AFTER_LOST)
            for event in guesses:
                self.assertEqual(event["action_type"], schema.ACTION_OPEN)
                target = repository.decode_probability(event["target_mine_probability"])
                minimum = repository.decode_probability(event["minimum_available_mine_probability"])
                self.assertIs(type(target), Fraction)
                self.assertEqual(target, minimum)

    def test_real_official_expert_prefix_and_value_equal_spec(self):
        self.execute(2, spec=replace(EXPERT_GENERAL_V1), official=True)
        row = self.run_row()
        self.assertEqual((row["benchmark_set_id"], row["width"], row["height"], row["num_mines"]),
                         ("EXPERT_GENERAL_V1", 30, 16, 99))
        self.assertEqual((row["requested_games"], row["processed_games"], row["run_status"]),
                         (2, 2, "COMPLETED"))
        self.assertEqual([game["board_fingerprint"] for game in self.rows("games", "game_index")],
                         [generate_board(EXPERT_GENERAL_V1, index).board_fingerprint for index in range(2)])
        self.provenance.assert_called_once_with(Path(runner.__file__).resolve().parent)

    def test_real_chord_nulls_and_certainty_probabilities_survive_sqlite_codec(self):
        board = fixed_board(CHORD_SPEC, {(1, 0)})
        with patch.object(runner, "generate_board", return_value=board):
            self.execute(1, spec=CHORD_SPEC)
        events = self.rows("action_events", "action_index")
        self.assertEqual([event["action_type"] for event in events],
                         [schema.ACTION_OPEN, schema.ACTION_FLAG, schema.ACTION_OPEN, schema.ACTION_CHORD])
        self.assertEqual([event["target_mine_probability"] for event in events], [None, "1/1", "0/1", None])
        self.assertTrue(all(event["minimum_available_mine_probability"] is None for event in events))
        self.assertTrue(all(event["selection_candidate_count"] is None for event in events))
        self.assertEqual(events[-1]["inference_category"], schema.INFERENCE_LOCAL_DETERMINISTIC)
        self.assertIsNotNone(events[-1]["decision_compute_ns"])

    def test_fresh_engines_static_evaluation_and_only_public_traces_enter_adapter(self):
        engines, collectors, results = [], [], []

        def new_engine(*args, **kwargs):
            engine = MinesweeperEngine(*args, **kwargs)
            engines.append(engine)
            return engine

        def new_collector():
            collector = TelemetryCollector()
            collectors.append(collector)
            return collector

        def play(engine, **kwargs):
            # Snapshot/layout access is allowed before this execution boundary only.
            with patch.object(engine, "get_board_snapshot", side_effect=AssertionError("hidden read")):
                result = run_stage3(engine, **kwargs)
            results.append(result)
            return result

        with (
            patch.object(runner, "MinesweeperEngine", side_effect=new_engine),
            patch.object(runner, "TelemetryCollector", side_effect=new_collector),
            patch.object(runner, "run_stage3", side_effect=play) as execute,
            patch.object(runner, "trace_to_telemetry", wraps=trace_to_telemetry) as adapt,
            patch.object(runner, "analyze_board", wraps=analyze_board) as analyze,
            patch.object(repository, "persist_completed_game", wraps=repository.persist_completed_game) as persist,
        ):
            self.execute(2)
        self.assertEqual(len({id(engine) for engine in engines}), 2)
        self.assertEqual(len({id(collector) for collector in collectors}), 2)
        self.assertEqual((execute.call_count, analyze.call_count, persist.call_count), (2, 2, 2))
        traces = [trace for result in results for trace in result.traces]
        self.assertEqual(adapt.call_count, len(traces))
        for call, trace in zip(adapt.call_args_list, traces):
            self.assertEqual(call.args, (trace,))
            self.assertEqual(call.kwargs, {})
        for index, call in enumerate(analyze.call_args_list):
            self.assertEqual(call.args[0].mines, generate_board(SMALL_SPEC, index).mine_positions)
            metrics = analyze_board(call.args[0])
            game = self.rows("games", "game_index")[index]
            self.assertEqual((game["board_3bv"], game["board_ops"]), (metrics.total_3bv, metrics.total_ops))

    def test_unexecuted_plan_suffix_never_enters_persistence(self):
        board = fixed_board(SUFFIX_SPEC, {(1, 2), (2, 1), (4, 0), (4, 1), (4, 2)})
        results = []

        def play(engine, **kwargs):
            result = run_stage3(engine, **kwargs)
            results.append(result)
            return result

        with patch.object(runner, "generate_board", return_value=board), \
                patch.object(runner, "run_stage3", side_effect=play):
            self.execute(1, spec=SUFFIX_SPEC)
        result = results[0]
        self.assertEqual(len(result.traces[4].decision.plan.actions), 3)
        self.assertEqual(result.traces[4].decision.plan.actions[1], SimpleMove(Action.FLAG, 1, 2))
        self.assertEqual(result.traces[5].move, SimpleMove(Action.OPEN, 2, 0))
        events = self.rows("action_events", "action_index")
        self.assertEqual(len(events), len(result.traces))
        action_values = {Action.OPEN: schema.ACTION_OPEN, Action.FLAG: schema.ACTION_FLAG,
                         Action.CHORD: schema.ACTION_CHORD}
        self.assertEqual([(event["action_type"], event["x"], event["y"]) for event in events],
                         [(action_values[trace.move.action], trace.move.x, trace.move.y) for trace in result.traces])

    def test_first_open_win_still_adapts_policy_trace_and_has_no_compute(self):
        with patch.object(runner, "trace_to_telemetry", wraps=trace_to_telemetry) as adapt:
            self.execute(1, spec=EMPTY_SPEC)
        adapt.assert_called_once()
        self.assertIsNone(adapt.call_args.args[0].decision)
        game = self.rows("games", "game_index")[0]
        self.assertEqual((game["total_actions"], game["compute_time_total_ns"], game["compute_time_max_ns"]),
                         (1, 0, None))
        self.assertEqual(game["result"], schema.GAME_RESULT_WIN)

    def test_generated_identity_fingerprint_and_first_click_safety_fail_before_solver(self):
        valid = fixed_board(CHORD_SPEC, {(1, 0)})
        for board in (replace(valid, game_index=1), replace(valid, seed=1),
                      replace(valid, board_fingerprint="0" * 64), fixed_board(CHORD_SPEC, {(0, 0)})):
            with self.subTest(board=board), patch.object(runner, "generate_board", return_value=board), \
                    patch.object(runner, "run_stage3") as play, \
                    self.assertRaises(lifecycle.BenchmarkInvariantError):
                self.execute(1, spec=CHORD_SPEC)
            play.assert_not_called()
            self.assert_failed("GAME_EXECUTION_FAILED")

    def test_observer_result_or_terminal_status_disagreement_fails_closed(self):
        for mutation in (lambda result: replace(result, traces=result.traces[:-1]),
                         lambda result: replace(result, status=GameStatus.PLAYING),
                         lambda result: replace(result, status=GameStatus.LOST)):
            def play(engine, **kwargs):
                return mutation(run_stage3(engine, **kwargs))

            with self.subTest(mutation=mutation), patch.object(runner, "run_stage3", side_effect=play), \
                    self.assertRaises(lifecycle.BenchmarkInvariantError):
                self.execute(1, spec=EMPTY_SPEC)
            self.assert_failed("GAME_EXECUTION_FAILED")

    def test_game_invariants_reject_policy_candidate_and_chord_metadata_corruption(self):
        with patch.object(runner, "generate_board", return_value=fixed_board(CHORD_SPEC, {(1, 0)})):
            record, events = runner._play_game(CHORD_SPEC, 0)
        changes = (
            (),
            (replace(events[0], x=1), *events[1:]),
            (replace(events[0], inference_category=InferenceCategory.LOCAL_DETERMINISTIC,
                     decision_compute_ns=0), *events[1:]),
            (events[0], replace(events[1], inference_category=None, decision_compute_ns=None,
                                target_mine_probability=None), *events[2:]),
            (events[0], replace(events[1], selection_candidate_count=1), *events[2:]),
            (*events[:-1], replace(events[-1], target_mine_probability=Fraction(0, 1))),
        )
        for invalid in changes:
            with self.subTest(events=invalid), self.assertRaises(lifecycle.BenchmarkInvariantError):
                runner._validate_stage3_game(record, invalid)

    def test_game_invariants_reject_nonopen_or_nonminimum_guess(self):
        record, events = runner._play_game(SMALL_SPEC, 1)
        guess = events[-1]
        self.assertEqual(guess.inference_category, InferenceCategory.PROBABILITY_GUESS)
        for invalid in (replace(guess, action_type=Action.FLAG),
                        replace(guess, target_mine_probability=Fraction(1, 1))):
            with self.subTest(guess=invalid), self.assertRaises(lifecycle.BenchmarkInvariantError):
                runner._validate_stage3_game(record, (*events[:-1], invalid))

    def test_game_invariants_compare_actual_action_and_category_counts_to_record(self):
        with patch.object(runner, "generate_board", return_value=fixed_board(CHORD_SPEC, {(1, 0)})):
            record, events = runner._play_game(CHORD_SPEC, 0)
        for invalid in (
            replace(record, open_count=record.open_count - 1, flag_count=record.flag_count + 1),
            replace(record, local_deterministic_count=record.local_deterministic_count - 1,
                    global_certainty_count=record.global_certainty_count + 1),
        ):
            with self.subTest(record=invalid), self.assertRaises(lifecycle.BenchmarkInvariantError):
                runner._validate_stage3_game(invalid, events)

    def test_v1_tables_and_columns_are_unchanged(self):
        self.execute(1, spec=EMPTY_SPEC)
        with closing(repository.connect_database_readonly(self.database)) as reader:
            self.assertEqual(reader.execute("PRAGMA user_version").fetchone()[0], 1)
            schema.validate_existing_schema(reader)
            self.assertEqual({row[0] for row in reader.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'",
            )}, {"benchmark_runs", "games", "action_events"})
            columns = {row[1] for table in ("games", "action_events")
                       for row in reader.execute(f"PRAGMA table_info({table})")}
            self.assertTrue({"modeled_action_us", "game_total_modeled_us", "cursor_before"}.isdisjoint(columns))
        self.assertEqual((schema.TELEMETRY_SCHEMA_VERSION, schema.PHYSICAL_SCHEMA_VERSION), (1, 1))


class Stage3BenchmarkLifecycleTests(Stage3BenchmarkTestCase):
    def test_created_running_transitions_committed_before_execution_and_progress_after_commit(self):
        connect, create_run = repository.connect_database, repository.create_run
        writer, statuses, progress = [], [], []

        def capture(path):
            connection = connect(path)
            writer.append(connection)
            return connection

        def create(connection, **kwargs):
            run_id = create_run(connection, **kwargs)
            statuses.append(repository.fetch_run(connection, run_id)["run_status"])
            self.assertFalse(connection.in_transaction)
            return run_id

        def play(engine, **kwargs):
            self.assertFalse(writer[0].in_transaction)
            self.assertEqual(self.run_row()["run_status"], "RUNNING")
            statuses.append("RUNNING")
            return run_stage3(engine, **kwargs)

        def report(run_id, processed, requested):
            self.assertFalse(writer[0].in_transaction)
            self.assertEqual(self.run_row()["processed_games"], processed)
            self.assertEqual([game["game_index"] for game in self.rows("games", "game_index")],
                             list(range(processed)))
            progress.append((run_id, processed, requested))

        with patch.object(repository, "connect_database", side_effect=capture), \
                patch.object(repository, "create_run", side_effect=create), \
                patch.object(runner, "run_stage3", side_effect=play):
            run_id = self.execute(2, progress=report)
        self.assertEqual(statuses, ["CREATED", "RUNNING", "RUNNING"])
        self.assertEqual(progress, [(run_id, 1, 2), (run_id, 2, 2)])
        self.assertEqual(self.run_row()["run_status"], "COMPLETED")
        with self.assertRaises(sqlite3.ProgrammingError):
            writer[0].execute("SELECT 1")

    def test_stop_before_first_game_aborts_empty_prefix(self):
        with patch.object(runner, "_play_game") as play:
            self.execute(stop_requested=lambda: True)
        play.assert_not_called()
        row = self.run_row()
        self.assertEqual((row["run_status"], row["processed_games"], row["failure_code"]), ("ABORTED", 0, None))
        self.assertIsNotNone(row["finished_at"])
        self.assertEqual(self.rows("games", "game_index"), [])

    def test_stop_during_game_is_only_polled_at_next_boundary(self):
        stop, in_game = False, False
        calls, progress = [], []

        def requested():
            self.assertFalse(in_game)
            calls.append(stop)
            return stop

        def play(engine, **kwargs):
            nonlocal stop, in_game
            stop = in_game = True
            try:
                return run_stage3(engine, **kwargs)
            finally:
                in_game = False

        with patch.object(runner, "run_stage3", side_effect=play) as execute:
            run_id = self.execute(stop_requested=requested, progress=lambda *args: progress.append(args))
        execute.assert_called_once()
        self.assertEqual(calls, [False, True])
        self.assertEqual(progress, [(run_id, 1, 3)])
        self.assertEqual((self.run_row()["run_status"], self.run_row()["processed_games"]), ("ABORTED", 1))

    def test_last_requested_game_completion_wins_over_stop(self):
        stop = Mock(return_value=False)

        def progress(*args):
            stop.return_value = True

        self.execute(1, stop_requested=stop, progress=progress)
        stop.assert_called_once()
        self.assertEqual(self.run_row()["run_status"], "COMPLETED")

    def test_execution_failure_preserves_committed_prefix(self):
        play, error = runner._play_game, RuntimeError("execution failed")

        def fail_second(spec, index):
            if index == 1:
                raise error
            return play(spec, index)

        with patch.object(runner, "_play_game", side_effect=fail_second), self.assertRaises(RuntimeError) as raised:
            self.execute()
        self.assertIs(raised.exception, error)
        self.assert_failed("GAME_EXECUTION_FAILED", 1)

    def test_actual_mid_game_insert_failure_rolls_back_game_events_and_increment_together(self):
        connect, statements = repository.connect_database, []

        def capture(path):
            connection = connect(path)
            connection.execute("""
                CREATE TRIGGER reject_second_game BEFORE INSERT ON action_events
                WHEN NEW.action_index = 1 AND NEW.game_id IN
                    (SELECT game_id FROM games WHERE game_index = 1)
                BEGIN SELECT RAISE(ABORT, 'injected event insert failure'); END
            """)
            connection.set_trace_callback(statements.append)
            return connection

        progress = []
        with patch.object(repository, "connect_database", side_effect=capture), \
                self.assertRaises(sqlite3.IntegrityError):
            self.execute(progress=lambda *args: progress.append(args))
        self.assert_failed("GAME_PERSISTENCE_FAILED", 1)
        self.assertEqual([values[1] for values in progress], [1])
        rollback = statements.index("ROLLBACK")
        failure = next(index for index, sql in enumerate(statements) if "run_status = 'FAILED'" in sql)
        self.assertLess(rollback, failure)
        self.assertIn("BEGIN", statements[rollback + 1:failure])
        self.assertIn("COMMIT", statements[failure + 1:])

    def test_progress_failure_retains_just_committed_game(self):
        error = RuntimeError("progress failed")
        with self.assertRaises(RuntimeError) as raised:
            self.execute(progress=Mock(side_effect=error))
        self.assertIs(raised.exception, error)
        self.assert_failed("PROGRESS_CALLBACK_FAILED", 1)

    def test_stop_callback_failure_is_fatal_before_execution(self):
        error = RuntimeError("stop failed")
        with patch.object(runner, "_play_game") as play, self.assertRaises(RuntimeError) as raised:
            self.execute(stop_requested=Mock(side_effect=error))
        self.assertIs(raised.exception, error)
        play.assert_not_called()
        self.assert_failed("STOP_REQUEST_FAILED")

    def test_completion_and_abort_finalization_failures_preserve_primary_error(self):
        update = repository.update_run_status
        for terminal, committed in (("COMPLETED", 1), ("ABORTED", 0)):
            error = sqlite3.OperationalError("finalization failed")

            def fail(connection, run_id, status, **kwargs):
                if status == terminal:
                    raise error
                return update(connection, run_id, status, **kwargs)

            with self.subTest(status=terminal), patch.object(repository, "update_run_status", side_effect=fail), \
                    self.assertRaises(sqlite3.OperationalError) as raised:
                self.execute(1, stop_requested=lambda: terminal == "ABORTED")
            self.assertIs(raised.exception, error)
            self.assert_failed("RUN_FINALIZATION_FAILED", committed)

    def test_matching_count_with_shifted_prefix_cannot_complete(self):
        persist = repository.persist_completed_game

        def shift(connection, run_id, record, events):
            game_id = persist(connection, run_id, record, events)
            connection.execute("UPDATE games SET game_index = 1 WHERE game_id = ?", (game_id,))
            return game_id

        with patch.object(repository, "persist_completed_game", side_effect=shift), \
                self.assertRaises(lifecycle.BenchmarkInvariantError):
            self.execute(1)
        row = self.run_row()
        self.assertEqual((row["run_status"], row["failure_code"], row["processed_games"]),
                         ("FAILED", "RUN_FINALIZATION_FAILED", 1))

    def test_best_effort_failed_update_preserves_original_and_running(self):
        error, update = RuntimeError("execution failed"), repository.update_run_status

        def fail(connection, run_id, status, **kwargs):
            if status == "FAILED":
                raise sqlite3.OperationalError("failure update failed")
            return update(connection, run_id, status, **kwargs)

        with patch.object(runner, "_play_game", side_effect=error), \
                patch.object(repository, "update_run_status", side_effect=fail), \
                self.assertRaises(RuntimeError) as raised:
            self.execute()
        self.assertIs(raised.exception, error)
        self.assertEqual((self.run_row()["run_status"], self.run_row()["processed_games"]), ("RUNNING", 0))
        self.assertIsNone(self.run_row()["finished_at"])
        self.assertIn("Best-effort FAILED update failed", error.__notes__[0])

    def test_keyboard_interrupt_and_system_exit_leave_running_without_failed_conversion(self):
        for error in (KeyboardInterrupt("interrupted"), SystemExit(7)):
            with self.subTest(error=type(error).__name__), patch.object(runner, "_play_game", side_effect=error), \
                    patch.object(repository, "update_run_status", wraps=repository.update_run_status) as update, \
                    self.assertRaises(type(error)) as raised:
                self.execute()
            self.assertIs(raised.exception, error)
            self.assertEqual([call.args[2] for call in update.call_args_list], ["RUNNING"])
            self.assertEqual((self.run_row()["run_status"], self.run_row()["processed_games"]), ("RUNNING", 0))
            self.assertIsNone(self.run_row()["finished_at"])

    def test_running_transition_failure_leaves_created_and_never_plays(self):
        with patch.object(repository, "update_run_status", side_effect=sqlite3.OperationalError("running failed")), \
                patch.object(runner, "_play_game") as play, self.assertRaises(sqlite3.OperationalError):
            self.execute()
        play.assert_not_called()
        self.assertEqual(self.run_row()["run_status"], "CREATED")


class Stage3BenchmarkAdmissionTests(Stage3BenchmarkTestCase):
    def test_invalid_inputs_rejected_before_provenance_or_database(self):
        cases = [dict(requested_games=value) for value in (0, -1, True, 1.5, "1")]
        cases += [dict(spec=None), dict(official=1), dict(progress=0), dict(stop_requested=False),
                  dict(spec=replace(EMPTY_SPEC, first_click_x=1)),
                  dict(spec=replace(EMPTY_SPEC, width=31)), dict(spec=replace(EMPTY_SPEC, height=17)),
                  dict(spec=replace(EXPERT_GENERAL_V1, width=29))]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), patch.object(repository, "connect_database") as connect, \
                    self.assertRaises((ValueError, TypeError)):
                self.execute(**kwargs)
            connect.assert_not_called()
            self.assertFalse(self.database.exists())
        self.provenance.assert_not_called()

    def test_official_requires_canonical_corpus_new_file_and_module_root(self):
        self.database.write_bytes(b"preserved existing artifact")
        original = self.database.read_bytes()
        for database, kwargs in (
            (self.database, {}),
            (self.directory / "small.sqlite3", {"spec": SMALL_SPEC}),
            (self.directory / "override.sqlite3", {"repository_root": self.directory}),
        ):
            with self.subTest(database=database, kwargs=kwargs), \
                    patch.object(repository, "connect_database") as connect, self.assertRaises(ValueError):
                runner.run_stage3_benchmark(database, 1, official=True, **kwargs)
            connect.assert_not_called()
        self.assertEqual(self.database.read_bytes(), original)
        self.assertFalse((self.directory / "small.sqlite3").exists())
        self.assertFalse((self.directory / "override.sqlite3").exists())

    def test_official_rejects_dirty_tree_but_development_records_it(self):
        self.provenance.return_value = (COMMIT, True)
        with patch.object(repository, "connect_database") as connect, self.assertRaisesRegex(ValueError, "clean"):
            self.execute(1, spec=EXPERT_GENERAL_V1, official=True)
        connect.assert_not_called()
        self.execute(1, spec=EMPTY_SPEC, repository_root=self.directory)
        self.assertEqual(self.run_row()["git_dirty"], 1)
        self.assertEqual(self.provenance.call_args.args, (self.directory,))

    def test_provenance_and_environment_errors_create_no_database(self):
        for name in ("_capture_git_provenance", "_capture_environment"):
            error = RuntimeError("metadata failure")
            with self.subTest(name=name), patch.object(lifecycle, name, side_effect=error), \
                    patch.object(repository, "connect_database") as connect, self.assertRaises(RuntimeError) as raised:
                self.execute()
            self.assertIs(raised.exception, error)
            connect.assert_not_called()
            self.assertFalse(self.database.exists())

    def test_frozen_profile_and_table_authentication_happen_before_writer(self):
        for name in ("PROFILE_SHA256", "TABLE_SHA256"):
            with self.subTest(name=name), patch.object(stage3_physical, name, "0" * 64), \
                    patch.object(repository, "connect_database") as connect, self.assertRaises(ValueError):
                self.execute(1, spec=EMPTY_SPEC)
            connect.assert_not_called()
            self.assertFalse(self.database.exists())

    def test_public_api_exposes_no_identity_or_timing_override(self):
        self.assertEqual(tuple(inspect.signature(runner.run_stage3_benchmark).parameters), (
            "database", "requested_games", "spec", "official", "stop_requested", "progress", "repository_root",
        ))

    def test_lower_layers_do_not_depend_on_stage3_benchmark(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("core_engine.py", "stage3_planner.py", "stage3_runner.py",
                     "stage3_telemetry.py", "telemetry_model.py", "telemetry_repository.py"):
            tree = ast.parse((root / name).read_text(encoding="utf-8"))
            imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
            self.assertNotIn("stage3_benchmark_runner", imports, name)


if __name__ == "__main__":
    unittest.main()
