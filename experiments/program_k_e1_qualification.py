"""Final fixed E1 implementation qualification, without effectiveness authority.

Import, preflight and historical reconstruction never execute a game or an
evaluator. Only execute_e1 dispatches work, after separate explicit authorization.
Publication is a separate API in program_k_e1_persistence.
"""

import builtins
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from math import isfinite
from pathlib import Path
import re
import time
from types import FunctionType, SimpleNamespace

from core_engine import Action, CellState, GameStatus
from simple_decision import DecisionKind
from experiments import program_k_e1_harness as _e1
from experiments import program_k_e1_execution as _execution
from experiments import program_k_e1_audit as _audit
from experiments import program_k_e1_suite as _suite
from experiments import program_k_e1_evaluator as _evaluator
from experiments import program_k_e1_operational as _operational
from experiments import program_k_evaluator as _findings
from experiments import program_k_harness as _harness


QUALIFICATION_SOURCE_PATHS = (
    "experiments/program_k_e1_qualification.py",
    "experiments/program_k_e1_persistence.py",
)
# Recomputed from the clean committed post-Slice-5 baseline, not prompt text.
ACCEPTED_OPERATIONAL_SOURCE_DIGEST = "e60d340b78b08dcfa26f736e93138b68c0d12dc967690fd0de7db3b4c11ac97e"
_AUTHORITIES = _execution._AUTHORITY_FIELDS
_ERRORS = (OSError, ValueError, TypeError, AttributeError, IndexError, KeyError)
# Fixed reconciliation bodies, distinct from the live orchestration entrypoints.
_AGGREGATE_BODY = _suite.aggregate_e1_suite
_RESOURCE_BODY = _operational.summarize_operational_resources


class E1QualificationError(ValueError):
    """An invalid identity, scope or immutable evidence graph fails closed."""


class E1ReconstructionError(E1QualificationError):
    """The retained prefix cannot supply a complete suite/resource structure."""


def _need(condition, detail):
    if not condition:
        raise E1QualificationError(detail)


def _checked(value, cls):
    _need(type(value) is cls, "Expected exact " + cls.__name__ + ".")
    return replace(value)


def _sha(value):
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
          "Invalid SHA-256 identity.")


def validate_run_id(run_id):
    _need(type(run_id) is str
          and re.fullmatch(r"e1-[A-Za-z0-9][A-Za-z0-9_-]{0,75}", run_id) is not None,
          "E1 run id must be a safe e1- prefixed local artifact name.")
    return run_id


def evaluation_run_id(run_id, schedule_index):
    validate_run_id(run_id)
    _need(type(schedule_index) is int and schedule_index in range(2, 54, 3),
          "Evaluator identity requires a fixed K-P0 schedule index.")
    return f"{run_id}-kp0-{schedule_index:02d}"


@dataclass(frozen=True, slots=True)
class E1QualificationSourceFile:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(type(self.path) is str and self.path in QUALIFICATION_SOURCE_PATHS,
              "Unregistered final qualification source.")
        _sha(self.sha256)
        _need(type(self.size_bytes) is int and self.size_bytes > 0, "Invalid source size.")


@dataclass(frozen=True, slots=True)
class E1QualificationSourceIdentity:
    operational_source_identity: _operational.E1OperationalSourceIdentity
    files: tuple[E1QualificationSourceFile, ...]
    spec_sha256: str
    protocol_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        source = _checked(self.operational_source_identity,
                          _operational.E1OperationalSourceIdentity)
        _need(source.digest == ACCEPTED_OPERATIONAL_SOURCE_DIGEST,
              "Accepted Slice-5 operational source identity drifted.")
        _need(type(self.files) is tuple and len(self.files) == 2
              and all(type(f) is E1QualificationSourceFile for f in self.files)
              and tuple(f.path for f in self.files) == QUALIFICATION_SOURCE_PATHS,
              "Exact ordered qualification/persistence source files required.")
        for item in self.files:
            _checked(item, E1QualificationSourceFile)
        _e1._frozen_identities(self)
        _need(all(getattr(source, name) == getattr(self, name) for name in _AUTHORITIES),
              "Final frozen authority chain differs.")

    @property
    def digest(self):
        _checked(self, E1QualificationSourceIdentity)
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
        return hashlib.sha256(raw).hexdigest()


