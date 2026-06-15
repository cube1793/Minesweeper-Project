"""
zini_calculator.py
G.ZiNi calculator scaffolding for immutable board snapshots.

This module intentionally stays outside MinesweeperEngine.  It will grow into
the dynamic G.ZiNi simulation layer, while BoardSnapshot and board_analyzer keep
providing the static board facts.
"""

from dataclasses import dataclass
from enum import Enum

from board_snapshot import BoardSnapshot, Coordinate


@dataclass(frozen=True)
class ZiniMove:
    """Minimal trace entry for tests and manual reference-site validation."""

    action: str
    x: int
    y: int
    premium: int | None
    clicks_added: int


@dataclass(frozen=True)
class ZiniResult:
    """Result returned by G.ZiNi calculations."""

    clicks: int
    moves: tuple[ZiniMove, ...] = ()


@dataclass(frozen=True)
class ZiniSearchResult:
    """Best min-tie result plus search completion metadata."""

    result: ZiniResult
    exact: bool
    timed_out: bool
    state_limited: bool
    elapsed_seconds: float
    unique_states: int
    search_calls: int
    best_clicks: int
    deterministic_clicks: int


from zini_core import (
    TopLeftKey,
    _ACTION_CLICK,
    _ACTION_FALLBACK_CLICK,
    _ACTION_FLAG_CHORD,
    _UNIT_ISOLATED,
    _UNIT_OPENING,
    _PremiumCandidate,
    _PremiumContext,
    _Static3BvUnit,
    _ZiniBoardState,
    _ZiniStateKey,
    _apply_next_g_zini_move,
    _apply_premium_candidate,
    _build_premium_context,
    _calculate_premium,
    _click_covered_candidate,
    _click_fallback_cell,
    _copy_zini_state,
    _count_adjacent_covered_3bv,
    _count_adjacent_unflagged_mines,
    _extract_static_3bv_units,
    _find_fallback_click_targets,
    _find_premium_candidates,
    _flag_adjacent_unflagged_mines,
    _flag_and_chord_uncovered_candidate,
    _is_covered_non_3bv,
    _neighbors,
    _opening_reveal_cells,
    _reveal_chord_neighbors,
    _run_g_zini_loop,
    _safe_cells,
    _select_best_premium_candidate,
    _select_fallback_click_target,
    _top_left_key,
    _zini_state_key,
)
from zini_min_ties import (
    _MinTieSearch,
    _MinTieSearchLimitReached,
    _calculate_g_zini_min_ties_bounded,
)

class ZiniAdvancedTerminationReason(str, Enum):
    """Reason a bounded advanced best-so-far search stopped.

    SEARCH_EXHAUSTED means only that the configured bounded strategy has no
    more candidates to expand.  It does not prove a global minimum or optimal
    ZiNi value.
    """

    TIME_LIMIT = "time_limit"
    EVALUATION_LIMIT = "evaluation_limit"
    STALL_LIMIT = "stall_limit"
    SEARCH_EXHAUSTED = "search_exhausted"


@dataclass(frozen=True)
class ZiniNeighborhoodBeamConfig:
    """Configuration for bounded neighborhood-beam search policies."""

    premium_window: int = 2
    beam_size: int = 8
    max_decision_points: int = 6
    max_alternatives_per_point: int = 3
    prefix_diversity_length: int = 20
    retain_click_margin: int = 3
    max_seconds: float | None = 5.0
    max_evaluations: int | None = 500
    stall_seconds: float | None = None
    seed: int = 0
    ranking_policy: str = "standard_v1"
    chain_depth: int = 2
    chain_branching: int = 2
    standard_phase_evaluations: int | None = None

    def __post_init__(self):
        _validate_neighborhood_beam_config(self)


@dataclass(frozen=True)
class ZiniAdvancedSearchResult:
    """Heuristic best-so-far result from a future advanced bounded search.

    Advanced neighborhood-beam search does not prove a minimum or optimum, so
    future APIs returning this type must always set exact to False.
    """

    result: ZiniResult
    exact: bool
    termination_reason: ZiniAdvancedTerminationReason
    elapsed_seconds: float
    evaluations: int
    generations: int
    best_clicks: int
    deterministic_clicks: int
    strategy_name: str
    strategy_version: str
    config: ZiniNeighborhoodBeamConfig


def _validate_neighborhood_beam_config(config: ZiniNeighborhoodBeamConfig):
    """Validate bounds for a future neighborhood-beam search."""
    if config.premium_window < 0:
        raise ValueError("premium_window cannot be negative.")
    if config.beam_size <= 0:
        raise ValueError("beam_size must be positive.")
    if config.max_decision_points <= 0:
        raise ValueError("max_decision_points must be positive.")
    if config.max_alternatives_per_point <= 0:
        raise ValueError("max_alternatives_per_point must be positive.")
    if config.prefix_diversity_length <= 0:
        raise ValueError("prefix_diversity_length must be positive.")
    if config.retain_click_margin < 0:
        raise ValueError("retain_click_margin cannot be negative.")
    if config.chain_depth <= 0:
        raise ValueError("chain_depth must be positive.")
    if config.chain_branching <= 0:
        raise ValueError("chain_branching must be positive.")
    if (
        config.standard_phase_evaluations is not None
        and config.standard_phase_evaluations < 0
    ):
        raise ValueError("standard_phase_evaluations cannot be negative.")
    if config.max_seconds is not None and config.max_seconds < 0:
        raise ValueError("max_seconds cannot be negative.")
    if config.max_evaluations is not None and config.max_evaluations < 0:
        raise ValueError("max_evaluations cannot be negative.")
    if config.stall_seconds is not None and config.stall_seconds < 0:
        raise ValueError("stall_seconds cannot be negative.")
    if (
        config.max_seconds is None
        and config.max_evaluations is None
        and config.stall_seconds is None
    ):
        raise ValueError("At least one advanced search limit is required.")
    if config.ranking_policy not in _SUPPORTED_NEIGHBORHOOD_BEAM_RANKING_POLICIES:
        raise ValueError(
            f"Unsupported neighborhood-beam ranking policy: "
            f"{config.ranking_policy}"
        )
    if config.ranking_policy == "standard_seeded_chain_v1":
        if config.max_evaluations is None:
            raise ValueError(
                "standard_seeded_chain_v1 requires max_evaluations."
            )
        if (
            config.standard_phase_evaluations is not None
            and config.standard_phase_evaluations > config.max_evaluations
        ):
            raise ValueError(
                "standard_phase_evaluations cannot exceed max_evaluations."
            )


