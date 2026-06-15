"""Internal advanced neighborhood-beam search for G.ZiNi."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from random import Random
from time import perf_counter
from typing import TYPE_CHECKING, Iterator, Protocol

from board_snapshot import BoardSnapshot, Coordinate
from zini_core import (
    _ACTION_FALLBACK_CLICK,
    _PremiumCandidate,
    _PremiumContext,
    _ZiniBoardState,
    _apply_premium_candidate,
    _build_premium_context,
    _click_fallback_cell,
    _copy_zini_state,
    _find_fallback_click_targets,
    _find_premium_candidates,
    _run_g_zini_loop,
)

if TYPE_CHECKING:
    from zini_calculator import (
        ZiniAdvancedSearchResult,
        ZiniAdvancedTerminationReason,
        ZiniMove,
        ZiniNeighborhoodBeamConfig,
        ZiniResult,
    )


_ALTERNATIVE_PREMIUM = "premium"
_ALTERNATIVE_FALLBACK = "fallback"
_NEIGHBORHOOD_BEAM_STRATEGY_NAME = "neighborhood_beam"
_NEIGHBORHOOD_BEAM_STRATEGY_VERSION = "1"
_SUPPORTED_NEIGHBORHOOD_BEAM_RANKING_POLICIES = frozenset(
    {"standard_v1", "chain_v1", "standard_seeded_chain_v1"}
)


_ZiniMoveSignatureEntry = tuple[str, int, int, int | None, int]
_ZiniMoveSignature = tuple[_ZiniMoveSignatureEntry, ...]


@dataclass(frozen=True)
class _AdvancedTrajectory:
    """One complete replay-valid trajectory retained by advanced search."""

    result: ZiniResult


@dataclass(frozen=True)
class _NeighborhoodAlternative:
    """One alternate Premium or fallback action at a replayed decision."""

    kind: str
    coord: Coordinate
    premium: int | None


@dataclass(frozen=True)
class _NeighborhoodDecision:
    """A replay decision with an independent snapshot of its dynamic state."""

    step_index: int
    state: _ZiniBoardState
    prefix_moves: tuple[ZiniMove, ...]
    alternatives: tuple[_NeighborhoodAlternative, ...]


@dataclass(frozen=True)
class _ChainAncestryEntry:
    """One deviation that must remain present in a chain trajectory."""

    step_index: int
    move_signature: _ZiniMoveSignatureEntry


@dataclass(frozen=True)
class _ChainTrajectoryNode:
    """One complete trajectory retained while extending a deviation chain."""

    trajectory: _AdvancedTrajectory
    last_step_index: int
    ancestry: tuple[_ChainAncestryEntry, ...]



class _NeighborhoodPolicy(Protocol):
    """Internal policy seam for bounded neighborhood-beam behavior."""

    def collect_decisions(
        self,
        snapshot: BoardSnapshot,
        context: _PremiumContext,
        trajectory: _AdvancedTrajectory,
        config: ZiniNeighborhoodBeamConfig,
    ) -> tuple[_NeighborhoodDecision, ...]: ...

    def select_decisions(
        self,
        decisions: tuple[_NeighborhoodDecision, ...],
        config: ZiniNeighborhoodBeamConfig,
        random: Random,
    ) -> tuple[_NeighborhoodDecision, ...]: ...

    def select_alternatives(
        self,
        alternatives: tuple[_NeighborhoodAlternative, ...],
        config: ZiniNeighborhoodBeamConfig,
        random: Random,
    ) -> tuple[_NeighborhoodAlternative, ...]: ...

    def iter_rollout_deviations(
        self,
        snapshot: BoardSnapshot,
        decision: _NeighborhoodDecision,
        alternative: _NeighborhoodAlternative,
        context: _PremiumContext,
        config: ZiniNeighborhoodBeamConfig,
        random: Random,
        known_trajectory_signatures: set[_ZiniMoveSignature],
    ) -> Iterator[_AdvancedTrajectory]: ...

    def rank_trajectory(
        self,
        trajectory: _AdvancedTrajectory,
        config: ZiniNeighborhoodBeamConfig,
    ) -> tuple: ...

    def diversity_key(
        self,
        trajectory: _AdvancedTrajectory,
        config: ZiniNeighborhoodBeamConfig,
    ) -> _ZiniMoveSignature: ...


class _StandardNeighborhoodPolicyV1:
    """Current single-deviation neighborhood behavior, unchanged."""

    def collect_decisions(
        self,
        snapshot: BoardSnapshot,
        context: _PremiumContext,
        trajectory: _AdvancedTrajectory,
        config: ZiniNeighborhoodBeamConfig,
    ) -> tuple[_NeighborhoodDecision, ...]:
        return _collect_neighborhood_decisions(
            snapshot,
            context,
            trajectory,
            config,
        )

    def select_decisions(
        self,
        decisions: tuple[_NeighborhoodDecision, ...],
        config: ZiniNeighborhoodBeamConfig,
        random: Random,
    ) -> tuple[_NeighborhoodDecision, ...]:
        return self._sample_ordered(
            decisions,
            config.max_decision_points,
            key=lambda item: item.step_index,
            random=random,
        )

    def select_alternatives(
        self,
        alternatives: tuple[_NeighborhoodAlternative, ...],
        config: ZiniNeighborhoodBeamConfig,
        random: Random,
    ) -> tuple[_NeighborhoodAlternative, ...]:
        return self._sample_ordered(
            alternatives,
            config.max_alternatives_per_point,
            key=_neighborhood_alternative_key,
            random=random,
        )

    def iter_rollout_deviations(
        self,
        snapshot: BoardSnapshot,
        decision: _NeighborhoodDecision,
        alternative: _NeighborhoodAlternative,
        context: _PremiumContext,
        config: ZiniNeighborhoodBeamConfig,
        random: Random,
        known_trajectory_signatures: set[_ZiniMoveSignature],
    ) -> Iterator[_AdvancedTrajectory]:
        yield _rollout_neighborhood_deviation(
            decision,
            alternative,
            context,
        )

    def rank_trajectory(
        self,
        trajectory: _AdvancedTrajectory,
        config: ZiniNeighborhoodBeamConfig,
    ) -> tuple:
        return _rank_advanced_trajectory(trajectory, config)

    def diversity_key(
        self,
        trajectory: _AdvancedTrajectory,
        config: ZiniNeighborhoodBeamConfig,
    ) -> _ZiniMoveSignature:
        return _advanced_prefix_key(
            trajectory,
            config.prefix_diversity_length,
        )

    @staticmethod
    def _sample_ordered(items, limit: int, *, key, random: Random):
        ordered = tuple(sorted(items, key=key))
        if len(ordered) <= limit:
            return ordered
        indices = sorted(random.sample(range(len(ordered)), limit))
        return tuple(ordered[index] for index in indices)


class _ChainNeighborhoodPolicyV1(_StandardNeighborhoodPolicyV1):
    """Bounded chain of forward-only deviations and deterministic rollouts."""

    def __init__(self):
        self._seen_nodes: set[tuple[_ZiniMoveSignature, int]] = set()
        self._seen_extensions: set[tuple] = set()
        self._yielded_signatures: set[_ZiniMoveSignature] = set()

    def iter_rollout_deviations(
        self,
        snapshot: BoardSnapshot,
        decision: _NeighborhoodDecision,
        alternative: _NeighborhoodAlternative,
        context: _PremiumContext,
        config: ZiniNeighborhoodBeamConfig,
        random: Random,
        known_trajectory_signatures: set[_ZiniMoveSignature],
    ) -> Iterator[_AdvancedTrajectory]:
        if config.chain_depth == 1:
            yield from super().iter_rollout_deviations(
                snapshot,
                decision,
                alternative,
                context,
                config,
                random,
                known_trajectory_signatures,
            )
            return

        yield from _iter_chain_neighborhood_rollouts(
            policy=self,
            snapshot=snapshot,
            initial_decision=decision,
            initial_alternative=alternative,
            context=context,
            config=config,
            random=random,
            known_trajectory_signatures=known_trajectory_signatures,
        )


def _get_neighborhood_policy(
    config: ZiniNeighborhoodBeamConfig,
) -> _NeighborhoodPolicy:
    """Resolve the configured internal neighborhood policy."""
    if config.ranking_policy == "standard_v1":
        return _StandardNeighborhoodPolicyV1()
    if config.ranking_policy == "chain_v1":
        return _ChainNeighborhoodPolicyV1()
    raise ValueError(
        f"Unsupported neighborhood-beam ranking policy: "
        f"{config.ranking_policy}"
    )


@dataclass
class _NeighborhoodBeamSearch:
    """Bounded best-so-far search over local G.ZiNi trajectory deviations."""

    snapshot: BoardSnapshot
    context: _PremiumContext
    config: ZiniNeighborhoodBeamConfig
    baseline: ZiniResult
    started_at: float
    evaluations: int = 0
    generations: int = 0
    best: _AdvancedTrajectory = field(init=False)
    last_improvement_at: float = field(init=False)
    random: Random = field(init=False)
    policy: _NeighborhoodPolicy = field(init=False)
    trajectory_signatures: set[_ZiniMoveSignature] = field(default_factory=set)
    attempted_deviations: set[tuple] = field(default_factory=set)

    def __post_init__(self):
        self.best = _AdvancedTrajectory(self.baseline)
        self.last_improvement_at = self.started_at
        self.random = Random(self.config.seed)
        self.policy = _get_neighborhood_policy(self.config)
        self.trajectory_signatures.add(
            _zini_move_signature(self.baseline.moves)
        )

    def run(self) -> ZiniAdvancedTerminationReason:
        """Search complete trajectories until a configured bound is reached."""
        from zini_calculator import ZiniAdvancedTerminationReason
        beam = (self.best,)

        while True:
            termination = self._limit_reason()
            if termination is not None:
                return termination

            generated: list[_AdvancedTrajectory] = []
            found_unattempted = False
            evaluated_this_generation = False

            for trajectory in sorted(
                beam,
                key=lambda item: self.policy.rank_trajectory(
                    item,
                    self.config,
                ),
            ):
                decisions = self._unattempted_decisions(trajectory)
                decisions = self._select_decisions(decisions)
                if decisions:
                    found_unattempted = True

                for decision in decisions:
                    alternatives = self._select_alternatives(
                        decision.alternatives
                    )
                    for alternative in alternatives:
                        termination = self._limit_reason()
                        if termination is not None:
                            if evaluated_this_generation:
                                self.generations += 1
                            return termination

                        deviation_key = self._deviation_key(
                            trajectory,
                            decision,
                            alternative,
                        )
                        self.attempted_deviations.add(deviation_key)
                        rollouts = self.policy.iter_rollout_deviations(
                            self.snapshot,
                            decision,
                            alternative,
                            self.context,
                            self.config,
                            self.random,
                            self.trajectory_signatures,
                        )
                        while True:
                            termination = self._limit_reason()
                            if termination is not None:
                                if evaluated_this_generation:
                                    self.generations += 1
                                return termination

                            try:
                                candidate = next(rollouts)
                            except StopIteration:
                                break

                            self.evaluations += 1
                            evaluated_this_generation = True

                            signature = _zini_move_signature(
                                candidate.result.moves
                            )
                            if signature in self.trajectory_signatures:
                                continue

                            self.trajectory_signatures.add(signature)
                            generated.append(candidate)
                            if candidate.result.clicks < self.best.result.clicks:
                                self.best = candidate
                                self.last_improvement_at = perf_counter()

            if evaluated_this_generation:
                self.generations += 1
            if not found_unattempted:
                return ZiniAdvancedTerminationReason.SEARCH_EXHAUSTED

            beam = _select_diverse_advanced_beam(
                (*beam, *generated),
                self.best.result.clicks,
                self.config,
                self.policy,
            )

    def _unattempted_decisions(
        self,
        trajectory: _AdvancedTrajectory,
    ) -> tuple[_NeighborhoodDecision, ...]:
        decisions = self.policy.collect_decisions(
            self.snapshot,
            self.context,
            trajectory,
            self.config,
        )
        available = []
        for decision in decisions:
            alternatives = tuple(
                alternative
                for alternative in decision.alternatives
                if self._deviation_key(
                    trajectory,
                    decision,
                    alternative,
                ) not in self.attempted_deviations
            )
            if alternatives:
                available.append(
                    _NeighborhoodDecision(
                        step_index=decision.step_index,
                        state=decision.state,
                        prefix_moves=decision.prefix_moves,
                        alternatives=alternatives,
                    )
                )
        return tuple(sorted(available, key=lambda item: item.step_index))

    def _select_decisions(
        self,
        decisions: tuple[_NeighborhoodDecision, ...],
    ) -> tuple[_NeighborhoodDecision, ...]:
        return self.policy.select_decisions(
            decisions,
            self.config,
            self.random,
        )

    def _select_alternatives(
        self,
        alternatives: tuple[_NeighborhoodAlternative, ...],
    ) -> tuple[_NeighborhoodAlternative, ...]:
        return self.policy.select_alternatives(
            alternatives,
            self.config,
            self.random,
        )

    def _deviation_key(
        self,
        trajectory: _AdvancedTrajectory,
        decision: _NeighborhoodDecision,
        alternative: _NeighborhoodAlternative,
    ) -> tuple:
        return (
            _zini_move_signature(trajectory.result.moves),
            decision.step_index,
            alternative.kind,
            alternative.coord,
            alternative.premium,
        )

    def _limit_reason(self) -> ZiniAdvancedTerminationReason | None:
        from zini_calculator import ZiniAdvancedTerminationReason

        now = perf_counter()
        if (
            self.config.max_seconds is not None
            and now - self.started_at >= self.config.max_seconds
        ):
            return ZiniAdvancedTerminationReason.TIME_LIMIT
        if (
            self.config.max_evaluations is not None
            and self.evaluations >= self.config.max_evaluations
        ):
            return ZiniAdvancedTerminationReason.EVALUATION_LIMIT
        if (
            self.config.stall_seconds is not None
            and now - self.last_improvement_at >= self.config.stall_seconds
        ):
            return ZiniAdvancedTerminationReason.STALL_LIMIT
        return None


@dataclass(frozen=True)
class _SeededChainSearchOutcome:
    """Combined result and accounting for a two-phase seeded search."""

    result: ZiniResult
    termination_reason: ZiniAdvancedTerminationReason
    evaluations: int
    generations: int


def _remaining_advanced_seconds(
    started_at: float,
    max_seconds: float | None,
) -> float | None:
    """Return the remaining global wall-time budget for a search phase."""
    if max_seconds is None:
        return None
    return max(0.0, max_seconds - (perf_counter() - started_at))


def _run_standard_seeded_chain_search(
    snapshot: BoardSnapshot,
    context: _PremiumContext,
    config: ZiniNeighborhoodBeamConfig,
    deterministic_result: ZiniResult,
    started_at: float,
) -> _SeededChainSearchOutcome:
    """Run standard search, then chain-expand only its best trajectory."""
    from zini_calculator import (
        ZiniAdvancedTerminationReason,
        _resolve_standard_phase_evaluations,
    )

    standard_budget = _resolve_standard_phase_evaluations(config)
    total_budget = config.max_evaluations
    if total_budget is None:
        raise ValueError(
            "standard_seeded_chain_v1 requires max_evaluations."
        )
    chain_budget = total_budget - standard_budget

    remaining_seconds = _remaining_advanced_seconds(
        started_at,
        config.max_seconds,
    )
    if remaining_seconds == 0:
        return _SeededChainSearchOutcome(
            result=deterministic_result,
            termination_reason=ZiniAdvancedTerminationReason.TIME_LIMIT,
            evaluations=0,
            generations=0,
        )
    if total_budget == 0:
        return _SeededChainSearchOutcome(
            result=deterministic_result,
            termination_reason=(
                ZiniAdvancedTerminationReason.EVALUATION_LIMIT
            ),
            evaluations=0,
            generations=0,
        )

    phase_one_config = replace(
        config,
        ranking_policy="standard_v1",
        max_seconds=remaining_seconds,
        max_evaluations=standard_budget,
        standard_phase_evaluations=None,
    )
    phase_one_search = _NeighborhoodBeamSearch(
        snapshot=snapshot,
        context=context,
        config=phase_one_config,
        baseline=deterministic_result,
        started_at=perf_counter(),
    )
    phase_one_reason = phase_one_search.run()

    if phase_one_reason == ZiniAdvancedTerminationReason.TIME_LIMIT:
        return _SeededChainSearchOutcome(
            result=phase_one_search.best.result,
            termination_reason=phase_one_reason,
            evaluations=phase_one_search.evaluations,
            generations=phase_one_search.generations,
        )

    remaining_seconds = _remaining_advanced_seconds(
        started_at,
        config.max_seconds,
    )
    if remaining_seconds == 0:
        return _SeededChainSearchOutcome(
            result=phase_one_search.best.result,
            termination_reason=ZiniAdvancedTerminationReason.TIME_LIMIT,
            evaluations=phase_one_search.evaluations,
            generations=phase_one_search.generations,
        )
    if chain_budget == 0:
        return _SeededChainSearchOutcome(
            result=phase_one_search.best.result,
            termination_reason=(
                ZiniAdvancedTerminationReason.EVALUATION_LIMIT
            ),
            evaluations=phase_one_search.evaluations,
            generations=phase_one_search.generations,
        )

    phase_two_config = replace(
        config,
        ranking_policy="chain_v1",
        max_seconds=remaining_seconds,
        max_evaluations=chain_budget,
        standard_phase_evaluations=None,
    )
    phase_two_search = _NeighborhoodBeamSearch(
        snapshot=snapshot,
        context=context,
        config=phase_two_config,
        baseline=phase_one_search.best.result,
        started_at=perf_counter(),
    )
    phase_two_reason = phase_two_search.run()

    return _SeededChainSearchOutcome(
        result=phase_two_search.best.result,
        termination_reason=phase_two_reason,
        evaluations=(
            phase_one_search.evaluations + phase_two_search.evaluations
        ),
        generations=(
            phase_one_search.generations + phase_two_search.generations
        ),
    )


def _calculate_g_zini_neighborhood_beam_bounded(
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
    from zini_calculator import (
        ZiniAdvancedSearchResult,
        ZiniNeighborhoodBeamConfig,
        ZiniResult,
        _validate_neighborhood_beam_config,
    )

    if not snapshot.mines_placed:
        raise ValueError("Cannot calculate G.ZiNi before mines are placed.")

    resolved_config = config or ZiniNeighborhoodBeamConfig()
    _validate_neighborhood_beam_config(resolved_config)

    started_at = perf_counter()
    context = _build_premium_context(snapshot)
    deterministic_moves = _run_g_zini_loop(
        _ZiniBoardState.create(snapshot),
        context,
    )
    deterministic_result = ZiniResult(
        clicks=sum(move.clicks_added for move in deterministic_moves),
        moves=deterministic_moves,
    )
    if resolved_config.ranking_policy == "standard_seeded_chain_v1":
        outcome = _run_standard_seeded_chain_search(
            snapshot,
            context,
            resolved_config,
            deterministic_result,
            started_at,
        )
        result = outcome.result
        termination_reason = outcome.termination_reason
        evaluations = outcome.evaluations
        generations = outcome.generations
    else:
        search = _NeighborhoodBeamSearch(
            snapshot=snapshot,
            context=context,
            config=resolved_config,
            baseline=deterministic_result,
            started_at=started_at,
        )
        termination_reason = search.run()
        result = search.best.result
        evaluations = search.evaluations
        generations = search.generations

    return ZiniAdvancedSearchResult(
        result=result,
        exact=False,
        termination_reason=termination_reason,
        elapsed_seconds=perf_counter() - started_at,
        evaluations=evaluations,
        generations=generations,
        best_clicks=result.clicks,
        deterministic_clicks=deterministic_result.clicks,
        strategy_name=_NEIGHBORHOOD_BEAM_STRATEGY_NAME,
        strategy_version=_NEIGHBORHOOD_BEAM_STRATEGY_VERSION,
        config=resolved_config,
    )


def _zini_move_signature(
    moves: tuple[ZiniMove, ...],
) -> _ZiniMoveSignature:
    """Return the canonical signature used for trajectory deduplication."""
    return tuple(
        (move.action, move.x, move.y, move.premium, move.clicks_added)
        for move in moves
    )


def _premium_candidate_key(candidate: _PremiumCandidate):
    x, y = candidate.coord
    return -candidate.premium, y, x


def _neighborhood_alternative_key(
    alternative: _NeighborhoodAlternative,
):
    x, y = alternative.coord
    if alternative.kind == _ALTERNATIVE_PREMIUM:
        return 0, -alternative.premium, y, x
    return 1, 0, y, x


def _collect_neighborhood_decisions(
    snapshot: BoardSnapshot,
    context: _PremiumContext,
    trajectory: _AdvancedTrajectory,
    config: ZiniNeighborhoodBeamConfig,
) -> tuple[_NeighborhoodDecision, ...]:
    """Replay a complete trajectory and collect alternate local decisions."""
    state = _ZiniBoardState.create(snapshot)
    decisions = []

    for step_index, expected_move in enumerate(trajectory.result.moves):
        candidates = tuple(
            sorted(
                _find_premium_candidates(state, context),
                key=_premium_candidate_key,
            )
        )
        best_premium = max(
            (candidate.premium for candidate in candidates),
            default=None,
        )
        coord = (expected_move.x, expected_move.y)

        if best_premium is None or best_premium < 0:
            if expected_move.action != _ACTION_FALLBACK_CLICK:
                raise RuntimeError(
                    "Advanced trajectory expected a non-fallback move in a "
                    "fallback state."
                )
            targets = _find_fallback_click_targets(state, context)
            if coord not in targets:
                raise RuntimeError(
                    "Advanced trajectory fallback target is not available."
                )
            alternatives = tuple(
                _NeighborhoodAlternative(
                    kind=_ALTERNATIVE_FALLBACK,
                    coord=target,
                    premium=None,
                )
                for target in targets
                if target != coord
            )
            decision_state = _copy_zini_state(state)
            actual_move = _click_fallback_cell(state, coord, context)
        else:
            matching = tuple(
                candidate
                for candidate in candidates
                if candidate.coord == coord
            )
            if len(matching) != 1:
                raise RuntimeError(
                    "Advanced trajectory Premium candidate is not available."
                )
            selected_candidate = matching[0]
            minimum_premium = max(0, best_premium - config.premium_window)
            alternatives = tuple(
                _NeighborhoodAlternative(
                    kind=_ALTERNATIVE_PREMIUM,
                    coord=candidate.coord,
                    premium=candidate.premium,
                )
                for candidate in candidates
                if candidate.premium >= minimum_premium
                and candidate.coord != coord
            )
            decision_state = _copy_zini_state(state)
            actual_move = _apply_premium_candidate(
                state,
                selected_candidate,
                context,
            )

        if actual_move != expected_move:
            raise RuntimeError(
                "Advanced trajectory move does not match current G.ZiNi "
                "semantics."
            )
        if alternatives:
            decisions.append(
                _NeighborhoodDecision(
                    step_index=step_index,
                    state=decision_state,
                    prefix_moves=trajectory.result.moves[:step_index],
                    alternatives=tuple(
                        sorted(
                            alternatives,
                            key=_neighborhood_alternative_key,
                        )
                    ),
                )
            )

    if not state.all_safe_cells_revealed():
        raise RuntimeError("Advanced trajectory replay did not solve the board.")
    if trajectory.result.clicks != sum(
        move.clicks_added for move in trajectory.result.moves
    ):
        raise RuntimeError("Advanced trajectory click total is inconsistent.")

    return tuple(sorted(decisions, key=lambda item: item.step_index))


def _apply_neighborhood_alternative(
    state: _ZiniBoardState,
    alternative: _NeighborhoodAlternative,
    context: _PremiumContext,
) -> ZiniMove:
    """Apply one replay deviation using existing G.ZiNi move semantics."""
    if alternative.kind == _ALTERNATIVE_PREMIUM:
        if alternative.premium is None:
            raise RuntimeError("Premium alternative is missing Premium.")
        return _apply_premium_candidate(
            state,
            _PremiumCandidate(
                coord=alternative.coord,
                premium=alternative.premium,
            ),
            context,
        )
    if alternative.kind == _ALTERNATIVE_FALLBACK:
        return _click_fallback_cell(state, alternative.coord, context)
    raise RuntimeError(f"Unknown neighborhood alternative: {alternative.kind}")


def _rollout_neighborhood_deviation(
    decision: _NeighborhoodDecision,
    alternative: _NeighborhoodAlternative,
    context: _PremiumContext,
) -> _AdvancedTrajectory:
    """Apply one deviation and finish the board with deterministic G.ZiNi."""
    from zini_calculator import ZiniResult

    state = _copy_zini_state(decision.state)
    move = _apply_neighborhood_alternative(state, alternative, context)
    completion = _run_g_zini_loop(state, context)
    moves = decision.prefix_moves + (move,) + completion
    return _AdvancedTrajectory(
        ZiniResult(
            clicks=sum(item.clicks_added for item in moves),
            moves=moves,
        )
    )


def _zini_move_signature_entry(move: ZiniMove) -> _ZiniMoveSignatureEntry:
    """Return the canonical signature for one trace move."""
    return (
        move.action,
        move.x,
        move.y,
        move.premium,
        move.clicks_added,
    )


def _validate_chain_ancestry(node: _ChainTrajectoryNode):
    """Ensure every earlier deviation is preserved in the current trace."""
    moves = node.trajectory.result.moves
    for entry in node.ancestry:
        if entry.step_index >= len(moves):
            raise RuntimeError("Chain ancestry step is outside the trajectory.")
        if _zini_move_signature_entry(moves[entry.step_index]) != (
            entry.move_signature
        ):
            raise RuntimeError(
                "Chain rollout did not preserve an earlier deviation."
            )


def _chain_node_key(
    node: _ChainTrajectoryNode,
) -> tuple[_ZiniMoveSignature, int]:
    return (
        _zini_move_signature(node.trajectory.result.moves),
        node.last_step_index,
    )


def _chain_ancestry_signature(
    ancestry: tuple[_ChainAncestryEntry, ...],
) -> tuple[tuple[int, _ZiniMoveSignatureEntry], ...]:
    return tuple(
        (entry.step_index, entry.move_signature)
        for entry in ancestry
    )


def _chain_extension_key(
    node: _ChainTrajectoryNode,
    decision: _NeighborhoodDecision,
    alternative: _NeighborhoodAlternative,
) -> tuple:
    return (
        _chain_ancestry_signature(node.ancestry),
        _zini_move_signature(node.trajectory.result.moves),
        node.last_step_index,
        decision.step_index,
        alternative.kind,
        alternative.coord,
        alternative.premium,
    )


def _chain_choice_key(
    choice: tuple[_NeighborhoodDecision, _NeighborhoodAlternative],
) -> tuple:
    decision, alternative = choice
    return decision.step_index, _neighborhood_alternative_key(alternative)


def _select_chain_choices(
    policy: _ChainNeighborhoodPolicyV1,
    snapshot: BoardSnapshot,
    context: _PremiumContext,
    node: _ChainTrajectoryNode,
    config: ZiniNeighborhoodBeamConfig,
    random: Random,
) -> tuple[tuple[_NeighborhoodDecision, _NeighborhoodAlternative], ...]:
    """Select bounded forward-only extensions for one complete trajectory."""
    _validate_chain_ancestry(node)
    decisions = tuple(
        decision
        for decision in policy.collect_decisions(
            snapshot,
            context,
            node.trajectory,
            config,
        )
        if decision.step_index > node.last_step_index
    )
    decisions = policy.select_decisions(decisions, config, random)
    choices = []
    for decision in decisions:
        alternatives = policy.select_alternatives(
            decision.alternatives,
            config,
            random,
        )
        for alternative in alternatives:
            extension_key = _chain_extension_key(
                node,
                decision,
                alternative,
            )
            if extension_key not in policy._seen_extensions:
                choices.append((decision, alternative))

    return policy._sample_ordered(
        tuple(choices),
        config.chain_branching,
        key=_chain_choice_key,
        random=random,
    )


def _chain_node_from_rollout(
    trajectory: _AdvancedTrajectory,
    step_index: int,
    ancestry: tuple[_ChainAncestryEntry, ...],
) -> _ChainTrajectoryNode:
    if step_index >= len(trajectory.result.moves):
        raise RuntimeError("Chain deviation step is outside the trajectory.")
    entry = _ChainAncestryEntry(
        step_index=step_index,
        move_signature=_zini_move_signature_entry(
            trajectory.result.moves[step_index]
        ),
    )
    node = _ChainTrajectoryNode(
        trajectory=trajectory,
        last_step_index=step_index,
        ancestry=ancestry + (entry,),
    )
    _validate_chain_ancestry(node)
    return node


def _should_yield_chain_trajectory(
    policy: _ChainNeighborhoodPolicyV1,
    trajectory: _AdvancedTrajectory,
    known_trajectory_signatures: set[_ZiniMoveSignature],
) -> bool:
    signature = _zini_move_signature(trajectory.result.moves)
    if (
        signature in known_trajectory_signatures
        or signature in policy._yielded_signatures
    ):
        return False
    policy._yielded_signatures.add(signature)
    return True


def _iter_chain_neighborhood_rollouts(
    *,
    policy: _ChainNeighborhoodPolicyV1,
    snapshot: BoardSnapshot,
    initial_decision: _NeighborhoodDecision,
    initial_alternative: _NeighborhoodAlternative,
    context: _PremiumContext,
    config: ZiniNeighborhoodBeamConfig,
    random: Random,
    known_trajectory_signatures: set[_ZiniMoveSignature],
) -> Iterator[_AdvancedTrajectory]:
    """Yield complete forward-only chain trajectories one at a time."""
    initial_trajectory = _rollout_neighborhood_deviation(
        initial_decision,
        initial_alternative,
        context,
    )
    initial_node = _chain_node_from_rollout(
        initial_trajectory,
        initial_decision.step_index,
        (),
    )
    initial_node_key = _chain_node_key(initial_node)
    if initial_node_key in policy._seen_nodes:
        return
    policy._seen_nodes.add(initial_node_key)

    if _should_yield_chain_trajectory(
        policy,
        initial_trajectory,
        known_trajectory_signatures,
    ):
        yield initial_trajectory

    frontier = (initial_node,)
    for _depth in range(2, config.chain_depth + 1):
        next_frontier = []
        for node in frontier:
            choices = _select_chain_choices(
                policy,
                snapshot,
                context,
                node,
                config,
                random,
            )
            for decision, alternative in choices:
                extension_key = _chain_extension_key(
                    node,
                    decision,
                    alternative,
                )
                policy._seen_extensions.add(extension_key)
                child_trajectory = _rollout_neighborhood_deviation(
                    decision,
                    alternative,
                    context,
                )
                child_node = _chain_node_from_rollout(
                    child_trajectory,
                    decision.step_index,
                    node.ancestry,
                )
                child_node_key = _chain_node_key(child_node)
                if child_node_key in policy._seen_nodes:
                    continue
                policy._seen_nodes.add(child_node_key)
                next_frontier.append(child_node)

                if _should_yield_chain_trajectory(
                    policy,
                    child_trajectory,
                    known_trajectory_signatures,
                ):
                    yield child_trajectory

        if not next_frontier:
            return
        frontier = tuple(next_frontier)


def _rank_advanced_trajectory(
    trajectory: _AdvancedTrajectory,
    config: ZiniNeighborhoodBeamConfig,
):
    """Return the configured deterministic trajectory ranking key."""
    if config.ranking_policy in (
        "standard_v1",
        "chain_v1",
    ):
        return (
            trajectory.result.clicks,
            len(trajectory.result.moves),
            _zini_move_signature(trajectory.result.moves),
        )
    raise ValueError(
        f"Unsupported neighborhood-beam ranking policy: "
        f"{config.ranking_policy}"
    )


def _advanced_prefix_key(
    trajectory: _AdvancedTrajectory,
    prefix_length: int,
) -> _ZiniMoveSignature:
    return _zini_move_signature(trajectory.result.moves[:prefix_length])


def _select_diverse_advanced_beam(
    trajectories: tuple[_AdvancedTrajectory, ...],
    best_clicks: int,
    config: ZiniNeighborhoodBeamConfig,
    policy: _NeighborhoodPolicy,
) -> tuple[_AdvancedTrajectory, ...]:
    """Select a ranked beam while preserving distinct move prefixes."""
    maximum_clicks = best_clicks + config.retain_click_margin
    unique_by_signature = {}
    for trajectory in sorted(
        trajectories,
        key=lambda item: policy.rank_trajectory(item, config),
    ):
        if trajectory.result.clicks > maximum_clicks:
            continue
        signature = _zini_move_signature(trajectory.result.moves)
        unique_by_signature.setdefault(signature, trajectory)

    ordered = tuple(
        sorted(
            unique_by_signature.values(),
            key=lambda item: policy.rank_trajectory(item, config),
        )
    )
    selected = []
    deferred = []
    prefixes = set()

    for trajectory in ordered:
        prefix = policy.diversity_key(trajectory, config)
        if prefix in prefixes:
            deferred.append(trajectory)
            continue
        prefixes.add(prefix)
        selected.append(trajectory)
        if len(selected) == config.beam_size:
            return tuple(selected)

    for trajectory in deferred:
        selected.append(trajectory)
        if len(selected) == config.beam_size:
            break
    return tuple(selected)

