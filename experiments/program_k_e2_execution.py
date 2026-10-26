"""I6 bounded worker composition over accepted runners and canonical I1 evidence.

No board, file, timer or process is touched at import. Production generation and
answer ownership stay inside the invoked worker; the public boundary exports
explicit canonical I1 bytes and a small closed transport header only. This module
neither selects Actual-E2 N nor authorizes an execution or a research verdict.
"""

from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
import inspect
import json
import os
import platform
from time import perf_counter_ns

import benchmark_board
from core_engine import CellState, GameStatus, MinesweeperEngine
import stage3_planner
from stage3_physical import action_cost, load_timing_table, validate_timing_table
from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records
from experiments import program_k_e2_physical as physical
from experiments import program_k_e2_game as game
from experiments import program_k_e2_audit as audit
from experiments import program_k_e2_evaluator as evaluator
from experiments import program_k_runner as runner
from experiments import program_k_capability as capability
from experiments import program_k_policy as policy
from experiments import program_k_evidence as evidence


class E2ExecutionError(ValueError):
    """A static public diagnosis; never an interpolated private exception."""


class E2EvidenceIncomplete(E2ExecutionError):
    """Required public evidence is unavailable, without a semantic-failure diagnosis."""


class E2IdentityMismatch(E2ExecutionError):
    """Implementation/runtime identity differs; this is not a research verdict."""


class WorkerKind(Enum):
    PRIMARY = "PRIMARY"
    DETERMINISM = "DETERMINISM"
    K_CONTROL = "K_CONTROL"


_COMPONENTS = ("physical_inputs", "public_effects", "terminal_effects", "decision_spans",
               "decisions", "guess_checkpoints", "flag_provenance", "acquisitions")
_ROLES = ("control", "kp0", "repeat_control", "repeat_kp0")
STREAM_NAMES = ("boards", "runtime") + tuple(
    role + "_" + component for role in _ROLES for component in ("arms",) + _COMPONENTS
) + ("control_maintenance", "repeat_control_maintenance", "pairs", "certificate_audits",
     "oracle_b_audits", "oracle_b_coverage", "evaluators", "repeat_certificate_audits", "repeat_oracle_b_audits",
     "repeat_oracle_b_coverage", "repeat_evaluators", "control_determinism", "kp0_determinism", "kcontrol_arms",
     "kcontrol_maintenance")
_TIMINGS = ("v1_plan_position_ns", "k_analysis_planning_ns", "k_execution_validation_ns",
            "v1_execution_validation_ns", "shadow_ns", "evidence_ns", "comparison_ns",
            "oracle_ns", "evaluator_ns")
_HEADER_FIELDS = ("role", "outcome", "total_model_us", "comparable_compute_ns",
                  "effect_evidence_complete", "p3_evidence_complete", "g5_evidence_complete", "diagnostics")
_BUNDLE_KEYS = {"version", "position", "kind", "board", "arm_order", "streams", "headers", "status", "reasons"}
_REASONS = frozenset(("PUBLIC_AUDIT_FAIL", "PUBLIC_AUDIT_INCOMPLETE", "PRIVATE_ASSERTION_FALSIFIED",
    "P3_IMPLEMENTATION_IDENTITY_FAIL", "P3_EVIDENCE_INCOMPLETE", "DETERMINISM_OR_PRIOR_AUDIT_FAIL",
    "DETERMINISM_OR_PRIOR_EVIDENCE_INCOMPLETE", "KCONTROL_IMPLEMENTATION_IDENTITY_FAIL",
    "SHADOW_IMPLEMENTATION_IDENTITY_FAIL", "KCONTROL_SHADOW_EVIDENCE_INCOMPLETE",
    "KCONTROL_REQUIRED_EVIDENCE_INCOMPLETE", "PRIMARY_COMPUTE_EVIDENCE_INCOMPLETE",
    "G5_EVIDENCE_INCOMPLETE"))


def _need(condition, reason):
    if not condition:
        if reason == "IMPLEMENTATION_IDENTITY_FAIL":
            raise E2IdentityMismatch(reason) from None
        raise E2ExecutionError(reason) from None


def _uint(value, *, positive=False):
    _need(type(value) is int and (1 if positive else 0) <= value <= identity.UINT64_MAX,
          "EXACT_UNSIGNED_INTEGER_REQUIRED")


def _text(value):
    _need(type(value) is str and bool(value) and all(32 <= ord(c) < 127 for c in value),
          "PUBLIC_ASCII_IDENTIFIER_REQUIRED")


def _cells(value):
    return tuple(sorted(value, key=lambda cell: (cell[1], cell[0])))


def _record(value, cls):
    _need(type(value) is cls, "CANONICAL_RECORD_TYPE_REQUIRED")
    cls.__post_init__(value)


@dataclass(frozen=True, slots=True)
class PriorBindingTimingFact:
    """Optional operational observation, never a persisted evidence record.

    The interval contains the complete initial PRIMARY prior revalidation in
    the selected downstream worker. Decode/transport and parent binding remain
    owned by the operational caller. The callback occurs before target setup
    and solver execution, so a caller can acknowledge a transport boundary
    without reclassifying ordinary K-CONTROL work as Oracle work.
    """

    work_position: int
    kind: WorkerKind
    start_ns: int
    end_ns: int

    def __post_init__(self):
        _uint(self.work_position)
        _need(type(self.kind) is WorkerKind and self.kind in
              (WorkerKind.K_CONTROL, WorkerKind.DETERMINISM), "DOWNSTREAM_BINDING_KIND_REQUIRED")
        _uint(self.start_ns)
        _uint(self.end_ns)
        _need(self.start_ns <= self.end_ns, "PRIOR_BINDING_INTERVAL_ORDER")

    @property
    def wall_ns(self):
        return self.end_ns - self.start_ns


def _revalidate_primary_prior(work, first_primary_bundle, kind, observer):
    if observer is None:
        revalidate_bundle(first_primary_bundle, work, WorkerKind.PRIMARY)
        return
    _need(callable(observer), "PRIOR_BINDING_OBSERVER_REQUIRED")
    started = perf_counter_ns()
    revalidate_bundle(first_primary_bundle, work, WorkerKind.PRIMARY)
    ended = perf_counter_ns()
    observer(PriorBindingTimingFact(work.position, kind, started, ended))


@dataclass(frozen=True, slots=True)
class BoardWork:
    position: int
    board: records.BoardIdentity
    protocol_seed: bytes
    run_id: str
    oracle_b_selected: bool
    determinism_selected: bool
    k_control_selected: bool
    runtime: records.RuntimeIdentity | None = None

    def __post_init__(self):
        _uint(self.position)
        _record(self.board, records.BoardIdentity)
        _need(type(self.protocol_seed) is bytes and len(self.protocol_seed) == 32, "PROTOCOL_SEED_REQUIRED")
        _text(self.run_id)
        _need(all(type(value) is bool for value in (self.oracle_b_selected, self.determinism_selected,
                                                   self.k_control_selected)), "EXACT_SELECTION_FLAGS_REQUIRED")
        if self.runtime is not None:
            _record(self.runtime, records.RuntimeIdentity)

    @property
    def unit_id(self):
        return "e2-board-" + str(self.position)

    @property
    def arm_order(self):
        return identity.arm_order(self.protocol_seed, self.board.game_index)


def make_work_plan(boards, *, protocol_seed, run_id, runtime=None):
    """Freeze caller-supplied positions; never choose N, indices or replacements."""
    _need(type(boards) is tuple and bool(boards), "FINITE_NONEMPTY_BOARD_TUPLE_REQUIRED")
    for board in boards:
        _record(board, records.BoardIdentity)
    indices = tuple(board.game_index for board in boards)
    digest = identity.corpus_digest(protocol_seed, len(boards), indices)
    selections = tuple(frozenset(identity.select_subset_positions(label, protocol_seed, digest,
                                                                  len(boards), min(len(boards), cap)))
                       for label, cap in ((identity.ORACLE_B_LABEL, identity.ORACLE_B_CAP),
                                          (identity.DETERMINISM_LABEL, identity.DETERMINISM_CAP),
                                          (identity.KCONTROL_LABEL, identity.KCONTROL_CAP)))
    return tuple(BoardWork(index, board, protocol_seed, run_id,
                           *(index in selection for selection in selections), runtime)
                 for index, board in enumerate(boards))


def revalidate_work_plan(plan):
    _need(type(plan) is tuple and bool(plan), "FINITE_WORK_PLAN_REQUIRED")
    for work in plan:
        _record(work, BoardWork)
    _need(tuple(work.position for work in plan) == tuple(range(len(plan))), "WORK_POSITION_COVERAGE_MISMATCH")
    first = plan[0]
    _need(all((work.protocol_seed, work.run_id, work.runtime) ==
              (first.protocol_seed, first.run_id, first.runtime) for work in plan), "WORK_PLAN_IDENTITY_MISMATCH")
    expected = make_work_plan(tuple(work.board for work in plan), protocol_seed=first.protocol_seed,
                              run_id=first.run_id, runtime=first.runtime)
    _need(expected == plan, "PROSPECTIVE_SUBSET_MEMBERSHIP_MISMATCH")
    return plan


