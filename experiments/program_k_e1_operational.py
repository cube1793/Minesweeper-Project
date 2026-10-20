"""E1 single-operation containment and descriptive resource evidence.

This module confers no execution authorization and performs no persistence.
The Windows Job applies to the worker tree; coordinator private committed bytes
are sampled separately. Stack samples are containment observations, not exact
decision timings. Archived runner spans retain their original boundaries.
"""

from dataclasses import MISSING, asdict, dataclass, fields, is_dataclass, replace
import hashlib
import inspect
import json
import multiprocessing
from pathlib import Path
import pickle
from queue import Empty, Full, Queue
import sys
import threading
import time

from core_engine import MinesweeperEngine
from experiments import program_k_capability as _capability
from experiments import program_k_e1_audit as _audit
from experiments import program_k_e1_execution as _execution
from experiments import program_k_e1_harness as _e1
from experiments import program_k_e1_suite as _suite
from experiments import program_k_harness as _harness
from experiments import program_k_policy as _policy
from experiments import program_k_runner as _runner
import stage3_planner as _planner
import stage3_runner as _v1


MONITORING_POLICY = "WINDOWS_JOB_MEMORY_AND_STACK_SAMPLING_WATCHDOG_V1"
MONITORING_CONTEXT = (
    "SUPERVISED_STACK_SAMPLING_V1; no line/profile tracer installed; "
    "runner spans measured in supervised execution context"
)
SAMPLING_MEASUREMENT = (
    "Main-worker-thread fixed decision code stack sampled at monitor_interval_ms; "
    "elapsed time begins at first observed frame, resets before physical input, "
    "and may miss spans between samples. Thread scheduling/GIL delays can delay "
    "samples; parent case/job deadlines remain independent. Runner DecisionTimings "
    "are authoritative duration spans; shadow threads are excluded."
)
ACCEPTED_AUDIT_SOURCE_DIGEST = "47ceca0595cacf08f70bd14911a805c5d0358fa3e60e695349a66689b9d994b1"
ACCEPTED_SUITE_SOURCE_DIGEST = "afbc71a19af9d31944ed9489420b5eb505871ba195b4888bac185301b3d8c328"
OPERATIONAL_SOURCE_PATHS = (
    "experiments/program_k_e1_evaluator.py",
    "experiments/program_k_e1_operational.py",
)
_AUTHORITY_FIELDS = _execution._AUTHORITY_FIELDS
_CHUNK_SIZE = 65536


class E1OperationalError(ValueError):
    """An operational identity or evidence admission failed."""


class E1OperationalAbort(RuntimeError):
    """Containment abort; never an ordinary game outcome."""


def _need(condition, detail):
    if not condition:
        raise E1OperationalError(detail)


def _checked(value, cls):
    _need(type(value) is cls, "Expected exact " + cls.__name__ + ".")
    return replace(value)


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Invalid SHA-256 digest.")


def _integer(value, name, *, positive=False):
    _need(type(value) is int and value >= (1 if positive else 0),
          name + " must be an exact " + ("positive" if positive else "nonnegative") + " integer.")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True, slots=True)
class E1OperationalSourceFile:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(self.path in OPERATIONAL_SOURCE_PATHS and type(self.path) is str,
              "Only the evaluator and operational modules extend this identity.")
        _sha(self.sha256)
        _integer(self.size_bytes, "Source byte size", positive=True)


@dataclass(frozen=True, slots=True)
class E1OperationalSourceIdentity:
    plan_source_identity: _e1.E1SourceIdentity
    execution_source_identity: _execution.E1ExecutionSourceIdentity
    audit_source_identity: _audit.E1AuditSourceIdentity
    suite_source_identity: _suite.E1SuiteSourceIdentity
    files: tuple[E1OperationalSourceFile, ...]
    spec_sha256: str
    protocol_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        plan = _checked(self.plan_source_identity, _e1.E1SourceIdentity)
        execution = _checked(self.execution_source_identity, _execution.E1ExecutionSourceIdentity)
        audit = _checked(self.audit_source_identity, _audit.E1AuditSourceIdentity)
        suite = _checked(self.suite_source_identity, _suite.E1SuiteSourceIdentity)
        _need(execution.plan_source_digest == plan.digest
              and audit.execution_source_digest == execution.digest
              and suite.audit_source_digest == audit.digest
              and audit.digest == ACCEPTED_AUDIT_SOURCE_DIGEST
              and suite.digest == ACCEPTED_SUITE_SOURCE_DIGEST,
              "Accepted Slice-1 through Slice-4 source chain differs.")
        _need(type(self.files) is tuple and len(self.files) == 2
              and tuple(item.path for item in self.files) == OPERATIONAL_SOURCE_PATHS,
              "Operational file identity catalog differs.")
        for item in self.files:
            _checked(item, E1OperationalSourceFile)
        _e1._frozen_identities(self)
        _need(all(getattr(source, name) == getattr(self, name)
                  for source in (plan, execution, audit, suite) for name in _AUTHORITY_FIELDS),
              "Frozen source authority chain differs.")

    @property
    def digest(self):
        _checked(self, E1OperationalSourceIdentity)
        return hashlib.sha256(_json(asdict(self))).hexdigest()

    @property
    def evaluator_file(self):
        return self.files[0]

    @property
    def operational_file(self):
        return self.files[1]


def _capture_operational_source_identity(plan, root):
    """Prospective source capture; never materializes a case or invents an archive."""
    plan = _checked(plan, _e1.E1Plan)
    _need(plan.runtime == _e1.capture_runtime_identity(), "Plan runtime/executable identity differs.")
    execution = _execution.capture_execution_source_identity(plan)
    root = Path(root)
    authority = tuple(getattr(plan.prerequisite, name) for name in _AUTHORITY_FIELDS)
    audit_raw = (root / _audit.AUDIT_SOURCE_PATH).read_bytes()
    audit = _audit.E1AuditSourceIdentity(
        execution.digest, _audit.E1AuditSourceFile(
            _audit.AUDIT_SOURCE_PATH, hashlib.sha256(audit_raw).hexdigest(), len(audit_raw)),
        *authority)
    suite_raw = (root / _suite.SUITE_SOURCE_PATH).read_bytes()
    suite = _suite.E1SuiteSourceIdentity(
        audit.digest, _suite.E1SuiteSourceFile(
            _suite.SUITE_SOURCE_PATH, hashlib.sha256(suite_raw).hexdigest(), len(suite_raw)),
        *authority)
    identities = []
    for path in OPERATIONAL_SOURCE_PATHS:
        raw = (root / path).read_bytes()
        identities.append(E1OperationalSourceFile(path, hashlib.sha256(raw).hexdigest(), len(raw)))
    return E1OperationalSourceIdentity(
        plan.source_identity, execution, audit, suite, tuple(identities), *authority)


