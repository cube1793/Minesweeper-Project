"""I6 containment tests: synthetic records/fake IPC and short disposable processes.

No board is generated, no solver/corpus/rehearsal runs, and temporary I2 roots
are not research artifacts. The execution adapter's semantic validator is
mocked only for deliberately minimal transport fixtures.
"""

import ast
from dataclasses import FrozenInstanceError, replace
import inspect
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_operational as op
from experiments import program_k_e2_records as records
from experiments import program_k_e2_store as store


def _envelope(**changes):
    value = op.OperatingEnvelope(
        concurrency=2, max_decision_wall_ms=100, max_arm_wall_ms=1000,
        max_case_wall_ms=5000, max_job_wall_ms=10000, max_launcher_wall_ms=15000,
        shadow_timeout_ms=100, max_physical_inputs=10,
        worker_memory_cap_bytes=100_000_000, coordinator_memory_cap_bytes=100_000_000,
        memory_cap_bytes=250_000_000, archive_cap_bytes=2_000_000,
        monitor_interval_ms=10, max_payload_bytes=100_000, max_ipc_frame_bytes=4096,
        aggregation_wall_ms=1000, validation_wall_ms=1000, publication_wall_ms=1000,
        readback_wall_ms=1000, report_wall_ms=1000)
    return replace(value, **changes)


def _plan(count=1):
    boards = tuple(records.BoardIdentity(index + 701, "invented-" + str(index), 2, 1, 1,
                                         (0, 0), "synthetic-generator", "synthetic-spec")
                   for index in range(count))
    return execution.make_work_plan(boards, protocol_seed=b"x" * 32, run_id="synthetic-unit")


def _bundle(work, kind, *, status=records.AuditStatus.PASS, extra=()):
    data = records.encode(work.board)
    return execution.WorkerBundle(work.position, kind, data, work.arm_order,
                                   (("boards", (data,) + extra),), (), status,
                                   () if status is records.AuditStatus.PASS else ("PRIVATE_ASSERTION_FALSIFIED",))


def _result(work, kind, status=records.AuditStatus.PASS, reason="ADMITTED", *, bundle=True):
    return op._OperationResult(op.UnitReceipt(work.position, kind, status, reason, 3, 0),
                               _bundle(work, kind, status=status) if bundle else None, ())


class _FakeJobAPI:
    def __init__(self):
        self.closed = self.terminated = 0

    def TerminateJobObject(self, job, code):
        self.terminated += 1
        return 1

    def CloseHandle(self, job):
        self.closed += 1
        return 1


def _success_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    channel = op._Channel(connection, envelope)
    channel.send(b"S")
    channel.result(execution.encode_bundle(_bundle(work, kind)))
    connection.close()


def _error_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    channel = op._Channel(connection, envelope)
    channel.send(b"S")
    channel.send(b"XWORKER_EXCEPTION")


def _malformed_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    connection.send_bytes(b"unknown-public-message")
    connection.recv_bytes(1)


def _nonzero_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    os._exit(7)


def _waiting_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    channel = op._Channel(connection, envelope)
    channel.send(b"S")
    threading.Event().wait(30)


def _decision_timeout_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    channel = op._Channel(connection, envelope)
    channel.send(b"S")
    channel.send(b"XDECISION_TIMEOUT")


def _input_cap_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    channel = op._Channel(connection, envelope)
    channel.send(b"S")
    channel.event("ARM_START", "CONTROL")
    for _ in range(envelope.max_physical_inputs + 1):
        channel.event("BEFORE_INPUT", "CONTROL")


def _oversize_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    channel = op._Channel(connection, envelope)
    channel.send(b"S")
    channel.send(b"H" + str(envelope.max_payload_bytes + 1).encode("ascii"))


def _failed_then_exit_worker(work, kind, first, envelope, connection, barrier):
    barrier.wait()
    channel = op._Channel(connection, envelope)
    channel.send(b"S")
    channel.result(execution.encode_bundle(_bundle(work, kind, status=records.AuditStatus.FAIL)))
    os._exit(9)


def _close_then_late_exit_worker(work, kind, first, envelope, connection, barrier):
    _success_worker(work, kind, first, envelope, connection, barrier)
    time.sleep(0.04)


