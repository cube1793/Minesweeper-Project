"""Exact probability persistence without connection-management responsibilities."""

import sqlite3
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from math import comb
from unittest.mock import patch

from telemetry_repository import decode_probability, encode_probability


class ProbabilityCodecTests(unittest.TestCase):
    def assert_round_trip(self, probability, expected_text=None):
        encoded = encode_probability(probability)
        if expected_text is not None:
            self.assertEqual(encoded, expected_text)
        decoded = decode_probability(encoded)
        self.assertIsInstance(decoded, Fraction)
        self.assertEqual(decoded, probability)
        self.assertEqual(encode_probability(decoded), encoded)
        return encoded

    def test_none_round_trip(self):
        self.assertIsNone(encode_probability(None))
        self.assertIsNone(decode_probability(None))

    def test_endpoints_and_ordinary_canonical_probabilities(self):
        fixtures = (
            (Fraction(0, 1), "0/1"),
            (Fraction(1, 1), "1/1"),
            (Fraction(1, 2), "1/2"),
            (Fraction(1, 3), "1/3"),
            (Fraction(2, 9), "2/9"),
        )
        for probability, text in fixtures:
            with self.subTest(text=text):
                self.assert_round_trip(probability, text)

    def test_encoding_uses_fraction_normalization(self):
        self.assert_round_trip(Fraction(2, 4), "1/2")
        self.assert_round_trip(Fraction(0, 99), "0/1")
        self.assert_round_trip(Fraction(-3, -3), "1/1")

    def test_encoding_rejects_non_fraction_types(self):
        for value in (0, 1, True, False, 0.5, Decimal("0.5"), "1/2", b"1/2", [], object()):
            with self.subTest(value=value), self.assertRaises(TypeError):
                encode_probability(value)

    def test_decoding_rejects_non_text_types(self):
        for value in (0, 1, True, 0.5, Decimal("0.5"), Fraction(1, 2), b"1/2", [], object()):
            with self.subTest(value=value), self.assertRaises(TypeError):
                decode_probability(value)

    def test_encoding_rejects_probabilities_outside_unit_interval(self):
        for value in (Fraction(-1, 2), Fraction(3, 2), Fraction(-1), Fraction(2)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                encode_probability(value)

    def test_decoding_rejects_malformed_or_noncanonical_text(self):
        invalid = (
            "", "0", "1", "1.0", "0.5", "+1/2", "-1/2", "1/+2", "1/-2",
            "-0/1", "00/1", "01/2", "1/02", "0/2", "2/4", "2/2", "2/1",
            "1/0", "0/0", "1/00", " 1/2", "1/2 ", "1 /2", "1/ 2", "1\t/2",
            "\t1/2", "1/2\n", "\n1/2", "1/\n2", "1/2\r\n", "1/2\x00",
            "1//2", "1/2/3", "/2", "1/", "1e0/2", "1_0/20", "a/b",
            "\u0661/2", "1/\u0662", "\uff11/\uff12", "\u00b9/2", "1\u20442",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_probability(value)

    def test_beyond_sqlite_signed_64_bit_round_trip(self):
        probability = Fraction(2**80 + 1, 2**81 + 1)
        self.assertGreater(probability.numerator, 2**63 - 1)
        self.assertGreater(probability.denominator, 2**63 - 1)
        self.assert_round_trip(probability)

    def test_representative_hundred_digit_round_trip(self):
        probability = Fraction(10**99 + 7, 10**100 + 9)
        self.assertGreaterEqual(len(str(probability.numerator)), 99)
        self.assertGreaterEqual(len(str(probability.denominator)), 100)
        self.assert_round_trip(probability)

    def test_large_integer_world_counts_round_trip(self):
        # Expert-board first-click exclusion leaves 479 cells and 99 mines.
        total_worlds = comb(479, 99)
        target_mined_worlds = comb(478, 98)
        self.assertGreater(len(str(total_worlds)), 100)
        self.assertGreater(target_mined_worlds, 2**63 - 1)
        self.assert_round_trip(Fraction(target_mined_worlds, total_worlds), "99/479")
        self.assert_round_trip(Fraction(1, total_worlds))

    def test_no_float_conversion_and_distinct_sub_float_precision_values(self):
        denominator = 10**100 + 9
        values = (Fraction(1, 3), Fraction(denominator - 1, denominator), Fraction(1))
        with patch.object(Fraction, "__float__", side_effect=AssertionError("No float conversion")):
            encoded = [self.assert_round_trip(value) for value in values]
        self.assertEqual(len(set(encoded)), len(values))
        self.assertLess(decode_probability(encoded[1]), decode_probability(encoded[2]))

    @unittest.skipUnless(hasattr(sys, "get_int_max_str_digits"), "Runtime has no integer-string limit")
    def test_integer_string_safety_setting_is_unchanged(self):
        original = sys.get_int_max_str_digits()
        with patch.object(sys, "set_int_max_str_digits", side_effect=AssertionError("Global mutation")):
            for value in (None, Fraction(0), Fraction(1), Fraction(10**99 + 7, 10**100 + 9)):
                self.assertEqual(decode_probability(encode_probability(value)), value)
            with self.assertRaises(ValueError):
                decode_probability("2/4")
            self.assertEqual(sys.get_int_max_str_digits(), original)
        self.assertEqual(sys.get_int_max_str_digits(), original)

    def test_every_accepted_small_canonical_text_reserializes_identically(self):
        for denominator in range(1, 31):
            for numerator in range(denominator + 1):
                probability = Fraction(numerator, denominator)
                text = f"{probability.numerator}/{probability.denominator}"
                with self.subTest(text=text):
                    self.assertEqual(encode_probability(decode_probability(text)), text)


class RationalTextSqlSemanticsTests(unittest.TestCase):
    def test_sqlite_text_order_and_minimum_are_not_rational_order(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE probabilities (probability TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO probabilities VALUES (?)", [("1/3",), ("2/9",)],
        )
        sql_order = [row[0] for row in connection.execute(
            "SELECT probability FROM probabilities ORDER BY probability",
        )]
        sql_minimum = connection.execute("SELECT MIN(probability) FROM probabilities").fetchone()[0]
        self.assertEqual(sql_order, ["1/3", "2/9"])
        self.assertEqual(sql_minimum, "1/3")
        rational_order = sorted(map(decode_probability, sql_order))
        self.assertEqual(rational_order, [Fraction(2, 9), Fraction(1, 3)])
        self.assertEqual(min(map(decode_probability, sql_order)), Fraction(2, 9))
        self.assertNotEqual(decode_probability(sql_minimum), rational_order[0])


if __name__ == "__main__":
    unittest.main()
