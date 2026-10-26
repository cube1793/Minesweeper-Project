"""Pure R0 metadata identities and the unchanged closed V1 fact vocabulary.

No capture, launch, persistence, measurement or qualification occurs here. V2
identities distinguish physical archive bytes from logical workload bytes; they
do not establish either measurement or numerical admission. Historical V1 facts
remain independent of the current runtime and codec profile.
"""

from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
from hashlib import sha256
import json
from types import MappingProxyType

from experiments import program_k_e2_records as records
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_operational as operational
from experiments import program_k_e2_readiness as readiness
from experiments import program_k_e2_physical as physical


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


# Separate closed V2 metadata. These types never enter the historical registry.
V2_MATERIALIZATION_MAPPING_POLICY = "synthetic-2x1-to-reference-30x16-for-k-or-d/v1"
V2_FAMILY_POLICY_REASONS = frozenset((
    "SYNTHETIC_BOTH_MINIMA_SHORTFALL", "SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL",
    "SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL", "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT"))
V2_TEXT_REJECTION_REASONS = V2_FAMILY_POLICY_REASONS | frozenset((
    "SYNTHETIC_TEXT_LOGICAL_RECORD_CAP", "SYNTHETIC_TEXT_LSUM_CAP", "SYNTHETIC_TEXT_LLEGACY_CAP",
    "SYNTHETIC_TEXT_CANONICAL_RECORD_FAILURE", "SYNTHETIC_TEXT_SEMANTIC_OR_PRIOR_FAILURE",
    "SYNTHETIC_TEXT_SUNIT_CAP", "SYNTHETIC_TEXT_WNEW_CAP", "SYNTHETIC_TEXT_FRAME_FAILURE",
    "SYNTHETIC_TEXT_WIRE_FAILURE"))
V2_REFERENCE_REJECTION_REASONS = (V2_FAMILY_POLICY_REASONS - {"SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT"}) | frozenset((
    "LOGICAL_MINIMUM_COMPOSITE_CAP", "REFERENCE_SUNIT_CAP", "REFERENCE_WNEW_CAP",
    "REFERENCE_PHYSICAL_MINIMUM_COMPOSITE_CAP", "WORKER_PAYLOAD_CAP", "WORKER_LEGACY_CAP",
    "WORKER_WIRE_CAP", "WB02_METADATA_CAP", "LOGICAL_PAYLOAD_CAP", "WB02_WORK_KIND_BINDING",
    "WB02_BOUNDARY_VALIDATION_FAILED", "KCONTROL_REFERENCE_BINDING", "REPEAT_FIRST_PREMISE_BINDING",
    "REPEAT_FIRST_HEADER_BINDING", "CONTROL_O4_REFERENCE_BINDING", "CONTROL_O4_DECISION_BINDING",
    "CONTROL_DETERMINISM_SUMMARY_MISMATCH", "KCONTROL_CLASSIFICATION_MISMATCH",
    "NONCANONICAL_OR_WRONG_RECORD_FAMILY", "WRONG_LOGICAL_RECORD_TYPE", "NONCANONICAL_LOGICAL_BYTES",
    "PREPARED_PAYLOAD_LOGICAL_MISMATCH", "CONTEXTUAL_CRC_MISMATCH", "UNEXPECTED_LOGICAL_KEY",
    "MODE_LENGTH_MISMATCH", "REFERENCE_MUTATION_SCOPE", "REFERENCE_WIRE_SIZE_BINDING",
    "REFERENCE_SELECTED_FACT_BINDING", "REFERENCE_SELECTED_SIZE_BINDING",
    "REFERENCE_CANONICAL_RECORD_FAILURE", "REFERENCE_CANDIDATE_BINDING_OR_CAP_FAILURE"))
_V2_TRIAL_FIELDS = ("ordinal", "knob", "actual_physical_bytes", "actual_logical_bytes",
                    "physical_margin", "logical_margin", "eligible", "rejection_reason")
_V2_CONSTRUCTOR_FIELDS = ("position", "family", "constructor_kind", "physical_target", "logical_target",
    "selected_knob", "selected_trial_ordinal", "actual_physical_bytes", "actual_logical_bytes",
    "physical_margin", "logical_margin", "physical_excess", "logical_excess", "text_window_applies",
    "text_window_upper_bound", "zero_oracle", "trials")
