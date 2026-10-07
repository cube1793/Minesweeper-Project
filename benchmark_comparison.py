"""Outcome-aware Stage-2 to Stage-3 comparison under frozen Model C.

Stage-2 costs are explicit post-hoc evaluation, not historical telemetry fields.
Only common wins (WW) contribute to primary modeled time-to-win statistics.
Whole-prefix costs are diagnostic even when both solvers' outcome labels agree.
No candidate-count or historical compute-time comparison is performed here.

Connections belong to the caller and are only read. Sources must be completed
artifacts or caller-verified stable snapshots. Two read-only connections alone
do not establish an atomic snapshot across files; this module adds no locking
or snapshot infrastructure. Official eligibility retains the existing stricter
COMPLETED, clean provenance and complete requested-prefix requirements.
"""

import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from benchmark_modeled_time import (
    ModelCEvaluation, authenticate_model_c, reconstruct_persisted_game,
    validate_run_identity,
)
from benchmark_statistics import BenchmarkStatisticsError, validate_paired_prefix_sources
import telemetry_schema as schema


@dataclass(frozen=True)
class ComparisonSource:
    """A display label distinguishes artifacts even when their run IDs coincide."""

    label: str
    run_id: int
    solver_stage: str
    telemetry_schema_version: int
    evaluation_kind: str


@dataclass(frozen=True)
class OutcomeContingency:
    """First letter is Stage 2's outcome; second letter is Stage 3's."""

    ww: int
    wl: int
    lw: int
    ll: int


@dataclass(frozen=True)
class WWModeledTime:
    """Exact common-win workload; delta is Stage 3 minus Stage 2, in us.

    Ratio is the ratio of totals, not a mean of per-game ratios. Empty WW has
    zero sums/counts and no ratio/reduction, and is not evidence of equal speed.
    Negative reduction denotes slowdown and is never clamped.
    """

    game_count: int
    stage2_total_us: int
    stage3_total_us: int
    total_delta_us: int
    ratio: Fraction | None
    reduction: Fraction | None
    stage3_faster: int
    stage2_faster: int
    ties: int
    paired_deltas_us: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Stage2Stage3Comparison:
    left: ComparisonSource
    right: ComparisonSource
    prefix_games: int
    require_official: bool
    evaluation: ModelCEvaluation
    outcomes: OutcomeContingency
    stage2_wins: int
    stage2_losses: int
    stage2_win_rate: Fraction
    stage3_wins: int
    stage3_losses: int
    stage3_win_rate: Fraction
    primary: WWModeledTime
    diagnostic_stage2_total_us: int
    diagnostic_stage3_total_us: int


def compare_stage2_stage3_sources(
    left_connection: sqlite3.Connection, left_run_id: int,
    right_connection: sqlite3.Connection, right_run_id: int,
    prefix_games: int, *, left_source_label: str, right_source_label: str,
    require_official: bool = False,
) -> Stage2Stage3Comparison:
    """Compare exactly [0, prefix_games), with Stage 2 left and Stage 3 right.

    Both modes require canonical EXPERT_GENERAL_V1 solver/config identities.
    Official mode additionally requires official-eligible complete artifacts.
    Diagnostic mode does not become official just because eligibility happens
    to hold. Source labels must be distinct nonempty display names; they are
    never used as solver identity or evidence that the sources are stable.

    Every included game is structurally validated and reconstructed, including
    losses. Missing or corrupt action rows invalidate the entire comparison;
    they are never dropped, repaired, or represented as zero-cost games.
    Callers can pass one connection twice for a same-source comparison.
    """
    if any(type(label) is not str or not label.strip() for label in (
        left_source_label, right_source_label,
    )) or left_source_label.strip() == right_source_label.strip():
        raise BenchmarkStatisticsError("Source labels must be distinct nonempty strings.")

    pair = validate_paired_prefix_sources(
        left_connection, left_run_id, right_connection, right_run_id,
        prefix_games, require_official=require_official,
    )
    evaluation = authenticate_model_c()
    left_run = validate_run_identity(
        left_connection, left_run_id, solver_stage=schema.SOLVER_STAGE_STAGE_2,
        evaluation=evaluation,
    )
    right_run = validate_run_identity(
        right_connection, right_run_id, solver_stage=schema.SOLVER_STAGE_STAGE_3,
        evaluation=evaluation,
    )

    ww = wl = lw = ll = 0
    stage2_total = stage3_total = 0
    diagnostic_stage2 = diagnostic_stage3 = 0
    stage3_faster = stage2_faster = ties = 0
    deltas = []
    for identity in pair.identities:
        stage2 = reconstruct_persisted_game(
            left_connection, left_run, identity.game_index, evaluation=evaluation,
        )
        stage3 = reconstruct_persisted_game(
            right_connection, right_run, identity.game_index, evaluation=evaluation,
        )
        diagnostic_stage2 += stage2.total_modeled_us
        diagnostic_stage3 += stage3.total_modeled_us
        if stage2.result == "WIN" and stage3.result == "WIN":
            ww += 1
            stage2_total += stage2.total_modeled_us
            stage3_total += stage3.total_modeled_us
            delta = stage3.total_modeled_us - stage2.total_modeled_us
            deltas.append((identity.game_index, delta))
            if delta < 0:
                stage3_faster += 1
            elif delta > 0:
                stage2_faster += 1
            else:
                ties += 1
        elif stage2.result == "WIN":
            wl += 1
        elif stage3.result == "WIN":
            lw += 1
        else:
            ll += 1

    ratio = Fraction(stage3_total, stage2_total) if ww else None
    return Stage2Stage3Comparison(
        left=ComparisonSource(
            left_source_label, left_run_id, schema.SOLVER_STAGE_STAGE_2,
            schema.TELEMETRY_SCHEMA_VERSION, "post_hoc_frozen_model_c",
        ),
        right=ComparisonSource(
            right_source_label, right_run_id, schema.SOLVER_STAGE_STAGE_3,
            schema.TELEMETRY_SCHEMA_VERSION_STAGE_3, "declared_frozen_model_c",
        ),
        prefix_games=prefix_games, require_official=require_official,
        evaluation=evaluation, outcomes=OutcomeContingency(ww, wl, lw, ll),
        stage2_wins=ww + wl, stage2_losses=lw + ll,
        stage2_win_rate=Fraction(ww + wl, prefix_games),
        stage3_wins=ww + lw, stage3_losses=wl + ll,
        stage3_win_rate=Fraction(ww + lw, prefix_games),
        primary=WWModeledTime(
            game_count=ww, stage2_total_us=stage2_total, stage3_total_us=stage3_total,
            total_delta_us=stage3_total - stage2_total, ratio=ratio,
            reduction=1 - ratio if ratio is not None else None,
            stage3_faster=stage3_faster, stage2_faster=stage2_faster, ties=ties,
            paired_deltas_us=tuple(deltas),
        ),
        diagnostic_stage2_total_us=diagnostic_stage2,
        diagnostic_stage3_total_us=diagnostic_stage3,
    )
