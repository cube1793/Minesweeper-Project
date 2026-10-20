"""Public-only certificates, bounded Oracle A, and materialized Oracle B.

Oracle A and direct local-rule checks do not import K or Stage-2 counting/accounting.
Oracle B lazily calls frozen Stage-2 exact counting on its own Q(M) construction;
agreement with K is SHARED-KERNEL REPRESENTATION EVIDENCE. Certificates are
detached public evidence, not additional retained K state.
Coordinates remain (x, y); ordered outputs use the reading-order key (y, x).
This module supplies unit-verification foundations, not an E0 qualification run.
"""

from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path

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


# P-8 is a separate timing-premise checker. Neither a private fixture PASS nor
# merely constructing this API qualifies the full frozen timing premise.
P8_GRID_WIDTH = 30
P8_GRID_HEIGHT = 16
P8_CELL_COUNT = P8_GRID_WIDTH * P8_GRID_HEIGHT
P8_EXPECTED_TRIPLE_COUNT = P8_CELL_COUNT * P8_CELL_COUNT * (P8_CELL_COUNT - 1)
P8_CHECKER_IDENTITY = "experiments.program_k_oracles.check_frozen_p8"
P8_CHECKER_VERSION = 1


def _p8_positive_table(table):
    """Reject mutable, nonrectangular, nonpositive and non-true-int inputs."""
    if (type(table) is not tuple or not table
            or type(table[0]) is not tuple or not table[0]
            or any(type(row) is not tuple or len(row) != len(table[0])
                   for row in table)
            or any(type(value) is not int or value <= 0
                   for row in table for value in row)):
        raise PublicProofError("P-8 needs an immutable positive true-int dx/dy table.")
    return table


def _p8_cells(cells, table):
    if type(cells) is not tuple or len(cells) < 2:
        raise PublicProofError("P-8 needs an immutable domain with at least two cells.")
    for cell in cells:
        _coordinate(cell, len(table), len(table[0]))
    if len(set(cells)) != len(cells):
        raise PublicProofError("P-8 coordinate domain contains duplicates.")
    return tuple(sorted(cells, key=_reading_order))


def _p8_table_digest(table):
    encoded = ",".join(str(value) for row in table for value in row).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _p8_displacement(start, end):
    return abs(end[0] - start[0]), abs(end[1] - start[1])


@dataclass(frozen=True)
class P8Witness:
    """One exact ordered triple; displacements/values follow cb, bv, cv order."""

    triple_index: int
    c: Coordinate
    b: Coordinate
    v: Coordinate
    displacements: tuple[Coordinate, Coordinate, Coordinate]
    table_values: tuple[int, int, int]
    gap: int

    def __post_init__(self):
        if type(self.triple_index) is not int or self.triple_index < 0:
            raise PublicProofError("P-8 witness index must be a nonnegative true int.")
        for cell in (self.c, self.b, self.v):
            if (type(cell) is not tuple or len(cell) != 2
                    or any(type(value) is not int or value < 0 for value in cell)):
                raise PublicProofError("P-8 witness coordinates must be immutable (x,y) ints.")
        expected = (_p8_displacement(self.c, self.b),
                    _p8_displacement(self.b, self.v),
                    _p8_displacement(self.c, self.v))
        if (self.b == self.v or type(self.displacements) is not tuple
                or any(type(item) is not tuple or len(item) != 2
                       or any(type(value) is not int or value < 0 for value in item)
                       for item in self.displacements)
                or self.displacements != expected
                or type(self.table_values) is not tuple or len(self.table_values) != 3
                or any(type(value) is not int or value <= 0 for value in self.table_values)
                or type(self.gap) is not int
                or self.gap != self.table_values[0] + self.table_values[1] - self.table_values[2]):
            raise PublicProofError("P-8 witness displacements, values or exact gap disagree.")