class EnvelopeAndPlanTests(unittest.TestCase):
    def test_frozen_candidate_caps_and_exact_types(self):
        value = _envelope()
        self.assertEqual(value.fixed_report_receipt_allowance, 268435456)
        for field, invalid in (("concurrency", 3), ("concurrency", True),
                               ("max_decision_wall_ms", 30001), ("max_arm_wall_ms", 420001),
                               ("shadow_timeout_ms", 1001), ("max_launcher_wall_ms", 43200001),
                               ("memory_cap_bytes", 4294967297), ("archive_cap_bytes", 17179869185),
                               ("max_ipc_frame_bytes", 65537), ("max_physical_inputs", True),
                               ("max_payload_bytes", 67108865),
                               ("monitor_interval_ms", 0), ("max_case_wall_ms", 1.0),
                               ("fixed_report_receipt_allowance", 1)):
            with self.subTest(field=field), self.assertRaises(op.OperationalError):
                replace(value, **{field: invalid})
        with self.assertRaises(FrozenInstanceError):
            value.concurrency = 4

    def test_case_job_launcher_and_shadow_caps_are_separate(self):
        value = _envelope()
        self.assertNotEqual(value.max_case_wall_ms, value.max_job_wall_ms)
        self.assertNotEqual(value.max_job_wall_ms, value.max_launcher_wall_ms)
        self.assertNotEqual(value.shadow_timeout_ms, value.max_arm_wall_ms)
        for changes in (dict(max_arm_wall_ms=50), dict(max_case_wall_ms=500),
                        dict(max_job_wall_ms=1000), dict(max_launcher_wall_ms=1000),
                        dict(monitor_interval_ms=101), dict(max_payload_bytes=3000000)):
            with self.assertRaises(op.OperationalError):
                replace(value, **changes)

    def test_finite_work_plan_has_exact_prospective_flags(self):
        first, second = _plan(3), _plan(3)
        self.assertEqual(first, second)
        self.assertIs(op.validate_work_plan(first), first)
        changed = (replace(first[0], oracle_b_selected=not first[0].oracle_b_selected),) + first[1:]
        for bad in ([], (), first[::-1], first[:-1] + (first[0],), changed):
            with self.assertRaises(ValueError):
                op.validate_work_plan(bad)
        duplicate = (first[0], replace(first[1], board=first[0].board))
        with self.assertRaises(ValueError):
            op.validate_work_plan(duplicate)

    def test_no_implicit_real_corpus_identity_in_tests(self):
        for work in _plan(4):
            self.assertLess(work.board.game_index, 1000000000)
            self.assertEqual(work.board.generator_identity, "synthetic-generator")


class WatchdogAndMemoryTests(unittest.TestCase):
    def test_watchdog_samples_only_declared_regions_and_excludes_initial_input(self):
        wanted, other = object(), object()
        report = []
        watchdog = op.DecisionWatchdog(17, (wanted,), (), _envelope(), report.append)
        unrelated = SimpleNamespace(f_code=other, f_lineno=2, f_back=None)
        frame = SimpleNamespace(f_code=wanted, f_lineno=2, f_back=unrelated)
        self.assertFalse(watchdog.sample(frames={17: unrelated}, now_ns=0))
        self.assertFalse(watchdog.sample(frames={17: frame}, now_ns=10))
        self.assertFalse(watchdog.sample(frames={17: frame}, now_ns=99_000_010))
        self.assertTrue(watchdog.sample(frames={17: frame}, now_ns=100_000_010))
        self.assertEqual(report, ["DECISION_TIMEOUT"])
        self.assertTrue(watchdog.sample(frames={17: frame}, now_ns=200_000_010))
        self.assertEqual(len(report), 1)

    def test_region_bridge_and_input_reset(self):
        code = object()
        watchdog = op.DecisionWatchdog(1, (), ((code, 20, 30),), _envelope(), lambda _: None)
        frame = SimpleNamespace(f_code=code, f_lineno=20, f_back=None)
        watchdog.sample(frames={1: frame}, now_ns=0)
        watchdog.reset()
        self.assertFalse(watchdog.sample(frames={1: frame}, now_ns=200000000))
        frame.f_lineno = 31
        self.assertFalse(watchdog.sample(frames={1: frame}, now_ns=400000000))

    def test_watchdog_thread_is_explicit_and_reaped(self):
        watchdog = op.DecisionWatchdog(threading.get_ident(), (), (), _envelope(), lambda _: None)
        self.assertIsNone(watchdog._thread)
        watchdog.start()
        watchdog.stop()
        self.assertFalse(watchdog._thread.is_alive())
        self.assertFalse(watchdog.timed_out)

    def test_shared_memory_sums_all_live_worker_trees_plus_parent(self):
        ledger = op._MemoryLedger(_envelope())
        with patch.object(op.harness, "_coordinator_private_bytes", return_value=300):
            first, breach = ledger.sample("a", 100, "0:PRIMARY", 2)
            second, breach2 = ledger.sample("b", 200, "1:PRIMARY", 3)
            self.assertEqual((first.worker_bytes, first.combined_bytes), (100, 400))
            self.assertEqual((second.worker_bytes, second.coordinator_bytes, second.combined_bytes), (300, 300, 600))
            self.assertFalse(breach or breach2)
            self.assertIs(second.method, records.MemoryMethod.PRIVATE_BYTES)
            self.assertIs(second.process_role, records.ProcessRole.COMBINED)
            ledger.remove("a")
            third, _ = ledger.sample("b", 200, "1:PRIMARY", 4)
            self.assertEqual(third.worker_bytes, 200)

    def test_worker_coordinator_and_combined_memory_caps(self):
        envelope = _envelope(worker_memory_cap_bytes=100, coordinator_memory_cap_bytes=100,
                             memory_cap_bytes=150)
        with patch.object(op.harness, "_coordinator_private_bytes", return_value=80):
            ledger = op._MemoryLedger(envelope)
            self.assertTrue(ledger.sample("a", 80, "unit", 1)[1])
        with patch.object(op.harness, "_coordinator_private_bytes", return_value=True):
            with self.assertRaises(op.OperationalError):
                ledger.sample("a", 0, "unit", 1)


