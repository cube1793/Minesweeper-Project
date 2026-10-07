"""Common board identity pairing across caller-owned telemetry sources."""

import sqlite3
import unittest

import benchmark_statistics as statistics
import telemetry_repository as repository
import telemetry_schema as schema
from core_engine import Action, GameStatus
from telemetry_collector import TelemetryCollector


class PairingSourcesTests(unittest.TestCase):
    def source(self):
        connection = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(connection.close)
        schema.initialize_schema(connection)
        return connection

    def add_run(self, connection, version=1, **overrides):
        values = dict(
            telemetry_schema_version=version, created_at="2026-10-07T00:00:00Z",
            git_commit="a" * 40, git_dirty=False,
            solver_stage="STAGE_2" if version == 1 else "STAGE_3",
            solver_policy="SIMPLE_MINIMUM_RISK" if version == 1 else "E_FIRST_FIRST_REVEAL_V1",
            solver_config_snapshot={"initial_open": [0, 0]}, width=8, height=6,
            num_mines=7, first_click_policy=schema.FIRST_CLICK_FIXED_0_0,
            board_generator_version=schema.BOARD_GENERATOR_V1,
            benchmark_set_id="PAIRING_TEST_V1", requested_games=3,
            environment_snapshot={"fixture": True}, run_status=schema.RUN_STATUS_RUNNING,
        )
        values.update(overrides)
        run_id = repository.create_run(connection, **values)
        for index in range(values["requested_games"]):
            collector = TelemetryCollector()
            collector.record_action(
                action_type=Action.OPEN, x=0, y=0, status_after=GameStatus.WON,
                safe_cells_opened_delta=1, explicit_flag_delta=0,
            )
            game = collector.finalize(
                game_index=index, seed=index, board_fingerprint=f"{index:064x}",
                board_3bv=1, board_ops=0,
            )
            repository.persist_completed_game(connection, run_id, game, collector.events)
        repository.update_run_status(connection, run_id, schema.RUN_STATUS_COMPLETED)
        return run_id

    def pair(self):
        left, right = self.source(), self.source()
        return left, self.add_run(left), right, self.add_run(right, 2)

    def test_same_source_accepts_exactly_four_known_version_pairs(self):
        connection = self.source()
        for versions in ((1, 1), (1, 2), (2, 1), (2, 2)):
            with self.subTest(versions=versions):
                left, right = (self.add_run(connection, version) for version in versions)
                result = statistics.validate_paired_prefix(
                    connection, left, right, 3, require_official=True,
                )
                self.assertEqual(tuple(item.game_index for item in result.identities), (0, 1, 2))
                self.assertEqual(result, statistics.validate_paired_prefix_sources(
                    connection, left, connection, right, 3, require_official=True,
                ))

    def test_two_sources_accept_known_pairs_with_equal_run_ids(self):
        for versions in ((1, 1), (1, 2), (2, 1), (2, 2)):
            with self.subTest(versions=versions):
                left, right = self.source(), self.source()
                left_id = self.add_run(left, versions[0])
                right_id = self.add_run(right, versions[1])
                self.assertEqual((left_id, right_id), (1, 1))
                result = statistics.validate_paired_prefix_sources(
                    left, left_id, right, right_id, 2, require_official=True,
                )
                self.assertEqual((result.left_run_id, result.right_run_id), (1, 1))
                self.assertEqual(tuple(item.seed for item in result.identities), (0, 1))
                self.assertEqual(result.prefix_games, 2)

    def test_unknown_versions_rejected_even_when_both_match(self):
        for version in (0, -1, 3, 999, 1.5, "unknown"):
            for changed in ((0,), (1,), (0, 1)):
                with self.subTest(version=version, changed=changed):
                    left, left_id, right, right_id = self.pair()
                    for index in changed:
                        connection, run_id = ((left, left_id), (right, right_id))[index]
                        connection.execute(
                            "UPDATE benchmark_runs SET telemetry_schema_version = ? WHERE run_id = ?",
                            (version, run_id),
                        )
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "telemetry_schema_version"):
                        statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3)

    def test_every_common_run_compatibility_field_remains_strict(self):
        for field, value in (
            ("benchmark_set_id", "OTHER"), ("width", 9), ("height", 7),
            ("num_mines", 8), ("first_click_policy", "OTHER"),
            ("board_generator_version", "OTHER"),
        ):
            for side in (0, 1):
                with self.subTest(field=field, side=side):
                    left, left_id, right, right_id = self.pair()
                    connection, run_id = ((left, left_id), (right, right_id))[side]
                    connection.execute(f"UPDATE benchmark_runs SET {field} = ? WHERE run_id = ?", (value, run_id))
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, field):
                        statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3)

    def test_each_game_identity_mismatch_rejected_on_either_source(self):
        for field, value in (
            ("seed", 99), ("board_fingerprint", "f" * 64),
            ("first_click_x", 1), ("first_click_y", 1),
        ):
            for side in (0, 1):
                with self.subTest(field=field, side=side):
                    left, left_id, right, right_id = self.pair()
                    connection, run_id = ((left, left_id), (right, right_id))[side]
                    connection.execute(
                        f"UPDATE games SET {field} = ? WHERE run_id = ? AND game_index = 1", (value, run_id),
                    )
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, f"game_index 1: {field}"):
                        statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3)

    def test_first_middle_last_missing_rows_never_disappear_in_join(self):
        for side in (0, 1):
            for missing in (0, 1, 2):
                with self.subTest(side=side, missing=missing):
                    left, left_id, right, right_id = self.pair()
                    connection, run_id = ((left, left_id), (right, right_id))[side]
                    connection.execute("DELETE FROM games WHERE run_id = ? AND game_index = ?", (run_id, missing))
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "missing exact coverage"):
                        statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3)

    def test_matching_shifted_indices_fail_explicit_prefix(self):
        left, left_id, right, right_id = self.pair()
        for connection, run_id in ((left, left_id), (right, right_id)):
            connection.execute("UPDATE games SET game_index = 3 WHERE run_id = ? AND game_index = 0", (run_id,))
        with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "missing exact coverage"):
            statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3)

    def test_official_eligibility_checks_both_entire_artifacts(self):
        for side in (0, 1):
            for corruption in ("dirty", "running", "outside_gap"):
                with self.subTest(side=side, corruption=corruption):
                    left, left_id, right, right_id = self.pair()
                    connection, run_id = ((left, left_id), (right, right_id))[side]
                    if corruption == "dirty":
                        connection.execute("UPDATE benchmark_runs SET git_dirty = 1 WHERE run_id = ?", (run_id,))
                    elif corruption == "running":
                        repository.update_run_status(connection, run_id, schema.RUN_STATUS_RUNNING)
                    else:
                        connection.execute("UPDATE games SET game_index = 3 WHERE run_id = ? AND game_index = 2", (run_id,))
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "not official-eligible"):
                        statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 2, require_official=True)
                    self.assertFalse(statistics.validate_paired_prefix_sources(
                        left, left_id, right, right_id, 2,
                    ).require_official)

    def test_diagnostic_range_ignores_unselected_identity_but_never_exceeds_requested(self):
        left, left_id, right, right_id = self.pair()
        right.execute("UPDATE games SET seed = 100 WHERE run_id = ? AND game_index = 2", (right_id,))
        self.assertEqual(statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 2).prefix_games, 2)
        with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "seed"):
            statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3)
        with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "exceeds requested_games"):
            statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 4)

    def test_unknown_runs_and_invalid_arguments_fail_closed(self):
        left, left_id, right, right_id = self.pair()
        for a, b in ((999, right_id), (left_id, 999), (True, right_id), (left_id, "1")):
            with self.subTest(ids=(a, b)), self.assertRaises(statistics.BenchmarkStatisticsError):
                statistics.validate_paired_prefix_sources(left, a, right, b, 1)
        for prefix in (0, -1, True, False, 1.0, "1", None):
            with self.subTest(prefix=prefix), self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "prefix_games"):
                statistics.validate_paired_prefix_sources(left, left_id, right, right_id, prefix)
        for value in (1, "false", None):
            with self.subTest(official=value), self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "require_official"):
                statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 1, require_official=value)

    def test_pairing_keeps_solver_identity_and_action_completeness_separate(self):
        left, left_id, right, right_id = self.pair()
        right.execute("UPDATE benchmark_runs SET solver_stage = 'OTHER', solver_policy = 'OTHER' WHERE run_id = ?", (right_id,))
        right.execute("DELETE FROM action_events")
        result = statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3, require_official=True)
        self.assertEqual(len(result.identities), 3)
        self.assertEqual(right.execute("SELECT COUNT(*) FROM action_events").fetchone()[0], 0)

    def test_both_sources_remain_select_only_on_success_and_rejection(self):
        left, left_id, right, right_id = self.pair()
        left.row_factory = sqlite3.Row
        connections = (left, right)
        before = tuple(tuple(connection.iterdump()) for connection in connections)
        changes = tuple(connection.total_changes for connection in connections)
        statements, denied = [], []

        def allow_reads_only(operation, argument, unused, database, source):
            if operation not in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION):
                denied.append((operation, argument))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        for connection in connections:
            connection.set_trace_callback(statements.append)
            connection.set_authorizer(allow_reads_only)
        try:
            statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3, require_official=True)
            with self.assertRaises(statistics.BenchmarkStatisticsError):
                statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 4)
        finally:
            for connection in connections:
                connection.set_authorizer(None)
                connection.set_trace_callback(None)
        self.assertEqual(denied, [])
        self.assertTrue(statements)
        self.assertTrue(all(statement.lstrip().upper().startswith("SELECT ") for statement in statements))
        self.assertEqual(tuple(tuple(connection.iterdump()) for connection in connections), before)
        self.assertEqual(tuple(connection.total_changes for connection in connections), changes)
        self.assertIs(left.row_factory, sqlite3.Row)
        self.assertIsNone(right.row_factory)
        for connection in connections:
            self.assertFalse(connection.in_transaction)
            self.assertIsNone(connection.isolation_level)
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)

    def test_caller_transactions_and_uncommitted_work_remain_caller_owned(self):
        left, left_id, right, right_id = self.pair()
        for connection, run_id in ((left, left_id), (right, right_id)):
            connection.execute("BEGIN")
            connection.execute("UPDATE benchmark_runs SET app_version = 'pending' WHERE run_id = ?", (run_id,))
        changes = (left.total_changes, right.total_changes)
        statistics.validate_paired_prefix_sources(left, left_id, right, right_id, 3, require_official=True)
        self.assertEqual((left.total_changes, right.total_changes), changes)
        for connection, run_id in ((left, left_id), (right, right_id)):
            self.assertTrue(connection.in_transaction)
            connection.rollback()
            self.assertIsNone(connection.execute("SELECT app_version FROM benchmark_runs WHERE run_id = ?", (run_id,)).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