@dataclass(frozen=True)
class P8Result:
    """Immutable reconstructable scan evidence, including its actual value table.

    ``status`` is derived: incomplete coverage cannot become PASS even when all
    visited gaps are positive. A nonpositive authenticated prefix independently
    sets ``premise_failure``; interruption cannot erase that counterexample.
    A PRIVATE_BOUNDED_CHECK PASS says nothing about P-8 qualification.
    """

    scope: str
    table: tuple[tuple[int, ...], ...]
    cells: tuple[Coordinate, ...]
    expected_triple_count: int
    visited_triple_count: int
    complete: bool
    interruption_reason: str | None
    authentication_status: str
    profile_sha256: str | None
    table_sha256: str
    physical_model_id: str | None
    physical_profile_version: int | None
    timing_unit: str
    table_order: str
    checker_identity: str
    checker_version: int
    checker_source_sha256: str
    minimum_gap: int | None
    minimum_gap_witness: P8Witness | None
    zero_gap_count: int
    negative_gap_count: int
    counterexamples: tuple[P8Witness, ...]
    counterexample_limit: int

    def __post_init__(self):
        if any(type(value) is not str for value in (
                self.scope, self.authentication_status, self.table_sha256,
                self.timing_unit, self.table_order, self.checker_identity,
                self.checker_source_sha256)):
            raise PublicProofError("P-8 identity/status fields must be immutable strings.")
        _p8_positive_table(self.table)
        cells = _p8_cells(self.cells, self.table)
        if self.cells != cells:
            raise PublicProofError("P-8 evidence coordinates must be in (y,x) traversal order.")
        n = len(cells)
        if (type(self.expected_triple_count) is not int
                or self.expected_triple_count != n * n * (n - 1)
                or type(self.visited_triple_count) is not int
                or not 0 <= self.visited_triple_count <= self.expected_triple_count
                or type(self.complete) is not bool
                or self.complete != (self.visited_triple_count == self.expected_triple_count)
                or (self.complete and self.interruption_reason is not None)
                or (not self.complete and (type(self.interruption_reason) is not str
                                           or not self.interruption_reason))):
            raise PublicProofError("P-8 coverage/completion evidence is inconsistent.")
        for count in (self.zero_gap_count, self.negative_gap_count):
            if type(count) is not int or count < 0:
                raise PublicProofError("P-8 gap counts must be nonnegative true ints.")
        bad_count = self.zero_gap_count + self.negative_gap_count
        if bad_count > self.visited_triple_count:
            raise PublicProofError("P-8 nonpositive count exceeds visited triples.")
        if (type(self.counterexample_limit) is not int or self.counterexample_limit <= 0
                or type(self.counterexamples) is not tuple
                or len(self.counterexamples) != min(bad_count, self.counterexample_limit)
                or any(type(item) is not P8Witness or item.gap > 0
                       for item in self.counterexamples)
                or any(left.triple_index >= right.triple_index
                       for left, right in zip(self.counterexamples, self.counterexamples[1:]))):
            raise PublicProofError("P-8 counterexamples must be a deterministic bounded prefix.")
        if self.visited_triple_count == 0:
            if self.minimum_gap is not None or self.minimum_gap_witness is not None:
                raise PublicProofError("Unvisited P-8 evidence cannot fabricate a minimum.")
        elif (type(self.minimum_gap) is not int
              or type(self.minimum_gap_witness) is not P8Witness
              or self.minimum_gap != self.minimum_gap_witness.gap
              or (self.minimum_gap <= 0) != bool(bad_count)
              or (self.minimum_gap < 0) != bool(self.negative_gap_count)):
            raise PublicProofError("P-8 minimum/count evidence is inconsistent.")
        witnesses = self.counterexamples
        if self.minimum_gap_witness is not None:
            witnesses += (self.minimum_gap_witness,)
        positions = {cell: index for index, cell in enumerate(cells)}
        for witness in witnesses:
            if any(cell not in positions for cell in (witness.c, witness.b, witness.v)):
                raise PublicProofError("P-8 witness lies outside its recorded domain.")
            ci, bi, vi = (positions[cell] for cell in (witness.c, witness.b, witness.v))
            index = ci * n * (n - 1) + bi * (n - 1) + vi - (vi > bi)
            if (witness.triple_index != index or index >= self.visited_triple_count
                    or witness.table_values != tuple(self.table[dx][dy]
                                                     for dx, dy in witness.displacements)
                    or witness.gap < self.minimum_gap):
                raise PublicProofError("P-8 witness does not reconstruct from the table/prefix.")
        if (type(self.table_sha256) is not str
                or self.table_sha256 != _p8_table_digest(self.table)
                or self.table_order != "dx_major_dy_minor" or self.timing_unit != "us"
                or self.checker_identity != P8_CHECKER_IDENTITY
                or type(self.checker_version) is not int
                or self.checker_version != P8_CHECKER_VERSION
                or type(self.checker_source_sha256) is not str
                or len(self.checker_source_sha256) != 64
                or any(c not in "0123456789abcdef" for c in self.checker_source_sha256)):
            raise PublicProofError("P-8 table/checker identity is missing or malformed.")
        if self.scope == "FROZEN_P8":
            # Lazy import preserves independence of the public arithmetic and
            # certificate APIs from production inference/planning dependencies.
            from stage3_physical import MODEL_C_V1_IDENTITY, validate_timing_table

            identity = MODEL_C_V1_IDENTITY
            validate_timing_table(self.table)
            if (self.cells != tuple((x, y) for y in range(P8_GRID_HEIGHT)
                                    for x in range(P8_GRID_WIDTH))
                    or self.expected_triple_count != P8_EXPECTED_TRIPLE_COUNT
                    or self.authentication_status != "AUTHENTICATED"
                    or self.profile_sha256 != identity.physical_profile_sha256
                    or self.table_sha256 != identity.timing_table_sha256
                    or self.physical_model_id != identity.physical_model_id
                    or type(self.physical_profile_version) is not int
                    or self.physical_profile_version != identity.physical_profile_version):
                raise PublicProofError("Frozen P-8 evidence requires the full authenticated domain.")
        elif (self.scope != "PRIVATE_BOUNDED_CHECK"
              or self.authentication_status != "NOT_EVALUATED"
              or any(value is not None for value in (
                  self.profile_sha256, self.physical_model_id, self.physical_profile_version))):
            raise PublicProofError("Private fixture evidence cannot assert frozen authentication.")

    @property
    def status(self) -> str:
        if not self.complete:
            return "INCOMPLETE"
        return "FAIL" if self.zero_gap_count or self.negative_gap_count else "PASS"

    @property
    def completion_marker(self) -> str:
        return "COMPLETE" if self.complete else "INCOMPLETE"

    @property
    def premise_failure(self) -> bool:
        return self.scope == "FROZEN_P8" and bool(self.zero_gap_count or self.negative_gap_count)

    @property
    def failure_kind(self) -> str | None:
        if self.premise_failure:
            return "FROZEN_PREMISE_FAILURE"
        if self.zero_gap_count or self.negative_gap_count:
            return "SYNTHETIC_COUNTEREXAMPLE"
        return None

    @property
    def counterexamples_complete(self) -> bool:
        return len(self.counterexamples) == self.zero_gap_count + self.negative_gap_count

    @property
    def evidence_sha256(self) -> str:
        """Canonical evidence identity; includes all reconstructable premises."""
        payload = {**asdict(self), "status": self.status,
                   "completion_marker": self.completion_marker,
                   "premise_failure": self.premise_failure,
                   "failure_kind": self.failure_kind}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()


