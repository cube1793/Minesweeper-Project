"""I8 pure R0 planning and outcome-blind admission (frozen protocol §§20–22).

No runner, board generation, persistence, bootstrap, publication or authorization
is performed here. Supplied measurements are claims to validate, not proof that
R0 happened. Even a successful selection is only a derived envelope proposal;
accepted real R0 evidence and later adjudication remain external prerequisites.
The sole I/O entry point, capture_review_sources, is a read-only pre-commit guard.
"""

from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction
from hashlib import sha1, sha256

from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_operational as operational
from experiments import program_k_e2_qualification as qualification
from experiments import program_k_e2_records as records


I7_BASELINE = "1e6355ecfc9497338d75ef3e723fddf2445d378b"
I8_BASELINE = "9071469e2e4a884722ea02e2faea3441d916876c"
AMENDMENT_PATH = "docs/stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md"
AMENDMENT_SHA256 = "5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf"
AMENDMENT_BYTE_LENGTH = 58_052
AMENDMENT_RECEIPT = "external-content-freeze-acceptance:2026-10-24:" + AMENDMENT_SHA256
SYNTHETIC_INDEX_LOW = 2_000_000_000_000
SYNTHETIC_SEARCH_LIMIT = 100_000
# Disjoint consecutive 10k blocks; finite 100k-candidate operational ceiling.
# Tests lower the attempt bound and use an explicitly synthetic protocol seed.
SYNTHETIC_INDEX_HIGH = SYNTHETIC_INDEX_LOW + SYNTHETIC_SEARCH_LIMIT * 10_000
CALIBRATION_ROUTES = ("P", "K", "D", "O", "O_K_BIND", "O_D_REPEAT",
                      "O_K_SETUP", "O_D_SETUP")
I8_PATHS = ("experiments/program_k_e2_readiness.py", "tests/test_program_k_e2_readiness.py")
I7_FIXTURE_PATH = "tests/test_program_k_e2_qualification.py"
REVIEW_PATHS = I8_PATHS + (I7_FIXTURE_PATH,)
AMENDMENT_CANDIDATE_PATHS = tuple("experiments/program_k_e2_" + name + ".py"
    for name in ("analysis", "audit", "execution", "operational", "readiness", "qualification"))
AMENDMENT_REVIEW_PATHS = AMENDMENT_CANDIDATE_PATHS + tuple(
    "tests/test_" + path.split("/")[-1] for path in AMENDMENT_CANDIDATE_PATHS)
POSTPROCESS_PHASES = (records.Phase.AGGREGATION, records.Phase.VALIDATION,
                      records.Phase.PUBLICATION, records.Phase.READBACK, records.Phase.REPORT)
_NS_PER_MS = 1_000_000
_NS_PER_SECOND = 1_000_000_000
_ROOT = qualification._ROOT
_git = qualification._git
_blobs = qualification._blobs


class ReadinessError(ValueError):
    """Invalid or incomplete operational facts; never a scientific verdict."""


def _need(condition, reason):
    if not condition:
        raise ReadinessError(reason)


def _integer(value, minimum=0):
    _need(type(value) is int and minimum <= value <= identity.UINT64_MAX,
          "EXACT_INTEGER_REQUIRED")


def _boolean(value):
    _need(type(value) is bool, "EXACT_BOOLEAN_REQUIRED")


def _seed(value):
    _need(type(value) is bytes and len(value) == 32, "EXACT_PROTOCOL_SEED_REQUIRED")


def _record(value, cls):
    _need(type(value) is cls, "EXACT_" + cls.__name__.upper() + "_REQUIRED")
    cls.__post_init__(value)
    return value


def _constants():
    """Reuse I1 authority; fail closed if a caller replaces frozen constants."""
    expected = (
        (identity.R0_A_BOARD_COUNT, 64), (identity.R0_A_CONCURRENCY_CANDIDATES, (1, 2, 4)),
        (identity.N_LADDER, (1000, 2500, 5000, 10000)), (identity.CANDIDATE_MAX, 10000),
        (identity.KCONTROL_CAP, 256), (identity.ORACLE_B_CAP, 128),
        (identity.DETERMINISM_CAP, 256), (identity.BOOTSTRAP_REPLICATES, 10000),
        (identity.EXECUTION_WALL_SAFETY_FACTOR, Fraction(2)),
        (identity.POSTPROCESS_WALL_SAFETY_FACTOR, Fraction(2)),
        (identity.ARCHIVE_BYTES_SAFETY_FACTOR, Fraction(3, 2)),
        (identity.MEMORY_SAFETY_FACTOR, Fraction(3, 2)),
        (identity.MAX_ACTUAL_E2_LAUNCHER_WALL_SECONDS, 43200),
        (identity.MAX_COMBINED_MEMORY_BYTES, 4294967296),
        (identity.MAX_ARCHIVE_BYTES, 17179869184),
        (identity.FIXED_REPORT_RECEIPT_ALLOWANCE, 268435456),
        (identity.MAX_DECISION_WALL_MS, 30000), (identity.MAX_ARM_WALL_MS, 420000),
        (identity.SHADOW_TIMEOUT_MS, 1000),
    )
    _need(all(type(a) is type(b) and a == b for a, b in expected), "FROZEN_CONSTANT_DRIFT")
    _need(all(type(n) is int for n in identity.N_LADDER + identity.R0_A_CONCURRENCY_CANDIDATES),
          "FROZEN_CONSTANT_DRIFT")


