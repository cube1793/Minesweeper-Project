"""Exact post-hoc Model C evaluation of complete, ordered physical inputs.

This is structural validation, not action replay or solver validation. The
caller owns database connections and must supply stable artifacts/snapshots;
reads never configure a connection or open a write transaction. Historical
Stage-2 metadata remains unchanged: its modeled time is an explicit evaluation
under the same authenticated frozen model declared by Stage 3.
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import InitVar, dataclass, field
from pathlib import Path

import stage3_physical as physical
import telemetry_schema as schema


class ModeledTimeValidationError(ValueError):
    """The model, run identity, or complete physical input stream is invalid."""


@dataclass(frozen=True)
class ModelCEvaluation:
    """Explicit frozen evaluation configuration authenticated at construction.

    A path may locate a preserved copy, but its exact bytes and stored integer
    table must authenticate. No caller-supplied identity string/table is used.
    Every field is immutable and excluded from constructor/replace overrides.
    """

    profile_path: InitVar[str | Path | None] = None
    table: physical.TimingTable = field(init=False, repr=False)
    initial_cursor: tuple[int, int] = field(default=(0, 0), init=False)
    physical_model_id: str = field(default="overlap_floor_log2_distance_v1", init=False)
    physical_profile_version: int = field(default=1, init=False)
    physical_profile_sha256: str = field(default=physical.PROFILE_SHA256, init=False)
    timing_table_sha256: str = field(default=physical.TABLE_SHA256, init=False)
    timing_unit: str = field(default="us", init=False)

    def __post_init__(self, profile_path: str | Path | None) -> None:
        try:
            table = physical.load_timing_table(
                physical.PROFILE_PATH if profile_path is None else profile_path,
            )
        except (OSError, ValueError, TypeError) as exc:
            raise ModeledTimeValidationError(f"Frozen Model C authentication failed: {exc}") from exc
        object.__setattr__(self, "table", table)


def authenticate_model_c(profile_path: str | Path | None = None) -> ModelCEvaluation:
    """Authenticate actual preserved profile bytes and table exactly once."""
    return ModelCEvaluation(profile_path)


@dataclass(frozen=True)
class ModeledTimeRun:
    run_id: int
    width: int
    height: int
    solver_stage: str


@dataclass(frozen=True)
class ModeledGameCost:
    game_index: int
    result: str
    total_modeled_us: int
    ordered_actions: tuple[tuple[int, int, int], ...]


def _require_evaluation(evaluation: ModelCEvaluation) -> None:
    if type(evaluation) is not ModelCEvaluation:
        raise ModeledTimeValidationError("An authenticated explicit ModelCEvaluation is required.")


def _integer(name: str, value: int, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ModeledTimeValidationError(f"{name} must be an integer >= {minimum}, excluding bool.")


def _stage3_config(evaluation: ModelCEvaluation) -> dict:
    return {
        "initial_open": [0, 0], "initial_cursor": list(evaluation.initial_cursor),
        "algorithm_spec_version": 1,
        "algorithm_spec_sha256": "6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",
        "physical_model_id": evaluation.physical_model_id,
        "physical_profile_version": evaluation.physical_profile_version,
        "physical_profile_sha256": evaluation.physical_profile_sha256,
        "timing_table_sha256": evaluation.timing_table_sha256,
        "timing_unit": evaluation.timing_unit,
    }


def validate_run_identity(
    connection: sqlite3.Connection, run_id: int, *, solver_stage: str,
    evaluation: ModelCEvaluation,
) -> ModeledTimeRun:
    """Validate canonical Stage-2 post-hoc or Stage-3 declared-model identity.

    This does not grant official lifecycle eligibility; board pairing/coverage
    owns that separate check. Canonical serialized configs preserve bool/int
    distinctions and reject missing, extra or changed fields.
    """
    _require_evaluation(evaluation)
    _integer("run_id", run_id, 1)
    if solver_stage == schema.SOLVER_STAGE_STAGE_2:
        semantic_version = schema.TELEMETRY_SCHEMA_VERSION
        policy = schema.SOLVER_POLICY_SIMPLE_MINIMUM_RISK
        config = {"accept_guesses": True, "initial_open": [0, 0]}
    elif solver_stage == schema.SOLVER_STAGE_STAGE_3:
        semantic_version = schema.TELEMETRY_SCHEMA_VERSION_STAGE_3
        policy = schema.SOLVER_POLICY_E_FIRST_FIRST_REVEAL_V1
        config = _stage3_config(evaluation)
    else:
        raise ModeledTimeValidationError("Unsupported modeled-time solver role.")
    expected = {
        "telemetry_schema_version": semantic_version, "solver_stage": solver_stage,
        "solver_policy": policy, "benchmark_set_id": "EXPERT_GENERAL_V1",
        "width": 30, "height": 16, "num_mines": 99,
        "first_click_policy": schema.FIRST_CLICK_FIXED_0_0,
        "board_generator_version": schema.BOARD_GENERATOR_V1,
        "solver_config_snapshot": json.dumps(config, sort_keys=True, separators=(",", ":")),
    }
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        row = cursor.execute(
            "SELECT telemetry_schema_version, solver_stage, solver_policy, benchmark_set_id, "
            "width, height, num_mines, first_click_policy, board_generator_version, "
            "solver_config_snapshot FROM benchmark_runs WHERE run_id = ?", (run_id,),
        ).fetchone()
    if row is None:
        raise ModeledTimeValidationError(f"Unknown run_id: {run_id}.")
    for name, value in expected.items():
        if type(row[name]) is not type(value) or row[name] != value:
            raise ModeledTimeValidationError(f"Incompatible modeled-time run identity: {name}.")
    return ModeledTimeRun(run_id, row["width"], row["height"], solver_stage)


def _reconstruct(
    *, game_index: int, result: str, total_actions: int,
    game_first_click: tuple[int, int], rows: tuple[tuple[int, int, int, int, int], ...],
    width: int, height: int, first_click: tuple[int, int], evaluation: ModelCEvaluation,
) -> ModeledGameCost:
    _require_evaluation(evaluation)
    _integer("game_index", game_index)
    _integer("width", width, 1)
    _integer("height", height, 1)
    if width > 30 or height > 16:
        raise ModeledTimeValidationError("Board dimensions exceed the frozen timing table.")
    if type(result) is not str or result not in ("WIN", "LOSS"):
        raise ModeledTimeValidationError("A completed supported WIN or LOSS result is required.")
    _integer("total_actions", total_actions, 1)
    if len(rows) != total_actions:
        raise ModeledTimeValidationError("Complete action row count must equal total_actions.")
    for label, coordinate in (("run first click", first_click), ("game first click", game_first_click)):
        if not isinstance(coordinate, (tuple, list)) or len(coordinate) != 2:
            raise ModeledTimeValidationError(f"Invalid {label} coordinate.")
        for value in coordinate:
            _integer(label, value)
        if tuple(coordinate) != (0, 0):
            raise ModeledTimeValidationError(f"Canonical {label} must be (0, 0).")
    expected_terminal = schema.STATUS_AFTER_WON if result == "WIN" else schema.STATUS_AFTER_LOST
    cursor = evaluation.initial_cursor
    total = 0
    actions = []
    for expected_index, (index, action, x, y, status) in enumerate(rows):
        _integer("action_index", index)
        if index != expected_index:
            raise ModeledTimeValidationError("Action indices must be exactly 0..total_actions-1.")
        if type(action) is not int or action not in (schema.ACTION_OPEN, schema.ACTION_FLAG, schema.ACTION_CHORD):
            raise ModeledTimeValidationError("Unsupported physical action type.")
        if type(status) is not int or status not in (
            schema.STATUS_AFTER_PLAYING, schema.STATUS_AFTER_WON, schema.STATUS_AFTER_LOST,
        ):
            raise ModeledTimeValidationError("Unsupported action status.")
        _integer("x", x)
        _integer("y", y)
        if x >= width or y >= height:
            raise ModeledTimeValidationError("Action target lies outside the run board.")
        if expected_index == 0 and (action, x, y) != (schema.ACTION_OPEN, 0, 0):
            raise ModeledTimeValidationError("First physical input must be OPEN (0, 0).")
        expected_status = expected_terminal if expected_index == total_actions - 1 else schema.STATUS_AFTER_PLAYING
        if status != expected_status:
            raise ModeledTimeValidationError("Early terminal or final result/status mismatch.")
        total += evaluation.table[abs(x - cursor[0])][abs(y - cursor[1])]
        cursor = (x, y)
        actions.append((action, x, y))
    return ModeledGameCost(game_index, result, total, tuple(actions))


def reconstruct_game(
    record, events, *, width: int, height: int, evaluation: ModelCEvaluation,
    first_click: tuple[int, int] = (0, 0),
) -> ModeledGameCost:
    """Validate immutable GameRecord/ActionEvents and sum actual target costs.

    Neither trace-provided costs nor automatic Engine effects are inputs.
    Board dimensions may be smaller for deterministic development fixtures.
    """
    # Public enum types only, loaded at the in-memory boundary. Persisted
    # reconstruction neither imports Engine here nor executes/replays actions.
    from core_engine import Action, GameStatus

    action_map = {"OPEN": schema.ACTION_OPEN, "FLAG": schema.ACTION_FLAG, "CHORD": schema.ACTION_CHORD}
    status_map = {"PLAYING": schema.STATUS_AFTER_PLAYING, "WON": schema.STATUS_AFTER_WON, "LOST": schema.STATUS_AFTER_LOST}
    rows = []
    for event in events:
        if not isinstance(event.action_type, Action) or not isinstance(event.status_after, GameStatus):
            raise ModeledTimeValidationError("In-memory action/status must be public Action/GameStatus enums.")
        rows.append((
            event.action_index, action_map[event.action_type.name], event.x, event.y,
            status_map[event.status_after.name],
        ))
    return _reconstruct(
        game_index=record.game_index, result=record.result, total_actions=record.total_actions,
        game_first_click=(record.first_click_x, record.first_click_y), rows=tuple(rows),
        width=width, height=height, first_click=first_click, evaluation=evaluation,
    )


def reconstruct_persisted_game(
    connection: sqlite3.Connection, run: ModeledTimeRun, game_index: int, *,
    evaluation: ModelCEvaluation,
) -> ModeledGameCost:
    """Read every action row for one validated run/game, without any mutation.

    The caller must keep the source stable from run validation through reading.
    Separate read-only connections do not provide a cross-file atomic snapshot.
    """
    _require_evaluation(evaluation)
    if type(run) is not ModeledTimeRun:
        raise ModeledTimeValidationError("A validated modeled-time run is required.")
    # Recheck against this connection: a handle from another source or one
    # constructed by a caller must not bypass stored identity authentication.
    current_run = validate_run_identity(
        connection, run.run_id, solver_stage=run.solver_stage, evaluation=evaluation,
    )
    if current_run != run:
        raise ModeledTimeValidationError("Modeled-time run handle disagrees with its source.")
    _integer("game_index", game_index)
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        game = cursor.execute(
            "SELECT game_id, game_index, result, total_actions, first_click_x, first_click_y "
            "FROM games WHERE run_id = ? AND game_index = ?", (run.run_id, game_index),
        ).fetchone()
        if game is None:
            raise ModeledTimeValidationError(f"Missing game_index: {game_index}.")
        rows = tuple(tuple(row) for row in cursor.execute(
            "SELECT action_index, action_type, x, y, status_after FROM action_events "
            "WHERE game_id = ? ORDER BY action_index", (game["game_id"],),
        ).fetchall())
    result = {schema.GAME_RESULT_WIN: "WIN", schema.GAME_RESULT_LOSS: "LOSS"}.get(game["result"])
    if type(game["result"]) is not int:
        result = None
    return _reconstruct(
        game_index=game["game_index"], result=result, total_actions=game["total_actions"],
        game_first_click=(game["first_click_x"], game["first_click_y"]), rows=rows,
        width=run.width, height=run.height, first_click=(0, 0), evaluation=evaluation,
    )
