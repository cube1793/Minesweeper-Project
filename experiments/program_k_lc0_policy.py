"""Experimental K-LC0 / DISTANCE_BAND_V1, restricted to native K survivors.

One native select_policy call owns evidence, candidates, routes, pruning and g.
Certainty selection allows E <= 21/20 E(g), then minimizes the Euclidean length
of that unchanged full action sequence. Distance ties mean Python float ==,
without rounding or tolerance; E, L and the frozen final key break those ties.
This is neither a new physical cost nor a region-completion guarantee.
"""

from dataclasses import dataclass, replace
from fractions import Fraction
import math

from core_engine import Action
from experiments.program_k_policy import (
    KCandidate, KPolicyIntegrityError, PolicySelection, select_policy,
)
from stage3_planner import RevealPlan, _final_tie_key


POLICY_ID = "K-LC0"
POLICY_DEFINITION = "DISTANCE_BAND_V1"
CONTROL_ID = "K-LC0-CONTROL"


def route_distance(plan: RevealPlan, cursor: tuple[int, int]) -> float:
    """Board-cell distance, including every setup and the terminal input.

    Evaluate the native exact_route order; never search for another FLAG order.
    Mathematical equality and floating-point equality need not coincide.
    """
    points = (cursor,) + tuple((move.x, move.y) for move in plan.actions)
    return math.fsum(math.hypot(b[0] - a[0], b[1] - a[1])
                     for a, b in zip(points, points[1:]))


def in_distance_band(plan: RevealPlan, g: RevealPlan) -> bool:
    return 20 * plan.latency_us * g.reveals <= 21 * g.latency_us * plan.reveals


def _rank(candidate: KCandidate, cursor: tuple[int, int]) -> tuple:
    plan = candidate.plan
    return (route_distance(plan, cursor), Fraction(plan.latency_us, plan.reveals),
            plan.latency_us, _final_tie_key(plan))


@dataclass(frozen=True)
class DistanceSelection:
    """Original K result and the one-input experimental choice, archive only."""

    native: PolicySelection
    selected: PolicySelection
    band: tuple[KCandidate, ...]
    control: bool
    reason: str

    @property
    def policy_id(self) -> str:
        return CONTROL_ID if self.control else POLICY_ID

    @property
    def overridden(self) -> bool:
        return self.selected.plan != self.native.plan


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise KPolicyIntegrityError("DISTANCE_BAND_SELECTION", detail)


def _native_band(native: PolicySelection) -> tuple[KCandidate, ...]:
    _require(type(native) is PolicySelection and native.failure_code is None,
             "A successful native selection is required.")
    if native.continuation == "EXACT_GUESS":
        _require(native.plan is None and not native.candidates and not native.survivors
                 and native.category == "EXACT_MINIMUM_RISK_GUESS",
                 "Exact guess must retain its native no-setup selection.")
        return ()
    _require(native.plan is not None and bool(native.survivors),
             "Certainty requires native survivors and g.")
    if any(c.category == "SETUP_OPEN" or
           (len(c.plan.actions) > 1 and c.plan.actions[-1].action is Action.OPEN)
           for c in native.survivors):
        raise KPolicyIntegrityError("SETUP_OPEN_SURVIVED", "Native integrity failure is not recoverable.")
    _require(any(c.plan == native.plan and c.category == native.category
                 for c in native.survivors), "Native g must be a survivor.")
    return tuple(c for c in native.survivors if in_distance_band(c.plan, native.plan))


def apply_distance_band(native: PolicySelection, *, control: bool = False) -> DistanceSelection:
    """Pure adapter over one native result; no inference or candidate generation."""
    _require(type(control) is bool, "CONTROL must be boolean.")
    band = _native_band(native)
    selected = native
    if native.continuation == "EXACT_GUESS":
        reason = "EXACT_GUESS_UNCHANGED"
    elif control:
        reason = "CONTROL_NATIVE_G"
    else:
        winner = min(band, key=lambda c: _rank(c, native.cursor))
        if winner.plan != native.plan:
            selected = replace(native, plan=winner.plan, category=winner.category,
                               move=winner.plan.actions[0])
        reason = "DISTANCE_BAND_OVERRIDE" if selected is not native else "NATIVE_G_RETAINED"
    return DistanceSelection(native, selected, band, control, reason)


def select_distance_policy(evidence, cursor, table, *, control: bool = False) -> DistanceSelection:
    """Exactly one call to native K selection, with its normal SETUP_OPEN vocabulary."""
    _require(type(control) is bool, "CONTROL must be boolean.")
    return apply_distance_band(select_policy(evidence, cursor, table), control=control)


def validate_distance_selection(result: DistanceSelection) -> None:
    """Validate the new ranking separately from native physical execution checks.

    Only stored evidence/plans are inspected. No inference, regeneration,
    repruning, routing, or native policy call is authorized by this check.
    """
    _require(type(result) is DistanceSelection and type(result.control) is bool,
             "Expected an experimental selection record.")
    native, selected = result.native, result.selected
    band = _native_band(native)
    _require(result.band == band, "Band differs from the exact native-survivor band.")
    _require(type(selected) is PolicySelection and selected.evidence is native.evidence
             and selected.cursor == native.cursor and selected.candidates is native.candidates
             and selected.survivors is native.survivors
             and selected.failure_code is None,
             "Evidence, cursor, candidates and survivors must remain unchanged.")
    if native.continuation == "EXACT_GUESS" or result.control:
        _require(selected is native, "Guess/CONTROL must keep the original native result.")
        expected_reason = ("EXACT_GUESS_UNCHANGED" if native.continuation == "EXACT_GUESS"
                           else "CONTROL_NATIVE_G")
    else:
        matches = tuple(c for c in band if c.plan == selected.plan and c.category == selected.category)
        _require(len(matches) == 1 and selected.move == matches[0].plan.actions[0],
                 "Selected plan/category/first input must identify one band survivor.")
        chosen_key = _rank(matches[0], native.cursor)
        _require(all(chosen_key <= _rank(c, native.cursor) for c in band),
                 "Selected survivor violates distance / E / L / frozen tie ranking.")
        expected_reason = "DISTANCE_BAND_OVERRIDE" if result.overridden else "NATIVE_G_RETAINED"
    _require(result.reason == expected_reason, "Selection reason disagrees with the choice.")
