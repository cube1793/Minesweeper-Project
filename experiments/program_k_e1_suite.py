"""Pure cross-run semantics for a supplied, detached fixed E1 suite.

PASS describes this aggregate only. Resource qualification and effectiveness
remain unevaluated. Source reads authenticate provenance; all evidence comes
from the caller's immutable records.
"""

from dataclasses import asdict, dataclass, fields, replace
from fractions import Fraction
import hashlib
import json
from math import isfinite
from pathlib import Path

from core_engine import Action, CellState, GameStatus
from experiments import program_k_e1_audit as _audit
from experiments import program_k_e1_execution as _execution
from experiments import program_k_e1_harness as _e1
from experiments import program_k_evidence as _evidence
from experiments import program_k_harness as _harness
from experiments import program_k_oracles as _oracles
from experiments import program_k_runner as _runner
from simple_algorithm import SimpleMove
from simple_decision import DecisionKind
from stage3_runner import Stage3ActionTrace


SUITE_SOURCE_PATH = "experiments/program_k_e1_suite.py"
TIMING_CONTEXT = _audit.TIMING_CONTEXT
RESOURCE_STATUS = "NOT_EVALUATED_IN_SLICE_4"
EFFECTIVENESS_STATUS = "NOT_EVALUATED_IN_E1"
N2_STATUS = "OPEN_FOR_OPERATIONAL_G9_LAYER"
_AUTHORITIES = ("spec_sha256", "protocol_sha256", "model_id",
                "profile_sha256", "table_sha256")


class E1SuiteError(ValueError):
    """Unbound, unsafe or stale inputs cannot form an aggregate."""


def _need(condition, detail):
    if not condition:
        raise E1SuiteError(detail)


