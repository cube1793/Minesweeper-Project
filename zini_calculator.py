"""
zini_calculator.py
G.ZiNi calculator scaffolding for immutable board snapshots.

This module intentionally stays outside MinesweeperEngine.  It will grow into
the dynamic G.ZiNi simulation layer, while BoardSnapshot and board_analyzer keep
providing the static board facts.
"""

from dataclasses import dataclass, field
from time import perf_counter

from board_analyzer import BoardAnalysis, CellClass, analyze_board
from board_snapshot import BoardSnapshot, Coordinate


_UNIT_OPENING = "opening"
_UNIT_ISOLATED = "isolated"
_ACTION_CLICK = "click"
_ACTION_FLAG_CHORD = "flag_chord"
_ACTION_FALLBACK_CLICK = "fallback_click"


TopLeftKey = tuple[int, int]
_ZiniStateKey = tuple[frozenset[Coordinate], frozenset[Coordinate]]


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

        state_key = self._state_key(state)
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
            next_state = self._copy_state(state)
            if candidate.coord in next_state.revealed:
                move = _flag_and_chord_uncovered_candidate(
                    next_state,
                    candidate,
                    self.context,
                )
            else:
                move = _click_covered_candidate(next_state, candidate)

            next_key = self._state_key(next_state)
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

        next_state = self._copy_state(state)
        move = _click_fallback_cell(next_state, target, self.context)
        if self._state_key(next_state) == state_key:
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

    @staticmethod
    def _copy_state(state: _ZiniBoardState) -> _ZiniBoardState:
        return _ZiniBoardState(
            snapshot=state.snapshot,
            revealed=set(state.revealed),
            flagged_mines=set(state.flagged_mines),
        )

    @staticmethod
    def _state_key(state: _ZiniBoardState) -> _ZiniStateKey:
        return (
            frozenset(state.revealed),
            frozenset(state.flagged_mines),
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


def _select_fallback_click_target(
    state: _ZiniBoardState,
    context: _PremiumContext,
) -> Coordinate | None:
    """Select the top-leftmost unresolved static 3BV unit target."""
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

    if not targets:
        return None
    return min(targets, key=_top_left_key)


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

    if candidate.coord in state.revealed:
        return _flag_and_chord_uncovered_candidate(state, candidate, context)

    return _click_covered_candidate(state, candidate)


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
