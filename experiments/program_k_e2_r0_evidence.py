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
from experiments import program_k_e2_identity as identity


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


# Archive manifests have registry order; CompletionReceipt keeps its independent
# historical sorted-name order. Neither order changes the other owner's codec.
V2_ARCHIVE_STREAM_NAMES = execution.STREAM_NAMES + (
    "operations", "resources", "qualification_identity", "postprocessing_operations")
V2_ARCHIVE_ATTRIBUTABLE_PATHS = tuple("streams/" + name + ".pkf" for name in execution.STREAM_NAMES)
V2_ARCHIVE_PRE_MANIFEST_PATHS = tuple(sorted(V2_ARCHIVE_ATTRIBUTABLE_PATHS + (
    "streams/operations.pkf", "streams/resources.pkf", "streams/qualification_identity.pkf",
    "streams/materialization-v2.json", "postprocessing/postprocessing_operations.pkf",
    "postprocessing/analysis.json", "postprocessing/report.html", "coordinator.json", "status.json")))
V2_ARCHIVE_FINAL_PATHS = tuple(sorted(V2_ARCHIVE_PRE_MANIFEST_PATHS + ("manifest.json", "COMPLETE.json")))
V2_ARCHIVE_SCOPE = "experiment-local-all-bytes;execution-pkf-attributable;all-other-files-fixed-support"
_V2_ARCHIVE_FILE_FIELDS = ("path", "byte_length", "sha256")
_V2_ARCHIVE_FIELDS = (
    "schema", "kind", "classification", "synthetic_non_evidence", "selection_receipt_sha256",
    "corpus_sha256", "source_sha256", "protocol_sha256", "materialization_file", "codec_profile_sha256",
    "size_basis", "source_plan_identity", "materialization_plan_identity", "family_counts", "targets",
    "family_totals", "e_final", "b_proc", "remaining_procedural_budget", "physical_minimum_total",
    "materialization_readback_complete", "readback_streams", "durable_operation_count", "durable_primary_count",
    "durable_sample_max_coordinator_private_bytes", "runtime_monitor_peak_coordinator_private_bytes",
    "runtime_peak_is_independent", "constructor_rejections_are_runtime_provenance",
    "qualification_identity_stream", "postprocessing_operations_stream", "analysis_file", "report_file",
    "streams", "inventory_before_manifest_receipt", "attributable_bytes", "projected_fixed_bytes",
    "projected_archive_bytes", "fixed_allowance_cap", "archive_cap", "scope")


@dataclass(frozen=True, slots=True)
class V2ArchiveFileEvidence:
    """Exact file identity in the closed experiment-local V2 layout."""

    path: str
    byte_length: int
    sha256: str

    def __post_init__(self):
        _need(type(self.path) is str and self.path in V2_ARCHIVE_FINAL_PATHS, "V2_ARCHIVE_FILE_PATH")
        _v2_integer(self.byte_length)
        _profile_identity(self.sha256)


@dataclass(frozen=True, slots=True)
class V2ArchiveManifestEvidence:
    """Structural bindings for a synthetic experiment archive, not admission.

    Projected numbers are shape-checked here, including provisional zeroes for
    the pure encoded-length fixed point. The close owner enforces final exact
    accounting and caps before any manifest/completion publication.
    """

    schema: str
    kind: str
    classification: str
    synthetic_non_evidence: bool
    selection_receipt_sha256: str
    corpus_sha256: str
    source_sha256: str
    protocol_sha256: str
    materialization_file: V2ArchiveFileEvidence
    codec_profile_sha256: str
    size_basis: SizeBasisV2
    source_plan_identity: str
    materialization_plan_identity: str
    family_counts: tuple
    targets: readiness.DualComponentSizes
    family_totals: tuple
    e_final: int
    b_proc: int
    remaining_procedural_budget: int
    physical_minimum_total: int
    materialization_readback_complete: bool
    readback_streams: tuple
    durable_operation_count: int
    durable_primary_count: int
    durable_sample_max_coordinator_private_bytes: int
    runtime_monitor_peak_coordinator_private_bytes: int
    runtime_peak_is_independent: bool
    constructor_rejections_are_runtime_provenance: bool
    qualification_identity_stream: records.StreamDigest
    postprocessing_operations_stream: records.StreamDigest
    analysis_file: V2ArchiveFileEvidence
    report_file: V2ArchiveFileEvidence
    streams: tuple
    inventory_before_manifest_receipt: tuple
    attributable_bytes: int
    projected_fixed_bytes: int
    projected_archive_bytes: int
    fixed_allowance_cap: int
    archive_cap: int
    scope: str

    def __post_init__(self):
        for value, expected in ((self.schema, R0B_EXPERIMENT_V2), (self.kind, "archive_manifest"),
                (self.classification, "SYNTHETIC_NON_EFFECTIVENESS"), (self.scope, V2_ARCHIVE_SCOPE)):
            _need(type(value) is str and value == expected, "V2_ARCHIVE_IDENTITY")
        for value in (self.synthetic_non_evidence, self.materialization_readback_complete,
                      self.constructor_rejections_are_runtime_provenance):
            _v2_boolean(value)
            _need(value, "V2_ARCHIVE_SYNTHETIC_READBACK_REQUIRED")
        _v2_boolean(self.runtime_peak_is_independent)
        _need(not self.runtime_peak_is_independent, "V2_ARCHIVE_RUNTIME_PEAK_PROVENANCE")
        for value in (self.selection_receipt_sha256, self.corpus_sha256, self.source_sha256,
                      self.protocol_sha256, self.codec_profile_sha256, self.source_plan_identity,
                      self.materialization_plan_identity):
            _profile_identity(value)
        _need(self.protocol_sha256 == identity.PROTOCOL_SHA256, "V2_ARCHIVE_PROTOCOL_IDENTITY")
        _basis(self.size_basis)
        _need(self.size_basis.codec_profile_sha256 == self.codec_profile_sha256, "V2_ARCHIVE_PROFILE_IDENTITY")
        _need(type(self.family_counts) is tuple and len(self.family_counts) == len(readiness.V2_FAMILIES),
              "V2_ARCHIVE_FAMILY_COUNTS")
        for pair, family in zip(self.family_counts, readiness.V2_FAMILIES):
            _need(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str and pair[0] == family,
                  "V2_ARCHIVE_FAMILY_COUNT_ORDER")
            _v2_integer(pair[1], 0, 10000)
        _v2_exact(self.targets, readiness.DualComponentSizes)
        _need(type(self.family_totals) is tuple, "V2_ARCHIVE_FAMILY_TOTALS")
        for total in self.family_totals:
            _v2_exact(total, V2FamilyTotalEvidence)
        _need(tuple(total.family for total in self.family_totals) == readiness.V2_FAMILIES,
              "V2_ARCHIVE_FAMILY_TOTAL_ORDER")
        for value in (self.e_final, self.b_proc, self.remaining_procedural_budget, self.physical_minimum_total,
                      self.durable_operation_count, self.durable_primary_count,
                      self.durable_sample_max_coordinator_private_bytes, self.attributable_bytes,
                      self.projected_fixed_bytes, self.projected_archive_bytes,
                      self.fixed_allowance_cap, self.archive_cap):
            _v2_integer(value)
        _v2_integer(self.runtime_monitor_peak_coordinator_private_bytes, 1)
        _need(self.fixed_allowance_cap == identity.FIXED_REPORT_RECEIPT_ALLOWANCE
              and self.archive_cap == identity.MAX_ARCHIVE_BYTES, "V2_ARCHIVE_CAP_IDENTITIES")
        for streams, names in ((self.streams, V2_ARCHIVE_STREAM_NAMES),
                (self.readback_streams, execution.STREAM_NAMES + ("operations", "resources"))):
            _need(type(streams) is tuple, "V2_ARCHIVE_STREAM_TUPLE")
            for stream in streams:
                _v2_exact(stream, records.StreamDigest)
            _need(tuple(stream.name for stream in streams) == names, "V2_ARCHIVE_STREAM_ORDER")
        for stream in (self.qualification_identity_stream, self.postprocessing_operations_stream):
            _v2_exact(stream, records.StreamDigest)
        _need(self.readback_streams == self.streams[:-2]
              and (self.qualification_identity_stream, self.postprocessing_operations_stream) == self.streams[-2:],
              "V2_ARCHIVE_REPEATED_STREAM_BINDING")
        _need(type(self.inventory_before_manifest_receipt) is tuple, "V2_ARCHIVE_INVENTORY_TUPLE")
        for fact in self.inventory_before_manifest_receipt:
            _v2_exact(fact, V2ArchiveFileEvidence)
        _need(tuple(fact.path for fact in self.inventory_before_manifest_receipt) == V2_ARCHIVE_PRE_MANIFEST_PATHS,
              "V2_ARCHIVE_PRE_MANIFEST_INVENTORY")
        inventory = {fact.path: fact for fact in self.inventory_before_manifest_receipt}
        for fact, path in ((self.materialization_file, "streams/materialization-v2.json"),
                          (self.analysis_file, "postprocessing/analysis.json"),
                          (self.report_file, "postprocessing/report.html")):
            _v2_exact(fact, V2ArchiveFileEvidence)
            _need(fact.path == path and fact == inventory[path], "V2_ARCHIVE_REPEATED_FILE_BINDING")
        for stream in self.streams:
            directory = "postprocessing/" if stream.name == "postprocessing_operations" else "streams/"
            fact = inventory[directory + stream.name + ".pkf"]
            _need((fact.byte_length, fact.sha256) == (stream.byte_length, stream.sha256),
                  "V2_ARCHIVE_INVENTORY_STREAM_BINDING")


