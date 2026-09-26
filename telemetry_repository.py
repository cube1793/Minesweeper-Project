"""Concrete SQLite persistence for finalized generic telemetry.

Use connect_database and close the returned connection when finished. Connections
use SQLite autocommit (isolation_level=None); each write operation below owns an
explicit, short BEGIN/COMMIT/ROLLBACK transaction. Do not wrap these operations
in a caller transaction or change the connection's operating mode.

Canonical rational TEXT is opaque to SQLite numeric operations. Decode to
Fraction before mathematical comparison or arithmetic.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

from core_engine import Action, GameStatus
from telemetry_model import ActionEvent, GameRecord, InferenceCategory
import telemetry_schema as schema


_CANONICAL_PROBABILITY = re.compile(r"(0|[1-9][0-9]*)/([1-9][0-9]*)")
_UTC_TIMESTAMP = re.compile(
    r"(?:[0-9]{4}-?[0-9]{2}-?[0-9]{2}|[0-9]{4}-?W[0-9]{2}(?:-?[1-7])?)"
    r"[T ][0-9:.,]+(?:Z|[+-][0-9:.,]+)"
)


def encode_probability(value: Fraction | None) -> str | None:
    """Encode an exact probability as reduced ``n/d`` TEXT, or SQL NULL.

    Decimal conversion respects the runtime's integer-string safety limit.
    """
    if value is None:
        return None
    if not isinstance(value, Fraction):
        raise TypeError("Probability must be a Fraction or None.")
    if not 0 <= value <= 1:
        raise ValueError("Probability must be in [0, 1].")
    return f"{value.numerator}/{value.denominator}"


def decode_probability(value: str | None) -> Fraction | None:
    """Decode only canonical ASCII ``n/d`` TEXT representing a value in [0, 1]."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Stored probability must be a string or None.")
    match = _CANONICAL_PROBABILITY.fullmatch(value)
    if match is None:
        raise ValueError("Stored probability must use canonical ASCII n/d syntax.")
    probability = Fraction(int(match[1]), int(match[2]))
    if encode_probability(probability) != value:
        raise ValueError("Stored probability must be reduced canonical n/d TEXT.")
    return probability


_ACTION_TO_DB = {
    Action.OPEN: schema.ACTION_OPEN,
    Action.FLAG: schema.ACTION_FLAG,
    Action.CHORD: schema.ACTION_CHORD,
}
_INFERENCE_TO_DB = {
    InferenceCategory.LOCAL_DETERMINISTIC: schema.INFERENCE_LOCAL_DETERMINISTIC,
    InferenceCategory.GLOBAL_CERTAINTY: schema.INFERENCE_GLOBAL_CERTAINTY,
    InferenceCategory.PROBABILITY_GUESS: schema.INFERENCE_PROBABILITY_GUESS,
}
_STATUS_TO_DB = {
    GameStatus.PLAYING: schema.STATUS_AFTER_PLAYING,
    GameStatus.WON: schema.STATUS_AFTER_WON,
    GameStatus.LOST: schema.STATUS_AFTER_LOST,
}
_RESULT_TO_DB = {
    "WIN": schema.GAME_RESULT_WIN,
    "LOSS": schema.GAME_RESULT_LOSS,
}
_RUN_STATUSES = frozenset((
    schema.RUN_STATUS_CREATED, schema.RUN_STATUS_RUNNING,
    schema.RUN_STATUS_COMPLETED, schema.RUN_STATUS_ABORTED,
    schema.RUN_STATUS_INTERRUPTED, schema.RUN_STATUS_FAILED,
))
_UNCHANGED = object()


def connect_database(path: str | Path) -> sqlite3.Connection:
    """Open a file database, verify FK/WAL/FULL, and initialize/check its schema.

    The caller owns closing the connection. Failed setup closes it here.
    In-memory databases are rejected because they cannot establish WAL mode.
    Schema initialization occurs only on this fresh, transaction-free connection.
    """
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        for setting, requested, expected in (
            ("foreign_keys", "ON", 1),
            ("journal_mode", "WAL", "wal"),
            ("synchronous", "FULL", 2),
        ):
            connection.execute(f"PRAGMA {setting} = {requested}")
            effective = connection.execute(f"PRAGMA {setting}").fetchone()[0]
            if effective != expected:
                raise RuntimeError(
                    f"Required SQLite {setting}={requested} was not established: "
                    f"effective value is {effective!r}."
                )
        schema.initialize_schema(connection)
        connection.row_factory = sqlite3.Row
    except BaseException:
        connection.close()
        raise
    return connection


@contextmanager
def _transaction(connection: sqlite3.Connection):
    """Own one transaction without committing or rolling back caller work."""
    if connection.isolation_level is not None or connection.in_transaction:
        raise RuntimeError("Repository writes require an idle autocommit connection.")
    connection.execute("BEGIN")
    try:
        yield
        connection.execute("COMMIT")
    except BaseException as error:
        if connection.in_transaction:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error as rollback_error:
                # Do not let a failed cleanup hide the original persistence error
                # or leave a connection with partial work available for reuse.
                error.add_note(f"SQLite rollback failed: {rollback_error}")
                connection.close()
        raise


