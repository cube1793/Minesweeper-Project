"""Frozen-model authentication and complete-input reconstruction boundaries."""

import ast
import hashlib
import inspect
import json
import sqlite3
import unittest
from dataclasses import FrozenInstanceError, replace
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import benchmark_modeled_time as modeled
import benchmark_runner
import benchmark_statistics
import stage3_benchmark_runner
import stage3_physical as physical
import telemetry_repository as repository
import telemetry_schema as schema
from benchmark_board import EXPERT_GENERAL_V1
from core_engine import Action, GameStatus, MinesweeperEngine
from stage3_runner import run_stage3
from telemetry_collector import TelemetryCollector
from tests.test_telemetry_repository import STARTED_AT, completed_game, run_inputs


def memory_database():
    connection = sqlite3.connect(":memory:", isolation_level=None)
    schema.initialize_schema(connection)
    return connection


def install_run(connection, *, stage3=False, record=None, events=None):
    identity = (stage3_benchmark_runner if stage3 else benchmark_runner)._benchmark_identity(EXPERT_GENERAL_V1)
    run_id = repository.create_run(connection, **run_inputs(**identity, requested_games=1))
    repository.update_run_status(connection, run_id, schema.RUN_STATUS_RUNNING, started_at=STARTED_AT)
    if record is not None:
        repository.persist_completed_game(connection, run_id, record, events)
    return run_id


def loose(value, **changes):
    fields = dict(vars(value))
    fields.update(changes)
    return SimpleNamespace(**fields)


class ModelAuthenticationTests(unittest.TestCase):
    def test_actual_profile_and_table_authenticated_once_and_immutable(self):
        with patch.object(physical, "load_timing_table", wraps=physical.load_timing_table) as loader:
            evaluation = modeled.authenticate_model_c()
        loader.assert_called_once_with(physical.PROFILE_PATH)
        self.assertEqual(evaluation.initial_cursor, (0, 0))
        self.assertEqual(evaluation.timing_unit, "us")
        self.assertEqual(evaluation.physical_profile_sha256, physical.PROFILE_SHA256)
        self.assertEqual(evaluation.timing_table_sha256, physical.TABLE_SHA256)
        self.assertIsInstance(evaluation.table, tuple)
        with self.assertRaises(FrozenInstanceError):
            evaluation.table = ()
        with self.assertRaises(TypeError):
            modeled.ModelCEvaluation(table=())
        with self.assertRaises(ValueError):
            replace(evaluation, timing_unit="ms")

    def test_missing_profile_fails_without_fallback(self):
        with patch.object(Path, "read_bytes", side_effect=FileNotFoundError("missing")):
            with self.assertRaisesRegex(modeled.ModeledTimeValidationError, "authentication"):
                modeled.authenticate_model_c()

    def test_corrupted_profile_bytes_fail(self):
        with patch.object(Path, "read_bytes", return_value=b"corrupted profile"):
            with self.assertRaisesRegex(modeled.ModeledTimeValidationError, "profile SHA"):
                modeled.authenticate_model_c()

    def test_corrupt_table_content_and_hash_fail_independently(self):
        original = json.loads(physical.PROFILE_PATH.read_bytes())
        for change in ("content", "hash", "bool", "float"):
            profile = json.loads(json.dumps(original))
            if change == "hash":
                profile["table_sha256"] = "0" * 64
            else:
                profile["timing_table_us"][0][0] = {"content": 1, "bool": True, "float": 1.0}[change]
            raw = json.dumps(profile).encode()
            # Let only the profile-byte gate pass, isolating its independent
            # metadata/table validation. No production profile is changed.
            with self.subTest(change=change), patch.object(Path, "read_bytes", return_value=raw), \
                    patch.object(physical, "PROFILE_SHA256", hashlib.sha256(raw).hexdigest()):
                with self.assertRaises(modeled.ModeledTimeValidationError):
                    modeled.authenticate_model_c()

    def test_wrong_model_metadata_and_unit_fail(self):
        original = json.loads(physical.PROFILE_PATH.read_bytes())
        for field, value in (("model_id", "latest"), ("timing_unit", "ms"), ("grid_width", True)):
            raw = json.dumps({**original, field: value}).encode()
            with self.subTest(field=field), patch.object(Path, "read_bytes", return_value=raw), \
                    patch.object(physical, "PROFILE_SHA256", hashlib.sha256(raw).hexdigest()):
                with self.assertRaisesRegex(modeled.ModeledTimeValidationError, "metadata"):
                    modeled.authenticate_model_c()


class InMemoryReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation = modeled.authenticate_model_c()

    def setUp(self):
        self.record, self.events = completed_game()

    def evaluate(self, record=None, events=None, **kwargs):
        return modeled.reconstruct_game(
            self.record if record is None else record, self.events if events is None else events,
            width=30, height=16, evaluation=self.evaluation, **kwargs,
        )

    def test_exact_sum_includes_initial_and_terminal_targets(self):
        result = self.evaluate()
        table = self.evaluation.table
        self.assertEqual(result.total_modeled_us, table[0][0] + table[2][1] + 2 * table[1][1])
        self.assertEqual(result.ordered_actions, ((1, 0, 0), (2, 2, 1), (3, 3, 2), (1, 4, 3)))
        self.assertEqual(result.result, "WIN")
        self.assertIs(type(result.total_modeled_us), int)

    def test_loss_final_input_is_counted(self):
        record, events = completed_game(status=GameStatus.LOST)
        self.assertEqual(self.evaluate(record, events).total_modeled_us, self.evaluate().total_modeled_us)
        self.assertEqual(self.evaluate(record, events).result, "LOSS")

    def test_missing_extra_duplicate_shifted_and_noncontiguous_actions_rejected(self):
        cases = (
            (), self.events[:-1], (*self.events, self.events[-1]),
            (self.events[0], loose(self.events[1], action_index=0), *self.events[2:]),
            tuple(loose(event, action_index=event.action_index + 1) for event in self.events),
            (self.events[0], loose(self.events[1], action_index=8), *self.events[2:]),
        )
        for index, events in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(events=events)

    def test_nonpositive_or_mismatched_total_actions_rejected(self):
        for total in (0, -1, True, 4.0, 3, 5):
            with self.subTest(total=total), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(record=loose(self.record, total_actions=total))

    def test_coordinate_and_index_domains_reject_bool_float_text_and_bounds(self):
        for field, value in (("x", True), ("y", False), ("x", "2"), ("y", 1.0),
                             ("x", -1), ("x", 30), ("y", 16), ("action_index", True),
                             ("action_index", 1.0), ("action_index", "1")):
            events = (self.events[0], loose(self.events[1], **{field: value}), *self.events[2:])
            with self.subTest(field=field, value=value), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(events=events)

    def test_action_status_require_actual_public_enums(self):
        impostor_action = Enum("OtherAction", {"OPEN": 1})
        impostor_status = Enum("OtherStatus", {"PLAYING": 1})
        for field, value in (("action_type", 1), ("action_type", "OPEN"),
                             ("action_type", impostor_action.OPEN), ("action_type", 99),
                             ("status_after", 1), ("status_after", impostor_status.PLAYING),
                             ("status_after", "INVALID")):
            events = (self.events[0], loose(self.events[1], **{field: value}), *self.events[2:])
            with self.subTest(field=field, value=value), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(events=events)

    def test_wrong_first_action_and_target_rejected(self):
        for change in (dict(action_type=Action.FLAG), dict(action_type=Action.CHORD), dict(x=1), dict(y=1)):
            with self.subTest(change=change), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(events=(loose(self.events[0], **change), *self.events[1:]))

    def test_first_click_run_game_mismatch_and_bool_rejected(self):
        for change in (dict(first_click_x=1), dict(first_click_y=1), dict(first_click_x=False)):
            with self.subTest(change=change), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(record=loose(self.record, **change))
        for click in ((1, 0), (False, 0), (0,), "00"):
            with self.subTest(click=click), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(first_click=click)

    def test_early_terminal_post_terminal_and_final_mismatch_rejected(self):
        for index, status in ((0, GameStatus.WON), (1, GameStatus.LOST),
                              (3, GameStatus.PLAYING), (3, GameStatus.LOST)):
            events = list(self.events)
            events[index] = loose(events[index], status_after=status)
            with self.subTest(index=index, status=status), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(events=events)

    def test_unsupported_game_result_and_dimensions_rejected(self):
        for result in ("PLAYING", "WON", 1, True, None):
            with self.subTest(result=result), self.assertRaises(modeled.ModeledTimeValidationError):
                self.evaluate(record=loose(self.record, result=result))
        for width, height in ((True, 16), (30, False), (31, 16), (30, 17), (0, 16)):
            with self.subTest(width=width, height=height), self.assertRaises(modeled.ModeledTimeValidationError):
                modeled.reconstruct_game(self.record, self.events, width=width, height=height, evaluation=self.evaluation)

    def test_evaluation_is_explicit_and_no_trace_cost_is_consulted(self):
        with self.assertRaises(modeled.ModeledTimeValidationError):
            modeled.reconstruct_game(self.record, self.events, width=30, height=16, evaluation=None)
        events = tuple(loose(event, modeled_action_us=-999999, cursor_before=(99, 99)) for event in self.events)
        with patch.object(physical, "load_timing_table", side_effect=AssertionError("reauth per game")):
            self.assertEqual(self.evaluate(events=events).total_modeled_us, self.evaluate().total_modeled_us)

    def test_equal_total_does_not_prove_ordered_action_identity(self):
        # FLAG and CHORD share the displacement model; changed physical input
        # types can have equal totals while still being distinct streams.
        changed = (self.events[0], loose(self.events[1], action_type=Action.CHORD), *self.events[2:])
        self.assertEqual(self.evaluate().total_modeled_us, self.evaluate(events=changed).total_modeled_us)
        self.assertNotEqual(self.evaluate().ordered_actions, self.evaluate(events=changed).ordered_actions)

    def test_equal_cost_different_target_order_remains_distinct(self):
        reconstructed = []
        for targets in (((0, 0), (1, 0), (0, 1)), ((0, 0), (0, 1), (1, 0))):
            collector = TelemetryCollector()
            for index, (x, y) in enumerate(targets):
                collector.record_action(
                    action_type=Action.OPEN, x=x, y=y,
                    status_after=GameStatus.WON if index == 2 else GameStatus.PLAYING,
                    safe_cells_opened_delta=1, explicit_flag_delta=0,
                )
            record = collector.finalize(
                game_index=0, seed=0, board_fingerprint="a" * 64, board_3bv=3, board_ops=0,
            )
            reconstructed.append(self.evaluate(record, collector.events))
        self.assertEqual(self.evaluation.table[1][0], self.evaluation.table[0][1])
        self.assertEqual(reconstructed[0].total_modeled_us, reconstructed[1].total_modeled_us)
        self.assertNotEqual(reconstructed[0].ordered_actions, reconstructed[1].ordered_actions)


class PersistedReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation = modeled.authenticate_model_c()

    def setUp(self):
        self.connection = memory_database()
        self.addCleanup(self.connection.close)
        self.record, self.events = completed_game()
        self.stage2_id = install_run(self.connection, record=self.record, events=self.events)
        self.stage3_id = install_run(self.connection, stage3=True, record=self.record, events=self.events)

    def validate(self, run_id=None, stage=None):
        return modeled.validate_run_identity(
            self.connection, self.stage3_id if run_id is None else run_id,
            solver_stage=schema.SOLVER_STAGE_STAGE_3 if stage is None else stage,
            evaluation=self.evaluation,
        )

    def evaluate(self, run_id=None, stage=None):
        return modeled.reconstruct_persisted_game(
            self.connection, self.validate(run_id, stage), 0, evaluation=self.evaluation,
        )

    def test_stage2_posthoc_and_stage3_same_actual_table_equal_without_backfill(self):
        before = tuple(self.connection.iterdump())
        left = self.evaluate(self.stage2_id, schema.SOLVER_STAGE_STAGE_2)
        right = self.evaluate()
        self.assertEqual(left, right)
        self.assertEqual(tuple(self.connection.iterdump()), before)

    def test_run_role_version_policy_corpus_and_first_click_identity(self):
        for field, value in (("telemetry_schema_version", 1), ("solver_stage", "STAGE_2"),
                             ("solver_policy", "OTHER"), ("benchmark_set_id", "OTHER"),
                             ("width", 29), ("height", 15), ("num_mines", 98),
                             ("first_click_policy", "OTHER"), ("board_generator_version", "V2")):
            original = self.connection.execute(f"SELECT {field} FROM benchmark_runs WHERE run_id=?", (self.stage3_id,)).fetchone()[0]
            self.connection.execute(f"UPDATE benchmark_runs SET {field}=? WHERE run_id=?", (value, self.stage3_id))
            with self.subTest(field=field), self.assertRaises(modeled.ModeledTimeValidationError):
                self.validate()
            self.connection.execute(f"UPDATE benchmark_runs SET {field}=? WHERE run_id=?", (original, self.stage3_id))

    def test_every_stage3_config_field_missing_changed_or_extra_fails(self):
        original = self.connection.execute("SELECT solver_config_snapshot FROM benchmark_runs WHERE run_id=?", (self.stage3_id,)).fetchone()[0]
        config = json.loads(original)
        cases = [{key: value for key, value in config.items() if key != removed} for removed in config]
        cases.extend({**config, field: value} for field, value in (
            ("initial_open", [1, 0]), ("initial_cursor", [0, 1]), ("initial_cursor", [False, 0]),
            ("algorithm_spec_version", True), ("algorithm_spec_sha256", "bad"),
            ("physical_model_id", "other"), ("physical_profile_version", 1.0),
            ("physical_profile_sha256", "bad"), ("timing_table_sha256", "bad"),
            ("timing_unit", "ms"), ("extra", 1),
        ))
        for index, changed in enumerate(cases):
            self.connection.execute("UPDATE benchmark_runs SET solver_config_snapshot=? WHERE run_id=?", (json.dumps(changed, sort_keys=True, separators=(",", ":")), self.stage3_id))
            with self.subTest(case=index), self.assertRaises(modeled.ModeledTimeValidationError):
                self.validate()

    def test_stage2_config_and_role_are_not_inferred_or_backfilled(self):
        for value in ('{}', '{"accept_guesses":1,"initial_open":[0,0]}', '{"accept_guesses":false,"initial_open":[0,0]}'):
            self.connection.execute("UPDATE benchmark_runs SET solver_config_snapshot=? WHERE run_id=?", (value, self.stage2_id))
            with self.subTest(value=value), self.assertRaises(modeled.ModeledTimeValidationError):
                self.validate(self.stage2_id, schema.SOLVER_STAGE_STAGE_2)
        with self.assertRaises(modeled.ModeledTimeValidationError):
            self.validate(self.stage2_id, schema.SOLVER_STAGE_STAGE_3)

    def test_unknown_run_or_role_rejected(self):
        for run_id, stage in ((999, "STAGE_3"), (True, "STAGE_3"), (self.stage2_id, "STAGE_4")):
            with self.subTest(run_id=run_id, stage=stage), self.assertRaises(modeled.ModeledTimeValidationError):
                self.validate(run_id, stage)

    def test_reconstruction_rechecks_source_identity_and_handle_dimensions(self):
        run = self.validate()
        with self.assertRaises(modeled.ModeledTimeValidationError):
            modeled.reconstruct_persisted_game(self.connection, replace(run, width=1), 0, evaluation=self.evaluation)
        self.connection.execute("UPDATE benchmark_runs SET solver_policy='changed' WHERE run_id=?", (self.stage3_id,))
        with self.assertRaises(modeled.ModeledTimeValidationError):
            modeled.reconstruct_persisted_game(self.connection, run, 0, evaluation=self.evaluation)

    def test_handle_from_other_source_with_equal_run_id_cannot_skip_identity(self):
        run = self.validate()
        other = memory_database()
        self.addCleanup(other.close)
        install_run(other)
        other_id = install_run(other, record=self.record, events=self.events)
        self.assertEqual(run.run_id, other_id)
        before = tuple(other.iterdump())
        with self.assertRaisesRegex(modeled.ModeledTimeValidationError, "run identity"):
            modeled.reconstruct_persisted_game(other, run, 0, evaluation=self.evaluation)
        self.assertEqual(tuple(other.iterdump()), before)

    def test_pairing_passes_but_deleted_raw_actions_fail_reconstruction(self):
        for index in (None, 1):
            connection = memory_database()
            try:
                left = install_run(connection, record=self.record, events=self.events)
                right = install_run(connection, stage3=True, record=self.record, events=self.events)
                where = "" if index is None else " AND action_index=1"
                connection.execute("DELETE FROM action_events WHERE game_id=(SELECT game_id FROM games WHERE run_id=?)" + where, (right,))
                benchmark_statistics.validate_paired_prefix(connection, left, right, 1)
                run = modeled.validate_run_identity(connection, right, solver_stage="STAGE_3", evaluation=self.evaluation)
                with self.subTest(deleted=index), self.assertRaisesRegex(modeled.ModeledTimeValidationError, "row count"):
                    modeled.reconstruct_persisted_game(connection, run, 0, evaluation=self.evaluation)
            finally:
                connection.close()

    def test_persisted_structural_corruption_fails_closed(self):
        mutations = (
            "UPDATE action_events SET action_index=action_index+10 WHERE game_id=2",
            "UPDATE action_events SET action_index=8 WHERE game_id=2 AND action_index=1",
            "UPDATE games SET total_actions=5 WHERE game_id=2",
            "UPDATE games SET result=99 WHERE game_id=2",
            "UPDATE games SET first_click_x=1 WHERE game_id=2",
            "UPDATE action_events SET x=30 WHERE game_id=2 AND action_index=1",
            "UPDATE action_events SET x='bad' WHERE game_id=2 AND action_index=1",
            "UPDATE action_events SET y=1.5 WHERE game_id=2 AND action_index=1",
            "UPDATE action_events SET action_type=99 WHERE game_id=2 AND action_index=1",
            "UPDATE action_events SET status_after=99 WHERE game_id=2 AND action_index=1",
            "UPDATE action_events SET action_type=2 WHERE game_id=2 AND action_index=0",
            "UPDATE action_events SET x=1 WHERE game_id=2 AND action_index=0",
            "UPDATE action_events SET status_after=2 WHERE game_id=2 AND action_index=1",
            "UPDATE action_events SET status_after=3 WHERE game_id=2 AND action_index=3",
        )
        self.connection.execute("PRAGMA ignore_check_constraints=ON")
        for mutation in mutations:
            self.connection.execute("SAVEPOINT corruption")
            try:
                self.connection.execute(mutation)
                with self.subTest(mutation=mutation), self.assertRaises(modeled.ModeledTimeValidationError):
                    self.evaluate()
            finally:
                self.connection.execute("ROLLBACK TO corruption")
                self.connection.execute("RELEASE corruption")

    def test_extra_persisted_row_and_missing_game_fail(self):
        self.connection.execute("INSERT INTO action_events SELECT game_id, 9, inference_category, selection_candidate_count, target_mine_probability, minimum_available_mine_probability, decision_compute_ns, action_type, x, y, status_after, safe_cells_opened_delta, explicit_flag_delta FROM action_events WHERE game_id=2 AND action_index=3")
        with self.assertRaises(modeled.ModeledTimeValidationError):
            self.evaluate()
        with self.assertRaises(modeled.ModeledTimeValidationError):
            modeled.reconstruct_persisted_game(self.connection, self.validate(), 5, evaluation=self.evaluation)

    def test_reader_preserves_connection_and_uses_only_select(self):
        self.connection.execute("PRAGMA query_only=ON")
        statements = []
        self.connection.set_trace_callback(statements.append)
        changes = self.connection.total_changes
        factory = self.connection.row_factory
        self.evaluate()
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT") for sql in statements))
        self.assertEqual(self.connection.total_changes, changes)
        self.assertIs(self.connection.row_factory, factory)
        self.assertFalse(self.connection.in_transaction)