_V2_TOTAL_FIELDS = ("family", "physical_bytes", "logical_bytes", "physical_excess")
_V2_MATERIALIZATION_FIELDS = ("schema", "size_basis", "codec_profile_bytes", "codec_profile_sha256",
    "source_plan_identity", "materialization_plan_identity", "mapping_policy", "protocol_seed", "run_id",
    "runtime", "work_count", "family_counts", "targets", "streams", "constructor_facts", "family_totals",
    "physical_minimum_total", "fixed_allowance_reservation", "b_proc", "committed_procedural_excess",
    "remaining_procedural_budget", "durable_operation_count", "durable_primary_count",
    "attributable_experiment_bytes", "current_sealed_pkf_bytes",
    "runtime_monitor_peak_coordinator_private_bytes", "progress_complete", "cleanup_complete",
    "synthetic_non_evidence")
_V2_STREAM_FIELDS = ("name", "sha256", "byte_length", "record_count")


def _v2_integer(value, minimum=0, maximum=None):
    _need(type(value) is int and value >= minimum and (maximum is None or value <= maximum),
          "V2_EXACT_INTEGER_REQUIRED")


def _v2_signed_integer(value):
    _need(type(value) is int, "V2_EXACT_SIGNED_INTEGER_REQUIRED")


def _v2_boolean(value):
    _need(type(value) is bool, "V2_EXACT_BOOLEAN_REQUIRED")


def _v2_family(value):
    _need(type(value) is str and value in readiness.V2_FAMILIES, "V2_EXACT_FAMILY_REQUIRED")


def _v2_exact(value, cls):
    _need(type(value) is cls, "V2_EXACT_EVIDENCE_TYPE_REQUIRED")
    cls.__post_init__(value)


@dataclass(frozen=True, slots=True)
class V2ConstructorTrialEvidence:
    """Closed runtime provenance, not a reconstruction of rejected candidates."""

    ordinal: int
    knob: int
    actual_physical_bytes: int | None
    actual_logical_bytes: int | None
    physical_margin: int | None
    logical_margin: int | None
    eligible: bool
    rejection_reason: str | None

    def __post_init__(self):
        _v2_integer(self.ordinal, 1, 8)
        _v2_integer(self.knob, 0, physical.MAX_PAYLOAD_BYTES)
        for actual, margin in ((self.actual_physical_bytes, self.physical_margin),
                               (self.actual_logical_bytes, self.logical_margin)):
            _need((actual is None) == (margin is None), "V2_TRIAL_MARGIN_AVAILABILITY")
            if actual is not None:
                _v2_integer(actual)
                _v2_signed_integer(margin)
        _v2_boolean(self.eligible)
        if self.eligible:
            _need(self.rejection_reason is None and self.actual_physical_bytes is not None
                  and self.actual_logical_bytes is not None, "V2_ELIGIBLE_TRIAL_SHAPE")
        else:
            _need(type(self.rejection_reason) is str
                  and self.rejection_reason in V2_TEXT_REJECTION_REASONS | V2_REFERENCE_REJECTION_REASONS,
                  "V2_CLOSED_CONSTRUCTOR_REJECTION_REQUIRED")


@dataclass(frozen=True, slots=True)
class V2ConstructorEvidence:
    position: int
    family: str
    constructor_kind: str
    physical_target: int
    logical_target: int
    selected_knob: int
    selected_trial_ordinal: int
    actual_physical_bytes: int
    actual_logical_bytes: int
    physical_margin: int
    logical_margin: int
    physical_excess: int
    logical_excess: int
    text_window_applies: bool
    text_window_upper_bound: int | None
    zero_oracle: bool
    trials: tuple

    def __post_init__(self):
        _v2_integer(self.position, 0, 9999)
        _v2_family(self.family)
        expected_kind = "reference" if self.family == "reference" else "text"
        _need(type(self.constructor_kind) is str and self.constructor_kind == expected_kind,
              "V2_CONSTRUCTOR_KIND_BINDING")
        for value in (self.physical_target, self.logical_target, self.actual_physical_bytes,
                      self.actual_logical_bytes, self.physical_excess, self.logical_excess):
            _v2_integer(value)
        _v2_signed_integer(self.physical_margin)
        _v2_signed_integer(self.logical_margin)
        maximum = 2_581_110 if expected_kind == "reference" else physical.MAX_PAYLOAD_BYTES
        _v2_integer(self.selected_knob, 0, maximum)
        _v2_integer(self.selected_trial_ordinal, 0, 8)
        _v2_boolean(self.text_window_applies)
        _v2_boolean(self.zero_oracle)
        if self.text_window_upper_bound is not None:
            _v2_integer(self.text_window_upper_bound)
        _need(type(self.trials) is tuple and len(self.trials) <= 8, "V2_BOUNDED_TRIAL_TUPLE_REQUIRED")
        reasons = V2_REFERENCE_REJECTION_REASONS if expected_kind == "reference" else V2_TEXT_REJECTION_REASONS
        for trial in self.trials:
            _v2_exact(trial, V2ConstructorTrialEvidence)
            _v2_integer(trial.knob, 0, maximum)
            _need(trial.eligible or trial.rejection_reason in reasons, "V2_CONSTRUCTOR_REJECTION_KIND")
        _need(tuple(trial.ordinal for trial in self.trials) == tuple(range(1, len(self.trials) + 1))
              and len({trial.knob for trial in self.trials}) == len(self.trials), "V2_CANONICAL_TRIAL_SEQUENCE")
        if self.zero_oracle:
            _need(self.family in ("oracle_primary", "oracle_repeat") and not self.trials
                  and self.selected_knob == self.selected_trial_ordinal == 0
                  and self.physical_target == self.logical_target == 0
                  and self.actual_physical_bytes == self.actual_logical_bytes == 0,
                  "V2_ZERO_ORACLE_EVIDENCE_SHAPE")
        else:
            _need(bool(self.trials) and self.selected_trial_ordinal > 0, "V2_SELECTED_TRIAL_REQUIRED")