def capture_operational_source_identity(plan):
    return _capture_operational_source_identity(plan, Path(__file__).resolve().parents[1])


def require_operating_envelope(envelope):
    """Admit the existing numeric contract and this runtime's E1 monitoring context."""
    envelope = _harness.require_envelope(envelope)
    runtime = _e1.capture_runtime_identity()
    _need((envelope.runtime_identity, envelope.machine_identity, envelope.python_identity)
          == (runtime.platform, runtime.node, runtime.python_version),
          "Operating envelope runtime/machine/Python identity differs.")
    _need(envelope.monitoring_policy == MONITORING_POLICY,
          "An explicit E1 stack-sampling monitoring policy is required.")
    return envelope


@dataclass(frozen=True, slots=True)
class E1MonitorEvent:
    sequence: int
    event: str
    elapsed_ns: int
    physical_inputs: int
    detail: str | None = None

    def __post_init__(self):
        _need(type(self.event) is str and self.event in (
            "JOB_ATTACHED", "STARTED", "BEFORE_INPUT", "RESULT_STARTED",
            "FINISHED", "WORKER_ABORT", "SYSTEM_DECISION_TIMEOUT"),
              "Unknown E1 monitor event.")
        for name in ("sequence", "elapsed_ns", "physical_inputs"):
            _integer(getattr(self, name), name)
        _need(self.detail is None or type(self.detail) is str, "Monitor detail must be text.")


@dataclass(frozen=True, slots=True)
class E1OperationReceipt:
    """Canonical result bytes plus a conservative receipt/event byte charge.

    The receipt charge uses its normalized in-memory JSON shape plus 256 bytes
    for the budget counters' encoded lengths. Transfer admission also reserves
    conservative header space and charges every event. Wire bytes are separately
    capped. These are containment accounting, not a future durable codec size.
    """
    operation_kind: str
    operation_id: str
    schedule_index: int
    case_id: str
    repetition: int
    variant: str
    operational_source_digest: str
    envelope_digest: str
    status: str
    reason: str | None
    events: tuple[E1MonitorEvent, ...]
    elapsed_ns: int
    physical_inputs: int
    result_digest: str | None
    result_size_bytes: int
    exit_code: int | None
    memory_evidence: _harness.MemoryEvidence | None
    monitoring_policy: str
    monitoring_context: str
    monitor_interval_ms: int
    archive_used_before_bytes: int
    archive_result_bytes: int
    archive_used_after_bytes: int
    sampling_measurement: str = SAMPLING_MEASUREMENT
    envelope: _harness.OperatingEnvelope | None = None
    archive_receipt_bytes: int = 0

    def __post_init__(self):
        _need(type(self.operation_kind) is str
              and self.operation_kind in ("SCHEDULED_RUN", "POST_HOC_EVALUATOR"),
              "Only the two E1 operation kinds are admitted.")
        _integer(self.schedule_index, "schedule_index")
        _integer(self.repetition, "repetition", positive=True)
        _need(type(self.case_id) is str and type(self.variant) is str,
              "Receipt case/variant must be exact strings.")
        _need(self.schedule_index < 54, "Schedule index is outside the fixed family.")
        entry = _e1.build_schedule()[self.schedule_index]
        _need((self.case_id, self.repetition, self.variant)
              == (entry.case_id, entry.repetition, entry.variant), "Receipt schedule identity differs.")
        prefix = f"{self.operation_kind}:{self.schedule_index:02d}"
        _need(type(self.operation_id) is str and (
            self.operation_id == prefix if self.operation_kind == "SCHEDULED_RUN"
            else self.operation_id.startswith(prefix + ":") and bool(self.operation_id[len(prefix) + 1:].strip())),
              "Operation identifier differs.")
        _sha(self.operational_source_digest)
        _sha(self.envelope_digest)
        envelope = require_operating_envelope(self.envelope)
        _need(self.envelope_digest == _harness.content_digest(envelope),
              "Receipt envelope content digest differs.")
        _need(type(self.status) is str and self.status in ("COMPLETE", "INCOMPLETE")
              and (self.reason is None if self.status == "COMPLETE"
                   else type(self.reason) is str and bool(self.reason)), "Invalid lifecycle status/reason.")
        _need(all(type(value) is str for value in
                  (self.monitoring_policy, self.monitoring_context, self.sampling_measurement))
              and self.monitoring_policy == MONITORING_POLICY
              and self.monitoring_context == MONITORING_CONTEXT
              and self.sampling_measurement == SAMPLING_MEASUREMENT, "Monitoring context differs.")
        _integer(self.monitor_interval_ms, "monitor_interval_ms", positive=True)
        _need(self.monitor_interval_ms == envelope.monitor_interval_ms,
              "Sampling interval differs from the declared envelope.")
        for name in ("elapsed_ns", "physical_inputs", "result_size_bytes",
                     "archive_used_before_bytes", "archive_result_bytes", "archive_used_after_bytes",
                     "archive_receipt_bytes"):
            _integer(getattr(self, name), name)
        _need(self.archive_result_bytes == self.result_size_bytes
              and self.archive_used_after_bytes == (
                  self.archive_used_before_bytes + self.archive_result_bytes + self.archive_receipt_bytes)
              and self.archive_receipt_bytes == _receipt_archive_charge(self),
              "Archive budget arithmetic differs.")
        _need(self.exit_code is None or type(self.exit_code) is int, "Invalid exit code.")
        _need(type(self.events) is tuple, "Monitor events must be immutable.")
        count, elapsed = 0, 0
        for index, event in enumerate(self.events):
            _checked(event, E1MonitorEvent)
            count += event.event == "BEFORE_INPUT"
            _need(event.sequence == index and elapsed <= event.elapsed_ns <= self.elapsed_ns
                  and event.physical_inputs == count, "Monitor event chronology/input count differs.")
            elapsed = event.elapsed_ns
        _need(count == self.physical_inputs, "Final input count differs.")
        if self.operation_kind == "POST_HOC_EVALUATOR":
            _need(self.variant == "K-P0" and self.physical_inputs == 0,
                  "Evaluator cannot perform Engine inputs.")
        if self.result_digest is not None:
            _sha(self.result_digest)
        if self.memory_evidence is not None:
            _checked(self.memory_evidence, _harness.MemoryEvidence)
            _need(self.memory_evidence.memory_cap_bytes == envelope.memory_cap_bytes,
                  "Memory evidence cap differs from the declared envelope.")
        if self.status == "COMPLETE":
            memory = self.memory_evidence
            _need(self.exit_code == 0 and self.result_digest is not None
                  and self.result_size_bytes > 0 and memory is not None
                  and memory.peak_worker_tree_bytes <= memory.worker_budget_bytes
                  and memory.peak_combined_bytes <= memory.memory_cap_bytes
                  and len(self.events) >= 3 and self.events[0].event == "JOB_ATTACHED"
                  and self.events[1].event == "STARTED" and self.events[-1].event == "FINISHED",
                  "Lifecycle completion requires clean exit and complete containment evidence.")
            _need(self.elapsed_ns < envelope.max_case_wall_ms * 1000000
                  and self.physical_inputs <= envelope.max_physical_inputs_per_case
                  and self.archive_used_after_bytes <= envelope.archive_cap_bytes,
                  "Completed operation exceeds its declared containment envelope.")


