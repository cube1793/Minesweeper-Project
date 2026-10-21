"""Slice-6 qualification tests using manual records and mocked dispatch only.

The frozen schedule names bind metadata in the accepted Slice-4 fixtures.
No board, scheduled research action, or actual E1 evaluator is executed here.
Synthetic E1_PASS exercises assessment; it is not an actual E1 result.
"""

import ast
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
import hashlib
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import benchmark_board
import core_engine
from core_engine import Action, CellState, GameStatus
from experiments import program_k_e1_audit as audit
from experiments import program_k_e1_evaluator as e1_evaluator
from experiments import program_k_e1_execution as execution
from experiments import program_k_e1_harness as e1
from experiments import program_k_e1_operational as operational
from experiments import program_k_e1_qualification as qualification
from experiments import program_k_e1_suite as suite
from experiments import program_k_evaluator as evaluator
from experiments import program_k_harness as harness
from experiments import program_k_oracles as oracles
from tests.test_program_k_e1_audit import _corrupt
from tests.test_program_k_e1_operational import (
    _aggregate, _envelope, _manual_evaluation, _manual_receipt, _receipt_change,
)
from tests.test_program_k_e1_suite import (
    _bind_p3, _data, _declared_result, _index, _set,
)
from tests import test_program_k_e1_audit as audit_fixtures
from tests import test_program_k_e1_operational as operational_fixtures
from tests import test_program_k_e1_suite as suite_fixtures


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "e1-slice6-manual"
_MANUAL = {}


def _finding(aggregate, binding, run_id, *, falsification=False):
    """Rename a declared Slice-5 finding; no hidden answer is constructed."""
    found = _manual_evaluation(aggregate, binding, falsification=falsification)
    evaluation_id = qualification.evaluation_run_id(
        run_id, binding.schedule_entry.schedule_index)
    sealed = replace(found.finding.sealed_input, run_id=evaluation_id)
    result = replace(found.finding, sealed_input=sealed)
    call = replace(found.evaluator_calls[0], sealed_input_digest=sealed.assertions_digest)
    return replace(found, evaluation_run_id=evaluation_id, finding=result,
                   evaluator_calls=(call,))


def _operations(aggregate, source, envelope, *, run_id=RUN_ID, evaluations=True):
    """Declare fresh receipts for exactly this detached evidence family."""
    scheduled, evaluated, used = [], [], 0
    for binding in aggregate.bindings:
        receipt = _manual_receipt(
            binding.schedule_entry, source.operational_source_identity,
            (binding.archive, binding.audit, None),
            physical_inputs=len(binding.archive.result.traces),
            envelope=envelope, used=used)
        scheduled.append(operational.E1OperationResult(
            receipt, binding.archive, binding.audit))
        used = receipt.archive_used_after_bytes
    if evaluations:
        for binding in aggregate.bindings:
            if binding.schedule_entry.variant != "K-P0":
                continue
            found = _finding(aggregate, binding, run_id)
            receipt = _manual_receipt(
                binding.schedule_entry, source.operational_source_identity,
                (None, None, found), kind="POST_HOC_EVALUATOR",
                envelope=envelope, used=used)
            evaluated.append(operational.E1OperationResult(receipt, evaluation=found))
            used = receipt.archive_used_after_bytes
    return tuple(scheduled), tuple(evaluated)


def _qualification_data(*, aggregate=None, envelope=None, run_id=RUN_ID):
    """Return aggregate, CURRENT final identity, envelope, scheduled, evaluators.

    Only existing detached fixture components are cached. Final qualification
    source identity is captured on every call so edits are never masked.
    """
    default = aggregate is None and envelope is None
    aggregate = _aggregate() if aggregate is None else aggregate
    envelope = _envelope() if envelope is None else envelope
    source = qualification.capture_qualification_source_identity(aggregate.plan)
    key = run_id, source.operational_source_identity.digest
    if default and key in _MANUAL:
        scheduled, evaluated = _MANUAL[key]
    else:
        scheduled, evaluated = _operations(
            aggregate, source, envelope, run_id=run_id,
            evaluations=aggregate.suite_status != "FAIL")
        if default:
            _MANUAL[key] = scheduled, evaluated
    return aggregate, source, envelope, scheduled, evaluated


def _record(**changes):
    """Complete manual record, with optional constructor-field replacements.

    Persistence tests reuse this helper. ``aggregate`` is an optional fixture
    input, not a qualification-record field. Alternate run IDs and envelopes
    generate a matching declared receipt/finding graph.
    """
    aggregate = changes.pop("aggregate", None)
    values = _qualification_data(
        aggregate=aggregate, envelope=changes.get("operating_envelope"),
        run_id=changes.get("run_id", RUN_ID))
    aggregate, source, envelope, scheduled, evaluated = values
    arguments = dict(
        run_id=RUN_ID, purpose="E1_QUALIFICATION",
        authorization_reference="Slice-6 MANUAL TEST ONLY; no execution authorization.",
        source_identity=source, plan=aggregate.plan, operating_envelope=envelope,
        started_utc="2026-10-20T00:00:00Z", ended_utc="2026-10-20T00:00:01Z",
        elapsed_ns=1_000_000_000, scheduled_results=scheduled,
        evaluator_results=evaluated, interruptions=(),
        diagnosed_implementation_defects=())
    arguments.update(changes)
    return qualification.E1QualificationRecord(**arguments)


def _rechain(results, *, used=0):
    changed = []
    for result in results:
        receipt = _receipt_change(result.receipt, archive_used_before_bytes=used)
        changed.append(replace(result, receipt=receipt))
        used = receipt.archive_used_after_bytes
    return tuple(changed)


def _scheduled_change(result, *, checked=None, **receipt_changes):
    checked = result.audit if checked is None else checked
    raw = operational._payload_bytes((result.archive, checked, None))
    receipt_changes.update(result_digest=hashlib.sha256(raw).hexdigest(),
                           result_size_bytes=len(raw), archive_result_bytes=len(raw))
    receipt = _receipt_change(result.receipt, **receipt_changes)
    return operational.E1OperationResult(receipt, result.archive, checked)


def _abort_event(result, event_name):
    """Declare contradictory COMPLETE containment evidence without dispatch."""
    receipt = result.receipt
    final = receipt.events[-1]
    abort = operational.E1MonitorEvent(
        final.sequence, event_name, final.elapsed_ns, final.physical_inputs,
        "Manual contradictory completion fixture")
    events = receipt.events[:-1] + (abort, replace(
        final, sequence=final.sequence + 1, elapsed_ns=final.elapsed_ns + 1))
    return replace(result, receipt=_receipt_change(receipt, events=events))


