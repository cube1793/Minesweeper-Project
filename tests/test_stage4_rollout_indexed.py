"""Regression checks for the call-local indexed density hint."""

from dataclasses import asdict
from fractions import Fraction
import inspect
import unittest
from unittest.mock import patch

import stage4_rollout as rollout
from stage4_candidates import EvidenceInput
from stage4_policy import PolicyLimits
from tests import stage4_rollout_reference as reference


H, F = -2, -3


def semantic(result):
    fields = asdict(result)
    fields.pop("work")
    return fields


class IndexedPilotTests(unittest.TestCase):
    def compare(self, grid, mines, guess=True, **kwargs):
        actual = rollout.pilot_p0(grid, mines, 2, guess, **kwargs)
        expected = reference.pilot_p0(grid, mines, 2, guess, **kwargs)
        self.assertEqual(semantic(actual), semantic(expected))
        return actual

    def test_public_signature_and_version(self):
        self.assertEqual(tuple(inspect.signature(rollout.pilot_p0).parameters),
                         ("observation", "num_mines", "counted_inputs", "allow_guess", "max_work", "cancelled"))
        self.assertIsNone(rollout.pilot_p0.__closure__)
        self.assertEqual(rollout.PILOT_ID, "PUBLIC_LOCAL_COST_P0_V2_INDEXED_HINT")
        self.assertEqual(rollout.PILOT_WORK_ID, "P0_WORK_V2_RESIDUAL_CONSTRAINT_EDGES")

    def test_global_density_and_row_major_tie(self):
        result = self.compare(((H, H, H),), 1)
        self.assertEqual(result.risk_hint, Fraction(1, 3))
        self.assertEqual(result.sequence, (EvidenceInput("OPEN", 0, 0),))

    def test_flag_cost_breaks_equal_hint(self):
        result = self.compare(((F, H, F),), 1)
        self.assertEqual(result.sequence, (EvidenceInput("OPEN", 1, 0),))

    def test_lower_hint_precedes_unflag_cost(self):
        result = self.compare(((H, 1, H, F, F, F, F, F),), 2)
        self.assertEqual(result.sequence, (EvidenceInput("FLAG", 3, 0), EvidenceInput("OPEN", 3, 0)))

    def test_global_density_is_a_floor(self):
        result = self.compare(((H, 1, H, 1, H, H, H),), 2)
        self.assertEqual(result.risk_hint, Fraction(2, 5))
        self.assertEqual(result.sequence, (EvidenceInput("OPEN", 5, 0),))

    def test_safe_priority_and_flag_preparation(self):
        result = self.compare(((F, 0, H),), 0)
        self.assertEqual(result.reason, "PROVEN_SAFE_COST")
        self.assertEqual(result.sequence, (EvidenceInput("OPEN", 2, 0),))
        shared = ((1, 1, 0), (H, 1, H), (H, H, H))
        prepared = self.compare(shared, 1)
        self.assertEqual(prepared.sequence, (EvidenceInput("FLAG", 0, 1), EvidenceInput("CHORD", 1, 1)))

    def test_empty_constraints_and_density_reuse(self):
        grid = ((0, 0, 0, 0), (1, 1, 1, 1), (H, H, H, H))
        with patch.object(rollout, "Fraction", wraps=Fraction) as fractions:
            result = rollout.pilot_p0(grid, 2, 2, True)
        self.assertEqual(fractions.call_count, 5)
        with patch.object(reference, "Fraction", wraps=Fraction) as old_fractions:
            expected = reference.pilot_p0(grid, 2, 2, True)
        self.assertEqual(old_fractions.call_count, 14)
        self.assertEqual(semantic(result), semantic(expected))

    def test_zero_work_and_cancellation(self):
        for function in (rollout.pilot_p0, reference.pilot_p0):
            zero = function(((H, H),), 1, 0, True, max_work=0)
            self.assertEqual((zero.status, zero.reason, zero.work, zero.sequence),
                             ("PILOT_UNRESOLVED", "PILOT_WORK_LIMIT", 0, ()))
            stopped = function(((H, H),), 1, 0, True, cancelled=lambda: True)
            self.assertEqual((stopped.reason, stopped.work, stopped.sequence), ("CANCELLED", 0, ()))

    def test_bad_callback_and_exception(self):
        def broken():
            raise RuntimeError("callback failure")

        for callback in (lambda: 1, lambda: None, broken):
            result = self.compare(((H, H),), 1, cancelled=callback)
            self.assertEqual(result.status, "ERROR")
            self.assertFalse(result.sequence)

    def test_guess_cap_boundary_counts_initialization_and_selection(self):
        complete = rollout.pilot_p0(((H, H, H),), 1, 0, True)
        self.assertEqual(complete.work, 21)
        for cap in (complete.work - 1, complete.work, complete.work + 1):
            result = rollout.pilot_p0(((H, H, H),), 1, 0, True, max_work=cap)
            self.assertLessEqual(result.work, cap)
            self.assertEqual(result.status, "PILOT_UNRESOLVED" if cap < complete.work else "READY")
            if cap < complete.work:
                self.assertIsNone(result.risk_hint)
                self.assertFalse(result.sequence)

    def test_inference_cap_and_partial_facts_preserved(self):
        row = tuple(H if i % 2 == 0 else 1 for i in range(479)) + (0,)
        result = self.compare((row,), 120)
        self.assertFalse(result.inference_complete)
        self.assertTrue(result.proven_safe)
        for cap in (0, 1, 480, 481, 700, 1200, 3000):
            self.compare((row,), 120, max_work=cap)

    def test_guess_off_and_no_viable_open(self):
        stalled = self.compare(((H, 1, H),), 1, guess=False)
        self.assertEqual(stalled.reason, "LOCAL_RULES_STALLED_GUESS_OFF")
        exhausted = self.compare(((H,),), 1)
        self.assertEqual(exhausted.reason, "NO_VIABLE_LOCAL_OPEN")

    def test_cache_is_rebuilt_for_every_call(self):
        first = rollout.pilot_p0(((H, H, H),), 1, 0, True)
        second = self.compare(((H, H, H),), 2)
        self.assertEqual(second.risk_hint, Fraction(2, 3))
        again = rollout.pilot_p0(((H, H, H),), 1, 0, True)
        self.assertEqual(first, again)
        self.assertEqual(first.work, again.work)

    def test_per_call_cap_and_aggregate_profile_validation(self):
        for bad in (-1, True, 20_001, 2_000_000):
            with self.assertRaises(ValueError):
                rollout.pilot_p0(((H, H),), 1, 0, True, max_work=bad)
        self.assertEqual(PolicyLimits().pilot_work, 10_000_000)
        self.assertEqual(rollout.RolloutLimits().max_pilot_work, 10_000_000)
        self.assertEqual(PolicyLimits(pilot_work=30_000_000).pilot_work, 30_000_000)
        self.assertEqual(rollout.RolloutLimits(max_pilot_work=30_000_000).max_pilot_work, 30_000_000)
        for bad in (-1, True, 30_000_001):
            with self.assertRaises(ValueError):
                PolicyLimits(pilot_work=bad)
            with self.assertRaises(ValueError):
                rollout.RolloutLimits(max_pilot_work=bad)


if __name__ == "__main__":
    unittest.main()