def encode_archive_manifest_v2(value):
    """Pure explicit archive shape; canonical ASCII JSON with one final LF."""
    _v2_exact(value, V2ArchiveManifestEvidence)
    nested = ("materialization_file", "size_basis", "family_counts", "targets", "family_totals",
              "readback_streams", "qualification_identity_stream", "postprocessing_operations_stream",
              "analysis_file", "report_file", "streams", "inventory_before_manifest_receipt")
    node = {name: getattr(value, name) for name in _V2_ARCHIVE_FIELDS if name not in nested}
    node["size_basis"] = json.loads(encode_size_basis(value.size_basis))
    node["family_counts"] = [[family, count] for family, count in value.family_counts]
    node["targets"] = {axis: {family: getattr(getattr(value.targets, axis), family)
                             for family in readiness.V2_FAMILIES} for axis in ("physical", "logical")}
    node["family_totals"] = [{name: getattr(total, name) for name in _V2_TOTAL_FIELDS}
                             for total in value.family_totals]
    for field in ("materialization_file", "analysis_file", "report_file"):
        node[field] = {name: getattr(getattr(value, field), name) for name in _V2_ARCHIVE_FILE_FIELDS}
    node["inventory_before_manifest_receipt"] = [
        {name: getattr(fact, name) for name in _V2_ARCHIVE_FILE_FIELDS}
        for fact in value.inventory_before_manifest_receipt]
    for field in ("qualification_identity_stream", "postprocessing_operations_stream"):
        node[field] = {name: getattr(getattr(value, field), name) for name in _V2_STREAM_FIELDS}
    for field in ("streams", "readback_streams"):
        node[field] = [{name: getattr(stream, name) for name in _V2_STREAM_FIELDS}
                       for stream in getattr(value, field)]
    return _v2_json(node) + b"\n"


def decode_archive_manifest_v2(data, *, expected_profile_sha256=None):
    """Decode structural bindings without performing I/O or semantic readback."""
    _need(type(data) is bytes and 0 < len(data) <= physical.MAX_PAYLOAD_BYTES,
          "V2_BOUNDED_ARCHIVE_METADATA_BYTES_REQUIRED")
    if expected_profile_sha256 is not None:
        _profile_identity(expected_profile_sha256)
    try:
        node = json.loads(data.decode("ascii"), object_pairs_hook=_v2_unique,
                          parse_float=_no_float, parse_constant=_no_float)
        _v2_fields(node, _V2_ARCHIVE_FIELDS)
        values = dict(node)
        values["size_basis"] = decode_size_basis(_v2_json(node["size_basis"]))
        _need(type(node["family_counts"]) is list, "V2_ARCHIVE_FAMILY_COUNTS")
        for pair in node["family_counts"]:
            _need(type(pair) is list and len(pair) == 2, "V2_ARCHIVE_FAMILY_COUNT_PAIR")
        values["family_counts"] = tuple(tuple(pair) for pair in node["family_counts"])
        _v2_fields(node["targets"], ("physical", "logical"))
        for axis in ("physical", "logical"):
            _v2_fields(node["targets"][axis], readiness.V2_FAMILIES)
        values["targets"] = readiness.DualComponentSizes(*(readiness.ComponentSizes(**node["targets"][axis])
                                                            for axis in ("physical", "logical")))
        _need(type(node["family_totals"]) is list, "V2_ARCHIVE_FAMILY_TOTALS")
        totals = []
        for total in node["family_totals"]:
            _v2_fields(total, _V2_TOTAL_FIELDS)
            totals.append(V2FamilyTotalEvidence(**total))
        values["family_totals"] = tuple(totals)
        for field in ("materialization_file", "analysis_file", "report_file"):
            _v2_fields(node[field], _V2_ARCHIVE_FILE_FIELDS)
            values[field] = V2ArchiveFileEvidence(**node[field])
        _need(type(node["inventory_before_manifest_receipt"]) is list, "V2_ARCHIVE_INVENTORY_ARRAY")
        inventory = []
        for fact in node["inventory_before_manifest_receipt"]:
            _v2_fields(fact, _V2_ARCHIVE_FILE_FIELDS)
            inventory.append(V2ArchiveFileEvidence(**fact))
        values["inventory_before_manifest_receipt"] = tuple(inventory)
        for field in ("qualification_identity_stream", "postprocessing_operations_stream"):
            _v2_fields(node[field], _V2_STREAM_FIELDS)
            values[field] = records.StreamDigest(**node[field])
        for field in ("streams", "readback_streams"):
            _need(type(node[field]) is list, "V2_ARCHIVE_STREAM_ARRAY")
            streams = []
            for stream in node[field]:
                _v2_fields(stream, _V2_STREAM_FIELDS)
                streams.append(records.StreamDigest(**stream))
            values[field] = tuple(streams)
        value = V2ArchiveManifestEvidence(**values)
        if expected_profile_sha256 is not None:
            _need(value.codec_profile_sha256 == expected_profile_sha256, "V2_EXPECTED_PROFILE_MISMATCH")
        _need(encode_archive_manifest_v2(value) == data, "V2_NONCANONICAL_ARCHIVE_METADATA")
        return value
    except EvidenceError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise EvidenceError("V2_MALFORMED_ARCHIVE_METADATA") from None


# Slice 1R: supplied calibration claims only. No archive access or live capture.
R0A_COMPONENTS_V2 = ("P", "K", "O", "D", "O_K_BIND", "O_D_REPEAT")
R0A_WALL_PHASES_V2 = ("COMPLETE_ROUTE", "ORCHESTRATION", "PRIOR_ENCODE", "PRIOR_BIND",
                      "PARENT_ADMISSION", "TARGET_PHASE", "CLEANUP")
_R0A_SETUP_ROUTES_V2 = {"K": "K", "D": "D", "O_K_BIND": "O_K_SETUP", "O_D_REPEAT": "O_D_SETUP"}
_R0A_TARGET_FAMILIES_V2 = {"P": "primary", "K": "k_control", "O": "oracle_primary",
                          "D": "determinism", "O_K_BIND": None, "O_D_REPEAT": "oracle_repeat"}
_R0A_TARGET_KINDS_V2 = {"P": execution.WorkerKind.PRIMARY, "O": execution.WorkerKind.PRIMARY,
    "K": execution.WorkerKind.K_CONTROL, "O_K_BIND": execution.WorkerKind.K_CONTROL,
    "D": execution.WorkerKind.DETERMINISM, "O_D_REPEAT": execution.WorkerKind.DETERMINISM}
_R0A_POSITIONS_V2 = tuple(range(64))
_R0A_STREAMS_V2 = execution.STREAM_NAMES + ("operations", "resources")


def _r0a_uint(value, minimum=0):
    _v2_integer(value, minimum, identity.UINT64_MAX)


def _r0a_true(value):
    _v2_boolean(value)
    _need(value, "R0A_V2_COMPLETE_CLAIM_REQUIRED")


def _r0a_tuple(value):
    _need(type(value) is tuple, "R0A_V2_EXACT_TUPLE_REQUIRED")


def _r0a_positions(value, *, empty=False):
    _r0a_tuple(value)
    _need(empty or bool(value), "R0A_V2_POSITIONS_REQUIRED")
    for position in value:
        _v2_integer(position, 0, 63)
    _need(value == tuple(sorted(set(value))), "R0A_V2_POSITION_ORDER")


def _r0a_path(value):
    # Lexical claims only: deliberately no Path, resolve, stat or file access.
    _need(type(value) is str and bool(value)
          and all(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF for c in value)
          and "\\" not in value and ":" not in value
          and all(part not in ("", ".", "..") for part in value.split("/")),
          "R0A_V2_CANONICAL_RELATIVE_PATH")


def _r0a_head(value):
    _need(type(value) is str and len(value) == 40
          and all(c in "0123456789abcdef" for c in value), "R0A_V2_HEAD_IDENTITY")


def provenance_digest_v2(selection_source_head, r0_harness_source_head, sources, working_files,
                         runtime, executable, dont_write_bytecode):
    """Bind seven supplied fields, without importing their harness-owned carrier.

    The separator ends in LF; the canonical node and complete preimage do not.
    This digest proves neither live source identity nor CRLF normalization.
    """
    _r0a_head(selection_source_head)
    _r0a_head(r0_harness_source_head)
    _r0a_tuple(sources)
    _need(bool(sources), "R0A_V2_SOURCES_REQUIRED")
    for source in sources:
        _v2_exact(source, records.SourceBlobIdentity)
    paths = tuple(source.path for source in sources)
    _need(paths == tuple(sorted(set(paths))), "R0A_V2_SOURCE_ORDER")
    _r0a_tuple(working_files)
    _need(len(working_files) == len(sources), "R0A_V2_WORKING_COVERAGE")
    for item, path in zip(working_files, paths):
        _need(type(item) is tuple and len(item) == 4, "R0A_V2_WORKING_SHAPE")
        _need(type(item[0]) is str and item[0] == path, "R0A_V2_WORKING_PATH")
        _profile_identity(item[1])
        _r0a_uint(item[2])
        _v2_boolean(item[3])
    _v2_exact(runtime, records.RuntimeIdentity)
    _need(type(executable) is str and bool(executable), "R0A_V2_EXECUTABLE")
    _r0a_true(dont_write_bytecode)
    node = {"dont_write_bytecode": dont_write_bytecode, "executable": executable,
        "r0_harness_source_head": r0_harness_source_head,
        "runtime": records.encode(runtime).decode("ascii"), "selection_source_head": selection_source_head,
        "sources": [records.encode(source).decode("ascii") for source in sources],
        "working_files": [[path, digest, length, normalized] for path, digest, length, normalized in working_files]}
    return sha256(b"program-k-e2-r0-provenance/v2\n" + _v2_json(node)).hexdigest()


@dataclass(frozen=True, slots=True)
class R0AIntervalV2:
    started_ns: int
    finished_ns: int

    def __post_init__(self):
        _r0a_uint(self.started_ns)
        _r0a_uint(self.finished_ns)
        _need(self.started_ns <= self.finished_ns, "R0A_V2_INTERVAL_ORDER")

    @property
    def duration_ns(self):
        return self.finished_ns - self.started_ns


@dataclass(frozen=True, slots=True)
class R0AWallIntervalV2:
    phase: str
    positions: tuple
    interval: R0AIntervalV2

    def __post_init__(self):
        _need(type(self.phase) is str and self.phase in R0A_WALL_PHASES_V2, "R0A_V2_WALL_PHASE")
        _r0a_positions(self.positions, empty=True)
        _v2_exact(self.interval, R0AIntervalV2)


@dataclass(frozen=True, slots=True)
class R0AMonitorEvidenceV2:
    coordinator_private_peak_bytes: int
    combined_peak_bytes: int
    memory_sample_count: int

    def __post_init__(self):
        for value in (self.coordinator_private_peak_bytes, self.combined_peak_bytes, self.memory_sample_count):
            _r0a_uint(value, 1)
        _need(self.combined_peak_bytes >= self.coordinator_private_peak_bytes, "R0A_V2_MONITOR_MEMORY")


