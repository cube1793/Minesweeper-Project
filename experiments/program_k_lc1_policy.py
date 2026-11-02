"""Experimental K-LC1 / SINGLETON_BAND_V1 over one native K selection.

Keep actual K-LC0 as baseline. Only an already-safe, surviving direct OPEN
whose physical HIDDEN component minus current M is its target may escape the
105% band, up to exactly 110% of native g and strictly nearer than baseline.
This public geometry does not certify an independent inference component or
bound whole-game Model C. No inference, routing, pruning or persistent cache.
"""

from dataclasses import dataclass, replace
from fractions import Fraction

from core_engine import Action, CellState
from experiments.program_k_lc0_policy import (
    DistanceSelection, apply_distance_band, route_distance,
    validate_distance_selection,
)
from experiments.program_k_policy import (
    KCandidate, KPolicyIntegrityError, PolicySelection, _coordinate,
    _guess_move, _validate_inputs, select_policy,
)
from simple_algorithm import SimpleMove
from stage3_planner import RevealPlan, _final_tie_key


POLICY_ID = "K-LC1"
POLICY_DEFINITION = "SINGLETON_BAND_V1"


@dataclass(frozen=True)
class SingletonAssessment:
    """Projection of one original survivor, never a generated candidate.

    Non-OPEN survivors have empty component/remainder and fail DIRECT_OPEN.
    Integer comparisons and D are projections of unchanged native plans.
    """

    candidate: KCandidate
    component: frozenset[tuple[int, int]]
    productive: frozenset[tuple[int, int]]
    distance: float
    band105_lhs: int
    band105_rhs: int
    band110_lhs: int
    band110_rhs: int
    failures: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class SingletonSelection:
    """Native authority, actual K-LC0 baseline, final choice and diagnostics."""

    native: PolicySelection
    baseline: DistanceSelection
    selected: PolicySelection
    assessments: tuple[SingletonAssessment, ...]
    reason: str

    @property
    def policy_id(self) -> str:
        return POLICY_ID

    @property
    def policy_definition(self) -> str:
        return POLICY_DEFINITION

    @property
    def exception_applied(self) -> bool:
        return self.selected.plan != self.baseline.selected.plan


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise KPolicyIntegrityError("SINGLETON_BAND_SELECTION", detail)


def _check_native(native: PolicySelection) -> None:
    """Check record/state consistency, not independently prove native g."""
    _require(type(native) is PolicySelection and native.failure_code is None,
             "A successful native selection is required.")
    _validate_inputs(native.evidence, native.cursor)
    _require(type(native.candidates) is tuple and type(native.survivors) is tuple,
             "Native candidate records must be immutable.")
    if native.continuation == "EXACT_GUESS":
        _require(native.move == _guess_move(native.evidence),
                 "Native guess target/risk must remain unchanged.")
        return
    _require(bool(native.evidence.selection_safe_cells), "Certainty requires current safety.")
    width, height = len(native.evidence.observation[0]), len(native.evidence.observation)
    _require(all(type(c) is KCandidate for c in native.candidates + native.survivors),
             "Expected original native candidate records.")
    _require(all(c in native.candidates for c in native.survivors)
             and len(set(native.survivors)) == len(native.survivors),
             "Survivors must be unique original candidates.")
    for c in native.survivors:
        p = c.plan
        _require(type(p) is RevealPlan and type(p.latency_us) is int and p.latency_us > 0
                 and type(p.reveals) is int and p.reveals > 0
                 and type(p.actions) is tuple and bool(p.actions)
                 and all(type(m) is SimpleMove and type(m.action) is Action
                         and _coordinate((m.x, m.y), width, height) for m in p.actions),
                 "Invalid native survivor plan.")
        _require(type(c.setup_cells) is frozenset and type(c.reveal_cells) is frozenset
                 and c.setup_cells <= native.evidence.after.H & native.evidence.after.M
                 and c.reveal_cells <= native.evidence.selection_safe_cells
                 and len(c.reveal_cells) == p.reveals,
                 "Native survivor setup/reveal sets disagree with current evidence.")
        if c.category == "DIRECT_SAFE_OPEN":
            target = (p.actions[-1].x, p.actions[-1].y)
            _require(len(p.actions) == 1 and p.actions[0].action is Action.OPEN
                     and not c.setup_cells and p.reveals == 1
                     and c.reveal_cells == frozenset({target}),
                     "Malformed native direct-safe OPEN.")
    _require(any(c.plan == native.plan and c.category == native.category
                 for c in native.survivors)
             and native.move == native.plan.actions[0],
             "Native g/category/first move must identify an original survivor.")


def _hidden_components(observation) -> dict:
    """Read at most the current 30 x 16 cells; include hidden M in connectivity."""
    remaining = {(x, y) for y, row in enumerate(observation)
                 for x, v in enumerate(row) if v == CellState.HIDDEN}
    result = {}
    while remaining:
        seed = min(remaining, key=lambda c: (c[1], c[0]))
        remaining.remove(seed)
        component, todo = {seed}, [seed]
        while todo:
            x, y = todo.pop()
            for ny in range(y - 1, y + 2):
                for nx in range(x - 1, x + 2):
                    cell = (nx, ny)
                    if cell in remaining:
                        remaining.remove(cell)
                        component.add(cell)
                        todo.append(cell)
        frozen = frozenset(component)
        result.update((c, frozen) for c in component)
    return result


