"""Bounded Unit 1 tests, including a direct complete-placement oracle.

The fixed public corpus below is registered before execution. No random
search or external fixtures are used. Each oracle board has at most twelve
unrevealed cells, counting physical flags as unrevealed. The run driver also
enforces a conservative limit of 512 solver calls (base plus joint queries).
"""

import inspect
import runpy
import sys
import types
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from fractions import Fraction
from itertools import combinations
from math import comb, prod
from unittest.mock import patch

import simple_algorithm
import simple_probability
import stage4_opening as opening
from core_engine import Action, CellState, GameStatus, MinesweeperEngine


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value
TOY = ((H, 1, H, H, H),)
SEPARATE_COMPONENTS = ((H, 1, H, 1, H, H, H, 1, H, 1, H, H),)
PUBLIC_CORPUS = (
    ("five_cell_opening", TOY, 1),
    ("five_cell_remaining_budget", TOY, 3),
    ("singleton_zero", ((H,),), 0),
    ("singleton_mine", ((H,),), 1),
    ("corner_joint_impossible", ((H, H), (H, H)), 1),
    ("two_dimensional_edges", ((H, H, H), (H, H, H)), 2),
    ("zero_mines", ((H, H, H), (H, H, H)), 0),
    ("safe_number_unique_world", ((0, H, H),), 1),
    ("contradictory_clues", ((0, H, 1),), 1),
    ("impossible_mine_budget", ((H, H),), 3),
    ("opened_only", ((0,),), 0),
    ("overlap_one_mine", ((1, H, 1), (H, H, H)), 1),
    ("overlap_two_mines", ((1, H, 1), (H, H, H)), 2),
    ("positive_correlated_zero", ((H, 1, H, 1, H, H, H),), 2),
    ("correlated_budget_change", ((H, 1, H, 1, H, H, H),), 3),
    ("separate_components_budget_2", SEPARATE_COMPONENTS, 2),
    ("separate_components_budget_3", SEPARATE_COMPONENTS, 3),
    ("separate_components_budget_4", SEPARATE_COMPONENTS, 4),
    ("unproved_distant_flag", ((F, H, H, H),), 1),
    ("unproved_adjacent_flag", ((F, 1, H, H, H),), 1),
    ("locally_impossible_clue", ((2, H),), 1),
    ("overlapping_edge_clues", ((H, H, 1), (H, 2, H)), 2),
    ("public_zero_and_edge", ((0, H, H, H), (H, H, 1, H)), 1),
    ("all_flags_reproved_safe", ((F, 0, F),), 0),
)
ORACLE_COMPARISONS = []
ENGINE_EXAMPLE = {}
BOUNDARY_EVIDENCE = {}
LARGE_INTEGER_COMPARISON = {}


def direct_placement_oracle(observation, num_mines):
    """Enumerate complete mine subsets and compare public numbers directly.

    This code never constructs a virtual zero observation and never calls a
    product constraint builder, probability helper, or existing test oracle.
    Flags are simply unresolved cells. Opened cells cannot contain mines.
    """
    unresolved = tuple(
        (x, y) for y, row in enumerate(observation)
        for x, value in enumerate(row) if value in (H, F)
    )
    if len(unresolved) > 12:
        raise ValueError("Oracle corpus exceeds the twelve-cell bound.")
    clues = tuple(
        (x, y, value) for y, row in enumerate(observation)
        for x, value in enumerate(row) if 0 <= value <= 8
    )
    counts = {cell: [0, 0] for cell in unresolved}
    total = 0
    if not 0 <= num_mines <= len(unresolved):
        return total, counts
    for selected in combinations(unresolved, num_mines):
        if any(
            sum(abs(mx - x) <= 1 and abs(my - y) <= 1 for mx, my in selected) != clue
            for x, y, clue in clues
        ):
            continue
        total += 1
        for x, y in unresolved:
            counts[(x, y)][0] += (x, y) in selected
            counts[(x, y)][1] += not any(
                abs(mx - x) <= 1 and abs(my - y) <= 1 for mx, my in selected
            )
    return total, counts


def all_coordinates(observation):
    return [(x, y) for y, row in enumerate(observation) for x in range(len(row))]