def _plain(value):
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if type(value) is dict:
        return {key: _plain(item) for key, item in value.items()}
    if type(value) in (tuple, list):
        return [_plain(item) for item in value]
    return value


def _receipt_archive_charge(receipt):
    values = _plain(receipt)
    values["archive_receipt_bytes"] = 0
    values["archive_used_after_bytes"] = values["archive_used_before_bytes"] + values["archive_result_bytes"]
    return len(_json(values)) + 256


def _make_receipt(**values):
    """Construct a new receipt's byte accounting; never repair an admitted one."""
    values = dict(values)
    for field in fields(E1OperationReceipt):
        if field.name not in values and field.default is not MISSING:
            values[field.name] = field.default
    values["archive_receipt_bytes"] = 0
    values["archive_used_after_bytes"] = values["archive_used_before_bytes"] + values["archive_result_bytes"]
    values["archive_receipt_bytes"] = _receipt_archive_charge(values)
    values["archive_used_after_bytes"] += values["archive_receipt_bytes"]
    return E1OperationReceipt(**values)


@dataclass(frozen=True, slots=True)
class E1OperationResult:
    receipt: E1OperationReceipt
    archive: _execution.E1ScheduledRunArchive | None = None
    audit: _audit.E1RunAudit | None = None
    evaluation: object | None = None

    def __post_init__(self):
        _checked(self.receipt, E1OperationReceipt)
        if self.archive is not None:
            _checked(self.archive, _execution.E1ScheduledRunArchive)
        if self.audit is not None:
            _checked(self.audit, _audit.E1RunAudit)
        if self.evaluation is not None:
            from experiments import program_k_e1_evaluator as evaluator
            _checked(self.evaluation, evaluator.E1EvaluatorFinding)
        _need((self.archive is None) == (self.audit is None), "Archive/audit must be retained together.")
        _need(self.evaluation is None or self.archive is None,
              "Evaluator evidence cannot be mixed with a scheduled-run payload.")

    @property
    def archive_content_digest(self):
        return None if self.archive is None else _suite._content_digest(self.archive)

    @property
    def audit_content_digest(self):
        return None if self.audit is None else _suite._content_digest(self.audit)

    @property
    def evaluator_content_digest(self):
        if self.evaluation is None:
            return None
        from experiments import program_k_e1_evaluator as evaluator
        return evaluator.content_digest(self.evaluation)


def _payload_bytes(payload):
    _need(type(payload) is tuple and len(payload) == 3, "Malformed E1 payload.")
    archive, audit, evaluation = payload
    from experiments import program_k_e1_evaluator as evaluator
    return _json({
        "archive": None if archive is None else _suite._encoded(archive),
        "audit": None if audit is None else _suite._encoded(audit),
        "evaluation": None if evaluation is None else json.loads(evaluator.canonical_bytes(evaluation)),
    })


class _PhysicalInputGuard:
    """Worker-local wrapper at the single physical Engine boundary."""

    def __init__(self, cap, report, watchdog=None):
        _integer(cap, "Physical input cap", positive=True)
        self.cap, self.report, self.watchdog, self.count = cap, report, watchdog, 0
        self.original = None

    def __enter__(self):
        original = self.original = MinesweeperEngine.step
        guard = self

        def counted(engine, *args, **kwargs):
            if guard.watchdog is not None and guard.watchdog.timed_out:
                raise E1OperationalAbort("SYSTEM_DECISION_TIMEOUT")
            if guard.count >= guard.cap:
                raise E1OperationalAbort("SYSTEM_INPUT_CAP")
            guard.count += 1
            if guard.watchdog is not None:
                guard.watchdog.reset()
            guard.report("BEFORE_INPUT")
            return original(engine, *args, **kwargs)

        MinesweeperEngine.step = counted
        return self

    def __exit__(self, *_):
        MinesweeperEngine.step = self.original


class _DecisionWatchdog:
    """Sample one thread only; no callbacks are installed on the execution thread."""

    def __init__(self, main_thread_id, decision_codes, max_wall_ms, interval_ms, report,
                 *, regions=()):
        _integer(max_wall_ms, "Decision wall cap", positive=True)
        _integer(interval_ms, "Sampling interval", positive=True)
        self.main_thread_id, self.decision_codes = main_thread_id, frozenset(decision_codes)
        self.max_wall_ms, self.interval_ms, self.report = max_wall_ms, interval_ms, report
        self.regions = tuple(regions)
        self.timed_out = False
        self._failure = None
        self._key = self._since = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def reset(self):
        with self._lock:
            self._key = self._since = None

    def sample(self, frames=None, now_ns=None):
        frames = sys._current_frames() if frames is None else frames
        now_ns = time.monotonic_ns() if now_ns is None else now_ns
        frame = frames.get(self.main_thread_id)
        selected = None
        while frame is not None:
            if (frame.f_code in self.decision_codes or any(
                    frame.f_code is code and first <= frame.f_lineno <= last
                    for code, first, last in self.regions)):
                selected = frame
            frame = frame.f_back
        key = None if selected is None else id(selected)
        detail = None
        with self._lock:
            if key is None:
                self._key = self._since = None
            elif key != self._key:
                self._key, self._since = key, now_ns
            elif not self.timed_out and now_ns - self._since >= self.max_wall_ms * 1000000:
                self.timed_out = True
                detail = f"continuously sampled decision; interval_ms={self.interval_ms}; elapsed_ns={now_ns-self._since}"
        if detail is not None:
            self.report("SYSTEM_DECISION_TIMEOUT", detail)
        return self.timed_out

    def _monitor(self):
        try:
            while not self._stop.wait(self.interval_ms / 1000):
                if self.sample():
                    return
        except BaseException as error:
            self.timed_out = True
            self._failure = "STACK_MONITOR_INCOMPLETE:" + type(error).__name__
            try:
                self.report("WORKER_ABORT", self._failure)
            except BaseException:
                pass

    def start(self):
        self._thread = threading.Thread(target=self._monitor, daemon=True,
                                        name="program-k-e1-stack-sampler")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            if self._thread.is_alive():
                raise E1OperationalAbort("STACK_MONITOR_REAP_INCOMPLETE")
        if self._failure is not None:
            raise E1OperationalAbort(self._failure)


