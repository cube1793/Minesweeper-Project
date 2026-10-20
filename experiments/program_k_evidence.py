"""Pure Slice-6 public evidence, never solver state or research qualification.

No Engine, solver call, evaluator, fingerprint or answer is accepted here.  O-4
projects only the frozen semantic fields; timing and V1 candidate pools are not
part of that identity.  Effects, including terminal disclosures, are archives.
"""

from dataclasses import dataclass, fields, is_dataclass
from itertools import combinations

from core_engine import Action, CellState, GameStatus
from simple_algorithm import Constraint, InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision
from simple_probability import CellProbability, ProbabilityResult
from stage3_planner import RevealPlan, Stage3Decision


Coordinate = tuple[int, int]
Observation = tuple[tuple[int, ...], ...]
FLAG_EXACT_VARIABLE_LIMIT = 16


class EvidenceError(ValueError):
    """Malformed or incomplete public evidence cannot establish equality."""


def _need(condition, detail):
    if not condition:
        raise EvidenceError(detail)


def _integer(value, label, minimum=0):
    _need(type(value) is int and value >= minimum, label + " must be a true integer.")
    return value


def _coordinate(cell):
    _need(type(cell) is tuple and len(cell) == 2
          and all(type(v) is int for v in cell)
          and 0 <= cell[0] < 30 and 0 <= cell[1] < 16,
          "Expected an integer (x,y) coordinate inside the frozen grid.")
    return cell


def _ordered_cells(cells):
    _need(type(cells) is tuple, "An ordered coordinate sequence must be a tuple.")
    return tuple(_coordinate(cell) for cell in cells)


def _set_cells(cells):
    _need(type(cells) in (tuple, frozenset), "Expected immutable coordinate membership.")
    validated = tuple(_coordinate(cell) for cell in cells)
    _need(len(set(validated)) == len(validated), "Duplicate set coordinate.")
    return tuple(sorted(validated, key=lambda cell: (cell[1], cell[0])))


def _grid(rows, *, terminal=False):
    # Deliberately rejects ArchivalObservation, Engine, iterators and adapters.
    _need(type(rows) in (tuple, list) and 1 <= len(rows) <= 16,
          "Expected explicit public rows, not an archive or Engine.")
    _need(type(rows[0]) in (tuple, list) and 1 <= len(rows[0]) <= 30,
          "Expected nonempty public rows.")
    width = len(rows[0])
    allowed = tuple(CellState) if terminal else (CellState.HIDDEN, CellState.FLAGGED)
    _need(all(type(row) in (tuple, list) and len(row) == width for row in rows),
          "Public rows must be rectangular.")
    _need(all(type(value) in (int, CellState)
              and (value in allowed or 0 <= value <= 8)
              for row in rows for value in row), "Unsupported public glyph.")
    return tuple(tuple(int(value) for value in row) for row in rows)


@dataclass(frozen=True)
class MoveProjection:
    action: Action
    x: int
    y: int

    def __post_init__(self):
        _need(type(self.action) is Action, "Expected physical Action.")
        _coordinate((self.x, self.y))


@dataclass(frozen=True)
class ConstraintProjection:
    source: Coordinate
    remaining_mines: int
    hidden_cells: tuple[Coordinate, ...]

    def __post_init__(self):
        _coordinate(self.source)
        _integer(self.remaining_mines, "remaining_mines")
        object.__setattr__(self, "hidden_cells", _set_cells(self.hidden_cells))


@dataclass(frozen=True)
class DeterministicProjection:
    safe_cells: tuple[Coordinate, ...]
    mine_cells: tuple[Coordinate, ...]

    def __post_init__(self):
        object.__setattr__(self, "safe_cells", _set_cells(self.safe_cells))
        object.__setattr__(self, "mine_cells", _set_cells(self.mine_cells))


@dataclass(frozen=True)
class CellProbabilityProjection:
    coordinate: Coordinate
    mine_worlds: int
    total_worlds: int

    def __post_init__(self):
        _coordinate(self.coordinate)
        _integer(self.mine_worlds, "mine_worlds")
        _integer(self.total_worlds, "total_worlds", 1)
        _need(self.mine_worlds <= self.total_worlds,
              "mine_worlds cannot exceed total_worlds.")


