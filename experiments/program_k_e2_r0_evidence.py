"""Pure R0 metadata identities and the unchanged closed V1 fact vocabulary.

No capture, launch, persistence, measurement or qualification occurs here. V2
identities distinguish physical archive bytes from logical workload bytes; they
do not establish either measurement or numerical admission. Historical V1 facts
remain independent of the current runtime and codec profile.
"""

from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
import json
from types import MappingProxyType

from experiments import program_k_e2_records as records
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_operational as operational
from experiments import program_k_e2_readiness as readiness


class EvidenceError(ValueError):
    """Unsupported, mixed or noncanonical metadata identity/fact."""


def _need(condition, reason):
    if not condition:
        raise EvidenceError(reason)


R0A_OBSERVATIONS_V1 = "program-k-e2-r0a-observations/v1"
R0A_OBSERVATIONS_V2 = "program-k-e2-r0a-observations/v2"
R0_RUN_V1 = "program-k-e2-r0-run/v1"
R0_RUN_V2 = "program-k-e2-r0-run/v2"
R0B_EXPERIMENT_V1 = "program-k-e2-r0b-experiment/v1"
R0B_EXPERIMENT_V2 = "program-k-e2-r0b-experiment/v2"
_V1_SCHEMAS = (R0A_OBSERVATIONS_V1, R0_RUN_V1, R0B_EXPERIMENT_V1)
_V2_SCHEMAS = (R0A_OBSERVATIONS_V2, R0_RUN_V2, R0B_EXPERIMENT_V2)


def schema_version(schema):
    """Classify an explicitly supplied schema, never a filename or payload."""
    _need(type(schema) is str, "EXPLICIT_R0_SCHEMA_REQUIRED")
    if schema in _V1_SCHEMAS:
        return 1
    _need(schema in _V2_SCHEMAS, "UNKNOWN_R0_SCHEMA")
    return 2


def _profile_identity(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "CANONICAL_PROFILE_SHA256_REQUIRED")


_BASIS_IDENTITIES = (
    ("logical_record_codec", "program-k-e2-records/v1"),
    ("logical_counting", "sum-exact-REC.encode-record-bytes"),
    ("durable_counting", "sum-complete-attributable-PKE2RF02-frames"),
    ("record_frame_format", "PKE2RF02"),
    ("worker_container_format", "PKE2WB02"),
    ("qualification_policy", "dual-independent-ceil-3-over-2/v1"),
)


@dataclass(frozen=True, slots=True)
class SizeBasisV2:
    """Identity only: physical and logical counts have no cross-credit.

    The profile digest is supplied evidence, not a qualification claim. No
    alternative counting, frame/container or qualification policy is supported.
    """

    codec_profile_sha256: str
    logical_record_codec: str = "program-k-e2-records/v1"
    logical_counting: str = "sum-exact-REC.encode-record-bytes"
    durable_counting: str = "sum-complete-attributable-PKE2RF02-frames"
    record_frame_format: str = "PKE2RF02"
    worker_container_format: str = "PKE2WB02"
    qualification_policy: str = "dual-independent-ceil-3-over-2/v1"

    def __post_init__(self):
        _profile_identity(self.codec_profile_sha256)
        for name, expected in _BASIS_IDENTITIES:
            value = getattr(self, name)
            _need(type(value) is str and value == expected, "SIZE_BASIS_" + name.upper())


def _basis(basis):
    _need(type(basis) is SizeBasisV2, "EXACT_SIZE_BASIS_V2_REQUIRED")
    SizeBasisV2.__post_init__(basis)


def encode_size_basis(basis):
    _basis(basis)
    node = {field.name: getattr(basis, field.name) for field in fields(SizeBasisV2)}
    return json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _unique(pairs):
    node = dict(pairs)
    _need(len(node) == len(pairs), "DUPLICATE_SIZE_BASIS_FIELD")
    return node


def _no_float(_):
    raise EvidenceError("METADATA_FLOAT_FORBIDDEN")


