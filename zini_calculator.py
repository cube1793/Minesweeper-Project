"""
zini_calculator.py
G.ZiNi calculator scaffolding for immutable board snapshots.

This module intentionally stays outside MinesweeperEngine.  It will grow into
the dynamic G.ZiNi simulation layer, while BoardSnapshot and board_analyzer keep
providing the static board facts.
"""

from dataclasses import dataclass, field
from enum import Enum
from random import Random
from time import perf_counter
from typing import Iterator, Protocol

from board_analyzer import BoardAnalysis, CellClass, analyze_board
from board_snapshot import BoardSnapshot, Coordinate


_UNIT_OPENING = "opening"
_UNIT_ISOLATED = "isolated"
_ACTION_CLICK = "click"
_ACTION_FLAG_CHORD = "flag_chord"
_ACTION_FALLBACK_CLICK = "fallback_click"
_ALTERNATIVE_PREMIUM = "premium"
_ALTERNATIVE_FALLBACK = "fallback"
_NEIGHBORHOOD_BEAM_STRATEGY_NAME = "neighborhood_beam"
_NEIGHBORHOOD_BEAM_STRATEGY_VERSION = "1"
_SUPPORTED_NEIGHBORHOOD_BEAM_RANKING_POLICIES = frozenset(
    {"standard_v1", "chain_v1"}
)


TopLeftKey = tuple[int, int]
_ZiniStateKey = tuple[frozenset[Coordinate], frozenset[Coordinate]]
_ZiniMoveSignatureEntry = tuple[str, int, int, int | None, int]
_ZiniMoveSignature = tuple[_ZiniMoveSignatureEntry, ...]


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


class _MinTieSearchLimitReached(Exception):
    """Internal cooperative bounded-search stop signal."""


@dataclass(frozen=True)
class _Static3BvUnit:
    """One static 3BV unit used as input for future G.ZiNi simulation."""

    kind: str
    representative: Coordinate
    cells: frozenset[Coordinate]
    opening_id: int | None = None


@dataclass(frozen=True)
class _PremiumContext:
    """Static lookup data used while calculating Premium values."""

    analysis: BoardAnalysis
    units: tuple[_Static3BvUnit, ...]
    opening_units_by_id: dict[int, _Static3BvUnit]
    isolated_cells: frozenset[Coordinate]


@dataclass(frozen=True)
class _PremiumCandidate:
    """One selectable number-cell candidate and its Premium."""

    coord: Coordinate
    premium: int


@dataclass
class _ZiniBoardState:
    """Dynamic board state used by the G.ZiNi simulation."""

    snapshot: BoardSnapshot
    revealed: set[Coordinate]
    flagged_mines: set[Coordinate]

    @classmethod
    def create(cls, snapshot: BoardSnapshot):
        """Create an empty dynamic state for a finalized snapshot."""
        return cls(snapshot=snapshot, revealed=set(), flagged_mines=set())

    def reveal_unit(self, unit: _Static3BvUnit):
        """
        Reveal one static 3BV unit.

        Opening units reveal their zero-cell group plus the surrounding border
        ring.  Isolated units reveal only their representative number cell.
        """
        if unit.kind == _UNIT_OPENING:
            self.revealed.update(_opening_reveal_cells(self.snapshot, unit))
            return

        if unit.kind == _UNIT_ISOLATED:
            self.revealed.add(unit.representative)
            return

        raise ValueError(f"Unknown 3BV unit kind: {unit.kind}")

    def flag_mine(self, coord: Coordinate):
        """
        Mark a known mine as flagged.

        G.ZiNi has unfair prior knowledge, so this state tracks confirmed mine
        flags only.  Non-mine flags are not part of the 1st-pass algorithm.
        """
        if coord not in self.snapshot.mines:
            raise ValueError("G.ZiNi board state can only flag mine coordinates.")
        self.flagged_mines.add(coord)

    def all_safe_cells_revealed(self) -> bool:
        """Return whether every non-mine cell has been revealed."""
        return all(
            coord in self.revealed
            for coord in _safe_cells(self.snapshot)
        )


