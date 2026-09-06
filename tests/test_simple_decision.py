"""Position analysis fixtures contain visible values, never a mine layout."""

import inspect
import runpy
import sys
import types
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from fractions import Fraction
from unittest.mock import patch

import simple_algorithm
import simple_decision
import simple_probability
from core_engine import Action, CellState
from simple_algorithm import (
    InconsistentObservationError,
    InferenceResult,
    SimpleMove,
    build_constraints,
)
from simple_decision import DecisionKind, SimpleDecision, analyze_position
from simple_probability import CellProbability, ProbabilityResult


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value


class SimpleDecisionTests(unittest.TestCase):
    def test_local_safe_open_preserves_constraints_and_inference(self):
        observation = [[0, H]]

        decision = analyze_position(observation, 0)

        self.assertEqual(decision.kind, DecisionKind.LOCAL_DETERMINISTIC)
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 1, 0))
        self.assertEqual(decision.constraints, build_constraints(observation))
        self.assertEqual(decision.deterministic_result, InferenceResult({(1, 0)}, ()))
        self.assertIsNone(decision.probability_result)

    def test_local_mine_flag_retains_all_facts_and_mine_priority(self):
        decision = analyze_position([[0, H, H, 3], [H, H, H, H]], 3)

        self.assertEqual(decision.kind, DecisionKind.LOCAL_DETERMINISTIC)
        self.assertEqual(decision.move, SimpleMove(Action.FLAG, 2, 0))
        self.assertEqual(decision.deterministic_result.safe_cells, {(1, 0), (0, 1), (1, 1)})
        self.assertEqual(decision.deterministic_result.mine_cells, {(2, 0), (2, 1), (3, 1)})
        self.assertIsNone(decision.probability_result)

    def test_local_move_skips_both_probability_calculation_and_selection(self):
        with (
            patch("simple_decision.calculate_probabilities") as calculate,
            patch("simple_decision.choose_probability_move") as choose,
        ):
            for observation, mines in (
                ([[1, H]], 1), ([[0, H]], 0),
                ([[1, H, H, F]], 2), ([[F, 1, H]], 1),
            ):
                decision = analyze_position(observation, mines)
                self.assertEqual(decision.kind, DecisionKind.LOCAL_DETERMINISTIC)

        calculate.assert_not_called()
        choose.assert_not_called()

    def test_local_move_rejects_more_global_flags_than_total_mines(self):
        observation = [[1, H, H, F, F]]
        original = deepcopy(observation)

        with (
            patch("simple_decision.calculate_probabilities") as calculate,
            patch("simple_decision.choose_probability_move") as choose,
            self.assertRaisesRegex(InconsistentObservationError, "remaining_mines=-1"),
        ):
            analyze_position(observation, 1)

        calculate.assert_not_called()
        choose.assert_not_called()
        self.assertEqual(observation, original)

    def test_local_move_rejects_remaining_mines_exceeding_hidden_count(self):
        observation = [[1, H, 1]]
        original = deepcopy(observation)

        with (
            patch("simple_decision.calculate_probabilities") as calculate,
            patch("simple_decision.choose_probability_move") as choose,
            self.assertRaisesRegex(InconsistentObservationError, "remaining_mines=2"),
        ):
            analyze_position(observation, 2)

        calculate.assert_not_called()
        choose.assert_not_called()
        self.assertEqual(observation, original)

    def test_global_certain_mine_flags_before_certain_safe_cells(self):
        observation = ((H, 2, 2, H), (F, H, H, F))

        decision = analyze_position(observation, 4)

        self.assertEqual(decision.kind, DecisionKind.GLOBAL_CERTAINTY)
        self.assertEqual(decision.move, SimpleMove(Action.FLAG, 0, 0))
        self.assertEqual(decision.deterministic_result, InferenceResult((), ()))
        self.assertEqual(decision.constraints, build_constraints(observation))
        self.assertEqual(decision.probability_result.total_worlds, 1)
        self.assertEqual(
            tuple(cell.mine_worlds for cell in decision.probability_result.probabilities),
            (1, 1, 0, 0),
        )

    def test_global_zero_probability_safe_open(self):
        decision = analyze_position([[H, 1, H, H, H]], 1)

        self.assertEqual(decision.kind, DecisionKind.GLOBAL_CERTAINTY)
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 3, 0))
        self.assertEqual(decision.deterministic_result, InferenceResult((), ()))
        self.assertEqual(self.selected_probability(decision), Fraction(0))

    def test_uncertain_guess_opens_minimum_probability_including_floating_cells(self):
        decision = analyze_position([[H, 1, H, H, H, H]], 2)

        self.assertEqual(decision.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 3, 0))
        self.assertEqual(self.selected_probability(decision), Fraction(1, 3))
        self.assertEqual(decision.deterministic_result, InferenceResult((), ()))

    def test_unopened_observation_uses_fixed_layout_risk_without_first_click_policy(self):
        decision = analyze_position([[H, H], [H, H]], 1)

        self.assertEqual(decision.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 0, 0))
        self.assertEqual(decision.constraints, ())
        self.assertEqual(self.selected_probability(decision), Fraction(1, 4))

    def test_certainty_classification_uses_exact_counts_below_float_precision(self):
        # These uncertain fractions round to 0.0 / 1.0 if converted to float.
        denominator = 10**400
        for numerator in (0, 1, denominator - 1, denominator):
            with self.subTest(numerator=numerator):
                result = ProbabilityResult(
                    denominator, (CellProbability((0, 0), numerator, denominator),),
                    (), ((0, 0),),
                )
                with patch("simple_decision.calculate_probabilities", return_value=result):
                    decision = analyze_position([[H]], 0)

                certain = numerator in (0, denominator)
                expected_kind = (
                    DecisionKind.GLOBAL_CERTAINTY if certain
                    else DecisionKind.PROBABILITY_GUESS
                )
                self.assertEqual(decision.kind, expected_kind)
                self.assertIs(decision.probability_result, result)
                self.assertEqual(
                    decision.move.action, Action.FLAG if numerator == denominator else Action.OPEN,
                )

    def test_same_input_produces_same_decision_without_mutating_observation(self):
        for observation, mines in (
            ([[1, H]], 1),
            ([[H, 1, H, H, H]], 1),
            ([[H, 1, H, H, H]], 3),
            ([[H, 1, H]], 1),
        ):
            with self.subTest(observation=observation):
                original = deepcopy(observation)
                expected = analyze_position(observation, mines)
                for _ in range(5):
                    self.assertEqual(analyze_position(observation, mines), expected)
                    self.assertEqual(observation, original)

    def test_decision_is_frozen_and_copies_constraint_sequence(self):
        decision = analyze_position([[1, H]], 1)
        constraints = list(decision.constraints)
        copied = SimpleDecision(
            decision.kind, decision.move, constraints,
            decision.deterministic_result, decision.probability_result,
        )
        constraints.clear()

        self.assertEqual(copied, decision)
        self.assertIsInstance(copied.constraints, tuple)
        with self.assertRaises(FrozenInstanceError):
            copied.kind = DecisionKind.PROBABILITY_GUESS
        with self.assertRaises(FrozenInstanceError):
            copied.move.x = 0

    def test_consistent_position_without_hidden_cells_returns_none(self):
        for observation, mines in (([[0]], 0), ([[1, F]], 1)):
            with self.subTest(observation=observation):
                self.assertIsNone(analyze_position(observation, mines))

    def test_solver_inconsistencies_propagate_without_fallback(self):
        for observation, mines in (([[0, F]], 1), ([[H, 1, H, H, 1, H]], 1)):
            with self.subTest(observation=observation):
                with self.assertRaises(InconsistentObservationError):
                    analyze_position(observation, mines)

    def test_invalid_public_inputs_raise(self):
        for mines in (True, 0.0, "0", None, -1):
            with self.subTest(mines=mines):
                with self.assertRaises(ValueError):
                    analyze_position([[0, H]], mines)
        for observation in ([], [[]], [[H], []], [[CellState.MINE]], [[True]]):
            with self.subTest(observation=observation):
                with self.assertRaises(ValueError):
                    analyze_position(observation, 0)

    def test_public_signature_accepts_only_observation_and_total_mines(self):
        self.assertEqual(
            tuple(inspect.signature(analyze_position).parameters),
            ("observation", "num_mines"),
        )
        with self.assertRaises(TypeError):
            analyze_position([[H]], 0, snapshot=object())
        with self.assertRaises(TypeError):
            analyze_position([[H]], 0, engine=object())

    def test_analyzer_and_solvers_load_without_engine_snapshot_replay_or_zini(self):
        public_types = types.ModuleType("core_engine")
        public_types.Action = Action
        public_types.CellState = CellState
        blocked = {
            name: None for name in (
                "board_snapshot", "board_analyzer", "replay_model",
                "replay_recorder", "replay_player", "zini_core", "simple_runner",
            )
        }
        with patch.dict(sys.modules, {"core_engine": public_types, **blocked}):
            algorithm = types.ModuleType("simple_algorithm")
            algorithm.__dict__.update(runpy.run_path(simple_algorithm.__file__))
            with patch.dict(sys.modules, {"simple_algorithm": algorithm}):
                probability = types.ModuleType("simple_probability")
                probability.__dict__.update(runpy.run_path(simple_probability.__file__))
                with patch.dict(sys.modules, {"simple_probability": probability}):
                    analyzer = runpy.run_path(simple_decision.__file__)
                    for observation, mines, kind in (
                        ([[1, H]], 1, "LOCAL_DETERMINISTIC"),
                        ([[H, 1, H, H]], 1, "GLOBAL_CERTAINTY"),
                        ([[H, 1, H]], 1, "PROBABILITY_GUESS"),
                    ):
                        decision = analyzer["analyze_position"](observation, mines)
                        self.assertEqual(decision.kind.name, kind)

    @staticmethod
    def selected_probability(decision):
        return next(
            cell.probability for cell in decision.probability_result.probabilities
            if cell.coordinate == (decision.move.x, decision.move.y)
        )


if __name__ == "__main__":
    unittest.main()