def evidence_by_cell(result):
    return {item.coordinate: item for item in result.evidence}


class OpeningOracleTests(unittest.TestCase):
    def test_registered_direct_oracle_corpus(self):
        for name, observation, num_mines in PUBLIC_CORPUS:
            with self.subTest(case=name):
                denominator, expected = direct_placement_oracle(observation, num_mines)
                result = opening.analyze_openings(observation, num_mines, all_coordinates(observation))
                record = {
                    "case": name, "observation": observation, "num_mines": num_mines,
                    "expected_D": denominator, "actual_D": result.total_worlds,
                    "status": result.status, "cells": [],
                }
                ORACLE_COMPARISONS.append(record)
                self.assertEqual(result.total_worlds, denominator)
                if denominator == 0:
                    self.assertEqual(result.status, "INCONSISTENT_INPUT")
                    self.assertEqual(result.decision, "DEFER")
                    self.assertTrue(all(item.zero_worlds is None for item in result.evidence))
                    continue
                self.assertEqual(result.status, "COMPLETE")
                for item in result.evidence:
                    x, y = item.coordinate
                    if observation[y][x] != H:
                        self.assertEqual(item.status, "EXCLUDED")
                        self.assertIsNone(item.zero_worlds)
                        continue
                    mine_count, zero_count = expected[item.coordinate]
                    record["cells"].append({
                        "coordinate": item.coordinate,
                        "expected": [denominator, mine_count, zero_count],
                        "actual": [item.total_worlds, item.mine_worlds, item.zero_worlds],
                    })
                    self.assertEqual(item.status, "EXACT")
                    self.assertEqual(item.mine_worlds, mine_count)
                    self.assertEqual(item.zero_worlds, zero_count)
                    self.assertIs(type(item.total_worlds), int)
                    self.assertIs(type(item.mine_worlds), int)
                    self.assertIs(type(item.zero_worlds), int)
                    self.assertEqual(item.mine_probability, Fraction(mine_count, denominator))
                    self.assertEqual(item.zero_probability, Fraction(zero_count, denominator))
                    self.assertLessEqual(0, item.zero_worlds)
                    self.assertLessEqual(item.zero_worlds, denominator - item.mine_worlds)
                    self.assertLessEqual(denominator - item.mine_worlds, denominator)
                    self.assertEqual(item.zero_status == "CERTAIN_ZERO", zero_count == denominator)

    def test_joint_zero_differs_from_product_and_conditional_probability(self):
        observation = ((H, 1, H, 1, H, H, H),)
        result = opening.analyze_openings(observation, 2, [(5, 0), (6, 0)])
        cells = evidence_by_cell(result)
        independent_product = prod(1 - cells[(x, 0)].mine_probability for x in (5, 6))
        self.assertEqual(result.total_worlds, 3)
        self.assertEqual(cells[(6, 0)].zero_probability, Fraction(1, 3))
        self.assertEqual(independent_product, Fraction(4, 9))
        self.assertNotEqual(cells[(6, 0)].zero_probability, independent_product)
        conditional_zero_given_safe = cells[(6, 0)].zero_probability / (1 - cells[(6, 0)].mine_probability)
        self.assertEqual(conditional_zero_given_safe, Fraction(1, 2))
        self.assertNotEqual(cells[(6, 0)].zero_probability, conditional_zero_given_safe)

    def test_global_budget_couples_separate_components_and_floating_cells(self):
        results = [opening.analyze_openings(SEPARATE_COMPONENTS, count, [(0, 0), (2, 0), (5, 0)])
                   for count in (2, 3, 4)]
        self.assertEqual([result.total_worlds for result in results], [1, 4, 6])
        middle = evidence_by_cell(results[1])
        self.assertEqual(middle[(0, 0)].mine_probability, Fraction(1, 4))
        self.assertEqual(middle[(2, 0)].mine_probability, Fraction(3, 4))
        self.assertEqual(middle[(5, 0)].mine_probability, Fraction(1, 4))
        self.assertEqual(evidence_by_cell(results[0])[(5, 0)].mine_probability, 0)
        self.assertEqual(evidence_by_cell(results[2])[(5, 0)].mine_probability, Fraction(1, 2))

    def test_large_integer_binomial_boundary(self):
        result = opening.analyze_openings(((H,) * 80,), 20, [(0, 0), (40, 0)])
        self.assertGreater(result.total_worlds, 2**53)
        self.assertEqual(result.total_worlds, comb(80, 20))
        cells = evidence_by_cell(result)
        for coordinate, available in (((0, 0), 78), ((40, 0), 77)):
            item = cells[coordinate]
            self.assertEqual(item.mine_worlds, comb(79, 19))
            self.assertEqual(item.zero_worlds, comb(available, 20))
        LARGE_INTEGER_COMPARISON.update({
            "formula_D": "C(80,20)", "D": result.total_worlds,
            "formula_M": "C(79,19)", "M": cells[(0, 0)].mine_worlds,
            "corner_Z_formula": "C(78,20)", "corner_Z": cells[(0, 0)].zero_worlds,
            "interior_Z_formula": "C(77,20)", "interior_Z": cells[(40, 0)].zero_worlds,
        })