def _r0a_intervals(value):
    _r0a_tuple(value)
    previous = 0
    for interval in value:
        _v2_exact(interval, R0AIntervalV2)
        _need(previous <= interval.started_ns, "R0A_V2_TELEMETRY_INTERVAL_ORDER")
        previous = interval.finished_ns


@dataclass(frozen=True, slots=True)
class R0AOracleTelemetryV2:
    probes: int
    calls: int
    wall_ns: int
    intervals: tuple

    def __post_init__(self):
        for value in (self.probes, self.calls, self.wall_ns):
            _r0a_uint(value)
        _r0a_intervals(self.intervals)
        _need(self.calls <= self.probes == len(self.intervals)
              and self.wall_ns == sum(i.duration_ns for i in self.intervals), "R0A_V2_ORACLE_TELEMETRY")


@dataclass(frozen=True, slots=True)
class R0ATelemetryV2:
    worker_memory: int
    coordinator_memory: int
    combined_memory: int
    decision_wall: int
    arm_wall: int
    shadow_wall: int
    physical_inputs: int
    oracle: R0AOracleTelemetryV2
    resources_complete: bool
    cleanup_complete: bool
    watchdogs_complete: bool
    prior_binding_intervals: tuple

    def __post_init__(self):
        for value in (self.worker_memory, self.coordinator_memory, self.combined_memory,
                      self.decision_wall, self.arm_wall, self.shadow_wall, self.physical_inputs):
            _r0a_uint(value)
        _need(self.combined_memory >= max(self.worker_memory, self.coordinator_memory)
              and self.decision_wall <= self.arm_wall, "R0A_V2_TELEMETRY_MAXIMA")
        _v2_exact(self.oracle, R0AOracleTelemetryV2)
        for flag in (self.resources_complete, self.cleanup_complete, self.watchdogs_complete):
            _r0a_true(flag)
        _r0a_intervals(self.prior_binding_intervals)


@dataclass(frozen=True, slots=True)
class R0APayloadAxesV2:
    logical_sum_bytes: int
    legacy_bundle_bytes: int
    wb02_wire_bytes: int
    physical_frame_bytes: int

    def __post_init__(self):
        for value in (self.logical_sum_bytes, self.legacy_bundle_bytes, self.wb02_wire_bytes,
                      self.physical_frame_bytes):
            _v2_integer(value, 1, physical.MAX_PAYLOAD_BYTES)
        _need(self.wb02_wire_bytes > 48 + self.physical_frame_bytes, "R0A_V2_WB02_SIZE_CLAIM")


@dataclass(frozen=True, slots=True)
class R0AArchiveEvidenceV2:
    relative_directory: str
    streams: tuple

    def __post_init__(self):
        _r0a_path(self.relative_directory)
        _r0a_tuple(self.streams)
        for stream in self.streams:
            _v2_exact(stream, records.StreamDigest)
        _need(tuple(stream.name for stream in self.streams) == _R0A_STREAMS_V2, "R0A_V2_STREAM_ORDER")
        _r0a_uint(sum(stream.byte_length for stream in self.streams))
        _r0a_uint(sum(stream.record_count for stream in self.streams))


@dataclass(frozen=True, slots=True)
class R0AByteCountV2:
    physical_bytes: int
    logical_bytes: int
    record_count: int

    def __post_init__(self):
        for value in (self.physical_bytes, self.logical_bytes, self.record_count):
            _r0a_uint(value)
        _need((self.physical_bytes == 0) == (self.logical_bytes == 0) == (self.record_count == 0),
              "R0A_V2_ZERO_RECORD_PARITY")


@dataclass(frozen=True, slots=True)
class R0ACaseEvidenceV2:
    receipt: operational.UnitReceipt
    observation: R0ATelemetryV2
    payload: R0APayloadAxesV2
    archive: R0AArchiveEvidenceV2
    family: str | None
    owned_bytes: R0AByteCountV2
    readback_complete: bool

    def __post_init__(self):
        _v2_exact(self.receipt, operational.UnitReceipt)
        _need(self.receipt.status is records.AuditStatus.PASS and self.receipt.reason == "ADMITTED"
              and type(self.receipt.exit_code) is int and self.receipt.exit_code == 0,
              "R0A_V2_ADMITTED_RECEIPT_REQUIRED")
        _v2_integer(self.receipt.position, 0, 63)
        _r0a_uint(self.receipt.elapsed_ns, 1)
        _v2_exact(self.observation, R0ATelemetryV2)
        _need(self.observation.arm_wall <= self.receipt.elapsed_ns, "R0A_V2_CASE_WALL_ORDER")
        _v2_exact(self.payload, R0APayloadAxesV2)
        _v2_exact(self.archive, R0AArchiveEvidenceV2)
        _v2_exact(self.owned_bytes, R0AByteCountV2)
        if self.family is None:
            _need(self.owned_bytes == R0AByteCountV2(0, 0, 0), "R0A_V2_NO_FAMILY_BYTES")
        else:
            _v2_family(self.family)
            _need(self.family in ("oracle_primary", "oracle_repeat") or self.owned_bytes.record_count > 0,
                  "R0A_V2_NONORACLE_BYTES_REQUIRED")
        _need(self.owned_bytes.physical_bytes <= self.payload.physical_frame_bytes
              and self.owned_bytes.logical_bytes <= self.payload.logical_sum_bytes
              and self.owned_bytes.physical_bytes <= sum(s.byte_length for s in self.archive.streams)
              and self.owned_bytes.record_count <= sum(s.record_count for s in self.archive.streams),
              "R0A_V2_OWNED_SUBSET_CLAIM")
        _r0a_true(self.readback_complete)


@dataclass(frozen=True, slots=True)
class R0AUnitEvidenceV2:
    position: int
    target: R0ACaseEvidenceV2
    setup: R0ACaseEvidenceV2 | None

    def __post_init__(self):
        _v2_integer(self.position, 0, 63)
        _v2_exact(self.target, R0ACaseEvidenceV2)
        _need(self.target.receipt.position == self.position, "R0A_V2_TARGET_POSITION")
        if self.setup is not None:
            _v2_exact(self.setup, R0ACaseEvidenceV2)
            _need(self.setup.receipt.position == self.position
                  and self.setup.receipt.kind is execution.WorkerKind.PRIMARY
                  and self.setup.family == "reference", "R0A_V2_SETUP_IDENTITY")


@dataclass(frozen=True, slots=True)
class R0ASetupWaveV2:
    route: str
    positions: tuple
    setup_interval: R0AIntervalV2
    target_interval: R0AIntervalV2
    monitor: R0AMonitorEvidenceV2
    readback_complete: bool

    def __post_init__(self):
        _need(type(self.route) is str and self.route in _R0A_SETUP_ROUTES_V2.values(), "R0A_V2_SETUP_ROUTE")
        _r0a_positions(self.positions)
        _v2_exact(self.setup_interval, R0AIntervalV2)
        _v2_exact(self.target_interval, R0AIntervalV2)
        _need(self.setup_interval.finished_ns <= self.target_interval.started_ns, "R0A_V2_SETUP_BEFORE_TARGET")
        _v2_exact(self.monitor, R0AMonitorEvidenceV2)
        _r0a_true(self.readback_complete)


@dataclass(frozen=True, slots=True)
class R0AProgressV2:
    position: int
    done: int
    total: int

    def __post_init__(self):
        _v2_integer(self.position, 0, 63)
        _r0a_uint(self.done, 1)
        _r0a_uint(self.total, 1)
        _need((self.done, self.total) == (self.position + 1, 64), "R0A_V2_PROGRESS_CLAIM")


def _r0a_inside(inner, outer):
    _need(outer.started_ns <= inner.started_ns <= inner.finished_ns <= outer.finished_ns,
          "R0A_V2_INTERVAL_CONTAINMENT")


def _r0a_wall_key(value):
    return (value.interval.started_ns, value.interval.finished_ns, value.phase, value.positions)


def _r0a_union(intervals):
    total, end = 0, 0
    for interval in sorted(intervals, key=lambda i: (i.started_ns, i.finished_ns)):
        total += max(0, interval.finished_ns - max(end, interval.started_ns))
        end = max(end, interval.finished_ns)
    _r0a_uint(total)
    return total


def _r0a_wall(component):
    rows = component.wall_intervals
    if component.component in ("P", "K", "O", "D"):
        _need(len(rows) == 1 and rows[0].phase == "COMPLETE_ROUTE"
              and rows[0].positions == _R0A_POSITIONS_V2
              and rows[0].interval == component.complete_interval, "R0A_V2_COMPLETE_WALL")
        return component.complete_interval.duration_ns
    phases = {name: tuple(row for row in rows if row.phase == name) for name in R0A_WALL_PHASES_V2}
    orchestration, cleanup = phases["ORCHESTRATION"], phases["CLEANUP"]
    _need(len(orchestration) == len(cleanup) == 1
          and orchestration[0].positions == cleanup[0].positions == (), "R0A_V2_ROUTE_OVERHEAD_REQUIRED")
    waves = component.setup_waves
    _need(orchestration[0].interval.finished_ns <= waves[0].setup_interval.started_ns
          and waves[-1].target_interval.finished_ns <= cleanup[0].interval.started_ns,
          "R0A_V2_OVERHEAD_CHRONOLOGY")
    if component.component == "O_D_REPEAT":
        _need(all(not phases[name] for name in ("COMPLETE_ROUTE", "PRIOR_ENCODE", "PRIOR_BIND", "PARENT_ADMISSION")),
              "R0A_V2_REPEAT_PHASE_SET")
        expected = tuple((wave.positions, wave.target_interval) for wave in waves)
        _need(tuple((row.positions, row.interval) for row in phases["TARGET_PHASE"]) == expected,
              "R0A_V2_TARGET_WAVE_COVERAGE")
        intervals = tuple(row.interval for row in rows)
        _need(all(a.finished_ns <= b.started_ns for a, b in zip(intervals, intervals[1:])),
              "R0A_V2_REPEAT_PHASE_OVERLAP")
        wall = sum(i.duration_ns for i in intervals)
    else:
        _need(not phases["COMPLETE_ROUTE"] and not phases["TARGET_PHASE"], "R0A_V2_BIND_PHASE_SET")
        encodes = phases["PRIOR_ENCODE"]
        _need(tuple(row.positions for row in encodes) == tuple(w.positions for w in waves),
              "R0A_V2_ENCODING_WAVE_COVERAGE")
        for row, wave in zip(encodes, waves):
            _r0a_inside(row.interval, wave.target_interval)
        admissions = phases["PARENT_ADMISSION"]
        _need(tuple(row.positions for row in admissions) == tuple((p,) for p in _R0A_POSITIONS_V2),
              "R0A_V2_ADMISSION_COVERAGE")
        expected = []
        for unit in component.units:
            bindings = unit.target.observation.prior_binding_intervals
            _need(bool(bindings), "R0A_V2_BINDING_OBSERVATION_REQUIRED")
            expected.extend(R0AWallIntervalV2("PRIOR_BIND", (unit.position,), i) for i in bindings)
        _need(phases["PRIOR_BIND"] == tuple(sorted(expected, key=_r0a_wall_key)), "R0A_V2_BINDING_MULTISET")
        for wave in waves:
            for row in phases["PRIOR_BIND"] + admissions:
                if row.positions[0] in wave.positions:
                    _r0a_inside(row.interval, wave.target_interval)
        wall = _r0a_union(tuple(row.interval for row in rows))
    _r0a_uint(wall, 1)
    return wall


