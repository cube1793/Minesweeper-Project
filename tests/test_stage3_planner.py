"""Independent production Stage-3 planner oracles and frozen-pilot differential.

Only the differential fixture constructs engine layouts. Every planner call
receives public observation, public mine count, cursor and the frozen table.
"""

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError
from fractions import Fraction
import hashlib
import inspect
from itertools import permutations
from pathlib import Path
from random import Random
import runpy
import sys
import types
import unittest
from unittest.mock import patch

from benchmark_board import EXPERT_GENERAL_V1, generate_board
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from experiments import stage3_policy_planner as experimental
import simple_algorithm
import simple_decision
import simple_probability
from simple_algorithm import InferenceResult, SimpleMove
from simple_decision import DecisionKind, analyze_position
from stage3_physical import load_timing_table
import stage3_planner as planner


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
EXPERIMENTAL_SHA256 = "a452dc5174f3a7244fd193ef76d9ca44f89e8ef79c1c2f7427109ce3449675fc"

# A public clue-7 has eight hidden neighbors: seven are already locally
# certain mines and (3,3) is safe. Outer visible clues certify all seven.
SEVEN_SETUP = (
    (1, 2, 3, 2, 1),
    (2, H, H, H, 2),
    (3, H, 7, H, 2),
    (2, H, H, H, 1),
    (1, 2, 2, 1, 0),
)

# The clue at (2,2) requires exactly two setup flags. The certain mine at
# (6,2) is unrelated to every reveal, and must never become a detour.
TWO_SETUP_WITH_UNRELATED_MINE = (
    (1, 1, 2, 1, 1, 0, 0),
    (1, H, 2, H, 1, 1, 1),
    (1, 1, 2, 1, 1, 1, H),
    (0, 0, H, 0, 0, 1, 1),
    (0, 0, 0, 0, 0, 0, 0),
)


def reveal_plan(latency, reveals, x=0, y=0, action=Action.OPEN, flags=()):
    actions = tuple(SimpleMove(Action.FLAG, *cell) for cell in flags)
    return planner.RevealPlan(actions + (SimpleMove(action, x, y),), latency, reveals)


def plan_signature(plan):
    return plan.actions, plan.latency_us, plan.reveals


class ProductionPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def candidates(self, observation, num_mines, cursor=(0, 0)):
        evidence = analyze_position(observation, num_mines)
        return planner.generate_reveal_plans(observation, evidence, cursor, self.table)

    def test_local_certainty_blocks_probability_and_excludes_extra_global_facts(self):
        observation = [[F, 1, H, H], [1, 1, H, H]]
        with patch("simple_decision.calculate_probabilities", side_effect=AssertionError):
            decision = planner.plan_position(observation, 1, (1, 0), self.table)
        self.assertEqual(decision.evidence.kind, DecisionKind.LOCAL_DETERMINISTIC)
        self.assertIsNone(decision.evidence.probability_result)
        safe, mines = planner.certainty_pool(decision.evidence)
        self.assertEqual(safe, {(2, 0), (2, 1)})
        self.assertFalse(mines)
        # The public global budget would additionally certify column 3, but
        # Stage 2 did not reach that inference path in this observation.
        self.assertNotIn((3, 0), safe)
        self.assertNotIn((3, 1), safe)

    def test_global_certainty_uses_all_facts_only_after_real_probability_call(self):
        observation = [[H, 2, 2, H], [F, H, H, F]]
        with patch("simple_decision.calculate_probabilities",
                   wraps=simple_probability.calculate_probabilities) as calculate:
            decision = planner.plan_position(observation, 4, (0, 0), self.table)
        calculate.assert_called_once_with(observation, 4)
        self.assertEqual(decision.evidence.kind, DecisionKind.GLOBAL_CERTAINTY)
        self.assertEqual(decision.evidence.deterministic_result, InferenceResult((), ()))
        self.assertEqual(planner.certainty_pool(decision.evidence),
                         ({(1, 1), (2, 1)}, {(0, 0), (3, 0)}))
        plans = planner.generate_reveal_plans(
            observation, decision.evidence, (0, 0), self.table)
        self.assertTrue(any(len(plan.actions) > 1 for plan in plans))
        direct_opens = {plan.actions[0] for plan in plans if len(plan.actions) == 1
                        and plan.actions[0].action == Action.OPEN}
        self.assertEqual(direct_opens, {SimpleMove(Action.OPEN, 1, 1),
                                       SimpleMove(Action.OPEN, 2, 1)})

    def test_speed_selection_can_open_from_same_local_pool_before_stage2_flag(self):
        observation = [[0, H, H, 3], [H, H, H, H]]
        decision = planner.plan_position(observation, 3, (0, 0), self.table)
        self.assertEqual(decision.evidence.move, SimpleMove(Action.FLAG, 2, 0))
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 1, 0))

    def test_direct_open_is_one_reveal_and_chord_counts_only_adjacent_hidden(self):
        observation = [[F, 1, H, H], [1, 1, H, H]]
        plans = self.candidates(observation, 1)
        expected = {
            ((SimpleMove(Action.OPEN, 2, 0),), 1),
            ((SimpleMove(Action.OPEN, 2, 1),), 1),
            ((SimpleMove(Action.CHORD, 1, 0),), 2),
            ((SimpleMove(Action.CHORD, 1, 1),), 2),
        }
        self.assertEqual({(plan.actions, plan.reveals) for plan in plans}, expected)
        # Extra hidden column 3 could be opened by a flood, but contributes
        # nothing to the guaranteed reveal counts before actual execution.

    def test_zero_and_empty_chords_are_excluded(self):
        for observation, mines in (([[0, H]], 0), ([[F, 1, 0, 0, H]], 1)):
            with self.subTest(observation=observation):
                plans = self.candidates(observation, mines)
                self.assertTrue(plans)
                self.assertTrue(all(plan.actions[-1].action == Action.OPEN for plan in plans))
        self.assertEqual(self.candidates([[1, H]], 1), ())

    def test_setup_open_and_setup_chord_are_exact_first_reveal_candidates(self):
        observation = [[1, H, 1, H]]
        plans = self.candidates(observation, 1)
        flag = SimpleMove(Action.FLAG, 1, 0)
        self.assertEqual({(plan.actions, plan.reveals) for plan in plans}, {
            ((flag, SimpleMove(Action.OPEN, 3, 0)), 1),
            ((flag, SimpleMove(Action.CHORD, 2, 0)), 1),
        })
        decision = planner.plan_position(observation, 1, (0, 0), self.table)
        self.assertEqual(decision.move, flag)
        self.assertEqual(decision.evidence.deterministic_result.safe_cells, frozenset())
        self.assertEqual(decision.plan.actions[0], flag)

    def test_whole_setup_only_and_no_unrelated_flag_detour(self):
        plans = self.candidates(TWO_SETUP_WITH_UNRELATED_MINE, 3)
        center = [plan for plan in plans
                  if plan.actions[-1] == SimpleMove(Action.CHORD, 2, 2)]
        self.assertEqual(len(center), 1)
        self.assertEqual({(move.x, move.y) for move in center[0].actions[:-1]},
                         {(1, 1), (3, 1)})
        self.assertEqual(len(center[0].actions), 3)
        self.assertTrue(all(SimpleMove(Action.FLAG, 6, 2) not in plan.actions for plan in plans))
        self.assertTrue(all(plan.actions[-1].action in (Action.OPEN, Action.CHORD)
                            and all(move.action == Action.FLAG for move in plan.actions[:-1])
                            for plan in plans))

    def test_no_virtual_inference_probability_or_retained_new_mines(self):
        observation = [[1, H, 1, H, H, 1, H]]
        with (
            patch.object(planner, "analyze_position", wraps=analyze_position) as analyze,
            patch("simple_decision.infer_deterministic",
                  wraps=simple_algorithm.infer_deterministic) as infer,
            patch("simple_decision.calculate_probabilities", side_effect=AssertionError),
        ):
            decision = planner.plan_position(observation, 2, (0, 0), self.table)
        analyze.assert_called_once_with(observation, 2)
        infer.assert_called_once()
        self.assertEqual(planner.certainty_pool(decision.evidence), (set(), {(1, 0)}))
        plans = planner.generate_reveal_plans(
            observation, decision.evidence, (0, 0), self.table)
        self.assertEqual({move for plan in plans for move in plan.actions[:-1]},
                         {SimpleMove(Action.FLAG, 1, 0)})
        self.assertEqual({plan.actions[-1] for plan in plans},
                         {SimpleMove(Action.OPEN, 3, 0), SimpleMove(Action.CHORD, 2, 0)})

    def test_setup_reaches_structural_maximum_seven_without_candidate_cap(self):
        plans = self.candidates(SEVEN_SETUP, 7)
        center = next(plan for plan in plans
                      if plan.actions[-1] == SimpleMove(Action.CHORD, 2, 2))
        self.assertEqual(len(center.actions) - 1, 7)
        self.assertEqual(center.reveals, 1)
        self.assertEqual({(move.x, move.y) for move in center.actions[:-1]},
                         {(1, 1), (2, 1), (3, 1), (1, 2), (3, 2), (1, 3), (2, 3)})
        self.assertTrue(all(len(plan.actions) - 1 <= 7 for plan in plans))

    def test_all_eight_neighbors_certain_mines_cannot_form_reveal_setup(self):
        observation = [[H, H, H], [H, 8, H], [H, H, H]]
        self.assertEqual(self.candidates(observation, 8), ())
        decision = planner.plan_position(observation, 8, (1, 1), self.table)
        self.assertEqual(decision.move, SimpleMove(Action.FLAG, 1, 0))
        self.assertIsNone(decision.plan)

    def test_deduplicate_identical_actions_only_keep_equal_metric_alternatives(self):
        duplicates = self.candidates([[0, H, 0], [0, 0, 0]], 0)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].actions, (SimpleMove(Action.OPEN, 1, 0),))
        alternatives = self.candidates([[0, H, H, 0]], 0, (1, 0))
        self.assertEqual(len(alternatives), 2)
        self.assertEqual({(plan.latency_us, plan.reveals) for plan in alternatives},
                         {(126005, 1)})
        self.assertEqual(planner.prune_dominated(alternatives), alternatives)

    def test_exact_route_matches_exhaustive_permutations_for_zero_through_seven_flags(self):
        random = Random(7026)
        for count in range(8):
            with self.subTest(setup_size=count):
                cells = random.sample([(x, y) for y in range(5) for x in range(7)], count + 2)
                cursor, target, *flags = cells
                terminal = SimpleMove(Action.CHORD, *target)
                actions, latency = planner.exact_route(self.table, cursor, flags, terminal)
                # This factorial oracle shares no DP or production cost helper.
                expected = min(
                    (sum(self.table[abs(a[0] - b[0])][abs(a[1] - b[1])]
                         for a, b in zip((cursor,) + route, route + (target,))),
                     tuple((y, x) for x, y in route))
                    for route in permutations(flags)
                )
                self.assertEqual((latency, tuple((m.y, m.x) for m in actions[:-1])), expected)
                self.assertEqual(actions[-1], terminal)
                self.assertTrue(all(move.action == Action.FLAG for move in actions[:-1]))

    def test_route_uses_table_and_terminal_input_not_greedy_or_euclidean_distance(self):
        table = [[1] * 16 for _ in range(30)]
        table[1][0], table[2][0], table[3][0] = 10, 1, 1
        actions, latency = planner.exact_route(
            table, (0, 0), {(1, 0), (2, 0)}, SimpleMove(Action.OPEN, 4, 0))
        self.assertEqual(actions, (SimpleMove(Action.FLAG, 2, 0),
                                   SimpleMove(Action.FLAG, 1, 0), SimpleMove(Action.OPEN, 4, 0)))
        self.assertEqual(latency, 12)

    def test_route_ties_use_setup_coordinate_reading_order(self):
        table = tuple((1,) * 16 for _ in range(30))
        flags = [(1, 1), (2, 0), (1, 0)]
        for input_order in permutations(flags):
            actions, latency = planner.exact_route(
                table, (0, 0), input_order, SimpleMove(Action.OPEN, 3, 3))
            self.assertEqual([(move.x, move.y) for move in actions[:-1]],
                             [(1, 0), (2, 0), (1, 1)])
            self.assertEqual(latency, 4)

    def test_dominance_matches_independent_all_pairs_oracle(self):
        random = Random(807)
        for count in (0, 1, 2, 10, 100, 300):
            plans = tuple(reveal_plan(random.randrange(1, 60), random.randrange(1, 9),
                                      x=index % 30, y=index // 30) for index in range(count))
            expected = tuple(candidate for candidate in plans if not any(
                other.latency_us <= candidate.latency_us
                and other.reveals >= candidate.reveals
                and (other.latency_us != candidate.latency_us or other.reveals != candidate.reveals)
                for other in plans))
            self.assertEqual(planner.prune_dominated(plans), expected)

    def test_dominance_requires_one_strict_metric_and_keeps_equal_plans(self):
        a, b = reveal_plan(10, 2), reveal_plan(10, 2, x=1)
        worse_latency, worse_reveal = reveal_plan(11, 2), reveal_plan(10, 1)
        tradeoff = reveal_plan(9, 1)
        self.assertEqual(planner.prune_dominated((a, b, worse_latency, worse_reveal, tradeoff)),
                         (a, b, tradeoff))

    def test_e_first_beats_latency_first_and_uses_exact_integer_precision(self):
        fast, efficient = reveal_plan(50, 1), reveal_plan(350, 8, x=1)
        self.assertEqual(planner.select_reveal_plan((fast, efficient)), efficient)
        tiny_difference = (reveal_plan(2**60 + 1, 3), reveal_plan(2**60, 3, x=1))
        self.assertEqual(float(Fraction(tiny_difference[0].latency_us, 3)),
                         float(Fraction(tiny_difference[1].latency_us, 3)))
        self.assertGreater(planner.compare_efficiency(*tiny_difference), 0)
        self.assertEqual(planner.select_reveal_plan(tiny_difference), tiny_difference[1])
        self.assertEqual(planner.compare_efficiency(reveal_plan(3, 2), reveal_plan(6, 4)), 0)

    def test_e_selection_matches_fraction_oracle(self):
        random = Random(344)
        for _ in range(30):
            plans = tuple(reveal_plan(random.randrange(1, 2**70), random.randrange(1, 9),
                                      x=i % 30, y=i // 30) for i in range(60))
            expected = min(plans, key=lambda item: (
                Fraction(item.latency_us, item.reveals), item.latency_us,
                item.actions[-1].y, item.actions[-1].x))
            self.assertEqual(planner.select_reveal_plan(plans), expected)

    def test_final_ties_use_latency_then_y_x_action_rank_and_setup_order(self):
        cases = (
            (reveal_plan(30, 2, y=1), reveal_plan(60, 4)),
            (reveal_plan(30, 2, x=2, y=0), reveal_plan(30, 2, x=0, y=1)),
            (reveal_plan(30, 2, x=1), reveal_plan(30, 2, x=2)),
            (reveal_plan(30, 2), reveal_plan(30, 2, action=Action.FLAG)),
            (reveal_plan(30, 2, action=Action.FLAG), reveal_plan(30, 2, action=Action.CHORD)),
            (reveal_plan(30, 2, x=4, flags=((2, 0),)),
             reveal_plan(30, 2, x=4, flags=((0, 1),))),
            # This longer setup wins lexicographically; action count is not
            # a preferred metric at the final tie boundary.
            (reveal_plan(30, 2, x=4, flags=((0, 0), (1, 0))),
             reveal_plan(30, 2, x=4, flags=((2, 0),))),
        )
        for better, worse in cases:
            with self.subTest(better=better, worse=worse):
                self.assertEqual(planner.select_reveal_plan((worse, better)), better)
                self.assertEqual(planner.select_reveal_plan((better, worse)), better)

    def test_nearest_certain_flag_fallback_uses_frozen_cost_then_y_x(self):
        observation = [[H, 1, 0, 1, H]]
        nearby = planner.plan_position(observation, 2, (3, 0), self.table)
        tie = planner.plan_position(observation, 2, (2, 0), self.table)
        self.assertEqual(nearby.move, SimpleMove(Action.FLAG, 4, 0))
        self.assertEqual(tie.move, SimpleMove(Action.FLAG, 0, 0))
        self.assertIsNone(nearby.plan)
        self.assertIsNone(tie.plan)

    def test_guess_exactly_preserves_stage2_tie_even_when_cursor_is_farther(self):
        decision = planner.plan_position([[H, H, H]], 1, (2, 0), self.table)
        self.assertEqual(decision.evidence.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 0, 0))
        self.assertIs(decision.move, decision.evidence.move)
        self.assertIsNone(decision.plan)

    def test_guess_minimum_includes_floating_hidden_cells(self):
        observation = [[H, 1, H, H, H, H]]
        decision = planner.plan_position(observation, 2, (5, 0), self.table)
        probabilities = decision.evidence.probability_result
        selected = next(cell for cell in probabilities.probabilities
                        if cell.coordinate == (decision.move.x, decision.move.y))
        self.assertEqual(decision.evidence.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 3, 0))
        self.assertIn(selected.coordinate, probabilities.unconstrained_cells)
        self.assertEqual(selected.probability, Fraction(1, 3))
        self.assertEqual(selected.probability,
                         min(cell.probability for cell in probabilities.probabilities))

    def test_deterministic_public_inputs_remain_unmutated(self):
        for observation, num_mines in (
            ([[1, H, 1, H]], 1), ([[H, 2, 2, H], [F, H, H, F]], 4),
            ([[H, 1, H, H, H, H]], 2), ([list(row) for row in SEVEN_SETUP], 7),
        ):
            with self.subTest(observation=observation):
                before = deepcopy(observation)
                expected = planner.plan_position(observation, num_mines, (0, 0), self.table)
                for _ in range(3):
                    self.assertEqual(planner.plan_position(observation, num_mines, (0, 0), self.table),
                                     expected)
                    self.assertEqual(observation, before)
                if expected.plan is not None:
                    with self.assertRaises(FrozenInstanceError):
                        expected.plan.reveals = 99
                with self.assertRaises(FrozenInstanceError):
                    expected.move = SimpleMove(Action.OPEN, 0, 0)

    def test_public_api_has_no_hidden_input_or_selectable_l_first_policy(self):
        self.assertEqual(tuple(inspect.signature(planner.plan_position).parameters),
                         ("observation", "num_mines", "cursor", "table"))
        for keyword in ("engine", "mine_positions", "snapshot", "board_fingerprint",
                        "replay", "history", "policy"):
            with self.subTest(keyword=keyword), self.assertRaises(TypeError):
                planner.plan_position([[0, H]], 0, (0, 0), self.table, **{keyword: object()})

    def test_planner_loads_and_runs_with_only_public_core_types(self):
        public_types = types.ModuleType("core_engine")
        public_types.Action, public_types.CellState = Action, CellState
        blocked = {name: None for name in (
            "board_snapshot", "board_analyzer", "benchmark_board", "benchmark_runner",
            "replay_model", "replay_player", "zini_core", "simple_runner",
            "stage3_runner", "stage3_calibration", "stage3_calibration_analysis",
            "experiments", "experiments.stage3_policy_planner",
        )}
        with patch.dict(sys.modules, {"core_engine": public_types, **blocked}):
            algorithm = types.ModuleType("simple_algorithm")
            algorithm.__dict__.update(runpy.run_path(simple_algorithm.__file__))
            with patch.dict(sys.modules, {"simple_algorithm": algorithm}):
                probability = types.ModuleType("simple_probability")
                probability.__dict__.update(runpy.run_path(simple_probability.__file__))
                with patch.dict(sys.modules, {"simple_probability": probability}):
                    analyzer = types.ModuleType("simple_decision")
                    analyzer.__dict__.update(runpy.run_path(simple_decision.__file__))
                    with patch.dict(sys.modules, {"simple_decision": analyzer}):
                        isolated = runpy.run_path(planner.__file__)
                        for observation, mines, kind in (
                            ([[1, H, 1, H]], 1, "LOCAL_DETERMINISTIC"),
                            ([[H, 1, H, H]], 1, "GLOBAL_CERTAINTY"),
                            ([[H, 1, H]], 1, "PROBABILITY_GUESS"),
                        ):
                            decision = isolated["plan_position"](observation, mines, (0, 0), self.table)
                            self.assertEqual(decision.evidence.kind.name, kind)
        imports = set()
        for node in ast.walk(ast.parse(Path(planner.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertFalse(imports.intersection(blocked))

    def test_planner_rejects_changed_timing_table_before_analysis(self):
        table = [list(row) for row in self.table]
        table[1][1] += 1
        with patch.object(planner, "analyze_position") as analyze:
            with self.assertRaises(ValueError):
                planner.plan_position([[0, H]], 0, (0, 0), table)
        analyze.assert_not_called()


class ProductionExperimentalDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def compare_state(self, observation, num_mines, cursor):
        original = deepcopy(observation)
        actual = planner.plan_position(observation, num_mines, cursor, self.table)
        reference = experimental.plan_position(observation, num_mines, cursor, self.table, "E-FIRST")
        self.assertEqual(actual.evidence, reference.evidence)
        self.assertEqual(actual.move, reference.move)
        candidates = planner.generate_reveal_plans(observation, actual.evidence, cursor, self.table)
        survivors = planner.prune_dominated(candidates)
        self.assertEqual({plan_signature(plan) for plan in candidates},
                         {plan_signature(plan) for plan in reference.candidates})
        self.assertEqual({plan_signature(plan) for plan in survivors},
                         {plan_signature(plan) for plan in reference.survivors})
        if actual.plan is None:
            self.assertNotIn("E-FIRST", reference.choices)
        else:
            self.assertEqual(plan_signature(actual.plan), plan_signature(reference.choices["E-FIRST"]))
        self.assertEqual(observation, original)
        return actual

    def test_frozen_experimental_reference_source_identity(self):
        # Authenticate the Git source, independent of Windows checkout CRLF.
        source = Path(experimental.__file__).read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         EXPERIMENTAL_SHA256)

    def test_curated_public_states_candidates_survivors_and_selection_match(self):
        fixtures = (
            ([[1, H, 1, H]], 1, (0, 0)),
            ([[F, 1, H, H], [1, 1, H, H]], 1, (1, 0)),
            ([[0, H]], 0, (0, 0)),
            ([[H, 1, 0, 1, H]], 2, (3, 0)),
            ([[H, 1, 0, 1, H]], 2, (2, 0)),
            ([[H, 2, 2, H], [F, H, H, F]], 4, (0, 0)),
            ([[H, 1, H, H, H, H]], 2, (5, 0)),
            ([[H, H, H]], 1, (2, 0)),
            (TWO_SETUP_WITH_UNRELATED_MINE, 3, (2, 2)),
            (SEVEN_SETUP, 7, (4, 4)),
        )
        for observation, mines, cursor in fixtures:
            with self.subTest(observation=observation):
                self.compare_state(observation, mines, cursor)

    def test_fixed_expert_complete_public_trajectories_match(self):
        kinds, actions, outcomes = set(), set(), set()
        self.compared_states = 0
        self.game_state_counts = {}
        for game_index in (0, 1, 2, 3, 100000):
            board = generate_board(EXPERT_GENERAL_V1, game_index)
            engine = MinesweeperEngine(30, 16, 99)
            engine.reset_with_mines(30, 16, 99, board.mine_positions)
            engine.step(0, 0, Action.OPEN)
            cursor = (0, 0)
            count = 0
            while engine.status == GameStatus.PLAYING:
                with self.subTest(game_index=game_index, action_index=count + 1):
                    observation = engine.get_observation()
                    decision = self.compare_state(observation, 99, cursor)
                    kinds.add(decision.evidence.kind)
                    actions.add(decision.move.action)
                    engine.step(decision.move.x, decision.move.y, decision.move.action)
                    cursor = (decision.move.x, decision.move.y)
                    count += 1
                    self.assertLess(count, 600, "Planner must make public progress until terminal.")
            self.compared_states += count
            self.game_state_counts[game_index] = count
            outcomes.add(engine.status)
        self.assertEqual(kinds, set(DecisionKind))
        self.assertEqual(actions, {Action.OPEN, Action.FLAG, Action.CHORD})
        self.assertEqual(outcomes, {GameStatus.WON, GameStatus.LOST})


if __name__ == "__main__":
    unittest.main()
