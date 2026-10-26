"""I6 containment tests: synthetic records/fake IPC and short disposable processes.

No board is generated, no solver/corpus/rehearsal runs, and temporary I2 roots
are not research artifacts. The execution adapter's semantic validator is
mocked only for deliberately minimal transport fixtures.
"""

import ast
import builtins
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, replace
import inspect
import json
import os
from pathlib import Path
import pickle
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


def _r0_literal_worker(production_target, arguments, corrupt_telemetry=False):
    """Test-only literal materialization, then the unchanged production target."""
    from tests.test_program_k_e2_execution import _literal_context
    accepted = op._Channel.result
    def result(channel, data, *, tags=(b"H", b"D", b"F")):
        if corrupt_telemetry and tags == (b"T", b"U", b"V"):
            value = json.loads(data)
            value[:4] = [0, 0, 0, []]
            data = json.dumps(value, separators=(",", ":")).encode("ascii")
        return accepted(channel, data, tags=tags)
    with _literal_context(arguments[0]), patch.object(op._Channel, "result", new=result):
        production_target(*arguments)


def _r0_ordering_worker(arguments, mode):
    """Synthetic IPC adversary; no board materialization or solver execution."""
    work, kind, first, envelope, connection, barrier, observing = arguments
    barrier.wait()
    channel = op._Channel(connection, envelope)
    expected = ("K_CONTROL",) if kind is execution.WorkerKind.K_CONTROL else ("CONTROL", "K_P0")
    extra = "CONTROL" if kind is execution.WorkerKind.K_CONTROL else "K_CONTROL"
    arms = {"early": (), "partial": expected[:-1], "wrong": (extra,),
            "extra": expected + (extra,), "late_arm": expected}[mode]
    try:
        channel.send(b"S")
        for arm in arms:
            channel.event("ARM_START", arm)
            channel.event("ARM_END", arm)
        channel.send(b"T14")
        if mode == "late_arm":
            channel.event("ARM_START", extra)
    except (EOFError, OSError, op.OperationalAbort):
        pass
    finally:
        connection.close()


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


class R0TransportOrderingTests(unittest.TestCase):
    def run_ordering(self, kind, mode):
        context = op.multiprocessing.get_context("spawn")
        work = replace(_plan()[0], oracle_b_selected=False)
        envelope, api, pids = _envelope(), _FakeJobAPI(), []
        def process(*, target, args):
            self.assertIs(target, op._worker_main)
            self.assertIs(args[-1], True)
            return context.Process(target=_r0_ordering_worker, args=(args, mode))
        def attach(pid, budget):
            pids.append(pid)
            return api, object(), lambda: 512
        proxy = SimpleNamespace(Pipe=context.Pipe, Event=context.Event, Process=process)
        started = time.monotonic_ns()
        with patch.object(op.multiprocessing, "get_context", return_value=proxy), \
                patch.object(op.harness, "_attach_memory_job", side_effect=attach), \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=512):
            result = op._supervise_operation(work, kind, None, envelope,
                op._MemoryLedger(envelope), threading.Event(), started, started, r0_observe=True)
        self.assertEqual(result.receipt.reason, "MALFORMED_IPC_OR_IDENTITY")
        self.assertIs(result.receipt.status, records.AuditStatus.FAIL)
        self.assertIsNone(result.bundle)
        self.assertFalse(result.observation.watchdogs_complete)
        self.assertTrue(result.observation.cleanup_complete)
        self.assertEqual(api.closed, 1)
        self.assertFalse(any(child.pid in pids for child in op.multiprocessing.active_children()))
        self.assertFalse(any(thread.name == "program-k-e2-ipc-reader" and thread.is_alive()
                             for thread in threading.enumerate()))

    def test_r0_telemetry_requires_exact_completed_arm_set_for_each_worker_kind(self):
        for kind in execution.WorkerKind:
            for mode in ("early", "partial", "wrong", "extra"):
                with self.subTest(kind=kind, mode=mode):
                    self.run_ordering(kind, mode)

    def test_r0_arm_events_are_rejected_once_telemetry_header_starts(self):
        for kind in execution.WorkerKind:
            with self.subTest(kind=kind):
                self.run_ordering(kind, "late_arm")


