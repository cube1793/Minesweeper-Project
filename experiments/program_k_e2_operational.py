"""I6 bounded execution and append-only operational transport.

All effects require an explicit call. This is a candidate containment envelope,
not R0 admission or an Actual-E2 launcher. Each operation owns a fresh process;
the parent attaches its Windows Job before releasing any research work. Memory
samples use the accepted Job peak committed worker-tree bytes plus the current
coordinator private bytes (not instantaneous RSS). No E1 suite is imported.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import Enum
import json
import multiprocessing
from pathlib import Path
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

    def result(self, data, *, tags=(b"H", b"D", b"F")):
        _need(type(data) is bytes and 0 < len(data) <= self.envelope.max_payload_bytes, "PAYLOAD_CAP")
        self.send(tags[0] + str(len(data)).encode("ascii"))
        chunk = self.envelope.max_ipc_frame_bytes - 1
        for start in range(0, len(data), chunk):
            self.send(tags[1] + data[start:start + chunk])
        self.send(tags[2])


def _worker_main(work, kind, first_bytes, envelope, connection, barrier, r0_observe=False):
    """Spawn target; barrier precedes generation/source checks/private answers."""
    barrier.wait()
    channel = _Channel(connection, envelope)
    watchdog = None
    abort_reason = None
    counts = {}
    current_arm = None
    oracle_facts = []
    r0_arm_started, r0_max_arm = None, 0

    def observe_oracle(fact):
        execution.audit.OracleBTimingFact.__post_init__(fact)
        _need(type(fact) is execution.audit.OracleBTimingFact
              and fact.arm == execution._arm(work, records.Arm.K_P0,
                  repeat=kind is execution.WorkerKind.DETERMINISM)
              and not oracle_facts, "ORACLE_TIMING_IDENTITY")
        oracle_facts.append(fact)

    def observe_prior(fact):
        _need(type(fact) is execution.PriorBindingTimingFact
              and fact.work_position == work.position and fact.kind is kind,
              "PRIOR_TIMING_IDENTITY")
        execution.PriorBindingTimingFact.__post_init__(fact)
        channel.send(b"B")

    def abort(code):
        nonlocal abort_reason
        abort_reason = abort_reason or code
        channel.send(b"X" + code.encode("ascii"))

    def check():
        if abort_reason is not None or (watchdog is not None and watchdog.timed_out):
            raise OperationalAbort(abort_reason or "DECISION_TIMEOUT")

    def observe(name, arm):
        nonlocal current_arm, abort_reason
        nonlocal r0_arm_started, r0_max_arm
        check()
        _need(name in ("ARM_START", "ARM_END", "BEFORE_INPUT")
              and arm in ("CONTROL", "K_P0", "K_CONTROL"), "WORKER_BOUNDARY")
        if name == "ARM_START":
            _need(current_arm is None and arm not in counts, "ARM_REUSE")
            current_arm, counts[arm] = arm, 0
            if r0_observe:
                r0_arm_started = time.perf_counter_ns()
        else:
            _need(current_arm == arm, "ARM_BOUNDARY_ORDER")
        if name == "BEFORE_INPUT":
            if counts[arm] >= envelope.max_physical_inputs:
                abort_reason = "PHYSICAL_INPUT_CAP"
                raise OperationalAbort(abort_reason)
            counts[arm] += 1
            watchdog.reset()
        if r0_observe and name == "ARM_END":
            r0_max_arm = max(r0_max_arm, time.perf_counter_ns() - r0_arm_started)
            r0_arm_started = None
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
        if r0_observe and work.oracle_b_selected and kind is not execution.WorkerKind.K_CONTROL:
            kwargs["oracle_timing_observer"] = observe_oracle
        if r0_observe and work.oracle_b_selected and kind is not execution.WorkerKind.PRIMARY:
            # The acknowledged frame ends a parent-clock boundary containing
            # spawn transport, child decode and accepted prior validation, before
            # any downstream solver can begin.
            kwargs["prior_binding_observer"] = observe_prior
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
        if r0_observe:
            _need(len(oracle_facts) == int(work.oracle_b_selected and kind is not
                  execution.WorkerKind.K_CONTROL), "ORACLE_TIMING_COVERAGE")
            fact = oracle_facts[0] if oracle_facts else None
            telemetry = (0, 0, 0, ()) if fact is None else (
                fact.applicability_checks, fact.actual_checks, fact.wall_ns, fact.intervals)
            channel.result(json.dumps(telemetry + (r0_max_arm,), separators=(",", ":")).encode("ascii"),
                           tags=(b"T", b"U", b"V"))
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

    R0 uses complete conservative P/K/D standalone boundaries and three Oracle
    route boundaries. These per-worker totals alone omit coordinator persistence
    and cannot substitute for the complete directly observed route measurements.
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
    observation: object = None


@dataclass(frozen=True, slots=True)
class _R0Observation:
    worker_memory: int
    coordinator_memory: int
    combined_memory: int
    decision_wall: int
    arm_wall: int
    shadow_wall: int
    physical_inputs: int
    oracle: tuple
    resources_complete: bool
    cleanup_complete: bool
    watchdogs_complete: bool
    prior_binding_intervals: tuple = ()

    @property
    def prior_binding_wall_ns(self):
        return _interval_union_wall(self.prior_binding_intervals)

    def __post_init__(self):
        for value in (self.worker_memory, self.coordinator_memory, self.combined_memory,
                      self.decision_wall, self.arm_wall, self.shadow_wall, self.physical_inputs):
            _integer(value)
        for value in (self.resources_complete, self.cleanup_complete, self.watchdogs_complete):
            _need(type(value) is bool, "EXACT_COMPLETION_FLAG")
        _need(type(self.oracle) is tuple and len(self.oracle) == 4, "ORACLE_TELEMETRY")
        probes, calls, wall, intervals = self.oracle
        for value in (probes, calls, wall):
            _integer(value)
        _need(calls <= probes and type(intervals) is tuple and len(intervals) == probes,
              "ORACLE_TELEMETRY_COUNTS")
        previous = 0
        total = 0
        for interval in intervals:
            _need(type(interval) is tuple and len(interval) == 2, "ORACLE_TELEMETRY_INTERVAL")
            start, end = interval
            _integer(start)
            _integer(end)
            _need(previous <= start <= end, "ORACLE_TELEMETRY_ORDER")
            previous, total = end, total + end - start
        _need(total == wall, "ORACLE_TELEMETRY_WALL")
        _need(self.combined_memory >= max(self.worker_memory, self.coordinator_memory),
              "R0_MEMORY_ACCOUNTING")
        _need(type(self.prior_binding_intervals) is tuple, "PRIOR_BINDING_INTERVALS")
        previous = 0
        for interval in self.prior_binding_intervals:
            _need(type(interval) is tuple and len(interval) == 2, "PRIOR_BINDING_INTERVAL")
            start, end = interval
            _integer(start)
            _integer(end)
            _need(previous <= start <= end, "PRIOR_BINDING_INTERVAL_ORDER")
            previous = end


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
                         job_started_ns, launcher_started_ns, *, worker_target=None, r0_observe=False):
    """One disposable process. The private test target never changes the public plan."""
    started = time.monotonic_ns()
    counter_started = time.perf_counter_ns() if r0_observe else None
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    barrier = context.Event()
    _need(type(r0_observe) is bool and (not r0_observe or worker_target is None), "R0_PRODUCTION_WORKER_REQUIRED")
    args = (work, kind, first_bytes, envelope, child, barrier)
    process = context.Process(target=_worker_main if worker_target is None else worker_target,
                              args=args + (True,) if r0_observe else args)
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
    telemetry_size, telemetry, telemetry_wire = None, None, bytearray()
    max_worker = max_coordinator = max_combined = max_arm = 0
    max_decision = max_shadow = 0
    resources_complete = cleanup_complete = True
    prior_binding_intervals = []
    prior_bound = False
    prior_cleanup_started = None

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
        nonlocal first_sample, peak_sample, last_sample, max_worker, max_coordinator, max_combined
        nonlocal resources_complete
        try:
            worker = peak_memory()
            current, breached = ledger.sample(token, worker, _unit_id(work.position, kind),
                                              time.monotonic_ns() - started)
        except BaseException:
            resources_complete = False
            raise
        if r0_observe:
            max_worker = max(max_worker, worker)
            max_coordinator = max(max_coordinator, current.coordinator_bytes)
            max_combined = max(max_combined, current.combined_bytes)
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
            elif tag == b"B":
                _need(r0_observe and work.oracle_b_selected and first_bytes is not None
                      and kind is not execution.WorkerKind.PRIMARY and started_frame
                      and not prior_bound and not data and not counts and expected_size is None,
                      "PRIOR_BINDING_BOUNDARY")
                prior_binding_intervals.append((counter_started, time.perf_counter_ns()))
                prior_bound = True
            elif tag == b"E":
                _need(started_frame and expected_size is None, "MALFORMED_IPC")
                _need(not r0_observe or telemetry_size is None, "R0_ARM_AFTER_TELEMETRY")
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
            elif tag in (b"T", b"U", b"V"):
                _need(r0_observe and started_frame and current_arm is None
                      and expected_size is None and telemetry is None, "UNEXPECTED_R0_TELEMETRY")
                if tag == b"T":
                    _need(telemetry_size is None and data and data.isdigit(), "R0_TELEMETRY_HEADER")
                    expected_arms = ({"K_CONTROL"} if kind is execution.WorkerKind.K_CONTROL
                                     else {"CONTROL", "K_P0"})
                    _need(set(counts) == expected_arms, "R0_TELEMETRY_BEFORE_COMPLETE_ARMS")
                    telemetry_size = int(data)
                    _need(str(telemetry_size).encode("ascii") == data
                          and 0 < telemetry_size <= envelope.max_payload_bytes, "R0_TELEMETRY_CAP")
                elif tag == b"U":
                    _need(telemetry_size is not None and data
                          and len(telemetry_wire) + len(data) <= telemetry_size, "R0_TELEMETRY_CHUNK")
                    telemetry_wire.extend(data)
                else:
                    _need(not data and telemetry_size == len(telemetry_wire), "R0_TELEMETRY_LENGTH")
                    node = json.loads(telemetry_wire.decode("ascii"))
                    _need(type(node) is list and len(node) == 5 and type(node[3]) is list,
                          "R0_TELEMETRY_SHAPE")
                    intervals = tuple(tuple(pair) if type(pair) is list else pair for pair in node[3])
                    fact = execution.audit.OracleBTimingFact(execution._arm(work, records.Arm.K_P0,
                        repeat=kind is execution.WorkerKind.DETERMINISM),
                                                            *node[:3], intervals)
                    _need((work.oracle_b_selected and kind is not execution.WorkerKind.K_CONTROL)
                          or node[:4] == [0, 0, 0, []], "UNSELECTED_ORACLE_TIMING")
                    _integer(node[4])
                    _need(node[4] <= time.perf_counter_ns() - counter_started, "ARM_TIMING_CLOCK_BINDING")
                    max_arm = node[4]
                    _need(len(intervals) <= 2 * envelope.max_physical_inputs, "ORACLE_TIMING_COUNT_CAP")
                    _need(all(counter_started <= a <= b <= time.perf_counter_ns() for a, b in intervals),
                          "ORACLE_TIMING_CLOCK_BINDING")
                    telemetry = (fact.applicability_checks, fact.actual_checks, fact.wall_ns, fact.intervals)
                    telemetry_wire.clear()
            elif tag == b"H":
                _need(started_frame and expected_size is None and current_arm is None
                      and data and all(48 <= c <= 57 for c in data), "MALFORMED_IPC")
                _need(not r0_observe or telemetry is not None, "MISSING_R0_TELEMETRY")
                _need(not r0_observe or not work.oracle_b_selected or first_bytes is None
                      or prior_bound, "MISSING_PRIOR_BINDING_BOUNDARY")
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
                binding_started = time.perf_counter_ns() if r0_observe and first_bytes is not None else None
                candidate = execution.decode_bundle(bytes(wire))
                execution.revalidate_bundle(candidate, work, kind, max_payload_bytes=envelope.max_payload_bytes)
                _bind_prior_bundle(candidate, first_bytes, work, kind, envelope)
                if binding_started is not None:
                    prior_binding_intervals.append((binding_started, time.perf_counter_ns()))
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
                if r0_observe:
                    if work.oracle_b_selected and kind is not execution.WorkerKind.K_CONTROL:
                        prefix = "repeat_" if kind is execution.WorkerKind.DETERMINISM else ""
                        decisions = tuple(records.decode(value) for value in streams[prefix + "kp0_decisions"])
                        children = tuple(records.decode(value) for value in streams[prefix + "oracle_b_audits"])
                        # Every captured noninitial K decision reaches both applicability probes.
                        _need(telemetry[0] == 2 * sum(value.action_ordinal > 0 for value in decisions)
                              and telemetry[1] == sum(value.status is not records.AuditStatus.INCOMPLETE
                                                      for value in children), "ORACLE_TIMING_EVIDENCE_BINDING")
                    for name, values in candidate.streams:
                        if name.endswith("decision_spans") or name == "kcontrol_maintenance":
                            for encoded in values:
                                value = records.decode(encoded)
                                if type(value) is records.DecisionSpanRecord:
                                    max_decision = max(max_decision, value.duration_ns or 0)
                                else:
                                    timings = dict(value.timings)
                                    max_decision = max(max_decision, timings.get("v1_plan_position_ns") or 0)
                                    max_shadow = max(max_shadow, timings.get("shadow_ns") or 0)
                    for observed, cap, diagnosis, inclusive in (
                        (max_arm, envelope.max_arm_wall_ms, "ARM_TIMEOUT", True),
                        (max_decision, envelope.max_decision_wall_ms, "DECISION_TIMEOUT", True),
                        (max_shadow, envelope.shadow_timeout_ms, "SHADOW_TIMEOUT", False),
                    ):
                        if observed >= cap * 1_000_000 if inclusive else observed > cap * 1_000_000:
                            raise OperationalAbort(diagnosis)
                if time.monotonic_ns() - validation_started >= envelope.validation_wall_ms * 1_000_000:
                    raise OperationalAbort("VALIDATION_TIMEOUT")
                wire.clear()
                finished = True
                if r0_observe and prior_bound:
                    prior_cleanup_started = time.perf_counter_ns()
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
                    cleanup_complete = False
                    reason = reason or "JOB_CLOSE_INCOMPLETE"
            except BaseException:
                cleanup_complete = False
                reason = reason or "JOB_CLOSE_INCOMPLETE"
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
                reason = reason or "WORKER_REAP_INCOMPLETE"
                cleanup_complete = False
            if process.is_alive():
                cleanup_complete = False
                reason = "WORKER_REAP_INCOMPLETE"
        parent.close()
        child.close()
        if reader is not None:
            reader.join(timeout=1)
            if reader.is_alive():
                cleanup_complete = False
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
    if prior_cleanup_started is not None:
        # Solver work has completed before F. This directly timed tail contains
        # accepted result acknowledgement, prior transport retirement and all
        # worker/reader/Job cleanup without including the K solver interval.
        prior_binding_intervals.append((prior_cleanup_started, time.perf_counter_ns()))
    summary_reason = reason or ("AUDIT_FAIL" if status is records.AuditStatus.FAIL else
                                "AUDIT_INCOMPLETE" if status is records.AuditStatus.INCOMPLETE else "ADMITTED")
    observation = None if not r0_observe else _R0Observation(
        max_worker, max_coordinator, max_combined, max_decision, max_arm, max_shadow,
        max(counts.values(), default=0), telemetry or (0, 0, 0, ()),
        resources_complete and bool(samples), cleanup_complete,
        finished and telemetry is not None and reason not in ("DECISION_TIMEOUT", "ARM_TIMEOUT", "CASE_TIMEOUT",
            "JOB_TIMEOUT", "LAUNCHER_TIMEOUT", "SHADOW_TIMEOUT", "WATCHDOG_INCOMPLETE"),
        tuple(prior_binding_intervals))
    return _OperationResult(UnitReceipt(work.position, kind, status, summary_reason, elapsed,
                                       exit_code), bundle, samples, observation)


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
        return len(store._key_bytes(key)) + len(data) + 2

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


class R0Component(Enum):
    PRIMARY = "P"
    K_CONTROL = "K"
    ORACLE_B = "O"
    DETERMINISM = "D"
    ORACLE_K_BIND = "O_K_BIND"
    ORACLE_D_REPEAT = "O_D_REPEAT"


@dataclass(frozen=True, slots=True)
class R0Work:
    """Explicit operational-only identity, never an accepted E2 BoardWork plan.

    The later launcher authenticates the first-64 selection. This boundary only
    executes supplied identities, without generating a corpus or selecting N.
    """

    position: int
    board: records.BoardIdentity
    protocol_seed: bytes
    run_id: str
    runtime: records.RuntimeIdentity | None = None

    def __post_init__(self):
        execution.BoardWork(self.position, self.board, self.protocol_seed, self.run_id,
                            False, False, False, self.runtime)
        _need(self.run_id.startswith("R0-"), "R0_RUN_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class R0UnitMeasurement:
    """Strict target attribution; setup totals are containment diagnostics only.

    Reference bytes are only rank-0 control_maintenance from prerequisite
    PRIMARY archives. Supporting bytes are outside all bundle-stream families.
    """
    work: R0Work
    component: R0Component
    status: records.AuditStatus
    reasons: tuple
    wall_ns: int
    durable_bytes: int
    setup_wall_ns: int
    setup_bytes: int
    max_case_wall_ns: int
    observations: tuple
    reference_bytes: int = 0
    supporting_bytes: int = 0
    max_payload_bytes: int = 0

    def __post_init__(self):
        _need(type(self.work) is R0Work and type(self.component) is R0Component
              and type(self.status) is records.AuditStatus, "R0_MEASUREMENT_IDENTITY")
        R0Work.__post_init__(self.work)
        _need(type(self.reasons) is tuple and all(type(s) is str and s
              and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in s) for s in self.reasons),
              "R0_STATIC_REASONS")
        for value in (self.wall_ns, self.durable_bytes, self.setup_wall_ns, self.setup_bytes,
                      self.max_case_wall_ns, self.reference_bytes, self.supporting_bytes,
                      self.max_payload_bytes):
            _integer(value)
        _need(type(self.observations) is tuple, "R0_OBSERVATIONS_TUPLE")
        for item in self.observations:
            _need(type(item) is _R0Observation, "R0_OBSERVATION_TYPE")
            _R0Observation.__post_init__(item)


@dataclass(frozen=True, slots=True)
class R0ComponentMeasurement:
    """Outcome-blind component facts, not admission or a readiness verdict.

    P/K/D are directly timed complete standalone waves. O primary and D-repeat
    use complete affected target phases, through coordinator-equivalent admission,
    encoding, persistence/readback and cleanup. Their baseline work is conservative
    duplicate wall inclusion. O K-bind unions only directly observed prior
    preparation/transport/binding/validation phases, excluding the K solver.
    All six routes retain every prerequisite observation for containment.
    """

    component: R0Component
    concurrency: int
    units: tuple
    wall_ns: int
    coordinator_memory_bytes: int
    complete_wall_ns: int
    combined_memory_bytes: int

    def __post_init__(self):
        _need(type(self.component) is R0Component and type(self.concurrency) is int
              and self.concurrency in (1, 2, 4), "R0_COMPONENT_CONCURRENCY")
        _need(type(self.units) is tuple and bool(self.units), "R0_UNIT_COVERAGE")
        for unit in self.units:
            _need(type(unit) is R0UnitMeasurement and unit.component is self.component,
                  "R0_UNIT_COMPONENT")
            R0UnitMeasurement.__post_init__(unit)
        _need(tuple(unit.work.position for unit in self.units) == tuple(range(len(self.units)))
              and len({unit.work.board.game_index for unit in self.units}) == len(self.units),
              "R0_MEASUREMENT_COVERAGE")
        for value in (self.wall_ns, self.coordinator_memory_bytes, self.complete_wall_ns,
                      self.combined_memory_bytes):
            _integer(value)
        _need(self.complete_wall_ns >= self.wall_ns, "R0_WALL_ACCOUNTING")
        _need(self.combined_memory_bytes >= self.coordinator_memory_bytes, "R0_MEMORY_ACCOUNTING")


def _r0_work(work, component):
    return execution.BoardWork(work.position, work.board, work.protocol_seed, work.run_id,
        component in (R0Component.ORACLE_B, R0Component.ORACLE_K_BIND, R0Component.ORACLE_D_REPEAT),
        component in (R0Component.DETERMINISM, R0Component.ORACLE_D_REPEAT),
        component in (R0Component.K_CONTROL, R0Component.ORACLE_K_BIND), work.runtime)


def _bundle_stream_bytes(operation, names=None):
    """Exact accepted store key/TAB/record/LF framing, never diagnostic keys."""
    if operation.bundle is None:
        return 0
    return sum(_EvidenceSink._size((operation.receipt.position, _kind_rank(operation.receipt.kind), index), data)
               for name, values in operation.bundle.streams if names is None or name in names
               for index, data in enumerate(values))


def _r0_attributable_bytes(operation, component):
    if component is R0Component.ORACLE_K_BIND:
        return 0  # Wall-only: the K target emits no Oracle audit family.
    if component in (R0Component.ORACLE_B, R0Component.ORACLE_D_REPEAT):
        return _bundle_stream_bytes(operation, {"oracle_b_audits" if component is
            R0Component.ORACLE_B else "repeat_oracle_b_audits"})
    excluded = {"oracle_b_audits", "repeat_oracle_b_audits"}
    if component is R0Component.PRIMARY:
        excluded.add("control_maintenance")
    return _bundle_stream_bytes(operation, set(execution.STREAM_NAMES) - excluded)


def _interval_union_wall(intervals):
    """Union directly observed wall intervals, never subtraction of whole runs."""
    total, end = 0, None
    for start, stop in sorted(intervals):
        total += stop - start if end is None or start >= end else max(0, stop - end)
        end = stop if end is None else max(end, stop)
    return total


class _R0MemoryMonitor:
    """Keep the accepted shared ledger sampled during setup and persistence too."""

    def __init__(self, ledger, cancel, envelope):
        self.ledger, self.cancel, self.envelope = ledger, cancel, envelope
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.coordinator = self.combined = 0
        self.reason = None
        self.thread = threading.Thread(target=self.run, daemon=True, name="program-k-r0-memory")

    def sample(self):
        with self.lock:
            try:
                value, breached = self.ledger.sample("r0-coordinator", 0, "R0", 0)
                self.coordinator = max(self.coordinator, value.coordinator_bytes)
                self.combined = max(self.combined, value.combined_bytes)
                if breached:
                    self.reason = self.reason or "MEMORY_CAP"
            except Exception:
                self.reason = self.reason or "MEMORY_MONITOR_INCOMPLETE"
            if self.reason is not None:
                self.cancel.set()

    def check(self):
        self.sample()
        if self.reason is not None:
            raise OperationalAbort(self.reason)

    def run(self):
        while not self.stop.wait(self.envelope.monitor_interval_ms / 1000):
            self.sample()

    def __enter__(self):
        self.check()
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=1)
        self.ledger.remove("r0-coordinator")
        if self.thread.is_alive():
            self.cancel.set()
            raise OperationalAbort("MEMORY_MONITOR_REAP_INCOMPLETE")
        if exc[0] is None and self.reason is not None:
            raise OperationalAbort(self.reason)


def _persist_r0(root, operation, envelope, *, oracle_only=False, byte_budget=None):
    """Existing I2 records only, exclusive files, strict streaming readback."""
    if byte_budget is not None:
        _integer(byte_budget)
        if byte_budget <= 8192:
            raise OperationalAbort("ARCHIVE_CAP")
        # Tighten this archive's allowance to the remaining whole-run budget.
        # Execution/watchdog caps are unchanged; this copy only owns persistence.
        envelope = replace(envelope, archive_cap_bytes=min(envelope.archive_cap_bytes, byte_budget),
                           max_payload_bytes=min(envelope.max_payload_bytes, byte_budget))
    root.mkdir()
    started = time.monotonic_ns()

    def publication_check():
        if time.monotonic_ns() - started >= envelope.publication_wall_ms * 1_000_000:
            raise OperationalAbort("PUBLICATION_TIMEOUT")

    if not oracle_only:
        sink = _EvidenceSink(root, envelope, 1)
        try:
            receipt = sink.admit(operation)
            seals = sink.seal()
            publication_check()
            readback_streams(root, seals, envelope)
            return receipt, sink.byte_length
        finally:
            sink.close()
    writers = []
    try:
        seals = []
        streams = {} if operation.bundle is None else dict(operation.bundle.streams)
        # Whole-worker resource samples belong to the prerequisite archive;
        # their persistence is not incremental Oracle maintenance work.
        for name in (("repeat_oracle_b_audits",) if operation.receipt.kind is
                     execution.WorkerKind.DETERMINISM else ("oracle_b_audits",)):
            writer = store.StreamWriter(root, name)
            writers.append(writer)
            values = tuple(records.decode(data) for data in streams.get(name, ()))
            for index, value in enumerate(values):
                key = (operation.receipt.position, _kind_rank(operation.receipt.kind), index)
                added = _EvidenceSink._size(key, records.encode(value))
                if sum(item.byte_length for item in writers) + added > envelope.archive_cap_bytes:
                    raise OperationalAbort("ARCHIVE_CAP")
                writer.append(key, value)
                publication_check()
            writer.checkpoint()
            seals.append(writer.seal())
            publication_check()
        deadline = time.monotonic_ns() + envelope.readback_wall_ms * 1_000_000

        def visit(*_):
            if time.monotonic_ns() >= deadline:
                raise OperationalAbort("READBACK_TIMEOUT")

        for writer, seal in zip(writers, seals):
            visit()
            observed = store.scan_stream(root, writer.stream_name, visit=visit)
            visit()
            _need(observed == seal, "READBACK_INTEGRITY_FAIL")
        return operation.receipt, sum(item.byte_length for item in writers)
    finally:
        for writer in writers:
            writer.close()


def measure_r0_component(plan, component, root, envelope, *, cancel=None, progress=None):
    """Public R0-only measurement, using the SAME production process supervisor.

    No private worker target, solver replay codec, retry, selector, bootstrap or
    readiness decision exists here. A later launcher supplies authenticated R0 identities
    and a new ignored root. Raw evidence is sealed beneath each unit; the return
    and optional progress observer expose only immutable operational facts.
    At most c primary references are retained. Each K/D setup wave is completed
    before the corresponding target wave starts. Exceptions preserve the root.
    """
    envelope = _envelope(envelope)
    _need(type(component) is R0Component and type(plan) is tuple and bool(plan), "R0_PLAN_REQUIRED")
    for work in plan:
        _need(type(work) is R0Work, "R0_WORK_REQUIRED")
        R0Work.__post_init__(work)
    first = plan[0]
    _need(tuple(work.position for work in plan) == tuple(range(len(plan)))
          and len({work.board.game_index for work in plan}) == len(plan)
          and all((work.protocol_seed, work.run_id, work.runtime) ==
                  (first.protocol_seed, first.run_id, first.runtime) for work in plan), "R0_PLAN_IDENTITY")
    _need(progress is None or callable(progress), "R0_PROGRESS_OBSERVER")
    _need(cancel is None or (callable(getattr(cancel, "is_set", None))
                            and callable(getattr(cancel, "set", None))), "CANCELLATION_TOKEN")
    cancel = threading.Event() if cancel is None else cancel
    root = Path(root)
    root.mkdir()  # Exclusive: never overwrite, retry, remove, or reuse a failed root.
    complete_started = time.perf_counter_ns()
    started = time.monotonic_ns()
    ledger = _MemoryLedger(envelope)
    units, measured_wall, all_intervals = [], 0, []
    archive_bytes = 0
    target_kind = {R0Component.PRIMARY: execution.WorkerKind.PRIMARY,
                   R0Component.ORACLE_B: execution.WorkerKind.PRIMARY,
                   R0Component.ORACLE_K_BIND: execution.WorkerKind.K_CONTROL,
                   R0Component.ORACLE_D_REPEAT: execution.WorkerKind.DETERMINISM,
                   R0Component.K_CONTROL: execution.WorkerKind.K_CONTROL,
                   R0Component.DETERMINISM: execution.WorkerKind.DETERMINISM}[component]
    needs_setup = component in (R0Component.K_CONTROL, R0Component.DETERMINISM,
                               R0Component.ORACLE_K_BIND, R0Component.ORACLE_D_REPEAT)

    def checkpoint():
        monitor.check()
        now = time.monotonic_ns()
        if archive_bytes > envelope.archive_cap_bytes:
            cancel.set()
            raise OperationalAbort("ARCHIVE_CAP")
        if now - started >= min(envelope.max_job_wall_ms, envelope.max_launcher_wall_ms) * 1_000_000:
            cancel.set()
            raise OperationalAbort("JOB_TIMEOUT" if envelope.max_job_wall_ms <= envelope.max_launcher_wall_ms
                                   else "LAUNCHER_TIMEOUT")

    def supervise(work, kind, prior):
        return _supervise_operation(work, kind, prior, envelope, ledger, cancel, started, started,
                                    r0_observe=True)

    def admit(operation, work):
        # Reproduce the Actual-E2 coordinator's second parent revalidation.
        validation_started = time.monotonic_ns()
        _need(operation.receipt.position == work.position, "R0_COORDINATOR_POSITION")
        if operation.bundle is not None:
            execution.revalidate_bundle(operation.bundle, work, operation.receipt.kind,
                                        max_payload_bytes=envelope.max_payload_bytes)
        if time.monotonic_ns() - validation_started >= envelope.validation_wall_ms * 1_000_000:
            raise OperationalAbort("VALIDATION_TIMEOUT")

    orchestration_started = time.perf_counter_ns()
    with _R0MemoryMonitor(ledger, cancel, envelope) as monitor, ThreadPoolExecutor(
            max_workers=envelope.concurrency, thread_name_prefix="program-k-r0") as pool:
        orchestration_interval = (orchestration_started, time.perf_counter_ns())
        if component is R0Component.ORACLE_K_BIND:
            all_intervals.append(orchestration_interval)
        else:
            measured_wall += orchestration_interval[1] - orchestration_interval[0]
        for offset in range(0, len(plan), envelope.concurrency):
            checkpoint()
            batch = plan[offset:offset + envelope.concurrency]
            standalone_started = time.perf_counter_ns()
            works = tuple(_r0_work(work, component) for work in batch)
            roots = tuple(root / str(work.position) for work in batch)
            for directory in roots:
                directory.mkdir()
            setups, setup_bytes = [None] * len(batch), [0] * len(batch)
            setup_supporting, reference_bytes = [0] * len(batch), [0] * len(batch)
            setup_payloads = [0] * len(batch)
            if needs_setup:
                futures = tuple(pool.submit(supervise, work, execution.WorkerKind.PRIMARY, None) for work in works)
                setups = [future.result() for future in futures]
                for index, operation in enumerate(setups):
                    admit(operation, works[index])
                    receipt, size = _persist_r0(roots[index] / "setup", operation, envelope,
                                               byte_budget=envelope.archive_cap_bytes - archive_bytes)
                    setups[index] = replace(operation, receipt=receipt)
                    setup_bytes[index] = size
                    persisted = receipt.reason != "ARCHIVE_CAP"
                    setup_supporting[index] = size - (_bundle_stream_bytes(operation) if persisted else 0)
                    _need(setup_supporting[index] >= 0, "R0_BYTE_OWNERSHIP")
                    reference_bytes[index] = (_bundle_stream_bytes(operation, {"control_maintenance"})
                                              if persisted else 0)
                    archive_bytes += size
                checkpoint()
            # K/D include their complete setup; Oracle downstream routes begin
            # after setup, but include directly timed prior encoding/preparation.
            target_started = time.perf_counter_ns()
            encoding_started = time.perf_counter_ns()
            priors = tuple(None if setup is None or setup.bundle is None or
                           setup.receipt.status is not records.AuditStatus.PASS else
                           execution.encode_bundle(setup.bundle) for setup in setups)
            encoding_interval = (encoding_started, time.perf_counter_ns())
            setup_payloads = [0 if prior is None else len(prior) for prior in priors]
            if component is R0Component.ORACLE_K_BIND:
                all_intervals.append(encoding_interval)
            futures = []
            for index, work in enumerate(works):
                setup = setups[index]
                if setup is not None and (setup.receipt.status is not records.AuditStatus.PASS or setup.bundle is None):
                    futures.append(None)
                else:
                    futures.append(pool.submit(supervise, work, target_kind, priors[index]))
            outcomes = [future.result() if future is not None else
                        _missing(work, target_kind, "PRIMARY_PREMISES_MISSING")
                        for work, future in zip(works, futures)]
            for index, operation in enumerate(outcomes):
                setup = setups[index]
                admission_started = time.perf_counter_ns()
                admit(operation, works[index])
                admission_interval = (admission_started, time.perf_counter_ns())
                if component is R0Component.ORACLE_K_BIND:
                    all_intervals.append(admission_interval)
                # Actual _workflow encodes every admitted primary as a prior,
                # including a primary without downstream targets. Keep that
                # phase inside P/O-primary calibration boundaries as well.
                payload = None if operation.bundle is None else execution.encode_bundle(operation.bundle)
                receipt, size = _persist_r0(roots[index] / "target", operation, envelope,
                                           byte_budget=envelope.archive_cap_bytes - archive_bytes)
                archive_bytes += size
                observation = operation.observation
                if component is R0Component.ORACLE_K_BIND and observation is not None:
                    all_intervals.extend(observation.prior_binding_intervals)
                related = tuple(item for item in (setup, operation) if item is not None)
                status = (records.AuditStatus.FAIL if any(item.receipt.status is records.AuditStatus.FAIL
                          for item in related) or receipt.status is records.AuditStatus.FAIL else
                          records.AuditStatus.INCOMPLETE if receipt.status is not records.AuditStatus.PASS
                          or any(item.receipt.status is not records.AuditStatus.PASS for item in related) else
                          records.AuditStatus.PASS)
                observations = tuple(item.observation for item in related if item.observation is not None)
                if status is records.AuditStatus.PASS and (len(observations) != len(related) or not all(
                    item.resources_complete and item.cleanup_complete and item.watchdogs_complete
                    for item in observations)):
                    status = records.AuditStatus.INCOMPLETE
                if component is R0Component.ORACLE_K_BIND and status is records.AuditStatus.PASS and (
                        observation is None or not observation.prior_binding_intervals):
                    status = records.AuditStatus.INCOMPLETE
                reasons = tuple(dict.fromkeys(item.receipt.reason for item in related
                                              if item.receipt.reason != "ADMITTED"))
                if receipt.reason != "ADMITTED" and receipt.reason not in reasons:
                    reasons += (receipt.reason,)
                if status is not records.AuditStatus.PASS and not reasons:
                    reasons = ("R0_OBSERVATION_INCOMPLETE",)
                wall = (0 if observation is None else observation.prior_binding_wall_ns) + (
                    encoding_interval[1] - encoding_interval[0] + admission_interval[1] - admission_interval[0]) if (
                    component is R0Component.ORACLE_K_BIND) else time.perf_counter_ns() - (
                    standalone_started if component in (R0Component.PRIMARY, R0Component.K_CONTROL,
                                                        R0Component.DETERMINISM) else target_started)
                persisted = receipt.reason != "ARCHIVE_CAP"
                attributable = _r0_attributable_bytes(operation, component) if persisted else 0
                supporting = setup_supporting[index] + size - (_bundle_stream_bytes(operation) if persisted else 0)
                _need(supporting >= 0, "R0_BYTE_OWNERSHIP")
                unit = R0UnitMeasurement(batch[index], component, status, reasons, wall, attributable,
                    0 if setup is None else setup.receipt.elapsed_ns, setup_bytes[index],
                    max(item.receipt.elapsed_ns for item in related), observations,
                    reference_bytes[index], supporting, max(setup_payloads[index],
                    0 if payload is None else len(payload)))
                units.append(unit)
                if progress is not None:
                    progress(unit, len(units), len(plan))
                if status is not records.AuditStatus.PASS:
                    cancel.set()
            checkpoint()
            if component is not R0Component.ORACLE_K_BIND:
                measured_wall += time.perf_counter_ns() - (standalone_started if component in (
                    R0Component.PRIMARY, R0Component.K_CONTROL, R0Component.DETERMINISM) else target_started)
        cleanup_started = time.perf_counter_ns()
    cleanup_interval = (cleanup_started, time.perf_counter_ns())
    if component is R0Component.ORACLE_K_BIND:
        all_intervals.append(cleanup_interval)
    else:
        measured_wall += cleanup_interval[1] - cleanup_interval[0]
    measured_wall += _interval_union_wall(all_intervals)
    observations = tuple(item for unit in units for item in unit.observations)
    coordinator_peak = max((item.coordinator_memory for item in observations), default=0)
    combined_peak = max((item.combined_memory for item in observations), default=0)
    complete_wall = time.perf_counter_ns() - complete_started
    if component in (R0Component.PRIMARY, R0Component.K_CONTROL, R0Component.DETERMINISM,
                     R0Component.ORACLE_B):
        # These routes have no excluded prerequisite. The entire launcher
        # boundary conservatively includes all scheduling/checkpoint overhead.
        measured_wall = complete_wall
    return R0ComponentMeasurement(component, envelope.concurrency, tuple(units), measured_wall,
                                   max(monitor.coordinator, coordinator_peak),
                                   complete_wall, max(monitor.combined, combined_peak))


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
