"""I7 synthetic integration qualification over sealed I2 evidence.

This is implementation qualification, not Actual-E2 admission or a research
verdict. It never executes an Engine, runner, oracle or private evaluator. The
I6 terminal result is required because post-seal operational failures cannot be
inferred from immutable files. Its claims are reconciled, not trusted as proof.

One validation pass per stream uses the unchanged I2 scanner. Fixed one-record
queues merge its callbacks by board/unit; only the current board's detailed
premises and compact O(N) receipts/analysis rows remain resident. I6's preceding
seal/readback is a separate phase; this layer does not repeat either pass.
"""

from dataclasses import dataclass
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import platform
from queue import Empty, Full, Queue
import subprocess
import threading
import time

from core_engine import CellState
from stage3_physical import action_cost, load_timing_table
from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records
from experiments import program_k_e2_store as store
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_operational as operational
from experiments import program_k_e2_game as game
from experiments import program_k_e2_analysis as analysis
from experiments import program_k_e2_report as report
from experiments import program_k_oracles as oracles


_ROOT = Path(__file__).resolve().parents[1]
_PROTOCOL = "docs/stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md"
_FREEZE = "6d3eb456d72632d24e9cab14bdeea0cffd279092"
_BLOB = "3351017f0f0116be00917be3ff95312120f43117"
_E1 = "6106f730320c35e7123a75526f34dbeadeef3c5d"
_PROTECTED = (
    "docs/stage3-extended/STAGE3_PROGRAM_K_RESEARCH_SPEC.md",
    "docs/stage3-extended/STAGE3_PROGRAM_K_GATE_R_PROTOCOL.md",
    "experiments/program_k_capability.py", "experiments/program_k_policy.py",
    "experiments/program_k_runner.py", "experiments/program_k_oracles.py",
    "experiments/program_k_evidence.py", "experiments/program_k_harness.py",
    "experiments/program_k_evaluator.py", "tests/test_program_k_semantics.py",
    "tests/test_program_k_policy.py", "tests/test_program_k_harness.py",
    "core_engine.py", "simple_algorithm.py", "simple_probability.py",
    "simple_decision.py", "stage3_physical.py", "stage3_planner.py",
    "stage3_runner.py", "calibration/stage3_physical_profile_v1.json",
)
_E2 = tuple("experiments/program_k_e2_" + name + ".py" for name in (
    "identity", "records", "store", "analysis", "report", "game", "audit",
    "evaluator", "execution", "operational", "qualification"))
_CANDIDATES = (_E2[-1], "tests/test_program_k_e2_qualification.py")
_AMENDMENT = "docs/stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md"
_AMENDMENT_SHA256 = "5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf"
_AMENDMENT_BYTE_LENGTH = 58_052
_R0_SOURCE_PATHS = ("experiments/program_k_e2_readiness.py",
                    "experiments/program_k_e2_r0_harness.py", _AMENDMENT)
_REPAIR_TEST = "tests/test_program_k_e2_operational.py"
IDENTITY_STREAM = "qualification_identity"
_STREAMS = execution.STREAM_NAMES + ("operations", "resources")
_SCOPE = "SYNTHETIC_I7_INTEGRATION_ONLY"


class QualificationError(ValueError):
    """Static public failure; no raw exception/private evidence is published."""


def _need(condition, reason):
    if not condition:
        raise QualificationError(reason)


def _git(*args, data=None):
    result = subprocess.run(("git", "--no-optional-locks", "-C", str(_ROOT), *args), input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=30, check=False)
    _need(result.returncode == 0, "SOURCE_IDENTITY_UNAVAILABLE")
    return result.stdout


def _blobs(refs):
    raw = _git("cat-file", "--batch", data=("\n".join(refs) + "\n").encode("ascii"))
    result = []
    for _ in refs:
        header, separator, raw = raw.partition(b"\n")
        parts = header.split()
        _need(separator and len(parts) == 3 and parts[1] == b"blob", "SOURCE_BLOB_REQUIRED")
        size = int(parts[2])
        value, raw = raw[:size], raw[size:]
        _need(len(value) == size and raw.startswith(b"\n"), "SOURCE_BLOB_TRUNCATED")
        raw = raw[1:]
        result.append((parts[0].decode("ascii"), value))
    _need(not raw, "SOURCE_BLOB_TRAILING_DATA")
    return tuple(result)