def _capture_qualification_source_identity(plan, root):
    """Prospective exact-byte capture; no archive, board or execution required."""
    try:
        source = _operational.capture_operational_source_identity(plan)
        identities = []
        for path in QUALIFICATION_SOURCE_PATHS:
            raw = (Path(root) / path).read_bytes()
            identities.append(E1QualificationSourceFile(
                path, hashlib.sha256(raw).hexdigest(), len(raw)))
        return E1QualificationSourceIdentity(
            source, tuple(identities), *(getattr(source, name) for name in _AUTHORITIES))
    except _ERRORS as error:
        raise E1QualificationError("Final source capture refused: " + str(error)) from error


def capture_qualification_source_identity(plan):
    return _capture_qualification_source_identity(plan, Path(__file__).resolve().parents[1])


@dataclass(frozen=True, slots=True)
class E1Preflight:
    status: str
    reasons: tuple[str, ...]

    def __post_init__(self):
        _texts(self.reasons)
        _need(type(self.status) is str
              and self.status == ("NOT_READY" if self.reasons else "READY"),
              "Preflight status differs from its reasons.")


def preflight_e1(plan, envelope, source_identity, *, run_id,
                 authorization_reference, repository_root=None):
    """Read-only admission of this runtime and the accepted actual E0/P-8."""
    reasons = []
    checks = (
        ("RUN_ID", lambda: validate_run_id(run_id)),
        ("AUTHORIZATION", lambda: _authorization(authorization_reference)),
        ("PLAN", lambda: _checked(plan, _e1.E1Plan)),
        ("ENVELOPE", lambda: _operational.require_operating_envelope(envelope)),
        ("SOURCE", lambda: _checked(source_identity, E1QualificationSourceIdentity)),
    )
    for label, check in checks:
        try:
            check()
        except _ERRORS as error:
            reasons.append(label + ": " + str(error))
    if not reasons:
        try:
            _need(plan.runtime == _e1.capture_runtime_identity(), "Plan runtime is not current.")
            _need(source_identity == capture_qualification_source_identity(plan),
                  "Final source identity is not current.")
            _need(source_identity.operational_source_identity.plan_source_identity
                  == plan.source_identity, "Plan source binding differs.")
            _need(_e1.load_accepted_e0_prerequisite() == plan.prerequisite,
                  "Accepted E0/P-8 prerequisite differs.")
        except _ERRORS as error:
            reasons.append("CURRENT_PREREQUISITES: " + str(error))
    if repository_root is not None:
        try:
            validate_run_id(run_id)
            destination = Path(repository_root) / "results" / "program_k_research" / run_id
            _need(not destination.exists() and not destination.is_symlink(),
                  "Artifact destination already exists.")
        except _ERRORS as error:
            reasons.append("DESTINATION: " + str(error))
    return E1Preflight("NOT_READY" if reasons else "READY", tuple(reasons))


def _authorization(value):
    _need(type(value) is str and bool(value.strip()),
          "A separate nonblank execution authorization reference is mandatory.")


def _texts(value):
    _need(type(value) is tuple and all(type(v) is str and bool(v.strip()) for v in value),
          "Explicit immutable text reasons required.")


def _historical_envelope(envelope):
    value = _harness.require_envelope(envelope)
    _need(value.monitoring_policy == _operational.MONITORING_POLICY,
          "Historical envelope has another monitoring policy.")
    return value


def _bound_function(function, **bindings):
    """Reuse an exact existing function body with private admission bindings.

    Slices 4/5 couple deterministic reconciliation to live-source admission.
    Historical evidence needs their same checks against its retained identities.
    This creates no module mutation, global monkeypatch, executable artifact code
    or concurrent bypass of live execution admission.
    """
    namespace = dict(function.__globals__)
    namespace.update(bindings)
    bound = FunctionType(function.__code__, namespace, function.__name__,
                         function.__defaults__, function.__closure__)
    bound.__kwdefaults__ = function.__kwdefaults__
    return bound


