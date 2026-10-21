"""One-way fixed-board E1 answer adapter after the complete public suite.

Only this adapter reconstructs E1 answers for falsification. Admission and the
public archive seal finish first; truth then reaches only the accepted
``program_k_evaluator`` comparison API. Returned evidence retains its approved
finding structure and answer digest, never the complete layout. No result can
resume execution, establish public proof, or select a later experiment.
"""

from dataclasses import asdict, dataclass, fields, replace
import hashlib
import json
from pathlib import Path
import re

import benchmark_board as _board
from experiments import program_k_e1_harness as _e1
from experiments import program_k_e1_suite as _suite
from experiments import program_k_evaluator as _evaluator
from experiments import program_k_harness as _harness


EVALUATOR_SOURCE_PATH = "experiments/program_k_e1_evaluator.py"


class E1EvaluatorError(ValueError):
    """Unbound, premature, stale or substituted evaluator input."""


def _need(condition, detail):
    if not condition:
        raise E1EvaluatorError(detail)


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Invalid SHA-256.")


def _source_identity():
    raw = Path(__file__).read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def require_complete_suite(plan, aggregate):
    """Reconstruct the entire supplied aggregate, without execution or truth.

    Exact tagged encoding includes fields whose dataclass equality excludes
    timing. All 54 bound archives and audits must exist even when public semantic
    coverage is INCOMPLETE. This is sequencing evidence, not authorization.
    """
    try:
        _need(type(plan) is _e1.E1Plan, "An exact current E1 plan is required.")
        replace(plan)
        _need(plan.runtime == _e1.capture_runtime_identity(),
              "Current evaluator runtime differs from the sealed plan.")
        _need(type(aggregate) is _suite.E1SuiteAggregate,
              "An already-built complete 54-run aggregate is required.")
        _suite._encoded(aggregate)  # Reject live/mutable/hidden graph attachments.
        _need(_suite._encoded(aggregate.plan) == _suite._encoded(plan)
              and aggregate.plan_identity == plan.source_identity.digest,
              "Aggregate belongs to another plan.")
        _need(type(aggregate.bindings) is tuple and len(aggregate.bindings) == 54
              and all(type(b) is _suite.AuditedScheduledRun for b in aggregate.bindings),
              "Exactly 54 immutable archive/audit bindings are required.")
        for bound in aggregate.bindings:
            # Slice 3 deliberately admits incomplete structures for diagnosis.
            # Evaluator sequencing instead requires all terminal archives.
            replace(bound.archive)
        rebuilt = _suite.aggregate_e1_suite(
            plan, tuple(b.archive for b in aggregate.bindings),
            tuple(b.audit for b in aggregate.bindings))
        _need(_suite._encoded(rebuilt) == _suite._encoded(aggregate),
              "Suite summary or exact archive/audit bindings do not reconstruct.")
        _need(aggregate.coverage.status == "PASS"
              and aggregate.coverage.expected_count == aggregate.coverage.archive_count
              == aggregate.coverage.audit_count == 54
              and aggregate.suite_status in ("PASS", "INCOMPLETE"),
              "Evaluator requires complete fixed coverage with PASS/INCOMPLETE semantics.")
        return aggregate
    except (OSError, ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        if type(error) is E1EvaluatorError:
            raise
        raise E1EvaluatorError("Complete suite admission refused: " + str(error)) from error


def validate_evaluator_request(plan, aggregate, binding):
    """Truth-free exact K-P0 membership admission; no arbitrary archive override."""
    require_complete_suite(plan, aggregate)
    try:
        _need(type(binding) is _suite.AuditedScheduledRun,
              "An exact aggregate-owned binding is required.")
        _suite._encoded(binding)
        entry = binding.schedule_entry
        _need(type(entry) is _e1.ScheduleEntry, "Missing exact schedule entry.")
        replace(entry)
        _need(entry.variant == "K-P0", "Only scheduled K-P0 archives are evaluator targets.")
        expected = aggregate.bindings[entry.schedule_index]
        _need(_suite._encoded(binding) == _suite._encoded(expected),
              "Binding is not the exact member of this complete aggregate.")
        return expected
    except (ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        if type(error) is E1EvaluatorError:
            raise
        raise E1EvaluatorError("K-P0 binding admission refused: " + str(error)) from error


def _seal(binding, evaluation_run_id):
    # Reuse the accepted public projection, including its approved legacy
    # archive digest. The wrapper separately binds the complete E1 archive.
    return _harness.seal_execution_archive(
        _harness.ExecutionArchive(binding.case.case_id, "K-P0", binding.archive.result),
        run_id=evaluation_run_id)


def _phase_run_id(run_id):
    _need(type(run_id) is str
          and re.fullmatch(r"e1-[A-Za-z0-9][A-Za-z0-9_-]{0,75}", run_id) is not None,
          "An exact qualification run identity is required.")


@dataclass(frozen=True, slots=True)
class E1EvaluatorRequest:
    """One public seal, with no plan, execution result, audit or answer graph.

    Its digest is compared with the independently retained phase commitment.
    A self-consistent request alone is never evidence of complete-suite membership.
    """

    schedule_entry: _e1.ScheduleEntry
    case: _e1.SealedCaseRegistration
    plan_source_digest: str
    suite_source_digest: str
    suite_content_digest: str
    archive_content_digest: str
    evaluation_run_id: str
    sealed_input: _evaluator.SealedEvaluatorInput

    def __post_init__(self):
        _need(type(self.schedule_entry) is _e1.ScheduleEntry
              and type(self.case) is _e1.SealedCaseRegistration
              and type(self.sealed_input) is _evaluator.SealedEvaluatorInput,
              "Exact detached schedule, case and public seal required.")
        entry, case, sealed = (replace(self.schedule_entry), replace(self.case),
                               replace(self.sealed_input))
        _need(entry == _e1.build_schedule()[entry.schedule_index]
              and entry.variant == "K-P0" and case.case_id == entry.case_id,
              "Compact target is not an exact fixed K-P0 schedule member.")
        for name in ("plan_source_digest", "suite_source_digest", "suite_content_digest",
                     "archive_content_digest"):
            _sha(getattr(self, name))
        suffix = f"-kp0-{entry.schedule_index:02d}"
        _need(type(self.evaluation_run_id) is str and self.evaluation_run_id.endswith(suffix),
              "Evaluator run identity does not bind its schedule index.")
        _phase_run_id(self.evaluation_run_id[:-len(suffix)])
        _need((sealed.case_id, sealed.run_id, sealed.width, sealed.height)
              == (case.case_id + ":K-P0", self.evaluation_run_id, case.width, case.height),
              "Public seal differs from the compact case/run binding.")


def request_bytes(request):
    """Closed value encoding of one target, including its public assertions."""
    _need(type(request) is E1EvaluatorRequest, "Exact compact evaluator request required.")
    checked = replace(request)
    return json.dumps(asdict(checked), sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def request_digest(request):
    return hashlib.sha256(request_bytes(request)).hexdigest()


@dataclass(frozen=True, slots=True)
class E1EvaluatorAdmission:
    """The 18 immutable projections and commitments from one admitted suite.

    This value stays in the coordinator. Only one target and its independent
    commitment cross each worker boundary. Neither object identity nor a cache
    is used as membership authority.
    """

    run_id: str
    operational_source_identity: object
    suite_content_digest: str
    targets: tuple[E1EvaluatorRequest, ...]
    target_digests: tuple[str, ...]

    def __post_init__(self):
        from experiments import program_k_e1_operational as operational
        _phase_run_id(self.run_id)
        _sha(self.suite_content_digest)
        _need(type(self.operational_source_identity) is operational.E1OperationalSourceIdentity,
              "Exact admitted operational source identity required.")
        replace(self.operational_source_identity)
        _admission_catalog(self)
        for target, digest in zip(self.targets, self.target_digests):
            _need(request_digest(target) == digest, "Admitted target commitment differs.")


def _admission_catalog(admission):
    """Check the small fixed catalog; never traverse unrelated public seals."""
    from experiments import program_k_e1_operational as operational
    _phase_run_id(admission.run_id)
    _sha(admission.suite_content_digest)
    _need(type(admission.targets) is tuple and len(admission.targets) == 18
          and type(admission.target_digests) is tuple and len(admission.target_digests) == 18,
          "Exactly 18 ordered evaluator targets and commitments required.")
    source = admission.operational_source_identity
    _need(type(source) is operational.E1OperationalSourceIdentity,
          "Exact admitted operational source identity required.")
    replace(source)
    plan_digest, suite_digest = source.plan_source_identity.digest, source.suite_source_identity.digest
    for index, target, digest in zip(range(2, 54, 3), admission.targets, admission.target_digests):
        _need(type(target) is E1EvaluatorRequest
              and type(target.schedule_entry) is _e1.ScheduleEntry
              and target.schedule_entry == _e1.build_schedule()[index]
              and (target.plan_source_digest, target.suite_source_digest,
                   target.suite_content_digest, target.evaluation_run_id)
              == (plan_digest, suite_digest, admission.suite_content_digest,
                  f"{admission.run_id}-kp0-{index:02d}"),
              "Missing, reordered, substituted or stale admitted evaluator target.")
        _sha(digest)


def _admit_constructed_suite(plan, aggregate, *, run_id):
    """Project the aggregate just returned by live orchestration's sole builder.

    Private construction seam, not an admission API for supplied aggregates.
    External aggregate callers use admit_evaluator_phase and its reconstruction.
    """
    from experiments import program_k_e1_operational as operational
    _phase_run_id(run_id)
    _need(type(plan) is _e1.E1Plan and type(aggregate) is _suite.E1SuiteAggregate,
          "An exact constructed plan/suite is required.")
    replace(plan)
    source = operational.capture_operational_source_identity(plan)
    _need(aggregate.plan == plan and aggregate.plan_identity == plan.source_identity.digest
          and aggregate.source_identity == source.suite_source_identity
          and aggregate.coverage.status == "PASS"
          and aggregate.coverage.expected_count == aggregate.coverage.archive_count
          == aggregate.coverage.audit_count == 54
          and type(aggregate.bindings) is tuple and len(aggregate.bindings) == 54
          and aggregate.suite_status in ("PASS", "INCOMPLETE"),
          "Evaluator phase requires the complete non-FAIL constructed suite.")
    # The sole whole-suite content digest for the live evaluator phase.
    digest = _suite._content_digest(aggregate)
    targets = []
    for entry, binding in zip(plan.schedule, aggregate.bindings):
        _need(type(binding) is _suite.AuditedScheduledRun
              and binding.schedule_entry == entry, "Constructed suite order differs.")
        # The suite builder also supports incomplete diagnostic records; live
        # admission requires every scheduled archive to be terminal.
        replace(binding.archive)
        if entry.variant == "K-P0":
            evaluation_id = f"{run_id}-kp0-{entry.schedule_index:02d}"
            targets.append(E1EvaluatorRequest(
                entry, binding.case, plan.source_identity.digest, aggregate.source_identity.digest,
                digest, binding.archive_content_digest, evaluation_id, _seal(binding, evaluation_id)))
    return E1EvaluatorAdmission(run_id, source, digest, tuple(targets),
                                tuple(request_digest(target) for target in targets))


def admit_evaluator_phase(plan, aggregate, *, run_id):
    """One complete admission for an externally supplied public aggregate."""
    return _admit_constructed_suite(
        plan, require_complete_suite(plan, aggregate), run_id=run_id)


def validate_compact_request(request, expected_digest, source_identity):
    """Authenticate one transported target against its independent commitment."""
    from experiments import program_k_e1_operational as operational
    _sha(expected_digest)
    _need(request_digest(request) == expected_digest,
          "Compact request differs from the admitted target commitment.")
    operational.require_evaluator_source_identity(source_identity, request.case.runtime)
    _need((request.plan_source_digest, request.suite_source_digest)
          == (source_identity.plan_source_identity.digest, source_identity.suite_source_identity.digest),
          "Compact request source binding differs.")
    return request


def validate_admitted_request(admission, request):
    """Truth-free membership check against persistent admitted values."""
    _need(type(admission) is E1EvaluatorAdmission and type(request) is E1EvaluatorRequest,
          "Exact immutable admission and compact request required.")
    _admission_catalog(admission)
    # Validate shape before indexing; bools and CONTROL targets cannot select a slot.
    request_bytes(request)
    position = request.schedule_entry.schedule_index // 3
    expected_digest = admission.target_digests[position]
    _need(request_bytes(request) == request_bytes(admission.targets[position]),
          "Request is not the exact admitted K-P0 projection.")
    validate_compact_request(request, expected_digest, admission.operational_source_identity)
    return expected_digest


def _fixed_answer(case, sealed):
    """Private evaluator scope; never returns an answer from the public adapter."""
    definition = _e1._definition(case.case_id)
    _need((case.width, case.height, case.num_mines)
          == (definition.width, definition.height, definition.num_mines)
          and (sealed.width, sealed.height) == (case.width, case.height),
          "Answer dimensions or declared mine count differ from the fixed case.")
    if case.game_index is None:
        _need(definition.game_index is None and case.seed is None,
              "Synthetic case cannot acquire a generator identity.")
        mines = definition.mine_positions
    else:
        spec = _board.EXPERT_GENERAL_V1
        _need(type(spec) is _board.BenchmarkSetSpec
              and all(type(v) is int for v in
                      (spec.width, spec.height, spec.num_mines,
                       spec.first_click_x, spec.first_click_y))
              and (spec.benchmark_set_id, spec.width, spec.height, spec.num_mines,
                   spec.first_click_x, spec.first_click_y,
                   spec.board_generator_version, spec.seed_scheme)
              == (case.benchmark_set_id, case.width, case.height, case.num_mines,
                  *case.first_click, case.board_generator_version, case.seed_scheme),
              "Frozen Expert generator metadata differs from the seal.")
        generated = _board.generate_board(spec, case.game_index)  # Exactly once; no retry.
        _need(type(generated) is _board.BenchmarkBoard
              and type(generated.game_index) is int and type(generated.seed) is int
              and generated.game_index == generated.seed
              == case.game_index == case.seed == definition.game_index,
              "Generated Expert index or seed differs.")
        mines = generated.mine_positions
    _need(type(mines) in (tuple, frozenset)
          and all(type(c) is tuple and len(c) == 2
                  and all(type(v) is int for v in c) for c in mines),
          "Fixed answer requires detached exact integer coordinates.")
    fingerprint = _board.calculate_board_fingerprint(
        case.width, case.height, case.num_mines, mines)
    _need(case.first_click not in mines, "Fixed answer violates first-click safety.")
    _need(fingerprint == case.board_fingerprint == definition.board_fingerprint,
          "Reconstructed fixed answer fingerprint differs from the seal.")
    if case.game_index is not None:
        _need(type(generated.board_fingerprint) is str
              and generated.board_fingerprint == fingerprint,
              "Generator fingerprint does not reconstruct from its exact layout.")
    return _evaluator.HiddenAnswer(
        sealed.case_id, sealed.run_id, sealed.width, sealed.height,
        frozenset(mines), sealed.archive_digest, case.num_mines)


@dataclass(frozen=True, slots=True)
class E1EvaluatorFinding:
    """Detached evaluator finding and both legacy/E1 archive bindings.

    ``answer_digest`` is the existing evaluator's exact archive-bound digest.
    A matching comparison remains only NO_COUNTEREXAMPLE, never public proof.
    Actual evaluator call spans stay separate from runner and oracle timings.
    """

    schedule_index: int
    case_id: str
    repetition: int
    variant: str
    evaluation_run_id: str
    suite_source_digest: str
    suite_content_digest: str
    plan_source_digest: str
    archive_content_digest: str
    board_fingerprint: str
    sealed_archive_digest: str
    answer_digest: str
    evaluator_source_sha256: str
    evaluator_source_size_bytes: int
    finding: _evaluator.FalsificationResult
    evaluator_calls: tuple[_evaluator.EvaluatorCallDiagnostic, ...]

    def __post_init__(self):
        _need(type(self.schedule_index) is int and 0 <= self.schedule_index < 54
              and type(self.case_id) is str
              and type(self.repetition) is int
              and type(self.variant) is str and self.variant == "K-P0",
              "Malformed scheduled evaluator identity.")
        entry = _e1.build_schedule()[self.schedule_index]
        _need((entry.case_id, entry.repetition, entry.variant)
              == (self.case_id, self.repetition, self.variant),
              "Evaluator schedule/case/repetition substitution.")
        _need(type(self.evaluation_run_id) is str and bool(self.evaluation_run_id.strip()),
              "Explicit evaluator run identity required.")
        for name in ("suite_source_digest", "suite_content_digest", "plan_source_digest",
                     "archive_content_digest", "board_fingerprint",
                     "sealed_archive_digest", "answer_digest",
                     "evaluator_source_sha256"):
            _sha(getattr(self, name))
        _need(type(self.evaluator_source_size_bytes) is int
              and self.evaluator_source_size_bytes > 0, "Missing evaluator source byte size.")
        _need(type(self.finding) is _evaluator.FalsificationResult,
              "Existing immutable evaluator finding required.")
        finding = replace(self.finding)  # Existing constructors check every nested comparison.
        _need(finding.case_id == self.case_id + ":K-P0"
              and finding.run_id == self.evaluation_run_id
              and finding.sealed_input.archive_digest == self.sealed_archive_digest
              and finding.answer_digest == self.answer_digest,
              "Existing finding differs from its schedule/run/archive/answer binding.")
        _need(type(self.evaluator_calls) is tuple and len(self.evaluator_calls) == 1
              and type(self.evaluator_calls[0]) is _evaluator.EvaluatorCallDiagnostic,
              "Exactly one actual evaluator call diagnostic is required.")
        call = replace(self.evaluator_calls[0])
        _need(call.sequence == 0 and call.error is None
              and (call.sealed_input_digest, call.answer_digest, call.classification,
                   call.evaluated_coordinate_count)
              == (finding.sealed_input.assertions_digest, finding.answer_digest,
                  finding.classification, finding.evaluated_coordinate_count),
              "Evaluator diagnostic does not bind the exact retained finding.")
        object.__setattr__(self, "finding", finding)
        object.__setattr__(self, "evaluator_calls", (call,))

    @property
    def classification(self):
        return self.finding.classification

    @property
    def proof_upgrade_allowed(self):
        return False


def canonical_bytes(finding):
    """In-memory integrity encoding only; no durable E1 codec or readback."""
    _need(type(finding) is E1EvaluatorFinding, "Exact E1 evaluator finding required.")
    checked = replace(finding)
    # The accepted codec admits only its closed finding/diagnostic vocabulary;
    # the new envelope is encoded explicitly and cannot contain a HiddenAnswer.
    values = tuple((f.name, _harness.canonical_bytes(getattr(checked, f.name)).decode("ascii"))
                   for f in fields(checked))
    return json.dumps(values, ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def content_digest(finding):
    return hashlib.sha256(canonical_bytes(finding)).hexdigest()


def _verify_admitted_finding(plan, aggregate, binding, finding, evaluation_run_id,
                            *, suite_content_digest=None):
    # The operational summary has already reconstructed the complete aggregate
    # once. Its private call may reuse that exact aggregate's computed digest;
    # public verification always admits and hashes the supplied aggregate.
    expected_suite_digest = (_suite._content_digest(aggregate)
                             if suite_content_digest is None else suite_content_digest)
    _sha(expected_suite_digest)
    _need(type(finding) is E1EvaluatorFinding, "Exact E1 evaluator finding required.")
    finding = replace(finding)
    sealed = _seal(binding, finding.evaluation_run_id)
    _need(evaluation_run_id is None or finding.evaluation_run_id == evaluation_run_id,
          "Evaluator operation identity differs.")
    _need((finding.schedule_index, finding.case_id, finding.repetition, finding.variant)
          == (binding.schedule_entry.schedule_index, binding.case.case_id,
              binding.schedule_entry.repetition, "K-P0"),
          "Finding belongs to another scheduled run.")
    _need((finding.suite_source_digest, finding.suite_content_digest,
           finding.plan_source_digest, finding.archive_content_digest, finding.board_fingerprint)
          == (aggregate.source_identity.digest, expected_suite_digest,
              plan.source_identity.digest, binding.archive_content_digest,
              binding.case.board_fingerprint),
          "Finding suite/source/archive binding differs.")
    _need((finding.evaluator_source_sha256, finding.evaluator_source_size_bytes)
          == _source_identity(), "Evaluator source bytes changed.")
    _need(finding.finding.sealed_input == sealed
          and finding.sealed_archive_digest == sealed.archive_digest,
          "Finding does not retain the exact accepted public archive seal.")
    canonical_bytes(finding)
    return finding


def verify_e1_finding(plan, aggregate, binding, finding, *, evaluation_run_id=None):
    """Truth-free parent verification of worker-produced immutable evidence.

    This verifies source, suite, archive, seal and call/answer-digest binding.
    The worker separately calls the accepted ``verify_bound_finding`` against
    its reconstructed answer. This function never regenerates a board or
    purports to independently prove a hidden truth bit from a digest.
    """
    binding = validate_evaluator_request(plan, aggregate, binding)
    try:
        return _verify_admitted_finding(plan, aggregate, binding, finding, evaluation_run_id)
    except (OSError, ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        if type(error) is E1EvaluatorError:
            raise
        raise E1EvaluatorError("Retained evaluator binding refused: " + str(error)) from error


def evaluate_scheduled_kp0(plan, aggregate, binding, *, evaluation_run_id):
    """Evaluate one already completed K-P0 binding, after all 54 runs exist.

    This operation is intended for the supervised evaluator worker. It confers
    no research execution authorization and has no Engine/runner callback.
    """
    binding = validate_evaluator_request(plan, aggregate, binding)
    _need(type(evaluation_run_id) is str and bool(evaluation_run_id.strip()),
          "Explicit evaluator run identity required.")
    source_sha, source_size = _source_identity()
    sealed = _seal(binding, evaluation_run_id)
    try:
        answer = _fixed_answer(binding.case, sealed)
        with _evaluator.collect_evaluator_diagnostics() as calls:
            finding = _evaluator.evaluate_falsification(sealed, answer)
        _evaluator.verify_bound_finding(finding, sealed, answer)
        retained = E1EvaluatorFinding(
            binding.schedule_entry.schedule_index, binding.case.case_id,
            binding.schedule_entry.repetition, "K-P0", evaluation_run_id,
            aggregate.source_identity.digest, _suite._content_digest(aggregate),
            plan.source_identity.digest, binding.archive_content_digest, binding.case.board_fingerprint,
            sealed.archive_digest, answer.answer_digest, source_sha, source_size,
            finding, tuple(calls))
        _need(_source_identity() == (source_sha, source_size),
              "Evaluator source changed during the operation.")
        _need(_suite.capture_suite_source_identity(plan, binding.archive, binding.audit)
              == aggregate.source_identity, "Suite source changed during evaluator work.")
        return retained
    except (OSError, ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        if type(error) is E1EvaluatorError:
            raise
        raise E1EvaluatorError("Post-hoc fixed-board evaluation refused: " + str(error)) from error


def verify_compact_finding(request, expected_digest, source_identity, finding):
    """Parent/worker verification against one admitted public projection only.

    Hidden-answer binding is checked by the accepted comparator in the worker;
    this truth-free verifier retains the original no-proof-upgrade semantics.
    Historical reconstruction continues to use _verify_admitted_finding.
    """
    validate_compact_request(request, expected_digest, source_identity)
    _need(type(finding) is E1EvaluatorFinding, "Exact E1 evaluator finding required.")
    finding = replace(finding)
    entry, case, sealed = request.schedule_entry, request.case, request.sealed_input
    _need((finding.schedule_index, finding.case_id, finding.repetition, finding.variant,
           finding.evaluation_run_id, finding.plan_source_digest, finding.suite_source_digest,
           finding.suite_content_digest, finding.archive_content_digest, finding.board_fingerprint)
          == (entry.schedule_index, case.case_id, entry.repetition, "K-P0",
              request.evaluation_run_id, request.plan_source_digest, request.suite_source_digest,
              request.suite_content_digest, request.archive_content_digest, case.board_fingerprint),
          "Finding differs from its admitted target/source/archive binding.")
    _need((finding.evaluator_source_sha256, finding.evaluator_source_size_bytes)
          == (source_identity.evaluator_file.sha256, source_identity.evaluator_file.size_bytes),
          "Finding evaluator source differs.")
    _need(finding.finding.sealed_input == sealed
          and finding.sealed_archive_digest == sealed.archive_digest,
          "Finding public seal differs from the exact admitted input.")
    canonical_bytes(finding)
    return finding


def evaluate_compact_request(request, expected_digest, source_identity):
    """Worker-only falsification; no aggregate reconstruction, hash or transport."""
    validate_compact_request(request, expected_digest, source_identity)
    try:
        sealed = request.sealed_input
        answer = _fixed_answer(request.case, sealed)
        with _evaluator.collect_evaluator_diagnostics() as calls:
            finding = _evaluator.evaluate_falsification(sealed, answer)
        _evaluator.verify_bound_finding(finding, sealed, answer)
        entry = request.schedule_entry
        retained = E1EvaluatorFinding(
            entry.schedule_index, entry.case_id, entry.repetition, "K-P0",
            request.evaluation_run_id, request.suite_source_digest, request.suite_content_digest,
            request.plan_source_digest, request.archive_content_digest, request.case.board_fingerprint,
            sealed.archive_digest, answer.answer_digest, source_identity.evaluator_file.sha256,
            source_identity.evaluator_file.size_bytes, finding, tuple(calls))
        return verify_compact_finding(request, expected_digest, source_identity, retained)
    except (OSError, ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        if type(error) is E1EvaluatorError:
            raise
        raise E1EvaluatorError("Compact fixed-board evaluation refused: " + str(error)) from error