@dataclass(frozen=True)
class ProbabilityProjection:
    total_worlds: int
    probabilities: tuple[CellProbabilityProjection, ...]
    frontier_cells: tuple[Coordinate, ...]
    unconstrained_cells: tuple[Coordinate, ...]

    def __post_init__(self):
        _integer(self.total_worlds, "total_worlds", 1)
        _need(type(self.probabilities) is tuple and all(
            type(item) is CellProbabilityProjection for item in self.probabilities),
            "Expected complete ordered immutable marginal sequence.")
        for item in self.probabilities:
            CellProbabilityProjection(item.coordinate, item.mine_worlds, item.total_worlds)
            _need(item.total_worlds == self.total_worlds,
                  "Every marginal must use the enclosing total_worlds.")
        coordinates = tuple(item.coordinate for item in self.probabilities)
        _need(len(set(coordinates)) == len(coordinates), "Duplicate marginal coordinate.")
        _ordered_cells(self.frontier_cells)
        _ordered_cells(self.unconstrained_cells)
        frontier, unconstrained = set(self.frontier_cells), set(self.unconstrained_cells)
        _need(len(frontier) == len(self.frontier_cells)
              and len(unconstrained) == len(self.unconstrained_cells),
              "Probability partitions cannot contain duplicate coordinates.")
        _need(not frontier & unconstrained and frontier | unconstrained == set(coordinates),
              "Frontier and unconstrained cells must partition the complete probability domain.")


@dataclass(frozen=True)
class V1EvidenceProjection:
    kind: DecisionKind
    move: MoveProjection
    constraints: tuple[ConstraintProjection, ...]
    deterministic_result: DeterministicProjection
    probability_result: ProbabilityProjection | None

    def __post_init__(self):
        _need(type(self.kind) is DecisionKind and type(self.move) is MoveProjection
              and type(self.constraints) is tuple
              and all(type(c) is ConstraintProjection for c in self.constraints)
              and type(self.deterministic_result) is DeterministicProjection
              and (self.probability_result is None
                   or type(self.probability_result) is ProbabilityProjection),
              "Missing or malformed frozen evidence fields.")


@dataclass(frozen=True)
class PlanProjection:
    actions: tuple[MoveProjection, ...]
    latency_us: int
    reveals: int

    def __post_init__(self):
        _need(type(self.actions) is tuple and bool(self.actions)
              and all(type(action) is MoveProjection for action in self.actions),
              "Expected ordered physical plan actions.")
        _integer(self.latency_us, "latency_us", 1)
        _integer(self.reveals, "reveals", 1)


@dataclass(frozen=True)
class V1DecisionProjection:
    move: MoveProjection
    evidence: V1EvidenceProjection
    plan: PlanProjection | None

    def __post_init__(self):
        _need(type(self.move) is MoveProjection
              and type(self.evidence) is V1EvidenceProjection
              and (self.plan is None or type(self.plan) is PlanProjection),
              "Missing frozen Stage3Decision fields.")
        _need(self.plan is None or self.plan.actions[0] == self.move,
              "A present plan must start with the selected physical move.")


def _move(move):
    _need(type(move) is SimpleMove, "Missing frozen move.")
    return MoveProjection(move.action, move.x, move.y)


