"""Public-only certificates, bounded Oracle A, and materialized Oracle B.

Oracle A and direct local-rule checks do not import K or Stage-2 counting/accounting.
Oracle B lazily calls frozen Stage-2 exact counting on its own Q(M) construction;
agreement with K is SHARED-KERNEL REPRESENTATION EVIDENCE. Certificates are
detached public evidence, not additional retained K state.
Coordinates remain (x, y); ordered outputs use the reading-order key (y, x).
This module supplies unit-verification foundations, not an E0 qualification run.
"""

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from core_engine import CellState, GameStatus


Coordinate = tuple[int, int]
PublicObservation = tuple[tuple[int, ...], ...]
ORACLE_A_MAX_VARIABLES = 16
SHARED_KERNEL_EVIDENCE = "SHARED-KERNEL REPRESENTATION EVIDENCE"
FROZEN_EXACT_KERNEL = "simple_probability.calculate_probabilities"


class PublicProofError(ValueError):
    """A public input, certificate, or its ordered premises is invalid."""


class OracleANotEvaluated(ValueError):
    """The finite independent oracle did not evaluate this position."""

    status = "ORACLE_A_NOT_EVALUATED"

    def __init__(self, variable_count: int):
        self.variable_count = variable_count
        self.envelope = ORACLE_A_MAX_VARIABLES
        self.reason = "unfixed variable count exceeds the qualified finite envelope"
        super().__init__(
            f"{self.status}: {variable_count} unfixed variables exceed "
            f"the {self.envelope}-variable envelope."
        )


def _reading_order(cell: Coordinate) -> tuple[int, int]:
    return cell[1], cell[0]


def _public_grid(observation, num_mines: int, status: GameStatus) -> PublicObservation:
    # Gate status before reading even the shape of an observation-like object.
    if status is not GameStatus.PLAYING:
        raise PublicProofError("Only a PLAYING public observation is admissible.")
    if type(observation) not in (list, tuple) or not observation:
        raise PublicProofError("Public observation must be a nonempty list/tuple grid.")
    if type(observation[0]) not in (list, tuple) or not observation[0]:
        raise PublicProofError("Public observation must have nonempty list/tuple rows.")
    width = len(observation[0])
    rows = []
    for row in observation:
        if type(row) not in (list, tuple) or len(row) != width:
            raise PublicProofError("Public observation must be rectangular.")
        frozen_row = []
        for value in row:
            if type(value) not in (int, CellState) or (
                value not in (CellState.HIDDEN, CellState.FLAGGED)
                and not 0 <= value <= 8
            ):
                raise PublicProofError("Unsupported or answer-bearing public glyph.")
            frozen_row.append(int(value))
        rows.append(tuple(frozen_row))
    if type(num_mines) is not int or not 0 <= num_mines <= width * len(rows):
        raise PublicProofError("Public mine total is outside the board bounds.")
    return tuple(rows)


def _coordinate(cell, width: int, height: int) -> Coordinate:
    if (
        type(cell) is not tuple
        or len(cell) != 2
        or any(type(value) is not int for value in cell)
        or not 0 <= cell[0] < width
        or not 0 <= cell[1] < height
    ):
        raise PublicProofError("Coordinate must be an in-board (x, y) integer tuple.")
    return cell


def _mine_set(cells, grid: PublicObservation) -> frozenset[Coordinate]:
    if type(cells) not in (tuple, list, set, frozenset):
        raise PublicProofError("Mine premises must be a finite coordinate collection.")
    return frozenset(_coordinate(cell, len(grid[0]), len(grid)) for cell in cells)


def _neighbors(cell: Coordinate, grid: PublicObservation) -> frozenset[Coordinate]:
    x, y = cell
    return frozenset(
        (nx, ny)
        for ny in range(max(0, y - 1), min(len(grid), y + 2))
        for nx in range(max(0, x - 1), min(len(grid[0]), x + 2))
        if (nx, ny) != cell
    )