@dataclass(frozen=True, slots=True)
class ProjectionHeader:
    role: str
    outcome: str
    total_model_us: int
    comparable_compute_ns: int | None
    effect_evidence_complete: bool
    p3_evidence_complete: bool
    g5_evidence_complete: bool
    diagnostics: tuple

    def __post_init__(self):
        _need(type(self.role) is str and self.role in _ROLES, "UNKNOWN_PROJECTION_ROLE")
        _need(type(self.outcome) is str and self.outcome in records.Outcome.__members__, "UNKNOWN_OUTCOME")
        _uint(self.total_model_us)
        if self.comparable_compute_ns is not None:
            _uint(self.comparable_compute_ns)
        _need(all(type(value) is bool for value in (self.effect_evidence_complete,
                   self.p3_evidence_complete, self.g5_evidence_complete)), "EXACT_COMPLETENESS_REQUIRED")
        _need(type(self.diagnostics) is tuple, "IMMUTABLE_DIAGNOSTICS_REQUIRED")
        for reason in self.diagnostics:
            _text(reason)


@dataclass(frozen=True, slots=True)
class WorkerBundle:
    work_position: int
    kind: WorkerKind
    board: bytes
    arm_order: identity.ArmOrder
    streams: tuple
    projection_headers: tuple
    status: records.AuditStatus
    reason_codes: tuple

    def __post_init__(self):
        _uint(self.work_position)
        _need(type(self.kind) is WorkerKind and type(self.arm_order) is identity.ArmOrder,
              "EXACT_WORKER_KIND_ORDER_REQUIRED")
        _need(type(self.board) is bytes and type(self.streams) is tuple
              and type(self.projection_headers) is tuple and type(self.reason_codes) is tuple,
              "IMMUTABLE_WORKER_BOUNDARY_REQUIRED")
        _need(type(self.status) is records.AuditStatus, "LOCAL_AUDIT_STATUS_REQUIRED")
        for reason in self.reason_codes:
            _need(type(reason) is str and reason in _REASONS, "CLOSED_PUBLIC_DIAGNOSIS_REQUIRED")
        for header in self.projection_headers:
            _record(header, ProjectionHeader)
        names = []
        for stream in self.streams:
            _need(type(stream) is tuple and len(stream) == 2 and type(stream[0]) is str and stream[0] in STREAM_NAMES
                  and type(stream[1]) is tuple and all(type(data) is bytes for data in stream[1]),
                  "UNKNOWN_OR_MUTABLE_RECORD_STREAM")
            names.append(stream[0])
        _need(names == sorted(set(names), key=STREAM_NAMES.index), "STREAM_ORDER_OR_DUPLICATE")
        _need(self.status is records.AuditStatus.PASS or bool(self.reason_codes), "NONPASS_REQUIRES_DIAGNOSIS")