class R0ComponentTests(unittest.TestCase):
    def plan(self, count=1):
        return tuple(op.R0Work(work.position, work.board, work.protocol_seed,
                               "R0-synthetic", work.runtime) for work in _plan(count))

    def result(self, work, kind, *, status=records.AuditStatus.PASS, reason="ADMITTED",
               elapsed=3, observation=None, bundle=True):
        value = _result(work, kind, status, reason, bundle=bundle)
        if work.oracle_b_selected and value.bundle is not None:
            coverage = records.OracleBCoverageRecord(execution._arm(work, records.Arm.K_P0), True, ())
            value = replace(value, bundle=replace(value.bundle, streams=value.bundle.streams +
                (("oracle_b_coverage", (records.encode(coverage),)),)))
        if observation is None:
            observation = op._R0Observation(100, 200, 300, 2, 5, 1, 1, (0, 0, 0, ()), True, True, True)
            if work.oracle_b_selected and kind is execution.WorkerKind.K_CONTROL:
                now = time.perf_counter_ns()
                observation = replace(observation, prior_binding_intervals=((now - 2, now - 1),))
        return replace(value, receipt=replace(value.receipt, elapsed_ns=elapsed), observation=observation)

    def run_component(self, directory, component, *, plan=None, supervise=None,
                      envelope=None, cancel=None, progress=None):
        plan = self.plan() if plan is None else plan
        def default(work, kind, *args, **kwargs):
            self.assertEqual(kwargs, {"r0_observe": True})
            return self.result(work, kind)
        with patch.object(op, "_supervise_operation", side_effect=default if supervise is None else supervise), \
                patch.object(execution, "revalidate_bundle"), \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=200), \
                patch("benchmark_board.generate_board", side_effect=AssertionError("No indexed generation")):
            return op.measure_r0_component(plan, component, Path(directory) / "r0",
                _envelope() if envelope is None else envelope, cancel=cancel, progress=progress)

    def test_component_routes_use_exact_flags_and_only_production_supervision(self):
        expected = {
            op.R0Component.PRIMARY: ((False, False, False), (execution.WorkerKind.PRIMARY,)),
            op.R0Component.ORACLE_B: ((True, False, False), (execution.WorkerKind.PRIMARY,)),
            op.R0Component.K_CONTROL: ((False, False, True),
                (execution.WorkerKind.PRIMARY, execution.WorkerKind.K_CONTROL)),
            op.R0Component.DETERMINISM: ((False, True, False),
                (execution.WorkerKind.PRIMARY, execution.WorkerKind.DETERMINISM)),
            op.R0Component.ORACLE_K_BIND: ((True, False, True),
                (execution.WorkerKind.PRIMARY, execution.WorkerKind.K_CONTROL)),
            op.R0Component.ORACLE_D_REPEAT: ((True, True, False),
                (execution.WorkerKind.PRIMARY, execution.WorkerKind.DETERMINISM)),
        }
        for component, (flags, kinds) in expected.items():
            calls = []
            def supervise(work, kind, prior, envelope, ledger, cancel, job, launcher, **kwargs):
                self.assertEqual(kwargs, {"r0_observe": True})
                self.assertEqual((work.oracle_b_selected, work.determinism_selected, work.k_control_selected), flags)
                self.assertEqual(work.run_id, "R0-synthetic")
                self.assertEqual(job, launcher)
                self.assertEqual(prior is None, kind is execution.WorkerKind.PRIMARY)
                if prior is not None:
                    self.assertIs(execution.decode_bundle(prior).kind, execution.WorkerKind.PRIMARY)
                calls.append(kind)
                return self.result(work, kind)
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                value = self.run_component(directory, component, supervise=supervise)
                self.assertEqual(tuple(calls), kinds)
                self.assertIs(value.units[0].status, records.AuditStatus.PASS)
                self.assertFalse(any(path.name == "COMPLETE.json" for path in Path(directory).rglob("*")))

    def test_k_and_d_complete_wall_contains_setup_persistence_prior_target_and_cleanup(self):
        for component in (op.R0Component.K_CONTROL, op.R0Component.DETERMINISM):
            setup_done, lock = set(), threading.Lock()
            target_clock_calls = []
            prepared_references = set()
            accepted_encode = execution.encode_bundle
            def encode(bundle):
                prepared_references.add(bundle.work_position)
                return accepted_encode(bundle)
            def supervise(work, kind, *args, **kwargs):
                if kind is execution.WorkerKind.PRIMARY:
                    with lock:
                        setup_done.add(work.position)
                    return self.result(work, kind, elapsed=10**12)
                self.assertEqual(setup_done, {0, 1})
                self.assertEqual(prepared_references, {0, 1})
                return self.result(work, kind, elapsed=7)
            real_clock = time.perf_counter_ns
            def clock():
                target_clock_calls.append(frozenset(setup_done))
                return real_clock()
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory, \
                    patch.object(op.time, "perf_counter_ns", side_effect=clock), \
                    patch.object(execution, "encode_bundle", side_effect=encode):
                value = self.run_component(directory, component, plan=self.plan(2), supervise=supervise)
            self.assertTrue(target_clock_calls)
            self.assertEqual(target_clock_calls[0], frozenset())  # Complete launcher interval starts before setup.
            self.assertEqual(target_clock_calls[1], frozenset())  # Standalone boundary also starts before setup.
            self.assertTrue(any(done == {0, 1} for done in target_clock_calls[2:]))
            self.assertLess(value.wall_ns, 10**12)
            self.assertTrue(all(unit.setup_wall_ns == 10**12 for unit in value.units))
            self.assertTrue(all(unit.wall_ns < unit.setup_wall_ns for unit in value.units))

    def test_o_complete_route_has_positive_wall_with_zero_audit_bytes(self):
        intervals = (((10, 30),), ((20, 40),))
        def supervise(work, kind, *args, **kwargs):
            observation = op._R0Observation(100, 200, 300, 2, 5, 0, 1,
                (1, 1, 20, intervals[work.position]), True, True, True)
            return self.result(work, kind, elapsed=10**12, observation=observation)
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.ORACLE_B,
                                       plan=self.plan(2), supervise=supervise)
            self.assertGreater(value.wall_ns, 30)
            for unit in value.units:
                self.assertGreater(unit.wall_ns, 0)
                self.assertEqual(unit.setup_wall_ns, 0)
                target = Path(directory) / "r0" / str(unit.work.position) / "target"
                self.assertTrue((target / "oracle_b_coverage.jsonl").is_file())
                self.assertEqual(unit.durable_bytes, 0)
                self.assertEqual((target / "oracle_b_audits.jsonl").stat().st_size, 0)
                self.assertGreater(unit.supporting_bytes, 0)
                self.assertIs(unit.status, records.AuditStatus.PASS)

    def test_cohort_wall_is_direct_elapsed_not_sum_of_parallel_worker_receipts(self):
        def supervise(work, kind, *args, **kwargs):
            return self.result(work, kind, elapsed=10**12)
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.PRIMARY,
                                       plan=self.plan(2), supervise=supervise)
        self.assertLess(value.wall_ns, 10**12)
        self.assertGreaterEqual(value.complete_wall_ns, value.wall_ns)

    def test_standalone_boundary_includes_every_operational_phase(self):
        for component in (op.R0Component.PRIMARY, op.R0Component.K_CONTROL, op.R0Component.DETERMINISM,
                          op.R0Component.ORACLE_B, op.R0Component.ORACLE_D_REPEAT):
            clock, events = [1], []
            original_persist, original_encode = op._persist_r0, execution.encode_bundle
            def tick(name, amount):
                events.append(name)
                clock[0] += amount
            def supervise(work, kind, *args, **kwargs):
                tick("setup" if kind is execution.WorkerKind.PRIMARY and component in (
                    op.R0Component.K_CONTROL, op.R0Component.DETERMINISM,
                    op.R0Component.ORACLE_D_REPEAT) else "target", 100)
                return self.result(work, kind)
            def encode(bundle):
                tick("encoding", 10)
                return original_encode(bundle)
            def persist(*args, **kwargs):
                result = original_persist(*args, **kwargs)
                tick("persistence_readback_close", 20)
                return result
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory, \
                    patch.object(op.time, "perf_counter_ns", side_effect=lambda: clock[0]), \
                    patch.object(execution, "encode_bundle", side_effect=encode), \
                    patch.object(op, "_persist_r0", side_effect=persist):
                value = self.run_component(directory, component, supervise=supervise,
                                           envelope=_envelope(concurrency=1))
            self.assertIn("target", events)
            self.assertIn("encoding", events)
            self.assertIn("persistence_readback_close", events)
            expected = 260 if component in (op.R0Component.K_CONTROL, op.R0Component.DETERMINISM) else (
                140 if component is op.R0Component.ORACLE_D_REPEAT else 130)
            self.assertEqual(value.wall_ns, expected)

    def test_oracle_k_bind_excludes_solver_and_requires_binding_evidence(self):
        def supervise(work, kind, *args, **kwargs):
            return self.result(work, kind, elapsed=10**12)
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.ORACLE_K_BIND, supervise=supervise)
        self.assertLess(value.wall_ns, 10**12)
        self.assertEqual(value.units[0].durable_bytes, 0)
        self.assertGreater(value.units[0].wall_ns, 0)
        def missing(work, kind, *args, **kwargs):
            result = self.result(work, kind)
            return replace(result, observation=replace(result.observation, prior_binding_intervals=()))
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.ORACLE_K_BIND, supervise=missing)
        self.assertIs(value.units[0].status, records.AuditStatus.INCOMPLETE)

    def test_zero_repeat_oracle_audit_is_completed_with_nonzero_route_wall(self):
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.ORACLE_D_REPEAT)
        self.assertIs(value.units[0].status, records.AuditStatus.PASS)
        self.assertGreater(value.wall_ns, 0)
        self.assertEqual(value.units[0].durable_bytes, 0)

    def test_setup_intervals_include_admission_readback_and_close_before_target(self):
        routes = ((op.R0Component.K_CONTROL, "K", False),
                  (op.R0Component.DETERMINISM, "D", False),
                  (op.R0Component.ORACLE_K_BIND, "O_K_SETUP", True),
                  (op.R0Component.ORACLE_D_REPEAT, "O_D_SETUP", True))
        for component, route, oracle in routes:
            clock, events = [10], []
            original_readback, original_close = op.readback_streams, store.StreamWriter.close
            original_persist, original_encode = op._persist_r0, execution.encode_bundle

            def tick(name, amount):
                events.append((name, clock[0], clock[0] + amount))
                clock[0] += amount

            def supervise(work, kind, *args, **kwargs):
                if kind is execution.WorkerKind.PRIMARY:
                    self.assertIs(work.oracle_b_selected, oracle)
                    tick("setup_launch_execution_decode", 11)
                    tick("setup_worker_reap", 13)
                else:
                    tick("target_work", 10000)
                return self.result(work, kind, elapsed=24)

            def admit(bundle, *args, **kwargs):
                tick("setup_admission" if bundle.kind is execution.WorkerKind.PRIMARY else "target_admission", 17)

            def persist(root, *args, **kwargs):
                tick(root.name + "_persistence", 19)
                return original_persist(root, *args, **kwargs)

            def readback(root, *args, **kwargs):
                result = original_readback(root, *args, **kwargs)
                tick(root.name + "_readback", 23)
                return result

            def close(writer):
                result = original_close(writer)
                tick(writer.path.parent.name + "_writer_close", 1)
                return result

            def encode(bundle):
                tick("prior_encoding" if bundle.kind is execution.WorkerKind.PRIMARY else "target_encoding", 29)
                return original_encode(bundle)

            with self.subTest(route=route), tempfile.TemporaryDirectory() as directory, \
                    patch.object(op.time, "perf_counter_ns", side_effect=lambda: clock[0]), \
                    patch.object(op, "_supervise_operation", side_effect=supervise), \
                    patch.object(execution, "revalidate_bundle", side_effect=admit), \
                    patch.object(execution, "encode_bundle", side_effect=encode), \
                    patch.object(op, "_persist_r0", side_effect=persist), \
                    patch.object(op, "readback_streams", side_effect=readback), \
                    patch.object(store.StreamWriter, "close", new=close), \
                    patch.object(op.harness, "_coordinator_private_bytes", return_value=200):
                value = op.measure_r0_component(self.plan(), component, Path(directory) / "r0",
                                                _envelope(concurrency=1))
            setup, = value.setup_measurements
            setup_events = tuple(event for event in events if event[0].startswith("setup_"))
            self.assertEqual(setup.route, route)
            self.assertEqual(setup.positions, (0,))
            self.assertEqual(setup.started_ns, setup_events[0][1])
            self.assertEqual(setup.finished_ns, setup_events[-1][2])
            self.assertEqual(setup.wall_ns, sum(end - start for _, start, end in setup_events))
            self.assertLess(setup.wall_ns, 10000)
            self.assertEqual(setup.finished_ns, next(start for name, start, _ in events if name == "prior_encoding"))
            self.assertLess(setup.finished_ns, next(start for name, start, _ in events if name == "target_work"))
            self.assertTrue({"setup_launch_execution_decode", "setup_worker_reap", "setup_admission",
                             "setup_persistence", "setup_readback", "setup_writer_close"}
                            <= {name for name, _, _ in setup_events})
            self.assertTrue(setup.readback_complete and setup.cleanup_complete and setup.resources_complete
                            and setup.watchdogs_complete and setup.progress_complete)
            self.assertGreater(setup.max_payload_bytes, 0)
            self.assertEqual(setup.max_case_wall_ns, 24)

    def test_setup_waves_are_disjoint_and_cover_each_position_once(self):
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.ORACLE_D_REPEAT, plan=self.plan(3),
                                       envelope=_envelope(concurrency=2))
        first, second = value.setup_measurements
        self.assertEqual((first.positions, second.positions), ((0, 1), (2,)))
        self.assertLessEqual(first.finished_ns, second.started_ns)
        self.assertLessEqual(first.wall_ns + second.wall_ns, value.complete_wall_ns)
        self.assertEqual(value.setup_wall_ns, first.wall_ns + second.wall_ns)
        for setup in value.setup_measurements:
            self.assertEqual(setup.route, "O_D_SETUP")
            self.assertEqual(setup.completed_units, len(setup.positions))
        with self.assertRaisesRegex(ValueError, "R0_SETUP_COVERAGE"):
            replace(value, setup_measurements=(first,))
        with self.assertRaises(ValueError):
            replace(value, setup_measurements=(second, first))
        with self.assertRaisesRegex(ValueError, "R0_SETUP_ROUTE_OR_ORDER"):
            replace(value, setup_measurements=(replace(first, route="D"), second))

    def test_setup_observer_preserves_exact_oracle_bind_wall_without_solver_reattribution(self):
        clock = [1]
        original_persist, original_encode = op._persist_r0, execution.encode_bundle

        def supervise(work, kind, *args, **kwargs):
            if kind is execution.WorkerKind.PRIMARY:
                clock[0] += 1000
                return self.result(work, kind)
            start = clock[0]
            clock[0] += 20 + 10000 + 30  # Binding, ordinary K solver, binding cleanup.
            result = self.result(work, kind)
            return replace(result, observation=replace(result.observation,
                prior_binding_intervals=((start, start + 20), (start + 10020, start + 10050))))

        def admit(bundle, *args, **kwargs):
            clock[0] += 100 if bundle.kind is execution.WorkerKind.PRIMARY else 40

        def persist(root, *args, **kwargs):
            result = original_persist(root, *args, **kwargs)
            clock[0] += 300 if root.name == "setup" else 400
            return result

        def encode(bundle):
            clock[0] += 10
            return original_encode(bundle)

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op.time, "perf_counter_ns", side_effect=lambda: clock[0]), \
                patch.object(op, "_supervise_operation", side_effect=supervise), \
                patch.object(execution, "revalidate_bundle", side_effect=admit), \
                patch.object(execution, "encode_bundle", side_effect=encode), \
                patch.object(op, "_persist_r0", side_effect=persist), \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=200):
            value = op.measure_r0_component(self.plan(), op.R0Component.ORACLE_K_BIND,
                                            Path(directory) / "r0", _envelope(concurrency=1))
        self.assertEqual(value.wall_ns, 10 + 20 + 30 + 40)
        self.assertEqual(value.units[0].wall_ns, value.wall_ns)
        self.assertEqual(value.setup_wall_ns, 1000 + 100 + 300)
        self.assertEqual(value.units[0].durable_bytes, 0)
        self.assertGreater(value.complete_wall_ns, 10000)

    def test_setup_memory_is_independent_through_persistence_and_readback(self):
        for component in (op.R0Component.ORACLE_K_BIND, op.R0Component.ORACLE_D_REPEAT):
            for setup_peak, target_peak in ((2000, 9000), (9000, 2000)):
                memory, sampled = [200], threading.Event()
                original_persist, original_readback = op._persist_r0, op.readback_streams

                def coordinator():
                    if memory[0] != 200:
                        sampled.set()
                    return memory[0]

                def spike(value):
                    sampled.clear()
                    memory[0] = value
                    self.assertTrue(sampled.wait(1), "Production monitor did not sample setup/target phase")

                def persist(root, *args, **kwargs):
                    spike((setup_peak if root.name == "setup" else target_peak) - 100)
                    result = original_persist(root, *args, **kwargs)
                    memory[0] = 200
                    return result

                def readback(root, *args, **kwargs):
                    spike(setup_peak if root.name == "setup" else target_peak)
                    return original_readback(root, *args, **kwargs)

                def supervise(work, kind, *args, **kwargs):
                    result = self.result(work, kind)
                    if kind is not execution.WorkerKind.PRIMARY:
                        result = replace(result, observation=replace(result.observation,
                            worker_memory=500, combined_memory=700, decision_wall=20,
                            arm_wall=50, shadow_wall=10, physical_inputs=5),
                            receipt=replace(result.receipt, elapsed_ns=80))
                    return result

                with self.subTest(component=component, setup=setup_peak, target=target_peak), \
                        tempfile.TemporaryDirectory() as directory, \
                        patch.object(op.harness, "_coordinator_private_bytes", side_effect=coordinator), \
                        patch.object(op, "_supervise_operation", side_effect=supervise), \
                        patch.object(execution, "revalidate_bundle"), \
                        patch.object(op, "_persist_r0", side_effect=persist), \
                        patch.object(op, "readback_streams", side_effect=readback):
                    value = op.measure_r0_component(self.plan(), component, Path(directory) / "r0", _envelope())
                setup, = value.setup_measurements
                self.assertEqual(setup.max_coordinator_memory_bytes, setup_peak)
                self.assertEqual(setup.max_combined_memory_bytes, setup_peak)
                self.assertEqual(value.coordinator_memory_bytes, max(setup_peak, target_peak))
                self.assertEqual(value.combined_memory_bytes, max(setup_peak, target_peak))
                self.assertEqual((setup.max_worker_memory_bytes, setup.max_decision_wall_ns,
                    setup.max_arm_wall_ns, setup.max_case_wall_ns, setup.max_shadow_wall_ns,
                    setup.max_physical_inputs), (100, 2, 5, 3, 1, 1))
                self.assertFalse(any(thread.name == "program-k-r0-memory" and thread.is_alive()
                                     for thread in threading.enumerate()))

    def test_setup_inapplicability_zero_payload_and_incomplete_observations_are_distinct(self):
        for component in (op.R0Component.PRIMARY, op.R0Component.ORACLE_B):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                value = self.run_component(directory, component)
            self.assertEqual(value.setup_measurements, ())
            self.assertIsNone(value.setup_wall_ns)
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.K_CONTROL)
        setup, = value.setup_measurements
        zero = replace(setup, payload_bytes=(0,))
        self.assertEqual(zero.max_payload_bytes, 0)
        self.assertTrue(zero.progress_complete)
        self.assertTrue(zero.resources_complete)
        missing = replace(setup, observations=(None,))
        self.assertFalse(missing.resources_complete)
        self.assertFalse(missing.watchdogs_complete)
        self.assertFalse(missing.cleanup_complete)
        self.assertFalse(replace(setup, memory_sample_count=0).resources_complete)
        self.assertFalse(replace(setup, readback_complete=False).progress_complete)
        for name in ("resources_complete", "watchdogs_complete", "cleanup_complete"):
            changed = replace(setup, observations=(replace(setup.observations[0], **{name: False}),))
            self.assertFalse(getattr(changed, name))

    def test_setup_facts_are_deeply_immutable_and_validate_exact_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.ORACLE_K_BIND)
        setup, = value.setup_measurements
        for item in (setup,) + setup.receipts + setup.observations:
            self.assertFalse(hasattr(item, "__dict__"))
            for field in fields(item):
                with self.assertRaises(FrozenInstanceError):
                    setattr(item, field.name, None)
        invalid = (("route", "O_K_BIND"), ("receipts", list(setup.receipts)),
                   ("observations", []), ("payload_bytes", [0]), ("payload_bytes", (True,)),
                   ("started_ns", True), ("finished_ns", setup.started_ns - 1),
                   ("coordinator_memory_bytes", 1.5), ("combined_memory_bytes", 0),
                   ("memory_sample_count", -1), ("readback_complete", 1),
                   ("receipts", (replace(setup.receipts[0], kind=execution.WorkerKind.K_CONTROL),)))
        for name, field_value in invalid:
            with self.subTest(name=name), self.assertRaises(ValueError):
                replace(setup, **{name: field_value})

    def test_setup_readback_or_close_failure_never_launches_target(self):
        for boundary in ("readback", "close"):
            calls = []
            original_close = store.StreamWriter.close

            def supervise(work, kind, *args, **kwargs):
                calls.append(kind)
                return self.result(work, kind)

            def close(writer):
                original_close(writer)
                if writer.path.parent.name == "setup":
                    raise OSError("setup close failed")

            failure = (patch.object(op, "readback_streams", side_effect=OSError("setup readback failed"))
                       if boundary == "readback" else patch.object(store.StreamWriter, "close", new=close))
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as directory, \
                    failure:
                with self.assertRaises(OSError):
                    self.run_component(directory, op.R0Component.ORACLE_D_REPEAT, supervise=supervise)
                self.assertEqual(calls, [execution.WorkerKind.PRIMARY])
                self.assertFalse((Path(directory) / "r0" / "0" / "target").exists())
                self.assertFalse(any(thread.name == "program-k-r0-memory" and thread.is_alive()
                                     for thread in threading.enumerate()))

    def test_exact_store_framing_and_rank_specific_ownership(self):
        work = op._r0_work(self.plan()[0], op.R0Component.K_CONTROL)
        for kind, component in ((execution.WorkerKind.PRIMARY, op.R0Component.PRIMARY),
                                (execution.WorkerKind.K_CONTROL, op.R0Component.K_CONTROL),
                                (execution.WorkerKind.DETERMINISM, op.R0Component.DETERMINISM)):
            result = self.result(work, kind)
            # Canonical synthetic transport records test byte ownership, not
            # semantic record membership (covered by literal route integration).
            data = records.encode(work.board)
            names = ("boards", "control_maintenance", "repeat_control_maintenance",
                     "oracle_b_coverage", "repeat_oracle_b_coverage", "oracle_b_audits",
                     "repeat_oracle_b_audits")
            result = replace(result, bundle=replace(result.bundle, streams=tuple(
                (name, (data,)) for name in sorted(names, key=execution.STREAM_NAMES.index))))
            size = len(store._key_bytes((work.position, op._kind_rank(kind), 0))) + len(data) + 2
            self.assertEqual(op._bundle_stream_bytes(result), size * len(names))
            self.assertEqual(op._r0_attributable_bytes(result, component), size * (
                4 if component is op.R0Component.PRIMARY else 5))
            self.assertEqual(op._r0_attributable_bytes(result, op.R0Component.ORACLE_B), size)
            self.assertEqual(op._r0_attributable_bytes(result, op.R0Component.ORACLE_D_REPEAT), size)
            self.assertEqual(op._r0_attributable_bytes(result, op.R0Component.ORACLE_K_BIND), 0)
            self.assertGreater(size, op._EvidenceSink._size((0,), data))

    def test_closed_immutable_results_and_progress_exclude_treatment_fields(self):
        progress = []
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.PRIMARY, plan=self.plan(2),
                progress=lambda unit, done, total: progress.append((unit, done, total)))
        self.assertEqual(tuple((done, total) for _, done, total in progress), ((1, 2), (2, 2)))
        self.assertEqual(tuple(unit for unit, _, _ in progress), value.units)
        for item in (value,) + value.units + tuple(obs for unit in value.units for obs in unit.observations):
            self.assertFalse(hasattr(item, "__dict__"))
            for field in fields(item):
                with self.assertRaises(FrozenInstanceError):
                    setattr(item, field.name, None)
            for name in ("bundle", "model_c_delta", "ww_wl_lw_ll", "g5_g8_g9", "mechanism_rankings", "research_verdict"):
                self.assertFalse(hasattr(item, name))
                with self.assertRaises(TypeError):
                    replace(item, **{name: 1})

    def test_missing_or_incomplete_operational_observation_cannot_pass(self):
        baseline = op._R0Observation(100, 200, 300, 2, 5, 1, 1, (0, 0, 0, ()), True, True, True)
        for field in (None, "resources_complete", "cleanup_complete", "watchdogs_complete"):
            def supervise(work, kind, *args, **kwargs):
                result = self.result(work, kind, observation=baseline)
                return replace(result, observation=None if field is None else replace(baseline, **{field: False}))
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                value = self.run_component(directory, op.R0Component.PRIMARY, supervise=supervise)
            self.assertIs(value.units[0].status, records.AuditStatus.INCOMPLETE)
            self.assertIn("R0_OBSERVATION_INCOMPLETE", value.units[0].reasons)

    def test_failed_setup_is_preserved_and_never_retried_or_used_for_target(self):
        for component in (op.R0Component.K_CONTROL, op.R0Component.DETERMINISM):
            calls = []
            def supervise(work, kind, *args, **kwargs):
                calls.append(kind)
                return self.result(work, kind, status=records.AuditStatus.FAIL, reason="AUDIT_FAIL")
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                value = self.run_component(directory, component, supervise=supervise)
                self.assertEqual(calls, [execution.WorkerKind.PRIMARY])
                self.assertIs(value.units[0].status, records.AuditStatus.FAIL)
                self.assertEqual(value.units[0].reasons, ("AUDIT_FAIL", "PRIMARY_PREMISES_MISSING"))
                setup, = value.setup_measurements
                self.assertEqual(setup.completed_units, 0)
                self.assertFalse(setup.progress_complete)
                self.assertTrue(setup.readback_complete)
                self.assertIs(setup.receipts[0].status, records.AuditStatus.FAIL)
                self.assertTrue((Path(directory) / "r0" / "0" / "setup" / "boards.jsonl").is_file())
                self.assertTrue((Path(directory) / "r0" / "0" / "target" / "operations.jsonl").is_file())

    def test_k_target_failure_and_incomplete_and_d_mismatch_are_preserved_without_retry(self):
        cases = ((op.R0Component.K_CONTROL, records.AuditStatus.FAIL, "AUDIT_FAIL"),
                 (op.R0Component.K_CONTROL, records.AuditStatus.INCOMPLETE, "AUDIT_INCOMPLETE"),
                 (op.R0Component.DETERMINISM, records.AuditStatus.FAIL, "DETERMINISM_MISMATCH"))
        for component, status, reason in cases:
            calls = []
            def supervise(work, kind, *args, **kwargs):
                calls.append(kind)
                return self.result(work, kind) if kind is execution.WorkerKind.PRIMARY else self.result(
                    work, kind, status=status, reason=reason)
            with self.subTest(component=component, reason=reason), tempfile.TemporaryDirectory() as directory:
                value = self.run_component(directory, component, supervise=supervise)
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(set(calls)), 2)
                self.assertIs(calls[0], execution.WorkerKind.PRIMARY)
                self.assertIs(value.units[0].status, status)
                self.assertEqual(value.units[0].reasons, (reason,))
                self.assertGreater(value.units[0].setup_bytes, 0)
                self.assertGreater(value.units[0].durable_bytes, 0)
                self.assertTrue((Path(directory) / "r0" / "0" / "target" / "operations.jsonl").is_file())

    def test_target_memory_watchdog_and_case_cap_reasons_remain_incomplete(self):
        for reason in ("MEMORY_CAP", "MEMORY_MONITOR_INCOMPLETE", "DECISION_TIMEOUT",
                       "ARM_TIMEOUT", "CASE_TIMEOUT", "WATCHDOG_INCOMPLETE"):
            calls = []
            def supervise(work, kind, *args, **kwargs):
                calls.append(kind)
                if kind is execution.WorkerKind.PRIMARY:
                    return self.result(work, kind)
                observation = op._R0Observation(100, 200, 300, 2, 5, 1, 1, (0, 0, 0, ()),
                    reason != "MEMORY_MONITOR_INCOMPLETE", True, reason.startswith("MEMORY"))
                return self.result(work, kind, status=records.AuditStatus.INCOMPLETE,
                                   reason=reason, observation=observation, bundle=False)
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                value = self.run_component(directory, op.R0Component.K_CONTROL, supervise=supervise)
                self.assertEqual(calls, [execution.WorkerKind.PRIMARY, execution.WorkerKind.K_CONTROL])
                unit, = value.units
                self.assertIs(unit.status, records.AuditStatus.INCOMPLETE)
                self.assertEqual(unit.reasons, (reason,))
                self.assertTrue(all(type(item) is op._R0Observation for item in unit.observations))
                self.assertTrue(all(item.cleanup_complete for item in unit.observations))
                self.assertTrue((Path(directory) / "r0" / "0" / "setup" / "boards.jsonl").is_file())

    def test_failure_and_progress_exception_leave_partial_roots_without_retry(self):
        calls = []
        def supervise(work, kind, *args, **kwargs):
            calls.append(work.position)
            return self.result(work, kind)
        def fail(*args):
            raise RuntimeError("synthetic progress failure")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "synthetic progress failure"):
                self.run_component(directory, op.R0Component.PRIMARY, plan=self.plan(2),
                                   supervise=supervise, envelope=_envelope(concurrency=1), progress=fail)
            self.assertEqual(calls, [0])
            self.assertTrue((Path(directory) / "r0" / "0" / "target" / "boards.jsonl").exists())
            with self.assertRaises(FileExistsError):
                self.run_component(directory, op.R0Component.PRIMARY, supervise=supervise)
            self.assertEqual(calls, [0])

    def test_rejects_non_r0_wrong_order_duplicate_and_identity_drift_before_root_creation(self):
        plan = self.plan(2)
        invalid = ((), list(plan), _plan(2), plan[::-1],
                   (plan[0], replace(plan[1], board=plan[0].board)),
                   (plan[0], replace(plan[1], run_id="R0-different")),
                   (plan[0], replace(plan[1], protocol_seed=b"z" * 32)))
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op, "_supervise_operation", side_effect=AssertionError("Invalid plan ran")):
            for plan_value in invalid:
                with self.subTest(plan=type(plan_value)), self.assertRaises(ValueError):
                    op.measure_r0_component(plan_value, op.R0Component.PRIMARY, Path(directory) / "r0", _envelope())
                self.assertFalse((Path(directory) / "r0").exists())
            for invalid_component in ("P", None, True):
                with self.assertRaises(ValueError):
                    op.measure_r0_component(plan, invalid_component, Path(directory) / "r0", _envelope())
        with self.assertRaisesRegex(ValueError, "R0_RUN_ID_REQUIRED"):
            replace(plan[0], run_id="actual-e2")

    def test_existing_root_is_exclusive_and_public_api_has_no_worker_injection(self):
        self.assertNotIn("worker_target", inspect.signature(op.measure_r0_component).parameters)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "r0"
            root.mkdir()
            sentinel = root / "preserved.txt"
            sentinel.write_text("preserve", encoding="ascii")
            with self.assertRaises(FileExistsError):
                self.run_component(directory, op.R0Component.PRIMARY)
            self.assertEqual(sentinel.read_text(encoding="ascii"), "preserve")

    def test_shared_ledger_and_bounded_parallelism_are_reused_for_all_units(self):
        active = peak = 0
        ledgers, lock = [], threading.Lock()
        def supervise(work, kind, prior, envelope, ledger, *args, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                ledgers.append(ledger)
            time.sleep(0.005)
            with lock:
                active -= 1
            return self.result(work, kind)
        with tempfile.TemporaryDirectory() as directory:
            value = self.run_component(directory, op.R0Component.PRIMARY, plan=self.plan(3), supervise=supervise)
        self.assertLessEqual(peak, 2)
        self.assertEqual(len(value.units), 3)
        self.assertEqual(len({id(ledger) for ledger in ledgers}), 1)
        self.assertTrue(all(isinstance(ledger, op._MemoryLedger) for ledger in ledgers))

    def test_coordinator_memory_cap_preserves_root_and_prevents_workers(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=100_000_001), \
                patch.object(op, "_supervise_operation", side_effect=AssertionError("Memory cap worker")):
            with self.assertRaisesRegex(op.OperationalAbort, "MEMORY_CAP"):
                op.measure_r0_component(self.plan(), op.R0Component.PRIMARY,
                                        Path(directory) / "r0", _envelope())
            self.assertTrue((Path(directory) / "r0").is_dir())

    def test_observation_rejects_nonexact_memory_counts_and_mutable_or_inconsistent_intervals(self):
        baseline = op._R0Observation(100, 200, 300, 2, 5, 1, 1, (1, 1, 2, ((10, 12),)), True, True, True)
        for field in ("worker_memory", "coordinator_memory", "combined_memory", "decision_wall",
                      "arm_wall", "shadow_wall", "physical_inputs"):
            for invalid in (True, -1, 1.0, None):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    replace(baseline, **{field: invalid})
        for oracle in ((True, 1, 2, ((10, 12),)), (1, 1.0, 2, ((10, 12),)),
                       (1, 1, True, ((10, 12),)), (1, 2, 2, ((10, 12),)),
                       (1, 1, 2, [(10, 12)]), (1, 1, 2, ([10, 12],)),
                       (1, 1, 2, ((10, 12.0),)), (1, 1, 2, ((12, 10),)),
                       (2, 1, 4, ((10, 12), (11, 13))), (1, 1, 3, ((10, 12),)),
                       (0, 0, 1, ())):
            with self.subTest(oracle=oracle), self.assertRaises(ValueError):
                replace(baseline, oracle=oracle)
        with self.assertRaisesRegex(ValueError, "R0_MEMORY_ACCOUNTING"):
            replace(baseline, combined_memory=199)

    def test_final_persistence_checkpoint_cannot_escape_publication_cap(self):
        original = store.StreamWriter.seal
        clock, offset = time.monotonic_ns, [0]
        def late_seal(writer):
            result = original(writer)
            offset[0] += 2_000_000
            return result
        for oracle_only in (False, True):
            offset[0] = 0
            with self.subTest(oracle_only=oracle_only), tempfile.TemporaryDirectory() as directory, \
                    patch.object(op.time, "monotonic_ns", side_effect=lambda: clock() + offset[0]), \
                    patch.object(store.StreamWriter, "seal", new=late_seal):
                work = op._r0_work(self.plan()[0], op.R0Component.ORACLE_B if oracle_only else op.R0Component.PRIMARY)
                with self.assertRaisesRegex(op.OperationalAbort, "PUBLICATION_TIMEOUT"):
                    op._persist_r0(Path(directory) / "target", self.result(work, execution.WorkerKind.PRIMARY),
                                   _envelope(publication_wall_ms=1), oracle_only=oracle_only)
                self.assertTrue((Path(directory) / "target").is_dir())
                self.assertFalse((Path(directory) / "target" / "COMPLETE.json").exists())

    def test_coordinator_equivalent_readmission_obeys_validation_cap(self):
        clock, offset = time.monotonic_ns, [0]
        def delayed_validation(*args, **kwargs):
            offset[0] += 2_000_000
        def supervise(work, kind, *args, **kwargs):
            return self.result(work, kind)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op.time, "monotonic_ns", side_effect=lambda: clock() + offset[0]), \
                patch.object(execution, "revalidate_bundle", side_effect=delayed_validation), \
                patch.object(op, "_supervise_operation", side_effect=supervise), \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=200):
            with self.assertRaisesRegex(op.OperationalAbort, "VALIDATION_TIMEOUT"):
                op.measure_r0_component(self.plan(), op.R0Component.ORACLE_B,
                    Path(directory) / "r0", _envelope(validation_wall_ms=1))

    def test_component_archive_cannot_exceed_remaining_global_budget(self):
        calls = []
        def supervise(work, kind, *args, **kwargs):
            calls.append(work.position)
            return self.result(work, kind)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(op.OperationalAbort, "ARCHIVE_CAP"):
                self.run_component(directory, op.R0Component.PRIMARY, plan=self.plan(3), supervise=supervise,
                                   envelope=_envelope(concurrency=1, archive_cap_bytes=8400, max_payload_bytes=8000))
            size = sum(path.stat().st_size for path in (Path(directory) / "r0").rglob("*.jsonl"))
            self.assertLessEqual(size, 8400)
            self.assertTrue(calls)
            self.assertEqual(calls, list(range(len(calls))))
            self.assertLessEqual(len(calls), 3)

    def test_coordinator_peak_during_persistence_is_observed_and_monitor_reaped(self):
        memory, sampled = [200], threading.Event()
        original = op._persist_r0
        def coordinator():
            if memory[0] == 1000:
                sampled.set()
            return memory[0]
        def persist(*args, **kwargs):
            memory[0] = 1000
            self.assertTrue(sampled.wait(1), "Background monitor did not observe persistence")
            value = original(*args, **kwargs)
            memory[0] = 200
            return value
        def supervise(work, kind, *args, **kwargs):
            return self.result(work, kind)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op.harness, "_coordinator_private_bytes", side_effect=coordinator), \
                patch.object(op, "_supervise_operation", side_effect=supervise), \
                patch.object(execution, "revalidate_bundle"), \
                patch.object(op, "_persist_r0", side_effect=persist):
            value = op.measure_r0_component(self.plan(), op.R0Component.PRIMARY,
                                            Path(directory) / "r0", _envelope())
        self.assertEqual(value.coordinator_memory_bytes, 1000)
        self.assertGreaterEqual(value.combined_memory_bytes, 1000)
        self.assertFalse(any(thread.name == "program-k-r0-memory" and thread.is_alive()
                             for thread in threading.enumerate()))

    def test_precancelled_public_measurement_spawns_no_process_and_remains_incomplete(self):
        cancel = threading.Event()
        cancel.set()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=200), \
                patch("multiprocessing.process.BaseProcess.start", side_effect=AssertionError("Cancelled process started")):
            value = op.measure_r0_component(self.plan(), op.R0Component.PRIMARY,
                                            Path(directory) / "r0", _envelope(), cancel=cancel)
        self.assertIs(value.units[0].status, records.AuditStatus.INCOMPLETE)
        self.assertIn("CANCELLED", value.units[0].reasons)

    def test_literal_spawn_uses_production_worker_job_ipc_and_reaps_every_component(self):
        from tests.test_program_k_e2_execution import _literal_work
        work = _literal_work()
        plan = (op.R0Work(0, work.board, work.protocol_seed, "R0-contained-literal"),)
        context = op.multiprocessing.get_context("spawn")
        original_attach = op.harness._attach_memory_job
        envelope = _envelope(concurrency=1, max_decision_wall_ms=1000, max_arm_wall_ms=5000,
            max_case_wall_ms=15000, max_job_wall_ms=30000, max_launcher_wall_ms=45000,
            worker_memory_cap_bytes=500_000_000, coordinator_memory_cap_bytes=2_000_000_000,
            memory_cap_bytes=3_000_000_000, max_physical_inputs=30,
            archive_cap_bytes=5_000_000, max_payload_bytes=1_000_000)
        for component in op.R0Component:
            requested, attached = [], []
            def process(*, target, args):
                self.assertIs(target, op._worker_main)
                self.assertIs(args[-1], True)
                requested.append(target)
                return context.Process(target=_r0_literal_worker, args=(target, args))
            def attach(pid, budget):
                attached.append(pid)
                return original_attach(pid, budget)
            proxy = SimpleNamespace(Pipe=context.Pipe, Event=context.Event, Process=process)
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory, \
                    patch.object(op.multiprocessing, "get_context", return_value=proxy), \
                    patch.object(op.harness, "_attach_memory_job", side_effect=attach), \
                    patch.object(op.harness, "_coordinator_private_bytes", return_value=200):
                value = op.measure_r0_component(plan, component, Path(directory) / "r0", envelope)
                self.assertIs(value.units[0].status, records.AuditStatus.PASS, value.units[0].reasons)
                unit = value.units[0]
                target_root = Path(directory) / "r0" / "0" / "target"
                excluded = {"operations", "resources", "oracle_b_audits", "repeat_oracle_b_audits"}
                if component is op.R0Component.PRIMARY:
                    excluded.add("control_maintenance")
                if component is op.R0Component.ORACLE_K_BIND:
                    expected_bytes = 0
                    self.assertEqual(len(unit.observations[-1].prior_binding_intervals), 3)
                elif component in (op.R0Component.ORACLE_B, op.R0Component.ORACLE_D_REPEAT):
                    name = "oracle_b_audits" if component is op.R0Component.ORACLE_B else "repeat_oracle_b_audits"
                    expected_bytes = (target_root / (name + ".jsonl")).stat().st_size
                else:
                    expected_bytes = sum(path.stat().st_size for path in target_root.glob("*.jsonl")
                                         if path.stem not in excluded)
                self.assertEqual(unit.durable_bytes, expected_bytes)
                setup_root = target_root.parent / "setup"
                self.assertEqual(unit.reference_bytes, (setup_root / "control_maintenance.jsonl").stat().st_size
                                 if setup_root.exists() else 0)
                if setup_root.exists():
                    setup, = value.setup_measurements
                    self.assertEqual(setup.positions, (0,))
                    self.assertEqual(setup.observations, (unit.observations[0],))
                    self.assertEqual(setup.max_case_wall_ns, unit.setup_wall_ns)
                    self.assertGreater(setup.wall_ns, setup.max_case_wall_ns)
                    self.assertTrue(setup.resources_complete and setup.cleanup_complete
                                    and setup.readback_complete and setup.watchdogs_complete
                                    and setup.progress_complete)
                    self.assertGreater(setup.max_worker_memory_bytes, 0)
                    self.assertLessEqual(setup.max_payload_bytes, unit.max_payload_bytes)
                else:
                    self.assertEqual(value.setup_measurements, ())
                self.assertEqual(unit.supporting_bytes, sum(path.stat().st_size
                    for path in target_root.parent.rglob("*.jsonl") if path.stem in ("operations", "resources")))
                self.assertTrue(all(item.resources_complete and item.cleanup_complete and item.watchdogs_complete
                                    for item in value.units[0].observations))
                self.assertTrue(all(item.worker_memory > 0 for item in value.units[0].observations))
                self.assertEqual(len(requested), 2 if component in (op.R0Component.K_CONTROL,
                    op.R0Component.DETERMINISM, op.R0Component.ORACLE_K_BIND,
                    op.R0Component.ORACLE_D_REPEAT) else 1)
                self.assertEqual(len(attached), len(requested))
                self.assertFalse(any(child.pid in attached for child in op.multiprocessing.active_children()))
                self.assertFalse(any(thread.name in ("program-k-e2-ipc-reader", "program-k-e2-watchdog")
                                     and thread.is_alive() for thread in threading.enumerate()))

    def test_selected_zero_telemetry_cannot_override_nonempty_oracle_evidence(self):
        from tests.test_program_k_e2_execution import _literal_work
        work = _literal_work()
        plan = (op.R0Work(0, work.board, work.protocol_seed, "R0-corrupt-literal"),)
        context = op.multiprocessing.get_context("spawn")
        def process(*, target, args):
            self.assertIs(target, op._worker_main)
            return context.Process(target=_r0_literal_worker, args=(target, args, True))
        proxy = SimpleNamespace(Pipe=context.Pipe, Event=context.Event, Process=process)
        envelope = _envelope(concurrency=1, max_decision_wall_ms=1000, max_arm_wall_ms=5000,
            max_case_wall_ms=15000, max_job_wall_ms=30000, max_launcher_wall_ms=45000,
            worker_memory_cap_bytes=500_000_000, coordinator_memory_cap_bytes=2_000_000_000,
            memory_cap_bytes=3_000_000_000, max_physical_inputs=30,
            archive_cap_bytes=5_000_000, max_payload_bytes=1_000_000)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op.multiprocessing, "get_context", return_value=proxy), \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=200):
            value = op.measure_r0_component(plan, op.R0Component.ORACLE_B, Path(directory) / "r0", envelope)
            self.assertIs(value.units[0].status, records.AuditStatus.FAIL)
            self.assertIn("MALFORMED_IPC_OR_IDENTITY", value.units[0].reasons)
            self.assertFalse(any(thread.name == "program-k-e2-ipc-reader" and thread.is_alive()
                                 for thread in threading.enumerate()))