def project_v1_decision(decision: Stage3Decision) -> V1DecisionProjection:
    """Detach every O-4 semantic field; preserve sequences and canonicalize sets."""
    _need(type(decision) is Stage3Decision, "Missing frozen Stage3Decision.")
    evidence = decision.evidence
    _need(type(evidence) is SimpleDecision, "Missing frozen SimpleDecision.")
    _need(type(evidence.constraints) is tuple and all(
        type(c) is Constraint for c in evidence.constraints), "Missing ordered constraints.")
    _need(type(evidence.deterministic_result) is InferenceResult,
          "Missing deterministic result.")
    deterministic = evidence.deterministic_result
    probability = evidence.probability_result
    projected_probability = None
    if probability is not None:
        _need(type(probability) is ProbabilityResult and type(probability.probabilities) is tuple
              and all(type(c) is CellProbability for c in probability.probabilities),
              "Malformed probability result.")
        projected_probability = ProbabilityProjection(
            probability.total_worlds,
            tuple(CellProbabilityProjection(c.coordinate, c.mine_worlds, c.total_worlds)
                  for c in probability.probabilities),
            probability.frontier_cells, probability.unconstrained_cells,
        )
    plan = decision.plan
    _need(plan is None or type(plan) is RevealPlan, "Malformed plan.")
    return V1DecisionProjection(
        _move(decision.move),
        V1EvidenceProjection(
            evidence.kind, _move(evidence.move),
            tuple(ConstraintProjection(c.source, c.remaining_mines,
                                       _set_cells(c.hidden_cells)) for c in evidence.constraints),
            DeterministicProjection(_set_cells(deterministic.safe_cells),
                                    _set_cells(deterministic.mine_cells)),
            projected_probability,
        ),
        None if plan is None else PlanProjection(
            tuple(_move(move) for move in plan.actions), plan.latency_us, plan.reveals),
    )


@dataclass(frozen=True)
class EvidenceMismatch:
    boundary: int
    path: str
    expected: object
    actual: object

    def __post_init__(self):
        _integer(self.boundary, "boundary")
        _need(type(self.path) is str and bool(self.path), "Mismatch needs an exact path.")
        _immutable(self.expected)
        _immutable(self.actual)


def _immutable(value):
    if type(value) in (int, str, bool, type(None), Action, GameStatus, DecisionKind):
        return
    if type(value) is tuple:
        for child in value:
            _immutable(child)
        return
    if type(value) in _EVIDENCE_TYPES:
        for field in fields(value):
            _immutable(getattr(value, field.name))
        return
    raise EvidenceError("Evidence contains unsupported or mutable data.")


@dataclass(frozen=True)
class EvidenceComparison:
    status: str
    boundary: int
    mismatches: tuple[EvidenceMismatch, ...] = ()
    detail: str = ""

    def __post_init__(self):
        _integer(self.boundary, "boundary")
        _need(type(self.status) is str and self.status in (
            "PASS", "FAIL", "INCOMPLETE", "NOT_REACHED", "NOT_EVALUATED"),
              "Unsupported comparison coverage.")
        _need(type(self.mismatches) is tuple
              and all(type(m) is EvidenceMismatch for m in self.mismatches),
              "Expected immutable mismatches.")
        _need(self.status != "PASS" or not self.mismatches,
              "Failed comparison cannot PASS.")
        _need(type(self.detail) is str, "Expected comparison detail.")


def _differences(left, right, boundary, path=""):
    if type(left) is not type(right):
        return (EvidenceMismatch(boundary, path or "decision", left, right),)
    if is_dataclass(left):
        return tuple(m for field in fields(left) for m in _differences(
            getattr(left, field.name), getattr(right, field.name), boundary,
            (path + "." if path else "") + field.name))
    if type(left) is tuple:
        result = ()
        if len(left) != len(right):
            result = (EvidenceMismatch(boundary, path + ".length", len(left), len(right)),)
        return result + tuple(m for index, (a, b) in enumerate(zip(left, right))
                              for m in _differences(a, b, boundary, f"{path}[{index}]"))
    return () if left == right else (EvidenceMismatch(boundary, path, left, right),)


def _checked_projection(value):
    """Reconstruct a supplied projection so absent nested fields cannot compare equal."""
    _need(type(value) is V1DecisionProjection, "Expected frozen V1 semantic projection.")

    def rebuild(item):
        if type(item) is tuple:
            return tuple(rebuild(child) for child in item)
        if type(item) in (MoveProjection, ConstraintProjection, DeterministicProjection,
                          CellProbabilityProjection, ProbabilityProjection,
                          V1EvidenceProjection, PlanProjection, V1DecisionProjection):
            return type(item)(**{field.name: rebuild(getattr(item, field.name))
                                 for field in fields(item)})
        _immutable(item)
        return item

    return rebuild(value)