class OpeningContractTests(unittest.TestCase):
    def test_safe_zero_possible_and_impossible_are_distinct(self):
        cells = evidence_by_cell(opening.analyze_openings(TOY, 1, all_coordinates(TOY)))
        self.assertTrue(cells[(3, 0)].certain_safe)
        self.assertEqual(cells[(3, 0)].zero_status, "POSSIBLE_ZERO")
        self.assertEqual(cells[(4, 0)].zero_status, "CERTAIN_ZERO")
        unique = evidence_by_cell(opening.analyze_openings(((0, H, H),), 1, [(1, 0), (2, 0)]))
        self.assertTrue(unique[(1, 0)].certain_safe)
        self.assertEqual(unique[(1, 0)].zero_status, "ZERO_IMPOSSIBLE")
        self.assertEqual(unique[(2, 0)].mine_probability, 1)

    def test_physical_flags_supply_no_mine_facts(self):
        observation = ((F, H, H, H),)
        result = opening.analyze_openings(observation, 1, all_coordinates(observation), allow_guess=True)
        cells = evidence_by_cell(result)
        self.assertEqual(result.total_worlds, 4)
        self.assertEqual(cells[(3, 0)].mine_probability, Fraction(1, 4))
        self.assertEqual(cells[(3, 0)].zero_probability, Fraction(1, 2))
        self.assertEqual(cells[(0, 0)].reason, "PHYSICALLY_FLAGGED")
        self.assertNotIn((0, 0), result.admissible_candidates)
        zero = opening.analyze_openings(((F, H, H),), 0, [(0, 0), (2, 0)])
        self.assertEqual(zero.total_worlds, 1)
        self.assertEqual(zero.query_order, ((2, 0),))

    def test_inputs_and_independent_virtual_observations_are_immutable(self):
        observation = [[F, 1, H, H, H]]
        candidates = [[4, 0], [3, 0], [2, 0], [0, 0], [1, 0], [4, 0]]
        original = deepcopy((observation, candidates))
        calls = []
        real_solver = opening.calculate_probabilities

        def capture(grid, num_mines):
            calls.append(grid)
            return real_solver(grid, num_mines)

        with patch.object(opening, "calculate_probabilities", side_effect=capture):
            result = opening.analyze_openings(observation, 1, candidates)
        self.assertEqual((observation, candidates), original)
        self.assertEqual(calls[0], ((H, 1, H, H, H),))
        self.assertEqual(len(calls), 4)
        self.assertEqual(len({id(grid) for grid in calls}), 4)
        for grid in calls:
            self.assertIs(type(grid), tuple)
            self.assertIs(type(grid[0]), tuple)
            self.assertEqual(grid[0][1], 1)
        for grid, target in zip(calls[1:], (2, 3, 4)):
            self.assertEqual(grid[0][target], 0)
            self.assertEqual(sum(value == 0 for value in grid[0]), 1)
        observation[0][4] = 0
        candidates[0][0] = 0
        self.assertEqual(result.identity.observation, ((F, 1, H, H, H),))
        self.assertEqual(result.identity.candidates, ((0, 0), (1, 0), (2, 0), (3, 0), (4, 0)))
        with self.assertRaises(FrozenInstanceError):
            result.total_worlds = 0
        with self.assertRaises(FrozenInstanceError):
            result.identity.mode = "changed"
        with self.assertRaises(FrozenInstanceError):
            result.evidence[-1].zero_worlds = 0

    def test_identity_binds_observation_mines_candidates_mode_and_guess(self):
        args = (TOY, 1, [(3, 0), (4, 0)])
        base = opening.analyze_openings(*args)
        variants = (
            opening.analyze_openings(((H, 1, H, 1, H),), 1, args[2]),
            opening.analyze_openings(TOY, 2, args[2]),
            opening.analyze_openings(TOY, 1, [(4, 0)]),
            opening.analyze_openings(*args, mode=opening.EFFICIENCY_PRIORITIZED),
            opening.analyze_openings(*args, allow_guess=True),
        )
        for result in variants:
            self.assertNotEqual(result.identity, base.identity)
        self.assertEqual(evidence_by_cell(base)[(4, 0)].zero_worlds, 2)
        self.assertEqual(evidence_by_cell(variants[0])[(4, 0)].zero_worlds, 1)
        self.assertEqual(evidence_by_cell(variants[1])[(4, 0)].zero_worlds, 0)
        self.assertEqual(opening.analyze_openings(*args), base)
        flag_variant = opening.analyze_openings(((H, 1, H, H, F),), 1, args[2])
        self.assertNotEqual(flag_variant.identity, base.identity)
        self.assertNotIn((4, 0), flag_variant.query_order)

    def test_candidate_order_and_duplicates_do_not_change_result(self):
        expected = opening.analyze_openings(TOY, 1, [(0, 0), (2, 0), (3, 0), (4, 0)])
        actual = opening.analyze_openings(TOY, 1, [[4, 0], [3, 0], [2, 0], [0, 0], [4, 0]])
        self.assertEqual(expected, actual)

    def test_malformed_inputs_raise_separately_from_inconsistency(self):
        for grid in (None, [], [[]], [[H], [H, H]], [[True]], [[-3.0]], [[-5]], [[9]]):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                opening.analyze_openings(grid, 0, [])
        for mines in (True, 1.0, "1", None):
            with self.subTest(mines=mines), self.assertRaises(ValueError):
                opening.analyze_openings(((H,),), mines, [])
        for candidates in (None, [(1, 0)], [(-1, 0)], [(False, 0)], [(0, 0, 0)], [0]):
            with self.subTest(candidates=candidates), self.assertRaises(ValueError):
                opening.analyze_openings(((H,),), 0, candidates)
        with self.assertRaises(ValueError):
            opening.analyze_openings(TOY, 1, [], mode="unknown")
        with self.assertRaises(ValueError):
            opening.analyze_openings(TOY, 1, [], allow_guess=1)

    def test_original_inconsistency_defers_without_zero_numerators(self):
        result = opening.analyze_openings(((0, H, 1),), 1, [(1, 0)])
        self.assertEqual(result.status, "INCONSISTENT_INPUT")
        self.assertEqual(result.decision, "DEFER")
        self.assertIsNone(result.evidence[0].zero_probability)
        self.assertFalse(result.evidence[0].certain_safe)

    def test_base_failure_is_not_evaluated(self):
        with patch.object(opening, "calculate_probabilities", side_effect=RuntimeError("registered base failure")):
            result = opening.analyze_openings(TOY, 1, [(4, 0)])
        self.assertEqual(result.status, "NOT_EVALUATED")
        self.assertIn("RuntimeError", result.reason)
        self.assertIsNone(result.total_worlds)
        self.assertIsNone(result.evidence[0].zero_worlds)
        self.assertEqual(result.decision, "DEFER")

    def test_one_joint_failure_preserves_other_queries_and_counts(self):
        real_solver = opening.calculate_probabilities

        def fail_first_zero(grid, mines):
            if grid[0][0] == 0:
                raise TimeoutError("registered joint failure")
            return real_solver(grid, mines)

        with patch.object(opening, "calculate_probabilities", side_effect=fail_first_zero):
            result = opening.analyze_openings(TOY, 1, [(0, 0), (4, 0)])
        cells = evidence_by_cell(result)
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual((cells[(0, 0)].total_worlds, cells[(0, 0)].mine_worlds), (2, 1))
        self.assertIsNone(cells[(0, 0)].zero_worlds)
        self.assertEqual(cells[(0, 0)].zero_status, "NOT_EVALUATED")
        self.assertEqual(cells[(4, 0)].zero_status, "CERTAIN_ZERO")
        self.assertEqual(result.query_order, ((4, 0),))

    def test_invalid_joint_counts_cannot_become_certainty(self):
        base = simple_probability.calculate_probabilities(TOY, 1)
        with patch.object(opening, "calculate_probabilities", side_effect=[base, types.SimpleNamespace(total_worlds=3)]):
            result = opening.analyze_openings(TOY, 1, [(4, 0)])
        self.assertEqual(result.status, "PARTIAL")
        self.assertIsNone(result.evidence[0].zero_worlds)
        self.assertIn("ValueError", result.evidence[0].reason)
        self.assertEqual(result.decision, "DEFER")

    def test_certainty_and_order_use_exact_integers(self):
        denominator = 2**60
        evidence = opening.OpeningEvidence((0, 0), "EXACT", "constructed precision boundary",
                                          denominator, 0, denominator - 1)
        self.assertEqual(float(evidence.zero_probability), 1.0)
        self.assertEqual(evidence.zero_status, "POSSIBLE_ZERO")
        self.assertTrue(evidence.certain_safe)
        for counts in ((0, 0, 0), (2, 1, 2), (2, -1, 0), (2, 0, -1), (2, 0, True)):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                opening.OpeningEvidence((0, 0), "EXACT", "invalid", *counts)


