"""Synchronous Stage 2 benchmark execution under the frozen V1 contract.

The runner owns lifecycle, provenance and exact-prefix completion policy.
Execution, inference translation, collection and persistence stay in their
existing modules. Stop requests are checked only before starting each game.

Stable failure codes identify the operation that failed: GAME_EXECUTION_FAILED
(generation through game validation), GAME_PERSISTENCE_FAILED,
PROGRESS_CALLBACK_FAILED, STOP_REQUEST_FAILED, or RUN_FINALIZATION_FAILED.
Exception messages are never used as persisted codes.
"""

import os
import platform
import sqlite3
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from benchmark_board import (
    EXPERT_GENERAL_V1, BenchmarkSetSpec, calculate_board_fingerprint, generate_board,
)
from board_analyzer import analyze_board
from core_engine import Action, GameStatus, MinesweeperEngine
from simple_runner import SimpleActionTrace, StopReason, run_simple
from simple_telemetry import decision_to_telemetry
from telemetry_collector import TelemetryCollector
from telemetry_model import ActionEvent, GameRecord
import telemetry_repository as repository
import telemetry_schema as schema


class BenchmarkInvariantError(RuntimeError):
    """Execution or persisted coverage violates the benchmark contract."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _capture_git_provenance(repository_root: Path) -> tuple[str, bool]:
    """Capture the checked-out commit and complete non-ignored tree once."""
    commit = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True, capture_output=True,
    ).stdout.decode("ascii").strip()
    status = subprocess.run(
        ["git", "-C", str(repository_root), "status", "--porcelain=v1",
         "--untracked-files=all"],
        check=True, capture_output=True,
    ).stdout
    return commit, bool(status)


def _capture_environment() -> dict:
    clock = time.get_clock_info("perf_counter")
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_identifier": platform.processor() or None,
        "sqlite_version": sqlite3.sqlite_version,
        "perf_counter": {
            "implementation": clock.implementation,
            "monotonic": clock.monotonic,
            "adjustable": clock.adjustable,
            "resolution": clock.resolution,
        },
    }


def _record_trace(collector: TelemetryCollector, trace: SimpleActionTrace) -> None:
    metadata = {}
    if trace.decision is not None:
        telemetry = decision_to_telemetry(trace.decision)
        metadata = {
            "inference_category": telemetry.inference_category,
            "selection_candidate_count": telemetry.selection_candidate_count,
            "target_mine_probability": telemetry.target_mine_probability,
            "minimum_available_mine_probability": telemetry.minimum_available_mine_probability,
            "decision_compute_ns": trace.decision_compute_ns,
        }
    elif trace.decision_compute_ns is not None:
        raise BenchmarkInvariantError("A policy OPEN must have no decision timing.")
    collector.record_action(
        action_type=trace.move.action, x=trace.move.x, y=trace.move.y,
        status_after=trace.status_after,
        safe_cells_opened_delta=trace.safe_cells_opened_delta,
        explicit_flag_delta=trace.explicit_flag_delta,
        **metadata,
    )


def _validate_baseline_game(
    record: GameRecord, events: tuple[ActionEvent, ...], spec: BenchmarkSetSpec,
) -> None:
    if not events:
        raise BenchmarkInvariantError("A benchmark game requires a policy OPEN.")
    first = events[0]
    if (
        first.action_index != 0 or first.action_type != Action.OPEN
        or (first.x, first.y) != (spec.first_click_x, spec.first_click_y)
        or any(value is not None for value in (
            first.inference_category, first.selection_candidate_count,
            first.target_mine_probability, first.minimum_available_mine_probability,
            first.decision_compute_ns,
        ))
    ):
        raise BenchmarkInvariantError("Event zero must be the untimed policy OPEN.")
    if (
        record.local_deterministic_count + record.global_certainty_count
        + record.probability_guess_count != record.total_actions - 1
    ):
        raise BenchmarkInvariantError("Every action after the policy OPEN must be analyzed.")


def _play_game(spec: BenchmarkSetSpec, game_index: int) -> tuple[GameRecord, tuple[ActionEvent, ...]]:
    board = generate_board(spec, game_index)
    if board.game_index != game_index or board.seed != game_index:
        raise BenchmarkInvariantError("Generator V1 must preserve game_index == seed.")
    engine = MinesweeperEngine(spec.width, spec.height, spec.num_mines)
    engine.reset_with_mines(spec.width, spec.height, spec.num_mines, board.mine_positions)
    snapshot = engine.get_board_snapshot()
    if not snapshot.mines_placed or (
        snapshot.width, snapshot.height, snapshot.num_mines,
    ) != (spec.width, spec.height, spec.num_mines):
        raise BenchmarkInvariantError("Installed board dimensions or placement do not match the set.")
    fingerprint = calculate_board_fingerprint(
        snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines,
    )
    if fingerprint != board.board_fingerprint:
        raise BenchmarkInvariantError("Installed board fingerprint does not match the generated board.")
    if (spec.first_click_x, spec.first_click_y) in snapshot.mines:
        raise BenchmarkInvariantError("The benchmark policy OPEN must be safe.")
    analysis = analyze_board(snapshot)
    collector = TelemetryCollector()

    def observer(trace: SimpleActionTrace) -> None:
        _record_trace(collector, trace)

    result = run_simple(
        engine, accept_guesses=True,
        initial_open=(spec.first_click_x, spec.first_click_y), observer=observer,
    )
    if (result.stop_reason, result.status) not in (
        (StopReason.WON, GameStatus.WON), (StopReason.LOST, GameStatus.LOST),
    ) or result.status != engine.status:
        raise BenchmarkInvariantError("Stage 2 must finish with matching terminal status, never GUESS_REQUIRED.")
    events = collector.events
    if not events or events[-1].status_after != result.status:
        raise BenchmarkInvariantError("Terminal execution and telemetry status must match.")
    record = collector.finalize(
        game_index=game_index, seed=board.seed, board_fingerprint=fingerprint,
        board_3bv=analysis.total_3bv, board_ops=analysis.total_ops,
    )
    _validate_baseline_game(record, events, spec)
    return record, events


def run_benchmark(
    database: str | Path, requested_games: int, *,
    spec: BenchmarkSetSpec = EXPERT_GENERAL_V1, official: bool = False,
    stop_requested: Callable[[], bool] | None = None,
    progress: Callable[[int, int, int], None] | None = None,
    repository_root: str | Path | None = None,
) -> int:
    """Execute a V1 prefix and return its run_id after COMPLETED or ABORTED.

    Own a file connection opened/closed through the repository boundary.
    Official provenance comes only from this module's repository; supplying
    repository_root or dirty provenance is rejected before opening the database.
    Development mode allows a provenance root override and records its dirty state.
    The reserved EXPERT_GENERAL_V1 identity requires the exact canonical spec
    in both modes; custom set IDs retain their generic configuration support.

    stop_requested() is polled before each game, including the first. A request
    during play takes effect after that game's commit; completing the requested
    prefix wins over stop. progress(run_id, processed_games, requested_games)
    runs synchronously only after a successful game commit.

    Ordinary exceptions after RUNNING attempt a separate FAILED update, then
    propagate unchanged. KeyboardInterrupt/SystemExit are not converted into
    normal failures; RUNNING may remain, as with a failed FAILED update.
    """
    if not isinstance(database, (str, Path)) or not str(database) or str(database) == ":memory:":
        raise ValueError("database must be a nonempty file path.")
    if type(requested_games) is not int or not 1 <= requested_games <= (1 << 63) - 1:
        raise ValueError("requested_games must be a positive SQLite int, excluding bool.")
    if not isinstance(spec, BenchmarkSetSpec):
        raise ValueError("spec must be a BenchmarkSetSpec.")
    if spec.benchmark_set_id == EXPERT_GENERAL_V1.benchmark_set_id and spec != EXPERT_GENERAL_V1:
        raise ValueError("EXPERT_GENERAL_V1 requires the exact canonical benchmark specification.")
    if not isinstance(official, bool):
        raise ValueError("official must be a bool.")
    if official and repository_root is not None:
        raise ValueError("Official benchmark execution does not allow a repository_root override.")
    for name, callback in (("stop_requested", stop_requested), ("progress", progress)):
        if callback is not None and not callable(callback):
            raise ValueError(f"{name} must be callable or None.")
    root = Path(__file__).resolve().parent if repository_root is None else Path(repository_root)
    git_commit, git_dirty = _capture_git_provenance(root)
    if official and git_dirty:
        raise ValueError("Official benchmark execution requires a clean Git working tree.")
    environment = _capture_environment()
    first_click = (spec.first_click_x, spec.first_click_y)
    first_click_policy = (
        schema.FIRST_CLICK_FIXED_0_0 if first_click == (0, 0)
        else f"FIRST_CLICK_FIXED_{spec.first_click_x}_{spec.first_click_y}"
    )
    connection = repository.connect_database(database)
    try:
        run_id = repository.create_run(
            connection, telemetry_schema_version=schema.TELEMETRY_SCHEMA_VERSION,
            created_at=_utc_now(), git_commit=git_commit, git_dirty=git_dirty,
            solver_stage=schema.SOLVER_STAGE_STAGE_2,
            solver_policy=schema.SOLVER_POLICY_SIMPLE_MINIMUM_RISK,
            solver_config_snapshot={"accept_guesses": True, "initial_open": list(first_click)},
            width=spec.width, height=spec.height, num_mines=spec.num_mines,
            first_click_policy=first_click_policy,
            board_generator_version=spec.board_generator_version,
            benchmark_set_id=spec.benchmark_set_id, requested_games=requested_games,
            environment_snapshot=environment,
        )
        repository.update_run_status(
            connection, run_id, schema.RUN_STATUS_RUNNING, started_at=_utc_now(),
        )
        failure_code = "STOP_REQUEST_FAILED"
        try:
            for game_index in range(requested_games):
                failure_code = "STOP_REQUEST_FAILED"
                if stop_requested is not None and stop_requested():
                    failure_code = "RUN_FINALIZATION_FAILED"
                    repository.update_run_status(
                        connection, run_id, schema.RUN_STATUS_ABORTED, finished_at=_utc_now(),
                    )
                    return run_id
                failure_code = "GAME_EXECUTION_FAILED"
                record, events = _play_game(spec, game_index)
                failure_code = "GAME_PERSISTENCE_FAILED"
                repository.persist_completed_game(connection, run_id, record, events)
                if progress is not None:
                    failure_code = "PROGRESS_CALLBACK_FAILED"
                    progress(run_id, game_index + 1, requested_games)

            failure_code = "RUN_FINALIZATION_FAILED"
            indices = repository.fetch_game_indices(connection, run_id)
            if indices != tuple(range(requested_games)):
                raise BenchmarkInvariantError("Completed runs require exact requested prefix coverage.")
            repository.update_run_status(
                connection, run_id, schema.RUN_STATUS_COMPLETED, finished_at=_utc_now(),
            )
        except Exception as error:
            try:
                repository.update_run_status(
                    connection, run_id, schema.RUN_STATUS_FAILED,
                    finished_at=_utc_now(), failure_code=failure_code,
                )
            except Exception as cleanup_error:
                error.add_note(f"Best-effort FAILED update failed: {cleanup_error}")
            raise
        return run_id
    finally:
        connection.close()
