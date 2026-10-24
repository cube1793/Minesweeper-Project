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
I8_PATHS = ("experiments/program_k_e2_readiness.py", "tests/test_program_k_e2_readiness.py")
I7_FIXTURE_PATH = "tests/test_program_k_e2_qualification.py"
REVIEW_PATHS = I8_PATHS + (I7_FIXTURE_PATH,)
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

    def __post_init__(self):
        _seed(self.protocol_seed)
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
    """One separately accounted P/K/O/D 64-unit component, not I6 receipt time.

    Oracle-B units include each scheduled applicability check. A unit with no
    applicable private comparison still has a completed operational path/record.
    Durable bytes include attributable persistence/progress/cleanup overhead;
    each archived byte belongs to exactly one component.
    """

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
    oracle_b: ComponentMeasurement
    determinism: ComponentMeasurement
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
        for component in _components(self):
            _record(component, ComponentMeasurement)
        _need(type(self.wall_accounting) is WallAccounting, "WALL_ACCOUNTING_REQUIRED")
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

    @property
    def primary_pairs_per_hour(self):
        _record(self, R0AConcurrencyMeasurement)
        return Fraction(identity.R0_A_BOARD_COUNT * 3600 * _NS_PER_SECOND, self.primary.wall_ns)


def _components(measurement):
    return (measurement.primary, measurement.k_control, measurement.oracle_b, measurement.determinism)


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
    ordered = tuple(sorted(measurements, key=lambda v: v.concurrency))
    _need(tuple(v.concurrency for v in ordered) == identity.R0_A_CONCURRENCY_CANDIDATES,
          "R0A_CONCURRENCY_COVERAGE")
    _need(all(v.plan == ordered[0].plan for v in ordered), "R0A_IDENTITY_MISMATCH")
    return ordered


@dataclass(frozen=True, slots=True)
class ComponentSizes:
    primary: int
    k_control: int
    oracle_b: int
    determinism: int

    def __post_init__(self):
        for value in _components(self):
            _integer(value, 1)


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

    @property
    def unit_counts(self):
        return (identity.CANDIDATE_MAX, identity.KCONTROL_CAP,
                identity.ORACLE_B_CAP, identity.DETERMINISM_CAP)


def derive_r0b_sizing_plan(measurements):
    values = validate_r0a_measurements(measurements)
    maxima = tuple(max(_components(v)[i].max_unit_bytes for v in values) for i in range(4))
    sizes = ComponentSizes(*(ceil_fraction(identity.ARCHIVE_BYTES_SAFETY_FACTOR * v) for v in maxima))
    return R0BSizingPlan(values[0].plan.protocol_seed, sizes)


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
    return value


def validate_r0b_measurement(value, measurements):
    _complete_r0b(value)
    sizing = derive_r0b_sizing_plan(measurements)
    _need(value.protocol_seed == sizing.protocol_seed, "R0B_PROTOCOL_IDENTITY_MISMATCH")
    _need(all(actual >= needed for actual, needed in zip(_components(value.unit_bytes),
              _components(sizing.unit_bytes))), "R0B_PAYLOAD_UNDERSIZED")
    _need(value.archive_bytes >= sum(n * size for n, size in
              zip(sizing.unit_counts, _components(value.unit_bytes))), "R0B_ARCHIVE_ACCOUNTING")
    _need(value.archive_bytes >= max(p.output_bytes for p in value.phases), "R0B_OUTPUT_ACCOUNTING")
    return value


def _scaled(n, values):
    _constants()
    _integer(n, 1)
    _need(n <= identity.CANDIDATE_MAX, "PROJECTION_N_DOMAIN")
    counts = (n, min(n, identity.KCONTROL_CAP), min(n, identity.ORACLE_B_CAP),
              min(n, identity.DETERMINISM_CAP))
    return sum((Fraction(value * count, identity.R0_A_BOARD_COUNT)
                for value, count in zip(values, counts)), Fraction())


def project_execution(n, measurement):
    _record(measurement, R0AConcurrencyMeasurement)
    return identity.EXECUTION_WALL_SAFETY_FACTOR * _scaled(n,
        tuple(v.wall_ns for v in _components(measurement)))


def project_postprocess(measurement):
    _complete_r0b(measurement)
    return identity.POSTPROCESS_WALL_SAFETY_FACTOR * measurement.complete_wall_ns


def project_archive(n, measurements):
    """Concurrency-independent §21.6 projection.

    Conservative implementation convention: use the componentwise largest
    durable totals across c1/c2/c4. This prevents a concurrency-dependent archive
    estimate when serialization/progress overhead differs between rehearsals.
    """
    values = validate_r0a_measurements(measurements)
    maxima = tuple(max(_components(v)[i].durable_bytes for v in values) for i in range(4))
    return identity.ARCHIVE_BYTES_SAFETY_FACTOR * _scaled(n, maxima) + identity.FIXED_REPORT_RECEIPT_ALLOWANCE


