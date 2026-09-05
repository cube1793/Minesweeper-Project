"""Exact probability fixtures expressed solely in public observation values."""

import inspect
import runpy
import sys
import types
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from fractions import Fraction
from math import comb
from unittest.mock import patch

import simple_algorithm
import simple_probability
from core_engine import Action, CellState
from simple_algorithm import (
    InconsistentObservationError,
    SimpleMove,
    build_constraints,
    choose_deterministic_move,
    infer_deterministic,
)
from simple_probability import (
    CellProbability,
    ProbabilityResult,
    calculate_probabilities,
    choose_probability_move,
)


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value

# a=(1,1), b=(2,1), c=(0,0), d=(3,0): a+b+c=1, a+b+d=1.
# The component has two one-mine assignments (a or b) and one two-mine
# assignment (c and d). Columns 4 and 5 contain four unconstrained cells.
VARIABLE_COMPONENT = ((H, 2, 2, H, H, H), (F, H, H, F, H, H))
VARIABLE_FRONTIER = ((0, 0), (3, 0), (1, 1), (2, 1))
FLOATING = ((4, 0), (5, 0), (4, 1), (5, 1))

# Two copies of the variable component, separated by flagged column 4.
# All six flags are known mines; no hidden cells are unconstrained.
TWO_COMPONENTS = (
    (H, 2, 2, H, F, H, 2, 2, H),
    (F, H, H, F, F, F, H, H, F),
)


def by_coordinate(result):
    return {cell.coordinate: cell for cell in result.probabilities}


