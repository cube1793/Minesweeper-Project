"""S3D2-A / PROVEN_OPENING_V1 arithmetic, record, execution and small-run checks.

Synthetic records isolate selection arithmetic; like the K-LC1 fixtures they do
not certify native g or pruning. Real-K states use tiny public observations.
Engine layouts are fixed tiny synthetic boards confined to Engine construction.
No public Expert generation/execution occurs in this module. Expected values
were fixed beforehand in VERIFICATION_PLAN.json (hand calculation).
"""

from dataclasses import replace
from fractions import Fraction
import math
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus
from experiments import program_d2_opening_policy as policy
from experiments import program_d2_opening_runner as d2runner
from experiments import program_k_lc1_policy as lc1
from experiments.program_k_capability import (
    Accounting, DecisionAnalysis, KIntegrityError, KLocalSession, LocalAnalysis,
)
from experiments.program_k_lc1_runner import run_k_lc1
from experiments.program_k_policy import KCandidate, KPolicyIntegrityError, PolicySelection
from experiments.program_k_runner import KExecutionError, validate_k_p0_execution
from simple_algorithm import SimpleMove
from stage3_physical import load_timing_table
from stage3_planner import RevealPlan
from tests.test_program_k_harness import PublicPort, Slice6ArchiveSentinelPort, fixed_engine


H, F, PLAYING = int(CellState.HIDDEN), int(CellState.FLAGGED), GameStatus.PLAYING
WIDTH, HEIGHT = 12, 4
X01 = ((H, 1, H), (1, 1, H))          # LOCAL_SAFE, one mine, cursor (0,1)
X02 = ((0, 0, 1, H, H, H, H),)        # EXACT_SAFE, one mine, cursor (0,0)


def cells(values):
    return frozenset(map(tuple, values))


def O(x, y):
    return SimpleMove(Action.OPEN, x, y)


def direct(target, latency):
    return KCandidate(RevealPlan((O(*target),), latency, 1),
                      "DIRECT_SAFE_OPEN", frozenset(), frozenset({target}))


def chord(target, reveals, latency, flags=()):
    return KCandidate(RevealPlan(tuple(SimpleMove(Action.FLAG, *p) for p in flags)
                                 + (SimpleMove(Action.CHORD, *target),), latency, len(reveals)),
                      "SETUP_CHORD" if flags else "DIRECT_CHORD", cells(flags), cells(reveals))


def record(candidates, survivors, *, g=None, cursor=(0, 0), unresolved=(), mines=(), flags=(),
           safe_extra=()):
    """Public-domain-consistent arithmetic fixture on a 12 x 4 grid.

    Every cell not named is a revealed number. Latencies, survivors and g are
    stated by the test; nothing here re-proves native routing or pruning.
    """
    candidates, survivors = tuple(candidates), tuple(survivors)
    safe = frozenset().union(*(c.reveal_cells for c in candidates)) | cells(safe_extra)
    mines, flags, unresolved = cells(mines), cells(flags), cells(unresolved)
    hidden = (safe | unresolved | mines) - flags
    observation = tuple(tuple(F if (x, y) in flags else H if (x, y) in hidden else 1
                              for x in range(WIDTH)) for y in range(HEIGHT))
    account = Accounting(flags, hidden, mines, flags | mines, hidden - mines, 0, ())
    local = LocalAnalysis(account, account, frozenset(), safe, safe, frozenset(), safe, ())
    evidence = DecisionAnalysis(observation, len(mines), local, None, None, "NOT_REACHED",
                                account, (), "LOCAL_SAFE", safe, None)
    g = survivors[0] if g is None else g
    return PolicySelection(evidence, cursor, g.plan.actions[0], g.plan, g.category,
                           candidates, survivors)


def checked(native):
    result = policy.apply_proven_opening(lc1.apply_singleton_band(native))
    policy.validate_opening_selection(result)
    return result


def s1(l4=140, l5=150, l6=160, **kwargs):
    o4, o5, o6 = direct((4, 0), l4), direct((5, 0), l5), direct((6, 0), l6)
    return record((o4, o5, o6), (o4,), mines=((3, 0),), **kwargs), (o4, o5, o6)


def s5(l51=130, cursor=(4, 0), order=(0, 1, 2)):
    items = (direct((4, 2), 120), direct((3, 1), 130), direct((5, 1), l51))
    return record(tuple(items[i] for i in order), (items[0],), cursor=cursor, mines=((4, 3),))


def s6(latency, scale=1):
    o51, o61 = direct((5, 1), latency), direct((6, 1), latency + 10 * scale)
    q = chord((5, 0), ((5, 1), (6, 1)), 200 * scale)
    survivors = (o51, q) if latency < 200 * scale else (q,)
    return record((o51, o61, q), survivors, g=q)