@dataclass(frozen=True)
class LocalMineCertificate:
    """Raw pre-acquisition premises; no K residual/classification is trusted.

    ``retained_mines`` is the M snapshot before this acquisition. Prior support
    certificates are supplied separately to the checker in acquisition order.
    A first-pass batch uses the same pre-acquisition snapshot for every target.
    """

    observation: PublicObservation
    num_mines: int
    clue: Coordinate
    target: Coordinate
    retained_mines: frozenset[Coordinate]
    status: GameStatus

    def __post_init__(self):
        grid = _public_grid(self.observation, self.num_mines, self.status)
        object.__setattr__(self, "observation", grid)
        object.__setattr__(self, "clue", _coordinate(self.clue, len(grid[0]), len(grid)))
        object.__setattr__(self, "target", _coordinate(self.target, len(grid[0]), len(grid)))
        object.__setattr__(self, "retained_mines", _mine_set(self.retained_mines, grid))


@dataclass(frozen=True)
class ExactGlobalMineCertificate:
    """Detached Phase-D evidence, before any member of the G1 batch is acquired.

    The full raw observation, public mine total and pre-acquisition M identify
    the premises without an answer-derived fingerprint. Claimed counts/reached
    status are checked, not trusted. This is a distinct origin from local proof.
    """

    observation: PublicObservation
    num_mines: int
    target: Coordinate
    retained_mines: frozenset[Coordinate]
    status: GameStatus
    total_worlds: int
    mine_worlds: tuple[tuple[Coordinate, int], ...]
    exact_reached: bool = True

    def __post_init__(self):
        grid = _public_grid(self.observation, self.num_mines, self.status)
        object.__setattr__(self, "observation", grid)
        object.__setattr__(self, "target", _coordinate(self.target, len(grid[0]), len(grid)))
        object.__setattr__(self, "retained_mines", _mine_set(self.retained_mines, grid))
        if type(self.total_worlds) is not int or type(self.exact_reached) is not bool:
            raise PublicProofError("Exact evidence requires integer Z and a boolean reached marker.")
        if type(self.mine_worlds) not in (tuple, list):
            raise PublicProofError("Exact marginals must be an ordered list/tuple.")
        counts = []
        for entry in self.mine_worlds:
            if type(entry) not in (tuple, list) or len(entry) != 2:
                raise PublicProofError("Each exact marginal needs a coordinate and numerator.")
            cell, numerator = entry
            cell = _coordinate(cell, len(grid[0]), len(grid))
            if type(numerator) is not int:
                raise PublicProofError("Exact numerators must be integers, never floats.")
            counts.append((cell, numerator))
        object.__setattr__(self, "mine_worlds", tuple(counts))


MineCertificate = LocalMineCertificate | ExactGlobalMineCertificate


@dataclass(frozen=True)
class ExactGlobalCertificateCheck:
    target: Coordinate
    total_worlds: int
    mine_worlds: int
    antecedents: tuple[Coordinate, ...]
    oracle_a_status: str
    oracle_a_variable_count: int
    oracle_a_envelope: int
    oracle_a_reason: str | None
    arithmetic_evidence: str


@dataclass(frozen=True)
class LocalCertificateCheck:
    """Independently reconstructed facts for the certificate's clue only."""

    target: Coordinate
    clue: Coordinate
    clue_value: int
    physical_flags: frozenset[Coordinate]
    logical_mines: frozenset[Coordinate]
    unresolved: frozenset[Coordinate]
    residual: int
    antecedents: tuple[Coordinate, ...]


