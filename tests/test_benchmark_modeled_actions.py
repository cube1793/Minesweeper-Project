"""Model C's ordered-action seam needs no fabricated telemetry identity."""

import unittest
from unittest.mock import patch

from benchmark_modeled_time import (
    ModeledTimeValidationError, authenticate_model_c, evaluate_ordered_actions,
)
from core_engine import Action, GameStatus, MinesweeperEngine
from stage3_physical import action_cost


class OrderedModelCActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation = authenticate_model_c()

    def setUp(self):
        self.rows = (
            (0, Action.OPEN, 0, 0, GameStatus.PLAYING),
            (1, Action.FLAG, 1, 0, GameStatus.PLAYING),
            (2, Action.CHORD, 0, 0, GameStatus.WON),
        )

    def evaluate(self, rows=None, **overrides):
        options = dict(total_actions=3, terminal_status=GameStatus.WON,
                       width=2, height=1, evaluation=self.evaluation)
        options.update(overrides)
        return evaluate_ordered_actions(self.rows if rows is None else rows, **options)

    def test_exact_integer_cost_includes_initial_and_terminal_inputs_without_database(self):
        with patch("sqlite3.connect", side_effect=AssertionError("database")), \
             patch.object(MinesweeperEngine, "step", side_effect=AssertionError("reconstruction")), \
             patch("stage3_physical.load_timing_table", side_effect=AssertionError("reauthentication")):
            total = self.evaluate(iter(self.rows))
        self.assertIs(type(total), int)
        self.assertEqual(total, self.evaluation.table[0][0] + 2 * self.evaluation.table[1][0])
        self.assertEqual(total, sum(action_cost(self.evaluation.table, start, end) for start, end in (
            ((0, 0), (0, 0)), ((0, 0), (1, 0)), ((1, 0), (0, 0)),
        )))

    def test_single_winning_and_losing_inputs_both_have_the_initial_cost(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            with self.subTest(status=status):
                self.assertEqual(self.evaluate(
                    ((0, Action.OPEN, 0, 0, status),), total_actions=1, terminal_status=status,
                ), self.evaluation.table[0][0])

    def test_authentication_is_required(self):
        for evaluation in (None, self.evaluation.table, object()):
            with self.subTest(evaluation=type(evaluation)), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(evaluation=evaluation)

    def test_empty_missing_extra_and_wrong_count_streams_rejected(self):
        for rows, count in (((), 0), ((), 3), (self.rows[:-1], 3), (self.rows * 2, 3),
                            (self.rows, True), (self.rows, 3.0), (self.rows, -1)):
            with self.subTest(rows=rows, count=count), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(rows, total_actions=count)

    def test_action_indices_reject_gaps_duplicates_reordering_and_nonintegers(self):
        for index in (0, 2, -1, True, 1.0, "1"):
            rows = (self.rows[0], (index, *self.rows[1][1:]), self.rows[2])
            with self.subTest(index=index), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(rows)
        with self.assertRaises(ModeledTimeValidationError):
            self.evaluate(tuple(reversed(self.rows)))

    def test_only_actual_public_action_and_status_enums_are_accepted(self):
        for position, values in ((1, (0, True, "OPEN", None)), (4, (0, True, "PLAYING", None))):
            for value in values:
                first = list(self.rows[0])
                first[position] = value
                with self.subTest(position=position, value=value), self.assertRaises(ModeledTimeValidationError):
                    self.evaluate((tuple(first), *self.rows[1:]))

    def test_canonical_first_open_and_target_required(self):
        for action, x, y in ((Action.FLAG, 0, 0), (Action.CHORD, 0, 0), (Action.OPEN, 1, 0)):
            with self.subTest(action=action, target=(x, y)), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(((0, action, x, y, GameStatus.PLAYING), *self.rows[1:]))

    def test_early_terminal_incomplete_and_terminal_mismatch_rejected(self):
        for index, status in ((0, GameStatus.WON), (1, GameStatus.LOST),
                              (2, GameStatus.PLAYING), (2, GameStatus.LOST)):
            rows = list(self.rows)
            rows[index] = (*rows[index][:4], status)
            with self.subTest(index=index, status=status), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(rows)
        for status in (GameStatus.PLAYING, 1, True, "WON", None):
            with self.subTest(terminal_status=status), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(terminal_status=status)

    def test_dimensions_and_coordinate_domains_are_checked(self):
        for width, height in ((0, 1), (31, 1), (1, 17), (True, 1), (2, 1.0)):
            with self.subTest(dimensions=(width, height)), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(width=width, height=height)
        for x, y in ((2, 0), (1, 1), (-1, 0), (True, 0), (1, 0.0), ("1", 0)):
            with self.subTest(target=(x, y)), self.assertRaises(ModeledTimeValidationError):
                self.evaluate((self.rows[0], (1, Action.FLAG, x, y, GameStatus.PLAYING), self.rows[2]))

    def test_malformed_row_shapes_and_noniterable_input_rejected(self):
        for rows in (42, (None,), ((0, Action.OPEN),), ((0, Action.OPEN, 0, 0, GameStatus.WON, 99),)):
            with self.subTest(rows=rows), self.assertRaises(ModeledTimeValidationError):
                self.evaluate(rows)


if __name__ == "__main__":
    unittest.main()