class OpeningArithmeticTests(unittest.TestCase):
    def test_a01_safe_cell_with_an_unresolved_neighbour_is_not_a_proven_zero(self):
        o4, o5 = direct((4, 0), 140), direct((5, 0), 150)
        r = checked(record((o4, o5), (o4,), unresolved=((6, 0),), mines=((3, 0),)))
        self.assertEqual(r.zero_proven, frozenset())
        self.assertEqual((r.reason, r.assessments, r.applied), ("NO_PROVEN_OPENING", (), None))
        self.assertEqual(r.move, O(4, 0))
        self.assertIs(r.selected, r.inner.selected)
        self.assertEqual((r.baseline_reveal.direct, r.baseline_reveal.guaranteed,
                          r.baseline_reveal.bound_kind), (cells(((4, 0),)), cells(((4, 0),)), "EXACT"))

    def test_a02_hidden_mine_or_flag_neighbour_proves_nonzero_not_zero(self):
        o4, o5 = direct((4, 0), 140), direct((5, 0), 150)
        for flags in ((), ((6, 0),)):
            with self.subTest(flags=flags):
                native = record((o4, o5), (o4,), mines=((3, 0), (6, 0)), flags=flags)
                r = checked(native)
                self.assertEqual((r.zero_proven, r.reason), (frozenset(), "NO_PROVEN_OPENING"))
                zero, nonzero = policy.classify_safe_cells(
                    native.evidence.observation, native.evidence.selection_safe_cells,
                    native.evidence.after.M)
                self.assertEqual((zero, nonzero), (frozenset(), cells(((4, 0), (5, 0)))))

    def test_a03_zero_proof_guaranteed_set_and_exact_versus_lower_bound(self):
        r = checked(s1()[0])
        self.assertEqual(r.zero_proven, cells(((5, 0), (6, 0))))
        self.assertEqual(len(r.assessments), 1)
        region = r.assessments[0].region
        self.assertEqual((region.cells, region.guaranteed, region.undetermined, region.bound_kind,
                          region.guaranteed_count),
                         (cells(((5, 0), (6, 0))), cells(((4, 0), (5, 0), (6, 0))), frozenset(), "EXACT", 3))
        lower = checked(s1(unresolved=((7, 0),))[0])
        region = lower.assessments[0].region
        self.assertEqual(lower.zero_proven, cells(((5, 0),)))
        self.assertEqual((region.cells, region.guaranteed, region.undetermined, region.bound_kind),
                         (cells(((5, 0),)), cells(((4, 0), (5, 0), (6, 0))), cells(((6, 0),)), "LOWER_BOUND"))
        self.assertEqual((lower.move, lower.assessments[0].gain_lhs, lower.assessments[0].gain_rhs),
                         (O(5, 0), 150, 420))

    def test_a04_one_region_is_counted_once_and_shared_borders_are_never_summed(self):
        o51, o61 = direct((5, 1), 150), direct((6, 1), 150)
        r = checked(record((o51, o61), (o51, o61), g=o51))
        self.assertEqual(r.inner.selected.move, O(5, 1))
        self.assertEqual(len(r.assessments), 1)
        a = r.assessments[0]
        self.assertEqual((a.region.cells, a.region.guaranteed_count, a.region.bound_kind, a.target),
                         (cells(((5, 1), (6, 1))), 2, "EXACT", (5, 1)))
        self.assertEqual((r.baseline_reveal.guaranteed_count, a.gain_lhs, a.gain_rhs, a.failures,
                          r.reason), (2, 300, 300, ("GAIN",), "NO_ELIGIBLE_OPENING"))
        shared = checked(s5())
        first, second = shared.assessments
        self.assertEqual((first.region.cells, first.region.guaranteed),
                         (cells(((3, 1),)), cells(((3, 1), (4, 2)))))
        self.assertEqual((second.region.cells, second.region.guaranteed),
                         (cells(((5, 1),)), cells(((5, 1), (4, 2)))))
        self.assertEqual(first.region.guaranteed & second.region.guaranteed, cells(((4, 2),)))
        self.assertEqual(shared.baseline_reveal.guaranteed_count, 1)
        for a in shared.assessments:  # each stands alone: 120 * 2, never 120 * 3 or 120 * 4
            self.assertEqual((a.region.guaranteed_count, a.region.bound_kind, a.gain_lhs, a.gain_rhs),
                             (2, "EXACT", 130, 240))

    def test_a05_corner_and_edge_cells_use_only_in_board_neighbours(self):
        corner = [direct((1, 1), 100), direct((0, 1), 110), direct((1, 0), 110), direct((0, 0), 120)]
        r = checked(record(corner, (corner[0],), cursor=(3, 3)))
        region = r.assessments[0].region
        self.assertEqual((len(r.assessments), region.cells, region.guaranteed, region.bound_kind),
                         (1, cells(((0, 0), (1, 0), (0, 1), (1, 1))),
                          cells(((0, 0), (1, 0), (0, 1), (1, 1))), "EXACT"))
        self.assertEqual((r.assessments[0].gain_lhs, r.assessments[0].gain_rhs), (400, 400))
        edge = [direct((5, 3), 100), direct((6, 3), 110), direct((7, 3), 120)]
        r = checked(record(edge, (edge[0],)))
        region = r.assessments[0].region
        self.assertEqual((region.cells, region.guaranteed_count, region.bound_kind),
                         (cells(((5, 3), (6, 3), (7, 3))), 3, "EXACT"))
        for a in r.assessments:
            self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in a.region.guaranteed))
        self.assertEqual(len(policy._neighbors((0, 0), WIDTH, HEIGHT)), 3)
        self.assertEqual(len(policy._neighbors((6, 3), WIDTH, HEIGHT)), 5)
        self.assertEqual(len(policy._neighbors((6, 2), WIDTH, HEIGHT)), 8)

    def test_a06_covering_opening_with_gain_replaces_an_open_baseline(self):
        native, (o4, o5, o6) = s1()
        r = checked(native)
        a = r.applied
        self.assertEqual(r.inner.selected.move, O(4, 0))
        self.assertEqual((r.reason, r.move, r.category), ("PROVEN_OPENING_OVERRIDE", O(5, 0),
                                                          "PROVEN_OPENING_OPEN"))
        self.assertTrue(r.override_applied)
        self.assertIsNone(r.selected)
        self.assertIs(a.candidate, o5)
        self.assertEqual((a.target, a.gain_lhs, a.gain_rhs, a.failures, a.distance),
                         ((5, 0), 150, 420, (), 5.0))
        self.assertEqual(r.baseline_reveal.guaranteed_count, 1)
        self.assertEqual((r.policy_id, r.policy_definition), ("S3D2-A", "PROVEN_OPENING_V1"))

    def test_a07_cheaper_chord_keeps_k_lc1_and_equality_does_not_apply(self):
        for latency, gain, applied in ((150, (300, 400), True), (199, (398, 400), True),
                                       (200, (400, 400), False), (250, (500, 400), False)):
            with self.subTest(latency=latency):
                r = checked(s6(latency))
                a = r.assessments[0]
                self.assertEqual(r.inner.selected.move, SimpleMove(Action.CHORD, 5, 0))
                self.assertEqual(((a.gain_lhs, a.gain_rhs), r.override_applied), (gain, applied))
                self.assertEqual(r.baseline_reveal.guaranteed_count, 2)
                if applied:
                    self.assertEqual((r.move, a.failures), (O(5, 1), ()))
                else:
                    self.assertEqual((r.move, a.failures), (SimpleMove(Action.CHORD, 5, 0), ("GAIN",)))
                    self.assertIs(r.selected, r.inner.selected)

    def test_a08_opening_competes_with_a_chord_that_needs_a_setup_flag(self):
        o51, o61 = direct((5, 1), 150), direct((6, 1), 160)
        q = chord((5, 2), ((5, 1), (6, 1)), 260, flags=((4, 3),))
        r = checked(record((o51, o61, q), (o51, q), g=q, mines=((4, 3),)))
        self.assertEqual(r.inner.selected.move, SimpleMove(Action.FLAG, 4, 3))
        self.assertEqual((r.move, r.category), (O(5, 1), "PROVEN_OPENING_OPEN"))
        self.assertEqual((r.applied.gain_lhs, r.applied.gain_rhs), (300, 520))

    def test_a09_opening_that_does_not_cover_the_baseline_is_kept_out(self):
        o91, o51, o61 = direct((9, 1), 110), direct((5, 1), 130), direct((6, 1), 140)
        r = checked(record((o91, o51, o61), (o91,)))
        first, second = r.assessments
        self.assertEqual((first.region.cells, first.region.guaranteed_count, first.gain_lhs,
                          first.gain_rhs, first.failures),
                         (cells(((5, 1), (6, 1))), 2, 130, 220, ("COVERS_BASELINE",)))
        self.assertEqual((second.region.cells, second.failures), (cells(((9, 1),)),
                                                                  ("EXTRA_REVEAL", "GAIN")))
        self.assertEqual((r.reason, r.move), ("NO_ELIGIBLE_OPENING", O(9, 1)))
        self.assertIs(r.selected, r.inner.selected)

    def test_a10_large_guaranteed_reveal_loses_when_movement_cost_is_too_high(self):
        r = checked(s1(140, 500, 510)[0])
        a = r.assessments[0]
        self.assertEqual((a.region.guaranteed_count, a.gain_lhs, a.gain_rhs, a.failures),
                         (3, 500, 420, ("GAIN",)))
        self.assertEqual((r.reason, r.move), ("NO_ELIGIBLE_OPENING", O(4, 0)))

    def test_a11_pruned_opening_may_be_chosen_and_pruning_diagnostics_are_recorded(self):
        native, (o4, o5, o6) = s1()
        r = checked(native)
        self.assertNotIn(o5, native.survivors)
        self.assertEqual((r.applied.native_survivor, r.applied.g_dominated), (False, False))
        lc1.validate_singleton_selection(r.inner)  # the K-LC1 record is untouched
        self.assertEqual((r.inner.selected.plan, r.inner.native.survivors), (o4.plan, (o4,)))
        pocket = [direct(c, 145 + i) for i, c in enumerate(((8, 2), (9, 2), (8, 3), (9, 3)))]
        wide = checked(record((o4, o5, o6, *pocket), (o4,), mines=((3, 0),)))
        first, second = wide.assessments
        self.assertEqual((first.region.cells, first.failures, first.native_survivor, first.g_dominated),
                         (cells(((5, 0), (6, 0))), (), False, True))
        self.assertEqual((second.region.guaranteed_count, second.target, second.gain_lhs,
                          second.gain_rhs, second.failures, second.g_dominated),
                         (4, (8, 2), 145, 560, ("COVERS_BASELINE",), False))
        self.assertEqual(wide.move, O(5, 0))
        o51, o61 = direct((5, 1), 150), direct((6, 1), 150)
        survivor = checked(record((o51, o61), (o51, o61), g=o51))
        self.assertTrue(survivor.assessments[0].native_survivor)

    def test_a12_rank_is_rate_then_distance_then_cost_then_frozen_key(self):
        orders = ((0, 1, 2), (2, 1, 0), (1, 2, 0))
        for order in orders:
            with self.subTest(order=order):
                self.assertEqual(checked(s5(order=order)).move, O(3, 1))       # frozen key
                self.assertEqual(checked(s5(l51=125, order=order)).move, O(5, 1))  # rate
                near = checked(s5(cursor=(3, 0), order=order))               # distance
                self.assertEqual(near.move, O(3, 1))
        tie = checked(s5())
        self.assertEqual([a.eligible for a in tie.assessments], [True, True])
        self.assertEqual(tie.assessments[0].distance, tie.assessments[1].distance)
        self.assertEqual(tie.assessments[0].distance, math.hypot(1, 1))
        near = checked(s5(cursor=(3, 0)))
        self.assertEqual([a.distance for a in near.assessments], [1.0, math.hypot(2, 1)])

    def test_a13_exact_guess_is_unchanged_and_not_evaluated(self):
        evidence = KLocalSession(2, 2, 1).analyze_decision(((1, H), (H, H)), status=PLAYING)
        with patch.object(policy, "opening_regions", side_effect=AssertionError("guess geometry")), \
                patch.object(policy, "_direct_opens", side_effect=AssertionError("guess candidates")):
            r = policy.select_opening_policy(evidence, (0, 1), load_timing_table())
            policy.validate_opening_selection(r)
        self.assertEqual((r.reason, r.assessments, r.applied, r.baseline_reveal, r.zero_proven),
                         ("EXACT_GUESS_UNCHANGED", (), None, None, frozenset()))
        self.assertEqual(r.move, O(*evidence.guess_target))
        self.assertIs(r.selected, r.inner.native)

    def test_a14_k_lc1_singleton_exception_stays_the_baseline(self):
        q = chord((10, 0), ((10, 1), (11, 1)), 200)
        o10, o101, o111 = direct((1, 0), 108), direct((10, 1), 190), direct((11, 1), 195)
        r = checked(record((q, o10, o101, o111), (q, o10), g=q))
        self.assertTrue(r.inner.exception_applied)
        exception = next(a for a in r.inner.assessments if a.eligible)
        self.assertEqual((exception.band105_lhs, exception.band105_rhs,
                          exception.band110_lhs, exception.band110_rhs), (4320, 4200, 2160, 2200))
        first, second = r.assessments
        self.assertEqual((first.region.cells, first.gain_lhs, first.gain_rhs, first.failures),
                         (cells(((1, 0),)), 108, 108, ("EXTRA_REVEAL", "GAIN")))
        self.assertEqual((second.region.cells, second.gain_lhs, second.gain_rhs, second.failures),
                         (cells(((10, 1), (11, 1))), 190, 216, ("COVERS_BASELINE",)))
        self.assertEqual((r.reason, r.move), ("NO_ELIGIBLE_OPENING", O(1, 0)))
        self.assertIs(r.selected, r.inner.selected)

    def test_a15_large_integers_stay_exact(self):
        scale = 10**30
        for latency, applied in ((199 * scale, True), (200 * scale, False)):
            with self.subTest(latency=latency):
                r = checked(s6(latency, scale))
                a = r.assessments[0]
                self.assertEqual(r.override_applied, applied)
                self.assertEqual((a.gain_lhs, a.gain_rhs), (latency * 2, 400 * scale))
                self.assertIs(type(a.gain_lhs), int)

    def test_a16_native_and_k_lc1_failures_propagate_without_fallback(self):
        error = KPolicyIntegrityError("SETUP_OPEN_SURVIVED", "sentinel")
        with patch.object(policy, "select_singleton_policy", side_effect=error), \
                self.assertRaises(KPolicyIntegrityError) as caught:
            policy.select_opening_policy(None, (0, 0), load_timing_table())
        self.assertIs(caught.exception, error)
        inner = lc1.apply_singleton_band(s1()[0])
        with self.assertRaises(KPolicyIntegrityError) as caught:
            policy.apply_proven_opening(replace(inner, reason="FAKE"))
        self.assertEqual(caught.exception.code, "SINGLETON_BAND_SELECTION")
        with self.assertRaises(KPolicyIntegrityError):
            policy.apply_proven_opening(None)

    def test_a17_missing_or_malformed_direct_open_is_an_error_not_a_silent_keep(self):
        o4, o5 = direct((4, 0), 140), direct((5, 0), 150)
        missing = record((o4, o5), (o4,), mines=((3, 0),), safe_extra=((6, 0),))
        wrong_reveal = KCandidate(RevealPlan((O(6, 0),), 160, 1), "DIRECT_SAFE_OPEN",
                                  frozenset(), frozenset({(5, 0)}))
        duplicate = direct((5, 0), 151)
        native, _ = s1()
        outside = chord((8, 0), ((9, 3),), 300)
        for bad in (missing,
                    record((o4, o5, wrong_reveal), (o4,), mines=((3, 0),), safe_extra=((6, 0),)),
                    replace(native, candidates=native.candidates + (duplicate,)),
                    replace(native, candidates=native.candidates + (outside,))):
            with self.subTest(candidates=len(bad.candidates)), \
                    self.assertRaises(KPolicyIntegrityError) as caught:
                policy.apply_proven_opening(lc1.apply_singleton_band(bad))
            self.assertEqual(caught.exception.code, "PROVEN_OPENING_SELECTION")

    def test_a18_region_with_guaranteed_count_one_never_applies(self):
        o91, o51, o61 = direct((9, 1), 110), direct((5, 1), 130), direct((6, 1), 140)
        r = checked(record((o91, o51, o61), (o91,)))
        single = r.assessments[1]
        self.assertEqual((single.region.guaranteed_count, single.region.bound_kind), (1, "EXACT"))
        self.assertIn("EXTRA_REVEAL", single.failures)
        self.assertFalse(r.override_applied)

    def test_a19_baseline_chord_gets_its_own_guaranteed_flood_credit(self):
        q = chord((4, 1), ((5, 1),), 120)
        opens = [direct((5, 1), 130), direct((6, 1), 140), direct((7, 1), 150)]
        r = checked(record((q, *opens), (q,), mines=((8, 0),)))
        credit, a = r.baseline_reveal, r.assessments[0]
        self.assertEqual((credit.direct, credit.guaranteed, credit.bound_kind),
                         (cells(((5, 1),)), cells(((5, 1), (6, 1), (7, 1))), "EXACT"))
        self.assertEqual((a.region.cells, a.gain_lhs, a.gain_rhs, a.failures),
                         (cells(((5, 1), (6, 1))), 390, 360, ("GAIN",)))
        self.assertEqual(r.move, SimpleMove(Action.CHORD, 4, 1))
        self.assertLess(130 * 1, 120 * 3)  # without the credit this would wrongly apply


