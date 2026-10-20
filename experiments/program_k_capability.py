"""Experimental Program-K local/exact semantic core; no policy or Engine access.

Slices 1/2 implement the bounded A/B/C local and D/E exact decision evidence.
The session retains mine identities plus minimal public lifecycle metadata. It
never retains inferred safes, probabilities, counts, components or proof archives.
The preceding observation is used only to reject public-state regression; all
inference uses the current observation.

This slice admits physical flags only after this owner has acquired their mine
identity. Separately supported V1 flags outside M require a later admission path;
P <= M is NOT a universal K-C invariant or a restriction on frozen K-CONTROL.
Continuation classification executes no action. No research stage is implemented.
"""

from dataclasses import dataclass
from fractions import Fraction

from core_engine import CellState, GameStatus
from experiments.program_k_oracles import ExactGlobalMineCertificate, LocalMineCertificate


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


@dataclass(frozen=True)
class ExactAnalysis:
    """Detached D/E counts; never stored on the session or reused next decision.

    K and Oracle B share arithmetic, but construct their informational inputs
    separately. Their agreement is representation evidence, not independent
    arithmetic corroboration. Oracle A supplies the bounded independent check.
    """

    unresolved_cells: tuple[Coordinate, ...]
    frontier_cells: tuple[Coordinate, ...]
    unconstrained_cells: tuple[Coordinate, ...]
    total_worlds: int
    mine_worlds: tuple[tuple[Coordinate, int], ...]
    G0: frozenset[Coordinate]
    G1: frozenset[Coordinate]
    minimum_risk: Fraction | None
    minimum_risk_cells: frozenset[Coordinate]
    shared_kernel_evidence: str = "SHARED-KERNEL REPRESENTATION EVIDENCE"
    kernel: str = "simple_probability.calculate_probabilities"


@dataclass(frozen=True)
class DecisionAnalysis:
    """Current-decision continuation evidence, not a physical action or plan.

    A later physical input expires this entire record as decision authority.
    Only M is retained by the session; callers may archive detached evidence.
    """

    observation: Observation
    num_mines: int
    local: LocalAnalysis
    phase_d: ExactAnalysis | None
    phase_e: ExactAnalysis | None
    phase_e_status: str
    after: Accounting
    exact_certificates: tuple[ExactGlobalMineCertificate, ...]
    continuation: str
    selection_safe_cells: frozenset[Coordinate]
    guess_target: Coordinate | None

    @property
    def phase_d_status(self) -> str:
        return "NOT_REACHED" if self.phase_d is None else "REACHED"


def _exact_evidence(total_worlds, mine_worlds, frontier, floating) -> ExactAnalysis:
    """Classify already validated integer counts, also used for E restriction."""
    minimum = min((count for _, count in mine_worlds), default=None)
    return ExactAnalysis(
        unresolved_cells=tuple(cell for cell, _ in mine_worlds),
        frontier_cells=frontier,
        unconstrained_cells=floating,
        total_worlds=total_worlds,
        mine_worlds=mine_worlds,
        G0=frozenset(cell for cell, count in mine_worlds if count == 0),
        G1=frozenset(cell for cell, count in mine_worlds if count == total_worlds),
        minimum_risk=None if minimum is None else Fraction(minimum, total_worlds),
        minimum_risk_cells=frozenset(
            cell for cell, count in mine_worlds if count == minimum
        ),
    )


