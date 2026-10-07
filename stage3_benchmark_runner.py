"""Stage-3 benchmark identity and executed-trace telemetry, on shared lifecycle.

Board installation and static evaluation stay here. Only the Engine reaches
the approved Stage-3 runner, and only public executed traces reach the adapter.
The existing repository owns atomic game persistence and physical schema V1.
"""

from collections import Counter
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

import benchmark_runner as lifecycle
from benchmark_board import (
    EXPERT_GENERAL_V1, BenchmarkSetSpec, calculate_board_fingerprint, generate_board,
)
from board_analyzer import analyze_board
from benchmark_modeled_time import authenticate_model_c, reconstruct_game
from core_engine import Action, GameStatus, MinesweeperEngine
import stage3_physical as physical
from stage3_physical import load_timing_table
from stage3_runner import Stage3ActionTrace, run_stage3
from stage3_telemetry import trace_to_telemetry
from telemetry_collector import TelemetryCollector
from telemetry_model import ActionEvent, GameRecord, InferenceCategory
import telemetry_schema as schema


ALGORITHM_SPEC_VERSION = 1
ALGORITHM_SPEC_SHA256 = "6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33"
PHYSICAL_MODEL_ID = "overlap_floor_log2_distance_v1"
PHYSICAL_PROFILE_VERSION = 1
TIMING_UNIT = "us"


def _validate_spec(spec: BenchmarkSetSpec) -> None:
    if not isinstance(spec, BenchmarkSetSpec):
        raise ValueError("spec must be a BenchmarkSetSpec.")
    if (spec.first_click_x, spec.first_click_y) != (0, 0):
        raise ValueError("Stage-3 benchmark requires canonical first click (0, 0).")
    if not (1 <= spec.width <= 30 and 1 <= spec.height <= 16):
        raise ValueError("Stage-3 board must fit the frozen 30-by-16 timing table.")


def _benchmark_identity(spec: BenchmarkSetSpec) -> dict:
    """Build semantic V2 identity only after authenticating frozen inputs.

    Continuation invokes this during read-only preflight, including when all
    requested games are already committed. No caller can supply identity facts.
    """
    _validate_spec(spec)
    load_timing_table()
    return {
        "telemetry_schema_version": schema.TELEMETRY_SCHEMA_VERSION_STAGE_3,
        "solver_stage": schema.SOLVER_STAGE_STAGE_3,
        "solver_policy": schema.SOLVER_POLICY_E_FIRST_FIRST_REVEAL_V1,
        "solver_config_snapshot": {
            "initial_open": [0, 0],
            "initial_cursor": [0, 0],
            "algorithm_spec_version": ALGORITHM_SPEC_VERSION,
            "algorithm_spec_sha256": ALGORITHM_SPEC_SHA256,
            "physical_model_id": PHYSICAL_MODEL_ID,
            "physical_profile_version": PHYSICAL_PROFILE_VERSION,
            "physical_profile_sha256": physical.PROFILE_SHA256,
            "timing_table_sha256": physical.TABLE_SHA256,
            "timing_unit": TIMING_UNIT,
        },
        "width": spec.width, "height": spec.height, "num_mines": spec.num_mines,
        "first_click_policy": schema.FIRST_CLICK_FIXED_0_0,
        "board_generator_version": spec.board_generator_version,
        "benchmark_set_id": spec.benchmark_set_id,
    }


def _record_trace(collector: TelemetryCollector, trace: Stage3ActionTrace) -> None:
    metadata = trace_to_telemetry(trace)
    collector.record_action(
        action_type=trace.move.action, x=trace.move.x, y=trace.move.y,
        status_after=trace.status_after,
        safe_cells_opened_delta=trace.safe_cells_opened_delta,
        explicit_flag_delta=trace.explicit_flag_delta,
        inference_category=metadata.inference_category,
        selection_candidate_count=metadata.selection_candidate_count,
        target_mine_probability=metadata.target_mine_probability,
        minimum_available_mine_probability=metadata.minimum_available_mine_probability,
        decision_compute_ns=metadata.decision_compute_ns,
    )


def _validate_stage3_game(record: GameRecord, events: tuple[ActionEvent, ...]) -> None:
    """Check the Stage-3 stream and summaries, without board-answer evidence."""
    if not events:
        raise lifecycle.BenchmarkInvariantError("A Stage-3 game requires a policy OPEN.")
    first = events[0]
    if (
        first.action_index != 0 or first.action_type != Action.OPEN
        or (first.x, first.y) != (0, 0)
        or any(value is not None for value in (
            first.inference_category, first.selection_candidate_count,
            first.target_mine_probability, first.minimum_available_mine_probability,
            first.decision_compute_ns,
        ))
    ):
        raise lifecycle.BenchmarkInvariantError("Event zero must be the untimed policy OPEN (0, 0).")
    for event in events[1:]:
        if (
            event.inference_category is None or event.decision_compute_ns is None
            or event.selection_candidate_count is not None
        ):
            raise lifecycle.BenchmarkInvariantError(
                "Every later Stage-3 action must be analyzed with no candidate count.",
            )
        if event.inference_category == InferenceCategory.PROBABILITY_GUESS and (
            event.action_type != Action.OPEN
            or not isinstance(event.target_mine_probability, Fraction)
            or not isinstance(event.minimum_available_mine_probability, Fraction)
            or event.target_mine_probability != event.minimum_available_mine_probability
        ):
            raise lifecycle.BenchmarkInvariantError("Stage-3 guesses require exact minimum-risk OPEN.")
        if event.action_type == Action.CHORD and (
            event.target_mine_probability is not None
            or event.minimum_available_mine_probability is not None
            or event.inference_category == InferenceCategory.PROBABILITY_GUESS
        ):
            raise lifecycle.BenchmarkInvariantError("Stage-3 CHORD requires non-guess NULL probabilities.")

    action_counts = Counter(event.action_type for event in events)
    category_counts = Counter(event.inference_category for event in events[1:])
    if (
        record.total_actions != len(events)
        or (record.open_count, record.flag_count, record.chord_count) != (
            action_counts[Action.OPEN], action_counts[Action.FLAG], action_counts[Action.CHORD],
        )
        or (
            record.local_deterministic_count, record.global_certainty_count,
            record.probability_guess_count,
        ) != (
            category_counts[InferenceCategory.LOCAL_DETERMINISTIC],
            category_counts[InferenceCategory.GLOBAL_CERTAINTY],
            category_counts[InferenceCategory.PROBABILITY_GUESS],
        )
        or record.local_deterministic_count + record.global_certainty_count
        + record.probability_guess_count != record.total_actions - 1
    ):
        raise lifecycle.BenchmarkInvariantError("Stage-3 action and category summaries must match events.")