class OpeningRecordValidationTests(unittest.TestCase):
    def test_v01_tampered_records_are_rejected(self):
        r = checked(s1()[0])
        a = r.applied
        grown = replace(a.region, guaranteed=a.region.guaranteed | {(7, 0)})
        variants = [
            replace(r, applied=replace(a, region=grown)),
            replace(r, assessments=(replace(a, region=grown),)),
            replace(r, assessments=(replace(a, region=replace(a.region, bound_kind="LOWER_BOUND")),)),
            replace(r, assessments=(replace(a, gain_rhs=a.gain_rhs + 1),)),
            replace(r, assessments=(replace(a, failures=("GAIN",)),)),
            replace(r, assessments=(replace(a, g_dominated=True),)),
            replace(r, assessments=()),
            replace(r, zero_proven=r.zero_proven | {(4, 0)}),
            replace(r, baseline_reveal=replace(r.baseline_reveal,
                                               guaranteed=r.baseline_reveal.guaranteed | {(5, 0)})),
            replace(r, reason="NO_ELIGIBLE_OPENING"),
            replace(r, move=r.inner.selected.move),
            replace(r, move=O(6, 0)),
            replace(r, category="DIRECT_SAFE_OPEN"),
            replace(r, applied=None),
        ]
        kept = checked(s1(140, 500, 510)[0])
        variants += [replace(kept, applied=kept.assessments[0]), replace(kept, move=O(5, 0)),
                     replace(kept, reason="PROVEN_OPENING_OVERRIDE"),
                     replace(kept, category="PROVEN_OPENING_OPEN")]
        for index, bad in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(KPolicyIntegrityError):
                policy.validate_opening_selection(bad)

    def test_v02_kept_choice_must_be_the_k_lc1_object_itself(self):
        kept = checked(s1(140, 500, 510)[0])
        self.assertIs(kept.selected, kept.inner.selected)
        copy = replace(kept, inner=replace(kept.inner, selected=replace(kept.inner.selected)))
        with self.assertRaises(KPolicyIntegrityError) as caught:
            policy.validate_opening_selection(copy)
        self.assertEqual(caught.exception.code, "SINGLETON_BAND_SELECTION")

    def test_v03_mutable_payload_is_rejected(self):
        r = checked(s1()[0])
        a = r.applied
        for bad in (replace(r, assessments=(replace(a, failures=list(a.failures)),)),
                    replace(r, assessments=(replace(a, region=replace(a.region, cells=set(a.region.cells))),)),
                    replace(r, assessments=[a]),
                    replace(r, zero_proven=set(r.zero_proven)),
                    replace(r, baseline_reveal=replace(r.baseline_reveal,
                                                       direct=set(r.baseline_reveal.direct)))):
            with self.subTest(bad=type(bad.assessments).__name__), \
                    self.assertRaises(KPolicyIntegrityError):
                policy.validate_opening_selection(bad)

    def test_v04_validation_never_reselects_infers_generates_or_prunes(self):
        for r in (checked(s1()[0]), checked(s1(140, 500, 510)[0])):
            with patch.object(policy, "select_singleton_policy", side_effect=AssertionError("K-LC1")), \
                    patch.object(lc1, "select_policy", side_effect=AssertionError("native")), \
                    patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("inference")), \
                    patch("experiments.program_k_policy.exact_route", side_effect=AssertionError("route")), \
                    patch("experiments.program_k_policy.prune_dominated", side_effect=AssertionError("prune")), \
                    patch("experiments.program_k_policy._generate_candidates",
                          side_effect=AssertionError("generate")):
                policy.validate_opening_selection(r)

    def test_v05_existing_validators_are_not_relaxed_for_a_pruned_opening(self):
        table = load_timing_table()
        session = KLocalSession(7, 1, 1)
        evidence = session.analyze_decision(X02, status=PLAYING)
        r = policy.select_opening_policy(evidence, (0, 0), table)
        self.assertTrue(r.override_applied)
        native = r.inner.native
        self.assertNotIn(r.applied.candidate, native.survivors)
        forged = replace(native, plan=r.applied.candidate.plan, category="DIRECT_SAFE_OPEN", move=r.move)
        with self.assertRaises(KIntegrityError) as caught:
            validate_k_p0_execution(X02, r.move, status=PLAYING, num_mines=1, cursor=(0, 0),
                                    current_mines=session.M, decision=evidence, selection=forged)
        self.assertEqual(caught.exception.code, "SELECTED_PLAN")
        with self.assertRaises(KPolicyIntegrityError):
            lc1.validate_singleton_selection(replace(r.inner, selected=forged))
        # The untouched K-LC1 record and its own move still pass the old validator.
        validate_k_p0_execution(X02, r.inner.selected.move, status=PLAYING, num_mines=1, cursor=(0, 0),
                                current_mines=session.M, decision=evidence, selection=r.inner.selected)