def _decision_watchdog(report, envelope):
    # The K runner's own frame bridges its adjacent analysis and policy calls.
    # Restrict that frame to the planning block, excluding Engine, archival and
    # shadow wait work. These source lines belong to authenticated frozen bytes.
    lines, first = inspect.getsourcelines(_runner.run_k_p0)
    lower = next(first + n for n, line in enumerate(lines)
                 if "decision = session.analyze_decision(" in line)
    upper = next(first + n for n, line in enumerate(lines)
                 if "analysis_ns = perf_counter_ns() - started_ns" in line)
    codes = (_capability.KLocalSession.analyze_decision.__code__, _policy.select_policy.__code__,
             _planner.plan_position.__code__, _runner.validate_k_p0_execution.__code__,
             _v1._validate_execution.__code__)
    return _DecisionWatchdog(threading.get_ident(), codes, envelope.max_decision_wall_ms,
                             envelope.monitor_interval_ms, report,
                             regions=((_runner.run_k_p0.__code__, lower, upper),))


def _require_no_tracer():
    _need(sys.gettrace() is None and sys.getprofile() is None
          and threading.gettrace() is None and threading.getprofile() is None,
          "E1 timing context requires no line/profile tracer.")


class _WorkerChannel:
    """Bounded, acknowledged E1 IPC; worker memory remains under the Job cap."""

    def __init__(self, connection, envelope):
        self.connection, self.envelope = connection, envelope
        self._lock = threading.Lock()

    def _send(self, message):
        raw = pickle.dumps(message, protocol=5)
        _need(len(raw) <= _CHUNK_SIZE + 4096, "IPC frame exceeds its bounded size.")
        self.connection.send_bytes(raw)
        if self.connection.recv_bytes(32) != b"CONTINUE":
            raise E1OperationalAbort("SYSTEM_PARENT_ABORT")

    def event(self, event, payload=None):
        with self._lock:
            self._send((event, payload))

    def finish(self, payload):
        canonical = _payload_bytes(payload)
        wire = pickle.dumps(payload, protocol=5)
        with self._lock:
            self._send(("RESULT_STARTED", (len(wire), hashlib.sha256(wire).hexdigest(),
                                           len(canonical), hashlib.sha256(canonical).hexdigest())))
            for offset in range(0, len(wire), _CHUNK_SIZE):
                self._send(("RESULT_CHUNK", wire[offset:offset + _CHUNK_SIZE]))
            self._send(("FINISHED", None))


def _validate_scheduled_payload(plan, entry, identity, envelope, payload):
    archive, audit, evaluation = payload
    _need(evaluation is None, "Scheduled payload contains evaluator data.")
    _checked(archive, _execution.E1ScheduledRunArchive)
    _checked(audit, _audit.E1RunAudit)
    _suite._validate_pair(plan, archive, audit)
    _need(archive.schedule_entry == entry and audit.schedule_entry == entry
          and archive.shadow_timeout_s == envelope.shadow_timeout_ms / 1000,
          "Worker returned another requested schedule/timeout.")
    _need(_audit.capture_audit_source_identity(plan, archive) == identity.audit_source_identity
          and _suite.capture_suite_source_identity(plan, archive, audit) == identity.suite_source_identity,
          "Actual archive/audit source capture differs from prospective identity.")
    _need(archive.execution_source_identity == identity.execution_source_identity,
          "Execution source identity differs.")


def _scheduled_worker_operation(plan, entry, identity, envelope, *, report=None):
    _need(capture_operational_source_identity(plan) == identity, "Worker source precheck differs.")
    if report is None:
        archive = _execution.execute_scheduled_entry(
            plan, entry.schedule_index, shadow_timeout_s=envelope.shadow_timeout_ms / 1000)
    else:
        watchdog = _decision_watchdog(report, envelope)
        watchdog.start()
        try:
            with _PhysicalInputGuard(envelope.max_physical_inputs_per_case, report, watchdog):
                archive = _execution.execute_scheduled_entry(
                    plan, entry.schedule_index, shadow_timeout_s=envelope.shadow_timeout_ms / 1000)
        finally:
            watchdog.stop()
        _need(not watchdog.timed_out, "SYSTEM_DECISION_TIMEOUT")
    # Public post-hoc replay calls some of the same functions, but is not a
    # physical decision span. Case/job/Job-memory supervision remains active.
    audit = _audit.audit_scheduled_run(plan, archive)
    payload = (archive, audit, None)
    _validate_scheduled_payload(plan, entry, identity, envelope, payload)
    _need(capture_operational_source_identity(plan) == identity, "Worker source postcheck differs.")
    return payload


