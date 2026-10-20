"""Segregated post-hoc Program-K falsification, never a public proof source.

This is the only Program-K experimental module that consumes a hidden answer.
Its two inputs are visibly separate: immutable assertions sealed from an already
archived public run, and an evaluator-only answer snapshot. Qualification derives
that snapshot from the same completed archive's terminal observation and declared
mine count; arbitrary supplied snapshots remain synthetic, unbound comparisons.
Neither input is an Engine, live session, callback, policy input, or public
certificate. There are no imports of solver, oracle, runner, Engine, or
public-proof modules.

A counterexample is a G1 falsification finding. Agreement means only that this
comparison found no counterexample; it cannot establish sound public provenance,
acquire/repair M, upgrade certainty, or select/tune any later case or action.
The implementation-versus-research diagnosis belongs to the qualification
harness under the frozen protocol, not to this one-way comparison.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
from time import perf_counter_ns


Coordinate = tuple[int, int]
EVALUATOR_IDENTITY = "program_k_evaluator.post_hoc_falsification.v2"
CERTAINTY_ASSERTION_TYPES = frozenset({
    "LOGICAL_M", "CERTAINTY_OPEN", "CERTAINTY_CHORD_OPENED",
})
EXCLUDED_ASSERTION_TYPES = frozenset({
    "POLICY_INITIAL_OPEN", "EXACT_MINIMUM_RISK_GUESS",
})
_DIAGNOSTICS = ContextVar("program_k_evaluator_diagnostics", default=())


class EvaluatorInputError(ValueError):
    """Malformed, unsealed, or mismatched records are not falsification evidence."""


def _require(condition, detail):
    if not condition:
        raise EvaluatorInputError(detail)


def _identity(value, label):
    _require(type(value) is str and bool(value.strip()), label + " must be an explicit identity.")


def _digest(value):
    _require(type(value) is str and len(value) == 64
             and all(char in "0123456789abcdef" for char in value),
             "Expected a lowercase SHA-256 digest of the sealed archive.")


def _dimensions(width, height):
    _require(type(width) is int and type(height) is int
             and 1 <= width <= 30 and 1 <= height <= 16,
             "Dimensions must be true integers within the frozen 30-by-16 grid.")


def _coordinate(cell, width=30, height=16):
    _require(type(cell) is tuple and len(cell) == 2
             and all(type(value) is int for value in cell)
             and 0 <= cell[0] < width and 0 <= cell[1] < height,
             "Expected an in-board true-integer coordinate stored as (x,y).")
    return cell


def _coordinate_set(cells):
    # No iteration of arbitrary Engine/answer adapters or mutable containers.
    _require(type(cells) in (tuple, frozenset), "Expected immutable coordinate membership.")
    checked = tuple(_coordinate(cell) for cell in cells)
    _require(len(set(checked)) == len(checked), "Duplicate asserted coordinate.")
    return tuple(sorted(checked, key=lambda cell: (cell[1], cell[0])))


def _hash(payload):
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvaluatorCallDiagnostic:
    """Separate actual-call evidence; never part of semantic evaluator equality.

    Each duration is the exclusive evaluator API call span, including its input
    validation. It is not combined with solver/oracle/evidence spans. Missing
    identities/counts mean malformed inputs or failed work, never measured zero.
    """

    sequence: int
    duration_ns: int
    sealed_input_digest: str | None
    answer_digest: str | None
    classification: str
    evaluated_coordinate_count: int | None
    error: str | None
    evaluator_identity: str = EVALUATOR_IDENTITY

    def __post_init__(self):
        _require(all(type(value) is int and value >= 0
                     for value in (self.sequence, self.duration_ns)),
                 "Evaluator call sequence/duration require nonnegative integer nanoseconds.")
        _require(self.evaluator_identity == EVALUATOR_IDENTITY,
                 "Unknown measured evaluator identity.")
        for value in (self.sealed_input_digest, self.answer_digest):
            if value is not None:
                _digest(value)
        if self.classification == "ERROR":
            _require(type(self.error) is str and bool(self.error)
                     and self.evaluated_coordinate_count is None,
                     "Failed evaluator work needs an explicit error and absent coverage.")
        else:
            _require(self.classification in ("G1_FALSIFICATION", "NO_COUNTEREXAMPLE", "NOT_EVALUATED")
                     and self.error is None and self.sealed_input_digest is not None
                     and self.answer_digest is not None
                     and type(self.evaluated_coordinate_count) is int
                     and self.evaluated_coordinate_count >= 0
                     and (self.classification == "NOT_EVALUATED")
                         == (self.evaluated_coordinate_count == 0),
                     "Measured evaluator result identity/classification/coverage differs.")


@contextmanager
def collect_evaluator_diagnostics():
    """Collect actual calls in this post-hoc operation, outside semantic results."""
    records = []
    token = _DIAGNOSTICS.set(_DIAGNOSTICS.get() + (records,))
    try:
        yield records
    finally:
        _DIAGNOSTICS.reset(token)


@dataclass(frozen=True, slots=True)
class ArchivedAssertion:
    """One already-archived assertion at a zero-based physical input boundary.

    LOGICAL_M records the entire archived M snapshot immediately before that
    input. CERTAINTY_OPEN records its single selected target, and
    CERTAINTY_CHORD_OPENED records cells actually opened by that certainty CHORD,
    not its planned suffix, hypothetical reveals, or terminal mine disclosures.
    The caller must derive these records from the sealed public action/effect
    archive, whose digest is retained by SealedEvaluatorInput.

    Initial OPEN and uncertain guesses remain explicit excluded records. Input
    zero cannot be relabeled as a certainty OPEN or CHORD. This evaluator does
    not infer certainty or repair an incorrectly labeled source archive.
    """

    assertion_type: str
    physical_input_boundary: int
    coordinates: tuple[Coordinate, ...]

    def __post_init__(self):
        _require(type(self.assertion_type) is str
                 and self.assertion_type in CERTAINTY_ASSERTION_TYPES | EXCLUDED_ASSERTION_TYPES,
                 "Unsupported archived assertion type.")
        _require(type(self.physical_input_boundary) is int and self.physical_input_boundary >= 0,
                 "Physical input boundary must be a nonnegative true integer.")
        coordinates = _coordinate_set(self.coordinates)
        if self.assertion_type == "POLICY_INITIAL_OPEN":
            _require(self.physical_input_boundary == 0 and coordinates == ((0, 0),),
                     "Canonical initial OPEN is excluded and belongs only to boundary zero.")
        elif self.assertion_type != "LOGICAL_M":
            _require(self.physical_input_boundary > 0,
                     "Canonical initial input cannot become a certainty assertion or exact guess.")
            _require(bool(coordinates), "An executed reveal assertion cannot be empty.")
            if self.assertion_type != "CERTAINTY_CHORD_OPENED":
                _require(len(coordinates) == 1, "An OPEN records exactly one target.")
        elif self.physical_input_boundary == 0:
            _require(not coordinates, "Canonical initialization has empty M.")
        object.__setattr__(self, "coordinates", coordinates)


@dataclass(frozen=True, slots=True)
class SealedEvaluatorInput:
    """Public assertion archive only; no hidden answer or writable solver owner.

    ``archive_digest`` binds the assertions to the separately retained complete
    public archive. It is an integrity reference, not a substitute for those
    reconstructable public records or independent public certificate checks.
    Sealing is immutable value capture, not proof of the assertions' correctness.
    """

    case_id: str
    run_id: str
    width: int
    height: int
    assertions: tuple[ArchivedAssertion, ...]
    archive_digest: str

    def __post_init__(self):
        _identity(self.case_id, "Case")
        _identity(self.run_id, "Run")
        _dimensions(self.width, self.height)
        _digest(self.archive_digest)
        _require(type(self.assertions) is tuple
                 and all(type(item) is ArchivedAssertion for item in self.assertions),
                 "Expected an ordered tuple of sealed assertions, never an Engine or live session.")
        checked = tuple(ArchivedAssertion(item.assertion_type, item.physical_input_boundary,
                                          item.coordinates) for item in self.assertions)
        previous_boundary, seen = -1, set()
        for item in checked:
            _require(item.physical_input_boundary >= previous_boundary,
                     "Archived assertion boundaries must preserve chronological order.")
            key = (item.physical_input_boundary, item.assertion_type)
            _require(key not in seen, "Duplicate assertion at a physical input boundary.")
            seen.add(key)
            previous_boundary = item.physical_input_boundary
            for cell in item.coordinates:
                _coordinate(cell, self.width, self.height)
        object.__setattr__(self, "assertions", checked)

    @property
    def assertions_digest(self) -> str:
        return _hash({
            "case_id": self.case_id, "run_id": self.run_id,
            "width": self.width, "height": self.height,
            "archive_digest": self.archive_digest,
            "assertions": tuple((item.assertion_type, item.physical_input_boundary,
                                 item.coordinates) for item in self.assertions),
        })


@dataclass(frozen=True, slots=True)
class HiddenAnswer:
    """Evaluator-only answer storage, separate from sealed public assertions.

    Bound answers are derived only by the post-hoc terminal adapter below. The
    optional absent binding supports synthetic comparison tests, but cannot
    satisfy qualification. There is no live Engine or extraction callback and
    no conversion to a solver/public-proof input.
    """

    case_id: str
    run_id: str
    width: int
    height: int
    mines: frozenset[Coordinate]
    archive_digest: str | None = None
    num_mines: int | None = None

    def __post_init__(self):
        _identity(self.case_id, "Case")
        _identity(self.run_id, "Run")
        _dimensions(self.width, self.height)
        checked = _coordinate_set(self.mines)
        for cell in checked:
            _coordinate(cell, self.width, self.height)
        object.__setattr__(self, "mines", frozenset(checked))
        _require((self.archive_digest is None) == (self.num_mines is None),
                 "Archive binding and declared mine count must be supplied together.")
        if self.archive_digest is not None:
            _digest(self.archive_digest)
            _require(type(self.num_mines) is int
                     and 0 <= self.num_mines < self.width * self.height
                     and len(checked) == self.num_mines,
                     "Bound terminal truth must match the declared game mine count.")

    @property
    def answer_digest(self) -> str:
        return _hash({
            "case_id": self.case_id, "run_id": self.run_id,
            "width": self.width, "height": self.height,
            "archive_digest": self.archive_digest, "num_mines": self.num_mines,
            "mines": tuple(sorted(self.mines, key=lambda cell: (cell[1], cell[0]))),
        })


def derive_terminal_answer(sealed: SealedEvaluatorInput, *, terminal_status: str,
                           terminal_rows: tuple[tuple[int, ...], ...],
                           num_mines: int) -> HiddenAnswer:
    """Derive evaluator-only truth from the exact completed archive projection.

    The harness validates/reconstructs the complete ExecutionArchive, checks its
    digest against ``sealed``, and supplies its final archival rows/status plus
    the independently declared game mine count. This function accepts detached
    values only, never an Engine, solver owner or callback.

    These integer glyphs follow core_engine.get_observation/_update_status:
    WON automatically flags every mine and reveals every safe cell. LOST exposes
    every mine as FLAGGED(-3), EXPLODED(-4) or MINE(-5); FALSE_FLAG(-6) is safe.
    Terminal truth never becomes acquisition or public-proof evidence.
    """
    public = _checked_input(sealed)
    _require(type(terminal_status) is str and terminal_status in ("WON", "LOST"),
             "Evaluator truth requires an explicit completed WON or LOST archive.")
    _require(type(num_mines) is int and 0 <= num_mines < public.width * public.height,
             "Declared game mine count must be an in-range true integer.")
    _require(type(terminal_rows) is tuple and len(terminal_rows) == public.height
             and all(type(row) is tuple and len(row) == public.width
                     for row in terminal_rows),
             "Terminal archive dimensions must exactly match the sealed execution.")
    allowed = (-3,) if terminal_status == "WON" else (-2, -3, -4, -5, -6)
    _require(all(type(value) is int and (value in allowed or 0 <= value <= 8)
                 for row in terminal_rows for value in row),
             "Terminal archive contains a malformed or outcome-incompatible glyph.")
    if terminal_status == "LOST":
        _require(any(value == -4 for row in terminal_rows for value in row),
                 "LOST archive must contain an actually exploded mine.")
    mines = frozenset((x, y) for y, row in enumerate(terminal_rows)
                      for x, value in enumerate(row) if value in (-3, -4, -5))
    _require(len(mines) == num_mines,
             "Reconstructed terminal mines differ from the declared game mine count.")
    for y, row in enumerate(terminal_rows):
        for x, value in enumerate(row):
            if 0 <= value <= 8:
                adjacent = sum(abs(mx-x) <= 1 and abs(my-y) <= 1 and (mx, my) != (x, y)
                               for mx, my in mines)
                _require(value == adjacent,
                         "Revealed terminal clue disagrees with reconstructed actual mines.")
    return HiddenAnswer(public.case_id, public.run_id, public.width, public.height,
                        mines, public.archive_digest, num_mines)


@dataclass(frozen=True, slots=True)
class CoordinateComparison:
    """Segregated truth comparison; its booleans are never public premises."""

    coordinate: Coordinate
    asserted_mine: bool
    hidden_mine: bool

    def __post_init__(self):
        _coordinate(self.coordinate)
        _require(type(self.asserted_mine) is bool and type(self.hidden_mine) is bool,
                 "Truth comparisons require exact booleans.")

    @property
    def matches(self) -> bool:
        return self.asserted_mine == self.hidden_mine


@dataclass(frozen=True, slots=True)
class AssertionFinding:
    assertion: ArchivedAssertion
    comparisons: tuple[CoordinateComparison, ...]

    def __post_init__(self):
        _require(type(self.assertion) is ArchivedAssertion
                 and type(self.comparisons) is tuple
                 and all(type(item) is CoordinateComparison for item in self.comparisons),
                 "Findings require the exact sealed assertion and immutable comparisons.")
        assertion = ArchivedAssertion(self.assertion.assertion_type,
                                      self.assertion.physical_input_boundary,
                                      self.assertion.coordinates)
        comparisons = tuple(CoordinateComparison(item.coordinate, item.asserted_mine,
                                                 item.hidden_mine) for item in self.comparisons)
        if assertion.assertion_type in EXCLUDED_ASSERTION_TYPES:
            _require(not comparisons, "Initial OPEN and uncertain guesses must not be truth assertions.")
        else:
            _require(tuple(item.coordinate for item in comparisons) == assertion.coordinates,
                     "Every asserted coordinate needs exactly one ordered comparison.")
            expected = assertion.assertion_type == "LOGICAL_M"
            _require(all(item.asserted_mine is expected for item in comparisons),
                     "Comparison meaning disagrees with the archived assertion type.")
        object.__setattr__(self, "assertion", assertion)
        object.__setattr__(self, "comparisons", comparisons)

    @property
    def counterexamples(self) -> tuple[Coordinate, ...]:
        return tuple(item.coordinate for item in self.comparisons if not item.matches)

    @property
    def classification(self) -> str:
        if self.assertion.assertion_type in EXCLUDED_ASSERTION_TYPES:
            return "EXCLUDED_NONCERTAINTY"
        if self.counterexamples:
            return "G1_FALSIFICATION"
        return "NO_COUNTEREXAMPLE" if self.comparisons else "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class FalsificationResult:
    """One-way findings only, with no action, proof, state update or repair API.

    The complete answer is not copied into this record. Only comparisons needed
    to explain findings and the evaluator-only answer digest are retained here.
    Even NO_COUNTEREXAMPLE is not a PASS or an independent public-proof result.
    """

    sealed_input: SealedEvaluatorInput
    answer_digest: str
    findings: tuple[AssertionFinding, ...]

    def __post_init__(self):
        _require(type(self.sealed_input) is SealedEvaluatorInput,
                 "Result must reference the explicit sealed public assertions.")
        _digest(self.answer_digest)
        sealed = _checked_input(self.sealed_input)
        _require(type(self.findings) is tuple
                 and all(type(item) is AssertionFinding for item in self.findings),
                 "Expected complete ordered immutable findings.")
        findings = tuple(AssertionFinding(item.assertion, item.comparisons) for item in self.findings)
        _require(tuple(item.assertion for item in findings) == sealed.assertions,
                 "Findings must cover the exact sealed assertion sequence.")
        object.__setattr__(self, "sealed_input", sealed)
        object.__setattr__(self, "findings", findings)

    @property
    def case_id(self) -> str:
        return self.sealed_input.case_id

    @property
    def run_id(self) -> str:
        return self.sealed_input.run_id

    @property
    def evaluator_identity(self) -> str:
        return EVALUATOR_IDENTITY

    @property
    def evaluated_coordinate_count(self) -> int:
        return sum(len(item.comparisons) for item in self.findings)

    @property
    def excluded_assertion_count(self) -> int:
        return sum(item.classification == "EXCLUDED_NONCERTAINTY" for item in self.findings)

    @property
    def classification(self) -> str:
        if any(item.counterexamples for item in self.findings):
            return "G1_FALSIFICATION"
        return "NO_COUNTEREXAMPLE" if self.evaluated_coordinate_count else "NOT_EVALUATED"

    @property
    def proof_upgrade_allowed(self) -> bool:
        return False

    @property
    def research_progression_must_stop(self) -> bool:
        return self.classification == "G1_FALSIFICATION"


def _checked_input(sealed):
    _require(type(sealed) is SealedEvaluatorInput,
             "Only an explicit sealed evaluator input is accepted.")
    return SealedEvaluatorInput(sealed.case_id, sealed.run_id, sealed.width, sealed.height,
                                sealed.assertions, sealed.archive_digest)


def _checked_answer(public, answer):
    _require(type(answer) is HiddenAnswer, "Hidden truth requires its separate immutable snapshot.")
    truth = HiddenAnswer(answer.case_id, answer.run_id, answer.width, answer.height, answer.mines,
                         answer.archive_digest, answer.num_mines)
    _require((public.case_id, public.run_id, public.width, public.height)
             == (truth.case_id, truth.run_id, truth.width, truth.height),
             "Answer and sealed assertion case/run/dimension identities differ.")
    _require(truth.archive_digest is None or truth.archive_digest == public.archive_digest,
             "Answer and sealed assertion archive digests differ.")
    return truth


def verify_bound_finding(finding, sealed, answer) -> None:
    """Validate retained findings against this archive's derived terminal truth.

    Qualification supplies ``derive_terminal_answer``'s result, never an
    independent user answer. This is a pure integrity check of existing evidence:
    it does not invoke the evaluator again, create a finding or resume execution.
    Every retained truth bit and the complete assertion sequence are checked in
    addition to the case/run/dimensions/archive/count answer identity.
    """
    public = _checked_input(sealed)
    truth = _checked_answer(public, answer)
    _require(truth.archive_digest is not None,
             "Unbound synthetic answers cannot qualify execution evidence.")
    _require(type(finding) is FalsificationResult, "Missing typed evaluator finding.")
    checked = FalsificationResult(finding.sealed_input, finding.answer_digest, finding.findings)
    _require(checked.sealed_input == public and checked.answer_digest == truth.answer_digest,
             "Evaluator finding is not bound to this exact execution-board truth.")
    _require(all(comparison.hidden_mine == (comparison.coordinate in truth.mines)
                 for item in checked.findings for comparison in item.comparisons),
             "Retained evaluator comparisons disagree with bound terminal truth.")


def _evaluate_falsification(sealed, answer):
    public = _checked_input(sealed)
    truth = _checked_answer(public, answer)
    findings = []
    for assertion in public.assertions:
        comparisons = ()
        if assertion.assertion_type in CERTAINTY_ASSERTION_TYPES:
            comparisons = tuple(CoordinateComparison(
                cell, assertion.assertion_type == "LOGICAL_M", cell in truth.mines,
            ) for cell in assertion.coordinates)
        findings.append(AssertionFinding(assertion, comparisons))
    return FalsificationResult(public, truth.answer_digest, tuple(findings))


def evaluate_falsification(sealed: SealedEvaluatorInput, answer: HiddenAnswer) -> FalsificationResult:
    """Compare archived assertions after execution; never call back into it.

    The caller owns archive capture and must finish/seal the solver record before
    supplying its evaluator-only hidden answer. The semantic result cannot resume
    a solver, modify M, create a certificate, or pick later cases. Revalidation
    rejects malformed/deserialized records before reading truth. Optional scoped
    timing remains separate from that immutable result.
    """
    collectors = _DIAGNOSTICS.get()
    if not collectors:
        return _evaluate_falsification(sealed, answer)
    started = perf_counter_ns()
    try:
        result = _evaluate_falsification(sealed, answer)
    except BaseException as error:
        elapsed = perf_counter_ns() - started
        for records in collectors:
            records.append(EvaluatorCallDiagnostic(len(records), elapsed, None, None,
                                                   "ERROR", None, type(error).__name__))
        raise
    elapsed = perf_counter_ns() - started
    for records in collectors:
        records.append(EvaluatorCallDiagnostic(
            len(records), elapsed, result.sealed_input.assertions_digest,
            result.answer_digest, result.classification, result.evaluated_coordinate_count, None))
    return result
