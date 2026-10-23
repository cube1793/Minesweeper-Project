"""I6 bounded execution and append-only operational transport.

All effects require an explicit call. This is a candidate containment envelope,
not R0 admission or an Actual-E2 launcher. Each operation owns a fresh process;
the parent attaches its Windows Job before releasing any research work. Memory
samples use the accepted Job peak committed worker-tree bytes plus the current
coordinator private bytes (not instantaneous RSS). No E1 suite is imported.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import multiprocessing
from queue import Empty, Full, Queue
import sys
import threading
import time

from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_records as records
from experiments import program_k_e2_store as store
from experiments import program_k_harness as harness


class OperationalError(ValueError):
    """Malformed operational request or evidence; never a research verdict."""


class OperationalAbort(RuntimeError):
    """A static, answer-free containment reason."""


def _need(condition, reason):
    if not condition:
        raise OperationalError(reason)


def _integer(value, minimum=0, maximum=(1 << 64) - 1):
    _need(type(value) is int and minimum <= value <= maximum, "EXACT_INTEGER_REQUIRED")


@dataclass(frozen=True, slots=True)
class OperatingEnvelope:
    """Explicit candidate caps. I8/R0 owns acceptance and tightening.

    Every admitted unit is checkpointed; there is no implicit close/completion.
    The fixed report allowance is represented without performing I8 projections.
    """

    concurrency: int
    max_decision_wall_ms: int
    max_arm_wall_ms: int
    max_case_wall_ms: int
    max_job_wall_ms: int
    max_launcher_wall_ms: int
    shadow_timeout_ms: int
    max_physical_inputs: int
    worker_memory_cap_bytes: int
    coordinator_memory_cap_bytes: int
    memory_cap_bytes: int
    archive_cap_bytes: int
    monitor_interval_ms: int
    max_payload_bytes: int
    max_ipc_frame_bytes: int
    aggregation_wall_ms: int
    validation_wall_ms: int
    publication_wall_ms: int
    readback_wall_ms: int
    report_wall_ms: int
    fixed_report_receipt_allowance: int = 268_435_456

    def __post_init__(self):
        _need(type(self.concurrency) is int and self.concurrency in (1, 2, 4), "CONCURRENCY_DOMAIN")
        limits = ((self.max_decision_wall_ms, 30_000), (self.max_arm_wall_ms, 420_000),
                  (self.shadow_timeout_ms, 1_000), (self.max_launcher_wall_ms, 43_200_000),
                  (self.memory_cap_bytes, 4_294_967_296), (self.archive_cap_bytes, 17_179_869_184),
                  (self.max_ipc_frame_bytes, 65_536))
        for value, high in limits:
            _integer(value, 1, high)
        for value in (self.max_case_wall_ms, self.max_job_wall_ms, self.max_physical_inputs,
                      self.worker_memory_cap_bytes, self.coordinator_memory_cap_bytes,
                      self.monitor_interval_ms, self.max_payload_bytes, self.aggregation_wall_ms,
                      self.validation_wall_ms, self.publication_wall_ms, self.readback_wall_ms,
                      self.report_wall_ms):
            _integer(value, 1)
        _need(self.max_decision_wall_ms <= self.max_arm_wall_ms <= self.max_case_wall_ms
              <= self.max_job_wall_ms <= self.max_launcher_wall_ms, "WALL_CAP_ORDER")
        _need(self.monitor_interval_ms <= self.max_decision_wall_ms, "MONITOR_INTERVAL")
        _need(self.worker_memory_cap_bytes <= self.memory_cap_bytes
              and self.coordinator_memory_cap_bytes <= self.memory_cap_bytes, "MEMORY_CAP_ORDER")
        _need(self.max_ipc_frame_bytes >= 128
              and self.max_payload_bytes <= min(self.archive_cap_bytes, 67_108_864),
              "IPC_PAYLOAD_CAP_ORDER")
        _need(all(value <= self.max_launcher_wall_ms for value in (
            self.aggregation_wall_ms, self.validation_wall_ms, self.publication_wall_ms,
            self.readback_wall_ms, self.report_wall_ms)), "PHASE_WALL_CAP")
        _need(type(self.fixed_report_receipt_allowance) is int
              and self.fixed_report_receipt_allowance == 268_435_456, "FIXED_ARCHIVE_ALLOWANCE")


def _envelope(value):
    _need(type(value) is OperatingEnvelope, "EXACT_ENVELOPE_REQUIRED")
    OperatingEnvelope.__post_init__(value)
    return value


def validate_work_plan(plan):
    """No selection is made here; caller supplies the complete frozen finite plan."""
    _need(type(plan) is tuple and bool(plan), "FINITE_NONEMPTY_PLAN_REQUIRED")
    execution.revalidate_work_plan(plan)
    _need(tuple(work.position for work in plan) == tuple(range(len(plan))), "PLAN_POSITION_ORDER")
    _need(len({work.board.game_index for work in plan}) == len(plan), "DUPLICATE_BOARD_IDENTITY")
    return plan


def _kinds(work):
    result = (execution.WorkerKind.PRIMARY,)
    if work.determinism_selected:
        result += (execution.WorkerKind.DETERMINISM,)
    if work.k_control_selected:
        result += (execution.WorkerKind.K_CONTROL,)
    return result


def _kind_rank(kind):
    return (execution.WorkerKind.PRIMARY, execution.WorkerKind.DETERMINISM,
            execution.WorkerKind.K_CONTROL).index(kind)


def _unit_id(position, kind):
    return str(position) + ":" + kind.value


class DecisionWatchdog:
    """Sample the accepted decision stack; install no trace/profile callback.

    Regions bridge K analysis and policy in the runner frame. The execution
    adapter exposes the authenticated source targets; validation is separate.
    Sampling interval is explicit and an expired sample can never grant PASS.
    """

    def __init__(self, thread_id, codes, regions, envelope, report):
        self.thread_id, self.codes, self.regions = thread_id, frozenset(codes), tuple(regions)
        self.envelope, self.report = _envelope(envelope), report
        self.timed_out = False
        self._key = self._since = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def reset(self):
        with self._lock:
            self._key = self._since = None

    def sample(self, *, frames=None, now_ns=None):
        frames = sys._current_frames() if frames is None else frames
        now_ns = time.monotonic_ns() if now_ns is None else now_ns
        current, selected = frames.get(self.thread_id), None
        while current is not None:
            if current.f_code in self.codes or any(current.f_code is code and first <= current.f_lineno <= last
                                                   for code, first, last in self.regions):
                selected = current
            current = current.f_back
        key = None if selected is None else id(selected)
        breached = False
        with self._lock:
            if key is None:
                self._key = self._since = None
            elif self._key != key:
                self._key, self._since = key, now_ns
            elif not self.timed_out and now_ns - self._since >= self.envelope.max_decision_wall_ms * 1_000_000:
                self.timed_out = breached = True
        if breached:
            self.report("DECISION_TIMEOUT")
        return self.timed_out

    def _monitor(self):
        try:
            while not self._stop.wait(self.envelope.monitor_interval_ms / 1000):
                if self.sample():
                    return
        except BaseException:
            self.timed_out = True
            try:
                self.report("WATCHDOG_INCOMPLETE")
            except BaseException:
                pass

    def start(self):
        _need(self._thread is None, "WATCHDOG_ALREADY_STARTED")
        _need(sys.gettrace() is None and sys.getprofile() is None
              and threading.gettrace() is None and threading.getprofile() is None, "TIMING_TRACER_FORBIDDEN")
        self._thread = threading.Thread(target=self._monitor, daemon=True, name="program-k-e2-watchdog")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            if self._thread.is_alive():
                raise OperationalAbort("WATCHDOG_REAP_INCOMPLETE")


class _Channel:
    def __init__(self, connection, envelope):
        self.connection, self.envelope = connection, envelope
        self.lock = threading.Lock()

    def send(self, frame):
        _need(type(frame) is bytes and 0 < len(frame) <= self.envelope.max_ipc_frame_bytes,
              "IPC_FRAME_CAP")
        with self.lock:
            self.connection.send_bytes(frame)
            if self.connection.recv_bytes(1) != b"+":
                raise OperationalAbort("PARENT_ABORT")

    def event(self, name, arm):
        self.send(b"E" + json.dumps((name, arm), separators=(",", ":"), ensure_ascii=True).encode("ascii"))

    def result(self, data):
        _need(type(data) is bytes and 0 < len(data) <= self.envelope.max_payload_bytes, "PAYLOAD_CAP")
        self.send(b"H" + str(len(data)).encode("ascii"))
        chunk = self.envelope.max_ipc_frame_bytes - 1
        for start in range(0, len(data), chunk):
            self.send(b"D" + data[start:start + chunk])
        self.send(b"F")


def _worker_main(work, kind, first_bytes, envelope, connection, barrier):
    """Spawn target; barrier precedes generation/source checks/private answers."""
    barrier.wait()
    channel = _Channel(connection, envelope)
    watchdog = None
    abort_reason = None
    counts = {}
    current_arm = None

    def abort(code):
        nonlocal abort_reason
        abort_reason = abort_reason or code
        channel.send(b"X" + code.encode("ascii"))

    def check():
        if abort_reason is not None or (watchdog is not None and watchdog.timed_out):
            raise OperationalAbort(abort_reason or "DECISION_TIMEOUT")

    def observe(name, arm):
        nonlocal current_arm, abort_reason
        check()
        _need(name in ("ARM_START", "ARM_END", "BEFORE_INPUT")
              and arm in ("CONTROL", "K_P0", "K_CONTROL"), "WORKER_BOUNDARY")
        if name == "ARM_START":
            _need(current_arm is None and arm not in counts, "ARM_REUSE")
            current_arm, counts[arm] = arm, 0
        else:
            _need(current_arm == arm, "ARM_BOUNDARY_ORDER")
        if name == "BEFORE_INPUT":
            if counts[arm] >= envelope.max_physical_inputs:
                abort_reason = "PHYSICAL_INPUT_CAP"
                raise OperationalAbort(abort_reason)
            counts[arm] += 1
            watchdog.reset()
        channel.event(name, arm)
        if name == "ARM_END":
            current_arm = None
            watchdog.reset()

    try:
        channel.send(b"S")
        codes, regions = execution.decision_watchdog_targets()
        watchdog = DecisionWatchdog(threading.get_ident(), codes, regions, envelope, abort)
        watchdog.start()
        kwargs = dict(shadow_timeout_ms=envelope.shadow_timeout_ms,
                      max_physical_inputs=envelope.max_physical_inputs, observer=observe, abort_check=check)
        if kind is execution.WorkerKind.PRIMARY:
            _need(first_bytes is None, "PRIMARY_HAS_PRIOR")
            bundle = execution.execute_primary(work, **kwargs)
        else:
            first = execution.decode_bundle(first_bytes)
            if kind is execution.WorkerKind.DETERMINISM:
                bundle = execution.execute_repeat(work, first, **kwargs)
            else:
                _need(kind is execution.WorkerKind.K_CONTROL, "UNKNOWN_WORKER_KIND")
                bundle = execution.execute_k_control(work, first, **kwargs)
        check()
        _need(current_arm is None, "UNFINISHED_ARM")
        watchdog.stop()
        watchdog = None
        execution.revalidate_bundle(bundle, work, kind, max_payload_bytes=envelope.max_payload_bytes)
        channel.result(execution.encode_bundle(bundle))
    except BaseException as error:
        # No exception repr/traceback crosses the answer-owning worker boundary.
        reason = abort_reason or ("REQUIRED_EVIDENCE_INCOMPLETE" if isinstance(error, execution.E2EvidenceIncomplete)
                                 else "IMPLEMENTATION_IDENTITY_FAIL" if isinstance(error, execution.E2IdentityMismatch)
                                 else "PHYSICAL_INPUT_CAP" if type(error) is execution.E2ExecutionError
                                 and error.args == ("SYSTEM_INPUT_CAP",) else
                                 "WORKER_SEMANTIC_ERROR" if isinstance(error, ValueError) else "WORKER_EXCEPTION")
        try:
            channel.send(b"X" + reason.encode("ascii"))
        except BaseException:
            pass
    finally:
        if watchdog is not None:
            try:
                watchdog.stop()
            except BaseException:
                pass
        connection.close()


class _MemoryLedger:
    """Account all simultaneously active worker Jobs, never one worker alone."""

    def __init__(self, envelope):
        self.envelope = envelope
        self.values = {}
        self.lock = threading.Lock()

    def sample(self, token, worker, unit_id, elapsed_ns):
        _integer(worker)
        coordinator = harness._coordinator_private_bytes()
        _integer(coordinator)
        with self.lock:
            self.values[token] = worker
            total_worker = sum(self.values.values())
        sample = records.ResourceSampleRecord(unit_id, records.ProcessRole.COMBINED, total_worker,
            coordinator, total_worker + coordinator, "monotonic_ns:" + str(time.monotonic_ns()),
            elapsed_ns, records.MemoryMethod.PRIVATE_BYTES)
        breach = (worker > self.envelope.worker_memory_cap_bytes
                  or coordinator > self.envelope.coordinator_memory_cap_bytes
                  or sample.combined_bytes > self.envelope.memory_cap_bytes)
        return sample, breach

    def remove(self, token):
        with self.lock:
            self.values.pop(token, None)


@dataclass(frozen=True, slots=True)
class UnitReceipt:
    """Operational total wall, not a future R0 component measurement.

    R0 must measure non-overlapping or explicitly non-double-counted P64 primary
    pair, K64 K-CONTROL, O64 Oracle-B and D64 determinism wall components. These
    total elapsed values alone do not satisfy that later protocol requirement.
    """

    position: int
    kind: execution.WorkerKind
    status: records.AuditStatus
    reason: str
    elapsed_ns: int
    exit_code: int | None

    def __post_init__(self):
        _integer(self.position)
        _integer(self.elapsed_ns)
        _need(type(self.kind) is execution.WorkerKind and type(self.status) is records.AuditStatus,
              "UNIT_CLASSIFICATION_TYPE")
        _need(type(self.reason) is str and self.reason and len(self.reason) <= 80
              and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in self.reason), "STATIC_REASON_REQUIRED")
        _need(self.exit_code is None or type(self.exit_code) is int, "EXIT_CODE_TYPE")


@dataclass(frozen=True, slots=True)
class _OperationResult:
    receipt: UnitReceipt
    bundle: object
    samples: tuple


def _missing(work, kind, reason):
    return _OperationResult(UnitReceipt(work.position, kind, records.AuditStatus.INCOMPLETE,
                                       reason, 0, None), None, ())


def _bind_prior_bundle(candidate, first_bytes, work, kind, envelope):
    """Bind returned repeat/reference premises to the earlier producer exactly."""
    if kind is execution.WorkerKind.PRIMARY:
        _need(first_bytes is None, "PRIMARY_PRIOR_BINDING")
        return
    first = execution.decode_bundle(first_bytes)
    execution.revalidate_bundle(first, work, execution.WorkerKind.PRIMARY,
                                max_payload_bytes=envelope.max_payload_bytes)
    actual, expected = dict(candidate.streams), dict(first.streams)
    if kind is execution.WorkerKind.DETERMINISM:
        names = tuple(name for name in expected if name.startswith("control_") or name.startswith("kp0_"))
        _need(all(actual.get(name) == expected[name] for name in names), "REPEAT_FIRST_PREMISE_BINDING")
        _need(candidate.projection_headers[:len(first.projection_headers)] == first.projection_headers,
              "REPEAT_FIRST_HEADER_BINDING")
        _need(first.status is not records.AuditStatus.FAIL or candidate.status is records.AuditStatus.FAIL,
              "FIRST_FAILURE_CANNOT_BE_UPGRADED")
        _need(first.status is not records.AuditStatus.INCOMPLETE or candidate.status is not records.AuditStatus.PASS,
              "FIRST_INCOMPLETE_CANNOT_BE_UPGRADED")
    else:
        _need(actual.get("control_maintenance") == expected.get("control_maintenance"),
              "KCONTROL_REFERENCE_BINDING")


def _supervise_operation(work, kind, first_bytes, envelope, ledger, cancel,
                         job_started_ns, launcher_started_ns, *, worker_target=None):
    """One disposable process. The private test target never changes the public plan."""
    started = time.monotonic_ns()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    barrier = context.Event()
    process = context.Process(target=_worker_main if worker_target is None else worker_target,
                              args=(work, kind, first_bytes, envelope, child, barrier))
    inbox, reader_stop = Queue(maxsize=2), threading.Event()
    reader = api = job = peak_memory = None
    token = object()
    first_sample = peak_sample = last_sample = None
    reason, diagnosed_fail = None, False
    bundle = None
    wire = bytearray()
    expected_size = None
    started_frame = finished = False
    current_arm = None
    arm_started = None
    counts = {}

    def read_frames():
        while not reader_stop.is_set():
            try:
                value = (True, parent.recv_bytes(envelope.max_ipc_frame_bytes))
            except BaseException:
                value = (False, b"")
            while not reader_stop.is_set():
                try:
                    inbox.put(value, timeout=0.02)
                    break
                except Full:
                    continue
            if not value[0]:
                return

    def sample():
        nonlocal first_sample, peak_sample, last_sample
        current, breached = ledger.sample(token, peak_memory(), _unit_id(work.position, kind),
                                          time.monotonic_ns() - started)
        first_sample = first_sample or current
        last_sample = current
        if peak_sample is None or current.combined_bytes > peak_sample.combined_bytes:
            peak_sample = current
        if breached:
            cancel.set()
            raise OperationalAbort("MEMORY_CAP")

    try:
        if cancel.is_set():
            raise OperationalAbort("CANCELLED")
        process.start()
        child.close()
        api, job, peak_memory = harness._attach_memory_job(process.pid, envelope.worker_memory_cap_bytes)
        sample()
        reader = threading.Thread(target=read_frames, daemon=True, name="program-k-e2-ipc-reader")
        reader.start()
        barrier.set()
        while True:
            if cancel.is_set():
                raise OperationalAbort("CANCELLED")
            sample()
            now = time.monotonic_ns()
            deadlines = ((started + envelope.max_case_wall_ms * 1_000_000, "CASE_TIMEOUT"),
                         (job_started_ns + envelope.max_job_wall_ms * 1_000_000, "JOB_TIMEOUT"),
                         (launcher_started_ns + envelope.max_launcher_wall_ms * 1_000_000, "LAUNCHER_TIMEOUT"))
            if current_arm is not None:
                deadlines += ((arm_started + envelope.max_arm_wall_ms * 1_000_000, "ARM_TIMEOUT"),)
            deadline, expiry = min(deadlines)
            if now >= deadline:
                if expiry in ("JOB_TIMEOUT", "LAUNCHER_TIMEOUT"):
                    cancel.set()
                raise OperationalAbort(expiry)
            if finished and not process.is_alive():
                process.join(timeout=0)
                if process.exitcode != 0:
                    raise OperationalAbort("PROCESS_NONZERO_EXIT")
                break
            wait = min(envelope.monitor_interval_ms / 1000, (deadline - now) / 1_000_000_000)
            try:
                good, frame = inbox.get(timeout=wait)
            except Empty:
                if not process.is_alive():
                    if finished:
                        process.join(timeout=0)
                        if process.exitcode != 0:
                            raise OperationalAbort("PROCESS_NONZERO_EXIT")
                        break
                    raise OperationalAbort("PROCESS_LOST")
                continue
            if not good:
                if finished:
                    process.join(timeout=wait)
                    continue
                raise OperationalAbort("PROCESS_LOST")
            _need(not finished and frame, "MALFORMED_IPC")
            tag, data = frame[:1], frame[1:]
            if tag == b"S":
                _need(not started_frame and not data, "MALFORMED_IPC")
                started_frame = True
            elif tag == b"E":
                _need(started_frame and expected_size is None, "MALFORMED_IPC")
                event = json.loads(data.decode("ascii"))
                _need(type(event) is list and len(event) == 2
                      and event[0] in ("ARM_START", "ARM_END", "BEFORE_INPUT")
                      and event[1] in ("CONTROL", "K_P0", "K_CONTROL"), "MALFORMED_IPC")
                name, arm = event
                if name == "ARM_START":
                    _need(current_arm is None and arm not in counts, "MALFORMED_IPC")
                    current_arm, arm_started, counts[arm] = arm, now, 0
                else:
                    _need(current_arm == arm, "MALFORMED_IPC")
                    if name == "ARM_END":
                        current_arm, arm_started = None, None
                    else:
                        counts[arm] += 1
                        if counts[arm] > envelope.max_physical_inputs:
                            raise OperationalAbort("PHYSICAL_INPUT_CAP")
            elif tag == b"H":
                _need(started_frame and expected_size is None and current_arm is None
                      and data and all(48 <= c <= 57 for c in data), "MALFORMED_IPC")
                expected_size = int(data)
                _need(str(expected_size).encode("ascii") == data and expected_size > 0, "MALFORMED_IPC")
                if expected_size > envelope.max_payload_bytes:
                    raise OperationalAbort("IPC_PAYLOAD_CAP")
            elif tag == b"D":
                _need(expected_size is not None and data and len(wire) + len(data) <= expected_size,
                      "MALFORMED_IPC")
                wire.extend(data)
            elif tag == b"F":
                _need(not data and expected_size is not None and len(wire) == expected_size, "MALFORMED_IPC")
                validation_started = time.monotonic_ns()
                candidate = execution.decode_bundle(bytes(wire))
                execution.revalidate_bundle(candidate, work, kind, max_payload_bytes=envelope.max_payload_bytes)
                _bind_prior_bundle(candidate, first_bytes, work, kind, envelope)
                streams = dict(candidate.streams)
                physical_names = ({"CONTROL": "control_physical_inputs", "K_P0": "kp0_physical_inputs"}
                                  if kind is execution.WorkerKind.PRIMARY else
                                  {"CONTROL": "repeat_control_physical_inputs", "K_P0": "repeat_kp0_physical_inputs"}
                                  if kind is execution.WorkerKind.DETERMINISM else
                                  {"K_CONTROL": "kcontrol_maintenance"})
                expected_counts = {arm: len(streams[name]) for arm, name in physical_names.items() if name in streams}
                _need(counts == expected_counts, "PHYSICAL_INPUT_STREAM_BINDING")
                bundle = candidate
                diagnosed_fail = candidate.status is records.AuditStatus.FAIL
                if time.monotonic_ns() - validation_started >= envelope.validation_wall_ms * 1_000_000:
                    raise OperationalAbort("VALIDATION_TIMEOUT")
                wire.clear()
                finished = True
            elif tag == b"X":
                allowed = {b"DECISION_TIMEOUT", b"WATCHDOG_INCOMPLETE", b"PHYSICAL_INPUT_CAP",
                           b"WORKER_SEMANTIC_ERROR", b"WORKER_EXCEPTION", b"REQUIRED_EVIDENCE_INCOMPLETE",
                           b"IMPLEMENTATION_IDENTITY_FAIL"}
                _need(data in allowed, "MALFORMED_IPC")
                diagnosed_fail = data in (b"WORKER_SEMANTIC_ERROR", b"IMPLEMENTATION_IDENTITY_FAIL")
                raise OperationalAbort(data.decode("ascii"))
            else:
                raise OperationalError("MALFORMED_IPC")
            parent.send_bytes(b"+")
    except OperationalAbort as error:
        reason = str(error)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError, OverflowError):
        reason, diagnosed_fail = "MALFORMED_IPC_OR_IDENTITY", True
    except (Exception, KeyboardInterrupt):
        reason = "SUPERVISION_INCOMPLETE"
    finally:
        reader_stop.set()
        if job is not None:
            try:
                sample()
            except BaseException:
                reason = reason or "MEMORY_MONITOR_INCOMPLETE"
            try:
                if process.is_alive():
                    api.TerminateJobObject(job, 1)
                if not api.CloseHandle(job):
                    reason = reason or "JOB_CLOSE_INCOMPLETE"
            except BaseException:
                reason = reason or "JOB_CLOSE_INCOMPLETE"
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
                reason = reason or "WORKER_REAP_INCOMPLETE"
            if process.is_alive():
                reason = "WORKER_REAP_INCOMPLETE"
        parent.close()
        child.close()
        if reader is not None:
            reader.join(timeout=1)
            if reader.is_alive():
                reason = reason or "READER_REAP_INCOMPLETE"
        ledger.remove(token)
    elapsed = time.monotonic_ns() - started
    if not finished and reason is None:
        reason = "MISSING_RESULT"
    if reason is None and elapsed >= envelope.max_case_wall_ms * 1_000_000:
        reason = "CASE_TIMEOUT"
    status = (records.AuditStatus.FAIL if diagnosed_fail else records.AuditStatus.INCOMPLETE
              if reason is not None else bundle.status)
    samples = tuple(item for index, item in enumerate((first_sample, peak_sample, last_sample))
                    if item is not None and item not in (first_sample, peak_sample, last_sample)[:index])
    exit_code = process.exitcode
    if process.pid is not None and not process.is_alive():
        process.close()
    summary_reason = reason or ("AUDIT_FAIL" if status is records.AuditStatus.FAIL else
                                "AUDIT_INCOMPLETE" if status is records.AuditStatus.INCOMPLETE else "ADMITTED")
    return _OperationResult(UnitReceipt(work.position, kind, status, summary_reason, elapsed,
                                       exit_code), bundle, samples)


def _workflow(work, envelope, ledger, cancel, job_started, launcher_started):
    outcomes = []
    first = None
    for kind in _kinds(work):
        if cancel.is_set():
            result = _missing(work, kind, "CANCELLED")
        elif kind is not execution.WorkerKind.PRIMARY and first is None:
            result = _missing(work, kind, "PRIMARY_PREMISES_MISSING")
        else:
            result = _supervise_operation(work, kind, first, envelope, ledger, cancel,
                                          job_started, launcher_started)
        outcomes.append(result)
        if kind is execution.WorkerKind.PRIMARY and result.bundle is not None:
            first = execution.encode_bundle(result.bundle)
    return tuple(outcomes)


class _EvidenceSink:
    """One I2 writer per centrally declared stream; no rescan or alternate store."""

    def __init__(self, root, envelope, operation_count):
        self.envelope = envelope
        # Reserve bounded operational events/resources before accepting data.
        # Static unit IDs and at most three memory samples use <4096 bytes/unit.
        self.reserve = 4096 * (operation_count + 1)
        _need(self.reserve < envelope.archive_cap_bytes, "ARCHIVE_OPERATION_RESERVE")
        self.writers = {}
        self.event_ordinal = 0
        self.resource_ordinal = 0
        self.started = time.monotonic_ns()
        self.durable_units = 0
        self.durable_boards = 0
        self.sealed = False
        self.names = tuple(execution.STREAM_NAMES) + ("operations", "resources")
        _need(len(self.names) == len(set(self.names)), "DUPLICATE_STREAM_NAME")
        try:
            for name in self.names:
                self.writers[name] = store.StreamWriter(root, name)
        except BaseException:
            self.close()
            raise

    @property
    def byte_length(self):
        return sum(writer.byte_length for writer in self.writers.values())

    @staticmethod
    def _size(key, data):
        return len(json.dumps(key, separators=(",", ":")).encode("ascii")) + len(data) + 2

    def _append(self, name, key, record):
        data = records.encode(record)
        _need(self.byte_length + self._size(key, data) <= self.envelope.archive_cap_bytes,
              "ARCHIVE_OPERATION_RESERVE_EXHAUSTED")
        self.writers[name].append(key, record)

    def event(self, unit_id, event_kind, status, phase=records.Phase.EXECUTION):
        value = records.OperationEventRecord(phase, unit_id, event_kind,
            time.monotonic_ns() - self.started, self.event_ordinal, status)
        self._append("operations", (self.event_ordinal,), value)
        self.event_ordinal += 1

    def checkpoint(self):
        for writer in self.writers.values():
            writer.checkpoint()

    def admit(self, result):
        receipt, bundle = result.receipt, result.bundle
        rank = _kind_rank(receipt.kind)
        pending = []
        if bundle is not None:
            for name, values in bundle.streams:
                _need(name in execution.STREAM_NAMES, "UNKNOWN_STREAM")
                for index, data in enumerate(values):
                    _need(type(data) is bytes, "NONCANONICAL_STREAM_RECORD")
                    record = records.decode(data)
                    key = (receipt.position, rank, index)
                    pending.append((name, key, record, data))
            added = sum(self._size(key, data) for _, key, _, data in pending)
            if self.byte_length + added > self.envelope.archive_cap_bytes - self.reserve:
                status = records.AuditStatus.FAIL if receipt.status is records.AuditStatus.FAIL else records.AuditStatus.INCOMPLETE
                receipt = UnitReceipt(receipt.position, receipt.kind, status, "ARCHIVE_CAP", receipt.elapsed_ns,
                                      receipt.exit_code)
                pending = []
            else:
                for name, key, record, _ in pending:
                    self._append(name, key, record)
        for sample in result.samples:
            _need(type(sample) is records.ResourceSampleRecord, "INVALID_MEMORY_SAMPLE")
            self._append("resources", (self.resource_ordinal,), sample)
            self.resource_ordinal += 1
        state = records.OperationStatus.COMPLETED if receipt.status is records.AuditStatus.PASS else (
            records.OperationStatus.FAILED if receipt.status is records.AuditStatus.FAIL else records.OperationStatus.INCOMPLETE)
        self.event(_unit_id(receipt.position, receipt.kind) + ":" + receipt.reason,
                   records.EventKind.END if state is records.OperationStatus.COMPLETED else records.EventKind.ERROR, state)
        self.checkpoint()
        self.durable_units += 1
        if receipt.kind is execution.WorkerKind.PRIMARY and pending:
            self.durable_boards += 1
            self.event("durable_primary_count:" + str(self.durable_boards), records.EventKind.PROGRESS,
                       records.OperationStatus.RUNNING)
            self.writers["operations"].checkpoint()
        return receipt

    def seal(self):
        self.sealed = True
        return tuple(self.writers[name].seal() for name in self.names)

    def close(self):
        for writer in self.writers.values():
            writer.close()


@dataclass(frozen=True, slots=True)
class CoordinatorResult:
    """Compact operation receipts only; detailed evidence lives in I2 streams."""

    receipts: tuple
    streams: tuple
    durable_units: int
    durable_primary_boards: int
    archive_bytes: int
    status: records.AuditStatus
    reason_codes: tuple = ()


def readback_streams(root, sealed_streams, envelope):
    """Verify each declared sealed I2 stream once, without retaining its records.

    The unchanged scanner owns canonical records, key ordering and byte hashing.
    Its visitor checks the deadline during that same pass; an empty stream is
    checked before and after scanning. A verified digest tuple is detached and
    immutable. No completion publication or second whole-stream pass occurs.
    """
    envelope = _envelope(envelope)
    deadline = time.monotonic_ns() + envelope.readback_wall_ms * 1_000_000

    def check_deadline(*_):
        if time.monotonic_ns() >= deadline:
            raise OperationalAbort("READBACK_TIMEOUT")

    try:
        names = tuple(execution.STREAM_NAMES) + ("operations", "resources")
        _need(type(sealed_streams) is tuple and len(sealed_streams) == len(names),
              "READBACK_INTEGRITY_FAIL")
        _need(len(names) == len(set(names)), "READBACK_INTEGRITY_FAIL")
        for digest in sealed_streams:
            _need(type(digest) is records.StreamDigest, "READBACK_INTEGRITY_FAIL")
            records.StreamDigest.__post_init__(digest)
        by_name = {digest.name: digest for digest in sealed_streams}
        _need(len(by_name) == len(names) and set(by_name) == set(names), "READBACK_INTEGRITY_FAIL")
        verified = []
        for name in names:
            check_deadline()
            observed = store.scan_stream(root, name, visit=check_deadline)
            check_deadline()
            _need(type(observed) is records.StreamDigest, "READBACK_INTEGRITY_FAIL")
            records.StreamDigest.__post_init__(observed)
            expected = by_name[name]
            _need((observed.name, observed.sha256, observed.byte_length, observed.record_count)
                  == (expected.name, expected.sha256, expected.byte_length, expected.record_count),
                  "READBACK_INTEGRITY_FAIL")
            verified.append(observed)
        return tuple(verified)
    except OperationalAbort:
        raise
    except Exception:
        raise OperationalError("READBACK_INTEGRITY_FAIL") from None


def coordinate(plan, root, envelope, *, cancel=None, launcher_started_ns=None):
    """Execute only a supplied finite plan; never choose N or authorize a run.

    At most c complete board workflows are retained. Waiting/admission is in
    supplied position order, so a slow early board cannot create an unbounded
    reorder buffer. A later board is submitted only after a prior admission.
    No process is reused, retried or silently dropped. No COMPLETE receipt is
    published here: verified stream seals are not an Actual-E2 completion claim.
    A PASS return requires the strict one-pass readback after all stream seals.
    """
    plan, envelope = validate_work_plan(plan), _envelope(envelope)
    _need(cancel is None or (callable(getattr(cancel, "is_set", None))
                            and callable(getattr(cancel, "set", None))), "CANCELLATION_TOKEN")
    cancel = threading.Event() if cancel is None else cancel
    started = time.monotonic_ns()
    launcher_started_ns = started if launcher_started_ns is None else launcher_started_ns
    _integer(launcher_started_ns)
    _need(launcher_started_ns <= started, "FUTURE_LAUNCHER_START")
    sink = _EvidenceSink(root, envelope, sum(len(_kinds(work)) for work in plan))
    ledger = _MemoryLedger(envelope)
    futures, receipts = {}, []
    pool = ThreadPoolExecutor(max_workers=envelope.concurrency, thread_name_prefix="program-k-e2-supervisor")
    next_submit = 0
    streams = ()
    coordinator_reasons = []
    admission_closed_reason = None

    def parent_limits():
        now = time.monotonic_ns()
        reason = ("LAUNCHER_TIMEOUT" if now - launcher_started_ns >= envelope.max_launcher_wall_ms * 1_000_000
                  else "JOB_TIMEOUT" if now - started >= envelope.max_job_wall_ms * 1_000_000 else None)
        try:
            _, breach = ledger.sample("coordinator", 0, "coordinator", now - started)
            if breach:
                reason = reason or "MEMORY_CAP"
        except Exception:
            reason = reason or "MEMORY_MONITOR_INCOMPLETE"
        finally:
            ledger.remove("coordinator")
        if reason is not None:
            cancel.set()
            if reason not in coordinator_reasons:
                coordinator_reasons.append(reason)
        return reason

    def incomplete(result, reason):
        old = result.receipt
        status = records.AuditStatus.FAIL if old.status is records.AuditStatus.FAIL else records.AuditStatus.INCOMPLETE
        return _OperationResult(UnitReceipt(old.position, old.kind, status, reason,
                                            old.elapsed_ns, old.exit_code), None, result.samples)

    try:
        sink.event("coordinator", records.EventKind.START, records.OperationStatus.RUNNING)
        sink.checkpoint()
        for position, work in enumerate(plan):
            parent_limits()
            while not cancel.is_set() and next_submit < len(plan) and len(futures) < envelope.concurrency:
                pending = plan[next_submit]
                for kind in _kinds(pending):
                    sink.event(_unit_id(pending.position, kind), records.EventKind.START,
                               records.OperationStatus.RUNNING)
                sink.checkpoint()
                futures[next_submit] = pool.submit(_workflow, pending, envelope, ledger, cancel,
                                                   started, launcher_started_ns)
                next_submit += 1
            future = futures.pop(position, None)
            if future is None:
                for kind in _kinds(work):
                    sink.event(_unit_id(work.position, kind), records.EventKind.START,
                               records.OperationStatus.INCOMPLETE)
                results = tuple(_missing(work, kind, "CANCELLED_BEFORE_START") for kind in _kinds(work))
            else:
                try:
                    results = future.result()
                except KeyboardInterrupt:
                    cancel.set()
                    results = future.result()
                except Exception:
                    results = tuple(_missing(work, kind, "SUPERVISOR_EXCEPTION") for kind in _kinds(work))
            _need(type(results) is tuple and tuple(result.receipt.kind for result in results) == _kinds(work),
                  "MISSING_OR_DUPLICATE_TERMINAL_UNIT")
            for result in results:
                _need(result.receipt.position == position, "TERMINAL_UNIT_IDENTITY")
                reason = parent_limits()
                if admission_closed_reason is not None:
                    reason = admission_closed_reason
                if reason is not None:
                    admission_closed_reason = reason
                    result = incomplete(result, reason)
                if result.bundle is not None:
                    validation_started = time.monotonic_ns()
                    execution.revalidate_bundle(result.bundle, work, result.receipt.kind,
                                                max_payload_bytes=envelope.max_payload_bytes)
                    if time.monotonic_ns() - validation_started >= envelope.validation_wall_ms * 1_000_000:
                        result = incomplete(result, "VALIDATION_TIMEOUT")
                        admission_closed_reason = "VALIDATION_TIMEOUT"
                        cancel.set()
                        if "VALIDATION_TIMEOUT" not in coordinator_reasons:
                            coordinator_reasons.append("VALIDATION_TIMEOUT")
                publication_started = time.monotonic_ns()
                receipt = sink.admit(result)
                receipts.append(receipt)
                if time.monotonic_ns() - publication_started >= envelope.publication_wall_ms * 1_000_000:
                    admission_closed_reason = "PUBLICATION_TIMEOUT"
                    cancel.set()
                    if "PUBLICATION_TIMEOUT" not in coordinator_reasons:
                        coordinator_reasons.append("PUBLICATION_TIMEOUT")
                parent_limits()
                if receipt.reason in ("ARCHIVE_CAP", "MEMORY_CAP", "JOB_TIMEOUT", "LAUNCHER_TIMEOUT"):
                    admission_closed_reason = receipt.reason
                    cancel.set()
        parent_limits()
        status = records.AuditStatus.FAIL if any(value.status is records.AuditStatus.FAIL for value in receipts) else (
            records.AuditStatus.INCOMPLETE if coordinator_reasons or any(value.status is records.AuditStatus.INCOMPLETE for value in receipts)
            else records.AuditStatus.PASS)
        for reason in coordinator_reasons:
            sink.event("coordinator:" + reason, records.EventKind.ERROR, records.OperationStatus.INCOMPLETE,
                       records.Phase.PUBLICATION if reason == "PUBLICATION_TIMEOUT" else records.Phase.EXECUTION)
        # Successful admission is a distinct boundary from final stream seals.
        # Only the returned status plus read-back seals describes the final I6 operation.
        sink.event("coordinator:ADMISSION_END" if status is records.AuditStatus.PASS else "coordinator",
                   records.EventKind.END,
                   records.OperationStatus.COMPLETED if status is records.AuditStatus.PASS else (
                       records.OperationStatus.FAILED if status is records.AuditStatus.FAIL else records.OperationStatus.INCOMPLETE))
        streams = sink.seal()
        try:
            streams = readback_streams(root, streams, envelope)
        except OperationalAbort:
            coordinator_reasons.append("READBACK_TIMEOUT")
            if status is not records.AuditStatus.FAIL:
                status = records.AuditStatus.INCOMPLETE
        except OperationalError:
            coordinator_reasons.append("READBACK_INTEGRITY_FAIL")
            if status is not records.AuditStatus.FAIL:
                status = records.AuditStatus.INCOMPLETE
        # Sealing is only stream durability, never an Actual-E2 COMPLETE marker.
        # Failed post-seal readback is reported above, without rewriting seals.
        # A cap crossed by final fsync/readback still forbids a successful return.
        if parent_limits() is not None and status is not records.AuditStatus.FAIL:
            status = records.AuditStatus.INCOMPLETE
        return CoordinatorResult(tuple(receipts), streams, sink.durable_units, sink.durable_boards,
                                 sink.byte_length, status, tuple(coordinator_reasons))
    finally:
        cancel.set()
        pool.shutdown(wait=True, cancel_futures=False)
        sink.close()
