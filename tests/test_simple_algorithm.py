"""Observation-only solver tests; fixtures contain only visible cell values."""

import runpy
import sys
import types
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import simple_algorithm
from core_engine import Action, CellState
from simple_algorithm import (
    Constraint,
    InconsistentObservationError,
    InferenceResult,
    SimpleMove,
    build_constraints,
    choose_deterministic_move,
    infer_deterministic,
)


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value


class SimpleAlgorithmTests(unittest.TestCase):
    def test_matching_flags_make_all_remaining_neighbors_safe(self):
        observation = [[F, H, H], [H, 1, H], [H, H, H]]

        result = infer_deterministic(build_constraints(observation))

        self.assertEqual(
            result.safe_cells,
            {(1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2)},
        )
        self.assertEqual(result.mine_cells, frozenset())

    def test_remaining_count_equal_to_hidden_count_makes_all_mines(self):
        observation = [[F, H, H], [H, 8, H], [H, H, H]]

        result = infer_deterministic(build_constraints(observation))

        self.assertEqual(result.safe_cells, frozenset())
        self.assertEqual(
            result.mine_cells,
            {(1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2)},
        )

    def test_safe_and_mine_facts_coexist_and_flag_has_priority(self):
        observation = [[0, H, H, 3], [H, H, H, H]]

        result = infer_deterministic(build_constraints(observation))

        self.assertEqual(result.safe_cells, {(1, 0), (0, 1), (1, 1)})
        self.assertEqual(result.mine_cells, {(2, 0), (2, 1), (3, 1)})
        self.assertEqual(
            choose_deterministic_move(result), SimpleMove(Action.FLAG, 2, 0)
        )

    def test_multiple_constraints_deduplicate_safe_cells(self):
        constraints = build_constraints([[0, H, 0]])

        self.assertEqual(len(constraints), 2)
        self.assertEqual(
            infer_deterministic(constraints),
            InferenceResult(safe_cells={(1, 0)}, mine_cells=frozenset()),
        )

    def test_multiple_constraints_deduplicate_mine_cells(self):
        constraints = build_constraints([[1, H, 1]])

        self.assertEqual(len(constraints), 2)
        self.assertEqual(
            infer_deterministic(constraints),
            InferenceResult(safe_cells=frozenset(), mine_cells={(1, 0)}),
        )

    def test_flagged_cells_are_subtracted_and_excluded_from_hidden_cells(self):
        constraints = build_constraints([[F, 2, H], [H, H, H]])

        self.assertEqual(
            constraints,
            (Constraint((1, 0), 1, {(2, 0), (0, 1), (1, 1), (2, 1)}),),
        )

    def test_opened_numbers_are_not_hidden_cells(self):
        constraints = build_constraints([[1, F], [1, H]])

        self.assertEqual(
            constraints,
            (Constraint((0, 0), 0, {(1, 1)}), Constraint((0, 1), 0, {(1, 1)})),
        )

    def test_every_opened_number_from_zero_to_eight_creates_a_constraint(self):
        neighbors = {
            (0, 0), (1, 0), (2, 0), (0, 1),
            (2, 1), (0, 2), (1, 2), (2, 2),
        }
        for number in range(9):
            with self.subTest(number=number):
                self.assertEqual(
                    build_constraints([[H, H, H], [H, number, H], [H, H, H]]),
                    (Constraint((1, 1), number, neighbors),),
                )

    def test_corners_and_edges_only_include_in_bounds_neighbors(self):
        cases = (
            ((0, 0), {(1, 0), (0, 1), (1, 1)}),
            ((3, 0), {(2, 0), (2, 1), (3, 1)}),
            ((0, 2), {(0, 1), (1, 1), (1, 2)}),
            ((3, 2), {(2, 1), (3, 1), (2, 2)}),
            ((1, 0), {(0, 0), (2, 0), (0, 1), (1, 1), (2, 1)}),
            ((2, 2), {(1, 1), (2, 1), (3, 1), (1, 2), (3, 2)}),
            ((0, 1), {(0, 0), (1, 0), (1, 1), (0, 2), (1, 2)}),
            ((3, 1), {(2, 0), (3, 0), (2, 1), (2, 2), (3, 2)}),
        )
        for (x, y), neighbors in cases:
            with self.subTest(source=(x, y)):
                observation = [[H] * 4 for _ in range(3)]
                observation[y][x] = 0

                constraints = build_constraints(observation)

                self.assertEqual(constraints, (Constraint((x, y), 0, neighbors),))
                self.assertEqual(infer_deterministic(constraints).safe_cells, neighbors)

    def test_single_row_column_and_cell_observations(self):
        cases = (
            ([[0, H]], {(1, 0)}),
            ([[0], [H]], {(0, 1)}),
            ([[0]], frozenset()),
        )
        for observation, hidden_cells in cases:
            with self.subTest(observation=observation):
                self.assertEqual(
                    build_constraints(observation),
                    (Constraint((0, 0), 0, hidden_cells),),
                )

    def test_mine_tie_break_uses_row_then_column(self):
        result = InferenceResult(
            safe_cells=frozenset(), mine_cells={(0, 2), (3, 0), (1, 0)}
        )

        self.assertEqual(
            choose_deterministic_move(result), SimpleMove(Action.FLAG, 1, 0)
        )

    def test_safe_tie_break_uses_row_then_column(self):
        result = InferenceResult(
            safe_cells={(0, 2), (3, 0), (1, 0)}, mine_cells=frozenset()
        )

        self.assertEqual(
            choose_deterministic_move(result), SimpleMove(Action.OPEN, 1, 0)
        )

    def test_ambiguous_clue_returns_no_facts_and_no_move(self):
        result = infer_deterministic(build_constraints([[H, 1, H]]))

        self.assertEqual(result, InferenceResult(frozenset(), frozenset()))
        self.assertIsNone(choose_deterministic_move(result))

    def test_unopened_board_has_no_constraints_facts_or_first_move(self):
        for observation in ([[H]], [[H] * 9 for _ in range(9)], [[F, H]]):
            with self.subTest(observation=observation):
                constraints = build_constraints(observation)
                result = infer_deterministic(constraints)

                self.assertEqual(constraints, ())
                self.assertEqual(result, InferenceResult(frozenset(), frozenset()))
                self.assertIsNone(choose_deterministic_move(result))

    def test_negative_remaining_count_raises(self):
        for observation in ([[0, F]], [[0, F], [H, H]]):
            with self.subTest(observation=observation):
                with self.assertRaisesRegex(
                    InconsistentObservationError, r"\(0, 0\).*remaining_mines=-1"
                ):
                    build_constraints(observation)

    def test_remaining_count_above_hidden_count_raises(self):
        for observation in ([[2, H]], [[1]]):
            with self.subTest(observation=observation):
                with self.assertRaisesRegex(
                    InconsistentObservationError, r"\(0, 0\).*remaining_mines="
                ):
                    build_constraints(observation)

    def test_satisfied_constraint_without_hidden_cells_is_retained(self):
        constraints = build_constraints([[1, F]])

        self.assertEqual(constraints, (Constraint((0, 0), 0, frozenset()),))
        self.assertEqual(
            infer_deterministic(constraints), InferenceResult(frozenset(), frozenset())
        )

    def test_conflicting_safe_and_mine_inferences_raise(self):
        constraints = build_constraints([[0, H, 1]])

        with self.assertRaisesRegex(
            InconsistentObservationError, r"both safe and mine.*\(1, 0\)"
        ):
            infer_deterministic(constraints)

    def test_conflicting_result_cannot_be_constructed_for_move_selection(self):
        with self.assertRaisesRegex(InconsistentObservationError, "both safe and mine"):
            InferenceResult(safe_cells={(1, 0)}, mine_cells={(1, 0)})

    def test_repeated_observation_produces_same_result_and_move_without_mutation(self):
        observation = [[0, H, H, 3], [H, H, H, H]]
        original = deepcopy(observation)
        expected_constraints = build_constraints(observation)
        expected_result = infer_deterministic(expected_constraints)
        expected_move = SimpleMove(Action.FLAG, 2, 0)

        for _ in range(10):
            constraints = build_constraints(observation)
            result = infer_deterministic(constraints)
            self.assertEqual(constraints, expected_constraints)
            self.assertEqual(result, expected_result)
            self.assertEqual(choose_deterministic_move(result), expected_move)
            self.assertEqual(observation, original)

    def test_facts_are_not_propagated_until_a_new_observation_is_provided(self):
        result = infer_deterministic(build_constraints([[1, H, 1, H]]))

        self.assertEqual(result, InferenceResult(frozenset(), {(1, 0)}))
        self.assertEqual(
            choose_deterministic_move(result), SimpleMove(Action.FLAG, 1, 0)
        )

        new_result = infer_deterministic(build_constraints([[1, F, 1, H]]))

        self.assertEqual(new_result, InferenceResult({(3, 0)}, frozenset()))
        self.assertEqual(
            choose_deterministic_move(new_result), SimpleMove(Action.OPEN, 3, 0)
        )
        self.assertEqual(result, InferenceResult(frozenset(), {(1, 0)}))

    def test_subset_constraints_do_not_trigger_extra_inference(self):
        result = infer_deterministic(build_constraints([[1, 1, H], [H, H, H]]))

        self.assertEqual(result, InferenceResult(frozenset(), frozenset()))
        self.assertIsNone(choose_deterministic_move(result))

    def test_data_models_freeze_coordinate_sets_and_fields(self):
        cells = {(1, 0)}
        constraint = Constraint((0, 0), 0, cells)
        result = InferenceResult(cells, frozenset())
        move = choose_deterministic_move(result)
        cells.add((2, 0))

        self.assertEqual(constraint.hidden_cells, frozenset({(1, 0)}))
        self.assertEqual(result.safe_cells, frozenset({(1, 0)}))
        self.assertIsInstance(constraint.hidden_cells, frozenset)
        self.assertIsInstance(result.safe_cells, frozenset)
        self.assertIsInstance(result.mine_cells, frozenset)
        with self.assertRaises(FrozenInstanceError):
            constraint.remaining_mines = 1
        with self.assertRaises(FrozenInstanceError):
            result.safe_cells = frozenset()
        with self.assertRaises(FrozenInstanceError):
            move.x = 2

    def test_invalid_direct_constraint_counts_raise(self):
        for count in (-1, 2):
            with self.subTest(count=count):
                with self.assertRaises(InconsistentObservationError):
                    Constraint((0, 0), count, {(1, 0)})
        for count in (True, 0.0, "0"):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "must be an integer"):
                    Constraint((0, 0), count, {(1, 0)})

    def test_malformed_observation_shape_raises(self):
        for observation in ([], [[]], [[H], []], [[H], [H, H]], [H], None):
            with self.subTest(observation=observation):
                with self.assertRaises(ValueError):
                    build_constraints(observation)

    def test_unsupported_cell_values_including_game_over_states_raise(self):
        for value in (-6, -5, -4, -1, 9, True, 0.0, "0", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Unsupported observation value"):
                    build_constraints([[H, value]])

    def test_solver_runs_with_only_public_enums_available_from_engine_module(self):
        public_types = types.ModuleType("core_engine")
        public_types.Action = Action
        public_types.CellState = CellState
        observation = ((0, H, H, 3), (H, H, H, H))

        with patch.dict(sys.modules, {"core_engine": public_types}):
            solver = runpy.run_path(simple_algorithm.__file__)
            constraints = solver["build_constraints"](observation)
            result = solver["infer_deterministic"](constraints)
            move = solver["choose_deterministic_move"](result)

        self.assertEqual(result.safe_cells, {(1, 0), (0, 1), (1, 1)})
        self.assertEqual(result.mine_cells, {(2, 0), (2, 1), (3, 1)})
        self.assertEqual((move.action, move.x, move.y), (Action.FLAG, 2, 0))


if __name__ == "__main__":
    unittest.main()