class R0SetupMonitorTests(unittest.TestCase):
    def test_interval_samples_reset_independently_without_changing_global_peaks_or_cadence(self):
        ledger = op._MemoryLedger(_envelope())
        monitor = op._R0MemoryMonitor(ledger, threading.Event(), _envelope())
        memory, clock, calls = [10], [1], []

        def coordinator():
            calls.append(memory[0])
            return memory[0]

        with patch.object(op.harness, "_coordinator_private_bytes", side_effect=coordinator), \
                patch.object(op.time, "perf_counter_ns", side_effect=lambda: clock[0]):
            ledger.values["worker"] = 20
            monitor.sample()
            monitor.begin_setup()
            memory[0], clock[0] = 100, 2
            ledger.values["worker"] = 300
            monitor.sample()
            memory[0], clock[0] = 40, 3
            ledger.values["worker"] = 50
            monitor.sample()
            first = monitor.end_setup()
            memory[0] = 900
            ledger.values["worker"] = 1000
            monitor.sample()  # Target-only spike.
            clock[0] = 4
            monitor.begin_setup()
            memory[0], clock[0] = 50, 5
            ledger.values["worker"] = 60
            monitor.sample()
            second = monitor.end_setup()
        self.assertEqual(first, (1, 3, 100, 400, 2))
        self.assertEqual(second, (4, 5, 50, 110, 1))
        self.assertEqual((monitor.coordinator, monitor.combined), (900, 1900))
        self.assertEqual(calls, [10, 100, 40, 900, 50])  # Boundaries never add sampling calls.
        self.assertIsNone(monitor.setup)

    def test_setup_observation_preserves_cap_and_sampling_failure_behavior(self):
        for reason in ("MEMORY_CAP", "MEMORY_MONITOR_INCOMPLETE"):
            cancel = threading.Event()
            monitor = op._R0MemoryMonitor(op._MemoryLedger(_envelope()), cancel, _envelope())
            monitor.begin_setup()
            options = ({"return_value": 100_000_001} if reason == "MEMORY_CAP" else
                       {"side_effect": OSError("synthetic sampling failure")})
            with self.subTest(reason=reason), \
                    patch.object(op.harness, "_coordinator_private_bytes", **options):
                with self.assertRaisesRegex(op.OperationalAbort, reason):
                    monitor.check()
            self.assertTrue(cancel.is_set())
            self.assertEqual(monitor.reason, reason)
            snapshot = monitor.end_setup()
            self.assertEqual(snapshot[-1], 1 if reason == "MEMORY_CAP" else 0)
            self.assertEqual(monitor.coordinator, 100_000_001 if reason == "MEMORY_CAP" else 0)

    def test_setup_interval_lifecycle_is_closed(self):
        monitor = op._R0MemoryMonitor(op._MemoryLedger(_envelope()), threading.Event(), _envelope())
        with self.assertRaisesRegex(ValueError, "R0_SETUP_NOT_ACTIVE"):
            monitor.end_setup()
        monitor.begin_setup()
        with self.assertRaisesRegex(ValueError, "R0_SETUP_ALREADY_ACTIVE"):
            monitor.begin_setup()
        monitor.end_setup()


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


