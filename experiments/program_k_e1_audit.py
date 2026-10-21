"""Post-hoc public evidence for ONE detached scheduled run.

The plan supplies public metadata and source provenance, never an answer. Replay
is scratch integrity checking only. No result here confers research qualification,
and informational Oracle B materialization is never physical execution state.
"""

from dataclasses import asdict, dataclass, fields, replace
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import FunctionType, SimpleNamespace

from core_engine import Action, CellState, GameStatus
from experiments import program_k_capability as _capability
from experiments import program_k_e1_execution as _execution
from experiments import program_k_e1_harness as _e1
from experiments import program_k_evidence as _evidence
from experiments import program_k_harness as _harness
from experiments import program_k_oracles as _oracles
from experiments import program_k_policy as _policy
from experiments import program_k_runner as _runner
from simple_algorithm import SimpleMove
from simple_decision import DecisionKind
import stage3_physical as _physical
from stage3_runner import Stage3ActionTrace, Stage3RunnerError, _validate_execution


AUDIT_SOURCE_PATH = "experiments/program_k_e1_audit.py"
TIMING_CONTEXT = "ARCHIVED_RUNNER_SPANS; supervisor/tracer context is not inferred here"
_AUTHORITIES = ("spec_sha256", "protocol_sha256", "model_id", "profile_sha256", "table_sha256")
_EXACT_FIELDS = (
    "unresolved_cells", "frontier_cells", "unconstrained_cells", "total_worlds",
    "mine_worlds", "G0", "G1", "minimum_risk", "minimum_risk_cells",
    "shared_kernel_evidence", "kernel",
)
_PUBLIC_ERRORS = (ValueError, TypeError, AttributeError, IndexError, KeyError,
                  StopIteration, ZeroDivisionError, Stage3RunnerError)


class E1AuditError(ValueError):
    """An unbound input or changed source cannot establish an audit identity."""


def _need(condition, detail):
    if not condition:
        raise E1AuditError(detail)


def _checked(value, cls):
    _need(type(value) is cls, "Expected exact " + cls.__name__ + ".")
    try:
        return replace(value)
    except _PUBLIC_ERRORS as error:
        raise E1AuditError("Invalid " + cls.__name__ + ": " + str(error)) from error


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Invalid SHA-256.")


@dataclass(frozen=True, slots=True)
class E1AuditSourceFile:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(self.path == AUDIT_SOURCE_PATH and type(self.path) is str,
              "Only the audit module extends this runtime identity.")
        _sha(self.sha256)
        _need(type(self.size_bytes) is int and self.size_bytes > 0, "Invalid audit byte size.")


@dataclass(frozen=True, slots=True)
class E1AuditSourceIdentity:
    execution_source_digest: str
    audit_file: E1AuditSourceFile
    spec_sha256: str
    protocol_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        _sha(self.execution_source_digest)
        _checked(self.audit_file, E1AuditSourceFile)
        try:
            _e1._frozen_identities(self)
        except ValueError as error:
            raise E1AuditError("Frozen audit authority mismatch.") from error

    @property
    def digest(self):
        _checked(self, E1AuditSourceIdentity)
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
        return hashlib.sha256(raw).hexdigest()


def _validate_bindings(plan, archive):
    """Validate provenance before public checking; never reconstruct a board.

    Evidence defects are diagnosed by the audit below, rather than by invoking
    the archive constructor (which also rejects semantic stream corruption).
    Unsafe graphs and ambiguous provenance are input errors, not audit findings.
    """
    _checked(plan, _e1.E1Plan)
    _need(type(archive) is _execution.E1ScheduledRunArchive, "Expected exact scheduled archive.")
    _need(not hasattr(archive, "__dict__"), "Unexpected archive attachment.")
    source = _checked(archive.execution_source_identity, _execution.E1ExecutionSourceIdentity)
    entry = _checked(archive.schedule_entry, _e1.ScheduleEntry)
    case = _checked(archive.case, _e1.SealedCaseRegistration)
    receipt = _checked(archive.receipt, _execution.CaseMaterializationReceipt)
    _need(type(archive.plan_source_digest) is str
          and archive.plan_source_digest == plan.source_identity.digest == source.plan_source_digest,
          "Archive/plan source binding differs.")
    _need(entry == plan.schedule[entry.schedule_index], "Archive schedule binding differs.")
    expected_case = next(c for c in plan.cases if c.case_id == entry.case_id)
    _need(case == expected_case and case.runtime == plan.runtime,
          "Archive case/runtime seal differs.")
    for name in ("case_id", "source_type", "width", "height", "num_mines", "first_click",
                 "game_index", "seed", "board_fingerprint", "runtime"):
        _need(getattr(receipt, name) == getattr(case, name), "Materialization receipt differs: " + name)
    _need(type(archive.completion_status) is str and archive.completion_status == "COMPLETE",
          "Only structurally COMPLETE archives may enter the audit.")
    _execution._timeout(archive.shadow_timeout_s)
    _need(archive.shadow_timeout_usage == (
        "APPLIED" if entry.variant == "K-CONTROL" else "NOT_APPLICABLE"),
        "Shadow timeout applicability differs.")
    expected_type = {"CONTROL": _runner.ControlCaptureResult,
                     "K-CONTROL": _runner.KControlRunResult, "K-P0": _runner.KRunResult}[entry.variant]
    _need(type(archive.result) is expected_type, "Variant/result class differs.")
    try:
        _execution._require_detached_result(archive.result)
    except _PUBLIC_ERRORS as error:
        raise E1AuditError("Unsafe detached result graph: " + str(error)) from error
    result = archive.result
    if entry.variant == "CONTROL":
        _need(type(result.control) is _runner.Stage3RunResult
              and type(result.effects) is tuple and type(result.timings) is tuple,
              "Malformed CONTROL result collections.")
    trace_type = {"CONTROL": Stage3ActionTrace, "K-CONTROL": _runner.KControlActionTrace,
                  "K-P0": _runner.KActionTrace}[entry.variant]
    _need(type(result.traces) is tuple and all(type(t) is trace_type for t in result.traces),
          "Malformed immutable trace structure.")
    if entry.variant == "K-CONTROL":
        _need(type(result.shadow) is _runner.ShadowCheckpoint
              and all(type(t.shadow) is _runner.ShadowCheckpoint for t in result.traces),
              "Malformed shadow checkpoint structure.")
        for checkpoint in (result.shadow,) + tuple(t.shadow for t in result.traces):
            failure = checkpoint.failure
            _need(failure is None or (
                type(failure) is _runner.ShadowFailure
                and type(failure.failure_class) is str and type(failure.detail) is str),
                "Malformed shadow failure structure.")
    return source


def _capture_audit_source_identity(plan, archive, root):
    """Private byte-mutation test seam; all Slice-1/2 sources remain live."""
    try:
        archived = _validate_bindings(plan, archive)
        current = _execution.capture_execution_source_identity(plan)
        _need(current == archived, "Current Slice-2 execution source identity differs from archive.")
        raw = (Path(root) / AUDIT_SOURCE_PATH).read_bytes()
        return E1AuditSourceIdentity(
            current.digest,
            E1AuditSourceFile(AUDIT_SOURCE_PATH, hashlib.sha256(raw).hexdigest(), len(raw)),
            *(getattr(current, name) for name in _AUTHORITIES),
        )
    except (OSError,) + _PUBLIC_ERRORS as error:
        raise E1AuditError("Audit source capture refused: " + str(error)) from error


def capture_audit_source_identity(plan, archive):
    """Bind exact current sources to an explicit plan/archive pair."""
    return _capture_audit_source_identity(plan, archive, Path(__file__).resolve().parents[1])


@dataclass(frozen=True, slots=True)
class ModelCCostAudit:
    input_index: int
    expected_us: int | None
    trace_us: int | None
    effect_us: int | None
    status: str


@dataclass(frozen=True, slots=True)
class V1ActionAudit:
    input_index: int
    status: str
    detail: str
    external_flag: _evidence.ExternalV1FlagProvenance | None
    external_verification: _evidence.EvidenceComparison | None
    external_qualification: "ExternalV1FlagQualification | None" = None


@dataclass(frozen=True, slots=True)
class ExternalV1FlagQualification:
    """Original raw coverage and E1 premise-conditioned coverage are distinct.

    ``node_verification`` uses the unchanged independent frozen checker after
    earlier physical premises have been admitted chronologically. It never
    upgrades ``raw_verification``, including an unevaluated exact ancestor.
    """

    input_index: int
    boundary: int
    raw_verification: _evidence.EvidenceComparison
    node_verification: _evidence.EvidenceComparison
    decision_kind: DecisionKind
    public_hidden_variables: int
    target: tuple[int, int]
    independent_bounded_enumeration_ran: bool
    bounded_status: str
    bounded_reason: str | None
    prior_input_indices: tuple[int, ...]
    shared_kernel_input_digest: str | None
    shared_kernel_result: _oracles.OracleBResult | None
    shared_kernel_expected_flag: _evidence.MoveProjection | None
    shared_kernel_evidence: str | None
    prerequisite: _e1.AcceptedE0Prerequisite | None
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class PhysicalFlagWork:
    admitted_nodes: int
    raw_node_checks: int
    conditioned_node_checks: int
    prior_reference_checks: int
    support_views: int


@dataclass(frozen=True, slots=True)
class KReplayAudit:
    input_index: int
    decision_status: str
    policy_status: str
    archived_decision_digest: str | None
    replayed_decision_digest: str | None
    archived_selection_digest: str | None
    replayed_selection_digest: str | None
    shadow: _runner.ShadowCheckpoint | None
    external_antecedents: tuple
    detail: str


@dataclass(frozen=True, slots=True)
class OracleBAudit:
    input_index: int
    phase: str
    logical_mines: frozenset
    proofs: tuple
    expected: _capability.ExactAnalysis | None
    result: _oracles.OracleBResult | None
    status: str
    discrepancies: tuple[str, ...]
    interpretation: str


@dataclass(frozen=True, slots=True)
class OracleAAudit:
    input_index: int
    coverage: _harness.OracleCoverage | None
    result: _oracles.OracleAResult | None
    checkpoint_variable_count: int
    status: str
    discrepancies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OracleDiagnosticSpan:
    input_index: int
    operation: str
    start: int
    stop: int
    status: str
    discrepancies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MechanismObservation:
    input_index: int
    action: Action
    target: tuple[int, int]
    selected_category: str
    setup_cells: frozenset
    reveal_cells: frozenset
    planned_terminal_reveal_action: SimpleMove | None
    plan_latency_us: int | None
    plan_reveals: int | None
    modeled_action_us: int
    safe_cells_opened_delta: int
    kind: str
    relevant_physical_flags: frozenset
    prior_setup_input_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TimingSpan:
    name: str
    boundary: str
    duration_ns: int | None
    coverage: str