def _play_game(spec: BenchmarkSetSpec, game_index: int) -> tuple[GameRecord, tuple[ActionEvent, ...]]:
    _validate_spec(spec)
    board = generate_board(spec, game_index)
    if board.game_index != game_index or board.seed != game_index:
        raise lifecycle.BenchmarkInvariantError("Generator V1 must preserve game_index == seed.")
    engine = MinesweeperEngine(spec.width, spec.height, spec.num_mines)
    engine.reset_with_mines(spec.width, spec.height, spec.num_mines, board.mine_positions)
    snapshot = engine.get_board_snapshot()
    if not snapshot.mines_placed or (
        snapshot.width, snapshot.height, snapshot.num_mines,
    ) != (spec.width, spec.height, spec.num_mines):
        raise lifecycle.BenchmarkInvariantError("Installed board dimensions or placement do not match the set.")
    fingerprint = calculate_board_fingerprint(
        snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines,
    )
    if fingerprint != board.board_fingerprint:
        raise lifecycle.BenchmarkInvariantError("Installed board fingerprint does not match the generated board.")
    if (0, 0) in snapshot.mines:
        raise lifecycle.BenchmarkInvariantError("The benchmark policy OPEN must be safe.")
    analysis = analyze_board(snapshot)
    collector = TelemetryCollector()
    observed_traces = []

    def observer(trace: Stage3ActionTrace) -> None:
        _record_trace(collector, trace)
        observed_traces.append(trace)

    result = run_stage3(engine, observer=observer)
    if result.status not in (GameStatus.WON, GameStatus.LOST) or result.status != engine.status:
        raise lifecycle.BenchmarkInvariantError("Stage 3 must finish with matching terminal status.")
    events = collector.events
    if (
        not events or events[-1].status_after != result.status
        or tuple(observed_traces) != result.traces or len(events) != len(result.traces)
    ):
        raise lifecycle.BenchmarkInvariantError("Terminal telemetry must match the complete executed trace stream.")
    record = collector.finalize(
        game_index=game_index, seed=board.seed, board_fingerprint=fingerprint,
        board_3bv=analysis.total_3bv, board_ops=analysis.total_ops,
    )
    _validate_stage3_game(record, events)
    modeled = reconstruct_game(
        record, events, width=spec.width, height=spec.height,
        evaluation=authenticate_model_c(),
    )
    if modeled.total_modeled_us != result.total_modeled_us:
        raise lifecycle.BenchmarkInvariantError(
            "Stage-3 runner modeled time must match independent action-target reconstruction.",
        )
    return record, events


def run_stage3_benchmark(
    database: str | Path, requested_games: int, *,
    spec: BenchmarkSetSpec = EXPERT_GENERAL_V1, official: bool = False,
    stop_requested: Callable[[], bool] | None = None,
    progress: Callable[[int, int, int], None] | None = None,
    repository_root: str | Path | None = None,
) -> int:
    """Execute a Stage-3 prefix with semantic V2 telemetry on physical V1.

    Official execution requires the canonical corpus, a new database artifact,
    and clean module-root provenance. Development mode permits smaller fixed
    origin corpora and the existing dirty/provenance-root override convention.
    Stop, progress, transactions and failure handling follow run_benchmark.
    """
    _validate_spec(spec)
    if official:
        if spec != EXPERT_GENERAL_V1:
            raise ValueError("Official Stage-3 execution requires canonical EXPERT_GENERAL_V1.")
        if isinstance(database, (str, Path)) and Path(database).exists():
            raise ValueError("Official Stage-3 execution requires a new database artifact.")
    return lifecycle._run_benchmark(
        database, requested_games, spec=spec, official=official,
        stop_requested=stop_requested, progress=progress, repository_root=repository_root,
        benchmark_identity=_benchmark_identity, play_game=_play_game,
    )


def continue_stage3_benchmark(
    database: str | Path, run_id: int, *,
    stop_requested: Callable[[], bool] | None = None,
    progress: Callable[[int, int, int], None] | None = None,
) -> int:
    """Continue only an admitted clean canonical Stage-3 RUNNING exact prefix.

    The operator must first ensure the previous writer has exited. All stored
    identity, provenance, environment, coverage and physical-input checks run
    before opening the writer; rejection leaves lifecycle metadata unchanged.
    Requested count and committed games are preserved, including finalize-only.
    """
    return lifecycle._continue_benchmark(
        database, run_id, stop_requested=stop_requested, progress=progress,
        benchmark_identity=_benchmark_identity, play_game=_play_game,
    )