def _worker_main(kind, request, identity, envelope, connection, barrier):
    barrier.wait()  # No source validation, board materialization or answer before Job attachment.
    channel = _WorkerChannel(connection, envelope)
    try:
        require_operating_envelope(envelope)
        _require_no_tracer()
        channel.event("STARTED")
        if kind == "SCHEDULED_RUN":
            plan, entry = request
            payload = _scheduled_worker_operation(plan, entry, identity, envelope, report=channel.event)
        elif kind == "POST_HOC_EVALUATOR":
            from experiments import program_k_e1_evaluator as evaluator
            plan, aggregate, binding, run_id = request
            _need(capture_operational_source_identity(plan) == identity, "Evaluator source precheck differs.")
            finding = evaluator.evaluate_scheduled_kp0(
                plan, aggregate, binding, evaluation_run_id=run_id)
            evaluator.verify_e1_finding(plan, aggregate, binding, finding, evaluation_run_id=run_id)
            _need(capture_operational_source_identity(plan) == identity, "Evaluator source postcheck differs.")
            payload = (None, None, finding)
        else:
            raise E1OperationalError("Unknown E1 operation kind.")
        _require_no_tracer()
        channel.finish(payload)
    except BaseException as error:
        try:
            cause = error
            while cause.__cause__ is not None and not isinstance(cause, E1OperationalAbort):
                cause = cause.__cause__
            diagnosis = str(cause) if isinstance(cause, E1OperationalAbort) else f"{type(error).__name__}:{error}"
            channel.event("WORKER_ABORT", diagnosis[:2048])
        except BaseException:
            pass
        raise
    finally:
        connection.close()


