"""I3 pure aggregate analysis of supplied compact scalar board-pair rows.

No execution, selection, capture or storage lives here. Model C and comparable
compute remain separate. Diagnostics never feed gate classification. A caller
supplies other gate judgments; raw P3/outcome differences are not research FAIL.

Strict WW rows require Model-C totals. The separate classify_g8 missing-data
branch represents upstream incomplete evidence without inventing an invalid row.
G5 evidence completeness is explicit because I1 summaries contain counts only.
"""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records


PRACTICAL_MARGIN_US_PER_WW = identity.PRACTICAL_MARGIN_US_PER_WW
DIAGNOSTIC_WORST_N = 20
_GATE_NAMES = tuple(f"G{i}" for i in range(1, 11))
_MASK = identity.UINT64_MAX


class AnalysisError(ValueError):
    """Supplied analysis values violate the exact I3 contract."""


def _need(condition, message):
    if not condition:
        raise AnalysisError(message)


def _integer(value, minimum=None, maximum=None):
    _need(type(value) is int and (minimum is None or value >= minimum)
          and (maximum is None or value <= maximum), "Expected exact integer in bounds.")


def _boolean(value):
    _need(type(value) is bool, "Expected exact bool.")


def _enum(value, cls):
    _need(type(value) is cls, "Expected exact analysis enum.")


def _text(value):
    _need(type(value) is str and all(not 0xD800 <= ord(c) <= 0xDFFF for c in value),
          "Expected exact Unicode text without surrogates.")


def _owned(value, cls):
    _need(type(value) is cls, "Unexpected record type or subclass.")
    cls.__post_init__(value)


def _fraction(value):
    _need(type(value) is Fraction, "Expected exact Fraction.")


class GateStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    DEFER = "DEFER"
    INCOMPLETE = "INCOMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OverallVerdict(Enum):
    IMPLEMENTATION_IDENTITY_FAIL = "IMPLEMENTATION_IDENTITY_FAIL"
    INCOMPLETE = "INCOMPLETE"
    RESEARCH_FAIL = "RESEARCH_FAIL"
    RESEARCH_DEFER = "RESEARCH_DEFER"
    RESEARCH_PASS = "RESEARCH_PASS"


class G9PathologyDisposition(Enum):
    NONE = "NONE"
    UNRESOLVED_PATHOLOGY = "UNRESOLVED_PATHOLOGY"
    INHERENT_PATHOLOGY = "INHERENT_PATHOLOGY"


class G5Cause(Enum):
    NONE = "NONE"
    NO_EXPOSURE = "NO_EXPOSURE"
    MISSING_REQUIRED_DATA = "MISSING_REQUIRED_DATA"
    BOOTSTRAP_ZERO_EXPOSED_WW = "BOOTSTRAP_ZERO_EXPOSED_WW"
    ZERO_OVERLAP = "ZERO_OVERLAP"


class G8Cause(Enum):
    NONE = "NONE"
    OBSERVED_NO_WW = "OBSERVED_NO_WW"
    BOOTSTRAP_ZERO_WW = "BOOTSTRAP_ZERO_WW"
    MARGIN_OVERLAP = "MARGIN_OVERLAP"
    MISSING_REQUIRED_DATA = "MISSING_REQUIRED_DATA"


class G9Cause(Enum):
    NONE = "NONE"
    MISSING_REQUIRED_DATA = "MISSING_REQUIRED_DATA"
    INHERENT_PATHOLOGY = "INHERENT_PATHOLOGY"
    UNRESOLVED_PATHOLOGY = "UNRESOLVED_PATHOLOGY"
    OBSERVED_NO_WW = "OBSERVED_NO_WW"
    BOOTSTRAP_ZERO_WW = "BOOTSTRAP_ZERO_WW"
    NONPOSITIVE_LOWER_BOUND = "NONPOSITIVE_LOWER_BOUND"


@dataclass(frozen=True, slots=True)
class BoardAnalysisRow:
    position: int
    pair: records.PairComparisonRecord
    control_model_us: int | None
    kp0_model_us: int | None
    control_compute_ns: int | None
    kp0_compute_ns: int | None

    def __post_init__(self):
        _integer(self.position, 0)
        _need(type(self.pair) is records.PairComparisonRecord, "Expected exact PairComparisonRecord.")
        try:
            records.PairComparisonRecord.__post_init__(self.pair)
        except records.RecordError as exc:
            raise AnalysisError(str(exc)) from exc
        terminal = (records.Outcome.WIN, records.Outcome.LOSS)
        fully_terminal = self.pair.control_outcome in terminal and self.pair.kp0_outcome in terminal
        for value in (self.control_model_us, self.kp0_model_us):
            if value is not None:
                _integer(value, 1)
            else:
                _need(not fully_terminal, "Terminal pairs require both positive Model-C totals.")
        for value in (self.control_compute_ns, self.kp0_compute_ns):
            if value is not None:
                _integer(value, 0)
        if _is_ww(self):
            _need(self.pair.ww_delta_us == self.kp0_model_us - self.control_model_us,
                  "WW delta must equal K-P0 minus CONTROL Model C.")


