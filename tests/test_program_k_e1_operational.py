"""Slice-5 containment tests; no frozen E1 scheduled action is executed.

The 54 metadata-bound archives below are the existing Slice-4 manual records.
All real process work is a test-only NOOP: no Engine, board or solver exists in
that child. Dispatch tests replace the execution and evaluator boundaries.
"""

import ast
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import inspect
import multiprocessing
from pathlib import Path
import pickle
import platform
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import core_engine
from experiments import program_k_e1_audit as audit
from experiments import program_k_e1_execution as execution
from experiments import program_k_e1_evaluator as e1_evaluator
from experiments import program_k_e1_harness as e1
from experiments import program_k_e1_operational as operational
from experiments import program_k_e1_suite as suite
from experiments import program_k_harness as harness
from experiments import program_k_evaluator as evaluator
from tests.test_program_k_e1_audit import _corrupt
from tests.test_program_k_e1_suite import _data
from tests.test_program_k_e1_suite import _manual_audit


ROOT = Path(__file__).resolve().parents[1]
_AGGREGATE = None
_ADMISSION = None
_RESOURCE_DATA = None


def _aggregate():
    global _AGGREGATE
    if _AGGREGATE is None:
        _AGGREGATE = suite.aggregate_e1_suite(*_data())
    return _AGGREGATE


def _admission():
    global _ADMISSION
    if _ADMISSION is None:
        aggregate = _aggregate()
        _ADMISSION = e1_evaluator.admit_evaluator_phase(
            aggregate.plan, aggregate, run_id="e1-operational-unit")
    return _ADMISSION


def _envelope(**changes):
    values = dict(
        runtime_identity=platform.platform(), machine_identity=platform.node(),
        python_identity=sys.version, max_decision_wall_ms=1000,
        max_case_wall_ms=30000, max_job_wall_ms=120000,
        shadow_timeout_ms=1000, max_physical_inputs_per_case=1000,
        memory_cap_bytes=2_000_000_000, archive_cap_bytes=100_000_000,
        monitor_interval_ms=10,
        monitoring_policy="WINDOWS_JOB_MEMORY_AND_STACK_SAMPLING_WATCHDOG_V1",
        rationale="Explicit isolated Slice-5 containment unit-test envelope.")
    values.update(changes)
    return harness.OperatingEnvelope(**values)


def _dummy_decision_frame():
    """A fixed NON-E1 code identity, sampled without running a solver."""
    return sys._getframe()


def _other_frame():
    return sys._getframe()


def _blocked_non_e1_decision(ready, release):
    ready.set()
    release.wait(2)


def _noop_worker(kind, request, identity, envelope, connection, barrier):
    """Top-level spawn target; containment lifecycle only, no research work."""
    barrier.wait()
    channel = operational._WorkerChannel(connection, envelope)
    channel.event("STARTED")
    channel.finish((None, None, None))
    connection.close()


def _bounded_compact_worker(kind, request, identity, envelope, connection, barrier):
    """Spawn-only unit seam: fabricated answers, never any fixed research layout."""
    import benchmark_board
    encoded, digest = suite._encoded, suite._content_digest

    def reject_whole(value, operation, *args, **kwargs):
        if type(value) is suite.E1SuiteAggregate:
            raise AssertionError("Whole suite crossed the compact worker boundary")
        return operation(value, *args, **kwargs)

    def fabricated_answer(case, sealed):
        # Construct an explicitly invented unit answer only after the production
        # worker has passed its Job barrier and source/request authentication.
        cells = tuple((x, y) for y in range(case.height) for x in range(case.width)
                      if (x, y) != (0, 0))[:case.num_mines]
        return evaluator.HiddenAnswer(
            sealed.case_id, sealed.run_id, sealed.width, sealed.height,
            frozenset(cells), sealed.archive_digest, case.num_mines)

    with ExitStack() as stack:
        for owner, name in ((suite, "aggregate_e1_suite"),
                            (e1_evaluator, "require_complete_suite"),
                            (benchmark_board, "generate_board"),
                            (execution, "execute_scheduled_entry"),
                            (core_engine.MinesweeperEngine, "__init__"),
                            (core_engine.MinesweeperEngine, "step")):
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
        stack.enter_context(patch.object(
            suite, "_encoded", side_effect=lambda v, *a, **k: reject_whole(v, encoded, *a, **k)))
        stack.enter_context(patch.object(
            suite, "_content_digest", side_effect=lambda v, *a, **k: reject_whole(v, digest, *a, **k)))
        stack.enter_context(patch.object(e1_evaluator, "_fixed_answer", side_effect=fabricated_answer))
        operational._worker_main(kind, request, identity, envelope, connection, barrier)


def _manual_evaluation(aggregate, binding, *, falsification=False, evaluation_run_id=None):
    """Declare evaluator records from public assertions, never an actual answer."""
    run_id = ("slice5-manual-evaluator-" + str(binding.schedule_entry.schedule_index)
              if evaluation_run_id is None else evaluation_run_id)
    sealed = e1_evaluator._seal(binding, run_id)
    answer_digest = "1" * 64
    findings = []
    changed = False
    for assertion in sealed.assertions:
        comparisons = []
        if assertion.assertion_type not in evaluator.EXCLUDED_ASSERTION_TYPES:
            asserted_mine = assertion.assertion_type == "LOGICAL_M"
            for coordinate in assertion.coordinates:
                hidden_mine = asserted_mine
                if falsification and not changed:
                    hidden_mine = not asserted_mine
                    changed = True
                comparisons.append(evaluator.CoordinateComparison(
                    coordinate, asserted_mine, hidden_mine))
        findings.append(evaluator.AssertionFinding(assertion, tuple(comparisons)))
    result = evaluator.FalsificationResult(sealed, answer_digest, tuple(findings))
    diagnostic = evaluator.EvaluatorCallDiagnostic(
        0, 47, sealed.assertions_digest, answer_digest, result.classification,
        result.evaluated_coordinate_count, None)
    source = Path(e1_evaluator.__file__).read_bytes()
    return e1_evaluator.E1EvaluatorFinding(
        binding.schedule_entry.schedule_index, binding.case.case_id,
        binding.schedule_entry.repetition, "K-P0", run_id,
        aggregate.source_identity.digest, suite._content_digest(aggregate),
        aggregate.plan_identity, binding.archive_content_digest,
        binding.case.board_fingerprint, sealed.archive_digest, answer_digest,
        hashlib.sha256(source).hexdigest(), len(source), result, (diagnostic,))


def _manual_receipt(entry, identity, payload, *, physical_inputs=0,
                    kind="SCHEDULED_RUN", envelope=None, used=0):
    envelope = _envelope() if envelope is None else envelope
    events = [operational.E1MonitorEvent(0, "JOB_ATTACHED", 0, 0),
              operational.E1MonitorEvent(1, "STARTED", 1, 0)]
    for count in range(1, physical_inputs + 1):
        events.append(operational.E1MonitorEvent(
            len(events), "BEFORE_INPUT", len(events), count))
    events.append(operational.E1MonitorEvent(
        len(events), "FINISHED", len(events), physical_inputs))
    encoded = operational._payload_bytes(payload)
    memory = harness.MemoryEvidence(100, 200, 3, 1000, envelope.memory_cap_bytes)
    operation_id = f"{kind}:{entry.schedule_index:02d}"
    if payload[2] is not None:
        operation_id += ":" + payload[2].evaluation_run_id
    return operational._make_receipt(
        operation_kind=kind, operation_id=operation_id,
        schedule_index=entry.schedule_index, case_id=entry.case_id,
        repetition=entry.repetition, variant=entry.variant,
        operational_source_digest=identity.digest,
        envelope_digest=harness.content_digest(envelope),
        status="COMPLETE", reason=None, events=tuple(events),
        elapsed_ns=len(events) + 50, physical_inputs=physical_inputs,
        result_digest=hashlib.sha256(encoded).hexdigest(), result_size_bytes=len(encoded),
        exit_code=0, memory_evidence=memory,
        monitoring_policy=operational.MONITORING_POLICY,
        monitoring_context=operational.MONITORING_CONTEXT,
        monitor_interval_ms=envelope.monitor_interval_ms,
        archive_used_before_bytes=used, archive_result_bytes=len(encoded),
        archive_used_after_bytes=used + len(encoded), envelope=envelope)


def _receipt_change(receipt, **changes):
    values = {field.name: getattr(receipt, field.name) for field in fields(receipt)}
    values.update(changes)
    return operational._make_receipt(**values)


def _receipt_reaccount(receipt, *, used):
    """Test-only byte accounting, preserving deliberately corrupted fields."""
    value = _corrupt(receipt, archive_used_before_bytes=used)
    charge = operational._receipt_archive_charge(value)
    return _corrupt(
        value, archive_receipt_bytes=charge,
        archive_used_after_bytes=used + value.archive_result_bytes + charge)