def compare_v1_decisions(control, shadow, *, boundary: int) -> EvidenceComparison:
    """Bounded semantic comparison only; an absent noninitial decision is incomplete."""
    _integer(boundary, "boundary")
    try:
        left = (_checked_projection(control) if type(control) is V1DecisionProjection
                else project_v1_decision(control))
        right = (_checked_projection(shadow) if type(shadow) is V1DecisionProjection
                 else project_v1_decision(shadow))
        _immutable(left)
        _immutable(right)
    except (ValueError, TypeError, AttributeError) as error:
        return EvidenceComparison("INCOMPLETE", boundary, detail=str(error))
    mismatches = _differences(left, right, boundary)
    return EvidenceComparison("FAIL" if mismatches else "PASS", boundary, mismatches)


@dataclass(frozen=True)
class ShadowSoundnessEvidence:
    classification: str
    boundary: int
    implicated_boundary: int | None
    v1_decision: V1DecisionProjection | None
    safe_cells: tuple[Coordinate, ...]
    detail: str = ""

    def __post_init__(self):
        _integer(self.boundary, "boundary")
        _need(type(self.classification) is str and self.classification in (
            "SHADOW_SOUNDNESS_VIOLATION", "NO_DISCREPANCY", "NOT_EVALUATED"),
              "Unknown public shadow discrepancy classification.")
        _need(self.v1_decision is None or type(self.v1_decision) is V1DecisionProjection,
              "Expected a detached frozen V1 projection.")
        object.__setattr__(self, "safe_cells", _set_cells(self.safe_cells))
        _need(type(self.detail) is str, "Expected shadow discrepancy detail.")
        if self.implicated_boundary is not None:
            _integer(self.implicated_boundary, "implicated_boundary")
        _need((self.classification == "SHADOW_SOUNDNESS_VIOLATION")
              == (self.implicated_boundary == self.boundary),
              "A shadow contradiction must identify its exact implicated boundary.")
        _need(self.classification == "SHADOW_SOUNDNESS_VIOLATION"
              or self.implicated_boundary is None,
              "A nonviolation cannot implicate a shadow boundary.")
        if self.classification == "NOT_EVALUATED":
            _need(self.v1_decision is None, "Unevaluated checkpoint cannot claim V1 identity.")
        else:
            _need(self.v1_decision is not None, "Evaluated comparator requires frozen V1 evidence.")
        if self.classification == "SHADOW_SOUNDNESS_VIOLATION":
            _need(bool(self.safe_cells)
                  and self.v1_decision.evidence.kind is DecisionKind.PROBABILITY_GUESS,
                  "Public contradiction requires both a V1 guess and current shadow safety.")
        if (self.classification == "NO_DISCREPANCY" and self.v1_decision is not None
                and self.v1_decision.evidence.kind is DecisionKind.PROBABILITY_GUESS):
            _need(not self.safe_cells, "A safe-at-guess discrepancy cannot be suppressed.")


def compare_shadow_soundness(v1_decision, shadow_safe_cells, *, boundary: int):
    """Public discrepancy only, after the caller validates the sealed V1 input.

    No move is returned or changed. The runner owns shadow disable/containment.
    No hidden truth is needed to detect this frozen semantic contradiction.
    """
    _integer(boundary, "boundary")
    safe = _set_cells(shadow_safe_cells)
    if v1_decision is None:
        return ShadowSoundnessEvidence("NOT_EVALUATED", boundary, None, None, safe,
                                       "Initial input has no V1 decision.")
    decision = (_checked_projection(v1_decision) if type(v1_decision) is V1DecisionProjection
                else project_v1_decision(v1_decision))
    _immutable(decision)
    if decision.evidence.kind is not DecisionKind.PROBABILITY_GUESS:
        return ShadowSoundnessEvidence("NO_DISCREPANCY", boundary, None, decision, safe)
    probability = decision.evidence.probability_result
    _need(probability is not None and probability.probabilities
          and decision.move == decision.evidence.move and decision.move.action is Action.OPEN
          and all(0 < p.mine_worlds < p.total_worlds == probability.total_worlds
                  for p in probability.probabilities), "Invalid V1 probability-guess checkpoint.")
    return ShadowSoundnessEvidence(
        "SHADOW_SOUNDNESS_VIOLATION" if safe else "NO_DISCREPANCY", boundary,
        boundary if safe else None, decision, safe,
        "Current shadow safe certainty contradicts the sealed V1 guess." if safe else "",
    )