class WorkerAdapterTests(unittest.TestCase):
    def run_worker(self, kind, operation):
        frames = []
        state = SimpleNamespace(released=False, closed=False)
        connection = SimpleNamespace(send_bytes=frames.append, recv_bytes=lambda size: b"+",
                                     close=lambda: setattr(state, "closed", True))
        barrier = SimpleNamespace(wait=lambda: setattr(state, "released", True))
        work = _plan()[0]
        method = {execution.WorkerKind.PRIMARY: "execute_primary",
                  execution.WorkerKind.DETERMINISM: "execute_repeat",
                  execution.WorkerKind.K_CONTROL: "execute_k_control"}[kind]
        def invoke(*args, **kwargs):
            self.assertTrue(state.released)
            return operation(work, kind, kwargs)
        first = None if kind is execution.WorkerKind.PRIMARY else execution.encode_bundle(
            _bundle(work, execution.WorkerKind.PRIMARY))
        with patch.object(execution, method, side_effect=invoke) as called, \
             patch.object(execution, "decision_watchdog_targets", return_value=((), ())), \
             patch.object(execution, "revalidate_bundle", side_effect=lambda value, *args, **kwargs: value):
            op._worker_main(work, kind, first, _envelope(), connection, barrier)
        self.assertEqual(called.call_count, 1)
        self.assertTrue(state.closed)
        self.assertFalse(any(value.name == "program-k-e2-watchdog" and value.is_alive()
                             for value in threading.enumerate()))
        return frames

    def test_three_worker_dispatches_wait_for_release_and_close_every_monitor(self):
        def run(work, kind, kwargs):
            arm = "K_CONTROL" if kind is execution.WorkerKind.K_CONTROL else "CONTROL"
            kwargs["observer"]("ARM_START", arm)
            kwargs["observer"]("BEFORE_INPUT", arm)
            kwargs["abort_check"]()
            kwargs["observer"]("ARM_END", arm)
            return _bundle(work, kind)
        for kind in execution.WorkerKind:
            with self.subTest(kind=kind):
                frames = self.run_worker(kind, run)
                self.assertEqual(frames[0], b"S")
                self.assertEqual(frames[-1], b"F")
                self.assertEqual(sum(frame.startswith(b"E") for frame in frames), 3)

    def test_worker_input_cap_aborts_without_an_extra_physical_input(self):
        def run(work, kind, kwargs):
            kwargs["observer"]("ARM_START", "CONTROL")
            for _ in range(kwargs["max_physical_inputs"] + 1):
                kwargs["observer"]("BEFORE_INPUT", "CONTROL")
            self.fail("input cap did not abort")
        frames = self.run_worker(execution.WorkerKind.PRIMARY, run)
        self.assertEqual(frames[-1], b"XPHYSICAL_INPUT_CAP")
        self.assertEqual(sum(b"BEFORE_INPUT" in frame for frame in frames), 10)

    def test_private_exception_details_never_cross_ipc(self):
        def run(work, kind, kwargs):
            raise RuntimeError("hidden-answer coordinates [(11, 12)]")
        frames = self.run_worker(execution.WorkerKind.PRIMARY, run)
        self.assertEqual(frames[-1], b"XWORKER_EXCEPTION")
        self.assertNotIn(b"hidden-answer", b"".join(frames))

    def test_missing_evidence_and_identity_mismatch_are_distinct_static_diagnoses(self):
        for error, frame in ((execution.E2EvidenceIncomplete("private rejected premise"),
                              b"XREQUIRED_EVIDENCE_INCOMPLETE"),
                             (execution.E2IdentityMismatch("private source details"),
                              b"XIMPLEMENTATION_IDENTITY_FAIL")):
            def run(work, kind, kwargs):
                raise error
            with self.subTest(error=type(error)):
                frames = self.run_worker(execution.WorkerKind.PRIMARY, run)
                self.assertEqual(frames[-1], frame)
                self.assertNotIn(b"private", b"".join(frames))