def _exact_analysis(observation, num_mines, accounting) -> ExactAnalysis:
    # Lazy dependency keeps local inference independent of the exact layer.
    from simple_algorithm import InconsistentObservationError
    from simple_probability import calculate_probabilities

    # Q(M) is informational inference/accounting input ONLY. It is never an
    # actual physical observation or a source of physical CHORD eligibility.
    materialized = tuple(
        tuple(
            int(CellState.FLAGGED)
            if value == CellState.HIDDEN and (x, y) in accounting.M else value
            for x, value in enumerate(row)
        )
        for y, row in enumerate(observation)
    )
    try:
        result = calculate_probabilities(materialized, num_mines)
    except InconsistentObservationError as error:
        raise KIntegrityError("ZERO_WORLDS", "No consistent public exact worlds.") from error

    Z = result.total_worlds
    if type(Z) is not int or Z <= 0:
        raise KIntegrityError("EXACT_COUNTS", "Exact Z must be a positive integer.")
    counts = {}
    for item in result.probabilities:
        cell = item.coordinate
        if (
            type(cell) is not tuple or len(cell) != 2
            or any(type(value) is not int for value in cell)
            or cell not in accounting.U or cell in counts
        ):
            raise KIntegrityError("EXACT_DOMAIN", "Invalid/duplicate exact coordinate.")
        if (
            type(item.mine_worlds) is not int
            or type(item.total_worlds) is not int
            or item.total_worlds != Z or not 0 <= item.mine_worlds <= Z
        ):
            raise KIntegrityError("EXACT_COUNTS", "Invalid exact integer marginal.")
        counts[cell] = item.mine_worlds
    if counts.keys() != accounting.U:
        raise KIntegrityError("EXACT_DOMAIN", "Exact result omitted unresolved cells.")
    frontier = frozenset(cell for clue in accounting.constraints for cell in clue.Uc)
    expected_frontier = tuple(sorted(frontier, key=reading_order))
    expected_floating = tuple(sorted(accounting.U - frontier, key=reading_order))
    if (
        result.frontier_cells != expected_frontier
        or result.unconstrained_cells != expected_floating
    ):
        raise KIntegrityError("EXACT_DOMAIN", "Exact frontier/floating partition disagrees.")
    return _exact_evidence(
        Z, tuple((cell, counts[cell]) for cell in sorted(counts, key=reading_order)),
        expected_frontier, expected_floating,
    )


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
    """Own one game's M; retain the Slice-1 name/API for local-only inspection.

    ``validate`` checks only and does not advance the observation guard. Successful
    ``analyze_local`` or ``analyze_decision`` atomically commits acquired M and the
    current public guard. Rich certificates, safes and exact results leave through
    detached analysis records, never this owner. Start a new owner for each game.
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
        result = self._local_analysis(current)
        self._M = result.after.M
        self._previous = current
        return result

    def _local_analysis(self, current: Observation) -> LocalAnalysis:
        """Stage A/B/C without committing, so a failed D/E cannot partly commit."""
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
        return LocalAnalysis(
            before=before,
            after=after,
            acquired_mines=first.mine_cells,
            S_first=first.safe_cells,
            S_second_all=second.safe_cells,
            S_new=second.safe_cells - first.safe_cells,
            S_current=first.safe_cells | second.safe_cells,
            certificates=first.certificates,
        )

    def analyze_decision(self, observation: object, *, status: GameStatus) -> DecisionAnalysis:
        """Run bounded A/B/C, then D/E only after local-safe exhaustion.

        All G1 enter M simultaneously. E restricts D's counts without another
        exact call; every D-origin G0 survives. No supplementary local pass is
        performed. Classification/guess target is evidence for a later policy,
        not selection or execution of a physical input.
        """
        current = self._check_current(observation, status)
        local = self._local_analysis(current)
        phase_d = phase_e = None
        phase_e_status = "NOT_REACHED"
        exact_certificates = ()
        after = local.after
        safes = local.S_current
        guess_target = None
        if safes:
            continuation = "LOCAL_SAFE"
        else:
            phase_d = _exact_analysis(current, self._num_mines, local.after)
            # Every certificate uses the same pre-acquisition M1 and D evidence;
            # no member of the simultaneous G1 batch is another's premise.
            exact_certificates = tuple(
                ExactGlobalMineCertificate(
                    observation=current,
                    num_mines=self._num_mines,
                    target=cell,
                    retained_mines=local.after.M,
                    status=GameStatus.PLAYING,
                    total_worlds=phase_d.total_worlds,
                    mine_worlds=phase_d.mine_worlds,
                )
                for cell in sorted(phase_d.G1, key=reading_order)
            )
            after = _account(current, self._num_mines, local.after.M | phase_d.G1)
            if not after.U:
                raise KIntegrityError("EMPTY_U_PLAYING", "G1 exhausted U while PLAYING.")
            phase_e = _exact_evidence(
                phase_d.total_worlds,
                tuple(item for item in phase_d.mine_worlds if item[0] in after.U),
                tuple(cell for cell in phase_d.frontier_cells if cell in after.U),
                tuple(cell for cell in phase_d.unconstrained_cells if cell in after.U),
            )
            if phase_e.G0 != phase_d.G0 or phase_e.G1:
                raise KIntegrityError("EXACT_RESTRICTION", "Restriction changed certainty.")
            phase_e_status = "REACHED_CHANGED" if phase_d.G1 else "REACHED_NO_CHANGE"
            safes = phase_d.G0
            if safes:
                continuation = "EXACT_SAFE"
            else:
                if phase_e.minimum_risk is None or not 0 < phase_e.minimum_risk < 1:
                    raise KIntegrityError("EXACT_RISK", "Guess requires strictly uncertain risk.")
                continuation = "EXACT_GUESS"
                guess_target = min(phase_e.minimum_risk_cells, key=reading_order)
        result = DecisionAnalysis(
            observation=current,
            num_mines=self._num_mines,
            local=local,
            phase_d=phase_d,
            phase_e=phase_e,
            phase_e_status=phase_e_status,
            after=after,
            exact_certificates=exact_certificates,
            continuation=continuation,
            selection_safe_cells=safes,
            guess_target=guess_target,
        )
        self._M = after.M
        self._previous = current
        return result