@dataclass(frozen=True, slots=True)
class TimingCoverage:
    input_index: int
    timings: _evidence.DecisionTimings | None
    spans: tuple[TimingSpan, ...]


@dataclass(frozen=True, slots=True)
class E1RunAudit:
    source_identity: E1AuditSourceIdentity
    execution_source_digest: str
    schedule_entry: _e1.ScheduleEntry
    case: _e1.SealedCaseRegistration
    variant: str
    repetition: int
    public_effect_audit: _evidence.EvidenceComparison
    cost_audits: tuple[ModelCCostAudit, ...]
    expected_total_us: int | None
    recorded_total_us: int | None
    v1_audits: tuple[V1ActionAudit, ...]
    replay_audits: tuple[KReplayAudit, ...]
    acquisition_audits: tuple[_harness.AcquisitionAudit, ...]
    oracle_a_audits: tuple[OracleAAudit, ...]
    oracle_b_audits: tuple[OracleBAudit, ...]
    oracle_calls: tuple[_oracles.OracleCallDiagnostic, ...]
    oracle_spans: tuple[OracleDiagnosticSpan, ...]
    p3_audit: _harness.GuessCheckpointAudit | None
    p3_status: str
    mechanism_observations: tuple[MechanismObservation, ...]
    mechanism_status: str
    timings: tuple[TimingCoverage, ...]
    timing_context: str
    discrepancies: tuple[str, ...]
    incomplete_reasons: tuple[str, ...]
    audit_status: str
    physical_flag_work: PhysicalFlagWork = PhysicalFlagWork(0, 0, 0, 0, 0)

    def __post_init__(self):
        _need(self.audit_status in ("PASS", "FAIL", "INCOMPLETE"), "Invalid per-run audit status.")
        expected = "FAIL" if self.discrepancies else "INCOMPLETE" if self.incomplete_reasons else "PASS"
        _need(self.audit_status == expected, "Audit status contradicts retained findings.")
        _need(self.execution_source_digest == self.source_identity.execution_source_digest
              and self.variant == self.schedule_entry.variant
              and self.repetition == self.schedule_entry.repetition
              and self.case.case_id == self.schedule_entry.case_id
              and self.timing_context == TIMING_CONTEXT, "Audit result identity differs.")
        _require_audit_graph(self)


class _Findings:
    """Transient collection only; no mutable object leaves the audit."""

    def __init__(self):
        self.failures = []
        self.missing = []

    def check(self, condition, detail, *, missing=False):
        if not condition:
            (self.missing if missing else self.failures).append(detail)
        return bool(condition)

    def record(self, status, detail):
        if status != "PASS":
            (self.failures if status == "FAIL" else self.missing).append(detail)


def _cells(rows, glyph):
    return frozenset((x, y) for y, row in enumerate(rows) for x, value in enumerate(row)
                     if value == glyph)


def _digest(value):
    return _harness.content_digest(value)


def _effects(result, variant):
    return result.effects if variant == "CONTROL" else tuple(
        getattr(t, "public_effect", None) for t in result.traces)


def _public_stream(result, variant, case, findings):
    """Keep the existing comparison exactly; add independent trace bindings."""
    traces = result.traces
    effects = _effects(result, variant)
    comparison = _evidence.validate_public_effect_stream(effects, complete=True)
    absent = (type(effects) is not tuple or len(effects) != len(traces)
              or not effects or any(e is None for e in effects))
    findings.record("INCOMPLETE" if absent else comparison.status,
                    "Public effect stream: " + comparison.detail)
    failures_before, missing_before = len(findings.failures), len(findings.missing)
    findings.check(type(traces) is tuple and bool(traces), "Missing input traces.", missing=True)
    findings.check(type(effects) is tuple and len(effects) == len(traces),
                   "Missing paired public effects.", missing=True)
    trace_type = {"CONTROL": Stage3ActionTrace, "K-CONTROL": _runner.KControlActionTrace,
                  "K-P0": _runner.KActionTrace}[variant]
    for index, trace in enumerate(traces):
        label = "Input " + str(index) + ": "
        if not findings.check(type(trace) is trace_type, label + "wrong trace class."):
            continue
        if index >= len(effects) or type(effects[index]) is not _evidence.PublicEffectRecord:
            findings.check(False, label + "missing public effect.", missing=True)
            continue
        effect = effects[index]
        try:
            _checked(effect, _evidence.PublicEffectRecord)
            findings.check(type(trace.move) is SimpleMove and type(trace.move.action) is Action,
                           label + "invalid physical move.")
            findings.check(effect.input_index == index and effect.status_before is GameStatus.PLAYING,
                           label + "input index/preinput status differs.")
            findings.check((effect.move.action, effect.move.x, effect.move.y)
                           == (trace.move.action, trace.move.x, trace.move.y),
                           label + "trace/effect move differs.")
            findings.check(effect.cursor_before == trace.cursor_before
                           and effect.cursor_after == (trace.move.x, trace.move.y),
                           label + "trace/effect cursor differs.")
            findings.check(type(trace.modeled_action_us) is int
                           and trace.modeled_action_us == effect.modeled_action_us,
                           label + "trace/effect modeled cost differs.")
            findings.check(trace.status_after is effect.status_after,
                           label + "trace/effect status differs.")
            findings.check(len(effect.before_observation) == len(effect.after_observation.rows) == case.height
                           and all(len(r) == case.width for r in
                                   effect.before_observation + effect.after_observation.rows),
                           label + "public dimensions differ from sealed case.")
            if index:
                previous = effects[index - 1]
                if previous is None:
                    findings.check(False, label + "previous public effect is unavailable.", missing=True)
                else:
                    findings.check(previous.status_after is GameStatus.PLAYING
                                   and effect.before_observation == previous.after_observation.rows
                                   and effect.cursor_before == previous.cursor_after,
                                   label + "public continuity/postterminal boundary differs.")
            else:
                findings.check(trace.move == SimpleMove(Action.OPEN, *case.first_click)
                               and trace.cursor_before == case.first_click
                               and all(v == CellState.HIDDEN for row in effect.before_observation for v in row),
                               label + "canonical initial input differs.")
            if variant == "CONTROL":
                findings.check(trace.safe_cells_opened_delta == effect.safe_cells_opened_delta
                               and trace.explicit_flag_delta == effect.explicit_flag_delta,
                               label + "CONTROL public deltas differ.")
            else:
                findings.check(type(trace.input_index) is int and trace.input_index == index
                               and trace.public_effect_status == "CAPTURED",
                               label + "trace sequence/capture marker differs.")
            if variant == "K-CONTROL":
                findings.check(trace.observation == effect.before_observation,
                               label + "V1 archived observation differs.")
            # The existing stream checker authenticates record structure and
            # continuity. Independently reconstruct deltas and PLAYING progress.
            safe = sum(old in (CellState.HIDDEN, CellState.FLAGGED) and 0 <= new <= 8
                       for a, b in zip(effect.before_observation, effect.after_observation.rows)
                       for old, new in zip(a, b))
            findings.check(effect.safe_cells_opened_delta == safe
                           and effect.explicit_flag_delta == int(trace.move.action is Action.FLAG),
                           label + "public effect delta does not reconstruct.")
            if effect.status_after is GameStatus.PLAYING:
                _runner._validate_progress(effect.before_observation, effect.after_observation.rows, trace.move)
        except _PUBLIC_ERRORS as error:
            findings.check(False, label + "malformed public evidence: " + str(error))
    findings.check(type(result.status) is GameStatus
                   and result.status in (GameStatus.WON, GameStatus.LOST),
                   "Missing terminal run status.", missing=True)
    if effects and type(effects[-1]) is _evidence.PublicEffectRecord:
        findings.check(effects[-1].status_after is result.status, "Final effect/result status differs.")
    sound = (comparison.status == "PASS" and len(findings.failures) == failures_before
             and len(findings.missing) == missing_before)
    return effects, comparison, sound


def _costs(result, effects, table, findings):
    audits = []
    for index, trace in enumerate(result.traces):
        expected = effect_us = None
        trace_us = trace.modeled_action_us
        try:
            _need(type(trace.move) is SimpleMove and type(trace.cursor_before) is tuple,
                  "Missing exact cursor/move.")
            # Authenticate coordinates, then independently use the frozen lookup.
            _physical.action_cost(table, trace.cursor_before, (trace.move.x, trace.move.y))
            expected = table[abs(trace.move.x - trace.cursor_before[0])][abs(trace.move.y - trace.cursor_before[1])]
            if index < len(effects) and type(effects[index]) is _evidence.PublicEffectRecord:
                effect_us = effects[index].modeled_action_us
            status = ("INCOMPLETE" if effect_us is None else
                      "PASS" if type(trace_us) is int and type(effect_us) is int
                      and trace_us == effect_us == expected else "FAIL")
        except _PUBLIC_ERRORS as error:
            status = "FAIL"
            findings.check(False, "Model-C input " + str(index) + ": " + str(error))
        audits.append(ModelCCostAudit(index, expected, trace_us, effect_us, status))
        findings.record(status, "Model-C input " + str(index) + " cost mismatch/missing.")
    total = (sum(a.expected_us for a in audits)
             if audits and all(a.expected_us is not None for a in audits) else None)
    try:
        recorded = result.total_modeled_us
        if total is None:
            findings.check(False, "Model-C total reconstruction unavailable.", missing=True)
        else:
            findings.check(type(recorded) is int and total == recorded,
                           "Model-C total differs from exact per-input sum.")
    except _PUBLIC_ERRORS as error:
        recorded = None
        findings.check(False, "Missing modeled total: " + str(error), missing=True)
    return tuple(audits), total, recorded


_TIMING_BOUNDARIES = (
    ("v1_plan_position_ns", "Frozen V1 plan_position call only"),
    ("k_analysis_planning_ns", "K decision entry through selected policy return"),
    ("k_execution_validation_ns", "K physical execution validation only"),
    ("v1_execution_validation_ns", "Frozen V1 execution validation; K-CONTROL sums two disjoint calls"),
    ("shadow_ns", "Detached shadow analysis and output validation"),
    ("comparison_ns", "Detached public shadow comparison"),
    ("evidence_ns", "Runner evidence assembly/capture as measured by that variant"),
    ("oracle_ns", "Reserved runner field; post-hoc Oracle spans are separate"),
    ("evaluator_ns", "Reserved runner field; no such work belongs to this audit"),
)