def _require_run_status(run_status: str) -> None:
    if not isinstance(run_status, str) or run_status not in _RUN_STATUSES:
        raise ValueError(f"Unsupported run_status: {run_status!r}.")


def _require_integer(name: str, value: int) -> None:
    if type(value) is not int:
        raise ValueError(f"{name} must be an int, excluding bool.")


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a str.")


def _require_utc_timestamp(name: str, value: str) -> None:
    """Validate supplied ISO-8601 UTC text without formatting or clock ownership."""
    # Keep calendar/week dates and basic/extended UTC forms, but reject the
    # arbitrary Unicode date/time separators accepted by fromisoformat().
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError(f"{name} must be UTC ISO-8601 text.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be UTC ISO-8601 text.") from error
    if parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must include a UTC offset.")


def create_run(
    connection: sqlite3.Connection, *, telemetry_schema_version: int,
    created_at: str, git_commit: str, git_dirty: bool,
    solver_stage: str, solver_policy: str, solver_config_snapshot: object,
    width: int, height: int, num_mines: int, first_click_policy: str,
    board_generator_version: str, benchmark_set_id: str, requested_games: int,
    environment_snapshot: object, started_at: str | None = None,
    finished_at: str | None = None, run_status: str = schema.RUN_STATUS_CREATED,
    app_version: str | None = None, difficulty_name: str | None = None,
    failure_code: str | None = None,
) -> int:
    """Insert prepared run metadata and return its SQLite-generated run_id.

    A new run has no committed games, so processed_games starts at zero.
    Lifecycle choices and provenance collection belong to the caller. Snapshot
    inputs are JSON values, serialized with sorted keys and compact separators.
    Timestamp text is preserved after checking its ISO syntax and UTC offset.
    """
    for name, value in (
        ("telemetry_schema_version", telemetry_schema_version),
        ("width", width), ("height", height), ("num_mines", num_mines),
        ("requested_games", requested_games),
    ):
        _require_integer(name, value)
    for name, value in (
        ("git_commit", git_commit), ("solver_stage", solver_stage),
        ("solver_policy", solver_policy), ("first_click_policy", first_click_policy),
        ("board_generator_version", board_generator_version),
        ("benchmark_set_id", benchmark_set_id),
    ):
        _require_text(name, value)
    for name, value in (
        ("app_version", app_version), ("difficulty_name", difficulty_name),
        ("failure_code", failure_code),
    ):
        if value is not None:
            _require_text(name, value)
    _require_run_status(run_status)
    _require_utc_timestamp("created_at", created_at)
    for name, value in (("started_at", started_at), ("finished_at", finished_at)):
        if value is not None:
            _require_utc_timestamp(name, value)
    if not isinstance(git_dirty, bool):
        raise ValueError("git_dirty must be a bool.")
    config_json = json.dumps(
        solver_config_snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    environment_json = json.dumps(
        environment_snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    with _transaction(connection):
        cursor = connection.execute(
            """
            INSERT INTO benchmark_runs (
                telemetry_schema_version, created_at, started_at, finished_at,
                run_status, git_commit, git_dirty, app_version,
                solver_stage, solver_policy, solver_config_snapshot,
                width, height, num_mines, difficulty_name,
                first_click_policy, board_generator_version, benchmark_set_id,
                requested_games, processed_games, environment_snapshot, failure_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                telemetry_schema_version, created_at, started_at, finished_at,
                run_status, git_commit, int(git_dirty), app_version,
                solver_stage, solver_policy, config_json,
                width, height, num_mines, difficulty_name,
                first_click_policy, board_generator_version, benchmark_set_id,
                requested_games, environment_json, failure_code,
            ),
        )
        run_id = cursor.lastrowid
    return run_id


def update_run_status(
    connection: sqlite3.Connection, run_id: int, run_status: str, *,
    started_at: str | None = _UNCHANGED, finished_at: str | None = _UNCHANGED,
    failure_code: str | None = _UNCHANGED,
) -> None:
    """Write a caller-selected status and metadata in a separate transaction.

    Omitted metadata is preserved; explicit None stores SQL NULL. No transition
    policy or prefix validation is applied. SQLite enforces COMPLETED's processed
    count requirement. A missing run raises ValueError rather than a silent no-op.
    """
    _require_integer("run_id", run_id)
    _require_run_status(run_status)
    assignments = ["run_status = ?"]
    parameters = [run_status]
    for name, value in (
        ("started_at", started_at), ("finished_at", finished_at),
        ("failure_code", failure_code),
    ):
        if value is _UNCHANGED:
            continue
        if value is not None:
            if name == "failure_code":
                _require_text(name, value)
            else:
                _require_utc_timestamp(name, value)
        assignments.append(f"{name} = ?")
        parameters.append(value)
    parameters.append(run_id)
    with _transaction(connection):
        cursor = connection.execute(
            f"UPDATE benchmark_runs SET {', '.join(assignments)} WHERE run_id = ?",
            parameters,
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Unknown run_id: {run_id!r}.")


def fetch_run(connection: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    """Fetch stored run metadata/progress, or None; no read transaction is held."""
    _require_integer("run_id", run_id)
    return connection.execute(
        "SELECT * FROM benchmark_runs WHERE run_id = ?", (run_id,),
    ).fetchone()


def fetch_game_indices(connection: sqlite3.Connection, run_id: int) -> tuple[int, ...]:
    """Return stored game indices in order, without applying coverage policy.

    Missing runs and runs without games both return an empty tuple. The query
    uses the supplied connection and does not open or finish a transaction.
    """
    _require_integer("run_id", run_id)
    return tuple(row[0] for row in connection.execute(
        "SELECT game_index FROM games WHERE run_id = ? ORDER BY game_index", (run_id,),
    ).fetchall())


def _encode_game(record: GameRecord) -> tuple:
    if not isinstance(record.result, str) or record.result not in _RESULT_TO_DB:
        raise ValueError(f"Unsupported game result: {record.result!r}.")
    return (
        record.game_index, record.seed, record.board_fingerprint,
        record.first_click_x, record.first_click_y, _RESULT_TO_DB[record.result],
        record.total_actions, record.open_count, record.flag_count, record.chord_count,
        record.local_deterministic_count, record.global_certainty_count,
        record.probability_guess_count, int(record.had_probability_guess),
        record.first_guess_action_index, record.board_3bv, record.board_ops,
        record.compute_time_total_ns, record.compute_time_max_ns,
    )


def _encode_event(event: ActionEvent) -> tuple:
    # IntEnum members compare equal to plain ints and other IntEnums. Check
    # their domain types before looking up the explicit persistence mappings.
    if not isinstance(event.action_type, Action):
        raise ValueError(f"Unsupported action_type: {event.action_type!r}.")
    if not isinstance(event.status_after, GameStatus):
        raise ValueError(f"Unsupported status_after: {event.status_after!r}.")
    if event.inference_category is not None and not isinstance(
        event.inference_category, InferenceCategory,
    ):
        raise ValueError(f"Unsupported inference_category: {event.inference_category!r}.")
    try:
        action_type = _ACTION_TO_DB[event.action_type]
        status_after = _STATUS_TO_DB[event.status_after]
        inference_category = (
            None if event.inference_category is None
            else _INFERENCE_TO_DB[event.inference_category]
        )
    except KeyError as error:
        raise ValueError(f"Unsupported telemetry enum member: {error.args[0]!r}.") from error
    return (
        event.action_index, inference_category, event.selection_candidate_count,
        encode_probability(event.target_mine_probability),
        encode_probability(event.minimum_available_mine_probability),
        event.decision_compute_ns, action_type, event.x, event.y, status_after,
        event.safe_cells_opened_delta, event.explicit_flag_delta,
    )


def persist_completed_game(
    connection: sqlite3.Connection, run_id: int, game_record: GameRecord,
    events: tuple[ActionEvent, ...],
) -> int:
    """Atomically insert a finalized game, its events, and one progress increment.

    The Collector owns terminal/sequence/summary consistency. Require its complete
    immutable event snapshot, but do not rederive summaries or solver semantics.
    Encode before BEGIN so the transaction only covers database work. Any failure,
    including COMMIT failure, rolls back this game without touching earlier games.
    The run status is never changed here. Return the generated game_id.
    """
    _require_integer("run_id", run_id)
    if not isinstance(game_record, GameRecord):
        raise TypeError("game_record must be a GameRecord.")
    if not isinstance(events, tuple) or any(not isinstance(event, ActionEvent) for event in events):
        raise TypeError("events must be a tuple of ActionEvent instances.")
    if len(events) != game_record.total_actions:
        raise ValueError("events must contain game_record.total_actions entries.")
    game_values = _encode_game(game_record)
    event_values = tuple(_encode_event(event) for event in events)
    with _transaction(connection):
        cursor = connection.execute(
            """
            INSERT INTO games (
                run_id, game_index, seed, board_fingerprint,
                first_click_x, first_click_y, result,
                total_actions, open_count, flag_count, chord_count,
                local_deterministic_count, global_certainty_count,
                probability_guess_count, had_probability_guess, first_guess_action_index,
                board_3bv, board_ops, compute_time_total_ns, compute_time_max_ns
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, *game_values),
        )
        game_id = cursor.lastrowid
        connection.executemany(
            """
            INSERT INTO action_events (
                game_id, action_index, inference_category, selection_candidate_count,
                target_mine_probability, minimum_available_mine_probability,
                decision_compute_ns, action_type, x, y, status_after,
                safe_cells_opened_delta, explicit_flag_delta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ((game_id, *values) for values in event_values),
        )
        cursor = connection.execute(
            "UPDATE benchmark_runs SET processed_games = processed_games + 1 WHERE run_id = ?",
            (run_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Unknown run_id: {run_id!r}.")
    return game_id
