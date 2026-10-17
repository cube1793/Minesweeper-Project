"""Authenticated, read-only composition for the four closed Timeline exemplars.

No selection, solver execution, G4/HTML input or presentation lives here. The
public entry point has only two explicit path arguments; frozen admission cannot
be overridden by callers. Private constants may be patched by synthetic tests.
"""

from contextlib import ExitStack, closing
from dataclasses import dataclass, fields
from hashlib import sha256
from pathlib import Path
import platform
import sqlite3
import subprocess

import benchmark_board as boards
import benchmark_modeled_time as modeled
import benchmark_statistics as statistics
from board_snapshot import BoardSnapshot
from core_engine import Action, GameStatus, MinesweeperEngine
from exemplar_board_reconstruction import ExemplarBoardReconstruction, reconstruct_board
from telemetry_model import ActionEvent, GameRecord, InferenceCategory
import telemetry_repository as repository
import telemetry_schema as schema
from timeline_analytics import project_timeline


class ExemplarEvidenceError(ValueError):
    """Admission, decoding, reconstruction or source preservation failed."""


@dataclass(frozen=True)
class ExemplarReference:
    """Already accepted identity and totals; LOSS costs are through termination."""

    game_index: int
    category: str
    board_fingerprint: str
    stage2_actions: int
    stage3_actions: int
    stage2_modeled_us: int
    stage3_modeled_us: int
    outcome: str


_SOURCE_HASHES = (
    ("stage2", "8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f"),
    ("stage3", "b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e"),
)
_PREFIX_GAMES = 100000
_REFERENCES = (
    ExemplarReference(73758, "Maximum Stage-3 WW advantage",
                      "7fe223012a42cdfb32ca5a493097920cd192b74869a58f1a008dc7e1efbc7f2d",
                      320, 177, 57365067, 30355982, "WIN"),
    ExemplarReference(73024, "Median-delta WW exemplar",
                      "4c3d414489f684c83fb7358c5a479e797493ad456b8ae12f8e4b7b44b6bcf8d8",
                      313, 207, 53655374, 37168019, "WIN"),
    ExemplarReference(93557, "Closest-to-zero Stage-3 WW advantage",
                      "22d9a199f0e1839ecdcc5be84b8054abe366be7b85b770b440be8484887ae2c3",
                      279, 204, 47034727, 39157214, "WIN"),
    ExemplarReference(1, "LL control",
                      "007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e",
                      4, 4, 720354, 720354, "LOSS"),
)
_SIDECARS = ("-wal", "-shm", "-journal")
_STAGES = (schema.SOLVER_STAGE_STAGE_2, schema.SOLVER_STAGE_STAGE_3)
_RESULTS = {schema.GAME_RESULT_WIN: "WIN", schema.GAME_RESULT_LOSS: "LOSS"}
_ACTIONS = {schema.ACTION_OPEN: Action.OPEN, schema.ACTION_FLAG: Action.FLAG,
            schema.ACTION_CHORD: Action.CHORD}
_STATUSES = {schema.STATUS_AFTER_PLAYING: GameStatus.PLAYING,
             schema.STATUS_AFTER_WON: GameStatus.WON, schema.STATUS_AFTER_LOST: GameStatus.LOST}
_INFERENCES = {schema.INFERENCE_LOCAL_DETERMINISTIC: InferenceCategory.LOCAL_DETERMINISTIC,
               schema.INFERENCE_GLOBAL_CERTAINTY: InferenceCategory.GLOBAL_CERTAINTY,
               schema.INFERENCE_PROBABILITY_GUESS: InferenceCategory.PROBABILITY_GUESS}


@dataclass(frozen=True)
class AcceptedSourceState:
    role: str
    path: Path
    sha256: str
    size_bytes: int
    mtime_ns: int
    sidecars: tuple[str, ...]


@dataclass(frozen=True)
class LoadedSolverRun:
    role: str
    summary: statistics.BenchmarkRunSummary
    coverage: statistics.RunCoverage
    solver_config_snapshot: str
    git_commit: str
    environment_snapshot: str


@dataclass(frozen=True)
class LoadedExemplar:
    reference: ExemplarReference
    board_snapshot: BoardSnapshot
    stage2: ExemplarBoardReconstruction
    stage3: ExemplarBoardReconstruction


@dataclass(frozen=True)
class AcceptedExemplarEvidence:
    sources: tuple[AcceptedSourceState, ...]
    runs: tuple[LoadedSolverRun, ...]
    evaluation: modeled.ModelCEvaluation
    exemplars: tuple[LoadedExemplar, ...]
    reconstruction_git_head: str | None
    reconstruction_git_dirty: bool | None
    python_version: str
    python_architecture: str