def _timing_coverage(result, variant, findings):
    records = []
    for index, trace in enumerate(result.traces):
        raw = (result.timings[index] if variant == "CONTROL" and index < len(result.timings)
               else None if variant == "CONTROL" else trace.timings)
        if raw is None:
            findings.check(False, "Input " + str(index) + ": missing timing record.", missing=True)
            records.append(TimingCoverage(index, None, ()))
            continue
        try:
            _checked(raw, _evidence.DecisionTimings)
        except _PUBLIC_ERRORS as error:
            findings.check(False, "Malformed timing record: " + str(error))
            records.append(TimingCoverage(index, raw, ()))
            continue
        required = {"evidence_ns"}
        applicable = {"evidence_ns"}
        if variant in ("CONTROL", "K-CONTROL"):
            applicable.add("v1_plan_position_ns")
            if index:
                required.add("v1_plan_position_ns")
        if variant == "CONTROL":
            findings.check(raw.v1_plan_position_ns == trace.decision_compute_ns,
                           "CONTROL planner timing differs from trace.")
            # Frozen CONTROL does not measure its validator.
            findings.check(raw.v1_execution_validation_ns is None,
                           "CONTROL execution-validation timing was manufactured.")
        elif variant == "K-P0":
            required.add("k_execution_validation_ns")
            applicable.update(("k_analysis_planning_ns", "k_execution_validation_ns"))
            if index:
                required.add("k_analysis_planning_ns")
        else:
            required.add("v1_execution_validation_ns")
            applicable.update(("v1_execution_validation_ns", "shadow_ns", "comparison_ns"))
            shadow = trace.shadow
            if index and type(shadow) is _runner.ShadowCheckpoint:
                if shadow.enabled and shadow.failure is None:
                    required.update(("shadow_ns", "comparison_ns"))
                elif shadow.failure is not None and shadow.failure.detected_boundary == index:
                    # Timeout returns no completed worker span. Other failure
                    # classes can end before the comparison was reached.
                    if shadow.failure.failure_class != "SHADOW_TIMEOUT":
                        required.add("shadow_ns")
        spans = []
        for name, boundary in _TIMING_BOUNDARIES:
            value = getattr(raw, name)
            if name in required:
                coverage = "MEASURED" if value is not None else "UNMEASURED_REQUIRED"
                findings.check(value is not None, "Input " + str(index) + ": " + name + " unmeasured.",
                               missing=True)
            elif variant == "CONTROL" and name == "v1_execution_validation_ns":
                coverage = "UNMEASURED"
            elif name in applicable:
                initial_na = index == 0 and name in (
                    "v1_plan_position_ns", "k_analysis_planning_ns", "shadow_ns", "comparison_ns")
                if initial_na:
                    coverage = "NOT_APPLICABLE"
                    findings.check(value is None, "Initial action has a fabricated " + name + ".")
                else:
                    coverage = "MEASURED" if value is not None else "UNMEASURED"
            else:
                coverage = "NOT_APPLICABLE"
                findings.check(value is None, "Unexpected runner timing field " + name + ".")
            spans.append(TimingSpan(name, boundary, value, coverage))
        records.append(TimingCoverage(index, raw, tuple(spans)))
    if variant == "CONTROL":
        findings.check(len(result.timings) == len(result.traces), "CONTROL timing coverage length differs.",
                       missing=True)
    return tuple(records)


def _semantic_equal(left, right, checked=None):
    """All fields participate; object identity is only a pair-work cache."""
    if type(left) is not type(right):
        return False
    if type(left) in (str, int, bool, type(None), Fraction, Action, CellState,
                      GameStatus, DecisionKind, frozenset):
        return left == right
    checked = {} if checked is None else checked
    pair = (id(left), id(right))
    if pair in checked:
        return checked[pair][2]
    if type(left) is tuple:
        result = len(left) == len(right) and all(
            _semantic_equal(a, b, checked) for a, b in zip(left, right))
    else:
        result = all(_semantic_equal(getattr(left, f.name), getattr(right, f.name), checked)
                     for f in fields(left))
    # Retaining both values also prevents id reuse for temporary tuple views.
    checked[pair] = (left, right, result)
    return result


_FLAG_BOUNDED_REASON = "Independent exact FLAG check exceeds 16 public variables."


class _MissingFlagReference(Exception):
    """A required public comparison was unavailable, with no semantic result."""


def _flag_reference_differences(flag, result):
    if type(result) is not _oracles.OracleBResult:
        return ("Missing Oracle-B exact semantics.",)
    probability = flag.decision.evidence.probability_result
    if probability is None:
        return ("Missing archived exact evidence.",)
    counts = tuple((p.coordinate, p.mine_worlds) for p in probability.probabilities)
    minimum = min((n for _, n in counts), default=None)
    expected = (
        flag.observation, tuple(c for c, _ in counts), probability.frontier_cells,
        probability.unconstrained_cells, probability.total_worlds, counts,
        frozenset(c for c, n in counts if n == 0),
        frozenset(c for c, n in counts if n == probability.total_worlds),
        None if minimum is None else Fraction(minimum, probability.total_worlds),
        frozenset(c for c, n in counts if n == minimum),
        _oracles.SHARED_KERNEL_EVIDENCE, _oracles.FROZEN_EXACT_KERNEL,
    )
    actual = tuple(getattr(result, field.name) for field in fields(result))
    differences = []
    if _harness.canonical_bytes(actual) != _harness.canonical_bytes(expected):
        differences.append("Oracle-B domain/order/counts/marginals/certainty differ.")
    target = (flag.move.x, flag.move.y)
    if target not in result.G1 or not result.G1 or flag.decision.evidence.move != (
            _evidence.MoveProjection(Action.FLAG, *min(result.G1, key=lambda c: (c[1], c[0])))
            if result.G1 else None):
        differences.append("Oracle-B expected FLAG/selected target differs.")
    return tuple(differences)


def validate_external_flag_qualification(qualification, flag, prerequisite):
    """Reconstruct retained E1 qualification assertions, without new arithmetic.

    Raises on malformed or contradictory evidence, returns the retained status.
    Full original provenance and chronological admission remain in the audit;
    suite/final gates use this to reject a manufactured status-only PASS.
    """
    _need(type(qualification) is ExternalV1FlagQualification
          and type(flag) is _evidence.ExternalV1FlagProvenance,
          "Missing typed external V1 FLAG qualification.")
    q = qualification
    _checked(flag, _evidence.ExternalV1FlagProvenance)
    projection = _evidence._checked_projection(flag.decision)
    _checked(q.raw_verification, _evidence.EvidenceComparison)
    _checked(q.node_verification, _evidence.EvidenceComparison)
    count = len(_cells(flag.observation, CellState.HIDDEN))
    _need(type(q.input_index) is int and type(q.boundary) is int
          and q.input_index == q.boundary == flag.input_index == flag.boundary
          == q.raw_verification.boundary == q.node_verification.boundary
          and q.decision_kind is flag.decision.evidence.kind
          and q.decision_kind in (DecisionKind.LOCAL_DETERMINISTIC, DecisionKind.GLOBAL_CERTAINTY)
          and type(q.public_hidden_variables) is int and q.public_hidden_variables == count
          and type(q.target) is tuple and len(q.target) == 2
          and all(type(v) is int for v in q.target)
          and q.target == (flag.move.x, flag.move.y)
          and projection.move == flag.move and flag.move.action is Action.FLAG
          and flag.observation[flag.move.y][flag.move.x] == CellState.HIDDEN
          and type(q.prior_input_indices) is tuple
          and all(type(v) is int for v in q.prior_input_indices)
          and q.prior_input_indices == tuple(f.input_index for f in flag.prior_flags)
          and type(q.status) is str and q.status in ("PASS", "FAIL", "INCOMPLETE"),
          "External qualification public binding differs.")
    if q.status != "PASS":
        return q.status
    _need(q.raw_verification.status != "FAIL" and q.node_verification.status != "FAIL",
          "Failed independent provenance cannot qualify.")
    exact = q.decision_kind is DecisionKind.GLOBAL_CERTAINTY
    _need(type(q.independent_bounded_enumeration_ran) is bool
          and q.independent_bounded_enumeration_ran == (exact and count <= 16)
          and q.bounded_status == ("PASS" if exact and count <= 16 else
                                   "NOT_EVALUATED" if exact else "NOT_APPLICABLE"),
          "Independent bounded execution/coverage differs.")
    if not exact or count <= 16:
        _need(q.node_verification.status == "PASS",
              "Independent local/bounded proof must PASS; shared evidence cannot replace it.")
        _need(q.node_verification.detail == (
            "INDEPENDENT_BOUNDED_PUBLIC_V1_EXACT_FLAG" if exact else "PUBLIC_V1_LOCAL_FLAG_EVIDENCE"),
            "Independent current-node evidence label differs.")
        _need(q.raw_verification.status == "PASS" or (
            q.raw_verification.status == "NOT_EVALUATED"
            and q.raw_verification.detail.startswith("FLAG antecedent:")),
            "Raw independent coverage cannot be relabeled.")
        _need(q.bounded_reason is None and q.shared_kernel_result is None
              and q.shared_kernel_input_digest is None and q.shared_kernel_evidence is None
              and q.shared_kernel_expected_flag is None and q.prerequisite is None,
              "Local/bounded qualification carries an unauthorized shared fallback.")
    else:
        raw_reason = q.raw_verification.detail
        while raw_reason.startswith("FLAG antecedent: "):
            raw_reason = raw_reason[len("FLAG antecedent: "):]
        _need(q.node_verification.status == "NOT_EVALUATED"
              and q.node_verification.detail == _FLAG_BOUNDED_REASON
              and q.raw_verification.status == "NOT_EVALUATED"
              and raw_reason == _FLAG_BOUNDED_REASON
              and q.bounded_reason == _FLAG_BOUNDED_REASON
              and q.shared_kernel_evidence == _oracles.SHARED_KERNEL_EVIDENCE,
              "Above-envelope raw/node coverage or shared-kernel disclosure differs.")
        _checked(q.prerequisite, _e1.AcceptedE0Prerequisite)
        _checked(prerequisite, _e1.AcceptedE0Prerequisite)
        _need(q.prerequisite == prerequisite,
              "External shared-kernel qualification is not bound to accepted E0.")
        _need(q.shared_kernel_input_digest == _oracles.oracle_b_input_digest(
            flag.observation, flag.num_mines, frozenset()),
            "External Oracle-B input identity differs.")
        _need(not _flag_reference_differences(flag, q.shared_kernel_result),
              "External Oracle-B exact semantics differ.")
        _need(q.shared_kernel_expected_flag == flag.decision.evidence.move,
              "External Oracle-B expected FLAG differs.")
    return q.status


