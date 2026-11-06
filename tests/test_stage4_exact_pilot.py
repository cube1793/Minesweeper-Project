"""New Q correctness, information-boundary and budget regression tests."""

from dataclasses import fields, replace
from fractions import Fraction
from math import comb
import inspect
import json
import unittest
from unittest.mock import patch

import stage4_exact_pilot as q
from stage4_candidates import EvidenceInput
from tests import stage4_pilot_oracle as oracle


H, F = -2, -3


class ExactPilotTests(unittest.TestCase):
    def query(self, grid, mines, guess=True, **kwargs):
        return q.ExactRequest(grid, mines, 2, guess, **kwargs)

    def test_shared_corner_exact_safety_fills_local_gap(self):
        grid = ((1, F, 1), (H, H, H), (1, H, 1))
        expected = oracle.posterior(grid, 1)
        result = q.choose_exact(self.query(grid, 1, False))
        self.assertEqual(expected["D"], 1)
        self.assertEqual(result.local_result.reason, "LOCAL_RULES_STALLED_GUESS_OFF")
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.basis, "UNIT4_EXACT_BASE")
        self.assertEqual(result.mine_probability, 0)
        self.assertEqual(result.base_result.base.total_worlds, 1)
        for positions in expected["layouts"]:
            replay = oracle.replay(grid, 1, positions,
                                   [(move.action, move.x, move.y) for move in result.sequence], 2)
            self.assertNotEqual(replay["outcome"], "LOST")
            self.assertGreater(sum(v >= 0 for row in replay["observation"] for v in row), 4)

    def test_same_density_different_exact_probabilities(self):
        grid = ((H, 1, H, 1, H, H, H),)
        result = q.choose_exact(self.query(grid, 2))
        expected = oracle.posterior(grid, 2)
        probabilities = {cell: Fraction(count, expected["D"]) for cell, count in expected["M"]}
        self.assertEqual(probabilities[(0, 0)], Fraction(1, 3))
        self.assertEqual(probabilities[(2, 0)], Fraction(2, 3))
        self.assertEqual(result.sequence, (EvidenceInput("OPEN", 0, 0),))
        self.assertEqual(result.mine_probability, Fraction(1, 3))
        self.assertEqual({row.coordinate: row.probability for row in result.base_result.base.marginals},
                         probabilities)

    def test_flagged_minimum_risk_includes_unflag_cost(self):
        grid = ((H, 1, H, F, F, F, F, F),)
        result = q.choose_exact(self.query(grid, 2))
        self.assertEqual(result.sequence, (EvidenceInput("FLAG", 3, 0), EvidenceInput("OPEN", 3, 0)))
        self.assertEqual(result.mine_probability, Fraction(1, 5))
        equal = q.choose_exact(self.query(((F, H, F),), 1))
        self.assertEqual(equal.sequence, (EvidenceInput("OPEN", 1, 0),))

    def test_fast_proof_and_safe_flag_release(self):
        result = q.choose_exact(self.query(((F, 0),), 0, False))
        self.assertEqual(result.sequence, (EvidenceInput("FLAG", 0, 0), EvidenceInput("OPEN", 0, 0)))
        self.assertEqual((result.basis, result.backend_calls), ("BASIC_RULES", 0))
        self.assertIsNone(result.base_result)

    def test_guess_off_requires_exact_absence(self):
        result = q.choose_exact(self.query(((H, 1, H),), 1, False))
        self.assertEqual((result.status, result.reason, result.terminal_outcome),
                         ("DEFER", "GUESS_BLOCKED", "GUESS_BLOCKED"))
        self.assertEqual(result.base_result.base.total_worlds, 2)
        self.assertEqual(result.sequence, ())

    def test_no_viable_precedes_guess_blocked(self):
        for guess in (True, False):
            result = q.choose_exact(self.query(((H,),), 1, guess))
            self.assertEqual((result.status, result.reason), ("DEFER", "NO_VIABLE_OPEN"))
            self.assertIsNone(result.terminal_outcome)
            self.assertFalse(result.sequence)

    def test_zero_and_partial_work_are_null(self):
        for limits in (q.ExactLimits(local_work=0), q.ExactLimits(exact_work=0),
                       q.ExactLimits(max_seconds=0), q.ExactLimits(local_work=1),
                       q.ExactLimits(exact_work=1)):
            result = q.choose_exact(self.query(((H, 1, H),), 1, limits=limits))
            self.assertEqual(result.status, "INSUFFICIENT")
            self.assertFalse(result.sequence)
            self.assertIsNone(result.mine_probability)
            self.assertIsNone(result.terminal_outcome)
            self.assertLessEqual(result.local_work, limits.local_work)
            self.assertLessEqual(result.exact_work, limits.exact_work)

    def test_cancellation_callback_errors_and_backend_exception(self):
        request = self.query(((H, 1, H),), 1)
        cancelled = q.choose_exact(request, cancelled=lambda: True)
        self.assertEqual(cancelled.status, "CANCELLED")
        for callback in (lambda: 1, lambda: None):
            result = q.choose_exact(request, cancelled=callback)
            self.assertEqual(result.status, "ERROR")
            self.assertFalse(result.sequence)
        with patch.object(q, "count_public", side_effect=RuntimeError("registered backend failure")):
            result = q.choose_exact(request)
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.backend_calls, 1)
        self.assertFalse(result.sequence)
        self.assertIsNone(result.mine_probability)

    def test_local_and_exact_contradiction(self):
        result = q.choose_exact(self.query(((2, H),), 1))
        self.assertEqual(result.status, "INCONSISTENT_INPUT")
        self.assertIsNone(result.terminal_outcome)
        # Odd cycle of three pair constraints has no integer placement.
        grid = ((1, H, 1), (H, H, H), (1, H, 2))
        expected = oracle.posterior(grid, 1)
        self.assertEqual(expected["D"], 0)
        result = q.choose_exact(self.query(grid, 1))
        self.assertEqual(result.status, "INCONSISTENT_INPUT")
        self.assertFalse(result.sequence)

    def test_large_integer_and_fraction_encoding(self):
        grid = tuple((H,) * 30 for _ in range(16))
        result = q.choose_exact(self.query(grid, 99))
        self.assertEqual(result.base_result.base.total_worlds, comb(480, 99))
        self.assertGreater(result.base_result.base.total_worlds, 2**53)
        self.assertEqual(result.mine_probability, Fraction(99, 480))
        payload = result.to_dict()
        self.assertEqual(payload["base_result"]["base"]["total_worlds"], str(comb(480, 99)))

    def test_payload_round_trip_preserves_limit_numeric_type(self):
        for seconds in (2, 2.0):
            original = q.ExactRequest(((H, F),), 1, 2**65, True,
                                      limits=q.ExactLimits(max_seconds=seconds))
            restored = q.ExactRequest.from_payload(json.loads(json.dumps(original.to_payload())))
            self.assertEqual(original, restored)
            self.assertIs(type(restored.limits.max_seconds), type(seconds))
            self.assertEqual(original.identity, restored.identity)
        self.assertNotEqual(self.query(((H, H),), 1, limits=q.ExactLimits(max_seconds=2)).identity,
                            self.query(((H, H),), 1, limits=q.ExactLimits(max_seconds=2.0)).identity)

    def test_public_dto_rejects_hidden_fields_and_invalid_types(self):
        request = self.query(((H, H),), 1)
        for forbidden in ("mines", "layout", "bbbv", "active_clicks", "rank", "episode_key", "engine"):
            payload = request.to_payload()
            payload[forbidden] = 0
            with self.assertRaises((TypeError, ValueError)):
                q.ExactRequest.from_payload(payload)
        payload = request.to_payload()
        payload["limits"]["layout"] = []
        with self.assertRaises((TypeError, ValueError)):
            q.ExactRequest.from_payload(payload)
        with self.assertRaises((TypeError, ValueError)):
            self.query(((True, H),), 1)
        with self.assertRaises((TypeError, ValueError)):
            q.ExactRequest(((H, H),), 1, True, True)
        self.assertEqual(tuple(inspect.signature(q.choose_exact).parameters), ("request", "cancelled"))
        self.assertNotIn("target", {field.name for field in fields(q.ExactRequest)})

    def test_complete_base_cache_is_bounded_public_and_cancellable(self):
        pilot = q.ExactPilot(cache_entries=1)
        request = self.query(((H, 1, H),), 1)
        first = pilot.choose(request)
        second = pilot.choose(replace(request, counted_inputs=7))
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual((second.backend_calls, second.exact_work), (0, 0))
        self.assertEqual(first.base_result, second.base_result)
        limited = pilot.choose(replace(request, limits=q.ExactLimits(exact_work=0)))
        self.assertEqual(limited.status, "INSUFFICIENT")
        cancelled = pilot.choose(request, cancelled=lambda: True)
        self.assertEqual(cancelled.status, "CANCELLED")
        changed = pilot.choose(replace(request, observation=((F, 1, H),)))
        self.assertFalse(changed.cache_hit)
        self.assertEqual(changed.cache_entries, 1)
        pilot.clear()
        self.assertFalse(pilot.choose(request).cache_hit)
        unsupported = pilot.choose(replace(request, prior_id="unregistered"))
        self.assertEqual(unsupported.status, "UNSUPPORTED")

    def test_failed_base_is_not_cached(self):
        pilot = q.ExactPilot()
        low = self.query(((H, 1, H),), 1, limits=q.ExactLimits(exact_work=1))
        self.assertEqual(pilot.choose(low).cache_entries, 0)
        result = pilot.choose(replace(low, limits=q.ExactLimits()))
        self.assertEqual(result.status, "READY")
        self.assertFalse(result.cache_hit)

    def test_same_public_state_from_distinct_oracle_worlds(self):
        grid = ((H, 1, H),)
        first = oracle.World(grid, 1, ((0, 0),))
        second = oracle.World(grid, 1, ((2, 0),))
        results = [q.choose_exact(self.query(world.observation, 1)) for world in (first, second)]
        self.assertEqual(results[0].request_id, results[1].request_id)
        self.assertEqual(results[0].sequence, results[1].sequence)
        self.assertEqual(results[0].mine_probability, results[1].mine_probability)


if __name__ == "__main__":
    unittest.main()