@dataclass(frozen=True)
class ExternalV1FlagProvenance:
    """An external physical FLAG antecedent, explicitly never a K-owned M fact."""

    observation: Observation
    num_mines: int
    decision: V1DecisionProjection
    move: MoveProjection
    boundary: int
    input_index: int
    prior_flags: tuple["ExternalV1FlagProvenance", ...] = ()
    origin: str = "EXTERNAL_V1_PHYSICAL_FLAG"
    enters_M: bool = False

    def __post_init__(self):
        object.__setattr__(self, "observation", _grid(self.observation))
        _integer(self.num_mines, "num_mines")
        _integer(self.boundary, "boundary", 1)
        _integer(self.input_index, "input_index", 1)
        _need(type(self.decision) is V1DecisionProjection and type(self.move) is MoveProjection
              and type(self.prior_flags) is tuple
              and all(type(p) is ExternalV1FlagProvenance for p in self.prior_flags),
              "Expected detached V1 FLAG evidence and ordered antecedents.")
        _need(type(self.origin) is str and self.origin == "EXTERNAL_V1_PHYSICAL_FLAG"
              and self.enters_M is False,
              "External V1 FLAG provenance cannot become M.")


def make_v1_flag_provenance(observation, decision, *, num_mines, boundary,
                            input_index=None, prior_flags=()):
    projection = project_v1_decision(decision)
    return ExternalV1FlagProvenance(
        _grid(observation), num_mines, projection, projection.move, boundary,
        boundary if input_index is None else input_index, tuple(prior_flags),
    )


def _public_constraints(observation):
    result = []
    width, height = len(observation[0]), len(observation)
    for y, row in enumerate(observation):
        for x, value in enumerate(row):
            if not 0 <= value <= 8:
                continue
            adjacent = tuple((nx, ny)
                             for ny in range(max(0, y - 1), min(height, y + 2))
                             for nx in range(max(0, x - 1), min(width, x + 2))
                             if (nx, ny) != (x, y))
            hidden = tuple(c for c in adjacent if observation[c[1]][c[0]] == CellState.HIDDEN)
            remaining = value - sum(observation[ny][nx] == CellState.FLAGGED for nx, ny in adjacent)
            _need(0 <= remaining <= len(hidden), "Invalid public clue residual.")
            result.append(ConstraintProjection((x, y), remaining, hidden))
    return tuple(result)


def verify_v1_flag_provenance(record) -> EvidenceComparison:
    """Independently check public V1 FLAG support, without invoking any solver.

    Local records reconstruct the complete direct-rule evidence. Exact records
    additionally reconstruct all public worlds up to 16 HIDDEN cells; above that
    envelope the result is explicitly NOT_EVALUATED, never arithmetic PASS.
    Earlier physical FLAG premises are checked separately from any K certificate.
    """
    return _verify_v1_flag_provenance(record, {})


def _verify_v1_flag_provenance(record, checked):
    # Shared immutable antecedents are checked once per audit invocation. The
    # object identity is only a work cache, never an evidence equality premise.
    if id(record) in checked:
        return checked[id(record)]
    result = _check_v1_flag_provenance(record, checked)
    checked[id(record)] = result
    return result