class RealDecisionMixin:
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def decide(self, observation, mines, cursor):
        session = KLocalSession(len(observation[0]), len(observation), mines)
        evidence = session.analyze_decision(observation, status=PLAYING)
        choice = policy.select_opening_policy(evidence, cursor, self.table)
        return session, evidence, choice

    def execute(self, observation, mines, at, state, /, *, move=None, **changes):
        # Positional-only so a test can override ``cursor`` (or any argument) by keyword.
        session, evidence, choice = state
        arguments = dict(status=PLAYING, num_mines=mines, cursor=at, current_mines=session.M,
                         decision=evidence, choice=choice, table=self.table)
        arguments.update(changes)
        d2runner.validate_opening_execution(observation, choice.move if move is None else move,
                                            **arguments)


class OpeningExecutionValidationTests(RealDecisionMixin, unittest.TestCase):
    def test_e01_applied_opening_passes_against_current_observation_cursor_and_m(self):
        for observation, mines, cursor, move in ((X01, 1, (0, 1), O(2, 1)), (X02, 1, (0, 0), O(5, 0))):
            with self.subTest(cursor=cursor):
                state = self.decide(observation, mines, cursor)
                self.assertEqual(state[2].move, move)
                self.execute(observation, mines, cursor, state)

    def test_e02_stale_observation_is_rejected(self):
        state = self.decide(X02, 1, (0, 0))
        for stale in (((0, 0, 1, H, H, 0, H),), ((0, 0, 1, H, 1, H, H),), ((0, 0, 1, H, H, H, 0),)):
            with self.subTest(stale=stale), self.assertRaises(KIntegrityError) as caught:
                self.execute(stale, 1, (0, 0), state)
            self.assertEqual(caught.exception.code, "STALE_OBSERVATION")
        other = KLocalSession(7, 1, 1).analyze_decision(X02, status=PLAYING)
        with self.assertRaises(KIntegrityError) as caught:  # equal value, not this decision
            self.execute(X02, 1, (0, 0), state, decision=other)
        self.assertEqual(caught.exception.code, "OPENING_EXECUTION")

    def test_e03_cursor_mismatch_is_rejected(self):
        state = self.decide(X02, 1, (0, 0))
        with self.assertRaises(KIntegrityError) as caught:
            self.execute(X02, 1, (0, 0), state, cursor=(1, 0))
        self.assertEqual(caught.exception.code, "CURSOR_MISMATCH")

    def test_e04_current_m_mismatch_is_rejected(self):
        state = self.decide(X02, 1, (0, 0))
        for mines in (frozenset(), cells(((3, 0), (4, 0)))):
            with self.subTest(mines=mines), self.assertRaises(KIntegrityError) as caught:
                self.execute(X02, 1, (0, 0), state, current_mines=mines)
            self.assertEqual(caught.exception.code, "M_MISMATCH")

    def test_e05_target_that_is_not_hidden_is_rejected(self):
        state = self.decide(X02, 1, (0, 0))
        for current in (((0, 0, 1, H, H, F, H),), ((0, 0, 1, H, H, 0, H),)):
            with self.subTest(current=current):
                with self.assertRaises(KIntegrityError):  # the unchanged K validator sees it first
                    self.execute(current, 1, (0, 0), state)
                # The opening check alone also refuses it, with both earlier checks set aside.
                with patch.object(d2runner, "validate_opening_selection"), \
                        patch.object(d2runner, "validate_k_p0_execution"), \
                        self.assertRaises(KExecutionError) as caught:
                    self.execute(current, 1, (0, 0), state)
                self.assertEqual(caught.exception.code, "OPENING_EXECUTION")

    def test_e06_other_input_or_action_is_rejected(self):
        state = self.decide(X02, 1, (0, 0))
        for move in (O(6, 0), O(4, 0), SimpleMove(Action.FLAG, 5, 0), SimpleMove(Action.CHORD, 5, 0),
                     (Action.OPEN, 5, 0)):
            with self.subTest(move=move), self.assertRaises(KExecutionError) as caught:
                self.execute(X02, 1, (0, 0), state, move=move)
            self.assertEqual(caught.exception.code, "OPENING_EXECUTION")

    def test_e07_wrong_zero_proof_is_rejected(self):
        session, evidence, choice = state = self.decide(X02, 1, (0, 0))
        a = choice.applied
        forged_region = replace(a.region, cells=a.region.cells | {(4, 0)})
        forged = replace(choice, applied=replace(a, region=forged_region),
                         assessments=(replace(a, region=forged_region),))
        with self.assertRaises(KPolicyIntegrityError) as caught:
            self.execute(X02, 1, (0, 0), (session, evidence, forged))
        self.assertEqual(caught.exception.code, "PROVEN_OPENING_SELECTION")
        # Live re-derivation on its own, with both earlier checks set aside: a flag or a
        # current mine next to the still-HIDDEN target removes the zero proof.
        with patch.object(d2runner, "validate_opening_selection"), \
                patch.object(d2runner, "validate_k_p0_execution"):
            with self.assertRaises(KExecutionError) as caught:
                self.execute(((0, 0, 1, H, H, H, F),), 1, (0, 0), state)
            self.assertEqual(caught.exception.code, "OPENING_EXECUTION")
            with self.assertRaises(KExecutionError) as caught:
                self.execute(X02, 1, (0, 0), state, current_mines=cells(((3, 0), (6, 0))))
            self.assertEqual(caught.exception.code, "OPENING_EXECUTION")
            self.execute(X02, 1, (0, 0), state)  # the unforged state still passes this check

    def test_e08_cost_that_differs_from_the_table_is_rejected(self):
        state = self.decide(X02, 1, (0, 0))
        changed = [list(row) for row in self.table]
        changed[5][0] += 1
        for table in (changed, None):
            with self.subTest(table=table is None), self.assertRaises(KExecutionError) as caught:
                self.execute(X02, 1, (0, 0), state, table=table)
            self.assertEqual(caught.exception.code, "OPENING_EXECUTION")

    def test_e09_kept_choice_behaves_exactly_like_the_existing_validator(self):
        kept_state = ((1, H, 2, H, H),)
        session, evidence, choice = state = self.decide(kept_state, 2, (2, 0))
        self.assertEqual((choice.reason, choice.move), ("NO_PROVEN_OPENING", O(4, 0)))
        self.execute(kept_state, 2, (2, 0), state)
        validate_k_p0_execution(kept_state, choice.move, status=PLAYING, num_mines=2, cursor=(2, 0),
                                current_mines=session.M, decision=evidence, selection=choice.selected)
        for changes, code in ((dict(cursor=(0, 0)), "CURSOR_MISMATCH"),
                              (dict(current_mines=frozenset()), "M_MISMATCH"),
                              (dict(status=GameStatus.WON), "PUBLIC_STATUS")):
            with self.subTest(code=code):
                with self.assertRaises(KIntegrityError) as ours:
                    self.execute(kept_state, 2, (2, 0), state, **changes)
                arguments = dict(status=PLAYING, num_mines=2, cursor=(2, 0), current_mines=session.M,
                                 decision=evidence, selection=choice.selected)
                arguments.update(changes)
                with self.assertRaises(KIntegrityError) as theirs:
                    validate_k_p0_execution(kept_state, choice.move, **arguments)
                self.assertEqual((ours.exception.code, theirs.exception.code), (code, code))
        with self.assertRaises(KExecutionError):
            self.execute(kept_state, 2, (2, 0), state, move=O(3, 0))
        guess = self.decide(((1, H), (H, H)), 1, (0, 1))
        self.assertEqual(guess[2].reason, "EXACT_GUESS_UNCHANGED")
        self.execute(((1, H), (H, H)), 1, (0, 1), guess)