@dataclass(frozen=True)
class OracleAResult:
    """Exact unreduced counts, with coordinates serialized in reading order."""

    total_worlds: int
    mine_worlds: tuple[tuple[Coordinate, int], ...]

    @property
    def unresolved_cells(self) -> tuple[Coordinate, ...]:
        return tuple(cell for cell, _ in self.mine_worlds)

    @property
    def G0(self) -> frozenset[Coordinate]:
        return frozenset(cell for cell, count in self.mine_worlds
                         if self.total_worlds > 0 and count == 0)

    @property
    def G1(self) -> frozenset[Coordinate]:
        return frozenset(cell for cell, count in self.mine_worlds
                         if self.total_worlds > 0 and count == self.total_worlds)

    @property
    def minimum_risk(self) -> Fraction | None:
        if self.total_worlds <= 0 or not self.mine_worlds:
            return None
        return Fraction(min(count for _, count in self.mine_worlds), self.total_worlds)

    @property
    def minimum_risk_cells(self) -> frozenset[Coordinate]:
        risk = self.minimum_risk
        return frozenset(cell for cell, count in self.mine_worlds
                         if risk is not None and Fraction(count, self.total_worlds) == risk)


@dataclass(frozen=True)
class OracleBResult:
    """Informational Q(M) and exact semantics; never actual physical state."""

    materialized_observation: PublicObservation
    unresolved_cells: tuple[Coordinate, ...]
    frontier_cells: tuple[Coordinate, ...]
    unconstrained_cells: tuple[Coordinate, ...]
    total_worlds: int
    mine_worlds: tuple[tuple[Coordinate, int], ...]
    G0: frozenset[Coordinate]
    G1: frozenset[Coordinate]
    minimum_risk: Fraction | None
    minimum_risk_cells: frozenset[Coordinate]
    shared_kernel_evidence: str = SHARED_KERNEL_EVIDENCE
    kernel: str = FROZEN_EXACT_KERNEL


def _supported_domains(grid, num_mines, retained_mines, supported):
    flags = frozenset(
        (x, y)
        for y, row in enumerate(grid)
        for x, value in enumerate(row)
        if value == CellState.FLAGGED
    )
    hidden = frozenset(
        (x, y)
        for y, row in enumerate(grid)
        for x, value in enumerate(row)
        if value == CellState.HIDDEN
    )
    if not retained_mines <= flags | hidden:
        raise PublicProofError("A retained mine is publicly revealed as safe.")
    fixed = flags | retained_mines
    if not fixed <= supported:
        raise PublicProofError("Every physical/logical fixed mine needs earlier public proof.")
    unresolved = hidden - retained_mines
    remaining = num_mines - len(fixed)
    if not 0 <= remaining <= len(unresolved):
        raise PublicProofError("Fixed public premises violate the global mine budget.")
    # Check every raw clue, independently of K's constraints or classification.
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            if 0 <= value <= 8:
                adjacent = _neighbors((x, y), grid)
                residual = value - len(adjacent & fixed)
                if not 0 <= residual <= len(adjacent & unresolved):
                    raise PublicProofError("Public clue residual is outside its bounds.")
    return flags, hidden, fixed, unresolved, remaining


def _public_extension(previous, current, supported):
    """Check chronological public consistency without predicting future reveals."""
    if previous is not None:
        if len(previous) != len(current) or len(previous[0]) != len(current[0]):
            raise PublicProofError("Proof history changed board dimensions.")
        for y, row in enumerate(previous):
            for x, value in enumerate(row):
                if value != CellState.HIDDEN and current[y][x] != value:
                    raise PublicProofError("Proof history regressed a clue or physical flag.")
    for x, y in supported:
        if current[y][x] not in (CellState.HIDDEN, CellState.FLAGGED):
            raise PublicProofError("A previously proved mine was publicly revealed as safe.")