@dataclass(frozen=True, slots=True)
class R0AComponentEvidenceV2:
    component: str
    complete_interval: R0AIntervalV2
    wall_intervals: tuple
    monitor: R0AMonitorEvidenceV2
    units: tuple
    setup_waves: tuple
    progress: tuple

    def __post_init__(self):
        _need(type(self.component) is str and self.component in R0A_COMPONENTS_V2, "R0A_V2_COMPONENT")
        _v2_exact(self.complete_interval, R0AIntervalV2)
        _r0a_uint(self.complete_interval.duration_ns, 1)
        _v2_exact(self.monitor, R0AMonitorEvidenceV2)
        for values in (self.wall_intervals, self.units, self.setup_waves, self.progress):
            _r0a_tuple(values)
        for row in self.wall_intervals:
            _v2_exact(row, R0AWallIntervalV2)
            _r0a_inside(row.interval, self.complete_interval)
        _need(tuple(map(_r0a_wall_key, self.wall_intervals)) == tuple(sorted(map(_r0a_wall_key, self.wall_intervals))),
              "R0A_V2_WALL_ORDER")
        has_setup = self.component in _R0A_SETUP_ROUTES_V2
        for unit in self.units:
            _v2_exact(unit, R0AUnitEvidenceV2)
            _need((unit.setup is not None) == has_setup
                  and unit.target.family == _R0A_TARGET_FAMILIES_V2[self.component]
                  and unit.target.receipt.kind is _R0A_TARGET_KINDS_V2[self.component], "R0A_V2_CASE_OWNERSHIP")
            for case in (unit.target,) if unit.setup is None else (unit.setup, unit.target):
                for interval in case.observation.oracle.intervals + case.observation.prior_binding_intervals:
                    _r0a_inside(interval, self.complete_interval)
        _need(tuple(unit.position for unit in self.units) == _R0A_POSITIONS_V2, "R0A_V2_UNIT_COVERAGE")
        for item in self.progress:
            _v2_exact(item, R0AProgressV2)
        _need(tuple(item.position for item in self.progress) == _R0A_POSITIONS_V2, "R0A_V2_PROGRESS_COVERAGE")
        previous = self.complete_interval.started_ns
        for wave in self.setup_waves:
            _v2_exact(wave, R0ASetupWaveV2)
            _need(has_setup and wave.route == _R0A_SETUP_ROUTES_V2[self.component]
                  and previous <= wave.setup_interval.started_ns, "R0A_V2_WAVE_ORDER")
            _r0a_inside(wave.setup_interval, self.complete_interval)
            _r0a_inside(wave.target_interval, self.complete_interval)
            previous = wave.target_interval.finished_ns
        _need(tuple(p for wave in self.setup_waves for p in wave.positions)
              == (_R0A_POSITIONS_V2 if has_setup else ()), "R0A_V2_SETUP_COVERAGE")
        _r0a_wall(self)

    @property
    def wall_ns(self):
        return r0a_component_wall_v2(self)

    @property
    def complete_wall_ns(self):
        return self.complete_interval.duration_ns


def r0a_component_wall_v2(component):
    """Reconstruct only supplied intervals, never actual clock observations."""
    _v2_exact(component, R0AComponentEvidenceV2)
    return _r0a_wall(component)


@dataclass(frozen=True, slots=True)
class R0ARouteContainmentV2:
    route: str
    max_worker_memory_bytes: int
    max_coordinator_memory_bytes: int
    max_combined_memory_bytes: int
    max_decision_wall_ns: int
    max_arm_wall_ns: int
    max_case_wall_ns: int
    max_shadow_wall_ns: int
    max_physical_inputs: int
    max_logical_sum_bytes: int
    max_legacy_bundle_bytes: int
    max_wb02_wire_bytes: int
    max_physical_frame_bytes: int
    launcher_wall_ns: int
    watchdogs_complete: bool
    resources_complete: bool
    cleanup_complete: bool
    progress_complete: bool
    readback_complete: bool
    watchdog_breaches: int
    resource_breaches: int

    def __post_init__(self):
        _need(type(self.route) is str and self.route in readiness.CALIBRATION_ROUTES, "R0A_V2_CONTAINMENT_ROUTE")
        for value in (self.max_worker_memory_bytes, self.max_coordinator_memory_bytes, self.max_combined_memory_bytes,
                      self.max_arm_wall_ns, self.max_case_wall_ns, self.max_physical_inputs, self.max_logical_sum_bytes,
                      self.max_legacy_bundle_bytes, self.max_wb02_wire_bytes, self.max_physical_frame_bytes,
                      self.launcher_wall_ns):
            _r0a_uint(value, 1)
        for value in (self.max_decision_wall_ns, self.max_shadow_wall_ns, self.watchdog_breaches, self.resource_breaches):
            _r0a_uint(value)
        _need(self.max_combined_memory_bytes >= max(self.max_worker_memory_bytes, self.max_coordinator_memory_bytes)
              and self.max_decision_wall_ns <= self.max_arm_wall_ns <= self.max_case_wall_ns,
              "R0A_V2_CONTAINMENT_MAXIMA")
        for flag in (self.watchdogs_complete, self.resources_complete, self.cleanup_complete,
                     self.progress_complete, self.readback_complete):
            _r0a_true(flag)
        _need(self.watchdog_breaches == self.resource_breaches == 0, "R0A_V2_BREACH_CLAIM")


def _r0a_components(components):
    _r0a_tuple(components)
    for component in components:
        _v2_exact(component, R0AComponentEvidenceV2)
    _need(tuple(c.component for c in components) == R0A_COMPONENTS_V2, "R0A_V2_COMPONENT_ORDER")


def summarize_r0a_components_v2(components):
    """Reconcile supplied unit claims, not persisted RF02 records."""
    _r0a_components(components)
    return _summarize_r0a_components_v2(components)


def _summarize_r0a_components_v2(components):
    # Only callers that have just revalidated the complete components use this.
    by_name = {component.component: component for component in components}
    result = []
    setup_components = {route: name for name, route in _R0A_SETUP_ROUTES_V2.items()}
    for family, route in readiness.R0A_FAMILY_ROUTES_V2:
        component = by_name[setup_components[route] if family == "reference" else route]
        values = tuple((unit.setup if family == "reference" else unit.target).owned_bytes for unit in component.units)
        result.append(readiness.R0AFamilySummaryV2(family, route, 64, sum(v.record_count for v in values),
            sum(v.physical_bytes for v in values), sum(v.logical_bytes for v in values),
            max(v.physical_bytes for v in values), max(v.logical_bytes for v in values)))
    return tuple(result)


def _r0a_containment(component, *, setup_only=False):
    cases = tuple(unit.setup for unit in component.units) if setup_only else tuple(
        case for unit in component.units for case in ((unit.target,) if unit.setup is None else (unit.setup, unit.target)))
    observations = tuple(case.observation for case in cases)
    monitors = tuple(w.monitor for w in component.setup_waves)
    if not setup_only:
        monitors += (component.monitor,)
    wall = sum(w.setup_interval.duration_ns for w in component.setup_waves) if setup_only else component.complete_wall_ns
    return R0ARouteContainmentV2(_R0A_SETUP_ROUTES_V2[component.component] if setup_only else component.component,
        max(v.worker_memory for v in observations),
        max(tuple(v.coordinator_memory for v in observations) + tuple(m.coordinator_private_peak_bytes for m in monitors)),
        max(tuple(v.combined_memory for v in observations) + tuple(m.combined_peak_bytes for m in monitors)),
        max(v.decision_wall for v in observations), max(v.arm_wall for v in observations),
        max(case.receipt.elapsed_ns for case in cases), max(v.shadow_wall for v in observations),
        max(v.physical_inputs for v in observations), max(case.payload.logical_sum_bytes for case in cases),
        max(case.payload.legacy_bundle_bytes for case in cases), max(case.payload.wb02_wire_bytes for case in cases),
        max(case.payload.physical_frame_bytes for case in cases), wall, True, True, True, True, True, 0, 0)


def derive_r0a_containment_v2(components):
    """Pure maxima of supplied observations; monitor peaks need not equal durable samples."""
    _r0a_components(components)
    return _derive_r0a_containment_v2(components)


def _derive_r0a_containment_v2(components):
    values = {c.component: _r0a_containment(c) for c in components}
    for component in components:
        if component.component in ("O_K_BIND", "O_D_REPEAT"):
            item = _r0a_containment(component, setup_only=True)
            values[item.route] = item
    return tuple(values[route] for route in readiness.CALIBRATION_ROUTES)