class _PhysicalFlagPremises:
    """Admit each physical node once; retained support is a flat chronological DAG.

    Frozen verifier work views have shallow prior records. Their memo entries
    refer to already checked originals, so neither _immutable nor public-support
    construction traverses a recursively duplicated ancestry tree. No work-view
    record or Python identity is serialized as semantic evidence.
    """

    def __init__(self, prerequisite=None):
        self.prerequisite = prerequisite
        self.records, self.qualifications, self.views, self.shallow = [], [], [], []
        self.qualified_k = []
        self.raw_checks = self.conditioned_checks = self.reference_checks = 0
        self.equal_checked, self.graph_checked = {}, {}

    def work(self):
        return PhysicalFlagWork(len(self.records), self.raw_checks,
                                self.conditioned_checks, self.reference_checks, len(self.views))

    def matches(self, supplied, expected):
        _require_audit_graph(supplied, checked=self.graph_checked)
        return _semantic_equal(supplied, expected, self.equal_checked)

    def active(self, external, observation, boundary):
        _need(self.matches(external, tuple(self.records)),
              "Physical FLAG provenance differs from admitted chronological nodes.")
        flags = _cells(observation, CellState.FLAGGED)
        _need(flags == frozenset((f.move.x, f.move.y) for f in external),
              "Every current physical FLAG needs exactly one qualified earlier provenance.")
        for flag, qualification in zip(self.records, self.qualifications):
            _need(flag.input_index < boundary and qualification.status == "PASS",
                  "Physical premise is not an earlier E1-qualified FLAG.")
            _oracles._public_extension(flag.observation, observation,
                                       {(flag.move.x, flag.move.y)})
        return tuple(self.views)

    def public_domains(self, observation, num_mines, logical, proofs, boundary):
        grid = _oracles._public_grid(observation, num_mines, GameStatus.PLAYING)
        _need(all(any(_semantic_equal(p, known) for known in self.qualified_k + self.views)
                  for p in proofs), "Public premise has not passed its chronological admission.")
        supported = frozenset(p.target for p in proofs)
        for proof in proofs:
            _need(proof.num_mines == num_mines, "Public premise mine total differs.")
            _oracles._public_extension(proof.observation, grid, supported)
        return _oracles._supported_domains(grid, num_mines, logical, supported)

    def qualify(self, flag, *, calls, findings):
        _require_audit_graph(flag, checked=self.graph_checked)
        _checked(flag, _evidence.ExternalV1FlagProvenance)
        _need(self.matches(flag.prior_flags, tuple(self.records)),
              "FLAG prior DAG differs from unique chronological executed provenance.")
        self.reference_checks += len(flag.prior_flags)
        _need(not self.records or flag.input_index > self.records[-1].input_index,
              "Physical FLAG admissions must have increasing input indices.")
        count = len(_cells(flag.observation, CellState.HIDDEN))
        flat = replace(flag, prior_flags=tuple(self.shallow))
        raw_cache = {id(p): q.raw_verification for p, q in zip(self.shallow, self.qualifications)}
        self.raw_checks += 1
        raw = (_evidence.verify_v1_flag_provenance(flat) if not self.records
               else _evidence._check_v1_flag_provenance(flat, raw_cache))
        node = raw
        if raw.status == "NOT_EVALUATED" and raw.detail.startswith("FLAG antecedent:"):
            self.conditioned_checks += 1
            conditioned = {id(p): _evidence.EvidenceComparison(
                "PASS", p.boundary, detail="CHRONOLOGICALLY_ADMITTED_PHYSICAL_PREMISE")
                for p in self.shallow}
            node = _evidence._check_v1_flag_provenance(flat, conditioned)
        _checked(raw, _evidence.EvidenceComparison)
        _checked(node, _evidence.EvidenceComparison)
        status, detail = "PASS", "Independent current-node public evidence with qualified chronological premises."
        result = digest = expected_flag = label = binding = None
        span = None
        exact = flag.decision.evidence.kind is DecisionKind.GLOBAL_CERTAINTY
        # The frozen checker has one post-enumeration failure and one success
        # label. Shape/provenance failures occur before combinations is entered.
        bounded_ran = exact and count <= 16 and node.detail in (
            "INDEPENDENT_BOUNDED_PUBLIC_V1_EXACT_FLAG",
            "Exact FLAG counts disagree with public complete worlds.")
        bounded_status = (node.status if bounded_ran else
                          "NOT_EVALUATED" if exact else "NOT_APPLICABLE")
        reason = (_FLAG_BOUNDED_REASON if exact and count > 16 else
                  "Independent check stopped before bounded enumeration: " + node.detail
                  if exact and not bounded_ran else None)
        if raw.status == "FAIL" or node.status == "FAIL":
            status, detail = "FAIL", "Independent public FLAG contradiction: " + (
                raw.detail if raw.status == "FAIL" else node.detail)
        elif any(q.status != "PASS" for q in self.qualifications):
            status, detail = ("FAIL" if any(q.status == "FAIL" for q in self.qualifications)
                              else "INCOMPLETE"), "An earlier physical premise did not qualify."
        elif exact and count > 16:
            if node.status != "NOT_EVALUATED" or node.detail != _FLAG_BOUNDED_REASON:
                status, detail = "FAIL", "Unexpected independent exact coverage above the envelope."
            elif self.prerequisite is None:
                status, detail = "INCOMPLETE", "Accepted E0 prerequisite binding is absent."
            else:
                try:
                    binding = _checked(self.prerequisite, _e1.AcceptedE0Prerequisite)
                    self.active(tuple(self.records), flag.observation, flag.input_index)
                    _oracles._supported_domains(flag.observation, flag.num_mines, frozenset(),
                                                frozenset(v.target for v in self.views))
                    digest = _oracles.oracle_b_input_digest(flag.observation, flag.num_mines, frozenset())
                    label = _oracles.SHARED_KERNEL_EVIDENCE
                    start = len(calls)
                    result = _oracles._materialized_exact(flag.observation, flag.num_mines, frozenset())
                    differences = _flag_reference_differences(flag, result)
                    if result is None:
                        status, detail = "INCOMPLETE", "Required Oracle-B comparison unavailable."
                        raise _MissingFlagReference(detail)
                    expected_flag = (_evidence.MoveProjection(
                        Action.FLAG, *min(result.G1, key=lambda c: (c[1], c[0]))) if result.G1 else None)
                    span = _diagnostic_span(calls, start, (_call_expectation(
                        "B", flag.observation, flag.num_mines, frozenset(), result),),
                        True, flag.input_index, "EXTERNAL_V1_FLAG_B", findings)
                    if differences or span.status != "PASS":
                        status, detail = "FAIL", "; ".join(differences) or "Oracle-B diagnostic mismatch."
                    else:
                        detail = ("Frozen V1 execution and exact certainty; " + label
                                  + "; accepted E0 arithmetic qualification. Independent enumeration NOT_EVALUATED.")
                except (_MissingFlagReference, OSError, TimeoutError) as error:
                    status, detail = "INCOMPLETE", str(error)
                    if digest is not None and span is None:
                        span = _diagnostic_span(calls, start, (_call_expectation(
                            "B", flag.observation, flag.num_mines, frozenset()),),
                            False, flag.input_index, "EXTERNAL_V1_FLAG_B", findings)
                except _PUBLIC_ERRORS as error:
                    status, detail = "FAIL", str(error)
                    if digest is not None and span is None:
                        span = _diagnostic_span(calls, start, (_call_expectation(
                            "B", flag.observation, flag.num_mines, frozenset()),),
                            False, flag.input_index, "EXTERNAL_V1_FLAG_B", findings)
        elif node.status != "PASS":
            status, detail = "INCOMPLETE", "Independent local/bounded current-node proof did not PASS."
        qualification = ExternalV1FlagQualification(
            flag.input_index, flag.boundary, raw, node, flag.decision.evidence.kind,
            count, (flag.move.x, flag.move.y), bounded_ran, bounded_status, reason,
            tuple(f.input_index for f in flag.prior_flags), digest, result, expected_flag,
            label, binding, status, detail)
        if status == "PASS":
            validate_external_flag_qualification(qualification, flag, self.prerequisite)
        return qualification, span

    def admit(self, flag, qualification):
        self.records.append(flag)
        self.qualifications.append(qualification)
        self.shallow.append(replace(flag, prior_flags=()))
        if qualification.status == "PASS":
            target, v1 = (flag.move.x, flag.move.y), flag.decision.evidence
            if v1.kind is DecisionKind.LOCAL_DETERMINISTIC:
                clue = next(c.source for c in v1.constraints if target in c.hidden_cells
                            and c.remaining_mines == len(c.hidden_cells))
                view = _oracles.LocalMineCertificate(
                    flag.observation, flag.num_mines, clue, target, frozenset(), GameStatus.PLAYING)
            else:
                probability = v1.probability_result
                view = _oracles.ExactGlobalMineCertificate(
                    flag.observation, flag.num_mines, target, frozenset(), GameStatus.PLAYING,
                    probability.total_worlds,
                    tuple((p.coordinate, p.mine_worlds) for p in probability.probabilities))
            self.views.append(view)