class DisposableLifecycleTests(unittest.TestCase):
    def run_target(self, target, *, envelope=None, cancel=None, job_offset=0, launcher_offset=0,
                   kind=execution.WorkerKind.PRIMARY):
        envelope = _envelope() if envelope is None else envelope
        work = _plan()[0]
        api = _FakeJobAPI()
        attached = []
        def attach(pid, budget):
            attached.append((pid, budget))
            return api, object(), lambda: 512
        started = time.monotonic_ns()
        with patch.object(op.harness, "_attach_memory_job", side_effect=attach), \
             patch.object(op.harness, "_coordinator_private_bytes", return_value=512), \
             patch.object(execution, "revalidate_bundle", side_effect=lambda bundle, *args, **kwargs: bundle):
            prior = None if kind is execution.WorkerKind.PRIMARY else execution.encode_bundle(
                _bundle(work, execution.WorkerKind.PRIMARY))
            result = op._supervise_operation(work, kind, prior, envelope,
                op._MemoryLedger(envelope), threading.Event() if cancel is None else cancel,
                started - job_offset, started - launcher_offset, worker_target=target)
        self.assertLess(time.monotonic_ns() - started, 10_000_000_000)
        self.assertFalse(any(child.pid in {pid for pid, _ in attached} for child in op.multiprocessing.active_children()))
        self.assertEqual(api.closed, len(attached))
        self.assertFalse(any(thread.name == "program-k-e2-ipc-reader" and thread.is_alive()
                             for thread in threading.enumerate()))
        return result, attached

    def test_worker_start_attach_release_finish_and_reap(self):
        result, attached = self.run_target(_success_worker)
        self.assertEqual(len(attached), 1)
        self.assertIs(result.receipt.status, records.AuditStatus.PASS, result.receipt)
        self.assertEqual(result.receipt.exit_code, 0)
        self.assertIsNotNone(result.bundle)
        self.assertTrue(result.samples)

    def test_worker_exception_is_incomplete_without_private_exception_text(self):
        result, attached = self.run_target(_error_worker)
        self.assertEqual(result.receipt.reason, "WORKER_EXCEPTION")
        self.assertIs(result.receipt.status, records.AuditStatus.INCOMPLETE)
        self.assertEqual(len(attached), 1)

    def test_complete_ipc_then_eof_before_process_exit_is_success(self):
        result, _ = self.run_target(_close_then_late_exit_worker)
        self.assertIs(result.receipt.status, records.AuditStatus.PASS, result.receipt)

    def test_malformed_ipc_is_diagnosed_failure(self):
        result, _ = self.run_target(_malformed_worker)
        self.assertIs(result.receipt.status, records.AuditStatus.FAIL)
        self.assertEqual(result.receipt.reason, "MALFORMED_IPC_OR_IDENTITY")

    def test_nonzero_process_exit_is_not_pass(self):
        result, _ = self.run_target(_nonzero_worker)
        self.assertIs(result.receipt.status, records.AuditStatus.INCOMPLETE)
        self.assertEqual(result.receipt.exit_code, 7)

    def test_diagnosed_audit_fail_survives_later_nonzero_exit(self):
        result, _ = self.run_target(_failed_then_exit_worker)
        self.assertIs(result.receipt.status, records.AuditStatus.FAIL)
        self.assertEqual(result.receipt.exit_code, 9)

    def test_kcontrol_failed_worker_is_never_reused(self):
        first, first_attached = self.run_target(_error_worker, kind=execution.WorkerKind.K_CONTROL)
        second, second_attached = self.run_target(_success_worker, kind=execution.WorkerKind.K_CONTROL)
        self.assertIs(first.receipt.status, records.AuditStatus.INCOMPLETE)
        self.assertIs(second.receipt.status, records.AuditStatus.PASS)
        self.assertNotEqual(first_attached[0][0], second_attached[0][0])

    def test_case_timeout_reaps_waiting_worker(self):
        envelope = _envelope(max_decision_wall_ms=10, max_arm_wall_ms=20, max_case_wall_ms=80)
        result, _ = self.run_target(_waiting_worker, envelope=envelope)
        self.assertEqual(result.receipt.reason, "CASE_TIMEOUT")

    def test_job_and_launcher_deadlines_remain_distinct(self):
        for name, job_offset, launcher_offset in (("JOB_TIMEOUT", 20_000_000_000, 0),
                                                 ("LAUNCHER_TIMEOUT", 0, 20_000_000_000)):
            with self.subTest(name=name):
                result, _ = self.run_target(_waiting_worker, job_offset=job_offset,
                                             launcher_offset=launcher_offset)
                self.assertEqual(result.receipt.reason, name)

    def test_parent_cancellation_before_start_has_no_child(self):
        cancel = threading.Event()
        cancel.set()
        result, attached = self.run_target(_success_worker, cancel=cancel)
        self.assertEqual(attached, [])
        self.assertEqual(result.receipt.reason, "CANCELLED")

    def test_explicit_decision_watchdog_and_physical_input_caps(self):
        for target, reason in ((_decision_timeout_worker, "DECISION_TIMEOUT"),
                               (_input_cap_worker, "PHYSICAL_INPUT_CAP"),
                               (_oversize_worker, "IPC_PAYLOAD_CAP")):
            with self.subTest(reason=reason):
                result, _ = self.run_target(target)
                self.assertEqual(result.receipt.reason, reason)
                self.assertIs(result.receipt.status, records.AuditStatus.INCOMPLETE)

    def test_attachment_failure_never_releases_worker(self):
        envelope, work = _envelope(), _plan()[0]
        with patch.object(op.harness, "_attach_memory_job", side_effect=OSError("static-test")):
            start = time.monotonic_ns()
            result = op._supervise_operation(work, execution.WorkerKind.PRIMARY, None, envelope,
                op._MemoryLedger(envelope), threading.Event(), start, start, worker_target=_success_worker)
        self.assertIs(result.receipt.status, records.AuditStatus.INCOMPLETE)
        self.assertIsNone(result.bundle)