def capture_sources():
    """Authenticate committed continuity and the permitted I7 candidate bytes.

    No raw E1 working-tree hash is used as the continuity authority. Before I7
    is committed, its candidates and the authorized cancellation-test repair are
    the only dirty-file exceptions. Candidate source/test bytes are bound below;
    the repair exception disappears once the I7 module is tracked.
    """
    head = _git("rev-parse", "HEAD").strip().decode("ascii")
    status = _git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8")
    candidate_is_new = not _git("ls-files", "--", _E2[-1]).strip()
    repair_modified = False
    for line in status.splitlines():
        repair = candidate_is_new and line == " M " + _REPAIR_TEST
        _need((line[:2] == "??" and line[3:] in _CANDIDATES) or repair,
              "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE")
        repair_modified = repair_modified or repair
    # R0-B uses readiness sizing/selection and the separately frozen amendment.
    # Bind their committed identities without weakening I7 worktree or plan hygiene.
    paths = tuple(sorted(set(_PROTECTED + ("benchmark_board.py", _PROTOCOL, _REPAIR_TEST)
                             + _E2 + _R0_SOURCE_PATHS)))
    committed = tuple(path for path in paths if not candidate_is_new or path != _E2[-1])
    refs = tuple(head + ":" + path for path in committed)
    refs += tuple(_E1 + ":" + path for path in _PROTECTED)
    refs += (_FREEZE + ":" + _PROTOCOL,)
    blobs = _blobs(refs)
    current = dict(zip(committed, blobs[:len(committed)]))
    for index, path in enumerate(_PROTECTED):
        _need(current[path] == blobs[len(committed) + index], "E1_CORE_IDENTITY_DRIFT")
    protocol_blob = blobs[-1]
    _need(current[_PROTOCOL] == protocol_blob and protocol_blob[0] == _BLOB,
          "FROZEN_PROTOCOL_IDENTITY_DRIFT")
    identity.validate_protocol_bytes(protocol_blob[1])
    amendment = current[_AMENDMENT][1]
    _need(len(amendment) == _AMENDMENT_BYTE_LENGTH
          and sha256(amendment).hexdigest() == _AMENDMENT_SHA256,
          "FROZEN_AMENDMENT_IDENTITY_DRIFT")
    candidates = {_E2[-1]: (_ROOT / _E2[-1]).read_bytes()}
    if repair_modified:
        candidates[_REPAIR_TEST] = (_ROOT / _REPAIR_TEST).read_bytes()
    if candidate_is_new:
        for path, candidate in candidates.items():
            current[path] = (sha1(b"blob " + str(len(candidate)).encode("ascii") + b"\0" + candidate).hexdigest(), candidate)
    _need(_git("rev-parse", "HEAD").strip().decode("ascii") == head
          and _git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8") == status
          and all((_ROOT / path).read_bytes() == value for path, value in candidates.items()),
          "SOURCE_CHANGED_DURING_CAPTURE")
    return tuple(records.SourceBlobIdentity(path, current[path][0],
                 sha256(current[path][1]).hexdigest(), len(current[path][1])) for path in paths)


def _plan(plan):
    operational.validate_work_plan(plan)
    _need(plan[0].protocol_seed.hex() == identity.PROTOCOL_SHA256, "PROTOCOL_SEED_MISMATCH")
    _need(plan[0].run_id.startswith("synthetic-i7-") and plan[0].runtime is not None,
          "SYNTHETIC_I7_IDENTITY_REQUIRED")
    runtime = records.RuntimeIdentity(platform.python_implementation(), platform.python_version(),
        os.name, platform.platform(), platform.machine(),
        None if plan[0].runtime.host is None else platform.node())
    _need(plan[0].runtime == runtime, "RUNTIME_IDENTITY_MISMATCH")
    for work in plan:
        index = work.board.game_index
        _need(not (1_000_000_000 <= index < 1_001_100_000 or 2_010_000 <= index < 2_010_100),
              "RESEARCH_OR_HOLDOUT_DOMAIN_FORBIDDEN")
    return plan


def _identity_records(plan):
    _plan(plan)
    indices = tuple(work.board.game_index for work in plan)
    digest = identity.corpus_digest(plan[0].protocol_seed, len(plan), indices).hex()
    corpus = records.CorpusIdentity("SYNTHETIC_I7", min(indices), max(indices) + 1,
                                    len(plan), indices, digest, ())
    return (records.ProtocolIdentity(_PROTOCOL, identity.PROTOCOL_SHA256, _BLOB, _FREEZE),
            corpus, plan[0].runtime) + capture_sources()


