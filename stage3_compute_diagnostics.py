"""Observation-only, serial diagnostics for the frozen Stage-3 planning call.

Use ``ComputeDiagnostics`` around calls through ``stage3_runner.plan_position``
or the unmodified runner. The context patches imported function aliases with
plain forwarding wrappers; it does not execute another analysis or choose any
action. Its process-global patches require a single diagnostic thread and no
concurrent planner users. All original aliases are restored on context exit.

COMPLETE measures the actual production planning call, including table
validation. ANALYSIS measures the nested complete Stage-2 analyzer. LOCAL
INFERENCE measures only ``infer_deterministic`` (not constraint construction
or selection). PROBABILITY ANALYSIS measures only actual probability calls.
CANDIDATE GENERATION is inclusive of EXACT ROUTING. These nested populations
overlap and must not be added as independent phases.

PLANNER-ONLY is COMPLETE minus ANALYSIS from the same invocation. It includes
table validation, certainty/planning/candidate/pruning/selection/fallback work,
and diagnostic bookkeeping outside the timed analyzer body. Parent measurements
include nested wrapper overhead; no overhead correction is estimated. Setup,
engine execution, telemetry, persistence and initial policy OPEN are outside
the COMPLETE boundary. These diagnostics are separate from production timing
telemetry and modeled physical cost.
"""

from collections.abc import Iterable
from contextlib import ExitStack
from dataclasses import dataclass, field
from functools import wraps
from threading import get_ident
from time import perf_counter_ns

import simple_decision
import stage3_planner
import stage3_runner


class ComputeDiagnosticsError(RuntimeError):
    """The diagnostic invocation/nesting/measurement contract was violated."""


@dataclass(frozen=True)
class TimingSummary:
    """Integer nanoseconds; P50 is nearest-rank median, not midpoint median."""

    count: int
    p50_ns: int | None
    p90_ns: int | None
    p95_ns: int | None
    p99_ns: int | None
    max_ns: int | None