def _v1_action(trace, effect, index, variant, num_mines, executed_flags, findings,
               premises=None, calls=None, spans=None):
    """Validate archived authority only; never invoke a V1 planner."""
    status, detail, verification, qualification = "PASS", "", None, None
    flag = trace.external_flag if variant == "K-CONTROL" else None
    try:
        if index and trace.decision is None:
            status, detail = "INCOMPLETE", "Missing noninitial V1 decision."
        else:
            _need(index != 0 or trace.decision is None, "Initial V1 input carries a decision.")
            _validate_execution(effect.before_observation, trace.move, trace.decision)
            if trace.decision is not None:
                _evidence.project_v1_decision(trace.decision)
        if variant == "K-CONTROL":
            flags = _cells(effect.before_observation, CellState.FLAGGED)
            active = tuple(f for f in executed_flags if (f.move.x, f.move.y) in flags)
            _need(premises.matches(trace.external_flag_antecedents, active),
                  "External FLAG antecedents differ from chronological executed flags.")
            if trace.move.action is Action.FLAG:
                if flag is None:
                    status, detail = "INCOMPLETE", "Missing executed V1 FLAG provenance."
                else:
                    _checked(flag, _evidence.ExternalV1FlagProvenance)
                    _need(flag.observation == effect.before_observation
                          and flag.num_mines == num_mines
                          and flag.move == effect.move
                          and flag.decision == _evidence.project_v1_decision(trace.decision)
                          and flag.boundary == flag.input_index == index
                          and premises.matches(flag.prior_flags, executed_flags),
                          "Executed V1 FLAG provenance binding differs.")
                    qualification, span = premises.qualify(flag, calls=calls, findings=findings)
                    if span is not None:
                        spans.append(span)
                    verification = qualification.raw_verification
                    _checked(verification, _evidence.EvidenceComparison)
                    _need(verification.boundary == index, "FLAG verifier boundary differs.")
                    status, detail = qualification.status, qualification.detail
            else:
                _need(flag is None, "Non-FLAG input carries external FLAG provenance.")
    except _PUBLIC_ERRORS as error:
        status, detail = "FAIL", str(error)
    findings.record(status, "V1 input " + str(index) + ": " + detail)
    return V1ActionAudit(index, status, detail, flag, verification, qualification)


def _replay(trace, effect, index, variant, case, table, session, external, findings):
    shadow = trace.shadow if variant == "K-CONTROL" else None
    decision = None
    ds, ps = "NOT_APPLICABLE", "NOT_APPLICABLE"
    ad = rd = ap = rp = None
    detail = ""
    if not index:
        try:
            _need(not trace.M_before and not trace.preinput_M, "Initial input has nonempty M.")
            if variant == "K-P0":
                _need(trace.selection is None and trace.category == "POLICY_INITIAL_OPEN",
                      "Initial K-P0 input is not the canonical policy action.")
                _runner.validate_k_p0_execution(
                    effect.before_observation, trace.move, status=GameStatus.PLAYING,
                    num_mines=case.num_mines, cursor=trace.cursor_before,
                    current_mines=trace.preinput_M, initial=True)
            else:
                _need(type(shadow) is _runner.ShadowCheckpoint and shadow == _runner.ShadowCheckpoint(),
                      "Initial shadow checkpoint is not empty/current.")
        except _PUBLIC_ERRORS as error:
            ds, detail = "FAIL", str(error)
            findings.record(ds, detail)
        return None, KReplayAudit(index, ds, ps, ad, rd, ap, rp, shadow, external, detail)
    if variant == "K-CONTROL":
        if type(shadow) is not _runner.ShadowCheckpoint:
            findings.check(False, "Missing shadow checkpoint.", missing=True)
            return None, KReplayAudit(index, "INCOMPLETE", ps, ad, rd, ap, rp, None, external,
                                      "Missing shadow checkpoint.")
        if shadow.failure is not None or not shadow.enabled or not shadow.evidence_valid:
            # Preserve the original checkpoint/failure/last-valid M. In
            # particular, never turn a stale attached decision into evidence.
            detail = ("Shadow disabled/invalidated: " + shadow.failure.failure_class + ": " + shadow.failure.detail
                      if shadow.failure is not None else "Healthy shadow lacks current evidence.")
            ds = ("FAIL" if shadow.failure is not None
                  and shadow.failure.failure_class != "SHADOW_TIMEOUT" else "INCOMPLETE")
            findings.record(ds, detail)
            findings.check(shadow.decision is None, "Invalidated shadow retained a decision.")
            return None, KReplayAudit(index, ds, ps, ad, rd, ap, rp, shadow, external, detail)
        decision = shadow.decision
    else:
        decision = trace.selection.evidence if trace.selection is not None else None
    if decision is None:
        findings.check(False, "Input " + str(index) + ": missing current K decision.", missing=True)
        return None, KReplayAudit(index, "INCOMPLETE", ps, ad, rd, ap, rp, shadow, external,
                                  "Missing current K decision.")
    try:
        _need(type(decision) is _capability.DecisionAnalysis, "Invalid K decision type.")
        _need(decision.observation == effect.before_observation and decision.num_mines == case.num_mines,
              "K decision public observation/mine total differs from sealed prefix.")
        _need(decision.local.before.M == trace.M_before and decision.after.M == trace.preinput_M,
              "K phase M snapshots differ from archived input.")
        _need(session.M == trace.M_before, "K replay prior M differs from archived chronological M.")
        admission = (_capability.CurrentPhysicalFlagAdmission(
            effect.before_observation, frozenset((f.move.x, f.move.y) for f in external))
            if variant == "K-CONTROL" else None)
        replay = session.analyze_decision(effect.before_observation, status=GameStatus.PLAYING,
                                         physical_flag_admission=admission)
        ad, rd = _digest(decision), _digest(replay)
        ds = "PASS" if _harness.canonical_bytes(decision) == _harness.canonical_bytes(replay) else "FAIL"
        findings.record(ds, "Input " + str(index) + ": K public decision replay differs.")
        if variant == "K-P0":
            selection = trace.selection
            _need(type(selection) is _policy.PolicySelection and trace.category == selection.category,
                  "K-P0 selection/category binding differs.")
            selected = _policy.select_policy(replay, trace.cursor_before, table)
            ap, rp = _digest(selection), _digest(selected)
            ps = "PASS" if _harness.canonical_bytes(selection) == _harness.canonical_bytes(selected) else "FAIL"
            findings.record(ps, "Input " + str(index) + ": K-P0 policy replay differs.")
            _runner.validate_k_p0_execution(
                effect.before_observation, trace.move, status=GameStatus.PLAYING,
                num_mines=case.num_mines, cursor=trace.cursor_before,
                current_mines=trace.preinput_M, decision=decision, selection=selection)
        else:
            _need(shadow.last_valid_boundary == index and shadow.last_valid_M == trace.preinput_M
                  and shadow.v1_continues is True, "Healthy shadow boundary/M differs.")
            if trace.decision is None or trace.soundness is None:
                findings.check(False, "Missing V1/shadow public comparison evidence.", missing=True)
            else:
                expected_soundness = _evidence.compare_shadow_soundness(
                    trace.decision, decision.selection_safe_cells, boundary=index)
                _need(_harness.canonical_bytes(trace.soundness)
                      == _harness.canonical_bytes(expected_soundness), "Archived shadow comparison differs.")
                _need(expected_soundness.classification != "SHADOW_SOUNDNESS_VIOLATION",
                      "Healthy shadow contains a diagnosed public semantic discrepancy.")
    except _PUBLIC_ERRORS as error:
        ds, detail = "FAIL", str(error)
        findings.record(ds, "K replay input " + str(index) + ": " + detail)
    return decision, KReplayAudit(index, ds, ps, ad, rd, ap, rp, shadow, external, detail)


def _mechanisms(result, effects, findings):
    observations, setups = [], []
    for index, (trace, effect) in enumerate(zip(result.traces, effects)):
        try:
            selection = trace.selection
            plan = None if selection is None else selection.plan
            setup, reveals, relevant, prior = frozenset(), frozenset(), frozenset(), ()
            terminal = None if plan is None else plan.actions[-1]
            if plan is not None:
                matches = tuple(c for c in selection.survivors
                                if c.plan == plan and c.category == selection.category)
                _need(len(matches) == 1, "Selected mechanism candidate is absent/ambiguous.")
                setup, reveals = matches[0].setup_cells, matches[0].reveal_cells
            kind = "OTHER"
            if terminal is not None and terminal.action is Action.CHORD:
                adjacent = _runner._neighbors((terminal.x, terminal.y), effect.before_observation)
                relevant = adjacent & _cells(effect.before_observation, CellState.FLAGGED)
                prior = tuple(i for i, target, chord in setups
                              if chord == (terminal.x, terminal.y) and target in relevant)
            if trace.category == "SETUP_CHORD" and trace.move.action is Action.FLAG:
                _need(terminal is not None and terminal.action is Action.CHORD,
                      "Setup FLAG lacks its current planned CHORD.")
                kind = "SETUP_CHORD_FLAG"
                setups.append((index, (trace.move.x, trace.move.y), (terminal.x, terminal.y)))
            elif trace.move.action is Action.CHORD:
                kind = "CHORD_AFTER_PRIOR_SETUP" if prior else "DIRECT_CHORD"
            observations.append(MechanismObservation(
                index, trace.move.action, (trace.move.x, trace.move.y), trace.category,
                setup, reveals, terminal, None if plan is None else plan.latency_us,
                None if plan is None else plan.reveals, trace.modeled_action_us,
                effect.safe_cells_opened_delta, kind, relevant, prior))
        except _PUBLIC_ERRORS as error:
            findings.check(False, "Mechanism input " + str(index) + ": " + str(error))
    return tuple(observations)


def _support_history(proofs, external, premises=None):
    """Unique checker views only; never recursively expand physical ancestry."""
    combined = list(proofs)
    if external:
        _need(premises is not None and premises.matches(external, tuple(premises.records)),
              "External proof history needs its chronological E1 admission registry.")
        _need(all(q.status == "PASS" for q in premises.qualifications),
              "External proof history contains an unqualified physical FLAG.")
        combined.extend(premises.views)
    unique = []
    for proof in combined:
        if proof not in unique:
            unique.append(proof)
    unique.sort(key=lambda p: sum(v != CellState.HIDDEN for row in p.observation for v in row))
    return tuple(unique)


def _call_expectation(oracle, grid, num_mines, retained, result=None, *, status="EVALUATED", reason=None):
    flags = _cells(grid, CellState.FLAGGED)
    unresolved = _cells(grid, CellState.HIDDEN) - retained
    method = "COMPLETE_WORLD_ENUMERATION" if oracle == "A" else "MATERIALIZED_EXACT"
    digest = (_oracles.oracle_a_input_digest(grid, flags | retained, unresolved, num_mines - len(flags | retained))
              if oracle == "A" else _oracles.oracle_b_input_digest(grid, num_mines, retained))
    output = None if result is None else _oracles.oracle_result_digest(result)
    return oracle, method, digest, output, len(unresolved), status, reason