def _is_ww(row):
    return row.pair.control_outcome is records.Outcome.WIN and row.pair.kp0_outcome is records.Outcome.WIN


@dataclass(frozen=True, slots=True)
class OutcomeCounts:
    ww: int
    wl: int
    lw: int
    ll: int
    error: int
    incomplete: int

    def __post_init__(self):
        for value in (self.ww, self.wl, self.lw, self.ll, self.error, self.incomplete):
            _integer(value, 0)


@dataclass(frozen=True, slots=True)
class PrimarySummary:
    n_w: int
    s_c: int
    s_k: int
    total_delta: int
    ratio: Fraction | None
    reduction: Fraction | None
    mean_saving_us: Fraction | None

    def __post_init__(self):
        for value in (self.n_w, self.s_c, self.s_k):
            _integer(value, 0)
        _integer(self.total_delta)
        _need(self.total_delta == self.s_k - self.s_c, "Primary delta mismatch.")
        if self.n_w == 0:
            _need(self.s_c == self.s_k == 0 and self.ratio is None
                  and self.reduction is None and self.mean_saving_us is None, "Invalid empty primary.")
        else:
            _need(self.s_c >= self.n_w and self.s_k >= self.n_w, "Positive WW totals required.")
            for value in (self.ratio, self.reduction, self.mean_saving_us):
                _fraction(value)
            _need(self.ratio == Fraction(self.s_k, self.s_c)
                  and self.reduction == 1 - self.ratio
                  and self.mean_saving_us == Fraction(self.s_c - self.s_k, self.n_w),
                  "Inconsistent exact primary arithmetic.")


@dataclass(frozen=True, slots=True)
class ScalarDistribution:
    """Diagnostic scalars; compute distributions are WW per-board totals."""

    count: int
    minimum: int | None
    maximum: int | None
    mean: Fraction | None
    median: int | Fraction | None
    p90: int | None
    p95: int | None
    p99: int | None

    def __post_init__(self):
        _integer(self.count, 0)
        values = (self.minimum, self.maximum, self.mean, self.median, self.p90, self.p95, self.p99)
        if self.count == 0:
            _need(all(v is None for v in values), "Empty distributions must be explicit None.")
            return
        for value in (self.minimum, self.maximum, self.p90, self.p95, self.p99):
            _integer(value)
        _fraction(self.mean)
        _need(type(self.median) is (int if self.count % 2 else Fraction), "Median type mismatch.")
        _need(self.minimum <= self.median <= self.p90 <= self.p95 <= self.p99 <= self.maximum
              and self.minimum <= self.mean <= self.maximum, "Distribution order mismatch.")


@dataclass(frozen=True, slots=True)
class WorstBoard:
    position: int
    game_index: int
    fingerprint: str
    delta_us: int
    diagnosis: str

    def __post_init__(self):
        _integer(self.position, 0)
        _integer(self.game_index, 0, _MASK)
        _integer(self.delta_us)
        _text(self.fingerprint)
        _text(self.diagnosis)


@dataclass(frozen=True, slots=True)
class DeltaDiagnostics:
    distribution: ScalarDistribution
    faster: int
    slower: int
    ties: int
    maximum_slowdown: int | None
    worst: tuple[WorstBoard, ...]

    def __post_init__(self):
        _owned(self.distribution, ScalarDistribution)
        for value in (self.faster, self.slower, self.ties):
            _integer(value, 0)
        _need(self.faster + self.slower + self.ties == self.distribution.count, "Diagnostic count mismatch.")
        if self.slower:
            _integer(self.maximum_slowdown, 1)
            _need(self.maximum_slowdown == self.distribution.maximum, "Maximum slowdown mismatch.")
        else:
            _need(self.maximum_slowdown is None, "No positive slowdown must be None.")
        _need(type(self.worst) is tuple and len(self.worst) == min(DIAGNOSTIC_WORST_N, self.distribution.count),
              "Invalid worst-N ownership/count.")
        for item in self.worst:
            _owned(item, WorstBoard)
        _need(self.worst == tuple(sorted(self.worst, key=_worst_key)), "Worst-N order mismatch.")


