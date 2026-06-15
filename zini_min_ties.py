"""Internal bounded maximum-Premium tie search for G.ZiNi."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING

from board_snapshot import BoardSnapshot
from zini_core import (
    _PremiumContext,
    _ZiniBoardState,
    _ZiniStateKey,
    _apply_premium_candidate,
    _build_premium_context,
    _click_fallback_cell,
    _copy_zini_state,
    _find_premium_candidates,
    _run_g_zini_loop,
    _select_fallback_click_target,
    _top_left_key,
    _zini_state_key,
)

if TYPE_CHECKING:
    from zini_calculator import ZiniMove, ZiniSearchResult


class _MinTieSearchLimitReached(Exception):
    """Internal cooperative bounded-search stop signal."""


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


def _calculate_g_zini_min_ties_bounded(
    snapshot: BoardSnapshot,
    *,
    max_seconds: float | None = None,
    max_states: int | None = None,
) -> ZiniSearchResult:
    """Run bounded maximum-Premium tie exploration."""
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

    from zini_calculator import ZiniResult, ZiniSearchResult

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