def _history_expectations(proofs, *, independent=False):
    """Predict calls from public proof syntax, without doing Oracle arithmetic.

    Existing APIs recheck exact ancestors in order. An over-envelope ancestor
    stops independent A before opening a measurement; that absence is real.
    """
    expected = []
    for proof in proofs:
        if type(proof) is _oracles.ExactGlobalMineCertificate:
            count = len(_cells(proof.observation, CellState.HIDDEN) - proof.retained_mines)
            if independent and count > _oracles.ORACLE_A_MAX_VARIABLES:
                return tuple(expected), count
            oracle = "A" if count <= _oracles.ORACLE_A_MAX_VARIABLES else "B"
            arithmetic = _oracles.OracleAResult(proof.total_worlds, proof.mine_worlds)
            expected.append(_call_expectation(
                oracle, proof.observation, proof.num_mines, proof.retained_mines, arithmetic))
    return tuple(expected), None


def _diagnostic_span(calls, start, expected, complete, index, operation, findings):
    differences = []
    actual = calls[start:]
    if (complete and len(actual) != len(expected)) or len(actual) > len(expected):
        differences.append("Oracle call coverage/count differs.")
    for offset, call in enumerate(actual):
        try:
            _checked(call, _oracles.OracleCallDiagnostic)
            _need(call.sequence == start + offset, "Oracle diagnostic sequence differs.")
            _need(call.oracle in ("A", "B")
                  and call.method in ("COMPLETE_WORLD_ENUMERATION", "MATERIALIZED_EXACT"),
                  "Unexpected Oracle method.")
            _need(call.duration_ns > 0, "Actual Oracle call duration must be positive.")
            if offset < len(expected):
                oracle, method, digest, output, count, status, reason = expected[offset]
                _need((call.oracle, call.method, call.input_digest, call.variable_count)
                      == (oracle, method, digest, count), "Oracle input/method/variable binding differs.")
                if not complete and call.status == "ERROR" and offset == len(actual) - 1:
                    continue
                _need(call.status == status and call.output_digest == output,
                      "Oracle output/status binding differs.")
                if status == "NOT_EVALUATED":
                    _need(call.reason == reason and count > 16,
                          "Oracle non-evaluation reason/envelope differs.")
        except _PUBLIC_ERRORS as error:
            differences.append(str(error))
    span = OracleDiagnosticSpan(index, operation, start, len(calls),
                                "FAIL" if differences else "PASS", tuple(differences))
    findings.record(span.status, operation + " diagnostics: " + "; ".join(differences))
    return span


class _ExactReferenceReuse:
    """One audit's arithmetic payloads, never certificate/history authority.

    Every frozen history, public-domain, target and claimed-count check still
    executes. Only their arithmetic leaves reuse successful results. Full
    canonical values (including types), not object IDs or digest equality,
    identify those leaves. Exceptions and non-evaluation are never cached.

    Private function bindings keep the existing validation implementation and
    its call graph intact without patching any module or process-global state.
    Nothing here is retained by the returned audit or shared with another run.
    """

    def __init__(self):
        self._a = {}
        self._b = {}
        namespace = dict(vars(_oracles))
        for name in (
                "_check_exact", "_verify_history", "verify_local_certificate",
                "verify_exact_global_certificate", "enumerate_public_worlds",
                "materialized_exact_reference"):
            namespace[name] = self._bind(namespace[name], namespace)
        namespace["_enumerate_supported"] = self._enumerate_supported
        namespace["_materialized_exact"] = self._materialized_exact
        self.oracles = SimpleNamespace(**namespace)
        self.audit_acquisition = self._bind(
            _harness.audit_acquisition,
            dict(vars(_harness), _oracles=self.oracles))

    @staticmethod
    def _bind(function, namespace):
        # Keep injected verifier seams observable, including failed results.
        if type(function) is not FunctionType:
            return function
        bound = FunctionType(function.__code__, namespace, function.__name__,
                             function.__defaults__, function.__closure__)
        bound.__kwdefaults__ = function.__kwdefaults__
        return bound

    def _enumerate_supported(self, grid, fixed, unresolved, remaining):
        key = _harness.canonical_bytes((grid, fixed, unresolved, remaining))
        if key not in self._a:
            result = _oracles._enumerate_supported(grid, fixed, unresolved, remaining)
            _need(type(result) is _oracles.OracleAResult, "Oracle A returned the wrong class.")
            self._a[key] = result
            return result
        # Preserve logical diagnostic coverage, but measure this retrieval,
        # never replay the duration of the earlier expensive enumeration.
        with _oracles.measure_oracle_call(
                "A", "COMPLETE_WORLD_ENUMERATION",
                _oracles.oracle_a_input_digest(grid, fixed, unresolved, remaining),
                len(unresolved)) as measurement:
            result = self._a[key]
            measurement.finish(result)
            return result

    def _materialized_exact(self, grid, num_mines, retained):
        key = _harness.canonical_bytes((grid, num_mines, retained))
        if key not in self._b:
            result = _oracles._materialized_exact(grid, num_mines, retained)
            _need(type(result) is _oracles.OracleBResult, "Oracle B returned the wrong class.")
            self._b[key] = result
            return result
        variables = len(_cells(grid, CellState.HIDDEN) - retained)
        with _oracles.measure_oracle_call(
                "B", "MATERIALIZED_EXACT",
                _oracles.oracle_b_input_digest(grid, num_mines, retained),
                variables) as measurement:
            result = self._b[key]
            measurement.finish(result)
            return result


def _audit_certificate(certificate, index, proofs, external, calls, findings, premises=None,
                       references=None):
    start = len(calls)
    checker = _oracles if references is None else references.oracles
    if premises is None and not external:
        acquisition = _harness.audit_acquisition if references is None else references.audit_acquisition
        audit = acquisition(certificate, boundary=index,
                            prior_certificates=proofs, external_flags=external)
    else:
        # K-CONTROL's physical premises were independently admitted once at
        # their executed inputs. Existing low-level certificate checks preserve
        # direct local/exact strength without re-proving that DAG at each use.
        external_audits, check = [], None
        try:
            _need(premises is not None, "Missing chronological physical premise qualification.")
            views = premises.active(external, certificate.observation, index)
            external_audits = [
                _harness.ExternalFlagAudit(record, q.raw_verification, (view,))
                for record, q, view in zip(premises.records, premises.qualifications, views)]
            history = _support_history(proofs, external, premises)
            premises.public_domains(certificate.observation, certificate.num_mines,
                                    certificate.retained_mines, history, index)
            supported = frozenset(p.target for p in history)
            check = (_oracles._check_local(certificate, supported)
                     if type(certificate) is _oracles.LocalMineCertificate
                     else checker._check_exact(certificate, supported))
            status, detail = "PASS", "Public physical premises admitted once; current K certificate independently checked."
        except _PUBLIC_ERRORS as error:
            status, detail = "FAIL", str(error)
        audit = _harness.AcquisitionAudit(
            certificate, index, proofs, tuple(external_audits), check, status, detail,
            certificate.retained_mines, certificate.retained_mines | {certificate.target})
    _need(type(audit) is _harness.AcquisitionAudit, "Acquisition verifier returned the wrong class.")
    bound = (audit.certificate == certificate and audit.boundary == index
             and audit.prior_certificates == proofs
             and (premises.matches(tuple(f.record for f in audit.external_flags), external)
                  if premises is not None else tuple(f.record for f in audit.external_flags) == external)
             and audit.owned_M_before == certificate.retained_mines
             and audit.owned_M_after == certificate.retained_mines | {certificate.target})
    findings.check(bound, "Acquisition audit is not bound to the requested certificate/history.")
    findings.record(audit.status, "Acquisition input " + str(index) + ": " + audit.detail)
    # The accepted verifier can stop while checking an invalid external flag.
    # Keep its returned audit even then; never derive proof views from that
    # unverified flag merely to explain diagnostics.
    support = list(proofs)
    for flag in audit.external_flags:
        if flag.verification.status == "PASS":
            support.extend(flag.public_support)
    unique = []
    for proof in support:
        if proof not in unique:
            unique.append(proof)
    unique.sort(key=lambda p: sum(v != CellState.HIDDEN for row in p.observation for v in row))
    history = tuple(unique) + (
        (certificate,) if type(certificate) is _oracles.ExactGlobalMineCertificate else ())
    if premises is not None:
        history = ((certificate,) if type(certificate) is _oracles.ExactGlobalMineCertificate
                   and audit.status == "PASS" else ())
    expected, _ = _history_expectations(history)
    span = _diagnostic_span(calls, start, expected, audit.status == "PASS", index,
                            "ACQUISITION", findings)
    passed = bound and audit.status == "PASS" and span.status == "PASS"
    if passed and premises is not None:
        premises.qualified_k.append(certificate)
    return audit, span, passed


def _exact_differences(expected, actual):
    if type(expected) is not _capability.ExactAnalysis or type(actual) is not _oracles.OracleBResult:
        return ("Missing exact semantic record.",)
    differences = tuple(name + " differs" for name in _EXACT_FIELDS
                        if _harness.canonical_bytes(getattr(expected, name))
                        != _harness.canonical_bytes(getattr(actual, name)))
    if (actual.shared_kernel_evidence != _oracles.SHARED_KERNEL_EVIDENCE
            or actual.kernel != _oracles.FROZEN_EXACT_KERNEL):
        differences += ("Frozen exact-kernel identity/shared-kernel disclosure differs.",)
    if type(actual.total_worlds) is not int or actual.total_worlds <= 0:
        differences += ("Exact reference has no positive integer world count.",)
    return differences