def _resource_data():
    global _RESOURCE_DATA
    if _RESOURCE_DATA is None:
        aggregate = _aggregate()
        identity = operational.capture_operational_source_identity(aggregate.plan)
        scheduled, evaluations = [], []
        used = 0
        for binding in aggregate.bindings:
            receipt = _manual_receipt(
                binding.schedule_entry, identity, (binding.archive, binding.audit, None),
                physical_inputs=len(binding.archive.result.traces), used=used)
            scheduled.append(receipt)
            used = receipt.archive_used_after_bytes
        for binding in aggregate.bindings:
            if binding.schedule_entry.variant != "K-P0":
                continue
            finding = _manual_evaluation(aggregate, binding)
            receipt = _manual_receipt(
                binding.schedule_entry, identity, (None, None, finding),
                kind="POST_HOC_EVALUATOR", used=used)
            evaluations.append(operational.E1OperationResult(receipt, evaluation=finding))
            used = receipt.archive_used_after_bytes
        _RESOURCE_DATA = tuple(scheduled), tuple(evaluations)
    return _RESOURCE_DATA


class _FakeConnection:
    def __init__(self, messages=()):
        self.messages = iter(messages)
        self.closed = threading.Event()
        self.acknowledgments = []

    def recv_bytes(self, maxlength):
        try:
            return next(self.messages)
        except StopIteration:
            self.closed.wait(2)
            raise EOFError("test IPC closed")

    def send_bytes(self, data):
        self.acknowledgments.append(data)

    def close(self):
        self.closed.set()


class _FakeProcess:
    def __init__(self, log, *, aborted=False, finish=False):
        self.log, self.aborted, self.finish = log, aborted, finish
        self.pid = self.exitcode = None
        self.alive = False

    def start(self):
        self.log.append("spawn")
        self.pid = 123
        self.alive = not self.aborted
        self.exitcode = 7 if self.aborted else None

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.log.append("join")
        if self.finish:
            self.alive, self.exitcode = False, 0

    def terminate(self):
        self.log.append("terminate")
        self.alive, self.exitcode = False, 1

    def kill(self):
        self.log.append("kill")
        self.alive, self.exitcode = False, 1


def _result_messages(payload, physical_inputs=0, *, corrupt_digest=False):
    canonical = operational._payload_bytes(payload)
    wire = pickle.dumps(payload, protocol=5)
    metadata = (len(wire), hashlib.sha256(wire).hexdigest(), len(canonical),
                "0" * 64 if corrupt_digest else hashlib.sha256(canonical).hexdigest())
    messages = [("STARTED", None)] + [("BEFORE_INPUT", None)] * physical_inputs
    messages.append(("RESULT_STARTED", metadata))
    messages.extend(("RESULT_CHUNK", wire[offset:offset + operational._CHUNK_SIZE])
                    for offset in range(0, len(wire), operational._CHUNK_SIZE))
    messages.append(("FINISHED", None))
    return tuple(pickle.dumps(message, protocol=5) for message in messages)