class StrictReadbackTests(unittest.TestCase):
    @staticmethod
    def sealed_fixture(directory, *, populated=True):
        seals = []
        for name in tuple(execution.STREAM_NAMES) + ("operations", "resources"):
            with store.StreamWriter(directory, name) as writer:
                if populated and name == "boards":
                    writer.append((0,), _plan()[0].board)
                seals.append(writer.seal())
        return tuple(seals)

    def test_exact_readback_scans_every_stream_once_and_returns_detached_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            seals = self.sealed_fixture(directory)
            with patch.object(store, "scan_stream", wraps=store.scan_stream) as scan:
                verified = op.readback_streams(directory, seals, _envelope())
            self.assertEqual(verified, seals)
            self.assertIs(type(verified), tuple)
            self.assertEqual([call.args[1] for call in scan.call_args_list], [seal.name for seal in seals])
            self.assertTrue(all(callable(call.kwargs["visit"]) for call in scan.call_args_list))
            self.assertTrue(all(first is not second for first, second in zip(verified, seals)))
            with self.assertRaises(FrozenInstanceError):
                verified[0].record_count = 9
            self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_exact_unique_declared_seals_are_required_before_any_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            seals = self.sealed_fixture(directory)
            cases = (list(seals), seals[:-1], seals + (seals[0],),
                     (seals[0],) + seals[:-1],
                     (replace(seals[0], name="unexpected_stream"),) + seals[1:],
                     (object(),) + seals[1:])
            for invalid in cases:
                with self.subTest(value=type(invalid).__name__), \
                     patch.object(store, "scan_stream") as scan, \
                     self.assertRaisesRegex(op.OperationalError, "^READBACK_INTEGRITY_FAIL$"):
                    op.readback_streams(directory, invalid, _envelope())
                scan.assert_not_called()

    def test_every_digest_field_must_match_the_seal_without_retry(self):
        original = store.scan_stream
        with tempfile.TemporaryDirectory() as directory:
            seals = self.sealed_fixture(directory)
            for field, value in (("name", "runtime"), ("sha256", "f" * 64),
                                 ("byte_length", seals[0].byte_length + 1),
                                 ("record_count", seals[0].record_count + 1)):
                def mismatch(root, name, **kwargs):
                    return replace(original(root, name, **kwargs), **{field: value})
                with self.subTest(field=field), patch.object(store, "scan_stream", side_effect=mismatch) as scan, \
                     self.assertRaisesRegex(op.OperationalError, "^READBACK_INTEGRITY_FAIL$"):
                    op.readback_streams(directory, seals, _envelope())
                self.assertEqual(scan.call_count, 1)

    def test_readback_deadline_is_enforced_inside_the_scanner_visitor(self):
        original = store.scan_stream
        clock = [0]
        def expired_record(root, name, *, visit):
            def expire(key, record):
                clock[0] = 1_000_000
                visit(key, record)
            return original(root, name, visit=expire)
        with tempfile.TemporaryDirectory() as directory:
            seals = self.sealed_fixture(directory)
            with patch.object(op.time, "monotonic_ns", side_effect=lambda: clock[0]), \
                 patch.object(store, "scan_stream", side_effect=expired_record) as scan, \
                 self.assertRaisesRegex(op.OperationalAbort, "^READBACK_TIMEOUT$"):
                op.readback_streams(directory, seals, _envelope(readback_wall_ms=1))
            self.assertEqual(scan.call_count, 1)

    def test_empty_stream_readback_still_checks_deadline_after_scan(self):
        original = store.scan_stream
        clock = [0]
        def expired_empty(root, name, **kwargs):
            value = original(root, name, **kwargs)
            clock[0] = 1_000_000
            return value
        with tempfile.TemporaryDirectory() as directory:
            seals = self.sealed_fixture(directory, populated=False)
            with patch.object(op.time, "monotonic_ns", side_effect=lambda: clock[0]), \
                 patch.object(store, "scan_stream", side_effect=expired_empty) as scan, \
                 self.assertRaisesRegex(op.OperationalAbort, "^READBACK_TIMEOUT$"):
                op.readback_streams(directory, seals, _envelope(readback_wall_ms=1))
            self.assertEqual(scan.call_count, 1)