class SimpleProbabilityTests(unittest.TestCase):
    def assert_worlds(self, result, total_worlds, mine_worlds):
        """Check counts, exact values, common denominator, and complete coverage."""
        self.assertEqual(result.total_worlds, total_worlds)
        self.assertIs(type(result.total_worlds), int)
        cells = by_coordinate(result)
        self.assertEqual(set(cells), set(mine_worlds))
        self.assertEqual(len(result.probabilities), len(mine_worlds))
        for coordinate, count in mine_worlds.items():
            with self.subTest(coordinate=coordinate):
                cell = cells[coordinate]
                self.assertEqual(cell.mine_worlds, count)
                self.assertEqual(cell.total_worlds, total_worlds)
                self.assertIs(type(cell.mine_worlds), int)
                self.assertIs(type(cell.total_worlds), int)
                self.assertIsInstance(cell.probability, Fraction)
                self.assertEqual(cell.probability, Fraction(count, total_worlds))

    def test_unconstrained_only_one_mine_two_hidden(self):
        result = calculate_probabilities([[H, H]], num_mines=1)

        self.assert_worlds(result, 2, {(0, 0): 1, (1, 0): 1})
        self.assertEqual(result.frontier_cells, ())
        self.assertEqual(result.unconstrained_cells, ((0, 0), (1, 0)))

    def test_unopened_grid_uses_fixed_layout_density(self):
        result = calculate_probabilities([[H] * 4 for _ in range(3)], 3)

        self.assert_worlds(
            result, comb(12, 3),
            {(x, y): comb(11, 2) for y in range(3) for x in range(4)},
        )
        self.assertEqual(
            {cell.probability for cell in result.probabilities}, {Fraction(1, 4)}
        )

    def test_large_unconstrained_counts_preserve_python_integer_precision(self):
        result = calculate_probabilities([[H] * 60], 30)

        self.assertGreater(result.total_worlds, 2**53)
        self.assert_worlds(
            result, comb(60, 30), {(x, 0): comb(59, 29) for x in range(60)}
        )

    def test_simple_fifty_fifty_constraint_without_unconstrained_cells(self):
        result = calculate_probabilities([[H, 1, H]], 1)

        self.assert_worlds(result, 2, {(0, 0): 1, (2, 0): 1})
        self.assertEqual(result.frontier_cells, ((0, 0), (2, 0)))
        self.assertEqual(result.unconstrained_cells, ())

    def test_flags_reduce_both_local_and_global_mine_counts(self):
        result = calculate_probabilities([[F, 2, H], [H, H, H]], 2)

        self.assert_worlds(
            result, 4, {(2, 0): 1, (0, 1): 1, (1, 1): 1, (2, 1): 1}
        )
        self.assertNotIn((0, 0), by_coordinate(result))
        self.assertNotIn((1, 0), by_coordinate(result))

    def test_nonadjacent_flags_also_reduce_global_remaining_mines(self):
        result = calculate_probabilities([[F, H, H, H]], 2)

        self.assert_worlds(result, 3, {(1, 0): 1, (2, 0): 1, (3, 0): 1})
        self.assertEqual(result.frontier_cells, ())

    def test_frontier_and_floating_cells_are_all_present_in_reading_order(self):
        result = calculate_probabilities(VARIABLE_COMPONENT, 4)

        self.assertEqual(result.frontier_cells, VARIABLE_FRONTIER)
        self.assertEqual(result.unconstrained_cells, FLOATING)
        self.assertEqual(
            tuple(cell.coordinate for cell in result.probabilities),
            ((0, 0), (3, 0), (4, 0), (5, 0), (1, 1), (2, 1), (4, 1), (5, 1)),
        )

    def test_variable_component_uses_complete_board_binomial_weights(self):
        constraints = build_constraints(VARIABLE_COMPONENT)
        self.assertEqual(
            [(c.remaining_mines, c.hidden_cells) for c in constraints],
            [(1, {(0, 0), (1, 1), (2, 1)}),
             (1, {(3, 0), (1, 1), (2, 1)})],
        )
        result = calculate_probabilities(VARIABLE_COMPONENT, 4)

        # R=2: the two k=1 assignments each receive C(4,1)=4 worlds;
        # the k=2 assignment receives C(4,0)=1. Local 1/3 is incorrect.
        expected = {(0, 0): 1, (3, 0): 1, (1, 1): 4, (2, 1): 4}
        expected.update({cell: 2 for cell in FLOATING})
        self.assert_worlds(result, 9, expected)
        self.assertNotEqual(by_coordinate(result)[(1, 1)].probability, Fraction(1, 3))

    def test_specific_floating_cell_uses_choose_u_minus_one_r_minus_one(self):
        result = calculate_probabilities(VARIABLE_COMPONENT, 5)

        # R=3: denominator = 2*C(4,2)+C(4,1)=16.
        # Each floating numerator = 2*C(3,1)+C(3,0)=7.
        expected = {(0, 0): 4, (3, 0): 4, (1, 1): 6, (2, 1): 6}
        expected.update({cell: 7 for cell in FLOATING})
        self.assert_worlds(result, 16, expected)

    def test_zero_floating_mines_boundary_is_exact(self):
        result = calculate_probabilities([[H, 1, H, H, H]], 1)

        self.assert_worlds(result, 2, {(0, 0): 1, (2, 0): 1, (3, 0): 0, (4, 0): 0})
        self.assertEqual(choose_probability_move(result), SimpleMove(Action.OPEN, 3, 0))

    def test_all_floating_cells_mined_boundary_is_exact(self):
        result = calculate_probabilities([[H, 1, H, H, H]], 3)

        self.assert_worlds(result, 2, {(0, 0): 1, (2, 0): 1, (3, 0): 2, (4, 0): 2})

    def test_component_membership_uses_constraint_overlap_not_cell_adjacency(self):
        observation = [[H, H, 1, H, H, 1, H, H]]
        components = simple_probability._split_components(build_constraints(observation))

        # Hidden cells (3,0) and (4,0) are adjacent but share no constraint.
        self.assertEqual(
            tuple(component.cells for component in components),
            (((1, 0), (3, 0)), ((4, 0), (6, 0))),
        )
        result = calculate_probabilities(observation, 2)
        self.assert_worlds(
            result, 4,
            {(0, 0): 0, (1, 0): 2, (3, 0): 2, (4, 0): 2, (6, 0): 2, (7, 0): 0},
        )

    def test_overlapping_constraints_form_one_component_with_count_histograms(self):
        components = simple_probability._split_components(build_constraints(VARIABLE_COMPONENT))

        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].cells, VARIABLE_FRONTIER)
        counts = simple_probability._enumerate_component(components[0])
        self.assertEqual(counts.ways, {1: 2, 2: 1})
        expected = {(0, 0): {2: 1}, (3, 0): {2: 1},
                    (1, 1): {1: 1}, (2, 1): {1: 1}}
        for cell, histogram in expected.items():
            self.assertEqual(
                {k: count for k, count in counts.mine_ways[cell].items() if count},
                histogram,
            )
            self.assertTrue(all(type(count) is int for count in counts.mine_ways[cell].values()))

    def test_independent_variable_components_are_globally_coupled(self):
        components = simple_probability._split_components(build_constraints(TWO_COMPONENTS))
        self.assertEqual(len(components), 2)
        result = calculate_probabilities(TWO_COMPONENTS, 9)

        # F=6, R=3 requires (k_left,k_right)=(1,2) or (2,1).
        # Each contributes two worlds; local unweighted thirds are incorrect.
        expected = {
            (0, 0): 2, (3, 0): 2, (5, 0): 2, (8, 0): 2,
            (1, 1): 1, (2, 1): 1, (6, 1): 1, (7, 1): 1,
        }
        self.assert_worlds(result, 4, expected)
        self.assertEqual(result.unconstrained_cells, ())

    def test_many_components_count_worlds_without_assignment_cartesian_product(self):
        observation = [[H, 1, H] * 70]
        result = calculate_probabilities(observation, 70)

        self.assertEqual(
            len(simple_probability._split_components(build_constraints(observation))),
            70,
        )
        self.assert_worlds(
            result, 2**70,
            {(x, 0): 2**69 for x in range(210) if x % 3 != 1},
        )

    def test_large_forced_component_prunes_both_bounds_without_recursion_limit(self):
        width = 1100
        for mine_value in (0, 1):
            with self.subTest(mine_value=mine_value):
                clues = [2 * mine_value] + [3 * mine_value] * (width - 2)
                clues.append(2 * mine_value)
                observation = [clues, [H] * width]
                self.assertEqual(
                    len(simple_probability._split_components(build_constraints(observation))),
                    1,
                )

                result = calculate_probabilities(observation, width * mine_value)

                self.assert_worlds(
                    result, 1, {(x, 1): mine_value for x in range(width)}
                )

    def test_global_certainty_without_stage_one_inference_prioritizes_flag_over_safe_open(self):
        observation = ((H, 2, 2, H), (F, H, H, F))
        deterministic = infer_deterministic(build_constraints(observation))
        self.assertIsNone(choose_deterministic_move(deterministic))

        result = calculate_probabilities(observation, 4)

        self.assert_worlds(result, 1, {(0, 0): 1, (3, 0): 1, (1, 1): 0, (2, 1): 0})
        self.assertEqual(choose_probability_move(result), SimpleMove(Action.FLAG, 0, 0))

    def test_probability_only_certain_mines_are_flagged_before_uncertain_cells(self):
        observation = [[H, H, H], [H, H, 1]]
        deterministic = infer_deterministic(build_constraints(observation))
        self.assertIsNone(choose_deterministic_move(deterministic))

        result = calculate_probabilities(observation, 3)

        self.assert_worlds(
            result, 3, {(0, 0): 3, (1, 0): 1, (2, 0): 1, (0, 1): 3, (1, 1): 1}
        )
        self.assertEqual(choose_probability_move(result), SimpleMove(Action.FLAG, 0, 0))

    def test_multiple_components_and_floating_are_weighted_together(self):
        observation = tuple(tuple(row) + (H, H) for row in TWO_COMPONENTS)
        result = calculate_probabilities(observation, 10)

        # R=4, U=4. Combined component histogram is {2:4,3:4,4:1}.
        # Total=4*C(4,2)+4*C(4,1)+C(4,0)=41.
        # Shared-cell numerator=2*C(4,2)+C(4,1)=16.
        # Private-cell numerator=2*C(4,1)+C(4,0)=9.
        # Floating numerator=4*C(3,1)+4*C(3,0)=16.
        expected = {
            (0, 0): 9, (3, 0): 9, (5, 0): 9, (8, 0): 9,
            (1, 1): 16, (2, 1): 16, (6, 1): 16, (7, 1): 16,
            (9, 0): 16, (10, 0): 16, (9, 1): 16, (10, 1): 16,
        }
        self.assert_worlds(result, 41, expected)

    def test_no_hidden_cells_has_one_complete_world_and_no_move(self):
        for observation, total_mines in (([[0]], 0), ([[1, F]], 1), ([[F, F]], 2)):
            with self.subTest(observation=observation):
                result = calculate_probabilities(observation, total_mines)
                self.assert_worlds(result, 1, {})
                self.assertEqual(result.frontier_cells, ())
                self.assertEqual(result.unconstrained_cells, ())
                self.assertIsNone(choose_probability_move(result))

    def test_satisfied_empty_constraints_do_not_form_components(self):
        constraints = build_constraints([[1, F]])

        self.assertEqual(len(constraints), 1)
        self.assertEqual(simple_probability._split_components(constraints), ())

    def test_unconstrained_zero_and_all_mines(self):
        for num_mines in (0, 3):
            with self.subTest(num_mines=num_mines):
                result = calculate_probabilities([[H, H, H]], num_mines)
                self.assert_worlds(
                    result, 1, {(x, 0): int(num_mines == 3) for x in range(3)}
                )

    def test_inconsistent_component_with_no_direct_local_inferences_raises(self):
        # Hidden variables satisfy a+b=1, a+c=1, b+c=1: impossible in 0/1.
        observation = [[H, 2, H], [3, F, 3], [F, H, F]]
        deterministic = infer_deterministic(build_constraints(observation))
        self.assertIsNone(choose_deterministic_move(deterministic))

        with self.assertRaises(InconsistentObservationError):
            calculate_probabilities(observation, 4)

    def test_individually_satisfiable_components_with_impossible_total_raise(self):
        # Each component must contain one mine, but R=1.
        with self.assertRaises(InconsistentObservationError):
            calculate_probabilities([[1, H, H, 1]], 1)

    def test_valid_variable_component_cannot_satisfy_impossible_global_total(self):
        # Hidden count is four, but this component can only use one or two mines.
        with self.assertRaises(InconsistentObservationError):
            calculate_probabilities(((H, 2, 2, H), (F, H, H, F)), 5)

    def test_more_flags_than_total_mines_raises(self):
        with self.assertRaises(InconsistentObservationError):
            calculate_probabilities([[F, H]], 0)

    def test_more_remaining_mines_than_hidden_cells_raises(self):
        with self.assertRaises(InconsistentObservationError):
            calculate_probabilities([[H, H]], 3)

    def test_local_clue_inconsistencies_reuse_stage_one_error(self):
        for observation, total_mines in (([[0, F, H]], 1), ([[2, H]], 1), ([[1]], 0)):
            with self.subTest(observation=observation):
                with self.assertRaises(InconsistentObservationError):
                    calculate_probabilities(observation, total_mines)

    def test_invalid_total_mine_count_types_raise(self):
        for count in (True, False, 1.0, "1", None):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    calculate_probabilities([[H, H]], count)
        with self.assertRaises(InconsistentObservationError):
            calculate_probabilities([[H, H]], -1)

    def test_malformed_or_nonpublic_observation_values_raise(self):
        observations = ([], [[]], [[H], []], [[H], [H, H]], [H], None)
        for observation in observations:
            with self.subTest(observation=observation):
                with self.assertRaises(ValueError):
                    calculate_probabilities(observation, 0)
        for value in (-6, -5, -4, -1, 9, True, 0.0, "0", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_probabilities([[H, value]], 0)

    def test_selector_chooses_lowest_probability_frontier_cell(self):
        result = calculate_probabilities(VARIABLE_COMPONENT, 4)

        self.assertEqual(choose_probability_move(result), SimpleMove(Action.OPEN, 0, 0))

    def test_selector_includes_safer_unconstrained_cells(self):
        # Frontier=1/2, each of three floating cells=1/3.
        result = calculate_probabilities([[H, 1, H, H, H, H]], 2)

        self.assertEqual(choose_probability_move(result), SimpleMove(Action.OPEN, 3, 0))
        self.assertEqual(by_coordinate(result)[(3, 0)].probability, Fraction(1, 3))

    def test_selector_exact_tie_uses_y_then_x(self):
        result = calculate_probabilities([[F, H, H], [H, H, H]], 2)

        self.assertEqual(choose_probability_move(result), SimpleMove(Action.OPEN, 1, 0))

    def test_selector_compares_exact_ratios_below_float_precision(self):
        denominator = 2**61
        result = ProbabilityResult(
            total_worlds=denominator,
            probabilities=(
                CellProbability((0, 0), 2**60 + 1, denominator),
                CellProbability((1, 0), 2**60, denominator),
            ),
            frontier_cells=((0, 0), (1, 0)),
            unconstrained_cells=(),
        )

        self.assertEqual(choose_probability_move(result), SimpleMove(Action.OPEN, 1, 0))

    def test_selector_returns_flag_when_every_cell_is_certain_mine(self):
        result = calculate_probabilities([[H, H]], 2)

        self.assertEqual(choose_probability_move(result), SimpleMove(Action.FLAG, 0, 0))

    def test_selector_certain_mine_tie_uses_y_then_x_regardless_of_input_order(self):
        cells = ((0, 1), (2, 0), (1, 0))
        for ordered_cells in (cells, tuple(reversed(cells))):
            with self.subTest(ordered_cells=ordered_cells):
                result = ProbabilityResult(
                    total_worlds=1,
                    probabilities=tuple(CellProbability(cell, 1, 1) for cell in ordered_cells),
                    frontier_cells=ordered_cells,
                    unconstrained_cells=(),
                )

                self.assertEqual(
                    choose_probability_move(result), SimpleMove(Action.FLAG, 1, 0)
                )

    def test_selector_requires_exact_certainty_below_float_precision(self):
        denominator = 2**61
        result = ProbabilityResult(
            total_worlds=denominator,
            probabilities=(
                CellProbability((0, 0), denominator - 1, denominator),
                CellProbability((1, 0), denominator, denominator),
            ),
            frontier_cells=((0, 0), (1, 0)),
            unconstrained_cells=(),
        )

        self.assertEqual(choose_probability_move(result), SimpleMove(Action.FLAG, 1, 0))

    def test_probability_models_are_immutable_and_preserve_unreduced_counts(self):
        result = calculate_probabilities([[H] * 4], 2)
        cell = result.probabilities[0]

        self.assertEqual((cell.mine_worlds, cell.total_worlds), (3, 6))
        self.assertEqual(cell.probability, Fraction(1, 2))
        self.assertIsInstance(result.probabilities, tuple)
        self.assertIsInstance(result.frontier_cells, tuple)
        self.assertIsInstance(result.unconstrained_cells, tuple)
        with self.assertRaises(FrozenInstanceError):
            cell.mine_worlds = 0
        with self.assertRaises(FrozenInstanceError):
            cell.coordinate = (10, 10)
        with self.assertRaises(FrozenInstanceError):
            result.total_worlds = 1
        with self.assertRaises(FrozenInstanceError):
            result.probabilities = ()

    def test_probability_models_copy_mutable_constructor_inputs(self):
        coordinate = [0, 0]
        cell = CellProbability(coordinate, 1, 2)
        probabilities = [cell]
        region = [[0, 0]]
        result = ProbabilityResult(2, probabilities, region, [])

        coordinate[0] = 10
        probabilities.clear()
        region[0][0] = 20
        region.append([1, 1])

        self.assertEqual(cell.coordinate, (0, 0))
        self.assertEqual(result.probabilities, (cell,))
        self.assertEqual(result.frontier_cells, ((0, 0),))
        self.assertEqual(result.unconstrained_cells, ())

    def test_repeated_calls_are_deterministic_and_do_not_mutate_observation(self):
        observation = [list(row) for row in VARIABLE_COMPONENT]
        original = deepcopy(observation)
        expected = calculate_probabilities(observation, 5)
        expected_move = choose_probability_move(expected)

        for _ in range(10):
            result = calculate_probabilities(observation, 5)
            self.assertEqual(result, expected)
            self.assertEqual(choose_probability_move(result), expected_move)
            self.assertEqual(observation, original)

    def test_api_accepts_only_observation_and_public_total_mine_count(self):
        self.assertEqual(
            tuple(inspect.signature(calculate_probabilities).parameters),
            ("observation", "num_mines"),
        )

    def test_probability_solver_runs_with_only_public_engine_enums(self):
        public_types = types.ModuleType("core_engine")
        public_types.Action = Action
        public_types.CellState = CellState
        unavailable_snapshot = types.ModuleType("board_snapshot")
        unavailable_analyzer = types.ModuleType("board_analyzer")

        with patch.dict(sys.modules, {
            "core_engine": public_types,
            "board_snapshot": unavailable_snapshot,
            "board_analyzer": unavailable_analyzer,
        }):
            public_algorithm = types.ModuleType("simple_algorithm")
            public_algorithm.__dict__.update(runpy.run_path(simple_algorithm.__file__))
            with patch.dict(sys.modules, {"simple_algorithm": public_algorithm}):
                solver = runpy.run_path(simple_probability.__file__)
                result = solver["calculate_probabilities"](VARIABLE_COMPONENT, 4)
                move = solver["choose_probability_move"](result)

        self.assertEqual(result.total_worlds, 9)
        self.assertEqual(by_coordinate(result)[(1, 1)].probability, Fraction(4, 9))
        self.assertEqual((move.action, move.x, move.y), (Action.OPEN, 0, 0))


if __name__ == "__main__":
    unittest.main()