def summarize_samples(samples: Iterable[int]) -> TimingSummary:
    """Use nearest-rank ceil(p*N); an absent population has None statistics."""
    values = tuple(samples)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Timing samples must be non-negative integers, excluding bool.")
    ordered = sorted(values)
    count = len(ordered)
    if not count:
        return TimingSummary(0, None, None, None, None, None)

    def percentile(percent: int) -> int:
        return ordered[(percent * count + 99) // 100 - 1]

    return TimingSummary(
        count, percentile(50), percentile(90), percentile(95),
        percentile(99), ordered[-1],
    )


@dataclass(frozen=True)
class DecisionTiming:
    """Measurements belonging to one successful complete invocation only."""

    invocation_index: int
    complete_ns: int
    analysis_ns: int
    local_inference_ns: int
    probability_analysis_ns: int | None
    candidate_generation_ns: int | None
    exact_routing_ns: tuple[int, ...]
    planner_only_ns: int


_POPULATIONS = (
    "complete", "analysis", "local_inference", "probability_analysis",
    "planner_only", "candidate_generation", "exact_routing",
)
_ACTIVE_DIAGNOSTICS = None


@dataclass
class _Invocation:
    stack: list[str] = field(default_factory=lambda: ["complete"])
    samples: dict[str, list[int]] = field(
        default_factory=lambda: {name: [] for name in _POPULATIONS}
    )


class ComputeDiagnostics:
    """Collect successful calls without retaining observations or decisions.

    ``counts`` is a cheap progress snapshot. ``samples`` and ``decisions``
    return immutable-value snapshots for evidence/report generation. Re-entering
    an exited collector retains its prior completed measurements. An invocation
    that raises contributes no samples and propagates the original exception;
    such a failure must stop the qualification protocol, not be omitted from a
    reported successful run.
    """

    def __init__(self):
        self._samples = {name: [] for name in _POPULATIONS}
        self._decisions: list[DecisionTiming] = []
        self._invocation: _Invocation | None = None
        self._restoration: ExitStack | None = None
        self._thread: int | None = None

    @property
    def samples(self) -> dict[str, tuple[int, ...]]:
        return {name: tuple(values) for name, values in self._samples.items()}

    @property
    def counts(self) -> dict[str, int]:
        return {name: len(values) for name, values in self._samples.items()}

    @property
    def decisions(self) -> tuple[DecisionTiming, ...]:
        return tuple(self._decisions)

    def summaries(self) -> dict[str, TimingSummary]:
        return {name: summarize_samples(values) for name, values in self._samples.items()}

    def __enter__(self):
        global _ACTIVE_DIAGNOSTICS
        if _ACTIVE_DIAGNOSTICS is not None or self._restoration is not None:
            raise ComputeDiagnosticsError("Only one diagnostic context may be active.")
        restoration = ExitStack()
        self._restoration = restoration
        self._thread = get_ident()
        _ACTIVE_DIAGNOSTICS = self
        try:
            original = stage3_runner.plan_position
            restoration.callback(setattr, stage3_runner, "plan_position", original)
            stage3_runner.plan_position = self._complete_wrapper(original)
            for module, name, population, parent in (
                (stage3_planner, "analyze_position", "analysis", "complete"),
                (simple_decision, "infer_deterministic", "local_inference", "analysis"),
                (simple_decision, "calculate_probabilities", "probability_analysis", "analysis"),
                (stage3_planner, "generate_reveal_plans", "candidate_generation", "complete"),
                (stage3_planner, "exact_route", "exact_routing", "candidate_generation"),
            ):
                original = getattr(module, name)
                restoration.callback(setattr, module, name, original)
                setattr(module, name, self._nested_wrapper(original, population, parent))
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        global _ACTIVE_DIAGNOSTICS
        try:
            if self._restoration is not None:
                self._restoration.close()
        finally:
            self._restoration = None
            self._thread = None
            self._invocation = None
            if _ACTIVE_DIAGNOSTICS is self:
                _ACTIVE_DIAGNOSTICS = None
        return False

    def _require_context(self):
        if _ACTIVE_DIAGNOSTICS is not self or self._thread != get_ident():
            raise ComputeDiagnosticsError("Measurements require the active diagnostic thread.")

    @staticmethod
    def _validate_elapsed(elapsed: int):
        if type(elapsed) is not int or elapsed < 0:
            raise ComputeDiagnosticsError("Measured timing must be a non-negative integer.")

    def _complete_wrapper(self, original):
        @wraps(original)
        def measured(*args, **kwargs):
            self._require_context()
            if self._invocation is not None:
                raise ComputeDiagnosticsError("Complete planning calls must not be nested.")
            invocation = _Invocation()
            self._invocation = invocation
            try:
                started = perf_counter_ns()
                result = original(*args, **kwargs)
                elapsed = perf_counter_ns() - started
                self._validate_elapsed(elapsed)
                self._record_invocation(invocation, elapsed)
                return result
            finally:
                self._invocation = None
        return measured

    def _nested_wrapper(self, original, population: str, parent: str):
        @wraps(original)
        def measured(*args, **kwargs):
            self._require_context()
            invocation = self._invocation
            if invocation is None or invocation.stack[-1] != parent:
                raise ComputeDiagnosticsError(f"{population} must be nested directly in {parent}.")
            invocation.stack.append(population)
            try:
                started = perf_counter_ns()
                result = original(*args, **kwargs)
                elapsed = perf_counter_ns() - started
                self._validate_elapsed(elapsed)
                invocation.samples[population].append(elapsed)
                return result
            finally:
                invocation.stack.pop()
        return measured

    def _record_invocation(self, invocation: _Invocation, complete: int):
        samples = invocation.samples
        if invocation.stack != ["complete"]:
            raise ComputeDiagnosticsError("Nested timing stack did not return to COMPLETE.")
        if len(samples["analysis"]) != 1 or len(samples["local_inference"]) != 1:
            raise ComputeDiagnosticsError("Each decision requires exactly one analysis and local-inference call.")
        if len(samples["probability_analysis"]) > 1 or len(samples["candidate_generation"]) > 1:
            raise ComputeDiagnosticsError("Probability and candidate generation may each occur at most once.")
        analysis = samples["analysis"][0]
        planner_only = complete - analysis
        if planner_only < 0:
            raise ComputeDiagnosticsError("Negative same-invocation planner-only remainder.")
        record = DecisionTiming(
            len(self._decisions), complete, analysis, samples["local_inference"][0],
            samples["probability_analysis"][0] if samples["probability_analysis"] else None,
            samples["candidate_generation"][0] if samples["candidate_generation"] else None,
            tuple(samples["exact_routing"]), planner_only,
        )
        samples["complete"].append(complete)
        samples["planner_only"].append(planner_only)
        for name, values in samples.items():
            self._samples[name].extend(values)
        self._decisions.append(record)
