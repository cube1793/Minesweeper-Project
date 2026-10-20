"""Experimental Program-K local semantic core; no policy or Engine access.

Slice 1 implements only direct local acquisition and A/B/C decision evidence.
The session retains mine identities plus minimal public lifecycle metadata. It
never retains inferred safes, probabilities, counts, components or proof archives.
The preceding observation is used only to reject public-state regression; all
inference uses the current observation.

This slice admits physical flags only after this owner has acquired their mine
identity. Separately supported V1 flags outside M require a later admission path;
P <= M is NOT a universal K-C invariant or a restriction on frozen K-CONTROL.
No action selection, exact-probability layer or research stage is implemented.
"""

from dataclasses import dataclass

from core_engine import CellState, GameStatus
from experiments.program_k_oracles import LocalMineCertificate


Coordinate = tuple[int, int]
Observation = tuple[tuple[int, ...], ...]


class KIntegrityError(ValueError):
    """Fail closed without repairing retained mine identities."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


def reading_order(cell: Coordinate) -> tuple[int, int]:
    """Ordering key only; the coordinate itself remains (x, y)."""
    return cell[1], cell[0]


@dataclass(frozen=True)
class ClueAccounting:
    source: Coordinate
    clue_value: int
    fixed_mines: frozenset[Coordinate]
    Uc: frozenset[Coordinate]
    rc: int


@dataclass(frozen=True)
class Accounting:
    """One immutable phase, not persistent inference state."""

    P: frozenset[Coordinate]
    H: frozenset[Coordinate]
    M: frozenset[Coordinate]
    J: frozenset[Coordinate]
    U: frozenset[Coordinate]
    b: int
    constraints: tuple[ClueAccounting, ...]


@dataclass(frozen=True)
class DirectPass:
    safe_cells: frozenset[Coordinate]
    mine_cells: frozenset[Coordinate]
    certificates: tuple[LocalMineCertificate, ...]


@dataclass(frozen=True)
class LocalAnalysis:
    """Current A/B/C evidence. Callers must expire it after a physical input."""

    before: Accounting
    after: Accounting
    acquired_mines: frozenset[Coordinate]
    S_first: frozenset[Coordinate]
    S_second_all: frozenset[Coordinate]
    S_new: frozenset[Coordinate]
    S_current: frozenset[Coordinate]
    certificates: tuple[LocalMineCertificate, ...]


def _snapshot(observation: object, width: int, height: int) -> Observation:
    # Deliberately no duck-typed Engine, snapshot, iterator or attribute adapter.
    if type(observation) not in (tuple, list) or len(observation) != height:
        raise KIntegrityError("PUBLIC_SHAPE", "Expected public rows of this session.")
    rows = []
    for row in observation:
        if type(row) not in (tuple, list) or len(row) != width:
            raise KIntegrityError("PUBLIC_SHAPE", "Wrong public row width.")
        values = []
        for value in row:
            if (
                type(value) not in (int, CellState)
                or (value not in (CellState.HIDDEN, CellState.FLAGGED)
                    and not 0 <= value <= 8)
            ):
                raise KIntegrityError("PUBLIC_GLYPH", "Unsupported public cell value.")
            values.append(int(value))
        rows.append(tuple(values))
    return tuple(rows)


def _account(
    observation: Observation, num_mines: int, mines: frozenset[Coordinate],
) -> Accounting:
    height, width = len(observation), len(observation[0])
    flags = frozenset(
        (x, y) for y, row in enumerate(observation)
        for x, value in enumerate(row) if value == CellState.FLAGGED
    )
    hidden = frozenset(
        (x, y) for y, row in enumerate(observation)
        for x, value in enumerate(row) if value == CellState.HIDDEN
    )
    if not mines <= flags | hidden:
        raise KIntegrityError("M_REVEALED", "A retained mine is no longer hidden/flagged.")
    if not flags <= mines:
        raise KIntegrityError(
            "UNSUPPORTED_FLAG", "Slice 1 requires prior owned-M proof for flags.",
        )
    fixed = flags | mines
    unresolved = hidden - mines
    budget = num_mines - len(fixed)
    if not 0 <= budget <= len(unresolved):
        raise KIntegrityError("MINE_BUDGET", "Invalid remaining public mine budget.")
    constraints = []
    for y, row in enumerate(observation):
        for x, value in enumerate(row):
            if not 0 <= value <= 8:
                continue
            neighbors = frozenset(
                (nx, ny)
                for ny in range(max(0, y - 1), min(height, y + 2))
                for nx in range(max(0, x - 1), min(width, x + 2))
                if (nx, ny) != (x, y)
            )
            adjacent_fixed = neighbors & fixed
            Uc = neighbors & unresolved
            rc = value - len(adjacent_fixed)
            if not 0 <= rc <= len(Uc):
                raise KIntegrityError(
                    "CLUE_RESIDUAL", f"Invalid residual {rc} at {(x, y)}.",
                )
            constraints.append(ClueAccounting((x, y), value, adjacent_fixed, Uc, rc))
    return Accounting(flags, hidden, mines, fixed, unresolved, budget, tuple(constraints))


def _direct_pass(
    accounting: Accounting, observation: Observation, num_mines: int,
) -> DirectPass:
    """Complete direct pass; no deductions are substituted within this pass."""
    safe_cells: set[Coordinate] = set()
    mine_cells: set[Coordinate] = set()
    sources: dict[Coordinate, Coordinate] = {}
    for clue in accounting.constraints:
        if clue.rc == 0:
            safe_cells.update(clue.Uc)
        elif clue.rc == len(clue.Uc):
            mine_cells.update(clue.Uc)
            for cell in clue.Uc:
                # Constraint order is screen reading order; retain its first proof.
                sources.setdefault(cell, clue.source)
    if safe_cells & mine_cells:
        raise KIntegrityError("CONFLICTING_FACTS", "Direct safe and mine sets overlap.")
    certificates = tuple(
        LocalMineCertificate(
            observation=observation,
            num_mines=num_mines,
            clue=sources[cell],
            target=cell,
            retained_mines=accounting.M,
            status=GameStatus.PLAYING,
        )
        for cell in sorted(mine_cells, key=reading_order)
    )
    return DirectPass(frozenset(safe_cells), frozenset(mine_cells), certificates)


class KLocalSession:
    """Own one game's M; create a new instance for every new game.

    ``validate`` checks only and does not advance the observation guard. Successful
    ``analyze_local`` atomically commits acquired M and the current public guard.
    Rich certificates and safe sets leave through LocalAnalysis, never this owner.
    A rejected terminal call closes the owner without reading terminal rows or
    changing M. Other integrity failures propagate; the caller must stop the run.

    This pure boundary cannot authenticate a caller's claimed PLAYING observation
    against an Engine. Later status-gated capture is still required by A-E1/A-E2.
    Only detached current public rows and scalar metadata are accepted here.
    """

    __slots__ = ("_width", "_height", "_num_mines", "_M", "_previous", "_closed")

    def __init__(self, width: int, height: int, num_mines: int):
        if any(type(value) is not int for value in (width, height, num_mines)):
            raise KIntegrityError("PUBLIC_METADATA", "Dimensions/mine total must be integers.")
        if width <= 0 or height <= 0 or not 0 <= num_mines <= width * height:
            raise KIntegrityError("PUBLIC_METADATA", "Invalid dimensions/mine total.")
        self._width, self._height, self._num_mines = width, height, num_mines
        self._M: frozenset[Coordinate] = frozenset()
        self._previous = tuple((int(CellState.HIDDEN),) * width for _ in range(height))
        self._closed = False

    @property
    def M(self) -> frozenset[Coordinate]:
        return self._M

    def _check_current(self, observation: object, status: GameStatus) -> Observation:
        # Status first: do not iterate or inspect any terminal observation payload.
        if status is GameStatus.WON or status is GameStatus.LOST:
            self._closed = True
            raise KIntegrityError("TERMINAL_INPUT", "K reasoning requires PLAYING.")
        if status is not GameStatus.PLAYING:
            raise KIntegrityError("PUBLIC_STATUS", "Explicit GameStatus.PLAYING required.")
        if self._closed:
            raise KIntegrityError("SESSION_CLOSED", "A terminated session cannot resume.")
        current = _snapshot(observation, self._width, self._height)
        for y, row in enumerate(self._previous):
            for x, old in enumerate(row):
                new = current[y][x]
                if old == CellState.FLAGGED and new != old:
                    raise KIntegrityError("UNFLAGGING", "A physical flag disappeared.")
                if 0 <= old <= 8 and new != old:
                    raise KIntegrityError("PUBLIC_REGRESSION", "A revealed clue changed/disappeared.")
        return current

    def validate(self, observation: object, *, status: GameStatus) -> Accounting:
        """Check retained M/current accounting without repair or acquisition."""
        current = self._check_current(observation, status)
        accounting = _account(current, self._num_mines, self._M)
        if not accounting.U:
            raise KIntegrityError("EMPTY_U_PLAYING", "No unresolved cell while PLAYING.")
        return accounting

    def analyze_local(self, observation: object, *, status: GameStatus) -> LocalAnalysis:
        """Exactly one complete direct pass, acquisition, and one second check."""
        current = self._check_current(observation, status)
        before = _account(current, self._num_mines, self._M)
        if not before.U:
            raise KIntegrityError("EMPTY_U_PLAYING", "No unresolved cell while PLAYING.")
        first = _direct_pass(before, current, self._num_mines)
        staged_mines = self._M | first.mine_cells
        after = _account(current, self._num_mines, staged_mines)
        second = _direct_pass(after, current, self._num_mines)
        if second.mine_cells:
            raise KIntegrityError(
                "SECOND_PASS_MINE", "Normalized second check found an unacquired mine.",
            )
        if not first.safe_cells <= second.safe_cells:
            raise KIntegrityError("SAFE_REGRESSION", "Normalization lost first-pass safes.")
        if not after.U:
            raise KIntegrityError("EMPTY_U_PLAYING", "Acquisition exhausted U while PLAYING.")
        result = LocalAnalysis(
            before=before,
            after=after,
            acquired_mines=first.mine_cells,
            S_first=first.safe_cells,
            S_second_all=second.safe_cells,
            S_new=second.safe_cells - first.safe_cells,
            S_current=first.safe_cells | second.safe_cells,
            certificates=first.certificates,
        )
        self._M = staged_mines
        self._previous = current
        return result