def _check_v1_flag_provenance(record, checked):
    boundary = record.boundary if type(record) is ExternalV1FlagProvenance else 0
    try:
        _need(type(record) is ExternalV1FlagProvenance, "Missing external V1 FLAG record.")
        _immutable(record)
        ExternalV1FlagProvenance(**{field.name: getattr(record, field.name) for field in fields(record)})
        observation, evidence = record.observation, _checked_projection(record.decision).evidence
        width, height = len(observation[0]), len(observation)
        _need(record.boundary == record.input_index, "FLAG boundary/input index differ.")
        move = record.move
        _need(move == record.decision.move and move.action is Action.FLAG
              and move.x < width and move.y < height
              and observation[move.y][move.x] == CellState.HIDDEN,
              "FLAG must be the selected input at a current HIDDEN target.")
        _need(0 <= record.num_mines < width * height, "Invalid public mine total.")
        flags = {(x, y) for y, row in enumerate(observation) for x, glyph in enumerate(row)
                 if glyph == CellState.FLAGGED}
        hidden = tuple((x, y) for y, row in enumerate(observation) for x, glyph in enumerate(row)
                       if glyph == CellState.HIDDEN)
        budget = record.num_mines - len(flags)
        _need(0 <= budget <= len(hidden), "Invalid remaining public mine budget.")
        prior = {}
        last_index = -1
        for antecedent in record.prior_flags:
            _need(last_index < antecedent.input_index < record.input_index,
                  "FLAG antecedents must be earlier and ordered.")
            last_index = antecedent.input_index
            _need(antecedent.num_mines == record.num_mines
                  and len(antecedent.observation) == height
                  and len(antecedent.observation[0]) == width,
                  "FLAG antecedent belongs to different public metadata.")
            # Earlier revealed clues must still exist, without public regression.
            _need(all(old == CellState.HIDDEN or old == observation[y][x]
                      for y, row in enumerate(antecedent.observation)
                      for x, old in enumerate(row)), "FLAG antecedent public history regressed.")
            result = _verify_v1_flag_provenance(antecedent, checked)
            if result.status != "PASS":
                return EvidenceComparison(result.status, boundary, detail="FLAG antecedent: " + result.detail)
            cell = (antecedent.move.x, antecedent.move.y)
            _need(cell not in prior, "Duplicate physical FLAG antecedent.")
            prior[cell] = antecedent
        _need(set(prior) == flags, "Every physical FLAG needs its separate public V1 antecedent.")
        constraints = _public_constraints(observation)
        _need(evidence.constraints == constraints, "Frozen evidence constraints differ from public clues.")
        safes = {cell for clue in constraints if clue.remaining_mines == 0 for cell in clue.hidden_cells}
        mines = {cell for clue in constraints if clue.remaining_mines == len(clue.hidden_cells)
                 and clue.hidden_cells for cell in clue.hidden_cells}
        _need(not safes & mines and evidence.deterministic_result == DeterministicProjection(
            _set_cells(frozenset(safes)), _set_cells(frozenset(mines))),
            "Frozen direct-rule evidence disagrees with public reconstruction.")
        target = (move.x, move.y)
        if evidence.kind is DecisionKind.LOCAL_DETERMINISTIC:
            _need(evidence.probability_result is None and target in mines,
                  "Local FLAG lacks direct public mine support.")
            recommendation = min(mines, key=lambda c: (c[1], c[0]))
            _need(evidence.move == MoveProjection(Action.FLAG, *recommendation),
                  "Local recommendation differs from frozen reading-order mine choice.")
            return EvidenceComparison("PASS", boundary, detail="PUBLIC_V1_LOCAL_FLAG_EVIDENCE")
        _need(evidence.kind is DecisionKind.GLOBAL_CERTAINTY and not safes and not mines,
              "FLAG is not on a legitimate V1 exact-certainty path.")
        probability = evidence.probability_result
        _need(probability is not None, "Exact FLAG is missing its complete probability evidence.")
        _need(tuple(p.coordinate for p in probability.probabilities) == hidden,
              "Exact evidence omits/reorders public HIDDEN cells.")
        frontier = {cell for clue in constraints for cell in clue.hidden_cells}
        _need(probability.frontier_cells == _set_cells(frozenset(frontier))
              and probability.unconstrained_cells == tuple(c for c in hidden if c not in frontier),
              "Exact public frontier/floating partition differs.")
        _need(all(0 <= p.mine_worlds <= p.total_worlds == probability.total_worlds
                  for p in probability.probabilities), "Invalid exact marginal counts.")
        certain = tuple(p.coordinate for p in probability.probabilities
                        if p.mine_worlds == p.total_worlds)
        _need(target in certain and evidence.move == MoveProjection(Action.FLAG, *certain[0]),
              "Exact FLAG is not supported by its V1 certain-mine evidence.")
        if len(hidden) > FLAG_EXACT_VARIABLE_LIMIT:
            return EvidenceComparison("NOT_EVALUATED", boundary,
                                      detail="Independent exact FLAG check exceeds 16 public variables.")
        total, counts = 0, {cell: 0 for cell in hidden}
        for assignment in combinations(hidden, budget):
            chosen = frozenset(assignment)
            if all(len(chosen.intersection(clue.hidden_cells)) == clue.remaining_mines
                   for clue in constraints):
                total += 1
                for cell in chosen:
                    counts[cell] += 1
        _need(total > 0 and probability.total_worlds == total and all(
            p.mine_worlds == counts[p.coordinate] and p.total_worlds == total
            for p in probability.probabilities), "Exact FLAG counts disagree with public complete worlds.")
        return EvidenceComparison("PASS", boundary, detail="INDEPENDENT_BOUNDED_PUBLIC_V1_EXACT_FLAG")
    except (ValueError, TypeError, AttributeError) as error:
        return EvidenceComparison("FAIL", boundary, detail=str(error))