class OpeningModeTests(unittest.TestCase):
    def test_two_modes_have_distinct_risk_boundaries_and_zero_first(self):
        candidates = [(0, 0), (2, 0), (3, 0), (4, 0)]
        safety = opening.analyze_openings(TOY, 1, candidates, allow_guess=True)
        efficiency = opening.analyze_openings(TOY, 1, candidates,
                                             mode=opening.EFFICIENCY_PRIORITIZED, allow_guess=True)
        self.assertEqual(safety.admissible_candidates, ((3, 0), (4, 0)))
        self.assertEqual(safety.query_order, ((4, 0), (3, 0)))
        self.assertEqual(efficiency.admissible_candidates, tuple(candidates))
        self.assertEqual(efficiency.query_order, ((4, 0), (3, 0), (0, 0), (2, 0)))
        self.assertEqual(efficiency.exploratory_candidates, ((0, 0), (2, 0)))

    def test_guess_off_removes_risky_candidates_in_both_modes(self):
        for mode in (opening.SAFETY_PRESERVING, opening.EFFICIENCY_PRIORITIZED):
            with self.subTest(mode=mode):
                result = opening.analyze_openings(TOY, 1, [(0, 0), (2, 0), (3, 0), (4, 0)], mode=mode)
                self.assertEqual(result.admissible_candidates, ((3, 0), (4, 0)))
                risky_only = opening.analyze_openings(((H, H, H),), 1, [(0, 0)], mode=mode)
                self.assertEqual(risky_only.decision, "DEFER")
                self.assertEqual(risky_only.reason, "GUESS_DISABLED")

    def test_safety_uses_global_minimum_even_with_partial_queries(self):
        observation = ((H, 1, H, H, H, H),)
        missing = opening.analyze_openings(observation, 2, [(0, 0), (2, 0)], allow_guess=True)
        self.assertEqual(missing.global_minimum_risk, Fraction(1, 3))
        self.assertEqual(missing.global_minimum_cells, ((3, 0), (4, 0), (5, 0)))
        self.assertTrue(missing.is_candidate_subset)
        self.assertEqual(missing.decision, "DEFER")
        self.assertEqual(missing.reason, "GLOBAL_MINIMUM_NOT_QUERIED")
        included = opening.analyze_openings(observation, 2, [(0, 0), (5, 0)], allow_guess=True)
        self.assertEqual(included.query_order, ((5, 0),))
        self.assertTrue(included.is_candidate_subset)

    def test_safe_cell_outside_candidates_still_excludes_risk(self):
        result = opening.analyze_openings(TOY, 1, [(0, 0), (2, 0)], allow_guess=True)
        self.assertEqual(result.global_minimum_risk, 0)
        self.assertEqual(result.query_order, ())
        self.assertEqual(result.reason, "GLOBAL_MINIMUM_NOT_QUERIED")

    def test_efficiency_excludes_risky_zero_impossible_and_certain_mines(self):
        result = opening.analyze_openings(((H, H, H),), 1, [(0, 0), (1, 0), (2, 0)],
                                         mode=opening.EFFICIENCY_PRIORITIZED, allow_guess=True)
        self.assertEqual(result.query_order, ((0, 0), (2, 0)))
        for mode in (opening.SAFETY_PRESERVING, opening.EFFICIENCY_PRIORITIZED):
            dead = opening.analyze_openings(((H,),), 1, [(0, 0)], mode=mode, allow_guess=True)
            self.assertEqual(dead.decision, "DEFER")

    def test_proved_zero_components_reduce_duplicates_through_unqueried_cells(self):
        grid = ((H, H, H, H), (H, H, H, H))
        result = opening.analyze_openings(grid, 0, [(3, 1), (2, 0), (0, 0)])
        self.assertEqual(len(result.certain_zero_groups), 1)
        group = result.certain_zero_groups[0]
        self.assertEqual(len(group.cells), 8)
        self.assertEqual(group.candidate_cells, ((0, 0), (2, 0), (3, 1)))
        self.assertEqual(group.representative, (0, 0))
        self.assertEqual(result.query_order, ((0, 0),))
        self.assertTrue(result.is_candidate_subset)

    def test_proved_flag_zero_can_bridge_without_direct_open(self):
        result = opening.analyze_openings(((H, F, H),), 0, [(0, 0), (1, 0), (2, 0)])
        self.assertEqual(result.query_order, ((0, 0),))
        self.assertEqual(result.certain_zero_groups[0].cells, ((0, 0), (1, 0), (2, 0)))
        self.assertEqual(result.certain_zero_groups[0].candidate_cells, ((0, 0), (2, 0)))

    def test_possible_zeros_never_bridge_proved_components(self):
        grid = ((H, 1, H, 1, H),)
        result = opening.analyze_openings(grid, 1, [(0, 0), (2, 0), (4, 0)])
        self.assertEqual([group.cells for group in result.certain_zero_groups], [((0, 0),), ((4, 0),)])
        self.assertEqual(result.query_order, ((0, 0), (4, 0)))
        possible = opening.analyze_openings(((H, H, H, H, H),), 1, [(0, 0), (2, 0), (4, 0)],
                                           mode=opening.EFFICIENCY_PRIORITIZED, allow_guess=True)
        self.assertEqual(possible.certain_zero_groups, ())
        self.assertEqual(possible.query_order, ((0, 0), (4, 0), (2, 0)))

    def test_empty_and_excluded_candidates_defer(self):
        for candidates in ([], [(1, 0)]):
            result = opening.analyze_openings(TOY, 1, candidates)
            self.assertEqual(result.decision, "DEFER")
            self.assertTrue(result.is_candidate_subset)
        closed = opening.analyze_openings(((0,),), 0, [(0, 0)])
        self.assertEqual(closed.total_worlds, 1)
        self.assertFalse(closed.is_candidate_subset)
        self.assertIsNone(closed.global_minimum_risk)
        self.assertEqual(closed.evidence[0].reason, "ALREADY_OPEN")


