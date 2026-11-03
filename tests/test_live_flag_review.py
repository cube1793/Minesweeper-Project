"""Small fixed public positions, with an independent tiny world check.

The independent enumerator is test-only and never contributes to a review or
selection.  These tests start no worker, engine trajectory, or public game.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import combinations
import json
import unittest
from unittest.mock import patch

from core_engine import CellState
import live_flag_review as review
from simple_algorithm import InconsistentObservationError, infer_deterministic


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
SPLIT = ((1, F, H, H, 0, F, H, F),)


def public_worlds(observation, num_mines):
    """Independently enumerate a tiny fixed view, treating every FLAG as closed."""
    height, width = len(observation), len(observation[0])
    closed = [(x, y) for y, row in enumerate(observation)
              for x, value in enumerate(row) if value in (H, F)]
    worlds = []
    for placement in combinations(closed, num_mines):
        mines = frozenset(placement)
        valid = True
        for y, row in enumerate(observation):
            for x, clue in enumerate(row):
                if clue in (H, F):
                    continue
                adjacent = sum((nx, ny) in mines
                               for ny in range(max(0, y - 1), min(height, y + 2))
                               for nx in range(max(0, x - 1), min(width, x + 2))
                               if (nx, ny) != (x, y))
                if adjacent != clue:
                    valid = False
        if valid:
            worlds.append(mines)
    return worlds


class FlagReviewTests(unittest.TestCase):
    def test_self_flag_is_not_its_own_proof_and_real_mine_can_be_unverified(self):
        observation = ((F, 1, H),)
        report = review.review_flags(observation, 1)
        self.assertEqual(report.view, ((H, 1, H),))
        self.assertEqual(report.proved_mine, ())
        self.assertEqual(report.proved_safe, ())
        self.assertEqual(report.unverified, ((0, 0),))
        self.assertEqual(report.classification((0, 0)), review.UNVERIFIED)
        worlds = public_worlds(observation, 1)
        self.assertEqual(len(worlds), 2)
        # The flagged cell really is a mine in one valid placement.  That fact
        # is an expectation check here, never an input to the runtime review.
        self.assertTrue(any((0, 0) in world for world in worlds))
        self.assertTrue(any((0, 0) not in world for world in worlds))

    def test_two_flags_are_both_removed_from_every_inference_assumption(self):
        observation = ((F, 1, H, 1, F),)
        for num_mines in (1, 2):
            with self.subTest(num_mines=num_mines):
                report = review.review_flags(observation, num_mines)
                self.assertEqual(report.view, ((H, 1, H, 1, H),))
                self.assertEqual(report.proved_mine, ())
                self.assertEqual(report.proved_safe, ())
                self.assertEqual(report.unverified, ((0, 0), (4, 0)))
                worlds = public_worlds(observation, num_mines)
                self.assertEqual(len(worlds), 1)
                self.assertEqual({(0, 0), (4, 0)} <= worlds[0], num_mines == 2)

    def test_partition_proves_only_direct_mine_safe_and_leaves_other_flags_unverified(self):
        report = review.review_flags(SPLIT, 2)
        self.assertEqual(report.flags, ((1, 0), (5, 0), (7, 0)))
        self.assertEqual(report.proved_mine, ((1, 0),))
        self.assertEqual(report.proved_safe, ((5, 0),))
        self.assertEqual(report.unverified, ((7, 0),))
        self.assertEqual(report.removable, ((5, 0), (7, 0)))
        self.assertEqual(report.classification((1, 0)), review.PROVED_MINE)
        self.assertEqual(report.classification((5, 0)), review.PROVED_SAFE)
        self.assertEqual(report.classification((7, 0)), review.UNVERIFIED)
        self.assertEqual(report.scope, "LOCAL_DIRECT_WITH_TOTAL_V1")

    def test_public_total_zero_and_all_are_valid_independent_proof_witnesses(self):
        safe = review.review_flags(((F, H),), 0)
        mines = review.review_flags(((1, F, F),), 2)
        self.assertEqual(safe.proved_safe, ((0, 0),))
        self.assertEqual(mines.proved_mine, ((1, 0), (2, 0)))
        self.assertEqual(mines.removable, ())

    def test_physical_flag_count_is_not_subtracted_from_public_mine_budget(self):
        report = review.review_flags(((F, 1, F),), 1)
        self.assertEqual(report.unverified, ((0, 0), (2, 0)))
        self.assertEqual(report.proved_mine, ())

    def test_local_success_does_not_claim_propagation_or_exact_completion(self):
        observation = ((F, 1, H, 1, F, 0, H),)
        with patch("simple_probability.calculate_probabilities", side_effect=AssertionError("no exact")), \
             patch("simple_decision.analyze_position", side_effect=AssertionError("no second solver")), \
             patch("live_flag_review.infer_deterministic", wraps=infer_deterministic) as infer:
            report = review.review_flags(observation, 1)
        infer.assert_called_once()
        self.assertEqual(report.proved_safe, ((4, 0),))
        self.assertEqual(report.unverified, ((0, 0),))
        worlds = public_worlds(observation, 1)
        self.assertEqual(len(worlds), 1)
        self.assertNotIn((0, 0), worlds[0])  # Stronger proof exists; scope remains direct only.

    def test_direct_proofs_agree_with_independent_complete_placements_on_fixed_tiny_views(self):
        cases = ((SPLIT, 2), (((F, 1, H),), 1), (((F, 1, H, 1, F),), 1),
                 (((F, 1, H, 1, F),), 2), (((F, H),), 0), (((1, F, F),), 2))
        for observation, num_mines in cases:
            with self.subTest(observation=observation, num_mines=num_mines):
                report = review.review_flags(observation, num_mines)
                worlds = public_worlds(observation, num_mines)
                self.assertTrue(worlds)
                for cell in report.proved_mine:
                    self.assertTrue(all(cell in world for world in worlds))
                for cell in report.proved_safe:
                    self.assertTrue(all(cell not in world for world in worlds))

    def test_review_detaches_without_mutating_input_and_result_is_frozen(self):
        observation = [[CellState.FLAGGED, 1, CellState.HIDDEN]]
        before = deepcopy(observation)
        report = review.review_flags(observation, 1)
        self.assertEqual(observation, before)
        observation[0][0] = 0
        self.assertEqual(report.view, ((H, 1, H),))
        self.assertTrue(all(type(value) is int for row in report.view for value in row))
        with self.assertRaises(FrozenInstanceError):
            report.flags = ()

    def test_classifier_failures_are_not_replaced_by_unverified_results(self):
        for function in ("build_constraints", "infer_deterministic"):
            for error in (RuntimeError("review failed"), TimeoutError("review timeout")):
                with self.subTest(function=function, error=type(error).__name__), \
                     patch("live_flag_review." + function, side_effect=error), \
                     self.assertRaises(type(error)) as raised:
                    review.review_flags(((F, 1, H),), 1)
                self.assertIs(raised.exception, error)

    def test_detected_direct_and_public_budget_contradictions_propagate(self):
        for observation, num_mines in ((((1, F, 0),), 1), (((1, F, H, F, 1),), 1),
                                      (((2, F),), 1), (((0, F, H),), 2)):
            with self.subTest(observation=observation), self.assertRaises(InconsistentObservationError):
                review.review_flags(observation, num_mines)

    def test_review_rejects_malformed_and_truth_or_counter_shaped_input(self):
        bad_observations = ((), [], [[]], [[H], [H, H]], [[True, H]], [[-2.0, H]],
                            [[-5, H]], [[H] * 31], [[H, H]] * 17,
                            {"observation": [[F, H]], "active_right": 1}, object())
        for observation in bad_observations:
            with self.subTest(observation=observation), self.assertRaises(review.FlagReviewError):
                review.review_flags(observation, 1)
        for mines in (True, 1.0, -1, 2, "1"):
            with self.subTest(mines=mines), self.assertRaises(review.FlagReviewError):
                review.review_flags(((F, H),), mines)

    def test_no_flags_is_an_empty_partition_not_an_implicit_physical_change(self):
        report = review.review_flags(((H, 1, H),), 1)
        self.assertEqual((report.flags, report.proved_mine, report.proved_safe,
                          report.unverified, report.removable), ((), (), (), (), ()))


class FlagReviewValueTests(unittest.TestCase):
    def setUp(self):
        self.report = review.review_flags(SPLIT, 2)

    def test_strict_wire_roundtrip_contains_only_public_proof_data(self):
        wire = review.report_to_dict(self.report)
        self.assertEqual(review.report_from_dict(json.loads(json.dumps(wire))), self.report)
        self.assertEqual(set(wire), {"width", "height", "num_mines", "view", "view_identity", "flags",
                                    "proved_mine", "proved_safe", "unverified", "scope"})

    def test_view_identity_excludes_physical_flag_assumptions_but_flags_are_separately_bound(self):
        left = review.review_flags(((F, 1, H),), 1)
        right = review.review_flags(((H, 1, F),), 1)
        self.assertEqual(left.view_identity, right.view_identity)
        self.assertNotEqual(left.flags, right.flags)
        with self.assertRaises(review.FlagReviewError):
            review.validate_review_current(left, ((H, 1, F),), 1)

    def test_reuse_accepts_only_same_public_view_and_eligible_flag_removals(self):
        observation = [list(row) for row in SPLIT]
        with patch("live_flag_review.infer_deterministic", side_effect=AssertionError("reuse cannot infer")):
            self.assertIs(review.validate_review_current(self.report, observation, 2), self.report)
            for x, y in self.report.removable:
                observation[y][x] = H
                self.assertIs(review.validate_review_current(self.report, observation, 2), self.report)
            self.assertEqual(observation[0][1], F)

    def test_reuse_rejects_proved_mine_removal_new_flag_reveal_or_mine_count_change(self):
        mutations = ((1, H), (2, F), (2, 1), (0, 0))
        for x, value in mutations:
            observation = [list(row) for row in SPLIT]
            observation[0][x] = value
            with self.subTest(x=x, value=value), self.assertRaises(review.FlagReviewError):
                review.validate_review_current(self.report, observation, 2)
        with self.assertRaises(review.FlagReviewError):
            review.validate_review_current(self.report, SPLIT, 3)

    def test_wire_rejects_missing_extra_truth_fields_bool_shapes_and_unknown_scope(self):
        wire = review.report_to_dict(self.report)
        for field in tuple(wire):
            invalid = dict(wire)
            del invalid[field]
            with self.subTest(missing=field), self.assertRaises(review.FlagReviewError):
                review.report_from_dict(invalid)
        for field in ("layout", "adjacent", "active_flag", "wasted_flag", "run_id"):
            with self.subTest(extra=field), self.assertRaises(review.FlagReviewError):
                review.report_from_dict({**wire, field: []})
        invalid_values = (("width", True), ("height", 1.0), ("num_mines", True),
                          ("scope", "EXACT_ALL"), ("view_identity", "0" * 64),
                          ("view", self.report.view), ("flags", self.report.flags),
                          ("unverified", [[True, 0]]), ("proved_safe", [[5, False]]))
        for name, value in invalid_values:
            with self.subTest(name=name), self.assertRaises(review.FlagReviewError):
                review.report_from_dict({**wire, name: value})

    def test_wire_rejects_duplicate_unsorted_incomplete_or_overlapping_partition(self):
        wire = review.report_to_dict(self.report)
        invalid_values = (("flags", [[1, 0], [1, 0], [5, 0], [7, 0]]),
                          ("flags", [[7, 0], [5, 0], [1, 0]]),
                          ("unverified", []), ("unverified", [[1, 0], [7, 0]]),
                          ("proved_safe", [[2, 0], [5, 0]]), ("flags", [[1, 0]] * 481))
        for name, value in invalid_values:
            with self.subTest(name=name, value=value[:5]), self.assertRaises(review.FlagReviewError):
                review.report_from_dict({**wire, name: value})

    def test_wire_direct_witness_check_rejects_forged_mine_safe_and_all_unverified(self):
        wire = review.report_to_dict(self.report)
        partitions = (([[7, 0]], [[5, 0]], [[1, 0]]),
                      ([[1, 0]], [[7, 0]], [[5, 0]]),
                      ([], [], [[1, 0], [5, 0], [7, 0]]))
        with patch("live_flag_review.infer_deterministic", side_effect=AssertionError("DTO cannot infer")):
            for mine, safe, unknown in partitions:
                with self.subTest(mine=mine, safe=safe), self.assertRaises(review.FlagReviewError):
                    review.report_from_dict({**wire, "proved_mine": mine,
                                             "proved_safe": safe, "unverified": unknown})

    def test_value_rejects_nonpublic_view_and_unknown_classification_target(self):
        invalid_views = (((1, F, H, H, 0, H, H, H),),
                         ((True, H, H, H, 0, H, H, H),),
                         ((1, H, H, H, 0, H, H, H), (H,) * 8))
        for view in invalid_views:
            with self.subTest(view=view), self.assertRaises(review.FlagReviewError):
                replace(self.report, view=view)
        for target in ((0, 0), [1, 0], (True, 0), (1, False), (9, 0), "1,0"):
            with self.subTest(target=target), self.assertRaises(review.FlagReviewError):
                self.report.classification(target)

    def test_row_major_removal_order_is_by_y_then_x_and_not_classification_group(self):
        # All physical flags are unverified in this no-clue view.
        report = review.review_flags(((H, F, F), (F, H, F)), 2)
        self.assertEqual(report.removable, ((1, 0), (2, 0), (0, 1), (2, 1)))


if __name__ == "__main__":
    unittest.main()