def _check_local(certificate, supported) -> LocalCertificateCheck:
    grid = certificate.observation
    flags, _, _, unresolved, _ = _supported_domains(
        grid, certificate.num_mines, certificate.retained_mines, supported
    )
    x, y = certificate.clue
    value = grid[y][x]
    if not 0 <= value <= 8:
        raise PublicProofError("Certificate source must be a revealed clue.")
    adjacent = _neighbors(certificate.clue, grid)
    clue_flags = adjacent & flags
    clue_mines = adjacent & certificate.retained_mines
    antecedents = clue_flags | clue_mines
    neighborhood = adjacent & unresolved
    residual = value - len(antecedents)
    if certificate.target not in neighborhood:
        raise PublicProofError("Certificate target must be an unresolved neighbor.")
    if not neighborhood or residual != len(neighborhood):
        raise PublicProofError("Certificate does not satisfy the direct all-mines rule.")
    return LocalCertificateCheck(
        target=certificate.target,
        clue=certificate.clue,
        clue_value=value,
        physical_flags=clue_flags,
        logical_mines=clue_mines,
        unresolved=neighborhood,
        residual=residual,
        antecedents=tuple(sorted(antecedents, key=_reading_order)),
    )


def _check_exact(certificate, supported, *, independent_only=False):
    grid = certificate.observation
    _, _, fixed, unresolved, remaining = _supported_domains(
        grid, certificate.num_mines, certificate.retained_mines, supported
    )
    if not certificate.exact_reached or certificate.total_worlds <= 0:
        raise PublicProofError("Exact acquisition needs reached, positive-world evidence.")
    if certificate.target not in unresolved:
        raise PublicProofError("Exact target must be unresolved before acquisition.")
    # Reconstruct the normalized direct rules independently. At legitimate D,
    # every first-pass mine is already accounted for and C has no local safe.
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            if 0 <= value <= 8:
                adjacent = _neighbors((x, y), grid)
                neighborhood = adjacent & unresolved
                residual = value - len(adjacent & fixed)
                if neighborhood and residual in (0, len(neighborhood)):
                    raise PublicProofError("Exact layer preceded local certainty exhaustion.")
    variable_count = len(unresolved)
    if variable_count <= ORACLE_A_MAX_VARIABLES:
        actual = _enumerate_supported(grid, fixed, unresolved, remaining)
        coverage = "ORACLE_A_EVALUATED"
        reason = None
        evidence = "INDEPENDENT BOUNDED ARITHMETIC EVIDENCE"
    else:
        if independent_only:
            raise OracleANotEvaluated(variable_count)
        actual = _materialized_exact(grid, certificate.num_mines, certificate.retained_mines)
        coverage = "ORACLE_A_NOT_EVALUATED"
        reason = "unfixed variable count exceeds the qualified finite envelope"
        evidence = SHARED_KERNEL_EVIDENCE
    if (
        actual.total_worlds <= 0
        or certificate.total_worlds != actual.total_worlds
        or certificate.mine_worlds != actual.mine_worlds
        or dict(actual.mine_worlds).get(certificate.target) != actual.total_worlds
    ):
        raise PublicProofError("Exact certificate does not establish positive-world G1.")
    return ExactGlobalCertificateCheck(
        target=certificate.target,
        total_worlds=actual.total_worlds,
        mine_worlds=actual.total_worlds,
        antecedents=tuple(sorted(fixed, key=_reading_order)),
        oracle_a_status=coverage,
        oracle_a_variable_count=variable_count,
        oracle_a_envelope=ORACLE_A_MAX_VARIABLES,
        oracle_a_reason=reason,
        arithmetic_evidence=evidence,
    )


def _verify_history(certificates, *, independent_only=False):
    if type(certificates) not in (tuple, list):
        raise PublicProofError("Prior certificates must be an ordered list/tuple.")
    supported = set()
    previous = None
    num_mines = None
    for certificate in certificates:
        if type(certificate) not in (LocalMineCertificate, ExactGlobalMineCertificate):
            raise PublicProofError("Only local and exact-global public certificates are supported.")
        if num_mines is not None and certificate.num_mines != num_mines:
            raise PublicProofError("Proof history changed the public mine total.")
        _public_extension(previous, certificate.observation, supported)
        if type(certificate) is LocalMineCertificate:
            _check_local(certificate, supported)
        else:
            _check_exact(certificate, supported, independent_only=independent_only)
        # The target becomes available only after its own public proof check.
        supported.add(certificate.target)
        previous = certificate.observation
        num_mines = certificate.num_mines
    return frozenset(supported), previous, num_mines


