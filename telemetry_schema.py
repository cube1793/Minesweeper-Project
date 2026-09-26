"""SQLite V1 DDL and stable persistence constants for generic telemetry.

Physical schema versions are independent of benchmark_runs.telemetry_schema_version.
Connection operating mode and model encoding belong to telemetry_repository.
"""

import sqlite3


PHYSICAL_SCHEMA_VERSION = 1

# These database meanings are literals, independent of Engine/model enum values.
ACTION_OPEN = 1
ACTION_FLAG = 2
ACTION_CHORD = 3

INFERENCE_LOCAL_DETERMINISTIC = 1
INFERENCE_GLOBAL_CERTAINTY = 2
INFERENCE_PROBABILITY_GUESS = 3

STATUS_AFTER_PLAYING = 1
STATUS_AFTER_WON = 2
STATUS_AFTER_LOST = 3

GAME_RESULT_WIN = 1
GAME_RESULT_LOSS = 2

RUN_STATUS_CREATED = "CREATED"
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_COMPLETED = "COMPLETED"
RUN_STATUS_ABORTED = "ABORTED"
RUN_STATUS_INTERRUPTED = "INTERRUPTED"
RUN_STATUS_FAILED = "FAILED"

FIRST_CLICK_FIXED_0_0 = "FIRST_CLICK_FIXED_0_0"
BOARD_GENERATOR_V1 = "V1"