def _historical_checked(value, cls):
    """Revalidate the two runtime-bound records without reading today's runtime."""
    _need(type(value) is cls, "Expected exact " + cls.__name__ + ".")
    if cls not in (_operational.E1OperationReceipt, _operational.E1OperationResult):
        return replace(value)
    result = object.__new__(cls)
    for field in fields(cls):
        object.__setattr__(result, field.name, getattr(value, field.name))
    validator = _bound_function(
        cls.__post_init__, require_operating_envelope=_historical_envelope,
        _checked=_historical_checked)
    validator(result)
    return result


def _require_graph(value):
    """Closed detached graph, including every compare=False field."""
    active, checked = set(), set()

    def visit(item):
        cls = type(item)
        if cls in (str, int, bool, type(None), Fraction, Action, CellState,
                   GameStatus, DecisionKind):
            return
        if cls is float:
            _need(isfinite(item), "Nonfinite evidence value.")
            return
        key = id(item)
        _need(key not in active, "Cyclic evidence graph.")
        if key in checked:
            return
        active.add(key)
        if cls in (tuple, frozenset):
            children = item
        else:
            _need(cls in _RECORD_TYPES and cls.__dataclass_params__.frozen,
                  "Unsupported mutable/live/hidden evidence type.")
            names = tuple(f.name for f in fields(item))
            _need(not hasattr(item, "__dict__") or set(vars(item)) == set(names),
                  "Unexpected record attachment.")
            children = tuple(getattr(item, name) for name in names)
        for child in children:
            visit(child)
        active.remove(key)
        checked.add(key)
    visit(value)


def _utc(value):
    _need(type(value) is str and re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value) is not None,
        "An explicit UTC timestamp ending Z is required.")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise E1QualificationError("Invalid UTC timestamp.") from error


def _operation_stop(result):
    """Only observed hard stops; no diagnosis is inferred from a game loss."""
    if result.receipt.status == "INCOMPLETE":
        return "OPERATION_INCOMPLETE"
    if any(e.event in ("WORKER_ABORT", "SYSTEM_DECISION_TIMEOUT") for e in result.receipt.events):
        return "CONTRADICTORY_COMPLETE_ABORT"
    if result.receipt.operation_kind == "SCHEDULED_RUN":
        if result.archive is None or result.audit is None:
            return "COMPLETE_SCHEDULED_PAYLOAD_MISSING"
        if result.audit.audit_status != "PASS":
            return "PUBLIC_AUDIT_" + result.audit.audit_status
    else:
        if result.evaluation is None:
            return "COMPLETE_EVALUATOR_FINDING_MISSING"
        if result.evaluation.classification == "G1_FALSIFICATION":
            return "G1_FALSIFICATION"
    return None


@dataclass(frozen=True, slots=True)
class E1QualificationRecord:
    run_id: str
    purpose: str
    authorization_reference: str
    source_identity: E1QualificationSourceIdentity
    plan: _e1.E1Plan
    operating_envelope: _harness.OperatingEnvelope
    started_utc: str
    ended_utc: str
    elapsed_ns: int
    scheduled_results: tuple[_operational.E1OperationResult, ...]
    evaluator_results: tuple[_operational.E1OperationResult, ...]
    interruptions: tuple[str, ...] = ()
    diagnosed_implementation_defects: tuple[str, ...] = ()

    def __post_init__(self):
        _require_graph(self)
        validate_run_id(self.run_id)
        _authorization(self.authorization_reference)
        _need(type(self.purpose) is str and self.purpose == "E1_QUALIFICATION",
              "Only E1 implementation qualification is in scope.")
        source = _checked(self.source_identity, E1QualificationSourceIdentity)
        plan = _checked(self.plan, _e1.E1Plan)
        envelope = _historical_envelope(self.operating_envelope)
        _need(source.operational_source_identity.plan_source_identity == plan.source_identity,
              "Record plan/source chain differs.")
        _need((envelope.runtime_identity, envelope.machine_identity, envelope.python_identity)
              == (plan.runtime.platform, plan.runtime.node, plan.runtime.python_version),
              "Recorded runtime and operating envelope differ.")
        _need(_utc(self.ended_utc) >= _utc(self.started_utc), "UTC end precedes start.")
        _need(type(self.elapsed_ns) is int and self.elapsed_ns >= 0,
              "Elapsed time must be nonnegative integer nanoseconds.")
        _texts(self.interruptions)
        _texts(self.diagnosed_implementation_defects)
        _validate_operations(self)


