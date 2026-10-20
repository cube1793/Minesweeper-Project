"""Independent public-only local certificates and finite Program-K Oracle A.

These experimental checks do not import K accounting or Stage-2 inference/counting
code. Certificates are detached public evidence, not additional retained K state.
Coordinates remain (x, y); ordered outputs use the reading-order key (y, x).
This module supplies unit-verification foundations, not an E0 qualification run.
"""

from dataclasses import dataclass
from itertools import combinations

from core_engine import CellState, GameStatus


Coordinate = tuple[int, int]
PublicObservation = tuple[tuple[int, ...], ...]
ORACLE_A_MAX_VARIABLES = 16


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


def _verify_history(certificates):
    if type(certificates) not in (tuple, list):
        raise PublicProofError("Prior certificates must be an ordered list/tuple.")
    supported = set()
    previous = None
    num_mines = None
    for certificate in certificates:
        if type(certificate) is not LocalMineCertificate:
            raise PublicProofError("Only raw public local certificates are supported.")
        if num_mines is not None and certificate.num_mines != num_mines:
            raise PublicProofError("Proof history changed the public mine total.")
        _public_extension(previous, certificate.observation, supported)
        _check_local(certificate, supported)
        # The target becomes available only after its own independent check.
        supported.add(certificate.target)
        previous = certificate.observation
        num_mines = certificate.num_mines
    return frozenset(supported), previous, num_mines


def verify_local_certificate(
    certificate: LocalMineCertificate,
    *,
    prior_certificates: tuple[LocalMineCertificate, ...] = (),
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


def enumerate_public_worlds(
    observation,
    num_mines: int,
    *,
    status: GameStatus,
    logical_mines: frozenset[Coordinate] = frozenset(),
    proofs: tuple[LocalMineCertificate, ...] = (),
) -> OracleAResult:
    """Enumerate at most 16 unfixed public variables with integer-only counts.

    Every fixed physical/logical mine is separately supported by the supplied
    ordered public proof history. A zero-world result is reported as zero, not
    equality/PASS. Beyond the envelope, raise ORACLE_A_NOT_EVALUATED explicitly.
    No Engine instance, layout, evaluator data, or Stage-2/K helper is accepted.
    """
    grid = _public_grid(observation, num_mines, status)
    retained = _mine_set(logical_mines, grid)
    supported, previous, prior_mine_total = _verify_history(proofs)
    if prior_mine_total is not None and prior_mine_total != num_mines:
        raise PublicProofError("Oracle state changed the public mine total.")
    _public_extension(previous, grid, supported)
    _, _, fixed, unresolved, remaining = _supported_domains(
        grid, num_mines, retained, supported
    )
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