class OpeningBoundaryAndEngineTests(unittest.TestCase):
    def test_public_only_api_runs_with_engine_enums_and_no_private_modules(self):
        parameters = tuple(inspect.signature(opening.analyze_openings).parameters)
        self.assertEqual(parameters, ("observation", "num_mines", "candidates", "mode", "allow_guess"))
        public_engine = types.ModuleType("core_engine")
        public_engine.Action = Action
        public_engine.CellState = CellState
        with patch.dict(sys.modules, {
            "core_engine": public_engine,
            "board_snapshot": types.ModuleType("board_snapshot"),
            "board_analyzer": types.ModuleType("board_analyzer"),
        }):
            public_algorithm = types.ModuleType("simple_algorithm")
            public_algorithm.__dict__.update(runpy.run_path(simple_algorithm.__file__))
            with patch.dict(sys.modules, {"simple_algorithm": public_algorithm}):
                public_probability = types.ModuleType("simple_probability")
                public_probability.__dict__.update(runpy.run_path(simple_probability.__file__))
                with patch.dict(sys.modules, {"simple_probability": public_probability}):
                    public_opening = runpy.run_path(opening.__file__)
                    result = public_opening["analyze_openings"](TOY, 1, [(3, 0), (4, 0)])
        self.assertEqual(result.query_order, ((4, 0), (3, 0)))
        BOUNDARY_EVIDENCE.update({
            "signature": parameters, "engine_stub": "Action and CellState enums only",
            "board_snapshot_and_analyzer": "empty modules during isolated call",
            "layout_or_3bv_passed_to_policy": False,
        })

    def test_same_public_observation_different_hidden_layouts_same_result(self):
        results = []
        with patch("core_engine.time", types.SimpleNamespace(perf_counter=lambda: 0.0)):
            for mine_x in (0, 2):
                evaluator = MinesweeperEngine(5, 1, 1)
                evaluator.reset_with_mines(5, 1, 1, [(mine_x, 0)])
                observation = evaluator.step(1, 0, Action.OPEN)[0]
                self.assertEqual(observation, [list(TOY[0])])
                results.append(opening.analyze_openings(observation, 1, [(0, 0), (2, 0), (3, 0), (4, 0)]))
        self.assertEqual(results[0], results[1])
        BOUNDARY_EVIDENCE["different_layouts_identical_public_result"] = True

    def test_real_engine_five_cell_input_reduction(self):
        routes = {"A": (1, 4, 0), "B": (1, 3, 0, 4)}
        with patch("core_engine.time", types.SimpleNamespace(perf_counter=lambda: 0.0)):
            for name, route in routes.items():
                evaluator = MinesweeperEngine(5, 1, 1)
                evaluator.reset_with_mines(5, 1, 1, [(2, 0)])
                steps = []
                for x in route:
                    observation, reward, terminated, truncated, info = evaluator.step(x, 0, Action.OPEN)
                    counter = evaluator.get_counter_snapshot()
                    steps.append({
                        "input": ["OPEN", x, 0], "observation": observation,
                        "status": evaluator.status.name, "terminated": terminated,
                        "truncated": truncated, "active_inputs": counter["active_clicks"],
                        "wasted_inputs": counter["wasted_clicks"],
                        "completed_3bv": counter["completed_3bv"],
                    })
                    if len(steps) == 1:
                        self.assertEqual(observation, [list(TOY[0])])
                        policy = opening.analyze_openings(observation, 1, [(0, 0), (2, 0), (3, 0), (4, 0)])
                        self.assertEqual(policy.total_worlds, 2)
                        self.assertEqual(policy.query_order[0], (4, 0))
                total_inputs = counter["active_clicks"] + counter["wasted_clicks"]
                ENGINE_EXAMPLE[name] = {
                    "evaluation_only_mines": [[2, 0]], "steps": steps,
                    "status": evaluator.status.name, "final_3bv_display": info["stats"]["bbbv"],
                    "total_inputs_including_prefix": total_inputs,
                    "common_prefix_inputs": 1, "suffix_inputs": total_inputs - 1,
                    "clock": "constant test clock; no timing or CPS measurement",
                }
                self.assertEqual(evaluator.status, GameStatus.WON)
                self.assertEqual(info["stats"]["bbbv"], "2/2")
                self.assertEqual(total_inputs, len(route))
        self.assertEqual(ENGINE_EXAMPLE["A"]["total_inputs_including_prefix"], 3)
        self.assertEqual(ENGINE_EXAMPLE["B"]["total_inputs_including_prefix"], 4)


if __name__ == "__main__":
    unittest.main()