def _validate_operations(record):
    source = record.source_identity.operational_source_identity
    scheduled, evaluations = record.scheduled_results, record.evaluator_results
    _need(type(scheduled) is tuple and len(scheduled) <= 54
          and type(evaluations) is tuple and len(evaluations) <= 18,
          "Operation results require bounded immutable prefixes.")
    _need(not evaluations or len(scheduled) == 54,
          "Evaluator evidence cannot precede all 54 scheduled results.")
    used, stopped = 0, False
    envelope_digest = _harness.content_digest(record.operating_envelope)
    for kind, results, indices in (
        ("SCHEDULED_RUN", scheduled, range(54)),
        ("POST_HOC_EVALUATOR", evaluations, range(2, 54, 3)),
    ):
        for result, index in zip(results, indices):
            _need(not stopped, "A result follows a prior orchestration hard stop.")
            _historical_checked(result, _operational.E1OperationResult)
            receipt = result.receipt
            lifecycle = tuple(event.event for event in receipt.events)
            _need(lifecycle.count("JOB_ATTACHED") <= 1 and lifecycle.count("STARTED") <= 1
                  and lifecycle.count("RESULT_STARTED") <= 1 and lifecycle.count("FINISHED") <= 1
                  and ("FINISHED" not in lifecycle or lifecycle[-1] == "FINISHED"),
                  "Duplicate lifecycle boundary or event after FINISHED.")
            _need((receipt.operation_kind, receipt.schedule_index) == (kind, index),
                  "Skipped, duplicated, reordered or substituted operation.")
            _need(receipt.operational_source_digest == source.digest
                  and receipt.envelope_digest == envelope_digest
                  and receipt.envelope == record.operating_envelope,
                  "Receipt source/envelope differs from the record.")
            _need(receipt.archive_used_before_bytes == used,
                  "Archive budget chain has a gap, overlap or nonzero origin.")
            used = receipt.archive_used_after_bytes
            if kind == "SCHEDULED_RUN":
                _need(result.evaluation is None, "Scheduled operation contains evaluator data.")
                if result.archive is not None:
                    archive, audit = result.archive, result.audit
                    _suite._validate_pair(record.plan, archive, audit)
                    _need(archive.schedule_entry == record.plan.schedule[index]
                          and archive.execution_source_identity == source.execution_source_identity
                          and audit.source_identity == source.audit_source_identity
                          and archive.shadow_timeout_s
                          == record.operating_envelope.shadow_timeout_ms / 1000,
                          "Scheduled source/schedule/timeout binding differs.")
                    _need(receipt.physical_inputs == len(archive.result.traces),
                          "Receipt physical count differs from retained archive.")
            else:
                _need(result.archive is None and result.audit is None,
                      "Evaluator operation contains scheduled data.")
                run_id = evaluation_run_id(record.run_id, index)
                _need(receipt.operation_id == f"POST_HOC_EVALUATOR:{index:02d}:{run_id}",
                      "Evaluator operation id is not derived from the qualification run.")
                if result.evaluation is not None:
                    finding = result.evaluation
                    _need(finding.schedule_index == index and finding.evaluation_run_id == run_id
                          and (finding.evaluator_source_sha256, finding.evaluator_source_size_bytes)
                          == (source.evaluator_file.sha256, source.evaluator_file.size_bytes),
                          "Evaluator finding source/run/schedule differs.")
            if result.archive is not None or result.evaluation is not None:
                payload = _operational._payload_bytes(
                    (result.archive, result.audit, result.evaluation))
                _need(receipt.result_digest == hashlib.sha256(payload).hexdigest()
                      and receipt.result_size_bytes == len(payload),
                      "Retained payload differs from receipt digest/size.")
            stopped = _operation_stop(result) is not None
    if evaluations:
        aggregate = _reconstruct_suite(record)
        _need(aggregate.suite_status != "FAIL", "Evaluator result follows suite failure.")
        verify = _historical_finding_verifier(source)
        digest = _suite._content_digest(aggregate)
        for result in evaluations:
            if result.evaluation is not None:
                index = result.receipt.schedule_index
                verify(record.plan, aggregate, aggregate.bindings[index], result.evaluation,
                       evaluation_run_id(record.run_id, index), suite_content_digest=digest)