def _worst_key(item):
    return (-item.delta_us, item.game_index, item.position)


@dataclass(frozen=True, slots=True)
class BootstrapMetric:
    interval: tuple[Fraction, Fraction] | None
    defined_count: int
    undefined_count: int
    zero_eligible_count: int
    missing_data_count: int

    def __post_init__(self):
        for value in (self.defined_count, self.undefined_count, self.zero_eligible_count, self.missing_data_count):
            _integer(value, 0, identity.BOOTSTRAP_REPLICATES)
        _need(self.defined_count + self.undefined_count == identity.BOOTSTRAP_REPLICATES
              and self.zero_eligible_count + self.missing_data_count == self.undefined_count,
              "Bootstrap accounting mismatch.")
        if self.undefined_count:
            _need(self.interval is None, "Undefined replicates prohibit a shortened interval.")
        else:
            _need(type(self.interval) is tuple and len(self.interval) == 2, "Expected exact interval tuple.")
            for value in self.interval:
                _fraction(value)
            _need(self.interval[0] <= self.interval[1], "Interval order mismatch.")


@dataclass(frozen=True, slots=True)
class BootstrapSummary:
    replicates: int
    accepted_draws: int
    rejected_draws: int
    seed_hex: str
    g5: BootstrapMetric
    g8: BootstrapMetric
    g9: BootstrapMetric

    def __post_init__(self):
        _integer(self.replicates, identity.BOOTSTRAP_REPLICATES, identity.BOOTSTRAP_REPLICATES)
        _integer(self.accepted_draws, self.replicates)
        _integer(self.rejected_draws, 0)
        _need(type(self.seed_hex) is str and len(self.seed_hex) == 64
              and all(c in "0123456789abcdef" for c in self.seed_hex), "Invalid boot-seed hex.")
        for value in (self.g5, self.g8, self.g9):
            _owned(value, BootstrapMetric)


@dataclass(frozen=True, slots=True)
class G5Result:
    exposure_count: int
    exposure_fraction: Fraction
    diagnostic_setup_chord_flags: int
    qualifying_fallback_flags: int
    qualifying_flag_to_open_setup_flags: int
    exposed_ww_count: int
    mean_saving_us: Fraction | None
    diagnostics: DeltaDiagnostics
    evidence_complete: bool
    status: GateStatus
    cause: G5Cause
    bootstrap: BootstrapMetric

    def __post_init__(self):
        for value in (self.exposure_count, self.diagnostic_setup_chord_flags, self.qualifying_fallback_flags,
                      self.qualifying_flag_to_open_setup_flags, self.exposed_ww_count):
            _integer(value, 0)
        _fraction(self.exposure_fraction)
        _need(0 <= self.exposure_fraction <= 1 and self.exposed_ww_count <= self.exposure_count,
              "Invalid exposure counts/fraction.")
        _boolean(self.evidence_complete)
        _enum(self.status, GateStatus)
        _enum(self.cause, G5Cause)
        valid_no_exposure = self.exposure_count == 0 and self.evidence_complete
        _need((self.status is GateStatus.NOT_APPLICABLE) == valid_no_exposure
              and (self.cause is G5Cause.NO_EXPOSURE) == valid_no_exposure,
              "G5 N/A requires complete evidence establishing zero exposure.")
        _owned(self.diagnostics, DeltaDiagnostics)
        _owned(self.bootstrap, BootstrapMetric)
        _need(self.diagnostics.distribution.count == self.exposed_ww_count, "Exposed-WW count mismatch.")
        if self.exposed_ww_count:
            _fraction(self.mean_saving_us)
            _need(self.mean_saving_us == -self.diagnostics.distribution.mean, "Exposed saving sign mismatch.")
        else:
            _need(self.mean_saving_us is None, "Empty exposed saving must be None.")


@dataclass(frozen=True, slots=True)
class G8Result:
    status: GateStatus
    cause: G8Cause
    bootstrap: BootstrapMetric
    margin_us: int

    def __post_init__(self):
        _enum(self.status, GateStatus)
        _enum(self.cause, G8Cause)
        _need(self.status is not GateStatus.NOT_APPLICABLE, "G8 cannot be N/A.")
        _owned(self.bootstrap, BootstrapMetric)
        _integer(self.margin_us, PRACTICAL_MARGIN_US_PER_WW, PRACTICAL_MARGIN_US_PER_WW)