class ExecutionEqualityTests(unittest.TestCase):
    def test_real_runner_events_persisted_ordered_stream_and_total_equal(self):
        captured = []
        original = stage3_benchmark_runner.run_stage3

        def capture(*args, **kwargs):
            result = original(*args, **kwargs)
            captured.append(result)
            return result

        with patch.object(stage3_benchmark_runner, "run_stage3", side_effect=capture):
            record, events = stage3_benchmark_runner._play_game(EXPERT_GENERAL_V1, 0)
        result = captured[0]
        evaluation = modeled.authenticate_model_c()
        memory = modeled.reconstruct_game(record, events, width=30, height=16, evaluation=evaluation)
        connection = memory_database()
        self.addCleanup(connection.close)
        run_id = install_run(connection, stage3=True, record=record, events=events)
        run = modeled.validate_run_identity(connection, run_id, solver_stage="STAGE_3", evaluation=evaluation)
        persisted = modeled.reconstruct_persisted_game(connection, run, 0, evaluation=evaluation)
        trace_stream = tuple((repository._ACTION_TO_DB[trace.move.action], trace.move.x, trace.move.y) for trace in result.traces)
        event_stream = tuple((repository._ACTION_TO_DB[event.action_type], event.x, event.y) for event in events)
        db_stream = tuple(connection.execute("SELECT action_type,x,y FROM action_events ORDER BY action_index"))
        self.assertEqual(trace_stream, event_stream)
        self.assertEqual(event_stream, db_stream)
        self.assertEqual(memory.ordered_actions, db_stream)
        self.assertEqual(memory, persisted)
        self.assertEqual(result.total_modeled_us, persisted.total_modeled_us)
        self.assertTrue(any(action == schema.ACTION_CHORD for action, _, _ in db_stream))

    def test_runner_total_mismatch_rejected_before_completed_game_persistence(self):
        class RetainedConnection(sqlite3.Connection):
            def close(self):
                pass  # Retain the fixture for assertions after lifecycle close.

        connection = sqlite3.connect(":memory:", isolation_level=None, factory=RetainedConnection)
        self.addCleanup(sqlite3.Connection.close, connection)
        schema.initialize_schema(connection)
        original = stage3_benchmark_runner.run_stage3

        def incorrect_total(*args, **kwargs):
            result = original(*args, **kwargs)
            return loose(result, total_modeled_us=result.total_modeled_us + 1)

        with patch.object(stage3_benchmark_runner, "run_stage3", side_effect=incorrect_total), \
                patch.object(benchmark_runner, "_capture_git_provenance", return_value=("abc123", False)), \
                patch.object(repository, "connect_database", return_value=connection), \
                patch.object(repository, "persist_completed_game") as persist:
            with self.assertRaisesRegex(benchmark_runner.BenchmarkInvariantError, "modeled time"):
                stage3_benchmark_runner.run_stage3_benchmark("unused-fixture.sqlite3", 1)
        persist.assert_not_called()
        self.assertEqual(connection.execute("SELECT run_status,failure_code,processed_games FROM benchmark_runs").fetchone(),
                         ("FAILED", "GAME_EXECUTION_FAILED", 0))
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM games").fetchone()[0], 0)

    def test_terminal_initial_input_and_automatic_win_flags_have_one_cost(self):
        engine = MinesweeperEngine(3, 1, 1)
        engine.reset_with_mines(3, 1, 1, {(2, 0)})
        collector = TelemetryCollector()
        result = run_stage3(engine, observer=lambda trace: stage3_benchmark_runner._record_trace(collector, trace))
        record = collector.finalize(game_index=0, seed=0, board_fingerprint="a" * 64, board_3bv=1, board_ops=1)
        evaluation = modeled.authenticate_model_c()
        actual = modeled.reconstruct_game(record, collector.events, width=3, height=1, evaluation=evaluation)
        self.assertEqual(len(actual.ordered_actions), 1)
        self.assertEqual(engine.get_observation(), [[0, 1, -3]])
        self.assertEqual(record.flag_count, 0)
        self.assertEqual(actual.total_modeled_us, evaluation.table[0][0])
        self.assertEqual(actual.total_modeled_us, result.total_modeled_us)

    def test_flood_flag_clearing_is_not_a_synthetic_physical_action(self):
        engine = MinesweeperEngine(4, 3, 1)
        engine.reset_with_mines(4, 3, 1, {(1, 0)})
        collector = TelemetryCollector()
        for action, x, y, safe_delta, flag_delta in (
            (Action.OPEN, 0, 0, 1, 0), (Action.FLAG, 3, 2, 0, 1), (Action.OPEN, 3, 1, 10, 0),
        ):
            engine.step(x, y, action)
            collector.record_action(action_type=action, x=x, y=y, status_after=engine.status,
                                    safe_cells_opened_delta=safe_delta, explicit_flag_delta=flag_delta)
        self.assertEqual(engine.status, GameStatus.WON)
        self.assertGreaterEqual(engine.get_observation()[2][3], 0)
        record = collector.finalize(game_index=0, seed=0, board_fingerprint="a" * 64, board_3bv=1, board_ops=1)
        evaluation = modeled.authenticate_model_c()
        result = modeled.reconstruct_game(record, collector.events, width=4, height=3, evaluation=evaluation)
        self.assertEqual(len(result.ordered_actions), 3)
        self.assertEqual(record.flag_count, 1)
        self.assertEqual(result.total_modeled_us, evaluation.table[0][0] + evaluation.table[3][2] + evaluation.table[0][1])

    def test_reconstruction_has_no_solver_reanalysis_or_hidden_information_access(self):
        record, events = completed_game()
        evaluation = modeled.authenticate_model_c()
        with patch("stage3_planner.plan_position", side_effect=AssertionError("planner")), \
                patch("simple_decision.analyze_position", side_effect=AssertionError("solver")), \
                patch.object(MinesweeperEngine, "step", side_effect=AssertionError("execution")), \
                patch.object(MinesweeperEngine, "get_board_snapshot", side_effect=AssertionError("hidden")):
            modeled.reconstruct_game(record, events, width=30, height=16, evaluation=evaluation)
        tree = ast.parse(inspect.getsource(modeled))
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertNotIn("stage3_planner", imported)
        self.assertNotIn("stage3_runner", imported)
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertTrue({"get_board_snapshot", "step", "analyze_position", "plan_position"}.isdisjoint(calls))
        forbidden = {"BoardSnapshot", "mine_positions", "board_fingerprint", "board_3bv", "board_ops", "modeled_action_us"}
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertTrue(forbidden.isdisjoint(attributes))


if __name__ == "__main__":
    unittest.main()