def decode_size_basis(data):
    _need(type(data) is bytes, "EXACT_SIZE_BASIS_BYTES_REQUIRED")
    # Every supported field is fixed text except the exactly 64-character SHA.
    _need(len(data) == len(encode_size_basis(SizeBasisV2("0" * 64))), "SIZE_BASIS_LENGTH")
    try:
        node = json.loads(data.decode("ascii"), object_pairs_hook=_unique,
                          parse_float=_no_float, parse_constant=_no_float)
        _need(type(node) is dict and set(node) == {field.name for field in fields(SizeBasisV2)},
              "SIZE_BASIS_FIELDS")
        basis = SizeBasisV2(**node)
        _need(encode_size_basis(basis) == data, "NONCANONICAL_SIZE_BASIS")
        return basis
    except EvidenceError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError):
        raise EvidenceError("MALFORMED_SIZE_BASIS") from None


def validate_metadata_identity(schema, *, size_basis=None, expected_profile_sha256=None):
    """Validate explicit version/basis dispatch, returning the selected version.

    V1 accepts no V2 basis or profile binding. Its fact decoder needs no current
    profile. V2 requires the exact basis and, when supplied, expected profile
    equality. No V2 observation/run payload or migration is defined here.
    """
    version = schema_version(schema)
    if version == 1:
        _need(size_basis is None and expected_profile_sha256 is None, "V1_HAS_NO_V2_BASIS_OR_PROFILE")
    else:
        _basis(size_basis)
        if expected_profile_sha256 is not None:
            _profile_identity(expected_profile_sha256)
            _need(size_basis.codec_profile_sha256 == expected_profile_sha256, "CODEC_PROFILE_MISMATCH")
    return version


# Exact historical harness vocabulary. No class discovery or module lookup.
_FACT_TYPES = MappingProxyType({cls.__name__: cls for cls in (
    operational.OperatingEnvelope, operational.R0Work, operational.R0UnitMeasurement,
    operational.R0ComponentMeasurement, operational.R0SetupMeasurement, operational._R0Observation,
    operational.UnitReceipt, operational.CoordinatorResult,
    readiness.AmendmentProvenance, readiness.SubsetCounts, readiness.SyntheticCorpusSelection,
    readiness.SyntheticWorkload, readiness.R0APlan, readiness.ComponentMeasurement,
    readiness.OracleMeasurement, readiness.WallRouteMeasurement, readiness.ReferenceMeasurement,
    readiness.RouteContainment, readiness.R0AConcurrencyMeasurement, readiness.ComponentSizes,
    readiness.SupportingStreams, readiness.PhaseMeasurement, readiness.R0BMeasurement,
)})
_FACT_ENUMS = MappingProxyType({cls.__name__: cls for cls in (
    operational.R0Component, execution.WorkerKind, records.AuditStatus, records.Phase,
    readiness.WallAccounting, readiness.ByteAccounting,
)})
_FACT_RECORDS = (records.BoardIdentity, records.RuntimeIdentity, records.SourceBlobIdentity,
                 records.StreamDigest)
_LOCAL_FACT_FIELDS = (
    ("RunProvenance", ("selection_source_head", "r0_harness_source_head", "sources", "working_files",
                       "runtime", "executable", "dont_write_bytecode")),
    ("FileFact", ("path", "byte_length", "sha256")),
    ("ArchiveAccounting", ("files", "attributable_bytes", "fixed_allowance_bytes", "archive_bytes")),
    ("FinalizationFact", ("stages", "wall_ns", "max_progress_gap_ns", "progress_events", "complete")),
)


def _local_facts(local_fact_types):
    """Validate the four harness-owned types without importing their owner.

    This is a closed compatibility parameter, not a registration mechanism.
    Callers not using harness-local facts omit it; no global registry is changed.
    """
    _need(type(local_fact_types) is tuple and len(local_fact_types) in (0, 4),
          "CLOSED_LOCAL_FACT_TYPES_REQUIRED")
    result = {}
    for cls, (name, names) in zip(local_fact_types, _LOCAL_FACT_FIELDS):
        _need(type(cls) is type and cls.__name__ == cls.__qualname__ == name
              and cls.__module__ == "experiments.program_k_e2_r0_harness"
              and is_dataclass(cls), "CLOSED_LOCAL_FACT_TYPE_IDENTITY")
        _need(tuple(field.name for field in fields(cls)) == names
              and cls.__dataclass_params__.frozen and getattr(cls, "__slots__", None) == names,
              "CLOSED_LOCAL_FACT_TYPE_FIELDS")
        validator = getattr(cls, "__post_init__", None)
        _need(callable(validator) and getattr(validator, "__module__", None) == cls.__module__
              and getattr(validator, "__qualname__", None) == name + ".__post_init__",
              "CLOSED_LOCAL_FACT_VALIDATOR")
        result[name] = cls
    return result