def ceil_fraction(value):
    """Conservative conversion only; admission compares the unrounded Fraction."""
    _need(type(value) is Fraction and value >= 0, "NONNEGATIVE_FRACTION_REQUIRED")
    return -(-value.numerator // value.denominator)


@dataclass(frozen=True, slots=True)
class AmendmentProvenance:
    sha256: str = AMENDMENT_SHA256
    byte_length: int = AMENDMENT_BYTE_LENGTH
    external_receipt: str = AMENDMENT_RECEIPT
    protocol_sha256: str = identity.PROTOCOL_SHA256
    protocol_blob: str = identity.PROTOCOL_BLOB_ID
    protocol_commit: str = identity.FREEZE_COMMIT

    def __post_init__(self):
        _need((self.sha256, self.byte_length, self.external_receipt,
               self.protocol_sha256, self.protocol_blob, self.protocol_commit) ==
              (AMENDMENT_SHA256, AMENDMENT_BYTE_LENGTH, AMENDMENT_RECEIPT,
               identity.PROTOCOL_SHA256, identity.PROTOCOL_BLOB_ID, identity.FREEZE_COMMIT),
              "FROZEN_AMENDMENT_PROVENANCE_REQUIRED")
        _integer(self.byte_length, 1)


@dataclass(frozen=True, slots=True)
class SubsetCounts:
    n: int
    u_kd: int
    i_od: int
    i_ok: int
    corpus_digest: bytes

    def __post_init__(self):
        _integer(self.n, 1)
        _need(self.n <= identity.CANDIDATE_MAX, "COUNT_POPULATION_DOMAIN")
        for value in (self.u_kd, self.i_od, self.i_ok):
            _integer(value)
        _seed(self.corpus_digest)
        k, d, o = min(self.n, 256), min(self.n, 256), min(self.n, 128)
        _need(max(k, d) <= self.u_kd <= min(self.n, k + d)
              and max(0, o + d - self.n) <= self.i_od <= min(o, d)
              and max(0, o + k - self.n) <= self.i_ok <= min(o, k), "SUBSET_COUNT_RANGE")


def _memberships(protocol_seed, indices):
    """Reuse the frozen digest/selector; no board or candidate-stream generation."""
    _seed(protocol_seed)
    _need(type(indices) is tuple and 0 < len(indices) <= identity.CANDIDATE_MAX,
          "ORDERED_CORPUS_REQUIRED")
    digest = identity.corpus_digest(protocol_seed, len(indices), indices)
    sets = tuple(frozenset(identity.select_subset_positions(label, protocol_seed,
        digest, len(indices), min(len(indices), cap))) for label, cap in (
            (identity.KCONTROL_LABEL, identity.KCONTROL_CAP),
            (identity.ORACLE_B_LABEL, identity.ORACLE_B_CAP),
            (identity.DETERMINISM_LABEL, identity.DETERMINISM_CAP)))
    return digest, sets


def subset_counts(protocol_seed, indices):
    """Pure supplied-corpus counts. Real target invocation requires later authority."""
    digest, (k, o, d) = _memberships(protocol_seed, indices)
    return SubsetCounts(len(indices), len(k | d), len(o & d), len(o & k), digest)


def target_counts(protocol_seed, n, ordered_candidate_prefix):
    """Prospective count helper; deliberately does not select a real prefix."""
    _constants()
    _need(type(n) is int and n in identity.N_LADDER
          and type(ordered_candidate_prefix) is tuple and len(ordered_candidate_prefix) == n,
          "ALLOWED_CANDIDATE_PREFIX_REQUIRED")
    return subset_counts(protocol_seed, ordered_candidate_prefix)


def validate_final_corpus_digest(counts, protocol_seed, indices):
    _record(counts, SubsetCounts)
    _need(len(indices) == counts.n and identity.corpus_digest(protocol_seed, counts.n, indices)
          == counts.corpus_digest, "PROSPECTIVE_FINAL_DIGEST_MISMATCH")


def _synthetic_domain(low, high):
    _integer(low)
    _integer(high, 1)
    _need(SYNTHETIC_INDEX_LOW <= low < high <= SYNTHETIC_INDEX_HIGH,
          "SYNTHETIC_DOMAIN_REQUIRED")
    forbidden = ((identity.PRIMARY_LOW, identity.PRIMARY_HIGH),
                 (identity.REHEARSAL_LOW, identity.REHEARSAL_HIGH),
                 (1_000_000_000, 1_001_100_000), (2_010_000, 2_010_100))
    forbidden += tuple(v.domain for v in identity.DOCUMENTED_EXPOSURE_REGISTRY if v.domain)
    _need(all(high <= a or low >= b for a, b in forbidden)
          and not any(low <= i < high for v in identity.DOCUMENTED_EXPOSURE_REGISTRY
                      for i in v.indices), "RESERVED_SYNTHETIC_DOMAIN")


def synthetic_candidate_indices(ordinal):
    _integer(ordinal)
    _need(ordinal < SYNTHETIC_SEARCH_LIMIT, "SYNTHETIC_SEARCH_BOUND")
    low = SYNTHETIC_INDEX_LOW + ordinal * identity.CANDIDATE_MAX
    high = low + identity.CANDIDATE_MAX
    _synthetic_domain(low, high)
    return tuple(range(low, high))


@dataclass(frozen=True, slots=True)
class SyntheticCorpusSelection:
    protocol_seed: bytes
    ordinal: int
    counts: SubsetCounts

    def __post_init__(self):
        _seed(self.protocol_seed)
        _record(self.counts, SubsetCounts)
        _need(self.counts == subset_counts(self.protocol_seed, self.ordered_indices),
              "SYNTHETIC_MEMBERSHIP_MISMATCH")

    @property
    def ordered_indices(self):
        return synthetic_candidate_indices(self.ordinal)


def search_synthetic_corpus(target_u_kd, target_i_od, target_i_ok, *,
        protocol_seed=bytes.fromhex(identity.PROTOCOL_SHA256),
        attempt_limit=SYNTHETIC_SEARCH_LIMIT, auxiliary_k_bind=False,
        auxiliary_d_repeat=False):
    """First matching block, or None (NOT READY), with no fallback.

    Production uses the frozen seed/domain/bound. Explicit seed and smaller
    attempt bound support bounded synthetic-only qualification; no real-target
    selection is performed at import or by readiness validation.
    """
    _seed(protocol_seed)
    _integer(attempt_limit, 1)
    _need(attempt_limit <= SYNTHETIC_SEARCH_LIMIT, "SYNTHETIC_SEARCH_BOUND")
    for value in (target_u_kd, target_i_od, target_i_ok):
        _integer(value)
    _need(256 <= target_u_kd <= 512 and target_i_od <= 128 and target_i_ok <= 128,
          "SYNTHETIC_TARGET_RANGE")
    _boolean(auxiliary_k_bind)
    _boolean(auxiliary_d_repeat)
    for ordinal in range(attempt_limit):
        counts = subset_counts(protocol_seed, synthetic_candidate_indices(ordinal))
        if (counts.u_kd >= target_u_kd
                and counts.i_od >= max(target_i_od, int(not auxiliary_d_repeat))
                and counts.i_ok >= max(target_i_ok, int(not auxiliary_k_bind))):
            return SyntheticCorpusSelection(protocol_seed, ordinal, counts)
    return None


def _rehearsal_indices(seed):
    _seed(seed)
    _constants()
    return identity.select_indices(identity.REHEARSAL_LABEL, seed,
        identity.REHEARSAL_LOW, identity.REHEARSAL_HIGH, identity.R0_A_BOARD_COUNT,
        identity.E2_REHEARSAL_EXCLUSION_SET)


@dataclass(frozen=True, slots=True)
class R0APlan:
    """Ordered index identities only. No fingerprints, boards or execution."""

    protocol_seed: bytes
    ordered_indices: tuple
    provenance: AmendmentProvenance = AmendmentProvenance()

    def __post_init__(self):
        _seed(self.protocol_seed)
        _record(self.provenance, AmendmentProvenance)
        _need(type(self.ordered_indices) is tuple, "ORDERED_IDENTITIES_REQUIRED")
        for index in self.ordered_indices:
            _integer(index)
        _need(self.ordered_indices == _rehearsal_indices(self.protocol_seed),
              "FIRST_64_REHEARSAL_IDENTITIES_REQUIRED")

    @property
    def schedule(self):
        _record(self, R0APlan)
        return tuple((c, self.ordered_indices) for c in identity.R0_A_CONCURRENCY_CANDIDATES)


def build_r0a_plan(protocol_seed):
    return R0APlan(protocol_seed, _rehearsal_indices(protocol_seed))


class WallAccounting(Enum):
    NON_OVERLAPPING = "NON_OVERLAPPING"
    CONSERVATIVE_STANDALONE = "CONSERVATIVE_STANDALONE"


class ByteAccounting(Enum):
    NON_OVERLAPPING = "NON_OVERLAPPING"


@dataclass(frozen=True, slots=True)
class ComponentMeasurement:
    """P/K/D directly timed standalone route and attributable bundle bytes only."""

    wall_ns: int
    durable_bytes: int
    max_unit_bytes: int
    completed_units: int

    def __post_init__(self):
        for value in (self.wall_ns, self.durable_bytes, self.max_unit_bytes):
            _integer(value, 1)
        _integer(self.completed_units)
        _need(self.completed_units <= identity.R0_A_BOARD_COUNT, "COMPONENT_COUNT")
        _need(self.max_unit_bytes <= self.durable_bytes
              <= identity.R0_A_BOARD_COUNT * self.max_unit_bytes, "COMPONENT_BYTE_ACCOUNTING")


@dataclass(frozen=True, slots=True)
class OracleMeasurement:
    """Scheduled route completion is independent of audit-only zero bytes."""
    wall_ns: int
    durable_bytes: int
    max_unit_bytes: int
    completed_units: int

    def __post_init__(self):
        _integer(self.wall_ns, 1)
        for value in (self.durable_bytes, self.max_unit_bytes, self.completed_units):
            _integer(value)
        _need(self.completed_units <= 64 and self.max_unit_bytes <= self.durable_bytes
              <= 64 * self.max_unit_bytes, "ORACLE_BYTE_ACCOUNTING")


@dataclass(frozen=True, slots=True)
class WallRouteMeasurement:
    wall_ns: int
    completed_units: int

    def __post_init__(self):
        _integer(self.wall_ns, 1)
        _integer(self.completed_units)
        _need(self.completed_units <= 64, "ROUTE_COUNT")


@dataclass(frozen=True, slots=True)
class ReferenceMeasurement:
    """Exact rank-0 CM observations from every setup route, never whole archives."""
    route: str
    durable_bytes: int
    max_unit_bytes: int
    completed_units: int

    def __post_init__(self):
        _need(self.route in ("K", "D", "O_K_SETUP", "O_D_SETUP"), "REFERENCE_ROUTE")
        for value in (self.durable_bytes, self.max_unit_bytes):
            _integer(value, 1)
        _integer(self.completed_units)
        _need(self.completed_units <= 64 and self.max_unit_bytes <= self.durable_bytes
              <= 64 * self.max_unit_bytes, "REFERENCE_BYTE_ACCOUNTING")


@dataclass(frozen=True, slots=True)
class RouteContainment:
    route: str
    max_worker_memory_bytes: int
    max_coordinator_memory_bytes: int
    max_combined_memory_bytes: int
    max_decision_wall_ns: int
    max_arm_wall_ns: int
    max_case_wall_ns: int
    max_shadow_wall_ns: int
    max_physical_inputs: int
    max_payload_bytes: int
    launcher_wall_ns: int
    watchdogs_complete: bool
    resources_complete: bool
    cleanup_complete: bool
    progress_complete: bool
    readback_complete: bool
    watchdog_breaches: int = 0
    resource_breaches: int = 0

    def __post_init__(self):
        _need(self.route in CALIBRATION_ROUTES, "CONTAINMENT_ROUTE")
        for name in _CONTAINMENT_MAXIMA + ("max_payload_bytes", "launcher_wall_ns"):
            _integer(getattr(self, name), 0 if name in (
                "max_decision_wall_ns", "max_shadow_wall_ns") else 1)
        _need(self.max_combined_memory_bytes >= max(self.max_worker_memory_bytes,
              self.max_coordinator_memory_bytes), "MEMORY_PEAK_ACCOUNTING")
        _need(self.max_decision_wall_ns <= self.max_arm_wall_ns <= self.max_case_wall_ns,
              "OBSERVED_WALL_ORDER")
        for name in _CONTAINMENT_COMPLETENESS + ("readback_complete",):
            _boolean(getattr(self, name))
        _integer(self.watchdog_breaches)
        _integer(self.resource_breaches)


_CONTAINMENT_MAXIMA = ("max_worker_memory_bytes", "max_coordinator_memory_bytes",
    "max_combined_memory_bytes", "max_decision_wall_ns", "max_arm_wall_ns",
    "max_case_wall_ns", "max_shadow_wall_ns", "max_physical_inputs")
_CONTAINMENT_COMPLETENESS = ("watchdogs_complete", "resources_complete",
                           "cleanup_complete", "progress_complete")


@dataclass(frozen=True, slots=True)
class R0AConcurrencyMeasurement:
    """Closed operational input; treatment outcomes cannot be supplied.

    Memory follows I6: peak committed worker Job trees plus coordinator private
    bytes. max_worker is the largest individual Job tree; max_combined is the
    peak concurrent SUM of active Job trees plus the coordinator, not RSS and
    not max_worker + max_coordinator from unrelated sampling instants.
    The envelope records tested provisional caps, not a final frozen envelope.
    """

    concurrency: int
    plan: R0APlan
    primary: ComponentMeasurement
    k_control: ComponentMeasurement
    oracle_primary: OracleMeasurement
    determinism: ComponentMeasurement
    oracle_k_bind: WallRouteMeasurement
    oracle_d_repeat: OracleMeasurement
    references: tuple
    containment: tuple
    wall_accounting: WallAccounting
    byte_accounting: ByteAccounting
    envelope: operational.OperatingEnvelope
    max_worker_memory_bytes: int
    max_coordinator_memory_bytes: int
    max_combined_memory_bytes: int
    max_decision_wall_ns: int
    max_arm_wall_ns: int
    max_case_wall_ns: int
    max_shadow_wall_ns: int
    max_physical_inputs: int
    watchdogs_complete: bool
    resources_complete: bool
    cleanup_complete: bool
    progress_complete: bool
    watchdog_breaches: int = 0
    resource_breaches: int = 0

    def __post_init__(self):
        _constants()
        _integer(self.concurrency, 1)
        _need(self.concurrency in identity.R0_A_CONCURRENCY_CANDIDATES, "CONCURRENCY_DOMAIN")
        _record(self.plan, R0APlan)
        for component in (self.primary, self.k_control, self.determinism):
            _record(component, ComponentMeasurement)
        for component in (self.oracle_primary, self.oracle_d_repeat):
            _record(component, OracleMeasurement)
        _record(self.oracle_k_bind, WallRouteMeasurement)
        _need(type(self.references) is tuple and tuple(v.route for v in self.references)
              == ("K", "D", "O_K_SETUP", "O_D_SETUP"), "REFERENCE_ROUTE_COVERAGE")
        for reference in self.references:
            _record(reference, ReferenceMeasurement)
        _need(type(self.containment) is tuple and tuple(v.route for v in self.containment)
              == CALIBRATION_ROUTES, "CONTAINMENT_ROUTE_COVERAGE")
        for route in self.containment:
            _record(route, RouteContainment)
        _need(self.wall_accounting is WallAccounting.CONSERVATIVE_STANDALONE,
              "COMPLETE_STANDALONE_WALL_REQUIRED")
        _need(type(self.byte_accounting) is ByteAccounting, "DISJOINT_BYTES_REQUIRED")
        _record(self.envelope, operational.OperatingEnvelope)
        _need(self.envelope.concurrency == self.concurrency, "ENVELOPE_CONCURRENCY_MISMATCH")
        for value in (self.max_worker_memory_bytes, self.max_coordinator_memory_bytes,
                      self.max_combined_memory_bytes, self.max_decision_wall_ns,
                      self.max_arm_wall_ns, self.max_case_wall_ns, self.max_shadow_wall_ns,
                      self.max_physical_inputs):
            _integer(value, 1)
        _need(self.max_combined_memory_bytes >= max(self.max_worker_memory_bytes,
              self.max_coordinator_memory_bytes), "MEMORY_PEAK_ACCOUNTING")
        _need(self.max_decision_wall_ns <= self.max_arm_wall_ns <= self.max_case_wall_ns,
              "OBSERVED_WALL_ORDER")
        for value in (self.watchdogs_complete, self.resources_complete,
                      self.cleanup_complete, self.progress_complete):
            _boolean(value)
        _integer(self.watchdog_breaches)
        _integer(self.resource_breaches)
        for name in _CONTAINMENT_MAXIMA:
            _need(getattr(self, name) >= max(getattr(v, name) for v in self.containment),
                  "CONTAINMENT_MAXIMUM_OMITTED")
        for name in ("watchdog_breaches", "resource_breaches"):
            _need(getattr(self, name) >= max(getattr(v, name) for v in self.containment),
                  "CONTAINMENT_BREACH_OMITTED")

    @property
    def primary_pairs_per_hour(self):
        _record(self, R0AConcurrencyMeasurement)
        return Fraction(identity.R0_A_BOARD_COUNT * 3600 * _NS_PER_SECOND, self.primary.wall_ns)


def _components(measurement):
    return (measurement.primary, measurement.k_control, measurement.determinism,
            measurement.oracle_primary, measurement.oracle_k_bind, measurement.oracle_d_repeat)


def validate_r0a_measurements(measurements):
    """Require all three complete same-64 runs; normalize only their input order."""
    _constants()
    _need(type(measurements) is tuple and len(measurements) == 3, "R0A_COVERAGE_REQUIRED")
    for value in measurements:
        _record(value, R0AConcurrencyMeasurement)
        _need(all(v.completed_units == identity.R0_A_BOARD_COUNT for v in _components(value)),
              "R0A_COMPONENT_INCOMPLETE")
        _need(value.watchdogs_complete and value.resources_complete and value.cleanup_complete
              and value.progress_complete, "R0A_OPERATIONAL_EVIDENCE_INCOMPLETE")
        _need(all(v.completed_units == 64 for v in value.references), "R0A_REFERENCE_INCOMPLETE")
        _need(all(all(getattr(v, name) for name in _CONTAINMENT_COMPLETENESS)
                  and v.readback_complete for v in value.containment), "R0A_ROUTE_INCOMPLETE")
    ordered = tuple(sorted(measurements, key=lambda v: v.concurrency))
    _need(tuple(v.concurrency for v in ordered) == identity.R0_A_CONCURRENCY_CANDIDATES,
          "R0A_CONCURRENCY_COVERAGE")
    _need(all(v.plan == ordered[0].plan for v in ordered), "R0A_IDENTITY_MISMATCH")
    return ordered


@dataclass(frozen=True, slots=True)
class ComponentSizes:
    primary: int
    k_control: int
    oracle_primary: int
    oracle_repeat: int
    determinism: int
    reference: int

    def __post_init__(self):
        for value in (self.primary, self.k_control, self.determinism, self.reference):
            _integer(value, 1)
        _integer(self.oracle_primary)
        _integer(self.oracle_repeat)


def _sizes(value):
    return (value.primary, value.k_control, value.oracle_primary, value.oracle_repeat,
            value.determinism, value.reference)


@dataclass(frozen=True, slots=True)
class SyntheticWorkload:
    selection: SyntheticCorpusSelection
    target: SubsetCounts
    auxiliary_k_bind_complete: bool = False
    auxiliary_d_repeat_complete: bool = False

    def __post_init__(self):
        _record(self.selection, SyntheticCorpusSelection)
        _record(self.target, SubsetCounts)
        _need(self.target.n == identity.CANDIDATE_MAX, "NMAX_TARGET_REQUIRED")
        _boolean(self.auxiliary_k_bind_complete)
        _boolean(self.auxiliary_d_repeat_complete)
        actual = self.selection.counts
        _need(all(getattr(actual, n) >= getattr(self.target, n)
                  for n in ("u_kd", "i_od", "i_ok")), "SYNTHETIC_COUNT_DOMINANCE")
        _need((actual.i_ok > 0 or self.auxiliary_k_bind_complete)
              and (actual.i_od > 0 or self.auxiliary_d_repeat_complete),
              "ORACLE_STRUCTURAL_COVERAGE_REQUIRED")

    @property
    def unit_counts(self):
        actual = self.selection.counts
        return (10000, 256, 128, actual.i_od, 256, actual.u_kd)


def validate_synthetic_work_plan(plan, workload):
    """Later harness seam. Retain I7 and exact own-corpus membership validation."""
    _record(workload, SyntheticWorkload)
    qualification._plan(plan)
    _need(plan[0].protocol_seed == workload.selection.protocol_seed
          and tuple(v.board.game_index for v in plan) == workload.selection.ordered_indices,
          "SYNTHETIC_WORK_PLAN_IDENTITY")
    return plan


@dataclass(frozen=True, slots=True)
class R0BSizingPlan:
    """Minimum durable per-unit payloads, not materialized synthetic records."""

    protocol_seed: bytes
    unit_bytes: ComponentSizes

    def __post_init__(self):
        _constants()
        _seed(self.protocol_seed)
        _record(self.unit_bytes, ComponentSizes)

    @property
    def n_max(self):
        return identity.CANDIDATE_MAX

def derive_r0b_sizing_plan(measurements):
    values = validate_r0a_measurements(measurements)
    oracle = max(o.max_unit_bytes for v in values for o in (v.oracle_primary, v.oracle_d_repeat))
    maxima = (max(v.primary.max_unit_bytes for v in values),
              max(v.k_control.max_unit_bytes for v in values), oracle, oracle,
              max(v.determinism.max_unit_bytes for v in values),
              max(r.max_unit_bytes for v in values for r in v.references))
    sizes = ComponentSizes(*(ceil_fraction(identity.ARCHIVE_BYTES_SAFETY_FACTOR * v) for v in maxima))
    return R0BSizingPlan(values[0].plan.protocol_seed, sizes)


def synthetic_unit_payloads(workload, sizes):
    """All actual PRIMARY/D/K composite units, including zero-byte O schedules."""
    _record(workload, SyntheticWorkload)
    _record(sizes, ComponentSizes)
    _, (k, o, d) = _memberships(workload.selection.protocol_seed,
                               workload.selection.ordered_indices)
    result = []
    for position in range(identity.CANDIDATE_MAX):
        families = ("primary",) + (("reference",) if position in k | d else ())
        families += ("oracle_primary",) if position in o else ()
        result.append((position, "PRIMARY", families, sum(getattr(sizes, f) for f in families)))
        if position in d:
            families = ("determinism",) + (("oracle_repeat",) if position in o else ())
            result.append((position, "DETERMINISM", families, sum(getattr(sizes, f) for f in families)))
        if position in k:
            result.append((position, "K_CONTROL", ("k_control",), sizes.k_control))
    return tuple(result)


def validate_payload_fit(workload, sizes, max_payload_bytes):
    _integer(max_payload_bytes, 1)
    _need(all(v[3] <= max_payload_bytes for v in synthetic_unit_payloads(workload, sizes)),
          "R0B_COMPOSITE_PAYLOAD_CAP")


V2_FAMILIES = ("primary", "k_control", "oracle_primary", "oracle_repeat", "determinism", "reference")


@dataclass(frozen=True, slots=True)
class DualComponentSizes:
    """Supplied independent V2 bases, not a historical V1 measurement adapter."""

    physical: ComponentSizes
    logical: ComponentSizes

    def __post_init__(self):
        _record(self.physical, ComponentSizes)
        _record(self.logical, ComponentSizes)
        for family in ("oracle_primary", "oracle_repeat"):
            _need((getattr(self.physical, family) == 0) == (getattr(self.logical, family) == 0),
                  "ZERO_ORACLE_BASES_MUST_AGREE")


def derive_dual_targets(maxima):
    """Exact independent ceil(3/2) floors from supplied authenticated maxima.

    No measurement collection, witness coupling, constructor or qualification
    occurs here. These values are not added to the historical V1 fact registry.
    """
    _constants()
    _record(maxima, DualComponentSizes)
    return DualComponentSizes(*(ComponentSizes(*((3 * value + 1) // 2 for value in _sizes(basis)))
                                for basis in (maxima.physical, maxima.logical)))


@dataclass(frozen=True, slots=True)
class FamilySizeEvaluation:
    """Exact size-policy facts; eligibility is not run admission or evidence."""

    family: str
    physical_target: int
    logical_target: int
    actual_physical_bytes: int
    actual_logical_bytes: int

    def __post_init__(self):
        _need(type(self.family) is str and self.family in V2_FAMILIES, "EXACT_V2_FAMILY_REQUIRED")
        oracle = self.family in ("oracle_primary", "oracle_repeat")
        _integer(self.physical_target, 0 if oracle else 1)
        _integer(self.logical_target, 0 if oracle else 1)
        _integer(self.actual_physical_bytes)
        _integer(self.actual_logical_bytes)
        if oracle and (self.physical_target == 0 or self.logical_target == 0):
            _need(self.physical_target == self.logical_target == 0
                  and self.actual_physical_bytes == self.actual_logical_bytes == 0,
                  "ZERO_ORACLE_REQUIRES_EXACT_ZERO")

    @property
    def physical_margin(self):
        return self.actual_physical_bytes - self.physical_target

    @property
    def logical_margin(self):
        return self.actual_logical_bytes - self.logical_target

    @property
    def physical_excess(self):
        return max(self.physical_margin, 0)

    @property
    def logical_excess(self):
        return max(self.logical_margin, 0)

    @property
    def text_window_applies(self):
        return self.family != "reference" and self.physical_target > 0

    @property
    def text_window_upper_bound(self):
        return self.physical_target + 4096 if self.text_window_applies else None

    @property
    def rejection_reason(self):
        if self.physical_margin < 0 and self.logical_margin < 0:
            return "SYNTHETIC_BOTH_MINIMA_SHORTFALL"
        if self.physical_margin < 0:
            return "SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL"
        if self.logical_margin < 0:
            return "SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL"
        if self.text_window_applies and self.actual_physical_bytes > self.text_window_upper_bound:
            return "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT"
        return None

    @property
    def eligible(self):
        return self.rejection_reason is None


def evaluate_family_size(family, physical_target, logical_target, actual_physical_bytes, actual_logical_bytes):
    return FamilySizeEvaluation(family, physical_target, logical_target, actual_physical_bytes, actual_logical_bytes)


def validate_dual_payload_fit(workload, targets, max_payload_bytes):
    """Both bases must fit every actual unit; retain V1 physical diagnostics."""
    _record(targets, DualComponentSizes)
    validate_payload_fit(workload, targets.physical, max_payload_bytes)
    _need(all(unit[3] <= max_payload_bytes for unit in synthetic_unit_payloads(workload, targets.logical)),
          "LOGICAL_MINIMUM_COMPOSITE_CAP")


def _unit_counts_v2(unit_counts):
    """Closed order of supplied accepted workload.unit_counts, never a recount."""
    _need(type(unit_counts) is tuple and len(unit_counts) == len(V2_FAMILIES), "EXACT_V2_UNIT_COUNTS_REQUIRED")
    for count in unit_counts:
        _integer(count)
    _need(unit_counts[:3] == (identity.CANDIDATE_MAX, identity.KCONTROL_CAP, identity.ORACLE_B_CAP)
          and unit_counts[4] == identity.DETERMINISM_CAP
          and unit_counts[3] <= identity.ORACLE_B_CAP
          and max(identity.KCONTROL_CAP, identity.DETERMINISM_CAP) <= unit_counts[5]
              <= identity.KCONTROL_CAP + identity.DETERMINISM_CAP, "V2_UNIT_COUNT_DOMAIN")
    return unit_counts


def _physical_minimum_v2(physical_targets, unit_counts):
    _constants()
    _record(physical_targets, ComponentSizes)
    _unit_counts_v2(unit_counts)
    return sum(count * target for count, target in zip(unit_counts, _sizes(physical_targets)))


def minimum_archive_preflight(physical_targets, unit_counts, proven_support_bytes=0):
    """Only proven physical lower bounds; no full fixed-allowance reservation."""
    minimum = _physical_minimum_v2(physical_targets, unit_counts)
    _integer(proven_support_bytes)
    archive_minimum = minimum + proven_support_bytes
    _need(archive_minimum <= identity.MAX_ARCHIVE_BYTES, "SYNTHETIC_MINIMUM_ARCHIVE_CAP")
    return archive_minimum


def procedural_excess_capacity(physical_targets, unit_counts):
    """Procedural fixed reservation only, not a scientific impossibility verdict."""
    minimum = _physical_minimum_v2(physical_targets, unit_counts)
    capacity = identity.MAX_ARCHIVE_BYTES - identity.FIXED_REPORT_RECEIPT_ALLOWANCE - minimum
    _need(capacity >= 0, "SYNTHETIC_PROCEDURAL_FIXED_RESERVATION_INFEASIBLE")
    return capacity


def unit_physical_excess(observations):
    """One complete unit's supplied owned families; no copied-reference inference.

    Only eligible physical excess is chargeable. Logical surplus, rejected
    candidates and unused window/allowance cannot become credits or offsets.
    """
    _need(type(observations) is tuple and 0 < len(observations) <= len(V2_FAMILIES),
          "COMPLETE_UNIT_FAMILY_OBSERVATIONS_REQUIRED")
    names = []
    total = 0
    for observation in observations:
        _record(observation, FamilySizeEvaluation)
        _need(observation.family not in names, "DUPLICATE_UNIT_FAMILY")
        _need(observation.eligible, observation.rejection_reason)
        names.append(observation.family)
        total += observation.physical_excess
    return total


@dataclass(frozen=True, slots=True)
class ProceduralLedger:
    """Pure serial state; reserving is not durable and there is no refund path."""

    capacity: int
    committed_excess: int = 0
    reserved_excess: int = 0
    reservation_pending: bool = False

    def __post_init__(self):
        _constants()
        for amount in (self.capacity, self.committed_excess, self.reserved_excess):
            _integer(amount)
        _boolean(self.reservation_pending)
        _need(self.capacity <= identity.MAX_ARCHIVE_BYTES - identity.FIXED_REPORT_RECEIPT_ALLOWANCE,
              "PROCEDURAL_CAPACITY_DOMAIN")
        _need(self.reservation_pending or self.reserved_excess == 0, "RESERVATION_STATE_MISMATCH")
        _need(self.committed_excess + self.reserved_excess <= self.capacity,
              "SYNTHETIC_PROCEDURAL_EXCESS_BUDGET")


def reserve_procedural_unit(ledger, observations):
    """Reserve the whole unit before its first attributable persistence call."""
    _record(ledger, ProceduralLedger)
    _need(not ledger.reservation_pending, "PROCEDURAL_RESERVATION_ALREADY_PENDING")
    delta = unit_physical_excess(observations)
    _need(ledger.committed_excess + delta <= ledger.capacity, "SYNTHETIC_PROCEDURAL_EXCESS_BUDGET")
    return replace(ledger, reserved_excess=delta, reservation_pending=True)


def commit_procedural_unit(ledger):
    """Caller invokes only after required durability; this function performs no I/O."""
    _record(ledger, ProceduralLedger)
    _need(ledger.reservation_pending, "PROCEDURAL_RESERVATION_REQUIRED")
    return ProceduralLedger(ledger.capacity, ledger.committed_excess + ledger.reserved_excess)


def reconcile_procedural_excess(physical_targets, unit_counts, physical_totals, ledger):
    """Reconcile attributable physical excess only; final archive checks remain.

    Future close must independently check realized fixed allowance and actual
    total archive caps. Neither support nor logical bytes are excess terms here.
    """
    capacity = procedural_excess_capacity(physical_targets, unit_counts)
    _record(physical_totals, ComponentSizes)
    _record(ledger, ProceduralLedger)
    _need(not ledger.reservation_pending, "PROCEDURAL_RESERVATION_STILL_PENDING")
    _need(ledger.capacity == capacity, "PROCEDURAL_CAPACITY_BINDING")
    excess = 0
    for count, target, actual in zip(unit_counts, _sizes(physical_targets), _sizes(physical_totals)):
        minimum = count * target
        _need(actual >= minimum, "SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL")
        _need((count > 0 and target > 0) or actual == 0, "ZERO_FAMILY_REQUIRES_EXACT_TOTAL_ZERO")
        excess += actual - minimum
    _need(excess <= capacity, "SYNTHETIC_PROCEDURAL_EXCESS_BUDGET")
    _need(excess == ledger.committed_excess, "PROCEDURAL_EXCESS_RECONCILIATION")
    return excess


@dataclass(frozen=True, slots=True)
class SupportingStreams:
    """Actual sealed I7 supports; receipt/status claims stay outside bundle sizes."""
    streams: tuple
    receipts_complete: bool
    status_complete: bool
    work_plan_revalidated: bool
    qualification_complete: bool
    resources_complete: bool
    cleanup_complete: bool

    def __post_init__(self):
        _need(type(self.streams) is tuple and tuple(v.name for v in self.streams)
              == ("operations", "resources", qualification.IDENTITY_STREAM),
              "R0B_SUPPORTING_STREAM_COVERAGE")
        for value in self.streams:
            _record(value, records.StreamDigest)
            _need(value.byte_length > 0 and value.record_count > 0, "R0B_SUPPORTING_STREAM_EMPTY")
        for value in (self.receipts_complete, self.status_complete, self.work_plan_revalidated,
                      self.qualification_complete, self.resources_complete, self.cleanup_complete):
            _boolean(value)
            _need(value, "R0B_SUPPORTING_STRUCTURE_INCOMPLETE")


@dataclass(frozen=True, slots=True)
class PhaseMeasurement:
    phase: records.Phase
    wall_ns: int
    processed: int
    total: int
    output_bytes: int
    complete: bool
    progress_bounded: bool

    def __post_init__(self):
        _need(type(self.phase) is records.Phase and self.phase in POSTPROCESS_PHASES,
              "POSTPROCESS_PHASE_REQUIRED")
        _integer(self.wall_ns, 1)
        _integer(self.processed)
        _integer(self.total, 1)
        _integer(self.output_bytes)
        _need(self.processed <= self.total, "PHASE_PROGRESS_RANGE")
        _boolean(self.complete)
        _boolean(self.progress_bounded)


@dataclass(frozen=True, slots=True)
class R0BMeasurement:
    """Complete Nmax non-evidence postprocessing facts supplied by a later run.

    Phase walls are non-overlapping; AGGREGATION includes the full shared
    bootstrap. complete_wall_ns also includes orchestration between phases.
    progress_bounded attests bounded progress throughout that complete interval,
    including any residual overhead, not just the five reported phase intervals.
    streaming_reconstruction attests the entire §18 durable-processing contract:
    at most one reconstruction pass per phase, linear publication/readback/report
    plus declared sorting, and no repeated whole-corpus reconstruction per record.
    unit_bytes describes actual minimum generated payload sizes per unit family.
    archive_bytes includes the input/output archive; no output is materialized.
    """

    protocol_seed: bytes
    n_max: int
    complete_wall_ns: int
    phases: tuple
    bootstrap_replicates: int
    bootstrap_n: int
    shared_bootstrap_complete: bool
    compact_scalar_bootstrap: bool
    streaming_reconstruction: bool
    readback_complete: bool
    progress_bounded: bool
    synthetic_non_evidence: bool
    unit_bytes: ComponentSizes
    archive_bytes: int
    workload: SyntheticWorkload
    supporting: SupportingStreams
    realized_fixed_allowance_bytes: int
    realized_max_unit_payload_bytes: int
    max_combined_memory_bytes: int
    containment_complete: bool
    provenance: AmendmentProvenance = AmendmentProvenance()

    def __post_init__(self):
        _constants()
        _seed(self.protocol_seed)
        for value in (self.n_max, self.complete_wall_ns, self.bootstrap_replicates,
                      self.bootstrap_n, self.archive_bytes):
            _integer(value, 1)
        _need(type(self.phases) is tuple, "EXACT_PHASE_TUPLE_REQUIRED")
        for phase in self.phases:
            _record(phase, PhaseMeasurement)
        _record(self.unit_bytes, ComponentSizes)
        _record(self.workload, SyntheticWorkload)
        _record(self.supporting, SupportingStreams)
        _record(self.provenance, AmendmentProvenance)
        _integer(self.realized_fixed_allowance_bytes)
        _integer(self.realized_max_unit_payload_bytes, 1)
        _integer(self.max_combined_memory_bytes, 1)
        _boolean(self.containment_complete)
        for value in (self.shared_bootstrap_complete, self.compact_scalar_bootstrap,
                      self.streaming_reconstruction, self.readback_complete,
                      self.progress_bounded, self.synthetic_non_evidence):
            _boolean(value)


def _complete_r0b(value):
    _record(value, R0BMeasurement)
    _need(value.n_max == value.bootstrap_n == identity.CANDIDATE_MAX
          and value.bootstrap_replicates == identity.BOOTSTRAP_REPLICATES,
          "FULL_NMAX_BOOTSTRAP_REQUIRED")
    _need(tuple(p.phase for p in value.phases) == POSTPROCESS_PHASES, "POSTPROCESS_PHASE_COVERAGE")
    _need(all(p.complete and p.progress_bounded and p.processed == p.total for p in value.phases),
          "POSTPROCESS_PHASE_INCOMPLETE")
    _need(value.complete_wall_ns >= sum(p.wall_ns for p in value.phases),
          "POSTPROCESS_WALL_ACCOUNTING")
    _need(value.shared_bootstrap_complete and value.compact_scalar_bootstrap
          and value.streaming_reconstruction and value.readback_complete
          and value.progress_bounded and value.synthetic_non_evidence,
          "R0B_READINESS_INCOMPLETE")
    _need(value.containment_complete, "R0B_CONTAINMENT_INCOMPLETE")
    _need(value.realized_fixed_allowance_bytes <= identity.FIXED_REPORT_RECEIPT_ALLOWANCE,
          "R0B_FIXED_ALLOWANCE_CAP")
    report_bytes = next(p.output_bytes for p in value.phases if p.phase is records.Phase.REPORT)
    _need(value.realized_fixed_allowance_bytes >= sum(v.byte_length for v in value.supporting.streams)
          + report_bytes,
          "R0B_SUPPORTING_BYTE_ACCOUNTING")
    _need(value.archive_bytes <= identity.MAX_ARCHIVE_BYTES, "R0B_ARCHIVE_CAP")
    _need(identity.POSTPROCESS_WALL_SAFETY_FACTOR * value.complete_wall_ns
          <= identity.MAX_ACTUAL_E2_LAUNCHER_WALL_SECONDS * _NS_PER_SECOND,
          "R0B_POSTPROCESS_WALL_CAP")
    _need(identity.MEMORY_SAFETY_FACTOR * value.max_combined_memory_bytes
          <= identity.MAX_COMBINED_MEMORY_BYTES, "R0B_MEMORY_CAP")
    return value


def validate_r0b_measurement(value, measurements):
    _complete_r0b(value)
    sizing = derive_r0b_sizing_plan(measurements)
    _need(value.protocol_seed == sizing.protocol_seed == value.workload.selection.protocol_seed,
          "R0B_PROTOCOL_IDENTITY_MISMATCH")
    _need(all(actual >= needed for actual, needed in zip(_sizes(value.unit_bytes),
              _sizes(sizing.unit_bytes))), "R0B_PAYLOAD_UNDERSIZED")
    _need(value.archive_bytes >= sum(n * size for n, size in
              zip(value.workload.unit_counts, _sizes(value.unit_bytes)))
          + value.realized_fixed_allowance_bytes, "R0B_ARCHIVE_ACCOUNTING")
    _need(value.archive_bytes >= max(p.output_bytes for p in value.phases), "R0B_OUTPUT_ACCOUNTING")
    cap = min(v.envelope.max_payload_bytes for v in measurements)
    validate_payload_fit(value.workload, value.unit_bytes, cap)
    minimum_maximum = max(v[3] for v in synthetic_unit_payloads(value.workload, value.unit_bytes))
    _need(minimum_maximum <= value.realized_max_unit_payload_bytes <= cap,
          "R0B_REALIZED_PAYLOAD_CAP")
    return value


def _scaled(n, values, counts):
    _constants()
    _integer(n, 1)
    _need(n <= identity.CANDIDATE_MAX, "PROJECTION_N_DOMAIN")
    _need(len(values) == len(counts), "PROJECTION_TERM_COUNT")
    return sum((Fraction(value * count, identity.R0_A_BOARD_COUNT)
                for value, count in zip(values, counts)), Fraction())


def project_execution(n, measurement, counts):
    _record(measurement, R0AConcurrencyMeasurement)
    _record(counts, SubsetCounts)
    _need(counts.n == n, "PROJECTION_COUNT_POPULATION")
    return identity.EXECUTION_WALL_SAFETY_FACTOR * _scaled(n,
        tuple(v.wall_ns for v in _components(measurement)),
        (n, min(n, 256), min(n, 256), min(n, 128), counts.i_ok, counts.i_od))


def project_postprocess(measurement):
    _complete_r0b(measurement)
    return identity.POSTPROCESS_WALL_SAFETY_FACTOR * measurement.complete_wall_ns


def project_archive(n, measurements, counts):
    """Concurrency-independent §21.6 projection.

    Conservative implementation convention: use the componentwise largest
    durable totals across c1/c2/c4. This prevents a concurrency-dependent archive
    estimate when serialization/progress overhead differs between rehearsals.
    """
    values = validate_r0a_measurements(measurements)
    _record(counts, SubsetCounts)
    _need(counts.n == n, "PROJECTION_COUNT_POPULATION")
    maxima = (max(v.primary.durable_bytes for v in values),
              max(v.k_control.durable_bytes for v in values),
              max(o.durable_bytes for v in values for o in (v.oracle_primary, v.oracle_d_repeat)),
              max(v.determinism.durable_bytes for v in values),
              max(r.durable_bytes for v in values for r in v.references))
    return identity.ARCHIVE_BYTES_SAFETY_FACTOR * _scaled(n, maxima,
        (n, min(n, 256), min(n, 128) + counts.i_od, min(n, 256), counts.u_kd)
        ) + identity.FIXED_REPORT_RECEIPT_ALLOWANCE


def project_memory(measurement, r0b=None):
    _record(measurement, R0AConcurrencyMeasurement)
    maximum = measurement.max_combined_memory_bytes
    if r0b is not None:
        _complete_r0b(r0b)
        maximum = max(maximum, r0b.max_combined_memory_bytes)
    return identity.MEMORY_SAFETY_FACTOR * maximum


def _cap_reasons(value):
    envelope = value.envelope
    reasons = []
    if value.watchdog_breaches:
        reasons.append("WATCHDOG_BREACH")
    if value.resource_breaches:
        reasons.append("RESOURCE_BREACH")
    # I6 aborts at >= for decision/arm/case. The accepted shadow owner uses >.
    for name, observed, cap in (
        ("DECISION", value.max_decision_wall_ns, envelope.max_decision_wall_ms),
        ("ARM", value.max_arm_wall_ns, envelope.max_arm_wall_ms),
        ("CASE", value.max_case_wall_ns, envelope.max_case_wall_ms),
    ):
        if observed >= cap * _NS_PER_MS:
            reasons.append(name + "_CAP")
    if value.max_shadow_wall_ns > envelope.shadow_timeout_ms * _NS_PER_MS:
        reasons.append("SHADOW_CAP")
    if (value.max_worker_memory_bytes > envelope.worker_memory_cap_bytes
            or value.max_coordinator_memory_bytes > envelope.coordinator_memory_cap_bytes
            or value.max_combined_memory_bytes > envelope.memory_cap_bytes):
        reasons.append("TESTED_MEMORY_CAP")
    if value.max_physical_inputs > envelope.max_physical_inputs:
        reasons.append("PHYSICAL_INPUT_CAP")
    if (sum(v.durable_bytes for v in (value.primary, value.k_control,
            value.determinism, value.oracle_primary, value.oracle_d_repeat))
            + max(v.durable_bytes for v in value.references)) > envelope.archive_cap_bytes:
        reasons.append("TESTED_ARCHIVE_CAP")
    if any(v.max_payload_bytes > envelope.max_payload_bytes for v in value.containment):
        reasons.append("PAYLOAD_CAP")
    if any(v.launcher_wall_ns >= envelope.max_launcher_wall_ms * _NS_PER_MS
           for v in value.containment):
        reasons.append("CALIBRATION_LAUNCHER_CAP")
    if any(v.launcher_wall_ns >= envelope.max_job_wall_ms * _NS_PER_MS
           for v in value.containment):
        reasons.append("CALIBRATION_JOB_CAP")
    return tuple(reasons)


@dataclass(frozen=True, slots=True)
class AdmissionProjection:
    n: int
    concurrency: int
    execution_wall_ns: Fraction
    postprocess_wall_ns: Fraction
    launcher_wall_ns: Fraction
    archive_bytes: Fraction
    memory_bytes: Fraction
    primary_pairs_per_hour: Fraction
    reasons: tuple

    def __post_init__(self):
        _constants()
        _integer(self.n, 1)
        _integer(self.concurrency, 1)
        _need(self.n in identity.N_LADDER and self.concurrency in identity.R0_A_CONCURRENCY_CANDIDATES,
              "ADMISSION_PAIR_DOMAIN")
        for value in (self.execution_wall_ns, self.postprocess_wall_ns, self.launcher_wall_ns,
                      self.archive_bytes, self.memory_bytes, self.primary_pairs_per_hour):
            _need(type(value) is Fraction and value > 0, "POSITIVE_FRACTION_REQUIRED")
        _need(self.launcher_wall_ns == self.execution_wall_ns + self.postprocess_wall_ns,
              "LAUNCHER_ACCOUNTING")
        allowed = ("WATCHDOG_BREACH", "RESOURCE_BREACH", "DECISION_CAP", "ARM_CAP", "CASE_CAP",
                   "SHADOW_CAP", "TESTED_MEMORY_CAP", "PHYSICAL_INPUT_CAP", "TESTED_ARCHIVE_CAP",
                   "PAYLOAD_CAP", "CALIBRATION_LAUNCHER_CAP",
                   "CALIBRATION_JOB_CAP",
                   "LAUNCHER_CEILING", "ARCHIVE_CEILING", "MEMORY_CEILING")
        _need(type(self.reasons) is tuple and all(type(v) is str and v in allowed for v in self.reasons)
              and self.reasons == tuple(v for v in allowed if v in self.reasons), "ADMISSION_REASON_DOMAIN")
        for reason, observed, cap in (
            ("LAUNCHER_CEILING", self.launcher_wall_ns, identity.MAX_ACTUAL_E2_LAUNCHER_WALL_SECONDS * _NS_PER_SECOND),
            ("ARCHIVE_CEILING", self.archive_bytes, identity.MAX_ARCHIVE_BYTES),
            ("MEMORY_CEILING", self.memory_bytes, identity.MAX_COMBINED_MEMORY_BYTES),
        ):
            _need((reason in self.reasons) == (observed > cap), "PROJECTION_CEILING_RECONCILIATION")

    @property
    def admitted(self):
        return not self.reasons


class AdmissionState(Enum):
    CANDIDATE_PROPOSED = "CANDIDATE_PROPOSED"
    ACTUAL_E2_NOT_READY = "ACTUAL_E2_NOT_READY"


@dataclass(frozen=True, slots=True)
class CandidateEnvelopeProposal:
    """Not a freeze or authorization. No publisher/launcher exists in I8."""

    n: int
    envelope: operational.OperatingEnvelope
    projection: AdmissionProjection
    target_counts: SubsetCounts
    provenance: AmendmentProvenance = AmendmentProvenance()

    def __post_init__(self):
        _integer(self.n, 1)
        _record(self.envelope, operational.OperatingEnvelope)
        _record(self.projection, AdmissionProjection)
        _record(self.target_counts, SubsetCounts)
        _record(self.provenance, AmendmentProvenance)
        _need(self.target_counts.n == self.n, "PROPOSAL_TARGET_POPULATION")
        _need(self.projection.admitted and self.n == self.projection.n
              and self.envelope.concurrency == self.projection.concurrency,
              "ADMITTED_PROPOSAL_REQUIRED")
        _need(self.envelope.max_job_wall_ms * _NS_PER_MS >= self.projection.execution_wall_ns
              and self.envelope.max_launcher_wall_ms * _NS_PER_MS >= self.projection.launcher_wall_ns
              and self.envelope.archive_cap_bytes >= self.projection.archive_bytes
              and self.envelope.memory_cap_bytes >= self.projection.memory_bytes,
              "CONSERVATIVE_PROPOSAL_CAPS_REQUIRED")

    @property
    def frozen(self):
        return False

    @property
    def actual_e2_authorized(self):
        return False


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    state: AdmissionState
    projections: tuple
    candidate: CandidateEnvelopeProposal | None
    target_counts: tuple
    realized_synthetic_counts: SubsetCounts
    provenance: AmendmentProvenance = AmendmentProvenance()

    def __post_init__(self):
        _constants()
        _record(self.provenance, AmendmentProvenance)
        _record(self.realized_synthetic_counts, SubsetCounts)
        _validate_targets(self.target_counts)
        _need(self.realized_synthetic_counts.n == identity.CANDIDATE_MAX
              and all(getattr(self.realized_synthetic_counts, name)
                      >= getattr(self.target_counts[-1], name)
                      for name in ("u_kd", "i_od", "i_ok")), "ADMISSION_SYNTHETIC_DOMINANCE")
        _need(type(self.state) is AdmissionState and type(self.projections) is tuple,
              "ADMISSION_DECISION_TYPE")
        for projection in self.projections:
            _record(projection, AdmissionProjection)
        _need(tuple((p.n, p.concurrency) for p in self.projections) == tuple(
            (n, c) for n in identity.N_LADDER for c in identity.R0_A_CONCURRENCY_CANDIDATES),
            "ADMISSION_PROJECTION_COVERAGE")
        admitted = tuple(p for p in self.projections if p.admitted)
        if self.state is AdmissionState.ACTUAL_E2_NOT_READY:
            _need(not admitted and self.candidate is None, "NOT_READY_RECONCILIATION")
        else:
            _record(self.candidate, CandidateEnvelopeProposal)
            _need(self.candidate.target_counts == next(v for v in self.target_counts
                  if v.n == self.candidate.n), "ADMISSION_TARGET_IDENTITY")
            _need(bool(admitted) and self.candidate.projection == max(admitted,
                  key=lambda p: (p.n, p.primary_pairs_per_hour, -p.concurrency)),
                  "SELECTION_PRIORITY")


def _proposal(value, r0b, projection, counts):
    """Only scaling-dependent caps change; tested unit safety caps are retained.

    Ceil each Fraction to integer ms/bytes. Individual rounded phase budgets may
    sum above the rounded launcher by a few ms; the independent launcher ceiling
    still applies. Preserve the tested per-case ceiling if projection is smaller.
    """
    ms = lambda ns: ceil_fraction(Fraction(ns, _NS_PER_MS))
    job = max(value.envelope.max_case_wall_ms, ms(projection.execution_wall_ns))
    launcher = max(job, ms(projection.launcher_wall_ns))
    phases = tuple(ms(identity.POSTPROCESS_WALL_SAFETY_FACTOR * p.wall_ns) for p in r0b.phases)
    envelope = replace(value.envelope, max_job_wall_ms=job, max_launcher_wall_ms=launcher,
        worker_memory_cap_bytes=ceil_fraction(identity.MEMORY_SAFETY_FACTOR * value.max_worker_memory_bytes),
        coordinator_memory_cap_bytes=ceil_fraction(identity.MEMORY_SAFETY_FACTOR * max(
            value.max_coordinator_memory_bytes, r0b.max_combined_memory_bytes)),
        memory_cap_bytes=ceil_fraction(projection.memory_bytes),
        archive_cap_bytes=ceil_fraction(projection.archive_bytes),
        aggregation_wall_ms=phases[0], validation_wall_ms=phases[1], publication_wall_ms=phases[2],
        readback_wall_ms=phases[3], report_wall_ms=phases[4])
    return CandidateEnvelopeProposal(projection.n, envelope, projection, counts)


def _validate_targets(targets):
    _need(type(targets) is tuple, "TARGET_COUNT_TUPLE_REQUIRED")
    for value in targets:
        _record(value, SubsetCounts)
    _need(tuple(v.n for v in targets) == identity.N_LADDER, "TARGET_COUNT_LADDER_REQUIRED")
    return targets


def select_operating_candidate(measurements, r0b, target_counts):
    """Pure complete-facts admission; no measured facts are acquired here.

    Malformed/incomplete facts raise ReadinessError (or the reused I6 envelope
    validator's ValueError). Complete but inadmissible configurations produce a
    NOT_READY decision. Neither path is a research verdict.
    """
    values = validate_r0a_measurements(measurements)
    validate_r0b_measurement(r0b, values)
    _validate_targets(target_counts)
    _need(r0b.workload.target == target_counts[-1], "R0B_TARGET_IDENTITY_MISMATCH")
    postprocess = project_postprocess(r0b)
    projections = []
    for counts in target_counts:
        n = counts.n
        archive = project_archive(n, values, counts)
        for value in values:
            execution = project_execution(n, value, counts)
            memory = project_memory(value, r0b)
            launcher = execution + postprocess
            reasons = list(_cap_reasons(value))
            if launcher > identity.MAX_ACTUAL_E2_LAUNCHER_WALL_SECONDS * _NS_PER_SECOND:
                reasons.append("LAUNCHER_CEILING")
            if archive > identity.MAX_ARCHIVE_BYTES:
                reasons.append("ARCHIVE_CEILING")
            if memory > identity.MAX_COMBINED_MEMORY_BYTES:
                reasons.append("MEMORY_CEILING")
            projections.append(AdmissionProjection(n, value.concurrency, execution, postprocess,
                launcher, archive, memory, value.primary_pairs_per_hour, tuple(reasons)))
    projections = tuple(projections)
    admitted = tuple(p for p in projections if p.admitted)
    if not admitted:
        return AdmissionDecision(AdmissionState.ACTUAL_E2_NOT_READY, projections, None,
                                 target_counts, r0b.workload.selection.counts)
    selected = max(admitted, key=lambda p: (p.n, p.primary_pairs_per_hour, -p.concurrency))
    value = next(v for v in values if v.concurrency == selected.concurrency)
    counts = next(v for v in target_counts if v.n == selected.n)
    return AdmissionDecision(AdmissionState.CANDIDATE_PROPOSED, projections,
        _proposal(value, r0b, selected, counts), target_counts, r0b.workload.selection.counts)


@dataclass(frozen=True, slots=True)
class ReviewSourceBinding:
    baseline_head: str
    protocol: records.ProtocolIdentity
    committed: tuple
    candidates: tuple
    status: str
    provenance: AmendmentProvenance = AmendmentProvenance()


def _source_identity(path, blob, data):
    return records.SourceBlobIdentity(path, blob, sha256(data).hexdigest(), len(data))


def capture_review_sources():
    """Read-only exact amendment review capture at the live descendant HEAD.

    Preserve accepted I7 qualification hygiene: this review-only dirty whitelist
    never authorizes a dirty real R0 launch or weakens qualification.capture_sources.
    """
    head = _git("rev-parse", "HEAD").strip().decode("ascii")
    origin = _git("rev-parse", "origin/main").strip().decode("ascii")
    branch = _git("branch", "--show-current").strip().decode("ascii")
    _need(branch == "main", "MAIN_BRANCH_REQUIRED")
    _git("merge-base", "--is-ancestor", I8_BASELINE, head)
    status = _git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8")
    allowed = {" M " + path for path in AMENDMENT_REVIEW_PATHS}
    lines = status.splitlines()
    _need(len(lines) == len(set(lines)) and set(lines) <= allowed,
          "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE")
    paths = tuple(sorted(set(qualification._PROTECTED + qualification._E2
        + tuple("tests/test_" + path.split("/")[-1] for path in qualification._E2)
        + AMENDMENT_REVIEW_PATHS + (AMENDMENT_PATH,
        "benchmark_board.py", identity.PROTOCOL_PATH, "scripts/run_source_unittest_isolated.py"))))
    refs = tuple(head + ":" + path for path in paths)
    refs += tuple(identity.E1_CORE_BASELINE + ":" + path for path in qualification._PROTECTED)
    refs += (identity.FREEZE_COMMIT + ":" + identity.PROTOCOL_PATH,)
    blobs = _blobs(refs)
    current = dict(zip(paths, blobs[:len(paths)]))
    for i, path in enumerate(qualification._PROTECTED):
        _need(current[path] == blobs[len(paths) + i], "E1_CORE_IDENTITY_DRIFT")
    frozen = blobs[-1]
    _need(current[identity.PROTOCOL_PATH] == frozen and frozen[0] == identity.PROTOCOL_BLOB_ID,
          "FROZEN_PROTOCOL_IDENTITY_DRIFT")
    identity.validate_protocol_bytes(frozen[1])
    amendment = (_ROOT / AMENDMENT_PATH).read_bytes()
    _need(len(amendment) == AMENDMENT_BYTE_LENGTH and sha256(amendment).hexdigest()
          == AMENDMENT_SHA256 and current[AMENDMENT_PATH][1] == amendment,
          "FROZEN_AMENDMENT_IDENTITY_DRIFT")
    candidates = tuple((path, (_ROOT / path).read_bytes()) for path in sorted(AMENDMENT_REVIEW_PATHS))
    # Do not rely only on porcelain: also detect accepted working-source drift
    # hidden by index flags. CRLF conversion is not a source-content change.
    for path in paths:
        if path not in AMENDMENT_REVIEW_PATHS:
            _need((_ROOT / path).read_bytes().replace(b"\r\n", b"\n")
                  == current[path][1].replace(b"\r\n", b"\n"), "ACCEPTED_WORKING_SOURCE_DRIFT")
    _need(_git("rev-parse", "HEAD").strip().decode("ascii") == head
          and _git("rev-parse", "origin/main").strip().decode("ascii") == origin
          and _git("branch", "--show-current").strip().decode("ascii") == branch
          and _git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8") == status
          and (_ROOT / AMENDMENT_PATH).read_bytes() == amendment
          and all((_ROOT / path).read_bytes() == data for path, data in candidates),
          "SOURCE_CHANGED_DURING_CAPTURE")
    return ReviewSourceBinding(head, records.ProtocolIdentity(identity.PROTOCOL_PATH,
        identity.PROTOCOL_SHA256, identity.PROTOCOL_BLOB_ID, identity.FREEZE_COMMIT),
        tuple(_source_identity(path, *current[path]) for path in paths),
        tuple(_source_identity(path, sha1(b"blob " + str(len(data)).encode("ascii")
              + b"\0" + data).hexdigest(), data) for path, data in candidates), status)
