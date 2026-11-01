"""Focused distance selection and tiny public-port fixtures; no Expert runs.

The checked-in capture fixture contains stored native candidates only, never
terminal truth. Same-state tests do arithmetic, not a replay or new inference.
Fault injection patches this experimental module's bindings, not frozen globals.
"""

from dataclasses import replace
from fractions import Fraction
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus
from experiments import program_k_lc0_policy as policy
from experiments import program_k_lc0_runner as runner
from experiments.program_k_capability import KIntegrityError, KLocalSession
from experiments.program_k_policy import (
    KCandidate, KPolicyIntegrityError, PolicySelection, _select_candidates, select_policy,
)
from experiments.program_k_runner import run_k_p0, validate_k_p0_execution
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table
from stage3_planner import RevealPlan
from tests.test_program_k_harness import (
    PublicPort, Slice6ArchiveSentinelPort, SyntheticSetupPrefixPort, fixed_engine,
)


H = int(CellState.HIDDEN)
PLAYING = GameStatus.PLAYING
FIXTURE = Path(__file__).with_name("fixtures") / "program_k_lc0_native_candidates.json"


def candidate(latency, reveals, target, flags=(), action=Action.CHORD):
    actions = tuple(SimpleMove(Action.FLAG, *p) for p in flags) + (SimpleMove(action, *target),)
    category = "SETUP_CHORD" if flags else "DIRECT_CHORD"
    if action is Action.OPEN:
        category = "SETUP_OPEN" if flags else "DIRECT_SAFE_OPEN"
    return KCandidate(RevealPlan(actions, latency, reveals), category,
                      frozenset(flags), frozenset({target}))


def rank_only_native(items, cursor=(0, 0)):
    # This sentinel is ONLY for detached ranking arithmetic, not execution.
    return _select_candidates(SimpleNamespace(continuation="LOCAL_SAFE"), cursor, tuple(items))


def captured_native(case):
    candidates = tuple(KCandidate(
        RevealPlan(tuple(SimpleMove(Action[m[0]], m[1], m[2]) for m in c["actions"]),
                   c["L"], c["R"]), c["category"],
        frozenset(map(tuple, c["setup"])), frozenset(map(tuple, c["reveals"])),
    ) for c in case["candidates"])
    by_id = dict(zip((c["id"] for c in case["candidates"]), candidates))
    g = by_id[case["g"]]
    return PolicySelection(SimpleNamespace(continuation=case["phase"]), tuple(case["cursor"]),
                           g.plan.actions[0], g.plan, g.category, candidates,
                           tuple(by_id[i] for i in case["survivors"]))


class DistancePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_exact_band_inside_boundary_outside(self):
        for latency, expected in ((104, True), (105, True), (106, False)):
            g, p = candidate(200, 2, (8, 0)), candidate(latency, 1, (1, 0))
            native = rank_only_native((g, p))
            result = policy.apply_distance_band(native)
            self.assertEqual(p in result.band, expected)
            self.assertEqual(result.selected.plan, (p if expected else g).plan)
            policy.validate_distance_selection(result)

    def test_large_integer_band_does_not_round_float(self):
        scale = 10**30
        g = candidate(20 * scale, 1, (8, 0)).plan
        self.assertTrue(policy.in_distance_band(candidate(21 * scale, 1, (1, 0)).plan, g))
        self.assertFalse(policy.in_distance_band(candidate(21 * scale + 1, 1, (1, 0)).plan, g))

    def test_equal_efficiency_prefers_distance(self):
        a, b = candidate(100, 1, (8, 0)), candidate(200, 2, (1, 0))
        native = rank_only_native((a, b))
        self.assertEqual(native.plan, a.plan)
        self.assertEqual(policy.apply_distance_band(native).selected.plan, b.plan)

    def test_equal_distance_uses_exact_efficiency_before_latency(self):
        a, b = candidate(100, 1, (1, 0)), candidate(198, 2, (0, 1))
        self.assertEqual(policy.apply_distance_band(rank_only_native((a, b))).selected.plan, b.plan)

    def test_equal_distance_equal_efficiency_uses_latency(self):
        a, b = candidate(100, 1, (1, 0)), candidate(200, 2, (0, 1))
        self.assertEqual(policy.apply_distance_band(rank_only_native((b, a))).selected.plan, a.plan)

    def test_equal_distance_uses_frozen_terminal_reading_order(self):
        a, b = candidate(100, 1, (1, 0)), candidate(100, 1, (0, 1))
        self.assertEqual(policy.apply_distance_band(rank_only_native((b, a))).selected.plan, a.plan)

    def test_equal_distance_uses_frozen_action_rank_and_setup_key(self):
        a = candidate(100, 1, (2, 2), action=Action.OPEN)
        b = candidate(100, 1, (2, 2))
        self.assertEqual(policy.apply_distance_band(rank_only_native((b, a))).selected.plan, a.plan)
        a = candidate(100, 1, (2, 2), ((1, 0), (0, 1)))
        b = candidate(100, 1, (2, 2), ((0, 1), (1, 0)))
        self.assertEqual(policy.route_distance(a.plan, (0, 0)), policy.route_distance(b.plan, (0, 0)))
        self.assertEqual(policy.apply_distance_band(rank_only_native((b, a))).selected.plan, a.plan)

    def test_display_rounding_never_enters_selection(self):
        g, p = candidate(200, 2, (10, 1)), candidate(105, 1, (10, 0))
        self.assertEqual(round(policy.route_distance(g.plan, (0, 0)), 0),
                         round(policy.route_distance(p.plan, (0, 0)), 0))
        self.assertEqual(policy.apply_distance_band(rank_only_native((g, p))).selected.plan, p.plan)

    def test_full_route_includes_multiple_flags_and_terminal(self):
        p = candidate(100, 1, (3, 4), ((3, 0), (0, 0)))
        self.assertEqual(policy.route_distance(p.plan, (0, 0)), 11.0)
        self.assertEqual(tuple((m.x, m.y) for m in p.plan.actions), ((3, 0), (0, 0), (3, 4)))

    def test_close_first_input_does_not_beat_shorter_full_route(self):
        g = candidate(200, 2, (8, 0), ((1, 0),))
        p = candidate(105, 1, (3, 0), ((2, 0),))
        self.assertLess(math.hypot(1, 0), math.hypot(2, 0))
        self.assertEqual(policy.apply_distance_band(rank_only_native((g, p))).selected.plan, p.plan)

    def test_pruned_shorter_candidate_is_not_revived(self):
        g, removed = candidate(100, 1, (5, 0)), candidate(105, 1, (1, 0))
        native = rank_only_native((g, removed))
        result = policy.apply_distance_band(native)
        self.assertTrue(policy.in_distance_band(removed.plan, g.plan))
        self.assertNotIn(removed, result.band)
        self.assertEqual(result.selected.plan, g.plan)

    def test_adapter_calls_native_once_and_preserves_input_graph(self):
        owner = KLocalSession(4, 2, 1)
        evidence = owner.analyze_decision(((1, H, 1, H), (1, 1, 1, H)), status=PLAYING)
        with patch.object(policy, "select_policy", wraps=select_policy) as native_call:
            result = policy.select_distance_policy(evidence, (0, 0), self.table)
            policy.validate_distance_selection(result)
        self.assertEqual(native_call.call_count, 1)
        self.assertIs(result.selected.evidence, evidence)
        self.assertIs(result.selected.candidates, result.native.candidates)
        self.assertIs(result.selected.survivors, result.native.survivors)
        self.assertEqual(owner.M, evidence.after.M)

    def test_exact_guess_risk_target_no_setup_unchanged(self):
        evidence = KLocalSession(2, 2, 1).analyze_decision(((1, H), (H, H)), status=PLAYING)
        for control in (False, True):
            result = policy.select_distance_policy(evidence, (0, 1), self.table, control=control)
            self.assertEqual(evidence.continuation, "EXACT_GUESS")
            self.assertIs(result.selected, result.native)
            self.assertEqual(result.selected.move, SimpleMove(Action.OPEN, *evidence.guess_target))
            self.assertFalse(result.band)
            policy.validate_distance_selection(result)

    def test_native_integrity_failure_propagates(self):
        invalid = candidate(1, 1, (3, 0), ((1, 0),), action=Action.OPEN)
        with self.assertRaises(KPolicyIntegrityError) as context:
            rank_only_native((invalid,))
        self.assertEqual(context.exception.code, "SETUP_OPEN_SURVIVED")
        with patch.object(policy, "select_policy", side_effect=context.exception):
            with self.assertRaises(KPolicyIntegrityError) as propagated:
                policy.select_distance_policy(None, (0, 0), self.table)
        self.assertIs(propagated.exception, context.exception)

    def test_control_uses_native_g_and_explicit_identity(self):
        native = rank_only_native((candidate(200, 2, (8, 0)), candidate(105, 1, (1, 0))))
        result = policy.apply_distance_band(native, control=True)
        self.assertIs(result.selected, native)
        self.assertEqual(result.policy_id, "K-LC0-CONTROL")
        self.assertEqual(policy.apply_distance_band(native).policy_id, "K-LC0")
        policy.validate_distance_selection(result)

    def test_new_validator_rejects_wrong_ranking_even_if_native_plan_is_safe(self):
        native = rank_only_native((candidate(200, 2, (8, 0)), candidate(105, 1, (1, 0))))
        result = policy.apply_distance_band(native)
        with self.assertRaises(KPolicyIntegrityError):
            policy.validate_distance_selection(replace(result, selected=native, reason="NATIVE_G_RETAINED"))

    def test_new_validator_rejects_outside_band_and_graph_changes(self):
        native = rank_only_native((candidate(200, 2, (8, 0)), candidate(106, 1, (1, 0))))
        result = policy.apply_distance_band(native)
        outside = native.survivors[1]
        for bad in (
            replace(result, band=native.survivors),
            replace(result, selected=replace(native, plan=outside.plan, move=outside.plan.actions[0])),
            replace(result, selected=replace(native, candidates=())),
            replace(result, selected=replace(native, cursor=(1, 1))),
            replace(result, reason="FAKE"),
        ):
            with self.subTest(bad=bad.reason), self.assertRaises(KPolicyIntegrityError):
                policy.validate_distance_selection(bad)

    def test_native_execution_validation_binds_observation_m_cursor_and_decision(self):
        observation = ((1, H, 1, H),)
        evidence = KLocalSession(4, 1, 1).analyze_decision(observation, status=PLAYING)
        result = policy.select_distance_policy(evidence, (0, 0), self.table)
        kwargs = dict(status=PLAYING, num_mines=1, cursor=(0, 0), current_mines=evidence.after.M,
                      decision=evidence, selection=result.selected)
        validate_k_p0_execution(observation, result.selected.move, **kwargs)
        for changed in ({"cursor": (1, 0)}, {"current_mines": frozenset()},
                        {"decision": replace(evidence)}, {"status": GameStatus.WON}):
            with self.subTest(changed=changed), self.assertRaises(KIntegrityError):
                validate_k_p0_execution(observation, result.selected.move, **(kwargs | changed))
        with self.assertRaises(KIntegrityError):
            validate_k_p0_execution(((1, H, H, H),), result.selected.move, **kwargs)


class CapturedSameStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def check_case(self, name, actions, latency, reveals, band_size):
        case = next(c for c in self.fixture["cases"] if c["case"] == name)
        native = captured_native(case)
        result = policy.apply_distance_band(native)
        selected = result.selected.plan
        self.assertEqual([(m.action.name, m.x, m.y) for m in selected.actions], actions)
        self.assertEqual((selected.latency_us, selected.reveals), (latency, reveals))
        self.assertEqual(len(result.band), band_size)
        # Independent oracle: Fraction band, explicit segment sum and frozen key.
        def key(c):
            p = c.plan
            points = (native.cursor,) + tuple((m.x, m.y) for m in p.actions)
            d = math.fsum(math.hypot(x2-x1, y2-y1) for (x1,y1),(x2,y2) in zip(points, points[1:]))
            end = p.actions[-1]
            rank = {Action.OPEN: 0, Action.FLAG: 1, Action.CHORD: 2}
            return (d, Fraction(p.latency_us, p.reveals), p.latency_us,
                    (end.y, end.x, rank[end.action], tuple((m.y,m.x) for m in p.actions[:-1])))
        band = tuple(c for c in native.survivors if Fraction(c.plan.latency_us, c.plan.reveals)
                     <= Fraction(21,20) * Fraction(native.plan.latency_us, native.plan.reveals))
        self.assertEqual(selected, min(band, key=key).plan)
        self.assertIs(result.selected.evidence, native.evidence)
        self.assertIs(result.selected.candidates, native.candidates)
        self.assertIs(result.selected.survivors, native.survivors)
        policy.validate_distance_selection(result)
        return result

    def test_lc01_97_input72(self):
        result = self.check_case("LC01", [("CHORD",13,5)], 126005, 1, 2)
        self.assertEqual(policy.route_distance(result.selected.plan, (13,6)), 1.0)
        self.assertAlmostEqual(policy.route_distance(result.native.plan, (13,6)), 8.6943234517)

    def test_lc02_2026_input51(self):
        result = self.check_case("LC02", [("FLAG",11,9),("CHORD",10,9)], 319061, 3, 2)
        self.assertAlmostEqual(policy.route_distance(result.selected.plan, (9,8)), 3.2360679775)

    def test_lc03_97_input22_stays(self):
        self.assertFalse(self.check_case("LC03", [("FLAG",7,6),("CHORD",7,7)], 483709, 3, 1).overridden)

    def test_lc06_97_input43_stays(self):
        self.assertFalse(self.check_case("LC06", [("FLAG",14,8),("CHORD",13,8)], 420557, 3, 1).overridden)


class DistanceRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_once_per_input_first_only_and_fresh_sessions(self):
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
                patch.object(policy, "select_policy", wraps=select_policy) as select:
            results = [runner.run_k_lc0(PublicPort(fixed_engine(5,4,frozenset({(1,2),(3,2)}))),
                                       table=self.table) for _ in range(2)]
        self.assertIsNot(owners[0], owners[1])
        self.assertEqual(select.call_count, sum(len(r.traces)-1 for r in results))
        self.assertEqual(results[0], results[1])
        for result, owner in zip(results, owners):
            self.assertEqual(len(owner.calls), len(result.traces)-1)
            self.assertTrue(any(t.action.move.action is Action.FLAG for t in result.traces))
            self.assertEqual(result.traces[0].action.preinput_M, frozenset())
            for previous, fresh in zip(result.traces, result.traces[1:]):
                self.assertEqual(fresh.action.M_before, previous.action.preinput_M)
                self.assertIsNot(fresh.choice, previous.choice)
                self.assertEqual(fresh.action.move, fresh.choice.selected.plan.actions[0]
                                 if fresh.choice.selected.plan else fresh.choice.selected.move)

    def test_control_reproduces_native_tiny_run_and_public_effects(self):
        baseline = run_k_p0(fixed_engine(5,4,frozenset({(1,2),(3,2)})), table=self.table, capture_effects=True)
        control = runner.run_k_lc0(fixed_engine(5,4,frozenset({(1,2),(3,2)})), table=self.table,
                                  control=True, capture_effects=True)
        self.assertEqual(tuple(t.action for t in control.traces), baseline.traces)
        self.assertEqual(control.total_modeled_us, baseline.total_modeled_us)
        self.assertEqual(control.final_M, baseline.final_M)
        self.assertEqual(control.policy_id, "K-LC0-CONTROL")

    def test_terminal_status_first_and_archival_lane_only(self):
        for width, mines, expected in ((3,{(2,0)},GameStatus.WON),(2,{(0,0)},GameStatus.LOST)):
            port = Slice6ArchiveSentinelPort(fixed_engine(width,1,frozenset(mines)))
            with patch.object(runner, "select_distance_policy", side_effect=AssertionError("terminal analysis")):
                result = runner.run_k_lc0(port, table=self.table, capture_effects=True)
            self.assertIs(result.status, expected)
            self.assertEqual(len(result.traces), 1)
            self.assertEqual(result.final_M, frozenset())
            self.assertEqual(port.terminal_archive_reads, [expected])
            step = next(i for i,e in enumerate(port.events) if e[0] == "step")
            self.assertEqual(port.events[step+1], ("status", expected))
            self.assertFalse(port.forbidden_attempts)

    def test_progressed_or_terminal_start_rejected(self):
        engine = fixed_engine()
        engine.step(0,0,Action.OPEN)
        with self.assertRaises(KIntegrityError):
            runner.run_k_lc0(PublicPort(engine), table=self.table)
        terminal = fixed_engine(2,1,frozenset({(0,0)}))
        terminal.step(0,0,Action.OPEN)
        with self.assertRaises(KIntegrityError):
            runner.run_k_lc0(PublicPort(terminal), table=self.table)

    def test_current_public_mutation_is_caught_before_input(self):
        port = PublicPort(fixed_engine())
        original = runner.select_distance_policy
        def choose(*args, **kwargs):
            result = original(*args, **kwargs)
            port.observation_fault = lambda observation: ((H,H,H,H),)
            return result
        with patch.object(runner, "select_distance_policy", side_effect=choose):
            with self.assertRaises(KIntegrityError) as caught:
                runner.run_k_lc0(port, table=self.table)
        self.assertEqual(caught.exception.code, "STALE_OBSERVATION")
        self.assertEqual(len(port.inputs), 1)

    def test_multi_flag_suffix_expires_on_fresh_analysis_failure(self):
        port = SyntheticSetupPrefixPort()
        class FailSecondAnalysis(KLocalSession):
            def analyze_decision(self, observation, *, status):
                if len(port.inputs) >= 2:
                    raise RuntimeError("fresh analysis failure")
                return super().analyze_decision(observation, status=status)
        records = []
        with patch.object(runner, "KLocalSession", FailSecondAnalysis):
            with self.assertRaisesRegex(RuntimeError, "fresh analysis failure"):
                runner.run_k_lc0(port, table=self.table, observer=records.append)
        self.assertEqual(len(port.inputs), 2)
        self.assertGreaterEqual(len(records[-1].choice.selected.plan.actions), 3)
        self.assertIs(port.inputs[-1].action, Action.FLAG)

    def test_model_c_charges_only_actual_first_input(self):
        result = runner.run_k_lc0(fixed_engine(5,4,frozenset({(1,2),(3,2)})), table=self.table)
        for record in result.traces:
            trace = record.action
            self.assertEqual(trace.modeled_action_us,
                             action_cost(self.table, trace.cursor_before, (trace.move.x,trace.move.y)))
            if trace.category == "SETUP_CHORD":
                self.assertLess(trace.modeled_action_us, trace.selection.plan.latency_us)
        self.assertEqual(result.total_modeled_us, sum(t.action.modeled_action_us for t in result.traces))

    def test_no_progress_and_policy_failure_do_not_retry(self):
        class StuckPort(PublicPort):
            def step(self, x, y, action):
                self.inputs.append(SimpleMove(action,x,y))
        port = StuckPort(fixed_engine())
        with self.assertRaises(KIntegrityError) as caught:
            runner.run_k_lc0(port, table=self.table)
        self.assertEqual(caught.exception.code, "NO_PROGRESS")
        self.assertEqual(len(port.inputs), 1)
        port = PublicPort(fixed_engine())
        with patch.object(runner, "select_distance_policy", side_effect=KPolicyIntegrityError("SETUP_OPEN_SURVIVED", "fault")):
            with self.assertRaises(KPolicyIntegrityError):
                runner.run_k_lc0(port, table=self.table)
        self.assertEqual(len(port.inputs), 1)


if __name__ == "__main__":
    unittest.main()