def _checked(value, cls):
    _need(type(value) is cls, "Expected exact " + cls.__name__ + ".")
    try:
        return replace(value)
    except (ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        raise E1SuiteError("Invalid " + cls.__name__ + ": " + str(error)) from error


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Invalid SHA-256.")


@dataclass(frozen=True, slots=True)
class E1SuiteSourceFile:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(type(self.path) is str and self.path == SUITE_SOURCE_PATH,
              "Only the suite module extends the runtime identity.")
        _sha(self.sha256)
        _need(type(self.size_bytes) is int and self.size_bytes > 0, "Invalid suite byte size.")


@dataclass(frozen=True, slots=True)
class E1SuiteSourceIdentity:
    audit_source_digest: str
    suite_file: E1SuiteSourceFile
    spec_sha256: str
    protocol_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        _sha(self.audit_source_digest)
        _checked(self.suite_file, E1SuiteSourceFile)
        try:
            _e1._frozen_identities(self)
        except ValueError as error:
            raise E1SuiteError("Frozen suite authority differs.") from error

    @property
    def digest(self):
        _checked(self, E1SuiteSourceIdentity)
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditedScheduledRun:
    schedule_entry: _e1.ScheduleEntry
    case: _e1.SealedCaseRegistration
    archive: _execution.E1ScheduledRunArchive
    archive_content_digest: str
    audit: _audit.E1RunAudit
    audit_content_digest: str
    execution_source_digest: str
    audit_source_digest: str


@dataclass(frozen=True, slots=True)
class ScheduleCoverage:
    expected_count: int
    archive_count: int
    audit_count: int
    keys: tuple
    status: str


@dataclass(frozen=True, slots=True)
class SemanticRepetitionProjection:
    """Tagged immutable field trees; numeric timing noise is replaced explicitly."""

    case_id: str
    variant: str
    result: tuple
    audit_fields: tuple
    missing_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepetitionDeterminism:
    case_id: str
    variant: str
    first: SemanticRepetitionProjection
    second: SemanticRepetitionProjection
    status: str


@dataclass(frozen=True, slots=True)
class PhysicalStreamProjection:
    moves: tuple
    cursors: tuple
    costs_us: tuple
    cumulative_us: tuple
    total_us: int
    terminal_status: GameStatus
    input_statuses: tuple
    guesses: tuple


@dataclass(frozen=True, slots=True)
class ControlIdentityPair:
    case_id: str
    repetition: int
    control: PhysicalStreamProjection
    k_control: PhysicalStreamProjection
    public_effect_comparisons: tuple[_evidence.EvidenceComparison, ...]
    v1_decision_comparisons: tuple[_evidence.EvidenceComparison, ...]
    physical_differences: tuple[str, ...]
    incomplete_reasons: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class P3OutcomePair:
    case_id: str
    repetition: int
    comparison: _harness.GuessComparison
    control_outcome: GameStatus
    kp0_outcome: GameStatus
    outcome: str
    status: str


@dataclass(frozen=True, slots=True)
class ProductiveProgression:
    case_id: str
    repetition: int
    setup_input_indices: tuple[int, ...]
    setup_targets: tuple
    chord_input_index: int
    chord_target: tuple
    safe_cells_opened_delta: int


@dataclass(frozen=True, slots=True)
class MechanismCoverage:
    status: str
    progressions: tuple[ProductiveProgression, ...]
    observed_case_ids: tuple[str, ...]
    invalid_reasons: tuple[str, ...]
    abandoned_setups: tuple
    nonproductive_chords: tuple


@dataclass(frozen=True, slots=True)
class GameModelCDiagnostic:
    case_id: str
    repetition: int
    control_outcome: GameStatus
    control_us: int
    k_control_outcome: GameStatus
    k_control_us: int
    kp0_outcome: GameStatus
    kp0_us: int
    outcome: str
    delta_us: int | None


@dataclass(frozen=True, slots=True)
class ModelCDiagnostics:
    games: tuple[GameModelCDiagnostic, ...]
    ww_count: int
    wl_count: int
    lw_count: int
    ll_count: int
    control_wins: int
    control_losses: int
    kp0_wins: int
    kp0_losses: int
    ww_control_total_us: int
    ww_kp0_total_us: int
    ww_total_delta_us: int
    kp0_faster_count: int
    control_faster_count: int
    tie_count: int
    ww_deltas: tuple
    interpretation: str = "Fixed-suite complete-game diagnostics; no effectiveness inference."


@dataclass(frozen=True, slots=True)
class VariantDiagnosticCounts:
    variant: str
    runs: int
    actions_audited: int
    acquisition_audits: int
    oracle_a_evaluated: int
    oracle_a_not_evaluated: int
    oracle_b_phase_d: int
    oracle_b_phase_e: int
    oracle_calls: int
    p3_checkpoints: int
    setup_flags: int
    actual_chords: int
    productive_progressions: int
    failure_records: int
    incomplete_records: int
    failed_runs: int
    incomplete_runs: int


@dataclass(frozen=True, slots=True)
class RunnerTimingSamples:
    variant: str
    name: str
    boundary: str
    sample_count: int
    measured_ns: tuple[int, ...]
    not_applicable_count: int
    unmeasured_count: int
    unmeasured_required_count: int
    absent_record_count: int
    samples: tuple


@dataclass(frozen=True, slots=True)
class OracleTimingSamples:
    variant: str
    oracle: str
    method: str
    sample_count: int
    measured_ns: tuple[int, ...]
    samples: tuple


@dataclass(frozen=True, slots=True)
class SuiteDiagnostics:
    by_variant: tuple[VariantDiagnosticCounts, ...]
    runner_timings: tuple[RunnerTimingSamples, ...]
    oracle_timings: tuple[OracleTimingSamples, ...]
    timing_context: str = TIMING_CONTEXT
    resource_status: str = RESOURCE_STATUS
    n2_status: str = N2_STATUS


@dataclass(frozen=True, slots=True)
class E1SuiteAggregate:
    source_identity: E1SuiteSourceIdentity
    plan_identity: str
    plan: _e1.E1Plan
    bindings: tuple[AuditedScheduledRun, ...]
    coverage: ScheduleCoverage
    repetitions: tuple[RepetitionDeterminism, ...]
    control_identity_pairs: tuple[ControlIdentityPair, ...]
    p3_outcome_pairs: tuple[P3OutcomePair, ...]
    mechanism_coverage: MechanismCoverage
    model_c: ModelCDiagnostics
    diagnostics: SuiteDiagnostics
    semantic_failures: tuple[str, ...]
    incomplete_reasons: tuple[str, ...]
    suite_status: str
    supplement_status: str
    resource_status: str = RESOURCE_STATUS
    effectiveness_status: str = EFFECTIVENESS_STATUS
    n2_status: str = N2_STATUS


# Exact classes, never arbitrary dataclasses or a module-name wildcard. In
# particular, no evaluator records or answer-bearing construction records enter.
_RECORD_TYPES = (
    _e1.AcceptedE0Prerequisite, _e1.E1SourceFile, _e1.E1SourceIdentity, _e1.E1Plan,
    _execution.E1ExecutionSourceFile, _execution.E1ExecutionSourceIdentity,
    _execution.CaseMaterializationReceipt, _execution.E1ScheduledRunArchive,
    _harness.GuessComparison,
    E1SuiteSourceFile, E1SuiteSourceIdentity, AuditedScheduledRun, ScheduleCoverage,
    SemanticRepetitionProjection, RepetitionDeterminism, PhysicalStreamProjection,
    ControlIdentityPair, P3OutcomePair, ProductiveProgression, MechanismCoverage,
    GameModelCDiagnostic, ModelCDiagnostics, VariantDiagnosticCounts,
    RunnerTimingSamples, OracleTimingSamples, SuiteDiagnostics, E1SuiteAggregate,
) + _audit._AUDIT_RECORD_TYPES


def _encoded(value, *, semantic=False):
    """Lossless type-tagged tree, also used for explicit repetition projection.

    Every field participates, including compare=False fields. Sets are ordered
    by their lossless encoding. Float operational limits use exact hexadecimal
    representation. The E0 codec and its vocabulary are untouched.
    """
    active, memo = set(), {}

    def visit(item):
        cls = type(item)
        if cls in (Action, CellState, GameStatus, DecisionKind):
            return ("enum", cls.__module__ + "." + cls.__qualname__, item.name)
        if cls is type(None):
            return ("none",)
        if cls is bool:
            return ("bool", item)
        if cls is int:
            return ("int", str(item))
        if cls is str:
            return ("str", item)
        if cls is Fraction:
            return ("fraction", str(item.numerator), str(item.denominator))
        if cls is float:
            _need(isfinite(item), "Nonfinite operational value.")
            return ("float", item.hex())
        key = id(item)
        _need(key not in active, "Cyclic evidence graph.")
        if key in memo:
            return memo[key]
        active.add(key)
        if cls in (tuple, frozenset):
            children = tuple(visit(child) for child in item)
            if cls is frozenset:
                children = tuple(sorted(children, key=_json_bytes))
            result = (cls.__name__, children)
        else:
            _need(cls in _RECORD_TYPES and cls.__dataclass_params__.frozen,
                  "Unsupported mutable/live/hidden evidence type.")
            names = tuple(f.name for f in fields(item))
            _need(not hasattr(item, "__dict__") or set(vars(item)) == set(names),
                  "Unexpected evidence attachment.")
            pairs = []
            for name in names:
                child = getattr(item, name)
                duration = (cls is _evidence.DecisionTimings
                            or cls is Stage3ActionTrace and name == "decision_compute_ns"
                            or cls is _oracles.OracleCallDiagnostic and name == "duration_ns"
                            or cls is _audit.TimingSpan and name == "duration_ns")
                if semantic and duration:
                    projected = ("measurement", "UNMEASURED" if child is None else "MEASURED")
                elif semantic and cls is _harness.GuessCheckpointAudit and name == "archive_digest":
                    projected = ("content_identity", "ABSENT" if child is None else "BOUND")
                else:
                    projected = visit(child)
                pairs.append((name, projected))
            result = ("record", cls.__module__ + "." + cls.__qualname__, tuple(pairs))
        active.remove(key)
        memo[key] = result
        return result

    return visit(value)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("ascii")


def _content_digest(value):
    return hashlib.sha256(_json_bytes(_encoded(value))).hexdigest()


def _validate_pair(plan, archive, audit):
    _need(type(archive) is _execution.E1ScheduledRunArchive
          and type(audit) is _audit.E1RunAudit, "Exact archive AND audit required.")
    # Check the closed graph before any downstream record properties.
    _encoded(archive)
    _encoded(audit)
    try:
        source = _audit._validate_bindings(plan, archive)
        _checked(audit, _audit.E1RunAudit)
        _checked(audit.source_identity, _audit.E1AuditSourceIdentity)
        _need(audit.schedule_entry == archive.schedule_entry and audit.case == archive.case
              and audit.variant == archive.schedule_entry.variant
              and audit.repetition == archive.schedule_entry.repetition,
              "Archive/audit schedule, case, variant or repetition differs.")
        _need(audit.execution_source_digest == audit.source_identity.execution_source_digest
              == source.digest, "Audit/execution source binding differs.")
        p3 = audit.p3_audit
        if p3 is not None:
            _need(p3.case_id == archive.case.case_id and p3.variant == audit.variant
                  and p3.num_mines == archive.case.num_mines, "P-3 audit identity differs.")
            if p3.archive_digest is not None:
                expected = _harness.content_digest(_harness.ExecutionArchive(
                    archive.case.case_id, audit.variant, archive.result))
                _need(p3.archive_digest == expected, "P-3 audit belongs to different archive content.")
    except (ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        raise E1SuiteError("Archive/audit binding refused: " + str(error)) from error
    return source


def _capture_suite_source_identity(plan, archive, audit, root):
    try:
        _checked(plan, _e1.E1Plan)
        _validate_pair(plan, archive, audit)
        current = _audit.capture_audit_source_identity(plan, archive)
        _need(audit.source_identity == current, "Current Slice-3 audit source identity differs.")
        raw = (Path(root) / SUITE_SOURCE_PATH).read_bytes()
        return E1SuiteSourceIdentity(
            current.digest,
            E1SuiteSourceFile(SUITE_SOURCE_PATH, hashlib.sha256(raw).hexdigest(), len(raw)),
            *(getattr(current, name) for name in _AUTHORITIES))
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise E1SuiteError("Suite source capture refused: " + str(error)) from error


def capture_suite_source_identity(plan, archive, audit):
    """Authenticate the current source chain using one explicitly bound pair."""
    return _capture_suite_source_identity(plan, archive, audit, Path(__file__).resolve().parents[1])


def _effects(binding):
    result = binding.archive.result
    return result.effects if binding.schedule_entry.variant == "CONTROL" else tuple(
        t.public_effect for t in result.traces)


def _missing_evidence(binding):
    """Presence checks only; the retained per-run auditor owns public proof."""
    audit, result, variant = binding.audit, binding.archive.result, binding.schedule_entry.variant
    count = len(result.traces)
    missing = list(audit.incomplete_reasons)
    if not count or result.status not in (GameStatus.WON, GameStatus.LOST):
        missing.append("Complete terminal input stream absent.")
    effects = _effects(binding)
    if len(effects) != count or any(e is None for e in effects):
        missing.append("Paired public effects absent.")
    for name in ("cost_audits", "timings"):
        if tuple(item.input_index for item in getattr(audit, name)) != tuple(range(count)):
            missing.append("Incomplete " + name + " input coverage.")
    if audit.public_effect_audit.status != "PASS" and audit.public_effect_audit.status != "FAIL":
        missing.append("Public-effect audit incomplete.")
    if audit.expected_total_us is None or audit.recorded_total_us is None:
        missing.append("Complete-game Model-C audit absent.")
    if variant in ("CONTROL", "K-CONTROL"):
        if tuple(a.input_index for a in audit.v1_audits) != tuple(range(count)):
            missing.append("V1 action audit coverage absent.")
        if any(t.decision is None for t in result.traces[1:]):
            missing.append("Noninitial V1 decision absent.")
    if variant != "CONTROL":
        if tuple(a.input_index for a in audit.replay_audits) != tuple(range(count)):
            missing.append("K replay audit coverage absent.")
        if variant == "K-P0" and any(t.selection is None for t in result.traces[1:]):
            missing.append("Noninitial K-P0 selection absent.")
    if variant in ("CONTROL", "K-P0") and (audit.p3_audit is None or audit.p3_status != "COMPLETE"):
        missing.append("P-3 evidence absent/incomplete.")
    if variant == "K-P0" and (
            audit.mechanism_status != "COMPLETE"
            or tuple(m.input_index for m in audit.mechanism_observations) != tuple(range(count))):
        missing.append("Mechanism observation coverage absent.")
    return tuple(missing)


def _run_findings(binding):
    """Check retained summaries against their retained inputs, without replay.

    Per-run findings remain authoritative even when a caller has manufactured
    a contradictory top-level PASS. These checks do not repeat proof checking.
    """
    audit, result = binding.audit, binding.archive.result
    variant = binding.schedule_entry.variant
    failures, missing = list(audit.discrepancies), list(_missing_evidence(binding))

    def status(value, label, allowed=("PASS",)):
        if value == "FAIL":
            failures.append(label + " failed.")
        elif value not in allowed:
            missing.append(label + " incomplete.")

    status(audit.public_effect_audit.status, "Public-effect audit")
    for name in ("cost_audits", "v1_audits", "acquisition_audits",
                 "oracle_b_audits", "oracle_spans"):
        for record in getattr(audit, name):
            status(record.status, name)
    for record in audit.oracle_a_audits:
        status(record.status, "Oracle A", ("PASS", "NOT_EVALUATED"))
    for record in audit.replay_audits:
        allowed = ("PASS", "NOT_APPLICABLE") if record.input_index == 0 else ("PASS",)
        status(record.decision_status, "K replay decision", allowed)
        status(record.policy_status, "K replay policy",
               ("PASS", "NOT_APPLICABLE") if variant == "K-CONTROL" else allowed)
        for role, state, archived, replayed in (
                ("decision", record.decision_status, record.archived_decision_digest,
                 record.replayed_decision_digest),
                ("selection", record.policy_status, record.archived_selection_digest,
                 record.replayed_selection_digest)):
            if state == "PASS":
                if archived is None or replayed is None:
                    missing.append("Retained K replay " + role + " digests absent.")
                elif archived != replayed:
                    failures.append("Retained K replay " + role + " digests differ.")
        if 0 <= record.input_index < len(result.traces):
            trace = result.traces[record.input_index]
            if variant == "K-CONTROL" and (
                    _encoded(record.shadow) != _encoded(trace.shadow)
                    or _encoded(record.external_antecedents) != _encoded(trace.external_flag_antecedents)):
                failures.append("Retained shadow replay belongs to different archive content.")
            decision = (trace.shadow.decision if variant == "K-CONTROL" else
                        trace.selection.evidence if trace.selection is not None else None)
            if record.archived_decision_digest is not None and (
                    decision is None or record.archived_decision_digest != _harness.content_digest(decision)):
                failures.append("Retained replay decision belongs to different archive content.")
            if variant == "K-P0" and record.archived_selection_digest is not None and (
                    trace.selection is None
                    or record.archived_selection_digest != _harness.content_digest(trace.selection)):
                failures.append("Retained replay selection belongs to different archive content.")
    if variant == "K-CONTROL":
        for record in audit.v1_audits:
            if 0 <= record.input_index < len(result.traces) and (
                    _encoded(record.external_flag) != _encoded(result.traces[record.input_index].external_flag)):
                failures.append("Retained V1 action belongs to different archive content.")
        if result.traces and _encoded(result.shadow) != _encoded(replace(
                result.traces[-1].shadow, decision=None, evidence_valid=False)):
            failures.append("Final shadow checkpoint differs from last archived input.")
    for record in audit.cost_audits:
        if not 0 <= record.input_index < len(result.traces):
            continue
        trace = result.traces[record.input_index]
        effects = _effects(binding)
        effect = effects[record.input_index] if record.input_index < len(effects) else None
        if (record.trace_us != trace.modeled_action_us
                or effect is not None and record.effect_us != effect.modeled_action_us):
            failures.append("Retained Model-C audit belongs to different archive content.")
    if audit.recorded_total_us is not None and audit.recorded_total_us != result.total_modeled_us:
        failures.append("Recorded Model-C total differs from archive.")
    if audit.expected_total_us is not None and audit.expected_total_us != result.total_modeled_us:
        failures.append("Audited Model-C total differs from archive.")
    for record in audit.timings:
        if not 0 <= record.input_index < len(result.traces):
            continue
        raw = (result.timings[record.input_index]
               if variant == "CONTROL" and record.input_index < len(result.timings)
               else None if variant == "CONTROL" else result.traces[record.input_index].timings)
        if _encoded(raw) != _encoded(record.timings):
            failures.append("Retained timing coverage belongs to different archive content.")
        expected_names = tuple(name for name, _ in _audit._TIMING_BOUNDARIES)
        if tuple(s.name for s in record.spans) != expected_names:
            missing.append("Runner timing field coverage absent.")
        for span in record.spans:
            if raw is not None and span.name in expected_names and (
                    span.duration_ns != getattr(raw, span.name)):
                failures.append("Runner timing sample differs from archived span.")
            if span.coverage == "UNMEASURED_REQUIRED":
                missing.append("Required runner timing span unmeasured.")
    if variant in ("CONTROL", "K-P0") and audit.p3_audit is not None:
        if audit.p3_status != audit.p3_audit.status:
            failures.append("P-3 status differs from retained checkpoint evidence.")
    return tuple(failures), tuple(missing)


def _projection(binding):
    audit = binding.audit
    # Schedule index/repetition are pairing metadata, not repeated game state.
    # All other audit fields remain, with only the named duration/content-ID
    # substitutions in _encoded. No generic suffix-based semantic exclusions.
    audit_fields = tuple((f.name, _encoded(getattr(audit, f.name), semantic=True))
                         for f in fields(audit) if f.name not in ("schedule_entry", "repetition"))
    _, missing = _run_findings(binding)
    return SemanticRepetitionProjection(binding.case.case_id, binding.schedule_entry.variant,
                                        _encoded(binding.archive.result, semantic=True),
                                        audit_fields, missing)


def _repetition(first, second):
    left, right = _projection(first), _projection(second)
    if left.missing_evidence or right.missing_evidence:
        # Absence is not a reproduced semantic disagreement. Still diagnose a
        # disagreement in the complete physical stream independently of audits.
        a, b = first.archive.result, second.archive.result
        physical_a = (a.status, tuple((t.move, t.cursor_before, t.modeled_action_us, t.status_after)
                                     for t in a.traces))
        physical_b = (b.status, tuple((t.move, t.cursor_before, t.modeled_action_us, t.status_after)
                                     for t in b.traces))
        complete = bool(a.traces and b.traces) and all(
            r.status in (GameStatus.WON, GameStatus.LOST) for r in (a, b))
        status = ("FAIL" if complete and _encoded(physical_a) != _encoded(physical_b)
                  else "INCOMPLETE")
    else:
        status = "PASS" if left == right else "FAIL"
    return RepetitionDeterminism(first.case.case_id, first.schedule_entry.variant,
                                 left, right, status)


def _physical(binding):
    result = binding.archive.result
    costs = tuple(t.modeled_action_us for t in result.traces)
    _need(all(type(c) is int and c >= 0 for c in costs), "Invalid physical cost evidence.")
    cumulative, total = [], 0
    for cost in costs:
        total += cost
        cumulative.append(total)
    guesses = tuple((i, t.move) for i, t in enumerate(result.traces)
                    if t.decision is not None
                    and t.decision.evidence.kind is DecisionKind.PROBABILITY_GUESS)
    return PhysicalStreamProjection(tuple(t.move for t in result.traces),
                                    tuple(t.cursor_before for t in result.traces), costs,
                                    tuple(cumulative), total, result.status,
                                    tuple(t.status_after for t in result.traces), guesses)


def _control_identity(control, shadow):
    left, right = _physical(control), _physical(shadow)
    differences = [f.name + " differs" for f in fields(left)
                   if _encoded(getattr(left, f.name)) != _encoded(getattr(right, f.name))]
    a, b = control.archive.result, shadow.archive.result
    if len(a.traces) != len(b.traces):
        differences.append("Trace count differs.")
    ea, eb = _effects(control), _effects(shadow)
    effects = tuple(_evidence.compare_public_effects(
        ea[i] if i < len(ea) else None, eb[i] if i < len(eb) else None, boundary=i)
        for i in range(max(len(ea), len(eb))))
    decisions = tuple(_evidence.compare_v1_decisions(x.decision, y.decision, boundary=i)
                      for i, (x, y) in enumerate(zip(a.traces, b.traces)) if i)
    missing = []
    for label, comparisons in (("Public effect", effects), ("O-4", decisions)):
        for comparison in comparisons:
            if comparison.status == "FAIL":
                differences.append(label + " differs at input " + str(comparison.boundary))
            elif comparison.status != "PASS":
                missing.append(label + " incomplete at input " + str(comparison.boundary))
    for i, trace in enumerate(b.traces):
        checkpoint = trace.shadow
        if not checkpoint.v1_continues:
            differences.append("Shadow did not preserve V1 physical authority at input " + str(i))
        if trace.soundness is not None and trace.soundness.classification == "SHADOW_SOUNDNESS_VIOLATION":
            differences.append("SHADOW_SOUNDNESS_VIOLATION at input " + str(i))
        if i and (trace.soundness is None or trace.soundness.classification == "NOT_EVALUATED"):
            missing.append("Shadow soundness comparison absent at input " + str(i))
        failure = checkpoint.failure
        if failure is not None:
            if failure.failure_class == "SHADOW_TIMEOUT":
                missing.append("Shadow timeout at input " + str(i))
            else:
                differences.append(failure.failure_class + " at input " + str(i))
        elif i and (not checkpoint.enabled or not checkpoint.evidence_valid
                    or checkpoint.decision is None):
            missing.append("Shadow evidence invalidated/absent at input " + str(i))
    final = b.shadow
    if not final.v1_continues:
        differences.append("Final shadow did not preserve V1 authority.")
    if final.failure is not None:
        if final.failure.failure_class == "SHADOW_TIMEOUT":
            missing.append("Final shadow stream invalidated by timeout.")
        else:
            differences.append(final.failure.failure_class + " in final shadow stream.")
    return ControlIdentityPair(control.case.case_id, control.schedule_entry.repetition,
                               left, right, effects, decisions, tuple(differences), tuple(missing),
                               "FAIL" if differences else "INCOMPLETE" if missing else "PASS")


def _outcome(control, kp0):
    return "".join("W" if status is GameStatus.WON else "L"
                   if status is GameStatus.LOST else "?" for status in (control, kp0))


def _p3_pair(control, kp0):
    comparison = _harness.compare_guess_checkpoints(control.audit.p3_audit, kp0.audit.p3_audit)
    _need(type(comparison) is _harness.GuessComparison, "Malformed P-3 comparator result.")
    a, b = control.archive.result.status, kp0.archive.result.status
    outcome = _outcome(a, b)
    status = ("FAIL" if comparison.status == "FAIL" or outcome in ("WL", "LW")
              else "INCOMPLETE" if comparison.status != "PASS" or "?" in outcome else "PASS")
    return P3OutcomePair(control.case.case_id, control.schedule_entry.repetition,
                         comparison, a, b, outcome, status)


def _mechanism_coverage(bindings, repetitions):
    progressions, invalid, abandoned, nonproductive = [], [], [], []
    for bound in bindings:
        if bound.schedule_entry.variant != "K-P0":
            continue
        audit, traces = bound.audit, bound.archive.result.traces
        run_failures, run_missing = _run_findings(bound)
        evidence_pass = (audit.audit_status == "PASS" and not run_failures and not run_missing)
        observations = audit.mechanism_observations
        label = bound.case.case_id + "/" + str(bound.schedule_entry.repetition)
        indices = tuple(o.input_index for o in observations)
        if any(type(i) is not int for i in indices) or indices != tuple(sorted(set(indices))):
            invalid.append(label + ": duplicate, malformed or unordered mechanism indices.")
            continue
        by_index = {o.input_index: o for o in observations}
        used, invalid_inputs = set(), set()
        setups = [o for o in observations if o.kind == "SETUP_CHORD_FLAG"]
        for o in observations:
            errors = []
            if not 0 <= o.input_index < len(traces):
                invalid.append(label + ": mechanism index outside physical stream.")
                invalid_inputs.add(o.input_index)
                continue
            coordinate = lambda c: (type(c) is tuple and len(c) == 2
                                    and all(type(v) is int for v in c)
                                    and 0 <= c[0] < bound.case.width and 0 <= c[1] < bound.case.height)
            if (type(o.action) is not Action or not coordinate(o.target)
                    or any(type(cells) is not frozenset or not all(coordinate(c) for c in cells)
                           for cells in (o.setup_cells, o.reveal_cells, o.relevant_physical_flags))
                    or type(o.prior_setup_input_indices) is not tuple
                    or type(o.safe_cells_opened_delta) is not int or o.safe_cells_opened_delta < 0
                    or o.planned_terminal_reveal_action is not None
                    and type(o.planned_terminal_reveal_action) is not SimpleMove):
                invalid.append(label + ": malformed mechanism observation fields.")
                invalid_inputs.add(o.input_index)
                continue
            trace = traces[o.input_index]
            effect = trace.public_effect
            if (o.action != trace.move.action or o.target != (trace.move.x, trace.move.y)
                    or o.modeled_action_us != trace.modeled_action_us
                    or o.selected_category != trace.category or effect is None
                    or o.safe_cells_opened_delta != effect.safe_cells_opened_delta):
                errors.append("observation differs from archived physical input")
            if o.kind == "SETUP_CHORD_FLAG":
                if (o.action is not Action.FLAG or o.selected_category != "SETUP_CHORD"
                        or o.target not in o.setup_cells or o.planned_terminal_reveal_action is None
                        or o.planned_terminal_reveal_action.action is not Action.CHORD):
                    errors.append("setup lacks actual FLAG/current CHORD plan")
                if effect is not None and (
                        effect.before_observation[o.target[1]][o.target[0]] != CellState.HIDDEN
                        or effect.after_observation.rows[o.target[1]][o.target[0]] != CellState.FLAGGED):
                    errors.append("setup FLAG was not physically materialized")
            elif o.kind == "CHORD_AFTER_PRIOR_SETUP":
                prior = o.prior_setup_input_indices
                if (o.action is not Action.CHORD or not prior
                        or o.planned_terminal_reveal_action != trace.move
                        or any(type(i) is not int for i in prior)
                        or prior != tuple(sorted(set(prior)))
                        or any(i >= o.input_index or i not in by_index for i in prior)):
                    errors.append("invalid prior setup indices")
                else:
                    targets = []
                    for index in prior:
                        setup = by_index[index]
                        planned = setup.planned_terminal_reveal_action
                        if (index in invalid_inputs or setup.kind != "SETUP_CHORD_FLAG"
                                or setup.action is not Action.FLAG
                                or planned is None or planned.action is not Action.CHORD
                                or (planned.x, planned.y) != o.target
                                or setup.target not in o.relevant_physical_flags):
                            errors.append("prior index does not bind a relevant setup FLAG")
                        if any(t.status_after is not GameStatus.PLAYING
                               for t in traces[index:o.input_index]):
                            errors.append("terminal boundary between setup and CHORD")
                        targets.append(setup.target)
                    if effect is not None:
                        rows = effect.before_observation
                        physical_flags = frozenset((x, y) for y, row in enumerate(rows)
                                                   for x, v in enumerate(row) if v == CellState.FLAGGED)
                        adjacent_flags = frozenset(c for c in physical_flags
                                                   if max(abs(c[0] - o.target[0]),
                                                          abs(c[1] - o.target[1])) == 1)
                        if o.relevant_physical_flags != adjacent_flags:
                            errors.append("claimed setup flags absent from public physical state")
                    if not errors:
                        if o.safe_cells_opened_delta > 0:
                            if evidence_pass and audit.mechanism_status == "COMPLETE":
                                progressions.append(ProductiveProgression(
                                    bound.case.case_id, bound.schedule_entry.repetition, prior,
                                    tuple(targets), o.input_index, o.target, o.safe_cells_opened_delta))
                                used.update(prior)
                        else:
                            nonproductive.append((bound.case.case_id, bound.schedule_entry.repetition,
                                                  o.input_index))
            elif o.kind == "DIRECT_CHORD":
                if o.action is not Action.CHORD or o.prior_setup_input_indices:
                    errors.append("direct CHORD carries inconsistent setup claim")
            elif o.kind != "OTHER":
                errors.append("unknown mechanism kind")
            if o.action is Action.CHORD and o.kind not in ("DIRECT_CHORD", "CHORD_AFTER_PRIOR_SETUP"):
                errors.append("actual CHORD lacks mechanism classification")
            if errors:
                invalid_inputs.add(o.input_index)
            invalid.extend(label + "/" + str(o.input_index) + ": " + error for error in errors)
        abandoned.extend((bound.case.case_id, bound.schedule_entry.repetition, o.input_index,
                          o.target, o.modeled_action_us) for o in setups if o.input_index not in used)
    observed = tuple(case for case in _e1.CASE_IDS
                     if all(any(p.case_id == case and p.repetition == rep for p in progressions)
                            for rep in _e1.REPETITIONS)
                     and any(r.case_id == case and r.variant == "K-P0" and r.status == "PASS"
                             for r in repetitions))
    return MechanismCoverage("INVALID" if invalid else "OBSERVED" if observed else "MISSING",
                             tuple(progressions), observed, tuple(invalid),
                             tuple(abandoned), tuple(nonproductive))


def _model_c(groups):
    games = []
    for control, shadow, kp0 in groups:
        a, b, c = control.archive.result, shadow.archive.result, kp0.archive.result
        outcome = _outcome(a.status, c.status)
        games.append(GameModelCDiagnostic(
            control.case.case_id, control.schedule_entry.repetition,
            a.status, a.total_modeled_us, b.status, b.total_modeled_us,
            c.status, c.total_modeled_us, outcome,
            c.total_modeled_us - a.total_modeled_us if outcome == "WW" else None))
    wins = tuple(g for g in games if g.outcome == "WW")
    return ModelCDiagnostics(
        tuple(games), *(sum(g.outcome == pair for g in games) for pair in ("WW", "WL", "LW", "LL")),
        sum(g.control_outcome is GameStatus.WON for g in games),
        sum(g.control_outcome is GameStatus.LOST for g in games),
        sum(g.kp0_outcome is GameStatus.WON for g in games),
        sum(g.kp0_outcome is GameStatus.LOST for g in games),
        sum(g.control_us for g in wins), sum(g.kp0_us for g in wins),
        sum(g.delta_us for g in wins), sum(g.delta_us < 0 for g in wins),
        sum(g.delta_us > 0 for g in wins), sum(g.delta_us == 0 for g in wins),
        tuple((g.case_id, g.repetition, g.delta_us) for g in wins))


def _diagnostics(bindings, mechanism):
    counts, runner_timings, oracle_timings = [], [], []
    for variant in _e1.VARIANTS:
        runs = tuple(b for b in bindings if b.schedule_entry.variant == variant)
        audits = tuple(b.audit for b in runs)
        mechanisms = tuple(m for a in audits for m in a.mechanism_observations)
        counts.append(VariantDiagnosticCounts(
            variant, len(runs), sum(len(a.cost_audits) for a in audits),
            sum(len(a.acquisition_audits) for a in audits),
            sum(o.coverage is not None and o.coverage.status == "ORACLE_A_EVALUATED"
                for a in audits for o in a.oracle_a_audits),
            sum(o.coverage is not None and o.coverage.status == "ORACLE_A_NOT_EVALUATED"
                for a in audits for o in a.oracle_a_audits),
            sum(o.phase == "D" for a in audits for o in a.oracle_b_audits),
            sum(o.phase == "E" for a in audits for o in a.oracle_b_audits),
            sum(len(a.oracle_calls) for a in audits),
            sum(len(a.p3_audit.checkpoints) if a.p3_audit is not None else 0 for a in audits),
            sum(m.kind == "SETUP_CHORD_FLAG" for m in mechanisms),
            sum(m.action is Action.CHORD for m in mechanisms),
            len(mechanism.progressions) if variant == "K-P0" else 0,
            sum(len(a.discrepancies) for a in audits), sum(len(a.incomplete_reasons) for a in audits),
            sum(a.audit_status == "FAIL" for a in audits), sum(a.audit_status == "INCOMPLETE" for a in audits)))
        for name, boundary in _audit._TIMING_BOUNDARIES:
            samples = []
            absent = 0
            for bound in runs:
                for i in range(len(bound.archive.result.traces)):
                    coverage = tuple(t for t in bound.audit.timings if t.input_index == i)
                    spans = tuple(s for t in coverage for s in t.spans if s.name == name)
                    if len(spans) != 1:
                        absent += 1
                        continue
                    span = spans[0]
                    samples.append((bound.case.case_id, bound.schedule_entry.repetition,
                                    i, span.duration_ns, span.coverage, span.boundary))
            measured = tuple(s[3] for s in samples if type(s[3]) is int)
            runner_timings.append(RunnerTimingSamples(
                variant, name, boundary, len(measured), measured,
                sum(s[4] == "NOT_APPLICABLE" for s in samples),
                sum(s[4] == "UNMEASURED" for s in samples),
                sum(s[4] == "UNMEASURED_REQUIRED" for s in samples), absent, tuple(samples)))
        for oracle, method in (("A", "COMPLETE_WORLD_ENUMERATION"),
                               ("B", "MATERIALIZED_EXACT"), ("B", "MATERIALIZED_LOCAL")):
            samples = tuple((b.case.case_id, b.schedule_entry.repetition, call)
                            for b in runs for call in b.audit.oracle_calls
                            if (call.oracle, call.method) == (oracle, method))
            measured = tuple(s[2].duration_ns for s in samples)
            oracle_timings.append(OracleTimingSamples(variant, oracle, method,
                                                      len(measured), measured, samples))
    return SuiteDiagnostics(tuple(counts), tuple(runner_timings), tuple(oracle_timings))


def aggregate_e1_suite(plan, archives, audits):
    """Aggregate exactly the fixed schedule, without obtaining any new run evidence."""
    _checked(plan, _e1.E1Plan)
    _need(type(archives) is tuple and type(audits) is tuple
          and len(archives) == len(audits) == 54, "Exactly 54 immutable archives AND audits required.")
    for entry, archive, audit in zip(plan.schedule, archives, audits):
        _need(type(archive) is _execution.E1ScheduledRunArchive and type(audit) is _audit.E1RunAudit,
              "Exact scheduled archive/audit types required.")
        _need(archive.schedule_entry == audit.schedule_entry == entry,
              "Archives/audits must follow the exact 54-entry schedule order.")
    source = capture_suite_source_identity(plan, archives[0], audits[0])
    execution_source, audit_source = archives[0].execution_source_identity, audits[0].source_identity
    bindings = []
    for archive, audit in zip(archives, audits):
        actual = _validate_pair(plan, archive, audit)
        _need(actual == execution_source and audit.source_identity == audit_source,
              "Mixed execution/audit source identities.")
        bindings.append(AuditedScheduledRun(
            archive.schedule_entry, archive.case, archive, _content_digest(archive),
            audit, _content_digest(audit), actual.digest, audit.source_identity.digest))
    bindings = tuple(bindings)
    lookup = {(b.case.case_id, b.schedule_entry.repetition, b.schedule_entry.variant): b for b in bindings}
    repetitions = tuple(_repetition(lookup[case, 1, variant], lookup[case, 2, variant])
                        for case in _e1.CASE_IDS for variant in _e1.VARIANTS)
    groups = tuple(tuple(lookup[case, rep, variant] for variant in _e1.VARIANTS)
                   for case in _e1.CASE_IDS for rep in _e1.REPETITIONS)
    identity_pairs = tuple(_control_identity(c, k) for c, k, _ in groups)
    p3_pairs = tuple(_p3_pair(c, p) for c, _, p in groups)
    mechanism = _mechanism_coverage(bindings, repetitions)
    failures, missing = [], []
    for bound in bindings:
        label = str(bound.schedule_entry.schedule_index) + ": "
        run_failures, run_missing = _run_findings(bound)
        failures.extend(label + reason for reason in run_failures)
        missing.extend(label + reason for reason in run_missing)
    for label, records in (("Repetition", repetitions), ("CONTROL/K-CONTROL", identity_pairs),
                           ("CONTROL/K-P0 P-3/outcome", p3_pairs)):
        for record in records:
            detail = label + " " + record.case_id + "/" + (
                record.variant if type(record) is RepetitionDeterminism else str(record.repetition))
            if record.status == "FAIL":
                failures.append(detail)
            elif record.status != "PASS":
                missing.append(detail)
    if mechanism.status == "INVALID":
        failures.extend(mechanism.invalid_reasons)
    elif mechanism.status == "MISSING":
        missing.append("Deterministic productive K-P0 setup FLAG to CHORD coverage missing; prospective A-E5 required.")
    status = "FAIL" if failures else "INCOMPLETE" if missing else "PASS"
    supplement = {"OBSERVED": "NOT_REQUIRED", "MISSING": "REQUIRED_PROSPECTIVE_A_E5",
                  "INVALID": "NOT_APPLICABLE_ON_FAILURE"}[mechanism.status]
    aggregate = E1SuiteAggregate(
        source, plan.source_identity.digest, plan, bindings,
        ScheduleCoverage(54, len(archives), len(audits),
                         tuple((e.case_id, e.repetition, e.variant, e.schedule_index) for e in plan.schedule), "PASS"),
        repetitions, identity_pairs, p3_pairs, mechanism, _model_c(groups),
        _diagnostics(bindings, mechanism), tuple(failures), tuple(missing), status, supplement)
    _need(capture_suite_source_identity(plan, archives[0], audits[0]) == source,
          "Source changed during suite aggregation.")
    return aggregate