@dataclass(frozen=True, slots=True)
class G9Result:
    status: GateStatus
    cause: G9Cause
    concurrency: int
    pathology: G9PathologyDisposition
    observed_mean_net_headroom_ns: Fraction | None
    missing_compute_rows: int
    control_compute: ScalarDistribution
    kp0_compute: ScalarDistribution
    added_compute: ScalarDistribution
    bootstrap: BootstrapMetric

    def __post_init__(self):
        _enum(self.status, GateStatus)
        _enum(self.cause, G9Cause)
        _need(self.status is not GateStatus.NOT_APPLICABLE, "G9 cannot be N/A.")
        _enum(self.pathology, G9PathologyDisposition)
        _integer(self.concurrency, 1)
        _integer(self.missing_compute_rows, 0)
        if self.observed_mean_net_headroom_ns is not None:
            _fraction(self.observed_mean_net_headroom_ns)
            _need(self.missing_compute_rows == 0, "Incomplete compute cannot supply a complete WW mean.")
        for value in (self.control_compute, self.kp0_compute, self.added_compute):
            _owned(value, ScalarDistribution)
        _owned(self.bootstrap, BootstrapMetric)


def _validate_gates(gates):
    _need(type(gates) is dict and all(type(k) is str for k in gates)
          and set(gates) == set(_GATE_NAMES), "Expected exact complete G1..G10 dict.")
    for name, status in gates.items():
        _enum(status, GateStatus)
        _need(status is not GateStatus.NOT_APPLICABLE or name == "G5", "N/A is valid only for G5.")


def classify_overall(gates, *, implementation_identity_fail):
    """N/A for G5 asserts upstream zero exposure; analyze verifies that claim."""
    _validate_gates(gates)
    _boolean(implementation_identity_fail)
    if implementation_identity_fail:
        return OverallVerdict.IMPLEMENTATION_IDENTITY_FAIL
    for status, verdict in ((GateStatus.INCOMPLETE, OverallVerdict.INCOMPLETE),
                            (GateStatus.FAIL, OverallVerdict.RESEARCH_FAIL),
                            (GateStatus.DEFER, OverallVerdict.RESEARCH_DEFER)):
        if status in gates.values():
            return verdict
    return OverallVerdict.RESEARCH_PASS


def e3_trigger(gates, *, implementation_identity_fail, g8_cause):
    """Compute a prospective trigger only; this never authorizes E3 execution."""
    _validate_gates(gates)
    _boolean(implementation_identity_fail)
    _enum(g8_cause, G8Cause)
    return (not implementation_identity_fail and gates["G8"] is GateStatus.DEFER
            and g8_cause is G8Cause.MARGIN_OVERLAP
            and gates["G5"] in (GateStatus.PASS, GateStatus.NOT_APPLICABLE)
            and all(gates[name] is GateStatus.PASS for name in _GATE_NAMES if name not in ("G5", "G8")))