def _historical_aggregate(plan, archives, audits, source):
    def retained_identity(supplied_plan, archive, audit):
        _need(supplied_plan == plan, "Historical aggregate plan substitution.")
        _suite._validate_pair(plan, archive, audit)
        _need(archive.execution_source_identity == source.execution_source_identity
              and audit.source_identity == source.audit_source_identity,
              "Historical archive/audit source chain differs.")
        return source.suite_source_identity
    aggregate = _bound_function(
        _AGGREGATE_BODY, capture_suite_source_identity=retained_identity)
    return aggregate(plan, archives, audits)


def _reconstruct_suite(record):
    results = record.scheduled_results
    if len(results) != 54 or any(r.archive is None or r.audit is None for r in results):
        raise E1ReconstructionError("The complete 54 archive/audit family is unavailable.")
    return _historical_aggregate(
        record.plan, tuple(r.archive for r in results), tuple(r.audit for r in results),
        record.source_identity.operational_source_identity)


def reconstruct_e1_suite(record):
    """Reconcile retained evidence only; never audit, plan or execute a run."""
    _checked(record, E1QualificationRecord)
    return _reconstruct_suite(record)


def _historical_finding_verifier(source):
    return _bound_function(
        _evaluator._verify_admitted_finding,
        _source_identity=lambda: (source.evaluator_file.sha256, source.evaluator_file.size_bytes))


def _reconstruct_resources(record, aggregate):
    source = record.source_identity.operational_source_identity

    def aggregate_again(plan, archives, audits):
        return _historical_aggregate(plan, archives, audits, source)

    # The original summary has one fixed local import. Its private import
    # binding exposes the historical verifier, never an artifact-chosen module.
    evaluator_view = SimpleNamespace(
        _verify_admitted_finding=_historical_finding_verifier(source))
    experiments_view = SimpleNamespace(program_k_e1_evaluator=evaluator_view)

    def historical_import(name, globals=None, locals=None, fromlist=(), level=0):
        _need(name == "experiments" and fromlist == ("program_k_e1_evaluator",)
              and level == 0, "Unexpected historical reconciliation import.")
        return experiments_view

    private_builtins = dict(vars(builtins))
    private_builtins["__import__"] = historical_import
    suite_view = SimpleNamespace(**{**vars(_suite), "aggregate_e1_suite": aggregate_again})
    summarize = _bound_function(
        _RESOURCE_BODY,
        __builtins__=private_builtins, _suite=suite_view,
        _checked=_historical_checked,
        capture_operational_source_identity=lambda plan: source)
    return summarize(record.plan, aggregate, tuple(r.receipt for r in record.scheduled_results),
                     record.evaluator_results)


def reconstruct_e1_resources(record):
    """Rebuild the Slice-5 resource reconciliation from retained receipts."""
    _checked(record, E1QualificationRecord)
    return _reconstruct_resources(record, _reconstruct_suite(record))


@dataclass(frozen=True, slots=True)
class E1GateResult:
    gate_id: str
    status: str
    details: tuple[str, ...] = ()

    def __post_init__(self):
        _need(type(self.gate_id) is str and self.gate_id in tuple(f"G{i}" for i in range(1, 11)),
              "Unknown E1-stage gate.")
        _need(type(self.status) is str
              and self.status in ("PASS", "FAIL", "INCOMPLETE", "NOT_APPLICABLE"),
              "Unknown E1 gate status.")
        _texts(self.details)
        _need((self.gate_id == "G8") == (self.status == "NOT_APPLICABLE"),
              "Only G8 is not applicable at E1.")