def _oracle_b(index, phase, observation, num_mines, logical, proofs, expected, calls, findings,
              premises=None, references=None):
    start = len(calls)
    checker = _oracles if references is None else references.oracles
    actual = None
    differences = ()
    complete = False
    predicted, _ = _history_expectations(proofs) if premises is None else ((), None)
    # The leaf key exists even if the Oracle fails before producing a result.
    leaf = _call_expectation("B", observation, num_mines, logical)
    try:
        if premises is None:
            actual = checker.materialized_exact_reference(
                observation, num_mines, status=GameStatus.PLAYING,
                logical_mines=logical, proofs=proofs)
        else:
            premises.public_domains(observation, num_mines, logical, proofs, index)
            actual = checker._materialized_exact(observation, num_mines, logical)
        _need(type(actual) is _oracles.OracleBResult, "Oracle B returned the wrong class.")
        leaf = _call_expectation("B", observation, num_mines, logical, actual)
        complete = True
        differences = _exact_differences(expected, actual)
        materialized = tuple(tuple(int(CellState.FLAGGED)
                                   if v == CellState.HIDDEN and (x, y) in logical else v
                                   for x, v in enumerate(row)) for y, row in enumerate(observation))
        if actual.materialized_observation != materialized:
            differences += ("Oracle B informational Q(M) differs from its public premises.",)
    except _PUBLIC_ERRORS as error:
        differences = ("Oracle B public check: " + str(error),)
    span = _diagnostic_span(calls, start, predicted + (leaf,), complete, index, "PHASE_" + phase + "_B", findings)
    status = "FAIL" if differences or span.status == "FAIL" else "PASS"
    findings.record(status, "Oracle B Phase " + phase + " input " + str(index) + ": " + "; ".join(differences))
    interpretation = ("AUDITOR re-enumeration only; solver Phase E is restriction, not re-enumeration"
                      if phase == "E" else "PUBLIC PHASE-D SHARED-KERNEL REPRESENTATION EVIDENCE")
    return OracleBAudit(index, phase, logical, proofs, expected, actual, status, differences, interpretation), span


def _oracle_a(index, observation, num_mines, logical, proofs, exact, oracle_b, calls, findings,
              premises=None, references=None):
    start = len(calls)
    checker = _oracles if references is None else references.oracles
    predicted, blocked_ancestor = _history_expectations(proofs, independent=True)
    if premises is not None:
        predicted = ()
    variables = len(_cells(observation, CellState.HIDDEN) - logical)
    actual = coverage = None
    differences = ()
    status, complete = "FAIL", False
    expected = predicted
    try:
        if premises is None:
            actual = checker.enumerate_public_worlds(
                observation, num_mines, status=GameStatus.PLAYING, logical_mines=logical, proofs=proofs)
        else:
            _, _, fixed, unresolved, remaining = premises.public_domains(
                observation, num_mines, logical, proofs, index)
            if blocked_ancestor is not None:
                raise _oracles.OracleANotEvaluated(blocked_ancestor)
            actual = checker._enumerate_supported(observation, fixed, unresolved, remaining)
        _need(type(actual) is _oracles.OracleAResult, "Oracle A returned the wrong class.")
        _need(blocked_ancestor is None and variables <= 16,
              "Oracle A claimed evaluation outside its qualified envelope.")
        coverage = _harness.OracleCoverage("ORACLE_A_EVALUATED", variables, 16, None)
        expected += (_call_expectation("A", observation, num_mines, logical, actual),)
        complete = True
        if (type(actual.total_worlds) is not int or actual.total_worlds <= 0
                or actual.total_worlds != exact.total_worlds
                or _harness.canonical_bytes(actual.mine_worlds) != _harness.canonical_bytes(exact.mine_worlds)):
            differences += ("Oracle A counts differ from K Phase D.",)
        if (oracle_b is None or actual.total_worlds != oracle_b.total_worlds
                or _harness.canonical_bytes(actual.mine_worlds) != _harness.canonical_bytes(oracle_b.mine_worlds)):
            differences += ("Oracle A counts differ from Oracle B Phase D.",)
        status = "FAIL" if differences else "PASS"
    except _oracles.OracleANotEvaluated as error:
        # Only this existing exception means ordinary finite-envelope coverage.
        # A blocked ancestor has no synthetic leaf diagnostic.
        coverage = _harness.OracleCoverage(error.status, error.variable_count, error.envelope, error.reason)
        expected_count = blocked_ancestor if blocked_ancestor is not None else variables
        if error.variable_count != expected_count or expected_count <= 16 or error.envelope != 16:
            differences = ("Oracle A non-evaluation is misbound to its public envelope.",)
        if blocked_ancestor is None:
            expected += (_call_expectation(
                "A", observation, num_mines, logical, status="NOT_EVALUATED",
                reason=type(error).__name__ + ":" + str(error)),)
        complete, status = True, "FAIL" if differences else "NOT_EVALUATED"
    except _PUBLIC_ERRORS as error:
        differences = ("Oracle A public check failed: " + str(error),)
        if blocked_ancestor is None:
            expected += (_call_expectation("A", observation, num_mines, logical),)
    span = _diagnostic_span(calls, start, expected, complete, index, "PHASE_D_A", findings)
    if span.status == "FAIL":
        status = "FAIL"
    if status == "FAIL":
        findings.record(status, "Oracle A input " + str(index) + ": " + "; ".join(differences))
    return OracleAAudit(index, coverage, actual, variables, status, differences), span


def _certificate_binding(decision, effect, num_mines, findings):
    local, exact = decision.local.certificates, decision.exact_certificates
    acquired = decision.local.after.M - decision.local.before.M
    g1 = frozenset() if decision.phase_d is None else decision.phase_d.G1
    local_sound = findings.check(type(local) is tuple and len(local) == len(acquired)
                                 and all(type(c) is _oracles.LocalMineCertificate for c in local)
                                 and frozenset(c.target for c in local) == acquired == decision.local.acquired_mines,
                                 "Local acquisition certificate coverage differs.")
    exact_sound = findings.check(type(exact) is tuple and len(exact) == len(g1)
                                 and all(type(c) is _oracles.ExactGlobalMineCertificate for c in exact)
                                 and frozenset(c.target for c in exact) == g1,
                                 "Exact acquisition certificate coverage differs.")
    for certificates, retained in ((local, decision.local.before.M), (exact, decision.local.after.M)):
        for certificate in certificates:
            bound = findings.check(
                certificate.observation == effect.before_observation and certificate.num_mines == num_mines
                and certificate.status is GameStatus.PLAYING and certificate.retained_mines == retained,
                "Certificate differs from the public pre-acquisition boundary.")
            if type(certificate) is _oracles.ExactGlobalMineCertificate:
                exact_sound &= bound
                exact_sound &= findings.check(
                    certificate.exact_reached is True and decision.phase_d is not None
                    and certificate.total_worlds == decision.phase_d.total_worlds
                    and certificate.mine_worlds == decision.phase_d.mine_worlds,
                    "Exact certificate differs from archived Phase D.")
            else:
                local_sound &= bound
    return local_sound, exact_sound


def _phase_e_invariants(decision, findings):
    d, e = decision.phase_d, decision.phase_e
    if d is None:
        return findings.check(e is None and decision.phase_e_status == "NOT_REACHED"
                              and not decision.exact_certificates,
                              "Unreached exact phase carries Phase-E/acquisition evidence.")
    if e is None:
        findings.check(False, "Reached Phase D is missing Phase E.", missing=True)
        return False
    return findings.check(
        decision.phase_e_status == ("REACHED_CHANGED" if d.G1 else "REACHED_NO_CHANGE")
        and decision.after.M == decision.local.after.M | d.G1
        and decision.after.U == decision.local.after.U - d.G1
        and e.total_worlds == d.total_worlds
        and e.mine_worlds == tuple((c, n) for c, n in d.mine_worlds if c not in d.G1)
        and e.G0 == d.G0 == decision.selection_safe_cells and not e.G1,
        "Phase E restriction/G0 preservation/empty G1/changed status differs.")


def _shadow_lifecycle(trace, index, previous, findings):
    current = trace.shadow
    if type(current) is not _runner.ShadowCheckpoint:
        return
    label = "Shadow input " + str(index) + ": "
    findings.check(type(current.enabled) is bool and type(current.evidence_valid) is bool
                   and current.v1_continues is True and type(current.last_valid_M) is frozenset
                   and (current.last_valid_boundary is None or type(current.last_valid_boundary) is int),
                   label + "checkpoint flags/M/boundary types differ.")
    if not index:
        return
    if type(previous) is not _runner.ShadowCheckpoint:
        findings.check(False, label + "previous checkpoint missing.", missing=True)
        return
    findings.check(trace.M_before == previous.last_valid_M, label + "prior M differs.")
    failure = current.failure
    if failure is None:
        findings.check(previous.enabled, label + "invalidated shadow resumed.")
        return
    if not findings.check(type(failure) is _runner.ShadowFailure, label + "malformed failure."):
        return
    findings.check(failure.failure_class in (
        "SHADOW_TIMEOUT", "SHADOW_EXCEPTION", "SHADOW_SEMANTIC_EXCEPTION",
        "SHADOW_COMPARISON_EXCEPTION", "SHADOW_MALFORMED_OUTPUT", "SHADOW_SOUNDNESS_VIOLATION"),
        label + "unknown natural failure class.")
    findings.check(not current.enabled and not current.evidence_valid and current.decision is None
                   and current.last_valid_M == previous.last_valid_M == trace.preinput_M
                   and current.last_valid_boundary == previous.last_valid_boundary,
                   label + "invalidation/last-valid M boundary differs.")
    findings.check(type(failure.detected_boundary) is int and 1 <= failure.detected_boundary <= index
                   and failure.last_valid_boundary == previous.last_valid_boundary
                   and failure.invalidation_scope == "WHOLE_SHADOW_STREAM"
                   and type(failure.detail) is str and bool(failure.detail),
                   label + "failure provenance differs.")
    if previous.failure is None:
        findings.check(failure.detected_boundary == index, label + "failure begins at a different input.")
    else:
        findings.check(failure == previous.failure, label + "failure history was rewritten.")
    findings.check(failure.implicated_boundary == (
        failure.detected_boundary if failure.failure_class == "SHADOW_SOUNDNESS_VIOLATION" else None),
        label + "implicated boundary differs.")