def write_identity(root, plan):
    """Bind synthetic implementation evidence with existing I1/I2 vocabulary.

    Call before the I6 coordinator. This append-only stream is not an Actual-E2
    manifest, operating envelope, completion receipt or a new persistence format.
    """
    values = _identity_records(plan)
    with store.StreamWriter(root, IDENTITY_STREAM) as writer:
        for ordinal, value in enumerate(values):
            writer.append((ordinal,), value)
        writer.checkpoint()
        return writer.seal()


@dataclass(frozen=True, slots=True)
class QualificationResult:
    status: records.AuditStatus
    reason_codes: tuple
    rows: tuple
    streams: tuple
    analysis_json: bytes | None = None
    report_html: str | None = None


def canonical_result(result):
    """Deterministic public technical summary, never an evidence replacement."""
    _need(type(result) is QualificationResult, "QUALIFICATION_RESULT_REQUIRED")
    return json.dumps({"scope": _SCOPE, "status": result.status.value,
        "reasons": result.reason_codes,
        "rows": tuple({"position": row.position, "pair": records.encode(row.pair).decode("ascii"),
                       "control_model_us": row.control_model_us, "kp0_model_us": row.kp0_model_us,
                       "control_compute_ns": row.control_compute_ns, "kp0_compute_ns": row.kp0_compute_ns}
                      for row in result.rows),
        "streams": tuple((v.name, v.sha256, v.byte_length, v.record_count) for v in result.streams),
        "analysis_sha256": None if result.analysis_json is None else sha256(result.analysis_json).hexdigest(),
        "report_sha256": None if result.report_html is None else sha256(result.report_html.encode("utf-8")).hexdigest(),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


class _Cancelled(Exception):
    pass


class _Lane:
    """One buffered canonical record; the I2 scanner owns parsing and hashing."""

    def __init__(self, root, seal, cancel, deadline, failed, incomplete):
        self.seal, self.cancel, self.deadline = seal, cancel, deadline
        self.queue, self.current, self.done = Queue(maxsize=1), None, False
        self.thread = threading.Thread(target=self._run,
            args=(root, failed, incomplete), name="i7-scan-" + seal.name)
        self.thread.start()

    def _put(self, value):
        while not self.cancel.is_set():
            if time.monotonic_ns() >= self.deadline:
                raise _Cancelled()
            try:
                self.queue.put(value, timeout=0.02)
                return
            except Full:
                pass
        raise _Cancelled()

    def _run(self, root, failed, incomplete):
        def visit(key, record):
            state = getattr(record, "status", None)
            if state in (records.AuditStatus.FAIL, records.EvaluationStatus.FAIL, records.OperationStatus.FAILED):
                failed.set()
            if state in (records.AuditStatus.INCOMPLETE, records.OperationStatus.INCOMPLETE):
                incomplete.set()
            if getattr(record, "classification", None) == "IMPLEMENTATION_IDENTITY_FAIL":
                failed.set()
            if type(record) is records.PairComparisonRecord and record.p3_status is records.P3Status.FAIL:
                failed.set()
            self._put(("record", (key, record)))
        try:
            observed = store.scan_stream(root, self.seal.name, visit=visit)
            self._put(("end", observed))
        except _Cancelled:
            pass
        except Exception:
            try:
                self._put(("error", None))
            except _Cancelled:
                pass

    def peek(self):
        if self.current is not None or self.done:
            return self.current
        while True:
            _need(time.monotonic_ns() < self.deadline, "QUALIFICATION_TIMEOUT")
            try:
                kind, value = self.queue.get(timeout=0.02)
                break
            except Empty:
                if not self.thread.is_alive():
                    # Producer may have queued EOF between get's timeout and
                    # this liveness read. Drain that message before diagnosing.
                    try:
                        kind, value = self.queue.get_nowait()
                        break
                    except Empty:
                        raise QualificationError("DURABLE_READBACK_INCOMPLETE") from None
        _need(kind != "error", "DURABLE_READBACK_INTEGRITY_FAIL")
        if kind == "end":
            _need(type(value) is records.StreamDigest and value == self.seal, "DURABLE_SEAL_MISMATCH")
            self.done = True
        else:
            self.current = value
        return self.current

    def pop(self):
        value = self.peek()
        self.current = None
        return value


def _headers(streams, roles, table):
    headers = []
    for role in roles:
        physical = tuple(records.decode(v) for v in streams[role + "_physical_inputs"])
        spans = tuple(records.decode(v) for v in streams[role + "_decision_spans"])
        decisions = tuple(records.decode(v) for v in streams[role + "_decisions"])
        checkpoints = tuple(records.decode(v) for v in streams[role + "_guess_checkpoints"])
        _need(bool(physical) and physical[-1].after_status in (records.Status.WON, records.Status.LOST),
              "MISSING_TERMINAL_EVIDENCE")
        for item in physical:
            _need(item.input_us == action_cost(table, item.cursor_before, item.target),
                  "MODEL_C_IDENTITY_MISMATCH")
        guesses = tuple(item for item in decisions if item.category == "EXACT_MINIMUM_RISK_GUESS"
                        or item.semantic_kind == "probability_guess")
        _need(len(guesses) == len(checkpoints) and all(a.target == b.chosen_target for a, b in zip(guesses, checkpoints)),
              "GUESS_CHECKPOINT_COVERAGE_MISMATCH")
        _need(all(span.duration_ns is not None for span in spans), "MISSING_COMPARABLE_COMPUTE")
        headers.append(execution.ProjectionHeader(role,
            "WIN" if physical[-1].after_status is records.Status.WON else "LOSS",
            physical[-1].cumulative_us, sum(span.duration_ns for span in spans), True, True, True, ()))
    return tuple(headers)


def _required(work, kind):
    roles = {execution.WorkerKind.PRIMARY: ("control", "kp0"),
             execution.WorkerKind.DETERMINISM: execution._ROLES,
             execution.WorkerKind.K_CONTROL: ()}[kind]
    names = {"boards", "runtime"}
    names.update(role + "_" + component for role in roles for component in ("arms",) + execution._COMPONENTS)
    if kind is execution.WorkerKind.PRIMARY:
        names.update(("pairs", "certificate_audits", "oracle_b_audits", "oracle_b_coverage", "evaluators"))
        if work.k_control_selected or work.determinism_selected:
            names.add("control_maintenance")
    elif kind is execution.WorkerKind.DETERMINISM:
        names.update(("control_maintenance", "repeat_control_maintenance", "repeat_certificate_audits",
            "repeat_oracle_b_audits", "repeat_oracle_b_coverage", "repeat_evaluators",
            "control_determinism", "kp0_determinism"))
    else:
        names.update(("control_maintenance", "kcontrol_arms", "kcontrol_maintenance"))
    return roles, names


def _reconstruct(work, kind, values, table, envelope):
    roles, names = _required(work, kind)
    _need(all(name in names for name, data in values.items() if data), "UNEXPECTED_UNIT_STREAM")
    streams = {name: values.get(name, ()) for name in names}
    bundle = execution.WorkerBundle(work.position, kind, records.encode(work.board), work.arm_order,
        tuple((name, streams[name]) for name in execution.STREAM_NAMES if name in streams),
        _headers(streams, roles, table), records.AuditStatus.PASS, ())
    execution.revalidate_bundle(bundle, work, kind, max_payload_bytes=envelope.max_payload_bytes)
    for role in roles:
        _reconcile_public_children(execution.restore_projection(bundle, role), streams, role)
    return bundle


def _cells(values):
    return tuple(sorted(values, key=lambda cell: (cell[1], cell[0])))


def _reconcile_public_children(projection, streams, role):
    """Join retained children to the public preinput prefix, without inference.

    Truth is never loaded. The evaluator's public asserted-coordinate coverage
    is checked, not repeated or promoted into a proof. Oracle premises/digests
    are joined without running its exact kernel or accepting a new certificate.
    """
    board = projection.arm.board
    state = [[int(CellState.HIDDEN)] * board.width for _ in range(board.height)]
    is_k = projection.arm.arm is records.Arm.K_P0
    prefix = "repeat_" if role.startswith("repeat_") else ""
    has_k_children = is_k and prefix + "evaluators" in streams
    certificates = tuple(records.decode(v) for v in streams.get(prefix + "certificate_audits", ())) if is_k else ()
    oracle_checks = tuple(records.decode(v) for v in streams.get(prefix + "oracle_b_audits", ())) if is_k else ()
    proof_digests, guess_index = [], 0
    targets = {category: set() for category in records.AssertionCategory}
    for physical, decision, effect in zip(projection.physical_inputs, projection.decisions, projection.public_effects):
        ordinal = physical.action_ordinal
        observation = tuple(tuple(row) for row in state)
        flags = {(x, y) for y, row in enumerate(state) for x, value in enumerate(row) if value == CellState.FLAGGED}
        hidden = {(x, y) for y, row in enumerate(state) for x, value in enumerate(row) if value == CellState.HIDDEN}
        if decision.category == "EXACT_MINIMUM_RISK_GUESS" or decision.semantic_kind == "probability_guess":
            checkpoint = projection.guess_checkpoints[guess_index]
            guess_index += 1
            fixed = flags | set(decision.logical_mines_after)
            clues = tuple(((x, y), value) for y, row in enumerate(state) for x, value in enumerate(row) if 0 <= value <= 8)
            _need((checkpoint.public_clues, checkpoint.physical_p, checkpoint.effective_p_union_m,
                   checkpoint.unresolved, checkpoint.mine_budget) ==
                  (clues, _cells(flags), _cells(fixed), _cells(hidden - fixed), board.mines - len(fixed)),
                  "CHECKPOINT_PUBLIC_PREMISE_MISMATCH")
        if has_k_children:
            current = tuple(v for v in certificates if v.action_ordinal == ordinal)
            local_m = set(decision.logical_mines_before)
            for phase, source in (("D", records.AcquisitionSource.LOCAL), ("E", records.AcquisitionSource.EXACT_GLOBAL)):
                batch_m = _cells(local_m)
                for certificate in current:
                    if certificate.acquisition.source is not source:
                        continue
                    premises = dict(certificate.certificate_premises)
                    _need(premises["observation"] == observation and premises["num_mines"] == board.mines
                          and premises["retained_mines"] == batch_m
                          and certificate.owned_m_before == batch_m
                          and certificate.owned_m_after == _cells(set(batch_m) | {certificate.acquisition.cell})
                          and certificate.prior_certificate_sha256s == tuple(proof_digests),
                          "CERTIFICATE_PUBLIC_PREMISE_MISMATCH")
                    proof_digests.append(certificate.acquisition.certificate_sha256)
                    local_m.add(certificate.acquisition.cell)
                for check in oracle_checks:
                    if (check.action_ordinal, check.phase) != (ordinal, phase):
                        continue
                    logical = _cells(local_m)
                    materialized = tuple(tuple(int(CellState.FLAGGED)
                        if value == CellState.HIDDEN and (x, y) in local_m else value
                        for x, value in enumerate(row)) for y, row in enumerate(observation))
                    _need(check.public_observation == observation and check.logical_mines == logical
                          and check.prior_certificate_sha256s == tuple(proof_digests)
                          and check.expected.materialized_observation == materialized
                          and check.actual is not None and check.actual.materialized_observation == materialized
                          and check.input_digest == oracles.oracle_b_input_digest(observation, board.mines, frozenset(logical)),
                          "ORACLE_PUBLIC_PREMISE_MISMATCH")
            targets[records.AssertionCategory.LOGICAL_M].update(decision.logical_mines_after)
            if decision.category not in ("POLICY_INITIAL_OPEN", "EXACT_MINIMUM_RISK_GUESS"):
                if physical.action is records.Action.OPEN:
                    targets[records.AssertionCategory.CERTAINTY_OPEN].add(physical.target)
                elif physical.action is records.Action.CHORD:
                    targets[records.AssertionCategory.CERTAINTY_CHORD_OPENED].update(
                        change.cell for change in effect.changes
                        if change.before == "HIDDEN" and change.after.startswith("CLUE_"))
                    targets[records.AssertionCategory.CERTAINTY_CHORD_OPENED].update(
                        change.cell for terminal in projection.terminal_effects if terminal.action_ordinal == ordinal
                        for change in terminal.changes if change.presentation is records.TerminalPresentation.EXPLODED_MINE)
        for change in effect.changes:
            x, y = change.cell
            state[y][x] = (int(CellState.HIDDEN) if change.after == "HIDDEN" else
                           int(CellState.FLAGGED) if change.after == "FLAGGED" else int(change.after[5:]))
    if has_k_children:
        for data in streams[prefix + "evaluators"]:
            child = records.decode(data)
            expected = _cells(targets[child.assertion])
            _need(child.targets == expected and (child.status is records.EvaluationStatus.NOT_EVALUATED) == (not expected),
                  "EVALUATOR_ASSERTION_PREMISE_MISMATCH")


def _receipt_plan(plan, result):
    _need(type(result) is operational.CoordinatorResult and type(result.receipts) is tuple
          and type(result.streams) is tuple and type(result.status) is records.AuditStatus,
          "COORDINATOR_RESULT_REQUIRED")
    expected = tuple((work.position, kind) for work in plan for kind in operational._kinds(work))
    for receipt in result.receipts:
        _need(type(receipt) is operational.UnitReceipt, "EXACT_UNIT_RECEIPT_REQUIRED")
        operational.UnitReceipt.__post_init__(receipt)
        _need(receipt.status is not records.AuditStatus.PASS or receipt.exit_code == 0, "UNIT_EXIT_CODE_MISMATCH")
    _need(tuple((v.position, v.kind) for v in result.receipts) == expected, "SCHEDULED_UNIT_COVERAGE_MISMATCH")
    _need(type(result.durable_units) is int and result.durable_units == len(expected), "DURABLE_UNIT_COUNT_MISMATCH")
    _need(type(result.durable_primary_boards) is int and 0 <= result.durable_primary_boards <= len(plan),
          "DURABLE_PRIMARY_COUNT_MISMATCH")
    _need(type(result.archive_bytes) is int and result.archive_bytes == sum(v.byte_length for v in result.streams),
          "DURABLE_BYTE_COUNT_MISMATCH")
    _need(type(result.reason_codes) is tuple and all(type(v) is str and v and len(v) <= 80
          and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in v) for v in result.reason_codes),
          "STATIC_COORDINATOR_REASONS_REQUIRED")


def _events(lane, result, admitted_positions):
    receipts = result.receipts
    scheduled = {operational._unit_id(v.position, v.kind) for v in receipts}
    started, terminals, progress = set(), 0, 0
    ordinal, elapsed, last, first = 0, -1, None, None
    pending_progress, coordinator_ends = False, 0
    while lane.peek() is not None:
        key, event = lane.pop()
        _need(type(event) is records.OperationEventRecord and key == (ordinal,)
              and event.ordinal == ordinal and event.elapsed_ns >= elapsed, "OPERATION_KEY_ORDER_MISMATCH")
        if first is None:
            first = event
        ordinal, elapsed, last = ordinal + 1, event.elapsed_ns, event
        unit = event.unit_id
        _need(event.phase is records.Phase.EXECUTION or unit.startswith("coordinator:"),
              "OPERATION_PHASE_MISMATCH")
        _need(not pending_progress or unit.startswith("durable_primary_count:"),
              "MISSING_CHECKPOINT_PROGRESS_EVENT")
        if unit in scheduled:
            _need(event.event_kind is records.EventKind.START and unit not in started,
                  "DUPLICATE_OR_INVALID_UNIT_START")
            _need(event.status in (records.OperationStatus.RUNNING, records.OperationStatus.INCOMPLETE),
                  "INVALID_UNIT_START_STATUS")
            started.add(unit)
        elif unit.startswith("durable_primary_count:"):
            progress += 1
            _need(pending_progress and unit == "durable_primary_count:" + str(progress)
                  and event.event_kind is records.EventKind.PROGRESS
                  and event.status is records.OperationStatus.RUNNING,
                  "DURABLE_PROGRESS_MISMATCH")
            pending_progress = False
        elif unit == "coordinator" or unit.startswith("coordinator:"):
            _need(unit in {"coordinator", "coordinator:ADMISSION_END"}
                  or unit[len("coordinator:"):] in result.reason_codes, "UNKNOWN_COORDINATOR_EVENT")
            if event.event_kind is records.EventKind.START:
                _need(ordinal == 1 and event.status is records.OperationStatus.RUNNING,
                      "DUPLICATE_COORDINATOR_START")
            elif event.event_kind is records.EventKind.END:
                coordinator_ends += 1
                _need(coordinator_ends == 1 and terminals == len(receipts), "COORDINATOR_END_MISMATCH")
                _need(event.status in (records.OperationStatus.COMPLETED, records.OperationStatus.FAILED,
                                      records.OperationStatus.INCOMPLETE), "COORDINATOR_TERMINAL_STATUS")
            else:
                _need(event.event_kind is records.EventKind.ERROR and unit.startswith("coordinator:")
                      and event.status is records.OperationStatus.INCOMPLETE, "COORDINATOR_EVENT_MISMATCH")
        else:
            _need(terminals < len(receipts), "EXTRA_TERMINAL_EVENT")
            receipt = receipts[terminals]
            expected = operational._unit_id(receipt.position, receipt.kind)
            state = {records.AuditStatus.PASS: records.OperationStatus.COMPLETED,
                     records.AuditStatus.FAIL: records.OperationStatus.FAILED,
                     records.AuditStatus.INCOMPLETE: records.OperationStatus.INCOMPLETE}[receipt.status]
            _need(unit == expected + ":" + receipt.reason and expected in started
                  and event.status is state and event.event_kind is (
                      records.EventKind.END if receipt.status is records.AuditStatus.PASS else records.EventKind.ERROR),
                  "TERMINAL_RECEIPT_EVENT_MISMATCH")
            terminals += 1
            pending_progress = (receipt.kind is execution.WorkerKind.PRIMARY
                                and receipt.position in admitted_positions)
    _need(first is not None and first.unit_id == "coordinator" and first.event_kind is records.EventKind.START
          and last.unit_id in ("coordinator", "coordinator:ADMISSION_END") and last.event_kind is records.EventKind.END,
          "COORDINATOR_EVENT_BOUNDARY_MISMATCH")
    _need(started == scheduled and terminals == len(receipts)
          and progress == result.durable_primary_boards and not pending_progress
          and coordinator_ends == 1, "OPERATION_COVERAGE_MISMATCH")


def qualify(root, plan, coordinator_result, identity_seal, envelope):
    """Read-only synthetic integration validation; no execution/admission flags.

    Incomplete original headers are deliberately not invented from partial
    streams. Their receipts remain nonpassing, but raw FAIL evidence still wins.
    Only completely reconstructed primary rows can reach existing I3 analysis.
    """
    failed, incomplete, cancel = threading.Event(), threading.Event(), threading.Event()
    lanes, rows, verified, reasons = {}, [], (), []
    if type(coordinator_result) is operational.CoordinatorResult:
        if coordinator_result.status is records.AuditStatus.FAIL:
            failed.set()
        elif coordinator_result.status is records.AuditStatus.INCOMPLETE:
            incomplete.set()
        if type(coordinator_result.receipts) is tuple:
            for receipt in coordinator_result.receipts:
                if type(receipt) is operational.UnitReceipt:
                    if receipt.status is records.AuditStatus.FAIL:
                        failed.set()
                    elif receipt.status is records.AuditStatus.INCOMPLETE:
                        incomplete.set()
    try:
        _plan(plan)
        operational.OperatingEnvelope.__post_init__(envelope)
        _need(type(envelope) is operational.OperatingEnvelope, "OPERATING_ENVELOPE_REQUIRED")
        _receipt_plan(plan, coordinator_result)
        if coordinator_result.reason_codes:
            incomplete.set()
        seals = coordinator_result.streams + (identity_seal,)
        names = _STREAMS + (IDENTITY_STREAM,)
        _need({path.name for path in Path(root).iterdir()} == {name + ".jsonl" for name in names},
              "DURABLE_STREAM_DIRECTORY_COVERAGE_MISMATCH")
        _need(len(seals) == len(names), "STREAM_SEAL_COVERAGE_MISMATCH")
        for seal in seals:
            _need(type(seal) is records.StreamDigest, "EXACT_STREAM_SEAL_REQUIRED")
            records.StreamDigest.__post_init__(seal)
        _need(tuple(v.name for v in seals) == names, "STREAM_SEAL_IDENTITY_MISMATCH")
        expected_identity = _identity_records(plan)
        deadline = time.monotonic_ns() + envelope.validation_wall_ms * 1_000_000
        for seal in seals:
            lanes[seal.name] = _Lane(root, seal, cancel, deadline, failed, incomplete)
        for ordinal, expected in enumerate(expected_identity):
            _need(lanes[IDENTITY_STREAM].pop() == ((ordinal,), expected), "DURABLE_IDENTITY_MISMATCH")
        _need(lanes[IDENTITY_STREAM].peek() is None, "EXTRA_IDENTITY_RECORD")
        table, receipt_index, admitted = load_timing_table(), 0, set()
        for work in plan:
            primary = None
            for kind in operational._kinds(work):
                rank, values, payload_size = operational._kind_rank(kind), {}, 0
                for name in execution.STREAM_NAMES:
                    data, local = [], 0
                    lane = lanes[name]
                    while lane.peek() is not None:
                        key, record = lane.peek()
                        _need(len(key) == 3 and key[:2] >= (work.position, rank), "UNIT_KEY_ORDER_MISMATCH")
                        if key[:2] != (work.position, rank):
                            break
                        _need(key == (work.position, rank, local) and type(record) is execution._family(name),
                              "UNIT_KEY_OR_RECORD_FAMILY_MISMATCH")
                        encoded = records.encode(record)
                        payload_size += len(encoded)
                        _need(payload_size <= envelope.max_payload_bytes, "QUALIFICATION_UNIT_PAYLOAD_CAP")
                        data.append(encoded)
                        lane.pop()
                        local += 1
                    values[name] = tuple(data)
                receipt = coordinator_result.receipts[receipt_index]
                receipt_index += 1
                if kind is execution.WorkerKind.PRIMARY and values["boards"]:
                    admitted.add(work.position)
                if receipt.status is not records.AuditStatus.PASS:
                    continue
                bundle = _reconstruct(work, kind, values, table, envelope)
                if kind is execution.WorkerKind.PRIMARY:
                    primary = bundle
                    control, kp0 = (execution.restore_projection(bundle, role) for role in ("control", "kp0"))
                    pair = game.pair_projections(control, kp0).pair
                    rows.append(analysis.BoardAnalysisRow(work.position, pair, control.total_model_us,
                                kp0.total_model_us, control.comparable_compute_ns, kp0.comparable_compute_ns))
                else:
                    _need(primary is not None, "MISSING_PRIMARY_PREMISE")
                    operational._bind_prior_bundle(bundle, execution.encode_bundle(primary), work, kind, envelope)
        for name in execution.STREAM_NAMES:
            _need(lanes[name].peek() is None, "UNSCHEDULED_OR_EXTRA_UNIT")
        _need(len(admitted) == coordinator_result.durable_primary_boards, "ADMITTED_PRIMARY_COUNT_MISMATCH")
        _events(lanes["operations"], coordinator_result, admitted)
        ordinal = 0
        scheduled = {operational._unit_id(v.position, v.kind) for v in coordinator_result.receipts}
        sample_counts = dict.fromkeys(scheduled, 0)
        while lanes["resources"].peek() is not None:
            key, value = lanes["resources"].pop()
            _need(type(value) is records.ResourceSampleRecord and key == (ordinal,)
                  and value.unit_id in scheduled and value.method is records.MemoryMethod.PRIVATE_BYTES
                  and value.process_role is records.ProcessRole.COMBINED,
                  "RESOURCE_IDENTITY_MISMATCH")
            sample_counts[value.unit_id] += 1
            _need(sample_counts[value.unit_id] <= 3, "EXTRA_RESOURCE_SAMPLE")
            # worker_bytes is the SUM of concurrently active Jobs, not one Job.
            # Individual worker caps remain the accepted I6 containment boundary.
            if (value.combined_bytes > envelope.memory_cap_bytes
                    or value.coordinator_bytes > envelope.coordinator_memory_cap_bytes):
                incomplete.set()
            ordinal += 1
        _need(all(sample_counts[operational._unit_id(v.position, v.kind)] > 0
                  for v in coordinator_result.receipts if v.status is records.AuditStatus.PASS),
              "MISSING_RESOURCE_EVIDENCE")
        _need(_identity_records(plan) == expected_identity, "SOURCE_CHANGED_DURING_QUALIFICATION")
        _need(time.monotonic_ns() < deadline, "QUALIFICATION_TIMEOUT")
        verified = seals
    except QualificationError as error:
        reasons.append(str(error))
        incomplete.set()
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, subprocess.SubprocessError):
        reasons.append("INTEGRATION_EVIDENCE_INVALID")
        incomplete.set()
    finally:
        cancel.set()
        for lane in lanes.values():
            lane.thread.join()
    status = records.AuditStatus.FAIL if failed.is_set() else (
        records.AuditStatus.INCOMPLETE if incomplete.is_set() else records.AuditStatus.PASS)
    if status is not records.AuditStatus.PASS:
        reasons.append("PRIOR_OR_DURABLE_FAILURE" if status is records.AuditStatus.FAIL else "REQUIRED_EVIDENCE_INCOMPLETE")
        return QualificationResult(status, tuple(dict.fromkeys(reasons)), (), verified)
    # Reuse I3 exactly once. No supplied research gate judgments, overall verdict,
    # E3 trigger, Actual-E2 identity, readiness decision or COMPLETE publication.
    digest = identity.corpus_digest(plan[0].protocol_seed, len(plan), tuple(v.board.game_index for v in plan))
    try:
        started = time.monotonic_ns()
        result = analysis.analyze_effectiveness(tuple(rows), protocol_seed=plan[0].protocol_seed,
            corpus_digest=digest, concurrency=envelope.concurrency, gate_statuses=None, context=(_SCOPE,))
        _need(time.monotonic_ns() - started < envelope.aggregation_wall_ms * 1_000_000,
              "INTEGRATION_AGGREGATION_TIMEOUT")
        started = time.monotonic_ns()
        analysis_json, report_html = report.render_analysis_json(result), report.render_report_html(result)
        _need(time.monotonic_ns() - started < envelope.report_wall_ms * 1_000_000, "INTEGRATION_REPORT_TIMEOUT")
        _need(_identity_records(plan) == expected_identity, "SOURCE_CHANGED_DURING_QUALIFICATION")
        return QualificationResult(status, (), tuple(rows), verified, analysis_json, report_html)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, subprocess.SubprocessError):
        return QualificationResult(records.AuditStatus.INCOMPLETE, ("INTEGRATION_POSTPROCESSING_INCOMPLETE",), (), verified)