def _assess(native, baseline) -> tuple[SingletonAssessment, ...]:
    if native.continuation == "EXACT_GUESS":
        return ()  # No exception/component evaluation on guesses.
    components = _hidden_components(native.evidence.observation)
    g, b = native.plan, baseline.selected.plan
    baseline_distance = route_distance(b, native.cursor)
    records = []
    for candidate in native.survivors:
        p = candidate.plan
        target = (p.actions[-1].x, p.actions[-1].y)
        direct = (candidate.category == "DIRECT_SAFE_OPEN" and not candidate.setup_cells
                  and len(p.actions) == 1 and p.actions[0].action is Action.OPEN
                  and p.reveals == 1 and target in native.evidence.selection_safe_cells
                  and target in components)
        component = components[target] if direct else frozenset()
        productive = component - native.evidence.after.M
        distance = route_distance(p, native.cursor)
        a105, b105 = 20 * p.latency_us * g.reveals, 21 * g.latency_us * p.reveals
        a110, b110 = 10 * p.latency_us * g.reveals, 11 * g.latency_us * p.reveals
        failures = tuple(name for name, ok in (
            ("DIRECT_OPEN", direct),
            ("SINGLETON", direct and productive == frozenset({target})),
            ("OUTSIDE_105", a105 > b105),
            ("WITHIN_110", a110 <= b110),
            ("STRICT_DISTANCE", distance < baseline_distance),
        ) if not ok)
        records.append(SingletonAssessment(candidate, component, productive, distance,
                                            a105, b105, a110, b110, failures))
    return tuple(records)


def _rank(assessment: SingletonAssessment) -> tuple:
    p = assessment.candidate.plan
    return (assessment.distance, Fraction(p.latency_us, p.reveals),
            p.latency_us, _final_tie_key(p))


def apply_singleton_band(native: PolicySelection) -> SingletonSelection:
    """Pure projection of one native result; actual K-LC0 is always baseline."""
    _check_native(native)
    baseline = apply_distance_band(native, control=False)
    assessments = _assess(native, baseline)
    eligible = tuple(a for a in assessments if a.eligible)
    selected = baseline.selected
    if eligible:
        winner = min(eligible, key=_rank).candidate
        selected = replace(native, plan=winner.plan, category=winner.category,
                           move=winner.plan.actions[0])
    reason = ("EXACT_GUESS_UNCHANGED" if native.continuation == "EXACT_GUESS" else
              "SINGLETON_BAND_OVERRIDE" if eligible else "K_LC0_BASELINE_RETAINED")
    return SingletonSelection(native, baseline, selected, assessments, reason)


def select_singleton_policy(evidence, cursor, table) -> SingletonSelection:
    """One native selection, including its ordinary SETUP_OPEN failure contract."""
    return apply_singleton_band(select_policy(evidence, cursor, table))


def validate_singleton_selection(result: SingletonSelection) -> None:
    """Recheck stored arithmetic/geometry and bindings without native selection.

    This does not independently certify inference or the optimality of native g.
    The runner separately binds the final survivor to live state using the
    unchanged K execution validator before executing exactly its first input.
    """
    _require(type(result) is SingletonSelection, "Expected a K-LC1 selection record.")
    native, selected = result.native, result.selected
    _check_native(native)
    _require(type(result.baseline) is DistanceSelection and result.baseline.native is native
             and result.baseline.control is False, "Baseline must be actual K-LC0 of this native result.")
    validate_distance_selection(result.baseline)
    _require(type(selected) is PolicySelection and selected.evidence is native.evidence
             and selected.cursor == native.cursor and selected.candidates is native.candidates
             and selected.survivors is native.survivors and selected.failure_code is None,
             "Final selection must retain the native evidence/candidates/survivors.")
    expected = _assess(native, result.baseline)
    _require(type(result.assessments) is tuple
             and all(type(a) is SingletonAssessment and type(a.component) is frozenset
                     and type(a.productive) is frozenset and type(a.distance) is float
                     and all(type(v) is int for v in (a.band105_lhs, a.band105_rhs,
                                                      a.band110_lhs, a.band110_rhs))
                     and type(a.failures) is tuple for a in result.assessments)
             and result.assessments == expected,
             "Exception diagnostics disagree with current state or native plans.")
    eligible = tuple(a for a in expected if a.eligible)
    if native.continuation == "EXACT_GUESS":
        _require(selected is native and not result.assessments, "Guess must keep native identity.")
        reason = "EXACT_GUESS_UNCHANGED"
    elif eligible:
        winner = min(eligible, key=_rank).candidate
        _require(selected.plan == winner.plan and selected.category == winner.category
                 and selected.move == winner.plan.actions[0],
                 "Final plan/category/first input violates singleton rank.")
        reason = "SINGLETON_BAND_OVERRIDE"
    else:
        _require(selected is result.baseline.selected, "Ineligible exception must retain baseline.")
        reason = "K_LC0_BASELINE_RETAINED"
    _require(result.reason == reason, "Selection reason disagrees with final choice.")