@dataclass(frozen=True, slots=True)
class OverallAssessment:
    gates: tuple[tuple[str, GateStatus], ...]
    implementation_identity_fail: bool
    verdict: OverallVerdict
    e3_trigger: bool

    def __post_init__(self):
        _need(type(self.gates) is tuple and len(self.gates) == 10, "Expected owned gate tuple.")
        for index, item in enumerate(self.gates):
            _need(type(item) is tuple and len(item) == 2 and type(item[0]) is str
                  and item[0] == _GATE_NAMES[index], "Invalid gate tuple/order.")
        _validate_gates(dict(self.gates))
        _boolean(self.implementation_identity_fail)
        _enum(self.verdict, OverallVerdict)
        _boolean(self.e3_trigger)
        statuses = tuple(status for _, status in self.gates)
        incomplete = GateStatus.INCOMPLETE in statuses
        failed = GateStatus.FAIL in statuses
        deferred = GateStatus.DEFER in statuses
        # Validate the supplied assertion, without invoking a classifier at render time.
        valid = {
            OverallVerdict.IMPLEMENTATION_IDENTITY_FAIL: self.implementation_identity_fail,
            OverallVerdict.INCOMPLETE: not self.implementation_identity_fail and incomplete,
            OverallVerdict.RESEARCH_FAIL: not self.implementation_identity_fail and not incomplete and failed,
            OverallVerdict.RESEARCH_DEFER: not self.implementation_identity_fail and not incomplete and not failed and deferred,
            OverallVerdict.RESEARCH_PASS: not self.implementation_identity_fail and not incomplete and not failed and not deferred,
        }
        _need(valid[self.verdict], "Overall verdict contradicts gate precedence.")
        if self.e3_trigger:
            gates = dict(self.gates)
            _need(not self.implementation_identity_fail and gates["G8"] is GateStatus.DEFER
                  and gates["G5"] in (GateStatus.PASS, GateStatus.NOT_APPLICABLE)
                  and all(gates[name] is GateStatus.PASS for name in _GATE_NAMES if name not in ("G5", "G8")),
                  "E3 assertion contradicts supplied gate qualification.")


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    n: int
    concurrency: int
    outcomes: OutcomeCounts
    primary: PrimarySummary
    ww_diagnostics: DeltaDiagnostics
    bootstrap: BootstrapSummary
    g5: G5Result
    g8: G8Result
    g9: G9Result
    overall: OverallAssessment | None
    context: tuple[str, ...]

    def __post_init__(self):
        """Validate scalars and gate claims; never rerun row analysis or bootstrap."""
        _integer(self.n, 1)
        _integer(self.concurrency, 1)
        for value, cls in ((self.outcomes, OutcomeCounts), (self.primary, PrimarySummary),
                           (self.ww_diagnostics, DeltaDiagnostics), (self.bootstrap, BootstrapSummary),
                           (self.g5, G5Result), (self.g8, G8Result), (self.g9, G9Result)):
            _owned(value, cls)
        counts = self.outcomes
        _need(sum((counts.ww, counts.wl, counts.lw, counts.ll, counts.error, counts.incomplete)) == self.n,
              "Outcome counts must partition N.")
        _need(counts.ww == self.primary.n_w == self.ww_diagnostics.distribution.count,
              "WW count mismatch.")
        _need(self.bootstrap.accepted_draws == self.n * self.bootstrap.replicates,
              "Bootstrap draw count mismatch.")
        _need(self.g5.exposure_fraction == Fraction(self.g5.exposure_count, self.n)
              and self.g5.exposure_count <= self.n, "G5 population mismatch.")
        _need(self.g9.concurrency == self.concurrency
              and self.g9.missing_compute_rows <= counts.ww, "G9 input mismatch.")
        _need(self.g5.bootstrap == self.bootstrap.g5 and self.g8.bootstrap == self.bootstrap.g8
              and self.g9.bootstrap == self.bootstrap.g9, "Shared-bootstrap result mismatch.")
        _need((self.g5.status, self.g5.cause) == classify_g5(
            exposure_count=self.g5.exposure_count, evidence_complete=self.g5.evidence_complete,
            bootstrap=self.g5.bootstrap), "G5 status/cause contradict evidence or bootstrap.")
        # Integrated WW rows require complete Model-C totals. The standalone
        # classifier still supports missing evidence that cannot enter those rows.
        _need((self.g8.status, self.g8.cause) == classify_g8(
            observed_ww=self.primary.n_w, missing_required_data=False,
            bootstrap=self.g8.bootstrap), "G8 status/cause contradict WW count or bootstrap.")
        _need((self.g9.status, self.g9.cause) == classify_g9(
            observed_ww=self.primary.n_w, missing_compute=self.g9.missing_compute_rows > 0,
            pathology=self.g9.pathology, bootstrap=self.g9.bootstrap),
            "G9 status/cause contradict compute availability, pathology or bootstrap.")
        n_w, missing = self.primary.n_w, self.g9.missing_compute_rows
        control, kp0, added = self.g9.control_compute, self.g9.kp0_compute, self.g9.added_compute
        _need(added.count == n_w - missing
              and added.count <= control.count <= n_w
              and added.count <= kp0.count <= n_w,
              "G9 comparable-compute distribution counts mismatch.")
        # With no missing rows these bounds force all three counts to equal n_w.
        # Partial arm distributions may cover different row sets, so their means
        # are comparable only in the complete-compute case.
        observed = self.g9.observed_mean_net_headroom_ns
        if n_w == 0 or missing > 0:
            _need(observed is None, "Empty/incomplete WW compute requires no observed G9 mean.")
        else:
            _fraction(observed)
            _need(added.mean == kp0.mean - control.mean,
                  "G9 complete-compute mean arithmetic mismatch.")
            _need(observed == self.primary.mean_saving_us * 1000 - added.mean,
                  "G9 observed net headroom contradicts compact summary arithmetic.")
        if self.overall is not None:
            _owned(self.overall, OverallAssessment)
            gates = dict(self.overall.gates)
            _need(gates["G5"] is self.g5.status and gates["G8"] is self.g8.status
                  and gates["G9"] is self.g9.status, "Overall gates disagree with analysis.")
            qualified = (not self.overall.implementation_identity_fail and self.g8.status is GateStatus.DEFER
                         and self.g8.cause is G8Cause.MARGIN_OVERLAP
                         and self.g5.status in (GateStatus.PASS, GateStatus.NOT_APPLICABLE)
                         and all(gates[name] is GateStatus.PASS for name in _GATE_NAMES if name not in ("G5", "G8")))
            _need(self.overall.e3_trigger == qualified, "E3 assertion contradicts exact G8 cause/qualification.")
        _need(type(self.context) is tuple, "Context must be an immutable tuple.")
        for value in self.context:
            _text(value)


