"""Additive RF02 representation primitives; no operational format switch.

Contexts must come from an authenticated outer boundary. CRC32 detects corruption;
it does not replace that boundary's SHA-256 or semantic validation. Profile capture
is explicit read-only I/O. Codec qualification does not activate operational paths.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import struct
import zlib

from experiments import program_k_e2_records as records


FRAME_FORMAT = "PKE2RF02"
BUNDLE_FORMAT = "PKE2WB02"
STREAM_REGISTRY_REVISION = 1
MAX_PAYLOAD_BYTES = 67_108_864
UINT64_MAX = (1 << 64) - 1
CHUNK_BYTES = 65_536
RAW = 0
DEFLATE = 1
_CRC_DOMAIN = b"PKE2RF02-CHECK\0"
_CONSTRUCTOR_POLICY_NAMES = (
    "program-k-r0b-reference-constructor/v1",
    "program-k-r0b-text-constructor/v1",
)


class PhysicalError(ValueError):
    """Unsupported, malformed, noncanonical or out-of-bounds representation."""


def _need(condition, reason):
    if not condition:
        raise PhysicalError(reason)


def _uint(value, maximum=UINT64_MAX):
    _need(type(value) is int and 0 <= value <= maximum, "EXACT_UNSIGNED_INTEGER_REQUIRED")


def _bound(value):
    _uint(value, MAX_PAYLOAD_BYTES)
    _need(value > 0, "POSITIVE_PAYLOAD_BOUND_REQUIRED")


@dataclass(frozen=True, slots=True)
class StreamSpec:
    name: str
    key_arity: int
    record_types: tuple
    raw_only: bool = False


# Same order/types as execution.STREAM_NAMES/_family. Support names and arities
# come from operational._EvidenceSink, qualification.write_identity and the R0
# postprocessing event writer. Importing those owners would create a cycle and
# unnecessarily import operational machinery into this representation module.
_COMPONENT_TYPES = (
    ("arms", records.ArmIdentity),
    ("physical_inputs", records.PhysicalInputRecord),
    ("public_effects", records.PublicEffectRecord),
    ("terminal_effects", records.TerminalEffectRecord),
    ("decision_spans", records.DecisionSpanRecord),
    ("decisions", records.ActionDecisionRecord),
    ("guess_checkpoints", records.GuessCheckpointRecord),
    ("flag_provenance", records.ControlFlagProvenanceRecord),
    ("acquisitions", records.AcquisitionRecord),
)
STREAM_REGISTRY = (
    StreamSpec("boards", 3, (records.BoardIdentity,)),
    StreamSpec("runtime", 3, (records.RuntimeIdentity,)),
) + tuple(
    StreamSpec(role + "_" + name, 3, (cls,))
    for role in ("control", "kp0", "repeat_control", "repeat_kp0")
    for name, cls in _COMPONENT_TYPES
) + (
    StreamSpec("control_maintenance", 3, (records.KControlMaintenanceRecord,)),
    StreamSpec("repeat_control_maintenance", 3, (records.KControlMaintenanceRecord,)),
    StreamSpec("pairs", 3, (records.PairComparisonRecord,)),
    StreamSpec("certificate_audits", 3, (records.CertificateAuditRecord,)),
    StreamSpec("oracle_b_audits", 3, (records.OracleBAuditRecord,)),
    StreamSpec("oracle_b_coverage", 3, (records.OracleBCoverageRecord,), True),
    StreamSpec("evaluators", 3, (records.EvaluatorRecord,)),
    StreamSpec("repeat_certificate_audits", 3, (records.CertificateAuditRecord,)),
    StreamSpec("repeat_oracle_b_audits", 3, (records.OracleBAuditRecord,)),
    StreamSpec("repeat_oracle_b_coverage", 3, (records.OracleBCoverageRecord,), True),
    StreamSpec("repeat_evaluators", 3, (records.EvaluatorRecord,)),
    StreamSpec("control_determinism", 3, (records.DeterminismAuditRecord,)),
    StreamSpec("kp0_determinism", 3, (records.DeterminismAuditRecord,)),
    StreamSpec("kcontrol_arms", 3, (records.ArmIdentity,)),
    StreamSpec("kcontrol_maintenance", 3, (records.KControlMaintenanceRecord,)),
    StreamSpec("operations", 1, (records.OperationEventRecord,)),
    StreamSpec("resources", 1, (records.ResourceSampleRecord,)),
    StreamSpec("qualification_identity", 1, (records.ProtocolIdentity, records.CorpusIdentity,
                                            records.RuntimeIdentity, records.SourceBlobIdentity)),
    StreamSpec("postprocessing_operations", 1, (records.OperationEventRecord,)),
)


def _stream(name):
    _need(type(name) is str and 1 <= len(name) <= 64 and name.isascii(), "INVALID_STREAM_NAME")
    for spec in STREAM_REGISTRY:
        if spec.name == name:
            return spec
    raise PhysicalError("UNKNOWN_STREAM")


@dataclass(frozen=True, slots=True)
class FrameContext:
    codec_profile_sha256: bytes
    stream_name: str
    frame_format: str = FRAME_FORMAT
    stream_registry_revision: int = STREAM_REGISTRY_REVISION
    expected_key_arity: int = 3
    allowed_logical_record_types: tuple = ()

    def __post_init__(self):
        _need(type(self.codec_profile_sha256) is bytes and len(self.codec_profile_sha256) == 32,
              "PROFILE_SHA256_REQUIRED")
        _need(type(self.frame_format) is str and self.frame_format == FRAME_FORMAT,
              "FRAME_FORMAT_MISMATCH")
        _need(type(self.stream_registry_revision) is int
              and self.stream_registry_revision == STREAM_REGISTRY_REVISION, "REGISTRY_REVISION_MISMATCH")
        spec = _stream(self.stream_name)
        _need(type(self.expected_key_arity) is int and self.expected_key_arity == spec.key_arity,
              "KEY_ARITY_CONTEXT_MISMATCH")
        _need(type(self.allowed_logical_record_types) is tuple
              and self.allowed_logical_record_types == spec.record_types, "RECORD_TYPES_CONTEXT_MISMATCH")


def context_for(stream_name, codec_profile_sha256):
    spec = _stream(stream_name)
    return FrameContext(codec_profile_sha256, stream_name,
                        expected_key_arity=spec.key_arity, allowed_logical_record_types=spec.record_types)


def _context(context):
    _need(type(context) is FrameContext, "EXACT_FRAME_CONTEXT_REQUIRED")
    FrameContext.__post_init__(context)
    return _stream(context.stream_name)


def encode_uleb128(value):
    _uint(value)
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def decode_uleb128(data, offset=0):
    _need(type(data) is bytes, "IMMUTABLE_BYTES_REQUIRED")
    _uint(offset, len(data))
    value = 0
    for width in range(1, 11):
        _need(offset + width <= len(data), "TRUNCATED_ULEB128")
        byte = data[offset + width - 1]
        payload = byte & 127
        _need(width < 10 or payload <= 1, "ULEB128_OVERFLOW")
        value |= payload << (7 * (width - 1))
        if byte < 128:
            _need(width == 1 or payload != 0, "NONMINIMAL_ULEB128")
            return value, offset + width
    raise PhysicalError("OVERLONG_OR_UNTERMINATED_ULEB128")


def _key(key, arity):
    _need(type(key) is tuple and len(key) == arity, "KEY_ARITY_MISMATCH")
    for value in key:
        _uint(value)


def encode_payload(logical, *, raw_only=False, max_payload_bytes=MAX_PAYLOAD_BYTES):
    _bound(max_payload_bytes)
    _need(type(logical) is bytes and len(logical) <= max_payload_bytes, "LOGICAL_PAYLOAD_CAP")
    _need(type(raw_only) is bool, "EXACT_RAW_ONLY_FLAG_REQUIRED")
    if raw_only:
        return RAW, logical
    compressor = zlib.compressobj(level=6, method=zlib.DEFLATED, wbits=-15,
                                  memLevel=8, strategy=zlib.Z_DEFAULT_STRATEGY)
    view = memoryview(logical)
    parts = [compressor.compress(view[start:start + CHUNK_BYTES])
             for start in range(0, len(logical), CHUNK_BYTES)]
    parts.append(compressor.flush(zlib.Z_FINISH))
    compressed = b"".join(parts)
    return (DEFLATE, compressed) if len(compressed) < len(logical) else (RAW, logical)


def _lengths(mode, payload_length, logical_length, raw_only, limit):
    _bound(limit)
    _need(type(mode) is int and mode in (RAW, DEFLATE), "UNKNOWN_MODE")
    _uint(payload_length, limit)
    _uint(logical_length, limit)
    _need(type(raw_only) is bool, "EXACT_RAW_ONLY_FLAG_REQUIRED")
    _need(not raw_only or mode == RAW, "RAW_ONLY_STREAM")
    _need(payload_length == logical_length if mode == RAW else payload_length < logical_length,
          "MODE_LENGTH_MISMATCH")


def decode_payload(mode, payload, logical_length, *, raw_only=False,
                   max_payload_bytes=MAX_PAYLOAD_BYTES):
    _need(type(payload) is bytes, "IMMUTABLE_BYTES_REQUIRED")
    _lengths(mode, len(payload), logical_length, raw_only, max_payload_bytes)
    if mode == RAW:
        return payload
    inflater = zlib.decompressobj(wbits=-15)
    try:
        # The single extra byte only detects expansion beyond the declaration.
        # No unbounded decompress/flush and no retry that could stall forever.
        logical = inflater.decompress(payload, logical_length + 1)
    except zlib.error as error:
        raise PhysicalError("MALFORMED_DEFLATE") from error
    _need(len(logical) <= logical_length, "DEFLATE_EXPANSION_OVERFLOW")
    _need(inflater.eof, "DEFLATE_END_MARKER_REQUIRED")
    _need(not inflater.unused_data, "TRAILING_DEFLATE_DATA")
    _need(not inflater.unconsumed_tail, "UNCONSUMED_DEFLATE_DATA")
    _need(len(logical) == logical_length, "DEFLATE_LOGICAL_LENGTH_MISMATCH")
    return logical


def contextual_crc32(context, row_without_crc):
    _context(context)
    _need(type(row_without_crc) is bytes or type(row_without_crc) is memoryview,
          "CRC_BYTES_REQUIRED")
    name = context.stream_name.encode("ascii")
    crc = zlib.crc32(_CRC_DOMAIN, 0)
    for part in (context.codec_profile_sha256, bytes((len(name),)), name,
                 bytes((context.expected_key_arity,)), row_without_crc):
        crc = zlib.crc32(part, crc)
    return crc & 0xffffffff


def _logical(logical, context):
    try:
        record = records.decode(logical)
        _need(type(record) in context.allowed_logical_record_types, "WRONG_LOGICAL_RECORD_TYPE")
        _need(records.encode(record) == logical, "NONCANONICAL_LOGICAL_BYTES")
    except records.RecordError as error:
        raise PhysicalError("INVALID_LOGICAL_RECORD") from error


def encode_frame(logical, key, context, *, max_payload_bytes=MAX_PAYLOAD_BYTES):
    spec = _context(context)
    _key(key, spec.key_arity)
    _bound(max_payload_bytes)
    _need(type(logical) is bytes and len(logical) <= max_payload_bytes, "LOGICAL_PAYLOAD_CAP")
    _logical(logical, context)
    mode, payload = encode_payload(logical, raw_only=spec.raw_only, max_payload_bytes=max_payload_bytes)
    row = (struct.pack(">BII", mode, len(logical), len(payload))
           + b"".join(encode_uleb128(component) for component in key) + payload)
    return row + struct.pack(">I", contextual_crc32(context, row))


def _frame_from_payload(logical, key, context, mode, payload, *,
                        max_payload_bytes=MAX_PAYLOAD_BYTES):
    """Reframe an invocation-local payload without trusting its preparation.

    The caller obtains mode/payload from encode_payload. Every distinct copy
    still checks canonical logical bytes, bounded exact expansion and its own
    key/context before receiving a fresh contextual CRC. This representation
    helper grants no semantic, profile or persistence authority.
    """
    spec = _context(context)
    _key(key, spec.key_arity)
    _bound(max_payload_bytes)
    _need(type(logical) is bytes and len(logical) <= max_payload_bytes, "LOGICAL_PAYLOAD_CAP")
    _logical(logical, context)
    restored = decode_payload(mode, payload, len(logical), raw_only=spec.raw_only,
                              max_payload_bytes=max_payload_bytes)
    _need(restored == logical, "PREPARED_PAYLOAD_LOGICAL_MISMATCH")
    row = (struct.pack(">BII", mode, len(logical), len(payload))
           + b"".join(encode_uleb128(component) for component in key) + payload)
    return row + struct.pack(">I", contextual_crc32(context, row))


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    key: tuple
    logical_bytes: bytes
    mode: int
    frame_length: int


def decode_frame_from(data, offset, context, *, expected_key=None,
                      max_payload_bytes=MAX_PAYLOAD_BYTES):
    spec = _context(context)
    _bound(max_payload_bytes)
    _need(type(data) is bytes, "IMMUTABLE_BYTES_REQUIRED")
    _uint(offset, len(data))
    if expected_key is not None:
        _key(expected_key, spec.key_arity)
    start = offset
    _need(len(data) - offset >= 9, "TRUNCATED_FRAME_PREFIX")
    mode, logical_length, payload_length = struct.unpack_from(">BII", data, offset)
    _lengths(mode, payload_length, logical_length, spec.raw_only, max_payload_bytes)
    offset += 9
    values = []
    for _ in range(spec.key_arity):
        value, offset = decode_uleb128(data, offset)
        values.append(value)
    key = tuple(values)
    end = offset + payload_length + 4
    _need(end <= len(data), "TRUNCATED_FRAME_PAYLOAD_OR_CRC")
    expected_crc = struct.unpack_from(">I", data, end - 4)[0]
    _need(contextual_crc32(context, memoryview(data)[start:end - 4]) == expected_crc,
          "CONTEXTUAL_CRC_MISMATCH")
    _need(expected_key is None or key == expected_key, "UNEXPECTED_LOGICAL_KEY")
    logical = decode_payload(mode, data[offset:end - 4], logical_length,
                             raw_only=spec.raw_only, max_payload_bytes=max_payload_bytes)
    _logical(logical, context)
    return DecodedFrame(key, logical, mode, end - start), end


def decode_frame(data, context, *, expected_key=None, max_payload_bytes=MAX_PAYLOAD_BYTES):
    frame, end = decode_frame_from(data, 0, context, expected_key=expected_key,
                                   max_payload_bytes=max_payload_bytes)
    _need(end == len(data), "TRAILING_FRAME_BYTES")
    return frame


def _json(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _profile_contract():
    return {
        "frame_format": FRAME_FORMAT, "bundle_format": BUNDLE_FORMAT,
        "logical_codec": "program_k_e2_records.encode/decode:1",
        "compression": {"method": "DEFLATED", "level": 6, "wbits": -15,
                        "mem_level": 8, "strategy": "Z_DEFAULT_STRATEGY", "dictionary": None,
                        "chunk_bytes": CHUNK_BYTES, "fresh_per_record": True,
                        "finalization": "one Z_FINISH", "selection": "DEFLATE iff strictly shorter"},
        "crc": "crc32(PKE2RF02-CHECK\\0 || profile[32] || name_length:u8 || name:ASCII || arity:u8 || row,0)&0xffffffff;u32BE",
        "integers": {"key": "canonical unsigned ULEB128 uint64", "length": "u32BE",
                     "key_max_bytes": 10},
        "limits": {"payload_bytes": MAX_PAYLOAD_BYTES, "logical_bytes": MAX_PAYLOAD_BYTES,
                   "experiment_frame_bytes": MAX_PAYLOAD_BYTES + 43,
                   "support_frame_bytes": MAX_PAYLOAD_BYTES + 23},
        "stream_registry_revision": STREAM_REGISTRY_REVISION,
        "streams": [{"name": spec.name, "key_arity": spec.key_arity,
                     "record_types": [cls.__name__ for cls in spec.record_types], "raw_only": spec.raw_only}
                    for spec in STREAM_REGISTRY],
    }


def _keys(node, names):
    _need(type(node) is dict and set(node) == set(names), "PROFILE_SCHEMA_MISMATCH")


def _text(value):
    _need(type(value) is str and bool(value) and all(32 <= ord(c) <= 126 for c in value),
          "PROFILE_ASCII_TEXT_REQUIRED")


def _digest(value):
    _need(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
          "PROFILE_HEX_SHA256_REQUIRED")


def _artifact(node):
    _keys(node, ("role", "path", "byte_length", "sha256"))
    _text(node["role"])
    _text(node["path"])
    _uint(node["byte_length"])
    _need(node["byte_length"] > 0, "EMPTY_PROFILE_ARTIFACT")
    _digest(node["sha256"])


def _profile_node(node):
    _keys(node, ("schema_version", "status", "contract", "writer_sources", "runtime", "constructor_policies"))
    _need(type(node["schema_version"]) is int and node["schema_version"] == 1, "PROFILE_SCHEMA_VERSION")
    _need(type(node["status"]) is str and node["status"] in ("UNQUALIFIED_SLICE_1A", "QUALIFIED"),
          "PROFILE_STATUS")
    # Canonical bytes comparison distinguishes e.g. true from 1 in nested facts.
    _need(_json(node["contract"]) == _json(_profile_contract()), "PROFILE_CONTRACT_MISMATCH")
    sources = node["writer_sources"]
    _need(type(sources) is list, "PROFILE_SOURCE_LIST_REQUIRED")
    for item in sources:
        _artifact(item)
    _need([item["role"] for item in sources] == ["logical_records", "physical", "worker_bundle"],
          "PROFILE_WRITER_SOURCE_COVERAGE")
    runtime = node["runtime"]
    text_keys = ("python_implementation", "python_version", "python_abi", "platform",
                 "zlib_build_version", "zlib_runtime_version")
    provider_keys = ("zlib_provider_kind", "zlib_native_owner_role")
    # Historical unqualified canonical bytes remain decodable. New captures and
    # all qualified profiles use the complete extended runtime shape.
    legacy_runtime = (node["status"] == "UNQUALIFIED_SLICE_1A" and type(runtime) is dict
                      and set(runtime) == set(text_keys + ("artifacts", "unresolved")))
    if not legacy_runtime:
        text_keys += provider_keys
    _keys(runtime, text_keys + ("artifacts", "unresolved"))
    for key in text_keys:
        _text(runtime[key])
    _need(type(runtime["artifacts"]) is list and type(runtime["unresolved"]) is list,
          "PROFILE_RUNTIME_LIST_REQUIRED")
    for item in runtime["artifacts"]:
        _artifact(item)
    roles = [item["role"] for item in runtime["artifacts"]]
    _need(roles == sorted(set(roles)) and "interpreter" in roles
          and set(roles) <= {"interpreter", "base_interpreter", "python_dll", "zlib_extension"},
          "PROFILE_RUNTIME_ARTIFACT_COVERAGE")
    for item in runtime["unresolved"]:
        _text(item)
    _need(runtime["unresolved"] == sorted(set(runtime["unresolved"])), "PROFILE_UNRESOLVED_ORDER")
    policies = node["constructor_policies"]
    _need(type(policies) is list, "PROFILE_POLICY_LIST_REQUIRED")
    for item in policies:
        _keys(item, ("name", "sha256"))
        _text(item["name"])
        _digest(item["sha256"])
    names = [item["name"] for item in policies]
    _need(names == sorted(set(names)), "PROFILE_POLICY_ORDER")
    if node["status"] == "QUALIFIED":
        _need(runtime["unresolved"] == [], "PROFILE_QUALIFIED_UNRESOLVED")
        _need(tuple(names) == _CONSTRUCTOR_POLICY_NAMES, "PROFILE_QUALIFIED_POLICY_COVERAGE")
        provider = (runtime["zlib_provider_kind"], runtime["zlib_native_owner_role"])
        windows = runtime["platform"] == "win32"
        if provider == ("extension-file", "zlib_extension"):
            required = {"interpreter", "zlib_extension"} | ({"python_dll"} if windows else set())
        else:
            _need(provider == ("builtin-python-runtime", "python_dll") and windows,
                  "PROFILE_ZLIB_PROVIDER")
            required = {"interpreter", "python_dll"}
        _need(set(roles) in (required, required | {"base_interpreter"}),
              "PROFILE_QUALIFIED_RUNTIME_COVERAGE")


def _unique(pairs):
    result = dict(pairs)
    _need(len(result) == len(pairs), "DUPLICATE_PROFILE_FIELD")
    return result


def _no_float(_):
    raise PhysicalError("PROFILE_FLOAT_FORBIDDEN")


@dataclass(frozen=True, slots=True)
class CodecProfile:
    canonical_bytes: bytes

    def __post_init__(self):
        _need(type(self.canonical_bytes) is bytes and len(self.canonical_bytes) <= MAX_PAYLOAD_BYTES,
              "PROFILE_BYTES_REQUIRED")
        try:
            node = json.loads(self.canonical_bytes.decode("ascii"), object_pairs_hook=_unique,
                              parse_float=_no_float, parse_constant=_no_float)
            _profile_node(node)
            _need(_json(node) == self.canonical_bytes, "NONCANONICAL_PROFILE")
        except PhysicalError:
            raise
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
            raise PhysicalError("MALFORMED_PROFILE") from None

    @property
    def sha256(self):
        return sha256(self.canonical_bytes).digest()

    @property
    def qualified(self):
        CodecProfile.__post_init__(self)
        return json.loads(self.canonical_bytes)["status"] == "QUALIFIED"


def profile_from_facts(*, writer_sources, runtime, constructor_policies=()):
    """Freeze supplied facts; this is canonicalization, not runtime attestation."""
    _need(type(writer_sources) is tuple and type(runtime) is dict
          and type(constructor_policies) is tuple, "PROFILE_FACT_SHAPE")
    try:
        data = _json({"schema_version": 1, "status": "UNQUALIFIED_SLICE_1A",
                      "contract": _profile_contract(), "writer_sources": list(writer_sources),
                      "runtime": runtime, "constructor_policies": list(constructor_policies)})
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise PhysicalError("MALFORMED_PROFILE_FACTS") from None
    return CodecProfile(data)


def decode_profile(data):
    return CodecProfile(data)


def require_qualified_profile(profile):
    _need(type(profile) is CodecProfile, "EXACT_CODEC_PROFILE_REQUIRED")
    CodecProfile.__post_init__(profile)
    _need(profile.qualified, "OPERATIONAL_QUALIFICATION_UNAVAILABLE_IN_SLICE_1A")
    return profile


def capture_profile(*, constructor_policies=()):
    """Explicitly hash fixed writer/runtime artifacts; never write or qualify.

    Native dependency closure and constructor qualification need later evidence.
    Missing optional artifacts remain explicit unresolved facts, never guessed
    identities. No Git calls, subprocesses, corpus reads or board generation.
    """
    import os
    from pathlib import Path
    import platform
    import sys
    import sysconfig

    def artifact(role, path):
        path = Path(path).resolve(strict=True)
        digest = sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(CHUNK_BYTES):
                digest.update(chunk)
                size += len(chunk)
        return {"role": role, "path": str(path), "byte_length": size, "sha256": digest.hexdigest()}

    try:
        directory = Path(__file__).resolve(strict=True).parent
        sources = tuple(artifact(role, directory / filename) for role, filename in (
            ("logical_records", "program_k_e2_records.py"),
            ("physical", "program_k_e2_physical.py"),
            ("worker_bundle", "program_k_e2_execution.py")))
        artifacts = [artifact("interpreter", sys.executable)]
        unresolved = ["native_dependency_closure", "operational_qualification"]
        if not constructor_policies:
            unresolved.append("constructor_policy_identities")
        base = getattr(sys, "_base_executable", None)
        if base and Path(base).resolve() != Path(sys.executable).resolve():
            artifacts.append(artifact("base_interpreter", base))
        native = getattr(zlib, "__file__", None)
        if native:
            artifacts.append(artifact("zlib_extension", native))
        else:
            unresolved.append("zlib_native_artifact")
        if os.name == "nt":
            # The loaded DLL identity is observed through its actual module handle.
            import ctypes
            path_buffer = ctypes.create_unicode_buffer(32768)
            get_name = ctypes.windll.kernel32.GetModuleFileNameW
            get_name.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32)
            get_name.restype = ctypes.c_uint32
            count = get_name(ctypes.c_void_p(sys.dllhandle), path_buffer, len(path_buffer))
            if 0 < count < len(path_buffer):
                artifacts.append(artifact("python_dll", path_buffer.value))
            else:
                unresolved.append("python_dll")
        runtime = {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "python_abi": sysconfig.get_config_var("SOABI") or sys.implementation.cache_tag,
            "platform": sys.platform,
            "zlib_build_version": zlib.ZLIB_VERSION,
            "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
            "zlib_provider_kind": ("extension-file" if native else "builtin-python-runtime"
                if os.name == "nt" and getattr(getattr(zlib, "__spec__", None), "origin", None) == "built-in"
                else "unresolved"),
            "zlib_native_owner_role": ("zlib_extension" if native else "python_dll"
                if os.name == "nt" and getattr(getattr(zlib, "__spec__", None), "origin", None) == "built-in"
                else "unresolved"),
            "artifacts": sorted(artifacts, key=lambda item: item["role"]),
            "unresolved": sorted(unresolved),
        }
        return profile_from_facts(writer_sources=sources, runtime=runtime,
                                  constructor_policies=constructor_policies)
    except PhysicalError:
        raise
    except (OSError, ValueError, TypeError, AttributeError):
        raise PhysicalError("PROFILE_CAPTURE_INCOMPLETE") from None


def _qualified_policy_facts(policies):
    _need(type(policies) is tuple and len(policies) == 2, "PROFILE_QUALIFIED_POLICY_COVERAGE")
    frozen = []
    for item, expected in zip(policies, _CONSTRUCTOR_POLICY_NAMES):
        _keys(item, ("name", "sha256"))
        _need(type(item["name"]) is str and item["name"] == expected, "PROFILE_QUALIFIED_POLICY_COVERAGE")
        _digest(item["sha256"])
        frozen.append(dict(item))
    return tuple(frozen)


def _profile_artifact(role, path):
    from pathlib import Path

    path = Path(path).resolve(strict=True)
    digest, size = sha256(), 0
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
    result = {"role": role, "path": str(path), "byte_length": size, "sha256": digest.hexdigest()}
    _artifact(result)
    return result


def _loaded_python_dll_path():
    """Resolve the actual loaded runtime handle; never guess or search for a DLL."""
    import ctypes
    import sys
    from pathlib import Path

    handle = getattr(sys, "dllhandle", None)
    _need(type(handle) is int and 0 < handle < 1 << (8 * ctypes.sizeof(ctypes.c_void_p)),
          "PROFILE_PYTHON_DLL_HANDLE")
    buffer = ctypes.create_unicode_buffer(32768)
    get_name = ctypes.windll.kernel32.GetModuleFileNameW
    get_name.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32)
    get_name.restype = ctypes.c_uint32
    count = get_name(ctypes.c_void_p(handle), buffer, len(buffer))
    _need(type(count) is int and 0 < count < len(buffer) and bool(buffer.value), "PROFILE_PYTHON_DLL_PATH")
    return Path(buffer.value).resolve(strict=True)


def _codec_self_check(build_version, runtime_version):
    _text(build_version)
    _text(runtime_version)
    _need((build_version, runtime_version) == (zlib.ZLIB_VERSION, zlib.ZLIB_RUNTIME_VERSION),
          "PROFILE_ZLIB_VERSION_BINDING")
    raw = encode_payload(b"x")
    logical = b"x" * 4096
    first, second = encode_payload(logical), encode_payload(logical)
    for result in (raw, first, second):
        _need(type(result) is tuple and len(result) == 2 and type(result[0]) is int
              and type(result[1]) is bytes, "PROFILE_CODEC_SELF_CHECK_FAILED")
    _need(raw == (RAW, b"x") and decode_payload(*raw, 1) == b"x",
          "PROFILE_CODEC_SELF_CHECK_FAILED")
    _need(first == second and first[0] == DEFLATE and len(first[1]) < len(logical)
          and decode_payload(*first, len(logical)) == logical, "PROFILE_CODEC_SELF_CHECK_FAILED")


def capture_qualified_profile(*, constructor_policies):
    """Read exact writer/native identities and check the tiny codec in process.

    This qualifies only the representation identity. It writes no artifact and
    does not authorize persistence, a performance diagnostic, R0 or Actual E2.
    """
    import os
    from pathlib import Path
    import platform
    import sys
    import sysconfig
    import types
    import zlib as imported_zlib

    policies = _qualified_policy_facts(constructor_policies)
    try:
        _need(type(zlib) is types.ModuleType and zlib is imported_zlib
              and zlib is sys.modules.get("zlib") and zlib.__name__ == "zlib", "PROFILE_ZLIB_MODULE")
        spec = getattr(zlib, "__spec__", None)
        _need(spec is not None and getattr(spec, "name", None) == "zlib", "PROFILE_ZLIB_SPEC")
        native, origin = getattr(zlib, "__file__", None), getattr(spec, "origin", None)
        if native is None:
            _need(os.name == "nt" and type(origin) is str and origin == "built-in", "PROFILE_ZLIB_PROVIDER")
            provider, owner = "builtin-python-runtime", "python_dll"
        else:
            _need(type(native) is str and bool(native) and type(origin) is str and bool(origin),
                  "PROFILE_ZLIB_PROVIDER")
            native = Path(native).resolve(strict=True)
            _need(native == Path(origin).resolve(strict=True), "PROFILE_ZLIB_ORIGIN_BINDING")
            provider, owner = "extension-file", "zlib_extension"
        directory = Path(__file__).resolve(strict=True).parent
        writers = tuple(_profile_artifact(role, directory / filename) for role, filename in (
            ("logical_records", "program_k_e2_records.py"), ("physical", "program_k_e2_physical.py"),
            ("worker_bundle", "program_k_e2_execution.py")))
        artifacts = [_profile_artifact("interpreter", sys.executable)]
        base = getattr(sys, "_base_executable", None)
        if base is not None:
            _need(type(base) is str and bool(base), "PROFILE_BASE_INTERPRETER")
            if Path(base).resolve(strict=True) != Path(sys.executable).resolve(strict=True):
                artifacts.append(_profile_artifact("base_interpreter", base))
        if os.name == "nt":
            artifacts.append(_profile_artifact("python_dll", _loaded_python_dll_path()))
        if provider == "extension-file":
            artifacts.append(_profile_artifact("zlib_extension", native))
        runtime = {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "python_abi": sysconfig.get_config_var("SOABI") or sys.implementation.cache_tag,
            "platform": sys.platform,
            "zlib_build_version": zlib.ZLIB_VERSION,
            "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
            "zlib_provider_kind": provider,
            "zlib_native_owner_role": owner,
            "artifacts": sorted(artifacts, key=lambda item: item["role"]),
            "unresolved": [],
        }
        _codec_self_check(runtime["zlib_build_version"], runtime["zlib_runtime_version"])
        return CodecProfile(_json({"schema_version": 1, "status": "QUALIFIED", "contract": _profile_contract(),
            "writer_sources": list(writers), "runtime": runtime, "constructor_policies": list(policies)}))
    except PhysicalError:
        raise
    except (OSError, ValueError, TypeError, AttributeError, ImportError, zlib.error):
        raise PhysicalError("PROFILE_CAPTURE_INCOMPLETE") from None