@dataclass(frozen=True, slots=True)
class R0AConcurrencyEvidenceV2:
    concurrency: int
    run_id: str
    envelope: operational.OperatingEnvelope
    components: tuple
    family_summaries: tuple
    containment: tuple

    def __post_init__(self):
        _need(type(self.concurrency) is int and self.concurrency in (1, 2, 4), "R0A_V2_CONCURRENCY")
        _need(type(self.run_id) is str and self.run_id.startswith("R0-") and len(self.run_id) > 3
              and all(32 <= ord(c) < 127 for c in self.run_id), "R0A_V2_RUN_ID")
        _v2_exact(self.envelope, operational.OperatingEnvelope)
        _need(self.envelope.concurrency == self.concurrency, "R0A_V2_ENVELOPE_CONCURRENCY")
        _r0a_components(self.components)
        for component in self.components:
            if component.setup_waves:
                _need(tuple(w.positions for w in component.setup_waves) == tuple(
                    _R0A_POSITIONS_V2[start:start + self.concurrency] for start in range(0, 64, self.concurrency)),
                    "R0A_V2_CONCURRENCY_WAVES")
        _r0a_tuple(self.family_summaries)
        for summary in self.family_summaries:
            _v2_exact(summary, readiness.R0AFamilySummaryV2)
        _need(self.family_summaries == _summarize_r0a_components_v2(self.components), "R0A_V2_SIZE_RECONCILIATION")
        _r0a_tuple(self.containment)
        for item in self.containment:
            _v2_exact(item, R0ARouteContainmentV2)
            _need(max(item.max_logical_sum_bytes, item.max_legacy_bundle_bytes,
                      item.max_wb02_wire_bytes, item.max_physical_frame_bytes) <= self.envelope.max_payload_bytes,
                  "R0A_V2_PAYLOAD_CAP_CLAIM")
        _need(self.containment == _derive_r0a_containment_v2(self.components), "R0A_V2_CONTAINMENT_RECONCILIATION")


@dataclass(frozen=True, slots=True)
class R0APlanEvidenceV2:
    protocol_seed: bytes
    boards: tuple

    def __post_init__(self):
        _need(type(self.protocol_seed) is bytes and self.protocol_seed == bytes.fromhex(identity.PROTOCOL_SHA256),
              "R0A_V2_PROTOCOL_SEED")
        _r0a_tuple(self.boards)
        for board in self.boards:
            _v2_exact(board, records.BoardIdentity)
        # Frozen bounded index selection only, never board generation or target recount.
        readiness.R0APlan(self.protocol_seed, tuple(board.game_index for board in self.boards))


@dataclass(frozen=True, slots=True)
class R0AObservationsV2:
    """Complete supplied calibration claims, not live or durable authentication."""
    schema: str
    selection_receipt_sha256: str
    source_head: str
    provenance_sha256: str
    protocol: records.ProtocolIdentity
    amendment: readiness.AmendmentProvenance
    runtime: records.RuntimeIdentity
    plan: R0APlanEvidenceV2
    codec_profile_bytes: bytes
    codec_profile_sha256: str
    size_basis: SizeBasisV2
    concurrencies: tuple

    def __post_init__(self):
        _need(type(self.schema) is str and self.schema == R0A_OBSERVATIONS_V2, "R0A_V2_SCHEMA")
        for value in (self.selection_receipt_sha256, self.provenance_sha256, self.codec_profile_sha256):
            _profile_identity(value)
        _r0a_head(self.source_head)
        _v2_exact(self.protocol, records.ProtocolIdentity)
        _need(self.protocol == records.ProtocolIdentity(identity.PROTOCOL_PATH, identity.PROTOCOL_SHA256,
            identity.PROTOCOL_BLOB_ID, identity.FREEZE_COMMIT), "R0A_V2_FROZEN_PROTOCOL")
        _v2_exact(self.amendment, readiness.AmendmentProvenance)
        _v2_exact(self.runtime, records.RuntimeIdentity)
        _v2_exact(self.plan, R0APlanEvidenceV2)
        _basis(self.size_basis)
        _need(type(self.codec_profile_bytes) is bytes, "R0A_V2_PROFILE_BYTES")
        profile = physical.decode_profile(self.codec_profile_bytes)
        physical.require_qualified_profile(profile)
        _need(profile.sha256.hex() == self.codec_profile_sha256 == self.size_basis.codec_profile_sha256,
              "R0A_V2_PROFILE_BINDING")
        _r0a_tuple(self.concurrencies)
        for value in self.concurrencies:
            _v2_exact(value, R0AConcurrencyEvidenceV2)
        _need(tuple(value.concurrency for value in self.concurrencies) == (1, 2, 4)
              and len({value.run_id for value in self.concurrencies}) == 3, "R0A_V2_CONCURRENCY_ORDER")
        paths = tuple(case.archive.relative_directory for value in self.concurrencies for component in value.components
                      for unit in component.units for case in
                      ((unit.target,) if unit.setup is None else (unit.setup, unit.target)))
        _need(len(paths) == len(set(paths)), "R0A_V2_ARCHIVE_PATH_UNIQUENESS")


# Explicit V2 writers/readers. No dataclass discovery or V1 fact dispatch.
def _r0a_interval_node(v):
    return {"started_ns": v.started_ns, "finished_ns": v.finished_ns}


def _r0a_monitor_node(v):
    return {"coordinator_private_peak_bytes": v.coordinator_private_peak_bytes,
            "combined_peak_bytes": v.combined_peak_bytes, "memory_sample_count": v.memory_sample_count}


def _r0a_stream_node(v):
    return {"name": v.name, "sha256": v.sha256, "byte_length": v.byte_length, "record_count": v.record_count}


def _r0a_payload_node(v):
    return {"logical_sum_bytes": v.logical_sum_bytes, "legacy_bundle_bytes": v.legacy_bundle_bytes,
            "wb02_wire_bytes": v.wb02_wire_bytes, "physical_frame_bytes": v.physical_frame_bytes}


def _r0a_receipt_node(v):
    return {"position": v.position, "kind": v.kind.value, "status": v.status.value,
            "reason": v.reason, "elapsed_ns": v.elapsed_ns, "exit_code": v.exit_code}


def _r0a_telemetry_node(v):
    return {"worker_memory": v.worker_memory, "coordinator_memory": v.coordinator_memory,
        "combined_memory": v.combined_memory, "decision_wall": v.decision_wall,
        "arm_wall": v.arm_wall, "shadow_wall": v.shadow_wall, "physical_inputs": v.physical_inputs,
        "oracle": {"probes": v.oracle.probes, "calls": v.oracle.calls, "wall_ns": v.oracle.wall_ns,
                   "intervals": [_r0a_interval_node(i) for i in v.oracle.intervals]},
        "resources_complete": v.resources_complete, "cleanup_complete": v.cleanup_complete,
        "watchdogs_complete": v.watchdogs_complete,
        "prior_binding_intervals": [_r0a_interval_node(i) for i in v.prior_binding_intervals]}


def _r0a_case_node(v):
    return {"receipt": _r0a_receipt_node(v.receipt), "observation": _r0a_telemetry_node(v.observation),
        "payload": _r0a_payload_node(v.payload), "archive": {"relative_directory": v.archive.relative_directory,
        "streams": [_r0a_stream_node(s) for s in v.archive.streams]}, "family": v.family,
        "owned_bytes": {"physical_bytes": v.owned_bytes.physical_bytes, "logical_bytes": v.owned_bytes.logical_bytes,
                        "record_count": v.owned_bytes.record_count}, "readback_complete": v.readback_complete}


def _r0a_wave_node(v):
    return {"route": v.route, "positions": list(v.positions), "setup_interval": _r0a_interval_node(v.setup_interval),
        "target_interval": _r0a_interval_node(v.target_interval), "monitor": _r0a_monitor_node(v.monitor),
        "readback_complete": v.readback_complete}


def _r0a_component_node(v):
    return {"component": v.component, "complete_interval": _r0a_interval_node(v.complete_interval),
        "wall_intervals": [{"phase": row.phase, "positions": list(row.positions),
                            "interval": _r0a_interval_node(row.interval)} for row in v.wall_intervals],
        "monitor": _r0a_monitor_node(v.monitor),
        "units": [{"position": unit.position, "target": _r0a_case_node(unit.target),
                   "setup": None if unit.setup is None else _r0a_case_node(unit.setup)} for unit in v.units],
        "setup_waves": [_r0a_wave_node(wave) for wave in v.setup_waves],
        "progress": [{"position": item.position, "done": item.done, "total": item.total} for item in v.progress]}


def _r0a_summary_node(v):
    return {"family": v.family, "route": v.route, "completed_units": v.completed_units,
        "record_count": v.record_count, "physical_total_bytes": v.physical_total_bytes,
        "logical_total_bytes": v.logical_total_bytes, "physical_max_unit_bytes": v.physical_max_unit_bytes,
        "logical_max_unit_bytes": v.logical_max_unit_bytes}


def _r0a_containment_node(v):
    return {"route": v.route, "max_worker_memory_bytes": v.max_worker_memory_bytes,
        "max_coordinator_memory_bytes": v.max_coordinator_memory_bytes, "max_combined_memory_bytes": v.max_combined_memory_bytes,
        "max_decision_wall_ns": v.max_decision_wall_ns, "max_arm_wall_ns": v.max_arm_wall_ns,
        "max_case_wall_ns": v.max_case_wall_ns, "max_shadow_wall_ns": v.max_shadow_wall_ns,
        "max_physical_inputs": v.max_physical_inputs, "max_logical_sum_bytes": v.max_logical_sum_bytes,
        "max_legacy_bundle_bytes": v.max_legacy_bundle_bytes, "max_wb02_wire_bytes": v.max_wb02_wire_bytes,
        "max_physical_frame_bytes": v.max_physical_frame_bytes, "launcher_wall_ns": v.launcher_wall_ns,
        "watchdogs_complete": v.watchdogs_complete, "resources_complete": v.resources_complete,
        "cleanup_complete": v.cleanup_complete, "progress_complete": v.progress_complete,
        "readback_complete": v.readback_complete, "watchdog_breaches": v.watchdog_breaches,
        "resource_breaches": v.resource_breaches}