def _supervise_e1(kind, entry, identity, envelope, request, *, job_started_ns,
                  archive_used_bytes, worker_target=None, validate=None):
    """Private two-kind E1 process seam; a test target cannot add a research kind.

    A bounded reader thread isolates Connection.recv_bytes, whose framed receive
    can otherwise block after poll. Parent deadlines never depend on worker IPC
    completion. Each wire frame and total result are bounded before admission.
    Coordinator helpers run only bounded transport/pure verification. Python
    cannot forcibly cancel a thread; a failed bounded join is explicitly
    INCOMPLETE and can never certify containment completion.
    """
    _need(kind in ("SCHEDULED_RUN", "POST_HOC_EVALUATOR"), "Unknown E1 operation kind.")
    envelope = require_operating_envelope(envelope)
    entry = _checked(entry, _e1.ScheduleEntry)
    identity = _checked(identity, E1OperationalSourceIdentity)
    _integer(job_started_ns, "job_started_ns", positive=True)
    _integer(archive_used_bytes, "archive_used_bytes")
    started = time.monotonic_ns()
    _need(job_started_ns <= started, "Whole-job start must not be in the future.")
    run_id = request[-1] if kind == "POST_HOC_EVALUATOR" else None
    operation_id = f"{kind}:{entry.schedule_index:02d}" + (f":{run_id}" if run_id is not None else "")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    barrier = context.Event()
    process = context.Process(target=_worker_main if worker_target is None else worker_target,
                              args=(kind, request, identity, envelope, child, barrier))
    inbox = Queue(maxsize=2)
    reader_stop = threading.Event()
    reader = None
    api = job = peak_memory = None
    memory = None
    events, reason, payload = [], None, None
    inputs = peak_worker = peak_combined = samples = 0
    worker_budget = 0
    wire = bytearray()
    metadata = None
    result_digest = None
    result_size = 0
    finished = False
    validation_thread = None
    validation_result = Queue(maxsize=1)
    event_archive_bytes = 0
    header_archive_reserve = len(_json(_plain(envelope))) + len(_json(operation_id)) + 8192

    def validate_candidate(wire_buffer, declared, expected_inputs):
        try:
            _need(hashlib.sha256(wire_buffer).hexdigest() == declared[1],
                  "Result wire digest differs.")
            candidate = pickle.loads(wire_buffer)
            canonical = _payload_bytes(candidate)
            _need(len(canonical) == declared[2]
                  and hashlib.sha256(canonical).hexdigest() == declared[3],
                  "Result content digest/size differs.")
            if validate is not None:
                validate(candidate)
            archive, audit, evaluation = candidate
            _need((kind == "SCHEDULED_RUN" and evaluation is None)
                  or (kind == "POST_HOC_EVALUATOR" and archive is None and audit is None),
                  "Result operation kind differs.")
            if archive is not None:
                _need(len(archive.result.traces) == expected_inputs,
                      "Physical input count differs from final archive.")
            if kind == "POST_HOC_EVALUATOR":
                _need(expected_inputs == 0, "Evaluator performed physical inputs.")
            validation_result.put((candidate, len(canonical), declared[3], None))
        except BaseException as error:
            validation_result.put((None, 0, None, error))

    def record(event, detail=None):
        nonlocal event_archive_bytes
        item = E1MonitorEvent(len(events), event, time.monotonic_ns() - started, inputs, detail)
        events.append(item)
        event_archive_bytes += len(_json(asdict(item))) + 1
        result_bytes = 0 if metadata is None else metadata[2]
        if archive_used_bytes + result_bytes + header_archive_reserve + event_archive_bytes > envelope.archive_cap_bytes:
            raise E1OperationalAbort("SYSTEM_ARCHIVE_CAP")

    def read_frames():
        while not reader_stop.is_set():
            try:
                value = ("FRAME", parent.recv_bytes(_CHUNK_SIZE + 4096))
            except BaseException as error:
                value = ("READER_ERROR", type(error).__name__)
            while not reader_stop.is_set():
                try:
                    inbox.put(value, timeout=0.05)
                    break
                except Full:
                    continue
            if value[0] != "FRAME":
                return

    def sample_memory():
        nonlocal peak_worker, peak_combined, samples
        worker, coordinator = peak_memory(), _harness._coordinator_private_bytes()
        _integer(worker, "Worker-tree memory", positive=True)
        _integer(coordinator, "Coordinator memory", positive=True)
        peak_worker = max(peak_worker, worker)
        peak_combined = max(peak_combined, worker + coordinator)
        samples += 1
        return worker > worker_budget or worker + coordinator > envelope.memory_cap_bytes

    try:
        if archive_used_bytes >= envelope.archive_cap_bytes:
            raise E1OperationalAbort("SYSTEM_ARCHIVE_CAP")
        if started >= job_started_ns + envelope.max_job_wall_ms * 1000000:
            raise E1OperationalAbort("SYSTEM_JOB_TIMEOUT")
        process.start()
        child.close()
        worker_budget = envelope.memory_cap_bytes - _harness._coordinator_private_bytes()
        if worker_budget <= 0:
            raise E1OperationalAbort("SYSTEM_MEMORY_CAP")
        api, job, peak_memory = _harness._attach_memory_job(process.pid, worker_budget)
        record("JOB_ATTACHED")
        if sample_memory():
            raise E1OperationalAbort("SYSTEM_MEMORY_CAP")
        reader = threading.Thread(target=read_frames, daemon=True, name="program-k-e1-ipc-reader")
        reader.start()
        before_release = time.monotonic_ns()
        if before_release >= job_started_ns + envelope.max_job_wall_ms * 1000000:
            raise E1OperationalAbort("SYSTEM_JOB_TIMEOUT")
        if before_release >= started + envelope.max_case_wall_ms * 1000000:
            raise E1OperationalAbort("SYSTEM_CASE_TIMEOUT")
        barrier.set()
        while True:
            if sample_memory():
                raise E1OperationalAbort("SYSTEM_MEMORY_CAP")
            now = time.monotonic_ns()
            deadline, expiry = min(
                (job_started_ns + envelope.max_job_wall_ms * 1000000, "SYSTEM_JOB_TIMEOUT"),
                (started + envelope.max_case_wall_ms * 1000000, "SYSTEM_CASE_TIMEOUT"))
            if now >= deadline:
                raise E1OperationalAbort(expiry)
            if finished:
                if validation_thread is not None and not validation_thread.is_alive():
                    verified_payload, verified_size, verified_digest, validation_error = validation_result.get_nowait()
                    validation_thread = None
                    if validation_error is not None:
                        raise E1OperationalError("Result verification failed: " + str(validation_error))
                    payload, result_size, result_digest = verified_payload, verified_size, verified_digest
                if not process.is_alive():
                    process.join(timeout=0)
                    _need(process.exitcode == 0, "SYSTEM_PROCESS_ABORT")
                    if validation_thread is None:
                        break
                wait = min(envelope.monitor_interval_ms / 1000, (deadline - now) / 1000000000)
                if validation_thread is not None:
                    validation_thread.join(timeout=wait)
                else:
                    process.join(timeout=wait)
                continue
            wait = min(envelope.monitor_interval_ms / 1000, (deadline - now) / 1000000000)
            try:
                mode, raw = inbox.get(timeout=wait)
            except Empty:
                if not process.is_alive():
                    raise E1OperationalAbort("SYSTEM_PROCESS_ABORT")
                continue
            if mode != "FRAME":
                raise E1OperationalAbort("SYSTEM_PROCESS_ABORT:" + raw)
            message = pickle.loads(raw)
            _need(type(message) is tuple and len(message) == 2, "Malformed IPC message.")
            event, data = message
            if event == "STARTED":
                _need(len(events) == 1 and data is None, "Malformed start boundary.")
                record(event)
            elif event == "BEFORE_INPUT":
                _need(len(events) >= 2 and metadata is None and data is None
                      and kind == "SCHEDULED_RUN", "Unexpected physical input.")
                if inputs >= envelope.max_physical_inputs_per_case:
                    raise E1OperationalAbort("SYSTEM_INPUT_CAP")
                inputs += 1
                record(event)
            elif event in ("SYSTEM_DECISION_TIMEOUT", "WORKER_ABORT"):
                _need(type(data) is str and bool(data), "Missing worker diagnosis.")
                record(event, data)
                raise E1OperationalAbort(event if event == "SYSTEM_DECISION_TIMEOUT" else data)
            elif event == "RESULT_STARTED":
                _need(len(events) >= 2 and metadata is None and type(data) is tuple and len(data) == 4,
                      "Malformed result start.")
                wire_size, wire_digest, canonical_size, canonical_digest = data
                _integer(wire_size, "Wire size", positive=True)
                _integer(canonical_size, "Result size", positive=True)
                _sha(wire_digest)
                _sha(canonical_digest)
                remaining = envelope.archive_cap_bytes - archive_used_bytes
                if max(wire_size, canonical_size) > remaining:
                    raise E1OperationalAbort("SYSTEM_ARCHIVE_CAP")
                metadata = data
                record(event)
            elif event == "RESULT_CHUNK":
                _need(metadata is not None and type(data) is bytes and 0 < len(data) <= _CHUNK_SIZE,
                      "Malformed result chunk.")
                _need(len(wire) + len(data) <= metadata[0], "Result exceeds declared size.")
                wire.extend(data)
            elif event == "FINISHED":
                _need(data is None and metadata is not None and len(wire) == metadata[0],
                      "Result wire size differs.")
                record(event)
                finished = True
                validation_thread = threading.Thread(
                    target=validate_candidate, args=(wire, metadata, inputs), daemon=True,
                    name="program-k-e1-result-verifier")
                validation_thread.start()
            else:
                raise E1OperationalError("Unknown E1 worker message.")
            parent.send_bytes(b"CONTINUE")
    except (Exception, KeyboardInterrupt) as error:
        reason = str(error) if isinstance(error, E1OperationalAbort) else (
            f"SUPERVISION_INCOMPLETE:{type(error).__name__}:{error}")
    finally:
        reader_stop.set()
        if job is not None:
            try:
                if sample_memory():
                    reason = reason or "SYSTEM_MEMORY_CAP"
                memory = _harness.MemoryEvidence(
                    peak_worker, peak_combined, samples, worker_budget, envelope.memory_cap_bytes)
            except BaseException as error:
                reason = reason or f"MEMORY_MONITOR_INCOMPLETE:{type(error).__name__}"
            if reason is not None:
                if not api.TerminateJobObject(job, 1):
                    reason += ";JOB_TERMINATION_FAILED"
            if not api.CloseHandle(job):
                reason = (reason or "SYSTEM_JOB_CLOSE_FAILED") + ";JOB_CLOSE_FAILED"
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
                reason = (reason or "SYSTEM_PROCESS_ABORT") + ";WORKER_REAP_INCOMPLETE"
        parent.close()
        child.close()
        if reader is not None:
            reader.join(timeout=1)
            if reader.is_alive():
                reason = (reason or "SYSTEM_PROCESS_ABORT") + ";READER_REAP_INCOMPLETE"
        if validation_thread is not None:
            validation_thread.join(timeout=1)
            if validation_thread.is_alive():
                reason = (reason or "SYSTEM_PROCESS_ABORT") + ";RESULT_VERIFIER_REAP_INCOMPLETE"
        if reason is None and (not finished or process.exitcode != 0 or memory is None):
            reason = "SYSTEM_PROCESS_ABORT" if memory is not None else "MEMORY_MONITOR_INCOMPLETE"
    elapsed_ns = time.monotonic_ns() - started
    if reason is None and elapsed_ns >= envelope.max_case_wall_ms * 1000000:
        reason = "SYSTEM_CASE_TIMEOUT"
    if reason is None and time.monotonic_ns() >= job_started_ns + envelope.max_job_wall_ms * 1000000:
        reason = "SYSTEM_JOB_TIMEOUT"
    receipt_values = dict(
        operation_kind=kind, operation_id=operation_id, schedule_index=entry.schedule_index,
        case_id=entry.case_id, repetition=entry.repetition, variant=entry.variant,
        operational_source_digest=identity.digest, envelope_digest=_harness.content_digest(envelope),
        status="COMPLETE" if reason is None else "INCOMPLETE", reason=reason, events=tuple(events),
        elapsed_ns=elapsed_ns, physical_inputs=inputs, result_digest=result_digest, result_size_bytes=result_size,
        exit_code=process.exitcode, memory_evidence=memory, monitoring_policy=MONITORING_POLICY,
        monitoring_context=MONITORING_CONTEXT, monitor_interval_ms=envelope.monitor_interval_ms,
        archive_used_before_bytes=archive_used_bytes, archive_result_bytes=result_size, envelope=envelope)
    receipt = _make_receipt(**receipt_values)
    return E1OperationResult(receipt, *(payload if payload is not None else (None, None, None)))