_WB02_TEST_PROFILE = bytes.fromhex("36" * 32)  # Synthetic supplied identity; never qualified.


def _wb02_context_fixture():
    """One literal initial win per arm, assembled without engines, solvers or I/O."""
    board = records.BoardIdentity(700_001, "wb02-literal-one-cell", 1, 1, 0, (0, 0),
                                  "supplied-literal", "supplied-unit-spec")
    work = execution.make_work_plan((board,), protocol_seed=b"\x27" * 32, run_id="wb02-context-unit")[0]
    physical = records.PhysicalInputRecord(0, records.Action.OPEN, (0, 0), (0, 0),
                                            100_000, 100_000, records.Status.WON)
    public = records.PublicEffectRecord(0, (records.PublicCellChange((0, 0), "HIDDEN", "CLUE_0"),),
                                         records.Status.PLAYING, records.Status.WON)
    terminal = records.TerminalEffectRecord(0, (), records.Status.WON)
    timings = (("v1_plan_position_ns", None), ("k_analysis_planning_ns", None),
               ("k_execution_validation_ns", None), ("v1_execution_validation_ns", 2),
               ("shadow_ns", None), ("evidence_ns", 4), ("comparison_ns", None),
               ("oracle_ns", None), ("evaluator_ns", None))

    def projection(role):
        kind = records.Arm.CONTROL if role.endswith("control") else records.Arm.K_P0
        arm = execution._arm(work, kind, repeat=role.startswith("repeat_"))
        decision = records.ActionDecisionRecord(arm, 0,
            "CONTROL_INITIAL_OPEN" if kind is records.Arm.CONTROL else "POLICY_INITIAL_OPEN",
            "INITIAL", records.Action.OPEN, (0, 0), (), None, None, (), (), (), ())
        return execution.game.GameProjection(arm, records.Outcome.WIN, (physical,), (public,), (terminal,),
                                             (), (), (), (), (decision,), 100_000, 0, True, True, True)

    projections = {role: projection(role) for role in ("control", "kp0", "repeat_control", "repeat_kp0")}

    def maintenance(arm):
        control = arm.arm is records.Arm.CONTROL
        shadow = None if control else records.KControlShadowState(True, (), None, None, None, False, True)
        return records.KControlMaintenanceRecord(arm, physical, ((-2,),), public, terminal, None, None,
            timings, (), (), shadow, None, shadow, "REFERENCE" if control else "NOT_REACHED")

    def pair_streams(roles):
        streams, headers = {}, []
        for role in roles:
            header, values = execution._projection_streams(projections[role], role)
            headers.append(header)
            streams.update(values)
        return streams, tuple(headers)

    def children(streams, role, prefix):
        arm = projections[role].arm
        streams[prefix + "certificate_audits"] = ()
        streams[prefix + "oracle_b_audits"] = ()
        streams[prefix + "oracle_b_coverage"] = (records.encode(records.OracleBCoverageRecord(
            arm, work.oracle_b_selected, ())),)
        streams[prefix + "evaluators"] = tuple(records.encode(records.EvaluatorRecord(
            arm, category, (), records.EvaluationStatus.PASS, "SYNTHETIC_INITIAL_ONLY", ""))
            for category in records.AssertionCategory)

    def bundle(kind, streams, headers):
        streams["boards"] = (records.encode(board),)
        return execution.WorkerBundle(work.position, kind, records.encode(board), work.arm_order,
            tuple((name, streams[name]) for name in execution.STREAM_NAMES if name in streams),
            headers, records.AuditStatus.PASS, ())

    primary_streams, primary_headers = pair_streams(("control", "kp0"))
    reference = records.encode(maintenance(projections["control"].arm))
    primary_streams["control_maintenance"] = (reference,)
    primary_streams["pairs"] = (records.encode(execution.game.pair_projections(
        projections["control"], projections["kp0"]).pair),)
    children(primary_streams, "kp0", "")
    primary = bundle(execution.WorkerKind.PRIMARY, primary_streams, primary_headers)

    repeated_streams, repeated_headers = pair_streams(("control", "kp0", "repeat_control", "repeat_kp0"))
    repeated_streams["control_maintenance"] = (reference,)
    repeated_streams["repeat_control_maintenance"] = (records.encode(maintenance(projections["repeat_control"].arm)),)
    children(repeated_streams, "repeat_kp0", "repeat_")
    repeated_streams["control_determinism"] = (records.encode(execution._control_determinism(
        projections["control"], projections["repeat_control"], repeated_streams["control_maintenance"],
        repeated_streams["repeat_control_maintenance"])),)
    repeated_streams["kp0_determinism"] = (records.encode(execution.audit.determinism_record(
        execution.audit.compare_determinism(projections["kp0"], projections["repeat_kp0"], selected=True))),)
    repeated = bundle(execution.WorkerKind.DETERMINISM, repeated_streams, repeated_headers)

    k_arm = execution._arm(work, records.Arm.K_CONTROL)
    kcontrol = bundle(execution.WorkerKind.K_CONTROL, {
        "control_maintenance": (reference,), "kcontrol_arms": (records.encode(k_arm),),
        "kcontrol_maintenance": (records.encode(maintenance(k_arm)),)}, ())
    return work, (primary, repeated, kcontrol)