_V1_DDL = (
    f"""
    CREATE TABLE benchmark_runs (
        run_id INTEGER PRIMARY KEY,
        telemetry_schema_version INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT NULL,
        finished_at TEXT NULL,
        run_status TEXT NOT NULL CHECK (run_status IN (
            '{RUN_STATUS_CREATED}', '{RUN_STATUS_RUNNING}', '{RUN_STATUS_COMPLETED}',
            '{RUN_STATUS_ABORTED}', '{RUN_STATUS_INTERRUPTED}', '{RUN_STATUS_FAILED}'
        )),
        git_commit TEXT NOT NULL,
        git_dirty INTEGER NOT NULL CHECK (git_dirty IN (0, 1)),
        app_version TEXT NULL,
        solver_stage TEXT NOT NULL,
        solver_policy TEXT NOT NULL,
        solver_config_snapshot TEXT NOT NULL,
        width INTEGER NOT NULL CHECK (width > 0),
        height INTEGER NOT NULL CHECK (height > 0),
        num_mines INTEGER NOT NULL CHECK (num_mines >= 0 AND num_mines < width * height),
        difficulty_name TEXT NULL,
        first_click_policy TEXT NOT NULL,
        board_generator_version TEXT NOT NULL,
        benchmark_set_id TEXT NOT NULL,
        requested_games INTEGER NOT NULL CHECK (requested_games > 0),
        processed_games INTEGER NOT NULL DEFAULT 0
            CHECK (processed_games >= 0 AND processed_games <= requested_games),
        environment_snapshot TEXT NOT NULL,
        failure_code TEXT NULL,
        CHECK (run_status != '{RUN_STATUS_COMPLETED}' OR processed_games = requested_games)
    )
    """,
    f"""
    CREATE TABLE games (
        game_id INTEGER PRIMARY KEY,
        run_id INTEGER NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
        game_index INTEGER NOT NULL CHECK (game_index >= 0),
        seed INTEGER NOT NULL CHECK (seed >= 0),
        board_fingerprint TEXT NOT NULL CHECK (
            typeof(board_fingerprint) = 'text'
            AND length(board_fingerprint) = 64
            AND instr(board_fingerprint, char(0)) = 0
            AND board_fingerprint NOT GLOB '*[^0-9a-f]*'
        ),
        first_click_x INTEGER NOT NULL CHECK (first_click_x >= 0),
        first_click_y INTEGER NOT NULL CHECK (first_click_y >= 0),
        result INTEGER NOT NULL CHECK (result IN ({GAME_RESULT_WIN}, {GAME_RESULT_LOSS})),
        total_actions INTEGER NOT NULL CHECK (total_actions > 0),
        open_count INTEGER NOT NULL CHECK (open_count >= 0),
        flag_count INTEGER NOT NULL CHECK (flag_count >= 0),
        chord_count INTEGER NOT NULL CHECK (chord_count >= 0),
        local_deterministic_count INTEGER NOT NULL CHECK (local_deterministic_count >= 0),
        global_certainty_count INTEGER NOT NULL CHECK (global_certainty_count >= 0),
        probability_guess_count INTEGER NOT NULL CHECK (probability_guess_count >= 0),
        had_probability_guess INTEGER NOT NULL CHECK (had_probability_guess IN (0, 1)),
        first_guess_action_index INTEGER NULL CHECK (
            first_guess_action_index IS NULL
            OR (first_guess_action_index >= 0 AND first_guess_action_index < total_actions)
        ),
        board_3bv INTEGER NOT NULL CHECK (board_3bv >= 0),
        board_ops INTEGER NOT NULL CHECK (board_ops >= 0),
        compute_time_total_ns INTEGER NOT NULL CHECK (compute_time_total_ns >= 0),
        compute_time_max_ns INTEGER NULL
            CHECK (compute_time_max_ns IS NULL OR compute_time_max_ns >= 0),
        UNIQUE (run_id, game_index),
        CHECK (total_actions = open_count + flag_count + chord_count),
        CHECK (
            (probability_guess_count = 0 AND had_probability_guess = 0
                AND first_guess_action_index IS NULL)
            OR (probability_guess_count > 0 AND had_probability_guess = 1
                AND first_guess_action_index IS NOT NULL)
        )
    )
    """,
    f"""
    CREATE TABLE action_events (
        game_id INTEGER NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
        action_index INTEGER NOT NULL CHECK (action_index >= 0),
        inference_category INTEGER NULL CHECK (
            inference_category IS NULL OR inference_category IN (
                {INFERENCE_LOCAL_DETERMINISTIC}, {INFERENCE_GLOBAL_CERTAINTY},
                {INFERENCE_PROBABILITY_GUESS}
            )
        ),
        selection_candidate_count INTEGER NULL
            CHECK (selection_candidate_count IS NULL OR selection_candidate_count >= 1),
        target_mine_probability TEXT NULL,
        minimum_available_mine_probability TEXT NULL,
        decision_compute_ns INTEGER NULL
            CHECK (decision_compute_ns IS NULL OR decision_compute_ns >= 0),
        action_type INTEGER NOT NULL
            CHECK (action_type IN ({ACTION_OPEN}, {ACTION_FLAG}, {ACTION_CHORD})),
        x INTEGER NOT NULL CHECK (x >= 0),
        y INTEGER NOT NULL CHECK (y >= 0),
        status_after INTEGER NOT NULL
            CHECK (status_after IN ({STATUS_AFTER_PLAYING}, {STATUS_AFTER_WON}, {STATUS_AFTER_LOST})),
        safe_cells_opened_delta INTEGER NOT NULL CHECK (safe_cells_opened_delta >= 0),
        explicit_flag_delta INTEGER NOT NULL CHECK (explicit_flag_delta IN (-1, 0, 1)),
        PRIMARY KEY (game_id, action_index)
    ) WITHOUT ROWID
    """,
)


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Install V1 for user_version 0, accept V1, and reject other versions.

    The caller owns the connection and its operating mode. Installation uses
    a local savepoint so DDL and user_version change together without committing
    any pending caller transaction. Existing conflicting tables fail explicitly;
    this boundary does not repair schemas or migrate nonzero versions.
    """
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == PHYSICAL_SCHEMA_VERSION:
        return
    if version != 0:
        raise ValueError(f"Unsupported SQLite physical schema version: {version}.")

    connection.execute("SAVEPOINT telemetry_schema_v1")
    try:
        for statement in _V1_DDL:
            connection.execute(statement)
        connection.execute(f"PRAGMA user_version = {PHYSICAL_SCHEMA_VERSION}")
    except BaseException:
        connection.execute("ROLLBACK TO SAVEPOINT telemetry_schema_v1")
        connection.execute("RELEASE SAVEPOINT telemetry_schema_v1")
        raise
    connection.execute("RELEASE SAVEPOINT telemetry_schema_v1")