def _falsification(record):
    aggregate = qualification.reconstruct_e1_suite(record)
    index = next(i for i, result in enumerate(record.evaluator_results)
                 if result.receipt.case_id == "S-LIFECYCLE")
    original = record.evaluator_results[index]
    binding = aggregate.bindings[original.receipt.schedule_index]
    found = _finding(aggregate, binding, record.run_id, falsification=True)
    receipt = _manual_receipt(
        binding.schedule_entry, record.source_identity.operational_source_identity,
        (None, None, found), kind="POST_HOC_EVALUATOR",
        envelope=record.operating_envelope,
        used=original.receipt.archive_used_before_bytes)
    changed = operational.E1OperationResult(receipt, evaluation=found)
    return record.evaluator_results[:index] + (changed,)


def _mechanism_aggregate(status):
    plan, archives, checked = _data()
    for rep in (1, 2):
        index = _index(repetition=rep)
        observations = tuple(
            replace(item, kind="DIRECT_CHORD" if item.action is Action.CHORD else "OTHER",
                    prior_setup_input_indices=())
            if status == "MISSING" else
            replace(item, prior_setup_input_indices=(77,))
            if item.action is Action.CHORD else item
            for item in checked[index].mechanism_observations)
        checked = _set(checked, index, replace(
            checked[index], mechanism_observations=observations))
    return suite.aggregate_e1_suite(plan, archives, checked)


@contextmanager
def _blocked_execution():
    """A guard around NEW tests, separate from historical regression behavior."""
    boundaries = (
        (execution, "execute_scheduled_entry"),
        (execution, "_materialize_case"),
        (audit, "audit_scheduled_run"),
        (e1_evaluator, "evaluate_scheduled_kp0"),
        (e1_evaluator, "_fixed_answer"),
        (evaluator, "evaluate_falsification"),
        (benchmark_board, "generate_board"),
        (e1, "generate_board"),
        (core_engine.MinesweeperEngine, "__init__"),
        (core_engine.MinesweeperEngine, "step"),
        (oracles, "check_frozen_p8"),
        (oracles, "_scan_p8"),
        (harness, "execute_e0"),
    )
    with ExitStack() as stack:
        blocked = tuple(stack.enter_context(patch.object(
            module, name, side_effect=AssertionError("Forbidden research boundary: " + name)))
                        for module, name in boundaries)
        yield blocked
        for call in blocked:
            call.assert_not_called()


class QualificationCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = _record()

    def gates(self, result):
        return {gate.gate_id: gate.status for gate in result.gates}

    def execute_mocked(self, *, scheduled=None, evaluated=None, aggregate=None,
                       source_side_effect=None, construct_suite=False):
        record = self.record
        scheduled = record.scheduled_results if scheduled is None else scheduled
        evaluated = record.evaluator_results if evaluated is None else evaluated
        aggregate = _aggregate() if aggregate is None else aggregate
        log = []

        def scheduled_call(plan, index, envelope, **kwargs):
            log.append(("scheduled", index, kwargs))
            return scheduled[index]

        evaluated_iterator = iter(evaluated)

        def evaluated_call(admission, request, envelope, **kwargs):
            log.append(("evaluator", request.schedule_entry.schedule_index,
                        {**kwargs, "evaluation_run_id": request.evaluation_run_id}))
            e1_evaluator.validate_admitted_request(admission, request)
            return next(evaluated_iterator)

        with ExitStack() as stack:
            stack.enter_context(_blocked_execution())
            preflight = stack.enter_context(patch.object(
                qualification, "preflight_e1",
                return_value=qualification.E1Preflight("READY", ())))
            capture = stack.enter_context(patch.object(
                qualification, "capture_qualification_source_identity",
                **({"side_effect": source_side_effect} if source_side_effect is not None
                   else {"return_value": record.source_identity})))
            # Mock dispatch can finish within one Windows monotonic-clock tick.
            # Declare a deterministic whole-job span covering manual receipts.
            stack.enter_context(patch.object(
                qualification.time, "monotonic_ns", side_effect=(1_000_000_000, 2_000_000_000)))
            run = stack.enter_context(patch.object(
                operational, "supervise_scheduled_run", side_effect=scheduled_call))
            evaluate = stack.enter_context(patch.object(
                operational, "supervise_posthoc_evaluator", side_effect=evaluated_call))
            combine = stack.enter_context(patch.object(
                suite, "aggregate_e1_suite", **({"wraps": suite.aggregate_e1_suite}
                                              if construct_suite else {"return_value": aggregate})))
            result = qualification.execute_e1(
                run_id=record.run_id, plan=record.plan,
                envelope=record.operating_envelope, source_identity=record.source_identity,
                authorization_reference=record.authorization_reference)
        return result, run, evaluate, combine, capture, preflight, log


class FinalSourceIdentityTests(QualificationCase):
    def test_exact_current_operational_identity(self):
        self.assertEqual(self.record.source_identity.operational_source_identity,
                         operational.capture_operational_source_identity(self.record.plan))

    def test_exact_two_new_source_bytes_and_sizes(self):
        identity = self.record.source_identity
        paths = ("experiments/program_k_e1_qualification.py",
                 "experiments/program_k_e1_persistence.py")
        self.assertEqual(tuple(item.path for item in identity.files), paths)
        for item in identity.files:
            raw = (ROOT / item.path).read_bytes()
            self.assertEqual((item.sha256, item.size_bytes),
                             (hashlib.sha256(raw).hexdigest(), len(raw)))

    def test_frozen_authorities_preserved(self):
        for name in ("spec_sha256", "protocol_sha256", "model_id", "profile_sha256", "table_sha256"):
            self.assertEqual(getattr(self.record.source_identity, name),
                             getattr(self.record.plan.prerequisite, name))

    def test_identity_deterministic_and_immutable(self):
        again = qualification.capture_qualification_source_identity(self.record.plan)
        self.assertEqual(again, self.record.source_identity)
        self.assertEqual(again.digest, self.record.source_identity.digest)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            again.files = ()

    def test_test_sources_excluded(self):
        self.assertNotIn("test_program_k", repr(self.record.source_identity))

    def test_prospective_capture_does_not_need_archives_or_execution(self):
        with _blocked_execution(), patch.object(
                suite, "aggregate_e1_suite", side_effect=AssertionError("No archive required")):
            captured = qualification.capture_qualification_source_identity(self.record.plan)
        self.assertEqual(captured, self.record.source_identity)

    def test_both_new_source_byte_mutations_change_digest_without_writes(self):
        read = Path.read_bytes
        for filename in ("program_k_e1_qualification.py", "program_k_e1_persistence.py"):
            def altered(path, target=filename):
                raw = read(path)
                return raw + b"\n# manual in-memory identity probe\n" if path.name == target else raw
            with self.subTest(filename=filename), patch.object(Path, "read_bytes", altered):
                changed = qualification.capture_qualification_source_identity(self.record.plan)
            self.assertNotEqual(changed.digest, self.record.source_identity.digest)

    def test_slice5_byte_drift_is_rejected(self):
        read = Path.read_bytes
        for filename in ("program_k_e1_evaluator.py", "program_k_e1_operational.py"):
            def altered(path, target=filename):
                raw = read(path)
                return raw + b"\n# manual prior-slice drift\n" if path.name == target else raw
            with self.subTest(filename=filename), patch.object(Path, "read_bytes", altered):
                with self.assertRaises(ValueError):
                    qualification.capture_qualification_source_identity(self.record.plan)