def verify_local_certificate(
    certificate: LocalMineCertificate,
    *,
    prior_certificates: tuple[MineCertificate, ...] = (),
) -> LocalCertificateCheck:
    """Check a local acquisition from raw public premises and earlier proofs.

    Earlier certificates may have the same observation (simultaneous first-pass
    facts). Only identities explicitly in this certificate's pre-acquisition M
    or actual physical flags participate; ordering does not propagate a batch.
    This direct-rule checker does not claim complete-world satisfiability.
    """
    if type(certificate) is not LocalMineCertificate:
        raise PublicProofError("Expected a detached public local certificate.")
    supported, previous, num_mines = _verify_history(prior_certificates)
    if num_mines is not None and num_mines != certificate.num_mines:
        raise PublicProofError("Certificate changed the public mine total.")
    _public_extension(previous, certificate.observation, supported)
    return _check_local(certificate, supported)


def verify_exact_global_certificate(
    certificate: ExactGlobalMineCertificate,
    *,
    prior_certificates: tuple[MineCertificate, ...] = (),
) -> ExactGlobalCertificateCheck:
    """Verify pre-acquisition public G1 evidence and legitimacy of reaching D.

    Independent complete-world arithmetic is used within the 16-variable
    envelope. Larger proofs expose shared-kernel evidence and explicit Oracle-A
    non-evaluation. This checker never runs as part of live K acquisition.
    """
    if type(certificate) is not ExactGlobalMineCertificate:
        raise PublicProofError("Expected a detached public exact-global certificate.")
    supported, previous, num_mines = _verify_history(prior_certificates)
    if num_mines is not None and num_mines != certificate.num_mines:
        raise PublicProofError("Certificate changed the public mine total.")
    _public_extension(previous, certificate.observation, supported)
    return _check_exact(certificate, supported)


def _enumerate_supported(grid, fixed, unresolved, remaining) -> OracleAResult:
    """Independent arithmetic with already-checked public fixed-mine premises."""
    ordered = tuple(sorted(unresolved, key=_reading_order))
    if len(ordered) > ORACLE_A_MAX_VARIABLES:
        raise OracleANotEvaluated(len(ordered))
    clues = tuple(
        ((x, y), value)
        for y, row in enumerate(grid)
        for x, value in enumerate(row)
        if 0 <= value <= 8
    )
    total_worlds = 0
    numerators = {cell: 0 for cell in ordered}
    for selected in combinations(ordered, remaining):
        world_mines = fixed | frozenset(selected)
        if all(
            sum(
                abs(mx - x) <= 1 and abs(my - y) <= 1 and (mx, my) != (x, y)
                for mx, my in world_mines
            ) == value
            for (x, y), value in clues
        ):
            total_worlds += 1
            for cell in selected:
                numerators[cell] += 1
    return OracleAResult(
        total_worlds=total_worlds,
        mine_worlds=tuple((cell, numerators[cell]) for cell in ordered),
    )


def enumerate_public_worlds(
    observation,
    num_mines: int,
    *,
    status: GameStatus,
    logical_mines: frozenset[Coordinate] = frozenset(),
    proofs: tuple[MineCertificate, ...] = (),
) -> OracleAResult:
    """Enumerate at most 16 unfixed public variables with integer-only counts.

    Every fixed physical/logical mine is separately supported by the supplied
    ordered public proof history. A zero-world result is reported as zero, not
    equality/PASS. Beyond the envelope, raise ORACLE_A_NOT_EVALUATED explicitly.
    No Engine instance, layout, evaluator data, or Stage-2/K helper is accepted.
    """
    grid = _public_grid(observation, num_mines, status)
    retained = _mine_set(logical_mines, grid)
    # An exact ancestor outside A's envelope also prevents an independent
    # Oracle-A claim; never silently validate such a premise with Stage 2.
    supported, previous, prior_mine_total = _verify_history(proofs, independent_only=True)
    if prior_mine_total is not None and prior_mine_total != num_mines:
        raise PublicProofError("Oracle state changed the public mine total.")
    _public_extension(previous, grid, supported)
    _, _, fixed, unresolved, remaining = _supported_domains(
        grid, num_mines, retained, supported
    )
    return _enumerate_supported(grid, fixed, unresolved, remaining)


