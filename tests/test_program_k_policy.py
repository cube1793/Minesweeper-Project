"""Slice-3 implementation/unit verification only; no P-8 or E0 qualification.

Fixtures are declared public observations, including explicit public flag-prefix
states supplied to one K owner. No Engine input, hidden layout, complete game,
future observation construction, research evidence, or timing-table scan runs.
The private candidate seams exercise malformed/synthetic unit faults without
weakening authentication at the public policy entry point. Live freshness,
session/status binding and physical execution validation belong to the runner.
"""

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import inspect
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus
from experiments import program_k_policy as policy
from experiments.program_k_capability import KIntegrityError, KLocalSession
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table
from stage3_planner import RevealPlan, exact_route, prune_dominated, select_reveal_plan


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
HISTORICAL = ((1, H, 1, H),)
ONE_SETUP = ((1, H, 1, H), (1, 1, 1, H))
FLAGGED_PREFIX = ((1, F, 1, H), (1, 1, 1, H))

# Public literals from tests/test_stage3_planner.py. The outside clues certify
# the setup identities; no answer layout is supplied or reconstructed here.
SEVEN_SETUP = (
    (1, 2, 3, 2, 1),
    (2, H, H, H, 2),
    (3, H, 7, H, 2),
    (2, H, H, H, 1),
    (1, 2, 2, 1, 0),
)
TWO_SETUP_WITH_UNRELATED_MINE = (
    (1, 1, 2, 1, 1, 0, 0),
    (1, H, 2, H, 1, 1, 1),
    (1, 1, 2, 1, 1, 1, H),
    (0, 0, H, 0, 0, 1, 1),
    (0, 0, 0, 0, 0, 0, 0),
)


def decision(observation, mines):
    """Build accepted detached K evidence from a declared current public state."""
    return KLocalSession(len(observation[0]), len(observation), mines).analyze_decision(
        observation, status=GameStatus.PLAYING,
    )


def flagged_decision():
    owner = KLocalSession(4, 2, 1)
    owner.analyze_decision(ONE_SETUP, status=GameStatus.PLAYING)
    return owner.analyze_decision(FLAGGED_PREFIX, status=GameStatus.PLAYING)


def synthetic_candidate(latency, reveals, target, *, flags=(), action=Action.CHORD):
    """Explicit ranking-only input; not claimed to be an accepted board plan."""
    actions = tuple(SimpleMove(Action.FLAG, *cell) for cell in flags)
    plan = RevealPlan(actions + (SimpleMove(action, *target),), latency, reveals)
    category = "SETUP_CHORD" if flags else "DIRECT_CHORD"
    if action == Action.OPEN:
        category = "SETUP_OPEN" if flags else "DIRECT_SAFE_OPEN"
    return policy.KCandidate(plan, category, frozenset(flags), frozenset({target}))


class ProgramKPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def select(self, observation, mines, cursor=(0, 0), **kwargs):
        return policy.select_policy(decision(observation, mines), cursor, self.table, **kwargs)

    def test_a_historical_k_safe_open_requires_no_physical_flag(self):
        result = self.select(HISTORICAL, 1)

        self.assertEqual(result.evidence.after.M, {(1, 0)})
        self.assertEqual(result.evidence.after.P, frozenset())
        self.assertEqual(result.evidence.selection_safe_cells, {(3, 0)})
        self.assertEqual(result.continuation, "LOCAL_SAFE")
        self.assertEqual(result.category, "DIRECT_SAFE_OPEN")
        self.assertEqual(result.move, SimpleMove(Action.OPEN, 3, 0))
        self.assertEqual(result.plan.actions, (result.move,))
        self.assertEqual(result.plan.reveals, 1)
        self.assertIsNone(result.failure_code)

    def test_b_every_safe_has_direct_open_with_exact_cost_and_deterministic_tie(self):
        result = self.select(((0, H, H, 0),), 0, (1, 0))
        direct = tuple(c for c in result.candidates if c.category == "DIRECT_SAFE_OPEN")

        self.assertEqual({c.reveal_cells for c in direct},
                         {frozenset({(1, 0)}), frozenset({(2, 0)})})
        self.assertEqual(len(direct), 2)
        for candidate in direct:
            terminal = candidate.plan.actions[-1]
            self.assertEqual(candidate.setup_cells, frozenset())
            self.assertEqual(candidate.plan.actions, (terminal,))
            self.assertEqual(candidate.plan.reveals, 1)
            self.assertEqual(candidate.plan.latency_us,
                             action_cost(self.table, (1, 0), (terminal.x, terminal.y)))
        self.assertEqual({c.plan.latency_us for c in direct}, {126005})
        self.assertEqual(result.move, SimpleMove(Action.OPEN, 1, 0))

    def test_c_direct_chord_uses_actual_physical_flags_and_current_safe_neighbors(self):
        evidence = flagged_decision()
        result = policy.select_policy(evidence, (0, 0), self.table)
        chords = tuple(c for c in result.candidates if c.category == "DIRECT_CHORD")

        self.assertEqual({c.plan.actions[-1] for c in chords},
                         {SimpleMove(Action.CHORD, 2, 0), SimpleMove(Action.CHORD, 2, 1)})
        for candidate in chords:
            self.assertEqual(candidate.setup_cells, frozenset())
            self.assertEqual(candidate.reveal_cells, {(3, 0), (3, 1)})
            self.assertEqual(candidate.plan.reveals, 2)
            self.assertEqual(len(candidate.plan.actions), 1)
        self.assertEqual(result.category, "DIRECT_CHORD")
        self.assertEqual(result.move, SimpleMove(Action.CHORD, 2, 0))

    def test_d_one_mine_setup_chord_is_selected_and_counts_only_current_hidden_safes(self):
        result = self.select(ONE_SETUP, 1)

        self.assertEqual(result.category, "SETUP_CHORD")
        self.assertEqual(result.move, SimpleMove(Action.FLAG, 1, 0))
        self.assertEqual(result.plan.actions, (
            SimpleMove(Action.FLAG, 1, 0), SimpleMove(Action.CHORD, 2, 0),
        ))
        self.assertEqual((result.plan.latency_us, result.plan.reveals), (252010, 2))
        selected = next(c for c in result.survivors if c.plan == result.plan)
        self.assertEqual(selected.setup_cells, {(1, 0)})
        self.assertEqual(selected.reveal_cells, {(3, 0), (3, 1)})
        self.assertEqual({c.plan.actions[0] for c in result.candidates
                          if c.category == "DIRECT_SAFE_OPEN"},
                         {SimpleMove(Action.OPEN, 3, 0), SimpleMove(Action.OPEN, 3, 1)})

    def test_e_multi_mine_setup_delegates_route_order_and_stays_within_seven(self):
        evidence = decision(SEVEN_SETUP, 7)
        with patch.object(policy, "exact_route", wraps=exact_route) as route:
            result = policy.select_policy(evidence, (4, 4), self.table)
        center = next(c for c in result.candidates
                      if c.plan.actions[-1] == SimpleMove(Action.CHORD, 2, 2))
        expected_setup = frozenset({(1, 1), (2, 1), (3, 1), (1, 2),
                                    (3, 2), (1, 3), (2, 3)})

        self.assertEqual(center.setup_cells, expected_setup)
        self.assertEqual(center.reveal_cells, {(3, 3)})
        self.assertEqual(center.plan.reveals, 1)
        self.assertEqual((center.plan.actions, center.plan.latency_us),
                         exact_route(self.table, (4, 4), expected_setup,
                                     SimpleMove(Action.CHORD, 2, 2)))
        self.assertGreater(route.call_count, 0)
        self.assertTrue(any(set(call.args[2]) == expected_setup
                            and call.args[3] == SimpleMove(Action.CHORD, 2, 2)
                            for call in route.call_args_list))
        self.assertTrue(all(len(c.setup_cells) <= 7 for c in result.candidates))

    def test_f_logical_mine_does_not_already_satisfy_physical_chord_count(self):
        result = self.select(ONE_SETUP, 1)

        self.assertEqual(result.evidence.after.P, frozenset())
        self.assertFalse(any(c.category == "DIRECT_CHORD" for c in result.candidates))
        for candidate in result.candidates:
            if candidate.plan.actions[-1].action == Action.CHORD:
                self.assertEqual(candidate.category, "SETUP_CHORD")
                self.assertEqual(candidate.plan.actions[0], SimpleMove(Action.FLAG, 1, 0))

    def test_g_materialized_mine_is_not_flagged_twice_and_overlap_counts_once(self):
        evidence = flagged_decision()
        result = policy.select_policy(evidence, (0, 0), self.table)

        self.assertEqual(evidence.after.P, {(1, 0)})
        self.assertEqual(evidence.after.M, {(1, 0)})
        self.assertEqual(evidence.after.J, {(1, 0)})
        self.assertEqual(evidence.after.b, 0)
        self.assertTrue(all(not c.setup_cells for c in result.candidates))
        self.assertTrue(all(move.action != Action.FLAG
                            for c in result.candidates for move in c.plan.actions))
        self.assertFalse(result.setup_open_generated)

    def test_h_setup_open_and_direct_open_have_one_reveal_and_ordinary_dominance(self):
        result = self.select(HISTORICAL, 1)
        setup = next(c for c in result.candidates if c.category == "SETUP_OPEN")
        direct = next(c for c in result.candidates if c.category == "DIRECT_SAFE_OPEN")

        self.assertEqual(setup.plan.actions[-1], direct.plan.actions[-1])
        self.assertEqual(setup.plan.reveals, direct.plan.reveals)
        self.assertEqual(setup.plan.reveals, 1)
        self.assertGreater(setup.plan.latency_us, direct.plan.latency_us)
        self.assertNotIn(setup.plan, prune_dominated(c.plan for c in result.candidates))
        self.assertNotIn(setup, result.survivors)
        self.assertTrue(result.setup_open_generated)
        self.assertTrue(result.setup_open_pruned)
        # This curated cost comparison is unit evidence, never a P-8 PASS.

    def test_i_synthetic_detour_fault_survives_and_is_reported_without_auth_bypass(self):
        evidence = decision(HISTORICAL, 1)
        table = [[100] * 16 for _ in range(30)]
        table[1][0], table[2][0] = 1, 1
        table = tuple(tuple(row) for row in table)
        with self.assertRaises(ValueError):
            policy.select_policy(evidence, (0, 0), table)

        candidates = policy._generate_candidates(evidence, (0, 0), table, True)
        setup = next(c for c in candidates if c.category == "SETUP_OPEN")
        direct = next(c for c in candidates if c.category == "DIRECT_SAFE_OPEN")
        self.assertEqual((setup.plan.latency_us, direct.plan.latency_us), (2, 100))
        self.assertIn(setup.plan, prune_dominated(c.plan for c in candidates))
        with self.assertRaises(policy.KPolicyIntegrityError) as failure:
            policy._select_candidates(evidence, (0, 0), candidates)
        self.assertEqual(failure.exception.code, "SETUP_OPEN_SURVIVED")
        result = failure.exception.result
        self.assertEqual(result.failure_code, "SETUP_OPEN_SURVIVED")
        self.assertEqual(result.candidates, candidates)
        self.assertIn(setup, result.survivors)
        self.assertTrue(result.setup_open_generated)
        self.assertFalse(result.setup_open_pruned)
        self.assertIsNone(result.move)
        self.assertIsNone(result.plan)

    def test_j_omitted_dominated_setup_open_vocabulary_preserves_selection(self):
        for observation in (HISTORICAL, ONE_SETUP):
            with self.subTest(observation=observation):
                evidence = decision(observation, 1)
                generated = policy.select_policy(evidence, (0, 0), self.table)
                omitted = policy.select_policy(evidence, (0, 0), self.table,
                                               include_setup_open=False)
                self.assertEqual((generated.move, generated.plan, generated.category),
                                 (omitted.move, omitted.plan, omitted.category))
                self.assertEqual(generated.survivors, omitted.survivors)
                self.assertTrue(generated.setup_open_generated)
                self.assertFalse(omitted.setup_open_generated)
                self.assertFalse(any(c.category == "SETUP_OPEN" for c in omitted.candidates))

    def test_k_missing_reveal_candidates_fail_closed_without_standalone_flag(self):
        evidence = decision(HISTORICAL, 1)
        self.assertTrue(evidence.after.M)
        self.assertTrue(evidence.selection_safe_cells)
        with patch.object(policy, "_generate_candidates", return_value=()):
            with self.assertRaises(policy.KPolicyIntegrityError) as failure:
                policy.select_policy(evidence, (0, 0), self.table)
        self.assertEqual(failure.exception.code, "NO_REVEAL_CANDIDATE")
        result = failure.exception.result
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.survivors, ())
        self.assertEqual(result.failure_code, "NO_REVEAL_CANDIDATE")
        self.assertIsNone(result.move)
        self.assertIsNone(result.plan)

    def test_l_exact_guess_preserves_target_without_materializing_existing_mines(self):
        evidence = decision(((H, 1, H, H, H),), 3)
        self.assertEqual(evidence.continuation, "EXACT_GUESS")
        self.assertEqual(evidence.after.M, {(3, 0), (4, 0)})
        self.assertEqual(evidence.after.U, {(0, 0), (2, 0)})
        self.assertEqual(evidence.phase_e.minimum_risk, Fraction(1, 2))
        for cursor in ((0, 0), (2, 0), (4, 0)):
            with self.subTest(cursor=cursor), patch.object(
                policy, "exact_route", side_effect=AssertionError("Guess was routed"),
            ), patch.object(
                policy, "_generate_candidates", side_effect=AssertionError("Guess gained setup"),
            ):
                result = policy.select_policy(evidence, cursor, self.table)
                self.assertEqual(result.move, SimpleMove(Action.OPEN, *evidence.guess_target))
                self.assertEqual(result.move, SimpleMove(Action.OPEN, 0, 0))
                self.assertEqual(result.category, "EXACT_MINIMUM_RISK_GUESS")
                self.assertIsNone(result.plan)
                self.assertEqual((result.candidates, result.survivors), ((), ()))

    def test_m_equal_risk_guess_uses_yx_even_when_another_target_is_cheaper(self):
        evidence = decision(((1, H, H), (H, H, H)), 2)
        self.assertEqual(evidence.phase_e.minimum_risk_cells, {(1, 0), (0, 1), (1, 1)})
        self.assertEqual(evidence.guess_target, (1, 0))
        result = policy.select_policy(evidence, (0, 1), self.table)

        self.assertEqual(result.move, SimpleMove(Action.OPEN, 1, 0))
        self.assertLess(action_cost(self.table, (0, 1), (0, 1)),
                        action_cost(self.table, (0, 1), (1, 0)))
        self.assertIsNone(result.plan)

    def test_n_deduplication_merges_identical_sequences_only(self):
        result = policy.select_policy(flagged_decision(), (0, 0), self.table)
        sequences = tuple(c.plan.actions for c in result.candidates)
        self.assertEqual(len(sequences), len(set(sequences)))
        self.assertEqual(len(result.candidates), 4)  # Two OPENs, two distinct CHORDs.
        multiple = self.select(TWO_SETUP_WITH_UNRELATED_MINE, 3)
        same_terminal = tuple(c for c in multiple.candidates if c.category == "SETUP_OPEN"
                              and c.plan.actions[-1] == SimpleMove(Action.OPEN, 2, 3))
        self.assertGreater(len(same_terminal), 1)
        self.assertEqual(len({c.plan.actions for c in same_terminal}), len(same_terminal))
        self.assertGreater(len({c.setup_cells for c in same_terminal}), 1)

    def test_o_equal_latency_and_reveals_are_not_strictly_dominated(self):
        evidence = decision(((0, H, H, 0),), 0)
        result = policy.select_policy(evidence, (1, 0), self.table)

        self.assertEqual(len(result.candidates), 2)
        self.assertEqual({(c.plan.latency_us, c.plan.reveals) for c in result.candidates},
                         {(126005, 1)})
        self.assertEqual(result.survivors, result.candidates)

    def test_p_e_first_uses_exact_rational_comparison_across_nondominated_plans(self):
        evidence = decision(ONE_SETUP, 1)
        low_latency = synthetic_candidate(2**60 + 1, 3, (0, 0))
        efficient = synthetic_candidate(2**61 + 1, 6, (2, 0))
        self.assertEqual(float(Fraction(low_latency.plan.latency_us, 3)),
                         float(Fraction(efficient.plan.latency_us, 6)))
        self.assertLess(Fraction(efficient.plan.latency_us, 6),
                        Fraction(low_latency.plan.latency_us, 3))
        with patch.object(policy, "prune_dominated", wraps=prune_dominated) as prune, \
                patch.object(policy, "select_reveal_plan", wraps=select_reveal_plan) as select:
            result = policy._select_candidates(evidence, (0, 0), (low_latency, efficient))
        self.assertEqual(result.survivors, (low_latency, efficient))
        self.assertEqual(result.plan, efficient.plan)
        prune.assert_called_once()
        select.assert_called_once()

    def test_q_frozen_latency_coordinate_action_and_route_ties(self):
        evidence = decision(ONE_SETUP, 1)
        pairs = (
            (synthetic_candidate(30, 2, (0, 1)), synthetic_candidate(60, 4, (0, 0))),
            (synthetic_candidate(30, 2, (2, 0)), synthetic_candidate(30, 2, (0, 1))),
            (synthetic_candidate(30, 2, (1, 0)), synthetic_candidate(30, 2, (2, 0))),
            (synthetic_candidate(30, 1, (1, 0), action=Action.OPEN),
             synthetic_candidate(30, 1, (1, 0))),
            (synthetic_candidate(30, 2, (3, 0), flags=((2, 0),)),
             synthetic_candidate(30, 2, (3, 0), flags=((0, 1),))),
            (synthetic_candidate(30, 2, (3, 0), flags=((0, 0), (1, 0))),
             synthetic_candidate(30, 2, (3, 0), flags=((2, 0),))),
        )
        for better, worse in pairs:
            with self.subTest(better=better):
                for candidates in ((better, worse), (worse, better)):
                    result = policy._select_candidates(evidence, (0, 0), candidates)
                    self.assertEqual(result.plan, better.plan)

    def test_q_repeated_inputs_and_result_evidence_are_immutable(self):
        observation = [list(row) for row in ONE_SETUP]
        original = deepcopy(observation)
        evidence = decision(observation, 1)
        expected = policy.select_policy(evidence, (0, 0), self.table)
        for _ in range(5):
            self.assertEqual(policy.select_policy(evidence, (0, 0), self.table), expected)
        self.assertEqual(observation, original)
        self.assertIs(expected.evidence, evidence)
        self.assertEqual(expected.cursor, (0, 0))
        self.assertIsInstance(expected.candidates, tuple)
        self.assertIsInstance(expected.survivors, tuple)
        with self.assertRaises(FrozenInstanceError):
            expected.move = SimpleMove(Action.OPEN, 0, 0)
        with self.assertRaises(FrozenInstanceError):
            expected.candidates[0].category = "OTHER"
        with self.assertRaises(FrozenInstanceError):
            expected.plan.reveals = 999
        observation[0][0] = H
        self.assertEqual(expected.evidence.observation, ONE_SETUP)

    def test_r_observation_accounting_mismatch_is_rejected(self):
        evidence = decision(HISTORICAL, 1)
        malformed = (
            replace(evidence, observation=((1, F, 1, H),)),
            replace(evidence, after=replace(evidence.after, P=frozenset({(1, 0)}))),
            replace(evidence, after=replace(evidence.after, U=frozenset({(1, 0), (3, 0)}))),
        )
        for item in malformed:
            with self.subTest(evidence=item), self.assertRaises(KIntegrityError):
                policy.select_policy(item, (0, 0), self.table)
        # A self-consistent record cannot prove live freshness. The runner must
        # bind this exact evidence/current observation to the pre-action state.

    def test_s_nonhidden_safe_target_never_becomes_an_open_candidate(self):
        evidence = decision(HISTORICAL, 1)
        for target in ((0, 0), (1, 0)):
            malformed = replace(evidence, selection_safe_cells=frozenset({target}))
            with self.subTest(target=target), self.assertRaises(KIntegrityError):
                policy.select_policy(malformed, (0, 0), self.table)
        flagged = flagged_decision()
        malformed = replace(flagged, selection_safe_cells=frozenset({(1, 0)}))
        with self.assertRaises(KIntegrityError):
            policy.select_policy(malformed, (0, 0), self.table)

    def test_t_chord_target_must_be_actual_revealed_positive_clue(self):
        for evidence in (decision(((0, H),), 0), decision(ONE_SETUP, 1), flagged_decision()):
            with self.subTest(observation=evidence.observation):
                result = policy.select_policy(evidence, (0, 0), self.table)
                for candidate in result.candidates:
                    terminal = candidate.plan.actions[-1]
                    if terminal.action == Action.CHORD:
                        self.assertIn(evidence.observation[terminal.y][terminal.x], range(1, 9))
        # Private malformed seam: stale clue records must not override the
        # actual physical target glyph even before public consistency rejection.
        evidence = decision(HISTORICAL, 1)
        for invalid in (0, H, F):
            malformed = replace(evidence, observation=((1, H, invalid, H),))
            candidates = policy._generate_candidates(malformed, (0, 0), self.table, True)
            self.assertFalse(any(c.plan.actions[-1] == SimpleMove(Action.CHORD, 2, 0)
                                 for c in candidates))

    def test_u_every_setup_flag_is_hidden_owned_m_and_no_unrelated_mine_is_added(self):
        result = self.select(TWO_SETUP_WITH_UNRELATED_MINE, 3)
        for candidate in result.candidates:
            self.assertLessEqual(candidate.setup_cells, result.evidence.after.M)
            self.assertLessEqual(candidate.setup_cells, result.evidence.after.H)
            self.assertEqual({(m.x, m.y) for m in candidate.plan.actions[:-1]},
                             candidate.setup_cells)
            self.assertTrue(all(m.action == Action.FLAG for m in candidate.plan.actions[:-1]))
            self.assertNotIn((6, 2), candidate.setup_cells)
        center = next(c for c in result.candidates
                      if c.plan.actions[-1] == SimpleMove(Action.CHORD, 2, 2))
        self.assertEqual(center.setup_cells, {(1, 1), (3, 1)})
        self.assertEqual(center.reveal_cells, {(2, 3)})

    def test_v_selection_does_not_call_inference_or_frozen_v1_policy_authority(self):
        evidence = decision(ONE_SETUP, 1)
        blocked_calls = (
            "simple_algorithm.infer_deterministic", "simple_decision.analyze_position",
            "simple_probability.calculate_probabilities", "stage3_planner.generate_reveal_plans",
            "stage3_planner.certainty_pool", "stage3_planner.plan_position",
        )
        from contextlib import ExitStack
        with ExitStack() as stack:
            for target in blocked_calls:
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            stack.enter_context(patch.object(KLocalSession, "analyze_local", side_effect=AssertionError))
            stack.enter_context(patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError))
            result = policy.select_policy(evidence, (0, 0), self.table)
        self.assertEqual(result.move, SimpleMove(Action.FLAG, 1, 0))
        self.assertIs(result.evidence, evidence)

    def test_v_no_flood_expansion_or_extra_global_safe_credit(self):
        evidence = decision(((1, H, 1, H, H), (1, 1, 1, H, H)), 1)
        result = policy.select_policy(evidence, (0, 0), self.table)

        self.assertEqual(evidence.selection_safe_cells, {(3, 0), (3, 1)})
        self.assertIsNone(evidence.phase_d)
        self.assertEqual({c.plan.actions[-1] for c in result.candidates
                          if c.category == "DIRECT_SAFE_OPEN"},
                         {SimpleMove(Action.OPEN, 3, 0), SimpleMove(Action.OPEN, 3, 1)})
        self.assertTrue(all(c.plan.reveals == len(c.reveal_cells) for c in result.candidates))
        self.assertTrue(all(c.plan.reveals <= 2 for c in result.candidates))
        self.assertTrue(all((4, 0) not in c.reveal_cells and (4, 1) not in c.reveal_cells
                            for c in result.candidates))

    def test_v_import_and_api_need_no_engine_answer_or_evaluator_channel(self):
        public_types = types.ModuleType("core_engine")
        public_types.Action, public_types.CellState = Action, CellState
        public_types.GameStatus = GameStatus
        blocked = {name: None for name in (
            "board_snapshot", "board_analyzer", "benchmark_board", "benchmark_runner",
            "replay_model", "replay_player", "zini_core", "simple_runner", "stage3_runner",
            "experiments.program_k_runner", "experiments.program_k_shadow",
        )}
        evidence = decision(HISTORICAL, 1)
        with patch.dict(sys.modules, {"core_engine": public_types, **blocked}):
            isolated = runpy.run_path(policy.__file__)
            result = isolated["select_policy"](evidence, (0, 0), self.table)
        self.assertEqual(result.move, SimpleMove(Action.OPEN, 3, 0))
        imports = set()
        for node in ast.walk(ast.parse(Path(policy.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
                if node.module == "stage3_planner":
                    self.assertFalse({alias.name for alias in node.names} &
                                     {"certainty_pool", "generate_reveal_plans", "plan_position"})
        self.assertFalse(imports.intersection(blocked))
        self.assertEqual(tuple(inspect.signature(policy.select_policy).parameters),
                         ("evidence", "cursor", "table", "include_setup_open"))
        for keyword in ("engine", "answer", "snapshot", "future_observation", "evaluator"):
            with self.subTest(keyword=keyword), self.assertRaises(TypeError):
                policy.select_policy(evidence, (0, 0), self.table, **{keyword: object()})

    def test_exact_safe_uses_current_exact_pool_and_all_direct_opens(self):
        result = self.select(((H, 1, H, H, H),), 1, (4, 0))

        self.assertEqual(result.continuation, "EXACT_SAFE")
        self.assertEqual(result.evidence.selection_safe_cells, {(3, 0), (4, 0)})
        self.assertEqual({c.plan.actions for c in result.candidates}, {
            (SimpleMove(Action.OPEN, 3, 0),), (SimpleMove(Action.OPEN, 4, 0),),
        })
        self.assertEqual(result.move, SimpleMove(Action.OPEN, 3, 0))

    def test_exact_safe_setup_uses_final_m_including_simultaneous_g1_acquisition(self):
        evidence = decision(((H, 2, 2, H), (H, H, H, H)), 4)
        result = policy.select_policy(evidence, (0, 0), self.table)
        safes = frozenset({(1, 1), (2, 1)})

        self.assertEqual(evidence.continuation, "EXACT_SAFE")
        self.assertEqual(evidence.local.after.M, frozenset())
        self.assertEqual(evidence.phase_d.G1, {(0, 0), (3, 0), (0, 1), (3, 1)})
        self.assertEqual(evidence.after.M, evidence.phase_d.G1)
        self.assertEqual(evidence.phase_d.G0, safes)
        self.assertEqual({c.plan.actions for c in result.candidates
                          if c.category == "DIRECT_SAFE_OPEN"}, {
            (SimpleMove(Action.OPEN, 1, 1),), (SimpleMove(Action.OPEN, 2, 1),),
        })
        chords = {c.plan.actions[-1]: c for c in result.candidates
                  if c.category == "SETUP_CHORD"}
        expected_setups = {
            SimpleMove(Action.CHORD, 1, 0): frozenset({(0, 0), (0, 1)}),
            SimpleMove(Action.CHORD, 2, 0): frozenset({(3, 0), (3, 1)}),
        }
        self.assertEqual(chords.keys(), expected_setups.keys())
        for terminal, setup in expected_setups.items():
            candidate = chords[terminal]
            self.assertEqual(candidate.setup_cells, setup)
            self.assertEqual(candidate.reveal_cells, safes)
            self.assertEqual(candidate.plan.reveals, 2)
            self.assertEqual((candidate.plan.actions, candidate.plan.latency_us),
                             exact_route(self.table, (0, 0), setup, terminal))

    def test_whole_clue_requires_all_remaining_safes_and_exact_missing_flag_count(self):
        evidence = decision(ONE_SETUP, 1)
        terminal = SimpleMove(Action.CHORD, 2, 0)
        # Deliberately malformed private unit inputs: these are not accepted
        # decisions and do not bypass the public evidence validation contract.
        missing_safe = replace(evidence, selection_safe_cells=frozenset({(3, 0)}))
        wrong_clue = replace(evidence, observation=((1, H, 2, H), (1, 1, 1, H)))
        for malformed in (missing_safe, wrong_clue):
            with self.subTest(evidence=malformed):
                candidates = policy._generate_candidates(
                    malformed, (0, 0), self.table, True,
                )
                self.assertFalse(any(c.plan.actions[-1] == terminal for c in candidates))

    def test_exact_guess_rejects_changed_winner_incomplete_tie_and_invalid_risk(self):
        evidence = decision(((1, H, H), (H, H, H)), 2)
        exact = evidence.phase_e
        malformed = (
            replace(evidence, guess_target=(0, 1)),
            replace(evidence, guess_target=(0, 0)),
            replace(evidence, phase_e=replace(exact, minimum_risk_cells=frozenset({(1, 0)}))),
            replace(evidence, phase_e=replace(exact, minimum_risk=Fraction(0))),
            replace(evidence, phase_e=replace(exact, minimum_risk=Fraction(1))),
        )
        for item in malformed:
            with self.subTest(evidence=item), self.assertRaises(KIntegrityError):
                policy.select_policy(item, (0, 0), self.table)

    def test_bad_cursor_or_table_is_rejected_before_selection(self):
        evidence = decision(HISTORICAL, 1)
        for cursor in ((-1, 0), (4, 0), (0, 1), (True, 0), None):
            with self.subTest(cursor=cursor), self.assertRaises(ValueError):
                policy.select_policy(evidence, cursor, self.table)
        changed = [list(row) for row in self.table]
        changed[0][0] += 1
        with patch.object(policy, "_generate_candidates", side_effect=AssertionError):
            with self.assertRaises(ValueError):
                policy.select_policy(evidence, (0, 0), changed)


if __name__ == "__main__":
    unittest.main()