def project_memory(measurement):
    _record(measurement, R0AConcurrencyMeasurement)
    return identity.MEMORY_SAFETY_FACTOR * measurement.max_combined_memory_bytes


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
    if sum(v.durable_bytes for v in _components(value)) > envelope.archive_cap_bytes:
        reasons.append("TESTED_ARCHIVE_CAP")
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

    def __post_init__(self):
        _integer(self.n, 1)
        _record(self.envelope, operational.OperatingEnvelope)
        _record(self.projection, AdmissionProjection)
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

    def __post_init__(self):
        _constants()
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
            _need(bool(admitted) and self.candidate.projection == max(admitted,
                  key=lambda p: (p.n, p.primary_pairs_per_hour, -p.concurrency)),
                  "SELECTION_PRIORITY")


def _proposal(value, r0b, projection):
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
        coordinator_memory_cap_bytes=ceil_fraction(identity.MEMORY_SAFETY_FACTOR * value.max_coordinator_memory_bytes),
        memory_cap_bytes=ceil_fraction(projection.memory_bytes),
        archive_cap_bytes=ceil_fraction(projection.archive_bytes),
        aggregation_wall_ms=phases[0], validation_wall_ms=phases[1], publication_wall_ms=phases[2],
        readback_wall_ms=phases[3], report_wall_ms=phases[4])
    return CandidateEnvelopeProposal(projection.n, envelope, projection)


def select_operating_candidate(measurements, r0b):
    """Pure complete-facts admission; no measured facts are acquired here.

    Malformed/incomplete facts raise ReadinessError (or the reused I6 envelope
    validator's ValueError). Complete but inadmissible configurations produce a
    NOT_READY decision. Neither path is a research verdict.
    """
    values = validate_r0a_measurements(measurements)
    validate_r0b_measurement(r0b, values)
    postprocess = project_postprocess(r0b)
    projections = []
    for n in identity.N_LADDER:
        archive = project_archive(n, values)
        for value in values:
            execution = project_execution(n, value)
            memory = project_memory(value)
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
        return AdmissionDecision(AdmissionState.ACTUAL_E2_NOT_READY, projections, None)
    selected = max(admitted, key=lambda p: (p.n, p.primary_pairs_per_hour, -p.concurrency))
    value = next(v for v in values if v.concurrency == selected.concurrency)
    return AdmissionDecision(AdmissionState.CANDIDATE_PROPOSED, projections, _proposal(value, r0b, selected))


@dataclass(frozen=True, slots=True)
class ReviewSourceBinding:
    baseline_head: str
    protocol: records.ProtocolIdentity
    committed: tuple
    candidates: tuple
    status: str


def _source_identity(path, blob, data):
    return records.SourceBlobIdentity(path, blob, sha256(data).hexdigest(), len(data))


def capture_review_sources():
    """Authenticate this exact uncommitted I8 review without changing Git/I7.

    Committed continuity uses Git blob bytes; candidate identities hash the exact
    working bytes (including CRLF if present). Only the two new untracked files
    and the optional unstaged I7 fixture correction are permitted. This guard is
    deliberately specific to the accepted I7 baseline, not a future R0 launcher.
    """
    head = _git("rev-parse", "HEAD").strip().decode("ascii")
    origin = _git("rev-parse", "origin/main").strip().decode("ascii")
    branch = _git("branch", "--show-current").strip().decode("ascii")
    _need(head == origin == I7_BASELINE and branch == "main", "ACCEPTED_I7_BASELINE_REQUIRED")
    status = _git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8")
    allowed = {"?? " + path for path in I8_PATHS} | {" M " + I7_FIXTURE_PATH}
    lines = status.splitlines()
    _need(len(lines) == len(set(lines)) and set(lines) <= allowed
          and {"?? " + path for path in I8_PATHS} <= set(lines),
          "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE")
    paths = tuple(sorted(set(qualification._PROTECTED + qualification._E2
        + tuple("tests/test_" + path.split("/")[-1] for path in qualification._E2)
        + ("benchmark_board.py", identity.PROTOCOL_PATH, "scripts/run_source_unittest_isolated.py"))))
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
    candidates = tuple((path, (_ROOT / path).read_bytes()) for path in sorted(REVIEW_PATHS))
    # Do not rely only on porcelain: also detect accepted working-source drift
    # hidden by index flags. CRLF conversion is not a source-content change.
    for path in paths:
        if path != I7_FIXTURE_PATH:
            _need((_ROOT / path).read_bytes().replace(b"\r\n", b"\n")
                  == current[path][1].replace(b"\r\n", b"\n"), "ACCEPTED_WORKING_SOURCE_DRIFT")
    _need(_git("rev-parse", "HEAD").strip().decode("ascii") == head
          and _git("rev-parse", "origin/main").strip().decode("ascii") == origin
          and _git("branch", "--show-current").strip().decode("ascii") == branch
          and _git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8") == status
          and all((_ROOT / path).read_bytes() == data for path, data in candidates),
          "SOURCE_CHANGED_DURING_CAPTURE")
    return ReviewSourceBinding(head, records.ProtocolIdentity(identity.PROTOCOL_PATH,
        identity.PROTOCOL_SHA256, identity.PROTOCOL_BLOB_ID, identity.FREEZE_COMMIT),
        tuple(_source_identity(path, *current[path]) for path in paths),
        tuple(_source_identity(path, sha1(b"blob " + str(len(data)).encode("ascii")
              + b"\0" + data).hexdigest(), data) for path, data in candidates), status)