@dataclass(frozen=True, slots=True)
class V2FamilyTotalEvidence:
    family: str
    physical_bytes: int
    logical_bytes: int
    physical_excess: int

    def __post_init__(self):
        _v2_family(self.family)
        for value in (self.physical_bytes, self.logical_bytes, self.physical_excess):
            _v2_integer(value)


@dataclass(frozen=True, slots=True)
class V2MaterializationEvidence:
    """Sealed materialization claims, still requiring independent disk readback.

    The all-check monitor peak is runtime provenance. It is distinct from the
    maximum independently derivable from durable per-operation samples.
    """

    schema: str
    size_basis: SizeBasisV2
    codec_profile_bytes: bytes
    codec_profile_sha256: str
    source_plan_identity: str
    materialization_plan_identity: str
    mapping_policy: str
    protocol_seed: bytes
    run_id: str
    runtime: records.RuntimeIdentity
    work_count: int
    family_counts: tuple
    targets: readiness.DualComponentSizes
    streams: tuple
    constructor_facts: tuple
    family_totals: tuple
    physical_minimum_total: int
    fixed_allowance_reservation: int
    b_proc: int
    committed_procedural_excess: int
    remaining_procedural_budget: int
    durable_operation_count: int
    durable_primary_count: int
    attributable_experiment_bytes: int
    current_sealed_pkf_bytes: int
    runtime_monitor_peak_coordinator_private_bytes: int
    progress_complete: bool
    cleanup_complete: bool
    synthetic_non_evidence: bool

    def __post_init__(self):
        _need(type(self.schema) is str and self.schema == R0B_EXPERIMENT_V2, "V2_MATERIALIZATION_SCHEMA")
        _basis(self.size_basis)
        for value in (self.codec_profile_sha256, self.source_plan_identity, self.materialization_plan_identity):
            _profile_identity(value)
        _need(type(self.codec_profile_bytes) is bytes, "V2_CANONICAL_PROFILE_BYTES_REQUIRED")
        profile = physical.decode_profile(self.codec_profile_bytes)
        physical.require_qualified_profile(profile)
        _need(profile.sha256.hex() == self.codec_profile_sha256 == self.size_basis.codec_profile_sha256,
              "V2_PROFILE_BYTES_IDENTITY_MISMATCH")
        _need(type(self.mapping_policy) is str and self.mapping_policy == V2_MATERIALIZATION_MAPPING_POLICY,
              "V2_MATERIALIZATION_MAPPING_POLICY")
        _need(type(self.protocol_seed) is bytes and len(self.protocol_seed) == 32, "V2_PROTOCOL_SEED_REQUIRED")
        _need(type(self.run_id) is str and bool(self.run_id), "V2_RUN_ID_REQUIRED")
        _v2_exact(self.runtime, records.RuntimeIdentity)
        _v2_integer(self.work_count, 1, 10000)
        _need(type(self.family_counts) is tuple and len(self.family_counts) == len(readiness.V2_FAMILIES),
              "V2_FAMILY_COUNTS_REQUIRED")
        for pair, family in zip(self.family_counts, readiness.V2_FAMILIES):
            _need(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str and pair[0] == family,
                  "V2_FAMILY_COUNT_ORDER")
            _v2_integer(pair[1], 0, self.work_count)
        _v2_exact(self.targets, readiness.DualComponentSizes)
        _need(type(self.streams) is tuple, "V2_STREAM_SEALS_REQUIRED")
        for stream in self.streams:
            _v2_exact(stream, records.StreamDigest)
        _need(tuple(stream.name for stream in self.streams) == execution.STREAM_NAMES + ("operations", "resources"),
              "V2_STREAM_SEAL_COVERAGE")
        _need(type(self.constructor_facts) is tuple and len(self.constructor_facts) <= 6 * self.work_count,
              "V2_CONSTRUCTOR_FACTS_REQUIRED")
        for fact in self.constructor_facts:
            _v2_exact(fact, V2ConstructorEvidence)
            _need(fact.position < self.work_count, "V2_CONSTRUCTOR_POSITION")
        _need(type(self.family_totals) is tuple, "V2_FAMILY_TOTALS_REQUIRED")
        for total in self.family_totals:
            _v2_exact(total, V2FamilyTotalEvidence)
        _need(tuple(total.family for total in self.family_totals) == readiness.V2_FAMILIES,
              "V2_FAMILY_TOTAL_ORDER")
        for value in (self.physical_minimum_total, self.fixed_allowance_reservation, self.b_proc,
                      self.committed_procedural_excess, self.remaining_procedural_budget,
                      self.durable_operation_count, self.durable_primary_count,
                      self.attributable_experiment_bytes, self.current_sealed_pkf_bytes):
            _v2_integer(value)
        _v2_integer(self.runtime_monitor_peak_coordinator_private_bytes, 1)
        for value in (self.progress_complete, self.cleanup_complete, self.synthetic_non_evidence):
            _v2_boolean(value)
            _need(value, "V2_COMPLETED_SYNTHETIC_MATERIALIZATION_REQUIRED")