@dataclass(frozen=True)
class ArchivalObservation:
    """A non-sequence archive tag: never accepted by a solver/public-proof API."""

    rows: Observation
    status: GameStatus
    archival_only: bool = True

    def __post_init__(self):
        _need(type(self.status) is GameStatus and self.archival_only is True,
              "Archival status and segregation marker are required.")
        object.__setattr__(self, "rows", _grid(self.rows, terminal=self.status is not GameStatus.PLAYING))


@dataclass(frozen=True)
class PublicEffectRecord:
    input_index: int
    status_before: GameStatus
    before_observation: Observation
    move: MoveProjection
    status_after: GameStatus
    after_observation: ArchivalObservation
    safe_cells_opened_delta: int
    explicit_flag_delta: int
    cursor_before: Coordinate
    cursor_after: Coordinate
    modeled_action_us: int
    capture_method: str
    archival_only: bool = True

    def __post_init__(self):
        _integer(self.input_index, "input_index")
        _need(self.status_before is GameStatus.PLAYING and type(self.status_after) is GameStatus,
              "Effects require preinput PLAYING and explicit postinput status.")
        object.__setattr__(self, "before_observation", _grid(self.before_observation))
        _need(type(self.move) is MoveProjection and type(self.after_observation) is ArchivalObservation
              and self.after_observation.status is self.status_after and self.archival_only is True,
              "After-effects are explicitly segregated archival data.")
        object.__setattr__(self, "move", MoveProjection(self.move.action, self.move.x, self.move.y))
        object.__setattr__(self, "after_observation", ArchivalObservation(
            self.after_observation.rows, self.after_observation.status,
            self.after_observation.archival_only))
        _coordinate(self.cursor_before)
        _coordinate(self.cursor_after)
        _integer(self.modeled_action_us, "modeled_action_us", 1)
        _integer(self.safe_cells_opened_delta, "safe_cells_opened_delta")
        _integer(self.explicit_flag_delta, "explicit_flag_delta")
        _need(type(self.capture_method) is str and self.capture_method in (
            "STATUS_GATED_ACTUAL_EXECUTION", "INDEPENDENT_REPLAY"),
              "CONTROL public capture method must be explicit.")
        before, after = self.before_observation, self.after_observation.rows
        _need(len(before) == len(after) and len(before[0]) == len(after[0]),
              "Effect dimensions differ.")
        _need(self.move.x < len(before[0]) and self.move.y < len(before)
              and self.cursor_before[0] < len(before[0]) and self.cursor_before[1] < len(before)
              and self.cursor_after == (self.move.x, self.move.y), "Effect cursor/target mismatch.")
        safe = sum(old in (CellState.HIDDEN, CellState.FLAGGED) and 0 <= new <= 8
                   for a, b in zip(before, after) for old, new in zip(a, b))
        _need(self.safe_cells_opened_delta == safe
              and self.explicit_flag_delta == int(self.move.action is Action.FLAG),
              "Public deltas differ from frozen physical-input convention.")