class RealDecisionPathTests(RealDecisionMixin, unittest.TestCase):
    def full_path(self, observation, mines, cursor):
        state = session, evidence, r = self.decide(observation, mines, cursor)
        policy.validate_opening_selection(r)
        lc1.validate_singleton_selection(r.inner)
        self.execute(observation, mines, cursor, state)
        self.assertIs(r.inner.native.evidence, evidence)
        self.assertEqual(r.inner.native.evidence.after.M, session.M)
        return session, r

    def test_x01_local_safe_decision_applies_through_adapter_and_validators(self):
        session, r = self.full_path(X01, 1, (0, 1))
        a = r.applied
        self.assertEqual((r.inner.native.continuation, session.M), ("LOCAL_SAFE", cells(((0, 0),))))
        self.assertEqual(r.inner.native.evidence.selection_safe_cells, cells(((2, 0), (2, 1))))
        kept = r.inner.selected
        self.assertEqual((kept.move, kept.category, kept.plan.latency_us, kept.plan.reveals),
                         (SimpleMove(Action.FLAG, 0, 0), "SETUP_CHORD", 252010, 2))
        self.assertEqual((a.region.cells, a.region.guaranteed, a.region.bound_kind),
                         (cells(((2, 0), (2, 1))), cells(((2, 0), (2, 1))), "EXACT"))
        self.assertEqual((a.target, a.candidate.plan.latency_us, r.baseline_reveal.guaranteed_count,
                          a.gain_lhs, a.gain_rhs), ((2, 1), 180604, 2, 361208, 504020))
        self.assertEqual((r.move, r.reason), (O(2, 1), "PROVEN_OPENING_OVERRIDE"))

    def test_x02_exact_safe_decision_applies_through_adapter_and_validators(self):
        session, r = self.full_path(X02, 1, (0, 0))
        a = r.applied
        self.assertEqual((r.inner.native.continuation, session.M), ("EXACT_SAFE", cells(((3, 0),))))
        self.assertEqual(r.inner.native.evidence.selection_safe_cells, cells(((4, 0), (5, 0), (6, 0))))
        self.assertEqual((r.inner.selected.move, r.inner.selected.plan.latency_us), (O(4, 0), 264580))
        self.assertEqual((a.region.cells, a.region.guaranteed, a.region.bound_kind),
                         (cells(((5, 0), (6, 0))), cells(((4, 0), (5, 0), (6, 0))), "EXACT"))
        self.assertEqual((a.target, a.candidate.plan.latency_us, r.baseline_reveal.guaranteed_count,
                          a.gain_lhs, a.gain_rhs), ((5, 0), 294552, 1, 294552, 793740))
        self.assertEqual((r.move, r.reason), (O(5, 0), "PROVEN_OPENING_OVERRIDE"))
        self.assertFalse(a.native_survivor)