def _iter_p8_triples(cells):
    """The only exclusion is b == v; c == b and c == v remain in the domain."""
    for c in cells:
        for b in cells:
            for v in cells:
                if b != v:
                    yield c, b, v


def _scan_p8(table, cells, *, max_triples, interrupt_requested, counterexample_limit,
             scope, profile_identity=None):
    expected = len(cells) * len(cells) * (len(cells) - 1)
    if max_triples is not None and (type(max_triples) is not int or max_triples < 0):
        raise PublicProofError("P-8 private traversal limit must be a nonnegative true int.")
    if interrupt_requested is not None and not callable(interrupt_requested):
        raise PublicProofError("P-8 interruption hook must be callable.")
    if type(counterexample_limit) is not int or counterexample_limit <= 0:
        raise PublicProofError("P-8 counterexample limit must be a positive true int.")
    visited = zero_count = negative_count = 0
    minimum = minimum_witness = None
    counterexamples = []
    interruption_reason = None
    for c, b, v in _iter_p8_triples(cells):
        if max_triples is not None and visited >= max_triples:
            interruption_reason = "PRIVATE_TRIPLE_LIMIT"
            break
        if interrupt_requested is not None:
            # Cancellation is checked at a triple boundary, before any part of
            # that triple is counted. Callback failure preserves the prefix as
            # incomplete; it never converts interruption into positive evidence.
            try:
                interrupted = interrupt_requested()
                if type(interrupted) is not bool:
                    raise ValueError("Interruption hook must return a true boolean.")
            except (Exception, KeyboardInterrupt) as error:
                interruption_reason = f"INTERRUPTION_HOOK_ERROR:{type(error).__name__}"
                break
            if interrupted:
                interruption_reason = "INTERRUPTED"
                break
        cb = _p8_displacement(c, b)
        bv = _p8_displacement(b, v)
        cv = _p8_displacement(c, v)
        values = table[cb[0]][cb[1]], table[bv[0]][bv[1]], table[cv[0]][cv[1]]
        # No geometric surrogate, formula regeneration, added input charge or
        # tolerance. Each stored lookup already includes movement + target input.
        gap = values[0] + values[1] - values[2]
        witness = None
        if minimum is None or gap < minimum:
            witness = P8Witness(visited, c, b, v, (cb, bv, cv), values, gap)
            minimum, minimum_witness = gap, witness
        if gap <= 0:
            zero_count += gap == 0
            negative_count += gap < 0
            if len(counterexamples) < counterexample_limit:
                counterexamples.append(witness or P8Witness(
                    visited, c, b, v, (cb, bv, cv), values, gap,
                ))
        visited += 1
    complete = visited == expected
    return P8Result(
        scope=scope, table=table, cells=cells,
        expected_triple_count=expected, visited_triple_count=visited,
        complete=complete, interruption_reason=interruption_reason,
        authentication_status="AUTHENTICATED" if profile_identity is not None else "NOT_EVALUATED",
        profile_sha256=None if profile_identity is None else profile_identity.physical_profile_sha256,
        table_sha256=_p8_table_digest(table),
        physical_model_id=None if profile_identity is None else profile_identity.physical_model_id,
        physical_profile_version=None if profile_identity is None else profile_identity.physical_profile_version,
        timing_unit="us", table_order="dx_major_dy_minor",
        checker_identity=P8_CHECKER_IDENTITY, checker_version=P8_CHECKER_VERSION,
        checker_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        minimum_gap=minimum, minimum_gap_witness=minimum_witness,
        zero_gap_count=zero_count, negative_gap_count=negative_count,
        counterexamples=tuple(counterexamples), counterexample_limit=counterexample_limit,
    )