def _r0a_envelope_node(v):
    return {"concurrency": v.concurrency, "max_decision_wall_ms": v.max_decision_wall_ms,
        "max_arm_wall_ms": v.max_arm_wall_ms, "max_case_wall_ms": v.max_case_wall_ms,
        "max_job_wall_ms": v.max_job_wall_ms, "max_launcher_wall_ms": v.max_launcher_wall_ms,
        "shadow_timeout_ms": v.shadow_timeout_ms, "max_physical_inputs": v.max_physical_inputs,
        "worker_memory_cap_bytes": v.worker_memory_cap_bytes, "coordinator_memory_cap_bytes": v.coordinator_memory_cap_bytes,
        "memory_cap_bytes": v.memory_cap_bytes, "archive_cap_bytes": v.archive_cap_bytes,
        "monitor_interval_ms": v.monitor_interval_ms, "max_payload_bytes": v.max_payload_bytes,
        "max_ipc_frame_bytes": v.max_ipc_frame_bytes, "aggregation_wall_ms": v.aggregation_wall_ms,
        "validation_wall_ms": v.validation_wall_ms, "publication_wall_ms": v.publication_wall_ms,
        "readback_wall_ms": v.readback_wall_ms, "report_wall_ms": v.report_wall_ms,
        "fixed_report_receipt_allowance": v.fixed_report_receipt_allowance}


def _r0a_concurrency_node(v):
    return {"concurrency": v.concurrency, "run_id": v.run_id, "envelope": _r0a_envelope_node(v.envelope),
        "components": [_r0a_component_node(c) for c in v.components],
        "family_summaries": [_r0a_summary_node(s) for s in v.family_summaries],
        "containment": [_r0a_containment_node(c) for c in v.containment]}


def encode_r0a_observations_v2(value):
    """Encode bounded, complete supplied claims. Never publish or authenticate files."""
    _v2_exact(value, R0AObservationsV2)
    a = value.amendment
    node = {"schema": value.schema, "selection_receipt_sha256": value.selection_receipt_sha256,
        "source_head": value.source_head, "provenance_sha256": value.provenance_sha256,
        "protocol": records.encode(value.protocol).decode("ascii"),
        "amendment": {"sha256": a.sha256, "byte_length": a.byte_length, "external_receipt": a.external_receipt,
            "protocol_sha256": a.protocol_sha256, "protocol_blob": a.protocol_blob, "protocol_commit": a.protocol_commit},
        "runtime": records.encode(value.runtime).decode("ascii"),
        "plan": {"protocol_seed": value.plan.protocol_seed.hex(),
                 "boards": [records.encode(board).decode("ascii") for board in value.plan.boards]},
        "codec_profile_bytes": value.codec_profile_bytes.hex(), "codec_profile_sha256": value.codec_profile_sha256,
        "size_basis": json.loads(encode_size_basis(value.size_basis)),
        "concurrencies": [_r0a_concurrency_node(c) for c in value.concurrencies]}
    data = _v2_json(node) + b"\n"
    _need(0 < len(data) <= physical.MAX_PAYLOAD_BYTES, "R0A_V2_METADATA_BOUND")
    return data


def _r0a_fields(node, names):
    _v2_fields(node, names.split())
    return node


def _r0a_list(value, maximum):
    _need(type(value) is list and len(value) <= maximum, "R0A_V2_BOUNDED_ARRAY")
    return value


def _r0a_read_interval(node):
    return R0AIntervalV2(**_r0a_fields(node, "started_ns finished_ns"))


def _r0a_read_monitor(node):
    return R0AMonitorEvidenceV2(**_r0a_fields(node, "coordinator_private_peak_bytes combined_peak_bytes memory_sample_count"))


def _r0a_read_telemetry(node):
    _r0a_fields(node, "worker_memory coordinator_memory combined_memory decision_wall arm_wall shadow_wall physical_inputs "
               "oracle resources_complete cleanup_complete watchdogs_complete prior_binding_intervals")
    oracle = _r0a_fields(node["oracle"], "probes calls wall_ns intervals")
    return R0ATelemetryV2(node["worker_memory"], node["coordinator_memory"], node["combined_memory"],
        node["decision_wall"], node["arm_wall"], node["shadow_wall"], node["physical_inputs"],
        R0AOracleTelemetryV2(oracle["probes"], oracle["calls"], oracle["wall_ns"],
            tuple(_r0a_read_interval(i) for i in _r0a_list(oracle["intervals"], physical.MAX_PAYLOAD_BYTES))),
        node["resources_complete"], node["cleanup_complete"], node["watchdogs_complete"],
        tuple(_r0a_read_interval(i) for i in _r0a_list(node["prior_binding_intervals"], physical.MAX_PAYLOAD_BYTES)))


def _r0a_read_case(node):
    _r0a_fields(node, "receipt observation payload archive family owned_bytes readback_complete")
    receipt = _r0a_fields(node["receipt"], "position kind status reason elapsed_ns exit_code")
    _need(type(receipt["kind"]) is str and type(receipt["status"]) is str, "R0A_V2_RECEIPT_ENUM")
    archive = _r0a_fields(node["archive"], "relative_directory streams")
    return R0ACaseEvidenceV2(operational.UnitReceipt(receipt["position"], execution.WorkerKind(receipt["kind"]),
        records.AuditStatus(receipt["status"]), receipt["reason"], receipt["elapsed_ns"], receipt["exit_code"]),
        _r0a_read_telemetry(node["observation"]), R0APayloadAxesV2(**_r0a_fields(node["payload"],
            "logical_sum_bytes legacy_bundle_bytes wb02_wire_bytes physical_frame_bytes")),
        R0AArchiveEvidenceV2(archive["relative_directory"], tuple(records.StreamDigest(**_r0a_fields(s,
            "name sha256 byte_length record_count")) for s in _r0a_list(archive["streams"], len(_R0A_STREAMS_V2)))),
        node["family"], R0AByteCountV2(**_r0a_fields(node["owned_bytes"], "physical_bytes logical_bytes record_count")),
        node["readback_complete"])


def _r0a_read_wave(node):
    _r0a_fields(node, "route positions setup_interval target_interval monitor readback_complete")
    return R0ASetupWaveV2(node["route"], tuple(_r0a_list(node["positions"], 64)),
        _r0a_read_interval(node["setup_interval"]), _r0a_read_interval(node["target_interval"]),
        _r0a_read_monitor(node["monitor"]), node["readback_complete"])


def _r0a_read_component(node):
    _r0a_fields(node, "component complete_interval wall_intervals monitor units setup_waves progress")
    rows = []
    for row in _r0a_list(node["wall_intervals"], physical.MAX_PAYLOAD_BYTES):
        _r0a_fields(row, "phase positions interval")
        rows.append(R0AWallIntervalV2(row["phase"], tuple(_r0a_list(row["positions"], 64)), _r0a_read_interval(row["interval"])))
    units = []
    for unit in _r0a_list(node["units"], 64):
        _r0a_fields(unit, "position target setup")
        units.append(R0AUnitEvidenceV2(unit["position"], _r0a_read_case(unit["target"]),
                                     None if unit["setup"] is None else _r0a_read_case(unit["setup"])))
    return R0AComponentEvidenceV2(node["component"], _r0a_read_interval(node["complete_interval"]), tuple(rows),
        _r0a_read_monitor(node["monitor"]), tuple(units),
        tuple(_r0a_read_wave(w) for w in _r0a_list(node["setup_waves"], 64)),
        tuple(R0AProgressV2(**_r0a_fields(p, "position done total")) for p in _r0a_list(node["progress"], 64)))


def _r0a_read_concurrency(node):
    _r0a_fields(node, "concurrency run_id envelope components family_summaries containment")
    envelope = operational.OperatingEnvelope(**_r0a_fields(node["envelope"],
        "concurrency max_decision_wall_ms max_arm_wall_ms max_case_wall_ms max_job_wall_ms max_launcher_wall_ms "
        "shadow_timeout_ms max_physical_inputs worker_memory_cap_bytes coordinator_memory_cap_bytes memory_cap_bytes "
        "archive_cap_bytes monitor_interval_ms max_payload_bytes max_ipc_frame_bytes aggregation_wall_ms validation_wall_ms "
        "publication_wall_ms readback_wall_ms report_wall_ms fixed_report_receipt_allowance"))
    summaries = tuple(readiness.R0AFamilySummaryV2(**_r0a_fields(s,
        "family route completed_units record_count physical_total_bytes logical_total_bytes physical_max_unit_bytes logical_max_unit_bytes"))
        for s in _r0a_list(node["family_summaries"], 9))
    containment = tuple(R0ARouteContainmentV2(**_r0a_fields(c,
        "route max_worker_memory_bytes max_coordinator_memory_bytes max_combined_memory_bytes max_decision_wall_ns "
        "max_arm_wall_ns max_case_wall_ns max_shadow_wall_ns max_physical_inputs max_logical_sum_bytes max_legacy_bundle_bytes "
        "max_wb02_wire_bytes max_physical_frame_bytes launcher_wall_ns watchdogs_complete resources_complete cleanup_complete "
        "progress_complete readback_complete watchdog_breaches resource_breaches")) for c in _r0a_list(node["containment"], 8))
    return R0AConcurrencyEvidenceV2(node["concurrency"], node["run_id"], envelope,
        tuple(_r0a_read_component(c) for c in _r0a_list(node["components"], 6)), summaries, containment)


def _r0a_read_rec(value, cls):
    _need(type(value) is str and value.isascii(), "R0A_V2_EXACT_REC_STRING")
    data = value.encode("ascii")
    result = records.decode(data)
    _v2_exact(result, cls)
    _need(records.encode(result) == data, "R0A_V2_CANONICAL_REC_STRING")
    return result


