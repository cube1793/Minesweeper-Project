"""Exact viewing arithmetic, independent of Qt, workers and model totals."""
from fractions import Fraction
import unittest

from live_pacing import (PacingRate, PacingWait, decimal_display,
                         interval_ms_from_cps, cps_from_interval_ms)


class PacingTests(unittest.TestCase):
    def test_fixed_cps_exact_examples_half_up_and_applied_value(self):
        for cps, interval in (('4', 250), ('2', 500), ('10', 100), ('8', 125),
                              ('0.5', 2000), ('1000', 1), ('3', 333),
                              ('2000/667', 334), ('2000/1999', 1000)):
            with self.subTest(cps=cps):
                self.assertEqual(interval_ms_from_cps(cps), interval)
                self.assertEqual(cps_from_interval_ms(interval), Fraction(1000, interval))
        self.assertEqual(decimal_display(cps_from_interval_ms(333)), ('3.003003', True))
        self.assertIsNone(cps_from_interval_ms(0))
        for interval in (1, 2, 3, 16, 125, 180, 250, 333, 667, 1999, 2000):
            with self.subTest(interval=interval):
                self.assertEqual(interval_ms_from_cps(cps_from_interval_ms(interval)), interval)

    def test_fixed_cps_rejects_invalid_and_outside_integer_ms_domain(self):
        for value in ('0', '-1', '', 'NaN', 'Inf', '-inf', '0.499999', '1000.00001',
                      '1/0', '1e3', True, None, 4.0):
            with self.subTest(cps=value):
                with self.assertRaises(ValueError):
                    interval_ms_from_cps(value)
        for value in (-1, 2001, True, '250', 250.0, None):
            with self.subTest(interval=value):
                with self.assertRaises(ValueError):
                    cps_from_interval_ms(value)

    def test_reference_cases_exact_and_ceiling(self):
        # Independent reference values sealed by the preparation, including
        # same-cell floor, diagonal and the extreme frozen-table displacement.
        for cost, delays in ((126005, (2521, 505, 253, 127, 16)),
                             (144891, (2898, 580, 290, 145, 19)),
                             (394196, (7884, 1577, 789, 395, 50)),
                             (578005, (11561, 2313, 1157, 579, 73))):
            for rate, delay in zip(('0.05', '0.25', '0.5', '1', '8'), delays):
                with self.subTest(cost=cost, rate=rate):
                    setting = PacingRate(rate)
                    wait = PacingWait(cost, setting, 200)
                    self.assertEqual(wait.exact_us, Fraction(cost) / Fraction(rate))
                    self.assertEqual(wait.delay_ms, delay)
                    self.assertEqual(wait.deadline_ns, 200 + delay * 1_000_000)
                    self.assertEqual(wait.remaining_ms(wait.deadline_ns - 1), 1)
                    self.assertEqual(wait.remaining_ms(wait.deadline_ns), 0)
                    self.assertEqual(wait.remaining_ms(wait.deadline_ns + 10), 0)

    def test_four_cps_is_exact_and_not_every_distance(self):
        rate = PacingRate.from_cps('4')
        self.assertEqual(rate.rate, Fraction(25201, 50000))
        self.assertEqual(rate.rate, Fraction('0.50402'))
        self.assertEqual(rate.cps, 4)
        self.assertEqual(rate.duration_us(126005), 250000)
        self.assertNotEqual(rate.duration_us(394196), 250000)
        self.assertEqual(decimal_display(PacingRate('0.5').cps, 3), ('3.968', True))

    def test_rate_and_cps_boundaries_and_invalid_values(self):
        for rate in ('0.05', '8', '1', '1/4'):
            with self.subTest(rate=rate):
                setting = PacingRate(rate)
                self.assertEqual(PacingRate.from_cps(setting.cps), setting)
        for value in ('0', '-1', '0.04999999', '8.0000001', 'NaN', 'inf', '-inf',
                      '1/0', '', '1e999999999', True, None, .5, float('nan'), float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    PacingRate(value)
                with self.assertRaises(ValueError):
                    PacingRate.from_cps(value if value not in ('8.0000001',) else '100')

    def test_bad_cost_is_not_a_normal_delay_and_positive_minimum_is_one(self):
        for cost in (0, -1, True, 1.5, None):
            with self.subTest(cost=cost):
                with self.assertRaises(ValueError):
                    PacingWait(cost, PacingRate(), 0).delay_ms
        self.assertEqual(PacingWait(1, PacingRate('8'), 0).delay_ms, 1)

    def test_display_rounding_is_not_authority(self):
        setting = PacingRate('0.05')
        for _ in range(50):
            text, approximate = decimal_display(setting.cps)
            self.assertTrue(approximate)
            self.assertEqual(text, '0.39681')
            self.assertEqual(setting.rate, Fraction(1, 20))
        self.assertEqual(decimal_display(Fraction('0.50402')), ('0.50402', False))