class StreamingCoordinatorTests(unittest.TestCase):
    def run_plan(self, plan, directory, *, workflow=None, envelope=None, cancel=None):
        def default(work, *args):
            return tuple(_result(work, kind) for kind in op._kinds(work))
        with patch.object(op, "_workflow", side_effect=default if workflow is None else workflow), \
             patch.object(execution, "revalidate_bundle", side_effect=lambda bundle, *args, **kwargs: bundle), \
             patch.object(op.harness, "_coordinator_private_bytes", return_value=512):
            return op.coordinate(plan, directory, _envelope() if envelope is None else envelope, cancel=cancel)

    def test_production_pass_requires_exactly_one_readback_scan_per_declared_stream(self):
        names = tuple(execution.STREAM_NAMES) + ("operations", "resources")
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(store, "scan_stream", wraps=store.scan_stream) as scan:
            result = self.run_plan(_plan(), directory)
            self.assertIs(result.status, records.AuditStatus.PASS)
            self.assertEqual([call.args[1] for call in scan.call_args_list], list(names))
            self.assertEqual(tuple(digest.name for digest in result.streams), names)
            self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_production_readback_digest_mismatch_is_incomplete_without_a_second_scan(self):
        original = store.scan_stream
        def mismatch(root, name, **kwargs):
            return replace(original(root, name, **kwargs), sha256="f" * 64)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(store, "scan_stream", side_effect=mismatch) as scan:
            result = self.run_plan(_plan(), directory)
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertIn("READBACK_INTEGRITY_FAIL", result.reason_codes)
            self.assertEqual(scan.call_count, 1)
            self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_production_readback_rejects_record_and_key_corruption(self):
        original = op._EvidenceSink.seal
        for mode in ("record", "descending_key"):
            def corrupt(sink):
                seals = original(sink)
                path = sink.writers["boards"].path
                lines = path.read_bytes().splitlines(keepends=True)
                self.assertGreaterEqual(len(lines), 2)
                if mode == "record":
                    lines[0] = lines[0].split(b"\t", 1)[0] + b"\t{}\n"
                else:
                    lines[0], lines[1] = lines[1], lines[0]
                path.write_bytes(b"".join(lines))
                return seals
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory, \
                 patch.object(op._EvidenceSink, "seal", corrupt), \
                 patch.object(store, "scan_stream", wraps=store.scan_stream) as scan:
                result = self.run_plan(_plan(), directory)
                self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
                self.assertIn("READBACK_INTEGRITY_FAIL", result.reason_codes)
                self.assertEqual(scan.call_count, 1)
                self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_production_readback_timeout_is_incomplete_but_preserves_diagnosed_fail(self):
        original = store.scan_stream
        real_clock = time.monotonic_ns
        offset = [0]
        def slow(root, name, **kwargs):
            value = original(root, name, **kwargs)
            offset[0] += 101_000_000
            return value
        for primary_status in (records.AuditStatus.PASS, records.AuditStatus.FAIL):
            offset[0] = 0
            def workflow(work, *args):
                return tuple(_result(work, kind, primary_status) for kind in op._kinds(work))
            with self.subTest(primary_status=primary_status), tempfile.TemporaryDirectory() as directory, \
                 patch.object(op.time, "monotonic_ns", side_effect=lambda: real_clock() + offset[0]), \
                 patch.object(store, "scan_stream", side_effect=slow) as scan:
                result = self.run_plan(_plan(), directory, workflow=workflow,
                                       envelope=_envelope(readback_wall_ms=100))
                expected = records.AuditStatus.FAIL if primary_status is records.AuditStatus.FAIL else records.AuditStatus.INCOMPLETE
                self.assertIs(result.status, expected)
                self.assertIn("READBACK_TIMEOUT", result.reason_codes)
                self.assertEqual(scan.call_count, 1)
                names = [call.args[1] for call in scan.call_args_list]
                self.assertEqual(len(names), len(set(names)))
                self.assertEqual(names, [execution.STREAM_NAMES[0]])
                self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_production_readback_integrity_error_preserves_prior_fail_and_static_reason(self):
        def workflow(work, *args):
            return tuple(_result(work, kind, records.AuditStatus.FAIL) for kind in op._kinds(work))
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(store, "scan_stream", side_effect=store.StoreError("private corrupt path")) as scan:
            result = self.run_plan(_plan(), directory, workflow=workflow)
            self.assertIs(result.status, records.AuditStatus.FAIL)
            self.assertIn("READBACK_INTEGRITY_FAIL", result.reason_codes)
            self.assertNotIn("private", repr(result.reason_codes))
            self.assertEqual(scan.call_count, 1)

    def test_ordered_admission_is_independent_of_completion_arrival(self):
        plan = _plan(3)
        completed = []
        lock = threading.Lock()
        active = peak = 0
        def workflow(work, *args):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            if work.position == 0:
                time.sleep(0.03)
            with lock:
                active -= 1
                completed.append(work.position)
            return tuple(_result(work, kind) for kind in op._kinds(work))
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_plan(plan, directory, workflow=workflow)
            self.assertIs(result.status, records.AuditStatus.PASS)
            self.assertLessEqual(peak, 2)
            self.assertEqual(len(result.receipts), 9)
            self.assertEqual([receipt.position for receipt in result.receipts], [0] * 3 + [1] * 3 + [2] * 3)
            seen = []
            digest = store.scan_stream(directory, "boards", visit=lambda key, value: seen.append((key, value)))
            self.assertEqual([key for key, _ in seen], [(p, k, 0) for p in range(3) for k in range(3)])
            self.assertEqual(digest, next(item for item in result.streams if item.name == "boards"))
            self.assertEqual(result.archive_bytes, sum(path.stat().st_size for path in Path(directory).glob("*.jsonl")))
            self.assertFalse((Path(directory) / "COMPLETE.json").exists())
        self.assertEqual(sorted(completed), [0, 1, 2])

    def test_progress_is_monotone_and_checkpointed_before_count_advances(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_plan(_plan(2), directory)
            events = []
            store.scan_stream(directory, "operations", visit=lambda key, value: events.append(value))
            self.assertEqual([event.ordinal for event in events], list(range(len(events))))
            progress = [event.unit_id for event in events if event.event_kind is records.EventKind.PROGRESS]
            self.assertEqual(progress, ["durable_primary_count:1", "durable_primary_count:2"])
            self.assertEqual(result.durable_units, 6)
            self.assertEqual(result.durable_primary_boards, 2)
            self.assertEqual(events[-1].unit_id, "coordinator:ADMISSION_END")
            self.assertNotIn("ETA", repr(events))

    def test_cancelled_plan_retains_every_terminal_without_running(self):
        scheduled = tuple(f"{position}:{kind}" for position in range(2)
                          for kind in ("PRIMARY", "DETERMINISM", "K_CONTROL"))
        # Full-source parent memory is incidental, not this cancellation test's authority.
        for memory, reason, coordinator_reasons in (
                (512, "CANCELLED_BEFORE_START", ()),
                (100_000_001, "MEMORY_CAP", ("MEMORY_CAP",))):
            with self.subTest(coordinator_bytes=memory), tempfile.TemporaryDirectory() as directory:
                cancel = threading.Event()
                cancel.set()
                with patch.object(op, "_workflow", side_effect=AssertionError("cancelled work executed")) as workflow, \
                     patch.object(op.harness, "_coordinator_private_bytes", return_value=memory):
                    result = op.coordinate(_plan(2), directory, _envelope(), cancel=cancel)
                workflow.assert_not_called()
                self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
                self.assertEqual(result.reason_codes, coordinator_reasons)
                self.assertEqual(len(result.receipts), 6)
                self.assertEqual(tuple(f"{value.position}:{value.kind.value}" for value in result.receipts), scheduled)
                self.assertTrue(all(value.status is records.AuditStatus.INCOMPLETE for value in result.receipts))
                self.assertEqual(tuple(value.reason for value in result.receipts), (reason,) * 6)
                events = []
                store.scan_stream(directory, "operations", visit=lambda key, value: events.append(value))
                errors = tuple(event for event in events if event.event_kind is records.EventKind.ERROR)
                unit_errors = tuple(event for event in errors if not event.unit_id.startswith("coordinator:"))
                coordinator_errors = tuple(event for event in errors if event.unit_id.startswith("coordinator:"))
                self.assertEqual(tuple(event.unit_id for event in unit_errors),
                                 tuple(unit + ":" + reason for unit in scheduled))
                self.assertEqual(tuple(event.unit_id for event in coordinator_errors),
                                 tuple("coordinator:" + value for value in coordinator_reasons))
                self.assertTrue(all(event.status is records.OperationStatus.INCOMPLETE for event in errors))

    def test_diagnosed_fail_dominates_other_incomplete_units(self):
        def workflow(work, *args):
            return (_result(work, execution.WorkerKind.PRIMARY, records.AuditStatus.FAIL, "SEMANTIC_FAIL"),
                    _result(work, execution.WorkerKind.DETERMINISM, records.AuditStatus.INCOMPLETE, "TIMEOUT", bundle=False),
                    _result(work, execution.WorkerKind.K_CONTROL))
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_plan(_plan(), directory, workflow=workflow)
            self.assertIs(result.status, records.AuditStatus.FAIL)
            self.assertIs(result.receipts[0].status, records.AuditStatus.FAIL)

    def test_archive_cap_preserves_prefix_and_reserved_terminal_events(self):
        def workflow(work, *args):
            first = _result(work, execution.WorkerKind.PRIMARY)
            if work.position == 1:
                huge = _bundle(work, execution.WorkerKind.PRIMARY,
                               extra=(records.encode(work.board),) * 100)
                first = replace(first, bundle=huge)
            return (first,) + tuple(_result(work, kind) for kind in op._kinds(work)[1:])
        envelope = _envelope(concurrency=1, archive_cap_bytes=50000, max_payload_bytes=45000)
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_plan(_plan(2), directory, workflow=workflow, envelope=envelope)
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertTrue(any(value.reason == "ARCHIVE_CAP" for value in result.receipts))
            self.assertEqual(len(result.receipts), 6)
            self.assertLessEqual(result.archive_bytes, envelope.archive_cap_bytes)
            seen = []
            store.scan_stream(directory, "boards", visit=lambda key, value: seen.append(key))
            self.assertIn((0, 0, 0), seen)
            self.assertNotIn((1, 0, 0), seen)

    def test_no_overwrite_and_close_never_claims_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = op._EvidenceSink(directory, _envelope(), 1)
            sink.close()
            self.assertFalse(sink.sealed)
            with self.assertRaises(store.StoreError):
                op._EvidenceSink(directory, _envelope(), 1)
            self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_checkpoint_failure_cannot_advance_durable_counter(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = op._EvidenceSink(directory, _envelope(), 1)
            try:
                with patch.object(sink, "checkpoint", side_effect=store.StoreError("synthetic-fsync-failure")):
                    with self.assertRaises(store.StoreError):
                        sink.admit(_result(_plan()[0], execution.WorkerKind.PRIMARY))
                self.assertEqual(sink.durable_units, 0)
                self.assertEqual(sink.durable_boards, 0)
            finally:
                sink.close()

    def test_parent_publication_cap_is_retained_after_durable_prefix(self):
        original = op._EvidenceSink.admit
        def slow(sink, result):
            receipt = original(sink, result)
            time.sleep(0.003)
            return receipt
        with tempfile.TemporaryDirectory() as directory, patch.object(op._EvidenceSink, "admit", slow):
            result = self.run_plan(_plan(), directory, envelope=_envelope(publication_wall_ms=1))
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertIn("PUBLICATION_TIMEOUT", result.reason_codes)
            events = []
            store.scan_stream(directory, "operations", visit=lambda key, value: events.append(value))
            self.assertTrue(any(value.unit_id == "coordinator:PUBLICATION_TIMEOUT" for value in events))

    def test_expired_launcher_prevents_any_new_worker_and_classifies_whole_plan(self):
        envelope = _envelope()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(op, "_workflow", side_effect=AssertionError("expired launcher executed")), \
             patch.object(op.harness, "_coordinator_private_bytes", return_value=512):
            result = op.coordinate(_plan(), directory, envelope,
                launcher_started_ns=time.monotonic_ns() - envelope.max_launcher_wall_ms * 1000000)
            self.assertEqual(len(result.receipts), 3)
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertIn("LAUNCHER_TIMEOUT", result.reason_codes)

    def test_final_seal_deadline_cannot_claim_global_completed(self):
        original = op._EvidenceSink.seal
        def slow(sink):
            values = original(sink)
            time.sleep(0.12)
            return values
        envelope = _envelope(max_decision_wall_ms=10, max_arm_wall_ms=20, max_case_wall_ms=30,
                             max_job_wall_ms=100, max_launcher_wall_ms=100,
                             aggregation_wall_ms=50, validation_wall_ms=50, publication_wall_ms=50,
                             readback_wall_ms=50, report_wall_ms=50)
        with tempfile.TemporaryDirectory() as directory, patch.object(op._EvidenceSink, "seal", slow):
            result = self.run_plan(_plan(), directory, envelope=envelope)
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertTrue(set(result.reason_codes) & {"JOB_TIMEOUT", "LAUNCHER_TIMEOUT"})
            events = []
            store.scan_stream(directory, "operations", visit=lambda key, value: events.append(value))
            self.assertFalse(any(value.unit_id == "coordinator" and value.event_kind is records.EventKind.END
                                 and value.status is records.OperationStatus.COMPLETED for value in events))

    def test_workflow_never_retries_and_missing_primary_classifies_maintenance(self):
        work = _plan()[0]
        with patch.object(op, "_supervise_operation", return_value=op._missing(
                work, execution.WorkerKind.PRIMARY, "CASE_TIMEOUT")) as supervise:
            results = op._workflow(work, _envelope(), None, threading.Event(), 1, 1)
        self.assertEqual(supervise.call_count, 1)
        self.assertEqual(len(results), 3)
        self.assertEqual([value.receipt.reason for value in results[1:]], ["PRIMARY_PREMISES_MISSING"] * 2)

    def test_kcontrol_always_has_a_distinct_fresh_supervision_call(self):
        work = _plan()[0]
        kinds = []
        def supervise(work, kind, *args):
            kinds.append(kind)
            return _result(work, kind)
        with patch.object(op, "_supervise_operation", side_effect=supervise):
            op._workflow(work, _envelope(), None, threading.Event(), 1, 1)
        self.assertEqual(kinds, list(op._kinds(work)))
        self.assertEqual(len(kinds), len(set(kinds)))


class OperationalPurityTests(unittest.TestCase):
    def test_runtime_import_scope_and_no_e1_suite_or_research_verdict(self):
        tree = ast.parse(inspect.getsource(op))
        allowed = {"program_k_e2_execution", "program_k_e2_records", "program_k_e2_store", "program_k_harness"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "experiments":
                self.assertTrue(all(alias.name in allowed for alias in node.names))
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                self.assertNotIn(name, {"settrace", "setprofile", "generate_board", "run_k_p0", "run_k_control",
                                        "execute_e0", "git", "connect", "analyze_primary", "build_report"})
        self.assertNotIn("RESEARCH_PASS", inspect.getsource(op))


if __name__ == "__main__":
    unittest.main()