def _copy_zini_state(state: _ZiniBoardState) -> _ZiniBoardState:
    """Return an independent copy of one dynamic G.ZiNi board state."""
    return _ZiniBoardState(
        snapshot=state.snapshot,
        revealed=set(state.revealed),
        flagged_mines=set(state.flagged_mines),
    )


def _zini_state_key(state: _ZiniBoardState) -> _ZiniStateKey:
    """Return the immutable identity used to deduplicate search states."""
    return (
        frozenset(state.revealed),
        frozenset(state.flagged_mines),
    )


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


@dataclass
class _MinTieSearch:
    """Find the lowest-click path among equal maximum-Premium choices."""

    snapshot: BoardSnapshot
    context: _PremiumContext
    best_clicks: int
    best_moves: tuple[ZiniMove, ...]
    started_at: float
    max_seconds: float | None = None
    max_states: int | None = None
    best_cost_by_state: dict[_ZiniStateKey, int] = field(default_factory=dict)
    search_calls: int = 0
    timed_out: bool = False
    state_limited: bool = False

    def find_best_moves(self) -> tuple[ZiniMove, ...]:
        """Search maximum-Premium ties and return the best discovered path."""
        try:
            self._search(
                state=_ZiniBoardState.create(self.snapshot),
                clicks=0,
                moves=(),
            )
        except _MinTieSearchLimitReached:
            pass
        return self.best_moves

    def _search(
        self,
        state: _ZiniBoardState,
        clicks: int,
        moves: tuple[ZiniMove, ...],
    ):
        self.search_calls += 1

        if state.all_safe_cells_revealed():
            if clicks < self.best_clicks:
                self.best_clicks = clicks
                self.best_moves = moves
            return

        self._check_time_limit()

        if clicks >= self.best_clicks:
            return

        state_key = _zini_state_key(state)
        known_cost = self.best_cost_by_state.get(state_key)
        if known_cost is not None and known_cost <= clicks:
            return

        if (
            self.max_states is not None
            and len(self.best_cost_by_state) >= self.max_states
        ):
            self.state_limited = True
            raise _MinTieSearchLimitReached

        self.best_cost_by_state[state_key] = clicks

        candidates = _find_premium_candidates(state, self.context)
        best_premium = max(
            (candidate.premium for candidate in candidates),
            default=None,
        )

        if best_premium is None or best_premium < 0:
            self._search_fallback(state, state_key, clicks, moves)
            return

        best_candidates = sorted(
            (
                candidate
                for candidate in candidates
                if candidate.premium == best_premium
            ),
            key=lambda candidate: _top_left_key(candidate.coord),
        )
        next_branches: dict[
            _ZiniStateKey,
            tuple[_ZiniBoardState, ZiniMove],
        ] = {}

        for candidate in best_candidates:
            next_state = _copy_zini_state(state)
            move = _apply_premium_candidate(
                next_state,
                candidate,
                self.context,
            )

            next_key = _zini_state_key(next_state)
            if next_key == state_key:
                raise RuntimeError("G.ZiNi min-tie branch made no progress.")

            previous = next_branches.get(next_key)
            if previous is None or move.clicks_added < previous[1].clicks_added:
                next_branches[next_key] = (next_state, move)

        for next_state, move in next_branches.values():
            self._search(
                next_state,
                clicks + move.clicks_added,
                moves + (move,),
            )

    def _search_fallback(
        self,
        state: _ZiniBoardState,
        state_key: _ZiniStateKey,
        clicks: int,
        moves: tuple[ZiniMove, ...],
    ):
        target = _select_fallback_click_target(state, self.context)
        if target is None:
            raise ValueError(
                "G.ZiNi could not produce a fallback before solving."
            )

        next_state = _copy_zini_state(state)
        move = _click_fallback_cell(next_state, target, self.context)
        if _zini_state_key(next_state) == state_key:
            raise RuntimeError("G.ZiNi min-tie fallback made no progress.")

        self._search(
            next_state,
            clicks + move.clicks_added,
            moves + (move,),
        )

    def _check_time_limit(self):
        if (
            self.max_seconds is not None
            and perf_counter() - self.started_at >= self.max_seconds
        ):
            self.timed_out = True
            raise _MinTieSearchLimitReached


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
    if not snapshot.mines_placed:
        raise ValueError("Cannot calculate G.ZiNi before mines are placed.")
    if max_seconds is not None and max_seconds < 0:
        raise ValueError("max_seconds cannot be negative.")
    if max_states is not None and max_states < 0:
        raise ValueError("max_states cannot be negative.")

    started_at = perf_counter()
    context = _build_premium_context(snapshot)
    deterministic_moves = _run_g_zini_loop(
        _ZiniBoardState.create(snapshot),
        context,
    )
    deterministic_clicks = sum(
        move.clicks_added for move in deterministic_moves
    )
    search = _MinTieSearch(
        snapshot=snapshot,
        context=context,
        best_clicks=deterministic_clicks,
        best_moves=deterministic_moves,
        started_at=started_at,
        max_seconds=max_seconds,
        max_states=max_states,
    )
    moves = search.find_best_moves()
    result = ZiniResult(
        clicks=search.best_clicks,
        moves=moves,
    )

    return ZiniSearchResult(
        result=result,
        exact=not search.timed_out and not search.state_limited,
        timed_out=search.timed_out,
        state_limited=search.state_limited,
        elapsed_seconds=perf_counter() - started_at,
        unique_states=len(search.best_cost_by_state),
        search_calls=search.search_calls,
        best_clicks=search.best_clicks,
        deterministic_clicks=deterministic_clicks,
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
    search = _NeighborhoodBeamSearch(
        snapshot=snapshot,
        context=context,
        config=resolved_config,
        baseline=deterministic_result,
        started_at=started_at,
    )
    termination_reason = search.run()

    return ZiniAdvancedSearchResult(
        result=search.best.result,
        exact=False,
        termination_reason=termination_reason,
        elapsed_seconds=perf_counter() - started_at,
        evaluations=search.evaluations,
        generations=search.generations,
        best_clicks=search.best.result.clicks,
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


def _run_g_zini_loop(
    state: _ZiniBoardState,
    context: _PremiumContext,
) -> tuple[ZiniMove, ...]:
    """Run the G.ZiNi greedy loop until all safe cells are revealed."""
    max_moves = max(1, state.snapshot.width * state.snapshot.height * 4)
    moves: list[ZiniMove] = []

    for _ in range(max_moves):
        if state.all_safe_cells_revealed():
            return tuple(moves)

        before = (len(state.revealed), len(state.flagged_mines))
        move = _apply_next_g_zini_move(state, context)
        if move is None:
            raise ValueError("G.ZiNi could not produce a move before solving.")

        moves.append(move)
        after = (len(state.revealed), len(state.flagged_mines))
        if after == before and not state.all_safe_cells_revealed():
            raise RuntimeError("G.ZiNi move made no progress.")

    raise RuntimeError("G.ZiNi exceeded the safety move limit.")


def _extract_static_3bv_units(snapshot: BoardSnapshot) -> tuple[_Static3BvUnit, ...]:
    """
    Extract static 3BV units from a finalized board snapshot.

    Opening units are represented by the top-leftmost zero cell in the opening.
    The cells stored here are only the zero-cell group that identifies the 3BV
    unit; future reveal simulation must still reveal the surrounding border
    ring when an opening is clicked.  Border numbers are not independent 3BV
    units and are intentionally excluded.
    """
    analysis = analyze_board(snapshot)

    opening_cells_by_id: dict[int, list[Coordinate]] = {}
    isolated_units: list[_Static3BvUnit] = []

    for y in range(snapshot.height):
        for x in range(snapshot.width):
            cell_class = analysis.cell_class[y][x]
            coord = (x, y)

            if cell_class == CellClass.OPENING:
                opening_id = analysis.opening_id[y][x]
                opening_cells_by_id.setdefault(opening_id, []).append(coord)
            elif cell_class == CellClass.ISOLATED:
                isolated_units.append(
                    _Static3BvUnit(
                        kind=_UNIT_ISOLATED,
                        representative=coord,
                        cells=frozenset({coord}),
                    )
                )

    opening_units = [
        _Static3BvUnit(
            kind=_UNIT_OPENING,
            representative=min(cells, key=_top_left_key),
            cells=frozenset(cells),
            opening_id=opening_id,
        )
        for opening_id, cells in opening_cells_by_id.items()
    ]

    return tuple(
        sorted(
            [*opening_units, *isolated_units],
            key=lambda unit: _top_left_key(unit.representative),
        )
    )


def _build_premium_context(snapshot: BoardSnapshot) -> _PremiumContext:
    """Build static lookup data for Premium calculation."""
    analysis = analyze_board(snapshot)
    units = _extract_static_3bv_units(snapshot)

    return _PremiumContext(
        analysis=analysis,
        units=units,
        opening_units_by_id={
            unit.opening_id: unit
            for unit in units
            if unit.kind == _UNIT_OPENING and unit.opening_id is not None
        },
        isolated_cells=frozenset(
            unit.representative
            for unit in units
            if unit.kind == _UNIT_ISOLATED
        ),
    )


def _calculate_premium(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
) -> int:
    """
    Calculate the G.ZiNi Premium for one non-mine number candidate.

    Premium is an evaluation value for move selection, not a click count.  It
    must be returned as-is, including negative values.  Covered zero cells are
    not Premium candidates in this first-pass implementation.
    """
    if coord in state.snapshot.mines:
        raise ValueError("Cannot calculate Premium for a mine coordinate.")

    x, y = coord
    if state.snapshot.adjacent[y][x] == 0:
        raise ValueError("Premium candidates must be number cells.")

    premium = (
        _count_adjacent_covered_3bv(state, coord, context)
        - _count_adjacent_unflagged_mines(state, coord)
        - 1
    )
    if _is_covered_non_3bv(state, coord, context):
        premium -= 1
    return premium


def _count_adjacent_covered_3bv(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
) -> int:
    """
    Count distinct covered 3BV units adjacent to a candidate cell.

    Only neighbors are considered, so the candidate itself is never counted.
    Opening units are counted only when an adjacent covered zero cell belongs to
    that opening.  Adjacent covered border numbers do not count as opening 3BV
    by themselves, and repeated zero cells from the same opening count once.

    The later reveal/chord simulation must use the same adjacent-zero rule:
    if Premium counts an opening here, the move must actually reveal that
    opening's zero-cell unit; if Premium does not count it here, later logic
    must not assume the move solved it.
    """
    opening_ids: set[int] = set()
    isolated_cells: set[Coordinate] = set()

    for neighbor in _neighbors(state.snapshot, coord):
        if neighbor in state.revealed or neighbor in state.snapshot.mines:
            continue

        nx, ny = neighbor
        cell_class = context.analysis.cell_class[ny][nx]
        if cell_class == CellClass.OPENING:
            opening_id = context.analysis.opening_id[ny][nx]
            if opening_id in context.opening_units_by_id:
                opening_ids.add(opening_id)
        elif cell_class == CellClass.ISOLATED and neighbor in context.isolated_cells:
            isolated_cells.add(neighbor)

    return len(opening_ids) + len(isolated_cells)


def _count_adjacent_unflagged_mines(
    state: _ZiniBoardState,
    coord: Coordinate,
) -> int:
    """Count adjacent mines that have not already been flagged."""
    return sum(
        1
        for neighbor in _neighbors(state.snapshot, coord)
        if neighbor in state.snapshot.mines and neighbor not in state.flagged_mines
    )


def _is_covered_non_3bv(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
) -> bool:
    """Return whether coord is a covered border number cell."""
    if coord in state.revealed:
        return False

    x, y = coord
    return context.analysis.cell_class[y][x] == CellClass.BORDER


def _find_premium_candidates(
    state: _ZiniBoardState,
    context: _PremiumContext,
) -> tuple[_PremiumCandidate, ...]:
    """
    Calculate Premium candidates for the current board state.

    Candidates are non-mine number cells only.  Covered zero cells are excluded;
    opening fallback clicks are handled by a later step, not by Premium
    selection.
    """
    candidates = []
    for coord in _safe_cells(state.snapshot):
        x, y = coord
        if state.snapshot.adjacent[y][x] == 0:
            continue
        candidates.append(
            _PremiumCandidate(
                coord=coord,
                premium=_calculate_premium(state, coord, context),
            )
        )
    return tuple(candidates)


def _select_best_premium_candidate(
    state: _ZiniBoardState,
    context: _PremiumContext,
) -> _PremiumCandidate | None:
    """
    Select the highest-Premium candidate using top-leftmost tie-break.

    Negative Premium values are compared as normal integers.  If the board is
    already solved, or no number-cell candidates exist, return None and leave
    fallback handling to a later step.
    """
    if state.all_safe_cells_revealed():
        return None

    candidates = _find_premium_candidates(state, context)
    if not candidates:
        return None

    return min(
        candidates,
        key=lambda candidate: (-candidate.premium, _top_left_key(candidate.coord)),
    )


def _click_covered_candidate(
    state: _ZiniBoardState,
    candidate: _PremiumCandidate,
) -> ZiniMove:
    """
    Apply the click-only move for a covered number candidate.

    This helper intentionally does not flag or chord in the same iteration.
    Covered BORDER numbers reveal only their own coordinate here; opening flood
    reveal is handled only when a zero cell/opening is opened by later logic.
    """
    coord = candidate.coord
    if coord in state.revealed:
        raise ValueError("Covered candidate click requires an unrevealed cell.")
    if coord in state.snapshot.mines:
        raise ValueError("Covered candidate click cannot target a mine.")

    x, y = coord
    if state.snapshot.adjacent[y][x] == 0:
        raise ValueError("Covered candidate click requires a number cell.")

    state.revealed.add(coord)
    return ZiniMove(
        action=_ACTION_CLICK,
        x=x,
        y=y,
        premium=candidate.premium,
        clicks_added=1,
    )


def _flag_and_chord_uncovered_candidate(
    state: _ZiniBoardState,
    candidate: _PremiumCandidate,
    context: _PremiumContext,
) -> ZiniMove:
    """
    Apply flag + chord for an already revealed non-mine number candidate.

    This helper is only for the G.ZiNi branch where selected Premium is
    non-negative and the candidate is already uncovered. Click cost is the
    number of newly placed adjacent mine flags plus one chord click.
    """
    coord = candidate.coord
    if coord in state.snapshot.mines:
        raise ValueError("Flag+chord candidate cannot target a mine.")
    if coord not in state.revealed:
        raise ValueError("Flag+chord candidate must already be revealed.")
    if candidate.premium < 0:
        raise ValueError("Flag+chord candidate requires non-negative Premium.")

    x, y = coord
    if state.snapshot.adjacent[y][x] == 0:
        raise ValueError("Flag+chord candidate must be a number cell.")

    new_flags = _flag_adjacent_unflagged_mines(state, coord)
    _reveal_chord_neighbors(state, coord, context)

    return ZiniMove(
        action=_ACTION_FLAG_CHORD,
        x=x,
        y=y,
        premium=candidate.premium,
        clicks_added=new_flags + 1,
    )


def _apply_premium_candidate(
    state: _ZiniBoardState,
    candidate: _PremiumCandidate,
    context: _PremiumContext,
) -> ZiniMove:
    """Apply a selected Premium candidate using its current covered state."""
    if candidate.coord in state.revealed:
        return _flag_and_chord_uncovered_candidate(state, candidate, context)
    return _click_covered_candidate(state, candidate)


def _flag_adjacent_unflagged_mines(
    state: _ZiniBoardState,
    coord: Coordinate,
) -> int:
    """Flag adjacent mines that are not already flagged, returning new flags."""
    new_flags = 0
    for neighbor in _neighbors(state.snapshot, coord):
        if neighbor in state.snapshot.mines and neighbor not in state.flagged_mines:
            state.flag_mine(neighbor)
            new_flags += 1
    return new_flags


def _reveal_chord_neighbors(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
):
    """
    Reveal covered safe neighbors affected by a chord.

    Directly adjacent covered safe number cells, including BORDER numbers, are
    revealed as cells. Adjacent covered zero cells reveal their whole opening
    unit. Border-only contact does not reveal an opening unless a covered zero
    cell from that opening is directly adjacent.
    """
    opening_ids: set[int] = set()
    number_cells: set[Coordinate] = set()

    for neighbor in _neighbors(state.snapshot, coord):
        if neighbor in state.revealed or neighbor in state.snapshot.mines:
            continue

        nx, ny = neighbor
        cell_class = context.analysis.cell_class[ny][nx]
        if cell_class == CellClass.OPENING:
            opening_id = context.analysis.opening_id[ny][nx]
            if opening_id in context.opening_units_by_id:
                opening_ids.add(opening_id)
        elif cell_class in (CellClass.BORDER, CellClass.ISOLATED):
            number_cells.add(neighbor)

    for opening_id in opening_ids:
        state.reveal_unit(context.opening_units_by_id[opening_id])
    state.revealed.update(number_cells)


def _find_fallback_click_targets(
    state: _ZiniBoardState,
    context: _PremiumContext,
) -> tuple[Coordinate, ...]:
    """Return unresolved static 3BV targets in deterministic row-major order."""
    targets = []
    for unit in context.units:
        if unit.kind == _UNIT_OPENING:
            unrevealed_zero_cells = [
                coord for coord in unit.cells if coord not in state.revealed
            ]
            if unrevealed_zero_cells:
                targets.append(min(unrevealed_zero_cells, key=_top_left_key))
        elif unit.kind == _UNIT_ISOLATED and unit.representative not in state.revealed:
            targets.append(unit.representative)

    return tuple(sorted(targets, key=_top_left_key))


def _select_fallback_click_target(
    state: _ZiniBoardState,
    context: _PremiumContext,
) -> Coordinate | None:
    """Select the top-leftmost unresolved static 3BV unit target."""
    targets = _find_fallback_click_targets(state, context)
    return targets[0] if targets else None


def _click_fallback_cell(
    state: _ZiniBoardState,
    coord: Coordinate,
    context: _PremiumContext,
) -> ZiniMove:
    """
    Apply one fallback click to a covered safe cell.

    Number cells reveal only themselves.  Zero cells reveal their static opening
    unit, including the surrounding border ring, through state.reveal_unit().
    """
    if coord in state.snapshot.mines:
        raise ValueError("Fallback click cannot target a mine.")
    if coord in state.revealed:
        raise ValueError("Fallback click requires an unrevealed cell.")

    x, y = coord
    if state.snapshot.adjacent[y][x] == 0:
        opening_id = context.analysis.opening_id[y][x]
        unit = context.opening_units_by_id.get(opening_id)
        if unit is None:
            raise ValueError("Fallback zero click could not find opening unit.")
        state.reveal_unit(unit)
    else:
        state.revealed.add(coord)

    return ZiniMove(
        action=_ACTION_FALLBACK_CLICK,
        x=x,
        y=y,
        premium=None,
        clicks_added=1,
    )


def _apply_next_g_zini_move(
    state: _ZiniBoardState,
    context: _PremiumContext,
) -> ZiniMove | None:
    """
    Select and apply exactly one G.ZiNi move for the current state.

    This is a one-step orchestrator only.  It intentionally does not loop or
    calculate final G.ZiNi totals.
    """
    if state.all_safe_cells_revealed():
        return None

    candidate = _select_best_premium_candidate(state, context)
    if candidate is None or candidate.premium < 0:
        target = _select_fallback_click_target(state, context)
        if target is None:
            return None
        return _click_fallback_cell(state, target, context)

    return _apply_premium_candidate(state, candidate, context)


def _top_left_key(coord: Coordinate) -> TopLeftKey:
    """Return row-major sorting key for a coordinate stored as (x, y)."""
    x, y = coord
    return y, x


def _opening_reveal_cells(
    snapshot: BoardSnapshot,
    unit: _Static3BvUnit,
) -> frozenset[Coordinate]:
    """Return zero cells and adjacent safe border cells revealed by an opening."""
    reveal_cells = set(unit.cells)
    for coord in unit.cells:
        for neighbor in _neighbors(snapshot, coord):
            if neighbor not in snapshot.mines:
                reveal_cells.add(neighbor)
    return frozenset(reveal_cells)


def _safe_cells(snapshot: BoardSnapshot):
    """Yield all non-mine coordinates in row-major order."""
    for y in range(snapshot.height):
        for x in range(snapshot.width):
            coord = (x, y)
            if coord not in snapshot.mines:
                yield coord


def _neighbors(snapshot: BoardSnapshot, coord: Coordinate):
    """Yield in-bounds 8-way neighbor coordinates for a coordinate."""
    x, y = coord
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < snapshot.width and 0 <= ny < snapshot.height:
                yield nx, ny