def fact_node_v1(value, *, local_fact_types=()):
    """Encode the historical node shape, preserving exact scalar/record bytes."""
    local = _local_facts(local_fact_types)
    return _fact_node(value, local)


def _fact_node(value, local):
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is bytes:
        return {"bytes": value.hex()}
    if type(value) is Fraction:
        return {"fraction": [value.numerator, value.denominator]}
    if type(value) is tuple:
        return [_fact_node(v, local) for v in value]
    if type(value) is records.StreamDigest:
        records.StreamDigest.__post_init__(value)
        return {"stream": [value.name, value.sha256, value.byte_length, value.record_count]}
    if type(value) in _FACT_RECORDS:
        return {"record": records.encode(value).decode("ascii")}
    if type(value) in _FACT_ENUMS.values():
        return {"enum": type(value).__name__, "value": value.value}
    _need(type(value) in _FACT_TYPES.values() or type(value) in local.values(), "UNSUPPORTED_R0_METADATA")
    if hasattr(type(value), "__post_init__"):
        type(value).__post_init__(value)
    return {"fact": type(value).__name__, "fields":
            {field.name: _fact_node(getattr(value, field.name), local) for field in fields(value)}}


def fact_read_v1(node, *, local_fact_types=()):
    """Decode only the historical closed node vocabulary, without capture/I/O."""
    local = _local_facts(local_fact_types)
    return _fact_read(node, local)


def _fact_read(node, local):
    if node is None or type(node) in (str, int, bool):
        return node
    if type(node) is list:
        return tuple(_fact_read(v, local) for v in node)
    _need(type(node) is dict and all(type(key) is str for key in node), "INVALID_R0_METADATA")
    if set(node) == {"bytes"}:
        _need(type(node["bytes"]) is str, "INVALID_R0_BYTES")
        try:
            value = bytes.fromhex(node["bytes"])
        except ValueError:
            raise EvidenceError("INVALID_R0_BYTES") from None
        _need(value.hex() == node["bytes"], "NONCANONICAL_R0_BYTES")
        return value
    if set(node) == {"fraction"}:
        pair = node["fraction"]
        _need(type(pair) is list and len(pair) == 2, "INVALID_R0_FRACTION")
        a, b = pair
        _need(type(a) is int and type(b) is int and b > 0, "INVALID_R0_FRACTION")
        value = Fraction(a, b)
        _need((value.numerator, value.denominator) == (a, b), "NONCANONICAL_R0_FRACTION")
        return value
    if set(node) == {"stream"}:
        _need(type(node["stream"]) is list and len(node["stream"]) == 4, "INVALID_METADATA_STREAM")
        return records.StreamDigest(*node["stream"])
    if set(node) == {"record"}:
        _need(type(node["record"]) is str and node["record"].isascii(), "INVALID_METADATA_RECORD")
        value = records.decode(node["record"].encode("ascii"))
        _need(type(value) in _FACT_RECORDS, "UNSUPPORTED_METADATA_RECORD")
        return value
    if set(node) == {"enum", "value"}:
        _need(type(node["enum"]) is str and node["enum"] in _FACT_ENUMS, "UNSUPPORTED_METADATA_ENUM")
        _need(type(node["value"]) is str, "INVALID_METADATA_ENUM_VALUE")
        return _FACT_ENUMS[node["enum"]](node["value"])
    _need(set(node) == {"fact", "fields"} and type(node["fact"]) is str
          and (node["fact"] in _FACT_TYPES or node["fact"] in local), "UNSUPPORTED_METADATA_FACT")
    cls = _FACT_TYPES.get(node["fact"]) or local[node["fact"]]
    _need(type(node["fields"]) is dict and all(type(key) is str for key in node["fields"])
          and set(node["fields"]) == {field.name for field in fields(cls)}, "METADATA_FIELDS_MISMATCH")
    return cls(**{name: _fact_read(value, local) for name, value in node["fields"].items()})