def supervise_scheduled_run(plan, schedule_index, envelope, *, job_started_ns, archive_used_bytes):
    """One disposable scheduled invocation; later orchestration owns authorization."""
    plan = _checked(plan, _e1.E1Plan)
    _integer(schedule_index, "schedule_index")
    _need(schedule_index < 54, "Schedule index must be in 0..53.")
    envelope = require_operating_envelope(envelope)
    identity = capture_operational_source_identity(plan)
    entry = plan.schedule[schedule_index]

    def validate(payload):
        _validate_scheduled_payload(plan, entry, identity, envelope, payload)
        _need(capture_operational_source_identity(plan) == identity, "Parent source postcheck differs.")

    return _supervise_e1("SCHEDULED_RUN", entry, identity, envelope, (plan, entry),
                         job_started_ns=job_started_ns, archive_used_bytes=archive_used_bytes,
                         validate=validate)


def supervise_posthoc_evaluator(plan, suite_aggregate, kp0_binding, envelope, *,
                                job_started_ns, archive_used_bytes, evaluation_run_id):
    """One post-hoc worker after all fixed archives exist; no truth in the parent."""
    from experiments import program_k_e1_evaluator as evaluator
    binding = evaluator.validate_evaluator_request(plan, suite_aggregate, kp0_binding)
    _need(type(evaluation_run_id) is str and bool(evaluation_run_id.strip()),
          "Explicit evaluator run identifier is required.")
    envelope = require_operating_envelope(envelope)
    identity = capture_operational_source_identity(plan)

    def validate(payload):
        _need(payload[0] is None and payload[1] is None, "Evaluator returned solver records.")
        evaluator.verify_e1_finding(plan, suite_aggregate, binding, payload[2],
                                    evaluation_run_id=evaluation_run_id)
        _need(capture_operational_source_identity(plan) == identity, "Parent source postcheck differs.")

    return _supervise_e1(
        "POST_HOC_EVALUATOR", binding.schedule_entry, identity, envelope,
        (plan, suite_aggregate, binding, evaluation_run_id),
        job_started_ns=job_started_ns, archive_used_bytes=archive_used_bytes, validate=validate)


@dataclass(frozen=True, slots=True)
class E1ResourceSummary:
    operational_source_digest: str
    suite_content_digest: str
    scheduled_expected: int
    scheduled_received: int
    scheduled_complete: int
    scheduled_incomplete: int
    evaluator_expected: int
    evaluator_received: int
    evaluator_complete: int
    evaluator_incomplete: int
    scheduled_keys: tuple
    evaluator_keys: tuple
    total_physical_inputs: int
    case_elapsed_ns: tuple
    max_case_elapsed_ns: int
    memory_evidence: tuple
    max_peak_worker_tree_bytes: int | None
    max_peak_combined_sampled_bytes: int | None
    archive_bytes: int
    reasons: tuple[str, ...]
    classifications: tuple
    evaluator_call_count: int
    evaluator_duration_ns: int
    runner_timings: tuple
    oracle_timings: tuple
    monitoring_context: str
    n2_status: str
    resource_status: str


