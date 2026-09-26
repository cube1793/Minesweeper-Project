"""Frozen SQLite V1 structure, independent of repository connection policy."""

import runpy
import sqlite3
import sys
import unittest
from unittest.mock import patch

import telemetry_schema as schema


RUN_COLUMNS = (
    ("run_id", "INTEGER", 0, 1),
    ("telemetry_schema_version", "INTEGER", 1, 0),
    ("created_at", "TEXT", 1, 0),
    ("started_at", "TEXT", 0, 0),
    ("finished_at", "TEXT", 0, 0),
    ("run_status", "TEXT", 1, 0),
    ("git_commit", "TEXT", 1, 0),
    ("git_dirty", "INTEGER", 1, 0),
    ("app_version", "TEXT", 0, 0),
    ("solver_stage", "TEXT", 1, 0),
    ("solver_policy", "TEXT", 1, 0),
    ("solver_config_snapshot", "TEXT", 1, 0),
    ("width", "INTEGER", 1, 0),
    ("height", "INTEGER", 1, 0),
    ("num_mines", "INTEGER", 1, 0),
    ("difficulty_name", "TEXT", 0, 0),
    ("first_click_policy", "TEXT", 1, 0),
    ("board_generator_version", "TEXT", 1, 0),
    ("benchmark_set_id", "TEXT", 1, 0),
    ("requested_games", "INTEGER", 1, 0),
    ("processed_games", "INTEGER", 1, 0),
    ("environment_snapshot", "TEXT", 1, 0),
    ("failure_code", "TEXT", 0, 0),
)
GAME_COLUMNS = (
    ("game_id", "INTEGER", 0, 1),
    ("run_id", "INTEGER", 1, 0),
    ("game_index", "INTEGER", 1, 0),
    ("seed", "INTEGER", 1, 0),
    ("board_fingerprint", "TEXT", 1, 0),
    ("first_click_x", "INTEGER", 1, 0),
    ("first_click_y", "INTEGER", 1, 0),
    ("result", "INTEGER", 1, 0),
    ("total_actions", "INTEGER", 1, 0),
    ("open_count", "INTEGER", 1, 0),
    ("flag_count", "INTEGER", 1, 0),
    ("chord_count", "INTEGER", 1, 0),
    ("local_deterministic_count", "INTEGER", 1, 0),
    ("global_certainty_count", "INTEGER", 1, 0),
    ("probability_guess_count", "INTEGER", 1, 0),
    ("had_probability_guess", "INTEGER", 1, 0),
    ("first_guess_action_index", "INTEGER", 0, 0),
    ("board_3bv", "INTEGER", 1, 0),
    ("board_ops", "INTEGER", 1, 0),
    ("compute_time_total_ns", "INTEGER", 1, 0),
    ("compute_time_max_ns", "INTEGER", 0, 0),
)
EVENT_COLUMNS = (
    ("game_id", "INTEGER", 1, 1),
    ("action_index", "INTEGER", 1, 2),
    ("inference_category", "INTEGER", 0, 0),
    ("selection_candidate_count", "INTEGER", 0, 0),
    ("target_mine_probability", "TEXT", 0, 0),
    ("minimum_available_mine_probability", "TEXT", 0, 0),
    ("decision_compute_ns", "INTEGER", 0, 0),
    ("action_type", "INTEGER", 1, 0),
    ("x", "INTEGER", 1, 0),
    ("y", "INTEGER", 1, 0),
    ("status_after", "INTEGER", 1, 0),
    ("safe_cells_opened_delta", "INTEGER", 1, 0),
    ("explicit_flag_delta", "INTEGER", 1, 0),
)
FROZEN_CONSTANTS = {
    "PHYSICAL_SCHEMA_VERSION": 1,
    "TELEMETRY_SCHEMA_VERSION": 1,
    "SOLVER_STAGE_STAGE_2": "STAGE_2",
    "SOLVER_POLICY_SIMPLE_MINIMUM_RISK": "SIMPLE_MINIMUM_RISK",
    "ACTION_OPEN": 1,
    "ACTION_FLAG": 2,
    "ACTION_CHORD": 3,
    "INFERENCE_LOCAL_DETERMINISTIC": 1,
    "INFERENCE_GLOBAL_CERTAINTY": 2,
    "INFERENCE_PROBABILITY_GUESS": 3,
    "STATUS_AFTER_PLAYING": 1,
    "STATUS_AFTER_WON": 2,
    "STATUS_AFTER_LOST": 3,
    "GAME_RESULT_WIN": 1,
    "GAME_RESULT_LOSS": 2,
    "RUN_STATUS_CREATED": "CREATED",
    "RUN_STATUS_RUNNING": "RUNNING",
    "RUN_STATUS_COMPLETED": "COMPLETED",
    "RUN_STATUS_ABORTED": "ABORTED",
    "RUN_STATUS_INTERRUPTED": "INTERRUPTED",
    "RUN_STATUS_FAILED": "FAILED",
    "FIRST_CLICK_FIXED_0_0": "FIRST_CLICK_FIXED_0_0",
    "BOARD_GENERATOR_V1": "V1",
}