def _require(condition, message):
    if not condition:
        raise ExemplarEvidenceError(message)


def _hash_file(path):
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecars(path):
    return tuple(suffix for suffix in _SIDECARS if Path(str(path) + suffix).exists())


def _source_state(role, path):
    before = path.stat()
    entry_sidecars = _sidecars(path)
    digest = _hash_file(path)
    after = path.stat()
    sidecars = _sidecars(path)
    _require((before.st_size, before.st_mtime_ns, entry_sidecars)
             == (after.st_size, after.st_mtime_ns, sidecars),
             f"{role}: source changed while hashing.")
    _require(not sidecars, f"{role}: unexpected DB sidecars: {sidecars}.")
    return AcceptedSourceState(role, path, digest, after.st_size, after.st_mtime_ns, sidecars)


def _discover_run(connection, role, stage, evaluation):
    matches = []
    for run in statistics.list_benchmark_runs(connection):
        if run.solver_stage != stage:
            continue
        try:
            modeled.validate_run_identity(connection, run.run_id, solver_stage=stage, evaluation=evaluation)
        except modeled.ModeledTimeValidationError:
            continue
        coverage = statistics.get_run_coverage(connection, run.run_id)
        if (run.run_status == schema.RUN_STATUS_COMPLETED and not run.git_dirty
                and coverage.official_eligible and coverage.exact_requested_prefix
                and coverage.exact_processed_prefix
                and coverage.requested_games == coverage.processed_games
                == coverage.stored_game_count == _PREFIX_GAMES):
            row = repository.fetch_run(connection, run.run_id)
            matches.append(LoadedSolverRun(role, run, coverage, row["solver_config_snapshot"],
                                           row["git_commit"], row["environment_snapshot"]))
    _require(len(matches) == 1, f"{role}: expected exactly one accepted run; found {len(matches)}.")
    return matches[0]


def _reference(index):
    _require(type(index) is int, "Exemplar index must be an integer, excluding bool.")
    found = next((item for item in _REFERENCES if item.game_index == index), None)
    _require(found is not None, f"Game index {index} is not an admitted fixed exemplar.")
    return found


def _decode_enum(value, mapping, name):
    _require(type(value) is int and value in mapping, f"Invalid persisted {name}: {value!r}.")
    return mapping[value]


def _load_selected(connection, run, index):
    reference = _reference(index)  # Reject arbitrary detail reads before querying.
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        rows = cursor.execute("SELECT * FROM games WHERE run_id = ? AND game_index = ?",
                              (run.summary.run_id, index)).fetchall()
        _require(len(rows) == 1, f"{run.role} game {index}: expected exactly one selected game row.")
        row = rows[0]
        values = {field.name: row[field.name] for field in fields(GameRecord)}
        values["result"] = _decode_enum(values["result"], _RESULTS, "result")
        flag = values["had_probability_guess"]
        _require(type(flag) is int and flag in (0, 1), "Invalid persisted guess boolean.")
        values["had_probability_guess"] = bool(flag)
        record = GameRecord(**values)
        _require((record.game_index, record.seed, record.first_click_x, record.first_click_y,
                  record.board_fingerprint) == (index, index, 0, 0, reference.board_fingerprint),
                 f"{run.role} game {index}: selected identity/fingerprint mismatch.")
        events = []
        for event in cursor.execute(
            "SELECT * FROM action_events WHERE game_id = ? ORDER BY action_index", (row["game_id"],),
        ):
            values = {field.name: event[field.name] for field in fields(ActionEvent)}
            values["action_type"] = _decode_enum(values["action_type"], _ACTIONS, "action_type")
            values["status_after"] = _decode_enum(values["status_after"], _STATUSES, "status_after")
            if values["inference_category"] is not None:
                values["inference_category"] = _decode_enum(values["inference_category"], _INFERENCES,
                                                           "inference_category")
            for name in ("target_mine_probability", "minimum_available_mine_probability"):
                values[name] = repository.decode_probability(values[name])
            events.append(ActionEvent(**values))
    return record, tuple(events)


def _fixed_board(reference, records):
    index = reference.game_index
    spec = boards.EXPERT_GENERAL_V1
    _require((spec.benchmark_set_id, spec.width, spec.height, spec.num_mines,
              spec.first_click_x, spec.first_click_y, spec.board_generator_version, spec.seed_scheme)
             == ("EXPERT_GENERAL_V1", 30, 16, 99, 0, 0, "V1", "game_index"),
             "Benchmark generator configuration drift.")
    generated = boards.generate_board(spec, index)
    fingerprint = boards.calculate_board_fingerprint(30, 16, 99, generated.mine_positions)
    _require((generated.game_index, generated.seed) == (index, index)
             and fingerprint == generated.board_fingerprint == reference.board_fingerprint
             and all(record.board_fingerprint == fingerprint for record in records),
             f"Game {index}: generated seed/fingerprint mismatch.")
    engine = MinesweeperEngine()
    engine.reset_with_mines(30, 16, 99, generated.mine_positions)
    return engine.get_board_snapshot()