def _resolve_standard_phase_evaluations(
    config: ZiniNeighborhoodBeamConfig,
) -> int:
    """Resolve the fixed Phase 1 budget for seeded-chain search."""
    if config.max_evaluations is None:
        raise ValueError(
            "standard_seeded_chain_v1 requires max_evaluations."
        )
    if config.standard_phase_evaluations is not None:
        return config.standard_phase_evaluations
    return (config.max_evaluations + 1) // 2


from zini_advanced import (
    _ALTERNATIVE_FALLBACK,
    _ALTERNATIVE_PREMIUM,
    _NEIGHBORHOOD_BEAM_STRATEGY_NAME,
    _NEIGHBORHOOD_BEAM_STRATEGY_VERSION,
    _SUPPORTED_NEIGHBORHOOD_BEAM_RANKING_POLICIES,
    _AdvancedTrajectory,
    _ChainAncestryEntry,
    _ChainNeighborhoodPolicyV1,
    _ChainTrajectoryNode,
    _NeighborhoodAlternative,
    _NeighborhoodBeamSearch,
    _NeighborhoodDecision,
    _NeighborhoodPolicy,
    _SeededChainSearchOutcome,
    _StandardNeighborhoodPolicyV1,
    _ZiniMoveSignature,
    _ZiniMoveSignatureEntry,
    _advanced_prefix_key,
    _apply_neighborhood_alternative,
    _calculate_g_zini_neighborhood_beam_bounded,
    _chain_ancestry_signature,
    _chain_choice_key,
    _chain_extension_key,
    _chain_node_from_rollout,
    _chain_node_key,
    _collect_neighborhood_decisions,
    _get_neighborhood_policy,
    _iter_chain_neighborhood_rollouts,
    _neighborhood_alternative_key,
    _premium_candidate_key,
    _rank_advanced_trajectory,
    _remaining_advanced_seconds,
    _rollout_neighborhood_deviation,
    _run_standard_seeded_chain_search,
    _select_chain_choices,
    _select_diverse_advanced_beam,
    _should_yield_chain_trajectory,
    _validate_chain_ancestry,
    _zini_move_signature,
    _zini_move_signature_entry,
)


def calculate_g_zini(snapshot: BoardSnapshot) -> ZiniResult:
    """
    Calculate G.ZiNi for a finalized board snapshot.

    Raises:
        ValueError: if mines have not been placed yet.
        RuntimeError: if the internal simulation cannot make progress.
    """
    if not snapshot.mines_placed:
        raise ValueError("Cannot calculate G.ZiNi before mines are placed.")

    context = _build_premium_context(snapshot)
    state = _ZiniBoardState.create(snapshot)
    moves = _run_g_zini_loop(state, context)

    return ZiniResult(
        clicks=sum(move.clicks_added for move in moves),
        moves=moves,
    )


def calculate_g_zini_min_ties(snapshot: BoardSnapshot) -> ZiniResult:
    """
    Calculate an extended G.ZiNi result by exploring maximum-Premium ties.

    This extension explores only candidates tied for the highest Premium at
    each step and selects the path with the lowest total click count. Premium,
    move application, and fallback behavior remain identical to
    calculate_g_zini().

    Raises:
        ValueError: if mines have not been placed yet.
        RuntimeError: if an explored branch cannot make progress.
    """
    return calculate_g_zini_min_ties_bounded(snapshot).result


def calculate_g_zini_min_ties_bounded(
    snapshot: BoardSnapshot,
    *,
    max_seconds: float | None = None,
    max_states: int | None = None,
) -> ZiniSearchResult:
    """
    Run maximum-Premium tie exploration with optional execution limits.

    If a time or state limit is reached, return the best valid result found so
    far, initialized from deterministic G.ZiNi, with exact=False.

    Raises:
        ValueError: if mines have not been placed or a limit is negative.
        RuntimeError: if an explored branch cannot make progress.
    """
    return _calculate_g_zini_min_ties_bounded(
        snapshot,
        max_seconds=max_seconds,
        max_states=max_states,
    )


def calculate_g_zini_neighborhood_beam_bounded(
    snapshot: BoardSnapshot,
    *,
    config: ZiniNeighborhoodBeamConfig | None = None,
) -> ZiniAdvancedSearchResult:
    """Run bounded heuristic neighborhood-beam search for a best-so-far path.

    The deterministic G.ZiNi result is always used as the initial valid
    baseline.  This experimental search does not prove a minimum or optimum,
    including when its configured neighborhood is exhausted.

    Raises:
        ValueError: if mines have not been placed or config is invalid.
        RuntimeError: if replay or rollout cannot make progress consistently.
    """
    return _calculate_g_zini_neighborhood_beam_bounded(
        snapshot,
        config=config,
    )