class DeclaredPort:
    """Declared public prefix, not an Engine: the first input installs X02.

    The second input must be OPEN (5,0). ``faulty`` makes it reveal only its
    target as 1, which contradicts the proven guaranteed set.
    """

    width, height, num_mines, status = 7, 1, 1, PLAYING

    def __init__(self, faulty):
        self.faulty, self.inputs = faulty, []
        self.observation = ((H,) * 7,)

    def get_observation(self):
        return self.observation

    def step(self, x, y, action):
        move = SimpleMove(action, x, y)
        if not self.inputs:
            if move != O(0, 0):
                raise AssertionError("initial")
            self.observation = X02
        elif len(self.inputs) == 1:
            if move != O(5, 0):
                raise AssertionError("expected the proven opening")
            self.observation = ((0, 0, 1, H, H, 1, H),) if self.faulty else ((0, 0, 1, H, 1, 0, 0),)
        else:
            raise AssertionError("no third input is expected")
        self.inputs.append(move)


class OpeningRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def run_d2(self, width, height, mines, **kwargs):
        return d2runner.run_s3d2(fixed_engine(width, height, cells(mines)), table=self.table,
                                 capture_effects=True, **kwargs)

    def test_b01_applied_opening_that_ends_the_game(self):
        r = self.run_d2(7, 1, ((3, 0),))
        self.assertEqual((r.status, r.moves, r.total_modeled_us),
                         (GameStatus.WON, (O(0, 0), O(5, 0)), 420557))
        second = r.traces[1]
        self.assertEqual((second.choice.reason, second.choice.applied.region.bound_kind,
                          second.guarantee_status, second.action.category),
                         ("PROVEN_OPENING_OVERRIDE", "EXACT", "NOT_EVALUATED_TERMINAL",
                          "PROVEN_OPENING_OPEN"))
        self.assertIsNone(second.action.selection)
        self.assertEqual(second.choice.inner.selected.move, O(4, 0))
        self.assertEqual((r.policy_id, r.policy_definition, second.policy_id),
                         ("S3D2-A", "PROVEN_OPENING_V1", "S3D2-A"))
        k = run_k_lc1(fixed_engine(7, 1, cells(((3, 0),))), table=self.table, capture_effects=True)
        self.assertEqual((k.status, k.moves, k.total_modeled_us),
                         (GameStatus.WON, (O(0, 0), O(4, 0), O(5, 0)), 516590))

    def test_b02_applied_opening_then_play_continues_with_guarantee_check_and_guess(self):
        r = self.run_d2(8, 2, ((3, 1),))
        self.assertEqual((r.status, r.moves, r.total_modeled_us),
                         (GameStatus.WON, (O(0, 0), O(5, 0), O(3, 0)), 601161))
        second, third = r.traces[1], r.traces[2]
        a = second.choice.applied
        self.assertEqual(a.region.cells, cells((x, y) for x in (5, 6, 7) for y in (0, 1)))
        self.assertEqual((a.region.guaranteed_count, a.region.bound_kind, a.region.undetermined),
                         (8, "LOWER_BOUND", cells(((4, 0), (4, 1)))))
        self.assertEqual((second.choice.inner.selected.move, a.gain_lhs, a.gain_rhs),
                         (O(4, 0), 294552, 2116640))
        self.assertEqual((second.guarantee_status, second.action.status_after), ("PASS", PLAYING))
        self.assertEqual(second.action.public_effect.safe_cells_opened_delta, 8)
        guess = third.choice
        self.assertEqual((guess.reason, guess.applied, third.guarantee_status),
                         ("EXACT_GUESS_UNCHANGED", None, "NOT_APPLICABLE"))
        self.assertEqual((guess.inner.native.evidence.guess_target,
                          guess.inner.native.evidence.phase_e.minimum_risk), ((3, 0), Fraction(1, 2)))
        self.assertIs(third.action.selection, guess.inner.native)
        k = run_k_lc1(fixed_engine(8, 2, cells(((3, 1),))), table=self.table, capture_effects=True)
        self.assertEqual((k.status, k.moves, k.total_modeled_us),
                         (GameStatus.WON, (O(0, 0), O(4, 0), O(5, 0), O(3, 0)), 697194))

    def test_b03_loss_on_the_guess_stays_lost_without_retry(self):
        seen = []
        r = self.run_d2(8, 2, ((3, 0),), observer=seen.append)
        self.assertEqual((r.status, r.moves, r.total_modeled_us),
                         (GameStatus.LOST, (O(0, 0), O(5, 0), O(3, 0)), 601161))
        self.assertEqual((len(r.traces), tuple(seen)), (3, r.traces))
        self.assertEqual(r.traces[2].choice.reason, "EXACT_GUESS_UNCHANGED")
        self.assertIs(r.traces[2].action.status_after, GameStatus.LOST)
        won = self.run_d2(8, 2, ((3, 1),))
        # Same public observation before the guess: identical inputs, different outcome only.
        self.assertEqual(r.traces[2].choice.inner.native.evidence.observation,
                         won.traces[2].choice.inner.native.evidence.observation)

    def test_b04_initial_input_is_the_canonical_open_without_a_choice(self):
        for width, height, mines in ((7, 1, ((3, 0),)), (8, 2, ((3, 1),))):
            first = self.run_d2(width, height, mines).traces[0]
            self.assertEqual((first.action.move, first.action.category, first.choice,
                              first.guarantee_status, first.action.selection, first.action.cursor_before),
                             (O(0, 0), "POLICY_INITIAL_OPEN", None, "NOT_APPLICABLE", None, (0, 0)))
            self.assertFalse(first.action.preinput_M)

    def test_b05_one_decision_per_input_and_no_authority_after_the_input(self):
        owners = []

        class CountingSession(KLocalSession):
            def __init__(self, *args):
                super().__init__(*args)
                self.calls = []
                owners.append(self)

            def analyze_decision(self, observation, *, status):
                result = super().analyze_decision(observation, status=status)
                self.calls.append(result)
                return result

        with patch.object(d2runner, "KLocalSession", CountingSession), \
                patch.object(d2runner, "select_opening_policy",
                             wraps=policy.select_opening_policy) as select, \
                patch.object(lc1, "select_policy", wraps=lc1.select_policy) as native:
            results = [self.run_d2(8, 2, ((3, 1),)) for _ in range(2)]
        self.assertIsNot(owners[0], owners[1])
        self.assertEqual(results[0], results[1])
        decisions = sum(len(r.traces) - 1 for r in results)
        self.assertEqual((select.call_count, native.call_count), (decisions, decisions))
        for result, owner in zip(results, owners):
            self.assertEqual(len(owner.calls), len(result.traces) - 1)
            for before, after in zip(result.traces, result.traces[1:]):
                self.assertEqual(after.action.M_before, before.action.preinput_M)
                self.assertIsNot(before.choice, after.choice)
                self.assertEqual(after.action.move, after.choice.move)
                self.assertEqual(after.action.preinput_M, after.choice.inner.native.evidence.after.M)
            applied, later = result.traces[1].choice, result.traces[2].choice
            # Nothing of the old guaranteed set or its record is carried into the next decision.
            self.assertFalse(later.inner.native.evidence.selection_safe_cells
                             & applied.applied.region.guaranteed)
            self.assertNotEqual(later.inner.native.evidence.observation,
                                applied.inner.native.evidence.observation)
            self.assertIsNot(later.inner, applied.inner)

    def test_b06_game_without_an_opening_equals_k_lc1(self):
        mines = ((1, 0), (3, 0))
        r = self.run_d2(5, 1, mines)
        k = run_k_lc1(fixed_engine(5, 1, cells(mines)), table=self.table, capture_effects=True)
        self.assertEqual((r.status, r.moves, r.total_modeled_us),
                         (GameStatus.WON, (O(0, 0), O(2, 0), O(4, 0)), 487213))
        self.assertEqual(tuple(t.action for t in r.traces), tuple(t.action for t in k.traces))
        self.assertEqual(r.final_M, k.final_M)
        self.assertEqual([None if t.choice is None else t.choice.reason for t in r.traces],
                         [None, "EXACT_GUESS_UNCHANGED", "NO_PROVEN_OPENING"])
        for ours, theirs in zip(r.traces[1:], k.traces[1:]):
            self.assertEqual(ours.choice.inner, theirs.choice)
            self.assertIs(ours.action.selection, ours.choice.inner.selected)
            self.assertEqual(ours.guarantee_status, "NOT_APPLICABLE")

    def test_b07_tampered_move_is_rejected_before_the_input(self):
        port = PublicPort(fixed_engine(7, 1, cells(((3, 0),))))
        original = d2runner.select_opening_policy

        def tamper(*args):
            return replace(original(*args), move=O(6, 0))

        with patch.object(d2runner, "select_opening_policy", side_effect=tamper), \
                self.assertRaises(KIntegrityError):
            d2runner.run_s3d2(port, table=self.table)
        self.assertEqual(port.inputs, [O(0, 0)])

    def test_b08_public_state_change_after_the_decision_is_rejected_before_the_input(self):
        port = PublicPort(fixed_engine(7, 1, cells(((3, 0),))))
        original = d2runner.select_opening_policy

        def mutate(*args):
            result = original(*args)
            port.observation_fault = lambda observation: ((0, 0, 1, H, H, H, 0),)
            return result

        with patch.object(d2runner, "select_opening_policy", side_effect=mutate), \
                self.assertRaises(KIntegrityError) as caught:
            d2runner.run_s3d2(port, table=self.table)
        self.assertEqual((caught.exception.code, port.inputs), ("STALE_OBSERVATION", [O(0, 0)]))

    def test_b09_selection_error_propagates_and_is_not_replaced_by_the_k_lc1_input(self):
        for error in (KPolicyIntegrityError("PROVEN_OPENING_SELECTION", "fault"),
                      KPolicyIntegrityError("SETUP_OPEN_SURVIVED", "native fault")):
            port = PublicPort(fixed_engine(7, 1, cells(((3, 0),))))
            with patch.object(d2runner, "select_opening_policy", side_effect=error), \
                    self.assertRaises(KPolicyIntegrityError) as caught:
                d2runner.run_s3d2(port, table=self.table)
            self.assertIs(caught.exception, error)
            self.assertEqual(port.inputs, [O(0, 0)])
        port = PublicPort(fixed_engine(7, 1, cells(((3, 0),))))
        with patch.object(policy, "_evaluate", side_effect=KPolicyIntegrityError(
                "PROVEN_OPENING_SELECTION", "inner fault")), self.assertRaises(KPolicyIntegrityError):
            d2runner.run_s3d2(port, table=self.table)
        self.assertEqual(port.inputs, [O(0, 0)])

    def test_b10_guaranteed_set_that_is_not_revealed_stops_the_run(self):
        port = DeclaredPort(faulty=True)
        with self.assertRaises(KExecutionError) as caught:
            d2runner.run_s3d2(port, table=self.table)
        self.assertEqual((caught.exception.code, port.inputs), ("OPENING_GUARANTEE", [O(0, 0), O(5, 0)]))
        port, seen = DeclaredPort(faulty=False), []

        def observe(item):
            seen.append(item)
            if len(seen) == 2:
                raise RuntimeError("bounded declared prefix complete")

        with self.assertRaisesRegex(RuntimeError, "bounded declared prefix complete"):
            d2runner.run_s3d2(port, table=self.table, capture_effects=True, observer=observe)
        self.assertEqual((seen[1].guarantee_status, seen[1].choice.applied.region.bound_kind,
                          port.inputs), ("PASS", "EXACT", [O(0, 0), O(5, 0)]))

    def test_b11_terminal_status_is_read_first_and_terminal_rows_are_archive_only(self):
        for width, mines, expected in ((3, {(2, 0)}, GameStatus.WON), (2, {(0, 0)}, GameStatus.LOST)):
            port = Slice6ArchiveSentinelPort(fixed_engine(width, 1, frozenset(mines)))
            seen = []
            with patch.object(d2runner, "select_opening_policy",
                              side_effect=AssertionError("terminal analysis")):
                r = d2runner.run_s3d2(port, table=self.table, capture_effects=True,
                                      observer=seen.append)
            self.assertIs(r.status, expected)
            self.assertEqual((len(r.traces), tuple(seen)), (1, r.traces))
            self.assertEqual(port.terminal_archive_reads, [expected])
            step = next(i for i, e in enumerate(port.events) if e[0] == "step")
            self.assertEqual(port.events[step + 1], ("status", expected))
            self.assertFalse(port.forbidden_attempts)
        # An applied opening that ends the game reads no terminal row for its guarantee.
        port = Slice6ArchiveSentinelPort(fixed_engine(7, 1, cells(((3, 0),))))
        r = d2runner.run_s3d2(port, table=self.table)
        self.assertEqual((r.status, r.traces[1].guarantee_status, port.terminal_archive_reads),
                         (GameStatus.WON, "NOT_EVALUATED_TERMINAL", []))
        self.assertFalse(port.forbidden_attempts)


if __name__ == "__main__":
    unittest.main()
