"""Bounded synthetic paired facts; no official evidence or real exemplar IDs."""

import ast
import inspect
import unittest
from dataclasses import FrozenInstanceError, replace
from enum import Enum
from fractions import Fraction
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import patch

import representative_boards as selector
from representative_boards import ExemplarCategory as Category, PairedGameFact


# Synthetic fixture identities are deliberately outside the official corpus.
SYNTHETIC_BASE = 10**12


def paired(offset, delta=None, stage2="WIN", stage3="WIN"):
    return PairedGameFact(SYNTHETIC_BASE + offset, stage2, stage3, delta)


def memberships(games):
    return {item.category: item.game for item in selector.select_exemplars(games)}


def mixed_facts():
    return (
        paired(40, -90), paired(20, -90), paired(80, -8), paired(30, -8),
        paired(90, 0), paired(10, 0), paired(60, 50), paired(50, 50), paired(70, 4),
        paired(120, stage3="LOSS"), paired(110, stage3="LOSS"),
        paired(140, stage2="LOSS"), paired(130, stage2="LOSS"),
        paired(160, stage2="LOSS", stage3="LOSS"),
        paired(150, stage2="LOSS", stage3="LOSS"),
    )


class ExemplarSelectionTests(unittest.TestCase):
    def test_all_eight_categories_have_stable_order_and_original_selected_records(self):
        facts = mixed_facts()
        result = selector.select_exemplars(facts)
        expected_categories = (
            Category.MAX_STAGE3_WW_ADVANTAGE, Category.MEDIAN_DELTA_WW,
            Category.CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE, Category.STAGE2_WW_ADVANTAGE,
            Category.EXACT_WW_TIE, Category.WL, Category.LW, Category.LL,
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(tuple(item.category for item in result), expected_categories)
        self.assertEqual(tuple(item.category.value for item in result), (
            "max_stage3_ww_advantage", "median_delta_ww", "closest_to_zero_stage3_ww_advantage",
            "stage2_ww_advantage", "exact_ww_tie", "wl", "lw", "ll",
        ))
        by_index = {game.game_index: game for game in facts}
        for item, offset in zip(result, (20, 10, 30, 50, 10, 110, 130, 150)):
            self.assertIs(item.game, by_index[SYNTHETIC_BASE + offset])

    def test_maximum_stage3_advantage_uses_minimum_negative_delta_then_lowest_index(self):
        expected = paired(4, -90)
        result = memberships((paired(8, -90), paired(2, -1), paired(1, 50), expected))
        self.assertIs(result[Category.MAX_STAGE3_WW_ADVANTAGE], expected)

    def test_odd_ww_population_uses_middle_of_all_sorted_ww(self):
        expected = paired(30, 0)
        result = memberships((
            paired(10, 8), paired(50, -9), paired(20, 6), expected, paired(40, -4),
            paired(1, stage3="LOSS"), paired(2, stage2="LOSS"),
        ))
        self.assertIs(result[Category.MEDIAN_DELTA_WW], expected)

    def test_even_ww_population_uses_lower_median_not_upper_or_average(self):
        expected = paired(30, -2)
        result = memberships((paired(10, 8), paired(50, -9), paired(20, 1), expected))
        self.assertIs(result[Category.MEDIAN_DELTA_WW], expected)

    def test_median_delta_ties_are_sorted_by_game_index_before_selecting_rank(self):
        facts = tuple(paired(offset, 5) for offset in (40, 10, 30, 20))
        selected = memberships(facts)[Category.MEDIAN_DELTA_WW]
        self.assertIs(selected, facts[-1])
        self.assertEqual(selected.game_index, SYNTHETIC_BASE + 20)

    def test_closest_to_zero_stage3_advantage_requires_negative_and_lowest_tied_index(self):
        expected = paired(4, -2)
        result = memberships((paired(8, -2), paired(1, 0), paired(2, 1), paired(3, -80), expected))
        self.assertIs(result[Category.CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE], expected)

    def test_stage2_advantage_uses_largest_positive_delta_then_lowest_index(self):
        expected = paired(4, 90)
        result = memberships((paired(8, 90), paired(1, 0), paired(2, -200), paired(3, 1), expected))
        self.assertIs(result[Category.STAGE2_WW_ADVANTAGE], expected)

    def test_exact_ww_tie_uses_only_zero_then_lowest_index(self):
        expected = paired(4, 0)
        result = memberships((paired(8, 0), paired(1, -1), paired(2, 1), expected))
        self.assertIs(result[Category.EXACT_WW_TIE], expected)

    def test_wl_lw_ll_use_lowest_index_and_stage2_is_first_outcome_letter(self):
        for category, stage2, stage3 in (
            (Category.WL, "WIN", "LOSS"), (Category.LW, "LOSS", "WIN"),
            (Category.LL, "LOSS", "LOSS"),
        ):
            expected = paired(5, stage2=stage2, stage3=stage3)
            facts = (paired(9, stage2=stage2, stage3=stage3), expected, paired(1, -999))
            with self.subTest(category=category):
                self.assertIs(memberships(facts)[category], expected)
                self.assertIsNone(expected.delta_us)

    def test_empty_input_retains_all_eight_empty_categories(self):
        result = selector.select_exemplars(())
        self.assertEqual(tuple(item.category for item in result), tuple(Category))
        self.assertEqual(len(result), 8)
        self.assertTrue(all(item.game is None for item in result))

    def test_empty_ww_population_does_not_borrow_non_ww_records(self):
        facts = (paired(1, stage3="LOSS"), paired(2, stage2="LOSS"),
                 paired(3, stage2="LOSS", stage3="LOSS"))
        result = selector.select_exemplars(facts)
        self.assertTrue(all(item.game is None for item in result[:5]))
        self.assertEqual(tuple(item.game for item in result[5:]), facts)

    def test_absent_sign_and_zero_categories_are_empty_without_substitution(self):
        for delta, populated in (
            (-7, {Category.MAX_STAGE3_WW_ADVANTAGE, Category.CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE}),
            (7, {Category.STAGE2_WW_ADVANTAGE}), (0, {Category.EXACT_WW_TIE}),
        ):
            expected = paired(1, delta)
            with self.subTest(delta=delta):
                for category, game in memberships((expected,)).items():
                    if category in populated | {Category.MEDIAN_DELTA_WW}:
                        self.assertIs(game, expected)
                    else:
                        self.assertIsNone(game)

    def test_missing_outcome_categories_stay_empty(self):
        result = memberships((paired(1, -9), paired(2, stage3="LOSS")))
        self.assertIsNotNone(result[Category.WL])
        self.assertIsNone(result[Category.LW])
        self.assertIsNone(result[Category.LL])

    def test_one_game_keeps_every_matching_category_membership(self):
        game = paired(1, -11)
        result = selector.select_exemplars((game,))
        matches = tuple(item.category for item in result if item.game is game)
        self.assertEqual(matches, (Category.MAX_STAGE3_WW_ADVANTAGE, Category.MEDIAN_DELTA_WW,
                                   Category.CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE))
        self.assertEqual(len(result), 8)

    def test_all_permutations_of_bounded_mixed_population_are_equal(self):
        facts = (paired(1, -4), paired(2, 0), paired(3, 8), paired(4, stage3="LOSS"),
                 paired(5, stage2="LOSS"), paired(6, stage2="LOSS", stage3="LOSS"))
        expected = selector.select_exemplars(facts)
        for order in permutations(facts):
            self.assertEqual(selector.select_exemplars(order), expected)

    def test_delta_and_outcome_ties_are_independent_of_full_fixture_order(self):
        facts = mixed_facts()
        expected = selector.select_exemplars(facts)
        for offset in range(len(facts)):
            rotated = facts[offset:] + facts[:offset]
            for order in (rotated, tuple(reversed(rotated))):
                self.assertEqual(selector.select_exemplars(order), expected)

    def test_integer_deltas_keep_precision_beyond_float_and_fixed_width_ranges(self):
        magnitude = 10**100
        most_negative, less_negative = paired(8, -magnitude - 1), paired(1, -magnitude)
        most_positive, less_positive = paired(9, magnitude + 1), paired(2, magnitude)
        result = memberships((less_negative, most_positive, less_positive, most_negative))
        self.assertIs(result[Category.MAX_STAGE3_WW_ADVANTAGE], most_negative)
        self.assertIs(result[Category.CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE], less_negative)
        self.assertIs(result[Category.MEDIAN_DELTA_WW], less_negative)
        self.assertIs(result[Category.STAGE2_WW_ADVANTAGE], most_positive)

    def test_duplicate_indices_rejected_for_identical_equivalent_and_conflicting_facts(self):
        game = paired(1, -7)
        for duplicate in (game, replace(game), replace(game, delta_us=8), paired(1, stage3="LOSS")):
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, "Duplicate game_index"):
                selector.select_exemplars((game, paired(2, 0), duplicate))

    def test_duplicate_non_ww_records_are_also_invalid(self):
        game = paired(1, stage2="LOSS", stage3="LOSS")
        with self.assertRaisesRegex(ValueError, "Duplicate game_index"):
            selector.select_exemplars((game, game))

    def test_game_index_rejects_bool_noninteger_and_negative_values(self):
        for value in (True, False, -1, 1.0, "1", None, Fraction(1), [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "game_index"):
                PairedGameFact(value, "WIN", "WIN", -1)

    def test_outcomes_require_exact_win_loss_strings_without_coercion(self):
        class OtherOutcome(str, Enum):
            WIN = "WIN"

        for name in ("stage2_outcome", "stage3_outcome"):
            for value in ("WON", "LOST", "win", "WIN ", "", None, True, 1, [], OtherOutcome.WIN):
                with self.subTest(field=name, value=value), self.assertRaisesRegex(ValueError, name):
                    replace(paired(1, -1), **{name: value})

    def test_ww_requires_delta_instead_of_defaulting_missing_to_zero(self):
        with self.assertRaisesRegex(ValueError, "WW requires"):
            PairedGameFact(SYNTHETIC_BASE + 1, "WIN", "WIN")

    def test_ww_delta_requires_integer_excluding_bool(self):
        for delta in (None, True, False, 0.0, -1.0, "0", Fraction(1), float("nan"), [], {}):
            with self.subTest(delta=delta), self.assertRaisesRegex(ValueError, "WW requires"):
                paired(1, delta)

    def test_non_ww_rejects_all_nonnull_deltas_including_zero(self):
        for stage2, stage3 in (("WIN", "LOSS"), ("LOSS", "WIN"), ("LOSS", "LOSS")):
            for delta in (-5, 0, 5, True, False, 0.0, "0", Fraction(1)):
                with self.subTest(outcomes=(stage2, stage3), delta=delta):
                    with self.assertRaisesRegex(ValueError, "Non-WW requires"):
                        paired(1, delta, stage2, stage3)

    def test_inappropriate_records_and_noniterable_inputs_fail_closed(self):
        for games in (None, 42, (None,), ({},), ((SYNTHETIC_BASE, "WIN", "WIN", -1),),
                      (SimpleNamespace(game_index=SYNTHETIC_BASE, stage2_outcome="WIN",
                                       stage3_outcome="WIN", delta_us=-1),)):
            with self.subTest(games=games), self.assertRaises(ValueError):
                selector.select_exemplars(games)

    def test_input_models_are_frozen_and_input_list_is_not_reordered_or_retained(self):
        facts = list(mixed_facts())
        before = tuple(facts)
        result = selector.select_exemplars(facts)
        self.assertEqual(tuple(facts), before)
        with self.assertRaises(FrozenInstanceError):
            facts[0].delta_us = 999
        facts.clear()
        self.assertEqual(result, selector.select_exemplars(before))

    def test_iterable_input_is_consumed_once_without_a_sort_in_place_requirement(self):
        facts = mixed_facts()
        self.assertEqual(selector.select_exemplars(iter(facts)), selector.select_exemplars(facts))
        self.assertEqual(selector.select_exemplars(set(facts)), selector.select_exemplars(facts))

    def test_output_tuple_and_nested_dataclasses_are_immutable(self):
        result = selector.select_exemplars((paired(1, -7),))
        with self.assertRaises(TypeError):
            result[0] = result[1]
        for name, value in (("category", Category.LL), ("game", None)):
            with self.subTest(field=name), self.assertRaises(FrozenInstanceError):
                setattr(result[0], name, value)
        with self.assertRaises(FrozenInstanceError):
            result[0].game.game_index = SYNTHETIC_BASE + 99

    def test_selector_has_no_io_or_runtime_dependencies_on_project_execution_or_evidence(self):
        facts = mixed_facts()
        expected = selector.select_exemplars(facts)
        with patch("builtins.open", side_effect=AssertionError("filesystem access")), \
                patch("io.open", side_effect=AssertionError("filesystem access")), \
                patch("builtins.__import__", side_effect=AssertionError("runtime dependency")):
            result = selector.select_exemplars(facts)
        self.assertEqual(result, expected)
        tree = ast.parse(inspect.getsource(selector))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        # Restrict the pure module to value-model/iteration standard-library
        # imports; no SQLite, filesystem, Qt, solver, Engine, Model C or timeline.
        self.assertLessEqual(imports, {"collections.abc", "dataclasses", "enum", "typing"})


if __name__ == "__main__":
    unittest.main()
