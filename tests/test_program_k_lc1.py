"""Focused K-LC1 arithmetic fixtures and small public-port execution checks.

Captured fixtures are detached selection arithmetic, not new inference runs.
Synthetic ranking records intentionally do not certify native g or pruning.
No public Expert generation/execution occurs in this module.
"""

from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus
from experiments import program_k_lc1_policy as policy
from experiments import program_k_lc1_runner as runner
from experiments.program_k_capability import (
    Accounting, DecisionAnalysis, KIntegrityError, KLocalSession, LocalAnalysis,
)
from experiments.program_k_lc0_policy import apply_distance_band, validate_distance_selection
from experiments.program_k_lc0_runner import run_k_lc0
from experiments.program_k_policy import KCandidate, KPolicyIntegrityError, PolicySelection, select_policy
from experiments.program_k_runner import validate_k_p0_execution
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table
from stage3_planner import RevealPlan
from tests.test_program_k_harness import (
    PublicPort, Slice6ArchiveSentinelPort, SyntheticSetupPrefixPort, fixed_engine,
)


H, F, PLAYING = int(CellState.HIDDEN), int(CellState.FLAGGED), GameStatus.PLAYING
FIXTURE = Path(__file__).with_name("fixtures") / "program_k_lc1_singleton_native.json"


def cells(values):
    return frozenset(map(tuple, values))


def captured_native(case):
    """Rehydrate only selection premises, not omitted inference certificates."""
    def accounting(d):
        return Accounting(*(cells(d[k]) for k in ("P", "H", "M", "J", "U")), d["b"], ())
    d = case["native_evidence"]
    l = d["local"]
    local = LocalAnalysis(accounting(l["before"]), accounting(l["after"]),
                          *(cells(l[k]) for k in ("acquired_mines", "S_first", "S_second_all",
                                                 "S_new", "S_current")), ())
    assert d["phase_d"] is None and d["phase_e"] is None and not d["exact_certificates"]
    evidence = DecisionAnalysis(tuple(map(tuple, d["observation"])), d["num_mines"], local,
                                None, None, d["phase_e_status"], accounting(d["after"]), (),
                                d["continuation"], cells(d["selection_safe_cells"]), None)
    candidates = tuple(KCandidate(
        RevealPlan(tuple(SimpleMove(Action[m["action"]], m["x"], m["y"])
                         for m in c["plan"]["actions"]),
                   c["plan"]["latency_us"], c["plan"]["reveals"]),
        c["category"], cells(c["setup_cells"]), cells(c["reveal_cells"]),
    ) for c in case["candidates"])
    by_id = dict(zip((c["id"] for c in case["candidates"]), candidates))
    g = by_id[case["native_g"]]
    return PolicySelection(evidence, tuple(case["public_state"]["cursor"]), g.plan.actions[0],
                           g.plan, g.category, candidates, tuple(by_id[i] for i in case["survivors"])), by_id


def direct(latency=108, target=(1, 0)):
    return KCandidate(RevealPlan((SimpleMove(Action.OPEN, *target),), latency, 1),
                      "DIRECT_SAFE_OPEN", frozenset(), frozenset({target}))


def chord(latency=200, target=(10, 0), reveals=((10, 1), (11, 1)), flags=()):
    return KCandidate(RevealPlan(tuple(SimpleMove(Action.FLAG, *p) for p in flags)
                                 + (SimpleMove(Action.CHORD, *target),), latency, len(reveals)),
                      "SETUP_CHORD" if flags else "DIRECT_CHORD", cells(flags), cells(reveals))


def ranking_native(items=None, *, survivor_indices=None, cursor=(0, 0), extra_hidden=(),
                   mines=(), flags=(), g_index=0):
    """Public-domain-consistent arithmetic fixture, not a physical CHORD proof."""
    items = tuple(items or (chord(), direct()))
    safe = frozenset().union(*(c.reveal_cells for c in items))
    mines, flags = cells(mines), cells(flags)
    hidden = (safe | cells(extra_hidden) | mines) - flags
    observation = tuple(tuple(F if (x, y) in flags else H if (x, y) in hidden else 0
                              for x in range(30)) for y in range(4))
    account = Accounting(flags, hidden, mines, flags | mines, hidden - mines, 0, ())
    local = LocalAnalysis(account, account, frozenset(), safe, safe, frozenset(), safe, ())
    evidence = DecisionAnalysis(observation, len(mines), local, None, None, "NOT_REACHED",
                                account, (), "LOCAL_SAFE", safe, None)
    g = items[g_index]
    survivors = items if survivor_indices is None else tuple(items[i] for i in survivor_indices)
    return PolicySelection(evidence, cursor, g.plan.actions[0], g.plan, g.category, items, survivors)