def _json(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def encode_bundle(bundle):
    _record(bundle, WorkerBundle)
    return _json({"version": 1, "position": bundle.work_position, "kind": bundle.kind.value,
                  "board": bundle.board.decode("ascii"), "arm_order": bundle.arm_order.value,
                  "streams": tuple((name, tuple(data.decode("ascii") for data in values))
                                   for name, values in bundle.streams),
                  "headers": tuple({name: getattr(header, name) for name in _HEADER_FIELDS}
                                   for header in bundle.projection_headers),
                  "status": bundle.status.value, "reasons": bundle.reason_codes})


def _unique_object(pairs):
    node = dict(pairs)
    _need(len(node) == len(pairs), "DUPLICATE_IPC_FIELD")
    return node


def decode_bundle(data):
    _need(type(data) is bytes, "CANONICAL_IPC_BYTES_REQUIRED")
    try:
        node = json.loads(data.decode("ascii"), object_pairs_hook=_unique_object,
                          parse_float=lambda _: (_ for _ in ()).throw(E2ExecutionError("IPC_FLOAT_FORBIDDEN")),
                          parse_constant=lambda _: (_ for _ in ()).throw(E2ExecutionError("IPC_NONFINITE_FORBIDDEN")))
        _need(type(node) is dict and set(node) == _BUNDLE_KEYS and type(node["version"]) is int
              and node["version"] == 1, "IPC_HEADER_SCHEMA_MISMATCH")
        _need(type(node["streams"]) is list and type(node["headers"]) is list
              and type(node["reasons"]) is list, "IPC_COLLECTION_SHAPE")
        headers = []
        for header in node["headers"]:
            _need(type(header) is dict and set(header) == set(_HEADER_FIELDS)
                  and type(header["diagnostics"]) is list, "IPC_PROJECTION_HEADER_SHAPE")
            header["diagnostics"] = tuple(header["diagnostics"])
            headers.append(ProjectionHeader(**header))
        streams = []
        for stream in node["streams"]:
            _need(type(stream) is list and len(stream) == 2 and type(stream[1]) is list,
                  "IPC_STREAM_SHAPE")
            streams.append((stream[0], tuple(value.encode("ascii") for value in stream[1])))
        result = WorkerBundle(node["position"], WorkerKind(node["kind"]), node["board"].encode("ascii"),
                              identity.ArmOrder(node["arm_order"]), tuple(streams), tuple(headers),
                              records.AuditStatus(node["status"]), tuple(node["reasons"]))
        _need(encode_bundle(result) == data, "NONCANONICAL_IPC")
        return result
    except E2ExecutionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise E2ExecutionError("MALFORMED_IPC") from None


WB02_MAGIC = b"PKE2WB02"
WB02_SIZE_BASIS = "PKE2WB02-LSUM-LLEGACY-WIRE-V1"
_WB02_KEYS = frozenset(("container", "codec_profile_sha256", "size_basis", "position", "kind",
    "arm_order", "headers", "status", "reasons", "streams", "logical_bytes", "legacy_bytes",
    "frame_bytes", "wire_bytes"))


def legacy_json_string_size(data):
    """Exact V1 JSON-string size for nonempty printable canonical ASCII bytes.

    This arithmetic is not a canonical-record or semantic validation result.
    """
    _need(type(data) is bytes and bool(data) and all(32 <= b <= 126 for b in data),
          "LEGACY_COUNTER_ASCII_DOMAIN")
    return 2 + len(data) + data.count(b'"') + data.count(b"\\")


def _wire_json_size(node):
    """Count the closed transport metadata without allocating its JSON bytes."""
    if type(node) is str:
        _need(all(32 <= ord(c) <= 126 for c in node), "IPC_METADATA_ASCII_REQUIRED")
        return 2 + len(node) + node.count('"') + node.count("\\")
    if node is None:
        return 4
    if type(node) is bool:
        return 4 if node else 5
    if type(node) is int:
        _uint(node)
        return len(str(node))
    if type(node) in (tuple, list):
        return 2 + max(0, len(node) - 1) + sum(_wire_json_size(v) for v in node)
    _need(type(node) is dict and all(type(k) is str for k in node), "IPC_METADATA_SHAPE")
    return 2 + max(0, len(node) - 1) + sum(
        _wire_json_size(k) + 1 + _wire_json_size(v) for k, v in node.items())


def _transport_headers(bundle):
    return tuple({name: getattr(header, name) for name in _HEADER_FIELDS}
                 for header in bundle.projection_headers)


def _canonical_transport_record(data, cls):
    _need(type(data) is bytes and 0 < len(data) <= physical.MAX_PAYLOAD_BYTES,
          "WORKER_PAYLOAD_CAP")
    value = records.decode(data)
    _need(type(value) is cls and records.encode(value) == data,
          "NONCANONICAL_OR_WRONG_RECORD_FAMILY")


def legacy_bundle_size(bundle):
    """Count the unchanged V1 encoding, including its top-level board copy.

    Record bodies never become outer JSON strings here. Canonical records and
    their closed stream families are still independently checked.
    """
    _record(bundle, WorkerBundle)
    board_size = legacy_json_string_size(bundle.board)
    _canonical_transport_record(bundle.board, records.BoardIdentity)
    node = {"version": 1, "position": bundle.work_position, "kind": bundle.kind.value,
            "board": "", "arm_order": bundle.arm_order.value,
            "streams": tuple((name, ()) for name, _ in bundle.streams),
            "headers": _transport_headers(bundle), "status": bundle.status.value,
            "reasons": bundle.reason_codes}
    total = _wire_json_size(node) + board_size - 2
    for name, values in bundle.streams:
        total += max(0, len(values) - 1)
        for data in values:
            total += legacy_json_string_size(data)
            _canonical_transport_record(data, _family(name))
    return total


def _wb02_limits(codec_profile_sha256, max_payload_bytes, max_metadata_bytes):
    _need(type(codec_profile_sha256) is bytes and len(codec_profile_sha256) == 32,
          "WB02_PROFILE_IDENTITY_REQUIRED")
    for value in (max_payload_bytes, max_metadata_bytes):
        _need(type(value) is int and 0 < value <= physical.MAX_PAYLOAD_BYTES,
              "WB02_EXACT_BOUNDED_LIMIT_REQUIRED")
    _need(max_metadata_bytes <= max_payload_bytes, "WB02_METADATA_CAP_ORDER")


def _wb02_rank(kind):
    # Same durable rank order as operational._kind_rank; no operational import.
    return (WorkerKind.PRIMARY, WorkerKind.DETERMINISM, WorkerKind.K_CONTROL).index(kind)


def encode_bundle_v2(bundle, codec_profile_sha256, *,
                     max_payload_bytes=physical.MAX_PAYLOAD_BYTES,
                     max_metadata_bytes=None):
    """Compose one immutable WB02 message; the live worker path remains V1.

    This primitive checks representation, types and containment. Work-specific
    semantic admission still belongs to each independently validating boundary.
    A supplied profile digest binds context; it makes no qualification claim.
    """
    if max_metadata_bytes is None:
        max_metadata_bytes = max_payload_bytes
    _wb02_limits(codec_profile_sha256, max_payload_bytes, max_metadata_bytes)
    _record(bundle, WorkerBundle)
    logical_size = sum(len(data) for _, values in bundle.streams for data in values)
    _need(logical_size <= max_payload_bytes and len(bundle.board) <= max_payload_bytes,
          "WORKER_PAYLOAD_CAP")
    _need(dict(bundle.streams).get("boards") == (bundle.board,), "BOARD_IDENTITY_STREAM_REQUIRED")
    legacy_size = legacy_bundle_size(bundle)
    _need(legacy_size <= max_payload_bytes, "WORKER_LEGACY_CAP")
    frames, groups, frame_size = [], [], 0
    rank = _wb02_rank(bundle.kind)
    for name, values in bundle.streams:
        context = physical.context_for(name, codec_profile_sha256)
        group_size = 0
        for index, data in enumerate(values):
            frame = physical.encode_frame(data, (bundle.work_position, rank, index), context,
                                          max_payload_bytes=max_payload_bytes)
            group_size += len(frame)
            frame_size += len(frame)
            _need(48 + frame_size <= max_payload_bytes, "WORKER_WIRE_CAP")
            frames.append(frame)
        groups.append((name, len(values), sum(map(len, values)), group_size))
    node = {"container": WB02_MAGIC.decode("ascii"), "codec_profile_sha256": codec_profile_sha256.hex(),
            "size_basis": WB02_SIZE_BASIS, "position": bundle.work_position, "kind": bundle.kind.value,
            "arm_order": bundle.arm_order.value, "headers": _transport_headers(bundle),
            "status": bundle.status.value, "reasons": bundle.reason_codes, "streams": groups,
            "logical_bytes": logical_size, "legacy_bytes": legacy_size,
            "frame_bytes": frame_size, "wire_bytes": 0}
    # At most eight decimal digits occur under the fixed payload cap. Counting
    # reaches a fixed point without allocating a prospective oversized message.
    for _ in range(10):
        metadata_size = _wire_json_size(node)
        wire_size = 48 + metadata_size + frame_size
        if node["wire_bytes"] == wire_size:
            break
        node["wire_bytes"] = wire_size
    else:
        raise E2ExecutionError("WB02_SIZE_FIXED_POINT")
    _need(metadata_size <= max_metadata_bytes, "WB02_METADATA_CAP")
    _need(wire_size <= max_payload_bytes, "WORKER_WIRE_CAP")
    metadata = _json(node)
    _need(len(metadata) == metadata_size, "WB02_METADATA_SIZE_MISMATCH")
    body = b"".join((WB02_MAGIC, metadata_size.to_bytes(8, "big"), metadata, *frames))
    return body + sha256(body).digest()


def decode_bundle_v2(data, codec_profile_sha256, *,
                     max_payload_bytes=physical.MAX_PAYLOAD_BYTES,
                     max_metadata_bytes=None):
    """Decode explicit WB02 bytes, with no V1 guessing or validation bypass.

    The returned frozen WorkerBundle contains exact immutable logical bytes;
    callers must independently perform their own work/semantic validation.
    """
    if max_metadata_bytes is None:
        max_metadata_bytes = max_payload_bytes
    _wb02_limits(codec_profile_sha256, max_payload_bytes, max_metadata_bytes)
    _need(type(data) is bytes and 48 <= len(data) <= max_payload_bytes, "WB02_MESSAGE_CAP_OR_TRUNCATION")
    _need(data[:8] == WB02_MAGIC, "WB02_CONTAINER_IDENTITY")
    metadata_size = int.from_bytes(data[8:16], "big")
    _need(0 < metadata_size <= max_metadata_bytes and metadata_size <= len(data) - 48,
          "WB02_METADATA_CAP_OR_TRUNCATION")
    _need(sha256(memoryview(data)[:-32]).digest() == data[-32:], "WB02_SHA256_MISMATCH")
    metadata = data[16:16 + metadata_size]
    try:
        node = json.loads(metadata.decode("ascii"), object_pairs_hook=_unique_object,
            parse_float=lambda _: (_ for _ in ()).throw(E2ExecutionError("IPC_FLOAT_FORBIDDEN")),
            parse_constant=lambda _: (_ for _ in ()).throw(E2ExecutionError("IPC_NONFINITE_FORBIDDEN")))
        _need(type(node) is dict and set(node) == _WB02_KEYS, "WB02_METADATA_SCHEMA")
        _need(node["container"] == WB02_MAGIC.decode("ascii"), "WB02_CONTAINER_IDENTITY")
        _need(node["codec_profile_sha256"] == codec_profile_sha256.hex(), "WB02_PROFILE_IDENTITY")
        _need(node["size_basis"] == WB02_SIZE_BASIS, "WB02_SIZE_BASIS_IDENTITY")
        _uint(node["position"])
        kind, arm_order = WorkerKind(node["kind"]), identity.ArmOrder(node["arm_order"])
        status = records.AuditStatus(node["status"])
        _need(type(node["headers"]) is list and type(node["reasons"]) is list
              and type(node["streams"]) is list, "WB02_METADATA_COLLECTIONS")
        for key in ("logical_bytes", "legacy_bytes", "frame_bytes", "wire_bytes"):
            _need(type(node[key]) is int and 0 <= node[key] <= max_payload_bytes,
                  "WB02_DECLARED_SIZE_CAP")
        _need(node["wire_bytes"] == len(data) and
              node["frame_bytes"] == len(data) - 48 - metadata_size, "WB02_DECLARED_WIRE_SIZE")
        groups = node["streams"]
        names = []
        for group in groups:
            _need(type(group) is list and len(group) == 4 and type(group[0]) is str
                  and group[0] in STREAM_NAMES, "WB02_STREAM_SCHEMA")
            names.append(group[0])
            for value in group[1:]:
                _need(type(value) is int and 0 <= value <= max_payload_bytes,
                      "WB02_STREAM_SIZE_CAP")
            _need(group[1] <= group[3] // 16 and (group[1] != 0 or group[2:] == [0, 0]),
                  "WB02_STREAM_COUNT_SIZE")
        _need(names == sorted(set(names), key=STREAM_NAMES.index), "STREAM_ORDER_OR_DUPLICATE")
        _need(sum(g[2] for g in groups) == node["logical_bytes"] and
              sum(g[3] for g in groups) == node["frame_bytes"], "WB02_GROUP_TOTALS")
        _need(_json(node) == metadata, "NONCANONICAL_WB02_METADATA")
        headers = []
        for header in node["headers"]:
            _need(type(header) is dict and set(header) == set(_HEADER_FIELDS)
                  and type(header["diagnostics"]) is list, "IPC_PROJECTION_HEADER_SHAPE")
            headers.append(ProjectionHeader(**dict(header, diagnostics=tuple(header["diagnostics"]))))
        offset, streams = 16 + metadata_size, []
        rank = _wb02_rank(kind)
        for name, count, logical_size, group_size in groups:
            group_end, consumed, values = offset + group_size, 0, []
            context = physical.context_for(name, codec_profile_sha256)
            for index in range(count):
                _need(consumed < logical_size, "WB02_LOGICAL_SIZE_MISMATCH")
                frame, offset = physical.decode_frame_from(data, offset, context,
                    expected_key=(node["position"], rank, index),
                    max_payload_bytes=logical_size - consumed)
                _need(offset <= group_end, "WB02_GROUP_BOUNDARY")
                consumed += len(frame.logical_bytes)
                values.append(frame.logical_bytes)
            _need(offset == group_end and consumed == logical_size, "WB02_GROUP_SIZE_MISMATCH")
            streams.append((name, tuple(values)))
        _need(offset == len(data) - 32, "WB02_TRAILING_BYTES")
        boards = dict(streams).get("boards", ())
        _need(len(boards) == 1, "BOARD_IDENTITY_STREAM_REQUIRED")
        bundle = WorkerBundle(node["position"], kind, boards[0], arm_order, tuple(streams),
                              tuple(headers), status, tuple(node["reasons"]))
        _need(legacy_bundle_size(bundle) == node["legacy_bytes"], "WB02_LEGACY_SIZE_MISMATCH")
        return bundle
    except E2ExecutionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise E2ExecutionError("MALFORMED_WB02") from None


def _projection_streams(projection, role):
    game.GameProjection.__post_init__(projection)
    header = ProjectionHeader(role, projection.outcome.value, projection.total_model_us,
                               projection.comparable_compute_ns, projection.effect_evidence_complete,
                               projection.p3_evidence_complete, projection.g5_evidence_complete,
                               projection.diagnostics)
    streams = {role + "_arms": (records.encode(projection.arm),)}
    streams.update((role + "_" + name, tuple(records.encode(item) for item in getattr(projection, name)))
                   for name in _COMPONENTS)
    return header, streams


def restore_projection(bundle, role):
    """Rebuild only the explicit accepted I4 schema from canonical record bytes."""
    headers = tuple(header for header in bundle.projection_headers if header.role == role)
    _need(len(headers) == 1, "PROJECTION_HEADER_COVERAGE_MISMATCH")
    header, streams = headers[0], dict(bundle.streams)
    arms = streams.get(role + "_arms", ())
    _need(len(arms) == 1, "ARM_COVERAGE_MISMATCH")
    components = {name: tuple(records.decode(data) for data in streams[role + "_" + name])
                  for name in _COMPONENTS}
    return game.GameProjection(records.decode(arms[0]), records.Outcome(header.outcome),
                               components["physical_inputs"], components["public_effects"],
                               components["terminal_effects"], components["decision_spans"],
                               components["guess_checkpoints"], components["flag_provenance"],
                               components["acquisitions"], components["decisions"],
                               header.total_model_us, header.comparable_compute_ns,
                               header.effect_evidence_complete, header.p3_evidence_complete,
                               header.g5_evidence_complete, header.diagnostics)


def _family(name):
    suffixes = {"arms": records.ArmIdentity, "physical_inputs": records.PhysicalInputRecord,
                "public_effects": records.PublicEffectRecord, "terminal_effects": records.TerminalEffectRecord,
                "decision_spans": records.DecisionSpanRecord, "decisions": records.ActionDecisionRecord,
                "guess_checkpoints": records.GuessCheckpointRecord,
                "flag_provenance": records.ControlFlagProvenanceRecord, "acquisitions": records.AcquisitionRecord}
    for role in _ROLES:
        if name.startswith(role + "_") and name[len(role) + 1:] in suffixes:
            return suffixes[name[len(role) + 1:]]
    if name in ("control_maintenance", "repeat_control_maintenance", "kcontrol_maintenance"):
        return records.KControlMaintenanceRecord
    return {"boards": records.BoardIdentity, "runtime": records.RuntimeIdentity, "pairs": records.PairComparisonRecord,
            "certificate_audits": records.CertificateAuditRecord, "repeat_certificate_audits": records.CertificateAuditRecord,
            "oracle_b_audits": records.OracleBAuditRecord, "repeat_oracle_b_audits": records.OracleBAuditRecord,
            "oracle_b_coverage": records.OracleBCoverageRecord, "repeat_oracle_b_coverage": records.OracleBCoverageRecord,
            "evaluators": records.EvaluatorRecord, "repeat_evaluators": records.EvaluatorRecord,
            "control_determinism": records.DeterminismAuditRecord, "kp0_determinism": records.DeterminismAuditRecord,
            "kcontrol_arms": records.ArmIdentity}[name]


def revalidate_bundle(bundle, work, kind, max_payload_bytes=67_108_864):
    """Parent admission: types, canonical bytes, full bindings and local status."""
    _record(bundle, WorkerBundle)
    _record(work, BoardWork)
    _uint(max_payload_bytes, positive=True)
    _need(bundle.work_position == work.position and bundle.kind is kind and bundle.board == records.encode(work.board)
          and bundle.arm_order is work.arm_order, "WORKER_IDENTITY_MISMATCH")
    _need(sum(len(data) for _, values in bundle.streams for data in values) <= max_payload_bytes,
          "WORKER_PAYLOAD_CAP")
    _need(len(encode_bundle(bundle)) <= max_payload_bytes, "WORKER_PAYLOAD_CAP")
    streams = dict(bundle.streams)
    expected_roles = {WorkerKind.PRIMARY: ("control", "kp0"),
                      WorkerKind.DETERMINISM: _ROLES, WorkerKind.K_CONTROL: ()}[kind]
    required = {"boards"} | ({"runtime"} if work.runtime is not None else set())
    required.update(role + "_" + component for role in expected_roles for component in ("arms",) + _COMPONENTS)
    if kind is WorkerKind.PRIMARY:
        required.update(("pairs", "certificate_audits", "oracle_b_audits", "oracle_b_coverage", "evaluators"))
        if work.k_control_selected or work.determinism_selected:
            required.add("control_maintenance")
    elif kind is WorkerKind.DETERMINISM:
        required.update(("control_maintenance", "repeat_control_maintenance", "repeat_certificate_audits",
                         "repeat_oracle_b_audits", "repeat_oracle_b_coverage", "repeat_evaluators",
                         "control_determinism", "kp0_determinism"))
    else:
        required.update(("control_maintenance", "kcontrol_arms", "kcontrol_maintenance"))
    _need(set(streams) == required, "WORKER_KIND_STREAM_COVERAGE_MISMATCH")
    _need(streams.get("boards") == (bundle.board,), "BOARD_IDENTITY_STREAM_REQUIRED")
    if work.runtime is not None:
        _need(streams.get("runtime") == (records.encode(work.runtime),), "RUNTIME_IDENTITY_STREAM_REQUIRED")
    for name, values in bundle.streams:
        for data in values:
            value = records.decode(data)
            _need(type(value) is _family(name) and records.encode(value) == data,
                  "NONCANONICAL_OR_WRONG_RECORD_FAMILY")
            if isinstance(value, records.ArmIdentity):
                _need(value.board == work.board and value.run_id == work.run_id, "ARM_BOARD_BINDING_MISMATCH")
                repeated = name.startswith("repeat_")
                expected_kind = (records.Arm.K_CONTROL if name == "kcontrol_arms" else
                                 records.Arm.CONTROL if "control_" in name else records.Arm.K_P0)
                _need(value == _arm(work, expected_kind, repeat=repeated), "ARM_UNIT_IDENTITY_MISMATCH")
            if type(value) is records.KControlMaintenanceRecord:
                expected_kind = records.Arm.K_CONTROL if name == "kcontrol_maintenance" else records.Arm.CONTROL
                _need(value.arm == _arm(work, expected_kind, repeat=name.startswith("repeat_")),
                      "MAINTENANCE_ARM_UNIT_IDENTITY_MISMATCH")
    _need(tuple(header.role for header in bundle.projection_headers) == expected_roles,
          "WORKER_PROJECTION_COVERAGE_MISMATCH")
    projections = {role: restore_projection(bundle, role) for role in expected_roles}
    for role, projection in projections.items():
        expected_arm = records.Arm.CONTROL if role.endswith("control") else records.Arm.K_P0
        _need(projection.arm.board == work.board and projection.arm.run_id == work.run_id
              and projection.arm.arm is expected_arm, "PROJECTION_IDENTITY_MISMATCH")
        if role.endswith("control") and role + "_maintenance" in streams:
            _bind_control_reference(projection, tuple(records.decode(data) for data in streams[role + "_maintenance"]))
    if kind is WorkerKind.PRIMARY:
        expected_pair = game.pair_projections(projections["control"], projections["kp0"]).pair
        _need(streams.get("pairs") == (records.encode(expected_pair),), "PAIR_PROJECTION_MISMATCH")
        _need(expected_pair.p3_status is not records.P3Status.FAIL or bundle.status is records.AuditStatus.FAIL,
              "PAIR_FAILURE_CANNOT_BE_UPGRADED")
        _need(expected_pair.p3_status is not records.P3Status.INCOMPLETE
              or bundle.status is not records.AuditStatus.PASS, "PAIR_INCOMPLETE_CANNOT_BE_UPGRADED")
        _validate_k_children(streams, projections["kp0"], "", work.oracle_b_selected)
    elif kind is WorkerKind.DETERMINISM:
        _need(work.determinism_selected, "UNSELECTED_DETERMINISM_RESULT")
        _validate_k_children(streams, projections["repeat_kp0"], "repeat_", work.oracle_b_selected)
        expected = audit.determinism_record(audit.compare_determinism(
            projections["kp0"], projections["repeat_kp0"], selected=True))
        _need(streams.get("kp0_determinism") == (records.encode(expected),), "KP0_DETERMINISM_SUMMARY_MISMATCH")
        control_summary = _control_determinism(projections["control"], projections["repeat_control"],
                                                streams["control_maintenance"], streams["repeat_control_maintenance"])
        _need(streams.get("control_determinism") == (records.encode(control_summary),),
              "CONTROL_DETERMINISM_SUMMARY_MISMATCH")
    else:
        _need(work.k_control_selected and len(streams.get("kcontrol_arms", ())) == 1,
              "UNSELECTED_OR_UNBOUND_KCONTROL_RESULT")
        actual = tuple(records.decode(data) for data in streams.get("kcontrol_maintenance", ()))
        reference = tuple(records.decode(data) for data in streams.get("control_maintenance", ()))
        _need(bool(actual) and bool(reference), "KCONTROL_MAINTENANCE_COVERAGE_REQUIRED")
        status, reasons = compare_k_control(reference, actual)
        _need(bundle.status is status and bundle.reason_codes == reasons, "KCONTROL_CLASSIFICATION_MISMATCH")
    raw_fail = any(getattr(records.decode(data), "status", None) in
                   (records.AuditStatus.FAIL, records.EvaluationStatus.FAIL)
                   for name, values in bundle.streams if "audit" in name or "determinism" in name or "evaluators" in name
                   for data in values)
    _need(not raw_fail or bundle.status is records.AuditStatus.FAIL, "RAW_FAILURE_CANNOT_BE_UPGRADED")
    raw_incomplete = any(getattr(records.decode(data), "status", None) is records.AuditStatus.INCOMPLETE
                   for name, values in bundle.streams if "audit" in name or "determinism" in name
                   for data in values)
    _need(not raw_incomplete or bundle.status is not records.AuditStatus.PASS,
          "INCOMPLETE_EVIDENCE_CANNOT_BE_UPGRADED")
    _need(all(projection.effect_evidence_complete and projection.p3_evidence_complete
              and projection.g5_evidence_complete
              for projection in projections.values()) or bundle.status is not records.AuditStatus.PASS,
          "INCOMPLETE_PROJECTION_CANNOT_BE_UPGRADED")
    _need(all(projection.comparable_compute_ns is not None for projection in projections.values())
          or bundle.status is not records.AuditStatus.PASS, "INCOMPLETE_COMPUTE_CANNOT_BE_UPGRADED")
    return bundle


def _validate_k_children(streams, projection, prefix, oracle_selected):
    certificates = tuple(records.decode(data) for data in streams.get(prefix + "certificate_audits", ()))
    _need(tuple(item.acquisition for item in certificates) == projection.acquisitions,
          "CERTIFICATE_AUDIT_COVERAGE_MISMATCH")
    oracle_values = streams.get(prefix + "oracle_b_audits", ())
    coverage_values = streams.get(prefix + "oracle_b_coverage", ())
    _need(len(coverage_values) == 1, "ORACLE_B_COVERAGE_SINGLETON_REQUIRED")
    coverage = records.decode(coverage_values[0])
    _record(coverage, records.OracleBCoverageRecord)
    _need(coverage.arm == projection.arm and coverage.selected is oracle_selected,
          "ORACLE_B_COVERAGE_IDENTITY_MISMATCH")
    _need(all(ordinal < len(projection.physical_inputs) for ordinal, _ in coverage.applicable),
          "ORACLE_B_COVERAGE_BOUNDARY_MISMATCH")
    _need(oracle_selected or not oracle_values, "UNSELECTED_ORACLE_MAINTENANCE")
    if oracle_selected:
        children = tuple(records.decode(data) for data in oracle_values)
        _need(tuple((item.action_ordinal, item.phase) for item in children) == coverage.applicable,
              "ORACLE_B_COVERAGE_MISMATCH")
    values = tuple(records.decode(data) for data in streams.get(prefix + "evaluators", ()))
    _need(tuple(value.assertion for value in values) == tuple(records.AssertionCategory)
          and all(value.arm == projection.arm for value in values), "EVERY_K_BOARD_REQUIRES_THREE_EVALUATOR_CATEGORIES")


@dataclass(frozen=True, slots=True)
class _BoardOwner:
    board: records.BoardIdentity
    mines: frozenset = field(repr=False)

    def __post_init__(self):
        _record(self.board, records.BoardIdentity)
        _need(type(self.mines) is frozenset, "PRIVATE_LAYOUT_OWNERSHIP")
        _need(benchmark_board.calculate_board_fingerprint(self.board.width, self.board.height,
                  self.board.mines, self.mines) == self.board.fingerprint, "IMPLEMENTATION_IDENTITY_FAIL")
        _need(self.board.first_click not in self.mines, "IMPLEMENTATION_IDENTITY_FAIL")


def _materialize_board(work):
    """Production-only generator boundary; no synthetic layout flag/callback."""
    _record(work, BoardWork)
    board, spec = work.board, benchmark_board.EXPERT_GENERAL_V1
    _need(work.protocol_seed.hex() == identity.PROTOCOL_SHA256, "IMPLEMENTATION_IDENTITY_FAIL")
    _need((board.width, board.height, board.mines, board.first_click,
           board.generator_identity, board.spec_identity) == (30, 16, 99, (0, 0), "V1", "EXPERT_GENERAL_V1"),
          "IMPLEMENTATION_IDENTITY_FAIL")
    _need(work.runtime is not None, "IMPLEMENTATION_IDENTITY_FAIL")
    runtime = records.RuntimeIdentity(platform.python_implementation(), platform.python_version(),
                                      os.name, platform.platform(), platform.machine(),
                                      None if work.runtime.host is None else platform.node())
    _need(runtime == work.runtime, "IMPLEMENTATION_IDENTITY_FAIL")
    _need((spec.benchmark_set_id, spec.width, spec.height, spec.num_mines, spec.first_click_x,
           spec.first_click_y, spec.board_generator_version, spec.seed_scheme)
          == ("EXPERT_GENERAL_V1", 30, 16, 99, 0, 0, "V1", "game_index"), "IMPLEMENTATION_IDENTITY_FAIL")
    generated = benchmark_board.generate_board(spec, board.game_index)
    _need(type(generated) is benchmark_board.BenchmarkBoard and generated.game_index == generated.seed == board.game_index
          and generated.board_fingerprint == board.fingerprint, "IMPLEMENTATION_IDENTITY_FAIL")
    return _BoardOwner(board, generated.mine_positions)


class _InputPort:
    """Physical boundary cap; solver receives public metadata/observation only."""
    __slots__ = ("__engine", "width", "height", "num_mines", "_count", "_cap", "_observer", "_abort", "_arm")

    def __init__(self, engine, cap, observer, abort_check, arm):
        self.__engine = engine
        self.width, self.height, self.num_mines = engine.width, engine.height, engine.num_mines
        self._count, self._cap, self._observer, self._abort, self._arm = 0, cap, observer, abort_check, arm

    @property
    def status(self):
        return self.__engine.status

    def get_observation(self):
        return self.__engine.get_observation()

    def step(self, x, y, action):
        if self._abort is not None:
            self._abort()
        if self._observer is not None:
            self._observer("BEFORE_INPUT", self._arm)
        _need(self._count < self._cap, "SYSTEM_INPUT_CAP")
        self._count += 1
        return self.__engine.step(x, y, action)


def _fresh_engine(owner, cap, observer, abort_check, arm):
    _record(owner, _BoardOwner)
    _uint(cap, positive=True)
    board = owner.board
    engine = MinesweeperEngine(board.width, board.height, board.mines)
    engine.reset_with_mines(board.width, board.height, board.mines, owner.mines)
    _need(engine.status is GameStatus.PLAYING and all(value == CellState.HIDDEN
              for row in engine.get_observation() for value in row), "FRESH_ENGINE_REQUIRED")
    return _InputPort(engine, cap, observer, abort_check, arm)


def decision_watchdog_targets():
    """Sampling targets only; installs no callbacks, trace or profile hooks."""
    lines, first = inspect.getsourcelines(runner.run_k_p0)
    lower = next(first + index for index, line in enumerate(lines) if "decision = session.analyze_decision(" in line)
    upper = next(first + index for index, line in enumerate(lines) if "analysis_ns = perf_counter_ns() - started_ns" in line)
    return ((stage3_planner.plan_position.__code__, capability.KLocalSession.analyze_decision.__code__,
             policy.select_policy.__code__), ((runner.run_k_p0.__code__, lower, upper),))


def _arm(work, kind, *, repeat=False):
    return records.ArmIdentity(kind, work.board, work.run_id,
                                work.unit_id + ("-repeat" if repeat else "") + "-" + kind.value)


def _bundle(work, kind, streams, headers, status, reasons):
    streams["boards"] = (records.encode(work.board),)
    if work.runtime is not None:
        streams["runtime"] = (records.encode(work.runtime),)
    value = WorkerBundle(work.position, kind, records.encode(work.board), work.arm_order,
                         tuple((name, streams[name]) for name in STREAM_NAMES if name in streams),
                         tuple(headers), status, tuple(reasons))
    return revalidate_bundle(value, work, kind)


def _notify(observer, event, arm):
    if observer is not None:
        observer(event, arm.value)


def _oracle_b_coverage(raw, arm, selected):
    """Record raw reached phases independently of I5's returned audit children."""
    _need(type(raw) is runner.KRunResult and type(raw.traces) is tuple, "ORACLE_B_RAW_TRACE_REQUIRED")
    applicable = []
    for trace in raw.traces:
        _need(type(trace) is runner.KActionTrace, "ORACLE_B_RAW_TRACE_REQUIRED")
        if trace.input_index == 0 or trace.selection is None:
            continue
        _need(type(trace.selection) is policy.PolicySelection
              and type(trace.selection.evidence) is capability.DecisionAnalysis, "ORACLE_B_RAW_SELECTION_REQUIRED")
        decision = trace.selection.evidence
        if decision.phase_d is not None:
            applicable.append((trace.input_index, "D"))
        if decision.phase_e is not None:
            applicable.append((trace.input_index, "E"))
    return records.OracleBCoverageRecord(arm, selected, tuple(applicable))


def _run_pair(work, owner, table, *, repeat=False, max_physical_inputs=480, observer=None, abort_check=None,
              oracle_timing_observer=None):
    """Private direct seam for literal unit fixtures; public workers own generation."""
    _record(work, BoardWork)
    _record(owner, _BoardOwner)
    _need(owner.board == work.board, "PRIVATE_BOARD_BINDING_MISMATCH")
    validate_timing_table(table)
    order = ((records.Arm.CONTROL, records.Arm.K_P0) if work.arm_order is identity.ArmOrder.CONTROL_THEN_KP0
             else (records.Arm.K_P0, records.Arm.CONTROL))
    raw_results = {}
    # Phase A: adjacent solver arms only. Postprocessing cannot warm the second
    # arm's process selectively when the frozen order starts with K-P0.
    for kind in order:
        port = _fresh_engine(owner, max_physical_inputs, observer, abort_check, kind.value)
        _notify(observer, "ARM_START", kind)
        if kind is records.Arm.CONTROL:
            raw = runner.run_control_capture(port, table=table)
        else:
            raw = runner.run_k_p0(port, table=table, capture_effects=True)
        _notify(observer, "ARM_END", kind)
        raw_results[kind] = raw
        raw = port = None

    # Phase B: both solver arms have ended. Only these two bounded detached raw
    # results and the worker-owned answer remain alive for I4/I5 qualification.
    prefix = "repeat_" if repeat else ""
    control_arm, kp0_arm = (_arm(work, kind, repeat=repeat) for kind in (records.Arm.CONTROL, records.Arm.K_P0))
    control = game.project_control(raw_results[records.Arm.CONTROL], control_arm, table=table)
    kp0 = game.project_k_p0(raw_results[records.Arm.K_P0], kp0_arm, table=table)
    projections = {prefix + "control": control, prefix + "kp0": kp0}
    streams, headers, reasons, statuses = {}, {}, [], []
    if work.k_control_selected or work.determinism_selected:
        streams[prefix + "control_maintenance"] = tuple(records.encode(item) for item in
            _project_control_reference(raw_results[records.Arm.CONTROL], control))
    coverage = _oracle_b_coverage(raw_results[records.Arm.K_P0], kp0_arm, work.oracle_b_selected)
    audit_options = {} if oracle_timing_observer is None else {"oracle_timing_observer": oracle_timing_observer}
    public = audit.audit_k_p0(raw_results[records.Arm.K_P0], kp0, raw_arm=kp0_arm, table=table,
                              oracle_b_enabled=work.oracle_b_selected, **audit_options)
    # Exactly once, after both executions, with the same raw K result and answer.
    private_records = evaluator.evaluate_k_p0(raw_results[records.Arm.K_P0], kp0,
        evaluator.PrivateFixedAnswer(kp0_arm, owner.mines), raw_arm=kp0_arm, table=table)
    streams[prefix + "oracle_b_coverage"] = (records.encode(coverage),)
    streams[prefix + "certificate_audits"] = tuple(records.encode(item) for item in public.certificate_audits)
    streams[prefix + "oracle_b_audits"] = tuple(records.encode(item) for item in public.oracle_b_audits)
    streams[prefix + "evaluators"] = tuple(records.encode(item) for item in private_records)
    statuses.append(public.status)
    if public.status is not records.AuditStatus.PASS:
        reasons.append("PUBLIC_AUDIT_" + public.status.value)
    if any(item.status is records.EvaluationStatus.FAIL for item in private_records):
        statuses.append(records.AuditStatus.FAIL)
        reasons.append("PRIVATE_ASSERTION_FALSIFIED")
    raw_results.clear()  # No live/raw owner becomes part of a published payload.
    for role, projection in projections.items():
        headers[role], projected = _projection_streams(projection, role)
        streams.update(projected)
    paired = game.pair_projections(projections[prefix + "control"], projections[prefix + "kp0"])
    if paired.pair.p3_status is records.P3Status.FAIL:
        statuses.append(records.AuditStatus.FAIL)
        reasons.append("P3_IMPLEMENTATION_IDENTITY_FAIL")
    elif paired.pair.p3_status is records.P3Status.INCOMPLETE:
        statuses.append(records.AuditStatus.INCOMPLETE)
        reasons.append("P3_EVIDENCE_INCOMPLETE")
    if any(projection.comparable_compute_ns is None for projection in projections.values()):
        statuses.append(records.AuditStatus.INCOMPLETE)
        reasons.append("PRIMARY_COMPUTE_EVIDENCE_INCOMPLETE")
    if any(not projection.g5_evidence_complete for projection in projections.values()):
        statuses.append(records.AuditStatus.INCOMPLETE)
        reasons.append("G5_EVIDENCE_INCOMPLETE")
    if not repeat:
        streams["pairs"] = (records.encode(paired.pair),)
    status = (records.AuditStatus.FAIL if records.AuditStatus.FAIL in statuses else
              records.AuditStatus.INCOMPLETE if records.AuditStatus.INCOMPLETE in statuses else records.AuditStatus.PASS)
    return projections, streams, tuple(headers[role] for role in _ROLES if role in headers), status, tuple(reasons)


def execute_primary(work, *, shadow_timeout_ms=1000, max_physical_inputs=480, observer=None, abort_check=None,
                    oracle_timing_observer=None):
    owner = _materialize_board(work)
    table = load_timing_table()
    _, streams, headers, status, reasons = _run_pair(work, owner, table, max_physical_inputs=max_physical_inputs,
                                                     observer=observer, abort_check=abort_check,
                                                     oracle_timing_observer=oracle_timing_observer)
    return _bundle(work, WorkerKind.PRIMARY, streams, headers, status, reasons)


def _control_semantics(projection, maintenance):
    semantic_arm = replace(projection.arm, run_id="SEMANTIC", unit_id="SEMANTIC")
    chunks = [records.encode(projection.arm.board)]
    for component in _COMPONENTS:
        for value in getattr(projection, component):
            if type(value) is records.DecisionSpanRecord:
                value = replace(value, duration_ns=None)
            elif type(value) in (records.ActionDecisionRecord, records.GuessCheckpointRecord):
                value = replace(value, arm=semantic_arm)
            chunks.append(records.encode(value))
    for data in maintenance:
        value = records.decode(data)
        value = replace(value, arm=semantic_arm, timings=tuple((name, None) for name in _TIMINGS),
                        guess_checkpoint=None if value.guess_checkpoint is None else
                        replace(value.guess_checkpoint, arm=semantic_arm))
        chunks.append(records.encode(value))
    chunks.append(_json((projection.outcome.value, projection.total_model_us,
                         projection.effect_evidence_complete, projection.p3_evidence_complete,
                         projection.g5_evidence_complete, tuple(reason for reason in projection.diagnostics
                         if not reason.startswith("MISSING_COMPARABLE_COMPUTE:")))))
    return tuple(chunks)


def _control_determinism(first, repeat, first_maintenance, repeat_maintenance):
    left, right = _control_semantics(first, first_maintenance), _control_semantics(repeat, repeat_maintenance)
    first_digest = sha256(_json(tuple(data.decode("ascii") for data in left))).hexdigest()
    repeat_digest = sha256(_json(tuple(data.decode("ascii") for data in right))).hexdigest()
    difference = next(("CONTROL.semantic_records[" + str(i) + "]" for i, (a, b) in enumerate(zip(left, right))
                       if a != b), None)
    if difference is None and len(left) != len(right):
        difference = "CONTROL.semantic_records.length"
    if difference is None and first_digest != repeat_digest:
        difference = "CONTROL.semantic_digest"
    return records.DeterminismAuditRecord(True, first_digest, repeat_digest,
        records.AuditStatus.PASS if difference is None else records.AuditStatus.FAIL, difference)


def execute_repeat(work, first_primary_bundle, *, shadow_timeout_ms=1000, max_physical_inputs=480,
                   observer=None, abort_check=None, oracle_timing_observer=None,
                   prior_binding_observer=None):
    _record(work, BoardWork)
    if not work.determinism_selected:
        return None
    _revalidate_primary_prior(work, first_primary_bundle, WorkerKind.DETERMINISM, prior_binding_observer)
    owner, table = _materialize_board(work), load_timing_table()
    projections, streams, headers, status, reasons = _run_pair(
        work, owner, table, repeat=True, max_physical_inputs=max_physical_inputs,
        observer=observer, abort_check=abort_check, oracle_timing_observer=oracle_timing_observer)
    first = {role: restore_projection(first_primary_bundle, role) for role in ("control", "kp0")}
    retained = {name: values for name, values in first_primary_bundle.streams
                if name.startswith("control_") or name.startswith("kp0_")}
    streams.update(retained)
    control_summary = _control_determinism(first["control"], projections["repeat_control"],
                                           retained["control_maintenance"], streams["repeat_control_maintenance"])
    kp0_summary = audit.determinism_record(audit.compare_determinism(
        first["kp0"], projections["repeat_kp0"], selected=True))
    streams["control_determinism"] = (records.encode(control_summary),)
    streams["kp0_determinism"] = (records.encode(kp0_summary),)
    statuses = (status, first_primary_bundle.status, control_summary.status, kp0_summary.status)
    if records.AuditStatus.FAIL in statuses:
        status, reasons = records.AuditStatus.FAIL, reasons + ("DETERMINISM_OR_PRIOR_AUDIT_FAIL",)
    elif records.AuditStatus.INCOMPLETE in statuses:
        status, reasons = records.AuditStatus.INCOMPLETE, reasons + ("DETERMINISM_OR_PRIOR_EVIDENCE_INCOMPLETE",)
    # Both full first and repeat streams, including DecisionSpanRecord, travel
    # with the summaries. Durations are excluded only from semantic equality.
    return _bundle(work, WorkerKind.DETERMINISM, streams,
                    first_primary_bundle.projection_headers + headers, status, reasons)


def _v1_decision(decision):
    if decision is None:
        return None
    value = evidence.project_v1_decision(decision)
    proof, plan = value.evidence, value.plan
    probability = proof.probability_result
    return records.KControlV1Decision(
        records.Action[value.move.action.name], (value.move.x, value.move.y), proof.kind.name,
        records.Action[proof.move.action.name], (proof.move.x, proof.move.y),
        tuple((item.source, item.remaining_mines, item.hidden_cells) for item in proof.constraints),
        proof.deterministic_result.safe_cells, proof.deterministic_result.mine_cells,
        None if probability is None else probability.total_worlds,
        () if probability is None else tuple((item.coordinate, item.mine_worlds, item.total_worlds)
                                             for item in probability.probabilities),
        () if probability is None else probability.frontier_cells,
        () if probability is None else probability.unconstrained_cells,
        () if plan is None else tuple((records.Action[item.action.name], (item.x, item.y)) for item in plan.actions),
        None if plan is None else plan.latency_us, None if plan is None else plan.reveals)


def _accounting(value):
    _need(type(value) is capability.Accounting, "SHADOW_ACCOUNTING_TYPE")
    return records.KControlAccounting(_cells(value.P), _cells(value.H), _cells(value.M),
        _cells(value.J), _cells(value.U), value.b,
        tuple((item.source, item.clue_value, _cells(item.fixed_mines), _cells(item.Uc), item.rc)
              for item in value.constraints))


def _shadow_decision(value):
    _need(type(value) is capability.DecisionAnalysis, "SHADOW_DECISION_TYPE")
    def exact(snapshot, mines):
        if snapshot is None:
            return None
        materialized = tuple(tuple(int(CellState.FLAGGED) if glyph == CellState.HIDDEN and (x, y) in mines
                                    else glyph for x, glyph in enumerate(row))
                             for y, row in enumerate(value.observation))
        return audit._exact_snapshot(snapshot, materialized)
    local = value.local
    return records.KControlShadowDecision(value.observation, value.num_mines,
        _accounting(local.before), _accounting(local.after), _cells(local.acquired_mines),
        _cells(local.S_first), _cells(local.S_second_all), _cells(local.S_new), _cells(local.S_current),
        tuple(audit._certificate_semantics(item) for item in local.certificates),
        exact(value.phase_d, local.after.M), exact(value.phase_e, value.after.M), value.phase_e_status,
        _accounting(value.after), tuple(audit._certificate_semantics(item) for item in value.exact_certificates),
        value.continuation, _cells(value.selection_safe_cells), value.guess_target)


def _shadow_state(value, boundary):
    _need(type(value) is runner.ShadowCheckpoint, "SHADOW_CHECKPOINT_TYPE")
    _need(all(type(flag) is bool for flag in (value.enabled, value.evidence_valid, value.v1_continues)),
          "SHADOW_STATE_EXACT_FLAGS")
    current = (value.enabled and value.evidence_valid and value.failure is None
               and value.last_valid_boundary == boundary and value.decision is not None)
    failure = value.failure
    if failure is not None:
        _need(type(failure) is runner.ShadowFailure, "SHADOW_FAILURE_TYPE")
        # The accepted runner's exception detail may interpolate arbitrary error
        # text. Publish a fixed diagnosis, never a potentially private traceback.
        failure = (("failure_class", failure.failure_class), ("detected_boundary", failure.detected_boundary),
                   ("last_valid_boundary", failure.last_valid_boundary),
                   ("detail", "PUBLIC_SHADOW_FAILURE:" + failure.failure_class),
                   ("implicated_boundary", failure.implicated_boundary),
                   ("invalidation_scope", failure.invalidation_scope))
    return records.KControlShadowState(value.enabled, _cells(value.last_valid_M),
        _shadow_decision(value.decision) if current else None, failure, value.last_valid_boundary,
        current, value.v1_continues)


def _timings(value):
    _need(type(value) is evidence.DecisionTimings, "DECISION_TIMING_TYPE")
    evidence.DecisionTimings.__post_init__(value)
    return tuple((name, getattr(value, name)) for name in _TIMINGS)


def _project_control_reference(raw, projection):
    _need(type(raw) is runner.ControlCaptureResult and projection.arm.arm is records.Arm.CONTROL,
          "CONTROL_REFERENCE_TYPE")
    public = {item.action_ordinal: item for item in projection.public_effects}
    terminal = {item.action_ordinal: item for item in projection.terminal_effects}
    checkpoints = iter(projection.guess_checkpoints)
    result = []
    for index, (trace, physical) in enumerate(zip(raw.traces, projection.physical_inputs)):
        decision = _v1_decision(trace.decision)
        guess = (next(checkpoints) if decision is not None and decision.evidence_kind == "PROBABILITY_GUESS"
                 else None)
        result.append(records.KControlMaintenanceRecord(projection.arm, physical,
            raw.effects[index].before_observation, public.get(index), terminal.get(index), decision,
            guess, _timings(raw.timings[index]), (), (), None, None, None, "REFERENCE"))
    _need(next(checkpoints, None) is None, "CONTROL_GUESS_REFERENCE_COVERAGE")
    return tuple(result)


def _bind_control_reference(projection, reference):
    _need(len(reference) == len(projection.physical_inputs), "CONTROL_O4_REFERENCE_COVERAGE")
    public = {item.action_ordinal: item for item in projection.public_effects}
    terminal = {item.action_ordinal: item for item in projection.terminal_effects}
    guesses = []
    rows = [[-2] * projection.arm.board.width for _ in range(projection.arm.board.height)]
    for index, (item, physical, decision) in enumerate(zip(reference, projection.physical_inputs, projection.decisions)):
        _record(item, records.KControlMaintenanceRecord)
        _need(item.arm == projection.arm and item.physical == physical and item.public_effect == public.get(index)
              and item.terminal_effect == terminal.get(index) and item.observation == tuple(tuple(row) for row in rows),
              "CONTROL_O4_REFERENCE_BINDING")
        if index:
            value = item.v1_decision
            _need(value is not None and evidence.DecisionKind[value.evidence_kind].value == decision.semantic_kind
                  and (value.action, value.target) == (decision.action, decision.target)
                  and value.plan_actions == decision.plan_actions and value.plan_model_us == decision.plan_model_us
                  and value.plan_safe_reveals == decision.plan_safe_reveals, "CONTROL_O4_DECISION_BINDING")
        if item.guess_checkpoint is not None:
            guesses.append(item.guess_checkpoint)
        if item.public_effect is not None:
            for change in item.public_effect.changes:
                rows[change.cell[1]][change.cell[0]] = (-2 if change.after == "HIDDEN" else
                    -3 if change.after == "FLAGGED" else int(change.after.removeprefix("CLUE_")))
    _need(tuple(guesses) == projection.guess_checkpoints, "CONTROL_O4_GUESS_BINDING")


def _maintenance_classification(physical, decision, public, shadow, soundness, final, timings):
    if shadow.failure is not None:
        return ("IMPLEMENTATION_IDENTITY_FAIL" if dict(shadow.failure)["failure_class"] == "SHADOW_SOUNDNESS_VIOLATION"
                else "INCOMPLETE")
    if public is None or (physical.action_ordinal and (decision is None or not shadow.evidence_valid
                                                     or soundness is None)) or (
            physical.after_status is not records.Status.PLAYING and final is None):
        return "INCOMPLETE"
    measured = dict(timings)
    if measured["v1_execution_validation_ns"] is None or (physical.action_ordinal and any(
            measured[name] is None for name in ("v1_plan_position_ns", "shadow_ns", "comparison_ns"))):
        return "INCOMPLETE"
    if not physical.action_ordinal:
        return "NOT_REACHED"
    return "NOT_EVALUATED" if dict(soundness)["classification"] == "NOT_EVALUATED" else "PASS"


def project_k_control(raw, arm, *, table):
    """Detach full O-4/P-5 premises; never replay V1 or start a shadow loop."""
    _need(type(raw) is runner.KControlRunResult and type(raw.traces) is tuple and bool(raw.traces),
          "KCONTROL_RESULT_TYPE")
    _record(arm, records.ArmIdentity)
    _need(arm.arm is records.Arm.K_CONTROL, "KCONTROL_ARM_REQUIRED")
    validate_timing_table(table)
    last = raw.traces[-1].shadow
    _need(raw.shadow == replace(last, decision=None, evidence_valid=False), "FINAL_SHADOW_BINDING_MISMATCH")
    effects = tuple(trace.public_effect for trace in raw.traces)
    outcome = records.Outcome.WIN if raw.status is GameStatus.WON else records.Outcome.LOSS
    checkpoints, missing = game._control_checkpoints(raw.traces, effects, arm, outcome)
    if missing:
        raise E2EvidenceIncomplete("KCONTROL_GUESS_EVIDENCE_INCOMPLETE") from None
    guesses = iter(checkpoints)
    result, total, cursor, prior_m = [], 0, (0, 0), ()
    for index, trace in enumerate(raw.traces):
        _need(type(trace) is runner.KControlActionTrace and trace.input_index == index
              and trace.cursor_before == cursor and _cells(trace.M_before) == prior_m,
              "KCONTROL_INPUT_CONTINUITY")
        target = (trace.move.x, trace.move.y)
        cost = action_cost(table, cursor, target)
        _need(trace.modeled_action_us == cost, "KCONTROL_MODEL_C_BINDING")
        total += cost
        physical = records.PhysicalInputRecord(index, records.Action[trace.move.action.name], target,
                    cursor, cost, total, records.Status[trace.status_after.name])
        if trace.public_effect is None:
            public = terminal = None
        else:
            effect = trace.public_effect
            _need(effect.input_index == index and effect.move.action is trace.move.action
                  and (effect.move.x, effect.move.y) == target
                  and effect.before_observation == trace.observation and effect.cursor_before == cursor
                  and effect.modeled_action_us == cost and effect.status_after is trace.status_after,
                  "KCONTROL_EFFECT_BINDING")
            public, terminal = game._project_effect(effect)
        decision = _v1_decision(trace.decision)
        guess = (next(guesses) if decision is not None and decision.evidence_kind == "PROBABILITY_GUESS" else None)
        shadow = _shadow_state(trace.shadow, index)
        soundness = trace.soundness
        if soundness is not None:
            _need(type(soundness) is evidence.ShadowSoundnessEvidence
                  and soundness.boundary == index
                  and soundness.v1_decision == (None if trace.decision is None else evidence.project_v1_decision(trace.decision)),
                  "SHADOW_COMPARISON_V1_BINDING")
            _need(soundness.classification != "SHADOW_SOUNDNESS_VIOLATION" or shadow.failure is not None,
                  "IMPLEMENTATION_IDENTITY_FAIL")
            soundness = (("classification", soundness.classification), ("boundary", soundness.boundary),
                         ("implicated_boundary", soundness.implicated_boundary), ("safe_cells", soundness.safe_cells),
                         ("detail", "PUBLIC_SHADOW_COMPARISON:" + soundness.classification))
        final = _shadow_state(raw.shadow, index) if index == len(raw.traces) - 1 else None
        timings = _timings(trace.timings)
        classification = _maintenance_classification(physical, decision, public, shadow, soundness, final, timings)
        item = records.KControlMaintenanceRecord(arm, physical, trace.observation, public, terminal,
                decision, guess, timings, _cells(trace.M_before), _cells(trace.preinput_M),
                shadow, soundness, final, classification)
        result.append(item)
        cursor, prior_m = target, item.logical_m_preinput
    _need(next(guesses, None) is None and raw.total_modeled_us == total
          and raw.status is raw.traces[-1].status_after, "KCONTROL_FINAL_BINDING")
    return tuple(result)


def _control_identity(item):
    guess = item.guess_checkpoint
    if guess is not None:
        guess = replace(guess, arm=records.ArmIdentity(records.Arm.CONTROL, item.arm.board, "SEMANTIC", "SEMANTIC"))
    return (item.physical, item.observation, item.public_effect, item.terminal_effect, item.v1_decision, guess)


def compare_k_control(reference, actual):
    """Full CONTROL physical/Model-C/public/O-4 identity plus exact P-5 status."""
    _need(type(reference) is tuple and type(actual) is tuple and bool(reference) and bool(actual),
          "KCONTROL_FULL_REFERENCE_AND_ACTUAL_REQUIRED")
    for items, kind in ((reference, records.Arm.CONTROL), (actual, records.Arm.K_CONTROL)):
        for index, item in enumerate(items):
            _record(item, records.KControlMaintenanceRecord)
            _need(item.arm.arm is kind and item.physical.action_ordinal == index, "KCONTROL_STREAM_ORDER")
        _need(all(item.arm == items[0].arm for item in items), "KCONTROL_STREAM_ARM_IDENTITY")
    _need(reference[0].arm.board == actual[0].arm.board
          and reference[0].arm.run_id == actual[0].arm.run_id, "KCONTROL_BOARD_IDENTITY_MISMATCH")
    reasons, missing, mismatch = [], False, False
    terminal = lambda item: item.physical.after_status is not records.Status.PLAYING
    if len(reference) != len(actual):
        # Two declared completed streams of different lengths contradict O-4.
        # A missing tail remains incomplete; all available premises still bind.
        mismatch = terminal(reference[-1]) and terminal(actual[-1])
        missing = not mismatch
    if not terminal(reference[-1]) or not terminal(actual[-1]):
        missing = True
    for left, right in zip(reference, actual):
        expected, observed = _control_identity(left), _control_identity(right)
        if expected[:2] != observed[:2]:  # Physical inputs and public observation are never optional.
            mismatch = True
        guess_required = any(item.v1_decision is not None
                             and item.v1_decision.evidence_kind == "PROBABILITY_GUESS"
                             for item in (left, right))
        requirements = (True, terminal(left) or terminal(right),
                        left.physical.action_ordinal > 0, guess_required)
        for required, before, after in zip(requirements, expected[2:], observed[2:]):
            if before is None or after is None:
                if required:
                    missing = True
                elif before != after:
                    mismatch = True
            elif before != after:
                mismatch = True
    if mismatch:
        reasons.append("KCONTROL_IMPLEMENTATION_IDENTITY_FAIL")
    if any(item.classification == "IMPLEMENTATION_IDENTITY_FAIL" for item in actual):
        reasons.append("SHADOW_IMPLEMENTATION_IDENTITY_FAIL")
    if reasons:
        return records.AuditStatus.FAIL, tuple(reasons)
    if missing:
        return records.AuditStatus.INCOMPLETE, ("KCONTROL_REQUIRED_EVIDENCE_INCOMPLETE",)
    if any(item.classification in ("INCOMPLETE", "NOT_EVALUATED") for item in actual):
        return records.AuditStatus.INCOMPLETE, ("KCONTROL_SHADOW_EVIDENCE_INCOMPLETE",)
    return records.AuditStatus.PASS, ()


def execute_k_control(work, first_primary_bundle, *, shadow_timeout_ms=1000, max_physical_inputs=480,
                      observer=None, abort_check=None, prior_binding_observer=None):
    """One fresh process invocation only; the operational owner always retires it."""
    _record(work, BoardWork)
    if not work.k_control_selected:
        return None
    _uint(shadow_timeout_ms, positive=True)
    _need(shadow_timeout_ms <= identity.SHADOW_TIMEOUT_MS, "SHADOW_CAP_EXCEEDS_PROVISIONAL_CEILING")
    _revalidate_primary_prior(work, first_primary_bundle, WorkerKind.K_CONTROL, prior_binding_observer)
    owner, table = _materialize_board(work), load_timing_table()
    arm = _arm(work, records.Arm.K_CONTROL)
    port = _fresh_engine(owner, max_physical_inputs, observer, abort_check, arm.arm.value)
    _notify(observer, "ARM_START", arm.arm)
    raw = runner.run_k_control(port, table=table, shadow_timeout_s=shadow_timeout_ms / 1000, capture_effects=True)
    _notify(observer, "ARM_END", arm.arm)
    actual = project_k_control(raw, arm, table=table)
    raw = owner = port = None
    reference = dict(first_primary_bundle.streams).get("control_maintenance", ())
    status, reasons = compare_k_control(tuple(records.decode(data) for data in reference), actual)
    return _bundle(work, WorkerKind.K_CONTROL,
        {"control_maintenance": reference, "kcontrol_arms": (records.encode(arm),),
         "kcontrol_maintenance": tuple(records.encode(item) for item in actual)}, (), status, reasons)