def run_values(**overrides):
    values = dict(
        run_id=1, telemetry_schema_version=7,
        created_at="2026-09-26T00:00:00Z", started_at=None, finished_at=None,
        run_status="CREATED", git_commit="a" * 40, git_dirty=0, app_version=None,
        solver_stage="test-stage", solver_policy="test-policy",
        solver_config_snapshot="{}", width=9, height=9, num_mines=10,
        difficulty_name=None, first_click_policy="FIRST_CLICK_FIXED_0_0",
        board_generator_version="V1", benchmark_set_id="test-set",
        requested_games=3, processed_games=0, environment_snapshot="{}",
        failure_code=None,
    )
    values.update(overrides)
    return values


def game_values(**overrides):
    values = dict(
        game_id=1, run_id=1, game_index=0, seed=0,
        board_fingerprint="0123456789abcdef" * 4, first_click_x=0,
        first_click_y=0, result=1, total_actions=1, open_count=1, flag_count=0,
        chord_count=0, local_deterministic_count=0, global_certainty_count=0,
        probability_guess_count=0, had_probability_guess=0,
        first_guess_action_index=None, board_3bv=0, board_ops=0,
        compute_time_total_ns=0, compute_time_max_ns=None,
    )
    values.update(overrides)
    return values


def event_values(**overrides):
    values = dict(
        game_id=1, action_index=0, inference_category=None,
        selection_candidate_count=None, target_mine_probability=None,
        minimum_available_mine_probability=None, decision_compute_ns=None,
        action_type=1, x=0, y=0, status_after=1,
        safe_cells_opened_delta=0, explicit_flag_delta=0,
    )
    values.update(overrides)
    return values


def insert(connection, table, values):
    # Names come only from the fixed test fixtures, never external input.
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    connection.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )


class TelemetrySchemaTests(unittest.TestCase):
    def setUp(self):
        self.connection = self.new_connection()
        schema.initialize_schema(self.connection)

    def new_connection(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        return connection

    def tables(self, connection=None):
        connection = self.connection if connection is None else connection
        return {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }

    def add_parents(self):
        insert(self.connection, "benchmark_runs", run_values())
        insert(self.connection, "games", game_values())

    def assert_rejected(self, table, values):
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.connection, table, values)

    def test_new_database_installs_physical_v1_and_exactly_three_tables(self):
        self.assertEqual(schema.PHYSICAL_SCHEMA_VERSION, 1)
        self.assertEqual(self.connection.execute("PRAGMA user_version").fetchone(), (1,))
        self.assertEqual(self.tables(), {"benchmark_runs", "games", "action_events"})

    def test_exact_column_names_types_nullability_and_primary_keys(self):
        for table, expected in (
            ("benchmark_runs", RUN_COLUMNS), ("games", GAME_COLUMNS),
            ("action_events", EVENT_COLUMNS),
        ):
            with self.subTest(table=table):
                actual = tuple(
                    (row[1], row[2], row[3], row[5])
                    for row in self.connection.execute(f"PRAGMA table_info({table})")
                )
                self.assertEqual(actual, expected)

    def test_semantic_version_is_an_independent_run_column(self):
        insert(self.connection, "benchmark_runs", run_values(telemetry_schema_version=91))
        self.assertEqual(self.connection.execute(
            "SELECT telemetry_schema_version FROM benchmark_runs"
        ).fetchone(), (91,))
        self.assertEqual(self.connection.execute("PRAGMA user_version").fetchone(), (1,))

    def test_processed_games_default_is_zero(self):
        values = run_values()
        del values["processed_games"]
        insert(self.connection, "benchmark_runs", values)
        self.assertEqual(self.connection.execute(
            "SELECT processed_games FROM benchmark_runs"
        ).fetchone(), (0,))
        metadata = {row[1]: row for row in self.connection.execute(
            "PRAGMA table_info(benchmark_runs)"
        )}
        self.assertEqual(metadata["processed_games"][4], "0")

    def test_current_version_initialization_is_idempotent_and_preserves_data(self):
        self.add_parents()
        insert(self.connection, "action_events", event_values())
        self.connection.commit()
        before = list(self.connection.iterdump())
        for _ in range(2):
            self.assertIsNone(schema.initialize_schema(self.connection))
        self.assertEqual(list(self.connection.iterdump()), before)
        self.assertEqual(self.connection.execute("PRAGMA user_version").fetchone(), (1,))

    def test_unsupported_nonzero_versions_fail_without_changes(self):
        for version in (-1, 2, 2147483647):
            with self.subTest(version=version):
                connection = self.new_connection()
                connection.execute(f"PRAGMA user_version = {version}")
                with self.assertRaises(ValueError):
                    schema.initialize_schema(connection)
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (version,))
                self.assertEqual(self.tables(connection), set())

    def test_initializer_preserves_connection_operating_modes(self):
        for foreign_keys in (0, 1):
            with self.subTest(foreign_keys=foreign_keys):
                connection = self.new_connection()
                connection.execute(f"PRAGMA foreign_keys = {foreign_keys}")
                connection.execute("PRAGMA synchronous = NORMAL")
                names = ("foreign_keys", "journal_mode", "synchronous")
                before = tuple(connection.execute(f"PRAGMA {name}").fetchone() for name in names)
                schema.initialize_schema(connection)
                after = tuple(connection.execute(f"PRAGMA {name}").fetchone() for name in names)
                self.assertEqual(after, before)

    def test_v1_initialization_does_not_commit_pending_caller_work(self):
        insert(self.connection, "benchmark_runs", run_values())
        self.assertTrue(self.connection.in_transaction)
        schema.initialize_schema(self.connection)
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone(), (0,))

    def test_new_schema_initialization_preserves_outer_transaction(self):
        connection = self.new_connection()
        connection.execute("CREATE TABLE caller_work (value INTEGER)")
        connection.execute("INSERT INTO caller_work VALUES (1)")
        schema.initialize_schema(connection)
        self.assertTrue(connection.in_transaction)
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (1,))
        connection.rollback()
        self.assertEqual(self.tables(connection), {"caller_work"})
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM caller_work").fetchone(), (0,))
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (0,))

    def test_installation_failure_is_atomic_and_preserves_caller_work(self):
        for collision in ("benchmark_runs", "games", "action_events"):
            with self.subTest(collision=collision):
                connection = self.new_connection()
                connection.execute(f"CREATE TABLE {collision} (original INTEGER)")
                connection.execute(f"INSERT INTO {collision} VALUES (7)")
                with self.assertRaises(sqlite3.DatabaseError):
                    schema.initialize_schema(connection)
                self.assertTrue(connection.in_transaction)
                self.assertEqual(self.tables(connection), {collision})
                self.assertEqual(connection.execute(f"SELECT original FROM {collision}").fetchone(), (7,))
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (0,))
                connection.rollback()
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {collision}").fetchone(), (0,))

    def test_foreign_keys_declare_cascade(self):
        for table, parent, child_key, parent_key in (
            ("games", "benchmark_runs", "run_id", "run_id"),
            ("action_events", "games", "game_id", "game_id"),
        ):
            with self.subTest(table=table):
                foreign_keys = self.connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
                self.assertEqual(len(foreign_keys), 1)
                self.assertEqual(foreign_keys[0][2:7], (
                    parent, child_key, parent_key, "NO ACTION", "CASCADE",
                ))

    def test_run_delete_cascades_to_games_and_events_when_test_enables_fk(self):
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.assertEqual(self.connection.execute("PRAGMA foreign_keys").fetchone(), (1,))
        self.add_parents()
        insert(self.connection, "action_events", event_values())
        self.connection.execute("DELETE FROM benchmark_runs WHERE run_id = 1")
        for table in ("benchmark_runs", "games", "action_events"):
            self.assertEqual(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone(), (0,))

    def test_game_delete_cascades_only_its_events_when_test_enables_fk(self):
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.add_parents()
        insert(self.connection, "games", game_values(game_id=2, game_index=1))
        insert(self.connection, "action_events", event_values())
        insert(self.connection, "action_events", event_values(game_id=2))
        self.connection.execute("DELETE FROM games WHERE game_id = 1")
        self.assertEqual(self.connection.execute("SELECT run_id FROM benchmark_runs").fetchall(), [(1,)])
        self.assertEqual(self.connection.execute("SELECT game_id FROM games").fetchall(), [(2,)])
        self.assertEqual(self.connection.execute("SELECT game_id FROM action_events").fetchall(), [(2,)])

    def test_missing_parent_is_rejected_when_test_enables_fk(self):
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.assert_rejected("games", game_values())
        self.assert_rejected("action_events", event_values())

    def test_game_index_is_unique_within_run_only(self):
        self.add_parents()
        self.assert_rejected("games", game_values(game_id=2))
        insert(self.connection, "benchmark_runs", run_values(run_id=2))
        insert(self.connection, "games", game_values(game_id=2, run_id=2))

    def test_duplicate_seed_and_fingerprint_are_allowed(self):
        self.add_parents()
        insert(self.connection, "games", game_values(game_id=2, game_index=1))
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM games").fetchone(), (2,))

    def test_action_natural_key_is_unique_within_game_only(self):
        self.add_parents()
        insert(self.connection, "action_events", event_values())
        self.assert_rejected("action_events", event_values())
        insert(self.connection, "games", game_values(game_id=2, game_index=1))
        insert(self.connection, "action_events", event_values(game_id=2))
        insert(self.connection, "action_events", event_values(action_index=1))

    def test_action_events_is_without_rowid_and_has_no_surrogate_key(self):
        ddl = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'action_events'"
        ).fetchone()[0]
        self.assertRegex(ddl.upper(), r"\bWITHOUT\s+ROWID\b")
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(action_events)")]
        self.assertNotIn("event_id", columns)
        self.assertNotIn("id", columns)
        with self.assertRaises(sqlite3.OperationalError):
            self.connection.execute("SELECT rowid FROM action_events")

    def test_only_indexes_required_by_frozen_keys_exist(self):
        expected = {
            "benchmark_runs": [],
            "games": [(1, "u", 0, ("run_id", "game_index"))],
            "action_events": [(1, "pk", 0, ("game_id", "action_index"))],
        }
        for table, wanted in expected.items():
            with self.subTest(table=table):
                indexes = []
                for _, name, unique, origin, partial in self.connection.execute(f"PRAGMA index_list({table})"):
                    columns = tuple(row[2] for row in self.connection.execute(f"PRAGMA index_info('{name}')"))
                    indexes.append((unique, origin, partial, columns))
                self.assertEqual(indexes, wanted)
        self.assertEqual(self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('view', 'trigger') "
            "OR (type = 'index' AND sql IS NOT NULL)"
        ).fetchall(), [])

    def test_all_required_columns_reject_null(self):
        fixtures = (
            ("benchmark_runs", RUN_COLUMNS, run_values),
            ("games", GAME_COLUMNS, game_values),
            ("action_events", EVENT_COLUMNS, event_values),
        )
        for table, columns, fixture in fixtures:
            for name, _, not_null, _ in columns:
                if not_null:
                    with self.subTest(table=table, column=name):
                        self.assert_rejected(table, fixture(**{name: None}))

    def test_run_structural_checks_reject_invalid_values(self):
        for overrides in (
            dict(width=0), dict(width=-1), dict(height=0), dict(height=-1),
            dict(num_mines=-1), dict(num_mines=81), dict(num_mines=82),
            dict(requested_games=0), dict(requested_games=-1),
            dict(processed_games=-1), dict(processed_games=4),
            dict(git_dirty=-1), dict(git_dirty=2),
        ):
            with self.subTest(overrides=overrides):
                self.assert_rejected("benchmark_runs", run_values(**overrides))

    def test_run_valid_range_boundaries(self):
        for index, overrides in enumerate((
            dict(width=1, height=1, num_mines=0),
            dict(num_mines=80, git_dirty=1),
            dict(processed_games=3),
        ), 1):
            with self.subTest(overrides=overrides):
                insert(self.connection, "benchmark_runs", run_values(run_id=index, **overrides))

    def test_run_status_domain_is_exact_stable_strings(self):
        for index, status in enumerate((
            "CREATED", "RUNNING", "COMPLETED", "ABORTED", "INTERRUPTED", "FAILED",
        ), 1):
            insert(self.connection, "benchmark_runs", run_values(
                run_id=index, run_status=status, processed_games=3,
            ))
        for status in ("created", "WIN", "UNKNOWN", "", 1):
            with self.subTest(status=status):
                self.assert_rejected("benchmark_runs", run_values(run_id=7, run_status=status))

    def test_completed_run_requires_all_requested_games_on_insert_and_update(self):
        self.assert_rejected("benchmark_runs", run_values(run_status="COMPLETED"))
        insert(self.connection, "benchmark_runs", run_values())
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE benchmark_runs SET run_status = 'COMPLETED'")
        self.connection.execute("UPDATE benchmark_runs SET run_status = 'COMPLETED', processed_games = 3")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE benchmark_runs SET processed_games = 2")

    def test_game_nonnegative_ranges(self):
        for name in (
            "game_index", "seed", "first_click_x", "first_click_y",
            "local_deterministic_count",
            "global_certainty_count", "probability_guess_count", "board_3bv",
            "board_ops", "compute_time_total_ns", "compute_time_max_ns",
        ):
            with self.subTest(column=name):
                self.assert_rejected("games", game_values(**{name: -1}))
        for overrides in (
            dict(open_count=-1, flag_count=2),
            dict(flag_count=-1, open_count=2),
            dict(chord_count=-1, open_count=2),
        ):
            with self.subTest(overrides=overrides):
                self.assert_rejected("games", game_values(**overrides))
        for value in (0, -1):
            with self.subTest(total_actions=value):
                self.assert_rejected("games", game_values(total_actions=value, open_count=value))

    def test_game_physical_action_counts_must_sum_to_total(self):
        self.assert_rejected("games", game_values(total_actions=2))
        self.assert_rejected("games", game_values(open_count=2))
        insert(self.connection, "games", game_values(
            total_actions=3, open_count=1, flag_count=1, chord_count=1,
        ))

    def test_game_result_domain(self):
        for value in (-1, 0, 3, "WIN", "LOSS"):
            with self.subTest(value=value):
                self.assert_rejected("games", game_values(result=value))
        for index, value in enumerate((1, 2), 1):
            insert(self.connection, "games", game_values(game_id=index, game_index=index, result=value))

    def test_guess_summary_relationship_and_range(self):
        for overrides in (
            dict(had_probability_guess=-1), dict(had_probability_guess=2),
            dict(had_probability_guess=1), dict(first_guess_action_index=0),
            dict(probability_guess_count=1),
            dict(probability_guess_count=1, first_guess_action_index=0),
            dict(probability_guess_count=1, had_probability_guess=1),
            dict(probability_guess_count=1, had_probability_guess=1, first_guess_action_index=-1),
            dict(probability_guess_count=1, had_probability_guess=1, first_guess_action_index=1),
        ):
            with self.subTest(overrides=overrides):
                self.assert_rejected("games", game_values(**overrides))

    def test_guess_at_index_zero_and_last_action_are_generic_valid_values(self):
        for index, first_guess in enumerate((0, 2), 1):
            insert(self.connection, "games", game_values(
                game_id=index, game_index=index, total_actions=3, open_count=3,
                probability_guess_count=1, had_probability_guess=1,
                first_guess_action_index=first_guess,
            ))

    def test_fingerprint_must_be_exactly_64_lowercase_ascii_hex_characters(self):
        for value in (
            "", "0" * 63, "0" * 65, "A" * 64, "ａ" * 64,
            "０" * 64, "0" * 63 + "\n", "0" * 64 + "\0garbage",
            "0" * 32 + "\0" + "0" * 31, b"0" * 64,
        ):
            with self.subTest(value=value):
                self.assert_rejected("games", game_values(board_fingerprint=value))
        for position in range(64):
            value = "a" * position + "g" + "a" * (63 - position)
            with self.subTest(position=position):
                self.assert_rejected("games", game_values(board_fingerprint=value))
        insert(self.connection, "games", game_values())

    def test_fingerprint_shape_check_supports_caller_utf16_database_encoding(self):
        connection = self.new_connection()
        connection.execute("PRAGMA encoding = 'UTF-16'")
        schema.initialize_schema(connection)
        insert(connection, "benchmark_runs", run_values())
        insert(connection, "games", game_values())
        self.assertEqual(connection.execute(
            "SELECT board_fingerprint FROM games"
        ).fetchone(), ("0123456789abcdef" * 4,))

    def test_event_structural_checks_reject_invalid_values(self):
        for overrides in (
            dict(action_index=-1), dict(selection_candidate_count=0),
            dict(selection_candidate_count=-1), dict(decision_compute_ns=-1),
            dict(x=-1), dict(y=-1), dict(safe_cells_opened_delta=-1),
            dict(explicit_flag_delta=-2), dict(explicit_flag_delta=2),
        ):
            with self.subTest(overrides=overrides):
                self.assert_rejected("action_events", event_values(**overrides))

    def test_event_enum_domains_reject_values_outside_frozen_mappings(self):
        for name in ("inference_category", "action_type", "status_after"):
            for value in (-1, 0, 4, "OPEN", "PLAYING", "LOCAL_DETERMINISTIC"):
                with self.subTest(column=name, value=value):
                    self.assert_rejected("action_events", event_values(**{name: value}))

    def test_all_event_enum_values_and_delta_boundaries_are_accepted(self):
        for index, value in enumerate((1, 2, 3)):
            insert(self.connection, "action_events", event_values(
                action_index=index, inference_category=value, action_type=value,
                status_after=value, selection_candidate_count=1, decision_compute_ns=0,
                explicit_flag_delta=index - 1,
            ))

    def test_game_inference_totals_are_not_fixed_to_stage2_action_count_minus_one(self):
        for index, analyzed in enumerate((0, 3), 1):
            insert(self.connection, "games", game_values(
                game_id=index, game_index=index, total_actions=3, open_count=3,
                local_deterministic_count=analyzed,
            ))

    def test_action_zero_null_pattern_and_selector_semantics_are_not_sql_checks(self):
        # Generic DB facts deliberately differ from the Stage 2 policy adapter.
        insert(self.connection, "action_events", event_values(
            action_index=0, inference_category=3, action_type=3,
            selection_candidate_count=1, target_mine_probability="2/3",
            minimum_available_mine_probability="1/3", decision_compute_ns=0,
        ))
        insert(self.connection, "action_events", event_values(
            action_index=1, inference_category=1, action_type=2,
            target_mine_probability="1/3", minimum_available_mine_probability="2/9",
        ))
        insert(self.connection, "action_events", event_values(action_index=2))

    def test_event_continuity_terminal_order_and_raw_summary_equality_are_not_sql_checks(self):
        self.add_parents()
        insert(self.connection, "action_events", event_values(action_index=4, status_after=2))
        insert(self.connection, "action_events", event_values(action_index=7, status_after=1))
        self.assertEqual(self.connection.execute("SELECT total_actions FROM games").fetchone(), (1,))
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM action_events").fetchone(), (2,))

    def test_literal_persistence_constants(self):
        for name, value in FROZEN_CONSTANTS.items():
            with self.subTest(name=name):
                actual = getattr(schema, name)
                self.assertEqual(actual, value)
                self.assertIs(type(actual), type(value))

    def test_persistence_constants_do_not_depend_on_implementation_enums(self):
        # Loading with the implementation modules unavailable proves their enum
        # values/order cannot determine these persisted numbers and strings.
        with patch.dict(sys.modules, {"core_engine": None, "telemetry_model": None}):
            isolated = runpy.run_path(schema.__file__)
        self.assertEqual({name: isolated[name] for name in FROZEN_CONSTANTS}, FROZEN_CONSTANTS)


if __name__ == "__main__":
    unittest.main()