def _distribution(values):
    """Signed integer nearest ranks; this is solely diagnostic presentation."""
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return ScalarDistribution(0, None, None, None, None, None, None, None)
    for value in ordered:
        _integer(value)
    median = ordered[n // 2] if n % 2 else Fraction(ordered[n // 2 - 1] + ordered[n // 2], 2)
    return ScalarDistribution(n, ordered[0], ordered[-1], Fraction(sum(ordered), n), median,
                              *(ordered[(p * n + 99) // 100 - 1] for p in (90, 95, 99)))


def _diagnostics(rows):
    values = tuple(row.pair.ww_delta_us for row in rows)
    worst = sorted(rows, key=lambda row: (-row.pair.ww_delta_us, row.pair.board.game_index, row.position))
    return DeltaDiagnostics(_distribution(values), sum(v < 0 for v in values), sum(v > 0 for v in values),
                            sum(v == 0 for v in values), max((v for v in values if v > 0), default=None),
                            tuple(WorstBoard(row.position, row.pair.board.game_index, row.pair.board.fingerprint,
                                             row.pair.ww_delta_us, row.pair.diagnosis)
                                  for row in worst[:DIAGNOSTIC_WORST_N]))


def bootstrap_seed(protocol_seed, corpus_digest):
    for value in (protocol_seed, corpus_digest):
        _need(type(value) is bytes and len(value) == 32, "Bootstrap inputs require exact 32-byte bytes.")
    return identity.sha256_bytes(identity.BOOT_LABEL + b"\0" + protocol_seed + b"\0" + corpus_digest)


def splitmix64_step(state):
    _integer(state, 0, _MASK)
    state = (state + 0x9E3779B97F4A7C15) & _MASK
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
    return state, z ^ (z >> 31)


def uniform_position(state, n):
    """Return continuing state, unbiased position and rejected raw-output count."""
    _integer(state, 0, _MASK)
    _integer(n, 1, 1 << 64)
    limit = ((1 << 64) // n) * n
    rejected = 0
    while True:
        state, output = splitmix64_step(state)
        if output < limit:
            return state, output % n, rejected
        rejected += 1


def _metric(means, zero_count, missing_count=0):
    undefined = zero_count + missing_count
    interval = None
    if not undefined:
        means.sort()
        interval = (means[identity.LOWER_RANK - 1], means[identity.UPPER_RANK - 1])
    return BootstrapMetric(interval, len(means), undefined, zero_count, missing_count)


def _shared_bootstrap(rows, protocol_seed, corpus_digest):
    """One PRNG state, one replicate loop, three scalar accumulators per draw.

    Projection is O(N) once. Only three O(10,000) scalar-mean lists survive
    replicate boundaries; there is no draw matrix or per-replicate row copy.
    """
    seed = bootstrap_seed(protocol_seed, corpus_digest)
    state = identity.uint64_be_decode(seed[:8])
    compact = tuple((True, row.pair.g5.is_exposed, row.control_model_us - row.kp0_model_us,
                     None if row.control_compute_ns is None or row.kp0_compute_ns is None
                     else (row.control_model_us - row.kp0_model_us) * 1000
                     - (row.kp0_compute_ns - row.control_compute_ns))
                    if _is_ww(row) else (False, row.pair.g5.is_exposed, 0, None)
                    for row in rows)
    n = len(compact)
    g8_means, g5_means, g9_means = [], [], []
    zero_ww = zero_exposed = missing_compute = rejected = 0
    for _ in range(identity.BOOTSTRAP_REPLICATES):
        ww_count = exposed_count = saving_sum = exposed_sum = net_sum = 0
        compute_missing = False
        for _ in range(n):
            state, position, rejected_here = uniform_position(state, n)
            rejected += rejected_here
            is_ww, exposed, saving, net = compact[position]
            if is_ww:
                ww_count += 1
                saving_sum += saving
                if exposed:
                    exposed_count += 1
                    exposed_sum += saving
                if net is None:
                    compute_missing = True
                else:
                    net_sum += net
        if ww_count:
            g8_means.append(Fraction(saving_sum, ww_count))
            if compute_missing:
                missing_compute += 1
            else:
                g9_means.append(Fraction(net_sum, ww_count))
        else:
            zero_ww += 1
        if exposed_count:
            g5_means.append(Fraction(exposed_sum, exposed_count))
        else:
            zero_exposed += 1
    return BootstrapSummary(identity.BOOTSTRAP_REPLICATES, n * identity.BOOTSTRAP_REPLICATES,
                            rejected, seed.hex(), _metric(g5_means, zero_exposed),
                            _metric(g8_means, zero_ww), _metric(g9_means, zero_ww, missing_compute))


def classify_g5(*, exposure_count, evidence_complete, bootstrap):
    _integer(exposure_count, 0)
    _boolean(evidence_complete)
    _owned(bootstrap, BootstrapMetric)
    if not evidence_complete:
        return GateStatus.INCOMPLETE, G5Cause.MISSING_REQUIRED_DATA
    if exposure_count == 0:
        return GateStatus.NOT_APPLICABLE, G5Cause.NO_EXPOSURE
    if bootstrap.missing_data_count:
        return GateStatus.INCOMPLETE, G5Cause.MISSING_REQUIRED_DATA
    if bootstrap.zero_eligible_count:
        return GateStatus.DEFER, G5Cause.BOOTSTRAP_ZERO_EXPOSED_WW
    lower, upper = bootstrap.interval
    if lower >= 0:
        return GateStatus.PASS, G5Cause.NONE
    if upper < 0:
        return GateStatus.FAIL, G5Cause.NONE
    return GateStatus.DEFER, G5Cause.ZERO_OVERLAP


def classify_g8(*, observed_ww, missing_required_data, bootstrap):
    _integer(observed_ww, 0)
    _boolean(missing_required_data)
    _owned(bootstrap, BootstrapMetric)
    if missing_required_data or bootstrap.missing_data_count:
        return GateStatus.INCOMPLETE, G8Cause.MISSING_REQUIRED_DATA
    if observed_ww == 0:
        return GateStatus.DEFER, G8Cause.OBSERVED_NO_WW
    if bootstrap.zero_eligible_count:
        return GateStatus.DEFER, G8Cause.BOOTSTRAP_ZERO_WW
    lower, upper = bootstrap.interval
    if lower > PRACTICAL_MARGIN_US_PER_WW:
        return GateStatus.PASS, G8Cause.NONE
    if upper < PRACTICAL_MARGIN_US_PER_WW:
        return GateStatus.FAIL, G8Cause.NONE
    return GateStatus.DEFER, G8Cause.MARGIN_OVERLAP


def classify_g9(*, observed_ww, missing_compute, pathology, bootstrap):
    _integer(observed_ww, 0)
    _boolean(missing_compute)
    _enum(pathology, G9PathologyDisposition)
    _owned(bootstrap, BootstrapMetric)
    if missing_compute or bootstrap.missing_data_count:
        return GateStatus.INCOMPLETE, G9Cause.MISSING_REQUIRED_DATA
    if pathology is G9PathologyDisposition.INHERENT_PATHOLOGY:
        return GateStatus.FAIL, G9Cause.INHERENT_PATHOLOGY
    if pathology is G9PathologyDisposition.UNRESOLVED_PATHOLOGY:
        return GateStatus.DEFER, G9Cause.UNRESOLVED_PATHOLOGY
    if observed_ww == 0:
        return GateStatus.DEFER, G9Cause.OBSERVED_NO_WW
    if bootstrap.zero_eligible_count:
        return GateStatus.DEFER, G9Cause.BOOTSTRAP_ZERO_WW
    if bootstrap.interval[0] > 0:
        return GateStatus.PASS, G9Cause.NONE
    return GateStatus.DEFER, G9Cause.NONPOSITIVE_LOWER_BOUND


def analyze_effectiveness(rows, *, protocol_seed, corpus_digest, concurrency,
                          pathology=G9PathologyDisposition.NONE, g5_evidence_complete=True,
                          gate_statuses=None, implementation_identity_fail=False, context=()):
    """Analyze supplied rows only. Other gates and evidence qualification are caller-owned.

    Compute distributions contain available WW per-board comparable-span totals;
    their counts expose missing values. A complete observed net mean is withheld
    if any WW compute is missing. No absent value is coerced to zero.
    """
    _need(type(rows) is tuple and len(rows) >= 1, "Expected nonempty exact row tuple.")
    _integer(concurrency, 1)
    _enum(pathology, G9PathologyDisposition)
    _boolean(g5_evidence_complete)
    _boolean(implementation_identity_fail)
    _need(type(context) is tuple, "Context must be an immutable tuple.")
    for value in context:
        _text(value)
    bootstrap_seed(protocol_seed, corpus_digest)  # reject invalid bytes before any work
    if gate_statuses is not None:
        _validate_gates(gate_statuses)
    else:
        _need(not implementation_identity_fail, "Identity-fail assessment requires all supplied gates.")
    indices = set()
    counts = dict.fromkeys(("WW", "WL", "LW", "LL", "ERROR", "INCOMPLETE"), 0)
    for offset, row in enumerate(rows):
        _owned(row, BoardAnalysisRow)
        _need(row.position == offset, "Rows must already be in exact zero-based position order.")
        index = row.pair.board.game_index
        _need(index not in indices, "Duplicate game_index.")
        indices.add(index)
        outcomes = (row.pair.control_outcome, row.pair.kp0_outcome)
        if records.Outcome.ERROR in outcomes:
            category = "ERROR"
        elif records.Outcome.INCOMPLETE in outcomes:
            category = "INCOMPLETE"
        else:
            category = "".join("W" if v is records.Outcome.WIN else "L" for v in outcomes)
        counts[category] += 1
    ww = tuple(row for row in rows if _is_ww(row))
    exposed_ww = tuple(row for row in ww if row.pair.g5.is_exposed)
    n_w = len(ww)
    s_c = sum(row.control_model_us for row in ww)
    s_k = sum(row.kp0_model_us for row in ww)
    ratio = Fraction(s_k, s_c) if n_w else None
    primary = PrimarySummary(n_w, s_c, s_k, s_k - s_c, ratio,
                             1 - ratio if n_w else None, Fraction(s_c - s_k, n_w) if n_w else None)
    boot = _shared_bootstrap(rows, protocol_seed, corpus_digest)
    exposure_count = sum(row.pair.g5.is_exposed for row in rows)
    g5_status, g5_cause = classify_g5(exposure_count=exposure_count,
                                    evidence_complete=g5_evidence_complete, bootstrap=boot.g5)
    g5 = G5Result(exposure_count, Fraction(exposure_count, len(rows)),
                  sum(row.pair.g5.diagnostic_setup_chord_flags for row in rows),
                  sum(row.pair.g5.qualifying_fallback_flags for row in rows),
                  sum(row.pair.g5.qualifying_flag_to_open_setup_flags for row in rows), len(exposed_ww),
                  Fraction(sum(row.control_model_us - row.kp0_model_us for row in exposed_ww), len(exposed_ww))
                  if exposed_ww else None, _diagnostics(exposed_ww), g5_evidence_complete,
                  g5_status, g5_cause, boot.g5)
    g8_status, g8_cause = classify_g8(observed_ww=n_w, missing_required_data=False, bootstrap=boot.g8)
    g8 = G8Result(g8_status, g8_cause, boot.g8, PRACTICAL_MARGIN_US_PER_WW)
    missing = sum(row.control_compute_ns is None or row.kp0_compute_ns is None for row in ww)
    added = tuple(row.kp0_compute_ns - row.control_compute_ns for row in ww
                  if row.control_compute_ns is not None and row.kp0_compute_ns is not None)
    g9_status, g9_cause = classify_g9(observed_ww=n_w, missing_compute=bool(missing),
                                    pathology=pathology, bootstrap=boot.g9)
    g9 = G9Result(g9_status, g9_cause, concurrency, pathology,
                  Fraction((s_c - s_k) * 1000 - sum(added), n_w) if n_w and not missing else None,
                  missing, _distribution(row.control_compute_ns for row in ww if row.control_compute_ns is not None),
                  _distribution(row.kp0_compute_ns for row in ww if row.kp0_compute_ns is not None),
                  _distribution(added), boot.g9)
    overall = None
    if gate_statuses is not None:
        _need(gate_statuses["G5"] is g5.status and gate_statuses["G8"] is g8.status
              and gate_statuses["G9"] is g9.status, "Supplied G5/G8/G9 disagree with computed gates.")
        overall = OverallAssessment(tuple((name, gate_statuses[name]) for name in _GATE_NAMES),
                                    implementation_identity_fail,
                                    classify_overall(gate_statuses, implementation_identity_fail=implementation_identity_fail),
                                    e3_trigger(gate_statuses, implementation_identity_fail=implementation_identity_fail,
                                               g8_cause=g8.cause))
    return AnalysisResult(len(rows), concurrency, OutcomeCounts(*(counts[name] for name in counts)), primary,
                          _diagnostics(ww), boot, g5, g8, g9, overall, context)