@dataclass(frozen=True, slots=True)
class E1QualificationAssessment:
    verdict: str
    readiness: str
    gates: tuple[E1GateResult, ...]

    def __post_init__(self):
        _need(type(self.gates) is tuple and len(self.gates) == 10
              and all(type(g) is E1GateResult for g in self.gates)
              and tuple(g.gate_id for g in self.gates) == tuple(f"G{i}" for i in range(1, 11)),
              "All ten ordered E1 gates are required.")
        for gate in self.gates:
            _checked(gate, E1GateResult)
        expected = ("IMPLEMENTATION_IDENTITY_FAIL" if any(g.status == "FAIL" for g in self.gates)
                    else "INCOMPLETE" if any(g.status == "INCOMPLETE" for g in self.gates)
                    else "E1_PASS")
        readiness = ("E1_QUALIFIED" if expected == "E1_PASS" else
                     "E1_A_E5_REQUIRED" if expected == "INCOMPLETE"
                     and tuple(g.gate_id for g in self.gates if g.status == "INCOMPLETE") == ("G5",)
                     else "NOT_QUALIFIED")
        _need(type(self.verdict) is str and self.verdict == expected
              and type(self.readiness) is str and self.readiness == readiness,
              "Verdict/readiness do not follow E1 gate precedence.")

    @property
    def progression_allowed(self):
        return self.verdict == "E1_PASS"


