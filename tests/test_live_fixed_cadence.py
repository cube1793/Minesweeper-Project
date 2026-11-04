"""Independent integer oracle for one current fixed-period input."""
import unittest

from live_fixed_cadence import FixedCadence


class FixedCadenceTests(unittest.TestCase):
    def test_remaining_uses_actual_start_and_rounds_up(self):
        for interval in (0, 1, 16, 125, 200, 2000):
            for elapsed in (0, 1, 999999, 120000000, 200000000, 3000000000):
                with self.subTest(interval=interval, elapsed=elapsed):
                    start = 1000000000
                    remaining = max(0, interval * 1000000 - elapsed)
                    expected = remaining // 1000000 + bool(remaining % 1000000)
                    cadence = FixedCadence(interval, start)
                    self.assertEqual(cadence.deadline_ns, start + interval * 1000000)
                    self.assertEqual(cadence.remaining_ms(start + elapsed), expected)

    def test_late_input_starts_a_new_period_without_catchup(self):
        old = FixedCadence(200, 1000000000)
        self.assertEqual(old.remaining_ms(1900000000), 0)
        new = old.after_input(1900000000)
        self.assertEqual(new.deadline_ns, 2100000000)
        self.assertEqual(new.remaining_ms(1900000000), 200)
        self.assertEqual(new.transition_reason, 'late_restart')

    def test_invalid_values_are_rejected(self):
        for value in (-1, 2001, 1.0, True, None):
            with self.subTest(interval=value), self.assertRaises(ValueError):
                FixedCadence(value, 1)
        for value in (-1, 1.0, True, None):
            with self.subTest(start=value), self.assertRaises(ValueError):
                FixedCadence(200, value)