def make_public_effect(before, move, after, *, input_index, status_after, cursor_before,
                       modeled_action_us, capture_method="STATUS_GATED_ACTUAL_EXECUTION"):
    before = _grid(before)
    archived = ArchivalObservation(after, status_after)
    safe = sum(old in (CellState.HIDDEN, CellState.FLAGGED) and 0 <= new <= 8
               for a, b in zip(before, archived.rows) for old, new in zip(a, b))
    projected = _move(move)
    return PublicEffectRecord(input_index, GameStatus.PLAYING, before, projected, status_after,
                              archived, safe, int(move.action is Action.FLAG), cursor_before,
                              (move.x, move.y), modeled_action_us, capture_method)


def compare_public_effects(control, shadow, *, boundary=None):
    index = control.input_index if boundary is None and type(control) is PublicEffectRecord else boundary
    index = 0 if index is None else index
    if type(control) is not PublicEffectRecord or type(shadow) is not PublicEffectRecord:
        return EvidenceComparison("INCOMPLETE", index, detail="Missing public effect record.")
    try:
        for record in (control, shadow):
            PublicEffectRecord(**{field.name: getattr(record, field.name) for field in fields(record)})
    except (ValueError, TypeError, AttributeError) as error:
        return EvidenceComparison("INCOMPLETE", index, detail=str(error))
    mismatches = tuple(m for m in _differences(control, shadow, index)
                       if m.path != "capture_method")
    return EvidenceComparison("FAIL" if mismatches else "PASS", index, mismatches)


def validate_public_effect_stream(records, *, complete: bool):
    """Reconstruct initial through final input; terminal rows stay archival."""
    _need(type(complete) is bool, "Explicit completion marker required.")
    if type(records) is not tuple or not records:
        return EvidenceComparison("INCOMPLETE", 0, detail="No complete physical input evidence.")
    try:
        for index, record in enumerate(records):
            _need(type(record) is PublicEffectRecord, "Missing public effect input.")
            # Reconstruct invokes the invariant checks even on manually corrupted objects.
            PublicEffectRecord(**{field.name: getattr(record, field.name) for field in fields(record)})
            _need(record.input_index == index, "Physical input indices must be contiguous from zero.")
            if index == 0:
                _need(record.move == MoveProjection(Action.OPEN, 0, 0)
                      and record.cursor_before == (0, 0)
                      and all(v == CellState.HIDDEN for row in record.before_observation for v in row),
                      "Canonical initial input/observation is missing.")
            else:
                previous = records[index - 1]
                _need(previous.status_after is GameStatus.PLAYING, "Postterminal physical input.")
                _need(record.before_observation == previous.after_observation.rows
                      and record.cursor_before == previous.cursor_after,
                      "Public input effects/cursor do not reconstruct.")
        if not complete or records[-1].status_after is GameStatus.PLAYING:
            return EvidenceComparison("INCOMPLETE", len(records) - 1,
                                      detail="Final terminal input or completion marker is missing.")
        return EvidenceComparison("PASS", len(records) - 1)
    except (ValueError, TypeError, AttributeError) as error:
        return EvidenceComparison("FAIL", index, detail=str(error))


@dataclass(frozen=True)
class DecisionTimings:
    """Integer nanoseconds; None means UNMEASURED, never fabricated zero.

    plan_position and K entry-through-policy-return are comparable call spans.
    K execution validation, frozen validation, shadow and archive overhead are
    separate spans. comparison_ns measures public discrepancy/semantic comparison;
    oracle_ns is reserved for actual Oracle A/B work and stays None otherwise.
    These fields are never summed into a nested-work total.
    """

    v1_plan_position_ns: int | None = None
    k_analysis_planning_ns: int | None = None
    k_execution_validation_ns: int | None = None
    v1_execution_validation_ns: int | None = None
    shadow_ns: int | None = None
    evidence_ns: int | None = None
    comparison_ns: int | None = None
    oracle_ns: int | None = None
    evaluator_ns: int | None = None

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if value is not None:
                _integer(value, field.name)


_EVIDENCE_TYPES = (
    MoveProjection, ConstraintProjection, DeterministicProjection,
    CellProbabilityProjection, ProbabilityProjection, V1EvidenceProjection,
    PlanProjection, V1DecisionProjection, EvidenceMismatch, EvidenceComparison,
    ShadowSoundnessEvidence, ExternalV1FlagProvenance, ArchivalObservation,
    PublicEffectRecord, DecisionTimings,
)