def _load_exemplars(connections, runs, evaluation):
    games = []
    for reference in _REFERENCES:
        index = reference.game_index
        streams = tuple(_load_selected(connection, run, index)
                        for connection, run in zip(connections, runs))
        left, right = (stream[0] for stream in streams)
        identity_fields = ("game_index", "seed", "board_fingerprint", "first_click_x",
                           "first_click_y", "board_3bv", "board_ops")
        _require(all(getattr(left, name) == getattr(right, name) for name in identity_fields),
                 f"Game {index}: paired selected identity mismatch.")
        board = _fixed_board(reference, (left, right))
        reconstructions = []
        for side, (record, events) in enumerate(streams):
            timeline = project_timeline(record, events, width=30, height=16, evaluation=evaluation)
            reconstructed = reconstruct_board(board, timeline)
            expected_actions = (reference.stage2_actions, reference.stage3_actions)[side]
            expected_cost = (reference.stage2_modeled_us, reference.stage3_modeled_us)[side]
            _require((record.total_actions, timeline.total_modeled_us, record.result)
                     == (expected_actions, expected_cost, reference.outcome),
                     f"Game {index} {runs[side].role}: accepted action/cost/outcome totals mismatch.")
            reconstructions.append(reconstructed)
        games.append(LoadedExemplar(reference, board, *reconstructions))
    return tuple(games)


def _git_identity():
    """Read current reconstruction-source identity; unavailable outside Git."""
    command = ["git", "--no-optional-locks", "-C", str(Path(__file__).resolve().parent)]
    try:
        head = subprocess.check_output(command + ["rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
                                       text=True, timeout=10).strip()
        dirty = bool(subprocess.check_output(command + ["status", "--porcelain"],
                                             stderr=subprocess.DEVNULL, text=True, timeout=10).strip())
        return head, dirty
    except (OSError, subprocess.SubprocessError):
        return None, None


def load_accepted_exemplar_evidence(stage2_db_path, stage3_db_path) -> AcceptedExemplarEvidence:
    """Load only the frozen four cases from exact preserved stable DB files.

    Both paths are mandatory. immutable=True asserts no writer during the entire
    operation; entry/exit equality is a bounded preservation check, not a live
    atomic snapshot. DBs are closed before exit checks and before publication.
    Failures retain their cause; simultaneous stability failures are reported too.
    """
    authenticated = []
    failure = None
    try:
        paths = tuple(Path(path).resolve(strict=True) for path in (stage2_db_path, stage3_db_path))
        _require(all(path.is_file() for path in paths), "Both evidence paths must be files.")
        _require(not paths[0].samefile(paths[1]), "The two source roles require different physical files.")
        for (role, expected_hash), path in zip(_SOURCE_HASHES, paths):
            state = _source_state(role, path)
            _require(state.sha256 == expected_hash, f"{role}: accepted SHA-256 mismatch.")
            authenticated.append(state)
        evaluation = modeled.authenticate_model_c()
        with ExitStack() as stack:
            connections = tuple(stack.enter_context(closing(repository.connect_database_readonly(
                state.path, immutable=True))) for state in authenticated)
            runs = tuple(_discover_run(connection, state.role, stage, evaluation)
                         for connection, state, stage in zip(connections, authenticated, _STAGES))
            exemplars = _load_exemplars(connections, runs, evaluation)
    except BaseException as exc:
        failure = exc

    stability_errors = []
    for state in authenticated:
        try:
            _require(_source_state(state.role, state.path) == state,
                     f"{state.role}: exit source stability mismatch.")
        except Exception as exc:
            stability_errors.append(str(exc))
    if stability_errors:
        message = "Source preservation failed: " + "; ".join(stability_errors)
        if failure is not None:
            message += f" Original loading failure: {failure}"
        raise ExemplarEvidenceError(message) from failure
    if failure is not None:
        if not isinstance(failure, Exception):
            raise failure
        raise ExemplarEvidenceError(f"Accepted exemplar loading failed: {failure}") from failure
    head, dirty = _git_identity()
    return AcceptedExemplarEvidence(tuple(authenticated), runs, evaluation, exemplars,
                                   head, dirty, platform.python_version(), platform.machine())