def _v2_json(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _v2_fields(node, names):
    _need(type(node) is dict and all(type(key) is str for key in node) and set(node) == set(names),
          "V2_CLOSED_METADATA_FIELDS")


def _v2_hex(data):
    _need(type(data) is str, "V2_CANONICAL_HEX_REQUIRED")
    try:
        value = bytes.fromhex(data)
    except ValueError:
        raise EvidenceError("V2_CANONICAL_HEX_REQUIRED") from None
    _need(value.hex() == data, "V2_CANONICAL_HEX_REQUIRED")
    return value


def _v2_unique(pairs):
    result = dict(pairs)
    _need(len(result) == len(pairs), "V2_DUPLICATE_METADATA_FIELD")
    return result


def _v2_trial_node(value):
    return {name: getattr(value, name) for name in _V2_TRIAL_FIELDS}


def _v2_constructor_node(value):
    node = {name: getattr(value, name) for name in _V2_CONSTRUCTOR_FIELDS if name != "trials"}
    node["trials"] = [_v2_trial_node(trial) for trial in value.trials]
    return node


def encode_materialization_v2(value):
    """Explicit closed V2 encoding, including exactly one final ASCII LF."""
    _v2_exact(value, V2MaterializationEvidence)
    nested = ("size_basis", "codec_profile_bytes", "protocol_seed", "runtime", "family_counts",
              "targets", "streams", "constructor_facts", "family_totals")
    node = {name: getattr(value, name) for name in _V2_MATERIALIZATION_FIELDS if name not in nested}
    node.update(size_basis=json.loads(encode_size_basis(value.size_basis)),
        codec_profile_bytes=value.codec_profile_bytes.hex(), protocol_seed=value.protocol_seed.hex(),
        runtime=records.encode(value.runtime).decode("ascii"),
        family_counts=[[family, count] for family, count in value.family_counts],
        targets={axis: {family: getattr(getattr(value.targets, axis), family) for family in readiness.V2_FAMILIES}
                 for axis in ("physical", "logical")},
        streams=[{name: getattr(stream, name) for name in _V2_STREAM_FIELDS} for stream in value.streams],
        constructor_facts=[_v2_constructor_node(fact) for fact in value.constructor_facts],
        family_totals=[{name: getattr(total, name) for name in _V2_TOTAL_FIELDS} for total in value.family_totals])
    return _v2_json(node) + b"\n"


def decode_materialization_v2(data, *, expected_profile_sha256=None):
    """Decode canonical V2 claims without granting independent readback status."""
    _need(type(data) is bytes and 0 < len(data) <= physical.MAX_PAYLOAD_BYTES,
          "V2_BOUNDED_METADATA_BYTES_REQUIRED")
    if expected_profile_sha256 is not None:
        _profile_identity(expected_profile_sha256)
    try:
        node = json.loads(data.decode("ascii"), object_pairs_hook=_v2_unique,
                          parse_float=_no_float, parse_constant=_no_float)
        _v2_fields(node, _V2_MATERIALIZATION_FIELDS)
        values = dict(node)
        values["size_basis"] = decode_size_basis(_v2_json(node["size_basis"]))
        values["codec_profile_bytes"] = _v2_hex(node["codec_profile_bytes"])
        values["protocol_seed"] = _v2_hex(node["protocol_seed"])
        _need(type(node["runtime"]) is str and node["runtime"].isascii(), "V2_RUNTIME_RECORD_REQUIRED")
        values["runtime"] = records.decode(node["runtime"].encode("ascii"))
        _need(type(node["family_counts"]) is list, "V2_FAMILY_COUNTS_REQUIRED")
        for pair in node["family_counts"]:
            _need(type(pair) is list and len(pair) == 2, "V2_FAMILY_COUNT_PAIR_REQUIRED")
        values["family_counts"] = tuple(tuple(pair) for pair in node["family_counts"])
        _v2_fields(node["targets"], ("physical", "logical"))
        for axis in ("physical", "logical"):
            _v2_fields(node["targets"][axis], readiness.V2_FAMILIES)
        values["targets"] = readiness.DualComponentSizes(*(readiness.ComponentSizes(**node["targets"][axis])
                                                            for axis in ("physical", "logical")))
        _need(type(node["streams"]) is list, "V2_STREAM_SEALS_REQUIRED")
        streams = []
        for stream in node["streams"]:
            _v2_fields(stream, _V2_STREAM_FIELDS)
            streams.append(records.StreamDigest(**stream))
        values["streams"] = tuple(streams)
        _need(type(node["constructor_facts"]) is list, "V2_CONSTRUCTOR_FACTS_REQUIRED")
        facts = []
        for fact in node["constructor_facts"]:
            _v2_fields(fact, _V2_CONSTRUCTOR_FIELDS)
            _need(type(fact["trials"]) is list and len(fact["trials"]) <= 8, "V2_BOUNDED_TRIAL_TUPLE_REQUIRED")
            trials = []
            for trial in fact["trials"]:
                _v2_fields(trial, _V2_TRIAL_FIELDS)
                trials.append(V2ConstructorTrialEvidence(**trial))
            facts.append(V2ConstructorEvidence(**dict(fact, trials=tuple(trials))))
        values["constructor_facts"] = tuple(facts)
        _need(type(node["family_totals"]) is list, "V2_FAMILY_TOTALS_REQUIRED")
        totals = []
        for total in node["family_totals"]:
            _v2_fields(total, _V2_TOTAL_FIELDS)
            totals.append(V2FamilyTotalEvidence(**total))
        values["family_totals"] = tuple(totals)
        value = V2MaterializationEvidence(**values)
        if expected_profile_sha256 is not None:
            _need(value.codec_profile_sha256 == expected_profile_sha256, "V2_EXPECTED_PROFILE_MISMATCH")
        _need(encode_materialization_v2(value) == data, "V2_NONCANONICAL_METADATA")
        return value
    except EvidenceError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise EvidenceError("V2_MALFORMED_MATERIALIZATION_METADATA") from None


def plan_identity_v2(plan):
    """Incremental compact digest of exact work identities; no corpus selection."""
    _need(type(plan) is tuple and 0 < len(plan) <= 10000, "V2_EXACT_PLAN_REQUIRED")
    digest = sha256(b"PROGRAM_K_V2_MATERIALIZATION_PLAN_IDENTITY_V1\0")
    for position, work in enumerate(plan):
        _v2_exact(work, execution.BoardWork)
        _need(work.position == position, "V2_PLAN_POSITION_ORDER")
        _v2_exact(work.runtime, records.RuntimeIdentity)
        node = {"position": work.position, "board": records.encode(work.board).decode("ascii"),
            "protocol_seed": work.protocol_seed.hex(), "run_id": work.run_id,
            "runtime": records.encode(work.runtime).decode("ascii"),
            "oracle_b_selected": work.oracle_b_selected, "determinism_selected": work.determinism_selected,
            "k_control_selected": work.k_control_selected}
        digest.update(_v2_json(node) + b"\n")
    return digest.hexdigest()
