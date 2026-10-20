"""One-way fixed-board E1 answer adapter after the complete public suite.

Only this adapter reconstructs E1 answers for falsification. Admission and the
public archive seal finish first; truth then reaches only the accepted
``program_k_evaluator`` comparison API. Returned evidence retains its approved
finding structure and answer digest, never the complete layout. No result can
resume execution, establish public proof, or select a later experiment.
"""

from dataclasses import dataclass, fields, replace
import hashlib
import json
from pathlib import Path

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