def summarize_operational_resources(plan, suite_aggregate, scheduled_receipts, evaluator_results):
    """Pure evidence reconciliation; no execution, thresholds, or qualification."""
    from experiments import program_k_e1_evaluator as evaluator
    _checked(plan, _e1.E1Plan)
    _need(type(suite_aggregate) is _suite.E1SuiteAggregate,
          "Expected exact E1SuiteAggregate for resource reconciliation.")
    _suite._encoded(suite_aggregate)
    _need(type(suite_aggregate.bindings) is tuple and len(suite_aggregate.bindings) == 54,
          "The complete fixed archive/audit family is required.")
    aggregate = _suite.aggregate_e1_suite(
        plan, tuple(binding.archive for binding in suite_aggregate.bindings),
        tuple(binding.audit for binding in suite_aggregate.bindings))
    _need(_suite._encoded(aggregate) == _suite._encoded(suite_aggregate),
          "Suite aggregate does not reconstruct from its bound archive/audit family.")
    aggregate_digest = _suite._content_digest(aggregate)
    identity = capture_operational_source_identity(plan)
    _need(type(scheduled_receipts) is tuple and type(evaluator_results) is tuple,
          "Resource evidence inputs must be immutable tuples.")
    failures, missing, reasons = [], [], []
    scheduled, evaluations, memories = {}, {}, []
    classifications = {"G1_FALSIFICATION": 0, "NO_COUNTEREXAMPLE": 0, "NOT_EVALUATED": 0}
    evaluator_calls = []
    bindings = {b.schedule_entry.schedule_index: b for b in aggregate.bindings}

    def admit_receipt(receipt):
        _need(type(receipt) is E1OperationReceipt, "Expected exact E1OperationReceipt.")
        if receipt.memory_evidence is None and receipt.status == "COMPLETE":
            # Missing measurement is incompleteness, even for a corrupted or
            # externally restored completion claim. Validate every other field
            # without manufacturing memory measurements.
            altered = {field.name: getattr(receipt, field.name) for field in fields(receipt)}
            altered.update(status="INCOMPLETE", reason="MEMORY_EVIDENCE_MISSING")
            _make_receipt(**altered)
            _need(receipt.exit_code == 0 and receipt.result_digest is not None
                  and receipt.result_size_bytes > 0 and len(receipt.events) >= 3
                  and receipt.events[0].event == "JOB_ATTACHED"
                  and receipt.events[1].event == "STARTED"
                  and receipt.events[-1].event == "FINISHED", "Invalid completion evidence.")
            missing.append("Missing per-operation memory evidence.")
        else:
            _checked(receipt, E1OperationReceipt)
        return receipt

    for receipt in scheduled_receipts:
        try:
            admit_receipt(receipt)
            _need(receipt.operation_kind == "SCHEDULED_RUN", "Wrong scheduled receipt kind.")
            _need(receipt.schedule_index not in scheduled, "Duplicate scheduled receipt.")
            scheduled[receipt.schedule_index] = receipt
            binding = bindings[receipt.schedule_index]
            expected = _payload_bytes((binding.archive, binding.audit, None))
            if receipt.status == "COMPLETE":
                _need(receipt.physical_inputs == len(binding.archive.result.traces)
                      and receipt.result_digest == hashlib.sha256(expected).hexdigest()
                      and receipt.result_size_bytes == len(expected),
                      "Scheduled receipt/archive evidence differs.")
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            failures.append(str(error))
    for result in evaluator_results:
        try:
            _need(type(result) is E1OperationResult, "Expected exact E1OperationResult.")
            receipt = admit_receipt(result.receipt)
            if receipt.memory_evidence is None and receipt.status == "COMPLETE":
                altered = {field.name: getattr(receipt, field.name) for field in fields(receipt)}
                altered.update(status="INCOMPLETE", reason="MEMORY_EVIDENCE_MISSING")
                replace(result, receipt=_make_receipt(**altered))
            else:
                _checked(result, E1OperationResult)
            _need(receipt.operation_kind == "POST_HOC_EVALUATOR", "Wrong evaluator receipt kind.")
            _need(receipt.schedule_index not in evaluations, "Duplicate evaluator receipt.")
            evaluations[receipt.schedule_index] = receipt
            if result.evaluation is not None:
                binding = bindings[receipt.schedule_index]
                _need(binding.schedule_entry.variant == "K-P0", "Evaluator binding is not K-P0.")
                evaluator._verify_admitted_finding(
                    plan, aggregate, binding, result.evaluation, None,
                    suite_content_digest=aggregate_digest)
                _need(receipt.operation_id == (
                    f"POST_HOC_EVALUATOR:{receipt.schedule_index:02d}:{result.evaluation.evaluation_run_id}"),
                    "Evaluator receipt run identifier differs.")
                expected = _payload_bytes((None, None, result.evaluation))
                _need(receipt.result_digest == hashlib.sha256(expected).hexdigest()
                      and receipt.result_size_bytes == len(expected), "Evaluator receipt/result binding differs.")
                classifications[result.evaluation.finding.classification] += 1
                evaluator_calls.extend(result.evaluation.evaluator_calls)
            elif receipt.status == "COMPLETE":
                failures.append("Complete evaluator receipt lacks its finding.")
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            failures.append(str(error))
    expected_evaluators = {index for index, binding in bindings.items()
                           if binding.schedule_entry.variant == "K-P0"}
    if set(scheduled) != set(range(54)):
        missing.append("Scheduled receipt coverage is incomplete.")
    if set(evaluations) != expected_evaluators:
        missing.append("Evaluator receipt coverage is incomplete.")
    all_receipts = tuple(scheduled.values()) + tuple(evaluations.values())
    for receipt in all_receipts:
        if receipt.operational_source_digest != identity.digest:
            failures.append("Receipt operational source differs.")
        if receipt.reason is not None:
            reasons.append(receipt.reason)
            missing.append("An operation is incomplete.")
        if receipt.memory_evidence is None:
            missing.append("Missing per-operation memory evidence.")
        else:
            memories.append((receipt.operation_id, receipt.memory_evidence))
    if len({receipt.envelope_digest for receipt in all_receipts}) > 1:
        failures.append("Operation envelope identities differ.")
    budget_order = sorted(all_receipts, key=lambda r: (r.archive_used_before_bytes, r.archive_used_after_bytes))
    for previous, current in zip(budget_order, budget_order[1:]):
        if previous.archive_used_after_bytes > current.archive_used_before_bytes:
            failures.append("Operation archive budgets overlap.")
        elif previous.archive_used_after_bytes < current.archive_used_before_bytes:
            missing.append("Operation archive budget chain has a gap.")
    scheduled_complete = sum(receipt.status == "COMPLETE" for receipt in scheduled.values())
    evaluator_complete = sum(receipt.status == "COMPLETE" for receipt in evaluations.values())
    n2 = ("ADDRESSED_BY_SUPERVISED_CONTEXT_BINDING"
          if len(scheduled) == 54 and scheduled_complete == 54 and not failures
          and all(receipt.monitoring_context == MONITORING_CONTEXT
                                         for receipt in scheduled.values())
          else "INCOMPLETE")
    resource_status = ("FAIL_IDENTITY_OR_EVIDENCE" if failures else "INCOMPLETE" if missing
                       else "COMPLETE_CONTAINMENT_EVIDENCE")
    case_elapsed = tuple((index, receipt.elapsed_ns) for index, receipt in sorted(scheduled.items()))
    return E1ResourceSummary(
        identity.digest, aggregate_digest, 54, len(scheduled_receipts), scheduled_complete,
        len(scheduled_receipts) - scheduled_complete, 18, len(evaluator_results), evaluator_complete,
        len(evaluator_results) - evaluator_complete,
        tuple((r.schedule_index, r.case_id, r.repetition, r.variant) for _, r in sorted(scheduled.items())),
        tuple((r.schedule_index, r.case_id, r.repetition, r.variant) for _, r in sorted(evaluations.items())),
        sum(r.physical_inputs for r in scheduled.values()), case_elapsed,
        max((value for _, value in case_elapsed), default=0), tuple(memories),
        max((m.peak_worker_tree_bytes for _, m in memories), default=None),
        max((m.peak_combined_bytes for _, m in memories), default=None),
        sum(r.archive_result_bytes + r.archive_receipt_bytes for r in all_receipts),
        tuple(failures + missing + reasons), tuple(sorted(classifications.items())),
        len(evaluator_calls), sum(call.duration_ns for call in evaluator_calls),
        aggregate.diagnostics.runner_timings, aggregate.diagnostics.oracle_timings,
        MONITORING_CONTEXT, n2, resource_status)