class FreshWB02ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work, cls.bundles = _wb02_context_fixture()
        cls.envelope = _envelope()
        cls.wires = tuple(execution.encode_bundle_v2(bundle, _WB02_TEST_PROFILE,
            max_payload_bytes=cls.envelope.max_payload_bytes) for bundle in cls.bundles)

    def context(self, index=0, **changes):
        arguments = dict(wire=self.wires[index], work=self.work, kind=self.bundles[index].kind,
                         codec_profile_sha256=_WB02_TEST_PROFILE, envelope=self.envelope,
                         prior_primary_wire=None if index == 0 else self.wires[0])
        arguments.update(changes)
        return op._fresh_wb02_context(**arguments)

    def wire(self, bundle, profile=_WB02_TEST_PROFILE):
        return execution.encode_bundle_v2(bundle, profile, max_payload_bytes=self.envelope.max_payload_bytes)

    def test_exact_primary_and_downstream_wire_pass_real_semantic_validation(self):
        accepted = execution.revalidate_bundle
        for index, expected in enumerate(self.bundles):
            with self.subTest(kind=expected.kind), patch.object(execution, "revalidate_bundle", wraps=accepted) as checked:
                context = self.context(index)
            self.assertEqual(context.bundle, expected)
            self.assertEqual(context.work, self.work)
            self.assertIs(context.kind, expected.kind)
            self.assertEqual(context.codec_profile_sha256, _WB02_TEST_PROFILE)
            self.assertIs(context.wire, self.wires[index])
            self.assertEqual(checked.call_args_list[0].args, (context.bundle, self.work, expected.kind))
            self.assertEqual(checked.call_args_list[0].kwargs, {"max_payload_bytes": self.envelope.max_payload_bytes})
            self.assertEqual(checked.call_count, 1 if index == 0 else 2)

    def test_context_reports_exact_unit_and_all_stream_observations_including_empty_groups(self):
        for index, bundle in enumerate(self.bundles):
            with self.subTest(kind=bundle.kind):
                context = self.context(index)
                logical = sum(len(data) for _, values in bundle.streams for data in values)
                frames = sum(len(row.frame_bytes) for row in context.rows)
                self.assertEqual(context.logical_bytes, logical)
                self.assertEqual(context.physical_frame_bytes, frames)
                self.assertEqual(context.legacy_bundle_bytes, len(execution.encode_bundle(bundle)))
                self.assertEqual(context.wb02_wire_bytes, len(self.wires[index]))
                self.assertEqual(tuple(value.stream_name for value in context.stream_observations),
                                 tuple(name for name, _ in bundle.streams))
                expected_rows = [(name, (self.work.position, index, ordinal), data)
                                 for name, values in bundle.streams for ordinal, data in enumerate(values)]
                self.assertEqual([(row.stream_name, row.key, row.logical_bytes) for row in context.rows], expected_rows)
                for observation, (name, values) in zip(context.stream_observations, bundle.streams):
                    rows = tuple(row for row in context.rows if row.stream_name == name)
                    self.assertEqual((observation.record_count, observation.logical_bytes, observation.physical_frame_bytes),
                                     (len(values), sum(map(len, values)), sum(len(row.frame_bytes) for row in rows)))
                self.assertTrue(any(value.record_count == 0 and value.logical_bytes == value.physical_frame_bytes == 0
                                    for value in context.stream_observations) if index < 2 else True)
                for row in context.rows:
                    decoded = execution.physical.decode_frame(row.frame_bytes,
                        execution.physical.context_for(row.stream_name, _WB02_TEST_PROFILE))
                    self.assertEqual((decoded.key, decoded.logical_bytes, decoded.frame_length),
                                     (row.key, row.logical_bytes, row.frame_length))

    def test_each_boundary_is_fresh_and_neither_context_nor_view_is_wire_authority(self):
        accepted = execution.decode_bundle_view_v2
        with patch.object(execution, "decode_bundle_view_v2", wraps=accepted) as decoded:
            first, second = self.context(), self.context()
        self.assertIsNot(first, second)
        self.assertIsNot(first.bundle, second.bundle)
        self.assertIsNot(first.rows, second.rows)
        self.assertEqual(decoded.call_count, 2)
        self.assertTrue(all(call.args[0] is self.wires[0] for call in decoded.call_args_list))
        view = accepted(self.wires[0], _WB02_TEST_PROFILE)
        class BytesSubclass(bytes):
            pass
        for value in (first, second, view, self.bundles[0], bytearray(self.wires[0]), memoryview(self.wires[0]),
                      BytesSubclass(self.wires[0]), True, "36" * 32, b"\0" * 32):
            with self.subTest(input_type=type(value)), self.assertRaises(op.OperationalError):
                self.context(wire=value)

    def test_private_context_is_immutable_unserializable_and_has_no_authority_flag(self):
        context = self.context()
        self.assertTrue(type(context).__name__.startswith("_"))
        self.assertFalse(hasattr(context, "__dict__"))
        for value in (context,) + context.stream_observations:
            self.assertTrue({"validated", "trusted", "admitted"}.isdisjoint(dir(value)))
        with self.assertRaises(FrozenInstanceError):
            context.logical_bytes = 0
        with self.assertRaises(TypeError):
            pickle.dumps(context)
        names = inspect.signature(op._fresh_wb02_context).parameters
        self.assertTrue({"validated", "trusted", "admitted", "token", "context", "bundle", "view"}.isdisjoint(names))
        with self.assertRaises(TypeError):
            self.context(validated=True)

    def test_wrong_work_position_board_run_kind_and_exact_types_fail_closed(self):
        bad_works = (replace(self.work, position=self.work.position + 1),
                     replace(self.work, board=replace(self.work.board, fingerprint="different-fingerprint")),
                     replace(self.work, run_id="other-run"), None,
                     SimpleNamespace(**{field.name: getattr(self.work, field.name) for field in fields(self.work)}))
        for work in bad_works:
            with self.subTest(work=work), self.assertRaises(op.OperationalError):
                self.context(work=work)
        for kind in (execution.WorkerKind.DETERMINISM, execution.WorkerKind.K_CONTROL):
            with self.subTest(kind=kind), self.assertRaisesRegex(op.OperationalError, "^WB02_WORK_KIND_BINDING$"):
                self.context(kind=kind, prior_primary_wire=self.wires[0])
        for kind in ("PRIMARY", 0, True, None):
            with self.subTest(kind=kind), self.assertRaises(op.OperationalError):
                self.context(kind=kind)
        unselected = replace(self.work, determinism_selected=False)
        with self.assertRaises(op.OperationalError):
            self.context(1, work=unselected)

    def test_wrong_profile_type_length_and_current_binding_fail_closed(self):
        class BytesSubclass(bytes):
            pass
        for profile in (b"\x37" * 32, b"", b"x" * 31, b"x" * 33, bytearray(_WB02_TEST_PROFILE),
                        memoryview(_WB02_TEST_PROFILE), BytesSubclass(_WB02_TEST_PROFILE), True, "36" * 32):
            with self.subTest(profile_type=type(profile)), self.assertRaises(op.OperationalError):
                self.context(codec_profile_sha256=profile)

    def test_envelope_bound_and_exact_envelope_type_are_enforced(self):
        for envelope in (_envelope(max_payload_bytes=len(self.wires[0]) - 1), None,
                         SimpleNamespace(max_payload_bytes=self.envelope.max_payload_bytes)):
            with self.subTest(envelope=envelope), self.assertRaises(op.OperationalError):
                self.context(envelope=envelope)
        corrupted = replace(self.envelope)
        object.__setattr__(corrupted, "max_payload_bytes", True)
        with self.assertRaises(op.OperationalError):
            self.context(envelope=corrupted)

    def test_semantically_invalid_canonical_wire_is_not_accepted_by_representation_alone(self):
        bundle = self.bundles[0]
        arms = dict(bundle.streams)["control_arms"]
        wrong_arm = replace(records.decode(arms[0]), run_id="different-run")
        corrupted = replace(bundle, streams=tuple((name, (records.encode(wrong_arm),) if name == "control_arms" else values)
                                                for name, values in bundle.streams))
        wire = self.wire(corrupted)
        self.assertEqual(execution.decode_bundle_view_v2(wire, _WB02_TEST_PROFILE).bundle, corrupted)
        with self.assertRaises(op.OperationalError):
            self.context(wire=wire)

    def test_corruption_and_truncation_stay_owned_by_operational_boundary(self):
        corrupt = bytearray(self.wires[0])
        corrupt[-1] ^= 1
        for wire in (bytes(corrupt), self.wires[0][:-1], b"not-wb02"):
            with self.subTest(size=len(wire)), self.assertRaises(op.OperationalError):
                self.context(wire=wire)

    def test_fresh_lower_result_rows_and_sizes_are_checked_for_internal_consistency(self):
        view = execution.decode_bundle_view_v2(self.wires[0], _WB02_TEST_PROFILE)
        altered = [replace(view, **{name: getattr(view, name) + 1})
                   for name in ("logical_bytes", "legacy_bytes", "frame_bytes", "wire_bytes", "metadata_bytes")]
        altered += [replace(view, rows=view.rows[:-1]), replace(view, rows=view.rows[::-1]),
                    replace(view, rows=(replace(view.rows[0], key=(0, 2, 0)),) + view.rows[1:]),
                    replace(view, rows=(replace(view.rows[0], logical_bytes=records.encode(self.work.board) + b" "),) + view.rows[1:]),
                    replace(view, rows=(replace(view.rows[0], frame_length=view.rows[0].frame_length + 1),) + view.rows[1:])]
        for changed in altered:
            with self.subTest(view=changed), patch.object(execution, "decode_bundle_view_v2", return_value=changed):
                with self.assertRaises(op.OperationalError):
                    self.context()

    def test_primary_forbids_prior_and_downstream_requires_exact_prior_wire(self):
        with self.assertRaises(op.OperationalError):
            self.context(prior_primary_wire=self.wires[0])
        prior_context = self.context()
        prior_view = execution.decode_bundle_view_v2(self.wires[0], _WB02_TEST_PROFILE)
        for index in (1, 2):
            for prior in (None, bytearray(self.wires[0]), memoryview(self.wires[0]), prior_context, prior_view,
                          self.bundles[0], self.wires[index]):
                with self.subTest(kind=self.bundles[index].kind, prior_type=type(prior)), self.assertRaises(op.OperationalError):
                    self.context(index, prior_primary_wire=prior)

    def test_prior_is_freshly_decoded_and_semantically_validated_from_bytes(self):
        decode = execution.decode_bundle_view_v2
        validate = execution.revalidate_bundle
        for index in (1, 2):
            with self.subTest(kind=self.bundles[index].kind), \
                    patch.object(execution, "decode_bundle_view_v2", wraps=decode) as decoded, \
                    patch.object(execution, "revalidate_bundle", wraps=validate) as checked:
                context = self.context(index)
            self.assertEqual([call.args[0] for call in decoded.call_args_list], [self.wires[index], self.wires[0]])
            self.assertEqual([call.args[2] for call in checked.call_args_list],
                             [context.kind, execution.WorkerKind.PRIMARY])

    def test_copied_logical_premises_pass_while_rank_bound_physical_frames_differ(self):
        first = self.context()
        first_rows = {(row.stream_name, row.key[-1]): row for row in first.rows}
        for index in (1, 2):
            candidate = self.context(index)
            copied_names = ({name for name, _ in first.bundle.streams if name.startswith(("control_", "kp0_"))}
                            if index == 1 else {"control_maintenance"})
            copied = tuple(row for row in candidate.rows if row.stream_name in copied_names)
            self.assertTrue(copied)
            for row in copied:
                prior = first_rows[(row.stream_name, row.key[-1])]
                self.assertEqual(row.logical_bytes, prior.logical_bytes)
                self.assertNotEqual(row.key, prior.key)
                self.assertNotEqual(row.frame_bytes, prior.frame_bytes)

    def test_wrong_prior_logical_maintenance_fails_even_when_both_bundles_validate(self):
        first = self.bundles[0]
        reference = records.decode(dict(first.streams)["control_maintenance"][0])
        changed = replace(reference, timings=tuple((name, 9 if name == "evidence_ns" else value)
                                                   for name, value in reference.timings))
        prior = replace(first, streams=tuple((name, (records.encode(changed),) if name == "control_maintenance" else values)
                                            for name, values in first.streams))
        execution.revalidate_bundle(prior, self.work, execution.WorkerKind.PRIMARY,
                                    max_payload_bytes=self.envelope.max_payload_bytes)
        for index in (1, 2):
            with self.subTest(kind=self.bundles[index].kind), self.assertRaises(op.OperationalError):
                self.context(index, prior_primary_wire=self.wire(prior))

    def test_prior_header_prefix_and_profile_binding_fail_closed(self):
        first = self.bundles[0]
        changed = replace(first, projection_headers=(replace(first.projection_headers[0], diagnostics=("different-header",)),)
                                                    + first.projection_headers[1:])
        execution.revalidate_bundle(changed, self.work, execution.WorkerKind.PRIMARY,
                                    max_payload_bytes=self.envelope.max_payload_bytes)
        with self.assertRaises(op.OperationalError):
            self.context(1, prior_primary_wire=self.wire(changed))
        for index in (1, 2):
            with self.subTest(kind=self.bundles[index].kind), self.assertRaises(op.OperationalError):
                self.context(index, prior_primary_wire=self.wire(first, b"\x37" * 32))

    def test_prior_fail_and_incomplete_cannot_be_upgraded_but_retained_status_passes(self):
        for status, disallowed in ((records.AuditStatus.FAIL, (records.AuditStatus.PASS, records.AuditStatus.INCOMPLETE)),
                                   (records.AuditStatus.INCOMPLETE, (records.AuditStatus.PASS,))):
            prior = replace(self.bundles[0], status=status, reason_codes=("PRIVATE_ASSERTION_FALSIFIED",))
            for current in disallowed:
                candidate = replace(self.bundles[1], status=current,
                                    reason_codes=() if current is records.AuditStatus.PASS else ("PUBLIC_AUDIT_INCOMPLETE",))
                with self.subTest(prior=status, current=current), self.assertRaises(op.OperationalError):
                    self.context(1, wire=self.wire(candidate), prior_primary_wire=self.wire(prior))
            retained = replace(self.bundles[1], status=status, reason_codes=("PRIVATE_ASSERTION_FALSIFIED",))
            context = self.context(1, wire=self.wire(retained), prior_primary_wire=self.wire(prior))
            self.assertIs(context.bundle.status, status)

    def test_fresh_context_has_no_file_store_process_profile_or_reencoding_effects(self):
        forbidden = AssertionError("fresh WB02 validation performed an external effect")
        with ExitStack() as stack:
            for owner, names in ((builtins, ("open",)), (Path, ("open", "read_bytes", "write_bytes", "mkdir", "resolve")),
                                 (os, ("open", "stat", "lstat")),
                                 (store, ("StreamWriter", "FramedStreamWriter", "scan_stream", "scan_framed_stream")),
                                 (op.multiprocessing, ("get_context",)),
                                 (execution.physical, ("encode_frame", "capture_profile", "require_qualified_profile"))):
                for name in names:
                    stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            for index in range(3):
                self.assertEqual(self.context(index).bundle, self.bundles[index])

    def test_live_v1_coordinate_persists_jsonl_without_using_new_context_or_rf02(self):
        def workflow(work, *_):
            return tuple(op._OperationResult(op.UnitReceipt(work.position, bundle.kind, bundle.status,
                "ADMITTED", 1, 0), execution.decode_bundle(execution.encode_bundle(bundle)), ())
                for bundle in self.bundles)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(op, "_fresh_wb02_context", side_effect=AssertionError("live V1 called new context")), \
                patch.object(execution, "encode_bundle_v2", side_effect=AssertionError("live V1 encoded WB02")), \
                patch.object(execution, "decode_bundle_view_v2", side_effect=AssertionError("live V1 decoded WB02")), \
                patch.object(store, "FramedStreamWriter", side_effect=AssertionError("live V1 wrote RF02")), \
                patch.object(op, "_workflow", side_effect=workflow), \
                patch.object(op.harness, "_coordinator_private_bytes", return_value=200):
            result = op.coordinate((self.work,), directory, self.envelope)
            self.assertIs(result.status, records.AuditStatus.PASS, result.reason_codes)
            self.assertEqual(result.durable_units, 3)
            self.assertTrue((Path(directory) / "boards.jsonl").is_file())
            self.assertEqual(list(Path(directory).glob("*.pkf")), [])
            self.assertEqual(tuple(field.name for field in fields(op._OperationResult)),
                             ("receipt", "bundle", "samples", "observation"))

    def test_default_live_functions_have_no_new_v2_calls(self):
        for target in (op._worker_main, op._supervise_operation, op._workflow, op._EvidenceSink,
                       op._persist_r0, op.coordinate, op.readback_streams):
            with self.subTest(target=target.__name__):
                names = {node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                         for node in ast.walk(ast.parse(inspect.getsource(target))) if isinstance(node, ast.Call)}
                self.assertTrue({"_fresh_wb02_context", "encode_bundle_v2", "decode_bundle_v2",
                                 "decode_bundle_view_v2", "FramedStreamWriter"}.isdisjoint(names))


if __name__ == "__main__":
    unittest.main()