class PreflightTests(QualificationCase):
    def preflight(self, **changes):
        values = dict(plan=self.record.plan, envelope=self.record.operating_envelope,
                      source_identity=self.record.source_identity,
                      run_id=self.record.run_id,
                      authorization_reference=self.record.authorization_reference)
        values.update(changes)
        with _blocked_execution(), patch.object(
                e1, "load_accepted_e0_prerequisite",
                return_value=self.record.plan.prerequisite) as accepted:
            result = qualification.preflight_e1(**values)
        return result, accepted

    def test_current_plan_envelope_source_auth_and_id_ready(self):
        result, accepted = self.preflight()
        self.assertEqual((result.status, result.reasons), ("READY", ()))
        accepted.assert_called_once()

    def test_blank_authorization_not_ready(self):
        for authorization in (None, "", " \n "):
            with self.subTest(authorization=authorization):
                self.assertEqual(self.preflight(authorization_reference=authorization)[0].status,
                                 "NOT_READY")

    def test_safe_local_run_id_required(self):
        for run_id in ("", "e1-", "../e1-outside", "e1-../x", "e1-x/y", "e1-x\\y",
                       "e1-x:y", "E1-uppercase-prefix", "e1-x.", "e1-a" + "b" * 100):
            with self.subTest(run_id=run_id):
                self.assertEqual(self.preflight(run_id=run_id)[0].status, "NOT_READY")

    def test_wrong_final_source_identity_not_ready(self):
        original = self.record.source_identity
        changed = replace(original, files=(
            replace(original.files[0], sha256="a" * 64), original.files[1]))
        self.assertEqual(self.preflight(source_identity=changed)[0].status, "NOT_READY")

    def test_wrong_plan_runtime_not_ready(self):
        plan = self.record.plan
        changed = _corrupt(plan, runtime=replace(plan.runtime, node="different-machine"))
        self.assertEqual(self.preflight(plan=changed)[0].status, "NOT_READY")

    def test_wrong_envelope_runtime_not_ready(self):
        self.assertEqual(self.preflight(
            envelope=replace(self.record.operating_envelope, runtime_identity="different"))[0].status,
            "NOT_READY")

    def test_envelope_numeric_contract_cannot_use_boolean(self):
        changed = _corrupt(self.record.operating_envelope, memory_cap_bytes=True)
        self.assertEqual(self.preflight(envelope=changed)[0].status, "NOT_READY")

    def test_plan_cannot_authorize_itself(self):
        changed = _corrupt(self.record.plan, actual_execution_authorized=True)
        self.assertEqual(self.preflight(plan=changed)[0].status, "NOT_READY")

    def test_plan_supplement_must_remain_not_evaluated(self):
        changed = _corrupt(self.record.plan, supplement_status="REQUIRED_PROSPECTIVE_A_E5")
        self.assertEqual(self.preflight(plan=changed)[0].status, "NOT_READY")

    def test_accepted_e0_prerequisite_mismatch_not_ready(self):
        wrong = _corrupt(self.record.plan.prerequisite, p8_evidence_digest="b" * 64)
        with _blocked_execution(), patch.object(e1, "load_accepted_e0_prerequisite", return_value=wrong):
            result = qualification.preflight_e1(
                self.record.plan, self.record.operating_envelope, self.record.source_identity,
                run_id=self.record.run_id, authorization_reference=self.record.authorization_reference)
        self.assertEqual(result.status, "NOT_READY")

    def test_prerequisite_reader_failure_not_ready(self):
        with patch.object(e1, "load_accepted_e0_prerequisite", side_effect=ValueError("changed E0")):
            result = qualification.preflight_e1(
                self.record.plan, self.record.operating_envelope, self.record.source_identity,
                run_id=self.record.run_id, authorization_reference=self.record.authorization_reference)
        self.assertEqual(result.status, "NOT_READY")

    def test_publication_preflight_checks_destination_read_only(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "results/program_k_research" / self.record.run_id
            result, _ = self.preflight(repository_root=directory)
            self.assertEqual(result.status, "READY")
            self.assertFalse(destination.parent.exists())
            destination.mkdir(parents=True)
            self.assertEqual(self.preflight(repository_root=directory)[0].status, "NOT_READY")

    def test_preflight_reasons_frozen(self):
        result, _ = self.preflight(authorization_reference="")
        self.assertIs(type(result.reasons), tuple)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            result.status = "READY"


class RecordContractTests(QualificationCase):
    def test_scheduled_exact_prefix_and_empty_record_are_admitted(self):
        for count in (0, 1, 7, 53, 54):
            with self.subTest(count=count):
                result = replace(self.record, scheduled_results=self.record.scheduled_results[:count],
                                 evaluator_results=())
                self.assertEqual(len(result.scheduled_results), count)

    def test_duplicate_reordered_and_skipped_schedule_results_rejected(self):
        original = self.record.scheduled_results
        variants = ((original[0], original[0]), (original[1], original[0]),
                    (original[0], original[2]))
        for changed in variants:
            with self.subTest(indices=tuple(r.receipt.schedule_index for r in changed)):
                with self.assertRaises(ValueError):
                    replace(self.record, scheduled_results=_rechain(changed), evaluator_results=())

    def test_evaluator_cannot_precede_complete_scheduled_family(self):
        with self.assertRaises(ValueError):
            replace(self.record, scheduled_results=self.record.scheduled_results[:53])

    def test_evaluator_prefix_must_follow_exact_kp0_order(self):
        original = self.record.evaluator_results
        used = self.record.scheduled_results[-1].receipt.archive_used_after_bytes
        for changed in ((original[1],), (original[0], original[0]), (original[1], original[0])):
            with self.subTest(indices=tuple(r.receipt.schedule_index for r in changed)):
                with self.assertRaises(ValueError):
                    replace(self.record, evaluator_results=_rechain(changed, used=used))

    def test_source_mismatch_rejected(self):
        first = self.record.scheduled_results[0]
        changed = replace(first, receipt=_receipt_change(
            first.receipt, operational_source_digest="c" * 64))
        with self.assertRaises(ValueError):
            replace(self.record, scheduled_results=(changed,), evaluator_results=())

    def test_envelope_mismatch_rejected(self):
        changed = replace(self.record.operating_envelope, rationale="Different declared envelope")
        with self.assertRaises(ValueError):
            replace(self.record, operating_envelope=changed)

    def test_archive_budget_gap_and_overlap_rejected(self):
        last = self.record.evaluator_results[-1]
        for delta in (-1, 1):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                receipt = _receipt_change(
                    last.receipt, archive_used_before_bytes=last.receipt.archive_used_before_bytes + delta)
                replace(self.record, evaluator_results=self.record.evaluator_results[:-1] + (
                    replace(last, receipt=receipt),))

    def test_archive_budget_starts_at_zero(self):
        first = self.record.scheduled_results[0]
        changed = replace(first, receipt=_receipt_change(first.receipt, archive_used_before_bytes=1))
        with self.assertRaises(ValueError):
            replace(self.record, scheduled_results=(changed,), evaluator_results=())

    def test_results_after_operational_hard_stop_rejected(self):
        original = self.record.scheduled_results
        stopped = replace(original[0], receipt=_receipt_change(
            original[0].receipt, status="INCOMPLETE", reason="SYSTEM_CASE_TIMEOUT"))
        with self.assertRaises(ValueError):
            replace(self.record, scheduled_results=_rechain((stopped, original[1])),
                    evaluator_results=())

    def test_results_after_audit_hard_stop_rejected(self):
        for status in ("FAIL", "INCOMPLETE"):
            original = self.record.scheduled_results
            stopped = _scheduled_change(
                original[0], checked=replace(
                    original[0].audit, audit_status=status,
                    discrepancies=("Manual semantic failure",) if status == "FAIL" else (),
                    incomplete_reasons=("Manual missing evidence",) if status == "INCOMPLETE" else ()))
            with self.subTest(status=status), self.assertRaises(ValueError):
                replace(self.record, scheduled_results=_rechain((stopped, original[1])),
                        evaluator_results=())

    def test_results_after_evaluator_falsification_rejected(self):
        prefix = _falsification(self.record)
        next_result = self.record.evaluator_results[len(prefix)]
        used = self.record.scheduled_results[-1].receipt.archive_used_after_bytes
        with self.assertRaises(ValueError):
            replace(self.record, evaluator_results=_rechain(prefix + (next_result,), used=used))

    def test_complete_abort_event_cannot_be_followed_by_another_result(self):
        for event in ("WORKER_ABORT", "SYSTEM_DECISION_TIMEOUT"):
            stopped = _abort_event(self.record.scheduled_results[0], event)
            with self.subTest(event=event), self.assertRaises(ValueError):
                replace(self.record, scheduled_results=_rechain((
                    stopped, self.record.scheduled_results[1])), evaluator_results=())

    def test_duplicate_finished_and_event_after_finished_are_rejected(self):
        original = self.record.scheduled_results[0]
        receipt = original.receipt
        final = receipt.events[-1]
        duplicated = replace(final, sequence=final.sequence + 1, elapsed_ns=final.elapsed_ns + 1)
        after = operational.E1MonitorEvent(
            final.sequence + 1, "WORKER_ABORT", final.elapsed_ns + 1,
            final.physical_inputs, "Manual event after FINISHED")
        for event, status, reason in ((duplicated, "COMPLETE", None),
                                      (after, "INCOMPLETE", "SYSTEM_PROCESS_ABORT")):
            changed = replace(original, receipt=_receipt_change(
                receipt, events=receipt.events + (event,), status=status, reason=reason))
            with self.subTest(event=event.event), self.assertRaises(ValueError):
                replace(self.record, scheduled_results=(changed,), evaluator_results=())

    def test_mutable_or_live_graph_rejected(self):
        for changed in ({"scheduled_results": list(self.record.scheduled_results)},
                        {"interruptions": ["mutable"]},
                        {"diagnosed_implementation_defects": (lambda: None,)}):
            with self.subTest(field=next(iter(changed))), self.assertRaises(ValueError):
                replace(self.record, **changed)

    def test_detached_graph_is_immutable_and_nonduplicative(self):
        self.assertFalse(any(field.name in ("suite", "suite_aggregate", "resource_summary", "resources")
                             for field in fields(self.record)))
        seen = set()
        def visit(item):
            if id(item) in seen:
                return
            seen.add(id(item))
            if item is None or type(item) in (str, int, bool, float, Fraction) or isinstance(item, Enum):
                return
            if type(item) in (tuple, frozenset):
                for child in item:
                    visit(child)
                return
            self.assertTrue(is_dataclass(item), type(item))
            self.assertTrue(item.__dataclass_params__.frozen)
            self.assertNotIn(type(item).__name__, ("HiddenAnswer", "BoardSnapshot", "MinesweeperEngine"))
            for field in fields(item):
                visit(getattr(item, field.name))
        visit(self.record)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            self.record.run_id = "e1-changed"


class ReconstructionTests(QualificationCase):
    def test_54_manual_results_reconstruct_exact_suite(self):
        rebuilt = qualification.reconstruct_e1_suite(self.record)
        self.assertEqual(suite._encoded(rebuilt), suite._encoded(_aggregate()))

    def test_manual_receipts_and_findings_reconstruct_resources(self):
        expected = operational.summarize_operational_resources(
            self.record.plan, _aggregate(),
            tuple(result.receipt for result in self.record.scheduled_results),
            self.record.evaluator_results)
        actual = qualification.reconstruct_e1_resources(self.record)
        self.assertEqual(actual, expected)
        self.assertEqual(actual.resource_status, "COMPLETE_CONTAINMENT_EVIDENCE")

    def test_partial_record_has_no_fake_complete_suite(self):
        partial = replace(self.record, scheduled_results=self.record.scheduled_results[:5],
                          evaluator_results=())
        with self.assertRaises(qualification.E1ReconstructionError):
            qualification.reconstruct_e1_suite(partial)
        self.assertEqual(qualification.assess_e1(partial).verdict, "INCOMPLETE")

    def test_reconstruction_performs_no_execution_audit_or_truth_generation(self):
        with _blocked_execution():
            qualification.reconstruct_e1_suite(self.record)
            qualification.reconstruct_e1_resources(self.record)

    def test_historical_reconstruction_does_not_read_current_source(self):
        with _blocked_execution(), patch.object(
                Path, "read_bytes", side_effect=AssertionError("Historical source read")):
            qualification.reconstruct_e1_suite(self.record)
            qualification.reconstruct_e1_resources(self.record)
            self.assertEqual(qualification.assess_e1(self.record).verdict, "E1_PASS")


class MockOrchestrationTests(QualificationCase):
    def test_live_phase_constructs_admits_and_hashes_once_before_18_compact_dispatches(self):
        phase = {"active": False, "dispatched": 0}
        whole_hashes, admissions = [], []
        content_digest = suite._content_digest
        admit = e1_evaluator._admit_constructed_suite
        validate = e1_evaluator.validate_admitted_request

        def digest(value):
            if phase["active"] and type(value) is suite.E1SuiteAggregate:
                whole_hashes.append(value)
                self.assertEqual(phase["dispatched"], 0, "Whole-suite hash during dispatch")
            return content_digest(value)

        def admission(plan, aggregate, *, run_id):
            phase["active"] = True
            admitted = admit(plan, aggregate, run_id=run_id)
            admissions.append(admitted)
            return admitted

        def target(admitted, request):
            self.assertEqual(len(admissions), 1)
            self.assertEqual(len(whole_hashes), 1)
            result = validate(admitted, request)
            phase["dispatched"] += 1
            if phase["dispatched"] == 18:
                # Record construction below is historical reconciliation, outside
                # the live evaluator phase, and still admits its retained graph.
                phase["active"] = False
            return result

        with patch.object(e1_evaluator, "require_complete_suite",
                          side_effect=AssertionError("Repeated whole-suite admission")), \
                patch.object(e1_evaluator, "_admit_constructed_suite", side_effect=admission), \
                patch.object(e1_evaluator, "validate_admitted_request", side_effect=target), \
                patch.object(suite, "_content_digest", side_effect=digest):
            result, run, evaluate, combine, *_ = self.execute_mocked(construct_suite=True)
        self.assertEqual((run.call_count, combine.call_count, len(admissions),
                          len(whole_hashes), evaluate.call_count), (54, 1, 1, 1, 18))
        self.assertEqual(result.evaluator_results, self.record.evaluator_results)

    def test_exact_54_scheduled_and_18_evaluator_calls_once(self):
        result, run, evaluate, combine, capture, preflight, log = self.execute_mocked()
        self.assertEqual(run.call_count, 54)
        self.assertEqual(evaluate.call_count, 18)
        self.assertEqual(combine.call_count, 1)
        self.assertEqual(tuple(item[1] for item in log[:54]), tuple(range(54)))
        expected = tuple(entry.schedule_index for entry in self.record.plan.schedule
                         if entry.variant == "K-P0")
        self.assertEqual(tuple(item[1] for item in log[54:]), expected)
        self.assertTrue(all(item[0] == "scheduled" for item in log[:54]))
        self.assertTrue(all(item[0] == "evaluator" for item in log[54:]))
        self.assertEqual(result.scheduled_results, self.record.scheduled_results)
        self.assertEqual(result.evaluator_results, self.record.evaluator_results)
        preflight.assert_called_once()
        self.assertGreaterEqual(capture.call_count, 1)

    def test_single_whole_job_start_and_exact_archive_budget_forwarding(self):
        result, run, evaluate, combine, capture, preflight, log = self.execute_mocked()
        self.assertEqual(len({item[2]["job_started_ns"] for item in log}), 1)
        operations = self.record.scheduled_results + self.record.evaluator_results
        self.assertEqual(tuple(item[2]["archive_used_bytes"] for item in log),
                         tuple(item.receipt.archive_used_before_bytes for item in operations))

    def test_evaluator_ids_deterministically_bind_run_and_index(self):
        result, run, evaluate, combine, capture, preflight, log = self.execute_mocked()
        self.assertEqual(tuple(item[2]["evaluation_run_id"] for item in log[54:]),
                         tuple(f"{self.record.run_id}-kp0-{item[1]:02d}" for item in log[54:]))

    def test_not_ready_preflight_prevents_all_dispatch(self):
        with patch.object(qualification, "preflight_e1",
                          return_value=qualification.E1Preflight("NOT_READY", ("No authorization",))), \
                patch.object(operational, "supervise_scheduled_run") as run, \
                patch.object(operational, "supervise_posthoc_evaluator") as evaluate:
            with self.assertRaises(ValueError):
                qualification.execute_e1(
                    run_id=self.record.run_id, plan=self.record.plan,
                    envelope=self.record.operating_envelope,
                    source_identity=self.record.source_identity,
                    authorization_reference=self.record.authorization_reference)
        run.assert_not_called()
        evaluate.assert_not_called()

    def test_operational_incomplete_stops_scheduled_dispatch_without_loss(self):
        first = self.record.scheduled_results[0]
        for reason in ("SYSTEM_CASE_TIMEOUT", "SYSTEM_JOB_TIMEOUT", "SYSTEM_INPUT_CAP",
                       "SYSTEM_MEMORY_CAP", "SYSTEM_ARCHIVE_CAP", "SYSTEM_PROCESS_ABORT"):
            stopped = replace(first, receipt=_receipt_change(first.receipt, status="INCOMPLETE",
                                                             reason=reason))
            with self.subTest(reason=reason):
                result, run, evaluate, combine, *_ = self.execute_mocked(scheduled=(stopped,))
                self.assertEqual(run.call_count, 1)
                evaluate.assert_not_called()
                combine.assert_not_called()
                self.assertEqual(result.scheduled_results, (stopped,))
                self.assertEqual(result.scheduled_results[0].archive.result.status, GameStatus.WON)
                self.assertEqual(qualification.assess_e1(result).verdict, "INCOMPLETE")

    def test_audit_fail_stops_and_diagnoses_implementation_defect(self):
        first = self.record.scheduled_results[0]
        stopped = _scheduled_change(first, checked=replace(
            first.audit, audit_status="FAIL", discrepancies=("Manual semantic fault",)))
        result, run, evaluate, combine, *_ = self.execute_mocked(scheduled=(stopped,))
        self.assertEqual(run.call_count, 1)
        evaluate.assert_not_called()
        combine.assert_not_called()
        self.assertTrue(result.diagnosed_implementation_defects)
        self.assertEqual(qualification.assess_e1(result).verdict, "IMPLEMENTATION_IDENTITY_FAIL")

    def test_audit_incomplete_stops_without_replacement(self):
        first = self.record.scheduled_results[0]
        stopped = _scheduled_change(first, checked=replace(
            first.audit, audit_status="INCOMPLETE", incomplete_reasons=("Manual missing proof",)))
        result, run, evaluate, combine, *_ = self.execute_mocked(scheduled=(stopped,))
        self.assertEqual(run.call_count, 1)
        evaluate.assert_not_called()
        combine.assert_not_called()
        self.assertEqual(qualification.assess_e1(result).verdict, "INCOMPLETE")

    def test_complete_lifecycle_missing_payload_is_diagnosed_and_stops(self):
        first = self.record.scheduled_results[0]
        stopped = operational.E1OperationResult(first.receipt)
        result, run, evaluate, combine, *_ = self.execute_mocked(scheduled=(stopped,))
        self.assertEqual(run.call_count, 1)
        evaluate.assert_not_called()
        combine.assert_not_called()
        self.assertTrue(result.diagnosed_implementation_defects)

    def test_complete_receipt_with_abort_event_stops_and_cannot_pass(self):
        for event in ("WORKER_ABORT", "SYSTEM_DECISION_TIMEOUT"):
            stopped = _abort_event(self.record.scheduled_results[0], event)
            with self.subTest(event=event):
                result, run, evaluate, combine, *_ = self.execute_mocked(scheduled=(stopped,))
                self.assertEqual(run.call_count, 1)
                evaluate.assert_not_called()
                combine.assert_not_called()
                self.assertEqual(qualification.assess_e1(result).verdict,
                                 "IMPLEMENTATION_IDENTITY_FAIL")

    def test_failed_suite_prevents_hidden_evaluator(self):
        failed = replace(_aggregate(), suite_status="FAIL", semantic_failures=("Manual cross-run fault",))
        result, run, evaluate, combine, *_ = self.execute_mocked(aggregate=failed)
        self.assertEqual(run.call_count, 54)
        combine.assert_called_once()
        evaluate.assert_not_called()
        self.assertTrue(result.diagnosed_implementation_defects)

    def test_incomplete_complete_family_can_dispatch_evaluators(self):
        aggregate = _mechanism_aggregate("MISSING")
        source = self.record.source_identity
        scheduled, evaluated = _operations(aggregate, source, self.record.operating_envelope)
        result, run, evaluate, combine, *_ = self.execute_mocked(
            scheduled=scheduled, evaluated=evaluated, aggregate=aggregate)
        self.assertEqual((run.call_count, evaluate.call_count, combine.call_count), (54, 18, 1))
        self.assertEqual(qualification.assess_e1(result).readiness, "E1_A_E5_REQUIRED")

    def test_evaluator_operational_incomplete_stops_without_retry(self):
        first = self.record.evaluator_results[0]
        stopped = replace(first, receipt=_receipt_change(
            first.receipt, status="INCOMPLETE", reason="SYSTEM_PROCESS_ABORT"))
        result, run, evaluate, combine, *_ = self.execute_mocked(evaluated=(stopped,))
        self.assertEqual((run.call_count, evaluate.call_count), (54, 1))
        self.assertEqual(len(result.evaluator_results), 1)
        self.assertEqual(qualification.assess_e1(result).verdict, "INCOMPLETE")

    def test_complete_evaluator_missing_finding_is_diagnosed(self):
        stopped = operational.E1OperationResult(self.record.evaluator_results[0].receipt)
        result, run, evaluate, combine, *_ = self.execute_mocked(evaluated=(stopped,))
        self.assertEqual(evaluate.call_count, 1)
        self.assertTrue(result.diagnosed_implementation_defects)

    def test_g1_falsification_stops_exact_evaluator_prefix(self):
        prefix = _falsification(self.record)
        result, run, evaluate, combine, *_ = self.execute_mocked(evaluated=prefix)
        self.assertEqual(evaluate.call_count, len(prefix))
        self.assertEqual(result.evaluator_results, prefix)
        self.assertEqual(qualification.assess_e1(result).verdict, "IMPLEMENTATION_IDENTITY_FAIL")

    def test_source_recapture_drift_is_failure_and_stops(self):
        original = self.record.source_identity
        drifted = replace(original, files=(
            replace(original.files[0], sha256="d" * 64), original.files[1]))
        calls = []
        def source(plan):
            calls.append(plan)
            return original if len(calls) == 1 else drifted
        result, run, evaluate, combine, capture, *_ = self.execute_mocked(source_side_effect=source)
        self.assertGreaterEqual(capture.call_count, 2)
        self.assertTrue(result.diagnosed_implementation_defects)
        self.assertEqual(qualification.assess_e1(result).verdict, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertLessEqual(run.call_count, 54)
        self.assertLessEqual(evaluate.call_count, 18)


class GateAssessmentTests(QualificationCase):
    def test_complete_manual_evidence_has_exact_e1_gates(self):
        assessment = qualification.assess_e1(self.record)
        expected = {f"G{number}": "PASS" for number in range(1, 11)}
        expected["G8"] = "NOT_APPLICABLE"
        self.assertEqual(self.gates(assessment), expected)
        self.assertEqual((assessment.verdict, assessment.readiness, assessment.progression_allowed),
                         ("E1_PASS", "E1_QUALIFIED", True))

    def test_public_semantic_failure_precedes_incomplete(self):
        first = self.record.scheduled_results[0]
        failed = _scheduled_change(first, checked=replace(
            first.audit, audit_status="FAIL", discrepancies=("Manual semantic fault",)))
        record = replace(self.record, scheduled_results=(failed,), evaluator_results=())
        assessment = qualification.assess_e1(record)
        self.assertEqual(assessment.verdict, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertFalse(assessment.progression_allowed)

    def test_evaluator_falsification_cannot_be_public_proof(self):
        assessment = qualification.assess_e1(replace(
            self.record, evaluator_results=_falsification(self.record)))
        self.assertEqual(assessment.verdict, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertEqual(self.gates(assessment)["G1"], "FAIL")

    def test_missing_mechanism_alone_requires_prospective_a_e5(self):
        record = _record(aggregate=_mechanism_aggregate("MISSING"))
        assessment = qualification.assess_e1(record)
        expected = {f"G{number}": "PASS" for number in range(1, 11)}
        expected.update(G5="INCOMPLETE", G8="NOT_APPLICABLE")
        self.assertEqual(self.gates(assessment), expected)
        self.assertEqual((assessment.verdict, assessment.readiness, assessment.progression_allowed),
                         ("INCOMPLETE", "E1_A_E5_REQUIRED", False))

    def test_invalid_mechanism_is_implementation_failure(self):
        record = _record(aggregate=_mechanism_aggregate("INVALID"))
        assessment = qualification.assess_e1(record)
        self.assertEqual(assessment.verdict, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertEqual(self.gates(assessment)["G5"], "FAIL")

    def test_resource_incomplete_does_not_qualify(self):
        partial = replace(self.record, evaluator_results=self.record.evaluator_results[:-1])
        assessment = qualification.assess_e1(partial)
        self.assertEqual((assessment.verdict, assessment.readiness, assessment.progression_allowed),
                         ("INCOMPLETE", "NOT_QUALIFIED", False))
        self.assertEqual(self.gates(assessment)["G9"], "INCOMPLETE")

    def test_wl_and_lw_are_implementation_failure(self):
        for control, kp0 in ((GameStatus.WON, GameStatus.LOST), (GameStatus.LOST, GameStatus.WON)):
            plan, archives, checked = _data()
            for variant, status in (("CONTROL", control), ("K-CONTROL", control), ("K-P0", kp0)):
                for repetition in (1, 2):
                    index = _index(case="S-WIN", variant=variant, repetition=repetition)
                    archive = replace(archives[index], result=_declared_result(
                        archives[index].case, variant, status=status))
                    archives = _set(archives, index, archive)
                    checked = _set(checked, index, _bind_p3(archive, checked[index]))
            aggregate = suite.aggregate_e1_suite(plan, archives, checked)
            with self.subTest(control=control, kp0=kp0):
                assessment = qualification.assess_e1(_record(aggregate=aggregate))
                self.assertEqual(assessment.verdict, "IMPLEMENTATION_IDENTITY_FAIL")
                self.assertEqual(self.gates(assessment)["G7"], "FAIL")

    def test_truthful_out_of_envelope_oracle_a_not_evaluated_can_pass_g2(self):
        plan, archives, checked = _data()
        for repetition in (1, 2):
            index = _index(repetition=repetition)
            original = checked[index]
            oracle = replace(
                original.oracle_a_audits[0],
                coverage=harness.OracleCoverage("ORACLE_A_NOT_EVALUATED", 17, 16,
                                                "Declared beyond bounded enumeration"),
                result=None, status="NOT_EVALUATED")
            checked = _set(checked, index, replace(
                original, oracle_a_audits=(oracle,), oracle_calls=(),
                oracle_spans=()))
        aggregate = suite.aggregate_e1_suite(plan, archives, checked)
        assessment = qualification.assess_e1(_record(aggregate=aggregate))
        self.assertEqual(self.gates(assessment)["G2"], "PASS")

    def test_oracle_a_pass_without_retained_result_or_coverage_fails(self):
        last = self.record.scheduled_results[-1]
        original = last.audit.oracle_a_audits[0]
        for changes in ({"result": None}, {"coverage": None}, {"result": None, "coverage": None}):
            checked = replace(last.audit, oracle_a_audits=(replace(original, **changes),))
            updated = _scheduled_change(last, checked=checked)
            record = replace(self.record, scheduled_results=self.record.scheduled_results[:-1] + (updated,),
                             evaluator_results=())
            with self.subTest(changes=changes):
                assessment = qualification.assess_e1(record)
                self.assertEqual(self.gates(assessment)["G2"], "FAIL")
                self.assertEqual(assessment.verdict, "IMPLEMENTATION_IDENTITY_FAIL")

    def test_whole_job_elapsed_must_cover_receipts_and_stay_below_cap(self):
        receipt_total = sum(result.receipt.elapsed_ns for result in
                            self.record.scheduled_results + self.record.evaluator_results)
        cap = self.record.operating_envelope.max_job_wall_ms * 1_000_000
        for elapsed in (receipt_total - 1, cap, cap + 1):
            with self.subTest(elapsed=elapsed):
                assessment = qualification.assess_e1(replace(self.record, elapsed_ns=elapsed))
                self.assertEqual(self.gates(assessment)["G9"], "INCOMPLETE")
                self.assertEqual(assessment.verdict, "INCOMPLETE")
                self.assertFalse(assessment.progression_allowed)

    def test_posthoc_evaluator_zero_eligible_not_evaluated_is_separate_public_coverage(self):
        classifications = tuple(result.evaluation.classification for result in self.record.evaluator_results)
        self.assertIn("NOT_EVALUATED", classifications)
        self.assertIn("NO_COUNTEREXAMPLE", classifications)
        vacuous = tuple(result for result in self.record.evaluator_results
                        if result.evaluation.classification == "NOT_EVALUATED")
        self.assertEqual(tuple((result.receipt.case_id, result.receipt.repetition)
                               for result in vacuous if result.receipt.case_id == "S-WIN"),
                         (("S-WIN", 1), ("S-WIN", 2)))
        for result in vacuous:
            self.assertEqual(result.evaluation.finding.evaluated_coordinate_count, 0)
            self.assertEqual(result.evaluation.evaluator_calls[0].evaluated_coordinate_count, 0)
            self.assertIsNone(qualification._operation_stop(result))
        self.assertTrue(all(result.evaluation.proof_upgrade_allowed is False
                            for result in self.record.evaluator_results))
        self.assertEqual(qualification.assess_e1(self.record).verdict, "E1_PASS")

    def test_explicit_diagnosed_defect_precedes_other_gates(self):
        changed = replace(self.record, diagnosed_implementation_defects=("Manual source drift",))
        self.assertEqual(qualification.assess_e1(changed).verdict, "IMPLEMENTATION_IDENTITY_FAIL")

    def test_assessment_is_historical_and_read_only(self):
        with _blocked_execution(), patch.object(
                qualification, "capture_qualification_source_identity",
                side_effect=AssertionError("Historical final source capture")), patch.object(
                Path, "read_bytes", side_effect=AssertionError("Historical bytes")):
            assessment = qualification.assess_e1(self.record)
        self.assertEqual(assessment.verdict, "E1_PASS")

    def test_no_research_pass_or_effectiveness_acceptance_field(self):
        assessment = qualification.assess_e1(self.record)
        self.assertNotIn("RESEARCH_PASS", repr(assessment))
        for value in (self.record, assessment):
            for field in fields(value):
                self.assertNotIn(field.name, ("research_verdict", "effectiveness_accepted",
                                              "program_k_research_verdict"))
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            assessment.verdict = "RESEARCH_PASS"


class ExternalFlagGateTests(QualificationCase):
    """Gate wiring over real public R-1 evidence, without a scheduled run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A public corner 1-of-3 clue plus total 17 forces the 16 other
        # cells to mines. Nineteen HIDDEN variables exceed bounded Oracle A.
        observation = ((1,) + (CellState.HIDDEN,) * 9,
                       (CellState.HIDDEN,) * 10)
        with _blocked_execution():
            result = audit_fixtures._public_result(
                "K-CONTROL", 10, 2, 17, (observation,))
            trace = result.traces[1]
            premises = audit._PhysicalFlagPremises(cls.record.plan.prerequisite)
            findings = audit._Findings()
            with oracles.collect_oracle_diagnostics() as calls:
                cls.action = audit._v1_action(
                    trace, trace.public_effect, 1, "K-CONTROL", 17, (),
                    findings, premises=premises, calls=calls, spans=[])
        if cls.action.status != "PASS":
            raise AssertionError(cls.action.detail)

    def retained(self, action=None, *, status="PASS"):
        # Only the per-action gate and hard-stop are exercised. This is not a
        # constructed complete-game audit or a synthetic E1 qualification.
        checked = replace(
            self.record.scheduled_results[0].audit,
            v1_audits=(self.action if action is None else action,),
            audit_status=status,
            discrepancies=("Declared FLAG qualification failure",) if status == "FAIL" else (),
            incomplete_reasons=("Declared FLAG qualification missing",)
            if status == "INCOMPLETE" else ())
        return checked

    def test_above16_raw_not_evaluated_with_valid_e1_basis_does_not_stop(self):
        action = self.action
        qualified = action.external_qualification
        self.assertEqual(action.external_verification.status, "NOT_EVALUATED")
        self.assertEqual(qualified.status, "PASS")
        self.assertEqual(qualified.shared_kernel_evidence,
                         "SHARED-KERNEL REPRESENTATION EVIDENCE")
        self.assertFalse(qualified.independent_bounded_enumeration_ran)
        checked = self.retained()
        self.assertEqual(qualification._external_flag_findings(
            (checked,), self.record.plan.prerequisite), ([], []))
        self.assertIsNone(qualification._operation_stop(_scheduled_change(
            self.record.scheduled_results[0], checked=checked)))

    def test_missing_e1_external_flag_qualification_is_incomplete_and_stops(self):
        checked = self.retained(
            replace(self.action, external_qualification=None), status="INCOMPLETE")
        failed, missing = qualification._external_flag_findings(
            (checked,), self.record.plan.prerequisite)
        self.assertFalse(failed)
        self.assertTrue(missing)
        self.assertEqual(qualification._operation_stop(_scheduled_change(
            self.record.scheduled_results[0], checked=checked)), "PUBLIC_AUDIT_INCOMPLETE")

    def test_failed_external_flag_qualification_is_failure_and_stops(self):
        qualified = replace(self.action.external_qualification, status="FAIL",
                            detail="Declared shared-kernel mismatch")
        checked = self.retained(
            replace(self.action, external_qualification=qualified), status="FAIL")
        failed, missing = qualification._external_flag_findings(
            (checked,), self.record.plan.prerequisite)
        self.assertTrue(failed)
        self.assertFalse(missing)
        self.assertEqual(qualification._operation_stop(_scheduled_change(
            self.record.scheduled_results[0], checked=checked)), "PUBLIC_AUDIT_FAIL")

    def test_external_flag_accepted_e0_binding_cannot_be_replaced(self):
        original = self.action.external_qualification
        for prerequisite in (
                None, _corrupt(original.prerequisite, source_digest="0" * 64)):
            checked = self.retained(replace(
                self.action, external_qualification=replace(
                    original, prerequisite=prerequisite)))
            with self.subTest(prerequisite=prerequisite is None):
                failed, _ = qualification._external_flag_findings(
                    (checked,), self.record.plan.prerequisite)
                self.assertTrue(failed)

    def test_external_flag_action_and_raw_independent_result_bindings_are_exact(self):
        for action in (
                replace(self.action, input_index=self.action.input_index + 1),
                replace(self.action, external_verification=replace(
                    self.action.external_verification, status="PASS"))):
            with self.subTest(index=action.input_index,
                              raw=action.external_verification.status):
                failed, _ = qualification._external_flag_findings(
                    (self.retained(action),), self.record.plan.prerequisite)
                self.assertTrue(failed)


class QualificationPurityTests(unittest.TestCase):
    def test_cold_manual_fixture_initialization_never_generates_frozen_cases(self):
        with _blocked_execution(), patch.object(
                e1, "_seal_fixed_cases", side_effect=AssertionError("No frozen case sealing")), \
                patch.object(audit_fixtures, "_PLAN", None), \
                patch.object(suite_fixtures, "_DATA", None), \
                patch.object(operational_fixtures, "_AGGREGATE", None), \
                patch.object(operational_fixtures, "_RESOURCE_DATA", None), \
                patch.dict(_MANUAL, {}, clear=True):
            record = _record()
        self.assertEqual((len(record.scheduled_results), len(record.evaluator_results)), (54, 18))

    def test_orchestrator_never_persists_automatically(self):
        tree = ast.parse(inspect.getsource(qualification.execute_e1))
        forbidden = {"persist_e1_qualification", "write_text", "write_bytes", "mkdir", "open"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                self.assertNotIn(name, forbidden)

    def test_no_other_stage_corpus_or_supplement_execution(self):
        tree = ast.parse(inspect.getsource(qualification))
        forbidden = {"execute_e0", "run_e0", "execute_e2", "execute_e3", "select_supplement",
                     "read_official_database", "read_zini", "check_frozen_p8", "_scan_p8",
                     "generate_board", "evaluate_falsification", "execute_scheduled_entry"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                self.assertNotIn(name, forbidden)

    def test_orchestration_accepts_no_case_schedule_answer_or_variant_override(self):
        parameters = inspect.signature(qualification.execute_e1).parameters
        self.assertEqual(set(parameters), {
            "run_id", "plan", "envelope", "source_identity", "authorization_reference"})


if __name__ == "__main__":
    unittest.main()