class SourceIdentityTests(unittest.TestCase):
    def test_prospective_source_capture_needs_no_archive_or_execution(self):
        plan = _data()[0]
        with ExitStack() as stack:
            blocked = [
                stack.enter_context(patch.object(module, name, side_effect=AssertionError(name)))
                for module, name in (
                    (execution, "execute_scheduled_entry"),
                    (audit, "audit_scheduled_run"),
                    (audit, "capture_audit_source_identity"),
                    (suite, "capture_suite_source_identity"))]
            identity = operational.capture_operational_source_identity(plan)
        self.assertIsNotNone(identity)
        for call in blocked:
            call.assert_not_called()

    def test_exact_current_slice_one_through_four_chain(self):
        plan, archives, audits = _data()
        identity = operational.capture_operational_source_identity(plan)
        self.assertEqual(identity.plan_source_identity, plan.source_identity)
        self.assertEqual(identity.execution_source_identity,
                         execution.capture_execution_source_identity(plan))
        self.assertEqual(identity.audit_source_identity,
                         audit.capture_audit_source_identity(plan, archives[0]))
        self.assertEqual(identity.suite_source_identity,
                         suite.capture_suite_source_identity(plan, archives[0], audits[0]))
        self.assertEqual(identity.audit_source_identity.digest,
                         "b6cc2964e3b75b5d85889b9d69957ede6cf1789fb5d511618bbd747e36a5b211")
        self.assertEqual(identity.suite_source_identity.digest,
                         "edd1943499bfecdedb3a64fca2489db58ffb84593651dd61cde04266e875ff24")

    def test_evaluator_and_operational_exact_bytes_and_sizes(self):
        identity = operational.capture_operational_source_identity(_data()[0])
        for item, relative in (
                (identity.evaluator_file, "experiments/program_k_e1_evaluator.py"),
                (identity.operational_file, "experiments/program_k_e1_operational.py")):
            raw = (ROOT / relative).read_bytes()
            self.assertEqual(item.path, relative)
            self.assertEqual(item.sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual(item.size_bytes, len(raw))

    def test_identity_is_deterministic_and_frozen(self):
        first = operational.capture_operational_source_identity(_data()[0])
        second = operational.capture_operational_source_identity(_data()[0])
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            first.files = ()

    def test_no_test_file_participates_in_runtime_identity(self):
        identity = operational.capture_operational_source_identity(_data()[0])
        self.assertNotIn("test_program_k", repr(identity))

    def test_source_byte_drift_changes_operational_identity(self):
        original = operational.capture_operational_source_identity(_data()[0])
        read = Path.read_bytes
        for filename in ("program_k_e1_evaluator.py", "program_k_e1_operational.py"):
            def altered(path, target=filename):
                data = read(path)
                return data + b"\n# in-memory identity test\n" if path.name == target else data
            with self.subTest(filename=filename), patch.object(Path, "read_bytes", altered):
                changed = operational.capture_operational_source_identity(_data()[0])
            self.assertNotEqual(original.digest, changed.digest)

    def test_compact_source_validation_binds_every_current_source_and_runtime(self):
        plan = _data()[0]
        original = operational.capture_operational_source_identity(plan)
        self.assertEqual(operational.require_evaluator_source_identity(original, plan.runtime), original)
        read = Path.read_bytes
        for filename in ("program_k_e1_evaluator.py", "program_k_e1_operational.py",
                         "program_k_e1_harness.py", "benchmark_board.py",
                         "program_k_e1_execution.py", "program_k_e1_audit.py",
                         "program_k_e1_suite.py", "program_k_capability.py"):
            def altered(path, target=filename):
                raw = read(path)
                return raw + b"\n# compact source drift probe\n" if path.name == target else raw
            with self.subTest(filename=filename), patch.object(Path, "read_bytes", altered):
                with self.assertRaises(ValueError):
                    operational.require_evaluator_source_identity(original, plan.runtime)
        with self.assertRaises(ValueError):
            operational.require_evaluator_source_identity(original, replace(plan.runtime, node="stale"))

    def test_prior_slice_byte_drift_is_rejected(self):
        read = Path.read_bytes
        for filename in ("program_k_e1_harness.py", "program_k_e1_execution.py",
                         "program_k_e1_audit.py", "program_k_e1_suite.py"):
            def altered(path, target=filename):
                data = read(path)
                return data + b"\n# in-memory previous-slice drift\n" if path.name == target else data
            with self.subTest(filename=filename), patch.object(Path, "read_bytes", altered):
                with self.assertRaises(ValueError):
                    operational.capture_operational_source_identity(_data()[0])

    def test_exact_plan_class_required(self):
        with self.assertRaises(ValueError):
            operational.capture_operational_source_identity(SimpleNamespace(**{}))


class EnvelopeTests(unittest.TestCase):
    def test_exact_existing_envelope_and_current_runtime_accepted(self):
        envelope = _envelope()
        self.assertEqual(operational.require_operating_envelope(envelope), envelope)

    def test_arbitrary_or_subclass_envelope_rejected(self):
        class ExtendedEnvelope(harness.OperatingEnvelope):
            pass
        valid = _envelope()
        for value in (None, SimpleNamespace(**vars(valid)),
                      ExtendedEnvelope(**vars(valid))):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                operational.require_operating_envelope(value)

    def test_runtime_machine_and_python_mismatch_rejected(self):
        for name in ("runtime_identity", "machine_identity", "python_identity"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                operational.require_operating_envelope(replace(_envelope(), **{name: "different"}))

    def test_exact_stack_sampling_policy_required(self):
        for policy in (harness.OPERATIONAL_MONITOR_ID, "STACK", "windows_job_memory"):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                operational.require_operating_envelope(replace(_envelope(), monitoring_policy=policy))

    def test_bool_zero_and_negative_caps_rejected(self):
        numeric = tuple(field.name for field in fields(_envelope())
                        if type(getattr(_envelope(), field.name)) is int)
        for name in numeric:
            for value in (True, 0, -1):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    operational.require_operating_envelope(_corrupt(_envelope(), **{name: value}))

    def test_duration_order_and_shadow_ceiling_rejected(self):
        changes = (
            {"monitor_interval_ms": 1001}, {"max_decision_wall_ms": 30001},
            {"max_case_wall_ms": 120001}, {"shadow_timeout_ms": 60001},
            {"shadow_timeout_ms": 30001})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                operational.require_operating_envelope(_corrupt(_envelope(), **change))


class NoTracerTests(unittest.TestCase):
    def test_runtime_module_ast_has_no_line_or_profile_hook_call(self):
        tree = ast.parse(inspect.getsource(operational))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else "")
                self.assertNotIn(name, {"settrace", "setprofile"})

    def test_worker_measurement_context_is_explicit_and_noncomparative(self):
        context = operational.MONITORING_CONTEXT
        self.assertIn("SUPERVISED_STACK_SAMPLING_V1", context)
        self.assertIn("no line/profile tracer installed", context)
        self.assertIn("runner spans measured in supervised execution context", context)
        self.assertIn("monitor_interval_ms", operational.SAMPLING_MEASUREMENT)
        self.assertIn("may miss", operational.SAMPLING_MEASUREMENT)
        self.assertIn("GIL", operational.SAMPLING_MEASUREMENT)
        self.assertIn("authoritative", operational.SAMPLING_MEASUREMENT)


class StackSamplingWatchdogTests(unittest.TestCase):
    def watchdog(self, report=None):
        return operational._DecisionWatchdog(
            17, frozenset({_dummy_decision_frame.__code__}), 20, 5,
            Mock() if report is None else report)

    def test_short_synthetic_decision_does_not_abort(self):
        report = Mock()
        monitor = self.watchdog(report)
        frame = _dummy_decision_frame()
        monitor.sample({17: frame}, 1_000_000)
        monitor.sample({17: frame}, 19_000_000)
        monitor.sample({17: _other_frame()}, 21_000_000)
        self.assertNotIn("SYSTEM_DECISION_TIMEOUT", repr(report.call_args_list))

    def test_continuously_observed_fixed_frame_reports_timeout(self):
        report = Mock()
        monitor = self.watchdog(report)
        frame = _dummy_decision_frame()
        monitor.sample({17: frame}, 1_000_000)
        monitor.sample({17: frame}, 22_000_000)
        self.assertIn("SYSTEM_DECISION_TIMEOUT", repr(report.call_args_list))

    def test_shadow_thread_is_not_the_physical_decision_thread(self):
        report = Mock()
        monitor = self.watchdog(report)
        shadow = _dummy_decision_frame()
        monitor.sample({17: _other_frame(), 99: shadow}, 1_000_000)
        monitor.sample({17: _other_frame(), 99: shadow}, 1_000_000_000)
        self.assertNotIn("SYSTEM_DECISION_TIMEOUT", repr(report.call_args_list))

    def test_observed_gap_resets_continuous_decision_timer(self):
        report = Mock()
        monitor = self.watchdog(report)
        first = _dummy_decision_frame()
        monitor.sample({17: first}, 1_000_000)
        monitor.sample({17: _other_frame()}, 15_000_000)
        monitor.sample({17: _dummy_decision_frame()}, 25_000_000)
        self.assertNotIn("SYSTEM_DECISION_TIMEOUT", repr(report.call_args_list))

    def test_new_decision_frame_does_not_inherit_previous_decision_time(self):
        report = Mock()
        monitor = self.watchdog(report)
        first, second = _dummy_decision_frame(), _dummy_decision_frame()
        monitor.sample({17: first}, 1_000_000)
        monitor.sample({17: second}, 25_000_000)
        self.assertNotIn("SYSTEM_DECISION_TIMEOUT", repr(report.call_args_list))

    def test_real_monitor_thread_never_installs_tracer(self):
        report = Mock()
        monitor = operational._DecisionWatchdog(
            threading.get_ident(), frozenset({_dummy_decision_frame.__code__}), 20, 5, report)
        with ExitStack() as stack:
            hooks = [stack.enter_context(patch.object(
                owner, name, side_effect=AssertionError("Forbidden tracing hook")))
                     for owner in (sys, threading) for name in ("settrace", "setprofile")]
            monitor.start()
            monitor.stop()
        for hook in hooks:
            hook.assert_not_called()

    def test_live_stack_sampling_observes_non_e1_helper_timeout(self):
        ready, release, observed = threading.Event(), threading.Event(), threading.Event()
        reports = []
        def report(event, detail=None):
            reports.append((event, detail))
            if event == "SYSTEM_DECISION_TIMEOUT":
                observed.set()
        target = threading.Thread(
            target=_blocked_non_e1_decision, args=(ready, release), daemon=True)
        target.start()
        monitor = None
        try:
            self.assertTrue(ready.wait(1))
            monitor = operational._DecisionWatchdog(
                target.ident, frozenset({_blocked_non_e1_decision.__code__}), 25, 5, report)
            monitor.start()
            self.assertTrue(observed.wait(2), reports)
            self.assertTrue(monitor.timed_out)
        finally:
            release.set()
            target.join(2)
            if monitor is not None:
                monitor.stop()
        self.assertFalse(target.is_alive())

    def test_failed_stack_collection_cannot_silently_disable_monitor(self):
        observed = threading.Event()
        def report(event, detail=None):
            if event == "WORKER_ABORT":
                observed.set()
        monitor = operational._DecisionWatchdog(
            threading.get_ident(), frozenset({_dummy_decision_frame.__code__}), 20, 1, report)
        with patch.object(sys, "_current_frames", side_effect=RuntimeError("sample failed")):
            monitor.start()
            try:
                self.assertTrue(observed.wait(2))
            finally:
                with self.assertRaises(operational.E1OperationalAbort):
                    monitor.stop()
        self.assertTrue(monitor.timed_out)

    def test_failed_timeout_report_cannot_silently_disable_monitor(self):
        observed = threading.Event()
        def failed_sample():
            observed.set()
            raise OSError("IPC report failed")
        monitor = self.watchdog(Mock(side_effect=OSError("parent unavailable")))
        with patch.object(monitor, "sample", side_effect=failed_sample):
            monitor.start()
            try:
                self.assertTrue(observed.wait(2))
            finally:
                with self.assertRaises(operational.E1OperationalAbort):
                    monitor.stop()
        self.assertTrue(monitor.timed_out)


class PhysicalInputCapTests(unittest.TestCase):
    def test_exact_engine_boundary_counted_once_and_arguments_preserved(self):
        calls = []
        answer = object()
        def physical(owner, *args, **kwargs):
            calls.append((owner, args, kwargs))
            return answer
        engine = object.__new__(core_engine.MinesweeperEngine)
        report = Mock()
        with patch.object(core_engine.MinesweeperEngine, "step", physical):
            with operational._PhysicalInputGuard(3, report) as guard:
                self.assertIs(engine.step(1, 2, 0), answer)
                self.assertIs(engine.step(x=2, y=3, action=1), answer)
                self.assertEqual(guard.count, 2)
            self.assertIs(core_engine.MinesweeperEngine.step, physical)
        self.assertEqual(calls, [(engine, (1, 2, 0), {}),
                                 (engine, (), {"x": 2, "y": 3, "action": 1})])

    def test_cap_blocks_before_next_underlying_physical_input(self):
        underlying = Mock(return_value="same-result")
        engine = object.__new__(core_engine.MinesweeperEngine)
        with patch.object(core_engine.MinesweeperEngine, "step", underlying):
            with operational._PhysicalInputGuard(1, Mock()) as guard:
                self.assertEqual(engine.step(0, 0, 0), "same-result")
                with self.assertRaises(Exception):
                    engine.step(1, 0, 0)
                self.assertEqual(guard.count, 1)
        self.assertEqual(underlying.call_count, 1)

    def test_engine_semantic_exception_propagates_unchanged(self):
        problem = RuntimeError("declared Engine semantic failure")
        underlying = Mock(side_effect=problem)
        engine = object.__new__(core_engine.MinesweeperEngine)
        with patch.object(core_engine.MinesweeperEngine, "step", underlying):
            with operational._PhysicalInputGuard(3, Mock()) as guard:
                with self.assertRaises(RuntimeError) as caught:
                    engine.step(0, 0, 0)
                self.assertIs(caught.exception, problem)
                self.assertEqual(guard.count, 1)
        self.assertEqual(underlying.call_count, 1)

    def test_wrapper_is_removed_after_exception(self):
        original = core_engine.MinesweeperEngine.step
        with self.assertRaises(RuntimeError):
            with operational._PhysicalInputGuard(1, Mock()):
                raise RuntimeError("test-owned abort")
        self.assertIs(core_engine.MinesweeperEngine.step, original)


class PublicDispatchTests(unittest.TestCase):
    def scheduled_validator(self, index=0, envelope=None):
        with patch.object(operational, "_supervise_e1", return_value=None) as supervise:
            operational.supervise_scheduled_run(
                _data()[0], index, envelope or _envelope(),
                job_started_ns=time.monotonic_ns(), archive_used_bytes=0)
        supervise.assert_called_once()
        return supervise.call_args

    def test_scheduled_supervisor_dispatches_exactly_one_requested_operation(self):
        with patch.object(execution, "execute_scheduled_entry",
                          side_effect=AssertionError("No real scheduled boundary in parent")) as execute:
            called = self.scheduled_validator(7)
        self.assertEqual(called.args[0], "SCHEDULED_RUN")
        self.assertEqual(called.args[1], _data()[0].schedule[7])
        execute.assert_not_called()

    def test_schedule_index_requires_true_int_in_fixed_range(self):
        for index in (True, False, -1, 54, 0.0, "0", None):
            with self.subTest(index=index), patch.object(operational, "_supervise_e1") as supervise:
                with self.assertRaises(ValueError):
                    operational.supervise_scheduled_run(
                        _data()[0], index, _envelope(),
                        job_started_ns=time.monotonic_ns(), archive_used_bytes=0)
                supervise.assert_not_called()

    def test_scheduled_parent_admits_semantic_fail_without_lifecycle_relabel(self):
        _, archives, audits = _data()
        failed = replace(audits[0], discrepancies=("Declared semantic failure",),
                         audit_status="FAIL")
        validate = self.scheduled_validator().kwargs["validate"]
        validate((archives[0], failed, None))

    def test_scheduled_parent_rejects_other_schedule_entry(self):
        validate = self.scheduled_validator().kwargs["validate"]
        with self.assertRaises(ValueError):
            validate((_data()[1][1], _data()[2][1], None))

    def test_scheduled_parent_rejects_archive_shadow_timeout_not_from_envelope(self):
        validate = self.scheduled_validator(envelope=_envelope(shadow_timeout_ms=2500)).kwargs["validate"]
        with self.assertRaises(ValueError):
            validate((_data()[1][0], _data()[2][0], None))

    def test_scheduled_parent_rechecks_actual_audit_and_suite_source_identity(self):
        validate = self.scheduled_validator().kwargs["validate"]
        changed = replace(_data()[2][0].source_identity,
                          audit_file=replace(_data()[2][0].source_identity.audit_file,
                                             sha256="f" * 64))
        with patch.object(audit, "capture_audit_source_identity", return_value=changed):
            with self.assertRaises(ValueError):
                validate((_data()[1][0], _data()[2][0], None))

    def test_evaluator_requires_complete_exact_phase_admission(self):
        admission = _admission()
        target = admission.targets[0]
        for invalid in (None, _corrupt(admission, targets=admission.targets[:-1]), _aggregate()):
            with self.subTest(invalid=type(invalid).__name__), \
                    patch.object(operational, "_supervise_e1") as supervise:
                with self.assertRaises(ValueError):
                    operational.supervise_posthoc_evaluator(
                        invalid, target, _envelope(),
                        job_started_ns=time.monotonic_ns(), archive_used_bytes=0)
                supervise.assert_not_called()

    def test_evaluator_dispatch_is_posthoc_and_target_is_kp0_only(self):
        admission = _admission()
        target = admission.targets[0]
        with patch.object(operational, "_supervise_e1", return_value=None) as supervise, \
                patch.object(e1_evaluator, "evaluate_compact_request",
                             side_effect=AssertionError("No truth before worker barrier")) as evaluate:
            operational.supervise_posthoc_evaluator(
                admission, target, _envelope(),
                job_started_ns=time.monotonic_ns(), archive_used_bytes=0)
        supervise.assert_called_once()
        self.assertEqual(supervise.call_args.args[0], "POST_HOC_EVALUATOR")
        self.assertEqual(supervise.call_args.args[1], target.schedule_entry)
        self.assertEqual(supervise.call_args.args[4], (target, admission.target_digests[0]))
        evaluate.assert_not_called()

    def test_evaluator_parent_rejects_control_binding_without_worker(self):
        admission = _admission()
        with patch.object(operational, "_supervise_e1") as supervise:
            with self.assertRaises(ValueError):
                operational.supervise_posthoc_evaluator(
                    admission, _aggregate().bindings[0], _envelope(),
                    job_started_ns=time.monotonic_ns(), archive_used_bytes=0)
        supervise.assert_not_called()


class PayloadDAGIntegrationTests(unittest.TestCase):
    def test_long_flag_payload_uses_semantic_dag_bytes_without_dispatch(self):
        from tests.test_program_k_e1_suite import _enclosing_flag_graph
        k = 98
        # Prospective guard: each separately encoded archive/audit is bounded
        # by the enclosing-graph guard, plus the fixed payload JSON envelope.
        maximum_bytes = 2 * (1_000_000 + 40_000 * k + 2048 * k * k) + 256
        with patch.object(execution, "execute_scheduled_entry",
                          side_effect=AssertionError("No scheduled execution")) as execute, \
                patch.object(e1_evaluator, "evaluate_scheduled_kp0",
                             side_effect=AssertionError("No evaluator execution")) as evaluate, \
                patch.object(core_engine.MinesweeperEngine, "__init__",
                             side_effect=AssertionError("No Engine")) as engine:
            archive, checked = _enclosing_flag_graph(k)
            payload = (archive, checked, None)
            encoded = operational._payload_bytes(payload)
            self.assertEqual(encoded, operational._payload_bytes(payload))
            copied = _enclosing_flag_graph(k, copies=True)
            self.assertEqual(encoded, operational._payload_bytes((*copied, None)))
            mutated = _enclosing_flag_graph(k, mutation=True)
            self.assertNotEqual(hashlib.sha256(encoded).hexdigest(), hashlib.sha256(
                operational._payload_bytes((*mutated, None))).hexdigest())
        self.assertLessEqual(len(encoded), maximum_bytes)
        execute.assert_not_called()
        evaluate.assert_not_called()
        engine.assert_not_called()


class ProcessSupervisorTests(unittest.TestCase):
    def supervise(self, *, messages=(), envelope=None, peak=100, coordinator=100,
                  aborted=False, finish=False, used=0, clock_step=1_000_000,
                  attach_error=None, kind="SCHEDULED_RUN", entry=None, request=()):
        envelope = _envelope() if envelope is None else envelope
        log = []
        parent, child = _FakeConnection(messages), _FakeConnection()
        process = _FakeProcess(log, aborted=aborted, finish=finish)
        barrier = Mock()
        barrier.set.side_effect = lambda: log.append("release")
        context = Mock()
        context.Pipe.return_value = (parent, child)
        context.Event.return_value = barrier
        context.Process.return_value = process
        api = Mock()
        api.TerminateJobObject.side_effect = lambda *args: log.append("terminate-job") or True
        api.CloseHandle.side_effect = lambda *args: log.append("close-job") or True
        peak_fn = Mock(side_effect=peak) if isinstance(peak, Exception) else Mock(return_value=peak)
        def attach(pid, budget):
            log.append("attach")
            if attach_error is not None:
                raise attach_error
            return api, 44, peak_fn
        ticks = iter(range(1_000_000, 10_000_000_000, clock_step))
        with patch.object(operational.multiprocessing, "get_context", return_value=context), \
                patch.object(harness, "_attach_memory_job", side_effect=attach), \
                patch.object(harness, "_coordinator_private_bytes", return_value=coordinator), \
                patch.object(operational.time, "monotonic_ns", side_effect=lambda: next(ticks)):
            result = operational._supervise_e1(
                kind, _data()[0].schedule[0] if entry is None else entry,
                operational.capture_operational_source_identity(_data()[0]),
                envelope, request, job_started_ns=1, archive_used_bytes=used,
                worker_target=_noop_worker, validate=lambda payload: None)
        return result, log, context, parent

    def test_clean_complete_and_attach_before_release(self):
        result, log, context, parent = self.supervise(
            messages=_result_messages((None, None, None)), finish=True)
        self.assertEqual(result.receipt.status, "COMPLETE", result.receipt.reason)
        self.assertLess(log.index("attach"), log.index("release"))
        self.assertIn("close-job", log)
        self.assertIn("join", log)
        self.assertEqual(context.Process.call_count, 1)
        self.assertEqual(result.receipt.physical_inputs, 0)
        self.assertGreater(result.receipt.memory_evidence.sample_count, 0)
        self.assertTrue(all(value == b"CONTINUE" for value in parent.acknowledgments))

    def test_memory_cap_aborts_and_reaps_whole_job(self):
        result, log, context, _ = self.supervise(
            envelope=_envelope(memory_cap_bytes=1000), peak=901)
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIn("SYSTEM_MEMORY_CAP", result.receipt.reason)
        self.assertIn("terminate-job", log)
        self.assertIn("close-job", log)
        self.assertIn("terminate", log)
        self.assertIn("join", log)
        self.assertNotIn("release", log)
        self.assertEqual(context.Process.call_count, 1)

    def test_memory_monitor_failure_never_completes(self):
        result, log, _, _ = self.supervise(peak=RuntimeError("missing memory sample"))
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIsNone(result.receipt.memory_evidence)
        self.assertIn("terminate-job", log)

    def test_job_attachment_failure_never_releases_worker(self):
        result, log, _, _ = self.supervise(attach_error=OSError("declared Job failure"))
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertNotIn("release", log)
        self.assertIn("terminate", log)
        self.assertIn("join", log)

    def test_case_deadline_aborts_without_retry(self):
        envelope = _envelope(max_decision_wall_ms=2, max_case_wall_ms=3,
                             shadow_timeout_ms=1, monitor_interval_ms=1)
        result, log, context, _ = self.supervise(envelope=envelope)
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIn("SYSTEM_CASE_TIMEOUT", result.receipt.reason)
        self.assertIn("terminate-job", log)
        self.assertEqual(context.Process.call_count, 1)

    def test_whole_job_deadline_aborts_without_release(self):
        envelope = _envelope(max_decision_wall_ms=1, max_case_wall_ms=1,
                             max_job_wall_ms=1, shadow_timeout_ms=1, monitor_interval_ms=1)
        result, log, context, _ = self.supervise(envelope=envelope)
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIn("SYSTEM_JOB_TIMEOUT", result.receipt.reason)
        self.assertNotIn("release", log)
        self.assertEqual(context.Process.call_count, 1)

    def test_process_abort_is_incomplete_and_not_loss(self):
        result, _, context, _ = self.supervise(aborted=True)
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIn("SYSTEM_PROCESS_ABORT", result.receipt.reason)
        self.assertIsNone(result.archive)
        self.assertEqual(context.Process.call_count, 1)

    def test_archive_budget_exhaustion_prevents_worker_release(self):
        envelope = _envelope()
        result, log, _, _ = self.supervise(envelope=envelope, used=envelope.archive_cap_bytes)
        self.assertEqual(result.receipt.reason, "SYSTEM_ARCHIVE_CAP")
        self.assertNotIn("spawn", log)
        self.assertNotIn("release", log)

    def test_result_archive_byte_cap_aborts_before_accepting_payload(self):
        result, log, _, _ = self.supervise(
            messages=_result_messages((None, None, None)), envelope=_envelope(archive_cap_bytes=1))
        self.assertEqual(result.receipt.reason, "SYSTEM_ARCHIVE_CAP")
        self.assertIsNone(result.archive)
        self.assertIn("terminate-job", log)

    def test_result_content_digest_mismatch_is_incomplete(self):
        result, _, _, _ = self.supervise(
            messages=_result_messages((None, None, None), corrupt_digest=True))
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIn("digest", result.receipt.reason)

    def test_parent_reconciles_input_count_with_returned_archive(self):
        payload = (_data()[1][0], _data()[2][0], None)
        result, _, _, _ = self.supervise(messages=_result_messages(payload))
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIn("Physical input count", result.receipt.reason)

    def test_semantic_fail_archive_can_complete_process_lifecycle(self):
        failed = replace(_data()[2][0], discrepancies=("Declared semantic failure",),
                         audit_status="FAIL")
        payload = (_data()[1][0], failed, None)
        result, _, context, _ = self.supervise(
            messages=_result_messages(payload, len(payload[0].result.traces)), finish=True)
        self.assertEqual(result.receipt.status, "COMPLETE", result.receipt.reason)
        self.assertEqual(result.audit.audit_status, "FAIL")
        self.assertEqual(context.Process.call_count, 1)

    def test_evaluator_falsification_can_complete_without_physical_inputs(self):
        binding = next(b for b in _aggregate().bindings
                       if b.case.case_id == "S-LIFECYCLE" and b.schedule_entry.variant == "K-P0")
        finding = _manual_evaluation(_aggregate(), binding, falsification=True)
        result, _, context, _ = self.supervise(
            kind="POST_HOC_EVALUATOR", entry=binding.schedule_entry,
            request=(SimpleNamespace(evaluation_run_id=finding.evaluation_run_id),),
            messages=_result_messages((None, None, finding)), finish=True)
        self.assertEqual(result.receipt.status, "COMPLETE", result.receipt.reason)
        self.assertEqual(result.evaluation.classification, "G1_FALSIFICATION")
        self.assertEqual(result.receipt.physical_inputs, 0)
        self.assertEqual(context.Process.call_count, 1)

    def test_evaluator_process_abort_is_incomplete_without_retry(self):
        binding = next(b for b in _aggregate().bindings if b.schedule_entry.variant == "K-P0")
        result, _, context, _ = self.supervise(
            kind="POST_HOC_EVALUATOR", entry=binding.schedule_entry,
            request=(SimpleNamespace(evaluation_run_id="manual-abort"),), aborted=True)
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertIsNone(result.evaluation)
        self.assertEqual(result.receipt.physical_inputs, 0)
        self.assertEqual(context.Process.call_count, 1)

    def test_evaluator_physical_input_message_is_rejected(self):
        binding = next(b for b in _aggregate().bindings if b.schedule_entry.variant == "K-P0")
        result, _, _, _ = self.supervise(
            kind="POST_HOC_EVALUATOR", entry=binding.schedule_entry,
            request=(SimpleNamespace(evaluation_run_id="manual-abort"),),
            messages=(pickle.dumps(("STARTED", None)), pickle.dumps(("BEFORE_INPUT", None))))
        self.assertEqual(result.receipt.status, "INCOMPLETE")
        self.assertEqual(result.receipt.physical_inputs, 0)

    @unittest.skipUnless(sys.platform == "win32", "Actual Windows spawn/Job Object smoke")
    def test_real_windows_spawn_job_noop_smoke(self):
        before = {child.pid for child in multiprocessing.active_children()}
        result = operational._supervise_e1(
            "SCHEDULED_RUN", _data()[0].schedule[0],
            operational.capture_operational_source_identity(_data()[0]),
            _envelope(), (), job_started_ns=time.monotonic_ns(),
            archive_used_bytes=0, worker_target=_noop_worker, validate=lambda payload: None)
        self.assertEqual(result.receipt.status, "COMPLETE", result.receipt.reason)
        self.assertEqual(result.receipt.exit_code, 0)
        self.assertEqual(result.receipt.physical_inputs, 0)
        self.assertIsNone(result.archive)
        self.assertIsNone(result.audit)
        self.assertIsNone(result.evaluation)
        memory = result.receipt.memory_evidence
        self.assertGreater(memory.peak_worker_tree_bytes, 0)
        self.assertGreater(memory.sample_count, 0)
        self.assertGreaterEqual(memory.peak_combined_bytes, memory.peak_worker_tree_bytes)
        self.assertLessEqual(memory.peak_worker_tree_bytes, memory.worker_budget_bytes)
        self.assertLessEqual(memory.peak_combined_bytes, memory.memory_cap_bytes)
        self.assertIn("not machine-wide", memory.measurement)
        self.assertTrue({child.pid for child in multiprocessing.active_children()} <= before)


class WorkerDispatchTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Actual Windows compact spawn/Job unit fixtures")
    def test_all_18_spawned_compact_workers_use_only_fabricated_unit_answers(self):
        admission = _admission()
        supervise = operational._supervise_e1
        encoded, digest = suite._encoded, suite._content_digest
        before = {child.pid for child in multiprocessing.active_children()}
        dispatched, completed = [], []

        def reject_whole(value, operation, *args, **kwargs):
            self.assertIsNot(type(value), suite.E1SuiteAggregate)
            return operation(value, *args, **kwargs)

        def unit_spawn(kind, entry, identity, envelope, request, **kwargs):
            target, expected_digest = request
            self.assertIs(type(target), e1_evaluator.E1EvaluatorRequest)
            self.assertEqual(expected_digest, e1_evaluator.request_digest(target))
            self.assertEqual(entry, target.schedule_entry)
            dispatched.append(entry.schedule_index)
            return supervise(kind, entry, identity, envelope, request,
                             worker_target=_bounded_compact_worker, **kwargs)

        with ExitStack() as stack:
            for owner, name in ((suite, "aggregate_e1_suite"),
                                (e1_evaluator, "require_complete_suite"),
                                (e1_evaluator, "_fixed_answer"),
                                (evaluator, "evaluate_falsification")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
            stack.enter_context(patch.object(
                suite, "_encoded", side_effect=lambda v, *a, **k: reject_whole(v, encoded, *a, **k)))
            stack.enter_context(patch.object(
                suite, "_content_digest", side_effect=lambda v, *a, **k: reject_whole(v, digest, *a, **k)))
            stack.enter_context(patch.object(operational, "_supervise_e1", side_effect=unit_spawn))
            for target in admission.targets:
                with self.subTest(index=target.schedule_entry.schedule_index):
                    result = operational.supervise_posthoc_evaluator(
                        admission, target, _envelope(),
                        job_started_ns=time.monotonic_ns(), archive_used_bytes=0)
                    self.assertEqual(result.receipt.status, "COMPLETE", result.receipt.reason)
                    self.assertEqual(result.receipt.exit_code, 0)
                    self.assertEqual(result.receipt.physical_inputs, 0)
                    self.assertIsNotNone(result.receipt.memory_evidence)
                    self.assertEqual(result.evaluation.finding.sealed_input, target.sealed_input)
                    self.assertFalse(result.evaluation.proof_upgrade_allowed)
                    self.assertIsNone(result.archive)
                    self.assertIsNone(result.audit)
                    completed.append(result.receipt.schedule_index)
        self.assertEqual(dispatched, list(range(2, 54, 3)))
        self.assertEqual(completed, dispatched)
        self.assertTrue({child.pid for child in multiprocessing.active_children()} <= before)

    def test_scheduled_worker_exact_single_dispatch_no_tracer_and_audit_after_monitor(self):
        plan, archives, audits = _data()
        entry = plan.schedule[0]
        identity = operational.capture_operational_source_identity(plan)
        channel, connection, barrier = Mock(), Mock(), Mock()
        monitor = Mock(timed_out=False)
        stopped = []
        monitor.stop.side_effect = lambda: stopped.append(True)
        original_step = core_engine.MinesweeperEngine.step
        def check_audit(actual_plan, archive):
            self.assertEqual(stopped, [True])
            self.assertIs(core_engine.MinesweeperEngine.step, original_step)
            return audits[0]
        with ExitStack() as stack:
            hooks = [stack.enter_context(patch.object(
                owner, name, side_effect=AssertionError("Forbidden tracing hook")))
                     for owner in (sys, threading) for name in ("settrace", "setprofile")]
            stack.enter_context(patch.object(operational, "_WorkerChannel", return_value=channel))
            stack.enter_context(patch.object(operational, "_decision_watchdog", return_value=monitor))
            execute = stack.enter_context(patch.object(
                execution, "execute_scheduled_entry", return_value=archives[0]))
            check = stack.enter_context(patch.object(
                audit, "audit_scheduled_run", side_effect=check_audit))
            source = stack.enter_context(patch.object(
                operational, "capture_operational_source_identity", return_value=identity))
            operational._worker_main(
                "SCHEDULED_RUN", (plan, entry), identity, _envelope(), connection, barrier)
        barrier.wait.assert_called_once_with()
        execute.assert_called_once_with(plan, 0, shadow_timeout_s=1.0)
        check.assert_called_once_with(plan, archives[0])
        self.assertEqual(source.call_count, 2)
        monitor.start.assert_called_once_with()
        monitor.stop.assert_called_once_with()
        channel.finish.assert_called_once_with((archives[0], audits[0], None))
        connection.close.assert_called_once_with()
        for hook in hooks:
            hook.assert_not_called()

    def test_worker_source_precheck_failure_prevents_execution(self):
        plan = _data()[0]
        identity = operational.capture_operational_source_identity(plan)
        changed = replace(identity, files=(
            identity.files[0], replace(identity.files[1], sha256="0" * 64)))
        with patch.object(operational, "capture_operational_source_identity", return_value=changed), \
                patch.object(execution, "execute_scheduled_entry") as execute:
            with self.assertRaises(ValueError):
                operational._scheduled_worker_operation(
                    plan, plan.schedule[0], identity, _envelope())
        execute.assert_not_called()

    def test_worker_source_postcheck_failure_retains_no_success(self):
        plan, archives, audits = _data()
        identity = operational.capture_operational_source_identity(plan)
        changed = replace(identity, files=(
            identity.files[0], replace(identity.files[1], sha256="0" * 64)))
        with patch.object(operational, "capture_operational_source_identity",
                          side_effect=(identity, changed)), \
                patch.object(execution, "execute_scheduled_entry", return_value=archives[0]) as execute, \
                patch.object(audit, "audit_scheduled_run", return_value=audits[0]) as check:
            with self.assertRaises(ValueError):
                operational._scheduled_worker_operation(
                    plan, plan.schedule[0], identity, _envelope())
        execute.assert_called_once()
        check.assert_called_once()

    def test_execution_abort_does_not_retry_or_audit(self):
        plan = _data()[0]
        identity = operational.capture_operational_source_identity(plan)
        channel, monitor = Mock(), Mock(timed_out=False)
        with patch.object(operational, "_WorkerChannel", return_value=channel), \
                patch.object(operational, "_decision_watchdog", return_value=monitor), \
                patch.object(execution, "execute_scheduled_entry",
                             side_effect=operational.E1OperationalAbort("SYSTEM_INPUT_CAP")) as execute, \
                patch.object(audit, "audit_scheduled_run") as check:
            with self.assertRaises(operational.E1OperationalAbort):
                operational._worker_main(
                    "SCHEDULED_RUN", (plan, plan.schedule[0]), identity,
                    _envelope(), Mock(), Mock())
        execute.assert_called_once()
        check.assert_not_called()
        channel.finish.assert_not_called()
        self.assertIn("SYSTEM_INPUT_CAP", repr(channel.event.call_args_list))

    def test_evaluator_worker_calls_adapter_once_and_never_runner_or_engine(self):
        aggregate = _aggregate()
        admission = _admission()
        target, expected_digest = admission.targets[0], admission.target_digests[0]
        binding = aggregate.bindings[target.schedule_entry.schedule_index]
        finding = _manual_evaluation(aggregate, binding, evaluation_run_id=target.evaluation_run_id)
        identity = admission.operational_source_identity
        channel, connection, barrier = Mock(), Mock(), Mock()
        with patch.object(operational, "_WorkerChannel", return_value=channel), \
                patch.object(e1_evaluator, "evaluate_compact_request", return_value=finding) as evaluate, \
                patch.object(e1_evaluator, "verify_compact_finding", wraps=e1_evaluator.verify_compact_finding) as verify, \
                patch.object(execution, "execute_scheduled_entry", side_effect=AssertionError("runner")) as execute, \
                patch.object(core_engine.MinesweeperEngine, "step", side_effect=AssertionError("Engine")) as step:
            operational._worker_main(
                "POST_HOC_EVALUATOR",
                (target, expected_digest),
                identity, _envelope(), connection, barrier)
        evaluate.assert_called_once_with(target, expected_digest, identity)
        verify.assert_called_once()
        execute.assert_not_called()
        step.assert_not_called()
        barrier.wait.assert_called_once_with()
        channel.finish.assert_called_once_with((None, None, finding))
        self.assertNotIn("BEFORE_INPUT", repr(channel.event.call_args_list))

    def test_evaluator_worker_rejects_source_drift_before_comparison(self):
        admission = _admission()
        target, expected_digest = admission.targets[0], admission.target_digests[0]
        read = Path.read_bytes
        for filename in ("program_k_e1_evaluator.py", "program_k_e1_operational.py"):
            def changed(path, name=filename):
                raw = read(path)
                return raw + b"\n# changed before worker comparison\n" if path.name == name else raw
            with self.subTest(filename=filename), patch.object(Path, "read_bytes", changed), \
                    patch.object(operational, "_WorkerChannel") as channel, \
                    patch.object(e1_evaluator, "evaluate_compact_request") as evaluate:
                with self.assertRaises(ValueError):
                    operational._worker_main(
                        "POST_HOC_EVALUATOR", (target, expected_digest),
                        admission.operational_source_identity, _envelope(), Mock(), Mock())
                evaluate.assert_not_called()
                channel.return_value.finish.assert_not_called()

    def test_all_18_parent_and_worker_paths_transfer_only_compact_values(self):
        aggregate, admission = _aggregate(), _admission()
        findings = tuple(_manual_evaluation(
            aggregate, aggregate.bindings[target.schedule_entry.schedule_index],
            evaluation_run_id=target.evaluation_run_id) for target in admission.targets)
        encoded, digest = suite._encoded, suite._content_digest

        def no_aggregate_encode(value, *args, **kwargs):
            self.assertIsNot(type(value), suite.E1SuiteAggregate)
            return encoded(value, *args, **kwargs)

        def no_aggregate_digest(value, *args, **kwargs):
            self.assertIsNot(type(value), suite.E1SuiteAggregate)
            return digest(value, *args, **kwargs)

        with ExitStack() as stack:
            for owner, name in ((suite, "aggregate_e1_suite"),
                                (e1_evaluator, "require_complete_suite"),
                                (e1_evaluator, "_fixed_answer"),
                                (execution, "execute_scheduled_entry")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
            stack.enter_context(patch.object(suite, "_encoded", side_effect=no_aggregate_encode))
            stack.enter_context(patch.object(suite, "_content_digest", side_effect=no_aggregate_digest))
            for target, expected_digest, finding in zip(
                    admission.targets, admission.target_digests, findings):
                with self.subTest(index=target.schedule_entry.schedule_index), \
                        patch.object(operational, "_supervise_e1") as supervise:
                    operational.supervise_posthoc_evaluator(
                        admission, target, _envelope(),
                        job_started_ns=time.monotonic_ns(), archive_used_bytes=0)
                called = supervise.call_args
                self.assertEqual(called.args[4], (target, expected_digest))
                # Equal detached values survive the exact spawn serialization boundary.
                transported = pickle.loads(pickle.dumps(called.args[4]))
                self.assertEqual(transported, (target, expected_digest))
                channel = Mock()
                with patch.object(operational, "_WorkerChannel", return_value=channel), \
                        patch.object(e1_evaluator, "evaluate_compact_request", return_value=finding):
                    operational._worker_main(
                        called.args[0], transported, called.args[2], called.args[3], Mock(), Mock())
                channel.finish.assert_called_once_with((None, None, finding))
                called.kwargs["validate"]((None, None, finding))
                for wrong in ((aggregate.bindings[0].archive, None, finding),
                              (None, aggregate.bindings[0].audit, finding),
                              (None, None, _corrupt(finding, suite_content_digest="f" * 64))):
                    with self.assertRaises(ValueError):
                        called.kwargs["validate"](wrong)


class ReceiptIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.receipt = _manual_receipt(
            _data()[0].schedule[0],
            operational.capture_operational_source_identity(_data()[0]),
            (_data()[1][0], _data()[2][0], None),
            physical_inputs=len(_data()[1][0].result.traces))

    def test_missing_memory_cannot_claim_complete(self):
        with self.assertRaises(ValueError):
            _receipt_change(self.receipt, memory_evidence=None)

    def test_memory_samples_caps_and_budgets_are_exact(self):
        for change in ({"sample_count": 0}, {"worker_budget_bytes": True},
                       {"peak_worker_tree_bytes": 0}, {"peak_combined_bytes": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                _receipt_change(self.receipt, memory_evidence=_corrupt(
                    self.receipt.memory_evidence, **change))
        for change in ({"memory_cap_bytes": self.receipt.envelope.memory_cap_bytes + 1},
                       {"peak_worker_tree_bytes": 1001, "peak_combined_bytes": 1101}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                _receipt_change(self.receipt, memory_evidence=replace(
                    self.receipt.memory_evidence, **change))

    def test_exact_envelope_digest_and_monitor_interval_required(self):
        for change in ({"envelope": None}, {"envelope_digest": "0" * 64},
                       {"monitor_interval_ms": self.receipt.monitor_interval_ms + 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                _receipt_change(self.receipt, **change)

    def test_operation_id_and_archive_budget_arithmetic_cannot_be_spoofed(self):
        for change in ({"operation_id": self.receipt.operation_id + "-suffix"},
                       {"physical_inputs": self.receipt.physical_inputs + 1},
                       {"exit_code": 1}, {"result_digest": None}, {"repetition": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                _receipt_change(self.receipt, **change)
        with self.assertRaises(ValueError):
            replace(self.receipt, archive_used_after_bytes=self.receipt.archive_used_after_bytes + 1)

    def test_monitor_text_subclass_cannot_carry_live_attachments(self):
        class AttachedText(str):
            pass
        text = AttachedText(operational.MONITORING_CONTEXT)
        text.live = lambda: None
        with self.assertRaises(ValueError):
            _receipt_change(self.receipt, monitoring_context=text)
        event = AttachedText("STARTED")
        event.live = lambda: None
        with self.assertRaises(ValueError):
            operational.E1MonitorEvent(0, event, 0, 0)


class ResourceSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheduled, cls.evaluated = _resource_data()

    def summary(self, scheduled=None, evaluated=None, aggregate=None, *, rechain=True):
        aggregate = _aggregate() if aggregate is None else aggregate
        scheduled = self.scheduled if scheduled is None else scheduled
        evaluated = self.evaluated if evaluated is None else evaluated
        if rechain:
            # Newly declared fixture variants have their own retained-receipt
            # byte size. Build a fresh cumulative accounting sequence.
            rescheduled, reevaluated, used = [], [], 0
            for receipt in scheduled:
                receipt = _receipt_reaccount(receipt, used=used)
                rescheduled.append(receipt)
                used = receipt.archive_used_after_bytes
            for result in evaluated:
                receipt = _receipt_reaccount(result.receipt, used=used)
                reevaluated.append(_corrupt(result, receipt=receipt))
                used = receipt.archive_used_after_bytes
            scheduled, evaluated = tuple(rescheduled), tuple(reevaluated)
        return operational.summarize_operational_resources(
            aggregate.plan, aggregate, scheduled, evaluated)

    def test_exact_54_and_18_complete_coverage_is_descriptive(self):
        result = self.summary()
        self.assertEqual((result.scheduled_expected, result.scheduled_received,
                          result.scheduled_complete, result.scheduled_incomplete),
                         (54, 54, 54, 0))
        self.assertEqual((result.evaluator_expected, result.evaluator_received,
                          result.evaluator_complete, result.evaluator_incomplete),
                         (18, 18, 18, 0))
        self.assertEqual(result.resource_status, "COMPLETE_CONTAINMENT_EVIDENCE")
        self.assertEqual(len(result.scheduled_keys), 54)
        self.assertEqual(len(result.evaluator_keys), 18)

    def test_exact_trace_count_total_and_case_elapsed_retained(self):
        result = self.summary()
        self.assertEqual(result.total_physical_inputs,
                         sum(len(b.archive.result.traces) for b in _aggregate().bindings))
        self.assertEqual(result.case_elapsed_ns,
                         tuple((r.schedule_index, r.elapsed_ns) for r in self.scheduled))
        self.assertEqual(result.max_case_elapsed_ns,
                         max(r.elapsed_ns for r in self.scheduled))

    def test_memory_and_archive_evidence_retained_per_operation(self):
        result = self.summary()
        self.assertEqual(len(result.memory_evidence), 72)
        self.assertEqual(result.max_peak_worker_tree_bytes, 100)
        self.assertEqual(result.max_peak_combined_sampled_bytes, 200)
        self.assertEqual(result.archive_bytes,
                         sum(r.archive_result_bytes + r.archive_receipt_bytes for r in self.scheduled)
                         + sum(r.receipt.archive_result_bytes + r.receipt.archive_receipt_bytes
                               for r in self.evaluated))

    def test_runner_oracle_and_evaluator_timings_remain_separate(self):
        result = self.summary()
        self.assertEqual(result.runner_timings, _aggregate().diagnostics.runner_timings)
        self.assertEqual(result.oracle_timings, _aggregate().diagnostics.oracle_timings)
        self.assertEqual(result.evaluator_call_count, 18)
        self.assertEqual(result.evaluator_duration_ns, 18 * 47)
        self.assertEqual(sum(dict(result.classifications).values()), 18)
        self.assertEqual(result.monitoring_context, operational.MONITORING_CONTEXT)

    def test_n2_requires_complete_exact_supervised_context(self):
        self.assertEqual(self.summary().n2_status, "ADDRESSED_BY_SUPERVISED_CONTEXT_BINDING")
        self.assertNotEqual(self.summary(self.scheduled[:-1]).n2_status,
                            "ADDRESSED_BY_SUPERVISED_CONTEXT_BINDING")

    def test_missing_scheduled_or_evaluator_coverage_is_incomplete(self):
        for scheduled, evaluated in (
                (self.scheduled[:-1], self.evaluated),
                (self.scheduled, self.evaluated[:-1]), ((), ())):
            with self.subTest(scheduled=len(scheduled), evaluated=len(evaluated)):
                self.assertEqual(self.summary(scheduled, evaluated).resource_status, "INCOMPLETE")

    def test_duplicate_receipt_is_identity_failure(self):
        result = self.summary(self.scheduled + (self.scheduled[0],))
        self.assertEqual(result.resource_status, "FAIL_IDENTITY_OR_EVIDENCE")

    def test_wrong_result_digest_cannot_reconcile_archive(self):
        changed = _receipt_change(self.scheduled[0], result_digest="0" * 64)
        result = self.summary((changed,) + self.scheduled[1:])
        self.assertEqual(result.resource_status, "FAIL_IDENTITY_OR_EVIDENCE")
        self.assertTrue(any("Scheduled receipt/archive" in reason for reason in result.reasons))

    def test_lossless_timing_changes_cannot_reuse_original_receipt_digest(self):
        plan, archives, audits = _data()
        index = next(i for i, a in enumerate(archives) if a.schedule_entry.variant == "K-P0")
        old = archives[index]
        trace = old.result.traces[0]
        changed_trace = replace(trace, timings=replace(
            trace.timings, evidence_ns=trace.timings.evidence_ns + 1))
        changed = replace(old, result=replace(
            old.result, traces=(changed_trace,) + old.result.traces[1:]))
        changed_audit = _manual_audit(changed, audits[index].source_identity)
        aggregate = suite.aggregate_e1_suite(
            plan, archives[:index] + (changed,) + archives[index + 1:],
            audits[:index] + (changed_audit,) + audits[index + 1:])
        result = self.summary((self.scheduled[index],), (), aggregate)
        self.assertEqual(result.resource_status, "FAIL_IDENTITY_OR_EVIDENCE")
        self.assertTrue(any("Scheduled receipt/archive" in reason for reason in result.reasons))

    def test_physical_input_count_must_equal_archive_trace_count(self):
        old = self.scheduled[0]
        events = tuple(event for event in old.events if event.event != "BEFORE_INPUT")
        events = tuple(replace(event, sequence=i, physical_inputs=0)
                       for i, event in enumerate(events))
        changed = _receipt_change(old, physical_inputs=0, events=events)
        self.assertEqual(self.summary((changed,) + self.scheduled[1:]).resource_status,
                         "FAIL_IDENTITY_OR_EVIDENCE")

    def test_missing_memory_is_incomplete_evidence(self):
        missing = _receipt_change(self.scheduled[0], status="INCOMPLETE",
                                  reason="MEMORY_MONITOR_INCOMPLETE", memory_evidence=None)
        result = self.summary((missing,) + self.scheduled[1:])
        self.assertEqual(result.resource_status, "INCOMPLETE")
        self.assertIn("MEMORY_MONITOR_INCOMPLETE", result.reasons)

    def test_missing_memory_in_corrupt_completion_is_incomplete_not_success(self):
        missing = _corrupt(self.scheduled[0], memory_evidence=None)
        result = self.summary((missing,) + self.scheduled[1:])
        self.assertEqual(result.resource_status, "INCOMPLETE")
        self.assertTrue(any("memory evidence" in reason for reason in result.reasons))

    def test_archive_budget_overlap_fails_and_gap_is_incomplete(self):
        original = self.scheduled[-1]
        overlap = _receipt_change(
            original, archive_used_before_bytes=original.archive_used_before_bytes - 1)
        result = self.summary(self.scheduled[:-1] + (overlap,), rechain=False)
        self.assertEqual(result.resource_status, "FAIL_IDENTITY_OR_EVIDENCE")
        self.assertTrue(any("overlap" in reason for reason in result.reasons))
        final = self.evaluated[-1]
        gap_receipt = _receipt_change(
            final.receipt, archive_used_before_bytes=final.receipt.archive_used_before_bytes + 1)
        result = self.summary(evaluated=self.evaluated[:-1] + (
            replace(final, receipt=gap_receipt),), rechain=False)
        self.assertEqual(result.resource_status, "INCOMPLETE")
        self.assertTrue(any("gap" in reason for reason in result.reasons))

    def test_resource_summary_accepts_semantically_failed_complete_archive_family(self):
        plan, archives, audits = _data()
        failed = replace(audits[0], discrepancies=("Declared public semantic failure",),
                         audit_status="FAIL")
        aggregate = suite.aggregate_e1_suite(plan, archives, (failed,) + audits[1:])
        self.assertEqual(aggregate.suite_status, "FAIL")
        identity = operational.capture_operational_source_identity(plan)
        receipts, used = [], 0
        for binding in aggregate.bindings:
            receipt = _manual_receipt(
                binding.schedule_entry, identity, (binding.archive, binding.audit, None),
                physical_inputs=len(binding.archive.result.traces), used=used)
            receipts.append(receipt)
            used = receipt.archive_used_after_bytes
        result = self.summary(tuple(receipts), (), aggregate)
        self.assertEqual(result.scheduled_received, 54)
        self.assertEqual(result.scheduled_complete, 54)
        self.assertEqual(result.resource_status, "INCOMPLETE")

    def test_cap_and_timeout_abort_reasons_are_retained(self):
        for reason in ("SYSTEM_CASE_TIMEOUT", "SYSTEM_JOB_TIMEOUT", "SYSTEM_INPUT_CAP",
                       "SYSTEM_MEMORY_CAP", "SYSTEM_ARCHIVE_CAP", "SYSTEM_PROCESS_ABORT"):
            changed = _receipt_change(self.scheduled[0], status="INCOMPLETE", reason=reason)
            with self.subTest(reason=reason):
                result = self.summary((changed,) + self.scheduled[1:])
                self.assertEqual(result.resource_status, "INCOMPLETE")
                self.assertIn(reason, result.reasons)

    def test_evaluator_falsification_does_not_relabel_complete_lifecycle(self):
        index = next(i for i, item in enumerate(self.evaluated)
                     if item.receipt.case_id == "S-LIFECYCLE")
        old = self.evaluated[index]
        binding = _aggregate().bindings[old.receipt.schedule_index]
        finding = _manual_evaluation(_aggregate(), binding, falsification=True)
        receipt = _manual_receipt(
            binding.schedule_entry,
            operational.capture_operational_source_identity(_data()[0]),
            (None, None, finding), kind="POST_HOC_EVALUATOR",
            used=old.receipt.archive_used_before_bytes)
        updated = operational.E1OperationResult(receipt, evaluation=finding)
        result = self.summary(evaluated=self.evaluated[:index] + (updated,) + self.evaluated[index + 1:])
        self.assertEqual(updated.receipt.status, "COMPLETE")
        self.assertEqual(dict(result.classifications)["G1_FALSIFICATION"], 1)
        self.assertEqual(result.evaluator_complete, 18)

    def test_summary_calls_no_execution_truth_or_persistence_boundary(self):
        with ExitStack() as stack:
            blocked = [stack.enter_context(patch.object(
                obj, name, side_effect=AssertionError("Forbidden pure summary boundary: " + name)))
                       for obj, name in (
                           (execution, "execute_scheduled_entry"),
                           (audit, "audit_scheduled_run"),
                           (e1_evaluator, "evaluate_scheduled_kp0"),
                           (e1_evaluator, "_fixed_answer"),
                           (evaluator, "evaluate_falsification"),
                           (core_engine.MinesweeperEngine, "step"),
                           (Path, "write_text"), (Path, "write_bytes"), (Path, "mkdir"))]
            self.summary()
        for call in blocked:
            call.assert_not_called()

    def test_summary_is_frozen_and_does_not_issue_qualification(self):
        result = self.summary()
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            result.resource_status = "changed"
        for name in ("E1_PASS", "E1_QUALIFIED", "RESEARCH_PASS", "progression_allowed",
                     "effectiveness_accepted"):
            self.assertFalse(hasattr(result, name))


class PurityTests(unittest.TestCase):
    def test_no_orchestration_persistence_or_qualification_ast(self):
        tree = ast.parse(inspect.getsource(operational))
        forbidden_calls = {
            "execute_e0", "run_e0", "select_supplement", "write_text",
            "write_bytes", "mkdir", "persist", "write_qualification_artifact",
            "read_official_database", "read_zini"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else "")
                self.assertNotIn(name, forbidden_calls)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn(node.value, {"E1_PASS", "E1_QUALIFIED", "RESEARCH_PASS"})
            if isinstance(node, (ast.For, ast.While, ast.ListComp, ast.GeneratorExp)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        name = child.func.id if isinstance(child.func, ast.Name) else (
                            child.func.attr if isinstance(child.func, ast.Attribute) else "")
                        self.assertNotEqual(name, "supervise_scheduled_run")

    def test_noop_target_has_no_engine_solver_or_board_access(self):
        tree = ast.parse(inspect.getsource(_noop_worker))
        forbidden = {"MinesweeperEngine", "execute_scheduled_entry", "generate_board",
                     "run_control_capture", "run_k_control", "run_k_p0", "analyze_decision"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else "")
                self.assertNotIn(name, forbidden)


if __name__ == "__main__":
    unittest.main()