def _materialized_exact(grid, num_mines, retained) -> OracleBResult:
    # Independent from K's materialization and accounting. Only HIDDEN members
    # of M become informational flags; actual flags/clues and n are preserved.
    materialized = tuple(
        tuple(int(CellState.FLAGGED) if value == CellState.HIDDEN and (x, y) in retained
              else value for x, value in enumerate(row))
        for y, row in enumerate(grid)
    )
    unresolved = tuple(
        (x, y) for y, row in enumerate(materialized)
        for x, value in enumerate(row) if value == CellState.HIDDEN
    )
    from simple_probability import calculate_probabilities

    try:
        exact = calculate_probabilities(materialized, num_mines)
    except ValueError as error:
        raise PublicProofError(f"Materialized exact reference failed: {error}") from error
    if type(exact.total_worlds) is not int or exact.total_worlds <= 0:
        raise PublicProofError("Materialized reference requires positive integer Z.")
    counts = tuple(
        (_coordinate(item.coordinate, len(grid[0]), len(grid)), item.mine_worlds)
        for item in exact.probabilities
    )
    if (
        tuple(cell for cell, _ in counts) != unresolved
        or any(type(count) is not int or not 0 <= count <= exact.total_worlds
               for _, count in counts)
        or any(type(item.total_worlds) is not int or item.total_worlds != exact.total_worlds
               for item in exact.probabilities)
    ):
        raise PublicProofError("Materialized reference has invalid exact domain/counts.")
    frontier = tuple(cell for cell in unresolved if any(
        0 <= materialized[ny][nx] <= 8 for nx, ny in _neighbors(cell, materialized)
    ))
    frontier_set = frozenset(frontier)
    floating = tuple(cell for cell in unresolved if cell not in frontier_set)
    if exact.frontier_cells != frontier or exact.unconstrained_cells != floating:
        raise PublicProofError("Materialized reference has invalid frontier/floating domains.")
    minimum = min((count for _, count in counts), default=None)
    return OracleBResult(
        materialized_observation=materialized,
        unresolved_cells=unresolved,
        frontier_cells=frontier,
        unconstrained_cells=floating,
        total_worlds=exact.total_worlds,
        mine_worlds=counts,
        G0=frozenset(cell for cell, count in counts if count == 0),
        G1=frozenset(cell for cell, count in counts if count == exact.total_worlds),
        minimum_risk=None if minimum is None else Fraction(minimum, exact.total_worlds),
        minimum_risk_cells=frozenset(cell for cell, count in counts if count == minimum),
    )


def materialized_exact_reference(
    observation,
    num_mines: int,
    *,
    status: GameStatus,
    logical_mines: frozenset[Coordinate] = frozenset(),
    proofs: tuple[MineCertificate, ...] = (),
) -> OracleBResult:
    """Oracle B: independently materialize valid public premises and count.

    No scheduling/action selector is called. Q(M) is inference/accounting input
    only and supplies no physical FLAG/CHORD authority. K shares the frozen
    exact kernel, so this explicitly reports representation evidence only.
    """
    grid = _public_grid(observation, num_mines, status)
    retained = _mine_set(logical_mines, grid)
    supported, previous, prior_mine_total = _verify_history(proofs)
    if prior_mine_total is not None and prior_mine_total != num_mines:
        raise PublicProofError("Oracle state changed the public mine total.")
    _public_extension(previous, grid, supported)
    _supported_domains(grid, num_mines, retained, supported)
    return _materialized_exact(grid, num_mines, retained)