def assess_e1(record):
    """Pure implementation assessment; historical identities are not live admission."""
    _checked(record, E1QualificationRecord)
    aggregate = resources = None
    unavailable = ()
    try:
        aggregate = _reconstruct_suite(record)
        resources = _reconstruct_resources(record, aggregate)
    except E1ReconstructionError as error:
        unavailable = (str(error),)
    results = record.scheduled_results
    audits = tuple(r.audit for r in results if r.audit is not None)
    complete = len(results) == len(audits) == 54
    public_failures, public_missing = [], []
    for result in results:
        if result.archive is not None:
            archive, audit = result.archive, result.audit
            bound = _suite.AuditedScheduledRun(
                archive.schedule_entry, archive.case, archive, _suite._content_digest(archive),
                audit, _suite._content_digest(audit), archive.execution_source_identity.digest,
                audit.source_identity.digest)
            failed, missing = _suite._run_findings(bound)
            public_failures.extend(failed)
            public_missing.extend(missing)
    falsified = any(r.evaluation is not None and r.evaluation.classification == "G1_FALSIFICATION"
                    for r in record.evaluator_results)
    missing_payload = any(
        _operation_stop(r) in ("COMPLETE_SCHEDULED_PAYLOAD_MISSING", "COMPLETE_EVALUATOR_FINDING_MISSING")
        for r in results + record.evaluator_results)
    contradictory_abort = any(_operation_stop(r) == "CONTRADICTORY_COMPLETE_ABORT"
                              for r in results + record.evaluator_results)
    failures = tuple(public_failures)
    public_incomplete = not complete or bool(public_missing)
    gates = []

    def gate(number, *, failed=False, incomplete=False, details=()):
        gates.append(E1GateResult(f"G{number}", "FAIL" if failed else
                                  "INCOMPLETE" if incomplete else "PASS", tuple(details)))

    gate(1, failed=bool(failures) or falsified or missing_payload,
         incomplete=public_incomplete,
         details=failures + (("G1_FALSIFICATION: no public proof upgrade.",) if falsified else ()))
    equivalence_fail, equivalence_missing = [], []
    for audit in audits:
        for item in audit.acquisition_audits + audit.oracle_b_audits:
            if item.status == "FAIL":
                equivalence_fail.append("Public acquisition/equivalence check failed.")
            elif item.status != "PASS":
                equivalence_missing.append("Public acquisition/equivalence check incomplete.")
        for item in audit.oracle_a_audits:
            if item.status == "NOT_EVALUATED":
                coverage = item.coverage
                if (coverage is None or coverage.status != "ORACLE_A_NOT_EVALUATED"
                        or coverage.variable_count <= coverage.envelope or item.result is not None
                        or not coverage.reason or item.discrepancies):
                    equivalence_fail.append("Oracle-A non-evaluation is not truthfully bounded.")
            elif item.status == "FAIL":
                equivalence_fail.append("Oracle-A check failed.")
            elif item.status == "PASS" and (
                    item.coverage is None or item.coverage.status != "ORACLE_A_EVALUATED"
                    or item.coverage.variable_count > item.coverage.envelope
                    or item.result is None or item.discrepancies):
                equivalence_fail.append("Oracle-A PASS lacks evaluated bounded evidence.")
            elif item.status != "PASS":
                equivalence_missing.append("Oracle-A evidence incomplete.")
    gate(2, failed=bool(equivalence_fail), incomplete=public_incomplete or bool(equivalence_missing),
         details=tuple(equivalence_fail + equivalence_missing))
    evaluated = len(record.evaluator_results) == 18 and all(
        r.receipt.status == "COMPLETE" and r.evaluation is not None for r in record.evaluator_results)
    gate(3, failed=bool(failures), incomplete=public_incomplete or not evaluated,
         details=("Detached public records; post-hoc evaluator receipts have zero physical inputs.",))
    p3 = () if aggregate is None else aggregate.p3_outcome_pairs
    p3_failed = any(p.status == "FAIL" or p.outcome in ("WL", "LW") for p in p3)
    p3_missing = len(p3) != 18 or any(p.status != "PASS" for p in p3)
    gate(4, failed=p3_failed, incomplete=p3_missing)
    mechanism = None if aggregate is None else aggregate.mechanism_coverage
    gate(5, failed=mechanism is not None and mechanism.status == "INVALID",
         incomplete=mechanism is None or mechanism.status == "MISSING",
         details=(("Prospective A-E5 required; no supplement selected or executed.",)
                  if mechanism is not None and mechanism.status == "MISSING" else
                  ("E1 mechanism legality only; no effectiveness threshold.",)))
    controls = () if aggregate is None else aggregate.control_identity_pairs
    gate(6, failed=any(p.status == "FAIL" for p in controls),
         incomplete=len(controls) != 18 or any(p.status != "PASS" for p in controls))
    gate(7, failed=p3_failed, incomplete=p3_missing)
    gates.append(E1GateResult("G8", "NOT_APPLICABLE",
                              ("Model-C diagnostics only; effectiveness belongs to E2.",)))
    job_incomplete = (bool(record.interruptions)
                      or record.elapsed_ns >= record.operating_envelope.max_job_wall_ms * 1000000
                      or record.elapsed_ns < sum(r.receipt.elapsed_ns
                                                for r in results + record.evaluator_results))
    gate(9, failed=contradictory_abort
         or resources is not None and resources.resource_status == "FAIL_IDENTITY_OR_EVIDENCE",
         incomplete=resources is None or resources.resource_status != "COMPLETE_CONTAINMENT_EVIDENCE"
         or resources.n2_status != "ADDRESSED_BY_SUPERVISED_CONTEXT_BINDING" or job_incomplete,
         details=unavailable + (() if resources is None else resources.reasons)
         + record.interruptions)
    repetitions = () if aggregate is None else aggregate.repetitions
    gate(10, failed=bool(record.diagnosed_implementation_defects) or missing_payload
         or any(r.status == "FAIL" for r in repetitions)
         or aggregate is not None and aggregate.suite_status == "FAIL",
         incomplete=not complete or not evaluated or len(repetitions) != 27
         or any(r.status != "PASS" for r in repetitions),
         details=record.diagnosed_implementation_defects)
    gates = tuple(gates)
    verdict = ("IMPLEMENTATION_IDENTITY_FAIL" if any(g.status == "FAIL" for g in gates)
               else "INCOMPLETE" if any(g.status == "INCOMPLETE" for g in gates) else "E1_PASS")
    readiness = ("E1_QUALIFIED" if verdict == "E1_PASS" else
                 "E1_A_E5_REQUIRED" if verdict == "INCOMPLETE"
                 and tuple(g.gate_id for g in gates if g.status == "INCOMPLETE") == ("G5",)
                 else "NOT_QUALIFIED")
    return E1QualificationAssessment(verdict, readiness, gates)