def decode_r0a_observations_v2(data, *, expected_profile_sha256=None, expected_provenance_sha256=None,
                              expected_source_head=None, expected_selection_receipt_sha256=None,
                              expected_plan=None, expected_runtime=None):
    """Decode/reconcile supplied claims. Expected values are also supplied, never captured."""
    _need(type(data) is bytes and 0 < len(data) <= physical.MAX_PAYLOAD_BYTES, "R0A_V2_METADATA_BOUND")
    for digest in (expected_profile_sha256, expected_provenance_sha256, expected_selection_receipt_sha256):
        if digest is not None:
            _profile_identity(digest)
    if expected_source_head is not None:
        _r0a_head(expected_source_head)
    if expected_plan is not None:
        _v2_exact(expected_plan, R0APlanEvidenceV2)
    if expected_runtime is not None:
        _v2_exact(expected_runtime, records.RuntimeIdentity)
    try:
        node = json.loads(data.decode("ascii"), object_pairs_hook=_v2_unique,
                          parse_float=_no_float, parse_constant=_no_float)
        _r0a_fields(node, "schema selection_receipt_sha256 source_head provenance_sha256 protocol amendment runtime plan "
                    "codec_profile_bytes codec_profile_sha256 size_basis concurrencies")
        # Reject lexical drift before constructing the large supplied claim tree.
        # The final record-aware encode equality remains authoritative as well.
        _need(_v2_json(node) + b"\n" == data, "R0A_V2_NONCANONICAL_DOCUMENT")
        for observed, expected in ((node["codec_profile_sha256"], expected_profile_sha256),
                (node["provenance_sha256"], expected_provenance_sha256), (node["source_head"], expected_source_head),
                (node["selection_receipt_sha256"], expected_selection_receipt_sha256)):
            _need(expected is None or observed == expected, "R0A_V2_EXPECTED_BINDING_MISMATCH")
        plan = _r0a_fields(node["plan"], "protocol_seed boards")
        value = R0AObservationsV2(node["schema"], node["selection_receipt_sha256"], node["source_head"],
            node["provenance_sha256"], _r0a_read_rec(node["protocol"], records.ProtocolIdentity),
            readiness.AmendmentProvenance(**_r0a_fields(node["amendment"],
                "sha256 byte_length external_receipt protocol_sha256 protocol_blob protocol_commit")),
            _r0a_read_rec(node["runtime"], records.RuntimeIdentity),
            R0APlanEvidenceV2(_v2_hex(plan["protocol_seed"]),
                tuple(_r0a_read_rec(b, records.BoardIdentity) for b in _r0a_list(plan["boards"], 64))),
            _v2_hex(node["codec_profile_bytes"]), node["codec_profile_sha256"],
            decode_size_basis(_v2_json(node["size_basis"])),
            tuple(_r0a_read_concurrency(c) for c in _r0a_list(node["concurrencies"], 3)))
        for observed, expected in ((value.codec_profile_sha256, expected_profile_sha256),
                (value.provenance_sha256, expected_provenance_sha256), (value.source_head, expected_source_head),
                (value.selection_receipt_sha256, expected_selection_receipt_sha256),
                (value.plan, expected_plan), (value.runtime, expected_runtime)):
            _need(expected is None or observed == expected, "R0A_V2_EXPECTED_BINDING_MISMATCH")
        _need(encode_r0a_observations_v2(value) == data, "R0A_V2_NONCANONICAL_DOCUMENT")
        return value
    except EvidenceError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise EvidenceError("R0A_V2_MALFORMED_OBSERVATIONS") from None


# Slice 1W: this literal vocabulary belongs to the historical run schema. Future
# live source-closure changes must not redefine the identity of an existing run.
R0_RUN_V2_SOURCE_PATHS = (
    "benchmark_board.py",
    "board_analyzer.py",
    "board_snapshot.py",
    "calibration/stage3_physical_profile_v1.json",
    "core_engine.py",
    "docs/stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md",
    "docs/stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md",
    "docs/stage3-extended/STAGE3_PROGRAM_K_GATE_R_PROTOCOL.md",
    "docs/stage3-extended/STAGE3_PROGRAM_K_RESEARCH_SPEC.md",
    "experiments/__init__.py",
    "experiments/program_k_capability.py",
    "experiments/program_k_e2_analysis.py",
    "experiments/program_k_e2_audit.py",
    "experiments/program_k_e2_evaluator.py",
    "experiments/program_k_e2_execution.py",
    "experiments/program_k_e2_game.py",
    "experiments/program_k_e2_identity.py",
    "experiments/program_k_e2_operational.py",
    "experiments/program_k_e2_physical.py",
    "experiments/program_k_e2_qualification.py",
    "experiments/program_k_e2_r0_evidence.py",
    "experiments/program_k_e2_r0_harness.py",
    "experiments/program_k_e2_readiness.py",
    "experiments/program_k_e2_records.py",
    "experiments/program_k_e2_report.py",
    "experiments/program_k_e2_store.py",
    "experiments/program_k_evaluator.py",
    "experiments/program_k_evidence.py",
    "experiments/program_k_harness.py",
    "experiments/program_k_oracles.py",
    "experiments/program_k_policy.py",
    "experiments/program_k_runner.py",
    "simple_algorithm.py",
    "simple_decision.py",
    "simple_probability.py",
    "stage3_physical.py",
    "stage3_planner.py",
    "stage3_runner.py",
    "tests/test_program_k_e2_operational.py",
    "tests/test_program_k_harness.py",
    "tests/test_program_k_policy.py",
    "tests/test_program_k_semantics.py",
)
R0_RUN_V2_SELECTION_RECEIPT_SHA256 = "72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c"
R0_RUN_V2_SELECTION_RECEIPT_BYTES = 7364
R0_RUN_V2_SELECTION_SOURCE_HEAD = "cdba3513c23df77ba44449af1e551889a6954768"
R0_RUN_V2_CLASSIFICATION = "OPERATIONAL_NON_EFFECTIVENESS_R0_EVIDENCE"
R0_RUN_V2_STATUS = "COMPLETE_FOR_INDEPENDENT_REVIEW_NOT_ENVELOPE_ADMISSION"
R0_RUN_V2_FORBIDDEN_ACTIONS = tuple((name, False) for name in (
    "final_envelope_selected", "n_selected", "r0_admission_pass", "r0_b", "r0_b_pass",
    "actual_e2", "actual_e2_ready", "effectiveness_analysis", "effectiveness_result",
    "e3", "gate_p", "holdout", "target_recount", "synthetic_search", "bootstrap",
    "project_git_mutation"))
_R0_RUN_V2_COMPONENT_PHASES = (
    ("P", ("target",)), ("K", ("setup", "target")), ("O", ("target",)),
    ("D", ("setup", "target")), ("O_K_BIND", ("setup", "target")),
    ("O_D_REPEAT", ("setup", "target")))
_R0_RUN_V2_POSITIONS = tuple(format(position, "02d") for position in range(64))
R0_RUN_V2_PRE_MANIFEST_FILE_COUNT = 105_602
_R0_RUN_V2_FIELDS = (
    "schema", "mode", "classification", "status", "selection_receipt_sha256",
    "selection_receipt_byte_length", "selection_source_head", "source_head", "provenance_sha256",
    "provenance", "protocol", "amendment", "codec_profile_sha256", "plan", "corpus_sha256",
    "concurrency_runs", "observations_file", "inventory_before_manifest_receipt", "forbidden_actions")
_R0_RUN_V2_PROVENANCE_FIELDS = (
    "selection_source_head", "r0_harness_source_head", "sources", "working_files", "runtime",
    "executable", "dont_write_bytecode")


def r0_run_pre_manifest_paths_v2():
    """Pure fixed vocabulary, allocated only when a caller requests the layout."""
    return tuple(sorted(("INCOMPLETE.json", "r0a-observations-v2.json") + tuple(
        "calibration/c" + str(concurrency) + "/" + component + "/" + position + "/" + phase
        + "/" + name + ".pkf"
        for concurrency in (1, 2, 4) for component, phases in _R0_RUN_V2_COMPONENT_PHASES
        for position in _R0_RUN_V2_POSITIONS for phase in phases for name in _R0A_STREAMS_V2)))


def _r0_run_path_v2(path):
    _r0a_path(path)
    if path in ("INCOMPLETE.json", "r0a-observations-v2.json"):
        return
    parts = path.split("/")
    _need(len(parts) == 6 and parts[0] == "calibration" and parts[1] in ("c1", "c2", "c4")
          and parts[3] in _R0_RUN_V2_POSITIONS and parts[5].endswith(".pkf")
          and parts[5][:-4] in _R0A_STREAMS_V2, "R0_RUN_V2_FILE_PATH")
    _need(any(parts[2] == component and parts[4] in phases
              for component, phases in _R0_RUN_V2_COMPONENT_PHASES), "R0_RUN_V2_FILE_PATH")


def _r0_run_plan_v2(plan):
    """Validate supplied production identities only; never generate a board."""
    _v2_exact(plan, R0APlanEvidenceV2)
    for board in plan.boards:
        _need((board.width, board.height, board.mines, board.first_click,
               board.generator_identity, board.spec_identity) ==
              (30, 16, 99, (0, 0), "V1", "EXPERT_GENERAL_V1"), "R0_RUN_V2_BOARD_METADATA")
        _profile_identity(board.fingerprint)
    return plan


@dataclass(frozen=True, slots=True)
class R0RunProvenanceV2:
    """Recorded supplied capture facts, not a replay of historical live capture."""

    selection_source_head: str
    r0_harness_source_head: str
    sources: tuple
    working_files: tuple
    runtime: records.RuntimeIdentity
    executable: str
    dont_write_bytecode: bool

    def __post_init__(self):
        provenance_digest_v2(self.selection_source_head, self.r0_harness_source_head,
            self.sources, self.working_files, self.runtime, self.executable, self.dont_write_bytecode)
        _need(self.selection_source_head == R0_RUN_V2_SELECTION_SOURCE_HEAD,
              "R0_RUN_V2_SELECTION_SOURCE")
        _need(tuple(source.path for source in self.sources) == R0_RUN_V2_SOURCE_PATHS,
              "R0_RUN_V2_SOURCE_COVERAGE")


@dataclass(frozen=True, slots=True)
class R0RunFileV2:
    path: str
    byte_length: int
    sha256: str

    def __post_init__(self):
        _r0_run_path_v2(self.path)
        _r0a_uint(self.byte_length, 1 if self.path in
                   ("INCOMPLETE.json", "r0a-observations-v2.json") else 0)
        _profile_identity(self.sha256)