def _audit_run(result, variant, case, *, prerequisite=None):
    """Pure component assembly; private seam for detached non-E1 unit fixtures.

    The public entry below is the only plan/archive API and always authenticates
    its bindings before reaching this function. This seam never executes a run.
    """
    findings = _Findings()
    references = _ExactReferenceReuse()
    table = _physical.load_timing_table()
    effects, stream, stream_sound = _public_stream(result, variant, case, findings)
    costs, total, recorded = _costs(result, effects, table, findings)
    timings = _timing_coverage(result, variant, findings)
    v1_audits, replays, acquisitions, b_audits, a_audits, spans = [], [], [], [], [], []
    mechanisms = ()
    proofs, previous_m, executed_flags = (), frozenset(), ()
    proofs_valid, flags_valid = True, True
    premises = _PhysicalFlagPremises(prerequisite) if variant == "K-CONTROL" else None
    previous_shadow = None
    with _oracles.collect_oracle_diagnostics() as calls:
        if stream_sound:
            session = (_capability.KLocalSession(case.width, case.height, case.num_mines)
                       if variant != "CONTROL" else None)
            for index, (trace, effect) in enumerate(zip(result.traces, effects)):
                external = ()
                flag_check = None
                active_flags_valid = flags_valid
                if variant in ("CONTROL", "K-CONTROL"):
                    flag_check = _v1_action(trace, effect, index, variant, case.num_mines,
                                            executed_flags, findings, premises, calls, spans)
                    v1_audits.append(flag_check)
                if variant == "CONTROL":
                    continue
                findings.check(type(trace.M_before) is frozenset and type(trace.preinput_M) is frozenset
                               and trace.M_before == previous_m and trace.M_before <= trace.preinput_M,
                               "Input " + str(index) + ": chronological M lifecycle differs.")
                previous_m = trace.preinput_M
                if variant == "K-CONTROL":
                    external = trace.external_flag_antecedents
                    active = tuple(f for f in executed_flags
                                   if (f.move.x, f.move.y) in _cells(effect.before_observation, CellState.FLAGGED))
                    active_flags_valid &= premises.matches(external, active)
                    _shadow_lifecycle(trace, index, previous_shadow, findings)
                    previous_shadow = trace.shadow
                try:
                    decision, replay = _replay(trace, effect, index, variant, case, table,
                                               session, external, findings)
                    replays.append(replay)
                    if decision is not None:
                        local_bound, exact_bound = _certificate_binding(
                            decision, effect, case.num_mines, findings)
                        _phase_e_invariants(decision, findings)
                        # Retain every certificate check, even when replay has
                        # already diagnosed a mismatch. Invalid proof histories
                        # never gain authority for subsequent D/E Oracle work.
                        for certificate in decision.local.certificates:
                            audit, span, passed = _audit_certificate(
                                certificate, index, proofs, external, calls, findings, premises, references)
                            acquisitions.append(audit)
                            spans.append(span)
                            proofs += (certificate,)
                            proofs_valid &= passed
                        d_history = (_support_history(proofs, external, premises)
                                     if proofs_valid and active_flags_valid else ())
                        d_ready = (local_bound and proofs_valid and active_flags_valid
                                   and decision.observation == effect.before_observation
                                   and decision.num_mines == case.num_mines
                                   and decision.local.before.M == trace.M_before)
                        d_b = None
                        if decision.phase_d is not None:
                            if d_ready:
                                d_b, span = _oracle_b(
                                    index, "D", effect.before_observation, case.num_mines,
                                    decision.local.after.M, d_history, decision.phase_d, calls, findings, premises,
                                    references)
                                b_audits.append(d_b)
                                spans.append(span)
                                a, span = _oracle_a(
                                    index, effect.before_observation, case.num_mines,
                                    decision.local.after.M, d_history, decision.phase_d, d_b.result, calls, findings,
                                    premises, references)
                                a_audits.append(a)
                                spans.append(span)
                            else:
                                reason = "Phase D public proof history is incomplete/invalid."
                                findings.check(False, reason, missing=True)
                                b_audits.append(OracleBAudit(
                                    index, "D", decision.local.after.M, d_history, decision.phase_d,
                                    None, "INCOMPLETE", (reason,), "PUBLIC PHASE-D CHECK NOT EVALUATED"))
                                a_audits.append(OracleAAudit(
                                    index, None, None,
                                    len(_cells(effect.before_observation, CellState.HIDDEN) - decision.local.after.M),
                                    "INCOMPLETE", (reason,)))
                        for certificate in decision.exact_certificates:
                            audit, span, passed = _audit_certificate(
                                certificate, index, proofs, external, calls, findings, premises, references)
                            acquisitions.append(audit)
                            spans.append(span)
                            proofs += (certificate,)
                            proofs_valid &= passed
                        if decision.phase_e is not None:
                            if (d_ready and exact_bound and proofs_valid
                                    and d_b is not None and d_b.status == "PASS"):
                                e_history = _support_history(proofs, external, premises)
                                e, span = _oracle_b(
                                    index, "E", effect.before_observation, case.num_mines,
                                    decision.after.M, e_history, decision.phase_e, calls, findings, premises,
                                    references)
                                b_audits.append(e)
                                spans.append(span)
                            else:
                                reason = "Phase E requires publicly audited exact G1 certificates and Phase D."
                                findings.check(False, reason, missing=True)
                                b_audits.append(OracleBAudit(
                                    index, "E", decision.after.M, (), decision.phase_e, None,
                                    "INCOMPLETE", (reason,),
                                    "AUDITOR re-enumeration only; not performed without public prerequisites"))
                except _PUBLIC_ERRORS as error:
                    proofs_valid = False
                    findings.check(False, "K public evidence input " + str(index) + ": " + str(error))
                if variant == "K-CONTROL" and trace.move.action is Action.FLAG:
                    if trace.external_flag is not None:
                        executed_flags += (trace.external_flag,)
                        if flag_check.external_qualification is not None:
                            premises.admit(trace.external_flag, flag_check.external_qualification)
                    flags_valid &= (flag_check.status == "PASS"
                                    and flag_check.external_qualification is not None
                                    and flag_check.external_qualification.status == "PASS")
            if variant != "CONTROL":
                findings.check(result.final_M == previous_m, "Terminal archive changed last legitimate M.")
            if variant == "K-CONTROL":
                expected = replace(result.traces[-1].shadow, decision=None, evidence_valid=False)
                findings.check(result.shadow == expected, "Final shadow checkpoint differs from last input.")
            if variant == "K-P0":
                mechanisms = _mechanisms(result, effects, findings)
        else:
            findings.check(False, "Public semantic audit unavailable for an incomplete/corrupt input stream.",
                           missing=True)
    oracle_calls = tuple(calls)
    # Every call must belong to exactly one operation within this run, including
    # nested proof checks. Never sum these durations with runner/nested spans.
    cursor = 0
    for span in spans:
        findings.check(span.start == cursor and span.stop >= span.start,
                       "Oracle diagnostic operation spans overlap or omit calls.")
        cursor = span.stop
    findings.check(cursor == len(oracle_calls), "Oracle diagnostics contain an unbound operation.")
    p3 = None
    p3_status = "NOT_APPLICABLE"
    if variant in ("CONTROL", "K-P0"):
        p3 = _harness.extract_guess_checkpoints(
            _harness.ExecutionArchive(case.case_id, variant, result), num_mines=case.num_mines)
        _checked(p3, _harness.GuessCheckpointAudit)
        findings.check(p3.case_id == case.case_id and p3.variant == variant
                       and p3.num_mines == case.num_mines, "P-3 extraction identity differs.")
        p3_status = p3.status
        if p3_status != "COMPLETE":
            findings.check(False, "P-3 one-run evidence: " + "; ".join(p3.incomplete), missing=True)
    status = "FAIL" if findings.failures else "INCOMPLETE" if findings.missing else "PASS"
    return dict(
        public_effect_audit=stream, cost_audits=costs, expected_total_us=total, recorded_total_us=recorded,
        v1_audits=tuple(v1_audits), replay_audits=tuple(replays), acquisition_audits=tuple(acquisitions),
        oracle_a_audits=tuple(a_audits), oracle_b_audits=tuple(b_audits), oracle_calls=oracle_calls,
        oracle_spans=tuple(spans), p3_audit=p3, p3_status=p3_status,
        mechanism_observations=mechanisms,
        mechanism_status=("COMPLETE" if stream_sound and len(mechanisms) == len(result.traces) else "INCOMPLETE")
                         if variant == "K-P0" else "NOT_APPLICABLE",
        timings=timings, timing_context=TIMING_CONTEXT,
        discrepancies=tuple(findings.failures), incomplete_reasons=tuple(findings.missing),
        audit_status=status,
        physical_flag_work=PhysicalFlagWork(0, 0, 0, 0, 0) if premises is None else premises.work(),
    )


_AUDIT_RECORD_TYPES = (
    E1AuditSourceFile, E1AuditSourceIdentity, ModelCCostAudit, V1ActionAudit, KReplayAudit,
    OracleBAudit, OracleAAudit, OracleDiagnosticSpan, MechanismObservation, TimingSpan, TimingCoverage,
    E1RunAudit, _e1.ScheduleEntry, _e1.SealedCaseRegistration, _e1.RuntimeIdentity,
    ExternalV1FlagQualification, PhysicalFlagWork, _e1.AcceptedE0Prerequisite,
    _harness.AcquisitionAudit, _harness.ExternalFlagAudit, _harness.OracleCoverage,
    _harness.GuessCheckpointAudit, _harness.GuessCheckpoint,
    _oracles.OracleAResult, _oracles.OracleBResult, _oracles.OracleCallDiagnostic,
    _oracles.LocalCertificateCheck, _oracles.ExactGlobalCertificateCheck,
) + _execution._RESULT_RECORD_TYPES


def _require_audit_graph(value, active=None, checked=None):
    """Closed immutable vocabulary; no live owner, layout, callback or handle."""
    if type(value) in (str, int, bool, type(None), Fraction, Action, CellState, GameStatus, DecisionKind):
        return
    active = set() if active is None else active
    checked = set() if checked is None else checked
    key = id(value)
    _need(key not in active, "Cyclic audit graph.")
    if key in checked:
        return
    active.add(key)
    if type(value) in (tuple, frozenset):
        children = value
    else:
        _need(type(value) in _AUDIT_RECORD_TYPES and type(value).__dataclass_params__.frozen,
              "Unsupported mutable/live value in audit graph.")
        names = tuple(f.name for f in fields(value))
        _need(not hasattr(value, "__dict__") or set(vars(value)) == set(names),
              "Unexpected audit record attachment.")
        children = tuple(getattr(value, name) for name in names)
    for child in children:
        _require_audit_graph(child, active, checked)
    active.remove(key)
    if type(checked) is dict:
        checked[key] = value  # retain work-cache referents; never serialize IDs
    else:
        checked.add(key)


def audit_scheduled_run(plan, archive):
    """Audit one completed detached run, with current source checks on both sides."""
    source = capture_audit_source_identity(plan, archive)
    evidence = _audit_run(archive.result, archive.schedule_entry.variant, archive.case,
                          prerequisite=plan.prerequisite)
    _need(capture_audit_source_identity(plan, archive) == source, "Source changed during public audit.")
    return E1RunAudit(
        source, archive.execution_source_identity.digest, archive.schedule_entry, archive.case,
        archive.schedule_entry.variant, archive.schedule_entry.repetition, **evidence)