class SingletonArithmeticTests(unittest.TestCase):
    def checked(self, native):
        result = policy.apply_singleton_band(native)
        policy.validate_singleton_selection(result)
        return result

    def test_in_band_selection_is_actual_k_lc0(self):
        for latency in (100, 104, 105):
            with self.subTest(latency=latency):
                native = ranking_native((chord(), direct(latency)))
                result = self.checked(native)
                self.assertEqual(result.baseline, apply_distance_band(native, control=False))
                self.assertIs(result.selected, result.baseline.selected)
                self.assertFalse(result.exception_applied)

    def test_exact_105_outside_110_boundary_and_overflow_free_large_integers(self):
        scale = 10**30
        for latency, exception in ((105*scale, False), (105*scale+1, True),
                                   (110*scale, True), (110*scale+1, False)):
            with self.subTest(latency=latency):
                r = self.checked(ranking_native((chord(200*scale), direct(latency))))
                self.assertEqual(r.exception_applied, exception)
                a = r.assessments[1]
                self.assertEqual(a.band105_lhs > a.band105_rhs, latency > 105*scale)
                self.assertEqual(a.band110_lhs <= a.band110_rhs, latency <= 110*scale)

    def test_110_is_relative_to_native_g_not_baseline(self):
        native = ranking_native((chord(), chord(208, (8, 0)), direct(112)))
        r = self.checked(native)
        self.assertEqual(r.baseline.selected.plan, native.survivors[1].plan)
        self.assertFalse(r.exception_applied)  # 112 <= 1.1 * 104 is irrelevant.

    def test_distance_tie_and_worse_keep_baseline(self):
        for target in ((0, 3), (4, 0)):
            with self.subTest(target=target):
                r = self.checked(ranking_native((chord(target=(3, 0)), direct(target=target))))
                self.assertFalse(r.exception_applied)
                self.assertIn("STRICT_DISTANCE", r.assessments[1].failures)

    def test_full_native_route_includes_setup_and_terminal(self):
        g = chord(target=(8, 0), flags=((1, 2),))
        r = self.checked(ranking_native((g, direct(target=(4, 0))), mines=((1, 2),)))
        self.assertTrue(r.exception_applied)
        self.assertLess(math.hypot(1, 2), 4)
        self.assertEqual(policy.route_distance(g.plan, (0, 0)), math.fsum((math.hypot(1, 2), math.hypot(7, 2))))

    def test_distance_is_not_rounded_or_isclose(self):
        g = chord(target=(29, 1), reveals=((28, 3), (29, 3)))
        r = self.checked(ranking_native((g, direct(target=(29, 0)))))
        self.assertEqual(round(r.assessments[0].distance), round(r.assessments[1].distance))
        self.assertTrue(r.exception_applied)

    def test_multiple_eligible_distance_then_exact_efficiency(self):
        # Assumed survivors here isolate ranking; native dominance is not re-proved.
        p, q = direct(108, (3, 0)), direct(109, (0, 2))
        self.assertEqual(self.checked(ranking_native((chord(), p, q))).selected.plan, q.plan)
        p, q = direct(108, (2, 0)), direct(107, (0, 2))
        self.assertEqual(self.checked(ranking_native((chord(), p, q))).selected.plan, q.plan)

    def test_multiple_equal_eligible_uses_frozen_tie_independent_of_tuple_order(self):
        p, q = direct(108, (2, 0)), direct(108, (0, 2))
        for items in ((chord(), p, q), (chord(), q, p)):
            self.assertEqual(self.checked(ranking_native(items)).selected.plan, p.plan)

    def test_pruned_or_never_generated_open_is_not_restored(self):
        for native in (ranking_native(survivor_indices=(0,)), ranking_native((chord(),))):
            r = self.checked(native)
            self.assertIs(r.selected, r.baseline.selected)
            self.assertEqual(len(r.assessments), 1)

    def test_chord_revealing_one_cell_is_not_singleton_open(self):
        p = chord(108, (1, 0), ((1, 1),))
        r = self.checked(ranking_native((chord(), p)))
        self.assertFalse(r.exception_applied)
        self.assertIn("DIRECT_OPEN", r.assessments[1].failures)

    def test_setup_open_surviving_is_integrity_failure(self):
        p = KCandidate(RevealPlan((SimpleMove(Action.FLAG, 1, 1), SimpleMove(Action.OPEN, 1, 0)), 108, 1),
                       "SETUP_OPEN", cells(((1, 1),)), cells(((1, 0),)))
        with self.assertRaises(KPolicyIntegrityError) as caught:
            policy.apply_singleton_band(ranking_native((chord(), p), mines=((1, 1),)))
        self.assertEqual(caught.exception.code, "SETUP_OPEN_SURVIVED")

    def test_hidden_component_includes_m_before_subtracting_productive_remainder(self):
        r = self.checked(ranking_native(mines=((1, 1),)))
        a = r.assessments[1]
        self.assertEqual(a.component, cells(((1, 0), (1, 1))))
        self.assertEqual(a.productive, cells(((1, 0),)))
        self.assertTrue(r.exception_applied)

    def test_two_productive_cells_disallow_exception(self):
        r = self.checked(ranking_native(extra_hidden=((1, 1),)))
        self.assertFalse(r.exception_applied)
        self.assertIn("SINGLETON", r.assessments[1].failures)

    def test_diagonal_hidden_neighbor_counts(self):
        r = self.checked(ranking_native(extra_hidden=((2, 1),)))
        self.assertEqual(r.assessments[1].component, cells(((1, 0), (2, 1))))
        self.assertFalse(r.exception_applied)

    def test_hidden_m_connects_but_physical_flag_does_not(self):
        arguments = dict(mines=((2, 0),), extra_hidden=((3, 0),))
        hidden = self.checked(ranking_native(**arguments))
        flagged = self.checked(ranking_native(**arguments, flags=((2, 0),)))
        self.assertFalse(hidden.exception_applied)
        self.assertTrue(flagged.exception_applied)
        self.assertEqual(flagged.native.evidence.after.M, hidden.native.evidence.after.M)

    def test_bare_physical_flag_is_not_accepted_as_logical_m(self):
        with self.assertRaises(KPolicyIntegrityError):
            policy.apply_singleton_band(ranking_native(flags=((2, 0),)))

    def test_next_state_rechecks_component_without_cache(self):
        first = self.checked(ranking_native())
        next_state = self.checked(ranking_native(extra_hidden=((2, 1),)))
        self.assertTrue(first.exception_applied)
        self.assertFalse(next_state.exception_applied)
        self.assertEqual(first.assessments[1].productive, cells(((1, 0),)))

    def test_revealed_flagged_or_new_m_target_is_not_retained(self):
        first = self.checked(ranking_native())
        for kwargs in ({}, {"mines": ((1, 0),)}, {"mines": ((1, 0),), "flags": ((1, 0),)}):
            with self.subTest(kwargs=kwargs):
                current = self.checked(ranking_native((chord(),), **kwargs))
                self.assertNotEqual(current.selected.move, first.selected.move)
                self.assertFalse(current.exception_applied)

    def test_inconsistent_safe_state_or_survivor_membership_raises(self):
        n = ranking_native()
        invalids = [replace(n, candidates=(n.candidates[0],)),
                    replace(n, survivors=n.survivors+n.survivors),
                    replace(n, move=SimpleMove(Action.OPEN, 1, 0)),
                    replace(n, failure_code="NATIVE_FAILURE")]
        bad_evidence = replace(n.evidence, selection_safe_cells=n.evidence.selection_safe_cells|{(29, 3)})
        invalids.append(replace(n, evidence=bad_evidence))
        for bad in invalids:
            with self.subTest(bad=bad.failure_code), self.assertRaises(KPolicyIntegrityError):
                policy.apply_singleton_band(bad)

    def test_validator_rejects_exception_and_baseline_tampering(self):
        r = self.checked(ranking_native())
        a = r.assessments[1]
        variants = [replace(r, selected=r.native), replace(r, reason="FAKE"),
                    replace(r, assessments=(r.assessments[0], replace(a, band110_rhs=a.band110_rhs+1))),
                    replace(r, assessments=()),
                    replace(r, baseline=replace(r.baseline, control=True)),
                    replace(r, baseline=replace(r.baseline, band=r.native.survivors)),
                    replace(r, baseline=replace(r.baseline, selected=r.selected)),
                    replace(r, baseline=replace(r.baseline, native=replace(r.native))),
                    replace(r, selected=replace(r.selected, evidence=replace(r.native.evidence))),
                    replace(r, selected=replace(r.selected, candidates=())),
                    replace(r, selected=replace(r.selected, move=r.native.move))]
        for bad in variants:
            with self.subTest(reason=bad.reason), self.assertRaises(KPolicyIntegrityError):
                policy.validate_singleton_selection(bad)

    def test_baseline_fallback_record_cannot_be_replaced_by_equivalent_copy(self):
        r = self.checked(ranking_native((chord(), direct(111))))
        with self.assertRaises(KPolicyIntegrityError):
            policy.validate_singleton_selection(replace(r, selected=replace(r.selected)))

    def test_mutable_diagnostic_payload_is_rejected(self):
        r = self.checked(ranking_native())
        a = replace(r.assessments[1], component=set(r.assessments[1].component))
        with self.assertRaises(KPolicyIntegrityError):
            policy.validate_singleton_selection(replace(r, assessments=(r.assessments[0], a)))

    def test_validation_never_reselects_infers_routes_or_reprunes(self):
        r = self.checked(ranking_native())
        with patch.object(policy, "select_policy", side_effect=AssertionError("second native")), \
                patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("inference")), \
                patch("experiments.program_k_policy.exact_route", side_effect=AssertionError("route")), \
                patch("experiments.program_k_policy.prune_dominated", side_effect=AssertionError("prune")):
            policy.validate_singleton_selection(r)

    def test_old_validator_is_not_relaxed_for_exception(self):
        r = self.checked(ranking_native())
        with self.assertRaises(KPolicyIntegrityError):
            validate_distance_selection(replace(r.baseline, selected=r.selected, reason="DISTANCE_BAND_OVERRIDE"))


class CapturedSingletonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["case_id"]: c for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]}

    def check_case(self, cid, expected_id, exception):
        case = self.cases[cid]
        native, by_id = captured_native(case)
        r = policy.apply_singleton_band(native)
        policy.validate_singleton_selection(r)
        self.assertEqual(r.baseline.selected.plan, by_id[case["baseline_b"]].plan)
        self.assertEqual(r.baseline.reason, case["baseline_reason"])
        self.assertEqual(r.selected.plan, by_id[expected_id].plan)
        self.assertEqual(r.exception_applied, exception)
        self.assertIs(r.selected.evidence, native.evidence)
        self.assertIs(r.selected.candidates, native.candidates)
        self.assertIs(r.selected.survivors, native.survivors)
        validate_k_p0_execution(native.evidence.observation, r.selected.move, status=PLAYING,
                                num_mines=native.evidence.num_mines, cursor=native.cursor,
                                current_mines=native.evidence.after.M, decision=native.evidence,
                                selection=r.selected)
        return r

    def test_lr01_keeps_original_selection(self):
        r = self.check_case("LR01", "LR01:C026", False)
        self.assertEqual(r.selected.move, SimpleMove(Action.FLAG, 11, 8))
        a = next(a for a in r.assessments if a.candidate.category == "DIRECT_SAFE_OPEN")
        self.assertIn("WITHIN_110", a.failures)

    def test_lr02_keeps_existing_distance_override(self):
        r = self.check_case("LR02", "LR02:C008", False)
        self.assertEqual(r.selected.move, SimpleMove(Action.CHORD, 3, 10))

    def test_lr03_selects_singleton_o23_0(self):
        r = self.check_case("LR03", "LR03:C000", True)
        a = next(a for a in r.assessments if a.eligible)
        self.assertEqual(r.selected.move, SimpleMove(Action.OPEN, 23, 0))
        self.assertEqual(a.component, cells(((23, 0), (23, 1))))
        self.assertEqual((a.band105_lhs, a.band105_rhs), (11583360, 11224605))
        self.assertEqual((a.band110_lhs, a.band110_rhs), (5791680, 5879555))
        self.assertEqual(a.distance, math.sqrt(5))
        self.assertEqual(Fraction(a.candidate.plan.latency_us*r.native.plan.reveals,
                                  r.native.plan.latency_us), Fraction(579168, 534505))

    def test_public_state_hashes_and_preinput_m_are_bound(self):
        for case in self.cases.values():
            encoded = json.dumps(case["public_state"], sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.assertEqual(hashlib.sha256(encoded).hexdigest(), case["public_state_sha256"])
            self.assertEqual(case["native_evidence"]["after"]["M"], case["public_state"]["preinput_M"])
            self.assertEqual(case["native_evidence"]["observation"], case["public_state"]["observation"])


class SingletonNativeAndRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_exact_guess_unchanged_and_does_not_evaluate_components(self):
        evidence = KLocalSession(2, 2, 1).analyze_decision(((1, H), (H, H)), status=PLAYING)
        with patch.object(policy, "_hidden_components", side_effect=AssertionError("guess geometry")), \
                patch.object(policy, "select_policy", wraps=select_policy) as native_call:
            r = policy.select_singleton_policy(evidence, (0, 1), self.table)
            policy.validate_singleton_selection(r)
        self.assertEqual(native_call.call_count, 1)
        self.assertIs(r.selected, r.native)
        self.assertEqual(r.selected.move, SimpleMove(Action.OPEN, *evidence.guess_target))
        self.assertFalse(r.assessments)

    def test_native_failure_is_propagated_without_fallback(self):
        error = KPolicyIntegrityError("SETUP_OPEN_SURVIVED", "sentinel")
        with patch.object(policy, "select_policy", side_effect=error), self.assertRaises(KPolicyIntegrityError) as caught:
            policy.select_singleton_policy(None, (0, 0), self.table)
        self.assertIs(caught.exception, error)

    def test_exact_safe_uses_current_pool_and_new_m(self):
        for observation, mines in ((((H, 1, H, H, H),), 1),
                                   (((H, 2, 2, H), (H, H, H, H)), 4)):
            session = KLocalSession(len(observation[0]), len(observation), mines)
            evidence = session.analyze_decision(observation, status=PLAYING)
            result = policy.select_singleton_policy(evidence, (0, 0), self.table)
            policy.validate_singleton_selection(result)
            self.assertEqual(result.native.continuation, "EXACT_SAFE")
            self.assertEqual(result.native.evidence.after.M, session.M)
            validate_k_p0_execution(observation, result.selected.move, status=PLAYING,
                                    num_mines=mines, cursor=(0, 0), current_mines=session.M,
                                    decision=evidence, selection=result.selected)

    def test_runner_enters_guess_after_initial_without_exception(self):
        r = runner.run_k_lc1(fixed_engine(2, 2, cells(((1, 0),))), table=self.table,
                             capture_effects=True)
        self.assertEqual(len(r.traces), 2)
        self.assertIs(r.status, GameStatus.LOST)
        choice = r.traces[1].choice
        self.assertEqual(choice.reason, "EXACT_GUESS_UNCHANGED")
        self.assertIs(choice.selected, choice.native)
        self.assertFalse(choice.assessments)
        self.assertEqual(choice.native.evidence.phase_e.minimum_risk, Fraction(1, 3))

    def test_small_synthetic_prefix_executes_exception_then_fresh_replans(self):
        # Like SyntheticSetupPrefixPort, the first input installs a declared
        # public premise; it is not an assertion about an Engine's initial flood.
        # Subsequent OPEN/FLAG changes are real one-cell public input effects.
        class PrefixPort:
            width, height, num_mines, status = 6, 14, 2, PLAYING
            def __init__(self):
                self.inputs = []
                self.observation = ((H,)*self.width,)*self.height
            def get_observation(self):
                return self.observation
            def step(self, x, y, action):
                move = SimpleMove(action, x, y)
                if not self.inputs:
                    if move != SimpleMove(Action.OPEN, 0, 0):
                        raise AssertionError("initial")
                    mines = {(2, 2), (0, 11)}
                    hidden = mines | {(2, 1), (0, 10), (1, 10), (2, 10)}
                    self.observation = tuple(tuple(H if (cx, cy) in hidden else
                        sum(abs(mx-cx)<=1 and abs(my-cy)<=1 for mx, my in mines)
                        for cx in range(self.width)) for cy in range(self.height))
                else:
                    if self.observation[y][x] != H:
                        raise AssertionError("stale target")
                    if action is Action.OPEN and (x, y) != (2, 1):
                        raise AssertionError("exception should be first")
                    if action is Action.FLAG and (x, y) != (0, 11):
                        raise AssertionError("expected fresh baseline setup")
                    value = 1 if action is Action.OPEN else F
                    self.observation = tuple(tuple(value if (cx, cy)==(x, y) else old
                        for cx, old in enumerate(row)) for cy, row in enumerate(self.observation))
                self.inputs.append(move)
        port, seen = PrefixPort(), []
        def observe(record):
            seen.append(record)
            if len(seen) == 3:
                raise RuntimeError("bounded synthetic prefix complete")
        with self.assertRaisesRegex(RuntimeError, "bounded synthetic prefix complete"):
            runner.run_k_lc1(port, table=self.table, capture_effects=True, observer=observe)
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0),
                                      SimpleMove(Action.OPEN, 2, 1), SimpleMove(Action.FLAG, 0, 11)])
        self.assertTrue(seen[1].choice.exception_applied)
        self.assertEqual(seen[1].choice.baseline.selected.move, SimpleMove(Action.FLAG, 0, 11))
        self.assertEqual(seen[1].action.preinput_M, cells(((2, 2), (0, 11))))
        self.assertFalse(seen[2].choice.exception_applied)
        self.assertNotIn((2, 1), seen[2].choice.native.evidence.selection_safe_cells)
        self.assertEqual(seen[2].action.M_before, seen[1].action.preinput_M)
        self.assertEqual(seen[1].action.public_effect.explicit_flag_delta, 0)
        self.assertEqual(seen[2].action.public_effect.explicit_flag_delta, 1)

    def test_once_per_input_fresh_session_m_and_first_only(self):
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
        with patch.object(runner, "KLocalSession", CountingSession), \
                patch.object(policy, "select_policy", wraps=select_policy) as native_call:
            results = [runner.run_k_lc1(fixed_engine(5, 4, cells(((1, 2), (3, 2)))),
                                       table=self.table, capture_effects=True) for _ in range(2)]
        self.assertIsNot(owners[0], owners[1])
        self.assertEqual(results[0], results[1])
        self.assertEqual(native_call.call_count, sum(len(r.traces)-1 for r in results))
        for result, owner in zip(results, owners):
            self.assertEqual(len(owner.calls), len(result.traces)-1)
            self.assertEqual(result.policy_id, "K-LC1")
            self.assertEqual(result.policy_definition, "SINGLETON_BAND_V1")
            self.assertEqual(result.moves[0], SimpleMove(Action.OPEN, 0, 0))
            self.assertIsNone(result.traces[0].choice)
            self.assertFalse(result.traces[0].action.preinput_M)
            self.assertTrue(any(t.action.move.action is Action.FLAG for t in result.traces))
            for before, after in zip(result.traces, result.traces[1:]):
                self.assertEqual(after.action.M_before, before.action.preinput_M)
                self.assertIsNot(before.choice, after.choice)
                self.assertEqual(after.action.move, after.choice.selected.move)
                self.assertEqual(after.action.preinput_M, after.choice.native.evidence.after.M)
            for t in result.traces:
                self.assertEqual(t.policy_id, "K-LC1")
                a = t.action
                self.assertEqual(a.modeled_action_us, action_cost(self.table, a.cursor_before, (a.move.x, a.move.y)))
                self.assertEqual(a.public_effect.modeled_action_us, a.modeled_action_us)
            self.assertEqual(result.total_modeled_us, sum(t.action.modeled_action_us for t in result.traces))

    def test_small_run_baseline_fallback_matches_actual_lc0(self):
        mines = cells(((1, 2), (3, 2)))
        baseline = run_k_lc0(fixed_engine(5, 4, mines), table=self.table, capture_effects=True)
        result = runner.run_k_lc1(fixed_engine(5, 4, mines), table=self.table, capture_effects=True)
        self.assertFalse(any(t.choice and t.choice.exception_applied for t in result.traces))
        self.assertEqual(tuple(t.action for t in result.traces), tuple(t.action for t in baseline.traces))
        self.assertEqual(result.final_M, baseline.final_M)

    def test_terminal_status_first_and_archive_only_no_gui(self):
        for width, mines, expected in ((3, {(2, 0)}, GameStatus.WON), (2, {(0, 0)}, GameStatus.LOST)):
            port = Slice6ArchiveSentinelPort(fixed_engine(width, 1, frozenset(mines)))
            seen = []
            with patch.object(runner, "select_singleton_policy", side_effect=AssertionError("terminal analysis")):
                r = runner.run_k_lc1(port, table=self.table, capture_effects=True, observer=seen.append)
            self.assertIs(r.status, expected)
            self.assertEqual(len(r.traces), 1)
            self.assertEqual(tuple(seen), r.traces)
            self.assertEqual(port.terminal_archive_reads, [expected])
            step = next(i for i, e in enumerate(port.events) if e[0] == "step")
            self.assertEqual(port.events[step+1], ("status", expected))
            self.assertFalse(port.forbidden_attempts)

    def test_progressed_or_terminal_start_rejected(self):
        for engine in (fixed_engine(), fixed_engine(2, 1, cells(((0, 0),)))):
            engine.step(0, 0, Action.OPEN)
            with self.assertRaises(KIntegrityError):
                runner.run_k_lc1(PublicPort(engine), table=self.table)

    def test_current_state_mutation_rejected_before_second_input(self):
        port = PublicPort(fixed_engine())
        original = runner.select_singleton_policy
        def mutate(*args):
            result = original(*args)
            port.observation_fault = lambda observation: ((H, H, H, H),)
            return result
        with patch.object(runner, "select_singleton_policy", side_effect=mutate), self.assertRaises(KIntegrityError):
            runner.run_k_lc1(port, table=self.table)
        self.assertEqual(len(port.inputs), 1)

    def test_tampered_first_move_rejected_before_input(self):
        port = PublicPort(fixed_engine())
        original = runner.select_singleton_policy
        def tamper(*args):
            result = original(*args)
            return replace(result, selected=replace(result.selected, move=SimpleMove(Action.OPEN, 0, 0)))
        with patch.object(runner, "select_singleton_policy", side_effect=tamper), self.assertRaises(KIntegrityError):
            runner.run_k_lc1(port, table=self.table)
        self.assertEqual(len(port.inputs), 1)

    def test_multi_flag_suffix_expires_on_next_analysis_failure(self):
        port = SyntheticSetupPrefixPort()
        class FailSecond(KLocalSession):
            def analyze_decision(self, observation, *, status):
                if len(port.inputs) >= 2:
                    raise RuntimeError("fresh failure")
                return super().analyze_decision(observation, status=status)
        seen = []
        with patch.object(runner, "KLocalSession", FailSecond), self.assertRaisesRegex(RuntimeError, "fresh failure"):
            runner.run_k_lc1(port, table=self.table, observer=seen.append)
        self.assertEqual(len(port.inputs), 2)
        self.assertGreaterEqual(len(seen[-1].choice.selected.plan.actions), 3)
        self.assertIs(port.inputs[-1].action, Action.FLAG)

    def test_native_failure_and_no_progress_do_not_retry(self):
        port = PublicPort(fixed_engine())
        with patch.object(runner, "select_singleton_policy", side_effect=KPolicyIntegrityError("NATIVE", "fault")), \
                self.assertRaises(KPolicyIntegrityError):
            runner.run_k_lc1(port, table=self.table)
        self.assertEqual(len(port.inputs), 1)
        class Stuck(PublicPort):
            def step(self, x, y, action):
                self.inputs.append(SimpleMove(action, x, y))
        port = Stuck(fixed_engine())
        with self.assertRaises(KIntegrityError):
            runner.run_k_lc1(port, table=self.table)
        self.assertEqual(len(port.inputs), 1)


if __name__ == "__main__":
    unittest.main()