@dataclass(frozen=True, slots=True)
class R0RunManifestV2:
    """Closed R0-A archive facts for independent review, never admission."""

    schema: str
    mode: str
    classification: str
    status: str
    selection_receipt_sha256: str
    selection_receipt_byte_length: int
    selection_source_head: str
    source_head: str
    provenance_sha256: str
    provenance: R0RunProvenanceV2
    protocol: records.ProtocolIdentity
    amendment: readiness.AmendmentProvenance
    codec_profile_sha256: str
    plan: R0APlanEvidenceV2
    corpus_sha256: str
    concurrency_runs: tuple
    observations_file: R0RunFileV2
    inventory_before_manifest_receipt: tuple
    forbidden_actions: tuple

    def __post_init__(self):
        for value, expected in ((self.schema, R0_RUN_V2), (self.mode, "R0_A"),
                (self.classification, R0_RUN_V2_CLASSIFICATION), (self.status, R0_RUN_V2_STATUS),
                (self.selection_receipt_sha256, R0_RUN_V2_SELECTION_RECEIPT_SHA256),
                (self.selection_source_head, R0_RUN_V2_SELECTION_SOURCE_HEAD)):
            _need(type(value) is str and value == expected, "R0_RUN_V2_IDENTITY")
        _r0a_uint(self.selection_receipt_byte_length, 1)
        _need(self.selection_receipt_byte_length == R0_RUN_V2_SELECTION_RECEIPT_BYTES,
              "R0_RUN_V2_SELECTION_LENGTH")
        _r0a_head(self.source_head)
        for value in (self.provenance_sha256, self.codec_profile_sha256, self.corpus_sha256):
            _profile_identity(value)
        _v2_exact(self.provenance, R0RunProvenanceV2)
        p = self.provenance
        _need(self.source_head == p.r0_harness_source_head
              and self.selection_source_head == p.selection_source_head
              and self.provenance_sha256 == provenance_digest_v2(p.selection_source_head,
                  p.r0_harness_source_head, p.sources, p.working_files, p.runtime, p.executable,
                  p.dont_write_bytecode), "R0_RUN_V2_PROVENANCE_BINDING")
        _v2_exact(self.protocol, records.ProtocolIdentity)
        _need(self.protocol == records.ProtocolIdentity(identity.PROTOCOL_PATH, identity.PROTOCOL_SHA256,
            identity.PROTOCOL_BLOB_ID, identity.FREEZE_COMMIT), "R0_RUN_V2_PROTOCOL")
        _v2_exact(self.amendment, readiness.AmendmentProvenance)
        _need(type(self.amendment.byte_length) is int
              and all(type(value) is str for value in (self.amendment.sha256,
                  self.amendment.external_receipt, self.amendment.protocol_sha256,
                  self.amendment.protocol_blob, self.amendment.protocol_commit)),
              "R0_RUN_V2_AMENDMENT_FIELD_TYPES")
        _r0_run_plan_v2(self.plan)
        indices = tuple(board.game_index for board in self.plan.boards)
        _need(self.corpus_sha256 == identity.corpus_digest(self.plan.protocol_seed, len(indices), indices).hex(),
              "R0_RUN_V2_CORPUS")
        _need(type(self.concurrency_runs) is tuple and len(self.concurrency_runs) == 3,
              "R0_RUN_V2_CONCURRENCY_RUNS")
        for pair, concurrency in zip(self.concurrency_runs, (1, 2, 4)):
            _need(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is int and pair[0] == concurrency,
                  "R0_RUN_V2_CONCURRENCY_RUNS")
            run_id = pair[1]
            _need(type(run_id) is str and run_id.startswith("R0-") and len(run_id) > 3
                  and all(32 <= ord(char) < 127 for char in run_id), "R0_RUN_V2_RUN_ID")
        _need(len({pair[1] for pair in self.concurrency_runs}) == 3, "R0_RUN_V2_DISTINCT_RUN_IDS")
        _v2_exact(self.observations_file, R0RunFileV2)
        _need(self.observations_file.path == "r0a-observations-v2.json", "R0_RUN_V2_OBSERVATIONS_PATH")
        _need(type(self.inventory_before_manifest_receipt) is tuple
              and len(self.inventory_before_manifest_receipt) == R0_RUN_V2_PRE_MANIFEST_FILE_COUNT,
              "R0_RUN_V2_INVENTORY_COUNT")
        for fact in self.inventory_before_manifest_receipt:
            _v2_exact(fact, R0RunFileV2)
        paths = tuple(fact.path for fact in self.inventory_before_manifest_receipt)
        # Every legal path occurs once: the closed vocabulary has exactly this
        # cardinality. No large path table is allocated at module import.
        _need(paths == tuple(sorted(set(paths))), "R0_RUN_V2_INVENTORY_ORDER")
        _need(self.observations_file == self.inventory_before_manifest_receipt[-1],
              "R0_RUN_V2_OBSERVATIONS_FILE_BINDING")
        _need(type(self.forbidden_actions) is tuple
              and len(self.forbidden_actions) == len(R0_RUN_V2_FORBIDDEN_ACTIONS),
              "R0_RUN_V2_FORBIDDEN_ACTIONS")
        for pair, expected in zip(self.forbidden_actions, R0_RUN_V2_FORBIDDEN_ACTIONS):
            _need(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str
                  and pair[0] == expected[0] and pair[1] is False, "R0_RUN_V2_FORBIDDEN_ACTIONS")


def _r0_run_file_node_v2(value):
    return {"path": value.path, "byte_length": value.byte_length, "sha256": value.sha256}


def encode_r0_run_manifest_v2(value):
    """Encode the explicit bounded run vocabulary; never capture or publish."""
    _v2_exact(value, R0RunManifestV2)
    p, a = value.provenance, value.amendment
    node = {"schema": value.schema, "mode": value.mode, "classification": value.classification,
        "status": value.status, "selection_receipt_sha256": value.selection_receipt_sha256,
        "selection_receipt_byte_length": value.selection_receipt_byte_length,
        "selection_source_head": value.selection_source_head, "source_head": value.source_head,
        "provenance_sha256": value.provenance_sha256,
        "provenance": {"selection_source_head": p.selection_source_head,
            "r0_harness_source_head": p.r0_harness_source_head,
            "sources": [records.encode(source).decode("ascii") for source in p.sources],
            "working_files": [[path, digest, length, normalized]
                              for path, digest, length, normalized in p.working_files],
            "runtime": records.encode(p.runtime).decode("ascii"), "executable": p.executable,
            "dont_write_bytecode": p.dont_write_bytecode},
        "protocol": records.encode(value.protocol).decode("ascii"),
        "amendment": {"sha256": a.sha256, "byte_length": a.byte_length, "external_receipt": a.external_receipt,
            "protocol_sha256": a.protocol_sha256, "protocol_blob": a.protocol_blob,
            "protocol_commit": a.protocol_commit},
        "codec_profile_sha256": value.codec_profile_sha256,
        "plan": {"protocol_seed": value.plan.protocol_seed.hex(),
            "boards": [records.encode(board).decode("ascii") for board in value.plan.boards]},
        "corpus_sha256": value.corpus_sha256,
        "concurrency_runs": [[concurrency, run_id] for concurrency, run_id in value.concurrency_runs],
        "observations_file": _r0_run_file_node_v2(value.observations_file),
        "inventory_before_manifest_receipt": [_r0_run_file_node_v2(fact)
                                               for fact in value.inventory_before_manifest_receipt],
        "forbidden_actions": dict(value.forbidden_actions)}
    data = _v2_json(node) + b"\n"
    _need(0 < len(data) <= physical.MAX_PAYLOAD_BYTES, "R0_RUN_V2_METADATA_BOUND")
    return data


def decode_r0_run_manifest_v2(data):
    """Decode recorded authority without filesystem access or live recapture."""
    _need(type(data) is bytes and 0 < len(data) <= physical.MAX_PAYLOAD_BYTES, "R0_RUN_V2_METADATA_BOUND")
    try:
        node = json.loads(data.decode("ascii"), object_pairs_hook=_v2_unique,
                          parse_float=_no_float, parse_constant=_no_float)
        _v2_fields(node, _R0_RUN_V2_FIELDS)
        _need(_v2_json(node) + b"\n" == data, "R0_RUN_V2_NONCANONICAL_DOCUMENT")
        p = node["provenance"]
        _v2_fields(p, _R0_RUN_V2_PROVENANCE_FIELDS)
        sources = tuple(_r0a_read_rec(source, records.SourceBlobIdentity)
                        for source in _r0a_list(p["sources"], len(R0_RUN_V2_SOURCE_PATHS)))
        working = []
        for row in _r0a_list(p["working_files"], len(R0_RUN_V2_SOURCE_PATHS)):
            _need(type(row) is list and len(row) == 4, "R0_RUN_V2_WORKING_ROW")
            working.append(tuple(row))
        provenance = R0RunProvenanceV2(p["selection_source_head"], p["r0_harness_source_head"], sources,
            tuple(working), _r0a_read_rec(p["runtime"], records.RuntimeIdentity), p["executable"],
            p["dont_write_bytecode"])
        plan = _r0a_fields(node["plan"], "protocol_seed boards")
        runs = []
        for pair in _r0a_list(node["concurrency_runs"], 3):
            _need(type(pair) is list and len(pair) == 2, "R0_RUN_V2_CONCURRENCY_RUNS")
            runs.append(tuple(pair))
        inventory = tuple(R0RunFileV2(**_r0a_fields(fact, "path byte_length sha256"))
            for fact in _r0a_list(node["inventory_before_manifest_receipt"], R0_RUN_V2_PRE_MANIFEST_FILE_COUNT))
        forbidden = node["forbidden_actions"]
        _v2_fields(forbidden, tuple(name for name, _ in R0_RUN_V2_FORBIDDEN_ACTIONS))
        value = R0RunManifestV2(node["schema"], node["mode"], node["classification"], node["status"],
            node["selection_receipt_sha256"], node["selection_receipt_byte_length"],
            node["selection_source_head"], node["source_head"], node["provenance_sha256"], provenance,
            _r0a_read_rec(node["protocol"], records.ProtocolIdentity),
            readiness.AmendmentProvenance(**_r0a_fields(node["amendment"],
                "sha256 byte_length external_receipt protocol_sha256 protocol_blob protocol_commit")),
            node["codec_profile_sha256"], R0APlanEvidenceV2(_v2_hex(plan["protocol_seed"]),
                tuple(_r0a_read_rec(board, records.BoardIdentity) for board in _r0a_list(plan["boards"], 64))),
            node["corpus_sha256"], tuple(runs),
            R0RunFileV2(**_r0a_fields(node["observations_file"], "path byte_length sha256")),
            inventory, tuple((name, forbidden[name]) for name, _ in R0_RUN_V2_FORBIDDEN_ACTIONS))
        _need(encode_r0_run_manifest_v2(value) == data, "R0_RUN_V2_NONCANONICAL_DOCUMENT")
        return value
    except EvidenceError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise EvidenceError("R0_RUN_V2_MALFORMED_MANIFEST") from None
