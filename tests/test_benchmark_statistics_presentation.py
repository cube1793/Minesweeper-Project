"""Exact values stay separate from localized display and screen coordinates."""

import ast
import sys
import unittest
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import benchmark_statistics_presentation as presentation


class PresentationTests(unittest.TestCase):
    def test_localization_keys_defaults_and_explicit_errors(self):
        self.assertEqual(set(presentation.TEXT["ko"]), set(presentation.TEXT["en"]))
        self.assertEqual(presentation.DEFAULT_LANGUAGE, "ko")
        self.assertEqual(presentation.text("title"), "벤치마크 통계")
        self.assertEqual(presentation.text("title", "en"), "Benchmark Statistics")
        with self.assertRaises(ValueError):
            presentation.text("title", "fr")
        with self.assertRaises(KeyError):
            presentation.text("unknown_key")

    def test_exact_fraction_rates_and_means_do_not_need_floats(self):
        with patch.object(Fraction, "__float__", side_effect=AssertionError("No display float needed")):
            self.assertEqual(presentation.format_fraction(Fraction(2, 9)), "2/9")
            self.assertEqual(presentation.format_fraction(Fraction(1)), "1/1")
            self.assertEqual(presentation.format_rate(Fraction(19, 50)), "19/50 (38.00%)")
            self.assertEqual(presentation.format_rate(Fraction(1, 3)), "1/3 (33.33%)")
            self.assertEqual(presentation.format_mean(Fraction(99, 25)), "99/25 (≈ 3.96)")
            huge = Fraction(10**100 + 7, 10**101 + 9)
            self.assertTrue(presentation.format_rate(huge).startswith(presentation.format_fraction(huge)))
        for function in (presentation.format_fraction, presentation.format_rate,
                         presentation.format_mean, presentation.format_nanoseconds):
            self.assertEqual(function(None), "—")

    def test_nanosecond_unit_boundaries_and_exact_fraction_mean(self):
        for value, expected in (
            (0, "0 ns"), (999, "999 ns"), (1000, "1.000 µs"),
            (999999, "999.999 µs"), (1000000, "1.000 ms"),
            (999999999, "1000.000 ms"), (1000000000, "1.000 s"),
            (3020000000, "3.020 s"), (Fraction(95, 8), "95/8 ns (≈ 11.875 ns)"),
        ):
            with self.subTest(value=value):
                self.assertEqual(presentation.format_nanoseconds(value), expected)
        with self.assertRaises(ValueError):
            presentation.format_nanoseconds(-1)

    def test_discrete_points_keep_zero_and_numeric_order_immutable(self):
        distribution = ((0, 6), (2, 10), (11, 3))
        points = presentation.discrete_points(distribution)
        self.assertEqual(tuple((point.x, point.count) for point in points), distribution)
        self.assertIsInstance(points, tuple)
        with self.assertRaises(FrozenInstanceError):
            points[0].count = 1
        self.assertEqual(presentation.discrete_points(()), ())

    def test_exact_probability_order_large_fractions_and_float_collisions(self):
        a = Fraction(10**99 + 7, 10**100 + 9)
        b = Fraction(10**99 + 8, 10**100 + 9)
        distribution = ((a, 1), (b, 2), (Fraction(2, 9), 4), (Fraction(1, 3), 3))
        before = tuple(distribution)
        points = presentation.probability_points(distribution)
        self.assertEqual(tuple(point.x for point in points), tuple(sorted(point.x for point in points)))
        self.assertLess(points[2].x, points[3].x)
        self.assertEqual(tuple(point.exact_label for point in points[2:]), ("2/9", "1/3"))
        self.assertEqual(points[0].x, points[1].x)
        self.assertNotEqual(points[0].probability, points[1].probability)
        self.assertEqual(len(points), 4)  # Never merge by approximate X.
        for (risk, count), point in zip(distribution, points):
            self.assertIs(point.probability, risk)
            self.assertEqual(point.x, float(risk * 100))
            self.assertEqual(point.count, count)
            self.assertEqual(point.exact_label, f"{risk.numerator}/{risk.denominator}")
        self.assertEqual(distribution, before)
        with self.assertRaises(FrozenInstanceError):
            points[0].x = 0
        self.assertIn("2/9", presentation.probability_detail(points[2]))
        self.assertIn("Event count: 4", presentation.probability_detail(points[2], "en"))

    def test_percent_coordinates_preserve_fractional_precision_and_exact_details(self):
        distribution = ((Fraction(0), 1), (Fraction(1, 130), 2), (Fraction(1), 3))
        points = presentation.probability_points(distribution)
        self.assertEqual(tuple(point.x for point in points), (0.0, float(Fraction(10, 13)), 100.0))
        self.assertNotEqual(points[1].x, round(points[1].x))
        self.assertEqual(points[1].exact_label, "1/130")
        self.assertEqual(presentation.probability_detail(points[1], "en"),
                         "1/130 (0.77%)\nEvent count: 2")

    def test_presentation_dependency_direction(self):
        tree = ast.parse(Path(presentation.__file__).read_text(encoding="utf-8"))
        allowed = sys.stdlib_module_names | {"benchmark_statistics"}
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                self.assertIn(name.split(".")[0], allowed)


if __name__ == "__main__":
    unittest.main()