def _check_p8_table(table, *, cells=None, max_triples=None,
                    interrupt_requested=None, counterexample_limit=16) -> P8Result:
    """Private unit seam; synthetic/reduced evidence can never claim frozen P-8.

    Values are stored dx-major/dy-minor. If supplied, ``cells`` is an immutable
    reduced domain, sorted here by (y,x) without transposing stored coordinates.
    A partial/interrupted traversal is INCOMPLETE even for a positive table.
    """
    table = _p8_positive_table(table)
    if cells is None:
        cells = tuple((x, y) for y in range(len(table[0])) for x in range(len(table)))
    cells = _p8_cells(cells, table)
    return _scan_p8(table, cells, max_triples=max_triples,
                    interrupt_requested=interrupt_requested,
                    counterexample_limit=counterexample_limit,
                    scope="PRIVATE_BOUNDED_CHECK")


def check_frozen_p8(*, profile_path=None, table=None,
                    interrupt_requested=None, counterexample_limit=16) -> P8Result:
    """Authenticate and exhaustively check the fixed 110,361,600-triple domain.

    Calling without cancellation performs the full scan and needs separate
    execution authorization. Slice-6 unit tests may stop it immediately via
    ``interrupt_requested``; no range/subdomain parameter exists on this public
    API. The returned status cannot PASS until the full domain is visited.

    Exact profile bytes/metadata and all immutable table values are authenticated
    by the existing frozen APIs before traversal. A supplied table must itself
    be tuple-of-tuples, positive true ints, and match the authenticated profile.
    No calibration coefficients are accessed and no values are regenerated.
    """
    from stage3_physical import (
        MODEL_C_V1_IDENTITY, PROFILE_PATH, load_timing_table, validate_timing_table,
    )

    authenticated = load_timing_table(PROFILE_PATH if profile_path is None else profile_path)
    _p8_positive_table(authenticated)
    validate_timing_table(authenticated)
    if table is not None:
        _p8_positive_table(table)
        validate_timing_table(table)
        if table != authenticated:
            raise PublicProofError("P-8 table differs from the authenticated preserved profile.")
    cells = tuple((x, y) for y in range(P8_GRID_HEIGHT) for x in range(P8_GRID_WIDTH))
    return _scan_p8(authenticated, cells, max_triples=None,
                    interrupt_requested=interrupt_requested,
                    counterexample_limit=counterexample_limit,
                    scope="FROZEN_P8", profile_identity=MODEL_C_V1_IDENTITY)