def _now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def execute_e1(*, run_id, plan, envelope, source_identity, authorization_reference):
    """Future authorized single attempt: exact 54 then 18, with no retries.

    Slice-6 tests replace both supervisors. This function never publishes.
    Source drift and diagnosed implementation faults stop dispatch; operational
    interruptions preserve the obtained prefix without an invented outcome.
    """
    preflight = preflight_e1(
        plan, envelope, source_identity, run_id=run_id,
        authorization_reference=authorization_reference)
    _need(preflight.status == "READY", "E1 preflight refused: " + "; ".join(preflight.reasons))
    started = time.monotonic_ns()
    started_utc = _now_utc()
    scheduled, evaluations, interruptions, defects = [], [], [], []
    used = 0

    def source_current():
        try:
            _need(capture_qualification_source_identity(plan) == source_identity,
                  "Final E1 source identity changed.")
        except _ERRORS as error:
            defects.append("SOURCE_DRIFT: " + str(error))
            return False
        return True

    def stop(result):
        reason = _operation_stop(result)
        if reason is not None:
            if reason in ("COMPLETE_SCHEDULED_PAYLOAD_MISSING",
                          "COMPLETE_EVALUATOR_FINDING_MISSING", "PUBLIC_AUDIT_FAIL",
                          "G1_FALSIFICATION", "CONTRADICTORY_COMPLETE_ABORT"):
                defects.append(reason)
            else:
                interruptions.append(reason + ": " + (result.receipt.reason or "public evidence incomplete"))
        return reason is not None

    aggregate = None
    try:
        for entry in plan.schedule:
            if not source_current():
                break
            result = _operational.supervise_scheduled_run(
                plan, entry.schedule_index, envelope,
                job_started_ns=started, archive_used_bytes=used)
            _need(type(result) is _operational.E1OperationResult, "Supervisor returned a non-result.")
            scheduled.append(result)
            used = result.receipt.archive_used_after_bytes
            if stop(result) or not source_current():
                break
        if len(scheduled) == 54 and not interruptions and not defects:
            aggregate = _suite.aggregate_e1_suite(
                plan, tuple(r.archive for r in scheduled), tuple(r.audit for r in scheduled))
            if aggregate.suite_status == "FAIL":
                defects.append("SUITE_FAIL: " + "; ".join(aggregate.semantic_failures))
            elif source_current():
                for binding in aggregate.bindings:
                    if binding.schedule_entry.variant != "K-P0":
                        continue
                    if not source_current():
                        break
                    index = binding.schedule_entry.schedule_index
                    result = _operational.supervise_posthoc_evaluator(
                        plan, aggregate, binding, envelope, job_started_ns=started,
                        archive_used_bytes=used, evaluation_run_id=evaluation_run_id(run_id, index))
                    _need(type(result) is _operational.E1OperationResult, "Evaluator supervisor returned a non-result.")
                    evaluations.append(result)
                    used = result.receipt.archive_used_after_bytes
                    if stop(result) or not source_current():
                        break
    except KeyboardInterrupt:
        interruptions.append("ORCHESTRATION_INTERRUPTED")
    except Exception as error:
        defects.append("ORCHESTRATION_EXCEPTION: " + type(error).__name__ + ": " + str(error))
    source_current()
    ended_utc = _now_utc()
    elapsed = time.monotonic_ns() - started
    if elapsed >= envelope.max_job_wall_ms * 1000000:
        interruptions.append("SYSTEM_JOB_TIMEOUT")
    return E1QualificationRecord(
        run_id, "E1_QUALIFICATION", authorization_reference, source_identity, plan, envelope,
        started_utc, ended_utc, elapsed, tuple(scheduled), tuple(evaluations),
        tuple(interruptions), tuple(defects))


# Named closed families only; no private layouts, Engine, HiddenAnswer or test.
_RECORD_TYPES = _suite._RECORD_TYPES + (
    _findings.ArchivedAssertion, _findings.SealedEvaluatorInput, _findings.CoordinateComparison,
    _findings.AssertionFinding, _findings.FalsificationResult, _findings.EvaluatorCallDiagnostic,
    _evaluator.E1EvaluatorFinding, _operational.E1OperationalSourceFile,
    _operational.E1OperationalSourceIdentity, _operational.E1MonitorEvent,
    _operational.E1OperationReceipt, _operational.E1OperationResult,
    _operational.E1ResourceSummary, _harness.OperatingEnvelope, _harness.MemoryEvidence,
    E1QualificationSourceFile, E1QualificationSourceIdentity, E1Preflight,
    E1QualificationRecord, E1GateResult, E1QualificationAssessment,
)
